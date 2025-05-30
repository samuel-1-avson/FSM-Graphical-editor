# bsm_designer_project/graphics_scene.py

# Add this import at the top with other imports
from utils import get_standard_icon

# Update the imports section to include utils
import sys
import os
import json # For get_diagram_data
import logging # For logging within the scene
from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsLineItem,
    QMenu, QMessageBox, QDialog, QStyle, QGraphicsSceneMouseEvent,
    QGraphicsSceneDragDropEvent
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QKeyEvent, QCursor, QMouseEvent,
    QWheelEvent
)
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF, pyqtSignal, QPoint

# Add the import for get_standard_icon
from utils import get_standard_icon  # Add this line

from config import (
    COLOR_BACKGROUND_LIGHT, COLOR_GRID_MINOR, COLOR_GRID_MAJOR, COLOR_ACCENT_PRIMARY,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG,
    DEFAULT_EXECUTION_ENV # Import default environment
)
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
# Dialogs are needed for edit_item_properties

# Undo commands
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand


logger = logging.getLogger(__name__) # Logger specific to this module

class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool)

    def __init__(self, undo_stack, parent_window=None):
        super().__init__(parent_window) # Pass parent_window to QGraphicsScene
        self.parent_window = parent_window # Store reference to main window or parent dialog
        self.setSceneRect(0, 0, 6000, 4500)
        self.current_mode = "select"
        self.transition_start_item = None
        self.undo_stack = undo_stack # This is QUndoStack instance
        self._dirty = False
        self._mouse_press_items_positions = {}
        self._temp_transition_line = None
        self._validation_highlighted_items = [] # Store items with validation highlights

        self.item_moved.connect(self._handle_item_moved_visual_update)

        self.grid_size = 20
        self.grid_pen_light = QPen(QColor(COLOR_GRID_MINOR), 0.7, Qt.DotLine)
        self.grid_pen_dark = QPen(QColor(COLOR_GRID_MAJOR), 0.9, Qt.SolidLine)
        self.setBackgroundBrush(QColor(COLOR_BACKGROUND_LIGHT))
        self.snap_to_grid_enabled = True

    def _log_to_parent(self, level, message):
        """Helper to log through the parent_window if it has a log_message method."""
        if self.parent_window and hasattr(self.parent_window, 'log_message'):
            self.parent_window.log_message(level, message)
        else: # Fallback if no parent logger
            logger.log(getattr(logging, level.upper(), logging.INFO), f"(SceneDirect) {message}")

    def log_function(self, message: str, level: str = "ERROR"):
        """Public logging function for external modules like undo_commands."""
        self._log_to_parent(level.upper(), message)


    def _update_connected_transitions(self, state_item: GraphicsStateItem):
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                if item.start_item == state_item or item.end_item == state_item:
                    item.update_path()

    def _update_transitions_for_renamed_state(self, old_name:str, new_name:str):
        # This method is primarily a notification hook.
        # The actual data update for transitions (source/target names) happens
        # when get_diagram_data() is called, as transitions store references
        # to state items, and get_data() on transition items fetches the current
        # text_label of those referenced state items.
        # However, for immediate visual updates or other logic, this hook is useful.
        self._log_to_parent("INFO", f"Scene notified: State '{old_name}' changed to '{new_name}'. Dependent transitions' data will reflect this on next get_diagram_data().")
        # If transitions directly stored names and needed re-linking, that logic would go here.
        # For now, the visual update of transition labels is handled by their paint method
        # which calls _compose_label_string, which in turn uses the current event/condition/action strings.
        # If state names were part of the transition label itself (not typical for standard UML),
        # then transitions would need an explicit update here.


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
        if dirty and self.parent_window and hasattr(self.parent_window, '_clear_validation_highlights_on_modify'):
            self.parent_window._clear_validation_highlights_on_modify()


    def is_dirty(self):
        return self._dirty

    def set_mode(self, mode: str):
        old_mode = self.current_mode
        if old_mode == mode: return
        self.current_mode = mode
        self._log_to_parent("INFO", f"Interaction mode changed to: {mode}")
        self.transition_start_item = None # Reset transition start item on mode change
        if self._temp_transition_line:
            self.removeItem(self._temp_transition_line)
            self._temp_transition_line = None
        
        # Restore cursor based on the new mode
        if self.views(): 
            main_view = self.views()[0]
            if hasattr(main_view, '_restore_cursor_to_scene_mode'):
                main_view._restore_cursor_to_scene_mode()

        # Update item movability based on mode
        for item in self.items():
            movable_flag = mode == "select" # Only allow moving in select mode
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)):
                item.setFlag(QGraphicsItem.ItemIsMovable, movable_flag)

        # Update UI (toolbar buttons) to reflect the new mode
        # This part is a bit tricky as the scene shouldn't directly control main window UI too much.
        # Ideally, the main window connects to a signal from the scene or sets the mode itself.
        # For now, keeping the existing logic but acknowledging its slight architectural impurity.
        if self.parent_window and hasattr(self.parent_window, 'mode_action_group'): # For main window
            actions_map = {
                "select": getattr(self.parent_window, 'select_mode_action', None),
                "state": getattr(self.parent_window, 'add_state_mode_action', None),
                "transition": getattr(self.parent_window, 'add_transition_mode_action', None),
                "comment": getattr(self.parent_window, 'add_comment_mode_action', None)
            }
            action_to_check = actions_map.get(mode)
            if action_to_check and hasattr(action_to_check, 'isChecked') and not action_to_check.isChecked():
                action_to_check.setChecked(True)
        elif self.parent_window and hasattr(self.parent_window, 'sub_mode_action_group'): # For sub-FSM editor dialog
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
        """Update connected transitions when a state item is moved."""
        if isinstance(moved_item, GraphicsStateItem):
            self._update_connected_transitions(moved_item)
        # If a comment moves, it doesn't typically affect other items' paths.


    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos()
        # Prioritize getting a GraphicsStateItem, then others, then any top item.
        items_at_pos = self.items(pos)
        top_item_at_pos = next((item for item in items_at_pos if isinstance(item, GraphicsStateItem)), None)
        if not top_item_at_pos: # If no state item, check for comment or transition
            top_item_at_pos = next((item for item in items_at_pos if isinstance(item, (GraphicsCommentItem, GraphicsTransitionItem))), None)
            if not top_item_at_pos and items_at_pos: # Fallback to any item if specific types not found
                top_item_at_pos = items_at_pos[0] 

        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size - 60 # Center state on grid point
                grid_y = round(pos.y() / self.grid_size) * self.grid_size - 30
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type="State")
            elif self.current_mode == "comment":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size
                grid_y = round(pos.y() / self.grid_size) * self.grid_size
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type="Comment")
            elif self.current_mode == "transition":
                if isinstance(top_item_at_pos, GraphicsStateItem):
                    self._handle_transition_click(top_item_at_pos, pos)
                else: # Clicked on empty space or non-state item during transition drawing
                    if self.transition_start_item: # If a transition was being drawn
                        self._log_to_parent("INFO", "Transition drawing cancelled (clicked non-state/empty space).")
                    self.transition_start_item = None # Cancel transition
                    if self._temp_transition_line:
                        self.removeItem(self._temp_transition_line)
                        self._temp_transition_line = None
            else: # Select mode or other
                # Store positions of selected movable items for undo command on move
                self._mouse_press_items_positions.clear()
                selected_items_list = self.selectedItems()
                if selected_items_list: # Only if there are selected items
                    for item_to_process in [item for item in selected_items_list if item.flags() & QGraphicsItem.ItemIsMovable]:
                        self._mouse_press_items_positions[item_to_process] = item_to_process.pos()
                super().mousePressEvent(event) # Propagate for standard selection/move
        elif event.button() == Qt.RightButton:
            # Show context menu for the item under cursor, if any
            if top_item_at_pos and isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem)):
                if not top_item_at_pos.isSelected(): # If item not selected, select it exclusively
                    self.clearSelection()
                    top_item_at_pos.setSelected(True)
                self._show_context_menu(top_item_at_pos, event.screenPos()) # Pass global screen position
            else: # Right-click on empty space
                self.clearSelection() # Clear selection if right-clicking empty space
                # Optionally, show a scene-wide context menu here
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            # Update temporary line for transition drawing
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, event.scenePos()))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            if self._mouse_press_items_positions: # If items were being moved
                moved_items_data_for_command = [] # (item, old_pos, new_pos)
                emit_item_moved_for_these = [] # Items for which to emit item_moved

                for item, old_pos in self._mouse_press_items_positions.items():
                    new_pos = item.pos() # Current position after move
                    snapped_new_pos = new_pos
                    if self.snap_to_grid_enabled:
                        snapped_x = round(new_pos.x() / self.grid_size) * self.grid_size
                        snapped_y = round(new_pos.y() / self.grid_size) * self.grid_size
                        snapped_new_pos = QPointF(snapped_x, snapped_y)
                        if new_pos != snapped_new_pos:
                             item.setPos(snapped_new_pos) # Snap item to grid

                    # Check if item actually moved significantly
                    if (snapped_new_pos - old_pos).manhattanLength() > 0.1: # Small tolerance for float precision
                        moved_items_data_for_command.append((item, old_pos, snapped_new_pos))
                        emit_item_moved_for_these.append(item)
                
                if moved_items_data_for_command:
                    cmd = MoveItemsCommand(moved_items_data_for_command, "Move Items")
                    self.undo_stack.push(cmd)
                    # item_moved signal is emitted by itemChange, so no need to emit here explicitly for moved_item
                
                self._mouse_press_items_positions.clear() # Clear stored positions
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        items_at_pos = self.items(event.scenePos())
        item_to_edit = next((item for item in items_at_pos if isinstance(item, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem))), None)
        if item_to_edit:
            self.edit_item_properties(item_to_edit)
        else:
            super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, item, global_pos):
        menu = QMenu()
        edit_action = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        
        # Add "Edit Sub-Machine" action if it's a superstate
        if isinstance(item, GraphicsStateItem) and item.is_superstate:
            # This action is now part of the properties dialog itself.
            # If direct access is needed via context menu, it can be added here.
            # For now, properties dialog is the main entry point for sub-FSM editing.
            pass

        delete_action = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")

        action = menu.exec_(global_pos) # Show menu at global mouse position
        if action == edit_action:
            self.edit_item_properties(item) # Call existing properties editor
        elif action == delete_action:
            if not item.isSelected(): # Ensure item is selected before deleting
                self.clearSelection()
                item.setSelected(True)
            self.delete_selected_items()

    def edit_item_properties(self, item):
        # Lazy import to avoid circular dependency if dialogs import scene items
        from dialogs import StatePropertiesDialog, TransitionPropertiesDialog, CommentPropertiesDialog
    
        dialog_executed_and_accepted = False
        new_props_from_dialog = None
        DialogType = None

        old_props = item.get_data() if hasattr(item, 'get_data') else {} # Get current item data
        # Determine dialog type based on item type
        if isinstance(item, GraphicsStateItem): DialogType = StatePropertiesDialog
        elif isinstance(item, GraphicsTransitionItem): DialogType = TransitionPropertiesDialog
        elif isinstance(item, GraphicsCommentItem): DialogType = CommentPropertiesDialog
        else: return # Unknown item type

        # Determine parent for the dialog (main window or current view)
        dialog_parent = self.parent_window if self.parent_window else self.views()[0] if self.views() else None
        
        # Instantiate and exec dialog
        if DialogType == StatePropertiesDialog:
            # Pass scene_ref for name validation in StatePropertiesDialog
            dialog = DialogType(parent=dialog_parent, current_properties=old_props, is_new_state=False, scene_ref=self)
        else: # For Transition and Comment dialogs
            dialog = DialogType(parent=dialog_parent, current_properties=old_props)
        
        if dialog.exec() == QDialog.Accepted: # User clicked OK
            dialog_executed_and_accepted = True
            new_props_from_dialog = dialog.get_properties()

            # Specific validation for state names (must be unique)
            if isinstance(item, GraphicsStateItem): 
                current_new_name = new_props_from_dialog.get('name')
                existing_state_with_new_name = self.get_state_by_name(current_new_name)
                # If name changed AND new name already exists for a DIFFERENT item
                if current_new_name != old_props.get('name') and existing_state_with_new_name and existing_state_with_new_name != item:
                    QMessageBox.warning(dialog_parent, "Duplicate Name", f"A state with the name '{current_new_name}' already exists.")
                    return # Prevent applying changes

        if dialog_executed_and_accepted and new_props_from_dialog is not None:
            # Merge old props with new ones (new_props_from_dialog might not contain all fields)
            final_new_props = old_props.copy() # Start with a copy of old properties
            final_new_props.update(new_props_from_dialog) # Update with changes from dialog

            # Check if properties actually changed to avoid unnecessary undo commands
            if final_new_props == old_props:
                self._log_to_parent("INFO", "Properties unchanged.")
                return

            # Create and push undo command
            cmd = EditItemPropertiesCommand(item, old_props, final_new_props, f"Edit {type(item).__name__} Properties")
            self.undo_stack.push(cmd)

            # Log the change
            item_name_for_log = final_new_props.get('name', final_new_props.get('event', final_new_props.get('text', 'Item')))
            self._log_to_parent("INFO", f"Properties updated for: {item_name_for_log}")

        self.update() # Ensure scene redraws with updated item

    def _add_item_interactive(self, pos: QPointF, item_type: str, name_prefix:str="Item", initial_data:dict=None):
        # Lazy import for dialogs
        from dialogs import StatePropertiesDialog, CommentPropertiesDialog
        
        current_item = None # The item to be added
        initial_data = initial_data or {} # Ensure initial_data is a dict
        
        # Special handling for initial/final state flags from dragged tools
        is_initial_state_from_drag = initial_data.get('is_initial', False)
        is_final_state_from_drag = initial_data.get('is_final', False)

        dialog_parent = self.parent_window if self.parent_window else self.views()[0] if self.views() else None

        if item_type == "State":
            # Find a unique default name
            i = 1
            base_name = name_prefix if name_prefix != "Item" else "State" # Use provided prefix or default
            while self.get_state_by_name(f"{base_name}{i}"): # Ensure name is unique
                i += 1
            default_name = f"{base_name}{i}"

            # Prepare initial properties for the dialog
            initial_dialog_props = {
                'name': default_name,
                'is_initial': is_initial_state_from_drag, # From dragged tool
                'is_final': is_final_state_from_drag,     # From dragged tool
                'color': initial_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG),
                'action_language': initial_data.get('action_language', DEFAULT_EXECUTION_ENV),
                'entry_action':"", 'during_action':"", 'exit_action':"", 'description':"",
                'is_superstate': False, 'sub_fsm_data': {'states': [], 'transitions': [], 'comments': []}
            }
            props_dialog = StatePropertiesDialog(dialog_parent, current_properties=initial_dialog_props, is_new_state=True, scene_ref=self)

            if props_dialog.exec() == QDialog.Accepted:
                final_props = props_dialog.get_properties()
                # Check for name collision again after dialog, in case user changed it to an existing name
                if self.get_state_by_name(final_props['name']) and final_props['name'] != default_name: # If name changed AND it collides
                    QMessageBox.warning(dialog_parent, "Duplicate Name", f"A state named '{final_props['name']}' already exists.")
                    # Don't create item if name collides
                else:
                    # Create GraphicsStateItem with properties from dialog
                    current_item = GraphicsStateItem(
                        pos.x(), pos.y(), 120, 60, # Default size, position from click/drop
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
            if self.current_mode == "state": # If still in "add state" mode
                self.set_mode("select") # Switch back to select mode after adding
            if not current_item: return # If dialog cancelled or name collision, do nothing further

        elif item_type == "Comment":
            initial_text = initial_data.get('text', "Comment" if name_prefix == "Item" else name_prefix)
            comment_props_dialog = CommentPropertiesDialog(dialog_parent, {'text': initial_text}) 

            if comment_props_dialog.exec() == QDialog.Accepted:
                final_comment_props = comment_props_dialog.get_properties()
                if final_comment_props['text']: # Ensure comment text is not empty
                     current_item = GraphicsCommentItem(pos.x(), pos.y(), final_comment_props['text'])
                else: # No text, don't add
                    self.set_mode("select" if self.current_mode == "comment" else self.current_mode)
                    return
            else: # Dialog cancelled
                self.set_mode("select" if self.current_mode == "comment" else self.current_mode)
                return
        else:
            self._log_to_parent("WARNING", f"Unknown item type for addition: {item_type}")
            return

        # If item was successfully created, add it via UndoCommand
        if current_item:
            cmd = AddItemCommand(self, current_item, f"Add {item_type}")
            self.undo_stack.push(cmd)
            # Log the addition
            log_name = getattr(current_item, 'text_label', None) or \
                       (getattr(current_item, 'toPlainText', lambda: "Item")() if isinstance(current_item, GraphicsCommentItem) else "Item")
            self._log_to_parent("INFO", f"Added {item_type}: {log_name} at ({pos.x():.0f},{pos.y():.0f})")


    def _handle_transition_click(self, clicked_state_item: GraphicsStateItem, click_pos: QPointF):
        from dialogs import TransitionPropertiesDialog # Lazy import
        dialog_parent = self.parent_window if self.parent_window else self.views()[0] if self.views() else None
        
        if not self.transition_start_item: # First click: start of transition
            self.transition_start_item = clicked_state_item
            # Create and show temporary line for visual feedback
            if not self._temp_transition_line:
                self._temp_transition_line = QGraphicsLineItem()
                self._temp_transition_line.setPen(QPen(QColor(COLOR_ACCENT_PRIMARY), 1.8, Qt.DashLine))
                self.addItem(self._temp_transition_line) # Add to scene
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, click_pos))
            self._log_to_parent("INFO", f"Transition started from: {clicked_state_item.text_label}. Click target state.")
        else: # Second click: end of transition
            # Remove temporary line
            if self._temp_transition_line: 
                self.removeItem(self._temp_transition_line)
                self._temp_transition_line = None

            # Open properties dialog for the new transition
            initial_props = { # Default properties for a new transition
                'event': "", 'condition': "", 
                'action_language': DEFAULT_EXECUTION_ENV, 'action': "",
                'color': COLOR_ITEM_TRANSITION_DEFAULT, 'description':"",
                'control_offset_x':0, 'control_offset_y':0 # Default straight line
            }
            dialog = TransitionPropertiesDialog(dialog_parent, current_properties=initial_props, is_new_transition=True)

            if dialog.exec() == QDialog.Accepted: # User clicked OK
                props = dialog.get_properties()
                # Create the actual GraphicsTransitionItem
                new_transition = GraphicsTransitionItem(
                    self.transition_start_item, clicked_state_item, # Start and end items
                    event_str=props['event'], condition_str=props['condition'],
                    action_language=props.get('action_language', DEFAULT_EXECUTION_ENV),
                    action_str=props['action'],
                    color=props.get('color'), description=props.get('description', "")
                )
                # Set curve offsets from dialog
                new_transition.set_control_point_offset(QPointF(props['control_offset_x'],props['control_offset_y']))

                # Add via UndoCommand
                cmd = AddItemCommand(self, new_transition, "Add Transition")
                self.undo_stack.push(cmd)
                self._log_to_parent("INFO", f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{new_transition._compose_label_string()}]")
            else: # Dialog cancelled
                self._log_to_parent("INFO", "Transition addition cancelled by user.")

            self.transition_start_item = None # Reset for next transition
            self.set_mode("select") # Revert to select mode after adding transition

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Delete or (event.key() == Qt.Key_Backspace and sys.platform != 'darwin'): # Backspace for delete on non-Mac
            if self.selectedItems():
                self.delete_selected_items()
        elif event.key() == Qt.Key_Escape:
            if self.current_mode == "transition" and self.transition_start_item:
                # Cancel ongoing transition drawing
                self.transition_start_item = None
                if self._temp_transition_line:
                    self.removeItem(self._temp_transition_line)
                    self._temp_transition_line = None
                self._log_to_parent("INFO", "Transition drawing cancelled by Escape.")
                self.set_mode("select") # Revert to select mode
            elif self.current_mode != "select": # If in any other non-select mode
                self.set_mode("select") # Revert to select mode
            else: # In select mode, Esc clears selection
                self.clearSelection()
        else:
            super().keyPressEvent(event)

    def delete_selected_items(self):
        selected = self.selectedItems()
        if not selected: return

        items_to_delete_with_related = set() # Use a set to avoid duplicates
        for item in selected:
            items_to_delete_with_related.add(item)
            # If a state is deleted, also delete its connected transitions
            if isinstance(item, GraphicsStateItem): 
                for scene_item in self.items(): # Iterate over all items in scene
                    if isinstance(scene_item, GraphicsTransitionItem):
                        if scene_item.start_item == item or scene_item.end_item == item:
                            items_to_delete_with_related.add(scene_item)

        if items_to_delete_with_related:
            cmd = RemoveItemsCommand(self, list(items_to_delete_with_related), "Delete Items")
            self.undo_stack.push(cmd)
            self._log_to_parent("INFO", f"Queued deletion of {len(items_to_delete_with_related)} item(s).")
            self.clearSelection() # Clear selection after queuing deletion

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
            item_type_data_str = event.mimeData().text() # Get data from mime (e.g., "State", "Initial State")

            # Snap drop position to grid
            grid_x = round(pos.x() / self.grid_size) * self.grid_size
            grid_y = round(pos.y() / self.grid_size) * self.grid_size

            # Adjust position for states to be centered on drop point
            if "State" in item_type_data_str: # Crude check, refine if more types are added
                grid_x -= 60 # Half default width
                grid_y -= 30 # Half default height

            initial_props_for_add = {} # Store any special initial properties (like is_initial)
            actual_item_type_to_add = "Item" # Default, will be overridden
            name_prefix_for_add = "Item" # Default prefix for new item names

            # Determine item type and initial properties from dropped data
            if item_type_data_str == "State":
                actual_item_type_to_add = "State"
                name_prefix_for_add = "State"
            elif item_type_data_str == "Initial State":
                actual_item_type_to_add = "State"
                name_prefix_for_add = "Initial" # Suggests "Initial1", "Initial2", etc.
                initial_props_for_add['is_initial'] = True
            elif item_type_data_str == "Final State":
                actual_item_type_to_add = "State"
                name_prefix_for_add = "Final"
                initial_props_for_add['is_final'] = True
            elif item_type_data_str == "Comment":
                actual_item_type_to_add = "Comment"
                name_prefix_for_add = "Note" # Suggests "Note1", "Note2" for comments
            else:
                self._log_to_parent("WARNING", f"Unknown item type dropped: {item_type_data_str}")
                event.ignore()
                return

            # Call the interactive add method with determined type and initial data
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
                if item.start_item and item.end_item: # Ensure transition is valid
                    data['transitions'].append(item.get_data())
                else:
                    # Log orphaned/invalid transitions but don't add to data
                    self._log_to_parent("WARNING", f"Skipping save of orphaned/invalid transition: '{item._compose_label_string()}'.")
            elif isinstance(item, GraphicsCommentItem):
                data['comments'].append(item.get_data())
        return data

    def load_diagram_data(self, data):
        self.clear() # Clear existing scene content
        self.set_dirty(False) # Reset dirty flag after loading
        state_items_map = {} # To link transitions by state name

        # Load states
        for state_data in data.get('states', []):
            state_item = GraphicsStateItem(
                state_data['x'], state_data['y'],
                state_data.get('width', 120), state_data.get('height', 60), # Default size if not specified
                state_data['name'],
                state_data.get('is_initial', False), state_data.get('is_final', False),
                state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG),
                state_data.get('entry_action',""), state_data.get('during_action',""),
                state_data.get('exit_action',""), state_data.get('description',""),
                state_data.get('is_superstate', False), 
                state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}), # Ensure valid default
                action_language=state_data.get('action_language', DEFAULT_EXECUTION_ENV)
            )
            self.addItem(state_item)
            state_items_map[state_data['name']] = state_item # Map name to item for transitions

        # Load transitions
        for trans_data in data.get('transitions', []):
            src_item = state_items_map.get(trans_data['source'])
            tgt_item = state_items_map.get(trans_data['target'])
            if src_item and tgt_item: # Ensure source and target states exist
                trans_item = GraphicsTransitionItem(
                    src_item, tgt_item,
                    event_str=trans_data.get('event',""), condition_str=trans_data.get('condition',""),
                    action_language=trans_data.get('action_language', DEFAULT_EXECUTION_ENV),
                    action_str=trans_data.get('action',""),
                    color=trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT),
                    description=trans_data.get('description',"")
                )
                # Set control point offsets for curved transitions
                trans_item.set_control_point_offset(QPointF(trans_data.get('control_offset_x',0), trans_data.get('control_offset_y',0)))
                self.addItem(trans_item)
            else:
                # Log warning if a transition cannot be linked
                label_info = f"{trans_data.get('event','')}{trans_data.get('condition','')}{trans_data.get('action','')}"
                self._log_to_parent("WARNING", f"Load Warning: Could not link transition '{label_info}' due to missing states: Source='{trans_data['source']}', Target='{trans_data['target']}'.")


        # Load comments
        for comment_data in data.get('comments', []):
            comment_item = GraphicsCommentItem(comment_data['x'], comment_data['y'], comment_data.get('text', ""))
            comment_item.setTextWidth(comment_data.get('width', 150)) # Set width if specified
            self.addItem(comment_item)

        self.set_dirty(False) # Should be clean after successful load
        if self.undo_stack: self.undo_stack.clear() # Clear undo stack for new file

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect) # Call base to draw default background (brush)

        # Get visible rect from view to optimize drawing
        view_rect = self.views()[0].viewport().rect() if self.views() else rect
        visible_scene_rect = self.views()[0].mapToScene(view_rect).boundingRect() if self.views() else rect

        # Calculate grid lines based on visible area and grid size
        left = int(visible_scene_rect.left() / self.grid_size) * self.grid_size - self.grid_size # Extend slightly beyond view
        right = int(visible_scene_rect.right() / self.grid_size) * self.grid_size + self.grid_size
        top = int(visible_scene_rect.top() / self.grid_size) * self.grid_size - self.grid_size
        bottom = int(visible_scene_rect.bottom() / self.grid_size) * self.grid_size + self.grid_size

        # Draw minor grid lines
        painter.setPen(self.grid_pen_light)
        for x in range(left, right, self.grid_size):
            if x % (self.grid_size * 5) != 0: # Skip major lines
                painter.drawLine(x, top, x, bottom)
        for y in range(top, bottom, self.grid_size):
            if y % (self.grid_size * 5) != 0: # Skip major lines
                painter.drawLine(left, y, right, y)

        # Draw major grid lines
        major_grid_size = self.grid_size * 5
        # Ensure major lines align correctly even with negative coordinates
        first_major_left = left - (left % major_grid_size) if left >=0 else left - (left % major_grid_size) - major_grid_size
        first_major_top = top - (top % major_grid_size) if top >= 0 else top - (top % major_grid_size) - major_grid_size

        painter.setPen(self.grid_pen_dark)
        for x in range(first_major_left, right, major_grid_size):
            painter.drawLine(x, top, x, bottom)
        for y in range(first_major_top, bottom, major_grid_size):
            painter.drawLine(left, y, right, y)

    # --- Validation Methods ---
    def validate_diagram(self) -> list:
        issues = []
        states = [item for item in self.items() if isinstance(item, GraphicsStateItem)]
        transitions = [item for item in self.items() if isinstance(item, GraphicsTransitionItem)]

        # 1. Check for at least one initial state
        initial_states = [s for s in states if s.is_initial]
        if not initial_states:
            issues.append(("error", "No initial state defined in the diagram.", None))
        elif len(initial_states) > 1:
            issues.append(("error", f"Multiple initial states defined: {[s.text_label for s in initial_states]}.", initial_states[0]))

        # 2. Check for duplicate state names
        state_names = {}
        for state in states:
            name = state.text_label
            if name in state_names:
                issues.append(("error", f"Duplicate state name: '{name}'.", state))
            else:
                state_names[name] = state
        
        # 3. Check for states with no incoming/outgoing transitions (excluding initial/final)
        for state in states:
            name = state.text_label
            has_incoming = any(t.end_item == state for t in transitions)
            has_outgoing = any(t.start_item == state for t in transitions)

            if not state.is_initial and not has_incoming:
                issues.append(("warning", f"State '{name}' has no incoming transitions and is not initial.", state))
            if not state.is_final and not has_outgoing:
                issues.append(("warning", f"State '{name}' has no outgoing transitions and is not final (potential trap state).", state))

        # 4. Check transitions for valid source/target (should be caught by item logic, but good to double check)
        for i, transition in enumerate(transitions):
            if not transition.start_item or not transition.end_item:
                issues.append(("error", f"Transition {i+1} (Label: '{transition._compose_label_string()}') has missing source or target state.", transition))
            elif transition.start_item.text_label not in state_names or transition.end_item.text_label not in state_names:
                 issues.append(("error", f"Transition {i+1} (Label: '{transition._compose_label_string()}') references non-existent source/target state by name.", transition))

        # 5. Check for superstates with empty or invalid sub-FSMs
        for state in states:
            if state.is_superstate:
                sub_fsm_data = state.sub_fsm_data
                if not sub_fsm_data or not isinstance(sub_fsm_data, dict) or \
                   'states' not in sub_fsm_data or 'transitions' not in sub_fsm_data:
                    issues.append(("error", f"Superstate '{state.text_label}' has invalid or missing sub_fsm_data structure.", state))
                elif not sub_fsm_data.get('states'):
                    issues.append(("warning", f"Superstate '{state.text_label}' has an empty sub-machine (no sub-states defined).", state))
                else: # Validate sub-machine initial state
                    sub_initial_states = [s for s in sub_fsm_data.get('states', []) if s.get('is_initial')]
                    if not sub_initial_states:
                        issues.append(("error", f"Sub-machine in superstate '{state.text_label}' has no initial state defined.", state))
                    elif len(sub_initial_states) > 1:
                        issues.append(("error", f"Sub-machine in superstate '{state.text_label}' has multiple initial states.", state))

        return issues

    def highlight_validation_issues(self, issues: list):
        self.clear_validation_highlights() # Clear previous ones
        for issue_type, message, item_ref_or_name in issues:
            item_to_highlight = None
            if isinstance(item_ref_or_name, QGraphicsItem):
                item_to_highlight = item_ref_or_name
            elif isinstance(item_ref_or_name, str): # If only name is provided
                item_to_highlight = self.get_state_by_name(item_ref_or_name)
            
            if item_to_highlight and hasattr(item_to_highlight, 'set_validation_highlight'):
                item_to_highlight.set_validation_highlight(issue_type)
                self._validation_highlighted_items.append(item_to_highlight)

    def clear_validation_highlights(self):
        for item in self._validation_highlighted_items:
            if hasattr(item, 'set_validation_highlight'):
                item.set_validation_highlight(None) # Clear highlight
        self._validation_highlighted_items = []
        self.update() # Force repaint of the scene

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
            if -15 <= new_zoom_level <= 25: # Limit zoom range
                self.scale(factor, factor)
                self.zoom_level = new_zoom_level
            event.accept()
        else: # Allow vertical scrolling if Ctrl not pressed
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = True
            self._last_pan_point = self.mapFromGlobal(QCursor.pos()) # Store last pan point in view coordinates
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal: # Zoom in
            self.scale(1.12, 1.12); self.zoom_level +=1
        elif event.key() == Qt.Key_Minus: # Zoom out
            self.scale(1/1.12, 1/1.12); self.zoom_level -=1
        elif event.key() == Qt.Key_0 or event.key() == Qt.Key_Asterisk: # Reset zoom and center
            self.resetTransform()
            self.zoom_level = 0
            if self.scene():
                content_rect = self.scene().itemsBoundingRect()
                if not content_rect.isEmpty():
                    self.centerOn(content_rect.center())
                elif self.scene().sceneRect(): # Fallback to sceneRect if no items
                    self.centerOn(self.scene().sceneRect().center())
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = False
            if not self._is_panning_with_mouse_button: # Restore cursor only if not also mouse panning
                self._restore_cursor_to_scene_mode()
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton or \
           (self._is_panning_with_space and event.button() == Qt.LeftButton): # Pan with Space + Left Click or Middle Mouse
            self._last_pan_point = event.pos() # Store click position in view coordinates
            self.setCursor(Qt.ClosedHandCursor)
            self._is_panning_with_mouse_button = True
            event.accept()
        else:
            self._is_panning_with_mouse_button = False # Reset flag if other buttons
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button:
            delta_view = event.pos() - self._last_pan_point # Calculate delta in view coordinates
            self._last_pan_point = event.pos()
            # Adjust scrollbar values directly for smooth panning
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta_view.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta_view.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button and \
           (event.button() == Qt.MiddleButton or (self._is_panning_with_space and event.button() == Qt.LeftButton)):
            self._is_panning_with_mouse_button = False
            if self._is_panning_with_space: # If space was held, revert to open hand
                self.setCursor(Qt.OpenHandCursor)
            else: # Otherwise, restore cursor based on scene mode
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
        else: # Default
            self.setCursor(Qt.ArrowCursor)