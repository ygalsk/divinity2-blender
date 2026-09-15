"""Importing one Divinity II character into the current Blender scene."""

from dataclasses import dataclass
from pathlib import Path

import bpy

from ..divinity2 import rig
from ..divinity2.character import read_character

from . import material as dv2_material
from . import scene


@dataclass
class Result:
    """What arrived, so a caller can check rather than trust."""

    armature: object = None
    objects: list = None
    bones: int = 0
    shared_rig: bool = False
    skinned: int = 0
    materials: int = 0
    clips: int = 0

    def __post_init__(self):
        if self.objects is None:
            self.objects = []


def import_character(path, game_root, cache=None, scale=None) -> Result:
    """Read a `.cat` and build it: armature, meshes, skin, materials."""
    game_root = Path(game_root)
    cache = Path(cache) if cache else game_root.parent / ".dv2-texture-cache"
    factor = 1.0 / (scale or scene.UNITS_PER_METRE)

    character = read_character(path)
    result = Result(clips=len(character.clips))

    # Half the characters carry no skeleton: they share their family's.
    skeleton = rig.shared_skeleton(character, game_root)
    if skeleton is not None:
        result.armature = scene.build_armature(skeleton, character.name, factor)
        result.bones = len(result.armature.data.bones)
        result.shared_rig = character.skeleton is None

    for mesh in character.meshes:
        for node, world, _parent in scene.walk(mesh.root):
            if type(node).__name__ not in ("NiTriShape", "NiTriStrips"):
                continue
            if node.data is None or not node.data.num_vertices:
                continue

            obj = scene.build_mesh(node, world, factor)
            result.objects.append(obj)

            built = dv2_material.build_material(node, game_root, cache)
            if built is not None:
                obj.data.materials.append(built)
                result.materials += 1

            if result.armature is not None:
                if scene.bind_skin(obj, node, result.armature):
                    result.skinned += 1

    return result
