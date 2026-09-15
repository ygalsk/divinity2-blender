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


@unittest.skipUnless(GAME.is_dir(), "set DV2_GAME to an install")
class TestSkinning(unittest.TestCase):
    """The skinning formula, on the character that exposed it.

    `FroblinBoss.cat` bundles a body and a shoulder armour, and the armour's
    shape node sits 393 units off the origin while the body's sits on it. Any
    formula that folds `NiSkinData.skin_transform` into the deformation
    therefore looks right on the body and throws the armour off the character
    -- which reads like two rigs and is one wrong term.
    """

    @staticmethod
    def _skinned(node, parent=None, out=None):
        from divinity2 import skin as dv2_skin

        import numpy as np

        parent = np.eye(4) if parent is None else parent
        out = [] if out is None else out
        for child in getattr(node, "children", None) or ():
            if child is None:
                continue
            world = parent @ dv2_skin.matrix(child)
            if type(child).__name__ in ("NiTriShape", "NiTriStrips"):
                if getattr(child, "skin_instance", None) is not None:
                    out.append(child)
            TestSkinning._skinned(child, world, out)
        return out

    @staticmethod
    def _rest(skeleton_root):
        from divinity2 import skin as dv2_skin

        import numpy as np

        out = {}

        def walk(node, parent=np.eye(4)):
            world = parent @ dv2_skin.matrix(node)
            name = str(node.name)
            if name:
                out.setdefault(name, world)
            for child in getattr(node, "children", None) or ():
                if child is not None and hasattr(child, "children"):
                    walk(child, world)

        walk(skeleton_root)
        return out

    def _deformed(self, name):
        import numpy as np

        from divinity2 import rig, skin as dv2_skin

        character = read_character(GAME / f"Win32/Characters/Templates/{name}.cat")
        rest = self._rest(rig.shared_skeleton(character, GAME))
        out = {}
        for mesh in character.meshes:
            for shape in self._skinned(mesh.root):
                label = str(shape.name)
                if "_HI" not in label:
                    continue
                raw = np.array(
                    [[v.x, v.y, v.z] for v in shape.data.vertices], dtype=np.float64
                )
                out[label] = dv2_skin.to_rest_pose(raw, shape, rest)
        return out

    def test_the_armour_lands_inside_the_body(self):
        import numpy as np

        parts = self._deformed("FroblinBoss")
        body = parts["FroblinBoss_HI"]
        armour = parts["FroblinBoss_Armor_A_HI"]
        self.assertIsNotNone(body)
        self.assertIsNotNone(armour)

        low, high = body.min(0), body.max(0)
        self.assertTrue(
            np.all(armour.min(0) > low - 20.0) and np.all(armour.max(0) < high + 20.0),
            f"armour {armour.min(0)}..{armour.max(0)} "
            f"outside body {low}..{high}",
        )

    def test_a_character_stands_on_the_ground_at_a_plausible_height(self):
        body = self._deformed("Black_Goblin")["Froblin_HI"]
        self.assertLess(abs(body.min(0)[2]), 2.0, "feet should be near z = 0")
        height = body.max(0)[2] - body.min(0)[2]
        self.assertTrue(150.0 < height < 200.0, f"a goblin is {height} units tall")

    def test_folding_in_the_skin_transform_breaks_the_armour(self):
        """The negative control: add the wrong term, and the check must fail."""
        import numpy as np

        from divinity2 import rig, skin as dv2_skin

        character = read_character(GAME / "Win32/Characters/Templates/FroblinBoss.cat")
        rest = self._rest(rig.shared_skeleton(character, GAME))

        def wrongly(shape):
            inst = shape.skin_instance
            extra = dv2_skin.matrix(inst.data.skin_transform)
            raw = np.array(
                [[v.x, v.y, v.z] for v in shape.data.vertices], dtype=np.float64
            )
            weights = dv2_skin.weights(shape, len(raw))
            total = np.zeros((len(raw), 4, 4))
            mass = np.zeros(len(raw))
            for name, bone in dv2_skin.bone_matrices(shape).items():
                if name not in rest:
                    continue
                column = weights[name]
                touched = column > 0.0
                if not touched.any():
                    continue
                total[touched] += column[touched, None, None] * (
                    rest[name] @ bone @ extra
                )
                mass[touched] += column[touched]
            bound = mass > 1e-6
            total[bound] /= mass[bound, None, None]
            total[~bound] = np.eye(4)
            h = np.concatenate([raw, np.ones((len(raw), 1))], axis=1)
            return np.einsum("nij,nj->ni", total, h)[:, :3]

        parts = {}
        for mesh in character.meshes:
            for shape in self._skinned(mesh.root):
                if "_HI" in str(shape.name):
                    parts[str(shape.name)] = wrongly(shape)

        body = parts["FroblinBoss_HI"]
        armour = parts["FroblinBoss_Armor_A_HI"]
        self.assertGreater(
            float((armour.max(0) - body.max(0)).max()),
            100.0,
            "the wrong term should throw the armour off the character",
        )
