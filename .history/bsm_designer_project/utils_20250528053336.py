


# bsm_designer_project/utils.py
from PyQt5.QtWidgets import QApplication, QStyle
from PyQt5.QtGui import QIcon
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
