# FILE: bsm_designer_project/main.py
# Full content for main.py with all corrections up to this point.

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
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTime, QTimer, QPointF, QMetaObject, QFile, QTemporaryFile, QDir, QIODevice, QFileInfo, QEvent, QSize, QUrl, pyqtSignal, pyqtSlot, QThread, QPoint, QMimeData
# Note: QObject was imported twice in original, removed duplicate
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
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
from code_editor import CodeEditor
from fsm_simulator import FSMSimulator, FSMError
from ai_chatbot import AIChatbotManager
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
    FSM_TEMPLATES_BUILTIN # COLOR_ITEM_STATE_DEFAULT_BORDER is in this list now from config
)
from utils import get_standard_icon

# --- UI Managers ---
from ui_py_simulation_manager import PySimulationUIManager
from ui_ai_chatbot_manager import AIChatUIManager

# --- Logging Setup ---
try:
    from logging_setup import setup_global_logging
except ImportError:
    print("CRITICAL: logging_setup.py not found. Logging will be basic.")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# --- Qt Resource System ---
try:
    import resources_rc
    RESOURCES_AVAILABLE = True
    print("DEBUG: resources_rc.py imported successfully.")
except ImportError:
    RESOURCES_AVAILABLE = False
    print("WARNING: resources_rc.py not found. Icons and bundled files might be missing. Run: pyrcc5 resources.qrc -o resources_rc.py")


logger = logging.getLogger(__name__)

# --- DraggableToolButton Class Definition ---
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

# --- ResourceMonitorWorker Class Definition ---
class ResourceMonitorWorker(QObject):
    resourceUpdate = pyqtSignal(float, float, float, str)
    finished_signal = pyqtSignal()

    def __init__(self, interval_ms=2000, parent=None):
        super().__init__(parent)
        self.interval_ms = interval_ms
        self._monitoring = False
        self._nvml_initialized = False
        self._gpu_handle = None
        self._gpu_name_cache = "N/A"

        if PYNVML_AVAILABLE and pynvml:
            try:
                pynvml.nvmlInit()
                self._nvml_initialized = True
                if pynvml.nvmlDeviceGetCount() > 0:
                    self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    gpu_name_raw = pynvml.nvmlDeviceGetName(self._gpu_handle)
                    if isinstance(gpu_name_raw, bytes):
                        self._gpu_name_cache = gpu_name_raw.decode('utf-8')
                    elif isinstance(gpu_name_raw, str):
                        self._gpu_name_cache = gpu_name_raw
                    else:
                        logger.warning(f"NVML: Unexpected type for GPU name: {type(gpu_name_raw)}")
                        self._gpu_name_cache = "NVIDIA GPU Name TypeErr"
                else:
                    self._gpu_name_cache = "NVIDIA GPU N/A"
            except pynvml.NVMLError as e_nvml:
                logger.warning(f"Could not initialize NVML (for NVIDIA GPU monitoring): {e_nvml}")
                self._nvml_initialized = False
                error_code_str = f" (Code: {e_nvml.value})" if hasattr(e_nvml, 'value') else ""
                self._gpu_name_cache = f"NVIDIA NVML Err ({type(e_nvml).__name__}{error_code_str})"
            except AttributeError as e_attr:
                 logger.warning(f"NVML: Attribute error during init (possibly on .decode for name): {e_attr}")
                 self._nvml_initialized = False
                 self._gpu_name_cache = "NVML Attr Err"
            except Exception as e:
                logger.warning(f"Unexpected error during NVML init: {e}", exc_info=True)
                self._nvml_initialized = False
                self._gpu_name_cache = "NVML Init Error"
        elif not PYNVML_AVAILABLE:
            self._gpu_name_cache = "N/A (pynvml N/A)"

    @pyqtSlot()
    def start_monitoring(self):
        logger.info("ResourceMonitorWorker: start_monitoring called.")
        self._monitoring = True
        self._monitor_resources()

    @pyqtSlot()
    def stop_monitoring(self):
        logger.info("ResourceMonitorWorker: stop_monitoring called.")
        self._monitoring = False
        if self._nvml_initialized and PYNVML_AVAILABLE and pynvml:
            try:
                pynvml.nvmlShutdown()
                logger.info("ResourceMonitorWorker: NVML shutdown.")
            except Exception as e:
                logger.warning(f"Error shutting down NVML: {e}")
        self._nvml_initialized = False
        self._gpu_handle = None


    def _monitor_resources(self):
        logger.debug("Resource monitor worker loop started.")
        short_sleep_ms = 100

        while self._monitoring:

            if PYNVML_AVAILABLE and pynvml and not self._nvml_initialized :
                try:
                    pynvml.nvmlInit()
                    self._nvml_initialized = True
                    logger.info("NVML re-initialized successfully in worker loop.")
                except pynvml.NVMLError as e_reinit:
                    logger.warning(f"NVML: Failed to re-initialize in worker loop: {e_reinit}")
                    self._nvml_initialized = False
                    error_code_str = f" (Code: {e_reinit.value})" if hasattr(e_reinit, 'value') else ""
                    self._gpu_name_cache = f"NVIDIA NVML ReinitErr ({type(e_reinit).__name__}{error_code_str})"

            if PYNVML_AVAILABLE and pynvml and self._nvml_initialized and not self._gpu_handle:
                try:
                    if pynvml.nvmlDeviceGetCount() > 0:
                        self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                        gpu_name_raw = pynvml.nvmlDeviceGetName(self._gpu_handle)
                        if isinstance(gpu_name_raw, bytes): self._gpu_name_cache = gpu_name_raw.decode('utf-8')
                        elif isinstance(gpu_name_raw, str): self._gpu_name_cache = gpu_name_raw
                        else: self._gpu_name_cache = "NVIDIA GPU Name TypeErr (Poll)"
                        logger.info(f"NVML: GPU handle acquired for {self._gpu_name_cache} in worker loop.")
                    else:
                        self._gpu_name_cache = "NVIDIA GPU N/A"
                except pynvml.NVMLError as e_nvml_poll:
                    logger.debug(f"NVML: Error getting GPU handle during poll: {e_nvml_poll}")
                    error_code_str = f" (Code: {e_nvml_poll.value})" if hasattr(e_nvml_poll, 'value') else ""
                    self._gpu_name_cache = f"NVIDIA Poll Err ({type(e_nvml_poll).__name__}{error_code_str})"
                    self._gpu_handle = None
                    if hasattr(pynvml, 'NVML_ERROR_UNINITIALIZED') and e_nvml_poll.value == pynvml.NVML_ERROR_UNINITIALIZED: self._nvml_initialized = False
                except AttributeError as e_attr:
                     logger.warning(f"NVML: Attribute error getting GPU handle (possibly on .decode for name): {e_attr}")
                     self._gpu_name_cache = "NVML Handle Attr Err"
                     self._gpu_handle = None
                except Exception as e_poll:
                    logger.debug(f"NVML: Unexpected error getting GPU handle during poll: {e_poll}")
                    self._gpu_name_cache = "NVML Poll Error"
                    self._gpu_handle = None

            try:
                cpu_usage = psutil.cpu_percent(interval=None)
                ram_percent = psutil.virtual_memory().percent
                gpu_util, gpu_name_to_emit = -1.0, self._gpu_name_cache

                if self._nvml_initialized and self._gpu_handle and PYNVML_AVAILABLE and pynvml:
                    try: gpu_util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle).gpu
                    except pynvml.NVMLError as e_nvml_util:
                        logger.debug(f"NVML: Error getting GPU utilization: {e_nvml_util}")
                        gpu_util = -2.0
                        error_code_str = f" (Code: {e_nvml_util.value})" if hasattr(e_nvml_util, 'value') else ""
                        gpu_name_to_emit = f"NVIDIA Util Err ({type(e_nvml_util).__name__}{error_code_str})"
                        if hasattr(pynvml, 'NVML_ERROR_GPU_IS_LOST') and hasattr(pynvml, 'NVML_ERROR_INVALID_ARGUMENT') and hasattr(pynvml, 'NVML_ERROR_UNINITIALIZED') and \
                           e_nvml_util.value in (pynvml.NVML_ERROR_GPU_IS_LOST,
                                                 pynvml.NVML_ERROR_INVALID_ARGUMENT,
                                                 pynvml.NVML_ERROR_UNINITIALIZED):
                            self._gpu_handle = None
                            if e_nvml_util.value == pynvml.NVML_ERROR_UNINITIALIZED:
                                self._nvml_initialized = False
                            logger.warning(f"NVML: GPU handle lost or error {e_nvml_util.value}. Will attempt re-init/re-acquire.")
                    except Exception as e_util_other:
                        logger.debug(f"NVML: Unexpected error getting GPU utilization: {e_util_other}")
                        gpu_util = -2.0; gpu_name_to_emit = "NVML Util Error"

                if self._monitoring:
                    self.resourceUpdate.emit(cpu_usage, ram_percent, gpu_util, gpu_name_to_emit)

            except psutil.Error as e_psutil:
                 logger.error(f"psutil error in resource monitoring: {e_psutil}", exc_info=False)
                 if self._monitoring: self.resourceUpdate.emit(-1.0, -1.0, -3.0, f"PSUtil Error: {str(e_psutil)[:20]}")
            except Exception as e:
                logger.error(f"Error in resource monitoring data collection: {e}", exc_info=True)
                if self._monitoring:
                    self.resourceUpdate.emit(-1.0, -1.0, -3.0, f"Monitor Error: {str(e)[:20]}")

            for _ in range(self.interval_ms // short_sleep_ms):
                if not self._monitoring:
                    break
                QThread.msleep(short_sleep_ms)
            if not self._monitoring:
                break

        logger.debug("Resource monitor worker loop finished.")
        self.finished_signal.emit()


# MainWindow Class
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

        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False

        self.ide_code_editor: CodeEditor | None = None
        self.current_ide_file_path: str | None = None
        self.ide_output_console: QTextEdit | None = None
        self.ide_run_script_action: QAction | None = None
        self.ide_analyze_action: QAction | None = None
        self.ide_editor_is_dirty = False

        self.find_item_dialog: FindItemDialog | None = None

        self.init_ui() # This creates self.view, self.log_output, and other UI elements
        # The view signal connection MUST happen AFTER self.view is created by init_ui()
        if hasattr(self, 'view') and self.view:
            self.view.zoomChanged.connect(self.update_zoom_status_display)
        
        self.py_sim_ui_manager = PySimulationUIManager(self)
        self.ai_chat_ui_manager = AIChatUIManager(self)

        self._populate_dynamic_docks() # This uses docks created in init_ui


        self.py_sim_ui_manager.simulationStateChanged.connect(self._handle_py_sim_state_changed_by_manager)
        self.py_sim_ui_manager.requestGlobalUIEnable.connect(self._handle_py_sim_global_ui_enable_by_manager)

        self._internet_connected: bool | None = None
        self.internet_check_timer = QTimer(self)

        self.resource_monitor_worker: ResourceMonitorWorker | None = None
        self.resource_monitor_thread: QThread | None = None

        try:
            setup_global_logging(self.log_output) # self.log_output should exist now
            logger.info("Main window initialized and logging configured.")
        except Exception as e:
            print(f"ERROR: Failed to run setup_global_logging: {e}. UI logs might not work.")
            if not logging.getLogger().hasHandlers():
                 logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

        self._init_resource_monitor()

        self.matlab_status_label.setObjectName("MatlabStatusLabel")
        self.py_sim_status_label.setObjectName("PySimStatusLabel")
        self.internet_status_label.setObjectName("InternetStatusLabel")
        self.status_label.setObjectName("StatusLabel")
        self.cpu_status_label.setObjectName("CpuStatusLabel")
        self.ram_status_label.setObjectName("RamStatusLabel")
        self.gpu_status_label.setObjectName("GpuStatusLabel")
        self.zoom_status_label.setObjectName("ZoomStatusLabel")


        self._update_matlab_status_display(False, "Initializing. Configure MATLAB settings or attempt auto-detect.")
        self._update_py_sim_status_display()

        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)

        self._update_window_title()
        self.on_new_file(silent=True)
        self._init_internet_status_check()
        self._update_properties_dock()
        self._update_py_simulation_actions_enabled_state()
        self._update_zoom_to_selection_action_enable_state()
        self._update_align_distribute_actions_enable_state()
        
        if hasattr(self, 'view') and self.view: # Check if view exists for initial zoom update
            self.update_zoom_status_display(self.view.transform().m11())


        if self.ai_chat_ui_manager:
            if not self.ai_chatbot_manager.api_key:
                self.ai_chat_ui_manager.update_status_display("Status: API Key required. Configure in Settings.")
            elif self._internet_connected is None:
                self.ai_chat_ui_manager.update_status_display("Status: Checking connectivity...")
            elif self._internet_connected :
                self.ai_chat_ui_manager.update_status_display("Status: Ready.")
            else:
                self.ai_chat_ui_manager.update_status_display("Status: Offline. AI features unavailable.")
        else:
            logger.warning("MainWindow: ai_chat_ui_manager not initialized when trying to set initial status.")


    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050)
        self._create_central_widget()
        self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM"))
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_docks() 
        self._create_status_bar()
        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger()
        # Moved zoomChanged connection to after self.view is guaranteed to exist

    def _populate_dynamic_docks(self):
        if self.py_sim_ui_manager and self.py_sim_dock:
            py_sim_contents_widget = self.py_sim_ui_manager.create_dock_widget_contents()
            self.py_sim_dock.setWidget(py_sim_contents_widget)
        else:
            logger.error("Could not populate Python Simulation Dock: manager or dock missing.")

        if self.ai_chat_ui_manager and self.ai_chatbot_dock:
            ai_chat_contents_widget = self.ai_chat_ui_manager.create_dock_widget_contents()
            self.ai_chatbot_dock.setWidget(ai_chat_contents_widget)
        else:
            logger.error("Could not populate AI Chatbot Dock: manager or dock missing.")

        self.tabifyDockWidget(self.properties_dock, self.ai_chatbot_dock)
        self.tabifyDockWidget(self.ai_chatbot_dock, self.py_sim_dock)
        if hasattr(self, 'ide_dock'):
            self.tabifyDockWidget(self.py_sim_dock, self.ide_dock)


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
        if hasattr(self, 'scene'):
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

        self.find_item_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "Find"), "&Find Item...", self, shortcut=QKeySequence.Find, statusTip="Find an FSM element by text", triggered=self.on_show_find_item_dialog)

        logger.debug(f"MW: AI actions created. Settings: {self.openai_settings_action}, Clear: {self.clear_ai_chat_action}, Generate: {self.ask_ai_to_generate_fsm_action}")


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
        edit_menu.addAction(self.find_item_action)
        edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Mode"),"Interaction Mode")
        mode_menu.addAction(self.select_mode_action)
        mode_menu.addAction(self.add_state_mode_action)
        mode_menu.addAction(self.add_transition_mode_action)
        mode_menu.addAction(self.add_comment_mode_action)
        edit_menu.addSeparator()
        align_distribute_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogDetailedView, "AD"), "Align & Distribute")
        align_menu = align_distribute_menu.addMenu("Align")
        align_menu.addAction(self.align_left_action); align_menu.addAction(self.align_center_h_action); align_menu.addAction(self.align_right_action)
        align_menu.addSeparator()
        align_menu.addAction(self.align_top_action); align_menu.addAction(self.align_middle_v_action); align_menu.addAction(self.align_bottom_action)
        distribute_menu = align_distribute_menu.addMenu("Distribute")
        distribute_menu.addAction(self.distribute_h_action); distribute_menu.addAction(self.distribute_v_action)


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
        self.view_menu.addAction(self.zoom_in_action)
        self.view_menu.addAction(self.zoom_out_action)
        self.view_menu.addAction(self.reset_zoom_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.zoom_to_selection_action)
        self.view_menu.addAction(self.fit_diagram_action)
        self.view_menu.addSeparator()
        snap_menu = self.view_menu.addMenu("Snapping")
        snap_menu.addAction(self.snap_to_grid_action)
        snap_menu.addAction(self.snap_to_objects_action)
        self.show_snap_guidelines_action = QAction("Show Dynamic Snap Guidelines", self, checkable=True, statusTip="Show/hide dynamic alignment guidelines during drag")
        if hasattr(self, 'scene') and hasattr(self.scene, '_show_dynamic_snap_guidelines'):
            self.show_snap_guidelines_action.setChecked(self.scene._show_dynamic_snap_guidelines)
        else:
            self.show_snap_guidelines_action.setChecked(True)
        self.show_snap_guidelines_action.triggered.connect(self.on_toggle_show_snap_guidelines)
        snap_menu.addAction(self.show_snap_guidelines_action)
        self.view_menu.addSeparator()
        # Dock visibility actions will be added to view_menu in _create_docks

        tools_menu = menu_bar.addMenu("&Tools")
        ide_menu = tools_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogDetailedView, "IDE"), "Standalone Code IDE")
        ide_menu.addAction(self.ide_new_file_action)
        ide_menu.addAction(self.ide_open_file_action)
        ide_menu.addAction(self.ide_save_file_action)
        ide_menu.addAction(self.ide_save_as_file_action)
        ide_menu.addSeparator()
        ide_menu.addAction(self.ide_run_script_action)
        ide_menu.addAction(self.ide_analyze_action)

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
        tb_style = Qt.ToolButtonIconOnly

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
        edit_toolbar.addAction(self.find_item_action)

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

        view_toolbar = self.addToolBar("View Tools")
        view_toolbar.setObjectName("ViewToolBar")
        view_toolbar.setIconSize(icon_size)
        view_toolbar.setToolButtonStyle(tb_style)
        view_toolbar.addAction(self.zoom_in_action)
        view_toolbar.addAction(self.zoom_out_action)
        view_toolbar.addAction(self.reset_zoom_action)
        view_toolbar.addSeparator()
        view_toolbar.addAction(self.zoom_to_selection_action)
        view_toolbar.addAction(self.fit_diagram_action)

        align_toolbar = self.addToolBar("Alignment & Distribution")
        align_toolbar.setObjectName("AlignDistributeToolBar")
        align_toolbar.setIconSize(icon_size)
        align_toolbar.setToolButtonStyle(tb_style)
        align_toolbar.addAction(self.align_left_action); align_toolbar.addAction(self.align_center_h_action); align_toolbar.addAction(self.align_right_action)
        align_toolbar.addSeparator()
        align_toolbar.addAction(self.align_top_action); align_toolbar.addAction(self.align_middle_v_action); align_toolbar.addAction(self.align_bottom_action)
        align_toolbar.addSeparator()
        align_toolbar.addAction(self.distribute_h_action); align_toolbar.addAction(self.distribute_v_action)


    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)

        # --- Tools Dock (Visible by default) ---
        self.tools_dock = QDockWidget("Elements & Modes", self)
        self.tools_dock.setObjectName("ToolsDock")
        tools_widget_main = QWidget(); tools_widget_main.setObjectName("ToolsDockWidgetContents")
        tools_main_layout = QVBoxLayout(tools_widget_main); tools_main_layout.setSpacing(8); tools_main_layout.setContentsMargins(8,8,8,8)
        mode_group_box = QGroupBox("Interaction Mode"); mode_layout = QVBoxLayout(); mode_layout.setSpacing(6)
        self.toolbox_select_button = QToolButton(); self.toolbox_select_button.setDefaultAction(self.select_mode_action)
        self.toolbox_add_state_button = QToolButton(); self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action)
        self.toolbox_transition_button = QToolButton(); self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action)
        self.toolbox_add_comment_button = QToolButton(); self.toolbox_add_comment_button.setDefaultAction(self.add_comment_mode_action)
        for btn in [self.toolbox_select_button, self.toolbox_add_state_button, self.toolbox_transition_button, self.toolbox_add_comment_button]:
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(20,20)); mode_layout.addWidget(btn)
        mode_group_box.setLayout(mode_layout); tools_main_layout.addWidget(mode_group_box)

        draggable_group_box = QGroupBox("Drag New Elements"); draggable_layout = QVBoxLayout(); draggable_layout.setSpacing(6)
        drag_state_btn = DraggableToolButton("State", "application/x-bsm-tool", "State"); drag_state_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))
        drag_initial_state_btn = DraggableToolButton("Initial State", "application/x-bsm-tool", "Initial State"); drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt"))
        drag_final_state_btn = DraggableToolButton("Final State", "application/x-bsm-tool", "Final State"); drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt"))
        drag_comment_btn = DraggableToolButton("Comment", "application/x-bsm-tool", "Comment"); drag_comment_btn.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))
        for btn in [drag_state_btn, drag_initial_state_btn, drag_final_state_btn, drag_comment_btn]: draggable_layout.addWidget(btn)
        draggable_group_box.setLayout(draggable_layout); tools_main_layout.addWidget(draggable_group_box)

        self.templates_group_box = QGroupBox("FSM Templates")
        templates_layout = QVBoxLayout()
        templates_layout.setSpacing(6)
        self.template_buttons_container = QWidget()
        self.template_buttons_layout = QVBoxLayout(self.template_buttons_container)
        self.template_buttons_layout.setContentsMargins(0,0,0,0)
        self.template_buttons_layout.setSpacing(4)
        templates_layout.addWidget(self.template_buttons_container)
        templates_layout.addStretch()
        self.templates_group_box.setLayout(templates_layout)
        tools_main_layout.addWidget(self.templates_group_box)

        tools_main_layout.addStretch(); self.tools_dock.setWidget(tools_widget_main)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock)

        # --- Properties Dock (Visible by default) ---
        self.properties_dock = QDockWidget("Item Properties", self); self.properties_dock.setObjectName("PropertiesDock")
        properties_widget = QWidget(); properties_layout = QVBoxLayout(properties_widget); properties_layout.setContentsMargins(8,8,8,8); properties_layout.setSpacing(6)
        self.properties_editor_label = QLabel("<i>Select an item to view its properties.</i>"); self.properties_editor_label.setObjectName("PropertiesLabel")
        self.properties_editor_label.setWordWrap(True); self.properties_editor_label.setTextFormat(Qt.RichText); self.properties_editor_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        properties_layout.addWidget(self.properties_editor_label, 1)
        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"),"Edit Properties...") ; self.properties_edit_button.setEnabled(False)
        self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock); properties_layout.addWidget(self.properties_edit_button)
        self.properties_dock.setWidget(properties_widget); self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)

        # --- Log Dock (Hidden by default) ---
        self.log_dock = QDockWidget("Application Log", self); self.log_dock.setObjectName("LogDock")
        log_widget = QWidget(); log_layout = QVBoxLayout(log_widget); log_layout.setContentsMargins(0,0,0,0)
        self.log_output = QTextEdit(); self.log_output.setObjectName("LogOutputWidget"); self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output); self.log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.log_dock.setVisible(False) # <<<< MODIFIED: Hidden by default

        # --- Python Simulation Dock (Hidden by default) ---
        self.py_sim_dock = QDockWidget("Python Simulation", self); self.py_sim_dock.setObjectName("PySimDock")
        self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock)
        self.py_sim_dock.setVisible(False) # <<<< MODIFIED: Hidden by default

        # --- AI Chatbot Dock (Hidden by default) ---
        self.ai_chatbot_dock = QDockWidget("AI Assistant", self); self.ai_chatbot_dock.setObjectName("AIChatbotDock")
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock)
        self.ai_chatbot_dock.setVisible(False) # <<<< MODIFIED: Hidden by default

        # --- IDE Dock (Hidden by default) ---
        self._setup_ide_dock_widget() # _setup_ide_dock_widget already calls addDockWidget
        if hasattr(self, 'ide_dock'):
            self.ide_dock.setVisible(False) # <<<< MODIFIED: Hidden by default

        # --- Tabify Docks ---
        # Properties will be the primary tab in its group
        self.tabifyDockWidget(self.properties_dock, self.ai_chatbot_dock)
        # If PySimDock is shown, it will be tabbed with AI Chatbot (or properties if AI chat is also hidden)
        self.tabifyDockWidget(self.ai_chatbot_dock, self.py_sim_dock)
        if hasattr(self, 'ide_dock'):
             # If IDE Dock is shown, it will be tabbed with PySim (or the one before it if PySim is hidden)
            self.tabifyDockWidget(self.py_sim_dock, self.ide_dock)


        if hasattr(self, 'view_menu'): # Add toggle actions to View menu
            self.view_menu.addAction(self.tools_dock.toggleViewAction())
            self.view_menu.addAction(self.properties_dock.toggleViewAction())
            self.view_menu.addAction(self.log_dock.toggleViewAction())
            self.view_menu.addAction(self.py_sim_dock.toggleViewAction())
            self.view_menu.addAction(self.ai_chatbot_dock.toggleViewAction())
            if hasattr(self, 'ide_dock'):
                self.view_menu.addAction(self.ide_dock.toggleViewAction())

        self._load_and_display_templates()


    def _load_and_display_templates(self):
        while self.template_buttons_layout.count():
            child = self.template_buttons_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        templates_to_load = []
        for template_key, template_data_json_str in FSM_TEMPLATES_BUILTIN.items():
            try:
                template_data = json.loads(template_data_json_str)
                templates_to_load.append({
                    "id": f"builtin_{template_key}",
                    "name": template_data.get("name", "Unnamed Template"),
                    "description": template_data.get("description", ""),
                    "icon_resource": template_data.get("icon_resource"),
                    "data_json_str": template_data_json_str
                })
            except json.JSONDecodeError as e:
                logger.error(f"Error loading built-in template '{template_key}': {e}")

        # TODO: Load user-defined templates from a directory

        for template_info in templates_to_load:
            icon = QIcon()
            if template_info.get("icon_resource"):
                icon = QIcon(template_info["icon_resource"])
            if icon.isNull():
                icon = get_standard_icon(QStyle.SP_FileDialogContentsView, "Tmpl")

            template_btn = DraggableToolButton(
                template_info["name"],
                "application/x-bsm-template",
                template_info["data_json_str"]
            )
            template_btn.setIcon(icon)
            template_btn.setToolTip(template_info.get("description", template_info["name"])) # << Already using description
            self.template_buttons_layout.addWidget(template_btn)

        self.template_buttons_layout.addStretch(1)


    def _setup_ide_dock_widget(self):
        self.ide_dock = QDockWidget("Standalone Code IDE", self)
        self.ide_dock.setObjectName("IDEDock")
        self.ide_dock.setAllowedAreas(Qt.AllDockWidgetAreas)

        ide_main_widget = QWidget()
        ide_main_layout = QVBoxLayout(ide_main_widget)
        ide_main_layout.setContentsMargins(0,0,0,0)
        ide_main_layout.setSpacing(0)

        ide_toolbar = QToolBar("IDE Tools")
        ide_toolbar.setIconSize(QSize(20,20))
        ide_toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        ide_toolbar.addAction(self.ide_new_file_action)
        ide_toolbar.addAction(self.ide_open_file_action)
        ide_toolbar.addAction(self.ide_save_file_action)
        ide_toolbar.addAction(self.ide_save_as_file_action)
        ide_toolbar.addSeparator()
        ide_toolbar.addAction(self.ide_run_script_action)
        ide_toolbar.addSeparator()
        self.ide_language_combo = QComboBox()
        self.ide_language_combo.addItems(["Python", "C/C++ (Arduino)", "C/C++ (Generic)", "Text"])
        self.ide_language_combo.setToolTip("Select language for syntax highlighting and context")
        self.ide_language_combo.currentTextChanged.connect(self._on_ide_language_changed)
        ide_toolbar.addWidget(QLabel(" Language: "))
        ide_language_combo_container = QWidget()
        ide_language_combo_layout = QHBoxLayout(ide_language_combo_container)
        ide_language_combo_layout.setContentsMargins(2,0,2,0)
        ide_language_combo_layout.addWidget(self.ide_language_combo)
        ide_toolbar.addWidget(ide_language_combo_container)
        ide_toolbar.addSeparator()
        ide_toolbar.addAction(self.ide_analyze_action)


        ide_main_layout.addWidget(ide_toolbar)

        self.ide_code_editor = CodeEditor()
        self.ide_code_editor.setObjectName("StandaloneCodeEditor")
        self.ide_code_editor.setPlaceholderText("Create a new file or open an existing script...")
        self.ide_code_editor.textChanged.connect(self._on_ide_text_changed)
        ide_main_layout.addWidget(self.ide_code_editor, 1)

        self.ide_output_console = QTextEdit()
        self.ide_output_console.setObjectName("IDEOutputConsole")
        self.ide_output_console.setReadOnly(True)
        self.ide_output_console.setPlaceholderText("Script output will appear here...")
        self.ide_output_console.setFixedHeight(160)
        ide_main_layout.addWidget(self.ide_output_console)

        self.ide_dock.setWidget(ide_main_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ide_dock)

        self._update_ide_save_actions_enable_state()
        self._on_ide_language_changed(self.ide_language_combo.currentText())

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1)
        
        self.zoom_status_label = QLabel("Zoom: 100%") # <<<< ADDED
        self.zoom_status_label.setMinimumWidth(80)
        self.zoom_status_label.setAlignment(Qt.AlignCenter)
        self.zoom_status_label.setObjectName("ZoomStatusLabel")
        self.zoom_status_label.setStyleSheet(f"font-size:{APP_FONT_SIZE_SMALL}; padding:2px 4px;")
        self.status_bar.addPermanentWidget(self.zoom_status_label) # <<<< ADDED

        self.cpu_status_label = QLabel("CPU: --%"); self.cpu_status_label.setToolTip("CPU Usage");
        self.ram_status_label = QLabel("RAM: --%"); self.ram_status_label.setToolTip("RAM Usage");
        self.gpu_status_label = QLabel("GPU: N/A"); self.gpu_status_label.setToolTip("GPU Usage (NVIDIA only, if pynvml installed)");

        for label in [self.cpu_status_label, self.ram_status_label, self.gpu_status_label]:
            label.setMinimumWidth(80)
            label.setAlignment(Qt.AlignCenter)
            self.status_bar.addPermanentWidget(label)

        self.py_sim_status_label = QLabel("PySim: Idle"); self.py_sim_status_label.setToolTip("Internal Python FSM Simulation Status.");
        self.py_sim_status_label.setMinimumWidth(120); self.py_sim_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.py_sim_status_label)

        self.matlab_status_label = QLabel("MATLAB: Init..."); self.matlab_status_label.setToolTip("MATLAB connection status.");
        self.matlab_status_label.setMinimumWidth(140); self.matlab_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.matlab_status_label)

        self.internet_status_label = QLabel("Net: Init..."); self.internet_status_label.setToolTip("Internet connectivity. Checks periodically.");
        self.internet_status_label.setMinimumWidth(90); self.internet_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.internet_status_label)

        self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0,0); self.progress_bar.setVisible(False); self.progress_bar.setMaximumWidth(160); self.progress_bar.setTextVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _init_resource_monitor(self):
        self.resource_monitor_thread = QThread(self)
        self.resource_monitor_worker = ResourceMonitorWorker(interval_ms=2000)
        self.resource_monitor_worker.moveToThread(self.resource_monitor_thread)

        self.resource_monitor_worker.resourceUpdate.connect(self._update_resource_display)
        self.resource_monitor_thread.started.connect(self.resource_monitor_worker.start_monitoring)
        self.resource_monitor_worker.finished_signal.connect(self.resource_monitor_thread.quit)
        self.resource_monitor_worker.finished_signal.connect(self.resource_monitor_worker.deleteLater)
        self.resource_monitor_thread.finished.connect(self.resource_monitor_thread.deleteLater)
        self.resource_monitor_thread.start()
        logger.info("Resource monitor thread initialized and started.")



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
            elif PYNVML_AVAILABLE and self.resource_monitor_worker and self.resource_monitor_worker._nvml_initialized:
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
        logger.debug("MW: Received FSM Data (states: %d, transitions: %d)",
                     len(fsm_data.get('states',[])), len(fsm_data.get('transitions',[])))

        if clear_current_diagram:
            if not self.on_new_file(silent=True): 
                 logger.warning("MW: Clearing diagram cancelled by user (save prompt). Cannot add AI FSM.")
                 return
            logger.info("MW: Cleared diagram before AI generation.")

        if not clear_current_diagram:
            self.undo_stack.beginMacro(f"Add AI FSM: {original_user_prompt[:30]}...")

        state_items_map = {}
        items_to_add_for_undo_command = [] 

        layout_start_x, layout_start_y = 100, 100
        default_item_width, default_item_height = 120, 60
        GV_SCALE = 1.3 
        NODE_SEP = 0.8 
        RANK_SEP = 1.5 

        G = pgv.AGraph(directed=True, strict=False, rankdir='TB', ratio='auto', nodesep=str(NODE_SEP), ranksep=str(RANK_SEP))
        G.node_attr['shape'] = 'box'; G.node_attr['style'] = 'rounded,filled'
        G.node_attr['fillcolor'] = QColor(COLOR_ITEM_STATE_DEFAULT_BG).name()
        G.node_attr['color'] = QColor(COLOR_ITEM_STATE_DEFAULT_BORDER).name() 
        G.node_attr['fontname'] = "Arial"; G.node_attr['fontsize'] = "10"
        G.edge_attr['color'] = QColor(COLOR_ITEM_TRANSITION_DEFAULT).name()
        G.edge_attr['fontname'] = "Arial"; G.edge_attr['fontsize'] = "9"


        for state_data in fsm_data.get('states', []):
            name = state_data.get('name')
            label = (name[:25] + '...') if name and len(name) > 28 else name
            if name: G.add_node(name, label=label, width=str(default_item_width/72.0 * 1.1), height=str(default_item_height/72.0 * 1.1))

        for trans_data in fsm_data.get('transitions', []):
            source, target = trans_data.get('source'), trans_data.get('target')
            event_label = trans_data.get('event', '')
            if len(event_label) > 15: event_label = event_label[:12] + '...'

            if source and target and G.has_node(source) and G.has_node(target): G.add_edge(source, target, label=event_label)
            else: logger.warning("MW: Skipping Graphviz edge for AI FSM due to missing node(s): %s->%s", source, target)

        graphviz_positions = {}
        try:
            G.layout(prog="dot"); logger.debug("MW: Graphviz layout ('dot') for AI FSM successful.")
            raw_gv_pos = [{'name': n.name, 'x': float(n.attr['pos'].split(',')[0]), 'y': float(n.attr['pos'].split(',')[1])} for n in G.nodes() if 'pos' in n.attr]
            if raw_gv_pos:
                min_x_gv = min(p['x'] for p in raw_gv_pos); max_y_gv = max(p['y'] for p in raw_gv_pos) 
                for p_gv in raw_gv_pos: graphviz_positions[p_gv['name']] = QPointF((p_gv['x'] - min_x_gv) * GV_SCALE + layout_start_x, (max_y_gv - p_gv['y']) * GV_SCALE + layout_start_y)
            elif fsm_data.get('states'): logger.warning("MW: Graphviz - No valid positions extracted for AI FSM nodes, though states exist.")
        except Exception as e:
            logger.error("MW: Graphviz layout error for AI FSM: %s. Falling back to grid.", str(e).strip() or "Unknown", exc_info=True)
            if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager:
                self.ai_chat_ui_manager._append_to_chat_display("System", f"Warning: AI FSM layout failed (Graphviz error). Using basic grid layout.")
            graphviz_positions = {} 

        for i, state_data in enumerate(fsm_data.get('states', [])):
            name = state_data.get('name'); item_w, item_h = default_item_width, default_item_height
            if not name: logger.warning("MW: AI State data missing 'name'. Skipping."); continue
            pos = graphviz_positions.get(name)
            pos_x, pos_y = (pos.x(), pos.y()) if pos else (layout_start_x + (i % 3) * (item_w + 180), layout_start_y + (i // 3) * (item_h + 120))
            try:
                state_item = GraphicsStateItem(pos_x, pos_y, item_w, item_h, name,
                    is_initial=state_data.get('is_initial', False), is_final=state_data.get('is_final', False),
                    color=state_data.get('properties', {}).get('color',
                           state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG)),
                    entry_action=state_data.get('entry_action', ""), during_action=state_data.get('during_action', ""), exit_action=state_data.get('exit_action', ""),
                    description=state_data.get('description', fsm_data.get('description', "") if i==0 else ""), 
                    is_superstate=state_data.get('is_superstate', False), sub_fsm_data=state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}))

                self.connect_state_item_signals(state_item)
                items_to_add_for_undo_command.append(state_item); state_items_map[name] = state_item
            except Exception as e: logger.error("MW: Error creating AI GraphicsStateItem '%s': %s", name, e, exc_info=True)

        for trans_data in fsm_data.get('transitions', []):
            src_name, tgt_name = trans_data.get('source'), trans_data.get('target')
            if not src_name or not tgt_name: logger.warning("MW: AI Transition missing source/target. Skipping."); continue
            src_item, tgt_item = state_items_map.get(src_name), state_items_map.get(tgt_name)
            if src_item and tgt_item:
                try:
                    trans_item = GraphicsTransitionItem(src_item, tgt_item,
                        event_str=trans_data.get('event', ""), condition_str=trans_data.get('condition', ""), action_str=trans_data.get('action', ""),
                        color=trans_data.get('properties', {}).get('color',
                              trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT)),
                        description=trans_data.get('description', ""))
                    ox, oy = trans_data.get('control_offset_x'), trans_data.get('control_offset_y')
                    if ox is not None and oy is not None:
                        try: trans_item.set_control_point_offset(QPointF(float(ox), float(oy)))
                        except ValueError: logger.warning("MW: Invalid AI control offsets for transition %s->%s.", src_name, tgt_name)
                    items_to_add_for_undo_command.append(trans_item)
                except Exception as e: logger.error("MW: Error creating AI GraphicsTransitionItem %s->%s: %s", src_name, tgt_name, e, exc_info=True)
            else: logger.warning("MW: Could not find source/target GraphicsStateItem for AI transition: %s->%s. Skipping.", src_name, tgt_name)

        max_y_items = max((item.scenePos().y() + item.boundingRect().height() for item in state_items_map.values() if item.scenePos()), default=layout_start_y) if state_items_map else layout_start_y
        for i, comment_data in enumerate(fsm_data.get('comments', [])):
            text = comment_data.get('text'); width = comment_data.get('width')
            if not text: continue
            pos_x = comment_data.get('x', layout_start_x + i * (180 + 25))
            pos_y = comment_data.get('y', max_y_items + 120) 
            try:
                comment_item = GraphicsCommentItem(pos_x, pos_y, text)
                if width:
                    try: comment_item.setTextWidth(float(width))
                    except ValueError: logger.warning("MW: Invalid AI width for comment.")
                items_to_add_for_undo_command.append(comment_item)
            except Exception as e: logger.error("MW: Error creating AI GraphicsCommentItem: %s", e, exc_info=True)


        if items_to_add_for_undo_command:
            for item_to_add in items_to_add_for_undo_command:
                item_type_name = type(item_to_add).__name__.replace("Graphics","").replace("Item","")
                cmd_text = f"Add AI {item_type_name}" + (f": {item_to_add.text_label}" if hasattr(item_to_add, 'text_label') and item_to_add.text_label else "")
                self.undo_stack.push(AddItemCommand(self.scene, item_to_add, cmd_text)) 
            logger.info("MW: Added %d AI-generated items to diagram.", len(items_to_add_for_undo_command))
            QTimer.singleShot(100, self._fit_view_to_new_ai_items)
        else:
            logger.info("MW: No valid AI-generated items to add.")

        if not clear_current_diagram: 
            self.undo_stack.endMacro()

        if self.py_sim_active and items_to_add_for_undo_command:
            logger.info("MW: Reinitializing Python simulation after adding AI FSM.")
            try:
                if self.py_sim_ui_manager:
                    self.py_sim_ui_manager.on_stop_py_simulation(silent=True)
                    self.py_sim_ui_manager.on_start_py_simulation()
                    self.py_sim_ui_manager.append_to_action_log(["Python FSM Simulation reinitialized for new diagram from AI."])
            except FSMError as e:
                if self.py_sim_ui_manager:
                    self.py_sim_ui_manager.append_to_action_log([f"ERROR Re-initializing Sim after AI: {e}"])
                    self.py_sim_ui_manager.on_stop_py_simulation(silent=True)
        logger.debug("MW: ADD_FSM_TO_SCENE processing finished. Items involved: %d", len(items_to_add_for_undo_command))
        self.scene.scene_content_changed_for_find.emit()

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
                    return f"<span style='{style.replace('display: block;', '')} {none_style.replace('font-style:italic;','')}'> (none) </span>"
                
                return f"<span style='{style}'>{display_html}</span>"

            def bool_fmt(val): 
                 color_name = COLOR_ACCENT_SUCCESS if val else QColor(COLOR_TEXT_SECONDARY).darker(110).name()
                 text = "Yes" if val else "No"
                 return f"<span style='color:{color_name}; font-weight:bold; {std_font_size_css}'>{text}</span>"
            
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
        # This method is called by DiagramScene when a right-click occurs on an item.
        if not item.isSelected():
            self.scene.clearSelection() # Ensure only the context-clicked item is selected
            item.setSelected(True)

        menu = QMenu()
        edit_action = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        
        if isinstance(item, GraphicsStateItem) and item.is_superstate:
            pass

        delete_action = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")

        action = menu.exec_(global_pos)
        if action == edit_action:
            self.scene.edit_item_properties(item) # Delegate to scene's method
        elif action == delete_action:
            self.scene.delete_selected_items() # Delegate to scene's method

    @pyqtSlot()
    def on_show_find_item_dialog(self):
        if not self.find_item_dialog:
            self.find_item_dialog = FindItemDialog(parent=self, scene_ref=self.scene)
            self.find_item_dialog.item_selected_for_focus.connect(self.focus_on_item) # CORRECTED CONNECTION
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
    def focus_on_item(self, item_to_focus: QGraphicsItem): # CORRECTED SLOT AND SIGNATURE
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
        else:
            self._log_to_parent("WARNING", f"Could not find or focus on the provided item.")


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