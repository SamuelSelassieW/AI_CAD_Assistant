from image_to_primitives import analyze_image

shapes = analyze_image("test_plate_hole.png")
print("Detected shapes:", shapes)
for s in shapes:
    print(s.kind, s.params)