"""Weapons, and which hand they go in.

A weapon is bundled into the character like any other mesh, but its entry path
starts with `Attachables` and it carries no skin. It is not deformed by the
skeleton; it is carried by one bone.

Which bone is not written in the weapon's own file. The skeleton names the
attachment points itself -- `Dummy_1H_Sword`, `Dummy_2H_Axe`, `Bone_Weapon_01`
-- and a weapon called `1H_Sword_Long_A_A` belongs on `Dummy_1H_Sword`. The
match is by the longest `Dummy_` name that is a prefix of the weapon's, so a
skeleton that distinguishes `Dummy_1H_Sword_Long` from `Dummy_1H_Sword` still
gets the right one.
"""

from pathlib import PureWindowsPath

#: The entry path prefix that marks a carried mesh rather than a body part.
ATTACHABLES = "attachables"

#: How the skeleton names an attachment point.
DUMMY_PREFIX = "Dummy_"


def is_attachable(entry_name: str) -> bool:
    parts = PureWindowsPath(str(entry_name)).parts
    return bool(parts) and parts[0].lower() == ATTACHABLES


def weapon_name(entry_name: str) -> str:
    return PureWindowsPath(str(entry_name)).stem


def attachment_bone(weapon: str, bone_names) -> str | None:
    """The `Dummy_` bone this weapon belongs on, longest match wins."""
    weapon = weapon.lower()
    best = None
    for name in bone_names:
        if not name.startswith(DUMMY_PREFIX):
            continue
        stem = name[len(DUMMY_PREFIX):].lower()
        if weapon.startswith(stem) and (best is None or len(stem) > len(best[1])):
            best = (name, stem)
    return best[0] if best else None
