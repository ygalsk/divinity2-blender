"""python -m dv2lib unpack <out> [<game folder>]

Writes every file the game loads into <out>, and every binary-XML document
named beside them under <out>/docs. Without a game folder, the Developer's Cut
is looked for in DV2_GAME and every Steam library.
"""
import sys
import time
from pathlib import Path

from . import Dv2Error, locate, unpack


def main(argv: list[str]) -> int:
    if argv[:1] != ["unpack"] or len(argv) not in (2, 3):
        print(__doc__)
        return 2
    game = Path(argv[2]) if len(argv) == 3 else locate.find_game()
    packed = locate.packed_of(game) if game else None
    if packed is None:
        print(f"no Divinity II archives in {game}" if game else
              "no game install found; pass the game folder")
        return 2

    start = time.monotonic()

    def progress(done: int, total: int) -> None:
        if done % 500 == 0 or done == total:
            print(f"\r{done}/{total} files", end="", flush=True)

    try:
        meta = unpack.unpack(packed, Path(argv[1]), progress)
    except Dv2Error as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1
    print(f"\n{meta['files']} files, {meta['documents']} documents, "
          f"{len(meta['unknown_hashes'])} unnamed hashes, {time.monotonic() - start:.0f} s -> {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
