# bsm_designer_project/logging_setup.py

# FILE: bsm_designer_project/logging_setup.py

import logging
import html
import time
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtGui import QColor, QPalette # <--- ADDED QPalette HERE
from .config import (
    COLOR_ACCENT_ERROR, COLOR_ACCENT_WARNING, COLOR_TEXT_SECONDARY,
    COLOR_TEXT_EDITOR_DARK_PRIMARY, COLOR_ACCENT_SUCCESS, COLOR_BACKGROUND_EDITOR_DARK,
    COLOR_TEXT_EDITOR_DARK_SECONDARY
)

class QtLogSignal(QObject):
    log_received = pyqtSignal(str)

class HtmlFormatter(logging.Formatter):
    def __init__(self):
        super().__init__()
        self.level_colors = {
            logging.DEBUG: COLOR_TEXT_EDITOR_DARK_SECONDARY, # Use dynamic color string
            logging.INFO: COLOR_TEXT_EDITOR_DARK_PRIMARY,    # Use dynamic color string
            logging.WARNING: COLOR_ACCENT_WARNING,           # Use dynamic color string
            logging.ERROR: COLOR_ACCENT_ERROR,               # Use dynamic color string
            logging.CRITICAL: QColor(COLOR_ACCENT_ERROR).darker(120).name(), # Darker error
        }

    def format(self, record):
        timestamp = time.strftime('%H:%M:%S', time.localtime(record.created))
        plain_message = record.getMessage()
        escaped_msg = html.escape(plain_message)

        level_color_str = self.level_colors.get(record.levelno, COLOR_TEXT_EDITOR_DARK_PRIMARY)
        level_name_html = f"<b style='color:{level_color_str};'>{html.escape(record.levelname)}</b>"
        
        # Use a consistent secondary text color for logger name
        logger_name_color_str = COLOR_TEXT_EDITOR_DARK_SECONDARY 
        logger_name_html = f"<span style='color:{logger_name_color_str}; font-style:italic;'>[{html.escape(record.name)}]</span>"

        message_html = f"<span style='color:{level_color_str};'>{escaped_msg}</span>"

        log_entry_html = (
            f"<div style='line-height: 1.3; margin-bottom: 2px; font-family: Consolas, \"Courier New\", monospace; font-size: 9pt;'>"
            f"<span style='color:{COLOR_TEXT_EDITOR_DARK_SECONDARY}; font-size:7pt;'>[{timestamp}]</span> " # Darker timestamp
            f"{level_name_html} "
            f"{logger_name_html} "
            f"{message_html}"
            f"</div>"
        )
        return log_entry_html


class QTextEditHandler(logging.Handler):
    def __init__(self, text_edit_widget: QTextEdit):
        super().__init__()
        self.widget = text_edit_widget
        self.log_signal_emitter = QtLogSignal()
        self.log_signal_emitter.log_received.connect(self.widget.append)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_signal_emitter.log_received.emit(msg)
        except Exception:
            self.handleError(record)

def setup_global_logging(log_widget: QTextEdit):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG) 

    for handler in root_logger.handlers[:]: 
        root_logger.removeHandler(handler)
        handler.close()

    console_formatter = logging.Formatter('%(asctime)s.%(msecs)03d [%(levelname)-7s] [%(name)-25.25s] %(message)s',
                                          datefmt='%H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.DEBUG) 
    root_logger.addHandler(console_handler)

    ui_handler = QTextEditHandler(log_widget)
    ui_handler.setFormatter(HtmlFormatter())
    ui_handler.setLevel(logging.INFO) 
    root_logger.addHandler(ui_handler)

    # Set background color of the log_widget to match editor dark theme
    palette = log_widget.palette()
    palette.setColor(QPalette.Base, QColor(COLOR_BACKGROUND_EDITOR_DARK))
    log_widget.setPalette(palette)


    logging.info("Logging initialized (UI: HTML, Console: Plain).")