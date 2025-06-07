# bsm_designer_project/main.py

# FILE: bsm_designer_project/main.py
# Includes connections for validation signals and the Problems Dock.

import sys
import os
import tempfile
import subprocess
import io
import contextlib
import json
import html
import math
import socket
import re
import logging
import threading

from PyQt5.QtCore import (
    Qt, QTime, QTimer, QPointF, QMetaObject, QFile, QTemporaryFile, QDir,
    QIODevice, QFileInfo, QEvent, QSize, QUrl, pyqtSignal, pyqtSlot,
    QThread, QPoint, QMimeData, QObject, QSaveFile
)
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform, QKeyEvent, QKeySequence, QCursor,
    QDesktopServices, QWheelEvent, QMouseEvent, QCloseEvent, QFontMetrics, QPalette, QRegion
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QToolBox, QAction,
    QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QStatusBar, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout, # Added QColorDialog
    QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
    QFileDialog, QProgressBar, QTabWidget, QCheckBox, QActionGroup, QGraphicsItem, # Added QCheckBox
    QGroupBox, QUndoStack, QUndoCommand, QStyle, QSizePolicy, QGraphicsLineItem,
    QToolButton, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent,
    QGraphicsSceneHoverEvent, QGraphicsTextItem, QGraphicsDropShadowEffect,
    QHeaderView, QTableWidget, QTableWidgetItem, QAbstractItemView
)

import pygraphviz as pgv 

# --- Custom Modules ---
from graphics_scene import DiagramScene, ZoomableView
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
from fsm_simulator import FSMSimulator, FSMError
from ai_chatbot import AIChatbotManager, AIStatus, AIChatUIManager 
from dialogs import (MatlabSettingsDialog, FindItemDialog) 
from matlab_integration import MatlabConnection
from config import (
    APP_VERSION, APP_NAME, FILE_EXTENSION, FILE_FILTER, STYLE_SHEET_GLOBAL,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_STATE_DEFAULT_BORDER, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG,
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_PRIMARY_LIGHT, COLOR_BACKGROUND_APP,
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_BACKGROUND_LIGHT, COLOR_GRID_MINOR, COLOR_GRID_MAJOR,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_ON_ACCENT,
    COLOR_ACCENT_SECONDARY, COLOR_BORDER_LIGHT, COLOR_BORDER_MEDIUM,
    COLOR_DRAGGABLE_BUTTON_BG, COLOR_DRAGGABLE_BUTTON_BORDER,
    COLOR_DRAGGABLE_BUTTON_HOVER_BG, COLOR_DRAGGABLE_BUTTON_HOVER_BORDER,
    COLOR_DRAGGABLE_BUTTON_PRESSED_BG, APP_FONT_SIZE_SMALL, APP_FONT_SIZE_STANDARD,
    APP_FONT_FAMILY, APP_FONT_SIZE_EDITOR,
    COLOR_BACKGROUND_EDITOR_DARK, COLOR_TEXT_EDITOR_DARK_PRIMARY, COLOR_BORDER_DARK,
    COLOR_ACCENT_SUCCESS, COLOR_ACCENT_ERROR, COLOR_BACKGROUND_MEDIUM,
    FSM_TEMPLATES_BUILTIN,MIME_TYPE_BSM_TEMPLATE, DEFAULT_EXECUTION_ENV
)
from ui_py_simulation_manager import PySimulationUIManager
from ui_manager import UIManager
from ide_manager import IDEManager
from action_handlers import ActionHandler
from resource_monitor import ResourceMonitorManager
from snippet_manager import CustomSnippetManager # Added import

try:
    from logging_setup import setup_global_logging
except ImportError:
    print("CRITICAL: logging_setup.py not found. Logging will be basic.")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

try:
    import resources_rc
    RESOURCES_AVAILABLE = True
except ImportError:
    RESOURCES_AVAILABLE = False
    print("WARNING: resources_rc.py not found. Icons and bundled files might be missing. Run: pyrcc5 resources.qrc -o resources_rc.py")

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    RESOURCES_AVAILABLE = RESOURCES_AVAILABLE 

    # --- Properties Dock Logic (MOVED EARLIER for definition order) ---
    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems()
        
        if not all(hasattr(self, attr_name) and getattr(self, attr_name) is not None for attr_name in [
            'properties_editor_layout', '_dock_property_editors', 
            'properties_editor_container', 'properties_placeholder_label',
            'properties_edit_dialog_button', 'properties_apply_button', 
            'properties_revert_button'
        ]):
            logger.warning("MainWindow._update_properties_dock: One or more UI elements for properties dock are missing. Skipping update.")
            return

        while self.properties_editor_layout.count():
            child_layout_item = self.properties_editor_layout.takeAt(0)
            if child_layout_item:
                widget = child_layout_item.widget()
                if widget: widget.deleteLater()
                layout_in_item = child_layout_item.layout() 
                if layout_in_item:
                    while layout_in_item.count(): 
                        nested_child = layout_in_item.takeAt(0)
                        if nested_child.widget(): nested_child.widget().deleteLater()
        
        self._dock_property_editors.clear()
        self._current_edited_item_in_dock = None
        self._current_edited_item_original_props_in_dock = {} 
        
        if len(selected_items) == 1:
            self._current_edited_item_in_dock = selected_items[0]
            item_data = {}
            if hasattr(self._current_edited_item_in_dock, 'get_data'):
                item_data = self._current_edited_item_in_dock.get_data()
            
            self._current_edited_item_original_props_in_dock = item_data.copy() 

            self.properties_editor_container.setVisible(True)
            self.properties_placeholder_label.setVisible(False)
            self.properties_edit_dialog_button.setEnabled(True)

            if isinstance(self._current_edited_item_in_dock, GraphicsStateItem):
                name_edit = QLineEdit(item_data.get('name', ''))
                name_edit.textChanged.connect(self._on_dock_property_changed_mw)
                self.properties_editor_layout.addRow("Name:", name_edit)
                self._dock_property_editors['name'] = name_edit

                initial_cb = QCheckBox("Is Initial State")
                initial_cb.setChecked(item_data.get('is_initial', False))
                initial_cb.toggled.connect(self._on_dock_property_changed_mw)
                self.properties_editor_layout.addRow(initial_cb)
                self._dock_property_editors['is_initial'] = initial_cb
                
                final_cb = QCheckBox("Is Final State")
                final_cb.setChecked(item_data.get('is_final', False))
                final_cb.toggled.connect(self._on_dock_property_changed_mw)
                self.properties_editor_layout.addRow(final_cb)
                self._dock_property_editors['is_final'] = final_cb

                superstate_cb = QCheckBox("Is Superstate")
                superstate_cb.setChecked(item_data.get('is_superstate', False))
                superstate_cb.toggled.connect(self._on_dock_property_changed_mw)
                self.properties_editor_layout.addRow(superstate_cb)
                self._dock_property_editors['is_superstate'] = superstate_cb
                
                color_button = QPushButton()
                color_button.setObjectName("ColorButtonPropertiesDock") 
                self._update_dock_color_button_style(color_button, QColor(item_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG)))
                color_button.clicked.connect(lambda: self._on_dock_color_button_clicked(color_button))
                self.properties_editor_layout.addRow("Color:", color_button)
                self._dock_property_editors['color_button'] = color_button
                color_button.setProperty("currentColorHex", QColor(item_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG)).name())

            elif isinstance(self._current_edited_item_in_dock, GraphicsTransitionItem):
                event_edit = QLineEdit(item_data.get('event', ''))
                event_edit.textChanged.connect(self._on_dock_property_changed_mw)
                self.properties_editor_layout.addRow("Event:", event_edit)
                self._dock_property_editors['event'] = event_edit
                
                condition_edit = QLineEdit(item_data.get('condition', ''))
                condition_edit.textChanged.connect(self._on_dock_property_changed_mw)
                self.properties_editor_layout.addRow("Condition:", condition_edit)
                self._dock_property_editors['condition'] = condition_edit
                
                color_button = QPushButton()
                color_button.setObjectName("ColorButtonPropertiesDock")
                self._update_dock_color_button_style(color_button, QColor(item_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT)))
                color_button.clicked.connect(lambda: self._on_dock_color_button_clicked(color_button))
                self.properties_editor_layout.addRow("Color:", color_button)
                self._dock_property_editors['color_button'] = color_button
                color_button.setProperty("currentColorHex", QColor(item_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT)).name())

            elif isinstance(self._current_edited_item_in_dock, GraphicsCommentItem):
                text_edit = QTextEdit(item_data.get('text', ''))
                text_edit.setFixedHeight(80) 
                text_edit.textChanged.connect(self._on_dock_property_changed_mw)
                self.properties_editor_layout.addRow("Text:", text_edit)
                self._dock_property_editors['text'] = text_edit
            
            else:
                 self.properties_placeholder_label.setText(f"<i>Editing: {type(self._current_edited_item_in_dock).__name__}.<br>Use 'Advanced Edit...' for details.</i>")
                 self.properties_editor_container.setVisible(False)
                 self.properties_placeholder_label.setVisible(True)
                 self.properties_edit_dialog_button.setEnabled(True)

        elif len(selected_items) > 1:
            self.properties_placeholder_label.setText(f"<i><b>{len(selected_items)} items selected.</b><br><span style='font-size:{APP_FONT_SIZE_SMALL}; color:{COLOR_TEXT_SECONDARY};'>Select a single item to edit properties.</span></i>")
            self.properties_editor_container.setVisible(False); self.properties_placeholder_label.setVisible(True); self.properties_edit_dialog_button.setEnabled(False)
        else: 
            self.properties_placeholder_label.setText(f"<i>No item selected.</i><br><span style='font-size:{APP_FONT_SIZE_SMALL}; color:{COLOR_TEXT_SECONDARY};'>Click an item or use tools to add elements.</span>")
            self.properties_editor_container.setVisible(False); self.properties_placeholder_label.setVisible(True); self.properties_edit_dialog_button.setEnabled(False)
        
        self.properties_apply_button.setEnabled(False)
        self.properties_revert_button.setEnabled(False)

    def _update_dock_color_button_style(self, button: QPushButton, color: QColor):
        luminance = color.lightnessF()
        text_color_name = COLOR_TEXT_ON_ACCENT if luminance < 0.5 else COLOR_TEXT_PRIMARY
        button.setStyleSheet(f"""
            QPushButton#ColorButtonPropertiesDock {{
                background-color: {color.name()};
                color: {text_color_name};
                border: 1px solid {color.darker(130).name()};
                padding: 5px; 
                min-height: 20px;
                text-align: center;
            }}
            QPushButton#ColorButtonPropertiesDock:hover {{
                border: 1.5px solid {COLOR_ACCENT_PRIMARY};
            }}
        """)
        button.setText(color.name().upper())

    def _on_dock_color_button_clicked(self, color_button: QPushButton):
        current_color_hex = color_button.property("currentColorHex")
        initial_color = QColor(current_color_hex) if current_color_hex else QColor(Qt.white)
        
        dialog = QColorDialog(self)
        dialog.setCurrentColor(initial_color)
        if dialog.exec_():
            new_color = dialog.selectedColor()
            if new_color.isValid() and new_color != initial_color:
                self._update_dock_color_button_style(color_button, new_color)
                color_button.setProperty("currentColorHex", new_color.name())
                self._on_dock_property_changed_mw() 

    @pyqtSlot()
    def _on_dock_property_changed_mw(self): 
        if hasattr(self, 'properties_apply_button'): self.properties_apply_button.setEnabled(True)
        if hasattr(self, 'properties_revert_button'): self.properties_revert_button.setEnabled(True)

    @pyqtSlot()
    def _on_apply_dock_properties(self):
        if not self._current_edited_item_in_dock or not self._dock_property_editors:
            logger.warning("ApplyDockProperties: No item or editors to apply.")
            return

        old_props_full = self._current_edited_item_original_props_in_dock.copy()
        new_props_from_dock = old_props_full.copy() 

        item_type_changed = False 
        current_item_type = type(self._current_edited_item_in_dock)

        if current_item_type is GraphicsStateItem:
            if 'name' in self._dock_property_editors:
                new_name = self._dock_property_editors['name'].text().strip()
                if not new_name: QMessageBox.warning(self, "Invalid Name", "State name cannot be empty."); return
                existing_state = self.scene.get_state_by_name(new_name)
                if new_name != old_props_full.get('name') and existing_state and existing_state != self._current_edited_item_in_dock:
                    QMessageBox.warning(self, "Duplicate Name", f"A state named '{new_name}' already exists."); return
                new_props_from_dock['name'] = new_name
            if 'is_initial' in self._dock_property_editors: new_props_from_dock['is_initial'] = self._dock_property_editors['is_initial'].isChecked()
            if 'is_final' in self._dock_property_editors: new_props_from_dock['is_final'] = self._dock_property_editors['is_final'].isChecked()
            if 'is_superstate' in self._dock_property_editors: new_props_from_dock['is_superstate'] = self._dock_property_editors['is_superstate'].isChecked()
            if 'color_button' in self._dock_property_editors: new_props_from_dock['color'] = self._dock_property_editors['color_button'].property("currentColorHex")

        elif current_item_type is GraphicsTransitionItem:
            if 'event' in self._dock_property_editors: new_props_from_dock['event'] = self._dock_property_editors['event'].text().strip()
            if 'condition' in self._dock_property_editors: new_props_from_dock['condition'] = self._dock_property_editors['condition'].text().strip()
            if 'color_button' in self._dock_property_editors: new_props_from_dock['color'] = self._dock_property_editors['color_button'].property("currentColorHex")
        
        elif current_item_type is GraphicsCommentItem:
            if 'text' in self._dock_property_editors: new_props_from_dock['text'] = self._dock_property_editors['text'].toPlainText().strip()
        
        changed_in_dock = False
        for key, editor_widget in self._dock_property_editors.items():
            prop_key_in_data = key
            if key == 'color_button': prop_key_in_data = 'color'
            
            new_val = None
            old_val = old_props_full.get(prop_key_in_data)

            if isinstance(editor_widget, QLineEdit): new_val = editor_widget.text().strip()
            elif isinstance(editor_widget, QTextEdit): new_val = editor_widget.toPlainText().strip()
            elif isinstance(editor_widget, QCheckBox): new_val = editor_widget.isChecked()
            elif key == 'color_button': new_val = editor_widget.property("currentColorHex")
            
            if new_val is not None and new_val != old_val:
                changed_in_dock = True
                break
        
        if not changed_in_dock:
            logger.info("Properties in dock are identical to original, no changes applied.")
            self.properties_apply_button.setEnabled(False)
            self.properties_revert_button.setEnabled(False)
            return

        cmd = EditItemPropertiesCommand(self._current_edited_item_in_dock, old_props_full, new_props_from_dock, f"Edit Properties via Dock")
        self.undo_stack.push(cmd) 
        
        if hasattr(self._current_edited_item_in_dock, 'get_data'): 
            self._current_edited_item_original_props_in_dock = self._current_edited_item_in_dock.get_data().copy()

        self.properties_apply_button.setEnabled(False)
        self.properties_revert_button.setEnabled(False)
        item_name_for_log = new_props_from_dock.get('name', new_props_from_dock.get('event', new_props_from_dock.get('text', 'Item')))
        self.log_message("INFO", f"Properties updated via dock for: {item_name_for_log}")

    @pyqtSlot()
    def _on_revert_dock_properties(self):
        if not self._current_edited_item_in_dock or not self._dock_property_editors or not self._current_edited_item_original_props_in_dock:
            logger.warning("RevertDockProperties: No item, editors, or original props to revert.")
            return

        original_props = self._current_edited_item_original_props_in_dock
        current_item_type = type(self._current_edited_item_in_dock)

        for editor in self._dock_property_editors.values():
            editor.blockSignals(True)

        if current_item_type is GraphicsStateItem:
            if 'name' in self._dock_property_editors: self._dock_property_editors['name'].setText(original_props.get('name', ''))
            if 'is_initial' in self._dock_property_editors: self._dock_property_editors['is_initial'].setChecked(original_props.get('is_initial', False))
            if 'is_final' in self._dock_property_editors: self._dock_property_editors['is_final'].setChecked(original_props.get('is_final', False))
            if 'is_superstate' in self._dock_property_editors: self._dock_property_editors['is_superstate'].setChecked(original_props.get('is_superstate', False))
            if 'color_button' in self._dock_property_editors:
                color_val = QColor(original_props.get('color', COLOR_ITEM_STATE_DEFAULT_BG))
                self._update_dock_color_button_style(self._dock_property_editors['color_button'], color_val)
                self._dock_property_editors['color_button'].setProperty("currentColorHex", color_val.name())
        
        elif current_item_type is GraphicsTransitionItem:
            if 'event' in self._dock_property_editors: self._dock_property_editors['event'].setText(original_props.get('event', ''))
            if 'condition' in self._dock_property_editors: self._dock_property_editors['condition'].setText(original_props.get('condition', ''))
            if 'color_button' in self._dock_property_editors:
                color_val = QColor(original_props.get('color', COLOR_ITEM_TRANSITION_DEFAULT))
                self._update_dock_color_button_style(self._dock_property_editors['color_button'], color_val)
                self._dock_property_editors['color_button'].setProperty("currentColorHex", color_val.name())

        elif current_item_type is GraphicsCommentItem:
            if 'text' in self._dock_property_editors: self._dock_property_editors['text'].setPlainText(original_props.get('text', ''))

        for editor in self._dock_property_editors.values():
            editor.blockSignals(False)

        self.properties_apply_button.setEnabled(False)
        self.properties_revert_button.setEnabled(False)
        self.log_message("INFO", "Properties in dock reverted to selection state.")
    # --- END Properties Dock Logic ---

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - Untitled") # No [*] initially

        self.current_file_path = None
        self.last_generated_model_path = None
        self.undo_stack = QUndoStack(self)
        
        self.custom_snippet_manager = CustomSnippetManager(app_name=APP_NAME) # Instantiate snippet manager
        
        self.scene = DiagramScene(self.undo_stack, self, custom_snippet_manager=self.custom_snippet_manager) 
        self.view = ZoomableView(self.scene, self)

        self.ui_manager = UIManager(self)
        self.action_handler = ActionHandler(self)
        self.resource_monitor_manager = ResourceMonitorManager(self) 
        
        self.matlab_connection = MatlabConnection()
        self.ai_chatbot_manager = AIChatbotManager(self) 
        self.py_sim_ui_manager = PySimulationUIManager(self)
        self.ai_chat_ui_manager = AIChatUIManager(self) 

        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False
        self.find_item_dialog: FindItemDialog | None = None
        
        self._current_edited_item_original_props_in_dock = {} 

        self.ui_manager.setup_ui() 
        self.ide_manager = IDEManager(self) 

        try:
            if not hasattr(self, 'log_output') or not self.log_output: 
                self.log_output = QTextEdit() 
                logger.warning("MainWindow: log_output fallback used before logging setup.")
            setup_global_logging(self.log_output)
            logger.info("Main window initialized and logging configured.")
        except Exception as e:
            print(f"ERROR: Failed to run setup_global_logging: {e}. UI logs might not work.")
            if not logging.getLogger().hasHandlers():
                 logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

        self.ui_manager.populate_dynamic_docks() 
                                                 
        self._connect_signals() 
        self.action_handler.connect_actions() 

        if self.resource_monitor_manager: 
            self.resource_monitor_manager.setup_and_start_monitor()
            if self.resource_monitor_manager.worker:
                 self.resource_monitor_manager.worker.resourceUpdate.connect(self._update_resource_display)
            else:
                logger.error("MainWindow: ResourceMonitorManager worker not available for signal connection post setup.")

        self._internet_connected: bool | None = None
        self.internet_check_timer = QTimer(self)
        self._init_internet_status_check()

        self._set_status_label_object_names() 
        self._update_ui_element_states()      

        QTimer.singleShot(0, lambda: self.action_handler.on_new_file(silent=True)) 

        if self.ai_chat_ui_manager and self.ai_chatbot_manager:
            QTimer.singleShot(250, lambda: self.ai_chatbot_manager.set_online_status(
                self._internet_connected if self._internet_connected is not None else False
            ))
        else:
            logger.warning("MainWindow: ai_chat_ui_manager or ai_chatbot_manager not fully initialized for final status update.")

    def _connect_signals(self): 
        self.scene.selectionChanged.connect(self._update_zoom_to_selection_action_enable_state)
        self.scene.selectionChanged.connect(self._update_align_distribute_actions_enable_state)
        self.scene.selectionChanged.connect(self._update_properties_dock) 
        self.scene.scene_content_changed_for_find.connect(self._refresh_find_dialog_if_visible)
        self.scene.modifiedStatusChanged.connect(self.setWindowModified) 
        self.scene.modifiedStatusChanged.connect(self._update_window_title)
        self.scene.validation_issues_updated.connect(self.update_problems_dock)

        if hasattr(self, 'view') and self.view:
            self.view.zoomChanged.connect(self.update_zoom_status_display)
        
        if self.py_sim_ui_manager:
            self.py_sim_ui_manager.simulationStateChanged.connect(self._handle_py_sim_state_changed_by_manager)
            self.py_sim_ui_manager.requestGlobalUIEnable.connect(self._handle_py_sim_global_ui_enable_by_manager)
        
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)
        
        if self.ide_manager:
            self.ide_manager.ide_dirty_state_changed.connect(self._on_ide_dirty_state_changed_by_manager)
            self.ide_manager.ide_file_path_changed.connect(self._update_window_title)
            self.ide_manager.ide_language_combo_changed.connect(self._on_ide_language_changed_by_manager)
            
        if hasattr(self, 'properties_apply_button'):
            self.properties_apply_button.clicked.connect(self._on_apply_dock_properties)
        if hasattr(self, 'properties_revert_button'):
            self.properties_revert_button.clicked.connect(self._on_revert_dock_properties)
        if hasattr(self, 'properties_edit_dialog_button'):
            try: self.properties_edit_dialog_button.clicked.disconnect() 
            except TypeError: pass 
            self.properties_edit_dialog_button.clicked.connect(lambda: self.scene.edit_item_properties(self._current_edited_item_in_dock) if self._current_edited_item_in_dock else None)

    @pyqtSlot(float, float, float, str)
    def _update_resource_display(self, cpu_usage, ram_usage, gpu_util, gpu_name):
        if hasattr(self, 'cpu_status_label'): self.cpu_status_label.setText(f"CPU: {cpu_usage:.0f}%")
        if hasattr(self, 'ram_status_label'): self.ram_status_label.setText(f"RAM: {ram_usage:.0f}%")
        if hasattr(self, 'gpu_status_label'):
            if gpu_util == -1.0: self.gpu_status_label.setText(f"GPU: {gpu_name}") 
            elif gpu_util == -2.0: self.gpu_status_label.setText(f"GPU: NVML Err") 
            elif gpu_util == -3.0: self.gpu_status_label.setText(f"GPU: Mon Err") 
            elif self.resource_monitor_manager and self.resource_monitor_manager.worker and self.resource_monitor_manager.worker._nvml_initialized and self.resource_monitor_manager.worker._gpu_handle:
                self.gpu_status_label.setText(f"GPU: {gpu_util:.0f}%")
                self.gpu_status_label.setToolTip(f"GPU: {gpu_util:.0f}% ({gpu_name})")
            else: 
                 self.gpu_status_label.setText(f"GPU: N/A"); self.gpu_status_label.setToolTip(gpu_name)

    def _set_status_label_object_names(self):
        if hasattr(self, 'main_op_status_label'): self.main_op_status_label.setObjectName("MainOpStatusLabel")
        if hasattr(self, 'ide_file_status_label'): self.ide_file_status_label.setObjectName("IdeFileStatusLabel")
        if hasattr(self, 'zoom_status_label'): self.zoom_status_label.setObjectName("ZoomStatusLabel")
        if hasattr(self, 'cpu_status_label'): self.cpu_status_label.setObjectName("CpuStatusLabel")
        if hasattr(self, 'ram_status_label'): self.ram_status_label.setObjectName("RamStatusLabel")
        if hasattr(self, 'gpu_status_label'): self.gpu_status_label.setObjectName("GpuStatusLabel")
        if hasattr(self, 'py_sim_status_label'): self.py_sim_status_label.setObjectName("PySimStatusLabel")
        if hasattr(self, 'matlab_status_label'): self.matlab_status_label.setObjectName("MatlabStatusLabel")
        if hasattr(self, 'internet_status_label'): self.internet_status_label.setObjectName("InternetStatusLabel")

    def _update_ui_element_states(self):
        self._update_properties_dock()
        self._update_py_simulation_actions_enabled_state()
        self._update_zoom_to_selection_action_enable_state()
        self._update_align_distribute_actions_enable_state()
        if hasattr(self, 'view') and self.view:
             self.update_zoom_status_display(self.view.transform().m11())

    def _update_save_actions_enable_state(self):
        if hasattr(self, 'save_action'):
            self.save_action.setEnabled(self.scene.is_dirty())

    def _update_ide_save_actions_enable_state(self):
        if self.ide_manager:
            self.ide_manager.update_ide_save_actions_enable_state()

    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo())
        self.redo_action.setEnabled(self.undo_stack.canRedo())
        undo_text = self.undo_stack.undoText()
        redo_text = self.undo_stack.redoText()
        self.undo_action.setText(f"&Undo{(' ' + undo_text) if undo_text else ''}")
        self.redo_action.setText(f"&Redo{(' ' + redo_text) if redo_text else ''}")
        self.undo_action.setToolTip(f"Undo: {undo_text}" if undo_text else "Undo")
        self.redo_action.setToolTip(f"Redo: {redo_text}" if redo_text else "Redo")

    def _update_matlab_status_display(self, connected, message):
        status_text = f"MATLAB: {'Connected' if connected else 'Not Connected'}"
        tooltip_text = f"MATLAB Status: {message}"
        if hasattr(self, 'matlab_status_label'):
            self.matlab_status_label.setText(status_text)
            self.matlab_status_label.setToolTip(tooltip_text)
            text_color = COLOR_ACCENT_SUCCESS if connected else COLOR_ACCENT_ERROR
            bg_color = QColor(text_color).lighter(180).name()
            self.matlab_status_label.setStyleSheet(f"font-weight:bold; padding:2px 5px; color:{text_color}; background-color:{bg_color}; border-radius:3px;")
        if "Initializing" not in message or (connected and "Initializing" in message):
            logging.info("MATLAB Connection Status: %s", message)
        self._update_matlab_actions_enabled_state()

    def _update_matlab_actions_enabled_state(self):
        can_run_matlab_ops = self.matlab_connection.connected and not self.py_sim_active
        if hasattr(self, 'export_simulink_action'): self.export_simulink_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'run_simulation_action'): self.run_simulation_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'generate_matlab_code_action'): self.generate_matlab_code_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'matlab_settings_action'): self.matlab_settings_action.setEnabled(not self.py_sim_active)

    def _start_matlab_operation(self, operation_name):
        logging.info("MATLAB Operation: '%s' starting...", operation_name)
        if hasattr(self, 'main_op_status_label'): self.main_op_status_label.setText(f"MATLAB: {operation_name}...")
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False)

    def _finish_matlab_operation(self):
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(False)
        self._update_window_title() 
        self.set_ui_enabled_for_matlab_op(True)
        logging.info("MATLAB Operation: Finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        if hasattr(self, 'menuBar'): self.menuBar().setEnabled(enabled)
        for child in self.findChildren(QToolBar):
            child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock", "IDEDock", "ProblemsDock"]:
            dock = self.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(enabled)
        self._update_py_simulation_actions_enabled_state()

    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation()
        logging.log(logging.INFO if success else logging.ERROR, "MATLAB Result (ModelGen/Sim): %s", message)
        if success:
            if "Model generation" in message and data:
                self.last_generated_model_path = data
                QMessageBox.information(self, "Simulink Model Generation", f"Model generated successfully:\n{data}")
            elif "Simulation" in message:
                QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else:
            QMessageBox.warning(self, "MATLAB Operation Failed", message)

    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation()
        logging.log(logging.INFO if success else logging.ERROR, "MATLAB Code Gen Result: %s", message)
        if success and output_dir:
            msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Information); msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText); abs_dir = os.path.abspath(output_dir)
            msg_box.setText(f"Code generation completed successfully.<br>Generated files are in: <a href='file:///{abs_dir}'>{abs_dir}</a>")
            msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction)
            open_btn = msg_box.addButton("Open Directory", QMessageBox.ActionRole); msg_box.addButton(QMessageBox.Ok)
            msg_box.exec()
            if msg_box.clickedButton() == open_btn:
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(abs_dir)):
                    logging.error("Error opening directory: %s", abs_dir)
                    QMessageBox.warning(self, "Error Opening Directory", f"Could not automatically open the directory:\n{abs_dir}")
        elif not success:
            QMessageBox.warning(self, "Code Generation Failed", message)

    def _prompt_save_if_dirty(self) -> bool:
        if not self.scene.is_dirty(): return True
        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving or opening a new file.")
            return False
        file_desc = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled Diagram"
        reply = QMessageBox.question(self, "Save Diagram Changes?",
                                     f"The diagram '{file_desc}' has unsaved changes. Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save)
        if reply == QMessageBox.Save: return self.action_handler.on_save_file() 
        elif reply == QMessageBox.Cancel: return False
        return True
        
    def _prompt_ide_save_if_dirty(self) -> bool:
        if self.ide_manager:
            return self.ide_manager.prompt_ide_save_if_dirty()
        return True

    def _load_from_path(self, file_path): 
        try:
            if file_path.startswith(":/"):
                qfile = QFile(file_path)
                if not qfile.open(QIODevice.ReadOnly | QIODevice.Text):
                    logging.error("Failed to open resource file %s: %s", file_path, qfile.errorString())
                    return False
                file_content_bytes = qfile.readAll()
                qfile.close()
                file_content_str = file_content_bytes.data().decode('utf-8')
                data = json.loads(file_content_str)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data:
                logging.error("Invalid BSM file format: %s. Missing required keys.", file_path)
                return False
            self.scene.clear()
            self.scene.load_diagram_data(data) 
            for item in self.scene.items():
                if isinstance(item, GraphicsStateItem):
                    self.connect_state_item_signals(item)
            return True
        except json.JSONDecodeError as e: logging.error("JSONDecodeError loading %s: %s", file_path, e); return False
        except Exception as e: logging.error("Unexpected error loading %s: %s", file_path, e, exc_info=True); return False

    def _save_to_path(self, file_path) -> bool: 
        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving.")
            return False
        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            error_str = save_file.errorString(); logging.error("Failed to open QSaveFile for %s: %s", file_path, error_str)
            QMessageBox.critical(self, "Save Error", f"Could not open file for saving:\n{error_str}"); return False
        try:
            diagram_data = self.scene.get_diagram_data()
            json_data_str = json.dumps(diagram_data, indent=4, ensure_ascii=False)
            bytes_written = save_file.write(json_data_str.encode('utf-8'))
            if bytes_written == -1:
                 error_str = save_file.errorString(); logging.error("Error writing to QSaveFile %s: %s", file_path, error_str)
                 QMessageBox.critical(self, "Save Error", f"Could not write data to file:\n{error_str}"); save_file.cancelWriting(); return False
            if not save_file.commit():
                error_str = save_file.errorString(); logging.error("Failed to commit QSaveFile for %s: %s", file_path, error_str)
                QMessageBox.critical(self, "Save Error", f"Could not finalize saving file:\n{error_str}"); return False
            logging.info("Successfully saved diagram to: %s", file_path)
            self._update_window_title() 
            self.scene.set_dirty(False); self._update_save_actions_enable_state(); return True
        except Exception as e:
            logging.error("Unexpected error during save to %s: %s", file_path, e, exc_info=True)
            QMessageBox.critical(self, "Save Error", f"An unexpected error occurred during saving:\n{e}"); save_file.cancelWriting(); return False

    @pyqtSlot(QGraphicsItem)
    def focus_on_item(self, item_to_focus: QGraphicsItem):
        if item_to_focus and item_to_focus.scene() == self.scene:
            self.scene.clearSelection()
            item_to_focus.setSelected(True)
            item_rect = item_to_focus.sceneBoundingRect(); padding = 50
            view_rect_with_padding = item_rect.adjusted(-padding, -padding, padding, padding)
            if self.view: self.view.fitInView(view_rect_with_padding, Qt.KeepAspectRatio)
            display_name = "Item"
            if isinstance(item_to_focus, GraphicsStateItem): display_name = f"State: {item_to_focus.text_label}"
            elif isinstance(item_to_focus, GraphicsTransitionItem): display_name = f"Transition: {item_to_focus._compose_label_string()}"
            elif isinstance(item_to_focus, GraphicsCommentItem): display_name = f"Comment: {item_to_focus.toPlainText()[:30]}..."
            self.log_message("INFO", f"Focused on {display_name}")
            if self.find_item_dialog and not self.find_item_dialog.isHidden(): pass 
        else: self.log_message("WARNING", f"Could not find or focus on the provided item: {item_to_focus}")

    @pyqtSlot(bool) 
    def on_matlab_settings(self, checked=False): 
        dialog = MatlabSettingsDialog(matlab_connection=self.matlab_connection, parent=self)
        dialog.exec_()
        logger.info("MATLAB settings dialog closed.")

    def closeEvent(self, event: QCloseEvent):
        logger.info("MW_CLOSE: closeEvent received.")
        if not self._prompt_ide_save_if_dirty(): event.ignore(); return
        if not self._prompt_save_if_dirty(): event.ignore(); return
        if hasattr(self, 'py_sim_ui_manager') and self.py_sim_ui_manager: self.py_sim_ui_manager.on_stop_py_simulation(silent=True)
        if self.internet_check_timer and self.internet_check_timer.isActive(): self.internet_check_timer.stop(); logger.info("MW_CLOSE: Internet check timer stopped.")
        if self.ai_chatbot_manager: self.ai_chatbot_manager.stop_chatbot(); logger.info("MW_CLOSE: AI Chatbot manager stopped.")
        
        if self.resource_monitor_manager: 
            self.resource_monitor_manager.stop_monitoring_system()
            self.resource_monitor_manager = None 
            
        if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads: logging.info("MW_CLOSE: Closing application. %d MATLAB processes initiated by this session may still be running in the background if not completed.", len(self.matlab_connection._active_threads))
        app_temp_session_dir_name = f"BSMDesigner_Temp_{QApplication.applicationPid()}"; session_temp_dir_path = QDir(QDir.tempPath()).filePath(app_temp_session_dir_name)
        if QDir(session_temp_dir_path).exists():
            if QDir(session_temp_dir_path).removeRecursively(): logger.info(f"MW_CLOSE: Cleaned up session temporary directory: {session_temp_dir_path}")
            else: logger.warning(f"MW_CLOSE: Failed to clean up session temporary directory: {session_temp_dir_path}")
        logger.info("MW_CLOSE: Application closeEvent accepted.")
        event.accept()

    @pyqtSlot(float)
    def update_zoom_status_display(self, scale_factor: float):
        if hasattr(self, 'zoom_status_label'):
            zoom_percentage = int(scale_factor * 100)
            self.zoom_status_label.setText(f"Zoom: {zoom_percentage}%")

    @pyqtSlot(bool)
    def _handle_py_sim_state_changed_by_manager(self, is_running: bool):
        logger.debug(f"MW: PySim state changed by manager to: {is_running}")
        self.py_sim_active = is_running
        self._update_window_title()
        self._update_py_sim_status_display() 
        self._update_matlab_actions_enabled_state()
        self._update_py_simulation_actions_enabled_state()

    @pyqtSlot(bool)
    def _handle_py_sim_global_ui_enable_by_manager(self, enable: bool):
        logger.debug(f"MW: Global UI enable requested by PySim manager: {enable}")
        is_editable = enable
        diagram_editing_actions = [
            self.new_action, self.open_action, self.save_action, self.save_as_action,
            self.undo_action, self.redo_action, self.delete_action, self.select_all_action,
            self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action
        ]
        for action in diagram_editing_actions:
            if hasattr(action, 'setEnabled'): action.setEnabled(is_editable)
        if hasattr(self, 'tools_dock'): self.tools_dock.setEnabled(is_editable)
        if hasattr(self, 'properties_edit_dialog_button'): self.properties_edit_dialog_button.setEnabled(is_editable and len(self.scene.selectedItems())==1)
        if hasattr(self, 'properties_apply_button'): self.properties_apply_button.setEnabled(False) 
        if hasattr(self, 'properties_revert_button'): self.properties_revert_button.setEnabled(False) 
        for item in self.scene.items():
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)):
                item.setFlag(QGraphicsItem.ItemIsMovable, is_editable and self.scene.current_mode == "select")
        if not is_editable and self.scene.current_mode != "select": self.scene.set_mode("select")
        self._update_matlab_actions_enabled_state()
        self._update_py_simulation_actions_enabled_state()

    @pyqtSlot(list)
    def update_problems_dock(self, issues_with_items: list):
        if not hasattr(self, 'problems_list_widget') or self.problems_list_widget is None:
            logger.warning("MainWindow.update_problems_dock: self.problems_list_widget is not yet initialized. Update deferred.")
            return
        self.problems_list_widget.clear()
        if issues_with_items:
            for issue_msg, item_ref in issues_with_items:
                list_item_widget = QListWidgetItem(str(issue_msg))
                if item_ref: list_item_widget.setData(Qt.UserRole, item_ref)
                self.problems_list_widget.addItem(list_item_widget)
            self.problems_dock.setWindowTitle(f"Validation Issues ({len(issues_with_items)})")
            if self.problems_dock.isHidden() and len(issues_with_items) > 0: self.problems_dock.show(); self.problems_dock.raise_()
        else: self.problems_list_widget.addItem("No validation issues found."); self.problems_dock.setWindowTitle("Validation Issues")

    @pyqtSlot(QListWidgetItem)
    def on_problem_item_double_clicked(self, list_item: QListWidgetItem):
        item_ref = list_item.data(Qt.UserRole)
        if item_ref and isinstance(item_ref, QGraphicsItem) and item_ref.scene() == self.scene:
            self.focus_on_item(item_ref)
            logger.info(f"Focused on problematic item from Validation Issues list: {getattr(item_ref, 'text_label', type(item_ref).__name__)}")
        else: logger.debug(f"No valid QGraphicsItem reference found for clicked validation issue: '{list_item.text()}'")

    @pyqtSlot(bool)
    def _on_ide_dirty_state_changed_by_manager(self, is_dirty: bool):
        self._update_ide_save_actions_enable_state()
        self._update_window_title()

    @pyqtSlot(str)
    def _on_ide_language_changed_by_manager(self, language_param: str):
        ai_ready = self.ai_chatbot_manager is not None and \
                   self.ai_chatbot_manager.api_key is not None and \
                   self._internet_connected is True
        
        if hasattr(self, 'ide_analyze_action'):
            can_analyze = (language_param == "Python" or language_param.startswith("C/C++")) and ai_ready
            self.ide_analyze_action.setEnabled(can_analyze)
            tooltip = "Analyze the current code with AI"
            if not ai_ready: tooltip += " (Requires Internet & Gemini API Key)"
            elif not (language_param == "Python" or language_param.startswith("C/C++")):
                 tooltip += " (Best for Python or C/C++)"
            self.ide_analyze_action.setToolTip(tooltip)
        self._update_window_title()

    def _update_window_title(self):
        diagram_file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        diagram_is_dirty = self.scene.is_dirty()
        
        ide_dock_title_str = "Standalone Code IDE"
        ide_status_bar_str = "IDE: Idle"
        ide_is_dirty = False
        
        if self.ide_manager:
            ide_is_dirty = self.ide_manager.ide_editor_is_dirty
            current_ide_lang_text = self.ide_manager.ide_language_combo.currentText() if self.ide_manager.ide_language_combo else ""
            lang_info = f" ({current_ide_lang_text})" if current_ide_lang_text else ""
            ide_dirty_char_dock = "*" if ide_is_dirty else ""
            
            if self.ide_manager.current_ide_file_path:
                ide_fn = os.path.basename(self.ide_manager.current_ide_file_path)
                ide_dock_title_str = f"IDE: {ide_fn}{ide_dirty_char_dock}{lang_info}"
                ide_status_bar_str = f"IDE: {ide_fn}{ide_dirty_char_dock}"
            elif self.ide_manager.ide_code_editor and self.ide_manager.ide_code_editor.toPlainText().strip():
                ide_dock_title_str = f"IDE: Untitled Script{ide_dirty_char_dock}{lang_info}"
                ide_status_bar_str = f"IDE: Untitled Script{ide_dirty_char_dock}"
            else: 
                ide_dock_title_str = f"Standalone Code IDE{lang_info}"
            
            if hasattr(self, 'ide_dock'): self.ide_dock.setWindowTitle(ide_dock_title_str)
            if hasattr(self, 'ide_file_status_label'): self.ide_file_status_label.setText(ide_status_bar_str)

        pysim_title_suffix = ""
        main_op_pysim_text = ""
        if self.py_sim_active:
            pysim_title_suffix = " [PySim Active"
            main_op_pysim_text = "PySim: Active"
            if self.py_fsm_engine and self.py_fsm_engine.paused_on_breakpoint:
                pysim_title_suffix += " (Paused)"
                main_op_pysim_text += " (Paused)"
            pysim_title_suffix += "]"
        
        main_window_is_dirty = diagram_is_dirty or ide_is_dirty
        self.setWindowModified(main_window_is_dirty) # Let Qt handle [*]
        
        # Construct window title string
        title_parts = [f"{APP_NAME} - {diagram_file_name}"]
        if pysim_title_suffix:
            title_parts.append(pysim_title_suffix)
        
        # If IDE file is open AND distinct from diagram, append its info
        if self.ide_manager and self.ide_manager.current_ide_file_path and \
           self.ide_manager.current_ide_file_path != self.current_file_path:
            ide_fn_short = os.path.basename(self.ide_manager.current_ide_file_path)
            title_parts.append(f"(IDE: {ide_fn_short})")
        elif self.ide_manager and ide_is_dirty and not self.ide_manager.current_ide_file_path:
            title_parts.append("(IDE: Untitled)")

        self.setWindowTitle(" ".join(title_parts))

        # Update main operation status label
        main_op_text = f"File: {diagram_file_name}{'*' if diagram_is_dirty else ''}"
        if hasattr(self, 'progress_bar') and self.progress_bar.isVisible(): 
             if hasattr(self, 'main_op_status_label') and "MATLAB:" in self.main_op_status_label.text():
                 main_op_text = self.main_op_status_label.text() 
             else: 
                 main_op_text = "Processing..." 
        elif self.py_sim_active: 
            main_op_text = main_op_pysim_text
        elif not self.current_file_path and not diagram_is_dirty and not ide_is_dirty: 
            main_op_text = "Ready"

        if hasattr(self, 'main_op_status_label'):
            self.main_op_status_label.setText(main_op_text)
        
        self._update_py_sim_status_display()

    def _init_internet_status_check(self):
        self.internet_check_timer.timeout.connect(self._run_internet_check_job)
        self.internet_check_timer.start(15000) 
        QTimer.singleShot(100, self._run_internet_check_job) 

    def _run_internet_check_job(self):
        current_status = False; status_detail = "Checking..."
        try:
            s = socket.create_connection(("8.8.8.8", 53), timeout=1.5) 
            s.close()
            current_status = True
            status_detail = "Connected"
        except socket.timeout:
            status_detail = "Timeout"
        except (socket.gaierror, OSError): 
            status_detail = "Net Issue"
        
        if current_status != self._internet_connected or self._internet_connected is None: 
            self._internet_connected = current_status
            self._update_internet_status_display(current_status, status_detail)

    def _update_ai_features_enabled_state(self, is_online_and_key_present: bool):
        if hasattr(self, 'ask_ai_to_generate_fsm_action'): self.ask_ai_to_generate_fsm_action.setEnabled(is_online_and_key_present)
        if hasattr(self, 'clear_ai_chat_action'): self.clear_ai_chat_action.setEnabled(is_online_and_key_present)
        if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager:
            if self.ai_chat_ui_manager.ai_chat_send_button: self.ai_chat_ui_manager.ai_chat_send_button.setEnabled(is_online_and_key_present)
            if self.ai_chat_ui_manager.ai_chat_input:
                self.ai_chat_ui_manager.ai_chat_input.setEnabled(is_online_and_key_present)
                if not is_online_and_key_present:
                    if self.ai_chatbot_manager and not self.ai_chatbot_manager.api_key: self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText("AI disabled: API Key required.")
                    elif not self._internet_connected: self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText("AI disabled: Internet connection required.")
                else: self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText("Type your message to the AI...")
        if hasattr(self, 'ide_analyze_action') and self.ide_manager and self.ide_manager.ide_language_combo: 
            current_ide_lang = self.ide_manager.ide_language_combo.currentText()
            can_analyze_ide = (current_ide_lang == "Python" or current_ide_lang.startswith("C/C++")) and is_online_and_key_present
            self.ide_analyze_action.setEnabled(can_analyze_ide)
            tooltip = "Analyze the current code with AI"
            if not (self.ai_chatbot_manager and self.ai_chatbot_manager.api_key and self._internet_connected): tooltip += " (Requires Internet & Gemini API Key)"
            elif not (current_ide_lang == "Python" or current_ide_lang.startswith("C/C++")): tooltip += " (Best for Python or C/C++)"
            self.ide_analyze_action.setToolTip(tooltip)

    def _update_internet_status_display(self, is_connected: bool, message_detail: str):
        full_status_text = f"Net: {message_detail}"
        if hasattr(self, 'internet_status_label'):
            self.internet_status_label.setText(full_status_text)
            host_for_tooltip = "8.8.8.8:53 (Google DNS)"; self.internet_status_label.setToolTip(f"Internet Status: {message_detail} (Checks connection to {host_for_tooltip})")
            text_color = COLOR_ACCENT_SUCCESS if is_connected else COLOR_ACCENT_ERROR; bg_color = QColor(text_color).lighter(180).name()
            self.internet_status_label.setStyleSheet(f"font-size:{APP_FONT_SIZE_SMALL}; padding:2px 5px; color:{text_color}; background-color:{bg_color}; border-radius:3px;")
        logging.debug("Internet Status Update: %s", message_detail)
        key_present = self.ai_chatbot_manager is not None and bool(self.ai_chatbot_manager.api_key)
        ai_ready = is_connected and key_present
        if hasattr(self.ai_chatbot_manager, 'set_online_status'): self.ai_chatbot_manager.set_online_status(is_connected)
        self._update_ai_features_enabled_state(ai_ready)

    def _update_py_sim_status_display(self): 
        if hasattr(self, 'py_sim_status_label'):
            status_text = "PySim: Idle"; style = f"font-weight:normal;padding:2px 5px; color:{COLOR_TEXT_SECONDARY}; background-color:{COLOR_BACKGROUND_MEDIUM}; border-radius:3px;"; tooltip = "Internal Python FSM Simulation is Idle."
            if self.py_sim_active and self.py_fsm_engine:
                current_state_name = self.py_fsm_engine.get_current_state_name(); display_state_name = (current_state_name[:20] + '...') if len(current_state_name) > 23 else current_state_name
                status_text = f"PySim: Active ({html.escape(display_state_name)})"; 
                bg_color = QColor(COLOR_PY_SIM_STATE_ACTIVE).lighter(180).name(); 
                style = f"font-weight:bold;padding:2px 5px;color:{COLOR_PY_SIM_STATE_ACTIVE.name()}; background-color:{bg_color}; border-radius:3px;"; 
                tooltip = f"Python FSM Simulation Active: {current_state_name}"
                if self.py_fsm_engine.paused_on_breakpoint: 
                    status_text += " (Paused)"; tooltip += " (Paused at Breakpoint)"
            self.py_sim_status_label.setText(status_text); self.py_sim_status_label.setStyleSheet(style); self.py_sim_status_label.setToolTip(tooltip)

    def _update_py_simulation_actions_enabled_state(self):
        is_matlab_op_running = False
        if hasattr(self, 'progress_bar') and self.progress_bar: is_matlab_op_running = self.progress_bar.isVisible()
        sim_can_start = not self.py_sim_active and not is_matlab_op_running; sim_can_be_controlled = self.py_sim_active and not is_matlab_op_running
        if hasattr(self, 'start_py_sim_action'): self.start_py_sim_action.setEnabled(sim_can_start)
        if hasattr(self, 'stop_py_sim_action'): self.stop_py_sim_action.setEnabled(sim_can_be_controlled)
        if hasattr(self, 'reset_py_sim_action'): self.reset_py_sim_action.setEnabled(sim_can_be_controlled)
        if hasattr(self, 'py_sim_ui_manager') and self.py_sim_ui_manager: self.py_sim_ui_manager._update_internal_controls_enabled_state()

    @pyqtSlot()
    def _update_zoom_to_selection_action_enable_state(self):
        if hasattr(self, 'zoom_to_selection_action'):
            has_selection = bool(self.scene.selectedItems())
            self.zoom_to_selection_action.setEnabled(has_selection)

    @pyqtSlot()
    def _update_align_distribute_actions_enable_state(self):
        selected_count = len(self.scene.selectedItems())
        can_align = selected_count >= 2
        if hasattr(self, 'align_actions'):
            for action in self.align_actions: action.setEnabled(can_align)
        can_distribute = selected_count >= 3
        if hasattr(self, 'distribute_actions'):
            for action in self.distribute_actions: action.setEnabled(can_distribute)

    @pyqtSlot(str, str)
    def _handle_state_renamed_inline(self, old_name: str, new_name: str):
        logger.debug(f"MainWindow: State renamed inline from '{old_name}' to '{new_name}'.")
        self._refresh_find_dialog_if_visible()
        if self.scene.selectedItems() and len(self.scene.selectedItems()) == 1 and \
           isinstance(self.scene.selectedItems()[0], GraphicsStateItem) and \
           self.scene.selectedItems()[0].text_label == new_name:
            self._update_properties_dock() 

    def connect_state_item_signals(self, state_item: GraphicsStateItem):
        if hasattr(state_item, 'signals') and hasattr(state_item.signals, 'textChangedViaInlineEdit'):
            try: state_item.signals.textChangedViaInlineEdit.disconnect(self._handle_state_renamed_inline)
            except TypeError: pass 
            state_item.signals.textChangedViaInlineEdit.connect(self._handle_state_renamed_inline)
            logger.debug(f"Connected rename signal for state: {state_item.text_label}")

    @pyqtSlot()
    def _refresh_find_dialog_if_visible(self):
        if self.find_item_dialog and not self.find_item_dialog.isHidden():
            logger.debug("Refreshing FindItemDialog list due to scene change.")
            self.find_item_dialog.refresh_list()

    @pyqtSlot(GraphicsStateItem, bool)
    def on_toggle_state_breakpoint(self, state_item: GraphicsStateItem, set_bp: bool):
        if not self.py_fsm_engine or not self.py_sim_active:
            QMessageBox.information(self, "Simulation Not Active", "Breakpoints can only be managed during an active Python simulation.")
            if self.sender() and isinstance(self.sender(), QAction):
                self.sender().setChecked(not set_bp) 
            return

        state_name = state_item.text_label
        action_text = ""
        if set_bp:
            self.py_fsm_engine.add_state_breakpoint(state_name)
            current_tooltip = state_item.toolTip()
            if "[BP]" not in current_tooltip:
                state_item.setToolTip(f"{current_tooltip}\n[Breakpoint Set]" if current_tooltip else f"State: {state_name}\n[Breakpoint Set]")
            action_text = f"Breakpoint SET for state: {state_name}"
        else:
            self.py_fsm_engine.remove_state_breakpoint(state_name)
            state_item.setToolTip(state_item.toolTip().replace("\n[Breakpoint Set]", ""))
            action_text = f"Breakpoint CLEARED for state: {state_name}"
        
        state_item.update() 
        
        if hasattr(self, 'py_sim_ui_manager') and self.py_sim_ui_manager:
            self.py_sim_ui_manager.append_to_action_log([action_text])
        logger.info(action_text)

    def log_message(self, level_str: str, message: str): 
        level = getattr(logging, level_str.upper(), logging.INFO)
        logger.log(level, message)

    @pyqtSlot()
    def on_show_find_item_dialog(self):
        if not self.find_item_dialog:
            self.find_item_dialog = FindItemDialog(parent=self, scene_ref=self.scene)
            self.find_item_dialog.item_selected_for_focus.connect(self.focus_on_item)
            self.scene.scene_content_changed_for_find.connect(self._refresh_find_dialog_if_visible)

        if self.find_item_dialog.isHidden():
            self.find_item_dialog.refresh_list() 
            self.find_item_dialog.show()
            self.find_item_dialog.raise_()
            self.find_item_dialog.activateWindow()
        else:
            self.find_item_dialog.activateWindow()
        
        if hasattr(self.find_item_dialog, 'search_input'):
            self.find_item_dialog.search_input.selectAll()
            self.find_item_dialog.search_input.setFocus()

if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    script_dir = os.path.dirname(os.path.abspath(__file__)); parent_dir_of_script = os.path.dirname(script_dir)
    if parent_dir_of_script not in sys.path: sys.path.insert(0, parent_dir_of_script)
    
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(STYLE_SHEET_GLOBAL)
    
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())            