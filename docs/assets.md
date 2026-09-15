# The plain asset: `.item` and the compiled `.nif`

A `.cat` is a character (see `docs/cat.md`). **Everything else the game models
is one shape of file**, and there is no third: scenery, items, effects and the
flying fortresses are all `.item`, the compiled terrain is `.nif`, and both are
ordinary NIF 20.3.0.9 files with one Divinity block at the root.

```
Gamebryo File Format, Version 20.3.0.9
  CStreamableAssetData          <- the root block
    NiNode                      <- the model, an ordinary Gamebryo tree
```

3,446 files carry this layout: 1,695 scenery, 886 items, 378 effects, 21
fortresses, 466 compiled assets.

## `CStreamableAssetData`

The block is described in `nif.xml` (line 8098) and read by the engine in
`CStreamableAssetData::LoadBinary`, which is four reads and nothing else:

| read | field | what it is |
|---|---|---|
| `ReadLinkID` | `root` | the `NiNode` the whole model hangs off |
| one byte | `has_data` | whether an animation set follows |
| byte array | `data` | a **KFM without its header**, when the flag is set |
| `ReadMultipleLinkIDs` | `refs` | the objects the streamer keeps alive |

The KFM is handed to `DivTools::CKFMToolStreamer::LoadBinaryStream` — the same
streamer that reads a `.cat`'s `MdlMan::CAMDataEntry`. So a door and a goblin
carry their animation set the same way, and `divinity2.kfm` reads both.

`CStreamableAssetData::GetNIFRoot` returns `m_spNIFRoot` and does nothing
else: **the geometry is in the file, not streamed from somewhere else.** That
was the one thing worth checking before building on it, because the block's
name suggests otherwise.

## What each kind actually holds

Every one of the 3,446 files was opened, not a sample. None failed to read.

| kind | files | no geometry | skinned | carries clips | particles |
|---|---|---|---|---|---|
| scenery | 1,695 | 38 | 40 | 0 | 120 |
| item | 886 | 27 | 31 | 114 | 51 |
| effect | 378 | **152** | 7 | 376 | 301 |
| fortress | 21 | 0 | **16** | 11 | 2 |
| compiled | 466 | 0 | 0 | 0 | 0 |

So "scenery is static and items are not skinned" is false: 40 pieces of
scenery and 31 items carry a skin, and 114 items carry animation clips —
doors, chests, drawbridges and lids. They take the character path without
anything being added for them, because they are the same thing.

## The scale, and the trap in it

Every model in the game is authored in **centimetres**. How many of those
units reach the world is on the tree's root node, and the two kinds of file
say it differently:

| | root `Scene Root` scale | what a walk of the tree gives you |
|---|---|---|
| character, compiled asset | `1.0` | centimetres |
| scenery, item, effect, fortress | `0.01` | metres |

So the conversion is `1 / (100 × root scale)`, and it is one term, not two.

**`worldScale` is not the scale.** Every file carries a `NiFloatExtraData`
called `worldScale` reading 100.0, which looks exactly like a units-per-metre
field and is not one. The engine binds it as a **shader input**:
`DivStandardMaterial::HandleNormalMap` adds it to the material node graph
beside `LocalScale`, and `CShadingTools::SetupStandardData` overwrites the
authored value with `1.0f` before anything is drawn. Reading it as a unit
gives the right answer for a character — whose root is 1.0 — and leaves every
piece of scenery in the game at one hundredth of its size. A Maxos gate comes
out 6 cm wide.

A fortress is the only plain asset with a skin. It has no family folder and no
`Skeleton.nif`, so its bones are in its own node tree — which is therefore
both the skeleton and the model, and is not collapsed the way a character mesh
file's embedded skeleton copy is.

An effect with no geometry is not a failure. It is an emitter: nodes,
interpolators and timing, with the particles built by the engine at runtime.

## Why this is one code path

An asset is a character with one mesh, no family and usually no skeleton. So
`divinity2.character` reads both into the same `Character`, `read_model`
dispatches on the extension, and `blender.importer.import_asset` builds either
one without knowing which it has. There is no second importer.
