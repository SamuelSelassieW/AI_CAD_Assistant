import sys, FreeCAD
from pathlib import Path

kind = sys.argv[2] if len(sys.argv) > 2 else "spur"
args = sys.argv[3:]

if kind == "spur":      # module, teeth, height, out_path
    import freecad.gears.involutegear as gm
    Class = gm.InvoluteGear
elif kind == "helical":  # module, teeth, height, helix_angle, out_path
    import freecad.gears.involutegear as gm
    Class = gm.InvoluteGear
elif kind == "internal":  # module, teeth, thickness, out_path
    import freecad.gears.internalinvolutegear as gm
    Class = gm.InternalInvoluteGear
elif kind == "bevel":    # module, teeth, height, beta, out_path
    import freecad.gears.bevelgear as gm
    Class = gm.BevelGear
elif kind == "worm":     # module, teeth, height, beta, diameter, out_path
    import freecad.gears.wormgear as gm
    Class = gm.WormGear
else:
    raise ValueError(f"Unknown gear kind: {kind}")

doc = FreeCAD.newDocument("Gear")
gear = doc.addObject("Part::FeaturePython", "Gear")
Class(gear)

if kind == "spur":
    module, teeth, height, out_path = float(args[0]), int(args[1]), float(args[2]), args[3]
    gear.module = module
    gear.num_teeth = teeth
    gear.height = height
    gear.helix_angle = 0.0
    gear.double_helix = False

elif kind == "helical":
    module, teeth, height, helix_angle, out_path = (
        float(args[0]), int(args[1]), float(args[2]), float(args[3]), args[4]
    )
    gear.module = module
    gear.num_teeth = teeth
    gear.height = height
    gear.helix_angle = helix_angle
    gear.double_helix = False

elif kind == "internal":
    module, teeth, thickness, out_path = float(args[0]), int(args[1]), float(args[2]), args[3]
    gear.module = module
    gear.num_teeth = teeth
    gear.thickness = thickness

elif kind == "bevel":
    module, teeth, height, beta, out_path = (
        float(args[0]), int(args[1]), float(args[2]), float(args[3]), args[4]
    )
    gear.module = module
    gear.num_teeth = teeth
    gear.height = height
    gear.beta = beta

elif kind == "worm":
    module, teeth, height, beta, diameter, out_path = (
        float(args[0]), int(args[1]), float(args[2]), float(args[3]), float(args[4]), args[5]
    )
    gear.module = module
    gear.num_teeth = teeth
    gear.height = height
    gear.beta = beta
    gear.diameter = diameter

doc.recompute()
doc.saveAs(out_path)
FreeCAD.closeDocument(doc.Name)