"""What a shape's properties say about its surface.

`nif.xml` describes the blocks; what it does not say is which combinations
Divinity II actually ships and what they mean on screen. Measured over the
character templates, there are three:

| `NiAlphaProperty.flags` | what it is |
|---|---|
| 4844 | alpha test, `GREATER` than the threshold -- a cut-out |
| 4333 | alpha blend, `SRC_ALPHA` over `INV_SRC_ALPHA` |
| 4097 | additive, `ONE` plus `ONE` |

168 of the 324 characters carry one. Ignoring the block is why hair, capes
and glow planes arrive as opaque cards.

The flag word is the standard Gamebryo layout:

    bit 0      blending enabled
    bits 1-4   source blend factor
    bits 5-8   destination blend factor
    bit 9      testing enabled
    bits 10-12 test function
    bit 13     no sorter
"""

from dataclasses import dataclass

#: The blend factors, in the order the flag word numbers them.
FACTORS = (
    "ONE", "ZERO", "SRC_COLOR", "INV_SRC_COLOR", "DST_COLOR", "INV_DST_COLOR",
    "SRC_ALPHA", "INV_SRC_ALPHA", "DST_ALPHA", "INV_DST_ALPHA", "SRC_ALPHA_SAT",
)

#: The test functions, likewise.
FUNCTIONS = (
    "ALWAYS", "LESS", "EQUAL", "LESS_EQUAL", "GREATER", "NOT_EQUAL",
    "GREATER_EQUAL", "NEVER",
)


@dataclass
class Alpha:
    """A decoded `NiAlphaProperty`."""

    blending: bool = False
    source: str = "ONE"
    destination: str = "ZERO"
    testing: bool = False
    function: str = "ALWAYS"
    threshold: int = 0

    @property
    def additive(self) -> bool:
        return self.blending and self.source == "ONE" and self.destination == "ONE"

    @property
    def transparent(self) -> bool:
        """Does anything here make the surface see-through?"""
        return self.blending or self.testing


def _name(table, index: int, fallback: str) -> str:
    return table[index] if 0 <= index < len(table) else fallback


def alpha(block) -> Alpha:
    """Decode a `NiAlphaProperty`."""
    flags = int(block.flags)
    return Alpha(
        blending=bool(flags & 1),
        source=_name(FACTORS, (flags >> 1) & 0xF, "ONE"),
        destination=_name(FACTORS, (flags >> 5) & 0xF, "ZERO"),
        testing=bool((flags >> 9) & 1),
        function=_name(FUNCTIONS, (flags >> 10) & 0x7, "ALWAYS"),
        threshold=int(block.threshold),
    )

