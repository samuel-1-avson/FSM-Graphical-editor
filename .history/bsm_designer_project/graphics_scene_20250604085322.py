# FILE: bsm_designer_project/graphics_scene.py

import sys
import os
import json
import logging
import math
import re
import uuid # <--- IMPORT UUID

from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsLineItem,
    QMenu, QMessageBox, QDialog, QStyle, QGraphicsSceneMouseEvent,
    QGraphicsSceneDragDropEvent, QApplication, QGraphicsSceneContextMenuEvent
)
# ... (other imports remain the same)
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

        #self.item_moved.connect(self._handle_item_moved_visual_update)

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

    def get_item_by_uuid(self, uuid_str: str) -> QGraphicsItem | None: # <--- IMPLEMENTED METHOD
        if not uuid_str:
            return None
        for item in self.items():
            if hasattr(item, 'uuid') and item.uuid == uuid_str:
                return item
        return None

    def _update_connected_transitions(self, item_moved: QGraphicsItem):
        # ... (method remains the same, uses item references)
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
                if item.start_item and isinstance(item.start_item, GraphicsStateItem) and item.start_item.text_label == new_name: # was old_name
                    item.update_path() # Path might change if state size changes slightly with name
                    item.setToolTip(item.description or item._compose_label_string())
                if item.end_item and isinstance(item.end_item, GraphicsStateItem) and item.end_item.text_label == new_name: # was old_name
                    item.update_path()
                    item.setToolTip(item.description or item._compose_label_string())
        self._log_to_parent("INFO", f"Scene visually updated transitions for renamed state '{old_name}' to '{new_name}'.")
        self.run_all_validations("StateRenamed") # Re-validate
        self.scene_content_changed_for_find.emit() # Content for find dialog might have changed


    # ... (get_state_by_name, get_history_pseudo_state_by_id, set_dirty, is_dirty, set_mode, select_all, _handle_item_moved_visual_update, _clear_dynamic_guidelines, _mark_item_as_problematic, _clear_all_visual_validation_warnings, run_all_validations, mousePressEvent, contextMenuEvent, mouseMoveEvent, _calculate_object_snap_position, mouseReleaseEvent, mouseDoubleClickEvent, _show_context_menu, edit_item_properties, _add_item_interactive, _handle_transition_click, keyPressEvent, copy_selected_items remain largely the same, but internal creation/linking might use UUIDs where appropriate, handled by item constructors and commands)

    def get_state_by_name(self, name: str) -> GraphicsStateItem | None:
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name:
                return item
        return None

    def get_history_pseudo_state_by_id(self, h_id: str) -> GraphicsHistoryPseudoStateItem | None:
        # This was for a custom ID, now we use UUID. get_item_by_uuid replaces this.
        # If h_id was a name-based construction, this logic needs to adapt or be deprecated.
        # For now, let's assume get_item_by_uuid is preferred.
        logger.warning("get_history_pseudo_state_by_id is deprecated, use get_item_by_uuid.")
        return self.get_item_by_uuid(h_id) # Redirect if still called

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
        if parent_handler and hasattr(parent_handler, 'sub_mode_action_group') and isinstance(parent_handler, QDialog): # Check if parent is SubFSMEditorDialog
            action_group_name = 'sub_mode_action_group'; actions_prefix = 'sub_'

        if parent_handler and hasattr(parent_handler, action_group_name):
            actions_map = {
                "select": getattr(parent_handler, f'{actions_prefix}select_action' if actions_prefix else 'select_mode_action', None),
                "state": getattr(parent_handler, f'{actions_prefix}state_action' if actions_prefix else 'add_state_mode_action', None),
                "transition": getattr(parent_handler, f'{actions_prefix}transition_action' if actions_prefix else 'add_transition_mode_action', None),
                "comment": getattr(parent_handler, f'{actions_prefix}comment_action' if actions_prefix else 'add_comment_mode_action', None),
                "history_shallow": getattr(parent_handler, f'{actions_prefix}history_shallow_action' if actions_prefix else 'add_history_shallow_mode_action', None), # Assuming similar naming for sub-editor
            }
            action_to_check = actions_map.get(mode)
            if action_to_check and hasattr(action_to_check, 'isChecked') and not action_to_check.isChecked():
                action_to_check.setChecked(True)

    def select_all(self):
        for item in self.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable: item.setSelected(True)

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
            elif t.start_item not in states or t.end_item not in states: issue_msg = f"Orphaned Transition: Transition '{t._compose_label_string()}' connects to non-existent states."; current_validation_issues.append((issue_msg, t)); self._mark_item_as_problematic(t, "Orphaned")

        for h_item in history_items:
            if not h_item.parent_superstate_item or not isinstance(h_item.parent_superstate_item, GraphicsStateItem) or not h_item.parent_superstate_item.is_superstate:
                msg = f"History '{h_item.text_label}' must be inside a superstate."; current_validation_issues.append((msg, h_item)); self._mark_item_as_problematic(h_item, msg)
            if not h_item.default_target_substate_item:
                parent_name = h_item.parent_superstate_item.text_label if h_item.parent_superstate_item else "None"
                msg = f"History '{h_item.text_label}' in '{parent_name}' is missing a default target sub-state."; current_validation_issues.append((msg, h_item)); self._mark_item_as_problematic(h_item, msg)
            elif h_item.parent_superstate_item:
                parent_sub_state_names = [s['name'] for s in h_item.parent_superstate_item.sub_fsm_data.get('states', [])]
                if h_item.default_target_substate_item.text_label not in parent_sub_state_names:
                    msg = f"History '{h_item.text_label}' in '{h_item.parent_superstate_item.text_label}': Default target '{h_item.default_target_substate_item.text_label}' is not a direct sub-state."
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
                if isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsHistoryPseudoStateItem)): # H-item can be source for default only
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
                        if item_to_process.flags() & QGraphicsItem.ItemIsMovable and not isinstance(item_to_process, GraphicsHistoryPseudoStateItem): # H-item handled differently by its parent
                             self._mouse_press_items_positions[item_to_process] = item_to_process.pos()
                super().mousePressEvent(event)
        elif event.button() == Qt.RightButton: pass # Handled by contextMenuEvent
        else: super().mousePressEvent(event)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        # Check if the parent is SubFSMEditorDialog to potentially disable some actions
        is_sub_editor_context = isinstance(self.parent_window, QDialog) and self.parent_window.windowTitle().startswith("Sub-Machine Editor")

        item_at_pos = self.itemAt(event.scenePos(), self.views()[0].transform() if self.views() else QTransform())
        if item_at_pos and isinstance(item_at_pos, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem)):
            if self.parent_window and hasattr(self.parent_window, '_show_context_menu_for_item_from_scene'):
                self.parent_window._show_context_menu_for_item_from_scene(item_at_pos, event.screenPos()); event.accept(); return
            elif hasattr(self, '_show_context_menu'): # Fallback for DiagramScene directly in SubFSMEditor
                self._show_context_menu(item_at_pos, event.screenPos()); event.accept(); return
        elif not item_at_pos: # Click on empty space
            menu = QMenu(); add_state_action = menu.addAction(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"), "Add State Here")
            add_history_shallow_action = menu.addAction(get_standard_icon(QStyle.SP_FileDialogDetailedView, "H"), "Add Shallow History (H) Here")
            add_history_shallow_action.setToolTip("To add, ensure 'Add Shallow History (H)' mode is active and then click inside an existing Superstate.")
            add_history_shallow_action.setEnabled(False) # H-items should be added via toolbar/drag into superstate, not empty space.
            add_comment_action = menu.addAction(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"), "Add Comment Here")
            add_fsm_from_ai_action = None
            if not is_sub_editor_context and self.parent_window and hasattr(self.parent_window, 'ai_chat_ui_manager'): # Only for main window
                 menu.addSeparator(); add_fsm_from_ai_action = menu.addAction(get_standard_icon(QStyle.SP_ArrowRight, "AIGen"), "Generate FSM from Description (AI)...")
            action = menu.exec_(event.screenPos()); click_pos = event.scenePos()
            if action == add_state_action:
                grid_x = round(click_pos.x() / self.grid_size) * self.grid_size - 60; grid_y = round(click_pos.y() / self.grid_size) * self.grid_size - 30
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type="State")
            elif action == add_comment_action:
                grid_x = round(click_pos.x() / self.grid_size) * self.grid_size; grid_y = round(click_pos.y() / self.grid_size) * self.grid_size
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type="Comment")
            elif add_fsm_from_ai_action and action == add_fsm_from_ai_action:
                if not is_sub_editor_context and self.parent_window and hasattr(self.parent_window.ai_chat_ui_manager, 'on_ask_ai_to_generate_fsm'):
                    self.parent_window.ai_chat_ui_manager.on_ask_ai_to_generate_fsm()
            event.accept()
        else: super().contextMenuEvent(event)


    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        self._clear_dynamic_guidelines()
        if self.current_mode == "select" and event.buttons() & Qt.LeftButton and self._mouse_press_items_positions:
            dragged_items = list(self._mouse_press_items_positions.keys())
            if dragged_items:
                primary_dragged_item = dragged_items[0]; original_item_press_pos = self._mouse_press_items_positions.get(primary_dragged_item)
                original_mouse_press_scene_pos = event.buttonDownScenePos(Qt.LeftButton); current_mouse_scene_pos = event.scenePos()
                drag_vector = current_mouse_scene_pos - original_mouse_press_scene_pos
                if original_item_press_pos is not None:
                    potential_item_origin = original_item_press_pos + drag_vector; potential_sbr = primary_dragged_item.boundingRect().translated(potential_item_origin)
                    snap_points_x = {'left': potential_sbr.left(), 'center': potential_sbr.center().x(), 'right': potential_sbr.right()}; snap_points_y = {'top': potential_sbr.top(), 'center': potential_sbr.center().y(), 'bottom': potential_sbr.bottom()}
                    visible_rect = self.views()[0].mapToScene(self.views()[0].viewport().rect()).boundingRect() if self.views() else self.sceneRect()
                    for other_item in self.items():
                        if other_item in dragged_items or not isinstance(other_item, (GraphicsStateItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem)): continue # Allow H-item for snapping
                        other_sbr = other_item.sceneBoundingRect(); other_align_x = [other_sbr.left(), other_sbr.center().x(), other_sbr.right()]
                        for drag_x in snap_points_x.values():
                            for static_x in other_align_x:
                                if abs(drag_x - static_x) <= SNAP_THRESHOLD_PIXELS: line = QLineF(static_x, visible_rect.top(), static_x, visible_rect.bottom()); self._vertical_snap_lines.append(line); break
                        other_align_y = [other_sbr.top(), other_sbr.center().y(), other_sbr.bottom()]
                        for drag_y in snap_points_y.values():
                            for static_y in other_align_y:
                                if abs(drag_y - static_y) <= SNAP_THRESHOLD_PIXELS: line = QLineF(visible_rect.left(), static_y, visible_rect.right(), static_y); self._horizontal_snap_lines.append(line); break
                    if self._horizontal_snap_lines or self._vertical_snap_lines: self.update()
        elif self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, event.scenePos()))
        super().mouseMoveEvent(event)

    def _calculate_object_snap_position(self, moving_item: QGraphicsItem, candidate_item_origin_pos: QPointF) -> QPointF:
        if not self.snap_to_objects_enabled: return candidate_item_origin_pos
        current_best_x = candidate_item_origin_pos.x(); current_best_y = candidate_item_origin_pos.y()
        min_offset_x = SNAP_THRESHOLD_PIXELS + 1; min_offset_y = SNAP_THRESHOLD_PIXELS + 1
        moving_item_br = moving_item.boundingRect(); candidate_moving_sbr = moving_item_br.translated(candidate_item_origin_pos)
        moving_item_refs_x = {'left': candidate_moving_sbr.left(),'center': candidate_moving_sbr.center().x(),'right': candidate_moving_sbr.right()}
        moving_item_refs_y = {'top': candidate_moving_sbr.top(),'center': candidate_moving_sbr.center().y(),'bottom': candidate_moving_sbr.bottom()}
        for other_item in self.items():
            if other_item == moving_item or not isinstance(other_item, (GraphicsStateItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem)): continue
            other_sbr = other_item.sceneBoundingRect()
            other_item_snap_points_x = [other_sbr.left(), other_sbr.center().x(), other_sbr.right()]
            for moving_x_val in moving_item_refs_x.values():
                for other_x_val in other_item_snap_points_x:
                    diff_x = other_x_val - moving_x_val
                    if abs(diff_x) < min_offset_x: min_offset_x = abs(diff_x); current_best_x = candidate_item_origin_pos.x() + diff_x
            other_item_snap_points_y = [other_sbr.top(), other_sbr.center().y(), other_sbr.bottom()]
            for moving_y_val in moving_item_refs_y.values():
                for other_y_val in other_item_snap_points_y:
                    diff_y = other_y_val - moving_y_val
                    if abs(diff_y) < min_offset_y: min_offset_y = abs(diff_y); current_best_y = candidate_item_origin_pos.y() + diff_y
        final_x = current_best_x if min_offset_x <= SNAP_THRESHOLD_PIXELS else candidate_item_origin_pos.x()
        final_y = current_best_y if min_offset_y <= SNAP_THRESHOLD_PIXELS else candidate_item_origin_pos.y()
        return QPointF(final_x, final_y)


    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        super().mouseReleaseEvent(event) # Call super first to handle selection changes etc.
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            if self._mouse_press_items_positions:
                moved_items_data_for_command = []
                for item, old_pos in self._mouse_press_items_positions.items():
                    if isinstance(item, GraphicsHistoryPseudoStateItem) and item.parentItem():
                        # For H-items, positions are relative to parent. The itemChange handles constraints.
                        # The final position is already set by QGraphicsItem's move.
                        # We just need to record if it significantly moved from its original relative pos.
                        current_item_pos_after_drag = item.pos()
                        if (current_item_pos_after_drag - old_pos).manhattanLength() > 0.1 :
                            moved_items_data_for_command.append((item, old_pos, current_item_pos_after_drag))
                    else: # Regular items (States, Comments)
                        current_item_pos_after_drag = item.pos()
                        final_snapped_pos = current_item_pos_after_drag # Start with current
                        if self.snap_to_objects_enabled:
                            final_snapped_pos = self._calculate_object_snap_position(item, final_snapped_pos) # Snap based on current
                        if self.snap_to_grid_enabled:
                            grid_snapped_x = round(final_snapped_pos.x() / self.grid_size) * self.grid_size
                            grid_snapped_y = round(final_snapped_pos.y() / self.grid_size) * self.grid_size
                            final_snapped_pos = QPointF(grid_snapped_x, grid_snapped_y)

                        if (final_snapped_pos - old_pos).manhattanLength() > 0.1:
                            item.setPos(final_snapped_pos) # Apply final snapped position
                            moved_items_data_for_command.append((item, old_pos, final_snapped_pos))
                        elif (current_item_pos_after_drag - old_pos).manhattanLength() > 0.1 and \
                             (final_snapped_pos - current_item_pos_after_drag).manhattanLength() < 0.1:
                             # It moved, but snapping didn't change it further from the dragged pos
                             moved_items_data_for_command.append((item, old_pos, current_item_pos_after_drag))

                if moved_items_data_for_command:
                    cmd = MoveItemsCommand(moved_items_data_for_command, "Move Items")
                    self.undo_stack.push(cmd)
                    self.set_dirty(True)
                    self.run_all_validations("MoveItemsCommand_End")
                self._mouse_press_items_positions.clear()
        self._clear_dynamic_guidelines()

    # ... (mouseDoubleClickEvent, _show_context_menu, edit_item_properties, _add_item_interactive, _handle_transition_click, keyPressEvent, copy_selected_items remain)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        items_at_pos = self.items(event.scenePos())
        item_to_edit = next((item for item in items_at_pos if isinstance(item, (GraphicsStateItem, GraphicsCommentItem, GraphicsTransitionItem, GraphicsHistoryPseudoStateItem))), None)
        if item_to_edit and hasattr(item_to_edit, '_is_editing_inline') and item_to_edit._is_editing_inline: event.accept(); return
        if item_to_edit and isinstance(item_to_edit, (GraphicsStateItem, GraphicsCommentItem, GraphicsTransitionItem, GraphicsHistoryPseudoStateItem)):
            self.edit_item_properties(item_to_edit); event.accept(); return
        super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, item, global_pos): # For sub-editor context
        menu = QMenu(); edit_action = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        if isinstance(item, GraphicsStateItem) and item.is_superstate: pass # No specific change for sub-editor context menu
        delete_action = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")
        action = menu.exec_(global_pos)
        if action == edit_action: self.edit_item_properties(item)
        elif action == delete_action:
            if not item.isSelected(): self.clearSelection(); item.setSelected(True)
            self.delete_selected_items()

    def edit_item_properties(self, item): # This should be fine
        from dialogs import StatePropertiesDialog, TransitionPropertiesDialog, CommentPropertiesDialog, HistoryPseudoStatePropertiesDialog
        dialog_executed_and_accepted = False; new_props_from_dialog = None; DialogType = None
        old_props = item.get_data() if hasattr(item, 'get_data') else {}
        if isinstance(item, GraphicsStateItem): DialogType = StatePropertiesDialog
        elif isinstance(item, GraphicsTransitionItem): DialogType = TransitionPropertiesDialog
        elif isinstance(item, GraphicsCommentItem): DialogType = CommentPropertiesDialog
        elif isinstance(item, GraphicsHistoryPseudoStateItem): DialogType = HistoryPseudoStatePropertiesDialog
        else: return
        dialog_parent = self.parent_window
        if self.parent_window and hasattr(self.parent_window, 'sub_mode_action_group'): # Check if it's sub-editor
            pass # parent_window is already the SubFSMEditorDialog
        elif self.parent_window and self.parent_window.__class__.__name__ == "MainWindow": pass
        elif self.views(): dialog_parent = self.views()[0]
        else: dialog_parent = None

        if DialogType == StatePropertiesDialog: dialog = DialogType(parent=dialog_parent, current_properties=old_props, is_new_state=False, scene_ref=self)
        elif DialogType == HistoryPseudoStatePropertiesDialog: dialog = DialogType(parent=dialog_parent, current_properties=old_props, parent_superstate_item=item.parent_superstate_item)
        else: dialog = DialogType(parent=dialog_parent, current_properties=old_props)

        if dialog.exec() == QDialog.Accepted:
            dialog_executed_and_accepted = True; new_props_from_dialog = dialog.get_properties()
            if isinstance(item, GraphicsStateItem):
                current_new_name = new_props_from_dialog.get('name')
                existing_state_with_new_name = self.get_state_by_name(current_new_name)
                if current_new_name != old_props.get('name') and existing_state_with_new_name and existing_state_with_new_name != item:
                    QMessageBox.warning(dialog_parent, "Duplicate Name", f"A state named '{current_new_name}' already exists."); return
        if dialog_executed_and_accepted and new_props_from_dialog is not None:
            final_new_props = old_props.copy(); final_new_props.update(new_props_from_dialog)
            if final_new_props == old_props: self._log_to_parent("INFO", "Properties unchanged."); return
            cmd = EditItemPropertiesCommand(item, old_props, final_new_props, f"Edit {type(item).__name__} Properties")
            self.undo_stack.push(cmd) # This calls redo, which applies properties and validation
            item_name_for_log = final_new_props.get('name', final_new_props.get('event', final_new_props.get('text', item.uuid)))
            if isinstance(item, GraphicsHistoryPseudoStateItem): item_name_for_log = f"History ({final_new_props.get('type', 'H')}) ({item.uuid})"
            self._log_to_parent("INFO", f"Properties updated for: {item_name_for_log}")


    def _add_item_interactive(self, pos: QPointF, item_type: str, name_prefix:str="Item", initial_data:dict=None, parent_item:GraphicsStateItem=None):
        from dialogs import StatePropertiesDialog, CommentPropertiesDialog, HistoryPseudoStatePropertiesDialog
        current_item = None; initial_data = initial_data or {}
        dialog_parent = self.parent_window # Correctly gets main window or SubFSMEditorDialog
        # New items get a fresh UUID from their constructor by default
        # We don't pass item_uuid here, it will be auto-generated.
        if item_type == "State":
            i = 1; base_name = name_prefix if name_prefix != "Item" else "State"; default_name = f"{base_name}{i}"
            while self.get_state_by_name(default_name): i += 1; default_name = f"{base_name}{i}"
            initial_dialog_props = {'name': default_name, 'is_initial': initial_data.get('is_initial', False), 'is_final': initial_data.get('is_final', False), 'color': initial_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG), 'action_language': initial_data.get('action_language', DEFAULT_EXECUTION_ENV),'entry_action':"", 'during_action':"", 'exit_action':"", 'description':"", 'is_superstate': False, 'sub_fsm_data': {'states': [], 'transitions': [], 'comments': []}}
            props_dialog = StatePropertiesDialog(dialog_parent, current_properties=initial_dialog_props, is_new_state=True, scene_ref=self)
            if props_dialog.exec() == QDialog.Accepted:
                final_props = props_dialog.get_properties()
                if self.get_state_by_name(final_props['name']) and final_props['name'] != default_name: QMessageBox.warning(dialog_parent, "Duplicate Name", f"A state named '{final_props['name']}' already exists.")
                else: current_item = GraphicsStateItem(pos.x(), pos.y(), 120, 60, final_props['name'], final_props['is_initial'], final_props['is_final'], final_props.get('color'), final_props.get('entry_action',""), final_props.get('during_action',""), final_props.get('exit_action',""), final_props.get('description',""), final_props.get('is_superstate', False), final_props.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}), action_language=final_props.get('action_language', DEFAULT_EXECUTION_ENV))
                if current_item and self.parent_window and hasattr(self.parent_window, 'connect_state_item_signals'):
                    self.parent_window.connect_state_item_signals(current_item)
            if self.current_mode == "state": self.set_mode("select")
            if not current_item: return
        elif item_type == "HistoryShallow" or item_type == "HistoryDeep":
            if not parent_item or not parent_item.is_superstate:
                QMessageBox.warning(dialog_parent, "Invalid Parent", "History pseudo-states must be placed inside a Superstate.")
                self.set_mode("select"); return
            history_type_str = "shallow" if item_type == "HistoryShallow" else "deep"
            for child_h in parent_item.contained_history_pseudo_states:
                if child_h.history_type == history_type_str:
                    QMessageBox.warning(dialog_parent, "Duplicate History Type", f"Superstate '{parent_item.text_label}' already has a '{history_type_str}' history pseudo-state.")
                    self.set_mode("select"); return
            initial_h_props = {'type': history_type_str, 'parent_superstate_name': parent_item.text_label, 'default_target_substate_name': None, 'x_relative': pos.x(), 'y_relative': pos.y()}
            h_props_dialog = HistoryPseudoStatePropertiesDialog(dialog_parent, current_properties=initial_h_props, parent_superstate_item=parent_item)
            if h_props_dialog.exec() == QDialog.Accepted:
                final_h_props = h_props_dialog.get_properties()
                default_target_item = self.get_state_by_name(final_h_props.get('default_target_substate_name')) if final_h_props.get('default_target_substate_name') else None
                current_item = GraphicsHistoryPseudoStateItem(pos.x(), pos.y(), parent_superstate_item=parent_item, default_target_substate_item=default_target_item, history_type=history_type_str)
            if self.current_mode.startswith("history"): self.set_mode("select")
            if not current_item: return
        elif item_type == "Comment":
            initial_text = initial_data.get('text', "Comment" if name_prefix == "Item" else name_prefix)
            comment_props_dialog = CommentPropertiesDialog(dialog_parent, {'text': initial_text})
            if comment_props_dialog.exec() == QDialog.Accepted:
                final_comment_props = comment_props_dialog.get_properties()
                if final_comment_props['text']: current_item = GraphicsCommentItem(pos.x(), pos.y(), final_comment_props['text'])
                else: self.set_mode("select" if self.current_mode == "comment" else self.current_mode); return
            else: self.set_mode("select" if self.current_mode == "comment" else self.current_mode); return
        else: self._log_to_parent("WARNING", f"Unknown item type for addition: {item_type}"); return

        if current_item:
            cmd = AddItemCommand(self, current_item, f"Add {item_type}")
            self.undo_stack.push(cmd)
            log_name = current_item.uuid # Log with UUID for clarity
            pos_log = f"({pos.x():.0f},{pos.y():.0f})"
            if parent_item: pos_log += f" relative to '{parent_item.text_label}' (UUID: {parent_item.uuid})"
            self._log_to_parent("INFO", f"Added {item_type}: '{log_name}' at {pos_log}")

    def _handle_transition_click(self, clicked_item: QGraphicsItem, click_pos: QPointF): #Mostly fine, uses item refs
        from dialogs import TransitionPropertiesDialog
        dialog_parent = self.parent_window
        if hasattr(self.parent_window, 'sub_mode_action_group'): pass # Handled
        elif self.parent_window and self.parent_window.__class__.__name__ == "MainWindow": pass
        elif self.views(): dialog_parent = self.views()[0]
        else: dialog_parent = None

        if isinstance(clicked_item, GraphicsHistoryPseudoStateItem) and self.transition_start_item is None:
             QMessageBox.information(self.parent_window, "Invalid Transition Start", "Regular transitions cannot start from a History pseudo-state. It has an automatic default transition.")
             self.set_mode("select"); return

        if not self.transition_start_item:
            if not isinstance(clicked_item, GraphicsStateItem): # Can only start from regular state
                QMessageBox.information(self.parent_window, "Invalid Start", "Transitions must start from a regular State.")
                return
            self.transition_start_item = clicked_item
            if not self._temp_transition_line: self._temp_transition_line = QGraphicsLineItem(); self._temp_transition_line.setPen(QPen(QColor(COLOR_ACCENT_PRIMARY), 1.8, Qt.DashLine)); self.addItem(self._temp_transition_line)
            center_start = self.transition_start_item.sceneBoundingRect().center(); self._temp_transition_line.setLine(QLineF(center_start, click_pos))
            self._log_to_parent("INFO", f"Transition started from: {getattr(clicked_item, 'text_label', clicked_item.uuid)}. Click target state or H-pseudo-state.")
        else:
            if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
            if not isinstance(clicked_item, (GraphicsStateItem, GraphicsHistoryPseudoStateItem)): # Target can be State or H
                QMessageBox.information(self.parent_window, "Invalid Target", "Transitions must end on a regular State or a History pseudo-state.")
                self.transition_start_item = None; self.set_mode("select"); return

            if isinstance(clicked_item, GraphicsHistoryPseudoStateItem):
                if self.transition_start_item.parentItem() == clicked_item.parent_superstate_item:
                    QMessageBox.warning(self.parent_window, "Invalid Transition", "Cannot transition to a History pseudo-state within the same direct superstate hierarchy level. Use internal sub-state transitions or exit/re-enter the superstate.")
                    self.transition_start_item = None; self.set_mode("select"); return

            initial_props = {'event': "", 'condition': "",'action_language': DEFAULT_EXECUTION_ENV, 'action': "",'color': COLOR_ITEM_TRANSITION_DEFAULT, 'description':"",'control_offset_x':0, 'control_offset_y':0}
            dialog = TransitionPropertiesDialog(dialog_parent, current_properties=initial_props, is_new_transition=True)
            if dialog.exec() == QDialog.Accepted:
                props = dialog.get_properties()
                # new_transition instance gets a new UUID from its constructor
                new_transition = GraphicsTransitionItem(self.transition_start_item, clicked_item, event_str=props['event'], condition_str=props['condition'], action_language=props.get('action_language', DEFAULT_EXECUTION_ENV), action_str=props['action'], color=props.get('color'), description=props.get('description', ""))
                new_transition.set_control_point_offset(QPointF(props['control_offset_x'],props['control_offset_y']))
                cmd = AddItemCommand(self, new_transition, "Add Transition"); self.undo_stack.push(cmd)
                start_label = getattr(self.transition_start_item, 'text_label', self.transition_start_item.uuid)
                target_label = getattr(clicked_item, 'text_label', clicked_item.uuid)
                if isinstance(clicked_item, GraphicsHistoryPseudoStateItem): target_label = f"H-Item ({clicked_item.uuid})"
                self._log_to_parent("INFO", f"Added transition: {start_label} -> {target_label} [{new_transition._compose_label_string()}]")
            else: self._log_to_parent("INFO", "Transition addition cancelled by user.")
            self.transition_start_item = None; self.set_mode("select")

    def keyPressEvent(self, event: QKeyEvent): # Stays largely the same
        if event.matches(QKeySequence.Copy): self.copy_selected_items(); event.accept(); return
        elif event.matches(QKeySequence.Paste): self.paste_items_from_clipboard(); event.accept(); return
        if event.key() == Qt.Key_F2:
            selected = self.selectedItems()
            if len(selected) == 1 and isinstance(selected[0], (GraphicsStateItem, GraphicsCommentItem)) and selected[0].flags() & QGraphicsItem.ItemIsFocusable:
                if hasattr(selected[0], 'start_inline_edit') and not getattr(selected[0], '_is_editing_inline', False):
                    selected[0].start_inline_edit(); event.accept(); return
        if event.key() == Qt.Key_Delete or (event.key() == Qt.Key_Backspace and sys.platform != 'darwin'):
            if self.selectedItems(): self.delete_selected_items(); event.accept(); return
        elif event.key() == Qt.Key_Escape:
            active_editor_item = None
            for item in self.items():
                if hasattr(item, '_is_editing_inline') and item._is_editing_inline and hasattr(item, '_inline_editor_proxy') and item._inline_editor_proxy:
                    active_editor_item = item; break
            if active_editor_item:
                editor_widget = active_editor_item._inline_editor_proxy.widget()
                if editor_widget: active_editor_item._inline_edit_aborted = True; editor_widget.clearFocus()
                event.accept(); return
            if self.current_mode == "transition" and self.transition_start_item:
                self.transition_start_item = None
                if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
                self._log_to_parent("INFO", "Transition drawing cancelled by Escape."); self.set_mode("select"); event.accept(); return
            elif self.current_mode != "select": self.set_mode("select"); event.accept(); return
            else: self.clearSelection(); event.accept(); return
        super().keyPressEvent(event)


    def delete_selected_items(self): # RemoveItemsCommand now handles UUIDs
        selected = self.selectedItems()
        if not selected: return
        # RemoveItemsCommand constructor now handles related items and uses UUIDs internally
        cmd = RemoveItemsCommand(self, list(selected), "Delete Items"); self.undo_stack.push(cmd)
        self._log_to_parent("INFO", f"Queued deletion of {len(selected)} selected item(s) and their related elements."); self.clearSelection()

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent): # Stays same
        if event.mimeData().hasFormat("application/x-bsm-tool") or event.mimeData().hasFormat(MIME_TYPE_BSM_TEMPLATE): event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent): # Stays same
        if event.mimeData().hasFormat("application/x-bsm-tool") or event.mimeData().hasFormat(MIME_TYPE_BSM_TEMPLATE): event.acceptProposedAction()
        else: super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent): # Logic for creating items from drag/drop
        pos = event.scenePos(); mime_data = event.mimeData()
        if mime_data.hasFormat(MIME_TYPE_BSM_TEMPLATE):
            template_json_str = mime_data.data(MIME_TYPE_BSM_TEMPLATE).data().decode('utf-8')
            try: template_data = json.loads(template_json_str); self._add_template_to_scene(template_data, pos); event.acceptProposedAction()
            except json.JSONDecodeError as e: self._log_to_parent("ERROR", f"Error parsing dropped FSM template: {e}"); event.ignore()
            return
        elif mime_data.hasFormat("application/x-bsm-tool"):
            item_type_data_str = mime_data.text(); grid_x = round(pos.x() / self.grid_size) * self.grid_size; grid_y = round(pos.y() / self.grid_size) * self.grid_size
            initial_props_for_add = {}; actual_item_type_to_add = "Item"; name_prefix_for_add = "Item"; parent_for_history = None

            if "State" in item_type_data_str: grid_x -= 60; grid_y -= 30
            if item_type_data_str == "State": actual_item_type_to_add = "State"; name_prefix_for_add = "State"
            elif item_type_data_str == "Initial State": actual_item_type_to_add = "State"; name_prefix_for_add = "Initial"; initial_props_for_add['is_initial'] = True
            elif item_type_data_str == "Final State": actual_item_type_to_add = "State"; name_prefix_for_add = "Final"; initial_props_for_add['is_final'] = True
            elif item_type_data_str == "Comment": actual_item_type_to_add = "Comment"; name_prefix_for_add = "Note"
            elif item_type_data_str == "HistoryShallow":
                actual_item_type_to_add = "HistoryShallow"; name_prefix_for_add = "H"
                items_under_drop = self.items(pos)
                parent_for_history = next((it for it in items_under_drop if isinstance(it, GraphicsStateItem) and it.is_superstate), None)
                if not parent_for_history: QMessageBox.warning(self.parent_window, "Invalid Placement", "History (H) must be dropped inside a Superstate."); event.ignore(); return
                pos = parent_for_history.mapFromScene(pos)
            else: self._log_to_parent("WARNING", f"Unknown item type dropped: {item_type_data_str}"); event.ignore(); return
            # _add_item_interactive will create items with new UUIDs
            self._add_item_interactive(QPointF(grid_x if not parent_for_history else pos.x(), grid_y if not parent_for_history else pos.y()), item_type=actual_item_type_to_add, name_prefix=name_prefix_for_add, initial_data=initial_props_for_add, parent_item=parent_for_history)
            event.acceptProposedAction()
        else: super().dropEvent(event)


    def get_diagram_data(self): # Item.get_data() now includes UUIDs
        data = {'states': [], 'transitions': [], 'comments': [], 'history_pseudo_states': []}
        for item in self.items():
            if isinstance(item, GraphicsStateItem): data['states'].append(item.get_data())
            elif isinstance(item, GraphicsTransitionItem):
                if not (isinstance(item.start_item, GraphicsHistoryPseudoStateItem) and item == item.start_item.default_history_transition_item):
                    if item.start_item and item.end_item: data['transitions'].append(item.get_data())
                    else: self._log_to_parent("WARNING", f"Skipping save of orphaned/invalid transition (UUID: {item.uuid}).")
            elif isinstance(item, GraphicsCommentItem): data['comments'].append(item.get_data())
            elif isinstance(item, GraphicsHistoryPseudoStateItem): data['history_pseudo_states'].append(item.get_data())
        return data

    def load_diagram_data(self, data_from_file): # <--- RENAMED PARAMETER
        self.clear(); self._problematic_items.clear(); self._validation_issues = []; self.set_dirty(False)
        item_uuid_map = {} # Maps loaded UUID to newly created QGraphicsItem instance

        # First pass: Create States and Comments, mapping their UUIDs
        for state_data in data_from_file.get('states', []):
            item_uuid = state_data.get('uuid', str(uuid.uuid4())) # Use saved UUID or generate if missing (older files)
            state_item = GraphicsStateItem(
                state_data['x'], state_data['y'], state_data.get('width', 120), state_data.get('height', 60),
                state_data['name'], state_data.get('is_initial', False), state_data.get('is_final', False),
                state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG),
                state_data.get('entry_action',""), state_data.get('during_action',""), state_data.get('exit_action',""),
                state_data.get('description',""), state_data.get('is_superstate', False),
                state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}),
                action_language=state_data.get('action_language', DEFAULT_EXECUTION_ENV),
                item_uuid=item_uuid # Pass the UUID
            )
            if self.parent_window and hasattr(self.parent_window, 'connect_state_item_signals'): # Check parent_window type if sub-editor
                if self.parent_window.__class__.__name__ == "MainWindow": self.parent_window.connect_state_item_signals(state_item)
            self.addItem(state_item); item_uuid_map[item_uuid] = state_item

        for comment_data in data_from_file.get('comments', []):
            item_uuid = comment_data.get('uuid', str(uuid.uuid4()))
            comment_item = GraphicsCommentItem(
                comment_data['x'], comment_data['y'], comment_data.get('text', ""), item_uuid=item_uuid
            )
            comment_item.setTextWidth(comment_data.get('width', 150)); self.addItem(comment_item)
            item_uuid_map[item_uuid] = comment_item

        # Second pass: Create HistoryPseudoStateItems (they need their parent superstate from the map)
        for h_data in data_from_file.get('history_pseudo_states', []):
            item_uuid = h_data.get('uuid', str(uuid.uuid4()))
            parent_uuid = h_data.get('parent_superstate_uuid') # Link by UUID
            parent_state_item = item_uuid_map.get(parent_uuid) if parent_uuid else None

            if parent_state_item and isinstance(parent_state_item, GraphicsStateItem) and parent_state_item.is_superstate:
                # Default target will be linked in third pass
                h_item = GraphicsHistoryPseudoStateItem(
                    h_data['x_relative'], h_data['y_relative'],
                    parent_superstate_item=parent_state_item,
                    history_type=h_data.get('type', 'shallow'),
                    item_uuid=item_uuid # Pass the UUID
                )
                item_uuid_map[item_uuid] = h_item # Add to map for transition linking
            else:
                self._log_to_parent("WARNING", f"Load Warning: HistoryItem (UUID {item_uuid}) - Parent superstate (UUID {parent_uuid}) not found or not a superstate.")

        # Third pass: Create Transitions and link History item default targets
        for trans_data in data_from_file.get('transitions', []):
            item_uuid = trans_data.get('uuid', str(uuid.uuid4()))
            src_uuid = trans_data.get('source_uuid') # Expect UUID for linking
            tgt_uuid = trans_data.get('target_uuid')

            src_item = item_uuid_map.get(src_uuid) if src_uuid else None
            tgt_item = item_uuid_map.get(tgt_uuid) if tgt_uuid else None

            if src_item and tgt_item:
                trans_item = GraphicsTransitionItem(
                    src_item, tgt_item,
                    event_str=trans_data.get('event',""), condition_str=trans_data.get('condition',""),
                    action_language=trans_data.get('action_language', DEFAULT_EXECUTION_ENV),
                    action_str=trans_data.get('action',""), color=trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT),
                    description=trans_data.get('description',""), item_uuid=item_uuid # Pass the UUID
                )
                trans_item.set_control_point_offset(QPointF(trans_data.get('control_offset_x',0), trans_data.get('control_offset_y',0)))
                self.addItem(trans_item)
                item_uuid_map[item_uuid] = trans_item
            else:
                self._log_to_parent("WARNING", f"Load Warning: Transition (UUID {item_uuid}) - Source (UUID {src_uuid}) or Target (UUID {tgt_uuid}) not found. Display names: '{trans_data.get('source', 'N/A')}' -> '{trans_data.get('target', 'N/A')}'.")

        for h_data in data_from_file.get('history_pseudo_states', []):
            h_item_uuid = h_data.get('uuid')
            h_item_instance = item_uuid_map.get(h_item_uuid)
            if h_item_instance and isinstance(h_item_instance, GraphicsHistoryPseudoStateItem):
                default_target_substate_uuid = h_data.get('default_target_substate_uuid')
                if default_target_substate_uuid:
                    target_state_item = item_uuid_map.get(default_target_substate_uuid)
                    if isinstance(target_state_item, GraphicsStateItem):
                        h_item_instance.set_default_target_substate(target_state_item)
                    else:
                        self._log_to_parent("WARNING", f"Load Warning: HistoryItem (UUID {h_item_uuid}) - Default target substate (UUID {default_target_substate_uuid}) not found or not a state.")

        self.set_dirty(False); self.undo_stack.clear(); self.run_all_validations("LoadDiagramData"); self.scene_content_changed_for_find.emit()

    # ... (drawBackground, drawForeground remain the same)
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

    def copy_selected_items(self): # Data now includes UUIDs
        selected_items = self.selectedItems()
        if not selected_items: return
        items_to_copy_data = []
        for item in selected_items:
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem)):
                item_data = item.get_data() # This now includes 'uuid'
                item_type_str = "Unknown"
                if isinstance(item, GraphicsStateItem): item_type_str = "State"
                elif isinstance(item, GraphicsCommentItem): item_type_str = "Comment"
                elif isinstance(item, GraphicsHistoryPseudoStateItem): item_type_str = "HistoryPseudoState"
                items_to_copy_data.append({"item_type": item_type_str, "data": item_data})
        if items_to_copy_data:
            clipboard = QApplication.clipboard();
            try:
                json_data_str = json.dumps(items_to_copy_data); mime_data_obj = QMimeData()
                mime_data_obj.setData(MIME_TYPE_BSM_ITEMS, json_data_str.encode('utf-8'))
                mime_data_obj.setText(f"{len(items_to_copy_data)} BSM items copied"); clipboard.setMimeData(mime_data_obj)
                self._log_to_parent("INFO", f"Copied {len(items_to_copy_data)} item(s) to clipboard.")
            except (json.JSONDecodeError, TypeError) as e: self._log_to_parent("ERROR", f"Error serializing items for copy: {e}")


    def paste_items_from_clipboard(self):
        clipboard = QApplication.clipboard(); mime_data_clipboard = clipboard.mime_Data()
        if not mime_data_clipboard.hasFormat(MIME_TYPE_BSM_ITEMS): self._log_to_parent("DEBUG", "Paste: No BSM items found."); return
        try: json_data_bytes = mime_data_clipboard.data(MIME_TYPE_BSM_ITEMS); items_to_paste_data_list = json.loads(json_data_bytes.data().decode('utf-8'))
        except (json.JSONDecodeError, TypeError) as e: self._log_to_parent("ERROR", f"Error deserializing items for paste: {e}"); return
        if not items_to_paste_data_list: return

        paste_center_pos = QPointF(100, 100)
        if self.views(): view = self.views()[0]; global_cursor_pos = QCursor.pos(); view_cursor_pos = view.mapFromGlobal(global_cursor_pos); paste_center_pos = view.mapToScene(view_cursor_pos)
        
        offset_delta = QPointF(self.grid_size, self.grid_size)
        base_paste_pos = paste_center_pos
        pasted_graphic_items = []
        
        # Map of old (clipboard) UUIDs to new (pasted) item instances
        clipboard_uuid_to_new_item_map = {}

        self.undo_stack.beginMacro("Paste Items")

        # First pass: Paste States and Comments, generate NEW UUIDs, store mapping
        for i, item_info in enumerate(items_to_paste_data_list):
            item_type = item_info.get("item_type"); data = item_info.get("data")
            if not item_type or not data: continue

            new_item_uuid = str(uuid.uuid4()) # Generate a NEW UUID for the pasted item
            old_item_uuid = data.get('uuid') # Get the UUID from the clipboard data

            current_paste_pos = QPointF(data.get('x', base_paste_pos.x()) + (i+1) * offset_delta.x(), data.get('y', base_paste_pos.y()) + (i+1) * offset_delta.y())
            new_item = None

            if item_type == "State":
                original_name = data.get('name', "PastedState"); new_name = self._generate_unique_state_name(original_name)
                item_pos_x = round(current_paste_pos.x() / self.grid_size) * self.grid_size; item_pos_y = round(current_paste_pos.y() / self.grid_size) * self.grid_size
                new_item = GraphicsStateItem(x=item_pos_x, y=item_pos_y,w=data.get('width', 120), h=data.get('height', 60),text=new_name, is_initial=False,is_final=data.get('is_final', False),color=data.get('color', COLOR_ITEM_STATE_DEFAULT_BG),action_language=data.get('action_language', DEFAULT_EXECUTION_ENV),entry_action=data.get('entry_action', ""),during_action=data.get('during_action', ""),exit_action=data.get('exit_action', ""),description=data.get('description', ""),is_superstate=data.get('is_superstate', False),sub_fsm_data=json.loads(json.dumps(data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}))), item_uuid=new_item_uuid)
                if self.parent_window and hasattr(self.parent_window, 'connect_state_item_signals'):
                    if self.parent_window.__class__.__name__ == "MainWindow": self.parent_window.connect_state_item_signals(new_item)
            elif item_type == "Comment":
                item_pos_x = round(current_paste_pos.x() / self.grid_size) * self.grid_size; item_pos_y = round(current_paste_pos.y() / self.grid_size) * self.grid_size
                new_item = GraphicsCommentItem(x=item_pos_x, y=item_pos_y,text=data.get('text', "Pasted Comment"), item_uuid=new_item_uuid)
                new_item.setTextWidth(data.get('width', 150))
            
            if new_item:
                cmd = AddItemCommand(self, new_item, f"Paste {item_type}"); self.undo_stack.push(cmd)
                pasted_graphic_items.append(new_item)
                if old_item_uuid: clipboard_uuid_to_new_item_map[old_item_uuid] = new_item

        # Second pass: Paste HistoryPseudoStateItems, link to NEW parent UUIDs
        for i, item_info in enumerate(items_to_paste_data_list):
            item_type = item_info.get("item_type"); data = item_info.get("data")
            if item_type != "HistoryPseudoState" or not data: continue

            new_item_uuid = str(uuid.uuid4()) # New UUID for pasted H-item
            old_item_uuid = data.get('uuid')

            old_parent_uuid = data.get('parent_superstate_uuid')
            pasted_parent_item = clipboard_uuid_to_new_item_map.get(old_parent_uuid)

            if pasted_parent_item and isinstance(pasted_parent_item, GraphicsStateItem) and pasted_parent_item.is_superstate:
                # Ensure this type of H-item doesn't already exist in the NEW parent
                h_type = data.get('type', 'shallow')
                can_add_h = True
                for child_h in pasted_parent_item.contained_history_pseudo_states:
                    if child_h.history_type == h_type: can_add_h = False; break
                
                if can_add_h:
                    current_paste_pos = QPointF(data.get('x_relative', self.grid_size), data.get('y_relative', self.grid_size))
                    new_h_item = GraphicsHistoryPseudoStateItem(
                        x_relative=current_paste_pos.x(), y_relative=current_paste_pos.y(),
                        parent_superstate_item=pasted_parent_item,
                        history_type=h_type,
                        item_uuid=new_item_uuid
                    )
                    # Default target linking will happen after all items are created
                    pasted_graphic_items.append(new_h_item) # Added by virtue of parentItem
                    if old_item_uuid: clipboard_uuid_to_new_item_map[old_item_uuid] = new_h_item
                else:
                    self._log_to_parent("WARNING", f"Paste: Superstate '{pasted_parent_item.text_label}' (new UUID: {pasted_parent_item.uuid}) already has a '{h_type}' history. Skipped pasting H-item {old_item_uuid}.")
            else:
                 self._log_to_parent("WARNING", f"Paste: Parent superstate (old UUID: {old_parent_uuid}) for H-item {old_item_uuid} not found among pasted states or not a superstate.")


        # Third pass: Paste Transitions and link History default targets using the new UUIDs map
        # This pass must happen AFTER all states and H-items are created and mapped
        for i, item_info in enumerate(items_to_paste_data_list):
            item_type = item_info.get("item_type"); data = item_info.get("data")
            if not data: continue

            if item_type == "Transition":
                new_item_uuid = str(uuid.uuid4()) # New UUID for pasted transition

                old_source_uuid = data.get('source_uuid')
                old_target_uuid = data.get('target_uuid')

                new_src_item = clipboard_uuid_to_new_item_map.get(old_source_uuid)
                new_tgt_item = clipboard_uuid_to_new_item_map.get(old_target_uuid)

                if new_src_item and new_tgt_item:
                    new_transition = GraphicsTransitionItem(
                        new_src_item, new_tgt_item,
                        event_str=data.get('event', ""), condition_str=data.get('condition', ""),
                        action_language=data.get('action_language', DEFAULT_EXECUTION_ENV),
                        action_str=data.get('action', ""), color=data.get('color'),
                        description=data.get('description', ""), item_uuid=new_item_uuid
                    )
                    new_transition.set_control_point_offset(QPointF(data.get('control_offset_x',0),data.get('control_offset_y',0)))
                    cmd = AddItemCommand(self, new_transition, "Paste Transition"); self.undo_stack.push(cmd)
                    pasted_graphic_items.append(new_transition)
                else:
                    self._log_to_parent("WARNING", f"Paste: Could not link pasted transition (old UUID: {data.get('uuid')}). Source (old UUID: {old_source_uuid}) or Target (old UUID: {old_target_uuid}) not found in pasted set.")
            
            elif item_type == "HistoryPseudoState": # Now link default targets
                old_h_item_uuid = data.get('uuid')
                new_h_item_instance = clipboard_uuid_to_new_item_map.get(old_h_item_uuid)
                if new_h_item_instance and isinstance(new_h_item_instance, GraphicsHistoryPseudoStateItem):
                    old_default_target_uuid = data.get('default_target_substate_uuid')
                    if old_default_target_uuid:
                        new_target_state_instance = clipboard_uuid_to_new_item_map.get(old_default_target_uuid)
                        if new_target_state_instance and isinstance(new_target_state_instance, GraphicsStateItem):
                            new_h_item_instance.set_default_target_substate(new_target_state_instance)
                        else:
                            self._log_to_parent("WARNING", f"Paste: H-item (new UUID: {new_h_item_instance.uuid}) default target (old UUID: {old_default_target_uuid}) not found in pasted set or invalid.")


        self.undo_stack.endMacro()
        if pasted_graphic_items:
            self.clearSelection(); [gi.setSelected(True) for gi in pasted_graphic_items]; self._log_to_parent("INFO", f"Pasted {len(pasted_graphic_items)} item(s).")
            if self.views() and pasted_graphic_items: self.views()[0].ensureVisible(pasted_graphic_items[-1], 50, 50)
            self.scene_content_changed_for_find.emit()
            self.run_all_validations("PasteItems")


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


    def _add_template_to_scene(self, template_data: dict, drop_pos: QPointF):
        if not isinstance(template_data, dict): self._log_to_parent("ERROR", "Invalid template data format."); return
        self.undo_stack.beginMacro(f"Add Template: {template_data.get('name', 'Unnamed Template')}")
        
        newly_created_scene_items = []
        # Map of original_name (or a placeholder ID from template) to new GraphicsItem instance
        template_item_map_by_orig_name = {}
        # Map of original_name (or placeholder ID from template) to NEW UUID of created item
        template_orig_name_to_new_uuid_map = {}


        min_x_template = min((s.get('x', 0) for s in template_data.get('states', [])), default=0)
        min_y_template = min((s.get('y', 0) for s in template_data.get('states', [])), default=0)
        base_offset_x = drop_pos.x() - min_x_template; base_offset_y = drop_pos.y() - min_y_template
        
        # Generate unique suffix if any state name clashes
        instance_suffix = ""
        if any(self.get_state_by_name(s_data.get('name', "State")) for s_data in template_data.get('states', [])):
            i = 1
            while any(self.get_state_by_name(f"{s_data.get('name', 'State')}_{i}") for s_data in template_data.get('states',[])): i += 1
            instance_suffix = f"_{i}"

        # First pass: Create States and Comments with new UUIDs
        for state_data in template_data.get('states', []):
            original_name = state_data.get('name', "State") # Name from template file
            unique_name_for_scene = self._generate_unique_state_name(f"{original_name}{instance_suffix}")
            new_item_uuid = str(uuid.uuid4()) # Generate new UUID

            pos_x = round((base_offset_x + state_data.get('x', 0)) / self.grid_size) * self.grid_size
            pos_y = round((base_offset_y + state_data.get('y', 0)) / self.grid_size) * self.grid_size
            
            state_item = GraphicsStateItem(
                x=pos_x, y=pos_y,w=state_data.get('width', 120), h=state_data.get('height', 60),
                text=unique_name_for_scene,
                is_initial=state_data.get('is_initial', False) if not self.items() else False, # Only one initial for whole diagram
                is_final=state_data.get('is_final', False),color=state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG),
                action_language=state_data.get('action_language', DEFAULT_EXECUTION_ENV),
                entry_action=state_data.get('entry_action', ""),during_action=state_data.get('during_action', ""),
                exit_action=state_data.get('exit_action', ""),description=state_data.get('description', ""),
                is_superstate=state_data.get('is_superstate', False),
                sub_fsm_data=json.loads(json.dumps(state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}))), # Deep copy sub_fsm_data
                item_uuid=new_item_uuid # Use new UUID
            )
            if self.parent_window and hasattr(self.parent_window, 'connect_state_item_signals'):
                 if self.parent_window.__class__.__name__ == "MainWindow": self.parent_window.connect_state_item_signals(state_item)

            cmd = AddItemCommand(self, state_item, f"Add State from Template: {unique_name_for_scene}"); self.undo_stack.push(cmd)
            newly_created_scene_items.append(state_item)
            template_item_map_by_orig_name[original_name] = state_item # Map original template name to new instance
            template_orig_name_to_new_uuid_map[original_name] = new_item_uuid

        for comment_data in template_data.get('comments', []):
            new_item_uuid = str(uuid.uuid4())
            pos_x = round((base_offset_x + comment_data.get('x', 0)) / self.grid_size) * self.grid_size
            pos_y = round((base_offset_y + comment_data.get('y', 0)) / self.grid_size) * self.grid_size
            comment_item = GraphicsCommentItem(x=pos_x, y=pos_y,text=comment_data.get('text', "Comment"), item_uuid=new_item_uuid)
            comment_item.setTextWidth(comment_data.get('width', 150))
            cmd = AddItemCommand(self, comment_item, "Add Comment from Template"); self.undo_stack.push(cmd)
            newly_created_scene_items.append(comment_item)
            # Comments usually don't need to be mapped for linking, but if template had IDs for them:
            # if 'id' in comment_data: template_item_map_by_orig_name[comment_data['id']] = comment_item

        # Second pass: Create History items and link to new parent UUIDs
        history_items_to_link_default_target_template = []
        for h_data in template_data.get('history_pseudo_states', []):
            new_h_item_uuid = str(uuid.uuid4())
            parent_original_name = h_data.get('parent_superstate_name')
            parent_item_instance = template_item_map_by_orig_name.get(parent_original_name)

            if parent_item_instance and isinstance(parent_item_instance, GraphicsStateItem) and parent_item_instance.is_superstate:
                h_type = h_data.get('type', 'shallow')
                can_add_h = not any(child_h.history_type == h_type for child_h in parent_item_instance.contained_history_pseudo_states)
                if can_add_h:
                    h_item = GraphicsHistoryPseudoStateItem(
                        x_relative=h_data['x_relative'], y_relative=h_data['y_relative'],
                        parent_superstate_item=parent_item_instance, history_type=h_type,
                        item_uuid=new_h_item_uuid
                    )
                    newly_created_scene_items.append(h_item) # Added via parent
                    template_item_map_by_orig_name[f"H_{parent_original_name}_{h_type}"] = h_item # Store with a unique key
                    template_orig_name_to_new_uuid_map[f"H_{parent_original_name}_{h_type}"] = new_h_item_uuid
                    history_items_to_link_default_target_template.append((h_item, h_data.get('default_target_substate_name'))) # Store original target name
                else: self._log_to_parent("WARNING", f"Template: Superstate '{parent_item_instance.text_label}' already has a '{h_type}' history. Skipped.")
            else: self._log_to_parent("WARNING", f"Template: Parent superstate '{parent_original_name}' for H-item not found or not superstate.")


        # Third pass: Create Transitions, link using new item instances from map
        for trans_data in template_data.get('transitions', []):
            src_original_name = trans_data.get('source'); tgt_original_name = trans_data.get('target')
            src_item = template_item_map_by_orig_name.get(src_original_name)
            tgt_item = template_item_map_by_orig_name.get(tgt_original_name)

            if src_item and tgt_item:
                new_trans_uuid = str(uuid.uuid4())
                trans_item = GraphicsTransitionItem(
                    src_item, tgt_item,
                    event_str=trans_data.get('event', ""),condition_str=trans_data.get('condition', ""),
                    action_language=trans_data.get('action_language', DEFAULT_EXECUTION_ENV),
                    action_str=trans_data.get('action', ""),color=trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT),
                    description=trans_data.get('description', ""), item_uuid=new_trans_uuid
                )
                trans_item.set_control_point_offset(QPointF(trans_data.get('control_offset_x', 0),trans_data.get('control_offset_y', 0)))
                cmd = AddItemCommand(self, trans_item, f"Add Transition from Template"); self.undo_stack.push(cmd)
                newly_created_scene_items.append(trans_item)
            else: self._log_to_parent("WARNING", f"Template: Could not link transition. Missing state for '{src_original_name}' or '{tgt_original_name}'.")

        # Fourth pass: Link default targets for H-items using mapped instances
        for h_item_instance, default_target_orig_name in history_items_to_link_default_target_template:
            if default_target_orig_name:
                target_state_instance = template_item_map_by_orig_name.get(default_target_orig_name)
                if target_state_instance and isinstance(target_state_instance, GraphicsStateItem):
                    h_item_instance.set_default_target_substate(target_state_instance)
                else:
                    self._log_to_parent("WARNING", f"Template: H-item default target '{default_target_orig_name}' not found in template instances.")


        self.undo_stack.endMacro()
        if newly_created_scene_items:
            self.clearSelection(); [item.setSelected(True) for item in newly_created_scene_items]
            self._log_to_parent("INFO", f"Added {len(newly_created_scene_items)} items from template '{template_data.get('name', '')}'.")
            self.scene_content_changed_for_find.emit()
            if self.views() and newly_created_scene_items:
                combined_rect = QRectF()
                for i, item in enumerate(newly_created_scene_items):
                    if i == 0: combined_rect = item.sceneBoundingRect()
                    else: combined_rect = combined_rect.united(item.sceneBoundingRect())
                if not combined_rect.isEmpty(): self.views()[0].ensureVisible(combined_rect, 50, 50)
            self.run_all_validations("AddTemplateToScene")


# ... (ZoomableView class and its methods remain the same) ...
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