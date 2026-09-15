"""Opening a Divinity II NIF file.

The format itself is not described here. It is described in `nif.xml`, the
NifTools project's format specification, and read by `nifgen`, the Python
reader generated from it. `nif.xml` carries Divinity 2 as a version of its
own: NIF 20.3.0.9 with user version 0x20000 or 0x30000, extensions `nft`,
`item` and `cat`.

So this module does one thing: it puts the vendored reader on the path and
opens the file. If a block is read wrongly, the fix belongs in `nif.xml`
upstream, not here.
"""

import sys
from pathlib import Path

#: Divinity II's NIF version, as `nif.xml` states it.
NIF_VERSION = 0x14030009
#: The two user versions that mark the Divinity 2 variant of that version.
USER_VERSIONS = (0x20000, 0x30000)

_VENDOR = Path(__file__).resolve().parent.parent / "vendor"


def _reader():
    if str(_VENDOR) not in sys.path:
        sys.path.insert(0, str(_VENDOR))
    from nifgen.formats.nif import NifFile

    return NifFile


def read_nif(path: str | Path):
    """Open any NIF the game ships: `.nif`, `.cat`, `.item`, `.nft`."""
    return _reader().from_path(Path(path))


#: The name of the float the game writes next to every shape, giving the
#: number of game units in a metre. It reads 100.0 in all 2,956 occurrences
#: across the 324 character templates -- so the scale is stated, not inferred.
WORLD_SCALE = "worldScale"

#: What to assume when a file does not carry one.
DEFAULT_WORLD_SCALE = 100.0


def world_scale(nif) -> float:
    """Game units per metre, as the file states it."""
    for block in nif.blocks:
        if type(block).__name__ != "NiFloatExtraData":
            continue
        if str(block.name) == WORLD_SCALE and block.float_data > 0.0:
            return float(block.float_data)
    return DEFAULT_WORLD_SCALE


def is_divinity2(nif) -> bool:
    """Is this the Divinity 2 dialect, rather than another Gamebryo game?"""
    return nif.version == NIF_VERSION and nif.user_version in USER_VERSIONS
