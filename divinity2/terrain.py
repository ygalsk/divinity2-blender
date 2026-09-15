"""The ground of a region, and the textures that are not in the model.

A region's terrain is inside its `StaticMeshes.nif`, under a node called
`[--WorldProcessedTerrain--]`, as one `NiLODNode` per patch. Three things
about it are unlike every other mesh in the game.

**Its levels of detail are mostly missing.** Each patch's `NiLODNode` holds
one level inline and an empty stub for every finer one, waiting for a streamed
file the region may not ship. `divinity2.lod` picks the finest that actually
holds geometry; without that the ground of all 17 regions is lost.

**It carries no `NiTexturingProperty`.** A terrain shape resolves only a
`NiMaterialProperty`, so a reader that asks the model what to draw gets
nothing and the ground arrives white.

**Its material is splatted, and `Terrain.xml` holds the whole recipe.**

```
<Terrain splatdistance="116" splatblenddistance="20">
  <TerrainPatch index="6">
    <AlphaHeap>
      <AlphaMap path="TerrainTextures\\AlphaMaps\\6_6_AlphaMap_1.tga">
        <Layers><ID layerID="6" MaskIndex="2" AlphaMapIndex="1"/> ... </Layers>
    <MegaTexture path="TerrainTextures\\MegaTexture_6.dds"/>
  <Textures>
    <Texture path="BV2_Moss_A.dds" path_NM="..." TextureTiling="50" ID="6"/>
```

One `Texture` per `ID` gives the layer's picture and how often it tiles across
the patch. One channel of one alpha map -- `MaskIndex` 0 to 3 is red, green,
blue, alpha -- gives that layer's weight. The `MegaTexture` is the same ground
baked flat for distance; the game fades to it past `splatdistance`.

Two extensions lie in this chain and both were measured, not assumed: a
`MegaTexture` named `.dds` is a NIF like every other texture in this game, and
an `AlphaMap` named `.tga` is a `.dds` on disk, which is also a NIF.
`Terrain.xml` itself is Larian's binary XML -- see `divinity2.binxml`.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import binxml

#: The node a region's terrain hangs under.
ROOT_NODE = "[--WorldProcessedTerrain--]"

#: Where the region keeps its own pictures, beside `StaticMeshes.nif`.
TEXTURE_DIR = "TerrainTextures"

#: What the file calls the descriptor.
DESCRIPTOR = "Terrain.xml"

#: `MaskIndex` 0..3 is the alpha map's red, green, blue, alpha channel.
CHANNELS = ("R", "G", "B", "A")

_PATCH = re.compile(r"Terrain_Patch_(\d+)")


@dataclass
class Layer:
    """One splat layer of one patch."""

    texture: str            #: the diffuse, as the file names it
    normal: str             #: its normal map, or ""
    tiling: float           #: how many times it repeats across the patch
    mask: Path | None       #: the alpha map that weights it
    channel: int            #: which of the mask's four channels


@dataclass
class Patch:
    """One terrain patch: the baked picture, and the recipe behind it."""

    index: int
    megatexture: Path | None = None
    layers: list = field(default_factory=list)


def patch_of(path: str) -> int | None:
    """The patch index in a node path, or None when it is not terrain."""
    match = _PATCH.search(path or "")
    return int(match.group(1)) if match else None


def _beside(model_path, named: str) -> Path | None:
    """A path `Terrain.xml` names, resolved beside the model.

    The descriptor writes an alpha map as `.tga` and the file is `.dds`, the
    same way a mesh writes `.tga` for a texture that is a NIF.
    """
    if not named:
        return None
    here = Path(model_path).parent / named.replace("\\", "/")
    for candidate in (here, here.with_suffix(".dds")):
        if candidate.is_file():
            return candidate
    return None


def patches(model_path) -> dict:
    """Every patch the region describes, by index.

    Returns `{}` when the region ships no `Terrain.xml`, which is what a model
    outside a region does.
    """
    descriptor = Path(model_path).parent / DESCRIPTOR
    if not descriptor.is_file():
        return {}
    try:
        root = binxml.read(descriptor.read_bytes())
    except (binxml.Malformed, OSError):
        return {}

    textures = {}
    for entry in root.find_all("Texture"):
        try:
            layer_id = int(entry.get("ID", "-1"))
        except ValueError:
            continue
        if layer_id >= 0:
            textures[layer_id] = entry

    found = {}
    for node in root.find_all("TerrainPatch"):
        try:
            index = int(node.get("index"))
        except (TypeError, ValueError):
            continue
        patch = Patch(index=index)
        for mega in node.find_all("MegaTexture"):
            patch.megatexture = _beside(model_path, mega.get("path", ""))
            break
        for alpha in node.find_all("AlphaMap"):
            mask = _beside(model_path, alpha.get("path", ""))
            for entry in alpha.find_all("ID"):
                try:
                    layer_id = int(entry.get("layerID"))
                    channel = int(entry.get("MaskIndex"))
                except (TypeError, ValueError):
                    continue
                texture = textures.get(layer_id)
                if texture is None:
                    continue
                patch.layers.append(Layer(
                    texture=texture.get("path", ""),
                    normal=texture.get("path_NM", ""),
                    tiling=float(texture.get("TextureTiling", "1") or 1),
                    mask=mask,
                    channel=channel,
                ))
        # Lowest layer first, so a material can lay them down in order.
        patch.layers.sort(key=lambda lay: (str(lay.mask), lay.channel))
        found[index] = patch
    return found


def megatexture(model_path, index: int) -> Path | None:
    """The baked diffuse for one patch."""
    patch = patches(model_path).get(index)
    return patch.megatexture if patch else None
