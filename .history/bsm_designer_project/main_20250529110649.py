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
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_PRIMARY_LIGHT,
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_BACKGROUND_LIGHT, COLOR_GRID_MINOR, COLOR_GRID_MAJOR,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_ON_ACCENT,
    COLOR_ACCENT_SECONDARY, COLOR_BORDER_LIGHT, COLOR_BORDER_MEDIUM,
    DEFAULT_EXECUTION_ENV # Ensure this is imported
)
from export_utils import generate_plantuml_text, generate_mermaid_text # Add mermaid import
from utils import get_standard_icon

# --- UI Managers ---
from ui_py_simulation_manager import PySimulationUIManager
from ui_ai_chatbot_manager import AIChatUIManager

# --- Logging Setup ---
try:
    from logging_setup import setup_global_logging
except ImportError:
    print("CRITICAL: logging_setup.py not found. Logging will be basic.")
    # Fallback basicConfig if logging_setup is missing
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s', datefmt='%H:%M:%S')

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
    QDesktopServices, QWheelEvent, QMouseEvent, QCloseEvent, QFontMetrics, QPalette
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QSize, QUrl,
    QSaveFile, QIODevice, pyqtSlot
)

logger = logging.getLogger(__name__) # Main application logger

# --- DraggableToolButton Class Definition ---
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

        # Create a pixmap for the drag preview
        pixmap_size = QSize(max(150, self.width()), max(40, self.height()))
        pixmap = QPixmap(pixmap_size)
        pixmap.fill(Qt.transparent) # Transparent background

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw a styled button-like representation for the drag
        button_rect = QRectF(0, 0, pixmap_size.width() -1, pixmap_size.height() -1)
        # Use palette colors if available, otherwise fall back to config colors
        bg_color = QColor(self.palette().color(self.backgroundRole())).lighter(110)
        if not bg_color.isValid() or bg_color.alpha() == 0: # Check if color is valid (e.g. if palette not fully set)
            bg_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT) # Fallback
        border_color_qcolor = QColor(COLOR_ACCENT_PRIMARY)

        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color_qcolor, 1.5))
        painter.drawRoundedRect(button_rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5) # Adjust for crisp border

        # Draw icon and text
        icon_pixmap = self.icon().pixmap(QSize(20, 20), QIcon.Normal, QIcon.On)
        text_x_offset = 10
        icon_y_offset = (pixmap_size.height() - icon_pixmap.height()) / 2
        if not icon_pixmap.isNull():
            painter.drawPixmap(int(text_x_offset), int(icon_y_offset), icon_pixmap)
            text_x_offset += icon_pixmap.width() + 8 # Spacing after icon

        text_color_qcolor = self.palette().color(QPalette.ButtonText)
        if not text_color_qcolor.isValid(): text_color_qcolor = QColor(COLOR_TEXT_PRIMARY)
        painter.setPen(text_color_qcolor)
        painter.setFont(self.font())

        text_rect = QRectF(text_x_offset, 0, pixmap_size.width() - text_x_offset - 5, pixmap_size.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 4, pixmap.height() // 2)) # Hotspot for dragging
        drag.exec_(Qt.CopyAction | Qt.MoveAction)

# --- ResourceMonitorWorker Class Definition (Moved to top level) ---
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
                    self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0) # Get first GPU
                    gpu_name_raw = pynvml.nvmlDeviceGetName(self._gpu_handle)
                    # Handle bytes vs str for GPU name
                    if isinstance(gpu_name_raw, bytes): self._gpu_name_cache = gpu_name_raw.decode('utf-8', errors='replace')
                    elif isinstance(gpu_name_raw, str): self._gpu_name_cache = gpu_name_raw
                    else: logger.warning(f"NVML: Unexpected type for GPU name: {type(gpu_name_raw)}"); self._gpu_name_cache = "NVIDIA GPU Name TypeErr"
                else:
                    self._gpu_name_cache = "NVIDIA GPU N/A" # No NVIDIA GPU found by NVML
            except pynvml.NVMLError as e_nvml:
                logger.warning(f"Could not initialize NVML (for NVIDIA GPU monitoring): {e_nvml}")
                self._nvml_initialized = False
                error_code_str = f" (Code: {e_nvml.value})" if hasattr(e_nvml, 'value') else ""
                self._gpu_name_cache = f"NVIDIA NVML Err ({type(e_nvml).__name__}{error_code_str})"
            except AttributeError as e_attr: # e.g. if nvmlDeviceGetName somehow missing
                 logger.warning(f"NVML: Attribute error during init (possibly on .decode for name): {e_attr}")
                 self._nvml_initialized = False; self._gpu_name_cache = "NVML Attr Err"
            except Exception as e: # Catch-all for other init errors
                logger.warning(f"Unexpected error during NVML init: {e}", exc_info=True)
                self._nvml_initialized = False; self._gpu_name_cache = "NVML Init Error"
        elif not PYNVML_AVAILABLE:
            self._gpu_name_cache = "N/A (pynvml N/A)"

    @pyqtSlot()
    def start_monitoring(self):
        logger.info("ResourceMonitorWorker: start_monitoring called.")
        self._monitoring = True
        self._monitor_resources() # Start the loop

    @pyqtSlot()
    def stop_monitoring(self):
        logger.info("ResourceMonitorWorker: stop_monitoring called.")
        self._monitoring = False # Primary flag to stop the loop
        if self._nvml_initialized and PYNVML_AVAILABLE and pynvml:
            try:
                pynvml.nvmlShutdown()
                logger.info("ResourceMonitorWorker: NVML shutdown.")
            except Exception as e:
                logger.warning(f"Error shutting down NVML: {e}")
        self._nvml_initialized = False # Reset flags
        self._gpu_handle = None

    def _monitor_resources(self):
        logger.debug("Resource monitor worker loop started.")
        # Use a shorter sleep and cycle count to allow faster stop response
        short_sleep_ms = 200 # Check _monitoring flag more frequently
        cycles_per_update = max(1, self.interval_ms // short_sleep_ms)
        current_cycle = 0

        while self._monitoring: # Loop condition checks the flag
            if not self._monitoring: break # Exit if flag changed during sleep/processing

            if current_cycle == 0: # Time to update
                # --- NVML Re-initialization/Handle Acquisition Logic ---
                # Attempt to re-init NVML if it failed or GPU was lost
                if PYNVML_AVAILABLE and pynvml and not self._nvml_initialized :
                    try:
                        pynvml.nvmlInit()
                        self._nvml_initialized = True
                        logger.info("NVML re-initialized successfully in worker loop.")
                    except pynvml.NVMLError as e_reinit:
                        logger.warning(f"NVML: Failed to re-initialize in worker loop: {e_reinit}")
                        self._nvml_initialized = False; error_code_str = f" (Code: {e_reinit.value})" if hasattr(e_reinit, 'value') else ""; self._gpu_name_cache = f"NVIDIA NVML ReinitErr ({type(e_reinit).__name__}{error_code_str})"

                # Attempt to get GPU handle if NVML is initialized but no handle
                if PYNVML_AVAILABLE and pynvml and self._nvml_initialized and not self._gpu_handle:
                    try:
                        if pynvml.nvmlDeviceGetCount() > 0:
                            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                            gpu_name_raw = pynvml.nvmlDeviceGetName(self._gpu_handle)
                            if isinstance(gpu_name_raw, bytes): self._gpu_name_cache = gpu_name_raw.decode('utf-8', 'replace')
                            elif isinstance(gpu_name_raw, str): self._gpu_name_cache = gpu_name_raw
                            else: self._gpu_name_cache = "NVIDIA GPU Name TypeErr (Poll)"
                            logger.info(f"NVML: GPU handle acquired for {self._gpu_name_cache} in worker loop.")
                        else:
                            self._gpu_name_cache = "NVIDIA GPU N/A"
                    except pynvml.NVMLError as e_nvml_poll:
                        logger.debug(f"NVML: Error getting GPU handle during poll: {e_nvml_poll}")
                        error_code_str = f" (Code: {e_nvml_poll.value})" if hasattr(e_nvml_poll, 'value') else ""; self._gpu_name_cache = f"NVIDIA Poll Err ({type(e_nvml_poll).__name__}{error_code_str})"; self._gpu_handle = None
                        if e_nvml_poll.value == pynvml.NVML_ERROR_UNINITIALIZED: self._nvml_initialized = False
                    except AttributeError as e_attr: logger.warning(f"NVML: Attribute error getting GPU handle (possibly on .decode for name): {e_attr}"); self._gpu_name_cache = "NVML Handle Attr Err"; self._gpu_handle = None
                    except Exception as e_poll: logger.debug(f"NVML: Unexpected error getting GPU handle during poll: {e_poll}"); self._gpu_name_cache = "NVML Poll Error"; self._gpu_handle = None
                # --- End NVML Re-initialization/Handle Acquisition Logic ---

                try:
                    cpu_usage = psutil.cpu_percent(interval=None) # Non-blocking
                    ram_percent = psutil.virtual_memory().percent
                    gpu_util, gpu_name_to_emit = -1.0, self._gpu_name_cache # Default if no GPU or error

                    if self._nvml_initialized and self._gpu_handle and PYNVML_AVAILABLE and pynvml:
                        try: gpu_util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle).gpu
                        except pynvml.NVMLError as e_nvml_util: # Handle errors during utilization fetch
                            logger.debug(f"NVML: Error getting GPU utilization: {e_nvml_util}")
                            gpu_util = -2.0 # Specific error code for util fetch fail
                            error_code_str = f" (Code: {e_nvml_util.value})" if hasattr(e_nvml_util, 'value') else ""; gpu_name_to_emit = f"NVIDIA Util Err ({type(e_nvml_util).__name__}{error_code_str})"
                            # If GPU is lost or NVML uninitialized, reset handle/init flag
                            if e_nvml_util.value in (pynvml.NVML_ERROR_GPU_IS_LOST, pynvml.NVML_ERROR_INVALID_ARGUMENT, pynvml.NVML_ERROR_UNINITIALIZED):
                                self._gpu_handle = None
                                if e_nvml_util.value == pynvml.NVML_ERROR_UNINITIALIZED: self._nvml_initialized = False
                                logger.warning(f"NVML: GPU handle lost or error {e_nvml_util.value}. Attempting re-init/re-acquire on next cycle.")
                        except Exception as e_util_other: # Catch-all for other util fetch errors
                            logger.debug(f"NVML: Unexpected error getting GPU utilization: {e_util_other}")
                            gpu_util = -2.0; gpu_name_to_emit = "NVML Util Error"
                    
                    if self._monitoring: # Only emit if still supposed to be monitoring
                        self.resourceUpdate.emit(cpu_usage, ram_percent, gpu_util, gpu_name_to_emit)
                except Exception as e: # Catch errors in psutil or general logic
                    logger.error(f"Error in resource monitoring data collection: {e}", exc_info=True)
                    if self._monitoring:
                        self.resourceUpdate.emit(-1.0, -1.0, -3.0, f"Monitor Error: {str(e)[:20]}")

            QThread.msleep(short_sleep_ms) # Brief sleep in each cycle
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
        self.scene.item_moved.connect(self._clear_validation_highlights_on_modify)
        self.scene.changed.connect(self._clear_validation_highlights_on_modify) # Connect scene's generic changed signal too

        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False

        # --- IDE Dock Attributes ---
        self.ide_code_editor: CodeEditor | None = None
        self.current_ide_file_path: str | None = None
        self.ide_output_console: QTextEdit | None = None
        self.ide_run_script_action: QAction | None = None
        self.ide_analyze_action: QAction | None = None
        self.ide_editor_is_dirty = False
        # --- CRITICAL ORDERING ---
        self.init_ui() # Creates dock widget instances among other things

        # Setup logging as early as possible, requires self.log_output to be created by init_ui
        try:
            setup_global_logging(self.log_output)
            logger.info("Main window initialized and logging configured.")
        except Exception as e: # Fallback if setup_global_logging fails
            logger.error(f"Failed to run setup_global_logging: {e}. UI logs might not work as expected.")
            if not logging.getLogger().hasHandlers(): # Basic console logging if all else fails
                 logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s', datefmt='%H:%M:%S')

        self.py_sim_ui_manager = PySimulationUIManager(self)
        self.ai_chat_ui_manager = AIChatUIManager(self)

        # NOW that UI managers are created, populate their dock contents
        self._populate_dynamic_docks()


        self.py_sim_ui_manager.simulationStateChanged.connect(self._handle_py_sim_state_changed_by_manager)
        self.py_sim_ui_manager.requestGlobalUIEnable.connect(self._handle_py_sim_global_ui_enable_by_manager)

        self._internet_connected: bool | None = None
        self.internet_check_timer = QTimer(self)

        self.resource_monitor_worker: ResourceMonitorWorker | None = None
        self.resource_monitor_thread: QThread | None = None

        self._init_resource_monitor()

        # Set object names for status labels for potential styling via QSS
        if hasattr(self, 'matlab_status_label'): self.matlab_status_label.setObjectName("MatlabStatusLabel")
        if hasattr(self, 'py_sim_status_label'): self.py_sim_status_label.setObjectName("PySimStatusLabel")
        if hasattr(self, 'internet_status_label'): self.internet_status_label.setObjectName("InternetStatusLabel")
        if hasattr(self, 'status_label'): self.status_label.setObjectName("StatusLabel")

        self._update_matlab_status_display(False, "Initializing. Configure MATLAB settings or attempt auto-detect.")
        self._update_py_sim_status_display()

        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)

        self._update_window_title()
        self.on_new_file(silent=True) # Initialize with a clean, new file state
        self._init_internet_status_check()
        self.scene.selectionChanged.connect(self._update_properties_dock)
        self._update_properties_dock() # Initial call
        self._update_py_simulation_actions_enabled_state()

        # Initialize AI chatbot status display
        if self.ai_chat_ui_manager:
            if not self.ai_chatbot_manager.api_key:
                self.ai_chat_ui_manager.update_status_display("Status: API Key required. Configure in Settings.")
            elif self._internet_connected is True : # Check if internet status is known and true
                self.ai_chat_ui_manager.update_status_display("Status: Ready.")
            elif self._internet_connected is False:
                 self.ai_chat_ui_manager.update_status_display("Status: Offline. AI features unavailable.")
            # else: internet status is None (unknown), status will be updated by check job
        else:
            logger.warning("MainWindow: ai_chat_ui_manager not initialized when trying to set initial AI status.")


    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050)
        self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM"))
        self._create_central_widget()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_docks() # This will create QDockWidget instances
        self._create_status_bar()
        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger() # Default to select mode

    def _populate_dynamic_docks(self):
        """Populates dock widgets whose content depends on UI managers."""
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

        # Tabify after content is set for more reliable behavior
        self.tabifyDockWidget(self.properties_dock, self.ai_chatbot_dock)
        self.tabifyDockWidget(self.ai_chatbot_dock, self.py_sim_dock)
        if hasattr(self, 'ide_dock'): # If IDE dock exists
            self.tabifyDockWidget(self.py_sim_dock, self.ide_dock)
            self.ide_dock.raise_() # Optionally bring IDE dock to front of its tab group
        self.properties_dock.raise_() # Bring properties dock to front of its tab group


    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self)
        self.view.setObjectName("MainDiagramView")
        self.setCentralWidget(self.view)

    def _create_actions(self):
        # Helper for QStyle enums for icon fallbacks
        def _safe_get_style_enum(attr_name, fallback_attr_name=None):
            try: return getattr(QStyle, attr_name)
            except AttributeError:
                if fallback_attr_name:
                    try: return getattr(QStyle, fallback_attr_name)
                    except AttributeError: pass
                return QStyle.SP_CustomBase # Fallback to a generic base if all fail

        # File Actions
        self.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "New"), "&New", self, shortcut=QKeySequence.New, statusTip="Create a new file", triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "Opn"), "&Open...", self, shortcut=QKeySequence.Open, statusTip="Open an existing file", triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Sav"), "&Save", self, shortcut=QKeySequence.Save, statusTip="Save the current file", triggered=self.on_save_file)
        self.save_as_action = QAction(
            get_standard_icon(_safe_get_style_enum("SP_DriveHDIcon", "SP_DialogSaveButton"), "SA"), # Use helper for icon
            "Save &As...", self, shortcut=QKeySequence.SaveAs,
            statusTip="Save the current file with a new name", triggered=self.on_save_file_as
        )
        # Export Actions
        self.export_simulink_action = QAction(get_standard_icon(_safe_get_style_enum("SP_ArrowUp","SP_ArrowRight"), "->M"), "&Export to Simulink...", self, triggered=self.on_export_simulink)
        self.export_plantuml_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "PUML"), "Export as PlantUML...", self, triggered=self.on_export_plantuml) # New PlantUML action
        self.export_mermaid_action = QAction(get_standard_icon(QStyle.SP_FileDialogListView, "MMD"), "Export as Mermaid...", self, triggered=self.on_export_mermaid) # New Mermaid action

        self.exit_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", self, shortcut=QKeySequence.Quit, statusTip="Exit the application", triggered=self.close)

        # Edit Actions
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

        self.auto_layout_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "Layout"), "&Auto-Layout Diagram", self, statusTip="Automatically arrange diagram elements", triggered=self.on_auto_layout)
        self.validate_diagram_action = QAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Vld"), "&Validate Diagram", self, statusTip="Check diagram for common issues", triggered=self.on_validate_diagram)


        # Interaction Mode Actions
        self.mode_action_group = QActionGroup(self)
        self.mode_action_group.setExclusive(True)
        self.select_mode_action = QAction(QIcon.fromTheme("edit-select", get_standard_icon(QStyle.SP_ArrowRight, "Sel")), "Select/Move", self, checkable=True, triggered=lambda: self.scene.set_mode("select"))
        self.select_mode_action.setObjectName("select_mode_action") # For QSS or direct access
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", get_standard_icon(QStyle.SP_FileDialogNewFolder, "St")), "Add State", self, checkable=True, triggered=lambda: self.scene.set_mode("state"))
        self.add_state_mode_action.setObjectName("add_state_mode_action")
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", get_standard_icon(QStyle.SP_ArrowForward, "Tr")), "Add Transition", self, checkable=True, triggered=lambda: self.scene.set_mode("transition"))
        self.add_transition_mode_action.setObjectName("add_transition_mode_action")
        self.add_comment_mode_action = QAction(QIcon.fromTheme("insert-text", get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm")), "Add Comment", self, checkable=True, triggered=lambda: self.scene.set_mode("comment"))
        self.add_comment_mode_action.setObjectName("add_comment_mode_action")
        for action in [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action]:
            self.mode_action_group.addAction(action)
        self.select_mode_action.setChecked(True) # Default mode

        # Simulation Actions
        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation (MATLAB)...", self, triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"), "Generate &Code (C/C++ via MATLAB)...", self, triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"), "&MATLAB Settings...", self, triggered=self.on_matlab_settings)

        # Python Simulation Actions
        self.start_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Py▶"), "&Start Python Simulation", self, statusTip="Start internal FSM simulation")
        self.stop_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaStop, "Py■"), "S&top Python Simulation", self, statusTip="Stop internal FSM simulation", enabled=False)
        self.reset_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaSkipBackward, "Py«"), "&Reset Python Simulation", self, statusTip="Reset internal FSM simulation", enabled=False)

        # AI Chatbot Actions
        self.openai_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "AISet"), "AI Assistant Settings (Gemini)...", self) # Text updated to Gemini
        self.clear_ai_chat_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "Clear"), "Clear Chat History", self)
        self.ask_ai_to_generate_fsm_action = QAction(
            get_standard_icon(QStyle.SP_ArrowRight, "AIGen"), # Or a more AI-specific icon
            "Generate FSM from Description...",
            self
        )

        # Help Actions
        self.open_example_menu_action = QAction("Open E&xample...", self) # This seems to be a submenu trigger now
        self.quick_start_action = QAction(get_standard_icon(QStyle.SP_MessageBoxQuestion, "QS"), "&Quick Start Guide", self, triggered=self.on_show_quick_start)
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, triggered=self.on_about)

        # --- IDE Actions ---
        self.ide_new_file_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "IDENew"), "New Script", self, triggered=self.on_ide_new_file)
        self.ide_open_file_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "IDEOpn"), "Open Script...", self, triggered=self.on_ide_open_file)
        self.ide_save_file_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "IDESav"), "Save Script", self, triggered=self.on_ide_save_file)
        self.ide_save_as_file_action = QAction(get_standard_icon(_safe_get_style_enum("SP_DriveHDIcon", "SP_DialogSaveButton"), "IDESA"), "Save Script As...", self, triggered=self.on_ide_save_as_file)
        self.ide_run_script_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "IDERunPy"), "Run Python Script", self, triggered=self.on_ide_run_python_script)
        self.ide_analyze_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "IDEAI"), "Analyze with AI", self, triggered=self.on_ide_analyze_with_ai)


        logger.debug(f"MW: AI actions created. Settings: {self.openai_settings_action}, Clear: {self.clear_ai_chat_action}, Generate: {self.ask_ai_to_generate_fsm_action}")


    def _create_menus(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        example_menu = file_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ex"), "Open E&xample")
        # Add example file actions (paths should be relative or handled by a resource system)
        self.open_example_traffic_action = example_menu.addAction("Traffic Light FSM", lambda: self._open_example_file("traffic_light.bsm"))
        self.open_example_toggle_action = example_menu.addAction("Simple Toggle FSM", lambda: self._open_example_file("simple_toggle.bsm"))
        # Add more examples here
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        export_menu = file_menu.addMenu(get_standard_icon(QStyle.SP_DialogSaveButton, "Exp"), "&Export As") # Export submenu
        export_menu.addAction(self.export_simulink_action)
        export_menu.addAction(self.export_plantuml_action)
        export_menu.addAction(self.export_mermaid_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        # Edit Menu
        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.delete_action)
        edit_menu.addAction(self.select_all_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.auto_layout_action)
        edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Mode"),"Interaction Mode")
        mode_menu.addAction(self.select_mode_action)
        mode_menu.addAction(self.add_state_mode_action)
        mode_menu.addAction(self.add_transition_mode_action)
        mode_menu.addAction(self.add_comment_mode_action)

        # Simulation Menu
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

        # View Menu (Docks will be added here)
        self.view_menu = menu_bar.addMenu("&View")

        # Tools Menu
        tools_menu = menu_bar.addMenu("&Tools")
        tools_menu.addAction(self.validate_diagram_action)
        tools_menu.addSeparator()
        ide_menu = tools_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogDetailedView, "IDE"), "Standalone Code IDE")
        ide_menu.addAction(self.ide_new_file_action)
        ide_menu.addAction(self.ide_open_file_action)
        ide_menu.addAction(self.ide_save_file_action)
        ide_menu.addAction(self.ide_save_as_file_action)
        ide_menu.addSeparator()
        ide_menu.addAction(self.ide_run_script_action)
        ide_menu.addAction(self.ide_analyze_action)


        # AI Assistant Menu
        ai_menu = menu_bar.addMenu("&AI Assistant")
        ai_menu.addAction(self.ask_ai_to_generate_fsm_action)
        ai_menu.addAction(self.clear_ai_chat_action)
        ai_menu.addSeparator()
        ai_menu.addAction(self.openai_settings_action) # Text updated in action creation

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.quick_start_action)
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(22,22) # Consistent icon size for toolbars
        tb_style = Qt.ToolButtonTextBesideIcon # Style for tool buttons

        # File Toolbar
        file_toolbar = self.addToolBar("File")
        file_toolbar.setObjectName("FileToolBar")
        file_toolbar.setIconSize(icon_size)
        file_toolbar.setToolButtonStyle(tb_style)
        file_toolbar.addAction(self.new_action)
        file_toolbar.addAction(self.open_action)
        file_toolbar.addAction(self.save_action)

        # Edit Toolbar
        edit_toolbar = self.addToolBar("Edit")
        edit_toolbar.setObjectName("EditToolBar")
        edit_toolbar.setIconSize(icon_size)
        edit_toolbar.setToolButtonStyle(tb_style)
        edit_toolbar.addAction(self.undo_action)
        edit_toolbar.addAction(self.redo_action)
        edit_toolbar.addSeparator()
        edit_toolbar.addAction(self.delete_action)
        edit_toolbar.addSeparator()
        edit_toolbar.addAction(self.auto_layout_action)
        edit_toolbar.addAction(self.validate_diagram_action)


        # Interaction Tools Toolbar
        tools_tb = self.addToolBar("Interaction Tools")
        tools_tb.setObjectName("ToolsToolBar")
        tools_tb.setIconSize(icon_size)
        tools_tb.setToolButtonStyle(tb_style)
        tools_tb.addAction(self.select_mode_action)
        tools_tb.addAction(self.add_state_mode_action)
        tools_tb.addAction(self.add_transition_mode_action)
        tools_tb.addAction(self.add_comment_mode_action)

        # Simulation Tools Toolbar
        sim_toolbar = self.addToolBar("Simulation Tools")
        sim_toolbar.setObjectName("SimulationToolBar")
        sim_toolbar.setIconSize(icon_size)
        sim_toolbar.setToolButtonStyle(tb_style)
        # Python Sim controls
        sim_toolbar.addAction(self.start_py_sim_action)
        sim_toolbar.addAction(self.stop_py_sim_action)
        sim_toolbar.addAction(self.reset_py_sim_action)
        sim_toolbar.addSeparator()
        # MATLAB controls
        sim_toolbar.addAction(self.export_simulink_action) # Can be under a general "Export" or "MATLAB" group
        sim_toolbar.addAction(self.run_simulation_action)
        sim_toolbar.addAction(self.generate_code_action)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)

        # Tools Dock (Content created directly)
        self.tools_dock = QDockWidget("Tools", self)
        self.tools_dock.setObjectName("ToolsDock")
        self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_widget_main = QWidget()
        tools_widget_main.setObjectName("ToolsDockWidgetContents") # For specific QSS styling if needed
        tools_main_layout = QVBoxLayout(tools_widget_main)
        tools_main_layout.setSpacing(10); tools_main_layout.setContentsMargins(5,5,5,5)
        # Interaction Mode Group
        mode_group_box = QGroupBox("Interaction Modes")
        mode_layout = QVBoxLayout(); mode_layout.setSpacing(5)
        self.toolbox_select_button = QToolButton(); self.toolbox_select_button.setDefaultAction(self.select_mode_action)
        self.toolbox_add_state_button = QToolButton(); self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action)
        self.toolbox_transition_button = QToolButton(); self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action)
        self.toolbox_add_comment_button = QToolButton(); self.toolbox_add_comment_button.setDefaultAction(self.add_comment_mode_action)
        for btn in [self.toolbox_select_button, self.toolbox_add_state_button, self.toolbox_transition_button, self.toolbox_add_comment_button]:
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(18,18)); mode_layout.addWidget(btn)
        mode_group_box.setLayout(mode_layout); tools_main_layout.addWidget(mode_group_box)
        # Draggable Elements Group
        draggable_group_box = QGroupBox("Drag New Elements")
        draggable_layout = QVBoxLayout(); draggable_layout.setSpacing(5)
        drag_state_btn = DraggableToolButton(" State", "application/x-bsm-tool", "State")
        drag_state_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))
        drag_initial_state_btn = DraggableToolButton(" Initial State", "application/x-bsm-tool", "Initial State")
        drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt")) # Example icon
        drag_final_state_btn = DraggableToolButton(" Final State", "application/x-bsm-tool", "Final State")
        drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt")) # Example icon
        drag_comment_btn = DraggableToolButton(" Comment", "application/x-bsm-tool", "Comment")
        drag_comment_btn.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))
        for btn in [drag_state_btn, drag_initial_state_btn, drag_final_state_btn, drag_comment_btn]:
            btn.setIconSize(QSize(18,18)); draggable_layout.addWidget(btn)
        draggable_group_box.setLayout(draggable_layout); tools_main_layout.addWidget(draggable_group_box)
        tools_main_layout.addStretch() # Push groups to top
        self.tools_dock.setWidget(tools_widget_main)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.tools_dock.toggleViewAction())

        # Properties Dock (Content created directly)
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        properties_widget = QWidget()
        properties_layout = QVBoxLayout(properties_widget)
        properties_layout.setContentsMargins(5,5,5,5); properties_layout.setSpacing(5)
        self.properties_editor_label = QLabel("<i>No item selected.</i><br><small>Click an item to view/edit.</small>")
        self.properties_editor_label.setWordWrap(True); self.properties_editor_label.setTextFormat(Qt.RichText)
        self.properties_editor_label.setAlignment(Qt.AlignTop)
        self.properties_editor_label.setStyleSheet(f"padding: 5px; background-color: {COLOR_BACKGROUND_LIGHT}; border: 1px solid {COLOR_BORDER_MEDIUM};") # Basic styling
        properties_layout.addWidget(self.properties_editor_label, 1) # Label takes available space
        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"),"Edit Properties")
        self.properties_edit_button.setEnabled(False) # Disabled by default
        self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock)
        properties_layout.addWidget(self.properties_edit_button)
        self.properties_dock.setWidget(properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.properties_dock.toggleViewAction())

        # Log Dock (Content created directly)
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(5,5,5,5) # Minimal margins
        self.log_output = QTextEdit()
        self.log_output.setObjectName("LogOutputWidget") # For QSS styling
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)
        self.log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.log_dock.toggleViewAction())

        # Python Simulation Dock (QDockWidget instance created, content set later by _populate_dynamic_docks)
        self.py_sim_dock = QDockWidget("Python Simulation", self)
        self.py_sim_dock.setObjectName("PySimDock")
        self.py_sim_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock) # Add to right, will be tabified
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.py_sim_dock.toggleViewAction())

        # AI Chatbot Dock (QDockWidget instance created, content set later)
        self.ai_chatbot_dock = QDockWidget("AI Chatbot", self)
        self.ai_chatbot_dock.setObjectName("AIChatbotDock")
        self.ai_chatbot_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock) # Add to right, will be tabified
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.ai_chatbot_dock.toggleViewAction())

        # --- Standalone IDE Dock ---
        self._setup_ide_dock_widget() # Call helper to create IDE dock and its contents

        # Tabify docks: This should ideally happen AFTER their content widgets are set.
        # Moved to _populate_dynamic_docks.

    def _setup_ide_dock_widget(self):
        self.ide_dock = QDockWidget("Standalone Code IDE", self)
        self.ide_dock.setObjectName("IDEDock")
        self.ide_dock.setAllowedAreas(Qt.AllDockWidgetAreas) # Allow flexible placement

        ide_main_widget = QWidget()
        ide_main_layout = QVBoxLayout(ide_main_widget)
        ide_main_layout.setContentsMargins(0,0,0,0) # Toolbar will have its own margins
        ide_main_layout.setSpacing(0)

        # Toolbar for IDE
        ide_toolbar = QToolBar("IDE Tools")
        ide_toolbar.setIconSize(QSize(18,18))
        ide_toolbar.addAction(self.ide_new_file_action)
        ide_toolbar.addAction(self.ide_open_file_action)
        ide_toolbar.addAction(self.ide_save_file_action)
        ide_toolbar.addAction(self.ide_save_as_file_action)
        ide_toolbar.addSeparator()
        ide_toolbar.addAction(self.ide_run_script_action) # Add Run button
        ide_toolbar.addSeparator()
        self.ide_language_combo = QComboBox()
        self.ide_language_combo.addItems(["Python", "C/C++ (Arduino)", "C/C++ (Generic)", "Text"])
        self.ide_language_combo.setToolTip("Select language (syntax highlighting for Python & C/C++)")
        self.ide_language_combo.currentTextChanged.connect(self._on_ide_language_changed)
        ide_toolbar.addWidget(QLabel(" Language: "))
        ide_toolbar.addWidget(self.ide_language_combo)
        ide_toolbar.addSeparator()
        ide_toolbar.addAction(self.ide_analyze_action)


        ide_main_layout.addWidget(ide_toolbar)

        self.ide_code_editor = CodeEditor()
        self.ide_code_editor.setObjectName("StandaloneCodeEditor") # Different from ActionCodeEditor for potential styling
        self.ide_code_editor.setPlaceholderText("Create a new file or open an existing script...")
        self.ide_code_editor.textChanged.connect(self._on_ide_text_changed)
        ide_main_layout.addWidget(self.ide_code_editor, 1) # Code editor takes most space

        # Output console for IDE
        self.ide_output_console = QTextEdit()
        self.ide_output_console.setObjectName("IDEOutputConsole") # For QSS
        self.ide_output_console.setReadOnly(True)
        self.ide_output_console.setPlaceholderText("Script output will appear here...")
        self.ide_output_console.setFixedHeight(150) # Give it a reasonable default height
        ide_main_layout.addWidget(self.ide_output_console)

        self.ide_dock.setWidget(ide_main_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ide_dock) # Add to right by default
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.ide_dock.toggleViewAction())

        self._update_ide_save_actions_enable_state() # Init IDE save actions

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready") # General status
        self.status_bar.addWidget(self.status_label, 1) # Stretch factor of 1

        # Resource monitors (permanent widgets on the right)
        self.cpu_status_label = QLabel("CPU: --%"); self.cpu_status_label.setToolTip("CPU Usage"); self.cpu_status_label.setMinimumWidth(90); self.cpu_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.cpu_status_label)
        self.ram_status_label = QLabel("RAM: --%"); self.ram_status_label.setToolTip("RAM Usage"); self.ram_status_label.setMinimumWidth(90); self.ram_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.ram_status_label)
        self.gpu_status_label = QLabel("GPU: N/A"); self.gpu_status_label.setToolTip("GPU Usage (NVIDIA only, if pynvml installed)"); self.gpu_status_label.setMinimumWidth(130); self.gpu_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.gpu_status_label)

        # Simulation/Connectivity statuses
        self.py_sim_status_label = QLabel("PySim: Idle"); self.py_sim_status_label.setToolTip("Internal Python FSM Simulation Status."); self.py_sim_status_label.setMinimumWidth(100); self.py_sim_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.py_sim_status_label)
        self.matlab_status_label = QLabel("MATLAB: Initializing..."); self.matlab_status_label.setToolTip("MATLAB connection status."); self.matlab_status_label.setMinimumWidth(150); self.matlab_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.matlab_status_label)
        self.internet_status_label = QLabel("Internet: Init..."); self.internet_status_label.setToolTip("Internet connectivity. Checks periodically."); self.internet_status_label.setMinimumWidth(120); self.internet_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.internet_status_label)

        # Progress bar for long operations
        self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0,0); self.progress_bar.setVisible(False); self.progress_bar.setMaximumWidth(150); self.progress_bar.setTextVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self._update_ide_save_actions_enable_state() # Init IDE save actions

    def _init_resource_monitor(self):
        self.resource_monitor_thread = QThread(self) # Parent to main window for lifetime
        self.resource_monitor_worker = ResourceMonitorWorker(interval_ms=2000) # 2 sec interval
        self.resource_monitor_worker.moveToThread(self.resource_monitor_thread)

        # Connect signals and slots
        self.resource_monitor_worker.resourceUpdate.connect(self._update_resource_display)
        self.resource_monitor_thread.started.connect(self.resource_monitor_worker.start_monitoring)
        # Ensure worker is deleted when thread finishes to avoid resource leaks
        self.resource_monitor_thread.finished.connect(self.resource_monitor_worker.deleteLater)
        self.resource_monitor_thread.finished.connect(self.resource_monitor_thread.deleteLater) # Schedule thread for deletion too
        
        self.resource_monitor_thread.start()
        logger.info("Resource monitor thread initialized and started.")

    @pyqtSlot(float, float, float, str)
    def _update_resource_display(self, cpu_usage, ram_usage, gpu_util, gpu_name):
        if hasattr(self, 'cpu_status_label'): self.cpu_status_label.setText(f"CPU: {cpu_usage:.1f}%")
        if hasattr(self, 'ram_status_label'): self.ram_status_label.setText(f"RAM: {ram_usage:.1f}%")
        if hasattr(self, 'gpu_status_label'):
            if gpu_util == -1.0: self.gpu_status_label.setText(f"GPU: {gpu_name}") # N/A or pynvml N/A
            elif gpu_util == -2.0: self.gpu_status_label.setText(f"GPU: {gpu_name}") # Error fetching util
            elif gpu_util == -3.0: self.gpu_status_label.setText(f"GPU: {gpu_name}") # General monitor error
            else: self.gpu_status_label.setText(f"GPU: {gpu_util:.0f}% ({gpu_name})") # Valid reading

    @pyqtSlot(bool)
    def _handle_py_sim_state_changed_by_manager(self, is_running: bool):
        logger.debug(f"MW: PySim state changed by manager to: {is_running}")
        self.py_sim_active = is_running
        self._update_window_title() # Update window title (e.g., [PySim Running])
        self._update_py_sim_status_display() # Update status bar
        self._update_matlab_actions_enabled_state() # MATLAB ops usually disabled during PySim
        self._update_py_simulation_actions_enabled_state() # Update PySim control buttons

    @pyqtSlot(bool)
    def _handle_py_sim_global_ui_enable_by_manager(self, enable: bool):
        logger.debug(f"MW: Global UI enable requested by PySim manager: {enable}")
        is_editable = enable # If PySim running, diagram editing is disabled

        # Actions related to diagram editing
        diagram_editing_actions = [
            self.new_action, self.open_action, self.save_action, self.save_as_action,
            self.undo_action, self.redo_action, self.delete_action, self.select_all_action,
            self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action,
            self.auto_layout_action, self.validate_diagram_action, # Include new diagram actions
            self.export_simulink_action, self.export_plantuml_action, self.export_mermaid_action, # Export actions
        ]
        for action in diagram_editing_actions:
            if hasattr(action, 'setEnabled'): action.setEnabled(is_editable)

        # Enable/disable tools dock and properties edit button
        if hasattr(self, 'tools_dock'): self.tools_dock.setEnabled(is_editable)
        if hasattr(self, 'properties_edit_button'):
             self.properties_edit_button.setEnabled(is_editable and len(self.scene.selectedItems())==1)

        # Enable/disable item movability in the scene
        for item in self.scene.items():
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): # Only these are typically movable
                item.setFlag(QGraphicsItem.ItemIsMovable, is_editable and self.scene.current_mode == "select")

        # If UI is disabled (sim running), force select mode
        if not is_editable and self.scene.current_mode != "select":
            self.scene.set_mode("select")

        # Update other action states that depend on sim state
        self._update_matlab_actions_enabled_state()
        self._update_py_simulation_actions_enabled_state()


    def _add_fsm_data_to_scene(self, fsm_data: dict, clear_current_diagram: bool = False, original_user_prompt: str = "AI Generated FSM"):
        logger.info("MW: ADD_FSM_TO_SCENE clear_current_diagram=%s", clear_current_diagram)
        logger.debug("MW: Received FSM Data (states: %d, transitions: %d)",
                     len(fsm_data.get('states',[])), len(fsm_data.get('transitions',[])))

        if clear_current_diagram:
            if not self.on_new_file(silent=True): # This calls _clear_validation_highlights
                 logger.warning("MW: Clearing diagram cancelled by user (save prompt). Cannot add AI FSM.")
                 return
            logger.info("MW: Cleared diagram before AI generation.")
        else:
            self._clear_validation_highlights_on_modify() # Clear existing validation if not clearing diagram


        if not clear_current_diagram: # If adding to existing, wrap in undo macro
            self.undo_stack.beginMacro(f"Add AI FSM: {original_user_prompt[:30]}...")

        state_items_map = {} # To link transitions by name
        items_to_add_for_undo_command = [] # Collect items for single AddItemCommand if not clearing

        # --- Graphviz Auto-Layout ---
        layout_start_x, layout_start_y = 100, 100 # Default start position
        default_item_width, default_item_height = 120, 60
        GV_SCALE = 1.2 # Scale factor for Graphviz coordinates

        G = pgv.AGraph(directed=True, strict=False, rankdir='TB', ratio='auto', nodesep='0.75', ranksep='1.2 equally')
        for state_data in fsm_data.get('states', []):
            name = state_data.get('name')
            if name: G.add_node(name, label=name, width=str(default_item_width/72.0), height=str(default_item_height/72.0), shape='box', style='rounded')
        for trans_data in fsm_data.get('transitions', []):
            source, target = trans_data.get('source'), trans_data.get('target')
            if source and target and G.has_node(source) and G.has_node(target): G.add_edge(source, target, label=trans_data.get('event', ''))
            else: logger.warning("MW: Skipping Graphviz edge for AI FSM due to missing node(s): %s->%s", source, target)

        graphviz_positions = {}
        try:
            G.layout(prog="dot"); logger.debug("MW: Graphviz layout ('dot') for AI FSM successful.")
            raw_gv_pos = [{'name': n.name, 'x': float(n.attr['pos'].split(',')[0]), 'y': float(n.attr['pos'].split(',')[1])} for n in G.nodes() if 'pos' in n.attr]
            if raw_gv_pos:
                min_x_gv = min(p['x'] for p in raw_gv_pos); max_y_gv = max(p['y'] for p in raw_gv_pos) # Invert Y for Qt
                for p_gv in raw_gv_pos: graphviz_positions[p_gv['name']] = QPointF((p_gv['x'] - min_x_gv) * GV_SCALE + layout_start_x, (max_y_gv - p_gv['y']) * GV_SCALE + layout_start_y)
            else: logger.warning("MW: Graphviz - No valid positions extracted for AI FSM nodes.")
        except Exception as e:
            logger.error("MW: Graphviz layout error for AI FSM: %s. Falling back to grid.", str(e).strip() or "Unknown", exc_info=True)
            if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager:
                self.ai_chat_ui_manager._append_to_chat_display("System", f"Warning: AI FSM layout failed (Graphviz error). Using basic grid layout.")
            graphviz_positions = {} # Clear positions to trigger fallback grid layout
        # --- End Graphviz ---


        # Create State Items
        for i, state_data in enumerate(fsm_data.get('states', [])):
            name = state_data.get('name'); item_w, item_h = default_item_width, default_item_height
            if not name: logger.warning("MW: AI State data missing 'name'. Skipping."); continue
            
            # Get position from Graphviz or fallback to grid
            pos = graphviz_positions.get(name)
            pos_x, pos_y = (pos.x(), pos.y()) if pos else (layout_start_x + (i % 3) * (item_w + 150), layout_start_y + (i // 3) * (item_h + 100))
            
            try:
                state_item = GraphicsStateItem(pos_x, pos_y, item_w, item_h, name,
                    is_initial=state_data.get('is_initial', False), is_final=state_data.get('is_final', False),
                    color=state_data.get('properties', {}).get('color', state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG)),
                    action_language=state_data.get('action_language', DEFAULT_EXECUTION_ENV),
                    entry_action=state_data.get('entry_action', ""), during_action=state_data.get('during_action', ""), exit_action=state_data.get('exit_action', ""),
                    description=state_data.get('description', fsm_data.get('description', "") if i==0 else ""), # Use main FSM desc for first state
                    is_superstate=state_data.get('is_superstate', False), sub_fsm_data=state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}))
                items_to_add_for_undo_command.append(state_item); state_items_map[name] = state_item
            except Exception as e: logger.error("MW: Error creating AI GraphicsStateItem '%s': %s", name, e, exc_info=True)

        # Create Transition Items
        for trans_data in fsm_data.get('transitions', []):
            src_name, tgt_name = trans_data.get('source'), trans_data.get('target')
            if not src_name or not tgt_name: logger.warning("MW: AI Transition missing source/target. Skipping."); continue
            src_item, tgt_item = state_items_map.get(src_name), state_items_map.get(tgt_name)
            if src_item and tgt_item:
                try:
                    trans_item = GraphicsTransitionItem(src_item, tgt_item,
                        event_str=trans_data.get('event', ""), condition_str=trans_data.get('condition', ""),
                        action_language=trans_data.get('action_language', DEFAULT_EXECUTION_ENV),
                        action_str=trans_data.get('action', ""),
                        color=trans_data.get('properties', {}).get('color', trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT)), description=trans_data.get('description', ""))
                    ox, oy = trans_data.get('control_offset_x'), trans_data.get('control_offset_y')
                    if ox is not None and oy is not None: # Ensure offsets are numbers
                        try: trans_item.set_control_point_offset(QPointF(float(ox), float(oy)))
                        except ValueError: logger.warning("MW: Invalid AI control offsets for transition %s->%s.", src_name, tgt_name)
                    items_to_add_for_undo_command.append(trans_item)
                except Exception as e: logger.error("MW: Error creating AI GraphicsTransitionItem %s->%s: %s", src_name, tgt_name, e, exc_info=True)
            else: logger.warning("MW: Could not find source/target GraphicsStateItem for AI transition: %s->%s. Skipping.", src_name, tgt_name)

        # Create Comment Items
        max_y_items = max((item.scenePos().y() + item.boundingRect().height() for item in state_items_map.values() if item.scenePos()), default=layout_start_y) if state_items_map else layout_start_y
        for i, comment_data in enumerate(fsm_data.get('comments', [])):
            text = comment_data.get('text'); width = comment_data.get('width')
            if not text: continue # Skip empty comments
            # Position comments based on hints or fallback
            pos_x = comment_data.get('x', layout_start_x + i * (150 + 20)) # Basic grid for comments if no x,y
            pos_y = comment_data.get('y', max_y_items + 100) # Below states by default
            try:
                comment_item = GraphicsCommentItem(pos_x, pos_y, text)
                if width and isinstance(width, (int, float)) and width > 0 :
                    comment_item.setTextWidth(float(width))
                items_to_add_for_undo_command.append(comment_item)
            except Exception as e: logger.error("MW: Error creating AI GraphicsCommentItem: %s", e, exc_info=True)


        # Add items to scene
        if items_to_add_for_undo_command:
            if not clear_current_diagram: # Adding to existing, use undo commands for each item
                for item_to_add in items_to_add_for_undo_command:
                    item_type_name = type(item_to_add).__name__.replace("Graphics","").replace("Item","")
                    cmd_text = f"Add AI {item_type_name}" + (f": {item_to_add.text_label}" if hasattr(item_to_add, 'text_label') and item_to_add.text_label else "")
                    self.undo_stack.push(AddItemCommand(self.scene, item_to_add, cmd_text))
            else: # Cleared diagram, just add items directly (load_diagram_data style)
                for item_to_add in items_to_add_for_undo_command:
                     self.scene.addItem(item_to_add)

            logger.info("MW: Added %d AI-generated items to diagram.", len(items_to_add_for_undo_command))
            self.scene.set_dirty(True) # Mark scene as modified
            QTimer.singleShot(100, self._fit_view_to_new_ai_items) # Fit view after items are rendered
        else:
            logger.info("MW: No valid AI-generated items to add.")

        if not clear_current_diagram and items_to_add_for_undo_command: # End macro if it was started
            self.undo_stack.endMacro()
        elif not clear_current_diagram: # Ensure macro is ended even if no items added (edge case)
             self.undo_stack.endMacro()

        # Reinitialize simulation if it was active
        if self.py_sim_active and items_to_add_for_undo_command:
            logger.info("MW: Reinitializing Python simulation after adding AI FSM.")
            try:
                if self.py_sim_ui_manager:
                    self.py_sim_ui_manager.on_stop_py_simulation(silent=True) # Stop current
                    self.py_sim_ui_manager.on_start_py_simulation() # Start new with updated diagram
                    self.py_sim_ui_manager.append_to_action_log(["Python FSM Simulation reinitialized for new diagram from AI."])
            except FSMError as e:
                if self.py_sim_ui_manager:
                    self.py_sim_ui_manager.append_to_action_log([f"ERROR Re-initializing Sim after AI: {e}"])
                    self.py_sim_ui_manager.on_stop_py_simulation(silent=True) # Stop if re-init fails
        logger.debug("MW: ADD_FSM_TO_SCENE processing finished. Items involved: %d", len(items_to_add_for_undo_command))


    def _fit_view_to_new_ai_items(self):
        if not self.scene.items(): return
        items_bounds = self.scene.itemsBoundingRect()
        if self.view and not items_bounds.isNull():
            self.view.fitInView(items_bounds.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio) # Add padding
            logger.info("MW: View adjusted to AI generated items.")
        elif self.view and self.scene.sceneRect(): # Fallback if itemsBoundingRect is null but sceneRect exists
            self.view.centerOn(self.scene.sceneRect().center())


    def on_matlab_settings(self):
        dialog = MatlabSettingsDialog(matlab_connection=self.matlab_connection, parent=self)
        dialog.exec()
        logger.info("MATLAB settings dialog closed.")


    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems()
        html_content = ""
        edit_enabled = False
        item_type_tooltip = "item" # Default tooltip part

        if len(selected_items) == 1:
            item = selected_items[0]
            props = item.get_data() if hasattr(item, 'get_data') else {}
            item_type_name = type(item).__name__.replace("Graphics", "").replace("Item", "")
            item_type_tooltip = item_type_name.lower() # e.g., "state", "transition"
            edit_enabled = True

            # Helper to format text, especially for multi-line actions/descriptions
            def fmt(txt, max_chars=25):
                if not txt: return "<i>(none)</i>"
                txt_str = str(txt)
                first_line = txt_str.split('\n')[0] # Get first line only
                escaped_first_line = html.escape(first_line)
                ellipsis = "…" if len(first_line) > max_chars or '\n' in txt_str else ""
                return escaped_first_line[:max_chars] + ellipsis

            rows = "" # HTML table rows
            if isinstance(item, GraphicsStateItem):
                color_obj = QColor(props.get('color', COLOR_ITEM_STATE_DEFAULT_BG))
                # Determine text color for visibility against background
                color_style = f"background-color:{color_obj.name()}; color:{'black' if color_obj.lightnessF()>0.5 else 'white'}; padding:1px 4px; border-radius:2px;"
                rows += f"<tr><td><b>Name:</b></td><td>{html.escape(props.get('name', 'N/A'))}</td></tr>"
                rows += f"<tr><td><b>Initial/Final:</b></td><td>{'Yes' if props.get('is_initial') else 'No'} / {'Yes' if props.get('is_final') else 'No'}</td></tr>"
                if props.get('is_superstate'):
                    sub_states_count = len(props.get('sub_fsm_data',{}).get('states',[]))
                    rows += f"<tr><td><b>Superstate:</b></td><td>Yes ({sub_states_count} sub-state{'s' if sub_states_count != 1 else ''})</td></tr>"
                rows += f"<tr><td><b>Language:</b></td><td>{html.escape(props.get('action_language', DEFAULT_EXECUTION_ENV))}</td></tr>"
                rows += f"<tr><td><b>Color:</b></td><td><span style='{color_style}'>{html.escape(color_obj.name())}</span></td></tr>"
                for act_key in ['entry_action', 'during_action', 'exit_action']:
                    act_label = act_key.replace('_action','').capitalize()
                    rows += f"<tr><td><b>{act_label}:</b></td><td>{fmt(props.get(act_key, ''))}</td></tr>"
                if props.get('description'): rows += f"<tr><td colspan='2'><b>Desc:</b> {fmt(props.get('description'), 50)}</td></tr>"

            elif isinstance(item, GraphicsTransitionItem):
                color_obj = QColor(props.get('color', COLOR_ITEM_TRANSITION_DEFAULT))
                color_style = f"background-color:{color_obj.name()}; color:{'black' if color_obj.lightnessF()>0.5 else 'white'}; padding:1px 4px; border-radius:2px;"

                label_parts = []
                if props.get('event'): label_parts.append(html.escape(props.get('event')))
                if props.get('condition'): label_parts.append(f"[{html.escape(props.get('condition'))}]")
                if props.get('action'): label_parts.append(f"/{{{fmt(props.get('action'),15)}}}") # Use fmt for action
                full_label = " ".join(p for p in label_parts if p) or "<i>(No Label)</i>"

                rows += f"<tr><td><b>Label:</b></td><td style='font-size:8pt;'>{full_label}</td></tr>"
                rows += f"<tr><td><b>From/To:</b></td><td>{html.escape(props.get('source','N/A'))} → {html.escape(props.get('target','N/A'))}</td></tr>"
                rows += f"<tr><td><b>Language:</b></td><td>{html.escape(props.get('action_language', DEFAULT_EXECUTION_ENV))}</td></tr>"
                rows += f"<tr><td><b>Color:</b></td><td><span style='{color_style}'>{html.escape(color_obj.name())}</span></td></tr>"
                rows += f"<tr><td><b>Curve:</b></td><td>Bend={props.get('control_offset_x',0):.0f}, Shift={props.get('control_offset_y',0):.0f}</td></tr>"
                if props.get('description'): rows += f"<tr><td colspan='2'><b>Desc:</b> {fmt(props.get('description'), 50)}</td></tr>"

            elif isinstance(item, GraphicsCommentItem):
                rows += f"<tr><td colspan='2'><b>Text:</b> {fmt(props.get('text', ''), 60)}</td></tr>"
            else: # Fallback for unknown item types
                rows = "<tr><td>Unknown Item Type</td></tr>"
                item_type_name = "Unknown"

            # Construct final HTML content for the label
            html_content = f"""
                <div style='font-family:"Segoe UI",Arial;font-size:9pt;line-height:1.5;'>
                    <h4 style='margin:0 0 5px 0;padding:2px 0;color:{COLOR_ACCENT_PRIMARY};border-bottom:1px solid {COLOR_BORDER_LIGHT};'>
                        Type: {item_type_name}
                    </h4>
                    <table style='width:100%;border-collapse:collapse;'>{rows}</table>
                </div>"""
        elif len(selected_items) > 1:
            html_content = f"<i><b>{len(selected_items)} items selected.</b><br>Select a single item to view or edit its properties.</i>"
            item_type_tooltip = f"{len(selected_items)} items"
        else: # No items selected
            html_content = "<i>No item selected.</i><br><small>Click an item in the diagram or use the tools to add new elements.</small>"

        self.properties_editor_label.setText(html_content)
        self.properties_edit_button.setEnabled(edit_enabled)
        self.properties_edit_button.setToolTip(f"Edit properties of selected {item_type_tooltip}" if edit_enabled else "Select a single item to enable editing")


    def _on_edit_selected_item_properties_from_dock(self):
        selected = self.scene.selectedItems()
        if len(selected) == 1:
            self.scene.edit_item_properties(selected[0]) # Delegate to scene's method

    def _update_window_title(self):
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        ide_file_name = os.path.basename(self.current_ide_file_path) if self.current_ide_file_path else None

        sim_status_suffix = " [PySim Running]" if self.py_sim_active else ""
        ide_suffix = f" | IDE: {ide_file_name}{'*' if self.ide_editor_is_dirty else ''}" if ide_file_name else ""

        title = f"{APP_NAME} - {file_name}{sim_status_suffix}{ide_suffix}"
        self.setWindowTitle(title + "[*]") # [*] indicates modified status to Qt
        # Update main status bar label
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"File: {file_name}{' *' if self.isWindowModified() else ''} | PySim: {'Active' if self.py_sim_active else 'Idle'}")

    def _update_save_actions_enable_state(self):
        self.save_action.setEnabled(self.isWindowModified())
        # Save As is generally always enabled if there's a scene, or could depend on content.
        # For simplicity, let's enable if there's content or it's dirty.
        self.save_as_action.setEnabled(self.isWindowModified() or bool(self.scene.items()))


    def _update_ide_save_actions_enable_state(self):
        if hasattr(self, 'ide_save_file_action'):
            self.ide_save_file_action.setEnabled(self.ide_editor_is_dirty)
        if hasattr(self, 'ide_save_as_file_action'):
             self.ide_save_as_file_action.setEnabled(self.ide_code_editor is not None and bool(self.ide_code_editor.toPlainText()))

    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo())
        self.redo_action.setEnabled(self.undo_stack.canRedo())
        # Update text to show what will be undone/redone
        self.undo_action.setText(f"&Undo {self.undo_stack.undoText()}" if self.undo_stack.undoText() else "&Undo")
        self.redo_action.setText(f"&Redo {self.undo_stack.redoText()}" if self.undo_stack.redoText() else "&Redo")

    def _update_matlab_status_display(self, connected, message):
        text_color = COLOR_PY_SIM_STATE_ACTIVE.name() if connected else "#C62828" # Green if connected, Red if not
        status_text = f"MATLAB: {'Connected' if connected else 'Not Connected'}"
        tooltip_text = f"MATLAB Status: {message}"

        if hasattr(self, 'matlab_status_label'):
            self.matlab_status_label.setText(status_text)
            self.matlab_status_label.setToolTip(tooltip_text)
            self.matlab_status_label.setStyleSheet(f"font-weight:bold;padding:0 5px;color:{text_color};")

        # Log significant status changes
        if "Initializing" not in message or (connected and "Initializing" in message): # Avoid logging "Initializing..." repeatedly
            logging.info("MATLAB Connection Status: %s", message)

        self._update_matlab_actions_enabled_state() # Update actions based on new status


    def _update_matlab_actions_enabled_state(self):
        # MATLAB operations should be enabled if MATLAB is connected AND Python sim is NOT active
        can_run_matlab_ops = self.matlab_connection.connected and not self.py_sim_active

        if hasattr(self, 'export_simulink_action'): self.export_simulink_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'run_simulation_action'): self.run_simulation_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'generate_code_action'): self.generate_code_action.setEnabled(can_run_matlab_ops)
        # MATLAB settings should be accessible even if not connected, but not during PySim
        if hasattr(self, 'matlab_settings_action'): self.matlab_settings_action.setEnabled(not self.py_sim_active)

    def _start_matlab_operation(self, operation_name):
        logging.info("MATLAB Operation: '%s' starting...", operation_name)
        if hasattr(self, 'status_label'): self.status_label.setText(f"Running MATLAB: {operation_name}...")
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False) # Disable UI during operation

    def _finish_matlab_operation(self):
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(False)
        if hasattr(self, 'status_label'): self.status_label.setText("Ready") # Reset general status
        self.set_ui_enabled_for_matlab_op(True) # Re-enable UI
        logging.info("MATLAB Operation: Finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        """Enables/disables major UI elements during long MATLAB operations."""
        if hasattr(self, 'menuBar'): self.menuBar().setEnabled(enabled)
        # Disable toolbars
        for child in self.findChildren(QToolBar):
            child.setEnabled(enabled)
        # Disable central widget (diagram view)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)

        # Disable/enable dock widgets. Be specific if some should remain active.
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock", "IDEDock"]:
            dock = self.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(enabled)
        
        # Crucially, update PySim actions as they might be affected by MATLAB op status too
        self._update_py_simulation_actions_enabled_state()


    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation() # Handles UI re-enable and progress bar
        logging.log(logging.INFO if success else logging.ERROR, "MATLAB Result (ModelGen/Sim): %s", message)
        if success:
            if "Model generation" in message and data: # If model generation, data is the path
                self.last_generated_model_path = data
                QMessageBox.information(self, "Simulink Model Generation", f"Model generated successfully:\n{data}")
            elif "Simulation" in message: # If simulation
                QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
            # Could add more specific handling based on `data` or `message` if needed
        else: # Failure
            QMessageBox.warning(self, "MATLAB Operation Failed", message)

    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation()
        logging.log(logging.INFO if success else logging.ERROR, "MATLAB Code Gen Result: %s", message)
        if success and output_dir:
            msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Information); msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText); abs_dir = os.path.abspath(output_dir)
            # Make the path a clickable link
            msg_box.setText(f"Code generation completed successfully.<br>Generated files are in: <a href='file:///{abs_dir}'>{abs_dir}</a>")
            msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction) # Allow link clicking
            open_btn = msg_box.addButton("Open Directory", QMessageBox.ActionRole); msg_box.addButton(QMessageBox.Ok)
            msg_box.exec()
            if msg_box.clickedButton() == open_btn:
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(abs_dir)):
                    logging.error("Error opening directory: %s", abs_dir)
                    QMessageBox.warning(self, "Error Opening Directory", f"Could not automatically open the directory:\n{abs_dir}")
        elif not success:
            QMessageBox.warning(self, "Code Generation Failed", message)

    def _prompt_save_if_dirty(self) -> bool:
        if not self.isWindowModified(): # Check main window's modified status (tied to scene's dirty flag)
            return True
        if self.py_sim_active: # Don't prompt if simulation is active, just warn
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving or opening a new file.")
            return False

        file_desc = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes?",
                                     f"The diagram '{file_desc}' has unsaved changes. Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save) # Default to Save

        if reply == QMessageBox.Save:
            return self.on_save_file() # Returns True if save successful, False otherwise
        elif reply == QMessageBox.Cancel:
            return False # User cancelled
        return True # User chose Discard

    def on_new_file(self, silent=False):
        if not silent and not self._prompt_save_if_dirty():
            return False # User cancelled or save failed
        
        self._clear_validation_highlights_on_modify() # Clear any existing validation visuals

        if self.py_sim_ui_manager: # Stop simulation if active
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        self.scene.clear() # Clear all items from the scene
        self.scene.setSceneRect(0,0,6000,4500) # Reset scene rect
        self.current_file_path = None
        self.last_generated_model_path = None
        self.undo_stack.clear() # Clear undo history for new file
        self.scene.set_dirty(False) # New file is not dirty
        self.setWindowModified(False) # Update window modified status
        self._update_window_title() # Update title to "Untitled"
        self._update_undo_redo_actions_enable_state()
        if not silent:
            logging.info("New diagram created.")
            if hasattr(self, 'status_label'): self.status_label.setText("New diagram. Ready.")
        self.view.resetTransform() # Reset view zoom/pan
        self.view.centerOn(self.scene.sceneRect().center()) # Center view on new scene
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger() # Ensure select mode is active
        return True


    def on_open_file(self):
        if not self._prompt_save_if_dirty():
            return # User cancelled or save failed
        
        self._clear_validation_highlights_on_modify()

        if self.py_sim_ui_manager: # Stop simulation if active
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)

        if file_path:
            if self._load_from_path(file_path):
                self.current_file_path = file_path
                self.last_generated_model_path = None # Reset path of last MATLAB model
                self.undo_stack.clear() # Clear undo stack for newly opened file
                self.scene.set_dirty(False) # File is clean after load
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                logging.info("Opened file: %s", file_path)
                if hasattr(self, 'status_label'): self.status_label.setText(f"Opened: {os.path.basename(file_path)}")
                # Fit view to content after loading
                bounds = self.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio) # Add padding
                else: # If diagram is empty, reset view
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())
            else:
                QMessageBox.critical(self, "Error Opening File", f"Could not load the diagram from:\n{file_path}")
                logging.error("Failed to open file: %s", file_path)

    def _load_from_path(self, file_path):
        self._clear_validation_highlights_on_modify()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Basic validation of loaded data structure
            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data or 'comments' not in data:
                logging.error("Invalid BSM file format: %s. Missing required keys (states, transitions, comments).", file_path)
                return False
            self.scene.load_diagram_data(data) # Delegate to scene's load method
            return True
        except json.JSONDecodeError as e:
            logging.error("JSONDecodeError loading %s: %s", file_path, e)
            return False
        except Exception as e: # Catch other potential errors during file reading or scene loading
            logging.error("Unexpected error loading %s: %s", file_path, e, exc_info=True)
            return False

    def on_save_file(self) -> bool:
        if not self.current_file_path: # If no current path, use Save As
            return self.on_save_file_as()
        return self._save_to_path(self.current_file_path)

    def on_save_file_as(self) -> bool:
        default_filename = os.path.basename(self.current_file_path or "untitled" + FILE_EXTENSION)
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()

        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As",
                                                   os.path.join(start_dir, default_filename),
                                                   FILE_FILTER)
        if file_path:
            # Ensure correct extension
            if not file_path.lower().endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION

            if self._save_to_path(file_path):
                self.current_file_path = file_path # Update current path after successful Save As
                return True
        return False

    def _save_to_path(self, file_path) -> bool:
        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving.")
            return False
        
        self._clear_validation_highlights_on_modify()

        # Use QSaveFile for safer saving (atomic operation)
        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text): # Open in text mode for JSON
            error_str = save_file.errorString()
            logging.error("Failed to open QSaveFile for %s: %s", file_path, error_str)
            QMessageBox.critical(self, "Save Error", f"Could not open file for saving:\n{error_str}")
            return False

        try:
            diagram_data = self.scene.get_diagram_data() # Get data from scene
            json_data_str = json.dumps(diagram_data, indent=4, ensure_ascii=False) # Pretty print JSON
            bytes_written = save_file.write(json_data_str.encode('utf-8')) # Write as UTF-8 bytes

            if bytes_written == -1: # Error during write
                 error_str = save_file.errorString()
                 logging.error("Error writing to QSaveFile %s: %s", file_path, error_str)
                 QMessageBox.critical(self, "Save Error", f"Could not write data to file:\n{error_str}")
                 save_file.cancelWriting() # Important: cancel on failure
                 return False

            if not save_file.commit(): # Finalize write operation
                error_str = save_file.errorString()
                logging.error("Failed to commit QSaveFile for %s: %s", file_path, error_str)
                QMessageBox.critical(self, "Save Error", f"Could not finalize saving file:\n{error_str}")
                return False

            logging.info("Successfully saved diagram to: %s", file_path)
            if hasattr(self, 'status_label'): self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            self.scene.set_dirty(False) # Mark scene as clean
            self.setWindowModified(False) # Update window modified status
            self._update_window_title() # Update title to remove asterisk
            return True
        except Exception as e: # Catch other errors during data getting or JSON dump
            logging.error("Unexpected error during save to %s: %s", file_path, e, exc_info=True)
            QMessageBox.critical(self, "Save Error", f"An unexpected error occurred during saving:\n{e}")
            save_file.cancelWriting() # Ensure QSaveFile is cancelled on exception
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
        
        self._clear_validation_highlights_on_modify()

        # Dialog for model name and output directory
        dialog = QDialog(self)
        dialog.setWindowTitle("Export to Simulink")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp, "->M"))
        layout = QFormLayout(dialog)
        layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)

        # Suggest model name based on current file name
        base_name = os.path.splitext(os.path.basename(self.current_file_path or "BSM_Model"))[0]
        # Sanitize for MATLAB variable naming rules (starts with letter, alphanumeric or underscore)
        default_model_name = "".join(c if c.isalnum() or c=='_' else '_' for c in base_name)
        if not default_model_name or not default_model_name[0].isalpha():
            default_model_name = "Mdl_" + default_model_name if default_model_name else "Mdl_MyStateMachine"
        default_model_name = default_model_name.replace('-','_') # Replace hyphens

        name_edit = QLineEdit(default_model_name)
        layout.addRow("Simulink Model Name:", name_edit)

        # Suggest output directory based on current file path or home
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
            if not model_name or not output_dir: # Basic validation
                QMessageBox.warning(self, "Input Error", "Model name and output directory are required.")
                return
            # MATLAB model name validation
            if not model_name[0].isalpha() or not all(c.isalnum() or c=='_' for c in model_name):
                QMessageBox.warning(self, "Invalid Model Name", "Simulink model name must start with a letter and contain only alphanumeric characters or underscores.")
                return
            try: # Ensure output directory exists
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create output directory:\n{e}")
                return

            diagram_data = self.scene.get_diagram_data()
            if not diagram_data['states']: # Cannot export empty diagram
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
        self._clear_validation_highlights_on_modify()

        # Allow user to select the .slx model file
        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model to Simulate", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return # User cancelled

        self.last_generated_model_path = model_path # Remember for next time
        # Get simulation time from user
        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Enter simulation stop time (seconds):", 10.0, 0.001, 86400.0, 3)
        if not ok: return # User cancelled

        self._start_matlab_operation(f"Running Simulink simulation for '{os.path.basename(model_path)}'")
        self.matlab_connection.run_simulation(model_path, sim_time)

    def on_generate_code(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "Please configure MATLAB path in Settings.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before generating code.")
            return
        self._clear_validation_highlights_on_modify()

        # User selects model file
        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model for Code Generation", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path # Remember for next time

        # Dialog for code generation options
        dialog = QDialog(self); dialog.setWindowTitle("Code Generation Options"); dialog.setWindowIcon(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"))
        layout = QFormLayout(dialog); layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)
        lang_combo = QComboBox(); lang_combo.addItems(["C", "C++"]); lang_combo.setCurrentText("C++") # Default to C++
        layout.addRow("Target Language:", lang_combo)

        output_dir_edit = QLineEdit(os.path.dirname(model_path)) # Default to model's directory
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
            try: # Ensure directory exists
                os.makedirs(output_dir_base, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create output directory:\n{e}")
                return

            self._start_matlab_operation(f"Generating {language} code for '{os.path.basename(model_path)}'")
            self.matlab_connection.generate_code(model_path, language, output_dir_base)

    def _get_bundled_file_path(self, filename: str) -> str | None:
        """Attempts to find a file, prioritizing bundled location (_MEIPASS)."""
        # Check if running in a PyInstaller bundle
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Path when bundled by PyInstaller
            base_path = sys._MEIPASS
        elif getattr(sys, 'frozen', False): # Other frozen (e.g. cx_Freeze)
             base_path = os.path.dirname(sys.executable)
        else:
            # Path when running from source
            base_path = os.path.dirname(os.path.abspath(__file__))

        # Define common locations for bundled resources relative to base_path
        possible_subdirs = ['', 'docs', 'resources', 'examples', 
                            # PyInstaller often puts project structure inside _internal
                            '_internal/bsm_designer_project/docs', 
                            '_internal/bsm_designer_project/examples']

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
        self._clear_validation_highlights_on_modify()

        example_path = self._get_bundled_file_path(filename)
        if example_path and os.path.exists(example_path):
            if self._load_from_path(example_path):
                self.current_file_path = example_path # Treat example as a regular file once opened
                self.last_generated_model_path = None
                self.undo_stack.clear()
                self.scene.set_dirty(False) # Example file is clean on open
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
        if not self._prompt_ide_save_if_dirty(): # Check IDE first
            event.ignore()
            return

        if not self._prompt_save_if_dirty(): # Then check main diagram
            event.ignore()
            return
        
        self._clear_validation_highlights_on_modify() 

        if self.py_sim_ui_manager: # Stop simulation if active
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        if self.internet_check_timer and self.internet_check_timer.isActive():
            self.internet_check_timer.stop()
            logger.debug("Internet check timer stopped.")

        if self.ai_chatbot_manager:
            logger.debug("Stopping AI chatbot manager...")
            self.ai_chatbot_manager.stop_chatbot()
            logger.debug("AI chatbot manager stopped.")

        # Stop resource monitor thread
        if self.resource_monitor_thread and self.resource_monitor_thread.isRunning():
            logger.info("Stopping resource monitor worker and thread...")
            if self.resource_monitor_worker:
                # Signal worker to stop its loop and perform cleanup (like NVML shutdown)
                # QueuedConnection allows worker's event loop to process this.
                QMetaObject.invokeMethod(self.resource_monitor_worker, "stop_monitoring", Qt.QueuedConnection)
                logger.debug("stop_monitoring invoked on resource_monitor_worker (queued).")

            self.resource_monitor_thread.quit() # Request thread to exit event loop
            logger.debug("resource_monitor_thread.quit() called.")

            # Wait for thread to finish. Simplified wait time.
            # Worker's stop_monitoring should be quick.
            wait_time_ms = 500 # Reduced from complex calculation
            if not self.resource_monitor_thread.wait(wait_time_ms):
                logger.warning(f"Resource monitor thread did not quit gracefully after {wait_time_ms}ms. Terminating.")
                self.resource_monitor_thread.terminate() # Force terminate
                if not self.resource_monitor_thread.wait(200): # Wait for termination
                    logger.error("Resource monitor thread failed to terminate forcefully.")
            else:
                logger.info("Resource monitor thread stopped gracefully.")
        
        # Clean up references after thread is confirmed stopped or terminated
        self.resource_monitor_worker = None
        self.resource_monitor_thread = None
        logger.debug("Resource monitor worker and thread references cleared.")

        if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads:
            logging.info("Closing application. %d MATLAB processes initiated by this session may still be running in the background if not completed.", len(self.matlab_connection._active_threads))

        logger.info("Application closeEvent accepted.")
        event.accept()


    def _init_internet_status_check(self):
        self.internet_check_timer.timeout.connect(self._run_internet_check_job)
        self.internet_check_timer.start(15000) # Check every 15 seconds
        QTimer.singleShot(100, self._run_internet_check_job) # Initial check soon after start

    def _run_internet_check_job(self):
        current_status = False
        status_detail = "Checking..."
        try:
            s = socket.create_connection(("8.8.8.8", 53), timeout=1.5) # Google DNS, common check
            s.close()
            current_status = True
            status_detail = "Connected"
        except socket.timeout:
            status_detail = "Disconnected (Timeout)"
        except (socket.gaierror, OSError): # Covers host not found, network unreachable
            status_detail = "Disconnected (Net Issue)"

        # Update only if status changed or first time
        if current_status != self._internet_connected or self._internet_connected is None:
            self._internet_connected = current_status
            self._update_internet_status_display(current_status, status_detail)

    def _update_ai_features_enabled_state(self, is_online_and_key_present: bool):
        """Enables or disables AI-related UI elements based on connectivity and API key."""
        if hasattr(self, 'ask_ai_to_generate_fsm_action'):
            self.ask_ai_to_generate_fsm_action.setEnabled(is_online_and_key_present)
        if hasattr(self, 'clear_ai_chat_action'): # Clearing history interacts with worker
            self.clear_ai_chat_action.setEnabled(is_online_and_key_present)
        # openai_settings_action (Gemini settings) should always be enabled to allow key entry.

        # AI Chat UI elements in the dock
        if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager:
            if self.ai_chat_ui_manager.ai_chat_send_button:
                self.ai_chat_ui_manager.ai_chat_send_button.setEnabled(is_online_and_key_present)
            if self.ai_chat_ui_manager.ai_chat_input:
                self.ai_chat_ui_manager.ai_chat_input.setEnabled(is_online_and_key_present)
                # Update placeholder text based on state
                if not is_online_and_key_present:
                    if self.ai_chatbot_manager and not self.ai_chatbot_manager.api_key:
                        self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText("AI disabled: API Key required.")
                    elif not self._internet_connected:
                        self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText("AI disabled: Internet connection required.")
                else:
                    self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText("Type your message to the AI...")

        # IDE Analyze with AI action
        if hasattr(self, 'ide_analyze_action') and hasattr(self, 'ide_language_combo'):
            current_ide_lang = self.ide_language_combo.currentText()
            # Enable for Python/C++ if AI is ready
            can_analyze_ide = (current_ide_lang == "Python" or current_ide_lang.startswith("C/C++")) and is_online_and_key_present
            self.ide_analyze_action.setEnabled(can_analyze_ide)
            tooltip = "Analyze the current code with AI"
            if not is_online_and_key_present:
                tooltip += " (Requires Internet & Gemini API Key)"
            elif not (current_ide_lang == "Python" or current_ide_lang.startswith("C/C++")):
                 tooltip += " (Best for Python or C/C++)"
            self.ide_analyze_action.setToolTip(tooltip)

    def _update_internet_status_display(self, is_connected: bool, message_detail: str):
        full_status_text = f"Internet: {message_detail}"
        if hasattr(self, 'internet_status_label'):
            self.internet_status_label.setText(full_status_text)
            # Tooltip with more info (e.g., what's being checked)
            host_for_tooltip = socket.getfqdn('8.8.8.8') if is_connected else '8.8.8.8' # Show FQDN if resolved
            self.internet_status_label.setToolTip(f"{full_status_text} (Checks connection to {host_for_tooltip}:53)")
            # Color coding for status
            text_color = COLOR_PY_SIM_STATE_ACTIVE.name() if is_connected else "#D32F2F" # Green for connected, Red for disconnected
            self.internet_status_label.setStyleSheet(f"padding:0 5px;color:{text_color};")

        logging.debug("Internet Status Update: %s", message_detail)

        # Determine if AI features should be active
        key_present = self.ai_chatbot_manager is not None and bool(self.ai_chatbot_manager.api_key)
        ai_ready = is_connected and key_present

        # Notify AI Chatbot Manager of online status
        if hasattr(self.ai_chatbot_manager, 'set_online_status'):
            self.ai_chatbot_manager.set_online_status(is_connected)

        # Update UI elements related to AI
        self._update_ai_features_enabled_state(ai_ready)

        # Update AI Chatbot Dock's specific status label
        if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager:
            if not key_present:
                self.ai_chat_ui_manager.update_status_display("Status: API Key required. Configure in Settings.")
            elif not is_connected:
                self.ai_chat_ui_manager.update_status_display("Status: Offline. AI features unavailable.")
            # If key_present and is_connected, the manager's own statusUpdate will set "Ready" or "Thinking"


    def _update_py_sim_status_display(self):
        if hasattr(self, 'py_sim_status_label'):
            if self.py_sim_active and self.py_fsm_engine: # Check if engine exists
                current_state_name = self.py_fsm_engine.get_current_state_name()
                self.py_sim_status_label.setText(f"PySim: Active ({html.escape(current_state_name)})")
                self.py_sim_status_label.setStyleSheet(f"font-weight:bold;padding:0 5px;color:{COLOR_PY_SIM_STATE_ACTIVE.name()};")
            else:
                self.py_sim_status_label.setText("PySim: Idle")
                self.py_sim_status_label.setStyleSheet("font-weight:normal;padding:0 5px;") # Reset style

    def _update_py_simulation_actions_enabled_state(self):
        # Check if a MATLAB operation is running (indicated by progress bar visibility)
        is_matlab_op_running = False
        if hasattr(self, 'progress_bar') and self.progress_bar: # Ensure progress_bar exists
            is_matlab_op_running = self.progress_bar.isVisible()

        # Simulation can start if not already active and no MATLAB op is running
        sim_can_start = not self.py_sim_active and not is_matlab_op_running
        # Simulation can be controlled (stop/reset/step) if active and no MATLAB op
        sim_can_be_controlled = self.py_sim_active and not is_matlab_op_running

        if hasattr(self, 'start_py_sim_action'): self.start_py_sim_action.setEnabled(sim_can_start)
        if hasattr(self, 'stop_py_sim_action'): self.stop_py_sim_action.setEnabled(sim_can_be_controlled)
        if hasattr(self, 'reset_py_sim_action'): self.reset_py_sim_action.setEnabled(sim_can_be_controlled)

        # Also update controls within the PySimDock via its UI manager
        if self.py_sim_ui_manager:
            self.py_sim_ui_manager._update_internal_controls_enabled_state()

    # --- IDE Dock Methods ---
    def _prompt_ide_save_if_dirty(self) -> bool:
        if not self.ide_editor_is_dirty or not self.ide_code_editor: # No need to prompt if not dirty or no editor
            return True

        file_desc = os.path.basename(self.current_ide_file_path) if self.current_ide_file_path else "Untitled Script"
        reply = QMessageBox.question(self, "Save IDE Script?",
                                     f"The script '{file_desc}' in the IDE has unsaved changes. Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save) # Default to Save
        if reply == QMessageBox.Save:
            return self.on_ide_save_file() # Returns True on success
        elif reply == QMessageBox.Cancel:
            return False # User cancelled
        return True # User chose Discard

    def on_ide_new_file(self):
        if not self._prompt_ide_save_if_dirty(): # Prompt before clearing
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
        if not self._prompt_ide_save_if_dirty(): # Prompt before opening new
            return

        start_dir = os.path.dirname(self.current_ide_file_path) if self.current_ide_file_path else QDir.homePath()
        # Filter for common script/text files
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Script File", start_dir,
                                                   "Python Files (*.py);;C/C++ Files (*.c *.cpp *.h *.hpp *.ino);;Text Files (*.txt);;All Files (*)")
        if file_path and self.ide_code_editor:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.ide_code_editor.setPlainText(f.read())
                self.current_ide_file_path = file_path
                self.ide_editor_is_dirty = False # Clean after load
                self._update_ide_save_actions_enable_state()
                self._update_window_title()
                if self.ide_output_console: self.ide_output_console.clear() # Clear output for new file
                logger.info("IDE: Opened script: %s", file_path)
                # Auto-detect language from extension
                if hasattr(self, 'ide_language_combo'):
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext == ".py": self.ide_language_combo.setCurrentText("Python")
                    elif ext in [".ino", ".c", ".cpp", ".h", ".hpp"]: self.ide_language_combo.setCurrentText("C/C++ (Arduino)") # Or generic C++
                    else: self.ide_language_combo.setCurrentText("Text") # Default for others

            except Exception as e:
                QMessageBox.critical(self, "Error Opening Script", f"Could not load script from {file_path}:\n{e}")
                logger.error("IDE: Failed to open script %s: %s", file_path, e)

    def _save_ide_to_path(self, file_path) -> bool:
        if not self.ide_code_editor: return False
        try:
            # Use QSaveFile for atomic saves
            save_file = QSaveFile(file_path)
            if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
                QMessageBox.critical(self, "Error Saving Script", f"Could not open file for saving:\n{save_file.errorString()}")
                return False
            
            save_file.write(self.ide_code_editor.toPlainText().encode('utf-8'))
            if not save_file.commit():
                QMessageBox.critical(self, "Error Saving Script", f"Could not commit save to file:\n{save_file.errorString()}")
                return False

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
        if not self.current_ide_file_path: # No current path, so Save As
            return self.on_ide_save_as_file()
        if self.ide_editor_is_dirty: # Only save if actually dirty
             return self._save_ide_to_path(self.current_ide_file_path)
        return True # Not dirty, considered successful

    def on_ide_save_as_file(self) -> bool:
        default_filename = os.path.basename(self.current_ide_file_path or "untitled_script.py")
        start_dir = os.path.dirname(self.current_ide_file_path) if self.current_ide_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Script As", os.path.join(start_dir, default_filename),
                                                   "Python Files (*.py);;C/C++ Files (*.c *.cpp *.h *.hpp *.ino);;Text Files (*.txt);;All Files (*)")
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
    def _on_ide_language_changed(self, language: str):
        if self.ide_code_editor:
            self.ide_code_editor.set_language(language) # Update syntax highlighter

        # Enable/disable Run button based on language
        if self.ide_run_script_action:
            is_python = (language == "Python")
            self.ide_run_script_action.setEnabled(is_python)
            self.ide_run_script_action.setToolTip("Run the current Python script in the editor" if is_python else "Run is currently only supported for Python scripts")
        
        # Update AI Analyze action based on language and AI readiness
        if self.ide_analyze_action:
            key_present = self.ai_chatbot_manager is not None and bool(self.ai_chatbot_manager.api_key)
            ai_ready_for_analysis = key_present and self._internet_connected is True
            can_analyze_lang = (language == "Python" or language.startswith("C/C++"))
            
            self.ide_analyze_action.setEnabled(can_analyze_lang and ai_ready_for_analysis)
            tooltip = "Analyze the current code with AI"
            if not ai_ready_for_analysis: tooltip += " (Requires Internet & Gemini API Key)"
            elif not can_analyze_lang: tooltip += " (Best for Python or C/C++)"
            self.ide_analyze_action.setToolTip(tooltip)

        logger.info(f"IDE: Language changed to {language}.")


    @pyqtSlot()
    def on_ide_run_python_script(self):
        if not self.ide_code_editor or not self.ide_output_console:
            logger.error("IDE: Code editor or output console not available for running script.")
            return

        if self.ide_language_combo.currentText() != "Python":
            QMessageBox.information(self, "Run Script", "Currently, only Python scripts can be run directly from the IDE.")
            return

        code_to_run = self.ide_code_editor.toPlainText()
        if not code_to_run.strip(): # Check if there's any code
            self.ide_output_console.setHtml("<i>No Python code to run.</i>")
            return

        # --- Security Warning ---
        reply = QMessageBox.warning(self, "Security Warning: Python Script Execution",
                                      "You are about to run a Python script directly within the application's process. "
                                      "This script will have access to your system resources, including file system and network.\n\n"
                                      "<b>Only run scripts from trusted sources.</b> Malicious code could cause harm.\n\n"
                                      "Do you want to proceed with execution?",
                                      QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if reply == QMessageBox.Cancel:
            self.ide_output_console.append("<i style='color:orange;'>Execution cancelled by user due to security warning.</i>")
            self.ide_output_console.ensureCursorVisible()
            return
        # --- End Security Warning ---

        self.ide_output_console.clear() # Clear previous output
        self.ide_output_console.append(f"<i style='color:grey;'>Running Python script at {QTime.currentTime().toString('hh:mm:ss')}...</i><hr>")

        # Prepare a restricted environment
        script_globals = {"__name__": "__ide_script__"} # Basic globals
        script_locals = {} # Locals for the script

        stdout_capture = io.StringIO() # Capture stdout
        stderr_capture = io.StringIO() # Capture stderr

        try:
            # Redirect stdout and stderr for the duration of exec
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                exec(code_to_run, script_globals, script_locals) # Execute the script

            # Append captured output to the console
            self.ide_output_console.append(html.escape(stdout_capture.getvalue()))
            err_output = stderr_capture.getvalue()
            if err_output: # If there's anything in stderr, display it as error
                self.ide_output_console.append(f"<pre style='color:red;'>{html.escape(err_output)}</pre>")
            self.ide_output_console.append("<hr><i style='color:grey;'>Execution finished.</i>")
        except Exception as e:
            import traceback # Import only if needed
            self.ide_output_console.append(f"<pre style='color:red;'><b>Error during execution:</b>\n{html.escape(str(e))}\n--- Traceback ---\n{html.escape(traceback.format_exc())}</pre>")
            self.ide_output_console.append("<hr><i style='color:red;'>Execution failed.</i>")
        finally:
            stdout_capture.close()
            stderr_capture.close()
            self.ide_output_console.ensureCursorVisible() # Scroll to end

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

        # Display message in IDE console and send to main AI chat
        self.ide_output_console.append(f"<i style='color:grey;'>Sending code to AI for analysis ({selected_language})... (Response will appear in main AI Chat window)</i><hr>")
        if self.ai_chat_ui_manager:
            self.ai_chat_ui_manager._append_to_chat_display("IDE", f"Requesting AI analysis for the current script ({selected_language}).")
        self.ai_chatbot_manager.send_message(prompt)


    def log_message(self, level_str: str, message: str):
        """Main window's central logging method, delegates to Python's logging."""
        level = getattr(logging, level_str.upper(), logging.INFO) # Convert string level to logging level
        logger.log(level, message) # Use the main application logger

    # --- New Auto-Layout Method ---
    @pyqtSlot()
    def on_auto_layout(self):
        logger.info("User triggered Auto-Layout.")
        self._clear_validation_highlights_on_modify()

        if not self.scene.items():
            QMessageBox.information(self, "Empty Diagram", "Nothing to layout.")
            return
        if self.py_sim_active: # Don't layout if simulation is running
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before auto-layout.")
            return

        diagram_data = self.scene.get_diagram_data()
        if not diagram_data.get('states'): # Auto-layout primarily works on states
            QMessageBox.information(self, "No States", "Auto-layout requires states in the diagram.")
            return

        state_items_map = {item.text_label: item for item in self.scene.items() if isinstance(item, GraphicsStateItem)}

        # Create Graphviz graph
        G = pgv.AGraph(directed=True, strict=False, rankdir='TB', ratio='auto', nodesep='1.0', ranksep='1.5 equally')
        default_item_width, default_item_height = 120, 60 # Default sizes for Graphviz nodes (in points)

        # Add nodes to Graphviz graph
        for state_data in diagram_data.get('states', []):
            name = state_data.get('name')
            item = state_items_map.get(name)
            item_w = item.rect().width() if item else default_item_width
            item_h = item.rect().height() if item else default_item_height
            if name:
                G.add_node(name, label=name, width=str(item_w/72.0), height=str(item_h/72.0), shape='box', style='rounded', fixedsize='true')

        # Add edges to Graphviz graph
        for trans_data in diagram_data.get('transitions', []):
            source, target = trans_data.get('source'), trans_data.get('target')
            if source and target and G.has_node(source) and G.has_node(target):
                G.add_edge(source, target)

        graphviz_positions = {} # Store {name: QPointF}
        GV_SCALE = 1.3 # Scale factor from Graphviz points to scene coordinates
        layout_start_x, layout_start_y = 70, 70 # Top-left offset in scene

        try:
            G.layout(prog="dot") # Use "dot" layout engine (good for hierarchies)
            raw_gv_pos = [{'name': n.name, 'x': float(n.attr['pos'].split(',')[0]), 'y': float(n.attr['pos'].split(',')[1])}
                          for n in G.nodes() if 'pos' in n.attr] # Extract positions
            if raw_gv_pos:
                min_x_gv = min(p['x'] for p in raw_gv_pos) # Normalize coordinates
                max_y_gv = max(p['y'] for p in raw_gv_pos) # Invert Y for Qt scene

                for p_gv in raw_gv_pos:
                    scene_x = (p_gv['x'] - min_x_gv) * GV_SCALE + layout_start_x
                    scene_y = (max_y_gv - p_gv['y']) * GV_SCALE + layout_start_y 
                    graphviz_positions[p_gv['name']] = QPointF(scene_x, scene_y)
            else:
                raise RuntimeError("Graphviz did not return positions.")
        except Exception as e:
            logger.error(f"Auto-layout failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Layout Error", f"Auto-layout failed using Graphviz: {e}\n\nMake sure Graphviz 'dot' command is in your system PATH.\nAttempting a basic grid layout as fallback.")
            # Fallback to basic grid layout if Graphviz fails
            graphviz_positions.clear()
            states = diagram_data.get('states', [])
            num_states = len(states)
            cols = int(math.sqrt(num_states)) + 1 if num_states > 0 else 1
            for i, state_data in enumerate(states):
                name = state_data.get('name')
                row, col = divmod(i, cols)
                scene_x = layout_start_x + col * (default_item_width + 100) # Spacing
                scene_y = layout_start_y + row * (default_item_height + 80)
                graphviz_positions[name] = QPointF(scene_x, scene_y)


        # Apply new positions via UndoCommand
        moved_items_data_for_command = []
        for item_name, new_pos_qpoint in graphviz_positions.items():
            item = state_items_map.get(item_name)
            if item:
                old_pos = item.pos()
                if (new_pos_qpoint - old_pos).manhattanLength() > 1.0: # Only if moved significantly
                    moved_items_data_for_command.append((item, old_pos, new_pos_qpoint))

        if moved_items_data_for_command:
            cmd = MoveItemsCommand(moved_items_data_for_command, "Auto-Layout")
            self.undo_stack.push(cmd)
            self.scene.update() # Ensure scene redraws
            logger.info("Diagram auto-layout applied.")
            # Fit view to new layout
            self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
        else:
            QMessageBox.information(self, "Auto-Layout", "Layout applied, but no significant changes were made to item positions.")

    # --- New Validation Methods ---
    @pyqtSlot()
    def on_validate_diagram(self):
        logger.info("User triggered Diagram Validation.")
        self._clear_validation_highlights_on_modify()

        if not self.scene.items():
            QMessageBox.information(self, "Empty Diagram", "Nothing to validate.")
            return

        issues = self.scene.validate_diagram() # Call scene's validation method
        if not issues:
            QMessageBox.information(self, "Validation Complete", "No issues found in the diagram.")
            self.scene.clear_validation_highlights() # Ensure any previous highlights are gone
        else:
            self.show_validation_issues_dialog(issues)
            self.scene.highlight_validation_issues(issues) # Tell scene to highlight

    def show_validation_issues_dialog(self, issues):
        dialog = QDialog(self)
        dialog.setWindowTitle("Diagram Validation Issues")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "Vld"))
        dialog.setMinimumWidth(450); dialog.setMinimumHeight(300)
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        list_widget.setAlternatingRowColors(True)
        for issue_type, message, item_ref_or_name in issues:
            item_widget = QListWidgetItem(f"[{issue_type.upper()}] {message}")
            if issue_type == "error":
                item_widget.setForeground(QColor("red"))
            elif issue_type == "warning":
                item_widget.setForeground(QColor("darkorange"))
            # Store reference or name to allow jumping to item
            if item_ref_or_name:
                item_widget.setData(Qt.UserRole, item_ref_or_name)
            list_widget.addItem(item_widget)

        list_widget.itemDoubleClicked.connect(self._on_validation_issue_selected)
        layout.addWidget(list_widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec_()

    def _on_validation_issue_selected(self, list_item: QListWidgetItem):
        """Handles double-click on a validation issue: selects and shows the item."""
        item_ref = list_item.data(Qt.UserRole)
        if isinstance(item_ref, QGraphicsItem) and item_ref.scene() == self.scene:
            self.scene.clearSelection()
            item_ref.setSelected(True)
            self.view.ensureVisible(item_ref, 50, 50) # Ensure item is visible with margin
        elif isinstance(item_ref, str): # If only name was stored (e.g., for duplicate name error)
            found_item = self.scene.get_state_by_name(item_ref)
            if found_item:
                self.scene.clearSelection()
                found_item.setSelected(True)
                self.view.ensureVisible(found_item, 50, 50)

    def _clear_validation_highlights_on_modify(self, *_args): # Accept potential args from signals
        """Clears validation highlights when the diagram is modified."""
        if hasattr(self.scene, 'clear_validation_highlights'):
            self.scene.clear_validation_highlights()


    @pyqtSlot()
    def on_export_plantuml(self):
        if self.py_sim_active: QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before exporting."); return
        if not self.scene.items(): QMessageBox.information(self, "Empty Diagram", "Cannot export an empty diagram."); return
        self._clear_validation_highlights_on_modify()

        default_filename = "diagram.puml"
        diagram_title = "FSM"
        if self.current_file_path:
            base = os.path.splitext(os.path.basename(self.current_file_path))[0]
            default_filename = base + ".puml"
            diagram_title = base
        
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Diagram as PlantUML",
                                                   os.path.join(start_dir, default_filename),
                                                   "PlantUML Files (*.puml *.plantuml *.pu);;All Files (*)")
        if file_path:
            diagram_data = self.scene.get_diagram_data()
            try:
                plantuml_content = generate_plantuml_text(diagram_data, diagram_name=diagram_title)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(plantuml_content)
                logger.info(f"Diagram exported as PlantUML to: {file_path}")
                QMessageBox.information(self, "PlantUML Export Successful", f"Diagram exported as PlantUML to:\n{file_path}")
            except Exception as e:
                logger.error(f"Error generating or writing PlantUML for {file_path}: {e}", exc_info=True)
                QMessageBox.critical(self, "PlantUML Export Error", f"Could not generate or save PlantUML text:\n{e}")

    @pyqtSlot()
    def on_export_mermaid(self):
        if self.py_sim_active: QMessageBox.warning(self, "Simulation Active", "Please stop simulation first."); return
        if not self.scene.items(): QMessageBox.information(self, "Empty Diagram", "Nothing to export."); return
        self._clear_validation_highlights_on_modify()

        default_filename = os.path.splitext(os.path.basename(self.current_file_path or "diagram"))[0] + ".md"
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getSaveFileName(self, "Export as Mermaid Diagram", os.path.join(start_dir, default_filename), "Mermaid/Markdown Files (*.mmd *.mermaid *.md);;All Files (*)")
        if not file_path: return

        diagram_data = self.scene.get_diagram_data()
        diagram_title = os.path.splitext(os.path.basename(self.current_file_path or "FSM_Diagram"))[0]
        try:
            mermaid_content = generate_mermaid_text(diagram_data, diagram_title=diagram_title)
            with open(file_path, 'w', encoding='utf-8') as f: f.write(mermaid_content)
            logger.info(f"Diagram exported as Mermaid to: {file_path}")
            QMessageBox.information(self, "Mermaid Export Successful", f"Diagram exported as Mermaid to:\n{file_path}")
        except Exception as e:
            logger.error(f"Error generating or writing Mermaid for {file_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Mermaid Export Error", f"Could not generate or save Mermaid text:\n{e}")


if __name__ == '__main__':
    # Enable High DPI scaling for better visuals on high-resolution displays
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    import traceback # Ensure traceback is imported for IDE script execution error handling

    # Ensure dependencies/icons directory exists for QSS (e.g., for QComboBox arrow)
    app_dir = os.path.dirname(os.path.abspath(__file__))
    deps_icons_dir = os.path.join(app_dir, "dependencies", "icons")
    if not os.path.exists(deps_icons_dir):
        try:
            os.makedirs(deps_icons_dir, exist_ok=True)
            print(f"Info: Created directory for QSS icons: {deps_icons_dir}")
        except OSError as e: # Catch potential permission errors, etc.
            print(f"Warning: Could not create directory {deps_icons_dir}: {e}")


    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET_GLOBAL) # Apply global stylesheet
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())