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


def build_material(shape, game_root: Path, cache: Path):
    """One material per shape, from its NiTexturingProperty."""
    properties = list(shape.properties or ())
    texturing = next(
        (p for p in properties if type(p).__name__ == "NiTexturingProperty"), None
    )
    material_property = next(
        (p for p in properties if type(p).__name__ == "NiMaterialProperty"), None
    )

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

    return material
