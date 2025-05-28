
# bsm_designer_project/dialogs.py

import sys
import json
from PyQt5.QtGui import QTextDocument # For FindFlags
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QCheckBox, QPushButton, QTextEdit,
    QSpinBox, QComboBox, QDialogButtonBox, QColorDialog, QHBoxLayout,
    QLabel, QFileDialog, QGroupBox, QMenu, QAction, QVBoxLayout, QStyle,
    QMessageBox, QInputDialog, QGraphicsView, QUndoStack, QToolBar, QActionGroup,
    QSpacerItem, QSizePolicy
)
from PyQt5.QtGui import QColor, QIcon, QPalette
from PyQt5.QtCore import Qt, QDir, QSize, QPointF

from config import (
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_ON_ACCENT, MECHATRONICS_COMMON_ACTIONS, MECHATRONICS_COMMON_EVENTS,
    MECHATRONICS_COMMON_CONDITIONS, COLOR_ACCENT_PRIMARY
)
from code_editor import CodeEditor 
from utils import get_standard_icon
from matlab_integration import MatlabConnection

try:
    from graphics_scene import DiagramScene, ZoomableView
    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    print(f"SubFSMEditorDialog: Could not import DiagramScene/ZoomableView: {e}. Visual sub-editor will be disabled.")
    DiagramScene = None
    ZoomableView = None
    IMPORTS_SUCCESSFUL = False


class SubFSMEditorDialog(QDialog): 
    def __init__(self, sub_fsm_data_initial: dict, parent_state_name: str, parent_window_ref=None):
        super().__init__(parent_window_ref)
        self.parent_window_ref = parent_window_ref
        self.setWindowTitle(f"Sub-Machine Editor: {parent_state_name}")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "SubEdit"))
        self.setMinimumSize(800, 600)

        self.current_sub_fsm_data = sub_fsm_data_initial

        layout = QVBoxLayout(self)

        if IMPORTS_SUCCESSFUL:
            self.sub_undo_stack = QUndoStack(self)
            self.sub_scene = DiagramScene(self.sub_undo_stack, parent_window=self)
            self.sub_view = ZoomableView(self.sub_scene, self)
            toolbar = QToolBar("Sub-Editor Tools")
            toolbar.setIconSize(QSize(18,18))
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
                action.setCheckable(True)
                action.triggered.connect(lambda checked=False, m=mode: self.sub_scene.set_mode(m))
                toolbar.addAction(action)
                self.sub_mode_action_group.addAction(action)
                setattr(self, f"sub_{mode}_action", action) 

            toolbar.addSeparator()
            self.sub_undo_action = self.sub_undo_stack.createUndoAction(self, "Undo")
            self.sub_undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "UnSub"))
            toolbar.addAction(self.sub_undo_action)
            self.sub_redo_action = self.sub_undo_stack.createRedoAction(self, "Redo")
            self.sub_redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "ReSub"))
            toolbar.addAction(self.sub_redo_action)

            layout.addWidget(toolbar)
            layout.addWidget(self.sub_view, 1)
            self.sub_scene.load_diagram_data(self.current_sub_fsm_data)
            self.sub_undo_stack.clear()
            self.sub_scene.set_dirty(False)
            self.sub_select_action.setChecked(True) 
            self.sub_scene.set_mode("select")
            self.status_label = QLabel("Visually edit the sub-machine. Click OK to save changes to the parent state.")
        else:
            self.json_edit_label = QLabel("Sub-Machine Data (JSON - Visual Editor Failed to Load):")
            layout.addWidget(self.json_edit_label)
            self.json_text_edit = QTextEdit()
            self.json_text_edit.setPlainText(json.dumps(self.current_sub_fsm_data, indent=2, ensure_ascii=False))
            self.json_text_edit.setAcceptRichText(False); self.json_text_edit.setLineWrapMode(QTextEdit.NoWrap)
            layout.addWidget(self.json_text_edit, 1)
            self.status_label = QLabel("Hint: A full visual editor for sub-machines would replace this JSON view.")

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
                if updated_data.get('states'):
                    has_initial = any(s.get('is_initial', False) for s in updated_data.get('states', []))
                    if not has_initial:
                        reply = QMessageBox.question(self, "No Initial Sub-State",
                                                     "The sub-machine does not have an initial state defined. "
                                                     "It's recommended to define one for predictable behavior. "
                                                     "Continue saving?",
                                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                        if reply == QMessageBox.No: return
                self.current_sub_fsm_data = updated_data; self.accept()
            else: QMessageBox.warning(self, "Invalid Sub-Machine Structure", "Unexpected sub-machine editor data structure.")
        else:
            try:
                parsed_new_data = json.loads(self.json_text_edit.toPlainText()) 
                if isinstance(parsed_new_data, dict) and all(k in parsed_new_data for k in ['states', 'transitions', 'comments']):
                    self.current_sub_fsm_data = parsed_new_data; self.accept()
                else: QMessageBox.warning(self, "Invalid JSON Structure", "JSON needs 'states', 'transitions', 'comments' lists.")
            except json.JSONDecodeError as e: QMessageBox.warning(self, "JSON Parse Error", f"Could not parse JSON: {e}")

    def get_updated_sub_fsm_data(self) -> dict: return self.current_sub_fsm_data 
    def log_message(self, level, message): 
        print(f"SubFSMEditor Log ({level}): {message}")
        if self.parent_window_ref and hasattr(self.parent_window_ref, 'log_message'):
             self.parent_window_ref.log_message(level, f"[SubEditor] {message}")


class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False, scene_ref=None):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "Props"))
        self.setMinimumWidth(480)

        self.parent_window_ref = parent
        self.scene_ref = scene_ref

        layout = QFormLayout(self)
        layout.setSpacing(10) 
        layout.setContentsMargins(12,12,12,12)

        p = current_properties or {}

        self.name_edit = QLineEdit(p.get('name', "StateName"))
        self.is_initial_cb = QCheckBox("Is Initial State"); self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Is Final State"); self.is_final_cb.setChecked(p.get('is_final', False))
        
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton")
        self.current_color = QColor(p.get('color', COLOR_ITEM_STATE_DEFAULT_BG)); self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)

        self.is_superstate_cb = QCheckBox("Is Superstate (Composite State)")
        self.is_superstate_cb.setChecked(p.get('is_superstate', False))
        self.is_superstate_cb.toggled.connect(self._on_superstate_toggled)
        self.edit_sub_fsm_button = QPushButton(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Sub"), "Edit Sub-Machine...")
        self.edit_sub_fsm_button.clicked.connect(self._on_edit_sub_fsm)
        self.edit_sub_fsm_button.setEnabled(self.is_superstate_cb.isChecked())
        raw_sub_fsm_data = p.get('sub_fsm_data', {})
        self.current_sub_fsm_data = raw_sub_fsm_data if isinstance(raw_sub_fsm_data, dict) and all(k in raw_sub_fsm_data for k in ['states', 'transitions', 'comments']) else {'states': [], 'transitions': [], 'comments': []}
        
        self.entry_action_edit = CodeEditor(); self.entry_action_edit.setPlainText(p.get('entry_action', "")); self.entry_action_edit.setFixedHeight(80); self.entry_action_edit.setObjectName("ActionCodeEditor")
        self.during_action_edit = CodeEditor(); self.during_action_edit.setPlainText(p.get('during_action', "")); self.during_action_edit.setFixedHeight(80); self.during_action_edit.setObjectName("ActionCodeEditor")
        self.exit_action_edit = CodeEditor(); self.exit_action_edit.setPlainText(p.get('exit_action', "")); self.exit_action_edit.setFixedHeight(80); self.exit_action_edit.setObjectName("ActionCodeEditor")

        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75)

        entry_action_btn = self._create_insert_snippet_button(self.entry_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        during_action_btn = self._create_insert_snippet_button(self.during_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        exit_action_btn = self._create_insert_snippet_button(self.exit_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")

        layout.addRow("Name:", self.name_edit)
        cb_layout = QHBoxLayout(); cb_layout.addWidget(self.is_initial_cb); cb_layout.addWidget(self.is_final_cb); cb_layout.addStretch()
        layout.addRow("", cb_layout)
        layout.addRow("Color:", self.color_button)
        cb_layout_super = QHBoxLayout(); cb_layout_super.addWidget(self.is_superstate_cb); cb_layout_super.addWidget(self.edit_sub_fsm_button); cb_layout_super.addStretch()
        layout.addRow("Hierarchy:", cb_layout_super)

        def add_field_with_note(form_layout, label_text, text_edit_widget, snippet_button):
            h_editor_btn_layout = QHBoxLayout()
            h_editor_btn_layout.setSpacing(5)
            h_editor_btn_layout.addWidget(text_edit_widget, 1) 
            
            v_btn_container = QVBoxLayout()
            v_btn_container.setSpacing(0)
            v_btn_container.addWidget(snippet_button)
            v_btn_container.addStretch() 
            h_editor_btn_layout.addLayout(v_btn_container)

            safety_note_label = QLabel("<small><i>Note: Python code runs in a restricted environment.</i></small>")
            safety_note_label.setToolTip(
                "Code is checked for common unsafe operations (e.g., 'import os').\n"
                "However, always review your code for correctness and unintended side effects.\n"
                "Allowed builtins include: print, len, abs, math functions, etc. No file I/O or OS calls."
            )
            safety_note_label.setStyleSheet("margin-top: 2px; color: grey;") 

            field_v_layout = QVBoxLayout()
            field_v_layout.setSpacing(2) 
            field_v_layout.addLayout(h_editor_btn_layout)
            field_v_layout.addWidget(safety_note_label)
            
            form_layout.addRow(label_text, field_v_layout)

        add_field_with_note(layout, "Entry Action:", self.entry_action_edit, entry_action_btn)
        add_field_with_note(layout, "During Action:", self.during_action_edit, during_action_btn)
        add_field_with_note(layout, "Exit Action:", self.exit_action_edit, exit_action_btn)
        
        layout.addRow("Description:", self.description_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addRow(btns)

        if is_new_state: self.name_edit.selectAll(); self.name_edit.setFocus()

    def _on_superstate_toggled(self, checked): 
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
                    self.is_superstate_cb.setChecked(True)

    def _on_edit_sub_fsm(self): 
        parent_state_name = self.name_edit.text().strip() or "Unnamed Superstate"
        dialog_parent = self if not isinstance(self.parent_window_ref, SubFSMEditorDialog) else self.parent_window_ref
        sub_editor_dialog = SubFSMEditorDialog(self.current_sub_fsm_data, parent_state_name, dialog_parent)
        if sub_editor_dialog.exec() == QDialog.Accepted:
            updated_data = sub_editor_dialog.get_updated_sub_fsm_data()
            self.current_sub_fsm_data = updated_data
            QMessageBox.information(self, "Sub-Machine Updated",
                                    "Sub-machine data has been updated in this dialog. "
                                    "Click OK to save these changes to the state.")

    def _create_insert_snippet_button(self, target_widget, snippets_dict: dict, button_text="Insert...", icon_size_px=14): # target_widget can be CodeEditor
        button = QPushButton(button_text); button.setObjectName("SnippetButton")
        button.setToolTip("Insert common snippets"); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ins"))
        button.setIconSize(QSize(icon_size_px + 2, icon_size_px + 2))
        menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n"))
            menu.addAction(action)
        button.setMenu(menu); return button

    def _choose_color(self): 
        color = QColorDialog.getColor(self.current_color, self, "Select State Color")
        if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self): 
        luminance = self.current_color.lightnessF()
        text_color = COLOR_TEXT_PRIMARY if luminance > 0.5 else COLOR_TEXT_ON_ACCENT
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color};")

    def get_properties(self): 
        sub_data_to_return = {'states': [], 'transitions': [], 'comments': []}
        if self.is_superstate_cb.isChecked():
            sub_data_to_return = self.current_sub_fsm_data
        return {
            'name': self.name_edit.text().strip(), 'is_initial': self.is_initial_cb.isChecked(),
            'is_final': self.is_final_cb.isChecked(), 'color': self.current_color.name(),
            'entry_action': self.entry_action_edit.toPlainText().strip(),
            'during_action': self.during_action_edit.toPlainText().strip(),
            'exit_action': self.exit_action_edit.toPlainText().strip(),
            'description': self.description_edit.toPlainText().strip(),
            'is_superstate': self.is_superstate_cb.isChecked(), 'sub_fsm_data': sub_data_to_return
        }


class TransitionPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogInfoView, "Props"))
        self.setMinimumWidth(520)

        layout = QFormLayout(self); layout.setSpacing(10); layout.setContentsMargins(12,12,12,12) 
        p = current_properties or {}

        self.event_edit = QLineEdit(p.get('event', ""))
        self.condition_edit = QLineEdit(p.get('condition', ""))
        self.action_edit = CodeEditor(); self.action_edit.setPlainText(p.get('action', "")); self.action_edit.setFixedHeight(80); self.action_edit.setObjectName("ActionCodeEditor")
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton")
        self.current_color = QColor(p.get('color', COLOR_ITEM_TRANSITION_DEFAULT)); self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)
        self.offset_perp_spin = QSpinBox(); self.offset_perp_spin.setRange(-1000, 1000); self.offset_perp_spin.setValue(int(p.get('control_offset_x', 0)))
        self.offset_tang_spin = QSpinBox(); self.offset_tang_spin.setRange(-1000, 1000); self.offset_tang_spin.setValue(int(p.get('control_offset_y', 0)))
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75)

        event_btn = self._create_insert_snippet_button_lineedit(self.event_edit, MECHATRONICS_COMMON_EVENTS, " Insert Event")
        condition_btn = self._create_insert_snippet_button_lineedit(self.condition_edit, MECHATRONICS_COMMON_CONDITIONS, " Insert Condition")
        action_btn = self._create_insert_snippet_button_qtextedit(self.action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        
        def add_field_with_button_and_note(form_layout, label_text, edit_widget, snippet_button, is_code_field=True):
            h_editor_btn_layout = QHBoxLayout()
            h_editor_btn_layout.setSpacing(5)
            h_editor_btn_layout.addWidget(edit_widget, 1)
            
            v_btn_container = QVBoxLayout()
            v_btn_container.setSpacing(0)
            v_btn_container.addWidget(snippet_button)
            v_btn_container.addStretch()
            h_editor_btn_layout.addLayout(v_btn_container)

            field_v_layout = QVBoxLayout()
            field_v_layout.setSpacing(2)
            field_v_layout.addLayout(h_editor_btn_layout)

            if is_code_field:
                safety_note_label = QLabel("<small><i>Note: Python code runs in a restricted environment.</i></small>")
                safety_note_label.setToolTip(
                    "Code is checked for common unsafe operations (e.g., 'import os').\n"
                    "Always review your code for correctness and unintended side effects.\n"
                    "Allowed builtins include: print, len, abs, math functions, etc. No file I/O or OS calls."
                )
                safety_note_label.setStyleSheet("margin-top: 2px; color: grey;")
                field_v_layout.addWidget(safety_note_label)
            
            form_layout.addRow(label_text, field_v_layout)

        add_field_with_button_and_note(layout, "Event Trigger:", self.event_edit, event_btn, is_code_field=False) 
        add_field_with_button_and_note(layout, "Condition (Guard):", self.condition_edit, condition_btn, is_code_field=True)
        add_field_with_button_and_note(layout, "Transition Action:", self.action_edit, action_btn, is_code_field=True)

        layout.addRow("Color:", self.color_button)
        curve_layout = QHBoxLayout()
        curve_layout.addWidget(QLabel("Bend (Perp):")); curve_layout.addWidget(self.offset_perp_spin); curve_layout.addSpacing(10)
        curve_layout.addWidget(QLabel("Mid Shift (Tang):")); curve_layout.addWidget(self.offset_tang_spin); curve_layout.addStretch()
        layout.addRow("Curve Shape:", curve_layout)
        layout.addRow("Description:", self.description_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        if is_new_transition: self.event_edit.setFocus()

    def _create_insert_snippet_button_lineedit(self, target_line_edit: QLineEdit, snippets_dict: dict, button_text="Insert..."): 
        button = QPushButton(button_text); button.setObjectName("SnippetButton")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins")); button.setIconSize(QSize(14+2,14+2))
        button.setToolTip("Insert common snippets."); menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            def insert_logic(checked=False, line_edit=target_line_edit, s=snippet):
                current_text = line_edit.text(); cursor_pos = line_edit.cursorPosition()
                new_text = current_text[:cursor_pos] + s + current_text[cursor_pos:]
                line_edit.setText(new_text); line_edit.setCursorPosition(cursor_pos + len(s))
            action.triggered.connect(insert_logic); menu.addAction(action)
        button.setMenu(menu); return button

    def _create_insert_snippet_button_qtextedit(self, target_text_edit, snippets_dict: dict, button_text="Insert..."):  # target_text_edit can be CodeEditor
        button = QPushButton(button_text); button.setObjectName("SnippetButton")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins")); button.setIconSize(QSize(14+2,14+2))
        button.setToolTip("Insert common snippets."); menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, text_edit=target_text_edit, s=snippet: text_edit.insertPlainText(s + "\n"))
            menu.addAction(action)
        button.setMenu(menu); return button

    def _choose_color(self): 
        color = QColorDialog.getColor(self.current_color, self, "Select Transition Color")
        if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self): 
        luminance = self.current_color.lightnessF()
        text_color = COLOR_TEXT_PRIMARY if luminance > 0.5 else COLOR_TEXT_ON_ACCENT
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color};")

    def get_properties(self): 
        return {
            'event': self.event_edit.text().strip(), 'condition': self.condition_edit.text().strip(),
            'action': self.action_edit.toPlainText().strip(), 'color': self.current_color.name(),
            'control_offset_x': self.offset_perp_spin.value(), 'control_offset_y': self.offset_tang_spin.value(),
            'description': self.description_edit.toPlainText().strip()
        }


class CommentPropertiesDialog(QDialog): # Unchanged
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent)
        self.setWindowTitle("Comment Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cmt"))
        p = current_properties or {}; layout = QVBoxLayout(self)
        layout.setSpacing(8); layout.setContentsMargins(12,12,12,12)
        self.text_edit = QTextEdit(p.get('text', "Comment"))
        self.text_edit.setMinimumHeight(100); self.text_edit.setPlaceholderText("Enter your comment or note here.")
        layout.addWidget(QLabel("Comment Text:")); layout.addWidget(self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setMinimumWidth(380); self.text_edit.setFocus(); self.text_edit.selectAll()

    def get_properties(self):
        return {'text': self.text_edit.toPlainText()}


class MatlabSettingsDialog(QDialog): # Unchanged
    def __init__(self, matlab_connection: MatlabConnection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings"); self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"))
        self.setMinimumWidth(580)
        main_layout = QVBoxLayout(self); main_layout.setSpacing(10); main_layout.setContentsMargins(10,10,10,10)
        path_group = QGroupBox("MATLAB Executable Path"); path_form_layout = QFormLayout()
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
        self.test_status_label = QLabel("Status: Unknown"); self.test_status_label.setWordWrap(True)
        self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse); self.test_status_label.setMinimumHeight(30)
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

    def _auto_detect(self): # Unchanged
        self.test_status_label.setText("Status: Auto-detecting MATLAB, please wait..."); self.test_status_label.setStyleSheet("")
        from PyQt5.QtWidgets import QApplication; QApplication.processEvents()
        self.matlab_connection.detect_matlab()

    def _browse(self): # Unchanged
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        start_dir = QDir.homePath()
        if self.path_edit.text() and QDir(QDir.toNativeSeparators(self.path_edit.text())).exists():
             path_obj = QDir(self.path_edit.text()); path_obj.cdUp(); start_dir = path_obj.absolutePath()
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path: self.path_edit.setText(path); self._update_test_label_from_signal(False, "Path changed. Click 'Test Connection' or 'Apply & Close'.")

    def _test_connection_and_update_label(self): # Unchanged
        path = self.path_edit.text().strip()
        if not path: self._update_test_label_from_signal(False, "MATLAB path is empty. Cannot test."); return
        self.test_status_label.setText("Status: Testing connection, please wait..."); self.test_status_label.setStyleSheet("")
        from PyQt5.QtWidgets import QApplication; QApplication.processEvents()
        if self.matlab_connection.set_matlab_path(path): self.matlab_connection.test_connection()

    def _update_test_label_from_signal(self, success, message): # Unchanged
        status_prefix = "Status: "; current_style = "font-weight: bold; padding: 3px;"
        if success:
            if "path set and appears valid" in message : status_prefix = "Status: Path seems valid. "
            elif "test successful" in message : status_prefix = "Status: Connected! "
            current_style += f"color: {COLOR_ACCENT_PRIMARY};"
        else: status_prefix = "Status: Error. "; current_style += f"color: #C62828;"
        self.test_status_label.setText(status_prefix + message); self.test_status_label.setStyleSheet(current_style)
        if success and self.matlab_connection.matlab_path and not self.path_edit.text():
            self.path_edit.setText(self.matlab_connection.matlab_path)

    def _apply_settings(self): # Unchanged
        path = self.path_edit.text().strip()
        if self.matlab_connection.matlab_path != path:
            self.matlab_connection.set_matlab_path(path)
            if path and not self.matlab_connection.connected : self.matlab_connection.test_connection()
        self.accept()


class FindReplaceDialog(QDialog):
    def __init__(self, code_editor_ref, parent=None, replace_mode=False):
        super().__init__(parent)
        self.editor = code_editor_ref # Reference to the CodeEditor instance

        self.setWindowTitle("Find/Replace in Script")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "Find"))
        self.setMinimumWidth(350)
        # Make it non-modal by default (Window modality allows interaction with parent)
        self.setWindowModality(Qt.NonModal) 

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(8)

        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Enter text to find...")
        form_layout.addRow("Find what:", self.find_edit)

        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace with (optional)...")
        form_layout.addRow("Replace with:", self.replace_edit)
        
        self.replace_label = form_layout.labelForField(self.replace_edit) # Get the label for replace_edit

        options_layout = QHBoxLayout()
        self.match_case_cb = QCheckBox("Match case")
        self.whole_word_cb = QCheckBox("Whole word") 
        options_layout.addWidget(self.match_case_cb)
        options_layout.addWidget(self.whole_word_cb)
        options_layout.addStretch()
        form_layout.addRow("Options:", options_layout)

        main_layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)
        self.find_next_btn = QPushButton("Find Next")
        self.find_prev_btn = QPushButton("Find Previous") # New button
        self.replace_btn = QPushButton("Replace")
        self.replace_all_btn = QPushButton("Replace All")
        close_btn = QPushButton("Close")

        button_layout.addStretch() # Push buttons to the right
        button_layout.addWidget(self.find_next_btn)
        button_layout.addWidget(self.find_prev_btn)
        button_layout.addSpacing(10) # Add a bit more space before replace buttons
        button_layout.addWidget(self.replace_btn)
        button_layout.addWidget(self.replace_all_btn)
        button_layout.addWidget(close_btn)
        main_layout.addLayout(button_layout)

        # Connect signals
        self.find_next_btn.clicked.connect(self.on_find_next)
        self.find_prev_btn.clicked.connect(self.on_find_previous)
        self.replace_btn.clicked.connect(self.on_replace)
        self.replace_all_btn.clicked.connect(self.on_replace_all)
        close_btn.clicked.connect(self.close)
        self.find_edit.textChanged.connect(self._update_button_states)

        self.prepare_for_mode(replace_mode)
        self._update_button_states()

    def prepare_for_mode(self, replace_mode: bool):
        self.replace_edit.setVisible(replace_mode)
        if self.replace_label: self.replace_label.setVisible(replace_mode)
        self.replace_btn.setVisible(replace_mode)
        self.replace_all_btn.setVisible(replace_mode)
        self.setWindowTitle("Replace in Script" if replace_mode else "Find in Script")

    def set_find_focus(self):
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def set_replace_focus(self):
        self.prepare_for_mode(True) # Ensure replace fields are visible
        self.replace_edit.setFocus()
        self.replace_edit.selectAll()

    def _update_button_states(self):
        has_find_text = bool(self.find_edit.text())
        self.find_next_btn.setEnabled(has_find_text)
        self.find_prev_btn.setEnabled(has_find_text)
        self.replace_btn.setEnabled(has_find_text)
        self.replace_all_btn.setEnabled(has_find_text)

    def _get_find_flags(self) -> QTextDocument.FindFlags:
        flags = QTextDocument.FindFlags() # Empty flags
        if self.match_case_cb.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        if self.whole_word_cb.isChecked():
            flags |= QTextDocument.FindWholeWords
        return flags

    def _perform_find(self, search_backward=False):
        if not self.editor: return False
        find_text = self.find_edit.text()
        if not find_text: return False

        flags = self._get_find_flags()
        if search_backward:
            flags |= QTextDocument.FindBackward

        # Use a document cursor for finding to avoid modifying the main visible cursor directly during search
        # unless a match is found.
        current_editor_cursor = self.editor.textCursor()
        doc = self.editor.document()
        search_cursor = QTextDocument(doc).find(find_text, current_editor_cursor if not search_backward else current_editor_cursor.position(), flags)
        
        found = not search_cursor.isNull()

        if not found: # Try wrap-around
            if search_backward:
                wrap_cursor = self.editor.textCursor()
                wrap_cursor.movePosition(QTextDocument.End)
                search_cursor = QTextDocument(doc).find(find_text, wrap_cursor, flags)
            else:
                wrap_cursor = self.editor.textCursor()
                wrap_cursor.movePosition(QTextDocument.Start)
                search_cursor = QTextDocument(doc).find(find_text, wrap_cursor, flags)
            
            found = not search_cursor.isNull()
            if not found:
                 QMessageBox.information(self, "Find", f"Cannot find '{find_text}'.")
                 return False # Return False if not found even after wrap
        
        if found:
            self.editor.setTextCursor(search_cursor) # Select the found text
        return found # Return whether text was found

    def on_find_next(self):
        self._perform_find(search_backward=False)
    
    def on_find_previous(self):
        self._perform_find(search_backward=True)

    def on_replace(self):
        if not self.editor: return
        find_text = self.find_edit.text()
        replace_text = self.replace_edit.text()
        if not find_text: return

        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        
        text_to_compare_selection = selected_text
        text_to_compare_find = find_text
        if not self.match_case_cb.isChecked():
            text_to_compare_selection = selected_text.lower()
            text_to_compare_find = find_text.lower()

        if cursor.hasSelection() and text_to_compare_selection == text_to_compare_find :
            cursor.insertText(replace_text)
        # After replacing (or if no selection matched), find the next occurrence
        self._perform_find(search_backward=False)

    def on_replace_all(self):
        if not self.editor: return
        find_text = self.find_edit.text()
        replace_text = self.replace_edit.text()
        if not find_text: return

        flags = self._get_find_flags()
        count = 0
        
        original_cursor_pos = self.editor.textCursor().position() # Store original position
        
        doc = self.editor.document()
        current_cursor = QTextDocument(doc).find(find_text, 0, flags) # Start search from beginning

        self.editor.textCursor().beginEditBlock() 
        
        while not current_cursor.isNull():
            self.editor.setTextCursor(current_cursor) # Select the found text
            self.editor.textCursor().insertText(replace_text)
            count += 1
            # Start next search from the end of the last replacement
            current_cursor = QTextDocument(doc).find(find_text, self.editor.textCursor().position(), flags)

        self.editor.textCursor().endEditBlock()
        
        # Restore cursor to original position or a sensible place
        cursor_to_restore = self.editor.textCursor()
        if count == 0 : # if nothing was replaced, restore to original position
            cursor_to_restore.setPosition(original_cursor_pos)
        # else: cursor will be at the end of the last replacement which is fine.
        self.editor.setTextCursor(cursor_to_restore)
        
        QMessageBox.information(self, "Replace All", f"Replaced {count} occurrence(s) of '{find_text}'.")

    def closeEvent(self, event):
        if self.parent() and hasattr(self.parent(), '_find_replace_dialog_instance'):
             if self.parent()._find_replace_dialog_instance == self:
                 self.parent()._find_replace_dialog_instance = None
        super().closeEvent(event)
