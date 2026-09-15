"""The whole interface: one import operator and one panel.

Choose a name, press OK, the asset arrives. No file browser, no preferences
beyond the game's location, no command line.
"""

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.types import AddonPreferences, Operator, Panel

from ..blender.importer import import_character
from ..divinity2 import catalog

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


def _character_items(self, context):
    root = _game_root(context)
    if not root:
        return [("", "Set the install path in Preferences", "")]
    found = catalog.search(root, self.search)
    if not found:
        return [("", "Nothing matches", "")]
    return [(str(a.path), a.name, a.kind) for a in found]


class DV2_OT_import_character(Operator):
    """Import a Divinity II character by name"""

    bl_idname = "divinity2.import_character"
    bl_label = "Divinity II asset"
    bl_options = {"REGISTER", "UNDO"}

    search: StringProperty(name="Name", default="")
    choice: EnumProperty(name="Asset", items=_character_items)

    def invoke(self, context, event):
        if not _game_root(context):
            self.report({"ERROR"}, "Set the Divinity II install path in Preferences")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "search")
        layout.prop(self, "choice")

    def execute(self, context):
        if not self.choice:
            self.report({"ERROR"}, "No asset chosen")
            return {"CANCELLED"}

        result = import_character(self.choice, _game_root(context))
        self.report(
            {"INFO"},
            f"{len(result.objects)} objects, {result.bones} bones, "
            f"{result.skinned} skinned, {result.clips} clips",
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
        layout.operator(DV2_OT_import_character.bl_idname, icon="OUTLINER_OB_ARMATURE")


def _menu(self, context):
    self.layout.operator(DV2_OT_import_character.bl_idname, text="Divinity II asset")


_classes = (DV2_AddonPreferences, DV2_OT_import_character, DV2_PT_panel)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(_menu)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(_menu)
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
