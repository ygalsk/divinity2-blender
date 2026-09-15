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

from dataclasses import dataclass, field
from pathlib import Path

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
            character.meshes.append(Mesh(name=name, root=entry.mesh_data_reference))

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
