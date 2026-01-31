from pathlib import Path
import FreeCAD

def generate_drawing_with_dims(model_path) -> Path:
    """
    Create a simple TechDraw page (front + isometric view) for the given
    model .FCStd file and save it next to the model.

    Returns the path to the new drawing .FCStd file.
    """
    from FreeCAD import Vector
    import TechDraw

    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(model_path)

    # open source model
    src_doc = FreeCAD.open(str(model_path))

    solids = [obj for obj in src_doc.Objects if hasattr(obj, "Shape")]
    if not solids:
        FreeCAD.closeDocument(src_doc.Name)
        raise ValueError("Model document contains no solid objects.")

    # new drawing document
    draw_doc = FreeCAD.newDocument("AIDrawing")

    page = draw_doc.addObject("TechDraw::DrawPage", "Page")
    template = draw_doc.addObject("TechDraw::DrawSVGTemplate", "Template")
    template.Template = TechDraw.getStandardTemplateFile(
        "A4_Landscape_ISO7200TD.svg"
    )
    page.Template = template

    # front view
    view_front = draw_doc.addObject("TechDraw::DrawViewPart", "Front")
    view_front.Source = solids
    view_front.Direction = Vector(0, 0, 1)
    page.addView(view_front)

    # isometric view
    view_iso = draw_doc.addObject("TechDraw::DrawViewPart", "Iso")
    view_iso.Source = solids
    view_iso.Direction = Vector(1, 1, 1)
    page.addView(view_iso)

    draw_doc.recompute()

    out_path = model_path.with_name(model_path.stem + "_drawing.FCStd")
    draw_doc.saveAs(str(out_path))

    FreeCAD.closeDocument(src_doc.Name)
    FreeCAD.closeDocument(draw_doc.Name)
    return out_path

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("Usage: drawing_generator_dims.py <model.FCStd>")
    p = generate_drawing_with_dims(sys.argv[1])
    print("Drawing saved to:", p)