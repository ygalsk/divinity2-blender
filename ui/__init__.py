"""The whole interface: one import operator and one panel.

Choose a name, press OK, the asset arrives. No file browser, no preferences
beyond the game's location, no command line.
"""

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import AddonPreferences, Operator, Panel

from ..blender.importer import import_asset
from ..blender.region import KINDS, import_region
from ..divinity2 import catalog, region

PACKAGE = __package__.rpartition(".")[0]


def _game_root(context) -> str:
    return context.preferences.addons[PACKAGE].preferences.game_root


class DV2_AddonPreferences(AddonPreferences):
    bl_idname = PACKAGE

    game_root: StringProperty(
        name="Divinity II install",
        description="The folder holding Win32 and World",
        subtype="DIR_PATH",
        default="",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "game_root")
        if self.game_root and not catalog.looks_like_game(self.game_root):
            layout.label(text="No Win32 folder here", icon="ERROR")


def _asset_items(self, context):
    root = _game_root(context)
    if not root:
        return [("", "Set the install path in Preferences", "")]
    found = catalog.search(root, self.search)
    if not found:
        return [("", "Nothing matches", "")]
    return [(str(a.path), a.name, a.kind) for a in found]


class DV2_OT_import_asset(Operator):
    """Import a Divinity II model by name: character, scenery, item, effect"""

    bl_idname = "divinity2.import_asset"
    bl_label = "Divinity II asset"
    bl_options = {"REGISTER", "UNDO"}

    search: StringProperty(name="Name", default="")
    choice: EnumProperty(name="Asset", items=_asset_items)

    def invoke(self, context, event):
        if not _game_root(context):
            self.report({"ERROR"}, "Set the Divinity II install path in Preferences")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "search")
        layout.prop(self, "choice")

    def _resolve(self, context) -> str | None:
        """The asset to import: the one picked, or the one a name can only mean.

        The enum is only filled in by the dialog, so a script that passes a
        name alone arrives here with nothing chosen. A name that matches one
        asset, or matches one exactly, needs no second question.
        """
        if self.choice:
            return self.choice
        root = _game_root(context)
        found = catalog.search(root, self.search) if root else []
        exact = [a for a in found if a.name.lower() == self.search.lower()]
        if exact:
            return str(exact[0].path)
        if len(found) == 1:
            return str(found[0].path)
        if found:
            self.report(
                {"ERROR"}, f"{len(found)} assets match '{self.search}' -- pick one"
            )
        else:
            self.report({"ERROR"}, f"Nothing matches '{self.search}'")
        return None

    def execute(self, context):
        chosen = self._resolve(context)
        if chosen is None:
            return {"CANCELLED"}

        result = import_asset(chosen, _game_root(context))
        self.report(
            {"INFO"},
            f"{len(result.objects)} objects, {result.bones} bones, "
            f"{result.skinned} skinned, {result.clips} clips",
        )
        return {"FINISHED"}


def _region_items(self, context):
    root = _game_root(context)
    found = region.regions(root) if root else []
    return [(n, n, "") for n in found] or [("", "No World folder here", "")]


def _sub_items(self, context):
    root = _game_root(context)
    found = region.subregions(root, self.region_name) if root and self.region_name else []
    return [(n, n, "") for n in found] or [("Main", "Main", "")]


class DV2_OT_import_region(Operator):
    """Import a whole Divinity II region: ground, props, people, lights"""

    bl_idname = "divinity2.import_region"
    bl_label = "Divinity II region"
    bl_options = {"REGISTER", "UNDO"}

    region_name: EnumProperty(name="Region", items=_region_items)
    sub: EnumProperty(name="Sub-region", items=_sub_items)
    time: EnumProperty(
        name="Time of day",
        items=[(t, t, "Which Lights folder to read") for t in region.TIMES],
    )
    terrain: BoolProperty(name="Ground", default=True)
    scenery: BoolProperty(name="Scenery", default=True)
    item: BoolProperty(name="Items", default=True)
    character: BoolProperty(name="Characters", default=True)
    light: BoolProperty(name="Lights", default=True)
    tree: BoolProperty(name="Trees", default=True)
    trigger: BoolProperty(name="Triggers", default=False)
    vegetation: BoolProperty(name="Vegetation library", default=False)

    def invoke(self, context, event):
        if not _game_root(context):
            self.report({"ERROR"}, "Set the Divinity II install path in Preferences")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "region_name")
        layout.prop(self, "sub")
        layout.prop(self, "time")
        grid = layout.grid_flow(columns=2, even_columns=True)
        for kind in KINDS:
            grid.prop(self, kind)

    def execute(self, context):
        chosen = tuple(k for k in KINDS if getattr(self, k))
        built = import_region(
            _game_root(context), self.region_name, self.sub, self.time, chosen
        )
        for failure in built.failed[:5]:
            self.report({"WARNING"}, failure)
        parts = ", ".join(f"{v} {k}" for k, v in built.counts.items())
        self.report(
            {"INFO"},
            f"{self.region_name}/{self.sub}: {parts or 'nothing'} "
            f"from {built.models} models, {built.unresolved} unresolved",
        )
        return {"FINISHED"}


class DV2_PT_panel(Panel):
    bl_label = "Divinity II"
    bl_idname = "DV2_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Divinity II"

    def draw(self, context):
        layout = self.layout
        if not _game_root(context):
            layout.label(text="Set the install path in Preferences", icon="ERROR")
            return
        layout.operator(DV2_OT_import_asset.bl_idname, icon="OUTLINER_OB_ARMATURE")
        layout.operator(DV2_OT_import_region.bl_idname, icon="WORLD")


def _menu(self, context):
    self.layout.operator(DV2_OT_import_asset.bl_idname, text="Divinity II asset")
    self.layout.operator(DV2_OT_import_region.bl_idname, text="Divinity II region")


_classes = (DV2_AddonPreferences, DV2_OT_import_asset,
            DV2_OT_import_region, DV2_PT_panel)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(_menu)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(_menu)
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
