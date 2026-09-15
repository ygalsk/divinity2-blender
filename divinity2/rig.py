"""The shared rig.

Half the characters carry no skeleton and no clips of their own. They are not
broken: they share a rig with every other character of their family. 105 human
characters run on one `HumanMale` skeleton, and a Froblin has five animation
sets to pick from.

A character's family is the first segment of its mesh entries' paths --
`HumanMale\\Meshes\\M_Torso_A.nif` is family `HumanMale` -- and the family's
files live in `Win32/Characters/<family>/`:

    Skeleton.nif          the skeleton every character of the family uses
    <set>.kfm             one animation set: which clips, and how they join
    <set>.kf              the clips themselves

`Attachables` is not a family. It is where the weapons live.
"""

import re
from pathlib import Path

from .nif import read_nif

CHARACTERS = Path("Win32") / "Characters"
SKELETON_FILE = "Skeleton.nif"

#: A path segment that names a place, not a family.
NOT_A_FAMILY = {"attachables"}


def families(character) -> list[str]:
    """The families a character's meshes come from, most likely first."""
    seen = []
    for mesh in character.meshes:
        head = str(mesh.name).replace("\\", "/").split("/")[0]
        if head.lower() in NOT_A_FAMILY or head in seen:
            continue
        seen.append(head)
    return seen


def family_of(character, game_root) -> str | None:
    """The family that actually owns a skeleton on disk."""
    for name in families(character):
        if (Path(game_root) / CHARACTERS / name / SKELETON_FILE).is_file():
            return name
    return None


def skeleton_path(character, game_root) -> Path | None:
    name = family_of(character, game_root)
    if name is None:
        return None
    return Path(game_root) / CHARACTERS / name / SKELETON_FILE


def shared_skeleton(character, game_root):
    """The family's skeleton as a NiNode, or None when it owns one already."""
    if character.skeleton is not None:
        return character.skeleton
    path = skeleton_path(character, game_root)
    if path is None:
        return None
    nif = read_nif(path)
    return next((b for b in nif.blocks if type(b).__name__ == "NiNode"), None)


def clip_files(character, game_root) -> list[Path]:
    """The `.kf` files the character's own KFM names, resolved on disk."""
    name = family_of(character, game_root)
    if name is None:
        return []
    directory = Path(game_root) / CHARACTERS / name
    named = {
        m.decode().replace("\\", "/").split("/")[-1]
        for m in re.findall(rb"[\x20-\x7e]{4,}", character.animation_set)
        if m.lower().endswith(b".kf")
    }
    return sorted(directory / n for n in named if (directory / n).is_file())
