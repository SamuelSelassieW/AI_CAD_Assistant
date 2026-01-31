import sys
from pathlib import Path

import FreeCAD, Part

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from cad_primitives import (
    make_box,
    make_cylinder,
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
    make_cyl_with_hole,
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
)

def main():
    if len(sys.argv) < 3:
        raise SystemExit("Usage: text_model_runner.py <code_file.py> <out.FCStd>")

    code_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    code = code_path.read_text(encoding="utf-8")

    doc = FreeCAD.newDocument("AIModel")

    class _SafePart:
        @staticmethod
        def show(shape):
            obj = doc.addObject("Part::Feature", "AI_Shape")
            obj.Shape = shape

    exec_globals = {
        "__builtins__": {},
        "FreeCAD": FreeCAD,
        "Part": _SafePart,
        "make_box": make_box,
        "make_cylinder": make_cylinder,
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
        "make_cyl_with_hole": make_cyl_with_hole,
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
    }

    exec(code, exec_globals, exec_globals)
    doc.recompute()
    doc.saveAs(str(out_path))


if __name__ == "__main__":
    main()
