"""Read Divinity II: Developer's Cut's own files: its archives, and the binary XML in them, named.

    python -m dv2lib unpack <out> [<game folder>]

Standard library only, so it runs anywhere Python 3.11 does, Blender's included.
Taken from dv2mod (https://github.com/ygalsk/dv2-mod), which owns the research.
"""

__version__ = "0.1.0"


class Dv2Error(Exception):
    """A file this library cannot use. The message says which and why."""
