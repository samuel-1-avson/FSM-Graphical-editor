
import sys # Required by MatlabSettingsDialog for browse filter
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QCheckBox, QPushButton, QTextEdit,
    QSpinBox, QComboBox, QDialogButtonBox, QColorDialog, QHBoxLayout,
    QLabel, QFileDialog, QGroupBox, QMenu, QAction, QVBoxLayout, QStyle
)
from PyQt5.QtGui import QColor, QIcon, QPalette
from PyQt5.QtCore import Qt, QDir, QSize

from config import (
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_ON_ACCENT, MECHATRONICS_COMMON_ACTIONS, MECHATRONICS_COMMON_EVENTS,
    MECHATRONICS_COMMON_CONDITIONS
)
from utils import get_standard_icon
from matlab_integration import MatlabConnection # For type hinting


class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "Props"))
        self.setMinimumWidth(480)

        layout = QFormLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12,12,12,12)

        p = current_properties or {} # Use empty dict if no props passed

        self.name_edit = QLineEdit(p.get('name', "StateName"))
        self.name_edit.setPlaceholderText("Unique name for the state")

        self.is_initial_cb = QCheckBox("Is Initial State")
        self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Is Final State")
        self.is_final_cb.setChecked(p.get('is_final', False))

        self.color_button = QPushButton("Choose Color...")
        self.color_button.setObjectName("ColorButton") # For QSS
        self.current_color = QColor(p.get('color', COLOR_ITEM_STATE_DEFAULT_BG))
        self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)

        # Text Edits for actions
        self.entry_action_edit = QTextEdit(p.get('entry_action', ""))
        self.entry_action_edit.setFixedHeight(65) # Adjust as needed
        self.entry_action_edit.setPlaceholderText("MATLAB actions on entry...")
        entry_action_btn = self._create_insert_snippet_button(self.entry_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")

        self.during_action_edit = QTextEdit(p.get('during_action', ""))
        self.during_action_edit.setFixedHeight(65)
        self.during_action_edit.setPlaceholderText("MATLAB actions during state...")
        during_action_btn = self._create_insert_snippet_button(self.during_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")

        self.exit_action_edit = QTextEdit(p.get('exit_action', ""))
        self.exit_action_edit.setFixedHeight(65)
        self.exit_action_edit.setPlaceholderText("MATLAB actions on exit...")
        exit_action_btn = self._create_insert_snippet_button(self.exit_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")

        self.description_edit = QTextEdit(p.get('description', ""))
        self.description_edit.setFixedHeight(75)
        self.description_edit.setPlaceholderText("Optional notes about this state")

        layout.addRow("Name:", self.name_edit)
        cb_layout = QHBoxLayout()
        cb_layout.addWidget(self.is_initial_cb); cb_layout.addWidget(self.is_final_cb); cb_layout.addStretch()
        layout.addRow("", cb_layout) # Empty label for checkboxes
        layout.addRow("Color:", self.color_button)

        def add_field(lbl, te, btn): # Helper for consistent layout of TextEdit + Button
            h = QHBoxLayout(); h.setSpacing(5)
            h.addWidget(te,1) # TextEdit takes most space
            v = QVBoxLayout(); v.addWidget(btn); v.addStretch() # Button aligned top
            h.addLayout(v)
            layout.addRow(lbl,h)

        add_field("Entry Action:", self.entry_action_edit, entry_action_btn)
        add_field("During Action:", self.during_action_edit, during_action_btn)
        add_field("Exit Action:", self.exit_action_edit, exit_action_btn)
        layout.addRow("Description:", self.description_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

        if is_new_state: # Focus name field for new states
            self.name_edit.selectAll()
            self.name_edit.setFocus()

    def _create_insert_snippet_button(self, target_widget: QTextEdit, snippets_dict: dict, button_text="Insert...", icon_size_px=14):
        button = QPushButton(button_text)
        button.setObjectName("SnippetButton") # For QSS
        button.setToolTip("Insert common snippets")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ins"))
        button.setIconSize(QSize(icon_size_px + 2, icon_size_px + 2)) # Adjust for visual padding

        menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n"))
            menu.addAction(action)
        button.setMenu(menu)
        return button

    def _choose_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select State Color")
        if color.isValid():
            self.current_color = color
            self._update_color_button_style()

    def _update_color_button_style(self):
        # Set button text color based on background luminance for readability
        luminance = self.current_color.lightnessF()
        text_color = COLOR_TEXT_PRIMARY if luminance > 0.5 else COLOR_TEXT_ON_ACCENT
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color};")

    def get_properties(self):
        return {
            'name': self.name_edit.text().strip(),
            'is_initial': self.is_initial_cb.isChecked(),
            'is_final': self.is_final_cb.isChecked(),
            'color': self.current_color.name(),
            'entry_action': self.entry_action_edit.toPlainText().strip(),
            'during_action': self.during_action_edit.toPlainText().strip(),
            'exit_action': self.exit_action_edit.toPlainText().strip(),
            'description': self.description_edit.toPlainText().strip()
        }


class TransitionPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogInfoView, "Props"))
        self.setMinimumWidth(520)

        layout = QFormLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12,12,12,12)

        p = current_properties or {}

        self.event_edit = QLineEdit(p.get('event', ""))
        self.event_edit.setPlaceholderText("e.g., timeout_event, button_press(ID)")
        event_btn = self._create_insert_snippet_button_lineedit(self.event_edit, MECHATRONICS_COMMON_EVENTS, " Insert Event")

        self.condition_edit = QLineEdit(p.get('condition', ""))
        self.condition_edit.setPlaceholderText("e.g., variable_x > 10 && flag_is_true")
        condition_btn = self._create_insert_snippet_button_lineedit(self.condition_edit, MECHATRONICS_COMMON_CONDITIONS, " Insert Condition")

        self.action_edit = QTextEdit(p.get('action', ""))
        self.action_edit.setPlaceholderText("MATLAB actions on transition...")
        self.action_edit.setFixedHeight(65)
        action_btn = self._create_insert_snippet_button_qtextedit(self.action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")

        self.color_button = QPushButton("Choose Color...")
        self.color_button.setObjectName("ColorButton")
        self.current_color = QColor(p.get('color', COLOR_ITEM_TRANSITION_DEFAULT))
        self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)

        # Controls for curve shape (control_offset_x is perp, control_offset_y is tangent)
        self.offset_perp_spin = QSpinBox() # Perpendicular offset from midpoint
        self.offset_perp_spin.setRange(-1000, 1000); self.offset_perp_spin.setSingleStep(10)
        self.offset_perp_spin.setValue(int(p.get('control_offset_x', 0)))
        self.offset_perp_spin.setToolTip("Perpendicular bend of curve (0 for straight line).")

        self.offset_tang_spin = QSpinBox() # Tangential offset of control point
        self.offset_tang_spin.setRange(-1000, 1000); self.offset_tang_spin.setSingleStep(10)
        self.offset_tang_spin.setValue(int(p.get('control_offset_y', 0)))
        self.offset_tang_spin.setToolTip("Tangential shift of curve midpoint along the line.")

        self.description_edit = QTextEdit(p.get('description', ""))
        self.description_edit.setFixedHeight(75)
        self.description_edit.setPlaceholderText("Optional notes for this transition")

        def add_field_with_button(label_text, edit_widget, button): # Helper like in StatePropsDialog
            h_layout = QHBoxLayout(); h_layout.setSpacing(5)
            h_layout.addWidget(edit_widget, 1)
            v_button_layout = QVBoxLayout(); v_button_layout.addWidget(button); v_button_layout.addStretch()
            h_layout.addLayout(v_button_layout)
            layout.addRow(label_text, h_layout)

        add_field_with_button("Event Trigger:", self.event_edit, event_btn)
        add_field_with_button("Condition (Guard):", self.condition_edit, condition_btn)
        add_field_with_button("Transition Action:", self.action_edit, action_btn) # Uses QTextEdit specific helper
        layout.addRow("Color:", self.color_button)

        curve_layout = QHBoxLayout()
        curve_layout.addWidget(QLabel("Bend (Perp):")); curve_layout.addWidget(self.offset_perp_spin)
        curve_layout.addSpacing(10)
        curve_layout.addWidget(QLabel("Mid Shift (Tang):")); curve_layout.addWidget(self.offset_tang_spin)
        curve_layout.addStretch()
        layout.addRow("Curve Shape:", curve_layout)
        layout.addRow("Description:", self.description_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        if is_new_transition: # Focus event field for new transitions
            self.event_edit.setFocus()


    def _create_insert_snippet_button_lineedit(self, target_line_edit: QLineEdit, snippets_dict: dict, button_text="Insert..."):
        button = QPushButton(button_text)
        button.setObjectName("SnippetButton")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins"))
        button.setIconSize(QSize(14+2,14+2)) # Standard icon size for these buttons
        button.setToolTip("Insert common snippets.")
        menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            # Logic to insert snippet into QLineEdit at cursor position
            def insert_logic(checked=False, line_edit=target_line_edit, s=snippet):
                current_text = line_edit.text()
                cursor_pos = line_edit.cursorPosition()
                new_text = current_text[:cursor_pos] + s + current_text[cursor_pos:]
                line_edit.setText(new_text)
                line_edit.setCursorPosition(cursor_pos + len(s))
            action.triggered.connect(insert_logic)
            menu.addAction(action)
        button.setMenu(menu)
        return button

    def _create_insert_snippet_button_qtextedit(self, target_text_edit: QTextEdit, snippets_dict: dict, button_text="Insert..."):
        # Same as the one in StatePropertiesDialog, just adapted for this class structure.
        button = QPushButton(button_text)
        button.setObjectName("SnippetButton")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins"))
        button.setIconSize(QSize(14+2,14+2))
        button.setToolTip("Insert common snippets.")
        menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, text_edit=target_text_edit, s=snippet: text_edit.insertPlainText(s + "\n"))
            menu.addAction(action)
        button.setMenu(menu)
        return button

    def _choose_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select Transition Color")
        if color.isValid():
            self.current_color = color
            self._update_color_button_style()

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
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent)
        self.setWindowTitle("Comment Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cmt"))

        p = current_properties or {}
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12,12,12,12)

        self.text_edit = QTextEdit(p.get('text', "Comment"))
        self.text_edit.setMinimumHeight(100)
        self.text_edit.setPlaceholderText("Enter your comment or note here.")
        layout.addWidget(QLabel("Comment Text:"))
        layout.addWidget(self.text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setMinimumWidth(380)
        self.text_edit.setFocus()
        self.text_edit.selectAll()

    def get_properties(self):
        # Currently only text is editable; width is managed by scene/item.
        return {'text': self.text_edit.toPlainText()}


class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection: MatlabConnection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings")
        self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"))
        self.setMinimumWidth(580)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10); main_layout.setContentsMargins(10,10,10,10)

        # Path Group
        path_group = QGroupBox("MATLAB Executable Path")
        path_form_layout = QFormLayout() # For label + field
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path)
        self.path_edit.setPlaceholderText("e.g., C:\\...\\MATLAB\\R202Xy\\bin\\matlab.exe")
        path_form_layout.addRow("Path:", self.path_edit)

        btn_layout = QHBoxLayout(); btn_layout.setSpacing(6)
        auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_BrowserReload,"Det"), " Auto-detect")
        auto_detect_btn.clicked.connect(self._auto_detect)
        auto_detect_btn.setToolTip("Attempt to find MATLAB installations.")
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), " Browse...")
        browse_btn.clicked.connect(self._browse)
        browse_btn.setToolTip("Browse for MATLAB executable.")
        btn_layout.addWidget(auto_detect_btn); btn_layout.addWidget(browse_btn); btn_layout.addStretch()

        path_v_layout = QVBoxLayout(); path_v_layout.setSpacing(8)
        path_v_layout.addLayout(path_form_layout); path_v_layout.addLayout(btn_layout)
        path_group.setLayout(path_v_layout)
        main_layout.addWidget(path_group)

        # Test Group
        test_group = QGroupBox("Connection Test")
        test_layout = QVBoxLayout(); test_layout.setSpacing(8)
        self.test_status_label = QLabel("Status: Unknown")
        self.test_status_label.setWordWrap(True)
        self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.test_status_label.setMinimumHeight(30) # Allow for 2 lines of text

        test_btn = QPushButton(get_standard_icon(QStyle.SP_CommandLink,"Test"), " Test Connection")
        test_btn.clicked.connect(self._test_connection_and_update_label)
        test_btn.setToolTip("Test connection to the specified MATLAB path.")

        test_layout.addWidget(test_btn); test_layout.addWidget(self.test_status_label, 1) # Label stretches
        test_group.setLayout(test_layout)
        main_layout.addWidget(test_group)

        # Dialog Buttons
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        # Apply and Close for OK, simply reject for Cancel
        dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close")
        dialog_buttons.accepted.connect(self._apply_settings)
        dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)

        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        # Initialize status label
        if self.matlab_connection.matlab_path and self.matlab_connection.connected:
             self._update_test_label_from_signal(True, f"Connected: {self.matlab_connection.matlab_path}")
        elif self.matlab_connection.matlab_path:
            self._update_test_label_from_signal(False, f"Path previously set, but connection unconfirmed or failed.")
        else:
            self._update_test_label_from_signal(False, "MATLAB path not set.")


    def _auto_detect(self):
        self.test_status_label.setText("Status: Auto-detecting MATLAB, please wait...")
        self.test_status_label.setStyleSheet("") # Clear previous color style
        # Need QApplication to process events if this dialog blocks
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents() # Ensure label updates
        self.matlab_connection.detect_matlab() # This will emit connectionStatusChanged

    def _browse(self):
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        start_dir = QDir.homePath()
        if self.path_edit.text() and QDir(QDir.toNativeSeparators(self.path_edit.text())).exists(): #Check path validity
             path_obj = QDir(self.path_edit.text())
             path_obj.cdUp() # Go to bin directory generally
             start_dir = path_obj.absolutePath()

        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path:
            self.path_edit.setText(path)
            # Indicate path has changed and needs re-testing
            self._update_test_label_from_signal(False, "Path changed. Click 'Test Connection' or 'Apply & Close'.")


    def _test_connection_and_update_label(self):
        path = self.path_edit.text().strip()
        if not path:
            self._update_test_label_from_signal(False, "MATLAB path is empty. Cannot test.")
            return
        self.test_status_label.setText("Status: Testing connection, please wait...")
        self.test_status_label.setStyleSheet("") # Clear previous style
        # Need QApplication to process events if this dialog blocks
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()
        # set_matlab_path first validates, then test_connection performs the actual test.
        # connectionStatusChanged signal will update the label.
        if self.matlab_connection.set_matlab_path(path): # This emits if path is structurally valid
            self.matlab_connection.test_connection() # This emits on test result


    def _update_test_label_from_signal(self, success, message):
        status_prefix = "Status: "
        current_style = "font-weight: bold; padding: 3px;"
        if success:
            if "path set and appears valid" in message : status_prefix = "Status: Path seems valid. "
            elif "test successful" in message : status_prefix = "Status: Connected! "
            current_style += f"color: #2E7D32;" # Green
        else:
            status_prefix = "Status: Error. "
            current_style += f"color: #C62828;" # Red

        self.test_status_label.setText(status_prefix + message)
        self.test_status_label.setStyleSheet(current_style)

        # If auto-detect successful, update path_edit if it was empty
        if success and self.matlab_connection.matlab_path and not self.path_edit.text():
            self.path_edit.setText(self.matlab_connection.matlab_path)


    def _apply_settings(self):
        path = self.path_edit.text().strip()
        # If path in dialog differs from stored path, update and potentially re-test
        if self.matlab_connection.matlab_path != path:
            self.matlab_connection.set_matlab_path(path) # This updates connected state if structurally valid
            # If path is non-empty but set_matlab_path failed to mark as connected (e.g., invalid structurally)
            # or if it's a new valid path, a test is good.
            if path and not self.matlab_connection.connected :
                self.matlab_connection.test_connection() # Try a full test
        self.accept()
