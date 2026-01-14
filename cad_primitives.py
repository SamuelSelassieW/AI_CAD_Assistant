import FreeCAD, Part
from FreeCAD import Vector
import math
import subprocess
from pathlib import Path

FREECADCMD = r"C:\Program Files\FreeCAD 1.0\bin\freecadcmd.exe"
_SCRIPT_DIR = Path(__file__).parent
_FAST_BOLT_SCRIPT = _SCRIPT_DIR / "fasteners_bolt_script.py"
_GEAR_SCRIPT = _SCRIPT_DIR / "gears_script.py"

def make_fasteners_hex_bolt(size, length):
    # normalize inputs
    if isinstance(size, (int, float)):
        size_str = f"M{int(size)}"
    else:
        size_str = str(size)
    length_mm = float(length)

    out_dir = _SCRIPT_DIR / "generated_models"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"fast_bolt_{size_str}_{int(length_mm)}.FCStd"
    if not out_path.exists():
        subprocess.run(
            [FREECADCMD, str(_FAST_BOLT_SCRIPT), size_str, str(int(length_mm)), str(out_path)],
            check=True,
        )
    doc = FreeCAD.open(str(out_path))
    shape = doc.Objects[0].Shape
    FreeCAD.closeDocument(doc.Name)
    return shape

def make_box(L, W, H):
    return Part.makeBox(L, W, H)

def make_cylinder(radius, height):
    return Part.makeCylinder(radius, height)

def make_cyl_with_hole(outer_radius, height,
                       hole_radius, hole_depth=None, depth=None):
    """
    Solid cylinder with a coaxial cylindrical hole.
    You may pass hole_depth=... or depth=... (both mean the same).
    """
    if hole_depth is None and depth is not None:
        hole_depth = depth
    if hole_depth is None:
        raise ValueError("hole_depth/depth must be provided")

    outer = Part.makeCylinder(outer_radius, height)
    inner = Part.makeCylinder(hole_radius, hole_depth * 1.2, Vector(0, 0, 0))
    return outer.cut(inner)

def make_tri_prism(base, height, thickness):
    """
    Right triangle in XY plane, extruded along +Z by 'thickness'.
    base along X, height along Y.
    """
    p1 = Vector(0, 0, 0)
    p2 = Vector(base, 0, 0)
    p3 = Vector(base / 2.0, height, 0)

    wire = Part.makePolygon([p1, p2, p3, p1])
    face = Part.Face(wire)
    prism = face.extrude(Vector(0, 0, thickness))
    return prism

def make_plate_with_hole(L, W, thickness, hole_radius):
    plate = Part.makeBox(L, W, thickness)
    if hole_radius is None or hole_radius <= 0:
        return plate  # no hole rather than a FreeCAD error
    hole = Part.makeCylinder(
        hole_radius,
        thickness * 1.2,
        FreeCAD.Vector(L / 2.0, W / 2.0, -thickness * 0.1),
    )
    return plate.cut(hole)

import math
from FreeCAD import Vector

def make_hex_prism(flat, thickness):
    """Regular hex prism; 'flat' = across-flats size."""
    r = flat / (3 ** 0.5)  # circumradius
    pts = [Vector(r * math.cos(math.radians(a)),
                  r * math.sin(math.radians(a)), 0)
           for a in range(0, 360, 60)]
    pts.append(pts[0])
    wire = Part.makePolygon(pts)
    face = Part.Face(wire)
    return face.extrude(Vector(0, 0, thickness))

def make_hex_nut(flat, thickness, hole_radius):
    body = make_hex_prism(flat, thickness)
    hole = Part.makeCylinder(
        hole_radius,
        thickness * 1.2,
        Vector(0, 0, -0.1 * thickness),
    )
    return body.cut(hole)

def make_hex_bolt(shaft_radius, shaft_length, head_flat, head_thickness):
    shaft = Part.makeCylinder(shaft_radius, shaft_length)
    head = make_hex_prism(head_flat, head_thickness)
    head.translate(Vector(0, 0, shaft_length))
    return shaft.fuse(head)

# -------- Screw / bolt helpers (no detailed threads yet) --------
from FreeCAD import Vector

def make_screw_blank(shaft_diameter, shaft_length, head_diameter, head_height):
    r_shaft = shaft_diameter / 2.0
    r_head = head_diameter / 2.0
    shaft = Part.makeCylinder(r_shaft, shaft_length)
    head = Part.makeCylinder(r_head, head_height)
    head.translate(Vector(0, 0, shaft_length))
    return shaft.fuse(head)

def make_slotted_screw(shaft_diameter, shaft_length, head_diameter, head_height,
                       slot_width, slot_depth):
    screw = make_screw_blank(shaft_diameter, shaft_length, head_diameter, head_height)
    slot_len = head_diameter * 1.2
    slot = Part.makeBox(slot_len, slot_width, slot_depth)
    slot.translate(Vector(-slot_len / 2.0,
                          -slot_width / 2.0,
                          shaft_length + head_height - slot_depth))
    return screw.cut(slot)

def make_cross_screw(shaft_diameter, shaft_length, head_diameter, head_height,
                     slot_width, slot_depth):
    screw = make_screw_blank(shaft_diameter, shaft_length, head_diameter, head_height)
    slot_len = head_diameter * 1.2
    slot1 = Part.makeBox(slot_len, slot_width, slot_depth)
    slot1.translate(Vector(-slot_len / 2.0,
                           -slot_width / 2.0,
                           shaft_length + head_height - slot_depth))
    slot2 = slot1.copy()
    center_z = shaft_length + head_height / 2.0
    slot2.rotate(Vector(0, 0, center_z), Vector(0, 0, 1), 90)
    return screw.cut(slot1).cut(slot2)

def make_socket_head_screw(shaft_diameter, shaft_length, head_diameter, head_height,
                           socket_flat):
    screw = make_screw_blank(shaft_diameter, shaft_length, head_diameter, head_height)
    # hex socket cut into head
    hole = make_hex_prism(socket_flat, head_height * 1.2)
    hole.translate(Vector(0, 0, shaft_length - head_height * 0.1))
    return screw.cut(hole)

def make_L_bracket(leg_x, leg_y, width, thickness, fillet_radius=0.0):
    """
    L‑bracket made from two rectangular plates:
      leg_x × width × thickness  and  width × leg_y × thickness
    sharing a corner at the origin.
    """
    leg1 = Part.makeBox(leg_x, width, thickness)
    leg2 = Part.makeBox(width, leg_y, thickness)
    bracket = leg1.fuse(leg2)
    if fillet_radius > 0:
        bracket = bracket.makeFillet(fillet_radius, bracket.Edges)
    return bracket


def make_flange(outer_d, inner_d, thickness,
                bolt_circle_d=0.0, bolt_hole_d=0.0, bolt_count=0):
    """
    Circular flange:
      - outer_d : outer diameter
      - inner_d : inner (pipe) diameter
      - thickness : plate thickness
      - optional bolt circle with 'bolt_count' holes of diameter bolt_hole_d
        on a circle of diameter bolt_circle_d
    """
    r_out = outer_d / 2.0
    r_in  = inner_d / 2.0

    outer = Part.makeCylinder(r_out, thickness)
    inner = Part.makeCylinder(r_in, thickness * 1.2, Vector(0, 0, -0.1 * thickness))
    flange = outer.cut(inner)

    if bolt_count > 0 and bolt_circle_d > 0 and bolt_hole_d > 0:
        r_bc = bolt_circle_d / 2.0
        r_bh = bolt_hole_d / 2.0
        holes = []
        for k in range(bolt_count):
            angle = 2 * math.pi * k / bolt_count
            x = r_bc * math.cos(angle)
            y = r_bc * math.sin(angle)
            h = Part.makeCylinder(r_bh, thickness * 1.2,
                                  Vector(x, y, -0.1 * thickness))
            holes.append(h)
        hole_union = holes[0]
        for h in holes[1:]:
            hole_union = hole_union.fuse(h)
        flange = flange.cut(hole_union)

    return flange

def _run_gear(kind, *params, name="gear"):
    out_dir = _SCRIPT_DIR / "generated_models"
    out_dir.mkdir(exist_ok=True)
    tag = "_".join(str(p).replace(".", "p") for p in params)
    out_path = out_dir / f"{kind}_{tag}.FCStd"
    if not out_path.exists():
        subprocess.run(
            [FREECADCMD, str(_GEAR_SCRIPT), kind, *[str(p) for p in params], str(out_path)],
            check=True,
        )
    doc = FreeCAD.open(str(out_path))
    shape = doc.Objects[0].Shape
    FreeCAD.closeDocument(doc.Name)
    return shape

def make_spur_gear(module, teeth, width, *_, **__):
    """Parallel spur gear."""
    return _run_gear("spur", float(module), int(teeth), float(width))

def make_helical_gear(module, teeth, width, helix_angle, *_, **__):
    """Parallel helical gear."""
    return _run_gear("helical", float(module), int(teeth), float(width), float(helix_angle))

def make_internal_gear(module, teeth, thickness, *_, **__):
    """Internal involute gear."""
    return _run_gear("internal", float(module), int(teeth), float(thickness))

def make_bevel_gear(module, teeth, height, beta, *_, **__):
    """Bevel gear (intersecting shafts)."""
    return _run_gear("bevel", float(module), int(teeth), float(height), float(beta))

def make_worm_gear(module, teeth, height, beta, diameter, *_, **__):
    """Worm gear (non-parallel, non-intersecting)."""
    return _run_gear("worm", float(module), int(teeth), float(height), float(beta), float(diameter))