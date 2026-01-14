import sys, FreeCAD

# Usage: freecadcmd.exe test_gear_props.py involute / internal / bevel / worm
kind = sys.argv[2] if len(sys.argv) > 2 else "involute"

if kind == "involute":
    import freecad.gears.involutegear as gm
    Class = gm.InvoluteGear
elif kind == "internal":
    import freecad.gears.internalinvolutegear as gm
    Class = gm.InternalInvoluteGear
elif kind == "bevel":
    import freecad.gears.bevelgear as gm
    Class = gm.BevelGear
elif kind == "worm":
    import freecad.gears.wormgear as gm
    Class = gm.WormGear
else:
    raise ValueError(f"Unknown kind: {kind}")

doc = FreeCAD.newDocument("GearProps")
gear = doc.addObject("Part::FeaturePython", "Gear")
Class(gear)

print("Kind:", kind)
print("Properties:", gear.PropertiesList)
for name in gear.PropertiesList:
    try:
        val = getattr(gear, name)
    except Exception:
        continue
    if name.lower() in ("module", "teeth", "teeth1", "teeth2", "width", "height", "thickness", "beta", "helixangle"):
        print(f"  {name} = {val}")