# bsm_designer_project/file_operations_manager.py
import os
import json
import logging
import sys # For _get_bundled_file_path fallback

from PyQt5.QtWidgets import QFileDialog, QMessageBox, QInputDialog
from PyQt5.QtCore import QDir, QFile, QIODevice, QSaveFile, QUrl, QObject, QFileInfo, Qt
from PyQt5.QtGui import QDesktopServices

from config import (
    FILE_EXTENSION, FILE_FILTER, COLOR_ITEM_STATE_DEFAULT_BG,
    DEFAULT_EXECUTION_ENV
)
# Assuming graphics_items.py is in the same directory or on Python path
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem

# Needs RESOURCES_AVAILABLE for _get_bundled_file_path
try:
    import resources_rc
    RESOURCES_AVAILABLE = True
except ImportError:
    RESOURCES_AVAILABLE = False
    print("WARNING (FileOperationsManager): resources_rc.py not found. Bundled files might be missing.")


logger = logging.getLogger(__name__)

class FileOperationsManager(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window # Reference to the MainWindow instance

    def _get_bundled_file_path(self, filename: str, resource_prefix: str = "") -> str | None:
        if RESOURCES_AVAILABLE:
            actual_resource_path_prefix = f"/{resource_prefix}" if resource_prefix else ""
            resource_path = f":{actual_resource_path_prefix}/{filename}".replace("//", "/")

            if QFile.exists(resource_path):
                app_temp_root_dir = QDir(QDir.tempPath())
                # Use applicationName if set, otherwise a generic name + PID
                app_name_for_temp = self.mw.applicationName() if self.mw.applicationName() else "BSMDesigner"
                app_temp_session_dir_name = f"{app_name_for_temp}_Temp_{self.mw.applicationPid() if hasattr(self.mw, 'applicationPid') and self.mw.applicationPid() is not None else os.getpid()}"
                
                if not app_temp_root_dir.exists(app_temp_session_dir_name):
                    if not app_temp_root_dir.mkpath(app_temp_session_dir_name):
                        self.mw.log_message("ERROR", f"Could not create session temp directory: {app_temp_root_dir.filePath(app_temp_session_dir_name)}")
                        # Fall through to filesystem search if temp creation fails
                
                session_temp_dir_path = app_temp_root_dir.filePath(app_temp_session_dir_name)
                if QDir(session_temp_dir_path).exists(): # Check if path creation was successful
                    temp_disk_path = QDir(session_temp_dir_path).filePath(filename)
                    temp_file_info = QFileInfo(temp_disk_path)
                    QDir().mkpath(temp_file_info.absolutePath()) # Ensure specific subdir for file exists

                    if QFile.exists(temp_disk_path): # Overwrite if exists
                        if not QFile.remove(temp_disk_path):
                             self.mw.log_message("WARNING", f"Could not remove existing temp file: {temp_disk_path}")

                    if QFile.copy(resource_path, temp_disk_path):
                        self.mw.log_message("DEBUG", f"Copied resource '{resource_path}' to temporary disk path: {temp_disk_path} for external open.")
                        return temp_disk_path
                    else:
                        source_file_for_error = QFile(resource_path)
                        if not source_file_for_error.open(QIODevice.ReadOnly):
                             self.mw.log_message("WARNING",f"Failed to open resource file '{resource_path}' for reading: {source_file_for_error.errorString()}")
                        else:
                            source_file_for_error.close()
                        self.mw.log_message("WARNING",f"Failed to copy resource '{resource_path}' to '{temp_disk_path}'.")
                else:
                    self.mw.log_message("WARNING", f"Session temp directory '{session_temp_dir_path}' does not exist or was not created.")
            else:
                self.mw.log_message("DEBUG", f"File '{resource_path}' not found in Qt Resources.")
        elif not RESOURCES_AVAILABLE:
             self.mw.log_message("DEBUG", "RESOURCES_AVAILABLE is False, cannot load from Qt resources. Trying filesystem.")


        # Filesystem fallback
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
        else:
            # Assuming this file (file_operations_manager.py) is in bsm_designer_project
            base_path = os.path.dirname(os.path.abspath(__file__))

        prefix_to_subdir_map = { "examples": "examples", "docs": "docs", "icons": "dependencies/icons"}
        search_paths = []
        if resource_prefix and resource_prefix in prefix_to_subdir_map:
            search_paths.append(os.path.join(base_path, prefix_to_subdir_map[resource_prefix], filename))
        search_paths.append(os.path.join(base_path, filename)) # Check in current module's dir
        # Check one level up for "examples", "docs" if this file is in a subdir of project root
        project_root_path = os.path.dirname(base_path)
        if resource_prefix and resource_prefix in prefix_to_subdir_map:
            search_paths.append(os.path.join(project_root_path, prefix_to_subdir_map[resource_prefix], filename))


        for path_to_check in search_paths:
            norm_path_to_check = os.path.normpath(path_to_check)
            if os.path.exists(norm_path_to_check):
                self.mw.log_message("DEBUG",f"Found bundled file '{filename}' via filesystem fallback at: {norm_path_to_check}")
                return norm_path_to_check
        
        self.mw.log_message("WARNING", f"Bundled file '{filename}' (prefix: '{resource_prefix}') ultimately not found in paths: {search_paths}")
        return None

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

    def on_new_file(self, silent=False):
        if not silent:
            if not self._prompt_save_if_dirty(): return False
            if hasattr(self.mw, '_prompt_ide_save_if_dirty') and not self.mw._prompt_ide_save_if_dirty():
                 return False

        if hasattr(self.mw, 'py_sim_ui_manager') and self.mw.py_sim_ui_manager:
            self.mw.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        self.mw.scene.clear()
        self.mw.scene.setSceneRect(0,0,6000,4500)
        self.mw.current_file_path = None
        self.mw.last_generated_model_path = None
        self.mw.undo_stack.clear()
        self.mw.scene.set_dirty(False)
        self.mw._update_window_title()
        self.mw._update_undo_redo_actions_enable_state()
        self.mw._update_save_actions_enable_state()
        if not silent:
            self.mw.log_message("INFO", "New diagram created.")
            if hasattr(self.mw, 'status_label'): self.mw.status_label.setText("New diagram. Ready.")
        if self.mw.view:
            self.mw.view.resetTransform()
            if self.mw.scene and self.mw.scene.sceneRect():
                self.mw.view.centerOn(self.mw.scene.sceneRect().center())
        if hasattr(self.mw, 'select_mode_action'): self.mw.select_mode_action.trigger()
        self.mw._refresh_find_dialog_if_visible()
        if self.mw.scene: self.mw.scene.run_all_validations("NewFile")
        return True

    def on_open_file(self):
        if not self._prompt_save_if_dirty(): return
        if hasattr(self.mw, '_prompt_ide_save_if_dirty') and not self.mw._prompt_ide_save_if_dirty():
            return

        if hasattr(self.mw, 'py_sim_ui_manager') and self.mw.py_sim_ui_manager:
            self.mw.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        start_dir = os.path.dirname(self.mw.current_file_path) if self.mw.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self.mw, "Open BSM File", start_dir, FILE_FILTER)

        if file_path:
            if self._load_from_path(file_path):
                self.mw.current_file_path = file_path
                self.mw.last_generated_model_path = None
                self.mw.undo_stack.clear()
                self.mw.scene.set_dirty(False)
                self.mw._update_window_title()
                self.mw._update_undo_redo_actions_enable_state()
                self.mw._update_save_actions_enable_state()
                self.mw.log_message("INFO", f"Opened file: {file_path}")
                if hasattr(self.mw, 'status_label'): self.mw.status_label.setText(f"Opened: {os.path.basename(file_path)}")
                bounds = self.mw.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    self.mw.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else:
                    self.mw.view.resetTransform()
                    if self.mw.scene.sceneRect(): self.mw.view.centerOn(self.mw.scene.sceneRect().center())
                self.mw._refresh_find_dialog_if_visible()
            else:
                QMessageBox.critical(self.mw, "Error Opening File", f"Could not load the diagram from:\n{file_path}")
                self.mw.log_message("ERROR", f"Failed to open file: {file_path}")

    def _load_from_path(self, file_path):
        try:
            if file_path.startswith(":/"):
                qfile = QFile(file_path)
                if not qfile.open(QIODevice.ReadOnly | QIODevice.Text):
                    self.mw.log_message("ERROR", f"Failed to open resource file {file_path}: {qfile.errorString()}")
                    return False
                file_content_bytes = qfile.readAll()
                qfile.close()
                file_content_str = file_content_bytes.data().decode('utf-8')
                data = json.loads(file_content_str)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data:
                self.mw.log_message("ERROR", f"Invalid BSM file format: {file_path}. Missing required keys.")
                return False

            self.mw.scene.clear()
            self.mw.scene.load_diagram_data(data)

            for item in self.mw.scene.items():
                if isinstance(item, GraphicsStateItem):
                    if hasattr(self.mw, 'connect_state_item_signals'):
                         self.mw.connect_state_item_signals(item)

            return True
        except json.JSONDecodeError as e:
            self.mw.log_message("ERROR", f"JSONDecodeError loading {file_path}: {e}")
            return False
        except Exception as e:
            self.mw.log_message("ERROR", f"Unexpected error loading {file_path}: {type(e).__name__} - {e}")
            logger.error(f"Unexpected error loading {file_path}: {e}", exc_info=True)
            return False

    def on_save_file(self) -> bool:
        if not self.mw.current_file_path:
            return self.on_save_file_as()
        if self.mw.scene.is_dirty():
             return self._save_to_path(self.mw.current_file_path)
        return True

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
            self.mw.log_message("ERROR", f"Failed to open QSaveFile for {file_path}: {error_str}")
            QMessageBox.critical(self.mw, "Save Error", f"Could not open file for saving:\n{error_str}")
            return False
        try:
            diagram_data = self.mw.scene.get_diagram_data()
            json_data_str = json.dumps(diagram_data, indent=4, ensure_ascii=False)
            bytes_written = save_file.write(json_data_str.encode('utf-8'))
            if bytes_written == -1:
                 error_str = save_file.errorString()
                 self.mw.log_message("ERROR", f"Error writing to QSaveFile {file_path}: {error_str}")
                 QMessageBox.critical(self.mw, "Save Error", f"Could not write data to file:\n{error_str}")
                 save_file.cancelWriting()
                 return False
            if not save_file.commit():
                error_str = save_file.errorString()
                self.mw.log_message("ERROR", f"Failed to commit QSaveFile for {file_path}: {error_str}")
                QMessageBox.critical(self.mw, "Save Error", f"Could not finalize saving file:\n{error_str}")
                return False
            self.mw.log_message("INFO", f"Successfully saved diagram to: {file_path}")
            if hasattr(self.mw, 'status_label'): self.mw.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            self.mw.scene.set_dirty(False)
            self.mw._update_window_title()
            self.mw._update_save_actions_enable_state()
            return True
        except Exception as e:
            self.mw.log_message("ERROR", f"Unexpected error during save to {file_path}: {type(e).__name__} - {e}")
            logger.error(f"Unexpected error during save to {file_path}: {e}", exc_info=True)
            QMessageBox.critical(self.mw, "Save Error", f"An unexpected error occurred during saving:\n{e}")
            save_file.cancelWriting()
            return False

    def _open_example_file(self, filename: str):
        if not self._prompt_save_if_dirty():
            return
        if hasattr(self.mw, 'py_sim_ui_manager') and self.mw.py_sim_ui_manager:
            self.mw.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        example_path = self._get_bundled_file_path(filename, resource_prefix="examples")

        if example_path:
            if self._load_from_path(example_path):
                if example_path.startswith(QDir.tempPath().replace('/', os.sep)) and RESOURCES_AVAILABLE: # Normalize path separators for comparison
                    self.mw.current_file_path = f":/examples/{filename}"
                else:
                    self.mw.current_file_path = example_path

                self.mw.last_generated_model_path = None
                self.mw.undo_stack.clear()
                self.mw.scene.set_dirty(False)
                self.mw.setWindowModified(False)
                self.mw._update_window_title()
                self.mw._update_undo_redo_actions_enable_state()
                self.mw.log_message("INFO", f"Opened example file: {filename} (from {example_path})")
                if hasattr(self.mw, 'status_label'): self.mw.status_label.setText(f"Opened example: {filename}")
                bounds = self.mw.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    self.mw.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else:
                    self.mw.view.resetTransform()
                    if self.mw.scene.sceneRect(): self.mw.view.centerOn(self.mw.scene.sceneRect().center())
                self.mw._refresh_find_dialog_if_visible()
            else:
                QMessageBox.critical(self.mw, "Error Opening Example", f"Could not load the example file:\n{filename}\nPath tried: {example_path}")
                self.mw.log_message("ERROR", f"Failed to open example file: {filename} from path: {example_path}")
        else:
            QMessageBox.warning(self.mw, "Example File Not Found", f"The example file '{filename}' could not be found.")
            self.mw.log_message("WARNING", f"Example file '{filename}' not found.")