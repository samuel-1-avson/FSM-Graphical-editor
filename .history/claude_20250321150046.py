import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QDockWidget, QTreeWidget, QTreeWidgetItem, 
                             QAction, QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QComboBox, 
                             QLineEdit, QRadioButton, QGroupBox, QGraphicsView, QGraphicsScene, 
                             QGraphicsItem, QGraphicsRectItem, QTableWidget, QHeaderView, QSplitter,
                             QTabWidget, QTextEdit, QStatusBar, QFrame, QMenu, QPushButton, QCheckBox)
from PyQt5.QtGui import QIcon, QPen, QBrush, QColor, QFont, QPixmap
from PyQt5.QtCore import Qt, QRectF, QPointF, QSize

class Node(QGraphicsRectItem):
    def __init__(self, x, y, width, height, color, text="", parent=None):
        super().__init__(x, y, width, height, parent)
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.black, 1))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.text = text
        
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.text:
            painter.setPen(Qt.black)
            painter.drawText(self.rect(), Qt.AlignCenter, self.text)

class Connection(QGraphicsItem):
    def __init__(self, startNode, endNode, parent=None):
        super().__init__(parent)
        self.startNode = startNode
        self.endNode = endNode
        self.setZValue(-1)  # Ensure connections are drawn behind nodes
        
    def boundingRect(self):
        return QRectF(self.startNode.x(), self.startNode.y(), 
                     self.endNode.x() - self.startNode.x() + self.endNode.rect().width(), 
                     self.endNode.y() - self.startNode.y() + self.endNode.rect().height())
        
    def paint(self, painter, option, widget):
        painter.setPen(QPen(Qt.black, 2))
        startPoint = QPointF(self.startNode.x() + self.startNode.rect().width(), 
                           self.startNode.y() + self.startNode.rect().height()/2)
        endPoint = QPointF(self.endNode.x(), 
                         self.endNode.y() + self.endNode.rect().height()/2)
        painter.drawLine(startPoint, endPoint)
        # Draw arrow at end
        painter.setBrush(Qt.black)
        arrowSize = 10
        angle = 0.5  # Arrow head angle
        painter.drawPolygon(
            QPointF(endPoint),
            QPointF(endPoint.x() - arrowSize * (1 + angle), endPoint.y() - arrowSize * angle),
            QPointF(endPoint.x() - arrowSize * (1 + angle), endPoint.y() + arrowSize * angle),
        )

class NFCouserPanel(QGraphicsRectItem):
    def __init__(self, x, y, width, height, parent=None):
        super().__init__(x, y, width, height, parent)
        self.setPen(QPen(Qt.black, 2))
        self.setBrush(QBrush(QColor(255, 200, 200)))
        
        # Add horizontal lines for the grid
        numRows = 4
        rowHeight = height / numRows
        for i in range(1, numRows):
            line = QGraphicsRectItem(x, y + i * rowHeight, width, 1, self)
            line.setBrush(QBrush(Qt.black))
            
        # Add vertical lines for the grid
        numCols = 3
        colWidth = width / numCols
        for i in range(1, numCols):
            line = QGraphicsRectItem(x + i * colWidth, y, 1, height, self)
            line.setBrush(QBrush(Qt.black))
            
        # Add small rectangles in cells
        for row in range(numRows):
            for col in range(numCols):
                if row < 3:  # Only add to top 3 rows
                    for subCol in range(4):  # 4 small rects per cell
                        rect = QGraphicsRectItem(
                            x + col * colWidth + 10 + subCol * 20, 
                            y + row * rowHeight + 15, 
                            15, 5, self
                        )
                        rect.setBrush(QBrush(Qt.black))
                        
        # Add small circle in the middle
        circle = QGraphicsEllipseItem(x + width/2 - 5, y + height/2 - 5, 10, 10, self)
        circle.setBrush(QBrush(Qt.gray))
        circle.setPen(QPen(Qt.black, 1))
        
        # Add a row of black rectangles at the bottom
        for i in range(5):
            rect = QGraphicsRectItem(x + width/2 - 50 + i * 20, y + height - rowHeight/2, 15, 5, self)
            rect.setBrush(QBrush(Qt.black))

class BrainSimulatorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Brain Simulator")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        
        # Create main layout
        mainLayout = QVBoxLayout(self.centralWidget)
        
        # Create menu bar
        self.createMenuBar()
        
        # Create toolbar
        self.createToolbar()
        
        # Create status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Paused (33.323/s)")
        
        # Create dock widgets
        self.createDockWidgets()
        
        # Create central graphics view
        self.graphicsView = QGraphicsView()
        self.scene = QGraphicsScene()
        self.graphicsView.setScene(self.scene)
        self.graphicsView.setRenderHint(QPushButton().render(), True)
        self.graphicsView.setBackgroundBrush(QBrush(QColor(200, 200, 200)))
        
        # Add central network visualization panel to layout
        mainLayout.addWidget(self.graphicsView)
        
        # Add nodes to scene
        self.createNetworkGraph()
        
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
        
        # Tools menu
        toolsMenu = menuBar.addMenu("Tools")
        toolsMenu.addAction("Settings")
        
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
        toolbar.addSeparator()
        
        # Add line edit for iteration count
        toolbar.addWidget(QLabel("  "))
        toolbar.addWidget(QLineEdit("10000"))
        
        # Add CUDA selector
        toolbar.addWidget(QLabel("  "))
        cudaCombo = QComboBox()
        cudaCombo.addItem("CUDA")
        toolbar.addWidget(cudaCombo)
        
        # Add World selector
        toolbar.addWidget(QLabel("World:  "))
        worldCombo = QComboBox()
        worldCombo.addItem("CustomPongWorld")
        toolbar.addWidget(worldCombo)
        
    def createDockWidgets(self):
        # Tasks dock widget
        tasksDock = QDockWidget("Tasks")
        tasksDock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tasksWidget = QWidget()
        tasksLayout = QVBoxLayout(tasksWidget)
        
        # Add period settings group
        periodGroup = QGroupBox("Period settings")
        periodLayout = QVBoxLayout(periodGroup)
        
        uniformRadio = QRadioButton("Uniform")
        uniformRadio.setChecked(True)
        normalRadio = QRadioButton("Normal")
        constantRadio = QRadioButton("Constant")
        combinationRadio = QRadioButton("Combination")
        
        periodLayout.addWidget(uniformRadio)
        periodLayout.addWidget(normalRadio)
        periodLayout.addWidget(constantRadio)
        periodLayout.addWidget(combinationRadio)
        
        tasksLayout.addWidget(periodGroup)
        tasksDock.setWidget(tasksWidget)
        self.addDockWidget(Qt.LeftDockWidgetArea, tasksDock)
        
        # Network dock widget
        networkDock = QDockWidget("Network")
        networkDock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        networkWidget = QTabWidget()
        tabHarm = QWidget()
        tabAsm = QWidget()
        tabCSharp = QWidget()
        
        networkWidget.addTab(tabHarm, "HARM")
        networkWidget.addTab(tabAsm, "ASM")
        networkWidget.addTab(tabCSharp, "C#")
        
        networkDock.setWidget(networkWidget)
        self.addDockWidget(Qt.LeftDockWidgetArea, networkDock)
        
        # Task properties dock widget
        taskPropDock = QDockWidget("Task Properties")
        taskPropDock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        taskPropWidget = QWidget()
        taskPropLayout = QVBoxLayout(taskPropWidget)
        
        # Add period parameters group
        periodParamGroup = QGroupBox("Period parameters")
        periodParamLayout = QVBoxLayout(periodParamGroup)
        
        periodLabel = QLabel("Period: 1")
        randomPeriod1 = QLabel("RandomPeriod: False")
        randomPeriod2 = QLabel("RandomPeriod: 10")
        randomPeriod3 = QLabel("RandomPeriod: 1")
        
        periodParamLayout.addWidget(periodLabel)
        periodParamLayout.addWidget(randomPeriod1)
        periodParamLayout.addWidget(randomPeriod2)
        periodParamLayout.addWidget(randomPeriod3)
        
        taskPropLayout.addWidget(periodParamGroup)
        taskPropDock.setWidget(taskPropWidget)
        self.addDockWidget(Qt.LeftDockWidgetArea, taskPropDock)
        
        # Node properties dock widget
        nodePropDock = QDockWidget("Node Properties")
        nodePropDock.setAllowedAreas(Qt.RightDockWidgetArea)
        nodePropWidget = QWidget()
        nodePropLayout = QVBoxLayout(nodePropWidget)
        
        nodeNameLabel = QLabel("Node_424 - MyRandomNode")
        
        # Add General group
        generalGroup = QGroupBox("General")
        generalLayout = QVBoxLayout(generalGroup)
        
        nameLabel = QLabel("Name: Node_424")
        gpuLabel = QLabel("GPU: 0")
        idLabel = QLabel("ID: 424")
        orderLabel = QLabel("TopologicalOrder: 13")
        
        generalLayout.addWidget(nameLabel)
        generalLayout.addWidget(gpuLabel)
        generalLayout.addWidget(idLabel)
        generalLayout.addWidget(orderLabel)
        
        # Add Persistance group
        persistanceGroup = QGroupBox("Persistance")
        persistanceLayout = QVBoxLayout(persistanceGroup)
        
        dataFolderLabel = QLabel("DataFolder: ")
        
        persistanceLayout.addWidget(dataFolderLabel)
        
        nodePropLayout.addWidget(nodeNameLabel)
        nodePropLayout.addWidget(generalGroup)
        nodePropLayout.addWidget(persistanceGroup)
        
        nodePropDock.setWidget(nodePropWidget)
        self.addDockWidget(Qt.RightDockWidgetArea, nodePropDock)
        
        # Memory blocks dock widget
        memoryDock = QDockWidget("Memory Blocks")
        memoryDock.setAllowedAreas(Qt.RightDockWidgetArea)
        memoryWidget = QWidget()
        memoryLayout = QVBoxLayout(memoryWidget)
        
        memoryTable = QTableWidget(2, 3)
        memoryTable.setHorizontalHeaderLabels(["Name", "Size", "Type"])
        memoryTable.setItem(0, 0, QTableWidget.QTableWidgetItem("Output"))
        memoryTable.setItem(0, 1, QTableWidget.QTableWidgetItem("3"))
        memoryTable.setItem(0, 2, QTableWidget.QTableWidgetItem("Single"))
        memoryTable.setItem(1, 0, QTableWidget.QTableWidgetItem("RandomNumber"))
        memoryTable.setItem(1, 1, QTableWidget.QTableWidgetItem("4"))
        memoryTable.setItem(1, 2, QTableWidget.QTableWidgetItem("Single"))
        
        memoryLayout.addWidget(memoryTable)
        memoryDock.setWidget(memoryWidget)
        self.addDockWidget(Qt.RightDockWidgetArea, memoryDock)
        
        # Console dock widget
        consoleDock = QDockWidget("Console")
        consoleDock.setAllowedAreas(Qt.BottomDockWidgetArea)
        consoleText = QTextEdit()
        consoleText.setReadOnly(True)
        consoleText.setStyleSheet("background-color: black; color: white;")
        consoleFont = QFont("Courier New", 9)
        consoleText.setFont(consoleFont)
        
        # Add console output
        consoleOutput = """Freeing memory...
GPU 0: 687 MB used, 1360 MB free
Clearing simulation...
Stopped after 12 steps.
--------------
Updating memory blocks...
Successful update after 1 cycle(s).
Scheduling...
Initializing tasks...
Allocating memory...
GPU 0: 694 MB used, 1353 MB free
Starting simulation...
Paused."""
        
        consoleText.setText(consoleOutput)
        
        consoleDock.setWidget(consoleText)
        self.addDockWidget(Qt.BottomDockWidgetArea, consoleDock)
        
        # Validation dock widget
        validationDock = QDockWidget("Validation")
        validationDock.setAllowedAreas(Qt.BottomDockWidgetArea)
        validationWidget = QTabWidget()
        
        # Create tabs
        errorsTab = QWidget()
        warningsTab = QWidget()
        infoTab = QWidget()
        
        # Add content to info tab
        infoLayout = QVBoxLayout(infoTab)
        infoTable = QTableWidget(3, 2)
        infoTable.setColumnWidth(0, 150)
        infoTable.setColumnWidth(1, 800)
        infoTable.setHorizontalHeaderLabels(["", ""])
        infoTable.verticalHeader().setVisible(False)
        
        # Add row data
        infoTable.setItem(0, 0, QTableWidget.QTableWidgetItem("NKmeansWM00"))
        infoTable.setItem(0, 1, QTableWidget.QTableWidgetItem("Node will load data from user defined folder: C:\\projects\\BrainSimulatorSampleProjects\\"))
        infoTable.setItem(1, 0, QTableWidget.QTableWidgetItem("Hid1"))
        infoTable.setItem(1, 1, QTableWidget.QTableWidgetItem("Node will load data from user defined folder: C:\\projects\\BrainSimulatorSampleProjects\\"))
        infoTable.setItem(2, 0, QTableWidget.QTableWidgetItem("Hid2"))
        infoTable.setItem(2, 1, QTableWidget.QTableWidgetItem("Node will load data from user defined folder: C:\\projects\\BrainSimulatorSampleProjects\\"))
        
        infoLayout.addWidget(infoTable)
        
        # Add tabs to widget
        validationWidget.addTab(errorsTab, "Errors")
        validationWidget.addTab(warningsTab, "Warnings")
        validationWidget.addTab(infoTab, "Info")
        
        validationDock.setWidget(validationWidget)
        self.addDockWidget(Qt.BottomDockWidgetArea, validationDock)
        
    def createNetworkGraph(self):
        # Create visual_wm node
        visualWM = Node(520, 200, 60, 60, QColor(173, 216, 230), "Visual_WM")
        self.scene.addItem(visualWM)
        
        # Create NFcouser00 panel
        nfcouser = NFCouserPanel(670, 215, 180, 180)
        self.scene.addItem(nfcouser)
        
        # Create parentInput nodes
        parentInput1 = Node(320, 250, 60, 60, QColor(173, 216, 230), "ParentInput")
        parentInput2 = Node(320, 420, 60, 60, QColor(173, 216, 230), "ParentInput")
        self.scene.addItem(parentInput1)
        self.scene.addItem(parentInput2)
        
        # Create Node_424 node
        node424 = Node(704, 550, 60, 60, QColor(255, 165, 0), "Node_424\nUniform (0.1)")
        self.scene.addItem(node424)
        
        # Create Output node
        outputNode = Node(850, 550, 60, 60, QColor(200, 200, 200), "Output")
        self.scene.addItem(outputNode)
        
        # Create connections
        connection1 = Connection(parentInput1, visualWM)
        connection2 = Connection(parentInput2, node424)
        connection3 = Connection(node424, outputNode)
        self.scene.addItem(connection1)
        self.scene.addItem(connection2)
        self.scene.addItem(connection3)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BrainSimulatorGUI()
    window.show()
    sys.exit(app.exec_())