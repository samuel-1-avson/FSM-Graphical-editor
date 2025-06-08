# bsm_designer_project/config.py
# (Changes are additive or modifications)

from PyQt5.QtGui import QColor
import json

# --- Configuration ---
APP_VERSION = "1.7.2" # Incremented version
APP_NAME = "Brain State Machine Designer"
FILE_EXTENSION = ".bsm"
FILE_FILTER = f"Brain State Machine Files (*{FILE_EXTENSION});;All Files (*)"

# --- Execution Environments and Snippets ---
EXECUTION_ENV_PYTHON_GENERIC = "Python (Generic Simulation)"
EXECUTION_ENV_ARDUINO_CPP = "Arduino (C++)"
EXECUTION_ENV_RASPBERRYPI_PYTHON = "RaspberryPi (Python)"
EXECUTION_ENV_MICROPYTHON = "MicroPython"
EXECUTION_ENV_C_GENERIC = "C (Generic Embedded)"

MIME_TYPE_BSM_ITEMS = "application/x-bsm-designer-items"
MIME_TYPE_BSM_TEMPLATE = "application/x-bsm-template"
DEFAULT_EXECUTION_ENV = EXECUTION_ENV_PYTHON_GENERIC

MECHATRONICS_SNIPPETS = {
    # ... (content remains the same) ...
}

FSM_TEMPLATES_BUILTIN = {
    # ... (content remains the same) ...
}


# --- THEME AND COLOR CONFIGURATION ---
# Base Light Theme Colors (current defaults)
COLOR_BACKGROUND_APP_LIGHT = "#ECEFF1"
COLOR_BACKGROUND_LIGHT_LIGHT = "#FAFAFA"
COLOR_BACKGROUND_MEDIUM_LIGHT = "#E0E0E0"
COLOR_BACKGROUND_DARK_LIGHT = "#BDBDBD"
COLOR_BACKGROUND_EDITOR_DARK_LIGHT = "#263238" # Editor remains dark for now
COLOR_TEXT_EDITOR_DARK_PRIMARY_LIGHT = "#ECEFF1"
COLOR_TEXT_EDITOR_DARK_SECONDARY_LIGHT = "#90A4AE"
COLOR_BACKGROUND_DIALOG_LIGHT = "#FFFFFF"
COLOR_TEXT_PRIMARY_LIGHT = "#212121"
COLOR_TEXT_SECONDARY_LIGHT = "#757575"
COLOR_TEXT_ON_ACCENT_LIGHT = "#FFFFFF"
COLOR_ACCENT_PRIMARY_LIGHT_THEME = "#0277BD" # Theme's primary accent
COLOR_ACCENT_PRIMARY_LIGHT_LIGHT_THEME = "#B3E5FC" # Lighter version of accent
COLOR_ACCENT_SECONDARY_LIGHT_THEME = "#FF8F00"
COLOR_ACCENT_SUCCESS_LIGHT = "#4CAF50"
COLOR_ACCENT_WARNING_LIGHT = "#FFC107"
COLOR_ACCENT_ERROR_LIGHT = "#D32F2F"
COLOR_BORDER_LIGHT_LIGHT = "#CFD8DC"
COLOR_BORDER_MEDIUM_LIGHT = "#90A4AE"
COLOR_BORDER_DARK_LIGHT = "#607D8B"
COLOR_ITEM_STATE_DEFAULT_BG_LIGHT = "#E3F2FD"
COLOR_ITEM_STATE_DEFAULT_BORDER_LIGHT = "#64B5F6"
COLOR_ITEM_TRANSITION_DEFAULT_LIGHT = "#00796B"
COLOR_ITEM_COMMENT_BG_LIGHT = "#FFF9C4"
COLOR_ITEM_COMMENT_BORDER_LIGHT = "#FFEE58"
COLOR_GRID_MINOR_LIGHT = "#ECEFF1"
COLOR_GRID_MAJOR_LIGHT = "#CFD8DC"
COLOR_DRAGGABLE_BUTTON_BG_LIGHT = "#E8EAF6"
COLOR_DRAGGABLE_BUTTON_BORDER_LIGHT = "#C5CAE9"

# Base Dark Theme Colors
COLOR_BACKGROUND_APP_DARK = "#263238" # Dark blue-grey
COLOR_BACKGROUND_LIGHT_DARK = "#37474F" # Slightly lighter dark
COLOR_BACKGROUND_MEDIUM_DARK = "#455A64" # Medium dark
COLOR_BACKGROUND_DARK_DARK = "#546E7A" # Darker medium
COLOR_BACKGROUND_EDITOR_DARK_DARK = "#1A2428" # Even darker editor
COLOR_TEXT_EDITOR_DARK_PRIMARY_DARK = "#CFD8DC" # Light grey text
COLOR_TEXT_EDITOR_DARK_SECONDARY_DARK = "#78909C" # Medium grey text
COLOR_BACKGROUND_DIALOG_DARK = "#37474F"
COLOR_TEXT_PRIMARY_DARK = "#ECEFF1" # Very light grey/off-white
COLOR_TEXT_SECONDARY_DARK = "#B0BEC5" # Lighter grey
COLOR_TEXT_ON_ACCENT_DARK = "#FFFFFF" # White for high contrast on accents
COLOR_ACCENT_PRIMARY_DARK_THEME = "#4FC3F7" # Light blue accent
COLOR_ACCENT_PRIMARY_LIGHT_DARK_THEME = "#81D4FA" # Even lighter blue
COLOR_ACCENT_SECONDARY_DARK_THEME = "#FFB74D" # Light orange accent
COLOR_ACCENT_SUCCESS_DARK = "#81C784" # Light green
COLOR_ACCENT_WARNING_DARK = "#FFD54F" # Light yellow/amber
COLOR_ACCENT_ERROR_DARK = "#E57373" # Light red
COLOR_BORDER_LIGHT_DARK = "#546E7A"
COLOR_BORDER_MEDIUM_DARK = "#78909C"
COLOR_BORDER_DARK_DARK = "#90A4AE" # Lighter borders for dark theme
COLOR_ITEM_STATE_DEFAULT_BG_DARK = "#4A6572" # Darker blue-grey for states
COLOR_ITEM_STATE_DEFAULT_BORDER_DARK = "#78909C"
COLOR_ITEM_TRANSITION_DEFAULT_DARK = "#4DB6AC" # Tealish
COLOR_ITEM_COMMENT_BG_DARK = "#424242" # Dark grey for comments
COLOR_ITEM_COMMENT_BORDER_DARK = "#616161"
COLOR_GRID_MINOR_DARK = "#455A64"
COLOR_GRID_MAJOR_DARK = "#546E7A"
COLOR_DRAGGABLE_BUTTON_BG_DARK = "#37474F"
COLOR_DRAGGABLE_BUTTON_BORDER_DARK = "#546E7A"

# --- Dynamically set colors based on a (future) theme setting ---
# For now, we will keep the original names and modify their values based on theme.
# This section will be populated by a theme manager or in main.py.
# The global stylesheet will then reference these dynamic names.

COLOR_BACKGROUND_APP = COLOR_BACKGROUND_APP_LIGHT
COLOR_BACKGROUND_LIGHT = COLOR_BACKGROUND_LIGHT_LIGHT
COLOR_BACKGROUND_MEDIUM = COLOR_BACKGROUND_MEDIUM_LIGHT
COLOR_BACKGROUND_DARK = COLOR_BACKGROUND_DARK_LIGHT
COLOR_BACKGROUND_EDITOR_DARK = COLOR_BACKGROUND_EDITOR_DARK_LIGHT
COLOR_TEXT_EDITOR_DARK_PRIMARY = COLOR_TEXT_EDITOR_DARK_PRIMARY_LIGHT
COLOR_TEXT_EDITOR_DARK_SECONDARY = COLOR_TEXT_EDITOR_DARK_SECONDARY_LIGHT
COLOR_BACKGROUND_DIALOG = COLOR_BACKGROUND_DIALOG_LIGHT
COLOR_TEXT_PRIMARY = COLOR_TEXT_PRIMARY_LIGHT
COLOR_TEXT_SECONDARY = COLOR_TEXT_SECONDARY_LIGHT
COLOR_TEXT_ON_ACCENT = COLOR_TEXT_ON_ACCENT_LIGHT
COLOR_ACCENT_PRIMARY = COLOR_ACCENT_PRIMARY_LIGHT_THEME
COLOR_ACCENT_PRIMARY_LIGHT = COLOR_ACCENT_PRIMARY_LIGHT_LIGHT_THEME
COLOR_ACCENT_SECONDARY = COLOR_ACCENT_SECONDARY_LIGHT_THEME
COLOR_ACCENT_SUCCESS = COLOR_ACCENT_SUCCESS_LIGHT
COLOR_ACCENT_WARNING = COLOR_ACCENT_WARNING_LIGHT
COLOR_ACCENT_ERROR = COLOR_ACCENT_ERROR_LIGHT
COLOR_BORDER_LIGHT = COLOR_BORDER_LIGHT_LIGHT
COLOR_BORDER_MEDIUM = COLOR_BORDER_MEDIUM_LIGHT
COLOR_BORDER_DARK = COLOR_BORDER_DARK_LIGHT
COLOR_ITEM_STATE_DEFAULT_BG = COLOR_ITEM_STATE_DEFAULT_BG_LIGHT
COLOR_ITEM_STATE_DEFAULT_BORDER = COLOR_ITEM_STATE_DEFAULT_BORDER_LIGHT
COLOR_ITEM_STATE_SELECTION_BG = "#FFECB3" # Keep this one theme-agnostic for now or derive
COLOR_ITEM_STATE_SELECTION_BORDER = COLOR_ACCENT_SECONDARY # Could also be themed
COLOR_ITEM_TRANSITION_DEFAULT = COLOR_ITEM_TRANSITION_DEFAULT_LIGHT
COLOR_ITEM_TRANSITION_SELECTION = "#B2DFDB" # Keep or derive
COLOR_ITEM_COMMENT_BG = COLOR_ITEM_COMMENT_BG_LIGHT
COLOR_ITEM_COMMENT_BORDER = COLOR_ITEM_COMMENT_BORDER_LIGHT
COLOR_GRID_MINOR = COLOR_GRID_MINOR_LIGHT
COLOR_GRID_MAJOR = COLOR_GRID_MAJOR_LIGHT
COLOR_SNAP_GUIDELINE = QColor(Qt.red) # This should be a setting

COLOR_DRAGGABLE_BUTTON_BG = COLOR_DRAGGABLE_BUTTON_BG_LIGHT
COLOR_DRAGGABLE_BUTTON_BORDER = COLOR_DRAGGABLE_BUTTON_BORDER_LIGHT
COLOR_DRAGGABLE_BUTTON_HOVER_BG = "#B9D9EB" # Theme this
COLOR_DRAGGABLE_BUTTON_HOVER_BORDER = COLOR_ACCENT_PRIMARY # Uses dynamic accent
COLOR_DRAGGABLE_BUTTON_PRESSED_BG = "#98BAD6" # Theme this

COLOR_PY_SIM_STATE_ACTIVE = QColor(COLOR_ACCENT_SUCCESS) # Uses dynamic success
COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH = 2.5

APP_FONT_FAMILY = "Segoe UI, Arial, sans-serif"
APP_FONT_SIZE_STANDARD = "9pt"
APP_FONT_SIZE_SMALL = "8pt"
APP_FONT_SIZE_EDITOR = "10pt"

# Default item visual properties (can be overridden by settings or item-specific props)
DEFAULT_STATE_SHAPE = "rectangle" # "rectangle", "ellipse"
DEFAULT_STATE_BORDER_STYLE = Qt.SolidLine # Qt.SolidLine, Qt.DashLine, Qt.DotLine
DEFAULT_STATE_BORDER_WIDTH = 1.8
DEFAULT_TRANSITION_LINE_STYLE = Qt.SolidLine
DEFAULT_TRANSITION_LINE_WIDTH = 2.2
DEFAULT_TRANSITION_ARROWHEAD = "filled" # "filled", "open", "none"


# Function to update colors based on theme (called from main.py)
def DYNAMIC_UPDATE_COLORS_FROM_THEME(theme_name: str):
    global COLOR_BACKGROUND_APP, COLOR_BACKGROUND_LIGHT, COLOR_BACKGROUND_MEDIUM, \
           COLOR_BACKGROUND_DARK, COLOR_BACKGROUND_EDITOR_DARK, COLOR_TEXT_EDITOR_DARK_PRIMARY, \
           COLOR_TEXT_EDITOR_DARK_SECONDARY, COLOR_BACKGROUND_DIALOG, COLOR_TEXT_PRIMARY, \
           COLOR_TEXT_SECONDARY, COLOR_TEXT_ON_ACCENT, COLOR_ACCENT_PRIMARY, \
           COLOR_ACCENT_PRIMARY_LIGHT, COLOR_ACCENT_SECONDARY, COLOR_ACCENT_SUCCESS, \
           COLOR_ACCENT_WARNING, COLOR_ACCENT_ERROR, COLOR_BORDER_LIGHT, \
           COLOR_BORDER_MEDIUM, COLOR_BORDER_DARK, COLOR_ITEM_STATE_DEFAULT_BG, \
           COLOR_ITEM_STATE_DEFAULT_BORDER, COLOR_ITEM_TRANSITION_DEFAULT, \
           COLOR_ITEM_COMMENT_BG, COLOR_ITEM_COMMENT_BORDER, COLOR_GRID_MINOR, \
           COLOR_GRID_MAJOR, COLOR_DRAGGABLE_BUTTON_BG, COLOR_DRAGGABLE_BUTTON_BORDER, \
           COLOR_DRAGGABLE_BUTTON_HOVER_BG, COLOR_DRAGGABLE_BUTTON_PRESSED_BG, \
           COLOR_PY_SIM_STATE_ACTIVE

    if theme_name == "Dark":
        COLOR_BACKGROUND_APP = COLOR_BACKGROUND_APP_DARK
        COLOR_BACKGROUND_LIGHT = COLOR_BACKGROUND_LIGHT_DARK
        COLOR_BACKGROUND_MEDIUM = COLOR_BACKGROUND_MEDIUM_DARK
        COLOR_BACKGROUND_DARK = COLOR_BACKGROUND_DARK_DARK
        COLOR_BACKGROUND_EDITOR_DARK = COLOR_BACKGROUND_EDITOR_DARK_DARK
        COLOR_TEXT_EDITOR_DARK_PRIMARY = COLOR_TEXT_EDITOR_DARK_PRIMARY_DARK
        COLOR_TEXT_EDITOR_DARK_SECONDARY = COLOR_TEXT_EDITOR_DARK_SECONDARY_DARK
        COLOR_BACKGROUND_DIALOG = COLOR_BACKGROUND_DIALOG_DARK
        COLOR_TEXT_PRIMARY = COLOR_TEXT_PRIMARY_DARK
        COLOR_TEXT_SECONDARY = COLOR_TEXT_SECONDARY_DARK
        COLOR_TEXT_ON_ACCENT = COLOR_TEXT_ON_ACCENT_DARK
        COLOR_ACCENT_PRIMARY = COLOR_ACCENT_PRIMARY_DARK_THEME
        COLOR_ACCENT_PRIMARY_LIGHT = COLOR_ACCENT_PRIMARY_LIGHT_DARK_THEME
        COLOR_ACCENT_SECONDARY = COLOR_ACCENT_SECONDARY_DARK_THEME
        COLOR_ACCENT_SUCCESS = COLOR_ACCENT_SUCCESS_DARK
        COLOR_ACCENT_WARNING = COLOR_ACCENT_WARNING_DARK
        COLOR_ACCENT_ERROR = COLOR_ACCENT_ERROR_DARK
        COLOR_BORDER_LIGHT = COLOR_BORDER_LIGHT_DARK
        COLOR_BORDER_MEDIUM = COLOR_BORDER_MEDIUM_DARK
        COLOR_BORDER_DARK = COLOR_BORDER_DARK_DARK
        COLOR_ITEM_STATE_DEFAULT_BG = COLOR_ITEM_STATE_DEFAULT_BG_DARK
        COLOR_ITEM_STATE_DEFAULT_BORDER = COLOR_ITEM_STATE_DEFAULT_BORDER_DARK
        COLOR_ITEM_TRANSITION_DEFAULT = COLOR_ITEM_TRANSITION_DEFAULT_DARK
        COLOR_ITEM_COMMENT_BG = COLOR_ITEM_COMMENT_BG_DARK
        COLOR_ITEM_COMMENT_BORDER = COLOR_ITEM_COMMENT_BORDER_DARK
        COLOR_GRID_MINOR = COLOR_GRID_MINOR_DARK
        COLOR_GRID_MAJOR = COLOR_GRID_MAJOR_DARK
        COLOR_DRAGGABLE_BUTTON_BG = COLOR_DRAGGABLE_BUTTON_BG_DARK
        COLOR_DRAGGABLE_BUTTON_BORDER = COLOR_DRAGGABLE_BUTTON_BORDER_DARK
        COLOR_DRAGGABLE_BUTTON_HOVER_BG = QColor(COLOR_DRAGGABLE_BUTTON_BG_DARK).lighter(120).name()
        COLOR_DRAGGABLE_BUTTON_PRESSED_BG = QColor(COLOR_DRAGGABLE_BUTTON_BG_DARK).lighter(140).name()
        COLOR_PY_SIM_STATE_ACTIVE = QColor(COLOR_ACCENT_SUCCESS_DARK)
    else: # Default to Light theme
        COLOR_BACKGROUND_APP = COLOR_BACKGROUND_APP_LIGHT
        COLOR_BACKGROUND_LIGHT = COLOR_BACKGROUND_LIGHT_LIGHT
        COLOR_BACKGROUND_MEDIUM = COLOR_BACKGROUND_MEDIUM_LIGHT
        COLOR_BACKGROUND_DARK = COLOR_BACKGROUND_DARK_LIGHT
        COLOR_BACKGROUND_EDITOR_DARK = COLOR_BACKGROUND_EDITOR_DARK_LIGHT
        COLOR_TEXT_EDITOR_DARK_PRIMARY = COLOR_TEXT_EDITOR_DARK_PRIMARY_LIGHT
        COLOR_TEXT_EDITOR_DARK_SECONDARY = COLOR_TEXT_EDITOR_DARK_SECONDARY_LIGHT
        COLOR_BACKGROUND_DIALOG = COLOR_BACKGROUND_DIALOG_LIGHT
        COLOR_TEXT_PRIMARY = COLOR_TEXT_PRIMARY_LIGHT
        COLOR_TEXT_SECONDARY = COLOR_TEXT_SECONDARY_LIGHT
        COLOR_TEXT_ON_ACCENT = COLOR_TEXT_ON_ACCENT_LIGHT
        COLOR_ACCENT_PRIMARY = COLOR_ACCENT_PRIMARY_LIGHT_THEME
        COLOR_ACCENT_PRIMARY_LIGHT = COLOR_ACCENT_PRIMARY_LIGHT_LIGHT_THEME
        COLOR_ACCENT_SECONDARY = COLOR_ACCENT_SECONDARY_LIGHT_THEME
        COLOR_ACCENT_SUCCESS = COLOR_ACCENT_SUCCESS_LIGHT
        COLOR_ACCENT_WARNING = COLOR_ACCENT_WARNING_LIGHT
        COLOR_ACCENT_ERROR = COLOR_ACCENT_ERROR_LIGHT
        COLOR_BORDER_LIGHT = COLOR_BORDER_LIGHT_LIGHT
        COLOR_BORDER_MEDIUM = COLOR_BORDER_MEDIUM_LIGHT
        COLOR_BORDER_DARK = COLOR_BORDER_DARK_LIGHT
        COLOR_ITEM_STATE_DEFAULT_BG = COLOR_ITEM_STATE_DEFAULT_BG_LIGHT
        COLOR_ITEM_STATE_DEFAULT_BORDER = COLOR_ITEM_STATE_DEFAULT_BORDER_LIGHT
        COLOR_ITEM_TRANSITION_DEFAULT = COLOR_ITEM_TRANSITION_DEFAULT_LIGHT
        COLOR_ITEM_COMMENT_BG = COLOR_ITEM_COMMENT_BG_LIGHT
        COLOR_ITEM_COMMENT_BORDER = COLOR_ITEM_COMMENT_BORDER_LIGHT
        COLOR_GRID_MINOR = COLOR_GRID_MINOR_LIGHT
        COLOR_GRID_MAJOR = COLOR_GRID_MAJOR_LIGHT
        COLOR_DRAGGABLE_BUTTON_BG = COLOR_DRAGGABLE_BUTTON_BG_LIGHT
        COLOR_DRAGGABLE_BUTTON_BORDER = COLOR_DRAGGABLE_BUTTON_BORDER_LIGHT
        COLOR_DRAGGABLE_BUTTON_HOVER_BG = "#B9D9EB"
        COLOR_DRAGGABLE_BUTTON_PRESSED_BG = "#98BAD6"
        COLOR_PY_SIM_STATE_ACTIVE = QColor(COLOR_ACCENT_SUCCESS_LIGHT)
    
    # Update other colors that depend on the primary accents etc.
    global COLOR_ITEM_STATE_SELECTION_BG, COLOR_ITEM_STATE_SELECTION_BORDER, \
           COLOR_ITEM_TRANSITION_SELECTION, COLOR_SNAP_GUIDELINE

    COLOR_ITEM_STATE_SELECTION_BG = QColor(COLOR_ACCENT_SECONDARY).lighter(180).name() if theme_name == "Dark" else "#FFECB3"
    COLOR_ITEM_STATE_SELECTION_BORDER = COLOR_ACCENT_SECONDARY
    COLOR_ITEM_TRANSITION_SELECTION = QColor(COLOR_ACCENT_PRIMARY).lighter(160).name() if theme_name == "Dark" else "#B2DFDB"
    COLOR_SNAP_GUIDELINE = QColor(COLOR_ACCENT_ERROR) if theme_name == "Dark" else QColor(Qt.red)

# Initial call to set default (Light) theme colors
DYNAMIC_UPDATE_COLORS_FROM_THEME("Light")


STYLE_SHEET_GLOBAL = f"""
    /* Existing styles will be dynamically updated or replaced */
    /* This string will be REBUILT by main.py when theme changes */
"""

def GET_CURRENT_STYLE_SHEET():
    # This function will now generate the stylesheet based on current dynamic colors
    # This helps to avoid a massive static string and makes it theme-aware
    return f"""
    QWidget {{
        font-family: {APP_FONT_FAMILY};
        font-size: {APP_FONT_SIZE_STANDARD};
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
    }}
    QMainWindow {{
        background-color: {COLOR_BACKGROUND_APP}; /* Dynamic */
    }}
    QDockWidget::title {{
        background-color: {QColor(COLOR_BACKGROUND_MEDIUM).darker(105).name()}; /* Dynamic */
        padding: 6px 10px; 
        border: 1px solid {COLOR_BORDER_LIGHT}; /* Dynamic */
        border-bottom: 2px solid {COLOR_ACCENT_PRIMARY}; /* Dynamic */
        font-weight: bold;
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
        border-top-left-radius: 3px; 
        border-top-right-radius: 3px;
    }}
    QDockWidget {{
        border: 1px solid {COLOR_BORDER_LIGHT}; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; /* Ensure dock text color is themed */
    }}
    QDockWidget QWidget {{ /* Ensure widgets inside docks also get base text color */
        color: {COLOR_TEXT_PRIMARY};
    }}
    QDockWidget::close-button, QDockWidget::float-button {{
        subcontrol-position: top right;
        subcontrol-origin: margin;
        position: absolute;
        top: 1px; right: 4px; padding: 1px; 
        border-radius: 2px;
        /* Icons for these are usually system-provided, color might be hard to theme via QSS only */
    }}
    QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
        background-color: {COLOR_BACKGROUND_DARK}; /* Dynamic */
    }}
    QToolBar {{
        background-color: {COLOR_BACKGROUND_MEDIUM}; /* Dynamic */
        border-bottom: 1px solid {COLOR_BORDER_LIGHT}; /* Dynamic */
        padding: 2px; 
        spacing: 3px; 
    }}
    QToolButton {{
        background-color: transparent;
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
        padding: 4px 6px; 
        margin: 0px; 
        border: 1px solid transparent;
        border-radius: 3px;
    }}
    QToolButton:hover, QDockWidget#ToolsDock QToolButton:hover {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT}; /* Dynamic */
        border: 1px solid {COLOR_ACCENT_PRIMARY}; /* Dynamic */
        color: {QColor(COLOR_ACCENT_PRIMARY).darker(130).name() if QColor(COLOR_ACCENT_PRIMARY_LIGHT).lightnessF() > 0.6 else COLOR_TEXT_ON_ACCENT};
    }}
    QToolButton:pressed, QDockWidget#ToolsDock QToolButton:pressed {{
        background-color: {COLOR_ACCENT_PRIMARY}; /* Dynamic */
        color: {COLOR_TEXT_ON_ACCENT}; /* Dynamic */
    }}
    QToolButton:checked, QDockWidget#ToolsDock QToolButton:checked {{
        background-color: {COLOR_ACCENT_PRIMARY}; /* Dynamic */
        color: {COLOR_TEXT_ON_ACCENT}; /* Dynamic */
        border: 1px solid {QColor(COLOR_ACCENT_PRIMARY).darker(120).name()}; /* Dynamic */
    }}
    QToolBar QToolButton:disabled {{
        color: {COLOR_TEXT_SECONDARY}; /* Dynamic */
        background-color: transparent;
    }}
    QMenuBar {{
        background-color: {COLOR_BACKGROUND_MEDIUM}; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
        border-bottom: 1px solid {COLOR_BORDER_LIGHT}; /* Dynamic */
        padding: 2px; 
    }}
    QMenuBar::item {{
        background-color: transparent;
        padding: 4px 10px; 
        color: {COLOR_TEXT_PRIMARY}; /* Ensure menu bar item text is themed */
    }}
    QMenuBar::item:selected {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT}; /* Dynamic */
        color: {QColor(COLOR_ACCENT_PRIMARY).darker(130).name() if QColor(COLOR_ACCENT_PRIMARY_LIGHT).lightnessF() > 0.6 else COLOR_TEXT_PRIMARY}; /* Dynamic */
    }}
    QMenuBar::item:pressed {{
        background-color: {COLOR_ACCENT_PRIMARY}; /* Dynamic */
        color: {COLOR_TEXT_ON_ACCENT}; /* Dynamic */
    }}
    QMenu {{
        background-color: {COLOR_BACKGROUND_DIALOG}; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
        border: 1px solid {COLOR_BORDER_MEDIUM}; /* Dynamic */
        border-radius: 3px;
        padding: 4px; 
    }}
    QMenu::item {{
        padding: 5px 25px 5px 25px; 
        border-radius: 3px;
        color: {COLOR_TEXT_PRIMARY}; /* Ensure menu item text is themed */
    }}
    QMenu::item:selected {{
        background-color: {COLOR_ACCENT_PRIMARY}; /* Dynamic */
        color: {COLOR_TEXT_ON_ACCENT}; /* Dynamic */
    }}
    QMenu::separator {{
        height: 1px;
        background: {COLOR_BORDER_LIGHT}; /* Dynamic */
        margin: 4px 6px; 
    }}
    QMenu::icon {{
        padding-left: 5px;
    }}
    QStatusBar {{
        background-color: {COLOR_BACKGROUND_MEDIUM}; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
        border-top: 1px solid {COLOR_BORDER_LIGHT}; /* Dynamic */
        padding: 2px 4px; 
    }}
    QStatusBar::item {{
        border: none;
        margin: 0 2px; 
    }}
    QLabel#StatusLabel, QLabel#MatlabStatusLabel, QLabel#PySimStatusLabel, QLabel#AIChatStatusLabel, QLabel#InternetStatusLabel,
    QLabel#MainOpStatusLabel, QLabel#IdeFileStatusLabel,
    QMainWindow QLabel[objectName$="StatusLabel"],
    QLabel#ZoomStatusLabel
    {{
         padding: 1px 4px; 
         font-size: {APP_FONT_SIZE_SMALL};
         border-radius: 2px;
         color: {COLOR_TEXT_SECONDARY}; /* Default for status labels, specific styles override */
    }}
    QLabel#CpuStatusLabel, QLabel#RamStatusLabel, QLabel#GpuStatusLabel {{
        font-size: {APP_FONT_SIZE_SMALL};
        padding: 1px 4px; 
        min-width: 60px; 
        border: 1px solid {COLOR_BORDER_LIGHT}; /* Dynamic */
        background-color: {COLOR_BACKGROUND_APP}; /* Dynamic */
        border-radius: 2px;
        color: {COLOR_TEXT_SECONDARY}; /* Dynamic */
    }}
    QDialog {{
        background-color: {COLOR_BACKGROUND_DIALOG}; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; /* Ensure dialog text is themed */
    }}
    QDialog QLabel, QDialog QCheckBox, QDialog QRadioButton {{ /* Ensure text in dialogs gets themed color */
        color: {COLOR_TEXT_PRIMARY};
    }}
    QLabel {{ /* General QLabel theming - careful not to override too much */
        color: {COLOR_TEXT_PRIMARY};
        background-color: transparent;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
        background-color: {QColor(COLOR_BACKGROUND_DIALOG).lighter(102 if QColor(COLOR_BACKGROUND_DIALOG).lightnessF() > 0.5 else 115).name()}; /* Dynamic, lighter for light, darker for dark */
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
        border: 1px solid {COLOR_BORDER_MEDIUM}; /* Dynamic */
        border-radius: 3px; 
        padding: 5px 7px; 
        font-size: {APP_FONT_SIZE_STANDARD};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border: 1.5px solid {COLOR_ACCENT_PRIMARY}; /* Dynamic */
        outline: none;
    }}
    QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
        background-color: {COLOR_BACKGROUND_MEDIUM}; /* Dynamic */
        color: {COLOR_TEXT_SECONDARY}; /* Dynamic */
        border-color: {COLOR_BORDER_LIGHT}; /* Dynamic */
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 22px; 
        border-left-width: 1px;
        border-left-color: {COLOR_BORDER_MEDIUM}; /* Dynamic */
        border-left-style: solid;
        border-top-right-radius: 2px;
        border-bottom-right-radius: 2px;
        background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102 if QColor(COLOR_BACKGROUND_LIGHT).lightnessF() > 0.5 else 110).name()}; /* Dynamic */
    }}
    QComboBox::drop-down:hover {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT}; /* Dynamic */
    }}
    QComboBox::down-arrow {{
         image: url(:/icons/arrow_down.png); /* Consider theme-specific icons */
         width: 10px; height:10px; 
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLOR_BACKGROUND_DIALOG}; /* Dynamic */
        border: 1px solid {COLOR_BORDER_MEDIUM}; /* Dynamic */
        selection-background-color: {COLOR_ACCENT_PRIMARY}; /* Dynamic */
        selection-color: {COLOR_TEXT_ON_ACCENT}; /* Dynamic */
        border-radius: 2px;
        padding: 1px;
        color: {COLOR_TEXT_PRIMARY}; /* For non-selected items in dropdown */
    }}
    QPushButton {{
        background-color: {QColor(COLOR_BACKGROUND_MEDIUM).lighter(105).name()}; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
        border: 1px solid {COLOR_BORDER_MEDIUM}; /* Dynamic */
        padding: 6px 15px; 
        border-radius: 4px; 
        min-height: 22px; 
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {QColor(COLOR_BACKGROUND_MEDIUM).name()}; /* Dynamic */
        border-color: {COLOR_BORDER_DARK}; /* Dynamic */
    }}
    QPushButton:pressed {{
        background-color: {QColor(COLOR_BACKGROUND_DARK).name()}; /* Dynamic */
    }}
    QPushButton:disabled {{
        background-color: {QColor(COLOR_BACKGROUND_LIGHT).darker(102 if QColor(COLOR_BACKGROUND_LIGHT).lightnessF() < 0.5 else 95).name()}; /* Dynamic */
        color: {COLOR_TEXT_SECONDARY}; /* Dynamic */
        border-color: {COLOR_BORDER_LIGHT}; /* Dynamic */
    }}
    QDialogButtonBox QPushButton {{
        min-width: 80px; 
    }}
    QDialogButtonBox QPushButton[text="OK"], QDialogButtonBox QPushButton[text="Apply & Close"],
    QDialogButtonBox QPushButton[text="Save"]
    {{
        background-color: {COLOR_ACCENT_PRIMARY}; /* Dynamic */
        color: {COLOR_TEXT_ON_ACCENT}; /* Dynamic */
        border-color: {QColor(COLOR_ACCENT_PRIMARY).darker(120).name()}; /* Dynamic */
        font-weight: bold;
    }}
    QDialogButtonBox QPushButton[text="OK"]:hover, QDialogButtonBox QPushButton[text="Apply & Close"]:hover,
    QDialogButtonBox QPushButton[text="Save"]:hover
    {{
        background-color: {QColor(COLOR_ACCENT_PRIMARY).lighter(110).name()}; /* Dynamic */
    }}
    QDialogButtonBox QPushButton[text="Cancel"], QDialogButtonBox QPushButton[text="Discard"],
    QDialogButtonBox QPushButton[text="Close"]
    {{
        background-color: {COLOR_BACKGROUND_MEDIUM}; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
        border-color: {COLOR_BORDER_MEDIUM}; /* Dynamic */
    }}
    QDialogButtonBox QPushButton[text="Cancel"]:hover, QDialogButtonBox QPushButton[text="Discard"]:hover,
    QDialogButtonBox QPushButton[text="Close"]:hover
    {{
        background-color: {QColor(COLOR_BACKGROUND_MEDIUM).darker(110).name()}; /* Dynamic */
    }}
    QGroupBox {{
        background-color: transparent;
        border: 1px solid {COLOR_BORDER_LIGHT}; /* Dynamic */
        border-radius: 4px; 
        margin-top: 10px; 
        padding: 10px 8px 8px 8px; 
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px; 
        left: 10px; 
        background-color: {COLOR_BACKGROUND_APP}; /* Match app background */
        color: {COLOR_ACCENT_PRIMARY}; /* Dynamic */
        font-weight: bold;
        border-radius: 2px;
    }}
    QTabWidget::pane {{
        border: 1px solid {COLOR_BORDER_LIGHT}; /* Dynamic */
        border-top: none;
        border-bottom-left-radius: 3px;
        border-bottom-right-radius: 3px;
        background-color: {COLOR_BACKGROUND_DIALOG}; /* Dynamic */
        padding: 6px; 
    }}
    QTabBar::tab {{
        background: {COLOR_BACKGROUND_MEDIUM}; /* Dynamic */
        color: {COLOR_TEXT_SECONDARY}; /* Dynamic */
        border: 1px solid {COLOR_BORDER_LIGHT}; /* Dynamic */
        border-bottom-color: {COLOR_BACKGROUND_DIALOG};  /* Match pane bg */
        border-top-left-radius: 3px;
        border-top-right-radius: 3px;
        padding: 6px 15px; 
        margin-right: 1px;
        min-width: 70px; 
    }}
    QTabBar::tab:selected {{
        background: {COLOR_BACKGROUND_DIALOG}; /* Dynamic, match pane bg */
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
        font-weight: bold;
        border-bottom-color: {COLOR_BACKGROUND_DIALOG}; /* Match pane bg */
    }}
    QTabBar::tab:!selected:hover {{
        background: {COLOR_ACCENT_PRIMARY_LIGHT}; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
        border-bottom-color: {COLOR_BORDER_LIGHT};  /* Dynamic */
    }}
    QCheckBox {{
        spacing: 8px; 
        color: {COLOR_TEXT_PRIMARY}; /* Ensure checkbox text is themed */
    }}
    QCheckBox::indicator {{
        width: 14px; 
        height: 14px;
    }}
    QCheckBox::indicator:unchecked {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; /* Dynamic */
        border-radius: 2px;
        background-color: {QColor(COLOR_BACKGROUND_DIALOG).lighter(102 if QColor(COLOR_BACKGROUND_DIALOG).lightnessF() > 0.5 else 110).name()}; /* Dynamic */
    }}
    QCheckBox::indicator:unchecked:hover {{
        border: 1px solid {COLOR_ACCENT_PRIMARY}; /* Dynamic */
    }}
    QCheckBox::indicator:checked {{
        border: 1px solid {QColor(COLOR_ACCENT_PRIMARY).darker(120).name()}; /* Dynamic */
        border-radius: 2px;
        background-color: {COLOR_ACCENT_PRIMARY}; /* Dynamic */
        image: url(:/icons/check.png); /* Consider theme-specific check icon */
    }}
    QCheckBox::indicator:checked:hover {{
        background-color: {QColor(COLOR_ACCENT_PRIMARY).lighter(110).name()}; /* Dynamic */
    }}
    /* Code Editor styles - these typically have their own dark theme */
    QTextEdit#LogOutputWidget, QTextEdit#PySimActionLog, QTextEdit#AIChatDisplay,
    QPlainTextEdit#ActionCodeEditor, QTextEdit#IDEOutputConsole, QPlainTextEdit#StandaloneCodeEditor,
    QTextEdit#SubFSMJsonEditor 
    {{
         font-family: Consolas, 'Courier New', monospace;
         font-size: {APP_FONT_SIZE_EDITOR};
         background-color: {COLOR_BACKGROUND_EDITOR_DARK}; /* Dynamic */
         color: {COLOR_TEXT_EDITOR_DARK_PRIMARY}; /* Dynamic */
         border: 1px solid {COLOR_BORDER_DARK}; /* Dynamic */
         border-radius: 3px;
         padding: 6px; 
         selection-background-color: {QColor(COLOR_ACCENT_PRIMARY).darker(110).name()}; /* Dynamic */
         selection-color: {COLOR_TEXT_ON_ACCENT}; /* Dynamic */
    }}
    QScrollBar:vertical {{
         border: 1px solid {COLOR_BORDER_LIGHT}; /* Dynamic */
         background: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102 if QColor(COLOR_BACKGROUND_LIGHT).lightnessF() > 0.5 else 110).name()}; /* Dynamic */
         width: 14px; 
         margin: 0px;
    }}
    QScrollBar::handle:vertical {{
         background: {COLOR_BORDER_DARK}; /* Dynamic */
         min-height: 25px;
         border-radius: 7px;
    }}
    QScrollBar::handle:vertical:hover {{
         background: {QColor(COLOR_BORDER_DARK).lighter(120).name()}; /* Dynamic */
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
         height: 0px;
         background: transparent;
    }}
    QScrollBar:horizontal {{
         border: 1px solid {COLOR_BORDER_LIGHT}; /* Dynamic */
         background: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102 if QColor(COLOR_BACKGROUND_LIGHT).lightnessF() > 0.5 else 110).name()}; /* Dynamic */
         height: 14px; 
         margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
         background: {COLOR_BORDER_DARK}; /* Dynamic */
         min-width: 25px;
         border-radius: 7px;
    }}
    QScrollBar::handle:horizontal:hover {{
         background: {QColor(COLOR_BORDER_DARK).lighter(120).name()}; /* Dynamic */
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
         width: 0px;
         background: transparent;
    }}

    /* Editor specific scrollbars */
    QTextEdit#LogOutputWidget QScrollBar:vertical, QTextEdit#PySimActionLog QScrollBar:vertical,
    QTextEdit#AIChatDisplay QScrollBar:vertical, QPlainTextEdit#ActionCodeEditor QScrollBar:vertical,
    QTextEdit#IDEOutputConsole QScrollBar:vertical, QPlainTextEdit#StandaloneCodeEditor QScrollBar:vertical,
    QTextEdit#SubFSMJsonEditor QScrollBar:vertical
    {{
         border: 1px solid {COLOR_BORDER_DARK}; /* Dynamic */
         background: {QColor(COLOR_BACKGROUND_EDITOR_DARK).lighter(110).name()}; /* Dynamic */
    }}
    QTextEdit#LogOutputWidget QScrollBar::handle:vertical, QTextEdit#PySimActionLog QScrollBar::handle:vertical,
    QTextEdit#AIChatDisplay QScrollBar::handle:vertical, QPlainTextEdit#ActionCodeEditor QScrollBar::handle:vertical,
    QTextEdit#IDEOutputConsole QScrollBar::handle:vertical, QPlainTextEdit#StandaloneCodeEditor QScrollBar::handle:vertical,
    QTextEdit#SubFSMJsonEditor QScrollBar::handle:vertical
    {{
         background: {COLOR_TEXT_EDITOR_DARK_SECONDARY}; /* Dynamic */
    }}
    QTextEdit#LogOutputWidget QScrollBar::handle:vertical:hover, QTextEdit#PySimActionLog QScrollBar::handle:vertical:hover,
    QTextEdit#AIChatDisplay QScrollBar::handle:vertical:hover, QPlainTextEdit#ActionCodeEditor QScrollBar::handle:vertical:hover,
    QTextEdit#IDEOutputConsole QScrollBar::handle:vertical:hover, QPlainTextEdit#StandaloneCodeEditor QScrollBar::handle:vertical:hover,
    QTextEdit#SubFSMJsonEditor QScrollBar::handle:vertical:hover
    {{
         background: {QColor(COLOR_TEXT_EDITOR_DARK_SECONDARY).lighter(120).name()}; /* Dynamic */
    }}

    QPushButton#SnippetButton {{
        background-color: {COLOR_ACCENT_SECONDARY}; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic text for snippet button */
        border: 1px solid {QColor(COLOR_ACCENT_SECONDARY).darker(130).name()}; /* Dynamic */
        font-weight: normal;
        padding: 4px 8px; 
        min-height: 0;
    }}
    QPushButton#SnippetButton:hover {{
        background-color: {QColor(COLOR_ACCENT_SECONDARY).lighter(110).name()}; /* Dynamic */
    }}
    QPushButton#ColorButton, QPushButton#ColorButtonPropertiesDock {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; min-height: 24px; padding: 3px; /* Dynamic */
    }}
    QPushButton#ColorButton:hover, QPushButton#ColorButtonPropertiesDock:hover {{
        border: 1px solid {COLOR_ACCENT_PRIMARY}; /* Dynamic */
    }}
    QProgressBar {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; border-radius: 3px; /* Dynamic */
        background-color: {COLOR_BACKGROUND_LIGHT}; text-align: center; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; height: 12px; /* Dynamic */
    }}
    QProgressBar::chunk {{
        background-color: {COLOR_ACCENT_PRIMARY}; border-radius: 2px; /* Dynamic */
    }}
    QPushButton#DraggableToolButton {{
        background-color: {COLOR_DRAGGABLE_BUTTON_BG}; color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
        border: 1px solid {COLOR_DRAGGABLE_BUTTON_BORDER}; /* Dynamic */
        padding: 5px 7px;  
        text-align: left; 
        font-weight: 500;
        min-height: 32px; 
    }}
    QPushButton#DraggableToolButton:hover {{
        background-color: {QColor(COLOR_DRAGGABLE_BUTTON_HOVER_BG).name() if isinstance(COLOR_DRAGGABLE_BUTTON_HOVER_BG, QColor) else COLOR_DRAGGABLE_BUTTON_HOVER_BG}; /* Dynamic hover */
        border-color: {COLOR_DRAGGABLE_BUTTON_HOVER_BORDER}; /* Dynamic hover */
    }}
    QPushButton#DraggableToolButton:pressed {{ background-color: {QColor(COLOR_DRAGGABLE_BUTTON_PRESSED_BG).name() if isinstance(COLOR_DRAGGABLE_BUTTON_PRESSED_BG, QColor) else COLOR_DRAGGABLE_BUTTON_PRESSED_BG}; }} /* Dynamic pressed */

    #PropertiesDock QLabel#PropertiesLabel {{
        padding: 6px; background-color: {COLOR_BACKGROUND_DIALOG}; /* Dynamic */
        border: 1px solid {COLOR_BORDER_LIGHT}; border-radius: 3px; /* Dynamic */
        font-size: {APP_FONT_SIZE_STANDARD};
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
    }}
    #PropertiesDock QPushButton {{ 
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT}; /* Dynamic */
        font-weight:bold;
    }}
    #PropertiesDock QPushButton:hover {{ background-color: {QColor(COLOR_ACCENT_PRIMARY).lighter(110).name()}; }} /* Dynamic */
    /* Style for PropertiesDock ColorButton is handled by _update_dock_color_button_style */

    QDockWidget#ToolsDock QToolButton {{ /* Retain specific if ElementsPaletteDock needs different padding */
        padding: 6px 8px; text-align: left; 
        min-height: 34px; 
        font-weight: 500;
    }}

    QDockWidget#PySimDock QPushButton {{
        padding: 5px 10px; 
    }}
    QDockWidget#PySimDock QPushButton:disabled {{
        background-color: {COLOR_BACKGROUND_MEDIUM}; /* Dynamic */
        color: {COLOR_TEXT_SECONDARY}; /* Dynamic */
    }}
    QDockWidget#PySimDock QTableWidget {{
        alternate-background-color: {QColor(COLOR_BACKGROUND_APP).lighter(105 if QColor(COLOR_BACKGROUND_APP).lightnessF() > 0.5 else 115).name()}; /* Dynamic */
        gridline-color: {COLOR_BORDER_LIGHT}; /* Dynamic */
        background-color: {COLOR_BACKGROUND_DIALOG}; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; /* For table text */
    }}
     QDockWidget#PySimDock QHeaderView::section,
     QTableWidget QHeaderView::section
     {{
        background-color: {COLOR_BACKGROUND_MEDIUM}; /* Dynamic */
        padding: 4px; 
        border: 1px solid {COLOR_BORDER_LIGHT}; /* Dynamic */
        border-bottom: 2px solid {COLOR_BORDER_DARK}; /* Dynamic */
        font-weight: bold;
        color: {COLOR_TEXT_PRIMARY}; /* For header text */
    }}
    QDockWidget#AIChatbotDock QPushButton#AIChatSendButton,
    QDockWidget#PySimDock QPushButton[text="Trigger"]
    {{
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT}; /* Dynamic */
        font-weight: bold;
        padding: 5px; 
        min-width: 0;
    }}
    QDockWidget#AIChatbotDock QPushButton#AIChatSendButton:hover,
    QDockWidget#PySimDock QPushButton[text="Trigger"]:hover
    {{
        background-color: {QColor(COLOR_ACCENT_PRIMARY).lighter(110).name()}; /* Dynamic */
    }}
    QDockWidget#AIChatbotDock QPushButton#AIChatSendButton:disabled,
    QDockWidget#PySimDock QPushButton[text="Trigger"]:disabled
    {{
        background-color: {COLOR_BACKGROUND_MEDIUM}; /* Dynamic */
        color: {COLOR_TEXT_SECONDARY}; /* Dynamic */
        border-color: {COLOR_BORDER_LIGHT}; /* Dynamic */
    }}
    QLineEdit#AIChatInput, QLineEdit#PySimEventNameEdit
    {{
        padding: 6px 8px; 
    }}
    QDockWidget#ProblemsDock QListWidget {{
        background-color: {COLOR_BACKGROUND_DIALOG}; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; /* Dynamic */
    }}
    QDockWidget#ProblemsDock QListWidget::item {{ 
        padding: 4px; 
        border-bottom: 1px dotted {COLOR_BORDER_LIGHT}; /* Dynamic */
        color: {COLOR_TEXT_PRIMARY}; /* Ensure item text is themed */
    }}
    QDockWidget#ProblemsDock QListWidget::item:selected {{ 
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT}; /* Dynamic */
        color: {QColor(COLOR_ACCENT_PRIMARY).darker(130).name() if QColor(COLOR_ACCENT_PRIMARY_LIGHT).lightnessF() > 0.6 else COLOR_TEXT_ON_ACCENT}; /* Dynamic */
    }}
    QLabel#ErrorLabel {{ 
        color: {COLOR_ACCENT_ERROR}; /* Dynamic */
        font-weight: bold; 
    }}
    QLabel#HardwareHintLabel {{
        color: {COLOR_TEXT_SECONDARY}; /* Dynamic */
        font-style: italic;
        font-size: 7.5pt;
    }}
    QLabel#SafetyNote {{
        color: {COLOR_TEXT_SECONDARY}; /* Dynamic */
        font-style: italic;
        font-size: {APP_FONT_SIZE_SMALL};
    }}
    QGroupBox#IDEOutputGroup, QGroupBox#IDEToolbarGroup {{ /* If you wrap IDE toolbar/output in groupboxes */
        /* Add specific styling if needed, or let general QGroupBox style apply */
    }}
    """