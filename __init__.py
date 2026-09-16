"""Fabex '__init__.py' © 2012 Vilem Novak

Import Modules, Register and Unregister Classes.
"""

import subprocess
import sys

import opencamlib
import shapely
import bpy
from bpy.props import CollectionProperty, IntProperty

from .engine import FABEX_ENGINE, get_panels
from .operators import register as ops_register, unregister as ops_unregister
from .properties import register as props_register, unregister as props_unregister
from .properties.operation_props import CAM_OPERATION_Properties
from .preferences import CamAddonPreferences
from .ui import register as ui_register, unregister as ui_unregister
from .ui.icons import register as icons_register, unregister as icons_unregister
from .utilities.addon_utils import (
    on_blender_startup,
    keymap_register,
    keymap_unregister,
)
from .utilities.thread_utils import timer_update

# Legacy Mastercam-style companion UI retained for compatibility.
from . import mcam_ui
# New CNC mill workspace: ribbon, WCS/origin tools, gnomon and parameter pages.
from . import mastercam_workspace

_mcam_created_index = False

classes = (FABEX_ENGINE, CamAddonPreferences)


def register() -> None:
    global _mcam_created_index

    for cls in classes:
        bpy.utils.register_class(cls)

    icons_register()
    props_register()
    ops_register()
    ui_register()
    keymap_register()

    bpy.utils.register_class(CAM_OPERATION_Properties)
    bpy.types.Scene.cam_operations = CollectionProperty(type=CAM_OPERATION_Properties)

    for panel in get_panels():
        panel.COMPAT_ENGINES.add("FABEX_RENDER")

    bpy.app.handlers.frame_change_pre.append(timer_update)
    bpy.app.handlers.load_post.append(on_blender_startup)

    if not hasattr(bpy.types.Scene, "cam_active_operation"):
        bpy.types.Scene.cam_active_operation = IntProperty(default=0)
        _mcam_created_index = True

    mcam_ui.register()
    mastercam_workspace.register()


def unregister() -> None:
    mastercam_workspace.unregister()
    mcam_ui.unregister()

    if _mcam_created_index and hasattr(bpy.types.Scene, "cam_active_operation"):
        del bpy.types.Scene.cam_active_operation

    for cls in classes:
        bpy.utils.unregister_class(cls)

    icons_unregister()
    ui_unregister()
    ops_unregister()
    props_unregister()
    keymap_unregister()

    bpy.utils.unregister_class(CAM_OPERATION_Properties)
    if hasattr(bpy.types.Scene, "cam_operations"):
        del bpy.types.Scene.cam_operations

    for panel in get_panels():
        if "FABEX_RENDER" in panel.COMPAT_ENGINES:
            panel.COMPAT_ENGINES.remove("FABEX_RENDER")

    try:
        bpy.app.handlers.frame_change_pre.remove(timer_update)
    except ValueError:
        pass
    try:
        bpy.app.handlers.load_post.remove(on_blender_startup)
    except ValueError:
        pass


if __name__ == "__package__":
    register()
