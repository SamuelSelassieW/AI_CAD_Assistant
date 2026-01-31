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
    # structural / shaft helpers
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

User descriptions may:
- be very short or ungrammatical,
- mix upper/lower case,
- contain spelling mistakes.
You must ignore grammar and casing and focus on:
- the type of part (bolt, tube, shaft, plate, slot, pocket, keyway, drum, gear, flange, etc.)
- all numeric dimensions.

Treat upper/lower case as identical.

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
- make_rect_tube(length, width, height, wall_thickness=0.0)
- make_pipe(outer_d, inner_d, length)
- make_stepped_shaft(d1, L1, d2, L2, d3=None, L3=None)
- make_flat_bar_2holes(length, width, thickness, hole_d, edge_offset)
- make_drum_with_flange(core_d, core_length, flange_d, flange_thickness,
                        flange_count=2, bore_d=0.0)
- make_shaft_with_keyway(shaft_diameter, shaft_length, key_width, key_depth)
- make_plate_with_slot(L, W, thickness, slot_width, edge_offset)
- make_plate_with_pocket(L, W, thickness,
                         pocket_length, pocket_width, pocket_depth)

Mapping from noisy descriptions to helpers:
- Words like "rectangular tube", "box tube", "hollow section", "frame member"
  ⇒ use make_rect_tube(length, width, height, wall_thickness).
- Words like "pipe", "tube", "roller", "hollow cylinder" or outer + inner diameters
  ⇒ use make_pipe(outer_d, inner_d, length).
- "stepped shaft", "two diameters", "three diameters", "shoulder on the shaft"
  ⇒ use make_stepped_shaft(d1, L1, d2, L2, d3, L3).
- "keyed shaft", "keyway", "key slot in the shaft"
  ⇒ use make_shaft_with_keyway(shaft_diameter, shaft_length, key_width, key_depth).
- "flat bar with two holes", "link", "strap with holes at each end"
  ⇒ use make_flat_bar_2holes(length, width, thickness, hole_d, edge_offset).
- "drum", "spool", "roller with flanges"
  ⇒ use make_drum_with_flange(core_d, core_length, flange_d, flange_thickness,
                               flange_count, bore_d).
- "slot", "elongated hole", "long hole" in a plate
  ⇒ use make_plate_with_slot(L, W, thickness, slot_width, edge_offset).
- "pocket", "recess", "shallow cavity" on the top face of a plate
  ⇒ use make_plate_with_pocket(L, W, thickness,
                               pocket_length, pocket_width, pocket_depth).
- Cylinder with a through or blind hole along the axis
  ⇒ use make_cyl_with_hole(...), never plain make_cylinder for that case.
- Circular flange with bolt circle / bolt holes
  ⇒ use make_flange(...), not make_plate_with_hole(...).

Gears:
- If the description mentions a worm gear or screw gear,
  ALWAYS use make_worm_gear(module, teeth, height, beta, diameter).
- "spur gear" ⇒ make_spur_gear(module, teeth, width)
- "helical gear" ⇒ make_helical_gear(module, teeth, width, helix_angle)
- "internal gear" ⇒ make_internal_gear(module, teeth, thickness)
- "bevel gear" ⇒ make_bevel_gear(module, teeth, height, beta)

General rules:
- Assume: 'import FreeCAD, Part' AND 'from cad_primitives import *' are already done.
- DO NOT write any import or from statements.
- DO NOT call any Part.* or FreeCAD.* functions (except Part.show(shape)).
- Always assume millimetres for dimensions when units are not stated.
- If any parameter is not clearly given, choose a simple numeric default
  (for example 10 or 5), but DO NOT pass None or leave arguments empty.
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
    useful = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        # drop imports, from, and code fences
        if s.startswith("import ") or s.startswith("from "):
            continue
        if s.startswith("```"):
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
