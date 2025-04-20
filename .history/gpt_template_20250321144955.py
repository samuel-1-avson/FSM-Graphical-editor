import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QMenuBar, QMenu, QToolBar, QDockWidget,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QLabel, QVBoxLayout,
    QWidget, QGraphicsView, QGraphicsScene, QStatusBar, QAction
)
from PyQt5.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Brain Simulator - PyQt Example")

        # 1. Create Menus, Toolbars, and Actions
        self.create_actions()
        self.create_menus()
        self.create_tool_bar()

        # 2. Create the central widget (for node-based editor)
        self.create_central_widget()

        # 3. Create dock widgets for Properties (right) and Log/Console (bottom)
        self.create_dock_widgets()

        # 4. (Optional) Show a status bar at the bottom
        self.statusBar().showMessage("Ready")

    def create_actions(self):
        """Create actions used in menus and toolbars."""
        # File actions
        self.action_new = QAction("New...", self)
        self.action_open = QAction("Open...", self)
        self.action_save = QAction("Save", self)
        self.action_exit = QAction("Exit", self)

        # Edit actions
        self.action_copy = QAction("Copy", self)
        self.action_paste = QAction("Paste", self)

        # Tools actions
        self.action_options = QAction("Options", self)

        # Help actions
        self.action_about = QAction("About", self)

        # Sample toolbar actions
        self.action_pointer = QAction("Pointer", self)
        self.action_node = QAction("Node", self)
        self.action_link = QAction("Link", self)

    def create_menus(self):
        """Set up the menu bar and add menus."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.action_new)
        file_menu.addAction(self.action_open)
        file_menu.addAction(self.action_save)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

        # Edit menu
        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.action_copy)
        edit_menu.addAction(self.action_paste)

        # Tools menu
        tools_menu = menu_bar.addMenu("&Tools")
        tools_menu.addAction(self.action_options)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.action_about)

    def create_tool_bar(self):
        """Create a main toolbar with sample actions."""
        tool_bar = QToolBar("Main Toolbar", self)
        tool_bar.setAllowedAreas(Qt.TopToolBarArea | Qt.LeftToolBarArea)
        self.addToolBar(Qt.TopToolBarArea, tool_bar)

        # Add actions to toolbar
        tool_bar.addAction(self.action_pointer)
        tool_bar.addAction(self.action_node)
        tool_bar.addAction(self.action_link)

    def create_central_widget(self):
        """Create the main central widget (e.g., a QGraphicsView for nodes)."""
        scene = QGraphicsScene(self)
        scene.setSceneRect(0, 0, 800, 600)

        view = QGraphicsView(scene)
        view.setRenderHints(view.renderHints() | view.renderHints())

        self.setCentralWidget(view)

    def create_dock_widgets(self):
        """Create docks for property panel (right) and console/log panel (bottom)."""

        # Dock: Node Properties (on the right)
        properties_dock = QDockWidget("Node Properties", self)
        properties_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)

        properties_widget = QWidget(properties_dock)
        vbox = QVBoxLayout(properties_widget)

        label = QLabel("Properties Panel", properties_widget)
        vbox.addWidget(label)

        # A simple tree widget to hold some property data
        property_tree = QTreeWidget(properties_widget)
        property_tree.setHeaderLabels(["Property", "Value"])
        
        # Example item
        item_name = QTreeWidgetItem(property_tree)
        item_name.setText(0, "Name")
        item_name.setText(1, "MyNode")

        # Example item 2
        item_random = QTreeWidgetItem(property_tree)
        item_random.setText(0, "RandomSeed")
        item_random.setText(1, "42")

        property_tree.addTopLevelItem(item_name)
        property_tree.addTopLevelItem(item_random)

        vbox.addWidget(property_tree)
        properties_widget.setLayout(vbox)

        properties_dock.setWidget(properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, properties_dock)

        # Dock: Console/Log (on the bottom)
        log_dock = QDockWidget("Log / Console", self)
        log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)

        log_console = QTextEdit(log_dock)
        log_console.setReadOnly(True)
        log_console.setPlainText("Log messages go here...")

        log_dock.setWidget(log_console)
        self.addDockWidget(Qt.BottomDockWidgetArea, log_dock)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
