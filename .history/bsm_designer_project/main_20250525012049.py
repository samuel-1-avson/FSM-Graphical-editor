
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
import pygraphviz as pgv # Ensure this is installed

# --- Custom Modules ---
# Moved DiagramScene and ZoomableView to graphics_scene.py
from graphics_scene import DiagramScene, ZoomableView
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
from fsm_simulator import FSMSimulator, FSMError
from ai_chatbot import AIChatbotManager
from matlab_integration import MatlabConnection
from dialogs import (StatePropertiesDialog, TransitionPropertiesDialog, CommentPropertiesDialog,
                     MatlabSettingsDialog) # SubFSMEditorDialog is used by StatePropertiesDialog
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
    QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit, # QGraphicsView, QGraphicsScene are base classes
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

        # Initialize AI Chatbot Manager
        self.ai_chatbot_manager = AIChatbotManager(self) # Pass self (MainWindow) as parent
        self.scene = DiagramScene(self.undo_stack, self) # Pass self (MainWindow) as parent_window
        self.scene.modifiedStatusChanged.connect(self.setWindowModified)
        self.scene.modifiedStatusChanged.connect(self._update_window_title)

        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False
        self._py_sim_currently_highlighted_item: GraphicsStateItem | None = None
        self._py_sim_currently_highlighted_transition: GraphicsTransitionItem | None = None # Not yet used for highlighting

        self._internet_connected: bool | None = None # Initialize
        self.internet_check_timer = QTimer(self)

        self.init_ui() # This creates self.log_output

        # Setup global logging AFTER UI elements like log_output are created
        try:
            setup_global_logging(self.log_output) # Pass the QTextEdit widget
            logger.info("Main window initialized and logging configured.")
        except NameError: # Fallback if setup_global_logging somehow isn't defined
            logger.error("Failed to run setup_global_logging. UI logs might not work.")


        # Connect AI Chatbot signals
        self.ai_chatbot_manager.statusUpdate.connect(self._update_ai_chat_status)
        self.ai_chatbot_manager.errorOccurred.connect(self._handle_ai_error)
        self.ai_chatbot_manager.fsmDataReceived.connect(self._handle_fsm_data_from_ai)
        self.ai_chatbot_manager.plainResponseReady.connect(self._handle_plain_ai_response)

        # Set object names for styling or direct access if needed
        self.ai_chat_display.setObjectName("AIChatDisplay")
        self.ai_chat_input.setObjectName("AIChatInput")
        self.ai_chat_send_button.setObjectName("AIChatSendButton")
        self.ai_chat_status_label.setObjectName("AIChatStatusLabel")
        self._update_ai_chat_status("Status: API Key required. Configure in Settings.") # Initial status

        # Status bar labels
        self.matlab_status_label.setObjectName("MatlabStatusLabel")
        self.py_sim_status_label.setObjectName("PySimStatusLabel")
        self.internet_status_label.setObjectName("InternetStatusLabel")
        self.status_label.setObjectName("StatusLabel") # General status

        # Initialize status displays
        self._update_matlab_status_display(False, "Initializing. Configure MATLAB settings or attempt auto-detect.")
        self._update_py_sim_status_display()

        # Connect MATLAB signals
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)

        self._update_window_title()
        self.on_new_file(silent=True) # Start with a clean, untitled diagram
        self._init_internet_status_check() # Start checking internet connectivity
        self.scene.selectionChanged.connect(self._update_properties_dock)
        self._update_properties_dock() # Initial state of properties dock
        self._update_py_simulation_actions_enabled_state() # Initial state of sim actions

        # Set initial AI status based on API key
        if not self.ai_chatbot_manager.api_key:
            self._update_ai_chat_status("Status: API Key required. Configure in Settings.")
        else:
            self._update_ai_chat_status("Status: Ready.")

    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050) # Adjusted for potentially more docks
        self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM")) # Generic desktop icon
        self._create_central_widget()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_docks() # This creates self.log_output
        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()
        self.select_mode_action.trigger() # Start in select mode


    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self)
        self.view.setObjectName("MainDiagramView")
        self.setCentralWidget(self.view)

    def _create_actions(self):
        # Helper for QStyle enums, robust against missing ones in some themes/platforms
        def _safe_get_style_enum(attr_name, fallback_attr_name=None):
            try: return getattr(QStyle, attr_name)
            except AttributeError:
                if fallback_attr_name:
                    try: return getattr(QStyle, fallback_attr_name)
                    except AttributeError: pass
                return QStyle.SP_CustomBase # A very generic fallback

        # File Actions
        self.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "New"), "&New", self, shortcut=QKeySequence.New, statusTip="Create a new file", triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "Opn"), "&Open...", self, shortcut=QKeySequence.Open, statusTip="Open an existing file", triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Sav"), "&Save", self, shortcut=QKeySequence.Save, statusTip="Save the current file", triggered=self.on_save_file)
        self.save_as_action = QAction(get_standard_icon(QStyle.SP_DriveHDIcon),"Save &As...", self, shortcut=QKeySequence.SaveAs, statusTip="Save the current file with a new name", triggered=self.on_save_file_as)
        self.export_simulink_action = QAction(get_standard_icon(_safe_get_style_enum("SP_ArrowUp","SP_ArrowRight"), "->M"), "&Export to Simulink...", self, triggered=self.on_export_simulink)
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

        # Mode Actions
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
        self.select_mode_action.setChecked(True) # Default mode

        # Simulation Actions (MATLAB)
        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation (MATLAB)...", self, triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"), "Generate &Code (C/C++ via MATLAB)...", self, triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"), "&MATLAB Settings...", self, triggered=self.on_matlab_settings)

        # Simulation Actions (Python)
        self.start_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Py▶"), "&Start Python Simulation", self, statusTip="Start internal FSM simulation", triggered=self.on_start_py_simulation)
        self.stop_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaStop, "Py■"), "S&top Python Simulation", self, statusTip="Stop internal FSM simulation", triggered=self.on_stop_py_simulation, enabled=False)
        self.reset_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaSkipBackward, "Py«"), "&Reset Python Simulation", self, statusTip="Reset internal FSM simulation to initial state", triggered=self.on_reset_py_simulation, enabled=False)

        # AI Chatbot Actions
        self.openai_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "AISet"), "AI Assistant Settings...", self, triggered=self.on_openai_settings)
        self.clear_ai_chat_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "Clear"), "Clear Chat History", self, triggered=self.on_clear_ai_chat_history)
        self.ask_ai_to_generate_fsm_action = QAction(QIcon.fromTheme("system-run", get_standard_icon(QStyle.SP_DialogYesButton, "AIGen")), "Generate FSM from Description...", self, triggered=self.on_ask_ai_to_generate_fsm)

        # Help Actions
        self.open_example_menu_action = QAction("Open E&xample...", self) # Placeholder for menu, actual examples added directly
        self.quick_start_action = QAction(get_standard_icon(QStyle.SP_MessageBoxQuestion, "QS"), "&Quick Start Guide", self, triggered=self.on_show_quick_start)
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, triggered=self.on_about)


    def _create_menus(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        example_menu = file_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ex"), "Open E&xample")
        self.open_example_traffic_action = example_menu.addAction("Traffic Light FSM", lambda: self._open_example_file("traffic_light.bsm"))
        self.open_example_toggle_action = example_menu.addAction("Simple Toggle FSM", lambda: self._open_example_file("simple_toggle.bsm"))
        # Add more examples here if needed
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_simulink_action)
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

        # View Menu (for toggling docks)
        self.view_menu = menu_bar.addMenu("&View") # Actions added when docks are created

        # AI Assistant Menu
        ai_menu = menu_bar.addMenu("&AI Assistant")
        ai_menu.addAction(self.ask_ai_to_generate_fsm_action)
        ai_menu.addAction(self.clear_ai_chat_action)
        ai_menu.addSeparator()
        ai_menu.addAction(self.openai_settings_action)

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.quick_start_action)
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(22,22) # Standard icon size for toolbars
        tb_style = Qt.ToolButtonTextBesideIcon # Or Qt.ToolButtonIconOnly

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
        edit_toolbar.setToolButtonStyle(tb_style) # Or Qt.ToolButtonIconOnly for smaller toolbar
        edit_toolbar.addAction(self.undo_action)
        edit_toolbar.addAction(self.redo_action)
        edit_toolbar.addSeparator()
        edit_toolbar.addAction(self.delete_action)

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
        sim_toolbar.setToolButtonStyle(tb_style) # Text helps clarify Python vs MATLAB
        sim_toolbar.addAction(self.start_py_sim_action)
        sim_toolbar.addAction(self.stop_py_sim_action)
        sim_toolbar.addAction(self.reset_py_sim_action)
        sim_toolbar.addSeparator()
        sim_toolbar.addAction(self.export_simulink_action) # Can be here or just in File menu
        sim_toolbar.addAction(self.run_simulation_action)
        sim_toolbar.addAction(self.generate_code_action)

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready") # General status
        self.status_bar.addWidget(self.status_label, 1) # Stretch factor 1

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
        self.progress_bar.setRange(0,0) # Indeterminate
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setTextVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)

        # --- Tools Dock (Drag & Drop, Modes) ---
        self.tools_dock = QDockWidget("Tools", self)
        self.tools_dock.setObjectName("ToolsDock")
        self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_widget_main = QWidget()
        tools_widget_main.setObjectName("ToolsDockWidgetContents") # For styling
        tools_main_layout = QVBoxLayout(tools_widget_main)
        tools_main_layout.setSpacing(10)
        tools_main_layout.setContentsMargins(5,5,5,5)

        # Mode Group (using QToolButtons linked to actions)
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

        # Draggable Elements Group
        draggable_group_box = QGroupBox("Drag New Elements")
        draggable_layout = QVBoxLayout()
        draggable_layout.setSpacing(5)
        drag_state_btn = DraggableToolButton(" State", "application/x-bsm-tool", "State")
        drag_state_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))
        drag_initial_state_btn = DraggableToolButton(" Initial State", "application/x-bsm-tool", "Initial State")
        drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt")) # Placeholder icon
        drag_final_state_btn = DraggableToolButton(" Final State", "application/x-bsm-tool", "Final State")
        drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt")) # Placeholder icon
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

        # --- Properties Dock ---
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
        properties_layout.addWidget(self.properties_editor_label, 1) # Allow label to take more space
        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"),"Edit Properties")
        self.properties_edit_button.setEnabled(False)
        self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock)
        properties_layout.addWidget(self.properties_edit_button)
        self.properties_dock.setWidget(properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        self.view_menu.addAction(self.properties_dock.toggleViewAction())

        # --- Log Dock ---
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(5,5,5,5)
        self.log_output = QTextEdit() # This is where logs go
        self.log_output.setObjectName("LogOutput") # For styling
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)
        self.log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.view_menu.addAction(self.log_dock.toggleViewAction())

        # --- Python Simulation Dock ---
        self.py_sim_dock = QDockWidget("Python Simulation", self)
        self.py_sim_dock.setObjectName("PySimDock")
        self.py_sim_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        py_sim_widget = QWidget()
        py_sim_layout = QVBoxLayout(py_sim_widget)
        py_sim_layout.setContentsMargins(5,5,5,5)
        py_sim_layout.setSpacing(5)

        # Controls Group
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

        # Event Trigger Group
        event_group = QGroupBox("Event Trigger")
        event_layout = QHBoxLayout()
        event_layout.setSpacing(5)
        self.py_sim_event_combo = QComboBox() # Populate with possible events
        self.py_sim_event_combo.addItem("None (Internal Step)") # Default option
        self.py_sim_event_combo.setEditable(False) # Usually False, but can be True if users can type any event
        event_layout.addWidget(self.py_sim_event_combo, 1)

        self.py_sim_event_name_edit = QLineEdit()
        self.py_sim_event_name_edit.setPlaceholderText("Custom event name")
        event_layout.addWidget(self.py_sim_event_name_edit, 1)
        self.py_sim_trigger_event_btn = QPushButton(get_standard_icon(QStyle.SP_MediaPlay, "Trg"),"Trigger")
        self.py_sim_trigger_event_btn.clicked.connect(self.on_trigger_py_event) # Connect this
        event_layout.addWidget(self.py_sim_trigger_event_btn)
        event_group.setLayout(event_layout)
        py_sim_layout.addWidget(event_group)

        # Current State Group
        state_group = QGroupBox("Current State")
        state_layout = QVBoxLayout()
        self.py_sim_current_state_label = QLabel("<i>Not Running</i>")
        self.py_sim_current_state_label.setStyleSheet("font-size: 9pt; padding: 3px;")
        state_layout.addWidget(self.py_sim_current_state_label)
        state_group.setLayout(state_layout)
        py_sim_layout.addWidget(state_group)

        # Variables Group
        variables_group = QGroupBox("Variables")
        variables_layout = QVBoxLayout()
        self.py_sim_variables_table = QTableWidget()
        self.py_sim_variables_table.setRowCount(0); self.py_sim_variables_table.setColumnCount(2)
        self.py_sim_variables_table.setHorizontalHeaderLabels(["Name", "Value"])
        self.py_sim_variables_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.py_sim_variables_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.py_sim_variables_table.setEditTriggers(QAbstractItemView.NoEditTriggers) # Read-only
        variables_layout.addWidget(self.py_sim_variables_table)
        variables_group.setLayout(variables_layout)
        py_sim_layout.addWidget(variables_group)

        # Action Log Group
        log_group = QGroupBox("Action Log")
        log_layout = QVBoxLayout()
        self.py_sim_action_log_output = QTextEdit()
        self.py_sim_action_log_output.setReadOnly(True)
        self.py_sim_action_log_output.setObjectName("PySimActionLog") # For styling
        self.py_sim_action_log_output.setHtml("<i>Simulation log will appear here...</i>")
        log_layout.addWidget(self.py_sim_action_log_output)
        log_group.setLayout(log_layout)
        py_sim_layout.addWidget(log_group, 1) # Allow log to take more space

        self.py_sim_dock.setWidget(py_sim_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock)
        self.view_menu.addAction(self.py_sim_dock.toggleViewAction())

        # --- AI Chatbot Dock ---
        self.ai_chatbot_dock = QDockWidget("AI Chatbot", self)
        self.ai_chatbot_dock.setObjectName("AIChatbotDock")
        self.ai_chatbot_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        ai_chat_widget = QWidget()
        ai_chat_layout = QVBoxLayout(ai_chat_widget)
        ai_chat_layout.setContentsMargins(5,5,5,5)
        ai_chat_layout.setSpacing(5)
        self.ai_chat_display = QTextEdit() # For chat history
        self.ai_chat_display.setReadOnly(True)
        self.ai_chat_display.setStyleSheet("font-size: 9pt; padding: 5px;") # Basic styling
        self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
        ai_chat_layout.addWidget(self.ai_chat_display, 1) # Allow display to take more space

        input_layout = QHBoxLayout()
        self.ai_chat_input = QLineEdit() # For user input
        self.ai_chat_input.setPlaceholderText("Type your message to the AI...")
        self.ai_chat_input.returnPressed.connect(self.on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_input, 1)
        self.ai_chat_send_button = QPushButton(get_standard_icon(QStyle.SP_ArrowForward, "Snd"),"Send") # Send button
        self.ai_chat_send_button.clicked.connect(self.on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_send_button)
        ai_chat_layout.addLayout(input_layout)

        self.ai_chat_status_label = QLabel("Status: Initializing...") # For AI status updates
        self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;")
        ai_chat_layout.addWidget(self.ai_chat_status_label)

        self.ai_chatbot_dock.setWidget(ai_chat_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock)
        self.view_menu.addAction(self.ai_chatbot_dock.toggleViewAction())

        # Tabify docks on the right
        self.tabifyDockWidget(self.properties_dock, self.ai_chatbot_dock)
        self.tabifyDockWidget(self.ai_chatbot_dock, self.py_sim_dock) # AI then PySim


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
        elif ok: # User pressed OK but description was empty
            QMessageBox.warning(self, "Empty Description", "Please provide a description for the FSM.")

    def _handle_fsm_data_from_ai(self, fsm_data: dict, source_message: str):
        logger.info("AI: Received FSM data. Source: '%s...'", source_message[:30])
        self._append_to_ai_chat_display("AI", f"Received FSM structure. (Source: {source_message[:30]}...) Adding to diagram.")

        if not fsm_data or (not fsm_data.get('states') and not fsm_data.get('transitions')):
            logger.error("AI: Returned empty or invalid FSM data structure.")
            self._update_ai_chat_status("Status: AI returned no FSM data.")
            self._append_to_ai_chat_display("System", "AI did not return a valid FSM structure to draw.")
            return

        # Ask user whether to clear or add to existing diagram
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("Add AI Generated FSM")
        msg_box.setText("AI has generated an FSM. Do you want to clear the current diagram before adding the new FSM, or add to the existing one?")
        
        clear_button = msg_box.addButton("Clear and Add", QMessageBox.AcceptRole) # YesRole is more standard for Yes
        add_to_existing_button = msg_box.addButton("Add to Existing", QMessageBox.AcceptRole) # NoRole for No
        cancel_button = msg_box.addButton("Cancel", QMessageBox.RejectRole) # RejectRole for Cancel
        msg_box.setDefaultButton(cancel_button) # Default to cancel
        msg_box.exec_()
        
        clicked_button = msg_box.clickedButton()
        reply = -1 # Default to indicate no valid choice or cancel
        if clicked_button == clear_button: reply = 0
        elif clicked_button == add_to_existing_button: reply = 1
        elif clicked_button == cancel_button: reply = 2

        if reply == 2 or reply == -1: # User cancelled or closed dialog
            logger.info("AI: User cancelled adding AI generated FSM.")
            self._update_ai_chat_status("Status: FSM generation cancelled by user.")
            return
        
        clear_current = (reply == 0)
        self._add_fsm_data_to_scene(fsm_data, clear_current_diagram=clear_current, original_user_prompt=source_message)
        self._update_ai_chat_status("Status: FSM added to diagram.")
        logger.info("AI: FSM data from AI processed and added to scene.")
        
    def _handle_plain_ai_response(self, ai_message: str):
        logger.info("AI: Received plain AI response.")
        self._append_to_ai_chat_display("AI", ai_message)

    def on_send_ai_chat_message(self):
        message = self.ai_chat_input.text().strip()
        if not message: return

        self.ai_chat_input.clear()
        self._append_to_ai_chat_display("You", message)
        self.ai_chatbot_manager.send_message(message) # Send to manager
        self._update_ai_chat_status("Status: Sending message...")

    def _add_fsm_data_to_scene(self, fsm_data: dict, clear_current_diagram: bool = False, original_user_prompt: str = "AI Generated FSM"):
        logger.info("AI: ADD_FSM_TO_SCENE clear_current_diagram=%s", clear_current_diagram)
        logger.debug("AI: Received FSM Data (states: %d, transitions: %d)", 
                     len(fsm_data.get('states',[])), len(fsm_data.get('transitions',[])))

        if clear_current_diagram:
            if not self.on_new_file(silent=True): # Prompts for save if dirty
                 logger.warning("AI: Clearing diagram cancelled by user (save prompt). Cannot add AI FSM.")
                 return
            logger.info("AI: Cleared diagram before AI generation.")
        
        if not clear_current_diagram:
            self.undo_stack.beginMacro(f"Add AI FSM: {original_user_prompt[:30]}...")

        state_items_map = {}
        items_to_add_for_undo_command = [] # To group additions into a single undo step if not clearing

        # Layout parameters
        layout_start_x, layout_start_y = 100, 100 # Top-left for the layout bounding box
        items_per_row = 3 # For fallback grid layout
        default_item_width, default_item_height = 120, 60
        padding_x, padding_y = 150, 100
        GV_SCALE = 1.2  # Scale factor for Graphviz coordinates

        # Use Graphviz for layout if available and states are present
        G = pgv.AGraph(directed=True, strict=False) # Strict=False allows parallel edges if AI generates them
        
        # Add nodes to Graphviz graph
        for state_data in fsm_data.get('states', []):
            name = state_data.get('name')
            if name: G.add_node(name, width=default_item_width/72.0, height=default_item_height/72.0) # GV units are inches

        # Add edges to Graphviz graph
        for trans_data in fsm_data.get('transitions', []):
            source = trans_data.get('source')
            target = trans_data.get('target')
            if source and target and G.has_node(source) and G.has_node(target):
                G.add_edge(source, target, label=trans_data.get('event', ''))
            else:
                logger.warning("AI: Skipping edge due to missing Graphviz node(s): %s->%s", source, target)

        graphviz_positions = {}
        try:
            G.layout(prog="dot") # Use 'dot' for hierarchical layout
            logger.debug("AI: Graphviz layout ('dot') successful.")

            # Extract positions, handling potential errors
            raw_gv_positions = []
            for node in G.nodes():
                try:
                    pos_str = node.attr['pos']
                    parts = pos_str.split(',')
                    if len(parts) == 2:
                        raw_gv_positions.append({'name': node.name, 'x': float(parts[0]), 'y': float(parts[1])})
                    else:
                        logger.warning("AI: Graphviz malformed pos '%s' for node '%s'.", pos_str, node.name)
                except KeyError: # 'pos' attribute missing
                    logger.warning("AI: Graphviz node '%s' has no 'pos' attribute.", node.name)
                except ValueError: # float conversion failed
                    logger.warning("AI: Graphviz cannot parse pos '%s' for node '%s'.", node.attr.get('pos'), node.name)

            if raw_gv_positions:
                # Normalize and scale Graphviz positions (GV y-axis is often inverted)
                min_x_gv = min(p['x'] for p in raw_gv_positions)
                # Max Y for inversion before scaling
                # In Graphviz, Y typically increases downwards. In Qt GraphicsScene, Y increases downwards.
                # So, if GV output is already like Qt, we don't need to invert Y *relative to other Ys*.
                # However, GV's origin might be different.
                # Let's assume GV origin is bottom-left, Qt is top-left for scene coordinates.
                
                # Simpler: find min_y, then use (p_y - min_y) for relative positioning, then scale.
                # If GV's Y increases upwards, then we'd use (max_y_gv - p_y).
                # 'dot' usually has Y increasing downwards in its output coordinate system.
                min_y_gv = min(p['y'] for p in raw_gv_positions)
                # No, 'dot' output usually has Y increasing upwards. So we need to flip.
                max_y_gv = max(p['y'] for p in raw_gv_positions)


                for p_gv in raw_gv_positions:
                    item_w = default_item_width # Use default for layout calculation
                    item_h = default_item_height
                    # Transform GV coordinates to Qt scene coordinates
                    # GV x -> Qt x (scaled, offset)
                    # GV y (increases up) -> Qt y (increases down, scaled, offset)
                    qt_x = (p_gv['x'] - min_x_gv) * GV_SCALE + layout_start_x #- item_w / 2
                    qt_y = (max_y_gv - p_gv['y']) * GV_SCALE + layout_start_y #- item_h / 2
                    graphviz_positions[p_gv['name']] = QPointF(qt_x, qt_y)
            else:
                 logger.warning("AI: Graphviz - No valid positions extracted from nodes.")
        except Exception as e: # Catch broad exceptions from Graphviz layout
            error_msg = str(e).strip() or "Unknown Graphviz error"
            logger.error("AI: Graphviz layout error: %s. Falling back to grid layout.", error_msg, exc_info=True)
            graphviz_positions = {} # Ensure it's empty on error

        # Add states to scene
        for i, state_data in enumerate(fsm_data.get('states', [])):
            name = state_data.get('name')
            if not name:
                logger.warning("AI: State data missing 'name'. Skipping: %s", state_data)
                continue

            item_w = state_data.get('width', default_item_width) # Use provided width if any
            item_h = state_data.get('height', default_item_height)
            
            pos = graphviz_positions.get(name)
            if pos:
                pos_x, pos_y = pos.x(), pos.y()
            else: # Fallback to grid layout
                logger.debug("AI: Using fallback grid layout for state '%s'.", name)
                pos_x = layout_start_x + (i % items_per_row) * (default_item_width + padding_x)
                pos_y = layout_start_y + (i // items_per_row) * (default_item_height + padding_y)

            try:
                state_item = GraphicsStateItem(
                    pos_x, pos_y, item_w, item_h, name,
                    is_initial=state_data.get('is_initial', False),
                    is_final=state_data.get('is_final', False),
                    color=state_data.get('properties', {}).get('color', COLOR_ITEM_STATE_DEFAULT_BG),
                    entry_action=state_data.get('entry_action', ""),
                    during_action=state_data.get('during_action', ""),
                    exit_action=state_data.get('exit_action', ""),
                    description=state_data.get('description', ""), # AI might provide this top-level
                    is_superstate=state_data.get('is_superstate', False),
                    sub_fsm_data=state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]})
                )
                # self.scene.addItem(state_item) # AddItemCommand will do this
                items_to_add_for_undo_command.append(state_item)
                state_items_map[name] = state_item
            except Exception as e:
                logger.error("AI: Error creating GraphicsStateItem '%s': %s", name, e, exc_info=True)

        # Add transitions to scene
        for trans_data in fsm_data.get('transitions', []):
            source_name = trans_data.get('source')
            target_name = trans_data.get('target')

            if not source_name or not target_name:
                logger.warning("AI: Transition missing source/target. Skipping: %s", trans_data)
                continue

            source_item = state_items_map.get(source_name)
            target_item = state_items_map.get(target_name)

            if source_item and target_item:
                try:
                    trans_item = GraphicsTransitionItem(
                        source_item, target_item,
                        event_str=trans_data.get('event', ""),
                        condition_str=trans_data.get('condition', ""),
                        action_str=trans_data.get('action', ""),
                        color=trans_data.get('properties', {}).get('color', COLOR_ITEM_TRANSITION_DEFAULT),
                        description=trans_data.get('description', "") # AI might provide this top-level
                    )
                    # Handle control_offset if provided by AI
                    offset_x = trans_data.get('control_offset_x')
                    offset_y = trans_data.get('control_offset_y')
                    if offset_x is not None and offset_y is not None:
                        try:
                            trans_item.set_control_point_offset(QPointF(float(offset_x), float(offset_y)))
                        except ValueError:
                            logger.warning("AI: Invalid control offsets for transition %s->%s.", source_name, target_name)
                    # self.scene.addItem(trans_item) # AddItemCommand will do this
                    items_to_add_for_undo_command.append(trans_item)
                except Exception as e:
                    logger.error("AI: Error creating GraphicsTransitionItem %s->%s: %s", source_name, target_name, e, exc_info=True)
            else:
                logger.warning("AI: Could not find source ('%s') or target ('%s') for transition. Skipping.", source_name, target_name)

        # Add comments to scene
        # Determine start Y for comments to be below states if not using Graphviz for comments
        max_y_of_laid_out_items = layout_start_y
        if state_items_map: # if any states were laid out
             max_y_of_laid_out_items = max((item.scenePos().y() + item.boundingRect().height() for item in state_items_map.values() if item.scenePos()), default=layout_start_y)
        
        comment_start_y_fallback = max_y_of_laid_out_items + padding_y
        comment_start_x_fallback = layout_start_x

        for i, comment_data in enumerate(fsm_data.get('comments', [])):
            text = comment_data.get('text')
            if not text: continue

            # Use AI provided x, y, width if available, else fallback
            comment_x = comment_data.get('x', comment_start_x_fallback + i * (150 + 20)) # Simple horizontal spread
            comment_y = comment_data.get('y', comment_start_y_fallback)
            comment_width = comment_data.get('width') # Can be None

            try:
                comment_item = GraphicsCommentItem(comment_x, comment_y, text)
                if comment_width is not None:
                    try: comment_item.setTextWidth(float(comment_width))
                    except ValueError: logger.warning("AI: Invalid width '%s' for comment.", comment_width)
                # self.scene.addItem(comment_item) # AddItemCommand will do this
                items_to_add_for_undo_command.append(comment_item)
            except Exception as e:
                logger.error("AI: Error creating GraphicsCommentItem: %s", e, exc_info=True)

        # Use AddItemCommand for all items to make it undoable
        if items_to_add_for_undo_command:
            for item in items_to_add_for_undo_command:
                # Determine a good description for the undo command
                item_type_name = type(item).__name__.replace("Graphics","").replace("Item","")
                cmd_text = f"Add AI {item_type_name}"
                if hasattr(item, 'text_label') and item.text_label: cmd_text += f": {item.text_label}"
                elif hasattr(item, '_compose_label_string'): cmd_text += f" ({item._compose_label_string()})" # For transitions
                # else use default cmd_text
                add_cmd = AddItemCommand(self.scene, item, cmd_text)
                # self.undo_stack.push(add_cmd) # Pushing directly if not using macro, or let macro handle it
                if clear_current_diagram: # If clearing, individual commands are fine (stack was cleared)
                    self.undo_stack.push(add_cmd)
                else: # If adding to existing, they are already part of the macro via AddItemCommand
                    # If not clearing, we want these to be part of the single "Add AI FSM" macro action.
                    # The AddItemCommand will add to scene. We just need to ensure they are part of the current macro.
                    # This logic seems a bit off here if macro is already started.
                    # The `AddItemCommand` itself should be the one pushed to the stack.
                    # The loop here is about *creating* the items.
                    # The command should take the list of items.
                    # --> REVISIT: For now, pushing individual AddItemCommands is okay even in a macro.
                    # The items are added to the scene by AddItemCommand's redo.
                    self.scene.addItem(item) # Add to scene first, then command will re-add if undone/redone
                                            # Or rather, AddItemCommand should add it in its redo.
                                            # So, don't add here if using command.
                    # Correct: just create AddItemCommand, it will handle adding to scene.
                    if not clear_current_diagram: # These were created but not yet added if macro is used
                        self.undo_stack.push(add_cmd) # AddItemCommand.redo will add it
                    else: # If clearing, the scene is clear, so AddItemCommand will add it.
                        self.undo_stack.push(add_cmd)


            logger.info("AI: Added %d items to diagram.", len(items_to_add_for_undo_command))
            QTimer.singleShot(100, self._fit_view_to_new_ai_items) # Fit view after items are added
        else:
            logger.info("AI: No valid items were generated to add to the diagram.")

        if not clear_current_diagram and items_to_add_for_undo_command: # Only end macro if it was started
            self.undo_stack.endMacro()
        elif not clear_current_diagram and not items_to_add_for_undo_command: # Macro was started but nothing added
             self.undo_stack.endMacro() # Still need to end it
             # Check if the last command is an empty macro and remove it
             if self.undo_stack.count() > 0 and self.undo_stack.command(self.undo_stack.count() -1).childCount() == 0:
                 # This is tricky, QUndoStack doesn't directly expose popping.
                 # For simplicity, an empty macro is okay, just does nothing on undo/redo.
                 pass

        # If Python simulation was active, re-initialize it with the new diagram
        if self.py_sim_active and items_to_add_for_undo_command: # Only if something was added
            current_diagram_data = self.scene.get_diagram_data() # Get the updated diagram
            try:
                self.py_fsm_engine = FSMSimulator(current_diagram_data['states'], current_diagram_data['transitions'])
                self._append_to_py_simulation_log(["Python FSM Simulation reinitialized for new diagram from AI."])
                self._update_py_simulation_dock_ui()
            except FSMError as e:
                self._append_to_py_simulation_log([f"ERROR Re-initializing Sim after AI: {e}"])
                self.on_stop_py_simulation(silent=True) # Stop sim if re-init fails

        logger.debug("AI: ADD_FSM_TO_SCENE processing finished. Items queued for undo/redo: %d", len(items_to_add_for_undo_command))


    def _fit_view_to_new_ai_items(self):
        if not self.scene.items(): return
        items_bounds = self.scene.itemsBoundingRect()
        if self.view and not items_bounds.isNull():
            padded_bounds = items_bounds.adjusted(-50, -50, 50, 50) # Add some padding
            self.view.fitInView(padded_bounds, Qt.KeepAspectRatio)
            logger.info("AI: View adjusted to AI generated items.")
        elif self.view and self.scene.sceneRect(): # Fallback to sceneRect center if no items
             self.view.centerOn(self.scene.sceneRect().center())

    def _handle_ai_error(self, error_message: str):
        self._append_to_ai_chat_display("System Error", error_message)
        logger.error("AI Chatbot Error: %s", error_message)
        # Show a shorter version in the status label
        short_error = error_message.split('\n')[0].split(':')[0][:50] # First part of first line
        self._update_ai_chat_status(f"Error: {short_error}...")

    def _update_ai_chat_status(self, status_text: str):
        if hasattr(self, 'ai_chat_status_label'):
            self.ai_chat_status_label.setText(status_text)
            # Determine style based on status
            is_thinking = "thinking..." in status_text.lower() or \
                          "sending..." in status_text.lower() or \
                          "generating..." in status_text.lower()
            is_key_required = "api key required" in status_text.lower() or \
                              "inactive" in status_text.lower() or \
                              "api key error" in status_text.lower() # Added this specific error
            is_error_state = "error" in status_text.lower() or \
                             "failed" in status_text.lower() or \
                             is_key_required # Key required is an error state for operation

            if is_error_state: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: red;")
            elif is_thinking: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: #FF8F00;") # Orange for thinking
            else: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;") # Default

            # Enable/disable UI elements based on status
            can_send = not is_thinking and not is_key_required

            if hasattr(self, 'ai_chat_send_button'): self.ai_chat_send_button.setEnabled(can_send)
            if hasattr(self, 'ai_chat_input'):
                self.ai_chat_input.setEnabled(can_send)
                # Optionally set focus if chatbot is visible and ready
                if can_send and hasattr(self, 'ai_chatbot_dock') and self.ai_chatbot_dock.isVisible() and self.isActiveWindow(): # Check if window is active
                    self.ai_chat_input.setFocus()
            if hasattr(self, 'ask_ai_to_generate_fsm_action'): # Enable/disable menu item
                self.ask_ai_to_generate_fsm_action.setEnabled(can_send)

    def _append_to_ai_chat_display(self, sender: str, message: str):
        timestamp = QTime.currentTime().toString('hh:mm')
        sender_color_hex_str = COLOR_ACCENT_PRIMARY # Default for AI
        if sender == "You": sender_color_hex_str = COLOR_ACCENT_SECONDARY
        elif sender == "System Error" or sender == "System": sender_color_hex_str = "#D32F2F" # Error red

        # Basic Markdown-like formatting to HTML
        escaped_message = html.escape(message)
        # Bold: **text** -> <b>text</b>
        escaped_message = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped_message)
        # Italics: *text* -> <i>text</i> (ensure not part of bold)
        escaped_message = re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'<i>\1</i>', escaped_message) # Avoid * in **
        # Code blocks: ```code``` -> <pre><code>code</code></pre>
        escaped_message = re.sub(r'```(.*?)```', r'<pre><code style="background-color:#f0f0f0; padding:2px 4px; border-radius:3px;">\1</code></pre>', escaped_message, flags=re.DOTALL)
        # Inline code: `code` -> <code>code</code>
        escaped_message = re.sub(r'`(.*?)`', r'<code style="background-color:#f0f0f0; padding:1px 3px; border-radius:2px;">\1</code>', escaped_message)
        escaped_message = escaped_message.replace("\n", "<br>") # Convert newlines

        formatted_html = (
            f"<div style='margin-bottom: 8px;'>"
            f"<span style='font-size:8pt; color:grey;'>[{timestamp}]</span> "
            f"<strong style='color:{sender_color_hex_str};'>{html.escape(sender)}:</strong>"
            f"<div style='margin-top: 3px; padding-left: 5px; border-left: 2px solid {sender_color_hex_str if sender != 'System Error' else '#FFCDD2'};'>{escaped_message}</div>"
            f"</div>"
        )
        self.ai_chat_display.append(formatted_html)
        self.ai_chat_display.ensureCursorVisible() # Scroll to bottom

    def on_openai_settings(self):
        current_key = self.ai_chatbot_manager.api_key if self.ai_chatbot_manager.api_key else ""
        key, ok = QInputDialog.getText(
            self, "OpenAI API Key", "Enter OpenAI API Key (blank to clear):",
            QLineEdit.PasswordEchoOnEdit, current_key # Use PasswordEchoOnEdit for privacy
        )
        if ok:
            new_key = key.strip()
            self.ai_chatbot_manager.set_api_key(new_key if new_key else None)
            if new_key:
                logger.info("AI: OpenAI API Key set/updated.")
                # self._update_ai_chat_status("Status: API Key Set. Ready.") # Manager will emit status
            else:
                logger.info("AI: OpenAI API Key cleared.")
                # self._update_ai_chat_status("Status: API Key cleared. AI Assistant inactive.")

    def on_clear_ai_chat_history(self):
        if self.ai_chatbot_manager:
            self.ai_chatbot_manager.clear_conversation_history()
            if hasattr(self, 'ai_chat_display'): # Check if UI element exists
                self.ai_chat_display.clear()
                self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
            logger.info("AI: Chat history cleared.")
            # self._update_ai_chat_status("Status: Chat history cleared.") # Manager might emit this

    # --- Properties Dock Methods ---
    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems()
        html_content = ""
        edit_enabled = False
        item_type_for_tooltip = "item"

        if len(selected_items) == 1:
            item = selected_items[0]
            props = item.get_data() if hasattr(item, 'get_data') else {}
            item_type_name = type(item).__name__.replace("Graphics", "").replace("Item", "")
            item_type_for_tooltip = item_type_name.lower()
            edit_enabled = True

            # Helper to format property text for display
            def format_prop_text(text_content, max_chars=25):
                if not text_content: return "<i>(none)</i>"
                escaped = html.escape(str(text_content))
                first_line = escaped.split('\n')[0] # Show only first line if multi-line
                if len(first_line) > max_chars or '\n' in escaped:
                    return first_line[:max_chars] + "…" # Ellipsis if too long or multi-line
                return first_line

            rows_html = ""
            if isinstance(item, GraphicsStateItem):
                color_val = props.get('color', COLOR_ITEM_STATE_DEFAULT_BG)
                try: color_obj = QColor(color_val)
                except: color_obj = QColor(COLOR_ITEM_STATE_DEFAULT_BG) # Fallback
                text_on_color = 'black' if color_obj.lightnessF() > 0.5 else 'white'
                color_style = f"background-color:{color_obj.name()}; color:{text_on_color}; padding: 1px 4px; border-radius:2px;"

                rows_html += f"<tr><td><b>Name:</b></td><td>{html.escape(props.get('name', 'N/A'))}</td></tr>"
                rows_html += f"<tr><td><b>Initial:</b></td><td>{'Yes' if props.get('is_initial') else 'No'}</td></tr>"
                rows_html += f"<tr><td><b>Final:</b></td><td>{'Yes' if props.get('is_final') else 'No'}</td></tr>"
                if props.get('is_superstate'):
                     sub_fsm_data = props.get('sub_fsm_data',{})
                     num_sub_states = len(sub_fsm_data.get('states',[]))
                     num_sub_trans = len(sub_fsm_data.get('transitions',[]))
                     rows_html += f"<tr><td><b>Superstate:</b></td><td>Yes ({num_sub_states} sub-states, {num_sub_trans} sub-trans.)</td></tr>"

                rows_html += f"<tr><td><b>Color:</b></td><td><span style='{color_style}'>{html.escape(color_obj.name())}</span></td></tr>"
                rows_html += f"<tr><td><b>Entry:</b></td><td>{format_prop_text(props.get('entry_action', ''))}</td></tr>"
                rows_html += f"<tr><td><b>During:</b></td><td>{format_prop_text(props.get('during_action', ''))}</td></tr>"
                rows_html += f"<tr><td><b>Exit:</b></td><td>{format_prop_text(props.get('exit_action', ''))}</td></tr>"
                if props.get('description'): rows_html += f"<tr><td colspan='2'><b>Desc:</b> {format_prop_text(props.get('description'), 50)}</td></tr>"

            elif isinstance(item, GraphicsTransitionItem):
                color_val = props.get('color', COLOR_ITEM_TRANSITION_DEFAULT)
                try: color_obj = QColor(color_val)
                except: color_obj = QColor(COLOR_ITEM_TRANSITION_DEFAULT)
                text_on_color = 'black' if color_obj.lightnessF() > 0.5 else 'white'
                color_style = f"background-color:{color_obj.name()}; color:{text_on_color}; padding: 1px 4px; border-radius:2px;"

                event_text = html.escape(props.get('event', '')) if props.get('event') else ''
                condition_text = f"[{html.escape(props.get('condition', ''))}]" if props.get('condition') else ''
                action_text = f"/{{{format_prop_text(props.get('action', ''), 15)}}}" if props.get('action') else ''
                label_parts = [p for p in [event_text, condition_text, action_text] if p]
                full_label = " ".join(label_parts) if label_parts else "<i>(No Label)</i>"

                rows_html += f"<tr><td><b>Label:</b></td><td style='font-size:8pt;'>{full_label}</td></tr>"
                rows_html += f"<tr><td><b>From:</b></td><td>{html.escape(props.get('source','N/A'))}</td></tr>"
                rows_html += f"<tr><td><b>To:</b></td><td>{html.escape(props.get('target','N/A'))}</td></tr>"
                rows_html += f"<tr><td><b>Color:</b></td><td><span style='{color_style}'>{html.escape(color_obj.name())}</span></td></tr>"
                rows_html += f"<tr><td><b>Curve:</b></td><td>Bend={props.get('control_offset_x',0):.0f}, Shift={props.get('control_offset_y',0):.0f}</td></tr>"
                if props.get('description'): rows_html += f"<tr><td colspan='2'><b>Desc:</b> {format_prop_text(props.get('description'), 50)}</td></tr>"

            elif isinstance(item, GraphicsCommentItem):
                rows_html += f"<tr><td colspan='2'><b>Text:</b> {format_prop_text(props.get('text', ''), 60)}</td></tr>"
            else:
                rows_html = "<tr><td>Unknown Item Type</td></tr>"
                item_type_name = "Unknown"

            html_content = f"""<div style='font-family: "Segoe UI", Arial, sans-serif; font-size: 9pt; line-height: 1.5;'>
                             <h4 style='margin:0 0 5px 0; padding:2px 0; color: {COLOR_ACCENT_PRIMARY}; border-bottom: 1px solid {COLOR_BORDER_LIGHT};'>Type: {item_type_name}</h4>
                             <table style='width: 100%; border-collapse: collapse;'>{rows_html}</table></div>"""
        elif len(selected_items) > 1:
            html_content = f"<i><b>{len(selected_items)} items selected.</b><br>Select a single item to view/edit its properties.</i>"
            item_type_for_tooltip = f"{len(selected_items)} items"
        else: # No items selected
            html_content = "<i>No item selected.</i><br><small>Click an item in the diagram or use tools to add new items.</small>"

        self.properties_editor_label.setText(html_content)
        self.properties_edit_button.setEnabled(edit_enabled)
        self.properties_edit_button.setToolTip(f"Edit detailed properties of the selected {item_type_for_tooltip}" if edit_enabled else "Select a single item to enable editing")

    def _on_edit_selected_item_properties_from_dock(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1:
            self.scene.edit_item_properties(selected_items[0])

    # --- Window and File Management ---
    def _update_window_title(self):
        title = APP_NAME
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        title += f" - {file_name}"
        if self.py_sim_active: title += " [PySim Running]"
        self.setWindowTitle(title + ("[*]" if self.isWindowModified() else ""))
        # Update general status label as well
        if self.status_label:
            self.status_label.setText(f"File: {file_name}{' *' if self.isWindowModified() else ''} | PySim: {'Active' if self.py_sim_active else 'Idle'}")


    def _update_save_actions_enable_state(self):
        self.save_action.setEnabled(self.isWindowModified())

    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo())
        self.redo_action.setEnabled(self.undo_stack.canRedo())
        # Update text to show what will be undone/redone
        undo_text = self.undo_stack.undoText()
        redo_text = self.undo_stack.redoText()
        self.undo_action.setText(f"&Undo {undo_text}" if undo_text else "&Undo")
        self.redo_action.setText(f"&Redo {redo_text}" if redo_text else "&Redo")

    def _update_matlab_status_display(self, connected, message):
        text = f"MATLAB: {'Connected' if connected else 'Not Connected'}"
        tooltip = f"MATLAB Status: {message}"
        self.matlab_status_label.setText(text)
        self.matlab_status_label.setToolTip(tooltip)
        style_sheet = f"font-weight: bold; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE if connected else '#C62828'};" # Green if connected, Red if not
        self.matlab_status_label.setStyleSheet(style_sheet)
        if "Initializing" not in message: # Don't log initial placeholder message
            logging.info("MATLAB Conn: %s", message)
        self._update_matlab_actions_enabled_state()

    def _update_matlab_actions_enabled_state(self):
        can_run_matlab = self.matlab_connection.connected and not self.py_sim_active
        for action in [self.export_simulink_action, self.run_simulation_action, self.generate_code_action]:
            action.setEnabled(can_run_matlab)
        self.matlab_settings_action.setEnabled(not self.py_sim_active) # Can always open settings unless PySim active

    def _start_matlab_operation(self, operation_name):
        logging.info("MATLAB Operation: %s starting...", operation_name)
        self.status_label.setText(f"Running: {operation_name}...")
        self.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False) # Disable most UI

    def _finish_matlab_operation(self):
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready") # Or previous status
        self.set_ui_enabled_for_matlab_op(True) # Re-enable UI
        logging.info("MATLAB Operation: Finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        self.menuBar().setEnabled(enabled)
        for child in self.findChildren(QToolBar): child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
        # Selectively enable/disable docks
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock"]:
            dock = self.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(enabled)
        # Ensure PySim actions are correctly updated based on its own state too
        self._update_py_simulation_actions_enabled_state() # This will also consider matlab op

    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation()
        log_level = logging.INFO if success else logging.ERROR
        logging.log(log_level, "MATLAB Result: %s", message)
        if success:
            if "Model generation" in message and data:
                self.last_generated_model_path = data
                QMessageBox.information(self, "Simulink Model Generation", f"Simulink model generated successfully:\n{data}")
            elif "Simulation" in message:
                QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else:
            QMessageBox.warning(self, "MATLAB Operation Failed", message)

    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation()
        log_level = logging.INFO if success else logging.ERROR
        logging.log(log_level, "MATLAB Code Gen Result: %s", message)

        if success and output_dir:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText) # Allow HTML for link
            abs_output_dir = os.path.abspath(output_dir)
            msg_box.setText(f"Code generation completed.<br>Output directory: <a href='file:///{abs_output_dir}'>{abs_output_dir}</a>")
            msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction) # Make link clickable
            open_dir_button = msg_box.addButton("Open Directory", QMessageBox.ActionRole)
            msg_box.addButton(QMessageBox.Ok)
            msg_box.exec_()
            if msg_box.clickedButton() == open_dir_button:
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(abs_output_dir)):
                    logging.error("Error opening directory %s", abs_output_dir)
                    QMessageBox.warning(self, "Error Opening Directory", f"Could not open directory:\n{abs_output_dir}")
        elif not success:
            QMessageBox.warning(self, "Code Generation Failed", message)

    def _prompt_save_if_dirty(self) -> bool: # Returns True if safe to proceed, False if cancelled
        if not self.isWindowModified(): return True # Not dirty, safe to proceed

        if self.py_sim_active: # Don't allow save/open/new if sim is running
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python FSM simulation before saving or opening a new file.")
            return False

        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes?",
                                     f"The document '{file_name}' has unsaved changes.\nDo you want to save them before continuing?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save) # Default to Save

        if reply == QMessageBox.Save: return self.on_save_file() # Returns True on successful save, False on cancel/fail
        return reply != QMessageBox.Cancel # True if Discard, False if Cancel

    def on_new_file(self, silent=False): # silent=True to suppress save prompt (used internally)
        if not silent and not self._prompt_save_if_dirty(): return False # User cancelled save prompt

        self.on_stop_py_simulation(silent=True) # Stop sim if running
        self.scene.clear()
        self.scene.setSceneRect(0,0,6000,4500) # Reset scene rect
        self.current_file_path = None
        self.last_generated_model_path = None
        self.undo_stack.clear()
        self.scene.set_dirty(False) # Important: set scene dirty state
        self.setWindowModified(False) # Update window modified state

        self._update_window_title()
        self._update_undo_redo_actions_enable_state()
        if not silent: # Only log/update status if not an internal silent call
            logging.info("New diagram created. Ready.")
            self.status_label.setText("New diagram created. Ready.")
        self.view.resetTransform() # Reset zoom/pan
        self.view.centerOn(self.scene.sceneRect().center())
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger() # Ensure select mode
        return True

    def on_open_file(self):
        if not self._prompt_save_if_dirty(): return

        self.on_stop_py_simulation(silent=True)
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)

        if file_path:
            logging.info("Attempting to open file: %s", file_path)
            if self._load_from_path(file_path):
                self.current_file_path = file_path
                self.last_generated_model_path = None # Reset this
                self.undo_stack.clear() # Clear undo stack for new file
                self.scene.set_dirty(False)
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                logging.info("Successfully opened: %s", file_path)
                self.status_label.setText(f"Opened: {os.path.basename(file_path)}")
                # Fit view to content
                items_bounds = self.scene.itemsBoundingRect()
                if not items_bounds.isEmpty():
                    self.view.fitInView(items_bounds.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)
                else:
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())
            else:
                QMessageBox.critical(self, "Error Opening File", f"Could not load or parse file: {file_path}")
                logging.error("Failed to open file: %s", file_path)

    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Basic validation
            if not isinstance(data, dict) or ('states' not in data or 'transitions' not in data):
                logging.error("Error: Invalid BSM file format in %s.", file_path)
                return False
            self.scene.load_diagram_data(data) # Scene handles populating itself
            return True
        except json.JSONDecodeError as e:
            logging.error("Error decoding JSON from %s: %s", file_path, e)
            return False
        except Exception as e: # Catch other potential errors during load
            logging.error("Error loading file %s: %s: %s", file_path, type(e).__name__, str(e), exc_info=True)
            return False

    def on_save_file(self) -> bool: # Returns True on success, False on failure/cancel
        if not self.current_file_path: # If no current path, treat as Save As
            return self.on_save_file_as()
        return self._save_to_path(self.current_file_path)

    def on_save_file_as(self) -> bool:
        start_path = self.current_file_path if self.current_file_path \
                     else os.path.join(QDir.homePath(), "untitled" + FILE_EXTENSION)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As", start_path, FILE_FILTER)

        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION # Ensure correct extension
            if self._save_to_path(file_path):
                self.current_file_path = file_path # Update current path
                self.scene.set_dirty(False) # Mark as clean after successful save
                self.setWindowModified(False)
                self._update_window_title()
                return True
        return False # Cancelled or failed

    def _save_to_path(self, file_path) -> bool:
        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python FSM simulation before saving.")
            return False

        save_file = QSaveFile(file_path) # Use QSaveFile for atomic saves
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            error_str = save_file.errorString()
            logging.error("Error opening save file %s: %s", file_path, error_str)
            QMessageBox.critical(self, "Save Error", f"Failed to open file for saving:\n{error_str}")
            return False
        try:
            data = self.scene.get_diagram_data()
            json_data = json.dumps(data, indent=4, ensure_ascii=False)
            bytes_written = save_file.write(json_data.encode('utf-8'))
            if bytes_written == -1: # Error during write
                error_str = save_file.errorString()
                logging.error("Error writing data to %s: %s", file_path, error_str)
                QMessageBox.critical(self, "Save Error", f"Failed to write data to file:\n{error_str}")
                save_file.cancelWriting()
                return False

            if not save_file.commit(): # Finalize the save
                error_str = save_file.errorString()
                logging.error("Error committing save to %s: %s", file_path, error_str)
                QMessageBox.critical(self, "Save Error", f"Failed to commit saved file:\n{error_str}")
                return False

            logging.info("File saved successfully: %s", file_path)
            self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            self.scene.set_dirty(False) # Mark as clean
            self.setWindowModified(False)
            return True
        except Exception as e: # Catch other potential errors
            logging.error("Error saving file %s: %s: %s", file_path, type(e).__name__, str(e), exc_info=True)
            QMessageBox.critical(self, "Save Error", f"An error occurred during saving:\n{str(e)}")
            save_file.cancelWriting() # Ensure temp file is discarded
            return False

    def on_select_all(self): self.scene.select_all()
    def on_delete_selected(self): self.scene.delete_selected_items()

    # --- MATLAB/Simulink Methods ---
    def on_export_simulink(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected. Configure in Simulation menu.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before exporting to Simulink.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Export to Simulink")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp, "->M")) # Standard arrow up for export
        layout = QFormLayout(dialog)
        layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)

        # Model Name (Sanitized default)
        default_model_name_base = os.path.splitext(os.path.basename(self.current_file_path))[0] if self.current_file_path else "BSM_Model"
        model_name_default = "".join(c if c.isalnum() or c=='_' else '_' for c in default_model_name_base)
        if not model_name_default or not model_name_default[0].isalpha():
            model_name_default = "Mdl_" + model_name_default # Ensure starts with letter
        model_name_default = model_name_default.replace('-', '_') # Replace hyphens

        model_name_edit = QLineEdit(model_name_default)
        layout.addRow("Simulink Model Name:", model_name_edit)

        # Output Directory
        default_out_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        output_dir_edit = QLineEdit(default_out_dir)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw")," Browse...")
        browse_btn.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(output_dir_edit, 1); dir_layout.addWidget(browse_btn)
        layout.addRow("Output Directory:", dir_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        dialog.setMinimumWidth(450)

        if dialog.exec_() == QDialog.Accepted:
            model_name = model_name_edit.text().strip()
            output_dir = output_dir_edit.text().strip()
            if not model_name or not output_dir:
                QMessageBox.warning(self, "Input Error", "Model name and output directory must be specified.")
                return
            # Validate model name (Simulink requirements)
            if not model_name[0].isalpha() or not all(c.isalnum() or c == '_' for c in model_name):
                QMessageBox.warning(self, "Invalid Model Name", "Model name must start with a letter, and contain only alphanumeric characters or underscores.")
                return
            try: os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create directory:\n{e}")
                return

            diagram_data = self.scene.get_diagram_data()
            if not diagram_data['states']:
                QMessageBox.information(self, "Empty Diagram", "Cannot export: the diagram contains no states.")
                return

            self._start_matlab_operation(f"Exporting '{model_name}' to Simulink")
            self.matlab_connection.generate_simulink_model(diagram_data['states'], diagram_data['transitions'], output_dir, model_name)

    def on_run_simulation(self): # MATLAB simulation
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before running a MATLAB simulation.")
            return

        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model to Simulate", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path # Remember last used model
        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Simulation stop time (seconds):", 10.0, 0.001, 86400.0, 3)
        if not ok: return

        self._start_matlab_operation(f"Running Simulink simulation for '{os.path.basename(model_path)}'")
        self.matlab_connection.run_simulation(model_path, sim_time)

    def on_generate_code(self): # MATLAB codegen
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before generating code via MATLAB.")
            return

        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model for Code Generation", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path
        # --- Code Generation Options Dialog ---
        dialog = QDialog(self)
        dialog.setWindowTitle("Code Generation Options")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"))
        layout = QFormLayout(dialog); layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)

        lang_combo = QComboBox(); lang_combo.addItems(["C", "C++"]); lang_combo.setCurrentText("C++")
        layout.addRow("Target Language:", lang_combo)

        output_dir_edit = QLineEdit(os.path.dirname(model_path)) # Default to model's dir
        browse_btn_codegen = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw")," Browse...")
        browse_btn_codegen.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Base Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
        dir_layout_codegen = QHBoxLayout(); dir_layout_codegen.addWidget(output_dir_edit, 1); dir_layout_codegen.addWidget(browse_btn_codegen)
        layout.addRow("Base Output Directory:", dir_layout_codegen)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        dialog.setMinimumWidth(450)

        if dialog.exec_() == QDialog.Accepted:
            language = lang_combo.currentText()
            output_dir_base = output_dir_edit.text().strip()
            if not output_dir_base:
                QMessageBox.warning(self, "Input Error", "Base output directory required.")
                return
            try: os.makedirs(output_dir_base, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create directory:\n{e}")
                return

            self._start_matlab_operation(f"Generating {language} code for '{os.path.basename(model_path)}'")
            self.matlab_connection.generate_code(model_path, language, output_dir_base)

    def on_matlab_settings(self):
        if self.py_sim_active:
             QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before changing MATLAB settings.")
             return
        MatlabSettingsDialog(self.matlab_connection, self).exec_()

    # --- Help and Example Methods ---
    def _get_bundled_file_path(self, filename: str) -> str | None:
        try:
            # PyInstaller temporary folder
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                base_path = sys._MEIPASS
            # Bundled app (not in _MEIPASS, e.g. one-dir mode or other bundlers)
            elif getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            # Normal script execution
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            
            # Common locations for bundled resources
            possible_paths = [
                os.path.join(base_path, filename),
                os.path.join(base_path, 'docs', filename), # if you have a docs folder
                os.path.join(base_path, 'resources', filename), # common for general resources
                os.path.join(base_path, 'examples', filename) # specific examples folder
            ]
            for path_to_check in possible_paths:
                if os.path.exists(path_to_check):
                    return path_to_check
            # Final check directly in base_path (e.g. if file is at root for some reason)
            direct_path = os.path.join(base_path, filename)
            if os.path.exists(direct_path):
                return direct_path

            logger.warning("Bundled file '%s' not found in expected locations relative to %s.", filename, base_path)
            return None
        except Exception as e: # Catch any error during path determination
            logger.error("Error determining bundled file path for '%s': %s", filename, e, exc_info=True)
            return None

    def _open_example_file(self, filename: str):
        if not self._prompt_save_if_dirty():
            return

        example_file_path = self._get_bundled_file_path(filename) # Use the helper

        if example_file_path and os.path.exists(example_file_path):
            logger.info("Attempting to open example file: %s", example_file_path)
            if self._load_from_path(example_file_path):
                self.current_file_path = example_file_path # Treat it as if opened normally, but it's read-only in bundle
                self.last_generated_model_path = None
                self.undo_stack.clear()
                self.scene.set_dirty(False) # Example files are clean initially
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                logging.info("Successfully opened example: %s", filename)
                self.status_label.setText(f"Opened example: {filename}")
                items_bounds = self.scene.itemsBoundingRect()
                if not items_bounds.isEmpty():
                    self.view.fitInView(items_bounds.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)
                else:
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())
            else:
                QMessageBox.critical(self, "Error Opening Example", f"Could not load or parse example file: {filename}")
                logging.error("Failed to open example file: %s", filename)
        else:
            QMessageBox.warning(self, "Example Not Found", f"The example file '{filename}' could not be found.")
            logging.warning("Example file '%s' not found at expected path: %s", filename, example_file_path)

    def on_show_quick_start(self):
        guide_filename = "QUICK_START.html" # Assuming this is the name
        guide_path = self._get_bundled_file_path(guide_filename)
        if guide_path:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path)):
                QMessageBox.warning(self, "Could Not Open Guide", f"Failed to open the quick start guide using the default application for '{guide_filename}'. Path: {guide_path}")
                logging.warning("Failed to open quick start guide at %s", guide_path)
        else:
            QMessageBox.information(self, "Quick Start Not Found", f"The quick start guide ('{guide_filename}') was not found in the application bundle.")

    def on_about(self):
        about_text = f"""<h3 style='color:{COLOR_ACCENT_PRIMARY};'>{APP_NAME} v{APP_VERSION}</h3>
                         <p>A graphical tool for designing, simulating, and generating code for Finite State Machines (FSMs).</p>
                         <p>Features:</p>
                         <ul>
                             <li>Intuitive FSM diagram creation and editing.</li>
                             <li>Internal Python-based FSM simulation.</li>
                             <li>Integration with MATLAB/Simulink for model export, simulation, and C/C++ code generation.</li>
                             <li>AI Assistant for FSM generation from descriptions and chat-based help.</li>
                         </ul>
                         <p>Developed as a versatile environment for FSM development and education.</p>
                         <p style='font-size:8pt; color:{COLOR_TEXT_SECONDARY};'>
                           This tool is intended for research and educational purposes.
                           Always verify generated models and code.
                         </p>
                      """
        QMessageBox.about(self, "About " + APP_NAME, about_text)

    # --- Application Closing and Status Checks ---
    def closeEvent(self, event: QCloseEvent):
        self.on_stop_py_simulation(silent=True) # Ensure PySim is stopped
        if self.internet_check_timer and self.internet_check_timer.isActive():
            self.internet_check_timer.stop()

        if self.ai_chatbot_manager: # Gracefully stop AI worker
            self.ai_chatbot_manager.stop_chatbot()

        if self._prompt_save_if_dirty(): # Check for unsaved changes
            if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads:
                logging.info("Closing. %d MATLAB processes may persist if not completed.", len(self.matlab_connection._active_threads))
            event.accept()
        else:
            event.ignore()
            # If ignored, restart timers if they were stopped above
            if self.internet_check_timer and not self.internet_check_timer.isActive(): # Check if it was indeed stopped
                self.internet_check_timer.start()


    def _init_internet_status_check(self):
        self.internet_check_timer.timeout.connect(self._run_internet_check_job)
        self.internet_check_timer.start(15000) # Check every 15 seconds
        QTimer.singleShot(100, self._run_internet_check_job) # Initial check soon after start

    def _run_internet_check_job(self):
        host_to_check = "8.8.8.8" # Google's public DNS
        port_to_check = 53      # DNS port
        connection_timeout = 1.5 # seconds

        current_status = False
        status_message_detail = "Checking..."
        try:
            s = socket.create_connection((host_to_check, port_to_check), timeout=connection_timeout)
            s.close()
            current_status = True
            status_message_detail = "Connected"
        except socket.timeout:
            status_message_detail = "Disconnected (Timeout)"
        except socket.gaierror as e: # Address-related error
            status_message_detail = "Disconnected (DNS/Net Issue)"
        except OSError as e: # Other network errors (e.g., network unreachable)
            status_message_detail = "Disconnected (Net Error)"

        # Only update display if status changed or first time
        if current_status != self._internet_connected or self._internet_connected is None:
            self._internet_connected = current_status
            self._update_internet_status_display(current_status, status_message_detail)

    def _update_internet_status_display(self, is_connected: bool, message_detail: str):
        full_status_text = f"Internet: {message_detail}"
        self.internet_status_label.setText(full_status_text)
        try: # Try to get a human-readable name for the host for tooltip
            check_host_name_for_tooltip = socket.getfqdn('8.8.8.8') if is_connected else '8.8.8.8'
        except Exception: check_host_name_for_tooltip = '8.8.8.8'
        self.internet_status_label.setToolTip(f"{full_status_text} (Checks {check_host_name_for_tooltip}:{53})")

        style_sheet = f"font-weight: normal; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE if is_connected else '#D32F2F'};"
        self.internet_status_label.setStyleSheet(style_sheet)
        logging.debug("Internet Status: %s", message_detail) # Log more frequent checks at debug level

        # Notify AI Chatbot Manager about online status
        if hasattr(self.ai_chatbot_manager, 'set_online_status'):
            self.ai_chatbot_manager.set_online_status(is_connected)


    # --- Python Simulation Methods ---
    def _update_py_sim_status_display(self):
        if self.py_sim_active and self.py_fsm_engine:
            state_name = self.py_fsm_engine.get_current_state_name()
            self.py_sim_status_label.setText(f"PySim: Active ({state_name})")
            self.py_sim_status_label.setStyleSheet(f"font-weight: bold; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE};")
        else:
            self.py_sim_status_label.setText("PySim: Idle")
            self.py_sim_status_label.setStyleSheet("font-weight: normal; padding: 0px 5px;") # Default style

    def _update_py_simulation_actions_enabled_state(self):
        is_matlab_op_running = self.progress_bar.isVisible()
        sim_inactive = not self.py_sim_active

        # Start action is enabled if sim is inactive AND no MATLAB op is running
        self.start_py_sim_action.setEnabled(sim_inactive and not is_matlab_op_running)
        if hasattr(self, 'py_sim_start_btn'): self.py_sim_start_btn.setEnabled(sim_inactive and not is_matlab_op_running)

        # Other sim controls are enabled if sim IS active AND no MATLAB op is running
        sim_controls_enabled = self.py_sim_active and not is_matlab_op_running
        for widget in [self.stop_py_sim_action, self.reset_py_sim_action]: widget.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_stop_btn'): self.py_sim_stop_btn.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_reset_btn'): self.py_sim_reset_btn.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_step_btn'): self.py_sim_step_btn.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_event_name_edit'): self.py_sim_event_name_edit.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_trigger_event_btn'): self.py_sim_trigger_event_btn.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_event_combo'): self.py_sim_event_combo.setEnabled(sim_controls_enabled)

    def set_ui_enabled_for_py_sim(self, is_sim_running: bool):
        self.py_sim_active = is_sim_running
        self._update_window_title() # Reflect sim status in title
        is_editable = not is_sim_running # Diagram is editable if sim is NOT running

        # Set scene mode and item movability
        if is_editable and self.scene.current_mode != "select":
            self.scene.set_mode("select") # Default to select mode when editable
        elif not is_editable: # Sim running, force select mode (non-editing)
            self.scene.set_mode("select") # Ensure select mode, no item creation/drag for transitions

        for item in self.scene.items():
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)):
                item.setFlag(QGraphicsItem.ItemIsMovable, is_editable)

        # Enable/disable relevant actions
        actions_to_toggle = [
            self.new_action, self.open_action, self.save_action, self.save_as_action,
            self.undo_action, self.redo_action, self.delete_action, self.select_all_action,
            self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action
        ]
        for action in actions_to_toggle:
            if hasattr(action, 'setEnabled'): action.setEnabled(is_editable)
        
        # Enable/disable docks that allow editing
        if hasattr(self, 'tools_dock'): self.tools_dock.setEnabled(is_editable)
        if hasattr(self, 'properties_edit_button'):
             self.properties_edit_button.setEnabled(is_editable and len(self.scene.selectedItems())==1)

        self._update_matlab_actions_enabled_state() # MATLAB actions might depend on PySim state
        self._update_py_simulation_actions_enabled_state() # Update PySim specific actions
        self._update_py_sim_status_display() # Update status bar

    def _highlight_sim_active_state(self, state_name_to_highlight: str | None):
        # Clear previous highlight
        if self._py_sim_currently_highlighted_item:
            logging.debug("PySim: Unhighlighting state '%s'", self._py_sim_currently_highlighted_item.text_label)
            self._py_sim_currently_highlighted_item.set_py_sim_active_style(False)
            self._py_sim_currently_highlighted_item = None

        # Apply new highlight
        if state_name_to_highlight:
            for item in self.scene.items():
                if isinstance(item, GraphicsStateItem) and item.text_label == state_name_to_highlight:
                    logging.debug("PySim: Highlighting state '%s'", item.text_label)
                    item.set_py_sim_active_style(True)
                    self._py_sim_currently_highlighted_item = item
                    # Ensure the highlighted item is visible
                    if self.view and not self.view.ensureVisible(item, 50, 50): # ensureVisible might not always center
                        self.view.centerOn(item)
                    break
        self.scene.update() # Force repaint if needed

    def _highlight_sim_taken_transition(self, transition_label_or_id: str | None): # Placeholder
        # Clear previous highlight
        if self._py_sim_currently_highlighted_transition:
            if hasattr(self._py_sim_currently_highlighted_transition, 'set_py_sim_active_style'):
                 # Assuming GraphicsTransitionItem will have a similar method
                 self._py_sim_currently_highlighted_transition.set_py_sim_active_style(False) # type: ignore
            self._py_sim_currently_highlighted_transition = None
        # Find and highlight new one (implementation needed if desired)
        # ...
        self.scene.update()


    def _update_py_simulation_dock_ui(self):
        if not self.py_fsm_engine or not self.py_sim_active:
            self.py_sim_current_state_label.setText("<i>Not Running</i>")
            self.py_sim_variables_table.setRowCount(0)
            self._highlight_sim_active_state(None)
            self._highlight_sim_taken_transition(None) # Clear transition highlight
            self.py_sim_event_combo.clear() # Clear event combo
            self.py_sim_event_combo.addItem("None (Internal Step)")
            return

        current_state = self.py_fsm_engine.get_current_state_name()
        self.py_sim_current_state_label.setText(f"<b>{html.escape(current_state or 'N/A')}</b>")
        self._highlight_sim_active_state(current_state) # Highlight current state on diagram

        variables = self.py_fsm_engine.get_variables()
        self.py_sim_variables_table.setRowCount(len(variables))
        for row, (name, value) in enumerate(sorted(variables.items())): # Sort for consistent display
            self.py_sim_variables_table.setItem(row, 0, QTableWidgetItem(str(name)))
            self.py_sim_variables_table.setItem(row, 1, QTableWidgetItem(str(value)))
        self.py_sim_variables_table.resizeColumnsToContents()

        # Update event combo box
        current_combo_text = self.py_sim_event_combo.currentText() # Preserve selection if possible
        self.py_sim_event_combo.clear()
        self.py_sim_event_combo.addItem("None (Internal Step)")
        possible_events = self.py_fsm_engine.get_possible_events_from_current_state() # Get from simulator
        if possible_events:
            self.py_sim_event_combo.addItems(sorted(list(set(possible_events)))) # Add unique, sorted events
        
        index = self.py_sim_event_combo.findText(current_combo_text)
        if index != -1:
            self.py_sim_event_combo.setCurrentIndex(index)
        elif not possible_events: # If no possible events, select "None"
             self.py_sim_event_combo.setCurrentIndex(0)


    def _append_to_py_simulation_log(self, log_entries: list[str]):
        for entry in log_entries:
            # Basic HTML styling for log entries
            cleaned_entry = html.escape(entry)
            if "[Condition]" in entry or "[Eval Error]" in entry or "ERROR" in entry.upper() or "SecurityError" in entry:
                cleaned_entry = f"<span style='color:red; font-weight:bold;'>{cleaned_entry}</span>" # Errors in red
            elif "[Safety Check Failed]" in entry or "[Action Blocked]" in entry or "[Condition Blocked]" in entry:
                cleaned_entry = f"<span style='color:orange; font-weight:bold;'>{cleaned_entry}</span>" # Safety warnings in orange
            elif "Transitioned from" in entry or "Reset to state" in entry or "Simulation started" in entry:
                cleaned_entry = f"<span style='color:{COLOR_ACCENT_PRIMARY}; font-weight:bold;'>{cleaned_entry}</span>" # Key events in theme color
            elif "No eligible transition" in entry:
                cleaned_entry = f"<span style='color:{COLOR_TEXT_SECONDARY};'>{cleaned_entry}</span>" # Muted color for no transition

            self.py_sim_action_log_output.append(cleaned_entry)
        self.py_sim_action_log_output.verticalScrollBar().setValue(self.py_sim_action_log_output.verticalScrollBar().maximum())

        # Log important PySim events to the main log as well for traceability
        if log_entries:
            last_log_short = log_entries[-1].split('\n')[0][:100] # Get a short summary of the last log
            # Keywords for events important enough to also go to main log
            important_keywords = ["Transitioned from", "No eligible transition", "ERROR", "Reset to state", 
                                  "Simulation started", "Simulation stopped", "SecurityError", 
                                  "Safety Check Failed", "Action Blocked", "Condition Blocked"]
            if any(keyword in log_entries[-1] for keyword in important_keywords): # Check last entry for keywords
                logger.info("PySim: %s", last_log_short) 

    def on_start_py_simulation(self):
        if self.py_sim_active:
            QMessageBox.information(self, "Simulation Active", "Python simulation is already running.")
            return
        
        if self.scene.is_dirty():
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "The diagram has unsaved changes that won't be reflected in the simulation unless saved.\nStart simulation with the current in-memory state anyway?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No:
                return

        diagram_data = self.scene.get_diagram_data()
        if not diagram_data.get('states'):
            QMessageBox.warning(self, "Empty Diagram", "Cannot start simulation: The diagram has no states.")
            return
        try:
            self.py_fsm_engine = FSMSimulator(diagram_data['states'], diagram_data['transitions'])
            self.set_ui_enabled_for_py_sim(True) # Disables editing, enables sim controls
            self.py_sim_action_log_output.clear()
            self.py_sim_action_log_output.setHtml("<i>Simulation log will appear here...</i>") # Clear previous log
            initial_log = ["Python FSM Simulation started."] + self.py_fsm_engine.get_last_executed_actions_log()
            self._append_to_py_simulation_log(initial_log)
            self._update_py_simulation_dock_ui() # Update state display, variables, events
        except Exception as e: # Catch errors from FSMSimulator constructor or initial step
            msg = f"Failed to start Python FSM simulation:\n{e}"
            QMessageBox.critical(self, "FSM Initialization Error", msg)
            self._append_to_py_simulation_log([f"ERROR Starting Sim: {msg}"])
            logger.error("PySim: Failed to start Python FSM simulation: %s", e, exc_info=True)
            self.py_fsm_engine = None
            self.set_ui_enabled_for_py_sim(False) # Ensure UI is back to editable state

    def on_stop_py_simulation(self, silent=False):
        if not self.py_sim_active: return

        self._highlight_sim_active_state(None) # Remove highlight
        self._highlight_sim_taken_transition(None)

        self.py_fsm_engine = None
        self.set_ui_enabled_for_py_sim(False) # Re-enables editing
        self._update_py_simulation_dock_ui() # Update UI to reflect stopped state

        if not silent:
            self._append_to_py_simulation_log(["Python FSM Simulation stopped."])

    def on_reset_py_simulation(self):
        if not self.py_fsm_engine or not self.py_sim_active:
            QMessageBox.warning(self, "Simulation Not Active", "Python simulation is not running. Start it first.")
            return
        try:
            self.py_fsm_engine.reset()
            self.py_sim_action_log_output.append("<hr><i style='color:grey;'>Simulation Reset</i><hr>")
            reset_logs = self.py_fsm_engine.get_last_executed_actions_log()
            self._append_to_py_simulation_log(reset_logs)
            self._update_py_simulation_dock_ui()
            self._highlight_sim_taken_transition(None) # Clear any transition highlight
        except Exception as e:
            msg = f"Failed to reset Python FSM simulation:\n{e}"
            QMessageBox.critical(self, "FSM Reset Error", msg)
            self._append_to_py_simulation_log([f"ERROR DURING RESET: {msg}"])
            logging.error("PySim: Failed to reset: %s", e, exc_info=True)


    def on_step_py_simulation(self): # Internal step (no event)
        if not self.py_fsm_engine or not self.py_sim_active:
            QMessageBox.warning(self, "Simulation Not Active", "Python simulation is not running.")
            return
        try:
            _, log_entries = self.py_fsm_engine.step(event_name=None) # Pass None for internal step
            self._append_to_py_simulation_log(log_entries)
            self._update_py_simulation_dock_ui()
            self._highlight_sim_taken_transition(None) # Clear any transition highlight
        except Exception as e:
            msg = f"Simulation Step Error: {e}"
            QMessageBox.warning(self, "Simulation Step Error", str(e))
            self._append_to_py_simulation_log([f"ERROR DURING STEP: {msg}"])
            logging.error("PySim: Step error: %s", e, exc_info=True)


    def on_trigger_py_event(self): # Trigger event from combo or line edit
        if not self.py_fsm_engine or not self.py_sim_active:
            QMessageBox.warning(self, "Simulation Not Active", "Python simulation is not running.")
            return

        event_name_from_combo = self.py_sim_event_combo.currentText()
        event_name_from_edit = self.py_sim_event_name_edit.text().strip()

        event_to_trigger = None
        if event_name_from_edit: # Prioritize line edit if filled
            event_to_trigger = event_name_from_edit
        elif event_name_from_combo and event_name_from_combo != "None (Internal Step)":
            event_to_trigger = event_name_from_combo
        
        if not event_to_trigger: # If still no event, effectively an internal step
            self.on_step_py_simulation() # Call the internal step handler
            return
        
        try:
            _, log_entries = self.py_fsm_engine.step(event_name=event_to_trigger)
            self._append_to_py_simulation_log(log_entries)
            self._update_py_simulation_dock_ui()
            self.py_sim_event_name_edit.clear() # Clear custom event field after use
            self._highlight_sim_taken_transition(None) # Clear any transition highlight
        except Exception as e:
            msg = f"Simulation Event Error ({html.escape(event_to_trigger)}): {e}"
            QMessageBox.warning(self, "Simulation Event Error", str(e))
            self._append_to_py_simulation_log([f"ERROR DURING EVENT '{html.escape(event_to_trigger)}': {msg}"])
            logging.error("PySim: Event trigger error for '%s': %s", event_to_trigger, e, exc_info=True)

    # Helper for DiagramScene logging if it needs to call back to MainWindow
    def log_message(self, level_str: str, message: str):
        # Convert level_str (e.g., "INFO", "ERROR") to logging level
        level = getattr(logging, level_str.upper(), logging.INFO)
        logger.log(level, message) # Use the main application logger


if __name__ == '__main__':
    # High DPI scaling attributes (best practice)
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Ensure "dependencies/icons" exists for QSS (if QSS uses relative paths like "./dependencies/icons/...")
    app_dir = os.path.dirname(os.path.abspath(__file__))
    dependencies_dir = os.path.join(app_dir, "dependencies", "icons")
    if not os.path.exists(dependencies_dir):
        try:
            os.makedirs(dependencies_dir, exist_ok=True)
            # This print is mostly for development; in a bundled app, it's less relevant.
            print(f"Info: Created directory for QSS icons (if needed): {dependencies_dir}")
        except OSError as e:
            print(f"Warning: Could not create directory {dependencies_dir}: {e}")

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET_GLOBAL) # Apply global style
    main_win = MainWindow() # Create main window instance
    main_win.show()
    sys.exit(app.exec_())

 