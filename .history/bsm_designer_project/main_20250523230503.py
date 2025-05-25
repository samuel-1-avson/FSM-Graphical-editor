
# bsm_designer_project/main.py

import sys
import os
import tempfile 
import subprocess 
import json
import html 
import math 
import socket 
import re

print("Python Path (sys.path):")
for p in sys.path:
    print(f"  - {p}")

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
    QEvent, QTimer, QSize, QTime, QUrl,
    QSaveFile, QIODevice
)

from fsm_simulator import FSMSimulator, FSMError
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
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from undo_commands import (AddItemCommand, RemoveItemsCommand, MoveItemsCommand,
                           EditItemPropertiesCommand)
from dialogs import (StatePropertiesDialog, TransitionPropertiesDialog, CommentPropertiesDialog,
                     MatlabSettingsDialog)


class DraggableToolButton(QPushButton):
    def __init__(self, text, mime_type, item_type_data, parent=None):
        super().__init__(text, parent)
        self.setObjectName("DraggableToolButton"); self.mime_type = mime_type
        self.item_type_data = item_type_data; self.setText(text)
        self.setMinimumHeight(40); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.drag_start_position = QPoint()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton: self.drag_start_position = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton): return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance(): return
        drag = QDrag(self); mime_data = QMimeData(); mime_data.setText(self.item_type_data)
        mime_data.setData(self.mime_type, self.item_type_data.encode()); drag.setMimeData(mime_data)
        pixmap_size = QSize(max(150, self.width()), max(40, self.height())); pixmap = QPixmap(pixmap_size)
        pixmap.fill(Qt.transparent); painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing)
        button_rect = QRectF(0, 0, pixmap_size.width() -1, pixmap_size.height() -1)
        bg_color = QColor(self.palette().color(self.backgroundRole())).lighter(110)
        if not bg_color.isValid() or bg_color.alpha() == 0 : bg_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT)
        border_color_qcolor = QColor(COLOR_ACCENT_PRIMARY)
        painter.setBrush(bg_color); painter.setPen(QPen(border_color_qcolor, 1.5))
        painter.drawRoundedRect(button_rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5)
        icon_pixmap = self.icon().pixmap(QSize(20, 20), QIcon.Normal, QIcon.On)
        text_x_offset = 10; icon_y_offset = (pixmap_size.height() - icon_pixmap.height()) / 2
        if not icon_pixmap.isNull():
            painter.drawPixmap(int(text_x_offset), int(icon_y_offset), icon_pixmap)
            text_x_offset += icon_pixmap.width() + 8
        text_color_qcolor = self.palette().color(QPalette.ButtonText)
        if not text_color_qcolor.isValid(): text_color_qcolor = QColor(COLOR_TEXT_PRIMARY)
        painter.setPen(text_color_qcolor); painter.setFont(self.font())
        text_rect = QRectF(text_x_offset, 0, pixmap_size.width() - text_x_offset - 5, pixmap_size.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text()); painter.end()
        drag.setPixmap(pixmap); drag.setHotSpot(QPoint(pixmap.width() // 4, pixmap.height() // 2))
        drag.exec_(Qt.CopyAction | Qt.MoveAction)


class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool)

    def __init__(self, undo_stack, parent_window=None):
        super().__init__(parent_window)
        self.parent_window = parent_window; self.setSceneRect(0, 0, 6000, 4500) 
        self.current_mode = "select"; self.transition_start_item = None 
        self.log_function = print; self.undo_stack: QUndoStack = undo_stack
        self._dirty = False; self._mouse_press_items_positions = {} 
        self._temp_transition_line = None 
        self.item_moved.connect(self._handle_item_moved)
        self.grid_size = 20
        self.grid_pen_light = QPen(QColor(COLOR_GRID_MINOR), 0.7, Qt.DotLine)
        self.grid_pen_dark = QPen(QColor(COLOR_GRID_MAJOR), 0.9, Qt.SolidLine)
        self.setBackgroundBrush(QColor(COLOR_BACKGROUND_LIGHT)); self.snap_to_grid_enabled = True

    def _update_connected_transitions(self, state_item: GraphicsStateItem):
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem) and \
               (item.start_item == state_item or item.end_item == state_item):
                item.update_path()

    def _update_transitions_for_renamed_state(self, old_name:str, new_name:str):
        # This method is primarily a notification. The actual update happens in
        # EditItemPropertiesCommand if a state name changes, which then updates transition data if needed.
        self.log_function(f"State '{old_name}' renamed to '{new_name}'. Dependent transitions data (if any) was updated.", type_hint="GENERAL")


    def get_state_by_name(self, name: str) -> GraphicsStateItem | None:
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name: return item
        return None

    def set_dirty(self, dirty=True):
        if self._dirty != dirty: self._dirty = dirty; self.modifiedStatusChanged.emit(dirty)
        if self.parent_window: self.parent_window._update_save_actions_enable_state()

    def is_dirty(self): return self._dirty
    def set_log_function(self, log_function): self.log_function = log_function

    def set_mode(self, mode: str):
        old_mode = self.current_mode;
        if old_mode == mode: return
        self.current_mode = mode; self.log_function(f"Interaction mode changed to: {mode}", type_hint="GENERAL")
        self.transition_start_item = None
        if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
        if self.parent_window and self.parent_window.view: self.parent_window.view._restore_cursor_to_scene_mode()
        for item in self.items():
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): item.setFlag(QGraphicsItem.ItemIsMovable, mode == "select")
        # Update QAction check state in MainWindow
        if self.parent_window:
            actions_map = { "select": "select_mode_action", "state": "add_state_mode_action", 
                            "transition": "add_transition_mode_action", "comment": "add_comment_mode_action"}
            action_to_check_name = actions_map.get(mode)
            if action_to_check_name:
                action_to_check = getattr(self.parent_window, action_to_check_name, None)
                if action_to_check and hasattr(action_to_check, 'isChecked') and not action_to_check.isChecked():
                    action_to_check.setChecked(True)


    def select_all(self):
        for item in self.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable: item.setSelected(True)

    def _handle_item_moved(self, moved_item):
        if isinstance(moved_item, GraphicsStateItem): self._update_connected_transitions(moved_item)

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
                if isinstance(top_item_at_pos, GraphicsStateItem): self._handle_transition_click(top_item_at_pos, pos)
                else:
                    if self.transition_start_item: self.log_function("Transition drawing cancelled.", type_hint="GENERAL")
                    self.transition_start_item = None
                    if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
            else: 
                self._mouse_press_items_positions.clear()
                for item in [i for i in self.selectedItems() if i.flags() & QGraphicsItem.ItemIsMovable]:
                    self._mouse_press_items_positions[item] = item.pos()
                super().mousePressEvent(event)
        elif event.button() == Qt.RightButton:
            if top_item_at_pos and isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem)):
                if not top_item_at_pos.isSelected(): self.clearSelection(); top_item_at_pos.setSelected(True)
                self._show_context_menu(top_item_at_pos, event.screenPos())
            else: self.clearSelection()
        else: super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, event.scenePos()))
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            if self._mouse_press_items_positions:
                moved_items_data = []
                emit_item_moved_for = []
                for item, old_pos in self._mouse_press_items_positions.items():
                    new_pos = item.pos()
                    if self.snap_to_grid_enabled:
                        snapped_x = round(new_pos.x() / self.grid_size) * self.grid_size
                        snapped_y = round(new_pos.y() / self.grid_size) * self.grid_size
                        if new_pos.x() != snapped_x or new_pos.y() != snapped_y:
                            item.setPos(snapped_x, snapped_y); new_pos = QPointF(snapped_x, snapped_y)
                    if (new_pos - old_pos).manhattanLength() > 0.1:
                        moved_items_data.append((item, new_pos)) 
                        emit_item_moved_for.append(item)
                if moved_items_data:
                    cmd = MoveItemsCommand(moved_items_data) # Pass (item, new_pos) list
                    self.undo_stack.push(cmd)
                    for item in emit_item_moved_for: self.item_moved.emit(item)
                self._mouse_press_items_positions.clear()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        items_at_pos = self.items(event.scenePos())
        item_to_edit = next((i for i in items_at_pos if isinstance(i, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem))), None)
        if item_to_edit: self.edit_item_properties(item_to_edit)
        else: super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, item, global_pos):
        menu = QMenu()
        edit_action = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        delete_action = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")
        enter_superstate_action = None
        if isinstance(item, GraphicsStateItem) and item.is_superstate:
            enter_superstate_action = menu.addAction(get_standard_icon(QStyle.SP_DirIcon, "Entr"), "Enter Superstate...")
        
        action = menu.exec_(global_pos)
        if action == edit_action: self.edit_item_properties(item)
        elif action == delete_action:
            if not item.isSelected(): self.clearSelection(); item.setSelected(True)
            self.delete_selected_items()
        elif enter_superstate_action and action == enter_superstate_action:
             if self.parent_window: self.parent_window.enter_superstate_view(item)


    def edit_item_properties(self, item):
        old_props = item.get_data(); dialog_executed_and_accepted = False; new_props_from_dialog = None
        DialogType = None; dialog_kwargs = {'parent': self.parent_window, 'current_properties': old_props}

        if isinstance(item, GraphicsStateItem):
            DialogType = StatePropertiesDialog
            dialog_kwargs['scene_ref'] = self # Pass scene itself for context if needed by dialog
        elif isinstance(item, GraphicsTransitionItem): DialogType = TransitionPropertiesDialog
        elif isinstance(item, GraphicsCommentItem): DialogType = CommentPropertiesDialog
        else: return

        dialog = DialogType(**dialog_kwargs)
        if dialog.exec_() == QDialog.Accepted:
            dialog_executed_and_accepted = True; new_props_from_dialog = dialog.get_properties()
            if isinstance(item, GraphicsStateItem) and new_props_from_dialog['name'] != old_props['name'] and \
               self.get_state_by_name(new_props_from_dialog['name']):
                QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state named '{new_props_from_dialog['name']}' already exists.")
                return
        if dialog_executed_and_accepted and new_props_from_dialog is not None:
            final_new_props = old_props.copy(); final_new_props.update(new_props_from_dialog)
            cmd = EditItemPropertiesCommand(item, old_props, final_new_props, f"Edit {type(item).__name__} Properties")
            self.undo_stack.push(cmd)
            name_for_log = final_new_props.get('name', final_new_props.get('event', final_new_props.get('text', 'Item')))
            self.log_function(f"Properties updated for: {name_for_log}", type_hint="GENERAL")
        self.update()

    def _add_item_interactive(self, pos: QPointF, item_type: str, name_prefix:str="Item", initial_data:dict=None):
        current_item = None; initial_data = initial_data or {}
        dialog_kwargs = {'parent': self.parent_window}
        if item_type == "State":
            i = 1; base_name = name_prefix
            while self.get_state_by_name(f"{base_name}{i}"): i += 1
            default_name = f"{base_name}{i}"
            initial_dialog_props = {
                'name': default_name, 'is_initial': initial_data.get('is_initial', False),
                'is_final': initial_data.get('is_final', False), 
                'is_superstate': initial_data.get('is_superstate', False), # Handle from drag
                'sub_fsm_data': initial_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}),
                'color': initial_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG),
                'entry_action':"", 'during_action':"", 'exit_action':"", 'description':""
            }
            dialog_kwargs.update({'current_properties': initial_dialog_props, 'is_new_state': True, 'scene_ref': self})
            props_dialog = StatePropertiesDialog(**dialog_kwargs)
            if props_dialog.exec_() == QDialog.Accepted:
                final_props = props_dialog.get_properties()
                if self.get_state_by_name(final_props['name']) and final_props['name'] != default_name:
                    QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state named '{final_props['name']}' already exists.")
                else:
                    current_item = GraphicsStateItem(pos.x(), pos.y(), 120, 60, final_props['name'], 
                                                     final_props['is_initial'], final_props['is_final'],
                                                     final_props.get('color'), final_props.get('entry_action',""),
                                                     final_props.get('during_action',""), final_props.get('exit_action',""),
                                                     final_props.get('description',""), 
                                                     is_superstate=final_props.get('is_superstate', False), 
                                                     sub_fsm_data=final_props.get('sub_fsm_data'))
            if self.current_mode == "state": self.set_mode("select")
            if not current_item: return
        elif item_type == "Comment":
            dialog_kwargs['current_properties'] = {'text': initial_data.get('text', "Comment" if name_prefix == "Item" else name_prefix)}
            comment_props_dialog = CommentPropertiesDialog(**dialog_kwargs)
            if comment_props_dialog.exec_() == QDialog.Accepted:
                final_comment_props = comment_props_dialog.get_properties()
                if final_comment_props['text']: current_item = GraphicsCommentItem(pos.x(), pos.y(), final_comment_props['text'])
            if not current_item or self.current_mode == "comment": self.set_mode("select"); return
        else: self.log_function(f"Unknown item type: {item_type}", type_hint="GENERAL"); return

        if current_item:
            cmd = AddItemCommand(self, current_item, f"Add {item_type}")
            self.undo_stack.push(cmd)
            log_name = getattr(current_item, 'text_label', getattr(current_item, 'toPlainText', lambda: "Item")())
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
            self.log_function(f"Transition from: {clicked_state_item.text_label}. Click target.", type_hint="GENERAL")
        else:
            if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
            initial_props = {'event': "", 'condition': "", 'action': "", 'color': COLOR_ITEM_TRANSITION_DEFAULT, 'description':"", 'control_offset_x':0, 'control_offset_y':0}
            dialog = TransitionPropertiesDialog(self.parent_window, current_properties=initial_props, is_new_transition=True)
            if dialog.exec_() == QDialog.Accepted:
                props = dialog.get_properties()
                new_trans = GraphicsTransitionItem(self.transition_start_item, clicked_state_item, 
                                                  props['event'], props['condition'], props['action'], 
                                                  props.get('color'), props.get('description', ""))
                new_trans.set_control_point_offset(QPointF(props['control_offset_x'],props['control_offset_y']))
                cmd = AddItemCommand(self, new_trans, "Add Transition")
                self.undo_stack.push(cmd)
                self.log_function(f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{new_trans._compose_label_string()}]", type_hint="GENERAL")
            else: self.log_function("Transition cancelled.", type_hint="GENERAL")
            self.transition_start_item = None; self.set_mode("select")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Delete or (event.key() == Qt.Key_Backspace and sys.platform != 'darwin'):
            if self.selectedItems(): self.delete_selected_items()
        elif event.key() == Qt.Key_Escape:
            if self.current_mode == "transition" and self.transition_start_item:
                self.transition_start_item = None
                if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
                self.log_function("Transition drawing cancelled by Escape.", type_hint="GENERAL"); self.set_mode("select")
            elif self.current_mode != "select": self.set_mode("select")
            else: self.clearSelection()
        else: super().keyPressEvent(event)

    def delete_selected_items(self):
        selected = self.selectedItems();
        if not selected: return
        items_to_del_with_related = set()
        for item in selected:
            items_to_del_with_related.add(item)
            if isinstance(item, GraphicsStateItem):
                for scene_item in self.items():
                    if isinstance(scene_item, GraphicsTransitionItem) and \
                       (scene_item.start_item == item or scene_item.end_item == item):
                        items_to_del_with_related.add(scene_item)
        if items_to_del_with_related:
            cmd = RemoveItemsCommand(self, list(items_to_del_with_related), "Delete Items")
            self.undo_stack.push(cmd)
            self.log_function(f"Queued deletion of {len(items_to_del_with_related)} item(s).", type_hint="GENERAL"); self.clearSelection()

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"): event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"): event.acceptProposedAction()
        else: super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        pos = event.scenePos()
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            item_type_data_str = event.mimeData().text()
            grid_x = round(pos.x() / self.grid_size) * self.grid_size
            grid_y = round(pos.y() / self.grid_size) * self.grid_size
            if "State" in item_type_data_str: grid_x -= 60; grid_y -= 30
            
            initial_props = {}; item_to_add_type = "Item"; name_prefix = "Item"
            if item_type_data_str == "State": item_to_add_type = "State"; name_prefix = "State"
            elif item_type_data_str == "Initial State": item_to_add_type = "State"; name_prefix = "InitialState"; initial_props['is_initial'] = True
            elif item_type_data_str == "Final State": item_to_add_type = "State"; name_prefix = "FinalState"; initial_props['is_final'] = True
            elif item_type_data_str == "Comment": item_to_add_type = "Comment"; name_prefix = "Note"
            # Add for superstate if you create a draggable button for it:
            # elif item_type_data_str == "Superstate": item_to_add_type = "State"; name_prefix = "Superstate"; initial_props['is_superstate'] = True
            else: self.log_function(f"Unknown item type dropped: {item_type_data_str}", type_hint="GENERAL"); event.ignore(); return
            
            self._add_item_interactive(QPointF(grid_x, grid_y), item_type=item_to_add_type, name_prefix=name_prefix, initial_data=initial_props)
            event.acceptProposedAction()
        else: super().dropEvent(event)

    def get_diagram_data(self):
        data = {'states': [], 'transitions': [], 'comments': []}
        for item in self.items():
            if isinstance(item, GraphicsStateItem): data['states'].append(item.get_data())
            elif isinstance(item, GraphicsTransitionItem):
                if item.start_item and item.end_item: data['transitions'].append(item.get_data())
                else: self.log_function(f"Warning: Skipping save of orphaned transition: '{item._compose_label_string()}'.", type_hint="GENERAL")
            elif isinstance(item, GraphicsCommentItem): data['comments'].append(item.get_data())
        return data

    def load_diagram_data(self, data, is_sub_machine_load=False): # Added flag
        if not is_sub_machine_load: # Only clear scene for top-level loads
            self.clear(); self.set_dirty(False)
        
        state_items_map = {}
        for state_data in data.get('states', []):
            state_item = GraphicsStateItem(state_data['x'], state_data['y'], 
                                           state_data.get('width', 120), state_data.get('height', 60),
                                           state_data['name'], state_data.get('is_initial', False),
                                           state_data.get('is_final', False), state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG),
                                           state_data.get('entry_action',""), state_data.get('during_action',""),
                                           state_data.get('exit_action',""), state_data.get('description',""),
                                           is_superstate=state_data.get('is_superstate', False), # Load superstate flag
                                           sub_fsm_data=state_data.get('sub_fsm_data', None)) # Load sub_fsm_data
            self.addItem(state_item); state_items_map[state_data['name']] = state_item
        
        for trans_data in data.get('transitions', []):
            src_item = state_items_map.get(trans_data['source']); tgt_item = state_items_map.get(trans_data['target'])
            if src_item and tgt_item:
                trans_item = GraphicsTransitionItem(src_item, tgt_item, event_str=trans_data.get('event',""), 
                                                   condition_str=trans_data.get('condition',""), action_str=trans_data.get('action',""),
                                                   color=trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT), 
                                                   description=trans_data.get('description',""))
                trans_item.set_control_point_offset(QPointF(trans_data.get('control_offset_x',0), trans_data.get('control_offset_y',0)))
                self.addItem(trans_item)
            else: self.log_function(f"Warning (Load): Could not link transition: Src='{trans_data['source']}', Tgt='{trans_data['target']}'.", type_hint="GENERAL")
        
        for comment_data in data.get('comments', []):
            comment_item = GraphicsCommentItem(comment_data['x'], comment_data['y'], comment_data.get('text', ""))
            comment_item.setTextWidth(comment_data.get('width', 150)); self.addItem(comment_item)
        
        if not is_sub_machine_load: # Only for top-level
            self.set_dirty(False); self.undo_stack.clear()


    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        # ... (existing grid drawing code remains the same) ...
        view_rect = self.views()[0].viewport().rect() if self.views() else rect
        visible_scene_rect = self.views()[0].mapToScene(view_rect).boundingRect() if self.views() else rect
        left = int(visible_scene_rect.left() / self.grid_size) * self.grid_size - self.grid_size
        right = int(visible_scene_rect.right() / self.grid_size) * self.grid_size + self.grid_size
        top = int(visible_scene_rect.top() / self.grid_size) * self.grid_size - self.grid_size
        bottom = int(visible_scene_rect.bottom() / self.grid_size) * self.grid_size + self.grid_size
        painter.setPen(self.grid_pen_light)
        for x in range(left, right, self.grid_size):
            if x % (self.grid_size * 5) != 0: painter.drawLine(x, top, x, bottom)
        for y in range(top, bottom, self.grid_size):
            if y % (self.grid_size * 5) != 0: painter.drawLine(left, y, right, y)
        major_grid_size = self.grid_size * 5
        first_major_left = left - (left % major_grid_size); first_major_top = top - (top % major_grid_size)
        painter.setPen(self.grid_pen_dark)
        for x in range(first_major_left, right, major_grid_size): painter.drawLine(x, top, x, bottom)
        for y in range(first_major_top, bottom, major_grid_size): painter.drawLine(left, y, right, y)


class ZoomableView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag); self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.zoom_level = 0; self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._is_panning_with_space = False; self._is_panning_with_mouse_button = False; self._last_pan_point = QPoint()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y(); factor = 1.12 if delta > 0 else 1 / 1.12
            new_zoom_level = self.zoom_level + (1 if delta > 0 else -1)
            if -15 <= new_zoom_level <= 25: self.scale(factor, factor); self.zoom_level = new_zoom_level
            event.accept()
        else: super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = True; self._last_pan_point = self.mapFromGlobal(QCursor.pos()); self.setCursor(Qt.OpenHandCursor); event.accept()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal: self.scale(1.12, 1.12); self.zoom_level +=1
        elif event.key() == Qt.Key_Minus: self.scale(1/1.12, 1/1.12); self.zoom_level -=1
        elif event.key() == Qt.Key_0 or event.key() == Qt.Key_Asterisk:
            self.resetTransform(); self.zoom_level = 0
            if self.scene(): content_rect = self.scene().itemsBoundingRect()
            if self.scene() and not content_rect.isEmpty(): self.centerOn(content_rect.center())
            elif self.scene(): self.centerOn(self.scene().sceneRect().center())
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
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta_view.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta_view.y())
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
        current_scene_mode = self.scene().current_mode if self.scene() else "select"
        if current_scene_mode == "select": self.setCursor(Qt.ArrowCursor)
        elif current_scene_mode in ["state", "comment"]: self.setCursor(Qt.CrossCursor)
        elif current_scene_mode == "transition": self.setCursor(Qt.PointingHandCursor)
        else: self.setCursor(Qt.ArrowCursor)


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
        self._internet_connected: bool | None = None 
        self.internet_check_timer = QTimer(self) 
        
        # Hierarchy navigation attributes
        self.fsm_view_stack = [] # List of dicts: {'parent_item_name': str|None, 'scene_data': dict, 'view_state': dict, 'window_title_info': tuple}
        self.current_superstate_context_item: GraphicsStateItem | None = None # GSI whose sub-machine is currently displayed

        self.init_ui()
        self.ai_chatbot_manager.statusUpdate.connect(self._update_ai_chat_status)
        self.ai_chatbot_manager.errorOccurred.connect(self._handle_ai_error)
        self.ai_chatbot_manager.set_api_key(None)
        self.ai_chat_display.setObjectName("AIChatDisplay")
        self.ai_chat_input.setObjectName("AIChatInput")
        self.ai_chat_send_button.setObjectName("AIChatSendButton")
        self.ai_chat_status_label.setObjectName("AIChatStatusLabel")
        self._update_ai_chat_status("Status: API Key required. Configure in Settings.")
        self.matlab_status_label.setObjectName("MatlabStatusLabel")
        self.py_sim_status_label.setObjectName("PySimStatusLabel")
        self.internet_status_label.setObjectName("InternetStatusLabel")
        self.status_label.setObjectName("StatusLabel")
        self._update_matlab_status_display(False, "Initializing. Configure or auto-detect.")
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
        print(f"--- MW ({QTime.currentTime().toString('hh:mm:ss.zzz')}): MainWindow initialized. ---")
        if not self.ai_chatbot_manager.api_key: self._update_ai_chat_status("Status: API Key required.")
        else: self._update_ai_chat_status("Status: Ready.")
        
    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050); self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM"))
        self._create_central_widget(); self._create_actions(); self._create_menus(); self._create_toolbars()
        self._create_status_bar(); self._create_docks(); self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state(); self._update_undo_redo_actions_enable_state()
        self.select_mode_action.trigger()

    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self); self.view.setObjectName("MainDiagramView"); self.setCentralWidget(self.view)

    def _create_actions(self):
        self.openai_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "AISet"), "AI Settings...", self, triggered=self.on_openai_settings)
        self.clear_ai_chat_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "Clear"), "Clear Chat", self, triggered=self.on_clear_ai_chat_history)
        def _s(attr, fb=None): return getattr(QStyle,attr,getattr(QStyle,fb,QStyle.SP_CustomBase)) if fb else getattr(QStyle,attr,QStyle.SP_CustomBase)
        self.new_action = QAction(get_standard_icon(_s("SP_FileIcon"), "New"), "&New", self, shortcut=QKeySequence.New, triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(_s("SP_DialogOpenButton"), "Opn"), "&Open...", self, shortcut=QKeySequence.Open, triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(_s("SP_DialogSaveButton"), "Sav"), "&Save", self, shortcut=QKeySequence.Save, triggered=self.on_save_file)
        self.save_as_action = QAction(get_standard_icon(_s("SP_DriveHDIcon"),"SaveAs"),"Save &As...", self, shortcut=QKeySequence.SaveAs, triggered=self.on_save_file_as)
        self.open_example_menu_action = QAction("Open E&xample...", self) # Placeholder, actual actions in menu
        self.exit_action = QAction(get_standard_icon(_s("SP_DialogCloseButton"), "Exit"), "E&xit", self, shortcut=QKeySequence.Quit, triggered=self.close)
        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo"); self.undo_action.setShortcut(QKeySequence.Undo); self.undo_action.setIcon(get_standard_icon(_s("SP_ArrowBack"), "Un"))
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo"); self.redo_action.setShortcut(QKeySequence.Redo); self.redo_action.setIcon(get_standard_icon(_s("SP_ArrowForward"), "Re"))
        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_actions_enable_state); self.undo_stack.canRedoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.go_up_action = QAction(get_standard_icon(QStyle.SP_ArrowUp, "Up"), "Go to Parent FSM", self, triggered=self.go_up_to_parent_fsm, enabled=False)
        self.go_up_action.setShortcut(QKeySequence("Ctrl+Up"))
        self.select_all_action = QAction(get_standard_icon(_s("SP_FileDialogListView", "SP_FileDialogDetailedView"), "All"), "Select &All", self, shortcut=QKeySequence.SelectAll, triggered=self.on_select_all)
        self.delete_action = QAction(get_standard_icon(_s("SP_TrashIcon"), "Del"), "&Delete", self, shortcut=QKeySequence.Delete, triggered=self.on_delete_selected)
        self.mode_action_group = QActionGroup(self); self.mode_action_group.setExclusive(True)
        self.select_mode_action = QAction(QIcon.fromTheme("edit-select", get_standard_icon(_s("SP_ArrowRight"), "Sel")), "Select/Move", self, checkable=True, triggered=lambda: self.scene.set_mode("select")); self.select_mode_action.setObjectName("select_mode_action")
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", get_standard_icon(_s("SP_FileDialogNewFolder"), "St")), "Add State", self, checkable=True, triggered=lambda: self.scene.set_mode("state")); self.add_state_mode_action.setObjectName("add_state_mode_action")
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", get_standard_icon(_s("SP_ArrowForward"), "Tr")), "Add Transition", self, checkable=True, triggered=lambda: self.scene.set_mode("transition")); self.add_transition_mode_action.setObjectName("add_transition_mode_action")
        self.add_comment_mode_action = QAction(QIcon.fromTheme("insert-text", get_standard_icon(_s("SP_MessageBoxInformation"), "Cm")), "Add Comment", self, checkable=True, triggered=lambda: self.scene.set_mode("comment")); self.add_comment_mode_action.setObjectName("add_comment_mode_action")
        for action in [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action]: self.mode_action_group.addAction(action)
        self.select_mode_action.setChecked(True)
        self.export_simulink_action = QAction(get_standard_icon(_s("SP_ArrowUp","ExpSim"), "->M"), "&Export to Simulink...", self, triggered=self.on_export_simulink)
        self.run_simulation_action = QAction(get_standard_icon(_s("SP_MediaPlay"), "RunM"), "&Run Simulation (MATLAB)...", self, triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(_s("SP_DialogSaveButton", "GenC"), "Cde"), "Generate &Code (C/C++ via MATLAB)...", self, triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(_s("SP_ComputerIcon"), "CfgM"), "&MATLAB Settings...", self, triggered=self.on_matlab_settings)
        self.start_py_sim_action = QAction(get_standard_icon(_s("SP_MediaPlay"), "Py▶"), "&Start Python Simulation", self, triggered=self.on_start_py_simulation)
        self.stop_py_sim_action = QAction(get_standard_icon(_s("SP_MediaStop"), "Py■"), "S&top Python Simulation", self, triggered=self.on_stop_py_simulation, enabled=False)
        self.reset_py_sim_action = QAction(get_standard_icon(_s("SP_MediaSkipBackward"), "Py«"), "&Reset Python Simulation", self, triggered=self.on_reset_py_simulation, enabled=False)
        self.quick_start_action = QAction(get_standard_icon(QStyle.SP_MessageBoxQuestion, "QS"), "&Quick Start Guide", self, triggered=self.on_show_quick_start)
        self.about_action = QAction(get_standard_icon(_s("SP_DialogHelpButton"), "?"), "&About", self, triggered=self.on_about)

    def _create_menus(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File"); file_menu.addAction(self.new_action); file_menu.addAction(self.open_action)
        example_menu = file_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ex"), "Open E&xample")
        self.open_example_traffic_action = example_menu.addAction("Traffic Light FSM", lambda: self._open_example_file("traffic_light.bsm"))
        self.open_example_toggle_action = example_menu.addAction("Simple Toggle FSM", lambda: self._open_example_file("simple_toggle.bsm"))
        file_menu.addAction(self.save_action); file_menu.addAction(self.save_as_action); file_menu.addSeparator()
        file_menu.addAction(self.export_simulink_action); file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        edit_menu = menu_bar.addMenu("&Edit"); edit_menu.addAction(self.undo_action); edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator(); edit_menu.addAction(self.go_up_action); edit_menu.addSeparator()
        edit_menu.addAction(self.delete_action); edit_menu.addAction(self.select_all_action); edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Mode"),"Interaction Mode")
        mode_menu.addAction(self.select_mode_action); mode_menu.addAction(self.add_state_mode_action); mode_menu.addAction(self.add_transition_mode_action); mode_menu.addAction(self.add_comment_mode_action)
        sim_menu = menu_bar.addMenu("&Simulation")
        py_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_MediaPlay, "PyS"), "Python Simulation"); py_sim_menu.addAction(self.start_py_sim_action); py_sim_menu.addAction(self.stop_py_sim_action); py_sim_menu.addAction(self.reset_py_sim_action)
        sim_menu.addSeparator()
        matlab_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_ComputerIcon, "M"), "MATLAB/Simulink"); matlab_sim_menu.addAction(self.run_simulation_action); matlab_sim_menu.addAction(self.generate_code_action); matlab_sim_menu.addSeparator(); matlab_sim_menu.addAction(self.matlab_settings_action)
        self.view_menu = menu_bar.addMenu("&View")
        ai_menu = menu_bar.addMenu("&AI Assistant"); ai_menu.addAction(self.clear_ai_chat_action) ; ai_menu.addAction(self.openai_settings_action)
        help_menu = menu_bar.addMenu("&Help"); help_menu.addAction(self.quick_start_action); help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(22,22); tb_style = Qt.ToolButtonTextBesideIcon
        file_toolbar = self.addToolBar("File"); file_toolbar.setObjectName("FileToolBar"); file_toolbar.setIconSize(icon_size); file_toolbar.setToolButtonStyle(tb_style); file_toolbar.addAction(self.new_action); file_toolbar.addAction(self.open_action); file_toolbar.addAction(self.save_action)
        edit_toolbar = self.addToolBar("Edit"); edit_toolbar.setObjectName("EditToolBar"); edit_toolbar.setIconSize(icon_size); edit_toolbar.setToolButtonStyle(tb_style); edit_toolbar.addAction(self.undo_action); edit_toolbar.addAction(self.redo_action); edit_toolbar.addSeparator(); self.go_up_button = edit_toolbar.addAction(self.go_up_action); edit_toolbar.addSeparator(); edit_toolbar.addAction(self.delete_action)
        tools_tb = self.addToolBar("Interaction Tools"); tools_tb.setObjectName("ToolsToolBar"); tools_tb.setIconSize(icon_size); tools_tb.setToolButtonStyle(tb_style); tools_tb.addAction(self.select_mode_action); tools_tb.addAction(self.add_state_mode_action); tools_tb.addAction(self.add_transition_mode_action); tools_tb.addAction(self.add_comment_mode_action)
        sim_toolbar = self.addToolBar("Simulation Tools"); sim_toolbar.setObjectName("SimulationToolBar"); sim_toolbar.setIconSize(icon_size); sim_toolbar.setToolButtonStyle(tb_style); sim_toolbar.addAction(self.start_py_sim_action); sim_toolbar.addAction(self.stop_py_sim_action); sim_toolbar.addAction(self.reset_py_sim_action); sim_toolbar.addSeparator(); sim_toolbar.addAction(self.export_simulink_action); sim_toolbar.addAction(self.run_simulation_action); sim_toolbar.addAction(self.generate_code_action)

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self); self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready"); self.status_bar.addWidget(self.status_label, 1)
        self.py_sim_status_label = QLabel("PySim: Idle"); self.py_sim_status_label.setToolTip("Internal Python FSM Simulation Status."); self.status_bar.addPermanentWidget(self.py_sim_status_label)
        self.matlab_status_label = QLabel("MATLAB: Init..."); self.matlab_status_label.setToolTip("MATLAB connection status."); self.status_bar.addPermanentWidget(self.matlab_status_label)
        self.internet_status_label = QLabel("Internet: Init..."); self.internet_status_label.setToolTip("Internet connectivity. Checks periodically."); self.status_bar.addPermanentWidget(self.internet_status_label)
        self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0,0); self.progress_bar.setVisible(False); self.progress_bar.setMaximumWidth(150); self.progress_bar.setTextVisible(False); self.status_bar.addPermanentWidget(self.progress_bar)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)
        # Tools Dock
        self.tools_dock = QDockWidget("Tools", self); self.tools_dock.setObjectName("ToolsDock"); self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_main_widget = QWidget(); tools_main_layout = QVBoxLayout(tools_main_widget); tools_main_layout.setSpacing(10); tools_main_layout.setContentsMargins(5,5,5,5)
        mode_group = QGroupBox("Interaction Modes"); mode_layout = QVBoxLayout(); mode_layout.setSpacing(5)
        self.tb_select_btn = QToolButton(); self.tb_select_btn.setDefaultAction(self.select_mode_action)
        self.tb_add_state_btn = QToolButton(); self.tb_add_state_btn.setDefaultAction(self.add_state_mode_action)
        self.tb_add_trans_btn = QToolButton(); self.tb_add_trans_btn.setDefaultAction(self.add_transition_mode_action)
        self.tb_add_comment_btn = QToolButton(); self.tb_add_comment_btn.setDefaultAction(self.add_comment_mode_action)
        for btn in [self.tb_select_btn, self.tb_add_state_btn, self.tb_add_trans_btn, self.tb_add_comment_btn]: btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(18,18)); mode_layout.addWidget(btn)
        mode_group.setLayout(mode_layout); tools_main_layout.addWidget(mode_group)
        draggable_group = QGroupBox("Drag New Elements"); draggable_layout = QVBoxLayout(); draggable_layout.setSpacing(5)
        drag_state = DraggableToolButton(" State", "application/x-bsm-tool", "State"); drag_state.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))
        drag_initial = DraggableToolButton(" Initial State", "application/x-bsm-tool", "Initial State"); drag_initial.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt"))
        drag_final = DraggableToolButton(" Final State", "application/x-bsm-tool", "Final State"); drag_final.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt"))
        drag_comment = DraggableToolButton(" Comment", "application/x-bsm-tool", "Comment"); drag_comment.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))
        # drag_super = DraggableToolButton(" Superstate", "application/x-bsm-tool", "Superstate"); drag_super.setIcon(get_standard_icon(QStyle.SP_DirIcon, "SupSt")) # Example for superstate
        for btn in [drag_state, drag_initial, drag_final, drag_comment]: btn.setIconSize(QSize(18,18)); draggable_layout.addWidget(btn)
        draggable_group.setLayout(draggable_layout); tools_main_layout.addWidget(draggable_group)
        tools_main_layout.addStretch(); self.tools_dock.setWidget(tools_main_widget); self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock); self.view_menu.addAction(self.tools_dock.toggleViewAction())
        # Log Dock
        self.log_dock = QDockWidget("Output Log", self); self.log_dock.setObjectName("LogDock"); self.log_output = QTextEdit(); self.log_output.setObjectName("LogOutputWidget"); self.log_output.setReadOnly(True); self.log_dock.setWidget(self.log_output); self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock); self.view_menu.addAction(self.log_dock.toggleViewAction())
        # Properties Dock
        self.properties_dock = QDockWidget("Element Properties", self); self.properties_dock.setObjectName("PropertiesDock"); props_widget = QWidget(); self.props_layout = QVBoxLayout(props_widget); self.props_layout.setSpacing(8); self.props_layout.setContentsMargins(5,5,5,5); self.props_label = QLabel("<i>No item selected.</i>"); self.props_label.setAlignment(Qt.AlignTop | Qt.AlignLeft); self.props_label.setWordWrap(True); self.props_label.setTextInteractionFlags(Qt.TextSelectableByMouse); self.props_edit_btn = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton,"Edt"), " Edit Details..."); self.props_edit_btn.setEnabled(False); self.props_edit_btn.clicked.connect(self._on_edit_selected_item_properties_from_dock); self.props_edit_btn.setIconSize(QSize(16,16)); self.props_layout.addWidget(self.props_label, 1); self.props_layout.addWidget(self.props_edit_btn); self.properties_dock.setWidget(props_widget); self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock); self.view_menu.addAction(self.properties_dock.toggleViewAction())
        self._create_py_simulation_dock()
        self._create_ai_chatbot_dock()

    def _create_py_simulation_dock(self):
        self.py_sim_dock = QDockWidget("Python FSM Simulation", self); self.py_sim_dock.setObjectName("PySimDock"); py_sim_widget = QWidget(); py_sim_main_layout = QVBoxLayout(py_sim_widget); py_sim_main_layout.setSpacing(8); py_sim_main_layout.setContentsMargins(5,5,5,5)
        ctrl_row1 = QHBoxLayout(); self.py_sim_start_btn = QToolButton(); self.py_sim_start_btn.setDefaultAction(self.start_py_sim_action); self.py_sim_stop_btn = QToolButton(); self.py_sim_stop_btn.setDefaultAction(self.stop_py_sim_action); self.py_sim_reset_btn = QToolButton(); self.py_sim_reset_btn.setDefaultAction(self.reset_py_sim_action)
        for btn in [self.py_sim_start_btn, self.py_sim_stop_btn, self.py_sim_reset_btn]: btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(18,18)); ctrl_row1.addWidget(btn)
        py_sim_main_layout.addLayout(ctrl_row1); ctrl_row2 = QHBoxLayout(); self.py_sim_step_btn = QPushButton(get_standard_icon(QStyle.SP_MediaSeekForward, "Py→S"), " Step (Internal)"); self.py_sim_step_btn.clicked.connect(self.on_step_py_simulation); self.py_sim_step_btn.setIconSize(QSize(18,18)); ctrl_row2.addWidget(self.py_sim_step_btn); self.py_sim_event_edit = QLineEdit(); self.py_sim_event_edit.setPlaceholderText("Enter event name..."); self.py_sim_trigger_btn = QPushButton(get_standard_icon(QStyle.SP_ArrowForward, ">Ev"), " Trigger Event"); self.py_sim_trigger_btn.clicked.connect(self.on_trigger_py_event); self.py_sim_trigger_btn.setIconSize(QSize(18,18)); ctrl_row2.addWidget(self.py_sim_event_edit, 1); ctrl_row2.addWidget(self.py_sim_trigger_btn); py_sim_main_layout.addLayout(ctrl_row2)
        disp_group = QGroupBox("Simulation Status"); disp_layout = QFormLayout(disp_group); disp_layout.setSpacing(6); self.py_sim_curr_state_lbl = QLabel("<i>Not Running</i>"); disp_layout.addRow("Current State:", self.py_sim_curr_state_lbl); self.py_sim_vars_table = QTableWidget(); self.py_sim_vars_table.setColumnCount(2); self.py_sim_vars_table.setHorizontalHeaderLabels(["Variable", "Value"]); self.py_sim_vars_table.horizontalHeader().setStretchLastSection(True); self.py_sim_vars_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive); self.py_sim_vars_table.verticalHeader().setVisible(False); self.py_sim_vars_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.py_sim_vars_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.py_sim_vars_table.setAlternatingRowColors(True); self.py_sim_vars_table.setFixedHeight(150); disp_layout.addRow("FSM Variables:", self.py_sim_vars_table); py_sim_main_layout.addWidget(disp_group)
        log_group = QGroupBox("Python Simulation Action Log"); log_layout = QVBoxLayout(log_group); log_layout.setContentsMargins(2,2,2,2); self.py_sim_action_log = QTextEdit(); self.py_sim_action_log.setObjectName("PySimActionLog"); self.py_sim_action_log.setReadOnly(True); self.py_sim_action_log.setMinimumHeight(100); log_layout.addWidget(self.py_sim_action_log); py_sim_main_layout.addWidget(log_group, 1)
        py_sim_widget.setLayout(py_sim_main_layout); self.py_sim_dock.setWidget(py_sim_widget); self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock); self.view_menu.addAction(self.py_sim_dock.toggleViewAction())

    def _create_ai_chatbot_dock(self):
        # ... (AI Chatbot dock creation - code remains the same as previous version) ...
        self.ai_chatbot_dock = QDockWidget("AI Assistant", self); self.ai_chatbot_dock.setObjectName("AIChatbotDock"); self.ai_chatbot_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        chatbot_widget = QWidget(); chatbot_layout = QVBoxLayout(chatbot_widget); chatbot_layout.setSpacing(6); chatbot_layout.setContentsMargins(5,5,5,5)
        self.ai_chat_display = QTextEdit(); self.ai_chat_display.setObjectName("AIChatDisplay"); self.ai_chat_display.setReadOnly(True); self.ai_chat_display.setPlaceholderText("AI chat history..."); chatbot_layout.addWidget(self.ai_chat_display, 1)
        input_row = QHBoxLayout(); self.ai_chat_input = QLineEdit(); self.ai_chat_input.setObjectName("AIChatInput"); self.ai_chat_input.setPlaceholderText("Ask AI..."); self.ai_chat_input.returnPressed.connect(self._on_send_ai_chat_message); input_row.addWidget(self.ai_chat_input, 1)
        self.ai_chat_send_button = QPushButton(get_standard_icon(QStyle.SP_DialogYesButton, "Send"), "Send"); self.ai_chat_send_button.setObjectName("AIChatSendButton"); self.ai_chat_send_button.setIconSize(QSize(16,16)); self.ai_chat_send_button.clicked.connect(self._on_send_ai_chat_message); input_row.addWidget(self.ai_chat_send_button); chatbot_layout.addLayout(input_row)
        self.ai_chat_status_label = QLabel(); self.ai_chat_status_label.setObjectName("AIChatStatusLabel"); chatbot_layout.addWidget(self.ai_chat_status_label)
        chatbot_widget.setLayout(chatbot_layout); self.ai_chatbot_dock.setWidget(chatbot_widget); self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock)
        if hasattr(self, 'view_menu'):
            self.view_menu.addSeparator()
            ai_dock_action = self.ai_chatbot_dock.toggleViewAction(); ai_dock_action.setText("AI Assistant Panel"); self.view_menu.addAction(ai_dock_action)

    # --- AI Chatbot Methods (mostly unchanged, ensure object names are correct) ---
    def _on_send_ai_chat_message(self):
        user_message = self.ai_chat_input.text().strip()
        if not user_message: return
        self._append_to_ai_chat_display("You", user_message); self.ai_chat_input.clear()
        self._update_ai_chat_status("Status: Sending..."); self.ai_chatbot_manager.send_message(user_message)

    def _handle_ai_response(self, ai_message_text: str):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        final_status = "Status: Ready."; processed_as_fsm = False; fsm_desc = None
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", ai_message_text, re.DOTALL | re.IGNORECASE)
        json_string = None
        if json_match: json_string = json_match.group(1).strip(); self.log_message("AI: JSON in markdown.", type_hint="AI_ACTION")
        else:
            first_brace = ai_message_text.find('{');
            if first_brace != -1:
                balance = 0; last_brace_idx = -1
                for i, char in enumerate(ai_message_text[first_brace:]):
                    if char == '{': balance += 1
                    elif char == '}': balance -= 1
                    if balance == 0: last_brace_idx = first_brace + i; break
                if last_brace_idx != -1: json_string = ai_message_text[first_brace : last_brace_idx + 1]
        if json_string:
            try:
                fsm_data = json.loads(json_string)
                if isinstance(fsm_data, dict) and "states" in fsm_data and "transitions" in fsm_data:
                    processed_as_fsm = True; fsm_desc = fsm_data.get("description", "Generated FSM.")
                    self.log_message("AI: Valid FSM JSON.", type_hint="AI_ACTION")
                    reply = QMessageBox.question(self, "Generate FSM from AI?", "AI provided FSM data. Add to diagram?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                    if reply == QMessageBox.Yes:
                        self._add_fsm_data_to_scene(fsm_data, clear_current_diagram=False)
                        self._append_to_ai_chat_display("AI Assistant", fsm_desc + " (See diagram)")
                        final_status = "Status: FSM elements added."
                    else: self._append_to_ai_chat_display("AI Assistant", "[FSM data received, user chose not to add.]"); final_status = "Status: FSM generation cancelled."
                else: self.log_message("AI: JSON not FSM structure.", type_hint="AI_ACTION")
            except json.JSONDecodeError as e: self.log_message(f"AI: JSON parse error: {e}", type_hint="AIChatError")
        if not processed_as_fsm: self._append_to_ai_chat_display("AI Assistant", ai_message_text)
        self._update_ai_chat_status(final_status)
        
    def _add_fsm_data_to_scene(self, fsm_data: dict, clear_current_diagram: bool = False):
        # ... (Code for _add_fsm_data_to_scene remains the same as previous version) ...
        if clear_current_diagram: self.scene.clear(); self.undo_stack.clear(); self.log_message("Cleared diagram for AI gen.", type_hint="AI_ACTION")
        state_items_map = {}; start_x, start_y = 100,100; items_per_row=3; def_w,def_h=120,60; pad_x,pad_y=150,100
        items_to_add_cmds = []
        for i, state_data in enumerate(fsm_data.get('states',[])):
            name = state_data.get('name');
            if not name: self.log_message(f"AI Gen: State missing name. Skip: {state_data}", type_hint="AIChatError"); continue
            pos_x = state_data.get('x', start_x + (i % items_per_row) * (def_w+pad_x))
            pos_y = state_data.get('y', start_y + (i // items_per_row) * (def_h+pad_y))
            item_w = state_data.get('width', def_w); item_h = state_data.get('height', def_h)
            try:
                state_item = GraphicsStateItem(pos_x,pos_y,item_w,item_h,name,
                                               is_initial=state_data.get('is_initial',False),is_final=state_data.get('is_final',False),
                                               color=state_data.get('properties',{}).get('color'),
                                               entry_action=state_data.get('entry_action',""),during_action=state_data.get('during_action',""),
                                               exit_action=state_data.get('exit_action',""),description=state_data.get('description',""),
                                               is_superstate=state_data.get('is_superstate',False), # Handle superstate from AI
                                               sub_fsm_data=state_data.get('sub_fsm_data', None) # Handle sub_fsm_data
                                              )
                items_to_add_cmds.append(AddItemCommand(self.scene, state_item, f"Add AI State: {name}"))
                state_items_map[name] = state_item
            except Exception as e: self.log_message(f"AI Gen: Error creating State '{name}': {e}", type_hint="AIChatError")
        for trans_data in fsm_data.get('transitions',[]):
            src_name=trans_data.get('source'); tgt_name=trans_data.get('target')
            if not src_name or not tgt_name: self.log_message(f"AI Gen: Trans missing src/tgt. Skip: {trans_data}", type_hint="AIChatError"); continue
            src_item=state_items_map.get(src_name); tgt_item=state_items_map.get(tgt_name)
            if src_item and tgt_item:
                try:
                    trans_item = GraphicsTransitionItem(src_item,tgt_item,
                                                       event_str=trans_data.get('event',""),condition_str=trans_data.get('condition',""),
                                                       action_str=trans_data.get('action',""),color=trans_data.get('properties',{}).get('color'),
                                                       description=trans_data.get('description',""))
                    off_x=trans_data.get('control_offset_x'); off_y=trans_data.get('control_offset_y')
                    if off_x is not None and off_y is not None: trans_item.set_control_point_offset(QPointF(float(off_x),float(off_y)))
                    items_to_add_cmds.append(AddItemCommand(self.scene, trans_item, f"Add AI Trans: {src_name}->{tgt_name}"))
                except Exception as e: self.log_message(f"AI Gen: Error creating Trans '{src_name}'->'{tgt_name}': {e}", type_hint="AIChatError")
            else: self.log_message(f"AI Gen: Trans missing state for '{src_name}'->'{tgt_name}'. Skip.", type_hint="AIChatError")
        max_y_states = max((item.scenePos().y()+item.rect().height() for item in state_items_map.values()),default=start_y) if state_items_map else start_y
        comment_y_start = max_y_states + pad_y
        for i, comment_data in enumerate(fsm_data.get('comments',[])):
            text=comment_data.get('text');
            if not text: continue
            cmt_x=comment_data.get('x', start_x + i*(150+20)); cmt_y=comment_data.get('y', comment_y_start)
            cmt_w=comment_data.get('width')
            try:
                comment_item = GraphicsCommentItem(cmt_x,cmt_y,text)
                if cmt_w is not None: comment_item.setTextWidth(float(cmt_w))
                items_to_add_cmds.append(AddItemCommand(self.scene, comment_item, f"Add AI Comment: {text[:15]}..."))
            except Exception as e: self.log_message(f"AI Gen: Error creating Comment: {e}", type_hint="AIChatError")
        if items_to_add_cmds:
            self.undo_stack.beginMacro("Add AI Generated FSM")
            for cmd in items_to_add_cmds: self.undo_stack.push(cmd)
            self.undo_stack.endMacro()
            self.scene.set_dirty(True); QTimer.singleShot(0, self._fit_view_to_new_ai_items)

    def _fit_view_to_new_ai_items(self):
        if not self.scene.items(): return
        bounds = self.scene.itemsBoundingRect()
        if self.view and not bounds.isNull(): self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
        elif self.view: self.view.centerOn(self.scene.sceneRect().center())    

    def _handle_ai_error(self, error_message: str):
        self._append_to_ai_chat_display("System Error", error_message)
        self.log_message(f"AI Chatbot Error: {error_message}", type_hint="AIChatError") 
        short_err = error_message.split('\n')[0].split(':')[0][:50] 
        self._update_ai_chat_status(f"Error: {short_err}")

    def _update_ai_chat_status(self, status_text: str):
        if hasattr(self, 'ai_chat_status_label'):
            self.ai_chat_status_label.setText(status_text)
            is_thinking = "thinking..." in status_text.lower() or "sending..." in status_text.lower()
            is_key_req = "api key required" in status_text.lower() or "inactive" in status_text.lower()
            is_err = "error" in status_text.lower() or "failed" in status_text.lower() or is_key_req
            if is_err: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: red;")
            elif is_thinking: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;")
            else: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;")
            can_send = not is_thinking and not is_key_req
            if hasattr(self, 'ai_chat_send_button'): self.ai_chat_send_button.setEnabled(can_send)
            if hasattr(self, 'ai_chat_input'):
                self.ai_chat_input.setEnabled(can_send)
                if can_send: self.ai_chat_input.setFocus()
                 
    def _append_to_ai_chat_display(self, sender: str, message: str):
        timestamp = QTime.currentTime().toString('hh:mm') 
        color = COLOR_ACCENT_PRIMARY
        if sender == "You": color = COLOR_ACCENT_SECONDARY
        elif sender == "System Error": color = "#D32F2F"
        fmt_msg = (f"<div style='margin-bottom:5px;'><span style='font-size:8pt;color:grey;'>[{timestamp}]</span> "
                   f"<strong style='color:{color};'>{html.escape(sender)}:</strong> "
                   f"{html.escape(message).replace(r'\n','<br>')}</div>")
        self.ai_chat_display.append(fmt_msg); self.ai_chat_display.ensureCursorVisible()

    def on_openai_settings(self):
        current_key = self.ai_chatbot_manager.api_key or ""
        key, ok = QInputDialog.getText(self, "OpenAI API Key", "Enter OpenAI API Key (blank to clear):", 
                                       QLineEdit.PasswordEchoOnEdit, current_key)
        if ok:
            new_key = key.strip()
            self.ai_chatbot_manager.set_api_key(new_key if new_key else None)
            self.log_message(f"OpenAI API Key {'set' if new_key else 'cleared'}.", type_hint="AI_CONFIG")

    def on_clear_ai_chat_history(self):
        if self.ai_chatbot_manager:
            self.ai_chatbot_manager.clear_conversation_history()
            if hasattr(self, 'ai_chat_display'):
                self.ai_chat_display.clear(); self.ai_chat_display.setPlaceholderText("AI chat history...")
    
    # --- Property Dock Update ---
    def _update_properties_dock(self):
        selected = self.scene.selectedItems(); html = ""; edit_enabled = False; item_type_tooltip = "item"
        if len(selected) == 1:
            item = selected[0]; props = item.get_data(); item_type = type(item).__name__.replace("Graphics","").replace("Item","")
            item_type_tooltip = item_type.lower(); edit_enabled = True
            def fmt_prop(txt, max_chars=25):
                if not txt: return "<i>(none)</i>"
                esc = html.escape(str(txt)); first_line = esc.split('\n')[0]
                return first_line[:max_chars] + "…" if len(first_line) > max_chars or '\n' in esc else first_line
            rows = ""
            if isinstance(item, GraphicsStateItem):
                color_val = props.get('color', COLOR_ITEM_STATE_DEFAULT_BG); c_obj=QColor(color_val); txt_c='black' if c_obj.lightnessF()>0.5 else 'white'; c_style=f"background-color:{color_val};color:{txt_c};padding:1px 4px;border-radius:2px;"
                rows += f"<tr><td><b>Name:</b></td><td>{html.escape(props['name'])}</td></tr>"
                rows += f"<tr><td><b>Initial:</b></td><td>{'Yes' if props.get('is_initial') else 'No'}</td></tr><tr><td><b>Final:</b></td><td>{'Yes' if props.get('is_final') else 'No'}</td></tr>"
                rows += f"<tr><td><b>Superstate:</b></td><td>{'Yes' if props.get('is_superstate') else 'No'}</td></tr>" # Superstate info
                rows += f"<tr><td><b>Color:</b></td><td><span style='{c_style}'>{html.escape(props.get('color','N/A'))}</span></td></tr>"
                rows += f"<tr><td><b>Entry:</b></td><td>{fmt_prop(props.get('entry_action',''))}</td></tr>"
                rows += f"<tr><td><b>During:</b></td><td>{fmt_prop(props.get('during_action',''))}</td></tr>"
                rows += f"<tr><td><b>Exit:</b></td><td>{fmt_prop(props.get('exit_action',''))}</td></tr>"
                if props.get('description'): rows += f"<tr><td colspan='2'><b>Desc:</b> {fmt_prop(props.get('description'),50)}</td></tr>"
            elif isinstance(item, GraphicsTransitionItem):
                # ... (Transition property display - same as before) ...
                color_val=props.get('color',COLOR_ITEM_TRANSITION_DEFAULT);c_obj=QColor(color_val);txt_c='black' if c_obj.lightnessF()>0.5 else 'white';c_style=f"background-color:{color_val};color:{txt_c};padding:1px 4px;border-radius:2px;"
                evt=html.escape(props.get('event','')) if props.get('event') else ''; cnd=f"[{html.escape(props.get('condition',''))}]" if props.get('condition') else ''; act=f"/{{{fmt_prop(props.get('action',''),15)}}}" if props.get('action') else ''
                lbl_parts=[p for p in [evt,cnd,act] if p]; full_lbl=" ".join(lbl_parts) if lbl_parts else "<i>(No Label)</i>"
                rows+=f"<tr><td><b>Label:</b></td><td style='font-size:8pt;'>{full_lbl}</td></tr><tr><td><b>From:</b></td><td>{html.escape(props.get('source','N/A'))}</td></tr><tr><td><b>To:</b></td><td>{html.escape(props.get('target','N/A'))}</td></tr>"
                rows+=f"<tr><td><b>Color:</b></td><td><span style='{c_style}'>{html.escape(props.get('color','N/A'))}</span></td></tr>"
                rows+=f"<tr><td><b>Curve:</b></td><td>Bend={props.get('control_offset_x',0):.0f}, Shift={props.get('control_offset_y',0):.0f}</td></tr>"
                if props.get('description'): rows+=f"<tr><td colspan='2'><b>Desc:</b> {fmt_prop(props.get('description'),50)}</td></tr>"
            elif isinstance(item, GraphicsCommentItem): rows += f"<tr><td colspan='2'><b>Text:</b> {fmt_prop(props.get('text',''),60)}</td></tr>"
            else: rows = "<tr><td>Unknown Item</td></tr>"
            html = f"""<div style='font-family:"Segoe UI,Arial,sans-serif";font-size:9pt;line-height:1.5;'><h4 style='margin:0 0 5px 0;padding:2px 0;color:{COLOR_ACCENT_PRIMARY};border-bottom:1px solid {COLOR_BORDER_LIGHT};'>Type: {item_type}</h4><table style='width:100%;border-collapse:collapse;'>{rows}</table></div>"""
        elif len(selected) > 1: html = f"<i><b>{len(selected)} items selected.</b><br>Select one to view/edit.</i>"; item_type_tooltip = f"{len(selected)} items"
        else: html = "<i>No item selected.</i><br><small>Click an item or use tools to add.</small>"
        self.props_label.setText(html); self.props_edit_btn.setEnabled(edit_enabled)
        self.props_edit_btn.setToolTip(f"Edit {item_type_tooltip} properties" if edit_enabled else "Select one item to edit")

    def _on_edit_selected_item_properties_from_dock(self):
        selected = self.scene.selectedItems()
        if len(selected) == 1: self.scene.edit_item_properties(selected[0])

    def log_message(self, message: str, type_hint: str = "GENERAL"):
        # ... (Log message formatting - same as before, with new type_hints if needed) ...
        timestamp = QTime.currentTime().toString('hh:mm:ss.zzz')
        display_message = html.escape(message)
        formatted_log_entry = f"<span style='color:{COLOR_TEXT_SECONDARY};'>[{timestamp}]</span> "
        if type_hint == "NETWATCH": formatted_log_entry += f"<span style='color:grey;'><i>(NetChk)</i> {display_message}</span>"
        elif type_hint == "MATLAB_CONN": formatted_log_entry += f"<span style='color:{COLOR_TEXT_SECONDARY};'><i>(MATLAB)</i> {display_message}</span>"
        elif type_hint == "PYSIM_STATUS_UPDATE": formatted_log_entry += f"<span style='color:{COLOR_ACCENT_PRIMARY};'><i>(PySim)</i> {display_message}</span>"
        elif type_hint == "AI_CONFIG": formatted_log_entry += f"<span style='color:blue;'><i>(AI Cfg)</i> {display_message}</span>"
        elif type_hint == "AIChatError": formatted_log_entry += f"<span style='color:red;'><i>(AI Err)</i> {display_message}</span>"
        elif type_hint == "AI_ACTION": formatted_log_entry += f"<span style='color:purple;'><i>(AI Act)</i> {display_message}</span>"
        elif type_hint == "NAVIGATION": formatted_log_entry += f"<span style='color:green;'><i>(Nav)</i> {display_message}</span>"
        else: formatted_log_entry += display_message # GENERAL
        self.log_output.append(formatted_log_entry)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
        # Avoid flooding status bar with frequent/internal logs
        if type_hint not in ["NETWATCH", "MATLAB_CONN", "AI_CONFIG", "AIChatError", "AI_ACTION", "PYSIM_STATUS_UPDATE", "NAVIGATION"] and "worker:" not in message : 
            self.status_label.setText(message.split('\n')[0][:120])

    # Hierarchy Navigation Methods
    def enter_superstate_view(self, superstate_item: GraphicsStateItem):
        if not superstate_item or not superstate_item.is_superstate: return
        current_scene_data = self.scene.get_diagram_data()
        view_state = {'transform': self.view.transform(), 'h_scroll': self.view.horizontalScrollBar().value(),
                      'v_scroll': self.view.verticalScrollBar().value(), 'zoom_level': self.view.zoom_level}
        
        # parent_item_name is the name of the GSI we were *previously* inside, or None if top level
        parent_name_for_stack = self.current_superstate_context_item.text_label if self.current_superstate_context_item else None
        
        self.fsm_view_stack.append({
            'parent_item_name': parent_name_for_stack, 
            'scene_data': current_scene_data, 'view_state': view_state,
            'window_title_info': (self.current_file_path, self.isWindowModified())
        })
        self.current_superstate_context_item = superstate_item # This GSI's sub_fsm is now being viewed
        self.scene.clear(); self.undo_stack.clear() # Each level has its own undo stack
        self.scene.load_diagram_data(superstate_item.sub_fsm_data, is_sub_machine_load=True)
        self.scene.set_dirty(False)
        self._update_window_title(); self._update_navigation_actions()
        self.log_message(f"Entered superstate: {superstate_item.text_label}", type_hint="NAVIGATION")
        QTimer.singleShot(0, lambda: self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-50,-50,50,50), Qt.KeepAspectRatio) if self.scene.itemsBoundingRect().isValid() else None)


    def go_up_to_parent_fsm(self):
        if not self.fsm_view_stack: self.log_message("Already at top-level FSM.", type_hint="NAVIGATION"); return

        # Save current sub-machine's data back to the parent GSI in the parent's scene_data structure
        current_sub_fsm_edited_data = self.scene.get_diagram_data()
        parent_context_to_restore = self.fsm_view_stack[-1] # Data of the FSM level we are returning to
        parent_scene_data_to_modify = parent_context_to_restore['scene_data']
        
        # `self.current_superstate_context_item` is the GSI whose sub-machine we were just editing.
        # Its definition lives in `parent_scene_data_to_modify`.
        parent_gsi_name_to_update = self.current_superstate_context_item.text_label
        updated_in_parent_data = False

        for state_data_in_parent in parent_scene_data_to_modify.get('states', []):
            if state_data_in_parent.get('name') == parent_gsi_name_to_update:
                state_data_in_parent['sub_fsm_data'] = current_sub_fsm_edited_data
                state_data_in_parent['is_superstate'] = True # Ensure still marked
                updated_in_parent_data = True
                self.log_message(f"Saved changes from sub-machine '{parent_gsi_name_to_update}' to its definition.", type_hint="NAVIGATION")
                break
        if not updated_in_parent_data: self.log_message(f"Warning: Could not find parent state '{parent_gsi_name_to_update}' in parent data to save sub-machine changes.", type_hint="ERROR")

        # Pop and load the parent FSM level
        restored_context = self.fsm_view_stack.pop()
        self.scene.clear(); self.undo_stack.clear()
        self.scene.load_diagram_data(restored_context['scene_data'], is_sub_machine_load=True) # is_sub_machine_load means don't clear undo stack etc.
        
        # Set the current_superstate_context_item for the level we just loaded
        # This is the GSI whose sub-FSM we *would* enter if we went down again from this level.
        # It's the 'parent_item_name' stored in the *new* top of the stack (if stack not empty)
        if self.fsm_view_stack:
            new_context_parent_name = self.fsm_view_stack[-1].get('parent_item_name')
            self.current_superstate_context_item = self.scene.get_state_by_name(new_context_parent_name) if new_context_parent_name else None
        else: # Now at the very top level
            self.current_superstate_context_item = None
            
        # Restore view and window state
        self.view.setTransform(restored_context['view_state']['transform'])
        self.view.horizontalScrollBar().setValue(restored_context['view_state']['h_scroll'])
        self.view.verticalScrollBar().setValue(restored_context['view_state']['v_scroll'])
        self.view.zoom_level = restored_context['view_state']['zoom_level']
        self.current_file_path = restored_context['window_title_info'][0]
        # If sub-machine was modified, the parent FSM level is now considered modified
        parent_is_dirty = restored_context['window_title_info'][1] or (updated_in_parent_data and self.scene.is_dirty())
        self.setWindowModified(parent_is_dirty) # is_dirty of current scene reflects sub-machine's state
        self._update_window_title(); self._update_navigation_actions()
        log_dest_name = self.current_superstate_context_item.text_label if self.current_superstate_context_item else "Top-Level FSM"
        self.log_message(f"Returned to parent FSM. Current level: {log_dest_name}", type_hint="NAVIGATION")


    def _update_navigation_actions(self):
        can_go_up = bool(self.fsm_view_stack)
        self.go_up_action.setEnabled(can_go_up)
        if hasattr(self, 'go_up_button'): self.go_up_button.setEnabled(can_go_up)

    # --- Other MainWindow methods (file ops, sim ops, etc.) ---
    # (Many methods like _update_window_title, save/load, sim, matlab ops, etc. largely unchanged)
    # Need to adjust _update_window_title for hierarchy
    def _update_window_title(self):
        base_title = APP_NAME
        file_name_part = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        
        # Construct navigation path for title
        nav_path_parts = []
        if self.current_superstate_context_item: # If we are inside a sub-machine
            # Start with the name of the GSI whose sub-FSM is currently open
            nav_path_parts.append(f"{self.current_superstate_context_item.text_label} (Sub)")
            
            # Trace back through the stack to get parent names
            # Each 'parent_item_name' in the stack is the GSI containing the 'scene_data' of that level
            for entry in reversed(self.fsm_view_stack):
                containing_superstate_name = entry.get('parent_item_name')
                if containing_superstate_name:
                    nav_path_parts.insert(0, containing_superstate_name)
                # If parent_item_name is None, it means that stack entry was for the top-level FSM view.
        
        if nav_path_parts:
            title_fsm_part = f"{file_name_part} > " + " > ".join(nav_path_parts)
        else:
            title_fsm_part = file_name_part

        title = f"{base_title} - {title_fsm_part}"
        if self.py_sim_active: title += " [PySim Running]"
        title += "[*]" # For modified status
        self.setWindowTitle(title)

    def _update_save_actions_enable_state(self): self.save_action.setEnabled(self.isWindowModified())
    def _update_undo_redo_actions_enable_state(self):
        # Undo/Redo is per FSM level for now
        self.undo_action.setEnabled(self.undo_stack.canUndo()); self.redo_action.setEnabled(self.undo_stack.canRedo())
        self.undo_action.setText(f"&Undo {self.undo_stack.undoText()}" if self.undo_stack.canUndo() else "&Undo")
        self.redo_action.setText(f"&Redo {self.undo_stack.redoText()}" if self.undo_stack.canRedo() else "&Redo")

    def _update_matlab_status_display(self, connected, message):
        text = f"MATLAB: {'Connected' if connected else 'Not Connected'}"; tooltip = f"MATLAB Status: {message}"
        self.matlab_status_label.setText(text); self.matlab_status_label.setToolTip(tooltip)
        style = f"font-weight: bold; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE if connected else '#C62828'};"
        self.matlab_status_label.setStyleSheet(style)
        if "Initializing" not in message: self.log_message(f"MATLAB Conn: {message}", type_hint="MATLAB_CONN")
        self._update_matlab_actions_enabled_state()

    def _update_matlab_actions_enabled_state(self):
        # MATLAB ops typically on top-level FSM or currently viewed FSM if that makes sense.
        # For now, let's assume MATLAB ops are primarily for the currently active view.
        # Disable if deep inside a sub-machine might be too restrictive.
        can_run_matlab = self.matlab_connection.connected and not self.py_sim_active
        for action in [self.export_simulink_action, self.run_simulation_action, self.generate_code_action]: action.setEnabled(can_run_matlab)
        self.matlab_settings_action.setEnabled(not self.py_sim_active)

    def _start_matlab_operation(self, op_name):
        self.log_message(f"MATLAB Op: {op_name} starting...", type_hint="MATLAB_CONN")
        self.status_label.setText(f"Running: {op_name}..."); self.progress_bar.setVisible(True); self.set_ui_enabled_for_matlab_op(False)
    def _finish_matlab_operation(self):
        self.progress_bar.setVisible(False); self.status_label.setText("Ready"); self.set_ui_enabled_for_matlab_op(True)
        self.log_message("MATLAB Op: Finished processing.", type_hint="MATLAB_CONN")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        self.menuBar().setEnabled(enabled)
        for child in self.findChildren(QToolBar): child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock"]:
            dock = self.findChild(QDockWidget, dock_name); 
            if dock: dock.setEnabled(enabled)
        self._update_py_simulation_actions_enabled_state() # Re-eval PySim actions

    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation(); self.log_message(f"MATLAB Result ({('Success' if success else 'Failure')}): {message}", type_hint="MATLAB_CONN")
        if success:
            if "Model generation" in message and data: self.last_generated_model_path = data; QMessageBox.information(self, "Simulink Model Generation", f"Simulink model generated:\n{data}")
            elif "Simulation" in message: QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else: QMessageBox.warning(self, "MATLAB Operation Failed", message)

    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation(); self.log_message(f"MATLAB Code Gen Result ({('Success' if success else 'Failure')}): {message}", type_hint="MATLAB_CONN")
        if success and output_dir:
            msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Information); msg_box.setWindowTitle("Code Generation Successful"); msg_box.setTextFormat(Qt.RichText); msg_box.setText(f"Code generation completed.<br>Output: <a href='file:///{os.path.abspath(output_dir)}'>{os.path.abspath(output_dir)}</a>"); msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction)
            open_btn = msg_box.addButton("Open Directory", QMessageBox.ActionRole); msg_box.addButton(QMessageBox.Ok); msg_box.exec_()
            if msg_box.clickedButton() == open_btn:
                try: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(output_dir)))
                except Exception as e: self.log_message(f"Error opening dir {output_dir}: {e}", type_hint="GENERAL")
        elif not success: QMessageBox.warning(self, "Code Generation Failed", message)

    def _prompt_save_if_dirty(self) -> bool:
        # If currently viewing a sub-machine, prompt to save it back to its parent.
        # This requires more thought on how "dirty" status propagates up.
        # For now, a simple check on current view:
        if not self.isWindowModified(): return True
        if self.py_sim_active: QMessageBox.warning(self, "Simulation Active", "Stop Python sim before saving/opening."); return False
        
        fsm_level_name = "current FSM"
        if self.current_superstate_context_item:
            fsm_level_name = f"sub-machine '{self.current_superstate_context_item.text_label}'"
        else:
            fsm_level_name = f"'{os.path.basename(self.current_file_path) if self.current_file_path else 'Untitled'}'"

        reply = QMessageBox.question(self, "Save Changes?", f"The {fsm_level_name} has unsaved changes.\nDo you want to save them?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        
        if reply == QMessageBox.Save:
            if self.current_superstate_context_item: # Saving a sub-machine
                # This implies saving the *entire* hierarchy if the top-level file is known
                # Or, just saving the sub-machine data into its parent structure in memory.
                # For now, let's assume Save while in sub-machine means "Save the whole thing from top"
                return self._save_top_level_fsm()
            else: # Saving top-level FSM
                return self.on_save_file()
        return reply != QMessageBox.Cancel

    def _save_top_level_fsm(self) -> bool:
        """Ensures we are at the top level before saving the main file."""
        if not self.fsm_view_stack: # Already at top
            return self.on_save_file()

        # Need to go up, saving changes at each level, then save the top file.
        # This is complex if done directly. A simpler approach for now:
        QMessageBox.information(self, "Saving Hierarchy",
                                "To save, please navigate to the top-level FSM view first using 'Go to Parent FSM' (Ctrl+Up), then save the main file. "
                                "Changes in sub-machines will be incorporated when you navigate up.")
        return False # Indicate save was not performed directly here.

    def on_new_file(self, silent=False):
        if not silent and not self._prompt_save_if_dirty(): return False
        self.on_stop_py_simulation(silent=True)
        # Reset hierarchy navigation
        self.fsm_view_stack.clear()
        self.current_superstate_context_item = None
        self._update_navigation_actions()

        self.scene.clear(); self.scene.setSceneRect(0,0,6000,4500)
        self.current_file_path = None; self.last_generated_model_path = None
        self.undo_stack.clear(); self.scene.set_dirty(False)
        self._update_window_title(); self._update_undo_redo_actions_enable_state()
        if not silent: self.log_message("New diagram created.", type_hint="GENERAL")
        self.view.resetTransform(); self.view.centerOn(self.scene.sceneRect().center()); self.select_mode_action.trigger()
        return True

    def on_open_file(self):
        if not self._prompt_save_if_dirty(): return
        self.on_stop_py_simulation(silent=True)
        # Reset hierarchy before opening new top-level file
        self.fsm_view_stack.clear()
        self.current_superstate_context_item = None
        self._update_navigation_actions()

        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)
        if file_path:
            self.log_message(f"Opening file: {file_path}", type_hint="GENERAL")
            if self._load_from_path(file_path): # This loads into current scene
                self.current_file_path = file_path; self.last_generated_model_path = None
                self.undo_stack.clear(); self.scene.set_dirty(False) # Scene dirty status is set by load_diagram_data
                self._update_window_title(); self._update_undo_redo_actions_enable_state()
                self.log_message(f"Opened: {file_path}", type_hint="GENERAL")
                bounds = self.scene.itemsBoundingRect()
                if not bounds.isEmpty(): self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else: self.view.resetTransform(); self.view.centerOn(self.scene.sceneRect().center())
            else: QMessageBox.critical(self, "Error Opening File", f"Could not load file: {file_path}")

    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
            if not isinstance(data, dict) or ('states' not in data or 'transitions' not in data):
                self.log_message(f"Error: Invalid BSM file format in {file_path}.", type_hint="GENERAL"); return False
            # Pass is_sub_machine_load=False for top-level file load
            self.scene.load_diagram_data(data, is_sub_machine_load=False) 
            return True
        except Exception as e: self.log_message(f"Error loading {file_path}: {e}", type_hint="GENERAL"); return False

    def on_save_file(self) -> bool:
        if self.fsm_view_stack: # If in a sub-machine view
            return self._save_top_level_fsm()
        return self._save_to_path(self.current_file_path) if self.current_file_path else self.on_save_file_as()

    def on_save_file_as(self) -> bool:
        if self.fsm_view_stack: # If in a sub-machine view
            return self._save_top_level_fsm()
        start_path = self.current_file_path or os.path.join(QDir.homePath(), "untitled" + FILE_EXTENSION)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As", start_path, FILE_FILTER)
        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION): file_path += FILE_EXTENSION
            if self._save_to_path(file_path):
                self.current_file_path = file_path # Update current file path
                # scene.set_dirty(False) is handled by _save_to_path
                self._update_window_title()
                return True
        return False

    def _save_to_path(self, file_path) -> bool:
        if self.fsm_view_stack: # Should not be called directly if in sub-machine from public API
            self.log_message("Internal Error: _save_to_path called while in sub-machine view.", type_hint="ERROR")
            return self._save_top_level_fsm()

        # Ensure current scene (top-level) data is what's saved
        diagram_data_to_save = self.scene.get_diagram_data()
        
        save_file_obj = QSaveFile(file_path)
        if not save_file_obj.open(QIODevice.WriteOnly | QIODevice.Text):
            err = save_file_obj.errorString(); QMessageBox.critical(self, "Save Error", f"Failed to open for saving:\n{err}"); return False
        try:
            json_data = json.dumps(diagram_data_to_save, indent=4, ensure_ascii=False)
            if save_file_obj.write(json_data.encode('utf-8')) == -1:
                err = save_file_obj.errorString(); QMessageBox.critical(self, "Save Error", f"Failed to write data:\n{err}"); save_file_obj.cancelWriting(); return False
            if not save_file_obj.commit():
                err = save_file_obj.errorString(); QMessageBox.critical(self, "Save Error", f"Failed to commit saved file:\n{err}"); return False
            self.log_message(f"File saved: {file_path}", type_hint="GENERAL")
            self.scene.set_dirty(False) # Mark current scene (top-level) as not dirty
            return True
        except Exception as e: QMessageBox.critical(self, "Save Error", f"Error during saving:\n{e}"); save_file_obj.cancelWriting(); return False


    def on_select_all(self): self.scene.select_all()
    def on_delete_selected(self): self.scene.delete_selected_items()

    def on_export_simulink(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected."); return
        # Ensure we are exporting the top-level FSM
        if self.fsm_view_stack:
            QMessageBox.information(self, "Export Simulink", "Please navigate to the top-level FSM view to export the entire model to Simulink.")
            return

        # ... (rest of on_export_simulink - dialogs and call to matlab_connection - same as before) ...
        # The diagram_data passed to matlab_connection.generate_simulink_model will now include sub_fsm_data
        # if superstates exist, and the matlab_integration module is updated to handle it.
        dialog = QDialog(self); dialog.setWindowTitle("Export to Simulink"); dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp, "->M")); layout = QFormLayout(dialog); layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)
        model_name_default = "".join(c if c.isalnum() or c=='_' else '_' for c in os.path.splitext(os.path.basename(self.current_file_path))[0]) if self.current_file_path else "BSM_SimulinkModel"
        if not model_name_default or not model_name_default[0].isalpha(): model_name_default = "Model_" + model_name_default
        model_name_edit = QLineEdit(model_name_default); layout.addRow("Simulink Model Name:", model_name_edit)
        default_out_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        output_dir_edit = QLineEdit(default_out_dir); browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw")," Browse..."); browse_btn.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text()) or output_dir_edit.text())); dir_layout = QHBoxLayout(); dir_layout.addWidget(output_dir_edit, 1); dir_layout.addWidget(browse_btn); layout.addRow("Output Directory:", dir_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addRow(buttons); dialog.setMinimumWidth(450)
        if dialog.exec_() == QDialog.Accepted:
            model_name = model_name_edit.text().strip(); output_dir = output_dir_edit.text().strip()
            if not model_name or not output_dir: QMessageBox.warning(self, "Input Error", "Model name and output directory must be specified."); return
            if not model_name[0].isalpha() or not all(c.isalnum() or c == '_' for c in model_name): QMessageBox.warning(self, "Invalid Model Name", "Model name must start with a letter, and contain only alphanumeric characters or underscores."); return
            try: os.makedirs(output_dir, exist_ok=True)
            except OSError as e: QMessageBox.critical(self, "Directory Error", f"Could not create directory:\n{e}"); return
            diagram_data_to_export = self.scene.get_diagram_data() # This is the current view's data
            if not diagram_data_to_export['states']: QMessageBox.information(self, "Empty Diagram", "Cannot export: the diagram contains no states."); return
            self._start_matlab_operation(f"Exporting '{model_name}' to Simulink"); self.matlab_connection.generate_simulink_model(diagram_data_to_export, output_dir, model_name)


    def on_run_simulation(self): # MATLAB simulation
        # ... (same as before) ...
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB not connected."); return
        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model to Simulate", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return
        self.last_generated_model_path = model_path
        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Sim stop time (s):", 10.0, 0.001, 86400.0, 3)
        if not ok: return
        self._start_matlab_operation(f"Running Simulink simulation for '{os.path.basename(model_path)}'"); self.matlab_connection.run_simulation(model_path, sim_time)

    def on_generate_code(self): # MATLAB code gen
        # ... (same as before) ...
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB not connected."); return
        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model for Code Generation", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return
        self.last_generated_model_path = model_path
        dialog = QDialog(self); dialog.setWindowTitle("Code Generation Options"); dialog.setWindowIcon(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde")); layout = QFormLayout(dialog); layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)
        lang_combo = QComboBox(); lang_combo.addItems(["C", "C++"]); lang_combo.setCurrentText("C++"); layout.addRow("Target Language:", lang_combo)
        output_dir_edit = QLineEdit(os.path.dirname(model_path)); browse_btn_codegen = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw")," Browse..."); browse_btn_codegen.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Base Output Directory", output_dir_edit.text()) or output_dir_edit.text())); dir_layout_codegen = QHBoxLayout(); dir_layout_codegen.addWidget(output_dir_edit, 1); dir_layout_codegen.addWidget(browse_btn_codegen); layout.addRow("Base Output Directory:", dir_layout_codegen)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addRow(buttons); dialog.setMinimumWidth(450)
        if dialog.exec_() == QDialog.Accepted:
            language = lang_combo.currentText(); output_dir_base = output_dir_edit.text().strip()
            if not output_dir_base: QMessageBox.warning(self, "Input Error", "Base output directory required."); return
            try: os.makedirs(output_dir_base, exist_ok=True)
            except OSError as e: QMessageBox.critical(self, "Directory Error", f"Could not create directory:\n{e}"); return
            self._start_matlab_operation(f"Generating {language} code for '{os.path.basename(model_path)}'"); self.matlab_connection.generate_code(model_path, language, output_dir_base)

    def on_matlab_settings(self): MatlabSettingsDialog(self.matlab_connection, self).exec_()
    
    def on_show_quick_start(self):
        guide_filename = "QUICK_START.html" 
        guide_path = self._get_bundled_file_path(guide_filename)
        if guide_path:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path)):
                QMessageBox.warning(self, "Could Not Open Guide", f"Failed to open quick start guide: {guide_filename}")
    
    def _get_bundled_file_path(self, filename: str) -> str | None: # Helper for examples/docs
        try: base_path = sys._MEIPASS # type: ignore
        except AttributeError: # Not bundled
            # Try relative to main.py's directory, then one level up (common project structures)
            script_dir = os.path.dirname(__file__)
            paths_to_try = [
                os.path.join(script_dir, "examples", filename),
                os.path.join(script_dir, "..", "examples", filename), # If examples is sibling to bsm_designer_project
                os.path.join(script_dir, filename) # If file is directly in script_dir (e.g. for PyInstaller data files)
            ]
            for p in paths_to_try:
                if os.path.exists(p): return os.path.abspath(p)
            # Fallback if script_dir is "bsm_designer_project" and examples is inside it.
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "examples"))
        
        file_path = os.path.join(base_path, filename)
        if os.path.exists(file_path): return file_path
        else: self.log_message(f"Bundled file '{filename}' not found at: {file_path}",type_hint="ERROR"); return None

    def _open_example_file(self, example_filename: str):
        if not self._prompt_save_if_dirty(): return
        file_path = self._get_bundled_file_path(example_filename)
        if not file_path: QMessageBox.warning(self,"Example Not Found",f"Could not find: {example_filename}"); return
        self.on_stop_py_simulation(silent=True)
        self.fsm_view_stack.clear(); self.current_superstate_context_item = None; self._update_navigation_actions()
        self.log_message(f"Opening example: {file_path}", type_hint="GENERAL")
        if self._load_from_path(file_path):
            self.current_file_path = file_path; self.setWindowModified(False) # Examples are not dirty
            self.last_generated_model_path = None; self.undo_stack.clear()
            self._update_window_title(); self._update_undo_redo_actions_enable_state()
            self.log_message(f"Opened example: {example_filename}", type_hint="GENERAL")
            bounds = self.scene.itemsBoundingRect()
            if not bounds.isEmpty(): self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
            else: self.view.resetTransform(); self.view.centerOn(self.scene.sceneRect().center())
        else: QMessageBox.critical(self, "Error Opening Example", f"Could not load: {example_filename}")


    def on_about(self): QMessageBox.about(self, "About " + APP_NAME, f"<h3 style='color:{COLOR_ACCENT_PRIMARY};'>{APP_NAME} v{APP_VERSION}</h3><p>A graphical tool for designing and simulating Finite State Machines, with integration capabilities for MATLAB/Simulink and an AI assistant.</p><p>Developed to aid in the conceptualization and implementation of state-based logic, particularly for mechatronic and embedded systems.</p><p style='font-size:8pt; color:{COLOR_TEXT_SECONDARY};'>This tool is intended for research, educational, and prototyping purposes.</p>")

    def closeEvent(self, event: QCloseEvent):
        self.on_stop_py_simulation(silent=True)
        if self.internet_check_timer and self.internet_check_timer.isActive(): self.internet_check_timer.stop()
        if self.ai_chatbot_manager: self.ai_chatbot_manager.stop_chatbot()
        if self._prompt_save_if_dirty():
            if self.matlab_connection._active_threads: self.log_message(f"Closing. {len(self.matlab_connection._active_threads)} MATLAB ops may persist.", type_hint="GENERAL")
            event.accept()
        else: 
            event.ignore()
            if self.internet_check_timer: self.internet_check_timer.start()

    def _init_internet_status_check(self):
        self.internet_check_timer.timeout.connect(self._run_internet_check_job); self.internet_check_timer.start(15000) 
        QTimer.singleShot(100, self._run_internet_check_job) 

    def _run_internet_check_job(self):
        host="8.8.8.8"; port=53; timeout=1.5; current_status=False; msg_detail="Checking..."
        try: s=socket.create_connection((host,port),timeout=timeout); s.close(); current_status=True; msg_detail="Connected"
        except socket.timeout: msg_detail = "Disconnected (Timeout)"
        except socket.gaierror: msg_detail = "Disconnected (DNS/Net Issue)"
        except OSError as e: msg_detail = "Disconnected (Net Error)"; self.log_message(f"NetChk OSError: {e.strerror}", type_hint="NETWATCH")
        if current_status != self._internet_connected or self._internet_connected is None:
            self._internet_connected = current_status; self._update_internet_status_display(current_status, msg_detail)

    def _update_internet_status_display(self, is_connected: bool, message_detail: str):
        full_status = f"Internet: {message_detail}"; self.internet_status_label.setText(full_status)
        try: host_name = socket.getfqdn('8.8.8.8')
        except: host_name = '8.8.8.8' 
        self.internet_status_label.setToolTip(f"{full_status} (Checks {host_name}:{53})")
        style = f"padding:0px 5px;color:{COLOR_PY_SIM_STATE_ACTIVE if is_connected else '#D32F2F'};"
        self.internet_status_label.setStyleSheet(style)
        if self._internet_connected is not None: # Avoid logging initial check if not changed
            self.log_message(f"Internet Status: {message_detail}", type_hint="NETWATCH") 

    def _update_py_sim_status_display(self):
        if self.py_sim_active and self.py_fsm_engine:
            state_name = self.py_fsm_engine.get_current_state_name()
            self.py_sim_status_label.setText(f"PySim: Active ({state_name})")
            self.py_sim_status_label.setStyleSheet(f"font-weight:bold;padding:0px 5px;color:{COLOR_PY_SIM_STATE_ACTIVE};")
        else:
            self.py_sim_status_label.setText("PySim: Idle")
            self.py_sim_status_label.setStyleSheet("padding:0px 5px;")

    def _update_py_simulation_actions_enabled_state(self):
        is_matlab_running = self.progress_bar.isVisible(); sim_inactive = not self.py_sim_active
        can_start_py_sim = sim_inactive and not is_matlab_running and not self.fsm_view_stack # No PySim in sub-machines for now
        self.start_py_sim_action.setEnabled(can_start_py_sim); self.py_sim_start_btn.setEnabled(can_start_py_sim)
        can_control_py_sim = self.py_sim_active and not is_matlab_running
        for widget in [self.stop_py_sim_action, self.reset_py_sim_action, self.py_sim_stop_btn, 
                       self.py_sim_reset_btn, self.py_sim_step_btn, self.py_sim_event_edit, 
                       self.py_sim_trigger_btn]:
            widget.setEnabled(can_control_py_sim)

    def set_ui_enabled_for_py_sim(self, is_sim_running: bool):
        self.py_sim_active = is_sim_running; self._update_window_title(); is_editable = not is_sim_running
        if is_editable and self.scene.current_mode != "select": self.scene.set_mode("select")
        elif not is_editable: self.scene.set_mode("select") 
        for item in self.scene.items():
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): item.setFlag(QGraphicsItem.ItemIsMovable, is_editable)
        actions_to_toggle = [self.new_action, self.open_action, self.save_action, self.save_as_action, 
                             self.undo_action, self.redo_action, self.delete_action, self.select_all_action, 
                             self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action,
                             self.go_up_action] # Include navigation
        for action in actions_to_toggle: action.setEnabled(is_editable)
        self.tools_dock.setEnabled(is_editable)
        self.props_edit_btn.setEnabled(is_editable and len(self.scene.selectedItems())==1)
        self._update_matlab_actions_enabled_state(); self._update_py_simulation_actions_enabled_state(); self._update_py_sim_status_display()

    def _highlight_sim_active_state(self, state_name_to_highlight: str | None):
        if self._py_sim_currently_highlighted_item: self._py_sim_currently_highlighted_item.set_py_sim_active_style(False); self._py_sim_currently_highlighted_item = None
        if state_name_to_highlight:
            item = self.scene.get_state_by_name(state_name_to_highlight)
            if item: item.set_py_sim_active_style(True); self._py_sim_currently_highlighted_item = item
        self.scene.update()

    def _update_py_simulation_dock_ui(self):
        if not self.py_fsm_engine or not self.py_sim_active:
            self.py_sim_curr_state_lbl.setText("<i>Not Running</i>"); self.py_sim_vars_table.setRowCount(0); self._highlight_sim_active_state(None); return
        current_state = self.py_fsm_engine.get_current_state_name(); self.py_sim_curr_state_lbl.setText(f"<b>{html.escape(current_state or 'N/A')}</b>"); self._highlight_sim_active_state(current_state)
        variables = self.py_fsm_engine.get_variables(); self.py_sim_vars_table.setRowCount(len(variables))
        for row, (name, value) in enumerate(sorted(variables.items())):
            self.py_sim_vars_table.setItem(row, 0, QTableWidgetItem(str(name))); self.py_sim_vars_table.setItem(row, 1, QTableWidgetItem(str(value)))
        self.py_sim_vars_table.resizeColumnsToContents()

    def _append_to_py_simulation_log(self, log_entries: list[str]):
        for entry in log_entries:
            cleaned = html.escape(entry)
            if "[Condition]" in entry or "[Eval Error]" in entry or "ERROR" in entry.upper(): cleaned = f"<span style='color:{COLOR_ACCENT_SECONDARY};'>{cleaned}</span>"
            elif "Transitioned from" in entry or "Reset to state" in entry or "Simulation started" in entry: cleaned = f"<span style='color:{COLOR_ACCENT_PRIMARY};font-weight:bold;'>{cleaned}</span>"
            elif "No eligible transition" in entry: cleaned = f"<span style='color:{COLOR_TEXT_SECONDARY};'>{cleaned}</span>"
            self.py_sim_action_log.append(cleaned)
        self.py_sim_action_log.verticalScrollBar().setValue(self.py_sim_action_log.verticalScrollBar().maximum())
        if log_entries:
            last_log = log_entries[-1].split('\n')[0][:100]
            if any(k in last_log for k in ["Transitioned","No eligible","ERROR","Reset to","Sim started","Sim stopped"]):
                self.log_message(f"PySim: {last_log}", type_hint="PYSIM_STATUS_UPDATE")

    def on_start_py_simulation(self):
        if self.py_sim_active: QMessageBox.information(self, "Simulation Active", "Python sim already running."); return
        if self.fsm_view_stack: QMessageBox.warning(self, "Sub-Machine View", "Python simulation can only be started on the top-level FSM view for now."); return
        if self.scene.is_dirty() and QMessageBox.question(self, "Unsaved Changes", "Unsaved changes won't be in sim.\nStart anyway?", QMessageBox.Yes|QMessageBox.No, QMessageBox.Yes) == QMessageBox.No: return
        diagram_data = self.scene.get_diagram_data()
        if not diagram_data.get('states'): QMessageBox.warning(self, "Empty Diagram", "No states to simulate."); return
        try:
            self.py_fsm_engine = FSMSimulator(diagram_data['states'], diagram_data['transitions']); self.set_ui_enabled_for_py_sim(True); self.py_sim_action_log.clear()
            initial_log = ["Python FSM Simulation started."] + self.py_fsm_engine.get_last_executed_actions_log() 
            self._append_to_py_simulation_log(initial_log); self._update_py_simulation_dock_ui()
        except Exception as e:
            msg = f"Failed to start Python FSM simulation:\n{e}"; QMessageBox.critical(self, "FSM Init Error", msg); self._append_to_py_simulation_log([f"ERROR Starting Sim: {msg}"])
            self.py_fsm_engine = None; self.set_ui_enabled_for_py_sim(False)

    def on_stop_py_simulation(self, silent=False):
        if not self.py_sim_active: return
        self.py_fsm_engine = None; self.set_ui_enabled_for_py_sim(False); self._update_py_simulation_dock_ui(); self._highlight_sim_active_state(None)
        if not silent: self._append_to_py_simulation_log(["Python FSM Simulation stopped."])

    def on_reset_py_simulation(self):
        if not self.py_fsm_engine or not self.py_sim_active: QMessageBox.warning(self, "Sim Not Active", "Start Python sim first."); return
        try:
            self.py_fsm_engine.reset(); self.py_sim_action_log.append("<hr><i style='color:grey;'>Sim Reset</i><hr>")
            reset_logs = self.py_fsm_engine.get_last_executed_actions_log() 
            self._append_to_py_simulation_log(reset_logs); self._update_py_simulation_dock_ui()
        except Exception as e: msg = f"Failed to reset Py FSM sim:\n{e}"; QMessageBox.critical(self, "FSM Reset Error", msg); self._append_to_py_simulation_log([f"ERROR RESET: {msg}"])

    def on_step_py_simulation(self):
        if not self.py_fsm_engine or not self.py_sim_active: QMessageBox.warning(self, "Sim Not Active", "Python sim not running."); return
        try:
            _, log_entries = self.py_fsm_engine.step(event_name=None); self._append_to_py_simulation_log(log_entries); self._update_py_simulation_dock_ui()
        except Exception as e: msg = f"Sim Step Error: {e}"; QMessageBox.warning(self, "Sim Step Error", str(e)); self._append_to_py_simulation_log([f"ERROR STEP: {msg}"])

    def on_trigger_py_event(self):
        if not self.py_fsm_engine or not self.py_sim_active: QMessageBox.warning(self, "Sim Not Active", "Python sim not running."); return
        event_name = self.py_sim_event_edit.text().strip()
        if not event_name: self.on_step_py_simulation(); return 
        try:
            _, log_entries = self.py_fsm_engine.step(event_name=event_name); self._append_to_py_simulation_log(log_entries); self._update_py_simulation_dock_ui(); self.py_sim_event_edit.clear()
        except Exception as e: msg = f"Sim Event Error ({html.escape(event_name)}): {e}"; QMessageBox.warning(self, "Sim Event Error", str(e)); self._append_to_py_simulation_log([f"ERROR EVENT '{html.escape(event_name)}': {msg}"])

if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app_dir = os.path.dirname(os.path.abspath(__file__)); dependencies_dir = os.path.join(app_dir, "dependencies", "icons")
    if not os.path.exists(dependencies_dir):
        try: os.makedirs(dependencies_dir, exist_ok=True); print(f"Info: Created dir for QSS icons: {dependencies_dir}")
        except OSError as e: print(f"Warning: Could not create dir {dependencies_dir}: {e}")
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET_GLOBAL)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
