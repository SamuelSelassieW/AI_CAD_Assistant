import sys, os, webbrowser, logging, traceback, subprocess
from pathlib import Path

# ---------- Paths & logging setup ----------

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent


def setup_freecad_env():
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


# ---------- Toast widget ----------

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

        # left card
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

        # right card
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

        # ---- gear ambiguity check BEFORE calling the AI -------------------
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

    # ...  (keep the rest of your file: _generate_in_process, _generate_via_freecadcmd,
    # ImageToModelTab, ModelToDrawingTab, PromptHelpDialog, AboutDialog, MainWindow, main())