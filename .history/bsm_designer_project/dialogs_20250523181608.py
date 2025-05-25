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

    def create_color_button(self, initial_color: str) -> tuple[QPushButton, QColor]:
        """Create a color selection button with proper styling."""
        button = QPushButton(initial_color)
        button.setObjectName("ColorButton")
        color_obj = QColor(initial_color)
        self._update_color_button_style(button, color_obj)
        return button, color_obj

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

        self.name_edit = QLineEdit(p.get('name', "StateName"))
        self.name_edit.setPlaceholderText("Unique name for the state")

        self.is_initial_cb = QCheckBox("Is Initial State")
        self.is_initial_cb.setChecked(p.get('is_initial', False))

        self.is_final_cb = QCheckBox("Is Final State")
        self.is_final_cb.setChecked(p.get('is_final', False))

        self.color_button, self.current_color = self.create_color_button(
            p.get('color', COLOR_ITEM_STATE_DEFAULT_BG)
        )
        self.color_button.clicked.connect(self._choose_color)

        self.entry_action_edit = self._create_action_textedit(
            p.get('entry_action', ""), "Actions on entry..."
        )
        self.during_action_edit = self._create_action_textedit(
            p.get('during_action', ""), "Actions during state..."
        )
        self.exit_action_edit = self._create_action_textedit(
            p.get('exit_action', ""), "Actions on exit..."
        )

        self.description_edit = QTextEdit(p.get('description', ""))
        self.description_edit.setFixedHeight(75)
        self.description_edit.setPlaceholderText("Optional notes about this state")

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
        edit = QTextEdit(text)
        edit.setFixedHeight(65)
        edit.setPlaceholderText(placeholder)
        return edit

    def _setup_layout(self, layout: QFormLayout):
        layout.addRow("Name:", self.name_edit)

        cb_layout = QHBoxLayout()
        cb_layout.addWidget(self.is_initial_cb)
        cb_layout.addWidget(self.is_final_cb)
        cb_layout.addStretch()
        layout.addRow("", cb_layout)

        layout.addRow("Color:", self.color_button)

        self.add_field_with_button(layout, "Entry Action:",
                                 self.entry_action_edit, self.entry_action_btn)
        self.add_field_with_button(layout, "During Action:",
                                 self.during_action_edit, self.during_action_btn)
        self.add_field_with_button(layout, "Exit Action:",
                                 self.exit_action_edit, self.exit_action_btn)

        layout.addRow("Description:", self.description_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _choose_color(self):
        chosen_color = QColorDialog.getColor(self.current_color, self, "Select State Color")
        if chosen_color.isValid():
            self.current_color = chosen_color
            self._update_color_button_style(self.color_button, self.current_color)

    def get_properties(self) -> Dict[str, Any]:
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
        p = self.properties

        self.event_edit = QLineEdit(p.get('event', ""))
        self.event_edit.setPlaceholderText("e.g., timeout, button_press(ID)")

        self.condition_edit = QLineEdit(p.get('condition', ""))
        self.condition_edit.setPlaceholderText("e.g., var_x > 10 && flag")

        self.action_edit = QTextEdit(p.get('action', ""))
        self.action_edit.setPlaceholderText("Actions on transition...")
        self.action_edit.setFixedHeight(65)

        self.color_button, self.current_color = self.create_color_button(
            p.get('color', COLOR_ITEM_TRANSITION_DEFAULT)
        )
        self.color_button.clicked.connect(self._choose_color)

        self.offset_perp_spin = self._create_offset_spinbox(
            p.get('control_offset_x', 0), "Perpendicular bend of curve."
        )
        self.offset_tang_spin = self._create_offset_spinbox(
            p.get('control_offset_y', 0), "Tangential shift of curve midpoint."
        )

        self.description_edit = QTextEdit(p.get('description', ""))
        self.description_edit.setFixedHeight(75)
        self.description_edit.setPlaceholderText("Optional notes")

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
        spinbox = QSpinBox()
        spinbox.setRange(-1000, 1000)
        spinbox.setSingleStep(10)
        spinbox.setValue(int(value))
        spinbox.setToolTip(tooltip)
        return spinbox

    def _setup_layout(self, layout: QFormLayout):
        self.add_field_with_button(layout, "Event Trigger:",
                                 self.event_edit, self.event_btn)
        self.add_field_with_button(layout, "Condition (Guard):",
                                 self.condition_edit, self.condition_btn)
        self.add_field_with_button(layout, "Transition Action:",
                                 self.action_edit, self.action_btn)

        layout.addRow("Color:", self.color_button)

        curve_layout = QHBoxLayout()
        curve_layout.addWidget(QLabel("Bend (Perp):"))
        curve_layout.addWidget(self.offset_perp_spin)
        curve_layout.addSpacing(10)
        curve_layout.addWidget(QLabel("Mid Shift (Tang):"))
        curve_layout.addWidget(self.offset_tang_spin)
        curve_layout.addStretch()
        layout.addRow("Curve Shape:", curve_layout)

        layout.addRow("Description:", self.description_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _choose_color(self):
        chosen_color = QColorDialog.getColor(self.current_color, self, "Select Transition Color")
        if chosen_color.isValid():
            self.current_color = chosen_color
            self._update_color_button_style(self.color_button, self.current_color)

    def get_properties(self) -> Dict[str, Any]:
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
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        path_group = QGroupBox("MATLAB Executable Path")
        path_form_layout = QFormLayout()
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path)
        self.path_edit.setPlaceholderText("e.g., C:\\...\\MATLAB\\R202Xy\\bin\\matlab.exe")
        path_form_layout.addRow("Path:", self.path_edit)

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

        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close")
        dialog_buttons.accepted.connect(self._apply_settings)
        dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)

    def _connect_signals(self):
        self.matlab_connection.connectionStatusChanged.connect(
            self._update_test_label_from_signal
        )

    def _update_initial_status(self):
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
        self.test_status_label.setText("Status: Auto-detecting MATLAB...")
        QApplication.processEvents()
        self.matlab_connection.detect_matlab()

    def _browse(self):
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
        path = self.path_edit.text().strip()
        if not path:
            self._update_test_label_from_signal(False, "MATLAB path is empty.")
            return
        self.test_status_label.setText("Status: Testing connection...")
        QApplication.processEvents()
        if self.matlab_connection.set_matlab_path(path):
            self.matlab_connection.test_connection()

    def _update_test_label_from_signal(self, success: bool, message: str):
        status_prefix = "Status: "
        style = "font-weight:bold;padding:3px;"
        if success:
            if "path set" in message: status_prefix = "Status: Path valid. "
            elif "test successful" in message: status_prefix = "Status: Connected! "
            style += "color:#2E7D32;"
        else:
            status_prefix = "Status: Error. "
            style += "color:#C62828;"
        self.test_status_label.setText(status_prefix + message)
        self.test_status_label.setStyleSheet(style)
        if success and self.matlab_connection.matlab_path and not self.path_edit.text():
            self.path_edit.setText(self.matlab_connection.matlab_path)

    def _apply_settings(self):
        path = self.path_edit.text().strip()
        if self.matlab_connection.matlab_path != path:
            self.matlab_connection.set_matlab_path(path)
            if path and not self.matlab_connection.connected:
                self.matlab_connection.test_connection()
        self.accept()


class AppearanceSettingsTab(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.initial_settings = self._get_current_app_settings()

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)

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

        font_group = QGroupBox("Application Font")
        font_layout = QFormLayout(font_group)
        self.app_font_size_spinbox = QSpinBox()
        self.app_font_size_spinbox.setRange(7, 16)
        self.app_font_size_spinbox.setValue(self.initial_settings['app_font_size'])
        self.app_font_size_spinbox.setSuffix(" pt")
        font_layout.addRow("Base Font Size:", self.app_font_size_spinbox)
        font_layout.addRow(QLabel("<small><i>Note: A restart may be needed for all font changes to fully apply.</i></small>"))
        layout.addWidget(font_group)

        layout.addStretch()

    def _get_current_app_settings(self):
        settings_qt = QSettings(APP_NAME, "AppearanceSettings")
        scene = self.main_window.scene
        default_font_size = 9
        app_font = QApplication.instance().font()
        if app_font.pointSize() > 0:
            default_font_size = app_font.pointSize()
        elif app_font.pixelSize() > 0 and self.logicalDpiY() > 0:
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
        button.setText(color.name())

    def _choose_grid_color(self, grid_type_str):
        button, current_color_attr_name = (self.minor_grid_color_button, 'current_minor_grid_color') if grid_type_str == 'minor' \
                                       else (self.major_grid_color_button, 'current_major_grid_color')
        title = "Select Minor Grid Color" if grid_type_str == 'minor' else "Select Major Grid Color"
        chosen_color = QColorDialog.getColor(getattr(self, current_color_attr_name), self, title)
        if chosen_color.isValid():
            setattr(self, current_color_attr_name, chosen_color)
            self._update_color_button_style(button, chosen_color)

    def get_settings_data(self):
        return {
            'grid_visible': self.grid_visible_cb.isChecked(),
            'minor_grid_color': self.current_minor_grid_color.name(),
            'major_grid_color': self.current_major_grid_color.name(),
            'app_font_size': self.app_font_size_spinbox.value()
        }

    def apply_specific_settings(self, data):
        scene = self.main_window.scene
        settings_qt = QSettings(APP_NAME, "AppearanceSettings")
        scene.grid_visible = data['grid_visible']
        settings_qt.setValue("grid_visible", scene.grid_visible)
        scene.grid_pen_light.setColor(QColor(data['minor_grid_color']))
        settings_qt.setValue("minor_grid_color", data['minor_grid_color'])
        scene.grid_pen_dark.setColor(QColor(data['major_grid_color']))
        settings_qt.setValue("major_grid_color", data['major_grid_color'])
        scene.update()
        current_app_font_size = QApplication.instance().font().pointSize()
        if current_app_font_size <=0: current_app_font_size = 9
        new_font_size = data['app_font_size']
        settings_qt.setValue("app_font_size", new_font_size)
        if current_app_font_size != new_font_size:
            font = QApplication.instance().font()
            font.setPointSize(new_font_size)
            QApplication.instance().setFont(font)
            self.main_window.setStyleSheet("")
            self.main_window.setStyleSheet(self.main_window.global_style_sheet_template)
            from graphics_items import GraphicsStateItem, GraphicsTransitionItem # Local import
            for item in scene.items():
                if hasattr(item, 'font') and callable(getattr(item,'setFont', None)):
                    item_font = item.font()
                    if isinstance(item, GraphicsStateItem): item_font.setPointSize(new_font_size -1 if new_font_size > 8 else 7)
                    elif isinstance(item, GraphicsTransitionItem): item_font.setPointSize(new_font_size -2 if new_font_size > 9 else 7)
                    else: item_font.setPointSize(new_font_size)
                    item.setFont(item_font)
            scene.update()
        self.initial_settings = data.copy()


class PreferencesDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle(f"{APP_NAME} - Preferences")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Settings"))
        self.setMinimumSize(550, 450)
        self.settings_changed = False

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()

        self.appearance_tab = AppearanceSettingsTab(self.main_window, self)
        self.tab_widget.addTab(self.appearance_tab, "Appearance")

        self.ai_settings_tab_widget = self._create_ai_settings_tab()
        self.tab_widget.addTab(self.ai_settings_tab_widget, "AI Assistant")

        if hasattr(self.main_window, 'matlab_connection'):
            self.matlab_settings_tab_widget = self._create_matlab_settings_tab()
            self.tab_widget.addTab(self.matlab_settings_tab_widget, "MATLAB")

        main_layout.addWidget(self.tab_widget)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
        self.buttons.button(QDialogButtonBox.Ok).setText("Apply & Close")
        self.buttons.button(QDialogButtonBox.Apply).setText("Apply")
        self.buttons.accepted.connect(self._apply_and_accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply_all_settings)
        main_layout.addWidget(self.buttons)

    def _create_ai_settings_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(10,10,10,10); layout.setSpacing(8)
        settings_qt = QSettings(APP_NAME, "AISettings")

        # Get API key from QSettings (persisted value) or default to empty string
        current_api_key = settings_qt.value("api_key", "", type=str)

        self.api_key_edit_tab = QLineEdit(current_api_key)
        self.api_key_edit_tab.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.api_key_edit_tab.setPlaceholderText("Enter your OpenAI API Key")
        layout.addRow("OpenAI API Key:", self.api_key_edit_tab)

        self.model_name_combo_tab = QComboBox()
        self.model_name_combo_tab.addItems(["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"])

        default_model_from_manager = "gpt-3.5-turbo"
        if self.main_window.ai_chatbot_manager and self.main_window.ai_chatbot_manager.config:
            default_model_from_manager = self.main_window.ai_chatbot_manager.config.model_name

        current_model = settings_qt.value("model_name", default_model_from_manager, type=str)
        self.model_name_combo_tab.setCurrentText(current_model)
        self.model_name_combo_tab.setEditable(True)
        layout.addRow("Chat Model:", self.model_name_combo_tab)
        layout.addRow(QLabel("<small><i>API key changes apply immediately. Model changes apply on next chat request or app restart.</i></small>"))
        return widget

    def _create_matlab_settings_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(10,10,10,10); layout.setSpacing(8)
        settings_qt = QSettings(APP_NAME, "MATLABSettings")
        current_matlab_path = settings_qt.value("path", self.main_window.matlab_connection.matlab_path or "", type=str)
        self.matlab_path_edit_tab = QLineEdit(current_matlab_path)
        self.matlab_path_edit_tab.setPlaceholderText("e.g., C:\\...\\MATLAB\\R202Xy\\bin\\matlab.exe")
        path_browse_layout = QHBoxLayout(); path_browse_layout.addWidget(self.matlab_path_edit_tab, 1)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), " Browse...")
        browse_btn.clicked.connect(self._browse_matlab_path_tab)
        path_browse_layout.addWidget(browse_btn)
        layout.addRow("MATLAB Executable Path:", path_browse_layout)
        auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_BrowserReload,"Det"), " Auto-detect Path")
        auto_detect_btn.clicked.connect(self._auto_detect_matlab_path_tab)
        layout.addRow("", auto_detect_btn)
        self.matlab_test_status_label_tab = QLabel(f"Path: {current_matlab_path or 'Not set'}")
        layout.addRow(self.matlab_test_status_label_tab)
        return widget

    def _browse_matlab_path_tab(self):
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        start_dir = QDir.homePath()
        if self.matlab_path_edit_tab.text() and QDir(QDir.toNativeSeparators(self.matlab_path_edit_tab.text())).exists():
             path_obj = QDir(self.matlab_path_edit_tab.text()); path_obj.cdUp(); start_dir = path_obj.absolutePath()
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path: self.matlab_path_edit_tab.setText(path); self.matlab_test_status_label_tab.setText(f"Path changed to: {path}")

    def _auto_detect_matlab_path_tab(self):
        self.matlab_test_status_label_tab.setText("Auto-detecting...")
        QApplication.processEvents()
        if self.main_window.matlab_connection.detect_matlab():
            detected_path = self.main_window.matlab_connection.matlab_path
            self.matlab_path_edit_tab.setText(detected_path)
            self.matlab_test_status_label_tab.setText(f"Detected: {detected_path}")
        else:
            self.matlab_test_status_label_tab.setText("Auto-detection failed.")

    def apply_all_settings(self):
        # Appearance Settings
        appearance_data = self.appearance_tab.get_settings_data()
        self.appearance_tab.apply_specific_settings(appearance_data)
        settings_appr_qt = QSettings(APP_NAME, "AppearanceSettings")
        for key, value in appearance_data.items(): settings_appr_qt.setValue(key, value)

        # AI Settings
        ai_settings_qt = QSettings(APP_NAME, "AISettings")
        new_api_key = self.api_key_edit_tab.text().strip()
        ai_settings_qt.setValue("api_key", new_api_key)

        # Get current API key from the manager's stored property
        current_manager_api_key = self.main_window.ai_chatbot_manager.api_key or ""

        if current_manager_api_key != new_api_key:
            self.main_window.ai_chatbot_manager.set_api_key(new_api_key or None)

        new_model_name = self.model_name_combo_tab.currentText().strip()
        ai_settings_qt.setValue("model_name", new_model_name)
        if self.main_window.ai_chatbot_manager.config.model_name != new_model_name:
            self.main_window.ai_chatbot_manager.update_config({'model_name': new_model_name})
            self.main_window.log_message(f"AI Chat Model set to: {new_model_name}.", type_hint="AI_CONFIG")
        # If API key was newly set (and was not empty), ensure worker gets the current model.
        # The set_api_key in manager already re-creates worker with current manager.config
        # So, an explicit update_config call here for model might be redundant if API key changed,
        # but harmless. It's important if ONLY model changed and API key was already set.

        # MATLAB Settings
        if hasattr(self, 'matlab_settings_tab_widget'):
            matlab_settings_qt = QSettings(APP_NAME, "MATLABSettings")
            new_matlab_path = self.matlab_path_edit_tab.text().strip()
            matlab_settings_qt.setValue("path", new_matlab_path)
            if self.main_window.matlab_connection.matlab_path != new_matlab_path:
                 if self.main_window.matlab_connection.set_matlab_path(new_matlab_path):
                     self.matlab_test_status_label_tab.setText(f"Path set to: {new_matlab_path if new_matlab_path else 'None'}. Test if needed.")
                 else:
                     self.matlab_test_status_label_tab.setText(f"Invalid path: {new_matlab_path}. Path not set.")

        self.settings_changed = True
        self.main_window.log_message("Preferences applied.", type_hint="CONFIG")

    def _apply_and_accept(self):
        self.apply_all_settings()
        self.accept()