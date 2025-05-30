from PyQt5.QtGui import QColor

# --- Configuration ---
APP_VERSION = "1.8.0" # Updated version
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
COLOR_BACKGROUND_LIGHT = "#F5F5F5"
COLOR_BACKGROUND_MEDIUM = "#EEEEEE"
COLOR_BACKGROUND_DARK = "#E0E0E0"
COLOR_BACKGROUND_DIALOG = "#FFFFFF"
COLOR_TEXT_PRIMARY = "#212121"
COLOR_TEXT_SECONDARY = "#757575"
COLOR_TEXT_ON_ACCENT = "#FFFFFF"
COLOR_ACCENT_PRIMARY = "#1976D2" # Primary definition
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
# --- NEW PYTHON SIMULATION HIGHLIGHT COLORS ---
COLOR_PY_SIM_STATE_ACTIVE = QColor("#4CAF50")  # Green for active state
COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH = 2.5

# --- NEW: Dark Theme Code Editor Colors ---
COLOR_EDITOR_DARK_BACKGROUND = QColor("#263238") # The one used in stylesheet
COLOR_EDITOR_DARK_LINE_NUM_BG = QColor("#37474F") # Slightly lighter than editor bg
COLOR_EDITOR_DARK_LINE_NUM_FG = QColor("#7F8B92") # Muted foreground for line numbers
COLOR_EDITOR_DARK_CURRENT_LINE_BG_LN_AREA = QColor("#455A64") # Highlight for line number area
COLOR_EDITOR_DARK_CURRENT_LINE_FG_LN_AREA = QColor("#CFD8DC") # Bright foreground for current line number
COLOR_EDITOR_DARK_CURRENT_LINE_BG_EDITOR = QColor("#31414A") # Subtle highlight for editor area line


APP_FONT_FAMILY = "Segoe UI, Arial, sans-serif"
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
    QToolButton {{
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
    QLabel#StatusLabel, QLabel#MatlabStatusLabel, QLabel#PySimStatusLabel, QLabel#AIChatStatusLabel, QLabel#InternetStatusLabel {{
         padding: 0px 5px;
    }}
    QDialog {{
        background-color: {COLOR_BACKGROUND_DIALOG};
    }}
    QLabel {{
        color: {COLOR_TEXT_PRIMARY};
        background-color: transparent;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox, QTableWidget {{
        background-color: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 3px;
        padding: 5px 6px;
        font-size: 9pt;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus, QTableWidget:focus {{
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
         image: url(./dependencies/icons/arrow_down.png);
         width: 10px; height:10px;
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
    QDialogButtonBox QPushButton[text="OK"], QDialogButtonBox QPushButton[text="Apply & Close"] {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
        border-color: #0D47A1;
    }}
    QDialogButtonBox QPushButton[text="OK"]:hover, QDialogButtonBox QPushButton[text="Apply & Close"]:hover {{
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
    QTextEdit#LogOutputWidget, QTextEdit#PySimActionLog, QTextEdit#AIChatDisplay, QPlainTextEdit#ActionCodeEditor, QTextEdit#IDEOutputConsole, QPlainTextEdit#StandaloneCodeEditor {{
         font-family: Consolas, 'Courier New', monospace;
         background-color: #263238; /* This is COLOR_EDITOR_DARK_BACKGROUND */
         color: #CFD8DC; /* Light grey text for dark background */
         border: 1px solid #37474F;
         border-radius: 3px;
         padding: 5px;
    }}
    QScrollBar:vertical {{
         border: 1px solid {COLOR_BORDER_LIGHT}; background: {COLOR_BACKGROUND_LIGHT};
         width: 14px; margin: 0px;
    }}
    QScrollBar::handle:vertical {{
         background: {COLOR_BORDER_MEDIUM}; min-height: 25px; border-radius: 7px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
         height: 0px; background: transparent;
    }}
    QScrollBar:horizontal {{
         border: 1px solid {COLOR_BORDER_LIGHT}; background: {COLOR_BACKGROUND_LIGHT};
         height: 14px; margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
         background: {COLOR_BORDER_MEDIUM}; min-width: 25px; border-radius: 7px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
         width: 0px; background: transparent;
    }}
    QPushButton#SnippetButton {{
        background-color: {COLOR_ACCENT_SECONDARY}; color: {COLOR_TEXT_ON_ACCENT};
        border: 1px solid #E65100; font-weight: normal;
    }}
    QPushButton#SnippetButton:hover {{
        background-color: #FFA000;
    }}
    QPushButton#ColorButton {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; min-height: 24px; padding: 3px;
    }}
    QPushButton#ColorButton:hover {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QProgressBar {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; border-radius: 4px;
        background-color: {COLOR_BACKGROUND_LIGHT}; text-align: center;
        color: {COLOR_TEXT_PRIMARY}; height: 12px;
    }}
    QProgressBar::chunk {{
        background-color: {COLOR_ACCENT_PRIMARY}; border-radius: 3px;
    }}
    QPushButton#DraggableToolButton {{
        background-color: #E8EAF6; color: {COLOR_TEXT_PRIMARY};
        border: 1px solid #C5CAE9; padding: 8px 10px;
        border-radius: 4px; text-align: left; font-weight: 500;
    }}
    QPushButton#DraggableToolButton:hover {{
        background-color: #B9D9EB; border-color: {COLOR_ACCENT_PRIMARY};
    }}
    QPushButton#DraggableToolButton:pressed {{ background-color: #98BAD6; }}
    #PropertiesDock QLabel {{
        padding: 6px; background-color: {COLOR_BACKGROUND_DIALOG};
        border: 1px solid {COLOR_BORDER_LIGHT}; border-radius: 3px; line-height: 1.4;
    }}
    #PropertiesDock QPushButton {{
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT};
    }}
    #PropertiesDock QPushButton:hover {{ background-color: #1E88E5; }}
    QDockWidget#ToolsDock QToolButton {{
        padding: 6px 8px; text-align: left;
    }}
    QDockWidget#ToolsDock QToolButton:checked {{
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT};
        border: 1px solid #0D47A1;
    }}
    QDockWidget#PySimDock QPushButton {{
        padding: 5px 10px;
    }}
    QDockWidget#PySimDock QPushButton:disabled {{
        background-color: #E0E0E0;
        color: #9E9E9E;
    }}
    QDockWidget#PySimDock QTableWidget {{
        alternate-background-color: {COLOR_BACKGROUND_LIGHT};
        gridline-color: {COLOR_BORDER_LIGHT};
    }}
     QDockWidget#PySimDock QHeaderView::section {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        padding: 4px;
        border: 1px solid {COLOR_BORDER_LIGHT};
        font-weight: bold;
    }}
    QDockWidget#AIChatbotDock QPushButton#AIChatSendButton {{
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT};
    }}
    QDockWidget#AIChatbotDock QPushButton#AIChatSendButton:hover {{
        background-color: #1E88E5;
    }}
    QDockWidget#AIChatbotDock QPushButton#AIChatSendButton:disabled {{
        background-color: #E0E0E0;
        color: #9E9E9E;
        border-color: #BDBDBD;
    }}
    """