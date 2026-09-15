"""Weapons, and which bone carries them.

A weapon is bundled into the character like any other mesh, but its entry path
starts with `Attachables` and it carries no skin. It is not deformed by the
skeleton; one bone carries it.

Which bone is not in the assets, and it is not in the game's XML or Lua
either. It is in the executable, and with the 1.03 debug symbols it is one
function, `CRpgStats_V2_SlotMapManager::GetBoneNameForModelmanSlot`, which is
a chain of comparisons and nothing else:

| equipment slot | node |
|---|---|
| `handR` | `Bone_Weapon_01` |
| `weaponSlotBack` | `Bone_Weapon_02` |
| `handL`, `armL` | `Bone_Weapon_03` |
| `weaponSlotBack2` | `Bone_Weapon_04` |
| `weaponSlotBack3` | `Bone_Weapon_05` |
| `weaponSlotBack4` | `Bone_Weapon_06` |
| anything else | the empty string |

Which slot an item is in is the animation's business: a clip's text keys carry
`eq=handR:2H_Sword_Alguard` to equip and `ue=weaponSlotBack` to unequip. A
mesh a `.cat` simply bundles has no such event, so it is in the main hand,
`handR`, which is `Bone_Weapon_01`.

`Bone_Weapon_01` is in eight of the game's 46 family skeletons -- Froblin,
Goblin, HumanMale, HumanFemale, SkeletonHuman and the three Trolls -- which
is every rig that carries anything. The rest have no socket and get none.

See `divinity2/engine.py` for the whole table and where it was read.
"""

from pathlib import PureWindowsPath

from .engine import MAIN_HAND, SLOT_TO_NODE, node_for_slot

#: The entry path prefix that marks a carried mesh rather than a body part.
ATTACHABLES = "attachables"

#: The sockets, in the order the engine numbers them, for a character that
#: bundles more than one carried mesh and says nothing about slots.
SOCKETS = ("Bone_Weapon_01", "Bone_Weapon_02", "Bone_Weapon_03",
           "Bone_Weapon_04", "Bone_Weapon_05", "Bone_Weapon_06")


def is_attachable(entry_name: str) -> bool:
    parts = PureWindowsPath(str(entry_name)).parts
    return bool(parts) and parts[0].lower() == ATTACHABLES


def weapon_name(entry_name: str) -> str:
    return PureWindowsPath(str(entry_name)).stem


def attachment_bone(weapon: str, bone_names, index: int = 0) -> str | None:
    """The node the `index`-th carried mesh hangs on, or None if the rig has none.

    `index` 0 is the main hand, `node_for_slot("handR")`. Beyond that the
    sockets the rig actually has are taken in the engine's own order, so two
    carried meshes do not land on the same one.
    """
    have = [s for s in SOCKETS if s in set(bone_names)]
    if not have:
        return None
    if index == 0 and node_for_slot(MAIN_HAND) in have:
        return node_for_slot(MAIN_HAND)
    return have[min(index, len(have) - 1)]
