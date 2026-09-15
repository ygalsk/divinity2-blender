"""Reading the game's files. No Blender needed.

Point `DV2_GAME` at an install (or an extraction of one) to run these.
"""

import os
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from divinity2 import binxml, catalog, graph, lod, region, rig, terrain, texture
from divinity2.character import read_asset, read_character, read_model
from divinity2.nif import UNITS_PER_METRE, is_divinity2, read_nif

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
    def test_a_texture_is_found_whatever_the_case(self):
        """The assets spell their own textures freely; Linux does not."""
        found = texture.texture_path("btb_rocks_c.dds", GAME)
        self.assertTrue(found.is_file(), "BTB_Rocks_C.nif should be found")
        missing = texture.texture_path("no_such_texture_at_all.tga", GAME)
        self.assertFalse(missing.is_file(), "the index must not invent a file")

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


@unittest.skipUnless(GAME.is_dir(), "set DV2_GAME to an install")
class TestAnimationSet(unittest.TestCase):
    """The KFM, against NifTools' own description of it."""

    def test_every_animation_set_in_the_game_parses(self):
        from divinity2 import kfm

        files = sorted((GAME / "Win32/Characters").rglob("*.kfm"))
        self.assertGreater(len(files), 100)

        complete = 0
        for path in files:
            parsed = kfm.read(path.read_bytes())
            self.assertTrue(parsed.skeleton.endswith(".nif"), path.name)
            self.assertTrue(parsed.kf_files, path.name)
            complete += parsed.complete
        # 105 of 121 read to the last byte; the rest stop in a transition
        # list, after they have named their files. Both are usable.
        self.assertGreaterEqual(complete, 100)

    def test_a_character_carries_its_own_animation_set(self):
        from divinity2 import rig

        character = read_character(
            GAME / "Win32/Characters/Templates/Black_Goblin.cat"
        )
        parsed = rig.animation_set(character)
        self.assertIsNotNone(parsed, "the .cat's CAMDataEntry should parse")
        self.assertEqual(parsed.master, "Scene Root")
        self.assertTrue(parsed.skeleton.endswith("Skeleton.nif"))
        self.assertEqual(
            [p.name for p in rig.clip_files(character, GAME)], ["Froblin_Base.kf"]
        )

    def test_a_kfm_is_recognised_by_its_header(self):
        """The negative control: a NIF is not a KFM."""
        from divinity2 import kfm

        nif = GAME / "Win32/Characters/Froblin/Skeleton.nif"
        with self.assertRaises(ValueError):
            kfm.read(nif.read_bytes())


@unittest.skipUnless(GAME.is_dir(), "set DV2_GAME to an install")
class TestAsset(unittest.TestCase):
    """Everything that is not a character: scenery, items, effects, terrain."""

    def test_every_kind_is_indexed(self):
        kinds = {a.kind for a in catalog.assets(GAME)}
        self.assertEqual(kinds, set(catalog.KINDS))

    def test_a_chest_arrives_with_geometry(self):
        chest = read_model(catalog.search(GAME, "chest", kind="item")[0].path)
        self.assertIsNone(chest.skeleton)  # a chest has no rig
        self.assertEqual(len(chest.meshes), 1)
        self.assertTrue(_shapes(chest), "no NiTriShape under the root")

    def test_a_compiled_model_is_one_lod_group(self):
        """Two groups of one folder are two models, not two halves of one."""
        groups = catalog.search(GAME, "AL_Statue_A", kind="terrain")
        self.assertEqual(len(groups), 2)
        self.assertEqual(
            sorted(a.name for a in groups),
            ["AL_Statue_A LODGroup01", "AL_Statue_A LODGroup02"],
        )
        statue = read_model(groups[0].path)
        self.assertEqual(len(statue.meshes), 1)
        # the finest level, not the first file
        self.assertEqual(statue.path.name, "LODGroup01")

    def test_a_fortress_carries_its_own_bones(self):
        """It is skinned, and there is no family skeleton file for it."""
        fortress = read_model(catalog.search(GAME, "", kind="fortress")[0].path)
        self.assertIsNotNone(fortress.skeleton)
        self.assertIsNone(rig.skeleton_path(fortress, GAME))

    def test_read_model_dispatches_on_the_extension(self):
        cat = catalog.search(GAME, "Black_Goblin")[0].path
        self.assertTrue(read_model(cat).clips, "a .cat brings its clips")
        self.assertGreater(len(read_model(cat).meshes), 1)

    def test_the_root_node_states_the_scale(self):
        """A character leaves `Scene Root` at 1.0; a plain asset bakes 0.01."""
        goblin = read_model(catalog.search(GAME, "Black_Goblin")[0].path)
        self.assertEqual(float(goblin.meshes[0].root.scale), 1.0)
        chest = read_model(catalog.search(GAME, "chest", kind="item")[0].path)
        self.assertAlmostEqual(float(chest.meshes[0].root.scale), 0.01)

    def test_things_come_out_the_size_they_look(self):
        """The scale, end to end. Drop either term and this fails.

        `worldScale` was read as the unit until the engine said otherwise, and
        the result was every piece of scenery in the game at 1/100 of its
        size -- invisible on a character, because a character's root is 1.0.
        """
        for name, kind, low, high in (
            ("Black_Goblin", "character", 1.0, 2.5),   # a goblin
            ("IT_Door_Maxos_C", "item", 2.0, 8.0),     # a gate
            ("P_Damian_Fountain_A", "scenery", 1.0, 8.0),
        ):
            with self.subTest(name):
                size = _metres(read_model(catalog.search(GAME, name, kind=kind)[0].path))
                self.assertTrue(low <= max(size) <= high, f"{name} is {size}")

    def test_the_lod_node_shows_the_nearest_child_with_geometry(self):
        """The nearest child is usually an empty stub. 1,055 of 1,059 are."""
        from divinity2.nif import read_nif

        static = GAME / "World/Banditcamp/Main/StaticMeshes.nif"
        if not static.is_file():
            self.skipTest("no Banditcamp in this install")
        nif = read_nif(static)
        nodes = [b for b in nif.blocks if type(b).__name__ == "NiLODNode"]
        self.assertTrue(nodes, "the region's terrain is held in NiLODNodes")
        for node in nodes:
            with self.subTest(str(node.name)):
                show, hide = lod.lod_children(node)
                self.assertIsNotNone(show, "every one of them holds a mesh")
                self.assertTrue(lod._holds_geometry(show))
                # the negative control: the nearest child is the empty one
                first = [c for c in node.children if c is not None][0]
                self.assertIn(first, [show] + hide)

    def test_the_walk_names_things_and_drops_only_what_the_engine_drops(self):
        """A quarter of the game's shapes are called `Undefined Geometry`."""
        static = GAME / "World/Banditcamp/Main/StaticMeshes.nif"
        if not static.is_file():
            self.skipTest("no Banditcamp in this install")
        drawn = list(graph.walk(read_model(static).meshes[0].root))
        self.assertTrue(drawn)
        anonymous = [d for d in drawn if d.name.strip().lower() in graph.ANONYMOUS]
        self.assertEqual(anonymous, [], "every shape takes a name from above it")
        # every yielded shape carries its whole node path and real geometry
        for d in drawn:
            self.assertIn("/", d.path)
            self.assertTrue(d.data.num_vertices)
        # the negative control: the file holds shapes the walk must not yield
        culled = [b for b in read_nif(static).blocks
                  if type(b).__name__ in graph.SHAPES and lod.is_culled(b)]
        self.assertTrue(culled, "Banditcamp marks 10 shapes APP_CULLED")
        yielded = {id(d.shape) for d in drawn}
        self.assertTrue(all(id(c) not in yielded for c in culled))

    def test_the_terrain_finds_its_picture_by_index(self):
        """It carries no texturing property, so the model cannot say."""
        static = GAME / "World/Banditcamp/Main/StaticMeshes.nif"
        if not static.is_file():
            self.skipTest("no Banditcamp in this install")
        patches = [d for d in graph.walk(read_model(static).meshes[0].root)
                   if terrain.patch_of(d.path) is not None]
        self.assertTrue(patches, "the region's ground is in StaticMeshes.nif")
        for d in patches:
            with self.subTest(d.path):
                self.assertNotIn("NiTexturingProperty", d.properties)
                index = terrain.patch_of(d.path)
                self.assertIsNotNone(terrain.megatexture(static, index))
                self.assertTrue(d.data.uv_sets, "and it is already unwrapped")
        # the negative control: an ordinary shape is not terrain
        other = next(d for d in graph.walk(read_model(static).meshes[0].root)
                     if terrain.patch_of(d.path) is None)
        self.assertIsNone(terrain.megatexture(static, terrain.patch_of(other.path)))

    def test_a_texture_nif_is_not_a_model(self):
        """The negative control: the texture folder holds no geometry."""
        any_texture = next((GAME / catalog.TEXTURES).glob("*.nif"))
        with self.assertRaises(ValueError):
            read_asset(any_texture)


@unittest.skipUnless(GAME.is_dir(), "set DV2_GAME to an install")
class TestRegion(unittest.TestCase):
    """One region, read the way the engine reads it."""

    def test_children_come_out_in_the_engines_order(self):
        """`children[0]` is the position and `children[1]` the basis.

        The stream stores them the other way round, and `binxml` undoes that
        for everything. The proof is that the basis then has determinant +1:
        a placement is a rotation, and a reflection would turn every prop in
        the region inside out.
        """
        import numpy as np

        doc = binxml.read((GAME / "World/Banditcamp/Main/scenery.xml").read_bytes())
        found = list(doc.find_all("Scenery"))
        self.assertEqual(len(found), 775)
        for node in found:
            self.assertTrue(node.children[0].is_a("NiPoint3"))
            self.assertTrue(node.children[1].is_a("NiMatrix3"))
            rows = [[float(r.get(k)) for k in "xyz"] for r in node.children[1].children]
            self.assertGreater(np.linalg.det(np.array(rows)), 0.9)

    def test_a_region_holds_six_kinds_of_thing(self):
        found = region.read(GAME, "Banditcamp", "Main")
        counts = {k: len(found.of(k)) for k in
                  ("scenery", "character", "item", "trigger", "light", "tree")}
        self.assertEqual(counts, {"scenery": 775, "character": 47, "item": 169,
                                  "trigger": 82, "light": 96, "tree": 59})
        self.assertEqual(found.missing, {"scenery": 0, "character": 0, "item": 0})
        self.assertTrue(found.statics.is_file())
        self.assertTrue(found.vegetation.is_file())

    def test_a_character_finds_its_template(self):
        """Visual UUID -> `TemplateName` -> `Characters/Templates/<name>.cat`."""
        found = region.read(GAME, "Banditcamp", "Main")
        skeleton = next(p for p in found.of("character")
                        if p.fields.get("VisualPrototypeUUID") == "Skeleton_DW")
        self.assertEqual(skeleton.model.name, "Skeleton_DW.cat")

    def test_an_item_finds_its_model_through_two_tables(self):
        """Item UUID -> `VisualUUID` -> `Folder`/`NifFileName`.item."""
        found = region.read(GAME, "Banditcamp", "Main")
        barrel = next(p for p in found.of("item")
                      if p.fields.get("PrototypeUUID", "").startswith("IT_Containers_Barrels"))
        self.assertTrue(barrel.model.is_file())
        self.assertEqual(barrel.model.suffix, ".item")

    def test_an_area_trigger_is_a_prism(self):
        found = region.read(GAME, "Banditcamp", "Main")
        areas = [p for p in found.of("trigger") if p.polygon]
        self.assertTrue(areas)
        for area in areas:
            bottom, top = area.height
            self.assertGreater(top, bottom)
            # every corner sits on the bottom plane; the top is the extrusion
            for corner in area.polygon:
                self.assertAlmostEqual(corner[2], bottom, places=3)

    def test_the_sun_shines_downwards(self):
        """`MakeZRotation(z) * MakeYRotation(y)`, and the light goes along -X.

        The negative control is in the numbers: of the six axes the basis
        could use, only -X is below the horizon in every region that ships a
        `Day` set.
        """
        import numpy as np

        below = {}
        for name in region.regions(GAME):
            found = region.read(GAME, name, "Main")
            for sun in (p for p in found.of("light") if p.fields["shape"] == "sun"):
                basis = region.sun_basis(sun.fields["angle_y"], sun.fields["angle_z"])
                for label, axis in (("+X", basis[:, 0]), ("-X", -basis[:, 0]),
                                    ("+Y", basis[:, 1]), ("-Y", -basis[:, 1]),
                                    ("+Z", basis[:, 2]), ("-Z", -basis[:, 2])):
                    below[label] = below.get(label, 0) + (axis[2] < 0)
                below["total"] = below.get("total", 0) + 1
        self.assertGreater(below["total"], 0)
        self.assertEqual(below["-X"], below["total"])
        self.assertLess(below["+X"], below["total"])

    def test_a_tree_is_the_size_the_engine_gives_it(self):
        """`rescaled.y * size`, `rescaled.y = (1 - v) + instance.y * v * 2`."""
        found = region.read(GAME, "Banditcamp", "Main")
        trees = found.of("tree")
        self.assertTrue(trees)
        for tree in trees:
            self.assertGreater(tree.scale, 0.0)
            self.assertLess(tree.scale, 200.0)
        self.assertTrue(any(t.fields["spt"].endswith(".spt") for t in trees))



def _metres(character):
    """The model's overall size in metres, by the same rule the importer uses."""
    import numpy as np

    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for mesh in character.meshes:
        factor = 1.0 / (UNITS_PER_METRE * float(mesh.root.scale))

        def walk(node, m):
            r = node.rotation
            local = np.eye(4)
            local[:3, :3] = np.array([
                [r.m_11, r.m_12, r.m_13],
                [r.m_21, r.m_22, r.m_23],
                [r.m_31, r.m_32, r.m_33],
            ]).T * float(node.scale)
            local[:3, 3] = (node.translation.x, node.translation.y, node.translation.z)
            w = m @ local
            data = getattr(node, "data", None)
            if type(node).__name__ in ("NiTriShape", "NiTriStrips") and data is not None:
                if data.num_vertices:
                    v = np.array([(p.x, p.y, p.z, 1.0) for p in data.vertices]).T
                    yield (w @ v)[:3].T * factor
            for child in getattr(node, "children", ()) or ():
                if child is not None:
                    yield from walk(child, w)

        for points in walk(mesh.root, np.eye(4)):
            lo = np.minimum(lo, points.min(0))
            hi = np.maximum(hi, points.max(0))
    return (hi - lo).tolist()


def _shapes(character):
    """Every NiTriShape under a character's mesh roots."""
    out = []
    stack = [m.root for m in character.meshes]
    while stack:
        node = stack.pop()
        if node is None:
            continue
        if type(node).__name__ in ("NiTriShape", "NiTriStrips"):
            out.append(node)
        stack += list(getattr(node, "children", ()) or ())
    return out
