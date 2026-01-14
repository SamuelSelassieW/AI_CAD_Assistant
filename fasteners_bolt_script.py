import sys, FreeCAD, FastenersCmd

# argv: [freecadcmd.exe, script.py, size, length, out_path]
size = sys.argv[2]          # e.g. "M8"
length = sys.argv[3]        # e.g. "40"
out_path = sys.argv[4]

doc = FreeCAD.newDocument("Bolt")
obj = doc.addObject("Part::FeaturePython", "ISO4014_Bolt")
FastenersCmd.FSScrewObject(obj, "ISO4014", None)  # attach proxy + default params
doc.recompute()
obj.Diameter = size
obj.Length = length
doc.recompute()
doc.saveAs(out_path)
FreeCAD.closeDocument(doc.Name)