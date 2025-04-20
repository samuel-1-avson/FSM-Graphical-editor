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
                             QFileDialog, QProgressBar, QTabWidget, QCheckBox, QGroupBox)
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