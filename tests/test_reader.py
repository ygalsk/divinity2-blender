"""Reading the game's files. No Blender needed.

Point `DV2_GAME` at an install (or an extraction of one) to run these.
"""

import os
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from divinity2 import catalog, rig, texture
from divinity2.character import read_character
from divinity2.nif import is_divinity2, read_nif

GAME = Path(os.environ.get("DV2_GAME", ""))


@unittest.skipUnless(GAME.is_dir(), "set DV2_GAME to an install")
class TestCharacter(unittest.TestCase):
    def setUp(self):
        found = catalog.search(GAME, "Black_Goblin")
        self.assertTrue(found, "no Black_Goblin in the install")
        self.character = read_character(found[0].path)

    def test_it_is_the_divinity2_dialect(self):
        nif = read_nif(self.character.path)
        self.assertTrue(is_divinity2(nif))

    def test_a_creature_brings_its_own_skeleton_and_clips(self):
        self.assertIsNotNone(self.character.skeleton)
        self.assertTrue(self.character.meshes)
        self.assertTrue(self.character.clips)

    def test_clips_are_named_as_the_game_names_them(self):
        """A `.cat` holds only the character's own variant clips.

        `Black_Goblin` carries deaths, stuns and a flee -- not `Idle1` and not
        a walk. Those live in the family's shared `.kf`, which the bundled KFM
        names. Asserting `Idle1` here would be asserting the wrong thing.
        """
        names = {c.name for c in self.character.clips}
        self.assertIn("Stunned", names)
        self.assertTrue(any(n.startswith("Die_") for n in names))
        self.assertNotIn("Idle1", names)

    def test_the_animation_set_is_a_headerless_kfm(self):
        self.assertGreater(len(self.character.animation_set), 0)

    def test_a_shape_carries_uvs_although_has_uv_reads_zero(self):
        """The trap: `has_uv` is a legacy field and lies at this version."""
        nif = read_nif(self.character.path)
        data = next(
            b for b in nif.blocks if type(b).__name__ == "NiTriShapeData"
        )
        self.assertEqual(data.has_uv, 0)  # the field says no
        self.assertTrue(len(data.uv_sets))  # the shape says yes

    def test_the_family_rig_is_found(self):
        self.assertEqual(rig.family_of(self.character, GAME), "Froblin")
        self.assertTrue(rig.clip_files(self.character, GAME))

    def test_a_human_borrows_its_skeleton(self):
        human = read_character(catalog.search(GAME, "DefaultHumanMale")[0].path)
        self.assertIsNone(human.skeleton)  # not in its own file
        self.assertIsNotNone(rig.shared_skeleton(human, GAME))  # but found

    def test_a_non_character_is_refused(self):
        """The negative control: a texture NIF must not read as a character."""
        any_texture = next((GAME / catalog.TEXTURES).glob("*.nif"))
        with self.assertRaises(ValueError):
            read_character(any_texture)


@unittest.skipUnless(GAME.is_dir(), "set DV2_GAME to an install")
class TestTexture(unittest.TestCase):
    def test_a_texture_nif_becomes_a_dds(self):
        path = texture.texture_path("Froblin_A_DM.tga", GAME)
        self.assertTrue(path.exists(), path)
        dds = texture.to_dds(path)
        self.assertEqual(dds[:4], b"DDS ")
        self.assertIn(dds[84:88], (b"DXT1", b"DXT3", b"DXT5"))

    def test_a_character_is_not_a_texture(self):
        """The negative control, the other way round."""
        found = catalog.search(GAME, "Black_Goblin")
        with self.assertRaises(ValueError):
            texture.to_dds(found[0].path)


if __name__ == "__main__":
    unittest.main()
