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
# psutil and pynvml imports moved to resource_monitor.py

# --- Custom Modules ---
from graphics_scene import DiagramScene, ZoomableView
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
# CodeEditor import moved to ide_manager.py
from fsm_simulator import FSMSimulator, FSMError
from ai_chatbot import AIChatbotManager, AIStatus, AIChatUIManager # AIChatUIManager will be used by MainWindow
from dialogs import (MatlabSettingsDialog, FindItemDialog) # Other dialogs will be used by ActionHandler or other managers
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
    FSM_TEMPLATES_BUILTIN,MIME_TYPE_BSM_TEMPLATE, DEFAULT_EXECUTION_ENV # Added DEFAULT_EXECUTION_ENV
)
# from utils import get_standard_icon # UIManager and other managers will use this directly
from ui_py_simulation_manager import PySimulationUIManager
# c_code_generator import moved to action_handlers.py

# --- New Manager Imports ---
from ui_manager import UIManager
from ide_manager import IDEManager
from action_handlers import ActionHandler
from resource_monitor import ResourceMonitorManager


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
    RESOURCES_AVAILABLE = RESOURCES_AVAILABLE # Class attribute for utils._get_bundled_file_path

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - Untitled [*]")

        self.current_file_path = None
        self.last_generated_model_path = None # For MATLAB related flows
        self.undo_stack = QUndoStack(self)
        self.scene = DiagramScene(self.undo_stack, self)
        self.view = ZoomableView(self.scene, self) # Central widget is created by UIManager

        # --- Managers ---
        self.ui_manager = UIManager(self)
        self.action_handler = ActionHandler(self)
        # self.ide_manager = IDEManager(self) # MOVED - Initialized after UI setup
        self.resource_monitor_manager = ResourceMonitorManager(self)
        
        self.matlab_connection = MatlabConnection()
        self.ai_chatbot_manager = AIChatbotManager(self) 
        self.py_sim_ui_manager = PySimulationUIManager(self)
        self.ai_chat_ui_manager = AIChatUIManager(self) 

        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False

        self.find_item_dialog: FindItemDialog | None = None
        
        self.ui_manager.setup_ui() # Creates UI elements and assigns them to self.mw (which is self)

        # --- Initialize IDEManager AFTER UI setup ---
        self.ide_manager = IDEManager(self) # NOW ide_dock should exist

        # --- Properties Dock Specific Initialization ---
        self._current_edited_item_original_props_in_dock = {} 

        try:
            if not hasattr(self, 'log_output') or not self.log_output: # log_output created by UIManager
                self.log_output = QTextEdit() 
                logger.warning("MainWindow: log_output fallback used before logging setup.")
            setup_global_logging(self.log_output)
            logger.info("Main window initialized and logging configured.")
        except Exception as e:
            print(f"ERROR: Failed to run setup_global_logging: {e}. UI logs might not work.")
            if not logging.getLogger().hasHandlers():
                 logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

        # Populate docks whose content is managed by other UI managers
        self.ui_manager.populate_dynamic_docks() 
                                                 
        
        self._connect_signals()
        self.action_handler.connect_actions() 

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
            
        # Connect Properties Dock Buttons
        if hasattr(self, 'properties_apply_button'):
            self.properties_apply_button.clicked.connect(self._on_apply_dock_properties)
        if hasattr(self, 'properties_revert_button'):
            self.properties_revert_button.clicked.connect(self._on_revert_dock_properties)
        if hasattr(self, 'properties_edit_dialog_button'): # Already connected if done in UIManager, else connect here
            if not self.properties_edit_dialog_button.receivers(self.properties_edit_dialog_button.clicked): # Check if already connected
                self.properties_edit_dialog_button.clicked.connect(lambda: self.scene.edit_item_properties(self._current_edited_item_in_dock) if self._current_edited_item_in_dock else None)

    # ... (rest of _set_status_label_object_names, _update_ui_element_states, _update_save_actions_enable_state, _update_ide_save_actions_enable_state, _update_undo_redo_actions_enable_state, _update_matlab_status_display, _update_matlab_actions_enabled_state, _start_matlab_operation, _finish_matlab_operation, set_ui_enabled_for_matlab_op, _handle_matlab_modelgen_or_sim_finished, _handle_matlab_codegen_finished, _prompt_save_if_dirty, _prompt_ide_save_if_dirty, _load_from_path, _save_to_path, focus_on_item, on_matlab_settings, closeEvent, update_zoom_status_display, _update_resource_display, _handle_py_sim_state_changed_by_manager, _handle_py_sim_global_ui_enable_by_manager, update_problems_dock, on_problem_item_double_clicked, _on_ide_dirty_state_changed_by_manager, _on_ide_language_changed_by_manager, _update_window_title, _init_internet_status_check, _run_internet_check_job, _update_ai_features_enabled_state, _update_internet_status_display, _update_py_sim_status_display, _update_py_simulation_actions_enabled_state, _update_zoom_to_selection_action_enable_state, _update_align_distribute_actions_enable_state methods remain largely the same)

    # --- Properties Dock Logic ---
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
        new_props_from_dock = old_props_full.copy() # Start with a copy of old to fill in

        item_type_changed = False
        if isinstance(self._current_edited_item_in_dock, GraphicsStateItem):
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

        elif isinstance(self._current_edited_item_in_dock, GraphicsTransitionItem):
            if 'event' in self._dock_property_editors: new_props_from_dock['event'] = self._dock_property_editors['event'].text().strip()
            if 'condition' in self._dock_property_editors: new_props_from_dock['condition'] = self._dock_property_editors['condition'].text().strip()
            if 'color_button' in self._dock_property_editors: new_props_from_dock['color'] = self._dock_property_editors['color_button'].property("currentColorHex")
        
        elif isinstance(self._current_edited_item_in_dock, GraphicsCommentItem):
            if 'text' in self._dock_property_editors: new_props_from_dock['text'] = self._dock_property_editors['text'].toPlainText().strip()
        
        # Compare only relevant editable fields to see if something actually changed
        # This is a simplified check; ideally compare all fields present in _dock_property_editors
        changed_in_dock = False
        for key in self._dock_property_editors.keys():
            prop_key_in_data = key
            if key == 'color_button': prop_key_in_data = 'color' # Map UI key to data key
            
            new_val = None
            old_val = old_props_full.get(prop_key_in_data)

            if isinstance(self._dock_property_editors[key], QLineEdit): new_val = self._dock_property_editors[key].text().strip()
            elif isinstance(self._dock_property_editors[key], QTextEdit): new_val = self._dock_property_editors[key].toPlainText().strip()
            elif isinstance(self._dock_property_editors[key], QCheckBox): new_val = self._dock_property_editors[key].isChecked()
            elif key == 'color_button': new_val = self._dock_property_editors[key].property("currentColorHex")
            
            if new_val is not None and new_val != old_val:
                changed_in_dock = True
                break
        
        if not changed_in_dock:
            logger.info("Properties in dock are identical to original, no changes applied.")
            self.properties_apply_button.setEnabled(False)
            self.properties_revert_button.setEnabled(False)
            return

        cmd = EditItemPropertiesCommand(self._current_edited_item_in_dock, old_props_full, new_props_from_dock, f"Edit Properties via Dock")
        self.undo_stack.push(cmd) # This will trigger redo, which applies props and validates
        
        # After applying, store the new state as the "original" for subsequent reverts from the dock
        if hasattr(self._current_edited_item_in_dock, 'get_data'):
            self._current_edited_item_original_props_in_dock = self._current_edited_item_in_dock.get_data().copy()

        self.properties_apply_button.setEnabled(False)
        self.properties_revert_button.setEnabled(False)
        item_name = new_props_from_dock.get('name', new_props_from_dock.get('event', new_props_from_dock.get('text', 'Item')))
        self.log_message("INFO", f"Properties updated via dock for: {item_name}")


    @pyqtSlot()
    def _on_revert_dock_properties(self):
        if not self._current_edited_item_in_dock or not self._dock_property_editors or not self._current_edited_item_original_props_in_dock:
            logger.warning("RevertDockProperties: No item, editors, or original props to revert.")
            return

        original_props = self._current_edited_item_original_props_in_dock

        if isinstance(self._current_edited_item_in_dock, GraphicsStateItem):
            if 'name' in self._dock_property_editors: self._dock_property_editors['name'].setText(original_props.get('name', ''))
            if 'is_initial' in self._dock_property_editors: self._dock_property_editors['is_initial'].setChecked(original_props.get('is_initial', False))
            if 'is_final' in self._dock_property_editors: self._dock_property_editors['is_final'].setChecked(original_props.get('is_final', False))
            if 'is_superstate' in self._dock_property_editors: self._dock_property_editors['is_superstate'].setChecked(original_props.get('is_superstate', False))
            if 'color_button' in self._dock_property_editors:
                color_val = QColor(original_props.get('color', COLOR_ITEM_STATE_DEFAULT_BG))
                self._update_dock_color_button_style(self._dock_property_editors['color_button'], color_val)
                self._dock_property_editors['color_button'].setProperty("currentColorHex", color_val.name())
        
        elif isinstance(self._current_edited_item_in_dock, GraphicsTransitionItem):
            if 'event' in self._dock_property_editors: self._dock_property_editors['event'].setText(original_props.get('event', ''))
            if 'condition' in self._dock_property_editors: self._dock_property_editors['condition'].setText(original_props.get('condition', ''))
            if 'color_button' in self._dock_property_editors:
                color_val = QColor(original_props.get('color', COLOR_ITEM_TRANSITION_DEFAULT))
                self._update_dock_color_button_style(self._dock_property_editors['color_button'], color_val)
                self._dock_property_editors['color_button'].setProperty("currentColorHex", color_val.name())

        elif isinstance(self._current_edited_item_in_dock, GraphicsCommentItem):
            if 'text' in self._dock_property_editors: self._dock_property_editors['text'].setPlainText(original_props.get('text', ''))

        self.properties_apply_button.setEnabled(False)
        self.properties_revert_button.setEnabled(False)
        self.log_message("INFO", "Properties in dock reverted to selection state.")
    
    # --- END Properties Dock Logic ---


    @pyqtSlot(str, str)
    def _handle_state_renamed_inline(self, old_name: str, new_name: str):
        logger.debug(f"MainWindow: State renamed inline from '{old_name}' to '{new_name}'.")
        self._refresh_find_dialog_if_visible()
        if self.scene.selectedItems() and len(self.scene.selectedItems()) == 1 and \
           isinstance(self.scene.selectedItems()[0], GraphicsStateItem) and \
           self.scene.selectedItems()[0].text_label == new_name:
            self._update_properties_dock() # Refresh dock if the renamed item is the one being shown

    def connect_state_item_signals(self, state_item: GraphicsStateItem):
        if hasattr(state_item, 'signals') and hasattr(state_item.signals, 'textChangedViaInlineEdit'):
            try: state_item.signals.textChangedViaInlineEdit.disconnect(self._handle_state_renamed_inline)
            except TypeError: pass # Raised if not connected
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
            # If the action was triggered from a menu, toggle it back
            if self.sender() and isinstance(self.sender(), QAction):
                self.sender().setChecked(not set_bp) # Revert check state
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
        
        state_item.update() # To reflect any visual change related to breakpoint (if any in future)
        
        # Log to PySim dock if available
        if hasattr(self, 'py_sim_ui_manager') and self.py_sim_ui_manager:
            self.py_sim_ui_manager.append_to_action_log([action_text])
        logger.info(action_text)


    def log_message(self, level_str: str, message: str): # Centralized logging
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
    # ... (main execution block remains the same)
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