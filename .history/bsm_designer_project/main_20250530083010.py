
# bsm_designer_project/main.py

import sys
import os
import tempfile
import subprocess
import io # For capturing stdout/stderr
import contextlib # For redirecting stdout/stderr
import json
import html
import math
import socket
import re
import logging
from PyQt5.QtCore import QTime, QTimer, QPointF, QMetaObject
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
from code_editor import CodeEditor # Import CodeEditor
from fsm_simulator import FSMSimulator, FSMError
from ai_chatbot import AIChatbotManager
from dialogs import (MatlabSettingsDialog) # Removed duplicate internal MatlabSettingsDialog
from matlab_integration import MatlabConnection # Import from dedicated module
from config import (
    APP_VERSION, APP_NAME, FILE_EXTENSION, FILE_FILTER, STYLE_SHEET_GLOBAL,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG,
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_PRIMARY_LIGHT, COLOR_BACKGROUND_APP,
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_BACKGROUND_LIGHT, COLOR_GRID_MINOR, COLOR_GRID_MAJOR,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_ON_ACCENT,
    COLOR_ACCENT_SECONDARY, COLOR_BORDER_LIGHT, COLOR_BORDER_MEDIUM,
    COLOR_DRAGGABLE_BUTTON_BG, COLOR_DRAGGABLE_BUTTON_BORDER, 
    COLOR_DRAGGABLE_BUTTON_HOVER_BG, COLOR_DRAGGABLE_BUTTON_HOVER_BORDER,
    COLOR_DRAGGABLE_BUTTON_PRESSED_BG, APP_FONT_SIZE_SMALL, APP_FONT_SIZE_STANDARD, 
    APP_FONT_FAMILY, APP_FONT_SIZE_EDITOR,
    COLOR_BACKGROUND_EDITOR_DARK, COLOR_TEXT_EDITOR_DARK_PRIMARY, COLOR_BORDER_DARK,
    COLOR_ACCENT_SUCCESS, COLOR_ACCENT_ERROR, COLOR_BACKGROUND_MEDIUM
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
# --- End Logging Setup ---

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
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform, QKeyEvent, QPainterPathStroker, QPolygonF, QKeySequence,
    QDesktopServices, QWheelEvent, QMouseEvent, QCloseEvent, QFontMetrics, QPalette, QRegion
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QSize, QUrl,
    QSaveFile, QIODevice, pyqtSlot
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QSize, QUrl,
    QSaveFile, QIODevice, pyqtSlot # Add pyqtSlot if not already there
)

logger = logging.getLogger(__name__)

# --- DraggableToolButton Class Definition ---
class DraggableToolButton(QPushButton):
    def __init__(self, text, mime_type, item_type_data, parent=None):
        super().__init__(text, parent) 
        self.setObjectName("DraggableToolButton") 
        self.mime_type = mime_type
        self.item_type_data = item_type_data
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
        mime_data.setText(self.item_type_data)
        mime_data.setData(self.mime_type, self.item_type_data.encode())
        drag.setMimeData(mime_data)
        
        pixmap = QPixmap(self.size())
        #QWidget.render() is more suitable than QWidget.grab() for this purpose as it's designed for off-screen rendering.
        self.render(pixmap, QPoint(), QRegion(), QWidget.RenderFlags(QWidget.DrawChildren)) 
        
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn) 
        painter.fillRect(pixmap.rect(), QColor(0,0,0,150)) 
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos()) 
        drag.exec_(Qt.CopyAction | Qt.MoveAction)

# --- ResourceMonitorWorker Class Definition ---
class ResourceMonitorWorker(QObject):
    resourceUpdate = pyqtSignal(float, float, float, str) # cpu, ram, gpu_util, gpu_name

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
        cycles_per_update = max(1, self.interval_ms // short_sleep_ms)
        current_cycle = 0

        while self._monitoring: 
            if not self._monitoring: 
                break

            if current_cycle == 0:
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
                        if e_nvml_poll.value == pynvml.NVML_ERROR_UNINITIALIZED: self._nvml_initialized = False
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
                            if e_nvml_util.value in (pynvml.NVML_ERROR_GPU_IS_LOST,
                                                     pynvml.NVML_ERROR_INVALID_ARGUMENT,
                                                     pynvml.NVML_ERROR_UNINITIALIZED):
                                self._gpu_handle = None
                                if e_nvml_util.value == pynvml.NVML_ERROR_UNINITIALIZED:
                                    self._nvml_initialized = False
                                logger.warning(f"NVML: GPU handle lost or error {e_nvml_util.value}. Attempting re-init/re-acquire on next cycle.")
                        except Exception as e_util_other:
                            logger.debug(f"NVML: Unexpected error getting GPU utilization: {e_util_other}")
                            gpu_util = -2.0
                            gpu_name_to_emit = "NVML Util Error"
                    if self._monitoring: 
                        self.resourceUpdate.emit(cpu_usage, ram_percent, gpu_util, gpu_name_to_emit)
                except Exception as e:
                    logger.error(f"Error in resource monitoring data collection: {e}", exc_info=True)
                    if self._monitoring: 
                        self.resourceUpdate.emit(-1.0, -1.0, -3.0, f"Monitor Error: {str(e)[:20]}")

            QThread.msleep(short_sleep_ms)
            current_cycle = (current_cycle + 1) % cycles_per_update

        logger.debug("Resource monitor worker loop finished.")


# MainWindow Class
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_file_path = None
        self.last_generated_model_path = None
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)

        self.ai_chatbot_manager = AIChatbotManager(self)

        self.scene = DiagramScene(self.undo_stack, self)

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
        self.init_ui()

        self.py_sim_ui_manager = PySimulationUIManager(self)
        self.ai_chat_ui_manager = AIChatUIManager(self)

        self._populate_dynamic_docks()


        self.current_file_path = None
        self.last_generated_model_path = None
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)
        self.ai_chatbot_manager = AIChatbotManager(self)
        self.scene = DiagramScene(self.undo_stack, self)
        
        # Connect scene's selectionChanged to update zoom_to_selection_action enable state
        self.scene.selectionChanged.connect(self._update_zoom_to_selection_action_enable_state)
        # ... (rest of init, including init_ui call)
        self.init_ui() # Ensure actions are created before trying to connect to scene






        self.py_sim_ui_manager.simulationStateChanged.connect(self._handle_py_sim_state_changed_by_manager)
        self.py_sim_ui_manager.requestGlobalUIEnable.connect(self._handle_py_sim_global_ui_enable_by_manager)

        self._internet_connected: bool | None = None
        self.internet_check_timer = QTimer(self)

        self.resource_monitor_worker: ResourceMonitorWorker | None = None
        self.resource_monitor_thread: QThread | None = None

        try:
            setup_global_logging(self.log_output)
            logger.info("Main window initialized and logging configured.")
        except Exception as e:
            logger.error(f"Failed to run setup_global_logging: {e}. UI logs might not work.")
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
        
        self._update_matlab_status_display(False, "Initializing. Configure MATLAB settings or attempt auto-detect.")
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

        if self.ai_chat_ui_manager:
            if not self.ai_chatbot_manager.api_key:
                self.ai_chat_ui_manager.update_status_display("Status: API Key required. Configure in Settings.")
            elif self._internet_connected : 
                self.ai_chat_ui_manager.update_status_display("Status: Ready.")
        else:
            logger.warning("MainWindow: ai_chat_ui_manager not initialized when trying to set initial status.")
            
        pass # Keep existing content, just showing where to add    


    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050)
        self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM"))
        self._create_central_widget()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_docks() 
        self._create_status_bar()
        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger()

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


        # View Actions
        self.zoom_in_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Z+"), "Zoom In", self, shortcut="Ctrl++", statusTip="Zoom in the view", triggered=self.view.zoom_in if hasattr(self, 'view') else None)
        self.zoom_out_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "Z-"), "Zoom Out", self, shortcut="Ctrl+-", statusTip="Zoom out the view", triggered=self.view.zoom_out if hasattr(self, 'view') else None)
        self.reset_zoom_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "Z0"), "Reset Zoom/View", self, shortcut="Ctrl+0", statusTip="Reset zoom and center view", triggered=self.view.reset_view_and_zoom if hasattr(self, 'view') else None)
        
        self.zoom_to_selection_action = QAction(get_standard_icon(QStyle.SP_FileDialogDetailedView, "ZSel"), "Zoom to Selection", self, statusTip="Zoom to fit selected items", triggered=self.on_zoom_to_selection)
        self.zoom_to_selection_action.setEnabled(False) # Initially disabled

        self.fit_diagram_action = QAction(get_standard_icon(QStyle.SP_FileDialogListView, "ZFit"), "Fit Diagram in View", self, statusTip="Fit entire diagram in view", triggered=self.on_fit_diagram_in_view)
        
        # Snap Actions (from previous step, ensure they are here)
        self.snap_to_objects_action = QAction("Snap to Objects", self, checkable=True, statusTip="Enable/disable snapping to object edges and centers")
        self.snap_to_grid_action = QAction("Snap to Grid", self, checkable=True, statusTip="Enable/disable snapping to grid")
        if hasattr(self, 'scene'): # Check if scene exists before accessing its attributes
            self.snap_to_objects_action.setChecked(self.scene.snap_to_objects_enabled)
            self.snap_to_grid_action.setChecked(self.scene.snap_to_grid_enabled)
        self.snap_to_objects_action.triggered.connect(self.on_toggle_snap_to_objects)
        self.snap_to_grid_action.triggered.connect(self.on_toggle_snap_to_grid)



        self.open_example_menu_action = QAction("Open E&xample...", self)
        self.quick_start_action = QAction(get_standard_icon(QStyle.SP_MessageBoxQuestion, "QS"), "&Quick Start Guide", self, triggered=self.on_show_quick_start)
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, triggered=self.on_about)

        # --- IDE Actions ---
        self.ide_new_file_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "IDENew"), "New Script", self, triggered=self.on_ide_new_file)
        self.ide_open_file_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "IDEOpn"), "Open Script...", self, triggered=self.on_ide_open_file)
        self.ide_save_file_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "IDESav"), "Save Script", self, triggered=self.on_ide_save_file)
        self.ide_save_as_file_action = QAction(get_standard_icon(_safe_get_style_enum("SP_DriveHDIcon", "SP_DialogSaveButton"), "IDESA"), "Save Script As...", self, triggered=self.on_ide_save_as_file)
        self.ide_run_script_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "IDERunPy"), "Run Python Script", self, triggered=self.on_ide_run_python_script)
        self.ide_analyze_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "IDEAI"), "Analyze with AI", self, triggered=self.on_ide_analyze_with_ai)
        self.snap_to_objects_action = QAction("Snap to Objects", self, checkable=True, statusTip="Enable/disable snapping to object edges and centers")
        self.snap_to_objects_action.setChecked(self.scene.snap_to_objects_enabled)
        self.snap_to_objects_action.triggered.connect(self.on_toggle_snap_to_objects)
        
        self.snap_to_grid_action = QAction("Snap to Grid", self, checkable=True, statusTip="Enable/disable snapping to grid")
        self.snap_to_grid_action.setChecked(self.scene.snap_to_grid_enabled)
        self.snap_to_grid_action.triggered.connect(self.on_toggle_snap_to_grid)





        logger.debug(f"MW: AI actions created. Settings: {self.openai_settings_action}, Clear: {self.clear_ai_chat_action}, Generate: {self.ask_ai_to_generate_fsm_action}")
        pass


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
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Mode"),"Interaction Mode")
        mode_menu.addAction(self.select_mode_action)
        mode_menu.addAction(self.add_state_mode_action)
        mode_menu.addAction(self.add_transition_mode_action)
        mode_menu.addAction(self.add_comment_mode_action)

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
        # Add to View Menu or create if it doesn't exist
        if not hasattr(self, 'view_menu'):
            self.view_menu = menu_bar.addMenu("&View")
        self.view_menu.addSeparator()
        snap_menu = self.view_menu.addMenu("Snapping")
        snap_menu.addAction(self.snap_to_grid_action)
        snap_menu.addAction(self.snap_to_objects_action)
        self.view_menu.addSeparator() # Add separator after existing dock toggles if they are there

        # ... (rest of _create_menus, ensuring view_menu dock toggles are added if not done before)
        # Example: if self.tools_dock: self.view_menu.addAction(self.tools_dock.toggleViewAction())
        # Ensure view_menu exists when adding dock toggles later if it's created here for the first time.

        # Add dock toggles to view_menu if it's newly created or existing
        # This section might need to be adjusted based on when _create_docks is called relative to _create_menus
        
        if not hasattr(self, 'view_menu'): # Ensure view_menu exists
            self.view_menu = menu_bar.addMenu("&View")
        
        self.view_menu.addAction(self.zoom_in_action)
        self.view_menu.addAction(self.zoom_out_action)
        self.view_menu.addAction(self.reset_zoom_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.zoom_to_selection_action)
        self.view_menu.addAction(self.fit_diagram_action)
        self.view_menu.addSeparator()

        # Snapping submenu (from previous step)
        snap_menu = self.view_menu.addMenu("Snapping")
        snap_menu.addAction(self.snap_to_grid_action)
        snap_menu.addAction(self.snap_to_objects_action)
        
        # Dock Toggles (ensure they are added correctly, this might be a repetition if already done)
        # If _create_docks is called after _create_menus, self.view_menu will exist.
        # It's safer to add dock toggles in _create_docks after view_menu is guaranteed.
        # For now, let's assume view_menu exists or is created above.
        self.view_menu.addSeparator() # Separator before dock actions

        # Ensure dock toggles are added after view_menu is certainly created
        docks_to_add = []
        if hasattr(self, 'tools_dock') and self.tools_dock: docks_to_add.append(self.tools_dock)
        if hasattr(self, 'properties_dock') and self.properties_dock: docks_to_add.append(self.properties_dock)
        if hasattr(self, 'log_dock') and self.log_dock: docks_to_add.append(self.log_dock)
        if hasattr(self, 'py_sim_dock') and self.py_sim_dock: docks_to_add.append(self.py_sim_dock)
        if hasattr(self, 'ai_chatbot_dock') and self.ai_chatbot_dock: docks_to_add.append(self.ai_chatbot_dock)
        if hasattr(self, 'ide_dock') and self.ide_dock: docks_to_add.append(self.ide_dock)
        
        # Check if the first dock action is already in the menu to avoid duplicates
        first_dock_action_present = False
        if docks_to_add:
            for action in self.view_menu.actions():
                if action.text().startswith(docks_to_add[0].windowTitle()): # A bit heuristic
                    first_dock_action_present = True
                    break
        
        if docks_to_add and not first_dock_action_present:
            for dock in docks_to_add:
                self.view_menu.addAction(dock.toggleViewAction())
        
        
        
        
        
        
        
        
        
        
        
        if hasattr(self, 'view_menu'):
            docks_to_add = []
            if hasattr(self, 'tools_dock') and self.tools_dock: docks_to_add.append(self.tools_dock)
            if hasattr(self, 'properties_dock') and self.properties_dock: docks_to_add.append(self.properties_dock)
            if hasattr(self, 'log_dock') and self.log_dock: docks_to_add.append(self.log_dock)
            if hasattr(self, 'py_sim_dock') and self.py_sim_dock: docks_to_add.append(self.py_sim_dock)
            if hasattr(self, 'ai_chatbot_dock') and self.ai_chatbot_dock: docks_to_add.append(self.ai_chatbot_dock)
            if hasattr(self, 'ide_dock') and self.ide_dock: docks_to_add.append(self.ide_dock)
            
            if docks_to_add and not any(action.text() == docks_to_add[0].windowTitle() for action in self.view_menu.actions()):
                self.view_menu.addSeparator() # Add a separator before dock actions if not already there
                for dock in docks_to_add:
                    self.view_menu.addAction(dock.toggleViewAction())   
                    
                    
        pass             

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
        pass
        
        
        

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)

        self.tools_dock = QDockWidget("Elements & Modes", self) 
        self.tools_dock.setObjectName("ToolsDock")
        self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_widget_main = QWidget()
        tools_widget_main.setObjectName("ToolsDockWidgetContents")
        tools_main_layout = QVBoxLayout(tools_widget_main)
        tools_main_layout.setSpacing(8); tools_main_layout.setContentsMargins(8,8,8,8)
        
        mode_group_box = QGroupBox("Interaction Mode")
        mode_layout = QVBoxLayout(); mode_layout.setSpacing(6)
        self.toolbox_select_button = QToolButton(); self.toolbox_select_button.setDefaultAction(self.select_mode_action)
        self.toolbox_add_state_button = QToolButton(); self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action)
        self.toolbox_transition_button = QToolButton(); self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action)
        self.toolbox_add_comment_button = QToolButton(); self.toolbox_add_comment_button.setDefaultAction(self.add_comment_mode_action)
        for btn in [self.toolbox_select_button, self.toolbox_add_state_button, self.toolbox_transition_button, self.toolbox_add_comment_button]:
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(20,20)); mode_layout.addWidget(btn) 
        mode_group_box.setLayout(mode_layout); tools_main_layout.addWidget(mode_group_box)
        
        draggable_group_box = QGroupBox("Drag New Elements")
        draggable_layout = QVBoxLayout(); draggable_layout.setSpacing(6)
        drag_state_btn = DraggableToolButton("State", "application/x-bsm-tool", "State") 
        drag_state_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))
        drag_initial_state_btn = DraggableToolButton("Initial State", "application/x-bsm-tool", "Initial State")
        drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt")) 
        drag_final_state_btn = DraggableToolButton("Final State", "application/x-bsm-tool", "Final State")
        drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt"))
        drag_comment_btn = DraggableToolButton("Comment", "application/x-bsm-tool", "Comment")
        drag_comment_btn.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))
        for btn in [drag_state_btn, drag_initial_state_btn, drag_final_state_btn, drag_comment_btn]:
            draggable_layout.addWidget(btn)
        draggable_group_box.setLayout(draggable_layout); tools_main_layout.addWidget(draggable_group_box)
        tools_main_layout.addStretch()
        self.tools_dock.setWidget(tools_widget_main)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.tools_dock.toggleViewAction())

        self.properties_dock = QDockWidget("Item Properties", self) 
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        properties_widget = QWidget()
        properties_layout = QVBoxLayout(properties_widget)
        properties_layout.setContentsMargins(8,8,8,8); properties_layout.setSpacing(6)
        self.properties_editor_label = QLabel("<i>Select an item to view its properties.</i>")
        self.properties_editor_label.setObjectName("PropertiesLabel") 
        self.properties_editor_label.setWordWrap(True); self.properties_editor_label.setTextFormat(Qt.RichText)
        self.properties_editor_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        properties_layout.addWidget(self.properties_editor_label, 1)
        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"),"Edit Properties...") 
        self.properties_edit_button.setEnabled(False)
        self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock)
        properties_layout.addWidget(self.properties_edit_button)
        self.properties_dock.setWidget(properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.properties_dock.toggleViewAction())

        self.log_dock = QDockWidget("Application Log", self) 
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0,0,0,0) 
        self.log_output = QTextEdit()
        self.log_output.setObjectName("LogOutputWidget")
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)
        self.log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.log_dock.toggleViewAction())

        self.py_sim_dock = QDockWidget("Python Simulation", self)
        self.py_sim_dock.setObjectName("PySimDock")
        self.py_sim_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.py_sim_dock.toggleViewAction())

        self.ai_chatbot_dock = QDockWidget("AI Assistant", self) 
        self.ai_chatbot_dock.setObjectName("AIChatbotDock")
        self.ai_chatbot_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.ai_chatbot_dock.toggleViewAction())

        self._setup_ide_dock_widget()


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
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.ide_dock.toggleViewAction())

        self._update_ide_save_actions_enable_state() 

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1) 

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
        
        self._update_ide_save_actions_enable_state() 

    def _init_resource_monitor(self):
        self.resource_monitor_thread = QThread(self)
        self.resource_monitor_worker = ResourceMonitorWorker(interval_ms=2000)
        self.resource_monitor_worker.moveToThread(self.resource_monitor_thread)

        self.resource_monitor_worker.resourceUpdate.connect(self._update_resource_display)
        self.resource_monitor_thread.started.connect(self.resource_monitor_worker.start_monitoring)
        self.resource_monitor_thread.finished.connect(self.resource_monitor_worker.deleteLater)
        self.resource_monitor_thread.finished.connect(self.resource_monitor_thread.deleteLater)
        self.resource_monitor_thread.start()
        logger.info("Resource monitor thread initialized and started.")

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
    def on_toggle_snap_to_grid(self, checked):
        self.scene.snap_to_grid_enabled = checked
        logger.info(f"Snap to Grid {'enabled' if checked else 'disabled'}.")
        
        
        
    @pyqtSlot(bool)
    def on_toggle_snap_to_objects(self, checked):
        self.scene.snap_to_objects_enabled = checked
        logger.info(f"Snap to Objects {'enabled' if checked else 'disabled'}.")        

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
        G.node_attr['shape'] = 'box'
        G.node_attr['style'] = 'rounded,filled'
        G.node_attr['fillcolor'] = QColor(COLOR_ITEM_STATE_DEFAULT_BG).name()
        G.node_attr['color'] = QColor(COLOR_ITEM_STATE_DEFAULT_BORDER).name()
        G.node_attr['fontname'] = "Arial" 
        G.node_attr['fontsize'] = "10"
        G.edge_attr['color'] = QColor(COLOR_ITEM_TRANSITION_DEFAULT).name()
        G.edge_attr['fontname'] = "Arial"
        G.edge_attr['fontsize'] = "9"


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
            elif fsm_data.get('states'): logger.warning("MW: Graphviz - No valid positions extracted for AI FSM nodes, though states exist.") # Log only if states were expected
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
                           state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG)), # Check properties first, then top-level color
                    entry_action=state_data.get('entry_action', ""), during_action=state_data.get('during_action', ""), exit_action=state_data.get('exit_action', ""),
                    description=state_data.get('description', fsm_data.get('description', "") if i==0 else ""),
                    is_superstate=state_data.get('is_superstate', False), sub_fsm_data=state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}))
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
                              trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT)), # Check properties first
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
            if not clear_current_diagram:
                for item_to_add in items_to_add_for_undo_command:
                    item_type_name = type(item_to_add).__name__.replace("Graphics","").replace("Item","")
                    cmd_text = f"Add AI {item_type_name}" + (f": {item_to_add.text_label}" if hasattr(item_to_add, 'text_label') and item_to_add.text_label else "")
                    self.undo_stack.push(AddItemCommand(self.scene, item_to_add, cmd_text))
            else:
                for item_to_add in items_to_add_for_undo_command:
                     self.scene.addItem(item_to_add)

            logger.info("MW: Added %d AI-generated items to diagram.", len(items_to_add_for_undo_command))
            self.scene.set_dirty(True)
            QTimer.singleShot(100, self._fit_view_to_new_ai_items)
        else:
            logger.info("MW: No valid AI-generated items to add.")

        if not clear_current_diagram and items_to_add_for_undo_command:
            self.undo_stack.endMacro()
        elif not clear_current_diagram:
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
        std_font_size_css = f"font-size: {APP_FONT_SIZE_STANDARD};" # For general text in properties
        small_font_size_css = f"font-size: {APP_FONT_SIZE_SMALL};" # For less prominent details or compact display
        editor_font_size_css = f"font-size: {APP_FONT_SIZE_EDITOR};" # For code-like text


        if len(selected_items) == 1:
            item = selected_items[0]
            props = item.get_data() if hasattr(item, 'get_data') else {}
            item_type_name = type(item).__name__.replace("Graphics", "").replace("Item", "")
            item_type_tooltip = item_type_name
            edit_enabled = True

            def fmt(txt, max_chars=30, is_code=False): 
                none_style = f"color:{COLOR_TEXT_SECONDARY}; font-style:italic; {small_font_size_css}"
                if not txt: return f"<span style='{none_style}'>(none)</span>"
                txt_str = str(txt)
                first_line = txt_str.split('\n')[0]
                
                if is_code:
                    style = f"font-family: Consolas, 'Courier New', monospace; {small_font_size_css} background-color: {QColor(COLOR_BACKGROUND_EDITOR_DARK).lighter(115).name()}; color: {COLOR_TEXT_EDITOR_DARK_PRIMARY}; padding: 1px 3px; border-radius: 2px; border: 1px solid {QColor(COLOR_BORDER_DARK).lighter(110).name()};"
                else:
                    style = small_font_size_css 
                
                escaped_first_line = html.escape(first_line)
                ellipsis = "&hellip;" if len(first_line) > max_chars or '\n' in txt_str else ""
                # For empty code, display (none) with code style
                if is_code and not escaped_first_line.strip():
                    return f"<span style='{style} {none_style.replace('font-style:italic;','')}'>&nbsp;(none)&nbsp;</span>"
                return f"<span style='{style}'>{escaped_first_line[:max_chars].strip()}{ellipsis}</span>"
            
            def bool_fmt(val):
                 color = COLOR_ACCENT_SUCCESS if val else QColor(COLOR_TEXT_SECONDARY).darker(110).name()
                 text = "Yes" if val else "No"
                 return f"<span style='color:{color}; font-weight:bold; {std_font_size_css}'>{text}</span>"


            rows = ""
            table_style = f"width:100%; border-collapse:collapse; {std_font_size_css} {font_family_css}"
            # th_style is for table headers if we were using them, not used currently
            # td_key_style for the property name cell (left)
            td_key_style = f"padding:5px 8px; text-align:right; font-weight:normal; color:{COLOR_TEXT_SECONDARY}; border-bottom:1px solid {COLOR_BORDER_LIGHT}; width:38%; vertical-align:top;"
            # td_val_style for the property value cell (right)
            td_val_style = f"padding:5px 8px; border-bottom:1px solid {COLOR_BORDER_LIGHT}; vertical-align:top; word-break:break-all;" # Added word-break
            
            item_header_html = f"""
                <div style='{font_family_css}'>
                    <h4 style='margin:0 0 10px 0; padding-bottom:5px; color:{COLOR_ACCENT_PRIMARY}; border-bottom:2px solid {COLOR_BORDER_MEDIUM}; font-size:11pt; font-weight:bold;'>
                        {item_type_name} Properties
                    </h4>
                <table style='{table_style}'>
            """
            
            if isinstance(item, GraphicsStateItem):
                color_obj = QColor(props.get('color', COLOR_ITEM_STATE_DEFAULT_BG))
                lum = color_obj.lightnessF()
                # swatch_text_color not needed if not writing text on swatch
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
                    rows += f"<tr><td style='{td_key_style}'>{act_label}:</td><td style='{td_val_style}'>{fmt(props.get(act_key, ''), 35, is_code=True)}</td></tr>"
                if props.get('description'): rows += f"<tr><td style='{td_key_style}'>Desc:</td><td style='{td_val_style}white-space:normal;{small_font_size_css}'>{html.escape(props.get('description'))}</td></tr>"

            elif isinstance(item, GraphicsTransitionItem):
                color_obj = QColor(props.get('color', COLOR_ITEM_TRANSITION_DEFAULT))
                lum = color_obj.lightnessF()
                # swatch_text_color not needed
                color_style = f"display:inline-block; width:12px; height:12px; border:1px solid {color_obj.darker(120).name()}; background-color:{color_obj.name()}; margin-right:5px; vertical-align:middle;"

                label_parts = []
                if props.get('event'): label_parts.append(f"<b style='color:{COLOR_ACCENT_PRIMARY};'>{html.escape(props.get('event'))}</b>")
                if props.get('condition'): label_parts.append(f"<span style='font-family:Consolas,monospace; color:{COLOR_TEXT_SECONDARY}; {small_font_size_css}'>[{fmt(props.get('condition'), 20, is_code=True)}]</span>")
                if props.get('action'): label_parts.append(f"<span style='font-family:Consolas,monospace;color:{QColor(COLOR_ACCENT_SECONDARY).darker(110).name()}; {small_font_size_css}'>/{{{fmt(props.get('action'),20,is_code=True)}}}</span>")
                full_label = " ".join(p for p in label_parts if p) or f"<span style='color:{COLOR_TEXT_SECONDARY}; font-style:italic; {small_font_size_css}'>(No Label)</span>"

                rows += f"<tr><td style='{td_key_style}'>Label:</td><td style='{td_val_style} {std_font_size_css}'>{full_label}</td></tr>"
                rows += f"<tr><td style='{td_key_style}'>From / To:</td><td style='{td_val_style}'><b>{html.escape(props.get('source','N/A'))}</b> &rarr; <b>{html.escape(props.get('target','N/A'))}</b></td></tr>"
                rows += f"<tr><td style='{td_key_style}'>Color:</td><td style='{td_val_style}'><span style='{color_style}'></span>{html.escape(color_obj.name())}</td></tr>"
                rows += f"<tr><td style='{td_key_style}'>Action Lang:</td><td style='{td_val_style}'><span style='font-family:Consolas,monospace; {small_font_size_css}'>{html.escape(props.get('action_language','N/A'))}</span></td></tr>"
                rows += f"<tr><td style='{td_key_style}'>Curve (Bend/Shift):</td><td style='{td_val_style}'>{props.get('control_offset_x',0):.0f} / {props.get('control_offset_y',0):.0f}</td></tr>"
                if props.get('description'): rows += f"<tr><td style='{td_key_style}'>Desc:</td><td style='{td_val_style}white-space:normal;{small_font_size_css}'>{html.escape(props.get('description'))}</td></tr>"

            elif isinstance(item, GraphicsCommentItem):
                rows += f"<tr><td style='{td_key_style}'>Text:</td><td style='{td_val_style}white-space:normal; font-style:italic; color:{COLOR_TEXT_SECONDARY};'>{html.escape(props.get('text', ''))}</td></tr>"
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


    def _on_edit_selected_item_properties_from_dock(self):
        selected = self.scene.selectedItems()
        if len(selected) == 1:
            self.scene.edit_item_properties(selected[0])

    def _update_window_title(self):
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        ide_file_name = os.path.basename(self.current_ide_file_path) if self.current_ide_file_path else None

        sim_status_suffix = " [PySim Running]" if self.py_sim_active else ""
        ide_suffix = f" | IDE: {ide_file_name}{'*' if self.ide_editor_is_dirty else ''}" if ide_file_name else ""

        modified_indicator = "[*]" if self.isWindowModified() or self.ide_editor_is_dirty else ""
        title = f"{APP_NAME} - {file_name}{sim_status_suffix}{ide_suffix} {modified_indicator}".strip() 
        self.setWindowTitle(title)
        
        if hasattr(self, 'status_label'):
            main_file_status = f"File: {file_name}{' *' if self.isWindowModified() else ''}"
            pysim_status = f"PySim: {'Active' if self.py_sim_active else 'Idle'}"
            ide_file_status = ""
            if ide_file_name:
                 ide_file_status = f"IDE: {ide_file_name}{' *' if self.ide_editor_is_dirty else ''}"
            
            full_status_text_parts = [main_file_status, pysim_status]
            if ide_file_status: full_status_text_parts.append(ide_file_status)
            self.status_label.setText(" | ".join(full_status_text_parts))


    def _update_save_actions_enable_state(self):
        self.save_action.setEnabled(self.isWindowModified())

    def _update_ide_save_actions_enable_state(self):
        if hasattr(self, 'ide_save_file_action'):
            self.ide_save_file_action.setEnabled(self.ide_editor_is_dirty)
        if hasattr(self, 'ide_save_as_file_action'): 
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

        if "Initializing" not in message or (connected and "Initializing" in message):
            logging.info("MATLAB Connection Status: %s", message)

        self._update_matlab_actions_enabled_state()


    def _update_matlab_actions_enabled_state(self):
        can_run_matlab_ops = self.matlab_connection.connected and not self.py_sim_active

        if hasattr(self, 'export_simulink_action'): self.export_simulink_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'run_simulation_action'): self.run_simulation_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'generate_code_action'): self.generate_code_action.setEnabled(can_run_matlab_ops)
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

        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock", "IDEDock"]:
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
        if not self.isWindowModified():
            return True
        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving or opening a new file.")
            return False

        file_desc = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes?",
                                     f"The diagram '{file_desc}' has unsaved changes. Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save)

        if reply == QMessageBox.Save:
            return self.on_save_file()
        elif reply == QMessageBox.Cancel:
            return False
        return True

    def on_new_file(self, silent=False):
        if not silent and not self._prompt_save_if_dirty():
            return False

        if self.py_sim_ui_manager:
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        self.scene.clear()
        self.scene.setSceneRect(0,0,6000,4500)
        self.current_file_path = None
        self.last_generated_model_path = None
        self.undo_stack.clear()
        self.scene.set_dirty(False)
        self.setWindowModified(False) 
        self._update_window_title()
        self._update_undo_redo_actions_enable_state()
        if not silent:
            logging.info("New diagram created.")
            if hasattr(self, 'status_label'): self.status_label.setText("New diagram. Ready.")
        self.view.resetTransform()
        self.view.centerOn(self.scene.sceneRect().center())
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger()
        return True


    def on_open_file(self):
        if not self._prompt_save_if_dirty():
            return
        if self.py_sim_ui_manager:
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)

        if file_path:
            if self._load_from_path(file_path):
                self.current_file_path = file_path
                self.last_generated_model_path = None
                self.undo_stack.clear()
                self.scene.set_dirty(False)
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                logging.info("Opened file: %s", file_path)
                if hasattr(self, 'status_label'): self.status_label.setText(f"Opened: {os.path.basename(file_path)}")
                bounds = self.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else:
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())

            else:
                QMessageBox.critical(self, "Error Opening File", f"Could not load the diagram from:\n{file_path}")
                logging.error("Failed to open file: %s", file_path)

    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data:
                logging.error("Invalid BSM file format: %s. Missing required keys.", file_path)
                return False
            self.scene.load_diagram_data(data)
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
        return self._save_to_path(self.current_file_path)

    def on_save_file_as(self) -> bool:
        default_filename = os.path.basename(self.current_file_path or "untitled" + FILE_EXTENSION)
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()

        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As",
                                                   os.path.join(start_dir, default_filename),
                                                   FILE_FILTER)
        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION

            if self._save_to_path(file_path):
                self.current_file_path = file_path
                return True
        return False

    def _save_to_path(self, file_path) -> bool:
        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving.")
            return False

        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            error_str = save_file.errorString()
            logging.error("Failed to open QSaveFile for %s: %s", file_path, error_str)
            QMessageBox.critical(self, "Save Error", f"Could not open file for saving:\n{error_str}")
            return False

        try:
            diagram_data = self.scene.get_diagram_data()
            json_data_str = json.dumps(diagram_data, indent=4, ensure_ascii=False)
            bytes_written = save_file.write(json_data_str.encode('utf-8'))

            if bytes_written == -1:
                 error_str = save_file.errorString()
                 logging.error("Error writing to QSaveFile %s: %s", file_path, error_str)
                 QMessageBox.critical(self, "Save Error", f"Could not write data to file:\n{error_str}")
                 save_file.cancelWriting()
                 return False

            if not save_file.commit():
                error_str = save_file.errorString()
                logging.error("Failed to commit QSaveFile for %s: %s", file_path, error_str)
                QMessageBox.critical(self, "Save Error", f"Could not finalize saving file:\n{error_str}")
                return False

            logging.info("Successfully saved diagram to: %s", file_path)
            if hasattr(self, 'status_label'): self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            self.scene.set_dirty(False)
            self.setWindowModified(False) 
            self._update_window_title() 
            return True
        except Exception as e:
            logging.error("Unexpected error during save to %s: %s", file_path, e, exc_info=True)
            QMessageBox.critical(self, "Save Error", f"An unexpected error occurred during saving:\n{e}")
            save_file.cancelWriting()
            return False

    def on_select_all(self):
        self.scene.select_all()

    def on_delete_selected(self):
        self.scene.delete_selected_items()

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
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw")," Browse...")
        browse_btn.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
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

    def _get_bundled_file_path(self, filename: str) -> str | None:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        elif getattr(sys, 'frozen', False):
             base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        possible_subdirs = ['', 'docs', 'resources', 'examples', '_internal/bsm_designer_project/docs', '_internal/bsm_designer_project/examples']

        for subdir in possible_subdirs:
            path_to_check = os.path.join(base_path, subdir, filename)
            if os.path.exists(path_to_check):
                logger.debug(f"Found bundled file '{filename}' at: {path_to_check}")
                return path_to_check

        logger.warning(f"Bundled file '{filename}' not found near base path '{base_path}'. Searched subdirs: {possible_subdirs}")
        return None


    def _open_example_file(self, filename: str):
        if not self._prompt_save_if_dirty():
            return
        if self.py_sim_ui_manager: self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        example_path = self._get_bundled_file_path(filename)
        if example_path and os.path.exists(example_path):
            if self._load_from_path(example_path):
                self.current_file_path = example_path
                self.last_generated_model_path = None
                self.undo_stack.clear()
                self.scene.set_dirty(False)
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                logging.info("Opened example file: %s", filename)
                if hasattr(self, 'status_label'): self.status_label.setText(f"Opened example: {filename}")
                bounds = self.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else:
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())
            else:
                QMessageBox.critical(self, "Error Opening Example", f"Could not load the example file:\n{filename}")
                logging.error("Failed to open example file: %s", filename)
        else:
            QMessageBox.warning(self, "Example File Not Found", f"The example file '{filename}' could not be found.")
            logging.warning("Example file '%s' not found at path: %s", filename, example_path)

    def on_show_quick_start(self):
        guide_path = self._get_bundled_file_path("QUICK_START.html")
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
        if not self._prompt_ide_save_if_dirty(): 
            event.ignore()
            return

        if not self._prompt_save_if_dirty(): 
            event.ignore()
            return

        if self.py_sim_ui_manager:
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        if self.internet_check_timer and self.internet_check_timer.isActive():
            self.internet_check_timer.stop()
            logger.debug("Internet check timer stopped.")

        if self.ai_chatbot_manager:
            logger.debug("Stopping AI chatbot manager...")
            self.ai_chatbot_manager.stop_chatbot()
            logger.debug("AI chatbot manager stopped.")

        if self.resource_monitor_thread and self.resource_monitor_thread.isRunning():
            logger.info("Stopping resource monitor worker and thread...")
            if self.resource_monitor_worker:
                self.resource_monitor_worker._monitoring = False
                logger.debug("Resource worker _monitoring flag set to False.")
                
                QMetaObject.invokeMethod(self.resource_monitor_worker, "stop_monitoring", Qt.QueuedConnection)
                logger.debug("stop_monitoring invoked on resource_monitor_worker (queued).")

            self.resource_monitor_thread.quit()
            logger.debug("resource_monitor_thread.quit() called.")

            wait_time_ms = 200
            if self.resource_monitor_worker and hasattr(self.resource_monitor_worker, 'interval_ms'):
                wait_time_ms = self.resource_monitor_worker.interval_ms + 500 
            else:
                logger.warning("ResourceMonitorWorker or interval_ms not available, using default wait time for shutdown (2500ms).")
                wait_time_ms = 2500

            if not self.resource_monitor_thread.wait(wait_time_ms):
                logger.warning(f"Resource monitor thread did not quit gracefully after {wait_time_ms}ms. Terminating.")
                self.resource_monitor_thread.terminate()
                if not self.resource_monitor_thread.wait(500):
                    logger.error("Resource monitor thread failed to terminate forcefully.")
            else:
                logger.info("Resource monitor thread stopped gracefully.")

        self.resource_monitor_worker = None
        self.resource_monitor_thread = None
        logger.debug("Resource monitor worker and thread references cleared.")

        if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads:
            logging.info("Closing application. %d MATLAB processes initiated by this session may still be running in the background if not completed.", len(self.matlab_connection._active_threads))

        logger.info("Application closeEvent accepted.")
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
            elif not (current_ide_lang == "Python" or current_ide_lang.startswith("C/C++")): # Check if current_ide_lang matches what we want for analysis
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

        if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager:
            if not key_present:
                self.ai_chat_ui_manager.update_status_display("Status: API Key required. Configure in Settings.")
            elif not is_connected:
                self.ai_chat_ui_manager.update_status_display("Status: Offline. AI features unavailable.")


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

    # --- IDE Dock Methods ---
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
                self._update_window_title()
                if self.ide_output_console: self.ide_output_console.clear()
                logger.info("IDE: Opened script: %s", file_path)
                
                if hasattr(self, 'ide_language_combo'):
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext == ".py": self.ide_language_combo.setCurrentText("Python")
                    elif ext in [".ino", ".c", ".cpp", ".h"]: self.ide_language_combo.setCurrentText("C/C++ (Arduino)") 
                    else: self.ide_language_combo.setCurrentText("Text")

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
    def _on_ide_language_changed(self, language_param: str): # Renamed from language to avoid conflict
        if self.ide_code_editor:
            self.ide_code_editor.set_language(language_param)

        if self.ide_run_script_action:
            is_python = (language_param == "Python")
            self.ide_run_script_action.setEnabled(is_python)
            self.ide_run_script_action.setToolTip("Run the current Python script in the editor" if is_python else "Run is currently only supported for Python scripts")
        if self.ide_analyze_action:
            
            can_analyze = (language_param == "Python" or language_param.startswith("C/C++")) and \
                          self.ai_chatbot_manager is not None and \
                          self.ai_chatbot_manager.api_key is not None and \
                          self._internet_connected 
            self.ide_analyze_action.setEnabled(can_analyze)
            tooltip = "Analyze the current code with AI"
            if not (self.ai_chatbot_manager and self.ai_chatbot_manager.api_key and self._internet_connected):
                tooltip += " (Requires Internet & Gemini API Key)"
            elif not (language_param == "Python" or language_param.startswith("C/C++")): 
                 tooltip += " (Best for Python or C/C++)"
            self.ide_analyze_action.setToolTip(tooltip)

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

        # Clear previous output and add a timestamped start message
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
        
        self.ai_chat_ui_manager._append_to_chat_display("IDE", f"Requesting AI analysis for the current script ({selected_language}).")
        self.ai_chatbot_manager.send_message(prompt)


    def log_message(self, level_str: str, message: str):
        level = getattr(logging, level_str.upper(), logging.INFO)
        logger.log(level, message) 


if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    import traceback 
    app_dir = os.path.dirname(os.path.abspath(__file__))
    deps_icons_dir = os.path.join(app_dir, "dependencies", "icons")
    if not os.path.exists(deps_icons_dir):
        try:
            os.makedirs(deps_icons_dir, exist_ok=True)
            print(f"Info: Created directory for QSS icons: {deps_icons_dir}")
            check_png_path = os.path.join(deps_icons_dir, "check.png")
            if not os.path.exists(check_png_path):
                try:
                    from PIL import Image, ImageDraw 
                    img = Image.new('RGBA', (16, 16), (255, 0, 0, 0)) 
                    draw = ImageDraw.Draw(img)
                    draw.line([(3,8), (7,12), (13,3)], fill=(0,180,0,255), width=2)
                    img.save(check_png_path)
                    print(f"Info: Created dummy check.png at {check_png_path}")
                except ImportError:
                    print("Warning: PIL not found, cannot create dummy check.png. QCheckBox checkmark might not appear.")
                except Exception as e_img:
                    print(f"Warning: Could not create dummy check.png: {e_img}")
            arrow_down_png_path = os.path.join(deps_icons_dir, "arrow_down.png")
            if not os.path.exists(arrow_down_png_path):
                try:
                    from PIL import Image, ImageDraw
                    img_arrow = Image.new('RGBA', (12, 12), (255,0,0,0))
                    draw_arrow = ImageDraw.Draw(img_arrow)
                    draw_arrow.polygon([(2,3), (10,3), (6,9)], fill=(80,80,80,255))
                    img_arrow.save(arrow_down_png_path)
                    print(f"Info: Created dummy arrow_down.png at {arrow_down_png_path}")
                except ImportError:
                     print("Warning: PIL not found, cannot create dummy arrow_down.png.")
                except Exception as e_img_arr:
                    print(f"Warning: Could not create dummy arrow_down.png: {e_img_arr}")


        except OSError as e:
            print(f"Warning: Could not create directory {deps_icons_dir}: {e}")


    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET_GLOBAL)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
    pass
