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
from mathutils import Matrix, Vector

#: Game units per metre. The game's own unit is roughly a centimetre; this is
#: the factor that puts a character at a believable height in Blender. It is a
#: measurement, not a constant of the format -- see `docs/units.md`.
UNITS_PER_METRE = 100.0


def matrix_of(block) -> Matrix:
    """The local transform of any NiAVObject, as Blender wants it."""
    r = block.rotation
    basis = Matrix((
        (r.m_11, r.m_12, r.m_13),
        (r.m_21, r.m_22, r.m_23),
        (r.m_31, r.m_32, r.m_33),
    )).transposed()
    m = basis.to_4x4() @ Matrix.Scale(block.scale, 4)
    m.translation = Vector((block.translation.x, block.translation.y, block.translation.z))
    return m


def walk(node, parent_matrix=Matrix.Identity(4), parent=None):
    """Yield (node, world matrix, parent node) over a NIF node tree."""
    world = parent_matrix @ matrix_of(node)
    yield node, world, parent
    for child in getattr(node, "children", ()) or ():
        if child is None:
            continue
        yield from walk(child, world, node)


def _is_shape(block) -> bool:
    return type(block).__name__ in ("NiTriShape", "NiTriStrips")


# --------------------------------------------------------------------------
# the armature


def build_armature(skeleton_root, name: str, scale: float):
    """One armature from the skeleton's NiNode tree, bone transforms kept."""
    armature = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, armature)
    bpy.context.collection.objects.link(obj)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = {}
    for node, world, parent in walk(skeleton_root):
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
        bone.matrix = _scaled(world, scale)

        if parent is not None:
            bone.parent = edit_bones.get(str(parent.name))
        edit_bones[bone_name] = bone

    bpy.ops.object.mode_set(mode="OBJECT")
    return obj


def _scaled(world: Matrix, scale: float) -> Matrix:
    m = world.copy()
    m.translation = m.translation * scale
    return m


# --------------------------------------------------------------------------
# the meshes


def build_mesh(shape, world: Matrix, scale: float):
    """One NiTriShape as one Blender object, with its own transform."""
    data = shape.data
    name = str(shape.name) or "shape"

    vertices = [(v.x * scale, v.y * scale, v.z * scale) for v in data.vertices]
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
