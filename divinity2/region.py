"""A whole region: what stands in it, who walks it, and what lights it.

A region is a folder under `World/`, and what it holds is spread over three
places. The ground and the built geometry are NIFs beside it; the props, the
lights and the trees are binary XML beside those; the characters, the items
and the triggers live with the episode, not with the region, and name their
region in an attribute.

| what | file | what names its model |
|---|---|---|
| scenery | `World/<r>/<sub>/scenery.xml` | `rpgstats_sceneryprototypes.xml` |
| characters | `Episodes/<e>/Regions/<r>/Characters/*.xml` | `rpgstats_characterprototypes_visual.xml` |
| items | `Episodes/<e>/Regions/<r>/Items/*.xml` | `rpgstats_itemprototypes.xml` -> `..._itemvisualprototypes.xml` |
| triggers | `Episodes/<e>/Triggers/*.xml` | nothing: a trigger is a volume |
| lights | `World/<r>/<sub>/Lights/<time>/lights.xml` | nothing |
| trees | `World/<r>/<sub>/trees.xml` | `forest-settings.xml`, and see below |
| vegetation | `World/<r>/<sub>/Vegetation.nif` | itself |

**Every placement is stored the same way**: an `NiPoint3` child for the
position and an `NiMatrix3` child for the basis, in that order, and both in
metres. The engine's own readers say so --
`CRpgStats_V2_Scenery::LoadXML`, `CRpgStats_V2_Character::LoadXML`,
`CRpgStats_V2_Item::LoadXML` and `CGameLogic_Tree::LoadXML` all take
`children[0]` as the position and `children[1]` as the orientation. The
binary stream stores children in reverse, and `divinity2.binxml` undoes that
once, for everything; see its note.

**A trigger is a prism or a point.** `Trigger_area` holds a `PolyArea` with
`Top` and `Bottom` and a ring of `AreaPoint`s at the bottom height, so the
volume is that polygon extruded upward. `Trigger_Point`, `Trigger_Orientation`
and their named cousins hold a single position, with a basis when the thing
has a facing. The `Type` number is not decoded here: the child element is its
own label and needs no table.

**A tree has no mesh.** `model="BoxWood"` names a `CTreeModel` in
`forest-settings.xml`, whose `model` is a SpeedTree `.spt` -- a procedural
definition, not geometry. The whole SpeedTree runtime is linked into the game
(`CSpeedTreeRT::LoadTree`, `CTreeModel::SetupBranchGeometry`) and grows the
tree at load. So a tree arrives as a marker with its name, its position and
its size, and the size is exact:
`CGameLogic_Tree::PreparePhysicsData` computes it as
`rescaled.y * CTreeModel.size`, where `CGameLogic_Tree::UpdateInstanceData`
sets `rescaled.y = (1 - v) + instance.y * v * 2` for `v = treesizevariation`.
`instance.x` is the tree's rotation and `instance.z` its colour variation,
both fed to the SpeedTree shader; neither is converted here.

**Vegetation is scattered by the engine, not stored.** `Vegetation.nif` is the
region's library of grass and undergrowth meshes, one `NiNode` per source
file, and `vegetationtemplatedata.xml` names them again with their textures.
Where each blade stands is generated at load from a seed and a per-cell mask
(`Vegetation/VM_<x>_<y>.tga`, the names
`CVegetationGridManager::GenerateVegetationGridEntryDescriptors` scans for).
That generator is not reproduced here, so the library comes in unplaced.
"""

import struct
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import binxml

#: Where the placement files live, relative to the install.
WORLD = Path("World")
EPISODES = Path("Episodes")

#: The scenery prototype table, beside the install root, and the element in
#: it that names a model. The placement calls the thing `Scenery`; the
#: prototype that describes it is a `sceneryitem`.
SCENERY_PROTOTYPES = "rpgstats_sceneryprototypes.xml"
SCENERY_ITEM = "sceneryitem"

#: `Assets\...` in a prototype path *replaces* onto this folder, it does not
#: nest under it.
SCENERY_ROOT = Path("Win32") / "Scenery"
ITEM_ROOT = Path("Win32") / "Items"
CHARACTER_ROOT = Path("Win32") / "Characters" / "Templates"

#: The lights are authored three times, one folder per time of day.
TIMES = ("Day", "Dawn", "Dusk")

#: The one node that carries a trigger's polygon.
AREA = "PolyArea"


@dataclass
class Placed:
    """One thing standing in a region."""

    kind: str                       #: scenery, character, item, trigger, light, tree
    uuid: str                       #: the name the file gives it
    name: str                       #: what to call it in the scene
    position: tuple                 #: metres, region space
    basis: np.ndarray | None = None  #: 3x3 rotation, rows as the engine reads them
    scale: float = 1.0
    model: Path | None = None       #: the file holding its mesh, when it has one
    fields: dict = field(default_factory=dict)  #: everything else the file said
    polygon: list = field(default_factory=list)  #: a trigger's ring, in metres
    height: tuple | None = None     #: a trigger prism's (bottom, top)


@dataclass
class Region:
    name: str
    sub: str
    placed: list = field(default_factory=list)
    statics: Path | None = None      #: `StaticMeshes.nif`, the built geometry
    vegetation: Path | None = None   #: `Vegetation.nif`, the library
    missing: dict = field(default_factory=dict)  #: kind -> how many found no model

    def of(self, kind: str) -> list:
        return [p for p in self.placed if p.kind == kind]


# ---------------------------------------------------------------- the basics

def _point(node) -> tuple:
    return tuple(float(node.get(k, 0.0)) for k in "xyz")


def _basis(node) -> np.ndarray:
    return np.array([_point(row) for row in node.children], dtype=float)


def _placement(node):
    """(position, basis) from the two children every placement carries."""
    position, basis = (0.0, 0.0, 0.0), None
    for child in node.children:
        if child.is_a("NiPoint3") and position == (0.0, 0.0, 0.0):
            position = _point(child)
        elif child.is_a("NiMatrix3"):
            basis = _basis(child)
    return position, basis


def _folder(root, region: str, sub: str) -> Path:
    here = Path(root) / WORLD / region
    return here / sub if sub == "Main" else here / "Subregions" / sub


def _read(path: Path):
    try:
        return binxml.read(path.read_bytes())
    except (binxml.Malformed, OSError, IndexError, ValueError, struct.error):
        return None


@lru_cache(maxsize=4)
def _files(root: Path, under: str, suffix: str) -> dict:
    """Every file of one kind, keyed by its lower-cased relative path.

    Larian's own tables disagree with the disk about case, and a Linux
    filesystem does not forgive that.
    """
    base = Path(root) / under
    if not base.is_dir():
        return {}
    return {
        str(p.relative_to(base).with_suffix("")).lower().replace("\\", "/"): p
        for p in base.rglob(f"*{suffix}")
    }


# ------------------------------------------------------------- model lookups

@lru_cache(maxsize=4)
def _scenery_models(root: Path) -> dict:
    """Scenery prototype UUID -> the `.item` on disk."""
    doc = _read(Path(root) / SCENERY_PROTOTYPES)
    if doc is None:
        return {}
    files = _files(Path(root), str(SCENERY_ROOT), ".item")
    out = {}
    for node in doc.find_all(SCENERY_ITEM):
        uuid, named = node.get("UUID"), node.get("NIFFile")
        if not uuid or not named:
            continue
        parts = named.replace("\\", "/").split("/")
        if parts and parts[0].lower() == "assets":
            parts = parts[1:]
        found = files.get("/".join(parts).lower())
        if found:
            out[uuid] = found
    return out


@lru_cache(maxsize=4)
def _character_models(root: Path) -> dict:
    """Visual prototype UUID -> the `.cat` on disk.

    A `Visual` gives `PrototypeName` -- the family, `SkeletonHuman` -- and
    `TemplateName`, which is the template inside it. The template is also the
    name of a file under `Characters/Templates`, for 300 of the game's 302
    visuals; the two that are not are unused Froblin variants.
    """
    root = Path(root)
    files = _files(root, str(CHARACTER_ROOT), ".cat")
    out = {}
    for table in sorted((root / EPISODES).glob("*/rpgstats_characterprototypes_visual.xml")):
        doc = _read(table)
        if doc is None:
            continue
        for node in doc.find_all("Visual"):
            uuid = node.get("UUID")
            template = next((c.text for c in node.children if c.is_a("TemplateName")), "")
            found = files.get(template.lower())
            if uuid and found:
                out.setdefault(uuid, found)
    return out


@lru_cache(maxsize=4)
def _item_models(root: Path) -> dict:
    """Item prototype UUID -> the `.item` on disk.

    Two hops: an `item` names a `VisualUUID`, and that `itemvisual` names a
    `Folder` and a `NifFileName` under `Items`. 1,141 of 1,177 resolve; the
    rest are cutscene props the game does not ship.
    """
    root = Path(root)
    files = _files(root, str(ITEM_ROOT), ".item")
    visuals = {}
    for table in sorted((root / EPISODES).glob("*/rpgstats_itemvisualprototypes.xml")):
        doc = _read(table)
        if doc is None:
            continue
        for node in doc.find_all("itemvisual"):
            key = f"{node.get('Folder', '')}/{node.get('NifFileName', '')}"
            found = files.get(key.replace("\\", "/").lower())
            if node.get("UUID") and found:
                visuals.setdefault(node.get("UUID"), found)

    out = {}
    for table in sorted((root / EPISODES).glob("*/rpgstats_itemprototypes.xml")):
        doc = _read(table)
        if doc is None:
            continue
        for node in doc.find_all("item"):
            found = visuals.get(node.get("VisualUUID", ""))
            if node.get("UUID") and found:
                out.setdefault(node.get("UUID"), found)
    return out


# ------------------------------------------------------------- the placements

def _scenery(root: Path, region: str, sub: str) -> list:
    doc = _read(_folder(root, region, sub) / "scenery.xml")
    if doc is None:
        return []
    models = _scenery_models(Path(root))
    out = []
    for node in doc.find_all("Scenery"):
        position, basis = _placement(node)
        proto = node.get("PrototypeUUID", "")
        out.append(Placed(
            kind="scenery",
            uuid=node.get("UUID", proto),
            name=proto or node.get("UUID", "scenery"),
            position=position,
            basis=basis,
            scale=float(node.get("Scale", 1.0) or 1.0),
            model=models.get(proto),
            fields=dict(prototype=proto),
        ))
    return out


def _from_episodes(root: Path, region: str, sub: str, where: str, element: str,
                   kind: str, models: dict, model_key: str) -> list:
    """Characters and items: same shape, different table."""
    out = []
    for table in sorted((Path(root) / EPISODES).glob(f"*/Regions/{region}/{where}/*.xml")):
        doc = _read(table)
        if doc is None:
            continue
        for node in doc.find_all(element):
            # An `Item` without a position is not placed in the world -- it is
            # what something else is carrying, and the same files hold both.
            if node.get("RegionName") != region or node.get("SubRegionName") != sub:
                continue
            if not any(c.is_a("NiPoint3") for c in node.children):
                continue
            position, basis = _placement(node)
            key = node.get(model_key, "")
            out.append(Placed(
                kind=kind,
                uuid=node.get("UUID", ""),
                name=node.get("UUID") or key or kind,
                position=position,
                basis=basis,
                model=models.get(key),
                fields={k: node.get(k, "") for k in
                        ("PrototypeUUID", "VisualPrototypeUUID", "Script",
                         "Dialog", "Name", "ItemName", "IsLocked", "teamID")
                        if node.get(k) is not None},
            ))
    return out


def _triggers(root: Path, region: str, sub: str) -> list:
    out = []
    for table in sorted((Path(root) / EPISODES).glob("*/Triggers/*.xml")):
        doc = _read(table)
        if doc is None:
            continue
        for node in doc.find_all("Trigger"):
            kind_number = node.get("Type")
            if kind_number is None or not node.children:
                continue
            inner = node.children[0]
            base = next((c for c in inner.children if c.is_a("Trigger_base")), None)
            if base is None:
                continue
            if base.get("Region") != region or base.get("SubRegion", sub) != sub:
                continue

            shape = next((c for c in inner.children
                          if not c.is_a("Trigger_base")), None)
            placed = Placed(
                kind="trigger",
                uuid=node.get("UUID", ""),
                name=node.get("UUID", "trigger"),
                position=(0.0, 0.0, 0.0),
                fields=dict(type=kind_number,
                            shape=_label(shape) if shape is not None else "",
                            active=base.get("Active", "1")),
            )
            if shape is not None:
                area = next(shape.find_all(AREA), None)
                if area is not None:
                    ring = [_point(p) for point in area.find_all("AreaPoint")
                            for p in point.children if p.is_a("NiPoint3")]
                    placed.polygon = ring
                    placed.height = (float(area.get("Bottom", 0.0)),
                                     float(area.get("Top", 0.0)))
                    if ring:
                        placed.position = tuple(
                            sum(p[k] for p in ring) / len(ring) for k in range(3))
                else:
                    placed.position, placed.basis = _placement(shape)
            out.append(placed)
    return out


def _label(node) -> str:
    """A trigger's shape element, named by what it is rather than by number."""
    for name in ("Trigger_area", "Trigger_Point", "Trigger_Orientation",
                 "Trigger_PointSound", "Trigger_PointEncounter",
                 "Trigger_PlayerSpawnPoint"):
        if node.is_a(name):
            return name[len("Trigger_"):]
    return "other"


def _lights(root: Path, region: str, sub: str, time: str = "Day") -> list:
    doc = _read(_folder(root, region, sub) / "Lights" / time / "lights.xml")
    if doc is None:
        return []
    out = []
    for node in doc.find_all("point_light"):
        out.append(_light(node, "point"))
    for node in doc.find_all("dir_light"):
        out.append(_light(node, "sun"))
    return out


def _light(node, shape: str) -> Placed:
    """One light, with the colour and dimmer its `GBLight` carries.

    A point light's position is the `translate` under its `GBLight`; a
    directional light has none, only two angles. The engine builds its basis
    as `MakeZRotation(angle_z) * MakeYRotation(angle_y)`
    (`CDirLight::UpdateVisual`) and the light travels along that basis' **-X**
    -- measured, not assumed: of the nine regions that ship a `Day` set, -X
    points below the horizon for all nine and every other axis for fewer.
    """
    gb = next(node.find_all("GBLight"), None)
    position = (0.0, 0.0, 0.0)
    colour = (1.0, 1.0, 1.0)
    ambient = (0.0, 0.0, 0.0)
    dimmer = 1.0
    if gb is not None:
        dimmer = float(gb.get("dimmer", 1.0) or 1.0)
        for child in gb.children:
            if child.is_a("translate"):
                position = _point(child)
            elif child.is_a("diffuse_color"):
                colour = tuple(float(child.get(k, 1.0)) for k in "rgb")
            elif child.is_a("ambient_color"):
                ambient = tuple(float(child.get(k, 0.0)) for k in "rgb")

    fields = dict(shape=shape, dimmer=dimmer, colour=colour, ambient=ambient)
    if shape == "sun":
        fields["angle_y"] = float(node.get("angle_y", 0.0) or 0.0)
        fields["angle_z"] = float(node.get("angle_z", 0.0) or 0.0)
    else:
        fields["radius"] = float(node.get("m_fMaxAttenuationRadius", 1.0) or 1.0)
        fields["inner"] = float(node.get("m_fMinAttenuationRadius", 0.0) or 0.0)
    fields["shadows"] = (next(node.find_all("light"), node).get("m_bCastShadows", "0"))
    return Placed(kind="light", uuid=node.get("Name", ""),
                  name=node.get("Name", shape), position=position, fields=fields)


def sun_basis(angle_y: float, angle_z: float) -> np.ndarray:
    """`MakeZRotation(angle_z) * MakeYRotation(angle_y)`, as the engine builds it."""
    cy, sy = np.cos(angle_y), np.sin(angle_y)
    cz, sz = np.cos(angle_z), np.sin(angle_z)
    return np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]) @ \
        np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])


@lru_cache(maxsize=4)
def _tree_models(root: Path) -> dict:
    """`CTreeModel` name -> its size, variation and `.spt`, from `forest-settings.xml`."""
    doc = _read(Path(root) / "forest-settings.xml")
    if doc is None:
        return {}
    out = {}
    for node in doc.find_all("CTreeModel"):
        name = node.get("name")
        if name:
            out.setdefault(name, dict(
                spt=node.get("model", ""),
                size=float(node.get("size", 1.0) or 1.0),
                variation=float(node.get("treesizevariation", 0.0) or 0.0),
            ))
    return out


def _trees(root: Path, region: str, sub: str) -> list:
    doc = _read(_folder(root, region, sub) / "trees.xml")
    if doc is None:
        return []
    models = _tree_models(Path(root))
    out = []
    for node in doc.find_all("CGameLogic_Tree"):
        points = [c for c in node.children if c.is_a("NiPoint3")]
        if len(points) < 2:
            continue
        position, instance = _point(points[0]), _point(points[1])
        model = node.get("model", "")
        described = models.get(model, {})
        variation = described.get("variation", 0.0)
        rescaled = (1.0 - variation) + instance[1] * variation * 2.0
        out.append(Placed(
            kind="tree",
            uuid=node.get("uuid", ""),
            name=f"{model} {node.get('uuid', '')}".strip(),
            position=position,
            scale=rescaled * described.get("size", 1.0),
            fields=dict(model=model, spt=described.get("spt", ""),
                        variation_id=node.get("variation", "0"),
                        rotation=instance[0], colour=instance[2]),
        ))
    return out


# ------------------------------------------------------------------ the whole

def regions(root) -> list:
    """Every region folder the install ships."""
    base = Path(root) / WORLD
    return sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []


def subregions(root, region: str) -> list:
    """`Main` and whatever is under `Subregions`, in that order."""
    here = Path(root) / WORLD / region
    found = ["Main"] if (here / "Main").is_dir() else []
    under = here / "Subregions"
    if under.is_dir():
        found += sorted(p.name for p in under.iterdir() if p.is_dir())
    return found


def read(root, region: str, sub: str = "Main", time: str = "Day") -> Region:
    """Read one region into plain data. Knows nothing about Blender."""
    root = Path(root)
    here = _folder(root, region, sub)
    out = Region(name=region, sub=sub)

    out.placed += _scenery(root, region, sub)
    out.placed += _from_episodes(root, region, sub, "Characters", "Character",
                                 "character", _character_models(root),
                                 "VisualPrototypeUUID")
    out.placed += _from_episodes(root, region, sub, "Items", "Item",
                                 "item", _item_models(root), "PrototypeUUID")
    out.placed += _triggers(root, region, sub)
    out.placed += _lights(root, region, sub, time)
    out.placed += _trees(root, region, sub)

    statics = here / "StaticMeshes.nif"
    out.statics = statics if statics.is_file() else None
    plants = here / "Vegetation.nif"
    out.vegetation = plants if plants.is_file() else None

    for kind in ("scenery", "character", "item"):
        want = out.of(kind)
        out.missing[kind] = sum(1 for p in want if p.model is None)
    return out
