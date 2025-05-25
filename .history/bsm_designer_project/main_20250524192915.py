
import sys
import os
import tempfile
import subprocess
import json
import html
import math
import socket
import re
from PyQt5.QtCore import QTime, QTimer, QPointF
import pygraphviz as pgv # Ensure this is installed
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fsm_simulator import FSMSimulator, FSMError


from ai_chatbot import AIChatbotManager
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QToolBox, QAction,
    QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
    QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
    QFileDialog, QProgressBar, QTabWidget, QCheckBox, QActionGroup, QGraphicsItem,
    QGroupBox, QUndoStack, QUndoCommand, QStyle, QSizePolicy, QGraphicsLineItem,
    QToolButton, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent,
    QGraphicsSceneHoverEvent, QGraphicsTextItem, QGraphicsDropShadowEffect,
    QHeaderView, QTableWidget, QTableWidgetItem, QAbstractItemView
)
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform, QKeyEvent, QPainterPathStroker, QPolygonF, QKeySequence,
    QDesktopServices, QWheelEvent, QMouseEvent, QCloseEvent, QFontMetrics, QPalette
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QTimer, QSize, QUrl,
    QSaveFile, QIODevice
)

from config import (
    APP_VERSION, APP_NAME, FILE_EXTENSION, FILE_FILTER, STYLE_SHEET_GLOBAL,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG,
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_PRIMARY_LIGHT,
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_BACKGROUND_LIGHT, COLOR_GRID_MINOR, COLOR_GRID_MAJOR,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_ON_ACCENT,
    COLOR_ACCENT_SECONDARY, COLOR_BORDER_LIGHT, COLOR_BORDER_MEDIUM
)
from utils import get_standard_icon
from matlab_integration import MatlabConnection
from dialogs import (StatePropertiesDialog, TransitionPropertiesDialog, CommentPropertiesDialog,
                     MatlabSettingsDialog)

# DraggableToolButton class
class DraggableToolButton(QPushButton):
    def __init__(self, text, mime_type, item_type_data, parent=None):
        super().__init__(text, parent)
        self.setObjectName("DraggableToolButton")
        self.mime_type = mime_type
        self.item_type_data = item_type_data
        self.setText(text)
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.drag_start_position = QPoint()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.item_type_data)
        mime_data.setData(self.mime_type, self.item_type_data.encode())
        drag.setMimeData(mime_data)

        pixmap_size = QSize(max(150, self.width()), max(40, self.height()))
        pixmap = QPixmap(pixmap_size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        button_rect = QRectF(0, 0, pixmap_size.width() -1, pixmap_size.height() -1)
        bg_color = QColor(self.palette().color(self.backgroundRole())).lighter(110)
        if not bg_color.isValid() or bg_color.alpha() == 0:
            bg_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT)
        border_color_qcolor = QColor(COLOR_ACCENT_PRIMARY)

        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color_qcolor, 1.5))
        painter.drawRoundedRect(button_rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5)

        icon_pixmap = self.icon().pixmap(QSize(20, 20), QIcon.Normal, QIcon.On)
        text_x_offset = 10
        icon_y_offset = (pixmap_size.height() - icon_pixmap.height()) / 2
        if not icon_pixmap.isNull():
            painter.drawPixmap(int(text_x_offset), int(icon_y_offset), icon_pixmap)
            text_x_offset += icon_pixmap.width() + 8

        text_color_qcolor = self.palette().color(QPalette.ButtonText)
        if not text_color_qcolor.isValid():
            text_color_qcolor = QColor(COLOR_TEXT_PRIMARY)
        painter.setPen(text_color_qcolor)
        painter.setFont(self.font())

        text_rect = QRectF(text_x_offset, 0, pixmap_size.width() - text_x_offset - 5, pixmap_size.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 4, pixmap.height() // 2))
        drag.exec_(Qt.CopyAction | Qt.MoveAction)

# DiagramScene class
class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool)

    def __init__(self, undo_stack, parent_window=None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setSceneRect(0, 0, 6000, 4500)
        self.current_mode = "select"
        self.transition_start_item = None
        self.log_function = print
        self.undo_stack: QUndoStack = undo_stack
        self._dirty = False
        self._mouse_press_items_positions = {}
        self._temp_transition_line = None

        self.item_moved.connect(self._handle_item_moved_visual_update)

        self.grid_size = 20
        self.grid_pen_light = QPen(QColor(COLOR_GRID_MINOR), 0.7, Qt.DotLine)
        self.grid_pen_dark = QPen(QColor(COLOR_GRID_MAJOR), 0.9, Qt.SolidLine)
        self.setBackgroundBrush(QColor(COLOR_BACKGROUND_LIGHT))
        self.snap_to_grid_enabled = True

    def _update_connected_transitions(self, state_item: GraphicsStateItem):
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                if item.start_item == state_item or item.end_item == state_item:
                    item.update_path()

    def _update_transitions_for_renamed_state(self, old_name:str, new_name:str):
        # This method is called by EditItemPropertiesCommand.
        # It updates the string references in transition data if a state name changes.
        # This is important if transitions are re-created from data (e.g. during complex undo).
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                updated = False
                if item.start_item and item.start_item.text_label == new_name: # Check against new name if it's the current one
                    # This logic is a bit tricky. If this is called during an UNDO,
                    # `new_name` is actually the state's *old* name.
                    # The EditItemPropertiesCommand manages setting the properties.
                    # This function should ensure that if a state 'S1' is renamed to 'S2',
                    # any transition whose .get_data() would return 'S1' as source/target
                    # should reflect the new name if the state object itself is updated.
                    # The critical part is that GraphicsTransitionItem.get_data()
                    # gets the name from its linked start_item/end_item.text_label directly.
                    # So, if the state item's text_label is updated, get_data() is fine.
                    # This function primarily ensures visual path updates if needed,
                    # or if we were storing source/target names separately in GraphicsTransitionItem.
                    pass # Handled by item.update_path() if visuals change

                if item.end_item and item.end_item.text_label == new_name:
                    pass
                # If the transition item itself stored names, they would be updated here.
                # Since it gets names from linked items, just ensuring paths are updated is key.
                # item.update_path() # Called by _handle_item_moved_visual_update or after property edit
        self.log_function(f"Scene notified: State '{old_name}' changed to '{new_name}'. Dependent transitions' data should reflect this if they store names.", type_hint="GENERAL")


    def get_state_by_name(self, name: str) -> GraphicsStateItem | None:
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name:
                return item
        return None

    def set_dirty(self, dirty=True):
        if self._dirty != dirty:
            self._dirty = dirty
            self.modifiedStatusChanged.emit(dirty)
        if self.parent_window:
             self.parent_window._update_save_actions_enable_state()

    def is_dirty(self):
        return self._dirty

    def set_log_function(self, log_function):
        self.log_function = log_function

    def set_mode(self, mode: str):
        old_mode = self.current_mode
        if old_mode == mode: return
        self.current_mode = mode
        self.log_function(f"Interaction mode changed to: {mode}", type_hint="GENERAL")
        self.transition_start_item = None
        if self._temp_transition_line:
            self.removeItem(self._temp_transition_line)
            self._temp_transition_line = None
        if self.parent_window and self.parent_window.view:
            self.parent_window.view._restore_cursor_to_scene_mode()

        for item in self.items():
            movable_flag = mode == "select"
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)):
                item.setFlag(QGraphicsItem.ItemIsMovable, movable_flag)

        if self.parent_window:
            actions_map = { 
                "select": self.parent_window.select_mode_action,
                "state": self.parent_window.add_state_mode_action,
                "transition": self.parent_window.add_transition_mode_action,
                "comment": self.parent_window.add_comment_mode_action
            }
            for m, action_obj in actions_map.items(): 
                if m == mode and action_obj and hasattr(action_obj, 'isChecked') and not action_obj.isChecked():
                    action_obj.setChecked(True)

    def select_all(self):
        for item in self.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable:
                item.setSelected(True)

    def _handle_item_moved_visual_update(self, moved_item):
        # This is primarily for visual updates during/after a move.
        # The undoable command for the move is created in mouseReleaseEvent.
        if isinstance(moved_item, GraphicsStateItem):
            self._update_connected_transitions(moved_item)
        # This signal does not set the scene dirty by itself; MoveItemsCommand does.


    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos()
        items_at_pos = self.items(pos)
        top_item_at_pos = next((item for item in items_at_pos if isinstance(item, GraphicsStateItem)), None)
        if not top_item_at_pos:
            top_item_at_pos = next((item for item in items_at_pos if isinstance(item, (GraphicsCommentItem, GraphicsTransitionItem))), None)
            if not top_item_at_pos and items_at_pos: top_item_at_pos = items_at_pos[0]

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
                        self.log_function("Transition drawing cancelled (clicked non-state/empty space).", type_hint="GENERAL")
                    self.transition_start_item = None
                    if self._temp_transition_line:
                        self.removeItem(self._temp_transition_line)
                        self._temp_transition_line = None
            else: # select mode
                self._mouse_press_items_positions.clear()
                selected_items_list = self.selectedItems()
                if selected_items_list:
                    for item_to_process in [item for item in selected_items_list if item.flags() & QGraphicsItem.ItemIsMovable]:
                        self._mouse_press_items_positions[item_to_process] = item_to_process.pos()
                super().mousePressEvent(event) 
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
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, event.scenePos()))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            if self._mouse_press_items_positions:
                moved_items_data_for_command = [] 
                emit_item_moved_for_these = []

                for item, old_pos in self._mouse_press_items_positions.items():
                    new_pos = item.pos()
                    snapped_new_pos = new_pos
                    if self.snap_to_grid_enabled:
                        snapped_x = round(new_pos.x() / self.grid_size) * self.grid_size
                        snapped_y = round(new_pos.y() / self.grid_size) * self.grid_size
                        snapped_new_pos = QPointF(snapped_x, snapped_y)
                        if new_pos != snapped_new_pos:
                             item.setPos(snapped_new_pos) # Apply snap before recording new_pos for command

                    if (snapped_new_pos - old_pos).manhattanLength() > 0.1: 
                        moved_items_data_for_command.append((item, old_pos, snapped_new_pos))
                        emit_item_moved_for_these.append(item)
                
                if moved_items_data_for_command:
                    cmd = MoveItemsCommand(moved_items_data_for_command, "Move Items")
                    self.undo_stack.push(cmd)
                    # MoveItemsCommand will call scene.set_dirty(True)
                    # Visual update of connected transitions for states is handled by MoveItemsCommand's _apply_positions
                    # No need to emit item_moved here, as the command handles the state change.
                    # However, if other parts of the UI rely on item_moved for non-undo related updates,
                    # you might consider emitting it, but ensure it doesn't cause issues with undo stack.
                    # For now, assume command handles all necessary updates.

                self._mouse_press_items_positions.clear()
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
        old_props = item.get_data()
        dialog_executed_and_accepted = False
        new_props_from_dialog = None
        DialogType = None

        if isinstance(item, GraphicsStateItem): DialogType = StatePropertiesDialog
        elif isinstance(item, GraphicsTransitionItem): DialogType = TransitionPropertiesDialog
        elif isinstance(item, GraphicsCommentItem): DialogType = CommentPropertiesDialog
        else: return

        dialog = DialogType(parent=self.parent_window, current_properties=old_props)
        if dialog.exec_() == QDialog.Accepted:
            dialog_executed_and_accepted = True
            new_props_from_dialog = dialog.get_properties()

            if isinstance(item, GraphicsStateItem):
                old_name = old_props.get('name')
                current_new_name = new_props_from_dialog.get('name')
                existing_state_with_new_name = self.get_state_by_name(current_new_name)
                if current_new_name != old_name and existing_state_with_new_name and existing_state_with_new_name != item:
                    QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state with the name '{current_new_name}' already exists.")
                    return 

        if dialog_executed_and_accepted and new_props_from_dialog is not None:
            final_new_props = old_props.copy()
            final_new_props.update(new_props_from_dialog)

            if final_new_props == old_props:
                self.log_function("Properties unchanged.", type_hint="GENERAL")
                return

            cmd = EditItemPropertiesCommand(item, old_props, final_new_props, f"Edit {type(item).__name__} Properties")
            self.undo_stack.push(cmd)
            # EditItemPropertiesCommand calls set_dirty and _update_transitions_for_renamed_state

            item_name_for_log = final_new_props.get('name', final_new_props.get('event', final_new_props.get('text', 'Item')))
            self.log_function(f"Properties updated for: {item_name_for_log}", type_hint="GENERAL")
            # No need to call _update_transitions_for_renamed_state here, command does it.

        self.update() 

    def _add_item_interactive(self, pos: QPointF, item_type: str, name_prefix:str="Item", initial_data:dict=None):
        current_item = None
        initial_data = initial_data or {}
        is_initial_state_from_drag = initial_data.get('is_initial', False)
        is_final_state_from_drag = initial_data.get('is_final', False)

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
                'entry_action':"", 'during_action':"", 'exit_action':"", 'description':"",
                'is_superstate': False, 'sub_fsm_data': {'states': [], 'transitions': [], 'comments': []} # Default for new superstate
            }
            props_dialog = StatePropertiesDialog(self.parent_window, current_properties=initial_dialog_props, is_new_state=True, scene_ref=self)

            if props_dialog.exec_() == QDialog.Accepted:
                final_props = props_dialog.get_properties()
                if self.get_state_by_name(final_props['name']) and final_props['name'] != default_name: 
                    QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state named '{final_props['name']}' already exists.")
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
                        final_props.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]})
                    )
            if self.current_mode == "state": 
                self.set_mode("select")
            if not current_item: return 

        elif item_type == "Comment":
            initial_text = initial_data.get('text', "Comment" if name_prefix == "Item" else name_prefix)
            comment_props_dialog = CommentPropertiesDialog(self.parent_window, {'text': initial_text}) 

            if comment_props_dialog.exec_() == QDialog.Accepted:
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
            self.log_function(f"Unknown item type for addition: {item_type}", type_hint="GENERAL")
            return

        if current_item:
            cmd = AddItemCommand(self, current_item, f"Add {item_type}")
            self.undo_stack.push(cmd)
            # AddItemCommand handles scene.addItem and scene.set_dirty
            log_name = getattr(current_item, 'text_label', None) or \
                       (getattr(current_item, 'toPlainText', lambda: "Item")() if isinstance(current_item, GraphicsCommentItem) else "Item")
            self.log_function(f"Added {item_type}: {log_name} at ({pos.x():.0f},{pos.y():.0f})", type_hint="GENERAL")


    def _handle_transition_click(self, clicked_state_item: GraphicsStateItem, click_pos: QPointF):
        if not self.transition_start_item: 
            self.transition_start_item = clicked_state_item
            if not self._temp_transition_line:
                self._temp_transition_line = QGraphicsLineItem()
                self._temp_transition_line.setPen(QPen(QColor(COLOR_ACCENT_PRIMARY), 1.8, Qt.DashLine))
                self.addItem(self._temp_transition_line) 
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, click_pos))
            self.log_function(f"Transition started from: {clicked_state_item.text_label}. Click target state.", type_hint="GENERAL")
        else: 
            if self._temp_transition_line: 
                self.removeItem(self._temp_transition_line)
                self._temp_transition_line = None

            initial_props = { 
                'event': "", 'condition': "", 'action': "",
                'color': COLOR_ITEM_TRANSITION_DEFAULT, 'description':"",
                'control_offset_x':0, 'control_offset_y':0
            }
            dialog = TransitionPropertiesDialog(self.parent_window, current_properties=initial_props, is_new_transition=True)

            if dialog.exec_() == QDialog.Accepted:
                props = dialog.get_properties()
                new_transition = GraphicsTransitionItem(
                    self.transition_start_item, clicked_state_item,
                    event_str=props['event'], condition_str=props['condition'], action_str=props['action'],
                    color=props.get('color'), description=props.get('description', "")
                )
                new_transition.set_control_point_offset(QPointF(props['control_offset_x'],props['control_offset_y']))

                cmd = AddItemCommand(self, new_transition, "Add Transition")
                self.undo_stack.push(cmd)
                self.log_function(f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{new_transition._compose_label_string()}]", type_hint="GENERAL")
            else: 
                self.log_function("Transition addition cancelled by user.", type_hint="GENERAL")

            self.transition_start_item = None 
            self.set_mode("select") 

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Delete or (event.key() == Qt.Key_Backspace and sys.platform != 'darwin'): 
            if self.selectedItems():
                self.delete_selected_items()
        elif event.key() == Qt.Key_Escape:
            if self.current_mode == "transition" and self.transition_start_item:
                self.transition_start_item = None
                if self._temp_transition_line:
                    self.removeItem(self._temp_transition_line)
                    self._temp_transition_line = None
                self.log_function("Transition drawing cancelled by Escape.", type_hint="GENERAL")
                self.set_mode("select")
            elif self.current_mode != "select":
                self.set_mode("select")
            else: 
                self.clearSelection()
        else:
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
            # RemoveItemsCommand handles removing items and setting dirty status
            self.log_function(f"Queued deletion of {len(items_to_delete_with_related)} item(s).", type_hint="GENERAL")
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
                self.log_function(f"Unknown item type dropped: {item_type_data_str}", type_hint="GENERAL")
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
                    self.log_function(f"Warning: Skipping save of orphaned/invalid transition: '{item._compose_label_string()}'.", type_hint="GENERAL")
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
                state_data.get('is_superstate', False), # Load superstate property
                state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}) # Load sub_fsm_data
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
                    action_str=trans_data.get('action',""),
                    color=trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT),
                    description=trans_data.get('description',"")
                )
                trans_item.set_control_point_offset(QPointF(trans_data.get('control_offset_x',0), trans_data.get('control_offset_y',0)))
                self.addItem(trans_item)
            else:
                self.log_function(f"Warning (Load): Could not link transition '{trans_data.get('event','')}{trans_data.get('condition','')}{trans_data.get('action','')}' due to missing states: Source='{trans_data['source']}', Target='{trans_data['target']}'.", type_hint="GENERAL")

        for comment_data in data.get('comments', []):
            comment_item = GraphicsCommentItem(comment_data['x'], comment_data['y'], comment_data.get('text', ""))
            comment_item.setTextWidth(comment_data.get('width', 150)) 
            self.addItem(comment_item)

        self.set_dirty(False) 
        self.undo_stack.clear() 

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


# ZoomableView class
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
            if -15 <= new_zoom_level <= 25: 
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
            self.scale(1.12, 1.12); self.zoom_level +=1
        elif event.key() == Qt.Key_Minus:
            self.scale(1/1.12, 1/1.12); self.zoom_level -=1
        elif event.key() == Qt.Key_0 or event.key() == Qt.Key_Asterisk: 
            self.resetTransform()
            self.zoom_level = 0
            if self.scene():
                content_rect = self.scene().itemsBoundingRect()
                if not content_rect.isEmpty():
                    self.centerOn(content_rect.center())
                elif self.scene().sceneRect(): 
                    self.centerOn(self.scene().sceneRect().center())
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


# MainWindow class
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_file_path = None
        self.last_generated_model_path = None 
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)

        self.ai_chatbot_manager = AIChatbotManager(self) 
        self.scene = DiagramScene(self.undo_stack, self) 
        self.scene.set_log_function(self.log_message)
        self.scene.modifiedStatusChanged.connect(self.setWindowModified) 
        self.scene.modifiedStatusChanged.connect(self._update_window_title) 

        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False
        self._py_sim_currently_highlighted_item: GraphicsStateItem | None = None
        self._py_sim_currently_highlighted_transition: GraphicsTransitionItem | None = None 

        self._internet_connected: bool | None = None 
        self.internet_check_timer = QTimer(self) 

        self.init_ui() 

        # Connect signals from AIChatbotManager
        self.ai_chatbot_manager.statusUpdate.connect(self._update_ai_chat_status)
        self.ai_chatbot_manager.errorOccurred.connect(self._handle_ai_error)
        self.ai_chatbot_manager.fsmDataReceived.connect(self._handle_fsm_data_from_ai)
        self.ai_chatbot_manager.plainResponseReady.connect(self._handle_plain_ai_response) # <--- ADD THIS LINE



        



        self.ai_chat_display.setObjectName("AIChatDisplay")
        self.ai_chat_input.setObjectName("AIChatInput")
        self.ai_chat_send_button.setObjectName("AIChatSendButton")
        self.ai_chat_status_label.setObjectName("AIChatStatusLabel")
        self._update_ai_chat_status("Status: API Key required. Configure in Settings.") 

        self.matlab_status_label.setObjectName("MatlabStatusLabel")
        self.py_sim_status_label.setObjectName("PySimStatusLabel")
        self.internet_status_label.setObjectName("InternetStatusLabel")
        self.status_label.setObjectName("StatusLabel") 

        self._update_matlab_status_display(False, "Initializing. Configure MATLAB settings or attempt auto-detect.")
        self._update_py_sim_status_display()

        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)

        self._update_window_title()
        self.on_new_file(silent=True) 
        self._init_internet_status_check() 
        self.scene.selectionChanged.connect(self._update_properties_dock)
        self._update_properties_dock() 
        self._update_py_simulation_actions_enabled_state() 

        if not self.ai_chatbot_manager.api_key:
            self._update_ai_chat_status("Status: API Key required. Configure in Settings.")
        else:
            self._update_ai_chat_status("Status: Ready.")

    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050) 
        self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM")) 
        self._create_central_widget()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_docks()
        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()
        self.select_mode_action.trigger() 

    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self)
        self.view.setObjectName("MainDiagramView")
        self.setCentralWidget(self.view)

    def _create_actions(self):
        def _safe_get_style_enum(attr_name, fallback_attr_name=None):
            try: return getattr(QStyle, attr_name)
            except AttributeError:
                if fallback_attr_name:
                    try: return getattr(QStyle, fallback_attr_name)
                    except AttributeError: pass
                return QStyle.SP_CustomBase 

        self.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "New"), "&New", self, shortcut=QKeySequence.New, statusTip="Create a new file", triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "Opn"), "&Open...", self, shortcut=QKeySequence.Open, statusTip="Open an existing file", triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Sav"), "&Save", self, shortcut=QKeySequence.Save, statusTip="Save the current file", triggered=self.on_save_file)
        self.save_as_action = QAction(get_standard_icon(QStyle.SP_DriveHDIcon),"Save &As...", self, shortcut=QKeySequence.SaveAs, statusTip="Save the current file with a new name", triggered=self.on_save_file_as)
        self.export_simulink_action = QAction(get_standard_icon(_safe_get_style_enum("SP_ArrowUp","SP_ArrowRight"), "->M"), "&Export to Simulink...", self, triggered=self.on_export_simulink)
        self.exit_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", self, shortcut=QKeySequence.Quit, statusTip="Exit the application", triggered=self.close)

        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "Un"))
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "Re"))
        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.undo_stack.canRedoChanged.connect(self._update_undo_redo_actions_enable_state)

        self.select_all_action = QAction(get_standard_icon(_safe_get_style_enum("SP_FileDialogListView", "SP_FileDialogDetailedView"), "All"), "Select &All", self, shortcut=QKeySequence.SelectAll, triggered=self.on_select_all)
        self.delete_action = QAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "&Delete", self, shortcut=QKeySequence.Delete, triggered=self.on_delete_selected)

        self.mode_action_group = QActionGroup(self)
        self.mode_action_group.setExclusive(True)
        self.select_mode_action = QAction(QIcon.fromTheme("edit-select", get_standard_icon(QStyle.SP_ArrowRight, "Sel")), "Select/Move", self, checkable=True, triggered=lambda: self.scene.set_mode("select"))
        self.select_mode_action.setObjectName("select_mode_action")
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", get_standard_icon(QStyle.SP_FileDialogNewFolder, "St")), "Add State", self, checkable=True, triggered=lambda: self.scene.set_mode("state"))
        self.add_state_mode_action.setObjectName("add_state_mode_action")
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", get_standard_icon(QStyle.SP_ArrowForward, "Tr")), "Add Transition", self, checkable=True, triggered=lambda: self.scene.set_mode("transition"))
        self.add_transition_mode_action.setObjectName("add_transition_mode_action")
        self.add_comment_mode_action = QAction(QIcon.fromTheme("insert-text", get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm")), "Add Comment", self, checkable=True, triggered=lambda: self.scene.set_mode("comment"))
        self.add_comment_mode_action.setObjectName("add_comment_mode_action")
        for action in [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action]:
            self.mode_action_group.addAction(action)
        self.select_mode_action.setChecked(True) 

        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation (MATLAB)...", self, triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"), "Generate &Code (C/C++ via MATLAB)...", self, triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"), "&MATLAB Settings...", self, triggered=self.on_matlab_settings)

        self.start_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Py▶"), "&Start Python Simulation", self, statusTip="Start internal FSM simulation", triggered=self.on_start_py_simulation)
        self.stop_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaStop, "Py■"), "S&top Python Simulation", self, statusTip="Stop internal FSM simulation", triggered=self.on_stop_py_simulation, enabled=False)
        self.reset_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaSkipBackward, "Py«"), "&Reset Python Simulation", self, statusTip="Reset internal FSM simulation to initial state", triggered=self.on_reset_py_simulation, enabled=False)

        self.openai_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "AISet"), "AI Assistant Settings...", self, triggered=self.on_openai_settings)
        self.clear_ai_chat_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "Clear"), "Clear Chat History", self, triggered=self.on_clear_ai_chat_history)
        self.ask_ai_to_generate_fsm_action = QAction(QIcon.fromTheme("system-run", get_standard_icon(QStyle.SP_DialogYesButton, "AIGen")), "Generate FSM from Description...", self, triggered=self.on_ask_ai_to_generate_fsm)

        self.open_example_menu_action = QAction("Open E&xample...", self) 
        self.quick_start_action = QAction(get_standard_icon(QStyle.SP_MessageBoxQuestion, "QS"), "&Quick Start Guide", self, triggered=self.on_show_quick_start)
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, triggered=self.on_about)

    def _create_menus(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        example_menu = file_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ex"), "Open E&xample")
        self.open_example_traffic_action = example_menu.addAction("Traffic Light FSM", lambda: self._open_example_file("traffic_light.bsm"))
        self.open_example_toggle_action = example_menu.addAction("Simple Toggle FSM", lambda: self._open_example_file("simple_toggle.bsm"))
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_simulink_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.delete_action)
        edit_menu.addAction(self.select_all_action)
        edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Mode"),"Interaction Mode")
        mode_menu.addAction(self.select_mode_action)
        mode_menu.addAction(self.add_state_mode_action)
        mode_menu.addAction(self.add_transition_mode_action)
        mode_menu.addAction(self.add_comment_mode_action)

        sim_menu = menu_bar.addMenu("&Simulation")
        py_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_MediaPlay, "PyS"), "Python Simulation (Internal)")
        py_sim_menu.addAction(self.start_py_sim_action)
        py_sim_menu.addAction(self.stop_py_sim_action)
        py_sim_menu.addAction(self.reset_py_sim_action)
        sim_menu.addSeparator()
        matlab_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_ComputerIcon, "M"), "MATLAB/Simulink")
        matlab_sim_menu.addAction(self.run_simulation_action)
        matlab_sim_menu.addAction(self.generate_code_action)
        matlab_sim_menu.addSeparator()
        matlab_sim_menu.addAction(self.matlab_settings_action)

        self.view_menu = menu_bar.addMenu("&View")

        ai_menu = menu_bar.addMenu("&AI Assistant")
        ai_menu.addAction(self.ask_ai_to_generate_fsm_action)
        ai_menu.addAction(self.clear_ai_chat_action)
        ai_menu.addSeparator()
        ai_menu.addAction(self.openai_settings_action)

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.quick_start_action)
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(22,22)
        tb_style = Qt.ToolButtonTextBesideIcon

        file_toolbar = self.addToolBar("File")
        file_toolbar.setObjectName("FileToolBar")
        file_toolbar.setIconSize(icon_size)
        file_toolbar.setToolButtonStyle(tb_style)
        file_toolbar.addAction(self.new_action)
        file_toolbar.addAction(self.open_action)
        file_toolbar.addAction(self.save_action)

        edit_toolbar = self.addToolBar("Edit")
        edit_toolbar.setObjectName("EditToolBar")
        edit_toolbar.setIconSize(icon_size)
        edit_toolbar.setToolButtonStyle(tb_style) 
        edit_toolbar.addAction(self.undo_action)
        edit_toolbar.addAction(self.redo_action)
        edit_toolbar.addSeparator()
        edit_toolbar.addAction(self.delete_action)

        tools_tb = self.addToolBar("Interaction Tools")
        tools_tb.setObjectName("ToolsToolBar")
        tools_tb.setIconSize(icon_size)
        tools_tb.setToolButtonStyle(tb_style)
        tools_tb.addAction(self.select_mode_action)
        tools_tb.addAction(self.add_state_mode_action)
        tools_tb.addAction(self.add_transition_mode_action)
        tools_tb.addAction(self.add_comment_mode_action)

        sim_toolbar = self.addToolBar("Simulation Tools")
        sim_toolbar.setObjectName("SimulationToolBar")
        sim_toolbar.setIconSize(icon_size)
        sim_toolbar.setToolButtonStyle(tb_style)
        sim_toolbar.addAction(self.start_py_sim_action)
        sim_toolbar.addAction(self.stop_py_sim_action)
        sim_toolbar.addAction(self.reset_py_sim_action)
        sim_toolbar.addSeparator()
        sim_toolbar.addAction(self.export_simulink_action) 
        sim_toolbar.addAction(self.run_simulation_action)
        sim_toolbar.addAction(self.generate_code_action)

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready") 
        self.status_bar.addWidget(self.status_label, 1) 

        self.py_sim_status_label = QLabel("PySim: Idle")
        self.py_sim_status_label.setToolTip("Internal Python FSM Simulation Status.")
        self.status_bar.addPermanentWidget(self.py_sim_status_label)

        self.matlab_status_label = QLabel("MATLAB: Initializing...")
        self.matlab_status_label.setToolTip("MATLAB connection status.")
        self.status_bar.addPermanentWidget(self.matlab_status_label)

        self.internet_status_label = QLabel("Internet: Init...")
        self.internet_status_label.setToolTip("Internet connectivity status. Checks periodically.")
        self.status_bar.addPermanentWidget(self.internet_status_label)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0,0) 
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setTextVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)

        self.tools_dock = QDockWidget("Tools", self)
        self.tools_dock.setObjectName("ToolsDock")
        self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_widget_main = QWidget()
        tools_widget_main.setObjectName("ToolsDockWidgetContents")
        tools_main_layout = QVBoxLayout(tools_widget_main)
        tools_main_layout.setSpacing(10)
        tools_main_layout.setContentsMargins(5,5,5,5)

        mode_group_box = QGroupBox("Interaction Modes")
        mode_layout = QVBoxLayout()
        mode_layout.setSpacing(5)
        self.toolbox_select_button = QToolButton(); self.toolbox_select_button.setDefaultAction(self.select_mode_action)
        self.toolbox_add_state_button = QToolButton(); self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action)
        self.toolbox_transition_button = QToolButton(); self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action)
        self.toolbox_add_comment_button = QToolButton(); self.toolbox_add_comment_button.setDefaultAction(self.add_comment_mode_action)
        for btn in [self.toolbox_select_button, self.toolbox_add_state_button, self.toolbox_transition_button, self.toolbox_add_comment_button]:
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setIconSize(QSize(18,18))
            mode_layout.addWidget(btn)
        mode_group_box.setLayout(mode_layout)
        tools_main_layout.addWidget(mode_group_box)

        draggable_group_box = QGroupBox("Drag New Elements")
        draggable_layout = QVBoxLayout()
        draggable_layout.setSpacing(5)
        drag_state_btn = DraggableToolButton(" State", "application/x-bsm-tool", "State")
        drag_state_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))
        drag_initial_state_btn = DraggableToolButton(" Initial State", "application/x-bsm-tool", "Initial State")
        drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt")) 
        drag_final_state_btn = DraggableToolButton(" Final State", "application/x-bsm-tool", "Final State")
        drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt")) 
        drag_comment_btn = DraggableToolButton(" Comment", "application/x-bsm-tool", "Comment")
        drag_comment_btn.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))
        for btn in [drag_state_btn, drag_initial_state_btn, drag_final_state_btn, drag_comment_btn]:
            btn.setIconSize(QSize(18,18))
            draggable_layout.addWidget(btn)
        draggable_group_box.setLayout(draggable_layout)
        tools_main_layout.addWidget(draggable_group_box)

        tools_main_layout.addStretch()
        self.tools_dock.setWidget(tools_widget_main)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock)
        self.view_menu.addAction(self.tools_dock.toggleViewAction())

        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        properties_widget = QWidget()
        properties_layout = QVBoxLayout(properties_widget)
        properties_layout.setContentsMargins(5,5,5,5)
        properties_layout.setSpacing(5)
        self.properties_editor_label = QLabel("<i>No item selected.</i><br><small>Click an item in the diagram or use tools to add new items.</small>")
        self.properties_editor_label.setWordWrap(True)
        self.properties_editor_label.setTextFormat(Qt.RichText)
        self.properties_editor_label.setAlignment(Qt.AlignTop)
        self.properties_editor_label.setStyleSheet(f"padding: 5px; background-color: {COLOR_BACKGROUND_LIGHT}; border: 1px solid {COLOR_BORDER_MEDIUM};")
        properties_layout.addWidget(self.properties_editor_label, 1) 
        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"),"Edit Properties")
        self.properties_edit_button.setEnabled(False)
        self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock)
        properties_layout.addWidget(self.properties_edit_button)
        self.properties_dock.setWidget(properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        self.view_menu.addAction(self.properties_dock.toggleViewAction())

        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(5,5,5,5)
        self.log_output = QTextEdit()
        self.log_output.setObjectName("LogOutput")
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("font-family: Consolas, monospace; font-size: 9pt;")
        self.log_output.setHtml(f"<span style='color:{COLOR_TEXT_SECONDARY};'>[Starting log...]</span>")
        log_layout.addWidget(self.log_output)
        self.log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.view_menu.addAction(self.log_dock.toggleViewAction())

        self.py_sim_dock = QDockWidget("Python Simulation", self)
        self.py_sim_dock.setObjectName("PySimDock")
        self.py_sim_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        py_sim_widget = QWidget()
        py_sim_layout = QVBoxLayout(py_sim_widget)
        py_sim_layout.setContentsMargins(5,5,5,5)
        py_sim_layout.setSpacing(5)

        controls_group = QGroupBox("Controls")
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(5)
        self.py_sim_start_btn = QToolButton(); self.py_sim_start_btn.setDefaultAction(self.start_py_sim_action)
        self.py_sim_stop_btn = QToolButton(); self.py_sim_stop_btn.setDefaultAction(self.stop_py_sim_action)
        self.py_sim_reset_btn = QToolButton(); self.py_sim_reset_btn.setDefaultAction(self.reset_py_sim_action)
        self.py_sim_step_btn = QPushButton(get_standard_icon(QStyle.SP_MediaSeekForward, "Step"),"Step")
        self.py_sim_step_btn.clicked.connect(self.on_step_py_simulation)
        for btn in [self.py_sim_start_btn, self.py_sim_stop_btn, self.py_sim_reset_btn]:
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly); btn.setIconSize(QSize(18,18)); controls_layout.addWidget(btn)
        controls_layout.addWidget(self.py_sim_step_btn)
        controls_layout.addStretch()
        controls_group.setLayout(controls_layout)
        py_sim_layout.addWidget(controls_group)

        event_group = QGroupBox("Event Trigger")
        event_layout = QHBoxLayout()
        event_layout.setSpacing(5)
        self.py_sim_event_combo = QComboBox() 
        self.py_sim_event_combo.addItem("None (Internal Step)") 
        self.py_sim_event_combo.setEditable(False) 
        event_layout.addWidget(self.py_sim_event_combo, 1)

        self.py_sim_event_name_edit = QLineEdit()
        self.py_sim_event_name_edit.setPlaceholderText("Custom event name")
        event_layout.addWidget(self.py_sim_event_name_edit, 1)
        self.py_sim_trigger_event_btn = QPushButton(get_standard_icon(QStyle.SP_MediaPlay, "Trg"),"Trigger")
        self.py_sim_trigger_event_btn.clicked.connect(self.on_trigger_py_event) 
        event_layout.addWidget(self.py_sim_trigger_event_btn)
        event_group.setLayout(event_layout)
        py_sim_layout.addWidget(event_group)

        state_group = QGroupBox("Current State")
        state_layout = QVBoxLayout()
        self.py_sim_current_state_label = QLabel("<i>Not Running</i>")
        self.py_sim_current_state_label.setStyleSheet("font-size: 9pt; padding: 3px;")
        state_layout.addWidget(self.py_sim_current_state_label)
        state_group.setLayout(state_layout)
        py_sim_layout.addWidget(state_group)

        variables_group = QGroupBox("Variables")
        variables_layout = QVBoxLayout()
        self.py_sim_variables_table = QTableWidget()
        self.py_sim_variables_table.setRowCount(0); self.py_sim_variables_table.setColumnCount(2)
        self.py_sim_variables_table.setHorizontalHeaderLabels(["Name", "Value"])
        self.py_sim_variables_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.py_sim_variables_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.py_sim_variables_table.setEditTriggers(QAbstractItemView.NoEditTriggers) 
        variables_layout.addWidget(self.py_sim_variables_table)
        variables_group.setLayout(variables_layout)
        py_sim_layout.addWidget(variables_group)

        log_group = QGroupBox("Action Log")
        log_layout = QVBoxLayout()
        self.py_sim_action_log_output = QTextEdit()
        self.py_sim_action_log_output.setReadOnly(True)
        self.py_sim_action_log_output.setObjectName("PySimActionLog") # For specific styling
        self.py_sim_action_log_output.setHtml("<i>Simulation log will appear here...</i>")
        log_layout.addWidget(self.py_sim_action_log_output)
        log_group.setLayout(log_layout)
        py_sim_layout.addWidget(log_group, 1) 

        self.py_sim_dock.setWidget(py_sim_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock)
        self.view_menu.addAction(self.py_sim_dock.toggleViewAction())

        self.ai_chatbot_dock = QDockWidget("AI Chatbot", self)
        self.ai_chatbot_dock.setObjectName("AIChatbotDock")
        self.ai_chatbot_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        ai_chat_widget = QWidget()
        ai_chat_layout = QVBoxLayout(ai_chat_widget)
        ai_chat_layout.setContentsMargins(5,5,5,5)
        ai_chat_layout.setSpacing(5)
        self.ai_chat_display = QTextEdit() 
        self.ai_chat_display.setReadOnly(True)
        self.ai_chat_display.setStyleSheet("font-size: 9pt; padding: 5px;")
        self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
        ai_chat_layout.addWidget(self.ai_chat_display, 1) 

        input_layout = QHBoxLayout()
        self.ai_chat_input = QLineEdit() 
        self.ai_chat_input.setPlaceholderText("Type your message to the AI...")
        self.ai_chat_input.returnPressed.connect(self.on_send_ai_chat_message) # Corrected: MainWindow method
        input_layout.addWidget(self.ai_chat_input, 1)
        self.ai_chat_send_button = QPushButton(get_standard_icon(QStyle.SP_ArrowForward, "Snd"),"Send") 
        self.ai_chat_send_button.clicked.connect(self.on_send_ai_chat_message) # Corrected: MainWindow method
        input_layout.addWidget(self.ai_chat_send_button)
        ai_chat_layout.addLayout(input_layout)

        self.ai_chat_status_label = QLabel("Status: Initializing...") 
        self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;")
        ai_chat_layout.addWidget(self.ai_chat_status_label)

        self.ai_chatbot_dock.setWidget(ai_chat_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock)
        self.view_menu.addAction(self.ai_chatbot_dock.toggleViewAction())

        self.tabifyDockWidget(self.properties_dock, self.ai_chatbot_dock)
        self.tabifyDockWidget(self.ai_chatbot_dock, self.py_sim_dock) 

    # --- AI Chatbot Methods ---
    def on_ask_ai_to_generate_fsm(self):
        description, ok = QInputDialog.getMultiLineText(
            self, "Generate FSM", "Describe the FSM you want to create:",
            "Example: A traffic light with states Red, Yellow, Green. Event 'TIMER_EXPIRED' cycles through them."
        )
        if ok and description.strip():
            self.log_message(f"Sending FSM description to AI: '{description[:50]}...'", type_hint="AI_ACTION")
            self._update_ai_chat_status("Status: Generating FSM from description...")
            self.ai_chatbot_manager.generate_fsm_from_description(description)
            self._append_to_ai_chat_display("You", f"Generate an FSM: {description}")
        elif ok: 
            QMessageBox.warning(self, "Empty Description", "Please provide a description for the FSM.")

    def _handle_fsm_data_from_ai(self, fsm_data: dict, source_message: str):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MW_HANDLE_FSM_FROM_AI ({current_time}): Received FSM data. Source: '{source_message[:30]}...' ---")
        self._append_to_ai_chat_display("AI", f"Received FSM structure. (Source: {source_message[:30]}...) Adding to diagram.")

        if not fsm_data or (not fsm_data.get('states') and not fsm_data.get('transitions')):
            self.log_message("AI returned empty or invalid FSM data structure.", type_hint="AIChatError")
            self._update_ai_chat_status("Status: AI returned no FSM data.")
            self._append_to_ai_chat_display("System", "AI did not return a valid FSM structure to draw.")
            return

        # Ask user if they want to clear the current diagram or add to it
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("Add AI Generated FSM")
        msg_box.setText("AI has generated an FSM. Do you want to clear the current diagram before adding the new FSM, or add to the existing one?")
        
        clear_button = msg_box.addButton("Clear and Add", QMessageBox.AcceptRole) 
        add_to_existing_button = msg_box.addButton("Add to Existing", QMessageBox.AcceptRole) 
        cancel_button = msg_box.addButton("Cancel", QMessageBox.RejectRole) 
        
        msg_box.setDefaultButton(cancel_button) 
        
        msg_box.exec_() # Show the dialog
        
        clicked_button = msg_box.clickedButton()
        reply = -1 # Default to an invalid reply, indicating dialog was closed or unexpected button
        
        if clicked_button == clear_button:
            reply = 0 # Corresponds to "Clear and Add"
        elif clicked_button == add_to_existing_button:
            reply = 1 # Corresponds to "Add to Existing"
        elif clicked_button == cancel_button:
            reply = 2 # Corresponds to "Cancel"

        if reply == 2 or reply == -1: # Cancel or closed dialog
            self.log_message("User cancelled adding AI generated FSM.", type_hint="AI_ACTION")
            self._update_ai_chat_status("Status: FSM generation cancelled by user.")
            return
        
        clear_current = (reply == 0) # True if "Clear and Add" was chosen
        self._add_fsm_data_to_scene(fsm_data, clear_current_diagram=clear_current, original_user_prompt=source_message)
        self._update_ai_chat_status("Status: FSM added to diagram.")
        self.log_message("FSM data from AI processed and added to scene.", type_hint="AI_ACTION")
        
        
        
    def _handle_plain_ai_response(self, ai_message: str):
        """Handles a plain text response from the AI and appends it to the chat display."""
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MW_HANDLE_PLAIN_AI_RESPONSE ({current_time}): Received plain AI response. ---")
        self._append_to_ai_chat_display("AI", ai_message)
        # Optionally, update status if needed, but usually responseReady implies it's done.
        # self._update_ai_chat_status("Status: Ready.") # Worker's finally block should handle this.    

    def on_send_ai_chat_message(self): # THIS IS THE METHOD THAT WAS MISSING
        message = self.ai_chat_input.text().strip()
        if not message: return
        self.ai_chat_input.clear()
        self._append_to_ai_chat_display("You", message)
        self.ai_chatbot_manager.send_message(message) 
        self._update_ai_chat_status("Status: Sending message...")

    def _add_fsm_data_to_scene(self, fsm_data: dict, clear_current_diagram: bool = False, original_user_prompt: str = "AI Generated FSM"):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        self.log_message(f"--- ADD_FSM_TO_SCENE ({current_time}): clear_current_diagram={clear_current_diagram} ---", type_hint="AI_ACTION")
        self.log_message(f"--- ADD_FSM_TO_SCENE: Received FSM Data (states: {len(fsm_data.get('states',[]))}, transitions: {len(fsm_data.get('transitions',[]))}) ---", type_hint="AI_DEBUG")

        if clear_current_diagram:
            if not self.on_new_file(silent=True): 
                 self.log_message("Clearing diagram cancelled by user (save prompt). Cannot add AI FSM.", type_hint="AI_ACTION")
                 return
            self.log_message("Cleared diagram before AI generation.", type_hint="AI_ACTION")
        
        if not clear_current_diagram:
            self.undo_stack.beginMacro(f"Add AI FSM: {original_user_prompt[:30]}...")

        state_items_map = {}
        items_to_add_for_undo_command = [] 

        layout_start_x, layout_start_y = 100, 100 
        items_per_row = 3
        default_item_width, default_item_height = 120, 60
        padding_x, padding_y = 150, 100
        GV_SCALE = 1.2  

        G = pgv.AGraph(directed=True, strict=False) 
        
        for state_data in fsm_data.get('states', []):
            name = state_data.get('name')
            if name: G.add_node(name, width=default_item_width/72.0, height=default_item_height/72.0) 

        for trans_data in fsm_data.get('transitions', []):
            source = trans_data.get('source')
            target = trans_data.get('target')
            if source and target and G.has_node(source) and G.has_node(target):
                G.add_edge(source, target, label=trans_data.get('event', ''))
            else:
                self.log_message(f"AI Gen Warning: Skipping edge due to missing node(s) in Graphviz: {source}->{target}", type_hint="AIChatError")

        graphviz_positions = {}
        try:
            G.layout(prog="dot") 
            self.log_message("Graphviz layout ('dot') successful.", type_hint="AI_DEBUG")

            raw_gv_positions = []
            for node in G.nodes():
                try:
                    pos_str = node.attr['pos']
                    parts = pos_str.split(',')
                    if len(parts) == 2:
                        raw_gv_positions.append({'name': node.name, 'x': float(parts[0]), 'y': float(parts[1])})
                    else:
                        self.log_message(f"Graphviz Warning: Malformed pos '{pos_str}' for node '{node.name}'.", type_hint="AIChatError")
                except KeyError:
                    self.log_message(f"Graphviz Warning: Node '{node.name}' has no 'pos' attribute after layout.", type_hint="AIChatError")
                except ValueError:
                    self.log_message(f"Graphviz Warning: Cannot parse pos '{node.attr.get('pos')}' for node '{node.name}'.", type_hint="AIChatError")

            if raw_gv_positions:
                min_x_gv = min(p['x'] for p in raw_gv_positions)
                max_x_gv = max(p['x'] for p in raw_gv_positions)
                min_y_gv = min(p['y'] for p in raw_gv_positions)
                max_y_gv = max(p['y'] for p in raw_gv_positions)
                
                shifted_scaled_positions = []
                for p in raw_gv_positions:
                    shifted_scaled_positions.append({
                        'name': p['name'],
                        'x': (p['x'] - min_x_gv) * GV_SCALE,
                        'y': (p['y'] - min_y_gv) * GV_SCALE  
                    })

                max_y_shifted_scaled = 0
                if shifted_scaled_positions:
                     max_y_shifted_scaled = max(p['y'] for p in shifted_scaled_positions)

                for p_ss in shifted_scaled_positions:
                    item_w = default_item_width 
                    item_h = default_item_height
                    final_x = p_ss['x'] + layout_start_x - item_w / 2
                    final_y = (max_y_shifted_scaled - p_ss['y']) + layout_start_y - item_h / 2 
                    graphviz_positions[p_ss['name']] = QPointF(final_x, final_y)
            else:
                 self.log_message("Graphviz: No valid positions extracted from nodes.", type_hint="AIChatError")
        except Exception as e: 
            self.log_message(f"Graphviz layout error: {str(e).strip() or 'Unknown Graphviz error'}. Falling back to grid layout.", type_hint="AIChatError")
            graphviz_positions = {} 

        for i, state_data in enumerate(fsm_data.get('states', [])):
            name = state_data.get('name')
            if not name:
                self.log_message(f"AI Gen Warning: State data missing 'name'. Skipping: {state_data}", type_hint="AIChatError")
                continue

            item_w = state_data.get('width', default_item_width) # AI might not provide these, use defaults
            item_h = state_data.get('height', default_item_height)
            
            pos = graphviz_positions.get(name)
            if pos:
                pos_x, pos_y = pos.x(), pos.y()
            else: 
                self.log_message(f"Using fallback grid layout for state '{name}'.", type_hint="AI_DEBUG")
                pos_x = layout_start_x + (i % items_per_row) * (default_item_width + padding_x)
                pos_y = layout_start_y + (i // items_per_row) * (default_item_height + padding_y)

            try:
                state_item = GraphicsStateItem(
                    pos_x, pos_y, item_w, item_h, name,
                    is_initial=state_data.get('is_initial', False),
                    is_final=state_data.get('is_final', False),
                    color=state_data.get('properties', {}).get('color', COLOR_ITEM_STATE_DEFAULT_BG),
                    entry_action=state_data.get('entry_action', ""),
                    during_action=state_data.get('during_action', ""),
                    exit_action=state_data.get('exit_action', ""),
                    description=state_data.get('description', ""),
                    is_superstate=state_data.get('is_superstate', False),
                    sub_fsm_data=state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]})
                )
                items_to_add_for_undo_command.append(state_item)
                state_items_map[name] = state_item
            except Exception as e:
                self.log_message(f"Error creating GraphicsStateItem '{name}' from AI data: {e}", type_hint="AIChatError")

        for trans_data in fsm_data.get('transitions', []):
            source_name = trans_data.get('source')
            target_name = trans_data.get('target')

            if not source_name or not target_name:
                self.log_message(f"AI Gen Warning: Transition missing source/target. Skipping: {trans_data}", type_hint="AIChatError")
                continue

            source_item = state_items_map.get(source_name)
            target_item = state_items_map.get(target_name)

            if source_item and target_item:
                try:
                    trans_item = GraphicsTransitionItem(
                        source_item, target_item,
                        event_str=trans_data.get('event', ""),
                        condition_str=trans_data.get('condition', ""),
                        action_str=trans_data.get('action', ""),
                        color=trans_data.get('properties', {}).get('color', COLOR_ITEM_TRANSITION_DEFAULT),
                        description=trans_data.get('description', "")
                    )
                    offset_x = trans_data.get('control_offset_x')
                    offset_y = trans_data.get('control_offset_y')
                    if offset_x is not None and offset_y is not None:
                        try:
                            trans_item.set_control_point_offset(QPointF(float(offset_x), float(offset_y)))
                        except ValueError:
                            self.log_message(f"AI Gen Warning: Invalid control offsets for transition {source_name}->{target_name}. Skipping offset.", type_hint="AIChatError")
                    items_to_add_for_undo_command.append(trans_item)
                except Exception as e:
                    self.log_message(f"Error creating GraphicsTransitionItem from '{source_name}' to '{target_name}': {e}", type_hint="AIChatError")
            else:
                self.log_message(f"AI Gen Warning: Could not find source ('{source_name}') or target ('{target_name}') for transition. Skipping.", type_hint="AIChatError")

        max_y_of_laid_out_items = layout_start_y
        if state_items_map: 
             max_y_of_laid_out_items = max((item.scenePos().y() + item.boundingRect().height() for item in state_items_map.values() if item.scenePos()), default=layout_start_y)
        
        comment_start_y_fallback = max_y_of_laid_out_items + padding_y
        comment_start_x_fallback = layout_start_x

        for i, comment_data in enumerate(fsm_data.get('comments', [])):
            text = comment_data.get('text')
            if not text: continue

            comment_x = comment_data.get('x', comment_start_x_fallback + i * (150 + 20)) 
            comment_y = comment_data.get('y', comment_start_y_fallback)
            comment_width = comment_data.get('width')

            try:
                comment_item = GraphicsCommentItem(comment_x, comment_y, text)
                if comment_width is not None:
                    try: comment_item.setTextWidth(float(comment_width))
                    except ValueError: self.log_message(f"AI Gen Warning: Invalid width '{comment_width}' for comment. Using default.", type_hint="AIChatError")
                items_to_add_for_undo_command.append(comment_item)
            except Exception as e:
                self.log_message(f"Error creating GraphicsCommentItem: {e}", type_hint="AIChatError")

        if items_to_add_for_undo_command:
            for item in items_to_add_for_undo_command:
                item_type_name = type(item).__name__.replace("Graphics","").replace("Item","")
                cmd_text = f"Add AI {item_type_name}"
                if hasattr(item, 'text_label'): cmd_text += f": {item.text_label}"
                elif hasattr(item, '_compose_label_string'): cmd_text += f" ({item._compose_label_string()})" 
                add_cmd = AddItemCommand(self.scene, item, cmd_text)
                self.undo_stack.push(add_cmd) 
            
            self.log_message(f"AI Gen: Added {len(items_to_add_for_undo_command)} items to diagram.", type_hint="AI_ACTION")
            QTimer.singleShot(100, self._fit_view_to_new_ai_items) 
        else:
            self.log_message("AI Gen: No valid items were generated to add to the diagram.", type_hint="AI_ACTION")

        if not clear_current_diagram and items_to_add_for_undo_command: 
            self.undo_stack.endMacro()
        elif not clear_current_diagram and not items_to_add_for_undo_command: 
             self.undo_stack.endMacro() 
             if self.undo_stack.count() > 0 and self.undo_stack.command(self.undo_stack.count() -1).childCount() == 0:
                 pass

        if self.py_sim_active and items_to_add_for_undo_command: 
            current_diagram_data = self.scene.get_diagram_data() 
            try:
                self.py_fsm_engine = FSMSimulator(current_diagram_data['states'], current_diagram_data['transitions'])
                self._append_to_py_simulation_log(["Python FSM Simulation reinitialized for new diagram from AI."])
                self._update_py_simulation_dock_ui()
            except FSMError as e:
                self._append_to_py_simulation_log([f"ERROR Re-initializing Sim after AI: {e}"])
                self.on_stop_py_simulation(silent=True) 

        self.log_message(f"--- ADD_FSM_TO_SCENE ({QTime.currentTime().toString('hh:mm:ss.zzz')}): Processing finished. Items queued: {len(items_to_add_for_undo_command)} ---", type_hint="AI_DEBUG")


    def _fit_view_to_new_ai_items(self):
        if not self.scene.items(): return
        items_bounds = self.scene.itemsBoundingRect()
        if self.view and not items_bounds.isNull():
            padded_bounds = items_bounds.adjusted(-50, -50, 50, 50) 
            self.view.fitInView(padded_bounds, Qt.KeepAspectRatio)
            self.log_message("View adjusted to AI generated items.", type_hint="AI_ACTION")
        elif self.view and self.scene.sceneRect(): 
             self.view.centerOn(self.scene.sceneRect().center())

    def _handle_ai_error(self, error_message: str):
        self._append_to_ai_chat_display("System Error", error_message)
        self.log_message(f"AI Chatbot Error: {error_message}", type_hint="AIChatError")
        short_error = error_message.split('\n')[0].split(':')[0][:50]
        self._update_ai_chat_status(f"Error: {short_error}...")

    def _update_ai_chat_status(self, status_text: str):
        if hasattr(self, 'ai_chat_status_label'):
            self.ai_chat_status_label.setText(status_text)
            is_thinking = "thinking..." in status_text.lower() or \
                          "sending..." in status_text.lower() or \
                          "generating..." in status_text.lower()
            is_key_required = "api key required" in status_text.lower() or \
                              "inactive" in status_text.lower() or \
                              "api key error" in status_text.lower() 
            is_error_state = "error" in status_text.lower() or \
                             "failed" in status_text.lower() or \
                             is_key_required

            if is_error_state: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: red;")
            elif is_thinking: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: #FF8F00;") 
            else: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;") 

            can_send = not is_thinking and not is_key_required

            if hasattr(self, 'ai_chat_send_button'): self.ai_chat_send_button.setEnabled(can_send)
            if hasattr(self, 'ai_chat_input'):
                self.ai_chat_input.setEnabled(can_send)
                if can_send and hasattr(self, 'ai_chatbot_dock') and self.ai_chatbot_dock.isVisible() and self.isActiveWindow(): 
                    self.ai_chat_input.setFocus()
            if hasattr(self, 'ask_ai_to_generate_fsm_action'): 
                self.ask_ai_to_generate_fsm_action.setEnabled(can_send)


    def _append_to_ai_chat_display(self, sender: str, message: str):
        timestamp = QTime.currentTime().toString('hh:mm')
        sender_color_hex_str = COLOR_ACCENT_PRIMARY 
        if sender == "You": sender_color_hex_str = COLOR_ACCENT_SECONDARY
        elif sender == "System Error" or sender == "System": sender_color_hex_str = "#D32F2F" 

        escaped_message = html.escape(message)
        escaped_message = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped_message)
        escaped_message = re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'<i>\1</i>', escaped_message) 
        escaped_message = re.sub(r'```(.*?)```', r'<pre><code style="background-color:#f0f0f0; padding:2px 4px; border-radius:3px;">\1</code></pre>', escaped_message, flags=re.DOTALL)
        escaped_message = re.sub(r'`(.*?)`', r'<code style="background-color:#f0f0f0; padding:1px 3px; border-radius:2px;">\1</code>', escaped_message)
        escaped_message = escaped_message.replace("\n", "<br>") 

        formatted_html = (
            f"<div style='margin-bottom: 8px;'>"
            f"<span style='font-size:8pt; color:grey;'>[{timestamp}]</span> "
            f"<strong style='color:{sender_color_hex_str};'>{html.escape(sender)}:</strong>"
            f"<div style='margin-top: 3px; padding-left: 5px; border-left: 2px solid {sender_color_hex_str if sender != 'System Error' else '#FFCDD2'};'>{escaped_message}</div>"
            f"</div>"
        )
        self.ai_chat_display.append(formatted_html)
        self.ai_chat_display.ensureCursorVisible() 

    def on_openai_settings(self):
        current_key = self.ai_chatbot_manager.api_key if self.ai_chatbot_manager.api_key else ""
        key, ok = QInputDialog.getText(
            self, "OpenAI API Key", "Enter OpenAI API Key (blank to clear):",
            QLineEdit.PasswordEchoOnEdit, current_key 
        )
        if ok:
            new_key = key.strip()
            self.ai_chatbot_manager.set_api_key(new_key if new_key else None)
            if new_key:
                self.log_message("OpenAI API Key set/updated.", type_hint="AI_CONFIG")
            else:
                self.log_message("OpenAI API Key cleared.", type_hint="AI_CONFIG")

    def on_clear_ai_chat_history(self):
        if self.ai_chatbot_manager:
            self.ai_chatbot_manager.clear_conversation_history()
            if hasattr(self, 'ai_chat_display'): 
                self.ai_chat_display.clear()
                self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
            self.log_message("AI chat history cleared.", type_hint="AI_ACTION")

    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems()
        html_content = ""
        edit_enabled = False
        item_type_for_tooltip = "item"

        if len(selected_items) == 1:
            item = selected_items[0]
            props = item.get_data() if hasattr(item, 'get_data') else {}
            item_type_name = type(item).__name__.replace("Graphics", "").replace("Item", "")
            item_type_for_tooltip = item_type_name.lower()
            edit_enabled = True

            def format_prop_text(text_content, max_chars=25):
                if not text_content: return "<i>(none)</i>"
                escaped = html.escape(str(text_content))
                first_line = escaped.split('\n')[0]
                if len(first_line) > max_chars or '\n' in escaped:
                    return first_line[:max_chars] + "…"
                return first_line

            rows_html = ""
            if isinstance(item, GraphicsStateItem):
                color_val = props.get('color', COLOR_ITEM_STATE_DEFAULT_BG)
                try: color_obj = QColor(color_val)
                except: color_obj = QColor(COLOR_ITEM_STATE_DEFAULT_BG) 
                text_on_color = 'black' if color_obj.lightnessF() > 0.5 else 'white'
                color_style = f"background-color:{color_obj.name()}; color:{text_on_color}; padding: 1px 4px; border-radius:2px;"

                rows_html += f"<tr><td><b>Name:</b></td><td>{html.escape(props.get('name', 'N/A'))}</td></tr>"
                rows_html += f"<tr><td><b>Initial:</b></td><td>{'Yes' if props.get('is_initial') else 'No'}</td></tr>"
                rows_html += f"<tr><td><b>Final:</b></td><td>{'Yes' if props.get('is_final') else 'No'}</td></tr>"
                if props.get('is_superstate'):
                     rows_html += f"<tr><td><b>Superstate:</b></td><td>Yes ({len(props.get('sub_fsm_data',{}).get('states',[]))} sub-states)</td></tr>"

                rows_html += f"<tr><td><b>Color:</b></td><td><span style='{color_style}'>{html.escape(color_obj.name())}</span></td></tr>"
                rows_html += f"<tr><td><b>Entry:</b></td><td>{format_prop_text(props.get('entry_action', ''))}</td></tr>"
                rows_html += f"<tr><td><b>During:</b></td><td>{format_prop_text(props.get('during_action', ''))}</td></tr>"
                rows_html += f"<tr><td><b>Exit:</b></td><td>{format_prop_text(props.get('exit_action', ''))}</td></tr>"
                if props.get('description'): rows_html += f"<tr><td colspan='2'><b>Desc:</b> {format_prop_text(props.get('description'), 50)}</td></tr>"

            elif isinstance(item, GraphicsTransitionItem):
                color_val = props.get('color', COLOR_ITEM_TRANSITION_DEFAULT)
                try: color_obj = QColor(color_val)
                except: color_obj = QColor(COLOR_ITEM_TRANSITION_DEFAULT) 
                text_on_color = 'black' if color_obj.lightnessF() > 0.5 else 'white'
                color_style = f"background-color:{color_obj.name()}; color:{text_on_color}; padding: 1px 4px; border-radius:2px;"

                event_text = html.escape(props.get('event', '')) if props.get('event') else ''
                condition_text = f"[{html.escape(props.get('condition', ''))}]" if props.get('condition') else ''
                action_text = f"/{{{format_prop_text(props.get('action', ''), 15)}}}" if props.get('action') else ''
                label_parts = [p for p in [event_text, condition_text, action_text] if p]
                full_label = " ".join(label_parts) if label_parts else "<i>(No Label)</i>"

                rows_html += f"<tr><td><b>Label:</b></td><td style='font-size:8pt;'>{full_label}</td></tr>"
                rows_html += f"<tr><td><b>From:</b></td><td>{html.escape(props.get('source','N/A'))}</td></tr>"
                rows_html += f"<tr><td><b>To:</b></td><td>{html.escape(props.get('target','N/A'))}</td></tr>"
                rows_html += f"<tr><td><b>Color:</b></td><td><span style='{color_style}'>{html.escape(color_obj.name())}</span></td></tr>"
                rows_html += f"<tr><td><b>Curve:</b></td><td>Bend={props.get('control_offset_x',0):.0f}, Shift={props.get('control_offset_y',0):.0f}</td></tr>"
                if props.get('description'): rows_html += f"<tr><td colspan='2'><b>Desc:</b> {format_prop_text(props.get('description'), 50)}</td></tr>"

            elif isinstance(item, GraphicsCommentItem):
                rows_html += f"<tr><td colspan='2'><b>Text:</b> {format_prop_text(props.get('text', ''), 60)}</td></tr>"
            else:
                rows_html = "<tr><td>Unknown Item Type</td></tr>"
                item_type_name = "Unknown"

            html_content = f"""<div style='font-family: "Segoe UI", Arial, sans-serif; font-size: 9pt; line-height: 1.5;'>
                             <h4 style='margin:0 0 5px 0; padding:2px 0; color: {COLOR_ACCENT_PRIMARY}; border-bottom: 1px solid {COLOR_BORDER_LIGHT};'>Type: {item_type_name}</h4>
                             <table style='width: 100%; border-collapse: collapse;'>{rows_html}</table></div>"""
        elif len(selected_items) > 1:
            html_content = f"<i><b>{len(selected_items)} items selected.</b><br>Select a single item to view/edit its properties.</i>"
            item_type_for_tooltip = f"{len(selected_items)} items"
        else: 
            html_content = "<i>No item selected.</i><br><small>Click an item in the diagram or use tools to add new items.</small>"

        self.properties_editor_label.setText(html_content)
        self.properties_edit_button.setEnabled(edit_enabled)
        self.properties_edit_button.setToolTip(f"Edit detailed properties of the selected {item_type_for_tooltip}" if edit_enabled else "Select a single item to enable editing")

    def _on_edit_selected_item_properties_from_dock(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1:
            self.scene.edit_item_properties(selected_items[0])

    def log_message(self, message: str, type_hint: str = "GENERAL"):
        timestamp = QTime.currentTime().toString('hh:mm:ss.zzz')
        display_message = html.escape(message) 

        color = COLOR_TEXT_PRIMARY 
        prefix = ""
        if type_hint == "NETWATCH": color = "grey"; prefix = "<i>(NetCheck)</i> "
        elif type_hint == "MATLAB_CONN": color = COLOR_TEXT_SECONDARY; prefix = "<i>(MATLAB)</i> "
        elif type_hint == "PYSIM_STATUS_UPDATE": color = COLOR_ACCENT_PRIMARY; prefix = "<i>(PySim)</i> "
        elif type_hint == "AI_CONFIG": color = "blue"; prefix = "<i>(AI Cfg)</i> "
        elif type_hint == "AIChatError": color = "red"; prefix = "<i>(AI Err)</i> "
        elif type_hint == "AI_ACTION": color = COLOR_ACCENT_SECONDARY; prefix = "<i>(AI Action)</i> " 
        elif type_hint == "AI_DEBUG": color = "#FFA000"; prefix = "<i>(AI Debug)</i> " 
        
        formatted_log_entry = (f"<span style='color:{COLOR_TEXT_SECONDARY};'>[{timestamp}]</span> "
                               f"<span style='color:{color};'>{prefix}{display_message}</span>")

        self.log_output.append(formatted_log_entry)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum()) 

        if type_hint not in ["NETWATCH", "AI_DEBUG", "PYSIM_STATUS_UPDATE"] and "worker:" not in message.lower(): 
            self.status_label.setText(message.split('\n')[0][:120]) 


    def _update_window_title(self):
        title = APP_NAME
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        title += f" - {file_name}"
        if self.py_sim_active: title += " [PySim Running]"
        self.setWindowTitle(title + ("[*]" if self.isWindowModified() else ""))

    def _update_save_actions_enable_state(self):
        self.save_action.setEnabled(self.isWindowModified())

    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo())
        self.redo_action.setEnabled(self.undo_stack.canRedo())
        undo_text = self.undo_stack.undoText()
        redo_text = self.undo_stack.redoText()
        self.undo_action.setText(f"&Undo {undo_text}" if undo_text else "&Undo")
        self.redo_action.setText(f"&Redo {redo_text}" if redo_text else "&Redo")

    def _update_matlab_status_display(self, connected, message):
        text = f"MATLAB: {'Connected' if connected else 'Not Connected'}"
        tooltip = f"MATLAB Status: {message}"
        self.matlab_status_label.setText(text)
        self.matlab_status_label.setToolTip(tooltip)
        style_sheet = f"font-weight: bold; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE if connected else '#C62828'};" 
        self.matlab_status_label.setStyleSheet(style_sheet)
        if "Initializing" not in message: 
            self.log_message(f"MATLAB Conn: {message}", type_hint="MATLAB_CONN")
        self._update_matlab_actions_enabled_state()

    def _update_matlab_actions_enabled_state(self):
        can_run_matlab = self.matlab_connection.connected and not self.py_sim_active
        for action in [self.export_simulink_action, self.run_simulation_action, self.generate_code_action]:
            action.setEnabled(can_run_matlab)
        self.matlab_settings_action.setEnabled(not self.py_sim_active) 

    def _start_matlab_operation(self, operation_name):
        self.log_message(f"MATLAB Operation: {operation_name} starting...", type_hint="MATLAB_CONN")
        self.status_label.setText(f"Running: {operation_name}...")
        self.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False) 

    def _finish_matlab_operation(self):
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready") 
        self.set_ui_enabled_for_matlab_op(True) 
        self.log_message("MATLAB Operation: Finished processing.", type_hint="MATLAB_CONN")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        self.menuBar().setEnabled(enabled)
        for child in self.findChildren(QToolBar): child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock"]:
            dock = self.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(enabled)
        self._update_py_simulation_actions_enabled_state() 

    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation()
        self.log_message(f"MATLAB Result ({('Success' if success else 'Failure')}): {message}", type_hint="MATLAB_CONN")
        if success:
            if "Model generation" in message and data:
                self.last_generated_model_path = data
                QMessageBox.information(self, "Simulink Model Generation", f"Simulink model generated successfully:\n{data}")
            elif "Simulation" in message:
                QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else:
            QMessageBox.warning(self, "MATLAB Operation Failed", message)

    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation()
        self.log_message(f"MATLAB Code Gen Result ({('Success' if success else 'Failure')}): {message}", type_hint="MATLAB_CONN")
        if success and output_dir:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText)
            abs_output_dir = os.path.abspath(output_dir)
            msg_box.setText(f"Code generation completed.<br>Output directory: <a href='file:///{abs_output_dir}'>{abs_output_dir}</a>")
            msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction) 
            open_dir_button = msg_box.addButton("Open Directory", QMessageBox.ActionRole)
            msg_box.addButton(QMessageBox.Ok)
            msg_box.exec_()
            if msg_box.clickedButton() == open_dir_button:
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(abs_output_dir)):
                    self.log_message(f"Error opening directory {abs_output_dir}", type_hint="GENERAL")
                    QMessageBox.warning(self, "Error Opening Directory", f"Could not open directory:\n{abs_output_dir}")
        elif not success:
            QMessageBox.warning(self, "Code Generation Failed", message)

    def _prompt_save_if_dirty(self) -> bool: 
        if not self.isWindowModified(): return True 

        if self.py_sim_active: 
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python FSM simulation before saving or opening a new file.")
            return False

        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes?",
                                     f"The document '{file_name}' has unsaved changes.\nDo you want to save them before continuing?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save) 

        if reply == QMessageBox.Save: return self.on_save_file() 
        return reply != QMessageBox.Cancel 

    def on_new_file(self, silent=False): 
        if not silent and not self._prompt_save_if_dirty(): return False 

        self.on_stop_py_simulation(silent=True) 
        self.scene.clear()
        self.scene.setSceneRect(0,0,6000,4500) 
        self.current_file_path = None
        self.last_generated_model_path = None
        self.undo_stack.clear()
        self.scene.set_dirty(False) 
        self.setWindowModified(False) 

        self._update_window_title()
        self._update_undo_redo_actions_enable_state()
        if not silent: self.log_message("New diagram created. Ready.", type_hint="GENERAL")
        self.view.resetTransform() 
        self.view.centerOn(self.scene.sceneRect().center())
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger() 
        return True

    def on_open_file(self):
        if not self._prompt_save_if_dirty(): return

        self.on_stop_py_simulation(silent=True)
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)

        if file_path:
            self.log_message(f"Attempting to open file: {file_path}", type_hint="GENERAL")
            if self._load_from_path(file_path):
                self.current_file_path = file_path
                self.last_generated_model_path = None 
                self.undo_stack.clear() 
                self.scene.set_dirty(False)
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                self.log_message(f"Successfully opened: {file_path}", type_hint="GENERAL")
                items_bounds = self.scene.itemsBoundingRect()
                if not items_bounds.isEmpty():
                    self.view.fitInView(items_bounds.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)
                else:
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())
            else:
                QMessageBox.critical(self, "Error Opening File", f"Could not load or parse file: {file_path}")
                self.log_message(f"Failed to open file: {file_path}", type_hint="GENERAL")

    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict) or ('states' not in data or 'transitions' not in data):
                self.log_message(f"Error: Invalid BSM file format in {file_path}.", type_hint="GENERAL")
                return False
            self.scene.load_diagram_data(data) 
            return True
        except json.JSONDecodeError as e:
            self.log_message(f"Error decoding JSON from {file_path}: {e}", type_hint="GENERAL")
            return False
        except Exception as e:
            self.log_message(f"Error loading file {file_path}: {type(e).__name__}: {str(e)}", type_hint="GENERAL")
            return False

    def on_save_file(self) -> bool: 
        if not self.current_file_path: 
            return self.on_save_file_as()
        return self._save_to_path(self.current_file_path)

    def on_save_file_as(self) -> bool:
        start_path = self.current_file_path if self.current_file_path \
                     else os.path.join(QDir.homePath(), "untitled" + FILE_EXTENSION)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As", start_path, FILE_FILTER)

        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION
            if self._save_to_path(file_path):
                self.current_file_path = file_path 
                self.scene.set_dirty(False) 
                self.setWindowModified(False)
                self._update_window_title()
                return True
        return False 

    def _save_to_path(self, file_path) -> bool:
        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python FSM simulation before saving.")
            return False

        save_file = QSaveFile(file_path) 
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            error_str = save_file.errorString()
            self.log_message(f"Error opening save file {file_path}: {error_str}", type_hint="GENERAL")
            QMessageBox.critical(self, "Save Error", f"Failed to open file for saving:\n{error_str}")
            return False
        try:
            data = self.scene.get_diagram_data()
            json_data = json.dumps(data, indent=4, ensure_ascii=False)
            bytes_written = save_file.write(json_data.encode('utf-8'))
            if bytes_written == -1: 
                error_str = save_file.errorString()
                self.log_message(f"Error writing data to {file_path}: {error_str}", type_hint="GENERAL")
                QMessageBox.critical(self, "Save Error", f"Failed to write data to file:\n{error_str}")
                save_file.cancelWriting()
                return False

            if not save_file.commit(): 
                error_str = save_file.errorString()
                self.log_message(f"Error committing save to {file_path}: {error_str}", type_hint="GENERAL")
                QMessageBox.critical(self, "Save Error", f"Failed to commit saved file:\n{error_str}")
                return False

            self.log_message(f"File saved successfully: {file_path}", type_hint="GENERAL")
            self.scene.set_dirty(False) 
            self.setWindowModified(False)
            return True
        except Exception as e:
            self.log_message(f"Error saving file {file_path}: {type(e).__name__}: {str(e)}", type_hint="GENERAL")
            QMessageBox.critical(self, "Save Error", f"An error occurred during saving:\n{str(e)}")
            save_file.cancelWriting() 
            return False

    def on_select_all(self): self.scene.select_all()
    def on_delete_selected(self): self.scene.delete_selected_items()

    def on_export_simulink(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected. Configure in Simulation menu.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before exporting to Simulink.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Export to Simulink")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp, "->M"))
        layout = QFormLayout(dialog)
        layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)

        default_model_name_base = os.path.splitext(os.path.basename(self.current_file_path))[0] if self.current_file_path else "BSM_Model"
        model_name_default = "".join(c if c.isalnum() or c=='_' else '_' for c in default_model_name_base)
        if not model_name_default or not model_name_default[0].isalpha():
            model_name_default = "Mdl_" + model_name_default
        model_name_default = model_name_default.replace('-', '_') 

        model_name_edit = QLineEdit(model_name_default)
        layout.addRow("Simulink Model Name:", model_name_edit)

        default_out_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        output_dir_edit = QLineEdit(default_out_dir)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw")," Browse...")
        browse_btn.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(output_dir_edit, 1); dir_layout.addWidget(browse_btn)
        layout.addRow("Output Directory:", dir_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        dialog.setMinimumWidth(450)

        if dialog.exec_() == QDialog.Accepted:
            model_name = model_name_edit.text().strip()
            output_dir = output_dir_edit.text().strip()
            if not model_name or not output_dir:
                QMessageBox.warning(self, "Input Error", "Model name and output directory must be specified.")
                return
            if not model_name[0].isalpha() or not all(c.isalnum() or c == '_' for c in model_name):
                QMessageBox.warning(self, "Invalid Model Name", "Model name must start with a letter, and contain only alphanumeric characters or underscores.")
                return
            try: os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create directory:\n{e}")
                return

            diagram_data = self.scene.get_diagram_data()
            if not diagram_data['states']:
                QMessageBox.information(self, "Empty Diagram", "Cannot export: the diagram contains no states.")
                return

            self._start_matlab_operation(f"Exporting '{model_name}' to Simulink")
            self.matlab_connection.generate_simulink_model(diagram_data['states'], diagram_data['transitions'], output_dir, model_name)

    def on_run_simulation(self): 
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before running a MATLAB simulation.")
            return

        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model to Simulate", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path 
        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Simulation stop time (seconds):", 10.0, 0.001, 86400.0, 3)
        if not ok: return

        self._start_matlab_operation(f"Running Simulink simulation for '{os.path.basename(model_path)}'")
        self.matlab_connection.run_simulation(model_path, sim_time)

    def on_generate_code(self): 
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before generating code via MATLAB.")
            return

        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model for Code Generation", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path
        dialog = QDialog(self)
        dialog.setWindowTitle("Code Generation Options")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"))
        layout = QFormLayout(dialog); layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)

        lang_combo = QComboBox(); lang_combo.addItems(["C", "C++"]); lang_combo.setCurrentText("C++")
        layout.addRow("Target Language:", lang_combo)

        output_dir_edit = QLineEdit(os.path.dirname(model_path)) 
        browse_btn_codegen = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw")," Browse...")
        browse_btn_codegen.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Base Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
        dir_layout_codegen = QHBoxLayout(); dir_layout_codegen.addWidget(output_dir_edit, 1); dir_layout_codegen.addWidget(browse_btn_codegen)
        layout.addRow("Base Output Directory:", dir_layout_codegen)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        dialog.setMinimumWidth(450)

        if dialog.exec_() == QDialog.Accepted:
            language = lang_combo.currentText()
            output_dir_base = output_dir_edit.text().strip()
            if not output_dir_base:
                QMessageBox.warning(self, "Input Error", "Base output directory required.")
                return
            try: os.makedirs(output_dir_base, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create directory:\n{e}")
                return

            self._start_matlab_operation(f"Generating {language} code for '{os.path.basename(model_path)}'")
            self.matlab_connection.generate_code(model_path, language, output_dir_base)

    def on_matlab_settings(self):
        if self.py_sim_active:
             QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before changing MATLAB settings.")
             return
        MatlabSettingsDialog(self.matlab_connection, self).exec_()

    def _get_bundled_file_path(self, filename: str) -> str | None:
        try:
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                base_path = sys._MEIPASS
            elif getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            
            possible_paths = [
                os.path.join(base_path, filename),
                os.path.join(base_path, 'docs', filename),
                os.path.join(base_path, 'resources', filename),
                os.path.join(base_path, 'examples', filename) 
            ]
            for path_to_check in possible_paths:
                if os.path.exists(path_to_check):
                    return path_to_check
            direct_path = os.path.join(base_path, filename)
            if os.path.exists(direct_path):
                return direct_path

            self.log_message(f"Bundled file '{filename}' not found in expected locations relative to {base_path}.", type_hint="GENERAL")
            return None
        except Exception as e:
            self.log_message(f"Error determining bundled file path for '{filename}': {e}", type_hint="GENERAL")
            return None

    def _open_example_file(self, filename: str):
        if not self._prompt_save_if_dirty():
            return

        example_file_path = self._get_bundled_file_path(filename) 

        if example_file_path and os.path.exists(example_file_path):
            self.log_message(f"Attempting to open example file: {example_file_path}", type_hint="GENERAL")
            if self._load_from_path(example_file_path):
                self.current_file_path = example_file_path 
                self.last_generated_model_path = None
                self.undo_stack.clear()
                self.scene.set_dirty(False) 
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                self.log_message(f"Successfully opened example: {filename}", type_hint="GENERAL")
                items_bounds = self.scene.itemsBoundingRect()
                if not items_bounds.isEmpty():
                    self.view.fitInView(items_bounds.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)
                else:
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())
            else:
                QMessageBox.critical(self, "Error Opening Example", f"Could not load or parse example file: {filename}")
                self.log_message(f"Failed to open example file: {filename}", type_hint="GENERAL")
        else:
            QMessageBox.warning(self, "Example Not Found", f"The example file '{filename}' could not be found.")
            self.log_message(f"Example file '{filename}' not found at expected path: {example_file_path}", type_hint="GENERAL")

    def on_show_quick_start(self):
        guide_filename = "QUICK_START.html" 
        guide_path = self._get_bundled_file_path(guide_filename)
        if guide_path:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path)):
                QMessageBox.warning(self, "Could Not Open Guide", f"Failed to open the quick start guide using the default application for '{guide_filename}'. Path: {guide_path}")
                self.log_message(f"Failed to open quick start guide at {guide_path}", type_hint="GENERAL")
        else:
            QMessageBox.information(self, "Quick Start Not Found", f"The quick start guide ('{guide_filename}') was not found in the application bundle.")

    def on_about(self):
        about_text = f"""<h3 style='color:{COLOR_ACCENT_PRIMARY};'>{APP_NAME} v{APP_VERSION}</h3>
                         <p>A graphical tool for designing, simulating, and generating code for Finite State Machines (FSMs).</p>
                         <p>Features:</p>
                         <ul>
                             <li>Intuitive FSM diagram creation and editing.</li>
                             <li>Internal Python-based FSM simulation.</li>
                             <li>Integration with MATLAB/Simulink for model export, simulation, and C/C++ code generation.</li>
                             <li>AI Assistant for FSM generation from descriptions and chat-based help.</li>
                         </ul>
                         <p>Developed as a versatile environment for FSM development and education.</p>
                         <p style='font-size:8pt; color:{COLOR_TEXT_SECONDARY};'>
                           This tool is intended for research and educational purposes.
                           Always verify generated models and code.
                         </p>
                      """
        QMessageBox.about(self, "About " + APP_NAME, about_text)

    def closeEvent(self, event: QCloseEvent):
        self.on_stop_py_simulation(silent=True) 
        if self.internet_check_timer and self.internet_check_timer.isActive():
            self.internet_check_timer.stop()

        if self.ai_chatbot_manager:
            self.ai_chatbot_manager.stop_chatbot() 

        if self._prompt_save_if_dirty(): 
            if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads:
                self.log_message(f"Closing. {len(self.matlab_connection._active_threads)} MATLAB processes may persist if not completed.", type_hint="GENERAL")
            event.accept()
        else:
            event.ignore()
            if self.internet_check_timer: 
                self.internet_check_timer.start()

    def _init_internet_status_check(self):
        self.internet_check_timer.timeout.connect(self._run_internet_check_job)
        self.internet_check_timer.start(15000) 
        QTimer.singleShot(100, self._run_internet_check_job) 

    def _run_internet_check_job(self):
        host_to_check = "8.8.8.8" 
        port_to_check = 53      
        connection_timeout = 1.5 

        current_status = False
        status_message_detail = "Checking..."
        try:
            s = socket.create_connection((host_to_check, port_to_check), timeout=connection_timeout)
            s.close()
            current_status = True
            status_message_detail = "Connected"
        except socket.timeout:
            status_message_detail = "Disconnected (Timeout)"
        except socket.gaierror as e: 
            status_message_detail = "Disconnected (DNS/Net Issue)"
        except OSError as e: 
            status_message_detail = "Disconnected (Net Error)"

        if current_status != self._internet_connected or self._internet_connected is None:
            self._internet_connected = current_status
            self._update_internet_status_display(current_status, status_message_detail)

    def _update_internet_status_display(self, is_connected: bool, message_detail: str):
        full_status_text = f"Internet: {message_detail}"
        self.internet_status_label.setText(full_status_text)
        try: 
            check_host_name_for_tooltip = socket.getfqdn('8.8.8.8') if is_connected else '8.8.8.8'
        except Exception: check_host_name_for_tooltip = '8.8.8.8'
        self.internet_status_label.setToolTip(f"{full_status_text} (Checks {check_host_name_for_tooltip}:{53})")

        style_sheet = f"font-weight: normal; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE if is_connected else '#D32F2F'};"
        self.internet_status_label.setStyleSheet(style_sheet)
        self.log_message(f"Internet Status: {message_detail}", type_hint="NETWATCH")

        if hasattr(self.ai_chatbot_manager, 'set_online_status'):
            self.ai_chatbot_manager.set_online_status(is_connected)

    def _update_py_sim_status_display(self):
        if self.py_sim_active and self.py_fsm_engine:
            state_name = self.py_fsm_engine.get_current_state_name()
            self.py_sim_status_label.setText(f"PySim: Active ({state_name})")
            self.py_sim_status_label.setStyleSheet(f"font-weight: bold; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE};")
        else:
            self.py_sim_status_label.setText("PySim: Idle")
            self.py_sim_status_label.setStyleSheet("font-weight: normal; padding: 0px 5px;") 

    def _update_py_simulation_actions_enabled_state(self):
        is_matlab_op_running = self.progress_bar.isVisible()
        sim_inactive = not self.py_sim_active

        self.start_py_sim_action.setEnabled(sim_inactive and not is_matlab_op_running)
        if hasattr(self, 'py_sim_start_btn'): self.py_sim_start_btn.setEnabled(sim_inactive and not is_matlab_op_running)

        sim_controls_enabled = self.py_sim_active and not is_matlab_op_running
        for widget in [self.stop_py_sim_action, self.reset_py_sim_action]: widget.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_stop_btn'): self.py_sim_stop_btn.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_reset_btn'): self.py_sim_reset_btn.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_step_btn'): self.py_sim_step_btn.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_event_name_edit'): self.py_sim_event_name_edit.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_trigger_event_btn'): self.py_sim_trigger_event_btn.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_event_combo'): self.py_sim_event_combo.setEnabled(sim_controls_enabled)

    def set_ui_enabled_for_py_sim(self, is_sim_running: bool):
        self.py_sim_active = is_sim_running
        self._update_window_title()
        is_editable = not is_sim_running 

        if is_editable and self.scene.current_mode != "select":
            self.scene.set_mode("select") 
        elif not is_editable: 
            self.scene.set_mode("select") 

        for item in self.scene.items():
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)):
                item.setFlag(QGraphicsItem.ItemIsMovable, is_editable)

        actions_to_toggle = [
            self.new_action, self.open_action, self.save_action, self.save_as_action,
            self.undo_action, self.redo_action, self.delete_action, self.select_all_action,
            self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action
        ]
        for action in actions_to_toggle:
            if hasattr(action, 'setEnabled'): action.setEnabled(is_editable)
        
        if hasattr(self, 'tools_dock'): self.tools_dock.setEnabled(is_editable)
        if hasattr(self, 'properties_edit_button'):
             self.properties_edit_button.setEnabled(is_editable and len(self.scene.selectedItems())==1)

        self._update_matlab_actions_enabled_state() 
        self._update_py_simulation_actions_enabled_state() 
        self._update_py_sim_status_display() 

    def _highlight_sim_active_state(self, state_name_to_highlight: str | None):
        if self._py_sim_currently_highlighted_item:
            self.log_message(f"PySim: Unhighlighting state '{self._py_sim_currently_highlighted_item.text_label}'", type_hint="PYSIM_STATUS_UPDATE")
            self._py_sim_currently_highlighted_item.set_py_sim_active_style(False)
            self._py_sim_currently_highlighted_item = None

        if state_name_to_highlight:
            for item in self.scene.items():
                if isinstance(item, GraphicsStateItem) and item.text_label == state_name_to_highlight:
                    self.log_message(f"PySim: Highlighting state '{item.text_label}'", type_hint="PYSIM_STATUS_UPDATE")
                    item.set_py_sim_active_style(True)
                    self._py_sim_currently_highlighted_item = item
                    if self.view and not self.view.ensureVisible(item, 50, 50): 
                        self.view.centerOn(item)
                    break
        self.scene.update() 

    def _highlight_sim_taken_transition(self, transition_label_or_id: str | None): 
        # TODO: Implement transition highlighting
        # This requires FSMSimulator to return which transition was taken,
        # or enough info (source, target, event) to identify it.
        if self._py_sim_currently_highlighted_transition:
            if hasattr(self._py_sim_currently_highlighted_transition, 'set_py_sim_active_style'): # Assuming this method exists for transitions
                 self._py_sim_currently_highlighted_transition.set_py_sim_active_style(False)
            self._py_sim_currently_highlighted_transition = None
        
        self.scene.update()


    def _update_py_simulation_dock_ui(self):
        if not self.py_fsm_engine or not self.py_sim_active:
            self.py_sim_current_state_label.setText("<i>Not Running</i>")
            self.py_sim_variables_table.setRowCount(0)
            self._highlight_sim_active_state(None)
            self._highlight_sim_taken_transition(None) 
            self.py_sim_event_combo.clear() 
            self.py_sim_event_combo.addItem("None (Internal Step)")
            return

        current_state = self.py_fsm_engine.get_current_state_name()
        self.py_sim_current_state_label.setText(f"<b>{html.escape(current_state or 'N/A')}</b>")
        self._highlight_sim_active_state(current_state) 

        variables = self.py_fsm_engine.get_variables()
        self.py_sim_variables_table.setRowCount(len(variables))
        for row, (name, value) in enumerate(sorted(variables.items())): 
            self.py_sim_variables_table.setItem(row, 0, QTableWidgetItem(str(name)))
            self.py_sim_variables_table.setItem(row, 1, QTableWidgetItem(str(value)))
        self.py_sim_variables_table.resizeColumnsToContents()

        current_combo_text = self.py_sim_event_combo.currentText()
        self.py_sim_event_combo.clear()
        self.py_sim_event_combo.addItem("None (Internal Step)")
        possible_events = self.py_fsm_engine.get_possible_events_from_current_state() 
        if possible_events:
            self.py_sim_event_combo.addItems(sorted(list(set(possible_events)))) 
        
        index = self.py_sim_event_combo.findText(current_combo_text)
        if index != -1:
            self.py_sim_event_combo.setCurrentIndex(index)
        elif not possible_events: 
             self.py_sim_event_combo.setCurrentIndex(0)


    def _append_to_py_simulation_log(self, log_entries: list[str]):
        for entry in log_entries:
            cleaned_entry = html.escape(entry)
            if "[Condition]" in entry or "[Eval Error]" in entry or "ERROR" in entry.upper():
                cleaned_entry = f"<span style='color:{COLOR_ACCENT_SECONDARY};'>{cleaned_entry}</span>" 
            elif "Transitioned from" in entry or "Reset to state" in entry or "Simulation started" in entry:
                cleaned_entry = f"<span style='color:{COLOR_ACCENT_PRIMARY}; font-weight:bold;'>{cleaned_entry}</span>" 
            elif "No eligible transition" in entry:
                cleaned_entry = f"<span style='color:{COLOR_TEXT_SECONDARY};'>{cleaned_entry}</span>" 

            self.py_sim_action_log_output.append(cleaned_entry)
        self.py_sim_action_log_output.verticalScrollBar().setValue(self.py_sim_action_log_output.verticalScrollBar().maximum())

        if log_entries:
            last_log_short = log_entries[-1].split('\n')[0][:100]
            important_keywords = ["Transitioned from", "No eligible transition", "ERROR", "Reset to state", "Simulation started", "Simulation stopped"]
            if any(keyword in log_entries[-1] for keyword in important_keywords): 
                self.log_message(f"PySim: {last_log_short}", type_hint="PYSIM_STATUS_UPDATE")

    def on_start_py_simulation(self):
        if self.py_sim_active:
            QMessageBox.information(self, "Simulation Active", "Python simulation is already running.")
            return
        
        if self.scene.is_dirty():
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "The diagram has unsaved changes that won't be reflected in the simulation unless saved.\nStart simulation with the current in-memory state anyway?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No:
                return

        diagram_data = self.scene.get_diagram_data()
        if not diagram_data.get('states'):
            QMessageBox.warning(self, "Empty Diagram", "Cannot start simulation: The diagram has no states.")
            return
        try:
            self.py_fsm_engine = FSMSimulator(diagram_data['states'], diagram_data['transitions'])
            self.set_ui_enabled_for_py_sim(True) 
            self.py_sim_action_log_output.clear()
            self.py_sim_action_log_output.setHtml("<i>Simulation log will appear here...</i>") 
            initial_log = ["Python FSM Simulation started."] + self.py_fsm_engine.get_last_executed_actions_log()
            self._append_to_py_simulation_log(initial_log)
            self._update_py_simulation_dock_ui() 
        except Exception as e:
            msg = f"Failed to start Python FSM simulation:\n{e}"
            QMessageBox.critical(self, "FSM Initialization Error", msg)
            self._append_to_py_simulation_log([f"ERROR Starting Sim: {msg}"])
            self.py_fsm_engine = None
            self.set_ui_enabled_for_py_sim(False) 

    def on_stop_py_simulation(self, silent=False):
        if not self.py_sim_active: return

        self._highlight_sim_active_state(None)
        self._highlight_sim_taken_transition(None)

        self.py_fsm_engine = None
        self.set_ui_enabled_for_py_sim(False) 
        self._update_py_simulation_dock_ui() 

        if not silent:
            self._append_to_py_simulation_log(["Python FSM Simulation stopped."])

    def on_reset_py_simulation(self):
        if not self.py_fsm_engine or not self.py_sim_active:
            QMessageBox.warning(self, "Simulation Not Active", "Python simulation is not running. Start it first.")
            return
        try:
            self.py_fsm_engine.reset()
            self.py_sim_action_log_output.append("<hr><i style='color:grey;'>Simulation Reset</i><hr>")
            reset_logs = self.py_fsm_engine.get_last_executed_actions_log()
            self._append_to_py_simulation_log(reset_logs)
            self._update_py_simulation_dock_ui()
            self._highlight_sim_taken_transition(None) 
        except Exception as e:
            msg = f"Failed to reset Python FSM simulation:\n{e}"
            QMessageBox.critical(self, "FSM Reset Error", msg)
            self._append_to_py_simulation_log([f"ERROR DURING RESET: {msg}"])

    def on_step_py_simulation(self): 
        if not self.py_fsm_engine or not self.py_sim_active:
            QMessageBox.warning(self, "Simulation Not Active", "Python simulation is not running.")
            return
        try:
            _, log_entries = self.py_fsm_engine.step(event_name=None)
            self._append_to_py_simulation_log(log_entries)
            self._update_py_simulation_dock_ui()
            self._highlight_sim_taken_transition(None) 
        except Exception as e:
            msg = f"Simulation Step Error: {e}"
            QMessageBox.warning(self, "Simulation Step Error", str(e))
            self._append_to_py_simulation_log([f"ERROR DURING STEP: {msg}"])

    def on_trigger_py_event(self): 
        if not self.py_fsm_engine or not self.py_sim_active:
            QMessageBox.warning(self, "Simulation Not Active", "Python simulation is not running.")
            return

        event_name_from_combo = self.py_sim_event_combo.currentText()
        event_name_from_edit = self.py_sim_event_name_edit.text().strip()

        event_to_trigger = None
        if event_name_from_edit: 
            event_to_trigger = event_name_from_edit
        elif event_name_from_combo and event_name_from_combo != "None (Internal Step)":
            event_to_trigger = event_name_from_combo
        
        if not event_to_trigger: 
            self.on_step_py_simulation() 
            return
        
        try:
            _, log_entries = self.py_fsm_engine.step(event_name=event_to_trigger)
            self._append_to_py_simulation_log(log_entries)
            self._update_py_simulation_dock_ui()
            self.py_sim_event_name_edit.clear() 
            self._highlight_sim_taken_transition(None) 
        except Exception as e:
            msg = f"Simulation Event Error ({html.escape(event_to_trigger)}): {e}"
            QMessageBox.warning(self, "Simulation Event Error", str(e))
            self._append_to_py_simulation_log([f"ERROR DURING EVENT '{html.escape(event_to_trigger)}': {msg}"])


if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app_dir = os.path.dirname(os.path.abspath(__file__))
    dependencies_dir = os.path.join(app_dir, "dependencies", "icons")
    if not os.path.exists(dependencies_dir):
        try:
            os.makedirs(dependencies_dir, exist_ok=True)
            print(f"Info: Created directory for QSS icons (if needed): {dependencies_dir}")
        except OSError as e:
            print(f"Warning: Could not create directory {dependencies_dir}: {e}")

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET_GLOBAL) 
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())

