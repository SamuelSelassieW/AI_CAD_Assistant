import sys, os
from pathlib import Path

FREECAD_CANDIDATES = [
    r"C:\Program Files\FreeCAD 1.0\bin",
    r"C:\Program Files\FreeCAD 1.0\lib",
    r"C:\Program Files\FreeCAD 0.21\bin",
    r"C:\Program Files\FreeCAD 0.21\lib",
]

for p in FREECAD_CANDIDATES:
    if os.path.isdir(p):
        if p not in sys.path:
            sys.path.append(p)
        # make sure DLLs in these folders can be loaded
        try:
            os.add_dll_directory(p)
        except AttributeError:
            os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")

try:
    import FreeCAD, Part  # verify both
except ImportError:
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "FreeCAD not found",
            "FreeCAD (and its Part module) were not found.\n"
            "Please install FreeCAD 1.0 (or 0.21) in Program Files\n"
            "and try again.",
        )
        root.destroy()
    except Exception:
        print("FreeCAD/Part not found. Please install FreeCAD 1.0/0.21.", file=sys.stderr)
    sys.exit(1)

import app_gui

if __name__ == "__main__":
    app_gui.main()