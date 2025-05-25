# bsm_designer_project/main.py

import sys
import os
import tempfile
import subprocess
import json
import html
import math
import socket
import re
from PyQt5.QtCore import QTime, QTimer, QPointF
import pygraphviz as pgv

# --- Custom Modules ---
from graphics_scene import DiagramScene, ZoomableView
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
from fsm_simulator import FSMSimulator, FSMError # FSMSimulator now handles hierarchy
from ai_chatbot import AIChatbotManager
from matlab_integration import MatlabConnection
from dialogs import (StatePropertiesDialog, TransitionPropertiesDialog, CommentPropertiesDialog,
                     MatlabSettingsDialog)
from config import (
    APP_VERSION, APP_NAME, FILE_EXTENSION, FILE_FILTER, STYLE_SHEET_GLOBAL,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG,
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_PRIMARY_LIGHT,
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_BACKGROUND_LIGHT, COLOR_GRID_MINOR, COLOR_GRID_MAJOR,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_ON_ACCENT,
    COLOR_ACCENT_SECONDARY, COLOR_BORDER_LIGHT, COLOR_BORDER_MEDIUM
)
from utils import get_standard_icon

# --- Logging Setup ---
import logging
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
    QDesktopServices, QWheelEvent, QMouseEvent, QCloseEvent, QFontMetrics, QPalette
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QTimer, QSize, QUrl,
    QSaveFile, QIODevice
)

logger = logging.getLogger(__name__)


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

        pixmap_size = QSize(max(150, self.width()), max(40, self.height()))
        pixmap = QPixmap(pixmap_size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        button_rect = QRectF(0, 0, pixmap_size.width() -1, pixmap_size.height() -1)
        bg_color = QColor(self.palette().color(self.backgroundRole())).lighter(110)
        if not bg_color.isValid() or bg_color.alpha() == 0:
            bg_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT)
        border_color_qcolor = QColor(COLOR_ACCENT_PRIMARY)

        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color_qcolor, 1.5))
        painter.drawRoundedRect(button_rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5)

        icon_pixmap = self.icon().pixmap(QSize(20, 20), QIcon.Normal, QIcon.On)
        text_x_offset = 10
        icon_y_offset = (pixmap_size.height() - icon_pixmap.height()) / 2
        if not icon_pixmap.isNull():
            painter.drawPixmap(int(text_x_offset), int(icon_y_offset), icon_pixmap)
            text_x_offset += icon_pixmap.width() + 8

        text_color_qcolor = self.palette().color(QPalette.ButtonText)
        if not text_color_qcolor.isValid():
            text_color_qcolor = QColor(COLOR_TEXT_PRIMARY)
        painter.setPen(text_color_qcolor)
        painter.setFont(self.font())

        text_rect = QRectF(text_x_offset, 0, pixmap_size.width() - text_x_offset - 5, pixmap_size.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 4, pixmap.height() // 2))
        drag.exec_(Qt.CopyAction | Qt.MoveAction)


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
        self._py_sim_currently_highlighted_item: GraphicsStateItem | None = None
        self._py_sim_currently_highlighted_transition: GraphicsTransitionItem | None = None

        self._internet_connected: bool | None = None
        self.internet_check_timer = QTimer(self)

        self.init_ui()

        try:
            setup_global_logging(self.log_output)
            logger.info("Main window initialized and logging configured.")
        except NameError:
            logger.error("Failed to run setup_global_logging. UI logs might not work.")


        self.ai_chatbot_manager.statusUpdate.connect(self._update_ai_chat_status)
        self.ai_chatbot_manager.errorOccurred.connect(self._handle_ai_error)
        self.ai_chatbot_manager.fsmDataReceived.connect(self._handle_fsm_data_from_ai)
        self.ai_chatbot_manager.plainResponseReady.connect(self._handle_plain_ai_response)

        self.ai_chat_display.setObjectName("AIChatDisplay")
        self.ai_chat_input.setObjectName("AIChatInput")
        self.ai_chat_send_button.setObjectName("AIChatSendButton")
        self.ai_chat_status_label.setObjectName("AIChatStatusLabel")
        self._update_ai_chat_status("Status: API Key required. Configure in Settings.")

        self.matlab_status_label.setObjectName("MatlabStatusLabel")
        self.py_sim_status_label.setObjectName("PySimStatusLabel")
        self.internet_status_label.setObjectName("InternetStatusLabel")
        self.status_label.setObjectName("StatusLabel")

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

        if not self.ai_chatbot_manager.api_key:
            self._update_ai_chat_status("Status: API Key required. Configure in Settings.")
        else:
            self._update_ai_chat_status("Status: Ready.")

    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050)
        self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM"))
        self._create_central_widget()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_docks()
        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()
        self.select_mode_action.trigger()


    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self)
        self.view.setObjectName("MainDiagramView")
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
        self.save_as_action = QAction(get_standard_icon(QStyle.SP_DriveHDIcon),"Save &As...", self, shortcut=QKeySequence.SaveAs, statusTip="Save the current file with a new name", triggered=self.on_save_file_as)
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

        self.start_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Py▶"), "&Start Python Simulation", self, statusTip="Start internal FSM simulation", triggered=self.on_start_py_simulation)
        self.stop_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaStop, "Py■"), "S&top Python Simulation", self, statusTip="Stop internal FSM simulation", triggered=self.on_stop_py_simulation, enabled=False)
        self.reset_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaSkipBackward, "Py«"), "&Reset Python Simulation", self, statusTip="Reset internal FSM simulation to initial state", triggered=self.on_reset_py_simulation, enabled=False)

        self.openai_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "AISet"), "AI Assistant Settings...", self, triggered=self.on_openai_settings)
        self.clear_ai_chat_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "Clear"), "Clear Chat History", self, triggered=self.on_clear_ai_chat_history)
        self.ask_ai_to_generate_fsm_action = QAction(QIcon.fromTheme("system-run", get_standard_icon(QStyle.SP_DialogYesButton, "AIGen")), "Generate FSM from Description...", self, triggered=self.on_ask_ai_to_generate_fsm)

        self.open_example_menu_action = QAction("Open E&xample...", self)
        self.quick_start_action = QAction(get_standard_icon(QStyle.SP_MessageBoxQuestion, "QS"), "&Quick Start Guide", self, triggered=self.on_show_quick_start)
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, triggered=self.on_about)

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
        tb_style = Qt.ToolButtonTextBesideIcon

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

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1)

        self.py_sim_status_label = QLabel("PySim: Idle")
        self.py_sim_status_label.setToolTip("Internal Python FSM Simulation Status.")
        self.status_bar.addPermanentWidget(self.py_sim_status_label)

        self.matlab_status_label = QLabel("MATLAB: Initializing...")
        self.matlab_status_label.setToolTip("MATLAB connection status.")
        self.status_bar.addPermanentWidget(self.matlab_status_label)

        self.internet_status_label = QLabel("Internet: Init...")
        self.internet_status_label.setToolTip("Internet connectivity status. Checks periodically.")
        self.status_bar.addPermanentWidget(self.internet_status_label)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0,0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setTextVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)

        self.tools_dock = QDockWidget("Tools", self)
        self.tools_dock.setObjectName("ToolsDock")
        self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_widget_main = QWidget()
        tools_widget_main.setObjectName("ToolsDockWidgetContents")
        tools_main_layout = QVBoxLayout(tools_widget_main)
        tools_main_layout.setSpacing(10)
        tools_main_layout.setContentsMargins(5,5,5,5)

        mode_group_box = QGroupBox("Interaction Modes")
        mode_layout = QVBoxLayout()
        mode_layout.setSpacing(5)
        self.toolbox_select_button = QToolButton(); self.toolbox_select_button.setDefaultAction(self.select_mode_action)
        self.toolbox_add_state_button = QToolButton(); self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action)
        self.toolbox_transition_button = QToolButton(); self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action)
        self.toolbox_add_comment_button = QToolButton(); self.toolbox_add_comment_button.setDefaultAction(self.add_comment_mode_action)
        for btn in [self.toolbox_select_button, self.toolbox_add_state_button, self.toolbox_transition_button, self.toolbox_add_comment_button]:
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setIconSize(QSize(18,18))
            mode_layout.addWidget(btn)
        mode_group_box.setLayout(mode_layout)
        tools_main_layout.addWidget(mode_group_box)

        draggable_group_box = QGroupBox("Drag New Elements")
        draggable_layout = QVBoxLayout()
        draggable_layout.setSpacing(5)
        drag_state_btn = DraggableToolButton(" State", "application/x-bsm-tool", "State")
        drag_state_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))
        drag_initial_state_btn = DraggableToolButton(" Initial State", "application/x-bsm-tool", "Initial State")
        drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt"))
        drag_final_state_btn = DraggableToolButton(" Final State", "application/x-bsm-tool", "Final State")
        drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt"))
        drag_comment_btn = DraggableToolButton(" Comment", "application/x-bsm-tool", "Comment")
        drag_comment_btn.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))
        for btn in [drag_state_btn, drag_initial_state_btn, drag_final_state_btn, drag_comment_btn]:
            btn.setIconSize(QSize(18,18))
            draggable_layout.addWidget(btn)
        draggable_group_box.setLayout(draggable_layout)
        tools_main_layout.addWidget(draggable_group_box)

        tools_main_layout.addStretch()
        self.tools_dock.setWidget(tools_widget_main)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock)
        self.view_menu.addAction(self.tools_dock.toggleViewAction())

        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        properties_widget = QWidget()
        properties_layout = QVBoxLayout(properties_widget)
        properties_layout.setContentsMargins(5,5,5,5)
        properties_layout.setSpacing(5)
        self.properties_editor_label = QLabel("<i>No item selected.</i><br><small>Click an item in the diagram or use tools to add new items.</small>")
        self.properties_editor_label.setWordWrap(True)
        self.properties_editor_label.setTextFormat(Qt.RichText)
        self.properties_editor_label.setAlignment(Qt.AlignTop)
        self.properties_editor_label.setStyleSheet(f"padding: 5px; background-color: {COLOR_BACKGROUND_LIGHT}; border: 1px solid {COLOR_BORDER_MEDIUM};")
        properties_layout.addWidget(self.properties_editor_label, 1)
        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"),"Edit Properties")
        self.properties_edit_button.setEnabled(False)
        self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock)
        properties_layout.addWidget(self.properties_edit_button)
        self.properties_dock.setWidget(properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        self.view_menu.addAction(self.properties_dock.toggleViewAction())

        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(5,5,5,5)
        self.log_output = QTextEdit()
        self.log_output.setObjectName("LogOutput")
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)
        self.log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.view_menu.addAction(self.log_dock.toggleViewAction())

        self.py_sim_dock = QDockWidget("Python Simulation", self)
        self.py_sim_dock.setObjectName("PySimDock")
        self.py_sim_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        py_sim_widget = QWidget()
        py_sim_layout = QVBoxLayout(py_sim_widget)
        py_sim_layout.setContentsMargins(5,5,5,5)
        py_sim_layout.setSpacing(5)

        controls_group = QGroupBox("Controls")
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(5)
        self.py_sim_start_btn = QToolButton(); self.py_sim_start_btn.setDefaultAction(self.start_py_sim_action)
        self.py_sim_stop_btn = QToolButton(); self.py_sim_stop_btn.setDefaultAction(self.stop_py_sim_action)
        self.py_sim_reset_btn = QToolButton(); self.py_sim_reset_btn.setDefaultAction(self.reset_py_sim_action)
        self.py_sim_step_btn = QPushButton(get_standard_icon(QStyle.SP_MediaSeekForward, "Step"),"Step")
        self.py_sim_step_btn.clicked.connect(self.on_step_py_simulation)
        for btn in [self.py_sim_start_btn, self.py_sim_stop_btn, self.py_sim_reset_btn]:
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly); btn.setIconSize(QSize(18,18)); controls_layout.addWidget(btn)
        controls_layout.addWidget(self.py_sim_step_btn)
        controls_layout.addStretch()
        controls_group.setLayout(controls_layout)
        py_sim_layout.addWidget(controls_group)

        # --- Options Group (with Halt on Error checkbox) ---
        options_group = QGroupBox("Options")
        options_layout = QHBoxLayout()
        options_layout.setSpacing(5)
        self.py_sim_halt_on_error_checkbox = QCheckBox("Halt on Action Error")
        self.py_sim_halt_on_error_checkbox.setToolTip(
            "If checked, the simulation will stop if an error occurs in a state/transition action."
            "\nIf unchecked, errors are logged, and the simulation attempts to continue."
        )
        self.py_sim_halt_on_error_checkbox.setChecked(False) # Default to not halting
        options_layout.addWidget(self.py_sim_halt_on_error_checkbox)
        options_layout.addStretch()
        options_group.setLayout(options_layout)
        py_sim_layout.addWidget(options_group)
        # --- End Options Group ---

        event_group = QGroupBox("Event Trigger")
        event_layout = QHBoxLayout()
        event_layout.setSpacing(5)
        self.py_sim_event_combo = QComboBox()
        self.py_sim_event_combo.addItem("None (Internal Step)")
        self.py_sim_event_combo.setEditable(False)
        event_layout.addWidget(self.py_sim_event_combo, 1)
        self.py_sim_event_name_edit = QLineEdit()
        self.py_sim_event_name_edit.setPlaceholderText("Custom event name")
        event_layout.addWidget(self.py_sim_event_name_edit, 1)
        self.py_sim_trigger_event_btn = QPushButton(get_standard_icon(QStyle.SP_MediaPlay, "Trg"),"Trigger")
        self.py_sim_trigger_event_btn.clicked.connect(self.on_trigger_py_event)
        event_layout.addWidget(self.py_sim_trigger_event_btn)
        event_group.setLayout(event_layout)
        py_sim_layout.addWidget(event_group)

        state_group = QGroupBox("Current State")
        state_layout = QVBoxLayout()
        self.py_sim_current_state_label = QLabel("<i>Not Running</i>")
        self.py_sim_current_state_label.setStyleSheet("font-size: 9pt; padding: 3px;")
        state_layout.addWidget(self.py_sim_current_state_label)
        state_group.setLayout(state_layout)
        py_sim_layout.addWidget(state_group)

        variables_group = QGroupBox("Variables")
        variables_layout = QVBoxLayout()
        self.py_sim_variables_table = QTableWidget()
        self.py_sim_variables_table.setRowCount(0); self.py_sim_variables_table.setColumnCount(2)
        self.py_sim_variables_table.setHorizontalHeaderLabels(["Name", "Value"])
        self.py_sim_variables_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.py_sim_variables_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.py_sim_variables_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        variables_layout.addWidget(self.py_sim_variables_table)
        variables_group.setLayout(variables_layout)
        py_sim_layout.addWidget(variables_group)

        log_group = QGroupBox("Action Log")
        log_layout = QVBoxLayout()
        self.py_sim_action_log_output = QTextEdit()
        self.py_sim_action_log_output.setReadOnly(True)
        self.py_sim_action_log_output.setObjectName("PySimActionLog")
        self.py_sim_action_log_output.setHtml("<i>Simulation log will appear here...</i>")
        log_layout.addWidget(self.py_sim_action_log_output)
        log_group.setLayout(log_layout)
        py_sim_layout.addWidget(log_group, 1)

        self.py_sim_dock.setWidget(py_sim_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock)
        self.view_menu.addAction(self.py_sim_dock.toggleViewAction())

        self.ai_chatbot_dock = QDockWidget("AI Chatbot", self)
        self.ai_chatbot_dock.setObjectName("AIChatbotDock")
        self.ai_chatbot_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        ai_chat_widget = QWidget()
        ai_chat_layout = QVBoxLayout(ai_chat_widget)
        ai_chat_layout.setContentsMargins(5,5,5,5)
        ai_chat_layout.setSpacing(5)
        self.ai_chat_display = QTextEdit()
        self.ai_chat_display.setReadOnly(True)
        self.ai_chat_display.setStyleSheet("font-size: 9pt; padding: 5px;")
        self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
        ai_chat_layout.addWidget(self.ai_chat_display, 1)
        input_layout = QHBoxLayout()
        self.ai_chat_input = QLineEdit()
        self.ai_chat_input.setPlaceholderText("Type your message to the AI...")
        self.ai_chat_input.returnPressed.connect(self.on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_input, 1)
        self.ai_chat_send_button = QPushButton(get_standard_icon(QStyle.SP_ArrowForward, "Snd"),"Send")
        self.ai_chat_send_button.clicked.connect(self.on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_send_button)
        ai_chat_layout.addLayout(input_layout)
        self.ai_chat_status_label = QLabel("Status: Initializing...")
        self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;")
        ai_chat_layout.addWidget(self.ai_chat_status_label)
        self.ai_chatbot_dock.setWidget(ai_chat_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock)
        self.view_menu.addAction(self.ai_chatbot_dock.toggleViewAction())

        self.tabifyDockWidget(self.properties_dock, self.ai_chatbot_dock)
        self.tabifyDockWidget(self.ai_chatbot_dock, self.py_sim_dock)

    # --- AI Chatbot Methods ---
    def on_ask_ai_to_generate_fsm(self):
        description, ok = QInputDialog.getMultiLineText(
            self, "Generate FSM", "Describe the FSM you want to create:",
            "Example: A traffic light with states Red, Yellow, Green. Event 'TIMER_EXPIRED' cycles through them."
        )
        if ok and description.strip():
            logger.info("AI: Sending FSM description to AI: '%s...'", description[:50])
            self._update_ai_chat_status("Status: Generating FSM from description...")
            self.ai_chatbot_manager.generate_fsm_from_description(description)
            self._append_to_ai_chat_display("You", f"Generate an FSM: {description}")
        elif ok:
            QMessageBox.warning(self, "Empty Description", "Please provide a description for the FSM.")

    def _handle_fsm_data_from_ai(self, fsm_data: dict, source_message: str):
        logger.info("AI: Received FSM data. Source: '%s...'", source_message[:30])
        self._append_to_ai_chat_display("AI", f"Received FSM structure. (Source: {source_message[:30]}...) Adding to diagram.")

        if not fsm_data or (not fsm_data.get('states') and not fsm_data.get('transitions')):
            logger.error("AI: Returned empty or invalid FSM data structure.")
            self._update_ai_chat_status("Status: AI returned no FSM data.")
            self._append_to_ai_chat_display("System", "AI did not return a valid FSM structure to draw.")
            return

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("Add AI Generated FSM")
        msg_box.setText("AI has generated an FSM. Do you want to clear the current diagram before adding the new FSM, or add to the existing one?")
        clear_button = msg_box.addButton("Clear and Add", QMessageBox.AcceptRole)
        add_to_existing_button = msg_box.addButton("Add to Existing", QMessageBox.AcceptRole)
        cancel_button = msg_box.addButton("Cancel", QMessageBox.RejectRole)
        msg_box.setDefaultButton(cancel_button)
        msg_box.exec_()
        clicked_button = msg_box.clickedButton(); reply = -1
        if clicked_button == clear_button: reply = 0
        elif clicked_button == add_to_existing_button: reply = 1
        elif clicked_button == cancel_button: reply = 2
        if reply == 2 or reply == -1:
            logger.info("AI: User cancelled adding AI generated FSM."); self._update_ai_chat_status("Status: FSM generation cancelled by user."); return
        clear_current = (reply == 0)
        self._add_fsm_data_to_scene(fsm_data, clear_current_diagram=clear_current, original_user_prompt=source_message)
        self._update_ai_chat_status("Status: FSM added to diagram."); logger.info("AI: FSM data from AI processed and added to scene.")

    def _handle_plain_ai_response(self, ai_message: str):
        logger.info("AI: Received plain AI response."); self._append_to_ai_chat_display("AI", ai_message)

    def on_send_ai_chat_message(self):
        message = self.ai_chat_input.text().strip()
        if not message: return
        self.ai_chat_input.clear(); self._append_to_ai_chat_display("You", message)
        self.ai_chatbot_manager.send_message(message); self._update_ai_chat_status("Status: Sending message...")

    def _add_fsm_data_to_scene(self, fsm_data: dict, clear_current_diagram: bool = False, original_user_prompt: str = "AI Generated FSM"):
        logger.info("AI: ADD_FSM_TO_SCENE clear_current_diagram=%s", clear_current_diagram); logger.debug("AI: Received FSM Data (states: %d, transitions: %d)", len(fsm_data.get('states',[])), len(fsm_data.get('transitions',[])))
        if clear_current_diagram:
            if not self.on_new_file(silent=True): logger.warning("AI: Clearing diagram cancelled. Cannot add AI FSM."); return
            logger.info("AI: Cleared diagram before AI generation.")
        if not clear_current_diagram: self.undo_stack.beginMacro(f"Add AI FSM: {original_user_prompt[:30]}...")
        state_items_map={}; items_to_add_for_undo=[]
        layout_start_x,layout_start_y=100,100; items_per_row=3; default_item_width,default_item_height=120,60; padding_x,padding_y=150,100; GV_SCALE=1.2
        G=pgv.AGraph(directed=True,strict=False)
        for sd in fsm_data.get('states',[]): name=sd.get('name'); _=name and G.add_node(name,width=default_item_width/72.0,height=default_item_height/72.0)
        for td in fsm_data.get('transitions',[]): src,tgt=td.get('source'),td.get('target'); _=src and tgt and G.has_node(src)and G.has_node(tgt)and G.add_edge(src,tgt,label=td.get('event',''))or logger.warning("AI: Skip edge %s->%s",src,tgt)
        gv_pos={}; try:
            G.layout(prog="dot"); logger.debug("AI: Graphviz layout successful.")
            raw_gv_pos=[]; [raw_gv_pos.append({'name':n.name,'x':float(p[0]),'y':float(p[1])})for n in G.nodes()for p in[n.attr.get('pos','0,0').split(',')]if len(p)==2]
            if raw_gv_pos:min_x=min(p['x']for p in raw_gv_pos);max_y=max(p['y']for p in raw_gv_pos);[gv_pos.update({p['name']:QPointF((p['x']-min_x)*GV_SCALE+layout_start_x,(max_y-p['y'])*GV_SCALE+layout_start_y)})for p in raw_gv_pos]
            else:logger.warning("AI: Graphviz - No valid positions extracted.")
        except Exception as e:logger.error("AI: Graphviz layout error: %s. Fallback.",e,exc_info=True);gv_pos={}
        for i,sd in enumerate(fsm_data.get('states',[])):
            name=sd.get('name');_ =not name and logger.warning("AI: State missing name: %s",sd)or next((False for _ in()),True)and None
            if not name:continue
            w,h=sd.get('width',default_item_width),sd.get('height',default_item_height);pos=gv_pos.get(name)
            px,py=(pos.x(),pos.y())if pos else(layout_start_x+(i%items_per_row)*(default_item_width+padding_x),layout_start_y+(i//items_per_row)*(default_item_height+padding_y))
            try:
                si=GraphicsStateItem(px,py,w,h,name,sd.get('is_initial',False),sd.get('is_final',False),sd.get('properties',{}).get('color'),sd.get('entry_action',""),sd.get('during_action',""),sd.get('exit_action',""),sd.get('description',""),sd.get('is_superstate',False),sd.get('sub_fsm_data',{'states':[],'transitions':[],'comments':[]}))
                items_to_add_for_undo.append(si);state_items_map[name]=si
            except Exception as e:logger.error("AI: Error creating StateItem '%s': %s",name,e,exc_info=True)
        for td in fsm_data.get('transitions',[]):
            src_n,tgt_n=td.get('source'),td.get('target');_ =not src_n or not tgt_n and logger.warning("AI: Transition missing src/tgt: %s",td)or next((False for _ in()),True)and None
            if not src_n or not tgt_n:continue
            src_i,tgt_i=state_items_map.get(src_n),state_items_map.get(tgt_n)
            if src_i and tgt_i:
                try:
                    ti=GraphicsTransitionItem(src_i,tgt_i,td.get('event',""),td.get('condition',""),td.get('action',""),td.get('properties',{}).get('color'),td.get('description',""))
                    ox,oy=td.get('control_offset_x'),td.get('control_offset_y')
                    if ox is not None and oy is not None:try:ti.set_control_point_offset(QPointF(float(ox),float(oy)))except ValueError:logger.warning("AI: Invalid ctrl offsets %s->%s",src_n,tgt_n)
                    items_to_add_for_undo.append(ti)
                except Exception as e:logger.error("AI: Error creating TransItem %s->%s: %s",src_n,tgt_n,e,exc_info=True)
            else:logger.warning("AI: No src/tgt item for trans %s->%s",src_n,tgt_n)
        max_y_items=max((it.scenePos().y()+it.boundingRect().height()for it in state_items_map.values()if it.scenePos()),default=layout_start_y)if state_items_map else layout_start_y
        csy,csx=max_y_items+padding_y,layout_start_x
        for i,cd in enumerate(fsm_data.get('comments',[])):
            txt=cd.get('text');_ =not txt and None or next((False for _ in()),True)and None;if not txt:continue
            cx,cy,cw=cd.get('x',csx+i*(150+20)),cd.get('y',csy),cd.get('width')
            try:ci=GraphicsCommentItem(cx,cy,txt);_=cw is not None and(lambda:ci.setTextWidth(float(cw))if isinstance(cw,(int,float))else logger.warning("AI: Invalid comment width %s",cw))();items_to_add_for_undo.append(ci)
            except Exception as e:logger.error("AI: Error creating CommentItem: %s",e,exc_info=True)
        if items_to_add_for_undo:
            for item in items_to_add_for_undo:
                item_type=type(item).__name__.replace("Graphics","").replace("Item","");cmd_txt=f"Add AI {item_type}";_=hasattr(item,'text_label')and item.text_label and(cmd_txt:=f"{cmd_txt}: {item.text_label}")or hasattr(item,'_compose_label_string')and(cmd_txt:=f"{cmd_txt} ({item._compose_label_string()})");add_cmd=AddItemCommand(self.scene,item,cmd_txt);self.undo_stack.push(add_cmd)
            logger.info("AI: Added %d items.",len(items_to_add_for_undo));QTimer.singleShot(100,self._fit_view_to_new_ai_items)
        else:logger.info("AI: No valid items generated.")
        if not clear_current_diagram and items_to_add_for_undo:self.undo_stack.endMacro()
        elif not clear_current_diagram and not items_to_add_for_undo:self.undo_stack.endMacro();_=self.undo_stack.count()>0 and self.undo_stack.command(self.undo_stack.count()-1).childCount()==0 and None
        if self.py_sim_active and items_to_add_for_undo:
            diag_data=self.scene.get_diagram_data()
            try:
                halt_on_err = self.py_sim_halt_on_error_checkbox.isChecked() # Get current setting
                self.py_fsm_engine=FSMSimulator(diag_data['states'],diag_data['transitions'], halt_on_action_error=halt_on_err)
                self._append_to_py_simulation_log(["Python FSM Sim reinitialized for AI diagram."]);self._update_py_simulation_dock_ui()
            except FSMError as e:self._append_to_py_simulation_log([f"ERR Re-init Sim after AI: {e}"]);self.on_stop_py_simulation(silent=True)
        logger.debug("AI: ADD_FSM_TO_SCENE finished. Items: %d",len(items_to_add_for_undo))

    def _fit_view_to_new_ai_items(self):
        if not self.scene.items():return;items_bounds=self.scene.itemsBoundingRect()
        if self.view and not items_bounds.isNull():padded_bounds=items_bounds.adjusted(-50,-50,50,50);self.view.fitInView(padded_bounds,Qt.KeepAspectRatio);logger.info("AI: View adjusted.")
        elif self.view and self.scene.sceneRect():self.view.centerOn(self.scene.sceneRect().center())
    def _handle_ai_error(self,error_message:str):self._append_to_ai_chat_display("System Error",error_message);logger.error("AI Chatbot Error: %s",error_message);short_error=error_message.split('\n')[0].split(':')[0][:50];self._update_ai_chat_status(f"Error: {short_error}...")
    def _update_ai_chat_status(self,status_text:str):
        if hasattr(self,'ai_chat_status_label'):
            self.ai_chat_status_label.setText(status_text)
            is_thinking="thinking..."in status_text.lower()or"sending..."in status_text.lower()or"generating..."in status_text.lower()
            is_key_req="api key required"in status_text.lower()or"inactive"in status_text.lower()or"api key error"in status_text.lower()
            is_err="error"in status_text.lower()or"failed"in status_text.lower()or is_key_req
            if is_err:self.ai_chat_status_label.setStyleSheet("font-size:8pt;color:red;")
            elif is_thinking:self.ai_chat_status_label.setStyleSheet("font-size:8pt;color:#FF8F00;")
            else:self.ai_chat_status_label.setStyleSheet("font-size:8pt;color:grey;")
            can_send=not is_thinking and not is_key_req
            if hasattr(self,'ai_chat_send_button'):self.ai_chat_send_button.setEnabled(can_send)
            if hasattr(self,'ai_chat_input'):self.ai_chat_input.setEnabled(can_send);_=can_send and hasattr(self,'ai_chatbot_dock')and self.ai_chatbot_dock.isVisible()and self.isActiveWindow()and self.ai_chat_input.setFocus()
            if hasattr(self,'ask_ai_to_generate_fsm_action'):self.ask_ai_to_generate_fsm_action.setEnabled(can_send)
    def _append_to_ai_chat_display(self,sender:str,message:str):
        ts=QTime.currentTime().toString('hh:mm');sender_color=COLOR_ACCENT_PRIMARY
        if sender=="You":sender_color=COLOR_ACCENT_SECONDARY
        elif"System"in sender:sender_color="#D32F2F"
        msg=html.escape(message);msg=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',msg);msg=re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)',r'<i>\1</i>',msg);msg=re.sub(r'```(.*?)```',r'<pre><code style="background-color:#f0f0f0;padding:2px 4px;border-radius:3px;">\1</code></pre>',msg,flags=re.DOTALL);msg=re.sub(r'`(.*?)`',r'<code style="background-color:#f0f0f0;padding:1px 3px;border-radius:2px;">\1</code>',msg);msg=msg.replace("\n","<br>")
        fmt_html=f"<div style='margin-bottom:8px;'><span style='font-size:8pt;color:grey;'>[{ts}]</span> <strong style='color:{sender_color};'>{html.escape(sender)}:</strong><div style='margin-top:3px;padding-left:5px;border-left:2px solid {sender_color if'Error'not in sender else'#FFCDD2'};'>{msg}</div></div>"
        self.ai_chat_display.append(fmt_html);self.ai_chat_display.ensureCursorVisible()
    def on_openai_settings(self):curr_key=self.ai_chatbot_manager.api_key or"";key,ok=QInputDialog.getText(self,"OpenAI API Key","Enter OpenAI API Key (blank to clear):",QLineEdit.PasswordEchoOnEdit,curr_key);_=ok and(self.ai_chatbot_manager.set_api_key(key.strip()or None),logger.info(f"AI: OpenAI API Key {'set/updated'if key.strip()else'cleared'}."))
    def on_clear_ai_chat_history(self):_=self.ai_chatbot_manager and(self.ai_chatbot_manager.clear_conversation_history(),hasattr(self,'ai_chat_display')and(self.ai_chat_display.clear(),self.ai_chat_display.setPlaceholderText("AI chat history...")),logger.info("AI: Chat history cleared."))
    def _update_properties_dock(self):
        sel=self.scene.selectedItems();html_content="";edit_enabled=False;item_type_tt="item"
        if len(sel)==1:
            item=sel[0];props=item.get_data()if hasattr(item,'get_data')else{};item_type_name=type(item).__name__.replace("Graphics","").replace("Item","");item_type_tt=item_type_name.lower();edit_enabled=True
            def fmt(t,m=25):return"<i>(none)</i>"if not t else(e:=html.escape(str(t)),f:=e.split('\n')[0],f[:m]+"…"if len(f)>m or'\n'in e else f)
            rows=""
            if isinstance(item,GraphicsStateItem):
                c=QColor(props.get('color',COLOR_ITEM_STATE_DEFAULT_BG));tc='black'if c.lightnessF()>0.5 else'white';cs=f"background-color:{c.name()};color:{tc};padding:1px 4px;border-radius:2px;"
                rows+=f"<tr><td><b>Name:</b></td><td>{html.escape(props.get('name','N/A'))}</td></tr>"
                rows+=f"<tr><td><b>Initial:</b></td><td>{'Yes'if props.get('is_initial')else'No'}</td></tr>";rows+=f"<tr><td><b>Final:</b></td><td>{'Yes'if props.get('is_final')else'No'}</td></tr>"
                if props.get('is_superstate'):s_data=props.get('sub_fsm_data',{});s_s,s_t=len(s_data.get('states',[])),len(s_data.get('transitions',[]));rows+=f"<tr><td><b>Superstate:</b></td><td>Yes ({s_s} sub-states, {s_t} sub-trans.)</td></tr>"
                rows+=f"<tr><td><b>Color:</b></td><td><span style='{cs}'>{html.escape(c.name())}</span></td></tr>"
                rows+=f"<tr><td><b>Entry:</b></td><td>{fmt(props.get('entry_action',''))}</td></tr>";rows+=f"<tr><td><b>During:</b></td><td>{fmt(props.get('during_action',''))}</td></tr>";rows+=f"<tr><td><b>Exit:</b></td><td>{fmt(props.get('exit_action',''))}</td></tr>"
                if props.get('description'):rows+=f"<tr><td colspan='2'><b>Desc:</b> {fmt(props.get('description'),50)}</td></tr>"
            elif isinstance(item,GraphicsTransitionItem):
                c=QColor(props.get('color',COLOR_ITEM_TRANSITION_DEFAULT));tc='black'if c.lightnessF()>0.5 else'white';cs=f"background-color:{c.name()};color:{tc};padding:1px 4px;border-radius:2px;"
                evt,cond,act=html.escape(props.get('event',''))if props.get('event')else'',f"[{html.escape(props.get('condition',''))}]"if props.get('condition')else'',f"/{{{fmt(props.get('action',''),15)}}}"if props.get('action')else''
                lbl=" ".join(p for p in[evt,cond,act]if p)or"<i>(No Label)</i>"
                rows+=f"<tr><td><b>Label:</b></td><td style='font-size:8pt;'>{lbl}</td></tr>";rows+=f"<tr><td><b>From:</b></td><td>{html.escape(props.get('source','N/A'))}</td></tr>";rows+=f"<tr><td><b>To:</b></td><td>{html.escape(props.get('target','N/A'))}</td></tr>"
                rows+=f"<tr><td><b>Color:</b></td><td><span style='{cs}'>{html.escape(c.name())}</span></td></tr>";rows+=f"<tr><td><b>Curve:</b></td><td>Bend={props.get('control_offset_x',0):.0f}, Shift={props.get('control_offset_y',0):.0f}</td></tr>"
                if props.get('description'):rows+=f"<tr><td colspan='2'><b>Desc:</b> {fmt(props.get('description'),50)}</td></tr>"
            elif isinstance(item,GraphicsCommentItem):rows+=f"<tr><td colspan='2'><b>Text:</b> {fmt(props.get('text',''),60)}</td></tr>"
            else:rows="<tr><td>Unknown Item Type</td></tr>";item_type_name="Unknown"
            html_content=f"<div style='font-family:\"Segoe UI\",Arial,sans-serif;font-size:9pt;line-height:1.5;'><h4 style='margin:0 0 5px 0;padding:2px 0;color:{COLOR_ACCENT_PRIMARY};border-bottom:1px solid {COLOR_BORDER_LIGHT};'>Type: {item_type_name}</h4><table style='width:100%;border-collapse:collapse;'>{rows}</table></div>"
        elif len(sel)>1:html_content=f"<i><b>{len(sel)} items selected.</b><br>Select a single item to view/edit properties.</i>";item_type_tt=f"{len(sel)} items"
        else:html_content="<i>No item selected.</i><br><small>Click an item or use tools to add new items.</small>"
        self.properties_editor_label.setText(html_content);self.properties_edit_button.setEnabled(edit_enabled);self.properties_edit_button.setToolTip(f"Edit props of selected {item_type_tt}"if edit_enabled else"Select single item to enable editing")
    def _on_edit_selected_item_properties_from_dock(self):sel=self.scene.selectedItems();_=len(sel)==1 and self.scene.edit_item_properties(sel[0])
    def _update_window_title(self):
        fn=os.path.basename(self.current_file_path)if self.current_file_path else"Untitled";title=f"{APP_NAME} - {fn}{' [PySim Running]'if self.py_sim_active else''}{'[*]'if self.isWindowModified()else''}";self.setWindowTitle(title)
        if self.status_label:self.status_label.setText(f"File: {fn}{' *'if self.isWindowModified()else''} | PySim: {'Active'if self.py_sim_active else'Idle'}")
    def _update_save_actions_enable_state(self):self.save_action.setEnabled(self.isWindowModified())
    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo());self.redo_action.setEnabled(self.undo_stack.canRedo())
        ut,rt=self.undo_stack.undoText(),self.undo_stack.redoText();self.undo_action.setText(f"&Undo {ut}"if ut else"&Undo");self.redo_action.setText(f"&Redo {rt}"if rt else"&Redo")
    def _update_matlab_status_display(self,c,m):t=f"MATLAB: {'Connected'if c else'Not Connected'}";tt=f"MATLAB Status: {m}";self.matlab_status_label.setText(t);self.matlab_status_label.setToolTip(tt);ss=f"font-weight:bold;padding:0px 5px;color:{COLOR_PY_SIM_STATE_ACTIVE if c else'#C62828'};";self.matlab_status_label.setStyleSheet(ss);_ ="Initializing"not in m and logger.info("MATLAB Conn: %s",m);self._update_matlab_actions_enabled_state()
    def _update_matlab_actions_enabled_state(self):can_run=self.matlab_connection.connected and not self.py_sim_active;[a.setEnabled(can_run)for a in[self.export_simulink_action,self.run_simulation_action,self.generate_code_action]];self.matlab_settings_action.setEnabled(not self.py_sim_active)
    def _start_matlab_operation(self,op_name):logger.info("MATLAB Op: %s starting...",op_name);self.status_label.setText(f"Running: {op_name}...");self.progress_bar.setVisible(True);self.set_ui_enabled_for_matlab_op(False)
    def _finish_matlab_operation(self):self.progress_bar.setVisible(False);self.status_label.setText("Ready");self.set_ui_enabled_for_matlab_op(True);logger.info("MATLAB Op: Finished.")
    def set_ui_enabled_for_matlab_op(self,e):self.menuBar().setEnabled(e);[c.setEnabled(e)for c in self.findChildren(QToolBar)];self.centralWidget()and self.centralWidget().setEnabled(e);[d.setEnabled(e)for n in["ToolsDock","PropertiesDock","LogDock","PySimDock","AIChatbotDock"]if(d:=self.findChild(QDockWidget,n))];self._update_py_simulation_actions_enabled_state()
    def _handle_matlab_modelgen_or_sim_finished(self,s,m,d):self._finish_matlab_operation();ll=logging.INFO if s else logging.ERROR;logging.log(ll,"MATLAB Result: %s",m);_=s and(("Model generation"in m and d and(self.last_generated_model_path:=d,QMessageBox.information(self,"Simulink Model Generation",f"Model generated:\n{d}")))or("Simulation"in m and QMessageBox.information(self,"Simulation Complete",f"MATLAB sim finished.\n{m}")))or QMessageBox.warning(self,"MATLAB Op Failed",m)
    def _handle_matlab_codegen_finished(self,s,m,od):
        self._finish_matlab_operation();ll=logging.INFO if s else logging.ERROR;logging.log(ll,"MATLAB Code Gen: %s",m)
        if s and od:
            mb=QMessageBox(self);mb.setIcon(QMessageBox.Information);mb.setWindowTitle("Code Gen Successful");mb.setTextFormat(Qt.RichText);aod=os.path.abspath(od)
            mb.setText(f"Code gen complete.<br>Output: <a href='file:///{aod}'>{aod}</a>");mb.setTextInteractionFlags(Qt.TextBrowserInteraction)
            ob=mb.addButton("Open Directory",QMessageBox.ActionRole);mb.addButton(QMessageBox.Ok);mb.exec_()
            if mb.clickedButton()==ob and not QDesktopServices.openUrl(QUrl.fromLocalFile(aod)):logger.error("Err opening dir %s",aod);QMessageBox.warning(self,"Err Open Dir",f"Could not open:\n{aod}")
        elif not s:QMessageBox.warning(self,"Code Gen Failed",m)
    def _prompt_save_if_dirty(self)->bool:
        if not self.isWindowModified():return True
        if self.py_sim_active:QMessageBox.warning(self,"Sim Active","Stop Python sim before save/open.");return False
        fn=os.path.basename(self.current_file_path)if self.current_file_path else"Untitled";r=QMessageBox.question(self,"Save Changes?",f"'{fn}' has unsaved changes.\nSave before continuing?",QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Save)
        return self.on_save_file()if r==QMessageBox.Save else r!=QMessageBox.Cancel
    def on_new_file(self,silent=False):
        if not silent and not self._prompt_save_if_dirty():return False
        self.on_stop_py_simulation(silent=True);self.scene.clear();self.scene.setSceneRect(0,0,6000,4500);self.current_file_path=None;self.last_generated_model_path=None;self.undo_stack.clear();self.scene.set_dirty(False);self.setWindowModified(False)
        self._update_window_title();self._update_undo_redo_actions_enable_state();_ =not silent and(logger.info("New diagram created."),self.status_label.setText("New diagram. Ready."))
        self.view.resetTransform();self.view.centerOn(self.scene.sceneRect().center());hasattr(self,'select_mode_action')and self.select_mode_action.trigger();return True
    def on_open_file(self):
        if not self._prompt_save_if_dirty(): return
        self.on_stop_py_simulation(silent=True)
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)
        if file_path:
            logger.info("Attempting to open file: %s", file_path)
            if self._load_from_path(file_path):
                self.current_file_path = file_path; self.last_generated_model_path = None
                self.undo_stack.clear(); self.scene.set_dirty(False); self.setWindowModified(False)
                self._update_window_title(); self._update_undo_redo_actions_enable_state()
                logging.info("Successfully opened: %s", file_path); self.status_label.setText(f"Opened: {os.path.basename(file_path)}")
                # --- Security Warning on Open ---
                QMessageBox.information(self, "Security Notice",
                                        "The loaded BSM file may contain Python code for actions and conditions. "
                                        "This code will be executed during Python simulation.\n\n"
                                        "Ensure you trust the source of this file.",
                                        QMessageBox.Ok)
                # --- End Security Warning ---
                items_bounds = self.scene.itemsBoundingRect()
                if not items_bounds.isEmpty(): self.view.fitInView(items_bounds.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)
                else: self.view.resetTransform(); self.view.centerOn(self.scene.sceneRect().center())
            else: QMessageBox.critical(self, "Error Opening File", f"Could not load file: {file_path}"); logger.error("Failed to open file: %s", file_path)
    def _load_from_path(self,file_path):
        try:
            with open(file_path,'r',encoding='utf-8')as f:data=json.load(f)
            if not isinstance(data,dict)or('states'not in data or'transitions'not in data):logger.error("Invalid BSM format: %s",file_path);return False
            self.scene.load_diagram_data(data);return True
        except json.JSONDecodeError as e:logger.error("JSON Decode Error %s: %s",file_path,e);return False
        except Exception as e:logger.error("Load Error %s: %s: %s",file_path,type(e).__name__,e,exc_info=True);return False
    def on_save_file(self)->bool:return self._save_to_path(self.current_file_path)if self.current_file_path else self.on_save_file_as()
    def on_save_file_as(self)->bool:
        start_path=self.current_file_path or os.path.join(QDir.homePath(),"untitled"+FILE_EXTENSION)
        file_path,_=QFileDialog.getSaveFileName(self,"Save BSM File As",start_path,FILE_FILTER)
        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION):file_path+=FILE_EXTENSION
            if self._save_to_path(file_path):self.current_file_path=file_path;self.scene.set_dirty(False);self.setWindowModified(False);self._update_window_title();return True
        return False
    def _save_to_path(self,file_path)->bool:
        if self.py_sim_active:QMessageBox.warning(self,"Sim Active","Stop Python sim before saving.");return False
        save_file=QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly|QIODevice.Text):err=save_file.errorString();logger.error("Err open save %s: %s",file_path,err);QMessageBox.critical(self,"Save Error",f"Failed to open for saving:\n{err}");return False
        try:
            data=self.scene.get_diagram_data();json_data=json.dumps(data,indent=4,ensure_ascii=False)
            if save_file.write(json_data.encode('utf-8'))==-1:err=save_file.errorString();logger.error("Err write %s: %s",file_path,err);QMessageBox.critical(self,"Save Error",f"Failed to write data:\n{err}");save_file.cancelWriting();return False
            if not save_file.commit():err=save_file.errorString();logger.error("Err commit %s: %s",file_path,err);QMessageBox.critical(self,"Save Error",f"Failed to commit save:\n{err}");return False
            logger.info("File saved: %s",file_path);self.status_label.setText(f"Saved: {os.path.basename(file_path)}");self.scene.set_dirty(False);self.setWindowModified(False);return True
        except Exception as e:logger.error("Err saving %s: %s: %s",file_path,type(e).__name__,e,exc_info=True);QMessageBox.critical(self,"Save Error",f"Error during saving:\n{e}");save_file.cancelWriting();return False
    def on_select_all(self):self.scene.select_all()
    def on_delete_selected(self):self.scene.delete_selected_items()
    def on_export_simulink(self):
        if not self.matlab_connection.connected:QMessageBox.warning(self,"MATLAB Not Connected","MATLAB not connected.");return
        if self.py_sim_active:QMessageBox.warning(self,"PySim Active","Stop Python sim before export.");return
        dialog=QDialog(self);dialog.setWindowTitle("Export to Simulink");dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp,"->M"));layout=QFormLayout(dialog);layout.setSpacing(8);layout.setContentsMargins(10,10,10,10)
        base_name=os.path.splitext(os.path.basename(self.current_file_path))[0]if self.current_file_path else"BSM_Model";model_def="".join(c if c.isalnum()or c=='_'else'_'for c in base_name);model_def="Mdl_"+model_def if not model_def or not model_def[0].isalpha()else model_def.replace('-','_')
        model_name_edit=QLineEdit(model_def);layout.addRow("Simulink Model Name:",model_name_edit)
        out_dir_def=os.path.dirname(self.current_file_path)if self.current_file_path else QDir.homePath();output_dir_edit=QLineEdit(out_dir_def)
        browse_btn=QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw")," Browse...");browse_btn.clicked.connect(lambda:output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog,"Select Output Dir",output_dir_edit.text())or output_dir_edit.text()))
        dir_layout=QHBoxLayout();dir_layout.addWidget(output_dir_edit,1);dir_layout.addWidget(browse_btn);layout.addRow("Output Directory:",dir_layout)
        btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);btns.accepted.connect(dialog.accept);btns.rejected.connect(dialog.reject);layout.addRow(btns);dialog.setMinimumWidth(450)
        if dialog.exec_()==QDialog.Accepted:
            model_name,output_dir=model_name_edit.text().strip(),output_dir_edit.text().strip()
            if not model_name or not output_dir:QMessageBox.warning(self,"Input Error","Model name and output dir required.");return
            if not model_name[0].isalpha()or not all(c.isalnum()or c=='_'for c in model_name):QMessageBox.warning(self,"Invalid Model Name","Model name must start with letter, alphanumeric/underscores only.");return
            try:os.makedirs(output_dir,exist_ok=True)
            except OSError as e:QMessageBox.critical(self,"Directory Error",f"Could not create dir:\n{e}");return
            diag_data=self.scene.get_diagram_data()
            if not diag_data['states']:QMessageBox.information(self,"Empty Diagram","Cannot export: no states.");return
            self._start_matlab_operation(f"Exporting '{model_name}' to Simulink");self.matlab_connection.generate_simulink_model(diag_data['states'],diag_data['transitions'],output_dir,model_name)
    def on_run_simulation(self):
        if not self.matlab_connection.connected:QMessageBox.warning(self,"MATLAB Not Connected","MATLAB not connected.");return
        if self.py_sim_active:QMessageBox.warning(self,"PySim Active","Stop Python sim first.");return
        def_dir=os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath());model_path,_=QFileDialog.getOpenFileName(self,"Select Simulink Model",def_dir,"Simulink Models (*.slx);;All Files (*)")
        if not model_path:return
        self.last_generated_model_path=model_path;sim_time,ok=QInputDialog.getDouble(self,"Simulation Time","Stop time (s):",10.0,0.001,86400.0,3)
        if not ok:return
        self._start_matlab_operation(f"Running Simulink sim for '{os.path.basename(model_path)}'");self.matlab_connection.run_simulation(model_path,sim_time)
    def on_generate_code(self):
        if not self.matlab_connection.connected:QMessageBox.warning(self,"MATLAB Not Connected","MATLAB not connected.");return
        if self.py_sim_active:QMessageBox.warning(self,"PySim Active","Stop Python sim first.");return
        def_dir=os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath());model_path,_=QFileDialog.getOpenFileName(self,"Select Simulink Model for Code Gen",def_dir,"Simulink Models (*.slx);;All Files (*)")
        if not model_path:return
        self.last_generated_model_path=model_path;dialog=QDialog(self);dialog.setWindowTitle("Code Gen Options");dialog.setWindowIcon(get_standard_icon(QStyle.SP_DialogSaveButton,"Cde"));layout=QFormLayout(dialog);layout.setSpacing(8);layout.setContentsMargins(10,10,10,10)
        lang_combo=QComboBox();lang_combo.addItems(["C","C++"]);lang_combo.setCurrentText("C++");layout.addRow("Target Language:",lang_combo)
        output_dir_edit=QLineEdit(os.path.dirname(model_path));browse_btn=QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw")," Browse...");browse_btn.clicked.connect(lambda:output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog,"Select Base Output Dir",output_dir_edit.text())or output_dir_edit.text()))
        dir_layout=QHBoxLayout();dir_layout.addWidget(output_dir_edit,1);dir_layout.addWidget(browse_btn);layout.addRow("Base Output Directory:",dir_layout)
        btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);btns.accepted.connect(dialog.accept);btns.rejected.connect(dialog.reject);layout.addRow(btns);dialog.setMinimumWidth(450)
        if dialog.exec_()==QDialog.Accepted:
            lang,out_dir_base=lang_combo.currentText(),output_dir_edit.text().strip()
            if not out_dir_base:QMessageBox.warning(self,"Input Error","Base output dir required.");return
            try:os.makedirs(out_dir_base,exist_ok=True)
            except OSError as e:QMessageBox.critical(self,"Directory Error",f"Could not create dir:\n{e}");return
            self._start_matlab_operation(f"Generating {lang} code for '{os.path.basename(model_path)}'");self.matlab_connection.generate_code(model_path,lang,out_dir_base)
    def on_matlab_settings(self):_=self.py_sim_active and QMessageBox.warning(self,"PySim Active","Stop Python sim first.")or MatlabSettingsDialog(self.matlab_connection,self).exec_()
    def _get_bundled_file_path(self,filename:str)->str|None:
        try:base_path=sys._MEIPASS if getattr(sys,'frozen',False)and hasattr(sys,'_MEIPASS')else os.path.dirname(sys.executable)if getattr(sys,'frozen',False)else os.path.dirname(os.path.abspath(__file__))
            paths=[os.path.join(base_path,filename),os.path.join(base_path,'docs',filename),os.path.join(base_path,'resources',filename),os.path.join(base_path,'examples',filename)]
            for p in paths:
                if os.path.exists(p):return p
            dp=os.path.join(base_path,filename);return dp if os.path.exists(dp)else(logger.warning("Bundled file '%s' not found near %s.",filename,base_path),None)[1]
        except Exception as e:logger.error("Err determining bundled path for '%s': %s",filename,e,exc_info=True);return None
    def _open_example_file(self,filename:str):
        if not self._prompt_save_if_dirty():return
        ex_path=self._get_bundled_file_path(filename)
        if ex_path and os.path.exists(ex_path):
            logger.info("Opening example: %s",ex_path)
            if self._load_from_path(ex_path):self.current_file_path=ex_path;self.last_generated_model_path=None;self.undo_stack.clear();self.scene.set_dirty(False);self.setWindowModified(False);self._update_window_title();self._update_undo_redo_actions_enable_state();logging.info("Opened example: %s",filename);self.status_label.setText(f"Opened example: {filename}");bounds=self.scene.itemsBoundingRect();_=not bounds.isEmpty()and self.view.fitInView(bounds.adjusted(-50,-50,50,50),Qt.KeepAspectRatio)or(self.view.resetTransform(),self.view.centerOn(self.scene.sceneRect().center()))
            else:QMessageBox.critical(self,"Error Opening Example",f"Could not load example: {filename}");logger.error("Failed to open example: %s",filename)
        else:QMessageBox.warning(self,"Example Not Found",f"Example '{filename}' not found.");logger.warning("Example '%s' not found at: %s",filename,ex_path)
    def on_show_quick_start(self):guide_path=self._get_bundled_file_path("QUICK_START.html");_=guide_path and(not QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path))and(QMessageBox.warning(self,"Could Not Open Guide",f"Failed to open quick start guide '{guide_path}'."),logger.warning("Failed to open guide: %s",guide_path)))or QMessageBox.information(self,"Quick Start Not Found","Quick start guide not found.")
    def on_about(self):QMessageBox.about(self,"About "+APP_NAME,f"<h3 style='color:{COLOR_ACCENT_PRIMARY};'>{APP_NAME} v{APP_VERSION}</h3><p>Graphical FSM design, simulation, and code generation tool.</p><ul><li>Visual FSM editing</li><li>Python simulation</li><li>MATLAB/Simulink integration & C/C++ codegen</li><li>AI Assistant</li></ul><p>For research & education. Always verify outputs.</p>")
    def closeEvent(self,event:QCloseEvent):self.on_stop_py_simulation(silent=True);self.internet_check_timer and self.internet_check_timer.isActive()and self.internet_check_timer.stop();self.ai_chatbot_manager and self.ai_chatbot_manager.stop_chatbot();_=self._prompt_save_if_dirty()and(self.matlab_connection and hasattr(self.matlab_connection,'_active_threads')and self.matlab_connection._active_threads and logger.info("Closing. %d MATLAB processes may persist.",len(self.matlab_connection._active_threads)),event.accept())or(event.ignore(),self.internet_check_timer and self.internet_check_timer.start())
    def _init_internet_status_check(self):self.internet_check_timer.timeout.connect(self._run_internet_check_job);self.internet_check_timer.start(15000);QTimer.singleShot(100,self._run_internet_check_job)
    def _run_internet_check_job(self):
        host,port,timeout="8.8.8.8",53,1.5;status=False;msg_detail="Checking..."
        try:s=socket.create_connection((host,port),timeout=timeout);s.close();status=True;msg_detail="Connected"
        except socket.timeout:msg_detail="Disconnected (Timeout)"
        except socket.gaierror:msg_detail="Disconnected (DNS/Net Issue)"
        except OSError:msg_detail="Disconnected (Net Error)"
        if status!=self._internet_connected or self._internet_connected is None:self._internet_connected=status;self._update_internet_status_display(status,msg_detail)
    def _update_internet_status_display(self,is_conn,msg_detail):
        full_text=f"Internet: {msg_detail}";self.internet_status_label.setText(full_text)
        try:host_name=socket.getfqdn('8.8.8.8')if is_conn else'8.8.8.8'
        except:host_name='8.8.8.8'
        self.internet_status_label.setToolTip(f"{full_text} (Checks {host_name}:53)")
        style=f"font-weight:normal;padding:0px 5px;color:{COLOR_PY_SIM_STATE_ACTIVE if is_conn else'#D32F2F'};";self.internet_status_label.setStyleSheet(style);logging.debug("Internet Status: %s",msg_detail)
        hasattr(self.ai_chatbot_manager,'set_online_status')and self.ai_chatbot_manager.set_online_status(is_conn)

    # --- Python Simulation Methods ---
    def _update_py_sim_status_display(self):
        if self.py_sim_active and self.py_fsm_engine:state_name=self.py_fsm_engine.get_current_state_name();self.py_sim_status_label.setText(f"PySim: Active ({state_name})");self.py_sim_status_label.setStyleSheet(f"font-weight:bold;padding:0px 5px;color:{COLOR_PY_SIM_STATE_ACTIVE};")
        else:self.py_sim_status_label.setText("PySim: Idle");self.py_sim_status_label.setStyleSheet("font-weight:normal;padding:0px 5px;")
    def _update_py_simulation_actions_enabled_state(self):
        is_matlab_op=self.progress_bar.isVisible();sim_inactive=not self.py_sim_active
        self.start_py_sim_action.setEnabled(sim_inactive and not is_matlab_op);hasattr(self,'py_sim_start_btn')and self.py_sim_start_btn.setEnabled(sim_inactive and not is_matlab_op)
        sim_ctrls_enabled=self.py_sim_active and not is_matlab_op;[w.setEnabled(sim_ctrls_enabled)for w in[self.stop_py_sim_action,self.reset_py_sim_action]]
        hasattr(self,'py_sim_stop_btn')and self.py_sim_stop_btn.setEnabled(sim_ctrls_enabled);hasattr(self,'py_sim_reset_btn')and self.py_sim_reset_btn.setEnabled(sim_ctrls_enabled)
        hasattr(self,'py_sim_step_btn')and self.py_sim_step_btn.setEnabled(sim_ctrls_enabled);hasattr(self,'py_sim_event_name_edit')and self.py_sim_event_name_edit.setEnabled(sim_ctrls_enabled)
        hasattr(self,'py_sim_trigger_event_btn')and self.py_sim_trigger_event_btn.setEnabled(sim_ctrls_enabled);hasattr(self,'py_sim_event_combo')and self.py_sim_event_combo.setEnabled(sim_ctrls_enabled)
        # Enable/disable the halt checkbox: only when sim is NOT active and no MATLAB op
        if hasattr(self, 'py_sim_halt_on_error_checkbox'): self.py_sim_halt_on_error_checkbox.setEnabled(sim_inactive and not is_matlab_op)

    def set_ui_enabled_for_py_sim(self,is_sim_running:bool):
        self.py_sim_active=is_sim_running;self._update_window_title();is_editable=not is_sim_running
        if is_editable and self.scene.current_mode!="select":self.scene.set_mode("select")
        elif not is_editable:self.scene.set_mode("select")
        for item in self.scene.items():
            if isinstance(item,(GraphicsStateItem,GraphicsCommentItem)):item.setFlag(QGraphicsItem.ItemIsMovable,is_editable)
        actions_toggle=[self.new_action,self.open_action,self.save_action,self.save_as_action,self.undo_action,self.redo_action,self.delete_action,self.select_all_action,self.add_state_mode_action,self.add_transition_mode_action,self.add_comment_mode_action]
        [a.setEnabled(is_editable)for a in actions_toggle if hasattr(a,'setEnabled')]
        hasattr(self,'tools_dock')and self.tools_dock.setEnabled(is_editable)
        if hasattr(self,'properties_edit_button'):self.properties_edit_button.setEnabled(is_editable and len(self.scene.selectedItems())==1)
        self._update_matlab_actions_enabled_state();self._update_py_simulation_actions_enabled_state();self._update_py_sim_status_display()
    def _highlight_sim_active_state(self,state_name_to_highlight:str|None):
        if self._py_sim_currently_highlighted_item:logger.debug("PySim: Unhighlight '%s'",self._py_sim_currently_highlighted_item.text_label);self._py_sim_currently_highlighted_item.set_py_sim_active_style(False);self._py_sim_currently_highlighted_item=None
        if state_name_to_highlight and self.py_fsm_engine:
            leaf_state_name=self.py_fsm_engine.get_current_leaf_state_name()
            top_level_active=self.py_fsm_engine.sm.current_state.id if self.py_fsm_engine.sm and self.py_fsm_engine.sm.current_state else None
            if top_level_active:
                for item in self.scene.items():
                    if isinstance(item,GraphicsStateItem)and item.text_label==top_level_active:logger.debug("PySim: Highlight top '%s'(leaf:'%s')",top_level_active,leaf_state_name);item.set_py_sim_active_style(True);self._py_sim_currently_highlighted_item=item;self.view and not self.view.ensureVisible(item,50,50)and self.view.centerOn(item);break
        self.scene.update()
    def _highlight_sim_taken_transition(self,transition_label_or_id:str|None):
        if self._py_sim_currently_highlighted_transition:hasattr(self._py_sim_currently_highlighted_transition,'set_py_sim_active_style')and self._py_sim_currently_highlighted_transition.set_py_sim_active_style(False);self._py_sim_currently_highlighted_transition=None # type: ignore
        self.scene.update()
    def _update_py_simulation_dock_ui(self):
        if not self.py_fsm_engine or not self.py_sim_active:self.py_sim_current_state_label.setText("<i>Not Running</i>");self.py_sim_variables_table.setRowCount(0);self._highlight_sim_active_state(None);self._highlight_sim_taken_transition(None);self.py_sim_event_combo.clear();self.py_sim_event_combo.addItem("None (Internal Step)");return
        h_state_name=self.py_fsm_engine.get_current_state_name();self.py_sim_current_state_label.setText(f"<b>{html.escape(h_state_name or'N/A')}</b>");self._highlight_sim_active_state(h_state_name)
        main_vars=self.py_fsm_engine.get_variables();all_vars_disp=[]
        [all_vars_disp.append((f"{n}",str(v)))for n,v in sorted(main_vars.items())]
        if self.py_fsm_engine.active_sub_simulator:sub_vars=self.py_fsm_engine.active_sub_simulator.get_variables();[all_vars_disp.append((f"[SUB] {n}",str(v)))for n,v in sorted(sub_vars.items())]
        self.py_sim_variables_table.setRowCount(len(all_vars_disp));[self.py_sim_variables_table.setItem(r,0,QTableWidgetItem(n))or self.py_sim_variables_table.setItem(r,1,QTableWidgetItem(v))for r,(n,v)in enumerate(all_vars_disp)];self.py_sim_variables_table.resizeColumnsToContents()
        curr_combo_txt=self.py_sim_event_combo.currentText();self.py_sim_event_combo.clear();self.py_sim_event_combo.addItem("None (Internal Step)")
        poss_evts=self.py_fsm_engine.get_possible_events_from_current_state();poss_evts and self.py_sim_event_combo.addItems(sorted(list(set(poss_evts))))
        idx=self.py_sim_event_combo.findText(curr_combo_txt);self.py_sim_event_combo.setCurrentIndex(idx if idx!=-1 else 0 if not poss_evts else self.py_sim_event_combo.currentIndex())
    def _append_to_py_simulation_log(self,log_entries:list[str]):
        for entry in log_entries:
            clean=html.escape(entry)
            if any(k in entry for k in["[Code Error]","[Eval Error]","ERROR","SecurityError","HALTED"]):clean=f"<span style='color:red;font-weight:bold;'>{clean}</span>"
            elif any(k in entry for k in["[Safety Check Failed]","[Action Blocked]","[Condition Blocked]"]):clean=f"<span style='color:orange;font-weight:bold;'>{clean}</span>"
            elif any(k in entry for k in["Transitioned from","Reset to state","Simulation started","Entering state","Exiting state"]):clean=f"<span style='color:{COLOR_ACCENT_PRIMARY};font-weight:bold;'>{clean}</span>"
            elif any(k in entry for k in["No eligible transition","event is not allowed"]):clean=f"<span style='color:{COLOR_TEXT_SECONDARY};'>{clean}</span>"
            self.py_sim_action_log_output.append(clean)
        self.py_sim_action_log_output.verticalScrollBar().setValue(self.py_sim_action_log_output.verticalScrollBar().maximum())
        if log_entries:short_log=log_entries[-1].split('\n')[0][:100];imp_kw=["Transitioned from","No eligible transition","ERROR","Reset to state","Simulation started","Simulation stopped","SecurityError","Safety Check Failed","Action Blocked","Condition Blocked","Entering state","Exiting state", "HALTED", "[Code Error]"];any(k in log_entries[-1]for k in imp_kw)and logger.info("PySim: %s",short_log)
    def on_start_py_simulation(self):
        if self.py_sim_active: QMessageBox.information(self, "Simulation Active", "Python simulation is already running."); return
        if self.scene.is_dirty():
            reply = QMessageBox.question(self, "Unsaved Changes", "Diagram has unsaved changes. Start simulation with current in-memory state anyway?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No: return
        diagram_data = self.scene.get_diagram_data()
        if not diagram_data.get('states'): QMessageBox.warning(self, "Empty Diagram", "Cannot start simulation: No states."); return
        try:
            halt_on_err = self.py_sim_halt_on_error_checkbox.isChecked()
            self.py_fsm_engine = FSMSimulator(diagram_data['states'], diagram_data['transitions'], halt_on_action_error=halt_on_err)
            self.set_ui_enabled_for_py_sim(True)
            self.py_sim_action_log_output.clear(); self.py_sim_action_log_output.setHtml("<i>Simulation log...</i>")
            initial_log = ["Python FSM Simulation started."] + self.py_fsm_engine.get_last_executed_actions_log()
            self._append_to_py_simulation_log(initial_log); self._update_py_simulation_dock_ui()
        except Exception as e:
            msg = f"Failed to start Python FSM simulation:\n{e}"; QMessageBox.critical(self, "FSM Init Error", msg)
            self._append_to_py_simulation_log([f"ERROR Starting Sim: {msg}"]); logger.error("PySim: Start failed: %s", e, exc_info=True)
            self.py_fsm_engine = None; self.set_ui_enabled_for_py_sim(False)
    def on_stop_py_simulation(self,silent=False):
        if not self.py_sim_active:return
        self._highlight_sim_active_state(None);self._highlight_sim_taken_transition(None);self.py_fsm_engine=None;self.set_ui_enabled_for_py_sim(False);self._update_py_simulation_dock_ui()
        not silent and self._append_to_py_simulation_log(["Python FSM Simulation stopped."])
    def on_reset_py_simulation(self):
        if not self.py_fsm_engine or not self.py_sim_active:QMessageBox.warning(self,"Sim Not Active","Start simulation first.");return
        try:
            self.py_fsm_engine.reset()
            self.py_sim_action_log_output.append("<hr><i style='color:grey;'>Simulation Reset</i><hr>");
            logs=self.py_fsm_engine.get_last_executed_actions_log();self._append_to_py_simulation_log(logs)
            self._update_py_simulation_dock_ui();self._highlight_sim_taken_transition(None)
        except Exception as e:msg=f"Failed to reset sim:\n{e}";QMessageBox.critical(self,"FSM Reset Error",msg);self._append_to_py_simulation_log([f"ERROR RESET: {msg}"]);logger.error("PySim: Reset failed: %s",e,exc_info=True)
    def on_step_py_simulation(self):
        if not self.py_fsm_engine or not self.py_sim_active:QMessageBox.warning(self,"Sim Not Active","Start sim first.");return
        if self.py_fsm_engine.simulation_halted_flag: self._append_to_py_simulation_log(["[HALTED] Cannot step. Please reset simulation."]); return
        try:_,logs=self.py_fsm_engine.step(event_name=None);self._append_to_py_simulation_log(logs);self._update_py_simulation_dock_ui();self._highlight_sim_taken_transition(None)
        except Exception as e:msg=f"Sim Step Error: {e}";QMessageBox.warning(self,"Sim Step Error",str(e));self._append_to_py_simulation_log([f"ERROR STEP: {msg}"]);logger.error("PySim: Step error: %s",e,exc_info=True)
    def on_trigger_py_event(self):
        if not self.py_fsm_engine or not self.py_sim_active:QMessageBox.warning(self,"Sim Not Active","Start sim first.");return
        if self.py_fsm_engine.simulation_halted_flag: self._append_to_py_simulation_log(["[HALTED] Cannot trigger event. Please reset simulation."]); return
        evt_combo,evt_edit=self.py_sim_event_combo.currentText(),self.py_sim_event_name_edit.text().strip()
        evt_trig=evt_edit if evt_edit else evt_combo if evt_combo and evt_combo!="None (Internal Step)"else None
        if not evt_trig:self.on_step_py_simulation();return
        try:_,logs=self.py_fsm_engine.step(event_name=evt_trig);self._append_to_py_simulation_log(logs);self._update_py_simulation_dock_ui();self.py_sim_event_name_edit.clear();self._highlight_sim_taken_transition(None)
        except Exception as e:msg=f"Sim Event Error ({html.escape(evt_trig)}): {e}";QMessageBox.warning(self,"Sim Event Error",str(e));self._append_to_py_simulation_log([f"ERROR EVENT '{html.escape(evt_trig)}': {msg}"]);logger.error("PySim: Event trigger error for '%s': %s",evt_trig,e,exc_info=True)
    def log_message(self,level_str:str,message:str):level=getattr(logging,level_str.upper(),logging.INFO);logger.log(level,message)

if __name__ == '__main__':
    if hasattr(Qt,'AA_EnableHighDpiScaling'):QApplication.setAttribute(Qt.AA_EnableHighDpiScaling,True)
    if hasattr(Qt,'AA_UseHighDpiPixmaps'):QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps,True)
    app_dir=os.path.dirname(os.path.abspath(__file__));deps_dir=os.path.join(app_dir,"dependencies","icons")
    if not os.path.exists(deps_dir):
        try: os.makedirs(deps_dir,exist_ok=True); print(f"Info: Created dir for QSS icons: {deps_dir}")
        except OSError as e: print(f"Warning: Could not create dir {deps_dir}: {e}")
    app=QApplication(sys.argv);app.setStyleSheet(STYLE_SHEET_GLOBAL);main_win=MainWindow();main_win.show();sys.exit(app.exec_())