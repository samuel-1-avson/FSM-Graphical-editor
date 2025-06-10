# bsm_designer_project/ide_manager.py
import os
import io
import contextlib
import html
import logging
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QToolBar, QComboBox, QLabel,
    QTextEdit, QFileDialog, QMessageBox, QInputDialog, QStyle,
    QHBoxLayout
)
from PyQt5.QtCore import QObject, pyqtSlot, QSize, QTime, QDir, Qt, pyqtSignal 
from PyQt5.QtGui import QIcon, QColor

from .code_editor import CodeEditor
from .utils import get_standard_icon
from .config import ( 
    COLOR_BORDER_LIGHT, COLOR_TEXT_SECONDARY, APP_FONT_SIZE_SMALL, 
    COLOR_ACCENT_ERROR, COLOR_BORDER_DARK
)
# ... (rest of file is unchanged)

logger = logging.getLogger(__name__)

class IDEManager(QObject):
    ide_dirty_state_changed = pyqtSignal(bool)    
    ide_file_path_changed = pyqtSignal(str)      
    ide_language_combo_changed = pyqtSignal(str) 


    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

        self.ide_dock: QDockWidget | None = None
        self.ide_code_editor: CodeEditor | None = None
        self.ide_language_combo: QComboBox | None = None
        self.ide_output_console: QTextEdit | None = None

        self.current_ide_file_path: str | None = None
        self._ide_editor_is_dirty = False 

        self._setup_ide_dock_widget_content()
        self._connect_ide_actions()
        if self.ide_language_combo: # Ensure combo exists before accessing currentText
            self.on_ide_language_changed(self.ide_language_combo.currentText())

    @property
    def ide_editor_is_dirty(self):
        return self._ide_editor_is_dirty

    @ide_editor_is_dirty.setter
    def ide_editor_is_dirty(self, value: bool):
        if self._ide_editor_is_dirty != value:
            self._ide_editor_is_dirty = value
            self.ide_dirty_state_changed.emit(value) 

    def _setup_ide_dock_widget_content(self):
        self.ide_dock = self.mw.ide_dock 

        ide_main_widget = QWidget()
        ide_main_layout = QVBoxLayout(ide_main_widget)
        ide_main_layout.setContentsMargins(0,0,0,0) 
        ide_main_layout.setSpacing(0) 

        ide_toolbar = QToolBar("IDE Tools")
        ide_toolbar.setIconSize(QSize(18,18)) 
        ide_toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)

        ide_toolbar.addAction(self.mw.ide_new_file_action)
        ide_toolbar.addAction(self.mw.ide_open_file_action)
        ide_toolbar.addAction(self.mw.ide_save_file_action)
        ide_toolbar.addAction(self.mw.ide_save_as_file_action)
        ide_toolbar.addSeparator()
        ide_toolbar.addAction(self.mw.ide_run_script_action)
        ide_toolbar.addSeparator()

        self.ide_language_combo = QComboBox()
        self.ide_language_combo.addItems(["Python", "C/C++ (Arduino)", "C/C++ (Generic)", "Text"])
        self.ide_language_combo.setToolTip("Select language for syntax highlighting and context")
        self.ide_language_combo.currentTextChanged.connect(self.on_ide_language_changed)

        lang_label = QLabel(" Lang:") 
        lang_label.setStyleSheet(f"font-size: {APP_FONT_SIZE_SMALL}; padding-left: 3px; padding-right: 2px;")

        ide_toolbar.addWidget(lang_label)
        ide_language_combo_container = QWidget()
        ide_language_combo_layout = QHBoxLayout(ide_language_combo_container)
        ide_language_combo_layout.setContentsMargins(0,0,2,0) 
        ide_language_combo_layout.addWidget(self.ide_language_combo)
        ide_toolbar.addWidget(ide_language_combo_container)
        ide_toolbar.addSeparator()
        ide_toolbar.addAction(self.mw.ide_analyze_action)

        ide_main_layout.addWidget(ide_toolbar)

        self.ide_code_editor = CodeEditor()
        self.ide_code_editor.setObjectName("StandaloneCodeEditor")
        self.ide_code_editor.setPlaceholderText("Create a new file or open an existing script...")
        self.ide_code_editor.textChanged.connect(self.on_ide_text_changed)
        self.ide_code_editor.setStyleSheet(f"QPlainTextEdit#StandaloneCodeEditor {{ border-top: 1px solid {COLOR_BORDER_LIGHT}; border-bottom: 1px solid {COLOR_BORDER_LIGHT}; border-left: none; border-right: none; border-radius: 0px; }}")
        ide_main_layout.addWidget(self.ide_code_editor, 1)

        self.ide_output_console = QTextEdit()
        self.ide_output_console.setObjectName("IDEOutputConsole")
        self.ide_output_console.setReadOnly(True)
        self.ide_output_console.setPlaceholderText("Script output will appear here...")
        self.ide_output_console.setFixedHeight(120) 
        self.ide_output_console.setStyleSheet(f"QTextEdit#IDEOutputConsole {{ border-top: 1px solid {COLOR_BORDER_DARK}; border-bottom: none; border-left: none; border-right: none; border-radius: 0px; }}")

        ide_main_layout.addWidget(self.ide_output_console)

        self.ide_dock.setWidget(ide_main_widget)
        self.update_ide_save_actions_enable_state()

    def _connect_ide_actions(self):
        self.mw.ide_new_file_action.triggered.connect(self.on_ide_new_file)
        self.mw.ide_open_file_action.triggered.connect(self.on_ide_open_file)
        self.mw.ide_save_file_action.triggered.connect(self.on_ide_save_file)
        self.mw.ide_save_as_file_action.triggered.connect(self.on_ide_save_as_file)
        self.mw.ide_run_script_action.triggered.connect(self.on_ide_run_python_script)
        self.mw.ide_analyze_action.triggered.connect(self.on_ide_analyze_with_ai)

    def prompt_ide_save_if_dirty(self) -> bool:
        if not self.ide_editor_is_dirty or not self.ide_code_editor:
            return True

        file_desc = os.path.basename(self.current_ide_file_path) if self.current_ide_file_path else "Untitled Script"
        reply = QMessageBox.question(self.mw, "Save IDE Script?",
                                     f"The script '{file_desc}' in the IDE has unsaved changes. Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save)
        if reply == QMessageBox.Save:
            return self.on_ide_save_file()
        elif reply == QMessageBox.Cancel:
            return False
        return True

    @pyqtSlot()
    def on_ide_new_file(self):
        if not self.prompt_ide_save_if_dirty():
            return
        if self.ide_code_editor:
            self.ide_code_editor.clear()
            self.ide_code_editor.setPlaceholderText("Create a new file or open an existing script...")
        if self.ide_output_console:
            self.ide_output_console.clear()
            self.ide_output_console.setPlaceholderText("Script output will appear here...")

        old_path = self.current_ide_file_path
        self.current_ide_file_path = None
        if old_path is not None: 
            self.ide_file_path_changed.emit("") # Emit empty string for None

        self.ide_editor_is_dirty = False 
        logger.info("IDE: New script created.")

    @pyqtSlot()
    def on_ide_open_file(self):
        if not self.prompt_ide_save_if_dirty():
            return

        start_dir = os.path.dirname(self.current_ide_file_path) if self.current_ide_file_path else QDir.homePath()

        file_path, _ = QFileDialog.getOpenFileName(self.mw, "Open Script File", start_dir,
                                                   "Python Files (*.py);;C/C++ Files (*.c *.cpp *.h *.ino);;Text Files (*.txt);;All Files (*)")
        if file_path and self.ide_code_editor:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.ide_code_editor.setPlainText(f.read())

                if self.current_ide_file_path != file_path:
                    self.current_ide_file_path = file_path
                    self.ide_file_path_changed.emit(self.current_ide_file_path)

                self.ide_editor_is_dirty = False 

                if hasattr(self, 'ide_language_combo') and self.ide_language_combo: 
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext == ".py": self.ide_language_combo.setCurrentText("Python")
                    elif ext in [".ino", ".c", ".cpp", ".h"]: self.ide_language_combo.setCurrentText("C/C++ (Arduino)")
                    else: self.ide_language_combo.setCurrentText("Text")
                
                if self.ide_output_console: self.ide_output_console.clear()
                logger.info("IDE: Opened script: %s", file_path)

            except Exception as e:
                QMessageBox.critical(self.mw, "Error Opening Script", f"Could not load script from {file_path}:\n{e}")
                logger.error("IDE: Failed to open script %s: %s", file_path, e)

    def _save_ide_to_path(self, file_path) -> bool:
        if not self.ide_code_editor: return False
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.ide_code_editor.toPlainText())

            if self.current_ide_file_path != file_path:
                self.current_ide_file_path = file_path
                self.ide_file_path_changed.emit(self.current_ide_file_path)

            self.ide_editor_is_dirty = False 
            logger.info("IDE: Saved script to: %s", file_path)
            return True
        except Exception as e:
            QMessageBox.critical(self.mw, "Error Saving Script", f"Could not save script to {file_path}:\n{e}")
            logger.error("IDE: Failed to save script %s: %s", file_path, e)
            return False

    @pyqtSlot()
    def on_ide_save_file(self) -> bool:
        if not self.current_ide_file_path:
            return self.on_ide_save_as_file()
        if self.ide_editor_is_dirty:
             return self._save_ide_to_path(self.current_ide_file_path)
        return True

    @pyqtSlot()
    def on_ide_save_as_file(self) -> bool:
        default_filename = os.path.basename(self.current_ide_file_path or "untitled_script.py")
        start_dir = os.path.dirname(self.current_ide_file_path) if self.current_ide_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getSaveFileName(self.mw, "Save Script As", os.path.join(start_dir, default_filename),
                                                   "Python Files (*.py);;C/C++ Files (*.c *.cpp *.h *.ino);;Text Files (*.txt);;All Files (*)")
        if file_path:
            return self._save_ide_to_path(file_path)
        return False

    @pyqtSlot()
    def on_ide_text_changed(self):
        if not self.ide_editor_is_dirty:
            self.ide_editor_is_dirty = True 

    @pyqtSlot(str)
    def on_ide_language_changed(self, language_param: str):
        if self.ide_code_editor:
            self.ide_code_editor.set_language(language_param)
        self.ide_language_combo_changed.emit(language_param) 
        logger.info(f"IDE: Language changed to {language_param}.")

    @pyqtSlot()
    def on_ide_run_python_script(self):
        if not self.ide_code_editor or not self.ide_output_console:
            logger.error("IDE: Code editor or output console not available for running script.")
            return

        if self.ide_language_combo and self.ide_language_combo.currentText() != "Python":
            QMessageBox.information(self.mw, "Run Script", "Currently, only Python scripts can be run directly from the IDE.")
            return

        code_to_run = self.ide_code_editor.toPlainText()
        if not code_to_run.strip():
            self.ide_output_console.setHtml("<i>No Python code to run.</i>")
            self.ide_output_console.append(f"<hr style='border-color:{COLOR_BORDER_LIGHT};'><div style='color: {COLOR_TEXT_SECONDARY}; font-size: {APP_FONT_SIZE_SMALL};'><i>Execution finished (no code).</i></div>")
            return

        self.ide_output_console.clear()
        self.ide_output_console.append(f"<div style='color: {COLOR_TEXT_SECONDARY}; font-size: {APP_FONT_SIZE_SMALL};'><i>Running Python script at {QTime.currentTime().toString('hh:mm:ss')}...</i></div><hr style='border-color:{COLOR_BORDER_LIGHT};'>")

        script_globals = {"__name__": "__ide_script__"}
        script_locals = {}

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                exec(code_to_run, script_globals, script_locals)

            std_out_text = stdout_capture.getvalue()
            if std_out_text: self.ide_output_console.append(html.escape(std_out_text))

            err_output = stderr_capture.getvalue()
            if err_output:
                error_color_hex = COLOR_ACCENT_ERROR.name() if isinstance(COLOR_ACCENT_ERROR, QColor) else COLOR_ACCENT_ERROR
                self.ide_output_console.append(f"<pre style='color:{error_color_hex};'>{html.escape(err_output)}</pre>")
            self.ide_output_console.append(f"<hr style='border-color:{COLOR_BORDER_LIGHT};'><div style='color: {COLOR_TEXT_SECONDARY}; font-size: {APP_FONT_SIZE_SMALL};'><i>Execution finished.</i></div>")
        except Exception as e:
            import traceback
            error_color_hex = COLOR_ACCENT_ERROR.name() if isinstance(COLOR_ACCENT_ERROR, QColor) else COLOR_ACCENT_ERROR
            self.ide_output_console.append(f"<pre style='color:{error_color_hex};'><b>Error during execution:</b>\n{html.escape(str(e))}\n--- Traceback ---\n{html.escape(traceback.format_exc())}</pre>")
            self.ide_output_console.append(f"<hr style='border-color:{COLOR_BORDER_LIGHT};'><div style='color: {error_color_hex}; font-size: {APP_FONT_SIZE_SMALL};'><i>Execution failed.</i></div>")
        finally:
            stdout_capture.close()
            stderr_capture.close()
            self.ide_output_console.ensureCursorVisible()

    @pyqtSlot()
    def on_ide_analyze_with_ai(self):
        if not self.ide_code_editor or not self.ide_output_console:
            logger.error("IDE: Code editor or output console not available for AI analysis.")
            return
        if not self.mw.ai_chatbot_manager or not self.mw.ai_chatbot_manager.api_key:
            QMessageBox.warning(self.mw, "AI Assistant Not Ready", "Please configure your Google AI API key in AI Assistant Settings (Gemini) to use this feature.")
            return
        if not self.mw._internet_connected: # Access MainWindow's internet status
            QMessageBox.warning(self.mw, "AI Assistant Offline", "Internet connection is required for AI features.")
            return

        code_to_analyze = self.ide_code_editor.toPlainText()
        if not code_to_analyze.strip():
            self.ide_output_console.setHtml("<i>No code to analyze.</i>")
            return

        selected_language = self.ide_language_combo.currentText() if self.ide_language_combo else "Text"
        language_context = ""
        if "Arduino" in selected_language: language_context = "for Arduino"
        elif "C/C++" in selected_language: language_context = "for generic C/C++"
        elif "Python" in selected_language: language_context = "for Python"

        prompt = f"Please review the following {selected_language} code snippet {language_context}. Check for syntax errors, common programming mistakes, potential bugs, or suggest improvements. Provide feedback and, if there are issues, offer a corrected version or explain the problem:\n\n```\n{code_to_analyze}\n```"

        self.ide_output_console.append(f"<div style='color: {COLOR_TEXT_SECONDARY}; font-size: {APP_FONT_SIZE_SMALL};'><i>Sending code to AI for analysis ({selected_language})... (Response will appear in main AI Chat window)</i></div><hr style='border-color:{COLOR_BORDER_LIGHT};'>")

        if self.mw.ai_chat_ui_manager:
            self.mw.ai_chat_ui_manager._append_to_chat_display("IDE", f"Requesting AI analysis for the current script ({selected_language}).")
        self.mw.ai_chatbot_manager.send_message(prompt)

    def update_ide_save_actions_enable_state(self):
        """Called by MainWindow when its own state or relevant IDE state changes."""
        can_save = self.ide_editor_is_dirty
        can_save_as = self.ide_code_editor is not None and bool(self.ide_code_editor.toPlainText())
        
        if hasattr(self.mw, 'ide_save_file_action'): 
            self.mw.ide_save_file_action.setEnabled(can_save)
        if hasattr(self.mw, 'ide_save_as_file_action'):
             self.mw.ide_save_as_file_action.setEnabled(can_save_as)