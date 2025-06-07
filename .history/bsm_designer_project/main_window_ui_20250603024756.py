# main_window_ui.py
class MainWindowUIManager:
    def __init__(self, main_window):
        self.mw = main_window # main_window is the MainWindow instance

    def create_actions(self):
        self.mw.new_action = QAction(...)
        # ...
        # Connect actions to methods in MainWindow or other managers
        self.mw.new_action.triggered.connect(self.mw.file_operations_manager.on_new_file)

    def create_menus(self): # and so on
        # ...

# main.py
from main_window_ui import MainWindowUIManager
# ...
class MainWindow(QMainWindow):
    def __init__(self):
        # ...
        self.ui_manager = MainWindowUIManager(self)
        self.ui_manager.create_actions()
        self.ui_manager.create_menus()
        # ...