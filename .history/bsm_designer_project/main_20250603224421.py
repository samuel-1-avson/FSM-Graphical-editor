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
import psutil
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None

# --- Custom Modules ---
from graphics_scene import DiagramScene, ZoomableView
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
# CodeEditor import is now handled by IDEManager
from fsm_simulator import FSMSimulator, FSMError
from ai_chatbot import AIChatbotManager, AIStatus, AIChatUIManager
# MatlabSettingsDialog now imported by MatlabOperationsManager
from dialogs import FindItemDialog # Keep this one for MainWindow
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
from utils import get_standard_icon, get_bundled_file_path # Ensure get_bundled_file_path is here
from ui_py_simulation_manager import PySimulationUIManager
from c_code_generator import generate_c_code_files

# --- Manager Imports ---
from file_operations_manager import FileOperationsManager
from ide_manager import IDEManager
from matlab_operations_manager import MatlabOperationsManager
from view_manager import ViewManager
from alignment_manager import AlignmentManager 

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

class DraggableToolButton(QPushButton):
    def __init__(self, text, mime_type, item_type_data_str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("DraggableToolButton")
        self.mime_type = mime_type
        self.item_type_data_str = item_type_data_str
        self.setMinimumHeight(38)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.drag_start_position = QPoint()
        self.setIconSize(QSize(20,20))

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
        mime_data.setData(self.mime_type, self.item_type_data_str.encode('utf-8'))

        if self.mime_type == MIME_TYPE_BSM_TEMPLATE: 
            try:
                template_obj = json.loads(self.item_type_data_str)
                mime_data.setText(f"FSM Template: {template_obj.get('name', 'Custom Template')}")
            except json.JSONDecodeError:
                mime_data.setText("FSM Template (Invalid JSON)")
        else:
            mime_data.setText(self.item_type_data_str)

        drag.setMimeData(mime_data)
        pixmap = QPixmap(self.size()); pixmap.fill(Qt.transparent)
        self.render(pixmap, QPoint(), QRegion(), QWidget.RenderFlags(QWidget.DrawChildren))
        painter = QPainter(pixmap); painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.fillRect(pixmap.rect(), QColor(0, 0, 0, 150)); painter.end()
        drag.setPixmap(pixmap); drag.setHotSpot(event.pos()); drag.exec_(Qt.CopyAction)

class ResourceMonitorWorker(QObject): 
    resourceUpdate = pyqtSignal(float, float, float, str)
    finished_signal = pyqtSignal()
    MAX_NVML_REINIT_ATTEMPTS = 3; NVML_REINIT_BACKOFF_SECONDS = 30; WORKER_LOOP_CHECK_INTERVAL_MS = 100
    def __init__(self, interval_ms=2000, parent=None):
        super().__init__(parent); self.data_collection_interval_ms = interval_ms; self._nvml_initialized = False
        self._gpu_handle = None; self._gpu_name_cache = "N/A"; self._nvml_reinit_attempts = 0
        self._last_nvml_reinit_attempt_time = 0; self._stop_requested = False
        if PYNVML_AVAILABLE and pynvml: self._attempt_nvml_init()
        elif not PYNVML_AVAILABLE: self._gpu_name_cache = "N/A (pynvml N/A)"
    def _attempt_nvml_init(self, from_worker_loop=False):
        if self._stop_requested or self._nvml_initialized: return
        current_time = QTime.currentTime().secsTo(QTime(23,59,59))
        if self._nvml_reinit_attempts >= self.MAX_NVML_REINIT_ATTEMPTS and (current_time - self._last_nvml_reinit_attempt_time) < self.NVML_REINIT_BACKOFF_SECONDS and from_worker_loop: return
        try:
            pynvml.nvmlInit(); self._nvml_initialized = True; self._nvml_reinit_attempts = 0
            if pynvml.nvmlDeviceGetCount() > 0:
                self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0); gpu_name_raw = pynvml.nvmlDeviceGetName(self._gpu_handle)
                if isinstance(gpu_name_raw, bytes): self._gpu_name_cache = gpu_name_raw.decode('utf-8')
                elif isinstance(gpu_name_raw, str): self._gpu_name_cache = gpu_name_raw
                else: self._gpu_name_cache = "NVIDIA GPU Name TypeErr"
                logger.info(f"NVML initialized. GPU: {self._gpu_name_cache}")
            else: self._gpu_name_cache = "NVIDIA GPU N/A (No devices)"; logger.info("NVML initialized but no NVIDIA GPUs found.")
        except pynvml.NVMLError as e_nvml:
            self._nvml_reinit_attempts += 1; self._last_nvml_reinit_attempt_time = current_time
            if self._nvml_reinit_attempts <= self.MAX_NVML_REINIT_ATTEMPTS or not from_worker_loop: logger.warning(f"Could not initialize NVML (attempt {self._nvml_reinit_attempts}): {e_nvml}")
            else: logger.debug(f"NVML init attempt {self._nvml_reinit_attempts} failed: {e_nvml.value}")
            self._nvml_initialized = False; error_code_str = f" (Code: {e_nvml.value})" if hasattr(e_nvml, 'value') else ""; self._gpu_name_cache = f"NVML Init Err{error_code_str}"
        except AttributeError as e_attr: logger.warning(f"NVML: Attribute error during init: {e_attr}"); self._nvml_initialized = False; self._gpu_name_cache = "NVML Attr Err"
        except Exception as e: logger.warning(f"Unexpected error during NVML init: {e}", exc_info=True); self._nvml_initialized = False; self._gpu_name_cache = "NVML Unexp. Err"
    @pyqtSlot()
    def start_monitoring(self): logger.info("ResourceMonitorWorker: start_monitoring called."); self._stop_requested = False; self._monitor_resources()
    @pyqtSlot()
    def stop_monitoring(self):
        logger.info("ResourceMonitorWorker: stop_monitoring_slot called. Setting _stop_requested = True.")
        self._stop_requested = True
    def _shutdown_nvml(self):
        if self._nvml_initialized and PYNVML_AVAILABLE and pynvml:
            try: pynvml.nvmlShutdown(); logger.info("ResourceMonitorWorker: NVML shutdown successfully.")
            except Exception as e: logger.warning(f"Error shutting down NVML: {e}")
        self._nvml_initialized = False; self._gpu_handle = None
    def _monitor_resources(self):
        logger.info("ResourceMonitorWorker: _monitor_resources loop STARTED.")
        last_data_emit_time = 0
        worker_thread = self.thread()
        if not worker_thread: logger.error("ResourceMonitorWorker: CRITICAL - Worker is not associated with a QThread."); self.finished_signal.emit(); return
        loop_count = 0
        while not worker_thread.isInterruptionRequested() and not self._stop_requested:
            loop_count += 1
            if loop_count % 50 == 0: logger.debug(f"ResourceMonitorWorker: Loop iteration {loop_count}, InterruptionRequested: {worker_thread.isInterruptionRequested()}, StopRequested: {self._stop_requested}")
            current_loop_time = QTime.currentTime().msecsSinceStartOfDay()
            if (current_loop_time - last_data_emit_time) >= self.data_collection_interval_ms or last_data_emit_time == 0:
                if worker_thread.isInterruptionRequested() or self._stop_requested: logger.debug("ResourceMonitorWorker: Interruption/stop detected before emitting resourceUpdate."); break
                try:
                    cpu_usage = psutil.cpu_percent(interval=None); ram_percent = psutil.virtual_memory().percent; gpu_util = -1.0; gpu_name_to_emit = self._gpu_name_cache
                    if self._nvml_initialized and self._gpu_handle:
                        try: gpu_info = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle); gpu_util = float(gpu_info.gpu)
                        except pynvml.NVMLError as e: logger.warning(f"NVML error getting GPU util: {e}. Re-attempting init if needed."); gpu_util = -2.0; gpu_name_to_emit = f"NVML Read Err (Code: {e.value})" if hasattr(e, 'value') else "NVML Read Err"; self._nvml_initialized = False; self._attempt_nvml_init(from_worker_loop=True)
                        except Exception as e_gen: logger.error(f"Unexpected error getting GPU util: {e_gen}"); gpu_util = -3.0; gpu_name_to_emit = "GPU Mon. Err"
                    elif PYNVML_AVAILABLE and not self._nvml_initialized: self._attempt_nvml_init(from_worker_loop=True)
                    if not (worker_thread.isInterruptionRequested() or self._stop_requested): self.resourceUpdate.emit(cpu_usage, ram_percent, gpu_util, gpu_name_to_emit)
                    last_data_emit_time = current_loop_time
                except Exception as e: logger.error(f"ResourceMonitorWorker: Error in data collection: {e}", exc_info=False); \
                                         (not (worker_thread.isInterruptionRequested() or self._stop_requested) and self.resourceUpdate.emit(-1.0, -1.0, -3.0, "Data Error"))
            inner_loop_checks = int(self.data_collection_interval_ms / self.WORKER_LOOP_CHECK_INTERVAL_MS) + 1
            if inner_loop_checks <= 0: inner_loop_checks = 1
            for _i in range(inner_loop_checks):
                if worker_thread.isInterruptionRequested() or self._stop_requested: break
                QThread.msleep(self.WORKER_LOOP_CHECK_INTERVAL_MS)
            if worker_thread.isInterruptionRequested() or self._stop_requested: logger.debug("ResourceMonitorWorker: Exiting main while loop due to interruption/stop request."); break
        logger.info(f"ResourceMonitorWorker: _monitor_resources loop EXITED (Interruption: {worker_thread.isInterruptionRequested()}, StopFlag: {self._stop_requested}). Emitting finished_signal."); self.finished_signal.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - Untitled [*]")

        self.current_file_path = None
        self.undo_stack = QUndoStack(self)
        self.scene = DiagramScene(self.undo_stack, self)
        self.view: ZoomableView | None = None 
        self.alignment_manager = AlignmentManager(self)
        
        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False
        self.find_item_dialog: FindItemDialog | None = None

        self.matlab_connection = MatlabConnection()
        self.file_op_manager = FileOperationsManager(self)
        self.ide_manager = IDEManager(self)
        self.matlab_op_manager = MatlabOperationsManager(self, self.matlab_connection)
        self.view_manager = ViewManager(self)
        self.ai_chatbot_manager = AIChatbotManager(self) 
        self.ai_chat_ui_manager = AIChatUIManager(self)
        self.py_sim_ui_manager = PySimulationUIManager(self)

        self._internet_connected: bool | None = None
        self.internet_check_timer = QTimer(self)
        self.resource_monitor_worker: ResourceMonitorWorker | None = None
        self.resource_monitor_thread: QThread | None = None

        self.init_ui() 

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

        self._populate_dynamic_docks() 
        self._connect_signals() 

        self._init_resource_monitor()
        self._init_internet_status_check()

        self._set_status_label_object_names() 
        self._update_ui_element_states() 
        QTimer.singleShot(0, lambda: self.on_new_file_orchestrator(silent=True))
        if self.ai_chat_ui_manager and self.ai_chatbot_manager:
            QTimer.singleShot(250, lambda: self.ai_chatbot_manager.set_online_status(
                self._internet_connected if self._internet_connected is not None else False
            ))
        else:
            logger.warning("MainWindow: ai_chat_ui_manager or ai_chatbot_manager not fully initialized for final status update.")

    def _connect_signals(self):
        if hasattr(self, 'scene') and self.scene: 
            self.scene.selectionChanged.connect(self._update_align_distribute_actions_enable_state)
            self.scene.scene_content_changed_for_find.connect(self._refresh_find_dialog_if_visible)
            self.scene.modifiedStatusChanged.connect(self.setWindowModified)
            self.scene.selectionChanged.connect(self._update_properties_dock)
            self.scene.modifiedStatusChanged.connect(self.update_window_title)
            self.scene.validation_issues_updated.connect(self.update_problems_dock)
        else: logger.error("MainWindow._connect_signals: self.scene is not initialized.")
        if self.py_sim_ui_manager:
            self.py_sim_ui_manager.simulationStateChanged.connect(self._handle_py_sim_state_changed_by_manager)
            self.py_sim_ui_manager.requestGlobalUIEnable.connect(self._handle_py_sim_global_ui_enable_by_manager)
        else: logger.error("MainWindow._connect_signals: self.py_sim_ui_manager is not initialized.")

    def update_window_title(self): 
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        ide_dock_title = "Standalone Code IDE"; ide_simple_status_for_main_title = ""
        if self.ide_manager and self.ide_manager.ide_dock:
            current_ide_lang_text = self.ide_manager.ide_language_combo.currentText() if self.ide_manager.ide_language_combo else ""
            lang_info = f" ({current_ide_lang_text})" if current_ide_lang_text else ""
            if self.ide_manager.current_ide_file_path:
                ide_fn = os.path.basename(self.ide_manager.current_ide_file_path); ide_dock_title = f"IDE: {ide_fn}{'*' if self.ide_manager.ide_editor_is_dirty else ''}{lang_info}"; ide_simple_status_for_main_title = f"IDE: {ide_fn}{'*' if self.ide_manager.ide_editor_is_dirty else ''}"
            elif self.ide_manager.ide_code_editor and self.ide_manager.ide_code_editor.toPlainText().strip(): ide_dock_title = f"IDE: Untitled Script{'*' if self.ide_manager.ide_editor_is_dirty else ''}{lang_info}"; ide_simple_status_for_main_title = f"IDE: Untitled Script{'*' if self.ide_manager.ide_editor_is_dirty else ''}"
            else: ide_dock_title = f"Standalone Code IDE{lang_info}"
            self.ide_manager.ide_dock.setWindowTitle(ide_dock_title)
        sim_status_suffix = " [PySim Running]" if self.py_sim_active else ""
        if self.py_sim_active and self.py_fsm_engine and self.py_fsm_engine.paused_on_breakpoint: sim_status_suffix += " (Paused)"
        main_window_is_dirty = (hasattr(self,'scene') and self.scene.is_dirty()) or (self.ide_manager and self.ide_manager.ide_editor_is_dirty)
        self.setWindowModified(main_window_is_dirty)
        title = f"{APP_NAME} - {file_name}{sim_status_suffix} [*]"; self.setWindowTitle(title)
        if hasattr(self, 'status_label'):
            main_file_status = f"File: {file_name}{' *' if hasattr(self,'scene') and self.scene.is_dirty() else ''}"; pysim_status = f"PySim: {'Active' if self.py_sim_active else 'Idle'}"
            if self.py_sim_active and self.py_fsm_engine and self.py_fsm_engine.paused_on_breakpoint: pysim_status += " (Paused)"
            ide_status_for_bar = ide_simple_status_for_main_title; full_status_text_parts = [main_file_status, pysim_status]
            if ide_status_for_bar: full_status_text_parts.append(ide_status_for_bar)
            self.status_label.setText(" | ".join(p for p in full_status_text_parts if p))

    def _set_status_label_object_names(self):
        if hasattr(self, 'status_label'): self.status_label.setObjectName("StatusLabel")
        if hasattr(self, 'zoom_status_label'): self.zoom_status_label.setObjectName("ZoomStatusLabel")
        if hasattr(self, 'cpu_status_label'): self.cpu_status_label.setObjectName("CpuStatusLabel"); self.ram_status_label.setObjectName("RamStatusLabel"); self.gpu_status_label.setObjectName("GpuStatusLabel")
        if hasattr(self, 'py_sim_status_label'): self.py_sim_status_label.setObjectName("PySimStatusLabel")
        if hasattr(self, 'matlab_status_label'): self.matlab_status_label.setObjectName("MatlabStatusLabel")
        if hasattr(self, 'internet_status_label'): self.internet_status_label.setObjectName("InternetStatusLabel")

    def _update_ui_element_states(self):
        self._update_properties_dock(); self._update_py_simulation_actions_enabled_state()
        if self.view_manager: self.view_manager.update_zoom_to_selection_action_enable_state()
        if self.alignment_manager: self.alignment_manager.update_align_distribute_actions_enable_state()
        if hasattr(self, 'view') and self.view and self.view_manager: self.view_manager.update_zoom_status_display(self.view.transform().m11())

    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050); self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM"))
        self._create_central_widget(); self._create_actions()
        if self.view_manager: self.view_manager.connect_zoom_actions(); self.view_manager.connect_snap_actions()
        self._create_menus(); self._create_toolbars(); self._create_docks(); self._create_status_bar()
        self._update_save_actions_enable_state()
        if self.matlab_op_manager: self.matlab_op_manager.update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger()

    def _populate_dynamic_docks(self):
        if self.py_sim_ui_manager and hasattr(self, 'py_sim_dock') and self.py_sim_dock: self.py_sim_dock.setWidget(self.py_sim_ui_manager.create_dock_widget_contents())
        else: logger.error("Could not populate Python Simulation Dock.")
        if self.ai_chat_ui_manager and hasattr(self, 'ai_chatbot_dock') and self.ai_chatbot_dock:
            self.ai_chatbot_dock.setWidget(self.ai_chat_ui_manager.create_dock_widget_contents())
            if hasattr(self.ai_chat_ui_manager, 'ai_chat_status_label') and self.ai_chat_ui_manager.ai_chat_status_label: self.ai_chat_ui_manager.ai_chat_status_label.setObjectName("AIChatStatusLabel")
        else: logger.error("Could not populate AI Chatbot Dock.")
        docks_to_tabify = [(self.properties_dock, self.ai_chatbot_dock), (self.ai_chatbot_dock, self.py_sim_dock), (self.py_sim_dock, self.ide_dock if hasattr(self, 'ide_dock') else None), (self.log_dock, self.problems_dock)]
        for dock1, dock2 in docks_to_tabify:
            if dock1 and dock2:
                try: self.tabifyDockWidget(dock1, dock2)
                except Exception as e: logger.error(f"Error tabifying docks {dock1.objectName()} and {dock2.objectName()}: {e}")
            else: logger.warning(f"Skipping tabify for {getattr(dock1, 'objectName', lambda:'N/A')()} and {getattr(dock2, 'objectName', lambda:'N/A')()}")

    def _create_central_widget(self): self.view = ZoomableView(self.scene, self); self.view.setObjectName("MainDiagramView"); self.view.setStyleSheet(f"background-color: {COLOR_BACKGROUND_LIGHT}; border: 1px solid {COLOR_BORDER_LIGHT};"); self.setCentralWidget(self.view)

    def _create_actions(self):
        def _safe_get_style_enum(attr_name, fallback_attr_name=None):
            try: return getattr(QStyle, attr_name)
            except AttributeError:
                if fallback_attr_name:
                    try: return getattr(QStyle, fallback_attr_name)
                    except AttributeError: pass
                return QStyle.SP_CustomBase 
        self.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "New"), "&New", self, shortcut=QKeySequence.New, statusTip="Create a new file", triggered=lambda: self.on_new_file_orchestrator(silent=False))
        self.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "Opn"), "&Open...", self, shortcut=QKeySequence.Open, statusTip="Open an existing file", triggered=self.on_open_file_orchestrator)
        self.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Sav"), "&Save", self, shortcut=QKeySequence.Save, statusTip="Save the current file", triggered=self.file_op_manager.on_save_file)
        self.save_as_action = QAction(get_standard_icon(_safe_get_style_enum("SP_DriveHDIcon", "SP_DialogSaveButton"), "SA"), "Save &As...", self, shortcut=QKeySequence.SaveAs, statusTip="Save current file with new name", triggered=self.file_op_manager.on_save_file_as)
        self.generate_c_code_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "CGen"), "Generate &Basic C Code...", self, triggered=self.on_generate_c_code)
        self.exit_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", self, shortcut=QKeySequence.Quit, statusTip="Exit application", triggered=self.close)
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
        self.add_history_shallow_mode_action = QAction(get_standard_icon(QStyle.SP_FileDialogDetailedView, "H"), "Add Shallow History (H)", self, checkable=True, statusTip="Add Shallow History (H) inside a superstate"); self.add_history_shallow_mode_action.setObjectName("add_history_shallow_mode_action"); self.add_history_shallow_mode_action.triggered.connect(lambda: self.scene.set_mode("history_shallow"))
        for action in [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action, self.add_history_shallow_mode_action]: self.mode_action_group.addAction(action)
        self.select_mode_action.setChecked(True)
        self.export_simulink_action = QAction(get_standard_icon(_safe_get_style_enum("SP_ArrowUp","SP_ArrowRight"), "->M"), "&Export to Simulink...", self, triggered=self.matlab_op_manager.on_export_simulink)
        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation (MATLAB)...", self, triggered=self.matlab_op_manager.on_run_simulation)
        self.generate_matlab_code_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "CdeM"), "Generate &Code (C/C++ via MATLAB)...", self, triggered=self.matlab_op_manager.on_generate_matlab_code)
        self.matlab_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"), "&MATLAB Settings...", self, triggered=self.matlab_op_manager.on_matlab_settings)
        self.start_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Py▶"), "&Start Python Simulation", self, statusTip="Start internal FSM simulation", triggered=self.py_sim_ui_manager.on_start_py_simulation)
        self.stop_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaStop, "Py■"), "S&top Python Simulation", self, statusTip="Stop internal FSM simulation", enabled=False, triggered=lambda: self.py_sim_ui_manager.on_stop_py_simulation(silent=False))
        self.reset_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaSkipBackward, "Py«"), "&Reset Python Simulation", self, statusTip="Reset internal FSM simulation", enabled=False, triggered=self.py_sim_ui_manager.on_reset_py_simulation)
        self.openai_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "AISet"), "AI Assistant Settings (Gemini)...", self, triggered=self.ai_chat_ui_manager.on_gemini_settings)
        self.clear_ai_chat_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "Clear"), "Clear Chat History", self, triggered=self.ai_chat_ui_manager.on_clear_ai_chat_history)
        self.ask_ai_to_generate_fsm_action = QAction(get_standard_icon(QStyle.SP_ArrowRight, "AIGen"), "Generate FSM from Description...", self, triggered=self.ai_chat_ui_manager.on_ask_ai_to_generate_fsm)
        self.open_example_menu_action = QAction("Open E&xample...", self)
        self.quick_start_action = QAction(get_standard_icon(QStyle.SP_MessageBoxQuestion, "QS"), "&Quick Start Guide", self, triggered=self.on_show_quick_start)
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, triggered=self.on_about)
        self.zoom_in_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Z+"), "Zoom In", self, shortcut="Ctrl++", statusTip="Zoom in"); self.zoom_out_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "Z-"), "Zoom Out", self, shortcut="Ctrl+-", statusTip="Zoom out")
        self.reset_zoom_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "Z0"), "Reset Zoom/View", self, shortcut="Ctrl+0", statusTip="Reset zoom and center view")
        self.zoom_to_selection_action = QAction(get_standard_icon(QStyle.SP_FileDialogDetailedView, "ZSel"), "Zoom to Selection", self, statusTip="Zoom to fit selected items")
        self.fit_diagram_action = QAction(get_standard_icon(QStyle.SP_FileDialogListView, "ZFit"), "Fit Diagram in View", self, statusTip="Fit entire diagram in view")
        self.snap_to_objects_action = QAction("Snap to Objects", self, checkable=True, statusTip="Enable/disable snapping to object edges/centers")
        self.snap_to_grid_action = QAction("Snap to Grid", self, checkable=True, statusTip="Enable/disable snapping to grid")
        self.show_snap_guidelines_action = QAction("Show Dynamic Snap Guidelines", self, checkable=True, statusTip="Show/hide dynamic alignment guidelines")
        self.align_left_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "AlL"), "Align Left", self, statusTip="Align selected items left", triggered=lambda: self.alignment_manager.on_align_items("left"))
        self.align_center_h_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "AlCH"), "Align Center Horizontally", self, statusTip="Align selected items to horizontal center", triggered=lambda: self.alignment_manager.on_align_items("center_h"))
        self.align_right_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "AlR"), "Align Right", self, statusTip="Align selected items right", triggered=lambda: self.alignment_manager.on_align_items("right"))
        self.align_top_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "AlT"), "Align Top", self, statusTip="Align selected items top", triggered=lambda: self.alignment_manager.on_align_items("top"))
        self.align_middle_v_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "AlMV"), "Align Middle Vertically", self, statusTip="Align selected items to vertical middle", triggered=lambda: self.alignment_manager.on_align_items("middle_v"))
        self.align_bottom_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "AlB"), "Align Bottom", self, statusTip="Align selected items bottom", triggered=lambda: self.alignment_manager.on_align_items("bottom"))
        self.distribute_h_action = QAction(get_standard_icon(QStyle.SP_ArrowLeft, "DstH"), "Distribute Horizontally", self, statusTip="Distribute selected items horizontally", triggered=lambda: self.alignment_manager.on_distribute_items("horizontal"))
        self.distribute_v_action = QAction(get_standard_icon(QStyle.SP_ArrowUp, "DstV"), "Distribute Vertically", self, statusTip="Distribute selected items vertically", triggered=lambda: self.alignment_manager.on_distribute_items("vertical"))
        self.align_actions = [self.align_left_action, self.align_center_h_action, self.align_right_action, self.align_top_action, self.align_middle_v_action, self.align_bottom_action]
        self.distribute_actions = [self.distribute_h_action, self.distribute_v_action]
        self.ide_new_file_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "IDENew"), "New Script", self, triggered=self.ide_manager.on_ide_new_file)
        self.ide_open_file_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "IDEOpn"), "Open Script...", self, triggered=self.ide_manager.on_ide_open_file)
        self.ide_save_file_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "IDESav"), "Save Script", self, triggered=self.ide_manager.on_ide_save_file)
        self.ide_save_as_file_action = QAction(get_standard_icon(_safe_get_style_enum("SP_DriveHDIcon", "SP_DialogSaveButton"), "IDESA"), "Save Script As...", self, triggered=self.ide_manager.on_ide_save_as_file)
        self.ide_run_script_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "IDERunPy"), "Run Python Script", self, triggered=self.ide_manager.on_ide_run_python_script)
        self.ide_analyze_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "IDEAI"), "Analyze with AI", self, triggered=self.ide_manager.on_ide_analyze_with_ai)
        self.find_item_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "Find"), "&Find Item...", self, shortcut=QKeySequence.Find, statusTip="Find FSM element", triggered=self.on_show_find_item_dialog)
        if self.view_manager: self.view_manager.connect_zoom_actions(); self.view_manager.connect_snap_actions()
        else: logger.error("ViewManager not initialized when connecting actions in _create_actions.")

    def _create_menus(self):
        menu_bar = self.menuBar(); file_menu = menu_bar.addMenu("&File"); file_menu.addAction(self.new_action); file_menu.addAction(self.open_action)
        example_menu = file_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ex"), "Open E&xample")
        self.open_example_traffic_action = example_menu.addAction("Traffic Light FSM", lambda: self.on_open_example_file_orchestrator("traffic_light.bsm"))
        self.open_example_toggle_action = example_menu.addAction("Simple Toggle FSM", lambda: self.on_open_example_file_orchestrator("simple_toggle.bsm"))
        export_menu = file_menu.addMenu("E&xport");
        if hasattr(self, 'export_simulink_action'): export_menu.addAction(self.export_simulink_action)
        if hasattr(self, 'generate_c_code_action'): export_menu.addAction(self.generate_c_code_action)
        file_menu.addAction(self.save_action); file_menu.addAction(self.save_as_action); file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        edit_menu = menu_bar.addMenu("&Edit"); edit_menu.addAction(self.undo_action); edit_menu.addAction(self.redo_action); edit_menu.addSeparator()
        edit_menu.addAction(self.delete_action); edit_menu.addAction(self.select_all_action); edit_menu.addSeparator()
        if hasattr(self, 'find_item_action'): edit_menu.addAction(self.find_item_action)
        edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Mode"),"Interaction Mode")
        mode_menu.addAction(self.select_mode_action); mode_menu.addAction(self.add_state_mode_action); mode_menu.addAction(self.add_transition_mode_action); mode_menu.addAction(self.add_comment_mode_action)
        if hasattr(self, 'add_history_shallow_mode_action'): mode_menu.addAction(self.add_history_shallow_mode_action)
        edit_menu.addSeparator()
        align_distribute_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogDetailedView, "AD"), "Align & Distribute"); align_menu = align_distribute_menu.addMenu("Align")
        if hasattr(self, 'align_left_action'): align_menu.addAction(self.align_left_action); if hasattr(self, 'align_center_h_action'): align_menu.addAction(self.align_center_h_action); if hasattr(self, 'align_right_action'): align_menu.addAction(self.align_right_action)
        align_menu.addSeparator(); if hasattr(self, 'align_top_action'): align_menu.addAction(self.align_top_action); if hasattr(self, 'align_middle_v_action'): align_menu.addAction(self.align_middle_v_action); if hasattr(self, 'align_bottom_action'): align_menu.addAction(self.align_bottom_action)
        distribute_menu = align_distribute_menu.addMenu("Distribute"); if hasattr(self, 'distribute_h_action'): distribute_menu.addAction(self.distribute_h_action); if hasattr(self, 'distribute_v_action'): distribute_menu.addAction(self.distribute_v_action)
        sim_menu = menu_bar.addMenu("&Simulation"); py_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_MediaPlay, "PyS"), "Python Simulation (Internal)")
        if hasattr(self, 'start_py_sim_action'): py_sim_menu.addAction(self.start_py_sim_action); if hasattr(self, 'stop_py_sim_action'): py_sim_menu.addAction(self.stop_py_sim_action); if hasattr(self, 'reset_py_sim_action'): py_sim_menu.addAction(self.reset_py_sim_action)
        sim_menu.addSeparator(); matlab_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_ComputerIcon, "M"), "MATLAB/Simulink")
        if hasattr(self, 'run_simulation_action'): matlab_sim_menu.addAction(self.run_simulation_action); if hasattr(self, 'generate_matlab_code_action'): matlab_sim_menu.addAction(self.generate_matlab_code_action)
        matlab_sim_menu.addSeparator(); if hasattr(self, 'matlab_settings_action'): matlab_sim_menu.addAction(self.matlab_settings_action)
        self.view_menu = menu_bar.addMenu("&View"); if hasattr(self, 'zoom_in_action'): self.view_menu.addAction(self.zoom_in_action); if hasattr(self, 'zoom_out_action'): self.view_menu.addAction(self.zoom_out_action); if hasattr(self, 'reset_zoom_action'): self.view_menu.addAction(self.reset_zoom_action)
        self.view_menu.addSeparator(); if hasattr(self, 'zoom_to_selection_action'): self.view_menu.addAction(self.zoom_to_selection_action); if hasattr(self, 'fit_diagram_action'): self.view_menu.addAction(self.fit_diagram_action)
        self.view_menu.addSeparator(); snap_menu = self.view_menu.addMenu("Snapping")
        if hasattr(self, 'snap_to_grid_action'): snap_menu.addAction(self.snap_to_grid_action); if hasattr(self, 'snap_to_objects_action'): snap_menu.addAction(self.snap_to_objects_action); if hasattr(self, 'show_snap_guidelines_action'): snap_menu.addAction(self.show_snap_guidelines_action)
        self.view_menu.addSeparator()
        tools_menu = menu_bar.addMenu("&Tools"); ide_menu = tools_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogDetailedView, "IDE"), "Standalone Code IDE")
        if hasattr(self, 'ide_new_file_action'): ide_menu.addAction(self.ide_new_file_action); if hasattr(self, 'ide_open_file_action'): ide_menu.addAction(self.ide_open_file_action); if hasattr(self, 'ide_save_file_action'): ide_menu.addAction(self.ide_save_file_action); if hasattr(self, 'ide_save_as_file_action'): ide_menu.addAction(self.ide_save_as_file_action)
        ide_menu.addSeparator(); if hasattr(self, 'ide_run_script_action'): ide_menu.addAction(self.ide_run_script_action); if hasattr(self, 'ide_analyze_action'): ide_menu.addAction(self.ide_analyze_action)
        ai_menu = menu_bar.addMenu("&AI Assistant"); if hasattr(self, 'ask_ai_to_generate_fsm_action'): ai_menu.addAction(self.ask_ai_to_generate_fsm_action); if hasattr(self, 'clear_ai_chat_action'): ai_menu.addAction(self.clear_ai_chat_action)
        ai_menu.addSeparator(); if hasattr(self, 'openai_settings_action'): ai_menu.addAction(self.openai_settings_action)
        help_menu = menu_bar.addMenu("&Help"); if hasattr(self, 'quick_start_action'): help_menu.addAction(self.quick_start_action); if hasattr(self, 'about_action'): help_menu.addAction(self.about_action)    

    def _create_toolbars(self):
        icon_size = QSize(22, 22); tb_style_icon_only = Qt.ToolButtonIconOnly; tb_style_text_beside = Qt.ToolButtonTextBesideIcon
        file_toolbar = self.addToolBar("File"); file_toolbar.setObjectName("FileToolBar"); file_toolbar.setIconSize(icon_size); file_toolbar.setToolButtonStyle(tb_style_icon_only)
        if hasattr(self, 'new_action'): file_toolbar.addAction(self.new_action); if hasattr(self, 'open_action'): file_toolbar.addAction(self.open_action); if hasattr(self, 'save_action'): file_toolbar.addAction(self.save_action)
        edit_toolbar = self.addToolBar("Edit"); edit_toolbar.setObjectName("EditToolBar"); edit_toolbar.setIconSize(icon_size); edit_toolbar.setToolButtonStyle(tb_style_icon_only)
        if hasattr(self, 'undo_action'): edit_toolbar.addAction(self.undo_action); if hasattr(self, 'redo_action'): edit_toolbar.addAction(self.redo_action); edit_toolbar.addSeparator()
        if hasattr(self, 'delete_action'): edit_toolbar.addAction(self.delete_action); if hasattr(self, 'find_item_action'): edit_toolbar.addAction(self.find_item_action)
        tools_tb = self.addToolBar("Interaction Tools"); tools_tb.setObjectName("ToolsToolBar"); tools_tb.setIconSize(icon_size); tools_tb.setToolButtonStyle(tb_style_text_beside)
        if hasattr(self, 'select_mode_action'): tools_tb.addAction(self.select_mode_action); if hasattr(self, 'add_state_mode_action'): tools_tb.addAction(self.add_state_mode_action)
        if hasattr(self, 'add_transition_mode_action'): tools_tb.addAction(self.add_transition_mode_action); if hasattr(self, 'add_comment_mode_action'): tools_tb.addAction(self.add_comment_mode_action)
        if hasattr(self, 'add_history_shallow_mode_action'): tools_tb.addAction(self.add_history_shallow_mode_action) # Added
        code_gen_export_toolbar = self.addToolBar("Code Generation & Export"); code_gen_export_toolbar.setObjectName("CodeGenExportToolBar"); code_gen_export_toolbar.setIconSize(icon_size); code_gen_export_toolbar.setToolButtonStyle(tb_style_icon_only)
        if hasattr(self, 'export_simulink_action'): code_gen_export_toolbar.addAction(self.export_simulink_action); if hasattr(self, 'generate_matlab_code_action'): code_gen_export_toolbar.addAction(self.generate_matlab_code_action); if hasattr(self, 'generate_c_code_action'): code_gen_export_toolbar.addAction(self.generate_c_code_action)
        sim_toolbar = self.addToolBar("Simulation Tools"); sim_toolbar.setObjectName("SimulationToolBar"); sim_toolbar.setIconSize(icon_size); sim_toolbar.setToolButtonStyle(tb_style_icon_only)
        if hasattr(self, 'start_py_sim_action'): sim_toolbar.addAction(self.start_py_sim_action); if hasattr(self, 'stop_py_sim_action'): sim_toolbar.addAction(self.stop_py_sim_action); if hasattr(self, 'reset_py_sim_action'): sim_toolbar.addAction(self.reset_py_sim_action)
        sim_toolbar.addSeparator(); if hasattr(self, 'run_simulation_action'): sim_toolbar.addAction(self.run_simulation_action)
        view_toolbar = self.addToolBar("View Tools"); view_toolbar.setObjectName("ViewToolBar"); view_toolbar.setIconSize(icon_size); view_toolbar.setToolButtonStyle(tb_style_icon_only)
        if hasattr(self, 'zoom_in_action'): view_toolbar.addAction(self.zoom_in_action); if hasattr(self, 'zoom_out_action'): view_toolbar.addAction(self.zoom_out_action); if hasattr(self, 'reset_zoom_action'): view_toolbar.addAction(self.reset_zoom_action)
        view_toolbar.addSeparator(); if hasattr(self, 'zoom_to_selection_action'): view_toolbar.addAction(self.zoom_to_selection_action); if hasattr(self, 'fit_diagram_action'): view_toolbar.addAction(self.fit_diagram_action)
        align_toolbar = self.addToolBar("Alignment & Distribution"); align_toolbar.setObjectName("AlignDistributeToolBar"); align_toolbar.setIconSize(icon_size); align_toolbar.setToolButtonStyle(tb_style_icon_only)
        if hasattr(self, 'align_left_action'): align_toolbar.addAction(self.align_left_action); if hasattr(self, 'align_center_h_action'): align_toolbar.addAction(self.align_center_h_action); if hasattr(self, 'align_right_action'): align_toolbar.addAction(self.align_right_action)
        align_toolbar.addSeparator(); if hasattr(self, 'align_top_action'): align_toolbar.addAction(self.align_top_action); if hasattr(self, 'align_middle_v_action'): align_toolbar.addAction(self.align_middle_v_action); if hasattr(self, 'align_bottom_action'): align_toolbar.addAction(self.align_bottom_action)
        align_toolbar.addSeparator(); if hasattr(self, 'distribute_h_action'): align_toolbar.addAction(self.distribute_h_action); if hasattr(self, 'distribute_v_action'): align_toolbar.addAction(self.distribute_v_action)
    
    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)
        self.tools_dock = QDockWidget("Elements & Modes", self); self.tools_dock.setObjectName("ToolsDock")
        tools_widget_main = QWidget(); tools_widget_main.setObjectName("ToolsDockWidgetContents"); tools_main_layout = QVBoxLayout(tools_widget_main); tools_main_layout.setSpacing(8); tools_main_layout.setContentsMargins(8,8,8,8)
        mode_group_box = QGroupBox("Interaction Mode"); mode_layout = QVBoxLayout(); mode_layout.setSpacing(6)
        self.toolbox_select_button = QToolButton(); self.toolbox_select_button.setDefaultAction(self.select_mode_action)
        self.toolbox_add_state_button = QToolButton(); self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action)
        self.toolbox_transition_button = QToolButton(); self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action)
        self.toolbox_add_comment_button = QToolButton(); self.toolbox_add_comment_button.setDefaultAction(self.add_comment_mode_action)
        if hasattr(self, 'add_history_shallow_mode_action'): self.toolbox_add_history_shallow_button = QToolButton(); self.toolbox_add_history_shallow_button.setDefaultAction(self.add_history_shallow_mode_action)
        buttons_for_mode_group = [self.toolbox_select_button, self.toolbox_add_state_button, self.toolbox_transition_button, self.toolbox_add_comment_button]
        if hasattr(self, 'toolbox_add_history_shallow_button'): buttons_for_mode_group.append(self.toolbox_add_history_shallow_button)
        for btn in buttons_for_mode_group: btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(20,20)); mode_layout.addWidget(btn)
        mode_group_box.setLayout(mode_layout); tools_main_layout.addWidget(mode_group_box)
        draggable_group_box = QGroupBox("Drag New Elements"); draggable_layout = QVBoxLayout(); draggable_layout.setSpacing(6)
        drag_state_btn = DraggableToolButton("State", "application/x-bsm-tool", "State"); drag_state_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))
        drag_initial_state_btn = DraggableToolButton("Initial State", "application/x-bsm-tool", "Initial State"); drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt"))
        drag_final_state_btn = DraggableToolButton("Final State", "application/x-bsm-tool", "Final State"); drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt"))
        drag_comment_btn = DraggableToolButton("Comment", "application/x-bsm-tool", "Comment"); drag_comment_btn.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))
        # drag_history_shallow_btn = DraggableToolButton("Shallow History (H)", "application/x-bsm-tool", "HistoryShallow"); drag_history_shallow_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "HDrag")) # Optional
        buttons_for_drag_group = [drag_state_btn, drag_initial_state_btn, drag_final_state_btn, drag_comment_btn] # if 'drag_history_shallow_btn' in locals(): buttons_for_drag_group.append(drag_history_shallow_btn)
        for btn in buttons_for_drag_group: draggable_layout.addWidget(btn)
        draggable_group_box.setLayout(draggable_layout); tools_main_layout.addWidget(draggable_group_box)
        self.templates_group_box = QGroupBox("FSM Templates"); templates_layout = QVBoxLayout(); templates_layout.setSpacing(6); self.template_buttons_container = QWidget(); self.template_buttons_layout = QVBoxLayout(self.template_buttons_container); self.template_buttons_layout.setContentsMargins(0,0,0,0); self.template_buttons_layout.setSpacing(4); templates_layout.addWidget(self.template_buttons_container); templates_layout.addStretch(); self.templates_group_box.setLayout(templates_layout); tools_main_layout.addWidget(self.templates_group_box)
        tools_main_layout.addStretch(); self.tools_dock.setWidget(tools_widget_main); self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock)
        self.properties_dock = QDockWidget("Item Properties", self); self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock_widget_main = QWidget(); self.properties_dock_main_layout = QVBoxLayout(self.properties_dock_widget_main); self.properties_dock_main_layout.setContentsMargins(8,8,8,8); self.properties_dock_main_layout.setSpacing(6)
        self.properties_placeholder_label = QLabel("<i>Select a single item to view/edit its properties.</i>"); self.properties_placeholder_label.setObjectName("PropertiesLabel"); self.properties_placeholder_label.setWordWrap(True); self.properties_placeholder_label.setTextFormat(Qt.RichText); self.properties_placeholder_label.setAlignment(Qt.AlignTop | Qt.AlignLeft); self.properties_dock_main_layout.addWidget(self.properties_placeholder_label)
        self.properties_editor_container = QWidget(); self.properties_editor_layout = QFormLayout(self.properties_editor_container); self.properties_editor_layout.setContentsMargins(0,0,0,0); self.properties_editor_layout.setSpacing(8); self.properties_dock_main_layout.addWidget(self.properties_editor_container); self.properties_editor_container.setVisible(False); self.properties_dock_main_layout.addStretch(1)
        self.properties_apply_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton, "Apply"), "Apply Changes"); self.properties_apply_button.setEnabled(False); self.properties_apply_button.clicked.connect(self._on_apply_dock_properties)
        self.properties_revert_button = QPushButton(get_standard_icon(QStyle.SP_DialogCancelButton, "Revert"), "Revert"); self.properties_revert_button.setEnabled(False); self.properties_revert_button.clicked.connect(self._on_revert_dock_properties)
        self.properties_edit_dialog_button = QPushButton(get_standard_icon(QStyle.SP_FileDialogDetailedView, "AdvEdit"), "Advanced Edit..."); self.properties_edit_dialog_button.setToolTip("Open full properties dialog"); self.properties_edit_dialog_button.setEnabled(False); self.properties_edit_dialog_button.clicked.connect(self._on_edit_selected_item_properties_from_dock_button)
        button_layout_props = QHBoxLayout(); button_layout_props.addWidget(self.properties_revert_button); button_layout_props.addStretch(); button_layout_props.addWidget(self.properties_apply_button); self.properties_dock_main_layout.addLayout(button_layout_props); self.properties_dock_main_layout.addWidget(self.properties_edit_dialog_button)
        self.properties_dock.setWidget(self.properties_dock_widget_main); self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock); self._dock_property_editors = {}; self._current_edited_item_in_dock = None
        self.log_dock = QDockWidget("Application Log", self); self.log_dock.setObjectName("LogDock"); log_widget = QWidget(); log_layout = QVBoxLayout(log_widget); log_layout.setContentsMargins(0,0,0,0); self.log_output = QTextEdit(); self.log_output.setObjectName("LogOutputWidget"); self.log_output.setReadOnly(True); log_layout.addWidget(self.log_output); self.log_dock.setWidget(log_widget); self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock); self.log_dock.setVisible(True)
        self.problems_dock = QDockWidget("Validation Issues", self); self.problems_dock.setObjectName("ProblemsDock"); self.problems_list_widget = QListWidget(); self.problems_list_widget.itemDoubleClicked.connect(self.on_problem_item_double_clicked); self.problems_dock.setWidget(self.problems_list_widget); self.addDockWidget(Qt.BottomDockWidgetArea, self.problems_dock); self.problems_dock.setVisible(True)
        self.py_sim_dock = QDockWidget("Python Simulation", self); self.py_sim_dock.setObjectName("PySimDock"); self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock); self.py_sim_dock.setVisible(False)
        self.ai_chatbot_dock = QDockWidget("AI Assistant", self); self.ai_chatbot_dock.setObjectName("AIChatbotDock"); self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock); self.ai_chatbot_dock.setVisible(False)
        if self.ide_manager: self.ide_dock = self.ide_manager.setup_ide_dock_widget();
                           if self.ide_dock: self.ide_dock.setVisible(False)
                           else: logger.error("Failed to setup IDE dock via IDEManager.")
        else: logger.error("IDEManager not available.")
        if hasattr(self, 'view_menu'): # Add dock toggles to View menu
            for dock in [self.tools_dock, self.properties_dock, self.log_dock, self.problems_dock, self.py_sim_dock, self.ai_chatbot_dock]:
                if dock: self.view_menu.addAction(dock.toggleViewAction())
            if hasattr(self, 'ide_dock') and self.ide_dock: self.view_menu.addAction(self.ide_dock.toggleViewAction())
        self._load_and_display_templates()

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self); self.setStatusBar(self.status_bar); self.status_label = QLabel("Ready"); self.status_bar.addWidget(self.status_label, 1)
        self.zoom_status_label = QLabel("Zoom: 100%"); self.zoom_status_label.setMinimumWidth(80); self.zoom_status_label.setAlignment(Qt.AlignCenter); self.status_bar.addPermanentWidget(self.zoom_status_label)
        self.cpu_status_label = QLabel("CPU: --%"); self.cpu_status_label.setToolTip("CPU Usage"); self.ram_status_label = QLabel("RAM: --%"); self.ram_status_label.setToolTip("RAM Usage")
        self.gpu_status_label = QLabel("GPU: N/A"); self.gpu_status_label.setToolTip("GPU Usage (NVIDIA only)")
        for label in [self.cpu_status_label, self.ram_status_label, self.gpu_status_label]: label.setMinimumWidth(80); label.setAlignment(Qt.AlignCenter); self.status_bar.addPermanentWidget(label)
        self.py_sim_status_label = QLabel("PySim: Idle"); self.py_sim_status_label.setToolTip("Internal Python FSM Simulation Status."); self.py_sim_status_label.setMinimumWidth(120); self.py_sim_status_label.setAlignment(Qt.AlignCenter); self.status_bar.addPermanentWidget(self.py_sim_status_label)
        self.matlab_status_label = QLabel("MATLAB: Init..."); self.matlab_status_label.setToolTip("MATLAB connection status."); self.matlab_status_label.setMinimumWidth(140); self.matlab_status_label.setAlignment(Qt.AlignCenter); self.status_bar.addPermanentWidget(self.matlab_status_label)
        self.internet_status_label = QLabel("Net: Init..."); self.internet_status_label.setToolTip("Internet connectivity."); self.internet_status_label.setMinimumWidth(90); self.internet_status_label.setAlignment(Qt.AlignCenter); self.status_bar.addPermanentWidget(self.internet_status_label)
        self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0,0); self.progress_bar.setVisible(False); self.progress_bar.setMaximumWidth(160); self.progress_bar.setTextVisible(False); self.status_bar.addPermanentWidget(self.progress_bar)

    def _load_and_display_templates(self):
        if not hasattr(self, 'template_buttons_layout') or self.template_buttons_layout is None:
            logger.warning("template_buttons_layout not found for templates."); return
        while self.template_buttons_layout.count(): child = self.template_buttons_layout.takeAt(0);
                                                    if child.widget(): child.widget().deleteLater()
        templates_to_load = []
        for template_key, template_data_json_str in FSM_TEMPLATES_BUILTIN.items():
            try: template_data = json.loads(template_data_json_str); templates_to_load.append({"id": f"builtin_{template_key}","name": template_data.get("name", "Unnamed Template"),"description": template_data.get("description", ""),"icon_resource": template_data.get("icon_resource"),"data_json_str": template_data_json_str})
            except json.JSONDecodeError as e: logger.error(f"Error loading built-in template '{template_key}': {e}")
        for template_info in templates_to_load:
            icon = QIcon(); icon_path = template_info.get("icon_resource")
            if icon_path:
                if icon_path.startswith(":/") and RESOURCES_AVAILABLE: icon = QIcon(icon_path)
                                                                       if icon.isNull(): logger.warning(f"Template '{template_info['name']}': Qt resource icon '{icon_path}' not found."); icon = get_standard_icon(QStyle.SP_FileDialogContentsView, "Tmpl")
                else: fs_icon_path = get_bundled_file_path(os.path.basename(icon_path), resource_prefix="icons")
                      if fs_icon_path and os.path.exists(fs_icon_path): icon = QIcon(fs_icon_path)
                      else: logger.warning(f"Template '{template_info['name']}': Filesystem icon '{icon_path}' (resolved to '{fs_icon_path}') not found."); icon = get_standard_icon(QStyle.SP_FileDialogContentsView, "Tmpl")
            else: icon = get_standard_icon(QStyle.SP_FileDialogContentsView, "Tmpl")
            template_btn = DraggableToolButton(template_info["name"],MIME_TYPE_BSM_TEMPLATE,template_info["data_json_str"]); template_btn.setIcon(icon); template_btn.setToolTip(template_info.get("description", template_info["name"]))
            if hasattr(self, 'template_buttons_layout') and self.template_buttons_layout is not None: self.template_buttons_layout.addWidget(template_btn)
            else: logger.error("Cannot add template button, layout missing.")
        if hasattr(self, 'template_buttons_layout') and self.template_buttons_layout is not None: self.template_buttons_layout.addStretch(1)
        else: logger.error("Cannot add stretch to template_buttons_layout.")
        logger.info(f"Loaded {len(templates_to_load)} FSM templates.") 

    def on_new_file_orchestrator(self, silent=False):
        if not silent and self.ide_manager and not self.ide_manager._prompt_ide_save_if_dirty(): return False
        return self.file_op_manager.on_new_file(silent=silent)

    def on_open_file_orchestrator(self):
        if self.ide_manager and not self.ide_manager._prompt_ide_save_if_dirty(): return
        self.file_op_manager.on_open_file()

    def on_open_example_file_orchestrator(self, filename: str):
        if self.ide_manager and not self.ide_manager._prompt_ide_save_if_dirty(): return
        self.file_op_manager._open_example_file(filename)

    def closeEvent(self, event: QCloseEvent):
            logger.info("MW_CLOSE: closeEvent received.")
            if self.ide_manager and not self.ide_manager._prompt_ide_save_if_dirty(): event.ignore(); return
            if self.file_op_manager and not self.file_op_manager._prompt_save_if_dirty(): event.ignore(); return
            if hasattr(self, 'py_sim_ui_manager') and self.py_sim_ui_manager: self.py_sim_ui_manager.on_stop_py_simulation(silent=True)
            if self.internet_check_timer and self.internet_check_timer.isActive(): self.internet_check_timer.stop(); logger.info("MW_CLOSE: Internet check timer stopped.")
            if self.ai_chatbot_manager: self.ai_chatbot_manager.stop_chatbot(); logger.info("MW_CLOSE: AI Chatbot manager stopped.")
            
            worker_ref_for_nvml_shutdown = None
            if self.resource_monitor_thread and self.resource_monitor_thread.isRunning():
                logger.info("MW_CLOSE: Stopping resource monitor worker/thread...")
                worker_ref_for_nvml_shutdown = self.resource_monitor_worker 
                if self.resource_monitor_worker:
                    target_thread = self.resource_monitor_worker.thread() # Get actual thread worker is on
                    current_thread = QThread.currentThread()
                    if target_thread and target_thread != current_thread:
                         QMetaObject.invokeMethod(self.resource_monitor_worker, "stop_monitoring", Qt.BlockingQueuedConnection)
                    else: # Worker is in current thread or no thread, call directly
                         self.resource_monitor_worker.stop_monitoring()
                self.resource_monitor_thread.requestInterruption() 
                self.resource_monitor_thread.quit()
                if not self.resource_monitor_thread.wait(3000): logger.warning("MW_CLOSE: Resource monitor thread did not finish gracefully. Terminating."); self.resource_monitor_thread.terminate(); self.resource_monitor_thread.wait(500)
                else: logger.info("MW_CLOSE: Resource monitor thread stopped gracefully.")
            elif self.resource_monitor_worker: worker_ref_for_nvml_shutdown = self.resource_monitor_worker 

            if worker_ref_for_nvml_shutdown: logger.info("MW_CLOSE: Shutting down NVML."); worker_ref_for_nvml_shutdown._shutdown_nvml()
            
            managers_to_cleanup_and_delete = [self.view_manager, self.file_op_manager, self.ide_manager, self.matlab_op_manager, self.alignment_manager, self.ai_chat_ui_manager, self.py_sim_ui_manager, self.ai_chatbot_manager, self.resource_monitor_worker, self.resource_monitor_thread]
            for manager in managers_to_cleanup_and_delete:
                if manager:
                    if hasattr(manager, 'cleanup') and callable(manager.cleanup):
                        try: manager.cleanup()
                        except Exception as e: logger.error(f"Error during cleanup of {type(manager).__name__}: {e}")
                    if isinstance(manager, QObject): manager.deleteLater() 
            self.view_manager = None; self.file_op_manager = None; self.ide_manager = None; self.matlab_op_manager = None; self.alignment_manager = None; self.ai_chat_ui_manager = None; self.py_sim_ui_manager = None; self.ai_chatbot_manager = None; self.resource_monitor_worker = None; self.resource_monitor_thread = None
            if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads: logging.info("MW_CLOSE: Closing. %d MATLAB processes may still be running.", len(self.matlab_connection._active_threads))
            app_temp_session_dir_name = f"BSMDesigner_Temp_{QApplication.applicationPid()}"; session_temp_dir_path = QDir(QDir.tempPath()).filePath(app_temp_session_dir_name)
            if QDir(session_temp_dir_path).exists():
                if QDir(session_temp_dir_path).removeRecursively(): logger.info(f"MW_CLOSE: Cleaned up session temp dir: {session_temp_dir_path}")
                else: logger.warning(f"MW_CLOSE: Failed to clean up session temp dir: {session_temp_dir_path}")
            logger.info("MW_CLOSE: Application closeEvent accepted."); event.accept()    
            
    @pyqtSlot()
    def _update_undo_redo_actions_enable_state(self):
        if hasattr(self, 'undo_action') and self.undo_action is not None:
            self.undo_action.setEnabled(self.undo_stack.canUndo())
            undo_text = self.undo_stack.undoText()
            self.undo_action.setText(f"&Undo{(' ' + undo_text) if undo_text else ''}")
            self.undo_action.setToolTip(f"Undo: {undo_text}" if undo_text else "Undo")
        else:
            logger.warning("MainWindow._update_undo_redo_actions_enable_state: self.undo_action not found or not initialized.")

        if hasattr(self, 'redo_action') and self.redo_action is not None:
            self.redo_action.setEnabled(self.undo_stack.canRedo())
            redo_text = self.undo_stack.redoText()
            self.redo_action.setText(f"&Redo{(' ' + redo_text) if redo_text else ''}")
            self.redo_action.setToolTip(f"Redo: {redo_text}" if redo_text else "Redo")
        else:
            logger.warning("MainWindow._update_undo_redo_actions_enable_state: self.redo_action not found or not initialized.")        
        
    @pyqtSlot()
    def on_select_all(self):
        if hasattr(self, 'scene') and self.scene: self.scene.select_all()
        else: logger.warning("MainWindow.on_select_all: Scene not available.")

    @pyqtSlot()
    def _update_save_actions_enable_state(self):
        if hasattr(self, 'save_action') and self.save_action is not None and \
           hasattr(self, 'scene') and self.scene is not None:
            self.save_action.setEnabled(self.scene.is_dirty())
        else:
            logger.warning("MainWindow._update_save_actions_enable_state: save_action or scene not available.")
            
    @pyqtSlot()
    def on_delete_selected(self):
        if hasattr(self, 'scene') and self.scene:
            self.scene.delete_selected_items()
        else:
            logger.warning("MainWindow.on_delete_selected: Scene not available.")       
            
    @pyqtSlot()
    def on_show_find_item_dialog(self):
        if not self.find_item_dialog: 
            if hasattr(self, 'scene') and self.scene:
                self.find_item_dialog = FindItemDialog(parent=self, scene_ref=self.scene); self.find_item_dialog.item_selected_for_focus.connect(self.focus_on_item)
                self.scene.scene_content_changed_for_find.connect(self._refresh_find_dialog_if_visible)
            else: logger.error("MainWindow.on_show_find_item_dialog: Scene not available to create FindItemDialog."); QMessageBox.warning(self, "Error", "Cannot open Find Item dialog: Diagram scene is not initialized."); return
        if self.find_item_dialog.isHidden(): self.find_item_dialog.refresh_list(); self.find_item_dialog.show(); self.find_item_dialog.raise_(); self.find_item_dialog.activateWindow()
        else: self.find_item_dialog.activateWindow()
        if hasattr(self.find_item_dialog, 'search_input') and self.find_item_dialog.search_input: self.find_item_dialog.search_input.selectAll(); self.find_item_dialog.search_input.setFocus()

    @pyqtSlot(QGraphicsItem)
    def focus_on_item(self, item_to_focus: QGraphicsItem):
        if item_to_focus and item_to_focus.scene() == self.scene:
            self.scene.clearSelection(); item_to_focus.setSelected(True)
            item_rect = item_to_focus.sceneBoundingRect(); padding = 50; view_rect_with_padding = item_rect.adjusted(-padding, -padding, padding, padding)
            if self.view: self.view.fitInView(view_rect_with_padding, Qt.KeepAspectRatio)
            display_name = "Item"
            if isinstance(item_to_focus, GraphicsStateItem): display_name = f"State: {item_to_focus.text_label}"
            elif isinstance(item_to_focus, GraphicsTransitionItem): display_name = f"Transition: {item_to_focus._compose_label_string()}"
            elif isinstance(item_to_focus, GraphicsCommentItem): display_name = f"Comment: {item_to_focus.toPlainText()[:30]}..."
            elif isinstance(item_to_focus, GraphicsHistoryPseudoStateItem): display_name = f"History ({item_to_focus.text_label}) in {item_to_focus.parent_superstate_item.text_label if item_to_focus.parent_superstate_item else 'None'}"
            self.log_message("INFO", f"Focused on {display_name}")
        else: self.log_message("WARNING", f"Could not find or focus on: {item_to_focus}")

    @pyqtSlot()
    def _refresh_find_dialog_if_visible(self):
        if self.find_item_dialog and not self.find_item_dialog.isHidden(): logger.debug("Refreshing FindItemDialog list."); self.find_item_dialog.refresh_list()
        
    @pyqtSlot()
    def _update_properties_dock(self):
        if not all(hasattr(self, attr) for attr in ['properties_editor_layout', 'properties_placeholder_label', 'properties_editor_container', 'properties_edit_dialog_button', '_dock_property_editors', 'scene']):
            logger.warning("Properties dock UI/scene not fully initialized for update."); return
        selected_items = self.scene.selectedItems() if hasattr(self, 'scene') and self.scene else []
        while self.properties_editor_layout.count():
            layout_item = self.properties_editor_layout.takeAt(0)
            if layout_item: widget = layout_item.widget();
                           if widget: widget.deleteLater()
                           nested_layout = layout_item.layout()
                           if nested_layout:
                               while nested_layout.count(): nested_child = nested_layout.takeAt(0)
                                                            if nested_child.widget(): nested_child.widget().deleteLater()
        self._dock_property_editors.clear(); self._current_edited_item_in_dock = None
        if len(selected_items) == 1:
            self._current_edited_item_in_dock = selected_items[0]; item_data = {}
            if hasattr(self._current_edited_item_in_dock, 'get_data'): item_data = self._current_edited_item_in_dock.get_data()
            self.properties_editor_container.setVisible(True); self.properties_placeholder_label.setVisible(False); self.properties_edit_dialog_button.setEnabled(True)
            if isinstance(self._current_edited_item_in_dock, GraphicsStateItem):
                name_edit = QLineEdit(item_data.get('name', '')); name_edit.textChanged.connect(self._on_dock_property_changed); self.properties_editor_layout.addRow("Name:", name_edit); self._dock_property_editors['name'] = name_edit
                desc_edit = QTextEdit(item_data.get('description', '')); desc_edit.setFixedHeight(60); desc_edit.textChanged.connect(self._on_dock_property_changed); self.properties_editor_layout.addRow("Description:", desc_edit); self._dock_property_editors['description'] = desc_edit
                color_label = QLabel(); color_val = item_data.get('color', '#FFFFFF'); color_label.setText(f"<span style='background-color:{color_val}; color:{'black' if QColor(color_val).lightnessF() > 0.5 else 'white'}; padding: 2px 5px; border-radius:3px;'>{color_val}</span> (Advanced Edit...)"); self.properties_editor_layout.addRow("Color:", color_label)
                is_initial_cb = QCheckBox("Is Initial"); is_initial_cb.setChecked(item_data.get('is_initial', False)); is_initial_cb.toggled.connect(self._on_dock_property_changed); self.properties_editor_layout.addRow(is_initial_cb); self._dock_property_editors['is_initial'] = is_initial_cb
                is_final_cb = QCheckBox("Is Final"); is_final_cb.setChecked(item_data.get('is_final', False)); is_final_cb.toggled.connect(self._on_dock_property_changed); self.properties_editor_layout.addRow(is_final_cb); self._dock_property_editors['is_final'] = is_final_cb
            elif isinstance(self._current_edited_item_in_dock, GraphicsTransitionItem):
                event_edit = QLineEdit(item_data.get('event', '')); event_edit.textChanged.connect(self._on_dock_property_changed); self.properties_editor_layout.addRow("Event:", event_edit); self._dock_property_editors['event'] = event_edit
                condition_edit = QLineEdit(item_data.get('condition', '')); condition_edit.textChanged.connect(self._on_dock_property_changed); self.properties_editor_layout.addRow("Condition:", condition_edit); self._dock_property_editors['condition'] = condition_edit
            elif isinstance(self._current_edited_item_in_dock, GraphicsCommentItem):
                text_edit = QTextEdit(item_data.get('text', '')); text_edit.setFixedHeight(80); text_edit.textChanged.connect(self._on_dock_property_changed); self.properties_editor_layout.addRow("Text:", text_edit); self._dock_property_editors['text'] = text_edit
            elif isinstance(self._current_edited_item_in_dock, GraphicsHistoryPseudoStateItem):
                self.properties_placeholder_label.setText(f"<i>Editing: History ({item_data.get('type', 'H')}).<br><span style='font-size:{APP_FONT_SIZE_SMALL}; color:{COLOR_TEXT_SECONDARY};'>Use 'Advanced Edit...' to change default target.</span></i>")
                self.properties_editor_container.setVisible(False); self.properties_placeholder_label.setVisible(True)
            else: self.properties_placeholder_label.setText(f"<i>Editing: {type(self._current_edited_item_in_dock).__name__}.<br><span style='font-size:{APP_FONT_SIZE_SMALL}; color:{COLOR_TEXT_SECONDARY};'>Use 'Advanced Edit...' button.</span></i>"); self.properties_editor_container.setVisible(False); self.properties_placeholder_label.setVisible(True); self.properties_edit_dialog_button.setEnabled(True)
        elif len(selected_items) > 1: self.properties_placeholder_label.setText(f"<i><b>{len(selected_items)} items selected.</b><br><span style='font-size:{APP_FONT_SIZE_SMALL}; color:{COLOR_TEXT_SECONDARY};'>Select single item for dock edit.</span></i>"); self.properties_editor_container.setVisible(False); self.properties_placeholder_label.setVisible(True); self.properties_edit_dialog_button.setEnabled(False)
        else: self.properties_placeholder_label.setText(f"<i>No item selected.</i><br><span style='font-size:{APP_FONT_SIZE_SMALL}; color:{COLOR_TEXT_SECONDARY};'>Click item or use tools.</span>"); self.properties_editor_container.setVisible(False); self.properties_placeholder_label.setVisible(True); self.properties_edit_dialog_button.setEnabled(False)
        if hasattr(self, 'properties_apply_button'): self.properties_apply_button.setEnabled(False)
        if hasattr(self, 'properties_revert_button'): self.properties_revert_button.setEnabled(False)

    @pyqtSlot()
    def _on_dock_property_changed(self):
        if hasattr(self, 'properties_apply_button'): self.properties_apply_button.setEnabled(True)
        if hasattr(self, 'properties_revert_button'): self.properties_revert_button.setEnabled(True)

    @pyqtSlot()
    def _on_apply_dock_properties(self):
        if self._current_edited_item_in_dock and hasattr(self._current_edited_item_in_dock, 'get_data') and hasattr(self._current_edited_item_in_dock, 'set_properties'):
            item = self._current_edited_item_in_dock; old_props = item.get_data(); new_props_from_dock_editors = old_props.copy(); changed_by_dock_edit = False
            for prop_name, editor_widget in self._dock_property_editors.items():
                current_editor_value = None
                if isinstance(editor_widget, QLineEdit): current_editor_value = editor_widget.text()
                elif isinstance(editor_widget, QTextEdit): current_editor_value = editor_widget.toPlainText()
                elif isinstance(editor_widget, QCheckBox): current_editor_value = editor_widget.isChecked()
                elif isinstance(editor_widget, QComboBox): current_editor_value = editor_widget.currentText()
                elif isinstance(editor_widget, QSpinBox): current_editor_value = editor_widget.value()
                if current_editor_value is not None and prop_name in new_props_from_dock_editors:
                    if prop_name == 'color' and isinstance(editor_widget, QPushButton) and hasattr(editor_widget, 'current_color_obj'): current_editor_value = editor_widget.current_color_obj.name()
                    if new_props_from_dock_editors[prop_name] != current_editor_value: new_props_from_dock_editors[prop_name] = current_editor_value; changed_by_dock_edit = True
            if changed_by_dock_edit:
                logger.info(f"Properties Dock: Applying changes for {getattr(item, 'text_label', type(item).__name__)}.")
                if isinstance(item, GraphicsStateItem) and 'name' in new_props_from_dock_editors:
                    new_name = new_props_from_dock_editors['name'].strip()
                    if not new_name: QMessageBox.warning(self, "Invalid Name", "State name cannot be empty."); self._update_properties_dock(); return
                    if new_name != old_props['name'] and self.scene.get_state_by_name(new_name) and self.scene.get_state_by_name(new_name) != item: QMessageBox.warning(self, "Duplicate Name", f"State '{new_name}' already exists."); self._update_properties_dock(); return
                    new_props_from_dock_editors['name'] = new_name
                cmd = EditItemPropertiesCommand(item, old_props, new_props_from_dock_editors, f"Edit Properties via Dock for {getattr(item, 'text_label', type(item).__name__)}"); self.undo_stack.push(cmd)
            else: logger.info(f"Properties Dock: Apply clicked, no changes for {getattr(item, 'text_label', type(item).__name__)}.")
            self._update_properties_dock(); self.properties_apply_button.setEnabled(False); self.properties_revert_button.setEnabled(False)
        else: logger.warning("Properties Dock: Apply clicked, no item being edited.")

    @pyqtSlot()
    def _on_revert_dock_properties(self):
        if self._current_edited_item_in_dock: logger.info(f"Properties Dock: Revert for {getattr(self._current_edited_item_in_dock, 'text_label', type(self._current_edited_item_in_dock).__name__)}."); self._update_properties_dock(); self.properties_apply_button.setEnabled(False); self.properties_revert_button.setEnabled(False)
        else: logger.warning("Properties Dock: Revert clicked, no item being edited.")

    @pyqtSlot()
    def _on_edit_selected_item_properties_from_dock_button(self):
        if self._current_edited_item_in_dock:
            if self.properties_apply_button.isEnabled():
                reply = QMessageBox.question(self, "Unapplied Dock Changes", "Properties dock has unapplied changes. Apply before advanced edit?", QMessageBox.Apply | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Apply)
                if reply == QMessageBox.Apply: self._on_apply_dock_properties();
                                             if self.properties_apply_button.isEnabled(): return 
                elif reply == QMessageBox.Cancel: return
            self.scene.edit_item_properties(self._current_edited_item_in_dock); self._update_properties_dock(); self.properties_apply_button.setEnabled(False); self.properties_revert_button.setEnabled(False)
        else:
            selected = self.scene.selectedItems()
            if len(selected) == 1: self.scene.edit_item_properties(selected[0]); self._update_properties_dock(); self.properties_apply_button.setEnabled(False); self.properties_revert_button.setEnabled(False)
            else: QMessageBox.information(self, "Advanced Edit", "Select a single item for advanced edit.")

    @pyqtSlot(QListWidgetItem)
    def on_problem_item_double_clicked(self, list_item: QListWidgetItem):
        item_ref = list_item.data(Qt.UserRole)
        if item_ref and isinstance(item_ref, QGraphicsItem) and item_ref.scene() == self.scene: self.focus_on_item(item_ref); logger.info(f"Focused on problematic item: {getattr(item_ref, 'text_label', type(item_ref).__name__)}")
        else: logger.debug(f"No valid QGraphicsItem ref for validation issue: '{list_item.text()}'")

    @pyqtSlot(list)
    def update_problems_dock(self, issues_with_items: list):
        if not hasattr(self, 'problems_list_widget') or self.problems_list_widget is None: logger.warning("problems_list_widget not initialized for update."); return
        self.problems_list_widget.clear()
        if issues_with_items:
            for issue_msg, item_ref in issues_with_items: list_item_widget = QListWidgetItem(str(issue_msg));
                                                         if item_ref: list_item_widget.setData(Qt.UserRole, item_ref)
                                                         self.problems_list_widget.addItem(list_item_widget)
            self.problems_dock.setWindowTitle(f"Validation Issues ({len(issues_with_items)})")
            if self.problems_dock.isHidden() and len(issues_with_items) > 0: self.problems_dock.show(); self.problems_dock.raise_()
        else: self.problems_list_widget.addItem("No validation issues found."); self.problems_dock.setWindowTitle("Validation Issues")

    @pyqtSlot(bool)
    def _handle_py_sim_state_changed_by_manager(self, is_running: bool):
        logger.debug(f"MW: PySim state changed by manager to: {is_running}")
        self.py_sim_active = is_running; self.update_window_title(); self._update_py_sim_status_display()
        if self.matlab_op_manager: self.matlab_op_manager.update_matlab_actions_enabled_state()
        self._update_py_simulation_actions_enabled_state()

    @pyqtSlot(bool)
    def _handle_py_sim_global_ui_enable_by_manager(self, enable: bool):
        logger.debug(f"MW: Global UI enable requested by PySim manager: {enable}"); is_editable = enable
        diagram_editing_actions = [self.new_action, self.open_action, self.save_action, self.save_as_action, self.undo_action, self.redo_action, self.delete_action, self.select_all_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action, self.add_history_shallow_mode_action] 
        for action_obj in diagram_editing_actions:
            if action_obj and hasattr(action_obj, 'setEnabled'): action_obj.setEnabled(is_editable)
        if hasattr(self, 'tools_dock'): self.tools_dock.setEnabled(is_editable)
        if hasattr(self, 'properties_edit_dialog_button'): self.properties_edit_dialog_button.setEnabled(is_editable and hasattr(self.scene, 'selectedItems') and len(self.scene.selectedItems())==1)
        if hasattr(self, 'properties_apply_button'): self.properties_apply_button.setEnabled(False)
        if hasattr(self, 'properties_revert_button'): self.properties_revert_button.setEnabled(False)
        if hasattr(self, 'scene') and self.scene:
            for item in self.scene.items():
                if isinstance(item, (GraphicsStateItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem)): item.setFlag(QGraphicsItem.ItemIsMovable, is_editable and self.scene.current_mode == "select")
            if not is_editable and self.scene.current_mode != "select": self.scene.set_mode("select")
        if self.matlab_op_manager: self.matlab_op_manager.update_matlab_actions_enabled_state()
        self._update_py_simulation_actions_enabled_state()

    def _update_py_sim_status_display(self):
        if hasattr(self, 'py_sim_status_label'):
            status_text = "PySim: Idle"; style = f"font-weight:normal;padding:2px 5px; color:{COLOR_TEXT_SECONDARY}; background-color:{COLOR_BACKGROUND_MEDIUM}; border-radius:3px;"; tooltip = "Internal Python FSM Simulation is Idle."
            if self.py_sim_active and self.py_fsm_engine:
                current_state_name = self.py_fsm_engine.get_current_state_name(); display_state_name = (current_state_name[:20] + '...') if len(current_state_name) > 23 else current_state_name
                status_text = f"PySim: Active ({html.escape(display_state_name)})"; bg_color = QColor(COLOR_PY_SIM_STATE_ACTIVE).lighter(180).name(); style = f"font-weight:bold;padding:2px 5px;color:{COLOR_PY_SIM_STATE_ACTIVE.name()}; background-color:{bg_color}; border-radius:3px;"; tooltip = f"Python FSM Simulation Active: {current_state_name}"
                if self.py_fsm_engine.paused_on_breakpoint: status_text += " (Paused)"; tooltip += " (Paused at Breakpoint)"
            self.py_sim_status_label.setText(status_text); self.py_sim_status_label.setStyleSheet(style); self.py_sim_status_label.setToolTip(tooltip)

    def _update_py_simulation_actions_enabled_state(self):
        is_matlab_op_running = hasattr(self, 'progress_bar') and self.progress_bar and self.progress_bar.isVisible()
        sim_can_start = not self.py_sim_active and not is_matlab_op_running; sim_can_be_controlled = self.py_sim_active and not is_matlab_op_running
        if hasattr(self, 'start_py_sim_action'): self.start_py_sim_action.setEnabled(sim_can_start)
        if hasattr(self, 'stop_py_sim_action'): self.stop_py_sim_action.setEnabled(sim_can_be_controlled)
        if hasattr(self, 'reset_py_sim_action'): self.reset_py_sim_action.setEnabled(sim_can_be_controlled)
        if hasattr(self, 'py_sim_ui_manager') and self.py_sim_ui_manager: self.py_sim_ui_manager._update_internal_controls_enabled_state()

    @pyqtSlot()
    def on_generate_c_code(self):
        if not self.scene.items(): QMessageBox.information(self, "Empty Diagram", "Cannot generate code for empty diagram."); return
        default_filename_base = os.path.splitext(os.path.basename(self.current_file_path or "fsm_generated"))[0]
        default_filename_base = "".join(c if c.isalnum() or c == '_' else '_' for c in default_filename_base)
        if not default_filename_base or not default_filename_base[0].isalpha(): default_filename_base = "bsm_" + (default_filename_base if default_filename_base else "model")
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory for C Code", QDir.homePath())
        if output_dir:
            filename_base, ok = QInputDialog.getText(self, "Base Filename", "Enter base name for .c and .h files:", QLineEdit.Normal, default_filename_base)
            if ok and filename_base.strip():
                filename_base = filename_base.strip(); filename_base = "".join(c if c.isalnum() or c == '_' else '_' for c in filename_base)
                if not filename_base or not filename_base[0].isalpha(): QMessageBox.warning(self, "Invalid Filename", "Base filename must start with letter and contain only alphanumeric/underscores."); return
                diagram_data = self.scene.get_diagram_data()
                try: c_file_path, h_file_path = generate_c_code_files(diagram_data, output_dir, filename_base); QMessageBox.information(self, "C Code Generation Successful", f"Generated files:\n{c_file_path}\n{h_file_path}"); logger.info(f"C code generated to {output_dir} with base {filename_base}")
                except Exception as e: QMessageBox.critical(self, "C Code Generation Error", f"Failed to generate C code: {e}"); logger.error(f"Error generating C code: {e}", exc_info=True)
            elif ok: QMessageBox.warning(self, "Invalid Filename", "Base filename cannot be empty.")

    def _add_fsm_data_to_scene(self, fsm_data: dict, clear_current_diagram=True, original_user_prompt="AI Generated FSM"):
        if clear_current_diagram:
            if not self.on_new_file_orchestrator(silent=True): return 
        if self.scene: self.scene._add_template_to_scene(fsm_data, self.view.mapToScene(self.view.viewport().rect().center())) 
        else: logger.error("Cannot add FSM data: Scene not available.")
        self.update_window_title(); self._update_ui_element_states()
        self._fit_view_to_new_ai_items()

    def _fit_view_to_new_ai_items(self):
        if self.scene and self.scene.items(): bounds = self.scene.itemsBoundingRect()
                                             if not bounds.isEmpty() and self.view: self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
        else: logger.debug("Fit view: No items to fit or scene/view not ready.")

    def connect_state_item_signals(self, state_item: GraphicsStateItem):
        if state_item and hasattr(state_item, 'signals') and state_item.signals:
            try: state_item.signals.textChangedViaInlineEdit.disconnect(self._handle_state_renamed_inline)
            except (TypeError, RuntimeError): pass
            state_item.signals.textChangedViaInlineEdit.connect(self._handle_state_renamed_inline)
        else: logger.warning(f"Attempted to connect signals for invalid/uninitialized state_item: {state_item}")

    @pyqtSlot(str, str)
    def _handle_state_renamed_inline(self, old_name: str, new_name: str):
        if self.scene: self.scene._update_transitions_for_renamed_state(old_name, new_name)

    @pyqtSlot(float, float, float, str)
    def _update_resource_display(self, cpu_usage: float, ram_usage: float, gpu_util: float, gpu_name: str):
        if hasattr(self, 'cpu_status_label') and self.cpu_status_label: self.cpu_status_label.setText(f"CPU: {cpu_usage:.0f}%")
        if hasattr(self, 'ram_status_label') and self.ram_status_label: self.ram_status_label.setText(f"RAM: {ram_usage:.0f}%")
        if hasattr(self, 'gpu_status_label') and self.gpu_status_label:
            if gpu_util == -1.0: self.gpu_status_label.setText(f"GPU: {gpu_name}")
            elif gpu_util == -2.0: self.gpu_status_label.setText("GPU: Error"); self.gpu_status_label.setToolTip(gpu_name)
            elif gpu_util == -3.0: self.gpu_status_label.setText("GPU: Mon Error"); self.gpu_status_label.setToolTip(gpu_name)
            elif PYNVML_AVAILABLE and self.resource_monitor_worker and self.resource_monitor_worker._nvml_initialized and self.resource_monitor_worker._gpu_handle: self.gpu_status_label.setText(f"GPU: {gpu_util:.0f}%"); self.gpu_status_label.setToolTip(f"GPU: {gpu_util:.0f}% ({gpu_name})")
            else: self.gpu_status_label.setText("GPU: N/A"); self.gpu_status_label.setToolTip(gpu_name if gpu_name else "NVIDIA GPU status unavailable.")

    def _init_resource_monitor(self):
        if self.resource_monitor_thread is not None or self.resource_monitor_worker is not None: logger.warning("Resource monitor already initialized."); return
        self.resource_monitor_thread = QThread(self); self.resource_monitor_thread.setObjectName("ResourceMonitorQThread")
        self.resource_monitor_worker = ResourceMonitorWorker(interval_ms=2000); self.resource_monitor_worker.moveToThread(self.resource_monitor_thread)
        self.resource_monitor_worker.resourceUpdate.connect(self._update_resource_display); self.resource_monitor_thread.started.connect(self.resource_monitor_worker.start_monitoring)
        self.resource_monitor_worker.finished_signal.connect(self.resource_monitor_thread.quit)
        self.resource_monitor_thread.start(); logger.info("Resource monitor thread initialized and started.")

    def _init_internet_status_check(self): self.internet_check_timer.timeout.connect(self._run_internet_check_job); self.internet_check_timer.start(15000); QTimer.singleShot(100, self._run_internet_check_job)
    def _run_internet_check_job(self):
        current_status = False; status_detail = "Checking..."
        try: s = socket.create_connection(("8.8.8.8", 53), timeout=1.5); s.close(); current_status = True; status_detail = "Connected"
        except socket.timeout: status_detail = "Timeout"
        except (socket.gaierror, OSError): status_detail = "Net Issue"
        if current_status != self._internet_connected or self._internet_connected is None: self._internet_connected = current_status; self._update_internet_status_display(current_status, status_detail)

    def _update_ai_features_enabled_state(self, is_online_and_key_present: bool):
        if hasattr(self, 'ask_ai_to_generate_fsm_action'): self.ask_ai_to_generate_fsm_action.setEnabled(is_online_and_key_present)
        if hasattr(self, 'clear_ai_chat_action'): self.clear_ai_chat_action.setEnabled(is_online_and_key_present)
        if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager:
            if self.ai_chat_ui_manager.ai_chat_send_button: self.ai_chat_ui_manager.ai_chat_send_button.setEnabled(is_online_and_key_present)
            if self.ai_chat_ui_manager.ai_chat_input: self.ai_chat_ui_manager.ai_chat_input.setEnabled(is_online_and_key_present)
            placeholder = "AI disabled: API Key required." if self.ai_chatbot_manager and not self.ai_chatbot_manager.api_key else ("AI disabled: Internet connection required." if not self._internet_connected else "Type your message to the AI...")
            if not is_online_and_key_present: self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText(placeholder)
            else: self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText("Type your message to the AI...")
        if hasattr(self, 'ide_analyze_action') and self.ide_manager and self.ide_manager.ide_language_combo:
            current_ide_lang = self.ide_manager.ide_language_combo.currentText()
            can_analyze_ide = (current_ide_lang == "Python" or current_ide_lang.startswith("C/C++")) and is_online_and_key_present
            self.ide_analyze_action.setEnabled(can_analyze_ide)
            tooltip = "Analyze current code with AI" + (" (Requires Internet & Gemini API Key)" if not (self.ai_chatbot_manager and self.ai_chatbot_manager.api_key and self._internet_connected) else (" (Best for Python or C/C++)" if not (current_ide_lang == "Python" or current_ide_lang.startswith("C/C++")) else ""))
            self.ide_analyze_action.setToolTip(tooltip)

    def _update_internet_status_display(self, is_connected: bool, message_detail: str):
        full_status_text = f"Net: {message_detail}";
        if hasattr(self, 'internet_status_label'):
            self.internet_status_label.setText(full_status_text); self.internet_status_label.setToolTip(f"Internet Status: {message_detail} (Checks 8.8.8.8:53)")
            text_color = COLOR_ACCENT_SUCCESS if is_connected else COLOR_ACCENT_ERROR; bg_color = QColor(text_color).lighter(180).name()
            self.internet_status_label.setStyleSheet(f"font-size:{APP_FONT_SIZE_SMALL}; padding:2px 5px; color:{text_color}; background-color:{bg_color}; border-radius:3px;")
        logging.debug("Internet Status Update: %s", message_detail)
        key_present = self.ai_chatbot_manager is not None and bool(self.ai_chatbot_manager.api_key); ai_ready = is_connected and key_present
        if hasattr(self.ai_chatbot_manager, 'set_online_status'): self.ai_chatbot_manager.set_online_status(is_connected)
        self._update_ai_features_enabled_state(ai_ready)

    @pyqtSlot()
    def on_show_quick_start(self):
        guide_path = get_bundled_file_path("QUICK_START.html", resource_prefix="docs")
        if guide_path:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path)): QMessageBox.warning(self, "Could Not Open Guide", f"Failed to open Quick Start Guide.\nPath: {guide_path}"); logging.warning("Failed to open Quick Start Guide from: %s", guide_path)
        else: QMessageBox.information(self, "Guide Not Found", "Quick Start Guide (QUICK_START.html) not found.")

    @pyqtSlot()
    def on_about(self):
        QMessageBox.about(self, f"About {APP_NAME}", f"<h3 style='color:{COLOR_ACCENT_PRIMARY};'>{APP_NAME} v{APP_VERSION}</h3><p>Graphical tool for designing and simulating Brain State Machines.</p><ul><li>Visual FSM design</li><li>Internal Python FSM simulation</li><li>MATLAB/Simulink integration</li><li>AI Assistant (Gemini)</li></ul><p style='font-size:8pt;color:{COLOR_TEXT_SECONDARY};'>For research/education. Verify generated models/code.</p>")

    @pyqtSlot()
    def _update_align_distribute_actions_enable_state(self):
        if self.alignment_manager: self.alignment_manager.update_align_distribute_actions_enable_state()
        else: logger.warning("AlignmentManager not available for UI update.")

    @pyqtSlot(str)
    def on_align_items(self, mode: str):
        if self.alignment_manager: self.alignment_manager.on_align_items(mode)
        else: logger.error("AlignmentManager not available to perform alignment.")

    @pyqtSlot(str)
    def on_distribute_items(self, mode: str):
        if self.alignment_manager: self.alignment_manager.on_distribute_items(mode)
        else: logger.error("AlignmentManager not available to perform distribution.")

    def log_message(self, level_str: str, message: str): 
        level = getattr(logging, level_str.upper(), logging.INFO)
        logger.log(level, message)


if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    script_dir = os.path.dirname(os.path.abspath(__file__)); parent_dir_of_script = os.path.dirname(script_dir)
    if parent_dir_of_script not in sys.path: sys.path.insert(0, parent_dir_of_script)
    app.setStyleSheet(STYLE_SHEET_GLOBAL)
    main_win = MainWindow(); main_win.show(); sys.exit(app.exec_())