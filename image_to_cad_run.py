import os
import pathlib
import FreeCAD, Part

from image_to_primitives import analyze_image, DetectedShape
from cad_primitives import (
    make_box,
    make_plate_with_hole,
    make_tri_prism,
    make_hex_prism,
    make_hex_nut,
)

SCALE_MM_PER_PX = 0.5  # 1 pixel = 0.5 mm (tune later)

def inside_rect(rect, cx, cy) -> bool:
    x, y, w, h = rect["x"], rect["y"], rect["w"], rect["h"]
    return (x <= cx <= x + w) and (y <= cy <= y + h)

def image_to_cad(image_path: str):
    shapes = analyze_image(image_path)
    if not shapes:
        raise RuntimeError("No shapes found in image")

    rects = [s for s in shapes if s.kind == "rect"]
    circles = [s for s in shapes if s.kind == "circle"]
    tris = [s for s in shapes if s.kind == "triangle"]
    hexes = [s for s in shapes if s.kind == "hex"]

    doc = FreeCAD.newDocument("ImageModel")

    # 1) Single rectangle → plate/box
    if len(rects) == 1 and not (circles or tris or hexes):
        r = rects[0].params
        L = r["w"] * SCALE_MM_PER_PX
        W = r["h"] * SCALE_MM_PER_PX
        H = 5.0
        print(f"Pattern: single rect → plate {L:.1f} x {W:.1f} x {H:.1f}")
        shape = make_box(L, W, H)

    # 2) Rectangle + center circle → plate with hole
    elif len(rects) == 1 and len(circles) == 1 and not (tris or hexes):
        r = rects[0].params
        c = circles[0].params
        if not inside_rect(r, c["cx"], c["cy"]):
            raise RuntimeError("Circle is not inside rectangle (no plate-hole pattern)")

        L = r["w"] * SCALE_MM_PER_PX
        W = r["h"] * SCALE_MM_PER_PX
        thickness = 5.0
        hole_radius = c["r"] * SCALE_MM_PER_PX
        print(f"Pattern: rect+circle → plate_with_hole "
              f"L={L:.1f}, W={W:.1f}, t={thickness:.1f}, R={hole_radius:.1f}")
        shape = make_plate_with_hole(L, W, thickness, hole_radius)

    # 3) Single triangle → triangular prism
    elif len(tris) == 1 and not (rects or circles or hexes):
        t = tris[0].params
        base = t["w"] * SCALE_MM_PER_PX
        height = t["h"] * SCALE_MM_PER_PX
        thickness = 10.0
        print(f"Pattern: triangle → tri_prism base={base:.1f}, "
              f"h={height:.1f}, t={thickness:.1f}")
        shape = make_tri_prism(base, height, thickness)

    # 4) Single hex → hex prism
    elif len(hexes) == 1 and not (rects or circles or tris):
        h = hexes[0].params
        flat = max(h["w"], h["h"]) * SCALE_MM_PER_PX
        thickness = 8.0
        print(f"Pattern: single hex → hex_prism flat={flat:.1f}, t={thickness:.1f}")
        shape = make_hex_prism(flat, thickness)

    # 5) Hex + internal circle → hex nut
    elif len(hexes) == 1 and len(circles) == 1 and not (rects or tris):
        h = hexes[0].params
        c = circles[0].params
        if not inside_rect(h, c["cx"], c["cy"]):
            raise RuntimeError("Circle is not inside hex (no nut pattern)")

        flat = max(h["w"], h["h"]) * SCALE_MM_PER_PX
        thickness = min(h["w"], h["h"]) * SCALE_MM_PER_PX * 0.6
        hole_radius = c["r"] * SCALE_MM_PER_PX
        print(f"Pattern: hex+circle → hex_nut flat={flat:.1f}, "
              f"t={thickness:.1f}, R={hole_radius:.1f}")
        shape = make_hex_nut(flat, thickness, hole_radius)

    else:
        raise RuntimeError(f"Shape combination not supported yet: {shapes}")

    Part.show(shape)
    doc.recompute()

    base = pathlib.Path(__file__).parent
    out_dir = base / "generated_models"
    out_dir.mkdir(exist_ok=True)
    idx = len(list(out_dir.glob("img_model_*.FCStd"))) + 1
    file_path = out_dir / f"img_model_{idx}.FCStd"
    doc.saveAs(str(file_path))
    print("Saved model to:", file_path)

    if os.name == "nt":
        os.startfile(str(file_path))

if __name__ == "__main__":
    import sys
    img = sys.argv[1] if len(sys.argv) > 1 else "test_plate_hole.png"
    image_to_cad(img)