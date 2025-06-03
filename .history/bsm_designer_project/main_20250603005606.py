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
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
from code_editor import CodeEditor
from fsm_simulator import FSMSimulator, FSMError
from ai_chatbot import AIChatbotManager, AIStatus, AIChatUIManager
from dialogs import (MatlabSettingsDialog, FindItemDialog)
from matlab_integration import MatlabConnection
from config import (
    APP_VERSION, APP_NAME, FILE_EXTENSION, FILE_FILTER, STYLE_SHEET_GLOBAL,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_STATE_DEFAULT_BORDER, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG,
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_PRIMARY_LIGHT, COLOR_BACKGROUND_APP, COLOR_BACKGROUND_DIALOG,
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
from utils import get_standard_icon
from ui_py_simulation_manager import PySimulationUIManager
from c_code_generator import generate_c_code_files


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

        if not worker_thread:
            logger.error("ResourceMonitorWorker: CRITICAL - Worker is not associated with a QThread.")
            self.finished_signal.emit()
            return

        loop_count = 0
        while not worker_thread.isInterruptionRequested() and not self._stop_requested:
            loop_count += 1
            if loop_count % 50 == 0:
                logger.debug(f"ResourceMonitorWorker: Loop iteration {loop_count}, InterruptionRequested: {worker_thread.isInterruptionRequested()}, StopRequested: {self._stop_requested}")

            current_loop_time = QTime.currentTime().msecsSinceStartOfDay()

            if (current_loop_time - last_data_emit_time) >= self.data_collection_interval_ms or last_data_emit_time == 0:
                if worker_thread.isInterruptionRequested() or self._stop_requested:
                    logger.debug("ResourceMonitorWorker: Interruption/stop detected before emitting resourceUpdate.")
                    break
                try:
                    cpu_usage = psutil.cpu_percent(interval=None)
                    ram_percent = psutil.virtual_memory().percent
                    gpu_util = -1.0
                    gpu_name_to_emit = self._gpu_name_cache

                    if self._nvml_initialized and self._gpu_handle:
                        try:
                            gpu_info = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                            gpu_util = float(gpu_info.gpu)
                        except pynvml.NVMLError as e:
                            logger.warning(f"NVML error getting GPU util: {e}. Re-attempting init if needed.")
                            gpu_util = -2.0
                            gpu_name_to_emit = f"NVML Read Err (Code: {e.value})" if hasattr(e, 'value') else "NVML Read Err"
                            self._nvml_initialized = False
                            self._attempt_nvml_init(from_worker_loop=True)
                        except Exception as e_gen:
                            logger.error(f"Unexpected error getting GPU util: {e_gen}")
                            gpu_util = -3.0
                            gpu_name_to_emit = "GPU Mon. Err"
                    elif PYNVML_AVAILABLE and not self._nvml_initialized:
                        self._attempt_nvml_init(from_worker_loop=True)

                    if not (worker_thread.isInterruptionRequested() or self._stop_requested):
                        self.resourceUpdate.emit(cpu_usage, ram_percent, gpu_util, gpu_name_to_emit)
                    last_data_emit_time = current_loop_time
                except Exception as e:
                    logger.error(f"ResourceMonitorWorker: Error in data collection: {e}", exc_info=False)
                    if not (worker_thread.isInterruptionRequested() or self._stop_requested):
                         self.resourceUpdate.emit(-1.0, -1.0, -3.0, "Data Error")

            inner_loop_checks = int(self.data_collection_interval_ms / self.WORKER_LOOP_CHECK_INTERVAL_MS) + 1
            if inner_loop_checks <= 0: inner_loop_checks = 1

            for _i in range(inner_loop_checks):
                if worker_thread.isInterruptionRequested() or self._stop_requested:
                    break
                QThread.msleep(self.WORKER_LOOP_CHECK_INTERVAL_MS)

            if worker_thread.isInterruptionRequested() or self._stop_requested:
                logger.debug("ResourceMonitorWorker: Exiting main while loop due to interruption/stop request.")
                break

        logger.info(f"ResourceMonitorWorker: _monitor_resources loop EXITED (Interruption: {worker_thread.isInterruptionRequested()}, StopFlag: {self._stop_requested}). Emitting finished_signal.")
        self.finished_signal.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - Untitled [*]")

        self.current_file_path = None
        self.last_generated_model_path = None
        self.undo_stack = QUndoStack(self)
        self.scene = DiagramScene(self.undo_stack, self)

        self.matlab_connection = MatlabConnection()
        self.ai_chatbot_manager = AIChatbotManager(self)

        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False

        self.ide_code_editor: CodeEditor | None = None
        self.current_ide_file_path: str | None = None
        self.ide_output_console: QTextEdit | None = None
        self.ide_run_script_action: QAction | None = None
        self.ide_analyze_action: QAction | None = None
        self.ide_editor_is_dirty = False

        self.find_item_dialog: FindItemDialog | None = None
        
        self._dock_property_editors = {} 
        self._current_edited_item_in_dock = None

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

        self.py_sim_ui_manager = PySimulationUIManager(self)
        self.ai_chat_ui_manager = AIChatUIManager(self)

        self._populate_dynamic_docks()
        self._connect_signals()

        self._internet_connected: bool | None = None
        self.internet_check_timer = QTimer(self)
        self.resource_monitor_worker: ResourceMonitorWorker | None = None
        self.resource_monitor_thread: QThread | None = None
        self._init_resource_monitor()
        self._init_internet_status_check()

        self._set_status_label_object_names()
        self._update_ui_element_states()

        QTimer.singleShot(0, lambda: self.on_new_file(silent=True))

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

    def _set_status_label_object_names(self):
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
        if self.py_sim_ui_manager and hasattr(self, 'py_sim_dock') and self.py_sim_dock:
            py_sim_contents_widget = self.py_sim_ui_manager.create_dock_widget_contents()
            self.py_sim_dock.setWidget(py_sim_contents_widget)
        else:
            logger.error("Could not populate Python Simulation Dock: manager or dock missing.")

        if self.ai_chat_ui_manager and hasattr(self, 'ai_chatbot_dock') and self.ai_chatbot_dock:
            ai_chat_contents_widget = self.ai_chat_ui_manager.create_dock_widget_contents()
            self.ai_chatbot_dock.setWidget(ai_chat_contents_widget)
            if hasattr(self.ai_chat_ui_manager, 'ai_chat_status_label') and self.ai_chat_ui_manager.ai_chat_status_label:
                self.ai_chat_ui_manager.ai_chat_status_label.setObjectName("AIChatStatusLabel")
        else:
            logger.error("Could not populate AI Chatbot Dock: manager or dock missing.")

        docks_to_tabify = [
            (self.properties_dock, self.ai_chatbot_dock),
            (self.ai_chatbot_dock, self.py_sim_dock),
            (self.py_sim_dock, getattr(self, 'ide_dock', None)),
            (self.log_dock, self.problems_dock)
        ]
        for dock1_ref, dock2_ref in docks_to_tabify:
            if dock1_ref and dock2_ref:
                try:
                    self.tabifyDockWidget(dock1_ref, dock2_ref)
                except Exception as e: 
                    logger.error(f"Error tabifying docks {getattr(dock1_ref, 'objectName', lambda: 'N/A')()} and {getattr(dock2_ref, 'objectName', lambda: 'N/A')()}: {e}")

            else:
                obj_name1 = getattr(dock1_ref, 'objectName', lambda: 'N/A')()
                obj_name2 = getattr(dock2_ref, 'objectName', lambda: 'N/A')()
                logger.warning(f"Skipping tabify for docks: {obj_name1} and {obj_name2} as one or both might be missing.")


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
        self.generate_c_code_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "CGen"), "Generate &Basic C Code...", self, triggered=self.on_generate_c_code)
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
        self.generate_matlab_code_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "CdeM"), "Generate &Code (C/C++ via MATLAB)...", self, triggered=self.on_generate_matlab_code)
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

        self.find_item_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "Find"), "&Find Item...", self, shortcut=QKeySequence.Find, statusTip="Find an FSM element", triggered=self.on_show_find_item_dialog)
        logger.debug(f"MW: AI actions created. Settings: {self.openai_settings_action}, Clear: {self.clear_ai_chat_action}, Generate: {self.ask_ai_to_generate_fsm_action}")


    def _create_menus(self):
        menu_bar = self.menuBar(); file_menu = menu_bar.addMenu("&File"); file_menu.addAction(self.new_action); file_menu.addAction(self.open_action)
        example_menu = file_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ex"), "Open E&xample"); self.open_example_traffic_action = example_menu.addAction("Traffic Light FSM", lambda: self._open_example_file("traffic_light.bsm")); self.open_example_toggle_action = example_menu.addAction("Simple Toggle FSM", lambda: self._open_example_file("simple_toggle.bsm"))
        
        export_menu = file_menu.addMenu("E&xport") 
        export_menu.addAction(self.export_simulink_action)
        export_menu.addAction(self.generate_c_code_action) 

        file_menu.addAction(self.save_action); file_menu.addAction(self.save_as_action); file_menu.addSeparator()
        file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        
        edit_menu = menu_bar.addMenu("&Edit"); edit_menu.addAction(self.undo_action); edit_menu.addAction(self.redo_action); edit_menu.addSeparator(); edit_menu.addAction(self.delete_action); edit_menu.addAction(self.select_all_action); edit_menu.addSeparator(); edit_menu.addAction(self.find_item_action); edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Mode"),"Interaction Mode"); mode_menu.addAction(self.select_mode_action); mode_menu.addAction(self.add_state_mode_action); mode_menu.addAction(self.add_transition_mode_action); mode_menu.addAction(self.add_comment_mode_action); edit_menu.addSeparator()
        align_distribute_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogDetailedView, "AD"), "Align & Distribute"); align_menu = align_distribute_menu.addMenu("Align"); align_menu.addAction(self.align_left_action); align_menu.addAction(self.align_center_h_action); align_menu.addAction(self.align_right_action); align_menu.addSeparator(); align_menu.addAction(self.align_top_action); align_menu.addAction(self.align_middle_v_action); align_menu.addAction(self.align_bottom_action)
        distribute_menu = align_distribute_menu.addMenu("Distribute"); distribute_menu.addAction(self.distribute_h_action); distribute_menu.addAction(self.distribute_v_action)
        
        sim_menu = menu_bar.addMenu("&Simulation"); py_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_MediaPlay, "PyS"), "Python Simulation (Internal)"); py_sim_menu.addAction(self.start_py_sim_action); py_sim_menu.addAction(self.stop_py_sim_action); py_sim_menu.addAction(self.reset_py_sim_action); sim_menu.addSeparator()
        matlab_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_ComputerIcon, "M"), "MATLAB/Simulink"); matlab_sim_menu.addAction(self.run_simulation_action); matlab_sim_menu.addAction(self.generate_matlab_code_action); matlab_sim_menu.addSeparator(); matlab_sim_menu.addAction(self.matlab_settings_action)
        
        self.view_menu = menu_bar.addMenu("&View"); self.view_menu.addAction(self.zoom_in_action); self.view_menu.addAction(self.zoom_out_action); self.view_menu.addAction(self.reset_zoom_action); self.view_menu.addSeparator(); self.view_menu.addAction(self.zoom_to_selection_action); self.view_menu.addAction(self.fit_diagram_action); self.view_menu.addSeparator()
        snap_menu = self.view_menu.addMenu("Snapping"); snap_menu.addAction(self.snap_to_grid_action); snap_menu.addAction(self.snap_to_objects_action)
        self.show_snap_guidelines_action = QAction("Show Dynamic Snap Guidelines", self, checkable=True, statusTip="Show/hide dynamic alignment guidelines during drag")
        self.show_snap_guidelines_action.setChecked(self.scene._show_dynamic_snap_guidelines if hasattr(self.scene, '_show_dynamic_snap_guidelines') else True); self.show_snap_guidelines_action.triggered.connect(self.on_toggle_show_snap_guidelines); snap_menu.addAction(self.show_snap_guidelines_action); self.view_menu.addSeparator()
        
        tools_menu = menu_bar.addMenu("&Tools"); ide_menu = tools_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogDetailedView, "IDE"), "Standalone Code IDE"); ide_menu.addAction(self.ide_new_file_action); ide_menu.addAction(self.ide_open_file_action); ide_menu.addAction(self.ide_save_file_action); ide_menu.addAction(self.ide_save_as_file_action); ide_menu.addSeparator(); ide_menu.addAction(self.ide_run_script_action); ide_menu.addAction(self.ide_analyze_action)
        
        ai_menu = menu_bar.addMenu("&AI Assistant"); ai_menu.addAction(self.ask_ai_to_generate_fsm_action); ai_menu.addAction(self.clear_ai_chat_action); ai_menu.addSeparator(); ai_menu.addAction(self.openai_settings_action)
        help_menu = menu_bar.addMenu("&Help"); help_menu.addAction(self.quick_start_action); help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(22,22); tb_style = Qt.ToolButtonIconOnly
        file_toolbar = self.addToolBar("File"); file_toolbar.setObjectName("FileToolBar"); file_toolbar.setIconSize(icon_size); file_toolbar.setToolButtonStyle(tb_style); file_toolbar.addAction(self.new_action); file_toolbar.addAction(self.open_action); file_toolbar.addAction(self.save_action)
        edit_toolbar = self.addToolBar("Edit"); edit_toolbar.setObjectName("EditToolBar"); edit_toolbar.setIconSize(icon_size); edit_toolbar.setToolButtonStyle(tb_style); edit_toolbar.addAction(self.undo_action); edit_toolbar.addAction(self.redo_action); edit_toolbar.addSeparator(); edit_toolbar.addAction(self.delete_action); edit_toolbar.addAction(self.find_item_action)
        tools_tb = self.addToolBar("Interaction Tools"); tools_tb.setObjectName("ToolsToolBar"); tools_tb.setIconSize(icon_size); tools_tb.setToolButtonStyle(tb_style); tools_tb.addAction(self.select_mode_action); tools_tb.addAction(self.add_state_mode_action); tools_tb.addAction(self.add_transition_mode_action); tools_tb.addAction(self.add_comment_mode_action)
        
        code_gen_export_toolbar = self.addToolBar("Code Generation & Export")
        code_gen_export_toolbar.setObjectName("CodeGenExportToolBar")
        code_gen_export_toolbar.setIconSize(icon_size)
        code_gen_export_toolbar.setToolButtonStyle(tb_style)
        code_gen_export_toolbar.addAction(self.export_simulink_action)
        code_gen_export_toolbar.addAction(self.generate_matlab_code_action)
        code_gen_export_toolbar.addAction(self.generate_c_code_action)
        
        sim_toolbar = self.addToolBar("Simulation Tools"); sim_toolbar.setObjectName("SimulationToolBar"); sim_toolbar.setIconSize(icon_size); sim_toolbar.setToolButtonStyle(tb_style); sim_toolbar.addAction(self.start_py_sim_action); sim_toolbar.addAction(self.stop_py_sim_action); sim_toolbar.addAction(self.reset_py_sim_action); sim_toolbar.addSeparator(); sim_toolbar.addAction(self.run_simulation_action)
        
        view_toolbar = self.addToolBar("View Tools"); view_toolbar.setObjectName("ViewToolBar"); view_toolbar.setIconSize(icon_size); view_toolbar.setToolButtonStyle(tb_style); view_toolbar.addAction(self.zoom_in_action); view_toolbar.addAction(self.zoom_out_action); view_toolbar.addAction(self.reset_zoom_action); view_toolbar.addSeparator(); view_toolbar.addAction(self.zoom_to_selection_action); view_toolbar.addAction(self.fit_diagram_action)
        align_toolbar = self.addToolBar("Alignment & Distribution"); align_toolbar.setObjectName("AlignDistributeToolBar"); align_toolbar.setIconSize(icon_size); align_toolbar.setToolButtonStyle(tb_style); align_toolbar.addAction(self.align_left_action); align_toolbar.addAction(self.align_center_h_action); align_toolbar.addAction(self.align_right_action); align_toolbar.addSeparator(); align_toolbar.addAction(self.align_top_action); align_toolbar.addAction(self.align_middle_v_action); align_toolbar.addAction(self.align_bottom_action); align_toolbar.addSeparator(); align_toolbar.addAction(self.distribute_h_action); align_toolbar.addAction(self.distribute_v_action)


    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)
        
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
        
        self.properties_dock = QDockWidget("Item Properties", self); self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock_widget_main = QWidget()
        self.properties_dock_main_layout = QVBoxLayout(self.properties_dock_widget_main)
        self.properties_dock_main_layout.setContentsMargins(8,8,8,8)
        self.properties_dock_main_layout.setSpacing(6)
        self.properties_placeholder_label = QLabel("<i>Select a single item to view/edit its properties.</i>"); self.properties_placeholder_label.setObjectName("PropertiesLabel"); self.properties_placeholder_label.setWordWrap(True); self.properties_placeholder_label.setTextFormat(Qt.RichText); self.properties_placeholder_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.properties_dock_main_layout.addWidget(self.properties_placeholder_label)
        self.properties_editor_container = QWidget(); self.properties_editor_layout = QFormLayout(self.properties_editor_container); self.properties_editor_layout.setContentsMargins(0,0,0,0); self.properties_editor_layout.setSpacing(8); self.properties_dock_main_layout.addWidget(self.properties_editor_container); self.properties_editor_container.setVisible(False)
        self.properties_dock_main_layout.addStretch(1)
        self.properties_apply_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton, "Apply"), "Apply Changes"); self.properties_apply_button.setEnabled(False); self.properties_apply_button.clicked.connect(self._on_apply_dock_properties)
        self.properties_revert_button = QPushButton(get_standard_icon(QStyle.SP_DialogCancelButton, "Revert"), "Revert"); self.properties_revert_button.setEnabled(False); self.properties_revert_button.clicked.connect(self._on_revert_dock_properties)
        self.properties_edit_dialog_button = QPushButton(get_standard_icon(QStyle.SP_FileDialogDetailedView, "AdvEdit"), "Advanced Edit..."); self.properties_edit_dialog_button.setToolTip("Open full properties dialog"); self.properties_edit_dialog_button.setEnabled(False); self.properties_edit_dialog_button.clicked.connect(self._on_edit_selected_item_properties_from_dock_button)
        button_layout_props_dock = QHBoxLayout(); button_layout_props_dock.addWidget(self.properties_revert_button); button_layout_props_dock.addStretch(); button_layout_props_dock.addWidget(self.properties_apply_button)
        self.properties_dock_main_layout.addLayout(button_layout_props_dock)
        self.properties_dock_main_layout.addWidget(self.properties_edit_dialog_button)
        self.properties_dock.setWidget(self.properties_dock_widget_main); self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)

        self.log_dock = QDockWidget("Application Log", self); self.log_dock.setObjectName("LogDock")
        log_widget = QWidget(); log_layout = QVBoxLayout(log_widget); log_layout.setContentsMargins(0,0,0,0); self.log_output = QTextEdit(); self.log_output.setObjectName("LogOutputWidget"); self.log_output.setReadOnly(True); log_layout.addWidget(self.log_output); self.log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock); self.log_dock.setVisible(True)

        self.problems_dock = QDockWidget("Validation Issues", self); self.problems_dock.setObjectName("ProblemsDock")
        self.problems_list_widget = QListWidget(); self.problems_list_widget.itemDoubleClicked.connect(self.on_problem_item_double_clicked)
        self.problems_dock.setWidget(self.problems_list_widget); self.addDockWidget(Qt.BottomDockWidgetArea, self.problems_dock); self.problems_dock.setVisible(True)

        self.py_sim_dock = QDockWidget("Python Simulation", self); self.py_sim_dock.setObjectName("PySimDock"); self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock); self.py_sim_dock.setVisible(False)
        self.ai_chatbot_dock = QDockWidget("AI Assistant", self); self.ai_chatbot_dock.setObjectName("AIChatbotDock"); self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock); self.ai_chatbot_dock.setVisible(False)
        self._setup_ide_dock_widget();
        
        if hasattr(self, 'ide_dock'): self.ide_dock.setVisible(False)

        if hasattr(self, 'view_menu'): 
            self.view_menu.addAction(self.tools_dock.toggleViewAction())
            self.view_menu.addAction(self.properties_dock.toggleViewAction())
            self.view_menu.addAction(self.log_dock.toggleViewAction())
            self.view_menu.addAction(self.problems_dock.toggleViewAction())
            self.view_menu.addAction(self.py_sim_dock.toggleViewAction())
            self.view_menu.addAction(self.ai_chatbot_dock.toggleViewAction())
            if hasattr(self, 'ide_dock'): self.view_menu.addAction(self.ide_dock.toggleViewAction())

        self._load_and_display_templates()


    def _create_status_bar(self):
        self.status_bar = QStatusBar(self); self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready"); self.status_bar.addWidget(self.status_label, 1) 
        self.zoom_status_label = QLabel("Zoom: 100%"); self.zoom_status_label.setMinimumWidth(80); self.zoom_status_label.setAlignment(Qt.AlignCenter); self.status_bar.addPermanentWidget(self.zoom_status_label)
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
        self.resource_monitor_thread.start()
        logger.info("Resource monitor thread initialized and started.")


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


    def _load_and_display_templates(self):
        if hasattr(self, 'template_buttons_layout') and self.template_buttons_layout is not None:
            while self.template_buttons_layout.count():
                child = self.template_buttons_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        else:
            logger.warning("MainWindow: template_buttons_layout not found. Cannot clear/load templates.")
            return

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

        for template_info in templates_to_load:
            icon = QIcon()
            if template_info.get("icon_resource"):
                icon = QIcon(template_info["icon_resource"])
            if icon.isNull():
                icon = get_standard_icon(QStyle.SP_FileDialogContentsView, "Tmpl")

            template_btn = DraggableToolButton(
                template_info["name"],
                MIME_TYPE_BSM_TEMPLATE,
                template_info["data_json_str"]
            )
            template_btn.setIcon(icon)
            template_btn.setToolTip(template_info.get("description", template_info["name"]))
            self.template_buttons_layout.addWidget(template_btn)

        self.template_buttons_layout.addStretch(1)


    @pyqtSlot(list)
    def update_problems_dock(self, issues_with_items: list):
        if not hasattr(self, 'problems_list_widget') or self.problems_list_widget is None:
            logger.warning("MainWindow.update_problems_dock: self.problems_list_widget is not yet initialized. Update deferred.")
            return

        self.problems_list_widget.clear()
        if issues_with_items:
            for issue_msg, item_ref in issues_with_items:
                list_item_widget = QListWidgetItem(str(issue_msg))
                if item_ref:
                    list_item_widget.setData(Qt.UserRole, item_ref)
                self.problems_list_widget.addItem(list_item_widget)

            self.problems_dock.setWindowTitle(f"Validation Issues ({len(issues_with_items)})")
            if self.problems_dock.isHidden() and len(issues_with_items) > 0:
                self.problems_dock.show()
                self.problems_dock.raise_()
        else:
            self.problems_list_widget.addItem("No validation issues found.")
            self.problems_dock.setWindowTitle("Validation Issues")


    @pyqtSlot(QListWidgetItem)
    def on_problem_item_double_clicked(self, list_item: QListWidgetItem):
        item_ref = list_item.data(Qt.UserRole)
        if item_ref and isinstance(item_ref, QGraphicsItem) and item_ref.scene() == self.scene:
            self.focus_on_item(item_ref)
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
        if hasattr(self, 'properties_edit_dialog_button'): 
             self.properties_edit_dialog_button.setEnabled(is_editable and len(self.scene.selectedItems())==1)

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

    @pyqtSlot()
    def on_matlab_settings(self):
        dialog = MatlabSettingsDialog(matlab_connection=self.matlab_connection, parent=self)
        dialog.exec()
        logger.info("MATLAB settings dialog closed.")

    def _clear_dock_editors(self):
        if hasattr(self, 'properties_editor_layout'):
            while self.properties_editor_layout.count():
                child_layout_item = self.properties_editor_layout.takeAt(0) 
                if child_layout_item:
                    if child_layout_item.widget():
                        child_layout_item.widget().deleteLater()
                    elif child_layout_item.label(): # QFormLayout rows have labels
                         child_layout_item.label().deleteLater()
        if hasattr(self, '_dock_property_editors'):
            self._dock_property_editors.clear()
        self._current_edited_item_in_dock = None


    def _populate_dock_for_state(self, props: dict):
        name_edit = QLineEdit(props.get('name', ''))
        name_edit.textChanged.connect(self._dock_editors_changed)
        self.properties_editor_layout.addRow("Name:", name_edit)
        self._dock_property_editors['name'] = name_edit

        initial_cb = QCheckBox("Initial State")
        initial_cb.setChecked(props.get('is_initial', False))
        initial_cb.stateChanged.connect(self._dock_editors_changed)
        self.properties_editor_layout.addRow(initial_cb) 
        self._dock_property_editors['is_initial'] = initial_cb
        
        final_cb = QCheckBox("Final State")
        final_cb.setChecked(props.get('is_final', False))
        final_cb.stateChanged.connect(self._dock_editors_changed)
        self.properties_editor_layout.addRow(final_cb) 
        self._dock_property_editors['is_final'] = final_cb

        color_val = props.get('color', COLOR_ITEM_STATE_DEFAULT_BG)
        self._dock_property_editors['_current_color_obj'] = QColor(color_val) 
        
        color_button = QPushButton(color_val) 
        color_button.setStyleSheet(f"background-color: {color_val}; color: {COLOR_TEXT_ON_ACCENT if QColor(color_val).lightnessF() < 0.5 else COLOR_TEXT_PRIMARY}; border: 1px solid {QColor(color_val).darker(130).name()}; padding: 4px;")
        color_button.setToolTip("Click to change color")
        color_button.clicked.connect(lambda: self._pick_dock_color(color_button))
        self.properties_editor_layout.addRow("Color:", color_button)
        self._dock_property_editors['color_button'] = color_button


    def _populate_dock_for_transition(self, props: dict):
        event_edit = QLineEdit(props.get('event', ''))
        event_edit.textChanged.connect(self._dock_editors_changed)
        self.properties_editor_layout.addRow("Event:", event_edit)
        self._dock_property_editors['event'] = event_edit

        condition_edit = QLineEdit(props.get('condition', ''))
        condition_edit.setPlaceholderText("e.g., var == 10 (Python syntax)")
        condition_edit.textChanged.connect(self._dock_editors_changed)
        self.properties_editor_layout.addRow("Condition:", condition_edit)
        self._dock_property_editors['condition'] = condition_edit
        
        color_val = props.get('color', COLOR_ITEM_TRANSITION_DEFAULT)
        self._dock_property_editors['_current_color_obj'] = QColor(color_val)
        
        color_button = QPushButton(color_val)
        color_button.setStyleSheet(f"background-color: {color_val}; color: {COLOR_TEXT_ON_ACCENT if QColor(color_val).lightnessF() < 0.5 else COLOR_TEXT_PRIMARY}; border: 1px solid {QColor(color_val).darker(130).name()}; padding: 4px;")
        color_button.setToolTip("Click to change color")
        color_button.clicked.connect(lambda: self._pick_dock_color(color_button))
        self.properties_editor_layout.addRow("Color:", color_button)
        self._dock_property_editors['color_button'] = color_button


    def _populate_dock_for_comment(self, props: dict):
        current_text = props.get('text', '')
        display_text = (current_text[:100] + '...') if len(current_text) > 100 else current_text
        text_label_widget = QLabel(html.escape(display_text))
        text_label_widget.setWordWrap(True)
        text_label_widget.setStyleSheet(f"font-style: italic; color: {COLOR_TEXT_SECONDARY}; padding: 4px; border: 1px solid {COLOR_BORDER_LIGHT}; background-color: {COLOR_BACKGROUND_LIGHT}; border-radius: 3px;")
        self.properties_editor_layout.addRow("Text (Preview):", text_label_widget)


    def _pick_dock_color(self, color_button_ref: QPushButton):
        if self._current_edited_item_in_dock and '_current_color_obj' in self._dock_property_editors:
            initial_color = self._dock_property_editors['_current_color_obj']
            new_color = QColorDialog.getColor(initial_color, self, "Select Item Color")
            if new_color.isValid() and new_color != initial_color:
                self._dock_property_editors['_current_color_obj'] = new_color
                color_button_ref.setText(new_color.name())
                color_button_ref.setStyleSheet(f"background-color: {new_color.name()}; color: {COLOR_TEXT_ON_ACCENT if new_color.lightnessF() < 0.5 else COLOR_TEXT_PRIMARY}; border: 1px solid {new_color.darker(130).name()}; padding: 4px;")
                self._dock_editors_changed() 

    @pyqtSlot()
    def _dock_editors_changed(self):
        if not self._current_edited_item_in_dock:
            self.properties_apply_button.setEnabled(False)
            self.properties_revert_button.setEnabled(False)
            return

        original_props = self._current_edited_item_in_dock.get_data()
        changed = False

        if isinstance(self._current_edited_item_in_dock, GraphicsStateItem):
            if 'name' in self._dock_property_editors and self._dock_property_editors['name'].text().strip() != original_props.get('name'):
                changed = True
            if 'is_initial' in self._dock_property_editors and self._dock_property_editors['is_initial'].isChecked() != original_props.get('is_initial'):
                changed = True
            if 'is_final' in self._dock_property_editors and self._dock_property_editors['is_final'].isChecked() != original_props.get('is_final'):
                changed = True
        elif isinstance(self._current_edited_item_in_dock, GraphicsTransitionItem):
            if 'event' in self._dock_property_editors and self._dock_property_editors['event'].text().strip() != original_props.get('event'):
                changed = True
            if 'condition' in self._dock_property_editors and self._dock_property_editors['condition'].text().strip() != original_props.get('condition'):
                changed = True
        
        if '_current_color_obj' in self._dock_property_editors and \
            isinstance(self._current_edited_item_in_dock, (GraphicsStateItem, GraphicsTransitionItem)):
            if self._dock_property_editors['_current_color_obj'].name() != original_props.get('color'):
                changed = True
        
        self.properties_apply_button.setEnabled(changed)
        self.properties_revert_button.setEnabled(changed)


    @pyqtSlot()
    def _on_apply_dock_properties(self):
        if not self._current_edited_item_in_dock or not hasattr(self, '_dock_property_editors') or not self._dock_property_editors:
            return

        old_props = self._current_edited_item_in_dock.get_data()
        new_props_from_dock = old_props.copy() 
        item_type_name = "Item"

        if isinstance(self._current_edited_item_in_dock, GraphicsStateItem):
            item_type_name = "State"
            if 'name' in self._dock_property_editors:
                new_name = self._dock_property_editors['name'].text().strip()
                if not new_name:
                    QMessageBox.warning(self, "Invalid Name", "State name cannot be empty.")
                    self._populate_dock_for_state(old_props) 
                    return
                existing_state = self.scene.get_state_by_name(new_name)
                if existing_state and existing_state != self._current_edited_item_in_dock:
                    QMessageBox.warning(self, "Duplicate Name", f"A state named '{new_name}' already exists.")
                    self._populate_dock_for_state(old_props) 
                    return
                new_props_from_dock['name'] = new_name
            if 'is_initial' in self._dock_property_editors:
                new_props_from_dock['is_initial'] = self._dock_property_editors['is_initial'].isChecked()
            if 'is_final' in self._dock_property_editors:
                new_props_from_dock['is_final'] = self._dock_property_editors['is_final'].isChecked()

        elif isinstance(self._current_edited_item_in_dock, GraphicsTransitionItem):
            item_type_name = "Transition"
            if 'event' in self._dock_property_editors:
                new_props_from_dock['event'] = self._dock_property_editors['event'].text().strip()
            if 'condition' in self._dock_property_editors:
                new_props_from_dock['condition'] = self._dock_property_editors['condition'].text().strip()
        
        if '_current_color_obj' in self._dock_property_editors and \
           isinstance(self._current_edited_item_in_dock, (GraphicsStateItem, GraphicsTransitionItem)): 
             new_props_from_dock['color'] = self._dock_property_editors['_current_color_obj'].name()


        if new_props_from_dock != old_props:
            cmd = EditItemPropertiesCommand(self._current_edited_item_in_dock, old_props, new_props_from_dock, f"Edit {item_type_name} via Dock")
            self.undo_stack.push(cmd)
            self.log_message("INFO", f"Properties updated for {item_type_name} via dock.")
        
        self.properties_apply_button.setEnabled(False)
        self.properties_revert_button.setEnabled(False)


    @pyqtSlot()
    def _on_revert_dock_properties(self):
        if self._current_edited_item_in_dock:
            self._update_properties_dock() 
            self.properties_apply_button.setEnabled(False)
            self.properties_revert_button.setEnabled(False)

    @pyqtSlot()
    def _on_edit_selected_item_properties_from_dock_button(self):
        if self._current_edited_item_in_dock:
             self.scene.edit_item_properties(self._current_edited_item_in_dock)
             self._update_properties_dock() 
    
    def _log_to_parent(self, level, message): 
        if self.scene and hasattr(self.scene, 'log_function'):
            self.scene.log_function(message, level)
        else:
            logger.log(getattr(logging, level.upper(), logging.INFO), f"(MW_Direct) {message}")


    @pyqtSlot(GraphicsStateItem, bool)
    def on_toggle_state_breakpoint(self, state_item: GraphicsStateItem, set_bp: bool):
        if not self.py_fsm_engine or not self.py_sim_active:
            QMessageBox.information(self, "Simulation Not Active", "Breakpoints can only be managed during an active Python simulation.")
            sender_action = self.sender()
            if sender_action and isinstance(sender_action, QAction):
                sender_action.setChecked(not set_bp) 
            return

        state_name = state_item.text_label
        action_text = ""
        current_tooltip = state_item.toolTip() if state_item.toolTip() else f"State: {state_name}"
        bp_marker_text = "\n[Breakpoint Set]"

        if set_bp:
            self.py_fsm_engine.add_state_breakpoint(state_name)
            if bp_marker_text not in current_tooltip:
                 state_item.setToolTip(current_tooltip + bp_marker_text)
            action_text = f"Breakpoint SET for state: {state_name}"
        else:
            self.py_fsm_engine.remove_state_breakpoint(state_name)
            state_item.setToolTip(current_tooltip.replace(bp_marker_text, ""))
            action_text = f"Breakpoint CLEARED for state: {state_name}"
        
        state_item.update() 
        
        if hasattr(self, 'py_sim_ui_manager') and self.py_sim_ui_manager:
             self.py_sim_ui_manager.append_to_action_log([action_text])
        logger.info(action_text)


if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    
    script_dir = os.path.dirname(os.path.abspath(__file__)) 
    parent_dir_of_script = os.path.dirname(script_dir)      
    if parent_dir_of_script not in sys.path:
        sys.path.insert(0, parent_dir_of_script)


    app.setStyleSheet(STYLE_SHEET_GLOBAL)

    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())