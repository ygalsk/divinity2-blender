# Asking the engine instead of guessing

Some things are not in the assets. Which bone carries a weapon is not; what a
text key means is not; what a `UserPropBuffer` line does is not. Every one of
them can be inferred from the files, and every inference is wrong somewhere —
usually on the third of the corpus you did not check.

The executable knows all of it, and it can be read.

## The source

Divinity II: Ego Draconis 1.03 shipped with its PDB. The Developer's Cut
executables are a different build, but the same code, so the 1.03 symbols pair
across: 27,350 named functions with their classes, fields, enums and
signatures. With those applied, a decompilation reads
`CRpgStats_V2_SlotMapManager::GetBoneNameForModelmanSlot` rather than
`FUN_008e5850`.

Two queries carry almost everything this add-on needed.

## The name tables

Larian keeps its string constants in one class, `CGameLogic_FixedStrings`, and
initialises them in one function:

```sql
select c from functions where name = 'CGameLogic_FixedStrings::InitStrings'
```

85,844 characters, **1,140 fixed strings**, each an `ms_k…` symbol paired with
its literal. Grouped by prefix:

| table | entries | what it names |
|---|---|---|
| `ms_kLoadSaveEntry_*` | 485 | savegame fields |
| `ms_kLoadSaveTag_*` | 194 | savegame tags |
| `ms_kSkillEffect_*` | 146 | skill effect assets |
| `ms_kMdlManNode_*` | 46 | **model nodes and equipment slots** |
| `ms_kAchievement_*` | 44 | achievements |
| `ms_kStatusIcon_*` | 37 | status icons |
| `ms_kSwoosh_*` | 19 | weapon trails |
| `ms_kAnimation_*` | 15 | movement animations |
| `ms_kEffect_*` | 13 | flying fortress effects |

**The symbol name is not the value.** `ms_kMdlManNode_CastPrimary` holds
`"Dummy_Cast_Primary"`; `ms_kMdlManNode_HumanLeftEye` holds
`"Bone_Eye_Left"`. Matching skeletons against the symbol names finds a
fraction of what is there, which is exactly the mistake that made the weapon
sockets look absent.

The 46 that matter here are in `divinity2/engine.py`.

## The one function that answered the weapon question

```sql
select c from functions
where name = 'CRpgStats_V2_SlotMapManager::GetBoneNameForModelmanSlot'
```

A chain of comparisons, no data, no configuration:

| slot | node |
|---|---|
| `handR` | `Bone_Weapon_01` |
| `weaponSlotBack` | `Bone_Weapon_02` |
| `handL`, `armL` | `Bone_Weapon_03` |
| `weaponSlotBack2` | `Bone_Weapon_04` |
| `weaponSlotBack3` | `Bone_Weapon_05` |
| `weaponSlotBack4` | `Bone_Weapon_06` |
| anything else | the empty string |

The remaining slots — `armor`, `arms`, `body`, `claws`, `gloves`, `head`,
`helmet`, `legs`, `pants`, `tail`, `torso` — map to nothing because they swap
a body mesh rather than carry an object.

## What else this settled

- **`morph:` is Gamebryo's, not Larian's.** `NiControllerSequence::
  FindCorrespondingMorphFrame` and `VerifyMatchingMorphKeys` look it up: a
  `morph: L_Foot_Down` on a walk and the same label on a run mark the frames
  that must be aligned when one blends into the other. It is a blend
  alignment point, not a footstep event — it only happens to fall on one.
- **`eq=` and `ue=` are Larian's.** `eq=handR:2H_Sword_Alguard` equips,
  `ue=weaponSlotBack` unequips, and the slot goes through the table above.
  `Win32/Characters/CharacterAnimationData.xml` is an index of every clip's
  text keys, so the grammar can be read off the data as well as the code.
- **`MdlMan::CSlot` is a serialisable `NiObject`** — name, attach node, name
  id, equipment ids — but no file in the game ships one. The only `MdlMan::`
  blocks in 2,900 model files are the five a `.cat` holds.

## How to do this again

1. Find the concept's class: `select name from functions where name like
   '%Slot%'`.
2. Read the one function that answers the question.
3. Put the answer in code as a table with the function name next to it, so
   the next reader can check it rather than trust it.

Nothing here is a heuristic, so nothing here has a corpus to be wrong on.
