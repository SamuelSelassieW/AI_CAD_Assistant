import sys
import math
import subprocess
from pathlib import Path

import FreeCAD, Part
from FreeCAD import Vector

# -------------------------------------------------------------------
# Paths / environment
# -------------------------------------------------------------------

FREECADCMD = r"C:\Program Files\FreeCAD 1.0\bin\freecadcmd.exe"

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

_FAST_BOLT_SCRIPT = BASE_DIR / "fasteners_bolt_script.py"
_GEAR_SCRIPT = BASE_DIR / "gears_script.py"

_GENERATED_DIR = BASE_DIR / "generated_models"
_GENERATED_DIR.mkdir(exist_ok=True)


# -------------------------------------------------------------------
# Bolts (Fasteners / simple hex bolt)
# -------------------------------------------------------------------

def make_fasteners_hex_bolt(size, length):
    if isinstance(size, (int, float)):
        size_str = f"M{int(size)}"
    else:
        size_str = str(size)
    length_mm = float(length)

    if getattr(sys, "frozen", False):
        s = size_str.upper()
        if s.startswith("M"):
            try:
                d = float(s[1:])
            except ValueError:
                d = 8.0
        else:
            try:
                d = float(s)
            except ValueError:
                d = 8.0

        shaft_radius = d / 2.0
        shaft_length = length_mm
        head_flat = 1.5 * d
        head_thickness = 0.6 * d
        return make_hex_bolt(shaft_radius, shaft_length, head_flat, head_thickness)

    out_dir = _GENERATED_DIR
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"fast_bolt_{size_str}_{int(length_mm)}.FCStd"

    if not out_path.exists():
        cmd = [
            FREECADCMD,
            str(_FAST_BOLT_SCRIPT),
            size_str,
            str(int(length_mm)),
            str(out_path),
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)

        if result.returncode != 0 or not out_path.exists():
            msg = (
                f"Failed to generate bolt via freecadcmd.\n"
                f"Command: {' '.join(cmd)}\n"
                f"Exit code: {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}\n"
                f"Expected output file: {out_path}"
            )
            raise OSError(msg)

    doc = FreeCAD.open(str(out_path))
    shape = doc.Objects[0].Shape
    FreeCAD.closeDocument(doc.Name)
    return shape


# -------------------------------------------------------------------
# Basic primitives
# -------------------------------------------------------------------

def make_box(L, W, H):
    return Part.makeBox(L, W, H)


def make_cylinder(radius, height):
    return Part.makeCylinder(radius, height)


def make_cyl_with_hole(outer_radius, height,
                       hole_radius, hole_depth=None, depth=None):
    if hole_depth is None and depth is not None:
        hole_depth = depth
    if hole_depth is None:
        raise ValueError("hole_depth/depth must be provided")

    outer = Part.makeCylinder(outer_radius, height)
    inner = Part.makeCylinder(hole_radius, hole_depth * 1.2, Vector(0, 0, 0))
    return outer.cut(inner)


def make_tri_prism(base, height, thickness):
    p1 = Vector(0, 0, 0)
    p2 = Vector(base, 0, 0)
    p3 = Vector(base / 2.0, height, 0)

    wire = Part.makePolygon([p1, p2, p3, p1])
    face = Part.Face(wire)
    prism = face.extrude(Vector(0, 0, thickness))
    return prism


def make_plate_with_hole(L, W, thickness, hole_radius, *_, **__):
    plate = Part.makeBox(L, W, thickness)
    if hole_radius is None or hole_radius <= 0:
        return plate
    hole = Part.makeCylinder(
        hole_radius,
        thickness * 1.2,
        Vector(L / 2.0, W / 2.0, -thickness * 0.1),
    )
    return plate.cut(hole)


# -------------------------------------------------------------------
# Hex shapes, nuts, bolts
# -------------------------------------------------------------------

def make_hex_prism(flat, thickness):
    r = flat / (3 ** 0.5)
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


# -------------------------------------------------------------------
# Simple screw helpers
# -------------------------------------------------------------------

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
    hole = make_hex_prism(socket_flat, head_height * 1.2)
    hole.translate(Vector(0, 0, shaft_length - head_height * 0.1))
    return screw.cut(hole)


def make_L_bracket(leg_x, leg_y, width, thickness, fillet_radius=0.0):
    leg1 = Part.makeBox(leg_x, width, thickness)
    leg2 = Part.makeBox(width, leg_y, thickness)
    bracket = leg1.fuse(leg2)
    if fillet_radius > 0:
        bracket = bracket.makeFillet(fillet_radius, bracket.Edges)
    return bracket


# -------------------------------------------------------------------
# Flange
# -------------------------------------------------------------------

def make_flange(outer_d, inner_d, thickness,
                bolt_circle_d=0.0, bolt_hole_d=0.0, bolt_count=0):
    outer_d = float(outer_d)
    inner_d = float(inner_d)
    thickness = float(thickness)
    bolt_circle_d = 0.0 if bolt_circle_d in (None, "") else float(bolt_circle_d)
    bolt_hole_d = 0.0 if bolt_hole_d in (None, "") else float(bolt_hole_d)
    bolt_count = int(bolt_count or 0)

    r_out = outer_d / 2.0
    r_in = inner_d / 2.0

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


# -------------------------------------------------------------------
# Structural profiles and shafts
# -------------------------------------------------------------------

def make_rect_tube(length, width, height, wall_thickness=0.0):
    length = float(length)
    width = float(width)
    height = float(height)
    t = float(wall_thickness)

    outer = Part.makeBox(length, width, height)
    if t <= 0:
        return outer
    if width <= 2 * t or height <= 2 * t:
        raise ValueError("wall_thickness too large for given width/height")

    inner = Part.makeBox(
        length,
        width - 2 * t,
        height - 2 * t,
        Vector(0.0, t, t),
    )
    return outer.cut(inner)


def make_pipe(outer_d, inner_d, length):
    length = float(length)
    ro = float(outer_d) / 2.0
    ri = float(inner_d) / 2.0 if inner_d else 0.0

    outer = Part.makeCylinder(ro, length)
    if ri <= 0.0:
        return outer
    if ri >= ro:
        raise ValueError("inner_d must be smaller than outer_d")

    inner = Part.makeCylinder(ri, length * 1.2, Vector(0, 0, -0.1 * length))
    return outer.cut(inner)


def make_stepped_shaft(d1, L1, d2, L2, d3=None, L3=None):
    d1 = float(d1); L1 = float(L1)
    d2 = float(d2); L2 = float(L2)
    if d1 <= 0 or d2 <= 0 or L1 <= 0 or L2 <= 0:
        raise ValueError("d1,d2,L1,L2 must be > 0")

    z = 0.0
    shaft = Part.makeCylinder(d1 / 2.0, L1, Vector(0, 0, z))
    z += L1
    seg2 = Part.makeCylinder(d2 / 2.0, L2, Vector(0, 0, z))
    shaft = shaft.fuse(seg2)
    z += L2

    if d3 is not None and L3 is not None:
        d3 = float(d3); L3 = float(L3)
        if d3 > 0 and L3 > 0:
            seg3 = Part.makeCylinder(d3 / 2.0, L3, Vector(0, 0, z))
            shaft = shaft.fuse(seg3)

    return shaft


def make_flat_bar_2holes(length, width, thickness, hole_d, edge_offset):
    length = float(length)
    width = float(width)
    thickness = float(thickness)
    hole_d = float(hole_d)
    edge_offset = float(edge_offset)

    plate = Part.makeBox(length, width, thickness)
    if hole_d <= 0:
        return plate
    if edge_offset <= 0 or edge_offset >= length / 2.0:
        raise ValueError("edge_offset must be >0 and < length/2")

    r = hole_d / 2.0
    z0 = -0.1 * thickness
    h = thickness * 1.2

    hole1 = Part.makeCylinder(
        r, h,
        Vector(edge_offset, width / 2.0, z0),
    )
    hole2 = Part.makeCylinder(
        r, h,
        Vector(length - edge_offset, width / 2.0, z0),
    )
    holes = hole1.fuse(hole2)
    return plate.cut(holes)


def make_drum_with_flange(core_d, core_length,
                          flange_d, flange_thickness,
                          flange_count=2, bore_d=0.0):
    core_length = float(core_length)
    core_d = float(core_d)
    core = Part.makeCylinder(core_d / 2.0, core_length)

    flange_count = int(flange_count or 0)
    if flange_count >= 1 and flange_thickness and flange_d:
        ft = float(flange_thickness)
        fd = float(flange_d) / 2.0
        flange1 = Part.makeCylinder(fd, ft, Vector(0, 0, 0))
        drum = core.fuse(flange1)
        if flange_count >= 2:
            flange2 = Part.makeCylinder(fd, ft, Vector(0, 0, core_length - ft))
            drum = drum.fuse(flange2)
    else:
        drum = core

    if bore_d and bore_d > 0:
        rb = float(bore_d) / 2.0
        if rb >= core_d / 2.0:
            raise ValueError("bore_d must be smaller than core_d")
        bore = Part.makeCylinder(rb, core_length * 1.2,
                                 Vector(0, 0, -0.1 * core_length))
        drum = drum.cut(bore)

    return drum


def make_shaft_with_keyway(shaft_diameter, shaft_length, key_width, key_depth):
    shaft_diameter = float(shaft_diameter)
    shaft_length = float(shaft_length)
    key_width = float(key_width)
    key_depth = float(key_depth)

    if shaft_diameter <= 0 or shaft_length <= 0:
        raise ValueError("shaft_diameter and shaft_length must be > 0")
    if key_width <= 0 or key_depth <= 0:
        raise ValueError("key_width and key_depth must be > 0")

    r = shaft_diameter / 2.0
    shaft = Part.makeCylinder(r, shaft_length)

    slot_len = shaft_length * 1.2
    slot = Part.makeBox(
        key_width,
        key_depth,
        slot_len,
        Vector(-key_width / 2.0, r - key_depth, -0.1 * shaft_length),
    )
    return shaft.cut(slot)


def make_v_pulley(pitch_d, groove_width, groove_angle_deg,
                  bore_d, key_width=0.0, key_depth=0.0,
                  hub_length=0.0, hub_d=None):
    """
    Simple single‑groove V‑belt pulley.

    pitch_d          : nominal pitch diameter (we approximate as outer diameter)
    groove_width     : groove top width (mm)
    groove_angle_deg : included V angle in degrees (e.g. 38)
    bore_d           : shaft bore diameter
    key_width        : keyway width (0 => no keyway)
    key_depth        : keyway depth
    hub_length       : axial length of hub beyond the rim (0 => no hub)
    hub_d            : hub outer diameter (None => 0.6 * pitch_d)

    Geometry is approximate but useful for concept and layout models.
    """
    pitch_d = float(pitch_d)
    groove_width = float(groove_width)
    groove_angle_deg = float(groove_angle_deg)
    bore_d = float(bore_d)
    key_width = float(key_width)
    key_depth = float(key_depth)
    hub_length = float(hub_length)

    R = pitch_d / 2.0
    rim_thickness = groove_width + 4.0  # small margin beyond groove

    # main rim cylinder
    body = Part.makeCylinder(R, rim_thickness)

    # V‑groove cut: revolve a triangle around Z axis
    half_w = groove_width / 2.0
    half_angle = math.radians(groove_angle_deg / 2.0)
    # approximate depth from top width and angle
    groove_depth = half_w / math.tan(half_angle)
    groove_depth = min(groove_depth, R * 0.7)  # don't cut through the hub

    zmid = rim_thickness / 2.0

    p1 = Vector(R, 0, zmid - half_w)
    p2 = Vector(R - groove_depth, 0, zmid)
    p3 = Vector(R, 0, zmid + half_w)
    wire = Part.makePolygon([p1, p2, p3, p1])
    face = Part.Face(wire)
    groove = face.revolve(Vector(0, 0, zmid), Vector(0, 0, 1), 360)
    body = body.cut(groove)

    # Bore through rim + hub
    rb = bore_d / 2.0
    bore_len = rim_thickness + max(hub_length, 0.0) + 2.0
    bore = Part.makeCylinder(rb, bore_len, Vector(0, 0, -1.0))
    body = body.cut(bore)

    # Hub (optional)
    if hub_length > 0.0:
        hub_R = (float(hub_d) / 2.0) if hub_d not in (None, 0, "") else 0.6 * R
        hub = Part.makeCylinder(hub_R, hub_length, Vector(0, 0, rim_thickness))
        body = body.fuse(hub)

    # Keyway (optional) – cut like a slot on +Y side
    if key_width > 0.0 and key_depth > 0.0:
        slot_len = rim_thickness + hub_length + 2.0
        slot = Part.makeBox(
            key_width,
            key_depth,
            slot_len,
            Vector(-key_width / 2.0, rb - key_depth, -1.0),
        )
        body = body.cut(slot)

    return body

def make_plate_with_slot(L, W, thickness, slot_width, edge_offset):
    L = float(L)
    W = float(W)
    thickness = float(thickness)
    slot_width = float(slot_width)
    edge_offset = float(edge_offset)

    if L <= 0 or W <= 0 or thickness <= 0:
        raise ValueError("L, W, thickness must be > 0")
    if slot_width <= 0:
        raise ValueError("slot_width must be > 0")
    if edge_offset <= 0 or edge_offset >= L / 2.0:
        raise ValueError("edge_offset must be > 0 and < L/2")

    plate = Part.makeBox(L, W, thickness)

    slot_length = L - 2.0 * edge_offset
    if slot_length <= 0:
        raise ValueError("slot_length became <= 0; check edge_offset and L")

    slot = Part.makeBox(
        slot_length,
        slot_width,
        thickness * 1.2,
        Vector(edge_offset, (W - slot_width) / 2.0, -0.1 * thickness),
    )
    return plate.cut(slot)


def make_plate_with_pocket(L, W, thickness,
                           pocket_length, pocket_width, pocket_depth):
    L = float(L)
    W = float(W)
    thickness = float(thickness)
    pocket_length = float(pocket_length)
    pocket_width = float(pocket_width)
    pocket_depth = float(pocket_depth)

    if L <= 0 or W <= 0 or thickness <= 0:
        raise ValueError("L, W, thickness must be > 0")
    if pocket_length <= 0 or pocket_width <= 0 or pocket_depth <= 0:
        raise ValueError("Pocket dimensions must be > 0")
    if pocket_length >= L or pocket_width >= W:
        raise ValueError("Pocket must be smaller than plate in X/Y")
    if pocket_depth >= thickness:
        raise ValueError("pocket_depth must be < thickness")

    plate = Part.makeBox(L, W, thickness)

    px = (L - pocket_length) / 2.0
    py = (W - pocket_width) / 2.0
    pz = thickness - pocket_depth

    pocket = Part.makeBox(
        pocket_length,
        pocket_width,
        pocket_depth,
        Vector(px, py, pz),
    )
    return plate.cut(pocket)


# -------------------------------------------------------------------
# Gears (via external freecadcmd script)
# -------------------------------------------------------------------

def _run_gear(kind, *params, name="gear"):
    if getattr(sys, "frozen", False):
        raise OSError(
            "Gear generation via gears_script.py is not available in the "
            "packaged app. Please run app_gui.py from source to generate gears."
        )

    out_dir = _GENERATED_DIR
    out_dir.mkdir(exist_ok=True)
    tag = "_".join(str(p).replace(".", "p") for p in params)
    out_path = out_dir / f"{kind}_{tag}.FCStd"

    if not out_path.exists():
        cmd = [
            FREECADCMD,
            str(_GEAR_SCRIPT),
            kind,
            *[str(p) for p in params],
            str(out_path),
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)

        if result.returncode != 0 or not out_path.exists():
            msg = (
                f"Failed to generate gear via freecadcmd.\n"
                f"Command: {' '.join(cmd)}\n"
                f"Exit code: {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}\n"
                f"Expected output file: {out_path}"
            )
            raise OSError(msg)

    doc = FreeCAD.open(str(out_path))
    shape = doc.Objects[0].Shape
    FreeCAD.closeDocument(doc.Name)
    return shape


def make_spur_gear(module, teeth, width, *_, **__):
    return _run_gear("spur", float(module), int(teeth), float(width))


def make_helical_gear(module, teeth, width, helix_angle, *_, **__):
    return _run_gear("helical", float(module), int(teeth), float(width), float(helix_angle))


def make_internal_gear(module, teeth, thickness, *_, **__):
    return _run_gear("internal", float(module), int(teeth), float(thickness))


def make_bevel_gear(module, teeth, height, beta, *_, **__):
    return _run_gear("bevel", float(module), int(teeth), float(height), float(beta))


def make_worm_gear(module, teeth, height, beta, diameter, *_, **__):
    return _run_gear("worm", float(module), int(teeth), float(height), float(beta), float(diameter))
