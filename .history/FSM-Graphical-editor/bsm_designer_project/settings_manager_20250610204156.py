# bsm_designer_project/settings_manager.py

import json
import os
import logging
from PyQt5.QtCore import QObject, QStandardPaths, pyqtSignal, QDir, Qt # Added Qt
from .config import ( # Import new defaults
    DEFAULT_STATE_SHAPE, DEFAULT_STATE_BORDER_STYLE, DEFAULT_STATE_BORDER_WIDTH,
    DEFAULT_TRANSITION_LINE_STYLE, DEFAULT_TRANSITION_LINE_WIDTH, DEFAULT_TRANSITION_ARROWHEAD,
    APP_FONT_FAMILY, APP_FONT_SIZE_STANDARD,
    COLOR_GRID_MINOR_LIGHT, COLOR_GRID_MAJOR_LIGHT, COLOR_SNAP_GUIDELINE
)
# ... (rest of file is unchanged)


logger = logging.getLogger(__name__)

class SettingsManager(QObject):
    settingChanged = pyqtSignal(str, object) # key, new_value

    DEFAULTS = {
        # View settings
        "view_show_grid": True,
        "view_snap_to_grid": True,
        "view_snap_to_objects": True,
        "view_show_snap_guidelines": True,
        "grid_size": 20,

        # Behavior settings
        "resource_monitor_enabled": True,
        "resource_monitor_interval_ms": 2000,
        "autosave_enabled": False,
        "autosave_interval_minutes": 5,

        # Appearance settings (NEW)
        "appearance_theme": "Light", # "Light", "Dark"
        "canvas_grid_minor_color": COLOR_GRID_MINOR_LIGHT,
        "canvas_grid_major_color": COLOR_GRID_MAJOR_LIGHT,
        "canvas_snap_guideline_color": COLOR_SNAP_GUIDELINE.name(), # Store as hex string

        # Default Item Visuals (NEW)
        "state_default_shape": DEFAULT_STATE_SHAPE,
        "state_default_font_family": APP_FONT_FAMILY,
        "state_default_font_size": 10, # points
        "state_default_font_bold": True,
        "state_default_font_italic": False,
        "state_default_border_style_str": "Solid", # "Solid", "Dash", "Dot"
        "state_default_border_width": DEFAULT_STATE_BORDER_WIDTH,

        "transition_default_line_style_str": "Solid",
        "transition_default_line_width": DEFAULT_TRANSITION_LINE_WIDTH,
        "transition_default_arrowhead_style": DEFAULT_TRANSITION_ARROWHEAD,
        "transition_default_font_family": APP_FONT_FAMILY,
        "transition_default_font_size": 8, # points

        "comment_default_font_family": APP_FONT_FAMILY,
        "comment_default_font_size": 9, # points
        "comment_default_font_italic": True,
        
        # Perspective Settings
        "last_used_perspective": "Design Focus",
        "user_perspective_names": [], # List of custom perspective names
        # Individual perspectives like "perspective_MyCustomLayout" are stored dynamically
    }
    
    # Helper to map string style names to Qt.PenStyle enum values
    QT_PEN_STYLES_MAP = {
        "Solid": Qt.SolidLine,
        "Dash": Qt.DashLine,
        "Dot": Qt.DotLine,
        "DashDot": Qt.DashDotLine,
        "DashDotDot": Qt.DashDotDotLine,
        "CustomDash": Qt.CustomDashLine, # Requires pattern
    }
    STRING_TO_QT_PEN_STYLE = {name: enum_val for name, enum_val in QT_PEN_STYLES_MAP.items()}
    QT_PEN_STYLE_TO_STRING = {enum_val: name for name, enum_val in QT_PEN_STYLES_MAP.items()}


    def __init__(self, app_name="BSMDesigner", parent=None):
        super().__init__(parent)
        self.app_name = app_name
        self._settings = {}
        self.settings_file_path = self._get_settings_file_path()
        self.load_settings()

    def _get_settings_file_path(self):
        # ... (content remains the same) ...
        path = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
        if not path: 
            path = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
            if self.app_name and path:
                app_dir = QDir(path)
                if not app_dir.exists(self.app_name):
                    if not app_dir.mkpath(self.app_name):
                        logger.error(f"Could not create settings directory: {os.path.join(path, self.app_name)}")
                        path = os.path.join(os.getcwd(), "." + self.app_name.lower() + "_settings")
                    else:
                        path = os.path.join(path, self.app_name)
                else:
                     path = os.path.join(path, self.app_name)

        if not path: 
            logger.warning("Could not determine a standard config path. Using current directory for settings.")
            path = os.path.join(os.getcwd(), "." + self.app_name.lower() + "_settings")
            
        if not QDir(path).exists():
            if not QDir().mkpath(path):
                 logger.error(f"CRITICAL: Could not create settings directory at: {path}. Using emergency fallback.")
                 try:
                     script_dir = os.path.dirname(os.path.abspath(__file__))
                     path = os.path.join(script_dir, "user_settings")
                     if not QDir().mkpath(path):
                         path = os.path.join(os.getcwd(), "user_settings") 
                         QDir().mkpath(path)
                 except Exception as e_path:
                     logger.error(f"Error creating emergency settings path: {e_path}")
                     path = os.getcwd() 


        return os.path.join(path, "app_settings.json")

    def load_settings(self):
        # ... (content remains mostly the same, ensure new defaults are handled) ...
        self._settings = self.DEFAULTS.copy() 
        if os.path.exists(self.settings_file_path):
            try:
                with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    if isinstance(loaded_settings, dict):
                        for key in self.DEFAULTS: # Iterate known keys
                            if key in loaded_settings:
                                # Type check/conversion for robustness if needed
                                if key.endswith("_color") and isinstance(loaded_settings[key], str):
                                     self._settings[key] = loaded_settings[key] # Assume color hex strings are fine
                                elif key.endswith("_width") and isinstance(loaded_settings[key], (int, float)):
                                     self._settings[key] = float(loaded_settings[key])
                                elif key.endswith("_size") and isinstance(loaded_settings[key], (int, float)):
                                     self._settings[key] = int(loaded_settings[key])
                                elif "_style_str" in key and isinstance(loaded_settings[key], str):
                                     self._settings[key] = loaded_settings[key]
                                elif key == "user_perspective_names" and not isinstance(loaded_settings[key], list):
                                    logger.warning(f"Setting 'user_perspective_names' is not a list. Resetting to default.")
                                    self._settings[key] = self.DEFAULTS[key]
                                elif isinstance(loaded_settings[key], type(self.DEFAULTS[key])):
                                    self._settings[key] = loaded_settings[key]
                                else:
                                    logger.warning(f"Type mismatch for setting '{key}' in file. Expected {type(self.DEFAULTS[key])}, got {type(loaded_settings[key])}. Using default.")
                            # else: logger.debug(f"Setting '{key}' not in file, using default.") # Can be noisy
                        # Load dynamic perspective_XXX settings
                        for key, value in loaded_settings.items():
                            if key.startswith("perspective_") and key not in self.DEFAULTS:
                                self._settings[key] = value

                    else:
                        logger.warning(f"Settings file {self.settings_file_path} does not contain a dictionary. Using defaults.")
                logger.info(f"Settings loaded from {self.settings_file_path}")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from settings file '{self.settings_file_path}': {e}. Using defaults.")
                self._backup_and_reset_to_defaults()
            except Exception as e:
                logger.error(f"Failed to load settings from '{self.settings_file_path}': {e}. Using defaults.", exc_info=True)
                self._settings = self.DEFAULTS.copy()
        else:
            logger.info(f"Settings file not found at '{self.settings_file_path}'. Initializing with defaults.")
            self.save_settings()


    def _backup_and_reset_to_defaults(self):
        # ... (content remains the same) ...
        if os.path.exists(self.settings_file_path):
            try:
                backup_path = self.settings_file_path + f".{QDir.current().currentTime().toString('yyyyMMdd_hhmmss')}.bak"
                if QFile.copy(self.settings_file_path, backup_path):
                    logger.info(f"Backed up corrupted settings file to '{backup_path}'.")
                else:
                    logger.error(f"Failed to create backup of corrupted settings file: {self.settings_file_path}")
                QFile.remove(self.settings_file_path)
            except Exception as e_backup:
                logger.error(f"Failed to back up or remove corrupted settings file: {e_backup}")
        self._settings = self.DEFAULTS.copy()
        self.save_settings() 


    def save_settings(self):
        # ... (content remains the same) ...
        try:
            os.makedirs(os.path.dirname(self.settings_file_path), exist_ok=True)
            with open(self.settings_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=4, ensure_ascii=False)
            logger.debug(f"Settings saved to {self.settings_file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save settings to '{self.settings_file_path}': {e}", exc_info=True)
            return False

    def get(self, key: str, default_override=None):
        # ... (content remains the same) ...
        if key not in self._settings:
            if default_override is not None:
                return default_override
            return self.DEFAULTS.get(key) 
        return self._settings.get(key)

    def set(self, key: str, value: object, save_immediately: bool = True):
        # ... (content remains the same) ...
        old_value = self._settings.get(key)
        if old_value != value:
            self._settings[key] = value
            if save_immediately:
                self.save_settings()
            self.settingChanged.emit(key, value)
            logger.info(f"Setting '{key}' changed to: {value}")
        else:
            logger.debug(f"Setting '{key}' set to same value: {value}. No change emitted.")
            
    def remove_setting(self, key: str, save_immediately: bool = True):
        if key in self._settings:
            del self._settings[key]
            if save_immediately:
                self.save_settings()
            # self.settingChanged.emit(key, None) # Or some other signal for removal
            logger.info(f"Setting '{key}' removed.")
        else:
            logger.debug(f"Setting '{key}' not found, cannot remove.")


    def reset_to_defaults(self):
        # ... (content remains the same) ...
        logger.info("Resetting all settings to defaults.")
        
        # Preserve custom perspectives if they exist, unless a full reset is intended
        # For now, a full reset clears custom perspectives too.
        # A more nuanced reset could be implemented later.
        custom_perspectives_to_remove = [k for k in self._settings.keys() if k.startswith("perspective_")]
        for k_custom in custom_perspectives_to_remove:
            del self._settings[k_custom]
            
        self._settings = self.DEFAULTS.copy()
        self.save_settings()
        for key, value in self._settings.items():
            self.settingChanged.emit(key, value)