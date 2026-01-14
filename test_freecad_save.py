import FreeCAD, Part
from pathlib import Path

base = Path(__file__).parent
out_dir = base / "generated_models"
print("dir exists:", out_dir.exists(), "is_dir:", out_dir.is_dir())

doc = FreeCAD.newDocument("TestSave")
shape = Part.makeBox(10, 20, 30)
Part.show(shape)
doc.recompute()

file_path = out_dir / "test_save.FCStd"
print("saving to:", file_path)
doc.saveAs(str(file_path))
print("save OK")