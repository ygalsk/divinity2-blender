"""The game, unpacked: every file where its archive path puts it, and every document named.

    <out>/<archive path>              every file the game can load, from the archive that wins it
    <out>/docs/<archive path>.json    every binary-XML document as a plain named tree
    <out>/unpack.json                 what was written, every hash no name was recovered for,
                                      and every `.xml` that is not binary XML, with why

A tree is `{"name", "attrs": {name: value}, "text"?, "children"?}`. An unrecovered
name is written `#hhhhhhhh`, so the value still arrives and the gap is visible.

**Children are in the engine's order, which is the stream's reversed.**
`xml::dom::CStreamableNode::LoadBinary` pushes child slots 0..n-1 onto the head of a
work list and pops from the head, so the first child in the stream fills the last slot.
`CRpgStats_V2_Scenery::LoadXML` then takes `children[0]` as the position.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from . import Dv2Error, __version__, archive, binxml, corpus
from .names import NAMES, name_of

CHILD_ORDER = ("engine: xml::dom::CStreamableNode::LoadBinary fills the last child slot "
               "first, so children are written in slot order, the stream's reversed")


def plain(node: binxml.Node, unknown: dict, where: str) -> dict:
    """One node and everything under it, named, children in the engine's order."""
    def named(h: int) -> str:
        n = name_of(h)
        if n is None:
            unknown.setdefault(f"#{h:08x}", where)
            return f"#{h:08x}"
        return n
    out = {"name": named(node.name_hash), "attrs": {named(h): v for h, v in node.attributes}}
    if node.text is not None:
        out["text"] = node.text
    if node.children:
        out["children"] = [plain(c, unknown, where) for c in reversed(node.children)]
    return out


def unpack(packed: Path, out: Path, progress: Callable[[int, int], None] | None = None) -> dict:
    """Write the game into `out`. `progress(done, total)` is called per file; raising in it stops."""
    packed, out = Path(packed), Path(out)
    by_archive: dict[Path, list[corpus.Entry]] = {}
    for entry in corpus.index(packed).values():
        by_archive.setdefault(entry.archive, []).append(entry)
    total = sum(len(v) for v in by_archive.values())

    done, documents = 0, 0
    unknown: dict[str, str] = {}
    unreadable: dict[str, str] = {}
    for path, entries in by_archive.items():
        with archive.Archive(path) as ar:
            for entry in entries:
                data = ar.read(entry.entry)
                posix = entry.entry.posix_path()
                dest = archive.safe_destination(out, posix)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                if posix.lower().endswith(".xml"):
                    try:
                        found: dict[str, str] = {}
                        tree = plain(binxml.parse(binxml.payload(data)), found, entry.path)
                    except Dv2Error as exc:
                        # Plain-text XML lands here too; either way the reason is kept.
                        unreadable[entry.path] = str(exc)
                    else:
                        for h, where in found.items():
                            unknown.setdefault(h, where)
                        target = archive.safe_destination(out / "docs", posix + ".json")
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(json.dumps(tree, ensure_ascii=False, separators=(",", ":")),
                                          encoding="utf-8")
                        documents += 1
                done += 1
                if progress is not None:
                    progress(done, total)

    meta = {"generated_by": f"dv2lib {__version__}", "packed": str(packed),
            "child_order": CHILD_ORDER, "names": len(NAMES),
            "files": total, "documents": documents,
            "unknown_hashes": dict(sorted(unknown.items())),
            "unreadable": dict(sorted(unreadable.items()))}
    (out / "unpack.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    return meta
