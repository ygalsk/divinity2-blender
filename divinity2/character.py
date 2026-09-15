"""A Divinity II character template (`.cat`).

A `.cat` is a NIF file that bundles a whole character: the skeleton, the mesh
files, the animation set and the clips, each as an `MdlMan::` entry that keeps
the path it had before it was bundled. Nothing else has to be found on disk.

See `docs/cat.md` for the block layout.
"""

from dataclasses import dataclass, field
from pathlib import Path

from .nif import read_nif

#: The entry kinds a `.cat` root holds, by their block name without namespace.
SKELETON = "CSkeletonDataEntry"
MESH = "CMeshDataEntry"
ANIMATION = "CAnimationDataEntry"
ANIMATION_SET = "CAMDataEntry"

ROOT_BLOCK = "MdlMan::CModelTemplateDataEntry"


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
    nif = read_nif(path)
    return [
        Clip(
            name=str(s.name),
            start=s.start_time,
            stop=s.stop_time,
            sequence=s,
        )
        for s in nif.blocks
        if type(s).__name__ == "NiControllerSequence"
    ]
