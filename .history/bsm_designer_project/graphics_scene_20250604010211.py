

# FILE: bsm_designer_project/graphics_scene.py

import sys
import os
import json
import logging
import math
import re
import uuid # Ensure uuid is imported

from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsLineItem,
    QMenu, QMessageBox, QDialog, QStyle, QGraphicsSceneMouseEvent,
    QGraphicsSceneDragDropEvent, QApplication, QGraphicsSceneContextMenuEvent
)
from PyQt5.QtGui import QWheelEvent,QMouseEvent, QDrag, QDropEvent, QPixmap
from PyQt5.QtGui import QKeyEvent, QKeySequence, QCursor, QPainter, QColor, QPen, QBrush, QTransform
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF, pyqtSignal, QPoint, QMarginsF, QEvent, QMimeData, QTimer

from utils import get_standard_icon

from config import (
    COLOR_BACKGROUND_LIGHT, COLOR_GRID_MINOR, COLOR_GRID_MAJOR, COLOR_ACCENT_PRIMARY,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG,
    DEFAULT_EXECUTION_ENV, COLOR_BORDER_LIGHT, COLOR_BORDER_MEDIUM,
    MIME_TYPE_BSM_ITEMS, MIME_TYPE_BSM_TEMPLATE
)

try:
    from .graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem
except ImportError:
    from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem

try:
    from .undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
except ImportError:
    from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand

logger = logging.getLogger(__name__)

SNAP_THRESHOLD_PIXELS = 8
GUIDELINE_PEN_COLOR = QColor(Qt.red)
GUIDELINE_PEN_WIDTH = 0.8

class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool)
    scene_content_changed_for_find = pyqtSignal()
    validation_issues_updated = pyqtSignal(list)

    def __init__(self, undo_stack, parent_window=None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setSceneRect(0, 0, 6000, 4500)
        self.current_mode = "select"
        self.transition_start_item: QGraphicsItem | None = None
        self.undo_stack = undo_stack
        self._dirty = False
        self._mouse_press_items_positions = {}
        self._temp_transition_line = None

        self.item_moved.connect(self._handle_item_moved_visual_update)

        self.grid_size = 20
        self.grid_pen_light = QPen(QColor(COLOR_GRID_MINOR), 0.7, Qt.DotLine)
        self.grid_pen_dark = QPen(QColor(COLOR_GRID_MAJOR), 0.9, Qt.SolidLine)
        self.setBackgroundBrush(QColor(COLOR_BACKGROUND_LIGHT))
        self.snap_to_grid_enabled = True
        self.snap_to_objects_enabled = True

        self._horizontal_snap_lines: list[QLineF] = []
        self._vertical_snap_lines: list[QLineF] = []
        self._show_dynamic_snap_guidelines = True

        self._validation_issues = []
        self._problematic_items = set()

    def _log_to_parent(self, level, message):
        if self.parent_window and hasattr(self.parent_window, 'log_message'):
            self.parent_window.log_message(level, message)
        else:
            logger.log(getattr(logging, level.upper(), logging.INFO), f"(SceneDirect) {message}")

    def log_function(self, message: str, level: str = "ERROR"): # Used by undo commands
        self._log_to_parent(level.upper(), message)

    def get_item_by_uuid(self, uuid_str: str) -> QGraphicsItem | None:
        if not uuid_str:
            return None
        for item in self.items():
            if hasattr(item, 'uuid') and item.uuid == uuid_str:
                return item
        return None

    def _update_connected_transitions(self, item_moved: QGraphicsItem):
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                if item.start_item == item_moved or item.end_item == item_moved:
                    item.update_path()
            elif isinstance(item, GraphicsHistoryPseudoStateItem):
                if item == item_moved and item.default_history_transition_item:
                    item.default_history_transition_item.update_path()
                elif item.default_target_substate_item == item_moved and item.default_history_transition_item:
                    item.default_history_transition_item.update_path()


    def _update_transitions_for_renamed_state(self, old_name:str, new_name:str):
        # This method primarily updates display labels. UUIDs handle internal linking.
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                # Check if start_item or end_item is a GraphicsStateItem and its name matches
                if item.start_item and isinstance(item.start_item, GraphicsStateItem) and item.start_item.text_label == new_name: # was old_name
                    item.update_path() 
                    item.setToolTip(item.description or item._compose_label_string())
                if item.end_item and isinstance(item.end_item, GraphicsStateItem) and item.end_item.text_label == new_name: # was old_name
                    item.update_path()
                    item.setToolTip(item.description or item._compose_label_string())
        self._log_to_parent("INFO", f"Scene visually updated transitions for renamed state '{old_name}' to '{new_name}'.")
        self.run_all_validations("StateRenamed")
        self.scene_content_changed_for_find.emit()


    def get_state_by_name(self, name: str) -> GraphicsStateItem | None: # Still useful for UI/validation
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name:
                return item
        return None

    def set_dirty(self, dirty=True):
        if self._dirty != dirty:
            self._dirty = dirty
            self.modifiedStatusChanged.emit(dirty)
        if self.parent_window and hasattr(self.parent_window, '_update_save_actions_enable_state'):
             self.parent_window._update_save_actions_enable_state()

    def is_dirty(self): return self._dirty

    def set_mode(self, mode: str):
        old_mode = self.current_mode
        if old_mode == mode: return
        self.current_mode = mode
        self._log_to_parent("INFO", f"Interaction mode changed to: {mode}")
        self.transition_start_item = None
        if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
        if self.views():
            main_view = self.views()[0]
            if hasattr(main_view, '_restore_cursor_to_scene_mode'): main_view._restore_cursor_to_scene_mode()
        for item in self.items():
            movable_flag = mode == "select"
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem)):
                item.setFlag(QGraphicsItem.ItemIsMovable, movable_flag)
        
        parent_handler = self.parent_window
        action_group_name = 'mode_action_group'
        actions_prefix = ''
        
        # Check if parent_window is the SubFSMEditorDialog or MainWindow for correct action group
        if isinstance(parent_handler, QDialog) and parent_handler.windowTitle().startswith("Sub-Machine Editor"):
            action_group_name = 'sub_mode_action_group'; actions_prefix = 'sub_' # Used for SubFSMEditorDialog
        
        if parent_handler and hasattr(parent_handler, action_group_name):
            actions_map = {
                "select": getattr(parent_handler, f'{actions_prefix}select_action' if actions_prefix else 'select_mode_action', None),
                "state": getattr(parent_handler, f'{actions_prefix}state_action' if actions_prefix else 'add_state_mode_action', None),
                "transition": getattr(parent_handler, f'{actions_prefix}transition_action' if actions_prefix else 'add_transition_mode_action', None),
                "comment": getattr(parent_handler, f'{actions_prefix}comment_action' if actions_prefix else 'add_comment_mode_action', None),
                "history_shallow": getattr(parent_handler, f'{actions_prefix}history_shallow_action' if actions_prefix else 'add_history_shallow_mode_action', None),
            }
            action_to_check = actions_map.get(mode)
            if action_to_check and hasattr(action_to_check, 'isChecked') and not action_to_check.isChecked():
                action_to_check.setChecked(True)

    def select_all(self):
        for item in self.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable: item.setSelected(True)

    def _handle_item_moved_visual_update(self, moved_item):
        self._update_connected_transitions(moved_item)

    def _clear_dynamic_guidelines(self):
        if self._horizontal_snap_lines or self._vertical_snap_lines:
            self._horizontal_snap_lines.clear(); self._vertical_snap_lines.clear(); self.update()

    def _mark_item_as_problematic(self, item, problem_description="Validation Issue"):
        if hasattr(item, 'set_problematic_style'):
            item.set_problematic_style(True, problem_description)
            self._problematic_items.add(item)

    def _clear_all_visual_validation_warnings(self):
        for item in list(self._problematic_items):
            if hasattr(item, 'set_problematic_style'): item.set_problematic_style(False)
        self._problematic_items.clear()

    def run_all_validations(self, trigger_source="unknown_source"):
        logger.debug(f"Running all validations, triggered by: {trigger_source}")
        self._clear_all_visual_validation_warnings()
        current_validation_issues = []

        states = [item for item in self.items() if isinstance(item, GraphicsStateItem)]
        transitions = [item for item in self.items() if isinstance(item, GraphicsTransitionItem) and item.start_item is not None and not isinstance(item.start_item, GraphicsHistoryPseudoStateItem)]
        history_items = [item for item in self.items() if isinstance(item, GraphicsHistoryPseudoStateItem)]

        if not states and (transitions or history_items):
            issue_msg = "Diagram has transitions or history pseudo-states but no main states defined."
            current_validation_issues.append((issue_msg, None))
            for t in transitions: self._mark_item_as_problematic(t, "Orphaned Transition (No States)")
            for h in history_items: self._mark_item_as_problematic(h, "Orphaned History (No Parent Superstates)")

        if not states:
            if not current_validation_issues: current_validation_issues.append(("Diagram is empty or has no states.", None))
            self._validation_issues = current_validation_issues
            self.validation_issues_updated.emit(self._validation_issues)
            self.update(); return
        
        initial_states = [s for s in states if s.is_initial]
        if not initial_states:
            current_validation_issues.append(("Missing Initial State: The diagram must have exactly one initial state.", None))
        elif len(initial_states) > 1:
            issue_msg = f"Multiple Initial States: Found {len(initial_states)} initial states ({', '.join([s.text_label for s in initial_states])}). Only one is allowed."
            current_validation_issues.append((issue_msg, None))
            for s_init in initial_states: self._mark_item_as_problematic(s_init, "Multiple Initials")

        for state in states:
            if state.is_final:
                outgoing_transitions = [t for t in transitions if t.start_item == state]
                if outgoing_transitions:
                    issue_msg = f"Invalid Transition from Final State: State '{state.text_label}' is final and cannot have outgoing transitions."
                    current_validation_issues.append((issue_msg, state)); self._mark_item_as_problematic(state, "Final State with Outgoing Transition")
                    for t_out in outgoing_transitions: self._mark_item_as_problematic(t_out, "Transition From Final State")
        
        unreachable_states_set = set()
        if initial_states and len(initial_states) == 1:
            start_node = initial_states[0]; reachable_states_bfs = set(); q = [start_node]; visited_for_reachability = {start_node}
            while q:
                current = q.pop(0); reachable_states_bfs.add(current)
                for t in transitions: 
                    if t.start_item == current and t.end_item and t.end_item not in visited_for_reachability:
                        # Ensure end_item is a GraphicsStateItem for reachability checks (not H-item directly)
                        if isinstance(t.end_item, GraphicsStateItem):
                            q.append(t.end_item); visited_for_reachability.add(t.end_item)
            for s_state in states:
                if s_state not in reachable_states_bfs:
                    unreachable_states_set.add(s_state); issue_msg = f"Unreachable State: State '{s_state.text_label}' cannot be reached from the initial state ('{start_node.text_label}')."
                    current_validation_issues.append((issue_msg, s_state)); self._mark_item_as_problematic(s_state, "Unreachable")
        elif not initial_states:
            for s_state in states:
                unreachable_states_set.add(s_state); issue_msg = f"Unreachable State (No Initial): State '{s_state.text_label}' considered unreachable as no initial state is defined."
                current_validation_issues.append((issue_msg, s_state)); self._mark_item_as_problematic(s_state, "Unreachable (No Initial)")

        for state in states:
            if not state.is_final and state not in unreachable_states_set:
                has_outgoing = any(t.start_item == state for t in transitions)
                is_superstate_with_content_or_history = False
                if state.is_superstate:
                    if (state.sub_fsm_data and state.sub_fsm_data.get('states')) or state.contained_history_pseudo_states:
                        is_superstate_with_content_or_history = True
                if not has_outgoing and not is_superstate_with_content_or_history:
                    issue_msg = f"Dead-End State: Non-final state '{state.text_label}' has no outgoing transitions and is not a superstate with content/history."
                    current_validation_issues.append((issue_msg, state)); self._mark_item_as_problematic(state, "Dead-End State")

        for t in transitions:
            if not t.start_item or not t.end_item: issue_msg = f"Invalid Transition: Transition '{t._compose_label_string()}' has a missing source or target."; current_validation_issues.append((issue_msg, t)); self._mark_item_as_problematic(t, "Invalid Source/Target")
            # Check if items are actually in the current scene's states/history_items lists
            is_start_valid_in_scene = (isinstance(t.start_item, GraphicsStateItem) and t.start_item in states)
            is_end_valid_in_scene = False
            if isinstance(t.end_item, GraphicsStateItem) and t.end_item in states:
                is_end_valid_in_scene = True
            elif isinstance(t.end_item, GraphicsHistoryPseudoStateItem) and t.end_item in history_items:
                 is_end_valid_in_scene = True

            if not is_start_valid_in_scene or not is_end_valid_in_scene:
                 issue_msg = f"Orphaned Transition: Transition '{t._compose_label_string()}' connects to non-existent or invalid states/H-items."; current_validation_issues.append((issue_msg, t)); self._mark_item_as_problematic(t, "Orphaned/Invalid Target")


        for h_item in history_items:
            if not h_item.parent_superstate_item or not isinstance(h_item.parent_superstate_item, GraphicsStateItem) or not h_item.parent_superstate_item.is_superstate:
                msg = f"History '{h_item.text_label}' must be inside a superstate."; current_validation_issues.append((msg, h_item)); self._mark_item_as_problematic(h_item, msg)
            if not h_item.default_target_substate_item:
                parent_name = h_item.parent_superstate_item.text_label if h_item.parent_superstate_item else "None"
                msg = f"History '{h_item.text_label}' in '{parent_name}' is missing a default target sub-state."; current_validation_issues.append((msg, h_item)); self._mark_item_as_problematic(h_item, msg)
            elif h_item.parent_superstate_item and h_item.default_target_substate_item: # Parent and default target exist
                parent_sub_state_uuids = [s.get('uuid') for s in h_item.parent_superstate_item.sub_fsm_data.get('states', []) if s.get('uuid')]
                if h_item.default_target_substate_item.uuid not in parent_sub_state_uuids:
                    msg = f"History '{h_item.text_label}' in '{h_item.parent_superstate_item.text_label}': Default target '{h_item.default_target_substate_item.text_label}' (UUID: {h_item.default_target_substate_item.uuid}) is not a direct sub-state of this superstate."
                    current_validation_issues.append((msg, h_item)); self._mark_item_as_problematic(h_item, msg)

            if h_item.parent_superstate_item:
                count_same_type = sum(1 for other_h in h_item.parent_superstate_item.contained_history_pseudo_states if other_h.history_type == h_item.history_type)
                if count_same_type > 1:
                    msg = f"Superstate '{h_item.parent_superstate_item.text_label}' has multiple '{h_item.history_type}' history pseudo-states. Only one of each type (H, H*) allowed."
                    current_validation_issues.append((msg, h_item)); self._mark_item_as_problematic(h_item, msg)
        
        self._validation_issues = current_validation_issues; self.validation_issues_updated.emit(self._validation_issues); self.update()
        if self._validation_issues: logger.info(f"Validation found {len(self._validation_issues)} issues (Trigger: {trigger_source}).")
        else: logger.info(f"Validation passed with no issues (Trigger: {trigger_source}).")

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos()
        items_at_pos = self.items(pos)
        top_item_at_pos = next((item for item in items_at_pos if isinstance(item, (GraphicsStateItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem))), None)
        if not top_item_at_pos: top_item_at_pos = next((item for item in items_at_pos if isinstance(item, GraphicsTransitionItem)), None)
        if not top_item_at_pos and items_at_pos: top_item_at_pos = items_at_pos[0]

        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size - 60; grid_y = round(pos.y() / self.grid_size) * self.grid_size - 30
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type="State")
            elif self.current_mode == "comment":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size; grid_y = round(pos.y() / self.grid_size) * self.grid_size
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type="Comment")
            elif self.current_mode == "history_shallow":
                if isinstance(top_item_at_pos, GraphicsStateItem) and top_item_at_pos.is_superstate:
                    relative_pos = top_item_at_pos.mapFromScene(pos)
                    self._add_item_interactive(relative_pos, item_type="HistoryShallow", parent_item=top_item_at_pos)
                else:
                    QMessageBox.information(self.parent_window, "Invalid Placement", "Shallow History (H) pseudo-states can only be placed inside a Superstate.")
                    self.set_mode("select")
            elif self.current_mode == "transition":
                if isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsHistoryPseudoStateItem)):
                    self._handle_transition_click(top_item_at_pos, pos)
                else:
                    if self.transition_start_item: self._log_to_parent("INFO", "Transition drawing cancelled.")
                    self.transition_start_item = None
                    if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
            else: # Select mode
                self._mouse_press_items_positions.clear()
                selected_items_list = self.selectedItems()
                is_target_movable = top_item_at_pos and top_item_at_pos.flags() & QGraphicsItem.ItemIsMovable

                if top_item_at_pos and isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsCommentItem, GraphicsTransitionItem, GraphicsHistoryPseudoStateItem)) and \
                   is_target_movable and not top_item_at_pos.isSelected() and \
                   not (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                    self.clearSelection(); top_item_at_pos.setSelected(True); selected_items_list = [top_item_at_pos]

                is_transition_cp_drag = isinstance(top_item_at_pos, GraphicsTransitionItem) and hasattr(top_item_at_pos, '_dragging_control_point') and top_item_at_pos._dragging_control_point

                if not is_transition_cp_drag:
                    for item_to_process in selected_items_list:
                        if item_to_process.flags() & QGraphicsItem.ItemIsMovable and not (isinstance(item_to_process, GraphicsHistoryPseudoStateItem) and not item_to_process.parentItem()): # H-items are movable by parent or directly if not parented (error case)
                             self._mouse_press_items_positions[item_to_process] = item_to_process.pos()
                super().mousePressEvent(event)
        elif event.button() == Qt.RightButton: pass
        else: super().mousePressEvent(event)

    # ... (contextMenuEvent, mouseMoveEvent, _calculate_object_snap_position, mouseReleaseEvent, mouseDoubleClickEvent, _show_context_menu, edit_item_properties, _add_item_interactive, _handle_transition_click, keyPressEvent, delete_selected_items, dragEnterEvent, dragMoveEvent, dropEvent, _generate_unique_state_name, drawBackground, drawForeground remain structurally similar)
    # Key methods like load_diagram_data, copy, paste, add_template_to_scene are the main ones with UUID logic.
    
    # ... (drawBackground, drawForeground methods remain the same)

    def _generate_unique_state_name(self, base_name: str) -> str: # Stays same
        if not self.get_state_by_name(base_name): return base_name
        match = re.match(r"^(.*?)_Copy(\d+)$", base_name)
        if match: prefix = match.group(1); num = int(match.group(2))
        else: prefix = base_name; num = 0
        base_match_num = re.match(r"^(.*?)(\d+)$", base_name)
        if not match and base_match_num:
            prefix_base = base_match_num.group(1); num_base = int(base_match_num.group(2)); next_num_base = num_base + 1
            while self.get_state_by_name(f"{prefix_base}{next_num_base}"): next_num_base += 1
            return f"{prefix_base}{next_num_base}"
        else:
            next_num_copy = num + 1
            while self.get_state_by_name(f"{prefix}_Copy{next_num_copy}"): next_num_copy += 1
            return f"{prefix}_Copy{next_num_copy}"

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        view_rect = self.views()[0].viewport().rect() if self.views() else rect
        visible_scene_rect = self.views()[0].mapToScene(view_rect).boundingRect() if self.views() else rect
        left = int(visible_scene_rect.left() / self.grid_size) * self.grid_size - self.grid_size; right = int(visible_scene_rect.right() / self.grid_size) * self.grid_size + self.grid_size
        top = int(visible_scene_rect.top() / self.grid_size) * self.grid_size - self.grid_size; bottom = int(visible_scene_rect.bottom() / self.grid_size) * self.grid_size + self.grid_size
        painter.setPen(self.grid_pen_light)
        for x in range(left, right, self.grid_size):
            if x % (self.grid_size * 5) != 0: painter.drawLine(x, top, x, bottom)
        for y in range(top, bottom, self.grid_size):
            if y % (self.grid_size * 5) != 0: painter.drawLine(left, y, right, y)
        major_grid_size = self.grid_size * 5
        first_major_left = left - (left % major_grid_size) if left >=0 else left - (left % major_grid_size) - major_grid_size
        first_major_top = top - (top % major_grid_size) if top >= 0 else top - (top % major_grid_size) - major_grid_size
        painter.setPen(self.grid_pen_dark)
        for x in range(first_major_left, right, major_grid_size): painter.drawLine(x, top, x, bottom)
        for y in range(first_major_top, bottom, major_grid_size): painter.drawLine(left, y, right, y)

    def drawForeground(self, painter: QPainter, rect: QRectF):
        super().drawForeground(painter, rect)
        if self._show_dynamic_snap_guidelines:
            pen = QPen(GUIDELINE_PEN_COLOR, GUIDELINE_PEN_WIDTH, Qt.DashLine); painter.setPen(pen)
            for line in self._horizontal_snap_lines: painter.drawLine(line)
            for line in self._vertical_snap_lines: painter.drawLine(line)

# ZoomableView class remains the same
class ZoomableView(QGraphicsView):
    zoomChanged = pyqtSignal(float)
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag); self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.zoom_level_steps = 0; self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._is_panning_with_space = False; self._is_panning_with_mouse_button = False; self._last_pan_point = QPoint()
        self._emit_current_zoom()
    def _emit_current_zoom(self): self.zoomChanged.emit(self.transform().m11())
    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y(); factor = 1.12 if delta > 0 else 1 / 1.12; new_zoom_level_steps = self.zoom_level_steps + (1 if delta > 0 else -1)
            if -15 <= new_zoom_level_steps <= 15: self.scale(factor, factor); self.zoom_level_steps = new_zoom_level_steps; self._emit_current_zoom()
            event.accept()
        else: super().wheelEvent(event)
    def zoom_in(self):
        factor = 1.12; new_zoom_level_steps = self.zoom_level_steps + 1
        if new_zoom_level_steps <= 15: self.scale(factor, factor); self.zoom_level_steps = new_zoom_level_steps; self._emit_current_zoom()
    def zoom_out(self):
        factor = 1 / 1.12; new_zoom_level_steps = self.zoom_level_steps - 1
        if new_zoom_level_steps >= -15: self.scale(factor, factor); self.zoom_level_steps = new_zoom_level_steps; self._emit_current_zoom()
    def reset_view_and_zoom(self):
        self.resetTransform(); self.zoom_level_steps = 0
        if self.scene():
            content_rect = self.scene().itemsBoundingRect()
            if not content_rect.isEmpty(): self.centerOn(content_rect.center())
            elif self.scene().sceneRect(): self.centerOn(self.scene().sceneRect().center())
        self._emit_current_zoom()
    def fitInView(self, rect: QRectF, aspectRadioMode: Qt.AspectRatioMode = Qt.IgnoreAspectRatio): super().fitInView(rect, aspectRadioMode); self._emit_current_zoom()
    def setTransform(self, matrix: QTransform, combine: bool = False): super().setTransform(matrix, combine); self._emit_current_zoom()
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not self._is_panning_with_space and not event.isAutoRepeat(): self._is_panning_with_space = True; self._last_pan_point = self.mapFromGlobal(QCursor.pos()); self.setCursor(Qt.OpenHandCursor); event.accept()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal: self.zoom_in()
        elif event.key() == Qt.Key_Minus: self.zoom_out()
        elif event.key() == Qt.Key_0 or event.key() == Qt.Key_Asterisk: self.reset_view_and_zoom()
        else: super().keyPressEvent(event)
    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = False
            if not self._is_panning_with_mouse_button: self._restore_cursor_to_scene_mode()
            event.accept()
        else: super().keyReleaseEvent(event)
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton or (self._is_panning_with_space and event.button() == Qt.LeftButton):
            self._last_pan_point = event.pos(); self.setCursor(Qt.ClosedHandCursor); self._is_panning_with_mouse_button = True; event.accept()
        else: self._is_panning_with_mouse_button = False; super().mousePressEvent(event)
    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button:
            delta_view = event.pos() - self._last_pan_point; self._last_pan_point = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta_view.x()); self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta_view.y())
            event.accept()
        else: super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button and (event.button() == Qt.MiddleButton or (self._is_panning_with_space and event.button() == Qt.LeftButton)):
            self._is_panning_with_mouse_button = False
            if self._is_panning_with_space: self.setCursor(Qt.OpenHandCursor)
            else: self._restore_cursor_to_scene_mode()
            event.accept()
        else: super().mouseReleaseEvent(event)
    def _restore_cursor_to_scene_mode(self):
        current_scene_mode = self.scene().current_mode if self.scene() and hasattr(self.scene(), 'current_mode') else "select"
        if current_scene_mode == "select": self.setCursor(Qt.ArrowCursor)
        elif current_scene_mode in ["state", "comment", "history_shallow", "history_deep"]: self.setCursor(Qt.CrossCursor)
        elif current_scene_mode == "transition": self.setCursor(Qt.PointingHandCursor)
        else: self.setCursor(Qt.ArrowCursor)
    def zoom_to_rect(self, target_rect: QRectF, padding_factor: float = 0.1):
        if target_rect.isNull() or not self.scene(): return
        width_padding = target_rect.width() * padding_factor; height_padding = target_rect.height() * padding_factor
        padded_rect = target_rect.adjusted(-width_padding, -height_padding, width_padding, height_padding)
        self.fitInView(padded_rect, Qt.KeepAspectRatio)
    def zoom_to_selection(self):
        if not self.scene() or not self.scene().selectedItems(): return
        selection_rect = QRectF(); first_item = True
        for item in self.scene().selectedItems():
            if first_item: selection_rect = item.sceneBoundingRect(); first_item = False
            else: selection_rect = selection_rect.united(item.sceneBoundingRect())
        if not selection_rect.isEmpty(): self.zoom_to_rect(selection_rect)
    def fit_diagram_in_view(self):
        if not self.scene(): return
        items_rect = self.scene().itemsBoundingRect()
        if not items_rect.isEmpty(): self.zoom_to_rect(items_rect)
        else: self.zoom_to_rect(self.scene().sceneRect())
