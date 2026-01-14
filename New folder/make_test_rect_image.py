import cv2, numpy as np
from pathlib import Path

base = Path(__file__).parent
img = np.zeros((256,256), np.uint8)
cv2.rectangle(img, (40,70), (220,190), 255, -1)   # plate
cv2.circle(img, (130,130), 30, 0, -1)             # hole
out = base/"test_plate_hole.png"
cv2.imwrite(str(out), img)
print("saved:", out)