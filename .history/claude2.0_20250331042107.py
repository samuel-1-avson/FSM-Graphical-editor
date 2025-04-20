import sys
import simpy
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QDockWidget, QToolBox, QAction, 
                             QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit,
                             QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
                             QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
                             QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
                             QFileDialog, QTabWidget,QGraphicsView, QGraphicsItem, QGraphicsEllipseItem,)
from PyQt5.QtGui import QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QCursor, QPainter,QTransform,QPainterPath
from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QPoint, QTimer, QThread, pyqtSignal
import json
import random

class SimulationThread(QThread):
    update_signal = pyqtSignal(str, str)  # (state_name, transition_name)
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
        
        # Create SimPy process
        self.env.process(self.simulate_state_machine())
        
        # Run simulation
        while self.running:
            if not self.paused:
                try:
                    # Step through simulation
                    if self.step_mode:
                        self.env.step()
                        self.paused = True
                        self.step_mode = False
                    else:
                        self.env.step()
                except simpy.core.EmptySchedule:
                    self.log_signal.emit("Simulation complete - no more events")
                    self.running = False
            
            # Small delay to avoid hogging the CPU
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
            # Find possible transitions from current state
            transitions = self.state_machine.get_transitions(current_state)
            
            if not transitions:
                if current_state in self.state_machine.final_states:
                    self.log_signal.emit(f"Reached final state: {current_state}")
                else:
                    self.log_signal.emit(f"No transitions from state: {current_state}")
                break
                
            # Choose a transition based on probabilities or conditions
            transition = self.select_transition(transitions)
            
            # Execute any actions associated with the transition
            for action in transition.actions:
                self.log_signal.emit(f"Executing action: {action}")
                yield self.env.timeout(0.1)  # Small delay to visualize action execution
            
            # Move to the next state
            self.log_signal.emit(f"Transitioning: {current_state} -> {transition.label} -> {transition.target_state}")
            self.update_signal.emit(transition.target_state, transition.label)
            
            current_state = transition.target_state
            
            # Add a small delay between state transitions
            yield self.env.timeout(1)
    
    def select_transition(self, transitions):
        # For now, just select a random transition
        # In a more complex system, this could use probabilities or conditions
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
        self.actions = {}  # State -> [actions]
        
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
    def __init__(self, x, y, text, is_initial=False, is_final=False):
        super().__init__(x, y, 120, 60)
        self.text = text
        self.is_initial = is_initial
        self.is_final = is_final
        self.setPen(QPen(Qt.black, 2))
        self.setBrush(QBrush(QColor(173, 216, 230)))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        
        # Draw text
        painter.setPen(Qt.black)
        painter.drawText(self.rect(), Qt.AlignCenter, self.text)
        
        # Draw initial state indicator (green circle)
        if self.is_initial:
            painter.setPen(Qt.green)
            painter.setBrush(QBrush(Qt.green))
            painter.drawEllipse(int(self.rect().x() + 5), int(self.rect().y() + 5), 10, 10)
            
        # Draw final state indicator (double border)
        if self.is_final:
            painter.setPen(QPen(Qt.black, 2))
            painter.drawRect(self.rect().adjusted(5, 5, -5, -5))
        
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
        
        # If self-transition, create a loop
        if self.start_item == self.end_item:
            loop_size = 50
            control_point = QPointF(start_point.x() + loop_size, start_point.y() - loop_size)
            path = QPainterPath(start_point)
            path.quadTo(control_point, start_point)
        else:
            # Create a slight curve for transitions
            dx = end_point.x() - start_point.x()
            dy = end_point.y() - start_point.y()
            control_point = QPointF(start_point.x() + dx/2, start_point.y() + dy/2 - 20)
            
            path = QPainterPath(start_point)
            path.quadTo(control_point, end_point)
        
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
            # Create a background for the text
            text_rect = painter.fontMetrics().boundingRect(self.text)
            text_rect.moveCenter(mid_point.toPoint())
            painter.fillRect(text_rect, QBrush(QColor(255, 255, 220)))
            painter.drawText(text_rect, Qt.AlignCenter, self.text)
        
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
        self.state_items = {}  # Map of state names to GraphicsStateItem
        self.initial_state = None
        self.final_states = set()
        
    def set_mode(self, mode):
        self.mode = mode
        if mode == "select":
            QApplication.setOverrideCursor(Qt.ArrowCursor)
        else:
            QApplication.setOverrideCursor(Qt.CrossCursor)
    
    def set_log_function(self, log_function):
        self.log_function = log_function
    
    def build_state_machine(self):
        """Build and return a StateMachine object from the current diagram"""
        state_machine = StateMachine()
        
        # Add states
        for item in self.items():
            if isinstance(item, GraphicsStateItem):
                state_machine.add_state(item.text, item.is_initial, item.is_final)
                
        # Add transitions
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                source_state = item.start_item.text
                target_state = item.end_item.text
                state_machine.add_transition(source_state, target_state, item.text)
        
        return state_machine
    
    def highlight_state(self, state_name):
        """Highlight the specified state in the diagram"""
        for item in self.items():
            if isinstance(item, GraphicsStateItem):
                if item.text == state_name:
                    item.setBrush(QBrush(QColor(255, 200, 200)))  # Light red highlight
                else:
                    item.setBrush(QBrush(QColor(173, 216, 230)))  # Reset to default
    
    def highlight_transition(self, source_state, target_state):
        """Highlight the transition between two states"""
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                if item.start_item.text == source_state and item.end_item.text == target_state:
                    item.setPen(QPen(Qt.red, 3))
                else:
                    item.setPen(QPen(Qt.black, 2))
        
    def mousePressEvent(self, event):
        if self.mode == "state" and event.button() == Qt.LeftButton:
            state_type_dialog = QDialog()
            state_type_dialog.setWindowTitle("State Type")
            
            layout = QFormLayout(state_type_dialog)
            
            name_edit = QLineEdit()
            layout.addRow("State Name:", name_edit)
            
            type_combo = QComboBox()
            type_combo.addItems(["Regular State", "Initial State", "Final State"])
            layout.addRow("State Type:", type_combo)
            
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(state_type_dialog.accept)
            buttons.rejected.connect(state_type_dialog.reject)
            layout.addRow(buttons)
            
            if state_type_dialog.exec_() == QDialog.Accepted:
                text = name_edit.text()
                state_type = type_combo.currentText()
                
                if text:
                    is_initial = (state_type == "Initial State")
                    is_final = (state_type == "Final State")
                    
                if text:
                    if text in self.state_items:
                    QMessageBox.warning(None, "Duplicate State", "A state with this name already exists.")
                    returnis_initial = (state_type == "Initial State")    
                    
                    # Only one initial state allowed
                    if is_initial:
                        # Check if we already have an initial state
                        for item in self.items():
                            if isinstance(item, GraphicsStateItem) and item.is_initial:
                                item.is_initial = False
                                if self.log_function:
                                    self.log_function(f"Changed {item.text} to regular state")
                    
                    state = GraphicsStateItem(event.scenePos().x(), event.scenePos().y(), text, is_initial, is_final)
                    self.addItem(state)
                    self.state_items[text] = state
                    
                    if is_initial:
                        self.initial_state = text
                    if is_final:
                        self.final_states.add(text)
                    
                    if self.log_function:
                        self.log_function(f"Added {state_type.lower()}: {text}")
                    
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
                    # Allow self-transitions
                    text, ok = QInputDialog.getText(None, "Transition Label", "Enter transition label:")
                    if ok:
                        transition = GraphicsTransitionItem(self.transition_start_item, end_item, text)
                        self.addItem(transition)
                        if self.log_function:
                            if self.transition_start_item == end_item:
                                self.log_function(f"Added self-transition on {self.transition_start_item.text}: {text}")
                            else:
                                self.log_function(f"Added transition from {self.transition_start_item.text} to {end_item.text}: {text}")
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
                if isinstance(item, GraphicsStateItem):
                    # Remove any transitions connected to this state
                    transitions_to_remove = []
                    for transition_item in self.items():
                        if isinstance(transition_item, GraphicsTransitionItem):
                            if transition_item.start_item == item or transition_item.end_item == item:
                                transitions_to_remove.append(transition_item)
                    
                    for transition in transitions_to_remove:
                        self.removeItem(transition)
                    
                    # Remove the state itself
                    if item.text in self.state_items:
                        del self.state_items[item.text]
                    
                    if item.is_initial and item.text == self.initial_state:
                        self.initial_state = None
                    
                    if item.is_final and item.text in self.final_states:
                        self.final_states.remove(item.text)
                
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
            state_type_dialog = QDialog()
            state_type_dialog.setWindowTitle("State Type")
            
            layout = QFormLayout(state_type_dialog)
            
            name_edit = QLineEdit()
            name_edit.setText(event.mimeData().text())
            layout.addRow("State Name:", name_edit)
            
            type_combo = QComboBox()
            type_combo.addItems(["Regular State", "Initial State", "Final State"])
            layout.addRow("State Type:", type_combo)
            
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(state_type_dialog.accept)
            buttons.rejected.connect(state_type_dialog.reject)
            layout.addRow(buttons)
            
            if state_type_dialog.exec_() == QDialog.Accepted:
                text = name_edit.text()
                state_type = type_combo.currentText()
                
                if text:
                    is_initial = (state_type == "Initial State")
                    is_final = (state_type == "Final State")
                    
                    # Only one initial state allowed
                    if is_initial:
                        # Check if we already have an initial state
                        for item in self.items():
                            if isinstance(item, GraphicsStateItem) and item.is_initial:
                                item.is_initial = False
                                if self.log_function:
                                    self.log_function(f"Changed {item.text} to regular state")
                    
                    state = GraphicsStateItem(pos.x(), pos.y(), text, is_initial, is_final)
                    self.addItem(state)
                    self.state_items[text] = state
                    
                    if is_initial:
                        self.initial_state = text
                    if is_final:
                        self.final_states.add(text)
                    
                    if self.log_function:
                        self.log_function(f"Added {state_type.lower()}: {text}")
                    
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

class CodeGeneratorDialog(QDialog):
    def __init__(self, state_machine, parent=None):
        super().__init__(parent)
        self.state_machine = state_machine
        self.setWindowTitle("Code Generator")
        self.setMinimumSize(700, 500)
        
        layout = QVBoxLayout(self)
        
        # Create tabs for different code types
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
        
        # Generate code buttons
        button_layout = QHBoxLayout()
        
        save_button = QPushButton("Save Code")
        save_button.clicked.connect(self.save_code)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        # Generate code
        self.generate_code()
    
    def generate_code(self):
        # Generate Python code
        python_code = self.generate_python_code()
        self.python_tab.setText(python_code)
        
        # Generate SimPy code
        simpy_code = self.generate_simpy_code()
        self.simpy_tab.setText(simpy_code)
    
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
            "    def add_action(self, state, action):",
            "        if state not in self.actions:",
            "            self.actions[state] = []",
            "        self.actions[state].append(action)",
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
            "",
            "# Example usage:",
            "def main():",
            "    state_machine = StateMachine()",
            ""
        ]
        
        # Add states
        if self.state_machine.initial_state:
            code.append(f"    # Initialize with the initial state")
            code.append(f"    state_machine.set_state('{self.state_machine.initial_state}')")
        
        # Add transitions
        code.append("\n    # Define transitions between states")
        for transition in self.state_machine.transitions:
            source = transition.source_state
            target = transition.target_state
            label = transition.label if transition.label else "None"
            code.append(f"    state_machine.add_transition('{source}', '{target}', '{label}')")
        
        # Add final states check
        if self.state_machine.final_states:
            code.append("\n    # Check for final states")
            code.append("    def is_final_state(state):")
            final_states_list = ", ".join([f"'{state}'" for state in self.state_machine.final_states])
            code.append(f"        return state in [{final_states_list}]")
        
        code.append("\nif __name__ == '__main__':")
        code.append("    main()")
        
        return "\n".join(code)
    
    def generate_simpy_code(self):
        code = [
            "import simpy",
            "import random",
            "",
            "class StateMachineSimulation:",
            "    def __init__(self, env):",
            "        self.env = env",
            "        self.current_state = None",
            "        self.transitions = {}",
            "        self.final_states = set()",
            "",
            "    def add_transition(self, source, target, probability=1.0, delay=1.0):",
            "        if source not in self.transitions:",
            "            self.transitions[source] = []",
            "        self.transitions[source].append((target, probability, delay))",
            "",
            "    def add_final_state(self, state):",
            "        self.final_states.add(state)",
            "",
            "    def set_initial_state(self, state):",
            "        self.current_state = state",
            "",
            "    def run(self):",
            "        while self.current_state not in self.final_states:",
            "            yield self.env.process(self.step())",
            "",
            "    def step(self):",
            "        if self.current_state not in self.transitions:",
            "            return",
            "            ",
            "        transitions = self.transitions[self.current_state]",
            "        # Select transition based on probability",
            "        r = random.random()",
            "        cumulative_prob = 0",
            "        selected_transition = None",
            "        ",
            "        for target, prob, delay in transitions:",
            "            cumulative_prob += prob",
            "            if r <= cumulative_prob:",
            "                selected_transition = (target, delay)",
            "                break",
            "        ",
            "        if selected_transition:",
            "            target, delay = selected_transition",
            "            print(f\"Transitioning from {self.current_state} to {target} with delay {delay}\")",
            "            yield self.env.timeout(delay)",
            "            self.current_state = target",
            "",
            "# Example usage",
            "def main():",
            "    env = simpy.Environment()",
            "    sm = StateMachineSimulation(env)",
            ""
        ]
        
        # Add states
        if self.state_machine.initial_state:
            code.append(f"    # Set initial state")
            code.append(f"    sm.set_initial_state('{self.state_machine.initial_state}')")
        
        # Add transitions
        code.append("\n    # Define transitions")
        for transition in self.state_machine.transitions:
            source = transition.source_state
            target = transition.target_state
            code.append(f"    sm.add_transition('{source}', '{target}', 1.0, 1.0)")
        
        # Add final states
        if self.state_machine.final_states:
            code.append("\n    # Define final states")
            for state in self.state_machine.final_states:
                code.append(f"    sm.add_final_state('{state}')")
        
        code.append("\n    # Run the simulation")
        code.append("    env.process(sm.run())")
        code.append("    env.run(until=100)  # Run for a maximum of 100 time units")
        
        code.append("\nif __name__ == '__main__':")
        code.append("    main()")
        
        return "\n".join(code)
    
    def save_code(self):
        current_tab_index = self.tabs.currentIndex()
        
        file_type = "Python (*.py)" if current_tab_index == 0 else "Python (*.py)"
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Code", "", file_type)
        
        if file_name:
            with open(file_name, 'w') as f:
                if current_tab_index == 0:
                    f.write(self.python_tab.toPlainText())
                else:
                    f.write(self.simpy_tab.toPlainText())


class StateMachineDesigner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("State Machine Designer")
        self.setGeometry(100, 100, 1200, 800)
        
        self.setup_ui()
        self.state_machine = None
        self.simulation_thread = None
        
    def setup_ui(self):
        # Main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create diagram view
        self.setup_diagram_view()
        
        # Create toolbox
        self.setup_toolbox()
        
        # Create log panel
        self.setup_log_panel()
        
        # Create toolbar
        self.setup_toolbar()
        
        # Create status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")
        
    def setup_diagram_view(self):
        self.diagram_scene = DiagramScene()
        self.diagram_scene.set_log_function(self.log)
        
        self.diagram_view = QGraphicsView(self.diagram_scene)
        self.diagram_view.setRenderHint(QPainter.Antialiasing)
        self.diagram_view.setDragMode(QGraphicsView.RubberBandDrag)
        
        self.main_layout.addWidget(self.diagram_view)
        
    def setup_toolbox(self):
        self.toolbox_dock = QDockWidget("Tools", self)
        self.toolbox_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        self.toolbox = QToolBox()
        
        # State tools
        state_widget = QWidget()
        state_layout = QVBoxLayout(state_widget)
        
        normal_state = StateNode("Regular State")
        initial_state = StateNode("Initial State")
        final_state = StateNode("Final State")
        
        state_layout.addWidget(normal_state)
        state_layout.addWidget(initial_state)
        state_layout.addWidget(final_state)
        state_layout.addStretch()
        
        # Transition tools
        transition_widget = QWidget()
        transition_layout = QVBoxLayout(transition_widget)
        
        normal_transition = TransitionArrow("Transition")
        
        transition_layout.addWidget(normal_transition)
        transition_layout.addStretch()
        
        # Action tools
        action_widget = QWidget()
        action_layout = QVBoxLayout(action_widget)
        
        action = ActionTool("Action")
        
        action_layout.addWidget(action)
        action_layout.addStretch()
        
        # Add pages to toolbox
        self.toolbox.addItem(state_widget, "States")
        self.toolbox.addItem(transition_widget, "Transitions")
        self.toolbox.addItem(action_widget, "Actions")
        
        self.toolbox_dock.setWidget(self.toolbox)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.toolbox_dock)
        
    def setup_log_panel(self):
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        self.log_dock.setWidget(self.log_text)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        
    def setup_toolbar(self):
        # Main toolbar
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)
        
        # File actions
        new_action = QAction("New", self)
        new_action.triggered.connect(self.new_diagram)
        self.toolbar.addAction(new_action)
        
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_diagram)
        self.toolbar.addAction(open_action)
        
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_diagram)
        self.toolbar.addAction(save_action)
        
        self.toolbar.addSeparator()
        
        # Edit actions
        select_action = QAction("Select", self)
        select_action.triggered.connect(lambda: self.set_mode("select"))
        self.toolbar.addAction(select_action)
        
        state_action = QAction("Add State", self)
        state_action.triggered.connect(lambda: self.set_mode("state"))
        self.toolbar.addAction(state_action)
        
        transition_action = QAction("Add Transition", self)
        transition_action.triggered.connect(lambda: self.set_mode("transition"))
        self.toolbar.addAction(transition_action)
        
        action_action = QAction("Add Action", self)
        action_action.triggered.connect(lambda: self.set_mode("action"))
        self.toolbar.addAction(action_action)
        
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.set_mode("delete"))
        self.toolbar.addAction(delete_action)
        
        self.toolbar.addSeparator()
        
        # Simulation actions
        generate_action = QAction("Generate Code", self)
        generate_action.triggered.connect(self.generate_code)
        self.toolbar.addAction(generate_action)
        
        simulate_action = QAction("Simulate", self)
        simulate_action.triggered.connect(self.start_simulation)
        self.toolbar.addAction(simulate_action)
        
        pause_action = QAction("Pause", self)
        pause_action.triggered.connect(self.pause_simulation)
        self.toolbar.addAction(pause_action)
        
        step_action = QAction("Step", self)
        step_action.triggered.connect(self.step_simulation)
        self.toolbar.addAction(step_action)
        
        stop_action = QAction("Stop", self)
        stop_action.triggered.connect(self.stop_simulation)
        self.toolbar.addAction(stop_action)
        
    def set_mode(self, mode):
        self.diagram_scene.set_mode(mode)
        self.statusBar.showMessage(f"Mode: {mode}")
        
    def log(self, message):
        self.log_text.append(message)
        
    def new_diagram(self):
        reply = QMessageBox.question(self,
                                    'New Diagram',
                                    'Are you sure you want to create a new diagram? Unsaved changes will be lost.',
                                    QMessageBox.Yes | QMessageBox.No,
                                    QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.diagram_scene.clear()
            self.log("Created new diagram")
            
    def open_diagram(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Diagram", "", "JSON Files (*.json)")
        
        if file_name:
            try:
                with open(file_name, 'r') as f:
                    data = json.load(f)
                
                # Clear current diagram
                self.diagram_scene.clear()
                
                # Load states
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
                    self.diagram_scene.state_items[state_data['text']] = state
                    states[state_data['id']] = state
                    
                    if state_data.get('is_initial', False):
                        self.diagram_scene.initial_state = state_data['text']
                    if state_data.get('is_final', False):
                        self.diagram_scene.final_states.add(state_data['text'])
                
                # Load transitions
                for transition_data in data.get('transitions', []):
                    source = states.get(transition_data['source_id'])
                    target = states.get(transition_data['target_id'])
                    
                    if source and target:
                        transition = GraphicsTransitionItem(source, target, transition_data.get('text', ''))
                        self.diagram_scene.addItem(transition)
                
                # Load actions
                for action_data in data.get('actions', []):
                    action = GraphicsActionItem(action_data['x'], action_data['y'], action_data['text'])
                    self.diagram_scene.addItem(action)
                
                self.log(f"Opened diagram from {file_name}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open diagram: {str(e)}")
            
    def save_diagram(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Diagram", "", "JSON Files (*.json)")
        
        if file_name:
            # Prepare data structure for serialization
            data = {
                'states': [],
                'transitions': [],
                'actions': []
            }
            
            state_id_map = {}  # Map GraphicsStateItem to ID
            
            # Collect states
            for item in self.diagram_scene.items():
                if isinstance(item, GraphicsStateItem):
                    state_id = str(id(item))
                    state_id_map[item] = state_id
                    
                    state_data = {
                        'id': state_id,
                        'text': item.text,
                        'x': item.x(),
                        'y': item.y(),
                        'is_initial': item.is_initial,
                        'is_final': item.is_final
                    }
                    data['states'].append(state_data)
                    
                elif isinstance(item, GraphicsActionItem):
                    action_data = {
                        'text': item.text,
                        'x': item.x(),
                        'y': item.y()
                    }
                    data['actions'].append(action_data)
            
            # Collect transitions
            for item in self.diagram_scene.items():
                if isinstance(item, GraphicsTransitionItem):
                    source_id = state_id_map.get(item.start_item)
                    target_id = state_id_map.get(item.end_item)
                    
                    if source_id and target_id:
                        transition_data = {
                            'source_id': source_id,
                            'target_id': target_id,
                            'text': item.text
                        }
                        data['transitions'].append(transition_data)
            
            try:
                with open(file_name, 'w') as f:
                    json.dump(data, f)
                self.log(f"Saved diagram to {file_name}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save diagram: {str(e)}")
            
    def generate_code(self):
        try:
            # Build a state machine model from the diagram
            state_machine = self.diagram_scene.build_state_machine()
            
            # Show the code generator dialog
            dialog = CodeGeneratorDialog(state_machine, self)
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate code: {str(e)}")
            
    def start_simulation(self):
        try:
            # Check if simulation is already running
            if self.simulation_thread and self.simulation_thread.isRunning():
                QMessageBox.information(self, "Simulation", "Simulation is already running")
                return
                
            # Build a state machine model from the diagram
            state_machine = self.diagram_scene.build_state_machine()
            
            # Validate state machine
            if not state_machine.initial_state:
                QMessageBox.critical(self, "Error", "No initial state defined")
                return
                
            # Create and start simulation thread
            self.simulation_thread = SimulationThread(state_machine)
            self.simulation_thread.update_signal.connect(self.update_simulation_state)
            self.simulation_thread.log_signal.connect(self.log)
            self.simulation_thread.start()
            
            self.log("Simulation started")
            self.statusBar.showMessage("Simulation running")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start simulation: {str(e)}")
            
    def update_simulation_state(self, state_name, transition_name):
        # Update visual representation
        self.diagram_scene.highlight_state(state_name)
        
    def pause_simulation(self):
        if self.simulation_thread and self.simulation_thread.isRunning():
            self.simulation_thread.pause()
            self.log("Simulation paused")
            self.statusBar.showMessage("Simulation paused")
            
    def step_simulation(self):
        if self.simulation_thread and self.simulation_thread.isRunning():
            self.simulation_thread.step()
            self.log("Simulation step")
            
    def stop_simulation(self):
        if self.simulation_thread and self.simulation_thread.isRunning():
            self.simulation_thread.stop()
            self.log("Simulation stopped")
            self.statusBar.showMessage("Simulation stopped")


def main():
    app = QApplication(sys.argv)
    window = StateMachineDesigner()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()