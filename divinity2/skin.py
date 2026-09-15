"""Binding geometry to one armature.

A character's mesh files do not share a skeleton. Each one carries its own
copy, with its own root node, and -- this is the part that costs an afternoon
-- the copies are not in the same pose. `FroblinBoss.nif` and
`FroblinBoss_Armor_A.nif` both have a bone called `Bip01 Spine`, and the two
disagree about where it is by some 800 units.

Matched by node, every shape inside one file agrees to within 2.5 units.
Matched by name across files, they do not agree at all. So a bone is a node,
not a name, and binding a character's shapes to one armature by name alone
silently mixes two skeletons: the body arrives right and the armour arrives
folded somewhere else.

Blender has one rest pose per armature, so the geometry is moved instead. Each
shape is taken out of its own bind pose and into the armature's rest pose,
once, at import:

    v' = Σᵢ wᵢ · Rᵢ · Aᵢ · v

`Aᵢ` takes a vertex from skin space into bone `i`'s space and comes from the
file (`NiSkinData.skin_transform` composed with the bone's own), and `Rᵢ` is
where that bone rests in the armature. After it, the armature deforms the
shape from a rest pose that is genuinely its own.
"""

import numpy as np


def matrix(block) -> np.ndarray:
    """Any NIF transform -- node, skin or bone -- as a 4x4."""
    r = block.rotation
    m = np.eye(4)
    m[:3, :3] = (
        np.array(
            [
                [r.m_11, r.m_12, r.m_13],
                [r.m_21, r.m_22, r.m_23],
                [r.m_31, r.m_32, r.m_33],
            ]
        ).T
        * block.scale
    )
    m[:3, 3] = (block.translation.x, block.translation.y, block.translation.z)
    return m


def bone_matrices(shape) -> dict:
    """`Aᵢ` per bone name: skin space into that bone's space."""
    skin = getattr(shape, "skin_instance", None)
    if skin is None or skin.data is None:
        return {}

    globally = matrix(skin.data.skin_transform)
    return {
        str(skin.bones[i].name): globally @ matrix(skin.data.bone_list[i].skin_transform)
        for i in range(skin.num_bones)
    }


def weights(shape, count: int) -> dict:
    """`wᵢ` per bone name, as arrays over the shape's vertices."""
    skin = getattr(shape, "skin_instance", None)
    if skin is None or skin.data is None:
        return {}

    out = {}
    for i in range(skin.num_bones):
        column = np.zeros(count, dtype=np.float64)
        for entry in skin.data.bone_list[i].vertex_weights:
            if 0 <= entry.index < count:
                column[entry.index] = entry.weight
        out[str(skin.bones[i].name)] = column
    return out


def to_rest_pose(vertices: np.ndarray, shape, rest: dict) -> np.ndarray | None:
    """Move a shape out of its own bind pose and into the armature's.

    `rest` maps a bone name to its 4x4 rest matrix in the armature. Bones the
    armature does not have are dropped and the remaining weights renormalised,
    so a shape bound to a bone that was never built still arrives whole.
    """
    into_bone = bone_matrices(shape)
    if not into_bone:
        return None

    count = len(vertices)
    per_bone = weights(shape, count)
    total = np.zeros((count, 4, 4), dtype=np.float64)
    mass = np.zeros(count, dtype=np.float64)

    for name, weight in per_bone.items():
        target = rest.get(name)
        if target is None:
            continue
        touched = weight > 0.0
        if not touched.any():
            continue
        combined = np.asarray(target) @ into_bone[name]
        total[touched] += weight[touched, None, None] * combined
        mass[touched] += weight[touched]

    bound = mass > 1e-6
    if not bound.any():
        return None

    total[bound] /= mass[bound, None, None]
    total[~bound] = np.eye(4)

    homogeneous = np.concatenate(
        [vertices, np.ones((count, 1), dtype=np.float64)], axis=1
    )
    moved = np.einsum("nij,nj->ni", total, homogeneous)
    return moved[:, :3]


def bind_poses(shapes) -> dict:
    """Where each bone rests, taken from the skin rather than the skeleton.

    `Aᵢ` takes a vertex into bone `i`'s space, so its inverse is where that
    bone stands when the shape is in its bind pose. That is the pose the
    weights were painted against, and therefore the only rest pose at which the
    geometry is undeformed.

    A character's skeleton file can disagree with it -- by 7 units for a
    Froblin, by 800 for a FroblinBoss -- and the skeleton is the one that is
    wrong, because nothing was ever skinned to it.

    The first shape to mention a bone defines it; later shapes are moved onto
    that pose by `to_rest_pose`.
    """
    out = {}
    for shape in shapes:
        for name, into_bone in bone_matrices(shape).items():
            if name not in out:
                out[name] = np.linalg.inv(into_bone)
    return out


#: Two bind poses count as the same rig if no shared bone is further apart
#: than this, in game units. Shapes inside one file agree to about 2.5.
SAME_POSE = 5.0


def same_pose(a: dict, b: dict, tolerance: float = SAME_POSE) -> bool:
    """Were these two shapes skinned against the same skeleton pose?

    An empty bind matches anything: a shape with no skin has no opinion.
    """
    if not a or not b:
        return True
    shared = set(a) & set(b)
    if not shared:
        return True
    return all(
        float(np.abs(a[name] - b[name]).max()) <= tolerance for name in shared
    )
