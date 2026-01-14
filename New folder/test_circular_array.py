import FreeCAD, Part
from geom_ops import cyl, circular_array

doc = FreeCAD.newDocument("CircArrayTest")

base = cyl(5, 20)
pattern = circular_array(base, n=6, ax=0, ay=0, az=1, total_angle_deg=360, cx=0, cy=0, cz=0)
Part.show(pattern)
doc.recompute()
print("OK")