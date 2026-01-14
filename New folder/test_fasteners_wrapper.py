import FreeCAD, Part
from cad_primitives import make_fasteners_hex_bolt

doc = FreeCAD.newDocument("TestFastBolt")
shape = make_fasteners_hex_bolt("M8", 40)
Part.show(shape)
doc.recompute()
print("bolt shape ok")