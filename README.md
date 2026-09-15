# divinity2-blender

Divinity II: Ego Draconis and Developer's Cut (Larian Studios, 2009) assets in
Blender — characters with their skeletons, their clips and their textures.

## Use it

Install `divinity2-<version>.zip` through **Edit > Preferences > Add-ons >
Install from Disk**, then set the game's folder in the add-on's preferences.

Then **File > Import > Divinity II asset**, or the *Divinity II* tab in the 3D
sidebar (press N). Type a name — `goblin`, `damian` — and press OK.

To get an asset out again, use Blender's own glTF or FBX export. This add-on
does not write game files.

## What works

- A character template (`.cat`) arrives as one armature and one object per
  mesh, skinned, textured, in metres.
- Textures convert from the game's texture NIFs with no quality lost.

## What does not, yet

- The 162 human characters share a skeleton that is not in their own file, so
  they arrive without one.
- Clips are read and named but not yet applied; they are B-spline compressed.
- A weapon is imported but not attached to the hand it belongs in.

## How it reads the files

It does not. The NIF format is described by the NifTools project in `nif.xml`,
which covers Divinity II as a version of its own, and read by `nifgen`, the
Python reader generated from that description. `nifgen` is vendored under
`vendor/` unchanged, under its BSD-3-Clause licence.

What this add-on adds is what `nif.xml` does not say: which file is which
asset, how a character is bundled, where a texture really lives, and how all
of that becomes Blender data.

See `docs/` for the formats and `DECISIONS.md` for what is settled.
