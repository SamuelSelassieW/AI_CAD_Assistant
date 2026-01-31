import ollama
import re

# All helper functions the model is allowed to use
ALLOWED_HELPERS = [
    "make_box",
    "make_cylinder",
    "make_cyl_with_hole",
    "make_tri_prism",
    "make_plate_with_hole",
    "make_hex_prism",
    "make_hex_nut",
    "make_hex_bolt",
    "make_fasteners_hex_bolt",
    "make_screw_blank",
    "make_slotted_screw",
    "make_cross_screw",
    "make_socket_head_screw",
    "make_flange",
    "make_spur_gear",
    "make_helical_gear",
    "make_internal_gear",
    "make_bevel_gear",
    "make_worm_gear",
    # new structural / shaft helpers
    "make_rect_tube",
    "make_pipe",
    "make_stepped_shaft",
    "make_flat_bar_2holes",
    "make_drum_with_flange",
    "make_shaft_with_keyway",
    "make_plate_with_slot",
    "make_plate_with_pocket",
]

SYSTEM_PROMPT = """
You generate STRICT Python code to build ONE 3D solid using helper functions
from cad_primitives, then display it.

User descriptions may use any capitalization (upper/lower case); treat them the same.

Allowed helper calls (already imported for you):
- make_box(L, W, H)
- make_cylinder(radius, height)
- make_cyl_with_hole(outer_radius, height, hole_radius, hole_depth)
- make_tri_prism(base, height, thickness)
- make_plate_with_hole(L, W, thickness, hole_radius)
- make_hex_prism(flat, thickness)
- make_hex_nut(flat, thickness, hole_radius)
- make_hex_bolt(shaft_radius, shaft_length, head_flat, head_thickness)
- make_fasteners_hex_bolt(size, length_mm)
- make_screw_blank(shaft_diameter, shaft_length, head_diameter, head_height)
- make_slotted_screw(shaft_diameter, shaft_length, head_diameter, head_height,
                     slot_width, slot_depth)
- make_cross_screw(shaft_diameter, shaft_length, head_diameter, head_height,
                   slot_width, slot_depth)
- make_socket_head_screw(shaft_diameter, shaft_length, head_diameter, head_height,
                         socket_flat)
- make_flange(outer_d, inner_d, thickness, bolt_circle_d, bolt_hole_d, bolt_count)
- make_spur_gear(module, teeth, width)
- make_helical_gear(module, teeth, width, helix_angle)
- make_internal_gear(module, teeth, thickness)
- make_bevel_gear(module, teeth, height, beta)
- make_worm_gear(module, teeth, height, beta, diameter)

Structural / loom‑type helpers:
- make_rect_tube(length, width, height, wall_thickness=0.0)
    Rectangular frame member; if wall_thickness <= 0 it becomes a solid bar.
- make_pipe(outer_d, inner_d, length)
    Hollow or solid cylinder (roller, pipe, round bar).
- make_stepped_shaft(d1, L1, d2, L2, d3=None, L3=None)
    Shaft with 2 or 3 different diameters along its length.
- make_flat_bar_2holes(length, width, thickness, hole_d, edge_offset)
    Flat bar / link with two end holes, centered in width.
- make_drum_with_flange(core_d, core_length, flange_d, flange_thickness,
                        flange_count=2, bore_d=0.0)
    Spool / drum / roller with 0, 1, or 2 flanges and optional bore.
- make_shaft_with_keyway(shaft_diameter, shaft_length, key_width, key_depth)
    Cylindrical shaft with a straight keyway along its length.
- make_plate_with_slot(L, W, thickness, slot_width, edge_offset)
    Plate with one oblong slot along its length.
- make_plate_with_pocket(L, W, thickness,
                         pocket_length, pocket_width, pocket_depth)
    Plate with a rectangular recess on the top face.

Rules:
- Assume: 'import FreeCAD, Part' AND 'from cad_primitives import *' are already done.
- DO NOT write any import or from statements.
- DO NOT call any Part.* or FreeCAD.* functions (except Part.show(shape)).
- If the description mentions a cylinder with a hole or depth, ALWAYS use
  make_cyl_with_hole(...) and NEVER use make_cylinder(...) for that case.
- If the description clearly refers to:
    • rectangular tube / hollow box section / frame member ⇒ use make_rect_tube(...)
    • pipe / hollow roller / tube with bore ⇒ use make_pipe(...)
    • shaft with two or three diameters along its length ⇒ use make_stepped_shaft(...)
    • keyed shaft / shaft with keyway ⇒ use make_shaft_with_keyway(...)
    • flat bar or link with two end holes ⇒ use make_flat_bar_2holes(...)
    • plate with a long slot (oblong hole) ⇒ use make_plate_with_slot(...)
    • plate with a shallow rectangular recess / pocket ⇒ use make_plate_with_pocket(...)
    • drum / spool / roller with flanges ⇒ use make_drum_with_flange(...)
- If the description mentions a worm gear or screw gear, ALWAYS use
  make_worm_gear(module, teeth, height, beta, diameter) and NEVER use
  make_helical_gear or make_spur_gear for that case.
- If the description mentions a spur gear, use make_spur_gear(module, teeth, width).
- If it mentions a helical gear, use make_helical_gear(module, teeth, width, helix_angle).
- If it mentions an internal gear, use make_internal_gear(module, teeth, thickness).
- If it mentions a bevel gear, use make_bevel_gear(module, teeth, height, beta).

Code formatting:
- Create exactly ONE assignment:
    shape = <ONE allowed helper call with numeric arguments>
- Then call exactly:
    Part.show(shape)
- Output ONLY 1–3 lines of pure Python code, no comments, no text, no blank lines.
"""

def _sanitize_code(raw: str) -> str:
    """
    Find the first call to an allowed helper, even if the model:
    - omits 'shape ='
    - nests it inside Part.show(...)
    Then return:
        shape = <that_call>
        Part.show(shape)
    """
    # remove imports and blanks
    useful = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("import ") or s.startswith("from "):
            continue
        useful.append(s)
    text = " ".join(useful)

    call = None
    # find all function calls like name(...)
    for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(([^()]*)\)", text):
        name = m.group(1).strip()
        args = m.group(2).strip()
        if name in ALLOWED_HELPERS:
            call = f"{name}({args})" if args else f"{name}()"
            break

    if not call:
        raise ValueError(f"Model did not return a valid helper call. Raw:\n{raw}")

    return f"shape = {call}\nPart.show(shape)"

def generate_cad_code(description: str) -> str:
    resp = ollama.chat(
        model="llama3.2:3b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Create this part: {description}"},
        ],
    )
    raw = resp["message"]["content"].strip()
    return _sanitize_code(raw)

if __name__ == "__main__":
    desc = input("Describe a part: ")
    code = generate_cad_code(desc)
    print("\n--- GENERATED CODE ---")
    print(code)
