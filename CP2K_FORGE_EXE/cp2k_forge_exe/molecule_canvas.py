from __future__ import annotations

import ctypes
import math
import os
import re
from itertools import product

from PyQt5.QtCore import QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QBrush, QRadialGradient, QSurfaceFormat
from PyQt5.QtWidgets import QApplication, QOpenGLWidget, QSizePolicy, QWidget

from .chemistry import ATOM_COLORS, ATOM_RADII, VDW_RADII, Atom, spatial_candidate_pairs


DEFAULT_ROT_X = -72.4
DEFAULT_ROT_Y = -24.4
DEFAULT_ROT_Z = -7.5
SELECTED_ATOM_COLOR = QColor("#FFD400")
FROZEN_ATOM_COLOR = QColor("#D62828")
USE_OPENGL_CANVAS = os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen"
CanvasBase = QOpenGLWidget if USE_OPENGL_CANVAS else QWidget


GL_COLOR_BUFFER_BIT = 0x00004000
GL_PROJECTION = 0x1701
GL_MODELVIEW = 0x1700
GL_POINTS = 0x0000
GL_LINES = 0x0001
GL_BLEND = 0x0BE2
GL_SRC_ALPHA = 0x0302
GL_ONE_MINUS_SRC_ALPHA = 0x0303
GL_POINT_SMOOTH = 0x0B10
GL_LINE_SMOOTH = 0x0B20


class _OpenGLApi:
    def __init__(self) -> None:
        self.lib = ctypes.WinDLL("opengl32")
        self.glClearColor = self.lib.glClearColor
        self.glClearColor.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
        self.glClear = self.lib.glClear
        self.glClear.argtypes = [ctypes.c_uint]
        self.glViewport = self.lib.glViewport
        self.glViewport.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.glMatrixMode = self.lib.glMatrixMode
        self.glMatrixMode.argtypes = [ctypes.c_uint]
        self.glLoadIdentity = self.lib.glLoadIdentity
        self.glOrtho = self.lib.glOrtho
        self.glOrtho.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double]
        self.glEnable = self.lib.glEnable
        self.glEnable.argtypes = [ctypes.c_uint]
        self.glDisable = self.lib.glDisable
        self.glDisable.argtypes = [ctypes.c_uint]
        self.glBlendFunc = self.lib.glBlendFunc
        self.glBlendFunc.argtypes = [ctypes.c_uint, ctypes.c_uint]
        self.glPointSize = self.lib.glPointSize
        self.glPointSize.argtypes = [ctypes.c_float]
        self.glLineWidth = self.lib.glLineWidth
        self.glLineWidth.argtypes = [ctypes.c_float]
        self.glBegin = self.lib.glBegin
        self.glBegin.argtypes = [ctypes.c_uint]
        self.glEnd = self.lib.glEnd
        self.glColor4f = self.lib.glColor4f
        self.glColor4f.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
        self.glVertex2f = self.lib.glVertex2f
        self.glVertex2f.argtypes = [ctypes.c_float, ctypes.c_float]
        self.glFlush = self.lib.glFlush


if USE_OPENGL_CANVAS:
    _canvas_format = QSurfaceFormat()
    _canvas_format.setRenderableType(QSurfaceFormat.OpenGL)
    _canvas_format.setProfile(QSurfaceFormat.CompatibilityProfile)
    _canvas_format.setVersion(2, 1)
    _canvas_format.setSamples(4)
    _canvas_format.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(_canvas_format)


class MoleculeCanvas(CanvasBase):
    selection_changed = pyqtSignal(list)
    atom_clicked = pyqtSignal(int)
    history_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.atoms: list[Atom] = []
        self._atoms_by_index: dict[int, Atom] = {}
        self.bonds: list[tuple[int, int]] = []
        self.cell_vectors: tuple[tuple[float, float, float], ...] | None = None
        self.selected_atoms: set[int] = set()
        self.frozen_atoms: set[int] = set()
        self.show_symbols = False
        self.show_numbers = False
        self.show_compass = True
        self.hide_hydrogens = False
        self.clicked_label_atoms: set[int] = set()
        self.rot_x = DEFAULT_ROT_X
        self.rot_y = DEFAULT_ROT_Y
        self.rot_z = DEFAULT_ROT_Z
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.scale = 80.0
        self._scene_extent = 1.0
        self._center = (0.0, 0.0, 0.0)
        self.perspective_enabled = False
        self.perspective_angle = 45
        self.cell_color = QColor("#000000")
        self.cell_width = 1.5
        self.cell_line_type = "solid"
        self.cell_opacity = 1.0
        self.cell_visible = True
        self.cell_display_mode = "box"
        self.cell_repeats = (1, 1, 1)
        self.cell_boundary_tolerance = 1e-4
        self.atom_style_mode = "preset"
        self.atom_custom_color = QColor("#8E8E8E")
        self.atom_shadow_color = QColor("#B8B8B8")
        self.atom_size_scale = 1.0
        self.atom_radius_mode = "default"
        self.atom_representation_mode = "ball_stick"
        self.atom_index_representations: dict[int, str] = {}
        self.atom_element_colors: dict[str, QColor] = {}
        self.atom_index_colors: dict[int, QColor] = {}
        self.atom_element_sizes: dict[str, float] = {}
        self.atom_index_sizes: dict[int, float] = {}
        self.atom_outline_enabled = True
        self.atom_outline_color = QColor("#1F2937")
        self.atom_outline_width = 0.1
        self.bonds_visible = True
        self.bond_line_type = "solid"
        self.bond_color_mode = "split"
        self.bond_custom_color = QColor("#8A8A8A")
        self.bond_width = 1.0
        self.bond_outline_enabled = True
        self.bond_outline_color = QColor("#1F2937")
        self.bond_outline_width = 0.8
        self.hydrogen_bonds_visible = False
        self.hydrogen_bond_color = QColor("#9CA3AF")
        self.hydrogen_bond_width = 0.3
        self._custom_views: dict[int, tuple[float, float, float, float, float, float]] = {}
        self._projected: list[tuple[int, float, float, float, float]] = []
        self._drag_start = None
        self._drag_last = None
        self._drag_rot = None
        self._drag_pan = None
        self._drag_roll = None
        self._click_pos = None
        self._box_selecting = False
        self._box_start = None
        self._box_current = None
        self._interactive_rendering = False
        self._render_backend = "OpenGL" if USE_OPENGL_CANVAS else "QPainter"
        self._last_render_path = "not-painted"
        self._gl: _OpenGLApi | None = None
        self.use_fast_opengl_while_interacting = True
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._history_limit = 10
        self._history_suspended = 0
        self._history_batch_state: dict | None = None
        self._history_restoring = False
        self._drag_history_recorded = False
        if USE_OPENGL_CANVAS:
            self.setFormat(_canvas_format)
            self.setUpdateBehavior(QOpenGLWidget.PartialUpdate)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(520, 380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def render_backend_name(self) -> str:
        return self._render_backend

    def initializeGL(self) -> None:
        self._render_backend = "OpenGL"

    def resizeGL(self, _width: int, _height: int) -> None:
        return

    def paintGL(self) -> None:
        if self._should_use_fast_opengl():
            try:
                self._last_render_path = "fast-opengl"
                self._paint_scene_fast_opengl()
                return
            except Exception:
                self._last_render_path = "qpaint-fallback-after-fast-error"
                pass
        else:
            self._last_render_path = "qpaint-full"
        self._paint_scene()

    def _color_map_snapshot(self, mapping: dict) -> dict:
        return {str(key): QColor(value).name() for key, value in sorted(mapping.items(), key=lambda item: str(item[0]))}

    def _float_map_snapshot(self, mapping: dict) -> dict:
        return {str(key): float(value) for key, value in sorted(mapping.items(), key=lambda item: str(item[0]))}

    def _snapshot_state(self) -> dict:
        return {
            "bonds": [tuple(bond) for bond in self.bonds],
            "selected_atoms": sorted(self.selected_atoms),
            "clicked_label_atoms": sorted(self.clicked_label_atoms),
            "frozen_atoms": sorted(self.frozen_atoms),
            "view": {
                "rot_x": self.rot_x,
                "rot_y": self.rot_y,
                "rot_z": self.rot_z,
                "zoom": self.zoom,
                "pan_x": self.pan_x,
                "pan_y": self.pan_y,
                "scale": self.scale,
                "center": tuple(self._center),
                "scene_extent": self._scene_extent,
            },
            "labels": {
                "show_symbols": self.show_symbols,
                "show_numbers": self.show_numbers,
                "show_compass": self.show_compass,
                "hide_hydrogens": self.hide_hydrogens,
            },
            "perspective": {"enabled": self.perspective_enabled, "angle": self.perspective_angle},
            "cell": {
                "visible": self.cell_visible,
                "color": QColor(self.cell_color).name(),
                "width": self.cell_width,
                "line_type": self.cell_line_type,
                "opacity": self.cell_opacity,
                "display_mode": self.cell_display_mode,
                "repeats": tuple(self.cell_repeats),
            },
            "atom": {
                "style_mode": self.atom_style_mode,
                "custom_color": QColor(self.atom_custom_color).name(),
                "shadow_color": QColor(self.atom_shadow_color).name(),
                "size_scale": self.atom_size_scale,
                "radius_mode": self.atom_radius_mode,
                "representation_mode": self.atom_representation_mode,
                "index_representations": {
                    str(key): value
                    for key, value in sorted(self.atom_index_representations.items())
                },
                "element_colors": self._color_map_snapshot(self.atom_element_colors),
                "index_colors": self._color_map_snapshot(self.atom_index_colors),
                "element_sizes": self._float_map_snapshot(self.atom_element_sizes),
                "index_sizes": self._float_map_snapshot(self.atom_index_sizes),
                "outline_enabled": self.atom_outline_enabled,
                "outline_color": QColor(self.atom_outline_color).name(),
                "outline_width": self.atom_outline_width,
            },
            "bond": {
                "visible": self.bonds_visible,
                "line_type": self.bond_line_type,
                "color_mode": self.bond_color_mode,
                "custom_color": QColor(self.bond_custom_color).name(),
                "width": self.bond_width,
                "outline_enabled": self.bond_outline_enabled,
                "outline_color": QColor(self.bond_outline_color).name(),
                "outline_width": self.bond_outline_width,
                "hydrogen_visible": self.hydrogen_bonds_visible,
                "hydrogen_color": QColor(self.hydrogen_bond_color).name(),
                "hydrogen_width": self.hydrogen_bond_width,
            },
        }

    def _restore_state(self, state: dict) -> None:
        self._history_restoring = True
        try:
            self.bonds = sorted({self._bond_key(a1, a2) for a1, a2 in state.get("bonds", [])})
            self.selected_atoms = {int(value) for value in state.get("selected_atoms", [])}
            self.clicked_label_atoms = {int(value) for value in state.get("clicked_label_atoms", [])}
            self.frozen_atoms = {int(value) for value in state.get("frozen_atoms", [])}

            view = state.get("view", {})
            self.rot_x = float(view.get("rot_x", self.rot_x))
            self.rot_y = float(view.get("rot_y", self.rot_y))
            self.rot_z = float(view.get("rot_z", self.rot_z))
            self.zoom = float(view.get("zoom", self.zoom))
            self.pan_x = float(view.get("pan_x", self.pan_x))
            self.pan_y = float(view.get("pan_y", self.pan_y))
            self.scale = float(view.get("scale", self.scale))
            center = view.get("center", self._center)
            if isinstance(center, (list, tuple)) and len(center) == 3:
                self._center = (float(center[0]), float(center[1]), float(center[2]))
            self._scene_extent = float(view.get("scene_extent", self._scene_extent))

            labels = state.get("labels", {})
            self.show_symbols = bool(labels.get("show_symbols", self.show_symbols))
            self.show_numbers = bool(labels.get("show_numbers", self.show_numbers))
            self.show_compass = bool(labels.get("show_compass", self.show_compass))
            self.hide_hydrogens = bool(labels.get("hide_hydrogens", self.hide_hydrogens))

            perspective = state.get("perspective", {})
            self.perspective_enabled = bool(perspective.get("enabled", self.perspective_enabled))
            self.perspective_angle = max(20, min(60, int(perspective.get("angle", self.perspective_angle))))

            cell = state.get("cell", {})
            self.cell_visible = bool(cell.get("visible", self.cell_visible))
            self.cell_color = QColor(str(cell.get("color", QColor(self.cell_color).name())))
            self.cell_width = max(0.5, min(12.0, float(cell.get("width", self.cell_width))))
            self.cell_line_type = str(cell.get("line_type", self.cell_line_type))
            self.cell_opacity = max(0.05, min(1.0, float(cell.get("opacity", self.cell_opacity))))
            self.cell_display_mode = str(cell.get("display_mode", self.cell_display_mode))
            repeats = cell.get("repeats", self.cell_repeats)
            if isinstance(repeats, (list, tuple)) and len(repeats) == 3:
                self.cell_repeats = tuple(max(1, min(6, int(value))) for value in repeats)

            atom = state.get("atom", {})
            self.atom_style_mode = str(atom.get("style_mode", self.atom_style_mode))
            self.atom_custom_color = QColor(str(atom.get("custom_color", QColor(self.atom_custom_color).name())))
            self.atom_shadow_color = QColor(str(atom.get("shadow_color", QColor(self.atom_shadow_color).name())))
            self.atom_size_scale = max(0.2, min(3.0, float(atom.get("size_scale", self.atom_size_scale))))
            self.atom_radius_mode = str(atom.get("radius_mode", self.atom_radius_mode))
            self.atom_representation_mode = self._normalize_atom_representation(
                atom.get("representation_mode", self.atom_representation_mode)
            )
            self.atom_index_representations = {
                int(key): self._normalize_atom_representation(value)
                for key, value in dict(atom.get("index_representations", {})).items()
            }
            self.atom_element_colors = {str(key): QColor(str(value)) for key, value in dict(atom.get("element_colors", {})).items()}
            self.atom_index_colors = {int(key): QColor(str(value)) for key, value in dict(atom.get("index_colors", {})).items()}
            self.atom_element_sizes = {str(key): float(value) for key, value in dict(atom.get("element_sizes", {})).items()}
            self.atom_index_sizes = {int(key): float(value) for key, value in dict(atom.get("index_sizes", {})).items()}
            self.atom_outline_enabled = bool(atom.get("outline_enabled", self.atom_outline_enabled))
            self.atom_outline_color = QColor(str(atom.get("outline_color", QColor(self.atom_outline_color).name())))
            self.atom_outline_width = max(0.0, min(10.0, float(atom.get("outline_width", self.atom_outline_width))))

            bond = state.get("bond", {})
            self.bonds_visible = bool(bond.get("visible", self.bonds_visible))
            self.bond_line_type = str(bond.get("line_type", self.bond_line_type))
            self.bond_color_mode = str(bond.get("color_mode", self.bond_color_mode))
            self.bond_custom_color = QColor(str(bond.get("custom_color", QColor(self.bond_custom_color).name())))
            self.bond_width = max(0.0, min(12.0, float(bond.get("width", self.bond_width))))
            self.bond_outline_enabled = bool(bond.get("outline_enabled", self.bond_outline_enabled))
            self.bond_outline_color = QColor(str(bond.get("outline_color", QColor(self.bond_outline_color).name())))
            self.bond_outline_width = max(0.0, min(10.0, float(bond.get("outline_width", self.bond_outline_width))))
            self.hydrogen_bonds_visible = bool(bond.get("hydrogen_visible", self.hydrogen_bonds_visible))
            self.hydrogen_bond_color = QColor(str(bond.get("hydrogen_color", QColor(self.hydrogen_bond_color).name())))
            self.hydrogen_bond_width = max(0.0, min(0.8, float(bond.get("hydrogen_width", self.hydrogen_bond_width))))
        finally:
            self._history_restoring = False
        self.selection_changed.emit(sorted(self.selected_atoms))
        self.update()

    def _record_history(self) -> None:
        if self._history_restoring or self._history_suspended > 0:
            return
        state = self._snapshot_state()
        if self._undo_stack and self._undo_stack[-1] == state:
            return
        self._undo_stack.append(state)
        if len(self._undo_stack) > self._history_limit:
            self._undo_stack = self._undo_stack[-self._history_limit:]
        self._redo_stack.clear()
        self.history_changed.emit()

    def begin_history_batch(self) -> None:
        if self._history_suspended == 0:
            self._history_batch_state = self._snapshot_state()
        self._history_suspended += 1

    def end_history_batch(self, commit: bool = True) -> None:
        if self._history_suspended <= 0:
            return
        self._history_suspended -= 1
        if self._history_suspended == 0:
            state = self._history_batch_state
            self._history_batch_state = None
            if commit and state is not None and state != self._snapshot_state():
                self._undo_stack.append(state)
                if len(self._undo_stack) > self._history_limit:
                    self._undo_stack = self._undo_stack[-self._history_limit:]
                self._redo_stack.clear()
                self.history_changed.emit()

    def clear_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.history_changed.emit()

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        current = self._snapshot_state()
        state = self._undo_stack.pop()
        self._redo_stack.append(current)
        if len(self._redo_stack) > self._history_limit:
            self._redo_stack = self._redo_stack[-self._history_limit:]
        self._restore_state(state)
        self.history_changed.emit()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        current = self._snapshot_state()
        state = self._redo_stack.pop()
        self._undo_stack.append(current)
        if len(self._undo_stack) > self._history_limit:
            self._undo_stack = self._undo_stack[-self._history_limit:]
        self._restore_state(state)
        self.history_changed.emit()
        return True

    def set_molecule(self, atoms: list[Atom], bonds: list[tuple[int, int]], cell_vectors: tuple[tuple[float, float, float], ...] | None = None) -> None:
        self.atoms = list(atoms)
        self._atoms_by_index = {atom.index: atom for atom in self.atoms}
        self.bonds = sorted({self._bond_key(a1, a2) for a1, a2 in bonds if a1 != a2})
        self.cell_vectors = cell_vectors
        self.atom_index_representations.clear()
        self.selected_atoms.clear()
        self.clicked_label_atoms.clear()
        self.frozen_atoms.clear()
        self._projected = []
        self.clear_history()
        if not self.atoms:
            self.update()
            self.selection_changed.emit([])
            return
        self.auto_fit(record_history=False)
        self.selection_changed.emit([])

    def set_frozen_atoms(self, indices: set[int]) -> None:
        values = {int(index) for index in indices if int(index) > 0}
        if values == self.frozen_atoms:
            return
        self._record_history()
        self.frozen_atoms = values
        self.update()

    def set_show_symbols(self, show: bool) -> None:
        value = bool(show)
        if self.show_symbols == value:
            return
        self._record_history()
        self.show_symbols = value
        self.update()

    def set_show_numbers(self, show: bool) -> None:
        value = bool(show)
        if self.show_numbers == value:
            return
        self._record_history()
        self.show_numbers = value
        self.update()

    def set_show_compass(self, show: bool) -> None:
        value = bool(show)
        if self.show_compass == value:
            return
        self._record_history()
        self.show_compass = value
        self.update()

    def set_hide_hydrogens(self, hide: bool) -> None:
        value = bool(hide)
        if self.hide_hydrogens == value:
            return
        self._record_history()
        self.hide_hydrogens = value
        self.update()

    def clear_selection(self) -> None:
        if not self.selected_atoms and not self.clicked_label_atoms:
            return
        self._record_history()
        self.selected_atoms.clear()
        self.clicked_label_atoms.clear()
        self.selection_changed.emit([])
        self.update()

    def set_selected_atoms(self, indices: set[int] | list[int], *, emit: bool = True) -> None:
        values = {int(index) for index in indices if int(index) > 0}
        if values == self.selected_atoms and not self.clicked_label_atoms:
            return
        self._record_history()
        self.selected_atoms = values
        self.clicked_label_atoms.clear()
        if emit:
            self.selection_changed.emit(sorted(self.selected_atoms))
        self.update()

    def select_atoms_by_symbol(self, symbol: str, *, emit: bool = True) -> list[int]:
        key = self._normalized_symbol(symbol)
        values = [atom.index for atom in self.atoms if atom.symbol == key]
        self.set_selected_atoms(values, emit=emit)
        return values

    def auto_fit(self, *, record_history: bool = True) -> None:
        if not self.atoms:
            return
        if record_history:
            self._record_history()
        display_atoms = [atom for atom, _offset in self._display_atom_entries()] or list(self.atoms)
        cx = sum(atom.x for atom in display_atoms) / len(display_atoms)
        cy = sum(atom.y for atom in display_atoms) / len(display_atoms)
        cz = sum(atom.z for atom in display_atoms) / len(display_atoms)
        self._center = (cx, cy, cz)
        max_extent = 0.0
        for atom in display_atoms:
            radius = self._atom_radius_units(atom)
            max_extent = max(
                max_extent,
                abs(atom.x - cx) + radius,
                abs(atom.y - cy) + radius,
                abs(atom.z - cz) + radius,
            )
        for x, y, z in self._cell_points():
            max_extent = max(max_extent, abs(x - cx), abs(y - cy), abs(z - cz))
        self._scene_extent = max(max_extent, 1.0)
        self.rot_x, self.rot_y, self.rot_z = DEFAULT_ROT_X, DEFAULT_ROT_Y, DEFAULT_ROT_Z
        self.zoom = 1.0
        self.pan_x, self.pan_y = 0.0, max(self.height(), 1) * 0.14
        fit_factor = 2.90 if any(self.atom_representation(atom) == "vdw" for atom in display_atoms) else 2.20
        self.scale = min(max(self.width(), 1), max(self.height(), 1)) / (max_extent * fit_factor + 1)
        self.update()

    def refit_scene_scale(self) -> None:
        if not self.atoms:
            self.update()
            return
        display_atoms = [atom for atom, _offset in self._display_atom_entries()] or list(self.atoms)
        cx = sum(atom.x for atom in display_atoms) / len(display_atoms)
        cy = sum(atom.y for atom in display_atoms) / len(display_atoms)
        cz = sum(atom.z for atom in display_atoms) / len(display_atoms)
        self._center = (cx, cy, cz)
        max_extent = 0.0
        for atom in display_atoms:
            radius = self._atom_radius_units(atom)
            max_extent = max(
                max_extent,
                abs(atom.x - cx) + radius,
                abs(atom.y - cy) + radius,
                abs(atom.z - cz) + radius,
            )
        for x, y, z in self._cell_points():
            max_extent = max(max_extent, abs(x - cx), abs(y - cy), abs(z - cz))
        self._scene_extent = max(max_extent, 1.0)
        fit_factor = 2.90 if any(self.atom_representation(atom) == "vdw" for atom in display_atoms) else 2.20
        self.scale = min(max(self.width(), 1), max(self.height(), 1)) / (max_extent * fit_factor + 1)
        self.update()

    def set_perspective_enabled(self, enabled: bool) -> None:
        value = bool(enabled)
        if self.perspective_enabled == value:
            return
        self._record_history()
        self.perspective_enabled = value
        self.update()

    def set_perspective_angle(self, angle: int) -> None:
        value = max(20, min(60, int(angle)))
        if self.perspective_angle == value:
            return
        self._record_history()
        self.perspective_angle = value
        self.update()

    def set_cell_visible(self, visible: bool) -> None:
        value = bool(visible)
        if self.cell_visible == value:
            return
        self._record_history()
        self.cell_visible = value
        self.update()

    def set_cell_color(self, color: QColor) -> None:
        if color.isValid() and QColor(self.cell_color) != color:
            self._record_history()
            self.cell_color = QColor(color)
            self.update()

    def set_cell_width(self, width: float) -> None:
        value = max(0.5, min(12.0, float(width)))
        if abs(self.cell_width - value) < 1e-9:
            return
        self._record_history()
        self.cell_width = value
        self.update()

    def set_cell_line_type(self, line_type: str) -> None:
        value = str(line_type or "dash")
        if self.cell_line_type == value:
            return
        self._record_history()
        self.cell_line_type = value
        self.update()

    def set_cell_opacity(self, opacity: float) -> None:
        value = max(0.05, min(1.0, float(opacity)))
        if abs(self.cell_opacity - value) < 1e-9:
            return
        self._record_history()
        self.cell_opacity = value
        self.update()

    def set_cell_display_mode(self, mode: str) -> None:
        normalized = str(mode or "box").strip().lower()
        if normalized not in {"original", "box", "box_boundary"}:
            normalized = "box"
        if self.cell_display_mode == normalized:
            return
        self._record_history()
        self.cell_display_mode = normalized
        if self.atoms:
            self.auto_fit(record_history=False)
        else:
            self.update()

    def set_cell_repeats(self, nx: int, ny: int, nz: int) -> None:
        repeats = (
            max(1, min(6, int(nx))),
            max(1, min(6, int(ny))),
            max(1, min(6, int(nz))),
        )
        if self.cell_repeats == repeats:
            return
        self._record_history()
        self.cell_repeats = repeats
        if self.atoms:
            self.auto_fit(record_history=False)
        else:
            self.update()

    def save_custom_view(self, slot: int) -> None:
        self._custom_views[int(slot)] = (self.rot_x, self.rot_y, self.rot_z, self.zoom, self.pan_x, self.pan_y)

    def load_custom_view(self, slot: int) -> bool:
        state = self._custom_views.get(int(slot))
        if not state:
            return False
        self._record_history()
        self.rot_x, self.rot_y, self.rot_z, self.zoom, self.pan_x, self.pan_y = state
        self.update()
        return True

    def set_atom_style_mode(self, mode: str) -> None:
        value = "custom" if str(mode).lower() == "custom" else "preset"
        if self.atom_style_mode == value:
            return
        self._record_history()
        self.atom_style_mode = value
        self.update()

    def set_atom_custom_color(self, color: QColor) -> None:
        if color.isValid() and QColor(self.atom_custom_color) != color:
            self._record_history()
            self.atom_custom_color = QColor(color)
            self.update()

    def set_atom_shadow_color(self, color: QColor) -> None:
        if color.isValid() and QColor(self.atom_shadow_color) != color:
            self._record_history()
            self.atom_shadow_color = QColor(color)
            self.update()

    def set_atom_size_scale(self, scale: float) -> None:
        value = max(0.2, min(3.0, float(scale)))
        if abs(self.atom_size_scale - value) < 1e-9:
            return
        self._record_history()
        self.atom_size_scale = value
        self.update()

    def set_atom_radius_mode(self, mode: str) -> None:
        normalized = str(mode or "default").strip().lower()
        if normalized not in {"default", "equal", "real"}:
            normalized = "default"
        if self.atom_radius_mode == normalized:
            return
        self._record_history()
        self.atom_radius_mode = normalized
        self.update()

    @staticmethod
    def _normalize_atom_representation(mode: object) -> str:
        return "vdw" if str(mode or "").strip().lower() == "vdw" else "ball_stick"

    def atom_representation(self, atom_or_index: Atom | int) -> str:
        index = atom_or_index.index if isinstance(atom_or_index, Atom) else int(atom_or_index)
        return self.atom_index_representations.get(index, self.atom_representation_mode)

    def set_atom_representation_mode(self, mode: str) -> None:
        normalized = self._normalize_atom_representation(mode)
        if self.atom_representation_mode == normalized and not self.atom_index_representations:
            return
        self._record_history()
        self.atom_representation_mode = normalized
        self.atom_index_representations.clear()
        self.refit_scene_scale()

    def set_atom_index_representation(self, indices: set[int] | list[int], mode: str) -> int:
        values = {
            int(index)
            for index in indices
            if int(index) > 0 and (not self._atoms_by_index or int(index) in self._atoms_by_index)
        }
        if not values:
            return 0
        normalized = self._normalize_atom_representation(mode)
        old_state = self._snapshot_state()
        for index in values:
            if normalized == self.atom_representation_mode:
                self.atom_index_representations.pop(index, None)
            else:
                self.atom_index_representations[index] = normalized
        if old_state == self._snapshot_state():
            return 0
        if not self._history_restoring and self._history_suspended <= 0:
            self._undo_stack.append(old_state)
            if len(self._undo_stack) > self._history_limit:
                self._undo_stack = self._undo_stack[-self._history_limit:]
            self._redo_stack.clear()
            self.history_changed.emit()
        self.refit_scene_scale()
        return len(values)

    def set_atom_outline_enabled(self, enabled: bool) -> None:
        value = bool(enabled)
        if self.atom_outline_enabled == value:
            return
        self._record_history()
        self.atom_outline_enabled = value
        self.update()

    def set_atom_outline_color(self, color: QColor) -> None:
        if color.isValid() and QColor(self.atom_outline_color) != color:
            self._record_history()
            self.atom_outline_color = QColor(color)
            self.update()

    def set_atom_outline_width(self, width: float) -> None:
        value = max(0.0, min(10.0, float(width)))
        if abs(self.atom_outline_width - value) < 1e-9:
            return
        self._record_history()
        self.atom_outline_width = value
        self.update()

    def set_atom_element_color_rules(self, text: str) -> None:
        colors = self._parse_element_color_rules(text)
        if self._color_map_snapshot(self.atom_element_colors) == self._color_map_snapshot(colors):
            return
        self._record_history()
        self.atom_element_colors = colors
        self.update()

    def set_atom_index_color_rules(self, text: str) -> None:
        colors = self._parse_index_color_rules(text)
        if self._color_map_snapshot(self.atom_index_colors) == self._color_map_snapshot(colors):
            return
        self._record_history()
        self.atom_index_colors = colors
        self.update()

    def set_atom_element_style(self, symbol: str, color: QColor | None = None, size: float | None = None) -> None:
        key = self._normalized_symbol(symbol)
        if not key:
            return
        old_state = self._snapshot_state()
        if color is not None and color.isValid():
            self.atom_element_colors[key] = QColor(color)
        if size is not None:
            self.atom_element_sizes[key] = max(0.2, min(3.0, float(size)))
        if old_state != self._snapshot_state():
            if not self._history_restoring and self._history_suspended <= 0:
                self._undo_stack.append(old_state)
                if len(self._undo_stack) > self._history_limit:
                    self._undo_stack = self._undo_stack[-self._history_limit:]
                self._redo_stack.clear()
                self.history_changed.emit()
        self.update()

    def set_atom_index_style(self, indices: set[int] | list[int], color: QColor | None = None, size: float | None = None) -> None:
        values = {int(index) for index in indices if int(index) > 0}
        if not values:
            return
        old_state = self._snapshot_state()
        for index in values:
            if color is not None and color.isValid():
                self.atom_index_colors[index] = QColor(color)
            if size is not None:
                self.atom_index_sizes[index] = max(0.2, min(3.0, float(size)))
        if old_state != self._snapshot_state():
            if not self._history_restoring and self._history_suspended <= 0:
                self._undo_stack.append(old_state)
                if len(self._undo_stack) > self._history_limit:
                    self._undo_stack = self._undo_stack[-self._history_limit:]
                self._redo_stack.clear()
                self.history_changed.emit()
        self.update()

    def set_bonds_visible(self, visible: bool) -> None:
        value = bool(visible)
        if self.bonds_visible == value:
            return
        self._record_history()
        self.bonds_visible = value
        self.update()

    def set_bond_line_type(self, line_type: str) -> None:
        value = str(line_type or "solid")
        if self.bond_line_type == value:
            return
        self._record_history()
        self.bond_line_type = value
        self.update()

    def set_bond_color_mode(self, mode: str) -> None:
        normalized = str(mode or "split").strip().lower()
        value = "single" if normalized == "single" else "split"
        if self.bond_color_mode == value:
            return
        self._record_history()
        self.bond_color_mode = value
        self.update()

    def set_bond_custom_color(self, color: QColor) -> None:
        if color.isValid() and QColor(self.bond_custom_color) != color:
            self._record_history()
            self.bond_custom_color = QColor(color)
            self.update()

    def set_bond_width(self, width: float) -> None:
        value = max(0.0, min(12.0, float(width)))
        if abs(self.bond_width - value) < 1e-9:
            return
        self._record_history()
        self.bond_width = value
        self.update()

    def set_bond_outline_enabled(self, enabled: bool) -> None:
        value = bool(enabled)
        if self.bond_outline_enabled == value:
            return
        self._record_history()
        self.bond_outline_enabled = value
        self.update()

    def set_bond_outline_color(self, color: QColor) -> None:
        if color.isValid() and QColor(self.bond_outline_color) != color:
            self._record_history()
            self.bond_outline_color = QColor(color)
            self.update()

    def set_bond_outline_width(self, width: float) -> None:
        value = max(0.0, min(10.0, float(width)))
        if abs(self.bond_outline_width - value) < 1e-9:
            return
        self._record_history()
        self.bond_outline_width = value
        self.update()

    def set_hydrogen_bonds_visible(self, visible: bool) -> None:
        value = bool(visible)
        if self.hydrogen_bonds_visible == value:
            return
        self._record_history()
        self.hydrogen_bonds_visible = value
        self.update()

    def set_hydrogen_bond_color(self, color: QColor) -> None:
        if color.isValid() and QColor(self.hydrogen_bond_color) != color:
            self._record_history()
            self.hydrogen_bond_color = QColor(color)
            self.update()

    def set_hydrogen_bond_width(self, width: float) -> None:
        value = max(0.0, min(0.8, float(width)))
        if abs(self.hydrogen_bond_width - value) < 1e-9:
            return
        self._record_history()
        self.hydrogen_bond_width = value
        self.update()

    @staticmethod
    def _bond_key(a1: int, a2: int) -> tuple[int, int]:
        left, right = int(a1), int(a2)
        return (left, right) if left < right else (right, left)

    def add_bonds_for_selection(self) -> int:
        selected = sorted(self.selected_atoms)
        if len(selected) < 2:
            return 0
        current = set(self.bonds)
        candidates: list[tuple[int, int]] = []
        if len(selected) == 2:
            candidates = [self._bond_key(selected[0], selected[1])]
        else:
            atoms = {atom.index: atom for atom in self.atoms}
            for i, left in enumerate(selected):
                atom1 = atoms.get(left)
                if not atom1:
                    continue
                for right in selected[i + 1:]:
                    atom2 = atoms.get(right)
                    if not atom2:
                        continue
                    cutoff = min(3.0, max(0.9, (ATOM_RADII.get(atom1.symbol, 0.8) + ATOM_RADII.get(atom2.symbol, 0.8)) * 1.25 + 0.25))
                    distance = math.dist((atom1.x, atom1.y, atom1.z), (atom2.x, atom2.y, atom2.z))
                    if distance <= cutoff:
                        candidates.append(self._bond_key(left, right))
        added = 0
        for bond in candidates:
            if bond not in current and bond[0] != bond[1]:
                current.add(bond)
                added += 1
        if added:
            self._record_history()
            self.bonds = sorted(current)
            self.update()
        return added

    def remove_bonds_for_selection(self) -> int:
        selected = set(self.selected_atoms)
        if len(selected) < 2:
            return 0
        before = len(self.bonds)
        old_state = self._snapshot_state()
        next_bonds = [bond for bond in self.bonds if not (bond[0] in selected and bond[1] in selected)]
        self.bonds = next_bonds
        removed = before - len(self.bonds)
        if removed:
            if not self._history_restoring and self._history_suspended <= 0:
                self._undo_stack.append(old_state)
                if len(self._undo_stack) > self._history_limit:
                    self._undo_stack = self._undo_stack[-self._history_limit:]
                self._redo_stack.clear()
                self.history_changed.emit()
            self.update()
        return removed

    def set_view_axis(self, axis: str) -> None:
        vectors = self.cell_vectors or ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        axis_name = str(axis).upper()
        index = {"A": 1, "B": 0, "C": 2}.get(axis_name, 2)
        self.set_view_along_vector(vectors[index], keep_z_up=(axis_name == "A"))

    def set_reverse_view_axis(self, axis: str) -> None:
        vectors = self.cell_vectors or ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        axis_name = str(axis).upper()
        index = {"A": 1, "B": 0, "C": 2}.get(axis_name, 2)
        x, y, z = vectors[index]
        self.set_view_along_vector((-x, -y, -z), keep_z_up=(axis_name == "A"))

    def set_view_along_vector(self, vector: tuple[float, float, float], *, keep_z_up: bool = False) -> None:
        self._record_history()
        x, y, z = vector
        yz_len = math.hypot(y, z)
        self.rot_x = math.degrees(math.atan2(y, z if abs(z) > 1e-12 else 0.0))
        self.rot_y = math.degrees(math.atan2(-x, yz_len))
        self.rot_z = 0.0
        if keep_z_up:
            self._roll_to_keep_screen_z_up()
        self.pan_x, self.pan_y = 0.0, 0.0
        self.update()

    def rotate_view(self, axis: str, degrees: float) -> None:
        self._record_history()
        axis_name = str(axis or "").lower()
        if axis_name == "x":
            delta = self._axis_rotation_matrix("x", math.radians(degrees))
        elif axis_name == "y":
            delta = self._axis_rotation_matrix("y", math.radians(degrees))
        else:
            delta = self._axis_rotation_matrix("z", math.radians(degrees))
        self._set_rotation_matrix(self._matrix_multiply(delta, self._rotation_matrix()))
        self.update()

    def _roll_to_keep_screen_z_up(self) -> None:
        rx, ry, _rz = self._rotate(0.0, 0.0, 1.0)
        angle = math.degrees(math.atan2(-ry, rx))
        self.rot_z -= angle + 90.0

    @staticmethod
    def _axis_rotation_matrix(axis: str, angle: float) -> list[list[float]]:
        c, s = math.cos(angle), math.sin(angle)
        if axis == "x":
            return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]
        if axis == "y":
            return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]
        return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]

    @staticmethod
    def _matrix_multiply(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
        return [
            [sum(a[row][k] * b[k][col] for k in range(3)) for col in range(3)]
            for row in range(3)
        ]

    def _rotation_matrix(self) -> list[list[float]]:
        return self._matrix_multiply(
            self._axis_rotation_matrix("z", math.radians(self.rot_z)),
            self._matrix_multiply(
                self._axis_rotation_matrix("y", math.radians(self.rot_y)),
                self._axis_rotation_matrix("x", math.radians(self.rot_x)),
            ),
        )

    def _set_rotation_matrix(self, matrix: list[list[float]]) -> None:
        m00, _m01, _m02 = matrix[0]
        m10, _m11, _m12 = matrix[1]
        m20, m21, m22 = matrix[2]
        ry = math.asin(max(-1.0, min(1.0, -m20)))
        cy = math.cos(ry)
        if abs(cy) > 1e-8:
            rx = math.atan2(m21, m22)
            rz = math.atan2(m10, m00)
        else:
            rx = 0.0
            rz = math.atan2(-matrix[0][1], matrix[1][1])
        self.rot_x = math.degrees(rx)
        self.rot_y = math.degrees(ry)
        self.rot_z = math.degrees(rz)

    def _rotate_by_screen_drag(self, dx: float, dy: float) -> None:
        distance = math.hypot(dx, dy)
        if distance < 0.01:
            return
        limited_distance = min(distance, 46.0)
        scale = limited_distance / distance
        dx *= scale
        dy *= scale
        angle = min(math.radians(9.0), math.radians(limited_distance * 0.24))
        if angle <= 0:
            return
        axis_x = dy / limited_distance
        axis_y = dx / limited_distance
        axis_z = 0.0
        delta = self._arbitrary_axis_rotation_matrix(axis_x, axis_y, axis_z, angle)
        self._set_rotation_matrix(self._matrix_multiply(delta, self._rotation_matrix()))

    @staticmethod
    def _arbitrary_axis_rotation_matrix(x: float, y: float, z: float, angle: float) -> list[list[float]]:
        norm = math.sqrt(x * x + y * y + z * z)
        if norm <= 1e-12:
            return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        x, y, z = x / norm, y / norm, z / norm
        c, s = math.cos(angle), math.sin(angle)
        t = 1.0 - c
        return [
            [t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
        ]

    @staticmethod
    def _normalized_symbol(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return text[0].upper() + text[1:].lower()

    @staticmethod
    def _valid_color(value: str) -> QColor | None:
        color = QColor(str(value or "").strip())
        return color if color.isValid() else None

    @classmethod
    def _parse_element_color_rules(cls, text: str) -> dict[str, QColor]:
        rules: dict[str, QColor] = {}
        for chunk in re.split(r"[;\n]+", str(text or "")):
            parts = chunk.replace("=", " ").replace(":", " ").split()
            if len(parts) < 2:
                continue
            symbol = cls._normalized_symbol(parts[0])
            color = cls._valid_color(parts[1])
            if symbol and color:
                rules[symbol] = color
        return rules

    @staticmethod
    def _expand_index_token(token: str) -> set[int]:
        values: set[int] = set()
        for part in re.split(r"[,，\s]+", str(token or "")):
            if not part:
                continue
            if "-" in part:
                left, right = part.split("-", 1)
                try:
                    a, b = int(left), int(right)
                except ValueError:
                    continue
                if a > b:
                    a, b = b, a
                values.update(range(max(a, 1), b + 1))
            else:
                try:
                    value = int(part)
                except ValueError:
                    continue
                if value > 0:
                    values.add(value)
        return values

    @classmethod
    def _parse_index_color_rules(cls, text: str) -> dict[int, QColor]:
        rules: dict[int, QColor] = {}
        for chunk in re.split(r"[;\n]+", str(text or "")):
            parts = chunk.replace("=", " ").replace(":", " ").split()
            if len(parts) < 2:
                continue
            color = cls._valid_color(parts[-1])
            if not color:
                continue
            for atom_index in cls._expand_index_token(" ".join(parts[:-1])):
                rules[atom_index] = color
        return rules

    def _rotate(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        rx = math.radians(self.rot_x)
        y1 = y * math.cos(rx) - z * math.sin(rx)
        z1 = y * math.sin(rx) + z * math.cos(rx)
        ry = math.radians(self.rot_y)
        x1 = x * math.cos(ry) + z1 * math.sin(ry)
        z2 = -x * math.sin(ry) + z1 * math.cos(ry)
        rz = math.radians(self.rot_z)
        x2 = x1 * math.cos(rz) - y1 * math.sin(rz)
        y2 = x1 * math.sin(rz) + y1 * math.cos(rz)
        return x2, y2, z2

    @staticmethod
    def _vector_add(*vectors: tuple[float, float, float]) -> tuple[float, float, float]:
        return (
            sum(vector[0] for vector in vectors),
            sum(vector[1] for vector in vectors),
            sum(vector[2] for vector in vectors),
        )

    @staticmethod
    def _vector_scale(vector: tuple[float, float, float], factor: float) -> tuple[float, float, float]:
        return vector[0] * factor, vector[1] * factor, vector[2] * factor

    def _cell_inverse(self) -> tuple[tuple[float, float, float], ...] | None:
        if not self.cell_vectors:
            return None
        a, b, c = self.cell_vectors
        det = (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - b[0] * (a[1] * c[2] - a[2] * c[1])
            + c[0] * (a[1] * b[2] - a[2] * b[1])
        )
        if abs(det) < 1e-8:
            return None
        return (
            (
                (b[1] * c[2] - b[2] * c[1]) / det,
                (b[2] * c[0] - b[0] * c[2]) / det,
                (b[0] * c[1] - b[1] * c[0]) / det,
            ),
            (
                (c[1] * a[2] - c[2] * a[1]) / det,
                (c[2] * a[0] - c[0] * a[2]) / det,
                (c[0] * a[1] - c[1] * a[0]) / det,
            ),
            (
                (a[1] * b[2] - a[2] * b[1]) / det,
                (a[2] * b[0] - a[0] * b[2]) / det,
                (a[0] * b[1] - a[1] * b[0]) / det,
            ),
        )

    def _cart_to_fractional(self, point: tuple[float, float, float]) -> tuple[float, float, float] | None:
        inv = self._cell_inverse()
        if inv is None:
            return None
        x, y, z = point
        return (
            inv[0][0] * x + inv[0][1] * y + inv[0][2] * z,
            inv[1][0] * x + inv[1][1] * y + inv[1][2] * z,
            inv[2][0] * x + inv[2][1] * y + inv[2][2] * z,
        )

    def _fractional_to_cart(self, frac: tuple[float, float, float]) -> tuple[float, float, float]:
        if not self.cell_vectors:
            return (0.0, 0.0, 0.0)
        a, b, c = self.cell_vectors
        return (
            frac[0] * a[0] + frac[1] * b[0] + frac[2] * c[0],
            frac[0] * a[1] + frac[1] * b[1] + frac[2] * c[1],
            frac[0] * a[2] + frac[1] * b[2] + frac[2] * c[2],
        )

    def _cell_offset_vector(self, offset: tuple[int, int, int]) -> tuple[float, float, float]:
        if not self.cell_vectors:
            return (0.0, 0.0, 0.0)
        a, b, c = self.cell_vectors
        return self._vector_add(
            self._vector_scale(a, offset[0]),
            self._vector_scale(b, offset[1]),
            self._vector_scale(c, offset[2]),
        )

    def _display_atom_entries(self) -> list[tuple[Atom, tuple[int, int, int]]]:
        if not self.atoms:
            return []
        nx, ny, nz = self.cell_repeats
        if not self.cell_vectors:
            return [(atom, (0, 0, 0)) for atom in self.atoms]

        entries: list[tuple[Atom, tuple[int, int, int]]] = []
        seen: set[tuple[int, tuple[int, int, int]]] = set()
        repeat_offsets = list(product(range(nx), range(ny), range(nz)))
        wrap = self.cell_display_mode in {"box", "box_boundary"}
        duplicate_boundary = self.cell_display_mode == "box_boundary"
        tol = self.cell_boundary_tolerance

        for atom in self.atoms:
            base = (atom.x, atom.y, atom.z)
            boundary_offsets = [(0, 0, 0)]
            if wrap:
                frac = self._cart_to_fractional(base)
                if frac is None:
                    base_frac = None
                    base = (atom.x, atom.y, atom.z)
                else:
                    wrapped = tuple(value - math.floor(value) for value in frac)
                    base_frac = wrapped
                    base = self._fractional_to_cart(wrapped)
                if duplicate_boundary and base_frac is not None:
                    per_axis = [[0], [0], [0]]
                    for axis, value in enumerate(base_frac):
                        if abs(value) <= tol:
                            per_axis[axis].append(1)
                        elif abs(value - 1.0) <= tol:
                            per_axis[axis].append(-1)
                    boundary_offsets = list(product(per_axis[0], per_axis[1], per_axis[2]))

            for repeat_offset in repeat_offsets:
                for boundary_offset in boundary_offsets:
                    offset = (
                        int(repeat_offset[0] + boundary_offset[0]),
                        int(repeat_offset[1] + boundary_offset[1]),
                        int(repeat_offset[2] + boundary_offset[2]),
                    )
                    key = (atom.index, offset)
                    if key in seen:
                        continue
                    seen.add(key)
                    dx, dy, dz = self._cell_offset_vector(offset)
                    entries.append((
                        Atom(atom.index, atom.symbol, atom.atomic_number, base[0] + dx, base[1] + dy, base[2] + dz),
                        offset,
                    ))
        return entries

    def _project(self, atom: Atom) -> tuple[float, float, float]:
        return self._project_point(atom.x, atom.y, atom.z)

    def _perspective_factor(self, z_value: float) -> float:
        if not self.perspective_enabled:
            return 1.0
        half_fov = math.radians(max(20, min(60, self.perspective_angle))) / 2.0
        default_half_fov = math.radians(45.0) / 2.0
        scene_radius = max(self._scene_extent, 1.0)
        camera_distance = max(8.0, scene_radius * 3.2)
        camera_depth = camera_distance - z_value
        near_depth = max(0.35, camera_distance - scene_radius * 1.35)
        camera_depth = max(near_depth, camera_depth)
        focal = 1.0 / max(0.1, math.tan(half_fov))
        default_focal = 1.0 / math.tan(default_half_fov)
        factor = (camera_distance / camera_depth) * (focal / default_focal)
        return max(0.18, min(5.0, factor))

    def _project_point(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        cx, cy, cz = self._center
        px, py, pz = self._rotate(x - cx, y - cy, z - cz)
        s = self.scale * self.zoom
        perspective = self._perspective_factor(pz)
        return self.width() / 2 + px * s * perspective + self.pan_x, self.height() / 2 - py * s * perspective + self.pan_y, pz

    def _cell_points(self) -> list[tuple[float, float, float]]:
        if not self.cell_vectors:
            return []
        a, b, c = self.cell_vectors
        origin = self._cell_origin()
        nx, ny, nz = self.cell_repeats
        a_max = self._vector_scale(a, nx)
        b_max = self._vector_scale(b, ny)
        c_max = self._vector_scale(c, nz)
        return [
            origin,
            self._vector_add(origin, a_max),
            self._vector_add(origin, b_max),
            self._vector_add(origin, c_max),
            self._vector_add(origin, a_max, b_max),
            self._vector_add(origin, a_max, c_max),
            self._vector_add(origin, b_max, c_max),
            self._vector_add(origin, a_max, b_max, c_max),
        ]

    def _cell_edges(self) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
        if not self.cell_vectors:
            return []
        a, b, c = self.cell_vectors
        origin = self._cell_origin()
        nx, ny, nz = self.cell_repeats
        edges = []
        for j in range(ny + 1):
            for k in range(nz + 1):
                start = self._vector_add(origin, self._vector_scale(b, j), self._vector_scale(c, k))
                edges.append((start, self._vector_add(start, self._vector_scale(a, nx))))
        for i in range(nx + 1):
            for k in range(nz + 1):
                start = self._vector_add(origin, self._vector_scale(a, i), self._vector_scale(c, k))
                edges.append((start, self._vector_add(start, self._vector_scale(b, ny))))
        for i in range(nx + 1):
            for j in range(ny + 1):
                start = self._vector_add(origin, self._vector_scale(a, i), self._vector_scale(b, j))
                edges.append((start, self._vector_add(start, self._vector_scale(c, nz))))
        return edges

    def _cell_origin(self) -> tuple[float, float, float]:
        if not self.cell_vectors:
            return (0.0, 0.0, 0.0)
        a, b, c = self.cell_vectors
        nx, ny, nz = self.cell_repeats
        cx, cy, cz = self._center
        target = (
            cx - 0.5 * (nx * a[0] + ny * b[0] + nz * c[0]),
            cy - 0.5 * (nx * a[1] + ny * b[1] + nz * c[1]),
            cz - 0.5 * (nx * a[2] + ny * b[2] + nz * c[2]),
        )
        inv = self._cell_inverse()
        if inv is None:
            return (0.0, 0.0, 0.0)
        na = round(inv[0][0] * target[0] + inv[0][1] * target[1] + inv[0][2] * target[2])
        nb = round(inv[1][0] * target[0] + inv[1][1] * target[1] + inv[1][2] * target[2])
        nc = round(inv[2][0] * target[0] + inv[2][1] * target[1] + inv[2][2] * target[2])
        return (
            na * a[0] + nb * b[0] + nc * c[0],
            na * a[1] + nb * b[1] + nc * c[1],
            na * a[2] + nb * b[2] + nc * c[2],
        )

    def _atom_size_scale(self, atom: Atom) -> float:
        if atom.index in self.atom_index_sizes:
            return self.atom_index_sizes[atom.index]
        if atom.symbol in self.atom_element_sizes:
            return self.atom_element_sizes[atom.symbol]
        return self.atom_size_scale

    def _atom_radius_units(self, atom: Atom) -> float:
        size_scale = self._atom_size_scale(atom)
        if self.atom_representation(atom) == "vdw":
            return VDW_RADII.get(atom.symbol, max(1.2, ATOM_RADII.get(atom.symbol, 0.8) * 1.7)) * size_scale
        if self.atom_radius_mode == "equal":
            return 0.36 * size_scale
        if self.atom_radius_mode == "real":
            return ATOM_RADII.get(atom.symbol, 0.8) * 0.58 * size_scale
        return ATOM_RADII.get(atom.symbol, 0.8) * 0.45 * size_scale

    def _atom_radius(self, atom: Atom, z_value: float = 0.0) -> float:
        perspective = self._perspective_factor(z_value)
        radius_units = self._atom_radius_units(atom)
        projected_radius = radius_units * self.scale * self.zoom * perspective
        # Keep element/custom-size ratios stable at low zoom; a fixed px floor
        # makes H/O/metal atoms collapse to the same apparent size.
        return max(projected_radius, radius_units * 4.5)

    @staticmethod
    def _shade(hex_color: str | QColor, factor: float) -> QColor:
        factor = max(0.0, min(1.4, factor))
        source = QColor(hex_color)
        return QColor(
            max(0, min(255, int(source.red() * factor))),
            max(0, min(255, int(source.green() * factor))),
            max(0, min(255, int(source.blue() * factor))),
        )

    @staticmethod
    def _depth_factor(z_value: float) -> float:
        return max(0.35, min(1.0, 0.55 + 0.45 * ((z_value + 10) / 20)))

    def _atom_color(self, atom: Atom) -> QColor:
        if atom.symbol in self.atom_element_colors:
            return QColor(self.atom_element_colors[atom.symbol])
        if atom.index in self.atom_index_colors:
            return QColor(self.atom_index_colors[atom.index])
        if self.atom_style_mode == "custom":
            return QColor(self.atom_custom_color)
        return QColor(ATOM_COLORS.get(atom.symbol, "#AAAAAA"))

    def _line_style(self, line_type: str):
        return {
            "solid": Qt.SolidLine,
            "dash": Qt.DashLine,
            "dot": Qt.DotLine,
            "dash_dot": Qt.DashDotLine,
            "dash_dot_dot": Qt.DashDotDotLine,
        }.get(str(line_type or "solid"), Qt.SolidLine)

    def _make_pen(self, color: QColor, width: float, line_type: str = "solid", cap_style=Qt.RoundCap) -> QPen:
        pen = QPen(color, max(0.1, float(width)), self._line_style(line_type))
        pen.setCapStyle(cap_style)
        pen.setJoinStyle(Qt.RoundJoin)
        if line_type == "long_dash":
            pen.setStyle(Qt.CustomDashLine)
            pen.setDashPattern([8, 4])
        elif line_type == "short_dash":
            pen.setStyle(Qt.CustomDashLine)
            pen.setDashPattern([3, 2])
        return pen

    @staticmethod
    def _mix_color(left: QColor, right: QColor, right_weight: float) -> QColor:
        w = max(0.0, min(1.0, float(right_weight)))
        return QColor(
            max(0, min(255, int(left.red() * (1.0 - w) + right.red() * w))),
            max(0, min(255, int(left.green() * (1.0 - w) + right.green() * w))),
            max(0, min(255, int(left.blue() * (1.0 - w) + right.blue() * w))),
        )

    def _sphere_gradient(self, color: str, radius: float, sx: float, sy: float, depth: float) -> QRadialGradient:
        q = QColor(color)
        cr, cg, cb = q.red(), q.green(), q.blue()
        luminance = 0.299 * cr + 0.587 * cg + 0.114 * cb
        offset = radius * 0.3
        grad = QRadialGradient(QPointF(sx - offset, sy - offset), radius)
        shadow = QColor(self.atom_shadow_color)

        if luminance > 245:
            grad.setColorAt(0.0, QColor("#FFFFFF"))
            grad.setColorAt(0.35, QColor("#F8F8F8"))
            grad.setColorAt(0.70, QColor("#EEEEEE"))
            grad.setColorAt(1.0, self._mix_color(QColor("#E6E6E6"), shadow, 0.28))
        else:
            grad.setColorAt(0.0, QColor(
                max(0, min(255, int(cr + (255 - cr) * 0.55))),
                max(0, min(255, int(cg + (255 - cg) * 0.55))),
                max(0, min(255, int(cb + (255 - cb) * 0.55))),
            ))
            grad.setColorAt(0.35, QColor(
                max(0, min(255, int(cr + (255 - cr) * 0.12))),
                max(0, min(255, int(cg + (255 - cg) * 0.12))),
                max(0, min(255, int(cb + (255 - cb) * 0.12))),
            ))
            grad.setColorAt(0.70, QColor(cr, cg, cb))
            base_shadow = QColor(
                max(0, min(255, int(cr * 0.66))),
                max(0, min(255, int(cg * 0.66))),
                max(0, min(255, int(cb * 0.66))),
            )
            grad.setColorAt(1.0, self._mix_color(base_shadow, shadow, 0.25))
        return grad

    def _visible_atom_by_index(self, index: int) -> Atom | None:
        atom = self._atoms_by_index.get(index)
        if atom is not None and self.hide_hydrogens and atom.symbol == "H":
            return None
        return atom

    def _find_nearest_atom(self, x: float, y: float) -> int | None:
        best_idx = None
        best_key = (float("inf"), float("inf"))
        for atom_idx, sx, sy, sz, radius in self._projected:
            dist = math.hypot(x - sx, y - sy)
            hit_radius = max(radius, 10)
            if dist >= hit_radius:
                continue
            key = (-sz, dist / hit_radius)
            if key < best_key:
                best_idx, best_key = atom_idx, key
        return best_idx

    def _box_select_atoms(self) -> list[int]:
        if not self._box_start or not self._box_current:
            return []
        x1, y1 = self._box_start
        x2, y2 = self._box_current
        x_min, x_max = min(x1, x2), max(x1, x2)
        y_min, y_max = min(y1, y2), max(y1, y2)
        return [
            atom_idx
            for atom_idx, sx, sy, _sz, _radius in self._projected
            if x_min <= sx <= x_max and y_min <= sy <= y_max
        ]

    def _draw_bond_line(
        self,
        painter: QPainter,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: QColor,
        width: float,
        *,
        cap_style=Qt.RoundCap,
        outline: bool = True,
    ) -> None:
        if width <= 0:
            return
        if outline and self.bond_outline_enabled and self.bond_outline_width > 0:
            painter.setPen(self._make_pen(self.bond_outline_color, width + self.bond_outline_width * 2.0, self.bond_line_type, cap_style=cap_style))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        painter.setPen(self._make_pen(color, width, self.bond_line_type, cap_style=cap_style))
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    def _atom_sort_depth(self, projected_atom: tuple[int, float, float, float, float], atom: Atom) -> float:
        _atom_idx, _sx, _sy, sz, _radius = projected_atom
        return sz + self._atom_radius_units(atom) * 0.70

    def _bond_offset_delta(self, atom1_index: int, atom2_index: int) -> tuple[int, int, int]:
        if not self.cell_vectors or self.cell_display_mode not in {"box", "box_boundary"}:
            return (0, 0, 0)
        atom1 = self._visible_atom_by_index(atom1_index)
        atom2 = self._visible_atom_by_index(atom2_index)
        if atom1 is None or atom2 is None:
            return (0, 0, 0)
        frac1 = self._cart_to_fractional((atom1.x, atom1.y, atom1.z))
        frac2 = self._cart_to_fractional((atom2.x, atom2.y, atom2.z))
        if frac1 is None or frac2 is None:
            return (0, 0, 0)
        return (
            int(math.floor(frac2[0]) - math.floor(frac1[0])),
            int(math.floor(frac2[1]) - math.floor(frac1[1])),
            int(math.floor(frac2[2]) - math.floor(frac1[2])),
        )

    def _bond_render_pairs(
        self,
        atom1_index: int,
        atom2_index: int,
        image_offsets: list[tuple[int, int, int]],
        projected_by_key: dict[tuple[int, tuple[int, int, int]], tuple[int, float, float, float, float]],
        atoms_by_key: dict[tuple[int, tuple[int, int, int]], Atom],
    ) -> list[tuple[tuple[int, float, float, float, float], tuple[int, float, float, float, float], Atom, Atom]]:
        delta = self._bond_offset_delta(atom1_index, atom2_index)
        pairs: list[tuple[tuple[int, float, float, float, float], tuple[int, float, float, float, float], Atom, Atom]] = []
        seen: set[tuple[tuple[int, tuple[int, int, int]], tuple[int, tuple[int, int, int]]]] = set()
        for offset in image_offsets:
            key1 = (atom1_index, offset)
            key2_offset = (offset[0] + delta[0], offset[1] + delta[1], offset[2] + delta[2])
            key2 = (atom2_index, key2_offset)
            if key1 not in projected_by_key or key2 not in projected_by_key:
                continue
            if key1 not in atoms_by_key or key2 not in atoms_by_key:
                continue
            pair_key = (key1, key2)
            if pair_key in seen:
                continue
            seen.add(pair_key)
            pairs.append((projected_by_key[key1], projected_by_key[key2], atoms_by_key[key1], atoms_by_key[key2]))
        return pairs

    @staticmethod
    def _display_bond_key(
        key1: tuple[int, tuple[int, int, int]],
        key2: tuple[int, tuple[int, int, int]],
    ) -> tuple[tuple[int, tuple[int, int, int]], tuple[int, tuple[int, int, int]]]:
        return tuple(sorted((key1, key2), key=lambda item: (item[0], item[1])))

    def _source_display_bond_keys(
        self,
        image_offsets: list[tuple[int, int, int]],
        projected_by_key: dict[tuple[int, tuple[int, int, int]], tuple[int, float, float, float, float]],
    ) -> set[tuple[tuple[int, tuple[int, int, int]], tuple[int, tuple[int, int, int]]]]:
        keys: set[tuple[tuple[int, tuple[int, int, int]], tuple[int, tuple[int, int, int]]]] = set()
        for atom1_index, atom2_index in self.bonds:
            delta = self._bond_offset_delta(atom1_index, atom2_index)
            for offset in image_offsets:
                key1 = (atom1_index, offset)
                key2 = (atom2_index, (offset[0] + delta[0], offset[1] + delta[1], offset[2] + delta[2]))
                if key1 in projected_by_key and key2 in projected_by_key:
                    keys.add(self._display_bond_key(key1, key2))
        return keys

    def _extra_supercell_bond_pairs(
        self,
        projected_entries: list[tuple[Atom, tuple[int, int, int], tuple[int, float, float, float, float]]],
        existing_pairs: set[tuple[tuple[int, tuple[int, int, int]], tuple[int, tuple[int, int, int]]]],
    ) -> list[tuple[tuple[int, float, float, float, float], tuple[int, float, float, float, float], Atom, Atom]]:
        if not self.cell_vectors or not any(repeat > 1 for repeat in self.cell_repeats):
            return []
        pairs: list[tuple[tuple[int, float, float, float, float], tuple[int, float, float, float, float], Atom, Atom]] = []
        seen = set(existing_pairs)
        if len(projected_entries) < 2:
            return pairs
        points = [(entry[0].x, entry[0].y, entry[0].z) for entry in projected_entries]
        radii = [VDW_RADII.get(entry[0].symbol, 1.8) for entry in projected_entries]
        max_cutoff = 1.2 * max(radii)
        for i, j in spatial_candidate_pairs(points, max_cutoff):
            atom1, offset1, projected1 = projected_entries[i]
            atom2, offset2, projected2 = projected_entries[j]
            key1 = (atom1.index, offset1)
            if offset1 == offset2:
                continue
            delta = (offset2[0] - offset1[0], offset2[1] - offset1[1], offset2[2] - offset1[2])
            if max(abs(value) for value in delta) > 1:
                continue
            key2 = (atom2.index, offset2)
            pair_key = self._display_bond_key(key1, key2)
            if pair_key in seen:
                continue
            distance = math.dist(points[i], points[j])
            if distance <= 0.15:
                continue
            cutoff = 0.6 * (radii[i] + radii[j])
            if distance <= cutoff:
                seen.add(pair_key)
                pairs.append((projected1, projected2, atom1, atom2))
        return pairs

    def _bond_cut_factor(self, atom: Atom) -> float:
        return 0.94 if self.atom_representation(atom) == "vdw" else 0.68

    def _regular_bond_visible(self, atom1: Atom, atom2: Atom) -> bool:
        return (
            self.atom_representation(atom1) == "ball_stick"
            and self.atom_representation(atom2) == "ball_stick"
        )

    def _bond_sort_depth(self, p1, p2, atom1: Atom, atom2: Atom) -> float:
        _a1, sx1, sy1, sz1, r1 = p1
        _a2, sx2, sy2, sz2, r2 = p2
        length = math.hypot(sx2 - sx1, sy2 - sy1)
        if length < 1:
            return (sz1 + sz2) / 2.0
        t_start = min(0.49, max(0.0, (r1 * self._bond_cut_factor(atom1)) / length))
        t_end = max(0.51, min(1.0, 1.0 - (r2 * self._bond_cut_factor(atom2)) / length))
        z_start = sz1 + (sz2 - sz1) * t_start
        z_end = sz1 + (sz2 - sz1) * t_end
        return (z_start + z_end) / 2.0

    def _make_bond_items(self, p1, p2, atom1: Atom, atom2: Atom) -> list[tuple[str, float, tuple, tuple, Atom, Atom, float]]:
        if self.bond_width <= 0 or not self._regular_bond_visible(atom1, atom2):
            return []
        sort_depth = self._bond_sort_depth(p1, p2, atom1, atom2)
        return [("bond", sort_depth, p1, p2, atom1, atom2, self._depth_factor(sort_depth))]

    def _draw_bond(self, painter: QPainter, p1, p2, atom1: Atom, atom2: Atom, depth: float) -> None:
        if self.bond_width <= 0 or not self._regular_bond_visible(atom1, atom2):
            return
        _a1, sx1, sy1, _sz1, r1 = p1
        _a2, sx2, sy2, _sz2, r2 = p2
        dx, dy = sx2 - sx1, sy2 - sy1
        length = math.hypot(dx, dy)
        if length < 1:
            return
        cut1 = r1 * self._bond_cut_factor(atom1)
        cut2 = r2 * self._bond_cut_factor(atom2)
        if cut1 + cut2 >= length - 0.5:
            return
        x1, y1 = sx1 + dx * cut1 / length, sy1 + dy * cut1 / length
        x2, y2 = sx2 - dx * cut2 / length, sy2 - dy * cut2 / length
        width = max(0.0, self.bond_width * self.zoom * depth)
        if self.bond_color_mode == "single":
            self._draw_bond_line(painter, x1, y1, x2, y2, QColor(self.bond_custom_color), width)
            return
        mid_x, mid_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        self._draw_bond_line(painter, x1, y1, mid_x, mid_y, self._atom_color(atom1), width)
        self._draw_bond_line(painter, mid_x, mid_y, x2, y2, self._atom_color(atom2), width)

    def _hydrogen_bond_pairs(self) -> list[tuple[int, int]]:
        if not self.hydrogen_bonds_visible:
            return []
        atoms_by_index = {atom.index: atom for atom in self.atoms}
        neighbors: dict[int, set[int]] = {}
        for a1, a2 in self.bonds:
            neighbors.setdefault(a1, set()).add(a2)
            neighbors.setdefault(a2, set()).add(a1)
        donors = {"N", "O", "F", "S", "Cl"}
        acceptors = {"N", "O", "F", "Cl"}
        pairs: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for hydrogen in self.atoms:
            if hydrogen.symbol != "H" or self.hide_hydrogens:
                continue
            hydrogen_xyz = (hydrogen.x, hydrogen.y, hydrogen.z)
            donor_atoms = [
                atoms_by_index[index]
                for index in neighbors.get(hydrogen.index, set())
                if atoms_by_index.get(index) and atoms_by_index[index].symbol in donors
            ]
            if not donor_atoms:
                continue
            for donor in donor_atoms:
                donor_xyz = (donor.x, donor.y, donor.z)
                donor_to_h = (
                    hydrogen_xyz[0] - donor_xyz[0],
                    hydrogen_xyz[1] - donor_xyz[1],
                    hydrogen_xyz[2] - donor_xyz[2],
                )
                for acceptor in self.atoms:
                    if acceptor.index in {hydrogen.index, donor.index}:
                        continue
                    if acceptor.symbol not in acceptors:
                        continue
                    if acceptor.index in neighbors.get(hydrogen.index, set()):
                        continue
                    acceptor_xyz = (acceptor.x, acceptor.y, acceptor.z)
                    d_a = math.dist(donor_xyz, acceptor_xyz)
                    h_to_acceptor = (
                        acceptor_xyz[0] - hydrogen_xyz[0],
                        acceptor_xyz[1] - hydrogen_xyz[1],
                        acceptor_xyz[2] - hydrogen_xyz[2],
                    )
                    angle = self._vector_angle_degrees(donor_to_h, h_to_acceptor)
                    if d_a < 3.5 and angle < 35.0:
                        key = self._bond_key(hydrogen.index, acceptor.index)
                        if key not in seen:
                            seen.add(key)
                            pairs.append(key)
        return pairs

    @staticmethod
    def _vector_angle_degrees(v1: tuple[float, float, float], v2: tuple[float, float, float]) -> float:
        n1 = math.sqrt(v1[0] * v1[0] + v1[1] * v1[1] + v1[2] * v1[2])
        n2 = math.sqrt(v2[0] * v2[0] + v2[1] * v2[1] + v2[2] * v2[2])
        if n1 <= 1e-9 or n2 <= 1e-9:
            return 180.0
        dot = (v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]) / (n1 * n2)
        return math.degrees(math.acos(max(-1.0, min(1.0, dot))))

    def _draw_hydrogen_bond(self, painter: QPainter, p1, p2) -> None:
        if self.hydrogen_bond_width <= 0:
            return
        _a1, sx1, sy1, _sz1, r1 = p1
        _a2, sx2, sy2, _sz2, r2 = p2
        dx, dy = sx2 - sx1, sy2 - sy1
        length = math.hypot(dx, dy)
        if length < 1:
            return
        cut1, cut2 = r1 * 0.72, r2 * 0.72
        x1, y1 = sx1 + dx * cut1 / length, sy1 + dy * cut1 / length
        x2, y2 = sx2 - dx * cut2 / length, sy2 - dy * cut2 / length
        width = max(0.1, self.hydrogen_bond_width * self.zoom)
        painter.setPen(self._make_pen(QColor(self.hydrogen_bond_color), width, "dot"))
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    def _draw_atom(self, painter: QPainter, atom: Atom, sx: float, sy: float, sz: float, radius: float) -> None:
        color = self._atom_color(atom)
        depth = self._depth_factor(sz)
        painter.setPen(Qt.NoPen)
        if self._interactive_rendering:
            fast_color = QColor(color)
            fast_color = QColor(
                max(0, min(255, int(fast_color.red() * depth))),
                max(0, min(255, int(fast_color.green() * depth))),
                max(0, min(255, int(fast_color.blue() * depth))),
            )
            painter.setBrush(QBrush(fast_color))
            painter.drawEllipse(QPoint(int(sx), int(sy)), int(radius), int(radius))
        else:
            painter.setBrush(QBrush(self._sphere_gradient(color.name(), radius, sx, sy, depth)))
            painter.drawEllipse(QPoint(int(sx), int(sy)), int(radius), int(radius))

        if self.atom_outline_enabled and self.atom_outline_width > 0:
            painter.setPen(self._make_pen(self.atom_outline_color, max(0.2, self.atom_outline_width * self.zoom)))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPoint(int(sx), int(sy)), int(radius), int(radius))

        if atom.index in self.selected_atoms or atom.index in self.frozen_atoms:
            outline = SELECTED_ATOM_COLOR if atom.index in self.selected_atoms else FROZEN_ATOM_COLOR
            width = max(3, int(radius * 0.18)) if atom.index in self.selected_atoms else max(2, int(radius * 0.16))
            painter.setPen(QPen(outline, width))
            painter.drawEllipse(QPoint(int(sx), int(sy)), int(radius + 3), int(radius + 3))

        force_single_label = atom.index in self.clicked_label_atoms
        if not self._interactive_rendering and radius >= 6 and (force_single_label or self.show_symbols or self.show_numbers):
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(7, min(14, int(radius * 0.48))))
            painter.setFont(font)
            painter.setPen(QPen(QColor("#111827")))
            label = f"{atom.symbol}{atom.index}" if force_single_label else atom.symbol
            if force_single_label or (self.show_symbols and self.show_numbers):
                label = f"{atom.symbol}{atom.index}"
            elif self.show_numbers:
                label = str(atom.index)
            metrics = painter.fontMetrics()
            width = metrics.horizontalAdvance(label)
            height = metrics.height()
            painter.drawText(QRectF(sx - width / 2 - 2, sy - height / 2 - 1, width + 4, height + 2), Qt.AlignCenter, label)

    def _visible_atom_count(self) -> int:
        atoms = [atom for atom, _offset in self._display_atom_entries()]
        if not self.hide_hydrogens:
            return len(atoms)
        return sum(1 for atom in atoms if atom.symbol != "H")

    def _should_use_fast_opengl(self) -> bool:
        if not USE_OPENGL_CANVAS or not self.atoms:
            return False
        return self.use_fast_opengl_while_interacting and self._interactive_rendering

    def _project_display_entries(self) -> tuple[
        dict[tuple[int, tuple[int, int, int]], tuple[int, float, float, float, float]],
        list[tuple[Atom, tuple[int, int, int], tuple[int, float, float, float, float]]],
    ]:
        self._projected = []
        projected: dict[tuple[int, tuple[int, int, int]], tuple[int, float, float, float, float]] = {}
        entries: list[tuple[Atom, tuple[int, int, int], tuple[int, float, float, float, float]]] = []
        for atom, offset in self._display_atom_entries():
            if self.hide_hydrogens and atom.symbol == "H":
                continue
            sx, sy, sz = self._project(atom)
            radius = self._atom_radius(atom, sz)
            item = (atom.index, sx, sy, sz, radius)
            self._projected.append(item)
            projected[(atom.index, offset)] = item
            entries.append((atom, offset, item))
        return projected, entries

    def _project_visible_atoms(self) -> dict[tuple[int, tuple[int, int, int]], tuple[int, float, float, float, float]]:
        projected, _entries = self._project_display_entries()
        return projected

    def _gl_api(self) -> _OpenGLApi:
        if self._gl is None:
            self._gl = _OpenGLApi()
        return self._gl

    def _gl_set_color(self, color: QColor, depth: float = 1.0, alpha: float = 1.0) -> None:
        factor = max(0.35, min(1.15, depth))
        self._gl_api().glColor4f(
            ctypes.c_float(max(0.0, min(1.0, color.redF() * factor))),
            ctypes.c_float(max(0.0, min(1.0, color.greenF() * factor))),
            ctypes.c_float(max(0.0, min(1.0, color.blueF() * factor))),
            ctypes.c_float(max(0.0, min(1.0, alpha))),
        )

    def _gl_line(self, x1: float, y1: float, x2: float, y2: float, color: QColor, width: float, alpha: float = 1.0) -> None:
        gl = self._gl_api()
        if width <= 0:
            return
        gl.glLineWidth(ctypes.c_float(max(1.0, min(16.0, float(width)))))
        self._gl_set_color(color, 1.0, alpha)
        gl.glBegin(GL_LINES)
        gl.glVertex2f(ctypes.c_float(float(x1)), ctypes.c_float(float(y1)))
        gl.glVertex2f(ctypes.c_float(float(x2)), ctypes.c_float(float(y2)))
        gl.glEnd()

    def _gl_point(self, x: float, y: float, radius: float, color: QColor, depth: float, alpha: float = 1.0) -> None:
        gl = self._gl_api()
        gl.glPointSize(ctypes.c_float(max(2.0, min(96.0, radius * 2.0))))
        self._gl_set_color(color, depth, alpha)
        gl.glBegin(GL_POINTS)
        gl.glVertex2f(ctypes.c_float(float(x)), ctypes.c_float(float(y)))
        gl.glEnd()

    def _paint_scene_fast_opengl(self) -> None:
        gl = self._gl_api()
        width, height = max(1, self.width()), max(1, self.height())
        gl.glViewport(0, 0, width, height)
        gl.glClearColor(1.0, 1.0, 1.0, 1.0)
        gl.glClear(GL_COLOR_BUFFER_BIT)
        gl.glMatrixMode(GL_PROJECTION)
        gl.glLoadIdentity()
        gl.glOrtho(0.0, float(width), float(height), 0.0, -1.0, 1.0)
        gl.glMatrixMode(GL_MODELVIEW)
        gl.glLoadIdentity()
        gl.glEnable(GL_BLEND)
        gl.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        gl.glEnable(GL_POINT_SMOOTH)
        gl.glEnable(GL_LINE_SMOOTH)

        if not self.atoms:
            self._paint_fast_overlay()
            gl.glFlush()
            return

        projected_by_key, projected_entries = self._project_display_entries()
        atoms_by_key = {(atom.index, offset): atom for atom, offset, _item in projected_entries}
        image_offsets = sorted({offset for _atom, offset, _item in projected_entries})
        source_bond_keys = self._source_display_bond_keys(image_offsets, projected_by_key)

        if self.cell_visible:
            color = QColor(self.cell_color)
            gl.glLineWidth(ctypes.c_float(max(1.0, min(16.0, float(self.cell_width)))))
            self._gl_set_color(color, 1.0, self.cell_opacity)
            gl.glBegin(GL_LINES)
            for p1, p2 in self._cell_edges():
                sx1, sy1, _sz1 = self._project_point(*p1)
                sx2, sy2, _sz2 = self._project_point(*p2)
                gl.glVertex2f(ctypes.c_float(float(sx1)), ctypes.c_float(float(sy1)))
                gl.glVertex2f(ctypes.c_float(float(sx2)), ctypes.c_float(float(sy2)))
            gl.glEnd()

        if self.bonds_visible and self.bond_width > 0:
            visible_bonds = []
            for a1, a2 in self.bonds:
                for p1, p2, atom1, atom2 in self._bond_render_pairs(a1, a2, image_offsets, projected_by_key, atoms_by_key):
                    visible_bonds.append(((p1[3] + p2[3]) / 2.0, p1, p2, atom1, atom2))
            for p1, p2, atom1, atom2 in self._extra_supercell_bond_pairs(projected_entries, source_bond_keys):
                visible_bonds.append(((p1[3] + p2[3]) / 2.0, p1, p2, atom1, atom2))
            gl.glLineWidth(ctypes.c_float(max(0.5, min(16.0, self.bond_width * self.zoom))))
            for _depth, p1, p2, atom1, atom2 in sorted(visible_bonds, key=lambda item: item[0]):
                if not atom1 or not atom2 or not self._regular_bond_visible(atom1, atom2):
                    continue
                _a1, sx1, sy1, _sz1, r1 = p1
                _a2, sx2, sy2, _sz2, r2 = p2
                dx, dy = sx2 - sx1, sy2 - sy1
                length = math.hypot(dx, dy)
                if length < 1:
                    continue
                cut1 = r1 * self._bond_cut_factor(atom1)
                cut2 = r2 * self._bond_cut_factor(atom2)
                if cut1 + cut2 >= length - 0.5:
                    continue
                x1, y1 = sx1 + dx * cut1 / length, sy1 + dy * cut1 / length
                x2, y2 = sx2 - dx * cut2 / length, sy2 - dy * cut2 / length
                if self.bond_color_mode == "single":
                    self._gl_line(x1, y1, x2, y2, QColor(self.bond_custom_color), self.bond_width * self.zoom, 0.86)
                else:
                    mid_x, mid_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                    self._gl_line(x1, y1, mid_x, mid_y, self._atom_color(atom1), self.bond_width * self.zoom, 0.86)
                    self._gl_line(mid_x, mid_y, x2, y2, self._atom_color(atom2), self.bond_width * self.zoom, 0.86)

        if self.hydrogen_bonds_visible and self.hydrogen_bond_width > 0:
            gl.glLineWidth(ctypes.c_float(max(0.5, min(16.0, self.hydrogen_bond_width * 2.0))))
            self._gl_set_color(QColor(self.hydrogen_bond_color), 1.0, 0.65)
            gl.glBegin(GL_LINES)
            for a1, a2 in self._hydrogen_bond_pairs():
                for p1, p2, _atom1, _atom2 in self._bond_render_pairs(a1, a2, image_offsets, projected_by_key, atoms_by_key):
                    _i1, sx1, sy1, _z1, _r1 = p1
                    _i2, sx2, sy2, _z2, _r2 = p2
                    gl.glVertex2f(ctypes.c_float(float(sx1)), ctypes.c_float(float(sy1)))
                    gl.glVertex2f(ctypes.c_float(float(sx2)), ctypes.c_float(float(sy2)))
            gl.glEnd()

        selected_or_frozen = self.selected_atoms | self.frozen_atoms
        atom_batches: dict[tuple[int, str], list[tuple[float, float]]] = {}
        outline_batches: dict[int, list[tuple[float, float, QColor]]] = {}
        for atom, _offset, projected_atom in sorted(projected_entries, key=lambda row: row[2][3]):
            atom_idx, sx, sy, sz, radius = projected_atom
            if atom_idx in selected_or_frozen:
                outline = SELECTED_ATOM_COLOR if atom_idx in self.selected_atoms else FROZEN_ATOM_COLOR
                outline_size = int(round(max(2.0, min(96.0, (radius + 2.5) * 2.0))))
                outline_batches.setdefault(outline_size, []).append((sx, sy, outline))
            point_size = int(round(max(2.0, min(96.0, radius * 2.0))))
            base_color = self._atom_color(atom)
            depth = self._depth_factor(sz)
            bucket = 0.58 if depth < 0.62 else 0.78 if depth < 0.82 else 1.0
            fast_color = self._shade(base_color, bucket).name()
            atom_batches.setdefault((point_size, fast_color), []).append((sx, sy))
        for point_size, items in sorted(outline_batches.items()):
            gl.glPointSize(ctypes.c_float(float(point_size)))
            gl.glBegin(GL_POINTS)
            for sx, sy, color in items:
                self._gl_set_color(color, 1.0, 0.95)
                gl.glVertex2f(ctypes.c_float(float(sx)), ctypes.c_float(float(sy)))
            gl.glEnd()
        for (point_size, color_name), items in sorted(atom_batches.items()):
            gl.glPointSize(ctypes.c_float(float(point_size)))
            self._gl_set_color(QColor(color_name), 1.0, 1.0)
            gl.glBegin(GL_POINTS)
            for sx, sy in items:
                gl.glVertex2f(ctypes.c_float(float(sx)), ctypes.c_float(float(sy)))
            gl.glEnd()

        self._paint_fast_overlay()
        gl.glFlush()

    def _paint_fast_overlay(self) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        if self._box_selecting and self._box_start and self._box_current:
            x1, y1 = self._box_start
            x2, y2 = self._box_current
            x_min, y_min = min(x1, x2), min(y1, y2)
            x_max, y_max = max(x1, x2), max(y1, y2)
            painter.setPen(QPen(QColor("#176B87"), 1.5, Qt.DashLine))
            painter.setBrush(QColor(23, 107, 135, 30))
            painter.drawRect(x_min, y_min, x_max - x_min, y_max - y_min)
        if self.show_compass:
            self._draw_compass(painter)
        painter.end()

    def paintEvent(self, event) -> None:
        if USE_OPENGL_CANVAS:
            super().paintEvent(event)
            return
        self._last_render_path = "qpaint-widget"
        self._paint_scene()

    def _paint_scene(self) -> None:
        painter = QPainter(self)
        self._paint_scene_to_painter(painter, transparent_background=False)
        painter.end()

    def render_to_image(self, scale: float = 3.0, transparent_background: bool = False) -> QImage:
        scale = max(1.0, min(4.0, float(scale)))
        width = max(1, int(round(self.width() * scale)))
        height = max(1, int(round(self.height() * scale)))
        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent if transparent_background else QColor("#FFFFFF"))
        painter = QPainter(image)
        painter.scale(scale, scale)
        old_interactive = self._interactive_rendering
        self._interactive_rendering = False
        try:
            self._paint_scene_to_painter(painter, transparent_background=transparent_background)
        finally:
            self._interactive_rendering = old_interactive
            painter.end()
        return image

    def _paint_scene_to_painter(self, painter: QPainter, *, transparent_background: bool = False) -> None:
        painter.setRenderHint(QPainter.Antialiasing, not self._interactive_rendering)
        if not transparent_background:
            painter.fillRect(self.rect(), QColor("#FFFFFF"))

        if not self.atoms:
            painter.setPen(QPen(QColor("#7C8A99")))
            painter.drawText(self.rect(), Qt.AlignCenter, "Load a structure file to display atoms.")
            return

        projected_by_key, projected_entries = self._project_display_entries()
        atoms_by_key = {(atom.index, offset): atom for atom, offset, _item in projected_entries}
        image_offsets = sorted({offset for _atom, offset, _item in projected_entries})
        source_bond_keys = self._source_display_bond_keys(image_offsets, projected_by_key)

        render_items = []
        if self.bonds_visible and self.bond_width > 0:
            for a1, a2 in self.bonds:
                for p1, p2, atom1, atom2 in self._bond_render_pairs(a1, a2, image_offsets, projected_by_key, atoms_by_key):
                    render_items.extend(self._make_bond_items(p1, p2, atom1, atom2))
            for p1, p2, atom1, atom2 in self._extra_supercell_bond_pairs(projected_entries, source_bond_keys):
                render_items.extend(self._make_bond_items(p1, p2, atom1, atom2))

        if self.hydrogen_bonds_visible and self.hydrogen_bond_width > 0:
            for a1, a2 in self._hydrogen_bond_pairs():
                for p1, p2, _atom1, _atom2 in self._bond_render_pairs(a1, a2, image_offsets, projected_by_key, atoms_by_key):
                    render_items.append(("hbond", (p1[3] + p2[3]) / 2, p1, p2))

        for atom, _offset, projected_atom in projected_entries:
            _atom_idx, sx, sy, sz, radius = projected_atom
            render_items.append(("atom", self._atom_sort_depth(projected_atom, atom), atom, sx, sy, sz, radius))

        for item in sorted(render_items, key=lambda value: (value[1], 0 if value[0] != "atom" else 1)):
            kind = item[0]
            if kind == "atom":
                _kind, _depth, atom, sx, sy, sz, radius = item
                self._draw_atom(painter, atom, sx, sy, sz, radius)
            elif kind == "hbond":
                _kind, _depth, p1, p2 = item
                self._draw_hydrogen_bond(painter, p1, p2)
            else:
                _kind, _sort_depth, p1, p2, atom1, atom2, depth = item
                self._draw_bond(painter, p1, p2, atom1, atom2, depth)

        self._draw_cell_edges(painter)

        if self._box_selecting and self._box_start and self._box_current:
            x1, y1 = self._box_start
            x2, y2 = self._box_current
            x_min, y_min = min(x1, x2), min(y1, y2)
            x_max, y_max = max(x1, x2), max(y1, y2)
            painter.setPen(QPen(QColor("#176B87"), 1.5, Qt.DashLine))
            painter.setBrush(QColor(23, 107, 135, 30))
            painter.drawRect(x_min, y_min, x_max - x_min, y_max - y_min)

        if self.show_compass:
            self._draw_compass(painter)

    def _cell_pen_style(self):
        return {
            "solid": Qt.SolidLine,
            "dot": Qt.DotLine,
            "dash_dot": Qt.DashDotLine,
            "dash_dot_dot": Qt.DashDotDotLine,
        }.get(self.cell_line_type, Qt.DashLine)

    def _cell_pen(self) -> QPen:
        color = QColor(self.cell_color)
        color.setAlphaF(max(0.05, min(1.0, self.cell_opacity)))
        pen = QPen(color, max(0.5, self.cell_width), self._cell_pen_style())
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        if self.cell_line_type == "long_dash":
            pen.setStyle(Qt.CustomDashLine)
            pen.setDashPattern([8, 4])
        elif self.cell_line_type == "short_dash":
            pen.setStyle(Qt.CustomDashLine)
            pen.setDashPattern([3, 2])
        return pen

    def _draw_cell_edges(self, painter: QPainter) -> None:
        if not self.cell_visible:
            return
        edges = self._cell_edges()
        if not edges:
            return
        for p1, p2 in edges:
            sx1, sy1, sz1 = self._project_point(*p1)
            sx2, sy2, sz2 = self._project_point(*p2)
            self._draw_cell_edge(painter, sx1, sy1, sz1, sx2, sy2, sz2)

    def _draw_cell_edge(self, painter: QPainter, sx1: float, sy1: float, sz1: float, sx2: float, sy2: float, sz2: float) -> None:
        painter.save()
        clip = QPainterPath()
        clip.addRect(QRectF(self.rect()))
        if not self._interactive_rendering:
            for atom_index, ax, ay, atom_z, radius in self._projected:
                t = self._closest_point_fraction(ax, ay, sx1, sy1, sx2, sy2)
                closest_x = sx1 + (sx2 - sx1) * t
                closest_y = sy1 + (sy2 - sy1) * t
                line_depth = sz1 + (sz2 - sz1) * t
                distance = math.hypot(ax - closest_x, ay - closest_y)
                if distance > radius + self.cell_width + 1.5:
                    continue
                atom = self._visible_atom_by_index(atom_index)
                atom_depth = self._atom_sort_depth((atom_index, ax, ay, atom_z, radius), atom) if atom else atom_z
                if atom_depth <= line_depth:
                    continue
                ellipse = QPainterPath()
                clip_radius = radius + max(1.0, self.cell_width * 0.8)
                ellipse.addEllipse(QRectF(ax - clip_radius, ay - clip_radius, clip_radius * 2.0, clip_radius * 2.0))
                clip = clip.subtracted(ellipse)
        painter.setClipPath(clip)
        painter.setPen(self._cell_pen())
        painter.drawLine(int(sx1), int(sy1), int(sx2), int(sy2))
        painter.restore()

    @staticmethod
    def _closest_point_fraction(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        dx, dy = x2 - x1, y2 - y1
        length2 = dx * dx + dy * dy
        if length2 <= 1e-9:
            return 0.0
        return max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length2))

    def _draw_compass(self, painter: QPainter) -> None:
        origin_x = self.width() - 74
        origin_y = self.height() - 58
        length = 36
        axes = [
            ("X", (1.0, 0.0, 0.0), QColor("#D62828")),
            ("Y", (0.0, 1.0, 0.0), QColor("#2A9D55")),
            ("Z", (0.0, 0.0, 1.0), QColor("#2563EB")),
        ]
        font = painter.font()
        font.setBold(True)
        font.setPointSize(8)
        painter.setFont(font)
        for label, vector, color in axes:
            rx, ry, rz = self._rotate(*vector)
            depth = self._depth_factor(rz)
            end_x = origin_x + rx * length
            end_y = origin_y - ry * length
            painter.setPen(QPen(color, max(2, int(3 * depth)), cap=Qt.RoundCap))
            painter.drawLine(int(origin_x), int(origin_y), int(end_x), int(end_y))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPoint(int(end_x), int(end_y)), 3, 3)
            painter.setPen(QPen(color))
            painter.drawText(QRectF(end_x - 8, end_y - 18, 18, 16), Qt.AlignCenter, label)

    def mousePressEvent(self, event) -> None:
        self._drag_history_recorded = False
        shift = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)
        if event.button() == Qt.LeftButton and shift:
            self._box_selecting = True
            self._box_start = (event.x(), event.y())
            self._box_current = (event.x(), event.y())
            self.update()
        elif event.button() == Qt.LeftButton:
            self._interactive_rendering = True
            self._drag_start = (event.x(), event.y())
            self._drag_last = (event.x(), event.y())
            self._drag_rot = (self.rot_x, self.rot_y)
            self._click_pos = (event.x(), event.y())
        elif event.button() == Qt.RightButton:
            self._interactive_rendering = True
            self._drag_start = (event.x(), event.y())
            self._drag_roll = self.rot_z
            self._click_pos = (event.x(), event.y())
        elif event.button() == Qt.MiddleButton:
            self._interactive_rendering = True
            self._drag_start = (event.x(), event.y())
            self._drag_pan = (self.pan_x, self.pan_y)

    def mouseMoveEvent(self, event) -> None:
        if self._box_selecting:
            self._box_current = (event.x(), event.y())
            self.update()
            return
        if self._drag_start is None:
            return
        if event.buttons() & Qt.LeftButton and self._drag_rot is not None:
            last_x, last_y = self._drag_last or self._drag_start
            dx = event.x() - last_x
            dy = event.y() - last_y
            if not self._drag_history_recorded and (abs(dx) > 0.01 or abs(dy) > 0.01):
                self._record_history()
                self._drag_history_recorded = True
            self._rotate_by_screen_drag(dx, dy)
            self._drag_last = (event.x(), event.y())
            self.update()
        elif event.buttons() & Qt.RightButton and self._drag_roll is not None:
            dx = event.x() - self._drag_start[0]
            if not self._drag_history_recorded and abs(dx) > 0.01:
                self._record_history()
                self._drag_history_recorded = True
            self.rot_z = self._drag_roll + dx * 0.5
            self.update()
        elif event.buttons() & Qt.MiddleButton and self._drag_pan is not None:
            dx = event.x() - self._drag_start[0]
            dy = event.y() - self._drag_start[1]
            if not self._drag_history_recorded and (abs(dx) > 0.01 or abs(dy) > 0.01):
                self._record_history()
                self._drag_history_recorded = True
            self.pan_x = self._drag_pan[0] + dx
            self.pan_y = self._drag_pan[1] + dy
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._box_selecting:
            self._box_selecting = False
            selected = self._box_select_atoms()
            self._box_start = None
            self._box_current = None
            if selected:
                self._record_history()
                self.selected_atoms.update(selected)
                self.selection_changed.emit(sorted(self.selected_atoms))
            self.update()
            return

        if self._click_pos and event.button() in (Qt.LeftButton, Qt.RightButton):
            dx = event.x() - self._click_pos[0]
            dy = event.y() - self._click_pos[1]
            if abs(dx) < 5 and abs(dy) < 5:
                atom_idx = self._find_nearest_atom(event.x(), event.y())
                if event.button() == Qt.LeftButton and atom_idx is not None:
                    self._record_history()
                    if atom_idx in self.selected_atoms:
                        self.selected_atoms.remove(atom_idx)
                        self.clicked_label_atoms.discard(atom_idx)
                    else:
                        self.selected_atoms.add(atom_idx)
                        self.clicked_label_atoms.add(atom_idx)
                    self.atom_clicked.emit(atom_idx)
                    self.selection_changed.emit(sorted(self.selected_atoms))
                    self.update()
                elif atom_idx is None and self.selected_atoms:
                    self.clear_selection()
        self._interactive_rendering = False
        self._drag_start, self._drag_last, self._drag_rot, self._drag_pan, self._drag_roll, self._click_pos = None, None, None, None, None, None
        self.update()

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        next_zoom = max(0.1, min(20.0, self.zoom * (1.1 if delta > 0 else 0.9)))
        if abs(next_zoom - self.zoom) < 1e-9:
            return
        self._record_history()
        self.zoom = next_zoom
        self.update()
