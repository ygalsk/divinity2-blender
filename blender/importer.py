"""Importing one Divinity II character into the current Blender scene."""

from dataclasses import dataclass, field
from pathlib import Path

import bpy

from ..divinity2 import attach, lod, rig
from ..divinity2.character import read_character, read_clips

from . import animation as dv2_animation
from . import material as dv2_material
from . import scene

SHAPES = ("NiTriShape", "NiTriStrips")


@dataclass
class Result:
    """What arrived, so a caller can check rather than trust."""

    armature: object = None
    objects: list = field(default_factory=list)
    bones: int = 0
    shared_rig: bool = False
    skinned: int = 0
    attached: int = 0
    hidden_lods: int = 0
    materials: int = 0
    clips: int = 0
    actions: list = field(default_factory=list)


def import_character(
    path,
    game_root,
    cache=None,
    scale=None,
    with_animation: bool = True,
    shared_clips: bool = True,
) -> Result:
    """Read a `.cat` and build it: armature, meshes, skin, materials, clips."""
    game_root = Path(game_root)
    cache = Path(cache) if cache else game_root.parent / ".dv2-texture-cache"
    factor = 1.0 / (scale or scene.UNITS_PER_METRE)

    character = read_character(path)
    result = Result()

    # Half the characters carry no skeleton: they share their family's.
    skeleton = rig.shared_skeleton(character, game_root)

    # The skinned shapes come first: their bind poses are the armature's rest,
    # and the skeleton file supplies the hierarchy and fills the gaps.
    skinned_shapes = [
        node
        for mesh in character.meshes
        for node, _w, _p in scene.walk(mesh.root)
        if type(node).__name__ in SHAPES
        and getattr(node, "skin_instance", None) is not None
    ]
    rest = (
        scene.rest_matrices(skeleton, skinned_shapes)
        if skeleton is not None
        else None
    )

    if skeleton is not None:
        result.armature = scene.build_armature(
            skeleton, character.name, factor, rest
        )
        result.bones = len(result.armature.data.bones)
        result.shared_rig = character.skeleton is None

    bone_names = (
        [b.name for b in result.armature.data.bones] if result.armature else []
    )

    for mesh in character.meshes:
        carried = attach.is_attachable(mesh.name)
        bone = (
            attach.attachment_bone(attach.weapon_name(mesh.name), bone_names)
            if carried
            else None
        )

        for node, world, _parent in scene.walk(mesh.root):
            if type(node).__name__ not in SHAPES:
                continue
            if node.data is None or not node.data.num_vertices:
                continue

            obj = scene.build_mesh(node, world, factor, rest)
            result.objects.append(obj)

            # Every level of detail is in the file; show only the nearest.
            if not lod.is_nearest(node):
                obj.hide_set(True)
                obj.hide_render = True
                result.hidden_lods += 1

            built = dv2_material.build_material(node, game_root, cache)
            if built is not None:
                obj.data.materials.append(built)
                result.materials += 1

            if result.armature is None:
                continue

            if scene.bind_skin(obj, node, result.armature):
                result.skinned += 1
            elif bone is not None and scene.attach_to_bone(
                obj, result.armature, bone
            ):
                result.attached += 1

    # A family's shared `.kf` repeats what the character already bundles --
    # a Froblin's own 15 clips are exactly Froblin_Base.kf's 15 -- so the
    # shared set only contributes names the character does not already have.
    clips = list(character.clips)
    if shared_clips:
        known = {c.name for c in clips}
        for kf in rig.clip_files(character, game_root):
            for clip in read_clips(kf):
                if clip.name not in known:
                    known.add(clip.name)
                    clips.append(clip)
    result.clips = len(clips)

    if with_animation and result.armature is not None and clips:
        result.actions = dv2_animation.build_actions(
            result.armature, clips, factor
        )
        if result.actions:
            result.armature.animation_data.action = result.actions[0]
            bpy.context.scene.frame_start = 1
            bpy.context.scene.frame_end = int(result.actions[0].frame_range[1])

    return result
