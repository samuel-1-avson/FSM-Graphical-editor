


import logging
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QTextEdit # For type hint

# Custom Handler to emit logs to a QTextEdit via a signal (thread-safe)
class QtLogSignal(QObject):
    log_received = pyqtSignal(str)

class QTextEditHandler(logging.Handler):
    def __init__(self, text_edit_widget: QTextEdit):
        super().__init__()
        self.widget = text_edit_widget
        self.log_signal_emitter = QtLogSignal()
        self.log_signal_emitter.log_received.connect(self.widget.append) # Ensure widget.append is thread-safe or wrap it

    def emit(self, record):
        try:
            msg = self.format(record) # Use a formatter for consistent output
            # Emit signal to update UI from the main thread
            # self.widget.append(msg) # Direct append if always on main thread
            self.log_signal_emitter.log_received.emit(msg)
        except Exception:
            self.handleError(record)

def setup_global_logging(log_widget: QTextEdit):
    # Basic formatter
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)-5.5s] [%(name)-15.15s] %(message)s',
                                      datefmt='%H:%M:%S')
    # If you want milliseconds: '%(asctime)s.%(msecs)03d ...' but ensure datefmt doesn't conflict.
    # The default asctime format from basicConfig might be good enough if milliseconds aren't critical here.

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO) # Set default level

    # Console Handler (for development)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)

    # UI Log Widget Handler
    ui_handler = QTextEditHandler(log_widget)
    ui_handler.setFormatter(log_formatter) # You can customize the HTML formatting here
    # Example of custom formatting in emit or by subclassing Formatter for HTML:
    # class HtmlFormatter(logging.Formatter):
    #     def format(self, record):
    #         # ... (similar to MainWindow.log_message's HTML generation) ...
    #         # record.levelname, record.name, record.getMessage(), record.asctime
    #         # Use html.escape(record.getMessage())
    #         timestamp = time.strftime('%H:%M:%S', time.localtime(record.created)) # Or use record.asctime
    #         escaped_msg = html.escape(record.getMessage())
    #         # Basic color coding for level
    #         color = "black"
    #         if record.levelno == logging.ERROR: color = "red"
    #         elif record.levelno == logging.WARNING: color = "orange"
    #         elif record.levelno == logging.DEBUG: color = "grey"
    #         return f"<span style='color:grey;'>[{timestamp}]</span> <b style='color:{color};'>{record.levelname}:</b> [{record.name}] {escaped_msg}<br>"
    # ui_handler.setFormatter(HtmlFormatter())
    # For now, keeping it simple. `log_message`'s HTML formatting can be adapted into a custom Formatter.
    root_logger.addHandler(ui_handler)

    # Optional File Handler
    # file_handler = logging.FileHandler("bsm_designer.log", mode='a')
    # file_handler.setFormatter(log_formatter)
    # root_logger.addHandler(file_handler)

    logging.info("Logging initialized.")
    # Specific logger for fsm_simulator if it needs different handling (already has basicConfig)
    # If fsm_simulator's basicConfig is removed, it will inherit from root.
    # logging.getLogger('fsm_simulator').setLevel(logging.DEBUG) # Example