"""Building a Divinity II character in Blender.

This module knows Blender. It does not know how a NIF file is laid out --
`divinity2` does that. It receives blocks the reader produced and turns them
into objects, an armature and materials.

The one rule that decides whether a character arrives whole: every `NiTriShape`
keeps its own object and its own transform. Collapsing the shapes of a
character into a single mesh loses the transforms and the character arrives as
a heap.
"""

import bpy
import numpy as np
from mathutils import Matrix, Vector

from ..divinity2 import graph
from ..divinity2 import skin as dv2_skin

#: Game units per metre. The game's own unit is roughly a centimetre; this is
#: the factor that puts a character at a believable height in Blender. It is a
#: measurement, not a constant of the format -- see `docs/units.md`.
UNITS_PER_METRE = 100.0


def matrix_of(block) -> Matrix:
    """The local transform of any NiAVObject, as Blender wants it."""
    return Matrix(graph.matrix_of(block).tolist())


def _is_shape(block) -> bool:
    return type(block).__name__ in graph.SHAPES


def rest_matrices(skeleton_root) -> dict:
    """Every bone's rest transform, in game units, keyed by name.

    The skeleton file is the rest pose. Each mesh file carries a copy of the
    skeleton too, but that copy is collapsed -- every bone node in it sits at
    the origin -- so it gives the parentage and nothing else.

    In game units on purpose: the skin data that meets these matrices is in
    game units too, and converting to metres first would leave the two halves
    of the same equation on different scales.
    """
    out = {}
    stack = [(skeleton_root, np.eye(4))]
    while stack:
        node, parent = stack.pop()
        world = parent @ graph.matrix_of(node)
        name = str(node.name)
        if name and not _is_shape(node):
            out.setdefault(name, world)
        stack += [(c, world) for c in reversed(
            [c for c in (getattr(node, "children", ()) or []) if c is not None])]
    return out


# --------------------------------------------------------------------------
# the armature


def build_armature(skeleton_root, name: str, scale: float, rest: dict | None = None):
    """One armature from the skeleton's NiNode tree.

    The tree gives the hierarchy -- which bone parents which -- and `rest`
    gives where each bone stands. They come from different places on purpose:
    the parentage is only in the skeleton file, the pose is only trustworthy
    in the skin.
    """
    armature = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, armature)
    bpy.context.collection.objects.link(obj)

    _edit(obj, True)
    edit_bones = {}
    stack = [(skeleton_root, np.eye(4), None)]
    while stack:
        node, parent_world, parent = stack.pop()
        world = Matrix((parent_world @ graph.matrix_of(node)).tolist())
        stack += [(c, parent_world @ graph.matrix_of(node), node) for c in reversed(
            [c for c in (getattr(node, "children", ()) or []) if c is not None])]
        if _is_shape(node):
            continue
        bone_name = str(node.name)
        if not bone_name:
            continue

        bone = armature.edit_bones.new(bone_name)
        # A zero-length bone is dropped by Blender, so give every bone a
        # length; the matrix carries the real orientation.
        bone.head = (0.0, 0.0, 0.0)
        bone.tail = (0.0, 0.1, 0.0)
        placed = world
        if rest is not None and bone_name in rest:
            placed = Matrix(rest[bone_name].tolist())
        bone.matrix = _scaled(placed, scale)

        if parent is not None:
            bone.parent = edit_bones.get(str(parent.name))
        edit_bones[bone_name] = bone

    _edit(obj, False)
    return obj


def _edit(obj, on: bool) -> None:
    """Enter or leave edit mode on `obj`.

    Edit mode is only reachable through an operator, and the operator reads
    the context rather than its arguments: the object has to be the active one
    and the view layer has to know about it. `temp_override` states that
    outright, which is what makes this work when the add-on is driven from a
    script and `bpy.context` has no active object at all.
    """
    view_layer = bpy.context.view_layer
    active = view_layer.objects.active
    if on:
        if active is not None and active.mode != "OBJECT":
            with bpy.context.temp_override(active_object=active, object=active):
                bpy.ops.object.mode_set(mode="OBJECT")
        view_layer.objects.active = obj
        obj.select_set(True)
        view_layer.update()

    with bpy.context.temp_override(
        active_object=obj, object=obj, selected_objects=[obj]
    ):
        bpy.ops.object.mode_set(mode="EDIT" if on else "OBJECT")


def _scaled(world: Matrix, scale: float) -> Matrix:
    m = world.copy()
    m.translation = m.translation * scale
    return m


# --------------------------------------------------------------------------
# the meshes


def build_mesh(drawn, scale: float, rest: dict | None = None):
    """One drawable shape as one Blender object, with its own transform.

    A skinned shape is not placed by its node transform. Its geometry lives in
    skin space and is carried entirely by the bones, so it is moved into the
    armature's rest pose here and the object then sits at the origin. Placing
    it by its node transform as well applies the offset twice.
    """
    shape = drawn.shape
    data = drawn.data
    world = Matrix(drawn.world.tolist())
    name = drawn.name

    raw = np.array([(v.x, v.y, v.z) for v in data.vertices], dtype=np.float64)
    moved = dv2_skin.to_rest_pose(raw, shape, rest) if rest else None
    if moved is not None:
        raw = moved
        world = Matrix.Identity(4)

    vertices = (raw * scale).tolist()
    faces = [(t.v_1, t.v_2, t.v_3) for t in data.triangles]

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=False)

    if data.has_normals and len(data.normals):
        mesh.normals_split_custom_set_from_vertices(
            [(n.x, n.y, n.z) for n in data.normals]
        )

    # `has_uv` is a legacy field and reads 0 at NIF 20.3.0.9, whatever the
    # shape actually carries. The truth is in `data_flags.num_uv_sets`.
    if len(data.uv_sets):
        uv_layer = mesh.uv_layers.new(name="UVMap")
        source = data.uv_sets[0]
        for loop in mesh.loops:
            uv = source[loop.vertex_index]
            # NIF puts the UV origin at the top left, Blender at the bottom.
            uv_layer.data[loop.index].uv = (uv.u, 1.0 - uv.v)

    obj = bpy.data.objects.new(name, mesh)
    obj.matrix_world = _scaled(world, scale)
    bpy.context.collection.objects.link(obj)
    return obj


def bind_skin(obj, shape, armature_obj) -> int:
    """Weights from NiSkinData onto vertex groups. Returns the bone count."""
    skin = getattr(shape, "skin_instance", None)
    if skin is None or skin.data is None:
        return 0

    bones = [str(b.name) for b in skin.bones]
    for bone_name, bone_data in zip(bones, skin.data.bone_list):
        group = obj.vertex_groups.new(name=bone_name)
        for weight in bone_data.vertex_weights:
            group.add([weight.index], weight.weight, "REPLACE")

    modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
    modifier.object = armature_obj
    obj.parent = armature_obj
    return len(bones)


def attach_to_bone(obj, armature_obj, bone_name: str) -> bool:
    """Carry a weapon on one bone instead of deforming it with the skeleton.

    Blender parents a child to a bone's *tail*, so the child has to be moved
    back along the bone's own length, or the weapon floats a bone's length away
    from the hand holding it.
    """
    bone = armature_obj.data.bones.get(bone_name)
    if bone is None:
        return False

    world = obj.matrix_world.copy()
    obj.parent = armature_obj
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_world = (
        armature_obj.matrix_world
        @ Matrix.Translation(bone.tail_local - bone.head_local).inverted()
        @ bone.matrix_local
        @ world
    )
    return True
