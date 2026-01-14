import sys
from pathlib import Path
import FreeCAD, Part, TechDraw

def find_template_svg() -> Path:
    """Find a TechDraw template SVG in the FreeCAD installation."""
    base = Path(FreeCAD.getHomePath())
    cand_dirs = [
        base / "data" / "Mod" / "TechDraw" / "Templates",
        base / "Mod" / "TechDraw" / "Templates",
    ]
    for d in cand_dirs:
        if d.is_dir():
            # Prefer an A4 landscape template if available
            preferred = [
                "A4_Landscape_ISO7200TD.svg",
                "A4_Landscape.svg",
                "A4_LandscapeTD.svg",
            ]
            for name in preferred:
                p = d / name
                if p.is_file():
                    return p
            # Fallback: first svg in folder
            for p in d.glob("*.svg"):
                return p
    raise FileNotFoundError("Could not find TechDraw template folder")

def generate_basic_drawing(model_path: Path) -> Path:
    """Load a 3D model and create a TechDraw page with front/top/iso views."""
    if not model_path.is_file():
        raise FileNotFoundError(model_path)

    print("Opening model:", model_path)
    doc = FreeCAD.open(str(model_path))

    # pick first solid object in document as the source
    solids = [o for o in doc.Objects if hasattr(o, "Shape") and o.Shape.Solids]
    if not solids:
        raise RuntimeError("No solid shapes found in document")
    source = solids[0]

    # create page + template
    template_svg = find_template_svg()
    print("Using template:", template_svg)

    page = doc.addObject("TechDraw::DrawPage", "Page")
    template = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
    template.Template = str(template_svg)
    page.Template = template

    # front view
    front = doc.addObject("TechDraw::DrawViewPart", "Front")
    front.Source = [source]
    front.Direction = (0.0, 0.0, 1.0)
    page.addView(front)

    # top view
    top = doc.addObject("TechDraw::DrawViewPart", "Top")
    top.Source = [source]
    top.Direction = (0.0, -1.0, 0.0)
    page.addView(top)

    # isometric view
    iso = doc.addObject("TechDraw::DrawViewPart", "Iso")
    iso.Source = [source]
    iso.Direction = (1.0, -1.0, 1.0)
    page.addView(iso)

    doc.recompute()

    # save as a new FCStd file next to the model
    out_path = model_path.with_name(model_path.stem + "_drawing.FCStd")
    doc.saveAs(str(out_path))
    print("Drawing saved to:", out_path)
    return out_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python drawing_generator.py path/to/model.FCStd")
        sys.exit(1)
    model_file = Path(sys.argv[1])
    generate_basic_drawing(model_file)