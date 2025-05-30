# bsm_designer_project/dialogs.py

import sys
import json
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QCheckBox, QPushButton, QTextEdit,
    QSpinBox, QComboBox, QDialogButtonBox, QColorDialog, QHBoxLayout,
    QLabel, QFileDialog, QGroupBox, QMenu, QAction, QVBoxLayout, QStyle,
    QMessageBox, QInputDialog, QGraphicsView, QUndoStack, QToolBar, QActionGroup
)
from PyQt5.QtGui import QColor, QIcon, QPalette
from PyQt5.QtCore import Qt, QDir, QSize, QPointF

from config import (
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_ON_ACCENT, MECHATRONICS_SNIPPETS, COLOR_ACCENT_PRIMARY,
    DEFAULT_EXECUTION_ENV, EXECUTION_ENV_PYTHON_GENERIC, EXECUTION_ENV_ARDUINO_CPP,
    EXECUTION_ENV_C_GENERIC, EXECUTION_ENV_RASPBERRYPI_PYTHON, EXECUTION_ENV_MICROPYTHON
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


class SubFSMEditorDialog(QDialog): # Unchanged from previous correct version
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
            self.sub_scene = DiagramScene(self.sub_undo_stack, parent_window=self) # Pass self as parent_window for sub-scene
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
                setattr(self, f"sub_{mode}_action", action) # Store for easy access

            toolbar.addSeparator()
            self.sub_undo_action = self.sub_undo_stack.createUndoAction(self, "Undo")
            self.sub_undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "UnSub"))
            toolbar.addAction(self.sub_undo_action)
            self.sub_redo_action = self.sub_undo_stack.createRedoAction(self, "Redo")
            self.sub_redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "ReSub"))
            toolbar.addAction(self.sub_redo_action)

            layout.addWidget(toolbar)
            layout.addWidget(self.sub_view, 1)
            if isinstance(self.current_sub_fsm_data, dict) and \
               all(k in self.current_sub_fsm_data for k in ['states', 'transitions', 'comments']):
                self.sub_scene.load_diagram_data(self.current_sub_fsm_data)
            else: # Initialize with empty if data is malformed
                 self.sub_scene.load_diagram_data({'states': [], 'transitions': [], 'comments': []})
                 
            self.sub_undo_stack.clear()
            self.sub_scene.set_dirty(False) # Sub-editor starts clean
            if hasattr(self, "sub_select_action"): self.sub_select_action.setChecked(True)
            self.sub_scene.set_mode("select")
            self.status_label = QLabel("Visually edit the sub-machine. Click OK to save changes to the parent state.")
        else:
            self.json_edit_label = QLabel("Sub-Machine Data (JSON - Visual Editor Failed to Load):")
            layout.addWidget(self.json_edit_label)
            self.json_text_edit = QTextEdit()
            # Ensure current_sub_fsm_data is valid before dumping
            if isinstance(self.current_sub_fsm_data, dict) and \
               all(k in self.current_sub_fsm_data for k in ['states', 'transitions', 'comments']):
                self.json_text_edit.setPlainText(json.dumps(self.current_sub_fsm_data, indent=2, ensure_ascii=False))
            else:
                self.json_text_edit.setPlainText(json.dumps({'states': [], 'transitions': [], 'comments': [], 'error': 'Initial data malformed'}, indent=2))

            self.json_text_edit.setAcceptRichText(False); self.json_text_edit.setLineWrapMode(QTextEdit.NoWrap)
            layout.addWidget(self.json_text_edit, 1)
            self.status_label = QLabel("Hint: A full visual editor for sub-machines would replace this JSON view.")

        layout.addWidget(self.status_label)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_changes); button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept_changes(self): # Unchanged from previous version
        if IMPORTS_SUCCESSFUL and hasattr(self, 'sub_scene'):
            updated_data = self.sub_scene.get_diagram_data()
            # Perform basic validation on the structure of updated_data
            if isinstance(updated_data, dict) and \
               all(k in updated_data for k in ['states', 'transitions', 'comments']) and \
               isinstance(updated_data.get('states'), list) and \
               isinstance(updated_data.get('transitions'), list) and \
               isinstance(updated_data.get('comments'), list):

                # Check for initial state in the sub-machine if it's not empty
                if updated_data.get('states'): # Only check if there are states
                    has_initial = any(s.get('is_initial', False) for s in updated_data.get('states', []))
                    if not has_initial:
                        reply = QMessageBox.question(self, "No Initial Sub-State",
                                                     "The sub-machine does not have an initial state defined. "
                                                     "It's recommended to define one for predictable behavior. "
                                                     "Continue saving?",
                                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                        if reply == QMessageBox.No:
                            return # User chose not to save
                
                self.current_sub_fsm_data = updated_data
                self.accept() # Close dialog with QDialog.Accepted
            else:
                QMessageBox.warning(self, "Invalid Sub-Machine Structure",
                                    "The sub-machine editor returned data with an unexpected structure. Cannot save.")
        else: # Using JSON text edit fallback
            try:
                parsed_new_data = json.loads(self.json_text_edit.toPlainText()) # type: ignore
                if isinstance(parsed_new_data, dict) and all(k in parsed_new_data for k in ['states', 'transitions', 'comments']):
                    self.current_sub_fsm_data = parsed_new_data
                    self.accept()
                else:
                    QMessageBox.warning(self, "Invalid JSON Structure",
                                        "The provided JSON must be an object with 'states', 'transitions', and 'comments' lists at the top level.")
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "JSON Parse Error", f"Could not parse the JSON data: {e}")

    def get_updated_sub_fsm_data(self) -> dict: return self.current_sub_fsm_data # Unchanged
    def log_message(self, level, message): # Unchanged
        print(f"SubFSMEditor Log ({level}): {message}")
        if self.parent_window_ref and hasattr(self.parent_window_ref, 'log_message'):
             self.parent_window_ref.log_message(level, f"[SubEditor] {message}")


class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False, scene_ref=None):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "Props"))
        self.setMinimumWidth(520) # Increased width for language combo

        self.parent_window_ref = parent
        self.scene_ref = scene_ref # Reference to DiagramScene for name checking

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
        # Ensure sub_fsm_data is always a valid structure
        raw_sub_fsm_data = p.get('sub_fsm_data', {})
        if isinstance(raw_sub_fsm_data, dict) and \
           all(k in raw_sub_fsm_data for k in ['states', 'transitions', 'comments']):
            self.current_sub_fsm_data = raw_sub_fsm_data
        else:
            self.current_sub_fsm_data = {'states': [], 'transitions': [], 'comments': []} # Default empty structure
        
        self.action_language_combo = QComboBox()
        self.action_language_combo.addItems(list(MECHATRONICS_SNIPPETS.keys()))
        self.action_language_combo.setCurrentText(p.get('action_language', DEFAULT_EXECUTION_ENV))
        
        self.entry_action_edit = CodeEditor(); self.entry_action_edit.setPlainText(p.get('entry_action', "")); self.entry_action_edit.setFixedHeight(100); self.entry_action_edit.setObjectName("ActionCodeEditor")
        self.during_action_edit = CodeEditor(); self.during_action_edit.setPlainText(p.get('during_action', "")); self.during_action_edit.setFixedHeight(100); self.during_action_edit.setObjectName("ActionCodeEditor")
        self.exit_action_edit = CodeEditor(); self.exit_action_edit.setPlainText(p.get('exit_action', "")); self.exit_action_edit.setFixedHeight(100); self.exit_action_edit.setObjectName("ActionCodeEditor")
        
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75)

        self.entry_action_snippet_btn = self._create_insert_snippet_button(self.entry_action_edit, "actions", " Insert Action")
        self.during_action_snippet_btn = self._create_insert_snippet_button(self.during_action_edit, "actions", " Insert Action")
        self.exit_action_snippet_btn = self._create_insert_snippet_button(self.exit_action_edit, "actions", " Insert Action")
        
        self.action_language_combo.currentTextChanged.connect(self._on_action_language_changed)
        self._on_action_language_changed(self.action_language_combo.currentText()) # Initialize editors and snippets

        layout.addRow("Name:", self.name_edit)
        cb_layout = QHBoxLayout(); cb_layout.addWidget(self.is_initial_cb); cb_layout.addWidget(self.is_final_cb); cb_layout.addStretch()
        layout.addRow("", cb_layout)
        layout.addRow("Color:", self.color_button)
        cb_layout_super = QHBoxLayout(); cb_layout_super.addWidget(self.is_superstate_cb); cb_layout_super.addWidget(self.edit_sub_fsm_button); cb_layout_super.addStretch()
        layout.addRow("Hierarchy:", cb_layout_super)
        layout.addRow("Action Language:", self.action_language_combo)

        def add_field_with_note(form_layout, label_text, code_editor_widget, snippet_button):
            h_editor_btn_layout = QHBoxLayout()
            h_editor_btn_layout.setSpacing(5)
            h_editor_btn_layout.addWidget(code_editor_widget, 1) 
            
            v_btn_container = QVBoxLayout()
            v_btn_container.setSpacing(0)
            v_btn_container.addWidget(snippet_button)
            v_btn_container.addStretch() 
            h_editor_btn_layout.addLayout(v_btn_container)

            safety_note_label = QLabel("<small><i>Note: Code execution safety depends on the target environment.</i></small>")
            safety_note_label.setToolTip(
                "For 'Python (Generic Simulation)', code is checked for common unsafe operations.\n"
                "For other environments (Arduino, C, etc.), this editor provides text input; \n"
                "safety and correctness are the responsibility of the external compiler/interpreter."
            )
            safety_note_label.setStyleSheet("margin-top: 2px; color: grey;") 

            field_v_layout = QVBoxLayout()
            field_v_layout.setSpacing(2) 
            field_v_layout.addLayout(h_editor_btn_layout)
            field_v_layout.addWidget(safety_note_label)
            
            form_layout.addRow(label_text, field_v_layout)

        add_field_with_note(layout, "Entry Action:", self.entry_action_edit, self.entry_action_snippet_btn)
        add_field_with_note(layout, "During Action:", self.during_action_edit, self.during_action_snippet_btn)
        add_field_with_note(layout, "Exit Action:", self.exit_action_edit, self.exit_action_snippet_btn)
        
        layout.addRow("Description:", self.description_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addRow(btns)

        if is_new_state: self.name_edit.selectAll(); self.name_edit.setFocus()

    def _on_action_language_changed(self, language_mode: str):
        # Set language for each CodeEditor instance
        self.entry_action_edit.set_language(language_mode)
        self.during_action_edit.set_language(language_mode)
        self.exit_action_edit.set_language(language_mode)
        
        # Update snippet menus for the new language
        self._update_snippet_button_menu(self.entry_action_snippet_btn, self.entry_action_edit, language_mode, "actions")
        self._update_snippet_button_menu(self.during_action_snippet_btn, self.during_action_edit, language_mode, "actions")
        self._update_snippet_button_menu(self.exit_action_snippet_btn, self.exit_action_edit, language_mode, "actions")

    def _create_insert_snippet_button(self, target_widget: CodeEditor, snippet_category: str, button_text="Insert...", icon_size_px=14):
        button = QPushButton(button_text); button.setObjectName("SnippetButton") # Standard name for styling
        button.setToolTip("Insert common snippets for the current language."); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ins"))
        button.setIconSize(QSize(icon_size_px + 2, icon_size_px + 2)) # Slightly larger icon
        button.setMenu(QMenu(self)) # Menu will be populated by _update_snippet_button_menu
        return button

    def _update_snippet_button_menu(self, button: QPushButton, target_widget: CodeEditor, language_mode: str, snippet_category: str):
        menu = button.menu()
        if not menu: # Should not happen if _create_insert_snippet_button was called
            menu = QMenu(self)
            button.setMenu(menu)
        menu.clear()
        
        snippets_dict = MECHATRONICS_SNIPPETS.get(language_mode, {}).get(snippet_category, {})
        
        if not snippets_dict:
            action = QAction(f"(No '{snippet_category}' snippets for {language_mode})", self)
            action.setEnabled(False)
            menu.addAction(action)
        else:
            for name, snippet in snippets_dict.items():
                action = QAction(name, self)
                # Use a lambda that correctly captures loop variables
                action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n"))
                menu.addAction(action)
        button.setEnabled(bool(snippets_dict))


    def _on_superstate_toggled(self, checked): 
        self.edit_sub_fsm_button.setEnabled(checked)
        if not checked: # If unchecking superstate
            # Check if there's actual data in the sub-machine
            if self.current_sub_fsm_data and \
               (self.current_sub_fsm_data.get('states') or self.current_sub_fsm_data.get('transitions') or self.current_sub_fsm_data.get('comments')):
                reply = QMessageBox.question(self, "Discard Sub-Machine Data?",
                                             "Unchecking 'Is Superstate' will clear its internal diagram data. This cannot be undone here. Continue?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    # Clear the sub-FSM data
                    self.current_sub_fsm_data = {'states': [], 'transitions': [], 'comments': []}
                else:
                    # User cancelled, re-check the checkbox
                    self.is_superstate_cb.setChecked(True) # Prevent unchecking

    def _on_edit_sub_fsm(self): 
        parent_state_name = self.name_edit.text().strip() or "Unnamed Superstate"
        # Determine the correct parent for the SubFSMEditorDialog to avoid recursive parenting issues
        # If self.parent_window_ref is already a SubFSMEditorDialog, it means we are editing a sub-sub-FSM.
        # In such cases, the sub-editor should be parented to that existing sub-editor.
        # Otherwise, parent it to the main window or the current dialog if no main window ref.
        dialog_parent_widget = self.parent() # Default to current dialog's parent
        if self.parent_window_ref:
            if not isinstance(self.parent_window_ref, SubFSMEditorDialog): # Parent is main window
                dialog_parent_widget = self.parent_window_ref
            else: # Parent is another sub-editor
                 dialog_parent_widget = self.parent_window_ref
        
        sub_editor_dialog = SubFSMEditorDialog(self.current_sub_fsm_data, parent_state_name, dialog_parent_widget)
        if sub_editor_dialog.exec() == QDialog.Accepted:
            updated_data = sub_editor_dialog.get_updated_sub_fsm_data()
            self.current_sub_fsm_data = updated_data # Store the updated data
            QMessageBox.information(self, "Sub-Machine Updated",
                                    "Sub-machine data has been updated in this dialog. "
                                    "Click OK to save these changes to the state.")

    def _choose_color(self): 
        color = QColorDialog.getColor(self.current_color, self, "Select State Color")
        if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self): 
        luminance = self.current_color.lightnessF()
        text_color = COLOR_TEXT_PRIMARY if luminance > 0.5 else COLOR_TEXT_ON_ACCENT
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color};")

    def get_properties(self): 
        # Ensure sub_fsm_data is correctly structured, especially if superstate is unchecked
        sub_data_to_return = {'states': [], 'transitions': [], 'comments': []}
        if self.is_superstate_cb.isChecked():
            # Only return potentially populated sub_fsm_data if it's a superstate
             sub_data_to_return = self.current_sub_fsm_data 
        
        return {
            'name': self.name_edit.text().strip(), 'is_initial': self.is_initial_cb.isChecked(),
            'is_final': self.is_final_cb.isChecked(), 'color': self.current_color.name(),
            'action_language': self.action_language_combo.currentText(),
            'entry_action': self.entry_action_edit.toPlainText().strip(),
            'during_action': self.during_action_edit.toPlainText().strip(),
            'exit_action': self.exit_action_edit.toPlainText().strip(),
            'description': self.description_edit.toPlainText().strip(),
            'is_superstate': self.is_superstate_cb.isChecked(), 
            'sub_fsm_data': sub_data_to_return
        }


class TransitionPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogInfoView, "Props"))
        self.setMinimumWidth(560) # Increased width

        layout = QFormLayout(self); layout.setSpacing(10); layout.setContentsMargins(12,12,12,12) 
        p = current_properties or {}

        self.event_edit = QLineEdit(p.get('event', ""))
        self.condition_edit = QLineEdit(p.get('condition', ""))
        
        self.action_language_combo = QComboBox()
        self.action_language_combo.addItems(list(MECHATRONICS_SNIPPETS.keys()))
        self.action_language_combo.setCurrentText(p.get('action_language', DEFAULT_EXECUTION_ENV))

        self.action_edit = CodeEditor(); self.action_edit.setPlainText(p.get('action', "")); self.action_edit.setFixedHeight(100); self.action_edit.setObjectName("ActionCodeEditor")
        
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton")
        self.current_color = QColor(p.get('color', COLOR_ITEM_TRANSITION_DEFAULT)); self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)
        self.offset_perp_spin = QSpinBox(); self.offset_perp_spin.setRange(-1000, 1000); self.offset_perp_spin.setValue(int(p.get('control_offset_x', 0)))
        self.offset_tang_spin = QSpinBox(); self.offset_tang_spin.setRange(-1000, 1000); self.offset_tang_spin.setValue(int(p.get('control_offset_y', 0)))
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75)

        self.event_snippet_btn = self._create_insert_snippet_button_lineedit(self.event_edit, "events", " Insert Event")
        self.condition_snippet_btn = self._create_insert_snippet_button_lineedit(self.condition_edit, "conditions", " Insert Condition")
        self.action_snippet_btn = self._create_insert_snippet_button_codeeditor(self.action_edit, "actions", " Insert Action")

        self.action_language_combo.currentTextChanged.connect(self._on_action_language_changed)
        self._on_action_language_changed(self.action_language_combo.currentText()) # Initialize

        def add_field_with_button_and_note(form_layout, label_text, edit_widget, snippet_button, is_code_field=True, is_line_edit=False):
            h_editor_btn_layout = QHBoxLayout()
            h_editor_btn_layout.setSpacing(5)
            h_editor_btn_layout.addWidget(edit_widget, 1)
            
            v_btn_container = QVBoxLayout()
            v_btn_container.setSpacing(0)
            v_btn_container.addWidget(snippet_button)
            if not is_line_edit : v_btn_container.addStretch() # Stretch only for multi-line editors
            h_editor_btn_layout.addLayout(v_btn_container)

            field_v_layout = QVBoxLayout()
            field_v_layout.setSpacing(2)
            field_v_layout.addLayout(h_editor_btn_layout)

            if is_code_field:
                safety_note_label = QLabel("<small><i>Note: Code execution safety depends on the target environment.</i></small>")
                safety_note_label.setToolTip(
                    "For 'Python (Generic Simulation)', code is checked for common unsafe operations.\n"
                    "For other environments (Arduino, C, etc.), this editor provides text input; \n"
                    "safety and correctness are the responsibility of the external compiler/interpreter."
                )
                safety_note_label.setStyleSheet("margin-top: 2px; color: grey;")
                field_v_layout.addWidget(safety_note_label)
            
            form_layout.addRow(label_text, field_v_layout)

        add_field_with_button_and_note(layout, "Event Trigger:", self.event_edit, self.event_snippet_btn, is_code_field=False, is_line_edit=True) 
        add_field_with_button_and_note(layout, "Condition (Guard):", self.condition_edit, self.condition_snippet_btn, is_code_field=True, is_line_edit=True)
        layout.addRow("Action Language:", self.action_language_combo)
        add_field_with_button_and_note(layout, "Transition Action:", self.action_edit, self.action_snippet_btn, is_code_field=True)

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

    def _on_action_language_changed(self, language_mode: str):
        self.action_edit.set_language(language_mode)
        # Update snippet menus for all relevant fields
        self._update_snippet_button_menu(self.event_snippet_btn, self.event_edit, language_mode, "events")
        self._update_snippet_button_menu(self.condition_snippet_btn, self.condition_edit, language_mode, "conditions")
        self._update_snippet_button_menu(self.action_snippet_btn, self.action_edit, language_mode, "actions")

    def _create_insert_snippet_button_lineedit(self, target_line_edit: QLineEdit, snippet_category: str, button_text="Insert..."): 
        button = QPushButton(button_text); button.setObjectName("SnippetButton")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins")); button.setIconSize(QSize(14+2,14+2))
        button.setToolTip("Insert common snippets for the current language."); button.setMenu(QMenu(self))
        return button

    def _create_insert_snippet_button_codeeditor(self, target_code_editor: CodeEditor, snippet_category: str, button_text="Insert..."): 
        button = QPushButton(button_text); button.setObjectName("SnippetButton")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins")); button.setIconSize(QSize(14+2,14+2))
        button.setToolTip("Insert common snippets for the current language."); button.setMenu(QMenu(self))
        return button

    def _update_snippet_button_menu(self, button: QPushButton, target_widget, language_mode: str, snippet_category: str):
        menu = button.menu()
        if not menu: # Should not happen if _create_insert_snippet_button was called
            menu = QMenu(self)
            button.setMenu(menu)
        menu.clear()
        
        snippets_dict = MECHATRONICS_SNIPPETS.get(language_mode, {}).get(snippet_category, {})
        
        if not snippets_dict:
            action = QAction(f"(No '{snippet_category}' snippets for {language_mode})", self)
            action.setEnabled(False)
            menu.addAction(action)
        else:
            for name, snippet in snippets_dict.items():
                action = QAction(name, self)
                if isinstance(target_widget, QLineEdit):
                    # Lambda to insert text at cursor for QLineEdit
                    action.triggered.connect(
                        lambda checked=False, line_edit=target_widget, s=snippet: 
                        line_edit.insert(s) # QLineEdit.insert() inserts at cursor
                    )
                elif isinstance(target_widget, CodeEditor): # Or QPlainTextEdit
                     # Lambda to insert text and newline for CodeEditor
                    action.triggered.connect(
                        lambda checked=False, text_edit=target_widget, s=snippet: 
                        text_edit.insertPlainText(s + "\n")
                    )
                menu.addAction(action)
        button.setEnabled(bool(snippets_dict))

    def _choose_color(self): 
        color = QColorDialog.getColor(self.current_color, self, "Select Transition Color")
        if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self): 
        luminance = self.current_color.lightnessF()
        text_color = COLOR_TEXT_PRIMARY if luminance > 0.5 else COLOR_TEXT_ON_ACCENT
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color};")

    def get_properties(self): 
        return {
            'event': self.event_edit.text().strip(), 
            'condition': self.condition_edit.text().strip(),
            'action_language': self.action_language_combo.currentText(),
            'action': self.action_edit.toPlainText().strip(), 
            'color': self.current_color.name(),
            'control_offset_x': self.offset_perp_spin.value(), 
            'control_offset_y': self.offset_tang_spin.value(),
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