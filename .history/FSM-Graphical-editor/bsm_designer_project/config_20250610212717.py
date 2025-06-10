# bsm_designer_project/config.py
# (Changes are additive or modifications)
# bsm_designer_project/config.py

from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt # <--- ADD THIS LINE
import json

# --- Configuration ---
APP_VERSION = "1.8.0" # Incremented version
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
    "Python (Generic Simulation)": {
        "actions": {
            "Set Variable": "my_variable = 10",
            "Increment Counter": "counter = counter + 1",
            "Print Message": "print('Hello from FSM!')",
            "Log with Tick": "print(f'Current tick: {current_tick}, State: {sm.current_state.id if sm and sm.current_state else 'N/A'}')",
        },
        "conditions": {
            "Variable Equals": "my_variable == 10",
            "Counter Greater Than": "counter > 5",
        },
        "events": {
            "Timer Expired": "timer_expired",
            "Button Pressed": "button_pressed",
            "Sensor Detect": "sensor_detect_obj_A",
        }
    },
    "Arduino (C++)": {
        "actions": {
            "Digital Write HIGH": "digitalWrite(LED_PIN, HIGH);",
            "Digital Write LOW": "digitalWrite(LED_PIN, LOW);",
            "Analog Write": "analogWrite(MOTOR_PIN, speed_value);",
            "Serial Print": "Serial.println(\"Hello from Arduino FSM!\");",
            "Delay": "delay(1000); // 1 second delay"
        },
        "conditions": {
            "Digital Read HIGH": "digitalRead(BUTTON_PIN) == HIGH",
            "Analog Read Threshold": "analogRead(SENSOR_PIN) > 512",
            "Variable Check": "my_arduino_variable == SOME_VALUE"
        },
         "events": {
            "Timer Interrupt": "ISR_TIMER_EXPIRED_FLAG",
            "Button Change": "BUTTON_CHANGE_EVENT",
        }
    },
     "C (Generic Embedded)": {
        "actions": {
            "Set GPIO Pin High": "HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET); // Example for STM32 HAL",
            "Set GPIO Pin Low": "HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET);",
            "Toggle GPIO Pin": "HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5);",
            "Send UART Message": "HAL_UART_Transmit(&huart1, (uint8_t*)\"Msg\\r\\n\", 6, 100);",
            "Basic printf (if stdio redirected)": "printf(\"Event occurred\\n\");"
        },
        "conditions": {
            "Check GPIO Pin State": "HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_0) == GPIO_PIN_SET",
            "Check Flag Variable": "global_event_flag == 1",
        },
        "events": {
            "External Interrupt": "EXTI0_IRQ_FLAG",
            "Timer Overflow": "TIM2_UPDATE_FLAG",
        }
    },
    # Add other environments like RaspberryPi, MicroPython with relevant snippets
    "RaspberryPi (Python)": {
        "actions": {
            "GPIO Set High": "import RPi.GPIO as GPIO\nGPIO.setmode(GPIO.BCM) # or GPIO.BOARD\nGPIO.setup(17, GPIO.OUT)\nGPIO.output(17, GPIO.HIGH)",
            "GPIO Set Low": "import RPi.GPIO as GPIO\nGPIO.output(17, GPIO.LOW)",
            "Print Message": "print('RPi FSM action')",
        },
        "conditions": {
            "GPIO Read High": "import RPi.GPIO as GPIO\nGPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)\nGPIO.input(18) == GPIO.HIGH",
        },
        "events": {
            "Button Press RPi": "rpi_button_event",
        }
    },
    "MicroPython": {
        "actions": {
            "Pin On": "from machine import Pin\nled = Pin(2, Pin.OUT)\nled.on()",
            "Pin Off": "from machine import Pin\nled = Pin(2, Pin.OUT)\nled.off()",
            "Toggle Pin": "from machine import Pin\nled = Pin(2, Pin.OUT)\nled.value(not led.value())",
        },
        "conditions": {
            "Pin Value High": "from machine import Pin\nbutton = Pin(0, Pin.IN, Pin.PULL_UP)\nbutton.value() == 1",
        },
        "events": {
            "IRQ Triggered MicroPy": "micropy_irq_flag_event",
        }
    },
    "Text": { # For comments or generic text fields
        "actions": {}, "conditions": {}, "events": {}
    }
}

FSM_TEMPLATES_BUILTIN_JSON_STR = """
{
    "DebounceLogic": {
        "name": "Debounce Logic",
        "description": "A simple debounce pattern for an input signal.",
        "icon_resource": ":/icons/debounce_icon.png",
        "states": [
            {"name": "Unstable", "description": "Input is currently unstable or bouncing."},
            {"name": "Waiting", "entry_action": "start_debounce_timer()"},
            {"name": "Stable", "description": "Input is considered stable."}
        ],
        "transitions": [
            {"source": "Unstable", "target": "Waiting", "event": "input_change"},
            {"source": "Waiting", "target": "Stable", "event": "debounce_timer_expired"},
            {"source": "Waiting", "target": "Unstable", "event": "input_change_while_waiting", "control_offset_y": 60},
            {"source": "Stable", "target": "Unstable", "event": "input_goes_unstable_again", "control_offset_y": -60}
        ],
        "comments": [
            {"text": "Debounce timer should be set appropriately for your hardware.", "width": 180}
        ]
    },
    "Blinker": {
        "name": "Simple Blinker",
        "description": "Alternates between On and Off states based on a timer.",
        "icon_resource": ":/icons/blinker_icon.png",
        "states": [
            {"name": "LedOff", "is_initial": true, "entry_action": "set_led_off()\\nstart_timer(OFF_DURATION)"},
            {"name": "LedOn", "entry_action": "set_led_on()\\nstart_timer(ON_DURATION)"}
        ],
        "transitions": [
            {"source": "LedOff", "target": "LedOn", "event": "timer_expired"},
            {"source": "LedOn", "target": "LedOff", "event": "timer_expired"}
        ],
        "comments": [
            {"text": "Define ON_DURATION and OFF_DURATION variables in your simulation environment.", "width": 200}
        ]
    }
}
"""
try:
    # FSM_TEMPLATES_BUILTIN is now a dictionary where keys are template names
    # and values are the Python dictionary representations of each template.
    FSM_TEMPLATES_BUILTIN = json.loads(FSM_TEMPLATES_BUILTIN_JSON_STR)
except json.JSONDecodeError:
    FSM_TEMPLATES_BUILTIN = {} # Fallback to empty if JSON is bad


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
COLOR_DRAGGABLE_BUTTON_HOVER_BORDER = COLOR_ACCENT_PRIMARY # Theme this, was missing definition
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
           COLOR_DRAGGABLE_BUTTON_HOVER_BG, COLOR_DRAGGABLE_BUTTON_HOVER_BORDER, \
           COLOR_DRAGGABLE_BUTTON_PRESSED_BG, \
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
        COLOR_DRAGGABLE_BUTTON_HOVER_BORDER = COLOR_ACCENT_PRIMARY_DARK_THEME # Use themed accent
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
        COLOR_DRAGGABLE_BUTTON_HOVER_BORDER = COLOR_ACCENT_PRIMARY_LIGHT_THEME # Use themed accent
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
    /* This string will be REBUILT by main.py when theme changes */
"""

def GET_CURRENT_STYLE_SHEET():
    # This function will now generate the stylesheet based on current dynamic colors
    # This helps to avoid a massive static string and makes it theme-aware
    return f"""
    QWidget {{
        font-family: {APP_FONT_FAMILY};
        font-size: {APP_FONT_SIZE_STANDARD};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QMainWindow {{
        background-color: {COLOR_BACKGROUND_APP};
    }}
    QDockWidget::title {{
        background-color: {QColor(COLOR_BACKGROUND_MEDIUM).darker(105).name()};
        padding: 6px 10px; 
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom: 2px solid {COLOR_ACCENT_PRIMARY};
        font-weight: bold;
        color: {COLOR_TEXT_PRIMARY};
        border-top-left-radius: 3px; 
        border-top-right-radius: 3px;
    }}
    QDockWidget {{
        border: 1px solid {COLOR_BORDER_LIGHT};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QDockWidget QWidget {{
        color: {COLOR_TEXT_PRIMARY};
        background-color: {COLOR_BACKGROUND_APP};
    }}
    QDockWidget::close-button, QDockWidget::float-button {{
        subcontrol-position: top right;
        subcontrol-origin: margin;
        position: absolute;
        top: 1px; right: 4px; padding: 1px; 
        border-radius: 2px;
    }}
    QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
        background-color: {COLOR_BACKGROUND_DARK};
    }}
    QToolBar {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        border-bottom: 1px solid {COLOR_BORDER_LIGHT};
        padding: 2px; 
        spacing: 3px; 
    }}
    QToolButton {{
        background-color: transparent;
        color: {COLOR_TEXT_PRIMARY};
        padding: 4px 6px; 
        margin: 0px; 
        border: 1px solid transparent;
        border-radius: 3px;
    }}
    QToolButton:hover, QDockWidget#ElementsPaletteDock QToolButton:hover {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
        border: 1px solid {COLOR_ACCENT_PRIMARY};
        color: {QColor(COLOR_ACCENT_PRIMARY).darker(130).name() if QColor(COLOR_ACCENT_PRIMARY_LIGHT).lightnessF() > 0.6 else COLOR_TEXT_ON_ACCENT};
    }}
    QToolButton:pressed, QDockWidget#ElementsPaletteDock QToolButton:pressed {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}
    QToolButton:checked, QDockWidget#ElementsPaletteDock QToolButton:checked {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
        border: 1px solid {QColor(COLOR_ACCENT_PRIMARY).darker(120).name()};
    }}
    QToolBar QToolButton:disabled {{
        color: {COLOR_TEXT_SECONDARY};
        background-color: transparent;
    }}
    QMenuBar {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_PRIMARY};
        border-bottom: 1px solid {COLOR_BORDER_LIGHT};
        padding: 2px; 
    }}
    QMenuBar::item {{
        background-color: transparent;
        padding: 4px 10px; 
        color: {COLOR_TEXT_PRIMARY};
    }}
    QMenuBar::item:selected {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
        color: {QColor(COLOR_ACCENT_PRIMARY).darker(130).name() if QColor(COLOR_ACCENT_PRIMARY_LIGHT).lightnessF() > 0.6 else COLOR_TEXT_PRIMARY};
    }}
    QMenuBar::item:pressed {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}
    QMenu {{
        background-color: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 3px;
        padding: 4px; 
    }}
    QMenu::item {{
        padding: 5px 25px 5px 25px; 
        border-radius: 3px;
        color: {COLOR_TEXT_PRIMARY};
    }}
    QMenu::item:selected {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}
    QMenu::separator {{
        height: 1px;
        background: {COLOR_BORDER_LIGHT};
        margin: 4px 6px; 
    }}
    QMenu::icon {{
        padding-left: 5px;
    }}
    QStatusBar {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_PRIMARY};
        border-top: 1px solid {COLOR_BORDER_LIGHT};
        padding: 2px 4px; 
    }}
    QStatusBar::item {{
        border: none;
        margin: 0 2px; 
    }}
    QLabel#StatusLabel, QLabel#MatlabStatusLabel, QLabel#PySimStatusLabel, QLabel#AIChatStatusLabel, QLabel#InternetStatusLabel,
    QLabel#MainOpStatusLabel, QLabel#IdeFileStatusLabel,
    QMainWindow QLabel[objectName$="StatusLabel"],
    QLabel#ZoomStatusLabel, QLabel#InteractionModeStatusLabel
    {{
         padding: 1px 4px; 
         font-size: {APP_FONT_SIZE_SMALL};
         border-radius: 2px;
         color: {COLOR_TEXT_SECONDARY};
    }}
    QLabel#CpuStatusLabel, QLabel#RamStatusLabel, QLabel#GpuStatusLabel {{
        font-size: {APP_FONT_SIZE_SMALL};
        padding: 1px 4px; 
        min-width: 60px; 
        border: 1px solid {COLOR_BORDER_LIGHT};
        background-color: {COLOR_BACKGROUND_APP};
        border-radius: 2px;
        color: {COLOR_TEXT_SECONDARY};
    }}
    QDialog {{
        background-color: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QDialog QLabel, QDialog QCheckBox, QDialog QRadioButton, QDialog QSpinBox, QDialog QDoubleSpinBox, QDialog QFontComboBox {{
        color: {COLOR_TEXT_PRIMARY};
    }}
    QLabel {{
        color: {COLOR_TEXT_PRIMARY};
        background-color: transparent;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {QColor(COLOR_BACKGROUND_DIALOG).lighter(102 if QColor(COLOR_BACKGROUND_DIALOG).lightnessF() > 0.5 else 115).name()};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 3px; 
        padding: 5px 7px; 
        font-size: {APP_FONT_SIZE_STANDARD};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1.5px solid {COLOR_ACCENT_PRIMARY};
        outline: none;
    }}
    QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_SECONDARY};
        border-color: {COLOR_BORDER_LIGHT};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 22px; 
        border-left-width: 1px;
        border-left-color: {COLOR_BORDER_MEDIUM};
        border-left-style: solid;
        border-top-right-radius: 2px;
        border-bottom-right-radius: 2px;
        background-color: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102 if QColor(COLOR_BACKGROUND_LIGHT).lightnessF() > 0.5 else 110).name()};
    }}
    QComboBox::drop-down:hover {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
    }}
    QComboBox::down-arrow {{
         image: url(:/icons/arrow_down.png);
         width: 10px; height:10px; 
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLOR_BACKGROUND_DIALOG};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        selection-background-color: {COLOR_ACCENT_PRIMARY};
        selection-color: {COLOR_TEXT_ON_ACCENT};
        border-radius: 2px;
        padding: 1px;
        color: {COLOR_TEXT_PRIMARY};
    }}
    QPushButton {{
        background-color: {QColor(COLOR_BACKGROUND_MEDIUM).lighter(105).name()};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        padding: 6px 15px; 
        border-radius: 4px; 
        min-height: 22px; 
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {QColor(COLOR_BACKGROUND_MEDIUM).name()};
        border-color: {COLOR_BORDER_DARK};
    }}
    QPushButton:pressed {{
        background-color: {QColor(COLOR_BACKGROUND_DARK).name()};
    }}
    QPushButton:disabled {{
        background-color: {QColor(COLOR_BACKGROUND_LIGHT).darker(102 if QColor(COLOR_BACKGROUND_LIGHT).lightnessF() < 0.5 else 95).name()};
        color: {COLOR_TEXT_SECONDARY};
        border-color: {COLOR_BORDER_LIGHT};
    }}
    QDialogButtonBox QPushButton {{
        min-width: 80px; 
    }}
    QDialogButtonBox QPushButton[text="OK"], QDialogButtonBox QPushButton[text="OK & Save"], QDialogButtonBox QPushButton[text="Apply & Close"],
    QDialogButtonBox QPushButton[text="Save"]
    {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
        border-color: {QColor(COLOR_ACCENT_PRIMARY).darker(120).name()};
        font-weight: bold;
    }}
    QDialogButtonBox QPushButton[text="OK"]:hover, QDialogButtonBox QPushButton[text="OK & Save"]:hover, QDialogButtonBox QPushButton[text="Apply & Close"]:hover,
    QDialogButtonBox QPushButton[text="Save"]:hover
    {{
        background-color: {QColor(COLOR_ACCENT_PRIMARY).lighter(110).name()};
    }}
    QDialogButtonBox QPushButton[text="Cancel"], QDialogButtonBox QPushButton[text="Discard"],
    QDialogButtonBox QPushButton[text="Close"]
    {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_PRIMARY};
        border-color: {COLOR_BORDER_MEDIUM};
    }}
    QDialogButtonBox QPushButton[text="Cancel"]:hover, QDialogButtonBox QPushButton[text="Discard"]:hover,
    QDialogButtonBox QPushButton[text="Close"]:hover
    {{
        background-color: {QColor(COLOR_BACKGROUND_MEDIUM).darker(110).name()};
    }}
    QGroupBox {{
        background-color: transparent;
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-radius: 4px; 
        margin-top: 10px; 
        padding: 10px 8px 8px 8px; 
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px; 
        left: 10px; 
        background-color: {COLOR_BACKGROUND_APP};
        color: {COLOR_ACCENT_PRIMARY};
        font-weight: bold;
        border-radius: 2px;
    }}
    QTabWidget::pane {{
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-top: none;
        border-bottom-left-radius: 3px;
        border-bottom-right-radius: 3px;
        background-color: {COLOR_BACKGROUND_DIALOG};
        padding: 6px; 
    }}
    QTabBar::tab {{
        background: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_SECONDARY};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom-color: {COLOR_BACKGROUND_DIALOG};
        border-top-left-radius: 3px;
        border-top-right-radius: 3px;
        padding: 6px 15px; 
        margin-right: 1px;
        min-width: 70px; 
    }}
    QTabBar::tab:selected {{
        background: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
        font-weight: bold;
        border-bottom-color: {COLOR_BACKGROUND_DIALOG};
    }}
    QTabBar::tab:!selected:hover {{
        background: {COLOR_ACCENT_PRIMARY_LIGHT};
        color: {COLOR_TEXT_PRIMARY};
        border-bottom-color: {COLOR_BORDER_LIGHT};
    }}
    QCheckBox {{
        spacing: 8px; 
        color: {COLOR_TEXT_PRIMARY};
    }}
    QCheckBox::indicator {{
        width: 14px; 
        height: 14px;
    }}
    QCheckBox::indicator:unchecked {{
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 2px;
        background-color: {QColor(COLOR_BACKGROUND_DIALOG).lighter(102 if QColor(COLOR_BACKGROUND_DIALOG).lightnessF() > 0.5 else 110).name()};
    }}
    QCheckBox::indicator:unchecked:hover {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QCheckBox::indicator:checked {{
        border: 1px solid {QColor(COLOR_ACCENT_PRIMARY).darker(120).name()};
        border-radius: 2px;
        background-color: {COLOR_ACCENT_PRIMARY};
        image: url(:/icons/check.png);
    }}
    QCheckBox::indicator:checked:hover {{
        background-color: {QColor(COLOR_ACCENT_PRIMARY).lighter(110).name()};
    }}
    QTextEdit#LogOutputWidget, QTextEdit#PySimActionLog, QTextBrowser#AIChatDisplay,
    QPlainTextEdit#ActionCodeEditor, QTextEdit#IDEOutputConsole, QPlainTextEdit#StandaloneCodeEditor,
    QTextEdit#SubFSMJsonEditor 
    {{
         font-family: Consolas, 'Courier New', monospace;
         font-size: {APP_FONT_SIZE_EDITOR};
         background-color: {COLOR_BACKGROUND_EDITOR_DARK};
         color: {COLOR_TEXT_EDITOR_DARK_PRIMARY};
         border: 1px solid {COLOR_BORDER_DARK};
         border-radius: 3px;
         padding: 6px; 
         selection-background-color: {QColor(COLOR_ACCENT_PRIMARY).darker(110).name()};
         selection-color: {COLOR_TEXT_ON_ACCENT};
    }}
    QScrollBar:vertical {{
         border: 1px solid {COLOR_BORDER_LIGHT};
         background: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102 if QColor(COLOR_BACKGROUND_LIGHT).lightnessF() > 0.5 else 110).name()};
         width: 14px; 
         margin: 0px;
    }}
    QScrollBar::handle:vertical {{
         background: {COLOR_BORDER_DARK};
         min-height: 25px;
         border-radius: 7px;
    }}
    QScrollBar::handle:vertical:hover {{
         background: {QColor(COLOR_BORDER_DARK).lighter(120).name()};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
         height: 0px;
         background: transparent;
    }}
    QScrollBar:horizontal {{
         border: 1px solid {COLOR_BORDER_LIGHT};
         background: {QColor(COLOR_BACKGROUND_LIGHT).lighter(102 if QColor(COLOR_BACKGROUND_LIGHT).lightnessF() > 0.5 else 110).name()};
         height: 14px; 
         margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
         background: {COLOR_BORDER_DARK};
         min-width: 25px;
         border-radius: 7px;
    }}
    QScrollBar::handle:horizontal:hover {{
         background: {QColor(COLOR_BORDER_DARK).lighter(120).name()};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
         width: 0px;
         background: transparent;
    }}

    /* Editor specific scrollbars */
    QTextEdit#LogOutputWidget QScrollBar:vertical, QTextEdit#PySimActionLog QScrollBar:vertical,
    QTextBrowser#AIChatDisplay QScrollBar:vertical, QPlainTextEdit#ActionCodeEditor QScrollBar:vertical,
    QTextEdit#IDEOutputConsole QScrollBar:vertical, QPlainTextEdit#StandaloneCodeEditor QScrollBar:vertical,
    QTextEdit#SubFSMJsonEditor QScrollBar:vertical
    {{
         border: 1px solid {COLOR_BORDER_DARK};
         background: {QColor(COLOR_BACKGROUND_EDITOR_DARK).lighter(110).name()};
    }}
    QTextEdit#LogOutputWidget QScrollBar::handle:vertical, QTextEdit#PySimActionLog QScrollBar::handle:vertical,
    QTextBrowser#AIChatDisplay QScrollBar::handle:vertical, QPlainTextEdit#ActionCodeEditor QScrollBar::handle:vertical,
    QTextEdit#IDEOutputConsole QScrollBar::handle:vertical, QPlainTextEdit#StandaloneCodeEditor QScrollBar::handle:vertical,
    QTextEdit#SubFSMJsonEditor QScrollBar::handle:vertical
    {{
         background: {COLOR_TEXT_EDITOR_DARK_SECONDARY};
    }}
    QTextEdit#LogOutputWidget QScrollBar::handle:vertical:hover, QTextEdit#PySimActionLog QScrollBar::handle:vertical:hover,
    QTextBrowser#AIChatDisplay QScrollBar::handle:vertical:hover, QPlainTextEdit#ActionCodeEditor QScrollBar::handle:vertical:hover,
    QTextEdit#IDEOutputConsole QScrollBar::handle:vertical:hover, QPlainTextEdit#StandaloneCodeEditor QScrollBar::handle:vertical:hover,
    QTextEdit#SubFSMJsonEditor QScrollBar::handle:vertical:hover
    {{
         background: {QColor(COLOR_TEXT_EDITOR_DARK_SECONDARY).lighter(120).name()};
    }}

    QPushButton#SnippetButton {{
        background-color: {COLOR_ACCENT_SECONDARY};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {QColor(COLOR_ACCENT_SECONDARY).darker(130).name()};
        font-weight: normal;
        padding: 4px 8px; 
        min-height: 0;
    }}
    QPushButton#SnippetButton:hover {{
        background-color: {QColor(COLOR_ACCENT_SECONDARY).lighter(110).name()};
    }}
    QPushButton#ColorButton, QPushButton#ColorButtonPropertiesDock {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; min-height: 24px; padding: 3px;
    }}
    QPushButton#ColorButton:hover, QPushButton#ColorButtonPropertiesDock:hover {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QProgressBar {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; border-radius: 3px;
        background-color: {COLOR_BACKGROUND_LIGHT}; text-align: center;
        color: {COLOR_TEXT_PRIMARY}; height: 12px;
    }}
    QProgressBar::chunk {{
        background-color: {COLOR_ACCENT_PRIMARY}; border-radius: 2px;
    }}
    QPushButton#DraggableToolButton {{
        background-color: {COLOR_DRAGGABLE_BUTTON_BG}; color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_DRAGGABLE_BUTTON_BORDER};
        padding: 5px 7px;  
        text-align: left; 
        font-weight: 500;
        min-height: 32px; 
    }}
    QPushButton#DraggableToolButton:hover {{
        background-color: {QColor(COLOR_DRAGGABLE_BUTTON_HOVER_BG).name() if isinstance(COLOR_DRAGGABLE_BUTTON_HOVER_BG, QColor) else COLOR_DRAGGABLE_BUTTON_HOVER_BG};
        border-color: {COLOR_DRAGGABLE_BUTTON_HOVER_BORDER};
    }}
    QPushButton#DraggableToolButton:pressed {{ background-color: {QColor(COLOR_DRAGGABLE_BUTTON_PRESSED_BG).name() if isinstance(COLOR_DRAGGABLE_BUTTON_PRESSED_BG, QColor) else COLOR_DRAGGABLE_BUTTON_PRESSED_BG}; }}

    #PropertiesDock QLabel#PropertiesLabel {{
        padding: 6px; background-color: {COLOR_BACKGROUND_DIALOG};
        border: 1px solid {COLOR_BORDER_LIGHT}; border-radius: 3px;
        font-size: {APP_FONT_SIZE_STANDARD};
        color: {COLOR_TEXT_PRIMARY};
    }}
    #PropertiesDock QPushButton {{ 
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT};
        font-weight:bold;
    }}
    #PropertiesDock QPushButton:hover {{ background-color: {QColor(COLOR_ACCENT_PRIMARY).lighter(110).name()}; }}

    QDockWidget#ElementsPaletteDock QToolButton {{
        padding: 6px 8px; text-align: left; 
        min-height: 34px; 
        font-weight: 500;
    }}
    QDockWidget#ElementsPaletteDock QGroupBox {{
        color: {COLOR_TEXT_PRIMARY};
    }}
    QDockWidget#ElementsPaletteDock QGroupBox::title {{
        color: {COLOR_ACCENT_PRIMARY};
        background-color: {COLOR_BACKGROUND_APP};
    }}


    QDockWidget#PySimDock QPushButton {{
        padding: 5px 10px; 
    }}
    QDockWidget#PySimDock QPushButton:disabled {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_SECONDARY};
    }}
    QDockWidget#PySimDock QTableWidget {{
        alternate-background-color: {QColor(COLOR_BACKGROUND_APP).lighter(105 if QColor(COLOR_BACKGROUND_APP).lightnessF() > 0.5 else 115).name()};
        gridline-color: {COLOR_BORDER_LIGHT};
        background-color: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
    }}
     QDockWidget#PySimDock QHeaderView::section,
     QTableWidget QHeaderView::section
     {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        padding: 4px; 
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom: 2px solid {COLOR_BORDER_DARK};
        font-weight: bold;
        color: {COLOR_TEXT_PRIMARY};
    }}
    QDockWidget#AIChatbotDock QPushButton#AIChatSendButton,
    QDockWidget#PySimDock QPushButton[text="Trigger"]
    {{
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT};
        font-weight: bold;
        padding: 5px; 
        min-width: 0;
    }}
    QDockWidget#AIChatbotDock QPushButton#AIChatSendButton:hover,
    QDockWidget#PySimDock QPushButton[text="Trigger"]:hover
    {{
        background-color: {QColor(COLOR_ACCENT_PRIMARY).lighter(110).name()};
    }}
    QDockWidget#AIChatbotDock QPushButton#AIChatSendButton:disabled,
    QDockWidget#PySimDock QPushButton[text="Trigger"]:disabled
    {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_SECONDARY};
        border-color: {COLOR_BORDER_LIGHT};
    }}
    QLineEdit#AIChatInput, QLineEdit#PySimEventNameEdit
    {{
        padding: 6px 8px; 
    }}
    QDockWidget#ProblemsDock QListWidget {{
        background-color: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QDockWidget#ProblemsDock QListWidget::item {{ 
        padding: 4px; 
        border-bottom: 1px dotted {COLOR_BORDER_LIGHT};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QDockWidget#ProblemsDock QListWidget::item:selected {{ 
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
        color: {QColor(COLOR_ACCENT_PRIMARY).darker(130).name() if QColor(COLOR_ACCENT_PRIMARY_LIGHT).lightnessF() > 0.6 else COLOR_TEXT_ON_ACCENT};
    }}
    QLabel#ErrorLabel {{ 
        color: {COLOR_ACCENT_ERROR};
        font-weight: bold; 
    }}
    QLabel#HardwareHintLabel {{
        color: {COLOR_TEXT_SECONDARY};
        font-style: italic;
        font-size: 7.5pt;
    }}
    QLabel#SafetyNote {{
        color: {COLOR_TEXT_SECONDARY};
        font-style: italic;
        font-size: {APP_FONT_SIZE_SMALL};
    }}
    QGroupBox#IDEOutputGroup, QGroupBox#IDEToolbarGroup {{
    }}
    """
