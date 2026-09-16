# =====================================================================
#  mcam_ui.py — Mastercam-style UI layer for BlenderCAM
#  Put this file INSIDE the BlenderCAM addon folder and hook up
#  registration in its __init__.py (see instructions below).
# =====================================================================

import bpy
from bpy.props import (StringProperty, IntProperty, FloatProperty,
                       EnumProperty, BoolProperty, CollectionProperty)
from bpy.types import Panel, UIList, Operator, PropertyGroup

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def get_active_op(context):
    scene = context.scene
    ops = getattr(scene, "cam_operations", None)
    if not ops or not len(ops):
        return None
    i = min(max(scene.cam_active_operation, 0), len(ops) - 1)
    return ops[i]

def draw_safe(layout, ob, attr, text=None, **kw):
    """Draw a property only if it exists in this BlenderCAM version."""
    try:
        rna = ob.bl_rna.properties[attr]
    except KeyError:
        return
    if rna.is_readonly:
        return
    layout.prop(ob, attr, text=text, **kw)

def blendercam_present(context):
    return hasattr(context.scene, "cam_operations")

# ---------------------------------------------------------------------
# Tool Library (Mastercam-style)
# ---------------------------------------------------------------------

# map our tool types -> BlenderCAM cutter_type enum values
CUTTER_MAP = {
    'END': 'END', 'BALLNOSE': 'BALL', 'BULLNOSE': 'BULLNOSE',
    'VBIT': 'VBIT', 'DRILL': 'DRILL',
}

class MCAM_Tool(PropertyGroup):
    name: StringProperty(name="Name", default="New Tool")
    number: IntProperty(name="Tool #", min=1, default=1)
    bc_type: EnumProperty(name="Type", default='END', items=[
        ('END', "Flat End Mill", ""),
        ('BALLNOSE', "Ball Nose", ""),
        ('BULLNOSE', "Bull Nose", ""),
        ('VBIT', "V-Bit / Engraver", ""),
        ('DRILL', "Drill", "")])
    diameter: FloatProperty(name="Diameter", default=0.006, min=0.0,
                            subtype='DISTANCE')  # metres (BlenderCAM unit)
    flutes: IntProperty(name="Flutes", min=1, default=2)
    tip_angle: FloatProperty(name="Tip Angle (deg)", default=30.0, min=0.0, max=180.0)
    feed: FloatProperty(name="Feed XY", default=600.0, min=0.0)
    plunge: FloatProperty(name="Plunge", default=150.0, min=0.0)
    rpm: IntProperty(name="Spindle RPM", default=12000, min=0)
    notes: StringProperty(name="Notes")

class MCAM_UL_tools(UIList):
    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "name", text="", emboss=False, icon='MESH_CYLINDER')
            sub = row.row(align=True)
            sub.alignment = 'RIGHT'
            sub.scale_x = 0.35
            sub.label(text=f"#{item.number}  D{item.diameter * 1000:g}")

class MCAM_OT_tool_add(Operator):
    bl_idname = "mcam.tool_add"
    bl_label = "Add Tool"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        s = context.scene
        t = s.mcam_tools.add()
        t.name = f"T{len(s.mcam_tools):02d} End Mill"
        t.number = len(s.mcam_tools)
        s.mcam_active_tool = len(s.mcam_tools) - 1
        return {'FINISHED'}

class MCAM_OT_tool_remove(Operator):
    bl_idname = "mcam.tool_remove"
    bl_label = "Remove Tool"
    def execute(self, context):
        s = context.scene
        i = s.mcam_active_tool
        if 0 <= i < len(s.mcam_tools):
            s.mcam_tools.remove(i)
            s.mcam_active_tool = min(i, len(s.mcam_tools) - 1)
        return {'FINISHED'}

class MCAM_OT_apply_tool(Operator):
    """Copy selected library tool into the active operation"""
    bl_idname = "mcam.apply_tool"
    bl_label = "Apply Tool To Operation"
    def execute(self, context):
        s = context.scene
        op = get_active_op(context)
        if op is None or not len(s.mcam_tools):
            self.report({'WARNING'}, "Need an operation and a library tool")
            return {'CANCELLED'}
        t = s.mcam_tools[s.mcam_active_tool]
        mapping = {"cutter_type": CUTTER_MAP.get(t.bc_type, 'END'),
                   "cutter_diameter": t.diameter, "cutter_flutes": t.flutes,
                   "cutter_tip_angle": t.tip_angle, "feedrate": t.feed,
                   "plunge_feedrate": t.plunge, "spindle_rpm": t.rpm}
        for attr, val in mapping.items():
            if hasattr(op, attr):
                try:
                    setattr(op, attr, val)
                except (TypeError, ValueError):
                    pass
        self.report({'INFO'}, f"Applied '{t.name}' to '{op.name}'")
        return {'FINISHED'}

# ---------------------------------------------------------------------
# Operations manager operators
# ---------------------------------------------------------------------

class MCAM_OT_op_add(Operator):
    bl_idname = "mcam.op_add"
    bl_label = "Add Toolpath"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        try:  # prefer BlenderCAM's own operator (keeps defaults consistent)
            bpy.ops.scene.cam_operation_add()
            return {'FINISHED'}
        except Exception:
            pass
        s = context.scene
        op = s.cam_operations.add()
        op.name = f"Toolpath {len(s.cam_operations)}"
        s.cam_active_operation = len(s.cam_operations) - 1
        return {'FINISHED'}

class MCAM_OT_op_remove(Operator):
    bl_idname = "mcam.op_remove"
    bl_label = "Remove Toolpath"
    def execute(self, context):
        try:
            bpy.ops.scene.cam_operation_delete()
            return {'FINISHED'}
        except Exception:
            pass
        s = context.scene
        i = s.cam_active_operation
        if 0 <= i < len(s.cam_operations):
            s.cam_operations.remove(i)
            s.cam_active_operation = min(i, len(s.cam_operations) - 1)
        return {'FINISHED'}

class MCAM_OT_op_copy(Operator):
    bl_idname = "mcam.op_copy"
    bl_label = "Copy Toolpath"
    def execute(self, context):
        try:
            bpy.ops.scene.cam_operation_copy()
            return {'FINISHED'}
        except Exception:
            pass
        s, i = context.scene, context.scene.cam_active_operation
        ops = s.cam_operations
        if not 0 <= i < len(ops):
            return {'CANCELLED'}
        src = ops[i]
        new = ops.add()
        for p in src.bl_rna.properties:
            if p.is_readonly or p.identifier.startswith("bl_"):
                continue
            try:
                setattr(new, p.identifier, getattr(src, p.identifier))
            except Exception:
                pass
        new.name = src.name + ".copy"
        s.cam_active_operation = len(ops) - 1
        return {'FINISHED'}

class MCAM_OT_op_move(Operator):
    bl_idname = "mcam.op_move"
    bl_label = "Reorder Toolpath"
    direction: EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])
    def execute(self, context):
        s = context.scene
        i = s.cam_active_operation
        j = i - 1 if self.direction == 'UP' else i + 1
        if 0 <= j < len(s.cam_operations):
            s.cam_operations.move(i, j)
            s.cam_active_operation = j
        return {'FINISHED'}

def _call_first(context, candidates):
    for idname in candidates:
        mod, name = idname.split('.')
        try:
            getattr(getattr(bpy.ops, mod), name)()
            return True
        except Exception:
            continue
    return False

class MCAM_OT_calculate(Operator):
    bl_idname = "mcam.calculate"
    bl_label = "Calculate"
    def execute(self, context):
        if _call_first(context, ("object.calculate_cam_paths", "object.cam_calculate")):
            return {'FINISHED'}
        self.report({'ERROR'}, "BlenderCAM calculate operator not found")
        return {'CANCELLED'}

class MCAM_OT_simulate(Operator):
    bl_idname = "mcam.simulate"
    bl_label = "Verify"
    def execute(self, context):
        if _call_first(context, ("object.cam_simulate",)):
            return {'FINISHED'}
        self.report({'ERROR'}, "BlenderCAM simulate operator not found")
        return {'CANCELLED'}

class MCAM_OT_export(Operator):
    bl_idname = "mcam.export"
    bl_label = "Export G-Code"
    def execute(self, context):
        if _call_first(context, ("object.cam_export",)):
            return {'FINISHED'}
        self.report({'ERROR'}, "BlenderCAM export operator not found")
        return {'CANCELLED'}

# ---------------------------------------------------------------------
# Shared parameter sections (used by panels + popup dialog)
# ---------------------------------------------------------------------

def _draw_tool_section(layout, op):
    draw_safe(layout, op, "cutter_type", text="Type")
    draw_safe(layout, op, "cutter_diameter", text="Diameter")
    draw_safe(layout, op, "cutter_flutes", text="Flutes")
    draw_safe(layout, op, "cutter_tip_angle", text="Tip Angle")
    layout.label(text="Feeds & Speeds")
    draw_safe(layout, op, "feedrate")
    draw_safe(layout, op, "plunge_feedrate")
    draw_safe(layout, op, "spindle_rpm")
    draw_safe(layout, op, "spindle_rotation")

def _draw_cut_section(layout, op):
    draw_safe(layout, op, "movement", text="Cutting Method")
    draw_safe(layout, op, "movement_type", text="Cut Direction")
    draw_safe(layout, op, "skin", text="Stock To Leave (Z)")
    draw_safe(layout, op, "use_layers", text="Depth Cuts")
    draw_safe(layout, op, "stepdown", text="Max Rough Stepdown")
    draw_safe(layout, op, "first_down")
    draw_safe(layout, op, "distance", text="Stepover")
    draw_safe(layout, op, "distance_between_paths")
    draw_safe(layout, op, "distance_along_paths")
    draw_safe(layout, op, "parallel_step_back")

def _draw_link_section(layout, op):
    draw_safe(layout, op, "safety_height", text="Safety Height")
    draw_safe(layout, op, "clearance_height", text="Clearance Height")
    draw_safe(layout, op, "free_movement_height", text="Retract Height")
    draw_safe(layout, op, "min_z", text="Depth (Z bottom)")

def _draw_stock_section(layout, op):
    draw_safe(layout, op, "material_from_model", text="Stock From Model")
    draw_safe(layout, op, "material_radius_around_model", text="Stock On XY")
    draw_safe(layout, op, "material_size_x", text="Size X")
    draw_safe(layout, op, "material_size_y", text="Size Y")
    draw_safe(layout, op, "material_size_z", text="Size Z")
    draw_safe(layout, op, "material_center_x")
    draw_safe(layout, op, "material_center_y")
    draw_safe(layout, op, "material_center_z")

class MCAM_OT_op_params(Operator):
    """Mastercam-style parameter dialog for the active operation"""
    bl_idname = "mcam.op_params"
    bl_label = "Toolpath Parameters"
    def invoke(self, context, event):
        if get_active_op(context) is None:
            self.report({'WARNING'}, "No active toolpath operation")
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=430)
    def draw(self, context):
        op = get_active_op(context)
        for title, fn in (("Tool", _draw_tool_section),
                          ("Cut Parameters", _draw_cut_section),
                          ("Linking Parameters", _draw_link_section)):
            box = self.layout.box()
            box.label(text=title)
            fn(box, op)
    def execute(self, context):
        return {'FINISHED'}

class MCAM_OT_setup_sheet(Operator):
    bl_idname = "mcam.setup_sheet"
    bl_label = "Generate Setup Sheet"
    def execute(self, context):
        scene = context.scene
        txt = bpy.data.texts.get("MCAM_SetupSheet") or bpy.data.texts.new("MCAM_SetupSheet")
        txt.clear()
        txt.write("SETUP SHEET\n" + "=" * 60 + "\n")
        m = getattr(scene, "cam_machine", None)
        if m:
            txt.write(f"Machine post : {getattr(m, 'post_processor', '?')}\n\n")
        for i, op in enumerate(scene.cam_operations):
            txt.write(f"Operation {i + 1}: {op.name}\n")
            txt.write(f"  Type    : {getattr(op, 'strategy', '?')}\n")
            if hasattr(op, 'cutter_diameter'):
                txt.write(f"  Tool    : {getattr(op, 'cutter_type', '')}  "
                          f"D={op.cutter_diameter * 1000:g}mm  "
                          f"Flutes={getattr(op, 'cutter_flutes', '?')}\n")
                txt.write(f"  Feeds   : XY={op.feedrate:g}  "
                          f"Plunge={op.plunge_feedrate:g}  "
                          f"RPM={op.spindle_rpm}\n")
            txt.write(f"  Safety  : {getattr(op, 'safety_height', 0) * 1000:g}mm  "
                      f"Depth={getattr(op, 'min_z', 0) * 1000:g}mm\n")
            txt.write(f"  NC file : {getattr(op, 'filename', '')}\n\n")
        self.report({'INFO'}, "Setup sheet created: Text Editor > MCAM_SetupSheet")
        return {'FINISHED'}

# ---------------------------------------------------------------------
# UI Lists / Panels
# ---------------------------------------------------------------------

class MCAM_UL_ops(UIList):
    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            st = 'CHECKMARK'
            if getattr(item, 'computing', False):
                st = 'FILE_REFRESH'
            elif not getattr(item, 'valid', True):
                st = 'ERROR'
            row = layout.row(align=True)
            row.prop(item, "name", text="", emboss=False, icon=st)
            sub = row.row()
            sub.scale_x = 0.5
            sub.alignment = 'RIGHT'
            strat = getattr(item, 'strategy', '')
            sub.label(text=strat.replace('_', ' ').title()[:16])

class MCAM_PT_ribbon(Panel):
    bl_label = "MasterCAM"
    bl_idname = "MCAM_PT_ribbon"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    bl_options = {'HIDE_HEADER'}
    def draw(self, context):
        row = self.layout.row(align=True)
        row.scale_y = 1.3
        row.prop(context.scene, "mcam_ui_tab", expand=True)

class MCAM_PT_no_blendercam(Panel):
    bl_label = "BlenderCAM not found"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    @classmethod
    def poll(cls, context):
        return not blendercam_present(context)
    def draw(self, context):
        self.layout.label(text="Enable the BlenderCAM addon first.", icon='ERROR')

def _tab_poll(tab):
    def poll(cls, context):
        return blendercam_present(context) and context.scene.mcam_ui_tab == tab
    return classmethod(poll)

class MCAM_PT_home(Panel):
    bl_label = "Home"
    bl_parent_id = "MCAM_PT_ribbon"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    poll = _tab_poll('HOME')
    def draw(self, context):
        l = self.layout
        col = l.column(align=True)
        col.operator("mcam.op_add", icon='ADD')
        col.operator("mcam.calculate", icon='FILE_TICK')
        col.operator("mcam.simulate", icon='PLAY')
        col.operator("mcam.export", icon='EXPORT')
        col.operator("mcam.setup_sheet", icon='TEXT')

class MCAM_PT_operations(Panel):
    bl_label = "Toolpath Manager"
    bl_parent_id = "MCAM_PT_ribbon"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    poll = _tab_poll('TOOLPATHS')
    def draw(self, context):
        s, l = context.scene, self.layout
        op = get_active_op(context)
        row = l.row()
        row.template_list("MCAM_UL_ops", "", s, "cam_operations",
                          s, "cam_active_operation")
        col = row.column(align=True)
        col.operator("mcam.op_add", text="", icon='ADD')
        col.operator("mcam.op_remove", text="", icon='REMOVE')
        col.operator("mcam.op_copy", text="", icon='DUPLICATE')
        col.separator()
        col.operator("mcam.op_move", text="", icon='TRIA_UP').direction = 'UP'
        col.operator("mcam.op_move", text="", icon='TRIA_DOWN').direction = 'DOWN'
        if op:
            box = l.box()
            box.prop(op, "name", text="")
            draw_safe(box, op, "strategy", text="Toolpath Type")
            draw_safe(box, op, "path_object_name", text="NC Name")
            row = box.row(align=True)
            row.operator("mcam.calculate", text="Calculate", icon='FILE_TICK')
            row.operator("mcam.simulate", text="Verify", icon='PLAY')
            row.operator("mcam.export", text="G-Code", icon='EXPORT')
            l.operator("mcam.op_params", icon='PROPERTIES')

class MCAM_PT_geometry(Panel):
    bl_label = "Geometry (Chains)"
    bl_parent_id = "MCAM_PT_ribbon"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    bl_options = {'DEFAULT_CLOSED'}
    poll = _tab_poll('TOOLPATHS')
    def draw(self, context):
        op = get_active_op(context)
        if not op:
            return
        box = self.layout.box()
        draw_safe(box, op, "geometry_source")
        src = getattr(op, "geometry_source", "")
        if src == 'OBJECT':
            draw_safe(box, op, "object", text="Model Object")
        elif src == 'COLLECTION':
            draw_safe(box, op, "collection", text="Model Collection")
        elif src == 'IMAGE':
            draw_safe(box, op, "image", text="Heightmap Image")
        draw_safe(box, op, "curve_object", text="Chain 1 (Curve)")
        draw_safe(box, op, "curve_object2", text="Chain 2 (Curve)")

class MCAM_PT_tool(Panel):
    bl_label = "Tool"
    bl_parent_id = "MCAM_PT_ribbon"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    poll = _tab_poll('TOOLPATHS')
    def draw(self, context):
        op = get_active_op(context)
        if op:
            box = self.layout.box()
            _draw_tool_section(box, op)

class MCAM_PT_cut(Panel):
    bl_label = "Cut Parameters"
    bl_parent_id = "MCAM_PT_ribbon"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    bl_options = {'DEFAULT_CLOSED'}
    poll = _tab_poll('TOOLPATHS')
    def draw(self, context):
        op = get_active_op(context)
        if op:
            _draw_cut_section(self.layout.box(), op)

class MCAM_PT_linking(Panel):
    bl_label = "Linking Parameters"
    bl_parent_id = "MCAM_PT_ribbon"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    bl_options = {'DEFAULT_CLOSED'}
    poll = _tab_poll('TOOLPATHS')
    def draw(self, context):
        op = get_active_op(context)
        if op:
            _draw_link_section(self.layout.box(), op)

DRAWN = {"name", "strategy", "path_object_name", "geometry_source", "object",
         "collection", "image", "curve_object", "curve_object2", "cutter_type",
         "cutter_diameter", "cutter_flutes", "cutter_tip_angle", "feedrate",
         "plunge_feedrate", "spindle_rpm", "spindle_rotation", "movement",
         "movement_type", "skin", "use_layers", "stepdown", "first_down",
         "distance", "distance_between_paths", "distance_along_paths",
         "parallel_step_back", "safety_height", "clearance_height",
         "free_movement_height", "min_z", "material_from_model",
         "material_radius_around_model", "material_size_x", "material_size_y",
         "material_size_z", "material_center_x", "material_center_y",
         "material_center_z", "computing", "computing_index", "valid",
         "filename", "geometry_source"}

class MCAM_PT_advanced(Panel):
    bl_label = "All Other Parameters"
    bl_parent_id = "MCAM_PT_ribbon"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    bl_options = {'DEFAULT_CLOSED'}
    poll = _tab_poll('TOOLPATHS')
    def draw_header(self, context):
        self.layout.prop(context.scene, "mcam_show_advanced", text="")
    def draw(self, context):
        op = get_active_op(context)
        if not op or not context.scene.mcam_show_advanced:
            return
        col = self.layout.column(align=True)
        for p in op.bl_rna.properties:
            if p.identifier in DRAWN or p.is_readonly or p.identifier.startswith("bl_"):
                continue
            try:
                col.prop(op, p.identifier)
            except Exception:
                pass

class MCAM_PT_verify(Panel):
    bl_label = "Verify (Simulation)"
    bl_parent_id = "MCAM_PT_ribbon"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    poll = _tab_poll('VERIFY')
    def draw(self, context):
        l = self.layout
        col = l.column(align=True)
        col.operator("mcam.simulate", icon='PLAY')
        col.label(text="Detailed sim settings:")
        col.label(text="use BlenderCAM's own CAM tab", icon='INFO')

class MCAM_PT_stock(Panel):
    bl_label = "Stock Setup"
    bl_parent_id = "MCAM_PT_ribbon"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    poll = _tab_poll('MACHINE')
    def draw(self, context):
        op = get_active_op(context)
        if op:
            _draw_stock_section(self.layout.box(), op)

class MCAM_PT_tool_library(Panel):
    bl_label = "Tool Library"
    bl_parent_id = "MCAM_PT_ribbon"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    poll = _tab_poll('MACHINE')
    def draw(self, context):
        s, l = context.scene, self.layout
        row = l.row()
        row.template_list("MCAM_UL_tools", "", s, "mcam_tools",
                          s, "mcam_active_tool")
        col = row.column(align=True)
        col.operator("mcam.tool_add", text="", icon='ADD')
        col.operator("mcam.tool_remove", text="", icon='REMOVE')
        if len(s.mcam_tools):
            t = s.mcam_tools[s.mcam_active_tool]
            box = l.box()
            box.prop(t, "bc_type")
            box.prop(t, "diameter")
            box.prop(t, "flutes")
            box.prop(t, "tip_angle")
            box.prop(t, "feed")
            box.prop(t, "plunge")
            box.prop(t, "rpm")
            l.operator("mcam.apply_tool", icon='CHECKMARK')

class MCAM_PT_machine(Panel):
    bl_label = "Machine Definition"
    bl_parent_id = "MCAM_PT_ribbon"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MasterCAM"
    poll = _tab_poll('MACHINE')
    def draw(self, context):
        m = getattr(context.scene, "cam_machine", None)
        if not m:
            self.layout.label(text="No machine settings found", icon='ERROR')
            return
        box = self.layout.box()
        for attr in ("post_processor", "working_area", "feedrate_min",
                     "feedrate_max", "spindle_min", "spindle_max", "axis4", "axis5"):
            draw_safe(box, m, attr)

# ---------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------

classes = (
    MCAM_Tool,
    MCAM_UL_tools, MCAM_UL_ops,
    MCAM_OT_tool_add, MCAM_OT_tool_remove, MCAM_OT_apply_tool,
    MCAM_OT_op_add, MCAM_OT_op_remove, MCAM_OT_op_copy, MCAM_OT_op_move,
    MCAM_OT_calculate, MCAM_OT_simulate, MCAM_OT_export,
    MCAM_OT_op_params, MCAM_OT_setup_sheet,
    MCAM_PT_ribbon, MCAM_PT_no_blendercam,
    MCAM_PT_home, MCAM_PT_operations, MCAM_PT_geometry, MCAM_PT_tool,
    MCAM_PT_cut, MCAM_PT_linking, MCAM_PT_advanced, MCAM_PT_verify,
    MCAM_PT_stock, MCAM_PT_tool_library, MCAM_PT_machine,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.mcam_ui_tab = EnumProperty(name="Ribbon Tab", default='TOOLPATHS',
        items=[('HOME', "Home", ""),
               ('TOOLPATHS', "Toolpaths", ""),
               ('VERIFY', "Verify", ""),
               ('MACHINE', "Machine", "")])
    bpy.types.Scene.mcam_tools = CollectionProperty(type=MCAM_Tool, name="Tool Library")
    bpy.types.Scene.mcam_active_tool = IntProperty(default=0)
    bpy.types.Scene.mcam_show_advanced = BoolProperty(default=False)

def unregister():
    del bpy.types.Scene.mcam_ui_tab
    del bpy.types.Scene.mcam_tools
    del bpy.types.Scene.mcam_active_tool
    del bpy.types.Scene.mcam_show_advanced
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()
