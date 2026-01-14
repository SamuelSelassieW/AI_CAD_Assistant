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
]

SYSTEM_PROMPT = """
You generate STRICT Python code to build ONE 3D solid using helper functions
from cad_primitives, then display it.

Allowed helper calls (already imported for you):
- make_box(L, W, H)
- make_cylinder(radius, height)
- make_tri_prism(base, height, thickness)
- make_plate_with_hole(L, W, thickness, hole_radius)
- make_hex_prism(flat, thickness)
- make_hex_nut(flat, thickness, hole_radius)
- make_hex_bolt(shaft_radius, shaft_length, head_flat, head_thickness)
- make_screw_blank(shaft_diameter, shaft_length, head_diameter, head_height)
- make_slotted_screw(shaft_diameter, shaft_length, head_diameter, head_height,
                     slot_width, slot_depth)
- make_cross_screw(shaft_diameter, shaft_length, head_diameter, head_height,
                   slot_width, slot_depth)
- make_socket_head_screw(shaft_diameter, shaft_length, head_diameter, head_height,
                         socket_flat)
-- make_fasteners_hex_bolt(size, length_mm)
- make_cyl_with_hole(outer_radius, height, hole_radius, hole_depth)
- make_spur_gear(module, teeth, width)
- make_helical_gear(module, teeth, width, helix_angle)
- make_internal_gear(module, teeth, thickness)
- make_bevel_gear(module, teeth, height, beta)
- make_worm_gear(module, teeth, height, beta, diameter)
- make_flange(outer_d, inner_d, thickness, bolt_circle_d, bolt_hole_d, bolt_count)

Rules:
- Assume: 'import FreeCAD, Part' AND 'from cad_primitives import *' are already done.
- DO NOT write any import or from statements.
- DO NOT call any Part.* or FreeCAD.* functions (except Part.show(shape)).
- If the description mentions a cylinder with a hole or depth, ALWAYS use make_cyl_with_hole(...)
  and NEVER use make_cylinder(...) for that case.
- Create exactly ONE assignment:
    shape = <ONE allowed helper call with numeric arguments>
- Then call exactly:
    Part.show(shape)
- Output ONLY 1–3 lines of pure Python code, no comments, no text, no blank lines.
- If the description mentions a worm gear or screw gear, ALWAYS use
  make_worm_gear(module, teeth, height, beta, diameter)
  and NEVER use make_helical_gear or make_spur_gear for that case.
- If the description mentions a spur gear, use make_spur_gear(module, teeth, width).
- If it mentions a helical gear, use make_helical_gear(module, teeth, width, helix_angle).
- If it mentions an internal gear, use make_internal_gear(module, teeth, thickness).
- If it mentions a bevel gear, use make_bevel_gear(module, teeth, height, beta).
- If it mentions a worm gear or screw gear, ALWAYS use make_worm_gear(...).
- If the description mentions a circular flange, or flange with bolt circle/holes,
  use make_flange(...) and NOT make_plate_with_hole(...).
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