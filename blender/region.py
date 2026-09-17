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

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

from ..divinity2 import region as dv2_region
from ..divinity2 import vegetation as dv2_vegetation

from . import material as dv2_material
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

#: A sun's `dimmer` is a 0..1 multiplier too, and Blender's sun is an
#: irradiance in W/m^2. Blender's own default for daylight is 1.0 and the
#: game's rock is dark, so the sun is given this many watts per unit of
#: dimmer. A convenience, like `WATTS`; `dv2_dimmer` keeps the real value.
SUN_WATTS = 4.0

#: How much of the sun's authored `ambient_color` becomes Blender's world.
#: The game applies ambient per material, Blender applies it as an
#: environment, so the two cannot be equal. This is the fraction that does
#: not wash the scene out.
AMBIENT = 0.12


#: Ask for every sub-region, not just one.
ALL = "*"


@dataclass
class Built:
    """What arrived, so a caller can check rather than trust."""

    counts: dict = field(default_factory=dict)
    models: int = 0          #: distinct models imported
    failed: list = field(default_factory=list)
    unresolved: int = 0


def _named(name: str, made: list | None = None):
    found = bpy.data.collections.get(name)
    if found is None:
        found = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(found)
    if made is not None and found not in made:
        made.append(found)
    return found


def _matrix(placed) -> Matrix:
    """The placement's world matrix: basis rows as the engine reads them."""
    basis = Matrix.Identity(4)
    if placed.basis is not None:
        basis = Matrix([list(row) for row in placed.basis]).to_4x4()
    basis.translation = Vector(placed.position)
    return basis @ Matrix.Scale(placed.scale, 4)


#: The kinds the engine loads as static assets, which `SetupStandardData` runs
#: on (with the region's own nodes and the terrain). Scenery as a static asset
#: is read off the loader's name (`CStaticAssetDataManager`), not traced.
STANDARD_DATA_KINDS = ("terrain", "scenery")


def _import_into(path, game_root, cache, into, **options) -> list:
    """Import one model and move everything it made into `into` alone.

    Each object keeps what the importer decided -- a culled or coarse shape is
    already hidden -- as `dv2_drawn`, read before the move, since `into` may be
    a hidden collection. `_copy` draws a copy by it.
    """
    was = set(bpy.data.objects)
    import_asset(path, game_root, cache=cache, with_animation=False, **options)
    made = [o for o in bpy.data.objects if o not in was]
    for obj in made:
        obj["dv2_drawn"] = obj.visible_get() and not obj.hide_render
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        into.objects.link(obj)
    return made


def _library(path, game_root, cache, into, kind=""):
    """Import one model once and hide it; every placement is a copy of this."""
    made = _import_into(path, game_root, cache, into, standard_data=kind in STANDARD_DATA_KINDS)
    for obj in made:
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
    # The whole record in one property, as `dv2_material` is: a Blender property name
    # holds at most 63 characters (`MAX_IDPROP_NAME - 1`, bl_operators/wm.py), and a trigger's
    # `Trigger.Trigger_area.PolyArea.Points.AreaPoint[10].NiPoint3.x` is longer.
    obj["dv2_fields"] = json.dumps(placed.fields)


def _light(placed, into):
    """A point light, a spot or the sun, as `divinity2.region` read it."""
    shape = placed.fields.get("shape", "point")
    data = bpy.data.lights.new(placed.name or shape,
                               {"sun": "SUN", "spot": "SPOT"}.get(shape, "POINT"))
    data.color = placed.fields.get("colour", (1.0, 1.0, 1.0))
    dimmer = float(placed.fields.get("dimmer", 1.0))
    obj = bpy.data.objects.new(placed.name or shape, data)
    into.objects.link(obj)

    if shape in ("sun", "spot"):
        # The light travels along `direction`, its basis' column 0
        # (`NiDirectionalLight` / `NiSpotLight::UpdateWorldData`); a Blender
        # sun or spot shines along its own -Z.
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = Vector(placed.fields["direction"]).to_track_quat("-Z", "Y")
    if shape == "sun":
        data.energy = dimmer * SUN_WATTS
    else:
        radius = float(placed.fields.get("radius", 1.0))
        data.energy = dimmer * WATTS
        data.use_custom_distance = True
        data.cutoff_distance = radius
        data.shadow_soft_size = max(float(placed.fields.get("inner", 0.0)), 0.01)
        obj.location = placed.position
        if shape == "spot":
            data.spot_size = math.radians(float(placed.fields.get("fov", 45.0)))
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


def _world(placed):
    """The sky, from the sun's own `ambient_color`.

    Without one a region renders almost black: the game lights every surface
    with an ambient term and Blender has no ambient unless a world provides
    it.
    """
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("Divinity II")
        bpy.context.scene.world = world
    background = world.node_tree.nodes.get("Background")
    if background is None:
        return world
    ambient = placed.fields.get("ambient", (0.0, 0.0, 0.0))
    background.inputs[0].default_value = tuple(ambient) + (1.0,)
    background.inputs[1].default_value = AMBIENT * float(placed.fields.get("dimmer", 1.0))
    world["dv2_ambient"] = ambient
    return world


def _engine_globals(game_root, name: str, sub: str, time: str, statics) -> None:
    """The engine's shader globals for this sub-region's time setting, on the
    scene as `dv2_<name>`, where the materials read them (`material.GLOBALS`).
    The global atmosphere collection only: Blender has no camera to weigh the
    local volumes by (`divinity2.environment.frame`)."""
    from ..divinity2 import environment as dv2_environment
    from ..divinity2 import terrain as dv2_terrain

    scene = bpy.context.scene
    for key, value in dv2_material.GLOBALS.items():
        scene[f"dv2_{key}"] = value
    lit = dv2_environment.frame(dv2_environment.read(game_root, name, sub, time))
    scene["dv2_fGlobalNormalScale"] = lit["globals"]["fGlobalNormalScale"]
    scene["dv2_fGlobalLightmapIntensity"] = lit["settings"]["DarkMapBrightness"]
    if statics is not None:
        splat = dv2_terrain.splat(statics)
        scene["dv2_g_TerrainSplatRadius"] = splat["radius"]
        scene["dv2_g_TerrainSplatBlendRadius"] = splat["blend"]
    # The materials decode to linear once and expect it back unchanged.
    scene.view_settings.view_transform = "Standard"


def _one(game_root, name: str, sub: str, time: str, kinds, cache,
         built: Built, library: dict) -> list:
    """Build one sub-region into its own collections. Returns them."""
    read = dv2_region.read(game_root, name, sub, time)
    made = []
    templates = None
    _engine_globals(game_root, name, sub, time, read.statics)

    def _collection(label):
        return _named(f"{name} {sub} {label}", made)

    def count(kind):
        built.counts[kind] = built.counts.get(kind, 0) + 1

    if "terrain" in kinds and read.statics is not None:
        for _ in _import_into(read.statics, game_root, cache, _collection("terrain"), standard_data=True):
            count("terrain")

    for kind in ("scenery", "item", "character"):
        if kind not in kinds:
            continue
        want = read.of(kind)
        if not want:
            continue
        into = _collection(kind)
        if templates is None:
            templates = _collection("models")
            templates.hide_viewport = templates.hide_render = True
        for placed in want:
            if placed.model is None:
                built.unresolved += 1
                continue
            key = str(placed.model)
            if key not in library:
                try:
                    library[key] = _library(placed.model, game_root, cache, templates, kind)
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
        into = _collection(kind)
        for placed in want:
            make(placed, into)
            if placed.fields.get("shape") == "sun":
                _world(placed)
            count(kind)

    if "vegetation" in kinds and read.vegetation is not None:
        _vegetation(game_root, name, sub, read, _collection, cache, count)

    return made


def _vegetation(game_root, name, sub, read, _collection, cache, count):
    """Scatter the grass the way the engine scatters it.

    The library comes in once, hidden, and every blade is a linked copy of one
    of its meshes -- the same shape as the rest of the region, where one model
    is imported once and placed many times. Where each blade stands comes from
    `divinity2.vegetation`, which runs the engine's own generator; see
    `docs/vegetation.md`.
    """
    library = _collection("vegetation library")
    made = _import_into(read.vegetation, game_root, cache, library)
    library.hide_viewport = True

    # `dv2_path`'s second element is the `sNifFile` the plant table names.
    meshes = {}
    for obj in made:
        parts = str(obj.get("dv2_path", "")).split("/")
        if len(parts) > 1:
            meshes.setdefault(parts[1], []).append(obj)
    if not meshes:
        return

    recipe = dv2_vegetation.read(game_root, name, sub)
    into = _collection("vegetation")
    for plant in dv2_vegetation.scatter(recipe):
        source = meshes.get(recipe.plants[plant.plant].model)
        if not source:
            continue
        where = (Matrix.Translation((plant.x, plant.y, plant.z))
                 @ Matrix.Rotation(plant.rotation * 2.0 * math.pi, 4, "Z")
                 @ Matrix.Scale(plant.size, 4))
        for root in _copy(source, where, into, plant.plant):
            root["dv2_kind"] = "vegetation"
            root["dv2_plant"] = plant.plant
            root["dv2_colour"] = plant.colour
        count("vegetation")


def import_region(game_root, name: str, sub: str = "Main", time: str = "",
                  kinds=KINDS, cache=None) -> Built:
    """Build one region, or -- with `sub=ALL` -- all of its sub-regions.

    **Each sub-region has its own origin.** Banditcamp's cave spans x -155..17
    while its surface spans -85..185; Broken Valley's Chapel and Farm both sit
    within ten metres of zero. The engine loads one at a time and joins them
    with teleport triggers, so they are separate scenes that happen to share a
    coordinate system by accident, not by design.

    Building them all therefore stacks them. Nothing is moved to hide that --
    an offset would be geometry the game does not have -- so every sub-region
    gets its own collections and all but the first arrive switched off.
    """
    game_root = Path(game_root)
    built = Built()
    library = {}
    subs = dv2_region.subregions(game_root, name) if sub == ALL else [sub]

    for index, one in enumerate(subs):
        made = _one(game_root, name, one, time, kinds, cache, built, library)
        if index and made:
            layer = bpy.context.view_layer.layer_collection
            for collection in made:
                found = layer.children.get(collection.name)
                if found is not None:
                    found.exclude = True
    built.counts["sub-regions"] = len(subs)
    return built
