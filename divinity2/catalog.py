"""Finding an asset by name.

A modder knows the name of the thing they want -- `goblin`, `damian`, `chest`
-- not which of four thousand files holds it. The catalog is the index that
turns one into the other, built by walking the install once.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

#: Where each kind of asset lives, relative to the install root.
CHARACTERS = Path("Win32") / "Characters" / "Templates"
TEXTURES = Path("Win32") / "Textures"

#: What the extensions mean. A `.cat` is a whole character; the rest are one
#: part -- a helmet, a sword, a barrel -- and arrive without a skeleton.
CHARACTER_SUFFIX = ".cat"
PART_SUFFIXES = (".nif", ".item", ".nft")


@dataclass(frozen=True)
class Asset:
    name: str
    path: Path
    kind: str  # "character" or "part"

    def __str__(self) -> str:
        return self.name


@lru_cache(maxsize=8)
def characters(game_root: Path) -> tuple[Asset, ...]:
    """Every character template in the install, by name."""
    directory = Path(game_root) / CHARACTERS
    if not directory.is_dir():
        return ()
    return tuple(
        Asset(name=p.stem, path=p, kind="character")
        for p in sorted(directory.glob(f"*{CHARACTER_SUFFIX}"))
    )


def search(game_root: Path, term: str, limit: int = 100) -> list[Asset]:
    """Characters whose name contains `term`, case ignored."""
    term = (term or "").strip().lower()
    found = [a for a in characters(Path(game_root)) if term in a.name.lower()]
    return found[:limit]


def looks_like_game(path) -> bool:
    """Is this an install root rather than some other directory?"""
    path = Path(path)
    return (path / CHARACTERS).is_dir() or (path / TEXTURES).is_dir()
