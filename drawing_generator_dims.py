import sys
from pathlib import Path
import FreeCAD, Part, TechDraw

def find_template_svg() -> Path:
    base = Path(FreeCAD.getHomePath())
    cand_dirs = [
        base / "data" / "Mod" / "TechDraw" / "Templates",
        base / "Mod" / "TechDraw" / "Templates",
    ]
    for d in cand_dirs:
        if d.is_dir():
            preferred = [
                "A4_Landscape_ISO7200TD.svg",
                "A4_Landscape.svg",
                "A4_LandscapeTD.svg",
            ]
            for name in preferred:
                p = d / name
                if p.is_file():
                    return p
            for p in d.glob("*.svg"):
                return p
    raise FileNotFoundError("Could not find TechDraw template folder")

def generate_drawing_with_dims(model_path: Path) -> Path:
    if not model_path.is_file():
        raise FileNotFoundError(model_path)

    print("Opening model:", model_path)
    doc = FreeCAD.open(str(model_path))

    solids = [o for o in doc.Objects if hasattr(o, "Shape") and o.Shape.Solids]
    if not solids:
        raise RuntimeError("No solid shapes found in document")
    source = solids[0]

    template_svg = find_template_svg()
    print("Using template:", template_svg)

    page = doc.addObject("TechDraw::DrawPage", "Page")
    template = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
    template.Template = str(template_svg)
    page.Template = template

    # front view only (we'll auto-dimension this)
    front = doc.addObject("TechDraw::DrawViewPart", "Front")
    front.Source = [source]
    front.Direction = (0.0, 0.0, 1.0)

    # simple auto scale based on part size
    bb = source.Shape.BoundBox
    maxlen = max(bb.XLength, bb.YLength, bb.ZLength)
    if maxlen > 400:
        scale = 0.25
    elif maxlen > 200:
        scale = 0.5
    else:
        scale = 1.0
    front.Scale = scale
    print("Using view scale:", scale)

    page.addView(front)
    doc.recompute()

    # side view for thickness (uses same scale)
    side = doc.addObject("TechDraw::DrawViewPart", "Side")
    side.Source = [source]
    side.Direction = (1.0, 0.0, 0.0)
    side.Scale = scale
    page.addView(side)
    doc.recompute()

    # Try to add overall width (X) and height (Y) dimensions on the front view.
    try:
        dimX = doc.addObject("TechDraw::DrawViewDimension", "DimWidth")
        dimX.Type = "DistanceX"
        dimX.References2D = [(front, "Vertex1"), (front, "Vertex2")]
        page.addView(dimX)

        dimY = doc.addObject("TechDraw::DrawViewDimension", "DimHeight")
        dimY.Type = "DistanceY"
        dimY.References2D = [(front, "Vertex1"), (front, "Vertex4")]
        page.addView(dimY)

        dimT = doc.addObject("TechDraw::DrawViewDimension", "DimThickness")
        dimT.Type = "DistanceY"
        dimT.References2D = [(side, "Vertex1"), (side, "Vertex4")]
        page.addView(dimT)

        print("Dimensions added (overall width & height).")
    except Exception as e:
        print("Could not add dimensions automatically:", e)

    doc.recompute()

    out_path = model_path.with_name(model_path.stem + "_drawing_dims.FCStd")
    doc.saveAs(str(out_path))
    print("Drawing with dimensions saved to:", out_path)
    return out_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python drawing_generator_dims.py path/to/model.FCStd")
        sys.exit(1)
    model_file = Path(sys.argv[1])
    generate_drawing_with_dims(model_file)