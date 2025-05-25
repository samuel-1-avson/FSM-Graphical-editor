from PyQt5.QtWidgets import QStyle, QApplication
from PyQt5.QtGui import QIcon

def get_standard_icon(style_enum, alt_text=""): # Removed 'style_obj' argument
    """Get a standard icon from the style enum or return an empty icon on failure."""
    try:
        # Always use QApplication.style() for consistency
        icon = QApplication.style().standardIcon(style_enum)
        if icon.isNull():
            # This warning is fine if some icons are truly not available in the current theme
            # logger.warning(f"Standard icon for {style_enum} is null (Alt: {alt_text}). Current style: {QApplication.style().objectName()}")
            return QIcon()
        return icon
    except Exception as e:
        # Consider using logging here if you have it set up globally
        print(f"Warning: Could not get standard icon for {style_enum} (Alt: {alt_text}). Error: {e}")
        return QIcon()