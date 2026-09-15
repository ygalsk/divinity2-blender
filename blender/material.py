"""Materials for imported assets.

A Principled BSDF, not a Diffuse BSDF. Blender's own glTF and FBX exporters
read Principled and ignore Diffuse, so a Diffuse material means the asset
arrives in Unity untextured -- which is the whole point of importing it.

The texture itself comes from `divinity2.texture`, which turns the game's
texture NIF into DDS bytes. Blender loads DDS natively, so the bytes are
written once into a cache directory and loaded from there.
"""

from pathlib import Path

import bpy

from ..divinity2 import material as dv2_property
from ..divinity2 import terrain as dv2_terrain
from ..divinity2 import texture as dv2_texture

#: Which NiTexturingProperty slot means what.
DIFFUSE = "base_texture"
NORMAL = "normal_texture"
GLOSS = "gloss_texture"


def _source_name(texturing_property, slot: str) -> str | None:
    if not getattr(texturing_property, f"has_{slot}", 0):
        return None
    source = getattr(texturing_property, slot).source
    return str(source.file_name) if source is not None else None


def cached_image(texture_name: str, game_root: Path, cache: Path):
    """The game's texture NIF as a Blender image, converted once."""
    cache.mkdir(parents=True, exist_ok=True)
    dds = cache / (Path(texture_name).stem + ".dds")

    if not dds.exists():
        source = dv2_texture.texture_path(texture_name, game_root)
        if not source.exists():
            return None
        dds.write_bytes(dv2_texture.to_dds(source))

    return bpy.data.images.load(str(dds), check_existing=True)


def _transparency(material, principled, image_node, alpha) -> None:
    """Wire the diffuse texture's alpha channel the way the game reads it.

    A cut-out (`GREATER` than a threshold) becomes a hard comparison, so the
    edges stay crisp instead of fading; anything else blends. Additive shapes
    -- glows and magic planes -- also lose their shadow, which is what
    `ONE + ONE` means on screen.
    """
    tree = material.node_tree
    if alpha.testing and image_node is not None:
        compare = tree.nodes.new("ShaderNodeMath")
        compare.operation = "GREATER_THAN"
        compare.inputs[1].default_value = alpha.threshold / 255.0
        tree.links.new(image_node.outputs["Alpha"], compare.inputs[0])
        tree.links.new(compare.outputs["Value"], principled.inputs["Alpha"])
        material.surface_render_method = "DITHERED"
    elif image_node is not None:
        tree.links.new(image_node.outputs["Alpha"], principled.inputs["Alpha"])
        material.surface_render_method = "BLENDED"
    else:
        material.surface_render_method = "BLENDED"

    if alpha.additive:
        material.use_transparent_shadow = False


def build_material(drawn, game_root: Path, cache: Path, source=None):
    """One material per drawable, from the property state the walk resolved.

    The state comes from the walk, not from the shape: Gamebryo attaches
    render state to a node and a shape inherits it from the nearest ancestor
    that carries one (`NiAVObject::PushLocalProperties`).
    """
    found = drawn.properties
    texturing = found.get("NiTexturingProperty")
    material_property = found.get("NiMaterialProperty")
    alpha_property = found.get("NiAlphaProperty")
    specular = found.get("NiSpecularProperty")

    name = drawn.name or "material"
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    principled = material.node_tree.nodes["Principled BSDF"]

    if material_property is not None:
        colour = material_property.diffuse_color
        principled.inputs["Base Color"].default_value = (
            colour.r, colour.g, colour.b, 1.0
        )
        # NIF glossiness runs the opposite way to Blender's roughness.
        principled.inputs["Roughness"].default_value = max(
            0.0, 1.0 - min(material_property.glossiness / 100.0, 1.0)
        )

    # The game turns specular off per shape; every character shape measured
    # has it on, so this only ever shows up on the ones that do not.
    if specular is not None and not int(specular.flags) & 1:
        principled.inputs["Specular IOR Level"].default_value = 0.0

    diffuse_node = None
    if texturing is not None:
        diffuse = _source_name(texturing, DIFFUSE)
        if diffuse:
            image = cached_image(diffuse, game_root, cache)
            if image is not None:
                node = material.node_tree.nodes.new("ShaderNodeTexImage")
                node.image = image
                material.node_tree.links.new(
                    node.outputs["Color"], principled.inputs["Base Color"]
                )
                diffuse_node = node

        normal = _source_name(texturing, NORMAL)
        if normal:
            image = cached_image(normal, game_root, cache)
            if image is not None:
                image.colorspace_settings.name = "Non-Color"
                node = material.node_tree.nodes.new("ShaderNodeTexImage")
                node.image = image
                mapping = material.node_tree.nodes.new("ShaderNodeNormalMap")
                material.node_tree.links.new(
                    node.outputs["Color"], mapping.inputs["Color"]
                )
                material.node_tree.links.new(
                    mapping.outputs["Normal"], principled.inputs["Normal"]
                )

    if diffuse_node is None and source is not None:
        index = dv2_terrain.patch_of(drawn.path)
        if index is not None:
            _terrain(material, principled, source, index, cache)

    if alpha_property is not None:
        decoded = dv2_property.alpha(alpha_property)
        if decoded.transparent:
            _transparency(material, principled, diffuse_node, decoded)

    return material


def _image_of(path: Path, cache: Path):
    """A texture that lives beside the region rather than in `Textures/`.

    It is named `.dds` and it is a NIF, the same way a mesh names its texture
    `.tga` and the file is a NIF. The bytes inside are a DDS surface with the
    128-byte header missing, so the same conversion applies.
    """
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{Path(path).stem}.dds"
    try:
        if not out.exists():
            out.write_bytes(dv2_texture.to_dds(path))
        image = bpy.data.images.load(str(out), check_existing=True)
    except (ValueError, RuntimeError, OSError):
        return None
    image.name = Path(path).stem
    return image


def _terrain(material, principled, source, index: int, cache: Path) -> None:
    """The ground: a baked picture with the splat layers mixed over it.

    A terrain shape resolves no texturing property, so nothing in the model
    says what to draw. `Terrain.xml` does: one `MegaTexture` per patch, baked
    flat, and a list of layers each with its own tiling and one channel of one
    alpha map as its weight. The game fades between the two at
    `splatdistance`; Blender has no such distance, so the baked picture is the
    base and every layer is mixed over it by its mask -- where a mask is zero
    the baked ground shows through, which is what the game draws far away.
    """
    patch = dv2_terrain.patches(source).get(index)
    if patch is None:
        return
    tree = material.node_tree
    coords = tree.nodes.new("ShaderNodeTexCoord")
    principled.inputs["Roughness"].default_value = 0.9

    colour = None
    if patch.megatexture is not None:
        baked = _image_of(patch.megatexture, cache)
        if baked is not None:
            node = tree.nodes.new("ShaderNodeTexImage")
            node.image = baked
            tree.links.new(coords.outputs["UV"], node.inputs["Vector"])
            colour = node.outputs["Color"]

    for layer in patch.layers:
        image = cached_image(layer.texture, _game_of(cache, source), cache)
        mask = _image_of(layer.mask, cache) if layer.mask else None
        if image is None or mask is None:
            continue

        tiled = tree.nodes.new("ShaderNodeMapping")
        tiled.inputs["Scale"].default_value = (layer.tiling, layer.tiling, 1.0)
        tree.links.new(coords.outputs["UV"], tiled.inputs["Vector"])
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        node.extension = "REPEAT"
        tree.links.new(tiled.outputs["Vector"], node.inputs["Vector"])

        weight = tree.nodes.new("ShaderNodeTexImage")
        weight.image = mask
        weight.image.colorspace_settings.name = "Non-Color"
        tree.links.new(coords.outputs["UV"], weight.inputs["Vector"])
        split = tree.nodes.new("ShaderNodeSeparateColor")
        tree.links.new(weight.outputs["Color"], split.inputs["Color"])
        channel = (
            weight.outputs["Alpha"] if layer.channel == 3
            else split.outputs[layer.channel]
        )

        if colour is None:
            colour = node.outputs["Color"]
            continue
        mix = tree.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        tree.links.new(channel, mix.inputs["Factor"])
        tree.links.new(colour, mix.inputs[6])       # A
        tree.links.new(node.outputs["Color"], mix.inputs[7])   # B
        colour = mix.outputs[2]

    if colour is not None:
        tree.links.new(colour, principled.inputs["Base Color"])


def _game_of(cache: Path, source) -> Path:
    """Where the install is, from the model being read.

    A layer texture lives in `Win32/Textures` like every other, and the model
    is somewhere under `World/`, so the install root is above both.
    """
    for parent in Path(source).parents:
        if (parent / "Win32" / "Textures").is_dir():
            return parent
    return Path(cache).parent
