"""Larian's binary XML: a tree with every name replaced by a 32-bit hash, in a NIF container.

A document is a NIF file of one `xml::dom::CStreamableNode` block. The block is
three counts, a table of NUL-terminated strings, then the nodes depth first.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from . import Dv2Error

NIF_MAGIC = b"Gamebryo File Format"
BLOCK_TYPE = "xml::dom::CStreamableNode"

HAS_CHILDREN = 0x01
HAS_ATTRIBUTES = 0x02
HAS_TEXT = 0x04
NARROW_COUNTS = 0x08
KNOWN_FLAGS = 0x0F


class BinXmlError(Dv2Error):
    pass


@dataclass
class Node:
    name_hash: int
    attributes: list[tuple[int, str]] = field(default_factory=list)
    text: str | None = None
    children: list["Node"] = field(default_factory=list)


def payload(data: bytes) -> bytes:
    """The one block of a NIF-wrapped binary XML file.

    The header at NIF 20.3.0.9: a version line, version, endianness, user
    version, block count, block type names, a type index and a size per block,
    the string table, then the groups. The block follows.
    """
    if not data.startswith(NIF_MAGIC):
        raise BinXmlError("not a NIF file - binary XML is always NIF-wrapped")
    try:
        pos = data.index(b"\n") + 1
        pos += 4                                   # version
        if data[pos] != 1:
            raise BinXmlError(f"big-endian NIF not supported (endian={data[pos]})")
        pos += 1 + 4                               # endianness, user version
        num_blocks, = struct.unpack_from("<I", data, pos); pos += 4
        num_types, = struct.unpack_from("<H", data, pos); pos += 2
        types = []
        for _ in range(num_types):
            n, = struct.unpack_from("<I", data, pos); pos += 4
            types.append(data[pos:pos + n].decode("latin-1")); pos += n
        pos += 2 * num_blocks                      # block type index
        sizes = struct.unpack_from(f"<{num_blocks}I", data, pos); pos += 4 * num_blocks
        num_strings, = struct.unpack_from("<I", data, pos); pos += 8   # and max length
        for _ in range(num_strings):
            n, = struct.unpack_from("<I", data, pos); pos += 4 + n
        num_groups, = struct.unpack_from("<I", data, pos); pos += 4 + 4 * num_groups
    except (struct.error, IndexError, ValueError) as exc:
        raise BinXmlError(f"truncated NIF header: {exc}") from None
    if types != [BLOCK_TYPE]:
        raise BinXmlError(f"not binary XML; this file holds {types}")
    if len(sizes) != 1:
        raise BinXmlError(f"expected one block, found {len(sizes)}")
    return data[pos:pos + sizes[0]]


def parse(data: bytes) -> Node:
    """The root node of the bytes of one `xml::dom::CStreamableNode` block."""
    if len(data) < 12:
        raise BinXmlError("block is too short to hold the three header counts")
    n_nodes, n_attrs, n_strings = struct.unpack_from("<III", data, 0)
    pos = 12
    if pos + n_strings > len(data):
        raise BinXmlError(f"string table claims {n_strings} bytes, block has "
                          f"{len(data) - pos}")
    table = data[pos:pos + n_strings]
    pos += n_strings

    # The last string is NUL-terminated too, so the split leaves a trailing
    # empty element that is not a string.
    strings = table.split(b"\x00")[:-1] if n_strings else []

    at, next_string, nodes, attrs = pos, 0, 0, 0

    def take_string() -> str:
        nonlocal next_string
        if next_string >= len(strings):
            raise BinXmlError(
                f"node {nodes} wants a value but all {len(strings)} "
                "strings are already spoken for"
            )
        next_string += 1
        # Larian's files are UTF-8 where they are anything, but a handful of
        # strings are not valid UTF-8 at all; surrogateescape keeps their bytes.
        return strings[next_string - 1].decode("utf-8", errors="surrogateescape")

    def count(flags: int) -> int:
        nonlocal at
        if flags & NARROW_COUNTS:
            at += 1
            return data[at - 1]
        at += 4
        return struct.unpack_from("<I", data, at - 4)[0]

    def node() -> Node:
        nonlocal at, nodes, attrs
        if at >= len(data):
            raise BinXmlError("ran off the end of the block")
        flags = data[at]
        if flags & ~KNOWN_FLAGS:
            raise BinXmlError(
                f"node at offset {at} has flag bits {flags:#04x}; only the low "
                "four are known, so the rest of the walk would be a guess"
            )
        h, = struct.unpack_from("<I", data, at + 1)
        at += 5
        nodes += 1

        out = Node(name_hash=h)
        if flags & HAS_TEXT:
            out.text = take_string()
        if flags & HAS_ATTRIBUTES:
            for _ in range(count(flags)):
                ah, = struct.unpack_from("<I", data, at)
                at += 4
                out.attributes.append((ah, take_string()))
            attrs += len(out.attributes)
        n_child = count(flags) if flags & HAS_CHILDREN else 0
        for _ in range(n_child):
            out.children.append(node())
        return out

    try:
        root = node()
    except struct.error as exc:
        raise BinXmlError(f"ran off the end of the block: {exc}") from None

    if at != len(data):
        raise BinXmlError(f"consumed {at} of {len(data)} bytes")
    if nodes != n_nodes:
        raise BinXmlError(f"walked {nodes} nodes, header declares {n_nodes}")
    if attrs != n_attrs:
        raise BinXmlError(f"read {attrs} attributes, header declares {n_attrs}")
    if next_string != len(strings):
        raise BinXmlError(f"used {next_string} of {len(strings)} strings")
    return root
