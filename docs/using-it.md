# Using it

Everything this add-on does is reachable from two places: the **Divinity II**
tab in the 3D sidebar, and **File > Import**. There is no command line, no
extraction step and no settings beyond the game's folder. Two buttons: one
model, or one whole region.

## Install it once

1. **Edit > Preferences > Add-ons > Install from Disk**, pick
   `divinity2-<version>.zip`. Blender enables it straight away.
2. Still in Preferences, open the add-on and set **Divinity II install** to
   the folder that holds `Win32` — for a Steam copy that is
   `steamapps/common/divinity2_dev_cut/`. If the path is wrong the field says
   so.

Nothing is copied out of the game. The add-on reads the install where it is,
and writes converted textures to a cache folder beside it.

## Import something

Press **N** in the 3D viewport, open the **Divinity II** tab, click the
button. Type a name and press OK.

- The **Name** field filters as you type. It matches any part of the name, so
  `goblin` finds `Goblin`, `Black_Goblin` and `Goblin_Shaman`.
- The **Asset** dropdown lists what matched, each with its kind. Pick one.
- A name that matches exactly, or matches only one asset, needs no pick: a
  script can call the operator with the name alone.

There are 3,525 models in the install, of six kinds:

| kind | how many | what it is |
|---|---|---|
| character | 324 | a creature or person: armature, meshes, clips |
| scenery | 1,695 | walls, doors, trees, furniture, ruins |
| item | 886 | weapons, armour, containers, loot |
| effect | 378 | spell and particle effects |
| terrain | 221 | compiled props, one folder of pieces each |
| fortress | 21 | the flying fortresses, skinned |

Names follow the game's own prefixes, which is the fastest way to browse:
`P_` scenery props, `IT_` items, `EFF_` effects. Type just `P_Doors` or
`IT_Containers` to see a whole set.

## Import a whole region

The second button builds a level: the ground, every prop, every person, the
lights and the triggers, in one go.

- **Region** lists the 19 the game ships; **Sub-region** its interiors.
- **Time of day** picks which `Lights` folder to read — the sun and the lamps
  are authored three times.
- The tick boxes choose what to build. Triggers and the vegetation library are
  off by default: triggers are wireframe volumes that get in the way, and the
  vegetation library arrives unplaced (`docs/regions.md`, section 9).

Each kind lands in its own collection — `Banditcamp scenery`,
`Banditcamp light`, and so on — so you can switch off what you are not working
on. A hidden `Banditcamp models` collection holds one copy of each mesh; every
placement in the scene is a linked copy of it, so 775 props cost 105 meshes.

Everything the game's files said is kept on the object as a custom property:
`dv2_uuid`, `dv2_kind`, `dv2_prototype`, `dv2_path`, and for a tree its
`dv2_model` and `dv2_spt`. Nothing is dropped on the way in.

Banditcamp, whole: 157 models imported, 732 scenery, 169 items, 47 characters,
96 lights, 82 triggers, 59 trees, 69 pieces of built geometry, 0 failures.

## What arrives

**A character** is one armature and one object per mesh in the file. The
meshes are skinned to the armature, every clip in the character's set is an
action, and the first one is assigned so you can press space and watch it.
Text keys in a clip — footsteps, sound cues, equip events — arrive as pose
markers on the action, so nothing about a clip's timing is lost.

**Anything else** is one object per shape, placed by its own transform, with
no armature. A flying fortress is the exception: it is skinned and carries its
own bones, so it gets an armature like a character does.

Everything arrives in metres, and everything is in the same world: a goblin is
1.84 m, a Maxos gate 5.9 m wide, the Damian fountain 4.1 m across, a ruined
wall 15.7 m long. Import a character and a door together and the character
fits through the door.

Materials are Principled BSDF with the game's diffuse and normal map wired in,
and transparency honoured: a cut-out surface like hair or a leaf uses alpha
clipping, a blended one blends, an additive one casts no shadow.

## Levels of detail

A Divinity II file holds every level of detail at once. The add-on imports
them all and hides everything but the nearest, so the viewport shows one
model. The rest are in the outliner, hidden — **Alt+H** brings them back if
you want them; otherwise ignore them.

A compiled prop is the exception: its levels are separate files, one folder
per model, and the add-on takes the finest of each piece. There is nothing
hidden to reveal.

## Getting it out again

Use Blender's own exporters. **File > Export > glTF 2.0** carries the mesh,
the armature, the skin weights, the actions and the materials, and is what
Unity, Godot and Unreal all read. FBX works too.

This add-on does not write game files. It reads.

## When something looks wrong

- **A walk cycle treads in place.** That is the data. Divinity II clips carry
  no root motion — the engine moves the character, the clip only cycles the
  legs. Measured over all 729 clips of the human families: not one animates
  `Reference`.
- **A character stands below the floor.** Flying creatures and dragons are
  authored around their body, not their feet. 40 of 324 do this, and they are
  all flyers.
- **A weapon is held loosely.** The socket is right — `Bone_Weapon_01` on the
  right hand, which is what the engine's own slot table says — but a clip that
  was never meant to hold anything does not close the fingers.
- **An effect imports as nothing.** Many effects are emitters: nodes and
  timing with no geometry at all. There is nothing to show.
