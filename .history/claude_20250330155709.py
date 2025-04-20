import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QDockWidget, QToolBox, QAction, 
                             QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit,
                             QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
                             QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
                             QSpinBox, QComboBox,QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox)
from PyQt5.QtGui import QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QCursor,QPainter

from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QPoint

class StateNode(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(100, 40)
        self.setStyleSheet("background-color: lightblue; border-radius: 5px;")
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
            
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.text())
        mime_data.setData("application/x-state", b"state")
        drag.setMimeData(mime_data)
        
        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        
        drag.exec_(Qt.CopyAction | Qt.MoveAction)

class TransitionArrow(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(100, 40)
        self.setStyleSheet("background-color: lightgreen; border-radius: 5px;")
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
            
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.text())
        mime_data.setData("application/x-transition", b"transition")
        drag.setMimeData(mime_data)
        
        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        
        drag.exec_(Qt.CopyAction | Qt.MoveAction)

class ActionTool(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(100, 40)
        self.setStyleSheet("background-color: lightyellow; border-radius: 5px;")
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
            
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.text())
        mime_data.setData("application/x-action", b"action")
        drag.setMimeData(mime_data)
        
        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        
        drag.exec_(Qt.CopyAction | Qt.MoveAction)

class GraphicsStateItem(QGraphicsRectItem):
    def __init__(self, x, y, text):
        super().__init__(x, y, 120, 60)
        self.text = text
        self.setPen(QPen(Qt.black, 2))
        self.setBrush(QBrush(QColor(173, 216, 230)))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        
        # Draw text
        painter.setPen(Qt.black)
        painter.drawText(self.rect(), Qt.AlignCenter, self.text)
        
        # If selected, draw a highlight
        if self.isSelected():
            painter.setPen(QPen(Qt.blue, 2, Qt.DashLine))
            painter.drawRect(self.rect())

class GraphicsTransitionItem(QGraphicsPathItem):
    def __init__(self, start_item, end_item, text=""):
        super().__init__()
        self.start_item = start_item
        self.end_item = end_item
        self.text = text
        self.setPen(QPen(Qt.black, 2))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.update_path()
        
    def update_path(self):
        start_rect = self.start_item.rect()
        end_rect = self.end_item.rect()
        
        start_point = QPointF(self.start_item.x() + start_rect.width()/2, 
                              self.start_item.y() + start_rect.height()/2)
        end_point = QPointF(self.end_item.x() + end_rect.width()/2, 
                           self.end_item.y() + end_rect.height()/2)
        
        path = QPainterPath(start_point)
        path.lineTo(end_point)
        self.setPath(path)
        
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        
        # Draw arrow at the end
        line = self.path()
        angle = 0.5  # Arrow head angle in radians
        arrow_size = 10
        
        # Get the end point
        end_point = line.pointAtPercent(1)
        
        # Get the direction vector
        start_point = line.pointAtPercent(0.95)  # Use a point close to the end
        direction = QLineF(start_point, end_point)
        
        # Calculate arrow points
        direction.setLength(arrow_size)
        direction.setAngle(direction.angle() + 150)
        p1 = direction.p2()
        
        direction.setAngle(direction.angle() - 300)
        p2 = direction.p2()
        
        # Draw the arrow head
        arrow_head = QPainterPath()
        arrow_head.moveTo(end_point)
        arrow_head.lineTo(p1)
        arrow_head.lineTo(p2)
        arrow_head.lineTo(end_point)
        
        painter.fillPath(arrow_head, QBrush(Qt.black))
        
        # Draw the text if any
        if self.text:
            mid_point = line.pointAtPercent(0.5)
            painter.drawText(mid_point, self.text)
        
        # If selected, draw a highlight
        if self.isSelected():
            painter.setPen(QPen(Qt.blue, 2, Qt.DashLine))
            painter.drawPath(self.path())

class GraphicsActionItem(QGraphicsRectItem):
    def __init__(self, x, y, text):
        super().__init__(x, y, 80, 40)
        self.text = text
        self.setPen(QPen(Qt.black, 2))
        self.setBrush(QBrush(QColor(255, 255, 200)))  # Light yellow
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        
        # Draw text
        painter.setPen(Qt.black)
        painter.drawText(self.rect(), Qt.AlignCenter, self.text)
        
        # If selected, draw a highlight
        if self.isSelected():
            painter.setPen(QPen(Qt.blue, 2, Qt.DashLine))
            painter.drawRect(self.rect())

class DiagramScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 2000, 2000)
        self.current_state = None
        self.transition_start_item = None
        self.mode = "select"
        self.log_function = None
        
    def set_mode(self, mode):
        self.mode = mode
        if mode == "select":
            QApplication.setOverrideCursor(Qt.ArrowCursor)
        else:
            QApplication.setOverrideCursor(Qt.CrossCursor)
    
    def set_log_function(self, log_function):
        self.log_function = log_function
        
    def mousePressEvent(self, event):
        if self.mode == "state" and event.button() == Qt.LeftButton:
            text, ok = QInputDialog.getText(None, "State Name", "Enter state name:")
            if ok and text:
                state = GraphicsStateItem(event.scenePos().x(), event.scenePos().y(), text)
                self.addItem(state)
                if self.log_function:
                    self.log_function(f"Added state: {text}")
                self.set_mode("select")
                return
                
        elif self.mode == "transition" and event.button() == Qt.LeftButton:
            item = self.itemAt(event.scenePos(), QTransform())
            if isinstance(item, GraphicsStateItem):
                if not self.transition_start_item:
                    self.transition_start_item = item
                    if self.log_function:
                        self.log_function(f"Transition start: {item.text}")
                    return
                else:
                    end_item = item
                    if end_item != self.transition_start_item:
                        text, ok = QInputDialog.getText(None, "Transition Label", "Enter transition label:")
                        if ok:
                            transition = GraphicsTransitionItem(self.transition_start_item, end_item, text)
                            self.addItem(transition)
                            if self.log_function:
                                self.log_function(f"Added transition from {self.transition_start_item.text} to {end_item.text}")
                    self.transition_start_item = None
                    self.set_mode("select")
                    return
                    
        elif self.mode == "action" and event.button() == Qt.LeftButton:
            text, ok = QInputDialog.getText(None, "Action Name", "Enter action name:")
            if ok and text:
                action = GraphicsActionItem(event.scenePos().x(), event.scenePos().y(), text)
                self.addItem(action)
                if self.log_function:
                    self.log_function(f"Added action: {text}")
                self.set_mode("select")
                return
                
        elif self.mode == "delete" and event.button() == Qt.LeftButton:
            item = self.itemAt(event.scenePos(), QTransform())
            if item:
                self.removeItem(item)
                if self.log_function:
                    if hasattr(item, 'text'):
                        self.log_function(f"Deleted item: {item.text}")
                    else:
                        self.log_function("Deleted transition")
                self.set_mode("select")
                return
        
        # Default to standard handling if no special mode logic was triggered
        super().mousePressEvent(event)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-state") or \
           event.mimeData().hasFormat("application/x-transition") or \
           event.mimeData().hasFormat("application/x-action"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)
    
    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-state") or \
           event.mimeData().hasFormat("application/x-transition") or \
           event.mimeData().hasFormat("application/x-action"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)
    
    def dropEvent(self, event):
        pos = event.scenePos()
        
        if event.mimeData().hasFormat("application/x-state"):
            text = event.mimeData().text()
            state = GraphicsStateItem(pos.x(), pos.y(), text)
            self.addItem(state)
            if self.log_function:
                self.log_function(f"Added state: {text}")
            event.acceptProposedAction()
            
        elif event.mimeData().hasFormat("application/x-transition"):
            self.set_mode("transition")
            if self.log_function:
                self.log_function("Transition mode: Select start state")
            event.acceptProposedAction()
            
        elif event.mimeData().hasFormat("application/x-action"):
            text = event.mimeData().text()
            action = GraphicsActionItem(pos.x(), pos.y(), text)
            self.addItem(action)
            if self.log_function:
                self.log_function(f"Added action: {text}")
            event.acceptProposedAction()
            
        else:
            super().dropEvent(event)

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
        self.statusBar.showMessage("Ready")
        
        # Create the main working area (graphics view)
        self.graphicsView = QGraphicsView()
        self.scene = DiagramScene()
        self.graphicsView.setScene(self.scene)
        self.graphicsView.setRenderHint(QPainter.Antialiasing)
        self.graphicsView.setBackgroundBrush(QBrush(QColor(240, 240, 240)))
        self.graphicsView.setDragMode(QGraphicsView.RubberBandDrag)
        
        # Set up log function
        self.logText = None  # Will be set after dock widgets are created
        
        # Add graphics view (working area) to the main layout
        self.mainLayout.addWidget(self.graphicsView)
        
        # Create dock widgets
        self.createDockWidgets()
        
        # Set scene log function
        self.scene.set_log_function(self.log)
        
    def log(self, message):
        if self.logText:
            current_text = self.logText.toPlainText()
            self.logText.setText(f"{current_text}\n{message}")
            # Auto-scroll to bottom
            scrollbar = self.logText.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
    def createMenuBar(self):
        menuBar = self.menuBar()
        
        # File menu
        fileMenu = menuBar.addMenu("File")
        newAction = fileMenu.addAction("New")
        newAction.triggered.connect(self.newProject)
        openAction = fileMenu.addAction("Open")
        openAction.triggered.connect(self.openProject)
        saveAction = fileMenu.addAction("Save")
        saveAction.triggered.connect(self.saveProject)
        fileMenu.addSeparator()
        exitAction = fileMenu.addAction("Exit")
        exitAction.triggered.connect(self.close)
        
        # Edit menu
        editMenu = menuBar.addMenu("Edit")
        undoAction = editMenu.addAction("Undo")
        redoAction = editMenu.addAction("Redo")
        editMenu.addSeparator()
        cutAction = editMenu.addAction("Cut")
        copyAction = editMenu.addAction("Copy")
        pasteAction = editMenu.addAction("Paste")
        editMenu.addSeparator()
        deleteAction = editMenu.addAction("Delete")
        deleteAction.triggered.connect(lambda: self.scene.set_mode("delete"))
        
        # View menu
        viewMenu = menuBar.addMenu("View")
        zoomInAction = viewMenu.addAction("Zoom In")
        zoomInAction.triggered.connect(self.zoomIn)
        zoomOutAction = viewMenu.addAction("Zoom Out")
        zoomOutAction.triggered.connect(self.zoomOut)
        resetViewAction = viewMenu.addAction("Reset View")
        resetViewAction.triggered.connect(self.resetView)
        
        # Run menu
        runMenu = menuBar.addMenu("Run")
        startAction = runMenu.addAction("Start")
        startAction.triggered.connect(self.startSimulation)
        pauseAction = runMenu.addAction("Pause")
        pauseAction.triggered.connect(self.pauseSimulation)
        stepAction = runMenu.addAction("Step")
        stepAction.triggered.connect(self.stepSimulation)
        
        # Help menu
        helpMenu = menuBar.addMenu("Help")
        docAction = helpMenu.addAction("Documentation")
        aboutAction = helpMenu.addAction("About")
        aboutAction.triggered.connect(self.showAbout)
        
    def createToolbar(self):
        # Main toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # Add file operations
        newAction = toolbar.addAction("New")
        newAction.triggered.connect(self.newProject)
        openAction = toolbar.addAction("Open")
        openAction.triggered.connect(self.openProject)
        saveAction = toolbar.addAction("Save")
        saveAction.triggered.connect(self.saveProject)
        toolbar.addSeparator()
        
        # Add run controls
        startAction = toolbar.addAction("Start")
        startAction.triggered.connect(self.startSimulation)
        pauseAction = toolbar.addAction("Pause")
        pauseAction.triggered.connect(self.pauseSimulation)
        stepAction = toolbar.addAction("Step")
        stepAction.triggered.connect(self.stepSimulation)
        toolbar.addSeparator()
        
        # Add edit tools
        selectAction = toolbar.addAction("Select")
        selectAction.triggered.connect(lambda: self.scene.set_mode("select"))
        deleteAction = toolbar.addAction("Delete")
        deleteAction.triggered.connect(lambda: self.scene.set_mode("delete"))
        toolbar.addSeparator()
        
        # Add zoom controls
        zoomInAction = toolbar.addAction("Zoom In")
        zoomInAction.triggered.connect(self.zoomIn)
        zoomOutAction = toolbar.addAction("Zoom Out")
        zoomOutAction.triggered.connect(self.zoomOut)
        
    def createDockWidgets(self):
        # Toolbox dock widget (left side)
        toolboxDock = QDockWidget("Toolbox")
        toolboxDock.setAllowedAreas(Qt.LeftDockWidgetArea)
        
        # Create toolbox with multiple sections
        toolbox = QToolBox()
        
        # State tools section
        stateWidget = QWidget()
        stateLayout = QVBoxLayout(stateWidget)
        
        # Add state tools
        stateLayout.addWidget(QLabel("Drag or click to add states:"))
        
        stateButton1 = StateNode("Initial State")
        stateButton1.clicked.connect(lambda: self.scene.set_mode("state"))
        stateLayout.addWidget(stateButton1)
        
        stateButton2 = StateNode("Regular State")
        stateButton2.clicked.connect(lambda: self.scene.set_mode("state"))
        stateLayout.addWidget(stateButton2)
        
        stateButton3 = StateNode("Final State")
        stateButton3.clicked.connect(lambda: self.scene.set_mode("state"))
        stateLayout.addWidget(stateButton3)
        
        stateLayout.addStretch()
        toolbox.addItem(stateWidget, "States")
        
        # Transition tools section
        transitionWidget = QWidget()
        transitionLayout = QVBoxLayout(transitionWidget)
        
        # Add transition tools
        transitionLayout.addWidget(QLabel("Drag or click to add transitions:"))
        
        transButton1 = TransitionArrow("Simple Transition")
        transButton1.clicked.connect(lambda: self.scene.set_mode("transition"))
        transitionLayout.addWidget(transButton1)
        
        transButton2 = TransitionArrow("Conditional")
        transButton2.clicked.connect(lambda: self.scene.set_mode("transition"))
        transitionLayout.addWidget(transButton2)
        
        transitionLayout.addStretch()
        toolbox.addItem(transitionWidget, "Transitions")
        
        # Action tools section
        actionWidget = QWidget()
        actionLayout = QVBoxLayout(actionWidget)
        
        # Add action tools
        actionLayout.addWidget(QLabel("Drag or click to add actions:"))
        
        actionButton1 = ActionTool("Set Value")
        actionButton1.clicked.connect(lambda: self.scene.set_mode("action"))
        actionLayout.addWidget(actionButton1)
        
        actionButton2 = ActionTool("Call Function")
        actionButton2.clicked.connect(lambda: self.scene.set_mode("action"))
        actionLayout.addWidget(actionButton2)
        
        actionButton3 = ActionTool("Timer")
        actionButton3.clicked.connect(lambda: self.scene.set_mode("action"))
        actionLayout.addWidget(actionButton3)
        
        actionLayout.addStretch()
        toolbox.addItem(actionWidget, "Actions")
        
        # Other tools section
        otherWidget = QWidget()
        otherLayout = QVBoxLayout(otherWidget)
        
        # Add other tools
        otherLayout.addWidget(QLabel("Utility tools:"))
        
        selectButton = QPushButton("Select Mode")
        selectButton.clicked.connect(lambda: self.scene.set_mode("select"))
        otherLayout.addWidget(selectButton)
        
        deleteButton = QPushButton("Delete Mode")
        deleteButton.clicked.connect(lambda: self.scene.set_mode("delete"))
        otherLayout.addWidget(deleteButton)
        
        clearButton = QPushButton("Clear All")
        clearButton.clicked.connect(self.clearScene)
        otherLayout.addWidget(clearButton)
        
        otherLayout.addStretch()
        toolbox.addItem(otherWidget, "Other Tools")
        
        toolboxDock.setWidget(toolbox)
        self.addDockWidget(Qt.LeftDockWidgetArea, toolboxDock)
        
        # Properties dock widget (right side)
        propDock = QDockWidget("Properties")
        propDock.setAllowedAreas(Qt.RightDockWidgetArea)
        propWidget = QWidget()
        propLayout = QVBoxLayout(propWidget)
        propLayout.addWidget(QLabel("Properties will appear here when an item is selected"))
        propDock.setWidget(propWidget)
        self.addDockWidget(Qt.RightDockWidgetArea, propDock)
        
        # Log section (bottom)
        logDock = QDockWidget("Log")
        logDock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.logText = QTextEdit()
        self.logText.setReadOnly(True)
        self.logText.setStyleSheet("background-color: black; color: white;")
        logFont = QFont("Courier New", 9)
        self.logText.setFont(logFont)
        self.logText.setText("Application started.\nReady.")
        
        logDock.setWidget(self.logText)
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
    
    # Action functions
    def newProject(self):
        reply = QMessageBox.question(self, 'New Project', 
                                     'Create a new project? Unsaved changes will be lost.',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.scene.clear()
            self.log("New project created.")
    
    def openProject(self):
        self.log("Open project dialog would appear here.")
        # This would typically open a file dialog
        # For demonstration purposes, we'll just log the action
    
    def saveProject(self):
        self.log("Save project dialog would appear here.")
        # This would typically open a save file dialog
        # For demonstration purposes, we'll just log the action
    
    def startSimulation(self):
        self.log("Starting simulation...")
        self.statusBar.showMessage("Running")
    
    def pauseSimulation(self):
        self.log("Simulation paused.")
        self.statusBar.showMessage("Paused")
    
    def stepSimulation(self):
        self.log("Stepping simulation...")
        self.statusBar.showMessage("Stepped")
    
    def zoomIn(self):
        self.graphicsView.scale(1.2, 1.2)
        self.log("Zoomed in.")
    
    def zoomOut(self):
        self.graphicsView.scale(1/1.2, 1/1.2)
        self.log("Zoomed out.")
    
    def resetView(self):
        self.graphicsView.resetTransform()
        self.log("View reset.")
    
    def clearScene(self):
        reply = QMessageBox.question(self, 'Clear All', 
                                     'Remove all items from the diagram?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.scene.clear()
            self.log("Scene cleared.")
    
    def showAbout(self):
        QMessageBox.about(self, "About Brain Simulator", 
                         "Brain Simulator\nVersion 1.0\n\nA tool for creating and simulating state machines.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BrainSimulatorGUI()
    window.show()
    sys.exit(app.exec_())