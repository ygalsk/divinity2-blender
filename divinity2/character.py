"""A Divinity II model file, of either shape the game ships.

There are exactly two. A `.cat` bundles a whole character: the skeleton, the
mesh files, the animation set and the clips, each as an `MdlMan::` entry that
keeps the path it had before it was bundled. Everything else -- scenery, item,
effect, flying fortress, compiled asset -- is a plain NIF with one
`CStreamableAssetData` block at its root.

Both arrive here as a `Character`, because the difference between them is what
is filled in, not what they are: an asset is a character with one mesh, no
family and usually no skeleton.

See `docs/cat.md` for the `.cat` block layout, `docs/assets.md` for the rest.
"""

import struct
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path, PureWindowsPath

from .nif import read_nif

#: The entry kinds a `.cat` root holds, by their block name without namespace.
SKELETON = "CSkeletonDataEntry"
MESH = "CMeshDataEntry"
ANIMATION = "CAnimationDataEntry"
ANIMATION_SET = "CAMDataEntry"

#: The extension that marks a bundled character rather than a plain asset.
CHARACTER_SUFFIX = ".cat"

ROOT_BLOCK = "MdlMan::CModelTemplateDataEntry"

#: The root block of every non-character model file. `CStreamableAssetData`
#: is read by the engine in `CStreamableAssetData::LoadBinary`: one link to
#: the `NiNode` root, a flag byte, and -- when the flag is set -- an embedded
#: KFM handed to `DivTools::CKFMToolStreamer::LoadBinaryStream`. So an asset
#: carries its animation set exactly the way a `.cat` does.
STREAMABLE = "CStreamableAssetData"


@dataclass
class Clip:
    """One named animation, as the game lists it: `Idle1`, `Move_F_Normal`."""

    name: str
    start: float
    stop: float
    sequence: object  # NiControllerSequence

    @property
    def duration(self) -> float:
        return self.stop - self.start


@dataclass
class Mesh:
    """One mesh file that was bundled into the character."""

    name: str
    root: object  # NiNode
    #: The part's `MdlMan::CMeshEntry` (`texture_base`, `extra_data`, `search`),
    #: None where the table has no entry; see `mesh_entry`.
    entry: dict | None = None


@dataclass
class Character:
    """Everything a `.cat` holds."""

    name: str
    path: Path
    skeleton: object = None  # NiNode, the skeleton's own scene root
    meshes: list[Mesh] = field(default_factory=list)
    clips: list[Clip] = field(default_factory=list)
    animation_set: bytes = b""  # a KFM without its header

    def clip(self, name: str) -> Clip | None:
        for c in self.clips:
            if c.name == name:
                return c
        return None


def _kind(block) -> str:
    return type(block).__name__.split("::")[-1]


def _sequences(nif) -> list[Clip]:
    """Every clip a NIF holds, in file order."""
    return [
        Clip(name=str(s.name), start=s.start_time, stop=s.stop_time, sequence=s)
        for s in nif.blocks
        if type(s).__name__ == "NiControllerSequence"
    ]


def read_model(path: str | Path) -> Character:
    """Read any model the game ships: a `.cat`, a plain asset, or a folder."""
    path = Path(path)
    if path.is_dir():
        return read_compiled(path)
    if path.suffix.lower() == CHARACTER_SUFFIX:
        return read_character(path)
    return read_asset(path)


def read_compiled(group: str | Path) -> Character:
    """One `LODGroup` folder of a compiled asset.

    `CompiledAssets/<name>/LODGroup<nn>/<n>.nif`. A `LODGroup` is one model --
    a statue's figure is one, its plinth another -- and the numbered files
    inside it are its levels of detail. **The highest number is the finest**:
    of the 295 groups holding more than one file, 164 grow with the number,
    none shrink, and 5 are identical.

    The groups of one folder are not pieces of one object. Each is authored
    around its own centre -- the figure spans z -458..458, the plinth
    -154..154 -- and the world data, not the asset, says where each stands.
    Importing them together would stack them at the origin.
    """
    group = Path(group)
    files = sorted(group.glob("*.nif"), key=lambda p: (len(p.stem), p.stem))
    if not files:
        raise ValueError(f"{group.name} holds no NIF")
    model = read_asset(files[-1])
    model.name = group.parent.name if _only_group(group) else (
        f"{group.parent.name} {group.name}"
    )
    model.path = group
    return model


def _only_group(group: Path) -> bool:
    return len(list(group.parent.glob("LODGroup*"))) == 1


def read_asset(path: str | Path) -> Character:
    """Read one plain asset: scenery, an item, an effect, a fortress.

    The whole model hangs off the streamable block's root, so there is one
    mesh entry and it is the file. A fortress is skinned and carries its own
    bones in that same tree -- there is no family skeleton to find for it, so
    the tree is the skeleton too.
    """
    path = Path(path)
    nif = read_nif(path)

    block = next((b for b in nif.blocks if type(b).__name__ == STREAMABLE), None)
    root = block.root if block is not None else None
    if root is None:
        root = next((b for b in nif.blocks if type(b).__name__ == "NiNode"), None)
    if root is None:
        raise ValueError(f"{path.name} holds no model")

    skinned = any(type(b).__name__ == "NiSkinInstance" for b in nif.blocks)
    return Character(
        name=path.stem,
        path=path,
        skeleton=root if skinned else None,
        meshes=[Mesh(name=path.stem, root=root)],
        clips=_sequences(nif),
        animation_set=(
            bytes(block.data) if block is not None and block.has_data else b""
        ),
    )


#: The table `CMdlManMapper::Initialize` @0x68a2e0 loads, beside the templates' folder.
MESH_ENTRIES = "MdlManBinary.nif"


@lru_cache(maxsize=4)
def model_manager(path: str | Path) -> dict:
    """What `MdlManBinary.nif` says about character parts.

    - `entries`: the `CMeshEntry` blocks by part name in lower case.
      `CMeshEntry::LoadBinary` @0x1092340: string name, string texture base,
      string extra data, u8 search extra textures, u32 name id, link property
      group. The engine re-binds a part's maps by the entry's texture base
      (`CMeshWrapper::SetupTexturingProperty` @0xc9de80;
      docs/sources.md, "Character part maps"). Measured: 828, no name twice.
    - `templates`: each `CModelTemplate`'s slot assignments, template name in
      lower case -> the entry names it assigns (u32 name, u32, u32 prototype,
      u32 properties, u32 count, then count pairs of sized strings, slot and
      entry; `dv2mod.core.nifpatch.read_model_template`, which round-trips).
    - `meshes`: each `CMesh` block's name in lower case -> the entries it links
      (u32 source file, u32 name, u8, u32 slot hash, u32 count, then count pairs
      of u32 hash and a block link; `nifpatch.read_mesh`). Measured: the links
      resolve to `CMeshEntry` blocks, and `Pig` links `Pig_Body_A`, the entry
      `Pig_A`'s template assigns, where the part's own file is `Pig.nif`.

    nifgen has no such blocks, so the header is walked as
    `dv2mod.core.nifpatch.parse_header` walks it. Empty when the file is not there.
    """
    path = Path(path)
    out = {"entries": {}, "templates": {}, "meshes": {}}
    if not path.is_file():
        return out
    data = path.read_bytes()
    u32 = lambda at: struct.unpack_from("<I", data, at)[0]   # noqa: E731
    at = data.index(b"\n") + 1 + 4 + 1 + 4                  # version, endian, user version
    blocks = u32(at); at += 4
    types = []
    count = struct.unpack_from("<H", data, at)[0]; at += 2
    for _ in range(count):
        n = u32(at); types.append(data[at + 4:at + 4 + n].decode("latin-1")); at += 4 + n
    kinds = struct.unpack_from(f"<{blocks}H", data, at); at += 2 * blocks
    sizes = struct.unpack_from(f"<{blocks}I", data, at); at += 4 * blocks
    strings = []
    count = u32(at); at += 8                                   # count, longest
    for _ in range(count):
        n = u32(at); strings.append(data[at + 4:at + 4 + n].decode("latin-1")); at += 4 + n
    at += 4 + 4 * u32(at)                                      # groups
    text = lambda i: strings[i] if 0 <= i < len(strings) else None   # noqa: E731

    starts, names = [], {}
    for kind, size in zip(kinds, sizes):
        starts.append(at)
        at += size
    for index, (kind, start) in enumerate(zip(kinds, starts)):
        if types[kind & 0x7FFF] == "CMeshEntry":
            name, base, extra = struct.unpack_from("<IIi", data, start)
            names[index] = text(name)
            out["entries"][text(name).lower()] = {"name": text(name), "texture_base": text(base),
                                                  "extra_data": text(extra), "search": bool(data[start + 12])}
    for kind, start in zip(kinds, starts):
        kind = types[kind & 0x7FFF]
        if kind == "CModelTemplate":
            name, count = u32(start), u32(start + 16)
            pos, assigned = start + 20, set()
            for _ in range(count):
                pos += 4 + u32(pos)                            # the slot
                n = u32(pos)
                entry = data[pos + 4:pos + 4 + n].rstrip(b"\0").decode("latin-1")
                pos += 4 + n
                if entry:
                    assigned.add(entry)
            out["templates"].setdefault(text(name).lower(), set()).update(assigned)
        elif kind == "CMesh":
            name, count = u32(start + 4), u32(start + 13)
            linked = out["meshes"].setdefault(text(name).lower(), set())
            linked.update(names[u32(start + 17 + 8 * i + 4)] for i in range(count)
                          if u32(start + 17 + 8 * i + 4) in names)
    return out


def mesh_entry(path: str | Path, template: str, part: str) -> dict | None:
    """The `CMeshEntry` a template draws a part with: of the entries the
    template assigns, the one that is the part itself or that a `CMesh` of the
    part's name links. None when the table names none, or more than one."""
    manager = model_manager(path)
    assigned = {e.lower() for e in manager["templates"].get(template.lower(), ())}
    stem = PureWindowsPath(part).stem.lower()
    found = ({stem} | {e.lower() for e in manager["meshes"].get(stem, ())}) & assigned
    return manager["entries"].get(next(iter(found))) if len(found) == 1 else None


def read_character(path: str | Path) -> Character:
    """Read a `.cat` into plain data. Knows nothing about Blender."""
    path = Path(path)
    nif = read_nif(path)

    try:
        root = next(b for b in nif.blocks if type(b).__name__ == ROOT_BLOCK)
    except StopIteration:
        raise ValueError(f"{path.name} is not a character template") from None

    character = Character(name=path.stem, path=path)

    for entry in root.sub_entry_list:
        kind, name = _kind(entry), str(entry.name)

        if kind == SKELETON:
            character.skeleton = entry.skeleton_data_reference

        elif kind == MESH:
            character.meshes.append(Mesh(
                name=name, root=entry.mesh_data_reference,
                entry=mesh_entry(path.parent.parent / MESH_ENTRIES, path.stem, name)))

        elif kind == ANIMATION_SET:
            character.animation_set = bytes(entry.binary_data)

        elif kind == ANIMATION:
            for sequence in entry.controller_seq_list:
                character.clips.append(
                    Clip(
                        name=str(sequence.name),
                        start=sequence.start_time,
                        stop=sequence.stop_time,
                        sequence=sequence,
                    )
                )

    return character


def read_clips(path: str | Path) -> list[Clip]:
    """The clips in a standalone `.kf` file, as a family's shared set holds."""
    return _sequences(read_nif(path))
