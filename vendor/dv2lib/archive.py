"""The `.dv2` archive: a directory of paths, then each file stored raw or zlib-compressed."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

from . import Dv2Error

HEADER_SIZE_V5 = 22
DIR_ENTRY_SIZE = 12


class ArchiveError(Dv2Error):
    """Malformed archive, or a structural assumption did not hold."""


class UnsupportedVersion(ArchiveError):
    """Archive version we deliberately refuse to parse."""


@dataclass(frozen=True)
class Entry:
    """One file inside an archive."""

    path: str
    """Original path, backslash-separated, relative to the game data dir."""

    offset: int
    """Offset RELATIVE to Header.data_start. Add data_start for a file seek."""

    packed_size: int
    """Size of the bytes as stored in the archive."""

    unpacked_size: int
    """Size after decompression. Zero means the entry is stored raw."""

    @property
    def is_compressed(self) -> bool:
        return self.unpacked_size != 0

    def posix_path(self) -> str:
        return self.path.replace("\\", "/")


@dataclass(frozen=True)
class Header:
    version: int
    unknown_a: int  # V5 only. Always 1 across all 533 shipped archives.
    unknown_b: int  # V5 only. Always 4 across all 533 shipped archives.
    align_32k: int  # 0 -> data_start is 32K-aligned; 1 -> packed tight.
    unknown_d: int  # Always 1 across all 533 shipped archives.
    data_start: int
    string_space: int


class Archive:
    """Reader for a `.dv2` container."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._fh: BinaryIO = self.path.open("rb")
        try:
            self.header = self._read_header()
            self.entries = self._read_directory()
        except Exception:
            self._fh.close()
            raise

    def __enter__(self) -> "Archive":
        return self

    def __exit__(self, *exc: object) -> None:
        self._fh.close()

    def __iter__(self) -> Iterator[Entry]:
        return iter(self.entries)

    def _read_header(self) -> Header:
        raw = self._fh.read(4)
        if len(raw) < 4:
            raise ArchiveError(f"{self.path}: too short to be an archive")
        (version,) = struct.unpack("<I", raw)

        if version == 4:
            raise UnsupportedVersion(
                f"{self.path}: archive version 4 (the original Ego Draconis) is not "
                "implemented -- no V4 test corpus is available. Use the Developer's Cut."
            )
        if version != 5:
            raise UnsupportedVersion(f"{self.path}: unknown archive version {version}")

        rest = self._fh.read(HEADER_SIZE_V5 - 4)
        if len(rest) < HEADER_SIZE_V5 - 4:
            raise ArchiveError(f"{self.path}: truncated header")
        unknown_a, unknown_b, align_32k, unknown_d, data_start, string_space = (
            struct.unpack("<IIBBII", rest)
        )
        return Header(version, unknown_a, unknown_b, align_32k, unknown_d, data_start, string_space)

    def _read_directory(self) -> list[Entry]:
        blob = self._fh.read(self.header.string_space)
        if len(blob) != self.header.string_space:
            raise ArchiveError(f"{self.path}: truncated string table")
        # Trailing NUL produces an empty final element; drop empties.
        names = [n.decode("latin-1") for n in blob.split(b"\0") if n]

        raw = self._fh.read(4)
        if len(raw) < 4:
            raise ArchiveError(f"{self.path}: truncated file count")
        (count,) = struct.unpack("<I", raw)

        if count != len(names):
            raise ArchiveError(
                f"{self.path}: file count {count} != string count {len(names)}"
            )

        table = self._fh.read(count * DIR_ENTRY_SIZE)
        if len(table) != count * DIR_ENTRY_SIZE:
            raise ArchiveError(f"{self.path}: truncated directory")

        entries = []
        for i, name in enumerate(names):
            offset, packed, unpacked = struct.unpack_from(
                "<III", table, i * DIR_ENTRY_SIZE
            )
            entries.append(Entry(name, offset, packed, unpacked))
        return entries

    def read(self, entry: Entry) -> bytes:
        """Return an entry's decompressed content."""
        self._fh.seek(self.header.data_start + entry.offset)
        raw = self._fh.read(entry.packed_size)
        if len(raw) != entry.packed_size:
            raise ArchiveError(f"{entry.path}: truncated (wanted {entry.packed_size} bytes)")

        if not entry.is_compressed:
            return raw

        try:
            out = zlib.decompress(raw)
        except zlib.error as exc:
            raise ArchiveError(f"{entry.path}: zlib error: {exc}") from exc

        if len(out) != entry.unpacked_size:
            raise ArchiveError(
                f"{entry.path}: decompressed to {len(out)} bytes, "
                f"directory says {entry.unpacked_size}"
            )
        return out


def safe_destination(outdir: Path, posix_path: str) -> Path:
    """Resolve an archive path to a path inside outdir, refusing traversal."""
    dest = (outdir / posix_path).resolve()
    if not dest.is_relative_to(outdir.resolve()):
        raise ArchiveError(f"{posix_path}: path escapes the output directory")
    return dest
