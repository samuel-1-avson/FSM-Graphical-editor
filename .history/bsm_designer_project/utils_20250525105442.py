from PyQt5.QtWidgets import QStyle, QApplication
from PyQt5.QtGui import QIcon

def get_standard_icon(icon_type: QStyle.StandardPixmap, fallback_name: str = "", style=None) -> QIcon:
    """
    Get a standard icon from the system style, with fallback handling.
    
    Args:
        icon_type: QStyle.StandardPixmap enum value
        fallback_name: Optional name to use for fallback icon/tooltip
        style: Optional QStyle instance to get the icon from (uses app style if None)
        
    Returns:
        QIcon: The requested icon or a fallback if not available
    """
    if not style:
        style = QApplication.style()
    
    try:
        # First try to get the standard icon
        icon = style.standardIcon(icon_type)
        if not icon.isNull():
            return icon
            
        # If standard icon is null, try to get from theme
        if fallback_name:
            theme_icon = QIcon.fromTheme(fallback_name.lower())
            if not theme_icon.isNull():
                return theme_icon
                
    except Exception as e:
        print(f"Warning: Error getting icon {fallback_name}: {e}")
    
    # Ultimate fallback - empty icon
    return QIcon()