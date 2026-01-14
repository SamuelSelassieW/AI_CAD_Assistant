import ollama
import re

# Functions allowed from geom_ops
ALLOWED_FUNCS = [
    "box", "cyl", "cone", "sphere",
    "translate", "rotate",
    "union", "difference", "intersect",
    "fillet_all", "chamfer_all",
    "extrude_polygon", "loft_between_polygons",
    "sweep_profile_along_path",
    "linear_array", "mirror", "circular_array",
    "shell", "rib_between_points",
]

SYSTEM_PROMPT = """
You write Python code that uses ONLY functions from 'geom_ops' to build a 3D shape.

Assumptions:
- The following are already imported:
    import FreeCAD, Part
    from geom_ops import *
- A FreeCAD document already exists.

Allowed functions:
- box(L, W, H)
- cyl(radius, height)
- cone(r1, r2, height)
- sphere(radius)
- translate(shape, x, y, z)
- rotate(shape, ax, ay, az, angle_deg, cx=0, cy=0, cz=0)
- union(a, b, ...)
- difference(a, b)
- intersect(a, b)
- fillet_all(shape, radius)
- chamfer_all(shape, distance)
- extrude_polygon(points_2d, height)
- loft_between_polygons(points_2d_a, z_a, points_2d_b, z_b)
- sweep_profile_along_path(profile_points_2d, path_points_3d)
- linear_array(shape, nx, ny, nz, dx, dy, dz)
- mirror(shape, nx, ny, nz, px=0, py=0, pz=0)
- circular_array(shape, n, ax, ay, az, total_angle_deg=360, cx=0, cy=0, cz=0)
- shell(shape, thickness)
- rib_between_points(base_shape, x1, y1, x2, y2, thickness, height, z0=0)

Rules:
- DO NOT write any 'import' or 'from' statements.
- DO NOT call FreeCAD.* or Part.* directly (except Part.show(shape) if you wish).
- You may use multiple lines and intermediate variables.
- At the end:
    - assign the final solid to variable 'shape'
    - call: Part.show(shape)
- Output ONLY Python code, no explanations or comments.

Examples:

# block with a hole
body = box(60, 30, 10)
hole = cyl(5, 12)
hole = translate(hole, 30, 15, 0)
shape = difference(body, hole)
Part.show(shape)

# circular array of cylinders
base = cyl(3, 10)
shape = circular_array(base, 6, 0, 0, 1, 360, 0, 0, 0)
Part.show(shape)
"""

def _sanitize_code(raw: str) -> str:
    """
    Remove imports and any direct FreeCAD/Part calls (except Part.show).
    Keep the rest as-is.
    Ensure there is a final Part.show(shape).
    """
    lines = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("import ") or s.startswith("from "):
            continue
        if "FreeCAD." in s:
            continue
        if "Part." in s and "Part.show" not in s:
            continue
        lines.append(line)

    if not lines:
        raise ValueError(f"No valid code lines after sanitizing. Raw:\n{raw}")

    text = "\n".join(lines)

    # Require at least one assignment to 'shape'
    if "shape =" not in text:
        # try to find any allowed function call and build a shape assignment
        joined = " ".join(lines)
        for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(([^()]*)\)", joined):
            name = m.group(1)
            args = m.group(2)
            if name in ALLOWED_FUNCS:
                text = f"shape = {name}({args})"
                break
        else:
            raise ValueError(f"No 'shape =' and no allowed function call. Raw:\n{raw}")

    if "Part.show(shape)" not in text:
        text += "\nPart.show(shape)"

    return text

def generate_geom_code(description: str) -> str:
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
    code = generate_geom_code(desc)
    print("\n--- GENERATED CODE ---")
    print(code)