# bsm_designer_project/dialogs.py

import sys
import json
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QCheckBox, QPushButton, QTextEdit,
    QSpinBox, QComboBox, QDialogButtonBox, QColorDialog, QHBoxLayout,
    QLabel, QFileDialog, QGroupBox, QMenu, QAction, QVBoxLayout, QStyle,
    QMessageBox, QInputDialog, QToolBar, QActionGroup # Added QToolBar, QActionGroup
)
from PyQt5.QtGui import QColor, QIcon, QPalette, QKeySequence # Added QKeySequence
from PyQt5.QtCore import Qt, QDir, QSize, pyqtSignal

# Import QUndoStack
from PyQt5.QtWidgets import QUndoStack

# These will be imported from main.py after it's adjusted to allow this
# This relies on main.py being importable by dialogs.py
# and main.py importing dialogs.py carefully (e.g., function-local imports for dialogs it uses)
from bsm_designer_project.main import DiagramScene, ZoomableView


from config import (
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_ON_ACCENT, MECHATRONICS_COMMON_ACTIONS, MECHATRONICS_COMMON_EVENTS,
    MECHATRONICS_COMMON_CONDITIONS
)
from utils import get_standard_icon
from matlab_integration import MatlabConnection

# No logging setup here, dialogs will rely on the main app's logger if they need to log
# or pass messages back to the caller to log.

class SubFSMEditorDialog(QDialog):
    def __init__(self, sub_fsm_data_initial: dict, parent_state_name: str, parent_main_window_context, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Sub-Machine Editor: {parent_state_name}")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "SubEdit"))
        self.setMinimumSize(800, 600)

        self.current_sub_fsm_data = sub_fsm_data_initial
        self.parent_main_window_context = parent_main_window_context

        # Undo stack for the sub-diagram
        self.undo_stack = QUndoStack(self)

        # DiagramScene's parent_window will be this SubFSMEditorDialog instance
        self.scene = DiagramScene(self.undo_stack, parent_window=self)
        self.scene.load_diagram_data(self.current_sub_fsm_data if self.current_sub_fsm_data else {'states':[], 'transitions':[], 'comments':[]})
        self.scene.set_dirty(False) # Sub-diagram starts clean from passed data
        self.undo_stack.clear()

        self.view = ZoomableView(self.scene, self)

        # Layout
        layout = QVBoxLayout(self)

        # Toolbar for sub-editor
        self.toolbar = QToolBar("Sub-Machine Tools")
        self.toolbar.setIconSize(QSize(18,18))
        layout.addWidget(self.toolbar)
        self._create_sub_editor_actions()
        self._add_actions_to_sub_editor_toolbar()

        layout.addWidget(self.view, 1) # View takes most space

        self.status_label = QLabel("Visually edit the sub-machine. Click 'Save Sub-Machine' to apply changes to the parent state.")
        layout.addWidget(self.status_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("Save Sub-Machine")
        button_box.accepted.connect(self.accept_changes)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        if hasattr(self, 'select_mode_action_sub'):
            self.select_mode_action_sub.trigger()
        
        # Connect scene's modified status to dialog's windowModified property
        self.scene.modifiedStatusChanged.connect(self.setWindowModified)


    # --- Shim methods that DiagramScene might call on its parent_window ---
    def _update_save_actions_enable_state(self):
        # This dialog's "Save" is the OK button. Its dirty state is managed by QDialog/scene.
        # The main window's save actions are not relevant here.
        pass

    def get_view(self): # If DiagramScene tries to access parent_window.view (it shouldn't ideally)
        return self.view

    # This method might be called by DiagramScene.set_mode() via self.parent_window.view._restore_cursor_to_scene_mode()
    # Or if the view itself needs to restore cursor based on scene mode.
    def _restore_cursor_to_scene_mode(self): # Renamed for clarity, matches main window's potential call target
        if self.view and hasattr(self.view, '_restore_cursor_to_scene_mode'):
            self.view._restore_cursor_to_scene_mode()

    # --- End Shim methods ---

    def _create_sub_editor_actions(self):
        self.mode_action_group_sub = QActionGroup(self)
        self.mode_action_group_sub.setExclusive(True)

        self.select_mode_action_sub = QAction(get_standard_icon(QStyle.SP_ArrowRight, "Sel"), "Select/Move", self, checkable=True,
                                       triggered=lambda: self.scene.set_mode("select"))
        self.add_state_mode_action_sub = QAction(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"), "Add State", self, checkable=True,
                                          triggered=lambda: self.scene.set_mode("state"))
        self.add_transition_mode_action_sub = QAction(get_standard_icon(QStyle.SP_ArrowForward, "Tr"), "Add Transition", self, checkable=True,
                                               triggered=lambda: self.scene.set_mode("transition"))
        self.add_comment_mode_action_sub = QAction(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"), "Add Comment", self, checkable=True,
                                            triggered=lambda: self.scene.set_mode("comment"))
        
        for action in [self.select_mode_action_sub, self.add_state_mode_action_sub, self.add_transition_mode_action_sub, self.add_comment_mode_action_sub]:
            self.mode_action_group_sub.addAction(action)
            # Connect action changes to update cursor, as MainWindow normally does for its view
            action.triggered.connect(self._restore_cursor_to_scene_mode)


        self.delete_action_sub = QAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete", self,
                                         shortcut=QKeySequence.Delete,
                                         triggered=lambda: self.scene.delete_selected_items())

        self.undo_action_sub = self.undo_stack.createUndoAction(self, "&Undo")
        self.undo_action_sub.setShortcut(QKeySequence.Undo)
        self.undo_action_sub.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "Un"))

        self.redo_action_sub = self.undo_stack.createRedoAction(self, "&Redo")
        self.redo_action_sub.setShortcut(QKeySequence.Redo)
        self.redo_action_sub.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "Re"))

    def _add_actions_to_sub_editor_toolbar(self):
        self.toolbar.addAction(self.select_mode_action_sub)
        self.toolbar.addAction(self.add_state_mode_action_sub)
        self.toolbar.addAction(self.add_transition_mode_action_sub)
        self.toolbar.addAction(self.add_comment_mode_action_sub)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.delete_action_sub)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.undo_action_sub)
        self.toolbar.addAction(self.redo_action_sub)

    def accept_changes(self):
        self.current_sub_fsm_data = self.scene.get_diagram_data()
        self.accept()

    def get_updated_sub_fsm_data(self) -> dict:
        return self.current_sub_fsm_data

    def keyPressEvent(self, event):
        # Pass key events to the scene first
        self.scene.keyPressEvent(event)
        if not event.isAccepted(): # If scene didn't handle it (e.g. Esc for dialog close)
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # Use windowModified state which is connected to scene's dirty state
        if self.isWindowModified(): # Checks if scene.set_dirty(True) was called
            reply = QMessageBox.question(self, "Unsaved Changes in Sub-Machine",
                                         "There are unsaved changes in this sub-machine. Do you want to discard them?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore()
                return
        event.accept()


class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False, scene_ref=None):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "Props"))
        self.setMinimumWidth(480)

        self.parent_window_ref = parent # This is MainWindow or another SubFSMEditorDialog
        self.scene_ref = scene_ref # This is the DiagramScene instance (main or sub)

        layout = QFormLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12,12,12,12)

        p = current_properties or {}

        self.name_edit = QLineEdit(p.get('name', "StateName"))
        self.name_edit.setPlaceholderText("Unique name for the state")

        self.is_initial_cb = QCheckBox("Is Initial State")
        self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Is Final State")
        self.is_final_cb.setChecked(p.get('is_final', False))

        self.color_button = QPushButton("Choose Color...")
        self.color_button.setObjectName("ColorButton")
        self.current_color = QColor(p.get('color', COLOR_ITEM_STATE_DEFAULT_BG))
        self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)

        self.is_superstate_cb = QCheckBox("Is Superstate (Composite State)")
        self.is_superstate_cb.setChecked(p.get('is_superstate', False))
        self.is_superstate_cb.toggled.connect(self._on_superstate_toggled)

        self.edit_sub_fsm_button = QPushButton(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Sub"), "Edit Sub-Machine...")
        self.edit_sub_fsm_button.setToolTip("Open the editor for the internal states and transitions of this superstate.")
        self.edit_sub_fsm_button.clicked.connect(self._on_edit_sub_fsm)
        self.edit_sub_fsm_button.setEnabled(self.is_superstate_cb.isChecked())
        
        raw_sub_fsm_data = p.get('sub_fsm_data', {})
        if isinstance(raw_sub_fsm_data, dict) and \
           all(k in raw_sub_fsm_data for k in ['states', 'transitions', 'comments']):
            self.current_sub_fsm_data = raw_sub_fsm_data
        else:
            self.current_sub_fsm_data = {'states': [], 'transitions': [], 'comments': []}


        self.entry_action_edit = QTextEdit(p.get('entry_action', ""))
        self.entry_action_edit.setFixedHeight(65); self.entry_action_edit.setPlaceholderText("MATLAB/Python actions on entry...")
        entry_action_btn = self._create_insert_snippet_button(self.entry_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")

        self.during_action_edit = QTextEdit(p.get('during_action', ""))
        self.during_action_edit.setFixedHeight(65); self.during_action_edit.setPlaceholderText("MATLAB/Python actions during state...")
        during_action_btn = self._create_insert_snippet_button(self.during_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")

        self.exit_action_edit = QTextEdit(p.get('exit_action', ""))
        self.exit_action_edit.setFixedHeight(65); self.exit_action_edit.setPlaceholderText("MATLAB/Python actions on exit...")
        exit_action_btn = self._create_insert_snippet_button(self.exit_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")

        self.description_edit = QTextEdit(p.get('description', ""))
        self.description_edit.setFixedHeight(75); self.description_edit.setPlaceholderText("Optional notes about this state")

        layout.addRow("Name:", self.name_edit)
        cb_layout = QHBoxLayout(); cb_layout.addWidget(self.is_initial_cb); cb_layout.addWidget(self.is_final_cb); cb_layout.addStretch()
        layout.addRow("", cb_layout)
        layout.addRow("Color:", self.color_button)
        
        cb_layout_super = QHBoxLayout()
        cb_layout_super.addWidget(self.is_superstate_cb)
        cb_layout_super.addWidget(self.edit_sub_fsm_button)
        cb_layout_super.addStretch()
        layout.addRow("Hierarchy:", cb_layout_super)

        def add_field(lbl, te, btn):
            h = QHBoxLayout(); h.setSpacing(5); h.addWidget(te,1)
            v = QVBoxLayout(); v.addWidget(btn); v.addStretch(); h.addLayout(v)
            layout.addRow(lbl,h)

        add_field("Entry Action:", self.entry_action_edit, entry_action_btn)
        add_field("During Action:", self.during_action_edit, during_action_btn)
        add_field("Exit Action:", self.exit_action_edit, exit_action_btn)
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
        # Pass self.parent_window_ref (MainWindow or parent SubFSMEditorDialog) as context
        # Pass self (StatePropertiesDialog) as QDialog parent
        sub_editor_dialog = SubFSMEditorDialog(
            self.current_sub_fsm_data,
            parent_state_name,
            parent_main_window_context=self.parent_window_ref, 
            parent=self
        )
        
        if sub_editor_dialog.exec_() == QDialog.Accepted:
            updated_data = sub_editor_dialog.get_updated_sub_fsm_data()
            self.current_sub_fsm_data = updated_data
            QMessageBox.information(self, "Sub-Machine Updated",
                                    "Sub-machine data has been updated in this dialog. "
                                    "Click OK to save these changes to the state.")

    def _create_insert_snippet_button(self, target_widget: QTextEdit, snippets_dict: dict, button_text="Insert...", icon_size_px=14):
        # ... (unchanged)
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
        # ... (unchanged)
        color = QColorDialog.getColor(self.current_color, self, "Select State Color")
        if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self):
        # ... (unchanged)
        luminance = self.current_color.lightnessF()
        text_color = COLOR_TEXT_PRIMARY if luminance > 0.5 else COLOR_TEXT_ON_ACCENT
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color};")

    def get_properties(self):
        # ... (unchanged)
        sub_data_to_return = {'states': [], 'transitions': [], 'comments': []}
        if self.is_superstate_cb.isChecked():
            sub_data_to_return = self.current_sub_fsm_data

        return {
            'name': self.name_edit.text().strip(),
            'is_initial': self.is_initial_cb.isChecked(),
            'is_final': self.is_final_cb.isChecked(),
            'color': self.current_color.name(),
            'entry_action': self.entry_action_edit.toPlainText().strip(),
            'during_action': self.during_action_edit.toPlainText().strip(),
            'exit_action': self.exit_action_edit.toPlainText().strip(),
            'description': self.description_edit.toPlainText().strip(),
            'is_superstate': self.is_superstate_cb.isChecked(),
            'sub_fsm_data': sub_data_to_return
        }


class TransitionPropertiesDialog(QDialog):
    # ... (this class is unchanged)
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogInfoView, "Props"))
        self.setMinimumWidth(520)

        layout = QFormLayout(self); layout.setSpacing(8); layout.setContentsMargins(12,12,12,12)
        p = current_properties or {}

        self.event_edit = QLineEdit(p.get('event', "")); self.event_edit.setPlaceholderText("e.g., timeout_event, button_press(ID)")
        event_btn = self._create_insert_snippet_button_lineedit(self.event_edit, MECHATRONICS_COMMON_EVENTS, " Insert Event")

        self.condition_edit = QLineEdit(p.get('condition', "")); self.condition_edit.setPlaceholderText("e.g., variable_x > 10 && flag_is_true")
        condition_btn = self._create_insert_snippet_button_lineedit(self.condition_edit, MECHATRONICS_COMMON_CONDITIONS, " Insert Condition")

        self.action_edit = QTextEdit(p.get('action', "")); self.action_edit.setPlaceholderText("MATLAB/Python actions on transition...")
        self.action_edit.setFixedHeight(65)
        action_btn = self._create_insert_snippet_button_qtextedit(self.action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")

        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton")
        self.current_color = QColor(p.get('color', COLOR_ITEM_TRANSITION_DEFAULT))
        self._update_color_button_style(); self.color_button.clicked.connect(self._choose_color)

        self.offset_perp_spin = QSpinBox(); self.offset_perp_spin.setRange(-1000, 1000); self.offset_perp_spin.setSingleStep(10)
        self.offset_perp_spin.setValue(int(p.get('control_offset_x', 0))); self.offset_perp_spin.setToolTip("Perpendicular bend of curve (0 for straight line).")

        self.offset_tang_spin = QSpinBox(); self.offset_tang_spin.setRange(-1000, 1000); self.offset_tang_spin.setSingleStep(10)
        self.offset_tang_spin.setValue(int(p.get('control_offset_y', 0))); self.offset_tang_spin.setToolTip("Tangential shift of curve midpoint along the line.")

        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75)
        self.description_edit.setPlaceholderText("Optional notes for this transition")

        def add_field_with_button(label_text, edit_widget, button):
            h_layout = QHBoxLayout(); h_layout.setSpacing(5); h_layout.addWidget(edit_widget, 1)
            v_button_layout = QVBoxLayout(); v_button_layout.addWidget(button); v_button_layout.addStretch()
            h_layout.addLayout(v_button_layout); layout.addRow(label_text, h_layout)

        add_field_with_button("Event Trigger:", self.event_edit, event_btn)
        add_field_with_button("Condition (Guard):", self.condition_edit, condition_btn)
        add_field_with_button("Transition Action:", self.action_edit, action_btn)
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

    def _create_insert_snippet_button_qtextedit(self, target_text_edit: QTextEdit, snippets_dict: dict, button_text="Insert..."):
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
            'event': self.event_edit.text().strip(),
            'condition': self.condition_edit.text().strip(),
            'action': self.action_edit.toPlainText().strip(),
            'color': self.current_color.name(),
            'control_offset_x': self.offset_perp_spin.value(),
            'control_offset_y': self.offset_tang_spin.value(),
            'description': self.description_edit.toPlainText().strip()
        }


class CommentPropertiesDialog(QDialog):
    # ... (this class is unchanged)
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


class MatlabSettingsDialog(QDialog):
    # ... (this class is unchanged, assuming it doesn't use QMetaObject.invokeMethod problematicly)
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

    def _auto_detect(self):
        self.test_status_label.setText("Status: Auto-detecting MATLAB, please wait..."); self.test_status_label.setStyleSheet("")
        from PyQt5.QtWidgets import QApplication; QApplication.processEvents()
        self.matlab_connection.detect_matlab()

    def _browse(self):
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        start_dir = QDir.homePath()
        if self.path_edit.text() and QDir(QDir.toNativeSeparators(self.path_edit.text())).exists():
             path_obj = QDir(self.path_edit.text()); path_obj.cdUp(); start_dir = path_obj.absolutePath()
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path: self.path_edit.setText(path); self._update_test_label_from_signal(False, "Path changed. Click 'Test Connection' or 'Apply & Close'.")

    def _test_connection_and_update_label(self):
        path = self.path_edit.text().strip()
        if not path: self._update_test_label_from_signal(False, "MATLAB path is empty. Cannot test."); return
        self.test_status_label.setText("Status: Testing connection, please wait..."); self.test_status_label.setStyleSheet("")
        from PyQt5.QtWidgets import QApplication; QApplication.processEvents()
        if self.matlab_connection.set_matlab_path(path): self.matlab_connection.test_connection()

    def _update_test_label_from_signal(self, success, message):
        status_prefix = "Status: "; current_style = "font-weight: bold; padding: 3px;"
        if success:
            if "path set and appears valid" in message : status_prefix = "Status: Path seems valid. "
            elif "test successful" in message : status_prefix = "Status: Connected! "
            current_style += f"color: #2E7D32;"
        else: status_prefix = "Status: Error. "; current_style += f"color: #C62828;"
        self.test_status_label.setText(status_prefix + message); self.test_status_label.setStyleSheet(current_style)
        if success and self.matlab_connection.matlab_path and not self.path_edit.text():
            self.path_edit.setText(self.matlab_connection.matlab_path)

    def _apply_settings(self):
        path = self.path_edit.text().strip()
        if self.matlab_connection.matlab_path != path:
            self.matlab_connection.set_matlab_path(path)
            if path and not self.matlab_connection.connected : self.matlab_connection.test_connection()
        self.accept()