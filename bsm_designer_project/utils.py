from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

def get_standard_icon(style_enum, alt_text=""):
    """Get a standard icon from the style enum or return an empty icon on failure."""
    try:
        icon = QApplication.style().standardIcon(style_enum)
        if icon.isNull():  # Some styles might return null icons for enums they don't support
            print(f"Warning: Standard icon for {style_enum} is null. Alt text: {alt_text}")
            return QIcon()
        return icon
    except Exception as e:
        print(f"Warning: Could not get standard icon for {style_enum} (Alt: {alt_text}). Error: {e}")
        return QIcon()