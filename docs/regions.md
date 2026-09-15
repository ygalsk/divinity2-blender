# A region, whole

A Divinity II level is not a file. It is a list of placements in one file, a
prototype table in another, the meshes in a third, the built geometry in a
fourth and the terrain in a fifth. This page is the chain, and every step
carries the measurement that settled it.

Measured on `Banditcamp`, which has 775 placements, and on `RiverTown_FF`,
which has 626 and the terrain the first one is missing.

## The chain

```
World/<region>/Main/scenery.xml       775 placements: prototype, scale,
       |                              a 3x3 basis and a position
       v
rpgstats_sceneryprototypes.xml        1,726 prototypes: UUID -> NIFFile
       |
       v
Win32/Scenery/<path>.item             the mesh

World/<region>/Main/StaticMeshes.nif  the region's own built geometry
World/<region>/Main/Meshes/Terrain/   the ground, two files per patch
```

`scenery.xml` is not text and not a NIF scene. It is Larian's binary XML
inside an `xml::dom::CStreamableNode` block in a NIF container — the file
carries a `.xml` extension and holds neither.

## 1. The placement basis is stored in reverse row order

Read as they come, **775 of 775** Banditcamp matrices have determinant −1.
A determinant of −1 is a reflection, and a reflection is not a rotation: a
reader that builds an orientation from it does not fail, it silently produces
a different one. That is why assets stand on their side.

| rows | det < 0 | det > 0 |
|---|---:|---:|
| as read | 775 | 0 |
| **reversed** | **0** | **775** |
| transposed | 775 | 0 |

Transposing cannot help, whatever else is true: `det(Mᵀ) = det(M)`, so it
leaves every reflection a reflection. Only an odd permutation of the rows
changes the sign. Reversed, 746 of the 775 also stand upright.

`RiverTown_FF` says the same: 626 of 626 reversed, 624 upright.

## 2. `Assets` replaces, and the case does not match

A prototype names `Assets\Scenery\P_Junk\X`. The engine's `Assets` root
**replaces** onto `Win32/Scenery`, it does not nest under it, so that resolves
to `Win32/Scenery/Scenery/P_Junk/X.item`.

Larian's own paths disagree with their own filenames on case. Matching
literally loses **10 of Banditcamp's 775**; folding case resolves
**775 of 775**.

## 3. A scenery placement is already in metres

The mesh is not. A scenery `.item` carries the conversion on its own root node
as a scale of `0.01` (see `docs/assets.md`), so once the add-on has imported
it the placement's position applies unchanged. Banditcamp comes out
**292 × 222 × 76 m** — a camp, at the size a camp is.

## 4. The built geometry hides three things and flags one

`StaticMeshes.nif` is the region's own geometry: 14.4 MB and 79 shapes in
Banditcamp, placed at the origin because its nodes carry full world positions.
Three kinds of thing that are not world geometry sit inside it:

| what | shapes | marked |
|---|---:|---|
| `BC_Compartment_*_NDLWL` volume markers | 10 | **`APP_CULLED`** |
| `BC_terrain_*_low`, the region's own low terrain | 7 | no |
| `BC_ShadowHide_01`, an author-side helper | 4 | no |

`APP_CULLED` is bit 0 of any `NiAVObject`'s flags, and the engine says so
outright — `NiAVObject::GetAppCulled` is `return this->m_uFlags & 1;`. The
add-on hides those 10, and a culled node takes its subtree with it.

The other 11 carry no flag at all, so the engine must filter them by name and
so must anything else. The shapes themselves are all called `Editable Poly`;
the name that matters is on the nodes above them, which is why the add-on
keeps the whole node path on each object as `dv2_path`.

## 5. The terrain needs both halves of its placement

A patch ships `Meshes/Terrain/Terrain_Patch_<i>/0.nif`, `1.nif` and sometimes
`2.nif`. `0.nif` is an `NiLODNode` holding one level inline plus **one empty
stub node per streamed level**; the streamed file holds its geometry under a
node of the same name as its stub.

**Neither file places the patch on its own.** The stub carries half the
placement and the streamed node the other half, and the engine attaches one to
the other. On `Terrain_Patch_0`, stub + node is
`(11390.9, 62440.5, 11651.4)`, which is to within `0.000` exactly where
`0.nif` already puts its own inline level.

The stub is matched to the streamed node **by name, not by position**: a patch
carries one stub per level and their order is not fixed. Taking the first stub
misses `Terrain_Patch_1` by 184 units.

The streamed node's own translation is not a constant — 335 of the corpus's
494 streamed terrain files carry `(0, 0, 0)` and the rest carry a real offset
— so both halves have to be read. Neither may be assumed.

`Terrain.xml` names the diffuse, because a terrain mesh carries no
`NiTexturingProperty` at all.

## What is not here yet

- **Vegetation is generated, not stored.** `vegetationtemplates.xml` gives each
  layer an instance count and six noise parameters and no positions;
  `Vegetation.nif` is a library whose 36 nodes all sit at the origin.
  Reproducing it means reimplementing the engine's noise exactly, and a
  near-miss looks like a hit.
- **Lights are game data.** Not one of the corpus's 107 NIF block types is a
  light. `Lights/<time of day>/lights.xml` holds them, 8,765 instances.
- **Characters** are placed the same way scenery is, in the region's own
  character list.
