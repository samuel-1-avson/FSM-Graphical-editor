# bsm_designer_project/snippet_manager.py
import os
import json
import logging
from PyQt5.QtCore import QStandardPaths, QDir

logger = logging.getLogger(__name__)

DEFAULT_SNIPPET_FILENAME = "custom_code_snippets.json"

class CustomSnippetManager:
    def __init__(self, app_name="BSMDesigner"):
        self.app_name = app_name
        self.custom_snippets: dict = {}  # Structure: {lang: {category: {name: code}}}
        
        config_path = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
        if not config_path: # Fallback if AppConfigLocation is not specific enough
            config_path = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
            if self.app_name and config_path: # Create a subdirectory for the app if using generic AppDataLocation
                app_dir = QDir(config_path)
                if not app_dir.exists(self.app_name):
                    app_dir.mkpath(self.app_name)
                config_path = os.path.join(config_path, self.app_name)

        if not config_path: # Further fallback to current working directory (less ideal)
            logger.warning("Could not determine a standard config path. Using current directory for snippets.")
            config_path = os.getcwd()
            
        if not QDir(config_path).exists():
            QDir().mkpath(config_path)
            
        self.snippet_file_path = os.path.join(config_path, DEFAULT_SNIPPET_FILENAME)
        logger.info(f"Custom snippets will be loaded/saved at: {self.snippet_file_path}")
        
        self.load_custom_snippets()

    def load_custom_snippets(self):
        if not os.path.exists(self.snippet_file_path):
            logger.info(f"Custom snippet file not found at '{self.snippet_file_path}'. Starting with empty custom snippets.")
            self.custom_snippets = {}
            return

        try:
            with open(self.snippet_file_path, 'r', encoding='utf-8') as f:
                self.custom_snippets = json.load(f)
            if not isinstance(self.custom_snippets, dict):
                logger.warning(f"Custom snippet file '{self.snippet_file_path}' does not contain a valid dictionary. Resetting to empty.")
                self.custom_snippets = {}
            logger.info(f"Custom snippets loaded successfully from '{self.snippet_file_path}'.")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from snippet file '{self.snippet_file_path}'. Backing up and resetting.", exc_info=True)
            self._backup_and_reset_snippets()
        except Exception as e:
            logger.error(f"Failed to load custom snippets from '{self.snippet_file_path}': {e}", exc_info=True)
            self.custom_snippets = {} # Default to empty on other errors

    def _backup_and_reset_snippets(self):
        """Backs up the corrupted snippet file and resets to an empty dictionary."""
        try:
            backup_path = self.snippet_file_path + ".bak"
            if os.path.exists(self.snippet_file_path):
                os.replace(self.snippet_file_path, backup_path) # More atomic than copy+delete
                logger.info(f"Backed up corrupted snippet file to '{backup_path}'.")
        except Exception as e_backup:
            logger.error(f"Failed to back up corrupted snippet file: {e_backup}")
        self.custom_snippets = {}


    def save_custom_snippets(self) -> bool:
        try:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(self.snippet_file_path), exist_ok=True)
            with open(self.snippet_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.custom_snippets, f, indent=4, ensure_ascii=False)
            logger.info(f"Custom snippets saved successfully to '{self.snippet_file_path}'.")
            return True
        except Exception as e:
            logger.error(f"Failed to save custom snippets to '{self.snippet_file_path}': {e}", exc_info=True)
            return False

    def get_custom_snippets(self, language: str, category: str) -> dict:
        return self.custom_snippets.get(language, {}).get(category, {})

    def add_custom_snippet(self, language: str, category: str, name: str, code: str) -> bool:
        if not language or not category or not name:
            logger.warning("Cannot add custom snippet: language, category, or name is empty.")
            return False
            
        if language not in self.custom_snippets:
            self.custom_snippets[language] = {}
        if category not in self.custom_snippets[language]:
            self.custom_snippets[language][category] = {}
        
        self.custom_snippets[language][category][name] = code
        logger.info(f"Added/Updated custom snippet: [{language}][{category}] '{name}'")
        return self.save_custom_snippets()

    def edit_custom_snippet(self, language: str, category: str, old_name: str, new_name: str, new_code: str) -> bool:
        if not language or not category or not old_name or not new_name:
            logger.warning("Cannot edit custom snippet: language, category, old_name or new_name is empty.")
            return False

        lang_data = self.custom_snippets.get(language)
        if not lang_data:
            logger.warning(f"Cannot edit snippet: Language '{language}' not found.")
            return False
        cat_data = lang_data.get(category)
        if not cat_data:
            logger.warning(f"Cannot edit snippet: Category '{category}' not found for language '{language}'.")
            return False
        if old_name not in cat_data:
            logger.warning(f"Cannot edit snippet: Snippet '{old_name}' not found in [{language}][{category}].")
            return False

        # If name changed, remove old entry first
        if old_name != new_name:
            if new_name in cat_data:
                logger.warning(f"Cannot rename snippet to '{new_name}': name already exists in [{language}][{category}].")
                return False
            del cat_data[old_name]
        
        cat_data[new_name] = new_code
        logger.info(f"Edited custom snippet: [{language}][{category}] '{old_name}' -> '{new_name}'")
        return self.save_custom_snippets()

    def delete_custom_snippet(self, language: str, category: str, name: str) -> bool:
        if not language or not category or not name:
            logger.warning("Cannot delete custom snippet: language, category, or name is empty.")
            return False

        lang_data = self.custom_snippets.get(language)
        if not lang_data: return False # Language not found
        cat_data = lang_data.get(category)
        if not cat_data: return False # Category not found
        
        if name in cat_data:
            del cat_data[name]
            # Clean up empty categories or languages if desired
            if not cat_data: # If category becomes empty
                del lang_data[category]
            if not lang_data: # If language becomes empty
                del self.custom_snippets[language]
            logger.info(f"Deleted custom snippet: [{language}][{category}] '{name}'")
            return self.save_custom_snippets()
        logger.warning(f"Snippet '{name}' not found for deletion in [{language}][{category}].")
        return False

    def get_all_languages_with_custom_snippets(self) -> list[str]:
        return sorted(list(self.custom_snippets.keys()))

    def get_categories_for_language(self, language: str) -> list[str]:
        if language in self.custom_snippets:
            return sorted(list(self.custom_snippets[language].keys()))
        return []

    def get_snippet_names_for_language_category(self, language: str, category: str) -> list[str]:
        lang_data = self.custom_snippets.get(language, {})
        cat_data = lang_data.get(category, {})
        return sorted(list(cat_data.keys()))

    def get_snippet_code(self, language: str, category: str, name: str) -> str | None:
        return self.custom_snippets.get(language, {}).get(category, {}).get(name)