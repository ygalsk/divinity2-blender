"""Weapons, and which bone carries them.

A weapon is bundled into the character like any other mesh, but its entry path
starts with `Attachables` and it carries no skin. It is not deformed by the
skeleton; it is carried by one bone.

**Which bone is not written down anywhere in the assets.** The weapon's own
file says nothing about it: an `Attachables\\*.nif` holds a scene root, a node
named after the weapon, and the geometry, and the extra data on it is all
rendering (`worldScale`, `FallOffPower`, `EnableFallOff`). An `.item` file
adds `swoosh_begin` and `swoosh_end` for the trail effect and still nothing
about a hand. The game decides at runtime, from its own equipment rules.

So the bone is inferred, and the inference is stated here rather than hidden:

1. **A `Dummy_` named after the weapon.** Checked first because when a rig has
   one, it is unambiguous. Exactly one family does: `Froblin` carries
   `Dummy_1H_Sword` and `Dummy_1H_Sword01`, and a `1H_Sword_Long_A_A` lands in
   the hand there.
2. **The right hand.** Every rig that can hold anything has one, under one of
   four spellings -- `Bip01 R Hand`, `RightHand`, `Bip02 R Hand`,
   `Bone_Right_Hand`, `hand_T1_R`. This is the case for all the others.
3. **Nothing.** The mesh is still built and still parented to the armature, it
   just is not carried. Better a prop lying beside the character than a prop
   welded to the wrong bone.

The other `Dummy_` nodes are not attachment points for geometry at all, which
is worth saying because their names invite the mistake. Counted over all 47
family skeletons: `Dummy_Cast_Primary` and `Dummy_Cast_Secondary` are where a
spell leaves the body, `Dummy_Impact_01` to `Dummy_Impact_10` are where a hit
registers, `Dummy_Head_Above` and `Dummy_Head_Around` are where a status icon
floats, `Dummy_Foot_Left` and `Dummy_Foot_Right` are where footstep dust
spawns.
"""

import re
from pathlib import PureWindowsPath

#: The entry path prefix that marks a carried mesh rather than a body part.
ATTACHABLES = "attachables"

#: How a rig names an attachment point, when it names one at all.
DUMMY_PREFIX = "Dummy_"

#: Every spelling of the right hand that the game's 47 skeletons use.
RIGHT_HAND = re.compile(
    r"^(bip\d* r hand|righthand|bone_right_hand|hand_[a-z]\d+_r)$", re.I
)


def is_attachable(entry_name: str) -> bool:
    parts = PureWindowsPath(str(entry_name)).parts
    return bool(parts) and parts[0].lower() == ATTACHABLES


def weapon_name(entry_name: str) -> str:
    return PureWindowsPath(str(entry_name)).stem


def _named_dummy(weapon: str, bone_names) -> str | None:
    """The `Dummy_` bone this weapon is named for, longest match wins."""
    weapon = weapon.lower()
    best = None
    for name in bone_names:
        if not name.startswith(DUMMY_PREFIX):
            continue
        stem = name[len(DUMMY_PREFIX):].lower()
        if weapon.startswith(stem) and (best is None or len(stem) > len(best[1])):
            best = (name, stem)
    return best[0] if best else None


def right_hand(bone_names) -> str | None:
    """The rig's right hand, under whichever spelling it uses."""
    return next((n for n in bone_names if RIGHT_HAND.match(n)), None)


def attachment_bone(weapon: str, bone_names) -> str | None:
    """The bone this weapon is carried on, or None if the rig has none."""
    return _named_dummy(weapon, bone_names) or right_hand(bone_names)
