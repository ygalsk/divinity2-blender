# divinity2-blender

Divinity II: Ego Draconis and Developer's Cut (Larian Studios, 2009) assets in
Blender — every model the game ships: characters with their skeletons, their
clips and their textures, and the 3,275 pieces of scenery, items, effects and
terrain besides — and whole regions, with everything standing in them.

## Use it

You need your own copy of Divinity II: Developer's Cut and Blender 5.2 or
newer. Nothing else.

1. Install `divinity2-<version>.zip` through *Edit > Preferences > Get
   Extensions > Install from Disk*.
2. In the add-on's preferences, set **Game folder** to an empty folder with
   7 GB free, and press **Unpack the game**. A Steam copy is found by itself;
   otherwise set **Divinity II install** first. It takes about a minute.

Then **File > Import > Divinity II asset**, or the *Divinity II* tab in the 3D
sidebar (press N). Type a name — `goblin`, `damian`, `chest`, `P_Doors` — and
press OK.

The second button builds a whole region: the ground, every prop, every
person, the lights and the triggers, in one go.

`docs/using-it.md` is the whole guide: what the six kinds of asset are, what
arrives, and what to do when something looks wrong.

To get an asset out again, use Blender's own glTF or FBX export. This add-on
does not write game files.

## What works

- A character template (`.cat`) arrives as one armature and one object per
  mesh, skinned, textured, in metres.
- Every other model arrives too — 1,695 scenery, 886 items, 378 effects, 295
  compiled props, 21 flying fortresses, 3,599 in all — through the same code
  path, because an asset is a character with one mesh and no family. See
  `docs/assets.md`.
- A whole region arrives: 19 regions and 122 sub-regions, 43,795 scenery
  placements, 10,311 items, 1,011 characters, and the lights, triggers and
  trees besides. Each kind lands in its own collection and every placement is
  a linked copy, so Banditcamp's 732 scenery placements share 194 meshes. See
  `docs/regions.md`.
- The ground arrives at the level the game streams, not the one the region
  ships inline: Banditcamp's terrain is 36,883 vertices rather than 9,992,
  and RiverTown_FF's flying islands are real ground rather than 24-vertex
  plates.
- Water planes are drawn as water, with the colour and shininess the region's
  own `waterplanedata_v2.xml` gives them.
- Textures convert from the game's texture NIFs with no quality lost, and
  cut-out and blended surfaces arrive transparent rather than as opaque cards.
- Materials carry a diffuse map, a normal map, transparency, the shape's
  vertex colours and its two-sided flag — each where the file says it applies,
  which for the last two is mostly where the file says nothing. Both defaults
  come out of `nif.xml`, not out of taste: a shape with no
  `NiVertexColorProperty` uses its colours, and a shape with no
  `NiStencilProperty` is culled.
- Clips arrive as actions with their text keys as pose markers, so a footstep
  keeps its frame.
- Everything lands in one world at one scale: a goblin 1.84 m, a Maxos gate
  5.9 m, a ruined wall 15.7 m. The conversion is the model's own root
  transform, not the `worldScale` field that looks like one.
- **Checked against the running game.** Twelve positions read off a Banditcamp
  runthrough's coordinate overlay: the ground under the player's feet in the
  imported region is within 10 cm at 11 of them, mean error 5.3 cm.
  `docs/regions.md` section 12.
- **The grass grows.** A region ships no vegetation, only a recipe, and the
  engine scatters it at load. `divinity2/vegetation.py` runs the same
  generator, out of the game's own debug symbols: the mask's four channels,
  the 1024-card lottery, `CRandomNoise`'s shuffle and `CPerlinNoise` down to
  the constants. Banditcamp comes out at 4,737 plants, and their cached ground
  height agrees with the ground the add-on builds for **98% of samples within
  10 cm**. Fourteen of the game's sub-regions carry vegetation and all
  fourteen read: **523,223 plants** in five seconds. `docs/vegetation.md`.

## What does not, yet

- An effect that is a pure emitter imports as nothing: many hold timing and
  nodes with no geometry at all.
- Equipment is not simulated: a clip's `eq=`/`ue=` text keys arrive as pose
  markers but nothing swaps meshes on them.
- 16 of the game's 121 animation sets stop partway through their transition
  lists, so their blending data is only partly read. Their clips are not
  affected.
- Trees are markers at the right
  place and size — a SpeedTree is a procedural definition, and no mesh for one
  exists on disk. `docs/regions.md` sections 9 and 11.

A walk cycle treading in place is **not** on this list. Divinity II clips hold
no root motion: measured over all 729 clips of the human families, not one
animates `Reference` or `Reference NonAccum`. The engine moves the character;
the clip only cycles the legs.

## How it reads the files

The archives and the game's binary XML are read by
[divinity2-lib](https://github.com/ygalsk/divinity2-lib), the reader part of
the modding tool [dv2mod](https://github.com/ygalsk/dv2-mod), vendored under
`vendor/dv2lib` unchanged. It unpacks the game once, with every document
named, and the add-on reads what it wrote. The NIF format is described by the
NifTools project in `nif.xml`, which covers Divinity II as a version of its
own, and read by `nifgen`, the Python reader generated from that description.
`nifgen` is bundled unchanged as a wheel under `wheels/`, under its
BSD-3-Clause licence.

What this add-on adds is what `nif.xml` does not say: which file is which
asset, how a character is bundled, where a texture really lives, and how all
of that becomes Blender data.

Where the assets do not say — which bone carries a weapon, what a text key
means — the answer is read out of the executable rather than inferred from the
files. `docs/engine.md` says how, and `divinity2/engine.py` carries the
tables with the function they came from.

See `docs/` for the formats and `DECISIONS.md` for what is settled.
