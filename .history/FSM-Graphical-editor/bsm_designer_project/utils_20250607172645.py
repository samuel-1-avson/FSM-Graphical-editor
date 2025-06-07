# bsm_designer_project/utils.py
import os # Added for _get_bundled_file_path
import sys # Added for _get_bundled_file_path (for sys.modules)
from PyQt5.QtWidgets import QApplication, QStyle
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QFile, QDir, QIODevice, QFileInfo # Added for _get_bundled_file_path

import logging

logger = logging.getLogger(__name__)

def get_standard_icon(style_enum_value, alt_text=""):
    """
    Get a standard icon from the QStyle.StandardPixmap enum value.
    Returns an empty QIcon on failure.
    """
    if not isinstance(style_enum_value, QStyle.StandardPixmap):
        logger.error(
            f"Invalid type for style_enum_value in get_standard_icon. "
            f"Expected QStyle.StandardPixmap, got {type(style_enum_value)} (value: {style_enum_value}). Alt: {alt_text}"
        )
        return QIcon()

    try:
        style = QApplication.style()
        if not style:
            logger.error("QApplication.style() returned None. Cannot get standard icon.")
            return QIcon()
            
        icon = style.standardIcon(style_enum_value)
        if icon.isNull():
            # This can happen if the current system style doesn't provide a specific icon.
            # It's more of a warning/debug message unless an icon is absolutely critical.
            logger.debug(
                f"Standard icon for enum {style_enum_value} is null (Alt: {alt_text}). "
                f"Current style: {style.objectName()}"
            )
            return QIcon() # Return empty icon, let caller decide fallback
        return icon
    except Exception as e:
        logger.error(
            f"Exception in get_standard_icon for enum {style_enum_value} (Alt: {alt_text}): {e}",
            exc_info=True
        )
        return QIcon()

def _get_bundled_file_path(filename: str, resource_prefix: str = "") -> str | None:
    """
    Tries to get a file path from Qt resources first, then falls back to filesystem.
    If from resources, copies to a temporary location and returns that path.
    """
    # This relies on main.py (or an imported module) having imported resources_rc.py
    # We can check via a flag set in MainWindow or assume it's done.
    # For now, let's assume a global way to check if resources are available if needed,
    # or just try and catch.
    
    RESOURCES_AVAILABLE = False # This should ideally be set by the main application instance
    if QApplication.instance() and hasattr(QApplication.instance(), 'RESOURCES_AVAILABLE'):
        RESOURCES_AVAILABLE = QApplication.instance().RESOURCES_AVAILABLE
    elif 'resources_rc' in sys.modules: # Fallback check if resources_rc was imported
        RESOURCES_AVAILABLE = True


    if RESOURCES_AVAILABLE:
        actual_resource_path_prefix = f"/{resource_prefix}" if resource_prefix else ""
        resource_path = f":{actual_resource_path_prefix}/{filename}".replace("//", "/")

        if QFile.exists(resource_path):
            logger.debug(f"Found bundled file '{filename}' in Qt Resources at: {resource_path}")
            
            # Create a unique session temporary directory
            app_temp_root_dir = QDir(QDir.tempPath())
            app_temp_session_dir_name = f"BSMDesigner_Temp_{QApplication.applicationPid()}"
            if not app_temp_root_dir.exists(app_temp_session_dir_name):
                app_temp_root_dir.mkpath(app_temp_session_dir_name)

            session_temp_dir = app_temp_root_dir.filePath(app_temp_session_dir_name)
            
            temp_disk_path = QDir(session_temp_dir).filePath(filename)

            # Ensure the target directory for the temp file exists
            temp_file_info = QFileInfo(temp_disk_path)
            QDir().mkpath(temp_file_info.absolutePath())

            # If file already exists in temp (e.g. from previous run not cleaned up, or multiple calls), remove it
            if QFile.exists(temp_disk_path):
                QFile.remove(temp_disk_path)

            if QFile.copy(resource_path, temp_disk_path):
                logger.debug(f"Copied resource '{resource_path}' to temporary disk path: {temp_disk_path} for external open.")
                return temp_disk_path
            else:
                source_file_for_error = QFile(resource_path) # Re-open to check error
                source_file_for_error.open(QIODevice.ReadOnly)
                logger.warning(f"Failed to copy resource '{resource_path}' to '{temp_disk_path}'. Error: {source_file_for_error.errorString()}")
                source_file_for_error.close()
        else:
            logger.debug(f"File '{resource_path}' not found in Qt Resources.")
    else:
        logger.debug("Qt Resources not marked as available for _get_bundled_file_path.")


    # Filesystem fallback
    # import sys # Moved import here as it's only for this fallback
    if getattr(sys, 'frozen', False): # PyInstaller
        base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    else: # Running as script
        base_path = os.path.dirname(os.path.abspath(__file__)) # bsm_designer_project directory

    # Define a mapping from resource_prefix to actual subdirectory names
    prefix_to_subdir_map = {
        "examples": "examples",
        "docs": "docs",
        "icons": "dependencies/icons" 
        # Add more mappings if needed
    }
    
    search_paths = []
    if resource_prefix and resource_prefix in prefix_to_subdir_map:
        search_paths.append(os.path.join(base_path, prefix_to_subdir_map[resource_prefix], filename))
    
    # Always check relative to base_path as a final fallback
    search_paths.append(os.path.join(base_path, filename))


    for path_to_check in search_paths:
        if os.path.exists(path_to_check):
            logger.debug(f"Found bundled file '{filename}' via filesystem fallback at: {path_to_check}")
            return path_to_check
            
    logger.warning(f"Bundled file '{filename}' (prefix: '{resource_prefix}') ultimately not found.")
    return None