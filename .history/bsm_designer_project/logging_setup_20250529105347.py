import logging
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QTextEdit # For type hint
import html # For escaping messages for HTML display
import time # For custom timestamp formatting if needed

# Custom Handler to emit logs to a QTextEdit via a signal (thread-safe)
class QtLogSignal(QObject):
    log_received = pyqtSignal(str) # Signal emits pre-formatted HTML string

class QTextEditHandler(logging.Handler):
    def __init__(self, text_edit_widget: QTextEdit):
        super().__init__()
        self.widget = text_edit_widget
        self.log_signal_emitter = QtLogSignal()
        # Connect signal to a lambda that appends HTML to the QTextEdit
        self.log_signal_emitter.log_received.connect(lambda html_msg: self.widget.append(html_msg))

    def emit(self, record):
        try:
            # The formatter (HtmlFormatter) will handle HTML conversion.
            # If not using HtmlFormatter, format here.
            msg = self.format(record) 
            self.log_signal_emitter.log_received.emit(msg)
        except Exception:
            self.handleError(record) # Default error handling (prints to stderr)

class HtmlFormatter(logging.Formatter):
    """Custom formatter to convert log records to HTML."""
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        self.level_colors = {
            logging.DEBUG: "grey",
            logging.INFO: "black",
            logging.WARNING: "darkorange",
            logging.ERROR: "red",
            logging.CRITICAL: "darkred",
        }

    def format(self, record):
        # Basic formatting (timestamp, level, name, message)
        timestamp = time.strftime('%H:%M:%S', time.localtime(record.created))
        level_color = self.level_colors.get(record.levelno, "black")
        
        # Escape the actual log message to prevent HTML injection if message contains HTML-like chars
        escaped_message = html.escape(record.getMessage())
        
        # Bold for level name
        level_name_html = f"<b style='color:{level_color};'>{html.escape(record.levelname)}</b>"
        
        # Module/logger name part
        logger_name_html = f"[{html.escape(record.name)}]"

        # Combine parts into an HTML string
        # Using a div for each log entry for better structure and potential styling
        # Adding a bottom margin to visually separate log entries
        html_log_entry = (
            f"<div style='margin-bottom: 2px; font-family: Consolas, \"Courier New\", monospace; font-size: 9pt;'>"
            f"<span style='color:grey;'>[{timestamp}]</span> "
            f"{level_name_html}: {logger_name_html} "
            f"{escaped_message}"
            f"</div>"
        )
        return html_log_entry


def setup_global_logging(log_widget: QTextEdit):
    # Basic formatter for console (can be different from UI)
    console_formatter = logging.Formatter('%(asctime)s.%(msecs)03d [%(levelname)-7s] [%(name)-20s] %(message)s',
                                          datefmt='%H:%M:%S')

    # Root logger configuration
    root_logger = logging.getLogger()
    # Set level to DEBUG to capture all messages; handlers can filter further.
    root_logger.setLevel(logging.DEBUG) 
    
    # Clear existing handlers from root logger to avoid duplicates if this function is called multiple times
    # (though it should ideally be called once)
    if root_logger.hasHandlers():
        for handler in root_logger.handlers[:]: # Iterate over a copy
            root_logger.removeHandler(handler)
            handler.close() # Close handler before removing


    # Console Handler (for development/debugging)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO) # Console might show INFO and above
    root_logger.addHandler(console_handler)

    # UI Log Widget Handler (using custom HTML formatter)
    ui_handler = QTextEditHandler(log_widget)
    ui_html_formatter = HtmlFormatter() # Use our custom HTML formatter
    ui_handler.setFormatter(ui_html_formatter)
    ui_handler.setLevel(logging.INFO) # UI log widget might also show INFO and above by default
    root_logger.addHandler(ui_handler)

    # Optional File Handler (example, can be uncommented and configured)
    # try:
    #     file_handler = logging.FileHandler("bsm_designer.log", mode='a', encoding='utf-8')
    #     file_handler.setFormatter(console_formatter) # Use same format as console for file
    #     file_handler.setLevel(logging.DEBUG) # Log DEBUG and above to file
    #     root_logger.addHandler(file_handler)
    # except Exception as e:
    #     print(f"Warning: Could not set up file logging: {e}")

    logging.info("Global logging system initialized. Console level: INFO, UI level: INFO.")
    
    # Example: Set specific loggers to different levels if needed
    # logging.getLogger('fsm_simulator').setLevel(logging.DEBUG)
    # logging.getLogger('ai_chatbot').setLevel(logging.DEBUG