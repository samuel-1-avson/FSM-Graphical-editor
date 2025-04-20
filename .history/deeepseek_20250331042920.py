import sys
import simpy
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QDockWidget, QToolBox, QAction, 
                             QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit,
                             QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
                             QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
                             QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
                             QFileDialog, QTabWidget,QGraphicsView, QGraphicsItem, QGraphicsEllipseItem)
from PyQt5.QtGui import (QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QCursor, 
                        QPainter, QTransform, QPainterPath)
from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QPoint, QTimer, QThread, pyqtSignal, QLineF
import json
import random

class SimulationThread(QThread):
    update_signal = pyqtSignal(str, str)
    log_signal = pyqtSignal(str)
    
    def __init__(self, state_machine, env=None):
        super().__init__()
        self.state_machine = state_machine
        self.env = env if env else simpy.Environment()
        self.running = False
        self.paused = False
        self.step_mode = False
        self.step_event = None
        
    def run(self):
        self.running = True
        self.paused = False
        self.step_mode = False
        self.step_event = self.env.event()
        
        self.env.process(self.simulate_state_machine())
        
        while self.running:
            if not self.paused:
                try:
                    if self.step_mode:
                        self.env.step()
                        self.paused = True
                        self.step_mode = False
                    else:
                        self.env.step()
                except simpy.core.EmptySchedule:
                    self.log_signal.emit("Simulation complete - no more events")
                    self.running = False
            self.msleep(10)
    
    def step(self):
        self.step_mode = True
        self.paused = False
    
    def pause(self):
        self.paused = True
    
    def resume(self):
        self.paused = False
    
    def stop(self):
        self.running = False
        
    def simulate_state_machine(self):
        current_state = self.state_machine.initial_state
        if not current_state:
            self.log_signal.emit("Error: No initial state defined")
            return
            
        self.log_signal.emit(f"Starting simulation at state: {current_state}")
        self.update_signal.emit(current_state, "")
        
        while True:
            transitions = self.state_machine.get_transitions(current_state)
            
            if not transitions:
                if current_state in self.state_machine.final_states:
                    self.log_signal.emit(f"Reached final state: {current_state}")
                else:
                    self.log_signal.emit(f"No transitions from state: {current_state}")
                break
                
            transition = self.select_transition(transitions)
            
            for action in transition.actions:
                self.log_signal.emit(f"Executing action: {action}")
                yield self.env.timeout(0.1)
            
            self.log_signal.emit(f"Transitioning: {current_state} -> {transition.label} -> {transition.target_state}")
            self.update_signal.emit(transition.target_state, transition.label)
            
            current_state = transition.target_state
            yield self.env.timeout(1)
    
    def select_transition(self, transitions):
        return random.choice(transitions)

class StateTransition:
    def __init__(self, source_state, target_state, label="", condition=None, actions=None):
        self.source_state = source_state
        self.target_state = target_state
        self.label = label
        self.condition = condition if condition else lambda: True
        self.actions = actions if actions else []

class StateMachine:
    def __init__(self):
        self.states = set()
        self.transitions = []
        self.initial_state = None
        self.final_states = set()
        self.actions = {}
        
    def add_state(self, state_name, is_initial=False, is_final=False):
        self.states.add(state_name)
        if is_initial:
            self.initial_state = state_name
        if is_final:
            self.final_states.add(state_name)
            
    def add_transition(self, source, target, label="", condition=None, actions=None):
        transition = StateTransition(source, target, label, condition, actions)
        self.transitions.append(transition)
        
    def get_transitions(self, state):
        return [t for t in self.transitions if t.source_state == state]
        
    def add_action(self, state, action):
        if state not in self.actions:
            self.actions[state] = []
        self.actions[state].append(action)

class GraphicsStateItem(QGraphicsRectItem):
    def __init__(self, x, y, text, is_initial=False, is_final=False):
        super().__init__(x, y, 120, 60)
        self.text = text
        self.is_initial = is_initial
        self.is_final = is_final
        self.outgoing_transitions = []
        self.incoming_transitions = []
        self.setPen(QPen(Qt.black, 2))
        self.setBrush(QBrush(QColor(173, 216, 230)))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for transition in self.outgoing_transitions + self.incoming_transitions:
                transition.update_path()
        return super().itemChange(change, value)
        
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        painter.setPen(Qt.black)
        painter.drawText(self.rect(), Qt.AlignCenter, self.text)
        
        if self.is_initial:
            painter.setPen(Qt.green)
            painter.setBrush(QBrush(Qt.green))
            painter.drawEllipse(int(self.rect().x() + 5), int(self.rect().y() + 5), 10, 10)
            
        if self.is_final:
            painter.setPen(QPen(Qt.black, 2))
            painter.drawRect(self.rect().adjusted(5, 5, -5, -5))
        
        if self.isSelected():
            painter.setPen(QPen(Qt.blue, 2, Qt.DashLine))
            painter.drawRect(self.rect())

class GraphicsTransitionItem(QGraphicsPathItem):
    def __init__(self, start_item, end_item, text=""):
        super().__init__()
        self.start_item = start_item
        self.end_item = end_item
        self.text = text
        self.start_item.outgoing_transitions.append(self)
        self.end_item.incoming_transitions.append(self)
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
        
        if self.start_item == self.end_item:
            loop_size = 50
            control_point = QPointF(start_point.x() + loop_size, start_point.y() - loop_size)
            path = QPainterPath(start_point)
            path.quadTo(control_point, start_point)
        else:
            dx = end_point.x() - start_point.x()
            dy = end_point.y() - start_point.y()
            control_point = QPointF(start_point.x() + dx/2, start_point.y() + dy/2 - 20)
            
            path = QPainterPath(start_point)
            path.quadTo(control_point, end_point)
        
        self.setPath(path)
        
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        
        line = self.path()
        angle = 0.5
        arrow_size = 10
        
        end_point = line.pointAtPercent(1)
        start_point = line.pointAtPercent(0.95)
        direction = QLineF(start_point, end_point)
        
        direction.setLength(arrow_size)
        direction.setAngle(direction.angle() + 150)
        p1 = direction.p2()
        
        direction.setAngle(direction.angle() - 300)
        p2 = direction.p2()
        
        arrow_head = QPainterPath()
        arrow_head.moveTo(end_point)
        arrow_head.lineTo(p1)
        arrow_head.lineTo(p2)
        arrow_head.lineTo(end_point)
        
        painter.fillPath(arrow_head, QBrush(Qt.black))
        
        if self.text:
            mid_point = line.pointAtPercent(0.5)
            text_rect = painter.fontMetrics().boundingRect(self.text)
            text_rect.moveCenter(mid_point.toPoint())
            painter.fillRect(text_rect, QBrush(QColor(255, 255, 220)))
            painter.drawText(text_rect, Qt.AlignCenter, self.text)
        
        if self.isSelected():
            painter.setPen(QPen(Qt.blue, 2, Qt.DashLine))
            painter.drawPath(self.path())

class DiagramScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 2000, 2000)
        self.current_state = None
        self.transition_start_item = None
        self.mode = "select"
        self.log_function = None
        self.state_items = {}
        self.initial_state = None
        self.final_states = set()
        
    def set_mode(self, mode):
        self.mode = mode
        QApplication.setOverrideCursor(Qt.ArrowCursor if mode == "select" else Qt.CrossCursor)
    
    def set_log_function(self, log_function):
        self.log_function = log_function
    
    def build_state_machine(self):
        state_machine = StateMachine()
        
        for item in self.items():
            if isinstance(item, GraphicsStateItem):
                state_machine.add_state(item.text, item.is_initial, item.is_final)
                
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                state_machine.add_transition(item.start_item.text, item.end_item.text, item.text)
        
        return state_machine
    
    def highlight_state(self, state_name):
        for item in self.items():
            if isinstance(item, GraphicsStateItem):
                item.setBrush(QBrush(QColor(255, 200, 200) if item.text == state_name 
                            else QColor(173, 216, 230))
    
    def mousePressEvent(self, event):
        if self.mode == "state" and event.button() == Qt.LeftButton:
            state_type_dialog = QDialog()
            layout = QFormLayout(state_type_dialog)
            name_edit = QLineEdit()
            type_combo = QComboBox()
            type_combo.addItems(["Regular State", "Initial State", "Final State"])
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            
            layout.addRow("State Name:", name_edit)
            layout.addRow("State Type:", type_combo)
            layout.addRow(buttons)
            
            buttons.accepted.connect(state_type_dialog.accept)
            buttons.rejected.connect(state_type_dialog.reject)
            
            if state_type_dialog.exec_() == QDialog.Accepted:
                text = name_edit.text()
                if text in self.state_items:
                    QMessageBox.warning(None, "Duplicate State", "A state with this name already exists.")
                    return
                
                state_type = type_combo.currentText()
                is_initial = (state_type == "Initial State")
                is_final = (state_type == "Final State")
                
                if is_initial:
                    for item in self.items():
                        if isinstance(item, GraphicsStateItem) and item.is_initial:
                            item.is_initial = False
                            if self.log_function:
                                self.log_function(f"Changed {item.text} to regular state")
                
                state = GraphicsStateItem(event.scenePos().x(), event.scenePos().y(), text, is_initial, is_final)
                self.addItem(state)
                self.state_items[text] = state
                
                if is_initial: self.initial_state = text
                if is_final: self.final_states.add(text)
                self.log_function(f"Added {state_type.lower()}: {text}")
                self.set_mode("select")
                return
                
        elif self.mode == "transition" and event.button() == Qt.LeftButton:
            item = self.itemAt(event.scenePos(), QTransform())
            if isinstance(item, GraphicsStateItem):
                if not self.transition_start_item:
                    self.transition_start_item = item
                    self.log_function(f"Transition start: {item.text}")
                    return
                else:
                    text, ok = QInputDialog.getText(None, "Transition Label", "Enter transition label:")
                    if ok:
                        transition = GraphicsTransitionItem(self.transition_start_item, item, text)
                        self.addItem(transition)
                        self.log_function(f"Added transition: {self.transition_start_item.text} -> {item.text}")
                    self.transition_start_item = None
                    self.set_mode("select")
                    return
                    
        elif self.mode == "delete" and event.button() == Qt.LeftButton:
            item = self.itemAt(event.scenePos(), QTransform())
            if item:
                if isinstance(item, GraphicsTransitionItem):
                    item.start_item.outgoing_transitions.remove(item)
                    item.end_item.incoming_transitions.remove(item)
                
                if isinstance(item, GraphicsStateItem):
                    for transition in item.outgoing_transitions + item.incoming_transitions:
                        self.removeItem(transition)
                    del self.state_items[item.text]
                    if item.is_initial: self.initial_state = None
                    if item.is_final: self.final_states.discard(item.text)
                
                self.removeItem(item)
                self.log_function(f"Deleted item: {getattr(item, 'text', 'transition')}")
                self.set_mode("select")
                return
                
        super().mousePressEvent(event)
    
    def dropEvent(self, event):
        pos = event.scenePos()
        mime_data = event.mimeData()
        
        if mime_data.hasFormat("application/x-state"):
            state_type_dialog = QDialog()
            layout = QFormLayout(state_type_dialog)
            name_edit = QLineEdit(mime_data.text())
            type_combo = QComboBox()
            type_combo.addItems(["Regular State", "Initial State", "Final State"])
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            
            layout.addRow("State Name:", name_edit)
            layout.addRow("State Type:", type_combo)
            layout.addRow(buttons)
            
            buttons.accepted.connect(state_type_dialog.accept)
            buttons.rejected.connect(state_type_dialog.reject)
            
            if state_type_dialog.exec_() == QDialog.Accepted:
                text = name_edit.text()
                if text in self.state_items:
                    QMessageBox.warning(None, "Duplicate State", "A state with this name already exists.")
                    return
                
                state_type = type_combo.currentText()
                is_initial = (state_type == "Initial State")
                is_final = (state_type == "Final State")
                
                if is_initial:
                    for item in self.items():
                        if isinstance(item, GraphicsStateItem) and item.is_initial:
                            item.is_initial = False
                            if self.log_function:
                                self.log_function(f"Changed {item.text} to regular state")
                
                state = GraphicsStateItem(pos.x(), pos.y(), text, is_initial, is_final)
                self.addItem(state)
                self.state_items[text] = state
                
                if is_initial: self.initial_state = text
                if is_final: self.final_states.add(text)
                self.log_function(f"Added {state_type.lower()}: {text}")
                event.acceptProposedAction()
                
        elif mime_data.hasFormat("application/x-transition"):
            self.set_mode("transition")
            self.log_function("Transition mode: Select start state")
            event.acceptProposedAction()
            
        else:
            super().dropEvent(event)

class CodeGeneratorDialog(QDialog):
    def __init__(self, state_machine, parent=None):
        super().__init__(parent)
        self.state_machine = state_machine
        self.setWindowTitle("Code Generator")
        self.setMinimumSize(700, 500)
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.python_tab = QTextEdit()
        self.python_tab.setReadOnly(True)
        self.python_tab.setFont(QFont("Courier New", 10))
        
        self.simpy_tab = QTextEdit()
        self.simpy_tab.setReadOnly(True)
        self.simpy_tab.setFont(QFont("Courier New", 10))
        
        self.tabs.addTab(self.python_tab, "Python")
        self.tabs.addTab(self.simpy_tab, "SimPy")
        layout.addWidget(self.tabs)
        
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save Code")
        save_button.clicked.connect(self.save_code)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(save_button)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        
        self.generate_code()
    
    def generate_code(self):
        self.python_tab.setText(self.generate_python_code())
        self.simpy_tab.setText(self.generate_simpy_code())
    
    def generate_python_code(self):
        code = [
            "class StateMachine:",
            "    def __init__(self):",
            "        self.current_state = None",
            "        self.transitions = {}",
            "        self.actions = {}",
            "",
            "    def add_transition(self, source, target, action=None):",
            "        if source not in self.transitions:",
            "            self.transitions[source] = []",
            "        self.transitions[source].append((target, action))",
            "",
            "    def set_state(self, state):",
            "        self.current_state = state",
            "        if state in self.actions:",
            "            for action in self.actions[state]:",
            "                action()",
            "",
            "    def run_transition(self, trigger):",
            "        if self.current_state in self.transitions:",
            "            for (target, action) in self.transitions[self.current_state]:",
            "                if trigger == action:",
            "                    self.set_state(target)",
            "                    return True",
            "        return False",
            ""
        ]
        
        if self.state_machine.initial_state:
            code.append(f"    # Initialize with the initial state")
            code.append(f"    state_machine.set_state('{self.state_machine.initial_state}')")
        
        code.append("\n    # Define transitions between states")
        for transition in self.state_machine.transitions:
            label = transition.label
            action_param = f"'{label}'" if label else "None"
            code.append(f"    state_machine.add_transition('{transition.source_state}', "
                       f"'{transition.target_state}', {action_param})")
        
        if self.state_machine.final_states:
            code.append("\n    # Check for final states")
            code.append("    def is_final_state(state):")
            final_states = ", ".join([f"'{s}'" for s in self.state_machine.final_states])
            code.append(f"        return state in [{final_states}]")
        
        code.append("\nif __name__ == '__main__':")
        code.append("    main()")
        return "\n".join(code)
    
    # ... rest of the CodeGeneratorDialog and other classes remain the same ...

class StateMachineDesigner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("State Machine Designer")
        self.setGeometry(100, 100, 1200, 800)
        self.setup_ui()
        self.state_machine = None
        self.simulation_thread = None
    
    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        self.setup_diagram_view()
        self.setup_toolbox()
        self.setup_log_panel()
        self.setup_toolbar()
        
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")
    
    def setup_diagram_view(self):
        self.diagram_scene = DiagramScene()
        self.diagram_scene.set_log_function(self.log)
        self.diagram_view = QGraphicsView(self.diagram_scene)
        self.diagram_view.setRenderHint(QPainter.Antialiasing)
        self.main_layout.addWidget(self.diagram_view)
    
    def setup_toolbox(self):
        self.toolbox_dock = QDockWidget("Tools", self)
        self.toolbox = QToolBox()
        
        state_widget = QWidget()
        state_layout = QVBoxLayout(state_widget)
        state_layout.addWidget(StateNode("Regular State"))
        state_layout.addWidget(StateNode("Initial State"))
        state_layout.addWidget(StateNode("Final State"))
        
        transition_widget = QWidget()
        transition_layout = QVBoxLayout(transition_widget)
        transition_layout.addWidget(TransitionArrow("Transition"))
        
        action_widget = QWidget()
        action_layout = QVBoxLayout(action_widget)
        action_layout.addWidget(ActionTool("Action"))
        
        self.toolbox.addItem(state_widget, "States")
        self.toolbox.addItem(transition_widget, "Transitions")
        self.toolbox.addItem(action_widget, "Actions")
        
        self.toolbox_dock.setWidget(self.toolbox)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.toolbox_dock)
    
    def setup_log_panel(self):
        self.log_dock = QDockWidget("Log", self)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_dock.setWidget(self.log_text)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
    
    def setup_toolbar(self):
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)
        
        actions = [
            ("New", self.new_diagram),
            ("Open", self.open_diagram),
            ("Save", self.save_diagram),
            ("Select", lambda: self.set_mode("select")),
            ("Add State", lambda: self.set_mode("state")),
            ("Add Transition", lambda: self.set_mode("transition")),
            ("Delete", lambda: self.set_mode("delete")),
            ("Generate Code", self.generate_code),
            ("Simulate", self.start_simulation),
            ("Pause", self.pause_simulation),
            ("Step", self.step_simulation),
            ("Stop", self.stop_simulation)
        ]
        
        for text, handler in actions:
            action = QAction(text, self)
            action.triggered.connect(handler)
            self.toolbar.addAction(action)
            if text in ["New", "Open", "Save"]:
                self.toolbar.addSeparator()
    
    def save_diagram(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Diagram", "", "JSON Files (*.json)")
        if not file_name: return
        
        data = {'states': [], 'transitions': [], 'actions': []}
        state_id_map = {}
        
        for item in self.diagram_scene.items():
            if isinstance(item, GraphicsStateItem):
                state_id_map[item] = item.text
                data['states'].append({
                    'text': item.text,
                    'x': item.x(),
                    'y': item.y(),
                    'is_initial': item.is_initial,
                    'is_final': item.is_final
                })
            elif isinstance(item, GraphicsActionItem):
                data['actions'].append({
                    'text': item.text,
                    'x': item.x(),
                    'y': item.y()
                })
        
        for item in self.diagram_scene.items():
            if isinstance(item, GraphicsTransitionItem):
                data['transitions'].append({
                    'source': item.start_item.text,
                    'target': item.end_item.text,
                    'text': item.text
                })
        
        try:
            with open(file_name, 'w') as f:
                json.dump(data, f)
            self.log(f"Saved diagram to {file_name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Save failed: {str(e)}")
    
    def open_diagram(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Diagram", "", "JSON Files (*.json)")
        if not file_name: return
        
        try:
            with open(file_name, 'r') as f:
                data = json.load(f)
            
            self.diagram_scene.clear()
            states = {}
            
            for state_data in data.get('states', []):
                state = GraphicsStateItem(
                    state_data['x'],
                    state_data['y'],
                    state_data['text'],
                    state_data.get('is_initial', False),
                    state_data.get('is_final', False)
                )
                self.diagram_scene.addItem(state)
                states[state_data['text']] = state
                if state.is_initial: self.diagram_scene.initial_state = state.text
                if state.is_final: self.diagram_scene.final_states.add(state.text)
            
            for transition_data in data.get('transitions', []):
                source = states.get(transition_data['source'])
                target = states.get(transition_data['target'])
                if source and target:
                    transition = GraphicsTransitionItem(source, target, transition_data.get('text', ''))
                    self.diagram_scene.addItem(transition)
            
            for action_data in data.get('actions', []):
                action = GraphicsActionItem(action_data['x'], action_data['y'], action_data['text'])
                self.diagram_scene.addItem(action)
            
            self.log(f"Opened diagram from {file_name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Open failed: {str(e)}")

    # ... remaining methods remain the same ...

def main():
    app = QApplication(sys.argv)
    window = StateMachineDesigner()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()