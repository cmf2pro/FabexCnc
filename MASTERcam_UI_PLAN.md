# FabexCNC Mastercam-style UI Roadmap

## Goal
Provide a Mastercam-inspired CNC milling workflow inside Blender/Fabex without copying proprietary Mastercam assets or code.

## Phase 1 — Core workspace
- Dedicated Fabex CNC workspace
- Mastercam-style top command/ribbon organization
- CNC Mill workflow: Geometry, Planes, Toolpaths, Analyze, Transform, Verify, Machine
- Persistent Operations/Toolpaths manager
- Properties/task panel for operation parameters
- CNC coordinate/WCS/Cplane/Tplane concepts exposed clearly

## Phase 2 — Graphics viewport
- CNC origin/WCS manipulator
- Gnomon/axis display
- Top/Front/Right/Isometric view commands
- Fit, pan, zoom and rotate shortcuts
- Move/rotate origin workflow
- Selection filters and machining visibility controls

## Phase 3 — CAM workflow
- Tool library
- Stock/setup definition
- 2D contour/pocket/face/drill operations
- 3D roughing/finishing operations
- Wireframe/chain selection tools
- Operation parameter dialogs
- Toolpath regeneration and visibility controls

## Phase 4 — Verification and output
- Material/stock simulation
- Collision checking
- Toolpath statistics
- G-code editor/viewer
- Post processor selection
- NC output and save workflow

## Phase 5 — Shortcut system
Use Blender's keymap API and Fabex operators for a consistent CNC shortcut layer. Avoid overriding Blender shortcuts globally where conflicts exist.

Initial Mastercam-inspired mapping targets:
- F1: Window Zoom
- F2: Previous/50% view
- F3: Repaint
- F4: Analyze
- F5: Delete/selection action
- F9: Coordinate axes
- Alt+1: Top
- Alt+2: Front
- Alt+3: Back
- Alt+4: Bottom
- Alt+5: Right
- Alt+6: Left
- Alt+7: Isometric
- Alt+F1: Fit geometry
- Alt+F2: Unzoom
- Alt+F9: WCS/Cplane/Tplane axes
- Alt+T: Toggle toolpaths
- Alt+S: Shading toggle

Exact bindings will be implemented through Blender keymaps and made configurable to avoid conflicts.

## Important Blender behavior
Shift+F4 changes the current area to Blender's Console editor. It is not a suitable primary CAM UI. Fabex should provide the Mastercam-style workflow in a dedicated 3D View/Fabex workspace; Shift+F4 can remain available as an optional developer/debug shortcut.

## Safety
The UI should clearly distinguish preview/simulation from machine-ready NC output. No automatic machine execution should be added.
