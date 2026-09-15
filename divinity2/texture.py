"""Divinity II textures.

A texture in this game is a NIF file holding one
`NiPersistentSrcTextureRendererData` block: a DXT-compressed surface with its
mipmaps, and nothing else. Nothing but this game ships textures that way, so
this is ours to handle -- but the block itself is standard and described in
`nif.xml`.

The pixel data is already exactly what a DDS file carries. Only the 128-byte
header is missing, so a texture becomes loadable by writing that header in
front of the bytes. No decoding, no conversion, no quality lost.

A mesh names its texture with a `.tga` or `.dds` extension it never had on
disk; the file beside it is the same name with `.nif`. It does not name it in
the same case either, and nothing in the game ever noticed, because its
archives and Windows are both case-insensitive.
"""

import struct
from functools import lru_cache
from pathlib import Path

from .nif import read_nif

#: Where the game keeps every character and prop texture.
TEXTURE_DIR = Path("Win32") / "Textures"

#: nif.xml's PixelFormat values that carry a DDS four-character code.
FOURCC = {
    "FMT_DXT1": b"DXT1",
    "FMT_DXT3": b"DXT3",
    "FMT_DXT5": b"DXT5",
}

_DDSD = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000  # caps|h|w|fmt|mips|linear
_DDPF_FOURCC = 0x4
_DDSCAPS = 0x1000 | 0x8 | 0x400000  # texture|complex|mipmap


@lru_cache(maxsize=8)
def _by_lower_stem(game_root: Path) -> dict:
    """Every texture in the install, keyed by its name in lower case.

    A mesh asks for `btb_rocks_c.dds` and the file is `BTB_Rocks_C.nif`; a
    mesh asks for `p_environment_bv3_tree_a_Nm.tga` and the file is
    `P_Environment_BV3_Tree_A_NM.nif`. On Windows that is the same name. On
    Linux it is not, and taking the asset's spelling literally leaves 409 of
    the game's 3,525 models untextured.
    """
    directory = Path(game_root) / TEXTURE_DIR
    if not directory.is_dir():
        return {}
    return {p.stem.lower(): p for p in directory.glob("*.nif")}


def texture_path(texture_name: str, game_root: Path) -> Path:
    """`Flying_Froblin_A_DM.tga` -> `<game>/Win32/Textures/..._DM.nif`."""
    stem = Path(str(texture_name)).stem
    direct = Path(game_root) / TEXTURE_DIR / (stem + ".nif")
    if direct.is_file():
        return direct
    return _by_lower_stem(Path(game_root)).get(stem.lower(), direct)


def to_dds(path: str | Path) -> bytes:
    """Read a texture NIF and return it as a DDS file's bytes."""
    nif = read_nif(path)
    try:
        block = next(
            b for b in nif.blocks
            if type(b).__name__ == "NiPersistentSrcTextureRendererData"
        )
    except StopIteration:
        raise ValueError(f"{Path(path).name} holds no texture") from None

    fmt = FOURCC.get(block.pixel_format.name)
    if fmt is None:
        raise ValueError(f"{Path(path).name}: {block.pixel_format.name} is not DXT")

    top = block.mipmaps[0]
    pixels = bytes(block.pixel_data)

    header = struct.pack(
        "<4sIIIIIII44sII4sIIIIIIIIII",
        b"DDS ", 124, _DDSD,
        top.height, top.width,
        len(pixels) // block.num_mipmaps if block.num_mipmaps else len(pixels),
        0, block.num_mipmaps,
        b"\0" * 44,
        32, _DDPF_FOURCC, fmt, 0, 0, 0, 0, 0,
        _DDSCAPS, 0, 0, 0, 0,
    )
    return header + pixels
