import sys
import os
import tempfile
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QDockWidget, QToolBox, QAction, 
                             QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit,
                             QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
                             QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
                             QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
                             QFileDialog, QProgressBar, QTabWidget, QCheckBox, QActionGroup, QGraphicsItem, QGroupBox)
from PyQt5.QtGui import QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QCursor, QPainter, QPainterPath
from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir

class MatlabConnection(QObject):
    """Class to handle MATLAB connectivity"""
    connectionStatusChanged = pyqtSignal(bool, str)
    simulationFinished = pyqtSignal(bool, str)
    codeGenerationFinished = pyqtSignal(bool, str, str)
    
    def __init__(self):
        super().__init__()
        self.matlab_path = ""
        self.connected = False
        self.simulation_process = None
        
    def set_matlab_path(self, path):
        """Set the path to MATLAB executable"""
        self.matlab_path = path
        if os.path.exists(path):
            self.connected = True
            self.connectionStatusChanged.emit(True, "MATLAB connection established")
            return True
        else:
            self.connected = False
            self.connectionStatusChanged.emit(False, "Failed to connect to MATLAB - path invalid")
            return False
    
    def detect_matlab(self):
        """Try to auto-detect MATLAB installation"""
        # Common paths for different OS
        paths = []
        
        if sys.platform == 'win32':
            program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
            paths = [
                os.path.join(program_files, 'MATLAB', 'R2023b', 'bin', 'matlab.exe'),
                os.path.join(program_files, 'MATLAB', 'R2023a', 'bin', 'matlab.exe'),
                os.path.join(program_files, 'MATLAB', 'R2022b', 'bin', 'matlab.exe')
            ]
        elif sys.platform == 'darwin':  # macOS
            paths = [
                '/Applications/MATLAB_R2023b.app/bin/matlab',
                '/Applications/MATLAB_R2023a.app/bin/matlab',
                '/Applications/MATLAB_R2022b.app/bin/matlab'
            ]
        else:  # Linux
            paths = [
                '/usr/local/MATLAB/R2023b/bin/matlab',
                '/usr/local/MATLAB/R2023a/bin/matlab',
                '/usr/local/MATLAB/R2022b/bin/matlab'
            ]
        
        for path in paths:
            if os.path.exists(path):
                self.set_matlab_path(path)
                return True
        
        return False
    
    def generate_simulink_model(self, states, transitions, actions, output_dir):
        """Generate a Simulink model file (.slx) from the state machine"""
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected")
            return False
        
        # Create a MATLAB script file to generate the Simulink model
        temp_dir = tempfile.mkdtemp()
        model_name = "BrainSimulatorModel"
        script_file = os.path.join(temp_dir, "create_model.m")
        output_model = os.path.join(output_dir, f"{model_name}.slx")
        
        # Write MATLAB script for model generation
        with open(script_file, 'w') as f:
            f.write(f"% Auto-generated Simulink model script\n")
            f.write(f"model_name = '{model_name}';\n")
            f.write(f"close_system(model_name, 0);\n")  # Close if already open
            f.write(f"new_system(model_name);\n")
            f.write(f"open_system(model_name);\n\n")
            
            # Add Stateflow chart
            f.write("sf = Stateflow.Chart(model_name);\n")
            f.write("sf.Name = 'State Machine';\n\n")
            
            # Add states
            for i, state in enumerate(states):
                f.write(f"s{i} = Stateflow.State(sf);\n")
                f.write(f"s{i}.Name = '{state['name']}';\n")
                f.write(f"s{i}.Position = [{state['x']}, {state['y']}, 100, 50];\n")
                if state.get('is_initial', False):
                    f.write(f"s{i}.isInitialState = true;\n")
            
            # Add transitions
            for i, trans in enumerate(transitions):
                src_idx = next((idx for idx, s in enumerate(states) if s['name'] == trans['source']), None)
                dst_idx = next((idx for idx, s in enumerate(states) if s['name'] == trans['target']), None)
                
                if src_idx is not None and dst_idx is not None:
                    f.write(f"t{i} = Stateflow.Transition(sf);\n")
                    f.write(f"t{i}.Source = s{src_idx};\n")
                    f.write(f"t{i}.Destination = s{dst_idx};\n")
                    if trans.get('label'):
                        f.write(f"t{i}.LabelString = '{trans['label']}';\n")
            
            # Save the model
            f.write(f"\n% Save the model\n")
            f.write(f"save_system(model_name, '{output_model}');\n")
            f.write(f"disp('Model saved to {output_model}');\n")
            f.write(f"close_system(model_name, 0);\n")
        
        # Run the MATLAB script
        try:
            cmd = [self.matlab_path, "-batch", f"run('{script_file}')"]
            subprocess.run(cmd, check=True)
            return output_model
        except subprocess.CalledProcessError as e:
            self.simulationFinished.emit(False, f"MATLAB error: {str(e)}")
            return None
    
    def run_simulation(self, model_path, sim_time=10):
        """Run a simulation using the generated Simulink model"""
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected")
            return False
        
        if not os.path.exists(model_path):
            self.simulationFinished.emit(False, f"Model file not found: {model_path}")
            return False
        
        # Create a MATLAB script to run the simulation
        temp_dir = tempfile.mkdtemp()
        script_file = os.path.join(temp_dir, "run_sim.m")
        model_name = os.path.splitext(os.path.basename(model_path))[0]
        
        with open(script_file, 'w') as f:
            f.write(f"% Auto-generated simulation script\n")
            f.write(f"model_path = '{model_path}';\n")
            f.write(f"open_system(model_path);\n")
            f.write(f"set_param('{model_name}', 'StopTime', '{sim_time}');\n")
            f.write(f"try\n")
            f.write(f"    sim('{model_name}');\n")
            f.write(f"    disp('Simulation completed successfully');\n")
            f.write(f"    result = true;\n")
            f.write(f"catch e\n")
            f.write(f"    disp(['Simulation error: ', e.message]);\n")
            f.write(f"    result = false;\n")
            f.write(f"end\n")
            f.write(f"close_system('{model_name}', 0);\n")
            f.write(f"quit(~result);\n")  # Exit with status code
        
        # Run the simulation in a separate thread
        self.simulation_thread = QThread()
        self.simulation_worker = MatlabSimulationWorker(self.matlab_path, script_file)
        self.simulation_worker.moveToThread(self.simulation_thread)
        self.simulation_thread.started.connect(self.simulation_worker.run_simulation)
        self.simulation_worker.finished.connect(self.simulation_thread.quit)
        self.simulation_worker.finished.connect(self.simulation_finished_handler)
        self.simulation_thread.start()
        
        return True
    
    def simulation_finished_handler(self, success, message):
        """Handle simulation completion"""
        self.simulationFinished.emit(success, message)
    
    def generate_code(self, model_path, language="C++", output_dir=None):
        """Generate code from Simulink model"""
        if not self.connected:
            self.codeGenerationFinished.emit(False, "MATLAB not connected", "")
            return False
        
        if not output_dir:
            output_dir = os.path.dirname(model_path)
        
        model_name = os.path.splitext(os.path.basename(model_path))[0]
        
        # Create a MATLAB script for code generation
        temp_dir = tempfile.mkdtemp()
        script_file = os.path.join(temp_dir, "generate_code.m")
        
        with open(script_file, 'w') as f:
            f.write(f"% Auto-generated code generation script\n")
            f.write(f"model_path = '{model_path}';\n")
            f.write(f"open_system(model_path);\n")
            
            # Configure code generation settings
            f.write(f"cfg = coder.config('lib');\n")
            
            if language.lower() == "c++":
                f.write(f"cfg.TargetLang = 'C++';\n")
            else:
                f.write(f"cfg.TargetLang = 'C';\n")
            
            f.write(f"cfg.GenCodeOnly = true;\n")
            f.write(f"cfg.GenerateReport = true;\n")
            f.write(f"cfg.GenerateTestModel = true;\n")
            
            # Run code generation
            f.write(f"try\n")
            f.write(f"    cd('{output_dir}');\n")
            f.write(f"    rtwbuild('{model_name}');\n")
            f.write(f"    disp('Code generation completed successfully');\n")
            f.write(f"    code_dir = fullfile('{output_dir}', '{model_name}_ert_rtw');\n")
            f.write(f"    disp(['Code generated in: ', code_dir]);\n")
            f.write(f"    result = true;\n")
            f.write(f"catch e\n")
            f.write(f"    disp(['Code generation error: ', e.message]);\n")
            f.write(f"    code_dir = '';\n")
            f.write(f"    result = false;\n")
            f.write(f"end\n")
            
            f.write(f"close_system('{model_name}', 0);\n")
            f.write(f"if result\n")
            f.write(f"    quit(0, code_dir);\n")
            f.write(f"else\n")
            f.write(f"    quit(1);\n")
            f.write(f"end\n")
        
        # Run code generation in a separate thread
        self.codegen_thread = QThread()
        self.codegen_worker = MatlabCodegenWorker(self.matlab_path, script_file)
        self.codegen_worker.moveToThread(self.codegen_thread)
        self.codegen_thread.started.connect(self.codegen_worker.run_codegen)
        self.codegen_worker.finished.connect(self.codegen_thread.quit)
        self.codegen_worker.finished.connect(self.codegen_finished_handler)
        self.codegen_thread.start()
        
        return True
    
    def codegen_finished_handler(self, success, message, output_dir):
        """Handle code generation completion"""
        self.codeGenerationFinished.emit(success, message, output_dir)

class MatlabSimulationWorker(QObject):
    """Worker for running MATLAB simulation in a separate thread"""
    finished = pyqtSignal(bool, str)
    
    def __init__(self, matlab_path, script_file):
        super().__init__()
        self.matlab_path = matlab_path
        self.script_file = script_file
        
    def run_simulation(self):
        """Run the MATLAB simulation"""
        try:
            cmd = [self.matlab_path, "-batch", f"run('{self.script_file}')"]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.finished.emit(True, "Simulation completed successfully")
        except subprocess.CalledProcessError as e:
            error_msg = e.stdout if e.stdout else str(e)
            self.finished.emit(False, f"Simulation failed: {error_msg}")

class MatlabCodegenWorker(QObject):
    """Worker for running MATLAB code generation in a separate thread"""
    finished = pyqtSignal(bool, str, str)
    
    def __init__(self, matlab_path, script_file):
        super().__init__()
        self.matlab_path = matlab_path
        self.script_file = script_file
        
    def run_codegen(self):
        """Run the MATLAB code generation"""
        try:
            cmd = [self.matlab_path, "-batch", f"run('{self.script_file}')"]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Parse output to find the generated code directory
            output = result.stdout
            output_dir = ""
            
            for line in output.splitlines():
                if "Code generated in:" in line:
                    output_dir = line.split("Code generated in:")[1].strip()
                    break
            
            self.finished.emit(True, "Code generation completed successfully", output_dir)
        except subprocess.CalledProcessError as e:
            error_msg = e.stdout if e.stdout else str(e)
            self.finished.emit(False, f"Code generation failed: {error_msg}", "")

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

class SimulinkTool(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(100, 40)
        self.setStyleSheet("background-color: lightpink; border-radius: 5px;")
        
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
        mime_data.setData("application/x-simulink", b"simulink")
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
        
        # Draw initial state indicator (small circle)
        if self.is_initial:
            painter.setBrush(Qt.black)
            painter.drawEllipse(self.rect().left() - 15, self.rect().center().y() - 5, 10, 10)
        
        # Draw final state indicator (double border)
        if self.is_final:
            painter.setPen(QPen(Qt.black, 2))
            painter.setBrush(Qt.NoBrush)
            smaller_rect = self.rect().adjusted(5, 5, -5, -5)
            painter.drawRect(smaller_rect)
        
        # If selected, draw a highlight
        if self.isSelected():
            painter.setPen(QPen(Qt.blue, 2, Qt.DashLine))
            painter.drawRect(self.rect())
    
    def get_data(self):
        """Get state data for serialization or MATLAB export"""
        return {
            'name': self.text,
            'x': self.x(),
            'y': self.y(),
            'is_initial': self.is_initial,
            'is_final': self.is_final
        }

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
    
    def get_data(self):
        """Get transition data for serialization or MATLAB export"""
        return {
            'source': self.start_item.text,
            'target': self.end_item.text,
            'label': self.text
        }

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
    
    def get_data(self):
        """Get action data for serialization or MATLAB export"""
        return {
            'name': self.text,
            'x': self.x(),
            'y': self.y()
        }

class GraphicsSimulinkItem(QGraphicsRectItem):
    def __init__(self, x, y, text, block_type="Subsystem"):
        super().__init__(x, y, 100, 50)
        self.text = text
        self.block_type = block_type
        self.setPen(QPen(Qt.black, 2))
        self.setBrush(QBrush(QColor(255, 200, 200)))  # Light pink
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        
        # Draw text and block type
        painter.setPen(Qt.black)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        
        text_rect = QRectF(self.rect().x(), self.rect().y(), self.rect().width(), self.rect().height() * 0.6)
        painter.drawText(text_rect, Qt.AlignCenter, self.text)
        
        font.setBold(False)
        font.setItalic(True)
        painter.setFont(font)
        
        type_rect = QRectF(self.rect().x(), self.rect().y() + self.rect().height() * 0.6, 
                          self.rect().width(), self.rect().height() * 0.4)
        painter.drawText(type_rect, Qt.AlignCenter, self.block_type)
        
        # If selected, draw a highlight
        if self.isSelected():
            painter.setPen(QPen(Qt.blue, 2, Qt.DashLine))
            painter.drawRect(self.rect())
    
    def get_data(self):
        """Get Simulink block data for serialization or MATLAB export"""
        return {
            'name': self.text,
            'type': self.block_type,
            'x': self.x(),
            'y': self.y()
        }

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
                state_dialog = StatePropertiesDialog(text)
                if state_dialog.exec_() == QDialog.Accepted:
                    state = GraphicsStateItem(
                        event.scenePos().x(), 
                        event.scenePos().y(), 
                        text,
                        state_dialog.is_initial.isChecked(),
                        state_dialog.is_final.isChecked()
                    )
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
                
        elif self.mode == "simulink" and event.button() == Qt.LeftButton:
            text, ok = QInputDialog.getText(None, "Simulink Block", "Enter block name:")
            if ok and text:
                block_dialog = SimulinkBlockDialog(text)
                if block_dialog.exec_() == QDialog.Accepted:
                    block = GraphicsSimulinkItem(
                        event.scenePos().x(), 
                        event.scenePos().y(), 
                        text,
                        block_dialog.block_type.currentText()
                    )
                    self.addItem(block)
                    if self.log_function:
                        self.log_function(f"Added Simulink block: {text} ({block_dialog.block_type.currentText()})")
            self.set_mode("select")
            return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key_Delete:
            for item in self.selectedItems():
                if self.log_function:
                    if isinstance(item, GraphicsStateItem):
                        self.log_function(f"Deleted state: {item.text}")
                    elif isinstance(item, GraphicsTransitionItem):
                        self.log_function(f"Deleted transition: {item.text}")
                    elif isinstance(item, GraphicsActionItem):
                        self.log_function(f"Deleted action: {item.text}")
                    elif isinstance(item, GraphicsSimulinkItem):
                        self.log_function(f"Deleted Simulink block: {item.text}")
                self.removeItem(item)
        super().keyPressEvent(event)
    
    def get_states(self):
        """Get all states in the scene"""
        return [item for item in self.items() if isinstance(item, GraphicsStateItem)]
    
    def get_transitions(self):
        """Get all transitions in the scene"""
        return [item for item in self.items() if isinstance(item, GraphicsTransitionItem)]
    
    def get_actions(self):
        """Get all actions in the scene"""
        return [item for item in self.items() if isinstance(item, GraphicsActionItem)]
    
    def get_simulink_blocks(self):
        """Get all Simulink blocks in the scene"""
        return [item for item in self.items() if isinstance(item, GraphicsSimulinkItem)]
    
    def clear_selection(self):
        """Clear all selected items"""
        for item in self.selectedItems():
            item.setSelected(False)
    
    def select_all(self):
        """Select all items in the scene"""
        for item in self.items():
            item.setSelected(True)
    
    def export_data(self):
        """Export scene data for serialization or MATLAB export"""
        data = {
            'states': [state.get_data() for state in self.get_states()],
            'transitions': [trans.get_data() for trans in self.get_transitions()],
            'actions': [action.get_data() for action in self.get_actions()],
            'simulink_blocks': [block.get_data() for block in self.get_simulink_blocks()]
        }
        return data

class StatePropertiesDialog(QDialog):
    """Dialog for configuring state properties"""
    def __init__(self, state_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        
        layout = QFormLayout()
        
        self.state_name = QLineEdit(state_name)
        layout.addRow("State Name:", self.state_name)
        
        self.is_initial = QCheckBox()
        layout.addRow("Initial State:", self.is_initial)
        
        self.is_final = QCheckBox()
        layout.addRow("Final State:", self.is_final)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)

class SimulinkBlockDialog(QDialog):
    """Dialog for configuring Simulink block properties"""
    def __init__(self, block_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Simulink Block Properties")
        
        layout = QFormLayout()
        
        self.block_name = QLineEdit(block_name)
        layout.addRow("Block Name:", self.block_name)
        
        self.block_type = QComboBox()
        self.block_type.addItems(["Subsystem", "Function", "Integrator", "Gain", "Sum", "Product", 
                                 "Constant", "Display", "Scope", "Saturation", "Switch"])
        layout.addRow("Block Type:", self.block_type)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)

class TransitionPropertiesDialog(QDialog):
    """Dialog for configuring transition properties"""
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        
        layout = QFormLayout()
        
        self.label = QLineEdit(label)
        layout.addRow("Label:", self.label)
        
        self.priority = QSpinBox()
        self.priority.setMinimum(1)
        self.priority.setMaximum(100)
        layout.addRow("Priority:", self.priority)
        
        self.has_condition = QCheckBox()
        layout.addRow("Has Condition:", self.has_condition)
        
        self.condition = QLineEdit()
        layout.addRow("Condition:", self.condition)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)

class ActionPropertiesDialog(QDialog):
    """Dialog for configuring action properties"""
    def __init__(self, action_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Action Properties")
        
        layout = QFormLayout()
        
        self.action_name = QLineEdit(action_name)
        layout.addRow("Action Name:", self.action_name)
        
        self.action_type = QComboBox()
        self.action_type.addItems(["Entry", "Exit", "During", "On Event"])
        layout.addRow("Action Type:", self.action_type)
        
        self.code = QTextEdit()
        layout.addRow("Code:", self.code)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Brain State Machine Designer")
        self.setGeometry(100, 100, 1200, 800)
        
        self.init_ui()
        self.matlab_connection = MatlabConnection()
        self.current_file = None
        
    def init_ui(self):
        """Initialize the user interface"""
        self.create_actions()
        self.create_menus()
        self.create_toolbars()
        self.create_status_bar()
        self.create_dock_widgets()
        self.create_central_widget()
        
    def create_actions(self):
        """Create application actions"""
        # File actions
        self.new_action = QAction("&New", self, shortcut="Ctrl+N", triggered=self.new_file)
        self.open_action = QAction("&Open", self, shortcut="Ctrl+O", triggered=self.open_file)
        self.save_action = QAction("&Save", self, shortcut="Ctrl+S", triggered=self.save_file)
        self.save_as_action = QAction("Save &As...", self, shortcut="Ctrl+Shift+S", triggered=self.save_file_as)
        self.export_action = QAction("&Export to MATLAB", self, triggered=self.export_to_matlab)
        self.exit_action = QAction("E&xit", self, shortcut="Ctrl+Q", triggered=self.close)
        
        # Edit actions
        self.select_action = QAction("Select", self, checkable=True, checked=True, triggered=lambda: self.select_mode("select"))
        self.state_action = QAction("Add State", self, checkable=True, triggered=lambda: self.select_mode("state"))
        self.transition_action = QAction("Add Transition", self, checkable=True, triggered=lambda: self.select_mode("transition"))
        self.action_tool_action = QAction("Add Action", self, checkable=True, triggered=lambda: self.select_mode("action"))
        self.simulink_action = QAction("Add Simulink Block", self, checkable=True, triggered=lambda: self.select_mode("simulink"))
        self.delete_action = QAction("Delete Selected", self, shortcut="Delete", triggered=self.delete_selected)
        self.undo_action = QAction("Undo", self, shortcut="Ctrl+Z", triggered=self.undo)
        self.redo_action = QAction("Redo", self, shortcut="Ctrl+Y", triggered=self.redo)
        self.select_all_action = QAction("Select All", self, shortcut="Ctrl+A", triggered=self.select_all)
        
        # View actions
        self.zoom_in_action = QAction("Zoom In", self, shortcut="Ctrl++", triggered=self.zoom_in)
        self.zoom_out_action = QAction("Zoom Out", self, shortcut="Ctrl+-", triggered=self.zoom_out)
        self.zoom_reset_action = QAction("Reset Zoom", self, shortcut="Ctrl+0", triggered=self.zoom_reset)
        
        # Simulation actions
        self.run_simulation_action = QAction("Run Simulation", self, triggered=self.run_simulation)
        self.generate_code_action = QAction("Generate Code", self, triggered=self.generate_code)
        self.matlab_settings_action = QAction("MATLAB Settings", self, triggered=self.configure_matlab)
        
        # Help actions
        self.about_action = QAction("About", self, triggered=self.show_about)
        self.help_action = QAction("Help", self, shortcut="F1", triggered=self.show_help)
        
    def create_menus(self):
        """Create application menus"""
        # File menu
        self.file_menu = self.menuBar().addMenu("&File")
        self.file_menu.addAction(self.new_action)
        self.file_menu.addAction(self.open_action)
        self.file_menu.addAction(self.save_action)
        self.file_menu.addAction(self.save_as_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.export_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)
        
        # Edit menu
        self.edit_menu = self.menuBar().addMenu("&Edit")
        self.edit_menu.addAction(self.undo_action)
        self.edit_menu.addAction(self.redo_action)
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(self.select_all_action)
        self.edit_menu.addAction(self.delete_action)
        
        # View menu
        self.view_menu = self.menuBar().addMenu("&View")
        self.view_menu.addAction(self.zoom_in_action)
        self.view_menu.addAction(self.zoom_out_action)
        self.view_menu.addAction(self.zoom_reset_action)
        
        # Simulation menu
        self.simulation_menu = self.menuBar().addMenu("&Simulation")
        self.simulation_menu.addAction(self.run_simulation_action)
        self.simulation_menu.addAction(self.generate_code_action)
        self.simulation_menu.addSeparator()
        self.simulation_menu.addAction(self.matlab_settings_action)
        
        # Help menu
        self.help_menu = self.menuBar().addMenu("&Help")
        self.help_menu.addAction(self.help_action)
        self.help_menu.addAction(self.about_action)
        
    def create_toolbars(self):
        """Create application toolbars"""
        # File toolbar
        self.file_toolbar = self.addToolBar("File")
        self.file_toolbar.addAction(self.new_action)
        self.file_toolbar.addAction(self.open_action)
        self.file_toolbar.addAction(self.save_action)
        
        # Edit toolbar
        self.edit_toolbar = self.addToolBar("Edit")
        self.edit_toolbar.addAction(self.select_action)
        self.edit_toolbar.addAction(self.state_action)
        self.edit_toolbar.addAction(self.transition_action)
        self.edit_toolbar.addAction(self.action_tool_action)
        self.edit_toolbar.addAction(self.simulink_action)
        
        # Create action group for exclusive selection
        self.mode_group = QActionGroup(self)
        self.mode_group.addAction(self.select_action)
        self.mode_group.addAction(self.state_action)
        self.mode_group.addAction(self.transition_action)
        self.mode_group.addAction(self.action_tool_action)
        self.mode_group.addAction(self.simulink_action)
        
        # Simulation toolbar
        self.simulation_toolbar = self.addToolBar("Simulation")
        self.simulation_toolbar.addAction(self.run_simulation_action)
        self.simulation_toolbar.addAction(self.generate_code_action)
        
    def create_status_bar(self):
        """Create application status bar"""
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1)
        
        self.matlab_status = QLabel("MATLAB: Not Connected")
        self.status_bar.addPermanentWidget(self.matlab_status)
        
    def create_dock_widgets(self):
        """Create application dock widgets"""
        # Toolbox dock
        self.toolbox_dock = QDockWidget("Toolbox", self)
        self.toolbox_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        self.toolbox = QToolBox()
        
        # State components page
        state_widget = QWidget()
        state_layout = QVBoxLayout()
        
        self.state_node = StateNode("State")
        state_layout.addWidget(self.state_node)
        
        self.initial_state = StateNode("Initial State")
        state_layout.addWidget(self.initial_state)
        
        self.final_state = StateNode("Final State")
        state_layout.addWidget(self.final_state)
        
        state_layout.addStretch()
        state_widget.setLayout(state_layout)
        self.toolbox.addItem(state_widget, "States")
        
        # Transition components page
        transition_widget = QWidget()
        transition_layout = QVBoxLayout()
        
        self.transition_arrow = TransitionArrow("Transition")
        transition_layout.addWidget(self.transition_arrow)
        
        transition_layout.addStretch()
        transition_widget.setLayout(transition_layout)
        self.toolbox.addItem(transition_widget, "Transitions")
        
        # Action components page
        action_widget = QWidget()
        action_layout = QVBoxLayout()
        
        self.entry_action = ActionTool("Entry Action")
        action_layout.addWidget(self.entry_action)
        
        self.exit_action_tool = ActionTool("Exit Action")
        action_layout.addWidget(self.exit_action_tool)
        
        self.during_action = ActionTool("During Action")
        action_layout.addWidget(self.during_action)
        
        action_layout.addStretch()
        action_widget.setLayout(action_layout)
        self.toolbox.addItem(action_widget, "Actions")
        
        # Simulink components page
        simulink_widget = QWidget()
        simulink_layout = QVBoxLayout()
        
        self.subsystem_block = SimulinkTool("Subsystem")
        simulink_layout.addWidget(self.subsystem_block)
        
        self.function_block = SimulinkTool("Function")
        simulink_layout.addWidget(self.function_block)
        
        self.integrator_block = SimulinkTool("Integrator")
        simulink_layout.addWidget(self.integrator_block)
        
        simulink_layout.addStretch()
        simulink_widget.setLayout(simulink_layout)
        self.toolbox.addItem(simulink_widget, "Simulink")
        
        self.toolbox_dock.setWidget(self.toolbox)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.toolbox_dock)
        
        # Properties dock
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        
        self.properties_widget = QWidget()
        self.properties_layout = QFormLayout()
        self.properties_widget.setLayout(self.properties_layout)
        
        self.properties_dock.setWidget(self.properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        
        # Log dock
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        self.log_dock.setWidget(self.log_text)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        
    def create_central_widget(self):
        """Create the central widget (diagram view)"""
        central_widget = QWidget()
        layout = QVBoxLayout()
        
        self.scene = DiagramScene(self)
        self.scene.set_log_function(self.log_message)
        
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setAcceptDrops(True)
        
        layout.addWidget(self.view)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
    def select_mode(self, mode):
        """Set the current editing mode"""
        self.scene.set_mode(mode)
        self.log_message(f"Mode changed to: {mode}")
        
    def log_message(self, message):
        """Add a message to the log"""
        self.log_text.append(message)
        self.status_label.setText(message)
        
    def new_file(self):
        """Create a new file"""
        if self.maybe_save():
            self.scene.clear()
            self.current_file = None
            self.log_message("New file created")
            
    def open_file(self):
        """Open an existing file"""
        if self.maybe_save():
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open File", "", "Brain State Machine Files (*.bsm);;All Files (*)"
            )
            
            if file_path:
                self.load_file(file_path)
                
    def load_file(self, file_path):
        """Load a file from the given path"""
        try:
            import json
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            self.scene.clear()
            
            # Create states
            state_items = {}
            for state_data in data.get('states', []):
                state = GraphicsStateItem(
                    state_data['x'], 
                    state_data['y'], 
                    state_data['name'],
                    state_data.get('is_initial', False),
                    state_data.get('is_final', False)
                )
                self.scene.addItem(state)
                state_items[state_data['name']] = state
                
            # Create transitions
            for trans_data in data.get('transitions', []):
                if trans_data['source'] in state_items and trans_data['target'] in state_items:
                    transition = GraphicsTransitionItem(
                        state_items[trans_data['source']], 
                        state_items[trans_data['target']], 
                        trans_data.get('label', '')
                    )
                    self.scene.addItem(transition)
                    
            # Create actions
            for action_data in data.get('actions', []):
                action = GraphicsActionItem(
                    action_data['x'], 
                    action_data['y'], 
                    action_data['name']
                )
                self.scene.addItem(action)
                
            # Create Simulink blocks
            for block_data in data.get('simulink_blocks', []):
                block = GraphicsSimulinkItem(
                    block_data['x'], 
                    block_data['y'], 
                    block_data['name'],
                    block_data.get('type', 'Subsystem')
                )
                self.scene.addItem(block)
                
            self.current_file = file_path
            self.log_message(f"Loaded file: {file_path}")
            return True
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load file: {str(e)}")
            self.log_message(f"Error loading file: {str(e)}")
            return False
            
    def save_file(self):
        """Save the current file"""
        if self.current_file:
            return self.save_to_file(self.current_file)
        else:
            return self.save_file_as()
            
    def save_file_as(self):
        """Save the current file with a new name"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save File As", "", "Brain State Machine Files (*.bsm);;All Files (*)"
        )
        
        if file_path:
            if not file_path.endswith('.bsm'):
                file_path += '.bsm'
            return self.save_to_file(file_path)
        
        return False
            
    def save_to_file(self, file_path):
        """Save to the given file path"""
        try:
            import json
            data = self.scene.export_data()
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            self.current_file = file_path
            self.log_message(f"Saved to: {file_path}")
            return True
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save file: {str(e)}")
            self.log_message(f"Error saving file: {str(e)}")
            return False
            
    def maybe_save(self):
        """Ask to save if there are unsaved changes"""
        # For simplicity, always ask
        if self.scene.items():
            reply = QMessageBox.question(
                self, "Save Changes", 
                "There are unsaved changes. Do you want to save them?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                return self.save_file()
            elif reply == QMessageBox.Cancel:
                return False
        
        return True
            
    def export_to_matlab(self):
        """Export the current diagram to MATLAB"""
        if not self.matlab_connection.connected:
            if not self.configure_matlab():
                return
        
        # Get directory to save the model
        export_dir = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not export_dir:
            return
        
        # Get diagram data
        data = self.scene.export_data()
        
        # Generate model
        model_path = self.matlab_connection.generate_simulink_model(
            data['states'], data['transitions'], data['actions'], export_dir
        )
        
        if model_path:
            self.log_message(f"Model exported to: {model_path}")
        else:
            self.log_message("Failed to export model to MATLAB")
            
    def run_simulation(self):
        """Run a simulation using MATLAB"""
        if not self.matlab_connection.connected:
            if not self.configure_matlab():
                return
        
        # First save the model if not already saved
        if not self.current_file:
            if not self.save_file_as():
                return
        else:
            self.save_file()
        
        # Get directory to save the model
        export_dir = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not export_dir:
            return
        
        # Get diagram data
        data = self.scene.export_data()
        
        # Generate model
        self.log_message("Generating Simulink model...")
        model_path = self.matlab_connection.generate_simulink_model(
            data['states'], data['transitions'], data['actions'], export_dir
        )
        
        if model_path:
            self.log_message(f"Model generated at: {model_path}")
            
            # Run simulation
            self.log_message("Starting simulation...")
            self.matlab_connection.run_simulation(model_path)
        else:
            self.log_message("Failed to generate model for simulation")
            
    def generate_code(self):
        """Generate code from the model"""
        if not self.matlab_connection.connected:
            if not self.configure_matlab():
                return
        
        # First save the model if not already saved
        if not self.current_file:
            if not self.save_file_as():
                return
        else:
            self.save_file()
        
        # Get export directory
        export_dir = QFileDialog.getExistingDirectory(self, "Select Code Export Directory")
        if not export_dir:
            return
        
        # Get language
        language_dialog = QDialog(self)
        language_dialog.setWindowTitle("Select Target Language")
        layout = QVBoxLayout()
        
        language_combo = QComboBox()
        language_combo.addItems(["C", "C++"])
        layout.addWidget(QLabel("Target Language:"))
        layout.addWidget(language_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(language_dialog.accept)
        buttons.rejected.connect(language_dialog.reject)
        layout.addWidget(buttons)
        
        language_dialog.setLayout(layout)
        
        if language_dialog.exec_() != QDialog.Accepted:
            return
        
        language = language_combo.currentText()
        
        # Get diagram data
        data = self.scene.export_data()
        
        # Generate model first
        self.log_message(f"Generating Simulink model for {language} code generation...")
        model_path = self.matlab_connection.generate_simulink_model(
            data['states'], data['transitions'], data['actions'], export_dir
        )
        
        if model_path:
            self.log_message(f"Model generated at: {model_path}")
            
            # Generate code
            self.log_message(f"Starting {language} code generation...")
            self.matlab_connection.generate_code(model_path, language, export_dir)
        else:
            self.log_message("Failed to generate model for code generation")
            
    def configure_matlab(self):
        """Configure MATLAB connection"""
        dialog = QDialog(self)
        dialog.setWindowTitle("MATLAB Configuration")
        
        layout = QVBoxLayout()
        
        auto_detect = QPushButton("Auto-detect MATLAB")
        layout.addWidget(auto_detect)
        
        form_layout = QFormLayout()
        matlab_path = QLineEdit(self.matlab_connection.matlab_path)
        form_layout.addRow("MATLAB Executable Path:", matlab_path)
        layout.addLayout(form_layout)
        
        auto_detect.clicked.connect(lambda: self.auto_detect_matlab(matlab_path))
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(lambda: self.browse_matlab_path(matlab_path))
        form_layout.addRow("", browse_button)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            success = self.matlab_connection.set_matlab_path(matlab_path.text())
            if success:
                self.matlab_status.setText("MATLAB: Connected")
                self.log_message(f"MATLAB connection established: {matlab_path.text()}")
                return True
            else:
                self.matlab_status.setText("MATLAB: Not Connected")
                self.log_message("Failed to connect to MATLAB - path invalid")
                return False
        
        return False
            
    def auto_detect_matlab(self, text_field):
        """Auto-detect MATLAB installation"""
        if self.matlab_connection.detect_matlab():
            text_field.setText(self.matlab_connection.matlab_path)
            self.log_message(f"MATLAB detected at: {self.matlab_connection.matlab_path}")
        else:
            self.log_message("Could not auto-detect MATLAB installation")
    
    def browse_matlab_path(self, text_field):
        """Browse for MATLAB executable"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select MATLAB Executable", "", 
            "MATLAB Executable (matlab.exe);;All Files (*)" if sys.platform == 'win32' else "All Files (*)"
        )
        
        if file_path:
            text_field.setText(file_path)
            
    def delete_selected(self):
        """Delete selected items"""
        for item in self.scene.selectedItems():
            if isinstance(item, GraphicsStateItem):
                self.log_message(f"Deleted state: {item.text}")
            elif isinstance(item, GraphicsTransitionItem):
                self.log_message(f"Deleted transition: {item.text}")
            elif isinstance(item, GraphicsActionItem):
                self.log_message(f"Deleted action: {item.text}")
            elif isinstance(item, GraphicsSimulinkItem):
                self.log_message(f"Deleted Simulink block: {item.text}")
            self.scene.removeItem(item)
            
    def undo(self):
        """Undo last action"""
        # Placeholder for undo functionality
        self.log_message("Undo not implemented yet")
        
    def redo(self):
        """Redo last undone action"""
        # Placeholder for redo functionality
        self.log_message("Redo not implemented yet")
        
    def select_all(self):
        """Select all items in the scene"""
        self.scene.select_all()
        self.log_message("Selected all items")
        
    def zoom_in(self):
        """Zoom in on the diagram"""
        self.view.scale(1.2, 1.2)
        
    def zoom_out(self):
        """Zoom out of the diagram"""
        self.view.scale(1/1.2, 1/1.2)
        
    def zoom_reset(self):
        """Reset zoom to default"""
        self.view.resetTransform()
        
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About Brain State Machine Designer",
            """<h2>Brain State Machine Designer</h2>
            <p>A tool for designing brain state machines with MATLAB/Simulink integration.</p>
            <p>Version 1.0</p>"""
        )
        
    def show_help(self):
        """Show help dialog"""
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("Help")
        help_dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout()
        
        help_tabs = QTabWidget()
        
        # General tab
        general_tab = QWidget()
        general_layout = QVBoxLayout()
        general_text = QTextEdit()
        general_text.setReadOnly(True)
        general_text.setText("""
        <h2>General Usage</h2>
        <p>This application allows you to design brain state machines and export them to MATLAB/Simulink.</p>
        
        <h3>Basic Workflow</h3>
        <ol>
            <li>Add states and transitions to the diagram</li>
            <li>Configure properties of states and transitions</li>
            <li>Save your work</li>
            <li>Export to MATLAB for simulation or code generation</li>
        </ol>
        
        <h3>User Interface</h3>
        <p>The main window is divided into several areas:</p>
        <ul>
            <li><b>Central Canvas:</b> Where you create your state machine</li>
            <li><b>Toolbox:</b> Contains components you can add to your diagram</li>
            <li><b>Properties Panel:</b> Shows properties of selected items</li>
            <li><b>Log Panel:</b> Shows information about actions and events</li>
        </ul>
        """)
        general_layout.addWidget(general_text)
        general_tab.setLayout(general_layout)
        help_tabs.addTab(general_tab, "General")
        
        # States tab
        states_tab = QWidget()
        states_layout = QVBoxLayout()
        states_text = QTextEdit()
        states_text.setReadOnly(True)
        states_text.setText("""
        <h2>Working with States</h2>
        
        <h3>Adding States</h3>
        <p>You can add states in two ways:</p>
        <ul>
            <li>Select the "Add State" tool and click on the canvas</li>
            <li>Drag and drop a state from the toolbox to the canvas</li>
        </ul>
        
        <h3>State Types</h3>
        <ul>
            <li><b>Regular State:</b> Basic state in the state machine</li>
            <li><b>Initial State:</b> The state where execution begins</li>
            <li><b>Final State:</b> A terminal state where execution may end</li>
        </ul>
        
        <h3>State Properties</h3>
        <p>States have the following properties:</p>
        <ul>
            <li><b>Name:</b> Unique identifier for the state</li>
            <li><b>Position:</b> Location in the diagram</li>
            <li><b>Initial State:</b> Whether this is an initial state</li>
            <li><b>Final State:</b> Whether this is a final state</li>
        </ul>
        """)
        states_layout.addWidget(states_text)
        states_tab.setLayout(states_layout)
        help_tabs.addTab(states_tab, "States")
        
        # Transitions tab
        transitions_tab = QWidget()
        transitions_layout = QVBoxLayout()
        transitions_text = QTextEdit()
        transitions_text.setReadOnly(True)
        transitions_text.setText("""
        <h2>Working with Transitions</h2>
        
        <h3>Adding Transitions</h3>
        <p>To add a transition between states:</p>
        <ol>
            <li>Select the "Add Transition" tool</li>
            <li>Click on the source state</li>
            <li>Click on the target state</li>
            <li>Enter the transition label when prompted</li>
        </ol>
        
        <h3>Transition Properties</h3>
        <p>Transitions have the following properties:</p>
        <ul>
            <li><b>Source:</b> The state where the transition starts</li>
            <li><b>Target:</b> The state where the transition ends</li>
            <li><b>Label:</b> Text describing the transition condition</li>
            <li><b>Priority:</b> Order of evaluation when multiple transitions are possible</li>
        </ul>
        """)
        transitions_layout.addWidget(transitions_text)
        transitions_tab.setLayout(transitions_layout)
        help_tabs.addTab(transitions_tab, "Transitions")
        
        # MATLAB tab
        matlab_tab = QWidget()
        matlab_layout = QVBoxLayout()
        matlab_text = QTextEdit()
        matlab_text.setReadOnly(True)
        matlab_text.setText("""
        <h2>MATLAB Integration</h2>
        
        <h3>Configuring MATLAB</h3>
        <p>Before using MATLAB features, you need to configure the MATLAB connection:</p>
        <ol>
            <li>Go to Simulation > MATLAB Settings</li>
            <li>Use auto-detect or manually select your MATLAB executable</li>
            <li>Click OK to establish the connection</li>
        </ol>
        
        <h3>Exporting to MATLAB</h3>
        <p>To export your state machine to MATLAB/Simulink:</p>
        <ol>
            <li>Go to File > Export to MATLAB</li>
            <li>Select a directory to save the model</li>
            <li>The application will generate a Simulink model (.slx file)</li>
        </ol>
        
        <h3>Running Simulations</h3>
        <p>To run a simulation of your state machine:</p>
        <ol>
            <li>Go to Simulation > Run Simulation</li>
            <li>Select a directory for simulation output</li>
            <li>The application will generate a model and run it in Simulink</li>
        </ol>
        
        <h3>Generating Code</h3>
        <p>To generate code from your state machine:</p>
        <ol>
            <li>Go to Simulation > Generate Code</li>
            <li>Select the target language (C or C++)</li>
            <li>Select a directory for code output</li>
            <li>The application will generate code using MATLAB Coder</li>
        </ol>
        """)
        matlab_layout.addWidget(matlab_text)
        matlab_tab.setLayout(matlab_layout)
        help_tabs.addTab(matlab_tab, "MATLAB")
        
        layout.addWidget(help_tabs)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(help_dialog.accept)
        layout.addWidget(close_button)
        
        help_dialog.setLayout(layout)
        help_dialog.exec_()
    
    def closeEvent(self, event):
        """Handle application close event"""
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()


class MatlabSettingsDialog(QDialog):
    """Dialog for MATLAB settings"""
    def __init__(self, matlab_connection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # MATLAB path section
        path_group = QGroupBox("MATLAB Executable")
        path_layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        self.matlab_path = QLineEdit(self.matlab_connection.matlab_path)
        form_layout.addRow("Path:", self.matlab_path)
        path_layout.addLayout(form_layout)
        
        buttons_layout = QHBoxLayout()
        auto_detect = QPushButton("Auto-detect")
        browse_button = QPushButton("Browse...")
        buttons_layout.addWidget(auto_detect)
        buttons_layout.addWidget(browse_button)
        buttons_layout.addStretch()
        path_layout.addLayout(buttons_layout)
        
        auto_detect.clicked.connect(self.auto_detect_matlab)
        browse_button.clicked.connect(self.browse_matlab_path)
        
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)
        
        # Connection test section
        test_group = QGroupBox("Connection Test")
        test_layout = QVBoxLayout()
        
        test_button = QPushButton("Test Connection")
        test_button.clicked.connect(self.test_connection)
        test_layout.addWidget(test_button)
        
        self.test_result = QLabel("Connection status: Unknown")
        test_layout.addWidget(self.test_result)
        
        test_group.setLayout(test_layout)
        layout.addWidget(test_group)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
        
    def auto_detect_matlab(self):
        """Auto-detect MATLAB installation"""
        if self.matlab_connection.detect_matlab():
            self.matlab_path.setText(self.matlab_connection.matlab_path)
            self.test_result.setText("Connection status: MATLAB detected")
        else:
            self.test_result.setText("Connection status: Could not detect MATLAB")
    
    def browse_matlab_path(self):
        """Browse for MATLAB executable"""
        file_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select MATLAB Executable", "", file_filter
        )
        
        if file_path:
            self.matlab_path.setText(file_path)
    
    def test_connection(self):
        """Test the MATLAB connection"""
        path = self.matlab_path.text()
        if os.path.exists(path):
            try:
                # Simple test - just check if the executable exists and run a simple command
                temp_dir = tempfile.mkdtemp()
                test_script = os.path.join(temp_dir, "test.m")
                
                with open(test_script, 'w') as f:
                    f.write("disp('MATLAB connection test successful');\n")
                
                cmd = [path, "-batch", f"run('{test_script}')"]
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                
                if "successful" in result.stdout:
                    self.test_result.setText("Connection status: Success")
                    return True
                else:
                    self.test_result.setText("Connection status: Failed (unexpected output)")
                    return False
                    
            except Exception as e:
                self.test_result.setText(f"Connection status: Failed ({str(e)})")
                return False
        else:
            self.test_result.setText("Connection status: Failed (invalid path)")
            return False


class ExportOptionsDialog(QDialog):
    """Dialog for export options"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Options")
        
        layout = QVBoxLayout()
        
        # Model options
        model_group = QGroupBox("Model Options")
        model_layout = QFormLayout()
        
        self.model_name = QLineEdit("BrainStateMachine")
        model_layout.addRow("Model Name:", self.model_name)
        
        self.include_actions = QCheckBox()
        self.include_actions.setChecked(True)
        model_layout.addRow("Include Actions:", self.include_actions)
        
        self.include_simulink = QCheckBox()
        self.include_simulink.setChecked(True)
        model_layout.addRow("Include Simulink Blocks:", self.include_simulink)
        
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)
        
        # Simulation options
        sim_group = QGroupBox("Simulation Options")
        sim_layout = QFormLayout()
        
        self.sim_time = QSpinBox()
        self.sim_time.setMinimum(1)
        self.sim_time.setMaximum(3600)
        self.sim_time.setValue(10)
        sim_layout.addRow("Simulation Time (s):", self.sim_time)
        
        self.sim_solver = QComboBox()
        self.sim_solver.addItems(["FixedStep", "VariableStep"])
        sim_layout.addRow("Solver Type:", self.sim_solver)
        
        sim_group.setLayout(sim_layout)
        layout.addWidget(sim_group)
        
        # Code generation options
        code_group = QGroupBox("Code Generation Options")
        code_layout = QFormLayout()
        
        self.target_lang = QComboBox()
        self.target_lang.addItems(["C", "C++"])
        code_layout.addRow("Target Language:", self.target_lang)
        
        self.gen_test = QCheckBox()
        self.gen_test.setChecked(True)
        code_layout.addRow("Generate Test Harness:", self.gen_test)
        
        code_group.setLayout(code_layout)
        layout.addWidget(code_group)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()