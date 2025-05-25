# dialogs.py
import sys
from typing import Optional, Dict, Any
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QCheckBox, QPushButton, QTextEdit,
    QSpinBox, QComboBox, QDialogButtonBox, QColorDialog, QHBoxLayout,
    QLabel, QFileDialog, QGroupBox, QMenu, QAction, QVBoxLayout, QStyle,
    QTabWidget, QWidget, QApplication
)
from PyQt5.QtGui import QColor, QIcon, QPalette, QFont
from PyQt5.QtCore import Qt, QDir, QSize, QSettings

from config import (
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_ON_ACCENT, MECHATRONICS_COMMON_ACTIONS, MECHATRONICS_COMMON_EVENTS,
    MECHATRONICS_COMMON_CONDITIONS, COLOR_GRID_MINOR, COLOR_GRID_MAJOR, 
    APP_FONT_FAMILY, COLOR_BACKGROUND_LIGHT, APP_NAME
)
from utils import get_standard_icon
from matlab_integration import MatlabConnection


class BasePropertiesDialog(QDialog):
    """Base class for property dialogs with common functionality."""
    
    def __init__(self, parent=None, title="Properties", icon_type=QStyle.SP_DialogApplyButton, 
                 min_width=480):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(get_standard_icon(icon_type, "Props"))
        self.setMinimumWidth(min_width)
        
    def setup_layout(self):
        """Setup the main form layout with consistent spacing."""
        layout = QFormLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        return layout
        
    def create_color_button(self, initial_color: str) -> QPushButton:
        """Create a color selection button with proper styling."""
        button = QPushButton(initial_color)
        button.setObjectName("ColorButton")
        color = QColor(initial_color)
        self._update_color_button_style(button, color)
        return button, color
        
    def _update_color_button_style(self, button: QPushButton, color: QColor):
        """Update color button appearance based on color luminance."""
        luminance = color.lightnessF()
        text_color = COLOR_TEXT_PRIMARY if luminance > 0.5 else COLOR_TEXT_ON_ACCENT
        button.setStyleSheet(f"background-color: {color.name()}; color: {text_color};")
        button.setText(color.name())
        
    def create_snippet_button_for_textedit(self, target_widget: QTextEdit, 
                                         snippets_dict: Dict[str, str], 
                                         button_text: str = "Insert...",
                                         icon_size: int = 14) -> QPushButton:
        """Create a snippet insertion button for QTextEdit widgets."""
        button = QPushButton(button_text)
        button.setObjectName("SnippetButton")
        button.setToolTip("Insert common snippets")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ins"))
        button.setIconSize(QSize(icon_size + 2, icon_size + 2))
        
        menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            action.triggered.connect(
                lambda checked=False, text_edit=target_widget, s=snippet: 
                text_edit.insertPlainText(s + "\n")
            )
            menu.addAction(action)
        button.setMenu(menu)
        return button
        
    def create_snippet_button_for_lineedit(self, target_widget: QLineEdit, 
                                         snippets_dict: Dict[str, str], 
                                         button_text: str = "Insert...") -> QPushButton:
        """Create a snippet insertion button for QLineEdit widgets."""
        button = QPushButton(button_text)
        button.setObjectName("SnippetButton")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ins"))
        button.setIconSize(QSize(16, 16))
        button.setToolTip("Insert common snippets.")
        
        menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            action.triggered.connect(
                lambda checked=False, line_edit=target_widget, s=snippet: 
                self._insert_at_cursor(line_edit, s)
            )
            menu.addAction(action)
        button.setMenu(menu)
        return button
        
    def _insert_at_cursor(self, line_edit: QLineEdit, text: str):
        """Insert text at cursor position in line edit."""
        current_text = line_edit.text()
        cursor_pos = line_edit.cursorPosition()
        new_text = current_text[:cursor_pos] + text + current_text[cursor_pos:]
        line_edit.setText(new_text)
        line_edit.setCursorPosition(cursor_pos + len(text))
        
    def add_field_with_button(self, layout: QFormLayout, label: str, 
                            edit_widget, button_widget):
        """Add a field with an associated button to the layout."""
        h_layout = QHBoxLayout()
        h_layout.setSpacing(5)
        h_layout.addWidget(edit_widget, 1)
        
        v_layout = QVBoxLayout()
        v_layout.addWidget(button_widget)
        v_layout.addStretch()
        
        h_layout.addLayout(v_layout)
        layout.addRow(label, h_layout)


class StatePropertiesDialog(BasePropertiesDialog):
    """Dialog for editing state properties."""
    
    def __init__(self, parent=None, current_properties: Optional[Dict[str, Any]] = None, 
                 is_new_state: bool = False):
        super().__init__(parent, "State Properties", QStyle.SP_DialogApplyButton, 480)
        
        self.properties = current_properties or {}
        layout = self.setup_layout()
        self._setup_widgets()
        self._setup_layout(layout)
        
        if is_new_state:
            self.name_edit.selectAll()
            self.name_edit.setFocus()
            
    def _setup_widgets(self):
        """Initialize all widgets with current property values."""
        p = self.properties
        
        # Basic properties
        self.name_edit = QLineEdit(p.get('name', "StateName"))
        self.name_edit.setPlaceholderText("Unique name for the state")
        
        self.is_initial_cb = QCheckBox("Is Initial State")
        self.is_initial_cb.setChecked(p.get('is_initial', False))
        
        self.is_final_cb = QCheckBox("Is Final State")
        self.is_final_cb.setChecked(p.get('is_final', False))
        
        # Color selection
        self.color_button, self.current_color = self.create_color_button(
            p.get('color', COLOR_ITEM_STATE_DEFAULT_BG)
        )
        self.color_button.clicked.connect(self._choose_color)
        
        # Action text editors
        self.entry_action_edit = self._create_action_textedit(
            p.get('entry_action', ""), "Actions on entry..."
        )
        self.during_action_edit = self._create_action_textedit(
            p.get('during_action', ""), "Actions during state..."
        )
        self.exit_action_edit = self._create_action_textedit(
            p.get('exit_action', ""), "Actions on exit..."
        )
        
        # Description
        self.description_edit = QTextEdit(p.get('description', ""))
        self.description_edit.setFixedHeight(75)
        self.description_edit.setPlaceholderText("Optional notes about this state")
        
        # Action buttons
        self.entry_action_btn = self.create_snippet_button_for_textedit(
            self.entry_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action"
        )
        self.during_action_btn = self.create_snippet_button_for_textedit(
            self.during_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action"
        )
        self.exit_action_btn = self.create_snippet_button_for_textedit(
            self.exit_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action"
        )
        
    def _create_action_textedit(self, text: str, placeholder: str) -> QTextEdit:
        """Create a QTextEdit for action input."""
        edit = QTextEdit(text)
        edit.setFixedHeight(65)
        edit.setPlaceholderText(placeholder)
        return edit
        
    def _setup_layout(self, layout: QFormLayout):
        """Setup the dialog layout."""
        layout.addRow("Name:", self.name_edit)
        
        # Checkboxes layout
        cb_layout = QHBoxLayout()
        cb_layout.addWidget(self.is_initial_cb)
        cb_layout.addWidget(self.is_final_cb)
        cb_layout.addStretch()
        layout.addRow("", cb_layout)
        
        layout.addRow("Color:", self.color_button)
        
        # Action fields with buttons
        self.add_field_with_button(layout, "Entry Action:", 
                                 self.entry_action_edit, self.entry_action_btn)
        self.add_field_with_button(layout, "During Action:", 
                                 self.during_action_edit, self.during_action_btn)
        self.add_field_with_button(layout, "Exit Action:", 
                                 self.exit_action_edit, self.exit_action_btn)
        
        layout.addRow("Description:", self.description_edit)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
    def _choose_color(self):
        """Open color dialog and update button style."""
        color = QColorDialog.getColor(self.current_color, self, "Select State Color")
        if color.isValid():
            self.current_color = color
            self._update_color_button_style(self.color_button, color)
            
    def get_properties(self) -> Dict[str, Any]:
        """Return the current property values."""
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


class TransitionPropertiesDialog(BasePropertiesDialog):
    """Dialog for editing transition properties."""
    
    def __init__(self, parent=None, current_properties: Optional[Dict[str, Any]] = None, 
                 is_new_transition: bool = False):
        super().__init__(parent, "Transition Properties", QStyle.SP_FileDialogInfoView, 520)
        
        self.properties = current_properties or {}
        layout = self.setup_layout()
        self._setup_widgets()
        self._setup_layout(layout)
        
        if is_new_transition:
            self.event_edit.setFocus()
            
    def _setup_widgets(self):
        """Initialize all widgets with current property values."""
        p = self.properties
        
        # Event and condition inputs
        self.event_edit = QLineEdit(p.get('event', ""))
        self.event_edit.setPlaceholderText("e.g., timeout, button_press(ID)")
        
        self.condition_edit = QLineEdit(p.get('condition', ""))
        self.condition_edit.setPlaceholderText("e.g., var_x > 10 && flag")
        
        # Action input
        self.action_edit = QTextEdit(p.get('action', ""))
        self.action_edit.setPlaceholderText("Actions on transition...")
        self.action_edit.setFixedHeight(65)
        
        # Color selection
        self.color_button, self.current_color = self.create_color_button(
            p.get('color', COLOR_ITEM_TRANSITION_DEFAULT)
        )
        self.color_button.clicked.connect(self._choose_color)
        
        # Curve control spinboxes
        self.offset_perp_spin = self._create_offset_spinbox(
            p.get('control_offset_x', 0), "Perpendicular bend of curve."
        )
        self.offset_tang_spin = self._create_offset_spinbox(
            p.get('control_offset_y', 0), "Tangential shift of curve midpoint."
        )
        
        # Description
        self.description_edit = QTextEdit(p.get('description', ""))
        self.description_edit.setFixedHeight(75)
        self.description_edit.setPlaceholderText("Optional notes")
        
        # Snippet buttons
        self.event_btn = self.create_snippet_button_for_lineedit(
            self.event_edit, MECHATRONICS_COMMON_EVENTS, " Insert Event"
        )
        self.condition_btn = self.create_snippet_button_for_lineedit(
            self.condition_edit, MECHATRONICS_COMMON_CONDITIONS, " Insert Condition"
        )
        self.action_btn = self.create_snippet_button_for_textedit(
            self.action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action"
        )
        
    def _create_offset_spinbox(self, value: int, tooltip: str) -> QSpinBox:
        """Create a spinbox for curve offset values."""
        spinbox = QSpinBox()
        spinbox.setRange(-1000, 1000)
        spinbox.setSingleStep(10)
        spinbox.setValue(int(value))
        spinbox.setToolTip(tooltip)
        return spinbox
        
    def _setup_layout(self, layout: QFormLayout):
        """Setup the dialog layout."""
        self.add_field_with_button(layout, "Event Trigger:", 
                                 self.event_edit, self.event_btn)
        self.add_field_with_button(layout, "Condition (Guard):", 
                                 self.condition_edit, self.condition_btn)
        self.add_field_with_button(layout, "Transition Action:", 
                                 self.action_edit, self.action_btn)
        
        layout.addRow("Color:", self.color_button)
        
        # Curve shape controls
        curve_layout = QHBoxLayout()
        curve_layout.addWidget(QLabel("Bend (Perp):"))
        curve_layout.addWidget(self.offset_perp_spin)
        curve_layout.addSpacing(10)
        curve_layout.addWidget(QLabel("Mid Shift (Tang):"))
        curve_layout.addWidget(self.offset_tang_spin)
        curve_layout.addStretch()
        layout.addRow("Curve Shape:", curve_layout)
        
        layout.addRow("Description:", self.description_edit)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
    def _choose_color(self):
        """Open color dialog and update button style."""
        color = QColorDialog.getColor(self.current_color, self, "Select Transition Color")
        if color.isValid():
            self.current_color = color
            self._update_color_button_style(self.color_button, color)
            
    def get_properties(self) -> Dict[str, Any]:
        """Return the current property values."""
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
    """Simple dialog for editing comment text."""
    
    def __init__(self, parent=None, current_properties: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle("Comment Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cmt"))
        self.setMinimumWidth(380)
        
        properties = current_properties or {}
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        self.text_edit = QTextEdit(properties.get('text', "Comment"))
        self.text_edit.setMinimumHeight(100)
        self.text_edit.setPlaceholderText("Enter your comment or note here.")
        
        layout.addWidget(QLabel("Comment Text:"))
        layout.addWidget(self.text_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.text_edit.setFocus()
        self.text_edit.selectAll()
        
    def get_properties(self) -> Dict[str, str]:
        """Return the comment text."""
        return {'text': self.text_edit.toPlainText()}


class MatlabSettingsDialog(QDialog):
    """Dialog for MATLAB connection settings."""
    
    def __init__(self, matlab_connection: MatlabConnection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings")
        self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "CfgM"))
        self.setMinimumWidth(580)
        
        self._setup_ui()
        self._connect_signals()
        self._update_initial_status()
        
    def _setup_ui(self):
        """Setup the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Path configuration group
        path_group = QGroupBox("MATLAB Executable Path")
        path_form_layout = QFormLayout()
        
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path)
        self.path_edit.setPlaceholderText("e.g., C:\\...\\MATLAB\\R202Xy\\bin\\matlab.exe")
        path_form_layout.addRow("Path:", self.path_edit)
        
        # Path buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        
        auto_detect_btn = QPushButton(
            get_standard_icon(QStyle.SP_BrowserReload, "Det"), " Auto-detect"
        )
        auto_detect_btn.clicked.connect(self._auto_detect)
        auto_detect_btn.setToolTip("Attempt to find MATLAB installations.")
        
        browse_btn = QPushButton(
            get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), " Browse..."
        )
        browse_btn.clicked.connect(self._browse)
        browse_btn.setToolTip("Browse for MATLAB executable.")
        
        btn_layout.addWidget(auto_detect_btn)
        btn_layout.addWidget(browse_btn)
        btn_layout.addStretch()
        
        path_v_layout = QVBoxLayout()
        path_v_layout.setSpacing(8)
        path_v_layout.addLayout(path_form_layout)
        path_v_layout.addLayout(btn_layout)
        path_group.setLayout(path_v_layout)
        main_layout.addWidget(path_group)
        
        # Connection test group
        test_group = QGroupBox("Connection Test")
        test_layout = QVBoxLayout()
        test_layout.setSpacing(8)
        
        self.test_status_label = QLabel("Status: Unknown")
        self.test_status_label.setWordWrap(True)
        self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.test_status_label.setMinimumHeight(30)
        
        test_btn = QPushButton(
            get_standard_icon(QStyle.SP_CommandLink, "Test"), " Test Connection"
        )
        test_btn.clicked.connect(self._test_connection_and_update_label)
        test_btn.setToolTip("Test connection to the specified MATLAB path.")
        
        test_layout.addWidget(test_btn)
        test_layout.addWidget(self.test_status_label, 1)
        test_group.setLayout(test_layout)
        main_layout.addWidget(test_group)
        
        # Dialog buttons
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close")
        dialog_buttons.accepted.connect(self._apply_settings)
        dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)
        
    def _connect_signals(self):
        """Connect MATLAB connection signals."""
        self.matlab_connection.connectionStatusChanged.connect(
            self._update_test_label_from_signal
        )
        
    def _update_initial_status(self):
        """Update the initial status display."""
        if self.matlab_connection.matlab_path and self.matlab_connection.connected:
            self._update_test_label_from_signal(
                True, f"Connected: {self.matlab_connection.matlab_path}"
            )
        elif self.matlab_connection.matlab_path:
            self._update_test_label_from_signal(
                False, "Path previously set, connection unconfirmed."
            )
        else:
            self._update_test_label_from_signal(False, "MATLAB path not set.")
            
    def _auto_detect(self):
        """Auto-detect MATLAB installation."""
        self.test_status_label.setText("Status: Auto-detecting MATLAB...")
        QApplication.processEvents()
        self.matlab_connection.detect_matlab()
        
    def _browse(self):
        """Browse for MATLAB executable."""
        exe_filter = ("MATLAB Executable (matlab.exe)" if sys.platform == 'win32' 
                     else "MATLAB Executable (matlab);;All Files (*)")
        start_dir = QDir.homePath()
        
        if self.path_edit.text() and QDir(QDir.toNativeSeparators(self.path_edit.text())).exists():
            path_obj = QDir(self.path_edit.text())
            path_obj.cdUp()
            start_dir = path_obj.absolutePath()
            
        path, _ = QFileDialog.getOpenFileName(
            self, "Select MATLAB Executable", start_dir, exe_filter
        )
        if path:
            self.path_edit.setText(path)
            self._update_test_label_from_signal(False, "Path changed. Test or Apply.")
            
    def _test_connection_and_update_label(self):
        """Test the MATLAB connection and update status."""
        path = self.path_edit.text().strip()
        if not path:
            self._update_test_label_from_signal(False, "MATLAB path is empty.")
            return
            
        self.test_status_label.setText("Status: Testing connection...")
        QApplication.processEvents()
        
        if self.matlab_connection.set_matlab_path(path):
            self.matlab_connection.test_connection()
            
    def _update_test_label_from_signal(self, success: bool, message: str):
        """Update test status label based on connection signal."""
        status_prefix = "Status: "
        style = "font-weight:bold;padding:3px;"
        
        if success:
            if "path set" in message:
                status_prefix = "Status: Path valid. "
            elif "test successful" in message:
                status_prefix = "Status: Connected! "
            style += "color:#2E7D32;"  # Green
        else:
            status_prefix = "Status: Error. "
            style += "color:#C62828;"  # Red
            
        self.test_status_label.setText(status_prefix + message)
        self.test_status_label.setStyleSheet(style)
        
        if (success and self.matlab_connection.matlab_path and 
            not self.path_edit.text()):
            self.path_edit.setText(self.matlab_connection.matlab_path)
            
    def _apply_settings(self):
        """Apply the settings and close dialog."""
        path = self.path_edit.text().strip()
        if self.matlab_connection.matlab_path != path:
            self.matlab_connection.set_matlab_path(path)
            if path and not self.matlab_connection.connected:
                self.matlab_connection.test_connection()
        self.accept()


class AppearanceSettingsTab(QWidget):
    """Tab widget for appearance settings."""
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.initial_settings = self._get_current_app_settings()
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Grid settings group
        grid_group = QGroupBox("Diagram Grid")
        grid_layout = QFormLayout(grid_group)
        
        self.grid_visible_cb = QCheckBox("Show Grid")
        self.grid_visible_cb.setChecked(self.initial_settings['grid_visible'])
        grid_layout.addRow(self.grid_visible_cb)
        
        # Grid color buttons
        self.minor_grid_color_button = QPushButton(self.initial_settings['minor_grid_color'])
        self.minor_grid_color_button.setObjectName("ColorButton")
        self.current_minor_grid_color = QColor(self.initial_settings['minor_grid_color'])
        self._update_color_button_style(self.minor_grid_color_button, self.current_minor_grid_color)
        self.minor_grid_color_button.clicked.connect(lambda: self._choose_grid_color('minor'))
        grid_layout.addRow("Minor Grid Color:", self.minor_grid_color_button)
        
        self.major_grid_color_button = QPushButton(self.initial_settings['major_grid_color'])
        self.major_grid_color_button.setObjectName("ColorButton")
        self.current_major_grid_color = QColor(self.initial_settings['major_grid_color'])
        self._update_color_button_style(self.major_grid_color_button, self.current_major_grid_color)
        self.major_grid_color_button.clicked.connect(lambda: self._choose_grid_color('major'))
        grid_layout.addRow("Major Grid Color:", self.major_grid_color_button)
        
        layout.addWidget(grid_group)
        
        # Font settings group
        font_group = QGroupBox("Application Font")
        font_layout = QFormLayout(font_group)
        
        self.app_font_size_spinbox = QSpinBox()
        self.app_font_size_spinbox.setRange(7, 16)
        self.app_font_size_spinbox.setValue(self.initial_settings['app_font_size'])
        self.app_font_size_spinbox.setSuffix(" pt")
        font_layout.addRow("Base Font Size:", self.app_font_size_spinbox)
        
        font_layout.addRow(
            QLabel("<small><i>Note: A restart may be needed for all font changes to fully apply.</i></small>")
        )
        layout.addWidget(font_group)
        
        layout.addStretch()
        
    def _get_current_app_settings(self) -> Dict[str, Any]:
        """Get current application settings with fallbacks."""
        settings_qt = QSettings(APP_NAME, "AppearanceSettings")
        scene = self.main_window.scene
        
        # Determine default font size
        default_font_size = 9
        app_font = QApplication.instance().font()
        if app_font.pointSize() > 0:
            default_font_size = app_font.pointSize()
        elif app_font.pixelSize() > 0 and self.logicalDpiY() > 0:
            default_font_size = round(app_font.pixelSize() * 72 / self.logicalDpiY())
            
        return {
            'grid_visible': settings_qt.value("grid_visible", scene.grid_visible, type=bool),
            'minor_grid_color': settings_qt.value("minor_grid_color", 
                                                scene.grid_pen_light.color().name(), type=str),
            'major_grid_color': settings_qt.value("major_grid_color", 
                                                scene.grid_pen_dark.color().name(), type=str),
            'app_font_size': settings_qt.value("app_font_size", default_font_size, type=int)
        }
        
    def _update_color_button_style(self, button: QPushButton, color: QColor):
        """Update color button styling."""
        luminance = color.lightnessF()
        text_color = COLOR_TEXT_PRIMARY if luminance > 0.5 else COLOR_TEXT_ON_ACCENT
        button.setText(color.name())

    def get_properties(self):
        return {'name': self.name_edit.text().strip(), 'is_initial': self.is_initial_cb.isChecked(),
                'is_final': self.is_final_cb.isChecked(), 'color': self.current_color.name(),
                'entry_action': self.entry_action_edit.toPlainText().strip(),
                'during_action': self.during_action_edit.toPlainText().strip(),
                'exit_action': self.exit_action_edit.toPlainText().strip(),
                'description': self.description_edit.toPlainText().strip()}


class TransitionPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogInfoView, "Props"))
        self.setMinimumWidth(520)
        layout = QFormLayout(self); layout.setSpacing(8); layout.setContentsMargins(12,12,12,12)
        p = current_properties or {}

        self.event_edit = QLineEdit(p.get('event', "")); self.event_edit.setPlaceholderText("e.g., timeout, button_press(ID)")
        event_btn = self._create_insert_snippet_button_lineedit(self.event_edit, MECHATRONICS_COMMON_EVENTS, " Insert Event")
        self.condition_edit = QLineEdit(p.get('condition', "")); self.condition_edit.setPlaceholderText("e.g., var_x > 10 && flag")
        condition_btn = self._create_insert_snippet_button_lineedit(self.condition_edit, MECHATRONICS_COMMON_CONDITIONS, " Insert Condition")
        self.action_edit = QTextEdit(p.get('action', "")); self.action_edit.setPlaceholderText("Actions on transition...")
        self.action_edit.setFixedHeight(65); action_btn = self._create_insert_snippet_button_qtextedit(self.action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        self.color_button = QPushButton(p.get('color', COLOR_ITEM_TRANSITION_DEFAULT)); self.color_button.setObjectName("ColorButton")
        self.current_color = QColor(p.get('color', COLOR_ITEM_TRANSITION_DEFAULT)); self._update_color_button_style(); self.color_button.clicked.connect(self._choose_color)
        self.offset_perp_spin = QSpinBox(); self.offset_perp_spin.setRange(-1000, 1000); self.offset_perp_spin.setSingleStep(10)
        self.offset_perp_spin.setValue(int(p.get('control_offset_x', 0))); self.offset_perp_spin.setToolTip("Perpendicular bend of curve.")
        self.offset_tang_spin = QSpinBox(); self.offset_tang_spin.setRange(-1000, 1000); self.offset_tang_spin.setSingleStep(10)
        self.offset_tang_spin.setValue(int(p.get('control_offset_y', 0))); self.offset_tang_spin.setToolTip("Tangential shift of curve midpoint.")
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75); self.description_edit.setPlaceholderText("Optional notes")

        def add_field(lbl, edit, btn): h=QHBoxLayout();h.setSpacing(5);h.addWidget(edit,1);v=QVBoxLayout();v.addWidget(btn);v.addStretch();h.addLayout(v);layout.addRow(lbl,h)
        add_field("Event Trigger:", self.event_edit, event_btn)
        add_field("Condition (Guard):", self.condition_edit, condition_btn)
        add_field("Transition Action:", self.action_edit, action_btn)
        layout.addRow("Color:", self.color_button)
        curve_layout=QHBoxLayout();curve_layout.addWidget(QLabel("Bend (Perp):"));curve_layout.addWidget(self.offset_perp_spin);curve_layout.addSpacing(10)
        curve_layout.addWidget(QLabel("Mid Shift (Tang):"));curve_layout.addWidget(self.offset_tang_spin);curve_layout.addStretch()
        layout.addRow("Curve Shape:", curve_layout); layout.addRow("Description:", self.description_edit)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(self.accept); btns.rejected.connect(self.reject); layout.addRow(btns)
        if is_new_transition: self.event_edit.setFocus()

    def _create_insert_snippet_button_lineedit(self, target_line_edit: QLineEdit, snippets_dict: dict, button_text="Insert..."):
        button = QPushButton(button_text); button.setObjectName("SnippetButton"); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins")); button.setIconSize(QSize(16,16)); button.setToolTip("Insert common snippets.")
        menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            def insert_logic(checked=False, line_edit=target_line_edit, s=snippet): current_text=line_edit.text();cursor_pos=line_edit.cursorPosition();new_text=current_text[:cursor_pos]+s+current_text[cursor_pos:];line_edit.setText(new_text);line_edit.setCursorPosition(cursor_pos+len(s))
            action.triggered.connect(insert_logic); menu.addAction(action)
        button.setMenu(menu); return button

    def _create_insert_snippet_button_qtextedit(self, target_text_edit: QTextEdit, snippets_dict: dict, button_text="Insert..."):
        button = QPushButton(button_text); button.setObjectName("SnippetButton"); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins")); button.setIconSize(QSize(16,16)); button.setToolTip("Insert common snippets.")
        menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, text_edit=target_text_edit, s=snippet: text_edit.insertPlainText(s + "\n"))
            menu.addAction(action)
        button.setMenu(menu); return button

    def _choose_color(self): color = QColorDialog.getColor(self.current_color, self, "Select Transition Color");
    if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self): luminance=self.current_color.lightnessF();text_color=COLOR_TEXT_PRIMARY if luminance > 0.5 else COLOR_TEXT_ON_ACCENT;self.color_button.setStyleSheet(f"background-color:{self.current_color.name()};color:{text_color};"); self.color_button.setText(self.current_color.name())

    def get_properties(self):
        return {'event':self.event_edit.text().strip(),'condition':self.condition_edit.text().strip(),'action':self.action_edit.toPlainText().strip(),
                'color':self.current_color.name(),'control_offset_x':self.offset_perp_spin.value(),'control_offset_y':self.offset_tang_spin.value(),
                'description':self.description_edit.toPlainText().strip()}


class CommentPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent); self.setWindowTitle("Comment Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cmt"))
        p = current_properties or {}; layout = QVBoxLayout(self); layout.setSpacing(8); layout.setContentsMargins(12,12,12,12)
        self.text_edit = QTextEdit(p.get('text', "Comment")); self.text_edit.setMinimumHeight(100); self.text_edit.setPlaceholderText("Enter your comment or note here.")
        layout.addWidget(QLabel("Comment Text:")); layout.addWidget(self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.setMinimumWidth(380); self.text_edit.setFocus(); self.text_edit.selectAll()
    def get_properties(self): return {'text': self.text_edit.toPlainText()}


class MatlabSettingsDialog(QDialog): # This can be removed if MATLAB features are fully deprecated
    def __init__(self, matlab_connection: MatlabConnection, parent=None):
        super().__init__(parent); self.matlab_connection = matlab_connection; self.setWindowTitle("MATLAB Settings"); self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "CfgM")); self.setMinimumWidth(580) # Changed icon alt text
        main_layout = QVBoxLayout(self); main_layout.setSpacing(10); main_layout.setContentsMargins(10,10,10,10)
        path_group = QGroupBox("MATLAB Executable Path"); path_form_layout = QFormLayout(); self.path_edit = QLineEdit(self.matlab_connection.matlab_path); self.path_edit.setPlaceholderText("e.g., C:\\...\\MATLAB\\R202Xy\\bin\\matlab.exe"); path_form_layout.addRow("Path:", self.path_edit)
        btn_layout = QHBoxLayout(); btn_layout.setSpacing(6); auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_BrowserReload,"Det"), " Auto-detect"); auto_detect_btn.clicked.connect(self._auto_detect); auto_detect_btn.setToolTip("Attempt to find MATLAB installations.")
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), " Browse..."); browse_btn.clicked.connect(self._browse); browse_btn.setToolTip("Browse for MATLAB executable."); btn_layout.addWidget(auto_detect_btn); btn_layout.addWidget(browse_btn); btn_layout.addStretch()
        path_v_layout = QVBoxLayout(); path_v_layout.setSpacing(8); path_v_layout.addLayout(path_form_layout); path_v_layout.addLayout(btn_layout); path_group.setLayout(path_v_layout); main_layout.addWidget(path_group)
        test_group = QGroupBox("Connection Test"); test_layout = QVBoxLayout(); test_layout.setSpacing(8); self.test_status_label = QLabel("Status: Unknown"); self.test_status_label.setWordWrap(True); self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse); self.test_status_label.setMinimumHeight(30)
        test_btn = QPushButton(get_standard_icon(QStyle.SP_CommandLink,"Test"), " Test Connection"); test_btn.clicked.connect(self._test_connection_and_update_label); test_btn.setToolTip("Test connection to the specified MATLAB path.")
        test_layout.addWidget(test_btn); test_layout.addWidget(self.test_status_label, 1); test_group.setLayout(test_layout); main_layout.addWidget(test_group)
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close"); dialog_buttons.accepted.connect(self._apply_settings); dialog_buttons.rejected.connect(self.reject); main_layout.addWidget(dialog_buttons)
        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        if self.matlab_connection.matlab_path and self.matlab_connection.connected: self._update_test_label_from_signal(True, f"Connected: {self.matlab_connection.matlab_path}")
        elif self.matlab_connection.matlab_path: self._update_test_label_from_signal(False, f"Path previously set, connection unconfirmed.")
        else: self._update_test_label_from_signal(False, "MATLAB path not set.")

    def _auto_detect(self): self.test_status_label.setText("Status: Auto-detecting MATLAB..."); QApplication.processEvents(); self.matlab_connection.detect_matlab()
    def _browse(self):
        exe_filter="MATLAB Executable (matlab.exe)" if sys.platform=='win32' else "MATLAB Executable (matlab);;All Files (*)"; start_dir=QDir.homePath()
        if self.path_edit.text() and QDir(QDir.toNativeSeparators(self.path_edit.text())).exists(): path_obj=QDir(self.path_edit.text());path_obj.cdUp();start_dir=path_obj.absolutePath()
        path,_=QFileDialog.getOpenFileName(self,"Select MATLAB Executable",start_dir,exe_filter)
        if path:self.path_edit.setText(path);self._update_test_label_from_signal(False,"Path changed. Test or Apply.")
    def _test_connection_and_update_label(self):
        path=self.path_edit.text().strip()
        if not path:self._update_test_label_from_signal(False,"MATLAB path is empty.");return
        self.test_status_label.setText("Status: Testing connection...");QApplication.processEvents()
        if self.matlab_connection.set_matlab_path(path):self.matlab_connection.test_connection()
    def _update_test_label_from_signal(self,success,message):
        status_prefix="Status: ";style="font-weight:bold;padding:3px;"
        if success:
            if "path set" in message:status_prefix="Status: Path valid. "
            elif "test successful" in message:status_prefix="Status: Connected! "
            style+="color:#2E7D32;" # Green
        else: status_prefix="Status: Error. ";style+="color:#C62828;" # Red
        self.test_status_label.setText(status_prefix+message);self.test_status_label.setStyleSheet(style)
        if success and self.matlab_connection.matlab_path and not self.path_edit.text():self.path_edit.setText(self.matlab_connection.matlab_path)
    def _apply_settings(self):
        path=self.path_edit.text().strip()
        if self.matlab_connection.matlab_path!=path:
            self.matlab_connection.set_matlab_path(path)
            if path and not self.matlab_connection.connected:self.matlab_connection.test_connection()
        self.accept()


# --- Appearance Settings Tab Widget (as a separate class) ---
class AppearanceSettingsTab(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.initial_settings = self._get_current_app_settings() # Load initial/persisted settings

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)

        # --- Grid Settings ---
        grid_group = QGroupBox("Diagram Grid")
        grid_layout = QFormLayout(grid_group)
        self.grid_visible_cb = QCheckBox("Show Grid")
        self.grid_visible_cb.setChecked(self.initial_settings['grid_visible'])
        grid_layout.addRow(self.grid_visible_cb)

        self.minor_grid_color_button = QPushButton(self.initial_settings['minor_grid_color'])
        self.minor_grid_color_button.setObjectName("ColorButton")
        self.current_minor_grid_color = QColor(self.initial_settings['minor_grid_color'])
        self._update_color_button_style(self.minor_grid_color_button, self.current_minor_grid_color)
        self.minor_grid_color_button.clicked.connect(lambda: self._choose_grid_color('minor'))
        grid_layout.addRow("Minor Grid Color:", self.minor_grid_color_button)

        self.major_grid_color_button = QPushButton(self.initial_settings['major_grid_color'])
        self.major_grid_color_button.setObjectName("ColorButton")
        self.current_major_grid_color = QColor(self.initial_settings['major_grid_color'])
        self._update_color_button_style(self.major_grid_color_button, self.current_major_grid_color)
        self.major_grid_color_button.clicked.connect(lambda: self._choose_grid_color('major'))
        grid_layout.addRow("Major Grid Color:", self.major_grid_color_button)
        layout.addWidget(grid_group)

        # --- Font Settings ---
        font_group = QGroupBox("Application Font")
        font_layout = QFormLayout(font_group)
        self.app_font_size_spinbox = QSpinBox()
        self.app_font_size_spinbox.setRange(7, 16) # Sensible range for font sizes
        self.app_font_size_spinbox.setValue(self.initial_settings['app_font_size'])
        self.app_font_size_spinbox.setSuffix(" pt")
        font_layout.addRow("Base Font Size:", self.app_font_size_spinbox)
        font_layout.addRow(QLabel("<small><i>Note: A restart may be needed for all font changes to fully apply.</i></small>"))
        layout.addWidget(font_group)

        layout.addStretch()

    def _get_current_app_settings(self):
        # Use QSettings to load persisted values, with fallbacks to current app state or defaults
        settings_qt = QSettings(APP_NAME, "AppearanceSettings") # Using APP_NAME for org, specific name for app section
        scene = self.main_window.scene
        
        # Determine default font size carefully
        default_font_size = 9 # A sensible default
        app_font = QApplication.instance().font()
        if app_font.pointSize() > 0:
            default_font_size = app_font.pointSize()
        elif app_font.pixelSize() > 0 and self.logicalDpiY() > 0: # Try to convert from pixels if pointSize is not set
            default_font_size = round(app_font.pixelSize() * 72 / self.logicalDpiY())
        
        return {
            'grid_visible': settings_qt.value("grid_visible", scene.grid_visible, type=bool),
            'minor_grid_color': settings_qt.value("minor_grid_color", scene.grid_pen_light.color().name(), type=str),
            'major_grid_color': settings_qt.value("major_grid_color", scene.grid_pen_dark.color().name(), type=str),
            'app_font_size': settings_qt.value("app_font_size", default_font_size, type=int)
        }

    def _update_color_button_style(self, button, color):
        luminance = color.lightnessF()
        text_color = COLOR_TEXT_PRIMARY if luminance > 0.5 else COLOR_TEXT_ON_ACCENT
        button.setStyleSheet(f"background-color: {color.name()}; color: {text_color};")
        # Continuation of dialogs.py

        button.setText(color.name())
        
    def _choose_grid_color(self, grid_type: str):
        """Choose color for grid (minor or major)."""
        current_color = (self.current_minor_grid_color if grid_type == 'minor' 
                        else self.current_major_grid_color)
        button = (self.minor_grid_color_button if grid_type == 'minor' 
                 else self.major_grid_color_button)
        
        color = QColorDialog.getColor(current_color, self, f"Select {grid_type.title()} Grid Color")
        if color.isValid():
            if grid_type == 'minor':
                self.current_minor_grid_color = color
            else:
                self.current_major_grid_color = color
            self._update_color_button_style(button, color)
            
    def get_settings(self) -> Dict[str, Any]:
        """Return the current settings."""
        return {
            'grid_visible': self.grid_visible_cb.isChecked(),
            'minor_grid_color': self.current_minor_grid_color.name(),
            'major_grid_color': self.current_major_grid_color.name(),
            'app_font_size': self.app_font_size_spinbox.value()
        }
        
    def reset_to_defaults(self):
        """Reset settings to default values."""
        self.grid_visible_cb.setChecked(True)
        
        # Reset grid colors
        minor_color = QColor(COLOR_GRID_MINOR)
        major_color = QColor(COLOR_GRID_MAJOR)
        
        self.current_minor_grid_color = minor_color
        self.current_major_grid_color = major_color
        
        self._update_color_button_style(self.minor_grid_color_button, minor_color)
        self._update_color_button_style(self.major_grid_color_button, major_color)
        
        # Reset font size
        self.app_font_size_spinbox.setValue(9)


class GeneralSettingsTab(QWidget):
    """Tab widget for general application settings."""
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.initial_settings = self._get_current_general_settings()
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # File handling group
        file_group = QGroupBox("File Handling")
        file_layout = QFormLayout(file_group)
        
        self.auto_save_cb = QCheckBox("Enable Auto-save")
        self.auto_save_cb.setChecked(self.initial_settings['auto_save_enabled'])
        file_layout.addRow(self.auto_save_cb)
        
        self.auto_save_interval_spin = QSpinBox()
        self.auto_save_interval_spin.setRange(1, 60)
        self.auto_save_interval_spin.setValue(self.initial_settings['auto_save_interval'])
        self.auto_save_interval_spin.setSuffix(" minutes")
        self.auto_save_interval_spin.setEnabled(self.auto_save_cb.isChecked())
        self.auto_save_cb.toggled.connect(self.auto_save_interval_spin.setEnabled)
        file_layout.addRow("Auto-save Interval:", self.auto_save_interval_spin)
        
        self.backup_on_save_cb = QCheckBox("Create backup on save")
        self.backup_on_save_cb.setChecked(self.initial_settings['backup_on_save'])
        file_layout.addRow(self.backup_on_save_cb)
        
        layout.addWidget(file_group)
        
        # Editor behavior group
        editor_group = QGroupBox("Editor Behavior")
        editor_layout = QFormLayout(editor_group)
        
        self.snap_to_grid_cb = QCheckBox("Snap to grid when moving items")
        self.snap_to_grid_cb.setChecked(self.initial_settings['snap_to_grid'])
        editor_layout.addRow(self.snap_to_grid_cb)
        
        self.show_rulers_cb = QCheckBox("Show rulers")
        self.show_rulers_cb.setChecked(self.initial_settings['show_rulers'])
        editor_layout.addRow(self.show_rulers_cb)
        
        self.zoom_sensitivity_spin = QSpinBox()
        self.zoom_sensitivity_spin.setRange(1, 10)
        self.zoom_sensitivity_spin.setValue(self.initial_settings['zoom_sensitivity'])
        editor_layout.addRow("Zoom Sensitivity:", self.zoom_sensitivity_spin)
        
        layout.addWidget(editor_group)
        
        # Export settings group
        export_group = QGroupBox("Export Settings")
        export_layout = QFormLayout(export_group)
        
        self.default_export_format_combo = QComboBox()
        self.default_export_format_combo.addItems(["PNG", "SVG", "PDF", "MATLAB"])
        current_format = self.initial_settings['default_export_format']
        index = self.default_export_format_combo.findText(current_format)
        if index >= 0:
            self.default_export_format_combo.setCurrentIndex(index)
        export_layout.addRow("Default Export Format:", self.default_export_format_combo)
        
        self.export_dpi_spin = QSpinBox()
        self.export_dpi_spin.setRange(72, 600)
        self.export_dpi_spin.setValue(self.initial_settings['export_dpi'])
        self.export_dpi_spin.setSuffix(" DPI")
        export_layout.addRow("Export Image DPI:", self.export_dpi_spin)
        
        layout.addWidget(export_group)
        
        layout.addStretch()
        
    def _get_current_general_settings(self) -> Dict[str, Any]:
        """Get current general settings with fallbacks."""
        settings_qt = QSettings(APP_NAME, "GeneralSettings")
        
        return {
            'auto_save_enabled': settings_qt.value("auto_save_enabled", False, type=bool),
            'auto_save_interval': settings_qt.value("auto_save_interval", 5, type=int),
            'backup_on_save': settings_qt.value("backup_on_save", True, type=bool),
            'snap_to_grid': settings_qt.value("snap_to_grid", True, type=bool),
            'show_rulers': settings_qt.value("show_rulers", False, type=bool),
            'zoom_sensitivity': settings_qt.value("zoom_sensitivity", 3, type=int),
            'default_export_format': settings_qt.value("default_export_format", "PNG", type=str),
            'export_dpi': settings_qt.value("export_dpi", 300, type=int)
        }
        
    def get_settings(self) -> Dict[str, Any]:
        """Return the current settings."""
        return {
            'auto_save_enabled': self.auto_save_cb.isChecked(),
            'auto_save_interval': self.auto_save_interval_spin.value(),
            'backup_on_save': self.backup_on_save_cb.isChecked(),
            'snap_to_grid': self.snap_to_grid_cb.isChecked(),
            'show_rulers': self.show_rulers_cb.isChecked(),
            'zoom_sensitivity': self.zoom_sensitivity_spin.value(),
            'default_export_format': self.default_export_format_combo.currentText(),
            'export_dpi': self.export_dpi_spin.value()
        }
        
    def reset_to_defaults(self):
        """Reset settings to default values."""
        self.auto_save_cb.setChecked(False)
        self.auto_save_interval_spin.setValue(5)
        self.backup_on_save_cb.setChecked(True)
        self.snap_to_grid_cb.setChecked(True)
        self.show_rulers_cb.setChecked(False)
        self.zoom_sensitivity_spin.setValue(3)
        self.default_export_format_combo.setCurrentText("PNG")
        self.export_dpi_spin.setValue(300)


class PreferencesDialog(QDialog):
    """Main preferences dialog with tabbed interface."""
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Preferences")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailView, "Pref"))
        self.setMinimumSize(600, 500)
        self.resize(650, 550)
        
        # Track if settings changed
        self.settings_changed = False
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Add tabs
        self.appearance_tab = AppearanceSettingsTab(self.main_window, self)
        self.general_tab = GeneralSettingsTab(self.main_window, self)
        
        self.tab_widget.addTab(self.appearance_tab, 
                              get_standard_icon(QStyle.SP_DesktopIcon, "App"), "Appearance")
        self.tab_widget.addTab(self.general_tab, 
                              get_standard_icon(QStyle.SP_ComputerIcon, "Gen"), "General")
        
        layout.addWidget(self.tab_widget)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        reset_button = QPushButton("Reset to Defaults")
        reset_button.setIcon(get_standard_icon(QStyle.SP_BrowserReload, "Rst"))
        reset_button.clicked.connect(self._reset_current_tab)
        reset_button.setToolTip("Reset current tab to default settings")
        
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        
        dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        dialog_buttons.button(QDialogButtonBox.Ok).setText("OK")
        dialog_buttons.button(QDialogButtonBox.Apply).setText("Apply")
        dialog_buttons.accepted.connect(self._apply_and_accept)
        dialog_buttons.rejected.connect(self.reject)
        dialog_buttons.button(QDialogButtonBox.Apply).clicked.connect(self._apply_settings)
        
        button_layout.addWidget(dialog_buttons)
        layout.addLayout(button_layout)
        
    def _connect_signals(self):
        """Connect signals for change tracking."""
        # We could add change tracking here if needed
        pass
        
    def _reset_current_tab(self):
        """Reset the current tab to defaults."""
        current_index = self.tab_widget.currentIndex()
        if current_index == 0:  # Appearance tab
            self.appearance_tab.reset_to_defaults()
        elif current_index == 1:  # General tab
            self.general_tab.reset_to_defaults()
            
    def _apply_settings(self):
        """Apply all settings without closing dialog."""
        self._save_appearance_settings()
        self._save_general_settings()
        self.settings_changed = True
        
    def _apply_and_accept(self):
        """Apply settings and close dialog."""
        self._apply_settings()
        self.accept()
        
    def _save_appearance_settings(self):
        """Save appearance settings."""
        settings = self.appearance_tab.get_settings()
        settings_qt = QSettings(APP_NAME, "AppearanceSettings")
        
        for key, value in settings.items():
            settings_qt.setValue(key, value)
            
        # Apply grid settings immediately
        scene = self.main_window.scene
        scene.set_grid_visible(settings['grid_visible'])
        scene.update_grid_colors(settings['minor_grid_color'], settings['major_grid_color'])
        
        # Apply font settings
        current_font = QApplication.instance().font()
        if current_font.pointSize() != settings['app_font_size']:
            new_font = QFont(APP_FONT_FAMILY, settings['app_font_size'])
            QApplication.instance().setFont(new_font)
            
    def _save_general_settings(self):
        """Save general settings."""
        settings = self.general_tab.get_settings()
        settings_qt = QSettings(APP_NAME, "GeneralSettings")
        
        for key, value in settings.items():
            settings_qt.setValue(key, value)
            
        # Apply settings to main window
        if hasattr(self.main_window, 'apply_general_settings'):
            self.main_window.apply_general_settings(settings)


class ExportDialog(QDialog):
    """Dialog for export settings and options."""
    
    def __init__(self, parent=None, suggested_filename: str = "", 
                 default_format: str = "PNG"):
        super().__init__(parent)
        self.setWindowTitle("Export Diagram")
        self.setWindowIcon(get_standard_icon(QStyle.SP_DialogSaveButton, "Exp"))
        self.setMinimumWidth(500)
        
        self.export_settings = {}
        self._setup_ui(suggested_filename, default_format)
        
    def _setup_ui(self, suggested_filename: str, default_format: str):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # File selection group
        file_group = QGroupBox("Export File")
        file_layout = QFormLayout(file_group)
        
        self.filename_edit = QLineEdit(suggested_filename)
        self.filename_edit.setPlaceholderText("Enter filename...")
        
        browse_layout = QHBoxLayout()
        browse_layout.addWidget(self.filename_edit, 1)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.setIcon(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"))
        browse_btn.clicked.connect(self._browse_file)
        browse_layout.addWidget(browse_btn)
        
        file_layout.addRow("Filename:", browse_layout)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "SVG", "PDF", "MATLAB"])
        index = self.format_combo.findText(default_format)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
        self.format_combo.currentTextChanged.connect(self._format_changed)
        file_layout.addRow("Format:", self.format_combo)
        
        layout.addWidget(file_group)
        
        # Format-specific options group
        self.options_group = QGroupBox("Export Options")
        self.options_layout = QFormLayout(self.options_group)
        
        # Image options (PNG/PDF)
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" DPI")
        self.dpi_row = self.options_layout.addRow("Resolution:", self.dpi_spin)
        
        self.transparent_bg_cb = QCheckBox("Transparent background")
        self.transparent_bg_cb.setChecked(True)
        self.bg_row = self.options_layout.addRow(self.transparent_bg_cb)
        
        # MATLAB options
        self.matlab_format_combo = QComboBox()
        self.matlab_format_combo.addItems(["Stateflow", "State Machine Toolbox", "Custom Script"])
        self.matlab_row = self.options_layout.addRow("MATLAB Target:", self.matlab_format_combo)
        
        self.include_comments_cb = QCheckBox("Include comments in export")
        self.include_comments_cb.setChecked(True)
        self.comments_row = self.options_layout.addRow(self.include_comments_cb)
        
        layout.addWidget(self.options_group)
        
        # Area selection group
        area_group = QGroupBox("Export Area")
        area_layout = QFormLayout(area_group)
        
        self.area_combo = QComboBox()
        self.area_combo.addItems(["Entire Diagram", "Visible Area", "Selected Items Only"])
        area_layout.addRow("Export:", self.area_combo)
        
        layout.addWidget(area_group)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Export")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Initialize format-specific visibility
        self._format_changed(default_format)
        
    def _browse_file(self):
        """Browse for export file location."""
        current_format = self.format_combo.currentText()
        
        if current_format == "PNG":
            filter_str = "PNG Images (*.png);;All Files (*)"
            default_ext = ".png"
        elif current_format == "SVG":
            filter_str = "SVG Images (*.svg);;All Files (*)"
            default_ext = ".svg"
        elif current_format == "PDF":
            filter_str = "PDF Documents (*.pdf);;All Files (*)"
            default_ext = ".pdf"
        else:  # MATLAB
            filter_str = "MATLAB Files (*.m);;All Files (*)"
            default_ext = ".m"
            
        current_name = self.filename_edit.text()
        if not current_name.endswith(default_ext):
            current_name += default_ext
            
        filename, _ = QFileDialog.getSaveFileName(
            self, f"Export as {current_format}", current_name, filter_str
        )
        
        if filename:
            self.filename_edit.setText(filename)
            
    def _format_changed(self, format_name: str):
        """Update options visibility based on selected format."""
        is_image = format_name in ["PNG", "PDF"]
        is_matlab = format_name == "MATLAB"
        
        # Show/hide image options
        self.dpi_spin.setVisible(is_image)
        self.options_layout.labelForField(self.dpi_spin).setVisible(is_image)
        self.transparent_bg_cb.setVisible(format_name == "PNG")
        
        # Show/hide MATLAB options
        self.matlab_format_combo.setVisible(is_matlab)
        self.options_layout.labelForField(self.matlab_format_combo).setVisible(is_matlab)
        self.include_comments_cb.setVisible(is_matlab)
        
    def _validate_and_accept(self):
        """Validate inputs and accept dialog."""
        filename = self.filename_edit.text().strip()
        if not filename:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export Error", "Please specify a filename.")
            return
            
        self.export_settings = self.get_export_settings()
        self.accept()
        
    def get_export_settings(self) -> Dict[str, Any]:
        """Return current export settings."""
        format_name = self.format_combo.currentText()
        
        settings = {
            'filename': self.filename_edit.text().strip(),
            'format': format_name,
            'export_area': self.area_combo.currentText()
        }
        
        if format_name in ["PNG", "PDF"]:
            settings['dpi'] = self.dpi_spin.value()
            if format_name == "PNG":
                settings['transparent_background'] = self.transparent_bg_cb.isChecked()
        elif format_name == "MATLAB":
            settings['matlab_target'] = self.matlab_format_combo.currentText()
            settings['include_comments'] = self.include_comments_cb.isChecked()
            
        return settings


class AboutDialog(QDialog):
    """About dialog showing application information."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setWindowIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Abt"))
        self.setFixedSize(480, 320)
        self.setModal(True)
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # App icon and title
        title_layout = QHBoxLayout()
        title_layout.setSpacing(15)
        
        # Large app icon
        icon_label = QLabel()
        app_icon = get_standard_icon(QStyle.SP_ComputerIcon, "App")
        icon_label.setPixmap(app_icon.pixmap(QSize(64, 64)))
        icon_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(icon_label)
        
        # Title and version info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        app_title = QLabel(f"<h2>{APP_NAME}</h2>")
        app_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        info_layout.addWidget(app_title)
        
        version_label = QLabel("<b>Version 1.0.0</b>")
        version_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        info_layout.addWidget(version_label)
        
        subtitle_label = QLabel("State Machine Diagram Editor")
        subtitle_label.setStyleSheet("color: #666666;")
        subtitle_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        info_layout.addWidget(subtitle_label)
        
        title_layout.addLayout(info_layout, 1)
        layout.addLayout(title_layout)
        
        # Description
        description = QLabel(
            f"{APP_NAME} is a professional state machine diagram editor designed for "
            "mechatronics and embedded systems development. Create, edit, and export "
            "state diagrams with MATLAB integration support."
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignJustify)
        layout.addWidget(description)
        
        # Features list
        features_label = QLabel("<b>Key Features:</b>")
        layout.addWidget(features_label)
        
        features_text = QLabel(
            "• Visual state machine editor with intuitive interface\n"
            "• MATLAB Stateflow integration and code generation\n"
            "• Export to PNG, SVG, PDF, and MATLAB formats\n"
            "• Customizable appearance and grid system\n"
            "• Built-in snippet library for common patterns\n"
            "• Professional diagram layout and styling"
        )
        features_text.setStyleSheet("margin-left: 10px;")
        layout.addWidget(features_text)
        
        layout.addStretch()
        
        # Copyright and close button
        copyright_label = QLabel("© 2024 State Machine Designer. All rights reserved.")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet("color: #888888; font-size: 9pt;")
        layout.addWidget(copyright_label)
        
        close_button = QPushButton("Close")
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)


if __name__ == "__main__":
    # Simple test of dialogs
    app = QApplication(sys.argv)
    
    # Test state properties dialog
    state_dialog = StatePropertiesDialog(is_new_state=True)
    if state_dialog.exec_() == QDialog.Accepted:
        print("State properties:", state_dialog.get_properties())
        
    # Test transition properties dialog  
    transition_dialog = TransitionPropertiesDialog(is_new_transition=True)
    if transition_dialog.exec_() == QDialog.Accepted:
        print("Transition properties:", transition_dialog.get_properties())
        
    sys.exit(0)