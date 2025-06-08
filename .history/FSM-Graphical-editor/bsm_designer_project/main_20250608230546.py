# bsm_designer_project/main.py

import sys
import os

# --- BEGIN SYS.PATH MODIFICATION BLOCK (Option 2) ---
if __name__ == '__main__' and __package__ is None:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_script_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    import bsm_designer_project.main # Re-import self
    sys.exit(bsm_designer_project.main.main_entry_point())
# --- END SYS.PATH MODIFICATION BLOCK ---

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
    QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
    QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
    QFileDialog, QProgressBar, QTabWidget, QCheckBox, QActionGroup, QGraphicsItem,
    QGroupBox, QUndoStack, QUndoCommand, QStyle, QSizePolicy, QGraphicsLineItem,
    QToolButton, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent,
    QGraphicsSceneHoverEvent, QGraphicsTextItem, QGraphicsDropShadowEffect,
    QHeaderView, QTableWidget, QTableWidgetItem, QAbstractItemView
)

import pygraphviz as pgv

from .graphics_scene import DiagramScene, ZoomableView
from .graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from .undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
from .fsm_simulator import FSMSimulator, FSMError
from .ai_chatbot import AIChatbotManager, AIStatus, AIChatUIManager
from .dialogs import (MatlabSettingsDialog, FindItemDialog,SettingsDialog)
from .matlab_integration import MatlabConnection
from .settings_manager import SettingsManager

from . import config
from .config import (
    APP_VERSION, APP_NAME, FILE_EXTENSION, FILE_FILTER,
    FSM_TEMPLATES_BUILTIN, MIME_TYPE_BSM_TEMPLATE, DEFAULT_EXECUTION_ENV,
    APP_FONT_FAMILY, APP_FONT_SIZE_SMALL, APP_FONT_SIZE_STANDARD, APP_FONT_SIZE_EDITOR,
    DYNAMIC_UPDATE_COLORS_FROM_THEME, GET_CURRENT_STYLE_SHEET
)
from .ui_py_simulation_manager import PySimulationUIManager
from .ui_manager import UIManager
from .ide_manager import IDEManager
from .action_handlers import ActionHandler
from .resource_monitor import ResourceMonitorManager
from .snippet_manager import CustomSnippetManager

try:
    from .logging_setup import setup_global_logging
except ImportError:
    print("CRITICAL: logging_setup.py not found (relative import failed). Logging will be basic.")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

try:
    from . import resources_rc
    RESOURCES_AVAILABLE = True
except ImportError:
    RESOURCES_AVAILABLE = False
    print("WARNING: resources_rc.py not found (relative import failed). Icons and bundled files might be missing.")

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    RESOURCES_AVAILABLE = RESOURCES_AVAILABLE

    DEFAULT_PERSPECTIVES = { # Define this at class level or in __init__ before _init_perspectives
        "Design Focus": None,
        "Simulation Focus": None,
        "IDE Focus": None,
        "AI Focus": None,
    }
    DEFAULT_PERSPECTIVE_NAME = "Design Focus"


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
                self._update_dock_color_button_style(color_button, QColor(item_data.get('color', config.COLOR_ITEM_STATE_DEFAULT_BG)))
                color_button.clicked.connect(lambda: self._on_dock_color_button_clicked(color_button))
                self.properties_editor_layout.addRow("Color:", color_button)
                self._dock_property_editors['color_button'] = color_button
                color_button.setProperty("currentColorHex", QColor(item_data.get('color', config.COLOR_ITEM_STATE_DEFAULT_BG)).name())

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
                self._update_dock_color_button_style(color_button, QColor(item_data.get('color', config.COLOR_ITEM_TRANSITION_DEFAULT)))
                color_button.clicked.connect(lambda: self._on_dock_color_button_clicked(color_button))
                self.properties_editor_layout.addRow("Color:", color_button)
                self._dock_property_editors['color_button'] = color_button
                color_button.setProperty("currentColorHex", QColor(item_data.get('color', config.COLOR_ITEM_TRANSITION_DEFAULT)).name())

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
            self.properties_placeholder_label.setText(f"<i><b>{len(selected_items)} items selected.</b><br><span style='font-size:{APP_FONT_SIZE_SMALL}; color:{config.COLOR_TEXT_SECONDARY};'>Select a single item to edit properties.</span></i>")
            self.properties_editor_container.setVisible(False); self.properties_placeholder_label.setVisible(True); self.properties_edit_dialog_button.setEnabled(False)
        else: 
            self.properties_placeholder_label.setText(f"<i>No item selected.</i><br><span style='font-size:{APP_FONT_SIZE_SMALL}; color:{config.COLOR_TEXT_SECONDARY};'>Click an item or use tools to add elements.</span>")
            self.properties_editor_container.setVisible(False); self.properties_placeholder_label.setVisible(True); self.properties_edit_dialog_button.setEnabled(False)
        
        self.properties_apply_button.setEnabled(False)
        self.properties_revert_button.setEnabled(False)

    def _update_dock_color_button_style(self, button: QPushButton, color: QColor):
        luminance = color.lightnessF()
        text_color_name = config.COLOR_TEXT_ON_ACCENT if luminance < 0.5 else config.COLOR_TEXT_PRIMARY
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
                border: 1.5px solid {config.COLOR_ACCENT_PRIMARY};
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
                color_val = QColor(original_props.get('color', config.COLOR_ITEM_STATE_DEFAULT_BG))
                self._update_dock_color_button_style(self._dock_property_editors['color_button'], color_val)
                self._dock_property_editors['color_button'].setProperty("currentColorHex", color_val.name())
        
        elif current_item_type is GraphicsTransitionItem:
            if 'event' in self._dock_property_editors: self._dock_property_editors['event'].setText(original_props.get('event', ''))
            if 'condition' in self._dock_property_editors: self._dock_property_editors['condition'].setText(original_props.get('condition', ''))
            if 'color_button' in self._dock_property_editors:
                color_val = QColor(original_props.get('color', config.COLOR_ITEM_TRANSITION_DEFAULT))
                self._update_dock_color_button_style(self._dock_property_editors['color_button'], color_val)
                self._dock_property_editors['color_button'].setProperty("currentColorHex", color_val.name())

        elif current_item_type is GraphicsCommentItem:
            if 'text' in self._dock_property_editors: self._dock_property_editors['text'].setPlainText(original_props.get('text', ''))

        for editor in self._dock_property_editors.values():
            editor.blockSignals(False)

        self.properties_apply_button.setEnabled(False)
        self.properties_revert_button.setEnabled(False)
        self.log_message("INFO", "Properties in dock reverted to selection state.")

    def __init__(self):
        super().__init__()
        if not hasattr(QApplication.instance(), 'settings_manager'):
             QApplication.instance().settings_manager = SettingsManager(app_name=APP_NAME)
        self.settings_manager = QApplication.instance().settings_manager

        self._init_perspectives() # Initialize perspective attributes

        self.setWindowTitle(f"{APP_NAME} - Untitled") 

        self.current_file_path = None
        self.last_generated_model_path = None
        self.undo_stack = QUndoStack(self)
        
        self.custom_snippet_manager = CustomSnippetManager(app_name=APP_NAME)
        
        self.scene = DiagramScene(self.undo_stack, self, custom_snippet_manager=self.custom_snippet_manager) 
        self.view = ZoomableView(self.scene, self)

        self.ui_manager = UIManager(self)       
        self.action_handler = ActionHandler(self)
        self.resource_monitor_manager = ResourceMonitorManager(self, settings_manager=self.settings_manager) 
        
        self.matlab_connection = MatlabConnection()
        self.ai_chatbot_manager = AIChatbotManager(self) 
        self.py_sim_ui_manager = PySimulationUIManager(self)
        
        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False
        self.find_item_dialog: FindItemDialog | None = None
        
        self._current_edited_item_original_props_in_dock = {} 

        self.ui_manager.setup_ui() 
        self.ai_chat_ui_manager = AIChatUIManager(self) # Needs to be after ui_manager.setup_ui if it uses mw elements
        self.ide_manager = IDEManager(self) # Needs to be after ui_manager.setup_ui

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
        self._apply_initial_settings() # Includes perspective loading

        if self.settings_manager.get("resource_monitor_enabled"):
            if self.resource_monitor_manager: 
                self.resource_monitor_manager.setup_and_start_monitor()
                if self.resource_monitor_manager.worker:
                     self.resource_monitor_manager.worker.resourceUpdate.connect(self._update_resource_display)
                else:
                    logger.error("MainWindow: ResourceMonitorManager worker not available for signal connection post setup.")
        else:
            logger.info("Resource monitor disabled by settings.")
            if hasattr(self, 'cpu_status_label'): self.cpu_status_label.setVisible(False)
            if hasattr(self, 'ram_status_label'): self.ram_status_label.setVisible(False)
            if hasattr(self, 'gpu_status_label'): self.gpu_status_label.setVisible(False)

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
        
        # Define and apply default perspectives *after* all UI elements are created
        QTimer.singleShot(100, self._define_and_save_default_perspectives_if_needed)
        # QTimer.singleShot(150, lambda: self.apply_perspective_state(self.current_perspective_name)) # Now handled within _define_...

    # --- PERSPECTIVE MANAGEMENT (Copied from previous response) ---
    def _init_perspectives(self):
        self.current_perspective_name = self.settings_manager.get("gui_last_used_perspective", self.DEFAULT_PERSPECTIVE_NAME)
        self.perspectives_menu: QMenu | None = None # Will be created by UIManager
        self.perspective_action_group: QActionGroup | None = None # Will be created by UIManager
        logger.info(f"Initial perspective to load: {self.current_perspective_name}")

    def _define_and_save_default_perspectives_if_needed(self):
        logger.info("Checking and defining default perspectives if needed...")
        initial_load_perspective = self.current_perspective_name # Store the perspective we intend to load
        defined_any_new_default = False

        for name in self.DEFAULT_PERSPECTIVES.keys():
            setting_key = f"gui_perspective_{name}"
            if self.settings_manager.get(setting_key) is None:
                logger.info(f"Default perspective '{name}' not found in settings. Defining now.")
                self._arrange_ui_for_perspective(name) 
                state_bytes = self.saveState()
                if state_bytes:
                    self.settings_manager.set(setting_key, state_bytes.hex())
                    self.DEFAULT_PERSPECTIVES[name] = state_bytes 
                    defined_any_new_default = True
                    logger.info(f"Saved default state for perspective '{name}'.")
                else:
                    logger.warning(f"Could not save state for default perspective '{name}'.")
            else:
                if self.DEFAULT_PERSPECTIVES.get(name) is None: # Check if not already in memory cache
                    try:
                        state_hex = self.settings_manager.get(setting_key)
                        self.DEFAULT_PERSPECTIVES[name] = bytes.fromhex(state_hex)
                    except (TypeError, ValueError):
                        logger.error(f"Corrupted state for default perspective '{name}' in settings. Will attempt re-definition.")
                        self.settings_manager.set(setting_key, None)
                        self._arrange_ui_for_perspective(name)
                        state_bytes = self.saveState()
                        if state_bytes:
                            self.settings_manager.set(setting_key, state_bytes.hex())
                            self.DEFAULT_PERSPECTIVES[name] = state_bytes
                            defined_any_new_default = True
        
        if hasattr(self, '_create_perspective_menu'): # Rebuild menu if defaults were just defined
             self._create_perspective_menu()

        # Crucially, apply the intended perspective AFTER all defaults might have been defined
        QTimer.singleShot(0, lambda: self.apply_perspective_state(initial_load_perspective))


    def _arrange_ui_for_perspective(self, perspective_name: str):
        logger.debug(f"Arranging UI to define/apply layout for perspective: {perspective_name}")
        docks = {
            "elements": getattr(self, 'elements_palette_dock', None),
            "properties": getattr(self, 'properties_dock', None),
            "log": getattr(self, 'log_dock', None),
            "problems": getattr(self, 'problems_dock', None),
            "pysim": getattr(self, 'py_sim_dock', None),
            "ai": getattr(self, 'ai_chatbot_dock', None),
            "ide": getattr(self, 'ide_dock', None),
        }
        valid_docks = {name: dock for name, dock in docks.items() if dock is not None}

        for dock in valid_docks.values(): dock.setVisible(False)
        QApplication.processEvents()

        # Restore tabifications - this order MUST match how they are set up in UIManager._create_docks
        # or your _initial_ UI state that `saveState` would capture.
        if valid_docks.get("properties") and valid_docks.get("pysim"): self.tabifyDockWidget(valid_docks["properties"], valid_docks["pysim"])
        if valid_docks.get("pysim") and valid_docks.get("ai"): self.tabifyDockWidget(valid_docks["pysim"], valid_docks["ai"])
        if valid_docks.get("ai") and valid_docks.get("ide"): self.tabifyDockWidget(valid_docks["ai"], valid_docks["ide"])
        if valid_docks.get("log") and valid_docks.get("problems"): self.tabifyDockWidget(valid_docks["log"], valid_docks["problems"])

        if perspective_name == "Design Focus":
            if valid_docks.get("elements"): self.addDockWidget(Qt.LeftDockWidgetArea, valid_docks["elements"]); valid_docks["elements"].setVisible(True)
            if valid_docks.get("properties"): self.addDockWidget(Qt.RightDockWidgetArea, valid_docks["properties"]); valid_docks["properties"].setVisible(True); valid_docks["properties"].raise_()
            if valid_docks.get("problems"): self.addDockWidget(Qt.BottomDockWidgetArea, valid_docks["problems"]); valid_docks["problems"].setVisible(True)
            if valid_docks.get("log"): self.addDockWidget(Qt.BottomDockWidgetArea, valid_docks["log"]); valid_docks["log"].setVisible(True); valid_docks["problems"].raise_() # Problems on top of log
        
        elif perspective_name == "Simulation Focus":
            if valid_docks.get("pysim"): self.addDockWidget(Qt.RightDockWidgetArea, valid_docks["pysim"]); valid_docks["pysim"].setVisible(True); valid_docks["pysim"].raise_()
            if valid_docks.get("properties"): self.addDockWidget(Qt.RightDockWidgetArea, valid_docks["properties"]); valid_docks["properties"].setVisible(True) 
            if valid_docks.get("log"): self.addDockWidget(Qt.BottomDockWidgetArea, valid_docks["log"]); valid_docks["log"].setVisible(True); valid_docks["log"].raise_()
            if valid_docks.get("problems"): self.addDockWidget(Qt.BottomDockWidgetArea, valid_docks["problems"]); valid_docks["problems"].setVisible(False) # Usually hide problems in sim
        
        elif perspective_name == "IDE Focus":
            if valid_docks.get("ide"): self.addDockWidget(Qt.RightDockWidgetArea, valid_docks["ide"]); valid_docks["ide"].setVisible(True); valid_docks["ide"].raise_()
            if valid_docks.get("problems"): self.addDockWidget(Qt.BottomDockWidgetArea, valid_docks["problems"]); valid_docks["problems"].setVisible(True)
            if valid_docks.get("log"): self.addDockWidget(Qt.BottomDockWidgetArea, valid_docks["log"]); valid_docks["log"].setVisible(True); valid_docks["problems"].raise_()
        
        elif perspective_name == "AI Focus":
            if valid_docks.get("ai"): self.addDockWidget(Qt.RightDockWidgetArea, valid_docks["ai"]); valid_docks["ai"].setVisible(True); valid_docks["ai"].raise_()
            if valid_docks.get("log"): self.addDockWidget(Qt.BottomDockWidgetArea, valid_docks["log"]); valid_docks["log"].setVisible(True); valid_docks["log"].raise_()
        
        # Ensure all other defined docks are hidden if not explicitly set visible for this perspective
        # This loop might be redundant if the perspective logic above is comprehensive.
        active_perspective_docks = []
        if perspective_name == "Design Focus": active_perspective_docks = ["elements", "properties", "problems", "log"]
        elif perspective_name == "Simulation Focus": active_perspective_docks = ["pysim", "properties", "log", "problems"]
        elif perspective_name == "IDE Focus": active_perspective_docks = ["ide", "problems", "log"]
        elif perspective_name == "AI Focus": active_perspective_docks = ["ai", "log"]
        
        for dock_key, dock_widget in valid_docks.items():
            if dock_widget and dock_key not in active_perspective_docks:
                dock_widget.setVisible(False)

        QApplication.processEvents()

    def apply_perspective_state(self, perspective_name: str):
        logger.info(f"Applying perspective: {perspective_name}")
        state_bytes = None
        
        # Prioritize in-memory cache for defaults
        if perspective_name in self.DEFAULT_PERSPECTIVES and self.DEFAULT_PERSPECTIVES[perspective_name] is not None:
            state_bytes = self.DEFAULT_PERSPECTIVES[perspective_name]
            logger.debug(f"Using cached state for default perspective '{perspective_name}'.")
        else: # Custom perspective or default not yet cached
            state_hex = self.settings_manager.get(f"gui_perspective_{perspective_name}")
            if state_hex and isinstance(state_hex, str):
                try:
                    state_bytes = bytes.fromhex(state_hex)
                    logger.debug(f"Loaded state from settings for perspective '{perspective_name}'.")
                except ValueError:
                    logger.error(f"Corrupted perspective data (invalid hex) for '{perspective_name}'. Cannot apply.")
                    if perspective_name != self.DEFAULT_PERSPECTIVE_NAME: # Avoid infinite loop
                        QMessageBox.warning(self, "Layout Error", f"Layout data for '{perspective_name}' is corrupted. Reverting to default.")
                        self.apply_perspective_state(self.DEFAULT_PERSPECTIVE_NAME)
                    return
            elif perspective_name in self.DEFAULT_PERSPECTIVES:
                 # Default perspective but not in cache and not in settings (or corrupted)
                 logger.warning(f"Default perspective '{perspective_name}' data missing. Attempting to redefine and apply.")
                 self._define_and_save_default_perspectives_if_needed() # This will eventually call apply_perspective_state again
                 return # Avoid applying a potentially null state_bytes now

        if state_bytes:
            if self.restoreState(state_bytes):
                self.current_perspective_name = perspective_name
                # self.settings_manager.set("gui_last_used_perspective", perspective_name) # Save on exit
                self.log_message("INFO", f"Perspective '{perspective_name}' applied.")
                self._update_perspective_menu_checks()
            else:
                logger.warning(f"Failed to restore state for perspective: {perspective_name}. Forcing default layout.")
                if perspective_name != self.DEFAULT_PERSPECTIVE_NAME: # Avoid infinite loop
                    QMessageBox.warning(self, "Layout Error", f"Could not apply layout for '{perspective_name}'. Reverting to default.")
                    self.apply_perspective_state(self.DEFAULT_PERSPECTIVE_NAME)
        else:
            if perspective_name != self.DEFAULT_PERSPECTIVE_NAME: # If the missing one wasn't default
                logger.warning(f"Perspective '{perspective_name}' not found or data is null. Applying default.")
                self.apply_perspective_state(self.DEFAULT_PERSPECTIVE_NAME)
            else: # The default itself is missing, critical issue
                logger.error(f"CRITICAL: Default perspective '{self.DEFAULT_PERSPECTIVE_NAME}' data is missing and could not be defined.")
                QMessageBox.critical(self, "Critical Layout Error", "Default application layout is missing or corrupted. UI may be unstable.")


    def save_current_perspective_as(self):
        custom_perspective_names = self.settings_manager.get("gui_custom_perspective_names", [])
        name, ok = QInputDialog.getText(self, "Save Perspective", "Enter name for current layout:")
        if ok and name:
            clean_name = name.strip()
            if not clean_name: QMessageBox.warning(self, "Invalid Name", "Perspective name cannot be empty."); return
            if clean_name in self.DEFAULT_PERSPECTIVES: QMessageBox.warning(self, "Reserved Name", f"'{clean_name}' is a default perspective name and cannot be used."); return
            
            if clean_name in custom_perspective_names and clean_name != self.current_perspective_name : # Allow overwrite of existing custom, but not if renaming to itself
                reply = QMessageBox.question(self, "Overwrite Perspective?", f"A custom perspective named '{clean_name}' already exists. Overwrite it?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No: return

            state_bytes = self.saveState()
            if state_bytes:
                self.settings_manager.set(f"gui_perspective_{clean_name}", state_bytes.hex())
                if clean_name not in custom_perspective_names:
                    custom_perspective_names.append(clean_name)
                    self.settings_manager.set("gui_custom_perspective_names", custom_perspective_names)
                
                self.current_perspective_name = clean_name
                self._update_perspective_menu() 
                self.log_message("INFO", f"Saved current layout as perspective: '{clean_name}'.")
            else:
                self.log_message("ERROR", "Failed to save current window state for perspective."); QMessageBox.critical(self, "Error Saving Perspective", "Could not save the current layout.")

    def manage_perspectives_dialog(self):
        custom_perspective_names = list(self.settings_manager.get("gui_custom_perspective_names", [])) # Work with a copy
        if not custom_perspective_names:
            QMessageBox.information(self, "Manage Perspectives", "No custom perspectives to manage.")
            return

        dialog = QDialog(self); dialog.setWindowTitle("Manage Custom Perspectives"); dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog); list_widget = QListWidget(); list_widget.addItems(sorted(custom_perspective_names)); layout.addWidget(list_widget)
        btn_layout = QHBoxLayout(); rename_btn = QPushButton("Rename..."); delete_btn = QPushButton("Delete"); close_btn = QPushButton("Close")
        rename_btn.setIcon(get_standard_icon(QStyle.SP_FileLinkIcon, "Ren")); delete_btn.setIcon(get_standard_icon(QStyle.SP_TrashIcon, "Del"))
        btn_layout.addWidget(rename_btn); btn_layout.addWidget(delete_btn); btn_layout.addStretch(); btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        def on_rename():
            curr_item = list_widget.currentItem()
            if not curr_item: return
            old_name = curr_item.text()
            new_name, ok = QInputDialog.getText(dialog, "Rename Perspective", f"New name for '{old_name}':", QLineEdit.Normal, old_name)
            if ok and new_name:
                clean_new_name = new_name.strip()
                if not clean_new_name: QMessageBox.warning(dialog, "Invalid Name", "Perspective name cannot be empty."); return
                if clean_new_name == old_name: return
                if clean_new_name in self.DEFAULT_PERSPECTIVES or (clean_new_name in custom_perspective_names and clean_new_name != old_name) :
                    QMessageBox.warning(dialog, "Name Conflict", f"A perspective named '{clean_new_name}' already exists."); return
                
                old_key = f"gui_perspective_{old_name}"; new_key = f"gui_perspective_{clean_new_name}"
                data = self.settings_manager.get(old_key)
                if data:
                    self.settings_manager.set(new_key, data, save_immediately=False)
                    self.settings_manager.set(old_key, None, save_immediately=False) # Effectively remove
                    idx = custom_perspective_names.index(old_name); custom_perspective_names[idx] = clean_new_name
                    self.settings_manager.set("gui_custom_perspective_names", custom_perspective_names, save_immediately=True) # Save all changes
                    curr_item.setText(clean_new_name)
                    if self.current_perspective_name == old_name: self.current_perspective_name = clean_new_name
                    self._update_perspective_menu()
                    self.log_message("INFO", f"Renamed perspective '{old_name}' to '{clean_new_name}'.")

        def on_delete():
            curr_item = list_widget.currentItem()
            if not curr_item: return
            name_del = curr_item.text()
            reply = QMessageBox.question(dialog, "Delete Perspective", f"Delete '{name_del}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.settings_manager.set(f"gui_perspective_{name_del}", None, save_immediately=False)
                custom_perspective_names.remove(name_del)
                self.settings_manager.set("gui_custom_perspective_names", custom_perspective_names, save_immediately=True)
                list_widget.takeItem(list_widget.row(curr_item))
                if self.current_perspective_name == name_del:
                    self.current_perspective_name = self.DEFAULT_PERSPECTIVE_NAME
                    self.apply_perspective_state(self.current_perspective_name)
                self._update_perspective_menu()
                self.log_message("INFO", f"Deleted perspective '{name_del}'.")

        rename_btn.clicked.connect(on_rename); delete_btn.clicked.connect(on_delete); close_btn.clicked.connect(dialog.accept); list_widget.itemDoubleClicked.connect(on_rename)
        dialog.exec_()

    def _create_perspective_menu(self):
        if not hasattr(self, 'view_menu'): logger.error("Cannot create perspective menu: view_menu not found."); return
        if hasattr(self, 'perspectives_menu') and self.perspectives_menu: self.perspectives_menu.clear()
        else: self.perspectives_menu = QMenu("Perspectives", self); self.view_menu.addMenu(self.perspectives_menu)

        self.perspective_action_group = QActionGroup(self); self.perspective_action_group.setExclusive(True)

        for name in self.DEFAULT_PERSPECTIVES.keys():
            action = QAction(name, self, checkable=True)
            action.triggered.connect(lambda checked, p_name=name: self.apply_perspective_state(p_name) if checked else None)
            self.perspectives_menu.addAction(action); self.perspective_action_group.addAction(action); action.setData(name)

        custom_names = self.settings_manager.get("gui_custom_perspective_names", [])
        if custom_names:
            self.perspectives_menu.addSeparator()
            for name in sorted(custom_names):
                action = QAction(name, self, checkable=True)
                action.triggered.connect(lambda checked, p_name=name: self.apply_perspective_state(p_name) if checked else None)
                self.perspectives_menu.addAction(action); self.perspective_action_group.addAction(action); action.setData(name)
        
        self.perspectives_menu.addSeparator()
        save_as_action = self.perspectives_menu.addAction(get_standard_icon(QStyle.SP_DialogSaveButton), "Save Current As..."); save_as_action.triggered.connect(self.save_current_perspective_as)
        manage_action = self.perspectives_menu.addAction(get_standard_icon(QStyle.SP_FileDialogDetailedView), "Manage Custom..."); manage_action.triggered.connect(self.manage_perspectives_dialog)
        self.perspectives_menu.addSeparator()
        reset_layout_action = self.perspectives_menu.addAction(get_standard_icon(QStyle.SP_BrowserReload), "Reset Current Perspective"); reset_layout_action.triggered.connect(lambda: self.apply_perspective_state(self.current_perspective_name))
        self._update_perspective_menu_checks()

    def _update_perspective_menu_checks(self):
        if not hasattr(self, 'perspective_action_group') or not self.perspective_action_group: return
        for action in self.perspective_action_group.actions():
            action.setChecked(action.data() == self.current_perspective_name)

    # ... (rest of MainWindow methods: _apply_theme, _connect_signals, _apply_initial_settings, _handle_setting_changed, etc.) ...
    # ... (ensure _create_menus in UIManager calls self.mw._create_perspective_menu()) ...
    # ... (ensure calls to _init_perspectives and _define_and_save_default_perspectives_if_needed in __init__) ...
    # ... (ensure saving gui_last_used_perspective in closeEvent) ...

    def _apply_initial_settings(self):
        logger.debug("Applying initial settings from SettingsManager.")
        
        # Theme must be applied first as it affects default color values used by other settings
        initial_theme = self.settings_manager.get("appearance_theme")
        self._apply_theme(initial_theme) # This now updates config.* colors

        # Now apply other settings that might depend on themed colors
        if hasattr(self.scene, 'setBackgroundBrush'): # scene might not exist if called too early
            show_grid = self.settings_manager.get("view_show_grid")
            if hasattr(self, 'show_grid_action'): self.show_grid_action.setChecked(show_grid)
            
            self.scene.snap_to_grid_enabled = self.settings_manager.get("view_snap_to_grid")
            if hasattr(self, 'snap_to_grid_action'): self.snap_to_grid_action.setChecked(self.scene.snap_to_grid_enabled)

            self.scene.snap_to_objects_enabled = self.settings_manager.get("view_snap_to_objects")
            if hasattr(self, 'snap_to_objects_action'): self.snap_to_objects_action.setChecked(self.scene.snap_to_objects_enabled)

            self.scene._show_dynamic_snap_guidelines = self.settings_manager.get("view_show_snap_guidelines")
            if hasattr(self, 'show_snap_guidelines_action'): self.show_snap_guidelines_action.setChecked(self.scene._show_dynamic_snap_guidelines)
        
        self.scene.update() # Refresh scene with new grid colors etc.

        if self.resource_monitor_manager:
            if self.resource_monitor_manager.worker:
                interval = self.settings_manager.get("resource_monitor_interval_ms")
                self.resource_monitor_manager.worker.data_collection_interval_ms = interval
        
        self._update_window_title()
        # Perspective loading is handled by _define_and_save_default_perspectives_if_needed

    def closeEvent(self, event: QCloseEvent):
        logger.info("MW_CLOSE: closeEvent received.")
        if not self._prompt_ide_save_if_dirty(): event.ignore(); return
        if not self._prompt_save_if_dirty(): event.ignore(); return
        if hasattr(self, 'py_sim_ui_manager') and self.py_sim_ui_manager: self.py_sim_ui_manager.on_stop_py_simulation(silent=True)
        
        if self.internet_check_timer and self.internet_check_timer.isActive(): self.internet_check_timer.stop(); logger.info("MW_CLOSE: Internet check timer stopped.")
        if self.ai_chatbot_manager: self.ai_chatbot_manager.stop_chatbot(); logger.info("MW_CLOSE: AI Chatbot manager stopped.")
        
        if self.resource_monitor_manager: 
            self.resource_monitor_manager.stop_monitoring_system()
            # self.resource_monitor_manager = None # Don't nullify, might be needed if app isn't truly closing
            
        if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads: logging.info("MW_CLOSE: Closing application. %d MATLAB processes initiated by this session may still be running in the background if not completed.", len(self.matlab_connection._active_threads))
        
        app_temp_session_dir_name = f"BSMDesigner_Temp_{QApplication.applicationPid()}"; session_temp_dir_path = QDir(QDir.tempPath()).filePath(app_temp_session_dir_name)
        if QDir(session_temp_dir_path).exists():
            if QDir(session_temp_dir_path).removeRecursively(): logger.info(f"MW_CLOSE: Cleaned up session temporary directory: {session_temp_dir_path}")
            else: logger.warning(f"MW_CLOSE: Failed to clean up session temporary directory: {session_temp_dir_path}")

        # Save last used perspective BEFORE saving all settings
        self.settings_manager.set("gui_last_used_perspective", self.current_perspective_name, save_immediately=False)
        self.settings_manager.save_settings() # Ensure all pending settings, including last perspective, are saved

        logger.info("MW_CLOSE: Application closeEvent accepted.")
        event.accept()

    # All other MainWindow methods (_connect_signals, _apply_theme, etc.) remain the same as in your provided code.
    # Make sure that UIManager._create_menus calls self.mw._create_perspective_menu()

    # ... (rest of existing MainWindow methods as provided in the problem description) ...
    # ... _apply_theme, _connect_signals, _handle_setting_changed, _update_resource_display, etc. ...
    # ... _set_status_label_object_names, _update_ui_element_states, _update_save_actions_enable_state, etc. ...
    # ... _update_ide_save_actions_enable_state, _update_undo_redo_actions_enable_state, etc. ...
    # ... _update_matlab_status_display, _update_matlab_actions_enabled_state, etc. ...
    # ... _start_matlab_operation, _finish_matlab_operation, set_ui_enabled_for_matlab_op, etc. ...
    # ... _handle_matlab_modelgen_or_sim_finished, _handle_matlab_codegen_finished, etc. ...
    # ... _prompt_save_if_dirty, _prompt_ide_save_if_dirty, _load_from_path, _save_to_path, etc. ...
    # ... focus_on_item, on_matlab_settings, update_zoom_status_display, etc. ...
    # ... _handle_py_sim_state_changed_by_manager, _handle_py_sim_global_ui_enable_by_manager, etc. ...
    # ... update_problems_dock, on_problem_item_double_clicked, _on_ide_dirty_state_changed_by_manager, etc. ...
    # ... _on_ide_language_changed_by_manager, _update_window_title, _init_internet_status_check, etc. ...
    # ... _run_internet_check_job, _update_ai_features_enabled_state, _update_internet_status_display, etc. ...
    # ... _update_py_sim_status_display, _update_py_simulation_actions_enabled_state, etc. ...
    # ... _update_zoom_to_selection_action_enable_state, _update_align_distribute_actions_enable_state, etc. ...
    # ... _handle_state_renamed_inline, connect_state_item_signals, _refresh_find_dialog_if_visible, etc. ...
    # ... on_toggle_state_breakpoint, log_message, on_show_find_item_dialog, _add_fsm_data_to_scene etc. ...


def main_entry_point():
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    if not hasattr(QApplication.instance(), 'settings_manager'):
         QApplication.instance().settings_manager = SettingsManager(app_name=APP_NAME)
    
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    pass # Handled by the sys.path modification block at the top