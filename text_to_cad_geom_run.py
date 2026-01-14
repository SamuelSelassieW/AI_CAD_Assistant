import os
import pathlib
import FreeCAD, Part

from cad_code_geom import generate_geom_code
from geom_ops import (
    box, cyl, cone, sphere,
    translate, rotate,
    union, difference, intersect,
    fillet_all, chamfer_all,
    extrude_polygon, loft_between_polygons,
    sweep_profile_along_path,
    linear_array, mirror, circular_array,
    shell, rib_between_points,
)

def main():
    desc = input("Describe a part (general geom_ops engine): ")
    code = generate_geom_code(desc)

    print("\n--- GENERATED CODE ---")
    print(code)

    doc = FreeCAD.newDocument("AIModelGeom")

    exec_globals = {
        "FreeCAD": FreeCAD,
        "Part": Part,
        "box": box,
        "cyl": cyl,
        "cone": cone,
        "sphere": sphere,
        "translate": translate,
        "rotate": rotate,
        "union": union,
        "difference": difference,
        "intersect": intersect,
        "fillet_all": fillet_all,
        "chamfer_all": chamfer_all,
        "extrude_polygon": extrude_polygon,
        "loft_between_polygons": loft_between_polygons,
        "sweep_profile_along_path": sweep_profile_along_path,
        "linear_array": linear_array,
        "mirror": mirror,
        "circular_array": circular_array,
        "shell": shell,
        "rib_between_points": rib_between_points,
    }

    exec(code, exec_globals, {})
    doc.recompute()

    base = pathlib.Path(__file__).parent
    out_dir = base / "generated_models"
    out_dir.mkdir(exist_ok=True)
    idx = len(list(out_dir.glob("geom_model_*.FCStd"))) + 1
    file_path = out_dir / f"geom_model_{idx}.FCStd"
    doc.saveAs(str(file_path))
    print("Saved model to:", file_path)

    if os.name == "nt":
        os.startfile(str(file_path))

if __name__ == "__main__":
    main()