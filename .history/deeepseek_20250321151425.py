import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QDockWidget, QTreeWidget, QTreeWidgetItem, 
                             QAction, QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QComboBox, 
                             QLineEdit, QRadioButton, QGroupBox, QGraphicsView, QGraphicsScene, 
                             QGraphicsItem, QGraphicsRectItem, QTableWidget, QHeaderView, QSplitter,
                             QTabWidget, QTextEdit, QStatusBar, QFrame, QMenu, QPushButton, QCheckBox,
                             QTableWidgetItem, QGraphicsEllipseItem, QGraphicsPolygonItem, QStyle)
from PyQt5.QtGui import QIcon, QPen, QBrush, QColor, QFont, QPixmap, QPainter, QPolygonF
from PyQt5.QtCore import Qt, QRectF, QPointF, QSize, QObject, pyqtSignal

class StateSignal(QObject):
    transition_triggered = pyqtSignal(str, str)  # from_state, to_state

class StateNode(QGraphicsRectItem):
    def __init__(self, name, x, y, parent=None):
        super().__init__(0, 0, 120, 80, parent)
        self.setPos(x, y)
        self.name = name
        self.entry_action = ""
        self.exit_action = ""
        self.variables = {}
        self.is_initial = False
        self.setBrush(QBrush(QColor(173, 216, 230)))
        self.setPen(QPen(Qt.black, 2))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setZValue(1)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        painter.setPen(Qt.black)
        painter.drawText(self.rect(), Qt.AlignCenter, self.name)
        
        if self.is_initial:
            painter.setBrush(QBrush(Qt.green))
            painter.drawEllipse(QRectF(-20, 20, 15, 15))

class Transition(QGraphicsPolygonItem):
    def __init__(self, start_state, end_state, parent=None):
        super().__init__(parent)
        self.start_state = start_state
        self.end_state = end_state
        self.event = ""
        self.guard = ""
        self.action = ""
        self.setPen(QPen(Qt.black, 2))
        self.setZValue(0)
        self.update_path()

    def update_path(self):
        path = QPolygonF()
        start_point = self.start_state.pos() + QPointF(60, 40)
        end_point = self.end_state.pos() + QPointF(60, 40)
        
        # Create curved path
        ctrl_point = QPointF((start_point.x() + end_point.x())/2, 
                            (start_point.y() + end_point.y())/2 + 50)
        
        path.append(start_point)
        path.append(ctrl_point)
        path.append(end_point)
        self.setPolygon(path)
        
        # Add arrowhead
        arrow = QPolygonF()
        arrow.append(QPointF(-10, -5))
        arrow.append(QPointF(0, 0))
        arrow.append(QPointF(-10, 5))
        arrow.translate(end_point)
        self.arrowhead = QGraphicsPolygonItem(arrow, self)
        self.arrowhead.setBrush(QBrush(Qt.black))

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        mid_point = self.polygon()[1]
        painter.drawText(mid_point.x(), mid_point.y(), 
                        f"{self.event}\n[{self.guard}]\n/{self.action}")

class FSMSimulatorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mechatronics FSM Designer")
        self.setGeometry(100, 100, 1200, 800)
        self.current_state = None
        self.states = []
        self.transitions = []
        self.signals = StateSignal()
        
        self.initUI()
        self.create_initial_scene()
        
        self.signals.transition_triggered.connect(self.handle_transition)

    def initUI(self):
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        mainLayout = QVBoxLayout(self.centralWidget)
        
        self.create_menu_bar()
        self.create_toolbar()
        self.create_dock_widgets()
        
        # Create graphics view
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        mainLayout.addWidget(self.view)
        
        self.statusBar().showMessage("Ready")

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        file_menu.addAction("New", self.new_project)
        file_menu.addAction("Open", self.open_project)
        file_menu.addAction("Save", self.save_project)
        file_menu.addAction("Export to C", self.export_to_c)
        file_menu.addAction("Exit", self.close)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction("Add State", self.add_state)
        edit_menu.addAction("Add Transition", self.add_transition)
        edit_menu.addAction("Set Initial", self.set_initial_state)

        # Simulation menu
        sim_menu = menubar.addMenu("Simulation")
        sim_menu.addAction("Start", self.start_simulation)
        sim_menu.addAction("Step", self.step_simulation)
        sim_menu.addAction("Reset", self.reset_simulation)

    def create_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        toolbar.addAction(QIcon("icons/state.png"), "Add State", self.add_state)
        toolbar.addAction(QIcon("icons/transition.png"), "Add Transition", self.add_transition)
        toolbar.addSeparator()
        toolbar.addAction(QIcon("icons/simulate.png"), "Simulate", self.start_simulation)
        toolbar.addAction(QIcon("icons/reset.png"), "Reset", self.reset_simulation)

    def create_dock_widgets(self):
        # Properties dock
        self.props_dock = QDockWidget("Properties", self)
        self.props_widget = QTabWidget()
        
        # State properties
        self.state_props = QWidget()
        state_layout = QVBoxLayout(self.state_props)
        self.state_name = QLineEdit()
        self.state_entry = QTextEdit()
        self.state_exit = QTextEdit()
        self.state_vars = QTableWidget(0, 2)
        self.state_vars.setHorizontalHeaderLabels(["Name", "Value"])
        
        state_layout.addWidget(QLabel("State Name:"))
        state_layout.addWidget(self.state_name)
        state_layout.addWidget(QLabel("Entry Actions:"))
        state_layout.addWidget(self.state_entry)
        state_layout.addWidget(QLabel("Exit Actions:"))
        state_layout.addWidget(self.state_exit)
        state_layout.addWidget(QLabel("Variables:"))
        state_layout.addWidget(self.state_vars)
        
        # Transition properties
        self.trans_props = QWidget()
        trans_layout = QVBoxLayout(self.trans_props)
        self.trans_event = QLineEdit()
        self.trans_guard = QLineEdit()
        self.trans_action = QLineEdit()
        
        trans_layout.addWidget(QLabel("Event:"))
        trans_layout.addWidget(self.trans_event)
        trans_layout.addWidget(QLabel("Guard Condition:"))
        trans_layout.addWidget(self.trans_guard)
        trans_layout.addWidget(QLabel("Action:"))
        trans_layout.addWidget(self.trans_action)
        
        self.props_widget.addTab(self.state_props, "State")
        self.props_widget.addTab(self.trans_props, "Transition")
        self.props_dock.setWidget(self.props_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.props_dock)
        
        # Simulation dock
        sim_dock = QDockWidget("Simulation Control", self)
        sim_widget = QWidget()
        sim_layout = QVBoxLayout(sim_widget)
        
        self.event_list = QComboBox()
        self.trigger_btn = QPushButton("Trigger Event")
        self.current_state_label = QLabel("Current State: None")
        
        sim_layout.addWidget(QLabel("Available Events:"))
        sim_layout.addWidget(self.event_list)
        sim_layout.addWidget(self.trigger_btn)
        sim_layout.addWidget(self.current_state_label)
        sim_dock.setWidget(sim_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, sim_dock)

    def create_initial_scene(self):
        # Create initial state
        initial_state = StateNode("Initial", 100, 100)
        initial_state.is_initial = True
        self.scene.addItem(initial_state)
        self.states.append(initial_state)
        self.current_state = initial_state

    def add_state(self):
        state = StateNode(f"State_{len(self.states)+1}", 200, 200)
        self.scene.addItem(state)
        self.states.append(state)

    def add_transition(self):
        if len(self.selectedItems()) == 2:
            items = [item for item in self.selectedItems() if isinstance(item, StateNode)]
            if len(items) == 2:
                trans = Transition(items[0], items[1])
                self.scene.addItem(trans)
                self.transitions.append(trans)

    def set_initial_state(self):
        if self.selectedItems():
            item = self.selectedItems()[0]
            if isinstance(item, StateNode):
                for state in self.states:
                    state.is_initial = False
                item.is_initial = True
                self.current_state = item
                self.scene.update()

    def start_simulation(self):
        if self.current_state:
            self.statusBar().showMessage("Simulation running...")
            self.current_state.setBrush(QBrush(Qt.green))
            
    def handle_transition(self, from_state, to_state):
        self.current_state.setBrush(QBrush(QColor(173, 216, 230)))
        self.current_state = next(s for s in self.states if s.name == to_state)
        self.current_state.setBrush(QBrush(Qt.green))
        self.current_state_label.setText(f"Current State: {self.current_state.name}")

    def export_to_c(self):
        # Generate C code from FSM
        code = "/* Generated FSM Code */\n"
        code += f"enum States {{{', '.join([s.name for s in self.states])}}};\n"
        code += "void fsm_step() {\n"
        code += f"  static enum States current_state = {self.current_state.name};\n"
        code += "  switch(current_state) {\n"
        
        for state in self.states:
            code += f"    case {state.name}:\n"
            transitions = [t for t in self.transitions if t.start_state == state]
            if transitions:
                code += "      if ("
                code += " || ".join([f"({t.guard})" for t in transitions])
                code += ") {\n"
                for t in transitions:
                    code += f"        if ({t.guard}) {{\n"
                    code += f"          {t.action};\n"
                    code += f"          current_state = {t.end_state.name};\n"
                    code += "        }\n"
                code += "      }\n"
            code += "      break;\n"
        
        code += "  }\n}\n"
        print(code)

    def new_project(self):
        """Clear the current project and start a new one."""
        self.scene.clear()
        self.states = []
        self.transitions = []
        self.current_state = None
        self.create_initial_scene()
        self.statusBar().showMessage("New project created.")

    def open_project(self):
        """Open a saved project from a file."""
        # Implement file loading logic here
        self.statusBar().showMessage("Open project functionality not implemented yet.")

    def save_project(self):
        """Save the current project to a file."""
        # Implement file saving logic here
        self.statusBar().showMessage("Save project functionality not implemented yet.")

    def step_simulation(self):
        """Step through the simulation one transition at a time."""
        self.statusBar().showMessage("Step simulation functionality not implemented yet.")

    def reset_simulation(self):
        """Reset the simulation to the initial state."""
        if self.current_state:
            self.current_state.setBrush(QBrush(QColor(173, 216, 230)))
            self.current_state = next(s for s in self.states if s.is_initial)
            self.current_state.setBrush(QBrush(Qt.green))
            self.current_state_label.setText(f"Current State: {self.current_state.name}")
            self.statusBar().showMessage("Simulation reset to initial state.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FSMSimulatorGUI()
    window.show()
    sys.exit(app.exec_())