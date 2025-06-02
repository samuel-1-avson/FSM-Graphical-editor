# bsm_designer_project/graphics_scene.py

import sys
import os
import json 
import logging 
import math 
from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsLineItem,
    QMenu, QMessageBox, QDialog, QStyle, QGraphicsSceneMouseEvent,
    QGraphicsSceneDragDropEvent, QKeyEvent # Added QKeyEvent here
)
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QCursor, QMouseEvent, # Removed QKeyEvent from here
    QWheelEvent, QBrush 
)
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF, pyqtSignal, QPoint, QMarginsF, QEvent # Added QEvent

from utils import get_standard_icon

from config import (
    COLOR_BACKGROUND_LIGHT, COLOR_GRID_MINOR, COLOR_GRID_MAJOR, COLOR_ACCENT_PRIMARY,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG,
    DEFAULT_EXECUTION_ENV 
)
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem

from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand


logger = logging.getLogger(__name__) 

SNAP_THRESHOLD_PIXELS = 8 
GUIDELINE_PEN_COLOR = QColor(Qt.red) 
GUIDELINE_PEN_WIDTH = 0.8

class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool)

    def __init__(self, undo_stack, parent_window=None):
        super().__init__(parent_window) 
        self.parent_window = parent_window 
        self.setSceneRect(0, 0, 6000, 4500)
        self.current_mode = "select"
        self.transition_start_item = None
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


    def _log_to_parent(self, level, message):
        if self.parent_window and hasattr(self.parent_window, 'log_message'):
            self.parent_window.log_message(level, message)
        else: 
            logger.log(getattr(logging, level.upper(), logging.INFO), f"(SceneDirect) {message}")

    def log_function(self, message: str, level: str = "ERROR"):
        self._log_to_parent(level.upper(), message)


    def _update_connected_transitions(self, state_item: GraphicsStateItem):
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                if item.start_item == state_item or item.end_item == state_item:
                    item.update_path()

    def _update_transitions_for_renamed_state(self, old_name:str, new_name:str):
        self._log_to_parent("INFO", f"Scene notified: State '{old_name}' changed to '{new_name}'. Dependent transitions might need data update if they store names.")
        # If transitions store actual item references, they update visually via _update_connected_transitions.
        # If they store names (e.g., for save/load), their internal data might need an update
        # if a state they point to is renamed. This is more for data consistency than immediate visual.
        # The EditItemPropertiesCommand for the state should handle this data update.
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                needs_update = False
                if item.start_item and item.start_item.text_label == new_name: # Check if it now points to the new name
                    # This check is a bit circular if the item reference is already updated.
                    # The core idea is if the transition's *stored data* used old_name.
                    # For now, assume visual updates are primary.
                    pass 
                if item.end_item and item.end_item.text_label == new_name:
                    pass


    def get_state_by_name(self, name: str) -> GraphicsStateItem | None:
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

    def is_dirty(self):
        return self._dirty

    def set_mode(self, mode: str):
        old_mode = self.current_mode
        if old_mode == mode: return
        self.current_mode = mode
        self._log_to_parent("INFO", f"Interaction mode changed to: {mode}")
        self.transition_start_item = None
        if self._temp_transition_line:
            self.removeItem(self._temp_transition_line)
            self._temp_transition_line = None
        
        if self.views(): 
            main_view = self.views()[0]
            if hasattr(main_view, '_restore_cursor_to_scene_mode'):
                main_view._restore_cursor_to_scene_mode()

        for item in self.items():
            movable_flag = mode == "select"
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)):
                item.setFlag(QGraphicsItem.ItemIsMovable, movable_flag)

        if self.parent_window and hasattr(self.parent_window, 'mode_action_group'): 
            actions_map = {
                "select": getattr(self.parent_window, 'select_mode_action', None),
                "state": getattr(self.parent_window, 'add_state_mode_action', None),
                "transition": getattr(self.parent_window, 'add_transition_mode_action', None),
                "comment": getattr(self.parent_window, 'add_comment_mode_action', None)
            }
            action_to_check = actions_map.get(mode)
            if action_to_check and hasattr(action_to_check, 'isChecked') and not action_to_check.isChecked():
                action_to_check.setChecked(True)
        elif self.parent_window and hasattr(self.parent_window, 'sub_mode_action_group'): 
            actions_map_sub = {
                "select": getattr(self.parent_window, 'sub_select_action', None),
                "state": getattr(self.parent_window, 'sub_add_state_action', None),
                "transition": getattr(self.parent_window, 'sub_add_transition_action', None),
                "comment": getattr(self.parent_window, 'sub_add_comment_action', None)
            }
            action_to_check_sub = actions_map_sub.get(mode)
            if action_to_check_sub and hasattr(action_to_check_sub, 'isChecked') and not action_to_check_sub.isChecked():
                action_to_check_sub.setChecked(True)


    def select_all(self):
        for item in self.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable:
                item.setSelected(True)

    def _handle_item_moved_visual_update(self, moved_item):
        if isinstance(moved_item, GraphicsStateItem):
            self._update_connected_transitions(moved_item)

    def _clear_dynamic_guidelines(self):
        if self._horizontal_snap_lines or self._vertical_snap_lines:
            self._horizontal_snap_lines.clear()
            self._vertical_snap_lines.clear()
            self.update() 

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos()
        items_at_pos = self.items(pos)
        # Prioritize state/comment items for interaction, then transitions
        top_item_at_pos = next((item for item in items_at_pos if isinstance(item, (GraphicsStateItem, GraphicsCommentItem))), None)
        if not top_item_at_pos:
            top_item_at_pos = next((item for item in items_at_pos if isinstance(item, GraphicsTransitionItem)), None)
        if not top_item_at_pos and items_at_pos: # Fallback to any item
             top_item_at_pos = items_at_pos[0]


        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size - 60 
                grid_y = round(pos.y() / self.grid_size) * self.grid_size - 30
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type="State")
            elif self.current_mode == "comment":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size
                grid_y = round(pos.y() / self.grid_size) * self.grid_size
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type="Comment")
            elif self.current_mode == "transition":
                if isinstance(top_item_at_pos, GraphicsStateItem):
                    self._handle_transition_click(top_item_at_pos, pos)
                else: 
                    if self.transition_start_item:
                        self._log_to_parent("INFO", "Transition drawing cancelled (clicked non-state/empty space).")
                    self.transition_start_item = None 
                    if self._temp_transition_line:
                        self.removeItem(self._temp_transition_line)
                        self._temp_transition_line = None
            else: # Select mode
                # Store original positions for undo command if a drag starts
                self._mouse_press_items_positions.clear()
                selected_items_list = self.selectedItems()

                # If clicking on an unselected movable item, and not holding Ctrl/Shift, clear others and select it
                if top_item_at_pos and isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsCommentItem, GraphicsTransitionItem)) and \
                   top_item_at_pos.flags() & QGraphicsItem.ItemIsMovable and \
                   not top_item_at_pos.isSelected() and \
                   not (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                    self.clearSelection()
                    top_item_at_pos.setSelected(True)
                    selected_items_list = [top_item_at_pos] # Update for position storing

                # If clicking a transition's control point, the item itself handles it.
                # If it's a general item drag, store positions.
                if not (isinstance(top_item_at_pos, GraphicsTransitionItem) and top_item_at_pos._dragging_control_point):
                    for item_to_process in selected_items_list:
                        if item_to_process.flags() & QGraphicsItem.ItemIsMovable:
                             self._mouse_press_items_positions[item_to_process] = item_to_process.pos()
                
                super().mousePressEvent(event) # Let the scene handle selection/move start

        elif event.button() == Qt.RightButton:
            if top_item_at_pos and isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem)):
                if not top_item_at_pos.isSelected(): 
                    self.clearSelection()
                    top_item_at_pos.setSelected(True)
                self._show_context_menu(top_item_at_pos, event.screenPos()) 
            else: 
                self.clearSelection()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        self._clear_dynamic_guidelines() 

        if self.current_mode == "select" and event.buttons() & Qt.LeftButton and self._mouse_press_items_positions:
            if self.snap_to_objects_enabled and self._show_dynamic_snap_guidelines:
                dragged_items = list(self._mouse_press_items_positions.keys())
                if dragged_items:
                    primary_dragged_item = dragged_items[0] # Simplification: use first selected item
                    
                    # Calculate current potential origin based on drag
                    original_item_press_pos = self._mouse_press_items_positions.get(primary_dragged_item)
                    original_mouse_press_scene_pos = event.buttonDownScenePos(Qt.LeftButton) # Where mouse was pressed
                    current_mouse_scene_pos = event.scenePos()
                    drag_vector = current_mouse_scene_pos - original_mouse_press_scene_pos
                    
                    if original_item_press_pos is not None: # Ensure item was in map
                        potential_item_origin = original_item_press_pos + drag_vector
                        potential_sbr = primary_dragged_item.boundingRect().translated(potential_item_origin)

                        snap_points_x = {
                            'left': potential_sbr.left(), 'center': potential_sbr.center().x(), 'right': potential_sbr.right()
                        }
                        snap_points_y = {
                            'top': potential_sbr.top(), 'center': potential_sbr.center().y(), 'bottom': potential_sbr.bottom()
                        }

                        visible_rect = self.views()[0].mapToScene(self.views()[0].viewport().rect()).boundingRect() if self.views() else self.sceneRect()

                        for other_item in self.items():
                            if other_item in dragged_items or not isinstance(other_item, (GraphicsStateItem, GraphicsCommentItem)):
                                continue
                            other_sbr = other_item.sceneBoundingRect()

                            other_align_x = [other_sbr.left(), other_sbr.center().x(), other_sbr.right()]
                            for drag_x in snap_points_x.values():
                                for static_x in other_align_x:
                                    if abs(drag_x - static_x) <= SNAP_THRESHOLD_PIXELS:
                                        line = QLineF(static_x, visible_rect.top(), static_x, visible_rect.bottom())
                                        if line not in self._vertical_snap_lines: self._vertical_snap_lines.append(line)
                                        break 
                            other_align_y = [other_sbr.top(), other_sbr.center().y(), other_sbr.bottom()]
                            for drag_y in snap_points_y.values():
                                for static_y in other_align_y:
                                    if abs(drag_y - static_y) <= SNAP_THRESHOLD_PIXELS:
                                        line = QLineF(visible_rect.left(), static_y, visible_rect.right(), static_y)
                                        if line not in self._horizontal_snap_lines: self._horizontal_snap_lines.append(line)
                                        break
                        if self._horizontal_snap_lines or self._vertical_snap_lines:
                            self.update() 

        elif self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, event.scenePos()))
        
        super().mouseMoveEvent(event)


    def _calculate_object_snap_position(self, moving_item: QGraphicsItem, candidate_item_origin_pos: QPointF) -> QPointF:
        if not self.snap_to_objects_enabled:
            return candidate_item_origin_pos

        current_best_x = candidate_item_origin_pos.x()
        current_best_y = candidate_item_origin_pos.y()
        min_offset_x = SNAP_THRESHOLD_PIXELS + 1 
        min_offset_y = SNAP_THRESHOLD_PIXELS + 1

        moving_item_br = moving_item.boundingRect() 
        candidate_moving_sbr = moving_item_br.translated(candidate_item_origin_pos)

        moving_item_refs_x = {
            'left': candidate_moving_sbr.left(),
            'center': candidate_moving_sbr.center().x(),
            'right': candidate_moving_sbr.right()
        }
        moving_item_refs_y = {
            'top': candidate_moving_sbr.top(),
            'center': candidate_moving_sbr.center().y(),
            'bottom': candidate_moving_sbr.bottom()
        }

        for other_item in self.items():
            if other_item == moving_item or not isinstance(other_item, (GraphicsStateItem, GraphicsCommentItem)):
                continue

            other_sbr = other_item.sceneBoundingRect() 

            other_item_snap_points_x = [other_sbr.left(), other_sbr.center().x(), other_sbr.right()]
            for moving_ref_name, moving_x_val in moving_item_refs_x.items():
                for other_x_val in other_item_snap_points_x:
                    diff_x = other_x_val - moving_x_val
                    if abs(diff_x) < min_offset_x:
                        min_offset_x = abs(diff_x)
                        current_best_x = candidate_item_origin_pos.x() + diff_x
                    elif abs(diff_x) == min_offset_x: 
                        pass

            other_item_snap_points_y = [other_sbr.top(), other_sbr.center().y(), other_sbr.bottom()]
            for moving_ref_name, moving_y_val in moving_item_refs_y.items():
                for other_y_val in other_item_snap_points_y:
                    diff_y = other_y_val - moving_y_val
                    if abs(diff_y) < min_offset_y:
                        min_offset_y = abs(diff_y)
                        current_best_y = candidate_item_origin_pos.y() + diff_y
                    elif abs(diff_y) == min_offset_y:
                        pass
        
        final_x = current_best_x if min_offset_x <= SNAP_THRESHOLD_PIXELS else candidate_item_origin_pos.x()
        final_y = current_best_y if min_offset_y <= SNAP_THRESHOLD_PIXELS else candidate_item_origin_pos.y()

        return QPointF(final_x, final_y)


    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            if self._mouse_press_items_positions:
                moved_items_data_for_command = []
                # emit_item_moved_for_these = [] # This was not used, can remove

                for item, old_pos in self._mouse_press_items_positions.items():
                    current_item_pos_after_drag = item.pos() 
                    
                    final_snapped_pos = current_item_pos_after_drag

                    if self.snap_to_objects_enabled:
                        final_snapped_pos = self._calculate_object_snap_position(item, current_item_pos_after_drag)

                    if self.snap_to_grid_enabled:
                        # Snap the object-snapped position (or original drag if no object snap) to grid
                        grid_snapped_x = round(final_snapped_pos.x() / self.grid_size) * self.grid_size
                        grid_snapped_y = round(final_snapped_pos.y() / self.grid_size) * self.grid_size
                        final_snapped_pos = QPointF(grid_snapped_x, grid_snapped_y)
                    
                    # Only record a move if the final position is different from the original
                    if (final_snapped_pos - old_pos).manhattanLength() > 0.1 :
                        item.setPos(final_snapped_pos) 
                        moved_items_data_for_command.append((item, old_pos, final_snapped_pos))
                        # emit_item_moved_for_these.append(item) # Not used
                    elif (current_item_pos_after_drag - old_pos).manhattanLength() > 0.1 and \
                         (final_snapped_pos - current_item_pos_after_drag).manhattanLength() < 0.1:
                        # Item was dragged, but snapping brought it back to or very near original drag pos
                        # Still, it was a drag, so record the original drag outcome for undo
                         moved_items_data_for_command.append((item, old_pos, current_item_pos_after_drag))


                if moved_items_data_for_command:
                    cmd = MoveItemsCommand(moved_items_data_for_command, "Move Items")
                    self.undo_stack.push(cmd)
                    self.set_dirty(True) # Scene is dirty if items moved
                
                self._mouse_press_items_positions.clear()
        
        self._clear_dynamic_guidelines() 
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        items_at_pos = self.items(event.scenePos())
        item_to_edit = next((item for item in items_at_pos if isinstance(item, (GraphicsStateItem, GraphicsCommentItem, GraphicsTransitionItem))), None)
        
        if item_to_edit and hasattr(item_to_edit, '_is_editing_inline') and item_to_edit._is_editing_inline:
            event.accept() 
            return

        if item_to_edit and isinstance(item_to_edit, (GraphicsStateItem, GraphicsCommentItem)):
            self.edit_item_properties(item_to_edit) # Default to properties dialog
            event.accept()
            return
        elif item_to_edit and isinstance(item_to_edit, GraphicsTransitionItem):
            self.edit_item_properties(item_to_edit)
            event.accept()
            return

        super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, item, global_pos):
        menu = QMenu()
        edit_action = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        
        if isinstance(item, GraphicsStateItem) and item.is_superstate:
            pass 

        delete_action = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")

        action = menu.exec_(global_pos) 
        if action == edit_action:
            self.edit_item_properties(item) 
        elif action == delete_action:
            if not item.isSelected(): 
                self.clearSelection()
                item.setSelected(True)
            self.delete_selected_items()

    def edit_item_properties(self, item):
        from dialogs import StatePropertiesDialog, TransitionPropertiesDialog, CommentPropertiesDialog 
    
        dialog_executed_and_accepted = False
        new_props_from_dialog = None
        DialogType = None

        old_props = item.get_data() if hasattr(item, 'get_data') else {} 
        if isinstance(item, GraphicsStateItem): DialogType = StatePropertiesDialog
        elif isinstance(item, GraphicsTransitionItem): DialogType = TransitionPropertiesDialog
        elif isinstance(item, GraphicsCommentItem): DialogType = CommentPropertiesDialog
        else: return 

        dialog_parent = self.parent_window if self.parent_window else self.views()[0] if self.views() else None
        
        if DialogType == StatePropertiesDialog:
            dialog = DialogType(parent=dialog_parent, current_properties=old_props, is_new_state=False, scene_ref=self)
        else: 
            dialog = DialogType(parent=dialog_parent, current_properties=old_props)
        
        if dialog.exec() == QDialog.Accepted: 
            dialog_executed_and_accepted = True
            new_props_from_dialog = dialog.get_properties()

            if isinstance(item, GraphicsStateItem): 
                current_new_name = new_props_from_dialog.get('name')
                existing_state_with_new_name = self.get_state_by_name(current_new_name)
                if current_new_name != old_props.get('name') and existing_state_with_new_name and existing_state_with_new_name != item:
                    QMessageBox.warning(dialog_parent, "Duplicate Name", f"A state with the name '{current_new_name}' already exists.")
                    return 

        if dialog_executed_and_accepted and new_props_from_dialog is not None:
            final_new_props = old_props.copy()
            final_new_props.update(new_props_from_dialog)

            if final_new_props == old_props:
                self._log_to_parent("INFO", "Properties unchanged.")
                return

            cmd = EditItemPropertiesCommand(item, old_props, final_new_props, f"Edit {type(item).__name__} Properties")
            self.undo_stack.push(cmd)

            item_name_for_log = final_new_props.get('name', final_new_props.get('event', final_new_props.get('text', 'Item')))
            self._log_to_parent("INFO", f"Properties updated for: {item_name_for_log}")

        self.update() 

    def _add_item_interactive(self, pos: QPointF, item_type: str, name_prefix:str="Item", initial_data:dict=None):
        from dialogs import StatePropertiesDialog, CommentPropertiesDialog 
        current_item = None
        initial_data = initial_data or {}
        is_initial_state_from_drag = initial_data.get('is_initial', False)
        is_final_state_from_drag = initial_data.get('is_final', False)

        dialog_parent = self.parent_window if self.parent_window else self.views()[0] if self.views() else None

        if item_type == "State":
            i = 1
            base_name = name_prefix if name_prefix != "Item" else "State" 
            while self.get_state_by_name(f"{base_name}{i}"): 
                i += 1
            default_name = f"{base_name}{i}"

            initial_dialog_props = {
                'name': default_name,
                'is_initial': is_initial_state_from_drag,
                'is_final': is_final_state_from_drag,
                'color': initial_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG),
                'action_language': initial_data.get('action_language', DEFAULT_EXECUTION_ENV),
                'entry_action':"", 'during_action':"", 'exit_action':"", 'description':"",
                'is_superstate': False, 'sub_fsm_data': {'states': [], 'transitions': [], 'comments': []}
            }
            props_dialog = StatePropertiesDialog(dialog_parent, current_properties=initial_dialog_props, is_new_state=True, scene_ref=self)

            if props_dialog.exec() == QDialog.Accepted:
                final_props = props_dialog.get_properties()
                if self.get_state_by_name(final_props['name']) and final_props['name'] != default_name: 
                    QMessageBox.warning(dialog_parent, "Duplicate Name", f"A state named '{final_props['name']}' already exists.")
                else:
                    current_item = GraphicsStateItem(
                        pos.x(), pos.y(), 120, 60, 
                        final_props['name'],
                        final_props['is_initial'], final_props['is_final'],
                        final_props.get('color'),
                        final_props.get('entry_action',""),
                        final_props.get('during_action',""),
                        final_props.get('exit_action',""),
                        final_props.get('description',""),
                        final_props.get('is_superstate', False),
                        final_props.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}),
                        action_language=final_props.get('action_language', DEFAULT_EXECUTION_ENV)
                    )
            if self.current_mode == "state": 
                self.set_mode("select")
            if not current_item: return 

        elif item_type == "Comment":
            initial_text = initial_data.get('text', "Comment" if name_prefix == "Item" else name_prefix)
            comment_props_dialog = CommentPropertiesDialog(dialog_parent, {'text': initial_text}) 

            if comment_props_dialog.exec() == QDialog.Accepted:
                final_comment_props = comment_props_dialog.get_properties()
                if final_comment_props['text']: 
                     current_item = GraphicsCommentItem(pos.x(), pos.y(), final_comment_props['text'])
                else: 
                    self.set_mode("select" if self.current_mode == "comment" else self.current_mode)
                    return
            else: 
                self.set_mode("select" if self.current_mode == "comment" else self.current_mode)
                return
        else:
            self._log_to_parent("WARNING", f"Unknown item type for addition: {item_type}")
            return

        if current_item:
            cmd = AddItemCommand(self, current_item, f"Add {item_type}")
            self.undo_stack.push(cmd)
            log_name = getattr(current_item, 'text_label', None) or \
                       (getattr(current_item, 'toPlainText', lambda: "Item")() if isinstance(current_item, GraphicsCommentItem) else "Item")
            self._log_to_parent("INFO", f"Added {item_type}: {log_name} at ({pos.x():.0f},{pos.y():.0f})")


    def _handle_transition_click(self, clicked_state_item: GraphicsStateItem, click_pos: QPointF):
        from dialogs import TransitionPropertiesDialog 
        dialog_parent = self.parent_window if self.parent_window else self.views()[0] if self.views() else None
        if not self.transition_start_item: 
            self.transition_start_item = clicked_state_item
            if not self._temp_transition_line:
                self._temp_transition_line = QGraphicsLineItem()
                self._temp_transition_line.setPen(QPen(QColor(COLOR_ACCENT_PRIMARY), 1.8, Qt.DashLine))
                self.addItem(self._temp_transition_line) 
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, click_pos))
            self._log_to_parent("INFO", f"Transition started from: {clicked_state_item.text_label}. Click target state.")
        else: 
            if self._temp_transition_line: 
                self.removeItem(self._temp_transition_line)
                self._temp_transition_line = None

            initial_props = { 
                'event': "", 'condition': "", 
                'action_language': DEFAULT_EXECUTION_ENV, 'action': "",
                'color': COLOR_ITEM_TRANSITION_DEFAULT, 'description':"",
                'control_offset_x':0, 'control_offset_y':0
            }
            dialog = TransitionPropertiesDialog(dialog_parent, current_properties=initial_props, is_new_transition=True)

            if dialog.exec() == QDialog.Accepted:
                props = dialog.get_properties()
                new_transition = GraphicsTransitionItem(
                    self.transition_start_item, clicked_state_item,
                    event_str=props['event'], condition_str=props['condition'],
                    action_language=props.get('action_language', DEFAULT_EXECUTION_ENV),
                    action_str=props['action'],
                    color=props.get('color'), description=props.get('description', "")
                )
                new_transition.set_control_point_offset(QPointF(props['control_offset_x'],props['control_offset_y']))

                cmd = AddItemCommand(self, new_transition, "Add Transition")
                self.undo_stack.push(cmd)
                self._log_to_parent("INFO", f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{new_transition._compose_label_string()}]")
            else: 
                self._log_to_parent("INFO", "Transition addition cancelled by user.")

            self.transition_start_item = None 
            self.set_mode("select") 

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_F2:
            selected = self.selectedItems()
            if len(selected) == 1 and isinstance(selected[0], (GraphicsStateItem, GraphicsCommentItem)) \
               and selected[0].flags() & QGraphicsItem.ItemIsFocusable:
                if hasattr(selected[0], 'start_inline_edit') and not getattr(selected[0], '_is_editing_inline', False):
                    selected[0].start_inline_edit()
                    event.accept() 
                    return 
        
        if event.key() == Qt.Key_Delete or (event.key() == Qt.Key_Backspace and sys.platform != 'darwin'): 
            if self.selectedItems():
                self.delete_selected_items()
                event.accept()
                return
        elif event.key() == Qt.Key_Escape:
            active_editor_item = None
            for item in self.items(): 
                if hasattr(item, '_is_editing_inline') and item._is_editing_inline and hasattr(item, '_inline_editor_proxy') and item._inline_editor_proxy:
                    active_editor_item = item
                    break
            if active_editor_item:
                editor_widget = active_editor_item._inline_editor_proxy.widget()
                if editor_widget:
                    # Send an Escape key event to the editor itself
                    esc_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
                    QApplication.sendEvent(editor_widget, esc_event)
                self.set_mode("select") 
                event.accept()
                return 

            if self.current_mode == "transition" and self.transition_start_item:
                self.transition_start_item = None
                if self._temp_transition_line:
                    self.removeItem(self._temp_transition_line)
                    self._temp_transition_line = None
                self._log_to_parent("INFO", "Transition drawing cancelled by Escape.")
                self.set_mode("select")
                event.accept()
                return
            elif self.current_mode != "select": 
                self.set_mode("select")
                event.accept()
                return
            else: 
                self.clearSelection()
                event.accept()
                return
        
        super().keyPressEvent(event)


    def delete_selected_items(self):
        selected = self.selectedItems()
        if not selected: return

        items_to_delete_with_related = set() 
        for item in selected:
            items_to_delete_with_related.add(item)
            if isinstance(item, GraphicsStateItem): 
                for scene_item in self.items():
                    if isinstance(scene_item, GraphicsTransitionItem):
                        if scene_item.start_item == item or scene_item.end_item == item:
                            items_to_delete_with_related.add(scene_item)

        if items_to_delete_with_related:
            cmd = RemoveItemsCommand(self, list(items_to_delete_with_related), "Delete Items")
            self.undo_stack.push(cmd)
            self._log_to_parent("INFO", f"Queued deletion of {len(items_to_delete_with_related)} item(s).")
            self.clearSelection() 

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        pos = event.scenePos()
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            item_type_data_str = event.mimeData().text() 

            grid_x = round(pos.x() / self.grid_size) * self.grid_size
            grid_y = round(pos.y() / self.grid_size) * self.grid_size

            if "State" in item_type_data_str: 
                grid_x -= 60 
                grid_y -= 30 

            initial_props_for_add = {}
            actual_item_type_to_add = "Item" 
            name_prefix_for_add = "Item" 

            if item_type_data_str == "State":
                actual_item_type_to_add = "State"
                name_prefix_for_add = "State"
            elif item_type_data_str == "Initial State":
                actual_item_type_to_add = "State"
                name_prefix_for_add = "Initial" 
                initial_props_for_add['is_initial'] = True
            elif item_type_data_str == "Final State":
                actual_item_type_to_add = "State"
                name_prefix_for_add = "Final"
                initial_props_for_add['is_final'] = True
            elif item_type_data_str == "Comment":
                actual_item_type_to_add = "Comment"
                name_prefix_for_add = "Note"
            else:
                self._log_to_parent("WARNING", f"Unknown item type dropped: {item_type_data_str}")
                event.ignore()
                return

            self._add_item_interactive(QPointF(grid_x, grid_y),
                                       item_type=actual_item_type_to_add,
                                       name_prefix=name_prefix_for_add,
                                       initial_data=initial_props_for_add)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def get_diagram_data(self):
        data = {'states': [], 'transitions': [], 'comments': []}
        for item in self.items():
            if isinstance(item, GraphicsStateItem):
                data['states'].append(item.get_data())
            elif isinstance(item, GraphicsTransitionItem):
                if item.start_item and item.end_item: 
                    data['transitions'].append(item.get_data())
                else:
                    self._log_to_parent("WARNING", f"Skipping save of orphaned/invalid transition: '{item._compose_label_string()}'.")
            elif isinstance(item, GraphicsCommentItem):
                data['comments'].append(item.get_data())
        return data

    def load_diagram_data(self, data):
        self.clear() 
        self.set_dirty(False) 
        state_items_map = {} 

        for state_data in data.get('states', []):
            state_item = GraphicsStateItem(
                state_data['x'], state_data['y'],
                state_data.get('width', 120), state_data.get('height', 60),
                state_data['name'],
                state_data.get('is_initial', False), state_data.get('is_final', False),
                state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG),
                state_data.get('entry_action',""), state_data.get('during_action',""),
                state_data.get('exit_action',""), state_data.get('description',""),
                state_data.get('is_superstate', False), 
                state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}),
                action_language=state_data.get('action_language', DEFAULT_EXECUTION_ENV) 
            )
            self.addItem(state_item)
            state_items_map[state_data['name']] = state_item

        for trans_data in data.get('transitions', []):
            src_item = state_items_map.get(trans_data['source'])
            tgt_item = state_items_map.get(trans_data['target'])
            if src_item and tgt_item:
                trans_item = GraphicsTransitionItem(
                    src_item, tgt_item,
                    event_str=trans_data.get('event',""), condition_str=trans_data.get('condition',""),
                    action_language=trans_data.get('action_language', DEFAULT_EXECUTION_ENV), 
                    action_str=trans_data.get('action',""),
                    color=trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT),
                    description=trans_data.get('description',"")
                )
                trans_item.set_control_point_offset(QPointF(trans_data.get('control_offset_x',0), trans_data.get('control_offset_y',0)))
                self.addItem(trans_item)
            else:
                label_info = f"{trans_data.get('event','')}{trans_data.get('condition','')}{trans_data.get('action','')}"
                self._log_to_parent("WARNING", f"Load Warning: Could not link transition '{label_info}' due to missing states: Source='{trans_data['source']}', Target='{trans_data['target']}'.")


        for comment_data in data.get('comments', []):
            comment_item = GraphicsCommentItem(comment_data['x'], comment_data['y'], comment_data.get('text', ""))
            comment_item.setTextWidth(comment_data.get('width', 150)) 
            self.addItem(comment_item)

        self.set_dirty(False) 
        if self.undo_stack: self.undo_stack.clear() 

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect) 

        view_rect = self.views()[0].viewport().rect() if self.views() else rect
        visible_scene_rect = self.views()[0].mapToScene(view_rect).boundingRect() if self.views() else rect

        left = int(visible_scene_rect.left() / self.grid_size) * self.grid_size - self.grid_size 
        right = int(visible_scene_rect.right() / self.grid_size) * self.grid_size + self.grid_size
        top = int(visible_scene_rect.top() / self.grid_size) * self.grid_size - self.grid_size
        bottom = int(visible_scene_rect.bottom() / self.grid_size) * self.grid_size + self.grid_size

        painter.setPen(self.grid_pen_light)
        for x in range(left, right, self.grid_size):
            if x % (self.grid_size * 5) != 0: 
                painter.drawLine(x, top, x, bottom)
        for y in range(top, bottom, self.grid_size):
            if y % (self.grid_size * 5) != 0:
                painter.drawLine(left, y, right, y)

        major_grid_size = self.grid_size * 5
        first_major_left = left - (left % major_grid_size) if left >=0 else left - (left % major_grid_size) - major_grid_size
        first_major_top = top - (top % major_grid_size) if top >= 0 else top - (top % major_grid_size) - major_grid_size

        painter.setPen(self.grid_pen_dark)
        for x in range(first_major_left, right, major_grid_size):
            painter.drawLine(x, top, x, bottom)
        for y in range(first_major_top, bottom, major_grid_size):
            painter.drawLine(left, y, right, y)

    def drawForeground(self, painter: QPainter, rect: QRectF): 
        super().drawForeground(painter, rect) 
        if self._show_dynamic_snap_guidelines:
            pen = QPen(GUIDELINE_PEN_COLOR, GUIDELINE_PEN_WIDTH, Qt.DashLine)
            painter.setPen(pen)
            for line in self._horizontal_snap_lines:
                painter.drawLine(line)
            for line in self._vertical_snap_lines:
                painter.drawLine(line)


class ZoomableView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag) 
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate) 
        self.zoom_level = 0
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._is_panning_with_space = False
        self._is_panning_with_mouse_button = False 
        self._last_pan_point = QPoint()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier: 
            delta = event.angleDelta().y()
            factor = 1.12 if delta > 0 else 1 / 1.12
            new_zoom_level = self.zoom_level + (1 if delta > 0 else -1)
            min_zoom_level = -15 
            max_zoom_level = 15 
            if min_zoom_level <= new_zoom_level <= max_zoom_level: 
                self.scale(factor, factor)
                self.zoom_level = new_zoom_level
            event.accept()
        else: 
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = True
            self._last_pan_point = self.mapFromGlobal(QCursor.pos()) 
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal: 
            self.zoom_in()
        elif event.key() == Qt.Key_Minus: 
            self.zoom_out()
        elif event.key() == Qt.Key_0 or event.key() == Qt.Key_Asterisk: 
            self.reset_view_and_zoom()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = False
            if not self._is_panning_with_mouse_button: 
                self._restore_cursor_to_scene_mode()
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton or \
           (self._is_panning_with_space and event.button() == Qt.LeftButton):
            self._last_pan_point = event.pos() 
            self.setCursor(Qt.ClosedHandCursor)
            self._is_panning_with_mouse_button = True
            event.accept()
        else:
            self._is_panning_with_mouse_button = False 
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button:
            delta_view = event.pos() - self._last_pan_point
            self._last_pan_point = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta_view.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta_view.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button and \
           (event.button() == Qt.MiddleButton or (self._is_panning_with_space and event.button() == Qt.LeftButton)):
            self._is_panning_with_mouse_button = False
            if self._is_panning_with_space: 
                self.setCursor(Qt.OpenHandCursor)
            else: 
                self._restore_cursor_to_scene_mode()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _restore_cursor_to_scene_mode(self):
        current_scene_mode = self.scene().current_mode if self.scene() and hasattr(self.scene(), 'current_mode') else "select"
        if current_scene_mode == "select":
            self.setCursor(Qt.ArrowCursor)
        elif current_scene_mode in ["state", "comment"]:
            self.setCursor(Qt.CrossCursor)
        elif current_scene_mode == "transition":
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def zoom_in(self):
        factor = 1.12
        new_zoom_level = self.zoom_level + 1
        if new_zoom_level <= 15: 
            self.scale(factor, factor)
            self.zoom_level = new_zoom_level

    def zoom_out(self):
        factor = 1 / 1.12
        new_zoom_level = self.zoom_level - 1
        if new_zoom_level >= -15: 
            self.scale(factor, factor)
            self.zoom_level = new_zoom_level

    def reset_view_and_zoom(self):
        self.resetTransform()
        self.zoom_level = 0
        if self.scene():
            content_rect = self.scene().itemsBoundingRect()
            if not content_rect.isEmpty():
                self.centerOn(content_rect.center())
            elif self.scene().sceneRect(): 
                self.centerOn(self.scene().sceneRect().center())

    def zoom_to_rect(self, target_rect: QRectF, padding_factor: float = 0.1):
        if target_rect.isNull() or not self.scene():
            return

        width_padding = target_rect.width() * padding_factor
        height_padding = target_rect.height() * padding_factor
        padded_rect = target_rect.adjusted(-width_padding, -height_padding, width_padding, height_padding)
        
        self.fitInView(padded_rect, Qt.KeepAspectRatio)
        
    def zoom_to_selection(self):
        if not self.scene() or not self.scene().selectedItems():
            return
        
        selection_rect = QRectF()
        first_item = True
        for item in self.scene().selectedItems():
            if first_item:
                selection_rect = item.sceneBoundingRect()
                first_item = False
            else:
                selection_rect = selection_rect.united(item.sceneBoundingRect())
        
        if not selection_rect.isEmpty():
            self.zoom_to_rect(selection_rect)

    def fit_diagram_in_view(self):
        if not self.scene():
            return
        
        items_rect = self.scene().itemsBoundingRect()
        if not items_rect.isEmpty():
            self.zoom_to_rect(items_rect)
        else: 
            self.zoom_to_rect(self.scene().sceneRect())