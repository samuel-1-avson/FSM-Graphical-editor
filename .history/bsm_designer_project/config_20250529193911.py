from PyQt5.QtGui import QColor

# --- Configuration ---
APP_VERSION = "1.7.1" # Added IDE features for embedded
APP_NAME = "Brain State Machine Designer"
FILE_EXTENSION = ".bsm"
FILE_FILTER = f"Brain State Machine Files (*{FILE_EXTENSION});;All Files (*)"

# --- Execution Environments and Snippets ---
EXECUTION_ENV_PYTHON_GENERIC = "Python (Generic Simulation)"
EXECUTION_ENV_ARDUINO_CPP = "Arduino (C++)"
EXECUTION_ENV_RASPBERRYPI_PYTHON = "RaspberryPi (Python)"
EXECUTION_ENV_MICROPYTHON = "MicroPython"
EXECUTION_ENV_C_GENERIC = "C (Generic Embedded)"

# Default environment for new actions
DEFAULT_EXECUTION_ENV = EXECUTION_ENV_PYTHON_GENERIC

MECHATRONICS_SNIPPETS = {
    EXECUTION_ENV_PYTHON_GENERIC: {
        "actions": {
            "Print Message": "print('My message')",
            "Set Variable": "my_var = 10",
            "Increment Variable": "counter_var = counter_var + 1",
            "Conditional Print": "if condition_var:\n    print('Condition met')",
            "Log Value": "print(f'Value of x: {x_variable}')" # Python 3.6+ f-string
        },
        "events": { # Events are usually simple strings, less language-specific for triggering
            "Timeout Event": "timeout_event",
            "Sensor Trigger": "sensor_triggered",
            "User Input": "user_input_received",
        },
        "conditions": {
            "Variable Equals": "my_var == 10",
            "Variable Greater Than": "counter_var > 5",
            "Flag is True": "is_ready_flag", # Assumes boolean variable
            "Function Returns True": "check_condition_function()",
        }
    },
    EXECUTION_ENV_ARDUINO_CPP: {
        "actions": {
            "Digital Write High": "digitalWrite(PIN_NUMBER, HIGH);",
            "Digital Write Low": "digitalWrite(PIN_NUMBER, LOW);",
            "Analog Read": "int sensorValue = analogRead(ANALOG_PIN);",
            "Serial Print": "Serial.println(\"Hello, Arduino!\");",
            "Delay Milliseconds": "delay(1000); // Pauses for 1 second",
            "Set Pin Mode Output": "pinMode(PIN_NUMBER, OUTPUT);",
            "Set Pin Mode Input": "pinMode(PIN_NUMBER, INPUT);",
        },
        "events": {
            "Button Press (Interrupt)": "button_interrupt_event", # Placeholder, actual handling is complex
            "Timer Overflow": "timer_overflow_event",
        },
        "conditions": {
            "Digital Read High": "digitalRead(PIN_NUMBER) == HIGH",
            "Variable Equals": "variable_name == 100",
            "Millis Timeout": "(millis() - last_timestamp) > TIMEOUT_INTERVAL",
        }
    },
    EXECUTION_ENV_RASPBERRYPI_PYTHON: {
        "actions": {
            "GPIO Output High (RPi.GPIO)": "import RPi.GPIO as GPIO\nGPIO.setmode(GPIO.BCM) # or GPIO.BOARD\nGPIO.setup(PIN_NUMBER, GPIO.OUT)\nGPIO.output(PIN_NUMBER, GPIO.HIGH)",
            "GPIO Output Low (RPi.GPIO)": "import RPi.GPIO as GPIO\nGPIO.output(PIN_NUMBER, GPIO.LOW)",
            "Read GPIO Input (RPi.GPIO)": "import RPi.GPIO as GPIO\nGPIO.setup(PIN_NUMBER, GPIO.IN)\ninput_value = GPIO.input(PIN_NUMBER)",
            "Print to Console": "print('RPi Log: Message')",
            "Sleep Seconds": "import time\ntime.sleep(1.0)",
        },
        "events": {
            "GPIO Interrupt": "gpio_interrupt_event",
            "Network Message": "network_message_received",
        },
        "conditions": {
            "GPIO Input is High": "GPIO.input(PIN_NUMBER) == GPIO.HIGH", # Assumes RPi.GPIO imported and set up
            "Check File Exists": "import os\nos.path.exists('/path/to/file')",
        }
    },
    EXECUTION_ENV_MICROPYTHON: {
        "actions": {
            "Pin Output High": "from machine import Pin\npin = Pin(PIN_NUMBER, Pin.OUT)\npin.on() # or pin.value(1)",
            "Pin Output Low": "from machine import Pin\npin = Pin(PIN_NUMBER, Pin.OUT)\npin.off() # or pin.value(0)",
            "Read Pin Input": "from machine import Pin\npin = Pin(PIN_NUMBER, Pin.IN, Pin.PULL_UP)\nvalue = pin.value()",
            "ADC Read": "from machine import ADC\nadc = ADC(Pin(ADC_PIN_NUMBER))\nvalue = adc.read_u16()",
            "Delay Milliseconds": "import time\ntime.sleep_ms(100)",
        },
        "events": {
            "Pin Interrupt": "pin_interrupt_event",
            "Timer Callback": "timer_callback_event",
        },
        "conditions": {
            "Pin Value is High": "pin_instance.value() == 1",
            "Variable Check": "some_variable > THRESHOLD",
        }
    },
    EXECUTION_ENV_C_GENERIC: {
        "actions": {
            "Set Register Bit": "REGISTER_NAME |= (1 << BIT_POSITION);",
            "Clear Register Bit": "REGISTER_NAME &= ~(1 << BIT_POSITION);",
            "Toggle Register Bit": "REGISTER_NAME ^= (1 << BIT_POSITION);",
            "Write to Port": "PORT_ADDRESS = 0xFF;",
            "Basic Delay Loop": "for(volatile int i=0; i<10000; i++); // Simple delay",
        },
        "events": {
            "Hardware Interrupt": "ISR_event_flag_set",
            "Watchdog Timeout": "watchdog_timeout_event",
        },
        "conditions": {
            "Check Register Bit": "(REGISTER_NAME & (1 << BIT_POSITION)) != 0",
            "Compare Values": "sensor_reading > THRESHOLD_VALUE",
        }
    }
}

# --- UI Styling and Theme Colors ---
COLOR_BACKGROUND_APP = "#ECEFF1"  # Material Blue Grey 50 (Lighter overall background)
COLOR_BACKGROUND_LIGHT = "#FAFAFA" # Slightly off-white for content areas like scene, dialogs
COLOR_BACKGROUND_MEDIUM = "#E0E0E0" # For toolbars, menu bars, dock titles
COLOR_BACKGROUND_DARK = "#BDBDBD"   # For heavier UI elements or separators

COLOR_BACKGROUND_EDITOR_DARK = "#263238" # Material Blue Grey 900 (Code editors, logs)
COLOR_TEXT_EDITOR_DARK_PRIMARY = "#ECEFF1" # Material Blue Grey 50 (Text on dark editors)
COLOR_TEXT_EDITOR_DARK_SECONDARY = "#90A4AE" # Material Blue Grey 300 (Comments, line numbers on dark)

COLOR_BACKGROUND_DIALOG = "#FFFFFF" # Keep dialogs clean white
COLOR_TEXT_PRIMARY = "#212121"      # Dark Grey for general text
COLOR_TEXT_SECONDARY = "#757575"    # Medium Grey for less important text
COLOR_TEXT_ON_ACCENT = "#FFFFFF"    # White text on primary accent color

COLOR_ACCENT_PRIMARY = "#0277BD" # Material Light Blue 700 (Slightly darker primary blue)
COLOR_ACCENT_PRIMARY_LIGHT = "#B3E5FC" # Material Light Blue 100
COLOR_ACCENT_SECONDARY = "#FF8F00" # Amber 700
COLOR_ACCENT_SECONDARY_LIGHT = "#FFECB3" # Amber 100

COLOR_ACCENT_SUCCESS = "#4CAF50" # Material Green 500
COLOR_ACCENT_WARNING = "#FFC107" # Material Amber 500
COLOR_ACCENT_ERROR = "#D32F2F"   # Material Red 700

COLOR_BORDER_LIGHT = "#CFD8DC"   # Material Blue Grey 100
COLOR_BORDER_MEDIUM = "#90A4AE"  # Material Blue Grey 300
COLOR_BORDER_DARK = "#607D8B"    # Material Blue Grey 500

COLOR_ITEM_STATE_DEFAULT_BG = "#E3F2FD" # Material Blue 50
COLOR_ITEM_STATE_DEFAULT_BORDER = "#64B5F6" # Material Blue 300
COLOR_ITEM_STATE_SELECTION_BG = "#FFECB3" # Material Amber 100
COLOR_ITEM_STATE_SELECTION_BORDER = COLOR_ACCENT_SECONDARY # Amber 700
COLOR_ITEM_TRANSITION_DEFAULT = "#00796B" # Material Teal 700
COLOR_ITEM_TRANSITION_SELECTION = "#B2DFDB" # Material Teal 100
COLOR_ITEM_COMMENT_BG = "#FFF9C4" # Material Yellow 100
COLOR_ITEM_COMMENT_BORDER = "#FFEE58" # Material Yellow 400

COLOR_GRID_MINOR = "#ECEFF1" # Material Blue Grey 50
COLOR_GRID_MAJOR = "#CFD8DC" # Material Blue Grey 100

# Specific UI Element Colors
COLOR_DRAGGABLE_BUTTON_BG = "#E8EAF6"      # Material Indigo 50
COLOR_DRAGGABLE_BUTTON_BORDER = "#C5CAE9"  # Material Indigo 100
COLOR_DRAGGABLE_BUTTON_HOVER_BG = "#B9D9EB" # Light Blue for hover
COLOR_DRAGGABLE_BUTTON_HOVER_BORDER = COLOR_ACCENT_PRIMARY
COLOR_DRAGGABLE_BUTTON_PRESSED_BG = "#98BAD6" # Darker blue for pressed

# Python Simulation Highlight Colors
COLOR_PY_SIM_STATE_ACTIVE = QColor(COLOR_ACCENT_SUCCESS)
COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH = 2.5

APP_FONT_FAMILY = "Segoe UI, Arial, sans-serif"
APP_FONT_SIZE_STANDARD = "9pt"
APP_FONT_SIZE_SMALL = "8pt"
APP_FONT_SIZE_EDITOR = "10pt" # For code editors

STYLE_SHEET_GLOBAL = f"""
    QWidget {{
        font-family: {APP_FONT_FAMILY};
        font-size: {APP_FONT_SIZE_STANDARD};
    }}
    QMainWindow {{
        background-color: {COLOR_BACKGROUND_APP};
    }}
    QDockWidget::title {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        padding: 7px 10px;
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom: 2px solid {COLOR_ACCENT_PRIMARY};
        font-weight: bold;
        color: {COLOR_TEXT_PRIMARY};
        border-top-left-radius: 3px;
        border-top-right-radius: 3px;
    }}
    QDockWidget {{
        border: 1px solid {COLOR_BORDER_LIGHT}; 
    }}
    QDockWidget::close-button, QDockWidget::float-button {{
        subcontrol-position: top right;
        subcontrol-origin: margin;
        position: absolute;
        top: 2px; right: 5px; padding: 2px;
        border-radius: 3px;
    }}
    QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
        background-color: {COLOR_BACKGROUND_DARK};
    }}
    QToolBar {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        border-bottom: 1px solid {COLOR_BORDER_LIGHT};
        padding: 4px;
        spacing: 5px;
    }}
    QToolButton {{
        background-color: transparent;
        color: {COLOR_TEXT_PRIMARY};
        padding: 6px 8px;
        margin: 1px;
        border: 1px solid transparent;
        border-radius: 4px;
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
        padding: 3px;
    }}
    QMenuBar::item {{
        background-color: transparent;
        padding: 6px 14px;
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
        padding: 5px;
    }}
    QMenu::item {{
        padding: 7px 30px 7px 30px; 
        border-radius: 3px;
    }}
    QMenu::item:selected {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}
    QMenu::separator {{
        height: 1px;
        background: {COLOR_BORDER_LIGHT};
        margin: 5px 8px;
    }}
    QMenu::icon {{
        padding-left: 6px;
    }}
    QStatusBar {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_PRIMARY};
        border-top: 1px solid {COLOR_BORDER_LIGHT};
        padding: 3px 5px; 
    }}
    QStatusBar::item {{
        border: none; 
        margin: 0 3px;
    }}
    QLabel#StatusLabel, QLabel#MatlabStatusLabel, QLabel#PySimStatusLabel, QLabel#AIChatStatusLabel, QLabel#InternetStatusLabel,
    QMainWindow QLabel[objectName$="StatusLabel"] 
    {{
         padding: 2px 6px;
         font-size: {APP_FONT_SIZE_SMALL};
         border-radius: 3px; 
    }}
    QLabel#CpuStatusLabel, QLabel#RamStatusLabel, QLabel#GpuStatusLabel {{
        font-size: {APP_FONT_SIZE_SMALL};
        padding: 2px 6px;
        min-width: 70px; 
        border: 1px solid {COLOR_BORDER_LIGHT};
        background-color: {COLOR_BACKGROUND_APP};
        border-radius: 3px;
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
        border-radius: 4px; 
        padding: 6px 8px;
        font-size: {APP_FONT_SIZE_STANDARD};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
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
        width: 25px; 
        border-left-width: 1px;
        border-left-color: {COLOR_BORDER_MEDIUM};
        border-left-style: solid;
        border-top-right-radius: 3px;
        border-bottom-right-radius: 3px;
        background-color: {COLOR_BACKGROUND_LIGHT}; 
    }}
    QComboBox::drop-down:hover {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
    }}
    QComboBox::down-arrow {{
         image: url(./dependencies/icons/arrow_down.png);
         width: 12px; height:12px; 
    }}
    QComboBox QAbstractItemView {{ 
        background-color: {COLOR_BACKGROUND_DIALOG};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        selection-background-color: {COLOR_ACCENT_PRIMARY};
        selection-color: {COLOR_TEXT_ON_ACCENT};
        border-radius: 3px; 
        padding: 2px;
    }}
    QPushButton {{
        background-color: #EFEFEF; 
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        padding: 7px 18px; 
        border-radius: 4px;
        min-height: 22px;
        font-weight: 500; 
    }}
    QPushButton:hover {{
        background-color: {QColor(COLOR_BACKGROUND_MEDIUM).lighter(105).name()};
        border-color: {COLOR_BORDER_DARK};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_BACKGROUND_DARK};
    }}
    QPushButton:disabled {{
        background-color: {COLOR_BACKGROUND_LIGHT}; 
        color: {COLOR_TEXT_SECONDARY};
        border-color: {COLOR_BORDER_LIGHT};
    }}
    QDialogButtonBox QPushButton {{
        min-width: 90px;
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
        border-radius: 5px;
        margin-top: 12px; 
        padding: 12px 10px 10px 10px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 10px; 
        left: 12px;
        background-color: {COLOR_BACKGROUND_APP}; 
        color: {COLOR_ACCENT_PRIMARY};
        font-weight: bold;
        border-radius: 3px;
    }}
    QTabWidget::pane {{
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-top: none; 
        border-bottom-left-radius: 4px;
        border-bottom-right-radius: 4px;
        background-color: {COLOR_BACKGROUND_DIALOG};
        padding: 8px;
    }}
    QTabBar::tab {{
        background: {COLOR_BACKGROUND_MEDIUM};
        color: {COLOR_TEXT_SECONDARY};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom-color: {COLOR_BACKGROUND_DIALOG}; 
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        padding: 8px 18px; 
        margin-right: 2px;
        min-width: 80px; 
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
        spacing: 10px; 
    }}
    QCheckBox::indicator {{
        width: 16px; 
        height: 16px;
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
        border: 1px solid {QColor(COLOR_ACCENT_PRIMARY).darker(120).name()};
        border-radius: 3px;
        background-color: {COLOR_ACCENT_PRIMARY};
        image: url(./dependencies/icons/check.png); 
    }}
    QCheckBox::indicator:checked:hover {{
        background-color: {QColor(COLOR_ACCENT_PRIMARY).lighter(110).name()};
    }}
    QTextEdit#LogOutputWidget, QTextEdit#PySimActionLog, QTextEdit#AIChatDisplay,
    QPlainTextEdit#ActionCodeEditor, QTextEdit#IDEOutputConsole, QPlainTextEdit#StandaloneCodeEditor {{
         font-family: Consolas, 'Courier New', monospace;
         font-size: {APP_FONT_SIZE_EDITOR};
         background-color: {COLOR_BACKGROUND_EDITOR_DARK};
         color: {COLOR_TEXT_EDITOR_DARK_PRIMARY};
         border: 1px solid {COLOR_BORDER_DARK}; 
         border-radius: 4px;
         padding: 8px;
         selection-background-color: {QColor(COLOR_ACCENT_PRIMARY).darker(110).name()}; 
         selection-color: {COLOR_TEXT_ON_ACCENT};
    }}
    QScrollBar:vertical {{
         border: 1px solid {COLOR_BORDER_LIGHT};
         background: {COLOR_BACKGROUND_LIGHT};
         width: 16px; 
         margin: 0px;
    }}
    QScrollBar::handle:vertical {{
         background: {COLOR_BORDER_DARK}; 
         min-height: 30px; 
         border-radius: 8px; 
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
         height: 16px;
         margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
         background: {COLOR_BORDER_DARK};
         min-width: 30px;
         border-radius: 8px;
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
    QTextEdit#IDEOutputConsole QScrollBar:vertical, QPlainTextEdit#StandaloneCodeEditor QScrollBar:vertical {{
         border: 1px solid {COLOR_BORDER_DARK}; 
         background: {QColor(COLOR_BACKGROUND_EDITOR_DARK).lighter(110).name()}; 
    }}
    QTextEdit#LogOutputWidget QScrollBar::handle:vertical, QTextEdit#PySimActionLog QScrollBar::handle:vertical,
    QTextEdit#AIChatDisplay QScrollBar::handle:vertical, QPlainTextEdit#ActionCodeEditor QScrollBar::handle:vertical,
    QTextEdit#IDEOutputConsole QScrollBar::handle:vertical, QPlainTextEdit#StandaloneCodeEditor QScrollBar::handle:vertical {{
         background: {COLOR_TEXT_EDITOR_DARK_SECONDARY}; 
    }}
    QTextEdit#LogOutputWidget QScrollBar::handle:vertical:hover, QTextEdit#PySimActionLog QScrollBar::handle:vertical:hover,
    QTextEdit#AIChatDisplay QScrollBar::handle:vertical:hover, QPlainTextEdit#ActionCodeEditor QScrollBar::handle:vertical:hover,
    QTextEdit#IDEOutputConsole QScrollBar::handle:vertical:hover, QPlainTextEdit#StandaloneCodeEditor QScrollBar::handle:vertical:hover {{
         background: {QColor(COLOR_TEXT_EDITOR_DARK_SECONDARY).lighter(120).name()};
    }}

    QPushButton#SnippetButton {{
        background-color: {COLOR_ACCENT_SECONDARY};
        color: {COLOR_TEXT_PRIMARY}; 
        border: 1px solid {QColor(COLOR_ACCENT_SECONDARY).darker(130).name()};
        font-weight: normal;
        padding: 5px 10px; 
        min-height: 0; 
    }}
    QPushButton#SnippetButton:hover {{
        background-color: {QColor(COLOR_ACCENT_SECONDARY).lighter(110).name()};
    }}
    QPushButton#ColorButton {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; min-height: 26px; padding: 4px;
    }}
    QPushButton#ColorButton:hover {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QProgressBar {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; border-radius: 4px;
        background-color: {COLOR_BACKGROUND_LIGHT}; text-align: center;
        color: {COLOR_TEXT_PRIMARY}; height: 14px; 
    }}
    QProgressBar::chunk {{
        background-color: {COLOR_ACCENT_PRIMARY}; border-radius: 3px;
    }}
    QPushButton#DraggableToolButton {{
        background-color: {COLOR_DRAGGABLE_BUTTON_BG}; color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_DRAGGABLE_BUTTON_BORDER}; 
        padding: 9px; /* Adjusted padding - use qproperty-iconSize to ensure icon visibility */
        padding-left: 30px; /* Space for icon if set by qproperty-icon, and then text */
        text-align: left; font-weight: 500;
        qproperty-iconSize: 20px; /* Example if we need to enforce icon size for spacing calc */
    }}
    QPushButton#DraggableToolButton:hover {{
        background-color: {COLOR_DRAGGABLE_BUTTON_HOVER_BG}; border-color: {COLOR_DRAGGABLE_BUTTON_HOVER_BORDER};
    }}
    QPushButton#DraggableToolButton:pressed {{ background-color: {COLOR_DRAGGABLE_BUTTON_PRESSED_BG}; }}
    
    /* Styling for PropertiesDock (if needed beyond general QLabel) */
    #PropertiesDock QLabel#PropertiesLabel {{ /* Specific for the HTML display label */
        padding: 8px; background-color: {COLOR_BACKGROUND_DIALOG}; /* Slightly different from light, if preferred */
        border: 1px solid {COLOR_BORDER_LIGHT}; border-radius: 4px; line-height: 1.5;
        font-size: {APP_FONT_SIZE_STANDARD}; 
    }}
    #PropertiesDock QPushButton {{ 
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT};
        font-weight:bold; /* Make Edit button bold */
    }}
    #PropertiesDock QPushButton:hover {{ background-color: {QColor(COLOR_ACCENT_PRIMARY).lighter(110).name()}; }}

    QDockWidget#ToolsDock QToolButton {{ 
        padding: 8px 10px; text-align: left;
        min-height: 38px; /* Align height with DraggableToolButton */
        font-weight: 500; /* Match DraggableToolButton font weight */
    }}
    
    QDockWidget#PySimDock QPushButton {{
        padding: 6px 12px; 
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
        padding: 6px;
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom: 2px solid {COLOR_BORDER_DARK}; 
        font-weight: bold;
    }}
    QDockWidget#AIChatbotDock QPushButton#AIChatSendButton, 
    QDockWidget#PySimDock QPushButton[text="Trigger"] 
    {{
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT};
        font-weight: bold;
        /* For icon-only send button, ensure padding is small or icon is centered */
        padding: 6px; 
        min-width: 0; /* Allow button to be small */
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
        padding: 7px 9px; 
    }}
"""