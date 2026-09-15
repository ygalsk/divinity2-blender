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


#: Game units in a metre. Every model in the game is authored in
#: centimetres: a human template comes out 1.87 m, a Maxos gate 4.6 m tall, a
#: ruined wall 15.7 m long. How many of those units reach the world is on the
#: tree's root node -- see `blender.importer`.
#:
#: The `worldScale` float the files carry next to their shapes is **not**
#: this. It is a shader input: `DivStandardMaterial::HandleNormalMap` binds it
#: as a material-node variable beside `LocalScale`, and
#: `CShadingTools::SetupStandardData` overwrites the authored value with 1.0
#: before drawing. The engine never reads it as a unit, and neither do we.
UNITS_PER_METRE = 100.0


def is_divinity2(nif) -> bool:
    """Is this the Divinity 2 dialect, rather than another Gamebryo game?"""
    return nif.version == NIF_VERSION and nif.user_version in USER_VERSIONS
