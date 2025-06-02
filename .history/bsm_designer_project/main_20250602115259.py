
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

from PyQt5.QtCore import Qt, QTime, QTimer, QPointF, QMetaObject, QFile, QTemporaryFile, QDir, QIODevice, QFileInfo, QEvent, QSize, QUrl, pyqtSignal, pyqtSlot, QThread, QPoint, QMimeData, QObject
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

import pygraphviz as pgv # For AI FSM layout
import psutil
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None

# --- Custom Modules ---
from graphics_scene import DiagramScene, ZoomableView
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
from code_editor import CodeEditor
from fsm_simulator import FSMSimulator, FSMError
from ai_chatbot import AIChatbotManager, AIStatus, AIChatUIManager # AIChatUIManager is in ai_chatbot.py
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
    FSM_TEMPLATES_BUILTIN
)
from utils import get_standard_icon
from ui_py_simulation_manager import PySimulationUIManager


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

        if self.mime_type == "application/x-bsm-template":
            try:
                template_obj = json.loads(self.item_type_data_str)
                mime_data.setText(f"FSM Template: {template_obj.get('name', 'Custom Template')}")
            except json.JSONDecodeError:
                mime_data.setText("FSM Template (Invalid JSON)")
        else:
            mime_data.setText(self.item_type_data_str)

        drag.setMimeData(mime_data)

        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        self.render(pixmap, QPoint(), QRegion(), QWidget.RenderFlags(QWidget.DrawChildren))

        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.fillRect(pixmap.rect(), QColor(0, 0, 0, 150))
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())
        drag.exec_(Qt.CopyAction)

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
    def stop_monitoring(self): logger.info("ResourceMonitorWorker: stop_monitoring_slot called."); self._stop_requested = True; logger.debug("ResourceMonitorWorker: Stop flag set for worker loop.")
    def _shutdown_nvml(self):
        if self._nvml_initialized and PYNVML_AVAILABLE and pynvml:
            try: pynvml.nvmlShutdown(); logger.info("ResourceMonitorWorker: NVML shutdown successfully.")
            except Exception as e: logger.warning(f"Error shutting down NVML: {e}")
        self._nvml_initialized = False; self._gpu_handle = None
    def _monitor_resources(self):
        logger.debug("Resource monitor worker loop started."); last_data_emit_time = 0; worker_thread = self.thread()
        if not worker_thread: logger.error("ResourceMonitorWorker: Worker is not associated with a QThread. Cannot reliably stop."); self.finished_signal.emit(); return
        while not worker_thread.isInterruptionRequested():
            current_loop_time = QTime.currentTime().msecsSinceStartOfDay()
            if (current_loop_time - last_data_emit_time) >= self.data_collection_interval_ms or last_data_emit_time == 0:
                if worker_thread.isInterruptionRequested(): break
                if PYNVML_AVAILABLE and pynvml and not self._nvml_initialized: self._attempt_nvml_init(from_worker_loop=True)
                if worker_thread.isInterruptionRequested(): break
                if PYNVML_AVAILABLE and pynvml and self._nvml_initialized and not self._gpu_handle:
                    try:
                        if pynvml.nvmlDeviceGetCount() > 0:
                            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0); gpu_name_raw = pynvml.nvmlDeviceGetName(self._gpu_handle)
                            if isinstance(gpu_name_raw, bytes): self._gpu_name_cache = gpu_name_raw.decode('utf-8')
                            elif isinstance(gpu_name_raw, str): self._gpu_name_cache = gpu_name_raw
                            else: self._gpu_name_cache = "NVIDIA GPU Name TypeErr (Poll)"
                        else: self._gpu_name_cache = "NVIDIA GPU N/A (Poll)"
                    except pynvml.NVMLError as e_nvml_poll: self._gpu_handle = None; self._nvml_initialized = False if hasattr(pynvml, 'NVML_ERROR_UNINITIALIZED') and e_nvml_poll.value == pynvml.NVML_ERROR_UNINITIALIZED else self._nvml_initialized
                    except Exception: pass
                if worker_thread.isInterruptionRequested(): break
                try:
                    cpu_usage = psutil.cpu_percent(interval=None); ram_percent = psutil.virtual_memory().percent; gpu_util, gpu_name_to_emit = -1.0, self._gpu_name_cache
                    if self._nvml_initialized and self._gpu_handle and PYNVML_AVAILABLE and pynvml:
                        if worker_thread.isInterruptionRequested(): break
                        try: gpu_util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle).gpu
                        except pynvml.NVMLError as e_nvml_util: gpu_util = -2.0; self._gpu_handle = None; self._nvml_initialized = False if hasattr(pynvml, 'NVML_ERROR_UNINITIALIZED') and e_nvml_util.value == pynvml.NVML_ERROR_UNINITIALIZED else self._nvml_initialized
                        except Exception: gpu_util = -2.0
                    if worker_thread.isInterruptionRequested(): break
                    if not worker_thread.isInterruptionRequested(): self.resourceUpdate.emit(cpu_usage, ram_percent, gpu_util, gpu_name_to_emit)
                    last_data_emit_time = current_loop_time
                except Exception as e: logger.error(f"Error in resource monitoring data collection: {e}", exc_info=False); self.resourceUpdate.emit(-1.0, -1.0, -3.0, "Data Error") if not worker_thread.isInterruptionRequested() else None
            for _i in range(int(self.data_collection_interval_ms / self.WORKER_LOOP_CHECK_INTERVAL_MS) + 1):
                if worker_thread.isInterruptionRequested(): break
                QThread.msleep(self.WORKER_LOOP_CHECK_INTERVAL_MS)
            if worker_thread.isInterruptionRequested(): break
        logger.info(f"Resource monitor worker loop finished (Interruption requested: {worker_thread.isInterruptionRequested()})."); self.finished_signal.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - Untitled [*]")

        self.current_file_path = None
        self.last_generated_model_path = None
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)

        self.ai_chatbot_manager = AIChatbotManager(self)

        self.scene = DiagramScene(self.undo_stack, self)
        self.scene.selectionChanged.connect(self._update_zoom_to_selection_action_enable_state)
        self.scene.selectionChanged.connect(self._update_align_distribute_actions_enable_state)
        self.scene.selectionChanged.connect(self._update_properties_dock)
        self.scene.scene_content_changed_for_find.connect(self._refresh_find_dialog_if_visible)
        self.scene.modifiedStatusChanged.connect(self.setWindowModified)
        self.scene.modifiedStatusChanged.connect(self._update_window_title)
        self.scene.validation_issues_updated.connect(self.update_problems_dock) # Connect validation signal

        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False

        self.ide_code_editor: CodeEditor | None = None
        self.current_ide_file_path: str | None = None
        self.ide_output_console: QTextEdit | None = None
        self.ide_run_script_action: QAction | None = None
        self.ide_analyze_action: QAction | None = None
        self.ide_editor_is_dirty = False

        self.find_item_dialog: FindItemDialog | None = None
        self.problems_list_widget: QListWidget | None = None # For validation issues dock

        self.init_ui() # Creates UI elements including self.view
        if hasattr(self, 'view') and self.view: # Ensure view is created before connecting
            self.view.zoomChanged.connect(self.update_zoom_status_display)
            self.update_zoom_status_display(self.view.transform().m11())
        else:
            logger.error("MainWindow: self.view not initialized in init_ui() before use.")


        self.py_sim_ui_manager = PySimulationUIManager(self)
        self.ai_chat_ui_manager = AIChatUIManager(self) # Use the one from ai_chatbot.py

        self._populate_dynamic_docks() # Call after docks are created in init_ui

        self.py_sim_ui_manager.simulationStateChanged.connect(self._handle_py_sim_state_changed_by_manager)
        self.py_sim_ui_manager.requestGlobalUIEnable.connect(self._handle_py_sim_global_ui_enable_by_manager)

        self._internet_connected: bool | None = None
        self.internet_check_timer = QTimer(self)

        self.resource_monitor_worker: ResourceMonitorWorker | None = None
        self.resource_monitor_thread: QThread | None = None

        try:
            # Ensure log_output (QTextEdit for logs) is created in init_ui before this
            if not hasattr(self, 'log_output') or not self.log_output :
                self.log_output = QTextEdit() # Fallback, real creation should be in _create_docks
                logger.warning("MainWindow: log_output was not created by init_ui before logging setup. Fallback used.")
            setup_global_logging(self.log_output)
            logger.info("Main window initialized and logging configured.")
        except Exception as e:
            print(f"ERROR: Failed to run setup_global_logging: {e}. UI logs might not work.")
            if not logging.getLogger().hasHandlers(): # Ensure basic logging if setup fails
                 logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

        self._init_resource_monitor()

        # Ensure status bar labels are created before trying to set object names
        if hasattr(self, 'matlab_status_label'): self.matlab_status_label.setObjectName("MatlabStatusLabel")
        if hasattr(self, 'py_sim_status_label'): self.py_sim_status_label.setObjectName("PySimStatusLabel")
        if hasattr(self, 'internet_status_label'): self.internet_status_label.setObjectName("InternetStatusLabel")
        if hasattr(self, 'status_label'): self.status_label.setObjectName("StatusLabel")
        if hasattr(self, 'cpu_status_label'): self.cpu_status_label.setObjectName("CpuStatusLabel")
        if hasattr(self, 'ram_status_label'): self.ram_status_label.setObjectName("RamStatusLabel")
        if hasattr(self, 'gpu_status_label'): self.gpu_status_label.setObjectName("GpuStatusLabel")


        self._update_matlab_status_display(False, "Initializing. Configure MATLAB settings or attempt auto-detect.")
        self._update_py_sim_status_display()

        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)

        self._update_window_title()
        self.on_new_file(silent=True) # This will also trigger initial validation via scene.run_all_validations
        self._init_internet_status_check()
        self._update_properties_dock() # Initial update
        self._update_py_simulation_actions_enabled_state()
        self._update_zoom_to_selection_action_enable_state()
        self._update_align_distribute_actions_enable_state()

        # Initialize AI Chatbot status display
        if self.ai_chat_ui_manager and self.ai_chatbot_manager:
            initial_ai_status = self.ai_chatbot_manager.get_current_ai_status()
            initial_ai_text = "Status: Initializing AI..."
            if initial_ai_status == AIStatus.API_KEY_REQUIRED:
                 initial_ai_text = "Status: API Key required. Configure in Settings."
            elif initial_ai_status == AIStatus.OFFLINE:
                 initial_ai_text = "Status: Offline. AI features unavailable."
            elif initial_ai_status == AIStatus.INACTIVE:
                 initial_ai_text = "Status: AI Assistant Inactive."
            # Ensure ai_chat_status_label exists
            if hasattr(self.ai_chat_ui_manager, 'ai_chat_status_label') and self.ai_chat_ui_manager.ai_chat_status_label:
                self.ai_chat_ui_manager.update_status_display(initial_ai_status, initial_ai_text)
            else:
                logger.warning("MainWindow: ai_chat_ui_manager.ai_chat_status_label not ready for initial update.")

        else:
            logger.warning("MainWindow: ai_chat_ui_manager or ai_chatbot_manager not initialized when trying to set initial status.")


    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050)
        self._create_central_widget() # self.view created here
        self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM"))
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_docks() # self.log_output and self.problems_list_widget created here
        self._create_status_bar() # Status bar labels created here
        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger()

    def _populate_dynamic_docks(self):
        if self.py_sim_ui_manager and hasattr(self, 'py_sim_dock') and self.py_sim_dock:
            py_sim_contents_widget = self.py_sim_ui_manager.create_dock_widget_contents()
            self.py_sim_dock.setWidget(py_sim_contents_widget)
        else:
            logger.error("Could not populate Python Simulation Dock: manager or dock missing.")

        if self.ai_chat_ui_manager and hasattr(self, 'ai_chatbot_dock') and self.ai_chatbot_dock:
            ai_chat_contents_widget = self.ai_chat_ui_manager.create_dock_widget_contents()
            self.ai_chatbot_dock.setWidget(ai_chat_contents_widget)
        else:
            logger.error("Could not populate AI Chatbot Dock: manager or dock missing.")

        # Tabify Docks
        if hasattr(self, 'properties_dock') and hasattr(self, 'ai_chatbot_dock'):
            self.tabifyDockWidget(self.properties_dock, self.ai_chatbot_dock)
        if hasattr(self, 'ai_chatbot_dock') and hasattr(self, 'py_sim_dock'):
            self.tabifyDockWidget(self.ai_chatbot_dock, self.py_sim_dock)
        if hasattr(self, 'py_sim_dock') and hasattr(self, 'ide_dock'):
            self.tabifyDockWidget(self.py_sim_dock, self.ide_dock)
        if hasattr(self, 'log_dock') and hasattr(self, 'problems_dock'): # Ensure both exist
             self.tabifyDockWidget(self.log_dock, self.problems_dock)


    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self)
        self.view.setObjectName("MainDiagramView")
        self.view.setStyleSheet(f"background-color: {COLOR_BACKGROUND_LIGHT}; border: 1px solid {COLOR_BORDER_LIGHT};")
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
        self.save_as_action = QAction(
            get_standard_icon(_safe_get_style_enum("SP_DriveHDIcon", "SP_DialogSaveButton"), "SA"),
            "Save &As...", self, shortcut=QKeySequence.SaveAs,
            statusTip="Save the current file with a new name", triggered=self.on_save_file_as
        )
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

        self.start_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Py▶"), "&Start Python Simulation", self, statusTip="Start internal FSM simulation")
        self.stop_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaStop, "Py■"), "S&top Python Simulation", self, statusTip="Stop internal FSM simulation", enabled=False)
        self.reset_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaSkipBackward, "Py«"), "&Reset Python Simulation", self, statusTip="Reset internal FSM simulation", enabled=False)

        self.openai_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "AISet"), "AI Assistant Settings (Gemini)...", self)
        self.clear_ai_chat_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "Clear"), "Clear Chat History", self)
        self.ask_ai_to_generate_fsm_action = QAction(
            get_standard_icon(QStyle.SP_ArrowRight, "AIGen"),
            "Generate FSM from Description...",
            self
        )

        self.open_example_menu_action = QAction("Open E&xample...", self)
        self.quick_start_action = QAction(get_standard_icon(QStyle.SP_MessageBoxQuestion, "QS"), "&Quick Start Guide", self, triggered=self.on_show_quick_start)
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, triggered=self.on_about)

        self.zoom_in_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Z+"), "Zoom In", self, shortcut="Ctrl++", statusTip="Zoom in the view")
        if hasattr(self, 'view') and self.view: self.zoom_in_action.triggered.connect(self.view.zoom_in)

        self.zoom_out_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "Z-"), "Zoom Out", self, shortcut="Ctrl+-", statusTip="Zoom out the view")
        if hasattr(self, 'view') and self.view: self.zoom_out_action.triggered.connect(self.view.zoom_out)

        self.reset_zoom_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "Z0"), "Reset Zoom/View", self, shortcut="Ctrl+0", statusTip="Reset zoom and center view")
        if hasattr(self, 'view') and self.view: self.reset_zoom_action.triggered.connect(self.view.reset_view_and_zoom)

        self.zoom_to_selection_action = QAction(get_standard_icon(QStyle.SP_FileDialogDetailedView, "ZSel"), "Zoom to Selection", self, statusTip="Zoom to fit selected items", triggered=self.on_zoom_to_selection)
        self.zoom_to_selection_action.setEnabled(False)

        self.fit_diagram_action = QAction(get_standard_icon(QStyle.SP_FileDialogListView, "ZFit"), "Fit Diagram in View", self, statusTip="Fit entire diagram in view", triggered=self.on_fit_diagram_in_view)

        self.snap_to_objects_action = QAction("Snap to Objects", self, checkable=True, statusTip="Enable/disable snapping to object edges and centers")
        self.snap_to_grid_action = QAction("Snap to Grid", self, checkable=True, statusTip="Enable/disable snapping to grid")
        if hasattr(self, 'scene'): # Ensure scene exists
            self.snap_to_objects_action.setChecked(self.scene.snap_to_objects_enabled)
            self.snap_to_grid_action.setChecked(self.scene.snap_to_grid_enabled)
        self.snap_to_objects_action.triggered.connect(self.on_toggle_snap_to_objects)
        self.snap_to_grid_action.triggered.connect(self.on_toggle_snap_to_grid)

        self.align_left_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "AlL"), "Align Left", self, statusTip="Align selected items to the left", triggered=lambda: self.on_align_items("left"))
        self.align_center_h_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "AlCH"), "Align Center Horizontally", self, statusTip="Align selected items to their horizontal center", triggered=lambda: self.on_align_items("center_h"))
        self.align_right_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "AlR"), "Align Right", self, statusTip="Align selected items to the right", triggered=lambda: self.on_align_items("right"))
        self.align_top_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "AlT"), "Align Top", self, statusTip="Align selected items to the top", triggered=lambda: self.on_align_items("top"))
        self.align_middle_v_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "AlMV"), "Align Middle Vertically", self, statusTip="Align selected items to their vertical middle", triggered=lambda: self.on_align_items("middle_v"))
        self.align_bottom_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "AlB"), "Align Bottom", self, statusTip="Align selected items to the bottom", triggered=lambda: self.on_align_items("bottom"))

        self.distribute_h_action = QAction(get_standard_icon(QStyle.SP_ArrowLeft, "DstH"), "Distribute Horizontally", self, statusTip="Distribute selected items horizontally", triggered=lambda: self.on_distribute_items("horizontal"))
        self.distribute_v_action = QAction(get_standard_icon(QStyle.SP_ArrowUp, "DstV"), "Distribute Vertically", self, statusTip="Distribute selected items vertically", triggered=lambda: self.on_distribute_items("vertical"))

        self.align_actions = [self.align_left_action, self.align_center_h_action, self.align_right_action, self.align_top_action, self.align_middle_v_action, self.align_bottom_action]
        self.distribute_actions = [self.distribute_h_action, self.distribute_v_action]
        for action in self.align_actions: action.setEnabled(False)
        for action in self.distribute_actions: action.setEnabled(False)

        self.ide_new_file_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "IDENew"), "New Script", self, triggered=self.on_ide_new_file)
        self.ide_open_file_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "IDEOpn"), "Open Script...", self, triggered=self.on_ide_open_file)
        self.ide_save_file_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "IDESav"), "Save Script", self, triggered=self.on_ide_save_file)
        self.ide_save_as_file_action = QAction(get_standard_icon(_safe_get_style_enum("SP_DriveHDIcon", "SP_DialogSaveButton"), "IDESA"), "Save Script As...", self, triggered=self.on_ide_save_as_file)
        self.ide_run_script_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "IDERunPy"), "Run Python Script", self, triggered=self.on_ide_run_python_script)
        self.ide_analyze_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "IDEAI"), "Analyze with AI", self, triggered=self.on_ide_analyze_with_ai)

        self.find_item_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "Find"), "&Find Item...", self, shortcut=QKeySequence.Find, statusTip="Find an FSM element", triggered=self.on_show_find_item_dialog)
        logger.debug(f"MW: AI actions created. Settings: {self.openai_settings_action}, Clear: {self.clear_ai_chat_action}, Generate: {self.ask_ai_to_generate_fsm_action}")


    def _create_menus(self): # Structure from previous version
        menu_bar = self.menuBar(); file_menu = menu_bar.addMenu("&File"); file_menu.addAction(self.new_action); file_menu.addAction(self.open_action)
        example_menu = file_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ex"), "Open E&xample"); self.open_example_traffic_action = example_menu.addAction("Traffic Light FSM", lambda: self._open_example_file("traffic_light.bsm")); self.open_example_toggle_action = example_menu.addAction("Simple Toggle FSM", lambda: self._open_example_file("simple_toggle.bsm"))
        file_menu.addAction(self.save_action); file_menu.addAction(self.save_as_action); file_menu.addSeparator(); file_menu.addAction(self.export_simulink_action); file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        edit_menu = menu_bar.addMenu("&Edit"); edit_menu.addAction(self.undo_action); edit_menu.addAction(self.redo_action); edit_menu.addSeparator(); edit_menu.addAction(self.delete_action); edit_menu.addAction(self.select_all_action); edit_menu.addSeparator(); edit_menu.addAction(self.find_item_action); edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Mode"),"Interaction Mode"); mode_menu.addAction(self.select_mode_action); mode_menu.addAction(self.add_state_mode_action); mode_menu.addAction(self.add_transition_mode_action); mode_menu.addAction(self.add_comment_mode_action); edit_menu.addSeparator()
        align_distribute_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogDetailedView, "AD"), "Align & Distribute"); align_menu = align_distribute_menu.addMenu("Align"); align_menu.addAction(self.align_left_action); align_menu.addAction(self.align_center_h_action); align_menu.addAction(self.align_right_action); align_menu.addSeparator(); align_menu.addAction(self.align_top_action); align_menu.addAction(self.align_middle_v_action); align_menu.addAction(self.align_bottom_action)
        distribute_menu = align_distribute_menu.addMenu("Distribute"); distribute_menu.addAction(self.distribute_h_action); distribute_menu.addAction(self.distribute_v_action)
        sim_menu = menu_bar.addMenu("&Simulation"); py_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_MediaPlay, "PyS"), "Python Simulation (Internal)"); py_sim_menu.addAction(self.start_py_sim_action); py_sim_menu.addAction(self.stop_py_sim_action); py_sim_menu.addAction(self.reset_py_sim_action); sim_menu.addSeparator()
        matlab_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_ComputerIcon, "M"), "MATLAB/Simulink"); matlab_sim_menu.addAction(self.run_simulation_action); matlab_sim_menu.addAction(self.generate_code_action); matlab_sim_menu.addSeparator(); matlab_sim_menu.addAction(self.matlab_settings_action)
        self.view_menu = menu_bar.addMenu("&View"); self.view_menu.addAction(self.zoom_in_action); self.view_menu.addAction(self.zoom_out_action); self.view_menu.addAction(self.reset_zoom_action); self.view_menu.addSeparator(); self.view_menu.addAction(self.zoom_to_selection_action); self.view_menu.addAction(self.fit_diagram_action); self.view_menu.addSeparator()
        snap_menu = self.view_menu.addMenu("Snapping"); snap_menu.addAction(self.snap_to_grid_action); snap_menu.addAction(self.snap_to_objects_action)
        self.show_snap_guidelines_action = QAction("Show Dynamic Snap Guidelines", self, checkable=True, statusTip="Show/hide dynamic alignment guidelines during drag")
        self.show_snap_guidelines_action.setChecked(self.scene._show_dynamic_snap_guidelines if hasattr(self.scene, '_show_dynamic_snap_guidelines') else True); self.show_snap_guidelines_action.triggered.connect(self.on_toggle_show_snap_guidelines); snap_menu.addAction(self.show_snap_guidelines_action); self.view_menu.addSeparator()
        tools_menu = menu_bar.addMenu("&Tools"); ide_menu = tools_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogDetailedView, "IDE"), "Standalone Code IDE"); ide_menu.addAction(self.ide_new_file_action); ide_menu.addAction(self.ide_open_file_action); ide_menu.addAction(self.ide_save_file_action); ide_menu.addAction(self.ide_save_as_file_action); ide_menu.addSeparator(); ide_menu.addAction(self.ide_run_script_action); ide_menu.addAction(self.ide_analyze_action)
        ai_menu = menu_bar.addMenu("&AI Assistant"); ai_menu.addAction(self.ask_ai_to_generate_fsm_action); ai_menu.addAction(self.clear_ai_chat_action); ai_menu.addSeparator(); ai_menu.addAction(self.openai_settings_action)
        help_menu = menu_bar.addMenu("&Help"); help_menu.addAction(self.quick_start_action); help_menu.addAction(self.about_action)

    def _create_toolbars(self): # Structure from previous version
        icon_size = QSize(22,22); tb_style = Qt.ToolButtonIconOnly
        file_toolbar = self.addToolBar("File"); file_toolbar.setObjectName("FileToolBar"); file_toolbar.setIconSize(icon_size); file_toolbar.setToolButtonStyle(tb_style); file_toolbar.addAction(self.new_action); file_toolbar.addAction(self.open_action); file_toolbar.addAction(self.save_action)
        edit_toolbar = self.addToolBar("Edit"); edit_toolbar.setObjectName("EditToolBar"); edit_toolbar.setIconSize(icon_size); edit_toolbar.setToolButtonStyle(tb_style); edit_toolbar.addAction(self.undo_action); edit_toolbar.addAction(self.redo_action); edit_toolbar.addSeparator(); edit_toolbar.addAction(self.delete_action); edit_toolbar.addAction(self.find_item_action)
        tools_tb = self.addToolBar("Interaction Tools"); tools_tb.setObjectName("ToolsToolBar"); tools_tb.setIconSize(icon_size); tools_tb.setToolButtonStyle(tb_style); tools_tb.addAction(self.select_mode_action); tools_tb.addAction(self.add_state_mode_action); tools_tb.addAction(self.add_transition_mode_action); tools_tb.addAction(self.add_comment_mode_action)
        sim_toolbar = self.addToolBar("Simulation Tools"); sim_toolbar.setObjectName("SimulationToolBar"); sim_toolbar.setIconSize(icon_size); sim_toolbar.setToolButtonStyle(tb_style); sim_toolbar.addAction(self.start_py_sim_action); sim_toolbar.addAction(self.stop_py_sim_action); sim_toolbar.addAction(self.reset_py_sim_action); sim_toolbar.addSeparator(); sim_toolbar.addAction(self.export_simulink_action); sim_toolbar.addAction(self.run_simulation_action); sim_toolbar.addAction(self.generate_code_action)
        view_toolbar = self.addToolBar("View Tools"); view_toolbar.setObjectName("ViewToolBar"); view_toolbar.setIconSize(icon_size); view_toolbar.setToolButtonStyle(tb_style); view_toolbar.addAction(self.zoom_in_action); view_toolbar.addAction(self.zoom_out_action); view_toolbar.addAction(self.reset_zoom_action); view_toolbar.addSeparator(); view_toolbar.addAction(self.zoom_to_selection_action); view_toolbar.addAction(self.fit_diagram_action)
        align_toolbar = self.addToolBar("Alignment & Distribution"); align_toolbar.setObjectName("AlignDistributeToolBar"); align_toolbar.setIconSize(icon_size); align_toolbar.setToolButtonStyle(tb_style); align_toolbar.addAction(self.align_left_action); align_toolbar.addAction(self.align_center_h_action); align_toolbar.addAction(self.align_right_action); align_toolbar.addSeparator(); align_toolbar.addAction(self.align_top_action); align_toolbar.addAction(self.align_middle_v_action); align_toolbar.addAction(self.align_bottom_action); align_toolbar.addSeparator(); align_toolbar.addAction(self.distribute_h_action); align_toolbar.addAction(self.distribute_v_action)


    def _create_docks(self): # Updated to include ProblemsDock
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)
        # --- Tools Dock ---
        self.tools_dock = QDockWidget("Elements & Modes", self); self.tools_dock.setObjectName("ToolsDock")
        tools_widget_main = QWidget(); tools_widget_main.setObjectName("ToolsDockWidgetContents"); tools_main_layout = QVBoxLayout(tools_widget_main); tools_main_layout.setSpacing(8); tools_main_layout.setContentsMargins(8,8,8,8)
        mode_group_box = QGroupBox("Interaction Mode"); mode_layout = QVBoxLayout(); mode_layout.setSpacing(6)
        self.toolbox_select_button = QToolButton(); self.toolbox_select_button.setDefaultAction(self.select_mode_action); self.toolbox_add_state_button = QToolButton(); self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action); self.toolbox_transition_button = QToolButton(); self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action); self.toolbox_add_comment_button = QToolButton(); self.toolbox_add_comment_button.setDefaultAction(self.add_comment_mode_action)
        for btn in [self.toolbox_select_button, self.toolbox_add_state_button, self.toolbox_transition_button, self.toolbox_add_comment_button]: btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(20,20)); mode_layout.addWidget(btn)
        mode_group_box.setLayout(mode_layout); tools_main_layout.addWidget(mode_group_box)
        draggable_group_box = QGroupBox("Drag New Elements"); draggable_layout = QVBoxLayout(); draggable_layout.setSpacing(6)
        drag_state_btn = DraggableToolButton("State", "application/x-bsm-tool", "State"); drag_state_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St")); drag_initial_state_btn = DraggableToolButton("Initial State", "application/x-bsm-tool", "Initial State"); drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt")); drag_final_state_btn = DraggableToolButton("Final State", "application/x-bsm-tool", "Final State"); drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt")); drag_comment_btn = DraggableToolButton("Comment", "application/x-bsm-tool", "Comment"); drag_comment_btn.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))
        for btn in [drag_state_btn, drag_initial_state_btn, drag_final_state_btn, drag_comment_btn]: draggable_layout.addWidget(btn)
        draggable_group_box.setLayout(draggable_layout); tools_main_layout.addWidget(draggable_group_box)
        self.templates_group_box = QGroupBox("FSM Templates"); templates_layout = QVBoxLayout(); templates_layout.setSpacing(6); self.template_buttons_container = QWidget(); self.template_buttons_layout = QVBoxLayout(self.template_buttons_container); self.template_buttons_layout.setContentsMargins(0,0,0,0); self.template_buttons_layout.setSpacing(4); templates_layout.addWidget(self.template_buttons_container); templates_layout.addStretch(); self.templates_group_box.setLayout(templates_layout); tools_main_layout.addWidget(self.templates_group_box)
        tools_main_layout.addStretch(); self.tools_dock.setWidget(tools_widget_main); self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock)
        # --- Properties Dock ---
        self.properties_dock = QDockWidget("Item Properties", self); self.properties_dock.setObjectName("PropertiesDock")
        properties_widget = QWidget(); properties_layout = QVBoxLayout(properties_widget); properties_layout.setContentsMargins(8,8,8,8); properties_layout.setSpacing(6)
        self.properties_editor_label = QLabel("<i>Select an item to view its properties.</i>"); self.properties_editor_label.setObjectName("PropertiesLabel"); self.properties_editor_label.setWordWrap(True); self.properties_editor_label.setTextFormat(Qt.RichText); self.properties_editor_label.setAlignment(Qt.AlignTop | Qt.AlignLeft); properties_layout.addWidget(self.properties_editor_label, 1)
        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"),"Edit Properties...") ; self.properties_edit_button.setEnabled(False); self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock); properties_layout.addWidget(self.properties_edit_button)
        self.properties_dock.setWidget(properties_widget); self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        # --- Log Dock ---
        self.log_dock = QDockWidget("Application Log", self); self.log_dock.setObjectName("LogDock")
        log_widget = QWidget(); log_layout = QVBoxLayout(log_widget); log_layout.setContentsMargins(0,0,0,0); self.log_output = QTextEdit(); self.log_output.setObjectName("LogOutputWidget"); self.log_output.setReadOnly(True); log_layout.addWidget(self.log_output); self.log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock); self.log_dock.setVisible(True)
        # --- Problems Dock (NEW) ---
        self.problems_dock = QDockWidget("Validation Issues", self); self.problems_dock.setObjectName("ProblemsDock")
        self.problems_list_widget = QListWidget(); self.problems_list_widget.itemDoubleClicked.connect(self.on_problem_item_double_clicked)
        self.problems_dock.setWidget(self.problems_list_widget); self.addDockWidget(Qt.BottomDockWidgetArea, self.problems_dock); self.problems_dock.setVisible(True)
        # --- Python Simulation Dock ---
        self.py_sim_dock = QDockWidget("Python Simulation", self); self.py_sim_dock.setObjectName("PySimDock"); self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock); self.py_sim_dock.setVisible(False)
        # --- AI Chatbot Dock ---
        self.ai_chatbot_dock = QDockWidget("AI Assistant", self); self.ai_chatbot_dock.setObjectName("AIChatbotDock"); self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock); self.ai_chatbot_dock.setVisible(False)
        # --- IDE Dock ---
        self._setup_ide_dock_widget(); self.ide_dock.setVisible(False) if hasattr(self, 'ide_dock') else None
        # --- Tabify Docks ---
        self.tabifyDockWidget(self.properties_dock, self.ai_chatbot_dock)
        self.tabifyDockWidget(self.ai_chatbot_dock, self.py_sim_dock)
        if hasattr(self, 'ide_dock'): self.tabifyDockWidget(self.py_sim_dock, self.ide_dock)
        self.tabifyDockWidget(self.log_dock, self.problems_dock) # Tabify problems with log
        # --- View Menu for Docks ---
        if hasattr(self, 'view_menu'):
            self.view_menu.addAction(self.tools_dock.toggleViewAction()); self.view_menu.addAction(self.properties_dock.toggleViewAction())
            self.view_menu.addAction(self.log_dock.toggleViewAction()); self.view_menu.addAction(self.problems_dock.toggleViewAction()) # Add problems dock toggle
            self.view_menu.addAction(self.py_sim_dock.toggleViewAction()); self.view_menu.addAction(self.ai_chatbot_dock.toggleViewAction())
            if hasattr(self, 'ide_dock'): self.view_menu.addAction(self.ide_dock.toggleViewAction())
        self._load_and_display_templates()


    def _create_status_bar(self):
        self.status_bar = QStatusBar(self); self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready"); self.status_bar.addWidget(self.status_label, 1)
        self.zoom_status_label = QLabel("Zoom: 100%"); self.zoom_status_label.setMinimumWidth(80); self.zoom_status_label.setAlignment(Qt.AlignCenter); self.zoom_status_label.setObjectName("ZoomStatusLabel"); self.zoom_status_label.setStyleSheet(f"font-size:{APP_FONT_SIZE_SMALL}; padding:2px 4px;"); self.status_bar.addPermanentWidget(self.zoom_status_label)
        self.cpu_status_label = QLabel("CPU: --%"); self.cpu_status_label.setToolTip("CPU Usage"); self.ram_status_label = QLabel("RAM: --%"); self.ram_status_label.setToolTip("RAM Usage"); self.gpu_status_label = QLabel("GPU: N/A"); self.gpu_status_label.setToolTip("GPU Usage (NVIDIA only, if pynvml installed)");
        for label in [self.cpu_status_label, self.ram_status_label, self.gpu_status_label]: label.setMinimumWidth(80); label.setAlignment(Qt.AlignCenter); self.status_bar.addPermanentWidget(label)
        self.py_sim_status_label = QLabel("PySim: Idle"); self.py_sim_status_label.setToolTip("Internal Python FSM Simulation Status."); self.py_sim_status_label.setMinimumWidth(120); self.py_sim_status_label.setAlignment(Qt.AlignCenter); self.status_bar.addPermanentWidget(self.py_sim_status_label)
        self.matlab_status_label = QLabel("MATLAB: Init..."); self.matlab_status_label.setToolTip("MATLAB connection status."); self.matlab_status_label.setMinimumWidth(140); self.matlab_status_label.setAlignment(Qt.AlignCenter); self.status_bar.addPermanentWidget(self.matlab_status_label)
        self.internet_status_label = QLabel("Net: Init..."); self.internet_status_label.setToolTip("Internet connectivity. Checks periodically."); self.internet_status_label.setMinimumWidth(90); self.internet_status_label.setAlignment(Qt.AlignCenter); self.status_bar.addPermanentWidget(self.internet_status_label)
        self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0,0); self.progress_bar.setVisible(False); self.progress_bar.setMaximumWidth(160); self.progress_bar.setTextVisible(False); self.status_bar.addPermanentWidget(self.progress_bar)

    def _init_resource_monitor(self):
        self.resource_monitor_thread = QThread(self)
        self.resource_monitor_thread.setObjectName("ResourceMonitorQThread")
        self.resource_monitor_worker = ResourceMonitorWorker(interval_ms=2000)
        self.resource_monitor_worker.moveToThread(self.resource_monitor_thread)

        self.resource_monitor_worker.resourceUpdate.connect(self._update_resource_display)
        self.resource_monitor_thread.started.connect(self.resource_monitor_worker.start_monitoring)

        self.resource_monitor_worker.finished_signal.connect(self.resource_monitor_thread.quit)
        self.resource_monitor_thread.finished.connect(self.resource_monitor_worker.deleteLater)
        self.resource_monitor_thread.finished.connect(self.resource_monitor_thread.deleteLater)

        self.resource_monitor_thread.start()
        logger.info("Resource monitor thread initialized and started.")


    def _setup_ide_dock_widget(self):
        self.ide_dock = QDockWidget("Standalone Code IDE", self)
        self.ide_dock.setObjectName("IDEDock")
        self.ide_dock.setAllowedAreas(Qt.AllDockWidgetAreas) # Allow docking anywhere

        ide_main_widget = QWidget()
        ide_main_layout = QVBoxLayout(ide_main_widget)
        ide_main_layout.setContentsMargins(0,0,0,0) # No external margins for the layout
        ide_main_layout.setSpacing(0) # No spacing between toolbar and editor

        # IDE Toolbar
        ide_toolbar = QToolBar("IDE Tools")
        ide_toolbar.setIconSize(QSize(20,20)) # Consistent icon size
        ide_toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly) # Or ToolButtonTextBesideIcon

        ide_toolbar.addAction(self.ide_new_file_action)
        ide_toolbar.addAction(self.ide_open_file_action)
        ide_toolbar.addAction(self.ide_save_file_action)
        ide_toolbar.addAction(self.ide_save_as_file_action)
        ide_toolbar.addSeparator()
        ide_toolbar.addAction(self.ide_run_script_action)
        ide_toolbar.addSeparator()

        # Language ComboBox
        self.ide_language_combo = QComboBox()
        self.ide_language_combo.addItems(["Python", "C/C++ (Arduino)", "C/C++ (Generic)", "Text"])
        self.ide_language_combo.setToolTip("Select language for syntax highlighting and context")
        self.ide_language_combo.currentTextChanged.connect(self._on_ide_language_changed)
        ide_toolbar.addWidget(QLabel(" Language: ")) # Add a label before the combo box
        # Add a container for the combo box to control its size better in the toolbar
        ide_language_combo_container = QWidget()
        ide_language_combo_layout = QHBoxLayout(ide_language_combo_container)
        ide_language_combo_layout.setContentsMargins(2,0,2,0) # Small margins
        ide_language_combo_layout.addWidget(self.ide_language_combo)
        ide_toolbar.addWidget(ide_language_combo_container)
        ide_toolbar.addSeparator()
        ide_toolbar.addAction(self.ide_analyze_action)


        ide_main_layout.addWidget(ide_toolbar)

        # Code Editor
        self.ide_code_editor = CodeEditor() # Assuming CodeEditor is imported
        self.ide_code_editor.setObjectName("StandaloneCodeEditor")
        self.ide_code_editor.setPlaceholderText("Create a new file or open an existing script...")
        self.ide_code_editor.textChanged.connect(self._on_ide_text_changed) # Connect signal for dirty status
        ide_main_layout.addWidget(self.ide_code_editor, 1) # Editor takes most space

        # Output Console
        self.ide_output_console = QTextEdit()
        self.ide_output_console.setObjectName("IDEOutputConsole")
        self.ide_output_console.setReadOnly(True)
        self.ide_output_console.setPlaceholderText("Script output will appear here...")
        self.ide_output_console.setFixedHeight(160) # Fixed height for console
        ide_main_layout.addWidget(self.ide_output_console)

        self.ide_dock.setWidget(ide_main_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ide_dock) # Or preferred area

        self._update_ide_save_actions_enable_state() # Initial state of save actions
        self._on_ide_language_changed(self.ide_language_combo.currentText()) # Set initial language for editor




    def _load_and_display_templates(self):
        # Clear existing template buttons if any
        # Accessing template_buttons_layout directly might be risky if it's not guaranteed to exist.
        # It's safer to check if self.templates_group_box and its layout exist first.
        if hasattr(self, 'template_buttons_layout') and self.template_buttons_layout is not None:
            while self.template_buttons_layout.count():
                child = self.template_buttons_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        else:
            logger.warning("MainWindow: template_buttons_layout not found. Cannot clear/load templates.")
            return # Can't proceed if the layout isn't there

        templates_to_load = []
        # Load built-in templates
        for template_key, template_data_json_str in FSM_TEMPLATES_BUILTIN.items():
            try:
                template_data = json.loads(template_data_json_str)
                templates_to_load.append({
                    "id": f"builtin_{template_key}", # Unique ID for the template
                    "name": template_data.get("name", "Unnamed Template"),
                    "description": template_data.get("description", ""),
                    "icon_resource": template_data.get("icon_resource"), # Path like ":/icons/my_icon.png"
                    "data_json_str": template_data_json_str # The full JSON string for dropping
                })
            except json.JSONDecodeError as e:
                logger.error(f"Error loading built-in template '{template_key}': {e}")

        # --- Placeholder for loading custom/user templates from a directory ---
        # custom_template_dir = "path/to/user_templates"
        # if os.path.exists(custom_template_dir):
        #     for filename in os.listdir(custom_template_dir):
        #         if filename.endswith(".bsmtpl") or filename.endswith(".json"): # Define a template extension
        #             try:
        #                 with open(os.path.join(custom_template_dir, filename), 'r') as f:
        #                     template_data = json.load(f)
        #                 templates_to_load.append({
        #                     "id": f"custom_{os.path.splitext(filename)[0]}",
        #                     "name": template_data.get("name", os.path.splitext(filename)[0]),
        #                     "description": template_data.get("description", ""),
        #                     "icon_resource": template_data.get("icon_resource"),
        #                     "data_json_str": json.dumps(template_data) # Re-serialize for consistency
        #                 })
        #             except Exception as e:
        #                 logger.error(f"Error loading custom template '{filename}': {e}")
        # --- End Placeholder ---


        for template_info in templates_to_load:
            icon = QIcon()
            if template_info.get("icon_resource"):
                icon = QIcon(template_info["icon_resource"]) # Load from Qt resources
            if icon.isNull(): # Fallback icon
                icon = get_standard_icon(QStyle.SP_FileDialogContentsView, "Tmpl")

            template_btn = DraggableToolButton(
                template_info["name"],
                MIME_TYPE_BSM_TEMPLATE, # Use the defined MIME type
                template_info["data_json_str"] # Pass the full JSON string
            )
            template_btn.setIcon(icon)
            template_btn.setToolTip(template_info.get("description", template_info["name"]))
            self.template_buttons_layout.addWidget(template_btn)

        self.template_buttons_layout.addStretch(1) # Add stretch after all buttons


    @pyqtSlot(list) # Slot to receive validation issues from the scene
    def update_problems_dock(self, issues_with_items: list):
        if not self.problems_list_widget:
            logger.error("Problems dock list widget not initialized.")
            return

        self.problems_list_widget.clear()
        if issues_with_items:
            for issue_msg, item_ref in issues_with_items:
                list_item_widget = QListWidgetItem(str(issue_msg)) # Ensure message is string
                if item_ref: # Store the item reference if available
                    list_item_widget.setData(Qt.UserRole, item_ref)
                self.problems_list_widget.addItem(list_item_widget)

            self.problems_dock.setWindowTitle(f"Validation Issues ({len(issues_with_items)})")
            if self.problems_dock.isHidden() and len(issues_with_items) > 0: # Optionally show if errors
                self.problems_dock.show()
                self.problems_dock.raise_()
        else:
            self.problems_list_widget.addItem("No validation issues found.")
            self.problems_dock.setWindowTitle("Validation Issues")

    @pyqtSlot(QListWidgetItem) # Slot for double-clicking an issue
    def on_problem_item_double_clicked(self, list_item: QListWidgetItem):
        item_ref = list_item.data(Qt.UserRole)
        if item_ref and isinstance(item_ref, QGraphicsItem) and item_ref.scene() == self.scene:
            self.focus_on_item(item_ref) # Use existing focus method
            logger.info(f"Focused on problematic item from Validation Issues list: {getattr(item_ref, 'text_label', type(item_ref).__name__)}")
        else:
            logger.debug(f"No valid QGraphicsItem reference found for clicked validation issue: '{list_item.text()}'")


    @pyqtSlot(float)
    def update_zoom_status_display(self, scale_factor: float):
        if hasattr(self, 'zoom_status_label'):
            zoom_percentage = int(scale_factor * 100)
            self.zoom_status_label.setText(f"Zoom: {zoom_percentage}%")

    @pyqtSlot(float, float, float, str)
    def _update_resource_display(self, cpu_usage, ram_usage, gpu_util, gpu_name):
        if hasattr(self, 'cpu_status_label'): self.cpu_status_label.setText(f"CPU: {cpu_usage:.0f}%")
        if hasattr(self, 'ram_status_label'): self.ram_status_label.setText(f"RAM: {ram_usage:.0f}%")
        if hasattr(self, 'gpu_status_label'):
            if gpu_util == -1.0: self.gpu_status_label.setText(f"GPU: {gpu_name}")
            elif gpu_util == -2.0: self.gpu_status_label.setText(f"GPU: Error")
            elif gpu_util == -3.0: self.gpu_status_label.setText(f"GPU: Mon Error")
            elif PYNVML_AVAILABLE and self.resource_monitor_worker and self.resource_monitor_worker._nvml_initialized and self.resource_monitor_worker._gpu_handle:
                self.gpu_status_label.setText(f"GPU: {gpu_util:.0f}%")
                self.gpu_status_label.setToolTip(f"GPU: {gpu_util:.0f}% ({gpu_name})")
            else:
                 self.gpu_status_label.setText(f"GPU: N/A")
                 self.gpu_status_label.setToolTip(gpu_name)

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
        if hasattr(self, 'properties_edit_button'):
             self.properties_edit_button.setEnabled(is_editable and len(self.scene.selectedItems())==1)

        for item in self.scene.items():
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)):
                item.setFlag(QGraphicsItem.ItemIsMovable, is_editable and self.scene.current_mode == "select")

        if not is_editable and self.scene.current_mode != "select":
            self.scene.set_mode("select")
        self._update_matlab_actions_enabled_state()
        self._update_py_simulation_actions_enabled_state()

    def _add_fsm_data_to_scene(self, fsm_data: dict, clear_current_diagram: bool = False, original_user_prompt: str = "AI Generated FSM"):
        logger.info("MW: ADD_FSM_TO_SCENE clear_current_diagram=%s", clear_current_diagram)
        logger.debug("MW: Received FSM Data (states: %d, transitions: %d)", len(fsm_data.get('states',[])), len(fsm_data.get('transitions',[])))
        if clear_current_diagram:
            if not self.on_new_file(silent=True): logger.warning("MW: Clearing diagram cancelled by user (save prompt). Cannot add AI FSM."); return
            logger.info("MW: Cleared diagram before AI generation.")
        if not clear_current_diagram: self.undo_stack.beginMacro(f"Add AI FSM: {original_user_prompt[:30]}...")
        state_items_map = {}; items_to_add_for_undo_command = []
        layout_start_x, layout_start_y = 100, 100; default_item_width, default_item_height = 120, 60; GV_SCALE = 1.3; NODE_SEP = 0.8; RANK_SEP = 1.5
        G = pgv.AGraph(directed=True, strict=False, rankdir='TB', ratio='auto', nodesep=str(NODE_SEP), ranksep=str(RANK_SEP)); G.node_attr['shape'] = 'box'; G.node_attr['style'] = 'rounded,filled'; G.node_attr['fillcolor'] = QColor(COLOR_ITEM_STATE_DEFAULT_BG).name(); G.node_attr['color'] = QColor(COLOR_ITEM_STATE_DEFAULT_BORDER).name(); G.node_attr['fontname'] = "Arial"; G.node_attr['fontsize'] = "10"; G.edge_attr['color'] = QColor(COLOR_ITEM_TRANSITION_DEFAULT).name(); G.edge_attr['fontname'] = "Arial"; G.edge_attr['fontsize'] = "9"
        for state_data in fsm_data.get('states', []): name = state_data.get('name'); label = (name[:25] + '...') if name and len(name) > 28 else name; G.add_node(name, label=label, width=str(default_item_width/72.0 * 1.1), height=str(default_item_height/72.0 * 1.1)) if name else None
        for trans_data in fsm_data.get('transitions', []): source, target = trans_data.get('source'), trans_data.get('target'); event_label = trans_data.get('event', ''); event_label = (event_label[:12] + '...') if len(event_label) > 15 else event_label; G.add_edge(source, target, label=event_label) if source and target and G.has_node(source) and G.has_node(target) else logger.warning("MW: Skipping Graphviz edge for AI FSM due to missing node(s): %s->%s", source, target)
        graphviz_positions = {}
        try:
            G.layout(prog="dot"); logger.debug("MW: Graphviz layout ('dot') for AI FSM successful.")
            raw_gv_pos = [{'name': n.name, 'x': float(n.attr['pos'].split(',')[0]), 'y': float(n.attr['pos'].split(',')[1])} for n in G.nodes() if 'pos' in n.attr]
            if raw_gv_pos: min_x_gv = min(p['x'] for p in raw_gv_pos); max_y_gv = max(p['y'] for p in raw_gv_pos); [graphviz_positions.update({p_gv['name']: QPointF((p_gv['x'] - min_x_gv) * GV_SCALE + layout_start_x, (max_y_gv - p_gv['y']) * GV_SCALE + layout_start_y)}) for p_gv in raw_gv_pos]
            elif fsm_data.get('states'): logger.warning("MW: Graphviz - No valid positions extracted for AI FSM nodes, though states exist.")
        except Exception as e: logger.error("MW: Graphviz layout error for AI FSM: %s. Falling back to grid.", str(e).strip() or "Unknown", exc_info=True); self.ai_chat_ui_manager._append_to_chat_display("System", f"Warning: AI FSM layout failed (Graphviz error). Using basic grid layout.") if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager else None; graphviz_positions = {}
        for i, state_data in enumerate(fsm_data.get('states', [])):
            name = state_data.get('name'); item_w, item_h = default_item_width, default_item_height
            if not name: logger.warning("MW: AI State data missing 'name'. Skipping."); continue
            pos = graphviz_positions.get(name); pos_x, pos_y = (pos.x(), pos.y()) if pos else (layout_start_x + (i % 3) * (item_w + 180), layout_start_y + (i // 3) * (item_h + 120))
            try: state_item = GraphicsStateItem(pos_x, pos_y, item_w, item_h, name, is_initial=state_data.get('is_initial', False), is_final=state_data.get('is_final', False), color=state_data.get('properties', {}).get('color', state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG)), entry_action=state_data.get('entry_action', ""), during_action=state_data.get('during_action', ""), exit_action=state_data.get('exit_action', ""), description=state_data.get('description', fsm_data.get('description', "") if i==0 else ""), is_superstate=state_data.get('is_superstate', False), sub_fsm_data=state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]})); self.connect_state_item_signals(state_item); items_to_add_for_undo_command.append(state_item); state_items_map[name] = state_item
            except Exception as e: logger.error("MW: Error creating AI GraphicsStateItem '%s': %s", name, e, exc_info=True)
        for trans_data in fsm_data.get('transitions', []):
            src_name, tgt_name = trans_data.get('source'), trans_data.get('target')
            if not src_name or not tgt_name: logger.warning("MW: AI Transition missing source/target. Skipping."); continue
            src_item, tgt_item = state_items_map.get(src_name), state_items_map.get(tgt_name)
            if src_item and tgt_item:
                try: trans_item = GraphicsTransitionItem(src_item, tgt_item, event_str=trans_data.get('event', ""), condition_str=trans_data.get('condition', ""), action_str=trans_data.get('action', ""), color=trans_data.get('properties', {}).get('color', trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT)), description=trans_data.get('description', "")); ox, oy = trans_data.get('control_offset_x'), trans_data.get('control_offset_y'); trans_item.set_control_point_offset(QPointF(float(ox), float(oy))) if ox is not None and oy is not None else None; items_to_add_for_undo_command.append(trans_item)
                except ValueError: logger.warning("MW: Invalid AI control offsets for transition %s->%s.", src_name, tgt_name)
                except Exception as e: logger.error("MW: Error creating AI GraphicsTransitionItem %s->%s: %s", src_name, tgt_name, e, exc_info=True)
            else: logger.warning("MW: Could not find source/target GraphicsStateItem for AI transition: %s->%s. Skipping.", src_name, tgt_name)
        max_y_items = max((item.scenePos().y() + item.boundingRect().height() for item in state_items_map.values() if item.scenePos()), default=layout_start_y) if state_items_map else layout_start_y
        for i, comment_data in enumerate(fsm_data.get('comments', [])):
            text = comment_data.get('text'); width = comment_data.get('width'); pos_x = comment_data.get('x', layout_start_x + i * (180 + 25)); pos_y = comment_data.get('y', max_y_items + 120)
            if not text: continue
            try: comment_item = GraphicsCommentItem(pos_x, pos_y, text); comment_item.setTextWidth(float(width)) if width else None; items_to_add_for_undo_command.append(comment_item)
            except ValueError: logger.warning("MW: Invalid AI width for comment.")
            except Exception as e: logger.error("MW: Error creating AI GraphicsCommentItem: %s", e, exc_info=True)
        if items_to_add_for_undo_command:
            for item_to_add in items_to_add_for_undo_command: item_type_name = type(item_to_add).__name__.replace("Graphics","").replace("Item",""); cmd_text = f"Add AI {item_type_name}" + (f": {item_to_add.text_label}" if hasattr(item_to_add, 'text_label') and item_to_add.text_label else ""); self.undo_stack.push(AddItemCommand(self.scene, item_to_add, cmd_text))
            logger.info("MW: Added %d AI-generated items to diagram.", len(items_to_add_for_undo_command)); QTimer.singleShot(100, self._fit_view_to_new_ai_items)
        else: logger.info("MW: No valid AI-generated items to add.")
        if not clear_current_diagram: self.undo_stack.endMacro()
        if self.py_sim_active and items_to_add_for_undo_command:
            logger.info("MW: Reinitializing Python simulation after adding AI FSM.")
            try: self.py_sim_ui_manager.on_stop_py_simulation(silent=True); self.py_sim_ui_manager.on_start_py_simulation(); self.py_sim_ui_manager.append_to_action_log(["Python FSM Simulation reinitialized for new diagram from AI."]) if self.py_sim_ui_manager else None
            except FSMError as e: self.py_sim_ui_manager.append_to_action_log([f"ERROR Re-initializing Sim after AI: {e}"]); self.py_sim_ui_manager.on_stop_py_simulation(silent=True) if self.py_sim_ui_manager else None
        logger.debug("MW: ADD_FSM_TO_SCENE processing finished. Items involved: %d", len(items_to_add_for_undo_command)); self.scene.scene_content_changed_for_find.emit()

    def _fit_view_to_new_ai_items(self):
        if not self.scene.items(): return
        items_bounds = self.scene.itemsBoundingRect()
        if self.view and not items_bounds.isNull():
            self.view.fitInView(items_bounds.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)
            logger.info("MW: View adjusted to AI generated items.")
        elif self.view and self.scene.sceneRect():
            self.view.centerOn(self.scene.sceneRect().center())


    def on_matlab_settings(self):
        dialog = MatlabSettingsDialog(matlab_connection=self.matlab_connection, parent=self)
        dialog.exec()
        logger.info("MATLAB settings dialog closed.")


    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems()
        html_content = ""
        edit_enabled = False
        item_type_tooltip = "item"

        font_family_css = f"font-family: '{APP_FONT_FAMILY.split(',')[0].strip()}', sans-serif;"
        std_font_size_css = f"font-size: {APP_FONT_SIZE_STANDARD};"
        small_font_size_css = f"font-size: {APP_FONT_SIZE_SMALL};"
        
        if len(selected_items) == 1:
            item = selected_items[0]
            props = item.get_data() if hasattr(item, 'get_data') else {}
            item_type_name = type(item).__name__.replace("Graphics", "").replace("Item", "")
            item_type_tooltip = item_type_name
            edit_enabled = True

            def fmt(txt, max_lines=2, max_line_chars=35, is_code=False):
                none_style = f"color:{COLOR_TEXT_SECONDARY}; font-style:italic; {small_font_size_css}"
                if not txt: return f"<span style='{none_style}'>(none)</span>"
                
                txt_str = str(txt)
                lines = txt_str.split('\n')
                
                display_lines = []
                for i, line_content in enumerate(lines): 
                    if i < max_lines:
                        escaped_line = html.escape(line_content)
                        if len(escaped_line) > max_line_chars:
                            display_lines.append(escaped_line[:max_line_chars] + "…")
                        else:
                            display_lines.append(escaped_line)
                    else:
                        if display_lines: 
                             display_lines[-1] += " …" 
                        else: 
                             display_lines.append("…")
                        break
                
                display_html = "<br>".join(display_lines)

                if is_code:
                    style = (f"font-family: Consolas, 'Courier New', monospace; {small_font_size_css} "
                             f"background-color: {QColor(COLOR_BACKGROUND_EDITOR_DARK).lighter(115).name()}; "
                             f"color: {COLOR_TEXT_EDITOR_DARK_PRIMARY}; padding: 2px 4px; border-radius: 3px; "
                             f"border: 1px solid {QColor(COLOR_BORDER_DARK).lighter(110).name()}; "
                             f"display: block; white-space: pre-wrap; overflow: hidden; text-overflow: ellipsis;")
                else:
                    style = small_font_size_css 

                if is_code and not txt.strip(): 
                    return f"<span style='{style.replace('display: block;', '')} {none_style.replace('font-style:italic;','')}'> (none) </span>"
                
                return f"<span style='{style}'>{display_html}</span>"

            def bool_fmt(val):
                 color_name = COLOR_ACCENT_SUCCESS if val else QColor(COLOR_TEXT_SECONDARY).darker(110).name()
                 text = "Yes" if val else "No"
                 current_std_font_size_css_local = f"font-size: {APP_FONT_SIZE_STANDARD};" 
                 return f"<span style='color:{color_name}; font-weight:bold; {current_std_font_size_css_local}'>{text}</span>"
            
            rows = ""
            table_style = f"width:100%; border-collapse:collapse; {std_font_size_css} {font_family_css}"
            td_key_style = f"padding:5px 8px; text-align:right; font-weight:normal; color:{COLOR_TEXT_SECONDARY}; border-bottom:1px solid {COLOR_BORDER_LIGHT}; width:38%; vertical-align:top;"
            td_val_style = f"padding:5px 8px; border-bottom:1px solid {COLOR_BORDER_LIGHT}; vertical-align:top; word-break:break-all;" 

            item_header_html = f"""
                <div style='{font_family_css}'>
                    <h4 style='margin:0 0 10px 0; padding-bottom:5px; color:{COLOR_ACCENT_PRIMARY}; border-bottom:2px solid {COLOR_BORDER_MEDIUM}; font-size:11pt; font-weight:bold;'>
                        {item_type_name} Properties
                    </h4>
                <table style='{table_style}'>
            """

            if isinstance(item, GraphicsStateItem):
                color_obj = QColor(props.get('color', COLOR_ITEM_STATE_DEFAULT_BG))
                color_style = f"display:inline-block; width:12px; height:12px; border:1px solid {color_obj.darker(120).name()}; background-color:{color_obj.name()}; margin-right:5px; vertical-align:middle;"

                rows += f"<tr><td style='{td_key_style}'>Name:</td><td style='{td_val_style}'><b>{html.escape(props.get('name', 'N/A'))}</b></td></tr>"
                rows += f"<tr><td style='{td_key_style}'>Initial:</td><td style='{td_val_style}'>{bool_fmt(props.get('is_initial'))}</td></tr>"
                rows += f"<tr><td style='{td_key_style}'>Final:</td><td style='{td_val_style}'>{bool_fmt(props.get('is_final'))}</td></tr>"

                if props.get('is_superstate'):
                    sub_states_count = len(props.get('sub_fsm_data',{}).get('states',[]))
                    rows += f"<tr><td style='{td_key_style}'>Superstate:</td><td style='{td_val_style}'><span style='color:{COLOR_ACCENT_PRIMARY}; font-weight:bold;'>Yes</span> ({sub_states_count} sub-state{'s' if sub_states_count != 1 else ''})</td></tr>"

                rows += f"<tr><td style='{td_key_style}'>Color:</td><td style='{td_val_style}'><span style='{color_style}'></span>{html.escape(color_obj.name())}</td></tr>"
                rows += f"<tr><td style='{td_key_style}'>Action Lang:</td><td style='{td_val_style}'><span style='font-family:Consolas,monospace; font-size:{APP_FONT_SIZE_SMALL}'>{html.escape(props.get('action_language','N/A'))}</span></td></tr>"
                for act_key in ['entry_action', 'during_action', 'exit_action']:
                    act_label = act_key.replace('_action','').capitalize()
                    rows += f"<tr><td style='{td_key_style}'>{act_label}:</td><td style='{td_val_style}'>{fmt(props.get(act_key, ''), max_lines=3, max_line_chars=40, is_code=True)}</td></tr>"
                if props.get('description'): rows += f"<tr><td style='{td_key_style}'>Desc:</td><td style='{td_val_style}white-space:normal;{small_font_size_css}'>{fmt(props.get('description'), max_lines=3, max_line_chars=50)}</td></tr>"


            elif isinstance(item, GraphicsTransitionItem):
                color_obj = QColor(props.get('color', COLOR_ITEM_TRANSITION_DEFAULT))
                color_style = f"display:inline-block; width:12px; height:12px; border:1px solid {color_obj.darker(120).name()}; background-color:{color_obj.name()}; margin-right:5px; vertical-align:middle;"

                label_parts = []
                if props.get('event'): label_parts.append(f"<b style='color:{COLOR_ACCENT_PRIMARY};'>{html.escape(props.get('event'))}</b>")
                if props.get('condition'): label_parts.append(f"<span style='font-family:Consolas,monospace; color:{COLOR_TEXT_SECONDARY}; {small_font_size_css}'>[{fmt(props.get('condition'), max_lines=1, max_line_chars=25, is_code=True)}]</span>") 
                if props.get('action'): label_parts.append(f"<span style='font-family:Consolas,monospace;color:{QColor(COLOR_ACCENT_SECONDARY).darker(110).name()}; {small_font_size_css}'>/{{{fmt(props.get('action'), max_lines=1, max_line_chars=25, is_code=True)}}}</span>") 
                full_label = " ".join(p for p in label_parts if p) or f"<span style='color:{COLOR_TEXT_SECONDARY}; font-style:italic; {small_font_size_css}'>(No Label)</span>"

                rows += f"<tr><td style='{td_key_style}'>Label:</td><td style='{td_val_style} {std_font_size_css}'>{full_label}</td></tr>"
                rows += f"<tr><td style='{td_key_style}'>From / To:</td><td style='{td_val_style}'><b>{html.escape(props.get('source','N/A'))}</b> → <b>{html.escape(props.get('target','N/A'))}</b></td></tr>"
                rows += f"<tr><td style='{td_key_style}'>Action Lang:</td><td style='{td_val_style}'><span style='font-family:Consolas,monospace; {small_font_size_css}'>{html.escape(props.get('action_language','N/A'))}</span></td></tr>"
                rows += f"<tr><td style='{td_key_style}'>Action:</td><td style='{td_val_style}'>{fmt(props.get('action', ''), max_lines=3, max_line_chars=40, is_code=True)}</td></tr>"

                rows += f"<tr><td style='{td_key_style}'>Color:</td><td style='{td_val_style}'><span style='{color_style}'></span>{html.escape(color_obj.name())}</td></tr>"
                rows += f"<tr><td style='{td_key_style}'>Curve (Bend/Shift):</td><td style='{td_val_style}'>{props.get('control_offset_x',0):.0f} / {props.get('control_offset_y',0):.0f}</td></tr>"
                if props.get('description'): rows += f"<tr><td style='{td_key_style}'>Desc:</td><td style='{td_val_style}white-space:normal;{small_font_size_css}'>{fmt(props.get('description'),max_lines=3, max_line_chars=50)}</td></tr>"

            elif isinstance(item, GraphicsCommentItem):
                rows += f"<tr><td style='{td_key_style}'>Text:</td><td style='{td_val_style}white-space:pre-wrap; font-style:italic; color:{COLOR_TEXT_SECONDARY};'>{fmt(props.get('text', ''), max_lines=5, max_line_chars=50)}</td></tr>" 
                rows += f"<tr><td style='{td_key_style}'>Width:</td><td style='{td_val_style}'>{props.get('width', 'N/A')} px</td></tr>"
            else:
                rows = f"<tr><td colspan='2' style='{td_val_style}text-align:center;'>Unknown Item Type</td></tr>"
                item_type_name = "Unknown"

            html_content = f"{item_header_html}{rows}</table></div>"
        elif len(selected_items) > 1:
            html_content = f"<div style='{font_family_css} {std_font_size_css} padding:10px;text-align:center;'><i><b>{len(selected_items)} items selected.</b><br><span style='{small_font_size_css} color:{COLOR_TEXT_SECONDARY};'>Select a single item to view or edit its properties.</span></i></div>"
            item_type_tooltip = f"{len(selected_items)} items"
        else:
            html_content = f"<div style='{font_family_css} {std_font_size_css} padding:10px;text-align:center;'><i>No item selected.</i><br><span style='{small_font_size_css} color:{COLOR_TEXT_SECONDARY};'>Click an item in the diagram or use the tools to add new elements.</span></div>"

        self.properties_editor_label.setText(html_content)
        self.properties_edit_button.setEnabled(edit_enabled)
        self.properties_edit_button.setToolTip(f"Edit properties of selected {item_type_tooltip}" if edit_enabled else "Select a single item to enable editing")


    def _show_context_menu_for_item_from_scene(self, item, global_pos):
        if not item.isSelected():
            self.scene.clearSelection() 
            item.setSelected(True)

        menu = QMenu()
        edit_action = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        
        if isinstance(item, GraphicsStateItem) and item.is_superstate:
            pass # Could add "Edit Sub-Machine" here if needed, but double-click also works

        delete_action = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")

        action = menu.exec_(global_pos)
        if action == edit_action:
            self.scene.edit_item_properties(item) 
        elif action == delete_action:
            self.scene.delete_selected_items() 


    def _on_edit_selected_item_properties_from_dock(self):
        selected = self.scene.selectedItems()
        if len(selected) == 1:
            self.scene.edit_item_properties(selected[0])

    def _update_window_title(self):
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        
        ide_dock_title = "Standalone Code IDE"
        ide_simple_status_for_main_title = ""
        if hasattr(self, 'ide_dock'): # Check if ide_dock exists
            current_ide_lang_text = self.ide_language_combo.currentText() if hasattr(self, 'ide_language_combo') else ""
            lang_info = f" ({current_ide_lang_text})" if current_ide_lang_text else ""
            
            if self.current_ide_file_path:
                ide_fn = os.path.basename(self.current_ide_file_path)
                ide_dock_title = f"IDE: {ide_fn}{'*' if self.ide_editor_is_dirty else ''}{lang_info}"
                ide_simple_status_for_main_title = f"IDE: {ide_fn}{'*' if self.ide_editor_is_dirty else ''}"
            elif self.ide_code_editor and self.ide_code_editor.toPlainText().strip():
                 ide_dock_title = f"IDE: Untitled Script{'*' if self.ide_editor_is_dirty else ''}{lang_info}"
                 ide_simple_status_for_main_title = f"IDE: Untitled Script{'*' if self.ide_editor_is_dirty else ''}"
            else:
                 ide_dock_title = f"Standalone Code IDE{lang_info}"
            self.ide_dock.setWindowTitle(ide_dock_title)

        sim_status_suffix = " [PySim Running]" if self.py_sim_active else ""
        
        # Consider both scene and IDE dirty status for the main window modified state
        main_window_is_dirty = self.scene.is_dirty() or self.ide_editor_is_dirty 
        self.setWindowModified(main_window_is_dirty) # Let Qt handle '*' based on this
        modified_indicator = "[*]" if main_window_is_dirty else "" # For manual title construction if needed
        
        title_parts = [f"{APP_NAME} - {file_name}"]
        if sim_status_suffix: title_parts.append(sim_status_suffix)
        # The self.setWindowModified(bool) should handle the asterisk automatically for the OS.
        # If you want it in the title bar text explicitly:
        # if main_window_is_dirty: title_parts.append("[*]") # Or just rely on OS
        
        title = " ".join(p for p in title_parts if p).strip()
        self.setWindowTitle(title)

        # Update status bar text
        if hasattr(self, 'status_label'):
            main_file_status = f"File: {file_name}{' *' if self.scene.is_dirty() else ''}" # Scene specific dirty
            pysim_status = f"PySim: {'Active' if self.py_sim_active else 'Idle'}"
            
            ide_status_for_bar = ide_simple_status_for_main_title # Already has its own dirty indicator
            
            full_status_text_parts = [main_file_status, pysim_status]
            if ide_status_for_bar: full_status_text_parts.append(ide_status_for_bar)
            self.status_label.setText(" | ".join(p for p in full_status_text_parts if p))


    def _update_save_actions_enable_state(self):
        self.save_action.setEnabled(self.scene.is_dirty()) 

    def _update_ide_save_actions_enable_state(self):
        if hasattr(self, 'ide_save_file_action'):
            self.ide_save_file_action.setEnabled(self.ide_editor_is_dirty)
        if hasattr(self, 'ide_save_as_file_action'): # Save As should be enabled if there's text
             self.ide_save_as_file_action.setEnabled(self.ide_code_editor is not None and bool(self.ide_code_editor.toPlainText()))

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

        if "Initializing" not in message or (connected and "Initializing" in message): # Avoid logging initial "Initializing"
            logging.info("MATLAB Connection Status: %s", message)

        self._update_matlab_actions_enabled_state()


    def _update_matlab_actions_enabled_state(self):
        can_run_matlab_ops = self.matlab_connection.connected and not self.py_sim_active

        if hasattr(self, 'export_simulink_action'): self.export_simulink_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'run_simulation_action'): self.run_simulation_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'generate_code_action'): self.generate_code_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'matlab_settings_action'): self.matlab_settings_action.setEnabled(not self.py_sim_active) # Settings always enabled unless sim active

    def _start_matlab_operation(self, operation_name):
        logging.info("MATLAB Operation: '%s' starting...", operation_name)
        if hasattr(self, 'status_label'): self.status_label.setText(f"Running MATLAB: {operation_name}...")
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False)

    def _finish_matlab_operation(self):
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(False)
        if hasattr(self, 'status_label'): self.status_label.setText("Ready") # Reset general status
        self.set_ui_enabled_for_matlab_op(True)
        logging.info("MATLAB Operation: Finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        if hasattr(self, 'menuBar'): self.menuBar().setEnabled(enabled)
        for child in self.findChildren(QToolBar):
            child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)

        # Enable/disable all dock widgets carefully
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock", "IDEDock", "ProblemsDock"]:
            dock = self.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(enabled)
        # Re-evaluate Python sim actions as they depend on py_sim_active AND this global enable state
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

        if reply == QMessageBox.Save:
            return self.on_save_file()
        elif reply == QMessageBox.Cancel:
            return False
        return True


    def on_new_file(self, silent=False):
        if not silent:
            if not self._prompt_save_if_dirty(): return False
            if not self._prompt_ide_save_if_dirty():
                 return False


        if self.py_sim_ui_manager:
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        self.scene.clear() # This should also clear any selection
        self.scene.setSceneRect(0,0,6000,4500)
        self.current_file_path = None
        self.last_generated_model_path = None
        self.undo_stack.clear()
        self.scene.set_dirty(False) # Scene is now clean
        self.setWindowModified(self.ide_editor_is_dirty) # Window modified if IDE is dirty
        self._update_window_title()
        self._update_undo_redo_actions_enable_state()
        self._update_save_actions_enable_state()
        if not silent:
            logging.info("New diagram created.")
            if hasattr(self, 'status_label'): self.status_label.setText("New diagram. Ready.")
        self.view.resetTransform()
        self.view.centerOn(self.scene.sceneRect().center())
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger()
        self._refresh_find_dialog_if_visible()
        self.scene.run_all_validations("NewFile") # Validate the empty scene
        return True


    def on_open_file(self):
        if not self._prompt_save_if_dirty(): return
        if not self._prompt_ide_save_if_dirty():
            return

        if self.py_sim_ui_manager:
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)

        if file_path:
            if self._load_from_path(file_path): # _load_from_path should call scene.run_all_validations
                self.current_file_path = file_path
                self.last_generated_model_path = None
                self.undo_stack.clear()
                self.scene.set_dirty(False)
                self.setWindowModified(self.ide_editor_is_dirty) # Window modified if IDE is dirty
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                self._update_save_actions_enable_state()
                logging.info("Opened file: %s", file_path)
                if hasattr(self, 'status_label'): self.status_label.setText(f"Opened: {os.path.basename(file_path)}")
                bounds = self.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else: # Empty diagram loaded, or error in itemsBoundingRect
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())
                self._refresh_find_dialog_if_visible()

            else:
                QMessageBox.critical(self, "Error Opening File", f"Could not load the diagram from:\n{file_path}")
                logging.error("Failed to open file: %s", file_path)

    def _load_from_path(self, file_path):
        try:
            if file_path.startswith(":/"): # Load from Qt resources
                qfile = QFile(file_path)
                if not qfile.open(QIODevice.ReadOnly | QIODevice.Text):
                    logging.error("Failed to open resource file %s: %s", file_path, qfile.errorString())
                    return False
                file_content_bytes = qfile.readAll()
                qfile.close()
                file_content_str = file_content_bytes.data().decode('utf-8')
                data = json.loads(file_content_str)
            else: # Load from filesystem
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data:
                logging.error("Invalid BSM file format: %s. Missing required keys.", file_path)
                return False

            self.scene.clear() # Clear existing scene content before loading
            self.scene.load_diagram_data(data) # This method in DiagramScene should call run_all_validations

            # Connect signals for newly loaded state items
            for item in self.scene.items():
                if isinstance(item, GraphicsStateItem):
                    self.connect_state_item_signals(item)

            return True
        except json.JSONDecodeError as e:
            logging.error("JSONDecodeError loading %s: %s", file_path, e)
            return False
        except Exception as e:
            logging.error("Unexpected error loading %s: %s", file_path, e, exc_info=True)
            return False

    def on_save_file(self) -> bool:
        if not self.current_file_path:
            return self.on_save_file_as()
        
        if self.scene.is_dirty(): # Only save if there are changes
             return self._save_to_path(self.current_file_path)
        return True # No changes, so consider it "saved"


    def on_save_file_as(self) -> bool:
        default_filename = os.path.basename(self.current_file_path or "untitled" + FILE_EXTENSION)
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()

        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As",
                                                   os.path.join(start_dir, default_filename),
                                                   FILE_FILTER)
        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION): # Ensure correct extension
                file_path += FILE_EXTENSION

            if self._save_to_path(file_path):
                self.current_file_path = file_path # Update current path after successful save as
                # Title and dirty status will be updated by _save_to_path
                return True
        return False

    def _save_to_path(self, file_path) -> bool:
        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving.")
            return False

        save_file = QSaveFile(file_path) # Use QSaveFile for atomic saves
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            error_str = save_file.errorString()
            logging.error("Failed to open QSaveFile for %s: %s", file_path, error_str)
            QMessageBox.critical(self, "Save Error", f"Could not open file for saving:\n{error_str}")
            return False

        try:
            diagram_data = self.scene.get_diagram_data()
            json_data_str = json.dumps(diagram_data, indent=4, ensure_ascii=False)
            bytes_written = save_file.write(json_data_str.encode('utf-8'))

            if bytes_written == -1: # Error during write
                 error_str = save_file.errorString()
                 logging.error("Error writing to QSaveFile %s: %s", file_path, error_str)
                 QMessageBox.critical(self, "Save Error", f"Could not write data to file:\n{error_str}")
                 save_file.cancelWriting()
                 return False

            if not save_file.commit(): # Finalize writing to the actual file
                error_str = save_file.errorString()
                logging.error("Failed to commit QSaveFile for %s: %s", file_path, error_str)
                QMessageBox.critical(self, "Save Error", f"Could not finalize saving file:\n{error_str}")
                return False

            logging.info("Successfully saved diagram to: %s", file_path)
            if hasattr(self, 'status_label'): self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            self.scene.set_dirty(False) # Scene is now clean
            self.setWindowModified(self.ide_editor_is_dirty) # Window modified only if IDE is dirty
            self._update_window_title()
            self._update_save_actions_enable_state() # Update save action enabled state
            return True
        except Exception as e:
            logging.error("Unexpected error during save to %s: %s", file_path, e, exc_info=True)
            QMessageBox.critical(self, "Save Error", f"An unexpected error occurred during saving:\n{e}")
            save_file.cancelWriting()
            return False

    def on_select_all(self):
        self.scene.select_all()

    def on_delete_selected(self):
        self.scene.delete_selected_items() # This will trigger validation via RemoveItemsCommand


    def on_export_simulink(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "Please configure MATLAB path in Settings first.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before exporting to Simulink.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Export to Simulink")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp, "->M"))
        layout = QFormLayout(dialog)
        layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)

        base_name = os.path.splitext(os.path.basename(self.current_file_path or "BSM_Model"))[0]
        default_model_name = "".join(c if c.isalnum() or c=='_' else '_' for c in base_name)
        if not default_model_name or not default_model_name[0].isalpha():
            default_model_name = "Mdl_" + default_model_name if default_model_name else "Mdl_MyStateMachine"
        default_model_name = default_model_name.replace('-','_')

        name_edit = QLineEdit(default_model_name)
        layout.addRow("Simulink Model Name:", name_edit)

        default_output_dir = os.path.dirname(self.current_file_path or QDir.homePath())
        output_dir_edit = QLineEdit(default_output_dir)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw")," Browse..."); browse_btn.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(output_dir_edit, 1); dir_layout.addWidget(browse_btn)
        layout.addRow("Output Directory:", dir_layout)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        dialog.setMinimumWidth(450)

        if dialog.exec() == QDialog.Accepted:
            model_name = name_edit.text().strip()
            output_dir = output_dir_edit.text().strip()
            if not model_name or not output_dir:
                QMessageBox.warning(self, "Input Error", "Model name and output directory are required.")
                return
            if not model_name[0].isalpha() or not all(c.isalnum() or c=='_' for c in model_name):
                QMessageBox.warning(self, "Invalid Model Name", "Simulink model name must start with a letter and contain only alphanumeric characters or underscores.")
                return
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create output directory:\n{e}")
                return

            diagram_data = self.scene.get_diagram_data()
            if not diagram_data['states']:
                QMessageBox.information(self, "Empty Diagram", "Cannot export an empty diagram (no states defined).")
                return

            self._start_matlab_operation(f"Exporting '{model_name}' to Simulink")
            self.matlab_connection.generate_simulink_model(diagram_data['states'], diagram_data['transitions'], output_dir, model_name)


    def on_run_simulation(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "Please configure MATLAB path in Settings.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before running a MATLAB simulation.")
            return

        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model to Simulate", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path
        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Enter simulation stop time (seconds):", 10.0, 0.001, 86400.0, 3)
        if not ok: return

        self._start_matlab_operation(f"Running Simulink simulation for '{os.path.basename(model_path)}'")
        self.matlab_connection.run_simulation(model_path, sim_time)

    def on_generate_code(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "Please configure MATLAB path in Settings.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before generating code.")
            return

        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model for Code Generation", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path

        dialog = QDialog(self); dialog.setWindowTitle("Code Generation Options"); dialog.setWindowIcon(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"))
        layout = QFormLayout(dialog); layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)
        lang_combo = QComboBox(); lang_combo.addItems(["C", "C++"]); lang_combo.setCurrentText("C++")
        layout.addRow("Target Language:", lang_combo)

        output_dir_edit = QLineEdit(os.path.dirname(model_path))
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw")," Browse..."); browse_btn.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Base Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(output_dir_edit, 1); dir_layout.addWidget(browse_btn)
        layout.addRow("Base Output Directory:", dir_layout)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject); layout.addRow(btns)
        dialog.setMinimumWidth(450)

        if dialog.exec() == QDialog.Accepted:
            language = lang_combo.currentText()
            output_dir_base = output_dir_edit.text().strip()
            if not output_dir_base:
                QMessageBox.warning(self, "Input Error", "Base output directory is required.")
                return
            try:
                os.makedirs(output_dir_base, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create output directory:\n{e}")
                return

            self._start_matlab_operation(f"Generating {language} code for '{os.path.basename(model_path)}'")
            self.matlab_connection.generate_code(model_path, language, output_dir_base)

    def _get_bundled_file_path(self, filename: str, resource_prefix: str = "") -> str | None:
        if RESOURCES_AVAILABLE:
            actual_resource_path_prefix = f"/{resource_prefix}" if resource_prefix else ""
            resource_path = f":{actual_resource_path_prefix}/{filename}".replace("//", "/")

            if QFile.exists(resource_path):
                logger.debug(f"Found bundled file '{filename}' in Qt Resources at: {resource_path}")
                app_temp_root_dir = QDir(QDir.tempPath())
                app_temp_session_dir_name = f"BSMDesigner_Temp_{QApplication.applicationPid()}"
                if not app_temp_root_dir.exists(app_temp_session_dir_name):
                    app_temp_root_dir.mkpath(app_temp_session_dir_name)

                session_temp_dir = app_temp_root_dir.filePath(app_temp_session_dir_name)
                temp_disk_path = QDir(session_temp_dir).filePath(filename)
                temp_file_info = QFileInfo(temp_disk_path)
                QDir().mkpath(temp_file_info.absolutePath())

                if QFile.exists(temp_disk_path):
                    QFile.remove(temp_disk_path)

                if QFile.copy(resource_path, temp_disk_path):
                    logger.debug(f"Copied resource '{resource_path}' to temporary disk path: {temp_disk_path} for external open.")
                    return temp_disk_path
                else:
                    source_file_for_error = QFile(resource_path)
                    source_file_for_error.open(QIODevice.ReadOnly)
                    logger.warning(f"Failed to copy resource '{resource_path}' to '{temp_disk_path}'. Error: {source_file_for_error.errorString()}")
                    source_file_for_error.close()
            else:
                logger.debug(f"File '{resource_path}' not found in Qt Resources.")

        logger.debug(f"File '{filename}' (prefix: '{resource_prefix}') not found in Qt Resources or copy failed, trying filesystem fallback.")

        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        prefix_to_subdir_map = {
            "examples": "examples", "docs": "docs", "icons": "dependencies/icons"
        }
        search_paths = []
        if resource_prefix and resource_prefix in prefix_to_subdir_map:
            search_paths.append(os.path.join(base_path, prefix_to_subdir_map[resource_prefix], filename))
        search_paths.append(os.path.join(base_path, filename))

        for path_to_check in search_paths:
            if os.path.exists(path_to_check):
                logger.debug(f"Found bundled file '{filename}' via filesystem fallback at: {path_to_check}")
                return path_to_check

        logger.warning(f"Bundled file '{filename}' (prefix: '{resource_prefix}') ultimately not found.")
        return None


    def _open_example_file(self, filename: str):
        if not self._prompt_save_if_dirty():
            return
        if self.py_sim_ui_manager: self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        example_path = self._get_bundled_file_path(filename, resource_prefix="examples")
        if example_path:
            if self._load_from_path(example_path):
                self.current_file_path = f":/examples/{filename}" if example_path.startswith(QDir.tempPath()) and RESOURCES_AVAILABLE else example_path
                self.last_generated_model_path = None
                self.undo_stack.clear()
                self.scene.set_dirty(False)
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                logging.info("Opened example file: %s (from %s)", filename, example_path)
                if hasattr(self, 'status_label'): self.status_label.setText(f"Opened example: {filename}")
                bounds = self.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else:
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())
                self._refresh_find_dialog_if_visible()
            else:
                QMessageBox.critical(self, "Error Opening Example", f"Could not load the example file:\n{filename}\nPath tried: {example_path}")
                logging.error("Failed to open example file: %s from path: %s", filename, example_path)
        else:
            QMessageBox.warning(self, "Example File Not Found", f"The example file '{filename}' could not be found.")
            logging.warning("Example file '%s' not found.", filename)

    def on_show_quick_start(self):
        guide_path = self._get_bundled_file_path("QUICK_START.html", resource_prefix="docs")
        if guide_path:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path)):
                QMessageBox.warning(self, "Could Not Open Guide", f"Failed to open the Quick Start Guide.\nPath: {guide_path}")
                logging.warning("Failed to open Quick Start Guide from: %s", guide_path)
        else:
            QMessageBox.information(self, "Guide Not Found", "The Quick Start Guide (QUICK_START.html) was not found.")


    def on_about(self):
        QMessageBox.about(self, f"About {APP_NAME}",
                          f"""<h3 style='color:{COLOR_ACCENT_PRIMARY};'>{APP_NAME} v{APP_VERSION}</h3>
                             <p>A graphical tool for designing and simulating Brain State Machines.</p>
                             <ul>
                                 <li>Visual FSM design and editing.</li>
                                 <li>Internal Python-based FSM simulation.</li>
                                 <li>MATLAB/Simulink model generation and simulation control.</li>
                                 <li>AI Assistant for FSM generation and chat (requires Google AI API Key for Gemini).</li>
                             </ul>
                             <p style='font-size:8pt;color:{COLOR_TEXT_SECONDARY};'>
                                 This software is intended for research and educational purposes.
                                 Always verify generated models and code.
                             </p>
                          """)

    def closeEvent(self, event: QCloseEvent):
        logger.info("MW_CLOSE: closeEvent received.")
        if not self._prompt_ide_save_if_dirty():
            logger.info("MW_CLOSE: IDE save prompt cancelled close.")
            event.ignore()
            return

        if not self._prompt_save_if_dirty():
            logger.info("MW_CLOSE: Diagram save prompt cancelled close.")
            event.ignore()
            return

        if self.py_sim_ui_manager:
            logger.debug("MW_CLOSE: Stopping Python simulation manager (silent).")
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        if self.internet_check_timer and self.internet_check_timer.isActive():
            self.internet_check_timer.stop()
            logger.debug("MW_CLOSE: Internet check timer stopped.")

        if self.ai_chatbot_manager:
            logger.debug("MW_CLOSE: Stopping AI chatbot manager...")
            self.ai_chatbot_manager.stop_chatbot()
            logger.debug("MW_CLOSE: AI chatbot manager stopped.")

        worker_ref_for_nvml_shutdown = None 

        if self.resource_monitor_thread and self.resource_monitor_thread.isRunning():
            logger.info("MW_CLOSE: Attempting to stop resource monitor worker and thread...")
            if self.resource_monitor_worker:
                worker_ref_for_nvml_shutdown = self.resource_monitor_worker 
                QMetaObject.invokeMethod(self.resource_monitor_worker, "stop_monitoring", Qt.QueuedConnection)
                logger.debug("MW_CLOSE: stop_monitoring invoked on resource worker.")
            
            self.resource_monitor_thread.quit()

            if not self.resource_monitor_thread.wait(3500): 
                logger.warning("MW_CLOSE: Resource monitor thread did not finish gracefully. Terminating.")
                self.resource_monitor_thread.terminate()
                if not self.resource_monitor_thread.wait(500): 
                     logger.error("MW_CLOSE: Resource monitor thread failed to terminate forcefully.")
            else:
                logger.info("MW_CLOSE: Resource monitor thread stopped gracefully.")
        
        if worker_ref_for_nvml_shutdown: 
             logger.info("MW_CLOSE: Shutting down NVML via worker reference.")
             worker_ref_for_nvml_shutdown._shutdown_nvml()
        elif self.resource_monitor_worker: 
            logger.info("MW_CLOSE: Shutting down NVML via direct worker attribute (thread might not have been running/found).")
            self.resource_monitor_worker._shutdown_nvml()
            
        self.resource_monitor_worker = None 
        self.resource_monitor_thread = None
        logger.debug("MW_CLOSE: Resource monitor worker and thread references cleared.")


        if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads:
            logging.info("MW_CLOSE: Closing application. %d MATLAB processes initiated by this session may still be running in the background if not completed.", len(self.matlab_connection._active_threads))

        app_temp_session_dir_name = f"BSMDesigner_Temp_{QApplication.applicationPid()}"
        session_temp_dir_path = QDir(QDir.tempPath()).filePath(app_temp_session_dir_name)
        if QDir(session_temp_dir_path).exists():
            if QDir(session_temp_dir_path).removeRecursively():
                logger.info(f"MW_CLOSE: Cleaned up session temporary directory: {session_temp_dir_path}")
            else:
                logger.warning(f"MW_CLOSE: Failed to clean up session temporary directory: {session_temp_dir_path}")


        logger.info("MW_CLOSE: Application closeEvent accepted.")
        event.accept()


    def _init_internet_status_check(self):
        self.internet_check_timer.timeout.connect(self._run_internet_check_job)
        self.internet_check_timer.start(15000)
        QTimer.singleShot(100, self._run_internet_check_job)

    def _run_internet_check_job(self):
        current_status = False
        status_detail = "Checking..."
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
        if hasattr(self, 'ask_ai_to_generate_fsm_action'):
            self.ask_ai_to_generate_fsm_action.setEnabled(is_online_and_key_present)
        if hasattr(self, 'clear_ai_chat_action'):
            self.clear_ai_chat_action.setEnabled(is_online_and_key_present)

        if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager:
            if self.ai_chat_ui_manager.ai_chat_send_button:
                self.ai_chat_ui_manager.ai_chat_send_button.setEnabled(is_online_and_key_present)
            if self.ai_chat_ui_manager.ai_chat_input:
                self.ai_chat_ui_manager.ai_chat_input.setEnabled(is_online_and_key_present)
                if not is_online_and_key_present:
                    if self.ai_chatbot_manager and not self.ai_chatbot_manager.api_key:
                        self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText("AI disabled: API Key required.")
                    elif not self._internet_connected:
                        self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText("AI disabled: Internet connection required.")
                else:
                    self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText("Type your message to the AI...")

        if hasattr(self, 'ide_analyze_action') and hasattr(self, 'ide_language_combo'):
            current_ide_lang = self.ide_language_combo.currentText()
            can_analyze_ide = (current_ide_lang == "Python" or current_ide_lang.startswith("C/C++")) and is_online_and_key_present
            self.ide_analyze_action.setEnabled(can_analyze_ide)
            tooltip = "Analyze the current code with AI"
            if not (self.ai_chatbot_manager and self.ai_chatbot_manager.api_key and self._internet_connected):
                tooltip += " (Requires Internet & Gemini API Key)"
            elif not (current_ide_lang == "Python" or current_ide_lang.startswith("C/C++")):
                 tooltip += " (Best for Python or C/C++)"
            self.ide_analyze_action.setToolTip(tooltip)

    def _update_internet_status_display(self, is_connected: bool, message_detail: str):
        full_status_text = f"Net: {message_detail}"
        if hasattr(self, 'internet_status_label'):
            self.internet_status_label.setText(full_status_text)
            host_for_tooltip = "8.8.8.8:53 (Google DNS)"
            self.internet_status_label.setToolTip(f"Internet Status: {message_detail} (Checks connection to {host_for_tooltip})")

            text_color = COLOR_ACCENT_SUCCESS if is_connected else COLOR_ACCENT_ERROR
            bg_color = QColor(text_color).lighter(180).name()
            self.internet_status_label.setStyleSheet(f"font-size:{APP_FONT_SIZE_SMALL}; padding:2px 5px; color:{text_color}; background-color:{bg_color}; border-radius:3px;")


        logging.debug("Internet Status Update: %s", message_detail)

        key_present = self.ai_chatbot_manager is not None and bool(self.ai_chatbot_manager.api_key)
        ai_ready = is_connected and key_present

        if hasattr(self.ai_chatbot_manager, 'set_online_status'):
            self.ai_chatbot_manager.set_online_status(is_connected)

        self._update_ai_features_enabled_state(ai_ready)


    def _update_py_sim_status_display(self):
        if hasattr(self, 'py_sim_status_label'):
            if self.py_sim_active and self.py_fsm_engine:
                current_state_name = self.py_fsm_engine.get_current_state_name()
                display_state_name = (current_state_name[:20] + '...') if len(current_state_name) > 23 else current_state_name
                self.py_sim_status_label.setText(f"PySim: Active ({html.escape(display_state_name)})")
                bg_color = QColor(COLOR_PY_SIM_STATE_ACTIVE).lighter(180).name()
                self.py_sim_status_label.setStyleSheet(f"font-weight:bold;padding:2px 5px;color:{COLOR_PY_SIM_STATE_ACTIVE.name()}; background-color:{bg_color}; border-radius:3px;")
                self.py_sim_status_label.setToolTip(f"Python FSM Simulation Active: {current_state_name}")

            else:
                self.py_sim_status_label.setText("PySim: Idle")
                self.py_sim_status_label.setStyleSheet(f"font-weight:normal;padding:2px 5px; color:{COLOR_TEXT_SECONDARY}; background-color:{COLOR_BACKGROUND_MEDIUM}; border-radius:3px;")
                self.py_sim_status_label.setToolTip("Internal Python FSM Simulation is Idle.")


    def _update_py_simulation_actions_enabled_state(self):
        is_matlab_op_running = False
        if hasattr(self, 'progress_bar') and self.progress_bar:
            is_matlab_op_running = self.progress_bar.isVisible()

        sim_can_start = not self.py_sim_active and not is_matlab_op_running
        sim_can_be_controlled = self.py_sim_active and not is_matlab_op_running

        if hasattr(self, 'start_py_sim_action'): self.start_py_sim_action.setEnabled(sim_can_start)
        if hasattr(self, 'stop_py_sim_action'): self.stop_py_sim_action.setEnabled(sim_can_be_controlled)
        if hasattr(self, 'reset_py_sim_action'): self.reset_py_sim_action.setEnabled(sim_can_be_controlled)

        if self.py_sim_ui_manager:
            self.py_sim_ui_manager._update_internal_controls_enabled_state()

    @pyqtSlot(bool)
    def on_toggle_snap_to_grid(self, checked):
        self.scene.snap_to_grid_enabled = checked
        logger.info(f"Snap to Grid {'enabled' if checked else 'disabled'}.")

    @pyqtSlot(bool)
    def on_toggle_snap_to_objects(self, checked):
        self.scene.snap_to_objects_enabled = checked
        logger.info(f"Snap to Objects {'enabled' if checked else 'disabled'}.")

    @pyqtSlot(bool)
    def on_toggle_show_snap_guidelines(self, checked):
        if hasattr(self.scene, '_show_dynamic_snap_guidelines'):
            self.scene._show_dynamic_snap_guidelines = checked
            if not checked:
                self.scene._clear_dynamic_guidelines()
            logger.info(f"Dynamic Snap Guidelines {'shown' if checked else 'hidden'}.")


    @pyqtSlot()
    def _update_zoom_to_selection_action_enable_state(self):
        if hasattr(self, 'zoom_to_selection_action'):
            has_selection = bool(self.scene.selectedItems())
            self.zoom_to_selection_action.setEnabled(has_selection)

    @pyqtSlot()
    def on_zoom_to_selection(self):
        if hasattr(self.view, 'zoom_to_selection'):
            self.view.zoom_to_selection()

    @pyqtSlot()
    def on_fit_diagram_in_view(self):
        if hasattr(self.view, 'fit_diagram_in_view'):
            self.view.fit_diagram_in_view()

    @pyqtSlot()
    def _update_align_distribute_actions_enable_state(self):
        selected_count = len(self.scene.selectedItems())

        can_align = selected_count >= 2
        if hasattr(self, 'align_actions'):
            for action in self.align_actions:
                action.setEnabled(can_align)

        can_distribute = selected_count >= 3
        if hasattr(self, 'distribute_actions'):
            for action in self.distribute_actions:
                action.setEnabled(can_distribute)

    @pyqtSlot(str)
    def on_align_items(self, mode: str):
        selected_items = [item for item in self.scene.selectedItems() if isinstance(item, (GraphicsStateItem, GraphicsCommentItem))]
        if len(selected_items) < 2:
            return

        old_positions_map = {item: item.pos() for item in selected_items}
        moved_items_data_for_command = []

        if not selected_items: return

        overall_selection_rect = QRectF()
        first = True
        for item in selected_items:
            if first:
                overall_selection_rect = item.sceneBoundingRect()
                first = False
            else:
                overall_selection_rect = overall_selection_rect.united(item.sceneBoundingRect())


        if mode == "left":
            ref_x = overall_selection_rect.left()
            for item in selected_items:
                item.setPos(ref_x, item.y())
        elif mode == "center_h":
            ref_x_center = overall_selection_rect.center().x()
            for item in selected_items:
                item_br = item.sceneBoundingRect()
                item.setPos(ref_x_center - item_br.width() / 2.0, item.y())
        elif mode == "right":
            ref_x = overall_selection_rect.right()
            for item in selected_items:
                item_br = item.sceneBoundingRect()
                item.setPos(ref_x - item_br.width(), item.y())
        elif mode == "top":
            ref_y = overall_selection_rect.top()
            for item in selected_items:
                item.setPos(item.x(), ref_y)
        elif mode == "middle_v":
            ref_y_middle = overall_selection_rect.center().y()
            for item in selected_items:
                item_br = item.sceneBoundingRect()
                item.setPos(item.x(), ref_y_middle - item_br.height() / 2.0)
        elif mode == "bottom":
            ref_y = overall_selection_rect.bottom()
            for item in selected_items:
                item_br = item.sceneBoundingRect()
                item.setPos(item.x(), ref_y - item_br.height())

        for item in selected_items:
            new_pos = item.pos()
            old_pos = old_positions_map[item]
            if (new_pos - old_pos).manhattanLength() > 0.1:
                moved_items_data_for_command.append((item, old_pos, new_pos))
                if isinstance(item, GraphicsStateItem):
                    self.scene._update_connected_transitions(item)

        if moved_items_data_for_command:
            cmd = MoveItemsCommand(moved_items_data_for_command, f"Align {mode.replace('_', ' ').title()}")
            self.undo_stack.push(cmd) # This will trigger validation via redo()
            self.scene.set_dirty(True) # set_dirty might also be called by command


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

        self.find_item_dialog.search_input.selectAll()
        self.find_item_dialog.search_input.setFocus()

    @pyqtSlot(QGraphicsItem)
    def focus_on_item(self, item_to_focus: QGraphicsItem):
        if item_to_focus and item_to_focus.scene() == self.scene:
            self.scene.clearSelection()
            item_to_focus.setSelected(True)

            item_rect = item_to_focus.sceneBoundingRect()
            padding = 50
            view_rect_with_padding = item_rect.adjusted(-padding, -padding, padding, padding)

            if self.view:
                 self.view.fitInView(view_rect_with_padding, Qt.KeepAspectRatio)

            display_name = "Item"
            if isinstance(item_to_focus, GraphicsStateItem):
                display_name = f"State: {item_to_focus.text_label}"
            elif isinstance(item_to_focus, GraphicsTransitionItem):
                display_name = f"Transition: {item_to_focus._compose_label_string()}"
            elif isinstance(item_to_focus, GraphicsCommentItem):
                display_name = f"Comment: {item_to_focus.toPlainText()[:30]}..."

            self._log_to_parent("INFO", f"Focused on {display_name}")
            # If find dialog is open, and this focus was from it, it often closes itself.
            # If focus is called from elsewhere (e.g. Problems Dock), this is fine.
            if self.find_item_dialog and not self.find_item_dialog.isHidden():
                 # Optionally hide it: self.find_item_dialog.hide()
                 pass
        else:
            self._log_to_parent("WARNING", f"Could not find or focus on the provided item: {item_to_focus}")


    @pyqtSlot(str)
    def on_distribute_items(self, mode: str):
        selected_items = [item for item in self.scene.selectedItems() if isinstance(item, (GraphicsStateItem, GraphicsCommentItem))]
        if len(selected_items) < 3:
            return

        old_positions_map = {item: item.pos() for item in selected_items}
        moved_items_data_for_command = []

        if mode == "horizontal":
            selected_items.sort(key=lambda item: item.sceneBoundingRect().left())

            start_x_coord = selected_items[0].sceneBoundingRect().left()
            # Correct the first item's position to its original Y but new sorted X (might be redundant if it didn't move)
            selected_items[0].setPos(start_x_coord, old_positions_map[selected_items[0]].y())

            min_x_overall = selected_items[0].sceneBoundingRect().left()
            max_x_overall_right_edge = selected_items[-1].sceneBoundingRect().right()

            total_width_of_items = sum(item.sceneBoundingRect().width() for item in selected_items)
            actual_span_covered_by_items_edges = max_x_overall_right_edge - min_x_overall

            if len(selected_items) <= 1: spacing = 0
            else: spacing = (actual_span_covered_by_items_edges - total_width_of_items) / (len(selected_items) - 1)

            if spacing < 0: # Overlap, distribute with minimal spacing
                spacing = 10 # Or some other sensible default
                logger.warning("Distribute Horizontal: Items wider than span, distributing with minimal spacing.")

            current_x_edge = selected_items[0].sceneBoundingRect().left() # Start from the leftmost item's left edge
            for i, item in enumerate(selected_items):
                item.setPos(current_x_edge, old_positions_map[item].y()) # Keep original Y
                current_x_edge += item.sceneBoundingRect().width() + spacing # Next item starts after this one + spacing

        elif mode == "vertical":
            selected_items.sort(key=lambda item: item.sceneBoundingRect().top())
            start_y_coord = selected_items[0].sceneBoundingRect().top()
            selected_items[0].setPos(old_positions_map[selected_items[0]].x(), start_y_coord)
            min_y_overall = selected_items[0].sceneBoundingRect().top()
            max_y_overall_bottom_edge = selected_items[-1].sceneBoundingRect().bottom()
            total_height_of_items = sum(item.sceneBoundingRect().height() for item in selected_items)
            actual_span_covered_by_items_edges = max_y_overall_bottom_edge - min_y_overall
            if len(selected_items) <= 1: spacing = 0
            else: spacing = (actual_span_covered_by_items_edges - total_height_of_items) / (len(selected_items) - 1)
            if spacing < 0: spacing = 10; logger.warning("Distribute Vertical: Items taller than span, distributing with minimal spacing.")
            current_y_edge = selected_items[0].sceneBoundingRect().top()
            for i, item in enumerate(selected_items):
                item.setPos(old_positions_map[item].x(), current_y_edge)
                current_y_edge += item.sceneBoundingRect().height() + spacing

        for item in selected_items:
            new_pos = item.pos()
            old_pos = old_positions_map[item]
            if (new_pos - old_pos).manhattanLength() > 0.1:
                moved_items_data_for_command.append((item, old_pos, new_pos))
                if isinstance(item, GraphicsStateItem):
                    self.scene._update_connected_transitions(item)

        if moved_items_data_for_command:
            cmd_text = "Distribute Horizontally" if mode == "horizontal" else "Distribute Vertically"
            cmd = MoveItemsCommand(moved_items_data_for_command, cmd_text)
            self.undo_stack.push(cmd) # Redo will trigger validation
            self.scene.set_dirty(True)

    def _prompt_ide_save_if_dirty(self) -> bool:
        if not self.ide_editor_is_dirty or not self.ide_code_editor:
            return True

        file_desc = os.path.basename(self.current_ide_file_path) if self.current_ide_file_path else "Untitled Script"
        reply = QMessageBox.question(self, "Save IDE Script?",
                                     f"The script '{file_desc}' in the IDE has unsaved changes. Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save)
        if reply == QMessageBox.Save:
            return self.on_ide_save_file()
        elif reply == QMessageBox.Cancel:
            return False
        return True

    def on_ide_new_file(self):
        if not self._prompt_ide_save_if_dirty():
            return
        if self.ide_code_editor:
            self.ide_code_editor.clear()
            self.ide_code_editor.setPlaceholderText("Create a new file or open an existing script...")
        if self.ide_output_console:
            self.ide_output_console.clear()
            self.ide_output_console.setPlaceholderText("Script output will appear here...")
        self.current_ide_file_path = None
        self.ide_editor_is_dirty = False
        self._update_ide_save_actions_enable_state()
        self._update_window_title() 
        logger.info("IDE: New script created.")

    def on_ide_open_file(self):
        if not self._prompt_ide_save_if_dirty():
            return

        start_dir = os.path.dirname(self.current_ide_file_path) if self.current_ide_file_path else QDir.homePath()

        file_path, _ = QFileDialog.getOpenFileName(self, "Open Script File", start_dir,
                                                   "Python Files (*.py);;C/C++ Files (*.c *.cpp *.h *.ino);;Text Files (*.txt);;All Files (*)")
        if file_path and self.ide_code_editor:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.ide_code_editor.setPlainText(f.read())
                self.current_ide_file_path = file_path
                self.ide_editor_is_dirty = False
                self._update_ide_save_actions_enable_state()
                
                if hasattr(self, 'ide_language_combo'):
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext == ".py": self.ide_language_combo.setCurrentText("Python")
                    elif ext in [".ino", ".c", ".cpp", ".h"]: self.ide_language_combo.setCurrentText("C/C++ (Arduino)")
                    else: self.ide_language_combo.setCurrentText("Text")
                else:
                    self._update_window_title() 

                if self.ide_output_console: self.ide_output_console.clear()
                logger.info("IDE: Opened script: %s", file_path)

            except Exception as e:
                QMessageBox.critical(self, "Error Opening Script", f"Could not load script from {file_path}:\n{e}")
                logger.error("IDE: Failed to open script %s: %s", file_path, e)

    def _save_ide_to_path(self, file_path) -> bool:
        if not self.ide_code_editor: return False
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.ide_code_editor.toPlainText())
            self.current_ide_file_path = file_path
            self.ide_editor_is_dirty = False
            self._update_ide_save_actions_enable_state()
            self._update_window_title() 
            logger.info("IDE: Saved script to: %s", file_path)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error Saving Script", f"Could not save script to {file_path}:\n{e}")
            logger.error("IDE: Failed to save script %s: %s", file_path, e)
            return False
        
    def on_ide_save_file(self) -> bool:
        if not self.current_ide_file_path:
            return self.on_ide_save_as_file()
        if self.ide_editor_is_dirty:
             return self._save_ide_to_path(self.current_ide_file_path)
        return True

    def on_ide_save_as_file(self) -> bool:
        default_filename = os.path.basename(self.current_ide_file_path or "untitled_script.py")
        start_dir = os.path.dirname(self.current_ide_file_path) if self.current_ide_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Script As", os.path.join(start_dir, default_filename),
                                                   "Python Files (*.py);;C/C++ Files (*.c *.cpp *.h *.ino);;Text Files (*.txt);;All Files (*)")
        if file_path:
            return self._save_ide_to_path(file_path)
        return False

    @pyqtSlot()
    def _on_ide_text_changed(self):
        if not self.ide_editor_is_dirty:
            self.ide_editor_is_dirty = True
            self._update_ide_save_actions_enable_state()
            self._update_window_title()
            
    @pyqtSlot(str)
    def _on_ide_language_changed(self, language_param: str):
        if self.ide_code_editor:
            self.ide_code_editor.set_language(language_param)

        if self.ide_run_script_action:
            is_python = (language_param == "Python")
            self.ide_run_script_action.setEnabled(is_python)
            self.ide_run_script_action.setToolTip("Run the current Python script in the editor" if is_python else "Run is currently only supported for Python scripts")

        ai_ready = self.ai_chatbot_manager is not None and \
                   self.ai_chatbot_manager.api_key is not None and \
                   self._internet_connected is True

        if self.ide_analyze_action:
            can_analyze = (language_param == "Python" or language_param.startswith("C/C++")) and ai_ready
            self.ide_analyze_action.setEnabled(can_analyze)
            tooltip = "Analyze the current code with AI"
            if not ai_ready:
                tooltip += " (Requires Internet & Gemini API Key)"
            elif not (language_param == "Python" or language_param.startswith("C/C++")):
                 tooltip += " (Best for Python or C/C++)"
            self.ide_analyze_action.setToolTip(tooltip)

        self._update_window_title() 
        logger.info(f"IDE: Language changed to {language_param}.")        

    @pyqtSlot()
    def on_ide_run_python_script(self):
        if not self.ide_code_editor or not self.ide_output_console:
            logger.error("IDE: Code editor or output console not available for running script.")
            return

        if self.ide_language_combo.currentText() != "Python":
            QMessageBox.information(self, "Run Script", "Currently, only Python scripts can be run directly from the IDE.")
            return

        code_to_run = self.ide_code_editor.toPlainText()
        if not code_to_run.strip():
            self.ide_output_console.setHtml("<i>No Python code to run.</i>")
            self.ide_output_console.append(f"<hr style='border-color:{COLOR_BORDER_LIGHT};'><div style='color: {COLOR_TEXT_SECONDARY}; font-size: {APP_FONT_SIZE_SMALL};'><i>Execution finished (no code).</i></div>")
            return

        self.ide_output_console.clear()
        self.ide_output_console.append(f"<div style='color: {COLOR_TEXT_SECONDARY}; font-size: {APP_FONT_SIZE_SMALL};'><i>Running Python script at {QTime.currentTime().toString('hh:mm:ss')}...</i></div><hr style='border-color:{COLOR_BORDER_LIGHT};'>")


        script_globals = {"__name__": "__ide_script__"}
        script_locals = {}

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                exec(code_to_run, script_globals, script_locals)

            std_out_text = stdout_capture.getvalue()
            if std_out_text: self.ide_output_console.append(html.escape(std_out_text))

            err_output = stderr_capture.getvalue()
            if err_output:
                self.ide_output_console.append(f"<pre style='color:{COLOR_ACCENT_ERROR};'>{html.escape(err_output)}</pre>")
            self.ide_output_console.append(f"<hr style='border-color:{COLOR_BORDER_LIGHT};'><div style='color: {COLOR_TEXT_SECONDARY}; font-size: {APP_FONT_SIZE_SMALL};'><i>Execution finished.</i></div>")
        except Exception as e:

            import traceback
            self.ide_output_console.append(f"<pre style='color:{COLOR_ACCENT_ERROR};'><b>Error during execution:</b>\n{html.escape(str(e))}\n--- Traceback ---\n{html.escape(traceback.format_exc())}</pre>")
            self.ide_output_console.append(f"<hr style='border-color:{COLOR_BORDER_LIGHT};'><div style='color: {COLOR_ACCENT_ERROR}; font-size: {APP_FONT_SIZE_SMALL};'><i>Execution failed.</i></div>")
        finally:
            stdout_capture.close()
            stderr_capture.close()
            self.ide_output_console.ensureCursorVisible()

    @pyqtSlot()
    def on_ide_analyze_with_ai(self):
        if not self.ide_code_editor or not self.ide_output_console:
            logger.error("IDE: Code editor or output console not available for AI analysis.")
            return
        if not self.ai_chatbot_manager or not self.ai_chatbot_manager.api_key:
            QMessageBox.warning(self, "AI Assistant Not Ready", "Please configure your Google AI API key in AI Assistant Settings (Gemini) to use this feature.")
            return
        if not self._internet_connected:
            QMessageBox.warning(self, "AI Assistant Offline", "Internet connection is required for AI features.")
            return

        code_to_analyze = self.ide_code_editor.toPlainText()
        if not code_to_analyze.strip():
            self.ide_output_console.setHtml("<i>No code to analyze.</i>")
            return

        selected_language = self.ide_language_combo.currentText()
        language_context = ""
        if "Arduino" in selected_language: language_context = "for Arduino"
        elif "C/C++" in selected_language: language_context = "for generic C/C++"
        elif "Python" in selected_language: language_context = "for Python"

        prompt = f"Please review the following {selected_language} code snippet {language_context}. Check for syntax errors, common programming mistakes, potential bugs, or suggest improvements. Provide feedback and, if there are issues, offer a corrected version or explain the problem:\n\n```\n{code_to_analyze}\n```"

        self.ide_output_console.append(f"<div style='color: {COLOR_TEXT_SECONDARY}; font-size: {APP_FONT_SIZE_SMALL};'><i>Sending code to AI for analysis ({selected_language})... (Response will appear in main AI Chat window)</i></div><hr style='border-color:{COLOR_BORDER_LIGHT};'>")

        if self.ai_chat_ui_manager: 
            self.ai_chat_ui_manager._append_to_chat_display("IDE", f"Requesting AI analysis for the current script ({selected_language}).")
        self.ai_chatbot_manager.send_message(prompt)


    def log_message(self, level_str: str, message: str):
        level = getattr(logging, level_str.upper(), logging.INFO)
        logger.log(level, message)

    

    @pyqtSlot(str)
    def focus_on_state_by_name(self, state_name: str):
        item_to_focus = self.scene.get_state_by_name(state_name)
        if item_to_focus and isinstance(item_to_focus, GraphicsStateItem):
            self.scene.clearSelection()
            item_to_focus.setSelected(True)

            item_rect = item_to_focus.sceneBoundingRect()
            padding = 50
            view_rect_with_padding = item_rect.adjusted(-padding, -padding, padding, padding)

            if self.view:
                 self.view.fitInView(view_rect_with_padding, Qt.KeepAspectRatio)

            self._log_to_parent("INFO", f"Focused on state: {state_name}")
            if self.find_item_dialog and not self.find_item_dialog.isHidden():
                 self.find_item_dialog.hide()
        else:
            self._log_to_parent("WARNING", f"Could not find state '{state_name}' to focus on.")

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
            try:
                state_item.signals.textChangedViaInlineEdit.disconnect(self._handle_state_renamed_inline)
            except TypeError: 
                pass
            state_item.signals.textChangedViaInlineEdit.connect(self._handle_state_renamed_inline)
            logger.debug(f"Connected rename signal for state: {state_item.text_label}")


    @pyqtSlot()
    def _refresh_find_dialog_if_visible(self):
        if self.find_item_dialog and not self.find_item_dialog.isHidden():
            logger.debug("Refreshing FindItemDialog list due to scene change.")
            self.find_item_dialog.refresh_list()


if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    
    app.setStyleSheet(STYLE_SHEET_GLOBAL)
    
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
