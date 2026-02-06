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
    # V-belt pulley helper
    "make_v_pulley",
]


class AmbiguousPartError(Exception):
    """Prompt mentions a supported class but is not specific enough."""
    pass


class UnsupportedPartError(Exception):
    """Prompt describes something not in our helper library."""
    pass


SYSTEM_PROMPT = """
You generate STRICT Python code to build ONE 3D solid using helper functions
from cad_primitives, then display it.

Your entire reply MUST be one of these:

1) A single line starting with:
   ASK_CLARIFY: ...
   or
   UNSUPPORTED_PART: ...

2) Exactly two lines of Python code:
   shape = <ONE allowed helper call with numeric arguments>
   Part.show(shape)

Any other kind of output (comments, English sentences, explanations) is invalid.

User descriptions may be short or ungrammatical. Ignore grammar and casing; focus on:
- the part type (bolt, tube, shaft, plate, slot, pocket, keyway, drum, gear, flange, V-belt pulley, etc.)
- all numeric dimensions.

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
- make_v_pulley(pitch_d, groove_width, groove_angle_deg,
                bore_d, key_width=0.0, key_depth=0.0,
                hub_length=0.0, hub_d=None)

Mapping from descriptions to helpers when you DO generate code:
- "rectangular tube", "box tube", "hollow section", "frame member"
  ⇒ make_rect_tube(length, width, height, wall_thickness).
- "pipe", "tube", "roller", "hollow cylinder" or outer + inner diameters
  ⇒ make_pipe(outer_d, inner_d, length).
- "stepped shaft", "two diameters", "three diameters", "shoulder on the shaft"
  ⇒ make_stepped_shaft(d1, L1, d2, L2, d3, L3).
- "keyed shaft", "keyway", "key slot in the shaft"
  ⇒ make_shaft_with_keyway(shaft_diameter, shaft_length, key_width, key_depth).
- "flat bar with two holes", "link", "strap with holes at each end"
  ⇒ make_flat_bar_2holes(length, width, thickness, hole_d, edge_offset).
- "drum", "spool", "roller with flanges"
  ⇒ make_drum_with_flange(core_d, core_length, flange_d, flange_thickness,
                           flange_count, bore_d).
- "slot", "elongated hole", "long hole" in a plate
  ⇒ make_plate_with_slot(L, W, thickness, slot_width, edge_offset).
- "pocket", "recess", "shallow cavity" on the top face of a plate
  ⇒ make_plate_with_pocket(L, W, thickness,
                           pocket_length, pocket_width, pocket_depth).
- Cylinder with a through or blind hole along the axis
  ⇒ make_cyl_with_hole(...), never plain make_cylinder for that case.
- Circular plate / carrier plate with outer diameter, thickness,
  central bore, and equally spaced holes on a bolt circle
  ⇒ treat as a flange and use make_flange(outer_d, inner_d, thickness,
                                          bolt_circle_d, bolt_hole_d, bolt_count).

- "V-belt pulley", "V belt pulley", "V pulley", "V-groove pulley"
  ⇒ ALWAYS use make_v_pulley(pitch_d, groove_width, groove_angle_deg,
                             bore_d, key_width, key_depth, hub_length, hub_d).
     If some values (like hub diameter or length) are not given, choose simple
     numeric defaults (e.g. hub_length=10, hub_d=0.6 * pitch_d) instead of
     asking the user. DO NOT output ASK_CLARIFY for V-belt pulleys and DO NOT
     reply with English sentences for them.

Gears:
- If the description mentions a worm gear or screw gear,
  ALWAYS use make_worm_gear(module, teeth, height, beta, diameter).
- "spur gear" ⇒ make_spur_gear(module, teeth, width)
- "helical gear" ⇒ make_helical_gear(module, teeth, width, helix_angle)
- "internal gear" ⇒ make_internal_gear(module, teeth, thickness)
- "bevel gear" ⇒ make_bevel_gear(module, teeth, height, beta)

Clarification / unsupported:
- If you genuinely cannot map the description to any helper or the part is not
  a reasonable fit (e.g. "banana shape"), output:
    UNSUPPORTED_PART: <short message>
- If the description fits a helper but is missing absolutely critical numbers,
  output:
    ASK_CLARIFY: <very short helpful message to the user>

General rules when you DO generate code:
- Assume: 'import FreeCAD, Part' AND 'from cad_primitives import *' are already done.
- DO NOT write any import or from statements.
- DO NOT call any Part.* or FreeCAD.* functions (except Part.show(shape)).
- Always assume millimetres when units are not stated.
- If any numeric value is missing, choose a reasonable simple default
  (e.g. 5 or 10); never pass None or omit required arguments.
- Create exactly ONE assignment:
    shape = <ONE allowed helper call with numeric arguments>
- Then call exactly:
    Part.show(shape)
- Output ONLY these two lines of Python code, no comments, no text, no blank lines.
"""


def _sanitize_code(raw: str) -> str:
    """
    Take raw model output containing Python code, strip imports / junk,
    and normalize into:

        shape = <helper_call(...)>
        Part.show(shape)
    """
    useful = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
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
    lower = raw.lower()

    # explicit markers for clarification / unsupported
    if raw.startswith("ASK_CLARIFY:") or raw.startswith("ASK_GEAR_TYPE:"):
        msg = raw.split(":", 1)[1].strip() or (
            "Part not well defined. Please refine your description."
        )
        raise AmbiguousPartError(msg)

    if raw.startswith("UNSUPPORTED_PART:"):
        msg = raw.split(":", 1)[1].strip() or (
            "Object not found in library; can't generate this figure for now."
        )
        raise UnsupportedPartError(msg)

    # known textual patterns we may see
    if lower.startswith("part_not_well_defined") or lower.startswith("part not well defined"):
        msg = raw.split(":", 1)[1].strip() if ":" in raw else raw
        msg = msg or "Part not well defined. Please refine your description."
        raise AmbiguousPartError(msg)

    if "not fit any standard cad primitive" in lower:
        raise UnsupportedPartError(raw)

    # Look for any allowed helper call; if found, sanitize normally
    for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", raw):
        name = m.group(1)
        if name in ALLOWED_HELPERS:
            return _sanitize_code(raw)

    # No helper call at all → AI answered in English / asked a question.
    # Treat as ambiguous part for the UI to surface via the red toast.
    raise AmbiguousPartError(raw)


if __name__ == "__main__":
    desc = input("Describe a part: ")
    try:
        code = generate_cad_code(desc)
        print("\n--- GENERATED CODE ---")
        print(code)
    except (AmbiguousPartError, UnsupportedPartError) as e:
        print("\n--- MESSAGE ---")
        print(str(e))
