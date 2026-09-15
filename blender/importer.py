"""Importing one Divinity II model into the current Blender scene.

A character and a barrel take the same path. Where they differ is what the
file filled in: a barrel has no skeleton, so no armature is built and every
shape keeps its own node transform.
"""

from dataclasses import dataclass, field
from pathlib import Path

import bpy

from ..divinity2 import attach, lod, rig
from ..divinity2.character import read_clips, read_model
from ..divinity2.nif import UNITS_PER_METRE

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


def import_asset(
    path,
    game_root,
    cache=None,
    scale=None,
    with_animation: bool = True,
    shared_clips: bool = True,
) -> Result:
    """Read any model file and build it: armature, meshes, skin, materials, clips."""
    game_root = Path(game_root)
    cache = Path(cache) if cache else game_root.parent / ".dv2-texture-cache"
    character = read_model(path)
    result = Result()

    # Half the characters carry no skeleton: they share their family's.
    skeleton = rig.shared_skeleton(character, game_root)
    rest = None

    if skeleton is not None:
        rest = scene.rest_matrices(skeleton)
        result.armature = scene.build_armature(
            skeleton, character.name, _factor(skeleton, scale), rest
        )
        result.bones = len(result.armature.data.bones)
        result.shared_rig = character.skeleton is None

    bone_names = (
        [b.name for b in result.armature.data.bones] if result.armature else []
    )

    carried_so_far = 0
    for mesh in character.meshes:
        bone = None
        if attach.is_attachable(mesh.name):
            bone = attach.attachment_bone(
                attach.weapon_name(mesh.name), bone_names, carried_so_far
            )
            carried_so_far += 1

        factor = _factor(mesh.root, scale)
        # A culled node takes its whole subtree with it, the way the engine's
        # `NiAVObject::Cull` does. `walk` is depth-first, so a parent is always
        # seen before its children.
        culled = set()
        # The node names above a shape are the only thing that tells some
        # geometry apart: a region's built mesh carries its own low-detail
        # terrain and the author's shadow helper under named nodes, with no
        # flag on either, and the engine filters them by that name. The shape
        # itself is usually called `Editable Poly`.
        trail = {}
        for node, world, parent in scene.walk(mesh.root):
            if lod.is_culled(node) or id(parent) in culled:
                culled.add(id(node))
            above = trail.get(id(parent), "")
            trail[id(node)] = f"{above}/{node.name}" if above else str(node.name)
            if type(node).__name__ not in SHAPES:
                continue
            if node.data is None or not node.data.num_vertices:
                continue

            obj = scene.build_mesh(node, world, factor, rest)
            obj["dv2_path"] = trail.get(id(node), str(node.name))
            result.objects.append(obj)

            # Every level of detail is in the file; show only the nearest,
            # never a shape the engine culls, and never one the buffer marks
            # NiHide.
            if (
                id(node) in culled
                or lod.is_hidden(node)
                or not lod.is_nearest(node)
            ):
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
            else:
                # No socket for it. It still travels with the character.
                obj.parent = result.armature

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

    if with_animation and clips and result.armature is not None:
        # A clip's translation keys are in game units in the bone's own local
        # space, and a Blender bone has no scale to carry the root's 0.01 --
        # `EditBone.matrix` keeps the orientation and drops it. So keys always
        # convert by the full unit, never by the tree's factor.
        result.actions = dv2_animation.build_actions(
            result.armature, clips, 1.0 / (scale or UNITS_PER_METRE)
        )
        if result.actions:
            first = _resting(result.actions)
            result.armature.animation_data.action = first
            bpy.context.scene.frame_start = 1
            bpy.context.scene.frame_end = int(first.frame_range[1])

    return result


def _factor(root, scale=None) -> float:
    """Game units to metres for one node tree.

    Every model in the game is authored in centimetres. How many of those
    units reach the world is stated on the tree's root node: a character
    leaves `Scene Root` at 1.0, and every scenery, item, effect and fortress
    bakes the conversion into it as 0.01. `scene.walk` already applies that
    scale, so the factor must not apply it a second time -- hence the product.

    `scale` overrides the unit, not the root: it is there for a file that
    turns out to be authored in something else.
    """
    return 1.0 / ((scale or UNITS_PER_METRE) * float(root.scale))


#: What the engine calls the state a character stands in, from its own
#: animation table: `CGameLogic_FixedStrings::ms_kAnimation_Still`, beside
#: `ms_kAnimation_F_Normal` and the rest of the movement set.
RESTING = "Still"


def _resting(actions):
    """The clip to show first.

    A character's own `.cat` holds only its variant clips -- `Black_Goblin`
    has `Stunned`, `Flee`, `Blind` and twelve ways to die -- and the standing
    clip comes from the family's shared set, which is appended after. Taking
    the first action therefore shows a goblin mid-stun.
    """
    for want in (RESTING, "Idle"):
        for action in actions:
            if action.name.rpartition("|")[2].startswith(want):
                return action
    return actions[0]
