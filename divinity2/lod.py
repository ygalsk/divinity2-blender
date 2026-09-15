"""Levels of detail.

A character ships every level of detail in the same file -- `Froblin_HI`,
`Froblin_MED`, `Froblin_LOW` -- and importing all three stacks three bodies in
the same place.

Which is which is written down, so it need not be guessed from the name. Every
shape carries a `UserPropBuffer` string, and in it:

    NiBoneLOD#Skin#0#0#

    LODDistance = 0.0

The number after `Skin#` is the level, 0 being the one the game shows up close.
A shape with no such string is not part of a LOD group and is always shown.
"""

import re

USER_PROP = "UserPropBuffer"

_LEVEL = re.compile(r"NiBoneLOD#\w+#(\d+)#")
_DISTANCE = re.compile(r"LODDistance\s*=\s*([0-9.]+)")

#: The level the game shows at close range.
NEAREST = 0

#: A line on its own in the buffer that means the shape is never drawn.
#: Seven shapes across the 324 templates carry it -- helper geometry that
#: would otherwise arrive as a visible lump.
HIDDEN = "NiHide"


def _user_prop(shape) -> str:
    for extra in getattr(shape, "extra_data_list", None) or ():
        if extra is None:
            continue
        if str(getattr(extra, "name", "")) == USER_PROP:
            return str(getattr(extra, "string_data", ""))
    return ""


def level_of(shape) -> int | None:
    """The shape's LOD level, or None when it is not in a LOD group."""
    match = _LEVEL.search(_user_prop(shape))
    return int(match.group(1)) if match else None


def distance_of(shape) -> float | None:
    match = _DISTANCE.search(_user_prop(shape))
    return float(match.group(1)) if match else None


def is_hidden(shape) -> bool:
    """Does the shape say it is never drawn?"""
    return any(
        line.strip().rstrip("#") == HIDDEN
        for line in _user_prop(shape).splitlines()
    )


def is_nearest(shape) -> bool:
    """Should this shape be the visible one?"""
    level = level_of(shape)
    return level is None or level == NEAREST
