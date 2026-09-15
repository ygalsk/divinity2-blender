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

- Materials carry a diffuse and a normal map and nothing else: no
  transparency, no vertex colours, no two-sided flag. Hair and capes therefore
  arrive opaque.
- The animation set (a KFM) is read by scraping filenames out of it, not by
  parsing it. Which clip belongs to which weapon set, and how clips blend into
  each other, is in there and is thrown away.
- A clip's text keys -- `morph: L_Foot_Down`, and the `v=` values on death
  animations -- are read but not carried into Blender.

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

See `docs/` for the formats and `DECISIONS.md` for what is settled.
