


# bsm_designer_project/utils.py
from PyQt5.QtWidgets import QApplication, QStyle
from PyQt5.QtGui import QIcon
# bsm_designer_project/utils.py
import os
from PyQt5.QtCore import QDir, QFile, QIODevice, QTemporaryFile
import logging # Add if not already there
logger = logging.getLogger(__name__) # Add if not already there

RESOURCES_AVAILABLE = True # Or however you determine this
try:
    import resources_rc # Make sure this is imported
except ImportError:
    RESOURCES_AVAILABLE = False

def get_bundled_file_path(filename: str, resource_prefix: str = "") -> str | None:
    if RESOURCES_AVAILABLE:
        actual_resource_path_prefix = f"/{resource_prefix}" if resource_prefix else ""
        resource_path = f":{actual_resource_path_prefix}/{filename}".replace("//", "/")

        if QFile.exists(resource_path):
            logger.debug(f"Found bundled file '{filename}' in Qt Resources at: {resource_path}")
            # For some external uses (like QDesktopServices.openUrl), a disk path is better
            # Create a temporary copy
            temp_file = QTemporaryFile(QDir.tempPath() + QDir.separator() + "bsm_temp_" + filename)
            if temp_file.open():
                source_file = QFile(resource_path)
                if source_file.open(QIODevice.ReadOnly):
                    temp_file.write(source_file.readAll())
                    source_file.close()
                    temp_file.setAutoRemove(False) # We want it to persist for a bit
                    temp_file.close() # Close to flush
                    logger.debug(f"Copied resource '{resource_path}' to temporary disk path: {temp_file.fileName()}")
                    # Note: Caller might need to manage deletion of this temp file if not auto-removed.
                    # For QDesktopServices, it usually handles it.
                    # For QMediaPlayer, it might need manual cleanup if it holds a lock.
                    # Let's assume QDesktopServices.openUrl handles local file paths well.
                    # A more robust solution for persistent temp files might involve a session-specific temp dir.
                    return temp_file.fileName()
                else:
                    logger.warning(f"Failed to open resource for reading: {resource_path}")
            else:
                logger.warning(f"Failed to create temporary file for {filename}: {temp_file.errorString()}")
        else:
            logger.debug(f"File '{resource_path}' not found in Qt Resources.")
    
    # Filesystem fallback (useful for development or if resources are not compiled)
    import sys # ensure sys is imported
    if getattr(sys, 'frozen', False): # Running as a bundled app (PyInstaller, etc.)
        base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    else: # Running as a script
        base_path = os.path.dirname(os.path.abspath(__file__)) # bsm_designer_project directory

    prefix_to_subdir_map = {
        "examples": "examples",
        "docs": "docs",
        "icons": "dependencies/icons" # Example, adjust if icons are bundled differently
    }
    search_paths = []
    if resource_prefix and resource_prefix in prefix_to_subdir_map:
        # Check relative to bsm_designer_project if base_path is bsm_designer_project itself
        search_paths.append(os.path.join(base_path, prefix_to_subdir_map[resource_prefix], filename))
        # Also check if base_path is the parent of bsm_designer_project
        search_paths.append(os.path.join(os.path.dirname(base_path), "bsm_designer_project", prefix_to_subdir_map[resource_prefix], filename))
    
    # General fallbacks
    search_paths.append(os.path.join(base_path, filename))
    search_paths.append(os.path.join(os.path.dirname(base_path), "bsm_designer_project", filename))


    for path_to_check in search_paths:
        abs_path_to_check = os.path.abspath(path_to_check)
        if os.path.exists(abs_path_to_check):
            logger.debug(f"Found bundled file '{filename}' via filesystem fallback at: {abs_path_to_check}")
            return abs_path_to_check

    logger.warning(f"Bundled file '{filename}' (prefix: '{resource_prefix}') ultimately not found.")
    return None

# ... (other utils like get_standard_icon)

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