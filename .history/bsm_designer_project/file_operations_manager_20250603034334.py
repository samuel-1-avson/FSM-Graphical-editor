# bsm_designer_project/file_operations_manager.py

import os
import json
import logging
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QDir, QFile, QIODevice, QSaveFile, QUrl, QObject, pyqtSlot
from PyQt5.QtGui import QDesktopServices

from config import FILE_FILTER, FILE_EXTENSION
try:
    from .utils import get_bundled_file_path # Try relative first
except ImportError:
    from utils import get_bundled_file_path # Fallback to direct

from graphics_items import GraphicsStateItem # Needed for _load_from_path to call connect_state_item_signals

logger = logging.getLogger(__name__)

class FileOperationsManager(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window

    @pyqtSlot()
    def _prompt_save_if_dirty(self) -> bool:
        if not self.mw.scene.is_dirty():
            return True
        if self.mw.py_sim_active:
            QMessageBox.warning(self.mw, "Simulation Active", "Please stop the Python simulation before saving or opening a new file.")
            return False

        file_desc = os.path.basename(self.mw.current_file_path) if self.mw.current_file_path else "Untitled Diagram"
        reply = QMessageBox.question(self.mw, "Save Diagram Changes?",
                                     f"The diagram '{file_desc}' has unsaved changes. Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save)
        if reply == QMessageBox.Save:
            return self.on_save_file()
        elif reply == QMessageBox.Cancel:
            return False
        return True

    @pyqtSlot(bool)
    def on_new_file(self, silent=False):
        if not silent:
            if not self._prompt_save_if_dirty():
                return False
            # MainWindow's orchestrator calls IDE dirty check

        if hasattr(self.mw, 'py_sim_ui_manager') and self.mw.py_sim_ui_manager:
            self.mw.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        self.mw.scene.clear()
        self.mw.scene.setSceneRect(0,0,6000,4500)
        self.mw.current_file_path = None
        if self.mw.matlab_op_manager: self.mw.matlab_op_manager.last_generated_model_path = None
        self.mw.undo_stack.clear()
        self.mw.scene.set_dirty(False)
        if hasattr(self.mw, 'update_window_title'): self.mw.update_window_title()
        if hasattr(self.mw, '_update_undo_redo_actions_enable_state'): self.mw._update_undo_redo_actions_enable_state()
        if hasattr(self.mw, '_update_save_actions_enable_state'): self.mw._update_save_actions_enable_state()

        if not silent:
            logger.info("New diagram created.")
            if hasattr(self.mw, 'status_label'): self.mw.status_label.setText("New diagram. Ready.")
        if self.mw.view:
            self.mw.view.resetTransform()
            if self.mw.scene and self.mw.scene.sceneRect():
                self.mw.view.centerOn(self.mw.scene.sceneRect().center())
        if hasattr(self.mw, 'select_mode_action'): self.mw.select_mode_action.trigger()
        if hasattr(self.mw, '_refresh_find_dialog_if_visible'): self.mw._refresh_find_dialog_if_visible()
        if self.mw.scene: self.mw.scene.run_all_validations("NewFile")
        return True

    @pyqtSlot()
    def on_open_file(self):
        if not self._prompt_save_if_dirty():
            return
        # MainWindow's orchestrator calls IDE dirty check

        if hasattr(self.mw, 'py_sim_ui_manager') and self.mw.py_sim_ui_manager:
            self.mw.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        start_dir = os.path.dirname(self.mw.current_file_path) if self.mw.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self.mw, "Open BSM File", start_dir, FILE_FILTER)

        if file_path:
            if self._load_from_path(file_path):
                self.mw.current_file_path = file_path
                if self.mw.matlab_op_manager: self.mw.matlab_op_manager.last_generated_model_path = None
                self.mw.undo_stack.clear()
                self.mw.scene.set_dirty(False)
                if hasattr(self.mw, 'update_window_title'): self.mw.update_window_title()
                if hasattr(self.mw, '_update_undo_redo_actions_enable_state'): self.mw._update_undo_redo_actions_enable_state()
                if hasattr(self.mw, '_update_save_actions_enable_state'): self.mw._update_save_actions_enable_state()
                logger.info("Opened file: %s", file_path)
                if hasattr(self.mw, 'status_label'): self.mw.status_label.setText(f"Opened: {os.path.basename(file_path)}")
                bounds = self.mw.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    if self.mw.view : self.mw.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                elif self.mw.view:
                    self.mw.view.resetTransform()
                    if self.mw.scene and self.mw.scene.sceneRect(): self.mw.view.centerOn(self.mw.scene.sceneRect().center())
                if hasattr(self.mw, '_refresh_find_dialog_if_visible'): self.mw._refresh_find_dialog_if_visible()
            else:
                QMessageBox.critical(self.mw, "Error Opening File", f"Could not load the diagram from:\n{file_path}")
                logger.error("Failed to open file: %s", file_path)

    def _load_from_path(self, file_path):
        try:
            if file_path.startswith(":/"):
                qfile = QFile(file_path)
                if not qfile.open(QIODevice.ReadOnly | QIODevice.Text):
                    logger.error("Failed to open resource file %s: %s", file_path, qfile.errorString())
                    return False
                file_content_bytes = qfile.readAll()
                qfile.close()
                file_content_str = file_content_bytes.data().decode('utf-8')
                data = json.loads(file_content_str)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data:
                logger.error("Invalid BSM file format: %s. Missing required keys.", file_path)
                return False

            self.mw.scene.clear()
            self.mw.scene.load_diagram_data(data)

            for item in self.mw.scene.items():
                if isinstance(item, GraphicsStateItem):
                    if hasattr(self.mw, 'connect_state_item_signals'): self.mw.connect_state_item_signals(item)

            return True
        except json.JSONDecodeError as e:
            logger.error("JSONDecodeError loading %s: %s", file_path, e)
            return False
        except Exception as e:
            logger.error("Unexpected error loading %s: %s", file_path, e, exc_info=True)
            return False

    @pyqtSlot()
    def on_save_file(self) -> bool:
        if not self.mw.current_file_path:
            return self.on_save_file_as()
        if self.mw.scene.is_dirty():
             return self._save_to_path(self.mw.current_file_path)
        return True

    @pyqtSlot()
    def on_save_file_as(self) -> bool:
        default_filename = os.path.basename(self.mw.current_file_path or "untitled" + FILE_EXTENSION)
        start_dir = os.path.dirname(self.mw.current_file_path) if self.mw.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getSaveFileName(self.mw, "Save BSM File As",
                                                   os.path.join(start_dir, default_filename),
                                                   FILE_FILTER)
        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION
            if self._save_to_path(file_path):
                self.mw.current_file_path = file_path
                return True
        return False

    def _save_to_path(self, file_path) -> bool:
        if self.mw.py_sim_active:
            QMessageBox.warning(self.mw, "Simulation Active", "Please stop the Python simulation before saving.")
            return False

        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            error_str = save_file.errorString()
            logger.error("Failed to open QSaveFile for %s: %s", file_path, error_str)
            QMessageBox.critical(self.mw, "Save Error", f"Could not open file for saving:\n{error_str}")
            return False
        try:
            diagram_data = self.mw.scene.get_diagram_data()
            json_data_str = json.dumps(diagram_data, indent=4, ensure_ascii=False)
            bytes_written = save_file.write(json_data_str.encode('utf-8'))
            if bytes_written == -1:
                 error_str = save_file.errorString(); logger.error("Error writing to QSaveFile %s: %s", file_path, error_str)
                 QMessageBox.critical(self.mw, "Save Error", f"Could not write data to file:\n{error_str}"); save_file.cancelWriting(); return False
            if not save_file.commit():
                error_str = save_file.errorString(); logger.error("Failed to commit QSaveFile for %s: %s", file_path, error_str)
                QMessageBox.critical(self.mw, "Save Error", f"Could not finalize saving file:\n{error_str}"); return False
            logger.info("Successfully saved diagram to: %s", file_path)
            if hasattr(self.mw, 'status_label'): self.mw.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            self.mw.scene.set_dirty(False)
            if hasattr(self.mw, 'update_window_title'): self.mw.update_window_title()
            if hasattr(self.mw, '_update_save_actions_enable_state'): self.mw._update_save_actions_enable_state()
            return True
        except Exception as e:
            logger.error("Unexpected error during save to %s: %s", file_path, e, exc_info=True)
            QMessageBox.critical(self.mw, "Save Error", f"An unexpected error occurred during saving:\n{e}"); save_file.cancelWriting(); return False

    @pyqtSlot(str)
    def _open_example_file(self, filename: str):
        if not self._prompt_save_if_dirty(): return
        if hasattr(self.mw, 'py_sim_ui_manager') and self.mw.py_sim_ui_manager:
            self.mw.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        example_path = get_bundled_file_path(filename, resource_prefix="examples")
        if example_path:
            if self._load_from_path(example_path):
                self.mw.current_file_path = f":/examples/{filename}" if example_path.startswith(QDir.tempPath()) and QFile.exists(f":/examples/{filename}") else example_path
                if self.mw.matlab_op_manager: self.mw.matlab_op_manager.last_generated_model_path = None
                self.mw.undo_stack.clear(); self.mw.scene.set_dirty(False); self.mw.setWindowModified(False)
                if hasattr(self.mw, 'update_window_title'): self.mw.update_window_title()
                if hasattr(self.mw, '_update_undo_redo_actions_enable_state'): self.mw._update_undo_redo_actions_enable_state()
                logger.info("Opened example file: %s (from %s)", filename, example_path)
                if hasattr(self.mw, 'status_label'): self.mw.status_label.setText(f"Opened example: {filename}")
                bounds = self.mw.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    if self.mw.view: self.mw.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                elif self.mw.view:
                    self.mw.view.resetTransform()
                    if self.mw.scene and self.mw.scene.sceneRect(): self.mw.view.centerOn(self.mw.scene.sceneRect().center())
                if hasattr(self.mw, '_refresh_find_dialog_if_visible'): self.mw._refresh_find_dialog_if_visible()
            else:
                QMessageBox.critical(self.mw, "Error Opening Example", f"Could not load the example file:\n{filename}\nPath tried: {example_path}")
                logger.error("Failed to open example file: %s from path: %s", filename, example_path)
        else:
            QMessageBox.warning(self.mw, "Example File Not Found", f"The example file '{filename}' could not be found.")
            logger.warning("Example file '%s' not found.", filename)