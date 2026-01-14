from dataclasses import dataclass
from typing import List, Dict
import cv2, numpy as np

@dataclass
class DetectedShape:
    kind: str              # 'rect', 'circle', 'triangle', 'hex'
    params: Dict[str, float]

def analyze_image(path: str) -> List[DetectedShape]:
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {path}")

    _, th = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    contours, hierarchy = cv2.findContours(
    th, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    shapes: List[DetectedShape] = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 100:
            continue

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        n = len(approx)
        x, y, w, h = cv2.boundingRect(approx)

        if n == 3:
            # triangle
            shapes.append(DetectedShape(
                "triangle",
                {"x": float(x), "y": float(y), "w": float(w), "h": float(h)},
            ))
        elif n == 4:
            # rectangle / square
            shapes.append(DetectedShape(
                "rect",
                {"x": float(x), "y": float(y), "w": float(w), "h": float(h)},
            ))
        elif 5 <= n <= 7:
            # approx hex
            shapes.append(DetectedShape(
                "hex",
                {"x": float(x), "y": float(y), "w": float(w), "h": float(h)},
            ))
        else:
            # round-ish → circle
            circularity = 4 * np.pi * area / (peri * peri + 1e-6)
            if circularity > 0.7:
                (cx, cy), r = cv2.minEnclosingCircle(cnt)
                shapes.append(DetectedShape(
                    "circle",
                    {"cx": float(cx), "cy": float(cy), "r": float(r)},
                ))

    return shapes