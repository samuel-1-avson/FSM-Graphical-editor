import sys
import simpy
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QDockWidget, QToolBox, QAction, 
                             QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit,
                             QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
                             QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
                             QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
                             QFileDialog, QTabWidget)
from PyQt5.QtGui import QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QCursor, QPainter
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
            painter.drawEllipse(self.rect().x() + 5, self.rect().y() + 5, 10, 10)
            
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