
# bsm_designer_project/ai_chatbot.py
# No changes needed in this file based on the bug fixes,
# assuming ui_ai_chatbot_manager.py is removed and this one is used.

# bsm_designer_project/alignment_manager.py
# No changes needed here as the cleanup is handled in MainWindow.

# bsm_designer_project/code_editor.py
# No changes needed for these bug fixes.

# bsm_designer_project/config.py
# No changes needed for these bug fixes.

# bsm_designer_project/create_dummy_icons.py
# No changes needed.

# bsm_designer_project/debounce_template.json
# CONTENT WILL BE REMOVED (representing deletion)

# bsm_designer_project/c_code_generator.py
# No changes needed for these bug fixes.

# bsm_designer_project/dialogs.py
# Applying fix for TransitionPropertiesDialog snippet insertion
import sys
import json
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QCheckBox, QPushButton, QTextEdit,
    QSpinBox, QComboBox, QDialogButtonBox, QColorDialog, QHBoxLayout,
    QLabel, QFileDialog, QGroupBox, QMenu, QAction, QVBoxLayout, QStyle,
    QMessageBox, QInputDialog, QGraphicsView, QUndoStack, QToolBar, QActionGroup,
    QMainWindow,
    QListWidget, QListWidgetItem,
    QGraphicsItem
)
from PyQt5.QtGui import QColor, QIcon, QPalette, QKeyEvent
from PyQt5.QtCore import Qt, QDir, QSize, QPointF, pyqtSignal, QVariant

from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem
from config import (
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_ON_ACCENT, MECHATRONICS_SNIPPETS, COLOR_ACCENT_PRIMARY, COLOR_ACCENT_ERROR,
    DEFAULT_EXECUTION_ENV, EXECUTION_ENV_PYTHON_GENERIC, EXECUTION_ENV_ARDUINO_CPP,
    EXECUTION_ENV_C_GENERIC, EXECUTION_ENV_RASPBERRYPI_PYTHON, EXECUTION_ENV_MICROPYTHON,
    APP_FONT_SIZE_SMALL, COLOR_TEXT_SECONDARY, COLOR_BACKGROUND_DIALOG,COLOR_ACCENT_SUCCESS,
    COLOR_BACKGROUND_LIGHT, COLOR_ACCENT_PRIMARY_LIGHT, COLOR_BORDER_MEDIUM
)
from code_editor import CodeEditor
from utils import get_standard_icon
from matlab_integration import MatlabConnection

import logging
logger = logging.getLogger(__name__)

try:
    from graphics_scene import DiagramScene, ZoomableView
    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    print(f"SubFSMEditorDialog: Could not import DiagramScene/ZoomableView: {e}. Visual sub-editor will be disabled.")
    DiagramScene = None; ZoomableView = None; IMPORTS_SUCCESSFUL = False


class SubFSMEditorDialog(QDialog):
    def __init__(self, sub_fsm_data_initial: dict, parent_state_name: str, parent_window_ref=None):
        super().__init__(parent_window_ref)
        self.parent_window_ref = parent_window_ref
        self.setWindowTitle(f"Sub-Machine Editor: {parent_state_name}")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "SubEdit"))
        self.setMinimumSize(800, 600)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#ErrorLabel {{ color: {COLOR_ACCENT_ERROR}; font-weight: bold; }}")
        self.current_sub_fsm_data = sub_fsm_data_initial if isinstance(sub_fsm_data_initial, dict) else {'states': [], 'transitions': [], 'comments': []}
        layout = QVBoxLayout(self)

        if IMPORTS_SUCCESSFUL:
            self.sub_undo_stack = QUndoStack(self)
            self.sub_scene = DiagramScene(self.sub_undo_stack, parent_window=self)
            self.sub_view = ZoomableView(self.sub_scene, self)
            toolbar = QToolBar("Sub-Editor Tools"); toolbar.setIconSize(QSize(20,20)); toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            self.sub_mode_action_group = QActionGroup(self); self.sub_mode_action_group.setExclusive(True)
            actions_data = [
                ("select", "Select/Move", QStyle.SP_ArrowRight, "SelSub"), ("state", "Add State", QStyle.SP_FileDialogNewFolder, "StSub"),
                ("transition", "Add Transition", QStyle.SP_ArrowForward, "TrSub"), ("comment", "Add Comment", QStyle.SP_MessageBoxInformation, "CmSub")
            ]
            for mode, text, icon_enum, icon_alt in actions_data:
                action = QAction(get_standard_icon(icon_enum, icon_alt), text, self); action.setCheckable(True)
                action.triggered.connect(lambda checked=False, m=mode: self.sub_scene.set_mode(m)); toolbar.addAction(action)
                self.sub_mode_action_group.addAction(action); setattr(self, f"sub_{mode}_action", action)
            toolbar.addSeparator()
            self.sub_undo_action = self.sub_undo_stack.createUndoAction(self, "Undo"); self.sub_undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "UnSub")); toolbar.addAction(self.sub_undo_action)
            self.sub_redo_action = self.sub_undo_stack.createRedoAction(self, "Redo"); self.sub_redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "ReSub")); toolbar.addAction(self.sub_redo_action)
            layout.addWidget(toolbar); layout.addWidget(self.sub_view, 1)
            self.sub_scene.load_diagram_data(self.current_sub_fsm_data); self.sub_undo_stack.clear(); self.sub_scene.set_dirty(False)
            if hasattr(self, 'sub_select_action'): self.sub_select_action.setChecked(True); self.sub_scene.set_mode("select")
            self.status_label = QLabel("Visually edit the sub-machine. Click OK to save changes to the parent state.")
            self.status_label.setStyleSheet(f"font-size: {APP_FONT_SIZE_SMALL}; color: {COLOR_TEXT_SECONDARY};")
        else:
            self.json_edit_label = QLabel("<b>Visual Sub-Editor Failed to Load. Editing as JSON:</b>"); self.json_edit_label.setObjectName("ErrorLabel"); layout.addWidget(self.json_edit_label)
            error_detail_label = QLabel("<small><i>This might be due to missing optional dependencies or an unexpected error. Check console/logs. You can still edit raw JSON below.</i></small>")
            error_detail_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; margin-bottom: 5px;"); error_detail_label.setWordWrap(True); layout.addWidget(error_detail_label)
            self.json_text_edit = CodeEditor(); self.json_text_edit.setPlainText(json.dumps(self.current_sub_fsm_data, indent=2, ensure_ascii=False)); self.json_text_edit.setLineWrapMode(CodeEditor.NoWrap)
            try: self.json_text_edit.set_language("JSON")
            except Exception: logger.warning("JSON language not available in CodeEditor for SubFSM."); self.json_text_edit.set_language("Text")
            self.json_text_edit.setObjectName("SubFSMJsonEditor"); layout.addWidget(self.json_text_edit, 1)
            self.status_label = QLabel("Edit the JSON data for the sub-machine. Click OK to save changes.")
        layout.addWidget(self.status_label)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); button_box.accepted.connect(self.accept_changes); button_box.rejected.connect(self.reject); layout.addWidget(button_box)

    def accept_changes(self):
        if IMPORTS_SUCCESSFUL and hasattr(self, 'sub_scene'):
            updated_data = self.sub_scene.get_diagram_data()
            if isinstance(updated_data, dict) and all(k in updated_data for k in ['states', 'transitions', 'comments']) and isinstance(updated_data.get('states'), list) and isinstance(updated_data.get('transitions'), list) and isinstance(updated_data.get('comments'), list):
                sub_states_list = updated_data.get('states', [])
                if sub_states_list and not any(s.get('is_initial', False) for s in sub_states_list):
                    msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Warning); msg_box.setWindowTitle("No Initial Sub-State")
                    msg_box.setText("Sub-machine does not have an initial state. Recommended to define one."); save_anyway_btn = msg_box.addButton("Save Anyway", QMessageBox.AcceptRole)
                    set_first_btn = msg_box.addButton("Set First as Initial & Save", QMessageBox.YesRole); cancel_btn = msg_box.addButton(QMessageBox.Cancel); msg_box.setDefaultButton(cancel_btn); msg_box.exec_()
                    reply = msg_box.clickedButton()
                    if reply == cancel_btn: return
                    if reply == set_first_btn and sub_states_list: sub_states_list[0]['is_initial'] = True; self.log_message("INFO", f"Set state '{sub_states_list[0].get('name', 'Unnamed')}' as initial in sub-machine.")
                self.current_sub_fsm_data = updated_data; self.accept()
            else: QMessageBox.warning(self, "Invalid Sub-Machine Structure", "Unexpected sub-machine editor data structure."); logger.error("SubFSMEditorDialog: Invalid data structure from sub_scene.get_diagram_data().")
        elif hasattr(self, 'json_text_edit'):
            try:
                parsed_new_data = json.loads(self.json_text_edit.toPlainText())
                if isinstance(parsed_new_data, dict) and all(k in parsed_new_data for k in ['states', 'transitions', 'comments']):
                    sub_states_list_json = parsed_new_data.get('states', [])
                    if sub_states_list_json and not any(s.get('is_initial', False) for s in sub_states_list_json):
                        msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Warning); msg_box.setWindowTitle("No Initial Sub-State")
                        msg_box.setText("Sub-machine (JSON) does not have an initial state. Recommended."); save_anyway_btn = msg_box.addButton("Save Anyway", QMessageBox.AcceptRole)
                        set_first_btn = msg_box.addButton("Set First as Initial & Save", QMessageBox.YesRole); cancel_btn = msg_box.addButton(QMessageBox.Cancel); msg_box.setDefaultButton(cancel_btn); msg_box.exec_()
                        reply = msg_box.clickedButton()
                        if reply == cancel_btn: return
                        if reply == set_first_btn and sub_states_list_json: sub_states_list_json[0]['is_initial'] = True; self.log_message("INFO", f"Set state '{sub_states_list_json[0].get('name', 'Unnamed')}' as initial (JSON)."); self.json_text_edit.setPlainText(json.dumps(parsed_new_data, indent=2, ensure_ascii=False))
                    self.current_sub_fsm_data = parsed_new_data; self.accept()
                else: QMessageBox.warning(self, "Invalid JSON Structure", "JSON needs 'states', 'transitions', 'comments' lists.")
            except json.JSONDecodeError as e: QMessageBox.warning(self, "JSON Parse Error", f"Could not parse JSON: {e}")
        else: logger.error("SubFSMEditorDialog: Neither visual scene nor JSON editor found on accept_changes."); self.reject()

    def get_updated_sub_fsm_data(self) -> dict: return self.current_sub_fsm_data
    def log_message(self, level, message):
        print(f"SubFSMEditor Log ({level}): {message}")
        if self.parent_window_ref and hasattr(self.parent_window_ref, 'log_message') and callable(self.parent_window_ref.log_message): self.parent_window_ref.log_message(level.upper(), f"[SubEditor] {message}")


class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False, scene_ref=None):
        super().__init__(parent)
        self.setWindowTitle("State Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "Props")); self.setMinimumWidth(600)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#SafetyNote, QLabel#HardwareHintLabel {{ font-size: {APP_FONT_SIZE_SMALL}; color: {COLOR_TEXT_SECONDARY}; }} QGroupBox {{ background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102).name()}; }}")
        self.parent_window_ref = parent; self.scene_ref = scene_ref; p = current_properties or {}
        main_layout = QVBoxLayout(self); main_layout.setSpacing(12); main_layout.setContentsMargins(15,15,15,15)
        id_group = QGroupBox("Identification & Hierarchy"); id_layout = QFormLayout(id_group); id_layout.setSpacing(10)
        self.name_edit = QLineEdit(p.get('name', "StateName")); id_layout.addRow("Name:", self.name_edit)
        self.is_initial_cb = QCheckBox("Is Initial State"); self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Is Final State"); self.is_final_cb.setChecked(p.get('is_final', False))
        cb_layout = QHBoxLayout(); cb_layout.addWidget(self.is_initial_cb); cb_layout.addSpacing(20); cb_layout.addWidget(self.is_final_cb); cb_layout.addStretch(); id_layout.addRow("", cb_layout)
        self.is_superstate_cb = QCheckBox("Is Superstate (Composite State)"); self.is_superstate_cb.setChecked(p.get('is_superstate', False)); self.is_superstate_cb.toggled.connect(self._on_superstate_toggled)
        self.edit_sub_fsm_button = QPushButton(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Sub"), "Edit Sub-Machine..."); self.edit_sub_fsm_button.clicked.connect(self._on_edit_sub_fsm); self.edit_sub_fsm_button.setEnabled(self.is_superstate_cb.isChecked())
        cb_layout_super = QHBoxLayout(); cb_layout_super.addWidget(self.is_superstate_cb); cb_layout_super.addSpacing(10); cb_layout_super.addWidget(self.edit_sub_fsm_button); cb_layout_super.addStretch(); id_layout.addRow("Hierarchy:", cb_layout_super)
        raw_sub_fsm_data = p.get('sub_fsm_data', {}); self.current_sub_fsm_data = raw_sub_fsm_data if isinstance(raw_sub_fsm_data, dict) and all(k in raw_sub_fsm_data for k in ['states', 'transitions', 'comments']) and isinstance(raw_sub_fsm_data.get('states'), list) and isinstance(raw_sub_fsm_data.get('transitions'), list) and isinstance(raw_sub_fsm_data.get('comments'), list) else {'states': [], 'transitions': [], 'comments': []}
        if raw_sub_fsm_data and self.current_sub_fsm_data != raw_sub_fsm_data: logger.warning(f"State '{p.get('name', 'Unknown')}' had invalid sub_fsm_data, reset to empty.")
        main_layout.addWidget(id_group)
        appearance_group = QGroupBox("Appearance"); appearance_layout = QFormLayout(appearance_group); appearance_layout.setSpacing(10)
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton"); self.current_color = QColor(p.get('color', COLOR_ITEM_STATE_DEFAULT_BG)); self._update_color_button_style(); self.color_button.clicked.connect(self._choose_color); appearance_layout.addRow("Display Color:", self.color_button); main_layout.addWidget(appearance_group)
        actions_group = QGroupBox("State Actions"); actions_layout = QFormLayout(actions_group); actions_layout.setSpacing(10)
        self.action_language_combo = QComboBox(); self.action_language_combo.addItems(list(MECHATRONICS_SNIPPETS.keys())); self.action_language_combo.setCurrentText(p.get('action_language', DEFAULT_EXECUTION_ENV)); actions_layout.addRow("Action Language:", self.action_language_combo)
        self.entry_action_edit = CodeEditor(); self.entry_action_edit.setPlainText(p.get('entry_action', "")); self.entry_action_edit.setFixedHeight(100); self.entry_action_edit.setObjectName("ActionCodeEditor")
        self.during_action_edit = CodeEditor(); self.during_action_edit.setPlainText(p.get('during_action', "")); self.during_action_edit.setFixedHeight(100); self.during_action_edit.setObjectName("ActionCodeEditor")
        self.exit_action_edit = CodeEditor(); self.exit_action_edit.setPlainText(p.get('exit_action', "")); self.exit_action_edit.setFixedHeight(100); self.exit_action_edit.setObjectName("ActionCodeEditor")
        self.entry_action_snippet_btn = self._create_insert_snippet_button(self.entry_action_edit, "actions", " Action"); self.during_action_snippet_btn = self._create_insert_snippet_button(self.during_action_edit, "actions", " Action"); self.exit_action_snippet_btn = self._create_insert_snippet_button(self.exit_action_edit, "actions", " Action")
        self.action_language_combo.currentTextChanged.connect(self._on_action_language_changed); self._on_action_language_changed(self.action_language_combo.currentText())
        def add_field_with_note_and_hw_hint(form_layout, label_text, code_editor_widget, snippet_button):
            h_editor_btn_layout = QHBoxLayout(); h_editor_btn_layout.setSpacing(6); h_editor_btn_layout.addWidget(code_editor_widget, 1)
            v_btn_container = QVBoxLayout(); v_btn_container.setSpacing(3); v_btn_container.addWidget(snippet_button)
            hw_hint_label = QLabel("<small><i>E.g., Arduino: `digitalWrite(PIN, HIGH);`</i></small>"); hw_hint_label.setObjectName("HardwareHintLabel"); hw_hint_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-style: italic; font-size: 7.5pt;"); hw_hint_label.setToolTip("Hardware actions can be simulated or mapped to real hardware."); v_btn_container.addWidget(hw_hint_label)
            safety_note_label = QLabel("<small><i>Note: Code safety depends on target environment.</i></small>"); safety_note_label.setObjectName("SafetyNote"); safety_note_label.setToolTip("Python (Generic Simulation) code is checked for basic safety. Other environments rely on external compilers/interpreters."); v_btn_container.addWidget(safety_note_label)
            v_btn_container.addStretch(1); h_editor_btn_layout.addLayout(v_btn_container); form_layout.addRow(label_text, h_editor_btn_layout)
        add_field_with_note_and_hw_hint(actions_layout, "Entry Action:", self.entry_action_edit, self.entry_action_snippet_btn); add_field_with_note_and_hw_hint(actions_layout, "During Action:", self.during_action_edit, self.during_action_snippet_btn); add_field_with_note_and_hw_hint(actions_layout, "Exit Action:", self.exit_action_edit, self.exit_action_snippet_btn); main_layout.addWidget(actions_group)
        desc_group = QGroupBox("Description / Notes"); desc_layout = QVBoxLayout(desc_group); self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75); desc_layout.addWidget(self.description_edit); main_layout.addWidget(desc_group)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(self.accept); btns.rejected.connect(self.reject); main_layout.addWidget(btns)
        if is_new_state: self.name_edit.selectAll(); self.name_edit.setFocus()

    def _on_action_language_changed(self, language_mode: str):
        self.entry_action_edit.set_language(language_mode); self.during_action_edit.set_language(language_mode); self.exit_action_edit.set_language(language_mode)
        self._update_snippet_button_menu(self.entry_action_snippet_btn, self.entry_action_edit, language_mode, "actions"); self._update_snippet_button_menu(self.during_action_snippet_btn, self.during_action_edit, language_mode, "actions"); self._update_snippet_button_menu(self.exit_action_snippet_btn, self.exit_action_edit, language_mode, "actions")

    def _create_insert_snippet_button(self, target_widget: CodeEditor, snippet_category: str, button_text="Insert...", icon_size_px=16):
        button = QPushButton(button_text); button.setObjectName("SnippetButton"); button.setToolTip(f"Insert common {snippet_category[:-1] if snippet_category.endswith('s') else snippet_category} snippets"); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "InsSnip")); button.setIconSize(QSize(icon_size_px, icon_size_px)); button.setMenu(QMenu(self)); return button

    def _update_snippet_button_menu(self, button: QPushButton, target_widget: CodeEditor, language_mode: str, snippet_category: str):
        menu = button.menu(); menu.clear(); menu.setStyleSheet("QMenu { font-size: 9pt; } QMenu::item { padding: 5px 20px; }"); snippets_dict = MECHATRONICS_SNIPPETS.get(language_mode, {}).get(snippet_category, {})
        if not snippets_dict: action = QAction(f"(No '{snippet_category}' snippets for {language_mode})", self); action.setEnabled(False); menu.addAction(action)
        else:
            for name, snippet in snippets_dict.items(): action = QAction(name, self); action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n")); menu.addAction(action)
        button.setEnabled(bool(snippets_dict))

    def _on_superstate_toggled(self, checked):
        self.edit_sub_fsm_button.setEnabled(checked)
        if not checked and self.current_sub_fsm_data and (self.current_sub_fsm_data.get('states') or self.current_sub_fsm_data.get('transitions')):
            reply = QMessageBox.question(self, "Discard Sub-Machine?", "Unchecking 'Is Superstate' will clear its internal diagram data. Continue?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes: self.current_sub_fsm_data = {'states': [], 'transitions': [], 'comments': []}
            else: self.is_superstate_cb.blockSignals(True); self.is_superstate_cb.setChecked(True); self.is_superstate_cb.blockSignals(False); self.edit_sub_fsm_button.setEnabled(True)

    def _on_edit_sub_fsm(self):
        parent_state_name = self.name_edit.text().strip() or "Unnamed Superstate"; dialog_parent = self.parent()
        while dialog_parent and not isinstance(dialog_parent, QMainWindow) and hasattr(dialog_parent, 'parent') and callable(dialog_parent.parent):
            if dialog_parent.parent() == dialog_parent: break; dialog_parent = dialog_parent.parent()
        if not dialog_parent: dialog_parent = self
        sub_editor_dialog = SubFSMEditorDialog(self.current_sub_fsm_data, parent_state_name, dialog_parent)
        if sub_editor_dialog.exec() == QDialog.Accepted: self.current_sub_fsm_data = sub_editor_dialog.get_updated_sub_fsm_data(); QMessageBox.information(self, "Sub-Machine Updated", "Sub-machine data updated. Click OK to save changes to the state.")

    def _choose_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select State Color") # Removed redundant self.current_color argument
        if color.isValid():
            self.current_color = color;
            self._update_color_button_style()

    def _update_color_button_style(self): luminance = self.current_color.lightnessF(); text_color_name = COLOR_TEXT_ON_ACCENT if luminance < 0.5 else COLOR_TEXT_PRIMARY; self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color_name}; border: 1px solid {self.current_color.darker(130).name()};")

    def get_properties(self):
        sub_data_to_return = {'states': [], 'transitions': [], 'comments': []} if not self.is_superstate_cb.isChecked() else self.current_sub_fsm_data
        return {'name': self.name_edit.text().strip(), 'is_initial': self.is_initial_cb.isChecked(), 'is_final': self.is_final_cb.isChecked(), 'color': self.current_color.name(), 'action_language': self.action_language_combo.currentText(), 'entry_action': self.entry_action_edit.toPlainText().strip(), 'during_action': self.during_action_edit.toPlainText().strip(), 'exit_action': self.exit_action_edit.toPlainText().strip(), 'description': self.description_edit.toPlainText().strip(), 'is_superstate': self.is_superstate_cb.isChecked(), 'sub_fsm_data': sub_data_to_return}


class TransitionPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent); self.setWindowTitle("Transition Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogInfoView, "Props")); self.setMinimumWidth(600)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#SafetyNote, QLabel#HardwareHintLabel {{ font-size: {APP_FONT_SIZE_SMALL}; color: {COLOR_TEXT_SECONDARY}; }} QGroupBox {{ background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102).name()}; }}")
        main_layout = QVBoxLayout(self); main_layout.setSpacing(12); main_layout.setContentsMargins(15,15,15,15); p = current_properties or {}
        logic_group = QGroupBox("Identification & Logic"); logic_layout = QFormLayout(logic_group); logic_layout.setSpacing(10)
        self.event_edit = QLineEdit(p.get('event', "")); self.condition_edit = QLineEdit(p.get('condition', ""))
        self.event_snippet_btn = self._create_insert_snippet_button_lineedit(self.event_edit, "events", " Event"); self.condition_snippet_btn = self._create_insert_snippet_button_lineedit(self.condition_edit, "conditions", " Condition")
        def add_lineedit_with_snippet(form_layout, label_text, edit_widget, snippet_button, is_code_field=True):
            h_editor_btn_layout = QHBoxLayout(); h_editor_btn_layout.setSpacing(6); h_editor_btn_layout.addWidget(edit_widget, 1); v_btn_container = QVBoxLayout(); v_btn_container.addWidget(snippet_button);
            if is_code_field: v_btn_container.addStretch()
            h_editor_btn_layout.addLayout(v_btn_container); field_v_layout = QVBoxLayout(); field_v_layout.setSpacing(3); field_v_layout.addLayout(h_editor_btn_layout)
            if is_code_field: safety_note_label = QLabel("<small><i>Note: Guard conditions are Python expressions for sim.</i></small>"); safety_note_label.setObjectName("SafetyNote"); safety_note_label.setToolTip("Conditions are Python expressions in simulator. Ensure valid syntax for target language in code generation."); field_v_layout.addWidget(safety_note_label)
            form_layout.addRow(label_text, field_v_layout)
        add_lineedit_with_snippet(logic_layout, "Event Trigger:", self.event_edit, self.event_snippet_btn, is_code_field=False); add_lineedit_with_snippet(logic_layout, "Condition (Guard):", self.condition_edit, self.condition_snippet_btn, is_code_field=True); main_layout.addWidget(logic_group)
        action_group = QGroupBox("Transition Action"); action_form_layout = QFormLayout(action_group); action_form_layout.setSpacing(10)
        self.action_language_combo = QComboBox(); self.action_language_combo.addItems(list(MECHATRONICS_SNIPPETS.keys())); self.action_language_combo.setCurrentText(p.get('action_language', DEFAULT_EXECUTION_ENV)); action_form_layout.addRow("Action Language:", self.action_language_combo)
        self.action_edit = CodeEditor(); self.action_edit.setPlainText(p.get('action', "")); self.action_edit.setFixedHeight(100); self.action_edit.setObjectName("ActionCodeEditor"); self.action_snippet_btn = self._create_insert_snippet_button_codeeditor(self.action_edit, "actions", " Action")
        def add_codeeditor_with_snippet_and_hw_hint(form_layout, label_text, code_editor_widget, snippet_button):
            h_editor_btn_layout = QHBoxLayout(); h_editor_btn_layout.setSpacing(6); h_editor_btn_layout.addWidget(code_editor_widget, 1)
            v_btn_container = QVBoxLayout(); v_btn_container.setSpacing(3); v_btn_container.addWidget(snippet_button)
            hw_hint_label = QLabel("<small><i>E.g., `motor_speed = 100;` or `valve_open();`</i></small>"); hw_hint_label.setObjectName("HardwareHintLabel"); hw_hint_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-style: italic; font-size: 7.5pt;"); hw_hint_label.setToolTip("Hardware actions or control function calls."); v_btn_container.addWidget(hw_hint_label)
            safety_note_label = QLabel("<small><i>Note: Code safety depends on target. Python checked.</i></small>"); safety_note_label.setObjectName("SafetyNote"); v_btn_container.addWidget(safety_note_label); v_btn_container.addStretch(1); h_editor_btn_layout.addLayout(v_btn_container); form_layout.addRow(label_text, h_editor_btn_layout)
        add_codeeditor_with_snippet_and_hw_hint(action_form_layout, "Action:", self.action_edit, self.action_snippet_btn); main_layout.addWidget(action_group)
        self.action_language_combo.currentTextChanged.connect(self._on_action_language_changed); self._on_action_language_changed(self.action_language_combo.currentText())
        appearance_desc_group = QGroupBox("Appearance & Description"); appearance_desc_layout = QFormLayout(appearance_desc_group); appearance_desc_layout.setSpacing(10)
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton"); self.current_color = QColor(p.get('color', COLOR_ITEM_TRANSITION_DEFAULT)); self._update_color_button_style(); self.color_button.clicked.connect(self._choose_color); appearance_desc_layout.addRow("Display Color:", self.color_button)
        self.offset_perp_spin = QSpinBox(); self.offset_perp_spin.setRange(-1000, 1000); self.offset_perp_spin.setValue(int(p.get('control_offset_x', 0))); self.offset_perp_spin.setSuffix(" px"); self.offset_tang_spin = QSpinBox(); self.offset_tang_spin.setRange(-1000, 1000); self.offset_tang_spin.setValue(int(p.get('control_offset_y', 0))); self.offset_tang_spin.setSuffix(" px")
        curve_layout = QHBoxLayout(); curve_layout.addWidget(QLabel("Bend (Perp):")); curve_layout.addWidget(self.offset_perp_spin,1); curve_layout.addSpacing(15); curve_layout.addWidget(QLabel("Mid Shift (Tang):")); curve_layout.addWidget(self.offset_tang_spin,1); curve_layout.addStretch(); appearance_desc_layout.addRow("Curve Shape:", curve_layout)
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75); appearance_desc_layout.addRow("Description:", self.description_edit); main_layout.addWidget(appearance_desc_group)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); main_layout.addWidget(buttons)
        if is_new_transition: self.event_edit.setFocus()

    def _on_action_language_changed(self, language_mode: str):
        self.action_edit.set_language(language_mode); self._update_snippet_button_menu(self.event_snippet_btn, self.event_edit, language_mode, "events"); self._update_snippet_button_menu(self.condition_snippet_btn, self.condition_edit, language_mode, "conditions"); self._update_snippet_button_menu(self.action_snippet_btn, self.action_edit, language_mode, "actions")

    def _create_insert_snippet_button_lineedit(self, target_line_edit: QLineEdit, snippet_category: str, button_text="Insert..."): button = QPushButton(button_text); button.setObjectName("SnippetButton"); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"InsSnip")); button.setIconSize(QSize(16,16)); button.setToolTip(f"Insert common {snippet_category} snippets."); button.setMenu(QMenu(self)); return button
    def _create_insert_snippet_button_codeeditor(self, target_code_editor: CodeEditor, snippet_category: str, button_text="Insert..."): button = QPushButton(button_text); button.setObjectName("SnippetButton"); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"InsSnip")); button.setIconSize(QSize(16,16)); button.setToolTip(f"Insert common {snippet_category} code snippets."); button.setMenu(QMenu(self)); return button

    def _update_snippet_button_menu(self, button: QPushButton, target_widget, language_mode: str, snippet_category: str):
        menu = button.menu(); menu.clear(); menu.setStyleSheet("QMenu { font-size: 9pt; } QMenu::item { padding: 5px 20px; }"); snippets_dict = MECHATRONICS_SNIPPETS.get(language_mode, {}).get(snippet_category, {})
        if not snippets_dict: action = QAction(f"(No '{snippet_category}' snippets for {language_mode})", self); action.setEnabled(False); menu.addAction(action)
        else:
            for name, snippet in snippets_dict.items():
                action = QAction(name, self)
                if isinstance(target_widget, QLineEdit):
                    action.triggered.connect(lambda checked=False, line_edit=target_widget, s=snippet: line_edit.insert(s)) # MODIFIED HERE
                elif isinstance(target_widget, CodeEditor):
                    action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n"))
                menu.addAction(action)
        button.setEnabled(bool(snippets_dict))

    def _choose_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select Transition Color");
        if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self): luminance = self.current_color.lightnessF(); text_color_name = COLOR_TEXT_ON_ACCENT if luminance < 0.5 else COLOR_TEXT_PRIMARY; self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color_name}; border: 1px solid {self.current_color.darker(130).name()};")

    def get_properties(self): return {'event': self.event_edit.text().strip(), 'condition': self.condition_edit.text().strip(), 'action_language': self.action_language_combo.currentText(), 'action': self.action_edit.toPlainText().strip(), 'color': self.current_color.name(), 'control_offset_x': self.offset_perp_spin.value(), 'control_offset_y': self.offset_tang_spin.value(), 'description': self.description_edit.toPlainText().strip()}


class CommentPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent); self.setWindowTitle("Comment Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cmt")); self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }}")
        p = current_properties or {}; layout = QVBoxLayout(self); layout.setSpacing(10); layout.setContentsMargins(15,15,15,15)
        self.text_edit = QTextEdit(p.get('text', "Comment")); self.text_edit.setMinimumHeight(120); self.text_edit.setPlaceholderText("Enter your comment or note here."); self.text_edit.setFontPointSize(10); layout.addWidget(QLabel("Comment Text:")); layout.addWidget(self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons); self.setMinimumWidth(400); self.text_edit.setFocus(); self.text_edit.selectAll()
    def get_properties(self): return {'text': self.text_edit.toPlainText()}


class HistoryPseudoStatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, parent_superstate_item: GraphicsStateItem = None):
        super().__init__(parent)
        self.setWindowTitle("History Pseudo-State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "PropsH"))
        self.setMinimumWidth(400)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QGroupBox {{ background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102).name()}; }}")
        p = current_properties or {}
        self.parent_superstate_item_ref = parent_superstate_item
        main_layout = QVBoxLayout(self); main_layout.setSpacing(12); main_layout.setContentsMargins(15, 15, 15, 15)
        details_group = QGroupBox("Details"); details_layout = QFormLayout(details_group); details_layout.setSpacing(10)
        history_type_str = p.get('type', 'shallow')
        self.type_label = QLabel(f"<b>{history_type_str.capitalize()} History ({'H' if history_type_str == 'shallow' else 'H*'})</b>"); details_layout.addRow("Type:", self.type_label)
        parent_name_str = p.get('parent_superstate_name', "<i>N/A - Parent not set</i>"); self.parent_name_label = QLabel(f"<i>{parent_name_str}</i>"); details_layout.addRow("Parent Superstate:", self.parent_name_label)
        self.default_target_combo = QComboBox(); self._populate_default_target_combo(p.get('default_target_substate_name')); details_layout.addRow("Default Target Sub-state:", self.default_target_combo); main_layout.addWidget(details_group)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(self.accept); btns.rejected.connect(self.reject); main_layout.addWidget(btns)
        if self.default_target_combo.count() > 0: self.default_target_combo.setFocus()
        else:
            btns.button(QDialogButtonBox.Ok).setFocus()
            if self.parent_superstate_item_ref and (not self.parent_superstate_item_ref.sub_fsm_data or not self.parent_superstate_item_ref.sub_fsm_data.get('states')):
                no_substates_label = QLabel("<small><i>Note: Parent superstate has no sub-states defined. Add sub-states to select a default target.</i></small>")
                no_substates_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-style: italic;"); main_layout.insertWidget(main_layout.count() -1, no_substates_label)

    def _populate_default_target_combo(self, current_default_target_name: str | None):
        self.default_target_combo.clear(); self.default_target_combo.addItem("", None)
        if self.parent_superstate_item_ref and self.parent_superstate_item_ref.is_superstate:
            sub_states_data = self.parent_superstate_item_ref.sub_fsm_data.get('states', [])
            if not sub_states_data: self.default_target_combo.setEnabled(False); self.default_target_combo.setToolTip("Parent superstate has no sub-states defined."); return
            self.default_target_combo.setEnabled(True); self.default_target_combo.setToolTip("Select sub-state if no history available.")
            current_index_to_set = 0
            for i, sub_state_dict in enumerate(sub_states_data):
                sub_state_name = sub_state_dict.get('name')
                if sub_state_name: self.default_target_combo.addItem(sub_state_name, sub_state_name);
                if sub_state_name == current_default_target_name: current_index_to_set = i + 1
            self.default_target_combo.setCurrentIndex(current_index_to_set)
        else: self.default_target_combo.setEnabled(False); self.default_target_combo.setToolTip("Parent superstate not available or not a superstate.")

    def get_properties(self) -> dict:
        selected_target_name = self.default_target_combo.currentData();
        return {'default_target_substate_name': selected_target_name if selected_target_name else None}


class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection: MatlabConnection, parent=None):
        super().__init__(parent); self.matlab_connection = matlab_connection; self.setWindowTitle("MATLAB Settings"); self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg")); self.setMinimumWidth(600)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#TestStatusLabel {{ padding: 5px; border-radius: 3px; }} QGroupBox {{ background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102).name()}; }}")
        main_layout = QVBoxLayout(self); main_layout.setSpacing(12); main_layout.setContentsMargins(12,12,12,12); path_group = QGroupBox("MATLAB Executable Path"); path_form_layout = QFormLayout(); path_form_layout.setSpacing(8)
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path); self.path_edit.setPlaceholderText("e.g., C:\\...\\MATLAB\\R202Xy\\bin\\matlab.exe"); path_form_layout.addRow("Path:", self.path_edit)
        btn_layout = QHBoxLayout(); btn_layout.setSpacing(8); auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_BrowserReload,"Det"), " Auto-detect"); auto_detect_btn.clicked.connect(self._auto_detect); auto_detect_btn.setToolTip("Attempt to find MATLAB installations.")
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), " Browse..."); browse_btn.clicked.connect(self._browse); browse_btn.setToolTip("Browse for MATLAB executable.")
        btn_layout.addWidget(auto_detect_btn); btn_layout.addWidget(browse_btn); btn_layout.addStretch(); path_v_layout = QVBoxLayout(); path_v_layout.setSpacing(10); path_v_layout.addLayout(path_form_layout); path_v_layout.addLayout(btn_layout); path_group.setLayout(path_v_layout); main_layout.addWidget(path_group)
        test_group = QGroupBox("Connection Test"); test_layout = QVBoxLayout(); test_layout.setSpacing(10); self.test_status_label = QLabel("Status: Unknown"); self.test_status_label.setObjectName("TestStatusLabel"); self.test_status_label.setWordWrap(True); self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse); self.test_status_label.setMinimumHeight(35)
        test_btn = QPushButton(get_standard_icon(QStyle.SP_CommandLink,"Test"), " Test Connection"); test_btn.clicked.connect(self._test_connection_and_update_label); test_btn.setToolTip("Test connection to the specified MATLAB path."); test_layout.addWidget(test_btn); test_layout.addWidget(self.test_status_label, 1); test_group.setLayout(test_layout); main_layout.addWidget(test_group)
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close"); dialog_buttons.accepted.connect(self._apply_settings); dialog_buttons.rejected.connect(self.reject); main_layout.addWidget(dialog_buttons)
        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        if self.matlab_connection.matlab_path and self.matlab_connection.connected: self._update_test_label_from_signal(True, f"Connected: {self.matlab_connection.matlab_path}")
        elif self.matlab_connection.matlab_path: self._update_test_label_from_signal(False, f"Path set, connection unconfirmed.")
        else: self._update_test_label_from_signal(False, "MATLAB path not set.")

    def _auto_detect(self): self.test_status_label.setText("Status: Auto-detecting MATLAB, please wait..."); self.test_status_label.setStyleSheet(f"font-style: italic; color: {COLOR_TEXT_SECONDARY}; background-color: {QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(120).name()};"); QApplication.processEvents(); self.matlab_connection.detect_matlab()
    def _browse(self):
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        start_dir = QDir.homePath(); path_obj = QDir(self.path_edit.text()); path_obj.cdUp(); start_dir = path_obj.absolutePath() if self.path_edit.text() and QDir(QDir.toNativeSeparators(self.path_edit.text())).exists() else start_dir
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path: self.path_edit.setText(path); self._update_test_label_from_signal(False, "Path changed. Test or Apply.")
    def _test_connection_and_update_label(self):
        path = self.path_edit.text().strip();
        if not path: self._update_test_label_from_signal(False, "MATLAB path is empty."); return
        self.test_status_label.setText("Status: Testing connection, please wait..."); self.test_status_label.setStyleSheet(f"font-style: italic; color: {COLOR_TEXT_SECONDARY}; background-color: {QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(120).name()};"); QApplication.processEvents()
        if self.matlab_connection.set_matlab_path(path): self.matlab_connection.test_connection()
    def _update_test_label_from_signal(self, success, message):
        status_prefix = "Status: "; current_style = "font-weight: bold; padding: 5px; border-radius: 3px;"
        if success: status_text = "Connected! " if "test successful" in message else "Path Valid. "; current_style += f"color: {COLOR_ACCENT_SUCCESS}; background-color: {QColor(COLOR_ACCENT_SUCCESS).lighter(180).name()};"; self.test_status_label.setText(status_prefix + status_text + message)
        else: status_text = "Error. "; current_style += f"color: {COLOR_ACCENT_ERROR}; background-color: {QColor(COLOR_ACCENT_ERROR).lighter(180).name()};"; self.test_status_label.setText(status_prefix + status_text + message)
        self.test_status_label.setStyleSheet(current_style)
        if success and self.matlab_connection.matlab_path and not self.path_edit.text(): self.path_edit.setText(self.matlab_connection.matlab_path)
    def _apply_settings(self):
        path = self.path_edit.text().strip()
        if self.matlab_connection.matlab_path != path: self.matlab_connection.set_matlab_path(path);
        if path and not self.matlab_connection.connected : self.matlab_connection.test_connection()
        self.accept()


class FindItemDialog(QDialog):
    item_selected_for_focus = pyqtSignal(QGraphicsItem)
    def __init__(self, parent=None, scene_ref=None):
        super().__init__(parent); self.scene_ref = scene_ref; self.setWindowTitle("Find Item"); self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "Find"))
        self.setWindowFlags((self.windowFlags() & ~Qt.WindowContextHelpButtonHint) | Qt.WindowStaysOnTopHint); self.setMinimumWidth(350); self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }}")
        layout = QVBoxLayout(self); layout.setContentsMargins(10,10,10,10); layout.setSpacing(8); self.search_label = QLabel("Search for FSM Element (Text in Name, Event, Action, Comment, etc.):"); layout.addWidget(self.search_label)
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Start typing to search..."); self.search_input.textChanged.connect(self._update_results_list); self.search_input.returnPressed.connect(self._on_return_pressed); layout.addWidget(self.search_input)
        self.results_list = QListWidget(); self.results_list.itemActivated.connect(self._on_item_activated); layout.addWidget(self.results_list); self._populate_initial_list(); self.search_input.setFocus()
    def _get_item_display_text(self, item: QGraphicsItem) -> str:
        if isinstance(item, GraphicsStateItem): return f"State: {item.text_label}"
        elif isinstance(item, GraphicsTransitionItem): label = item._compose_label_string(); return f"Transition: {item.start_item.text_label if item.start_item else '?'} -> {item.end_item.text_label if item.end_item else '?'} ({label if label else 'No event'})"
        elif isinstance(item, GraphicsCommentItem): text = item.toPlainText().split('\n')[0]; return f"Comment: {text[:30] + '...' if len(text) > 30 else text}"
        elif isinstance(item, GraphicsHistoryPseudoStateItem): return f"History: {item.text_label} (in {item.parent_superstate_item.text_label if item.parent_superstate_item else 'None'})"
        return "Unknown Item"
    def _populate_initial_list(self):
        self.results_list.clear();
        if not self.scene_ref: return
        all_items_with_text = []
        for item in self.scene_ref.items():
            if isinstance(item, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem)): # Added H-item
                list_item = QListWidgetItem(self._get_item_display_text(item)); list_item.setData(Qt.UserRole, QVariant(item)); all_items_with_text.append(list_item)
        all_items_with_text.sort(key=lambda x: x.text()); [self.results_list.addItem(list_item_widget) for list_item_widget in all_items_with_text]
    def _update_results_list(self):
        search_term = self.search_input.text().lower(); self.results_list.clear()
        if not self.scene_ref: return
        if not search_term: self._populate_initial_list(); return
        matching_list_items = []
        for item in self.scene_ref.items():
            item_matches = False; searchable_text = ""
            if isinstance(item, GraphicsStateItem): props = item.get_data(); searchable_text = (f"{props.get('name','')} {props.get('entry_action','')} {props.get('during_action','')} {props.get('exit_action','')} {props.get('description','')}").lower()
            elif isinstance(item, GraphicsTransitionItem): props = item.get_data(); searchable_text = (f"{props.get('event','')} {props.get('condition','')} {props.get('action','')} {props.get('description','')}").lower()
            elif isinstance(item, GraphicsCommentItem): searchable_text = item.toPlainText().lower()
            elif isinstance(item, GraphicsHistoryPseudoStateItem): props = item.get_data(); searchable_text = (f"history {props.get('type','')} {props.get('parent_superstate_name','')}").lower()
            if search_term in searchable_text: item_matches = True
            if item_matches: list_item = QListWidgetItem(self._get_item_display_text(item)); list_item.setData(Qt.UserRole, QVariant(item)); matching_list_items.append(list_item)
        matching_list_items.sort(key=lambda x: x.text()); [self.results_list.addItem(list_item_widget) for list_item_widget in matching_list_items]
    def _on_item_activated(self, list_item_widget: QListWidgetItem):
        if list_item_widget:
            stored_item_variant = list_item_widget.data(Qt.UserRole)
            if stored_item_variant is not None:
                actual_item = stored_item_variant # QVariant automatically converts to original type
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
            if self.results_list.currentRow() == -1: self.results_list.setCurrentRow(0 if event.key() == Qt.Key_Down else self.results_list.count() -1)
        else: super().keyPressEvent(event)

# bsm_designer_project/docs/QUICK_START.html
# No changes needed.

# bsm_designer_project/examples/simple_toggle.bsm
# No changes needed.

# bsm_designer_project/examples/traffic_light.bsm
# No changes needed.

# bsm_designer_project/export_utils.py
# No changes needed for these bug fixes.

# bsm_designer_project/file_operations_manager.py
# No changes needed for these bug fixes.

# bsm_designer_project/fsm_simulator.py
# No changes needed for these bug fixes.

# bsm_designer_project/graphics_items.py
# No changes needed for these bug fixes.

# bsm_designer_project/graphics_scene.py
# No changes needed for these bug fixes.

# bsm_designer_project/ide_manager.py
# No changes needed for these bug fixes.

# bsm_designer_project/logging_setup.py
# No changes needed.

# bsm_designer_project/main.py
# No changes needed based on the review; existing code already seems to incorporate fixes.

# bsm_designer_project/matlab_integration.py
# No changes needed for these bug fixes.

# bsm_designer_project/matlab_operations_manager.py
# No changes needed for these bug fixes.

# bsm_designer_project/resources.qrc
# No changes needed.

# bsm_designer_project/resources_rc.py
# No changes needed (this is a generated file).

# bsm_designer_project/run_test_fsm.py
# No changes needed.

# bsm_designer_project/statemachine/*
# These are library files, assumed correct. No changes.

# bsm_designer_project/test_graphviz.py
# No changes needed.

# bsm_designer_project/ui_ai_chatbot_manager.py
# CONTENT WILL BE REMOVED (representing deletion)

# bsm_designer_project/ui_py_simulation_manager.py
# No changes needed for these bug fixes.

# bsm_designer_project/undo_commands.py
# No changes needed for these bug fixes.

# bsm_designer_project/utils.py
# No changes needed.

# bsm_designer_project/view_manager.py
# No changes needed for these bug fixes.

# bsm_designer_project/__init__.py
# No changes needed.
```

```
--- START OF FILE bsm_designer_project/debounce_template.json ---
--- END OF FILE bsm_designer_project/debounce_template.json ---
```

```
--- START OF FILE bsm_designer_project/ui_ai_chatbot_manager.py ---
--- END OF FILE bsm_designer_project/ui_ai_chatbot_manager.py ---
```

```python
# bsm_designer_project/dialogs.py
# Applying fix for TransitionPropertiesDialog snippet insertion
import sys
import json
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QCheckBox, QPushButton, QTextEdit,
    QSpinBox, QComboBox, QDialogButtonBox, QColorDialog, QHBoxLayout,
    QLabel, QFileDialog, QGroupBox, QMenu, QAction, QVBoxLayout, QStyle,
    QMessageBox, QInputDialog, QGraphicsView, QUndoStack, QToolBar, QActionGroup,
    QMainWindow,
    QListWidget, QListWidgetItem,
    QGraphicsItem
)
from PyQt5.QtGui import QColor, QIcon, QPalette, QKeyEvent
from PyQt5.QtCore import Qt, QDir, QSize, QPointF, pyqtSignal, QVariant

from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem
from config import (
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_ON_ACCENT, MECHATRONICS_SNIPPETS, COLOR_ACCENT_PRIMARY, COLOR_ACCENT_ERROR,
    DEFAULT_EXECUTION_ENV, EXECUTION_ENV_PYTHON_GENERIC, EXECUTION_ENV_ARDUINO_CPP,
    EXECUTION_ENV_C_GENERIC, EXECUTION_ENV_RASPBERRYPI_PYTHON, EXECUTION_ENV_MICROPYTHON,
    APP_FONT_SIZE_SMALL, COLOR_TEXT_SECONDARY, COLOR_BACKGROUND_DIALOG,COLOR_ACCENT_SUCCESS,
    COLOR_BACKGROUND_LIGHT, COLOR_ACCENT_PRIMARY_LIGHT, COLOR_BORDER_MEDIUM
)
from code_editor import CodeEditor
from utils import get_standard_icon
from matlab_integration import MatlabConnection

import logging
logger = logging.getLogger(__name__)

try:
    from graphics_scene import DiagramScene, ZoomableView
    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    print(f"SubFSMEditorDialog: Could not import DiagramScene/ZoomableView: {e}. Visual sub-editor will be disabled.")
    DiagramScene = None; ZoomableView = None; IMPORTS_SUCCESSFUL = False


class SubFSMEditorDialog(QDialog):
    def __init__(self, sub_fsm_data_initial: dict, parent_state_name: str, parent_window_ref=None):
        super().__init__(parent_window_ref)
        self.parent_window_ref = parent_window_ref
        self.setWindowTitle(f"Sub-Machine Editor: {parent_state_name}")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "SubEdit"))
        self.setMinimumSize(800, 600)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#ErrorLabel {{ color: {COLOR_ACCENT_ERROR}; font-weight: bold; }}")
        self.current_sub_fsm_data = sub_fsm_data_initial if isinstance(sub_fsm_data_initial, dict) else {'states': [], 'transitions': [], 'comments': []}
        layout = QVBoxLayout(self)

        if IMPORTS_SUCCESSFUL:
            self.sub_undo_stack = QUndoStack(self)
            self.sub_scene = DiagramScene(self.sub_undo_stack, parent_window=self)
            self.sub_view = ZoomableView(self.sub_scene, self)
            toolbar = QToolBar("Sub-Editor Tools"); toolbar.setIconSize(QSize(20,20)); toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            self.sub_mode_action_group = QActionGroup(self); self.sub_mode_action_group.setExclusive(True)
            actions_data = [
                ("select", "Select/Move", QStyle.SP_ArrowRight, "SelSub"), ("state", "Add State", QStyle.SP_FileDialogNewFolder, "StSub"),
                ("transition", "Add Transition", QStyle.SP_ArrowForward, "TrSub"), ("comment", "Add Comment", QStyle.SP_MessageBoxInformation, "CmSub")
            ]
            for mode, text, icon_enum, icon_alt in actions_data:
                action = QAction(get_standard_icon(icon_enum, icon_alt), text, self); action.setCheckable(True)
                action.triggered.connect(lambda checked=False, m=mode: self.sub_scene.set_mode(m)); toolbar.addAction(action)
                self.sub_mode_action_group.addAction(action); setattr(self, f"sub_{mode}_action", action)
            toolbar.addSeparator()
            self.sub_undo_action = self.sub_undo_stack.createUndoAction(self, "Undo"); self.sub_undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "UnSub")); toolbar.addAction(self.sub_undo_action)
            self.sub_redo_action = self.sub_undo_stack.createRedoAction(self, "Redo"); self.sub_redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "ReSub")); toolbar.addAction(self.sub_redo_action)
            layout.addWidget(toolbar); layout.addWidget(self.sub_view, 1)
            self.sub_scene.load_diagram_data(self.current_sub_fsm_data); self.sub_undo_stack.clear(); self.sub_scene.set_dirty(False)
            if hasattr(self, 'sub_select_action'): self.sub_select_action.setChecked(True); self.sub_scene.set_mode("select")
            self.status_label = QLabel("Visually edit the sub-machine. Click OK to save changes to the parent state.")
            self.status_label.setStyleSheet(f"font-size: {APP_FONT_SIZE_SMALL}; color: {COLOR_TEXT_SECONDARY};")
        else:
            self.json_edit_label = QLabel("<b>Visual Sub-Editor Failed to Load. Editing as JSON:</b>"); self.json_edit_label.setObjectName("ErrorLabel"); layout.addWidget(self.json_edit_label)
            error_detail_label = QLabel("<small><i>This might be due to missing optional dependencies or an unexpected error. Check console/logs. You can still edit raw JSON below.</i></small>")
            error_detail_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; margin-bottom: 5px;"); error_detail_label.setWordWrap(True); layout.addWidget(error_detail_label)
            self.json_text_edit = CodeEditor(); self.json_text_edit.setPlainText(json.dumps(self.current_sub_fsm_data, indent=2, ensure_ascii=False)); self.json_text_edit.setLineWrapMode(CodeEditor.NoWrap)
            try: self.json_text_edit.set_language("JSON")
            except Exception: logger.warning("JSON language not available in CodeEditor for SubFSM."); self.json_text_edit.set_language("Text")
            self.json_text_edit.setObjectName("SubFSMJsonEditor"); layout.addWidget(self.json_text_edit, 1)
            self.status_label = QLabel("Edit the JSON data for the sub-machine. Click OK to save changes.")
        layout.addWidget(self.status_label)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); button_box.accepted.connect(self.accept_changes); button_box.rejected.connect(self.reject); layout.addWidget(button_box)

    def accept_changes(self):
        if IMPORTS_SUCCESSFUL and hasattr(self, 'sub_scene'):
            updated_data = self.sub_scene.get_diagram_data()
            if isinstance(updated_data, dict) and all(k in updated_data for k in ['states', 'transitions', 'comments']) and isinstance(updated_data.get('states'), list) and isinstance(updated_data.get('transitions'), list) and isinstance(updated_data.get('comments'), list):
                sub_states_list = updated_data.get('states', [])
                if sub_states_list and not any(s.get('is_initial', False) for s in sub_states_list):
                    msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Warning); msg_box.setWindowTitle("No Initial Sub-State")
                    msg_box.setText("Sub-machine does not have an initial state. Recommended to define one."); save_anyway_btn = msg_box.addButton("Save Anyway", QMessageBox.AcceptRole)
                    set_first_btn = msg_box.addButton("Set First as Initial & Save", QMessageBox.YesRole); cancel_btn = msg_box.addButton(QMessageBox.Cancel); msg_box.setDefaultButton(cancel_btn); msg_box.exec_()
                    reply = msg_box.clickedButton()
                    if reply == cancel_btn: return
                    if reply == set_first_btn and sub_states_list: sub_states_list[0]['is_initial'] = True; self.log_message("INFO", f"Set state '{sub_states_list[0].get('name', 'Unnamed')}' as initial in sub-machine.")
                self.current_sub_fsm_data = updated_data; self.accept()
            else: QMessageBox.warning(self, "Invalid Sub-Machine Structure", "Unexpected sub-machine editor data structure."); logger.error("SubFSMEditorDialog: Invalid data structure from sub_scene.get_diagram_data().")
        elif hasattr(self, 'json_text_edit'):
            try:
                parsed_new_data = json.loads(self.json_text_edit.toPlainText())
                if isinstance(parsed_new_data, dict) and all(k in parsed_new_data for k in ['states', 'transitions', 'comments']):
                    sub_states_list_json = parsed_new_data.get('states', [])
                    if sub_states_list_json and not any(s.get('is_initial', False) for s in sub_states_list_json):
                        msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Warning); msg_box.setWindowTitle("No Initial Sub-State")
                        msg_box.setText("Sub-machine (JSON) does not have an initial state. Recommended."); save_anyway_btn = msg_box.addButton("Save Anyway", QMessageBox.AcceptRole)
                        set_first_btn = msg_box.addButton("Set First as Initial & Save", QMessageBox.YesRole); cancel_btn = msg_box.addButton(QMessageBox.Cancel); msg_box.setDefaultButton(cancel_btn); msg_box.exec_()
                        reply = msg_box.clickedButton()
                        if reply == cancel_btn: return
                        if reply == set_first_btn and sub_states_list_json: sub_states_list_json[0]['is_initial'] = True; self.log_message("INFO", f"Set state '{sub_states_list_json[0].get('name', 'Unnamed')}' as initial (JSON)."); self.json_text_edit.setPlainText(json.dumps(parsed_new_data, indent=2, ensure_ascii=False))
                    self.current_sub_fsm_data = parsed_new_data; self.accept()
                else: QMessageBox.warning(self, "Invalid JSON Structure", "JSON needs 'states', 'transitions', 'comments' lists.")
            except json.JSONDecodeError as e: QMessageBox.warning(self, "JSON Parse Error", f"Could not parse JSON: {e}")
        else: logger.error("SubFSMEditorDialog: Neither visual scene nor JSON editor found on accept_changes."); self.reject()

    def get_updated_sub_fsm_data(self) -> dict: return self.current_sub_fsm_data
    def log_message(self, level, message):
        print(f"SubFSMEditor Log ({level}): {message}")
        if self.parent_window_ref and hasattr(self.parent_window_ref, 'log_message') and callable(self.parent_window_ref.log_message): self.parent_window_ref.log_message(level.upper(), f"[SubEditor] {message}")


class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False, scene_ref=None):
        super().__init__(parent)
        self.setWindowTitle("State Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "Props")); self.setMinimumWidth(600)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#SafetyNote, QLabel#HardwareHintLabel {{ font-size: {APP_FONT_SIZE_SMALL}; color: {COLOR_TEXT_SECONDARY}; }} QGroupBox {{ background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102).name()}; }}")
        self.parent_window_ref = parent; self.scene_ref = scene_ref; p = current_properties or {}
        main_layout = QVBoxLayout(self); main_layout.setSpacing(12); main_layout.setContentsMargins(15,15,15,15)
        id_group = QGroupBox("Identification & Hierarchy"); id_layout = QFormLayout(id_group); id_layout.setSpacing(10)
        self.name_edit = QLineEdit(p.get('name', "StateName")); id_layout.addRow("Name:", self.name_edit)
        self.is_initial_cb = QCheckBox("Is Initial State"); self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Is Final State"); self.is_final_cb.setChecked(p.get('is_final', False))
        cb_layout = QHBoxLayout(); cb_layout.addWidget(self.is_initial_cb); cb_layout.addSpacing(20); cb_layout.addWidget(self.is_final_cb); cb_layout.addStretch(); id_layout.addRow("", cb_layout)
        self.is_superstate_cb = QCheckBox("Is Superstate (Composite State)"); self.is_superstate_cb.setChecked(p.get('is_superstate', False)); self.is_superstate_cb.toggled.connect(self._on_superstate_toggled)
        self.edit_sub_fsm_button = QPushButton(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Sub"), "Edit Sub-Machine..."); self.edit_sub_fsm_button.clicked.connect(self._on_edit_sub_fsm); self.edit_sub_fsm_button.setEnabled(self.is_superstate_cb.isChecked())
        cb_layout_super = QHBoxLayout(); cb_layout_super.addWidget(self.is_superstate_cb); cb_layout_super.addSpacing(10); cb_layout_super.addWidget(self.edit_sub_fsm_button); cb_layout_super.addStretch(); id_layout.addRow("Hierarchy:", cb_layout_super)
        raw_sub_fsm_data = p.get('sub_fsm_data', {}); self.current_sub_fsm_data = raw_sub_fsm_data if isinstance(raw_sub_fsm_data, dict) and all(k in raw_sub_fsm_data for k in ['states', 'transitions', 'comments']) and isinstance(raw_sub_fsm_data.get('states'), list) and isinstance(raw_sub_fsm_data.get('transitions'), list) and isinstance(raw_sub_fsm_data.get('comments'), list) else {'states': [], 'transitions': [], 'comments': []}
        if raw_sub_fsm_data and self.current_sub_fsm_data != raw_sub_fsm_data: logger.warning(f"State '{p.get('name', 'Unknown')}' had invalid sub_fsm_data, reset to empty.")
        main_layout.addWidget(id_group)
        appearance_group = QGroupBox("Appearance"); appearance_layout = QFormLayout(appearance_group); appearance_layout.setSpacing(10)
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton"); self.current_color = QColor(p.get('color', COLOR_ITEM_STATE_DEFAULT_BG)); self._update_color_button_style(); self.color_button.clicked.connect(self._choose_color); appearance_layout.addRow("Display Color:", self.color_button); main_layout.addWidget(appearance_group)
        actions_group = QGroupBox("State Actions"); actions_layout = QFormLayout(actions_group); actions_layout.setSpacing(10)
        self.action_language_combo = QComboBox(); self.action_language_combo.addItems(list(MECHATRONICS_SNIPPETS.keys())); self.action_language_combo.setCurrentText(p.get('action_language', DEFAULT_EXECUTION_ENV)); actions_layout.addRow("Action Language:", self.action_language_combo)
        self.entry_action_edit = CodeEditor(); self.entry_action_edit.setPlainText(p.get('entry_action', "")); self.entry_action_edit.setFixedHeight(100); self.entry_action_edit.setObjectName("ActionCodeEditor")
        self.during_action_edit = CodeEditor(); self.during_action_edit.setPlainText(p.get('during_action', "")); self.during_action_edit.setFixedHeight(100); self.during_action_edit.setObjectName("ActionCodeEditor")
        self.exit_action_edit = CodeEditor(); self.exit_action_edit.setPlainText(p.get('exit_action', "")); self.exit_action_edit.setFixedHeight(100); self.exit_action_edit.setObjectName("ActionCodeEditor")
        self.entry_action_snippet_btn = self._create_insert_snippet_button(self.entry_action_edit, "actions", " Action"); self.during_action_snippet_btn = self._create_insert_snippet_button(self.during_action_edit, "actions", " Action"); self.exit_action_snippet_btn = self._create_insert_snippet_button(self.exit_action_edit, "actions", " Action")
        self.action_language_combo.currentTextChanged.connect(self._on_action_language_changed); self._on_action_language_changed(self.action_language_combo.currentText())
        def add_field_with_note_and_hw_hint(form_layout, label_text, code_editor_widget, snippet_button):
            h_editor_btn_layout = QHBoxLayout(); h_editor_btn_layout.setSpacing(6); h_editor_btn_layout.addWidget(code_editor_widget, 1)
            v_btn_container = QVBoxLayout(); v_btn_container.setSpacing(3); v_btn_container.addWidget(snippet_button)
            hw_hint_label = QLabel("<small><i>E.g., Arduino: `digitalWrite(PIN, HIGH);`</i></small>"); hw_hint_label.setObjectName("HardwareHintLabel"); hw_hint_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-style: italic; font-size: 7.5pt;"); hw_hint_label.setToolTip("Hardware actions can be simulated or mapped to real hardware."); v_btn_container.addWidget(hw_hint_label)
            safety_note_label = QLabel("<small><i>Note: Code safety depends on target environment.</i></small>"); safety_note_label.setObjectName("SafetyNote"); safety_note_label.setToolTip("Python (Generic Simulation) code is checked for basic safety. Other environments rely on external compilers/interpreters."); v_btn_container.addWidget(safety_note_label)
            v_btn_container.addStretch(1); h_editor_btn_layout.addLayout(v_btn_container); form_layout.addRow(label_text, h_editor_btn_layout)
        add_field_with_note_and_hw_hint(actions_layout, "Entry Action:", self.entry_action_edit, self.entry_action_snippet_btn); add_field_with_note_and_hw_hint(actions_layout, "During Action:", self.during_action_edit, self.during_action_snippet_btn); add_field_with_note_and_hw_hint(actions_layout, "Exit Action:", self.exit_action_edit, self.exit_action_snippet_btn); main_layout.addWidget(actions_group)
        desc_group = QGroupBox("Description / Notes"); desc_layout = QVBoxLayout(desc_group); self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75); desc_layout.addWidget(self.description_edit); main_layout.addWidget(desc_group)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(self.accept); btns.rejected.connect(self.reject); main_layout.addWidget(btns)
        if is_new_state: self.name_edit.selectAll(); self.name_edit.setFocus()

    def _on_action_language_changed(self, language_mode: str):
        self.entry_action_edit.set_language(language_mode); self.during_action_edit.set_language(language_mode); self.exit_action_edit.set_language(language_mode)
        self._update_snippet_button_menu(self.entry_action_snippet_btn, self.entry_action_edit, language_mode, "actions"); self._update_snippet_button_menu(self.during_action_snippet_btn, self.during_action_edit, language_mode, "actions"); self._update_snippet_button_menu(self.exit_action_snippet_btn, self.exit_action_edit, language_mode, "actions")

    def _create_insert_snippet_button(self, target_widget: CodeEditor, snippet_category: str, button_text="Insert...", icon_size_px=16):
        button = QPushButton(button_text); button.setObjectName("SnippetButton"); button.setToolTip(f"Insert common {snippet_category[:-1] if snippet_category.endswith('s') else snippet_category} snippets"); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "InsSnip")); button.setIconSize(QSize(icon_size_px, icon_size_px)); button.setMenu(QMenu(self)); return button

    def _update_snippet_button_menu(self, button: QPushButton, target_widget: CodeEditor, language_mode: str, snippet_category: str):
        menu = button.menu(); menu.clear(); menu.setStyleSheet("QMenu { font-size: 9pt; } QMenu::item { padding: 5px 20px; }"); snippets_dict = MECHATRONICS_SNIPPETS.get(language_mode, {}).get(snippet_category, {})
        if not snippets_dict: action = QAction(f"(No '{snippet_category}' snippets for {language_mode})", self); action.setEnabled(False); menu.addAction(action)
        else:
            for name, snippet in snippets_dict.items(): action = QAction(name, self); action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n")); menu.addAction(action)
        button.setEnabled(bool(snippets_dict))

    def _on_superstate_toggled(self, checked):
        self.edit_sub_fsm_button.setEnabled(checked)
        if not checked and self.current_sub_fsm_data and (self.current_sub_fsm_data.get('states') or self.current_sub_fsm_data.get('transitions')):
            reply = QMessageBox.question(self, "Discard Sub-Machine?", "Unchecking 'Is Superstate' will clear its internal diagram data. Continue?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes: self.current_sub_fsm_data = {'states': [], 'transitions': [], 'comments': []}
            else: self.is_superstate_cb.blockSignals(True); self.is_superstate_cb.setChecked(True); self.is_superstate_cb.blockSignals(False); self.edit_sub_fsm_button.setEnabled(True)

    def _on_edit_sub_fsm(self):
        parent_state_name = self.name_edit.text().strip() or "Unnamed Superstate"; dialog_parent = self.parent()
        while dialog_parent and not isinstance(dialog_parent, QMainWindow) and hasattr(dialog_parent, 'parent') and callable(dialog_parent.parent):
            if dialog_parent.parent() == dialog_parent: break; dialog_parent = dialog_parent.parent()
        if not dialog_parent: dialog_parent = self
        sub_editor_dialog = SubFSMEditorDialog(self.current_sub_fsm_data, parent_state_name, dialog_parent)
        if sub_editor_dialog.exec() == QDialog.Accepted: self.current_sub_fsm_data = sub_editor_dialog.get_updated_sub_fsm_data(); QMessageBox.information(self, "Sub-Machine Updated", "Sub-machine data updated. Click OK to save changes to the state.")

    def _choose_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select State Color")
        if color.isValid():
            self.current_color = color;
            self._update_color_button_style()

    def _update_color_button_style(self): luminance = self.current_color.lightnessF(); text_color_name = COLOR_TEXT_ON_ACCENT if luminance < 0.5 else COLOR_TEXT_PRIMARY; self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color_name}; border: 1px solid {self.current_color.darker(130).name()};")

    def get_properties(self):
        sub_data_to_return = {'states': [], 'transitions': [], 'comments': []} if not self.is_superstate_cb.isChecked() else self.current_sub_fsm_data
        return {'name': self.name_edit.text().strip(), 'is_initial': self.is_initial_cb.isChecked(), 'is_final': self.is_final_cb.isChecked(), 'color': self.current_color.name(), 'action_language': self.action_language_combo.currentText(), 'entry_action': self.entry_action_edit.toPlainText().strip(), 'during_action': self.during_action_edit.toPlainText().strip(), 'exit_action': self.exit_action_edit.toPlainText().strip(), 'description': self.description_edit.toPlainText().strip(), 'is_superstate': self.is_superstate_cb.isChecked(), 'sub_fsm_data': sub_data_to_return}


class TransitionPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent); self.setWindowTitle("Transition Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogInfoView, "Props")); self.setMinimumWidth(600)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#SafetyNote, QLabel#HardwareHintLabel {{ font-size: {APP_FONT_SIZE_SMALL}; color: {COLOR_TEXT_SECONDARY}; }} QGroupBox {{ background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102).name()}; }}")
        main_layout = QVBoxLayout(self); main_layout.setSpacing(12); main_layout.setContentsMargins(15,15,15,15); p = current_properties or {}
        logic_group = QGroupBox("Identification & Logic"); logic_layout = QFormLayout(logic_group); logic_layout.setSpacing(10)
        self.event_edit = QLineEdit(p.get('event', "")); self.condition_edit = QLineEdit(p.get('condition', ""))
        self.event_snippet_btn = self._create_insert_snippet_button_lineedit(self.event_edit, "events", " Event"); self.condition_snippet_btn = self._create_insert_snippet_button_lineedit(self.condition_edit, "conditions", " Condition")
        def add_lineedit_with_snippet(form_layout, label_text, edit_widget, snippet_button, is_code_field=True):
            h_editor_btn_layout = QHBoxLayout(); h_editor_btn_layout.setSpacing(6); h_editor_btn_layout.addWidget(edit_widget, 1); v_btn_container = QVBoxLayout(); v_btn_container.addWidget(snippet_button);
            if is_code_field: v_btn_container.addStretch()
            h_editor_btn_layout.addLayout(v_btn_container); field_v_layout = QVBoxLayout(); field_v_layout.setSpacing(3); field_v_layout.addLayout(h_editor_btn_layout)
            if is_code_field: safety_note_label = QLabel("<small><i>Note: Guard conditions are Python expressions for sim.</i></small>"); safety_note_label.setObjectName("SafetyNote"); safety_note_label.setToolTip("Conditions are Python expressions in simulator. Ensure valid syntax for target language in code generation."); field_v_layout.addWidget(safety_note_label)
            form_layout.addRow(label_text, field_v_layout)
        add_lineedit_with_snippet(logic_layout, "Event Trigger:", self.event_edit, self.event_snippet_btn, is_code_field=False); add_lineedit_with_snippet(logic_layout, "Condition (Guard):", self.condition_edit, self.condition_snippet_btn, is_code_field=True); main_layout.addWidget(logic_group)
        action_group = QGroupBox("Transition Action"); action_form_layout = QFormLayout(action_group); action_form_layout.setSpacing(10)
        self.action_language_combo = QComboBox(); self.action_language_combo.addItems(list(MECHATRONICS_SNIPPETS.keys())); self.action_language_combo.setCurrentText(p.get('action_language', DEFAULT_EXECUTION_ENV)); action_form_layout.addRow("Action Language:", self.action_language_combo)
        self.action_edit = CodeEditor(); self.action_edit.setPlainText(p.get('action', "")); self.action_edit.setFixedHeight(100); self.action_edit.setObjectName("ActionCodeEditor"); self.action_snippet_btn = self._create_insert_snippet_button_codeeditor(self.action_edit, "actions", " Action")
        def add_codeeditor_with_snippet_and_hw_hint(form_layout, label_text, code_editor_widget, snippet_button):
            h_editor_btn_layout = QHBoxLayout(); h_editor_btn_layout.setSpacing(6); h_editor_btn_layout.addWidget(code_editor_widget, 1)
            v_btn_container = QVBoxLayout(); v_btn_container.setSpacing(3); v_btn_container.addWidget(snippet_button)
            hw_hint_label = QLabel("<small><i>E.g., `motor_speed = 100;` or `valve_open();`</i></small>"); hw_hint_label.setObjectName("HardwareHintLabel"); hw_hint_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-style: italic; font-size: 7.5pt;"); hw_hint_label.setToolTip("Hardware actions or control function calls."); v_btn_container.addWidget(hw_hint_label)
            safety_note_label = QLabel("<small><i>Note: Code safety depends on target. Python checked.</i></small>"); safety_note_label.setObjectName("SafetyNote"); v_btn_container.addWidget(safety_note_label); v_btn_container.addStretch(1); h_editor_btn_layout.addLayout(v_btn_container); form_layout.addRow(label_text, h_editor_btn_layout)
        add_codeeditor_with_snippet_and_hw_hint(action_form_layout, "Action:", self.action_edit, self.action_snippet_btn); main_layout.addWidget(action_group)
        self.action_language_combo.currentTextChanged.connect(self._on_action_language_changed); self._on_action_language_changed(self.action_language_combo.currentText())
        appearance_desc_group = QGroupBox("Appearance & Description"); appearance_desc_layout = QFormLayout(appearance_desc_group); appearance_desc_layout.setSpacing(10)
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton"); self.current_color = QColor(p.get('color', COLOR_ITEM_TRANSITION_DEFAULT)); self._update_color_button_style(); self.color_button.clicked.connect(self._choose_color); appearance_desc_layout.addRow("Display Color:", self.color_button)
        self.offset_perp_spin = QSpinBox(); self.offset_perp_spin.setRange(-1000, 1000); self.offset_perp_spin.setValue(int(p.get('control_offset_x', 0))); self.offset_perp_spin.setSuffix(" px"); self.offset_tang_spin = QSpinBox(); self.offset_tang_spin.setRange(-1000, 1000); self.offset_tang_spin.setValue(int(p.get('control_offset_y', 0))); self.offset_tang_spin.setSuffix(" px")
        curve_layout = QHBoxLayout(); curve_layout.addWidget(QLabel("Bend (Perp):")); curve_layout.addWidget(self.offset_perp_spin,1); curve_layout.addSpacing(15); curve_layout.addWidget(QLabel("Mid Shift (Tang):")); curve_layout.addWidget(self.offset_tang_spin,1); curve_layout.addStretch(); appearance_desc_layout.addRow("Curve Shape:", curve_layout)
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75); appearance_desc_layout.addRow("Description:", self.description_edit); main_layout.addWidget(appearance_desc_group)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); main_layout.addWidget(buttons)
        if is_new_transition: self.event_edit.setFocus()

    def _on_action_language_changed(self, language_mode: str):
        self.action_edit.set_language(language_mode); self._update_snippet_button_menu(self.event_snippet_btn, self.event_edit, language_mode, "events"); self._update_snippet_button_menu(self.condition_snippet_btn, self.condition_edit, language_mode, "conditions"); self._update_snippet_button_menu(self.action_snippet_btn, self.action_edit, language_mode, "actions")

    def _create_insert_snippet_button_lineedit(self, target_line_edit: QLineEdit, snippet_category: str, button_text="Insert..."): button = QPushButton(button_text); button.setObjectName("SnippetButton"); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"InsSnip")); button.setIconSize(QSize(16,16)); button.setToolTip(f"Insert common {snippet_category} snippets."); button.setMenu(QMenu(self)); return button
    def _create_insert_snippet_button_codeeditor(self, target_code_editor: CodeEditor, snippet_category: str, button_text="Insert..."): button = QPushButton(button_text); button.setObjectName("SnippetButton"); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"InsSnip")); button.setIconSize(QSize(16,16)); button.setToolTip(f"Insert common {snippet_category} code snippets."); button.setMenu(QMenu(self)); return button

    def _update_snippet_button_menu(self, button: QPushButton, target_widget, language_mode: str, snippet_category: str):
        menu = button.menu(); menu.clear(); menu.setStyleSheet("QMenu { font-size: 9pt; } QMenu::item { padding: 5px 20px; }"); snippets_dict = MECHATRONICS_SNIPPETS.get(language_mode, {}).get(snippet_category, {})
        if not snippets_dict: action = QAction(f"(No '{snippet_category}' snippets for {language_mode})", self); action.setEnabled(False); menu.addAction(action)
        else:
            for name, snippet in snippets_dict.items():
                action = QAction(name, self)
                if isinstance(target_widget, QLineEdit):
                    action.triggered.connect(lambda checked=False, line_edit=target_widget, s=snippet: line_edit.insert(s))
                elif isinstance(target_widget, CodeEditor):
                    action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n"))
                menu.addAction(action)
        button.setEnabled(bool(snippets_dict))

    def _choose_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select Transition Color");
        if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self): luminance = self.current_color.lightnessF(); text_color_name = COLOR_TEXT_ON_ACCENT if luminance < 0.5 else COLOR_TEXT_PRIMARY; self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color_name}; border: 1px solid {self.current_color.darker(130).name()};")

    def get_properties(self): return {'event': self.event_edit.text().strip(), 'condition': self.condition_edit.text().strip(), 'action_language': self.action_language_combo.currentText(), 'action': self.action_edit.toPlainText().strip(), 'color': self.current_color.name(), 'control_offset_x': self.offset_perp_spin.value(), 'control_offset_y': self.offset_tang_spin.value(), 'description': self.description_edit.toPlainText().strip()}


class CommentPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent); self.setWindowTitle("Comment Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cmt")); self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }}")
        p = current_properties or {}; layout = QVBoxLayout(self); layout.setSpacing(10); layout.setContentsMargins(15,15,15,15)
        self.text_edit = QTextEdit(p.get('text', "Comment")); self.text_edit.setMinimumHeight(120); self.text_edit.setPlaceholderText("Enter your comment or note here."); self.text_edit.setFontPointSize(10); layout.addWidget(QLabel("Comment Text:")); layout.addWidget(self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons); self.setMinimumWidth(400); self.text_edit.setFocus(); self.text_edit.selectAll()
    def get_properties(self): return {'text': self.text_edit.toPlainText()}


class HistoryPseudoStatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, parent_superstate_item: GraphicsStateItem = None):
        super().__init__(parent)
        self.setWindowTitle("History Pseudo-State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "PropsH"))
        self.setMinimumWidth(400)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QGroupBox {{ background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102).name()}; }}")
        p = current_properties or {}
        self.parent_superstate_item_ref = parent_superstate_item
        main_layout = QVBoxLayout(self); main_layout.setSpacing(12); main_layout.setContentsMargins(15, 15, 15, 15)
        details_group = QGroupBox("Details"); details_layout = QFormLayout(details_group); details_layout.setSpacing(10)
        history_type_str = p.get('type', 'shallow')
        self.type_label = QLabel(f"<b>{history_type_str.capitalize()} History ({'H' if history_type_str == 'shallow' else 'H*'})</b>"); details_layout.addRow("Type:", self.type_label)
        parent_name_str = p.get('parent_superstate_name', "<i>N/A - Parent not set</i>"); self.parent_name_label = QLabel(f"<i>{parent_name_str}</i>"); details_layout.addRow("Parent Superstate:", self.parent_name_label)
        self.default_target_combo = QComboBox(); self._populate_default_target_combo(p.get('default_target_substate_name')); details_layout.addRow("Default Target Sub-state:", self.default_target_combo); main_layout.addWidget(details_group)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(self.accept); btns.rejected.connect(self.reject); main_layout.addWidget(btns)
        if self.default_target_combo.count() > 0: self.default_target_combo.setFocus()
        else:
            btns.button(QDialogButtonBox.Ok).setFocus()
            if self.parent_superstate_item_ref and (not self.parent_superstate_item_ref.sub_fsm_data or not self.parent_superstate_item_ref.sub_fsm_data.get('states')):
                no_substates_label = QLabel("<small><i>Note: Parent superstate has no sub-states defined. Add sub-states to select a default target.</i></small>")
                no_substates_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-style: italic;"); main_layout.insertWidget(main_layout.count() -1, no_substates_label)

    def _populate_default_target_combo(self, current_default_target_name: str | None):
        self.default_target_combo.clear(); self.default_target_combo.addItem("", None)
        if self.parent_superstate_item_ref and self.parent_superstate_item_ref.is_superstate:
            sub_states_data = self.parent_superstate_item_ref.sub_fsm_data.get('states', [])
            if not sub_states_data: self.default_target_combo.setEnabled(False); self.default_target_combo.setToolTip("Parent superstate has no sub-states defined."); return
            self.default_target_combo.setEnabled(True); self.default_target_combo.setToolTip("Select sub-state if no history available.")
            current_index_to_set = 0
            for i, sub_state_dict in enumerate(sub_states_data):
                sub_state_name = sub_state_dict.get('name')
                if sub_state_name: self.default_target_combo.addItem(sub_state_name, sub_state_name);
                if sub_state_name == current_default_target_name: current_index_to_set = i + 1
            self.default_target_combo.setCurrentIndex(current_index_to_set)
        else: self.default_target_combo.setEnabled(False); self.default_target_combo.setToolTip("Parent superstate not available or not a superstate.")

    def get_properties(self) -> dict:
        selected_target_name = self.default_target_combo.currentData();
        return {'default_target_substate_name': selected_target_name if selected_target_name else None}


class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection: MatlabConnection, parent=None):
        super().__init__(parent); self.matlab_connection = matlab_connection; self.setWindowTitle("MATLAB Settings"); self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg")); self.setMinimumWidth(600)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }} QLabel#TestStatusLabel {{ padding: 5px; border-radius: 3px; }} QGroupBox {{ background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102).name()}; }}")
        main_layout = QVBoxLayout(self); main_layout.setSpacing(12); main_layout.setContentsMargins(12,12,12,12); path_group = QGroupBox("MATLAB Executable Path"); path_form_layout = QFormLayout(); path_form_layout.setSpacing(8)
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path); self.path_edit.setPlaceholderText("e.g., C:\\...\\MATLAB\\R202Xy\\bin\\matlab.exe"); path_form_layout.addRow("Path:", self.path_edit)
        btn_layout = QHBoxLayout(); btn_layout.setSpacing(8); auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_BrowserReload,"Det"), " Auto-detect"); auto_detect_btn.clicked.connect(self._auto_detect); auto_detect_btn.setToolTip("Attempt to find MATLAB installations.")
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), " Browse..."); browse_btn.clicked.connect(self._browse); browse_btn.setToolTip("Browse for MATLAB executable.")
        btn_layout.addWidget(auto_detect_btn); btn_layout.addWidget(browse_btn); btn_layout.addStretch(); path_v_layout = QVBoxLayout(); path_v_layout.setSpacing(10); path_v_layout.addLayout(path_form_layout); path_v_layout.addLayout(btn_layout); path_group.setLayout(path_v_layout); main_layout.addWidget(path_group)
        test_group = QGroupBox("Connection Test"); test_layout = QVBoxLayout(); test_layout.setSpacing(10); self.test_status_label = QLabel("Status: Unknown"); self.test_status_label.setObjectName("TestStatusLabel"); self.test_status_label.setWordWrap(True); self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse); self.test_status_label.setMinimumHeight(35)
        test_btn = QPushButton(get_standard_icon(QStyle.SP_CommandLink,"Test"), " Test Connection"); test_btn.clicked.connect(self._test_connection_and_update_label); test_btn.setToolTip("Test connection to the specified MATLAB path."); test_layout.addWidget(test_btn); test_layout.addWidget(self.test_status_label, 1); test_group.setLayout(test_layout); main_layout.addWidget(test_group)
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close"); dialog_buttons.accepted.connect(self._apply_settings); dialog_buttons.rejected.connect(self.reject); main_layout.addWidget(dialog_buttons)
        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        if self.matlab_connection.matlab_path and self.matlab_connection.connected: self._update_test_label_from_signal(True, f"Connected: {self.matlab_connection.matlab_path}")
        elif self.matlab_connection.matlab_path: self._update_test_label_from_signal(False, f"Path set, connection unconfirmed.")
        else: self._update_test_label_from_signal(False, "MATLAB path not set.")

    def _auto_detect(self): self.test_status_label.setText("Status: Auto-detecting MATLAB, please wait..."); self.test_status_label.setStyleSheet(f"font-style: italic; color: {COLOR_TEXT_SECONDARY}; background-color: {QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(120).name()};"); QApplication.processEvents(); self.matlab_connection.detect_matlab()
    def _browse(self):
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        start_dir = QDir.homePath(); path_obj = QDir(self.path_edit.text()); path_obj.cdUp(); start_dir = path_obj.absolutePath() if self.path_edit.text() and QDir(QDir.toNativeSeparators(self.path_edit.text())).exists() else start_dir
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path: self.path_edit.setText(path); self._update_test_label_from_signal(False, "Path changed. Test or Apply.")
    def _test_connection_and_update_label(self):
        path = self.path_edit.text().strip();
        if not path: self._update_test_label_from_signal(False, "MATLAB path is empty."); return
        self.test_status_label.setText("Status: Testing connection, please wait..."); self.test_status_label.setStyleSheet(f"font-style: italic; color: {COLOR_TEXT_SECONDARY}; background-color: {QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(120).name()};"); QApplication.processEvents()
        if self.matlab_connection.set_matlab_path(path): self.matlab_connection.test_connection()
    def _update_test_label_from_signal(self, success, message):
        status_prefix = "Status: "; current_style = "font-weight: bold; padding: 5px; border-radius: 3px;"
        if success: status_text = "Connected! " if "test successful" in message else "Path Valid. "; current_style += f"color: {COLOR_ACCENT_SUCCESS}; background-color: {QColor(COLOR_ACCENT_SUCCESS).lighter(180).name()};"; self.test_status_label.setText(status_prefix + status_text + message)
        else: status_text = "Error. "; current_style += f"color: {COLOR_ACCENT_ERROR}; background-color: {QColor(COLOR_ACCENT_ERROR).lighter(180).name()};"; self.test_status_label.setText(status_prefix + status_text + message)
        self.test_status_label.setStyleSheet(current_style)
        if success and self.matlab_connection.matlab_path and not self.path_edit.text(): self.path_edit.setText(self.matlab_connection.matlab_path)
    def _apply_settings(self):
        path = self.path_edit.text().strip()
        if self.matlab_connection.matlab_path != path: self.matlab_connection.set_matlab_path(path);
        if path and not self.matlab_connection.connected : self.matlab_connection.test_connection()
        self.accept()


class FindItemDialog(QDialog):
    item_selected_for_focus = pyqtSignal(QGraphicsItem)
    def __init__(self, parent=None, scene_ref=None):
        super().__init__(parent); self.scene_ref = scene_ref; self.setWindowTitle("Find Item"); self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "Find"))
        self.setWindowFlags((self.windowFlags() & ~Qt.WindowContextHelpButtonHint) | Qt.WindowStaysOnTopHint); self.setMinimumWidth(350); self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND_DIALOG}; }}")
        layout = QVBoxLayout(self); layout.setContentsMargins(10,10,10,10); layout.setSpacing(8); self.search_label = QLabel("Search for FSM Element (Text in Name, Event, Action, Comment, etc.):"); layout.addWidget(self.search_label)
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Start typing to search..."); self.search_input.textChanged.connect(self._update_results_list); self.search_input.returnPressed.connect(self._on_return_pressed); layout.addWidget(self.search_input)
        self.results_list = QListWidget(); self.results_list.itemActivated.connect(self._on_item_activated); layout.addWidget(self.results_list); self._populate_initial_list(); self.search_input.setFocus()
    def _get_item_display_text(self, item: QGraphicsItem) -> str:
        if isinstance(item, GraphicsStateItem): return f"State: {item.text_label}"
        elif isinstance(item, GraphicsTransitionItem): label = item._compose_label_string(); return f"Transition: {item.start_item.text_label if item.start_item else '?'} -> {item.end_item.text_label if item.end_item else '?'} ({label if label else 'No event'})"
        elif isinstance(item, GraphicsCommentItem): text = item.toPlainText().split('\n')[0]; return f"Comment: {text[:30] + '...' if len(text) > 30 else text}"
        elif isinstance(item, GraphicsHistoryPseudoStateItem): return f"History: {item.text_label} (in {item.parent_superstate_item.text_label if item.parent_superstate_item else 'None'})"
        return "Unknown Item"
    def _populate_initial_list(self):
        self.results_list.clear();
        if not self.scene_ref: return
        all_items_with_text = []
        for item in self.scene_ref.items():
            if isinstance(item, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem)): # Added H-item
                list_item = QListWidgetItem(self._get_item_display_text(item)); list_item.setData(Qt.UserRole, QVariant(item)); all_items_with_text.append(list_item)
        all_items_with_text.sort(key=lambda x: x.text()); [self.results_list.addItem(list_item_widget) for list_item_widget in all_items_with_text]
    def _update_results_list(self):
        search_term = self.search_input.text().lower(); self.results_list.clear()
        if not self.scene_ref: return
        if not search_term: self._populate_initial_list(); return
        matching_list_items = []
        for item in self.scene_ref.items():
            item_matches = False; searchable_text = ""
            if isinstance(item, GraphicsStateItem): props = item.get_data(); searchable_text = (f"{props.get('name','')} {props.get('entry_action','')} {props.get('during_action','')} {props.get('exit_action','')} {props.get('description','')}").lower()
            elif isinstance(item, GraphicsTransitionItem): props = item.get_data(); searchable_text = (f"{props.get('event','')} {props.get('condition','')} {props.get('action','')} {props.get('description','')}").lower()
            elif isinstance(item, GraphicsCommentItem): searchable_text = item.toPlainText().lower()
            elif isinstance(item, GraphicsHistoryPseudoStateItem): props = item.get_data(); searchable_text = (f"history {props.get('type','')} {props.get('parent_superstate_name','')}").lower()
            if search_term in searchable_text: item_matches = True
            if item_matches: list_item = QListWidgetItem(self._get_item_display_text(item)); list_item.setData(Qt.UserRole, QVariant(item)); matching_list_items.append(list_item)
        matching_list_items.sort(key=lambda x: x.text()); [self.results_list.addItem(list_item_widget) for list_item_widget in matching_list_items]
    def _on_item_activated(self, list_item_widget: QListWidgetItem):
        if list_item_widget:
            stored_item_variant = list_item_widget.data(Qt.UserRole)
            if stored_item_variant is not None:
                actual_item = stored_item_variant # QVariant automatically converts to original type
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
            if self.results_list.currentRow() == -1: self.results_list.setCurrentRow(0 if event.key() == Qt.Key_Down else self.results_list.count() -1)
        else: super().keyPressEvent(event)
