import FreeCAD, Part, os
from pathlib import Path
from cad_primitives import make_L_bracket, make_flange

base = Path(__file__).parent / "generated_models"
base.mkdir(exist_ok=True)

doc = FreeCAD.newDocument("L_Flange_Test")
Part.show(make_L_bracket(40, 30, 10, 5, fillet_radius=1))
Part.show(make_flange(80, 40, 8, bolt_circle_d=60, bolt_hole_d=8, bolt_count=6))
doc.recompute()

out = base / "test_L_flange.FCStd"
doc.saveAs(str(out))
os.startfile(str(out))