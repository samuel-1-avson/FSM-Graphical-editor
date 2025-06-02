import logging
import html 
import time 
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QTextEdit
from config import (
    COLOR_ACCENT_ERROR, COLOR_ACCENT_WARNING, COLOR_TEXT_SECONDARY, 
    COLOR_TEXT_EDITOR_DARK_PRIMARY, COLOR_ACCENT_SUCCESS
) 
from PyQt5.QtGui import QColor

class QtLogSignal(QObject):
    log_received = pyqtSignal(str)

class HtmlFormatter(logging.Formatter):
    # ... (implementation as provided previously) ...
    def __init__(self):
        super().__init__()
        self.level_colors = {
            logging.DEBUG: QColor(COLOR_TEXT_SECONDARY).name(),
            logging.INFO: QColor(COLOR_TEXT_EDITOR_DARK_PRIMARY).name(),
            logging.WARNING: QColor(COLOR_ACCENT_WARNING).darker(10).name(),
            logging.ERROR: QColor(COLOR_ACCENT_ERROR).name(),
            logging.CRITICAL: QColor(COLOR_ACCENT_ERROR).darker(120).name(),
        }

    def format(self, record):
        timestamp = time.strftime('%H:%M:%S', time.localtime(record.created))
        # Ensure record.getMessage() is correctly retrieving the plain log message
        plain_message = record.getMessage()
        escaped_msg = html.escape(plain_message) # Escape the plain message
        
        level_color = self.level_colors.get(record.levelno, QColor(COLOR_TEXT_EDITOR_DARK_PRIMARY).name())
        level_name_html = f"<b style='color:{level_color};'>{html.escape(record.levelname)}</b>"
        logger_name_html = f"<span style='color:{QColor(COLOR_TEXT_SECONDARY).lighter(110).name()}; font-style:italic;'>[{html.escape(record.name)}]</span>"
        
        # Apply specific styling for the message part if needed, or just use level_color
        message_html = f"<span style='color:{level_color};'>{escaped_msg}</span>"

        log_entry_html = (
            f"<div style='line-height: 1.3; margin-bottom: 2px; font-family: Consolas, \"Courier New\", monospace; font-size: 9pt;'>" # Added font
            f"<span style='color:{QColor(COLOR_TEXT_SECONDARY).darker(110).name()}; font-size:7pt;'>[{timestamp}]</span> "
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
        # QTextEdit.append auto-scrolls. Using appendHtml for rich text.
        self.log_signal_emitter.log_received.connect(self.widget.appendHtml)

    def emit(self, record):
        try:
            msg = self.format(record) 
            self.log_signal_emitter.log_received.emit(msg)
        except Exception:
            self.handleError(record)

def setup_global_logging(log_widget: QTextEdit):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG) # Set root to DEBUG to allow finer control at handler level

    for handler in root_logger.handlers[:]: # Clear any existing handlers
        root_logger.removeHandler(handler)
        handler.close()

    console_formatter = logging.Formatter('%(asctime)s.%(msecs)03d [%(levelname)-7s] [%(name)-25.25s] %(message)s',
                                          datefmt='%H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.DEBUG) # Console can be verbose
    root_logger.addHandler(console_handler)

    ui_handler = QTextEditHandler(log_widget)
    ui_handler.setFormatter(HtmlFormatter())
    ui_handler.setLevel(logging.INFO) # UI log level (e.g., INFO and above)
    root_logger.addHandler(ui_handler)

    logging.info("Logging initialized (UI: HTML, Console: Plain).")