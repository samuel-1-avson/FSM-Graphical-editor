--- START OF FILE bsm_designer_project/ui_manager.py ---
# bsm_designer_project/ui_manager.py
import os
import json 
from PyQt5.QtWidgets import (
    QMainWindow, QDockWidget, QToolBox, QAction, QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QStatusBar, QTextEdit, QPushButton, QListWidget, QMenu, QActionGroup, QStyle,
    QSizePolicy, QToolButton, QGroupBox, QComboBox, QProgressBar, QFormLayout
)
from PyQt5.QtGui import QIcon, QKeySequence, QColor, QPalette, QFont, QPixmap, QRegion, QCursor
from PyQt5.QtCore import Qt, QSize, QDir, QObject 

from utils import get_standard_icon 
from custom_widgets import DraggableToolButton 
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
    FSM_TEMPLATES_BUILTIN, MIME_TYPE_BSM_TEMPLATE
)
import logging
logger = logging.getLogger(__name__)


class UIManager(QObject): 
    def __init__(self, main_window: QMainWindow):
        super().__init__(main_window) 
        self.mw = main_window

    def setup_ui(self):
        self.mw.setGeometry(50, 50, 1600, 1000) 
        self.mw.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM"))

        self._create_central_widget() 
        self._create_actions()        
        self._create_menus()
        self._create_toolbars()
        self._create_docks()          
        self._create_status_bar()     

        self.mw._update_save_actions_enable_state()
        self.mw._update_matlab_actions_enabled_state()
        self.mw._update_undo_redo_actions_enable_state()
        if hasattr(self.mw, 'select_mode_action'):
            self.mw.select_mode_action.trigger() 

    def _create_central_widget(self):
        self.mw.view.setObjectName("MainDiagramView")
        self.mw.view.setStyleSheet(f"background-color: {COLOR_BACKGROUND_LIGHT}; border: 1px solid {COLOR_BORDER_LIGHT};")
        self.mw.setCentralWidget(self.mw.view)

    def _create_actions(self):
        mw = self.mw

        def _safe_get_style_enum(attr_name, fallback_attr_name=None):
            try: return getattr(QStyle, attr_name)
            except AttributeError:
                if fallback_attr_name:
                    try: return getattr(QStyle, fallback_attr_name)
                    except AttributeError: pass
                return QStyle.SP_CustomBase 

        mw.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "New"), "&New", mw, shortcut=QKeySequence.New, statusTip="Create a new file")
        mw.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "Opn"), "&Open...", mw, shortcut=QKeySequence.Open, statusTip="Open an existing file")
        mw.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Sav"), "&Save", mw, shortcut=QKeySequence.Save, statusTip="Save the current file")
        mw.save_as_action = QAction(
            get_standard_icon(_safe_get_style_enum("SP_DriveHDIcon", "SP_DialogSaveButton"), "SA"),
            "Save &As...", mw, shortcut=QKeySequence.SaveAs,
            statusTip="Save the current file with a new name"
        )
        mw.export_simulink_action = QAction(get_standard_icon(_safe_get_style_enum("SP_ArrowUp","SP_ArrowRight"), "->M"), "&Export to Simulink...", mw)
        mw.generate_c_code_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "CGen"), "Generate &Basic C Code...", mw)
        
        mw.export_plantuml_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "PUML"), "Export to &PlantUML...", mw, statusTip="Export diagram to PlantUML text format")
        mw.export_mermaid_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "MMD"), "Export to &Mermaid...", mw, statusTip="Export diagram to Mermaid text format")
        
        # New Export Actions
        mw.export_png_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "PNG"), "Export to &PNG Image...", mw, statusTip="Export diagram to PNG image")
        mw.export_svg_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "SVG"), "Export to &SVG Image...", mw, statusTip="Export diagram to SVG vector image")


        mw.exit_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", mw, shortcut=QKeySequence.Quit, statusTip="Exit the application", triggered=mw.close)

        mw.undo_action = mw.undo_stack.createUndoAction(mw, "&Undo")
        mw.undo_action.setShortcut(QKeySequence.Undo)
        mw.undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "Un"))
        mw.redo_action = mw.undo_stack.createRedoAction(mw, "&Redo")
        mw.redo_action.setShortcut(QKeySequence.Redo)
        mw.redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "Re"))
        
        mw.select_all_action = QAction(get_standard_icon(_safe_get_style_enum("SP_FileDialogListView", "SP_FileDialogDetailedView"), "All"), "Select &All", mw, shortcut=QKeySequence.SelectAll)
        mw.delete_action = QAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "&Delete", mw, shortcut=QKeySequence.Delete)

        mw.mode_action_group = QActionGroup(mw)
        mw.mode_action_group.setExclusive(True)
        mw.select_mode_action = QAction(QIcon.fromTheme("edit-select", get_standard_icon(QStyle.SP_ArrowRight, "Sel")), "Select/Move", mw, checkable=True, triggered=lambda: mw.scene.set_mode("select"))
        mw.select_mode_action.setObjectName("select_mode_action") 
        mw.select_mode_action.setToolTip("Activate Select/Move mode (S)")
        mw.select_mode_action.setShortcut("S")

        mw.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", get_standard_icon(QStyle.SP_FileDialogNewFolder, "St")), "Add State", mw, checkable=True, triggered=lambda: mw.scene.set_mode("state"))
        mw.add_state_mode_action.setObjectName("add_state_mode_action")
        mw.add_state_mode_action.setToolTip("Activate Add State mode (A)")
        mw.add_state_mode_action.setShortcut("A")

        mw.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", get_standard_icon(QStyle.SP_ArrowForward, "Tr")), "Add Transition", mw, checkable=True, triggered=lambda: mw.scene.set_mode("transition"))
        mw.add_transition_mode_action.setObjectName("add_transition_mode_action")
        mw.add_transition_mode_action.setToolTip("Activate Add Transition mode (T)")
        mw.add_transition_mode_action.setShortcut("T")

        mw.add_comment_mode_action = QAction(QIcon.fromTheme("insert-text", get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm")), "Add Comment", mw, checkable=True, triggered=lambda: mw.scene.set_mode("comment"))
        mw.add_comment_mode_action.setObjectName("add_comment_mode_action")
        mw.add_comment_mode_action.setToolTip("Activate Add Comment mode (C)")
        mw.add_comment_mode_action.setShortcut("C")

        
        mw.preferences_action = QAction(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Prefs"), "&Preferences...", mw, statusTip="Configure application settings.")
        if hasattr(mw, 'on_show_preferences_dialog'):
            mw.preferences_action.triggered.connect(mw.on_show_preferences_dialog)
        else:
            logger.error("UIManager: MainWindow.on_show_preferences_dialog method not found for Preferences action.")

        mw.snap_to_objects_action = QAction("Snap to Objects", mw, checkable=True, statusTip="Enable/disable snapping to object edges and centers")
        mw.snap_to_grid_action = QAction("Snap to Grid", mw, checkable=True, statusTip="Enable/disable snapping to grid")
        
        mw.show_snap_guidelines_action = QAction("Show Dynamic Snap Guidelines", mw, checkable=True, statusTip="Show/hide dynamic alignment guidelines during drag")
        
        
        for action in [mw.select_mode_action, mw.add_state_mode_action, mw.add_transition_mode_action, mw.add_comment_mode_action]:
            mw.mode_action_group.addAction(action)
        mw.select_mode_action.setChecked(True) 

        mw.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation (MATLAB)...", mw)
        mw.generate_matlab_code_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "CdeM"), "Generate &Code (C/C++ via MATLAB)...", mw)
        mw.matlab_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"), "&MATLAB Settings...", mw, triggered=mw.on_matlab_settings)

        mw.start_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Py▶"), "&Start Python Simulation", mw, statusTip="Start internal FSM simulation")
        mw.stop_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaStop, "Py■"), "S&top Python Simulation", mw, statusTip="Stop internal FSM simulation", enabled=False)
        mw.reset_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaSkipBackward, "Py«"), "&Reset Python Simulation", mw, statusTip="Reset internal FSM simulation", enabled=False)

        mw.openai_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "AISet"), "AI Assistant Settings (Gemini)...", mw)
        mw.clear_ai_chat_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "Clear"), "Clear Chat History", mw)
        mw.ask_ai_to_generate_fsm_action = QAction(
            get_standard_icon(QStyle.SP_ArrowRight, "AIGen"),
            "Generate FSM from Description...",
            mw
        )
        
        mw.open_example_menu_action = QAction("Open E&xample...", mw) 
        mw.quick_start_action = QAction(get_standard_icon(QStyle.SP_MessageBoxQuestion, "QS"), "&Quick Start Guide", mw)
        mw.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", mw)
        
        mw.zoom_in_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Z+"), "Zoom In", mw, shortcut="Ctrl++", statusTip="Zoom in the view")
        if hasattr(mw, 'view') and mw.view: mw.zoom_in_action.triggered.connect(mw.view.zoom_in)

        mw.zoom_out_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "Z-"), "Zoom Out", mw, shortcut="Ctrl+-", statusTip="Zoom out the view")
        if hasattr(mw, 'view') and mw.view: mw.zoom_out_action.triggered.connect(mw.view.zoom_out)

        mw.reset_zoom_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "Z0"), "Reset Zoom/View", mw, shortcut="Ctrl+0", statusTip="Reset zoom and center view")
        if hasattr(mw, 'view') and mw.view: mw.reset_zoom_action.triggered.connect(mw.view.reset_view_and_zoom)

        mw.zoom_to_selection_action = QAction(get_standard_icon(QStyle.SP_FileDialogDetailedView, "ZSel"), "Zoom to Selection", mw, statusTip="Zoom to fit selected items")
        mw.zoom_to_selection_action.setEnabled(False) 

        mw.fit_diagram_action = QAction(get_standard_icon(QStyle.SP_FileDialogListView, "ZFit"), "Fit Diagram in View", mw, statusTip="Fit entire diagram in view")

        mw.snap_to_objects_action = QAction("Snap to Objects", mw, checkable=True, statusTip="Enable/disable snapping to object edges and centers")
        mw.snap_to_grid_action = QAction("Snap to Grid", mw, checkable=True, statusTip="Enable/disable snapping to grid")
        if hasattr(mw, 'scene'): 
            mw.snap_to_objects_action.setChecked(mw.scene.snap_to_objects_enabled)
            mw.snap_to_grid_action.setChecked(mw.scene.snap_to_grid_enabled)
        
        mw.align_left_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "AlL"), "Align Left", mw, statusTip="Align selected items to the left")
        mw.align_center_h_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "AlCH"), "Align Center Horizontally", mw, statusTip="Align selected items to their horizontal center")
        mw.align_right_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "AlR"), "Align Right", mw, statusTip="Align selected items to the right")
        mw.align_top_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "AlT"), "Align Top", mw, statusTip="Align selected items to the top")
        mw.align_middle_v_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "AlMV"), "Align Middle Vertically", mw, statusTip="Align selected items to their vertical middle")
        mw.align_bottom_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "AlB"), "Align Bottom", mw, statusTip="Align selected items to the bottom")
        mw.distribute_h_action = QAction(get_standard_icon(QStyle.SP_ArrowLeft, "DstH"), "Distribute Horizontally", mw, statusTip="Distribute selected items horizontally")
        mw.distribute_v_action = QAction(get_standard_icon(QStyle.SP_ArrowUp, "DstV"), "Distribute Vertically", mw, statusTip="Distribute selected items vertically")
        
        mw.align_actions = [mw.align_left_action, mw.align_center_h_action, mw.align_right_action, mw.align_top_action, mw.align_middle_v_action, mw.align_bottom_action]
        mw.distribute_actions = [mw.distribute_h_action, mw.distribute_v_action]
        for action in mw.align_actions: action.setEnabled(False)
        for action in mw.distribute_actions: action.setEnabled(False)
        
        mw.ide_new_file_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "IDENew"), "New Script", mw) 
        mw.ide_open_file_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "IDEOpn"), "Open Script...", mw)
        mw.ide_save_file_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "IDESav"), "Save Script", mw)
        mw.ide_save_as_file_action = QAction(get_standard_icon(_safe_get_style_enum("SP_DriveHDIcon", "SP_DialogSaveButton"), "IDESA"), "Save Script As...", mw)
        mw.ide_run_script_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "IDERunPy"), "Run Python Script", mw)
        mw.ide_analyze_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "IDEAI"), "Analyze with AI", mw)
        
        mw.find_item_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "Find"), "&Find Item...", mw, shortcut=QKeySequence.Find, statusTip="Find an FSM element")

        mw.save_perspective_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "SaveP"), "Save Current Perspective As...", mw)
        mw.reset_perspectives_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "ResetP"), "Reset to Default Layouts", mw)
        
        logger.debug("UIManager: Actions created and assigned to MainWindow, including Preferences and Perspective actions.")

    def _create_menus(self):
        mw = self.mw
        menu_bar = mw.menuBar()
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(mw.new_action)
        file_menu.addAction(mw.open_action)
        
        example_menu = file_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ex"), "Open E&xample")
        mw.open_example_traffic_action = example_menu.addAction("Traffic Light FSM") 
        mw.open_example_toggle_action = example_menu.addAction("Simple Toggle FSM")
        
        export_menu = file_menu.addMenu("E&xport")
        export_menu.addAction(mw.export_png_action) # New
        export_menu.addAction(mw.export_svg_action) # New
        export_menu.addSeparator() # New separator
        export_menu.addAction(mw.export_simulink_action)
        export_menu.addAction(mw.generate_c_code_action)
        export_menu.addSeparator()
        export_menu.addAction(mw.export_plantuml_action)
        export_menu.addAction(mw.export_mermaid_action)

        file_menu.addAction(mw.save_action)
        file_menu.addAction(mw.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(mw.exit_action)

        edit_menu = menu_bar.addMenu("&Edit") 
        edit_menu.addAction(mw.undo_action)
        edit_menu.addAction(mw.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(mw.delete_action)
        edit_menu.addAction(mw.select_all_action)
        edit_menu.addSeparator()
        edit_menu.addAction(mw.find_item_action)
        edit_menu.addSeparator()

        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Mode"),"Interaction Mode")
        mode_menu.addAction(mw.select_mode_action)
        mode_menu.addAction(mw.add_state_mode_action)
        mode_menu.addAction(mw.add_transition_mode_action)
        mode_menu.addAction(mw.add_comment_mode_action)
        edit_menu.addSeparator()

        align_distribute_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogDetailedView, "AD"), "Align & Distribute")
        align_menu = align_distribute_menu.addMenu("Align")
        align_menu.addAction(mw.align_left_action); align_menu.addAction(mw.align_center_h_action); align_menu.addAction(mw.align_right_action); align_menu.addSeparator(); align_menu.addAction(mw.align_top_action); align_menu.addAction(mw.align_middle_v_action); align_menu.addAction(mw.align_bottom_action)
        distribute_menu = align_distribute_menu.addMenu("Distribute")
        distribute_menu.addAction(mw.distribute_h_action); distribute_menu.addAction(mw.distribute_v_action)
        edit_menu.addSeparator()
        edit_menu.addAction(mw.preferences_action) 
        
        sim_menu = menu_bar.addMenu("&Simulation")
        py_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_MediaPlay, "PyS"), "Python Simulation (Internal)")
        py_sim_menu.addAction(mw.start_py_sim_action); py_sim_menu.addAction(mw.stop_py_sim_action); py_sim_menu.addAction(mw.reset_py_sim_action)
        sim_menu.addSeparator()
        matlab_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_ComputerIcon, "M"), "MATLAB/Simulink")
        matlab_sim_menu.addAction(mw.run_simulation_action); matlab_sim_menu.addAction(mw.generate_matlab_code_action); matlab_sim_menu.addSeparator(); matlab_sim_menu.addAction(mw.matlab_settings_action)
        
        mw.view_menu = menu_bar.addMenu("&View") 
        mw.view_menu.addAction(mw.zoom_in_action); mw.view_menu.addAction(mw.zoom_out_action); mw.view_menu.addAction(mw.reset_zoom_action); mw.view_menu.addSeparator(); mw.view_menu.addAction(mw.zoom_to_selection_action); mw.view_menu.addAction(mw.fit_diagram_action); mw.view_menu.addSeparator()
        snap_menu = mw.view_menu.addMenu("Snapping")
        snap_menu.addAction(mw.snap_to_grid_action); snap_menu.addAction(mw.snap_to_objects_action)
        mw.show_snap_guidelines_action = QAction("Show Dynamic Snap Guidelines", mw, checkable=True, statusTip="Show/hide dynamic alignment guidelines during drag")
        snap_menu.addAction(mw.show_snap_guidelines_action)
        
        mw.toolbars_menu = mw.view_menu.addMenu("Toolbars")
        mw.docks_menu = mw.view_menu.addMenu("Docks & Panels") 
        mw.view_menu.addSeparator()
        mw.perspectives_menu = mw.view_menu.addMenu("Perspectives")
        mw.perspectives_action_group = QActionGroup(mw) 
        mw.perspectives_menu.addSeparator() 
        mw.perspectives_menu.addAction(mw.save_perspective_action)
        mw.perspectives_menu.addAction(mw.reset_perspectives_action)


        tools_menu = menu_bar.addMenu("&Tools")
        ide_menu = tools_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogDetailedView, "IDE"), "Standalone Code IDE")
        ide_menu.addAction(mw.ide_new_file_action); ide_menu.addAction(mw.ide_open_file_action); ide_menu.addAction(mw.ide_save_file_action); ide_menu.addAction(mw.ide_save_as_file_action); ide_menu.addSeparator(); ide_menu.addAction(mw.ide_run_script_action); ide_menu.addAction(mw.ide_analyze_action)

        ai_menu = menu_bar.addMenu("&AI Assistant")
        ai_menu.addAction(mw.ask_ai_to_generate_fsm_action); ai_menu.addAction(mw.clear_ai_chat_action); ai_menu.addSeparator(); ai_menu.addAction(mw.openai_settings_action)
        
        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(mw.quick_start_action); help_menu.addAction(mw.about_action)
        logger.debug("UIManager: Menus created, Export to PNG/SVG added.")

    def _create_toolbars(self):
        mw = self.mw
        icon_size = QSize(20,20) 
        tb_style = Qt.ToolButtonIconOnly 
        
        for tb_child in mw.findChildren(QToolBar): 
            mw.removeToolBar(tb_child)
            tb_child.deleteLater()

        mw.main_toolbar = mw.addToolBar("Main Actions")
        mw.main_toolbar.setObjectName("MainToolbar")
        mw.main_toolbar.setIconSize(icon_size)
        mw.main_toolbar.setToolButtonStyle(tb_style)

        mw.main_toolbar.addAction(mw.new_action)
        mw.main_toolbar.addAction(mw.open_action)
        mw.main_toolbar.addAction(mw.save_action)
        mw.main_toolbar.addSeparator()
        mw.main_toolbar.addAction(mw.undo_action)
        mw.main_toolbar.addAction(mw.redo_action)
        mw.main_toolbar.addAction(mw.delete_action)
        mw.main_toolbar.addSeparator()
        mw.main_toolbar.addAction(mw.select_mode_action)
        mw.main_toolbar.addAction(mw.add_state_mode_action)
        mw.main_toolbar.addAction(mw.add_transition_mode_action)
        mw.main_toolbar.addAction(mw.add_comment_mode_action)
        mw.main_toolbar.addSeparator()

        align_menu_button = QToolButton(mw)
        align_menu_button.setIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Align"))
        align_menu_button.setToolTip("Align & Distribute")
        align_menu_button.setPopupMode(QToolButton.InstantPopup)
        align_dist_menu = QMenu(mw)
        align_menu_tb = align_dist_menu.addMenu("Align")
        align_menu_tb.addAction(mw.align_left_action); align_menu_tb.addAction(mw.align_center_h_action); align_menu_tb.addAction(mw.align_right_action)
        align_menu_tb.addSeparator()
        align_menu_tb.addAction(mw.align_top_action); align_menu_tb.addAction(mw.align_middle_v_action); align_menu_tb.addAction(mw.align_bottom_action)
        dist_menu_tb = align_dist_menu.addMenu("Distribute")
        dist_menu_tb.addAction(mw.distribute_h_action); dist_menu_tb.addAction(mw.distribute_v_action)
        align_menu_button.setMenu(align_dist_menu)
        mw.main_toolbar.addWidget(align_menu_button)
        mw.main_toolbar.addSeparator()

        mw.main_toolbar.addAction(mw.zoom_in_action)
        mw.main_toolbar.addAction(mw.zoom_out_action)
        mw.main_toolbar.addAction(mw.reset_zoom_action)
        mw.main_toolbar.addAction(mw.fit_diagram_action)
        mw.main_toolbar.addSeparator()
        
        mw.main_toolbar.addAction(mw.start_py_sim_action)
        mw.main_toolbar.addAction(mw.stop_py_sim_action)
        mw.main_toolbar.addAction(mw.reset_py_sim_action)
        mw.main_toolbar.addSeparator()

        export_menu_button = QToolButton(mw)
        export_menu_button.setIcon(get_standard_icon(QStyle.SP_DialogSaveButton, "Export"))
        export_menu_button.setToolTip("Export & Generate Code")
        export_menu_button.setPopupMode(QToolButton.InstantPopup)
        export_menu_tb = QMenu(mw)
        export_menu_tb.addAction(mw.export_png_action) # New
        export_menu_tb.addAction(mw.export_svg_action) # New
        export_menu_tb.addSeparator()
        export_menu_tb.addAction(mw.export_simulink_action)
        export_menu_tb.addAction(mw.generate_c_code_action)
        export_menu_tb.addAction(mw.generate_matlab_code_action)
        export_menu_tb.addSeparator()
        export_menu_tb.addAction(mw.export_plantuml_action)
        export_menu_tb.addAction(mw.export_mermaid_action)
        export_menu_button.setMenu(export_menu_tb)
        mw.main_toolbar.addWidget(export_menu_button)
            
        if hasattr(mw, 'toolbars_menu'): 
            mw.toolbars_menu.clear() 
            mw.toolbars_menu.addAction(mw.main_toolbar.toggleViewAction()) 
            
        logger.debug("UIManager: Consolidated main toolbar created with PNG/SVG export.")

    def _create_docks(self):
        mw = self.mw
        mw.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)

        mw.elements_palette_dock = QDockWidget("Elements Palette", mw)
        mw.elements_palette_dock.setObjectName("ElementsPaletteDock")
        tools_widget_main = QWidget()
        tools_widget_main.setObjectName("ElementsPaletteDockWidgetContents")
        tools_main_layout = QVBoxLayout(tools_widget_main)
        tools_main_layout.setSpacing(6) 
        tools_main_layout.setContentsMargins(6,6,6,6) 
        
        draggable_group_box = QGroupBox("Drag New Elements")
        draggable_layout = QVBoxLayout()
        draggable_layout.setSpacing(4) 
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
        draggable_group_box.setLayout(draggable_layout)
        tools_main_layout.addWidget(draggable_group_box)
        
        mw.templates_group_box = QGroupBox("FSM Templates")
        templates_layout = QVBoxLayout()
        templates_layout.setSpacing(4) 
        mw.template_buttons_container = QWidget() 
        mw.template_buttons_layout = QVBoxLayout(mw.template_buttons_container)
        mw.template_buttons_layout.setContentsMargins(0,0,0,0)
        mw.template_buttons_layout.setSpacing(3) 
        templates_layout.addWidget(mw.template_buttons_container)
        templates_layout.addStretch()
        mw.templates_group_box.setLayout(templates_layout)
        tools_main_layout.addWidget(mw.templates_group_box)
        
        tools_main_layout.addStretch()
        mw.elements_palette_dock.setWidget(tools_widget_main)
        mw.addDockWidget(Qt.LeftDockWidgetArea, mw.elements_palette_dock)
        
        self._load_and_display_templates() 

        mw.properties_dock = QDockWidget("Item Properties", mw); mw.properties_dock.setObjectName("PropertiesDock")
        mw.properties_dock_widget_main = QWidget()
        mw.properties_dock_main_layout = QVBoxLayout(mw.properties_dock_widget_main); mw.properties_dock_main_layout.setContentsMargins(8,8,8,8); mw.properties_dock_main_layout.setSpacing(6)
        mw.properties_placeholder_label = QLabel("<i>Select a single item to view/edit its properties.</i>"); mw.properties_placeholder_label.setObjectName("PropertiesLabel"); mw.properties_placeholder_label.setWordWrap(True); mw.properties_placeholder_label.setTextFormat(Qt.RichText); mw.properties_placeholder_label.setAlignment(Qt.AlignTop | Qt.AlignLeft); mw.properties_dock_main_layout.addWidget(mw.properties_placeholder_label)
        mw.properties_editor_container = QWidget(); mw.properties_editor_layout = QFormLayout(mw.properties_editor_container); mw.properties_editor_layout.setContentsMargins(0,0,0,0); mw.properties_editor_layout.setSpacing(8); mw.properties_dock_main_layout.addWidget(mw.properties_editor_container); mw.properties_editor_container.setVisible(False)
        mw.properties_dock_main_layout.addStretch(1)
        mw.properties_apply_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton, "Apply"), "Apply Changes"); mw.properties_apply_button.setEnabled(False)
        mw.properties_revert_button = QPushButton(get_standard_icon(QStyle.SP_DialogCancelButton, "Revert"), "Revert"); mw.properties_revert_button.setEnabled(False)
        mw.properties_edit_dialog_button = QPushButton(get_standard_icon(QStyle.SP_FileDialogDetailedView, "AdvEdit"), "Advanced Edit..."); mw.properties_edit_dialog_button.setToolTip("Open full properties dialog"); mw.properties_edit_dialog_button.setEnabled(False)
        button_layout_props = QHBoxLayout(); button_layout_props.addWidget(mw.properties_revert_button); button_layout_props.addStretch(); button_layout_props.addWidget(mw.properties_apply_button)
        mw.properties_dock_main_layout.addLayout(button_layout_props); mw.properties_dock_main_layout.addWidget(mw.properties_edit_dialog_button)
        mw.properties_dock.setWidget(mw.properties_dock_widget_main); mw.addDockWidget(Qt.RightDockWidgetArea, mw.properties_dock)
        mw._dock_property_editors = {}; mw._current_edited_item_in_dock = None 

        mw.log_dock = QDockWidget("Application Log", mw); mw.log_dock.setObjectName("LogDock")
        log_widget = QWidget(); log_layout = QVBoxLayout(log_widget); log_layout.setContentsMargins(0,0,0,0)
        mw.log_output = QTextEdit(); mw.log_output.setObjectName("LogOutputWidget"); mw.log_output.setReadOnly(True) 
        log_layout.addWidget(mw.log_output); mw.log_dock.setWidget(log_widget)
        mw.addDockWidget(Qt.BottomDockWidgetArea, mw.log_dock); 

        mw.problems_dock = QDockWidget("Validation Issues", mw); mw.problems_dock.setObjectName("ProblemsDock")
        mw.problems_list_widget = QListWidget()
        mw.problems_dock.setWidget(mw.problems_list_widget); mw.addDockWidget(Qt.BottomDockWidgetArea, mw.problems_dock); 
        mw.problems_dock.setVisible(False) 


        mw.py_sim_dock = QDockWidget("Python Simulation", mw); mw.py_sim_dock.setObjectName("PySimDock")
        mw.addDockWidget(Qt.RightDockWidgetArea, mw.py_sim_dock); mw.py_sim_dock.setVisible(False)

        mw.ai_chatbot_dock = QDockWidget("AI Assistant", mw); mw.ai_chatbot_dock.setObjectName("AIChatbotDock")
        mw.addDockWidget(Qt.RightDockWidgetArea, mw.ai_chatbot_dock); mw.ai_chatbot_dock.setVisible(False)
        
        mw.ide_dock = QDockWidget("Standalone Code IDE", mw) 
        mw.ide_dock.setObjectName("IDEDock")
        mw.ide_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        mw.addDockWidget(Qt.RightDockWidgetArea, mw.ide_dock)
        mw.ide_dock.setVisible(False) 
        
        if hasattr(mw, 'docks_menu'): 
            mw.docks_menu.clear() 
            mw.docks_menu.addAction(mw.elements_palette_dock.toggleViewAction()) 
            mw.docks_menu.addAction(mw.properties_dock.toggleViewAction())
            mw.docks_menu.addAction(mw.log_dock.toggleViewAction())
            mw.docks_menu.addAction(mw.problems_dock.toggleViewAction())
            mw.docks_menu.addAction(mw.py_sim_dock.toggleViewAction())
            mw.docks_menu.addAction(mw.ai_chatbot_dock.toggleViewAction())
            mw.docks_menu.addAction(mw.ide_dock.toggleViewAction())
        
        logger.debug("UIManager: Docks created.")

    def _load_and_display_templates(self):
        mw = self.mw
        if hasattr(mw, 'template_buttons_layout') and mw.template_buttons_layout is not None:
            while mw.template_buttons_layout.count():
                child = mw.template_buttons_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        else:
            logger.warning("UIManager: template_buttons_layout not found on MainWindow. Cannot clear/load templates.")
            return

        templates_to_load = []
        for template_key, template_dict_value in FSM_TEMPLATES_BUILTIN.items():
            templates_to_load.append({
                "id": f"builtin_{template_key}",
                "name": template_dict_value.get("name", "Unnamed Template"),
                "description": template_dict_value.get("description", ""),
                "icon_resource": template_dict_value.get("icon_resource"),
                "data_json_str": json.dumps(template_dict_value) 
            })

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
            template_btn.setIconSize(QSize(20,20)) 
            template_btn.setToolTip(template_info.get("description", template_info["name"]))
            mw.template_buttons_layout.addWidget(template_btn)

        mw.template_buttons_layout.addStretch(1)
        logger.debug("UIManager: FSM Templates loaded and displayed in Elements Palette Dock.")
        
    def _create_status_bar(self):
        mw = self.mw
        mw.status_bar = QStatusBar(mw); mw.setStatusBar(mw.status_bar)
        
        mw.main_op_status_label = QLabel("Ready"); 
        mw.main_op_status_label.setObjectName("MainOpStatusLabel")
        mw.status_bar.addWidget(mw.main_op_status_label, 1) 

        mw.ide_file_status_label = QLabel("IDE: Idle")
        mw.ide_file_status_label.setObjectName("IdeFileStatusLabel")
        mw.ide_file_status_label.setMinimumWidth(100) 
        mw.ide_file_status_label.setAlignment(Qt.AlignCenter)
        mw.status_bar.addPermanentWidget(mw.ide_file_status_label)

        mw.zoom_status_label = QLabel("Zoom: 100%"); mw.zoom_status_label.setMinimumWidth(70); mw.zoom_status_label.setAlignment(Qt.AlignCenter); mw.status_bar.addPermanentWidget(mw.zoom_status_label)
        
        resource_label_min_width = 60
        mw.cpu_status_label = QLabel("CPU: --%"); mw.cpu_status_label.setToolTip("CPU Usage"); mw.cpu_status_label.setMinimumWidth(resource_label_min_width);
        mw.ram_status_label = QLabel("RAM: --%"); mw.ram_status_label.setToolTip("RAM Usage"); mw.ram_status_label.setMinimumWidth(resource_label_min_width);
        mw.gpu_status_label = QLabel("GPU: N/A"); mw.gpu_status_label.setToolTip("GPU Usage (NVIDIA only, if pynvml installed)"); mw.gpu_status_label.setMinimumWidth(resource_label_min_width);
        
        mw.py_sim_status_label = QLabel("PySim: Idle"); mw.py_sim_status_label.setToolTip("Internal Python FSM Simulation Status."); mw.py_sim_status_label.setMinimumWidth(100); mw.py_sim_status_label.setAlignment(Qt.AlignCenter); mw.status_bar.addPermanentWidget(mw.py_sim_status_label)
        mw.matlab_status_label = QLabel("MATLAB: Init..."); mw.matlab_status_label.setToolTip("MATLAB connection status."); mw.matlab_status_label.setMinimumWidth(110); mw.matlab_status_label.setAlignment(Qt.AlignCenter); mw.status_bar.addPermanentWidget(mw.matlab_status_label)
        mw.internet_status_label = QLabel("Net: Init..."); mw.internet_status_label.setToolTip("Internet connectivity. Checks periodically."); mw.internet_status_label.setMinimumWidth(80); mw.internet_status_label.setAlignment(Qt.AlignCenter); mw.status_bar.addPermanentWidget(mw.internet_status_label)
        
        mw.progress_bar = QProgressBar(mw); mw.progress_bar.setRange(0,0); mw.progress_bar.setVisible(False); mw.progress_bar.setMaximumWidth(120); mw.progress_bar.setTextVisible(False); mw.status_bar.addPermanentWidget(mw.progress_bar)
        logger.debug("UIManager: Status bar created. Resource labels will be added by MainWindow based on settings.")

    def populate_dynamic_docks(self):
        mw = self.mw
        if mw.py_sim_ui_manager and hasattr(mw, 'py_sim_dock') and mw.py_sim_dock:
            py_sim_contents_widget = mw.py_sim_ui_manager.create_dock_widget_contents()
            mw.py_sim_dock.setWidget(py_sim_contents_widget)
        else:
            logger.error("UIManager: Could not populate Python Simulation Dock: PySimUIManager or py_sim_dock missing.")

        if mw.ai_chat_ui_manager and hasattr(mw, 'ai_chatbot_dock') and mw.ai_chatbot_dock:
            ai_chat_contents_widget = mw.ai_chat_ui_manager.create_dock_widget_contents()
            mw.ai_chatbot_dock.setWidget(ai_chat_contents_widget)
        else:
            logger.error("UIManager: Could not populate AI Chatbot Dock: AIChatUIManager or ai_chatbot_dock missing.")
        
        if mw.ide_manager and hasattr(mw, 'ide_dock') and mw.ide_dock:
            pass 
        else:
            logger.error("UIManager: Could not populate IDE Dock: IDEManager or ide_dock missing.")
        logger.debug("UIManager: Dynamic docks populated.")
--- END OF FILE bsm_designer_project/ui_manager.py ---