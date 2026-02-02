import sys, os, webbrowser, logging, traceback, subprocess
from pathlib import Path

# ---------- Paths & logging setup ----------

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent


def setup_freecad_env():
    """
    Make sure the embedded Python process can find the FreeCAD DLLs and modules.
    """
    candidates: list[Path] = []

    env_home = (
        os.environ.get("FREECAD_HOME")
        or os.environ.get("FREECAD_DIR")
        or os.environ.get("FREECAD_BASE")
    )
    if env_home:
        candidates.append(Path(env_home))

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
            if d.exists() and hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(d))
                except Exception:
                    pass

        if lib_dir.exists():
            lib_str = str(lib_dir)
            if lib_str not in sys.path:
                sys.path.insert(0, lib_str)

        break


if getattr(sys, "frozen", False):
    internal_dir = BASE_DIR / "_internal"
    if internal_dir.exists() and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(str(internal_dir))
        except Exception:
            pass

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
from PyQt6.QtGui import QPixmap

setup_freecad_env()

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
    make_rect_tube,
    make_pipe,
    make_stepped_shaft,
    make_flat_bar_2holes,
    make_drum_with_flange,
    make_shaft_with_keyway,
    make_plate_with_slot,
    make_plate_with_pocket,
    FREECADCMD,
)
from drawing_generator_dims import generate_drawing_with_dims
from image_to_cad_run import image_to_cad


# ---------- Toast notification widget ----------

class ToastWidget(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._opacity = 1.0
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

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


# ---------- Text → Model tab ----------

class TextToModelTab(QWidget):
    def __init__(self, main_window: QMainWindow):
        super().__init__()
        self.main = main_window
        self.last_model_path: Path | None = None

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

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

        hint_text = (
            "Generation may take 30–60 seconds."
            if self.main.freecad_available
            else "FreeCAD not found. Install FreeCAD to enable model generation."
        )
        self.hint_label = QLabel(hint_text)
        self.hint_label.setObjectName("secondaryText")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        l_layout.addWidget(self.hint_label)

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

        # --- Gear ambiguity check BEFORE calling the AI --------------------
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
        idx = len(list(MODELS_DIR.glob("model_*.FCStd"))) + 1
        out_path = MODELS_DIR / f"model_{idx}.FCStd"

        temp_dir = MODELS_DIR / "_temp"
        temp_dir.mkdir(exist_ok=True)
        script_path = temp_dir / "gen_code.py"

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


# ImageToModelTab, ModelToDrawingTab, PromptHelpDialog, AboutDialog
# (you can keep the versions you already have; no gear logic there)

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