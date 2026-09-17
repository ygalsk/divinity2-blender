"""Divinity II assets in Blender.

Registration only. The work is in `divinity2` (the game's files), `blender`
(turning them into Blender data) and `ui` (the two import operators).
"""

from . import ui


def register():
    ui.register()


def unregister():
    ui.unregister()
