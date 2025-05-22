
import sys
import os
import tempfile
import subprocess
import json
import html # Used for escaping in properties dock
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QToolBox, QAction,
    QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
    QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
    QFileDialog, QProgressBar, QTabWidget, QCheckBox, QActionGroup, QGraphicsItem,
    QGroupBox, QUndoStack, QUndoCommand, QStyle, QSizePolicy, QGraphicsLineItem,
    QToolButton, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent,
    QGraphicsSceneHoverEvent, QGraphicsTextItem, QGraphicsDropShadowEffect,
    QAbstractItemView
)
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform, QKeyEvent, QPainterPathStroker, QPolygonF, QKeySequence,
    QDesktopServices, QWheelEvent, QMouseEvent, QCloseEvent, QFontMetrics, QPalette,
    QImage, QPageSize # Added QImage, QPageSize
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QTimer, QSize, QTime, QUrl,
    QSaveFile, QIODevice
)
from PyQt5.QtSvg import QSvgGenerator # Added QSvgGenerator
from PyQt5.QtPrintSupport import QPrinter # Added QPrinter
import math


# --- Configuration ---
APP_VERSION = "1.6.2" # Added Diagram Export Feature
APP_NAME = "Brain State Machine Designer"
FILE_EXTENSION = ".bsm"
FILE_FILTER = f"Brain State Machine Files (*{FILE_EXTENSION});;All Files (*)"

# --- Mechatronics/Embedded Snippets --- (No change here)
MECHATRONICS_COMMON_ACTIONS = {
    "Digital Output (High)": "set_digital_output(PIN_NUMBER, 1); % Set pin HIGH",
    "Digital Output (Low)": "set_digital_output(PIN_NUMBER, 0); % Set pin LOW",
    "Read Digital Input": "input_value = read_digital_input(PIN_NUMBER);",
    "Set PWM Duty Cycle": "set_pwm_duty_cycle(PWM_CHANNEL, DUTY_VALUE_0_255);",
    "Read Analog Input": "sensor_value = read_adc_channel(ADC_CHANNEL);",
    "Start Timer": "start_software_timer(TIMER_ID, DURATION_MS);",
    "Stop Timer": "stop_software_timer(TIMER_ID);",
    "Increment Counter": "counter_variable = counter_variable + 1;",
    "Reset Counter": "counter_variable = 0;",
    "Set Variable": "my_variable = NEW_VALUE;",
    "Log Message": "log_event('Event description or variable_value');",
    "Send CAN Message": "send_can_message(CAN_ID, [BYTE1, BYTE2, BYTE3]);",
    "Set Motor Speed": "set_motor_speed(MOTOR_ID, SPEED_VALUE);",
    "Set Motor Position": "set_motor_position(MOTOR_ID, POSITION_TARGET);",
    "Open Solenoid Valve": "control_solenoid(VALVE_ID, VALVE_OPEN_CMD);",
    "Close Solenoid Valve": "control_solenoid(VALVE_ID, VALVE_CLOSE_CMD);",
    "Enable Component": "enable_subsystem(SUBSYSTEM_X, true);",
    "Disable Component": "enable_subsystem(SUBSYSTEM_X, false);",
    "Acknowledge Fault": "fault_acknowledged_flag = true;",
}

MECHATRONICS_COMMON_EVENTS = {
    "Timer Timeout": "timeout(TIMER_ID)",
    "Button Press": "button_pressed(BUTTON_NUMBER)",
    "Sensor Threshold Breach": "sensor_threshold(SENSOR_NAME)",
    "Data Packet Received": "data_reception_complete(CHANNEL)",
    "Emergency Stop Active": "emergency_stop",
    "Rising Edge Detection": "positive_edge(SIGNAL_NAME)",
    "Falling Edge Detection": "negative_edge(SIGNAL_NAME)",
    "Message Received": "msg_arrived(MSG_TYPE_ID)",
    "System Error Occurred": "system_fault(FAULT_CODE)",
    "User Input Event": "user_command(COMMAND_CODE)",
}

MECHATRONICS_COMMON_CONDITIONS = {
    "Is System Safe": "is_safety_interlock_active() == false",
    "Is Mode Nominal": "get_operating_mode() == NOMINAL_MODE",
    "Counter Reached Limit": "retry_counter >= MAX_RETRIES",
    "Variable is Value": "my_control_variable == TARGET_STATE_VALUE",
    "Flag is True": "is_ready_flag == true",
    "Flag is False": "is_busy_flag == false",
    "Battery Level OK": "get_battery_voltage_mv() > MINIMUM_OPERATING_VOLTAGE_MV",
    "Communication Healthy": "is_communication_link_up() == true",
    "Sensor Value In Range": "(sensor_data >= SENSOR_MIN_VALID && sensor_data <= SENSOR_MAX_VALID)",
    "Target Reached": "abs(current_position - target_position) < POSITION_TOLERANCE",
    "Input Signal High": "read_digital_input(PIN_FOR_CONDITION) == 1",
    "Input Signal Low": "read_digital_input(PIN_FOR_CONDITION) == 0",
}


# --- UI Styling and Theme Colors ---
COLOR_BACKGROUND_LIGHT = "#F5F5F5"
COLOR_BACKGROUND_MEDIUM = "#EEEEEE"
COLOR_BACKGROUND_DARK = "#E0E0E0"
COLOR_BACKGROUND_DIALOG = "#FFFFFF"

COLOR_TEXT_PRIMARY = "#212121"
COLOR_TEXT_SECONDARY = "#757575"
COLOR_TEXT_ON_ACCENT = "#FFFFFF"

COLOR_ACCENT_PRIMARY = "#1976D2"
COLOR_ACCENT_PRIMARY_LIGHT = "#BBDEFB"
COLOR_ACCENT_SECONDARY = "#FF8F00"
COLOR_ACCENT_SECONDARY_LIGHT = "#FFECB3"

COLOR_BORDER_LIGHT = "#CFD8DC"
COLOR_BORDER_MEDIUM = "#90A4AE"
COLOR_BORDER_DARK = "#607D8B"

COLOR_ITEM_STATE_DEFAULT_BG = "#E3F2FD"
COLOR_ITEM_STATE_DEFAULT_BORDER = "#90CAF9"
COLOR_ITEM_STATE_SELECTION = "#FFD54F"
COLOR_ITEM_TRANSITION_DEFAULT = "#009688"
COLOR_ITEM_TRANSITION_SELECTION = "#80CBC4"
COLOR_ITEM_COMMENT_BG = "#FFFDE7"
COLOR_ITEM_COMMENT_BORDER = "#FFF59D"
COLOR_GRID_MINOR = "#ECEFF1"
COLOR_GRID_MAJOR = "#CFD8DC"

APP_FONT_FAMILY = "Segoe UI, Arial, sans-serif"

# Global Stylesheet (QSS)
STYLE_SHEET_GLOBAL = f"""
    QWidget {{
        font-family: {APP_FONT_FAMILY};
        font-size: 9pt;
    }}
    QMainWindow {{
        background-color: {COLOR_BACKGROUND_LIGHT};
    }}
    QDockWidget::title {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        padding: 6px 8px;
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom: 2px solid {COLOR_ACCENT_PRIMARY};
        font-weight: bold;
        color: {COLOR_TEXT_PRIMARY};
    }}
    QDockWidget::close-button, QDockWidget::float-button {{
        subcontrol-position: top right;
        subcontrol-origin: margin;
        position: absolute;
        top: 0px; right: 5px;
    }}

    QToolBar {{
        background-color: {COLOR_BACKGROUND_DARK};
        border: none;
        padding: 3px;
        spacing: 4px;
    }}
    QToolBar QToolButton {{ /* General for ToolBar actions */
        background-color: transparent;
        color: {COLOR_TEXT_PRIMARY};
        padding: 5px 7px;
        margin: 1px;
        border: 1px solid transparent;
        border-radius: 4px;
    }}
    QToolBar QToolButton:hover {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QToolBar QToolButton:pressed {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}
    QToolBar QToolButton:checked {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
        border: 1px solid #0D47A1;
    }}

    QMenuBar {{
        background-color: {COLOR_BACKGROUND_DARK};
        color: {COLOR_TEXT_PRIMARY};
        border-bottom: 1px solid {COLOR_BORDER_LIGHT};
        padding: 2px;
    }}
    QMenuBar::item {{
        background-color: transparent;
        padding: 5px 12px;
    }}
    QMenuBar::item:selected {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QMenuBar::item:pressed {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}
    QMenu {{
        background-color: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 2px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 28px 6px 28px;
        border-radius: 3px;
    }}
    QMenu::item:selected {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}
    QMenu::separator {{
        height: 1px;
        background: {COLOR_BORDER_LIGHT};
        margin: 4px 8px;
    }}
    QMenu::icon {{
        padding-left: 5px;
    }}

    QStatusBar {{
        background-color: {COLOR_BACKGROUND_DARK};
        color: {COLOR_TEXT_PRIMARY};
        border-top: 1px solid {COLOR_BORDER_LIGHT};
        padding: 2px;
    }}
    QStatusBar::item {{
        border: none;
    }}
    QLabel#StatusLabel, QLabel#MatlabStatusLabel {{
         padding: 0px 5px;
    }}

    QDialog {{
        background-color: {COLOR_BACKGROUND_DIALOG};
    }}
    QLabel {{
        color: {COLOR_TEXT_PRIMARY};
        background-color: transparent;
    }}
    QLineEdit, QTextEdit, QSpinBox, QComboBox {{
        background-color: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 3px;
        padding: 5px 6px;
        font-size: 9pt;
    }}
    QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 22px;
        border-left-width: 1px;
        border-left-color: {COLOR_BORDER_MEDIUM};
        border-left-style: solid;
        border-top-right-radius: 3px;
        border-bottom-right-radius: 3px;
    }}
    QComboBox::down-arrow {{
        /* Removed explicit image, relying on native style */
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLOR_BACKGROUND_DIALOG};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        selection-background-color: {COLOR_ACCENT_PRIMARY};
        selection-color: {COLOR_TEXT_ON_ACCENT};
        padding: 2px;
        border-radius: 2px;
    }}

    QPushButton {{
        background-color: #E0E0E0;
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        padding: 6px 15px;
        border-radius: 3px;
        min-height: 20px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: #D6D6D6;
        border-color: {COLOR_BORDER_DARK};
    }}
    QPushButton:pressed {{
        background-color: #BDBDBD;
    }}
    QPushButton:disabled {{
        background-color: #F5F5F5;
        color: #BDBDBD;
        border-color: #EEEEEE;
    }}
    QDialogButtonBox QPushButton {{
        min-width: 85px;
    }}
    QDialogButtonBox QPushButton[text="OK"],
    QDialogButtonBox QPushButton[text="Apply & Close"],
    QDialogButtonBox QPushButton[text="Ok"] {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
        border-color: #0D47A1;
    }}
    QDialogButtonBox QPushButton[text="OK"]:hover,
    QDialogButtonBox QPushButton[text="Apply & Close"]:hover,
    QDialogButtonBox QPushButton[text="Ok"]:hover {{
        background-color: #1E88E5;
    }}

    QGroupBox {{
        background-color: {COLOR_BACKGROUND_LIGHT};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-radius: 5px;
        margin-top: 10px;
        padding: 10px 8px 8px 8px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        left: 10px;
        color: {COLOR_ACCENT_PRIMARY};
        font-weight: bold;
    }}

    QTabWidget::pane {{
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-radius: 4px;
        background-color: {COLOR_BACKGROUND_DIALOG};
        padding: 5px;
    }}
    QTabBar::tab {{
        background: {COLOR_BACKGROUND_DARK};
        color: {COLOR_TEXT_SECONDARY};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        padding: 7px 15px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
        border-color: {COLOR_BORDER_LIGHT};
        font-weight: bold;
    }}
    QTabBar::tab:!selected:hover {{
        background: {COLOR_ACCENT_PRIMARY_LIGHT};
        color: {COLOR_TEXT_PRIMARY};
    }}

    QCheckBox {{
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 15px;
        height: 15px;
    }}
    QCheckBox::indicator:unchecked {{
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 3px;
        background-color: {COLOR_BACKGROUND_DIALOG};
    }}
    QCheckBox::indicator:unchecked:hover {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QCheckBox::indicator:checked {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
        border-radius: 3px;
        background-color: {COLOR_ACCENT_PRIMARY};
    }}

    QTextEdit#LogOutputWidget {{
         font-family: Consolas, 'Courier New', monospace;
         background-color: #263238;
         color: #CFD8DC;
         border: 1px solid #37474F;
         border-radius: 3px;
         padding: 5px;
    }}
    QScrollBar:vertical {{
         border: 1px solid {COLOR_BORDER_LIGHT};
         background: {COLOR_BACKGROUND_LIGHT};
         width: 14px; margin: 0px;
    }}
    QScrollBar::handle:vertical {{
         background: {COLOR_BORDER_MEDIUM};
         min-height: 25px; border-radius: 7px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
         height: 0px; background: transparent;
    }}
    QScrollBar:horizontal {{
         border: 1px solid {COLOR_BORDER_LIGHT};
         background: {COLOR_BACKGROUND_LIGHT};
         height: 14px; margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
         background: {COLOR_BORDER_MEDIUM};
         min-width: 25px; border-radius: 7px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
         width: 0px; background: transparent;
    }}

    QPushButton#SnippetButton {{
        background-color: {COLOR_ACCENT_SECONDARY};
        color: {COLOR_TEXT_ON_ACCENT};
        border: 1px solid #E65100;
        font-weight: normal;
        icon-size: 14px;
        padding: 4px 8px;
        min-height: 18px;
    }}
    QPushButton#SnippetButton:hover {{
        background-color: #FFA000;
    }}

    QPushButton#ColorButton {{
        border: 1px solid {COLOR_BORDER_MEDIUM};
        min-height: 24px;
        padding: 3px;
    }}
    QPushButton#ColorButton:hover {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}

    QProgressBar {{
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 4px;
        background-color: {COLOR_BACKGROUND_LIGHT};
        text-align: center;
        color: {COLOR_TEXT_PRIMARY};
        height: 12px;
    }}
    QProgressBar::chunk {{
        background-color: {COLOR_ACCENT_PRIMARY};
        border-radius: 3px;
    }}

    QPushButton#DraggableToolButton {{
        background-color: #E8EAF6;
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid #C5CAE9;
        padding: 8px 10px 8px 10px;
        border-radius: 4px;
        text-align: left;
        font-weight: 500;
        icon-size: 18px;
    }}
    QPushButton#DraggableToolButton:hover {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
        border-color: {COLOR_ACCENT_PRIMARY};
    }}
    QPushButton#DraggableToolButton:pressed {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}

    #PropertiesDock QLabel {{
        padding: 8px;
        background-color: {COLOR_BACKGROUND_DIALOG};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-radius: 3px;
        line-height: 1.4;
    }}
    #PropertiesDock QPushButton {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
        icon-size: 16px;
    }}
    #PropertiesDock QPushButton:hover {{
        background-color: #1E88E5;
    }}

    QDockWidget#ToolsDock QToolButton {{
        padding: 7px 10px;
        text-align: left;
        icon-size: 18px;
        border-radius: 4px;
        border: 1px solid transparent;
    }}
     QDockWidget#ToolsDock QToolButton:hover {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
     QDockWidget#ToolsDock QToolButton:checked {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
        border: 1px solid #0D47A1;
    }}
    QDockWidget#ToolsDock QToolButton:pressed {{
        background-color: #1565C0;
        color: {COLOR_TEXT_ON_ACCENT};
    }}
"""


# --- Utility Functions ---
def get_standard_icon(standard_pixmap_enum_value, fallback_text=None, target_size=QSize(24, 24)):
    icon = QIcon()
    style = QApplication.style()
    if style:
        try:
            icon = style.standardIcon(standard_pixmap_enum_value)
        except Exception:
            pass

    if icon.isNull():
        pixmap = QPixmap(target_size)
        pixmap.fill(QColor(COLOR_BACKGROUND_MEDIUM))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        border_rect = QRectF(0.5, 0.5, target_size.width() - 1, target_size.height() - 1)
        painter.setPen(QPen(QColor(COLOR_BORDER_MEDIUM), 1))
        painter.drawRoundedRect(border_rect, 3, 3)

        if fallback_text:
            font_size_ratio = 0.4
            font_pixel_size = max(8, int(target_size.height() * font_size_ratio))
            font = QFont(APP_FONT_FAMILY, font_pixel_size, QFont.Bold if font_pixel_size > 10 else QFont.Normal)
            painter.setFont(font)
            painter.setPen(QColor(COLOR_TEXT_PRIMARY))
            display_text = fallback_text[:2].upper()
            if len(fallback_text) == 1: display_text = fallback_text[0].upper()
            elif len(fallback_text) > 1 and fallback_text[1].islower() and not fallback_text[0].isdigit():
                 display_text = fallback_text[0].upper()
            painter.drawText(pixmap.rect(), Qt.AlignCenter, display_text)
        else:
             painter.setPen(QPen(QColor(COLOR_ACCENT_PRIMARY), max(1, target_size.width() // 12) ))
             painter.setBrush(QColor(COLOR_ACCENT_PRIMARY))
             center_pt = pixmap.rect().center()
             radius = min(target_size.width(), target_size.height()) * 0.25
             painter.drawLine(center_pt + QPointF(0, -radius), center_pt + QPointF(0, radius))
             painter.drawLine(center_pt + QPointF(-radius, 0), center_pt + QPointF(radius, 0))
             if target_size.width() > 16:
                painter.drawLine(center_pt + QPointF(-radius*0.707, -radius*0.707), center_pt + QPointF(radius*0.707, radius*0.707))
                painter.drawLine(center_pt + QPointF(-radius*0.707, radius*0.707), center_pt + QPointF(radius*0.707, -radius*0.707))
        painter.end()
        return QIcon(pixmap)
    return icon


# --- MATLAB Connection Handling ---
class MatlabConnection(QObject):
    connectionStatusChanged = pyqtSignal(bool, str)
    simulationFinished = pyqtSignal(bool, str, str)
    codeGenerationFinished = pyqtSignal(bool, str, str)

    def __init__(self):
        super().__init__()
        self.matlab_path = ""
        self.connected = False
        self._active_threads = []

    def set_matlab_path(self, path):
        self.matlab_path = path.strip()
        if self.matlab_path and os.path.exists(self.matlab_path) and \
           (os.access(self.matlab_path, os.X_OK) or self.matlab_path.lower().endswith('.exe')):
            # Path seems structurally okay, but actual connection is tested separately.
            # We don't set self.connected = True here, test_connection does that.
            self.connectionStatusChanged.emit(True, f"MATLAB path set and appears valid: {self.matlab_path}")
            return True
        else:
            old_path = self.matlab_path
            self.connected = False # Definitely not connected if path is bad
            self.matlab_path = ""
            if old_path:
                self.connectionStatusChanged.emit(False, f"MATLAB path '{old_path}' is invalid or not executable.")
            else:
                self.connectionStatusChanged.emit(False, "MATLAB path cleared or not set.")
            return False

    def test_connection(self):
        if not self.matlab_path:
            self.connected = False
            self.connectionStatusChanged.emit(False, "MATLAB path not set. Cannot test connection.")
            return False
        # Ensure the current path is at least structurally valid first
        if not (os.path.exists(self.matlab_path) and \
                (os.access(self.matlab_path, os.X_OK) or self.matlab_path.lower().endswith('.exe'))):
            self.connected = False
            self.connectionStatusChanged.emit(False, f"MATLAB path '{self.matlab_path}' is invalid or not executable for test.")
            return False
        try:
            cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", "disp('MATLAB_CONNECTION_TEST_SUCCESS')"]
            process = subprocess.run(
                cmd, capture_output=True, text=True, timeout=20, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if process.returncode == 0 and "MATLAB_CONNECTION_TEST_SUCCESS" in process.stdout:
                self.connected = True
                self.connectionStatusChanged.emit(True, "MATLAB connection test successful.")
                return True
            else:
                self.connected = False
                error_msg = process.stderr or process.stdout or "Unexpected output or non-zero exit from MATLAB."
                if process.returncode != 0: error_msg = f"Exit Code {process.returncode}. {error_msg}"
                self.connectionStatusChanged.emit(False, f"MATLAB connection test failed: {error_msg[:250]}")
                return False
        except subprocess.TimeoutExpired:
            self.connected = False
            self.connectionStatusChanged.emit(False, "MATLAB connection test timed out (20s).")
            return False
        except FileNotFoundError:
            self.connected = False
            self.connectionStatusChanged.emit(False, f"MATLAB executable not found at: {self.matlab_path}")
            return False
        except Exception as e:
            self.connected = False
            self.connectionStatusChanged.emit(False, f"An unexpected error occurred during MATLAB test: {str(e)}")
            return False

    def detect_matlab(self):
        paths_to_check = []
        if sys.platform == 'win32':
            program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
            program_files_x86 = os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')
            matlab_bases = [os.path.join(program_files, 'MATLAB'), os.path.join(program_files_x86, 'MATLAB')]
            for matlab_base in matlab_bases:
                if os.path.isdir(matlab_base):
                    versions = sorted([d for d in os.listdir(matlab_base) if d.startswith('R20')], reverse=True)
                    for v_year_letter in versions:
                        paths_to_check.append(os.path.join(matlab_base, v_year_letter, 'bin', 'matlab.exe'))
            paths_to_check.append('matlab.exe')
            paths_to_check.append('matlab')
        elif sys.platform == 'darwin':
            base_app_path = '/Applications'
            potential_matlab_apps = sorted([d for d in os.listdir(base_app_path) if d.startswith('MATLAB_R20') and d.endswith('.app')], reverse=True)
            for app_name in potential_matlab_apps: paths_to_check.append(os.path.join(base_app_path, app_name, 'bin', 'matlab'))
            paths_to_check.append('matlab')
        else: # Linux / other Unix
            common_base_paths = ['/usr/local/MATLAB', '/opt/MATLAB']
            for base_path in common_base_paths:
                if os.path.isdir(base_path):
                    versions = sorted([d for d in os.listdir(base_path) if d.startswith('R20')], reverse=True)
                    for v_year_letter in versions: paths_to_check.append(os.path.join(base_path, v_year_letter, 'bin', 'matlab'))
            paths_to_check.append('matlab')

        for path_candidate in paths_to_check:
            is_path_command = path_candidate.lower() == 'matlab' or path_candidate.lower() == 'matlab.exe'
            if is_path_command:
                try:
                    test_process = subprocess.run([path_candidate, "-batch", "exit"], timeout=5, capture_output=True,
                                                  creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                    if test_process.returncode == 0:
                        if self.set_matlab_path(path_candidate):
                           # set_matlab_path emits "path set and appears valid", which is good.
                           # test_connection() will confirm and set self.connected
                           self.test_connection() # Confirm with a real test
                           if self.connected: return True
                except (FileNotFoundError, subprocess.TimeoutExpired, OSError): continue
            elif os.path.exists(path_candidate) and (os.access(path_candidate, os.X_OK) or path_candidate.lower().endswith('.exe')):
                if self.set_matlab_path(path_candidate):
                    self.test_connection()
                    if self.connected: return True
        self.connectionStatusChanged.emit(False, "MATLAB auto-detection failed. Please set the path manually.")
        return False

    def _run_matlab_script(self, script_content, worker_signal, success_message_prefix):
        if not self.connected:
            worker_signal.emit(False, "MATLAB not connected or path invalid.", "")
            return
        try:
            temp_dir = tempfile.mkdtemp(prefix="bsm_matlab_")
            script_file = os.path.join(temp_dir, "matlab_script.m")
            with open(script_file, 'w', encoding='utf-8') as f: f.write(script_content)
        except Exception as e:
            worker_signal.emit(False, f"Failed to create temporary MATLAB script: {e}", "")
            return
        worker = MatlabCommandWorker(self.matlab_path, script_file, worker_signal, success_message_prefix)
        thread = QThread(); worker.moveToThread(thread)
        thread.started.connect(worker.run_command)
        worker.finished_signal.connect(thread.quit); worker.finished_signal.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater); self._active_threads.append(thread)
        thread.finished.connect(lambda t=thread: self._active_threads.remove(t) if t in self._active_threads else None)
        thread.start()

    def generate_simulink_model(self, states, transitions, output_dir, model_name="BrainStateMachine"):
        if not self.connected: self.simulationFinished.emit(False, "MATLAB not connected.", ""); return False
        slx_file_path = os.path.join(output_dir, f"{model_name}.slx").replace('\\', '/')
        model_name_orig = model_name
        script_lines = [f"% Auto-generated Simulink model script for '{model_name_orig}'", f"disp('Starting Simulink model generation for {model_name_orig}...');",
                        f"modelNameVar = '{model_name_orig}';", f"outputModelPath = '{slx_file_path}';", "try",
                        "    if bdIsLoaded(modelNameVar), close_system(modelNameVar, 0); end", "    if exist(outputModelPath, 'file'), delete(outputModelPath); end",
                        "    hModel = new_system(modelNameVar);", "    open_system(hModel);", "    disp('Adding Stateflow chart...');",
                        "    machine = sfroot.find('-isa', 'Stateflow.Machine', 'Name', modelNameVar);", "    if isempty(machine)",
                        "        error('Stateflow machine for model ''%s'' not found after new_system.', modelNameVar);", "    end",
                        "    chartSFObj = Stateflow.Chart(machine);",  "    chartSFObj.Name = 'BrainStateMachineLogic';",
                        "    chartBlockSimulinkPath = [modelNameVar, '/', 'BSM_Chart'];",
                        "    add_block('stateflow/Chart', chartBlockSimulinkPath, 'Chart', chartSFObj.Path);",
                        "    set_param(chartBlockSimulinkPath, 'Position', [100 50 400 350]);", "    disp(['Stateflow chart block added at: ', chartBlockSimulinkPath]);",
                        "    stateHandles = containers.Map('KeyType','char','ValueType','any');", "% --- State Creation ---"]
        for i, state in enumerate(states):
            s_name_matlab = state['name'].replace("'", "''")
            s_id_matlab_safe = f"state_{i}_{state['name'].replace(' ', '_').replace('-', '_')}"; s_id_matlab_safe = ''.join(filter(str.isalnum, s_id_matlab_safe))
            if not s_id_matlab_safe or not s_id_matlab_safe[0].isalpha(): s_id_matlab_safe = 's_' + s_id_matlab_safe
            state_label_parts = []
            if state.get('entry_action'): state_label_parts.append(f"entry: {state['entry_action'].replace(chr(10), '; ')}")
            if state.get('during_action'): state_label_parts.append(f"during: {state['during_action'].replace(chr(10), '; ')}")
            if state.get('exit_action'): state_label_parts.append(f"exit: {state['exit_action'].replace(chr(10), '; ')}")
            s_label_string = "\\n".join(state_label_parts) if state_label_parts else ""; s_label_string_matlab = s_label_string.replace("'", "''")
            sf_x = state['x'] / 2.5 + 20; sf_y = state['y'] / 2.5 + 20; sf_w = max(60, state['width'] / 2.5); sf_h = max(40, state['height'] / 2.5)
            script_lines.extend([f"{s_id_matlab_safe} = Stateflow.State(chartSFObj);", f"{s_id_matlab_safe}.Name = '{s_name_matlab}';",
                                 f"{s_id_matlab_safe}.Position = [{sf_x}, {sf_y}, {sf_w}, {sf_h}];",
                                 f"if ~isempty('{s_label_string_matlab}'), {s_id_matlab_safe}.LabelString = sprintf('{s_label_string_matlab}'); end",
                                 f"stateHandles('{s_name_matlab}') = {s_id_matlab_safe};"])
            if state.get('is_initial', False):
                script_lines.append(f"defaultTransition_{i} = Stateflow.Transition(chartSFObj);")
                script_lines.append(f"defaultTransition_{i}.Destination = {s_id_matlab_safe};")
                script_lines.append(f"srcPos = [{sf_x-20} {sf_y + sf_h/2}];"); script_lines.append(f"dstPos = [{sf_x} {sf_y + sf_h/2}];")
        script_lines.append("% --- Transition Creation ---")
        for i, trans in enumerate(transitions):
            src_name_matlab = trans['source'].replace("'", "''"); dst_name_matlab = trans['target'].replace("'", "''"); label_parts = []
            if trans.get('event'): label_parts.append(trans['event'])
            if trans.get('condition'): label_parts.append(f"[{trans['condition']}]")
            if trans.get('action'): label_parts.append(f"/{{{trans['action']}}}")
            t_label = " ".join(label_parts).strip(); t_label_matlab = t_label.replace("'", "''")
            script_lines.extend([f"if isKey(stateHandles, '{src_name_matlab}') && isKey(stateHandles, '{dst_name_matlab}')",
                                 f"    srcStateHandle = stateHandles('{src_name_matlab}');", f"    dstStateHandle = stateHandles('{dst_name_matlab}');",
                                 f"    t{i} = Stateflow.Transition(chartSFObj);", f"    t{i}.Source = srcStateHandle;", f"    t{i}.Destination = dstStateHandle;"])
            if t_label_matlab: script_lines.append(f"    t{i}.LabelString = '{t_label_matlab}';")
            script_lines.append("else"); script_lines.append(f"    disp(['Warning: Could not create SF transition from ''{src_name_matlab}'' to ''{dst_name_matlab}''. State missing.']);"); script_lines.append("end")
        script_lines.extend(["% --- Finalize and Save ---", "    Simulink.BlockDiagram.arrangeSystem(chartBlockSimulinkPath, 'FullLayout', 'true', 'Animation', 'false');",
                             "    sf('FitToView', chartSFObj.Id);", "    disp(['Attempting to save Simulink model to: ', outputModelPath]);",
                             "    save_system(modelNameVar, outputModelPath, 'OverwriteIfChangedOnDisk', true);", "    close_system(modelNameVar, 0);",
                             "    disp(['Simulink model saved successfully to: ', outputModelPath]);", "    fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', outputModelPath);",
                             "catch e", "    disp('ERROR during Simulink model generation:');", "    disp(getReport(e, 'extended', 'hyperlinks', 'off'));",
                             "    if bdIsLoaded(modelNameVar), close_system(modelNameVar, 0); end",
                             "    fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', strrep(getReport(e, 'basic'), '\\n', ' '));", "end"])
        self._run_matlab_script("\n".join(script_lines), self.simulationFinished, "Model generation"); return True

    def run_simulation(self, model_path, sim_time=10):
        if not self.connected: self.simulationFinished.emit(False, "MATLAB not connected.", ""); return False
        if not os.path.exists(model_path): self.simulationFinished.emit(False, f"Model file not found: {model_path}", ""); return False
        model_path_matlab = model_path.replace('\\', '/'); model_dir_matlab = os.path.dirname(model_path_matlab)
        model_name = os.path.splitext(os.path.basename(model_path))[0]
        script_content = f"disp('Starting Simulink simulation...'); modelPath = '{model_path_matlab}'; modelName = '{model_name}'; modelDir = '{model_dir_matlab}'; currentSimTime = {sim_time};\n" \
                         f"try; prevPath = path; addpath(modelDir); disp(['Added to MATLAB path: ', modelDir]); load_system(modelPath);\n" \
                         f"    disp(['Simulating model: ', modelName, ' for ', num2str(currentSimTime), ' seconds.']);\n" \
                         f"    simOut = sim(modelName, 'StopTime', num2str(currentSimTime));\n" \
                         f"    disp('Simulink simulation completed successfully.');\n" \
                         f"    fprintf('MATLAB_SCRIPT_SUCCESS:Simulation of ''%s'' finished at t=%s. Results in MATLAB workspace (simOut).\\n', modelName, num2str(currentSimTime));\n" \
                         f"catch e; disp('ERROR during Simulink simulation:'); disp(getReport(e, 'extended', 'hyperlinks', 'off'));\n" \
                         f"    fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', strrep(getReport(e, 'basic'),'\\n',' '));\n" \
                         f"end; if bdIsLoaded(modelName), close_system(modelName, 0); end; path(prevPath); disp(['Restored MATLAB path. Removed: ', modelDir]);"
        self._run_matlab_script(script_content, self.simulationFinished, "Simulation"); return True

    def generate_code(self, model_path, language="C++", output_dir_base=None):
        if not self.connected: self.codeGenerationFinished.emit(False, "MATLAB not connected", ""); return False
        model_path_matlab = model_path.replace('\\', '/'); model_dir_matlab = os.path.dirname(model_path_matlab)
        model_name = os.path.splitext(os.path.basename(model_path))[0]
        if not output_dir_base: output_dir_base = os.path.dirname(model_path)
        code_gen_root_matlab = output_dir_base.replace('\\', '/')
        script_content = f"disp('Starting Simulink code generation...'); modelPath = '{model_path_matlab}'; modelName = '{model_name}'; codeGenBaseDir = '{code_gen_root_matlab}'; modelDir = '{model_dir_matlab}';\n" \
                         f"try; prevPath = path; addpath(modelDir); disp(['Added to MATLAB path: ', modelDir]); load_system(modelPath);\n" \
                         f"    if ~(license('test', 'MATLAB_Coder') && license('test', 'Simulink_Coder') && license('test', 'Embedded_Coder'))\n" \
                         f"        error('Required licenses (MATLAB Coder, Simulink Coder, Embedded Coder) are not available.'); end\n" \
                         f"    set_param(modelName,'SystemTargetFile','ert.tlc'); set_param(modelName,'GenerateMakefile','on');\n" \
                         f"    cfg = getActiveConfigSet(modelName);\n" \
                         f"    if strcmpi('{language}', 'C++'); set_param(cfg, 'TargetLang', 'C++');\n" \
                         f"        set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'C++ class');\n" \
                         f"        set_param(cfg.getComponent('Code Generation'),'TargetLangStandard', 'C++11 (ISO)'); disp('Configured for C++ (class interface, C++11).');\n" \
                         f"    else; set_param(cfg, 'TargetLang', 'C');\n" \
                         f"        set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'Reusable function'); disp('Configured for C (reusable function).'); end\n" \
                         f"    set_param(cfg, 'GenerateReport', 'on'); set_param(cfg, 'GenCodeOnly', 'on'); set_param(cfg, 'RTWVerbose', 'on');\n" \
                         f"    if ~exist(codeGenBaseDir, 'dir'), mkdir(codeGenBaseDir); disp(['Created base codegen dir: ', codeGenBaseDir]); end\n" \
                         f"    disp(['Code generation output base set to: ', codeGenBaseDir]);\n" \
                         f"    rtwbuild(modelName, 'CodeGenFolder', codeGenBaseDir, 'GenCodeOnly', true); disp('Code generation command (rtwbuild) executed.');\n" \
                         f"    actualCodeDir = fullfile(codeGenBaseDir, [modelName '_ert_rtw']);\n" \
                         f"    if ~exist(actualCodeDir, 'dir'); disp(['Warning: Standard codegen subdir ''', actualCodeDir, ''' not found.']); actualCodeDir = codeGenBaseDir; end\n" \
                         f"    disp(['Simulink code generation successful. Code/report in/under: ', actualCodeDir]); fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', actualCodeDir);\n" \
                         f"catch e; disp('ERROR during Simulink code generation:'); disp(getReport(e, 'extended', 'hyperlinks', 'off'));\n" \
                         f"    fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', strrep(getReport(e, 'basic'),'\\n',' '));\n" \
                         f"end; if bdIsLoaded(modelName), close_system(modelName, 0); end; path(prevPath);  disp(['Restored MATLAB path. Removed: ', modelDir]);"
        self._run_matlab_script(script_content, self.codeGenerationFinished, "Code generation"); return True

class MatlabCommandWorker(QObject):
    finished_signal = pyqtSignal(bool, str, str)
    def __init__(self, matlab_path, script_file, original_signal, success_message_prefix):
        super().__init__(); self.matlab_path = matlab_path; self.script_file = script_file
        self.original_signal = original_signal; self.success_message_prefix = success_message_prefix
    def run_command(self):
        output_data = ""; success = False; message = ""
        try:
            run_cmd_str = f"run('{self.script_file.replace('\\', '/')}')"
            cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", run_cmd_str]
            timeout_s = 600
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=timeout_s, check=False,
                                  creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            stdout = proc.stdout or ""; stderr = proc.stderr or ""
            if "MATLAB_SCRIPT_FAILURE:" in stdout:
                success = False
                for line in stdout.splitlines():
                    if line.startswith("MATLAB_SCRIPT_FAILURE:"): message = f"{self.success_message_prefix} script failure: {line.split(':', 1)[1].strip()}"; break
                if not message: message = f"{self.success_message_prefix} script failure. Stdout: {stdout[:500]}"
                if stderr: message += f"\nStderr: {stderr[:300]}"
            elif proc.returncode == 0:
                if "MATLAB_SCRIPT_SUCCESS:" in stdout:
                    success = True
                    for line in stdout.splitlines():
                        if line.startswith("MATLAB_SCRIPT_SUCCESS:"): output_data = line.split(":", 1)[1].strip(); break
                    message = f"{self.success_message_prefix} completed successfully."
                    if output_data and self.success_message_prefix != "Simulation": message += f" Data: {output_data}"
                    elif output_data and self.success_message_prefix == "Simulation": message = output_data
                else:
                    success = False; message = f"{self.success_message_prefix} script OK (exit 0), but no success marker."
                    message += f"\nStdout: {stdout[:500]}";
                    if stderr: message += f"\nStderr: {stderr[:300]}"
            else:
                success = False; err_out = stderr or stdout
                message = f"{self.success_message_prefix} process failed. Exit {proc.returncode}:\n{err_out[:1000]}"
            self.original_signal.emit(success, message, output_data if success else "")
        except subprocess.TimeoutExpired: self.original_signal.emit(False, f"{self.success_message_prefix} timed out ({timeout_s/60:.1f} min).", "")
        except FileNotFoundError: self.original_signal.emit(False, f"MATLAB not found: {self.matlab_path}", "")
        except Exception as e: self.original_signal.emit(False, f"Error in {self.success_message_prefix} worker: {type(e).__name__}: {e}", "")
        finally:
            if os.path.exists(self.script_file):
                try:
                    os.remove(self.script_file); script_dir = os.path.dirname(self.script_file)
                    if script_dir.startswith(tempfile.gettempdir()) and "bsm_matlab_" in script_dir and not os.listdir(script_dir): os.rmdir(script_dir)
                except OSError as e: print(f"Warning: Could not clean temp '{self.script_file}': {e}")
            self.finished_signal.emit(success, message, output_data)


# --- Draggable Toolbox Buttons ---
class DraggableToolButton(QPushButton):
    def __init__(self, text, mime_type, item_type_data, parent=None):
        super().__init__(text, parent); self.setObjectName("DraggableToolButton"); self.mime_type = mime_type
        self.item_type_data = item_type_data; self.setMinimumHeight(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed); self.drag_start_position = QPoint()
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton: self.drag_start_position = event.pos()
        super().mousePressEvent(event)
    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton) or (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance(): return
        drag = QDrag(self); mime_data = QMimeData(); mime_data.setText(self.item_type_data)
        mime_data.setData(self.mime_type, self.item_type_data.encode()); drag.setMimeData(mime_data)
        px_w = max(160, self.width()); px_h = max(36, self.height()); px_size = QSize(px_w, px_h)
        pixmap = QPixmap(px_size); pixmap.fill(Qt.transparent); painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing); btn_rect = QRectF(0, 0, px_size.width() - 1, px_size.height() - 1)
        bg_color = QColor(COLOR_ACCENT_PRIMARY); border_color = QColor(COLOR_ACCENT_PRIMARY).darker(120)
        text_color_drag = QColor(COLOR_TEXT_ON_ACCENT); painter.setBrush(bg_color)
        painter.setPen(QPen(border_color, 1.5)); painter.drawRoundedRect(btn_rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5)
        icon_s = self.iconSize() if not self.iconSize().isEmpty() else QSize(18,18)
        icon_px = self.icon().pixmap(icon_s, QIcon.Normal, QIcon.On)
        pad_l = 10; pad_r = 10; pad_tb = (px_h - icon_s.height()) / 2
        txt_x_off = pad_l; icon_y_off = pad_tb
        if not icon_px.isNull(): painter.drawPixmap(int(txt_x_off), int(icon_y_off), icon_px); txt_x_off += icon_px.width() + 8
        painter.setPen(text_color_drag); font_use = self.font()
        font_use.setWeight(QFont.Bold if self.font().weight() > QFont.Normal else self.font().weight()); painter.setFont(font_use)
        txt_rect = QRectF(txt_x_off, 0, px_size.width() - txt_x_off - pad_r, px_size.height())
        painter.drawText(txt_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text()); painter.end()
        drag.setPixmap(pixmap); drag.setHotSpot(QPoint(pixmap.width() // 4, pixmap.height() // 2)); drag.exec_(Qt.CopyAction | Qt.MoveAction)


# --- Graphics Items, Undo Commands, DiagramScene, ZoomableView ---
# (These classes were not changed in this specific update round, so they are omitted for brevity.
# They should be identical to the version from the previous step where they were reviewed.)
class GraphicsStateItem(QGraphicsRectItem):
    Type = QGraphicsItem.UserType + 1
    def type(self): return GraphicsStateItem.Type
    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False, color=None, entry_action="", during_action="", exit_action="", description=""):
        super().__init__(x, y, w, h); self.text_label = text; self.is_initial = is_initial; self.is_final = is_final
        self.base_color = QColor(color) if color else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        self.border_color = QColor(color).darker(120) if color else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)
        self.entry_action = entry_action; self.during_action = during_action; self.exit_action = exit_action; self.description = description
        self._text_color = QColor(COLOR_TEXT_PRIMARY); self._font = QFont(APP_FONT_FAMILY, 10, QFont.Bold); self._border_pen_width = 1.5
        self.setPen(QPen(self.border_color, self._border_pen_width)); self.setBrush(QBrush(self.base_color))
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True); self.shadow_effect = QGraphicsDropShadowEffect(); self.shadow_effect.setBlurRadius(10)
        self.shadow_effect.setColor(QColor(0, 0, 0, 60)); self.shadow_effect.setOffset(2.5, 2.5); self.setGraphicsEffect(self.shadow_effect)
    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing); current_rect = self.rect(); border_radius = 10
        painter.setPen(self.pen()); painter.setBrush(self.brush()); painter.drawRoundedRect(current_rect, border_radius, border_radius)
        painter.setPen(self._text_color); painter.setFont(self._font); text_rect = current_rect.adjusted(8, 8, -8, -8)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)
        if self.is_initial:
            mr = 6; ll = 18; mc = Qt.black; smcx = current_rect.left() - ll - mr / 2; smcy = current_rect.center().y()
            painter.setBrush(mc); painter.setPen(QPen(mc, self._border_pen_width)); painter.drawEllipse(QPointF(smcx, smcy), mr, mr)
            lsp = QPointF(smcx + mr, smcy); lep = QPointF(current_rect.left(), smcy); painter.drawLine(lsp, lep)
            arr_s = 8; ang_r = 0; arr_p1 = QPointF(lep.x() - arr_s * math.cos(ang_r + math.pi / 6), lep.y() - arr_s * math.sin(ang_r + math.pi / 6))
            arr_p2 = QPointF(lep.x() - arr_s * math.cos(ang_r - math.pi / 6), lep.y() - arr_s * math.sin(ang_r - math.pi / 6))
            painter.drawPolygon(QPolygonF([lep, arr_p1, arr_p2]))
        if self.is_final:
            painter.setPen(QPen(self.border_color.darker(120), self._border_pen_width + 0.5)); inner_rect = current_rect.adjusted(5, 5, -5, -5)
            painter.setBrush(Qt.NoBrush); painter.drawRoundedRect(inner_rect, border_radius - 3, border_radius - 3)
        if self.isSelected():
            sel_pen = QPen(QColor(COLOR_ITEM_STATE_SELECTION), self._border_pen_width + 1, Qt.SolidLine)
            sel_rect = self.boundingRect().adjusted(-1, -1, 1, 1); painter.setPen(sel_pen); painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(sel_rect, border_radius + 1, border_radius + 1)
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene(): self.scene().item_moved.emit(self)
        return super().itemChange(change, value)
    def get_data(self): return {'name': self.text_label, 'x': self.x(), 'y': self.y(), 'width': self.rect().width(), 'height': self.rect().height(), 'is_initial': self.is_initial, 'is_final': self.is_final, 'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_STATE_DEFAULT_BG).name(), 'entry_action': self.entry_action, 'during_action': self.during_action, 'exit_action': self.exit_action, 'description': self.description}
    def set_text(self, text):
        if self.text_label != text: self.prepareGeometryChange(); self.text_label = text; self.update()
    def set_properties(self, name, is_initial, is_final, color_hex=None, entry="", during="", exit_a="", desc=""):
        changed = False
        if self.text_label != name: self.text_label = name; changed = True
        if self.is_initial != is_initial: self.is_initial = is_initial; changed = True
        if self.is_final != is_final: self.is_final = is_final; changed = True
        new_bc = QColor(color_hex) if color_hex else QColor(COLOR_ITEM_STATE_DEFAULT_BG); new_brc = new_bc.darker(120) if color_hex else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)
        if self.base_color != new_bc: self.base_color = new_bc; self.border_color = new_brc; self.setBrush(self.base_color); self.setPen(QPen(self.border_color, self._border_pen_width)); changed = True
        if self.entry_action != entry: self.entry_action = entry; changed = True
        if self.during_action != during: self.during_action = during; changed = True
        if self.exit_action != exit_a: self.exit_action = exit_a; changed = True
        if self.description != desc: self.description = desc; changed = True
        if changed: self.prepareGeometryChange(); self.update()

class GraphicsTransitionItem(QGraphicsPathItem):
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type
    def __init__(self, start_item, end_item, event_str="", condition_str="", action_str="", color=None, description=""):
        super().__init__(); self.start_item = start_item; self.end_item = end_item; self.event_str = event_str; self.condition_str = condition_str; self.action_str = action_str
        self.base_color = QColor(color) if color else QColor(COLOR_ITEM_TRANSITION_DEFAULT); self.description = description
        self.arrow_size = 10; self._text_color = QColor(COLOR_TEXT_PRIMARY); self._font = QFont(APP_FONT_FAMILY, 8); self.control_point_offset = QPointF(0,0); self._pen_width = 2.0
        self.setPen(QPen(self.base_color, self._pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable)
        self.setZValue(-1); self.setAcceptHoverEvents(True); self.update_path()
        def _compose_label_string(self):
            parts = []
        if self.event_str:
            parts.append(self.event_str)
        if self.condition_str:
            parts.append(f"[{self.condition_str}]")
        if self.action_str:
            parts.append(f"/{{{self.action_str}}}")
        return " ".join(parts)
# ...existing code...
    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent): self.setPen(QPen(self.base_color.lighter(130), self._pen_width + 0.5)); super().hoverEnterEvent(event)
    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent): self.setPen(QPen(self.base_color, self._pen_width)); super().hoverLeaveEvent(event)
    def boundingRect(self):
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 25; path_bounds = self.path().boundingRect(); current_label = self._compose_label_string()
        if current_label:
            fm = QFontMetrics(self._font); text_rect = fm.boundingRect(current_label); mid_point = self.path().pointAtPercent(0.5)
            text_render_rect = QRectF(mid_point.x() - text_rect.width() - 10, mid_point.y() - text_rect.height() - 10, text_rect.width()*2 + 20, text_rect.height()*2 + 20)
            path_bounds = path_bounds.united(text_render_rect)
        return path_bounds.adjusted(-extra, -extra, extra, extra)
    def shape(self): ps = QPainterPathStroker(); ps.setWidth(18 + self.pen().widthF()); ps.setCapStyle(Qt.RoundCap); ps.setJoinStyle(Qt.RoundJoin); return ps.createStroke(self.path())
    def update_path(self):
        if not self.start_item or not self.end_item: self.setPath(QPainterPath()); return
        sc = self.start_item.sceneBoundingRect().center(); ec = self.end_item.sceneBoundingRect().center()
        sp = self._get_intersection_point(self.start_item, QLineF(sc, ec)); ep = self._get_intersection_point(self.end_item, QLineF(ec, sc))
        if sp is None: sp = sc;
        if ep is None: ep = ec
        path = QPainterPath(sp)
        if self.start_item == self.end_item:
            rect = self.start_item.sceneBoundingRect(); lrx = rect.width() * 0.40; lry = rect.height() * 0.40
            p1 = QPointF(rect.center().x() + lrx * 0.35, rect.top()); p2 = QPointF(rect.center().x() - lrx * 0.35, rect.top())
            ctrl1 = QPointF(rect.center().x() + lrx * 1.6, rect.top() - lry * 2.8); ctrl2 = QPointF(rect.center().x() - lrx * 1.6, rect.top() - lry * 2.8)
            path.moveTo(p1); path.cubicTo(ctrl1, ctrl2, p2); ep = p2
        else:
            mid_x = (sp.x() + ep.x()) / 2; mid_y = (sp.y() + ep.y()) / 2; dx = ep.x() - sp.x(); dy = ep.y() - sp.y()
            length = math.hypot(dx, dy); length = 1 if length == 0 else length; perp_x = -dy / length; perp_y = dx / length
            cpx = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y()
            cpy = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()
            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0: path.lineTo(ep)
            else: path.quadTo(QPointF(cpx, cpy), ep)
        self.setPath(path); self.prepareGeometryChange()
    def _get_intersection_point(self, item: QGraphicsRectItem, line: QLineF):
        item_rect = item.sceneBoundingRect()
        edges = [QLineF(item_rect.topLeft(), item_rect.topRight()), QLineF(item_rect.topRight(), item_rect.bottomRight()), QLineF(item_rect.bottomRight(), item_rect.bottomLeft()), QLineF(item_rect.bottomLeft(), item_rect.topLeft())]
        pts = [];
        for edge in edges:
            pt_var = QPointF();
            if line.intersect(edge, pt_var) == QLineF.BoundedIntersection:
                er = QRectF(edge.p1(), edge.p2()).normalized(); eps = 1e-3
                if (er.left()-eps <= pt_var.x() <= er.right()+eps and er.top()-eps <= pt_var.y() <= er.bottom()+eps): pts.append(QPointF(pt_var))
        if not pts: return item_rect.center()
        cp = pts[0]; md_sq = (QLineF(line.p1(), cp).length())**2
        for pt in pts[1:]: d_sq = (QLineF(line.p1(), pt).length())**2;
                           if d_sq < md_sq: md_sq = d_sq; cp = pt
        return cp
    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty(): return
        painter.setRenderHint(QPainter.Antialiasing); pen = self.pen()
        if self.isSelected():
            stroker = QPainterPathStroker(); stroker.setWidth(pen.widthF() + 6); stroker.setCapStyle(Qt.RoundCap); stroker.setJoinStyle(Qt.RoundJoin)
            sel_path = stroker.createStroke(self.path()); painter.setPen(Qt.NoPen); painter.setBrush(QColor(COLOR_ITEM_TRANSITION_SELECTION)); painter.drawPath(sel_path)
        painter.setPen(pen); painter.setBrush(Qt.NoBrush); painter.drawPath(self.path())
        if self.path().elementCount() < 1 : return
        pct_end = 0.999 if self.path().length() >= 1 else 0.9; lep = self.path().pointAtPercent(1.0)
        ang_rad = -self.path().angleAtPercent(pct_end) * (math.pi / 180.0)
        arr_p1 = lep + QPointF(math.cos(ang_rad - math.pi / 7) * self.arrow_size, math.sin(ang_rad - math.pi / 7) * self.arrow_size)
        arr_p2 = lep + QPointF(math.cos(ang_rad + math.pi / 7) * self.arrow_size, math.sin(ang_rad + math.pi / 7) * self.arrow_size)
        painter.setBrush(pen.color()); painter.drawPolygon(QPolygonF([lep, arr_p1, arr_p2]))
        label = self._compose_label_string()
        if label:
            painter.setFont(self._font); fm = QFontMetrics(self._font); txt_rect = fm.boundingRect(label); txt_pos = self.path().pointAtPercent(0.5)
            ang_deg = self.path().angleAtPercent(0.5); off_ang_rad = (ang_deg - 90.0) * (math.pi / 180.0); off_dist = 10
            tcx = txt_pos.x() + off_dist * math.cos(off_ang_rad); tcy = txt_pos.y() + off_dist * math.sin(off_ang_rad)
            tfp = QPointF(tcx - txt_rect.width() / 2, tcy - txt_rect.height() / 2); bg_pad = 2
            bg_rect = QRectF(tfp.x()-bg_pad, tfp.y()-bg_pad, txt_rect.width()+2*bg_pad, txt_rect.height()+2*bg_pad)
            painter.setBrush(QColor(COLOR_BACKGROUND_LIGHT).lighter(102)); painter.setPen(QPen(QColor(COLOR_BORDER_LIGHT), 0.5))
            painter.drawRoundedRect(bg_rect, 3, 3); painter.setPen(self._text_color); painter.drawText(tfp, label)
    def get_data(self): return {'source': self.start_item.text_label if self.start_item else "None", 'target': self.end_item.text_label if self.end_item else "None", 'event': self.event_str, 'condition': self.condition_str, 'action': self.action_str, 'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_TRANSITION_DEFAULT).name(), 'description': self.description, 'control_offset_x': self.control_point_offset.x(), 'control_offset_y': self.control_point_offset.y()}
    def set_properties(self, event_str="", condition_str="", action_str="", color_hex=None, description="", offset=None):
        changed = False
        if self.event_str != event_str: self.event_str = event_str; changed=True
        if self.condition_str != condition_str: self.condition_str = condition_str; changed=True
        if self.action_str != action_str: self.action_str = action_str; changed=True
        if self.description != description: self.description = description; changed=True
        new_color = QColor(color_hex) if color_hex else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        if self.base_color != new_color: self.base_color = new_color; self.setPen(QPen(self.base_color, self._pen_width)); changed = True
        if offset is not None and self.control_point_offset != offset: self.control_point_offset = offset; changed = True
        if changed: self.prepareGeometryChange(); self.update_path(); self.update()
    def set_control_point_offset(self, offset: QPointF):
        if self.control_point_offset != offset: self.control_point_offset = offset; self.update_path(); self.update()

class GraphicsCommentItem(QGraphicsTextItem):
    Type = QGraphicsItem.UserType + 3
    def type(self): return GraphicsCommentItem.Type
    def __init__(self, x, y, text="Comment"):
        super().__init__(); self.setPlainText(text); self.setPos(x, y); self.setFont(QFont(APP_FONT_FAMILY, 9)); self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self._default_width = 150; self.setTextWidth(self._default_width); self.border_pen = QPen(QColor(COLOR_ITEM_COMMENT_BORDER), 1)
        self.background_brush = QBrush(QColor(COLOR_ITEM_COMMENT_BG)); self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(8); self.shadow_effect.setColor(QColor(0,0,0,50)); self.shadow_effect.setOffset(2,2); self.setGraphicsEffect(self.shadow_effect)
    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing); painter.setPen(self.border_pen); painter.setBrush(self.background_brush); rect = self.boundingRect()
        painter.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5), 4, 4); self.setDefaultTextColor(QColor(COLOR_TEXT_PRIMARY)); super().paint(painter, option, widget)
        if self.isSelected(): sel_pen = QPen(QColor(COLOR_ACCENT_PRIMARY), 1.5, Qt.DashLine); painter.setPen(sel_pen); painter.setBrush(Qt.NoBrush); painter.drawRect(self.boundingRect())
    def get_data(self): dw = self.document().idealWidth() if self.textWidth() < 0 else self.textWidth(); return {'text': self.toPlainText(), 'x': self.x(), 'y': self.y(), 'width': dw}
    def set_properties(self, text, width=None): self.setPlainText(text); self.setTextWidth(width if width and width > 0 else self._default_width); self.update()
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene(): self.scene().item_moved.emit(self)
        return super().itemChange(change, value)

class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description); self.scene = scene; self.item_instance = item
        if isinstance(item, GraphicsTransitionItem): self.item_data = item.get_data(); self.start_item_name = item.start_item.text_label if item.start_item else None; self.end_item_name = item.end_item.text_label if item.end_item else None
        elif isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): self.item_data = item.get_data()
    def redo(self):
        if self.item_instance.scene() is None: self.scene.addItem(self.item_instance)
        if isinstance(self.item_instance, GraphicsTransitionItem):
            start_node = self.scene.get_state_by_name(self.start_item_name); end_node = self.scene.get_state_by_name(self.end_item_name)
            if start_node and end_node: self.item_instance.start_item = start_node; self.item_instance.end_item = end_node; self.item_instance.set_properties(event_str=self.item_data['event'], condition_str=self.item_data['condition'], action_str=self.item_data['action'], color_hex=self.item_data.get('color'), description=self.item_data.get('description', ""), offset=QPointF(self.item_data['control_offset_x'], self.item_data['control_offset_y'])); self.item_instance.update_path()
            else: self.scene.log_function(f"Error (Redo Add Transition): Missing state(s) for '{self.item_data.get('event', 'Unnamed Transition')}'.")
        self.scene.clearSelection(); self.item_instance.setSelected(True); self.scene.set_dirty(True)
    def undo(self): self.scene.removeItem(self.item_instance); self.scene.set_dirty(True)

class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items_to_remove, description="Remove Items"):
        super().__init__(description); self.scene = scene; self.removed_items_data = []; self.item_instances_for_quick_toggle = list(items_to_remove)
        for item in items_to_remove:
            item_data_entry = item.get_data(); item_data_entry['_type'] = item.type()
            if isinstance(item, GraphicsTransitionItem): item_data_entry['_start_name'] = item.start_item.text_label if item.start_item else None; item_data_entry['_end_name'] = item.end_item.text_label if item.end_item else None
            self.removed_items_data.append(item_data_entry)
    def redo(self):
        for item_instance in self.item_instances_for_quick_toggle:
            if item_instance.scene() == self.scene: self.scene.removeItem(item_instance)
        self.scene.set_dirty(True)
    def undo(self):
        newly_re_added = []; states_map = {}
        for item_data in self.removed_items_data:
            instance = None
            if item_data['_type'] == GraphicsStateItem.Type: state = GraphicsStateItem(item_data['x'], item_data['y'], item_data['width'], item_data['height'], item_data['name'], item_data['is_initial'], item_data['is_final'], item_data.get('color'), item_data.get('entry_action', ""), item_data.get('during_action', ""), item_data.get('exit_action', ""), item_data.get('description', "")); instance = state; states_map[state.text_label] = state
            elif item_data['_type'] == GraphicsCommentItem.Type: comment = GraphicsCommentItem(item_data['x'], item_data['y'], item_data['text']); comment.setTextWidth(item_data.get('width', 150)); instance = comment
            if instance: self.scene.addItem(instance); newly_re_added.append(instance)
        for item_data in self.removed_items_data:
            if item_data['_type'] == GraphicsTransitionItem.Type:
                src = states_map.get(item_data['_start_name']); tgt = states_map.get(item_data['_end_name'])
                if src and tgt: trans = GraphicsTransitionItem(src, tgt, event_str=item_data['event'], condition_str=item_data['condition'], action_str=item_data['action'], color=item_data.get('color'), description=item_data.get('description',"")); trans.set_control_point_offset(QPointF(item_data['control_offset_x'], item_data['control_offset_y'])); self.scene.addItem(trans); newly_re_added.append(trans)
                else: self.scene.log_function(f"Error (Undo Remove): Missing states for transition.")
        self.item_instances_for_quick_toggle = newly_re_added; self.scene.set_dirty(True)

class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_and_new_positions, description="Move Items"):
        super().__init__(description); self.items_and_new_positions = items_and_new_positions; self.items_and_old_positions = []; self.scene_ref = None
        if self.items_and_new_positions: self.scene_ref = self.items_and_new_positions[0][0].scene();
                                         for item, _ in self.items_and_new_positions: self.items_and_old_positions.append((item, item.pos()))
    def _apply_positions(self, positions_list):
        if not self.scene_ref: return
        for item, pos in positions_list: item.setPos(pos);
                                         if isinstance(item, GraphicsStateItem): self.scene_ref._update_connected_transitions(item)
        self.scene_ref.update(); self.scene_ref.set_dirty(True)
    def redo(self): self._apply_positions(self.items_and_new_positions)
    def undo(self): self._apply_positions(self.items_and_old_positions)

class EditItemPropertiesCommand(QUndoCommand):
    def __init__(self, item, old_props_data, new_props_data, description="Edit Properties"):
        super().__init__(description); self.item = item; self.old_props_data = old_props_data; self.new_props_data = new_props_data; self.scene_ref = item.scene()
    def _apply_properties(self, props):
        if not self.item or not self.scene_ref: return
        orig_name = None
        if isinstance(self.item, GraphicsStateItem):
            orig_name = self.item.text_label; self.item.set_properties(props['name'], props.get('is_initial', False), props.get('is_final', False), props.get('color'), props.get('entry_action', ""), props.get('during_action', ""), props.get('exit_action', ""), props.get('description', ""))
            if orig_name != props['name']: self.scene_ref._update_transitions_for_renamed_state(orig_name, props['name'])
        elif isinstance(self.item, GraphicsTransitionItem): self.item.set_properties(event_str=props.get('event',""), condition_str=props.get('condition',""), action_str=props.get('action',""), color_hex=props.get('color'), description=props.get('description',""), offset=QPointF(props['control_offset_x'], props['control_offset_y']))
        elif isinstance(self.item, GraphicsCommentItem): self.item.set_properties(text=props['text'], width=props.get('width'))
        self.item.update(); self.scene_ref.update(); self.scene_ref.set_dirty(True)
    def redo(self): self._apply_properties(self.new_props_data)
    def undo(self): self._apply_properties(self.old_props_data)

class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem); modifiedStatusChanged = pyqtSignal(bool)
    def __init__(self, undo_stack, parent_window=None):
        super().__init__(parent_window); self.parent_window = parent_window; self.setSceneRect(0,0,6000,4500); self.current_mode = "select"; self.transition_start_item = None
        self.log_function = print; self.undo_stack = undo_stack; self._dirty = False; self._mouse_press_items_positions = {}; self._temp_transition_line = None
        self.item_moved.connect(self._handle_item_moved); self.grid_size = 20; self.grid_pen_light = QPen(QColor(COLOR_GRID_MINOR),0.7,Qt.DotLine)
        self.grid_pen_dark = QPen(QColor(COLOR_GRID_MAJOR),0.9,Qt.SolidLine); self.setBackgroundBrush(QColor(COLOR_BACKGROUND_LIGHT)); self.snap_to_grid_enabled = True
    def _update_connected_transitions(self, state_item: GraphicsStateItem):
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem) and (item.start_item == state_item or item.end_item == state_item): item.update_path()
    def _update_transitions_for_renamed_state(self, old_name:str, new_name:str): self.log_function(f"State '{old_name}' renamed to '{new_name}'.")
    def get_state_by_name(self, name: str):
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name: return item
        return None
    def set_dirty(self, dirty=True):
        if self._dirty != dirty: self._dirty = dirty; self.modifiedStatusChanged.emit(dirty)
        if self.parent_window: self.parent_window._update_save_actions_enable_state()
    def is_dirty(self): return self._dirty
    def set_log_function(self, log_function): self.log_function = log_function
    def set_mode(self, mode: str):
        old_mode = self.current_mode; self.current_mode = mode;
        if old_mode == mode: return
        self.log_function(f"Mode: {mode}"); self.transition_start_item = None
        if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
        if self.parent_window and self.parent_window.view: self.parent_window.view._restore_cursor_to_scene_mode()
        for item in self.items():
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): item.setFlag(QGraphicsItem.ItemIsMovable, mode == "select")
        if self.parent_window:
            am = {"select": self.parent_window.select_mode_action, "state": self.parent_window.add_state_mode_action, "transition": self.parent_window.add_transition_mode_action, "comment": self.parent_window.add_comment_mode_action}
            for m, action in am.items():
                if m == mode and not action.isChecked(): action.setChecked(True); break
    def select_all(self):
        for item in self.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable: item.setSelected(True)
    def _handle_item_moved(self, moved_item):
        if isinstance(moved_item, GraphicsStateItem): self._update_connected_transitions(moved_item)
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos(); items_at_pos = self.items(pos)
        top_item = next((i for i in items_at_pos if isinstance(i, GraphicsStateItem)), None)
        if not top_item: top_item = next((i for i in items_at_pos if isinstance(i, (GraphicsCommentItem, GraphicsTransitionItem))), None)
        if not top_item and items_at_pos: top_item = items_at_pos[0]
        if event.button() == Qt.LeftButton:
            if self.current_mode == "state": gx = round(pos.x()/self.grid_size)*self.grid_size-60; gy = round(pos.y()/self.grid_size)*self.grid_size-30; self._add_item_interactive(QPointF(gx,gy),"State")
            elif self.current_mode == "comment": gx = round(pos.x()/self.grid_size)*self.grid_size; gy = round(pos.y()/self.grid_size)*self.grid_size; self._add_item_interactive(QPointF(gx,gy),"Comment")
            elif self.current_mode == "transition":
                if isinstance(top_item, GraphicsStateItem): self._handle_transition_click(top_item, pos)
                else: self.transition_start_item = None;
                      if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None; self.log_function("Transition cancelled.")
            else: self._mouse_press_items_positions.clear();
                  for item in [i for i in self.selectedItems() if i.flags() & QGraphicsItem.ItemIsMovable]: self._mouse_press_items_positions[item] = item.pos()
                  super().mousePressEvent(event)
        elif event.button() == Qt.RightButton:
            if top_item and isinstance(top_item, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem)):
                if not top_item.isSelected(): self.clearSelection(); top_item.setSelected(True)
                self._show_context_menu(top_item, event.screenPos())
            else: self.clearSelection()
        else: super().mousePressEvent(event)
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line: self._temp_transition_line.setLine(QLineF(self.transition_start_item.sceneBoundingRect().center(), event.scenePos()))
        else: super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button()==Qt.LeftButton and self.current_mode=="select" and self._mouse_press_items_positions:
            moved_data = []
            for item, old_pos in self._mouse_press_items_positions.items():
                new_pos = item.pos()
                if self.snap_to_grid_enabled:
                    sx = round(new_pos.x()/self.grid_size)*self.grid_size; sy = round(new_pos.y()/self.grid_size)*self.grid_size
                    if new_pos.x()!=sx or new_pos.y()!=sy: item.setPos(sx,sy); new_pos=QPointF(sx,sy)
                if (new_pos-old_pos).manhattanLength()>0.1: moved_data.append((item,new_pos))
            if moved_data: self.undo_stack.push(MoveItemsCommand(moved_data))
            self._mouse_press_items_positions.clear()
        super().mouseReleaseEvent(event)
    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        item = next((i for i in self.items(event.scenePos()) if isinstance(i, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem))), None)
        if item: self.edit_item_properties(item)
        else: super().mouseDoubleClickEvent(event)
    def _show_context_menu(self, item, global_pos):
        menu = QMenu(); edit_act = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton,"Edt",target_size=QSize(16,16)), "Properties...")
        del_act = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon,"Del",target_size=QSize(16,16)), "Delete")
        action = menu.exec_(global_pos)
        if action == edit_act: self.edit_item_properties(item)
        elif action == del_act:
            if not item.isSelected(): self.clearSelection(); item.setSelected(True)
            self.delete_selected_items()
    def edit_item_properties(self, item):
        old_props = item.get_data(); accepted = False; new_props = None
        if isinstance(item, GraphicsStateItem):
            dlg = StatePropertiesDialog(self.parent_window, old_props);
            if dlg.exec_()==QDialog.Accepted: accepted=True; new_props=dlg.get_properties()
            if new_props and new_props['name']!=old_props['name'] and self.get_state_by_name(new_props['name']): QMessageBox.warning(self.parent_window,"Dup Name",f"State '{new_props['name']}' exists."); return
        elif isinstance(item, GraphicsTransitionItem): dlg = TransitionPropertiesDialog(self.parent_window, old_props);
                                                      if dlg.exec_()==QDialog.Accepted: accepted=True; new_props=dlg.get_properties()
        elif isinstance(item, GraphicsCommentItem): dlg = CommentPropertiesDialog(self.parent_window, old_props);
                                                   if dlg.exec_()==QDialog.Accepted: accepted=True; new_props=dlg.get_properties()
        else: return
        if accepted and new_props is not None:
            final_props = old_props.copy(); final_props.update(new_props)
            cmd = EditItemPropertiesCommand(item,old_props,final_props,f"Edit {type(item).__name__} Props"); self.undo_stack.push(cmd)
            name = final_props.get('name',final_props.get('event',final_props.get('text','Item'))); self.log_function(f"Props updated: {name}")
        self.update()
    def _add_item_interactive(self, pos:QPointF, item_type:str, name_prefix:str="Item", initial_data:dict=None):
        item = None; is_init = initial_data.get('is_initial',False) if initial_data else False; is_final = initial_data.get('is_final',False) if initial_data else False
        if item_type == "State":
            i=1; base=name_prefix;
            while self.get_state_by_name(f"{base}{i}"): i+=1
            def_name=f"{base}{i}"; name_in=def_name; init_dlg_props={'name':name_in,'is_initial':is_init,'is_final':is_final,'color':initial_data.get('color') if initial_data else COLOR_ITEM_STATE_DEFAULT_BG}
            dlg=StatePropertiesDialog(self.parent_window,init_dlg_props,True)
            if dlg.exec_()==QDialog.Accepted:
                props=dlg.get_properties()
                if self.get_state_by_name(props['name']) and props['name']!=name_in: QMessageBox.warning(self.parent_window,"Dup Name",f"State '{props['name']}' exists.");
                                                                                 if self.current_mode=="state":self.set_mode("select"); return
                item=GraphicsStateItem(pos.x(),pos.y(),120,60,props['name'],props['is_initial'],props['is_final'],props.get('color'),props.get('entry_action',""),props.get('during_action',""),props.get('exit_action',""),props.get('description',""))
            else:
                if self.current_mode=="state": self.set_mode("select"); return
        elif item_type == "Comment":
            init_txt = (initial_data.get('text',"Comment") if initial_data else (name_prefix if name_prefix!="Item" else "Comment"))
            txt,ok = QInputDialog.getMultiLineText(self.parent_window,"New Comment","Enter comment:",init_txt)
            if ok and txt: item = GraphicsCommentItem(pos.x(),pos.y(),txt)
            else:
                if self.current_mode=="comment": self.set_mode("select"); return
        else: self.log_function(f"Unknown type: {item_type}"); return
        if item: cmd=AddItemCommand(self,item,f"Add {item_type}"); self.undo_stack.push(cmd); name=item.text_label if hasattr(item,'text_label') else item.toPlainText(); self.log_function(f"Added {item_type}: {name} at ({pos.x():.0f},{pos.y():.0f})")
        if self.current_mode in ["state","comment"]: self.set_mode("select")
    def _handle_transition_click(self, clicked_item:GraphicsStateItem, click_pos:QPointF):
        if not self.transition_start_item:
            self.transition_start_item=clicked_item
            if not self._temp_transition_line: self._temp_transition_line=QGraphicsLineItem(); self._temp_transition_line.setPen(QPen(QColor(COLOR_ACCENT_PRIMARY),1.8,Qt.DashLine)); self.addItem(self._temp_transition_line)
            self._temp_transition_line.setLine(QLineF(self.transition_start_item.sceneBoundingRect().center(),click_pos)); self.log_function(f"Transition from: {clicked_item.text_label}. Click target.")
        else:
            if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line=None
            init_props={'event':"",'condition':"",'action':"",'color':COLOR_ITEM_TRANSITION_DEFAULT,'description':"",'control_offset_x':0,'control_offset_y':0}
            dlg=TransitionPropertiesDialog(self.parent_window,init_props,True)
            if dlg.exec_()==QDialog.Accepted:
                props=dlg.get_properties(); trans=GraphicsTransitionItem(self.transition_start_item,clicked_item,props['event'],props['condition'],props['action'],props.get('color'),props.get('description',""))
                trans.set_control_point_offset(QPointF(props['control_offset_x'],props['control_offset_y'])); cmd=AddItemCommand(self,trans,"Add Transition"); self.undo_stack.push(cmd)
                self.log_function(f"Added trans: {self.transition_start_item.text_label} -> {clicked_item.text_label} [{trans._compose_label_string()}]")
            else: self.log_function("Transition cancelled.")
            self.transition_start_item=None; self.set_mode("select")
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in [Qt.Key_Delete, Qt.Key_Backspace]:
            if self.selectedItems(): self.delete_selected_items()
        elif event.key() == Qt.Key_Escape:
            if self.current_mode=="transition" and self.transition_start_item: self.transition_start_item=None;
                                                                              if self._temp_transition_line:self.removeItem(self._temp_transition_line);self._temp_transition_line=None; self.log_function("Transition cancelled (Esc)."); self.set_mode("select")
            elif self.current_mode!="select": self.set_mode("select")
            else: self.clearSelection()
        else: super().keyPressEvent(event)
    def delete_selected_items(self):
        sel = self.selectedItems();
        if not sel: return
        to_del = set()
        for item in sel: to_del.add(item);
                         if isinstance(item,GraphicsStateItem):
                            for si in self.items():
                                if isinstance(si,GraphicsTransitionItem) and (si.start_item==item or si.end_item==item): to_del.add(si)
        if to_del: cmd=RemoveItemsCommand(self,list(to_del),"Delete Items"); self.undo_stack.push(cmd); self.log_function(f"Queued delete: {len(to_del)} item(s)."); self.clearSelection()
    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"): event.setAccepted(True); event.acceptProposedAction()
        else: super().dragEnterEvent(event)
    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"): event.acceptProposedAction()
        else: super().dragMoveEvent(event)
    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        pos = event.scenePos()
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            type_str = event.mimeData().text(); gx=round(pos.x()/self.grid_size)*self.grid_size; gy=round(pos.y()/self.grid_size)*self.grid_size
            if "State" in type_str: gx-=60; gy-=30
            props={}; type_add="Item"; name_pref="Item"
            if type_str=="State": type_add="State"; name_pref="State"
            elif type_str=="Initial State": type_add="State"; name_pref="Initial"; props['is_initial']=True
            elif type_str=="Final State": type_add="State"; name_pref="Final"; props['is_final']=True
            elif type_str=="Comment": type_add="Comment"; name_pref="Note"
            else: self.log_function(f"Unknown dropped type: {type_str}"); event.ignore(); return
            self._add_item_interactive(QPointF(gx,gy),item_type=type_add,name_prefix=name_pref,initial_data=props); event.acceptProposedAction()
        else: super().dropEvent(event)
    def get_diagram_data(self):
        data={'states':[],'transitions':[],'comments':[]};
        for item in self.items():
            if isinstance(item,GraphicsStateItem): data['states'].append(item.get_data())
            elif isinstance(item,GraphicsTransitionItem):
                if item.start_item and item.end_item: data['transitions'].append(item.get_data())
                else: self.log_function(f"Skip save orphan trans: '{item._compose_label_string()}'.")
            elif isinstance(item,GraphicsCommentItem): data['comments'].append(item.get_data())
        return data
    def load_diagram_data(self, data):
        self.clear(); self.set_dirty(False); states_map={}
        for sd in data.get('states',[]):
            si=GraphicsStateItem(sd['x'],sd['y'],sd.get('width',120),sd.get('height',60),sd['name'],sd.get('is_initial',False),sd.get('is_final',False),sd.get('color',COLOR_ITEM_STATE_DEFAULT_BG),sd.get('entry_action',""),sd.get('during_action',""),sd.get('exit_action',""),sd.get('description',""))
            self.addItem(si); states_map[sd['name']]=si
        for td in data.get('transitions',[]):
            src=states_map.get(td['source']); tgt=states_map.get(td['target'])
            if src and tgt:
                ti=GraphicsTransitionItem(src,tgt,td.get('event',""),td.get('condition',""),td.get('action',""),td.get('color',COLOR_ITEM_TRANSITION_DEFAULT),td.get('description',""))
                ti.set_control_point_offset(QPointF(td.get('control_offset_x',0),td.get('control_offset_y',0))); self.addItem(ti)
            else: self.log_function(f"Warn (Load): No link trans '{td.get('event','')}': Src='{td['source']}', Tgt='{td['target']}'.")
        for cd in data.get('comments',[]): ci=GraphicsCommentItem(cd['x'],cd['y'],cd.get('text',"")); ci.setTextWidth(cd.get('width',150)); self.addItem(ci)
        self.set_dirty(False); self.undo_stack.clear()
    def drawBackground(self, painter:QPainter, rect:QRectF):
        super().drawBackground(painter,rect); vr=self.views()[0].viewport().rect() if self.views() else rect; vsr=self.views()[0].mapToScene(vr).boundingRect() if self.views() else rect
        l=int(vsr.left()); r=int(vsr.right()); t=int(vsr.top()); b=int(vsr.bottom()); fl=l-(l%self.grid_size); ft=t-(t%self.grid_size)
        painter.setPen(self.grid_pen_light)
        for x in range(fl,r,self.grid_size):
            if x%(self.grid_size*5)!=0: painter.drawLine(x,t,x,b)
        for y in range(ft,b,self.grid_size):
            if y%(self.grid_size*5)!=0: painter.drawLine(l,y,r,y)
        mgs=self.grid_size*5; fml=l-(l%mgs); fmt=t-(t%mgs); painter.setPen(self.grid_pen_dark)
        for x in range(fml,r,mgs): painter.drawLine(x,t,x,b)
        for y in range(fmt,b,mgs): painter.drawLine(l,y,r,y)

class ZoomableView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene,parent); self.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform|QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag); self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate); self.zoom_level=0
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._is_panning_space=False; self._is_panning_mouse=False; self._last_pan_point=QPoint()
    def wheelEvent(self, event:QWheelEvent):
        if event.modifiers()&Qt.ControlModifier:
            delta=event.angleDelta().y(); factor=1.12 if delta>0 else 1/1.12; new_zoom=self.zoom_level+(1 if delta>0 else -1)
            if -15<=new_zoom<=25: self.scale(factor,factor); self.zoom_level=new_zoom
            event.accept()
        else: super().wheelEvent(event)
    def keyPressEvent(self, event:QKeyEvent):
        if event.key()==Qt.Key_Space and not self._is_panning_space and not event.isAutoRepeat(): self._is_panning_space=True; self._last_pan_point=self.mapFromGlobal(QCursor.pos()); self.setCursor(Qt.OpenHandCursor); event.accept()
        elif event.key() in [Qt.Key_Plus, Qt.Key_Equal]: self.scale(1.12,1.12); self.zoom_level+=1
        elif event.key()==Qt.Key_Minus: self.scale(1/1.12,1/1.12); self.zoom_level-=1
        elif event.key() in [Qt.Key_0, Qt.Key_Asterisk]: self.resetTransform(); self.zoom_level=0;
                                                          if self.scene(): cr=self.scene().itemsBoundingRect();
                                                                           if not cr.isEmpty(): self.centerOn(cr.center())
                                                                           else: self.centerOn(self.scene().sceneRect().center())
        else: super().keyPressEvent(event)
    def keyReleaseEvent(self, event:QKeyEvent):
        if event.key()==Qt.Key_Space and self._is_panning_space and not event.isAutoRepeat(): self._is_panning_space=False;
                                                                                             if not self._is_panning_mouse: self._restore_cursor_to_scene_mode()
                                                                                             event.accept()
        else: super().keyReleaseEvent(event)
    def mousePressEvent(self, event:QMouseEvent):
        if event.button()==Qt.MiddleButton or (self._is_panning_space and event.button()==Qt.LeftButton): self._last_pan_point=event.pos(); self.setCursor(Qt.ClosedHandCursor); self._is_panning_mouse=True; event.accept()
        else: self._is_panning_mouse=False; super().mousePressEvent(event)
    def mouseMoveEvent(self, event:QMouseEvent):
        if self._is_panning_mouse: delta=event.pos()-self._last_pan_point; self._last_pan_point=event.pos(); hs=self.horizontalScrollBar(); vs=self.verticalScrollBar(); hs.setValue(hs.value()-delta.x()); vs.setValue(vs.value()-delta.y()); event.accept()
        else: super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event:QMouseEvent):
        if self._is_panning_mouse and (event.button()==Qt.MiddleButton or (self._is_panning_space and event.button()==Qt.LeftButton)):
            self._is_panning_mouse=False;
            if self._is_panning_space: self.setCursor(Qt.OpenHandCursor)
            else: self._restore_cursor_to_scene_mode()
            event.accept()
        else: super().mouseReleaseEvent(event)
    def _restore_cursor_to_scene_mode(self):
        mode=self.scene().current_mode if self.scene() else "select"
        if mode=="select": self.setCursor(Qt.ArrowCursor)
        elif mode in ["state","comment"]: self.setCursor(Qt.CrossCursor)
        elif mode=="transition": self.setCursor(Qt.PointingHandCursor)
        else: self.setCursor(Qt.ArrowCursor)


# --- Dialogs ---
# (StatePropertiesDialog, TransitionPropertiesDialog, CommentPropertiesDialog, MatlabSettingsDialog
# were updated in the previous step for icon sizing and snippet button unification.
# They are assumed to be the same as that version and are omitted here for brevity if no new changes for this feature.)
class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False):
        super().__init__(parent); self.setWindowTitle("State Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "Props", target_size=QSize(20,20))); self.setMinimumWidth(480)
        layout = QFormLayout(self); layout.setSpacing(8); layout.setContentsMargins(12,12,12,12); p = current_properties or {}
        self.name_edit = QLineEdit(p.get('name', "StateName")); self.name_edit.setPlaceholderText("Unique name for the state")
        self.is_initial_cb = QCheckBox("Is Initial State"); self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Is Final State"); self.is_final_cb.setChecked(p.get('is_final', False))
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton"); self.current_color = QColor(p.get('color', COLOR_ITEM_STATE_DEFAULT_BG)); self._update_color_button_style(); self.color_button.clicked.connect(self._choose_color)
        self.entry_action_edit = QTextEdit(p.get('entry_action', "")); self.entry_action_edit.setFixedHeight(65); self.entry_action_edit.setPlaceholderText("MATLAB actions on entry..."); entry_action_btn = self._create_insert_snippet_button(self.entry_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        self.during_action_edit = QTextEdit(p.get('during_action', "")); self.during_action_edit.setFixedHeight(65); self.during_action_edit.setPlaceholderText("MATLAB actions during state..."); during_action_btn = self._create_insert_snippet_button(self.during_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        self.exit_action_edit = QTextEdit(p.get('exit_action', "")); self.exit_action_edit.setFixedHeight(65); self.exit_action_edit.setPlaceholderText("MATLAB actions on exit..."); exit_action_btn = self._create_insert_snippet_button(self.exit_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75); self.description_edit.setPlaceholderText("Optional notes about this state")
        layout.addRow("Name:", self.name_edit); cb_layout = QHBoxLayout(); cb_layout.addWidget(self.is_initial_cb); cb_layout.addWidget(self.is_final_cb); cb_layout.addStretch(); layout.addRow("", cb_layout); layout.addRow("Color:", self.color_button)
        def add_field(lbl, te, btn): h = QHBoxLayout(); h.setSpacing(5); h.addWidget(te,1); v = QVBoxLayout(); v.addWidget(btn); v.addStretch(); h.addLayout(v); layout.addRow(lbl,h)
        add_field("Entry Action:", self.entry_action_edit, entry_action_btn); add_field("During Action:", self.during_action_edit, during_action_btn); add_field("Exit Action:", self.exit_action_edit, exit_action_btn); layout.addRow("Description:", self.description_edit)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(self.accept); btns.rejected.connect(self.reject); layout.addRow(btns)
        if is_new_state: self.name_edit.selectAll(); self.name_edit.setFocus()
    def _create_insert_snippet_button(self, target_widget, snippets_dict: dict, button_text="Insert...", icon_size_px=14):
        button = QPushButton(button_text); button.setObjectName("SnippetButton"); button.setToolTip(f"Insert common snippets"); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins", target_size=QSize(icon_size_px+2, icon_size_px+2)))
        menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            if isinstance(target_widget, QTextEdit): action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n"))
            elif isinstance(target_widget, QLineEdit): action.triggered.connect(lambda checked=False, line_edit=target_widget, s=snippet: (lambda le, sn: (le.setText(le.text()[:le.cursorPosition()] + sn + le.text()[le.cursorPosition():]), le.setCursorPosition(le.cursorPosition() + len(sn) - (len(le.text()) - (le.cursorPosition() + len(sn)))) ))(line_edit,s) ) # complex one-liner to insert at cursor
            menu.addAction(action)
        button.setMenu(menu); return button
    def _choose_color(self): color = QColorDialog.getColor(self.current_color, self, "Select State Color");
                           if color.isValid(): self.current_color = color; self._update_color_button_style()
    def _update_color_button_style(self): l = self.current_color.lightnessF(); tc = COLOR_TEXT_PRIMARY if l > 0.5 else COLOR_TEXT_ON_ACCENT; self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {tc};")
    def get_properties(self): return {'name': self.name_edit.text().strip(), 'is_initial': self.is_initial_cb.isChecked(), 'is_final': self.is_final_cb.isChecked(), 'color': self.current_color.name(), 'entry_action': self.entry_action_edit.toPlainText().strip(), 'during_action': self.during_action_edit.toPlainText().strip(), 'exit_action': self.exit_action_edit.toPlainText().strip(), 'description': self.description_edit.toPlainText().strip()}

class TransitionPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent); self.setWindowTitle("Transition Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogInfoView, "Props", target_size=QSize(20,20))); self.setMinimumWidth(520)
        layout = QFormLayout(self); layout.setSpacing(8); layout.setContentsMargins(12,12,12,12); p = current_properties or {}
        self.event_edit = QLineEdit(p.get('event', "")); self.event_edit.setPlaceholderText("e.g., timeout, button_press(ID)"); event_btn = self._create_insert_snippet_button(self.event_edit, MECHATRONICS_COMMON_EVENTS, " Insert Event")
        self.condition_edit = QLineEdit(p.get('condition', "")); self.condition_edit.setPlaceholderText("e.g., var_x > 10"); condition_btn = self._create_insert_snippet_button(self.condition_edit, MECHATRONICS_COMMON_CONDITIONS, " Insert Condition")
        self.action_edit = QTextEdit(p.get('action', "")); self.action_edit.setPlaceholderText("MATLAB actions..."); self.action_edit.setFixedHeight(65); action_btn = self._create_insert_snippet_button(self.action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton"); self.current_color = QColor(p.get('color', COLOR_ITEM_TRANSITION_DEFAULT)); self._update_color_button_style(); self.color_button.clicked.connect(self._choose_color)
        self.offset_perp_spin = QSpinBox(); self.offset_perp_spin.setRange(-1000,1000); self.offset_perp_spin.setSingleStep(10); self.offset_perp_spin.setValue(int(p.get('control_offset_x',0))); self.offset_perp_spin.setToolTip("Perpendicular bend.")
        self.offset_tang_spin = QSpinBox(); self.offset_tang_spin.setRange(-1000,1000); self.offset_tang_spin.setSingleStep(10); self.offset_tang_spin.setValue(int(p.get('control_offset_y',0))); self.offset_tang_spin.setToolTip("Tangential mid shift.")
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75); self.description_edit.setPlaceholderText("Optional notes")
        def add_field(lbl, ed, btn): h=QHBoxLayout();h.setSpacing(5);h.addWidget(ed,1);v=QVBoxLayout();v.addWidget(btn);v.addStretch();h.addLayout(v);layout.addRow(lbl,h)
        add_field("Event Trigger:",self.event_edit,event_btn); add_field("Condition (Guard):",self.condition_edit,condition_btn); add_field("Transition Action:",self.action_edit,action_btn); layout.addRow("Color:",self.color_button)
        cl=QHBoxLayout();cl.addWidget(QLabel("Bend (Perp):"));cl.addWidget(self.offset_perp_spin);cl.addSpacing(10);cl.addWidget(QLabel("Mid Shift (Tang):"));cl.addWidget(self.offset_tang_spin);cl.addStretch();layout.addRow("Curve Shape:",cl); layout.addRow("Description:",self.description_edit)
        btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);btns.accepted.connect(self.accept);btns.rejected.connect(self.reject);layout.addRow(btns)
        if is_new_transition: self.event_edit.setFocus()
    def _create_insert_snippet_button(self, target_widget, snippets_dict: dict, button_text="Insert...", icon_size_px=14): # Same as in StatePropertiesDialog
        button = QPushButton(button_text); button.setObjectName("SnippetButton"); button.setToolTip(f"Insert common snippets"); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins", target_size=QSize(icon_size_px+2, icon_size_px+2)))
        menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            if isinstance(target_widget, QTextEdit): action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n"))
            elif isinstance(target_widget, QLineEdit): action.triggered.connect(lambda checked=False, line_edit=target_widget, s=snippet: (lambda le, sn: (le.setText(le.text()[:le.cursorPosition()] + sn + le.text()[le.cursorPosition():]), le.setCursorPosition(le.cursorPosition() + len(sn) - (len(le.text()) - (le.cursorPosition() + len(sn)))) ))(line_edit,s) )
            menu.addAction(action)
        button.setMenu(menu); return button
    def _choose_color(self): color = QColorDialog.getColor(self.current_color, self, "Select Transition Color");
                           if color.isValid(): self.current_color = color; self._update_color_button_style()
    def _update_color_button_style(self): l=self.current_color.lightnessF();tc=COLOR_TEXT_PRIMARY if l>0.5 else COLOR_TEXT_ON_ACCENT; self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {tc};")
    def get_properties(self): return {'event':self.event_edit.text().strip(),'condition':self.condition_edit.text().strip(),'action':self.action_edit.toPlainText().strip(),'color':self.current_color.name(),'control_offset_x':self.offset_perp_spin.value(),'control_offset_y':self.offset_tang_spin.value(),'description':self.description_edit.toPlainText().strip()}

class CommentPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent); self.setWindowTitle("Comment Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cmt", target_size=QSize(20,20))); p = current_properties or {}
        layout=QVBoxLayout(self);layout.setSpacing(8);layout.setContentsMargins(12,12,12,12);self.text_edit=QTextEdit(p.get('text',"Comment"));self.text_edit.setMinimumHeight(100);self.text_edit.setPlaceholderText("Enter comment text")
        layout.addWidget(QLabel("Comment Text:"));layout.addWidget(self.text_edit);btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);btns.accepted.connect(self.accept);btns.rejected.connect(self.reject);layout.addWidget(btns);self.setMinimumWidth(380);self.text_edit.setFocus();self.text_edit.selectAll()
    def get_properties(self): return {'text': self.text_edit.toPlainText()}

class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection, parent=None):
        super().__init__(parent); self.matlab_connection = matlab_connection; self.setWindowTitle("MATLAB Settings"); self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg", target_size=QSize(20,20))); self.setMinimumWidth(580)
        ml=QVBoxLayout(self);ml.setSpacing(10);ml.setContentsMargins(10,10,10,10);pg=QGroupBox("MATLAB Executable Path");pfl=QFormLayout();self.pe=QLineEdit(self.matlab_connection.matlab_path);self.pe.setPlaceholderText("e.g., C:\\...\\MATLAB\\R202Xy\\bin\\matlab.exe");pfl.addRow("Path:",self.pe)
        bl=QHBoxLayout();bl.setSpacing(6);bis=QSize(16,16);adb=QPushButton(get_standard_icon(QStyle.SP_BrowserReload,"Det",target_size=bis)," Auto-detect");adb.setIconSize(bis);adb.clicked.connect(self._auto_detect);adb.setToolTip("Attempt to find MATLAB");brb=QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw",target_size=bis)," Browse...");brb.setIconSize(bis);brb.clicked.connect(self._browse);brb.setToolTip("Browse for MATLAB");bl.addWidget(adb);bl.addWidget(brb);bl.addStretch()
        pvl=QVBoxLayout();pvl.setSpacing(8);pvl.addLayout(pfl);pvl.addLayout(bl);pg.setLayout(pvl);ml.addWidget(pg);tg=QGroupBox("Connection Test");tl=QVBoxLayout();tl.setSpacing(8);self.tsl=QLabel("Status: Unknown");self.tsl.setWordWrap(True);self.tsl.setTextInteractionFlags(Qt.TextSelectableByMouse);self.tsl.setMinimumHeight(30)
        tb=QPushButton(get_standard_icon(QStyle.SP_CommandLink,"Test",target_size=bis)," Test Connection");tb.setIconSize(bis);tb.clicked.connect(self._test_connection_and_update_label);tb.setToolTip("Test connection");tl.addWidget(tb);tl.addWidget(self.tsl,1);tg.setLayout(tl);ml.addWidget(tg)
        dbb=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);dbb.button(QDialogButtonBox.Ok).setText("Apply & Close");dbb.accepted.connect(self._apply_settings);dbb.rejected.connect(self.reject);ml.addWidget(dbb);self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        if self.matlab_connection.matlab_path and self.matlab_connection.connected: self._update_test_label_from_signal(True, f"Connected: {self.matlab_connection.matlab_path}")
        elif self.matlab_connection.matlab_path: self._update_test_label_from_signal(False, f"Path: {self.matlab_connection.matlab_path}. Test or auto-detect.")
        else: self._update_test_label_from_signal(False, "MATLAB path not set.")
    def _auto_detect(self): self.tsl.setText("Status: Auto-detecting..."); self.tsl.setStyleSheet(""); QApplication.processEvents(); self.matlab_connection.detect_matlab()
    def _browse(self):
        f="MATLAB Executable (matlab.exe)" if sys.platform=='win32' else "MATLAB Executable (matlab);;All Files (*)";sd=os.path.dirname(self.pe.text()) if self.pe.text() and os.path.isdir(os.path.dirname(self.pe.text())) else QDir.homePath();p,_=QFileDialog.getOpenFileName(self,"Select MATLAB Executable",sd,f)
        if p: self.pe.setText(p); self._update_test_label_from_signal(False, "Path changed. Test or Apply.")
    def _test_connection_and_update_label(self):
        p=self.pe.text().strip();
        if not p: self._update_test_label_from_signal(False,"Path empty."); return
        self.tsl.setText("Status: Testing...");self.tsl.setStyleSheet("");QApplication.processEvents()
        if self.matlab_connection.set_matlab_path(p): self.matlab_connection.test_connection()
    def _update_test_label_from_signal(self,success,message):
        sp="Status: ";cs="font-weight:bold;padding:3px;"
        if success:
            if "path set and appears valid" in message or "detected" in message: sp="Status: Path valid. "
            elif "test successful" in message : sp="Status: Connected! "
            cs+=f"color:#2E7D32;"
        else: sp="Status: Error. "; cs+=f"color:#C62828;"
        self.tsl.setText(sp+message); self.tsl.setStyleSheet(cs)
        if success and self.matlab_connection.matlab_path: self.pe.setText(self.matlab_connection.matlab_path)
    def _apply_settings(self):
        p=self.pe.text().strip()
        if self.matlab_connection.matlab_path!=p or not self.matlab_connection.connected:
            if self.matlab_connection.set_matlab_path(p) and p and not self.matlab_connection.connected: self.matlab_connection.test_connection()
        self.accept()


# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.current_file_path = None; self.last_generated_model_path = None
        self.matlab_connection = MatlabConnection(); self.undo_stack = QUndoStack(self)
        self.scene = DiagramScene(self.undo_stack, self); self.scene.set_log_function(self.log_message)
        self.scene.modifiedStatusChanged.connect(self.setWindowModified); self.scene.modifiedStatusChanged.connect(self._update_window_title)
        self.init_ui(); self.status_label.setObjectName("StatusLabel"); self.matlab_status_label.setObjectName("MatlabStatusLabel")
        self._update_matlab_status_display(False, "Initializing. Configure MATLAB or attempt auto-detect.")
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)
        self._update_window_title(); self.on_new_file(silent=True)
        self.scene.selectionChanged.connect(self._update_properties_dock); self._update_properties_dock()

    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050); self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM", target_size=QSize(32,32)))
        self._create_central_widget(); self._create_actions(); self._create_menus(); self._create_toolbars(); self._create_status_bar(); self._create_docks()
        self._update_save_actions_enable_state(); self._update_matlab_actions_enabled_state(); self._update_undo_redo_actions_enable_state(); self.select_mode_action.trigger()

    def _create_actions(self):
        self.menu_icon_size = QSize(16,16); self.toolbar_icon_size = QSize(22,22); self.dialog_button_icon_size = QSize(16,16); self.dock_tool_icon_size = QSize(18,18)
        def _get_icon(std,fb,cat="toolbar"): s=self.toolbar_icon_size;
                                             if cat=="menu":s=self.menu_icon_size;
                                             elif cat=="dialog_btn":s=self.dialog_button_icon_size;
                                             elif cat=="dock_tool":s=self.dock_tool_icon_size; return get_standard_icon(std,fb,s)
        def _se(n,f=None):return getattr(QStyle,n,getattr(QStyle,f,QStyle.SP_CustomBase) if f else QStyle.SP_CustomBase)
        self.new_action=QAction(_get_icon(QStyle.SP_FileIcon,"New"),"&New",self,shortcut=QKeySequence.New,triggered=self.on_new_file)
        self.open_action=QAction(_get_icon(QStyle.SP_DialogOpenButton,"Opn"),"&Open...",self,shortcut=QKeySequence.Open,triggered=self.on_open_file)
        self.save_action=QAction(_get_icon(QStyle.SP_DialogSaveButton,"Sav"),"&Save",self,shortcut=QKeySequence.Save,triggered=self.on_save_file)
        self.save_as_action=QAction(_get_icon(_se("SP_DriveHDIcon","SP_DialogSaveButton"),"As"),"Save &As...",self,shortcut=QKeySequence.SaveAs,triggered=self.on_save_file_as)
        self.export_diagram_action = QAction(_get_icon(_se("SP_DialogSaveButton","SP_DriveHDIcon"),"Img",size_cat="menu"),"Export Diagram As...",self,statusTip="Export diagram as image/SVG/PDF",triggered=self.on_export_diagram) # New Action
        self.exit_action=QAction(_get_icon(QStyle.SP_DialogCloseButton,"Exit",size_cat="menu"),"E&xit",self,shortcut=QKeySequence.Quit,triggered=self.close)
        self.undo_action=self.undo_stack.createUndoAction(self,"&Undo");self.undo_action.setShortcut(QKeySequence.Undo);self.undo_action.setIcon(_get_icon(QStyle.SP_ArrowBack,"Un"))
        self.redo_action=self.undo_stack.createRedoAction(self,"&Redo");self.redo_action.setShortcut(QKeySequence.Redo);self.redo_action.setIcon(_get_icon(QStyle.SP_ArrowForward,"Re"))
        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_actions_enable_state); self.undo_stack.canRedoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.select_all_action=QAction(_get_icon(_se("SP_FileDialogListView","SP_FileDialogDetailedView"),"All"),"Select &All",self,shortcut=QKeySequence.SelectAll,triggered=self.on_select_all)
        self.delete_action=QAction(_get_icon(QStyle.SP_TrashIcon,"Del"),"&Delete",self,shortcut=QKeySequence.Delete,triggered=self.on_delete_selected)
        self.mode_action_group=QActionGroup(self);self.mode_action_group.setExclusive(True)
        self.select_mode_action=QAction(QIcon.fromTheme("edit-select",_get_icon(QStyle.SP_ArrowRight,"Sel")),"Select/Move",self,checkable=True,triggered=lambda:self.scene.set_mode("select"))
        self.add_state_mode_action=QAction(QIcon.fromTheme("draw-rectangle",_get_icon(QStyle.SP_FileDialogNewFolder,"St")),"Add State",self,checkable=True,triggered=lambda:self.scene.set_mode("state"))
        self.add_transition_mode_action=QAction(QIcon.fromTheme("draw-connector",_get_icon(_se("SP_ArrowForward","Tr-arrow"),"Tr")),"Add Transition",self,checkable=True,triggered=lambda:self.scene.set_mode("transition"))
        self.add_comment_mode_action=QAction(QIcon.fromTheme("insert-text",_get_icon(QStyle.SP_MessageBoxInformation,"Cm")),"Add Comment",self,checkable=True,triggered=lambda:self.scene.set_mode("comment"))
        for a in [self.select_mode_action,self.add_state_mode_action,self.add_transition_mode_action,self.add_comment_mode_action]: self.mode_action_group.addAction(a)
        self.select_mode_action.setChecked(True)
        self.export_simulink_action=QAction(_get_icon(_se("SP_ArrowUp","Exp"),"->M"),"&Export to Simulink...",self,triggered=self.on_export_simulink)
        self.run_simulation_action=QAction(_get_icon(QStyle.SP_MediaPlay,"Run"),"&Run Simulation...",self,triggered=self.on_run_simulation)
        self.generate_code_action=QAction(_get_icon(_se("SP_DialogSaveButton","GenC"),"Cde"),"Generate &Code (C/C++)...",self,triggered=self.on_generate_code)
        self.matlab_settings_action=QAction(_get_icon(QStyle.SP_ComputerIcon,"Cfg",size_cat="menu"),"&MATLAB Settings...",self,triggered=self.on_matlab_settings)
        self.about_action=QAction(_get_icon(QStyle.SP_DialogHelpButton,"?",size_cat="menu"),"&About",self,triggered=self.on_about)

    def _create_menus(self):
        mb=self.menuBar();fm=mb.addMenu("&File");fm.addAction(self.new_action);fm.addAction(self.open_action);fm.addAction(self.save_action);fm.addAction(self.save_as_action);fm.addAction(self.export_diagram_action);fm.addSeparator();fm.addAction(self.export_simulink_action);fm.addSeparator();fm.addAction(self.exit_action)
        em=mb.addMenu("&Edit");em.addAction(self.undo_action);em.addAction(self.redo_action);em.addSeparator();em.addAction(self.delete_action);em.addAction(self.select_all_action);em.addSeparator()
        mm=em.addMenu(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton,"Mode",target_size=self.menu_icon_size),"Interaction Mode");mm.addAction(self.select_mode_action);mm.addAction(self.add_state_mode_action);mm.addAction(self.add_transition_mode_action);mm.addAction(self.add_comment_mode_action)
        sm=mb.addMenu("&Simulation");sm.addAction(self.run_simulation_action);sm.addAction(self.generate_code_action);sm.addSeparator();sm.addAction(self.matlab_settings_action)
        self.view_menu=mb.addMenu("&View");hm=mb.addMenu("&Help");hm.addAction(self.about_action)

    def _create_toolbars(self):
        ftb=self.addToolBar("File");ftb.setObjectName("FileToolBar");ftb.setIconSize(self.toolbar_icon_size);ftb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon);ftb.addAction(self.new_action);ftb.addAction(self.open_action);ftb.addAction(self.save_action)
        etb=self.addToolBar("Edit");etb.setObjectName("EditToolBar");etb.setIconSize(self.toolbar_icon_size);etb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon);etb.addAction(self.undo_action);etb.addAction(self.redo_action);etb.addSeparator();etb.addAction(self.delete_action)
        ttb=self.addToolBar("Interaction Tools");ttb.setObjectName("ToolsToolBar");ttb.setIconSize(self.toolbar_icon_size);ttb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon);ttb.addAction(self.select_mode_action);ttb.addAction(self.add_state_mode_action);ttb.addAction(self.add_transition_mode_action);ttb.addAction(self.add_comment_mode_action)
        stb=self.addToolBar("Simulation Tools");stb.setObjectName("SimulationToolBar");stb.setIconSize(self.toolbar_icon_size);stb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon);stb.addAction(self.export_simulink_action);stb.addAction(self.run_simulation_action);stb.addAction(self.generate_code_action)

    def _create_status_bar(self):
        self.sb=QStatusBar(self);self.setStatusBar(self.sb);self.sl=QLabel("Ready");self.sb.addWidget(self.sl,1);self.msl=QLabel("MATLAB: Init...");self.msl.setToolTip("MATLAB status.");self.sb.addPermanentWidget(self.msl)
        self.pb=QProgressBar(self);self.pb.setRange(0,0);self.pb.setVisible(False);self.pb.setMaximumWidth(150);self.pb.setTextVisible(False);self.sb.addPermanentWidget(self.pb)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks|QMainWindow.AllowTabbedDocks|QMainWindow.AllowNestedDocks);self.td=QDockWidget("Tools",self);self.td.setObjectName("ToolsDock");self.td.setAllowedAreas(Qt.LeftDockWidgetArea|Qt.RightDockWidgetArea)
        tw=QWidget();tw.setObjectName("ToolsDockWidgetContents");tl=QVBoxLayout(tw);tl.setSpacing(10);tl.setContentsMargins(5,5,5,5);mgb=QGroupBox("Interaction Modes");ml=QVBoxLayout();ml.setSpacing(5)
        tsel=QToolButton();tsel.setDefaultAction(self.select_mode_action);taddst=QToolButton();taddst.setDefaultAction(self.add_state_mode_action);ttrans=QToolButton();ttrans.setDefaultAction(self.add_transition_mode_action);taddcom=QToolButton();taddcom.setDefaultAction(self.add_comment_mode_action)
        for b in [tsel,taddst,ttrans,taddcom]: b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon);b.setIconSize(self.dock_tool_icon_size);ml.addWidget(b)
        mgb.setLayout(ml);tl.addWidget(mgb);dgb=QGroupBox("Drag New Elements");dl=QVBoxLayout();dl.setSpacing(5)
        ds=DraggableToolButton("State","application/x-bsm-tool","State");ds.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder,"St",target_size=self.dock_tool_icon_size))
        dis=DraggableToolButton("Initial State","application/x-bsm-tool","Initial State");dis.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton,"I",target_size=self.dock_tool_icon_size))
        dfs=DraggableToolButton("Final State","application/x-bsm-tool","Final State");dfs.setIcon(get_standard_icon(QStyle.SP_DialogOkButton,"F",target_size=self.dock_tool_icon_size))
        dc=DraggableToolButton("Comment","application/x-bsm-tool","Comment");dc.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation,"Cm",target_size=self.dock_tool_icon_size))
        for b in [ds,dis,dfs,dc]: dl.addWidget(b)
        dgb.setLayout(dl);tl.addWidget(dgb);tl.addStretch();self.td.setWidget(tw);self.addDockWidget(Qt.LeftDockWidgetArea,self.td);self.view_menu.addAction(self.td.toggleViewAction())
        self.ld=QDockWidget("Output Log",self);self.ld.setObjectName("LogDock");self.ld.setAllowedAreas(Qt.AllDockWidgetAreas);self.lo=QTextEdit();self.lo.setObjectName("LogOutputWidget");self.lo.setReadOnly(True);self.ld.setWidget(self.lo);self.addDockWidget(Qt.BottomDockWidgetArea,self.ld);self.view_menu.addAction(self.ld.toggleViewAction())
        self.pd=QDockWidget("Element Properties",self);self.pd.setObjectName("PropertiesDock");self.pd.setAllowedAreas(Qt.RightDockWidgetArea|Qt.LeftDockWidgetArea)
        pw=QWidget();pw.setObjectName("PropertiesDockWidgetContents");self.pl=QVBoxLayout(pw);self.pl.setSpacing(8);self.pl.setContentsMargins(5,5,5,5)
        self.pel=QLabel("<i>No item selected.</i>");self.pel.setAlignment(Qt.AlignTop|Qt.AlignLeft);self.pel.setWordWrap(True);self.pel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.peb=QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton,"Edt",target_size=self.dialog_button_icon_size)," Edit Details...");self.peb.setIconSize(self.dialog_button_icon_size);self.peb.setEnabled(False);self.peb.clicked.connect(self._on_edit_selected_item_properties_from_dock)
        self.pl.addWidget(self.pel,1);self.pl.addWidget(self.peb);pw.setLayout(self.pl);self.pd.setWidget(pw);self.addDockWidget(Qt.RightDockWidgetArea,self.pd);self.view_menu.addAction(self.pd.toggleViewAction())

    def _create_central_widget(self): self.view=ZoomableView(self.scene,self);self.view.setObjectName("MainDiagramView");self.setCentralWidget(self.view)

    def _update_properties_dock(self):
        sel=self.scene.selectedItems();html="";edit_en=False;tip="item"
        if len(sel)==1:
            item=sel[0];props=item.get_data();item_type=type(item).__name__.replace("Graphics","").replace("Item","");tip=item_type.lower();edit_en=True
            def fmt(txt,mc=25):
                if not txt:return f"<i style='color:{COLOR_TEXT_SECONDARY};'>(none)</i>"
                esc=html.escape(txt);l1=esc.split('\n')[0];return l1[:mc]+"&hellip;" if len(l1)>mc or '\n' in esc else l1
            rows="";cval=props.get('color');defc=COLOR_ITEM_STATE_DEFAULT_BG
            if isinstance(item,GraphicsTransitionItem):defc=COLOR_ITEM_TRANSITION_DEFAULT
            elif isinstance(item,GraphicsCommentItem):defc=COLOR_ITEM_COMMENT_BG
            eff_c=cval if cval else defc;qc=QColor(eff_c);tc=COLOR_TEXT_PRIMARY if qc.lightnessF()>0.5 else COLOR_TEXT_ON_ACCENT
            cdisp=html.escape(cval) if cval else f"<i style='color:{COLOR_TEXT_SECONDARY};'>Default ({defc})</i>"
            cs=f"background-color:{eff_c};color:{tc};padding:1px 4px;border-radius:2px;display:inline-block;"
            tds="style='font-weight:bold;padding-right:8px;vertical-align:top;'"
            if isinstance(item,GraphicsStateItem):
                rows+=f"<tr><td {tds}>Name:</td><td>{html.escape(props['name'])}</td></tr>";rows+=f"<tr><td {tds}>Initial:</td><td>{'Yes' if props['is_initial'] else 'No'}</td></tr>";rows+=f"<tr><td {tds}>Final:</td><td>{'Yes' if props['is_final'] else 'No'}</td></tr>";rows+=f"<tr><td {tds}>Color:</td><td><span style='{cs}'>{cdisp}</span></td></tr>";rows+=f"<tr><td {tds}>Entry:</td><td>{fmt(props.get('entry_action'))}</td></tr>";rows+=f"<tr><td {tds}>During:</td><td>{fmt(props.get('during_action'))}</td></tr>";rows+=f"<tr><td {tds}>Exit:</td><td>{fmt(props.get('exit_action'))}</td></tr>"
                if props.get('description'):rows+=f"<tr><td {tds}>Desc:</td><td>{fmt(props.get('description'),50)}</td></tr>"
            elif isinstance(item,GraphicsTransitionItem):
                lbl_p=[];e=props.get('event');c=props.get('condition');a=props.get('action')
                if e:lbl_p.append(html.escape(e));
                if c:lbl_p.append(f"[{html.escape(c)}]");
                if a:lbl_p.append(f"/{{{fmt(a,15)}}}")
                flbl=" ".join(lbl_p) if lbl_p else f"<i style='color:{COLOR_TEXT_SECONDARY};'>(No Label)</i>"
                rows+=f"<tr><td {tds}>Label:</td><td style='font-size:8pt;'>{flbl}</td></tr>";rows+=f"<tr><td {tds}>From:</td><td>{html.escape(props['source'])}</td></tr>";rows+=f"<tr><td {tds}>To:</td><td>{html.escape(props['target'])}</td></tr>";rows+=f"<tr><td {tds}>Color:</td><td><span style='{cs}'>{cdisp}</span></td></tr>";rows+=f"<tr><td {tds}>Curve:</td><td>B={props.get('control_offset_x',0):.0f}, S={props.get('control_offset_y',0):.0f}</td></tr>"
                if props.get('description'):rows+=f"<tr><td {tds}>Desc:</td><td>{fmt(props.get('description'),50)}</td></tr>"
            elif isinstance(item,GraphicsCommentItem):rows+=f"<tr><td {tds}>Text:</td><td>{fmt(props['text'],60)}</td></tr>"
            else:rows="<tr><td>Unknown Item Type</td></tr>"
            html=f"""<div style='font-family:"{APP_FONT_FAMILY}";font-size:9pt;line-height:1.5;'><h4 style='margin:0 0 8px 0;padding-bottom:4px;color:{COLOR_ACCENT_PRIMARY};border-bottom:1px solid {COLOR_BORDER_LIGHT};'>Type: {item_type}</h4><table style='width:100%;border-collapse:collapse;table-layout:fixed;'><col style="width:70px;"/><col/>{rows}</table></div>"""
        elif len(sel)>1:html=f"<i><b>{len(sel)} items selected.</b><br>Select single item for properties.</i>";tip=f"{len(sel)} items"
        else:html=f"<i>No item selected.</i><br/><small style='color:{COLOR_TEXT_SECONDARY};'>Click item or use tools.</small>"
        self.pel.setText(html);self.peb.setEnabled(edit_en);self.peb.setToolTip(f"Edit details of {tip}" if edit_en else "Select single item")

    def _on_edit_selected_item_properties_from_dock(self): sel=self.scene.selectedItems();
                                                          if len(sel)==1: self.scene.edit_item_properties(sel[0])
    def log_message(self,message:str):ts=QTime.currentTime().toString('hh:mm:ss.zzz');self.lo.append(f"<span style='color:{COLOR_TEXT_SECONDARY};'>[{ts}]</span> {html.escape(message)}");self.lo.verticalScrollBar().setValue(self.lo.verticalScrollBar().maximum());self.sl.setText(message.split('\n')[0][:120])
    def _update_window_title(self):title=APP_NAME+(" - "+os.path.basename(self.current_file_path) if self.current_file_path else " - Untitled")+"[*]";self.setWindowTitle(title)
    def _update_save_actions_enable_state(self):self.save_action.setEnabled(self.isWindowModified())
    def _update_undo_redo_actions_enable_state(self):self.undo_action.setEnabled(self.undo_stack.canUndo());self.redo_action.setEnabled(self.undo_stack.canRedo());self.undo_action.setText(f"&Undo {self.undo_stack.undoText()}" if self.undo_stack.canUndo() else "&Undo");self.redo_action.setText(f"&Redo {self.undo_stack.redoText()}" if self.undo_stack.canRedo() else "&Redo")
    def _update_matlab_status_display(self,connected,message):txt=f"MATLAB: {'Connected' if connected else 'Not Connected'}";tip=f"MATLAB Status: {message}";self.msl.setText(txt);self.msl.setToolTip(tip);style="font-weight:bold;padding:0px 5px;"+(f"color:#2E7D32;" if connected else f"color:#C62828;");self.msl.setStyleSheet(style);self.log_message(f"MATLAB Conn: {message}");self._update_matlab_actions_enabled_state()
    def _update_matlab_actions_enabled_state(self):conn=self.matlab_connection.connected;self.export_simulink_action.setEnabled(conn);self.run_simulation_action.setEnabled(conn);self.generate_code_action.setEnabled(conn)
    def _start_matlab_operation(self,op_name):self.log_message(f"MATLAB Op: {op_name} starting...");self.sl.setText(f"Running: {op_name}...");self.pb.setVisible(True);self.set_ui_enabled_for_matlab_op(False)
    def _finish_matlab_operation(self):self.pb.setVisible(False);self.sl.setText("Ready");self.set_ui_enabled_for_matlab_op(True);self.log_message("MATLAB Op: Finished.")
    def set_ui_enabled_for_matlab_op(self,enabled:bool):self.menuBar().setEnabled(enabled);
                                                        for c in self.findChildren(QToolBar):c.setEnabled(enabled)
                                                        if self.centralWidget():self.centralWidget().setEnabled(enabled)
                                                        for n in ["ToolsDock","PropertiesDock","LogDock"]: d=self.findChild(QDockWidget,n);
                                                                                                           if d:d.setEnabled(enabled)
    def _handle_matlab_modelgen_or_sim_finished(self,success,message,data):
        self._finish_matlab_operation();self.log_message(f"MATLAB Result ({'OK' if success else 'FAIL'}): {message}")
        if success:
            if "Model generation" in message and data: self.last_generated_model_path=data;QMessageBox.information(self,"Simulink Model Gen",f"Model generated:\n{data}")
            elif "Simulation" in message: QMessageBox.information(self,"Sim Complete",f"MATLAB simulation finished.\n{message}")
        else: QMessageBox.warning(self,"MATLAB Op Failed",message)
    def _handle_matlab_codegen_finished(self,success,message,output_dir):
        self._finish_matlab_operation();self.log_message(f"MATLAB Code Gen ({'OK' if success else 'FAIL'}): {message}")
        if success and output_dir:
            mb=QMessageBox(self);mb.setIcon(QMessageBox.Information);mb.setWindowTitle("Code Gen Successful");mb.setTextFormat(Qt.RichText);ad=os.path.abspath(output_dir)
            mb.setText(f"Code gen done.<br/>Output: <a href='file:///{ad}'>{ad}</a>");mb.setTextInteractionFlags(Qt.TextBrowserInteraction)
            ob=mb.addButton("Open Directory",QMessageBox.ActionRole);mb.addButton(QMessageBox.Ok);mb.exec_()
            if mb.clickedButton()==ob:
                try: QDesktopServices.openUrl(QUrl.fromLocalFile(ad))
                except Exception as e: self.log_message(f"Error opening dir {ad}: {e}");QMessageBox.warning(self,"Error",f"Could not open dir:\n{e}")
        elif not success: QMessageBox.warning(self,"Code Gen Failed",message)
    def _prompt_save_if_dirty(self)->bool:
        if not self.isWindowModified():return True
        name=os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply=QMessageBox.question(self,"Save Changes?",f"Doc '{name}' has unsaved changes.\nSave?",QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Save)
        if reply==QMessageBox.Save:return self.on_save_file()
        return reply!=QMessageBox.Cancel
    def on_new_file(self,silent=False):
        if not silent and not self._prompt_save_if_dirty():return False
        self.scene.clear();self.scene.setSceneRect(0,0,6000,4500);self.current_file_path=None;self.last_generated_model_path=None;self.undo_stack.clear();self.scene.set_dirty(False)
        self._update_window_title();self._update_undo_redo_actions_enable_state()
        if not silent:self.log_message("New diagram.");self.view.resetTransform()
        self.view.centerOn(self.scene.sceneRect().center());self.select_mode_action.trigger();return True
    def on_open_file(self):
        if not self._prompt_save_if_dirty():return
        sd=os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath();fp,_=QFileDialog.getOpenFileName(self,"Open BSM File",sd,FILE_FILTER)
        if fp:
            self.log_message(f"Opening: {fp}")
            if self._load_from_path(fp):
                self.current_file_path=fp;self.last_generated_model_path=None;self.undo_stack.clear();self.scene.set_dirty(False);self._update_window_title();self._update_undo_redo_actions_enable_state();self.log_message(f"Opened: {fp}")
                b=self.scene.itemsBoundingRect();
                if not b.isEmpty():self.view.fitInView(b.adjusted(-50,-50,50,50),Qt.KeepAspectRatio)
                else:self.view.resetTransform();self.view.centerOn(self.scene.sceneRect().center())
            else:QMessageBox.critical(self,"Error Opening",f"Could not load: {fp}");self.log_message(f"Failed open: {fp}")
    def _load_from_path(self,file_path):
        try:
            with open(file_path,'r',encoding='utf-8') as f:data=json.load(f)
            if not isinstance(data,dict) or ('states' not in data or 'transitions' not in data):self.log_message(f"Error: Invalid BSM format: {file_path}.");return False
            self.scene.load_diagram_data(data);return True
        except Exception as e:self.log_message(f"Error loading {file_path}: {type(e).__name__}: {e}");return False
    def on_save_file(self)->bool:return self._save_to_path(self.current_file_path) if self.current_file_path else self.on_save_file_as()
    def on_save_file_as(self)->bool:
        sp=self.current_file_path if self.current_file_path else os.path.join(QDir.homePath(),"untitled"+FILE_EXTENSION);fp,_=QFileDialog.getSaveFileName(self,"Save BSM As",sp,FILE_FILTER)
        if fp:
            if not fp.lower().endswith(FILE_EXTENSION):fp+=FILE_EXTENSION
            if self._save_to_path(fp):self.current_file_path=fp;self.scene.set_dirty(False);self._update_window_title();return True
        return False
    def _save_to_path(self,file_path)->bool:
        sf=QSaveFile(file_path)
        if not sf.open(QIODevice.WriteOnly|QIODevice.Text):err=sf.errorString();self.log_message(f"Error open save {file_path}: {err}");QMessageBox.critical(self,"Save Error",f"Failed open file:\n{err}");return False
        try:
            data=self.scene.get_diagram_data();json_data=json.dumps(data,indent=4,ensure_ascii=False)
            if sf.write(json_data.encode('utf-8'))==-1 or not sf.commit():err=sf.errorString();self.log_message(f"Error write/commit {file_path}: {err}");QMessageBox.critical(self,"Save Error",f"Failed save file:\n{err}");sf.cancelWriting();return False
            self.log_message(f"File saved: {file_path}");return True
        except Exception as e:self.log_message(f"Error saving {file_path}: {type(e).__name__}: {e}");QMessageBox.critical(self,"Save Error",f"Error during save:\n{e}");sf.cancelWriting();return False
    def on_select_all(self):self.scene.select_all()
    def on_delete_selected(self):self.scene.delete_selected_items()
    def on_export_diagram(self): # NEW METHOD
        if not self.scene.items(): QMessageBox.information(self,"Empty Diagram","Nothing to export."); return
        def_fn="diagram_export";
        if self.current_file_path:base=os.path.splitext(os.path.basename(self.current_file_path))[0];def_fn=base+"_diagram"
        filters=["PNG Image (*.png)","JPEG Image (*.jpg *.jpeg)","Scalable Vector Graphics (*.svg)","PDF Document (*.pdf)","All Files (*)"]
        fp,sel_f=QFileDialog.getSaveFileName(self,"Export Diagram As",os.path.join(os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath(),def_fn),";;".join(filters))
        if not fp:return
        if sel_f==filters[0] and not fp.lower().endswith(".png"):fp+=".png"
        elif sel_f==filters[1] and not (fp.lower().endswith(".jpg") or fp.lower().endswith(".jpeg")):fp+=".jpg"
        elif sel_f==filters[2] and not fp.lower().endswith(".svg"):fp+=".svg"
        elif sel_f==filters[3] and not fp.lower().endswith(".pdf"):fp+=".pdf"
        self.log_message(f"Exporting to: {fp}");QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            items_r=self.scene.itemsBoundingRect();
            if items_r.isEmpty():QMessageBox.warning(self,"Export Error","No diagram bounds.");return
            pad=50;target_r=items_r.adjusted(-pad,-pad,pad,pad)
            if fp.lower().endswith((".png",".jpg",".jpeg")):
                sf=2.0;img_w=int(target_r.width()*sf);img_h=int(target_r.height()*sf);min_d=500
                if img_w<min_d and target_r.width()>0:img_w=min_d;img_h=int(min_d*(target_r.height()/target_r.width()))
                elif img_h<min_d and target_r.height()>0:img_h=min_d;img_w=int(min_d*(target_r.width()/target_r.height()))
                if img_w<=0 or img_h<=0:img_w=min_d;img_h=min_d
                img=QImage(img_w,img_h,QImage.Format_ARGB32_Premultiplied);img.fill(Qt.transparent if fp.lower().endswith(".png") else Qt.white)
                painter=QPainter(img);painter.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform)
                if not (fp.lower().endswith(".png") and self.scene.backgroundBrush().style()==Qt.NoBrush):painter.fillRect(img.rect(),self.scene.backgroundBrush())
                self.scene.render(painter,QRectF(img.rect()),target_r);painter.end()
                if not img.save(fp):raise IOError(f"Failed to save image: {fp}")
            elif fp.lower().endswith(".svg"):
                svg_gen=QSvgGenerator();svg_gen.setFileName(fp);svg_gen.setSize(QSize(int(target_r.width()),int(target_r.height())));svg_gen.setViewBox(target_r);svg_gen.setTitle("BSM Diagram");svg_gen.setDescription(f"Exported from {APP_NAME}")
                painter=QPainter(svg_gen);self.scene.render(painter);painter.end()
            elif fp.lower().endswith(".pdf"):
                printer=QPrinter(QPrinter.HighResolution);printer.setOutputFormat(QPrinter.PdfFormat);printer.setOutputFileName(fp)
                printer.setPageSize(QPageSize(QPageSize.A4));printer.setPageMargins(15,15,15,15,QPrinter.Millimeter)
                painter=QPainter(printer);page_r_p=painter.viewport();xs=page_r_p.width()/target_r.width();ys=page_r_p.height()/target_r.height();scale=min(xs,ys)
                painter.save();painter.translate(page_r_p.x()+(page_r_p.width()-target_r.width()*scale)/2,page_r_p.y()+(page_r_p.height()-target_r.height()*scale)/2);painter.scale(scale,scale);painter.translate(-target_r.topLeft())
                self.scene.render(painter);painter.restore();painter.end()
            self.log_message(f"Diagram exported: {fp}");QMessageBox.information(self,"Export Successful",f"Diagram exported to:\n{fp}")
        except Exception as e:self.log_message(f"Error exporting: {e}");QMessageBox.critical(self,"Export Error",f"Could not export:\n{str(e)}")
        finally:QApplication.restoreOverrideCursor()
    def on_export_simulink(self):
        if not self.matlab_connection.connected:QMessageBox.warning(self,"MATLAB Not Connected","Configure MATLAB.");return
        dlg=QDialog(self);dlg.setWindowTitle("Export to Simulink");dlg.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp,"->M",target_size=self.dialog_button_icon_size));layout=QFormLayout(dlg);layout.setSpacing(8);layout.setContentsMargins(10,10,10,10)
        name_def="BSM_Model";bis=self.dialog_button_icon_size
        if self.current_file_path:base=os.path.splitext(os.path.basename(self.current_file_path))[0];name_def="".join(c if c.isalnum() or c=='_' else '_' for c in base);if not name_def or not name_def[0].isalpha():name_def="Model_"+name_def
        ne=QLineEdit(name_def);ne.setPlaceholderText("Simulink model name");layout.addRow("Model Name:",ne);def_out=os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath();oe=QLineEdit(def_out)
        br=QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw",target_size=bis)," Browse...");br.setIconSize(bis);br.clicked.connect(lambda:oe.setText(QFileDialog.getExistingDirectory(dlg,"Select Output Dir",oe.text()) or oe.text()))
        dl=QHBoxLayout();dl.addWidget(oe,1);dl.addWidget(br);layout.addRow("Output Dir:",dl);btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);btns.accepted.connect(dlg.accept);btns.rejected.connect(dlg.reject);layout.addRow(btns);dlg.setMinimumWidth(450)
        if dlg.exec_()==QDialog.Accepted:
            name=ne.text().strip();out_dir=oe.text().strip()
            if not name or not out_dir:QMessageBox.warning(self,"Input Error","Model name & output dir required.");return
            if not name[0].isalpha() or not all(c.isalnum() or c=='_' for c in name):QMessageBox.warning(self,"Invalid Name","Model name: letter start, alnum/underscores.");return
            if not os.path.exists(out_dir):
                try:os.makedirs(out_dir,exist_ok=True)
                except OSError as e:QMessageBox.critical(self,"Dir Error",f"Could not create dir:\n{e}");return
            data=self.scene.get_diagram_data()
            if not data['states']:QMessageBox.information(self,"Empty Diagram","No states to export.");return
            self._start_matlab_operation(f"Exporting '{name}' to Simulink");self.matlab_connection.generate_simulink_model(data['states'],data['transitions'],out_dir,name)
    def on_run_simulation(self):
        if not self.matlab_connection.connected:QMessageBox.warning(self,"MATLAB Not Connected","MATLAB not connected.");return
        def_dir=os.path.dirname(self.last_generated_model_path) if self.last_generated_model_path else (os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath())
        path,_=QFileDialog.getOpenFileName(self,"Select Simulink Model",def_dir,"Simulink Models (*.slx);;All Files (*)")
        if not path:return
        self.last_generated_model_path=path;time,ok=QInputDialog.getDouble(self,"Sim Time","Stop time (s):",10.0,0.001,86400.0,3)
        if not ok:return
        self._start_matlab_operation(f"Simulating '{os.path.basename(path)}'");self.matlab_connection.run_simulation(path,time)
    def on_generate_code(self):
        if not self.matlab_connection.connected:QMessageBox.warning(self,"MATLAB Not Connected","MATLAB not connected.");return
        def_dir=os.path.dirname(self.last_generated_model_path) if self.last_generated_model_path else (os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath())
        path,_=QFileDialog.getOpenFileName(self,"Select Simulink Model for Code Gen",def_dir,"Simulink Models (*.slx);;All Files (*)")
        if not path:return
        self.last_generated_model_path=path;bis=self.dialog_button_icon_size;dlg=QDialog(self);dlg.setWindowTitle("Code Gen Options");dlg.setWindowIcon(get_standard_icon(QStyle.SP_DialogSaveButton,"Cde",target_size=bis));layout=QFormLayout(dlg);layout.setSpacing(8);layout.setContentsMargins(10,10,10,10)
        lang=QComboBox();lang.addItems(["C","C++"]);lang.setCurrentText("C++");layout.addRow("Target Language:",lang);def_out=os.path.dirname(path);oe=QLineEdit(def_out);oe.setPlaceholderText("Base dir for code")
        br=QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw",target_size=bis)," Browse...");br.setIconSize(bis);br.clicked.connect(lambda:oe.setText(QFileDialog.getExistingDirectory(dlg,"Select Base Output Dir",oe.text()) or oe.text()))
        dl=QHBoxLayout();dl.addWidget(oe,1);dl.addWidget(br);layout.addRow("Base Output Dir:",dl);btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);btns.accepted.connect(dlg.accept);btns.rejected.connect(dlg.reject);layout.addRow(btns);dlg.setMinimumWidth(450)
        if dlg.exec_()==QDialog.Accepted:
            language=lang.currentText();out_base=oe.text().strip()
            if not out_base:QMessageBox.warning(self,"Input Error","Base output dir required.");return
            if not os.path.exists(out_base):
                try:os.makedirs(out_base,exist_ok=True)
                except OSError as e:QMessageBox.critical(self,"Dir Error",f"Could not create dir:\n{e}");return
            self._start_matlab_operation(f"Generating {language} code for '{os.path.basename(path)}'");self.matlab_connection.generate_code(path,language,out_base)
    def on_matlab_settings(self):MatlabSettingsDialog(self.matlab_connection,self).exec_()
    def on_about(self):QMessageBox.about(self,"About "+APP_NAME,f"<h3 style='color:{COLOR_ACCENT_PRIMARY};'>{APP_NAME} v{APP_VERSION}</h3><p>Graphical tool for brain-inspired state machine design. Facilitates creation, visualization, modification of state diagrams, and integrates with MATLAB/Simulink for simulation and C/C++ code generation.</p><p><b>Features:</b><ul><li>Intuitive diagramming (click-to-add, drag-drop).</li><li>Rich property editing with snippets.</li><li>JSON storage ({FILE_EXTENSION}).</li><li>Undo/Redo.</li><li>Zoom/Pan canvas with grid/snapping.</li><li><b>MATLAB Integration:</b><ul><li>Auto/manual MATLAB path config.</li><li>Export to Simulink (.slx).</li><li>Run simulations.</li><li>Generate C/C++ code (Embedded Coder).</li></ul></li></ul></p><p><i>Developed by AI Revell Lab. For research/education.</i></p>")
    def closeEvent(self,event:QCloseEvent):
        if self._prompt_save_if_dirty():
            if self.matlab_connection._active_threads:self.log_message(f"Closing. {len(self.matlab_connection._active_threads)} MATLAB process(es) may run in background.")
            event.accept()
        else:event.ignore()

if __name__ == '__main__':
    if hasattr(Qt,'AA_EnableHighDpiScaling'):QApplication.setAttribute(Qt.AA_EnableHighDpiScaling,True)
    if hasattr(Qt,'AA_UseHighDpiPixmaps'):QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps,True)
    app=QApplication(sys.argv);app.setStyleSheet(STYLE_SHEET_GLOBAL);main_win=MainWindow();main_win.show();sys.exit(app.exec_())

