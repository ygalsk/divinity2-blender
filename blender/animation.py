"""Clips as Blender actions.

A pose in Blender is expressed against the bone's rest position, not against
the parent. The clip gives the bone's local transform relative to its parent,
so each sample has to be taken back into rest space:

    matrix_basis = rest_local⁻¹ @ local_from_clip

Skipping that step produces an armature that moves -- so every count agrees --
but whose bones sit wherever the rest pose happened to differ, which reads as
a broken rig rather than a wrong conversion.
"""

import bpy
from mathutils import Matrix, Quaternion, Vector

from ..divinity2 import animation as dv2_animation

#: A component the file does not carry is written as -FLT_MAX, not left out.
#: `trs_valid`, which is supposed to say which of the three are present, is an
#: empty array at NIF 20.3.0.9 -- the version does not write it. The sentinel
#: in the value is the only thing that tells the truth.
INVALID = 3.4028234663852886e38


def _present(value: float) -> bool:
    return abs(value) < INVALID


def _static(transform, factor: float):
    """The value of a track that is not animated."""
    location = Vector((0.0, 0.0, 0.0))
    rotation = Quaternion((1.0, 0.0, 0.0, 0.0))
    scale = 1.0

    if transform is not None:
        t = transform.translation
        if _present(t.x) and _present(t.y) and _present(t.z):
            location = Vector((t.x, t.y, t.z)) * factor

        r = transform.rotation
        if _present(r.w) and _present(r.x):
            candidate = Quaternion((r.w, r.x, r.y, r.z))
            if candidate.magnitude > 1e-6:
                rotation = candidate.normalized()

        if _present(transform.scale) and transform.scale > 0.0:
            scale = transform.scale

    return location, rotation, scale


def _sample(track, at: float, factor: float):
    """Location, rotation and scale of one bone at one point in the clip."""
    location, rotation, scale = _static(track.static, factor)

    if track.translations:
        t = dv2_animation.evaluate(track.translations, at)
        location = Vector(t) * factor
    if track.rotations:
        r = dv2_animation.evaluate(track.rotations, at)
        rotation = Quaternion(r).normalized()
    if track.scales:
        scale = dv2_animation.evaluate(track.scales, at)[0]

    return location, rotation, scale


def _rest_local(bone) -> Matrix:
    """A bone's rest transform relative to its parent."""
    if bone.parent is None:
        return bone.matrix_local.copy()
    return bone.parent.matrix_local.inverted_safe() @ bone.matrix_local


def build_action(armature_obj, clip, factor: float, fps: int | None = None):
    """One clip as one Blender action. Returns the action, or None."""
    tracks = [t for t in dv2_animation.tracks(clip.sequence)]
    if not tracks:
        return None

    fps = fps or bpy.context.scene.render.fps
    frames = max(2, int(round(clip.duration * fps)) + 1)

    action = bpy.data.actions.new(f"{armature_obj.name}|{clip.name}")
    action.use_fake_user = True

    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()
    previous = armature_obj.animation_data.action
    armature_obj.animation_data.action = action

    pose_bones = armature_obj.pose.bones
    rest = {b.name: _rest_local(b) for b in armature_obj.data.bones}
    used = 0

    for track in tracks:
        bone = pose_bones.get(track.node)
        if bone is None:
            continue
        bone.rotation_mode = "QUATERNION"
        basis = rest[track.node].inverted_safe()
        used += 1

        for frame in range(frames):
            at = frame / (frames - 1)
            location, rotation, scale = _sample(track, at, factor)
            local = Matrix.LocRotScale(location, rotation, (scale, scale, scale))
            bone.matrix_basis = basis @ local

            number = 1 + frame
            bone.keyframe_insert("location", frame=number, group=track.node)
            bone.keyframe_insert("rotation_quaternion", frame=number, group=track.node)
            bone.keyframe_insert("scale", frame=number, group=track.node)

    armature_obj.animation_data.action = previous
    if not used:
        bpy.data.actions.remove(action)
        return None

    action.frame_range  # realise the range Blender caches
    return action


def build_actions(armature_obj, clips, factor: float) -> list:
    """Every clip of a character, as actions on its armature."""
    built = []
    for clip in clips:
        action = build_action(armature_obj, clip, factor)
        if action is not None:
            built.append(action)
    return built
