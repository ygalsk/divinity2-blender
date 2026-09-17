# divinity2-blender

A Blender add-on that reads Divinity II: Ego Draconis and Developer's Cut
(Larian, 2009, Gamebryo 2.3.0.0, 32-bit x86): every model the game ships, and
whole regions with everything standing in them. It is released for other
people, so it has to work on a machine that is not this one.

The Unity port is a separate repository, `~/divinity2-port`. It loads this
add-on's working tree as a library (`dv2addon`) and owns everything only Unity
needs. Nothing here may exist for the port alone.

## The first rule: do not guess. Look it up, then copy it.

Every rule in this repository has to come from a source that can be named.
Never invent a constant, a formula, a shader state or an API behaviour.
Find it, copy it, and write down where it came from.

**Where to look, in this order:**

| question | source |
|---|---|
| what does the engine do | `~/dv2-measure/pdb/gup-decomp.tsv` — 134,240 decompiled functions with real names from `Divinity2GUP.pdb` |
| what is this field called | dv2mod's name table (copied into `divinity2-lib`), never a table here |
| what does the file format say | the NifTools descriptions in `vendor/`, `nif.xml`, `kfm.xml` |
| what does Blender do | `bpy` API docs, the bundled manual under the Blender MCP's `data/` |

A comment that states a rule names the function, file or page it came from:
`CRegionVisual::SetFogDepth` is a source; "this looked right" is not.
A path on this machine is not a source other people can read — a rule whose
evidence is a measurement is written into `docs/` and cited there.

**When you cannot find it, measure it, and say which it was.** A number that
came out of a measurement is written down as a measurement, with the method
and the spread. A number that is still a guess is marked as a guess or it
does not ship.

## Where things are

| what | path |
|---|---|
| the game, extracted by dv2mod | `~/dv2-extract` (`DV2_GAME`) |
| the game's documents, named, by dv2mod | `~/dv2-docs` (`DV2_DOCS`) |
| the tool that owns both | `~/dv2` (dv2mod) — its own CLAUDE.md applies there |
| the readers, no `bpy` anywhere | `divinity2/` |
| what touches Blender | `blender/`, `ui/` |
| the NIF reader, generated, unmodified | `wheels/nifgen-*.whl` |
| the archive and binary-XML reader, a copy, unmodified | `vendor/dv2lib`, from `~/divinity2-lib` |
| how each thing is read, and why | `docs/` — start at `docs/using-it.md` |
| settled decisions | `DECISIONS.md` |

## Who owns what

| layer | owns | must not own |
|---|---|---|
| dv2mod (`~/dv2`) | the research: where a name is first recovered, what is placed where, prototypes | anything the add-on imports |
| divinity2-lib (`~/divinity2-lib`) | archives, the search order, binary XML, the hash→name table, the unpack | geometry, images, animation |
| this add-on | NIF→mesh, DDS→image, KF→action, regions, the grass scatter | a name table, a binary-XML parser, anything only the Unity port needs |

A name that is missing is recovered in dv2mod (`binxml_names.py`), copied into
`divinity2-lib`'s `names.py`, and reaches the add-on as a new copy of
`vendor/dv2lib` and an unpack, never by a table here. `vendor/dv2lib` is never
edited here: change `~/divinity2-lib` and copy it over.

## Safety rules

- Never commit a game asset. Stage by explicit path; never `git add -A`.
- Never kill the game process or, under Proton, the Wine server.
- Ask before touching a savegame.
- Temporary files go outside the repository.
- Commit only when asked.

## How to work

- **Lose nothing.** A reader carries the whole record, not a chosen subset.
  A name that has not been recovered arrives as its hash so the value still
  crosses and the gap is visible.
- The screen is the proof. A region is right when the game and Blender show
  the same thing at the same place. No unit tests that count things.
- Test in the running Blender through the MCP. The installed extension is a
  copy; load the working tree as a package of its own to test it.
- Write short. Give every number the command that produced it.
- Docs, code and commits are in English.
