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

    DEFAULT_PERSPECTIVES = {
        "Design Focus": None,
        "Simulation Focus": None,
        "IDE Focus": None,
        "AI Focus": None,
    }
    DEFAULT_PERSPECTIVE_NAME = "Design Focus"

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
        self._dock_property_editors = {} # Initialize this attribute here

        self.ui_manager.setup_ui() # This creates menus, toolbars, docks
        self.ai_chat_ui_manager = AIChatUIManager(self)
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
        self._apply_initial_settings() # Includes theme and perspective loading

        # Ensure perspective menu is created if UIManager doesn't do it by default
        if not hasattr(self, 'perspectives_menu') or self.perspectives_menu is None:
            self._create_perspective_menu() # Call it directly if ui_manager doesn't

        # Define and apply default perspectives *after* all UI elements are created
        QTimer.singleShot(100, self._define_and_save_default_perspectives_if_needed)


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


    # --- PERSPECTIVE MANAGEMENT ---
    def _init_perspectives(self):
        self.current_perspective_name = self.settings_manager.get("gui_last_used_perspective", self.DEFAULT_PERSPECTIVE_NAME)
        self.perspectives_menu: QMenu | None = None
        self.perspective_action_group: QActionGroup | None = None
        logger.info(f"Initial perspective to load: {self.current_perspective_name}")

    def _define_and_save_default_perspectives_if_needed(self):
        logger.info("Checking and defining default perspectives if needed...")
        initial_load_perspective = self.current_perspective_name
        defined_any_new_default = False

        for name in self.DEFAULT_PERSPECTIVES.keys():
            setting_key = f"gui_perspective_{name}"
            # Check if the perspective state is already cached in memory
            if self.DEFAULT_PERSPECTIVES.get(name) is None:
                state_hex = self.settings_manager.get(setting_key)
                if state_hex and isinstance(state_hex, str):
                    try:
                        self.DEFAULT_PERSPECTIVES[name] = bytes.fromhex(state_hex)
                        logger.debug(f"Loaded default perspective '{name}' from settings into memory cache.")
                    except (TypeError, ValueError):
                        logger.error(f"Corrupted state for default perspective '{name}' in settings. Will redefine.")
                        self.settings_manager.set(setting_key, None) # Clear bad setting
                        # Fall through to redefine
                
                # If still None (either not in settings or corrupted and cleared)
                if self.DEFAULT_PERSPECTIVES.get(name) is None:
                    logger.info(f"Default perspective '{name}' not found/cached. Defining now.")
                    self._arrange_ui_for_perspective(name)
                    state_bytes = self.saveState()
                    if state_bytes:
                        self.settings_manager.set(setting_key, state_bytes.hex())
                        self.DEFAULT_PERSPECTIVES[name] = state_bytes
                        defined_any_new_default = True
                        logger.info(f"Saved default state for perspective '{name}'.")
                    else:
                        logger.warning(f"Could not save state for default perspective '{name}'.")
        
        if defined_any_new_default or not hasattr(self, 'perspectives_menu') or not self.perspectives_menu.actions():
             if hasattr(self, '_create_perspective_menu'): self._create_perspective_menu()

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

        # Make all docks floating temporarily to break existing tab groups and areas cleanly
        # Store original floating states to restore later if needed for non-perspective changes
        original_floating_states = {name: dock.isFloating() for name, dock in valid_docks.items()}
        for dock in valid_docks.values():
            dock.setFloating(True) # Break out of current areas/tabs
        QApplication.processEvents() # Allow UI to process floating

        # Now, hide all (they are floating so hiding is simpler)
        for dock in valid_docks.values():
            dock.setVisible(False)
        QApplication.processEvents()

        # Define areas and tabify (MUST match initial setup in UIManager if you want consistency)
        if valid_docks.get("properties") and valid_docks.get("pysim"): self.tabifyDockWidget(valid_docks["properties"], valid_docks["pysim"])
        if valid_docks.get("pysim") and valid_docks.get("ai"): self.tabifyDockWidget(valid_docks["pysim"], valid_docks["ai"])
        if valid_docks.get("ai") and valid_docks.get("ide"): self.tabifyDockWidget(valid_docks["ai"], valid_docks["ide"])
        if valid_docks.get("log") and valid_docks.get("problems"): self.tabifyDockWidget(valid_docks["log"], valid_docks["problems"])

        # Restore floating state to False before adding to dock areas
        for name, dock in valid_docks.items():
            dock.setFloating(False) 
        QApplication.processEvents()


        active_perspective_docks_config = {
            "Design Focus": {"elements": Qt.LeftDockWidgetArea, "properties": Qt.RightDockWidgetArea, "problems": Qt.BottomDockWidgetArea, "log": Qt.BottomDockWidgetArea},
            "Simulation Focus": {"pysim": Qt.RightDockWidgetArea, "properties": Qt.RightDockWidgetArea, "log": Qt.BottomDockWidgetArea, "problems": Qt.BottomDockWidgetArea},
            "IDE Focus": {"ide": Qt.RightDockWidgetArea, "problems": Qt.BottomDockWidgetArea, "log": Qt.BottomDockWidgetArea},
            "AI Focus": {"ai": Qt.RightDockWidgetArea, "log": Qt.BottomDockWidgetArea}
        }
        
        docks_to_show_and_area = active_perspective_docks_config.get(perspective_name, {})
        raised_dock_in_perspective = { # Which dock to raise_() in its tab group
            "Design Focus": "properties", "Simulation Focus": "pysim", "IDE Focus": "ide", "AI Focus": "ai"
        }.get(perspective_name)


        for dock_name, area in docks_to_show_and_area.items():
            if valid_docks.get(dock_name):
                self.addDockWidget(area, valid_docks[dock_name])
                valid_docks[dock_name].setVisible(True)
        
        if raised_dock_in_perspective and valid_docks.get(raised_dock_in_perspective):
            valid_docks[raised_dock_in_perspective].raise_()
        elif perspective_name == "Design Focus" and valid_docks.get("problems") and valid_docks.get("log"): # Special case for Design Focus
             valid_docks["problems"].raise_() # Problems on top of Log

        # Ensure any docks not in the perspective's config are hidden
        for name, dock in valid_docks.items():
            if name not in docks_to_show_and_area:
                dock.setVisible(False)
        
        QApplication.processEvents()


    def apply_perspective_state(self, perspective_name: str):
        logger.info(f"Applying perspective: {perspective_name}")
        state_bytes = None
        
        if perspective_name in self.DEFAULT_PERSPECTIVES and self.DEFAULT_PERSPECTIVES[perspective_name] is not None:
            state_bytes = self.DEFAULT_PERSPECTIVES[perspective_name]
        else:
            state_hex = self.settings_manager.get(f"gui_perspective_{perspective_name}")
            if state_hex and isinstance(state_hex, str):
                try: state_bytes = bytes.fromhex(state_hex)
                except ValueError:
                    logger.error(f"Corrupted perspective data for '{perspective_name}'. Applying default.")
                    if perspective_name != self.DEFAULT_PERSPECTIVE_NAME: self.apply_perspective_state(self.DEFAULT_PERSPECTIVE_NAME)
                    return
            elif perspective_name in self.DEFAULT_PERSPECTIVES: # Is a default, but not cached and not in settings (needs definition)
                logger.warning(f"Default perspective '{perspective_name}' data not found. Attempting to define and apply.")
                self._define_and_save_default_perspectives_if_needed() # This will eventually re-call apply_perspective_state
                return


        if state_bytes:
            if self.restoreState(state_bytes):
                self.current_perspective_name = perspective_name
                self.log_message("INFO", f"Perspective '{perspective_name}' applied.")
                self._update_perspective_menu_checks()
            else:
                logger.warning(f"Failed to restore state for perspective: {perspective_name}. Arranging manually.")
                self._arrange_ui_for_perspective(perspective_name) # Fallback to manual arrangement
                self.current_perspective_name = perspective_name
                self._update_perspective_menu_checks()
        else:
            if perspective_name != self.DEFAULT_PERSPECTIVE_NAME:
                logger.warning(f"Perspective '{perspective_name}' not found. Applying default.")
                self.apply_perspective_state(self.DEFAULT_PERSPECTIVE_NAME)
            else:
                logger.error(f"CRITICAL: Default perspective '{self.DEFAULT_PERSPECTIVE_NAME}' data is missing. Arranging manually.")
                self._arrange_ui_for_perspective(self.DEFAULT_PERSPECTIVE_NAME) # Ensure at least default is applied

    def save_current_perspective_as(self):
        custom_perspective_names = self.settings_manager.get("gui_custom_perspective_names", [])
        name, ok = QInputDialog.getText(self, "Save Perspective", "Enter name for current layout:")
        if ok and name:
            clean_name = name.strip()
            if not clean_name: QMessageBox.warning(self, "Invalid Name", "Perspective name cannot be empty."); return
            if clean_name in self.DEFAULT_PERSPECTIVES: QMessageBox.warning(self, "Reserved Name", f"'{clean_name}' is a default perspective name and cannot be used."); return
            
            if clean_name in custom_perspective_names and clean_name != self.current_perspective_name :
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
        custom_perspective_names = list(self.settings_manager.get("gui_custom_perspective_names", []))
        if not custom_perspective_names:
            QMessageBox.information(self, "Manage Perspectives", "No custom perspectives to manage.")
            return

        dialog = QDialog(self); dialog.setWindowTitle("Manage Custom Perspectives"); dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog); list_widget = QListWidget(); list_widget.addItems(sorted(custom_perspective_names)); layout.addWidget(list_widget)
        btn_layout = QHBoxLayout(); rename_btn = QPushButton("Rename..."); delete_btn = QPushButton("Delete"); close_btn = QPushButton("Close")
        rename_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileLinkIcon)); delete_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_TrashIcon))
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
                    self.settings_manager.set(old_key, None, save_immediately=False)
                    idx = custom_perspective_names.index(old_name); custom_perspective_names[idx] = clean_new_name
                    self.settings_manager.set("gui_custom_perspective_names", custom_perspective_names, save_immediately=True)
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
        
        # Remove old menu if it exists, to allow rebuilding
        if hasattr(self, 'perspectives_menu') and self.perspectives_menu:
            self.view_menu.removeAction(self.perspectives_menu.menuAction())
            self.perspectives_menu.deleteLater()
            self.perspectives_menu = None
            self.perspective_action_group = None

        self.perspectives_menu = QMenu("Perspectives", self)
        
        # Check if view_menu has a separator for "Toolbars" and add "Perspectives" before it
        target_action_for_insertion = None
        if hasattr(self, 'toolbars_menu') and self.toolbars_menu: # UIManager creates toolbars_menu
            target_action_for_insertion = self.toolbars_menu.menuAction()
        
        if target_action_for_insertion:
            self.view_menu.insertMenu(target_action_for_insertion, self.perspectives_menu)
            self.view_menu.insertSeparator(target_action_for_insertion) # Add a separator before toolbars
        else: # Fallback, add at the end
            self.view_menu.addSeparator()
            self.view_menu.addMenu(self.perspectives_menu)


        self.perspective_action_group = QActionGroup(self); self.perspective_action_group.setExclusive(True)

        for name in self.DEFAULT_PERSPECTIVES.keys():
            action = QAction(name, self, checkable=True)
            # Use a partial or lambda that captures the current p_name
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
        save_as_action = self.perspectives_menu.addAction(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton), "Save Current As..."); save_as_action.triggered.connect(self.save_current_perspective_as)
        manage_action = self.perspectives_menu.addAction(QApplication.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Manage Custom..."); manage_action.triggered.connect(self.manage_perspectives_dialog)
        self.perspectives_menu.addSeparator()
        reset_layout_action = self.perspectives_menu.addAction(QApplication.style().standardIcon(QStyle.SP_BrowserReload), "Reset Current Perspective"); reset_layout_action.triggered.connect(lambda: self.apply_perspective_state(self.current_perspective_name))
        self._update_perspective_menu_checks()

    def _update_perspective_menu(self): # Just calls create to rebuild
        if hasattr(self, '_create_perspective_menu'):
            self._create_perspective_menu()

    def _update_perspective_menu_checks(self):
        if not hasattr(self, 'perspective_action_group') or not self.perspective_action_group: return
        for action in self.perspective_action_group.actions():
            action.setChecked(action.data() == self.current_perspective_name)

    # --- (Rest of MainWindow methods as before) ---
    def _apply_theme(self, theme_name: str):
        logger.info(f"Applying theme: {theme_name}")
        DYNAMIC_UPDATE_COLORS_FROM_THEME(theme_name)
        if hasattr(self, 'scene') and self.scene:
            self.scene.setBackgroundBrush(QColor(config.COLOR_BACKGROUND_LIGHT))
            self.scene.grid_pen_light = QPen(QColor(config.COLOR_GRID_MINOR), 0.7, Qt.DotLine)
            self.scene.grid_pen_dark = QPen(QColor(config.COLOR_GRID_MAJOR), 0.9, Qt.SolidLine)
            self.scene._guideline_pen = QPen(QColor(config.COLOR_SNAP_GUIDELINE), config.GUIDELINE_PEN_WIDTH, Qt.DashLine)
            self.scene.update()
        new_stylesheet = GET_CURRENT_STYLE_SHEET()
        app_instance = QApplication.instance()
        if app_instance: app_instance.setStyleSheet(new_stylesheet)
        else: logger.error("Cannot apply theme: QApplication instance not found."); return
        self.update(); self.repaint()
        all_widgets = self.findChildren(QWidget)
        if self.menuBar(): all_widgets.append(self.menuBar())
        if self.statusBar(): all_widgets.append(self.statusBar())
        for child_widget in all_widgets:
            if child_widget:
                child_widget.style().unpolish(child_widget)
                child_widget.style().polish(child_widget)
                child_widget.update()
        if app_instance: app_instance.processEvents()
        logger.info(f"Theme '{theme_name}' applied and UI refreshed.")

    def _connect_signals(self):
        self.scene.selectionChanged.connect(self._update_zoom_to_selection_action_enable_state)
        self.scene.selectionChanged.connect(self._update_align_distribute_actions_enable_state)
        self.scene.selectionChanged.connect(self._update_properties_dock)
        self.scene.scene_content_changed_for_find.connect(self._refresh_find_dialog_if_visible)
        self.scene.modifiedStatusChanged.connect(self.setWindowModified)
        self.scene.modifiedStatusChanged.connect(self._update_window_title)
        self.scene.validation_issues_updated.connect(self.update_problems_dock)
        self.settings_manager.settingChanged.connect(self._handle_setting_changed)
        if hasattr(self, 'view') and self.view: self.view.zoomChanged.connect(self.update_zoom_status_display)
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
        if hasattr(self, 'properties_apply_button'): self.properties_apply_button.clicked.connect(self._on_apply_dock_properties)
        if hasattr(self, 'properties_revert_button'): self.properties_revert_button.clicked.connect(self._on_revert_dock_properties)
        if hasattr(self, 'properties_edit_dialog_button'):
            try: self.properties_edit_dialog_button.clicked.disconnect()
            except TypeError: pass
            self.properties_edit_dialog_button.clicked.connect(lambda: self.scene.edit_item_properties(self._current_edited_item_in_dock) if self._current_edited_item_in_dock else None)

    def _apply_initial_settings(self):
        logger.debug("Applying initial settings from SettingsManager.")
        initial_theme = self.settings_manager.get("appearance_theme")
        self._apply_theme(initial_theme)
        if hasattr(self.scene, 'setBackgroundBrush'):
            show_grid = self.settings_manager.get("view_show_grid")
            if hasattr(self, 'show_grid_action'): self.show_grid_action.setChecked(show_grid)
            self.scene.snap_to_grid_enabled = self.settings_manager.get("view_snap_to_grid")
            if hasattr(self, 'snap_to_grid_action'): self.snap_to_grid_action.setChecked(self.scene.snap_to_grid_enabled)
            self.scene.snap_to_objects_enabled = self.settings_manager.get("view_snap_to_objects")
            if hasattr(self, 'snap_to_objects_action'): self.snap_to_objects_action.setChecked(self.scene.snap_to_objects_enabled)
            self.scene._show_dynamic_snap_guidelines = self.settings_manager.get("view_show_snap_guidelines")
            if hasattr(self, 'show_snap_guidelines_action'): self.show_snap_guidelines_action.setChecked(self.scene._show_dynamic_snap_guidelines)
        self.scene.update()
        if self.resource_monitor_manager and self.resource_monitor_manager.worker:
            interval = self.settings_manager.get("resource_monitor_interval_ms")
            self.resource_monitor_manager.worker.data_collection_interval_ms = interval
        self._update_window_title()

    @pyqtSlot(str, object)
    def _handle_setting_changed(self, key: str, value: object):
        logger.info(f"Setting '{key}' changed to '{value}'. Updating UI.")
        theme_related_change = False
        if key == "appearance_theme":
            self._apply_theme(str(value))
            theme_related_change = True
            QTimer.singleShot(100, lambda: QMessageBox.information(self, "Theme Changed", "Application restart may be required for the theme to apply to all elements fully."))
        elif key in ["canvas_grid_minor_color", "canvas_grid_major_color", "canvas_snap_guideline_color"]:
            current_theme = self.settings_manager.get("appearance_theme")
            DYNAMIC_UPDATE_COLORS_FROM_THEME(current_theme)
            theme_related_change = True
            if self.scene: self.scene.update()
        if theme_related_change and key != "appearance_theme":
            new_stylesheet = GET_CURRENT_STYLE_SHEET()
            app_instance = QApplication.instance()
            if app_instance: app_instance.setStyleSheet(new_stylesheet)
            self.update(); self.repaint()
            for child_widget in self.findChildren(QWidget):
                if child_widget: child_widget.style().unpolish(child_widget); child_widget.style().polish(child_widget); child_widget.update()
            if app_instance: app_instance.processEvents()
        if key == "view_show_grid":
            if hasattr(self, 'show_grid_action'): self.show_grid_action.setChecked(bool(value))
            if self.scene: self.scene.update()
        elif key == "view_snap_to_grid":
            if self.scene: self.scene.snap_to_grid_enabled = bool(value)
            if hasattr(self, 'snap_to_grid_action'): self.snap_to_grid_action.setChecked(bool(value))
        elif key == "view_snap_to_objects":
            if self.scene: self.scene.snap_to_objects_enabled = bool(value)
            if hasattr(self, 'snap_to_objects_action'): self.snap_to_objects_action.setChecked(bool(value))
        elif key == "view_show_snap_guidelines":
            if self.scene:
                self.scene._show_dynamic_snap_guidelines = bool(value)
                if not bool(value): self.scene._clear_dynamic_guidelines()
                self.scene.update()
            if hasattr(self, 'show_snap_guidelines_action'): self.show_snap_guidelines_action.setChecked(bool(value))
        elif key == "resource_monitor_enabled":
            is_enabled = bool(value)
            if hasattr(self, 'cpu_status_label'): self.cpu_status_label.setVisible(is_enabled)
            if hasattr(self, 'ram_status_label'): self.ram_status_label.setVisible(is_enabled)
            if hasattr(self, 'gpu_status_label'): self.gpu_status_label.setVisible(is_enabled)
            if self.resource_monitor_manager:
                if is_enabled and (not self.resource_monitor_manager.thread or not self.resource_monitor_manager.thread.isRunning()):
                    self.resource_monitor_manager.setup_and_start_monitor()
                    if self.resource_monitor_manager.worker:
                        try: self.resource_monitor_manager.worker.resourceUpdate.disconnect(self._update_resource_display)
                        except TypeError: pass
                        self.resource_monitor_manager.worker.resourceUpdate.connect(self._update_resource_display)
                elif not is_enabled and self.resource_monitor_manager.thread and self.resource_monitor_manager.thread.isRunning():
                    self.resource_monitor_manager.stop_monitoring_system()
        elif key == "resource_monitor_interval_ms":
            if self.resource_monitor_manager and self.resource_monitor_manager.worker:
                self.resource_monitor_manager.worker.data_collection_interval_ms = int(value)
                logger.info(f"Resource monitor interval set to {value} ms.")
        self._update_window_title()

    @pyqtSlot()
    def on_show_preferences_dialog(self):
        dialog = SettingsDialog(self.settings_manager, self)
        dialog.exec_()
        logger.info("Preferences dialog closed.")

    @pyqtSlot(float, float, float, str)
    def _update_resource_display(self, cpu_usage, ram_usage, gpu_util, gpu_name):
        if hasattr(self, 'cpu_status_label'): self.cpu_status_label.setText(f"CPU: {cpu_usage:.0f}%")
        if hasattr(self, 'ram_status_label'): self.ram_status_label.setText(f"RAM: {ram_usage:.0f}%")
        if hasattr(self, 'gpu_status_label'):
            if gpu_util == -1.0: self.gpu_status_label.setText(f"GPU: {gpu_name}")
            elif gpu_util == -2.0: self.gpu_status_label.setText(f"GPU: NVML Err")
            elif gpu_util == -3.0: self.gpu_status_label.setText(f"GPU: Mon Err")
            elif self.resource_monitor_manager and self.resource_monitor_manager.worker and self.resource_monitor_manager.worker._nvml_initialized and self.resource_monitor_manager.worker._gpu_handle:
                self.gpu_status_label.setText(f"GPU: {gpu_util:.0f}%"); self.gpu_status_label.setToolTip(f"GPU: {gpu_util:.0f}% ({gpu_name})")
            else: self.gpu_status_label.setText(f"GPU: N/A"); self.gpu_status_label.setToolTip(gpu_name)

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
        if hasattr(self, 'view') and self.view: self.update_zoom_status_display(self.view.transform().m11())

    def _update_save_actions_enable_state(self):
        if hasattr(self, 'save_action'): self.save_action.setEnabled(self.scene.is_dirty())

    def _update_ide_save_actions_enable_state(self):
        if self.ide_manager: self.ide_manager.update_ide_save_actions_enable_state()

    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo()); self.redo_action.setEnabled(self.undo_stack.canRedo())
        undo_text = self.undo_stack.undoText(); redo_text = self.undo_stack.redoText()
        self.undo_action.setText(f"&Undo{(' ' + undo_text) if undo_text else ''}"); self.redo_action.setText(f"&Redo{(' ' + redo_text) if redo_text else ''}")
        self.undo_action.setToolTip(f"Undo: {undo_text}" if undo_text else "Undo"); self.redo_action.setToolTip(f"Redo: {redo_text}" if redo_text else "Redo")

    def _update_matlab_status_display(self, connected, message):
        status_text = f"MATLAB: {'Connected' if connected else 'Not Connected'}"; tooltip_text = f"MATLAB Status: {message}"
        if hasattr(self, 'matlab_status_label'):
            self.matlab_status_label.setText(status_text); self.matlab_status_label.setToolTip(tooltip_text)
            text_color = config.COLOR_ACCENT_SUCCESS if connected else config.COLOR_ACCENT_ERROR
            bg_color = QColor(text_color).lighter(180).name()
            self.matlab_status_label.setStyleSheet(f"font-weight:bold; padding:2px 5px; color:{text_color}; background-color:{bg_color}; border-radius:3px;")
        if "Initializing" not in message or (connected and "Initializing" in message): logging.info("MATLAB Connection Status: %s", message)
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
        self._update_window_title(); self.set_ui_enabled_for_matlab_op(True); logging.info("MATLAB Operation: Finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        if hasattr(self, 'menuBar'): self.menuBar().setEnabled(enabled)
        if hasattr(self, 'main_toolbar'): self.main_toolbar.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
        for dock_name in ["ElementsPaletteDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock", "ProblemsDock", "IDEDock"]:
            dock = self.findChild(QDockWidget, dock_name);
            if dock: dock.setEnabled(enabled)
        self._update_py_simulation_actions_enabled_state()

    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation(); logging.log(logging.INFO if success else logging.ERROR, "MATLAB Result (ModelGen/Sim): %s", message)
        if success:
            if "Model generation" in message and data: self.last_generated_model_path = data; QMessageBox.information(self, "Simulink Model Generation", f"Model generated successfully:\n{data}")
            elif "Simulation" in message: QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else: QMessageBox.warning(self, "MATLAB Operation Failed", message)

    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation(); logging.log(logging.INFO if success else logging.ERROR, "MATLAB Code Gen Result: %s", message)
        if success and output_dir:
            msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Information); msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText); abs_dir = os.path.abspath(output_dir); msg_box.setText(f"Code generation completed successfully.<br>Generated files are in: <a href='file:///{abs_dir}'>{abs_dir}</a>")
            msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction); open_btn = msg_box.addButton("Open Directory", QMessageBox.ActionRole); msg_box.addButton(QMessageBox.Ok); msg_box.exec()
            if msg_box.clickedButton() == open_btn and not QDesktopServices.openUrl(QUrl.fromLocalFile(abs_dir)):
                logging.error("Error opening directory: %s", abs_dir); QMessageBox.warning(self, "Error Opening Directory", f"Could not automatically open the directory:\n{abs_dir}")
        elif not success: QMessageBox.warning(self, "Code Generation Failed", message)

    def _prompt_save_if_dirty(self) -> bool:
        if not self.scene.is_dirty(): return True
        if self.py_sim_active: QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving or opening a new file."); return False
        file_desc = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled Diagram"
        reply = QMessageBox.question(self, "Save Diagram Changes?", f"The diagram '{file_desc}' has unsaved changes. Save them?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if reply == QMessageBox.Save: return self.action_handler.on_save_file()
        elif reply == QMessageBox.Cancel: return False
        return True

    def _prompt_ide_save_if_dirty(self) -> bool: return self.ide_manager.prompt_ide_save_if_dirty() if self.ide_manager else True

    def _load_from_path(self, file_path):
        try:
            if file_path.startswith(":/"):
                qfile = QFile(file_path);
                if not qfile.open(QIODevice.ReadOnly | QIODevice.Text): logging.error("Failed to open resource file %s: %s", file_path, qfile.errorString()); return False
                data = json.loads(qfile.readAll().data().decode('utf-8')); qfile.close()
            else:
                with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data: logging.error("Invalid BSM file format: %s.", file_path); return False
            self.scene.clear(); self.scene.load_diagram_data(data)
            for item in self.scene.items():
                if isinstance(item, GraphicsStateItem): self.connect_state_item_signals(item)
            return True
        except json.JSONDecodeError as e: logging.error("JSONDecodeError loading %s: %s", file_path, e); return False
        except Exception as e: logging.error("Unexpected error loading %s: %s", file_path, e, exc_info=True); return False

    def _save_to_path(self, file_path) -> bool:
        if self.py_sim_active: QMessageBox.warning(self, "Simulation Active", "Please stop Python simulation before saving."); return False
        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text): logging.error("Failed to open QSaveFile for %s: %s", file_path, save_file.errorString()); QMessageBox.critical(self, "Save Error", f"Could not open file for saving:\n{save_file.errorString()}"); return False
        try:
            diagram_data = self.scene.get_diagram_data(); json_data_str = json.dumps(diagram_data, indent=4, ensure_ascii=False)
            if save_file.write(json_data_str.encode('utf-8')) == -1: logging.error("Error writing QSaveFile %s: %s", file_path, save_file.errorString()); QMessageBox.critical(self, "Save Error", f"Could not write data to file:\n{save_file.errorString()}"); save_file.cancelWriting(); return False
            if not save_file.commit(): logging.error("Failed to commit QSaveFile for %s: %s", file_path, save_file.errorString()); QMessageBox.critical(self, "Save Error", f"Could not finalize saving file:\n{save_file.errorString()}"); return False
            logging.info("Successfully saved diagram to: %s", file_path); self._update_window_title(); self.scene.set_dirty(False); self._update_save_actions_enable_state(); return True
        except Exception as e: logging.error("Unexpected error during save to %s: %s", file_path, e, exc_info=True); QMessageBox.critical(self, "Save Error", f"An unexpected error occurred during saving:\n{e}"); save_file.cancelWriting(); return False

    @pyqtSlot(QGraphicsItem)
    def focus_on_item(self, item_to_focus: QGraphicsItem):
        if item_to_focus and item_to_focus.scene() == self.scene:
            self.scene.clearSelection(); item_to_focus.setSelected(True); item_rect = item_to_focus.sceneBoundingRect(); padding = 50
            if self.view: self.view.fitInView(item_rect.adjusted(-padding, -padding, padding, padding), Qt.KeepAspectRatio)
            display_name = "Item"
            if isinstance(item_to_focus, GraphicsStateItem): display_name = f"State: {item_to_focus.text_label}"
            elif isinstance(item_to_focus, GraphicsTransitionItem): display_name = f"Transition: {item_to_focus._compose_label_string()}"
            elif isinstance(item_to_focus, GraphicsCommentItem): display_name = f"Comment: {item_to_focus.toPlainText()[:30]}..."
            self.log_message("INFO", f"Focused on {display_name}")
        else: self.log_message("WARNING", f"Could not find or focus on item: {item_to_focus}")

    @pyqtSlot(bool)
    def on_matlab_settings(self, checked=False):
        dialog = MatlabSettingsDialog(matlab_connection=self.matlab_connection, parent=self); dialog.exec_(); logger.info("MATLAB settings dialog closed.")

    def closeEvent(self, event: QCloseEvent):
        logger.info("MW_CLOSE: closeEvent received.")
        if not self._prompt_ide_save_if_dirty(): event.ignore(); return
        if not self._prompt_save_if_dirty(): event.ignore(); return
        if hasattr(self, 'py_sim_ui_manager') and self.py_sim_ui_manager: self.py_sim_ui_manager.on_stop_py_simulation(silent=True)
        if self.internet_check_timer and self.internet_check_timer.isActive(): self.internet_check_timer.stop(); logger.info("MW_CLOSE: Internet check timer stopped.")
        if self.ai_chatbot_manager: self.ai_chatbot_manager.stop_chatbot(); logger.info("MW_CLOSE: AI Chatbot manager stopped.")
        if self.resource_monitor_manager: self.resource_monitor_manager.stop_monitoring_system() # self.resource_monitor_manager = None # Don't nullify
        if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads: logging.info("MW_CLOSE: Closing. %d MATLAB processes may still be running.", len(self.matlab_connection._active_threads))
        app_temp_session_dir_name = f"BSMDesigner_Temp_{QApplication.applicationPid()}"; session_temp_dir_path = QDir(QDir.tempPath()).filePath(app_temp_session_dir_name)
        if QDir(session_temp_dir_path).exists() and not QDir(session_temp_dir_path).removeRecursively(): logger.warning(f"MW_CLOSE: Failed to clean session temp dir: {session_temp_dir_path}")
        elif QDir(session_temp_dir_path).exists(): logger.info(f"MW_CLOSE: Cleaned session temp dir: {session_temp_dir_path}")
        self.settings_manager.set("gui_last_used_perspective", self.current_perspective_name, save_immediately=False)
        self.settings_manager.save_settings()
        logger.info("MW_CLOSE: Application closeEvent accepted."); event.accept()

    @pyqtSlot(float)
    def update_zoom_status_display(self, scale_factor: float):
        if hasattr(self, 'zoom_status_label'): self.zoom_status_label.setText(f"Zoom: {int(scale_factor * 100)}%")

    @pyqtSlot(bool)
    def _handle_py_sim_state_changed_by_manager(self, is_running: bool):
        logger.debug(f"MW: PySim state changed by manager to: {is_running}"); self.py_sim_active = is_running
        self._update_window_title(); self._update_py_sim_status_display(); self._update_matlab_actions_enabled_state(); self._update_py_simulation_actions_enabled_state()

    @pyqtSlot(bool)
    def _handle_py_sim_global_ui_enable_by_manager(self, enable: bool):
        logger.debug(f"MW: Global UI enable requested by PySim manager: {enable}"); is_editable = enable
        diagram_editing_actions = [self.new_action, self.open_action, self.save_action, self.save_as_action, self.undo_action, self.redo_action, self.delete_action, self.select_all_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action]
        for action in diagram_editing_actions:
            if hasattr(action, 'setEnabled'): action.setEnabled(is_editable)
        if hasattr(self, 'elements_palette_dock'): self.elements_palette_dock.setEnabled(is_editable)
        if hasattr(self, 'properties_edit_dialog_button'): self.properties_edit_dialog_button.setEnabled(is_editable and len(self.scene.selectedItems())==1)
        if hasattr(self, 'properties_apply_button'): self.properties_apply_button.setEnabled(False)
        if hasattr(self, 'properties_revert_button'): self.properties_revert_button.setEnabled(False)
        for item in self.scene.items():
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): item.setFlag(QGraphicsItem.ItemIsMovable, is_editable and self.scene.current_mode == "select")
        if not is_editable and self.scene.current_mode != "select": self.scene.set_mode("select")
        self._update_matlab_actions_enabled_state(); self._update_py_simulation_actions_enabled_state()

    @pyqtSlot(list)
    def update_problems_dock(self, issues_with_items: list):
        if not hasattr(self, 'problems_list_widget') or self.problems_list_widget is None: logger.warning("MainWindow.update_problems_dock: problems_list_widget not initialized."); return
        self.problems_list_widget.clear()
        if issues_with_items:
            for issue_msg, item_ref in issues_with_items:
                list_item_widget = QListWidgetItem(str(issue_msg))
                if item_ref: list_item_widget.setData(Qt.UserRole, item_ref)
                self.problems_list_widget.addItem(list_item_widget)
            self.problems_dock.setWindowTitle(f"Validation Issues ({len(issues_with_items)})")
            if self.problems_dock.isHidden(): self.problems_dock.show(); self.problems_dock.raise_()
        else: self.problems_list_widget.addItem("No validation issues found."); self.problems_dock.setWindowTitle("Validation Issues")

    @pyqtSlot(QListWidgetItem)
    def on_problem_item_double_clicked(self, list_item: QListWidgetItem):
        item_ref = list_item.data(Qt.UserRole)
        if item_ref and isinstance(item_ref, QGraphicsItem) and item_ref.scene() == self.scene:
            self.focus_on_item(item_ref); logger.info(f"Focused on problematic item: {getattr(item_ref, 'text_label', type(item_ref).__name__)}")
        else: logger.debug(f"No valid QGraphicsItem for validation issue: '{list_item.text()}'")

    @pyqtSlot(bool)
    def _on_ide_dirty_state_changed_by_manager(self, is_dirty: bool): self._update_ide_save_actions_enable_state(); self._update_window_title()

    @pyqtSlot(str)
    def _on_ide_language_changed_by_manager(self, language_param: str):
        ai_ready = self.ai_chatbot_manager is not None and self.ai_chatbot_manager.api_key is not None and self._internet_connected is True
        if hasattr(self, 'ide_analyze_action') and self.ide_manager and self.ide_manager.ide_language_combo:
            current_ide_lang = self.ide_manager.ide_language_combo.currentText()
            can_analyze_ide = (current_ide_lang == "Python" or current_ide_lang.startswith("C/C++")) and ai_ready
            self.ide_analyze_action.setEnabled(can_analyze_ide)
            tooltip = "Analyze code with AI";
            if not ai_ready: tooltip += " (Requires Internet & Gemini API Key)"
            elif not (current_ide_lang == "Python" or current_ide_lang.startswith("C/C++")): tooltip += " (Best for Python or C/C++)"
            self.ide_analyze_action.setToolTip(tooltip)
        self._update_window_title()

    def _update_window_title(self):
        diagram_fn = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"; diagram_dirty = self.scene.is_dirty()
        ide_dock_title, ide_status_bar, ide_dirty = "Standalone Code IDE", "IDE: Idle", False
        if self.ide_manager:
            ide_dirty = self.ide_manager.ide_editor_is_dirty; lang = self.ide_manager.ide_language_combo.currentText() if self.ide_manager.ide_language_combo else ""
            lang_info = f" ({lang})" if lang else ""; ide_dirty_char = "*" if ide_dirty else ""
            if self.ide_manager.current_ide_file_path:
                ide_fn = os.path.basename(self.ide_manager.current_ide_file_path)
                ide_dock_title = f"IDE: {ide_fn}{ide_dirty_char}{lang_info}"; ide_status_bar = f"IDE: {ide_fn}{ide_dirty_char}"
            elif self.ide_manager.ide_code_editor and self.ide_manager.ide_code_editor.toPlainText().strip():
                ide_dock_title = f"IDE: Untitled Script{ide_dirty_char}{lang_info}"; ide_status_bar = f"IDE: Untitled Script{ide_dirty_char}"
            else: ide_dock_title = f"Standalone Code IDE{lang_info}"
            if hasattr(self, 'ide_dock'): self.ide_dock.setWindowTitle(ide_dock_title)
            if hasattr(self, 'ide_file_status_label'): self.ide_file_status_label.setText(ide_status_bar)
        pysim_title_suffix, main_op_pysim_text = "", ""
        if self.py_sim_active:
            pysim_title_suffix = " [PySim Active"; main_op_pysim_text = "PySim: Active"
            if self.py_fsm_engine and self.py_fsm_engine.paused_on_breakpoint: pysim_title_suffix += " (Paused)"; main_op_pysim_text += " (Paused)"
            pysim_title_suffix += "]"
        self.setWindowModified(diagram_dirty or ide_dirty)
        title_parts = [f"{APP_NAME} - {diagram_fn}"]
        if pysim_title_suffix: title_parts.append(pysim_title_suffix)
        if self.ide_manager and self.ide_manager.current_ide_file_path and self.ide_manager.current_ide_file_path != self.current_file_path: title_parts.append(f"(IDE: {os.path.basename(self.ide_manager.current_ide_file_path)})")
        elif self.ide_manager and ide_dirty and not self.ide_manager.current_ide_file_path: title_parts.append("(IDE: Untitled)")
        self.setWindowTitle(" ".join(title_parts))
        main_op_text = f"File: {diagram_fn}{'*' if diagram_dirty else ''}"
        if hasattr(self, 'progress_bar') and self.progress_bar.isVisible(): main_op_text = self.main_op_status_label.text() if hasattr(self, 'main_op_status_label') and "MATLAB:" in self.main_op_status_label.text() else "Processing..."
        elif self.py_sim_active: main_op_text = main_op_pysim_text
        elif not self.current_file_path and not diagram_dirty and not ide_dirty: main_op_text = "Ready"
        if hasattr(self, 'main_op_status_label'): self.main_op_status_label.setText(main_op_text)
        self._update_py_sim_status_display()

    def _init_internet_status_check(self): self.internet_check_timer.timeout.connect(self._run_internet_check_job); self.internet_check_timer.start(15000); QTimer.singleShot(100, self._run_internet_check_job)

    def _run_internet_check_job(self):
        status, detail = False, "Checking..."
        try: s = socket.create_connection(("8.8.8.8", 53), timeout=1.5); s.close(); status, detail = True, "Connected"
        except socket.timeout: detail = "Timeout"
        except (socket.gaierror, OSError): detail = "Net Issue"
        if status != self._internet_connected or self._internet_connected is None: self._internet_connected = status; self._update_internet_status_display(status, detail)

    def _update_ai_features_enabled_state(self, is_online_and_key_present: bool):
        if hasattr(self, 'ask_ai_to_generate_fsm_action'): self.ask_ai_to_generate_fsm_action.setEnabled(is_online_and_key_present)
        if hasattr(self, 'clear_ai_chat_action'): self.clear_ai_chat_action.setEnabled(is_online_and_key_present)
        if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager:
            if self.ai_chat_ui_manager.ai_chat_send_button: self.ai_chat_ui_manager.ai_chat_send_button.setEnabled(is_online_and_key_present)
            if self.ai_chat_ui_manager.ai_chat_input:
                self.ai_chat_ui_manager.ai_chat_input.setEnabled(is_online_and_key_present)
                placeholder = "Type your message to the AI..." if is_online_and_key_present else ("AI disabled: API Key required." if self.ai_chatbot_manager and not self.ai_chatbot_manager.api_key else "AI disabled: Internet connection required.")
                self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText(placeholder)
        if hasattr(self, 'ide_analyze_action') and self.ide_manager and self.ide_manager.ide_language_combo:
            lang = self.ide_manager.ide_language_combo.currentText()
            can_analyze = (lang == "Python" or lang.startswith("C/C++")) and is_online_and_key_present
            self.ide_analyze_action.setEnabled(can_analyze)
            tooltip = "Analyze code with AI";
            if not (self.ai_chatbot_manager and self.ai_chatbot_manager.api_key and self._internet_connected): tooltip += " (Requires Internet & Gemini API Key)"
            elif not (lang == "Python" or lang.startswith("C/C++")): tooltip += " (Best for Python or C/C++)"
            self.ide_analyze_action.setToolTip(tooltip)

    def _update_internet_status_display(self, is_connected: bool, message_detail: str):
        if hasattr(self, 'internet_status_label'):
            self.internet_status_label.setText(f"Net: {message_detail}"); self.internet_status_label.setToolTip(f"Internet Status: {message_detail} (Checks 8.8.8.8:53)")
            text_color = config.COLOR_ACCENT_SUCCESS if is_connected else config.COLOR_ACCENT_ERROR; bg_color = QColor(text_color).lighter(180).name()
            self.internet_status_label.setStyleSheet(f"font-size:{APP_FONT_SIZE_SMALL}; padding:2px 5px; color:{text_color}; background-color:{bg_color}; border-radius:3px;")
        logging.debug("Internet Status Update: %s", message_detail)
        key_present = self.ai_chatbot_manager is not None and bool(self.ai_chatbot_manager.api_key)
        if hasattr(self.ai_chatbot_manager, 'set_online_status'): self.ai_chatbot_manager.set_online_status(is_connected)
        self._update_ai_features_enabled_state(is_connected and key_present)

    def _update_py_sim_status_display(self):
        if hasattr(self, 'py_sim_status_label'):
            status_text, style, tooltip = "PySim: Idle", f"font-weight:normal;padding:2px 5px; color:{config.COLOR_TEXT_SECONDARY}; background-color:{config.COLOR_BACKGROUND_MEDIUM}; border-radius:3px;", "Internal Python FSM Simulation is Idle."
            if self.py_sim_active and self.py_fsm_engine:
                state_name = self.py_fsm_engine.get_current_state_name(); display_name = (state_name[:20] + '...') if len(state_name) > 23 else state_name
                status_text = f"PySim: Active ({html.escape(display_name)})"; bg_color = QColor(config.COLOR_PY_SIM_STATE_ACTIVE).lighter(180).name()
                style = f"font-weight:bold;padding:2px 5px;color:{config.COLOR_PY_SIM_STATE_ACTIVE.name()}; background-color:{bg_color}; border-radius:3px;"; tooltip = f"Python FSM Simulation Active: {state_name}"
                if self.py_fsm_engine.paused_on_breakpoint: status_text += " (Paused)"; tooltip += " (Paused at Breakpoint)"
            self.py_sim_status_label.setText(status_text); self.py_sim_status_label.setStyleSheet(style); self.py_sim_status_label.setToolTip(tooltip)

    def _update_py_simulation_actions_enabled_state(self):
        is_matlab_running = hasattr(self, 'progress_bar') and self.progress_bar and self.progress_bar.isVisible()
        can_start = not self.py_sim_active and not is_matlab_running; can_control = self.py_sim_active and not is_matlab_running
        if hasattr(self, 'start_py_sim_action'): self.start_py_sim_action.setEnabled(can_start)
        if hasattr(self, 'stop_py_sim_action'): self.stop_py_sim_action.setEnabled(can_control)
        if hasattr(self, 'reset_py_sim_action'): self.reset_py_sim_action.setEnabled(can_control)
        if hasattr(self, 'py_sim_ui_manager') and self.py_sim_ui_manager: self.py_sim_ui_manager._update_internal_controls_enabled_state()

    @pyqtSlot()
    def _update_zoom_to_selection_action_enable_state(self):
        if hasattr(self, 'zoom_to_selection_action'): self.zoom_to_selection_action.setEnabled(bool(self.scene.selectedItems()))

    @pyqtSlot()
    def _update_align_distribute_actions_enable_state(self):
        count = len(self.scene.selectedItems())
        can_align, can_distribute = count >= 2, count >= 3
        if hasattr(self, 'align_actions'):
            for action in self.align_actions: action.setEnabled(can_align)
        if hasattr(self, 'distribute_actions'):
            for action in self.distribute_actions: action.setEnabled(can_distribute)

    @pyqtSlot(str, str)
    def _handle_state_renamed_inline(self, old_name: str, new_name: str):
        logger.debug(f"MainWindow: State renamed inline from '{old_name}' to '{new_name}'.")
        self._refresh_find_dialog_if_visible()
        if self.scene.selectedItems() and len(self.scene.selectedItems()) == 1 and isinstance(self.scene.selectedItems()[0], GraphicsStateItem) and self.scene.selectedItems()[0].text_label == new_name:
            self._update_properties_dock()

    def connect_state_item_signals(self, state_item: GraphicsStateItem):
        if hasattr(state_item, 'signals') and hasattr(state_item.signals, 'textChangedViaInlineEdit'):
            try: state_item.signals.textChangedViaInlineEdit.disconnect(self._handle_state_renamed_inline)
            except TypeError: pass
            state_item.signals.textChangedViaInlineEdit.connect(self._handle_state_renamed_inline)
            logger.debug(f"Connected rename signal for state: {state_item.text_label}")

    @pyqtSlot()
    def _refresh_find_dialog_if_visible(self):
        if self.find_item_dialog and not self.find_item_dialog.isHidden(): logger.debug("Refreshing FindItemDialog."); self.find_item_dialog.refresh_list()

    @pyqtSlot(GraphicsStateItem, bool)
    def on_toggle_state_breakpoint(self, state_item: GraphicsStateItem, set_bp: bool):
        if not self.py_fsm_engine or not self.py_sim_active:
            QMessageBox.information(self, "Simulation Not Active", "Breakpoints only work during active Python simulation.")
            if self.sender() and isinstance(self.sender(), QAction): self.sender().setChecked(not set_bp); return
        state_name = state_item.text_label; action_text = ""
        if set_bp:
            self.py_fsm_engine.add_state_breakpoint(state_name); tooltip = state_item.toolTip()
            if "[BP]" not in tooltip: state_item.setToolTip(f"{tooltip}\n[Breakpoint Set]" if tooltip else f"State: {state_name}\n[Breakpoint Set]")
            action_text = f"Breakpoint SET for state: {state_name}"
        else:
            self.py_fsm_engine.remove_state_breakpoint(state_name); state_item.setToolTip(state_item.toolTip().replace("\n[Breakpoint Set]", ""))
            action_text = f"Breakpoint CLEARED for state: {state_name}"
        state_item.update()
        if hasattr(self, 'py_sim_ui_manager') and self.py_sim_ui_manager: self.py_sim_ui_manager.append_to_action_log([action_text])
        logger.info(action_text)

    def log_message(self, level_str: str, message: str): logger.log(getattr(logging, level_str.upper(), logging.INFO), message)

    @pyqtSlot()
    def on_show_find_item_dialog(self):
        if not self.find_item_dialog:
            self.find_item_dialog = FindItemDialog(parent=self, scene_ref=self.scene)
            self.find_item_dialog.item_selected_for_focus.connect(self.focus_on_item)
            self.scene.scene_content_changed_for_find.connect(self._refresh_find_dialog_if_visible)
        if self.find_item_dialog.isHidden(): self.find_item_dialog.refresh_list(); self.find_item_dialog.show(); self.find_item_dialog.raise_(); self.find_item_dialog.activateWindow()
        else: self.find_item_dialog.activateWindow()
        if hasattr(self.find_item_dialog, 'search_input'): self.find_item_dialog.search_input.selectAll(); self.find_item_dialog.search_input.setFocus()

    def _add_fsm_data_to_scene(self, fsm_data: dict, clear_current_diagram: bool = False, original_user_prompt: str | None = None):
        if not isinstance(fsm_data, dict): self.log_message("ERROR", "Invalid FSM data format."); QMessageBox.critical(self, "Error Adding FSM Data", "Invalid FSM data structure."); return
        if clear_current_diagram and not self.action_handler.on_new_file(silent=True): self.log_message("ERROR", "Failed to clear diagram."); return
        self.undo_stack.beginMacro(f"Add FSM Data ({original_user_prompt[:20] if original_user_prompt else 'AI Generated'})")
        states_data, transitions_data, comments_data = fsm_data.get('states', []), fsm_data.get('transitions', []), fsm_data.get('comments', [])
        center_x, center_y = self.view.mapToScene(self.view.viewport().rect().center()).x(), self.view.mapToScene(self.view.viewport().rect().center()).y()
        if not clear_current_diagram and self.scene.items(): occupied_rect = self.scene.itemsBoundingRect(); center_x, center_y = (occupied_rect.right() + 100, occupied_rect.top()) if not occupied_rect.isEmpty() else (center_x, center_y)
        min_x, min_y, has_pos = float('inf'), float('inf'), False
        for item_list in [states_data, comments_data]:
            if item_list and all('x' in i and 'y' in i for i in item_list if isinstance(i, dict)):
                has_pos = True;
                for i_data in item_list:
                    if isinstance(i_data, dict): min_x, min_y = min(min_x, i_data.get('x', 0)), min(min_y, i_data.get('y', 0))
        if not has_pos or min_x == float('inf'): min_x, min_y = 0, 0
        state_map = {}
        for i, s_data in enumerate(states_data):
            if not isinstance(s_data, dict): self.log_message("WARNING", f"Skipping invalid state data: {s_data}"); continue
            name = s_data.get('name');
            if not name: self.log_message("WARNING", f"Skipping state: missing name: {s_data}"); continue
            unique_name = self.scene._generate_unique_state_name(name);
            if unique_name != name: self.log_message("INFO", f"State '{name}' renamed to '{unique_name}'.")
            pos_x, pos_y = (center_x + (s_data.get('x', 0) - min_x) if has_pos else (center_x + i * 150)), (center_y + (s_data.get('y', 0) - min_y) if has_pos else center_y)
            pos_x, pos_y = round(pos_x / self.scene.grid_size) * self.scene.grid_size, round(pos_y / self.scene.grid_size) * self.scene.grid_size
            state_item = GraphicsStateItem(pos_x, pos_y, s_data.get('width', 120), s_data.get('height', 60), unique_name, s_data.get('is_initial', False), s_data.get('is_final', False), s_data.get('properties', {}).get('color', config.COLOR_ITEM_STATE_DEFAULT_BG), s_data.get('entry_action', ""), s_data.get('during_action', ""), s_data.get('exit_action', ""), s_data.get('description', fsm_data.get('description', "") if s_data.get('is_initial', False) else ""), s_data.get('is_superstate', False), s_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}), action_language=s_data.get('action_language', DEFAULT_EXECUTION_ENV))
            self.connect_state_item_signals(state_item); cmd = AddItemCommand(self.scene, state_item, f"Add State '{unique_name}'"); self.undo_stack.push(cmd); state_map[name] = state_item
        for t_data in transitions_data:
            if not isinstance(t_data, dict): self.log_message("WARNING", f"Skipping invalid transition data: {t_data}"); continue
            src_item, tgt_item = state_map.get(t_data.get('source')), state_map.get(t_data.get('target'))
            if src_item and tgt_item:
                trans_item = GraphicsTransitionItem(src_item, tgt_item, event_str=t_data.get('event', ""), condition_str=t_data.get('condition', ""), action_language=t_data.get('action_language', DEFAULT_EXECUTION_ENV), action_str=t_data.get('action', ""), color=t_data.get('properties', {}).get('color', config.COLOR_ITEM_TRANSITION_DEFAULT), description=t_data.get('description', ""))
                trans_item.set_control_point_offset(QPointF(t_data.get('control_offset_x', 0), t_data.get('control_offset_y', 0))); cmd = AddItemCommand(self.scene, trans_item, "Add Transition"); self.undo_stack.push(cmd)
            else: self.log_message("WARNING", f"Could not link transition: source '{t_data.get('source')}' or target '{t_data.get('target')}' not found.")
        for i, c_data in enumerate(comments_data):
            if not isinstance(c_data, dict): self.log_message("WARNING", f"Skipping invalid comment data: {c_data}"); continue
            if not c_data.get('text'): continue
            pos_x, pos_y = (center_x + (c_data.get('x', 0) - min_x) if has_pos else (center_x + i * 100)), (center_y + (c_data.get('y', 0) - min_y) + 100 if has_pos else (center_y + 100 + i * 30))
            pos_x, pos_y = round(pos_x / self.scene.grid_size) * self.scene.grid_size, round(pos_y / self.scene.grid_size) * self.scene.grid_size
            comment_item = GraphicsCommentItem(pos_x, pos_y, c_data.get('text')); comment_item.setTextWidth(c_data.get('width', 150)); cmd = AddItemCommand(self.scene, comment_item, "Add Comment"); self.undo_stack.push(cmd)
        self.undo_stack.endMacro(); self.scene.set_dirty(True); self.scene.run_all_validations("AddFSMDataFromAI"); self.action_handler.on_fit_diagram_in_view(); self.log_message("INFO", "Successfully added FSM data to scene.")


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
    pass