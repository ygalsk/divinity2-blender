# Where the rules come from

A comment in the code that states an engine rule and cites no function of its
own points here. Each section says what the rule is, where in the engine it
was read, and what was measured to check it.

Addresses are in `Divinity2GUP.exe`, the build the PDB names, unless marked
**Dev Cut**: `Divinity2.exe`, the Developer's Cut, the build the game was
played in. Where the two differ, the Dev Cut wins. *Read* means read in the
decompilation or the disassembly. *Measured* means counted on the shipped
files, or on the shader cache the Dev Cut compiled while the game ran: each
entry a descriptor key and D3D9 bytecode, disassembled.

## Atmosphere defaults

Every atmosphere setting starts with a fixed value. Loading a time setting
builds a new collection, and a file then sets only the names it has, so a
name the file lacks keeps its starting value. The 33 values are
`SETTINGS_FACTORY` in `divinity2/environment.py`.

- Read: `CAtmosphereSettingsFactory::GetSettingsMap` @0x1156980 (Dev Cut
  @0xc7e430), identical in both builds. `CAtmosphere::Reload` @0x6d0e00 makes
  the new collection. `CAtmosphereSettingsCollection::LoadXML` @0x10a66d0 sets
  a value only if the name is in the map and drops unknown names.
- Measured: all 170 shipped atmosphere files carry every setting, so no
  starting value is ever left in place.

## Graphics options

The game reads `RenderMethod` and `StaticAssetHighQuality` from
`graphicoptions.xml` in the player's profile. With no file, or no attribute,
they are `RenderMethod` 1 (light pre-pass) and `StaticAssetHighQuality` 0.

- Read: `CGraphicSettings::GetSaveFile` @0x769010 names the file. Dev Cut
  `CGraphicSettings::LoadXML` @0x6a4f70 keeps the member when an attribute is
  missing. Constructor defaults: Dev Cut @0x6a2d80, GUP @0x76a700. Dev Cut
  `SetQualityIndex` @0x6a3a50: presets 0, 1 and 4 turn
  `StaticAssetHighQuality` off, 2 and 3 on, and 5 (user-defined) keeps the
  file's values.
- Measured: the profile the game was played with, and an earlier saved copy
  of it, both say `RenderMethod="1" StaticAssetHighQuality="1"
  QualityModeIndex="5"`. Dev Cut `SetRenderMethod` @0x6a2b70 has no caller
  and no pointer to it anywhere in the exe (byte search), so only the file
  sets the render method.

## Missing textures

A texture name the engine does not know draws as `_black`: a 32x32 DXT1 whose
every block is zero, so (0, 0, 0, 1) at every mip. The map stays on the
material and samples black.

- Read: `CTexturePalette::ConvertPath` @0x10dc3b0 makes the key: folder and
  extension stripped, lower case. The table is filled only from
  `Win32/Textures/Textures.bin`
  (`CTextureManager::ParsePersistentTextureCollection` @0x10d3a70). On a miss
  `CTexturePalette::GetTextureWrapper` @0x10dca00 asks again for `_black`.
  `DivStandardMaterial::GenerateDescriptor` @0x1135a00 sets a map's bit when
  the map has a texture, and the palette never returns none.
- Measured: `Textures.bin` holds 10,035 names, `_black`, `_white`, `_gray` and
  `_normalmap` among them. `_Black.nif` read with `divinity2.texture`: DXT1,
  32x32, 6 mips, 696 bytes, every block zero.

## Standard material

`DivStandardMaterial` samples base, dark, detail, gloss, glow, normal and
parallax, and computes on the raw texture values. Per pixel:

- parallax moves the UV by the height map, scaled by the map's offset, along
  the tangent-space eye vector;
- the normal takes x and y from alpha and green (DXT1, DXT5) or red and green
  (DXN), rebuilds z from them, then scales x and y by
  `fGlobalNormalScale * ObjectNormalScale`;
- albedo is base, times dark squared times `fGlobalLightmapIntensity`, times
  twice detail;
- glow is added unlit, times `ObjectHDRScale`.

- Read: `HandlePreLightTextureApplication` @0x112d860 inserts parallax,
  normal, dark, base, detail, decals, gloss, in that order. `HandleDarkMap`
  @0x1126290 and `HandleLightMap` @0x11262e0 both insert the dark map, and the
  compiler merges the two samples into the square.
- Measured, on the shader cache: 259 `DivStandardMaterial` pixel programs and
  116 vertex programs. Pixel programs sampling each map: base 255, gloss 149,
  normal 122, glow 80, dark 76, detail 57, parallax 26, decal 1. No program
  converts from sRGB; whether D3D9's sRGB sampler state was set is not
  checked. No program samples a bump map, and the one decal program is not
  decoded.

## Material gates

What `DivStandardMaterial::GenerateDescriptor` switches on for a shape:

- **Specular** is `NiSpecularProperty` flags & 1, and a shape without the
  property has flags 0. Off, the specular colour is 0 — light, pre-pass and
  fake specular — and the gloss map is not inserted.
- **Fake specular** is forced on (Dev Cut @0x40e11d) unless an
  `NiAlphaProperty` blends ONE/ONE; there `UseFakeSpecular` decides.
- **Environment**: `UseEnvMapping` true adds the engine's cube times
  `fEnvCubeMapIntensity`, masked by the gloss map (@0x113658e, Dev Cut
  @0x40eab0).
- **Fall-off**: `EnableFallOff` true turns it on (Dev Cut @0x40e3d6). On
  region, static-asset and terrain geometry `CShadingTools::SetupStandardData`
  @0x6ce490 (Dev Cut @0xba4a00) first sets it false, `FallOffPower` 2 and
  `FallOffColor` 0.
- **Fog**: off when `CanBeFogged` is false or the shape blends ONE/ONE
  (@0x1135d12, @0x1135d4f).
- **Vertex colours** (@0x11322b0, @0x112b400): ignored by default. AMB_DIFF
  replaces the diffuse and ambient colours, EMISSIVE the emissive colour;
  their alpha then replaces the diffuse alpha in the opacity (`HandleBaseMap`
  @0x1131ec0). LIGHTING_E means no light.

- Read: Dev Cut `DivStandardMaterial::GenerateDescriptor` @0x40e020, and the
  GUP decompilation where the Dev Cut does the same.
- Measured: 4,895 scenery shapes carry no `NiSpecularProperty`.

## Character part maps

A character part's maps are not the names its mesh carries. The engine
re-binds base, gloss, glow and normal by the part's `CMeshEntry` texture base
plus `_DM`, `_SM`, `_GM`, `_NM`, first by the entry's own name when it says to
search. A base it cannot find becomes `_black`; any other slot it cannot find
is removed, and so is the normal map on geometry without normals and
binormals. A new map is `WRAP_S_WRAP_T`, `FILTER_BILERP`, UV set 0. The Dev
Cut never switches a character to its diffuse map alone.

- Read: `MdlMan::CMeshWrapper::SetupTexturingProperty` @0xc9de80. The suffixes
  are `ms_pacTextureExtensions` @0x13ee630, read from the exe. The entries are
  in `Win32/Characters/MdlManBinary.nif`, loaded by
  `CMdlManMapper::Initialize` @0x68a2e0 and read by `CMeshEntry::LoadBinary`
  @0x1092340. `MdlMan::CModelTemplateDataEntry::RemoveNonBaseTextures`
  @0xca1810 clears every map but base and glow, which is what
  `F_Bandit_T1.cat` holds (measured). Dev Cut
  `CCharacterAsset::UpdateVisual` @0xb49840 has no distance test for
  diffuse-only textures. That the name is base then suffix is taken from the
  decompiler's output and not yet checked in the disassembly.
- Measured: 828 `CMeshEntry` blocks, no name twice, 4 that search by their own
  name, 327 whose texture base differs from their name. Of the 828 texture
  bases, `Textures.bin` has `_DM` for 805, `_SM` 773, `_GM` 215, `_NM` 765.

## Binormal and sign

The engine's binormal is the first per-vertex block after the normals, the
one `nif.xml` names `Tangents`; the stored tangent is never read. In the Dev
Cut the binormal carries a fourth component, the per-vertex sign `nif.xml`
calls `DIV2 Floats` (+1 on a shape without it), and the tangent is
cross(N, B) times that sign.

- Read: `NiD3DShaderDeclaration::PackEntry` @0x6176a0 (Dev Cut @0x5f7eb0)
  binds the block after the normals as the binormal. Dev Cut
  `NiGeometryData::LoadBinary` @0x561130 reads the sign array when the file's
  user version is above 0x2ffff, and the Dev Cut packing function @0x5e06c0
  writes it into the binormal's w, or +1 when the shape has none.
- Measured: all 69 cached Dev Cut vertex programs that take a binormal (57
  unskinned, 12 skinned) multiply the tangent by its w. Over all 1,695 scenery
  `.item` files and 624 character NIFs (one unreadable): user version 0x30000
  in every file; shapes with normals and binormals, with and without the sign,
  1,982 / 2,047 (scenery) and 279 / 1,041 (characters); the values are only
  +1 and −1. Sign times cross(N, B) is within 90° of +dP/du on 0.9838 of scenery
  corners and 0.9844 of character corners; without the sign, 0.6755 and
  0.6015.

## Skinned normals

A skinned vertex's normal and binormal move by the 3x3 part of the same
blended bone matrix that moves its position — not its inverse transpose —
with no renormalisation in the vertex program. The pixel program normalises
them, so only their directions matter. The sign is not transformed.

- Read: the Dev Cut skinned vertex program at cache offset 0x7d1a. GUP
  `DivStandardMaterial::HandlePositionFragment` @0x1132f50 agrees: the skinned
  position's bone transform is the matrix it hands to the normal fragment.

## Terrain pre-light pass

On a patch's highest level, with `RenderMethod` 1, the ground is
`DTS_PLPMaterial` for colour and `DTS_MRTMaterial` for the normal the light
pre-pass reads. Up to eight heap rows blend from the highest row down, each
taking what the running weight has left, row 0 painted at 1. The megatexture
replaces the splat only past `g_TerrainSplatRadius` less the blend radius. No
parallax, no layer gloss, and the megatexture's normal is never used. The
tangent is cross(B, N), with no sign.

- Read: Dev Cut `CTerrainSplatRenderer` constructor @0xbc9310 picks the
  material by render method; Dev Cut `CTerrainPatchLOD::AttachMaterial`
  @0xc88700 gives it to the highest level only.
  `CTerrainPatchLOD::RecreatePreLightPassExtraData` @0x753ea0 (Dev Cut
  @0xc890a0) always marks the first pass, which paints row 0 at 1. Dev Cut
  `CTerrainPatchLOD::RecreatePreLightPassPropertyState` @0xc8a2c0 binds the
  textures: alpha maps clamped on UV set 0, layers and composites
  wrapped on UV set 1, the megatexture clamped on UV set 0.
  `CDivTerrainSplatPreLightPassMaterial::GenerateDescriptor` @0x110c1c0 (Dev
  Cut @0x48e6a0) never reads parallax, and gloss needs an `NiSpecularProperty`
  the terrain does not have. Dev Cut @0xbc89d0 sets the splat radius to 2000
  when `StaticAssetHighQuality` is on; Dev Cut @0xbc8a30 passes the blend
  radius through unchanged.
- Measured, on the shader cache: 28 `DTS_PLPMaterial` and 28 `DTS_MRTMaterial`
  pixel programs; none sets gloss or parallax, none has more than 4 noise
  layers, and every one tiles layer r by index r mod 4. A ps_3_0 bytecode
  interpreter ran each cached program beside the model on random inputs.
  Colour: 26 of 8,400 trials differ, all by less than 1e-4, float32 rounding in
  the height-fog sine (0 of 8,400 with `HFWaveHeight` 0). Normal: 0 mismatches
  over 28 programs × 200; with cross(N, B) instead, 1,399 of 1,400 fail.

## Terrain composite slots

A composite map is bound to one of four slots on the texture side and read by
rank on the shader side, and the two count differently. The texture side takes
rows in order that have a `_CM` and any of UseGloss, UseNoiseBlending,
UseParallax. The shader side counts noise rows only. Where a row flags gloss or
parallax without noise, a noise row reads an earlier row's composite.

- Read: Dev Cut `CTerrainPatchLOD::RecreatePreLightPassPropertyState`
  @0xc8a2c0 binds the composites (@0xc8a69c–@0xc8a6fa; GUP @0x755530 agrees).
  `CDivTerrainSplatPreLightPassMaterial::GenerateDescriptor` @0x110c1c0 (Dev
  Cut @0x48e6a0) takes a slot per row with gloss or noise, stops at 4, and
  never reads parallax; gloss is always off on terrain (see above).
- Measured: over the 312 alpha heaps in the shipped `Terrain.xml` files, layer
  = position in `<Textures>`, first eight rows: 26 heaps disagree, 23 in
  `001_BattleTower_Beach/Main` and 3 in `BrokenValley_2/Main`, none in
  Banditcamp.

## Static assets

A region's `ASSET` nodes are props streamed by level. Level 0 is inline in
`StaticMeshes.nif`; level n > 0 is
`Win32/CompiledAssets/<asset>/<LODGroupNN>/<n>.nif`. With
`StaticAssetHighQuality` on, the finest level is requested and the finest
loaded one drawn. `StaticAssets.xml` gives each placement its switch distances
in cm and whether it casts shadows.

- Read: `CRegionVisual::ParseRegionNode` @0x6a3790, `CStaticAssetManager::Init`
  @0x6fe830 (Dev Cut @0xc06bf0, found by its only reference to the string
  `StaticAssets.xml`), `CStaticAssetDataManager::RequestLoadData` @0x73e040,
  `CollectLODNodeNames` @0x73e310, `CStaticAsset::UpdateStreaming` @0x742c60
  (Dev Cut @0xc772d0), `EvaluateLODNode` @0x742a40,
  `CStaticAssetManager::LoadXML` @0x6fe390, `FindDescriptor` @0x6fdfb0,
  `CStaticAssetDescriptor` constructor @0x740860.
- Measured: `Win32/CompiledAssets` holds 6 `0.nif`, 296 `1.nif` and 164
  `2.nif`; the six `0.nif` are Battle Tower upgrades attached at run time. In
  the tutorial's 37 LOD nodes only level 0 has geometry.
  `CNifManager::ms_fRescaleSize` is 0.01 in both exes (GUP @0x140aab8), which
  makes the distances cm. Of 795 descriptors in 28 `StaticAssets.xml` files,
  452 match `AssetDataDescriptors.xml`, 210 differ in distance only, 94 have
  no distances, 38 name no entry there, 1 has different level names — and the
  XML is what `UpdateStreaming` compares. `CastsShadow` is 1 on 513 and 0 on
  282; 794 are `STATIC_ASSET`, 1 `SHADOW_DUMMY`. Banditcamp has no static
  assets.
