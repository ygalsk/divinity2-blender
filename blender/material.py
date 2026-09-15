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


def build_material(shape, game_root: Path, cache: Path):
    """One material per shape, from its property blocks."""
    found = dv2_property.properties(shape)
    texturing = found.get("NiTexturingProperty")
    material_property = found.get("NiMaterialProperty")
    alpha_property = found.get("NiAlphaProperty")
    specular = found.get("NiSpecularProperty")

    name = str(shape.name) or "material"
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

    if alpha_property is not None:
        decoded = dv2_property.alpha(alpha_property)
        if decoded.transparent:
            _transparency(material, principled, diffuse_node, decoded)

    return material
