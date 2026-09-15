"""Clips.

A Divinity II clip does not store a key per frame. It stores the control
points of a cubic B-spline, quantised to 16-bit integers, and the game
evaluates the curve as it plays. This is why a keyframe importer reads such a
clip and finds nothing: there are no keyframes in it to find.

`nifgen` already undoes the quantisation -- `get_translations`,
`get_rotations`, `get_scales` hand back the control points as floats. What is
left is evaluating the curve through them, which is what this module does.

A track whose handle reads `NO_HANDLE` is not animated at all; the
interpolator's own static transform is the value for the whole clip.
"""

from dataclasses import dataclass, field

#: A handle of 0xFFFF means "this track is not animated".
NO_HANDLE = 65535

#: Gamebryo's B-splines are cubic.
DEGREE = 3

BSPLINE_INTERPOLATOR = "NiBSplineCompTransformInterpolator"
TRANSFORM_INTERPOLATOR = "NiTransformInterpolator"


def evaluate(control_points: list, at: float) -> tuple:
    """A uniform cubic B-spline through `control_points`, at 0.0 <= at <= 1.0.

    The control points are not points on the curve; each span is a weighted
    blend of four of them. Treating them as keyframes -- which is the tempting
    shortcut -- gives an animation that is close but wrong, and wrong in a way
    that looks like bad rigging rather than bad maths.
    """
    n = len(control_points)
    if n == 0:
        return ()
    if n <= DEGREE:
        return tuple(control_points[-1])

    spans = n - DEGREE
    u = max(0.0, min(1.0, at)) * spans
    i = min(int(u), spans - 1)
    t = u - i

    t2, t3 = t * t, t * t * t
    b = (
        (1.0 - 3.0 * t + 3.0 * t2 - t3) / 6.0,
        (4.0 - 6.0 * t2 + 3.0 * t3) / 6.0,
        (1.0 + 3.0 * t + 3.0 * t2 - 3.0 * t3) / 6.0,
        t3 / 6.0,
    )

    width = len(control_points[i])
    return tuple(
        sum(b[k] * control_points[i + k][axis] for k in range(4))
        for axis in range(width)
    )


@dataclass
class Track:
    """What one bone does over one clip."""

    node: str
    translations: list = field(default_factory=list)
    rotations: list = field(default_factory=list)
    scales: list = field(default_factory=list)
    static: object = None  # NiQuatTransform, when a track is not animated

    @property
    def animated(self) -> bool:
        return bool(self.translations or self.rotations or self.scales)


def _as_lists(interpolator):
    """Control points, or empty where the handle says the track is static."""
    def maybe(handle, get, wrap):
        if handle == NO_HANDLE:
            return []
        return [wrap(v) for v in get()]

    return (
        maybe(interpolator.translation_handle, interpolator.get_translations, tuple),
        maybe(interpolator.rotation_handle, interpolator.get_rotations, tuple),
        maybe(interpolator.scale_handle, interpolator.get_scales, lambda v: (v,)),
    )


def tracks(sequence) -> list[Track]:
    """One track per controlled block of a `NiControllerSequence`."""
    out = []
    for block in sequence.controlled_blocks:
        interpolator = block.interpolator
        if interpolator is None:
            continue
        node = str(block.node_name)
        kind = type(interpolator).__name__

        if kind == BSPLINE_INTERPOLATOR:
            translations, rotations, scales = _as_lists(interpolator)
            out.append(
                Track(
                    node=node,
                    translations=translations,
                    rotations=rotations,
                    scales=scales,
                    static=interpolator.transform,
                )
            )
        elif kind == TRANSFORM_INTERPOLATOR:
            # Plain keyframes. A clip mixes both kinds: the root is usually a
            # transform interpolator while the bones are B-splines.
            out.append(Track(node=node, static=interpolator.transform))

    return out
