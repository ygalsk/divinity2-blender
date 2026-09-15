"""Importing one Divinity II character into the current Blender scene."""

from dataclasses import dataclass, field
from pathlib import Path

import bpy

from ..divinity2 import attach, lod, rig
from ..divinity2 import skin as dv2_skin
from ..divinity2.character import read_character, read_clips

from . import animation as dv2_animation
from . import material as dv2_material
from . import scene

SHAPES = ("NiTriShape", "NiTriStrips")


@dataclass
class Result:
    """What arrived, so a caller can check rather than trust."""

    armature: object = None
    armatures: list = field(default_factory=list)
    objects: list = field(default_factory=list)
    bones: int = 0
    shared_rig: bool = False
    skinned: int = 0
    attached: int = 0
    hidden_lods: int = 0
    materials: int = 0
    clips: int = 0
    actions: list = field(default_factory=list)


@dataclass
class _Group:
    """Mesh files that were skinned against the same pose, and their armature."""

    bind: dict
    meshes: list = field(default_factory=list)
    armature: object = None
    rest: dict | None = None


def _group_by_bind(character) -> list[_Group]:
    """A character's mesh files, gathered by the pose they were skinned in.

    A third of the characters carry mesh files whose skeletons disagree --
    FroblinBoss's body and its armour differ by some 800 units on the same
    bone name. One armature cannot rest in two poses, so each group gets its
    own; the bones are named the same, so the same clips drive all of them.
    """
    groups: list[_Group] = []
    for mesh in character.meshes:
        shapes = [
            node
            for node, _w, _p in scene.walk(mesh.root)
            if type(node).__name__ in SHAPES
            and getattr(node, "skin_instance", None) is not None
        ]
        bind = dv2_skin.bind_poses(shapes) if shapes else {}

        for group in groups:
            if dv2_skin.same_pose(group.bind, bind):
                group.meshes.append(mesh)
                group.bind = group.bind or bind
                break
        else:
            groups.append(_Group(bind=bind, meshes=[mesh]))
    return groups


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
    groups = _group_by_bind(character)

    if skeleton is not None:
        for index, group in enumerate(groups):
            group.rest = scene.rest_matrices(skeleton, bind=group.bind)
            suffix = "" if index == 0 else f".{index:03d}"
            group.armature = scene.build_armature(
                skeleton, character.name + suffix, factor, group.rest
            )
        result.armatures = [g.armature for g in groups]
        result.armature = result.armatures[0]
        result.bones = len(result.armature.data.bones)
        result.shared_rig = character.skeleton is None

    bone_names = (
        [b.name for b in result.armature.data.bones] if result.armature else []
    )

    for group in groups:
        for mesh in group.meshes:
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

                obj = scene.build_mesh(node, world, factor, group.rest)
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

                if group.armature is None:
                    continue

                if scene.bind_skin(obj, node, group.armature):
                    result.skinned += 1
                elif bone is not None and scene.attach_to_bone(
                    obj, group.armature, bone
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

    if with_animation and clips and result.armatures:
        for armature in result.armatures:
            built = dv2_animation.build_actions(armature, clips, factor)
            if armature is result.armature:
                result.actions = built
            if built:
                armature.animation_data.action = built[0]
        if result.actions:
            bpy.context.scene.frame_start = 1
            bpy.context.scene.frame_end = int(result.actions[0].frame_range[1])

    return result
