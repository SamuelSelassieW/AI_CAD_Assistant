import FreeCAD, Part
from FreeCAD import Vector
import math

# ---------- Basic solids ----------

def box(L, W, H):
    """Axis-aligned box with origin at (0,0,0)."""
    return Part.makeBox(L, W, H)

def cyl(radius, height):
    """Cylinder along +Z with base at Z=0."""
    return Part.makeCylinder(radius, height)

def cone(r1, r2, height):
    """Cone/truncated cone along +Z."""
    return Part.makeCone(r1, r2, height)

def sphere(radius):
    return Part.makeSphere(radius)

# ---------- Transforms ----------

def translate(shape, x, y, z):
    """Return a translated copy of shape."""
    s = shape.copy()
    s.translate(Vector(x, y, z))
    return s

def rotate(shape, ax, ay, az, angle_deg, cx=0.0, cy=0.0, cz=0.0):
    """Rotate around axis (ax,ay,az) through center (cx,cy,cz)."""
    s = shape.copy()
    s.rotate(Vector(cx, cy, cz), Vector(ax, ay, az), angle_deg)
    return s

# ---------- Boolean operations ----------

def union(*shapes):
    """Fuse all shapes together."""
    if not shapes:
        raise ValueError("union() needs at least one shape")
    result = shapes[0]
    for s in shapes[1:]:
        result = result.fuse(s)
    return result

def difference(a, b):
    """Return a-b."""
    return a.cut(b)

def intersect(a, b):
    """Return intersection of a and b."""
    return a.common(b)

# ---------- Fillet / chamfer ----------

def fillet_all(shape, radius):
    """Fillet all edges with the same radius."""
    s = shape.copy()
    return s.makeFillet(radius, s.Edges)

def chamfer_all(shape, distance):
    """Chamfer all edges with same distance."""
    s = shape.copy()
    return s.makeChamfer(distance, s.Edges)

# ---------- Sketch-like profiles + extrude ----------

def extrude_polygon(points_2d, height):
    """
    Extrude a closed 2D polygon (in XY) along +Z by 'height'.
    points_2d: list of (x,y) tuples.
    """
    if len(points_2d) < 3:
        raise ValueError("Need at least 3 points for a polygon")
    pts = [Vector(x, y, 0.0) for x, y in points_2d]
    pts.append(pts[0])
    wire = Part.makePolygon(pts)
    face = Part.Face(wire)
    return face.extrude(Vector(0, 0, height))

# ---------- Simple loft (between two profiles) ----------

def loft_between_polygons(points_2d_a, z_a, points_2d_b, z_b):
    """
    Loft between two planar polygon profiles at different Z.
    Very simplified: same point count & ordering recommended.
    """
    def face_from_points(pts2d, z):
        pts = [Vector(x, y, z) for x, y in pts2d]
        pts.append(pts[0])
        wire = Part.makePolygon(pts)
        return Part.Face(wire)

    f1 = face_from_points(points_2d_a, z_a)
    f2 = face_from_points(points_2d_b, z_b)
    return Part.makeLoft([f1, f2])

# ---------- Sweep (profile along path) ----------

def sweep_profile_along_path(profile_points_2d, path_points_3d):
    """
    Sweep a 2D profile (in XY at Z=0) along a 3D polyline path.
    Very simplified sweep using makePipeShell.
    """
    # make profile wire + face
    p_pts = [Vector(x, y, 0.0) for x, y in profile_points_2d]
    p_pts.append(p_pts[0])
    prof_wire = Part.makePolygon(p_pts)
    prof_face = Part.Face(prof_wire)

    # make path wire
    path_vecs = [Vector(x, y, z) for x, y, z in path_points_3d]
    path_wire = Part.makePolygon(path_vecs)

    shell = Part.Wire(path_wire).makePipeShell([prof_face], True, True)
    return shell

# ---------- Linear array / pattern ----------

def linear_array(shape, nx, ny, nz, dx, dy, dz):
    """
    Create a linear pattern (array) and fuse all instances.
    nx,ny,nz: count in each direction.
    dx,dy,dz: spacing in mm.
    """
    instances = []
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                s = shape.copy()
                s.translate(Vector(i * dx, j * dy, k * dz))
                instances.append(s)

    if not instances:
        raise ValueError("linear_array: no instances created")

    result = instances[0]
    for s in instances[1:]:
        result = result.fuse(s)
    return result
# ---------- Mirror ----------

def mirror(shape, nx, ny, nz, px=0.0, py=0.0, pz=0.0):
    """
    Mirror shape about a plane with normal (nx,ny,nz) passing through point (px,py,pz).
    Similar to SolidWorks mirror feature.
    """
    s = shape.copy()
    return s.mirror(Vector(px, py, pz), Vector(nx, ny, nz))

# ---------- Circular array / pattern ----------

def circular_array(shape, n, ax, ay, az, total_angle_deg=360.0, cx=0.0, cy=0.0, cz=0.0):
    """
    Circular pattern of 'shape' rotated around axis (ax,ay,az) through (cx,cy,cz).
    total_angle_deg = sweep angle (360 for full circle).
    """
    if n < 1:
        raise ValueError("circular_array: n must be >= 1")
    angle_step = total_angle_deg / n
    instances = []
    for k in range(n):
        s = shape.copy()
        s.rotate(Vector(cx, cy, cz), Vector(ax, ay, az), k * angle_step)
        instances.append(s)
    result = instances[0]
    for s in instances[1:]:
        result = result.fuse(s)
    return result

# ---------- Shell (hollow solid) ----------

def shell(shape, thickness):
    """
    Create a hollow solid by offsetting all faces inward by 'thickness'.
    thickness > 0 = wall thickness (inside offset).
    Note: may fail for very complex shapes.
    """
    faces = shape.Faces
    return shape.makeThickness(faces, -thickness, 1e-3)

# ---------- Simple rib helper ----------

def rib_between_points(base_shape, x1, y1, x2, y2, thickness, height, z0=0.0):
    """
    Create a rectangular rib between (x1,y1) and (x2,y2) in XY at z=z0, extruded by 'height'.
    thickness is the rib width (perpendicular to the line).
    Rib is fused to base_shape.
    """
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        raise ValueError("rib_between_points: points must be different")

    # unit perpendicular vector
    nx = -dy / length
    ny = dx / length
    half = thickness / 2.0

    p1 = Vector(x1 + nx * half, y1 + ny * half, z0)
    p2 = Vector(x2 + nx * half, y2 + ny * half, z0)
    p3 = Vector(x2 - nx * half, y2 - ny * half, z0)
    p4 = Vector(x1 - nx * half, y1 - ny * half, z0)

    wire = Part.makePolygon([p1, p2, p3, p4, p1])
    face = Part.Face(wire)
    rib = face.extrude(Vector(0, 0, height))

    return base_shape.fuse(rib)