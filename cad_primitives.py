import sys
import math
import subprocess
from pathlib import Path

import FreeCAD, Part
from FreeCAD import Vector

# -------------------------------------------------------------------
# Paths / environment
# -------------------------------------------------------------------

# Path to FreeCAD's command-line executable
FREECADCMD = r"C:\Program Files\FreeCAD 1.0\bin\freecadcmd.exe"

# When frozen (PyInstaller), use the folder that contains the .exe.
# When running from source, use the folder that contains this file.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

# Where the helper scripts live (packaged next to the .exe)
_FAST_BOLT_SCRIPT = BASE_DIR / "fasteners_bolt_script.py"
_GEAR_SCRIPT = BASE_DIR / "gears_script.py"

# Shared folder for generated .FCStd templates (bolts, gears, etc.)
_GENERATED_DIR = BASE_DIR / "generated_models"
_GENERATED_DIR.mkdir(exist_ok=True)


# -------------------------------------------------------------------
# Bolts (Fasteners / simple hex bolt)
# -------------------------------------------------------------------

def make_fasteners_hex_bolt(size, length):
    """
    Hex bolt using the Fasteners workbench when running from source,
    or a built‑in approximate hex bolt when running from the packaged .exe.

    size  : e.g. 4, 8, "M8"
    length: shaft length in mm
    """

    # normalize inputs
    if isinstance(size, (int, float)):
        size_str = f"M{int(size)}"
    else:
        size_str = str(size)
    length_mm = float(length)

    # --- CASE 1: running from the PyInstaller .exe -----------------
    # sys.frozen is True only inside the packaged executable.
    if getattr(sys, "frozen", False):
        # Derive a nominal diameter d from the size string (e.g. "M8" -> 8.0)
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

        # Rough proportions for a hex head
        head_flat = 1.5 * d       # across flats
        head_thickness = 0.6 * d  # head height

        # Use our own simple hex‑bolt geometry (no external FreeCAD process)
        return make_hex_bolt(shaft_radius, shaft_length, head_flat, head_thickness)

    # --- CASE 2: running from source (normal Python) ----------------
    # Keep the existing behavior: use freecadcmd + Fasteners script.
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


# -------------------------------------------------------------------
# Hex shapes, nuts, bolts
# -------------------------------------------------------------------

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


# -------------------------------------------------------------------
# Flange
# -------------------------------------------------------------------

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
# Structural profiles and shafts (frames, rollers, links)
# -------------------------------------------------------------------

def make_rect_tube(length, width, height, wall_thickness=0.0):
    """
    Rectangular hollow section (RHS) or solid bar.
    length = along X, cross‑section = width (Y) × height (Z).
    If wall_thickness <= 0, returns a solid box.
    """
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
    """
    Hollow cylinder (pipe/roller).
    outer_d : outer diameter
    inner_d : inner diameter (0 or None => solid)
    length  : along +Z
    """
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
    """
    Coaxial shaft with 2 or 3 diameter steps along +Z.
    d* = diameters, L* = lengths of each segment.
    """
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
    """
    Flat bar with two through holes along its length.
    Holes are centered in width and placed at 'edge_offset'
    from each end.
    """
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
    """
    Spool/drum: cylindrical core with 0,1,2 end flanges and optional bore.
    core_d, core_length : diameter & length of central drum
    flange_d, flange_thickness : flange diameter & thickness
    flange_count : 0, 1, or 2 flanges
    bore_d : shaft bore diameter (0 => solid)
    """
    core_length = float(core_length)
    core = Part.makeCylinder(float(core_d) / 2.0, core_length)

    flange_count = int(flange_count)
    if flange_count >= 1 and flange_thickness > 0 and flange_d > 0:
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
        if rb >= float(core_d) / 2.0:
            raise ValueError("bore_d must be smaller than core_d")
        bore = Part.makeCylinder(rb, core_length * 1.2,
                                 Vector(0, 0, -0.1 * core_length))
        drum = drum.cut(bore)

    return drum


# -------------------------------------------------------------------
# Gears (via external freecadcmd script)
# -------------------------------------------------------------------

def _run_gear(kind, *params, name="gear"):
    """
    Use external freecadcmd + gears_script.py to generate gears
    when running from source. In the packaged .exe we raise a clear
    error instead of failing deep inside FreeCAD.
    """
    # In the .exe, don't attempt to run external scripts; it's fragile.
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
