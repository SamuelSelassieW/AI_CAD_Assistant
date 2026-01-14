import ScrewMaker
screwMaker = ScrewMaker.Instance
diams = screwMaker.GetAllDiams("ISO4014")
print("ISO4014 diameters:", diams)
lens = screwMaker.GetAllLengths("ISO4014", diams[1], False)
print("ISO4014 lengths for", diams[1], ":", lens[:20])