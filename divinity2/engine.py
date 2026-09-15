"""Names the engine looks up, taken from the engine.

Everything here is a string constant in `CGameLogic_FixedStrings::InitStrings`,
read out of the Divinity II executable with its 1.03 debug symbols. None of it
is inferred from the assets, and none of it needs to be: the game's own table
says what each name is for.

Regenerating it is one query against a decompilation of the executable --
`select c from functions where name = 'CGameLogic_FixedStrings::InitStrings'`
-- and pairing each `ms_k…` assignment with its literal. The function holds
1,140 fixed strings; the 46 below are the ones the model manager uses.
"""

#: Nodes the engine looks for in a skeleton. The artists' spelling is the
#: value, not the symbol name -- `ms_kMdlManNode_CastPrimary` holds
#: `"Dummy_Cast_Primary"` -- which is why matching on the symbol finds
#: nothing.
NODES = {
    # where a carried mesh goes
    "Bone_Weapon_01": "weapon socket 1",
    "Bone_Weapon_02": "weapon socket 2",
    "Bone_Weapon_03": "weapon socket 3",
    "Bone_Weapon_04": "weapon socket 4",
    "Bone_Weapon_05": "weapon socket 5",
    "Bone_Weapon_06": "weapon socket 6",
    # where an effect happens
    "Dummy_Cast_Primary": "a spell leaves the body",
    "Dummy_Cast_Secondary": "a second spell origin",
    "Dummy_Impact_01": "a hit registers",
    "Dummy_Impact_02": "a hit registers",
    "Dummy_Impact_03": "a hit registers",
    "Dummy_Impact_04": "a hit registers",
    "Dummy_Impact_05": "a hit registers",
    "Dummy_Impact_06": "a hit registers",
    "Dummy_Impact_07": "a hit registers",
    "Dummy_Impact_08": "a hit registers",
    "Dummy_Impact_09": "a hit registers",
    "Dummy_Impact_10": "a hit registers",
    "Dummy_Head_Above": "a status icon floats",
    "Dummy_Head_Around": "a status icon orbits",
    "Dummy_Foot_Left": "footstep dust",
    "Dummy_Foot_Right": "footstep dust",
    # the face rig
    "Head": "the head, for a human",
    "Neck": "the neck",
    "Bone_Eye_Left": "left eye",
    "Bone_Eye_Right": "right eye",
    "Bone_Lid_Left": "left upper lid",
    "Bone_Lid_Right": "right upper lid",
}

#: Equipment slots. These are **not** node names -- they name a place to put
#: an item, and `CRpgStats_V2_SlotMapManager::GetBoneNameForModelmanSlot`
#: turns the ones that hold something into a node.
SLOT_TO_NODE = {
    "handR": "Bone_Weapon_01",
    "weaponSlotBack": "Bone_Weapon_02",
    "handL": "Bone_Weapon_03",
    "armL": "Bone_Weapon_03",
    "weaponSlotBack2": "Bone_Weapon_04",
    "weaponSlotBack3": "Bone_Weapon_05",
    "weaponSlotBack4": "Bone_Weapon_06",
}

#: The slots the same table maps to nothing: they swap a body mesh rather
#: than carry an object.
BODY_SLOTS = (
    "armor", "arms", "body", "claws", "gloves", "head", "helmet", "legs",
    "pants", "tail", "torso",
)

#: The slot a character holds its weapon in when nothing says otherwise.
MAIN_HAND = "handR"


def node_for_slot(slot: str) -> str | None:
    """The skeleton node an equipment slot hangs its item on."""
    return SLOT_TO_NODE.get(slot)
