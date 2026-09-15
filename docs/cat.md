# The character template (`.cat`)

A character in Divinity II is one file. A `.cat` is a NIF that bundles the
skeleton, the meshes, the animation set and the clips, each as an `MdlMan::`
entry that keeps the path it had before it was bundled. Nothing has to be
found beside it on disk.

## What a `.cat` holds

Read from `Black_Goblin.cat`, 2026-09-15:

```
MdlMan::CModelTemplateDataEntry   'Templates\Black_Goblin.cat'
  MdlMan::CSkeletonDataEntry      'Froblin\skeleton.nif'
  MdlMan::CAMDataEntry            'Froblin\Froblin.kfm'
  MdlMan::CMeshDataEntry          'Froblin\Meshes\Froblin.nif'
  MdlMan::CMeshDataEntry          'Froblin\Meshes\1H_Sword_Long_A_A.nif'
  MdlMan::CAnimationDataEntry     'Froblin\Froblin.kf'
```

| entry | field | what it is |
|---|---|---|
| `CSkeletonDataEntry` | `skeleton_data_reference` | the skeleton's own `NiNode` scene root |
| `CAMDataEntry` | `binary_data` | **a KFM without its header**, as `nif.xml` says |
| `CMeshDataEntry` | `mesh_data_reference` | a mesh file's `NiNode` scene root |
| `CAnimationDataEntry` | `controller_seq_list` | the clips, as `NiControllerSequence` |

The clips are named as the game names them: `Idle1`, `Move_F_Normal`,
`Melee_Static_01`, `Hit_Back`. Each carries `start_time`, `stop_time` and one
controlled block per bone.

## Half the characters carry no skeleton

Of the 324 templates in the install, exactly **162 hold a skeleton and clips
and 162 hold neither**. The 162 without are the human ones —
`DefaultHumanMale`, `F_Bandit_T1`, `F_BlackRing_Keara` — and they carry only
meshes. They share a skeleton and its clips with every other human, which is
why the bundle does not repeat them.

Resolving that shared rig is not yet implemented.

## The version

Divinity II files are NIF **20.3.0.9** with user version `0x20000` or
`0x30000`. `nif.xml` gives that combination its own id, `V20_3_0_9_DIV2`, and
its own token `#DIVINITY2#`, and lists the extensions `nft`, `item` and `cat`.
The Div2-specific fields it guards — `div_2_floats` on geometry data,
`div_2_ints` and `div_2_ref` on a controller sequence — are present in real
files, so a reader that ignores the token reads these files wrongly.

## The trap

`NiTriShapeData.has_uv` reads **0** on every Divinity II shape, including ones
that carry a full UV set. It is a legacy field that this version no longer
writes. The truth is in `data_flags.num_uv_sets`, or simply in whether
`uv_sets` is non-empty. A reader that trusts `has_uv` produces a correct,
fully textured material on a mesh with no UV map, and the asset renders
untextured while every check passes.

## The shared rig

A `.cat` holds only what is unique to that character. Everything a family
shares lives in `Win32/Characters/<family>/`:

```
Win32/Characters/Froblin/
  Skeleton.nif              every Froblin uses this
  Froblin_Base.kf/.kfm      the base clips
  Froblin_Unarmed.kf/.kfm   four more sets: a Froblin has several walks
  Shaman.kf/.kfm
  Soldier_Dualwield.kf/.kfm
  Soldier_Onehanded.kf/.kfm
```

The family is the first segment of a mesh entry's path:
`HumanMale\Meshes\M_Torso_A.nif` is family `HumanMale`. `Attachables` is not a
family — it is where weapons live — so the family is the first segment that
has a `Skeleton.nif` beside it.

This explains both halves at once:

- `DefaultHumanMale.cat` carries four meshes, no skeleton and no clips. Its
  bundled KFM is 34 KB and names `Human_M_Base.kf`. The skeleton is
  `Win32/Characters/HumanMale/Skeleton.nif`, 123 bones.
- `Black_Goblin.cat` carries its own skeleton and 15 clips — but they are all
  deaths, stuns and a flee. No `Idle1`, no walk. Those are in
  `Froblin_Base.kf`, which its KFM names 15 times.

So a character's clips are in two places, and a tool that reads only the `.cat`
gets a creature that can die but not stand.

## A bone is a node, not a name

Each of a character's mesh files carries its own copy of the skeleton, with
its own `Scene Root`. The copies are **not in the same pose**.
`FroblinBoss.nif` and `FroblinBoss_Armor_A.nif` both contain a bone called
`Bip01 Spine`, and they disagree about where it is by some 800 game units.

Measured over all 324 templates: 317 carry skinned geometry, and **106 of them
have mesh files whose bind poses disagree by more than 5 units**. Matched by
node identity, every shape inside one file agrees to within 2.5 units. Matched
by name across files, they do not agree at all.

This is what makes a character arrive as a heap. Binding every shape to one
armature by bone name silently mixes two skeletons: the body is placed against
one pose and the armour against another.

Neither is a rigid offset from the other — hinging the two on the bone where
they agree best yields the identity, because they agree exactly on some bones
and not at all on others. They are two different authorings of one rig.

## The rest pose comes from the skin, not the skeleton

The skeleton file is not the pose anything was skinned to. `NiSkinData`
carries, per bone, the transform that takes a vertex from skin space into that
bone's space; its inverse is where the bone stood when the weights were
painted. That is the only pose at which the geometry is undeformed.

The skeleton file disagrees with it — by about 7 units for a Froblin, by
several hundred for a FroblinBoss — and the skeleton is the one that is wrong,
because nothing was ever skinned to it. The skeleton is still needed: it is
the only place the **hierarchy** is written down, and it supplies bones no
shape mentions.

## Clips are B-splines, not keyframes

A clip stores no keys. It stores the control points of a cubic B-spline,
quantised to 16-bit integers, and the game evaluates the curve as it plays.
`Black_Goblin`'s `Stunned` holds 1,158 `NiBSplineCompTransformInterpolator`
blocks and not one keyframe, which is why a keyframe importer reads it and
finds nothing at all.

A handle of `0xFFFF` means the track is not animated; the interpolator's own
static transform is the value for the whole clip. A component that is absent
is written as `-FLT_MAX`, not left out — `trs_valid`, which is supposed to say
which of translation, rotation and scale are present, is an **empty array** at
this version, so the sentinel in the value is the only thing that tells the
truth.

The control points are not points on the curve. Treating them as keyframes is
the tempting shortcut and gives an animation that is close but wrong, in a way
that reads as bad rigging rather than bad maths.
