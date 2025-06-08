# bsm_designer_project/settings_manager.py
import json
import os
import logging
from PyQt5.QtCore import QObject, QStandardPaths, pyqtSignal, QDir

logger = logging.getLogger(__name__)

class SettingsManager(QObject):
    settingChanged = pyqtSignal(str, object) # key, new_value

    # Define default values for all settings
    DEFAULTS = {
        "view_show_grid": True,
        "view_snap_to_grid": True,
        "view_snap_to_objects": True,
        "view_show_snap_guidelines": True,
        "grid_size": 20, # Example, not yet used in UI for modification
        "general_theme": "Light", # Example, not yet implemented fully

        "resource_monitor_enabled": True,
        "resource_monitor_interval_ms": 2000,

        "autosave_enabled": False, # Example
        "autosave_interval_minutes": 5, # Example
    }

    def __init__(self, app_name="BSMDesigner", parent=None):
        super().__init__(parent)
        self.app_name = app_name
        self._settings = {}
        self.settings_file_path = self._get_settings_file_path()
        self.load_settings()

    def _get_settings_file_path(self):
        path = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
        if not path: # Fallback if AppConfigLocation is not specific enough
            path = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
            if self.app_name and path:
                app_dir = QDir(path)
                if not app_dir.exists(self.app_name):
                    if not app_dir.mkpath(self.app_name):
                        logger.error(f"Could not create settings directory: {os.path.join(path, self.app_name)}")
                        # Fallback further if mkpath fails
                        path = os.path.join(os.getcwd(), "." + self.app_name.lower() + "_settings")
                    else:
                        path = os.path.join(path, self.app_name)
                else:
                     path = os.path.join(path, self.app_name)

        if not path: # Further fallback to current working directory (less ideal)
            logger.warning("Could not determine a standard config path. Using current directory for settings.")
            path = os.path.join(os.getcwd(), "." + self.app_name.lower() + "_settings")
            
        if not QDir(path).exists():
            if not QDir().mkpath(path):
                 logger.error(f"CRITICAL: Could not create settings directory at: {path}. Using emergency fallback.")
                 # Emergency fallback to a subfolder in the script's directory (not ideal for installed apps)
                 try:
                     script_dir = os.path.dirname(os.path.abspath(__file__))
                     path = os.path.join(script_dir, "user_settings")
                     if not QDir().mkpath(path):
                         path = os.path.join(os.getcwd(), "user_settings") # Absolute last resort
                         QDir().mkpath(path)
                 except Exception as e_path:
                     logger.error(f"Error creating emergency settings path: {e_path}")
                     path = os.getcwd() # True last resort


        return os.path.join(path, "app_settings.json")

    def load_settings(self):
        self._settings = self.DEFAULTS.copy() # Start with defaults
        if os.path.exists(self.settings_file_path):
            try:
                with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    if isinstance(loaded_settings, dict):
                        # Only update keys that are known in DEFAULTS to avoid loading junk
                        for key in self.DEFAULTS:
                            if key in loaded_settings:
                                self._settings[key] = loaded_settings[key]
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
            # Save defaults if no settings file exists yet
            self.save_settings()

    def _backup_and_reset_to_defaults(self):
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
        self.save_settings() # Save fresh defaults


    def save_settings(self):
        try:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(self.settings_file_path), exist_ok=True)
            with open(self.settings_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=4, ensure_ascii=False)
            logger.debug(f"Settings saved to {self.settings_file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save settings to '{self.settings_file_path}': {e}", exc_info=True)
            return False

    def get(self, key: str, default_override=None):
        """
        Get a setting value.
        If default_override is provided and key is not in settings, it returns default_override.
        Otherwise, it returns the setting value, or its hardcoded DEFAULTS value if not found.
        """
        if key not in self._settings:
            if default_override is not None:
                return default_override
            return self.DEFAULTS.get(key) # Fallback to hardcoded default
        return self._settings.get(key)

    def set(self, key: str, value: object, save_immediately: bool = True):
        """
        Set a setting value.
        Emits settingChanged signal if the value actually changes.
        """
        old_value = self._settings.get(key)
        if old_value != value:
            self._settings[key] = value
            if save_immediately:
                self.save_settings()
            self.settingChanged.emit(key, value)
            logger.info(f"Setting '{key}' changed to: {value}")
        else:
            logger.debug(f"Setting '{key}' set to same value: {value}. No change emitted.")

    def reset_to_defaults(self):
        """Resets all settings to their default values."""
        logger.info("Resetting all settings to defaults.")
        self._settings = self.DEFAULTS.copy()
        self.save_settings()
        # Emit signals for all changed settings
        for key, value in self._settings.items():
            self.settingChanged.emit(key, value)