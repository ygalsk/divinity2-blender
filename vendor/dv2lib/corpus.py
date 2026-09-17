r"""Which archive serves each path: the engine's search order.

The executable names 31 global archives under `Data/Win32/Packed/`, and the
order it names them in is the search order:

    grep -a -o 'Win32\\Packed\\[ -~]*\.dv2' <game>/bin/Divinity2-debug.exe

512 more archives sit under `World/<Region>/...` and `Episode_*/` and are
searched after the 31. Among them no XML path appears twice with different
content, so they are sorted by path. The first archive that holds a path
serves it -- per path, not per archive: `Patch.dv2` overrides region files,
and 1,824 of the 34,857 paths are in more than one archive.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import archive

#: Search order, highest priority first.
LOAD_ORDER: tuple[str, ...] = (
    "DKS_Patch.dv2", "DKS_Patch_2.dv2", "DKS_Patch_3.dv2", "DKS_Patch_4.dv2",
    "FOV_Patch.dv2", "FOV_Patch_2.dv2", "FOV_Patch_3.dv2", "FOV_Patch_4.dv2",
    "Patch.dv2", "Patch_2.dv2", "Patch_3.dv2", "Patch_4.dv2",
    "GUI.dv2", "GFX.dv2",
    "MainDataPlatform.dv2", "MainDataStartup.dv2", "MainDataStreaming.dv2",
    "MainDataStub.dv2",
    "Textures.dv2", "Textures2.dv2", "CompiledAssets.dv2",
    "ItemPhysx.dv2", "SceneryPhysx.dv2", "KFMs.dv2", "Effects.dv2",
    "FlyingFortresses.dv2", "Items.dv2", "Scenery.dv2",
    "Characters.dv2", "CharacterTemplates.dv2", "Trees.dv2",
)

#: Slots the executable names but the game does not ship: eleven of the twelve
#: override archives are empty, `Patch.dv2` is Larian's. What sits in them is a
#: mod, and a mod is not the game.
MOD_SLOTS: tuple[str, ...] = tuple(n for n in LOAD_ORDER[:12] if n != "Patch.dv2")


@dataclass(frozen=True)
class Entry:
    """One file the game would load, and the archive it comes from."""

    path: str                 # as the archive spells it, with backslashes
    archive: Path
    entry: archive.Entry


def archives(packed: Path) -> list[Path]:
    """Every archive the shipped game consults, best first."""
    out = [packed / n for n in LOAD_ORDER if n not in MOD_SLOTS and (packed / n).exists()]
    out += sorted(p for p in packed.rglob("*.dv2") if p.parent != packed)
    return out


def index(packed: Path) -> dict[str, Entry]:
    """Lower-cased path -> the entry the game would load."""
    out: dict[str, Entry] = {}
    for a in archives(Path(packed)):
        with archive.Archive(a) as ar:
            for e in ar:
                out.setdefault(e.path.lower(), Entry(e.path, a, e))
    return out
