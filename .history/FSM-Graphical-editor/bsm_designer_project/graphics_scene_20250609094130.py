# bsm_designer_project/graphics_scene.py

# FILE: bsm_designer_project/graphics_scene.py
# Includes connections for validation signals and the Problems Dock.

import sys
import os
import json
import logging
import math
import re
from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsLineItem,
    QMenu, QMessageBox, QDialog, QStyle, QGraphicsSceneMouseEvent,
    QGraphicsSceneDragDropEvent, QApplication, QGraphicsSceneContextMenuEvent
)
from PyQt5.QtGui import QWheelEvent,QMouseEvent, QDrag, QDropEvent, QPixmap
from PyQt5.QtGui import QKeyEvent, QKeySequence, QCursor, QPainter, QColor, QPen, QBrush, QTransform
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF, pyqtSignal, QPoint, QMarginsF, QEvent, QMimeData, QTimer

from . import config # Import config to access its dynamic color variables

from .utils import get_standard_icon # Corrected import

from .config import ( # Corrected import
    COLOR_ACCENT_PRIMARY,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG,
    DEFAULT_EXECUTION_ENV,
    MIME_TYPE_BSM_ITEMS,
    MIME_TYPE_BSM_TEMPLATE
)

try:
    from .graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
except ImportError:
    from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem

try:
    from .undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
except ImportError:
    from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand

from .snippet_manager import CustomSnippetManager # Corrected import
from .settings_manager import SettingsManager # Corrected import


logger = logging.getLogger(__name__)

SNAP_THRESHOLD_PIXELS = 8
GUIDELINE_PEN_WIDTH = 0.8


class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool)
    scene_content_changed_for_find = pyqtSignal()
    validation_issues_updated = pyqtSignal(list)
    interaction_mode_changed = pyqtSignal(str) # New signal for mode change


    def __init__(self, undo_stack, parent_window=None, custom_snippet_manager: CustomSnippetManager | None = None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.custom_snippet_manager = custom_snippet_manager
        self.setSceneRect(0, 0, 6000, 4500)
        self.current_mode = "select"
        self.transition_start_item = None
        self.undo_stack = undo_stack
        self._dirty = False
        self._mouse_press_items_positions = {}
        self._temp_transition_line = None
        self.current_hovered_target_item: GraphicsStateItem | None = None # New for hover highlight


        self.item_moved.connect(self._handle_item_moved_visual_update)

        self.grid_size = 20 

        self.grid_pen_light = QPen(QColor(config.COLOR_GRID_MINOR), 0.7, Qt.DotLine)
        self.grid_pen_dark = QPen(QColor(config.COLOR_GRID_MAJOR), 0.9, Qt.SolidLine)
        self.setBackgroundBrush(QColor(config.COLOR_BACKGROUND_LIGHT))

        self.snap_to_grid_enabled = True
        self.snap_to_objects_enabled = True
        self._show_dynamic_snap_guidelines = True
        self._guideline_pen = QPen(QColor(config.COLOR_SNAP_GUIDELINE), GUIDELINE_PEN_WIDTH, Qt.DashLine)


        self._horizontal_snap_lines: list[QLineF] = []
        self._vertical_snap_lines: list[QLineF] = []
        self._validation_issues = []
        self._problematic_items = set()
        
        if QApplication.instance() and hasattr(QApplication.instance(), 'settings_manager'):
            settings = QApplication.instance().settings_manager
            self.snap_to_grid_enabled = settings.get("view_snap_to_grid")
            self.snap_to_objects_enabled = settings.get("view_snap_to_objects")
            self._show_dynamic_snap_guidelines = settings.get("view_show_snap_guidelines")
            self.grid_size = settings.get("grid_size")
            self.grid_pen_light.setColor(QColor(settings.get("canvas_grid_minor_color")))
            self.grid_pen_dark.setColor(QColor(settings.get("canvas_grid_major_color")))
            self._guideline_pen.setColor(QColor(settings.get("canvas_snap_guideline_color")))
            self.setBackgroundBrush(QColor(config.COLOR_BACKGROUND_LIGHT)) # This ensures theme is applied

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.fillRect(rect, self.backgroundBrush())
        
        settings = QApplication.instance().settings_manager if QApplication.instance() and hasattr(QApplication.instance(), 'settings_manager') else None
        show_grid = True
        if settings:
            show_grid = settings.get("view_show_grid")
            self.grid_pen_light.setColor(QColor(settings.get("canvas_grid_minor_color")))
            self.grid_pen_dark.setColor(QColor(settings.get("canvas_grid_major_color")))
            self._guideline_pen.setColor(QColor(settings.get("canvas_snap_guideline_color")))
            self.setBackgroundBrush(QColor(config.COLOR_BACKGROUND_LIGHT))

        if not show_grid:
            return

        left = int(rect.left()) - (int(rect.left()) % self.grid_size)
        top = int(rect.top()) - (int(rect.top()) % self.grid_size)
        lines_light, lines_dark = [], []

        for x in range(left, int(rect.right()), self.grid_size):
            if x % (self.grid_size * 5) == 0: lines_dark.append(QLineF(x, rect.top(), x, rect.bottom()))
            else: lines_light.append(QLineF(x, rect.top(), x, rect.bottom()))
        for y in range(top, int(rect.bottom()), self.grid_size):
            if y % (self.grid_size * 5) == 0: lines_dark.append(QLineF(rect.left(), y, rect.right(), y))
            else: lines_light.append(QLineF(rect.left(), y, rect.right(), y))
        
        painter.setPen(self.grid_pen_light); painter.drawLines(lines_light)
        painter.setPen(self.grid_pen_dark); painter.drawLines(lines_dark)

        if self._show_dynamic_snap_guidelines and (self._horizontal_snap_lines or self._vertical_snap_lines):
            painter.setPen(self._guideline_pen)
            for line in self._horizontal_snap_lines: painter.drawLine(line)
            for line in self._vertical_snap_lines: painter.drawLine