import os
import pathlib

import FreeCAD, Part
from cad_code_ai_local import generate_cad_code
from cad_primitives import (
    make_box,
    make_cylinder,
    make_cyl_with_hole,
    make_tri_prism,
    make_plate_with_hole,
    make_hex_prism,
    make_hex_nut,
    make_hex_bolt,
    make_screw_blank,
    make_slotted_screw,
    make_cross_screw,
    make_socket_head_screw,
    make_fasteners_hex_bolt,
    make_flange,
    make_spur_gear,
    make_helical_gear,
    make_internal_gear,
    make_bevel_gear,
    make_worm_gear,
    # new helpers
    make_rect_tube,
    make_pipe,
    make_stepped_shaft,
    make_flat_bar_2holes,
    make_drum_with_flange,
    make_shaft_with_keyway,
    make_plate_with_slot,
    make_plate_with_pocket,
    make_v_pulley,
)


def main():
    desc = input("Describe a part: ")
    code = generate_cad_code(desc)

    print("\n--- GENERATED CODE ---")
    print(code)

    # New FreeCAD document
    doc = FreeCAD.newDocument("AIModel")

    # Safe wrapper: only allow Part.show(shape)
    class _SafePart:
        @staticmethod
        def show(shape):
            Part.show(shape)

    # Names available to the generated code (sandboxed)
    exec_globals = {
        "__builtins__": {},
        "FreeCAD": FreeCAD,
        "Part": _SafePart,
        "make_box": make_box,
        "make_cylinder": make_cylinder,
        "make_cyl_with_hole": make_cyl_with_hole,
        "make_tri_prism": make_tri_prism,
        "make_plate_with_hole": make_plate_with_hole,
        "make_hex_prism": make_hex_prism,
        "make_hex_nut": make_hex_nut,
        "make_hex_bolt": make_hex_bolt,
        "make_screw_blank": make_screw_blank,
        "make_slotted_screw": make_slotted_screw,
        "make_cross_screw": make_cross_screw,
        "make_socket_head_screw": make_socket_head_screw,
        "make_fasteners_hex_bolt": make_fasteners_hex_bolt,
        "make_flange": make_flange,
        "make_spur_gear": make_spur_gear,
        "make_helical_gear": make_helical_gear,
        "make_internal_gear": make_internal_gear,
        "make_bevel_gear": make_bevel_gear,
        "make_worm_gear": make_worm_gear,
        "make_rect_tube": make_rect_tube,
        "make_pipe": make_pipe,
        "make_stepped_shaft": make_stepped_shaft,
        "make_flat_bar_2holes": make_flat_bar_2holes,
        "make_drum_with_flange": make_drum_with_flange,
        "make_shaft_with_keyway": make_shaft_with_keyway,
        "make_plate_with_slot": make_plate_with_slot,
        "make_plate_with_pocket": make_plate_with_pocket,
         "make_v_pulley": make_v_pulley,
    }

    exec(code, exec_globals, {})
    doc.recompute()

    base = pathlib.Path(__file__).parent
    out_dir = base / "generated_models"
    out_dir.mkdir(exist_ok=True)
    idx = len(list(out_dir.glob("model_*.FCStd"))) + 1
    file_path = out_dir / f"model_{idx}.FCStd"

    doc.saveAs(str(file_path))
    print(f"Saved model to: {file_path}")

    if os.name == "nt":
        os.startfile(str(file_path))


if __name__ == "__main__":
    main()
