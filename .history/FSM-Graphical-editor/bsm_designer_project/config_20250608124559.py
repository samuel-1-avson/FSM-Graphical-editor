# bsm_designer_project/config.py

from PyQt5.QtGui import QColor
import json 

# --- Configuration ---
APP_VERSION = "1.7.1" 
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
    EXECUTION_ENV_PYTHON_GENERIC: { 
        "actions": {
            "Print Message": "print('Log: My message')",
            "Set Variable": "my_variable = 42",
            "Increment Counter": "counter = counter + 1 if 'counter' in locals() or 'counter' in globals() else 1",
            "Set Virtual LED On": "led_pin_state = 1  # Represents LED being turned ON",
            "Set Virtual LED Off": "led_pin_state = 0 # Represents LED being turned OFF",
            "Toggle Virtual LED": "led_pin_state = 1 - led_pin_state if 'led_pin_state' in locals() or 'led_pin_state' in globals() else 1",
            "Set Virtual Motor Speed": "motor_speed_percent = 75 # Represents motor at 75% speed",
            "Read Virtual Sensor": "if 'sensor_reading' in locals() or 'sensor_reading' in globals():\n    if sensor_reading > 500:\n        print('Virtual sensor threshold exceeded')\nelse:\n    print('Virtual sensor_reading not set')",
            "Simulate Button Press": "button_is_pressed = 1 # User might manage this variable externally in sim",
            "Simulate Button Release": "button_is_pressed = 0",
        },
        "events": { 
            "Timeout Event": "timeout_event_occurred",
            "Button Pressed Event": "button_was_pressed",
            "Sensor Threshold Reached Event": "sensor_limit_reached",
            "System Error Event": "system_error_detected",
        },
        "conditions": { 
            "Variable Equals Value": "my_variable == 42",
            "Virtual LED is On": "led_pin_state == 1",
            "Virtual LED is Off": "led_pin_state == 0",
            "Virtual Button is Pressed": "button_is_pressed == 1",
            "Sensor Value Above Threshold": "'sensor_reading' in locals() or 'sensor_reading' in globals() and sensor_reading > 750",
        }
    },
    EXECUTION_ENV_ARDUINO_CPP: {
        "actions": {
            "Digital Write High": "digitalWrite(MY_LED_PIN, HIGH); /* Define MY_LED_PIN (e.g., const int MY_LED_PIN = 13;) */",
            "Digital Write Low": "digitalWrite(MY_LED_PIN, LOW);",
            "Analog Read Sensor": "int sensorValue = analogRead(MY_ANALOG_SENSOR_PIN); /* Define MY_ANALOG_SENSOR_PIN */",
            "Serial Print Message": "Serial.println(\"Debug message\");",
            "Delay Milliseconds": "delay(1000); /* Pause for 1 second */",
            "Set Pin Mode Output": "pinMode(MY_OUTPUT_PIN, OUTPUT); /* Define MY_OUTPUT_PIN */",
            "Set Pin Mode Input Pullup": "pinMode(MY_INPUT_PIN, INPUT_PULLUP); /* Define MY_INPUT_PIN */",
            "Custom Function Call": "myCustomHwFunction(); /* Implement this function */",
        },
        "events": { 
            "Button_Press_Event": "EVT_BUTTON_PRESS", 
            "Timer_Expired_Event": "EVT_TIMER_EXPIRED",
            "Sensor_Data_Ready_Event": "EVT_SENSOR_READY",
        },
        "conditions": { 
            "Digital Read Pin High": "digitalRead(MY_BUTTON_PIN) == HIGH",
            "Digital Read Pin Low": "digitalRead(MY_BUTTON_PIN) == LOW",
            "Analog Sensor Above Threshold": "analogRead(MY_ANALOG_SENSOR_PIN) > 512",
            "Custom Flag is True": "my_global_flag == 1", 
            "Function Returns True": "checkMyHardwareCondition() == true /* Implement this function */",
        }
    },
    EXECUTION_ENV_RASPBERRYPI_PYTHON: { 
        "actions": {
            "Set GPIO High": "# import RPi.GPIO as GPIO\n# GPIO.setmode(GPIO.BCM) # or GPIO.BOARD\n# GPIO.setup(MY_GPIO_OUT, GPIO.OUT)\nGPIO.output(MY_GPIO_OUT, GPIO.HIGH)",
            "Set GPIO Low": "GPIO.output(MY_GPIO_OUT, GPIO.LOW)",
            "Read GPIO Input": "# GPIO.setup(MY_GPIO_IN, GPIO.IN)\ninput_state = GPIO.input(MY_GPIO_IN)",
            "PWM Set Duty Cycle": "# pwm_pin = GPIO.PWM(MY_PWM_PIN, 50) # 50Hz\n# pwm_pin.start(0)\npwm_pin.ChangeDutyCycle(75) # 75%",
            "Print to Console": "print('RPi Log: Message')",
            "Sleep Seconds": "import time\ntime.sleep(1.0)",
        },
        "events": {
            "GPIO Edge Event": "event_gpio_edge_detected",
            "Network Packet Event": "event_network_packet",
        },
        "conditions": {
            "GPIO Input is High": "GPIO.input(MY_GPIO_IN) == GPIO.HIGH", 
            "Check File Exists": "import os\nos.path.exists('/path/to/file')",
            "Variable Check": "current_value >= MAX_LIMIT",
        }
    },
    EXECUTION_ENV_MICROPYTHON: {
        "actions": {
            "Set Pin High": "# from machine import Pin\n# my_output_pin = Pin(PIN_NUMBER, Pin.OUT)\nmy_output_pin.on()",
            "Set Pin Low": "my_output_pin.off()",
            "Toggle Pin": "my_output_pin.value(not my_output_pin.value())",
            "Read ADC": "# from machine import ADC\n# adc_pin = ADC(Pin(ADC_PIN_NUM))\nvalue = adc_pin.read_u16()",
            "Delay Milliseconds": "import time\ntime.sleep_ms(100)",
        },
        "events": {
             "IRQ Pin Event": "EVENT_PIN_IRQ", 
             "Timer Callback Event": "EVENT_TIMER_CB" 
        },
        "conditions": {
            "Pin Value is High": "my_input_pin.value() == 1", 
            "Variable Check": "some_variable > THRESHOLD_VALUE",
        }
    },
    EXECUTION_ENV_C_GENERIC: {
         "actions": {
            "Set Register Bit": "SOME_REGISTER |= (1 << BIT_POS);",
            "Clear Register Bit": "SOME_REGISTER &= ~(1 << BIT_POS);",
            "Toggle Register Bit": "SOME_REGISTER ^= (1 << BIT_POS);",
            "Write to Port": "PORT_ADDRESS = 0xFF;",
            "Basic Delay Loop": "for(volatile int i=0; i<10000; i++); // Simple delay",
            "Call Control Function": "control_actuator(PARAM1, PARAM2); /* Implement this */",
        },
        "events": {
            "Interrupt_Event": "EVT_HW_INTERRUPT",
            "Message_Received_Event": "EVT_MSG_RECEIVED",
            "Watchdog_Timeout": "EVT_WATCHDOG_TIMEOUT",
        },
        "conditions": {
            "Check Register Bit Set": "(SOME_REGISTER & (1 << BIT_POS)) != 0",
            "Compare Values": "sensor_reading > THRESHOLD_VALUE",
            "Data Buffer Ready": "is_data_buffer_full() /* Implement this */",
        }
    }
}

FSM_TEMPLATES_BUILTIN = {
    "debounce": """
        {
            "name": "Debounce Logic (Built-in)",
            "description": "A simple debounce pattern for an input signal. Assumes 'start_debounce_timer()' and 'input_change' / 'debounce_timer_expired' events.",
            "icon_resource": ":/icons/debounce_icon.png",
            "states": [
                {
                    "name": "Unstable", "x": 50, "y": 50, "width": 120, "height": 60,
                    "description": "Input is currently unstable or bouncing.",
                    "action_language": "Python (Generic Simulation)"
                },
                {
                    "name": "Waiting", "x": 250, "y": 50, "width": 120, "height": 60,
                    "entry_action": "start_debounce_timer()",
                    "action_language": "Python (Generic Simulation)"
                },
                {
                    "name": "Stable", "x": 450, "y": 50, "width": 120, "height": 60,
                    "description": "Input is considered stable.",
                    "action_language": "Python (Generic Simulation)"
                }
            ],
            "transitions": [
                {"source": "Unstable", "target": "Waiting", "event": "input_change", "action_language": "Python (Generic Simulation)"},
                {"source": "Waiting", "target": "Stable", "event": "debounce_timer_expired", "action_language": "Python (Generic Simulation)"},
                {"source": "Waiting", "target": "Unstable", "event": "input_change_while_waiting", "control_offset_y": 40, "action_language": "Python (Generic Simulation)"},
                {"source": "Stable", "target": "Unstable", "event": "input_goes_unstable_again", "control_offset_y": -40, "action_language": "Python (Generic Simulation)"}
            ],
            "comments": [
                 {"text": "Debounce timer should be set appropriately based on input characteristics.", "x": 150, "y": 150, "width": 250}
            ]
        }
    """,
    "blinker": """
        {
            "name": "Simple Blinker",
            "description": "Toggles between On and Off states. Assumes 'set_led_high/low' actions and timer events are handled externally.",
            "icon_resource": ":/icons/blinker_icon.png",
            "states": [
                {"name": "LedOn", "x": 0, "y": 0, "width": 100, "height": 50, "entry_action": "set_led_high()", "color": "#AED581", "action_language": "Python (Generic Simulation)"},
                {"name": "LedOff", "x": 200, "y": 0, "width": 100, "height": 50, "entry_action": "set_led_low()", "color": "#EF9A9A", "action_language": "Python (Generic Simulation)"}
            ],
            "transitions": [
                {"source": "LedOn", "target": "LedOff", "event": "on_timer_expired", "action_language": "Python (Generic Simulation)"},
                {"source": "LedOff", "target": "LedOn", "event": "off_timer_expired", "action_language": "Python (Generic Simulation)"}
            ],
            "comments": [
                {"text": "Requires external timer logic to trigger events (e.g., 'on_timer_expired', 'off_timer_expired'). Implement 'set_led_high()' and 'set_led_low()' actions.", "x": 0, "y": 80, "width": 300}
            ]
        }
    """
}

COLOR_BACKGROUND_APP = "#ECEFF1"
COLOR_BACKGROUND_LIGHT = "#FAFAFA"
COLOR_BACKGROUND_MEDIUM = "#E0E0E0"
COLOR_BACKGROUND_DARK = "#BDBDBD"
COLOR_BACKGROUND_EDITOR_DARK = "#263238"
COLOR_TEXT_EDITOR_DARK_PRIMARY = "#ECEFF1"
COLOR_TEXT_EDITOR_DARK_SECONDARY = "#90A4AE"
COLOR_BACKGROUND_DIALOG = "#FFFFFF"
COLOR_TEXT_PRIMARY = "#212121"
COLOR_TEXT_SECONDARY = "#757575"
COLOR_TEXT_ON_ACCENT = "#FFFFFF"
COLOR_ACCENT_PRIMARY = "#0277BD"
COLOR_ACCENT_PRIMARY_LIGHT = "#B3E5FC"
COLOR_ACCENT_SECONDARY = "#FF8F00"
COLOR_ACCENT_SECONDARY_LIGHT = "#FFECB3"
COLOR_ACCENT_SUCCESS = "#4CAF50"
COLOR_ACCENT_WARNING = "#FFC107"
COLOR_ACCENT_ERROR = "#D32F2F"
COLOR_BORDER_LIGHT = "#CFD8DC"
COLOR_BORDER_MEDIUM = "#90A4AE"
COLOR_BORDER_DARK = "#607D8B"
COLOR_ITEM_STATE_DEFAULT_BG = "#E3F2FD"
COLOR_ITEM_STATE_DEFAULT_BORDER = "#64B5F6"
COLOR_ITEM_STATE_SELECTION_BG = "#FFECB3"
COLOR_ITEM_STATE_SELECTION_BORDER = COLOR_ACCENT_SECONDARY
COLOR_ITEM_TRANSITION_DEFAULT = "#00796B"
COLOR_ITEM_TRANSITION_SELECTION = "#B2DFDB"
COLOR_ITEM_COMMENT_BG = "#FFF9C4"
COLOR_ITEM_COMMENT_BORDER = "#FFEE58"
COLOR_GRID_MINOR = "#ECEFF1"
COLOR_GRID_MAJOR = "#CFD8DC"
COLOR_DRAGGABLE_BUTTON_BG = "#E8EAF6"
COLOR_DRAGGABLE_BUTTON_BORDER = "#C5CAE9"
COLOR_DRAGGABLE_BUTTON_HOVER_BG = "#B9D9EB"
COLOR_DRAGGABLE_BUTTON_HOVER_BORDER = COLOR_ACCENT_PRIMARY
COLOR_DRAGGABLE_BUTTON_PRESSED_BG = "#98BAD6"
COLOR_PY_SIM_STATE_ACTIVE = QColor(COLOR_ACCENT_SUCCESS)
COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH = 2.5
APP_FONT_FAMILY = "Segoe UI, Arial, sans-serif"
APP_FONT_SIZE_STANDARD = "9pt"
APP_FONT_SIZE_SMALL = "8pt"
APP_FONT_SIZE_EDITOR = "10pt"

STYLE_SHEET_GLOBAL = f"""
    QWidget {{
        font-family: {APP_FONT_FAMILY};
        font-size: {APP_FONT_SIZE_STANDARD};
    }}
    QMainWindow {{
        background-color: {COLOR_BACKGROUND_APP};
    }}
    QDockWidget::title {{
        background-color: {QColor(COLOR_BACKGROUND_MEDIUM).darker(105).name()};
        padding: 6px 10px; /* Reduced padding */
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom: 2px solid {COLOR_ACCENT_PRIMARY};
        font-weight: bold;
        color: {COLOR_TEXT_PRIMARY};
        border-top-left-radius: 3px; /* Smaller radius */
        border-top-right-radius: 3px;
    }}
    QDockWidget {{
        border: 1px solid {COLOR_BORDER_LIGHT};
    }}
    QDockWidget::close-button, QDockWidget::float-button {{
        subcontrol-position: top right;
        subcontrol-origin: margin;
        position: absolute;
        top: 1px; right: 4px; padding: 1px; /* Smaller padding */
        border-radius: 2px;
    }}
    QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
        background-color: {COLOR_BACKGROUND_DARK};
    }}
    QToolBar {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        border-bottom: 1px solid {COLOR_BORDER_LIGHT};
        padding: 2px; /* Reduced padding */
        spacing: 3px; /* Reduced spacing */
    }}
    QToolButton {{
        background-color: transparent;
        color: {COLOR_TEXT_PRIMARY};
        padding: 4px 6px; /* Reduced padding */
        margin: 0px; /* Reduced margin */
        border: 1px solid transparent;
        border-radius: 3px;
    }}
    QToolButton:hover, QDockWidget#ToolsDock QToolButton:hover {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QToolButton:pressed, QDockWidget#ToolsDock QToolButton:pressed {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}
    QToolButton:checked, QDockWidget#ToolsDock QToolButton:checked {{
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
        padding: 2px; /* Reduced padding */
    }}
    QMenuBar::item {{
        background-color: transparent;
        padding: 4px 10px; /* Reduced padding */
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
        border-radius: 3px;
        padding: 4px; /* Reduced padding */
    }}
    QMenu::item {{
        padding: 5px 25px 5px 25px; /* Adjusted padding */
        border-radius: 3px;
    }}
    QMenu::item:selected {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}
    QMenu::separator {{
        height: 1px;
        background: {COLOR_BORDER_LIGHT};
        margin: 4px 6px; /* Reduced margin */
    }}
    QMenu::icon {{
        padding-left: 5px;
    }}
    QStatusBar {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_PRIMARY};
        border-top: 1px solid {COLOR_BORDER_LIGHT};
        padding: 2px 4px; /* Reduced padding */
    }}
    QStatusBar::item {{
        border: none;
        margin: 0 2px; /* Reduced margin */
    }}
    QLabel#StatusLabel, QLabel#MatlabStatusLabel, QLabel#PySimStatusLabel, QLabel#AIChatStatusLabel, QLabel#InternetStatusLabel,
    QLabel#MainOpStatusLabel, QLabel#IdeFileStatusLabel,
    QMainWindow QLabel[objectName$="StatusLabel"],
    QLabel#ZoomStatusLabel
    {{
         padding: 1px 4px; /* Reduced padding */
         font-size: {APP_FONT_SIZE_SMALL};
         border-radius: 2px;
    }}
    QLabel#CpuStatusLabel, QLabel#RamStatusLabel, QLabel#GpuStatusLabel {{
        font-size: {APP_FONT_SIZE_SMALL};
        padding: 1px 4px; /* Reduced padding */
        min-width: 60px; /* Slightly reduced min-width */
        border: 1px solid {COLOR_BORDER_LIGHT};
        background-color: {COLOR_BACKGROUND_APP};
        border-radius: 2px;
    }}
    QDialog {{
        background-color: {COLOR_BACKGROUND_DIALOG};
    }}
    QLabel {{
        color: {COLOR_TEXT_PRIMARY};
        background-color: transparent;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
        background-color: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 3px; /* Smaller radius */
        padding: 5px 7px; /* Reduced padding */
        font-size: {APP_FONT_SIZE_STANDARD};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border: 1.5px solid {COLOR_ACCENT_PRIMARY};
        outline: none;
    }}
    QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_SECONDARY};
        border-color: {COLOR_BORDER_LIGHT};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 22px; /* Smaller dropdown arrow area */
        border-left-width: 1px;
        border-left-color: {COLOR_BORDER_MEDIUM};
        border-left-style: solid;
        border-top-right-radius: 2px;
        border-bottom-right-radius: 2px;
        background-color: {COLOR_BACKGROUND_LIGHT};
    }}
    QComboBox::drop-down:hover {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
    }}
    QComboBox::down-arrow {{
         image: url(:/icons/arrow_down.png);
         width: 10px; height:10px; /* Smaller arrow */
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLOR_BACKGROUND_DIALOG};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        selection-background-color: {COLOR_ACCENT_PRIMARY};
        selection-color: {COLOR_TEXT_ON_ACCENT};
        border-radius: 2px;
        padding: 1px;
    }}
    QPushButton {{
        background-color: #F5F5F5;
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        padding: 6px 15px; /* Reduced padding */
        border-radius: 4px; /* Slightly smaller radius */
        min-height: 22px; /* Reduced min-height */
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
        background-color: {COLOR_BACKGROUND_LIGHT};
        color: {COLOR_TEXT_SECONDARY};
        border-color: {COLOR_BORDER_LIGHT};
    }}
    QDialogButtonBox QPushButton {{
        min-width: 80px; /* Reduced min-width */
    }}
    QDialogButtonBox QPushButton[text="OK"], QDialogButtonBox QPushButton[text="Apply & Close"],
    QDialogButtonBox QPushButton[text="Save"]
    {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
        border-color: {QColor(COLOR_ACCENT_PRIMARY).darker(120).name()};
        font-weight: bold;
    }}
    QDialogButtonBox QPushButton[text="OK"]:hover, QDialogButtonBox QPushButton[text="Apply & Close"]:hover,
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
        border-radius: 4px; /* Smaller radius */
        margin-top: 10px; /* Reduced margin */
        padding: 10px 8px 8px 8px; /* Adjusted padding */
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px; /* Reduced padding */
        left: 10px; /* Adjusted position */
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
        padding: 6px; /* Reduced padding */
    }}
    QTabBar::tab {{
        background: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_SECONDARY};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom-color: {COLOR_BACKGROUND_DIALOG}; 
        border-top-left-radius: 3px;
        border-top-right-radius: 3px;
        padding: 6px 15px; /* Reduced padding */
        margin-right: 1px;
        min-width: 70px; /* Reduced min-width */
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
        spacing: 8px; /* Reduced spacing */
    }}
    QCheckBox::indicator {{
        width: 14px; /* Smaller indicator */
        height: 14px;
    }}
    QCheckBox::indicator:unchecked {{
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 2px;
        background-color: {COLOR_BACKGROUND_DIALOG};
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
    QTextEdit#LogOutputWidget, QTextEdit#PySimActionLog, QTextEdit#AIChatDisplay,
    QPlainTextEdit#ActionCodeEditor, QTextEdit#IDEOutputConsole, QPlainTextEdit#StandaloneCodeEditor,
    QTextEdit#SubFSMJsonEditor 
    {{
         font-family: Consolas, 'Courier New', monospace;
         font-size: {APP_FONT_SIZE_EDITOR};
         background-color: {COLOR_BACKGROUND_EDITOR_DARK};
         color: {COLOR_TEXT_EDITOR_DARK_PRIMARY};
         border: 1px solid {COLOR_BORDER_DARK};
         border-radius: 3px;
         padding: 6px; /* Reduced padding */
         selection-background-color: {QColor(COLOR_ACCENT_PRIMARY).darker(110).name()};
         selection-color: {COLOR_TEXT_ON_ACCENT};
    }}
    QScrollBar:vertical {{
         border: 1px solid {COLOR_BORDER_LIGHT};
         background: {COLOR_BACKGROUND_LIGHT};
         width: 14px; /* Thinner scrollbars */
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
         background: {COLOR_BACKGROUND_LIGHT};
         height: 14px; /* Thinner scrollbars */
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

    QTextEdit#LogOutputWidget QScrollBar:vertical, QTextEdit#PySimActionLog QScrollBar:vertical,
    QTextEdit#AIChatDisplay QScrollBar:vertical, QPlainTextEdit#ActionCodeEditor QScrollBar:vertical,
    QTextEdit#IDEOutputConsole QScrollBar:vertical, QPlainTextEdit#StandaloneCodeEditor QScrollBar:vertical,
    QTextEdit#SubFSMJsonEditor QScrollBar:vertical
    {{
         border: 1px solid {COLOR_BORDER_DARK};
         background: {QColor(COLOR_BACKGROUND_EDITOR_DARK).lighter(110).name()};
    }}
    QTextEdit#LogOutputWidget QScrollBar::handle:vertical, QTextEdit#PySimActionLog QScrollBar::handle:vertical,
    QTextEdit#AIChatDisplay QScrollBar::handle:vertical, QPlainTextEdit#ActionCodeEditor QScrollBar::handle:vertical,
    QTextEdit#IDEOutputConsole QScrollBar::handle:vertical, QPlainTextEdit#StandaloneCodeEditor QScrollBar::handle:vertical,
    QTextEdit#SubFSMJsonEditor QScrollBar::handle:vertical
    {{
         background: {COLOR_TEXT_EDITOR_DARK_SECONDARY};
    }}
    QTextEdit#LogOutputWidget QScrollBar::handle:vertical:hover, QTextEdit#PySimActionLog QScrollBar::handle:vertical:hover,
    QTextEdit#AIChatDisplay QScrollBar::handle:vertical:hover, QPlainTextEdit#ActionCodeEditor QScrollBar::handle:vertical:hover,
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
        padding: 4px 8px; /* Reduced padding */
        min-height: 0;
    }}
    QPushButton#SnippetButton:hover {{
        background-color: {QColor(COLOR_ACCENT_SECONDARY).lighter(110).name()};
    }}
    QPushButton#ColorButton, QPushButton#ColorButtonPropertiesDock {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; min-height: 24px; padding: 3px; /* Reduced */
    }}
    QPushButton#ColorButton:hover, QPushButton#ColorButtonPropertiesDock:hover {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QProgressBar {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; border-radius: 3px;
        background-color: {COLOR_BACKGROUND_LIGHT}; text-align: center;
        color: {COLOR_TEXT_PRIMARY}; height: 12px; /* Reduced height */
    }}
    QProgressBar::chunk {{
        background-color: {COLOR_ACCENT_PRIMARY}; border-radius: 2px;
    }}
    QPushButton#DraggableToolButton {{
        background-color: {COLOR_DRAGGABLE_BUTTON_BG}; color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_DRAGGABLE_BUTTON_BORDER};
        padding: 5px 7px;  /* Slightly reduced from 6px 8px */
        text-align: left; 
        font-weight: 500;
        min-height: 32px; /* Slightly reduced from 34px */
    }}
    QPushButton#DraggableToolButton:hover {{
        background-color: {COLOR_DRAGGABLE_BUTTON_HOVER_BG}; border-color: {COLOR_DRAGGABLE_BUTTON_HOVER_BORDER};
    }}
    QPushButton#DraggableToolButton:pressed {{ background-color: {COLOR_DRAGGABLE_BUTTON_PRESSED_BG}; }}

    #PropertiesDock QLabel#PropertiesLabel {{
        padding: 6px; background-color: {COLOR_BACKGROUND_DIALOG}; /* Reduced padding */
        border: 1px solid {COLOR_BORDER_LIGHT}; border-radius: 3px;
        font-size: {APP_FONT_SIZE_STANDARD};
    }}
    #PropertiesDock QPushButton {{ /* General button style within properties dock */
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT};
        font-weight:bold;
    }}
    #PropertiesDock QPushButton:hover {{ background-color: {QColor(COLOR_ACCENT_PRIMARY).lighter(110).name()}; }}
    #PropertiesDock QPushButton#ColorButtonPropertiesDock {{
         /* Styles for this are now handled by _update_dock_color_button_style in main.py */
    }}


    QDockWidget#ToolsDock QToolButton {{
        padding: 6px 8px; text-align: left; /* Reduced padding */
        min-height: 34px; /* Reduced height */
        font-weight: 500;
    }}

    QDockWidget#PySimDock QPushButton {{
        padding: 5px 10px; /* Reduced padding */
    }}
    QDockWidget#PySimDock QPushButton:disabled {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_SECONDARY};
    }}
    QDockWidget#PySimDock QTableWidget {{
        alternate-background-color: {COLOR_BACKGROUND_APP};
        gridline-color: {COLOR_BORDER_LIGHT};
        background-color: {COLOR_BACKGROUND_DIALOG};
    }}
     QDockWidget#PySimDock QHeaderView::section,
     QTableWidget QHeaderView::section
     {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        padding: 4px; /* Reduced padding */
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom: 2px solid {COLOR_BORDER_DARK};
        font-weight: bold;
    }}
    QDockWidget#AIChatbotDock QPushButton#AIChatSendButton,
    QDockWidget#PySimDock QPushButton[text="Trigger"]
    {{
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT};
        font-weight: bold;
        padding: 5px; /* Reduced padding */
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
        padding: 6px 8px; /* Reduced padding */
    }}
    QDockWidget#ProblemsDock QListWidget::item {{ 
        padding: 4px; /* Reduced padding */
        border-bottom: 1px dotted {COLOR_BORDER_LIGHT};
    }}
    QDockWidget#ProblemsDock QListWidget::item:selected {{ 
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QLabel#ErrorLabel {{ 
        color: {COLOR_ACCENT_ERROR}; 
        font-weight: bold; 
    }}

""" 