import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QDockWidget, QToolBox, QAction, 
                             QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit)
from PyQt5.QtGui import QIcon, QBrush, QColor, QFont
from PyQt5.QtCore import Qt

class BrainSimulatorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        # Set up the main window
        self.setWindowTitle("Brain Simulator")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        
        # Create main layout
        self.mainLayout = QVBoxLayout(self.centralWidget)
        
        # Create the menu bar
        self.createMenuBar()
        
        # Create toolbar with basic controls
        self.createToolbar()
        
        # Create the status bar at the bottom
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Paused (0.0/s)")
        
        # Create the main working area (graphics view)
        self.graphicsView = QGraphicsView()
        self.scene = QGraphicsScene()
        self.graphicsView.setScene(self.scene)
        self.graphicsView.setBackgroundBrush(QBrush(QColor(240, 240, 240)))
        
        # Add graphics view (working area) to the main layout
        self.mainLayout.addWidget(self.graphicsView)
        
        # Create dock widgets
        self.createDockWidgets()
        
    def createMenuBar(self):
        menuBar = self.menuBar()
        
        # File menu
        fileMenu = menuBar.addMenu("File")
        fileMenu.addAction("New")
        fileMenu.addAction("Open")
        fileMenu.addAction("Save")
        fileMenu.addAction("Exit")
        
        # Edit menu
        editMenu = menuBar.addMenu("Edit")
        editMenu.addAction("Undo")
        editMenu.addAction("Redo")
        editMenu.addAction("Cut")
        editMenu.addAction("Copy")
        editMenu.addAction("Paste")
        
        # Run menu
        runMenu = menuBar.addMenu("Run")
        runMenu.addAction("Start")
        runMenu.addAction("Pause")
        runMenu.addAction("Step")
        
        # View menu
        viewMenu = menuBar.addMenu("View")
        viewMenu.addAction("Zoom In")
        viewMenu.addAction("Zoom Out")
        viewMenu.addAction("Reset View")
        
        # Help menu
        helpMenu = menuBar.addMenu("Help")
        helpMenu.addAction("Documentation")
        helpMenu.addAction("About")
        
    def createToolbar(self):
        # Main toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # Add file operations
        toolbar.addAction(QIcon(), "New")
        toolbar.addAction(QIcon(), "Open")
        toolbar.addAction(QIcon(), "Save")
        toolbar.addSeparator()
        
        # Add run controls
        toolbar.addAction(QIcon(), "Start")
        toolbar.addAction(QIcon(), "Pause")
        toolbar.addAction(QIcon(), "Step")
        toolbar.addSeparator()
        
        # Add zoom controls
        toolbar.addAction(QIcon(), "Zoom In")
        toolbar.addAction(QIcon(), "Zoom Out")
        
    def createDockWidgets(self):
        # Toolbox dock widget (left side)
        toolboxDock = QDockWidget("Toolbox")
        toolboxDock.setAllowedAreas(Qt.LeftDockWidgetArea)
        
        # Create toolbox with multiple sections
        toolbox = QToolBox()
        
        # State tools section
        stateWidget = QWidget()
        stateLayout = QVBoxLayout(stateWidget)
        stateLayout.addWidget(QLabel("Drag state tools here"))
        toolbox.addItem(stateWidget, "States")
        
        # Transition tools section
        transitionWidget = QWidget()
        transitionLayout = QVBoxLayout(transitionWidget)
        transitionLayout.addWidget(QLabel("Drag transition tools here"))
        toolbox.addItem(transitionWidget, "Transitions")
        
        # Action tools section
        actionWidget = QWidget()
        actionLayout = QVBoxLayout(actionWidget)
        actionLayout.addWidget(QLabel("Drag action tools here"))
        toolbox.addItem(actionWidget, "Actions")
        
        # Other tools section
        otherWidget = QWidget()
        otherLayout = QVBoxLayout(otherWidget)
        otherLayout.addWidget(QLabel("Drag other tools here"))
        toolbox.addItem(otherWidget, "Other Tools")
        
        toolboxDock.setWidget(toolbox)
        self.addDockWidget(Qt.LeftDockWidgetArea, toolboxDock)
        
        # Properties dock widget (right side)
        propDock = QDockWidget("Properties")
        propDock.setAllowedAreas(Qt.RightDockWidgetArea)
        propWidget = QWidget()
        propLayout = QVBoxLayout(propWidget)
        propLayout.addWidget(QLabel("Properties will appear here"))
        propDock.setWidget(propWidget)
        self.addDockWidget(Qt.RightDockWidgetArea, propDock)
        
        # Log section (bottom)
        logDock = QDockWidget("Log")
        logDock.setAllowedAreas(Qt.BottomDockWidgetArea)
        logText = QTextEdit()
        logText.setReadOnly(True)
        logText.setStyleSheet("background-color: black; color: white;")
        logFont = QFont("Courier New", 9)
        logText.setFont(logFont)
        logText.setText("Application started.\nReady.")
        
        logDock.setWidget(logText)
        self.addDockWidget(Qt.BottomDockWidgetArea, logDock)
        
        # Validation dock widget (bottom)
        validationDock = QDockWidget("Validation")
        validationDock.setAllowedAreas(Qt.BottomDockWidgetArea)
        validationText = QTextEdit()
        validationText.setReadOnly(True)
        validationText.setText("No validation issues found.")
        
        validationDock.setWidget(validationText)
        self.addDockWidget(Qt.BottomDockWidgetArea, validationDock)
        
        # Set initial dock widget sizes
        self.resizeDocks([toolboxDock, propDock], [200, 250], Qt.Horizontal)
        self.resizeDocks([logDock, validationDock], [150, 150], Qt.Vertical)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BrainSimulatorGUI()
    window.show()
    sys.exit(app.exec_())