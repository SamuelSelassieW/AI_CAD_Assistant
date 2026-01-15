# AI CAD Assistant

AI‑powered parametric CAD assistant for FreeCAD + SolidWorks.

- Turn natural language into parametric parts (bolts, gears, flanges, brackets, etc.)
- Generate 3D models in FreeCAD and export to STEP for SolidWorks/Fusion
- Auto‑create simple engineering drawings with TechDraw

> Status: **Beta – Windows only**. Not for safety‑critical use.
>

## Features

- **Text → Model**: describe a part, the app uses helpers like:
  - `make_box`, `make_plate_with_hole`, `make_flange`
  - `make_cyl_with_hole`
  - `make_fasteners_hex_bolt`
  - `make_spur_gear`, `make_helical_gear`, `make_internal_gear`,
    `make_bevel_gear`, `make_worm_gear`
- **Image → Model (experimental)**: basic detection of rectangles / circles.
- **Model → Drawing**: creates a TechDraw page (front/side, overall dims) and saves it.

## Requirements

- Windows 10/11 (64‑bit)
- FreeCAD 1.0 (or 0.21) installed in `C:\Program Files\FreeCAD ...`
- Fasteners workbench installed via FreeCAD Addon Manager
- freecad.gears (Gears workbench) installed via FreeCAD Addon Manager

## Running from source (dev)

```powershell
git clone YOUR_REPO_URL.git
cd AI_CAD_Assistant
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app_gui.py
