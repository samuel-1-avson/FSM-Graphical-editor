
import sys
import os
import tempfile 
import subprocess 
import json
import html 
import math 
import socket 
# sys import is already present at the top

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

# --- FSM SIMULATOR IMPORT ---
from fsm_simulator import FSMSimulator, FSMError

# --- Modularized Imports ---
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


# --- Draggable Toolbox Buttons ---
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
        # Assuming COLOR_ACCENT_PRIMARY_LIGHT & COLOR_ACCENT_PRIMARY are hex strings
        if not bg_color.isValid() or bg_color.alpha() == 0 :
            bg_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT) # QColor() can take hex strings
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
            text_color_qcolor = QColor(COLOR_TEXT_PRIMARY) # Assuming COLOR_TEXT_PRIMARY is a hex string
        painter.setPen(text_color_qcolor)
        painter.setFont(self.font())

        text_rect = QRectF(text_x_offset, 0, pixmap_size.width() - text_x_offset - 5, pixmap_size.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 4, pixmap.height() // 2))
        drag.exec_(Qt.CopyAction | Qt.MoveAction)


# --- Diagram Scene ---
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

        self.item_moved.connect(self._handle_item_moved)

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
        self.log_function(f"State '{old_name}' renamed to '{new_name}'. Dependent transitions may need data update.", type_hint="GENERAL")

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
            for m, action_ref_name in actions_map.items():
                action = getattr(self.parent_window, action_ref_name.objectName(), None) if isinstance(action_ref_name, QAction) else self.parent_window.findChild(QAction, action_ref_name)
                # Fallback for direct action attribute access:
                if not action and hasattr(self.parent_window, action_ref_name) : action = getattr(self.parent_window, action_ref_name)

                if m == mode and action and hasattr(action, 'isChecked') and not action.isChecked():
                    action.setChecked(True)

    def select_all(self):
        for item in self.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable:
                item.setSelected(True)

    def _handle_item_moved(self, moved_item):
        if isinstance(moved_item, GraphicsStateItem):
            self._update_connected_transitions(moved_item)

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
                    if self.transition_start_item: self.log_function("Transition drawing cancelled (clicked non-state/empty space).", type_hint="GENERAL")
                    self.transition_start_item = None
                    if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
            else: 
                self._mouse_press_items_positions.clear()
                selected_items_list = self.selectedItems()
                if selected_items_list:
                    for item_to_process in [item for item in selected_items_list if item.flags() & QGraphicsItem.ItemIsMovable]:
                        self._mouse_press_items_positions[item_to_process] = item_to_process.pos()
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
                moved_items_data_for_command = []
                emit_item_moved_for_these = []
                for item, old_pos in self._mouse_press_items_positions.items():
                    new_pos = item.pos()
                    if self.snap_to_grid_enabled:
                        snapped_x = round(new_pos.x() / self.grid_size) * self.grid_size
                        snapped_y = round(new_pos.y() / self.grid_size) * self.grid_size
                        if new_pos.x() != snapped_x or new_pos.y() != snapped_y:
                            item.setPos(snapped_x, snapped_y) # Snap item
                            new_pos = QPointF(snapped_x, snapped_y) # Update new_pos for command
                    if (new_pos - old_pos).manhattanLength() > 0.1:
                        moved_items_data_for_command.append((item, old_pos, new_pos)) # old_pos is now correctly the original pre-move pos
                        emit_item_moved_for_these.append(item)
                
                if moved_items_data_for_command:
                    # Adjust to (item, new_pos) structure for existing MoveItemsCommand
                    cmd_data = [(item, new_p) for item, old_p, new_p in moved_items_data_for_command]
                    cmd = MoveItemsCommand(cmd_data)
                    self.undo_stack.push(cmd)
                    for item in emit_item_moved_for_these:
                         self.item_moved.emit(item) # Emit after command push for each actual move
                self._mouse_press_items_positions.clear()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        items_at_pos = self.items(event.scenePos())
        item_to_edit = next((item for item in items_at_pos if isinstance(item, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem))), None)
        if item_to_edit: self.edit_item_properties(item_to_edit)
        else: super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, item, global_pos):
        menu = QMenu()
        edit_action = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        delete_action = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")
        action = menu.exec_(global_pos)
        if action == edit_action: self.edit_item_properties(item)
        elif action == delete_action:
            if not item.isSelected(): self.clearSelection(); item.setSelected(True)
            self.delete_selected_items()

    def edit_item_properties(self, item):
        old_props = item.get_data()
        dialog_executed_and_accepted = False; new_props_from_dialog = None; DialogType = None
        if isinstance(item, GraphicsStateItem): DialogType = StatePropertiesDialog
        elif isinstance(item, GraphicsTransitionItem): DialogType = TransitionPropertiesDialog
        elif isinstance(item, GraphicsCommentItem): DialogType = CommentPropertiesDialog
        else: return

        dialog = DialogType(parent=self.parent_window, current_properties=old_props)
        if dialog.exec_() == QDialog.Accepted:
            dialog_executed_and_accepted = True
            new_props_from_dialog = dialog.get_properties()
            if isinstance(item, GraphicsStateItem) and new_props_from_dialog['name'] != old_props['name'] and self.get_state_by_name(new_props_from_dialog['name']):
                QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state with the name '{new_props_from_dialog['name']}' already exists.")
                return

        if dialog_executed_and_accepted and new_props_from_dialog is not None:
            final_new_props = old_props.copy(); final_new_props.update(new_props_from_dialog)
            cmd = EditItemPropertiesCommand(item, old_props, final_new_props, f"Edit {type(item).__name__} Properties")
            self.undo_stack.push(cmd)
            item_name_for_log = final_new_props.get('name', final_new_props.get('event', final_new_props.get('text', 'Item')))
            self.log_function(f"Properties updated for: {item_name_for_log}", type_hint="GENERAL")
        self.update()

    def _add_item_interactive(self, pos: QPointF, item_type: str, name_prefix:str="Item", initial_data:dict=None):
        current_item = None; initial_data = initial_data or {}
        is_initial_state_from_drag = initial_data.get('is_initial', False)
        is_final_state_from_drag = initial_data.get('is_final', False)

        if item_type == "State":
            i = 1; base_name = name_prefix
            while self.get_state_by_name(f"{base_name}{i}"): i += 1
            default_name = f"{base_name}{i}"
            initial_dialog_props = {'name': default_name, 'is_initial': is_initial_state_from_drag, 'is_final': is_final_state_from_drag, 'color': initial_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG), 'entry_action':"", 'during_action':"", 'exit_action':"", 'description':""}
            props_dialog = StatePropertiesDialog(self.parent_window, current_properties=initial_dialog_props, is_new_state=True)
            if props_dialog.exec_() == QDialog.Accepted:
                final_props = props_dialog.get_properties()
                if self.get_state_by_name(final_props['name']) and final_props['name'] != default_name: QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state named '{final_props['name']}' already exists.")
                else: current_item = GraphicsStateItem(pos.x(), pos.y(), 120, 60, final_props['name'], final_props['is_initial'], final_props['is_final'], final_props.get('color'), final_props.get('entry_action',""), final_props.get('during_action',""), final_props.get('exit_action',""), final_props.get('description',""))
            if self.current_mode == "state": self.set_mode("select")
            if not current_item: return
        elif item_type == "Comment":
            initial_text = initial_data.get('text', "Comment" if name_prefix == "Item" else name_prefix)
            comment_props_dialog = CommentPropertiesDialog(self.parent_window, {'text': initial_text})
            if comment_props_dialog.exec_() == QDialog.Accepted:
                final_comment_props = comment_props_dialog.get_properties()
                if final_comment_props['text']: current_item = GraphicsCommentItem(pos.x(), pos.y(), final_comment_props['text'])
                else: self.set_mode("select" if self.current_mode == "comment" else self.current_mode); return
            else: self.set_mode("select" if self.current_mode == "comment" else self.current_mode); return
        else: self.log_function(f"Unknown item type for addition: {item_type}", type_hint="GENERAL"); return

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
            self.log_function(f"Transition started from: {clicked_state_item.text_label}. Click target state.", type_hint="GENERAL")
        else:
            if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
            initial_props = {'event': "", 'condition': "", 'action': "", 'color': COLOR_ITEM_TRANSITION_DEFAULT, 'description':"", 'control_offset_x':0, 'control_offset_y':0}
            dialog = TransitionPropertiesDialog(self.parent_window, current_properties=initial_props, is_new_transition=True)
            if dialog.exec_() == QDialog.Accepted:
                props = dialog.get_properties()
                new_transition = GraphicsTransitionItem(self.transition_start_item, clicked_state_item, event_str=props['event'], condition_str=props['condition'], action_str=props['action'], color=props.get('color'), description=props.get('description', ""))
                new_transition.set_control_point_offset(QPointF(props['control_offset_x'],props['control_offset_y']))
                cmd = AddItemCommand(self, new_transition, "Add Transition")
                self.undo_stack.push(cmd)
                self.log_function(f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{new_transition._compose_label_string()}]", type_hint="GENERAL")
            else: self.log_function("Transition addition cancelled by user.", type_hint="GENERAL")
            self.transition_start_item = None
            self.set_mode("select")

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
        selected = self.selectedItems()
        if not selected: return
        items_to_delete_with_related = set()
        for item in selected:
            items_to_delete_with_related.add(item)
            if isinstance(item, GraphicsStateItem):
                for scene_item in self.items():
                    if isinstance(scene_item, GraphicsTransitionItem) and (scene_item.start_item == item or scene_item.end_item == item):
                        items_to_delete_with_related.add(scene_item)
        if items_to_delete_with_related:
            cmd = RemoveItemsCommand(self, list(items_to_delete_with_related), "Delete Items")
            self.undo_stack.push(cmd)
            self.log_function(f"Queued deletion of {len(items_to_delete_with_related)} item(s).", type_hint="GENERAL"); self.clearSelection()

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
            initial_props_for_add = {}; actual_item_type_to_add = "Item"; name_prefix_for_add = "Item"
            if item_type_data_str == "State": actual_item_type_to_add = "State"; name_prefix_for_add = "State"
            elif item_type_data_str == "Initial State": actual_item_type_to_add = "State"; name_prefix_for_add = "InitialState"; initial_props_for_add['is_initial'] = True
            elif item_type_data_str == "Final State": actual_item_type_to_add = "State"; name_prefix_for_add = "FinalState"; initial_props_for_add['is_final'] = True
            elif item_type_data_str == "Comment": actual_item_type_to_add = "Comment"; name_prefix_for_add = "Note"
            else: self.log_function(f"Unknown item type dropped: {item_type_data_str}", type_hint="GENERAL"); event.ignore(); return
            self._add_item_interactive(QPointF(grid_x, grid_y), item_type=actual_item_type_to_add, name_prefix=name_prefix_for_add, initial_data=initial_props_for_add)
            event.acceptProposedAction()
        else: super().dropEvent(event)

    def get_diagram_data(self):
        data = {'states': [], 'transitions': [], 'comments': []}
        for item in self.items():
            if isinstance(item, GraphicsStateItem): data['states'].append(item.get_data())
            elif isinstance(item, GraphicsTransitionItem):
                if item.start_item and item.end_item: data['transitions'].append(item.get_data())
                else: self.log_function(f"Warning: Skipping save of orphaned/invalid transition: '{item._compose_label_string()}'.", type_hint="GENERAL")
            elif isinstance(item, GraphicsCommentItem): data['comments'].append(item.get_data())
        return data

    def load_diagram_data(self, data):
        self.clear(); self.set_dirty(False); state_items_map = {}
        for state_data in data.get('states', []):
            state_item = GraphicsStateItem(state_data['x'], state_data['y'], state_data.get('width', 120), state_data.get('height', 60), state_data['name'], state_data.get('is_initial', False), state_data.get('is_final', False), state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG), state_data.get('entry_action',""), state_data.get('during_action',""), state_data.get('exit_action',""), state_data.get('description',""))
            self.addItem(state_item); state_items_map[state_data['name']] = state_item
        for trans_data in data.get('transitions', []):
            src_item = state_items_map.get(trans_data['source']); tgt_item = state_items_map.get(trans_data['target'])
            if src_item and tgt_item:
                trans_item = GraphicsTransitionItem(src_item, tgt_item, event_str=trans_data.get('event',""), condition_str=trans_data.get('condition',""), action_str=trans_data.get('action',""), color=trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT), description=trans_data.get('description',""))
                trans_item.set_control_point_offset(QPointF(trans_data.get('control_offset_x',0), trans_data.get('control_offset_y',0)))
                self.addItem(trans_item)
            else: self.log_function(f"Warning (Load): Could not link transition '{trans_data.get('event','')}{trans_data.get('condition','')}{trans_data.get('action','')}' due to missing states: Source='{trans_data['source']}', Target='{trans_data['target']}'.", type_hint="GENERAL")
        for comment_data in data.get('comments', []):
            comment_item = GraphicsCommentItem(comment_data['x'], comment_data['y'], comment_data.get('text', ""))
            comment_item.setTextWidth(comment_data.get('width', 150)); self.addItem(comment_item)
        self.set_dirty(False); self.undo_stack.clear()

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
            if x % (self.grid_size * 5) != 0: painter.drawLine(x, top, x, bottom)
        for y in range(top, bottom, self.grid_size):
            if y % (self.grid_size * 5) != 0: painter.drawLine(left, y, right, y)
        major_grid_size = self.grid_size * 5
        first_major_left = left - (left % major_grid_size); first_major_top = top - (top % major_grid_size)
        painter.setPen(self.grid_pen_dark)
        for x in range(first_major_left, right, major_grid_size): painter.drawLine(x, top, x, bottom)
        for y in range(first_major_top, bottom, major_grid_size): painter.drawLine(left, y, right, y)

# --- Zoomable Graphics View ---
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

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file_path = None
        self.last_generated_model_path = None
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)
        self.ai_chatbot_manager = AIChatbotManager(self) # Moved up
        self.scene = DiagramScene(self.undo_stack, self)
        self.scene.set_log_function(self.log_message)
        self.scene.modifiedStatusChanged.connect(self.setWindowModified)
        self.scene.modifiedStatusChanged.connect(self._update_window_title)

        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False
        self._py_sim_currently_highlighted_item: GraphicsStateItem | None = None
        
        self._internet_connected: bool | None = None 
        self.internet_check_timer = QTimer(self) 
        
        self.init_ui() # init_ui calls _create_docks where AI chat UI is made

        self.status_label.setObjectName("StatusLabel")
        self.matlab_status_label.setObjectName("MatlabStatusLabel")
        self.py_sim_status_label.setObjectName("PySimStatusLabel")
        self.internet_status_label.setObjectName("InternetStatusLabel")
        # AI Chat UI elements are created in _create_ai_chatbot_dock
        # and their object names are set there for robustness.

        self._update_matlab_status_display(False, "Initializing. Configure MATLAB settings or attempt auto-detect.")
        self._update_py_sim_status_display()

        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)
        
        self._update_window_title()
        self.on_new_file(silent=True)

        self.scene.selectionChanged.connect(self._update_properties_dock)
        self._update_properties_dock()
        self._update_py_simulation_actions_enabled_state()
        
        self._init_internet_status_check() 

    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050)
        self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM"))
        self._create_central_widget()
        self._create_actions()      # Actions, including AI related
        self._create_menus()        # Menus, including AI Assistant menu
        self._create_toolbars()
        self._create_status_bar()   # Status bar labels
        self._create_docks()        # Docks, including AI chatbot dock
        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()
        self.select_mode_action.trigger()

    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self); self.view.setObjectName("MainDiagramView"); self.setCentralWidget(self.view)

    def _create_actions(self):
        self.openai_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "AISet"), "AI Assistant Settings...", self, triggered=self.on_openai_settings)
        self.clear_ai_chat_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "Clear"), "Clear Chat History", self, triggered=self.on_clear_ai_chat_history)
        
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
        self.exit_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", self, shortcut=QKeySequence.Quit, statusTip="Exit the application", triggered=self.close)
        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo"); self.undo_action.setShortcut(QKeySequence.Undo); self.undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "Un"))
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo"); self.redo_action.setShortcut(QKeySequence.Redo); self.redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "Re"))
        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_actions_enable_state); self.undo_stack.canRedoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.select_all_action = QAction(get_standard_icon(_safe_get_style_enum("SP_FileDialogListView", "SP_FileDialogDetailedView"), "All"), "Select &All", self, shortcut=QKeySequence.SelectAll, triggered=self.on_select_all)
        self.delete_action = QAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "&Delete", self, shortcut=QKeySequence.Delete, triggered=self.on_delete_selected)
        self.mode_action_group = QActionGroup(self); self.mode_action_group.setExclusive(True)
        self.select_mode_action = QAction(QIcon.fromTheme("edit-select", get_standard_icon(QStyle.SP_ArrowRight, "Sel")), "Select/Move", self, checkable=True, triggered=lambda: self.scene.set_mode("select")); self.select_mode_action.setObjectName("select_mode_action")
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", get_standard_icon(QStyle.SP_FileDialogNewFolder, "St")), "Add State", self, checkable=True, triggered=lambda: self.scene.set_mode("state")); self.add_state_mode_action.setObjectName("add_state_mode_action")
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", get_standard_icon(QStyle.SP_ArrowForward, "Tr")), "Add Transition", self, checkable=True, triggered=lambda: self.scene.set_mode("transition")); self.add_transition_mode_action.setObjectName("add_transition_mode_action")
        self.add_comment_mode_action = QAction(QIcon.fromTheme("insert-text", get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm")), "Add Comment", self, checkable=True, triggered=lambda: self.scene.set_mode("comment")); self.add_comment_mode_action.setObjectName("add_comment_mode_action")
        for action in [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action]: self.mode_action_group.addAction(action)
        self.select_mode_action.setChecked(True)
        self.export_simulink_action = QAction(get_standard_icon(_safe_get_style_enum("SP_ArrowUp","->M"), "->M"), "&Export to Simulink...", self, triggered=self.on_export_simulink)
        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation (MATLAB)...", self, triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"), "Generate &Code (C/C++ via MATLAB)...", self, triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"), "&MATLAB Settings...", self, triggered=self.on_matlab_settings)
        self.start_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Py▶"), "&Start Python Simulation", self, statusTip="Start internal FSM simulation", triggered=self.on_start_py_simulation)
        self.stop_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaStop, "Py■"), "S&top Python Simulation", self, statusTip="Stop internal FSM simulation", triggered=self.on_stop_py_simulation, enabled=False)
        self.reset_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaSkipBackward, "Py«"), "&Reset Python Simulation", self, statusTip="Reset internal FSM simulation to initial state", triggered=self.on_reset_py_simulation, enabled=False)
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, triggered=self.on_about)

    def _create_menus(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File"); file_menu.addAction(self.new_action); file_menu.addAction(self.open_action); file_menu.addAction(self.save_action); file_menu.addAction(self.save_as_action); file_menu.addSeparator(); file_menu.addAction(self.export_simulink_action); file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        edit_menu = menu_bar.addMenu("&Edit"); edit_menu.addAction(self.undo_action); edit_menu.addAction(self.redo_action); edit_menu.addSeparator(); edit_menu.addAction(self.delete_action); edit_menu.addAction(self.select_all_action); edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Mode"),"Interaction Mode"); mode_menu.addAction(self.select_mode_action); mode_menu.addAction(self.add_state_mode_action); mode_menu.addAction(self.add_transition_mode_action); mode_menu.addAction(self.add_comment_mode_action)
        sim_menu = menu_bar.addMenu("&Simulation")
        py_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_MediaPlay, "PyS"), "Python Simulation (Internal)"); py_sim_menu.addAction(self.start_py_sim_action); py_sim_menu.addAction(self.stop_py_sim_action); py_sim_menu.addAction(self.reset_py_sim_action)
        sim_menu.addSeparator()
        matlab_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_ComputerIcon, "M"), "MATLAB/Simulink"); matlab_sim_menu.addAction(self.run_simulation_action); matlab_sim_menu.addAction(self.generate_code_action); matlab_sim_menu.addSeparator(); matlab_sim_menu.addAction(self.matlab_settings_action)
        self.view_menu = menu_bar.addMenu("&View") # View menu is created first
        # AI Assistant Menu is created separately after _create_docks populates self.ai_chatbot_dock
        ai_menu = menu_bar.addMenu("&AI Assistant")
        ai_menu.addAction(self.clear_ai_chat_action) 
        ai_menu.addAction(self.openai_settings_action)
        help_menu = menu_bar.addMenu("&Help"); help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(22,22); tb_style = Qt.ToolButtonTextBesideIcon
        file_toolbar = self.addToolBar("File"); file_toolbar.setObjectName("FileToolBar"); file_toolbar.setIconSize(icon_size); file_toolbar.setToolButtonStyle(tb_style); file_toolbar.addAction(self.new_action); file_toolbar.addAction(self.open_action); file_toolbar.addAction(self.save_action)
        edit_toolbar = self.addToolBar("Edit"); edit_toolbar.setObjectName("EditToolBar"); edit_toolbar.setIconSize(icon_size); edit_toolbar.setToolButtonStyle(tb_style); edit_toolbar.addAction(self.undo_action); edit_toolbar.addAction(self.redo_action); edit_toolbar.addSeparator(); edit_toolbar.addAction(self.delete_action)
        tools_tb = self.addToolBar("Interaction Tools"); tools_tb.setObjectName("ToolsToolBar"); tools_tb.setIconSize(icon_size); tools_tb.setToolButtonStyle(tb_style); tools_tb.addAction(self.select_mode_action); tools_tb.addAction(self.add_state_mode_action); tools_tb.addAction(self.add_transition_mode_action); tools_tb.addAction(self.add_comment_mode_action)
        sim_toolbar = self.addToolBar("Simulation Tools"); sim_toolbar.setObjectName("SimulationToolBar"); sim_toolbar.setIconSize(icon_size); sim_toolbar.setToolButtonStyle(tb_style); sim_toolbar.addAction(self.start_py_sim_action); sim_toolbar.addAction(self.stop_py_sim_action); sim_toolbar.addAction(self.reset_py_sim_action); sim_toolbar.addSeparator(); sim_toolbar.addAction(self.export_simulink_action); sim_toolbar.addAction(self.run_simulation_action); sim_toolbar.addAction(self.generate_code_action)

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self); self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready"); self.status_bar.addWidget(self.status_label, 1)
        self.py_sim_status_label = QLabel("PySim: Idle"); self.py_sim_status_label.setToolTip("Internal Python FSM Simulation Status."); self.status_bar.addPermanentWidget(self.py_sim_status_label)
        self.matlab_status_label = QLabel("MATLAB: Initializing..."); self.matlab_status_label.setToolTip("MATLAB connection status."); self.status_bar.addPermanentWidget(self.matlab_status_label)
        self.internet_status_label = QLabel("Internet: Init..."); self.internet_status_label.setToolTip("Internet connectivity status. Checks periodically."); self.status_bar.addPermanentWidget(self.internet_status_label)
        self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0,0); self.progress_bar.setVisible(False); self.progress_bar.setMaximumWidth(150); self.progress_bar.setTextVisible(False); self.status_bar.addPermanentWidget(self.progress_bar)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)
        self.tools_dock = QDockWidget("Tools", self); self.tools_dock.setObjectName("ToolsDock"); self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_widget_main = QWidget(); tools_widget_main.setObjectName("ToolsDockWidgetContents"); tools_main_layout = QVBoxLayout(tools_widget_main); tools_main_layout.setSpacing(10); tools_main_layout.setContentsMargins(5,5,5,5)
        mode_group_box = QGroupBox("Interaction Modes"); mode_layout = QVBoxLayout(); mode_layout.setSpacing(5)
        self.toolbox_select_button = QToolButton(); self.toolbox_select_button.setDefaultAction(self.select_mode_action); self.toolbox_add_state_button = QToolButton(); self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action); self.toolbox_transition_button = QToolButton(); self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action); self.toolbox_add_comment_button = QToolButton(); self.toolbox_add_comment_button.setDefaultAction(self.add_comment_mode_action)
        for btn in [self.toolbox_select_button, self.toolbox_add_state_button, self.toolbox_transition_button, self.toolbox_add_comment_button]: btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(18,18)); mode_layout.addWidget(btn)
        mode_group_box.setLayout(mode_layout); tools_main_layout.addWidget(mode_group_box)
        draggable_group_box = QGroupBox("Drag New Elements"); draggable_layout = QVBoxLayout(); draggable_layout.setSpacing(5)
        drag_state_btn = DraggableToolButton(" State", "application/x-bsm-tool", "State"); drag_state_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St")); drag_initial_state_btn = DraggableToolButton(" Initial State", "application/x-bsm-tool", "Initial State"); drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt")); drag_final_state_btn = DraggableToolButton(" Final State", "application/x-bsm-tool", "Final State"); drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt")); drag_comment_btn = DraggableToolButton(" Comment", "application/x-bsm-tool", "Comment"); drag_comment_btn.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))
        for btn in [drag_state_btn, drag_initial_state_btn, drag_final_state_btn, drag_comment_btn]: btn.setIconSize(QSize(18,18)); draggable_layout.addWidget(btn)
        draggable_group_box.setLayout(draggable_layout); tools_main_layout.addWidget(draggable_group_box)
        tools_main_layout.addStretch(); self.tools_dock.setWidget(tools_widget_main); self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock); self.view_menu.addAction(self.tools_dock.toggleViewAction())
        self.log_dock = QDockWidget("Output Log", self); self.log_dock.setObjectName("LogDock"); self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea); self.log_output = QTextEdit(); self.log_output.setObjectName("LogOutputWidget"); self.log_output.setReadOnly(True); self.log_dock.setWidget(self.log_output); self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock); self.view_menu.addAction(self.log_dock.toggleViewAction())
        self.properties_dock = QDockWidget("Element Properties", self); self.properties_dock.setObjectName("PropertiesDock"); self.properties_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea); properties_widget_main = QWidget(); properties_widget_main.setObjectName("PropertiesDockWidgetContents"); self.properties_layout = QVBoxLayout(properties_widget_main); self.properties_layout.setSpacing(8); self.properties_layout.setContentsMargins(5,5,5,5); self.properties_editor_label = QLabel("<i>No item selected.</i>"); self.properties_editor_label.setAlignment(Qt.AlignTop | Qt.AlignLeft); self.properties_editor_label.setWordWrap(True); self.properties_editor_label.setTextInteractionFlags(Qt.TextSelectableByMouse); self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton,"Edt"), " Edit Details..."); self.properties_edit_button.setEnabled(False); self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock); self.properties_edit_button.setIconSize(QSize(16,16)); self.properties_layout.addWidget(self.properties_editor_label, 1); self.properties_layout.addWidget(self.properties_edit_button); properties_widget_main.setLayout(self.properties_layout); self.properties_dock.setWidget(properties_widget_main); self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock); self.view_menu.addAction(self.properties_dock.toggleViewAction())
        self._create_py_simulation_dock()
        self._create_ai_chatbot_dock() # Create the AI chatbot dock

    def _create_py_simulation_dock(self):
        self.py_sim_dock = QDockWidget("Python FSM Simulation", self); self.py_sim_dock.setObjectName("PySimDock"); self.py_sim_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea); py_sim_widget = QWidget(); py_sim_main_layout = QVBoxLayout(py_sim_widget); py_sim_main_layout.setSpacing(8); py_sim_main_layout.setContentsMargins(5, 5, 5, 5)
        control_row1_layout = QHBoxLayout(); self.py_sim_start_btn = QToolButton(); self.py_sim_start_btn.setDefaultAction(self.start_py_sim_action); self.py_sim_stop_btn = QToolButton(); self.py_sim_stop_btn.setDefaultAction(self.stop_py_sim_action); self.py_sim_reset_btn = QToolButton(); self.py_sim_reset_btn.setDefaultAction(self.reset_py_sim_action)
        for btn in [self.py_sim_start_btn, self.py_sim_stop_btn, self.py_sim_reset_btn]: btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(18,18)); control_row1_layout.addWidget(btn)
        py_sim_main_layout.addLayout(control_row1_layout); control_row2_layout = QHBoxLayout(); self.py_sim_step_btn = QPushButton(get_standard_icon(QStyle.SP_MediaSeekForward, "Py→S"), " Step (Internal)"); self.py_sim_step_btn.clicked.connect(self.on_step_py_simulation); self.py_sim_step_btn.setIconSize(QSize(18,18)); control_row2_layout.addWidget(self.py_sim_step_btn); self.py_sim_event_name_edit = QLineEdit(); self.py_sim_event_name_edit.setPlaceholderText("Enter event name..."); self.py_sim_trigger_event_btn = QPushButton(get_standard_icon(QStyle.SP_ArrowForward, ">Ev"), " Trigger Event"); self.py_sim_trigger_event_btn.clicked.connect(self.on_trigger_py_event); self.py_sim_trigger_event_btn.setIconSize(QSize(18,18)); control_row2_layout.addWidget(self.py_sim_event_name_edit, 1); control_row2_layout.addWidget(self.py_sim_trigger_event_btn); py_sim_main_layout.addLayout(control_row2_layout)
        display_group = QGroupBox("Simulation Status"); display_layout = QFormLayout(display_group); display_layout.setSpacing(6); self.py_sim_current_state_label = QLabel("<i>Not Running</i>"); display_layout.addRow("Current State:", self.py_sim_current_state_label); self.py_sim_variables_table = QTableWidget(); self.py_sim_variables_table.setColumnCount(2); self.py_sim_variables_table.setHorizontalHeaderLabels(["Variable", "Value"]); self.py_sim_variables_table.horizontalHeader().setStretchLastSection(True); self.py_sim_variables_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive); self.py_sim_variables_table.verticalHeader().setVisible(False); self.py_sim_variables_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.py_sim_variables_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.py_sim_variables_table.setAlternatingRowColors(True); self.py_sim_variables_table.setFixedHeight(150); display_layout.addRow("FSM Variables:", self.py_sim_variables_table); py_sim_main_layout.addWidget(display_group)
        log_group = QGroupBox("Python Simulation Action Log"); log_layout = QVBoxLayout(log_group); log_layout.setContentsMargins(2,2,2,2); self.py_sim_action_log_output = QTextEdit(); self.py_sim_action_log_output.setObjectName("PySimActionLog"); self.py_sim_action_log_output.setReadOnly(True); self.py_sim_action_log_output.setMinimumHeight(100); log_layout.addWidget(self.py_sim_action_log_output); py_sim_main_layout.addWidget(log_group, 1)
        py_sim_widget.setLayout(py_sim_main_layout); self.py_sim_dock.setWidget(py_sim_widget); self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock); self.view_menu.addAction(self.py_sim_dock.toggleViewAction())

    def _create_ai_chatbot_dock(self): # INDENTED CORRECTLY
        self.ai_chatbot_dock = QDockWidget("AI Assistant", self)
        self.ai_chatbot_dock.setObjectName("AIChatbotDock")
        self.ai_chatbot_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)

        chatbot_widget_main = QWidget()
        chatbot_widget_main.setObjectName("AIChatbotDockWidgetContents")
        chatbot_main_layout = QVBoxLayout(chatbot_widget_main)
        chatbot_main_layout.setSpacing(6); chatbot_main_layout.setContentsMargins(5, 5, 5, 5)

        self.ai_chat_display = QTextEdit(); self.ai_chat_display.setObjectName("AIChatDisplay")
        self.ai_chat_display.setReadOnly(True)
        self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
        chatbot_main_layout.addWidget(self.ai_chat_display, 1) 

        input_layout = QHBoxLayout()
        self.ai_chat_input = QLineEdit(); self.ai_chat_input.setObjectName("AIChatInput")
        self.ai_chat_input.setPlaceholderText("Ask the AI assistant...")
        self.ai_chat_input.returnPressed.connect(self._on_send_ai_chat_message) 
        input_layout.addWidget(self.ai_chat_input, 1) 

        self.ai_chat_send_button = QPushButton(get_standard_icon(QStyle.SP_DialogYesButton, "Send"), "Send")
        self.ai_chat_send_button.setObjectName("AIChatSendButton")
        self.ai_chat_send_button.setIconSize(QSize(16,16))
        self.ai_chat_send_button.clicked.connect(self._on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_send_button)
        chatbot_main_layout.addLayout(input_layout)

        self.ai_chat_status_label = QLabel(); self.ai_chat_status_label.setObjectName("AIChatStatusLabel")
        self._update_ai_chat_status("Status: API Key required. Configure in Settings.")
        chatbot_main_layout.addWidget(self.ai_chat_status_label)

        chatbot_widget_main.setLayout(chatbot_main_layout)
        self.ai_chatbot_dock.setWidget(chatbot_widget_main)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock) 
        if hasattr(self, 'view_menu'):
             self.view_menu.addSeparator() 
             view_menu_action = self.ai_chatbot_dock.toggleViewAction()
             view_menu_action.setText("AI Assistant Panel") # Customize menu text
             self.view_menu.addAction(view_menu_action)
        else: print("Warning: view_menu not found for AI Chatbot dock toggle.")

    # ---- AI Chatbot Interaction Methods ----
    def _on_send_ai_chat_message(self):
        user_message = self.ai_chat_input.text().strip()
        if not user_message: return
        self._append_to_ai_chat_display("You", user_message)
        self.ai_chat_input.clear()
        self.ai_chatbot_manager.send_message(user_message) 

    def _handle_ai_response(self, ai_message_text: str):
        self.log_message(f"AI Raw Response: {ai_message_text[:200]}...", type_hint="AI_DEBUG")
        self._append_to_ai_chat_display("AI Assistant", ai_message_text)
        self._update_ai_chat_status("Status: Ready.") # Ensure status updates on response
        self.ai_chat_input.setFocus()
        
        # Try to parse as JSON, especially if a generation was expected
        try:
            # A simple heuristic: if it starts with { and ends with }, assume JSON.
            # A more robust check might be needed, or a flag from ChatbotWorker.
            potential_json = ai_message_text.strip()
            if potential_json.startswith("{") and potential_json.endswith("}"):
                fsm_data = json.loads(potential_json)
                if "states" in fsm_data and "transitions" in fsm_data: # Basic check for FSM structure
                    self.log_message("AI response appears to be FSM JSON data. Attempting to generate diagram.", type_hint="AI_ACTION")
                    # Ask user before clearing/adding (optional but good UX)
                    reply = QMessageBox.question(self, "Generate FSM from AI?",
                                                 "The AI provided FSM data. Do you want to add it to the current diagram? (This may clear existing elements if you choose to 'Clear and Add')",
                                                 QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                                                 QMessageBox.Yes)
                    if reply == QMessageBox.Yes:
                        self._add_fsm_data_to_scene(fsm_data, clear_current_diagram=False) # Append by default
                    elif reply == QMessageBox.No : # Some older Qt versions might return No if Yes/No/Cancel is presented
                        # If you add a "Clear and Add" option in QMessageBox
                        # self._add_fsm_data_to_scene(fsm_data, clear_current_diagram=True) 
                        pass # User chose not to add
                    else: # Cancel
                        self._update_ai_chat_status("Status: FSM generation cancelled by user.")
                        self.ai_chat_input.setFocus()
                        return
                    
                    self._append_to_ai_chat_display("AI Assistant", fsm_data.get("description", "Generated FSM elements.") + " (See diagram)")
                    self._update_ai_chat_status("Status: FSM elements added.")
                else: # Parsed as JSON, but not the FSM structure we expect for generation
                    self._append_to_ai_chat_display("AI Assistant", ai_message_text)
                    self._update_ai_chat_status("Status: Ready.")
            else: # Not JSON, treat as regular chat
                self._append_to_ai_chat_display("AI Assistant", ai_message_text)
                self._update_ai_chat_status("Status: Ready.")

        except json.JSONDecodeError:
            # Not valid JSON, treat as a regular text response
            self._append_to_ai_chat_display("AI Assistant", ai_message_text)
            self._update_ai_chat_status("Status: Ready.")
        except Exception as e:
            self.log_message(f"Error processing AI response for FSM generation: {e}", type_hint="AIChatError")
            self._append_to_ai_chat_display("System Error", f"Could not process FSM data: {e}")
            self._update_ai_chat_status("Status: Error processing FSM data.")

        self.ai_chat_input.setFocus()
        
    def _add_fsm_data_to_scene(self, fsm_data: dict, clear_current_diagram: bool = False):
        """
        Adds states and transitions from AI-generated data to the scene.
        'fsm_data' should have 'states' and 'transitions' keys.
        """
        if clear_current_diagram:
            self.scene.clear() # Consider an undo command for this
            self.undo_stack.clear() # Or provide a more granular clear that is undoable
            self.log_message("Cleared diagram before AI generation.", type_hint="AI_ACTION")

        state_items_map = {} # To link transitions by name

        # Add States
        # Basic auto-layout: position in a grid or line for now
        start_x, start_y = 100, 100
        current_x, current_y = start_x, start_y
        items_per_row = 3
        item_width, item_height = 120, 60 # Default state size
        padding_x, padding_y = 150, 100

        for i, state_data in enumerate(fsm_data.get('states', [])):
            name = state_data.get('name')
            if not name:
                self.log_message(f"AI Gen Warning: State data missing 'name'. Skipping: {state_data}", type_hint="AIChatError")
                continue
            
            # Auto-positioning (very basic grid)
            pos_x = current_x + (i % items_per_row) * (item_width + padding_x)
            pos_y = current_y + (i // items_per_row) * (item_height + padding_y)

            # Default properties that GraphicsStateItem expects
            props = {
                'x': pos_x, 'y': pos_y, 'width': item_width, 'height': item_height,
                'name': name,
                'is_initial': state_data.get('is_initial', False),
                'is_final': state_data.get('is_final', False),
                'color': state_data.get('properties', {}).get('color', COLOR_ITEM_STATE_DEFAULT_BG), # Get from properties or default
                'entry_action': state_data.get('entry_action', ""),
                'during_action': state_data.get('during_action', ""),
                'exit_action': state_data.get('exit_action', ""),
                'description': state_data.get('description', "")
            }
            
            state_item = GraphicsStateItem(**props) # Use dictionary unpacking
            
            # Add via undo command
            add_cmd = AddItemCommand(self.scene, state_item, f"Add AI State: {name}")
            self.undo_stack.push(add_cmd)
            state_items_map[name] = state_item
            self.log_message(f"AI Generated State: {name}", type_hint="AI_ACTION")

        # Add Transitions
        for trans_data in fsm_data.get('transitions', []):
            source_name = trans_data.get('source')
            target_name = trans_data.get('target')

            if not source_name or not target_name:
                self.log_message(f"AI Gen Warning: Transition missing source/target. Skipping: {trans_data}", type_hint="AIChatError")
                continue

            source_item = state_items_map.get(source_name)
            target_item = state_items_map.get(target_name)

            if source_item and target_item:
                trans_props = {
                    'event_str': trans_data.get('event', ""),
                    'condition_str': trans_data.get('condition', ""),
                    'action_str': trans_data.get('action', ""),
                    'color': trans_data.get('properties', {}).get('color', COLOR_ITEM_TRANSITION_DEFAULT),
                    'description': trans_data.get('description', "")
                }
                # Control point offsets can be added if AI provides them, or default
                # 'control_offset_x': trans_data.get('control_offset_x', 0),
                # 'control_offset_y': trans_data.get('control_offset_y', 0),

                trans_item = GraphicsTransitionItem(source_item, target_item, **trans_props)
                
                add_cmd = AddItemCommand(self.scene, trans_item, f"Add AI Transition: {source_name}->{target_name}")
                self.undo_stack.push(add_cmd)
                self.log_message(f"AI Generated Transition: {source_name} -> {target_name}", type_hint="AI_ACTION")

            else:
                self.log_message(f"AI Gen Warning: Could not find source ('{source_name}') or target ('{target_name}') state for transition. Skipping.", type_hint="AIChatError")
        
        # Add Comments (Optional)
        current_x = start_x # Reset for comments, or position relative to FSM bounds
        current_y += ((len(fsm_data.get('states', [])) // items_per_row) + 1) * (item_height + padding_y) # Below states
        
        for i, comment_data in enumerate(fsm_data.get('comments', [])):
            text = comment_data.get('text')
            if not text: continue
            
            # Basic positioning for comments
            comment_x = comment_data.get('x', current_x + i * 160) 
            comment_y = comment_data.get('y', current_y)

            comment_item = GraphicsCommentItem(comment_x, comment_y, text)
            # comment_item.setTextWidth(...) if AI provides width

            add_cmd = AddItemCommand(self.scene, comment_item, f"Add AI Comment")
            self.undo_stack.push(add_cmd)
            self.log_message(f"AI Generated Comment: {text[:30]}...", type_hint="AI_ACTION")

        self.scene.set_dirty(True)
        self.view.centerOn(self.scene.itemsBoundingRect().center()) # Center view    
        
        
        
        
        
        
        

    def _handle_ai_error(self, error_message: str):
        self._append_to_ai_chat_display("System Error", error_message)
        self.log_message(f"AI Chatbot Error: {error_message}", type_hint="AIChatError") 
        short_error = error_message.split('\n')[0].split(':')[0] # More concise error for status
        self._update_ai_chat_status(f"Error: {short_error}") 
        self.ai_chat_input.setFocus()

    def _update_ai_chat_status(self, status_text: str):
        if hasattr(self, 'ai_chat_status_label'):
            self.ai_chat_status_label.setText(status_text)
            if "error" in status_text.lower() or "failed" in status_text.lower() or "required" in status_text.lower():
                self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: red;")
                self.ai_chat_send_button.setEnabled(False) # Often disable send on error or key needed
                self.ai_chat_input.setEnabled(False)
            elif "thinking..." in status_text.lower() or "sending..." in status_text.lower():
                 self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;")
                 self.ai_chat_send_button.setEnabled(False)
                 self.ai_chat_input.setEnabled(False)
            else: # Ready, cleared etc.
                 self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;")
                 self.ai_chat_send_button.setEnabled(True)
                 self.ai_chat_input.setEnabled(True)
                 
    def _append_to_ai_chat_display(self, sender: str, message: str):
        timestamp = QTime.currentTime().toString('hh:mm') 
        sender_color_hex_str = COLOR_ACCENT_PRIMARY # Default for AI
        if sender == "You": sender_color_hex_str = COLOR_ACCENT_SECONDARY
        elif sender == "System Error": sender_color_hex_str = "#D32F2F"
            
        formatted_message = (
            f"<div style='margin-bottom: 5px;'>"
            f"<span style='font-size:8pt; color:grey;'>[{timestamp}]</span> "
            f"<strong style='color:{sender_color_hex_str};'>{html.escape(sender)}:</strong> "
            f"{html.escape(message).replace(r'\n', '<br>')}"
            f"</div>"
        )
        self.ai_chat_display.append(formatted_message); self.ai_chat_display.ensureCursorVisible()

    def on_openai_settings(self):
        current_key = self.ai_chatbot_manager.api_key if self.ai_chatbot_manager.api_key else ""
        key, ok = QInputDialog.getText(self, "OpenAI API Key", "Enter your OpenAI API Key (leave blank to clear):", QLineEdit.PasswordEchoOnEdit, current_key)
        if ok:
            new_key = key.strip()
            self.ai_chatbot_manager.set_api_key(new_key if new_key else None)
            if new_key:
                self.log_message("OpenAI API Key set/updated.", type_hint="AI_CONFIG")
                self._update_ai_chat_status("Status: Ready. API Key set.")
            else:
                self.log_message("OpenAI API Key cleared.", type_hint="AI_CONFIG")
                self._update_ai_chat_status("Status: API Key required.")

    def on_clear_ai_chat_history(self):
        if self.ai_chatbot_manager:
            self.ai_chatbot_manager.clear_conversation_history()
            # Status update is handled by manager if clear_history emits statusUpdate,
            # otherwise, call _update_ai_chat_status here. Let's assume manager does.
            
    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems(); html_content = ""; edit_enabled = False; item_type_for_tooltip = "item"
        if len(selected_items) == 1:
            item = selected_items[0]; props = item.get_data(); item_type_name = type(item).__name__.replace("Graphics", "").replace("Item", ""); item_type_for_tooltip = item_type_name.lower(); edit_enabled = True
            def format_prop_text(text_content, max_chars=25):
                if not text_content: return "<i>(none)</i>"; escaped = html.escape(text_content); first_line = escaped.split('\n')[0]
                return first_line[:max_chars] + "&hellip;" if len(first_line) > max_chars or '\n' in escaped else first_line
            rows_html = ""
            if isinstance(item, GraphicsStateItem):
                color_val = props.get('color', COLOR_ITEM_STATE_DEFAULT_BG); color_obj = QColor(color_val); text_on_color = 'black' if color_obj.lightnessF() > 0.5 else 'white'; color_style = f"background-color:{color_val}; color:{text_on_color}; padding: 1px 4px; border-radius:2px;"
                rows_html += f"<tr><td><b>Name:</b></td><td>{html.escape(props['name'])}</td></tr>"
                rows_html += f"<tr><td><b>Initial:</b></td><td>{'Yes' if props['is_initial'] else 'No'}</td></tr><tr><td><b>Final:</b></td><td>{'Yes' if props['is_final'] else 'No'}</td></tr>"
                rows_html += f"<tr><td><b>Color:</b></td><td><span style='{color_style}'>{html.escape(props.get('color','N/A'))}</span></td></tr>"
                rows_html += f"<tr><td><b>Entry:</b></td><td>{format_prop_text(props.get('entry_action'))}</td></tr><tr><td><b>During:</b></td><td>{format_prop_text(props.get('during_action'))}</td></tr><tr><td><b>Exit:</b></td><td>{format_prop_text(props.get('exit_action'))}</td></tr>"
                if props.get('description'): rows_html += f"<tr><td colspan='2'><b>Desc:</b> {format_prop_text(props.get('description'), 50)}</td></tr>"
            elif isinstance(item, GraphicsTransitionItem):
                color_val = props.get('color', COLOR_ITEM_TRANSITION_DEFAULT); color_obj = QColor(color_val); text_on_color = 'black' if color_obj.lightnessF() > 0.5 else 'white'; color_style = f"background-color:{color_val}; color:{text_on_color}; padding: 1px 4px; border-radius:2px;"
                label_parts = [p for p in [html.escape(props['event']) if props.get('event') else '', f"[{html.escape(props['condition'])}]" if props.get('condition') else '', f"/{{{format_prop_text(props['action'],15)}}}" if props.get('action') else ''] if p]; full_label = " ".join(label_parts) if label_parts else "<i>(No Label)</i>"
                rows_html += f"<tr><td><b>Label:</b></td><td style='font-size:8pt;'>{full_label}</td></tr><tr><td><b>From:</b></td><td>{html.escape(props['source'])}</td></tr><tr><td><b>To:</b></td><td>{html.escape(props['target'])}</td></tr>"
                rows_html += f"<tr><td><b>Color:</b></td><td><span style='{color_style}'>{html.escape(props.get('color','N/A'))}</span></td></tr>"
                rows_html += f"<tr><td><b>Curve:</b></td><td>Bend={props.get('control_offset_x',0):.0f}, Shift={props.get('control_offset_y',0):.0f}</td></tr>"
                if props.get('description'): rows_html += f"<tr><td colspan='2'><b>Desc:</b> {format_prop_text(props.get('description'), 50)}</td></tr>"
            elif isinstance(item, GraphicsCommentItem): rows_html += f"<tr><td colspan='2'><b>Text:</b> {format_prop_text(props['text'], 60)}</td></tr>"
            else: rows_html = "<tr><td>Unknown Item Type</td></tr>"
            html_content = f"""<div style='font-family: "Segoe UI, Arial, sans-serif", sans-serif; font-size: 9pt; line-height: 1.5;'><h4 style='margin:0 0 5px 0; padding:2px 0; color: {COLOR_ACCENT_PRIMARY}; border-bottom: 1px solid {COLOR_BORDER_LIGHT};'>Type: {item_type_name}</h4><table style='width: 100%; border-collapse: collapse;'>{rows_html}</table></div>"""
        elif len(selected_items) > 1: html_content = f"<i><b>{len(selected_items)} items selected.</b><br>Select a single item to view/edit its properties.</i>"; item_type_for_tooltip = f"{len(selected_items)} items"
        else: html_content = "<i>No item selected.</i><br><small>Click an item in the diagram or use tools to add new items.</small>"
        self.properties_editor_label.setText(html_content); self.properties_edit_button.setEnabled(edit_enabled); self.properties_edit_button.setToolTip(f"Edit detailed properties of the selected {item_type_for_tooltip}" if edit_enabled else "Select a single item to enable editing")

    def _on_edit_selected_item_properties_from_dock(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1: self.scene.edit_item_properties(selected_items[0])

    def log_message(self, message: str, type_hint: str = "GENERAL"):
        timestamp = QTime.currentTime().toString('hh:mm:ss.zzz')
        display_message = html.escape(message)
        formatted_log_entry = f"<span style='color:{COLOR_TEXT_SECONDARY};'>[{timestamp}]</span> "
        if type_hint == "NETWATCH": formatted_log_entry += f"<span style='color:grey;'><i>(NetCheck)</i> {display_message}</span>"
        elif type_hint == "MATLAB_CONN": formatted_log_entry += f"<span style='color:{COLOR_TEXT_SECONDARY};'><i>(MATLAB)</i> {display_message}</span>"
        elif type_hint == "PYSIM_STATUS_UPDATE": formatted_log_entry += f"<span style='color:{COLOR_ACCENT_PRIMARY};'><i>(PySim)</i> {display_message}</span>"
        elif type_hint == "AI_CONFIG": formatted_log_entry += f"<span style='color:blue;'><i>(AI Cfg)</i> {display_message}</span>" # Example
        elif type_hint == "AIChatError": formatted_log_entry += f"<span style='color:red;'><i>(AI Err)</i> {display_message}</span>" # Example
        else: formatted_log_entry += display_message
        self.log_output.append(formatted_log_entry)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
        if type_hint not in ["NETWATCH", "MATLAB_CONN", "AI_CONFIG", "AIChatError"] and "worker:" not in message : 
            self.status_label.setText(message.split('\n')[0][:120])

    def _update_window_title(self):
        title = APP_NAME; file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        title += f" - {file_name}";
        if self.py_sim_active: title += " [PySim Running]"
        title += "[*]"; self.setWindowTitle(title)

    def _update_save_actions_enable_state(self): self.save_action.setEnabled(self.isWindowModified())
    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo()); self.redo_action.setEnabled(self.undo_stack.canRedo())
        self.undo_action.setText(f"&Undo {self.undo_stack.undoText()}" if self.undo_stack.canUndo() else "&Undo")
        self.redo_action.setText(f"&Redo {self.undo_stack.redoText()}" if self.undo_stack.canRedo() else "&Redo")

    def _update_matlab_status_display(self, connected, message):
        text = f"MATLAB: {'Connected' if connected else 'Not Connected'}"; tooltip = f"MATLAB Status: {message}"
        self.matlab_status_label.setText(text); self.matlab_status_label.setToolTip(tooltip)
        # Assuming COLOR_PY_SIM_STATE_ACTIVE is a hex string for HTML-like style sheets
        style_sheet = f"font-weight: bold; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE if connected else '#C62828'};"
        self.matlab_status_label.setStyleSheet(style_sheet)
        if "Initializing" not in message: self.log_message(f"MATLAB Conn: {message}", type_hint="MATLAB_CONN")
        self._update_matlab_actions_enabled_state()

    def _update_matlab_actions_enabled_state(self):
        can_run_matlab = self.matlab_connection.connected and not self.py_sim_active
        for action in [self.export_simulink_action, self.run_simulation_action, self.generate_code_action]: action.setEnabled(can_run_matlab)
        self.matlab_settings_action.setEnabled(not self.py_sim_active)

    def _start_matlab_operation(self, operation_name):
        self.log_message(f"MATLAB Operation: {operation_name} starting...", type_hint="MATLAB_CONN")
        self.status_label.setText(f"Running: {operation_name}..."); self.progress_bar.setVisible(True); self.set_ui_enabled_for_matlab_op(False)
    def _finish_matlab_operation(self):
        self.progress_bar.setVisible(False); self.status_label.setText("Ready"); self.set_ui_enabled_for_matlab_op(True)
        self.log_message("MATLAB Operation: Finished processing.", type_hint="MATLAB_CONN")
    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        self.menuBar().setEnabled(enabled)
        for child in self.findChildren(QToolBar): child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock"]: # Added AIChatbotDock
            dock = self.findChild(QDockWidget, dock_name); 
            if dock: dock.setEnabled(enabled)
        self._update_py_simulation_actions_enabled_state()

    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation(); self.log_message(f"MATLAB Result ({('Success' if success else 'Failure')}): {message}", type_hint="MATLAB_CONN")
        if success:
            if "Model generation" in message and data: self.last_generated_model_path = data; QMessageBox.information(self, "Simulink Model Generation", f"Simulink model generated successfully:\n{data}")
            elif "Simulation" in message: QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else: QMessageBox.warning(self, "MATLAB Operation Failed", message)

    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation(); self.log_message(f"MATLAB Code Gen Result ({('Success' if success else 'Failure')}): {message}", type_hint="MATLAB_CONN")
        if success and output_dir:
            msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Information); msg_box.setWindowTitle("Code Generation Successful"); msg_box.setTextFormat(Qt.RichText); msg_box.setText(f"Code generation completed.<br>Output directory: <a href='file:///{os.path.abspath(output_dir)}'>{os.path.abspath(output_dir)}</a>"); msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction)
            open_dir_button = msg_box.addButton("Open Directory", QMessageBox.ActionRole); msg_box.addButton(QMessageBox.Ok); msg_box.exec_()
            if msg_box.clickedButton() == open_dir_button:
                try: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(output_dir)))
                except Exception as e: self.log_message(f"Error opening directory {output_dir}: {e}", type_hint="GENERAL"); QMessageBox.warning(self, "Error Opening Directory", f"Could not open directory:\n{e}")
        elif not success: QMessageBox.warning(self, "Code Generation Failed", message)

    def _prompt_save_if_dirty(self) -> bool:
        if not self.isWindowModified(): return True
        if self.py_sim_active: QMessageBox.warning(self, "Simulation Active", "Please stop the Python FSM simulation before saving or opening a new file."); return False
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes?", f"The document '{file_name}' has unsaved changes.\nDo you want to save them before continuing?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if reply == QMessageBox.Save: return self.on_save_file()
        return reply != QMessageBox.Cancel

    def on_new_file(self, silent=False):
        if not silent and not self._prompt_save_if_dirty(): return False
        self.on_stop_py_simulation(silent=True); self.scene.clear(); self.scene.setSceneRect(0,0,6000,4500)
        self.current_file_path = None; self.last_generated_model_path = None; self.undo_stack.clear(); self.scene.set_dirty(False)
        self._update_window_title(); self._update_undo_redo_actions_enable_state()
        if not silent: self.log_message("New diagram created. Ready.", type_hint="GENERAL")
        self.view.resetTransform(); self.view.centerOn(self.scene.sceneRect().center()); self.select_mode_action.trigger()
        return True

    def on_open_file(self):
        if not self._prompt_save_if_dirty(): return
        self.on_stop_py_simulation(silent=True)
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)
        if file_path:
            self.log_message(f"Attempting to open file: {file_path}", type_hint="GENERAL")
            if self._load_from_path(file_path):
                self.current_file_path = file_path; self.last_generated_model_path = None; self.undo_stack.clear(); self.scene.set_dirty(False)
                self._update_window_title(); self._update_undo_redo_actions_enable_state(); self.log_message(f"Successfully opened: {file_path}", type_hint="GENERAL")
                items_bounds = self.scene.itemsBoundingRect()
                if not items_bounds.isEmpty(): self.view.fitInView(items_bounds.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)
                else: self.view.resetTransform(); self.view.centerOn(self.scene.sceneRect().center())
            else: QMessageBox.critical(self, "Error Opening File", f"Could not load or parse file: {file_path}"); self.log_message(f"Failed to open file: {file_path}", type_hint="GENERAL")

    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
            if not isinstance(data, dict) or ('states' not in data or 'transitions' not in data): self.log_message(f"Error: Invalid BSM file format in {file_path}.", type_hint="GENERAL"); return False
            self.scene.load_diagram_data(data); return True
        except Exception as e: self.log_message(f"Error loading file {file_path}: {type(e).__name__}: {str(e)}", type_hint="GENERAL"); return False

    def on_save_file(self) -> bool: return self._save_to_path(self.current_file_path) if self.current_file_path else self.on_save_file_as()
    def on_save_file_as(self) -> bool:
        start_path = self.current_file_path if self.current_file_path else os.path.join(QDir.homePath(), "untitled" + FILE_EXTENSION)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As", start_path, FILE_FILTER)
        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION): file_path += FILE_EXTENSION
            if self._save_to_path(file_path): self.current_file_path = file_path; self.scene.set_dirty(False); self._update_window_title(); return True
        return False
    def _save_to_path(self, file_path) -> bool:
        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            error_str = save_file.errorString(); self.log_message(f"Error opening save file {file_path}: {error_str}", type_hint="GENERAL"); QMessageBox.critical(self, "Save Error", f"Failed to open file for saving:\n{error_str}"); return False
        try:
            data = self.scene.get_diagram_data(); json_data = json.dumps(data, indent=4, ensure_ascii=False)
            if save_file.write(json_data.encode('utf-8')) == -1: error_str = save_file.errorString(); self.log_message(f"Error writing data to {file_path}: {error_str}", type_hint="GENERAL"); QMessageBox.critical(self, "Save Error", f"Failed to write data to file:\n{error_str}"); save_file.cancelWriting(); return False
            if not save_file.commit(): error_str = save_file.errorString(); self.log_message(f"Error committing save to {file_path}: {error_str}", type_hint="GENERAL"); QMessageBox.critical(self, "Save Error", f"Failed to commit saved file:\n{error_str}"); return False
            self.log_message(f"File saved successfully: {file_path}", type_hint="GENERAL"); self.scene.set_dirty(False); return True
        except Exception as e: self.log_message(f"Error saving file {file_path}: {type(e).__name__}: {str(e)}", type_hint="GENERAL"); QMessageBox.critical(self, "Save Error", f"An error occurred during saving:\n{str(e)}"); save_file.cancelWriting(); return False

    def on_select_all(self): self.scene.select_all()
    def on_delete_selected(self): self.scene.delete_selected_items()
    def on_export_simulink(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected. Configure in Simulation menu."); return
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
            diagram_data = self.scene.get_diagram_data()
            if not diagram_data['states']: QMessageBox.information(self, "Empty Diagram", "Cannot export: the diagram contains no states."); return
            self._start_matlab_operation(f"Exporting '{model_name}' to Simulink"); self.matlab_connection.generate_simulink_model(diagram_data['states'], diagram_data['transitions'], output_dir, model_name)

    def on_run_simulation(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected."); return
        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model to Simulate", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return
        self.last_generated_model_path = model_path
        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Simulation stop time (seconds):", 10.0, 0.001, 86400.0, 3)
        if not ok: return
        self._start_matlab_operation(f"Running Simulink simulation for '{os.path.basename(model_path)}'"); self.matlab_connection.run_simulation(model_path, sim_time)

    def on_generate_code(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected."); return
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
    def on_about(self): QMessageBox.about(self, "About " + APP_NAME, f"<h3 style='color:{COLOR_ACCENT_PRIMARY};'>{APP_NAME} v{APP_VERSION}</h3><p>A graphical tool... (content as before) ...</p><p style='font-size:8pt; color:{COLOR_TEXT_SECONDARY};'>This tool is intended for research and educational purposes.</p>")

    def closeEvent(self, event: QCloseEvent):
        self.on_stop_py_simulation(silent=True)
        timer_was_active = self.internet_check_timer and self.internet_check_timer.isActive()
        if timer_was_active: self.internet_check_timer.stop()
        if self.ai_chatbot_manager: self.ai_chatbot_manager.stop_chatbot() # Stop chatbot thread
        if self._prompt_save_if_dirty():
            if self.matlab_connection._active_threads: self.log_message(f"Closing. {len(self.matlab_connection._active_threads)} MATLAB processes may persist.", type_hint="GENERAL")
            event.accept()
        else: 
            event.ignore(); 
            if timer_was_active and not event.isAccepted(): self.internet_check_timer.start()

    def _init_internet_status_check(self):
        self.internet_check_timer.timeout.connect(self._run_internet_check_job)
        self.internet_check_timer.start(15000) 
        QTimer.singleShot(100, self._run_internet_check_job) 

    def _run_internet_check_job(self):
        host_to_check = "8.8.8.8"; port_to_check = 53; connection_timeout = 1.5
        current_status = False; status_message_detail = "Checking..."
        try:
            s = socket.create_connection((host_to_check, port_to_check), timeout=connection_timeout); s.close()
            current_status = True; status_message_detail = "Connected"
        except socket.timeout: status_message_detail = "Disconnected (Timeout)"
        except socket.gaierror as e: status_message_detail = "Disconnected (DNS/Net Issue)"; self.log_message(f"NetCheck gaierror: {e}", type_hint="NETWATCH")
        except OSError as e: status_message_detail = "Disconnected (Net Error)"; self.log_message(f"NetCheck OSError: {e.strerror} (errno {e.errno})", type_hint="NETWATCH")
        if current_status != self._internet_connected or self._internet_connected is None:
            self._internet_connected = current_status
            self._update_internet_status_display(current_status, status_message_detail)

    def _update_internet_status_display(self, is_connected: bool, message_detail: str):
        full_status_text = f"Internet: {message_detail}"; self.internet_status_label.setText(full_status_text)
        try: check_host_name_for_tooltip = socket.getfqdn('8.8.8.8')
        except Exception: check_host_name_for_tooltip = '8.8.8.8' 
        self.internet_status_label.setToolTip(f"{full_status_text} (Checks {check_host_name_for_tooltip}:{53})")
        # Assuming COLOR_PY_SIM_STATE_ACTIVE is a hex string
        style_sheet = f"font-weight: normal; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE if is_connected else '#D32F2F'};"
        self.internet_status_label.setStyleSheet(style_sheet)
        self.log_message(f"Internet Status: {message_detail}", type_hint="NETWATCH") 

    def _update_py_sim_status_display(self):
        if self.py_sim_active and self.py_fsm_engine:
            state_name = self.py_fsm_engine.get_current_state_name()
            self.py_sim_status_label.setText(f"PySim: Active ({state_name})")
            self.py_sim_status_label.setStyleSheet(f"font-weight: bold; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE};") # Assumed hex string
        else:
            self.py_sim_status_label.setText("PySim: Idle"); self.py_sim_status_label.setStyleSheet("font-weight: normal; padding: 0px 5px;")

    def _update_py_simulation_actions_enabled_state(self):
        is_matlab_op_running = self.progress_bar.isVisible(); sim_inactive = not self.py_sim_active
        self.start_py_sim_action.setEnabled(sim_inactive and not is_matlab_op_running); self.py_sim_start_btn.setEnabled(sim_inactive and not is_matlab_op_running)
        for widget in [self.stop_py_sim_action, self.reset_py_sim_action, self.py_sim_stop_btn, self.py_sim_reset_btn, self.py_sim_step_btn, self.py_sim_event_name_edit, self.py_sim_trigger_event_btn]:
            widget.setEnabled(self.py_sim_active and not is_matlab_op_running)

    def set_ui_enabled_for_py_sim(self, is_sim_running: bool):
        self.py_sim_active = is_sim_running; self._update_window_title(); is_editable = not is_sim_running
        if is_editable and self.scene.current_mode != "select": self.scene.set_mode("select")
        elif not is_editable: self.scene.set_mode("select") 
        for item in self.scene.items():
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): item.setFlag(QGraphicsItem.ItemIsMovable, is_editable)
        actions_to_toggle = [self.new_action, self.open_action, self.save_action, self.save_as_action, self.undo_action, self.redo_action, self.delete_action, self.select_all_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action]
        for action in actions_to_toggle: action.setEnabled(is_editable)
        self.tools_dock.setEnabled(is_editable)
        self.properties_edit_button.setEnabled(is_editable and len(self.scene.selectedItems())==1)
        self._update_matlab_actions_enabled_state(); self._update_py_simulation_actions_enabled_state(); self._update_py_sim_status_display()

    def _highlight_sim_active_state(self, state_name_to_highlight: str | None):
        if self._py_sim_currently_highlighted_item: self._py_sim_currently_highlighted_item.set_py_sim_active_style(False); self._py_sim_currently_highlighted_item = None
        if state_name_to_highlight:
            for item in self.scene.items():
                if isinstance(item, GraphicsStateItem) and item.text_label == state_name_to_highlight: item.set_py_sim_active_style(True); self._py_sim_currently_highlighted_item = item; break
        self.scene.update()

    def _update_py_simulation_dock_ui(self):
        if not self.py_fsm_engine or not self.py_sim_active:
            self.py_sim_current_state_label.setText("<i>Not Running</i>"); self.py_sim_variables_table.setRowCount(0); self._highlight_sim_active_state(None); return
        current_state = self.py_fsm_engine.get_current_state_name(); self.py_sim_current_state_label.setText(f"<b>{html.escape(current_state or 'N/A')}</b>"); self._highlight_sim_active_state(current_state)
        variables = self.py_fsm_engine.get_variables(); self.py_sim_variables_table.setRowCount(len(variables))
        for row, (name, value) in enumerate(sorted(variables.items())):
            self.py_sim_variables_table.setItem(row, 0, QTableWidgetItem(str(name))); self.py_sim_variables_table.setItem(row, 1, QTableWidgetItem(str(value)))
        self.py_sim_variables_table.resizeColumnsToContents()

    def _append_to_py_simulation_log(self, log_entries: list[str]):
        for entry in log_entries:
            cleaned_entry = html.escape(entry) # Assuming COLOR_* are hex strings
            if "[Condition]" in entry or "[Eval Error]" in entry or "ERROR" in entry.upper(): cleaned_entry = f"<span style='color:{COLOR_ACCENT_SECONDARY};'>{cleaned_entry}</span>"
            elif "Transitioned from" in entry or "Reset to state" in entry or "Simulation started" in entry: cleaned_entry = f"<span style='color:{COLOR_ACCENT_PRIMARY}; font-weight:bold;'>{cleaned_entry}</span>"
            elif "No eligible transition" in entry: cleaned_entry = f"<span style='color:{COLOR_TEXT_SECONDARY};'>{cleaned_entry}</span>"
            self.py_sim_action_log_output.append(cleaned_entry)
        self.py_sim_action_log_output.verticalScrollBar().setValue(self.py_sim_action_log_output.verticalScrollBar().maximum())
        if log_entries:
            last_log_short = log_entries[-1].split('\n')[0][:100]
            important_keywords = ["Transitioned from", "No eligible transition", "ERROR", "Reset to state", "Simulation started", "Simulation stopped"]
            if any(keyword in last_log_short for keyword in important_keywords): self.log_message(f"PySim: {last_log_short}", type_hint="PYSIM_STATUS_UPDATE")

    def on_start_py_simulation(self):
        if self.py_sim_active: QMessageBox.information(self, "Simulation Active", "Python simulation is already running."); return
        if self.scene.is_dirty() and QMessageBox.question(self, "Unsaved Changes", "The diagram has unsaved changes that won't be reflected if you don't save.\nStart simulation with current in-memory state anyway?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.No: return
        diagram_data = self.scene.get_diagram_data()
        if not diagram_data.get('states'): QMessageBox.warning(self, "Empty Diagram", "Cannot start simulation: The diagram has no states."); return
        try:
            self.py_fsm_engine = FSMSimulator(diagram_data['states'], diagram_data['transitions']); self.set_ui_enabled_for_py_sim(True); self.py_sim_action_log_output.clear()
            initial_log = ["Python FSM Simulation started."] + self.py_fsm_engine.get_last_executed_actions_log() 
            self._append_to_py_simulation_log(initial_log); self._update_py_simulation_dock_ui()
        except Exception as e:
            msg = f"Failed to start Python FSM simulation:\n{e}"; QMessageBox.critical(self, "FSM Initialization Error", msg); self._append_to_py_simulation_log([f"ERROR Starting Sim: {msg}"])
            self.py_fsm_engine = None; self.set_ui_enabled_for_py_sim(False)

    def on_stop_py_simulation(self, silent=False):
        if not self.py_sim_active: return
        self.py_fsm_engine = None; self.set_ui_enabled_for_py_sim(False); self._update_py_simulation_dock_ui(); self._highlight_sim_active_state(None)
        if not silent: self._append_to_py_simulation_log(["Python FSM Simulation stopped."])

    def on_reset_py_simulation(self):
        if not self.py_fsm_engine or not self.py_sim_active: QMessageBox.warning(self, "Simulation Not Active", "Python simulation is not running. Start it first."); return
        try:
            self.py_fsm_engine.reset(); self.py_sim_action_log_output.append("<hr><i style='color:grey;'>Simulation Reset</i><hr>")
            reset_logs = self.py_fsm_engine.get_last_executed_actions_log() 
            self._append_to_py_simulation_log(reset_logs); self._update_py_simulation_dock_ui()
        except Exception as e: msg = f"Failed to reset Python FSM simulation:\n{e}"; QMessageBox.critical(self, "FSM Reset Error", msg); self._append_to_py_simulation_log([f"ERROR DURING RESET: {msg}"])

    def on_step_py_simulation(self):
        if not self.py_fsm_engine or not self.py_sim_active: QMessageBox.warning(self, "Simulation Not Active", "Python simulation is not running."); return
        try:
            _, log_entries = self.py_fsm_engine.step(event_name=None); self._append_to_py_simulation_log(log_entries); self._update_py_simulation_dock_ui()
        except Exception as e: msg = f"Simulation Step Error: {e}"; QMessageBox.warning(self, "Simulation Step Error", str(e)); self._append_to_py_simulation_log([f"ERROR DURING STEP: {msg}"])

    def on_trigger_py_event(self):
        if not self.py_fsm_engine or not self.py_sim_active: QMessageBox.warning(self, "Simulation Not Active", "Python simulation is not running."); return
        event_name = self.py_sim_event_name_edit.text().strip()
        if not event_name: self.on_step_py_simulation(); return 
        try:
            _, log_entries = self.py_fsm_engine.step(event_name=event_name); self._append_to_py_simulation_log(log_entries); self._update_py_simulation_dock_ui(); self.py_sim_event_name_edit.clear()
        except Exception as e: msg = f"Simulation Event Error ({html.escape(event_name)}): {e}"; QMessageBox.warning(self, "Simulation Event Error", str(e)); self._append_to_py_simulation_log([f"ERROR DURING EVENT '{html.escape(event_name)}': {msg}"])

if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app_dir = os.path.dirname(os.path.abspath(__file__)); dependencies_dir = os.path.join(app_dir, "dependencies", "icons")
    if not os.path.exists(dependencies_dir):
        try: os.makedirs(dependencies_dir, exist_ok=True); print(f"Info: Created directory for QSS icons: {dependencies_dir}")
        except OSError as e: print(f"Warning: Could not create directory {dependencies_dir}: {e}")
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET_GLOBAL)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
