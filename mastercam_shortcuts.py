"""Non-destructive Mastercam-inspired shortcut layer for FabexCNC.

Blender's native G/R/S remain untouched. Fabex commands use Shift+Alt
combinations to minimize collisions with Blender and existing Fabex shortcuts.
"""

import bpy

_KEYMAPS = []


def _add(km, idname, key, *, shift=False, ctrl=False, alt=False):
    item = km.keymap_items.new(idname, key, 'PRESS', shift=shift, ctrl=ctrl, alt=alt)
    _KEYMAPS.append((km, item))


def register():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        return
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    # WCS / origin
    _add(km, 'mcw.cursor_selected', 'C', shift=True, alt=True)
    _add(km, 'mcw.cursor_world', 'W', shift=True, alt=True)
    _add(km, 'mcw.origin_cursor', 'O', shift=True, alt=True)
    _add(km, 'mcw.set_wcs', 'W', shift=True, ctrl=True, alt=True)
    # CAM execution
    _add(km, 'mcw.operation_calculate', 'C', shift=True, ctrl=True)
    _add(km, 'mcw.operation_verify', 'V', shift=True, ctrl=True)
    _add(km, 'mcw.operation_export', 'P', shift=True, ctrl=True)
    # View / gnomon
    _add(km, 'mcw.update_gnomon', 'G', shift=True, alt=True)


def unregister():
    for km, item in reversed(_KEYMAPS):
        try:
            km.keymap_items.remove(item)
        except Exception:
            pass
    _KEYMAPS.clear()
