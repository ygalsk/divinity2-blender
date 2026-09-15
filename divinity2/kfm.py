"""The animation set (`.kfm`, and the copy inside a `.cat`).

A KFM is the manifest that ties a family together: which skeleton its clips
were made for, which `.kf` files hold them, and how one animation gives way to
another. Divinity II ships one per weapon set -- `Human_F_Base.kfm`,
`Human_F_Base_BOW.kfm`, `Human_F_Melee_2HSW.kfm` -- and bundles a copy of the
character's own into its `.cat` as `MdlMan::CAMDataEntry`, which `nif.xml`
describes as "a KFM without header".

The format is not ours to work out. NifTools describes it in `kfm.xml`
(`niftools/kfmxml`), the same way `nif.xml` describes NIF, and Divinity II
writes version **2.2.0.0b** (`0x0202000B`). This module implements that
description and nothing beyond it:

    Kfm             header string, unknown byte, NIF file name, master,
                    2 ints, 2 floats, animation count, animations, 1 int
    Animation       event code, KF file name, index, transitions
    Transition      animation, type, and -- unless the type is 5 --
                    duration, intermediate animations, text key pair count

At this version an animation carries **no name**, only an event code: the
`ver2="16927488"` on the `Name` field means it was dropped after 1.2.4b. Clip
names come from the `NiControllerSequence` blocks in the `.kf` itself. What
the KFM adds is which file, and which skeleton.
"""

import re
import struct
from dataclasses import dataclass, field

#: What the file calls itself. Divinity II writes 2.2.0.0b.
HEADER = b";Gamebryo KFM File Version"

#: Transition types that carry nothing after their two ints.
#:
#: `kfm.xml` says only type 5 is bare. Divinity II writes type 4 bare as
#: well: over the 121 animation sets in the game, the description's own rule
#: parses 77 of them to the exact byte and treating 4 as bare parses 105.
#: Types 1 and 2 do carry the payload -- 4 and 598 occurrences.
BARE_TRANSITIONS = frozenset({4, 5})


class Truncated(ValueError):
    """The bytes ran out before the structure did."""


class _Reader:
    def __init__(self, data: bytes, at: int = 0):
        self.data = data
        self.at = at

    def _take(self, count: int) -> bytes:
        end = self.at + count
        if end > len(self.data):
            raise Truncated(f"wanted {count} bytes at {self.at}")
        chunk = self.data[self.at : end]
        self.at = end
        return chunk

    def int32(self) -> int:
        return struct.unpack("<i", self._take(4))[0]

    def float32(self) -> float:
        return struct.unpack("<f", self._take(4))[0]

    def byte(self) -> int:
        return self._take(1)[0]

    def string(self) -> str:
        """A SizedString: a 32-bit length, then that many bytes."""
        length = self.int32()
        if not 0 <= length <= len(self.data) - self.at:
            raise Truncated(f"string of {length} at {self.at}")
        return self._take(length).decode("cp1252", "replace")


@dataclass
class Transition:
    """How one animation gives way to another."""

    animation: int
    type: int
    duration: float = 0.0
    events: list = field(default_factory=list)
    text_key_pairs: int = 0


@dataclass
class Animation:
    """One entry: an event code, the file its clips live in, its transitions."""

    event_code: int
    kf_file: str
    index: int
    transitions: list = field(default_factory=list)


@dataclass
class AnimationSet:
    """A whole KFM.

    `complete` says whether the transition lists were read to the end. The
    header and the animations' file references are what this add-on needs and
    they come first, so a set that stops early is still usable -- sixteen of
    the game's sets do, and every one of them has already named all its `.kf`
    files by then.
    """

    skeleton: str = ""
    master: str = ""
    animations: list = field(default_factory=list)
    complete: bool = True

    #: The bytes it was read from, so an incomplete set can be scanned.
    source: bytes = b""

    @property
    def kf_files(self) -> list[str]:
        """The `.kf` files this set uses, each once, in the order they appear."""
        seen = []
        for animation in self.animations:
            if animation.kf_file and animation.kf_file not in seen:
                seen.append(animation.kf_file)
        if not self.complete:
            for name in named_kf_files(self.source):
                if name not in seen:
                    seen.append(name)
        return seen


def _transition(reader: _Reader) -> Transition:
    animation = reader.int32()
    kind = reader.int32()
    if kind in BARE_TRANSITIONS:
        return Transition(animation=animation, type=kind)

    duration = reader.float32()
    events = []
    for _ in range(reader.int32()):
        reader.int32()  # the intermediate animation's unknown int
        events.append(reader.string())
    return Transition(
        animation=animation,
        type=kind,
        duration=duration,
        events=events,
        text_key_pairs=reader.int32(),
    )


def _body(reader: _Reader) -> AnimationSet:
    """Everything after the header string and the unknown byte."""
    out = AnimationSet(
        skeleton=reader.string(), master=reader.string(), source=reader.data
    )
    reader.int32()
    reader.int32()
    reader.float32()
    reader.float32()

    count = reader.int32()
    if not 0 <= count <= len(reader.data) // 8:
        raise Truncated(f"{count} animations in {len(reader.data)} bytes")

    for _ in range(count):
        mark = reader.at
        try:
            animation = Animation(
                event_code=reader.int32(),
                kf_file=reader.string(),
                index=reader.int32(),
            )
            animation.transitions = [
                _transition(reader) for _ in range(reader.int32())
            ]
        except (Truncated, struct.error, UnicodeError):
            # Stop where the bytes stop agreeing rather than throw away the
            # animations already read. See AnimationSet.complete.
            reader.at = mark
            out.complete = False
            break
        out.animations.append(animation)
    return out


#: Any printable run that ends in `.kf`, for the tail of a set that stopped.
_KF_NAME = re.compile(rb"[\x20-\x7e]{4,}")


def named_kf_files(data: bytes) -> list[str]:
    """Every `.kf` name the bytes mention, in order, each once.

    The fallback for the four animation sets whose transition lists stop
    before they have named their own file. It is a string scan, which is
    weaker than a parse -- it is used only where the parse ran out, and only
    for names it can check against the disk afterwards.
    """
    seen = []
    for match in _KF_NAME.finditer(data):
        text = match.group().decode("cp1252", "replace")
        if text.lower().endswith(".kf") and text not in seen:
            seen.append(text)
    return seen


def read(data: bytes) -> AnimationSet:
    """Parse a `.kfm` file's bytes."""
    if not data.startswith(HEADER):
        raise ValueError("not a KFM")
    start = data.index(b"\n") + 1
    reader = _Reader(data, start)
    reader.byte()  # present from 2.0.0.0b onwards
    return _body(reader)


def read_headerless(data: bytes) -> AnimationSet:
    """Parse a `MdlMan::CAMDataEntry`, which starts straight at the body."""
    return _body(_Reader(data))
