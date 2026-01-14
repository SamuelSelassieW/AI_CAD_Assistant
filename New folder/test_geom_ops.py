import FreeCAD, Part
from geom_ops import box, cyl, translate, union, fillet_all

doc = FreeCAD.newDocument("GeomTest")

b = box(40, 20, 10)
c = cyl(5, 15)
c = translate(c, 20, 10, 0)
shape = union(b, c)
shape = fillet_all(shape, 2)

Part.show(shape)
doc.recompute()
print("OK")