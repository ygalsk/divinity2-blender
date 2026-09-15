# Carried meshes (`Attachables\`)

A weapon, a torch, a book or an effect plane is bundled into a character's
`.cat` like any other mesh. Two things set it apart:

- its entry path starts with `Attachables\`, and
- it has no `NiSkinInstance`. It is not deformed by the skeleton; one bone
  carries it.

## Which bone is not in the files

This is the part worth writing down, because the naming invites a wrong
answer. Everything was checked:

| where | what is there | attachment? |
|---|---|---|
| `Attachables\*.nif` | scene root, a node named after the weapon, geometry, and rendering extra data (`worldScale`, `FallOffPower`, `EnableFallOff`, `UseEnvMapping`) | no |
| the `.cat`'s `CMeshDataEntry` | `name` and `mesh_data_reference`; the two Div2 fields `nif.xml` calls unknown read 2 and 1 on **every** entry, carried or not | no |
| `Win32/Items/**/*.item` | the same NIF again, plus `swoosh_begin` and `swoosh_end` for the weapon trail, and a `DivStandardMaterial` name | no |
| the family skeleton | `Dummy_` nodes — see below | for one family out of 47 |

The game decides at runtime, from its equipment rules. The assets do not
record it.

## What the `Dummy_` nodes actually are

Counted over all 47 family skeletons, they are effect points, not sockets:

| name | what the game hangs on it |
|---|---|
| `Dummy_Cast_Primary`, `Dummy_Cast_Secondary` | where a spell leaves the body |
| `Dummy_Impact_01` … `Dummy_Impact_10` | where a hit registers |
| `Dummy_Head_Above`, `Dummy_Head_Around` | where a status icon floats |
| `Dummy_Foot_Left`, `Dummy_Foot_Right` | where footstep dust spawns |
| `Dummy_1H_Sword`, `Dummy_1H_Sword01` | a grip — **`Froblin` only** |

`Dummy_1H_Sword` exists in exactly one skeleton. `HumanMale` and
`HumanFemale`, who carry swords, bows, staves and shields, have no weapon
dummy at all. A rule built on these names looks right on a goblin and is
wrong everywhere else.

## What the add-on does instead

1. If a `Dummy_` is named after the weapon, use it. Only a Froblin's sword
   ever matches, and it lands in the hand.
2. Otherwise the right hand, under whichever of the five spellings the rig
   uses: `Bip01 R Hand`, `Bip02 R Hand`, `RightHand`, `Bone_Right_Hand`,
   `hand_T1_R`. Every rig that can hold anything has one.
3. Otherwise nothing. The mesh is built and parented to the armature but not
   carried.

Case 2 is a guess, and it is marked as one: the object gets
`dv2_attachment_source = "inferred: right hand"` and the importer reports a
warning. A staff placed this way hangs in roughly the right place and at the
wrong angle, because the grip offset is part of what the game supplies and
the file does not.

**Where the real answer is:** in the executable's equipment code, not in the
assets. That is a job for the game side, not the importer.
