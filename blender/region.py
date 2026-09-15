"""Building a whole region in Blender.

One import per distinct model, then a linked copy per placement -- 775 barrels
and boulders in Banditcamp come from 105 meshes. Each kind lands in its own
collection, so a modder can switch off the triggers and keep the props.

What has no mesh still arrives, because where it stands is the knowledge:
a light becomes a Blender light, a trigger area becomes the prism it is, and a
tree becomes an empty the size the engine gives it. Everything the file said
is written onto the object as a `dv2_` property, so nothing is lost on the way
in.
"""

from dataclasses import dataclass, field
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

from ..divinity2 import region as dv2_region

from .importer import import_asset

#: One collection per kind, in the order they are built.
KINDS = ("terrain", "scenery", "item", "character", "tree", "light",
         "trigger", "vegetation")

#: A point light's dimmer is a 0..1 multiplier, not a wattage. Blender wants
#: watts, and a 40 W bulb at the radius these lights use looks like the game's.
#: This is a convenience, not a measurement -- the authored values are kept on
#: the object as `dv2_dimmer` and `dv2_radius`.
WATTS = 40.0

#: How big an empty stands in for a point, in metres.
MARKER = 0.25


@dataclass
class Built:
    """What arrived, so a caller can check rather than trust."""

    counts: dict = field(default_factory=dict)
    models: int = 0          #: distinct models imported
    failed: list = field(default_factory=list)
    unresolved: int = 0


def _collection(name: str):
    found = bpy.data.collections.get(name)
    if found is None:
        found = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(found)
    return found


def _matrix(placed) -> Matrix:
    """The placement's world matrix: basis rows as the engine reads them."""
    basis = Matrix.Identity(4)
    if placed.basis is not None:
        basis = Matrix([list(row) for row in placed.basis]).to_4x4()
    basis.translation = Vector(placed.position)
    return basis @ Matrix.Scale(placed.scale, 4)


def _library(path, game_root, cache, into):
    """Import one model once and hide it; every placement is a copy of this."""
    was = set(bpy.data.objects)
    import_asset(path, game_root, cache=cache, with_animation=False)
    made = [o for o in bpy.data.objects if o not in was]
    for obj in made:
        # Remember what the importer decided -- a culled or coarse shape is
        # already hidden -- before hiding the template itself.
        obj["dv2_drawn"] = obj.visible_get() and not obj.hide_render
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        into.objects.link(obj)
        obj.hide_set(True)
        obj.hide_render = True
    return made


def _copy(source, where: Matrix, into, name: str):
    """A linked copy of a whole imported model, parents and all."""
    copies = {}
    for obj in source:
        made = obj.copy()
        into.objects.link(made)
        drawn = bool(obj.get("dv2_drawn", True))
        made.hide_set(not drawn)
        made.hide_render = not drawn
        copies[obj.name] = made
    for obj in source:
        if obj.parent is not None and obj.parent.name in copies:
            copies[obj.name].parent = copies[obj.parent.name]
    roots = []
    for obj in source:
        if obj.parent is None:
            copies[obj.name].matrix_world = where @ obj.matrix_world
            roots.append(copies[obj.name])
    for root in roots:
        root.name = name
    return roots


def _describe(obj, placed):
    obj["dv2_kind"] = placed.kind
    obj["dv2_uuid"] = placed.uuid
    for key, value in placed.fields.items():
        obj[f"dv2_{key}"] = value


def _light(placed, into):
    """A point light or the sun, as `divinity2.region` read it."""
    shape = placed.fields.get("shape", "point")
    data = bpy.data.lights.new(placed.name or shape,
                               "SUN" if shape == "sun" else "POINT")
    data.color = placed.fields.get("colour", (1.0, 1.0, 1.0))
    dimmer = float(placed.fields.get("dimmer", 1.0))
    obj = bpy.data.objects.new(placed.name or shape, data)
    into.objects.link(obj)

    if shape == "sun":
        data.energy = dimmer
        basis = dv2_region.sun_basis(placed.fields.get("angle_y", 0.0),
                                     placed.fields.get("angle_z", 0.0))
        # The light travels along the basis' -X; a Blender sun shines along
        # its own -Z. Point -Z there and let Blender pick the rest.
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = Vector(
            (-basis[0][0], -basis[1][0], -basis[2][0])
        ).to_track_quat("-Z", "Y")
    else:
        radius = float(placed.fields.get("radius", 1.0))
        data.energy = dimmer * WATTS
        data.use_custom_distance = True
        data.cutoff_distance = radius
        data.shadow_soft_size = max(float(placed.fields.get("inner", 0.0)), 0.01)
        obj.location = placed.position
    _describe(obj, placed)
    return obj


def _trigger(placed, into):
    """An area trigger as the prism it is, a point trigger as an empty."""
    if placed.polygon and placed.height:
        bottom, top = placed.height
        ring = [Vector((p[0], p[1], bottom)) for p in placed.polygon]
        mesh = bpy.data.meshes.new(placed.name or "trigger")
        verts = ring + [Vector((v.x, v.y, top)) for v in ring]
        n = len(ring)
        faces = [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
        faces += [list(range(n))[::-1], list(range(n, 2 * n))]
        mesh.from_pydata([tuple(v) for v in verts], [], faces)
        mesh.update()
        obj = bpy.data.objects.new(placed.name or "trigger", mesh)
        obj.display_type = "WIRE"
    else:
        obj = bpy.data.objects.new(placed.name or "trigger", None)
        obj.empty_display_type = "SPHERE"
        obj.empty_display_size = MARKER
        obj.matrix_world = _matrix(placed)
    into.objects.link(obj)
    obj.hide_render = True
    _describe(obj, placed)
    return obj


def _tree(placed, into):
    """A marker where a SpeedTree grows, at the size the engine gives it."""
    obj = bpy.data.objects.new(placed.name or "tree", None)
    obj.empty_display_type = "CONE"
    obj.empty_display_size = max(placed.scale, 0.1)
    obj.location = placed.position
    into.objects.link(obj)
    obj.hide_render = True
    _describe(obj, placed)
    return obj


def import_region(game_root, name: str, sub: str = "Main", time: str = "Day",
                  kinds=KINDS, cache=None) -> Built:
    """Build one region, or the parts of it `kinds` asks for."""
    game_root = Path(game_root)
    read = dv2_region.read(game_root, name, sub, time)
    built = Built()
    library = {}
    templates = None

    def count(kind):
        built.counts[kind] = built.counts.get(kind, 0) + 1

    if "terrain" in kinds and read.statics is not None:
        into = _collection(f"{name} terrain")
        was = set(bpy.data.objects)
        import_asset(read.statics, game_root, cache=cache, with_animation=False)
        for obj in [o for o in bpy.data.objects if o not in was]:
            for collection in list(obj.users_collection):
                collection.objects.unlink(obj)
            into.objects.link(obj)
            count("terrain")

    for kind in ("scenery", "item", "character"):
        if kind not in kinds:
            continue
        want = read.of(kind)
        if not want:
            continue
        into = _collection(f"{name} {kind}")
        if templates is None:
            templates = _collection(f"{name} models")
            templates.hide_viewport = templates.hide_render = True
        for placed in want:
            if placed.model is None:
                built.unresolved += 1
                continue
            key = str(placed.model)
            if key not in library:
                try:
                    library[key] = _library(placed.model, game_root, cache, templates)
                    built.models += 1
                except Exception as exc:                       # noqa: BLE001
                    library[key] = []
                    built.failed.append(f"{placed.model.name}: {exc}")
            source = library[key]
            if not source:
                continue
            for root in _copy(source, _matrix(placed), into, placed.name):
                _describe(root, placed)
            count(kind)

    for kind, make in (("light", _light), ("trigger", _trigger), ("tree", _tree)):
        if kind not in kinds:
            continue
        want = read.of(kind)
        if not want:
            continue
        into = _collection(f"{name} {kind}")
        for placed in want:
            make(placed, into)
            count(kind)

    if "vegetation" in kinds and read.vegetation is not None:
        into = _collection(f"{name} vegetation")
        was = set(bpy.data.objects)
        import_asset(read.vegetation, game_root, cache=cache, with_animation=False)
        for obj in [o for o in bpy.data.objects if o not in was]:
            for collection in list(obj.users_collection):
                collection.objects.unlink(obj)
            into.objects.link(obj)
            count("vegetation")
        into.hide_viewport = True

    return built
