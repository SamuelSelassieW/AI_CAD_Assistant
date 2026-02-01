import sys, os, webbrowser, logging, traceback, textwrap, subprocess
from pathlib import Path

# ---------- Paths & logging setup ----------

# When running from PyInstaller, use the folder that contains the .exe.
# When running from source, use the folder that contains app_gui.py.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent


def setup_freecad_env():
    """
    Make sure the embedded Python process can find the FreeCAD DLLs and modules.

    We:
      - look for a FreeCAD installation (env var or common paths),
      - add its bin/ and lib/ to the DLL search path,
      - insert lib/ at the *front* of sys.path so we prefer the system FreeCAD
        over any partially-bundled copy inside _internal.
    """
    candidates: list[Path] = []

    # If user has a custom FreeCAD path in env vars, prefer that
    env_home = (
        os.environ.get("FREECAD_HOME")
        or os.environ.get("FREECAD_DIR")
        or os.environ.get("FREECAD_BASE")
    )
    if env_home:
        candidates.append(Path(env_home))

    # Common Windows install locations (adjust/add as needed)
    candidates.extend([
        Path(r"C:\Program Files\FreeCAD 1.0"),
        Path(r"C:\Program Files\FreeCAD 0.21.2"),
        Path(r"C:\Program Files\FreeCAD 0.21.1"),
        Path(r"C:\Program Files\FreeCAD 0.21"),
    ])

    for base in candidates:
        if not base.exists():
            continue

        bin_dir = base / "bin"
        lib_dir = base / "lib"

        for d in (bin_dir, lib_dir):
            if d.exists():
                # Add to DLL search path (for native .dll dependencies)
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(str(d))
                    except Exception:
                        # ignore if this fails; PATH may still work
                        pass

        # Make sure Python searches lib/ *before* PyInstaller's _internal
        if lib_dir.exists():
            lib_str = str(lib_dir)
            if lib_str not in sys.path:
                sys.path.insert(0, lib_str)

        # We found one working base, no need to try the rest
        break


# If running from the PyInstaller build, also add the _internal folder
# (where PyInstaller puts most .pyd/.dll files) to the DLL search path.
if getattr(sys, "frozen", False):
    internal_dir = BASE_DIR / "_internal"
    if internal_dir.exists():
        try:
            os.add_dll_directory(str(internal_dir))
        except Exception:
            pass

# NOTE: we call setup_freecad_env() *after* importing PyQt6 to avoid DLL conflicts.

MODELS_DIR = BASE_DIR / "generated_models"
MODELS_DIR.mkdir(exist_ok=True)

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOGS_DIR / "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("ai_cad_app")

# ---------- Other imports ----------

from license_utils import load_state, is_pro, can_use_pro_feature, consume_pro_credit

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPlainTextEdit, QPushButton, QComboBox, QStatusBar,
    QFileDialog, QMessageBox, QDialog, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, QEasingCurve, QPropertyAnimation, pyqtProperty
from PyQt6.QtGui import QPixmap, QColor, QPalette

# Now that PyQt is imported and its Qt DLLs are loaded, we can safely
# adjust the DLL search paths for FreeCAD.
setup_freecad_env()

# Try to import FreeCAD; if not available, keep running but disable generation features
try:
    import FreeCAD, Part
    FREECAD_AVAILABLE = True
    FREECAD_ERROR = ""
    logger.info("FreeCAD imported successfully.")
except Exception as e:
    FreeCAD = None
    Part = None
    FREECAD_AVAILABLE = False
    FREECAD_ERROR = str(e)
    logger.warning("FreeCAD import FAILED: %s", FREECAD_ERROR)

from cad_code_ai_local import (
    generate_cad_code,
    AmbiguousPartError,
    UnsupportedPartError,
)
from cad_primitives import (
    make_box,
    make_cylinder,
    make_tri_prism,
    make_plate_with_hole,
    make_hex_prism,
    make_hex_nut,
    make_hex_bolt,
    make_screw_blank,
    make_slotted_screw,
    make_cross_screw,
    make_socket_head_screw,
    make_fasteners_hex_bolt,
    make_cyl_with_hole,
    make_flange,
    make_spur_gear,
    make_helical_gear,
    make_internal_gear,
    make_bevel_gear,
    make_worm_gear,
    # new helpers
    make_rect_tube,
    make_pipe,
    make_stepped_shaft,
    make_flat_bar_2holes,
    make_drum_with_flange,
    make_shaft_with_keyway,
    make_plate_with_slot,
    make_plate_with_pocket,
    FREECADCMD,      # from cad_primitives
)
from drawing_generator_dims import generate_drawing_with_dims
from image_to_cad_run import image_to_cad


# ---------- Toast notification widget ----------

class ToastWidget(QWidget):
    """Small notification banner that appears at the top and auto-hides."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._opacity = 1.0

        # Transparent widget; we draw only the inner frame
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Inner frame: the visible rectangle
        self.frame = QFrame(self)
        self.frame.setObjectName("toastFrame")
        frame_layout = QHBoxLayout(self.frame)
        frame_layout.setContentsMargins(16, 8, 16, 8)

        self.label = QLabel("")
        frame_layout.addWidget(self.label)

        outer_layout.addWidget(self.frame)

        self.set_success_style()

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

        self.anim = QPropertyAnimation(self, b"opacity", self)
        self.anim.setDuration(400)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.hide()

    def set_success_style(self):
        self.frame.setStyleSheet("""
            QFrame#toastFrame {
                background-color: rgba(15, 23, 42, 0.3);
                border: 1px solid #22c55e;
                border-radius: 8px;
            }
        """)
        self.label.setStyleSheet("color: #bbf7d0; font-weight: 600;")

    def set_error_style(self):
        self.frame.setStyleSheet("""
            QFrame#toastFrame {
                background-color: rgba(15, 23, 42, 0.0);
                border: 1px solid #f97373;
                border-radius: 8px;
            }
        """)
        self.label.setStyleSheet("color: #fecaca; font-weight: 600;")

    @pyqtProperty(float)
    def opacity(self):
        return self._opacity

    @opacity.setter
    def opacity(self, value: float):
        self._opacity = value
        self.setWindowOpacity(value)

    def show_message(self, text: str, kind: str = "success", duration_ms: int = 3000):
        if kind == "success":
            self.set_success_style()
        elif kind == "error":
            self.set_error_style()

        self.label.setText(text)

        parent = self.parentWidget()
        if parent:
            pw = parent.width()
            self.adjustSize()
            w = self.width()
            self.move((pw - w) // 2, 10)

        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()

        self.anim.stop()
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.timer.stop()
        self.timer.start(duration_ms)
        self.anim.start()


# ---------- Tabs ----------

class TextToModelTab(QWidget):
    def __init__(self, main_window: QMainWindow):
        super().__init__()
        self.main = main_window
        self.last_model_path: Path | None = None

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # -------- Left card --------
        left = QFrame()
        left.setObjectName("card")
        l_layout = QVBoxLayout(left)
        l_layout.setContentsMargins(16, 16, 16, 16)
        l_layout.setSpacing(8)

        title = QLabel("Describe Your Part")
        title.setObjectName("cardTitle")
        l_layout.addWidget(title)

        subtitle = QLabel("Describe what you want to create in plain English.")
        subtitle.setObjectName("secondaryText")
        l_layout.addWidget(subtitle)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText(
            "Example: a rectangular tube frame member, or a shaft with keyway..."
        )
        self.prompt_edit.setMinimumHeight(160)
        l_layout.addWidget(self.prompt_edit)

        ex_row = QHBoxLayout()
        ex_label = QLabel("Quick examples:")
        ex_label.setObjectName("secondaryText")
        ex_row.addWidget(ex_label)

        self.example_combo = QComboBox()
        self.example_combo.addItems([
            "an M8 hex head bolt 40mm long using fasteners",
            "a rectangular tube 500mm long, 40mm wide, 30mm high with 3mm wall",
            "a shaft 25mm diameter and 200mm long with a 6mm wide, 3mm deep keyway",
            "a circular flange outer 80mm, inner 40mm, 8mm thick with 6 bolt holes "
            "of 8mm on a 60mm bolt circle",
            "a plate 100 by 40 by 8mm with a central slot 10mm wide leaving 15mm at each end",
        ])
        ex_row.addWidget(self.example_combo)

        ex_insert = QPushButton("Insert example")
        ex_insert.clicked.connect(self.insert_example)
        ex_row.addWidget(ex_insert)
        l_layout.addLayout(ex_row)

        self.generate_btn = QPushButton("Generate Model")
        self.generate_btn.clicked.connect(self.on_generate)
        l_layout.addWidget(self.generate_btn)

        if not self.main.freecad_available:
            self.generate_btn.setEnabled(False)

        if self.main.freecad_available:
            hint_text = "Generation may take 30–60 seconds."
        else:
            hint_text = "FreeCAD not found. Install FreeCAD to enable model generation."

        self.hint_label = QLabel(hint_text)
        self.hint_label.setObjectName("secondaryText")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        l_layout.addWidget(self.hint_label)

        # Help link: how to write good descriptions
        tips_row = QHBoxLayout()
        self.tips_btn = QPushButton("How to describe your part")
        self.tips_btn.setFlat(True)
        self.tips_btn.setStyleSheet(
            "color: #60a5fa; text-decoration: underline; border: none; padding: 0;"
        )
        self.tips_btn.clicked.connect(self.show_prompt_help)
        tips_row.addWidget(self.tips_btn)
        tips_row.addStretch()
        l_layout.addLayout(tips_row)

        splitter.addWidget(left)

        # -------- Right card --------
        right = QFrame()
        right.setObjectName("card")
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(16, 16, 16, 16)
        r_layout.setSpacing(8)

        r_title = QLabel("Generated CAD Code")
        r_title.setObjectName("cardTitle")
        r_layout.addWidget(r_title)

        self.code_view = QPlainTextEdit()
        self.code_view.setReadOnly(True)
        self.code_view.setMinimumHeight(160)
        self.code_view.setPlaceholderText("Generated code will appear here.")
        r_layout.addWidget(self.code_view)

        self.model_label = QLabel("Model: not generated yet")
        self.model_label.setObjectName("secondaryText")
        self.path_label = QLabel("Saved to: —")
        self.path_label.setObjectName("secondaryText")
        r_layout.addWidget(self.model_label)
        r_layout.addWidget(self.path_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.open_btn = QPushButton("Open in FreeCAD")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_in_freecad)
        btn_row.addWidget(self.open_btn)

        self.export_btn = QPushButton("Export STEP")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_step)
        btn_row.addWidget(self.export_btn)

        r_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def insert_example(self):
        self.prompt_edit.setPlainText(self.example_combo.currentText())

    def show_prompt_help(self):
        dlg = PromptHelpDialog(self.main)
        dlg.exec()

    def on_generate(self):
        if not self.main.freecad_available:
            QMessageBox.warning(
                self,
                "FreeCAD not available",
                "FreeCAD is not installed or its Python libraries could not be imported.\n"
                "Please install FreeCAD and restart the AI CAD Assistant.",
            )
            return

        desc = self.prompt_edit.toPlainText().strip()
        if not desc:
            self.main.statusBar().showMessage("Please enter a description.", 4000)
            return

        # --- gear ambiguity check BEFORE calling the AI --------------------
        desc_norm = desc.lower()
        if "gear" in desc_norm:
            has_type = any(
                w in desc_norm
                for w in ["spur", "helical", "worm", "screw gear", "bevel", "internal"]
            )
            if not has_type:
                msg = (
                    "Part not well defined. Please specify the gear type "
                    "(spur, helical, bevel, worm, internal).\n"
                    'Example: "spur gear module 2 with 20 teeth and 10mm width".'
                )
                self.code_view.setPlainText(msg)
                QMessageBox.information(self, "Part not well defined", msg)
                self.main.statusBar().showMessage(msg, 8000)
                if hasattr(self.main, "toast"):
                    self.main.toast.show_message(msg, kind="error")
                return
        # -------------------------------------------------------------------

        logger.info("Text → Model generation started. Description: %s", desc)

        self.generate_btn.setEnabled(False)
        self.main.statusBar().showMessage("Generating model...", 0)
        if hasattr(self.main, "toast"):
            self.main.toast.show_message("Generating model, please wait...", kind="success")
        QApplication.processEvents()

        try:
            code = generate_cad_code(desc)
            self.code_view.setPlainText(code)

            if getattr(sys, "frozen", False):
                self._generate_via_freecadcmd(code)
            else:
                self._generate_in_process(code)

            logger.info("Text → Model generation succeeded. Saved to %s", self.last_model_path)

            if hasattr(self.main, "toast"):
                self.main.toast.show_message("Model generated successfully!", kind="success")

        except AmbiguousPartError as e:
            msg = str(e) or (
                "Part not well defined. Please specify the gear type "
                "(spur, helical, bevel, worm, internal)."
            )
            self.code_view.setPlainText(msg)
            QMessageBox.information(self, "Part not well defined", msg)
            self.main.statusBar().showMessage(msg, 8000)
            if hasattr(self.main, "toast"):
                self.main.toast.show_message(msg, kind="error")

        except UnsupportedPartError as e:
            msg = str(e) or (
                "Object not found in library; can't generate this figure for now."
            )
            self.code_view.setPlainText(msg)
            QMessageBox.information(self, "Object not found", msg)
            self.main.statusBar().showMessage(msg, 8000)
            if hasattr(self.main, "toast"):
                self.main.toast.show_message(msg, kind="error")

        except Exception as e:
            logger.exception("Error generating model from text.")
            tb = traceback.format_exc()
            short_tb = "\n".join(tb.splitlines()[-15:])
            QMessageBox.critical(self, "Error generating model", short_tb)
            self.main.statusBar().showMessage(f"Error: {e}", 8000)
            if hasattr(self.main, "toast"):
                self.main.toast.show_message("Error generating model", kind="error")
        finally:
            self.generate_btn.setEnabled(True)

    def _generate_in_process(self, code: str):
        """Run the CAD code using the embedded FreeCAD (Python run only)."""
        doc = FreeCAD.newDocument("AIModel")

        class _SafePart:
            @staticmethod
            def show(shape):
                doc_inner = FreeCAD.ActiveDocument
                if doc_inner is None:
                    doc_inner = FreeCAD.newDocument("AIModel")
                obj = doc_inner.addObject("Part::Feature", "AI_Shape")
                obj.Shape = shape

        exec_globals = {
            "__builtins__": {},
            "FreeCAD": FreeCAD,
            "Part": _SafePart,
            "make_box": make_box,
            "make_cylinder": make_cylinder,
            "make_tri_prism": make_tri_prism,
            "make_plate_with_hole": make_plate_with_hole,
            "make_hex_prism": make_hex_prism,
            "make_hex_nut": make_hex_nut,
            "make_hex_bolt": make_hex_bolt,
            "make_screw_blank": make_screw_blank,
            "make_slotted_screw": make_slotted_screw,
            "make_cross_screw": make_cross_screw,
            "make_socket_head_screw": make_socket_head_screw,
            "make_fasteners_hex_bolt": make_fasteners_hex_bolt,
            "make_cyl_with_hole": make_cyl_with_hole,
            "make_flange": make_flange,
            "make_spur_gear": make_spur_gear,
            "make_helical_gear": make_helical_gear,
            "make_internal_gear": make_internal_gear,
            "make_bevel_gear": make_bevel_gear,
            "make_worm_gear": make_worm_gear,
            "make_rect_tube": make_rect_tube,
            "make_pipe": make_pipe,
            "make_stepped_shaft": make_stepped_shaft,
            "make_flat_bar_2holes": make_flat_bar_2holes,
            "make_drum_with_flange": make_drum_with_flange,
            "make_shaft_with_keyway": make_shaft_with_keyway,
            "make_plate_with_slot": make_plate_with_slot,
            "make_plate_with_pocket": make_plate_with_pocket,
        }

        exec(code, exec_globals, exec_globals)
        doc.recompute()

        idx = len(list(MODELS_DIR.glob("model_*.FCStd"))) + 1
        file_path = MODELS_DIR / f"model_{idx}.FCStd"
        doc.saveAs(str(file_path))

        self.last_model_path = file_path
        self.model_label.setText("Model: created")
        self.path_label.setText(f"Saved to: {file_path}")
        self.open_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.main.statusBar().showMessage(f"Saved model to: {file_path}", 5000)

    def _generate_via_freecadcmd(self, code: str):
        """
        Run the CAD code via external freecadcmd (used in the frozen .exe).

        We write a full Python script (imports + helper Part.show + your code +
        save) to _temp/gen_code.py and call:

            freecadcmd.exe gen_code.py

        For simplicity on this machine, we point FreeCAD's Python to the
        original project folder C:\\AI_CAD_Assistant so it can import
        cad_primitives.py from there.
        """
        # Where to store the final model
        idx = len(list(MODELS_DIR.glob("model_*.FCStd"))) + 1
        out_path = MODELS_DIR / f"model_{idx}.FCStd"

        # Temp script path
        temp_dir = MODELS_DIR / "_temp"
        temp_dir.mkdir(exist_ok=True)
        script_path = temp_dir / "gen_code.py"

        # Absolute path to the source project (where cad_primitives.py lives)
        src_dir_literal = r"C:\AI_CAD_Assistant"
        out_literal = repr(str(out_path))

        header = f"""import sys
from pathlib import Path
import FreeCAD, Part

SOURCE_DIR = Path(r\"\"\"{src_dir_literal}\"\"\")
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from cad_primitives import (
    make_box,
    make_cylinder,
    make_tri_prism,
    make_plate_with_hole,
    make_hex_prism,
    make_hex_nut,
    make_hex_bolt,
    make_screw_blank,
    make_slotted_screw,
    make_cross_screw,
    make_socket_head_screw,
    make_fasteners_hex_bolt,
    make_cyl_with_hole,
    make_flange,
    make_spur_gear,
    make_helical_gear,
    make_internal_gear,
    make_bevel_gear,
    make_worm_gear,
    make_rect_tube,
    make_pipe,
    make_stepped_shaft,
    make_flat_bar_2holes,
    make_drum_with_flange,
    make_shaft_with_keyway,
    make_plate_with_slot,
    make_plate_with_pocket,
)

doc = FreeCAD.newDocument("AIModel")
                                
class _SafePart:            
    @staticmethod
    def show(shape):
        obj = doc.addObject("Part::Feature", "AI_Shape")
        obj.Shape = shape

Part = _SafePart
"""

        footer = f"""

doc.recompute()
doc.saveAs({out_literal})
"""

        script_text = header + "\n" + code + "\n" + footer
        script_path.write_text(script_text, encoding="utf-8")

        cmd = [FREECADCMD, str(script_path)]
        logger.info("Running freecadcmd for Text → Model: %s", " ".join(cmd))

        result = subprocess.run(cmd, check=False, capture_output=True, text=True)

        if result.returncode != 0 or not out_path.exists():
            msg = (
                "freecadcmd failed while generating the model.\n"
                f"Command: {' '.join(cmd)}\n"
                f"Exit code: {result.returncode}\n\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )
            raise RuntimeError(msg)

        self.last_model_path = out_path
        self.model_label.setText("Model: created")
        self.path_label.setText(f"Saved to: {out_path}")
        self.open_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.main.statusBar().showMessage(f"Saved model to: {out_path}", 5000)

    def open_in_freecad(self):
        if self.last_model_path and self.last_model_path.exists():
            logger.info("Opening model in FreeCAD: %s", self.last_model_path)
            if hasattr(self.main, "toast"):
                self.main.toast.show_message("Opening in FreeCAD, please wait...", kind="success")
            os.startfile(str(self.last_model_path))

    def export_step(self):
        if not self.main.freecad_available:
            QMessageBox.warning(
                self,
                "FreeCAD not available",
                "STEP export requires FreeCAD. Install FreeCAD and restart the app.",
            )
            return

        state = self.main.lic_state
        if not can_use_pro_feature(state):
            QMessageBox.information(
                self,
                "Trial limit reached",
                "You have used your 3 free advanced exports.\n"
                "Please upgrade or buy more credits to continue.",
            )
            return

        if not self.last_model_path or not self.last_model_path.exists():
            QMessageBox.warning(self, "Export STEP", "No model available to export.")
            return

        try:
            if hasattr(self.main, "toast"):
                self.main.toast.show_message("Exporting STEP, please wait...", kind="success")

            consume_pro_credit(state)
            step_path = self.last_model_path.with_suffix(".step")
            logger.info("Exporting STEP: %s", step_path)

            doc = FreeCAD.open(str(self.last_model_path))
            Part.export(doc.Objects, str(step_path))
            FreeCAD.closeDocument(doc.Name)
            os.startfile(str(step_path))
            self.main.statusBar().showMessage(f"Exported STEP to: {step_path}", 5000)

            if hasattr(self.main, "toast"):
                self.main.toast.show_message("STEP exported successfully!", kind="success")
        except Exception as e:
            logger.exception("Error exporting STEP.")
            QMessageBox.critical(self, "Export STEP failed", str(e))
            if hasattr(self.main, "toast"):
                self.main.toast.show_message("Error exporting STEP", kind="error")


class ImageToModelTab(QWidget):
    def __init__(self, main_window: QMainWindow):
        super().__init__()
        self.main = main_window
        self.image_path: Path | None = None
        self.model_path: Path | None = None

        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel("Image → Model (Experimental)")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        subtitle = QLabel("Upload a simple sketch or orthographic view. Results may be approximate.")
        subtitle.setObjectName("secondaryText")
        layout.addWidget(subtitle)

        btn_row = QHBoxLayout()
        self.load_btn = QPushButton("Load image / sketch…")
        self.load_btn.clicked.connect(self.load_image)
        self.gen_btn = QPushButton("Detect & Generate Model")
        self.gen_btn.setEnabled(False)
        self.gen_btn.clicked.connect(self.on_generate)
        if not self.main.freecad_available:
            self.gen_btn.setEnabled(False)
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.gen_btn)
        layout.addLayout(btn_row)

        self.preview = QLabel("No image loaded.")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(250)
        self.preview.setObjectName("imagePreview")
        layout.addWidget(self.preview)

        self.info_label = QLabel("Model: (none)")
        self.info_label.setObjectName("secondaryText")
        self.path_label = QLabel("Path: (none)")
        self.path_label.setObjectName("secondaryText")
        layout.addWidget(self.info_label)
        layout.addWidget(self.path_label)

        open_row = QHBoxLayout()
        self.open_btn = QPushButton("Open in FreeCAD")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_model)
        open_row.addStretch()
        open_row.addWidget(self.open_btn)
        layout.addLayout(open_row)

        outer = QVBoxLayout(self)
        outer.addWidget(card)

    def load_image(self):
        fname, _ = QFileDialog.getOpenFileName(
            self,
            "Select image",
            str(BASE_DIR),
            "Images (*.png *.jpg *.jpeg *.bmp);;All files (*.*)",
        )
        if not fname:
            return
        self.image_path = Path(fname)
        pix = QPixmap(fname)
        if not pix.isNull():
            self.preview.setPixmap(
                pix.scaled(
                    400,
                    300,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.preview.setText(f"Loaded: {fname}")
        if self.main.freecad_available:
            self.gen_btn.setEnabled(True)
        self.main.statusBar().showMessage(f"Loaded image: {fname}", 4000)
        logger.info("Loaded image for Image → Model: %s", fname)

    def on_generate(self):
        if not self.main.freecad_available:
            QMessageBox.warning(
                self,
                "FreeCAD not available",
                "Generating a model from an image requires FreeCAD.\n"
                "Please install FreeCAD and restart the AI CAD Assistant.",
            )
            return

        if not self.image_path or not self.image_path.exists():
            self.main.statusBar().showMessage("No valid image selected.", 4000)
            return
        self.main.statusBar().showMessage("Generating model from image...", 0)
        if hasattr(self.main, "toast"):
            self.main.toast.show_message(
                "Generating from image, please wait...", kind="success"
            )
        QApplication.processEvents()

        logger.info("Image → Model generation started. Image: %s", self.image_path)

        try:
            result = image_to_cad(str(self.image_path))
            if isinstance(result, (str, Path)):
                self.model_path = Path(result)
            else:
                fcstd_files = sorted(MODELS_DIR.glob("*.FCStd"))
                self.model_path = fcstd_files[-1] if fcstd_files else None

            if not self.model_path:
                self.main.statusBar().showMessage("No model created.", 5000)
                logger.warning("Image → Model: no model created.")
                return

            self.info_label.setText("Model created from image.")
            self.path_label.setText(f"Path: {self.model_path}")
            self.open_btn.setEnabled(True)
            self.main.statusBar().showMessage(
                f"Saved model to: {self.model_path}", 5000
            )

            logger.info("Image → Model succeeded. Model at %s", self.model_path)

            if hasattr(self.main, "toast"):
                self.main.toast.show_message(
                    "Image-based model created!", kind="success"
                )
        except Exception as e:
            logger.exception("Error generating model from image.")
            self.main.statusBar().showMessage(f"Error: {e}", 8000)
            if hasattr(self.main, "toast"):
                self.main.toast.show_message(
                    "Error generating from image", kind="error"
                )

    def open_model(self):
        if self.model_path and self.model_path.exists():
            logger.info("Opening image-based model in FreeCAD: %s", self.model_path)
            if hasattr(self.main, "toast"):
                self.main.toast.show_message(
                    "Opening in FreeCAD, please wait...", kind="success"
                )
            os.startfile(str(self.model_path))


class ModelToDrawingTab(QWidget):
    def __init__(self, main_window: QMainWindow):
        super().__init__()
        self.main = main_window
        self.drawing_path: Path | None = None

        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel("Model → Drawing")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Select a generated model and create a basic engineering drawing."
        )
        subtitle.setObjectName("secondaryText")
        layout.addWidget(subtitle)

        layout.addWidget(QLabel("Select model from generated_models:"))
        self.model_combo = QComboBox()
        layout.addWidget(self.model_combo)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh list")
        self.refresh_btn.clicked.connect(self.refresh_models)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch()
        self.gen_btn = QPushButton("Generate Drawing")
        self.gen_btn.clicked.connect(self.on_generate)
        if not self.main.freecad_available:
            self.gen_btn.setEnabled(False)
        btn_row.addWidget(self.gen_btn)
        self.open_btn = QPushButton("Open Drawing")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_drawing)
        btn_row.addWidget(self.open_btn)
        layout.addLayout(btn_row)

        self.path_label = QLabel("Drawing: (none)")
        self.path_label.setObjectName("secondaryText")
        layout.addWidget(self.path_label)

        outer = QVBoxLayout(self)
        outer.addWidget(card)

        self.refresh_models()

    def refresh_models(self):
        self.model_combo.clear()
        fcstd_files = sorted(MODELS_DIR.glob("*.FCStd"))
        for p in fcstd_files:
            self.model_combo.addItem(p.name, p)
        if not fcstd_files:
            self.model_combo.addItem("(no models)", None)
        logger.info(
            "Model list refreshed for Model → Drawing. %d models found.",
            len(fcstd_files),
        )

    def on_generate(self):
        if not self.main.freecad_available:
            QMessageBox.warning(
                self,
                "FreeCAD not available",
                "Drawing generation requires FreeCAD and its TechDraw workbench.\n"
                "Please install FreeCAD and restart the AI CAD Assistant.",
            )
            return

        state = self.main.lic_state
        if not can_use_pro_feature(state):
            QMessageBox.information(
                self,
                "Trial limit reached",
                "You have used your 3 free advanced actions.\n"
                "Please upgrade or buy more credits to generate more drawings.",
            )
            return
        data = self.model_combo.currentData()
        if data is None or not Path(data).exists():
            self.main.statusBar().showMessage("No valid model selected.", 4000)
            return

        model_path = Path(data)
        logger.info("Model → Drawing generation started for %s", model_path)

        self.main.statusBar().showMessage("Generating drawing...", 0)
        if hasattr(self.main, "toast"):
            self.main.toast.show_message(
                "Generating drawing, please wait...", kind="success"
            )
        QApplication.processEvents()
        try:
            consume_pro_credit(state)
            out_path = generate_drawing_with_dims(model_path)
            self.drawing_path = out_path
            self.path_label.setText(f"Drawing: {out_path}")
            self.open_btn.setEnabled(True)
            self.main.statusBar().showMessage(
                f"Saved drawing to: {out_path}", 5000
            )

            logger.info("Model → Drawing succeeded. Drawing at %s", out_path)

            if hasattr(self.main, "toast"):
                self.main.toast.show_message(
                    "Drawing generated successfully!", kind="success"
                )
        except Exception as e:
            logger.exception("Error generating drawing.")
            self.main.statusBar().showMessage(f"Error: {e}", 8000)
            if hasattr(self.main, "toast"):
                self.main.toast.show_message(
                    "Error generating drawing", kind="error"
                )

    def open_drawing(self):
        if self.drawing_path and self.drawing_path.exists():
            logger.info("Opening drawing in FreeCAD: %s", self.drawing_path)
            if hasattr(self.main, "toast"):
                self.main.toast.show_message(
                    "Opening drawing in FreeCAD, please wait...", kind="success"
                )
            os.startfile(str(self.drawing_path))


# ---------- Prompt help dialog ----------

class PromptHelpDialog(QDialog):
    """Dialog with tips on how to describe parts for better results."""

    def __init__(self, main: QMainWindow):
        super().__init__(main)
        self.setWindowTitle("How to describe your part")
        self.setModal(True)
        self.resize(520, 420)

        layout = QVBoxLayout(self)

        text = """
<b>Guidelines for good part descriptions</b><br><br>
1. <b>Start with the base shape</b><br>
&nbsp;&nbsp;&nbsp;Examples: plate, block, cylinder, flange, bracket, gear, nut, bolt,
&nbsp;&nbsp;&nbsp;rectangular tube, shaft, roller, link, drum...<br><br>
2. <b>Always give key dimensions in millimetres (mm)</b><br>
&nbsp;&nbsp;&nbsp;• overall lengths / widths / heights<br>
&nbsp;&nbsp;&nbsp;• diameters (outer, inner, holes, shafts)<br>
&nbsp;&nbsp;&nbsp;• thicknesses and face widths<br><br>
3. <b>For holes, slots and pockets, specify:</b><br>
&nbsp;&nbsp;&nbsp;• how many (e.g. 2 holes, one slot)<br>
&nbsp;&nbsp;&nbsp;• diameter / width / depth<br>
&nbsp;&nbsp;&nbsp;• pattern/location (e.g. at each end, centred, on a bolt circle)<br><br>
4. <b>Say where features are located</b><br>
&nbsp;&nbsp;&nbsp;• centred, at one end, offset 10mm from an edge, etc.<br><br>
5. <b>Avoid vague words</b> like "small", "large", "thin". Use numbers instead.<br><br>
6. <b>If you want fillets, chamfers or keyways</b>, mention size and where<br>
&nbsp;&nbsp;&nbsp;• e.g. a 25mm shaft 150mm long with a 6mm wide, 3mm deep keyway<br><br>
<b>Example prompts</b><br>
• a rectangular plate 100mm by 60mm, 8mm thick with a central hole of 20mm<br>
• a rectangular tube 400mm long, 40mm wide, 30mm high with 3mm wall thickness<br>
• a shaft 25mm diameter and 200mm long with a 6mm wide, 3mm deep keyway<br>
• a plate 120 by 40 by 8mm with a 12mm wide slot leaving 20mm material at each end<br>
• a circular flange outer 80mm, inner 40mm, 8mm thick with 6 bolt holes of 8mm on a 60mm bolt circle<br>
"""
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


# ---------- About dialog ----------

class AboutDialog(QDialog):
    def __init__(self, main: QMainWindow):
        super().__init__(main)
        self.setWindowTitle("About – AI CAD Assistant")
        self.setModal(True)

        edition = "Pro" if main.is_pro else "Free"
        credits = main.lic_state.get("pro_credits", 0)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>AI CAD Assistant</b>"))
        layout.addWidget(QLabel(f"Edition: {edition}"))
        if not main.is_pro:
            layout.addWidget(QLabel(f"Remaining trial advanced actions: {credits}"))
        layout.addWidget(QLabel(" "))

        freecad_status = "Available" if main.freecad_available else "Not found"
        layout.addWidget(QLabel("<b>Environment</b>"))
        layout.addWidget(QLabel(f"FreeCAD: {freecad_status}"))
        if not main.freecad_available and main.freecad_error:
            err_txt = main.freecad_error
            if len(err_txt) > 120:
                err_txt = err_txt[:120] + "..."
            layout.addWidget(QLabel(f"FreeCAD error: {err_txt}"))

        layout.addWidget(QLabel(f"Models folder: {MODELS_DIR}"))
        layout.addWidget(QLabel(f"Log file: {LOG_FILE}"))
        layout.addWidget(QLabel(" "))

        layout.addWidget(
            QLabel(
                "This tool is for prototyping and educational use.\n"
                "Generated models and drawings must be reviewed and\n"
                "validated by a qualified engineer before real‑world use."
            )
        )
        layout.addWidget(
            QLabel(
                "See TERMS.md in the repository for full terms and disclaimer."
            )
        )

        btns = QHBoxLayout()
        btns.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)
        layout.addLayout(btns)


# ---------- Main window ----------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI CAD Assistant")
        self.resize(1100, 650)

        self.lic_state = load_state()
        self.is_pro = is_pro(self.lic_state)

        self.freecad_available = FREECAD_AVAILABLE
        self.freecad_error = FREECAD_ERROR

        logger.info(
            "Application started. FreeCAD available: %s. Error: %s",
            self.freecad_available,
            self.freecad_error,
        )

        tabs = QTabWidget()
        self.text_tab = TextToModelTab(self)
        self.image_tab = ImageToModelTab(self)
        self.drawing_tab = ModelToDrawingTab(self)

        tabs.addTab(self.text_tab, "Text → Model")
        tabs.addTab(self.image_tab, "Image → Model")
        tabs.addTab(self.drawing_tab, "Model → Drawing")
        self.setCentralWidget(tabs)

        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Ready.")

        if not self.freecad_available:
            status.showMessage(
                "FreeCAD not found. Model and drawing generation are disabled until you install it.",
                10000,
            )

        about_btn = QPushButton("About")
        about_btn.setFlat(True)
        about_btn.clicked.connect(self.show_about_dialog)
        status.addPermanentWidget(about_btn)

        download_btn = QPushButton("Download FreeCAD")
        download_btn.setFlat(True)
        download_btn.clicked.connect(self.open_freecad_download)
        status.addPermanentWidget(download_btn)

        self.toast = ToastWidget(self)
        self.toast.hide()

        if not self.freecad_available:
            self.toast.show_message(
                "FreeCAD is not installed or could not be imported. "
                "Install FreeCAD, then restart the AI CAD Assistant.",
                kind="error",
                duration_ms=8000,
            )

    def show_about_dialog(self):
        dlg = AboutDialog(self)
        dlg.exec()

    def open_freecad_download(self):
        url = "https://www.freecad.org/downloads.php"
        logger.info("Opening FreeCAD download page: %s", url)
        if hasattr(self, "toast"):
            self.toast.show_message(
                "Opening FreeCAD download page...", kind="success"
            )
        webbrowser.open(url)


# ---------- entry point ----------

def main():
    logger.info("Launching Qt application.")
    app = QApplication(sys.argv)

    candidates = [
        BASE_DIR / "style.qss",
        BASE_DIR / "_internal" / "style.qss",
    ]

    style_path = None
    for p in candidates:
        logger.info("Checking style at %s (exists=%s)", p, p.exists())
        if p.exists():
            style_path = p
            break

    if style_path:
        try:
            with open(style_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            logger.info("Loaded style.qss from %s", style_path)
        except Exception:
            logger.exception("Failed to load style.qss from %s", style_path)
    else:
        logger.warning("style.qss not found; using default Qt theme.")

    win = MainWindow()
    win.show()
    exit_code = app.exec()
    logger.info("Qt application exited with code %s.", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
