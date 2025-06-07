# bsm_designer_project/file_operations_manager.py
import os
import json
import logging
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QInputDialog
from PyQt5.QtCore import QDir, QFile, QIODevice, QSaveFile, QUrl
from PyQt5.QtGui import QDesktopServices

from config import FILE_EXTENSION, FILE_FILTER, COLOR_ITEM_STATE_DEFAULT_BG, DEFAULT_EXECUTION_ENV
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem # For type hinting and instantiation

# Needs RESOURCES_AVAILABLE and QDir, QFile, QIODevice for _get_bundled_file_path
try:
    import resources_rc # Assuming this is in the same dir or python path
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
        # This method is moved from MainWindow
        if RESOURCES_AVAILABLE:
            actual_resource_path_prefix = f"/{resource_prefix}" if resource_prefix else ""
            resource_path = f":{actual_resource_path_prefix}/{filename}".replace("//", "/")

            if QFile.exists(resource_path):
                # ... (rest of the logic from MainWindow._get_bundled_file_path) ...
                # For brevity, I'll assume the logic is copied correctly here
                # Remember to replace self.log_message with self.mw.log_message
                # and QApplication.applicationPid() with self.mw.applicationPid() if needed,
                # or just QApplication.applicationPid() directly.
                app_temp_root_dir = QDir(QDir.tempPath())
                app_temp_session_dir_name = f"BSMDesigner_Temp_{self.mw.applicationPid() if hasattr(self.mw, 'applicationPid') else os.getpid()}" # Fallback to os.getpid()
                if not app_temp_root_dir.exists(app_temp_session_dir_name):
                    app_temp_root_dir.mkpath(app_temp_session_dir_name)

                session_temp_dir = app_temp_root_dir.filePath(app_temp_session_dir_name)
                temp_disk_path = QDir(session_temp_dir).filePath(filename)
                
                # Ensure directory for temp_disk_path exists
                temp_file_info = QFileInfo(temp_disk_path)
                QDir().mkpath(temp_file_info.absolutePath())

                if QFile.exists(temp_disk_path): # Overwrite if exists
                    QFile.remove(temp_disk_path)

                if QFile.copy(resource_path, temp_disk_path):
                    self.mw.log_message("DEBUG", f"Copied resource '{resource_path}' to temporary disk path: {temp_disk_path} for external open.")
                    return temp_disk_path
                else:
                    source_file_for_error = QFile(resource_path) # Create a new QFile object to check error
                    if not source_file_for_error.open(QIODevice.ReadOnly): # Try to open it
                         self.mw.log_message("WARNING",f"Failed to open resource file '{resource_path}' for reading: {source_file_for_error.errorString()}")
                    else:
                        source_file_for_error.close()
                    self.mw.log_message("WARNING",f"Failed to copy resource '{resource_path}' to '{temp_disk_path}'.") # Removed errorString as it might not be set on QFile.copy
            else:
                self.mw.log_message("DEBUG", f"File '{resource_path}' not found in Qt Resources.")
        else:
            self.mw.log_message("WARNING", "RESOURCES_AVAILABLE is False, cannot load from Qt resources.")


        # Filesystem fallback (copied from MainWindow)
        import sys # Local import if not already available
        if getattr(sys, 'frozen', False): # Running as a bundled app (e.g., PyInstaller)
            base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
        else: # Running as a script
            base_path = os.path.dirname(os.path.abspath(__file__)) # bsm_designer_project dir

        # Define search paths relative to the application structure
        prefix_to_subdir_map = {
            "examples": "examples",  # Assuming examples are in bsm_designer_project/examples
            "docs": "docs",          # Assuming docs are in bsm_designer_project/docs
            "icons": "dependencies/icons" # etc.
        }
        search_paths = []
        if resource_prefix and resource_prefix in prefix_to_subdir_map:
            # Path relative to bsm_designer_project directory
            search_paths.append(os.path.join(base_path, prefix_to_subdir_map[resource_prefix], filename))
        # Also check directly in bsm_designer_project (if no prefix or prefix not in map)
        search_paths.append(os.path.join(base_path, filename))
        # If base_path itself is *inside* bsm_designer_project, and filename is at root of bsm_designer_project
        # e.g. main.py is in bsm_designer_project, and file is bsm_designer_project/somefile.txt
        # then os.path.join(base_path, filename) is correct.

        for path_to_check in search_paths:
            if os.path.exists(path_to_check):
                self.mw.log_message("DEBUG",f"Found bundled file '{filename}' via filesystem fallback at: {path_to_check}")
                return path_to_check
        
        self.mw.log_message("WARNING", f"Bundled file '{filename}' (prefix: '{resource_prefix}') ultimately not found.")
        return None


    def _prompt_save_if_dirty(self) -> bool:
        if not self.mw.scene.is_dirty():
            return True
        if self.mw.py_sim_active: # Access py_sim_active from MainWindow
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
            # Assuming _prompt_ide_save_if_dirty is still in MainWindow or will be moved to an IDE manager
            if hasattr(self.mw, '_prompt_ide_save_if_dirty') and not self.mw._prompt_ide_save_if_dirty():
                 return False

        if hasattr(self.mw, 'py_sim_ui_manager') and self.mw.py_sim_ui_manager:
            self.mw.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        self.mw.scene.clear()
        self.mw.scene.setSceneRect(0,0,6000,4500)
        self.mw.current_file_path = None
        self.mw.last_generated_model_path = None # Assuming this is mainly related to file context
        self.mw.undo_stack.clear()
        self.mw.scene.set_dirty(False) # MainWindow's scene
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
                    self.mw.view.centerOn(self.mw.scene.sceneRect().center())
                self.mw._refresh_find_dialog_if_visible()
            else:
                QMessageBox.critical(self.mw, "Error Opening File", f"Could not load the diagram from:\n{file_path}")
                self.mw.log_message("ERROR", f"Failed to open file: {file_path}")

    def _load_from_path(self, file_path):
        try:
            if file_path.startswith(":/"): # Resource file
                qfile = QFile(file_path)
                if not qfile.open(QIODevice.ReadOnly | QIODevice.Text):
                    self.mw.log_message("ERROR", f"Failed to open resource file {file_path}: {qfile.errorString()}")
                    return False
                file_content_bytes = qfile.readAll()
                qfile.close()
                file_content_str = file_content_bytes.data().decode('utf-8')
                data = json.loads(file_content_str)
            else: # Filesystem file
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data:
                self.mw.log_message("ERROR", f"Invalid BSM file format: {file_path}. Missing required keys.")
                return False

            self.mw.scene.clear() # Clear existing items
            self.mw.scene.load_diagram_data(data) # load_diagram_data is in DiagramScene

            # Connect signals for newly loaded state items
            for item in self.mw.scene.items():
                if isinstance(item, GraphicsStateItem):
                    if hasattr(self.mw, 'connect_state_item_signals'): # Ensure MainWindow has this method
                         self.mw.connect_state_item_signals(item)

            return True
        except json.JSONDecodeError as e:
            self.mw.log_message("ERROR", f"JSONDecodeError loading {file_path}: {e}")
            return False
        except Exception as e:
            self.mw.log_message("ERROR", f"Unexpected error loading {file_path}: {e}")
            logger.error(f"Unexpected error loading {file_path}: {e}", exc_info=True) # Full traceback for dev
            return False

    def on_save_file(self) -> bool:
        if not self.mw.current_file_path:
            return self.on_save_file_as()

        if self.mw.scene.is_dirty(): # Check dirty status from MainWindow's scene
             return self._save_to_path(self.mw.current_file_path)
        return True # No changes, no save needed

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
                self.mw.current_file_path = file_path # Update MainWindow's current_file_path
                return True
        return False

    def _save_to_path(self, file_path) -> bool:
        if self.mw.py_sim_active: # Check MainWindow's py_sim_active
            QMessageBox.warning(self.mw, "Simulation Active", "Please stop the Python simulation before saving.")
            return False

        # Use QSaveFile for safer saving
        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            error_str = save_file.errorString()
            self.mw.log_message("ERROR", f"Failed to open QSaveFile for {file_path}: {error_str}")
            QMessageBox.critical(self.mw, "Save Error", f"Could not open file for saving:\n{error_str}")
            return False
        try:
            diagram_data = self.mw.scene.get_diagram_data() # Get data from MainWindow's scene
            json_data_str = json.dumps(diagram_data, indent=4, ensure_ascii=False)
            bytes_written = save_file.write(json_data_str.encode('utf-8'))

            if bytes_written == -1: # Error during write
                 error_str = save_file.errorString()
                 self.mw.log_message("ERROR", f"Error writing to QSaveFile {file_path}: {error_str}")
                 QMessageBox.critical(self.mw, "Save Error", f"Could not write data to file:\n{error_str}")
                 save_file.cancelWriting() # Important to cancel
                 return False

            if not save_file.commit(): # Finalize write
                error_str = save_file.errorString()
                self.mw.log_message("ERROR", f"Failed to commit QSaveFile for {file_path}: {error_str}")
                QMessageBox.critical(self.mw, "Save Error", f"Could not finalize saving file:\n{error_str}")
                return False

            self.mw.log_message("INFO", f"Successfully saved diagram to: {file_path}")
            if hasattr(self.mw, 'status_label'): self.mw.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            self.mw.scene.set_dirty(False)
            self.mw._update_window_title() # Call MainWindow's method
            self.mw._update_save_actions_enable_state()
            return True
        except Exception as e:
            self.mw.log_message("ERROR", f"Unexpected error during save to {file_path}: {e}")
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
                # Determine if the loaded example was from a temp copy of a resource or direct filesystem
                # This logic might need refinement if temp paths are structured differently
                if example_path.startswith(QDir.tempPath()) and RESOURCES_AVAILABLE:
                    self.mw.current_file_path = f":/examples/{filename}" # Reflect it's a resource example
                else:
                    self.mw.current_file_path = example_path # Direct filesystem path

                self.mw.last_generated_model_path = None
                self.mw.undo_stack.clear()
                self.mw.scene.set_dirty(False)
                self.mw.setWindowModified(False) # Ensure main window knows it's clean
                self.mw._update_window_title()
                self.mw._update_undo_redo_actions_enable_state()
                self.mw.log_message("INFO", f"Opened example file: {filename} (from {example_path})")
                if hasattr(self.mw, 'status_label'): self.mw.status_label.setText(f"Opened example: {filename}")
                bounds = self.mw.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    self.mw.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else:
                    self.mw.view.resetTransform()
                    self.mw.view.centerOn(self.mw.scene.sceneRect().center())
                self.mw._refresh_find_dialog_if_visible()
            else:
                QMessageBox.critical(self.mw, "Error Opening Example", f"Could not load the example file:\n{filename}\nPath tried: {example_path}")
                self.mw.log_message("ERROR", f"Failed to open example file: {filename} from path: {example_path}")
        else:
            QMessageBox.warning(self.mw, "Example File Not Found", f"The example file '{filename}' could not be found.")
            self.mw.log_message("WARNING", f"Example file '{filename}' not found.")