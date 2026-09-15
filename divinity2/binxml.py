"""Larian's binary XML, enough of it to read one descriptor.

Most of this game's `.xml` files are not text. They are a tree with the
element and attribute names replaced by a 32-bit hash, packed into an
`xml::dom::CStreamableNode` block inside a NIF container -- so a `.xml` here is
neither XML nor, on its own, readable.

The add-on needs exactly one of them: `Terrain.xml`, which is the only place
the ground's textures are named. So this reads the format and asks for
attributes **by name**, hashing the name to compare. No table of recovered
names is needed and none is shipped.

The hash is `h = h * 33 + c` over the name's bytes, latin-1, starting at zero.

The format has no block-size oracle, so the header's three counts are the
check: the walk must land on the last byte of the block and agree with the
declared node, attribute and string counts. A misread layout would have to
get all four right by accident.
"""

import struct
from dataclasses import dataclass, field
from functools import lru_cache

#: Node flag bits. The low four are the only ones the format uses.
HAS_CHILDREN = 0x01
HAS_ATTRIBUTES = 0x02
HAS_TEXT = 0x04
NARROW_COUNTS = 0x08
KNOWN_FLAGS = 0x0F

#: A NIF container always starts with this.
NIF_MAGIC = b"Gamebryo File Format"


class Malformed(ValueError):
    pass


@lru_cache(maxsize=4096)
def hash_of(name: str) -> int:
    """Larian's 32-bit name hash. Case-sensitive."""
    h = 0
    for c in name.encode("latin-1"):
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


@dataclass
class Node:
    name_hash: int
    attributes: dict = field(default_factory=dict)  # hash -> str
    children: list = field(default_factory=list)
    text: str = ""

    def is_a(self, name: str) -> bool:
        return self.name_hash == hash_of(name)

    def get(self, name: str, default=None):
        return self.attributes.get(hash_of(name), default)

    def find_all(self, name: str):
        """Every descendant with this element name, in document order."""
        want = hash_of(name)
        stack = [self]
        while stack:
            node = stack.pop()
            if node.name_hash == want:
                yield node
            stack += reversed(node.children)


def payload(data: bytes) -> bytes:
    """The one block inside the NIF wrapper.

    The header is: the version line, then a version word, an endian byte, a
    user version, the block count, the type table, one type index per block,
    one size per block, and a string-table pair. Only its length matters here.
    """
    if not data.startswith(NIF_MAGIC):
        raise Malformed("not a NIF container")
    at = data.index(b"\n") + 1
    at += 4 + 1 + 4                                     # version, endian, user
    (blocks,), at = struct.unpack_from("<I", data, at), at + 4
    (types,), at = struct.unpack_from("<H", data, at), at + 2
    for _ in range(types):
        (n,), at = struct.unpack_from("<I", data, at), at + 4
        at += n
    at += 2 * blocks                                    # type index per block
    sizes = struct.unpack_from(f"<{blocks}I", data, at)
    at += 4 * blocks
    (strings,), at = struct.unpack_from("<I", data, at), at + 4
    at += 4                                             # max string length
    for _ in range(strings):
        (n,), at = struct.unpack_from("<I", data, at), at + 4
        at += n
    (groups,), at = struct.unpack_from("<I", data, at), at + 4
    at += 4 * groups
    if blocks != 1:
        raise Malformed(f"expected one block, found {blocks}")
    return data[at:at + sizes[0]]


def read(data: bytes) -> Node:
    """Parse a whole `.xml` file -- NIF wrapper and all -- into its root node."""
    block = payload(data) if data.startswith(NIF_MAGIC) else data
    if len(block) < 12:
        raise Malformed("block is too short for the three header counts")
    n_nodes, n_attrs, n_strings = struct.unpack_from("<III", block, 0)
    at = 12
    table = block[at:at + n_strings]
    at += n_strings
    # Every string is NUL-terminated, so the split leaves a trailing empty.
    strings = table.split(b"\x00")[:-1] if n_strings else []

    state = {"at": at, "next": 0, "nodes": 0, "attrs": 0}

    def take() -> str:
        if state["next"] >= len(strings):
            raise Malformed("a node wants a value and the strings are used up")
        state["next"] += 1
        return strings[state["next"] - 1].decode("utf-8", "surrogateescape")

    def count(flags: int) -> int:
        if flags & NARROW_COUNTS:
            state["at"] += 1
            return block[state["at"] - 1]
        state["at"] += 4
        return struct.unpack_from("<I", block, state["at"] - 4)[0]

    def node() -> Node:
        at = state["at"]
        if at >= len(block):
            raise Malformed("ran off the end of the block")
        flags = block[at]
        if flags & ~KNOWN_FLAGS:
            raise Malformed(f"unknown flag bits {flags:#04x}")
        name_hash, = struct.unpack_from("<I", block, at + 1)
        state["at"] = at + 5
        state["nodes"] += 1

        out = Node(name_hash=name_hash)
        if flags & HAS_TEXT:
            out.text = take()
        if flags & HAS_ATTRIBUTES:
            for _ in range(count(flags)):
                h, = struct.unpack_from("<I", block, state["at"])
                state["at"] += 4
                out.attributes[h] = take()
            state["attrs"] += len(out.attributes)
        for _ in range(count(flags) if flags & HAS_CHILDREN else 0):
            out.children.append(node())
        # The stream stores a node's children in reverse. Proven by the
        # engine's own readers: `CRpgStats_V2_Scenery::LoadXML`,
        # `CRpgStats_V2_Character::LoadXML`, `CRpgStats_V2_Item::LoadXML` and
        # `CGameLogic_Tree::LoadXML` all take `children[0]` as the position
        # and `children[1]` as the orientation, and every file has them the
        # other way round. The same reversal makes `LoadXML(NiMatrix3*)`,
        # which fills rows 0..2 from `children[0..2]`, come out with
        # determinant +1 instead of -1 on all 775 Banditcamp placements.
        out.children.reverse()
        return out

    root = node()
    if state["at"] != len(block):
        raise Malformed(f"consumed {state['at']} of {len(block)} bytes")
    if state["nodes"] != n_nodes:
        raise Malformed(f"walked {state['nodes']} nodes, header says {n_nodes}")
    if state["attrs"] != n_attrs:
        raise Malformed(f"read {state['attrs']} attributes, header says {n_attrs}")
    if state["next"] != len(strings):
        raise Malformed(f"used {state['next']} of {len(strings)} strings")
    return root
