# bsm_designer_project/dialogs.py
# Added theme combo and visual settings to SettingsDialog
# Added shape, font, border, icon options to StatePropertiesDialog

import sys
import json
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QCheckBox, QPushButton, QTextEdit,
    QSpinBox, QComboBox, QDialogButtonBox, QColorDialog, QHBoxLayout,
    QLabel, QFileDialog, QGroupBox, QMenu, QAction, QVBoxLayout, QStyle,
    QMessageBox, QInputDialog, QGraphicsView, QUndoStack, QToolBar, QActionGroup,
    QMainWindow, 
    QListWidget, QListWidgetItem, 
    QGraphicsItem,QTabWidget, QWidget,
    QFontComboBox, QDoubleSpinBox # Added for visual settings
)
from PyQt5.QtGui import QColor, QIcon, QPalette, QKeyEvent, QFont, QPixmap # Added QFont, QPixmap
from PyQt5.QtCore import Qt, QDir, QSize, QPointF, pyqtSignal, QVariant 
from settings_manager import SettingsManager
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from config import (
    APP_NAME, 
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_ON_ACCENT, MECHATRONICS_SNIPPETS, COLOR_ACCENT_PRIMARY, COLOR_ACCENT_ERROR,
    DEFAULT_EXECUTION_ENV, EXECUTION_ENV_PYTHON_GENERIC, EXECUTION_ENV_ARDUINO_CPP,
    EXECUTION_ENV_C_GENERIC, EXECUTION_ENV_RASPBERRYPI_PYTHON, EXECUTION_ENV_MICROPYTHON,
    APP_FONT_SIZE_SMALL, COLOR_TEXT_SECONDARY, COLOR_BACKGROUND_DIALOG,COLOR_ACCENT_SUCCESS,
    COLOR_BACKGROUND_LIGHT, COLOR_ACCENT_PRIMARY_LIGHT, COLOR_BORDER_MEDIUM,
    APP_FONT_FAMILY, # For default font family
    DEFAULT_STATE_SHAPE, DEFAULT_STATE_BORDER_STYLE, DEFAULT_STATE_BORDER_WIDTH, # For defaults
    COLOR_GRID_MINOR, COLOR_GRID_MAJOR, COLOR_SNAP_GUIDELINE # For defaults in settings dialog
)
from code_editor import CodeEditor
from utils import get_standard_icon
from matlab_integration import MatlabConnection
from snippet_manager import CustomSnippetManager

import logging
logger = logging.getLogger(__name__)

try:
    from graphics_scene import DiagramScene, ZoomableView
    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    print(f"SubFSMEditorDialog: Could not import DiagramScene/ZoomableView: {e}. Visual sub-editor will be disabled.")
    DiagramScene = None
    ZoomableView = None
    IMPORTS_SUCCESSFUL = False


class SubFSMEditorDialog(QDialog):
    # ... (no changes in this iteration) ...
    def __init__(self, sub_fsm_data_initial: dict, parent_state_name: str, parent_window_ref=None):
        super().__init__(parent_window_ref)
        self.parent_window_ref = parent_window_ref
        self.setWindowTitle(f"Sub-Machine Editor: {parent_state_name}")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "SubEdit"))
        self.setMinimumSize(800, 600)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#ErrorLabel {{ color: {COLOR_ACCENT_ERROR}; font-weight: bold; }}")


        self.current_sub_fsm_data = sub_fsm_data_initial if isinstance(sub_fsm_data_initial, dict) else \
                                    {'states': [], 'transitions': [], 'comments': []}


        layout = QVBoxLayout(self)

        if IMPORTS_SUCCESSFUL: 
            self.sub_undo_stack = QUndoStack(self)
            self.sub_scene = DiagramScene(self.sub_undo_stack, parent_window=self)
            self.sub_view = ZoomableView(self.sub_scene, self)
            toolbar = QToolBar("Sub-Editor Tools")
            toolbar.setIconSize(QSize(18,18)) 
            toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly) 
            self.sub_mode_action_group = QActionGroup(self)
            self.sub_mode_action_group.setExclusive(True)
            actions_data = [
                ("select", "Select/Move", QStyle.SP_ArrowRight, "SelSub"),
                ("state", "Add State", QStyle.SP_FileDialogNewFolder, "StSub"),
                ("transition", "Add Transition", QStyle.SP_ArrowForward, "TrSub"),
                ("comment", "Add Comment", QStyle.SP_MessageBoxInformation, "CmSub")
            ]
            for mode, text, icon_enum, icon_alt in actions_data:
                action = QAction(get_standard_icon(icon_enum, icon_alt), text, self)
                action.setToolTip(text) 
                action.setCheckable(True)
                action.triggered.connect(lambda checked=False, m=mode: self.sub_scene.set_mode(m))
                toolbar.addAction(action)
                self.sub_mode_action_group.addAction(action)
                setattr(self, f"sub_{mode}_action", action)

            toolbar.addSeparator()
            self.sub_undo_action = self.sub_undo_stack.createUndoAction(self, "Undo")
            self.sub_undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "UnSub"))
            self.sub_undo_action.setToolTip("Undo")
            toolbar.addAction(self.sub_undo_action)
            self.sub_redo_action = self.sub_undo_stack.createRedoAction(self, "Redo")
            self.sub_redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "ReSub"))
            self.sub_redo_action.setToolTip("Redo")
            toolbar.addAction(self.sub_redo_action)

            layout.addWidget(toolbar)
            layout.addWidget(self.sub_view, 1)
            self.sub_scene.load_diagram_data(self.current_sub_fsm_data)
            self.sub_undo_stack.clear()
            self.sub_scene.set_dirty(False) 
            if hasattr(self, 'sub_select_action'): self.sub_select_action.setChecked(True)
            self.sub_scene.set_mode("select")
            self.status_label = QLabel("Visually edit the sub-machine. Click OK to save changes to the parent state.")
            self.status_label.setStyleSheet(f"font-size: {APP_FONT_SIZE_SMALL}; color: {COLOR_TEXT_SECONDARY};")
        else: 
            self.json_edit_label = QLabel("<b>Visual Sub-Editor Failed to Load. Editing as JSON:</b>")
            self.json_edit_label.setObjectName("ErrorLabel") 
            layout.addWidget(self.json_edit_label)

            error_detail_label = QLabel(
                "<small><i>This might be due to missing optional dependencies (e.g., for graphical rendering) "
                "or an unexpected error. Check the application console/logs for specific import errors. "
                "You can still edit the sub-machine's raw JSON data below. Ensure the JSON structure is valid.</i></small>"
            )
            error_detail_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; margin-bottom: 5px;")
            error_detail_label.setWordWrap(True)
            layout.addWidget(error_detail_label)

            self.json_text_edit = CodeEditor() 
            self.json_text_edit.setPlainText(json.dumps(self.current_sub_fsm_data, indent=2, ensure_ascii=False))
            self.json_text_edit.setLineWrapMode(CodeEditor.NoWrap) 
            try:
                self.json_text_edit.set_language("JSON") 
            except Exception: 
                logger.warning("JSON language not available in CodeEditor, falling back to Text for SubFSM JSON.")
                self.json_text_edit.set_language("Text") 
            self.json_text_edit.setObjectName("SubFSMJsonEditor") 

            layout.addWidget(self.json_text_edit, 1)
            self.status_label = QLabel("Edit the JSON data for the sub-machine. Click OK to save changes.")


        layout.addWidget(self.status_label)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_changes); button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept_changes(self):
        if IMPORTS_SUCCESSFUL and hasattr(self, 'sub_scene'): 
            updated_data = self.sub_scene.get_diagram_data()
            if isinstance(updated_data, dict) and \
               all(k in updated_data for k in ['states', 'transitions', 'comments']) and \
               isinstance(updated_data.get('states'), list) and \
               isinstance(updated_data.get('transitions'), list) and \
               isinstance(updated_data.get('comments'), list):

                sub_states_list = updated_data.get('states', [])
                if sub_states_list:
                    has_initial = any(s.get('is_initial', False) for s in sub_states_list)
                    if not has_initial:
                        msg_box = QMessageBox(self)
                        msg_box.setIcon(QMessageBox.Warning)
                        msg_box.setWindowTitle("No Initial Sub-State")
                        msg_box.setText("The sub-machine does not have an initial state defined. "
                                        "It's recommended to define one for predictable behavior.")
                        save_anyway_btn = msg_box.addButton("Save Anyway", QMessageBox.AcceptRole)
                        set_first_btn = msg_box.addButton("Set First as Initial & Save", QMessageBox.YesRole)
                        cancel_btn = msg_box.addButton(QMessageBox.Cancel)
                        msg_box.setDefaultButton(cancel_btn)
                        msg_box.exec_()

                        reply = msg_box.clickedButton()

                        if reply == cancel_btn: return
                        if reply == set_first_btn:
                            if sub_states_list:
                                sub_states_list[0]['is_initial'] = True
                                self.log_message("INFO", f"Set state '{sub_states_list[0].get('name', 'Unnamed')}' as initial in sub-machine.")
                self.current_sub_fsm_data = updated_data
                self.accept()
            else:
                QMessageBox.warning(self, "Invalid Sub-Machine Structure", "Unexpected sub-machine editor data structure.")
                logger.error("SubFSMEditorDialog: Invalid data structure from sub_scene.get_diagram_data().")

        elif hasattr(self, 'json_text_edit'): 
            try:
                parsed_new_data = json.loads(self.json_text_edit.toPlainText())
                if isinstance(parsed_new_data, dict) and all(k in parsed_new_data for k in ['states', 'transitions', 'comments']):

                    sub_states_list_json = parsed_new_data.get('states', [])
                    if sub_states_list_json:
                        has_initial_json = any(s.get('is_initial', False) for s in sub_states_list_json)
                        if not has_initial_json:
                            msg_box = QMessageBox(self)
                            msg_box.setIcon(QMessageBox.Warning)
                            msg_box.setWindowTitle("No Initial Sub-State")
                            msg_box.setText("The sub-machine (JSON data) does not have an initial state defined. "
                                            "It's recommended to define one.")
                            save_anyway_btn = msg_box.addButton("Save Anyway", QMessageBox.AcceptRole)
                            set_first_btn = msg_box.addButton("Set First as Initial & Save", QMessageBox.YesRole)
                            cancel_btn = msg_box.addButton(QMessageBox.Cancel)
                            msg_box.setDefaultButton(cancel_btn)
                            msg_box.exec_()

                            reply = msg_box.clickedButton()
                            if reply == cancel_btn: return
                            if reply == set_first_btn:
                                if sub_states_list_json:
                                    sub_states_list_json[0]['is_initial'] = True 
                                    self.log_message("INFO", f"Set state '{sub_states_list_json[0].get('name', 'Unnamed')}' as initial in sub-machine (JSON).")
                                    self.json_text_edit.setPlainText(json.dumps(parsed_new_data, indent=2, ensure_ascii=False)) 
                    
                    self.current_sub_fsm_data = parsed_new_data 
                    self.accept()
                else:
                    QMessageBox.warning(self, "Invalid JSON Structure", "JSON needs 'states', 'transitions', 'comments' lists at the root.")
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "JSON Parse Error", f"Could not parse JSON: {e}")
        else:
            logger.error("SubFSMEditorDialog: Neither visual scene nor JSON editor found on accept_changes.")
            self.reject() 

    def get_updated_sub_fsm_data(self) -> dict:
        return self.current_sub_fsm_data

    def log_message(self, level, message):
        print(f"SubFSMEditor Log ({level}): {message}")
        if self.parent_window_ref and hasattr(self.parent_window_ref, 'log_message') and callable(self.parent_window_ref.log_message):
             self.parent_window_ref.log_message(level.upper(), f"[SubEditor] {message}")


class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False, scene_ref=None, custom_snippet_manager: CustomSnippetManager | None = None):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "Props"))
        self.setMinimumWidth(650) # Increased width for more options
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#SafetyNote, QLabel#HardwareHintLabel {{ font-size: {APP_FONT_SIZE_SMALL}; color: {COLOR_TEXT_SECONDARY}; }} QGroupBox {{ background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102).name()}; }}")

        self.parent_window_ref = parent
        self.scene_ref = scene_ref
        self.custom_snippet_manager = custom_snippet_manager
        p = current_properties or {}
        
        self.settings_manager = None
        if QApplication.instance() and hasattr(QApplication.instance(), 'settings_manager'):
            self.settings_manager = QApplication.instance().settings_manager


        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(12,12,12,12)

        # --- Tabs for organization ---
        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # == General Tab ==
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        general_layout.setSpacing(8)

        self.name_edit = QLineEdit(p.get('name', "StateName"))
        general_layout.addRow("Name:", self.name_edit)

        self.is_initial_cb = QCheckBox("Is Initial State"); self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Is Final State"); self.is_final_cb.setChecked(p.get('is_final', False))
        cb_layout = QHBoxLayout(); cb_layout.addWidget(self.is_initial_cb); cb_layout.addSpacing(15); cb_layout.addWidget(self.is_final_cb); cb_layout.addStretch()
        general_layout.addRow("", cb_layout)

        self.is_superstate_cb = QCheckBox("Is Superstate (Composite State)")
        self.is_superstate_cb.setChecked(p.get('is_superstate', False))
        self.is_superstate_cb.toggled.connect(self._on_superstate_toggled)
        self.edit_sub_fsm_button = QPushButton(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Sub"), "Edit Sub-Machine...")
        self.edit_sub_fsm_button.clicked.connect(self._on_edit_sub_fsm)
        self.edit_sub_fsm_button.setEnabled(self.is_superstate_cb.isChecked())
        cb_layout_super = QHBoxLayout(); cb_layout_super.addWidget(self.is_superstate_cb); cb_layout_super.addSpacing(8); cb_layout_super.addWidget(self.edit_sub_fsm_button); cb_layout_super.addStretch()
        general_layout.addRow("Hierarchy:", cb_layout_super)
        
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(60)
        general_layout.addRow("Description:", self.description_edit)
        
        tabs.addTab(general_tab, "General")

        # Initialize sub_fsm_data (same as before)
        raw_sub_fsm_data = p.get('sub_fsm_data', {})
        if isinstance(raw_sub_fsm_data, dict) and \
           all(k in raw_sub_fsm_data for k in ['states', 'transitions', 'comments']) and \
           isinstance(raw_sub_fsm_data.get('states'), list) and \
           isinstance(raw_sub_fsm_data.get('transitions'), list) and \
           isinstance(raw_sub_fsm_data.get('comments'), list):
            self.current_sub_fsm_data = raw_sub_fsm_data
        else:
            self.current_sub_fsm_data = {'states': [], 'transitions': [], 'comments': []}
            if raw_sub_fsm_data:
                logger.warning(f"State '{p.get('name', 'Unknown')}' had invalid sub_fsm_data, reset to empty.")

        # == Appearance Tab ==
        appearance_tab = QWidget()
        appearance_layout = QFormLayout(appearance_tab)
        appearance_layout.setSpacing(8)

        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton")
        self.current_color = QColor(p.get('color', COLOR_ITEM_STATE_DEFAULT_BG)); self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)
        appearance_layout.addRow("Display Color:", self.color_button)

        self.shape_combo = QComboBox()
        self.shape_combo.addItems(["Rectangle", "Ellipse"])
        self.shape_combo.setCurrentText(p.get('shape_type', DEFAULT_STATE_SHAPE).capitalize())
        appearance_layout.addRow("Shape:", self.shape_combo)

        # Font Controls
        font_group = QGroupBox("Label Font")
        font_layout = QFormLayout(font_group)
        self.font_family_combo = QFontComboBox()
        self.font_family_combo.setCurrentFont(QFont(p.get('font_family', APP_FONT_FAMILY)))
        font_layout.addRow("Family:", self.font_family_combo)
        self.font_size_spin = QSpinBox(); self.font_size_spin.setRange(6, 72); self.font_size_spin.setValue(p.get('font_size', 10))
        font_layout.addRow("Size:", self.font_size_spin)
        self.font_bold_cb = QCheckBox("Bold"); self.font_bold_cb.setChecked(p.get('font_bold', True))
        self.font_italic_cb = QCheckBox("Italic"); self.font_italic_cb.setChecked(p.get('font_italic', False))
        font_style_layout = QHBoxLayout(); font_style_layout.addWidget(self.font_bold_cb); font_style_layout.addWidget(self.font_italic_cb); font_style_layout.addStretch()
        font_layout.addRow("Style:", font_style_layout)
        appearance_layout.addWidget(font_group)

        # Border Controls
        border_group = QGroupBox("Border Style")
        border_layout = QFormLayout(border_group)
        self.border_style_combo = QComboBox()
        self.border_style_combo.addItems(list(SettingsManager.STRING_TO_QT_PEN_STYLE.keys()))
        default_border_style_str = p.get('border_style_str', SettingsManager.QT_PEN_STYLE_TO_STRING.get(DEFAULT_STATE_BORDER_STYLE, "Solid"))
        self.border_style_combo.setCurrentText(default_border_style_str)
        border_layout.addRow("Style:", self.border_style_combo)
        self.border_width_spin = QDoubleSpinBox(); self.border_width_spin.setRange(0.5, 10.0); self.border_width_spin.setSingleStep(0.1); self.border_width_spin.setValue(p.get('border_width', DEFAULT_STATE_BORDER_WIDTH)); self.border_width_spin.setDecimals(1)
        border_layout.addRow("Width:", self.border_width_spin)
        appearance_layout.addWidget(border_group)
        
        # Custom Icon
        icon_group = QGroupBox("Custom Icon (Optional)")
        icon_layout = QFormLayout(icon_group)
        self.icon_path_edit = QLineEdit(p.get('icon_path', ''))
        self.icon_path_edit.setPlaceholderText("Path to icon image (e.g., .png, .svg)")
        self.icon_browse_button = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon), "Browse...")
        self.icon_browse_button.clicked.connect(self._browse_for_icon)
        icon_file_layout = QHBoxLayout(); icon_file_layout.addWidget(self.icon_path_edit, 1); icon_file_layout.addWidget(self.icon_browse_button)
        icon_layout.addRow("Icon File:", icon_file_layout)
        self.icon_preview_label = QLabel("<i>No icon selected</i>")
        self.icon_preview_label.setFixedSize(32,32); self.icon_preview_label.setAlignment(Qt.AlignCenter)
        self.icon_preview_label.setStyleSheet(f"border: 1px solid {COLOR_BORDER_MEDIUM}; background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(105).name()};")
        self._update_icon_preview(p.get('icon_path', ''))
        icon_layout.addRow("Preview:", self.icon_preview_label)
        self.icon_path_edit.textChanged.connect(self._update_icon_preview) # Update preview on text change
        appearance_layout.addWidget(icon_group)

        tabs.addTab(appearance_tab, "Appearance")


        # == Actions Tab == (remains mostly the same)
        actions_tab = QWidget()
        actions_layout_outer = QVBoxLayout(actions_tab) # Use QVBoxLayout for the tab itself
        
        actions_group = QGroupBox("State Actions") # Keep groupbox for structure
        actions_layout = QFormLayout(actions_group) # Use QFormLayout inside groupbox
        actions_layout.setSpacing(8)

        self.action_language_combo = QComboBox()
        self.action_language_combo.addItems(list(MECHATRONICS_SNIPPETS.keys()))
        self.action_language_combo.setCurrentText(p.get('action_language', DEFAULT_EXECUTION_ENV))
        actions_layout.addRow("Action Language:", self.action_language_combo)

        self.entry_action_edit = CodeEditor(); self.entry_action_edit.setPlainText(p.get('entry_action', "")); self.entry_action_edit.setFixedHeight(80); self.entry_action_edit.setObjectName("ActionCodeEditor")
        self.during_action_edit = CodeEditor(); self.during_action_edit.setPlainText(p.get('during_action', "")); self.during_action_edit.setFixedHeight(80); self.during_action_edit.setObjectName("ActionCodeEditor")
        self.exit_action_edit = CodeEditor(); self.exit_action_edit.setPlainText(p.get('exit_action', "")); self.exit_action_edit.setFixedHeight(80); self.exit_action_edit.setObjectName("ActionCodeEditor")

        self.entry_action_snippet_btn = self._create_insert_snippet_button(self.entry_action_edit, "actions", " Action")
        self.during_action_snippet_btn = self._create_insert_snippet_button(self.during_action_edit, "actions", " Action")
        self.exit_action_snippet_btn = self._create_insert_snippet_button(self.exit_action_edit, "actions", " Action")

        self.action_language_combo.currentTextChanged.connect(self._on_action_language_changed)
        self._on_action_language_changed(self.action_language_combo.currentText())

        def add_field_with_note_and_hw_hint(form_layout, label_text, code_editor_widget, snippet_button):
            # ... (this helper function remains the same) ...
            h_editor_btn_layout = QHBoxLayout(); h_editor_btn_layout.setSpacing(6)
            h_editor_btn_layout.addWidget(code_editor_widget, 1)
            v_btn_container = QVBoxLayout(); v_btn_container.setSpacing(3)
            v_btn_container.addWidget(snippet_button)
            hw_hint_label = QLabel("<small><i>E.g., for Arduino: `digitalWrite(LED_PIN, HIGH);`</i></small>")
            hw_hint_label.setObjectName("HardwareHintLabel"); hw_hint_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-style: italic; font-size: 7.5pt;")
            hw_hint_label.setToolTip("Consider actions that interact with hardware signals.\nThese can be simulated as variable changes or later mapped to real hardware in code generation.")
            v_btn_container.addWidget(hw_hint_label)
            safety_note_label = QLabel("<small><i>Note: Code safety depends on target environment.</i></small>")
            safety_note_label.setObjectName("SafetyNote")
            safety_note_label.setToolTip("For 'Python (Generic Simulation)', code is checked for common unsafe operations.\nFor other environments (Arduino, C, etc.), this editor provides text input; \nsafety and correctness are the responsibility of the external compiler/interpreter.")
            v_btn_container.addWidget(safety_note_label)
            v_btn_container.addStretch(1)
            h_editor_btn_layout.addLayout(v_btn_container)
            form_layout.addRow(label_text, h_editor_btn_layout)

        add_field_with_note_and_hw_hint(actions_layout, "Entry Action:", self.entry_action_edit, self.entry_action_snippet_btn)
        add_field_with_note_and_hw_hint(actions_layout, "During Action:", self.during_action_edit, self.during_action_snippet_btn)
        add_field_with_note_and_hw_hint(actions_layout, "Exit Action:", self.exit_action_edit, self.exit_action_snippet_btn)
        
        actions_layout_outer.addWidget(actions_group) # Add groupbox to tab's layout
        tabs.addTab(actions_tab, "Actions")


        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

        if is_new_state: self.name_edit.selectAll(); self.name_edit.setFocus()

    def _browse_for_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Icon File", QDir.homePath(), "Images (*.png *.jpg *.jpeg *.svg *.ico)")
        if file_path:
            self.icon_path_edit.setText(file_path)
            # _update_icon_preview will be called by textChanged signal

    def _update_icon_preview(self, path_text: str):
        if path_text and os.path.exists(path_text):
            pixmap = QPixmap(path_text)
            if not pixmap.isNull():
                self.icon_preview_label.setPixmap(pixmap.scaled(32,32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.icon_preview_label.setText("<i>Invalid</i>")
        else:
            self.icon_preview_label.setText("<i>No icon</i>")


    def _update_snippet_button_menu(self, button: QPushButton, target_widget: CodeEditor, language_mode: str, snippet_category: str):
        # ... (remains the same) ...
        menu = button.menu()
        menu.clear()
        menu.setStyleSheet("QMenu { font-size: 9pt; } QMenu::item { padding: 5px 20px; }")
        
        built_in_snippets = MECHATRONICS_SNIPPETS.get(language_mode, {}).get(snippet_category, {})
        custom_snippets_dict = {}
        if self.custom_snippet_manager: 
            custom_snippets_dict = self.custom_snippet_manager.get_custom_snippets(language_mode, snippet_category)

        if not built_in_snippets and not custom_snippets_dict:
            action = QAction(f"(No '{snippet_category}' snippets for {language_mode})", self)
            action.setEnabled(False)
            menu.addAction(action)
            button.setEnabled(False)
            return

        button.setEnabled(True)
        if built_in_snippets:
            built_in_header = QAction("Built-in Snippets", self); built_in_header.setEnabled(False)
            menu.addAction(built_in_header)
            for name, snippet in built_in_snippets.items():
                action = QAction(name, self)
                action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n"))
                menu.addAction(action)
        
        if custom_snippets_dict:
            if built_in_snippets: menu.addSeparator()
            custom_header = QAction("Custom Snippets", self); custom_header.setEnabled(False)
            menu.addAction(custom_header)
            for name, snippet_code in custom_snippets_dict.items():
                action = QAction(f"{name}", self) 
                action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet_code: text_edit.insertPlainText(s + "\n"))
                menu.addAction(action)

    def _on_action_language_changed(self, language_mode: str):
        # ... (remains the same) ...
        self.entry_action_edit.set_language(language_mode)
        self.during_action_edit.set_language(language_mode)
        self.exit_action_edit.set_language(language_mode)
        self._update_snippet_button_menu(self.entry_action_snippet_btn, self.entry_action_edit, language_mode, "actions")
        self._update_snippet_button_menu(self.during_action_snippet_btn, self.during_action_edit, language_mode, "actions")
        self._update_snippet_button_menu(self.exit_action_snippet_btn, self.exit_action_edit, language_mode, "actions")

    def _create_insert_snippet_button(self, target_widget: CodeEditor, snippet_category: str, button_text="Insert...", icon_size_px=16):
        # ... (remains the same) ...
        button = QPushButton(button_text); button.setObjectName("SnippetButton")
        button.setToolTip(f"Insert common {snippet_category[:-1] if snippet_category.endswith('s') else snippet_category} snippets");
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "InsSnip"))
        button.setIconSize(QSize(icon_size_px, icon_size_px))
        button.setMenu(QMenu(self))
        return button

    def _on_superstate_toggled(self, checked):
        # ... (remains the same) ...
        self.edit_sub_fsm_button.setEnabled(checked)
        if not checked:
            if self.current_sub_fsm_data and \
               (self.current_sub_fsm_data.get('states') or self.current_sub_fsm_data.get('transitions')):
                reply = QMessageBox.question(self, "Discard Sub-Machine?",
                                             "Unchecking 'Is Superstate' will clear its internal diagram data. Continue?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.current_sub_fsm_data = {'states': [], 'transitions': [], 'comments': []}
                else:
                    self.is_superstate_cb.blockSignals(True)
                    self.is_superstate_cb.setChecked(True)
                    self.is_superstate_cb.blockSignals(False)
                    self.edit_sub_fsm_button.setEnabled(True)

    def _on_edit_sub_fsm(self):
        # ... (remains the same) ...
        parent_state_name = self.name_edit.text().strip() or "Unnamed Superstate"
        dialog_parent = self.parent()
        while dialog_parent and not isinstance(dialog_parent, QMainWindow) and hasattr(dialog_parent, 'parent') and callable(dialog_parent.parent):
            if dialog_parent.parent() == dialog_parent: break 
            dialog_parent = dialog_parent.parent()
        if not dialog_parent: dialog_parent = self
        sub_editor_dialog = SubFSMEditorDialog(self.current_sub_fsm_data, parent_state_name, dialog_parent)
        if sub_editor_dialog.exec() == QDialog.Accepted:
            updated_data = sub_editor_dialog.get_updated_sub_fsm_data()
            self.current_sub_fsm_data = updated_data
            QMessageBox.information(self, "Sub-Machine Updated", "Sub-machine data has been updated in this dialog. Click OK to save these changes to the state.")

    def _choose_color(self):
        # ... (remains the same) ...
        color = QColorDialog.getColor(self.current_color, self, "Select State Color")
        if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self):
        # ... (remains the same) ...
        luminance = self.current_color.lightnessF()
        text_color_name = COLOR_TEXT_ON_ACCENT if luminance < 0.5 else COLOR_TEXT_PRIMARY
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color_name}; border: 1px solid {self.current_color.darker(130).name()};")

    def get_properties(self):
        sub_data_to_return = {'states': [], 'transitions': [], 'comments': []}
        if self.is_superstate_cb.isChecked():
            sub_data_to_return = self.current_sub_fsm_data
        
        props = {
            'name': self.name_edit.text().strip(), 'is_initial': self.is_initial_cb.isChecked(),
            'is_final': self.is_final_cb.isChecked(), 'color': self.current_color.name(),
            'action_language': self.action_language_combo.currentText(),
            'entry_action': self.entry_action_edit.toPlainText().strip(),
            'during_action': self.during_action_edit.toPlainText().strip(),
            'exit_action': self.exit_action_edit.toPlainText().strip(),
            'description': self.description_edit.toPlainText().strip(),
            'is_superstate': self.is_superstate_cb.isChecked(), 'sub_fsm_data': sub_data_to_return,
            # New visual props
            'shape_type': self.shape_combo.currentText().lower(),
            'font_family': self.font_family_combo.currentFont().family(),
            'font_size': self.font_size_spin.value(),
            'font_bold': self.font_bold_cb.isChecked(),
            'font_italic': self.font_italic_cb.isChecked(),
            'border_style_str': self.border_style_combo.currentText(),
            'border_width': self.border_width_spin.value(),
            'icon_path': self.icon_path_edit.text().strip()
        }
        return props

# ... (TransitionPropertiesDialog and other dialogs will need similar enhancements for their respective visual properties)
# For brevity, I will skip fully detailing them here but the pattern is:
# 1. Add UI controls for new visual properties.
# 2. Load initial values from `current_properties` or settings defaults.
# 3. Include new properties in `get_properties()`.

class TransitionPropertiesDialog(QDialog):
    # ... (Constructor and most of existing setup)
    # TODO: Add UI for line style, width, arrowhead, label font
    def __init__(self, parent=None, current_properties=None, is_new_transition=False, custom_snippet_manager: CustomSnippetManager | None = None): # Added custom_snippet_manager
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogInfoView, "Props"))
        self.setMinimumWidth(600)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#SafetyNote, QLabel#HardwareHintLabel {{ font-size: {APP_FONT_SIZE_SMALL}; color: {COLOR_TEXT_SECONDARY}; }} QGroupBox {{ background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102).name()}; }}")
        
        self.custom_snippet_manager = custom_snippet_manager 
        main_layout = QVBoxLayout(self)
        
        main_layout.setSpacing(10) 
        main_layout.setContentsMargins(12,12,12,12) 
        p = current_properties or {}

        logic_group = QGroupBox("Identification & Logic")
        logic_layout = QFormLayout(logic_group)
        logic_layout.setSpacing(8) 

        self.event_edit = QLineEdit(p.get('event', ""))
        self.condition_edit = QLineEdit(p.get('condition', ""))

        self.event_snippet_btn = self._create_insert_snippet_button_lineedit(self.event_edit, "events", " Event")
        self.condition_snippet_btn = self._create_insert_snippet_button_lineedit(self.condition_edit, "conditions", " Condition")

        def add_lineedit_with_snippet(form_layout, label_text, edit_widget, snippet_button, is_code_field=True):
            # ... (remains same) ...
            h_editor_btn_layout = QHBoxLayout(); h_editor_btn_layout.setSpacing(6)
            h_editor_btn_layout.addWidget(edit_widget, 1)
            v_btn_container = QVBoxLayout(); v_btn_container.addWidget(snippet_button);
            if is_code_field: v_btn_container.addStretch() 
            h_editor_btn_layout.addLayout(v_btn_container)
            field_v_layout = QVBoxLayout(); field_v_layout.setSpacing(3) 
            field_v_layout.addLayout(h_editor_btn_layout)
            if is_code_field: 
                safety_note_label = QLabel("<small><i>Note: Guard conditions are evaluated. Python syntax for sim.</i></small>")
                safety_note_label.setObjectName("SafetyNote")
                safety_note_label.setToolTip("Conditions are evaluated as Python expressions in the simulator.\nEnsure syntax is valid for the target language during code generation.")
                field_v_layout.addWidget(safety_note_label)
            form_layout.addRow(label_text, field_v_layout)

        add_lineedit_with_snippet(logic_layout, "Event Trigger:", self.event_edit, self.event_snippet_btn, is_code_field=False)
        add_lineedit_with_snippet(logic_layout, "Condition (Guard):", self.condition_edit, self.condition_snippet_btn, is_code_field=True)
        main_layout.addWidget(logic_group)

        action_group = QGroupBox("Transition Action")
        action_form_layout = QFormLayout(action_group)
        action_form_layout.setSpacing(8) 

        self.action_language_combo = QComboBox()
        self.action_language_combo.addItems(list(MECHATRONICS_SNIPPETS.keys()))
        self.action_language_combo.setCurrentText(p.get('action_language', DEFAULT_EXECUTION_ENV))
        action_form_layout.addRow("Action Language:", self.action_language_combo)

        self.action_edit = CodeEditor(); self.action_edit.setPlainText(p.get('action', "")); self.action_edit.setFixedHeight(80); self.action_edit.setObjectName("ActionCodeEditor") 
        self.action_snippet_btn = self._create_insert_snippet_button_codeeditor(self.action_edit, "actions", " Action")

        def add_codeeditor_with_snippet_and_hw_hint(form_layout, label_text, code_editor_widget, snippet_button):
            # ... (remains same) ...
            h_editor_btn_layout = QHBoxLayout(); h_editor_btn_layout.setSpacing(6)
            h_editor_btn_layout.addWidget(code_editor_widget, 1)
            v_btn_container = QVBoxLayout(); v_btn_container.setSpacing(3)
            v_btn_container.addWidget(snippet_button)
            hw_hint_label = QLabel("<small><i>E.g., `motor_speed = 100;` or `valve_open();`</i></small>")
            hw_hint_label.setObjectName("HardwareHintLabel"); hw_hint_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-style: italic; font-size: 7.5pt;")
            hw_hint_label.setToolTip("Consider actions that set hardware outputs or call control functions.")
            v_btn_container.addWidget(hw_hint_label)
            safety_note_label = QLabel("<small><i>Note: Code safety depends on target. Generic Python checked.</i></small>")
            safety_note_label.setObjectName("SafetyNote")
            v_btn_container.addWidget(safety_note_label)
            v_btn_container.addStretch(1)
            h_editor_btn_layout.addLayout(v_btn_container)
            form_layout.addRow(label_text, h_editor_btn_layout)
        add_codeeditor_with_snippet_and_hw_hint(action_form_layout, "Action:", self.action_edit, self.action_snippet_btn)
        main_layout.addWidget(action_group)

        self.action_language_combo.currentTextChanged.connect(self._on_action_language_changed)
        self._on_action_language_changed(self.action_language_combo.currentText()) 

        appearance_desc_group = QGroupBox("Appearance & Description")
        appearance_desc_layout = QFormLayout(appearance_desc_group)
        appearance_desc_layout.setSpacing(8) 
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton")
        self.current_color = QColor(p.get('color', COLOR_ITEM_TRANSITION_DEFAULT)); self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)
        appearance_desc_layout.addRow("Display Color:", self.color_button)
        self.offset_perp_spin = QSpinBox(); self.offset_perp_spin.setRange(-1000, 1000); self.offset_perp_spin.setValue(int(p.get('control_offset_x', 0))); self.offset_perp_spin.setSuffix(" px")
        self.offset_tang_spin = QSpinBox(); self.offset_tang_spin.setRange(-1000, 1000); self.offset_tang_spin.setValue(int(p.get('control_offset_y', 0))); self.offset_tang_spin.setSuffix(" px")
        curve_layout = QHBoxLayout()
        curve_layout.addWidget(QLabel("Bend (Perp):")); curve_layout.addWidget(self.offset_perp_spin,1); curve_layout.addSpacing(15)
        curve_layout.addWidget(QLabel("Mid Shift (Tang):")); curve_layout.addWidget(self.offset_tang_spin,1); curve_layout.addStretch()
        appearance_desc_layout.addRow("Curve Shape:", curve_layout)
        
        # Line Style
        self.line_style_combo = QComboBox()
        self.line_style_combo.addItems(list(SettingsManager.STRING_TO_QT_PEN_STYLE.keys()))
        self.line_style_combo.setCurrentText(p.get('line_style_str', "Solid"))
        appearance_desc_layout.addRow("Line Style:", self.line_style_combo)

        self.line_width_spin = QDoubleSpinBox()
        self.line_width_spin.setRange(0.5, 10.0); self.line_width_spin.setSingleStep(0.1)
        self.line_width_spin.setValue(p.get('line_width', 2.2)); self.line_width_spin.setDecimals(1)
        appearance_desc_layout.addRow("Line Width:", self.line_width_spin)

        # Arrowhead Style
        self.arrowhead_style_combo = QComboBox()
        self.arrowhead_style_combo.addItems(["Filled", "Open", "None"]) # Add more if supported by renderer
        self.arrowhead_style_combo.setCurrentText(p.get('arrowhead_style', "Filled").capitalize())
        appearance_desc_layout.addRow("Arrowhead:", self.arrowhead_style_combo)

        # Label Font
        label_font_group = QGroupBox("Label Font")
        label_font_layout = QFormLayout(label_font_group)
        self.label_font_family_combo = QFontComboBox()
        self.label_font_family_combo.setCurrentFont(QFont(p.get('label_font_family', APP_FONT_FAMILY)))
        label_font_layout.addRow("Family:", self.label_font_family_combo)
        self.label_font_size_spin = QSpinBox(); self.label_font_size_spin.setRange(6, 24)
        self.label_font_size_spin.setValue(p.get('label_font_size', 8))
        label_font_layout.addRow("Size:", self.label_font_size_spin)
        appearance_desc_layout.addWidget(label_font_group)


        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(60) 
        appearance_desc_layout.addRow("Description:", self.description_edit)
        main_layout.addWidget(appearance_desc_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        if is_new_transition: self.event_edit.setFocus()

    def get_properties(self):
        return {
            'event': self.event_edit.text().strip(),
            'condition': self.condition_edit.text().strip(),
            'action_language': self.action_language_combo.currentText(),
            'action': self.action_edit.toPlainText().strip(),
            'color': self.current_color.name(),
            'control_offset_x': self.offset_perp_spin.value(),
            'control_offset_y': self.offset_tang_spin.value(),
            'description': self.description_edit.toPlainText().strip(),
            # New visual props
            'line_style_str': self.line_style_combo.currentText(),
            'line_width': self.line_width_spin.value(),
            'arrowhead_style': self.arrowhead_style_combo.currentText().lower(),
            'label_font_family': self.label_font_family_combo.currentFont().family(),
            'label_font_size': self.label_font_size_spin.value()
        }
    def _update_snippet_button_menu(self, button: QPushButton, target_widget, language_mode: str, snippet_category: str):
        # ... (remains same) ...
        menu = button.menu()
        menu.clear()
        menu.setStyleSheet("QMenu { font-size: 9pt; } QMenu::item { padding: 5px 20px; }")

        built_in_snippets = MECHATRONICS_SNIPPETS.get(language_mode, {}).get(snippet_category, {})
        custom_snippets_dict = {}
        if self.custom_snippet_manager:
            custom_snippets_dict = self.custom_snippet_manager.get_custom_snippets(language_mode, snippet_category)

        if not built_in_snippets and not custom_snippets_dict:
            action = QAction(f"(No '{snippet_category}' snippets for {language_mode})", self)
            action.setEnabled(False)
            menu.addAction(action)
            button.setEnabled(False)
            return

        button.setEnabled(True)
        if built_in_snippets:
            built_in_header = QAction("Built-in Snippets", self); built_in_header.setEnabled(False) 
            menu.addAction(built_in_header)
            for name, snippet in built_in_snippets.items():
                action = QAction(name, self)
                self._connect_snippet_action(action, target_widget, snippet)
                menu.addAction(action)
        
        if custom_snippets_dict:
            if built_in_snippets: menu.addSeparator()
            custom_header = QAction("Custom Snippets", self); custom_header.setEnabled(False) 
            menu.addAction(custom_header)
            for name, snippet_code in custom_snippets_dict.items():
                action = QAction(f"{name}", self) 
                self._connect_snippet_action(action, target_widget, snippet_code)
                menu.addAction(action)
    def _connect_snippet_action(self, action: QAction, target_widget, snippet: str):
        # ... (remains same) ...
        if isinstance(target_widget, QLineEdit):
            def insert_logic_lineedit(checked=False, line_edit=target_widget, s=snippet):
                current_text = line_edit.text(); cursor_pos = line_edit.cursorPosition()
                new_text = current_text[:cursor_pos] + s + current_text[cursor_pos:]
                line_edit.setText(new_text); line_edit.setCursorPosition(cursor_pos + len(s))
            action.triggered.connect(insert_logic_lineedit)
        elif isinstance(target_widget, CodeEditor) or isinstance(target_widget, QTextEdit):
            action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n"))
    def _on_action_language_changed(self, language_mode: str):
        # ... (remains same) ...
        self.action_edit.set_language(language_mode)
        self._update_snippet_button_menu(self.event_snippet_btn, self.event_edit, language_mode, "events")
        self._update_snippet_button_menu(self.condition_snippet_btn, self.condition_edit, language_mode, "conditions")
        self._update_snippet_button_menu(self.action_snippet_btn, self.action_edit, language_mode, "actions")
    def _create_insert_snippet_button_lineedit(self, target_line_edit: QLineEdit, snippet_category: str, button_text="Insert..."):
        # ... (remains same) ...
        button = QPushButton(button_text); button.setObjectName("SnippetButton")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"InsSnip")); button.setIconSize(QSize(16,16))
        button.setToolTip(f"Insert common {snippet_category} snippets."); button.setMenu(QMenu(self))
        return button
    def _create_insert_snippet_button_codeeditor(self, target_code_editor: CodeEditor, snippet_category: str, button_text="Insert..."):
        # ... (remains same) ...
        button = QPushButton(button_text); button.setObjectName("SnippetButton")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"InsSnip")); button.setIconSize(QSize(16,16))
        button.setToolTip(f"Insert common {snippet_category} code snippets."); button.setMenu(QMenu(self))
        return button
    def _choose_color(self):
        # ... (remains same) ...
        color = QColorDialog.getColor(self.current_color, self, "Select Transition Color")
        if color.isValid(): self.current_color = color; self._update_color_button_style()
    def _update_color_button_style(self):
        # ... (remains same) ...
        luminance = self.current_color.lightnessF()
        text_color_name = COLOR_TEXT_ON_ACCENT if luminance < 0.5 else COLOR_TEXT_PRIMARY
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color_name}; border: 1px solid {self.current_color.darker(130).name()};")

class CommentPropertiesDialog(QDialog):
    # TODO: Add Font controls here
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent)
        self.setWindowTitle("Comment Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cmt"))
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }}")
        p = current_properties or {}; layout = QVBoxLayout(self)
        layout.setSpacing(8); layout.setContentsMargins(12,12,12,12)
        
        self.text_edit = QTextEdit(p.get('text', "Comment"))
        self.text_edit.setMinimumHeight(100); self.text_edit.setPlaceholderText("Enter your comment or note here.")
        
        # Apply existing font from properties or defaults
        current_font = QFont(p.get('font_family', APP_FONT_FAMILY), p.get('font_size', 9))
        if p.get('font_italic', True): current_font.setItalic(True)
        self.text_edit.setCurrentFont(current_font) # Apply to editor for immediate visual feedback
        
        layout.addWidget(QLabel("Comment Text:")); layout.addWidget(self.text_edit)

        # Font Controls
        font_group = QGroupBox("Font Style")
        font_layout = QFormLayout(font_group)
        self.font_family_combo = QFontComboBox()
        self.font_family_combo.setCurrentFont(current_font)
        font_layout.addRow("Family:", self.font_family_combo)
        self.font_size_spin = QSpinBox(); self.font_size_spin.setRange(6, 48); self.font_size_spin.setValue(current_font.pointSize())
        font_layout.addRow("Size:", self.font_size_spin)
        self.font_italic_cb = QCheckBox("Italic"); self.font_italic_cb.setChecked(current_font.italic())
        font_layout.addRow(self.font_italic_cb)
        layout.addWidget(font_group)

        # Apply font changes immediately to the text_edit for preview
        self.font_family_combo.currentFontChanged.connect(lambda f: self.text_edit.setFontFamily(f.family()))
        self.font_size_spin.valueChanged.connect(lambda s: self.text_edit.setFontPointSize(s))
        self.font_italic_cb.toggled.connect(lambda i: self.text_edit.setFontItalic(i))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setMinimumWidth(350); self.text_edit.setFocus(); self.text_edit.selectAll()
        
    def get_properties(self):
        return {
            'text': self.text_edit.toPlainText(),
            'font_family': self.font_family_combo.currentFont().family(),
            'font_size': self.font_size_spin.value(),
            'font_italic': self.font_italic_cb.isChecked()
        }

class MatlabSettingsDialog(QDialog):
    # ... (no changes in this iteration) ...
    def __init__(self, matlab_connection: MatlabConnection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings"); self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"))
        self.setMinimumWidth(550) 
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#TestStatusLabel {{ padding: 5px; border-radius: 3px; }} QGroupBox {{ background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102).name()}; }}")
        main_layout = QVBoxLayout(self); main_layout.setSpacing(10); main_layout.setContentsMargins(10,10,10,10) 
        path_group = QGroupBox("MATLAB Executable Path"); path_form_layout = QFormLayout()
        path_form_layout.setSpacing(6) 
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path)
        self.path_edit.setPlaceholderText("e.g., C:\\...\\MATLAB\\R202Xy\\bin\\matlab.exe")
        path_form_layout.addRow("Path:", self.path_edit)
        btn_layout = QHBoxLayout(); btn_layout.setSpacing(6) 
        auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_BrowserReload,"Det"), " Auto-detect")
        auto_detect_btn.clicked.connect(self._auto_detect); auto_detect_btn.setToolTip("Attempt to find MATLAB installations.")
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), " Browse...")
        browse_btn.clicked.connect(self._browse); browse_btn.setToolTip("Browse for MATLAB executable.")
        btn_layout.addWidget(auto_detect_btn); btn_layout.addWidget(browse_btn); btn_layout.addStretch()
        path_v_layout = QVBoxLayout(); path_v_layout.setSpacing(8) 
        path_v_layout.addLayout(path_form_layout); path_v_layout.addLayout(btn_layout)
        path_group.setLayout(path_v_layout); main_layout.addWidget(path_group)
        test_group = QGroupBox("Connection Test"); test_layout = QVBoxLayout(); test_layout.setSpacing(8) 
        self.test_status_label = QLabel("Status: Unknown"); self.test_status_label.setObjectName("TestStatusLabel")
        self.test_status_label.setWordWrap(True); self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse); self.test_status_label.setMinimumHeight(30) 
        test_btn = QPushButton(get_standard_icon(QStyle.SP_CommandLink,"Test"), " Test Connection")
        test_btn.clicked.connect(self._test_connection_and_update_label); test_btn.setToolTip("Test connection to the specified MATLAB path.")
        test_layout.addWidget(test_btn); test_layout.addWidget(self.test_status_label, 1)
        test_group.setLayout(test_layout); main_layout.addWidget(test_group)
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close")
        dialog_buttons.accepted.connect(self._apply_settings); dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)
        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        if self.matlab_connection.matlab_path and self.matlab_connection.connected:
             self._update_test_label_from_signal(True, f"Connected: {self.matlab_connection.matlab_path}")
        elif self.matlab_connection.matlab_path:
            self._update_test_label_from_signal(False, f"Path previously set, but connection unconfirmed or failed.")
        else: self._update_test_label_from_signal(False, "MATLAB path not set.")
    def _auto_detect(self):
        # ... (remains same) ...
        self.test_status_label.setText("Status: Auto-detecting MATLAB, please wait..."); self.test_status_label.setStyleSheet(f"font-style: italic; color: {COLOR_TEXT_SECONDARY}; background-color: {QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(120).name()};")
        from PyQt5.QtWidgets import QApplication; QApplication.processEvents()
        self.matlab_connection.detect_matlab()
    def _browse(self):
        # ... (remains same) ...
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        start_dir = QDir.homePath()
        if self.path_edit.text() and QDir(QDir.toNativeSeparators(self.path_edit.text())).exists():
             path_obj = QDir(self.path_edit.text()); path_obj.cdUp(); start_dir = path_obj.absolutePath()
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path: self.path_edit.setText(path); self._update_test_label_from_signal(False, "Path changed. Click 'Test Connection' or 'Apply & Close'.")
    def _test_connection_and_update_label(self):
        # ... (remains same) ...
        path = self.path_edit.text().strip()
        if not path: self._update_test_label_from_signal(False, "MATLAB path is empty. Cannot test."); return
        self.test_status_label.setText("Status: Testing connection, please wait..."); self.test_status_label.setStyleSheet(f"font-style: italic; color: {COLOR_TEXT_SECONDARY}; background-color: {QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(120).name()};")
        from PyQt5.QtWidgets import QApplication; QApplication.processEvents()
        if self.matlab_connection.set_matlab_path(path): self.matlab_connection.test_connection()
    def _update_test_label_from_signal(self, success, message):
        # ... (remains same) ...
        status_prefix = "Status: "; current_style = "font-weight: bold; padding: 5px; border-radius: 3px;"
        if success:
            status_text = "Connected! "
            if "path set and appears valid" in message : status_text = "Path Valid. "
            elif "test successful" in message : status_text = "Connected! "
            current_style += f"color: {COLOR_ACCENT_SUCCESS}; background-color: {QColor(COLOR_ACCENT_SUCCESS).lighter(180).name()};"
            self.test_status_label.setText(status_prefix + status_text + message)
        else:
            status_text = "Error. "
            current_style += f"color: {COLOR_ACCENT_ERROR}; background-color: {QColor(COLOR_ACCENT_ERROR).lighter(180).name()};"
            self.test_status_label.setText(status_prefix + status_text + message)
        self.test_status_label.setStyleSheet(current_style)
        if success and self.matlab_connection.matlab_path and not self.path_edit.text():
            self.path_edit.setText(self.matlab_connection.matlab_path)
    def _apply_settings(self):
        # ... (remains same) ...
        path = self.path_edit.text().strip()
        if self.matlab_connection.matlab_path != path:
            self.matlab_connection.set_matlab_path(path)
            if path and not self.matlab_connection.connected : self.matlab_connection.test_connection()
        self.accept()

class FindItemDialog(QDialog):
    # ... (no changes in this iteration) ...
    item_selected_for_focus = pyqtSignal(QGraphicsItem) 
    def __init__(self, parent=None, scene_ref=None): 
        super().__init__(parent)
        self.scene_ref = scene_ref
        self.setWindowTitle("Find Item") 
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "Find"))
        self.setWindowFlags((self.windowFlags() & ~Qt.WindowContextHelpButtonHint) | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(350) 
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10,10,10,10); layout.setSpacing(8)
        self.search_label = QLabel("Search for FSM Element (Text in Name, Event, Action, Comment, etc.):") 
        layout.addWidget(self.search_label)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Start typing to search...")
        self.search_input.textChanged.connect(self._update_results_list)
        self.search_input.returnPressed.connect(self._on_return_pressed)
        layout.addWidget(self.search_input)
        self.results_list = QListWidget()
        self.results_list.itemActivated.connect(self._on_item_activated) 
        layout.addWidget(self.results_list)
        self._populate_initial_list() 
        self.search_input.setFocus()
    def _get_item_display_text(self, item: QGraphicsItem) -> str:
        if isinstance(item, GraphicsStateItem): return f"State: {item.text_label}"
        elif isinstance(item, GraphicsTransitionItem):
            label = item._compose_label_string()
            return f"Transition: {item.start_item.text_label if item.start_item else '?'} -> {item.end_item.text_label if item.end_item else '?'} ({label if label else 'No event'})"
        elif isinstance(item, GraphicsCommentItem):
            text = item.toPlainText().split('\n')[0]
            return f"Comment: {text[:30] + '...' if len(text) > 30 else text}"
        return "Unknown Item"
    def _populate_initial_list(self): 
        self.results_list.clear()
        if not self.scene_ref: return
        all_items_with_text = []
        for item in self.scene_ref.items():
            if isinstance(item, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem)):
                list_item = QListWidgetItem(self._get_item_display_text(item))
                list_item.setData(Qt.UserRole, QVariant(item)) 
                all_items_with_text.append(list_item)
        all_items_with_text.sort(key=lambda x: x.text())
        for list_item_widget in all_items_with_text:
            self.results_list.addItem(list_item_widget)
    def _update_results_list(self):
        search_term = self.search_input.text().lower()
        self.results_list.clear()
        if not self.scene_ref: return
        if not search_term: self._populate_initial_list(); return
        matching_list_items = []
        for item in self.scene_ref.items():
            item_matches = False; searchable_text = ""
            if isinstance(item, GraphicsStateItem):
                props = item.get_data()
                searchable_text = (f"{props.get('name','')} {props.get('entry_action','')} {props.get('during_action','')} {props.get('exit_action','')} {props.get('description','')}").lower()
            elif isinstance(item, GraphicsTransitionItem):
                props = item.get_data()
                searchable_text = (f"{props.get('event','')} {props.get('condition','')} {props.get('action','')} {props.get('description','')}").lower()
            elif isinstance(item, GraphicsCommentItem):
                searchable_text = item.toPlainText().lower()
            if search_term in searchable_text: item_matches = True
            if item_matches:
                list_item = QListWidgetItem(self._get_item_display_text(item))
                list_item.setData(Qt.UserRole, QVariant(item)) 
                matching_list_items.append(list_item)
        matching_list_items.sort(key=lambda x: x.text())
        for list_item_widget in matching_list_items:
            self.results_list.addItem(list_item_widget)
    def _on_item_activated(self, list_item_widget: QListWidgetItem):
        if list_item_widget:
            stored_item_variant = list_item_widget.data(Qt.UserRole)
            if stored_item_variant is not None:
                actual_item = stored_item_variant 
                if actual_item: self.item_selected_for_focus.emit(actual_item)
    def _on_return_pressed(self):
        if self.results_list.count() > 0:
            current_or_first_item = self.results_list.currentItem() if self.results_list.currentItem() else self.results_list.item(0)
            if current_or_first_item: self._on_item_activated(current_or_first_item)
    def refresh_list(self): self._update_results_list()
    def keyPressEvent(self, event: QKeyEvent): 
        if event.key() == Qt.Key_Escape: self.reject() 
        elif event.key() in (Qt.Key_Up, Qt.Key_Down) and self.results_list.count() > 0:
            self.results_list.setFocus()
            if self.results_list.currentRow() == -1:
                self.results_list.setCurrentRow(0 if event.key() == Qt.Key_Down else self.results_list.count() -1)
        else: super().keyPressEvent(event)

class SettingsDialog(QDialog):
    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle(f"{APP_NAME} - Preferences")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Prefs"))
        self.setMinimumWidth(550) # Increased width
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#RestartNote {{ color: {COLOR_ACCENT_ERROR}; font-style:italic; }}")

        self.original_settings_on_open = {}

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # --- View Tab ---
        view_tab = QWidget()
        view_layout = QFormLayout(view_tab)
        view_layout.setSpacing(10); view_layout.setContentsMargins(10,10,10,10)
        self.show_grid_cb = QCheckBox("Show Diagram Grid")
        view_layout.addRow(self.show_grid_cb)
        self.snap_to_grid_cb = QCheckBox("Snap to Grid during Drag")
        view_layout.addRow(self.snap_to_grid_cb)
        self.snap_to_objects_cb = QCheckBox("Snap to Objects during Drag")
        view_layout.addRow(self.snap_to_objects_cb)
        self.show_snap_guidelines_cb = QCheckBox("Show Dynamic Snap Guidelines during Drag")
        view_layout.addRow(self.show_snap_guidelines_cb)
        self.tabs.addTab(view_tab, "View")

        # --- Appearance Tab (NEW) ---
        appearance_tab = QWidget()
        appearance_layout_main = QVBoxLayout(appearance_tab) # Main layout for the tab
        appearance_layout_main.setSpacing(10)
        appearance_layout_main.setContentsMargins(10,10,10,10)

        # Theme Selection
        theme_group = QGroupBox("Application Theme")
        theme_layout = QFormLayout(theme_group)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        theme_layout.addRow("Theme:", self.theme_combo)
        theme_restart_note = QLabel("<i>Application restart required for full theme change.</i>")
        theme_restart_note.setObjectName("RestartNote") # Use existing style
        theme_restart_note.setStyleSheet(f"font-size: {APP_FONT_SIZE_SMALL};")
        theme_layout.addRow(theme_restart_note)
        appearance_layout_main.addWidget(theme_group)

        # Canvas Colors
        canvas_colors_group = QGroupBox("Canvas & Grid Colors")
        canvas_colors_layout = QFormLayout(canvas_colors_group)
        
        self.grid_minor_color_button = QPushButton("Minor Grid Color...")
        self.grid_minor_color_button.clicked.connect(lambda: self._pick_color_for_button(self.grid_minor_color_button, "canvas_grid_minor_color"))
        canvas_colors_layout.addRow(self.grid_minor_color_button)

        self.grid_major_color_button = QPushButton("Major Grid Color...")
        self.grid_major_color_button.clicked.connect(lambda: self._pick_color_for_button(self.grid_major_color_button, "canvas_grid_major_color"))
        canvas_colors_layout.addRow(self.grid_major_color_button)

        self.snap_guideline_color_button = QPushButton("Snap Guideline Color...")
        self.snap_guideline_color_button.clicked.connect(lambda: self._pick_color_for_button(self.snap_guideline_color_button, "canvas_snap_guideline_color"))
        canvas_colors_layout.addRow(self.snap_guideline_color_button)
        appearance_layout_main.addWidget(canvas_colors_group)
        
        appearance_layout_main.addStretch() # Push groups to top
        self.tabs.addTab(appearance_tab, "Appearance")


        # --- Behavior Tab ---
        behavior_tab = QWidget()
        behavior_layout = QFormLayout(behavior_tab)
        behavior_layout.setSpacing(10); behavior_layout.setContentsMargins(10,10,10,10)
        self.resource_monitor_enabled_cb = QCheckBox("Enable Resource Monitor in Status Bar")
        self.resource_monitor_interval_spin = QSpinBox()
        self.resource_monitor_interval_spin.setRange(500, 60000); self.resource_monitor_interval_spin.setSingleStep(500); self.resource_monitor_interval_spin.setSuffix(" ms")
        behavior_layout.addRow(self.resource_monitor_enabled_cb)
        behavior_layout.addRow("Resource Monitor Update Interval:", self.resource_monitor_interval_spin)
        restart_note = QLabel("<i>Some settings may require an application restart to take full effect.</i>")
        restart_note.setObjectName("RestartNote"); restart_note.setStyleSheet(f"font-size: {APP_FONT_SIZE_SMALL};")
        behavior_layout.addRow(restart_note)
        self.tabs.addTab(behavior_tab, "Behavior")
        
        main_layout.addWidget(self.tabs)

        button_layout = QHBoxLayout()
        self.reset_defaults_button = QPushButton("Reset to Defaults")
        self.reset_defaults_button.clicked.connect(self.on_reset_to_defaults)
        button_layout.addWidget(self.reset_defaults_button)
        button_layout.addStretch()
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
        self.button_box.button(QDialogButtonBox.Ok).setText("OK & Save")
        self.button_box.button(QDialogButtonBox.Apply).clicked.connect(self.apply_settings)
        self.button_box.accepted.connect(self.accept_settings); self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)
        main_layout.addLayout(button_layout)

        self.load_settings_to_ui()

    def _pick_color_for_button(self, button: QPushButton, setting_key: str):
        current_color_hex = self.settings_manager.get(setting_key)
        initial_color = QColor(current_color_hex)
        
        dialog = QColorDialog(self)
        dialog.setCurrentColor(initial_color)
        if dialog.exec_():
            new_color = dialog.selectedColor()
            if new_color.isValid() and new_color != initial_color:
                button.setStyleSheet(f"background-color: {new_color.name()}; color: {COLOR_TEXT_ON_ACCENT if new_color.lightnessF() < 0.5 else COLOR_TEXT_PRIMARY};")
                # Store the new color hex directly on the button temporarily or update a temp dict
                button.setProperty("pendingColorHex", new_color.name()) 
                # Enable Apply button if not already
                self.button_box.button(QDialogButtonBox.Apply).setEnabled(True)


    def load_settings_to_ui(self):
        self.original_settings_on_open.clear()

        # View Tab
        self.show_grid_cb.setChecked(self.settings_manager.get("view_show_grid"))
        self.original_settings_on_open["view_show_grid"] = self.show_grid_cb.isChecked()
        self.snap_to_grid_cb.setChecked(self.settings_manager.get("view_snap_to_grid"))
        self.original_settings_on_open["view_snap_to_grid"] = self.snap_to_grid_cb.isChecked()
        self.snap_to_objects_cb.setChecked(self.settings_manager.get("view_snap_to_objects"))
        self.original_settings_on_open["view_snap_to_objects"] = self.snap_to_objects_cb.isChecked()
        self.show_snap_guidelines_cb.setChecked(self.settings_manager.get("view_show_snap_guidelines"))
        self.original_settings_on_open["view_show_snap_guidelines"] = self.show_snap_guidelines_cb.isChecked()

        # Appearance Tab
        self.theme_combo.setCurrentText(self.settings_manager.get("appearance_theme"))
        self.original_settings_on_open["appearance_theme"] = self.theme_combo.currentText()
        
        minor_grid_color = QColor(self.settings_manager.get("canvas_grid_minor_color"))
        self.grid_minor_color_button.setStyleSheet(f"background-color: {minor_grid_color.name()}; color: {COLOR_TEXT_ON_ACCENT if minor_grid_color.lightnessF() < 0.5 else COLOR_TEXT_PRIMARY};")
        self.grid_minor_color_button.setProperty("pendingColorHex", minor_grid_color.name()) # Store initial
        self.original_settings_on_open["canvas_grid_minor_color"] = minor_grid_color.name()
        
        major_grid_color = QColor(self.settings_manager.get("canvas_grid_major_color"))
        self.grid_major_color_button.setStyleSheet(f"background-color: {major_grid_color.name()}; color: {COLOR_TEXT_ON_ACCENT if major_grid_color.lightnessF() < 0.5 else COLOR_TEXT_PRIMARY};")
        self.grid_major_color_button.setProperty("pendingColorHex", major_grid_color.name())
        self.original_settings_on_open["canvas_grid_major_color"] = major_grid_color.name()

        snap_guide_color = QColor(self.settings_manager.get("canvas_snap_guideline_color"))
        self.snap_guideline_color_button.setStyleSheet(f"background-color: {snap_guide_color.name()}; color: {COLOR_TEXT_ON_ACCENT if snap_guide_color.lightnessF() < 0.5 else COLOR_TEXT_PRIMARY};")
        self.snap_guideline_color_button.setProperty("pendingColorHex", snap_guide_color.name())
        self.original_settings_on_open["canvas_snap_guideline_color"] = snap_guide_color.name()


        # Behavior Tab
        self.resource_monitor_enabled_cb.setChecked(self.settings_manager.get("resource_monitor_enabled"))
        self.original_settings_on_open["resource_monitor_enabled"] = self.resource_monitor_enabled_cb.isChecked()
        self.resource_monitor_interval_spin.setValue(self.settings_manager.get("resource_monitor_interval_ms"))
        self.original_settings_on_open["resource_monitor_interval_ms"] = self.resource_monitor_interval_spin.value()
        
        self.button_box.button(QDialogButtonBox.Apply).setEnabled(False) # Disable Apply on fresh load


    def apply_settings(self):
        logger.info("Applying settings from Preferences dialog.")
        
        # View Tab
        self.settings_manager.set("view_show_grid", self.show_grid_cb.isChecked(), save_immediately=False)
        self.settings_manager.set("view_snap_to_grid", self.snap_to_grid_cb.isChecked(), save_immediately=False)
        self.settings_manager.set("view_snap_to_objects", self.snap_to_objects_cb.isChecked(), save_immediately=False)
        self.settings_manager.set("view_show_snap_guidelines", self.show_snap_guidelines_cb.isChecked(), save_immediately=False)

        # Appearance Tab
        self.settings_manager.set("appearance_theme", self.theme_combo.currentText(), save_immediately=False)
        self.settings_manager.set("canvas_grid_minor_color", self.grid_minor_color_button.property("pendingColorHex"), save_immediately=False)
        self.settings_manager.set("canvas_grid_major_color", self.grid_major_color_button.property("pendingColorHex"), save_immediately=False)
        self.settings_manager.set("canvas_snap_guideline_color", self.snap_guideline_color_button.property("pendingColorHex"), save_immediately=False)


        # Behavior Tab
        self.settings_manager.set("resource_monitor_enabled", self.resource_monitor_enabled_cb.isChecked(), save_immediately=False)
        self.settings_manager.set("resource_monitor_interval_ms", self.resource_monitor_interval_spin.value(), save_immediately=False)

        self.settings_manager.save_settings() 
        self.load_settings_to_ui() # Refresh original_settings_on_open and disable Apply
        QMessageBox.information(self, "Settings Applied", "Settings have been applied. Some changes may require an application restart.")


    def accept_settings(self):
        if self.button_box.button(QDialogButtonBox.Apply).isEnabled(): # Only apply if changes were made
            self.apply_settings()
        self.accept()

    def on_reset_to_defaults(self):
        reply = QMessageBox.question(self, "Reset Settings",
                                     "Are you sure you want to reset all settings to their default values? "
                                     "This cannot be undone and may require an application restart.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.settings_manager.reset_to_defaults()
            self.load_settings_to_ui() 
            QMessageBox.information(self, "Settings Reset", "All settings have been reset to defaults. Please restart the application if necessary.")

    def reject(self):
        changed = False
        if self.show_grid_cb.isChecked() != self.original_settings_on_open.get("view_show_grid"): changed = True
        # ... (check all other original_settings_on_open values) ...
        if self.theme_combo.currentText() != self.original_settings_on_open.get("appearance_theme"): changed = True
        if self.grid_minor_color_button.property("pendingColorHex") != self.original_settings_on_open.get("canvas_grid_minor_color"): changed = True
        # ... etc. for all settings ...
        
        if self.button_box.button(QDialogButtonBox.Apply).isEnabled(): # Simpler check
            changed = True

        if changed:
            reply = QMessageBox.question(self, "Discard Changes?",
                                         "You have unsaved changes in the preferences. Discard them?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return 
        super().reject()
