from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from PyQt5.QtCore import QEvent, QPoint, QRect, QSignalBlocker, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygon
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .backend_bridge import (
    BASIS_SET_OPTIONS,
    CHARGE_PRINT_OPTIONS,
    CUBE_PRINT_OPTIONS,
    DISPERSION_OPTIONS,
    FUNCTIONAL_OPTIONS,
    KPOINT_MODE_OPTIONS,
    MIXING_OPTIONS,
    MODEL_SIZE_OPTIONS,
    OT_MINIMIZER_OPTIONS,
    PERIODIC_OPTIONS,
    SCF_ACCURACY_OPTIONS,
    SCF_METHOD_OPTIONS,
    SLURM_CORES_PER_NODE_MODE_OPTIONS,
    SLURM_PRESET_OPTIONS,
    SLURM_TEMPLATE_OPTIONS,
    TASK_OPTIONS,
    backend_default_values,
    batch_generate_jobs,
    default_cores_per_node,
    diag_max_scf_default,
    dft_u_presets,
    ensure_backend_path,
    generate_job,
    is_optimization_task,
    magnetic_moment_presets,
    prepare_auto_fixed_preview,
    scf_accuracy_eps,
)
from .chemistry import ATOM_COLORS, atoms_to_range_text, convert_structure_with_multiwfn, load_molecule, parse_atom_indices
from .i18n import normalize_language, tr
from .molecule_canvas import MoleculeCanvas
from .settings import AppSettings, load_settings, multiwfn_exe_from_setting, normalize_multiwfn_path, save_settings
from .theme import LIGHT_QSS
from .visual_styles import DEFAULT_STYLE_ID, MAX_VISUAL_STYLES, load_visual_styles, save_visual_styles


ensure_backend_path()


TRANSITION_OR_MAGNETIC_ELEMENTS = {
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd",
    "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Ce", "U",
}

VESTA_BASIC_COLOR_PALETTE = [
    "#FF8080", "#FFFF80", "#80FF80", "#00FF80", "#80FFFF", "#0080FF", "#FF80C0", "#FF80FF",
    "#FF0000", "#FFFF00", "#80FF00", "#00FF40", "#00FFFF", "#0080C0", "#8080C0", "#FF00FF",
    "#804040", "#FF8040", "#00FF00", "#008080", "#004080", "#8080FF", "#800040", "#FF0080",
    "#800000", "#FF8000", "#008000", "#008040", "#0000FF", "#0000A0", "#800080", "#8000FF",
    "#400000", "#804000", "#004000", "#004040", "#000080", "#000040", "#400040", "#400080",
]

VIEWER_CONVERSION_OPTIONS = [
    ("cif", "CIF"),
    ("xyz", "XYZ"),
    ("pdb", "PDB"),
    ("gjf", "GJF"),
    ("gro", "GRO"),
    ("poscar", "POSCAR"),
]

BATCH_STRUCTURE_SUFFIXES = {
    ".cif", ".mcif", ".xyz", ".pdb", ".ent", ".gro", ".gjf", ".com",
    ".poscar", ".vasp", ".inp", ".restart",
}
STRUCTURE_FILE_FILTER = (
    "Structure files (*.cif *.mcif *.xyz *.pdb *.ent *.gro *.gjf *.com "
    "*.poscar *.vasp *.inp *.restart);;All files (*.*)"
)

VISUAL_FORM_LABEL_WIDTH = 74
VISUAL_CONTROL_HEIGHT = 26


class FileDropListWidget(QListWidget):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlternatingRowColors(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(url.toLocalFile())
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class FileDropLineEdit(QLineEdit):
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if self._first_local_file(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if self._first_local_file(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        path = self._first_local_file(event)
        if path:
            self.setText(path)
            self.file_dropped.emit(path)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    @staticmethod
    def _first_local_file(event) -> str:
        mime = event.mimeData()
        if not mime.hasUrls():
            return ""
        for url in mime.urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if Path(path).is_file():
                    return path
        return ""


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:
        event.ignore()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#64748B" if self.isEnabled() else "#A8B3C2"))
        right = self.width() - 14
        center = self.height() // 2
        painter.drawPolygon(QPolygon([QPoint(right - 5, center - 2), QPoint(right + 5, center - 2), QPoint(right, center + 4)]))
        painter.end()


class NoWheelSlider(QSlider):
    def wheelEvent(self, event) -> None:
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._spin_hover_zone = ""
        self._spin_pressed_zone = ""

    def wheelEvent(self, event) -> None:
        event.ignore()

    def _spin_zone_at(self, pos) -> str:
        if pos.x() < self.width() - 24:
            return ""
        return "up" if pos.y() < self.height() / 2 else "down"

    def mouseMoveEvent(self, event) -> None:
        zone = self._spin_zone_at(event.pos())
        if zone != self._spin_hover_zone:
            self._spin_hover_zone = zone
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._spin_hover_zone = ""
        self._spin_pressed_zone = ""
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self._spin_pressed_zone = self._spin_zone_at(event.pos())
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self._spin_pressed_zone = ""
        self._spin_hover_zone = self._spin_zone_at(event.pos())
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self._paint_flat_spin_buttons()

    def _paint_flat_spin_buttons(self) -> None:
        painter = QPainter(self)
        button_width = 23
        left = self.width() - button_width - 1
        top_rect = QRect(left, 1, button_width, max(1, self.height() // 2 - 1))
        bottom_rect = QRect(left, self.height() // 2, button_width, max(1, self.height() - self.height() // 2 - 1))
        for zone, rect in (("up", top_rect), ("down", bottom_rect)):
            color = QColor("#F8FAFC")
            if not self.isEnabled():
                color = QColor("#EEF2F7")
            elif self._spin_pressed_zone == zone:
                color = QColor("#D7EAF1")
            elif self._spin_hover_zone == zone:
                color = QColor("#E6F2F6")
            painter.fillRect(rect, color)
        painter.setPen(QPen(QColor("#D6E0EA"), 1))
        painter.drawLine(left, 1, left, self.height() - 2)
        painter.drawLine(left + 1, self.height() // 2, self.width() - 3, self.height() // 2)

        arrow_color = QColor("#176B87" if self._spin_hover_zone or self._spin_pressed_zone else "#64748B")
        if not self.isEnabled():
            arrow_color = QColor("#A8B3C2")
        painter.setPen(QPen(arrow_color, 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cx = left + button_width // 2
        up_y = top_rect.center().y() + (1 if self._spin_pressed_zone == "up" else 0)
        down_y = bottom_rect.center().y() + (1 if self._spin_pressed_zone == "down" else 0)
        painter.drawLine(QPoint(cx - 4, up_y + 2), QPoint(cx, up_y - 2))
        painter.drawLine(QPoint(cx, up_y - 2), QPoint(cx + 4, up_y + 2))
        painter.drawLine(QPoint(cx - 4, down_y - 2), QPoint(cx, down_y + 2))
        painter.drawLine(QPoint(cx, down_y + 2), QPoint(cx + 4, down_y - 2))
        painter.end()


class NoWheelSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._spin_hover_zone = ""
        self._spin_pressed_zone = ""

    def wheelEvent(self, event) -> None:
        event.ignore()

    def _spin_zone_at(self, pos) -> str:
        if pos.x() < self.width() - 24:
            return ""
        return "up" if pos.y() < self.height() / 2 else "down"

    def mouseMoveEvent(self, event) -> None:
        zone = self._spin_zone_at(event.pos())
        if zone != self._spin_hover_zone:
            self._spin_hover_zone = zone
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._spin_hover_zone = ""
        self._spin_pressed_zone = ""
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self._spin_pressed_zone = self._spin_zone_at(event.pos())
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self._spin_pressed_zone = ""
        self._spin_hover_zone = self._spin_zone_at(event.pos())
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        NoWheelDoubleSpinBox._paint_flat_spin_buttons(self)


class NoWheelTabBar(QTabBar):
    def wheelEvent(self, event) -> None:
        event.ignore()


class NoWheelTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(NoWheelTabBar())

    def wheelEvent(self, event) -> None:
        event.ignore()


class CollapsibleGroupBox(QGroupBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_title = ""
        self.setCheckable(True)
        self.setChecked(True)
        self.toggled.connect(self._set_expanded)
        self._set_expanded(True)

    def setTitle(self, title: str) -> None:
        text = str(title or "").strip()
        self._base_title = text.lstrip("\u25be\u25b8v>+- ").strip()
        self._sync_title()

    def _sync_title(self) -> None:
        marker = "\u25be" if self.isChecked() else "\u25b8"
        QGroupBox.setTitle(self, f"{marker} {self._base_title}" if self._base_title else marker)

    def _set_expanded(self, expanded: bool) -> None:
        for child in self.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            child.setVisible(expanded)
        self.setMaximumHeight(16777215 if expanded else 42)
        self.setProperty("collapsed", not expanded)
        self._sync_title()
        self.style().unpolish(self)
        self.style().polish(self)


class BackendWorker(QThread):
    succeeded = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)

    def __init__(self, mode: str, payload: dict[str, Any]):
        super().__init__()
        self.mode = mode
        self.payload = payload

    def run(self) -> None:
        try:
            if self.mode == "generate":
                result = generate_job(self.payload)
            elif self.mode == "batch":
                result = batch_generate_jobs(self.payload)
            elif self.mode == "preview":
                result = prepare_auto_fixed_preview(self.payload)
            else:
                raise ValueError(f"Unsupported backend mode: {self.mode}")
            self.succeeded.emit(self.mode, result)
        except Exception:
            self.failed.emit(self.mode, traceback.format_exc())


class CP2KForgeMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.language = normalize_language(self.settings.language)
        self.default_values = backend_default_values()
        self.magnetic_moment_presets = magnetic_moment_presets()
        self.dft_u_presets = dft_u_presets()
        self.visual_styles = load_visual_styles()
        self.value_widgets: dict[str, Any] = {}
        self.current_file: Path | None = None
        self.current_content = ""
        self.current_molecule = None
        self.batch_files: list[dict[str, str]] = []
        self.slab_reference_file: dict[str, str] | None = None
        self.worker: BackendWorker | None = None
        self._busy_mode = ""
        self._diag_max_touched = False
        self._disabled_tasks = {"MD", "BAND"}
        self._last_task_value = "ENERGY"
        self._applying_visual_style = False

        self.setWindowTitle(f"{tr(self.language, 'title')} {__version__}")
        self.setGeometry(120, 80, 1520, 940)
        self.setMinimumSize(1280, 760)
        self.setStyleSheet(LIGHT_QSS)
        self._build_ui()
        self._apply_defaults(reset_project=False)
        self.apply_language()
        self._refresh_preview_box(tr(self.language, "manual_indices_preview"))
        self._refresh_batch_list()
        self._update_task_controls()
        self._update_method_controls()
        self._update_feature_controls()
        self._update_slurm_controls()
        self._clear_results()
        self._saved_settings_snapshot = self._current_settings_snapshot()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 6, 12, 10)
        root.setSpacing(6)

        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #0F536A; font-size: 17pt; font-weight: bold; padding: 4px;")
        self.title_label.setVisible(False)

        self.subtitle_label = QLabel()
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("color: #547085; font-size: 9pt; padding-bottom: 6px;")
        self.subtitle_label.setVisible(False)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left.setMinimumWidth(600)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)
        self._build_input_panel(left_layout)
        self.tabs = NoWheelTabWidget()
        self.tabs.setMinimumWidth(580)
        self.generate_tab = QWidget()
        self.visual_tab = QWidget()
        self.settings_tab = QWidget()
        self.tabs.addTab(self.generate_tab, "")
        self.tabs.addTab(self.visual_tab, "")
        self.tabs.addTab(self.settings_tab, "")
        left_layout.addWidget(self.tabs)
        splitter.addWidget(left)

        right = QWidget()
        right.setMinimumWidth(620)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        self._build_visualization_panel(right_layout)

        self.result_group = QGroupBox()
        result_layout = QVBoxLayout(self.result_group)
        result_layout.setContentsMargins(10, 14, 10, 8)
        self.result_state_label = QLabel()
        self.result_state_label.setObjectName("ResultState")
        self.output_line = QLabel()
        self.output_line.setWordWrap(True)
        self.output_line.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.output_line.setObjectName("OutputLine")
        self.result_tabs = NoWheelTabWidget()
        self.result_tabs.setVisible(False)
        self.summary_text = self._make_result_text()
        self.summary_text.setMaximumHeight(190)
        self.summary_text.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.patched_text = self._make_result_text()
        self.diff_text = self._make_result_text()
        self.raw_text = self._make_result_text()
        self.commands_text = self._make_result_text()
        self.backend_log_text = self._make_result_text()
        self.result_tabs.addTab(self.summary_text, "")
        self.result_tabs.addTab(self.patched_text, "")
        self.result_tabs.addTab(self.diff_text, "")
        self.result_tabs.addTab(self.raw_text, "")
        self.result_tabs.addTab(self.commands_text, "")
        self.result_tabs.addTab(self.backend_log_text, "")
        result_layout.addWidget(self.result_state_label)
        result_layout.addWidget(self.output_line)
        result_layout.addWidget(self.summary_text)
        right_layout.addWidget(self.result_group, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([620, 980])

        self.status_label = QLabel()
        self.status_label.setObjectName("StatusLabel")
        root.addWidget(self.status_label)

        self._build_generate_tab()
        self._build_visualization_tab()
        self._build_settings_tab()
        self._polish_text_fit()
        self._disable_wheel_focus()
        self.tabs.currentChanged.connect(lambda _index: self._reflow_visual_settings_layout())
        self._reflow_visual_settings_layout()

    def _make_result_text(self) -> QPlainTextEdit:
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setLineWrapMode(QPlainTextEdit.NoWrap)
        return box

    def _small_button(self) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("SmallBtn")
        btn.setFixedWidth(38)
        return btn

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "viewer_toolbar"):
            self._reflow_viewer_toolbar()
        if hasattr(self, "visual_body_layout"):
            self._reflow_visual_settings_layout()

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self.visual_group if hasattr(self, "visual_group") else self)

    def _reflow_viewer_toolbar(self) -> None:
        if not hasattr(self, "viewer_toolbar"):
            return
        width = self.visual_group.width() or self.width()
        if width >= 1220:
            mode = "one"
        elif width >= 680:
            mode = "two"
        else:
            mode = "three"
        if getattr(self, "_viewer_toolbar_mode", "") == mode:
            return
        self._viewer_toolbar_mode = mode
        toolbar = self.viewer_toolbar
        self._clear_layout(toolbar)
        for column in range(24):
            toolbar.setColumnStretch(column, 0)

        axis_buttons = [
            self.view_a_btn,
            self.view_b_btn,
            self.view_c_btn,
            self.view_a_reverse_btn,
            self.view_b_reverse_btn,
            self.view_c_reverse_btn,
            self.reset_view_btn,
        ]
        rotate_buttons = [
            self.rotate_x_plus_btn,
            self.rotate_x_minus_btn,
            self.rotate_y_minus_btn,
            self.rotate_y_plus_btn,
            self.rotate_z_minus_btn,
            self.rotate_z_plus_btn,
        ]

        if mode == "one":
            column = 0
            toolbar.addWidget(self.viewer_export_image_btn, 0, column)
            column += 1
            toolbar.addWidget(self.viewer_export_transparent_box, 0, column)
            column += 1
            for button in axis_buttons + rotate_buttons:
                toolbar.addWidget(button, 0, column)
                column += 1
            toolbar.addWidget(self.view_step_label, 0, column)
            column += 1
            toolbar.addWidget(self.view_step_spin, 0, column)
            column += 1
            toolbar.setColumnStretch(column, 1)
            column += 1
            toolbar.addWidget(self.hide_compass_box, 0, column)
            column += 1
            toolbar.addWidget(self.show_symbols_box, 0, column)
            column += 1
            toolbar.addWidget(self.show_numbers_box, 0, column)
            return

        if mode == "two":
            column = 0
            for button in axis_buttons:
                toolbar.addWidget(button, 0, column)
                column += 1
            toolbar.setColumnStretch(column, 1)
            column += 1
            toolbar.addWidget(self.hide_compass_box, 0, column)
            column += 1
            toolbar.addWidget(self.show_symbols_box, 0, column)
            column += 1
            toolbar.addWidget(self.show_numbers_box, 0, column)

            column = 0
            toolbar.addWidget(self.viewer_export_image_btn, 1, column)
            column += 1
            toolbar.addWidget(self.viewer_export_transparent_box, 1, column)
            column += 1
            for button in rotate_buttons:
                toolbar.addWidget(button, 1, column)
                column += 1
            toolbar.addWidget(self.view_step_label, 1, column)
            column += 1
            toolbar.addWidget(self.view_step_spin, 1, column)
            column += 1
            toolbar.setColumnStretch(column, 1)
            return

        column = 0
        for button in axis_buttons:
            toolbar.addWidget(button, 0, column)
            column += 1
        toolbar.setColumnStretch(column, 1)

        column = 0
        for button in rotate_buttons:
            toolbar.addWidget(button, 1, column)
            column += 1
        toolbar.addWidget(self.view_step_label, 1, column)
        column += 1
        toolbar.addWidget(self.view_step_spin, 1, column)
        column += 1
        toolbar.setColumnStretch(column, 1)

        column = 0
        toolbar.addWidget(self.viewer_export_image_btn, 2, column)
        column += 1
        toolbar.addWidget(self.viewer_export_transparent_box, 2, column)
        column += 1
        toolbar.addWidget(self.hide_compass_box, 2, column)
        column += 1
        toolbar.addWidget(self.show_symbols_box, 2, column)
        column += 1
        toolbar.addWidget(self.show_numbers_box, 2, column)
        column += 1
        toolbar.setColumnStretch(column, 1)

    def _polish_text_fit(self) -> None:
        protected = {self.title_label, self.subtitle_label, self.status_label, self.output_line, self.result_state_label}
        for label in self.findChildren(QLabel):
            if label in protected:
                continue
            label.setWordWrap(True)
            label.setMinimumWidth(0)
        for button in self.findChildren(QPushButton):
            if button.objectName() == "SmallBtn":
                continue
            button.setMinimumWidth(0)
        self._stabilize_form_labels()

    def _stabilize_form_labels(self) -> None:
        label_names = [
            "structure_label", "batch_output_label", "slurm_template_label", "slurm_preset_label",
            "slurm_nodes_label", "slurm_cores_label", "slurm_cpn_mode_label", "slurm_cpn_label",
            "project_label", "task_label", "model_size_label", "periodic_label",
            "fixed_atoms_label", "selected_label", "freeze_percent_label", "exclude_label",
            "reference_label", "functional_label", "basis_label", "dispersion_label",
            "charge_label", "charge_print_label", "cube_label", "added_mos_label",
            "scf_method_label", "scf_accuracy_label", "mixing_label", "kpoints_mode_label",
            "kpoints_label", "cutoff_label", "rel_cutoff_label", "temperature_label",
            "diag_max_label", "diag_eps_label", "ot_minimizer_label", "ot_inner_max_label",
            "ot_inner_eps_label", "ot_outer_max_label", "ot_outer_eps_label",
            "mag_rows_label", "dft_u_rows_label",
        ]
        for name in label_names:
            label = getattr(self, name, None)
            if isinstance(label, QLabel):
                label.setWordWrap(False)
                label.setMinimumWidth(64)
        if hasattr(self, "view_step_label"):
            self.view_step_label.setWordWrap(False)
            self.view_step_label.setMinimumWidth(78)

    def _disable_wheel_focus(self) -> None:
        for widget in self.findChildren(QWidget):
            if widget.focusPolicy() == Qt.WheelFocus:
                widget.setFocusPolicy(Qt.StrongFocus)
            if isinstance(widget, (QComboBox, QDoubleSpinBox, QSpinBox, QSlider, QTabBar)):
                self._install_no_wheel_filter(widget)

    def _install_no_wheel_filter(self, widget: QWidget) -> None:
        widget.setProperty("noWheelSelect", True)
        widget.installEventFilter(self)
        viewport = getattr(widget, "viewport", None)
        if callable(viewport):
            child = viewport()
            if isinstance(child, QWidget):
                child.setProperty("noWheelSelect", True)
                child.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Wheel and isinstance(watched, QWidget) and watched.property("noWheelSelect"):
            event.ignore()
            return True
        return super().eventFilter(watched, event)

    def _prepare_visual_control(self, widget: QWidget) -> QWidget:
        if isinstance(widget, (QPushButton, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox)):
            widget.setMinimumHeight(VISUAL_CONTROL_HEIGHT)
            if not isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                widget.setMinimumWidth(0)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if isinstance(widget, QPushButton) and not widget.objectName():
            widget.setObjectName("VisualActionButton")
        return widget

    def _prepare_visual_label(self, label: QLabel) -> QLabel:
        label.setObjectName("VisualFormLabel")
        label.setMinimumWidth(VISUAL_FORM_LABEL_WIDTH)
        label.setMaximumWidth(VISUAL_FORM_LABEL_WIDTH)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setWordWrap(False)
        return label

    def _visual_row_widget(self, *widgets: QWidget, stretch: bool = True) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for widget in widgets:
            row_layout.addWidget(self._prepare_visual_control(widget))
        if stretch:
            row_layout.addStretch(1)
        return row

    def _visual_subhead_label(self) -> QLabel:
        label = QLabel()
        label.setObjectName("VisualSubhead")
        label.setWordWrap(False)
        return label

    def _add_visual_subhead(self, grid: QGridLayout, row: int, label: QLabel) -> int:
        grid.addWidget(label, row, 0, 1, 4)
        return row + 1

    def _add_visual_form_row(self, grid: QGridLayout, row: int, label: QLabel, control: QWidget) -> int:
        grid.addWidget(self._prepare_visual_label(label), row, 0)
        grid.addWidget(self._prepare_visual_control(control), row, 1, 1, 3)
        return row + 1

    def _add_visual_form_pair(
        self,
        grid: QGridLayout,
        row: int,
        left_label: QLabel,
        left_control: QWidget,
        right_label: QLabel,
        right_control: QWidget,
    ) -> int:
        grid.addWidget(self._prepare_visual_label(left_label), row, 0)
        grid.addWidget(self._prepare_visual_control(left_control), row, 1)
        grid.addWidget(self._prepare_visual_label(right_label), row, 2)
        grid.addWidget(self._prepare_visual_control(right_control), row, 3)
        return row + 1

    def _configure_visual_grid(self, grid: QGridLayout) -> None:
        grid.setContentsMargins(6, 12, 6, 6)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)
        grid.setColumnMinimumWidth(0, VISUAL_FORM_LABEL_WIDTH)
        grid.setColumnMinimumWidth(2, VISUAL_FORM_LABEL_WIDTH)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

    def _reflow_visual_settings_layout(self) -> None:
        layout = getattr(self, "visual_body_layout", None)
        if not isinstance(layout, QGridLayout):
            return
        groups = [
            getattr(self, "visual_view_group", None),
            getattr(self, "cell_style_group", None),
            getattr(self, "atom_style_group", None),
            getattr(self, "bond_style_group", None),
        ]
        if any(group is None for group in groups):
            return
        mode = "stack"
        if getattr(self, "_visual_settings_layout_mode", "") == mode:
            return
        self._visual_settings_layout_mode = mode
        while layout.count():
            layout.takeAt(0)
        layout.addWidget(self.visual_view_group, 0, 0, 1, 2)
        layout.addWidget(self.cell_style_group, 1, 0, 1, 2)
        layout.addWidget(self.atom_style_group, 2, 0, 1, 2)
        layout.addWidget(self.bond_style_group, 3, 0, 1, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 0)
        layout.setRowStretch(4, 1)

    def _visual_color_swatch(self) -> QLabel:
        swatch = QLabel()
        swatch.setObjectName("ColorSwatch")
        swatch.setFixedSize(28, 24)
        return swatch

    def _bind_color_button(self, button: QPushButton, swatch: QLabel) -> None:
        button.setObjectName("ColorChooseButton")
        button.setMinimumWidth(64)
        button._color_swatch = swatch

    def _visual_color_control(self, button: QPushButton) -> QWidget:
        swatch = self._visual_color_swatch()
        self._bind_color_button(button, swatch)
        return self._visual_row_widget(swatch, button, stretch=True)

    def _double_spin(self, minimum: float, maximum: float, value: float, step: float = 0.5, decimals: int = 1) -> NoWheelDoubleSpinBox:
        box = NoWheelDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(decimals)
        box.setSingleStep(step)
        box.setValue(value)
        return box

    def _spin(self, minimum: int, maximum: int, value: int) -> NoWheelSpinBox:
        box = NoWheelSpinBox()
        box.setRange(minimum, maximum)
        box.setSingleStep(1)
        box.setValue(value)
        return box

    def _register_widget(self, key: str, widget: Any) -> Any:
        self.value_widgets[key] = widget
        return widget

    def _line(self, key: str) -> QLineEdit:
        return self._register_widget(key, QLineEdit())

    def _combo(self, key: str, options: list[tuple[str, str]]) -> QComboBox:
        combo = NoWheelComboBox()
        for value, label in options:
            combo.addItem(label, value)
        return self._register_widget(key, combo)

    def _mark_combo_values_disabled(self, combo: QComboBox, disabled_values: set[str]) -> None:
        model = combo.model()
        for index in range(combo.count()):
            value = str(combo.itemData(index) or combo.itemText(index))
            item = model.item(index) if hasattr(model, "item") else None
            if item is not None:
                item.setEnabled(value not in disabled_values)

    def _check(self, key: str) -> QCheckBox:
        return self._register_widget(key, QCheckBox())

    def _text(self, key: str, min_height: int = 84) -> QPlainTextEdit:
        box = QPlainTextEdit()
        box.setMinimumHeight(min_height)
        return self._register_widget(key, box)

    def _build_input_panel(self, parent_layout: QVBoxLayout) -> None:
        self.input_group = CollapsibleGroupBox()
        self.input_group.setObjectName("PinnedInputGroup")
        self.input_group.setMinimumHeight(142)
        input_grid = QGridLayout(self.input_group)
        input_grid.setColumnStretch(1, 1)
        input_grid.setColumnMinimumWidth(0, 88)
        self.structure_label = QLabel()
        self.structure_edit = FileDropLineEdit()
        self.structure_edit.setObjectName("StructureDropEdit")
        self.structure_edit.setMinimumHeight(58)
        self.structure_edit.file_dropped.connect(self.load_structure_path)
        self.structure_browse_btn = self._small_button()
        self.structure_browse_btn.clicked.connect(self.browse_structure)
        self.load_original_btn = QPushButton()
        self.load_original_btn.setMinimumHeight(34)
        self.load_original_btn.clicked.connect(self.load_original_structure_from_field)
        self.convert_format_combo = NoWheelComboBox()
        for value, label in VIEWER_CONVERSION_OPTIONS:
            self.convert_format_combo.addItem(label, value)
        self.convert_format_combo.setMinimumHeight(34)
        self.convert_format_combo.setMinimumWidth(92)
        self.convert_load_btn = QPushButton()
        self.convert_load_btn.setMinimumHeight(34)
        self.convert_load_btn.setMinimumWidth(150)
        self.convert_load_btn.clicked.connect(self.convert_structure_from_field)
        input_grid.addWidget(self.structure_label, 0, 0)
        input_grid.addWidget(self.structure_edit, 0, 1, 1, 2)
        input_grid.addWidget(self.structure_browse_btn, 0, 3)
        input_grid.addWidget(self.load_original_btn, 1, 1)
        input_grid.addWidget(self.convert_format_combo, 1, 2)
        input_grid.addWidget(self.convert_load_btn, 1, 3)
        parent_layout.addWidget(self.input_group, 0)

    def _build_generate_tab(self) -> None:
        outer = QVBoxLayout(self.generate_tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self.generate_actions_bar = QWidget()
        self.generate_actions_bar.setObjectName("GenerateActionsBar")
        actions = QHBoxLayout(self.generate_actions_bar)
        actions.setContentsMargins(10, 8, 10, 8)
        actions.setSpacing(8)
        self.generate_btn = QPushButton()
        self.generate_btn.setObjectName("PrimaryBtn")
        self.generate_btn.clicked.connect(self.generate_inp)
        self.batch_generate_btn = QPushButton()
        self.batch_generate_btn.setObjectName("PrimaryBtn")
        self.batch_generate_btn.clicked.connect(self.batch_generate_inp)
        self.reset_btn = QPushButton()
        self.reset_btn.clicked.connect(self.reset_form)
        actions.addWidget(self.generate_btn)
        actions.addWidget(self.batch_generate_btn)
        actions.addWidget(self.reset_btn)
        actions.addStretch()
        outer.addWidget(self.generate_actions_bar, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.batch_group = CollapsibleGroupBox()
        batch_layout = QVBoxLayout(self.batch_group)
        batch_layout.setContentsMargins(10, 14, 10, 10)
        top_row = QHBoxLayout()
        self.batch_output_label = QLabel()
        self.batch_output_combo = NoWheelComboBox()
        self.batch_output_combo.addItem("", "separate_folders")
        self.batch_output_combo.addItem("", "source_folder")
        top_row.addWidget(self.batch_output_label)
        top_row.addWidget(self.batch_output_combo, 1)
        batch_layout.addLayout(top_row)
        self.batch_list = FileDropListWidget()
        self.batch_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.batch_list.setMinimumHeight(96)
        self.batch_list.files_dropped.connect(self._add_batch_paths)
        batch_layout.addWidget(self.batch_list)
        batch_btns = QHBoxLayout()
        self.add_batch_btn = QPushButton()
        self.add_batch_btn.clicked.connect(self.browse_batch_files)
        self.clear_batch_btn = QPushButton()
        self.clear_batch_btn.clicked.connect(self.clear_batch_files)
        batch_btns.addWidget(self.add_batch_btn)
        batch_btns.addWidget(self.clear_batch_btn)
        batch_btns.addStretch()
        batch_layout.addLayout(batch_btns)
        self.batch_hint_label = QLabel()
        self.batch_hint_label.setWordWrap(True)
        batch_layout.addWidget(self.batch_hint_label)
        layout.addWidget(self.batch_group)
        self.batch_group.setChecked(False)

        self.slurm_group = CollapsibleGroupBox()
        slurm_grid = QGridLayout(self.slurm_group)
        slurm_grid.setColumnStretch(1, 1)
        slurm_grid.setColumnStretch(3, 1)
        self.slurm_enabled_box = self._check("slurm_enabled")
        self.slurm_enabled_box.toggled.connect(self._update_slurm_controls)
        self.slurm_template_label = QLabel()
        self.slurm_template_combo = self._combo("slurm_template", SLURM_TEMPLATE_OPTIONS)
        self.slurm_template_combo.currentIndexChanged.connect(self._on_slurm_preset_family_changed)
        self.slurm_preset_label = QLabel()
        self.slurm_preset_combo = self._combo("slurm_preset", SLURM_PRESET_OPTIONS)
        self.slurm_preset_combo.currentIndexChanged.connect(self._on_slurm_preset_family_changed)
        self.slurm_nodes_label = QLabel()
        self.slurm_nodes_edit = self._line("slurm_nodes")
        self.slurm_nodes_edit.textChanged.connect(self._on_slurm_resource_changed)
        self.slurm_cores_label = QLabel()
        self.slurm_cores_edit = self._line("slurm_cores")
        self.slurm_cores_edit.textChanged.connect(self._on_slurm_resource_changed)
        self.slurm_cpn_mode_label = QLabel()
        self.slurm_cpn_mode_combo = self._combo("slurm_cores_per_node_mode", SLURM_CORES_PER_NODE_MODE_OPTIONS)
        self.slurm_cpn_mode_combo.currentIndexChanged.connect(self._on_slurm_resource_changed)
        self.slurm_cpn_label = QLabel()
        self.slurm_cpn_edit = self._line("slurm_cores_per_node")

        slurm_grid.addWidget(self.slurm_enabled_box, 0, 0, 1, 4)
        slurm_grid.addWidget(self.slurm_template_label, 1, 0)
        slurm_grid.addWidget(self.slurm_template_combo, 1, 1)
        slurm_grid.addWidget(self.slurm_preset_label, 1, 2)
        slurm_grid.addWidget(self.slurm_preset_combo, 1, 3)
        slurm_grid.addWidget(self.slurm_nodes_label, 2, 0)
        slurm_grid.addWidget(self.slurm_nodes_edit, 2, 1)
        slurm_grid.addWidget(self.slurm_cores_label, 2, 2)
        slurm_grid.addWidget(self.slurm_cores_edit, 2, 3)
        slurm_grid.addWidget(self.slurm_cpn_mode_label, 3, 0)
        slurm_grid.addWidget(self.slurm_cpn_mode_combo, 3, 1)
        slurm_grid.addWidget(self.slurm_cpn_label, 3, 2)
        slurm_grid.addWidget(self.slurm_cpn_edit, 3, 3)
        layout.addWidget(self.slurm_group)
        self.slurm_group.setChecked(False)

        self.basic_group = CollapsibleGroupBox()
        basic_grid = QGridLayout(self.basic_group)
        basic_grid.setColumnStretch(1, 1)
        basic_grid.setColumnStretch(3, 1)
        self.project_label = QLabel()
        self.project_edit = self._line("project")
        self.task_label = QLabel()
        self.task_combo = self._combo("task", TASK_OPTIONS)
        self._mark_combo_values_disabled(self.task_combo, self._disabled_tasks)
        self.task_combo.currentIndexChanged.connect(self._on_task_changed)
        self.model_size_label = QLabel()
        self.model_size_combo = self._combo("model_size", MODEL_SIZE_OPTIONS)
        self.periodic_label = QLabel()
        self.periodic_combo = self._combo("periodic", PERIODIC_OPTIONS)
        basic_grid.addWidget(self.project_label, 0, 0)
        basic_grid.addWidget(self.project_edit, 0, 1)
        basic_grid.addWidget(self.task_label, 0, 2)
        basic_grid.addWidget(self.task_combo, 0, 3)
        basic_grid.addWidget(self.model_size_label, 1, 0)
        basic_grid.addWidget(self.model_size_combo, 1, 1)
        basic_grid.addWidget(self.periodic_label, 1, 2)
        basic_grid.addWidget(self.periodic_combo, 1, 3)
        layout.addWidget(self.basic_group)

        self.fixed_group = CollapsibleGroupBox()
        fixed_grid = QGridLayout(self.fixed_group)
        fixed_grid.setColumnStretch(1, 1)
        fixed_grid.setColumnStretch(3, 1)
        self.fixed_atoms_label = QLabel()
        self.fixed_atoms_edit = self._line("fixed_atoms")
        self.fixed_atoms_edit.textChanged.connect(self._sync_frozen_atoms_from_field)
        self.selected_label = QLabel()
        self.selected_edit = QLineEdit()
        self.selected_edit.setReadOnly(True)
        self.use_selection_btn = QPushButton()
        self.use_selection_btn.clicked.connect(self.use_selection_as_fixed_atoms)
        self.clear_selection_btn = QPushButton()
        self.clear_selection_btn.clicked.connect(self.clear_fixed_atom_selection)
        self.fixed_hint_label = QLabel()
        self.fixed_hint_label.setObjectName("HintLabel")
        self.freeze_percent_label = QLabel()
        self.freeze_percent_edit = self._line("freeze_bottom_z_range_percent")
        self.exclude_label = QLabel()
        self.exclude_edit = self._line("fixed_atoms_exclude_indices")
        self.reference_label = QLabel()
        self.reference_edit = QLineEdit()
        self.reference_edit.setReadOnly(True)
        self.reference_browse_btn = self._small_button()
        self.reference_browse_btn.clicked.connect(self.browse_reference_structure)
        self.reference_clear_btn = QPushButton()
        self.reference_clear_btn.clicked.connect(self.clear_reference_structure)
        self.preview_btn = QPushButton()
        self.preview_btn.clicked.connect(self.preview_auto_fixed_atoms)
        self.fixed_preview_box = QPlainTextEdit()
        self.fixed_preview_box.setReadOnly(True)
        self.fixed_preview_box.setMinimumHeight(96)

        fixed_grid.addWidget(self.fixed_atoms_label, 0, 0)
        fixed_grid.addWidget(self.fixed_atoms_edit, 0, 1, 1, 3)
        fixed_grid.addWidget(self.selected_label, 1, 0)
        fixed_grid.addWidget(self.selected_edit, 1, 1, 1, 3)
        fixed_grid.addWidget(self.use_selection_btn, 2, 0, 1, 2)
        fixed_grid.addWidget(self.clear_selection_btn, 2, 2, 1, 2)
        fixed_grid.addWidget(self.fixed_hint_label, 3, 0, 1, 4)
        for widget in (
            self.freeze_percent_label,
            self.freeze_percent_edit,
            self.exclude_label,
            self.exclude_edit,
            self.reference_label,
            self.reference_edit,
            self.reference_browse_btn,
            self.reference_clear_btn,
            self.preview_btn,
            self.fixed_preview_box,
        ):
            widget.setVisible(False)
        layout.addWidget(self.fixed_group)
        self.fixed_group.setChecked(False)

        self.electronic_group = CollapsibleGroupBox()
        electronic_grid = QGridLayout(self.electronic_group)
        electronic_grid.setColumnStretch(1, 1)
        electronic_grid.setColumnStretch(3, 1)
        self.functional_label = QLabel()
        self.functional_combo = self._combo("functional", FUNCTIONAL_OPTIONS)
        self.basis_label = QLabel()
        self.basis_combo = self._combo("basis_set", BASIS_SET_OPTIONS)
        self.dispersion_label = QLabel()
        self.dispersion_combo = self._combo("dispersion", DISPERSION_OPTIONS)
        self.charge_label = QLabel()
        self.charge_edit = self._line("charge")
        self.charge_print_label = QLabel()
        self.charge_print_combo = self._combo("charge_print", CHARGE_PRINT_OPTIONS)
        self.cube_label = QLabel()
        self.cube_combo = self._combo("cube_print", CUBE_PRINT_OPTIONS)
        self.molden_box = self._check("molden_print")
        self.molden_box.toggled.connect(self._sync_molden_alias)
        self.add_mos_box = self._check("add_mos_for_pdos")
        self.add_mos_box.toggled.connect(self._update_pdos_controls)
        self.added_mos_label = QLabel()
        self.added_mos_edit = self._line("added_mos")
        electronic_grid.addWidget(self.functional_label, 0, 0)
        electronic_grid.addWidget(self.functional_combo, 0, 1)
        electronic_grid.addWidget(self.basis_label, 0, 2)
        electronic_grid.addWidget(self.basis_combo, 0, 3)
        electronic_grid.addWidget(self.dispersion_label, 1, 0)
        electronic_grid.addWidget(self.dispersion_combo, 1, 1)
        electronic_grid.addWidget(self.charge_label, 1, 2)
        electronic_grid.addWidget(self.charge_edit, 1, 3)
        electronic_grid.addWidget(self.charge_print_label, 2, 0)
        electronic_grid.addWidget(self.charge_print_combo, 2, 1)
        electronic_grid.addWidget(self.cube_label, 2, 2)
        electronic_grid.addWidget(self.cube_combo, 2, 3)
        electronic_grid.addWidget(self.molden_box, 3, 0, 1, 2)
        electronic_grid.addWidget(self.add_mos_box, 3, 2)
        electronic_grid.addWidget(self.added_mos_edit, 3, 3)
        layout.addWidget(self.electronic_group)

        self.scf_group = CollapsibleGroupBox()
        scf_grid = QGridLayout(self.scf_group)
        scf_grid.setColumnStretch(1, 1)
        scf_grid.setColumnStretch(3, 1)
        self.scf_method_label = QLabel()
        self.scf_method_combo = self._combo("scf_method", SCF_METHOD_OPTIONS)
        self.scf_method_combo.currentIndexChanged.connect(self._update_method_controls)
        self.scf_accuracy_label = QLabel()
        self.scf_accuracy_combo = self._combo("scf_accuracy", SCF_ACCURACY_OPTIONS)
        self.scf_accuracy_combo.currentIndexChanged.connect(self._apply_scf_accuracy_preset)
        self.mixing_label = QLabel()
        self.mixing_combo = self._combo("mixing", MIXING_OPTIONS)
        self.kpoints_mode_label = QLabel()
        self.kpoints_mode_combo = self._combo("kpoints_mode", KPOINT_MODE_OPTIONS)
        self.kpoints_mode_combo.currentIndexChanged.connect(self._update_method_controls)
        self.kpoints_label = QLabel()
        self.kpoints_edit = self._line("kpoints")
        self.cutoff_label = QLabel()
        self.cutoff_edit = self._line("cutoff")
        self.rel_cutoff_label = QLabel()
        self.rel_cutoff_edit = self._line("rel_cutoff")
        self.smearing_box = self._check("smearing")
        self.smearing_box.toggled.connect(self._update_method_controls)
        self.soft_element_box = self._check("soft_element_strategy")
        self.temperature_label = QLabel()
        self.temperature_edit = self._line("electronic_temperature")
        self.diag_max_label = QLabel()
        self.diag_max_edit = self._line("diag_max_scf")
        self.diag_max_edit.textEdited.connect(self._mark_diag_max_touched)
        self.diag_eps_label = QLabel()
        self.diag_eps_edit = self._line("diag_eps_scf")
        self.ot_minimizer_label = QLabel()
        self.ot_minimizer_combo = self._combo("ot_minimizer", OT_MINIMIZER_OPTIONS)
        self.ot_inner_max_label = QLabel()
        self.ot_inner_max_edit = self._line("ot_inner_max_scf")
        self.ot_inner_eps_label = QLabel()
        self.ot_inner_eps_edit = self._line("ot_inner_eps_scf")
        self.ot_outer_max_label = QLabel()
        self.ot_outer_max_edit = self._line("ot_outer_max_scf")
        self.ot_outer_eps_label = QLabel()
        self.ot_outer_eps_edit = self._line("ot_outer_eps_scf")
        scf_grid.addWidget(self.scf_method_label, 0, 0)
        scf_grid.addWidget(self.scf_method_combo, 0, 1)
        scf_grid.addWidget(self.scf_accuracy_label, 0, 2)
        scf_grid.addWidget(self.scf_accuracy_combo, 0, 3)
        scf_grid.addWidget(self.mixing_label, 1, 0)
        scf_grid.addWidget(self.mixing_combo, 1, 1)
        scf_grid.addWidget(self.kpoints_mode_label, 1, 2)
        scf_grid.addWidget(self.kpoints_mode_combo, 1, 3)
        scf_grid.addWidget(self.kpoints_label, 2, 0)
        scf_grid.addWidget(self.kpoints_edit, 2, 1)
        scf_grid.addWidget(self.cutoff_label, 2, 2)
        scf_grid.addWidget(self.cutoff_edit, 2, 3)
        scf_grid.addWidget(self.rel_cutoff_label, 3, 0)
        scf_grid.addWidget(self.rel_cutoff_edit, 3, 1)
        scf_grid.addWidget(self.temperature_label, 3, 2)
        scf_grid.addWidget(self.temperature_edit, 3, 3)
        scf_grid.addWidget(self.smearing_box, 4, 0, 1, 2)
        scf_grid.addWidget(self.soft_element_box, 4, 2, 1, 2)
        scf_grid.addWidget(self.diag_max_label, 5, 0)
        scf_grid.addWidget(self.diag_max_edit, 5, 1)
        scf_grid.addWidget(self.diag_eps_label, 5, 2)
        scf_grid.addWidget(self.diag_eps_edit, 5, 3)
        scf_grid.addWidget(self.ot_minimizer_label, 6, 0)
        scf_grid.addWidget(self.ot_minimizer_combo, 6, 1)
        scf_grid.addWidget(self.ot_inner_max_label, 6, 2)
        scf_grid.addWidget(self.ot_inner_max_edit, 6, 3)
        scf_grid.addWidget(self.ot_inner_eps_label, 7, 0)
        scf_grid.addWidget(self.ot_inner_eps_edit, 7, 1)
        scf_grid.addWidget(self.ot_outer_max_label, 7, 2)
        scf_grid.addWidget(self.ot_outer_max_edit, 7, 3)
        scf_grid.addWidget(self.ot_outer_eps_label, 8, 0)
        scf_grid.addWidget(self.ot_outer_eps_edit, 8, 1)
        layout.addWidget(self.scf_group)

        self.mag_group = CollapsibleGroupBox()
        mag_grid = QGridLayout(self.mag_group)
        mag_grid.setColumnStretch(0, 1)
        mag_grid.setColumnStretch(1, 1)
        self.enable_mag_box = self._check("enable_magnetism")
        self.enable_mag_box.toggled.connect(self._on_magnetism_toggled)
        self.enable_dft_u_box = self._check("enable_dft_u")
        self.enable_dft_u_box.toggled.connect(self._on_dft_u_toggled)
        self.mag_rows_label = QLabel()
        self.mag_rows_edit = self._text("magnetization_rows", 90)
        self.mag_rows_edit.textChanged.connect(self._on_magnetism_rows_changed)
        self.dft_u_rows_label = QLabel()
        self.dft_u_rows_edit = self._text("dft_u_rows", 90)
        self.dft_u_rows_edit.textChanged.connect(self._on_dft_u_rows_changed)
        mag_grid.addWidget(self.enable_mag_box, 0, 0)
        mag_grid.addWidget(self.enable_dft_u_box, 0, 1)
        mag_grid.addWidget(self.mag_rows_label, 1, 0)
        mag_grid.addWidget(self.dft_u_rows_label, 1, 1)
        mag_grid.addWidget(self.mag_rows_edit, 2, 0)
        mag_grid.addWidget(self.dft_u_rows_edit, 2, 1)
        layout.addWidget(self.mag_group)
        self.mag_group.setChecked(False)

        layout.addStretch()

    def _build_visualization_panel(self, parent_layout: QVBoxLayout) -> None:
        self.visual_group = QGroupBox()
        layout = QVBoxLayout(self.visual_group)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(8)

        self.viewer_toolbar = QGridLayout()
        self.viewer_toolbar.setHorizontalSpacing(4)
        self.viewer_toolbar.setVerticalSpacing(4)
        self.view_a_btn = self._small_button()
        self.view_b_btn = self._small_button()
        self.view_c_btn = self._small_button()
        self.view_a_reverse_btn = self._small_button()
        self.view_b_reverse_btn = self._small_button()
        self.view_c_reverse_btn = self._small_button()
        self.reset_view_btn = self._small_button()
        self.rotate_x_plus_btn = self._small_button()
        self.rotate_x_minus_btn = self._small_button()
        self.rotate_y_minus_btn = self._small_button()
        self.rotate_y_plus_btn = self._small_button()
        self.rotate_z_minus_btn = self._small_button()
        self.rotate_z_plus_btn = self._small_button()
        self.view_step_label = QLabel()
        self.view_step_label.setWordWrap(False)
        self.view_step_label.setMinimumWidth(78)
        self.view_step_spin = self._double_spin(1.0, 90.0, 22.5, 0.5)
        self.view_step_spin.setFixedWidth(110)
        self.viewer_export_image_btn = QPushButton()
        self.viewer_export_image_btn.setObjectName("SmallBtn")
        self.viewer_export_image_btn.setMinimumWidth(64)
        self.viewer_export_transparent_box = QCheckBox()
        self.hide_compass_box = QCheckBox()
        self.show_symbols_box = QCheckBox()
        self.show_symbols_box.setChecked(True)
        self.show_numbers_box = QCheckBox()
        self.show_numbers_box.setChecked(True)
        for button, text in (
            (self.view_a_btn, "a"),
            (self.view_b_btn, "b"),
            (self.view_c_btn, "c"),
            (self.view_a_reverse_btn, "a*"),
            (self.view_b_reverse_btn, "b*"),
            (self.view_c_reverse_btn, "c*"),
            (self.reset_view_btn, "◇"),
            (self.rotate_x_plus_btn, "↑"),
            (self.rotate_x_minus_btn, "↓"),
            (self.rotate_y_minus_btn, "←"),
            (self.rotate_y_plus_btn, "→"),
            (self.rotate_z_minus_btn, "↶"),
            (self.rotate_z_plus_btn, "↷"),
        ):
            button.setText(text)
        self.show_symbols_box.setChecked(False)
        self.show_numbers_box.setChecked(False)

        layout.addLayout(self.viewer_toolbar)

        toolbar = QHBoxLayout()
        self.viewer_copy_selection_btn = QPushButton()
        self.viewer_add_bond_btn = QPushButton()
        self.viewer_remove_bond_btn = QPushButton()
        self.viewer_undo_btn = QPushButton()
        self.viewer_redo_btn = QPushButton()
        for button in (
            self.viewer_copy_selection_btn,
            self.viewer_add_bond_btn,
            self.viewer_remove_bond_btn,
            self.viewer_undo_btn,
            self.viewer_redo_btn,
        ):
            button.setObjectName("SmallBtn")
            button.setMinimumWidth(74)
        toolbar.addWidget(self.viewer_copy_selection_btn)
        toolbar.addWidget(self.viewer_add_bond_btn)
        toolbar.addWidget(self.viewer_remove_bond_btn)
        toolbar.addWidget(self.viewer_undo_btn)
        toolbar.addWidget(self.viewer_redo_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.canvas = MoleculeCanvas()
        self.canvas.selection_changed.connect(self._on_selection_changed)
        self.canvas.history_changed.connect(self._update_visual_history_buttons)
        self.viewer_export_image_btn.clicked.connect(self.export_canvas_image)
        self.viewer_export_transparent_box.toggled.connect(self._on_export_transparent_changed)
        self.hide_compass_box.toggled.connect(self._on_hide_compass_changed)
        self.show_symbols_box.toggled.connect(self._on_show_symbols_changed)
        self.show_numbers_box.toggled.connect(self._on_show_numbers_changed)
        self.reset_view_btn.clicked.connect(self.canvas.auto_fit)
        self.view_a_btn.clicked.connect(lambda: self.canvas.set_view_axis("A"))
        self.view_b_btn.clicked.connect(lambda: self.canvas.set_view_axis("B"))
        self.view_c_btn.clicked.connect(lambda: self.canvas.set_view_axis("C"))
        self.view_a_reverse_btn.clicked.connect(lambda: self.canvas.set_reverse_view_axis("A"))
        self.view_b_reverse_btn.clicked.connect(lambda: self.canvas.set_reverse_view_axis("B"))
        self.view_c_reverse_btn.clicked.connect(lambda: self.canvas.set_reverse_view_axis("C"))
        self.rotate_x_plus_btn.clicked.connect(lambda: self.rotate_view_by_step("x", 1))
        self.rotate_x_minus_btn.clicked.connect(lambda: self.rotate_view_by_step("x", -1))
        self.rotate_y_minus_btn.clicked.connect(lambda: self.rotate_view_by_step("y", -1))
        self.rotate_y_plus_btn.clicked.connect(lambda: self.rotate_view_by_step("y", 1))
        self.rotate_z_minus_btn.clicked.connect(lambda: self.rotate_view_by_step("z", -1))
        self.rotate_z_plus_btn.clicked.connect(lambda: self.rotate_view_by_step("z", 1))
        self.viewer_copy_selection_btn.clicked.connect(self.copy_selected_atoms)
        self.viewer_add_bond_btn.clicked.connect(self.add_selected_bonds)
        self.viewer_remove_bond_btn.clicked.connect(self.remove_selected_bonds)
        self.viewer_undo_btn.clicked.connect(self.undo_visual_action)
        self.viewer_redo_btn.clicked.connect(self.redo_visual_action)
        layout.addWidget(self.canvas, 1)
        self._viewer_toolbar_mode = ""
        self._reflow_viewer_toolbar()
        self._update_visual_history_buttons()
        parent_layout.addWidget(self.visual_group, 6)

    def _build_visualization_tab(self) -> None:
        outer = QVBoxLayout(self.visual_tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.visual_scroll = scroll
        outer.addWidget(scroll, 1)

        body = QWidget()
        scroll.setWidget(body)
        layout = QGridLayout(body)
        self.visual_body_layout = layout
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        self.visual_style_group = CollapsibleGroupBox()
        style_grid = QGridLayout(self.visual_style_group)
        self._configure_visual_grid(style_grid)
        self.visual_style_label = QLabel()
        self.visual_style_combo = NoWheelComboBox()
        self.visual_style_save_btn = QPushButton()
        self.visual_style_rename_btn = QPushButton()
        self.visual_style_delete_btn = QPushButton()
        self.visual_style_actions_label = QLabel()
        row = 0
        row = self._add_visual_form_row(style_grid, row, self.visual_style_label, self.visual_style_combo)
        row = self._add_visual_form_row(
            style_grid,
            row,
            self.visual_style_actions_label,
            self._visual_row_widget(self.visual_style_save_btn, self.visual_style_rename_btn, self.visual_style_delete_btn),
        )

        self.visual_view_group = CollapsibleGroupBox()
        view_grid = QGridLayout(self.visual_view_group)
        self._configure_visual_grid(view_grid)
        self.visual_export_label = QLabel()
        self.visual_display_label = QLabel()
        self.visual_display_extra_label = QLabel()
        self.visual_quick_view_label = QLabel()
        self.visual_bookmark_label = QLabel()
        self.visual_bookmark_extra_label = QLabel()
        self.visual_selection_label = QLabel()
        self.visual_show_symbols_box = QCheckBox()
        self.visual_show_symbols_box.setChecked(False)
        self.visual_show_numbers_box = QCheckBox()
        self.visual_show_numbers_box.setChecked(False)
        self.visual_hide_compass_box = QCheckBox()
        self.visual_hide_h_box = QCheckBox()
        self.visual_reset_view_btn = QPushButton()
        self.visual_view_a_btn = QPushButton()
        self.visual_view_b_btn = QPushButton()
        self.visual_view_c_btn = QPushButton()
        self.save_view_1_btn = QPushButton()
        self.load_view_1_btn = QPushButton()
        self.save_view_2_btn = QPushButton()
        self.load_view_2_btn = QPushButton()
        self.visual_copy_selection_btn = QPushButton()
        self.export_image_btn = QPushButton()
        self.export_transparent_box = QCheckBox()
        self.export_scale_label = QLabel()
        self.export_scale_spin = self._double_spin(1.0, 4.0, 3.0, 0.5)
        self.perspective_box = QCheckBox()
        self.perspective_box.setChecked(False)
        self.perspective_angle_label = QLabel()
        self.perspective_angle_value_label = QLabel("45\u00b0")
        self.perspective_angle_slider = NoWheelSlider(Qt.Horizontal)
        self.perspective_angle_slider.setRange(20, 60)
        self.perspective_angle_slider.setValue(45)
        for button in (self.visual_view_a_btn, self.visual_view_b_btn, self.visual_view_c_btn):
            button.setFixedWidth(34)
        for button in (self.visual_reset_view_btn, self.save_view_1_btn, self.load_view_1_btn, self.save_view_2_btn, self.load_view_2_btn):
            button.setMinimumWidth(58)
        self.perspective_box.hide()
        self.perspective_angle_label.hide()
        self.perspective_angle_value_label.hide()
        self.perspective_angle_slider.hide()
        row = 0
        row = self._add_visual_form_pair(
            view_grid,
            row,
            self.visual_export_label,
            self._visual_row_widget(self.export_image_btn),
            self.export_scale_label,
            self._visual_row_widget(self.export_scale_spin),
        )
        row = self._add_visual_form_pair(
            view_grid,
            row,
            self.visual_display_label,
            self._visual_row_widget(self.export_transparent_box, self.visual_hide_compass_box),
            self.visual_display_extra_label,
            self._visual_row_widget(self.visual_show_symbols_box, self.visual_show_numbers_box, self.visual_hide_h_box),
        )
        row = self._add_visual_form_pair(
            view_grid,
            row,
            self.visual_quick_view_label,
            self._visual_row_widget(self.visual_view_a_btn, self.visual_view_b_btn, self.visual_view_c_btn, self.visual_reset_view_btn),
            self.visual_bookmark_label,
            self._visual_row_widget(self.save_view_1_btn, self.load_view_1_btn),
        )
        row = self._add_visual_form_pair(
            view_grid,
            row,
            self.visual_selection_label,
            self._visual_row_widget(self.visual_copy_selection_btn),
            self.visual_bookmark_extra_label,
            self._visual_row_widget(self.save_view_2_btn, self.load_view_2_btn),
        )
        layout.addWidget(self.visual_view_group, 0, 0, 1, 2)

        self.cell_style_group = CollapsibleGroupBox()
        cell_grid = QGridLayout(self.cell_style_group)
        self._configure_visual_grid(cell_grid)
        self.cell_visible_box = QCheckBox()
        self.cell_visible_box.setChecked(True)
        self.cell_visible_label = QLabel()
        self.cell_display_label = QLabel()
        self.cell_display_combo = NoWheelComboBox()
        self.cell_display_combo.addItem("", "original")
        self.cell_display_combo.addItem("", "box")
        self.cell_display_combo.addItem("", "box_boundary")
        self.cell_display_combo.setCurrentIndex(self.cell_display_combo.findData("box"))
        self.cell_repeat_x_label = QLabel()
        self.cell_repeat_y_label = QLabel()
        self.cell_repeat_z_label = QLabel()
        self.cell_repeat_blank_label = QLabel()
        self.cell_repeat_x_spin = self._spin(1, 6, 1)
        self.cell_repeat_y_spin = self._spin(1, 6, 1)
        self.cell_repeat_z_spin = self._spin(1, 6, 1)
        for spin in (self.cell_repeat_x_spin, self.cell_repeat_y_spin, self.cell_repeat_z_spin):
            spin.setFixedWidth(88)
        self.cell_color_label = QLabel()
        self.cell_color_btn = QPushButton()
        self.cell_line_label = QLabel()
        self.cell_line_combo = NoWheelComboBox()
        for value in ("dash", "solid", "dot", "dash_dot", "dash_dot_dot", "long_dash", "short_dash"):
            self.cell_line_combo.addItem(value, value)
        self.cell_line_combo.setCurrentIndex(self.cell_line_combo.findData("solid"))
        self.cell_width_label = QLabel()
        self.cell_width_spin = self._double_spin(0.5, 8.0, 1.5, 0.5)
        self.cell_opacity_label = QLabel()
        self.cell_opacity_value_label = QLabel("0%")
        self.cell_opacity_slider = NoWheelSlider(Qt.Horizontal)
        self.cell_opacity_slider.setRange(0, 95)
        self.cell_opacity_slider.setValue(0)
        self.cell_reset_btn = QPushButton()
        self.cell_reset_label = QLabel()

        row = 0
        row = self._add_visual_form_pair(
            cell_grid,
            row,
            self.cell_visible_label,
            self._visual_row_widget(self.cell_visible_box),
            self.cell_display_label,
            self.cell_display_combo,
        )
        row = self._add_visual_form_pair(
            cell_grid,
            row,
            self.cell_repeat_x_label,
            self._visual_row_widget(self.cell_repeat_x_spin),
            self.cell_repeat_y_label,
            self._visual_row_widget(self.cell_repeat_y_spin),
        )
        row = self._add_visual_form_pair(
            cell_grid,
            row,
            self.cell_repeat_z_label,
            self._visual_row_widget(self.cell_repeat_z_spin),
            self.cell_line_label,
            self.cell_line_combo,
        )
        row = self._add_visual_form_pair(
            cell_grid,
            row,
            self.cell_width_label,
            self.cell_width_spin,
            self.cell_color_label,
            self._visual_color_control(self.cell_color_btn),
        )
        row = self._add_visual_form_pair(
            cell_grid,
            row,
            self.cell_opacity_label,
            self._visual_row_widget(self.cell_opacity_slider, self.cell_opacity_value_label),
            self.cell_reset_label,
            self._visual_row_widget(self.cell_reset_btn),
        )
        layout.addWidget(self.cell_style_group, 1, 0, 1, 2)

        self.atom_style_group = CollapsibleGroupBox()
        atom_grid = QGridLayout(self.atom_style_group)
        self._configure_visual_grid(atom_grid)
        self.atom_target_subhead = self._visual_subhead_label()
        self.atom_appearance_subhead = self._visual_subhead_label()
        self.atom_number_subhead = self._visual_subhead_label()
        self.atom_shadow_color_btn = QPushButton()
        self.atom_shadow_color_label = QLabel()
        self.atom_radius_mode_label = QLabel()
        self.atom_radius_mode_combo = NoWheelComboBox()
        self.atom_radius_mode_combo.addItem("", "default")
        self.atom_radius_mode_combo.addItem("", "equal")
        self.atom_radius_mode_combo.addItem("", "real")
        self.atom_representation_label = QLabel()
        self.atom_representation_combo = NoWheelComboBox()
        self.atom_representation_combo.addItem("", "ball_stick")
        self.atom_representation_combo.addItem("", "vdw")
        self.selected_atom_representation_label = QLabel()
        self.selected_atom_representation_combo = NoWheelComboBox()
        self.selected_atom_representation_combo.addItem("", "ball_stick")
        self.selected_atom_representation_combo.addItem("", "vdw")
        self.selected_atom_representation_apply_btn = QPushButton()
        self.selected_atom_representation_apply_btn.setFixedWidth(72)
        self.selected_atom_size_label = QLabel()
        self.atom_element_label = QLabel()
        self.atom_element_combo = NoWheelComboBox()
        self.atom_element_color_label = QLabel()
        self.atom_element_color_btn = QPushButton()
        self.atom_element_size_label = QLabel()
        self.atom_element_size_spin = self._double_spin(0.2, 3.0, 1.0, 0.1)
        self.atom_index_label = QLabel()
        self.atom_index_edit = QLineEdit()
        self.atom_index_color_label = QLabel()
        self.atom_index_color_btn = QPushButton()
        self.atom_index_size_spin = self._double_spin(0.2, 3.0, 1.0, 0.1)
        self.atom_outline_box = QCheckBox()
        self.atom_outline_box.setChecked(True)
        self.atom_outline_label = QLabel()
        self.atom_outline_color_label = QLabel()
        self.atom_outline_color_btn = QPushButton()
        self.atom_outline_width_label = QLabel()
        self.atom_outline_width_spin = self._double_spin(0.0, 6.0, 0.1, 0.1)
        self.atom_reset_btn = QPushButton()
        self.atom_reset_label = QLabel()
        for spin in (self.atom_element_size_spin, self.atom_index_size_spin, self.atom_outline_width_spin):
            spin.setFixedWidth(82)

        row = 0
        row = self._add_visual_subhead(atom_grid, row, self.atom_target_subhead)
        row = self._add_visual_form_pair(
            atom_grid,
            row,
            self.atom_element_label,
            self.atom_element_combo,
            self.atom_index_label,
            self.atom_index_edit,
        )
        row = self._add_visual_subhead(atom_grid, row, self.atom_appearance_subhead)
        row = self._add_visual_form_pair(
            atom_grid,
            row,
            self.atom_representation_label,
            self.atom_representation_combo,
            self.selected_atom_representation_label,
            self._visual_row_widget(
                self.selected_atom_representation_combo,
                self.selected_atom_representation_apply_btn,
            ),
        )
        row = self._add_visual_form_pair(
            atom_grid,
            row,
            self.atom_radius_mode_label,
            self.atom_radius_mode_combo,
            self.selected_atom_size_label,
            self.atom_index_size_spin,
        )
        row = self._add_visual_form_pair(
            atom_grid,
            row,
            self.atom_element_size_label,
            self.atom_element_size_spin,
            self.atom_element_color_label,
            self._visual_color_control(self.atom_element_color_btn),
        )
        row = self._add_visual_form_pair(
            atom_grid,
            row,
            self.atom_shadow_color_label,
            self._visual_color_control(self.atom_shadow_color_btn),
            self.atom_outline_label,
            self._visual_row_widget(self.atom_outline_box),
        )
        row = self._add_visual_form_pair(
            atom_grid,
            row,
            self.atom_outline_color_label,
            self._visual_color_control(self.atom_outline_color_btn),
            self.atom_outline_width_label,
            self.atom_outline_width_spin,
        )
        row = self._add_visual_subhead(atom_grid, row, self.atom_number_subhead)
        row = self._add_visual_form_pair(
            atom_grid,
            row,
            self.atom_index_color_label,
            self._visual_color_control(self.atom_index_color_btn),
            self.atom_reset_label,
            self._visual_row_widget(self.atom_reset_btn),
        )
        layout.addWidget(self.atom_style_group, 2, 0, 1, 2)

        self.bond_style_group = CollapsibleGroupBox()
        bond_grid = QGridLayout(self.bond_style_group)
        self._configure_visual_grid(bond_grid)
        self.bond_display_subhead = self._visual_subhead_label()
        self.bond_color_subhead = self._visual_subhead_label()
        self.bond_width_subhead = self._visual_subhead_label()
        self.bond_visible_box = QCheckBox()
        self.bond_visible_box.setChecked(True)
        self.bond_visible_label = QLabel()
        self.bond_mode_label = QLabel()
        self.bond_mode_combo = NoWheelComboBox()
        self.bond_mode_combo.addItem("", "split")
        self.bond_mode_combo.addItem("", "single")
        self.bond_mode_combo.setCurrentIndex(self.bond_mode_combo.findData("split"))
        self.bond_mode_combo.setFixedWidth(104)
        self.hbond_visible_box = QCheckBox()
        self.hbond_visible_box.setChecked(False)
        self.hbond_visible_label = QLabel()
        self.hbond_color_label = QLabel()
        self.hbond_color_btn = QPushButton()
        self.hbond_width_label = QLabel()
        self.hbond_width_spin = self._double_spin(0.0, 0.8, 0.3, 0.1)
        self.bond_color_label = QLabel()
        self.bond_color_btn = QPushButton()
        self.bond_width_label = QLabel()
        self.bond_width_spin = self._double_spin(0.0, 8.0, 1.0, 0.5)
        self.bond_outline_box = QCheckBox()
        self.bond_outline_box.setChecked(True)
        self.bond_outline_label = QLabel()
        self.bond_outline_color_label = QLabel()
        self.bond_outline_color_btn = QPushButton()
        self.bond_outline_color_blank_label = QLabel()
        self.bond_outline_width_label = QLabel()
        self.bond_outline_width_spin = self._double_spin(0.0, 6.0, 0.8, 0.1)
        self.bond_reset_btn = QPushButton()
        self.bond_reset_label = QLabel()
        for spin in (self.bond_width_spin, self.hbond_width_spin, self.bond_outline_width_spin):
            spin.setFixedWidth(82)

        row = 0
        row = self._add_visual_subhead(bond_grid, row, self.bond_display_subhead)
        row = self._add_visual_form_pair(
            bond_grid,
            row,
            self.bond_visible_label,
            self._visual_row_widget(self.bond_visible_box),
            self.hbond_visible_label,
            self._visual_row_widget(self.hbond_visible_box),
        )
        row = self._add_visual_form_pair(
            bond_grid,
            row,
            self.bond_outline_label,
            self._visual_row_widget(self.bond_outline_box),
            self.bond_mode_label,
            self.bond_mode_combo,
        )
        row = self._add_visual_subhead(bond_grid, row, self.bond_color_subhead)
        row = self._add_visual_form_pair(
            bond_grid,
            row,
            self.bond_color_label,
            self._visual_color_control(self.bond_color_btn),
            self.hbond_color_label,
            self._visual_color_control(self.hbond_color_btn),
        )
        row = self._add_visual_form_pair(
            bond_grid,
            row,
            self.bond_outline_color_label,
            self._visual_color_control(self.bond_outline_color_btn),
            self.bond_outline_color_blank_label,
            QWidget(),
        )
        row = self._add_visual_subhead(bond_grid, row, self.bond_width_subhead)
        row = self._add_visual_form_pair(
            bond_grid,
            row,
            self.bond_width_label,
            self.bond_width_spin,
            self.hbond_width_label,
            self.hbond_width_spin,
        )
        row = self._add_visual_form_pair(
            bond_grid,
            row,
            self.bond_outline_width_label,
            self.bond_outline_width_spin,
            self.bond_reset_label,
            self._visual_row_widget(self.bond_reset_btn),
        )
        layout.addWidget(self.bond_style_group, 3, 0, 1, 2)
        layout.setRowStretch(4, 1)

        self.visual_style_combo.currentIndexChanged.connect(self._on_visual_style_changed)
        self.visual_style_save_btn.clicked.connect(self.save_current_visual_style)
        self.visual_style_rename_btn.clicked.connect(self.rename_current_visual_style)
        self.visual_style_delete_btn.clicked.connect(self.delete_current_visual_style)
        self.visual_show_symbols_box.toggled.connect(self._on_show_symbols_changed)
        self.visual_show_numbers_box.toggled.connect(self._on_show_numbers_changed)
        self.visual_hide_compass_box.toggled.connect(self._on_hide_compass_changed)
        self.visual_hide_h_box.toggled.connect(self._on_hide_h_changed)
        self.visual_reset_view_btn.clicked.connect(self.canvas.auto_fit)
        self.visual_view_a_btn.clicked.connect(lambda: self.canvas.set_view_axis("A"))
        self.visual_view_b_btn.clicked.connect(lambda: self.canvas.set_view_axis("B"))
        self.visual_view_c_btn.clicked.connect(lambda: self.canvas.set_view_axis("C"))
        self.save_view_1_btn.clicked.connect(lambda: self.save_custom_view(1))
        self.load_view_1_btn.clicked.connect(lambda: self.load_custom_view(1))
        self.save_view_2_btn.clicked.connect(lambda: self.save_custom_view(2))
        self.load_view_2_btn.clicked.connect(lambda: self.load_custom_view(2))
        self.visual_copy_selection_btn.clicked.connect(self.copy_selected_atoms)
        self.export_image_btn.clicked.connect(self.export_canvas_image)
        self.export_transparent_box.toggled.connect(self._on_export_transparent_changed)
        self.perspective_box.toggled.connect(self.canvas.set_perspective_enabled)
        self.perspective_angle_slider.valueChanged.connect(self._on_perspective_angle_changed)
        self.cell_visible_box.toggled.connect(self.canvas.set_cell_visible)
        self.cell_display_combo.currentIndexChanged.connect(self._on_cell_display_mode_changed)
        self.cell_repeat_x_spin.valueChanged.connect(self._on_cell_repeats_changed)
        self.cell_repeat_y_spin.valueChanged.connect(self._on_cell_repeats_changed)
        self.cell_repeat_z_spin.valueChanged.connect(self._on_cell_repeats_changed)
        self.cell_color_btn.clicked.connect(self.choose_cell_color)
        self.cell_width_spin.valueChanged.connect(self._on_cell_width_changed)
        self.cell_line_combo.currentIndexChanged.connect(self._on_cell_line_type_changed)
        self.cell_opacity_slider.valueChanged.connect(self._on_cell_opacity_changed)
        self.cell_reset_btn.clicked.connect(self.reset_cell_style)
        self.atom_shadow_color_btn.clicked.connect(self.choose_atom_shadow_color)
        self.atom_radius_mode_combo.currentIndexChanged.connect(self._on_atom_radius_mode_changed)
        self.atom_representation_combo.currentIndexChanged.connect(self._on_atom_representation_changed)
        self.selected_atom_representation_apply_btn.clicked.connect(self.apply_selected_atom_representation)
        self.atom_element_combo.currentIndexChanged.connect(lambda _index: self._on_atom_element_changed(select_atoms=True))
        self.atom_element_color_btn.clicked.connect(self.choose_atom_element_color)
        self.atom_element_size_spin.valueChanged.connect(self._on_atom_element_size_changed)
        self.atom_index_edit.textChanged.connect(self._on_atom_index_targets_changed)
        self.atom_index_color_btn.clicked.connect(self.choose_atom_index_color)
        self.atom_index_size_spin.valueChanged.connect(self._on_atom_index_size_changed)
        self.atom_outline_box.toggled.connect(self.canvas.set_atom_outline_enabled)
        self.atom_outline_color_btn.clicked.connect(self.choose_atom_outline_color)
        self.atom_outline_width_spin.valueChanged.connect(self.canvas.set_atom_outline_width)
        self.atom_reset_btn.clicked.connect(self.reset_atom_style)
        self.bond_visible_box.toggled.connect(self.canvas.set_bonds_visible)
        self.bond_mode_combo.currentIndexChanged.connect(self._on_bond_color_mode_changed)
        self.hbond_visible_box.toggled.connect(self.canvas.set_hydrogen_bonds_visible)
        self.hbond_color_btn.clicked.connect(self.choose_hydrogen_bond_color)
        self.hbond_width_spin.valueChanged.connect(self.canvas.set_hydrogen_bond_width)
        self.bond_color_btn.clicked.connect(self.choose_bond_color)
        self.bond_width_spin.valueChanged.connect(self.canvas.set_bond_width)
        self.bond_outline_box.toggled.connect(self.canvas.set_bond_outline_enabled)
        self.bond_outline_color_btn.clicked.connect(self.choose_bond_outline_color)
        self.bond_outline_width_spin.valueChanged.connect(self.canvas.set_bond_outline_width)
        self.bond_reset_btn.clicked.connect(self.reset_bond_style)
        self._on_cell_display_mode_changed()
        self._on_cell_repeats_changed()
        self._on_cell_width_changed(self.cell_width_spin.value())
        self.canvas.set_atom_outline_enabled(self.atom_outline_box.isChecked())
        self.canvas.set_atom_radius_mode(str(self.atom_radius_mode_combo.currentData() or "default"))
        self.canvas.set_atom_representation_mode(str(self.atom_representation_combo.currentData() or "ball_stick"))
        self.canvas.set_bond_outline_enabled(self.bond_outline_box.isChecked())
        self.canvas.set_bond_color_mode(str(self.bond_mode_combo.currentData() or "split"))
        self.canvas.set_bonds_visible(self.bond_visible_box.isChecked())
        self.canvas.set_hydrogen_bonds_visible(self.hbond_visible_box.isChecked())
        self.canvas.set_hydrogen_bond_width(self.hbond_width_spin.value())
        self._refresh_atom_element_combo()
        self._refresh_visual_style_combo()
        self._refresh_cell_color_button()
        self._refresh_visual_color_buttons()

    def _build_settings_tab(self) -> None:
        layout = QVBoxLayout(self.settings_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.settings_group = QGroupBox()
        grid = QGridLayout(self.settings_group)
        grid.setColumnStretch(1, 1)
        self.multiwfn_label = QLabel()
        self.multiwfn_edit = QLineEdit(normalize_multiwfn_path(self.settings.multiwfn_path))
        self.multiwfn_browse_btn = self._small_button()
        self.multiwfn_browse_btn.clicked.connect(self.browse_multiwfn)
        self.language_label = QLabel()
        self.language_combo = NoWheelComboBox()
        self.language_combo.addItem("", "zh")
        self.language_combo.addItem("", "en")
        self.language_combo.setCurrentIndex(0 if self.language == "zh" else 1)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        self.save_settings_btn = QPushButton()
        self.save_settings_btn.setObjectName("PrimaryBtn")
        self.save_settings_btn.clicked.connect(self.save_settings_from_ui)
        grid.addWidget(self.multiwfn_label, 0, 0)
        grid.addWidget(self.multiwfn_edit, 0, 1)
        grid.addWidget(self.multiwfn_browse_btn, 0, 2)
        grid.addWidget(self.language_label, 1, 0)
        grid.addWidget(self.language_combo, 1, 1, 1, 2)
        grid.addWidget(self.save_settings_btn, 2, 0, 1, 3)
        layout.addWidget(self.settings_group)
        layout.addWidget(self.visual_style_group)
        layout.addStretch()

    def _mirror_checkboxes(self, checked: bool, *boxes: QCheckBox) -> None:
        for box in boxes:
            if box.isChecked() == checked:
                continue
            blocker = QSignalBlocker(box)
            box.setChecked(checked)
            del blocker

    def _on_show_symbols_changed(self, checked: bool) -> None:
        self._mirror_checkboxes(bool(checked), self.show_symbols_box, self.visual_show_symbols_box)
        self.canvas.set_show_symbols(bool(checked))

    def _on_show_numbers_changed(self, checked: bool) -> None:
        self._mirror_checkboxes(bool(checked), self.show_numbers_box, self.visual_show_numbers_box)
        self.canvas.set_show_numbers(bool(checked))

    def _on_hide_compass_changed(self, checked: bool) -> None:
        self._mirror_checkboxes(bool(checked), self.hide_compass_box, self.visual_hide_compass_box)
        self.canvas.set_show_compass(not bool(checked))

    def _on_export_transparent_changed(self, checked: bool) -> None:
        self._mirror_checkboxes(bool(checked), self.viewer_export_transparent_box, self.export_transparent_box)

    def _on_hide_h_changed(self, checked: bool) -> None:
        self._mirror_checkboxes(bool(checked), self.visual_hide_h_box)
        self.canvas.set_hide_hydrogens(bool(checked))

    def _on_perspective_angle_changed(self, value: int) -> None:
        self.perspective_angle_value_label.setText(f"{int(value)}\u00b0")
        self.canvas.set_perspective_angle(int(value))

    def _set_color_swatch(self, swatch: QLabel | None, color: QColor, enabled: bool = True) -> None:
        if not isinstance(swatch, QLabel):
            return
        fill = color.name() if enabled else "#F1F5F9"
        border = "#94A3B8" if enabled else "#CBD5E1"
        swatch.setStyleSheet(f"background-color: {fill}; border: 1px solid {border}; border-radius: 4px;")
        swatch.setToolTip(color.name().upper())

    def _refresh_cell_color_button(self) -> None:
        color = getattr(self.canvas, "cell_color", QColor("#000000"))
        self.cell_color_btn.setText(tr(self.language, "choose_color"))
        self.cell_color_btn.setStyleSheet("")
        self.cell_color_btn.setToolTip(color.name().upper())
        self._set_color_swatch(getattr(self.cell_color_btn, "_color_swatch", None), color, self.cell_color_btn.isEnabled())

    def _seed_color_dialog_palette(self) -> None:
        for index in range(64):
            QColorDialog.setStandardColor(index, QColor("#FFFFFF"))
        for index, hex_color in enumerate(VESTA_BASIC_COLOR_PALETTE):
            QColorDialog.setStandardColor(index, QColor(hex_color))
        for index in range(QColorDialog.customCount()):
            QColorDialog.setCustomColor(index, QColor("#FFFFFF"))

    def _choose_color(self, current: QColor, title_key: str) -> QColor:
        self._seed_color_dialog_palette()
        return QColorDialog.getColor(QColor(current), self, tr(self.language, title_key))

    def choose_cell_color(self) -> None:
        current = getattr(self.canvas, "cell_color", QColor("#000000"))
        color = self._choose_color(current, "cell_color")
        if not color.isValid():
            return
        self.canvas.set_cell_color(color)
        self._refresh_cell_color_button()

    def _on_cell_display_mode_changed(self) -> None:
        self.canvas.set_cell_display_mode(str(self.cell_display_combo.currentData() or "box"))

    def _on_cell_repeats_changed(self) -> None:
        self.canvas.set_cell_repeats(
            self.cell_repeat_x_spin.value(),
            self.cell_repeat_y_spin.value(),
            self.cell_repeat_z_spin.value(),
        )

    def _on_cell_width_changed(self, value: float) -> None:
        self.canvas.set_cell_width(float(value))

    def _on_cell_line_type_changed(self) -> None:
        self.canvas.set_cell_line_type(str(self.cell_line_combo.currentData() or "dash"))

    def _on_cell_opacity_changed(self, value: int) -> None:
        transparency = max(0, min(95, int(value)))
        self.cell_opacity_value_label.setText(f"{transparency}%")
        self.canvas.set_cell_opacity(max(0.05, min(1.0, 1.0 - transparency / 100.0)))

    def _cell_transparency_from_opacity(self, opacity: float) -> int:
        alpha = max(0.05, min(1.0, float(opacity)))
        return max(0, min(95, int(round((1.0 - alpha) * 100))))

    def _button_text_color(self, color: QColor) -> str:
        luminance = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255
        return "#111827" if luminance > 0.62 else "#FFFFFF"

    def _set_color_button(self, button: QPushButton, color: QColor, text: str) -> None:
        button.setText(tr(self.language, "choose_color"))
        button.setStyleSheet("")
        button.setToolTip(f"{text}: {color.name().upper()}")
        self._set_color_swatch(getattr(button, "_color_swatch", None), color, button.isEnabled())

    def _refresh_visual_color_buttons(self) -> None:
        self._refresh_cell_color_button()
        symbol = self._current_atom_symbol()
        element_color = QColor(self.canvas.atom_element_colors.get(symbol, QColor(ATOM_COLORS.get(symbol, "#8E8E8E"))))
        self._set_color_button(self.atom_element_color_btn, element_color, tr(self.language, "atom_element_color"))
        index_color = QColor("#8E8E8E")
        for atom_index in sorted(self._current_atom_indices()):
            if atom_index in self.canvas.atom_index_colors:
                index_color = QColor(self.canvas.atom_index_colors[atom_index])
                break
        self._set_color_button(self.atom_shadow_color_btn, QColor(self.canvas.atom_shadow_color), tr(self.language, "atom_shadow_color"))
        self._set_color_button(self.atom_index_color_btn, index_color, tr(self.language, "atom_index_color"))
        self._set_color_button(self.atom_outline_color_btn, QColor(self.canvas.atom_outline_color), tr(self.language, "outline_color_choose"))
        self._set_color_button(self.bond_color_btn, QColor(self.canvas.bond_custom_color), tr(self.language, "bond_color_choose"))
        bond_single_color_enabled = str(self.bond_mode_combo.currentData() or "split") == "single"
        self.bond_color_btn.setEnabled(bond_single_color_enabled)
        self._set_color_swatch(getattr(self.bond_color_btn, "_color_swatch", None), QColor(self.canvas.bond_custom_color), bond_single_color_enabled)
        self._set_color_button(self.bond_outline_color_btn, QColor(self.canvas.bond_outline_color), tr(self.language, "outline_color_choose"))
        self._set_color_button(self.hbond_color_btn, QColor(self.canvas.hydrogen_bond_color), tr(self.language, "hydrogen_bond_color"))

    def _current_atom_symbol(self) -> str:
        return str(self.atom_element_combo.currentData() or self.atom_element_combo.currentText() or "H")

    def _current_atom_indices(self) -> set[int]:
        return parse_atom_indices(self.atom_index_edit.text())

    def _refresh_atom_element_combo(self) -> None:
        previous = self._current_atom_symbol() if hasattr(self, "atom_element_combo") else ""
        symbols: list[str] = []
        if self.current_molecule:
            for atom in self.current_molecule.atoms:
                if atom.symbol not in symbols:
                    symbols.append(atom.symbol)
        if not symbols:
            symbols = ["H", "C", "N", "O", "F", "S", "Cl", "Ti", "Fe", "Ni", "Cu", "Zn", "W", "Ce", "U"]
        blocker = QSignalBlocker(self.atom_element_combo)
        self.atom_element_combo.clear()
        for symbol in symbols:
            self.atom_element_combo.addItem(symbol, symbol)
        index = self.atom_element_combo.findData(previous)
        self.atom_element_combo.setCurrentIndex(index if index >= 0 else 0)
        del blocker
        self._on_atom_element_changed(select_atoms=False)

    def choose_atom_element_color(self) -> None:
        symbol = self._current_atom_symbol()
        current = QColor(self.canvas.atom_element_colors.get(symbol, QColor(ATOM_COLORS.get(symbol, "#8E8E8E"))))
        color = self._choose_color(current, "atom_element_color")
        if color.isValid():
            self.canvas.set_atom_element_style(symbol, color=color, size=self.atom_element_size_spin.value())
            self._refresh_visual_color_buttons()

    def choose_atom_index_color(self) -> None:
        indices = self._current_atom_indices()
        if not indices:
            self._set_status("status_no_selection")
            return
        current = QColor("#8E8E8E")
        for atom_index in sorted(indices):
            if atom_index in self.canvas.atom_index_colors:
                current = QColor(self.canvas.atom_index_colors[atom_index])
                break
        color = self._choose_color(current, "atom_index_color")
        if color.isValid():
            self.canvas.set_atom_index_style(indices, color=color, size=self.atom_index_size_spin.value())
            self._refresh_visual_color_buttons()

    def choose_atom_shadow_color(self) -> None:
        color = self._choose_color(QColor(self.canvas.atom_shadow_color), "atom_shadow_color")
        if color.isValid():
            self.canvas.set_atom_shadow_color(color)
            self._refresh_visual_color_buttons()

    def choose_atom_outline_color(self) -> None:
        color = self._choose_color(QColor(self.canvas.atom_outline_color), "atom_outline_color")
        if color.isValid():
            self.canvas.set_atom_outline_color(color)
            self._refresh_visual_color_buttons()

    def _on_atom_radius_mode_changed(self) -> None:
        self.canvas.set_atom_radius_mode(str(self.atom_radius_mode_combo.currentData() or "default"))

    def _on_atom_representation_changed(self) -> None:
        self.canvas.set_atom_representation_mode(
            str(self.atom_representation_combo.currentData() or "ball_stick")
        )

    def apply_selected_atom_representation(self) -> None:
        indices = self._current_atom_indices()
        if not indices:
            self._set_status("status_no_selection")
            return
        mode = str(self.selected_atom_representation_combo.currentData() or "ball_stick")
        changed = self.canvas.set_atom_index_representation(indices, mode)
        representation = tr(
            self.language,
            "atom_representation_vdw" if mode == "vdw" else "atom_representation_ball_stick",
        )
        self._set_status(
            "status_atom_representation_applied",
            f"{representation} ({changed or len(indices)})",
        )

    def choose_bond_color(self) -> None:
        color = self._choose_color(QColor(self.canvas.bond_custom_color), "bond_color")
        if color.isValid():
            self.canvas.set_bond_custom_color(color)
            self._refresh_visual_color_buttons()

    def _on_bond_color_mode_changed(self) -> None:
        mode = str(self.bond_mode_combo.currentData() or "split")
        self.canvas.set_bond_color_mode(mode)
        self.bond_color_btn.setEnabled(mode == "single")
        self._set_color_swatch(getattr(self.bond_color_btn, "_color_swatch", None), QColor(self.canvas.bond_custom_color), mode == "single")

    def choose_hydrogen_bond_color(self) -> None:
        color = self._choose_color(QColor(self.canvas.hydrogen_bond_color), "hydrogen_bond_color")
        if color.isValid():
            self.canvas.set_hydrogen_bond_color(color)
            self._refresh_visual_color_buttons()

    def choose_bond_outline_color(self) -> None:
        color = self._choose_color(QColor(self.canvas.bond_outline_color), "bond_outline_color")
        if color.isValid():
            self.canvas.set_bond_outline_color(color)
            self._refresh_visual_color_buttons()

    def _on_atom_element_changed(self, select_atoms: bool = True) -> None:
        symbol = self._current_atom_symbol()
        size = self.canvas.atom_element_sizes.get(symbol, 1.0)
        blocker = QSignalBlocker(self.atom_element_size_spin)
        self.atom_element_size_spin.setValue(size)
        del blocker
        if select_atoms and self.current_molecule:
            self.canvas.select_atoms_by_symbol(symbol)
        self._refresh_visual_color_buttons()

    def _on_atom_element_size_changed(self, value: float) -> None:
        symbol = self._current_atom_symbol()
        if self.current_molecule:
            for atom in self.current_molecule.atoms:
                if atom.symbol == symbol:
                    self.canvas.atom_index_sizes.pop(atom.index, None)
        self.canvas.set_atom_element_style(symbol, size=float(value))

    def _on_atom_index_targets_changed(self) -> None:
        indices = self._current_atom_indices()
        size = 1.0
        for atom_index in sorted(indices):
            if atom_index in self.canvas.atom_index_sizes:
                size = self.canvas.atom_index_sizes[atom_index]
                break
        blocker = QSignalBlocker(self.atom_index_size_spin)
        self.atom_index_size_spin.setValue(size)
        del blocker
        self._refresh_visual_color_buttons()

    def _on_atom_index_size_changed(self, value: float) -> None:
        indices = self._current_atom_indices()
        if indices:
            self.canvas.set_atom_index_style(indices, size=float(value))

    def _on_bond_type_changed(self) -> None:
        self.canvas.set_bond_line_type("solid")

    def copy_selected_atoms(self) -> None:
        text = self.selected_edit.text().strip()
        if not text:
            self._set_status("status_no_selection")
            return
        QApplication.clipboard().setText(text)
        self._set_status("status_selection_copied", text)

    def export_canvas_image(self) -> None:
        filters = "PNG (*.png);;TIFF (*.tif *.tiff);;JPEG (*.jpg *.jpeg);;BMP (*.bmp)"
        default_name = f"{self._safe_project() or 'CP2K_FORGE_view'}.png"
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            tr(self.language, "export_image"),
            str(Path.cwd() / default_name),
            filters,
        )
        if not path:
            return
        suffix = Path(path).suffix.lower()
        if not suffix:
            if "TIFF" in selected_filter:
                path += ".tif"
                suffix = ".tif"
            elif "JPEG" in selected_filter:
                path += ".jpg"
                suffix = ".jpg"
            elif "BMP" in selected_filter:
                path += ".bmp"
                suffix = ".bmp"
            else:
                path += ".png"
                suffix = ".png"
        fmt = {".jpg": "JPG", ".jpeg": "JPG", ".tif": "TIFF", ".tiff": "TIFF", ".bmp": "BMP"}.get(suffix, "PNG")
        transparent = self.export_transparent_box.isChecked() and fmt in {"PNG", "TIFF"}
        image = self.canvas.render_to_image(scale=self.export_scale_spin.value(), transparent_background=transparent)
        if not image.save(path, fmt):
            QMessageBox.warning(self, tr(self.language, "warning"), tr(self.language, "export_image_failed"))
            return
        self._set_status("status_image_exported", path)

    def save_custom_view(self, slot: int) -> None:
        self.canvas.save_custom_view(slot)
        self._set_status("status_view_saved", str(slot))

    def load_custom_view(self, slot: int) -> None:
        if self.canvas.load_custom_view(slot):
            self._set_status("status_view_loaded", str(slot))
        else:
            self._set_status("status_view_empty", str(slot))

    def rotate_view_by_step(self, axis: str, direction: int) -> None:
        self.canvas.rotate_view(axis, float(direction) * self.view_step_spin.value())

    def add_selected_bonds(self) -> None:
        added = self.canvas.add_bonds_for_selection()
        self._set_status("status_bonds_added", str(added))

    def remove_selected_bonds(self) -> None:
        removed = self.canvas.remove_bonds_for_selection()
        self._set_status("status_bonds_removed", str(removed))

    def _update_visual_history_buttons(self) -> None:
        if hasattr(self, "viewer_undo_btn"):
            self.viewer_undo_btn.setEnabled(self.canvas.can_undo())
        if hasattr(self, "viewer_redo_btn"):
            self.viewer_redo_btn.setEnabled(self.canvas.can_redo())

    def _sync_visual_controls_from_canvas(self) -> None:
        self._set_checked_blocked(self.show_symbols_box, self.canvas.show_symbols)
        self._set_checked_blocked(self.visual_show_symbols_box, self.canvas.show_symbols)
        self._set_checked_blocked(self.show_numbers_box, self.canvas.show_numbers)
        self._set_checked_blocked(self.visual_show_numbers_box, self.canvas.show_numbers)
        self._set_checked_blocked(self.hide_compass_box, not self.canvas.show_compass)
        self._set_checked_blocked(self.visual_hide_compass_box, not self.canvas.show_compass)
        self._set_checked_blocked(self.visual_hide_h_box, self.canvas.hide_hydrogens)

        self._set_checked_blocked(self.perspective_box, self.canvas.perspective_enabled)
        self._set_slider_value_blocked(self.perspective_angle_slider, self.canvas.perspective_angle)
        self.perspective_angle_value_label.setText(f"{self.canvas.perspective_angle}\u00b0")

        self._set_checked_blocked(self.cell_visible_box, self.canvas.cell_visible)
        self._set_combo_value_blocked(self.cell_display_combo, self.canvas.cell_display_mode)
        self._set_spin_value_blocked(self.cell_repeat_x_spin, self.canvas.cell_repeats[0])
        self._set_spin_value_blocked(self.cell_repeat_y_spin, self.canvas.cell_repeats[1])
        self._set_spin_value_blocked(self.cell_repeat_z_spin, self.canvas.cell_repeats[2])
        self._set_combo_value_blocked(self.cell_line_combo, self.canvas.cell_line_type)
        self._set_spin_value_blocked(self.cell_width_spin, self.canvas.cell_width)
        transparency = self._cell_transparency_from_opacity(self.canvas.cell_opacity)
        self._set_slider_value_blocked(self.cell_opacity_slider, transparency)
        self.cell_opacity_value_label.setText(f"{transparency}%")

        self._set_combo_value_blocked(self.atom_radius_mode_combo, self.canvas.atom_radius_mode)
        self._set_combo_value_blocked(
            self.atom_representation_combo,
            self.canvas.atom_representation_mode,
        )
        self._set_checked_blocked(self.atom_outline_box, self.canvas.atom_outline_enabled)
        self._set_spin_value_blocked(self.atom_outline_width_spin, self.canvas.atom_outline_width)
        self._on_atom_element_changed(select_atoms=False)
        self._on_atom_index_targets_changed()

        self._set_checked_blocked(self.bond_visible_box, self.canvas.bonds_visible)
        self._set_combo_value_blocked(self.bond_mode_combo, self.canvas.bond_color_mode)
        self._set_checked_blocked(self.hbond_visible_box, self.canvas.hydrogen_bonds_visible)
        self._set_spin_value_blocked(self.bond_width_spin, self.canvas.bond_width)
        self._set_checked_blocked(self.bond_outline_box, self.canvas.bond_outline_enabled)
        self._set_spin_value_blocked(self.bond_outline_width_spin, self.canvas.bond_outline_width)
        self._set_spin_value_blocked(self.hbond_width_spin, self.canvas.hydrogen_bond_width)

        self._refresh_visual_color_buttons()
        self._update_visual_history_buttons()

    def undo_visual_action(self) -> None:
        if self.canvas.undo():
            self._sync_visual_controls_from_canvas()
            self._set_status("status_visual_undo")
        else:
            self._set_status("status_visual_undo_empty")

    def redo_visual_action(self) -> None:
        if self.canvas.redo():
            self._sync_visual_controls_from_canvas()
            self._set_status("status_visual_redo")
        else:
            self._set_status("status_visual_redo_empty")

    def _style_by_name(self, name: str) -> dict[str, Any] | None:
        key = str(name or "").casefold()
        for style in self.visual_styles:
            if str(style.get("name", "")).casefold() == key:
                return style
        return None

    def _refresh_visual_style_combo(self, keep_current: bool = False, select_name: str | None = None) -> None:
        if not hasattr(self, "visual_style_combo"):
            return
        current = select_name or (self.visual_style_combo.currentData() if keep_current else DEFAULT_STYLE_ID)
        blocker = QSignalBlocker(self.visual_style_combo)
        self.visual_style_combo.clear()
        self.visual_style_combo.addItem(tr(self.language, "visual_style_default"), DEFAULT_STYLE_ID)
        for style in self.visual_styles:
            name = str(style.get("name", "")).strip()
            if name:
                self.visual_style_combo.addItem(name, name)
        index = self.visual_style_combo.findData(current)
        self.visual_style_combo.setCurrentIndex(index if index >= 0 else 0)
        del blocker

    def _current_visual_style_id(self) -> str:
        if not hasattr(self, "visual_style_combo"):
            return DEFAULT_STYLE_ID
        return str(self.visual_style_combo.currentData() or DEFAULT_STYLE_ID)

    def _color_map_to_json(self, values: dict[Any, QColor]) -> dict[str, str]:
        return {str(key): QColor(color).name() for key, color in values.items()}

    def _color_map_from_json(self, values: Any, *, int_keys: bool = False) -> dict[Any, QColor]:
        if not isinstance(values, dict):
            return {}
        result: dict[Any, QColor] = {}
        for raw_key, raw_color in values.items():
            color = QColor(str(raw_color))
            if not color.isValid():
                continue
            key: Any = raw_key
            if int_keys:
                try:
                    key = int(raw_key)
                except (TypeError, ValueError):
                    continue
            result[key] = color
        return result

    def _float_map_from_json(self, values: Any, *, int_keys: bool = False) -> dict[Any, float]:
        if not isinstance(values, dict):
            return {}
        result: dict[Any, float] = {}
        for raw_key, raw_value in values.items():
            key: Any = raw_key
            if int_keys:
                try:
                    key = int(raw_key)
                except (TypeError, ValueError):
                    continue
            try:
                result[key] = float(raw_value)
            except (TypeError, ValueError):
                continue
        return result

    def _default_visual_style_snapshot(self) -> dict[str, Any]:
        return {
            "view": {"rot_x": -72.4, "rot_y": -24.4, "rot_z": -7.5, "zoom": 1.0, "pan_x": 0.0, "pan_y": max(self.canvas.height(), 1) * 0.14},
            "labels": {"show_symbols": False, "show_numbers": False, "hide_hydrogens": False, "hide_compass": False},
            "perspective": {"enabled": False, "angle": 45},
            "cell": {
                "visible": True,
                "display_mode": "box",
                "repeats": [1, 1, 1],
                "color": "#000000",
                "width": 1.5,
                "line_type": "solid",
                "opacity": 1.0,
            },
            "atom": {
                "radius_mode": "default",
                "representation_mode": "ball_stick",
                "index_representations": {},
                "shadow_color": "#B8B8B8",
                "element_colors": {},
                "index_colors": {},
                "element_sizes": {},
                "index_sizes": {},
                "outline_enabled": True,
                "outline_color": "#1F2937",
                "outline_width": 0.1,
            },
            "bond": {
                "visible": True,
                "mode": "split",
                "custom_color": "#8A8A8A",
                "width": 1.0,
                "outline_enabled": True,
                "outline_color": "#1F2937",
                "outline_width": 0.8,
                "hydrogen_visible": False,
                "hydrogen_color": "#9CA3AF",
                "hydrogen_width": 0.3,
            },
        }

    def _capture_visual_style(self) -> dict[str, Any]:
        return {
            "view": {
                "rot_x": self.canvas.rot_x,
                "rot_y": self.canvas.rot_y,
                "rot_z": self.canvas.rot_z,
                "zoom": self.canvas.zoom,
                "pan_x": self.canvas.pan_x,
                "pan_y": self.canvas.pan_y,
            },
            "labels": {
                "show_symbols": self.show_symbols_box.isChecked(),
                "show_numbers": self.show_numbers_box.isChecked(),
                "hide_hydrogens": self.visual_hide_h_box.isChecked(),
                "hide_compass": self.hide_compass_box.isChecked(),
            },
            "perspective": {"enabled": self.perspective_box.isChecked(), "angle": self.perspective_angle_slider.value()},
            "cell": {
                "visible": self.cell_visible_box.isChecked(),
                "display_mode": str(self.cell_display_combo.currentData() or "box"),
                "repeats": [self.cell_repeat_x_spin.value(), self.cell_repeat_y_spin.value(), self.cell_repeat_z_spin.value()],
                "color": QColor(self.canvas.cell_color).name(),
                "width": self.cell_width_spin.value(),
                "line_type": str(self.cell_line_combo.currentData() or "dash"),
                "opacity": max(0.05, min(1.0, 1.0 - self.cell_opacity_slider.value() / 100.0)),
            },
            "atom": {
                "radius_mode": str(self.atom_radius_mode_combo.currentData() or "default"),
                "representation_mode": str(
                    self.atom_representation_combo.currentData() or "ball_stick"
                ),
                "index_representations": {
                    str(key): value
                    for key, value in self.canvas.atom_index_representations.items()
                },
                "shadow_color": QColor(self.canvas.atom_shadow_color).name(),
                "element_colors": self._color_map_to_json(self.canvas.atom_element_colors),
                "index_colors": self._color_map_to_json(self.canvas.atom_index_colors),
                "element_sizes": {str(key): value for key, value in self.canvas.atom_element_sizes.items()},
                "index_sizes": {str(key): value for key, value in self.canvas.atom_index_sizes.items()},
                "outline_enabled": self.atom_outline_box.isChecked(),
                "outline_color": QColor(self.canvas.atom_outline_color).name(),
                "outline_width": self.atom_outline_width_spin.value(),
            },
            "bond": {
                "visible": self.bond_visible_box.isChecked(),
                "mode": str(self.bond_mode_combo.currentData() or "split"),
                "custom_color": QColor(self.canvas.bond_custom_color).name(),
                "width": self.bond_width_spin.value(),
                "outline_enabled": self.bond_outline_box.isChecked(),
                "outline_color": QColor(self.canvas.bond_outline_color).name(),
                "outline_width": self.bond_outline_width_spin.value(),
                "hydrogen_visible": self.hbond_visible_box.isChecked(),
                "hydrogen_color": QColor(self.canvas.hydrogen_bond_color).name(),
                "hydrogen_width": self.hbond_width_spin.value(),
            },
        }

    def _set_combo_value_blocked(self, combo: QComboBox, value: str) -> None:
        blocker = QSignalBlocker(combo)
        self._set_combo_value(combo, value)
        del blocker

    def _set_checked_blocked(self, box: QCheckBox, checked: bool) -> None:
        blocker = QSignalBlocker(box)
        box.setChecked(bool(checked))
        del blocker

    def _set_spin_value_blocked(self, spin: QDoubleSpinBox | QSpinBox, value: float) -> None:
        blocker = QSignalBlocker(spin)
        if isinstance(spin, QSpinBox):
            spin.setValue(int(value))
        else:
            spin.setValue(float(value))
        del blocker

    def _set_slider_value_blocked(self, slider: QSlider, value: int) -> None:
        blocker = QSignalBlocker(slider)
        slider.setValue(int(value))
        del blocker

    def _apply_visual_style(self, settings: dict[str, Any]) -> None:
        if not isinstance(settings, dict):
            return
        self._applying_visual_style = True
        self.canvas.begin_history_batch()
        try:
            view = settings.get("view") or {}
            if isinstance(view, dict):
                self.canvas.rot_x = float(view.get("rot_x", self.canvas.rot_x))
                self.canvas.rot_y = float(view.get("rot_y", self.canvas.rot_y))
                self.canvas.rot_z = float(view.get("rot_z", self.canvas.rot_z))
                self.canvas.zoom = float(view.get("zoom", self.canvas.zoom))
                self.canvas.pan_x = float(view.get("pan_x", self.canvas.pan_x))
                self.canvas.pan_y = float(view.get("pan_y", self.canvas.pan_y))

            labels = settings.get("labels") or {}
            if isinstance(labels, dict):
                show_symbols = bool(labels.get("show_symbols", self.show_symbols_box.isChecked()))
                show_numbers = bool(labels.get("show_numbers", self.show_numbers_box.isChecked()))
                hide_h = bool(labels.get("hide_hydrogens", self.visual_hide_h_box.isChecked()))
                hide_compass = bool(labels.get("hide_compass", self.hide_compass_box.isChecked()))
                self._set_checked_blocked(self.show_symbols_box, show_symbols)
                self._set_checked_blocked(self.visual_show_symbols_box, show_symbols)
                self._set_checked_blocked(self.show_numbers_box, show_numbers)
                self._set_checked_blocked(self.visual_show_numbers_box, show_numbers)
                self._set_checked_blocked(self.visual_hide_h_box, hide_h)
                self._set_checked_blocked(self.hide_compass_box, hide_compass)
                self._set_checked_blocked(self.visual_hide_compass_box, hide_compass)
                self.canvas.set_show_symbols(show_symbols)
                self.canvas.set_show_numbers(show_numbers)
                self.canvas.set_hide_hydrogens(hide_h)
                self.canvas.set_show_compass(not hide_compass)

            perspective = settings.get("perspective") or {}
            if isinstance(perspective, dict):
                enabled = bool(perspective.get("enabled", False))
                angle = int(perspective.get("angle", 45))
                self._set_checked_blocked(self.perspective_box, enabled)
                self._set_slider_value_blocked(self.perspective_angle_slider, angle)
                self.perspective_angle_value_label.setText(f"{angle}\u00b0")
                self.canvas.set_perspective_enabled(enabled)
                self.canvas.set_perspective_angle(angle)

            cell = settings.get("cell") or {}
            if isinstance(cell, dict):
                color = QColor(str(cell.get("color", "#000000")))
                if not color.isValid():
                    color = QColor("#000000")
                opacity = max(0.05, min(1.0, float(cell.get("opacity", 0.80))))
                repeats = cell.get("repeats", [1, 1, 1])
                if not isinstance(repeats, (list, tuple)) or len(repeats) != 3:
                    repeats = [1, 1, 1]
                try:
                    repeat_x, repeat_y, repeat_z = (int(repeats[0]), int(repeats[1]), int(repeats[2]))
                except (TypeError, ValueError):
                    repeat_x, repeat_y, repeat_z = 1, 1, 1
                self._set_checked_blocked(self.cell_visible_box, bool(cell.get("visible", True)))
                self._set_combo_value_blocked(self.cell_display_combo, str(cell.get("display_mode", "box")))
                self._set_spin_value_blocked(self.cell_repeat_x_spin, repeat_x)
                self._set_spin_value_blocked(self.cell_repeat_y_spin, repeat_y)
                self._set_spin_value_blocked(self.cell_repeat_z_spin, repeat_z)
                self._set_combo_value_blocked(self.cell_line_combo, str(cell.get("line_type", "dash")))
                self._set_spin_value_blocked(self.cell_width_spin, float(cell.get("width", 1.5)))
                transparency = self._cell_transparency_from_opacity(opacity)
                self._set_slider_value_blocked(self.cell_opacity_slider, transparency)
                self.cell_opacity_value_label.setText(f"{transparency}%")
                self.canvas.set_cell_visible(self.cell_visible_box.isChecked())
                self.canvas.set_cell_display_mode(str(self.cell_display_combo.currentData() or "box"))
                self.canvas.set_cell_repeats(self.cell_repeat_x_spin.value(), self.cell_repeat_y_spin.value(), self.cell_repeat_z_spin.value())
                self.canvas.set_cell_color(color)
                self.canvas.set_cell_line_type(str(self.cell_line_combo.currentData() or "dash"))
                self.canvas.set_cell_width(self.cell_width_spin.value())
                self.canvas.set_cell_opacity(opacity)

            atom = settings.get("atom") or {}
            if isinstance(atom, dict):
                atom_shadow_color = QColor(str(atom.get("shadow_color", "#B8B8B8")))
                if not atom_shadow_color.isValid():
                    atom_shadow_color = QColor("#B8B8B8")
                atom_outline_color = QColor(str(atom.get("outline_color", "#1F2937")))
                if not atom_outline_color.isValid():
                    atom_outline_color = QColor("#1F2937")
                radius_mode = str(atom.get("radius_mode", "default"))
                representation_mode = str(atom.get("representation_mode", "ball_stick"))
                self._set_combo_value_blocked(self.atom_radius_mode_combo, radius_mode)
                self._set_combo_value_blocked(
                    self.atom_representation_combo,
                    representation_mode,
                )
                self._set_checked_blocked(self.atom_outline_box, bool(atom.get("outline_enabled", True)))
                self._set_spin_value_blocked(self.atom_outline_width_spin, float(atom.get("outline_width", 0.1)))
                self.canvas.set_atom_style_mode("preset")
                self.canvas.set_atom_radius_mode(str(self.atom_radius_mode_combo.currentData() or "default"))
                self.canvas.set_atom_representation_mode(
                    str(self.atom_representation_combo.currentData() or "ball_stick")
                )
                representation_overrides = atom.get("index_representations", {})
                if isinstance(representation_overrides, dict):
                    by_mode: dict[str, set[int]] = {"ball_stick": set(), "vdw": set()}
                    for raw_index, raw_mode in representation_overrides.items():
                        try:
                            atom_index = int(raw_index)
                        except (TypeError, ValueError):
                            continue
                        mode = "vdw" if str(raw_mode).strip().lower() == "vdw" else "ball_stick"
                        by_mode[mode].add(atom_index)
                    for mode, indices in by_mode.items():
                        if indices:
                            self.canvas.set_atom_index_representation(indices, mode)
                self.canvas.set_atom_shadow_color(atom_shadow_color)
                self.canvas.atom_size_scale = 1.0
                self.canvas.atom_element_colors = self._color_map_from_json(atom.get("element_colors", {}), int_keys=False)
                self.canvas.atom_index_colors = self._color_map_from_json(atom.get("index_colors", {}), int_keys=True)
                self.canvas.atom_element_sizes = self._float_map_from_json(atom.get("element_sizes", {}), int_keys=False)
                self.canvas.atom_index_sizes = self._float_map_from_json(atom.get("index_sizes", {}), int_keys=True)
                self.canvas.refit_scene_scale()
                self.canvas.set_atom_outline_enabled(self.atom_outline_box.isChecked())
                self.canvas.set_atom_outline_color(atom_outline_color)
                self.canvas.set_atom_outline_width(self.atom_outline_width_spin.value())
                self._on_atom_element_changed(select_atoms=False)
                self._on_atom_index_targets_changed()

            bond = settings.get("bond") or {}
            if isinstance(bond, dict):
                bond_custom_color = QColor(str(bond.get("custom_color", "#8A8A8A")))
                if not bond_custom_color.isValid():
                    bond_custom_color = QColor("#8A8A8A")
                bond_outline_color = QColor(str(bond.get("outline_color", "#1F2937")))
                if not bond_outline_color.isValid():
                    bond_outline_color = QColor("#1F2937")
                hbond_color = QColor(str(bond.get("hydrogen_color", "#9CA3AF")))
                if not hbond_color.isValid():
                    hbond_color = QColor("#9CA3AF")
                bond_mode = str(bond.get("mode", "split"))
                self._set_checked_blocked(self.bond_visible_box, bool(bond.get("visible", True)))
                self._set_combo_value_blocked(self.bond_mode_combo, bond_mode)
                self._set_checked_blocked(self.hbond_visible_box, bool(bond.get("hydrogen_visible", False)))
                self._set_spin_value_blocked(self.bond_width_spin, float(bond.get("width", 1.0)))
                self._set_checked_blocked(self.bond_outline_box, bool(bond.get("outline_enabled", True)))
                self._set_spin_value_blocked(self.bond_outline_width_spin, float(bond.get("outline_width", 0.8)))
                self._set_spin_value_blocked(self.hbond_width_spin, float(bond.get("hydrogen_width", 0.3)))
                self.canvas.set_bonds_visible(self.bond_visible_box.isChecked())
                self.canvas.set_bond_color_mode(str(self.bond_mode_combo.currentData() or "split"))
                self.canvas.set_hydrogen_bonds_visible(self.hbond_visible_box.isChecked())
                self.canvas.set_bond_custom_color(bond_custom_color)
                self.canvas.set_bond_width(self.bond_width_spin.value())
                self.canvas.set_bond_outline_enabled(self.bond_outline_box.isChecked())
                self.canvas.set_bond_outline_color(bond_outline_color)
                self.canvas.set_bond_outline_width(self.bond_outline_width_spin.value())
                self.canvas.set_hydrogen_bond_color(hbond_color)
                self.canvas.set_hydrogen_bond_width(self.hbond_width_spin.value())
        finally:
            self._applying_visual_style = False
            self.canvas.end_history_batch(commit=True)
        self.canvas.update()
        self._refresh_visual_color_buttons()

    def reset_cell_style(self) -> None:
        self._apply_visual_style({"cell": self._default_visual_style_snapshot()["cell"]})

    def reset_atom_style(self) -> None:
        self._apply_visual_style({"atom": self._default_visual_style_snapshot()["atom"]})

    def reset_bond_style(self) -> None:
        self._apply_visual_style({"bond": self._default_visual_style_snapshot()["bond"]})

    def _on_visual_style_changed(self) -> None:
        if self._applying_visual_style:
            return
        style_id = self._current_visual_style_id()
        if style_id == DEFAULT_STYLE_ID:
            self._apply_visual_style(self._default_visual_style_snapshot())
            self._set_status("status_style_loaded", tr(self.language, "visual_style_default"))
            return
        style = self._style_by_name(style_id)
        if style:
            self._apply_visual_style(style.get("settings", {}))
            self._set_status("status_style_loaded", style_id)

    def _prompt_visual_style_name(self, title_key: str, current: str = "") -> str:
        name, ok = QInputDialog.getText(self, tr(self.language, title_key), tr(self.language, "style_name"), text=current)
        if not ok:
            return ""
        return str(name or "").strip()[:48]

    def _confirm_replace_visual_style(self, name: str) -> bool:
        reply = QMessageBox.question(
            self,
            tr(self.language, "replace_visual_style_title"),
            tr(self.language, "replace_visual_style_confirm").format(name=name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def save_current_visual_style(self) -> None:
        style_id = self._current_visual_style_id()
        settings = self._capture_visual_style()
        if style_id != DEFAULT_STYLE_ID:
            if not self._confirm_replace_visual_style(style_id):
                return
            style = self._style_by_name(style_id)
            if style:
                style["settings"] = settings
                save_visual_styles(self.visual_styles)
                self._refresh_visual_style_combo(select_name=style_id)
                self._set_status("status_style_saved", style_id)
            return
        name = self._prompt_visual_style_name("save_visual_style")
        if not name:
            return
        existing = self._style_by_name(name)
        if existing:
            if not self._confirm_replace_visual_style(name):
                return
            existing["settings"] = settings
        else:
            if len(self.visual_styles) >= MAX_VISUAL_STYLES - 1:
                QMessageBox.warning(self, tr(self.language, "warning"), tr(self.language, "status_style_limit"))
                return
            self.visual_styles.append({"name": name, "settings": settings})
        save_visual_styles(self.visual_styles)
        self._refresh_visual_style_combo(select_name=name)
        self._set_status("status_style_saved", name)

    def rename_current_visual_style(self) -> None:
        style_id = self._current_visual_style_id()
        if style_id == DEFAULT_STYLE_ID:
            QMessageBox.warning(self, tr(self.language, "warning"), tr(self.language, "cannot_rename_default_style"))
            return
        style = self._style_by_name(style_id)
        if not style:
            return
        name = self._prompt_visual_style_name("rename_visual_style", style_id)
        if not name or name == style_id:
            return
        if self._style_by_name(name):
            QMessageBox.warning(self, tr(self.language, "warning"), tr(self.language, "style_name_exists"))
            return
        style["name"] = name
        save_visual_styles(self.visual_styles)
        self._refresh_visual_style_combo(select_name=name)
        self._set_status("status_style_renamed", name)

    def delete_current_visual_style(self) -> None:
        style_id = self._current_visual_style_id()
        if style_id == DEFAULT_STYLE_ID:
            QMessageBox.warning(self, tr(self.language, "warning"), tr(self.language, "cannot_delete_default_style"))
            return
        style = self._style_by_name(style_id)
        if not style:
            return
        reply = QMessageBox.question(
            self,
            tr(self.language, "delete_visual_style_title"),
            tr(self.language, "delete_visual_style_confirm").format(name=style_id),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.visual_styles = [item for item in self.visual_styles if str(item.get("name", "")).casefold() != style_id.casefold()]
        save_visual_styles(self.visual_styles)
        self._refresh_visual_style_combo(select_name=DEFAULT_STYLE_ID)
        self._apply_visual_style(self._default_visual_style_snapshot())
        self._set_status("status_style_deleted", style_id)

    def apply_language(self) -> None:
        lang = self.language
        self.setWindowTitle(f"{tr(lang, 'title')} {__version__}")
        self.title_label.setText(tr(lang, "title"))
        self.subtitle_label.setText(tr(lang, "subtitle"))
        self.tabs.setTabText(0, tr(lang, "tab_generate"))
        self.tabs.setTabText(1, tr(lang, "tab_visualization"))
        self.tabs.setTabText(2, tr(lang, "tab_settings"))

        self.input_group.setTitle(tr(lang, "group_input"))
        self.batch_group.setTitle(tr(lang, "group_batch"))
        self.slurm_group.setTitle(tr(lang, "group_slurm"))
        self.basic_group.setTitle(tr(lang, "group_basic"))
        self.fixed_group.setTitle(tr(lang, "group_fixed_atoms"))
        self.electronic_group.setTitle(tr(lang, "group_electronic"))
        self.scf_group.setTitle(tr(lang, "group_scf"))
        self.mag_group.setTitle(tr(lang, "group_magnetism"))
        self.visual_style_group.setTitle(tr(lang, "group_display_style"))
        self.visual_view_group.setTitle(tr(lang, "group_visual_view"))
        self.cell_style_group.setTitle(tr(lang, "group_cell_style"))
        self.atom_style_group.setTitle(tr(lang, "group_atom_style"))
        self.bond_style_group.setTitle(tr(lang, "group_bond_style"))
        self.visual_group.setTitle(tr(lang, "group_visualization"))
        self.result_group.setTitle(tr(lang, "group_results"))
        self.settings_group.setTitle(tr(lang, "settings_paths"))

        self.structure_label.setText(tr(lang, "structure_file"))
        self.structure_edit.setPlaceholderText(tr(lang, "structure_drop_placeholder"))
        self.structure_browse_btn.setText(tr(lang, "browse"))
        self.load_original_btn.setText(tr(lang, "load_original_structure"))
        self.convert_load_btn.setText(tr(lang, "convert_and_load_structure"))
        for index, (_value, label) in enumerate(VIEWER_CONVERSION_OPTIONS):
            self._set_combo_item_text(self.convert_format_combo, index, label)
        self.batch_output_label.setText(tr(lang, "batch_output_mode"))
        self.add_batch_btn.setText(tr(lang, "add_batch_files"))
        self.clear_batch_btn.setText(tr(lang, "clear_batch_files"))
        self.batch_hint_label.setText(tr(lang, "batch_hint"))

        self.slurm_enabled_box.setText(tr(lang, "slurm_enabled"))
        self.slurm_template_label.setText(tr(lang, "slurm_template"))
        self.slurm_preset_label.setText(tr(lang, "slurm_preset"))
        self.slurm_nodes_label.setText(tr(lang, "slurm_nodes"))
        self.slurm_cores_label.setText(tr(lang, "slurm_cores"))
        self.slurm_cpn_mode_label.setText(tr(lang, "slurm_cores_per_node_mode"))
        self.slurm_cpn_label.setText(tr(lang, "slurm_cores_per_node"))

        self.project_label.setText(tr(lang, "project"))
        self.task_label.setText(tr(lang, "task"))
        self.model_size_label.setText(tr(lang, "optimizer_preset"))
        self.periodic_label.setText(tr(lang, "periodicity"))

        self.fixed_atoms_label.setText(tr(lang, "fixed_atoms"))
        self.selected_label.setText(tr(lang, "selected_atoms"))
        self.use_selection_btn.setText(tr(lang, "use_selection"))
        self.clear_selection_btn.setText(tr(lang, "clear_selection"))
        self.fixed_hint_label.setText(tr(lang, "fixed_selection_hint"))
        self.freeze_percent_label.setText(tr(lang, "freeze_bottom_z_range"))
        self.exclude_label.setText(tr(lang, "exclude_atom_indices"))
        self.reference_label.setText(tr(lang, "slab_reference"))
        self.reference_browse_btn.setText(tr(lang, "browse"))
        self.reference_clear_btn.setText(tr(lang, "clear_reference"))
        self.preview_btn.setText(tr(lang, "preview_auto_indices"))
        self.fixed_atoms_edit.setPlaceholderText(tr(lang, "fixed_atoms_placeholder"))

        self.functional_label.setText(tr(lang, "functional"))
        self.basis_label.setText(tr(lang, "basis_set"))
        self.dispersion_label.setText(tr(lang, "dispersion"))
        self.charge_label.setText(tr(lang, "charge"))
        self.charge_print_label.setText(tr(lang, "charge_analysis"))
        self.cube_label.setText(tr(lang, "cube_output"))
        self.molden_box.setText(tr(lang, "molden_output"))
        self.add_mos_box.setText(tr(lang, "add_mos_for_pdos"))
        self.added_mos_label.setText(tr(lang, "added_mos"))

        self.scf_method_label.setText(tr(lang, "scf_method"))
        self.scf_accuracy_label.setText(tr(lang, "scf_accuracy"))
        self.mixing_label.setText(tr(lang, "mixing_method"))
        self.kpoints_mode_label.setText(tr(lang, "kpoint_mode"))
        self.kpoints_label.setText(tr(lang, "monkhorst_pack_grid"))
        self.cutoff_label.setText(tr(lang, "cutoff"))
        self.rel_cutoff_label.setText(tr(lang, "rel_cutoff"))
        self.smearing_box.setText(tr(lang, "smearing"))
        self.soft_element_box.setText(tr(lang, "soft_element_strategy"))
        self.temperature_label.setText(tr(lang, "smearing_temperature"))
        self.diag_max_label.setText(tr(lang, "diag_max_scf"))
        self.diag_eps_label.setText(tr(lang, "diag_eps_scf"))
        self.ot_minimizer_label.setText(tr(lang, "ot_minimizer"))
        self.ot_inner_max_label.setText(tr(lang, "inner_max_scf"))
        self.ot_inner_eps_label.setText(tr(lang, "inner_eps_scf"))
        self.ot_outer_max_label.setText(tr(lang, "outer_max_scf"))
        self.ot_outer_eps_label.setText(tr(lang, "outer_eps_scf"))

        self.enable_mag_box.setText(tr(lang, "magnetism"))
        self.enable_dft_u_box.setText(tr(lang, "dft_u"))
        self.mag_rows_label.setText(tr(lang, "initial_magnetization"))
        self.dft_u_rows_label.setText(tr(lang, "dft_u_entries"))

        self.generate_btn.setText(tr(lang, "generate"))
        self.batch_generate_btn.setText(tr(lang, "generate_batch"))
        self.reset_btn.setText(tr(lang, "reset"))

        self.show_symbols_box.setText(tr(lang, "show_symbols"))
        self.show_numbers_box.setText(tr(lang, "show_numbers"))
        self.hide_compass_box.setText(tr(lang, "hide_compass"))
        self.viewer_export_image_btn.setText(tr(lang, "export_image"))
        self.viewer_export_transparent_box.setText(tr(lang, "transparent_background"))
        self.view_a_btn.setText("a")
        self.view_b_btn.setText("b")
        self.view_c_btn.setText("c")
        self.view_a_reverse_btn.setText("a*")
        self.view_b_reverse_btn.setText("b*")
        self.view_c_reverse_btn.setText("c*")
        self.reset_view_btn.setText("◇")
        self.rotate_x_plus_btn.setText("↑")
        self.rotate_x_minus_btn.setText("↓")
        self.rotate_y_minus_btn.setText("←")
        self.rotate_y_plus_btn.setText("→")
        self.rotate_z_minus_btn.setText("↶")
        self.rotate_z_plus_btn.setText("↷")
        self.view_step_label.setText(tr(lang, "view_step"))
        self.view_a_btn.setToolTip(tr(lang, "view_a_tip"))
        self.view_b_btn.setToolTip(tr(lang, "view_b_tip"))
        self.view_c_btn.setToolTip(tr(lang, "view_c_tip"))
        self.view_a_reverse_btn.setToolTip(tr(lang, "view_a_reverse_tip"))
        self.view_b_reverse_btn.setToolTip(tr(lang, "view_b_reverse_tip"))
        self.view_c_reverse_btn.setToolTip(tr(lang, "view_c_reverse_tip"))
        self.reset_view_btn.setToolTip(tr(lang, "reset_view"))
        self.rotate_x_plus_btn.setToolTip(tr(lang, "rotate_x_plus_tip"))
        self.rotate_x_minus_btn.setToolTip(tr(lang, "rotate_x_minus_tip"))
        self.rotate_y_minus_btn.setToolTip(tr(lang, "rotate_y_minus_tip"))
        self.rotate_y_plus_btn.setToolTip(tr(lang, "rotate_y_plus_tip"))
        self.rotate_z_minus_btn.setToolTip(tr(lang, "rotate_z_minus_tip"))
        self.rotate_z_plus_btn.setToolTip(tr(lang, "rotate_z_plus_tip"))
        self.viewer_copy_selection_btn.setText(tr(lang, "copy_selection_short"))
        self.viewer_add_bond_btn.setText(tr(lang, "add_bond_selection_short"))
        self.viewer_remove_bond_btn.setText(tr(lang, "remove_bond_selection_short"))
        self.viewer_undo_btn.setText(tr(lang, "undo_visual_action"))
        self.viewer_redo_btn.setText(tr(lang, "redo_visual_action"))

        self.visual_style_label.setText(tr(lang, "visual_style"))
        self.visual_style_actions_label.setText(tr(lang, "visual_style_actions"))
        self.visual_style_save_btn.setText(tr(lang, "save_visual_style"))
        self.visual_style_rename_btn.setText(tr(lang, "rename_visual_style"))
        self.visual_style_delete_btn.setText(tr(lang, "delete_visual_style"))
        self.visual_export_label.setText(tr(lang, "visual_export_group"))
        self.visual_display_label.setText(tr(lang, "visual_display_group"))
        self.visual_display_extra_label.setText(tr(lang, "visual_display_group"))
        self.visual_quick_view_label.setText(tr(lang, "visual_quick_view_group"))
        self.visual_bookmark_label.setText(tr(lang, "visual_bookmark_group"))
        self.visual_bookmark_extra_label.setText(tr(lang, "visual_bookmark_group"))
        self.visual_selection_label.setText(tr(lang, "visual_selection_group"))
        self.visual_hide_compass_box.setText(tr(lang, "hide_compass"))
        self.visual_show_symbols_box.setText("元素" if lang == "zh" else "Elem.")
        self.visual_show_numbers_box.setText("编号" if lang == "zh" else "No.")
        self.visual_hide_h_box.setText("隐藏H" if lang == "zh" else "Hide H")
        self.visual_reset_view_btn.setText(tr(lang, "reset_view"))
        self.visual_view_a_btn.setText(tr(lang, "view_a"))
        self.visual_view_b_btn.setText(tr(lang, "view_b"))
        self.visual_view_c_btn.setText(tr(lang, "view_c"))
        self.save_view_1_btn.setText(tr(lang, "save_view_1"))
        self.load_view_1_btn.setText(tr(lang, "load_view_1"))
        self.save_view_2_btn.setText(tr(lang, "save_view_2"))
        self.load_view_2_btn.setText(tr(lang, "load_view_2"))
        self.visual_copy_selection_btn.setText(tr(lang, "copy_selection"))
        self.export_image_btn.setText(tr(lang, "export_image"))
        self.export_transparent_box.setText(tr(lang, "transparent_background"))
        self.export_scale_label.setText(tr(lang, "export_scale"))
        self.perspective_box.setText(tr(lang, "perspective_enabled"))
        self.perspective_angle_label.setText(tr(lang, "perspective_angle"))
        self.cell_visible_label.setText(tr(lang, "cell_visible"))
        self.cell_visible_box.setText("")
        self.cell_display_label.setText(tr(lang, "cell_display_mode"))
        self._set_combo_labels(self.cell_display_combo, [
            tr(lang, "cell_display_original"),
            tr(lang, "cell_display_box"),
            tr(lang, "cell_display_box_boundary"),
        ])
        self.cell_repeat_x_label.setText(f"{tr(lang, 'cell_repeats')} X")
        self.cell_repeat_y_label.setText(f"{tr(lang, 'cell_repeats')} Y")
        self.cell_repeat_z_label.setText(f"{tr(lang, 'cell_repeats')} Z")
        self.cell_repeat_blank_label.setText("")
        self.cell_color_label.setText(tr(lang, "cell_color"))
        self.cell_color_btn.setText(tr(lang, "choose_color"))
        self.cell_width_label.setText(tr(lang, "cell_width"))
        self.cell_line_label.setText(tr(lang, "cell_line_type"))
        self.cell_opacity_label.setText(tr(lang, "cell_opacity"))
        self.cell_reset_label.setText(tr(lang, "visual_style_actions"))
        self.cell_reset_btn.setText(tr(lang, "reset_cell_style"))
        line_labels = [
            tr(lang, "line_dash"),
            tr(lang, "line_solid"),
            tr(lang, "line_dot"),
            tr(lang, "line_dash_dot"),
            tr(lang, "line_dash_dot_dot"),
            tr(lang, "line_long_dash"),
            tr(lang, "line_short_dash"),
        ]
        self._set_combo_labels(self.cell_line_combo, line_labels)

        self.atom_target_subhead.setText(tr(lang, "atom_group_target"))
        self.atom_appearance_subhead.setText(tr(lang, "atom_group_appearance"))
        self.atom_number_subhead.setText(tr(lang, "atom_group_numbering"))
        self.atom_radius_mode_label.setText(tr(lang, "atom_radius_mode"))
        self._set_combo_labels(self.atom_radius_mode_combo, [
            tr(lang, "atom_radius_default"),
            tr(lang, "atom_radius_equal"),
            tr(lang, "atom_radius_real"),
        ])
        self.atom_representation_label.setText(tr(lang, "atom_representation"))
        self._set_combo_labels(self.atom_representation_combo, [
            tr(lang, "atom_representation_ball_stick"),
            tr(lang, "atom_representation_vdw"),
        ])
        self.selected_atom_representation_label.setText(tr(lang, "selected_atom_representation"))
        self._set_combo_labels(self.selected_atom_representation_combo, [
            tr(lang, "atom_representation_ball_stick"),
            tr(lang, "atom_representation_vdw"),
        ])
        self.selected_atom_representation_apply_btn.setText(tr(lang, "apply"))
        self.selected_atom_size_label.setText(tr(lang, "selected_atom_size"))
        self.atom_element_label.setText(tr(lang, "atom_element"))
        self.atom_element_size_label.setText(tr(lang, "atom_element_size"))
        self.atom_element_size_spin.setToolTip(tr(lang, "atom_element_size"))
        self.atom_index_label.setText(tr(lang, "atom_index_targets"))
        self.atom_index_edit.setPlaceholderText(tr(lang, "atom_index_placeholder"))
        self.atom_index_size_spin.setToolTip(tr(lang, "atom_index_size"))
        self.atom_element_color_label.setText(tr(lang, "atom_element_color"))
        self.atom_shadow_color_label.setText(tr(lang, "atom_shadow_color"))
        self.atom_outline_label.setText(tr(lang, "atom_outline"))
        self.atom_outline_box.setText("")
        self.atom_outline_color_label.setText(tr(lang, "atom_outline_color"))
        self.atom_outline_width_label.setText(tr(lang, "atom_outline_width"))
        self.atom_index_color_label.setText(tr(lang, "atom_index_color"))
        self.atom_reset_label.setText(tr(lang, "visual_style_actions"))
        self.atom_reset_btn.setText(tr(lang, "reset_atom_style"))

        self.bond_display_subhead.setText(tr(lang, "bond_group_display"))
        self.bond_color_subhead.setText(tr(lang, "bond_group_color"))
        self.bond_width_subhead.setText(tr(lang, "bond_group_width"))
        self.bond_visible_label.setText(tr(lang, "bond_visible"))
        self.bond_visible_box.setText("")
        self.bond_mode_label.setText(tr(lang, "bond_color_mode"))
        self._set_combo_labels(self.bond_mode_combo, [tr(lang, "bond_color_mode_split"), tr(lang, "bond_color_mode_single")])
        self.hbond_visible_label.setText(tr(lang, "show_hydrogen_bonds"))
        self.hbond_visible_box.setText("")
        self.bond_outline_label.setText(tr(lang, "bond_outline"))
        self.bond_outline_box.setText("")
        self.bond_color_label.setText(tr(lang, "bond_color"))
        self.hbond_color_label.setText(tr(lang, "hydrogen_bond_color"))
        self.bond_outline_color_label.setText(tr(lang, "bond_outline_color"))
        self.bond_outline_color_blank_label.setText("")
        self.hbond_width_label.setText(tr(lang, "hydrogen_bond_width"))
        self.hbond_width_spin.setToolTip(tr(lang, "hydrogen_bond_width"))
        self.bond_width_label.setText(tr(lang, "bond_width"))
        self.bond_outline_width_label.setText(tr(lang, "bond_outline_width"))
        self.bond_reset_label.setText(tr(lang, "visual_style_actions"))
        self.bond_reset_btn.setText(tr(lang, "reset_bond_style"))
        self._refresh_visual_style_combo(keep_current=True)
        self._refresh_visual_color_buttons()

        self.multiwfn_label.setText(tr(lang, "multiwfn_path"))
        self.multiwfn_browse_btn.setText(tr(lang, "browse"))
        self.language_label.setText(tr(lang, "language"))
        self.save_settings_btn.setText(tr(lang, "save_settings"))

        self.result_tabs.setTabText(0, tr(lang, "result_summary"))
        self.result_tabs.setTabText(1, tr(lang, "result_patched"))
        self.result_tabs.setTabText(2, tr(lang, "result_diff"))
        self.result_tabs.setTabText(3, tr(lang, "result_raw"))
        self.result_tabs.setTabText(4, tr(lang, "result_commands"))
        self.result_tabs.setTabText(5, tr(lang, "result_log"))
        self.status_label.setText(tr(lang, "status_ready"))

        self._set_combo_item_text(self.language_combo, 0, tr(lang, "language_chinese"))
        self._set_combo_item_text(self.language_combo, 1, tr(lang, "language_english"))
        self._set_combo_labels(self.batch_output_combo, [tr(lang, "batch_output_separate"), tr(lang, "batch_output_source")])
        self._set_task_combo_labels()
        self._set_combo_labels(self.slurm_template_combo, ["Non-SSH local", "SSH CP2K 2026.1"])
        self._set_combo_labels(self.slurm_cpn_mode_combo, [tr(lang, "mode_default"), tr(lang, "mode_custom")])
        self._refresh_preview_box(self.fixed_preview_box.toPlainText() or tr(lang, "manual_indices_preview"))
        self._refresh_batch_list()
        self._viewer_toolbar_mode = ""
        self._reflow_viewer_toolbar()

    def _set_combo_item_text(self, combo: QComboBox, index: int, text: str) -> None:
        if 0 <= index < combo.count():
            combo.setItemText(index, text)

    def _set_combo_labels(self, combo: QComboBox, labels: list[str]) -> None:
        for index, label in enumerate(labels):
            self._set_combo_item_text(combo, index, label)

    def _set_task_combo_labels(self) -> None:
        for index in range(self.task_combo.count()):
            value = str(self.task_combo.itemData(index) or self.task_combo.itemText(index))
            if value == "MD":
                text = "MD (开发中)" if self.language == "zh" else "MD (developing)"
            elif value == "BAND":
                text = "BAND (开发中)" if self.language == "zh" else "BAND (developing)"
            else:
                text = value
            self._set_combo_item_text(self.task_combo, index, text)
        self._mark_combo_values_disabled(self.task_combo, self._disabled_tasks)

    def _bundle_file(self, path: Path) -> dict[str, str]:
        return {
            "name": path.name,
            "path": str(path),
            "content": path.read_text(encoding="utf-8", errors="replace"),
        }

    def _bundle_current_file(self) -> dict[str, str] | None:
        if not self.current_file or not self.current_file.is_file():
            return None
        return {"name": self.current_file.name, "path": str(self.current_file), "content": self.current_content}

    def _load_visual_molecule(self, path: Path, *, convert_format: str | None = None):
        warnings: list[str] = []
        visual_path = path
        if convert_format:
            multiwfn_exe = multiwfn_exe_from_setting(self.multiwfn_edit.text())
            if multiwfn_exe:
                visual_path, conversion_warnings = convert_structure_with_multiwfn(path, multiwfn_exe, convert_format, path.parent)
                warnings.extend(conversion_warnings)
            else:
                raise RuntimeError(tr(self.language, "no_multiwfn"))
        molecule = load_molecule(visual_path)
        molecule.source_path = str(path)
        molecule.visual_source_path = str(visual_path)
        molecule.warnings = warnings + list(molecule.warnings or [])
        return molecule, visual_path

    def _safe_project(self) -> str:
        if self.current_file:
            return self.project_edit.text().strip() or self.current_file.stem
        return self.project_edit.text().strip() or "cp2k_job"

    def _collect_values(self) -> dict[str, Any]:
        values = dict(self.default_values)
        for key, widget in self.value_widgets.items():
            if isinstance(widget, QCheckBox):
                values[key] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                values[key] = widget.currentData() if widget.currentData() is not None else widget.currentText()
            elif isinstance(widget, QPlainTextEdit):
                values[key] = widget.toPlainText().strip()
            elif isinstance(widget, QLineEdit):
                values[key] = widget.text().strip()
        values["project"] = self._safe_project()
        values["molden_print"] = self.molden_box.isChecked()
        values["output_molden"] = self.molden_box.isChecked()
        values["source_path"] = str(self.current_file) if self.current_file else ""
        values["fixed_atoms_mode"] = "MANUAL"
        return values

    def _apply_values(self, values: dict[str, Any]) -> None:
        for key, widget in self.value_widgets.items():
            if key not in values:
                continue
            value = values[key]
            blocker = QSignalBlocker(widget)
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                index = widget.findData(value)
                if index < 0:
                    index = widget.findText(str(value))
                if index >= 0:
                    widget.setCurrentIndex(index)
            elif isinstance(widget, QPlainTextEdit):
                widget.setPlainText("" if value is None else str(value))
            elif isinstance(widget, QLineEdit):
                widget.setText("" if value is None else str(value))
            del blocker
        self._sync_molden_alias()

    def _apply_defaults(self, reset_project: bool = True) -> None:
        self._diag_max_touched = False
        self._apply_values(self.default_values)
        self._apply_task_defaults()
        self._apply_scf_accuracy_preset()
        self._apply_task_scf_defaults(force=True)
        if self.current_file and reset_project:
            self.project_edit.setText(self.current_file.stem)
        self._update_pdos_controls()

    def _apply_task_defaults(self) -> None:
        task = str(self.task_combo.currentData() or self.task_combo.currentText() or "ENERGY").upper()
        if task == "CELL_OPT":
            self._set_combo_value(self.periodic_combo, "XYZ")
            if self.functional_combo.currentText().strip() in {"", "PBE"}:
                self._set_combo_value(self.functional_combo, "PBEsol")
        elif task == "GEO_OPT":
            self._set_combo_value(self.periodic_combo, "XY")

    def _mark_diag_max_touched(self) -> None:
        self._diag_max_touched = True

    def _apply_diag_max_scf_default(self, force: bool = False) -> None:
        current = self.diag_max_edit.text().strip()
        next_value = diag_max_scf_default(str(self.task_combo.currentData() or self.task_combo.currentText()))
        can_replace = current in {"", "1280", "1000", "200"}
        if force or (not self._diag_max_touched and can_replace):
            self.diag_max_edit.setText(next_value)

    def _apply_task_scf_defaults(self, force: bool = False) -> None:
        inner_current = self.ot_inner_max_edit.text().strip()
        if force or inner_current in {"", "128", "25"}:
            self.ot_inner_max_edit.setText("25")
        self._apply_diag_max_scf_default(force=force)

    def _apply_scf_accuracy_preset(self) -> None:
        eps = scf_accuracy_eps(str(self.scf_accuracy_combo.currentData() or self.scf_accuracy_combo.currentText()))
        for widget in (self.diag_eps_edit, self.ot_inner_eps_edit, self.ot_outer_eps_edit):
            widget.setText(eps)

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index < 0:
            index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _sync_molden_alias(self) -> None:
        pass

    def _refresh_preview_box(self, text: str) -> None:
        self.fixed_preview_box.setPlainText(text or "")

    def _clear_results(self) -> None:
        self._set_result_state(None)
        self.output_line.setText("")
        for box in (
            self.summary_text,
            self.patched_text,
            self.diff_text,
            self.raw_text,
            self.commands_text,
            self.backend_log_text,
        ):
            box.setPlainText("")

    def _set_busy(self, busy: bool, mode: str = "") -> None:
        self._busy_mode = mode if busy else ""
        self.generate_btn.setEnabled(not busy)
        self.batch_generate_btn.setEnabled(not busy)
        self.reset_btn.setEnabled(not busy)
        self.preview_btn.setEnabled(not busy)
        self.structure_edit.setEnabled(not busy)
        self.structure_browse_btn.setEnabled(not busy)
        self.load_original_btn.setEnabled(not busy)
        self.convert_format_combo.setEnabled(not busy)
        self.convert_load_btn.setEnabled(not busy)
        self.batch_list.setEnabled(not busy)
        self.add_batch_btn.setEnabled(not busy)
        self.clear_batch_btn.setEnabled(not busy)

    def _summary_with_messages(self, header_lines: list[str], messages: list[dict[str, Any]] | None = None, notes: list[str] | None = None) -> str:
        lines = [line for line in header_lines if line]
        if notes:
            lines.append("")
            lines.append("patch_notes:")
            for note in notes:
                lines.append(f"- {note}")
        if messages:
            lines.append("")
            lines.append("messages:")
            for msg in messages:
                level = str(msg.get("level", "info")).upper()
                text = str(msg.get("text", "")).strip()
                if text:
                    lines.append(f"[{level}] {text}")
        return "\n".join(lines).strip()

    def _set_result_state(self, ok: bool | None, message: str = "") -> None:
        if ok is None:
            self.result_state_label.setText(tr(self.language, "result_status_ready"))
            self.result_state_label.setStyleSheet("color: #176B87; font-weight: bold;")
        elif ok:
            self.result_state_label.setText(tr(self.language, "result_status_success"))
            self.result_state_label.setStyleSheet("color: #15803D; font-weight: bold;")
        else:
            text = tr(self.language, "result_status_error")
            self.result_state_label.setText(f"{text}: {message}" if message else text)
            self.result_state_label.setStyleSheet("color: #B91C1C; font-weight: bold;")

    def _output_dir_text(self, path_text: str) -> str:
        try:
            path = Path(path_text)
            return str(path.parent) if path_text else ""
        except OSError:
            return path_text

    def _format_single_summary(self, data: dict[str, Any]) -> str:
        lines = [
            f"{tr(self.language, 'summary_output_path')}: {data.get('output_path', '')}",
            f"{tr(self.language, 'summary_slurm_path')}: {data.get('slurm_path', '')}" if data.get("slurm_path") else "",
            f"{tr(self.language, 'summary_job_dir')}: {data.get('job_dir', '')}" if data.get("job_dir") else "",
            f"{tr(self.language, 'summary_source_path')}: {data.get('source_path', '')}" if data.get("source_path") else "",
            f"{tr(self.language, 'summary_gjf_path')}: {data.get('gjf_path', '')}" if data.get("gjf_path") else "",
            f"{tr(self.language, 'summary_reference_gjf_path')}: {data.get('reference_gjf_path', '')}" if data.get("reference_gjf_path") else "",
        ]
        selection = data.get("auto_fixed_selection") or {}
        preview = selection.get("preview") or {}
        fixed_string = preview.get("fixed_atom_string") or selection.get("fixed_atom_string") or ""
        if fixed_string:
            lines.append(f"fixed_atoms: {fixed_string}")
        return self._summary_with_messages(lines, data.get("messages"), data.get("patch_notes"))

    def _format_batch_summary(self, data: dict[str, Any]) -> str:
        lines = [
            data.get("summary", ""),
            f"{tr(self.language, 'summary_batch_source_dir')}: {data.get('source_dir', '')}" if data.get("source_dir") else "",
            "",
        ]
        for item in data.get("results", []):
            mark = "OK" if item.get("ok") else "FAILED"
            role = " (template)" if item.get("role") == "template" else ""
            lines.append(f"[{mark}] {item.get('name', '')}{role}")
            if item.get("case_dir"):
                lines.append(f"  folder: {item['case_dir']}")
            if item.get("output_path"):
                lines.append(f"  inp: {item['output_path']}")
            if item.get("slurm_path"):
                lines.append(f"  slurm_path: {item['slurm_path']}")
            if item.get("error"):
                lines.append(f"  error: {item['error']}")
        if data.get("messages"):
            lines.append("")
            lines.append("messages:")
            for msg in data["messages"]:
                lines.append(f"[{str(msg.get('level', 'info')).upper()}] {msg.get('text', '')}")
        return "\n".join(lines).strip()

    def _format_preview_summary(self, data: dict[str, Any]) -> str:
        result = data.get("result") or {}
        preview = result.get("preview") or {}
        lines = [
            f"fixed_atoms: {preview.get('fixed_atom_string', result.get('fixed_atom_string', ''))}",
            f"fixed_atom_count: {preview.get('fixed_atom_count', 0)}",
            f"detected_slab_atom_count: {preview.get('detected_slab_atom_count', 0)}",
            f"{tr(self.language, 'summary_gjf_path')}: {data.get('gjf_path', '')}" if data.get("gjf_path") else "",
            f"{tr(self.language, 'summary_reference_gjf_path')}: {data.get('reference_gjf_path', '')}" if data.get("reference_gjf_path") else "",
        ]
        return self._summary_with_messages(lines, data.get("messages"))

    def _render_single_result(self, data: dict[str, Any]) -> None:
        ok = bool(data.get("ok"))
        self._set_result_state(ok, str(data.get("error", ""))[:400])
        output_dir = self._output_dir_text(str(data.get("output_path", "")))
        self.output_line.setText(f"{tr(self.language, 'summary_output_dir')}: {output_dir}" if output_dir else "")
        self.summary_text.setPlainText(self._format_single_summary(data))
        self.patched_text.setPlainText(str(data.get("patched_input", "")))
        self.diff_text.setPlainText(str(data.get("diff", "")))
        self.raw_text.setPlainText(str(data.get("raw_input", "")))
        self.commands_text.setPlainText(str(data.get("command_script", "")))
        self.backend_log_text.setPlainText(str(data.get("multiwfn_log", "")))
        self.result_tabs.setCurrentIndex(1)

    def _render_batch_result(self, data: dict[str, Any]) -> None:
        summary = self._format_batch_summary(data)
        self._set_result_state(bool(data.get("ok")), str(data.get("error", ""))[:400])
        self.output_line.setText(str(data.get("source_dir", "")))
        self.summary_text.setPlainText(summary)
        self.patched_text.setPlainText(summary)
        self.diff_text.setPlainText("")
        self.raw_text.setPlainText("")
        self.commands_text.setPlainText("")
        self.backend_log_text.setPlainText(summary)
        self.result_tabs.setCurrentIndex(0)

    def _render_preview_result(self, data: dict[str, Any]) -> None:
        result = data.get("result") or {}
        preview = result.get("preview") or {}
        fixed_text = preview.get("fixed_atom_string") or result.get("fixed_atom_string") or ""
        if fixed_text:
            self.fixed_atoms_edit.setText(fixed_text)
            self.canvas.set_frozen_atoms(parse_atom_indices(fixed_text))
        detail_lines = [
            f"fixed_atoms: {fixed_text}",
            f"fixed_atom_count: {preview.get('fixed_atom_count', 0)}",
            f"detected_slab_atom_count: {preview.get('detected_slab_atom_count', 0)}",
            f"range_mode: {preview.get('mode', '')}",
            f"z_min_slab={preview.get('z_min_slab', '')}, z_max_slab={preview.get('z_max_slab', '')}, z_threshold={preview.get('z_threshold', '')}",
        ]
        warnings = list(result.get("warnings") or [])
        errors = list(result.get("errors") or [])
        if preview.get("probable_adsorbate_string"):
            detail_lines.append(f"probable_adsorbates: {preview['probable_adsorbate_string']}")
        if preview.get("manual_excluded_string"):
            detail_lines.append(f"manual_exclusions: {preview['manual_excluded_string']}")
        if preview.get("unmatched_reference_string"):
            detail_lines.append(f"unmatched_reference_atoms: {preview['unmatched_reference_string']}")
        if warnings:
            detail_lines.append("")
            detail_lines.extend(f"warning: {text}" for text in warnings)
        if errors:
            detail_lines.append("")
            detail_lines.extend(f"error: {text}" for text in errors)
        self._refresh_preview_box("\n".join(line for line in detail_lines if line))
        self._set_result_state(bool(data.get("ok")), str(data.get("error", ""))[:400])
        self.output_line.setText(data.get("gjf_path", ""))
        self.summary_text.setPlainText(self._format_preview_summary(data))
        self.patched_text.setPlainText("")
        self.diff_text.setPlainText("")
        self.raw_text.setPlainText("")
        self.commands_text.setPlainText(str(data.get("command_script", "")))
        self.backend_log_text.setPlainText(str(data.get("multiwfn_log", "")))
        self.result_tabs.setCurrentIndex(0)

    def _set_status(self, key: str, suffix: str = "") -> None:
        text = tr(self.language, key)
        self.status_label.setText(f"{text}: {suffix}" if suffix else text)

    def _on_language_changed(self) -> None:
        self.language = normalize_language(self.language_combo.currentData())
        self.apply_language()

    def browse_structure(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr(self.language, "choose_file"),
            "",
            STRUCTURE_FILE_FILTER,
        )
        if path:
            self.load_structure_path(path)

    def load_structure_path(self, path: str) -> None:
        file_path = Path(path)
        self.structure_edit.setText(str(file_path))
        self.current_file = None
        self.current_content = ""
        self.current_molecule = None
        self.canvas.set_molecule([], [], None)
        self._clear_results()
        self.fixed_atoms_edit.clear()
        self.selected_edit.clear()
        if hasattr(self, "atom_index_edit"):
            self.atom_index_edit.clear()
        self._refresh_atom_element_combo()
        self.project_edit.clear()
        if file_path.is_file():
            self._set_status("status_path_ready", file_path.name)
        else:
            self._set_status("status_failed", str(file_path))

    def browse_batch_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr(self.language, "choose_batch_files"),
            str(self.current_file.parent) if self.current_file else "",
            STRUCTURE_FILE_FILTER,
        )
        if paths:
            self._add_batch_paths(paths)

    def _add_batch_paths(self, raw_paths: list[str]) -> None:
        existing = {item["path"].casefold() for item in self.batch_files}
        for path in self._expand_batch_paths(raw_paths):
            key = str(path.resolve()).casefold()
            if key in existing:
                continue
            try:
                self.batch_files.append(self._bundle_file(path))
                existing.add(key)
            except OSError:
                continue
        self._refresh_batch_list()

    def _expand_batch_paths(self, raw_paths: list[str]) -> list[Path]:
        paths: list[Path] = []
        seen: set[str] = set()
        for raw_path in raw_paths:
            path = Path(raw_path)
            candidates: list[Path]
            if path.is_dir():
                candidates = [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in BATCH_STRUCTURE_SUFFIXES]
            elif path.is_file():
                candidates = [path]
            else:
                continue
            for candidate in candidates:
                key = str(candidate.resolve()).casefold()
                if key in seen:
                    continue
                seen.add(key)
                paths.append(candidate)
        return paths

    def _refresh_batch_list(self) -> None:
        self.batch_list.clear()
        for item in self.batch_files:
            row = QListWidgetItem(f"{item['name']}    [{item['path']}]")
            row.setToolTip(item["path"])
            self.batch_list.addItem(row)
        if not self.batch_files:
            self.batch_list.addItem(QListWidgetItem(tr(self.language, "batch_empty")))

    def clear_batch_files(self) -> None:
        self.batch_files = []
        self._refresh_batch_list()

    def browse_reference_structure(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr(self.language, "choose_reference"),
            str(self.current_file.parent) if self.current_file else "",
            STRUCTURE_FILE_FILTER,
        )
        if not path:
            return
        file_path = Path(path)
        self.slab_reference_file = self._bundle_file(file_path)
        self.reference_edit.setText(path)

    def clear_reference_structure(self) -> None:
        self.slab_reference_file = None
        self.reference_edit.clear()
        self._refresh_preview_box(tr(self.language, "reference_empty"))

    def browse_multiwfn(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr(self.language, "choose_multiwfn"),
            normalize_multiwfn_path(self.multiwfn_edit.text()),
            "Multiwfn.exe (Multiwfn.exe);;Executable files (*.exe);;All files (*.*)",
        )
        if path:
            self.multiwfn_edit.setText(normalize_multiwfn_path(path))

    def _current_settings_snapshot(self) -> dict[str, str]:
        multiwfn = normalize_multiwfn_path(self.multiwfn_edit.text()) if hasattr(self, "multiwfn_edit") else normalize_multiwfn_path(self.settings.multiwfn_path)
        return {"multiwfn_path": multiwfn, "language": normalize_language(self.language)}

    def _settings_have_unsaved_changes(self) -> bool:
        return self._current_settings_snapshot() != getattr(self, "_saved_settings_snapshot", {})

    def _persist_settings(self, show_feedback: bool = False) -> Path:
        self.settings = AppSettings(
            multiwfn_path=normalize_multiwfn_path(self.multiwfn_edit.text()),
            language=self.language,
        )
        config_path = save_settings(self.settings)
        self._saved_settings_snapshot = self._current_settings_snapshot()
        if show_feedback:
            self._set_status("status_ready", str(config_path))
            QMessageBox.information(self, tr(self.language, "language"), f"{tr(self.language, 'settings_saved')} {config_path}")
        return config_path

    def save_settings_from_ui(self) -> None:
        self._persist_settings(show_feedback=True)

    def load_original_structure_from_field(self) -> None:
        self.load_structure_from_field(convert_format=None)

    def convert_structure_from_field(self) -> None:
        self.load_structure_from_field(convert_format=str(self.convert_format_combo.currentData() or "gjf"))

    def load_gjf_structure_from_field(self) -> None:
        self.load_structure_from_field(convert_format="gjf")

    def _structure_atom_summary(self, warnings: list[str] | None = None) -> str:
        if not self.current_molecule or not self.current_molecule.atoms:
            return ""
        atoms = self.current_molecule.atoms
        count_text = self._structure_element_count_text()
        selected_text = self._structure_selected_text()
        atom_tokens = [f"{atom.index}:{atom.symbol}" for atom in atoms]
        lines = [
            f"{tr(self.language, 'summary_structure')}: {self.current_file.name if self.current_file else ''}",
            f"{tr(self.language, 'summary_atom_count')}: {len(atoms)}",
            f"{tr(self.language, 'summary_element_counts')}: {count_text}",
            f"{tr(self.language, 'summary_selected_atoms')}: {selected_text}",
            f"{tr(self.language, 'summary_all_atoms')}:",
        ]
        for start in range(0, len(atom_tokens), 18):
            lines.append("  " + "  ".join(atom_tokens[start:start + 18]))
        if warnings:
            lines.append("")
            lines.append(tr(self.language, "summary_warnings") + ":")
            lines.extend(str(item) for item in warnings)
        return "\n".join(lines)

    def _structure_element_count_text(self) -> str:
        if not self.current_molecule or not self.current_molecule.atoms:
            return ""
        counts: dict[str, int] = {}
        for atom in self.current_molecule.atoms:
            counts[atom.symbol] = counts.get(atom.symbol, 0) + 1
        return ", ".join(f"{symbol}:{count}" for symbol, count in sorted(counts.items()))

    def _structure_selected_text(self) -> str:
        selected = sorted(self.canvas.selected_atoms)
        return atoms_to_range_text(selected) if selected else tr(self.language, "summary_no_selected_atoms")

    def _update_structure_summary(self, warnings: list[str] | None = None) -> None:
        text = self._structure_atom_summary(warnings)
        if text:
            atoms = self.current_molecule.atoms if self.current_molecule else []
            structure_name = self.current_file.name if self.current_file else ""
            self.result_state_label.setText(
                f"{tr(self.language, 'summary_structure')}: {structure_name} | "
                f"{tr(self.language, 'summary_atom_count')}: {len(atoms)}"
            )
            self.result_state_label.setStyleSheet("color: #176B87; font-weight: bold;")
            self.output_line.setText(
                f"{tr(self.language, 'summary_element_counts')}: {self._structure_element_count_text()}\n"
                f"{tr(self.language, 'summary_selected_atoms')}: {self._structure_selected_text()}"
            )
            self.summary_text.setPlainText(text)
            self.result_tabs.setCurrentIndex(0)

    def load_structure_from_field(self, *, convert_format: str | None = None) -> None:
        path = Path(self.structure_edit.text().strip().strip('"'))
        if not path.is_file():
            QMessageBox.warning(self, tr(self.language, "warning"), f"File not found:\n{path}")
            return
        try:
            molecule, active_path = self._load_visual_molecule(path, convert_format=convert_format)
            if not molecule.atoms:
                QMessageBox.warning(self, tr(self.language, "warning"), "\n".join(molecule.warnings or []))
                return
            self.current_file = active_path if convert_format else path
            self.current_content = self.current_file.read_text(encoding="utf-8", errors="replace")
            self.current_molecule = molecule
            self.canvas.set_molecule(molecule.atoms, molecule.bonds, molecule.cell_vectors)
            self._refresh_atom_element_combo()
            self.project_edit.setText(path.stem)
            self._apply_feature_presets()
            if convert_format:
                self.structure_edit.setText(str(active_path))
            status_name = f"{path.name} -> {active_path.name}" if convert_format and active_path != path else path.name
            self._set_status("status_converted_loaded" if convert_format else "status_loaded", status_name)
            self._sync_frozen_atoms_from_field()
            self._update_structure_summary(molecule.warnings)
        except Exception as exc:
            QMessageBox.critical(self, tr(self.language, "error"), str(exc))

    def _on_selection_changed(self, indices: list[int]) -> None:
        text = atoms_to_range_text(indices)
        self.selected_edit.setText(text)
        if hasattr(self, "atom_index_edit"):
            blocker = QSignalBlocker(self.atom_index_edit)
            self.atom_index_edit.setText(text)
            del blocker
            self._on_atom_index_targets_changed()
        self._update_structure_summary()

    def use_selection_as_fixed_atoms(self) -> None:
        text = self.selected_edit.text().strip()
        self.fixed_atoms_edit.setText(text)
        self.canvas.set_frozen_atoms(parse_atom_indices(text))

    def clear_fixed_atom_selection(self) -> None:
        self.fixed_atoms_edit.clear()
        self.canvas.set_frozen_atoms(set())

    def clear_selection(self) -> None:
        self.canvas.clear_selection()
        self.selected_edit.clear()
        if hasattr(self, "atom_index_edit"):
            self.atom_index_edit.clear()
        self._update_structure_summary()

    def _validated_multiwfn_setting(self) -> str | None:
        setting = normalize_multiwfn_path(self.multiwfn_edit.text())
        exe = multiwfn_exe_from_setting(setting)
        if not exe:
            QMessageBox.warning(self, tr(self.language, "warning"), tr(self.language, "no_multiwfn"))
            return None
        return setting

    def _start_worker(self, mode: str, payload: dict[str, Any], status_key: str) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, tr(self.language, "warning"), "A backend task is already running.")
            return
        self._set_busy(True, mode)
        self._set_status(status_key)
        self.worker = BackendWorker(mode, payload)
        self.worker.succeeded.connect(self._on_worker_succeeded)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_succeeded(self, mode: str, data: dict[str, Any]) -> None:
        ok = bool(data.get("ok"))
        if mode == "generate":
            if ok:
                self._set_status("status_generated", data.get("output_path", ""))
                self._render_single_result(data)
            else:
                self._set_status("status_failed")
                self._render_single_result(data)
                QMessageBox.critical(self, tr(self.language, "error"), str(data.get("error", ""))[:4000])
        elif mode == "batch":
            if ok:
                self._set_status("status_batch_generated", data.get("source_dir", ""))
            else:
                self._set_status("status_failed")
            self._render_batch_result(data)
            if not ok:
                QMessageBox.warning(self, tr(self.language, "warning"), str(data.get("error") or data.get("summary") or ""))
        elif mode == "preview":
            if ok:
                self._set_status("status_preview_ready", data.get("gjf_path", ""))
            else:
                self._set_status("status_failed")
            self._render_preview_result(data)
            if not ok:
                QMessageBox.warning(self, tr(self.language, "warning"), str(data.get("error", ""))[:4000])

    def _on_worker_failed(self, _mode: str, message: str) -> None:
        self._set_status("status_failed")
        self.summary_text.setPlainText(message)
        self.backend_log_text.setPlainText(message)
        self.result_tabs.setCurrentIndex(5)
        QMessageBox.critical(self, tr(self.language, "error"), message[:4000])

    def _on_worker_finished(self) -> None:
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        self._set_busy(False)
        self._update_task_controls()
        self._update_method_controls()
        self._update_feature_controls()
        self._update_slurm_controls()

    def generate_inp(self) -> None:
        template = self._bundle_current_file()
        if not template:
            QMessageBox.warning(self, tr(self.language, "warning"), tr(self.language, "no_structure"))
            return
        multiwfn_setting = self._validated_multiwfn_setting()
        if not multiwfn_setting:
            return
        self._persist_settings(show_feedback=False)
        values = self._collect_values()
        values["multiwfn_exe"] = multiwfn_setting
        payload = {"file": template, "slab_reference_file": self.slab_reference_file, "values": values}
        self._start_worker("generate", payload, "status_generating")

    def batch_generate_inp(self) -> None:
        template = self._bundle_current_file()
        if not template:
            QMessageBox.warning(self, tr(self.language, "warning"), tr(self.language, "load_template_first"))
            return
        multiwfn_setting = self._validated_multiwfn_setting()
        if not multiwfn_setting:
            return
        self._persist_settings(show_feedback=False)
        values = self._collect_values()
        values["multiwfn_exe"] = multiwfn_setting
        payload = {
            "template_file": template,
            "files": list(self.batch_files),
            "batch_output_mode": str(self.batch_output_combo.currentData() or "separate_folders"),
            "slab_reference_file": self.slab_reference_file,
            "values": values,
        }
        self._start_worker("batch", payload, "status_batch_generating")

    def preview_auto_fixed_atoms(self) -> None:
        template = self._bundle_current_file()
        if not template:
            QMessageBox.warning(self, tr(self.language, "warning"), tr(self.language, "no_structure"))
            return
        multiwfn_setting = self._validated_multiwfn_setting()
        if not multiwfn_setting:
            return
        values = self._collect_values()
        values["multiwfn_exe"] = multiwfn_setting
        payload = {
            "file": template,
            "slab_reference_file": self.slab_reference_file,
            "values": values,
            "percent": self.freeze_percent_edit.text().strip() or values.get("freeze_bottom_z_range_percent", "70"),
            "exclude_indices": self.exclude_edit.text().strip(),
        }
        self._start_worker("preview", payload, "status_previewing")

    def reset_form(self) -> None:
        self._apply_defaults()
        self.clear_batch_files()
        self.clear_reference_structure()
        self._refresh_preview_box(tr(self.language, "manual_indices_preview"))
        self._clear_results()
        self._set_status("status_ready")
        self._update_task_controls()
        self._update_method_controls()
        self._update_feature_controls()
        self._update_slurm_controls()
        self._sync_frozen_atoms_from_field()

    def _set_enabled(self, enabled: bool, *widgets: QWidget) -> None:
        for widget in widgets:
            if widget is not None:
                widget.setEnabled(enabled)

    def _current_elements(self) -> list[str]:
        if not self.current_molecule:
            return []
        seen: set[str] = set()
        elements: list[str] = []
        for atom in self.current_molecule.atoms:
            symbol = str(getattr(atom, "symbol", "")).strip()
            if symbol and symbol not in seen:
                seen.add(symbol)
                elements.append(symbol)
        return elements

    def _preset_rows_for_elements(self, presets: dict[str, str]) -> str:
        return "\n".join(f"{element} {presets[element]}" for element in self._current_elements() if element in presets)

    def _has_magnetic_or_u_presets(self) -> bool:
        elements = set(self._current_elements())
        preset_elements = set(self.magnetic_moment_presets) | set(self.dft_u_presets)
        return bool(elements & (preset_elements | TRANSITION_OR_MAGNETIC_ELEMENTS))

    def _apply_feature_presets(self) -> None:
        if self._has_magnetic_or_u_presets():
            self.mag_group.setChecked(True)
        if self.enable_mag_box.isChecked() and not self.mag_rows_edit.toPlainText().strip():
            rows = self._preset_rows_for_elements(self.magnetic_moment_presets)
            if rows:
                self.mag_rows_edit.setPlainText(rows)
        if self.enable_dft_u_box.isChecked() and not self.dft_u_rows_edit.toPlainText().strip():
            rows = self._preset_rows_for_elements(self.dft_u_presets)
            if rows:
                self.dft_u_rows_edit.setPlainText(rows)

    def _on_magnetism_toggled(self, checked: bool) -> None:
        if checked:
            self._apply_feature_presets()
        else:
            self.mag_rows_edit.clear()
        self._update_feature_controls()

    def _on_dft_u_toggled(self, checked: bool) -> None:
        if checked:
            self._apply_feature_presets()
        else:
            self.dft_u_rows_edit.clear()
        self._update_feature_controls()

    def _on_magnetism_rows_changed(self) -> None:
        if self.enable_mag_box.isChecked() and not self.mag_rows_edit.toPlainText().strip():
            blocker = QSignalBlocker(self.enable_mag_box)
            self.enable_mag_box.setChecked(False)
            del blocker
            self._update_feature_controls()

    def _on_dft_u_rows_changed(self) -> None:
        if self.enable_dft_u_box.isChecked() and not self.dft_u_rows_edit.toPlainText().strip():
            blocker = QSignalBlocker(self.enable_dft_u_box)
            self.enable_dft_u_box.setChecked(False)
            del blocker
            self._update_feature_controls()

    def _sync_frozen_atoms_from_field(self) -> None:
        self.canvas.set_frozen_atoms(parse_atom_indices(self.fixed_atoms_edit.text()))

    def _update_task_controls(self) -> None:
        is_opt = is_optimization_task(str(self.task_combo.currentData() or self.task_combo.currentText()))
        self._set_enabled(is_opt, self.model_size_label, self.model_size_combo)
        self.fixed_group.setEnabled(is_opt)
        self.fixed_group.setChecked(is_opt)
        if not is_opt:
            self.fixed_atoms_edit.clear()
            self.canvas.set_frozen_atoms(set())
        self._refresh_preview_box(tr(self.language, "manual_indices_preview"))
        self._update_fixed_atom_mode()
        self._apply_task_defaults()
        self._apply_task_scf_defaults()

    def _update_fixed_atom_mode(self) -> None:
        is_opt = is_optimization_task(str(self.task_combo.currentData() or self.task_combo.currentText()))
        self.fixed_atoms_edit.setReadOnly(False)
        self.fixed_atoms_edit.setPlaceholderText(tr(self.language, "fixed_atoms_placeholder"))
        self._set_enabled(is_opt, self.fixed_atoms_label, self.fixed_atoms_edit, self.selected_label, self.selected_edit, self.fixed_hint_label)
        self._set_enabled(is_opt, self.use_selection_btn)
        self._set_enabled(is_opt, self.clear_selection_btn)
        for widget in (
            self.freeze_percent_label,
            self.freeze_percent_edit,
            self.exclude_label,
            self.exclude_edit,
            self.reference_label,
            self.reference_edit,
            self.reference_browse_btn,
            self.reference_clear_btn,
            self.preview_btn,
            self.fixed_preview_box,
        ):
            widget.setEnabled(False)
        self._sync_frozen_atoms_from_field()

    def _update_feature_controls(self) -> None:
        self._set_enabled(self.enable_mag_box.isChecked(), self.mag_rows_label, self.mag_rows_edit)
        dft_u_enabled = self.enable_dft_u_box.isChecked()
        self._set_enabled(dft_u_enabled, self.dft_u_rows_label, self.dft_u_rows_edit)

    def _update_pdos_controls(self) -> None:
        is_diag = str(self.scf_method_combo.currentData() or self.scf_method_combo.currentText()) == "DIAG"
        if not is_diag:
            self.add_mos_box.setChecked(False)
        self.add_mos_box.setEnabled(is_diag)
        enabled = is_diag and self.add_mos_box.isChecked()
        if enabled and self.added_mos_edit.text().strip() in {"", "0"}:
            self.added_mos_edit.setText("30")
        self._set_enabled(enabled, self.added_mos_label, self.added_mos_edit)

    def _update_method_controls(self) -> None:
        is_ot = str(self.scf_method_combo.currentData() or self.scf_method_combo.currentText()) == "OT"
        if is_ot:
            self.smearing_box.setChecked(False)
            self._set_combo_value(self.kpoints_mode_combo, "GAMMA")
            self.kpoints_edit.setText("1,1,1")
        gamma_only = str(self.kpoints_mode_combo.currentData() or self.kpoints_mode_combo.currentText()) == "GAMMA"
        if gamma_only:
            self.kpoints_edit.setText("1,1,1")
        self._set_enabled(not is_ot, self.mixing_label, self.mixing_combo, self.kpoints_mode_label, self.kpoints_mode_combo)
        self._set_enabled((not is_ot) and (not gamma_only), self.kpoints_label, self.kpoints_edit)
        self.smearing_box.setEnabled(not is_ot)
        self._set_enabled((not is_ot) and self.smearing_box.isChecked(), self.temperature_label, self.temperature_edit)
        self._set_enabled(not is_ot, self.diag_max_label, self.diag_max_edit, self.diag_eps_label, self.diag_eps_edit)
        self._set_enabled(
            is_ot,
            self.ot_minimizer_label,
            self.ot_minimizer_combo,
            self.ot_inner_max_label,
            self.ot_inner_max_edit,
            self.ot_inner_eps_label,
            self.ot_inner_eps_edit,
            self.ot_outer_max_label,
            self.ot_outer_max_edit,
            self.ot_outer_eps_label,
            self.ot_outer_eps_edit,
        )
        self._update_pdos_controls()

    def _on_task_changed(self) -> None:
        task = str(self.task_combo.currentData() or self.task_combo.currentText() or "ENERGY").upper()
        if task in self._disabled_tasks:
            blocker = QSignalBlocker(self.task_combo)
            self._set_combo_value(self.task_combo, self._last_task_value)
            del blocker
            return
        self._last_task_value = task
        self._update_task_controls()
        self._update_method_controls()

    def _on_slurm_preset_family_changed(self) -> None:
        defaults = self._current_slurm_defaults()
        self.slurm_nodes_edit.setText(defaults["nodes"])
        self.slurm_cores_edit.setText(defaults["cores"])
        self.slurm_cpn_edit.setText(defaults["coresPerNode"])
        self._update_slurm_controls()

    def _on_slurm_resource_changed(self) -> None:
        if str(self.slurm_cpn_mode_combo.currentData() or "default") != "custom":
            self.slurm_cpn_edit.setText(self._current_slurm_cores_per_node())
        self._update_slurm_controls()

    def _current_slurm_defaults(self) -> dict[str, str]:
        template = str(self.slurm_template_combo.currentData() or "local")
        preset = str(self.slurm_preset_combo.currentData() or "general_64_4")
        nodes = self.slurm_nodes_edit.text().strip()
        cores = self.slurm_cores_edit.text().strip()
        per_node = default_cores_per_node(template, preset, nodes, cores)
        if template == "ssh":
            return {"nodes": "1", "cores": "32", "coresPerNode": per_node}
        current = {
            "general_64_4": {"nodes": "4", "cores": "64", "coresPerNode": per_node if preset == "general_64_4" else "16"},
            "small_32_1": {"nodes": "1", "cores": "32", "coresPerNode": per_node if preset == "small_32_1" else "32"},
            "memory_saving": {"nodes": "16", "cores": "128", "coresPerNode": per_node if preset == "memory_saving" else "8"},
        }
        defaults = current.get(preset, current["general_64_4"])
        defaults["coresPerNode"] = default_cores_per_node(template, preset, defaults["nodes"], defaults["cores"])
        return defaults

    def _current_slurm_cores_per_node(self) -> str:
        return default_cores_per_node(
            str(self.slurm_template_combo.currentData() or "local"),
            str(self.slurm_preset_combo.currentData() or "general_64_4"),
            self.slurm_nodes_edit.text().strip(),
            self.slurm_cores_edit.text().strip(),
        )

    def _update_slurm_controls(self) -> None:
        enabled = self.slurm_enabled_box.isChecked()
        template = str(self.slurm_template_combo.currentData() or "local")
        custom_mode = str(self.slurm_cpn_mode_combo.currentData() or "default") == "custom"
        self._set_enabled(
            enabled,
            self.slurm_template_label,
            self.slurm_template_combo,
            self.slurm_nodes_label,
            self.slurm_nodes_edit,
            self.slurm_cores_label,
            self.slurm_cores_edit,
            self.slurm_cpn_mode_label,
            self.slurm_cpn_mode_combo,
        )
        self._set_enabled(
            enabled and template != "ssh",
            self.slurm_preset_label,
            self.slurm_preset_combo,
        )
        self._set_enabled(enabled and custom_mode, self.slurm_cpn_label, self.slurm_cpn_edit)
        if enabled and not custom_mode:
            self.slurm_cpn_edit.setText(self._current_slurm_cores_per_node())

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.warning(
                self,
                tr(self.language, "warning"),
                tr(self.language, "backend_task_running_close"),
            )
            event.ignore()
            return
        if self._settings_have_unsaved_changes():
            reply = QMessageBox.question(
                self,
                tr(self.language, "settings_unsaved_title"),
                tr(self.language, "settings_unsaved_message"),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.Save:
                self._persist_settings(show_feedback=False)
        event.accept()
