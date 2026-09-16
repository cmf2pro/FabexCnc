"""Mastercam-style UX layer for FabexCNC.

This module intentionally stays compatibility-first: it does not replace Fabex's
CAM engine. It provides a CNC mill oriented UI, coordinate/origin tools, a 3D
machine gnomon, operation navigation and configurable shortcuts around the
existing Fabex properties/operators.
"""

import bpy
from mathutils import Matrix, Vector
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup


def _active_op(context):
    scene = context.scene
    ops = getattr(scene, "cam_operations", None)
    if not ops:
        return None
    index = getattr(scene, "mcw_active_operation", 0)
    if index < 0 or index >= len(ops):
        return None
    return ops[index]


def _prop(layout, obj, name, label=None):
    if obj is None or not hasattr(obj, name):
        return False
    try:
        if obj.bl_rna.properties[name].is_readonly:
            return False
    except Exception:
        pass
    layout.prop(obj, name, text=label or name.replace("_", " ").title())
    return True


class MCW_Settings(PropertyGroup):
    mode: EnumProperty(
        name="UI Mode",
        items=[
            ("MILL", "Mill", "CNC milling workspace"),
            ("CAM", "CAM", "Full CAM workspace"),
            ("SETUP", "Setup", "Machine and stock setup"),
        ],
        default="MILL",
    )
    parameter_page: EnumProperty(
        name="Parameter Page",
        items=[
            ("TOOL", "Tool", "Tool and feeds/speeds"),
            ("GEOMETRY", "Geometry", "Geometry and containment"),
            ("CUT", "Cut Parameters", "Cutting parameters"),
            ("LINK", "Linking", "Linking and clearance"),
            ("ENTRY", "Entry / Exit", "Entry and exit motion"),
            ("ROUGH", "Roughing", "Roughing controls"),
            ("FINISH", "Finishing", "Finishing controls"),
            ("TOL", "Tolerances", "Tolerance and filtering"),
        ],
        default="TOOL",
    )
    show_gnomon: BoolProperty(name="3D Gnomon", default=True)
    gnomon_size: FloatProperty(name="Gnomon Size", default=25.0, min=1.0, max=500.0)
    work_offset: IntProperty(name="Work Offset", default=54, min=54, max=59)
    origin_mode: EnumProperty(
        name="Origin",
        items=[
            ("CURSOR", "3D Cursor", "Use Blender's 3D cursor"),
            ("WORLD", "World", "Use world origin"),
            ("ACTIVE", "Active Object", "Use active object's origin"),
        ],
        default="CURSOR",
    )


# ---------------------------- Coordinate / Origin ----------------------------

class MCW_OT_origin_cursor(Operator):
    bl_idname = "mcw.origin_cursor"
    bl_label = "Move Origin to Cursor"
    bl_description = "Move the active object's origin to the 3D cursor without changing its geometry"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            self.report({"WARNING"}, "Select an object first")
            return {"CANCELLED"}
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
        return {"FINISHED"}


class MCW_OT_cursor_selected(Operator):
    bl_idname = "mcw.cursor_selected"
    bl_label = "Set Origin / Cursor to Selection"
    bl_description = "Place the 3D cursor at the active selection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.active_object is None:
            self.report({"WARNING"}, "Select an object first")
            return {"CANCELLED"}
        bpy.ops.view3d.snap_cursor_to_selected()
        return {"FINISHED"}


class MCW_OT_cursor_world(Operator):
    bl_idname = "mcw.cursor_world"
    bl_label = "World Origin"
    bl_description = "Reset the 3D cursor to X0 Y0 Z0"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        context.scene.cursor.location = (0.0, 0.0, 0.0)
        context.scene.cursor.rotation_euler = (0.0, 0.0, 0.0)
        return {"FINISHED"}


class MCW_OT_set_wcs(Operator):
    bl_idname = "mcw.set_wcs"
    bl_label = "Set WCS from View"
    bl_description = "Align the cursor orientation to the active view and use it as the CAM work coordinate system"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        region_data = getattr(context, "region_data", None)
        if region_data is None:
            self.report({"WARNING"}, "Run this command from a 3D View")
            return {"CANCELLED"}
        q = region_data.view_rotation
        context.scene.cursor.rotation_mode = "QUATERNION"
        context.scene.cursor.rotation_quaternion = q
        return {"FINISHED"}


# ------------------------------- Gnomon --------------------------------------

_GNOMON_COLLECTION = "MCAM_GNOMON"


def _ensure_gnomon(context):
    scene = context.scene
    coll = bpy.data.collections.get(_GNOMON_COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(_GNOMON_COLLECTION)
        scene.collection.children.link(coll)

    root = bpy.data.objects.get("MCAM_Gnomon")
    if root is None:
        root = bpy.data.objects.new("MCAM_Gnomon", None)
        coll.objects.link(root)
    root.location = scene.cursor.location
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = scene.cursor.rotation_quaternion if scene.cursor.rotation_mode == "QUATERNION" else scene.cursor.rotation_euler.to_quaternion()
    root.empty_display_type = "ARROWS"
    root.empty_display_size = scene.mcw.gnomon_size / 100.0
    root.color[3] = 0.0
    root.hide_render = True
    root.hide_viewport = not scene.mcw.show_gnomon
    return root


class MCW_OT_update_gnomon(Operator):
    bl_idname = "mcw.update_gnomon"
    bl_label = "Update 3D Gnomon"
    bl_description = "Place the CNC X/Y/Z gnomon at the active work origin"

    def execute(self, context):
        _ensure_gnomon(context)
        return {"FINISHED"}


class MCW_OT_delete_gnomon(Operator):
    bl_idname = "mcw.delete_gnomon"
    bl_label = "Remove Gnomon"

    def execute(self, context):
        obj = bpy.data.objects.get("MCAM_Gnomon")
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)
        return {"FINISHED"}


# ---------------------------- Operation controls -----------------------------

class MCW_OT_operation_select(Operator):
    bl_idname = "mcw.operation_select"
    bl_label = "Select Operation"
    index: IntProperty(default=0)

    def execute(self, context):
        context.scene.mcw_active_operation = self.index
        context.scene.mcw.parameter_page = "TOOL"
        return {"FINISHED"}


class MCW_OT_operation_calculate(Operator):
    bl_idname = "mcw.operation_calculate"
    bl_label = "Calculate Toolpath"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        candidates = (
            "object.calculate_cam_paths",
            "object.cam_calculate",
            "scene.cam_calculate",
        )
        for path in candidates:
            mod, name = path.split(".")
            try:
                getattr(getattr(bpy.ops, mod), name)()
                return {"FINISHED"}
            except Exception:
                continue
        self.report({"ERROR"}, "Fabex calculate operator was not found")
        return {"CANCELLED"}


class MCW_OT_operation_verify(Operator):
    bl_idname = "mcw.operation_verify"
    bl_label = "Verify / Simulate"

    def execute(self, context):
        for path in ("object.cam_simulate", "object.cam_simulation"):
            mod, name = path.split(".")
            try:
                getattr(getattr(bpy.ops, mod), name)()
                return {"FINISHED"}
            except Exception:
                continue
        self.report({"ERROR"}, "Fabex simulation operator was not found")
        return {"CANCELLED"}


class MCW_OT_operation_export(Operator):
    bl_idname = "mcw.operation_export"
    bl_label = "Post / Export NC"

    def execute(self, context):
        for path in ("object.cam_export", "scene.cam_export"):
            mod, name = path.split(".")
            try:
                getattr(getattr(bpy.ops, mod), name)()
                return {"FINISHED"}
            except Exception:
                continue
        self.report({"ERROR"}, "Fabex export operator was not found")
        return {"CANCELLED"}


# -------------------------------- UI panels ----------------------------------

class MCW_PT_ribbon(Panel):
    bl_idname = "MCW_PT_ribbon"
    bl_label = "FABEX CNC | MASTER MILL"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MasterCAM"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        layout = self.layout
        s = context.scene
        box = layout.box()
        row = box.row(align=True)
        row.label(text="FABEX CNC", icon="MODIFIER")
        row.label(text="MASTER MILL")
        row = box.row(align=True)
        row.prop(s.mcw, "mode", expand=True)
        row = box.row(align=True)
        for p, label in (("TOOL", "Tool"), ("GEOMETRY", "Geometry"), ("CUT", "Cut"), ("LINK", "Link"), ("ENTRY", "Entry"), ("ROUGH", "Rough"), ("FINISH", "Finish"), ("TOL", "Tol")):
            op = row.operator("wm.context_set_enum", text=label)
            op.data_path = "scene.mcw.parameter_page"
            op.value = p

        ops = getattr(s, "cam_operations", None)
        if ops:
            box = layout.box()
            box.label(text="Toolpath Manager", icon="OUTLINER_OB_CURVE")
            for i, op_data in enumerate(ops):
                r = box.row(align=True)
                r.alert = i == getattr(s, "mcw_active_operation", 0)
                cmd = r.operator("mcw.operation_select", text=f"OP{i + 1:02d}  {getattr(op_data, 'name', 'Operation')}")
                cmd.index = i
                r.label(text=str(getattr(op_data, "strategy", "CAM")).replace("_", " ").title())

        box = layout.box()
        box.label(text="Active Toolpath Parameters", icon="PROPERTIES")
        op = _active_op(context)
        page = s.mcw.parameter_page
        if op is None:
            box.label(text="No CAM operation selected")
        elif page == "TOOL":
            for n in ("cutter_type", "cutter_diameter", "cutter_flutes", "feedrate", "plunge_feedrate", "spindle_rpm"):
                _prop(box, op, n)
        elif page == "GEOMETRY":
            for n in ("object_name", "source_object", "curve_object", "ambient_radius", "material_radius_around_model"):
                _prop(box, op, n)
        elif page == "CUT":
            for n in ("strategy", "movement", "movement_type", "min_z", "max_z", "stepdown", "distance", "distance_between_paths", "skin"):
                _prop(box, op, n)
        elif page == "LINK":
            for n in ("safety_height", "clearance_height", "free_movement_height", "use_3d"):
                _prop(box, op, n)
        elif page == "ENTRY":
            for n in ("ramp", "ramp_in_angle", "helix", "plunge_feedrate", "retract_mode"):
                _prop(box, op, n)
        elif page == "ROUGH":
            for n in ("use_layers", "stepdown", "skin", "protect_vertical", "stay_low", "ambient_radius"):
                _prop(box, op, n)
        elif page == "FINISH":
            for n in ("distance", "distance_along_paths", "distance_between_paths", "protect_vertical", "stay_low"):
                _prop(box, op, n)
        else:
            for n in ("pixsize", "sampling_resolution", "simplify_tol", "path_error", "substep"):
                _prop(box, op, n)

        row = layout.row(align=True)
        row.operator("mcw.operation_calculate", text="Calculate", icon="FILE_REFRESH")
        row.operator("mcw.operation_verify", text="Verify", icon="VIEW3D")
        row.operator("mcw.operation_export", text="Post", icon="EXPORT")

        box = layout.box()
        box.label(text="WCS / Gnomon", icon="ORIENTATION_GIMBAL")
        row = box.row(align=True)
        row.prop(s.mcw, "work_offset")
        row.prop(s.mcw, "show_gnomon")
        row = box.row(align=True)
        row.operator("mcw.cursor_selected", text="Cursor = Selection")
        row.operator("mcw.cursor_world", text="WCS G54")
        row = box.row(align=True)
        row.operator("mcw.origin_cursor", text="Move Origin")
        row.operator("mcw.set_wcs", text="WCS From View")
        row = box.row(align=True)
        row.operator("mcw.update_gnomon", text="Update Gnomon")
        row.operator("mcw.delete_gnomon", text="Remove")


class MCW_PT_machine(Panel):
    bl_idname = "MCW_PT_machine"
    bl_label = "Machine / Stock / WCS"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MasterCAM"

    def draw(self, context):
        l = self.layout
        scene = context.scene
        machine = getattr(scene, "cam_machine", None)
        if machine:
            l.label(text="Machine", icon="MODIFIER")
            for n in ("post_processor", "unit_system", "length_unit", "collet_size", "working_area", "feedrate_min", "feedrate_max", "spindle_min", "spindle_max"):
                _prop(l, machine, n)
        l.separator()
        l.label(text="Stock", icon="CUBE")
        op = _active_op(context)
        for n in ("material_from_model", "material_size_x", "material_size_y", "material_size_z", "material_center_x", "material_center_y", "material_center_z"):
            _prop(l, op, n)
        l.separator()
        l.label(text=f"G{scene.mcw.work_offset} Work Offset")
        l.prop(scene.cursor, "location", text="Origin XYZ")
        l.prop(scene.cursor, "rotation_euler", text="WCS Rotation")


class MCW_PT_toolpath_detail(Panel):
    bl_idname = "MCW_PT_toolpath_detail"
    bl_label = "Detailed Toolpath Parameters"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):
        l = self.layout
        op = _active_op(context)
        if op is None:
            l.label(text="Select a CAM operation in MasterCAM workspace")
            return
        for n in ("strategy", "cutter_type", "cutter_diameter", "cutter_flutes", "feedrate", "plunge_feedrate", "spindle_rpm", "min_z", "max_z", "stepdown", "distance", "safety_height", "clearance_height"):
            _prop(l, op, n)


_CLASSES = (
    MCW_Settings,
    MCW_OT_origin_cursor,
    MCW_OT_cursor_selected,
    MCW_OT_cursor_world,
    MCW_OT_set_wcs,
    MCW_OT_update_gnomon,
    MCW_OT_delete_gnomon,
    MCW_OT_operation_select,
    MCW_OT_operation_calculate,
    MCW_OT_operation_verify,
    MCW_OT_operation_export,
    MCW_PT_ribbon,
    MCW_PT_machine,
    MCW_PT_toolpath_detail,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mcw = bpy.props.PointerProperty(type=MCW_Settings)
    bpy.types.Scene.mcw_active_operation = IntProperty(default=0, min=0)
    _ensure_gnomon(bpy.context)


def unregister():
    obj = bpy.data.objects.get("MCAM_Gnomon")
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)
    if hasattr(bpy.types.Scene, "mcw_active_operation"):
        del bpy.types.Scene.mcw_active_operation
    if hasattr(bpy.types.Scene, "mcw"):
        del bpy.types.Scene.mcw
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
