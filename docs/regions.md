# A region, whole

A Divinity II level is not a file. It is a list of placements in one file, a
prototype table in another, the meshes in a third, the built geometry in a
fourth and the terrain in a fifth — and the people, the loot and the triggers
are not with the region at all, they are with the episode. This page is the
chain, and every step carries the measurement that settled it.

Measured on `Banditcamp` and swept over the whole install: **19 regions, 122
sub-regions, 43,795 scenery placements, 10,311 items, 5,991 triggers, 3,685
lights, 3,323 trees and 1,011 characters.** Of those, nine scenery prototypes
find no file; every character and every item resolves.

## The chain

```
World/<region>/<sub>/scenery.xml      prototype, scale, a basis, a position
       -> rpgstats_sceneryprototypes.xml   sceneryitem: UUID -> NIFFile
       -> Win32/Scenery/<path>.item

Episodes/<e>/Regions/<r>/Characters/*.xml
       -> rpgstats_characterprototypes_visual.xml   Visual: TemplateName
       -> Win32/Characters/Templates/<name>.cat

Episodes/<e>/Regions/<r>/Items/*.xml
       -> rpgstats_itemprototypes.xml        item: VisualUUID
       -> rpgstats_itemvisualprototypes.xml  itemvisual: Folder, NifFileName
       -> Win32/Items/<folder>/<name>.item

Episodes/<e>/Triggers/*.xml           volumes and points, by Region/SubRegion
World/<region>/<sub>/Lights/<time>/lights.xml    point lights and one sun
World/<region>/<sub>/trees.xml        SpeedTree placements
World/<region>/<sub>/StaticMeshes.nif the region's own built geometry
World/<region>/<sub>/Vegetation.nif   the grass library, unplaced
```

None of the `.xml` files is text. Each is Larian's binary XML inside an
`xml::dom::CStreamableNode` block in a NIF container — the file carries a
`.xml` extension and holds neither. See `divinity2/binxml.py`.

## 1. The stream stores a node's children in reverse

This is one fact with two faces, and taking it for two separate quirks is how
it stayed hidden.

The engine's own readers say what the order must be:

| function | `children[0]` | `children[1]` |
|---|---|---|
| `CRpgStats_V2_Scenery::LoadXML` | `NiPoint3`, position | `NiMatrix3`, basis |
| `CRpgStats_V2_Character::LoadXML` | `NiPoint3` | `NiMatrix3` |
| `CRpgStats_V2_Item::LoadXML` | `NiPoint3` | `NiMatrix3` |
| `CGameLogic_Tree::LoadXML` | `m_kPosition` | `m_kInstanceData` |

Every file on disk has them the other way round. And `LoadXML(NiMatrix3*)`
fills rows 0, 1, 2 from `children[0..2]` in order — so the same reversal is
why a matrix read straight out of the file has determinant −1.

Reversing each node's children once, in the reader, settles both:

| | det < 0 | det > 0 |
|---|---:|---:|
| as the stream has it | 775 | 0 |
| **children reversed** | **0** | **775** |
| transposed | 775 | 0 |

Transposing cannot help, whatever else is true: `det(Mᵀ) = det(M)`, so it
leaves every reflection a reflection. And a tree's instance data is the
independent check — `CGameLogic_Tree::UpdateInstanceData` fills it from
`rand()/2³¹`, so all three components are in [0, 1]. After the reversal,
59 of 59 are.

## 2. `Assets` replaces, and the case does not match

A prototype names `Assets\Scenery\P_Junk\X`. The engine's `Assets` root
**replaces** onto `Win32/Scenery`, it does not nest under it, so that resolves
to `Win32/Scenery/Scenery/P_Junk/X.item`.

Larian's own paths disagree with their own filenames on case. Matching
literally loses **10 of Banditcamp's 775**; folding case resolves
**775 of 775**. The same fold is what gets items and characters to 100%.

## 3. A placement is already in metres

The mesh is not. A scenery `.item` carries the conversion on its own root node
as a scale of `0.01` (see `docs/assets.md`), so once the add-on has imported
it the placement's position applies unchanged.

## 4. The engine's own table for a region node

`CRegionVisual::ParseRegionNode` is the function that walks a region's
`StaticMeshes.nif` and decides what each node becomes. It is the answer to
"what is in here that is not geometry", and it is a table, not a guess:

| what it reads | what the node becomes |
|---|---|
| `CDummyGeometry` (RTTI) | nothing; the function returns at once |
| `effectproxy = yes` | a particle system from `Win32\Effects\<EffectFile>`, at the node's world transform, with `CullingDistance`. **The box is not drawn.** |
| `glowproxy` | a `CGlowEffect` |
| a name containing `PhysicsPROXY_` | a collision hull |
| `IsCubeMapPosition`, `CubemapPosition` | a cubemap probe |
| `IsItemPosition`, `ItemPosition`, `ItemPrototypeName`, `ItemCollectionName` | an item spawn |
| `IsStatic`, `ExternalAssetPath`, `ASSET` | a streamed asset reference |
| `TERRAIN_PATCH` | a terrain patch |
| `Imposter` | a billboard imposter |
| `River`, `WaterPlane` | a `CWaterPlane` |
| `decal` | a `CDecalNode` |
| `ANTIPORTAL_`, `antiportal` | a `CAntiPortal` |
| `DungeonPR`, `ENTRY-BOX` | an `NiRoom` / `NiShell` — the portal system |
| `ActiveDistance` | a distance |

`EffectFile` and `CullingDistance` are not attributes: they are `key = value`
lines inside the node's `UserPropBuffer`, pulled out by
`DivTools::CGBTools::GetExtraDataValue`. Positions in this function are
multiplied by `CNifManager::ms_fRescaleSize`.

The add-on reads the three that replace the geometry outright — `effectproxy`,
`glowproxy` and `PhysicsPROXY_` — and marks those shapes hidden with the
reason. Across all 19 regions that is 18 shapes of 2,273. The rest of the
table is read but not acted on yet; the markers are on every object as
`dv2_*` so nothing is lost.

## 5. The built geometry hides one thing and names another

`StaticMeshes.nif` is the region's own geometry: 14.4 MB and 69 drawn shapes
in Banditcamp, placed at the origin because its nodes carry full world
positions. Two kinds of thing in it are not world geometry:

| what | shapes | what marks it |
|---|---:|---|
| `BC_Compartment_*_NDLWL` volume markers | 10 | **`APP_CULLED`** |
| `BC_ShadowHide_01`, an author-side helper | 4 | **nothing** |

`APP_CULLED` is bit 0 of any `NiAVObject`'s flags, and the engine says so
outright — `NiAVObject::GetAppCulled` is `return this->m_uFlags & 1;`. The
add-on drops those 10, and a culled node takes its subtree with it.

`BC_ShadowHide_01` is the honest gap. Its flags are `0x210`, the same as the
58 shapes that are drawn; its node flags are `0x310`, the same as the other
52 nodes; it carries no `UserPropBuffer` and none of section 4's markers; and
`shadowHideObject` in the exe is a Scaleform text-field property, nothing to
do with it. **Only the name says what it is, and the add-on does not invent a
name test the engine does not have.** It comes in visible.

A third thing was on this list and should not have been. `BC_terrain_*_low`
is the region's ground, not junk: those patches are the coarse child of an
`NiLODNode` whose finer children are empty stubs for files this region does
not ship. Hiding them by name threw the floor away — see `divinity2/lod.py`.

Every object keeps its whole node path as `dv2_path`, because the shapes
themselves are nearly all called `Editable Poly` and the name that means
something is on a node above.

## 6. The terrain needs both halves of its placement

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

`Terrain.xml` names the ground's textures, because a terrain mesh carries no
`NiTexturingProperty` at all — see `divinity2/terrain.py` for the splat
recipe.

## 7. Lights

`Lights/<time of day>/lights.xml` holds a `point_light` per lamp and one
`dir_light` for the sun. A point light gives its position under `GBLight` as
`translate`, its colour as `diffuse_color`, its brightness as `dimmer` and its
reach as `m_fMaxAttenuationRadius`.

The sun has no position, only two angles, and the engine builds its basis in
`CDirLight::UpdateVisual` as `MakeZRotation(angle_z) * MakeYRotation(angle_y)`.
Which axis of that basis the light travels along is not written anywhere, so
it was measured: over the nine regions that ship a `Day` set,

| axis | points below the horizon |
|---|---:|
| **−X** | **9 of 9** |
| −Z | 8 of 9 |
| +Z | 1 of 9 |
| +X, +Y, −Y | 0 of 9 |

−X is the only one that is a sun in every region. The add-on aims Blender's
sun down that vector.

## 8. Triggers

`Episodes/<e>/Triggers/*.xml` holds all 5,991 of them, and a file is not one
region's: each trigger names its own `Region` and `SubRegion` in
`Trigger_base`. There are 17 `Type` numbers, but the number needs no table —
the trigger's one child element is its own label:

| element | what it carries |
|---|---|
| `Trigger_area` | a `PolyArea`: `Bottom`, `Top`, and a ring of `AreaPoint`s |
| `Trigger_Point` | one position |
| `Trigger_Orientation` | a position and a basis |
| `Trigger_PointSound`, `Trigger_PointEncounter`, `Trigger_PlayerSpawnPoint` | the same, with their own attributes |

Every corner of a `PolyArea` sits at `Bottom`, so the volume is that polygon
extruded up to `Top`. The add-on builds exactly that prism, as a wireframe.

## 9. Trees have no mesh, and that is not the reader's fault

`trees.xml` gives a tree a `uuid`, a `model`, a `variation`, a position and
three instance floats. `model` names a `CTreeModel` in `forest-settings.xml`,
whose own `model` is a SpeedTree `.spt`:

```
<CTreeModel name="BoxWood" model="ENV_TR_Boxwood_01.spt" size="15"
            treesizevariation="0.8" billboardDistance="100" .../>
```

`.spt` version `__IdvSpt_02_` is a **procedural definition, not geometry**.
The whole SpeedTree runtime is linked into the game — `CSpeedTreeRT::LoadTree`,
`CTreeModel::LoadSptFile`, `CTreeModel::SetupBranchGeometry`,
`SetupLeafMeshGeometry`, `SetupFrondGeometry` — and grows the tree at load.
No mesh for it exists on disk, in any file, ever. Nor does a reader exist to
borrow: the one free Blender add-on for SpeedTree, `ArdCarraigh/Blender_SRT_Addon`,
reads `.srt` from SpeedTree 7, four major versions later.

What *is* exact is where it stands and how big it is.
`CGameLogic_Tree::PreparePhysicsData` computes the scale as
`rescaled.y * CTreeModel.size`, and `CGameLogic_Tree::UpdateInstanceData`
computes `rescaled.y = (1 - v) + instance.y * v * 2` for
`v = treesizevariation`. So a tree arrives as a cone empty at the right place
and the right size, carrying its model name and its `.spt`.

`instance.x` is the tree's rotation and `instance.z` its colour variation.
Both go to the SpeedTree shader as a trig pair (`g_vTreeRotationTrig`); what
angle `instance.x` stands for is not resolved, so it is kept as a raw
`dv2_rotation` and not applied.

## 10. Vegetation is generated, not stored

`Vegetation.nif` is the region's **library** of grass and undergrowth: one
`NiNode` per source file, named exactly as `vegetationtemplatedata.xml` names
it (`GRS_BV_GrassSmall_D.nif`). The add-on can import that library, and does
not pretend to place it.

Where each blade stands is generated at load. `vegetationgridsettings.xml`
lists the grid cells that carry vegetation (`-3_-10`, 553 of them in
Banditcamp), and `Vegetation/VM_<x>_<y>.tga` is that cell's mask — which is
how `CVegetationGridManager::GenerateVegetationGridEntryDescriptors` finds
them, by scanning the folder for `VM_` and splitting the name. The instances
themselves come out of `VeggyLib` from `PosSeed`, `PosNoiseType` and
`PosNumOfSwizzles`. Reproducing that means reimplementing the engine's noise
exactly, and a near-miss looks like a hit.

## What is still open

- **Vegetation scatter**, above.
- **Water planes.** `UserPropBuffer=WaterPlane` marks them in
  `StaticMeshes.nif` and `Lights/<time>/waterplanedata_v2.xml` describes them;
  neither is read yet.
- **`BC_ShadowHide_01`**, section 5: no flag explains it.
- **Physics.** `Physics.nxb` is NVIDIA PhysX 2 `NxuStream` binary — a set of
  collision hulls, nothing visual, and nothing needs it to look right.
