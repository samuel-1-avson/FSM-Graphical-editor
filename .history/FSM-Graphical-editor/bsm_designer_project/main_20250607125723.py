


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
    QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
    QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
    QFileDialog, QProgressBar, QTabWidget, QCheckBox, QActionGroup, QGraphicsItem,
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
    FSM_TEMPLATES_BUILTIN,MIME_TYPE_BSM_TEMPLATE
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
        self.ui_manager.populate_dynamic_docks() # This also needs ide_dock to be available if it tries to tabify it.
                                                 # It's fine if populate_dynamic_docks is called after IDEManager init.
        
        self._connect_signals()
        self.action_handler.connect_actions() # Connect actions from UIManager to ActionHandler slots

        self._internet_connected: bool | None = None
        self.internet_check_timer = QTimer(self)
        self._init_internet_status_check()

        self._set_status_label_object_names() # Ensure status labels have object names for styling
        self._update_ui_element_states()      # Initial UI state update

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
        self.scene.modifiedStatusChanged.connect(self.setWindowModified) # Built-in Qt signal
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
        
        # Connect signals from IDEManager
        if self.ide_manager:
            self.ide_manager.ide_dirty_state_changed.connect(self._on_ide_dirty_state_changed_by_manager)
            self.ide_manager.ide_file_path_changed.connect(self._update_window_title) # Update window title if IDE file path changes
            self.ide_manager.ide_language_combo_changed.connect(self._on_ide_language_changed_by_manager)
            
        # Connect signals from AIChatbotManager (UI related signals already connected in AIChatUIManager)
        if self.ai_chatbot_manager:
            # MainWindow might need to react to some core AI status for enabling/disabling other features.
            # For now, most UI updates are handled by AIChatUIManager.
            # Example: If AI status changes to API_KEY_ERROR, maybe disable certain AI-related menu items
            # self.ai_chatbot_manager.statusUpdate.connect(self._handle_ai_core_status_change_for_mw)
            pass


    def _set_status_label_object_names(self):
        # Status labels are created by UIManager and assigned to self.mw
        if hasattr(self, 'status_label'): self.status_label.setObjectName("StatusLabel")
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
        """Called by IDEManager's signal or directly when IDE dirtiness changes."""
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
        if hasattr(self, 'status_label'): self.status_label.setText(f"Running MATLAB: {operation_name}...")
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False)

    def _finish_matlab_operation(self):
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(False)
        if hasattr(self, 'status_label'): self.status_label.setText("Ready")
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
        if not self.scene.is_dirty():
            return True
        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving or opening a new file.")
            return False
        file_desc = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled Diagram"
        reply = QMessageBox.question(self, "Save Diagram Changes?",
                                     f"The diagram '{file_desc}' has unsaved changes. Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save)
        if reply == QMessageBox.Save: return self.action_handler.on_save_file() # Delegate to ActionHandler
        elif reply == QMessageBox.Cancel: return False
        return True
        
    def _prompt_ide_save_if_dirty(self) -> bool:
        if self.ide_manager:
            return self.ide_manager.prompt_ide_save_if_dirty()
        return True


    def _load_from_path(self, file_path): # Used by ActionHandler
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

    def _save_to_path(self, file_path) -> bool: # Used by ActionHandler
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
            if hasattr(self, 'status_label'): self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            self.scene.set_dirty(False); self._update_window_title(); self._update_save_actions_enable_state(); return True
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

    @pyqtSlot(bool) # Modified to accept bool, even if not used by this specific slot
    def on_matlab_settings(self, checked=False): # Default arg for safety
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
        
        if self.resource_monitor_manager: # Use the manager to stop
            self.resource_monitor_manager.stop_monitoring_system()
            self.resource_monitor_manager = None # Allow garbage collection
            
        if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads: logging.info("MW_CLOSE: Closing application. %d MATLAB processes initiated by this session may still be running in the background if not completed.", len(self.matlab_connection._active_threads))
        app_temp_session_dir_name = f"BSMDesigner_Temp_{QApplication.applicationPid()}"; session_temp_dir_path = QDir(QDir.tempPath()).filePath(app_temp_session_dir_name)
        if QDir(session_temp_dir_path).exists():
            if QDir(session_temp_dir_path).removeRecursively(): logger.info(f"MW_CLOSE: Cleaned up session temporary directory: {session_temp_dir_path}")
            else: logger.warning(f"MW_CLOSE: Failed to clean up session temporary directory: {session_temp_dir_path}")
        logger.info("MW_CLOSE: Application closeEvent accepted.")
        event.accept()

    # --- Methods related to UI updates based on internal state, called by various managers/signals ---
    @pyqtSlot(float)
    def update_zoom_status_display(self, scale_factor: float):
        if hasattr(self, 'zoom_status_label'):
            zoom_percentage = int(scale_factor * 100)
            self.zoom_status_label.setText(f"Zoom: {zoom_percentage}%")

    @pyqtSlot(float, float, float, str)
    def _update_resource_display(self, cpu_usage, ram_usage, gpu_util, gpu_name):
        # This method is now connected to ResourceMonitorManager's worker signal
        if hasattr(self, 'cpu_status_label'): self.cpu_status_label.setText(f"CPU: {cpu_usage:.0f}%")
        if hasattr(self, 'ram_status_label'): self.ram_status_label.setText(f"RAM: {ram_usage:.0f}%")
        if hasattr(self, 'gpu_status_label'):
            # Logic for GPU display remains the same
            if gpu_util == -1.0: self.gpu_status_label.setText(f"GPU: {gpu_name}")
            elif gpu_util == -2.0: self.gpu_status_label.setText(f"GPU: Error")
            elif gpu_util == -3.0: self.gpu_status_label.setText(f"GPU: Mon Error")
            elif self.resource_monitor_manager and self.resource_monitor_manager.worker and self.resource_monitor_manager.worker._nvml_initialized and self.resource_monitor_manager.worker._gpu_handle:
                self.gpu_status_label.setText(f"GPU: {gpu_util:.0f}%")
                self.gpu_status_label.setToolTip(f"GPU: {gpu_util:.0f}% ({gpu_name})")
            else:
                 self.gpu_status_label.setText(f"GPU: N/A"); self.gpu_status_label.setToolTip(gpu_name)


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
        # This method updates a dock widget directly, so it remains in MainWindow
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
        # Handles interaction with Problems Dock, remains in MainWindow
        item_ref = list_item.data(Qt.UserRole)
        if item_ref and isinstance(item_ref, QGraphicsItem) and item_ref.scene() == self.scene:
            self.focus_on_item(item_ref)
            logger.info(f"Focused on problematic item from Validation Issues list: {getattr(item_ref, 'text_label', type(item_ref).__name__)}")
        else: logger.debug(f"No valid QGraphicsItem reference found for clicked validation issue: '{list_item.text()}'")

    @pyqtSlot(bool)
    def _on_ide_dirty_state_changed_by_manager(self, is_dirty: bool):
        # Called by IDEManager signal
        self._update_ide_save_actions_enable_state()
        self._update_window_title()

    @pyqtSlot(str)
    def _on_ide_language_changed_by_manager(self, language_param: str):
        # Called by IDEManager signal
        # MainWindow needs to update AI action enablement based on this
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
        # This method updates the main window title, so it remains here
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        ide_dock_title = "Standalone Code IDE"; ide_simple_status_for_main_title = ""
        if self.ide_manager: 
            current_ide_lang_text = self.ide_manager.ide_language_combo.currentText() if self.ide_manager.ide_language_combo else ""
            lang_info = f" ({current_ide_lang_text})" if current_ide_lang_text else ""
            if self.ide_manager.current_ide_file_path:
                ide_fn = os.path.basename(self.ide_manager.current_ide_file_path)
                ide_dock_title = f"IDE: {ide_fn}{'*' if self.ide_manager.ide_editor_is_dirty else ''}{lang_info}"
                ide_simple_status_for_main_title = f"IDE: {ide_fn}{'*' if self.ide_manager.ide_editor_is_dirty else ''}"
            elif self.ide_manager.ide_code_editor and self.ide_manager.ide_code_editor.toPlainText().strip():
                 ide_dock_title = f"IDE: Untitled Script{'*' if self.ide_manager.ide_editor_is_dirty else ''}{lang_info}"
                 ide_simple_status_for_main_title = f"IDE: Untitled Script{'*' if self.ide_manager.ide_editor_is_dirty else ''}"
            else: ide_dock_title = f"Standalone Code IDE{lang_info}"
            if hasattr(self, 'ide_dock'): self.ide_dock.setWindowTitle(ide_dock_title) 

        sim_status_suffix = " [PySim Running]" if self.py_sim_active else ""
        if self.py_sim_active and self.py_fsm_engine and self.py_fsm_engine.paused_on_breakpoint: sim_status_suffix += " (Paused)"
        
        main_window_is_dirty = self.scene.is_dirty()
        if self.ide_manager: main_window_is_dirty = main_window_is_dirty or self.ide_manager.ide_editor_is_dirty
        self.setWindowModified(main_window_is_dirty) 

        title = f"{APP_NAME} - {file_name}{sim_status_suffix} [*]"
        self.setWindowTitle(title)

        if hasattr(self, 'status_label'):
            main_file_status = f"File: {file_name}{' *' if self.scene.is_dirty() else ''}"
            pysim_status = f"PySim: {'Active' if self.py_sim_active else 'Idle'}"
            if self.py_sim_active and self.py_fsm_engine and self.py_fsm_engine.paused_on_breakpoint: pysim_status += " (Paused)"
            ide_status_for_bar = ide_simple_status_for_main_title
            full_status_text_parts = [main_file_status, pysim_status]
            if ide_status_for_bar: full_status_text_parts.append(ide_status_for_bar)
            self.status_label.setText(" | ".join(p for p in full_status_text_parts if p))


    def _init_internet_status_check(self):
        # Remains in MainWindow as it affects multiple managers (AI, potentially others)
        self.internet_check_timer.timeout.connect(self._run_internet_check_job)
        self.internet_check_timer.start(15000)
        QTimer.singleShot(100, self._run_internet_check_job)

    def _run_internet_check_job(self):
        current_status = False; status_detail = "Checking..."
        try: s = socket.create_connection(("8.8.8.8", 53), timeout=1.5); s.close(); current_status = True; status_detail = "Connected"
        except socket.timeout: status_detail = "Timeout"
        except (socket.gaierror, OSError): status_detail = "Net Issue"
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
        if hasattr(self, 'ide_analyze_action') and self.ide_manager and self.ide_manager.ide_language_combo: # Ensure ide_manager and its combo are checked
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
                status_text = f"PySim: Active ({html.escape(display_state_name)})"; bg_color = QColor(COLOR_PY_SIM_STATE_ACTIVE).lighter(180).name(); style = f"font-weight:bold;padding:2px 5px;color:{COLOR_PY_SIM_STATE_ACTIVE.name()}; background-color:{bg_color}; border-radius:3px;"; tooltip = f"Python FSM Simulation Active: {current_state_name}"
                if self.py_fsm_engine.paused_on_breakpoint: status_text += " (Paused)"; tooltip += " (Paused at Breakpoint)"
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

    def _update_properties_dock(self): # Called by scene selectionChanged
        selected_items = self.scene.selectedItems()
        
        if not hasattr(self, 'properties_editor_layout') or not hasattr(self, '_dock_property_editors') or \
           not hasattr(self, 'properties_editor_container') or not hasattr(self, 'properties_placeholder_label') or \
           not hasattr(self, 'properties_edit_dialog_button') or not hasattr(self, 'properties_apply_button') or \
           not hasattr(self, 'properties_revert_button'):
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
        
        if len(selected_items) == 1:
            self._current_edited_item_in_dock = selected_items[0]
            item_data = self._current_edited_item_in_dock.get_data() if hasattr(self._current_edited_item_in_dock, 'get_data') else {}
            self.properties_editor_container.setVisible(True)
            self.properties_placeholder_label.setVisible(False)
            self.properties_edit_dialog_button.setEnabled(True)
            if isinstance(self._current_edited_item_in_dock, GraphicsStateItem):
                name_edit = QLineEdit(item_data.get('name', '')); name_edit.textChanged.connect(self._on_dock_property_changed_mw)
                self.properties_editor_layout.addRow("Name:", name_edit); self._dock_property_editors['name'] = name_edit
            elif isinstance(self._current_edited_item_in_dock, GraphicsTransitionItem):
                event_edit = QLineEdit(item_data.get('event', '')); event_edit.textChanged.connect(self._on_dock_property_changed_mw)
                self.properties_editor_layout.addRow("Event:", event_edit); self._dock_property_editors['event'] = event_edit
            elif isinstance(self._current_edited_item_in_dock, GraphicsCommentItem):
                text_edit = QTextEdit(item_data.get('text', '')); text_edit.setFixedHeight(60); text_edit.textChanged.connect(self._on_dock_property_changed_mw)
                self.properties_editor_layout.addRow("Text:", text_edit); self._dock_property_editors['text'] = text_edit
            else:
                 self.properties_placeholder_label.setText(f"<i>Editing: {type(self._current_edited_item_in_dock).__name__}.<br>Dock editor UI needs full implementation. Use 'Advanced Edit...'</i>")
                 self.properties_editor_container.setVisible(False); self.properties_placeholder_label.setVisible(True)
        elif len(selected_items) > 1:
            self.properties_placeholder_label.setText(f"<i><b>{len(selected_items)} items selected.</b><br><span style='font-size:{APP_FONT_SIZE_SMALL}; color:{COLOR_TEXT_SECONDARY};'>Select a single item to edit properties.</span></i>")
            self.properties_editor_container.setVisible(False); self.properties_placeholder_label.setVisible(True); self.properties_edit_dialog_button.setEnabled(False)
        else:
            self.properties_placeholder_label.setText(f"<i>No item selected.</i><br><span style='font-size:{APP_FONT_SIZE_SMALL}; color:{COLOR_TEXT_SECONDARY};'>Click an item or use tools to add elements.</span>")
            self.properties_editor_container.setVisible(False); self.properties_placeholder_label.setVisible(True); self.properties_edit_dialog_button.setEnabled(False)
        self.properties_apply_button.setEnabled(False)
        self.properties_revert_button.setEnabled(False)

    def _on_dock_property_changed_mw(self): 
        if hasattr(self, 'properties_apply_button'): self.properties_apply_button.setEnabled(True)
        if hasattr(self, 'properties_revert_button'): self.properties_revert_button.setEnabled(True)

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
            if self.sender() and isinstance(self.sender(), QAction): self.sender().setChecked(not set_bp)
            return
        state_name = state_item.text_label; action_text = ""
        if set_bp:
            self.py_fsm_engine.add_state_breakpoint(state_name)
            current_tooltip = state_item.toolTip()
            if "[BP]" not in current_tooltip: state_item.setToolTip(f"{current_tooltip}\n[Breakpoint Set]" if current_tooltip else f"State: {state_name}\n[Breakpoint Set]")
            action_text = f"Breakpoint SET for state: {state_name}"
        else:
            self.py_fsm_engine.remove_state_breakpoint(state_name)
            state_item.setToolTip(state_item.toolTip().replace("\n[Breakpoint Set]", ""))
            action_text = f"Breakpoint CLEARED for state: {state_name}"
        state_item.update()
        if hasattr(self, 'py_sim_ui_manager') and self.py_sim_ui_manager: self.py_sim_ui_manager.append_to_action_log([action_text])
        logger.info(action_text)

    def log_message(self, level_str: str, message: str):
        level = getattr(logging, level_str.upper(), logging.INFO)
        logger.log(level, message)

    # --- Slot for FindItemDialog (delegated from ActionHandler) ---
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
