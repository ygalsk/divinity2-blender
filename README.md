# divinity2-blender

Divinity II: Ego Draconis and Developer's Cut (Larian Studios, 2009) assets in
Blender — every model the game ships: characters with their skeletons, their
clips and their textures, and the 3,201 pieces of scenery, items, effects
and terrain besides.

## Use it

Install `divinity2-<version>.zip` through **Edit > Preferences > Add-ons >
Install from Disk**, then set the game's folder in the add-on's preferences.

Then **File > Import > Divinity II asset**, or the *Divinity II* tab in the 3D
sidebar (press N). Type a name — `goblin`, `damian`, `chest`, `P_Doors` — and
press OK.

`docs/using-it.md` is the whole guide: what the six kinds of asset are, what
arrives, and what to do when something looks wrong.

To get an asset out again, use Blender's own glTF or FBX export. This add-on
does not write game files.

## What works

- A character template (`.cat`) arrives as one armature and one object per
  mesh, skinned, textured, in metres.
- Every other model arrives too — 1,695 scenery, 886 items, 378 effects, 221
  compiled props, 21 flying fortresses — through the same code path, because
  an asset is a character with one mesh and no family. See `docs/assets.md`.
- Textures convert from the game's texture NIFs with no quality lost, and
  cut-out and blended surfaces arrive transparent rather than as opaque cards.
- Clips arrive as actions with their text keys as pose markers, so a footstep
  keeps its frame.
- Everything lands in one world at one scale: a goblin 1.84 m, a Maxos gate
  5.9 m, a ruined wall 15.7 m. The conversion is the model's own root
  transform, not the `worldScale` field that looks like one.

## What does not, yet

- Materials carry a diffuse map, a normal map and transparency. Vertex
  colours and the two-sided flag are read but not wired up.
- An effect that is a pure emitter imports as nothing: many hold timing and
  nodes with no geometry at all.
- Equipment is not simulated: a clip's `eq=`/`ue=` text keys arrive as pose
  markers but nothing swaps meshes on them.
- 16 of the game's 121 animation sets stop partway through their transition
  lists, so their blending data is only partly read. Their clips are not
  affected.

A walk cycle treading in place is **not** on this list. Divinity II clips hold
no root motion: measured over all 729 clips of the human families, not one
animates `Reference` or `Reference NonAccum`. The engine moves the character;
the clip only cycles the legs.

## How it reads the files

It does not. The NIF format is described by the NifTools project in `nif.xml`,
which covers Divinity II as a version of its own, and read by `nifgen`, the
Python reader generated from that description. `nifgen` is vendored under
`vendor/` unchanged, under its BSD-3-Clause licence.

What this add-on adds is what `nif.xml` does not say: which file is which
asset, how a character is bundled, where a texture really lives, and how all
of that becomes Blender data.

Where the assets do not say — which bone carries a weapon, what a text key
means — the answer is read out of the executable rather than inferred from the
files. `docs/engine.md` says how, and `divinity2/engine.py` carries the
tables with the function they came from.

See `docs/` for the formats and `DECISIONS.md` for what is settled.
