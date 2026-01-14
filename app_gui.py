import sys, os
from pathlib import Path
from license_utils import load_state, is_pro, can_use_pro_feature, consume_pro_credit

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPlainTextEdit, QPushButton, QComboBox, QStatusBar,
    QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

import FreeCAD, Part

from cad_code_ai_local import generate_cad_code
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
)
from drawing_generator_dims import generate_drawing_with_dims
from image_to_cad_run import image_to_cad

BASE_DIR = Path(__file__).parent
MODELS_DIR = BASE_DIR / "generated_models"
MODELS_DIR.mkdir(exist_ok=True)


class TextToModelTab(QWidget):
    def __init__(self, main_window: QMainWindow):
        super().__init__()
        self.main = main_window
        self.last_model_path: Path | None = None

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # -------- Left: prompt & controls --------
        left = QWidget()
        l_layout = QVBoxLayout(left)
        l_layout.setContentsMargins(8, 8, 8, 8)
        l_layout.setSpacing(6)

        l_layout.addWidget(QLabel("Describe your part:"))
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText(
            "Example: an M8 hex head bolt 40mm long using fasteners"
        )
        self.prompt_edit.setMinimumHeight(120)
        l_layout.addWidget(self.prompt_edit)

        ex_layout = QHBoxLayout()
        self.example_combo = QComboBox()
        self.example_combo.addItems([
            "an M8 hex head bolt 40mm long using fasteners",
            "an L-shaped bracket with legs 40mm and 30mm, width 10mm and thickness 5mm",
            "a circular flange outer 80mm, inner 40mm, 8mm thick with 6 bolt holes "
            "of 8mm on a 60mm bolt circle",
            "a cylinder of base radius 30mm and height 50mm with a central hole "
            "of radius 15mm and depth 30mm",
        ])
        ex_insert = QPushButton("Insert example")
        ex_insert.clicked.connect(self.insert_example)
        ex_layout.addWidget(self.example_combo)
        ex_layout.addWidget(ex_insert)
        l_layout.addLayout(ex_layout)

        self.generate_btn = QPushButton("Generate Model")
        self.generate_btn.clicked.connect(self.on_generate)
        l_layout.addWidget(self.generate_btn)

        splitter.addWidget(left)

        # -------- Right: code & result info --------
        right = QWidget()
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(8, 8, 8, 8)
        r_layout.setSpacing(6)

        r_layout.addWidget(QLabel("Generated CAD code:"))
        self.code_view = QPlainTextEdit()
        self.code_view.setReadOnly(True)
        self.code_view.setMinimumHeight(160)
        r_layout.addWidget(self.code_view)

        self.model_label = QLabel("Model: (none)")
        self.path_label = QLabel("Path: (none)")
        r_layout.addWidget(self.model_label)
        r_layout.addWidget(self.path_label)

        btn_row = QHBoxLayout()
        self.open_btn = QPushButton("Open in FreeCAD")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_in_freecad)
        btn_row.addStretch()
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

    def on_generate(self):
        desc = self.prompt_edit.toPlainText().strip()
        if not desc:
            self.main.statusBar().showMessage("Please enter a description.", 4000)
            return

        self.generate_btn.setEnabled(False)
        self.main.statusBar().showMessage("Generating model...", 0)
        QApplication.processEvents()

        try:
            code = generate_cad_code(desc)
            self.code_view.setPlainText(code)

            doc = FreeCAD.newDocument("AIModel")

            class _SafePart:
                @staticmethod
                def show(shape):
                    Part.show(shape)

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
            }

            exec(code, exec_globals, {})
            doc.recompute()

            idx = len(list(MODELS_DIR.glob("model_*.FCStd"))) + 1
            file_path = MODELS_DIR / f"model_{idx}.FCStd"
            doc.saveAs(str(file_path))

            self.last_model_path = file_path
            self.model_label.setText("Model created.")
            self.path_label.setText(f"Path: {file_path}")
            self.open_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            self.main.statusBar().showMessage(f"Saved model to: {file_path}", 5000)

        except Exception as e:
            QMessageBox.critical(self, "Error generating model", str(e))
            self.main.statusBar().showMessage(f"Error: {e}", 8000)
        finally:
            self.generate_btn.setEnabled(True)

    def open_in_freecad(self):
        if self.last_model_path and self.last_model_path.exists():
            os.startfile(str(self.last_model_path))

    def export_step(self):
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
            consume_pro_credit(state)
            step_path = self.last_model_path.with_suffix(".step")
            doc = FreeCAD.open(str(self.last_model_path))
            Part.export(doc.Objects, str(step_path))
            FreeCAD.closeDocument(doc.Name)
            os.startfile(str(step_path))
            self.main.statusBar().showMessage(f"Exported STEP to: {step_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export STEP failed", str(e))


class ImageToModelTab(QWidget):
    def __init__(self, main_window: QMainWindow):
        super().__init__()
        self.main = main_window
        self.image_path: Path | None = None
        self.model_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        btn_row = QHBoxLayout()
        self.load_btn = QPushButton("Load image / sketch…")
        self.load_btn.clicked.connect(self.load_image)
        self.gen_btn = QPushButton("Detect & Generate Model")
        self.gen_btn.setEnabled(False)
        self.gen_btn.clicked.connect(self.on_generate)
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.gen_btn)
        layout.addLayout(btn_row)

        self.preview = QLabel("No image loaded.")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(250)
        layout.addWidget(self.preview)

        self.info_label = QLabel("Model: (none)")
        self.path_label = QLabel("Path: (none)")
        layout.addWidget(self.info_label)
        layout.addWidget(self.path_label)

        open_row = QHBoxLayout()
        self.open_btn = QPushButton("Open in FreeCAD")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_model)
        open_row.addStretch()
        open_row.addWidget(self.open_btn)
        layout.addLayout(open_row)

    def load_image(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select image", str(BASE_DIR),
            "Images (*.png *.jpg *.jpeg *.bmp);;All files (*.*)"
        )
        if not fname:
            return
        self.image_path = Path(fname)
        pix = QPixmap(fname)
        if not pix.isNull():
            self.preview.setPixmap(pix.scaled(
                400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        else:
            self.preview.setText(f"Loaded: {fname}")
        self.gen_btn.setEnabled(True)
        self.main.statusBar().showMessage(f"Loaded image: {fname}", 4000)

    def on_generate(self):
        if not self.image_path or not self.image_path.exists():
            self.main.statusBar().showMessage("No valid image selected.", 4000)
            return
        self.main.statusBar().showMessage("Generating model from image...", 0)
        QApplication.processEvents()
        try:
            result = image_to_cad(str(self.image_path))
            if isinstance(result, (str, Path)):
                self.model_path = Path(result)
            else:
                fcstd_files = sorted(MODELS_DIR.glob("*.FCStd"))
                self.model_path = fcstd_files[-1] if fcstd_files else None

            if not self.model_path:
                self.main.statusBar().showMessage("No model created.", 5000)
                return

            self.info_label.setText("Model created from image.")
            self.path_label.setText(f"Path: {self.model_path}")
            self.open_btn.setEnabled(True)
            self.main.statusBar().showMessage(f"Saved model to: {self.model_path}", 5000)
        except Exception as e:
            self.main.statusBar().showMessage(f"Error: {e}", 8000)

    def open_model(self):
        if self.model_path and self.model_path.exists():
            os.startfile(str(self.model_path))


class ModelToDrawingTab(QWidget):
    def __init__(self, main_window: QMainWindow):
        super().__init__()
        self.main = main_window
        self.drawing_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Select model from generated_models:"))
        self.model_combo = QComboBox()
        layout.addWidget(self.model_combo)

        btn_row = QHBoxLayout()
        self.gen_btn = QPushButton("Generate Drawing")
        self.gen_btn.clicked.connect(self.on_generate)
        self.open_btn = QPushButton("Open Drawing")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_drawing)
        self.refresh_btn = QPushButton("Refresh list")
        self.refresh_btn.clicked.connect(self.refresh_models)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.gen_btn)
        btn_row.addWidget(self.open_btn)
        layout.addLayout(btn_row)

        self.path_label = QLabel("Drawing: (none)")
        layout.addWidget(self.path_label)

        self.refresh_models()

    def refresh_models(self):
        self.model_combo.clear()
        fcstd_files = sorted(MODELS_DIR.glob("*.FCStd"))
        for p in fcstd_files:
            self.model_combo.addItem(p.name, p)
        if not fcstd_files:
            self.model_combo.addItem("(no models)", None)

    def on_generate(self):
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
        self.main.statusBar().showMessage("Generating drawing...", 0)
        QApplication.processEvents()
        try:
            consume_pro_credit(state)
            out_path = generate_drawing_with_dims(Path(data))
            self.drawing_path = out_path
            self.path_label.setText(f"Drawing: {out_path}")
            self.open_btn.setEnabled(True)
            self.main.statusBar().showMessage(f"Saved drawing to: {out_path}", 5000)
        except Exception as e:
            self.main.statusBar().showMessage(f"Error: {e}", 8000)

    def open_drawing(self):
        if self.drawing_path and self.drawing_path.exists():
            os.startfile(str(self.drawing_path))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI CAD Assistant")
        self.resize(1000, 600)

        # Load license state
        self.lic_state = load_state()
        self.is_pro = is_pro(self.lic_state)

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


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()