import sys
import os
import tempfile
import subprocess
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QToolBox, QAction,
    QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
    QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
    QFileDialog, QProgressBar, QTabWidget, QCheckBox, QActionGroup, QGraphicsItem,
    QGroupBox, QUndoStack, QUndoCommand
)
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir
)

# --- Configuration ---
APP_VERSION = "1.1"
FILE_EXTENSION = ".bsm"
FILE_FILTER = f"Brain State Machine Files (*{FILE_EXTENSION});;All Files (*)"

# --- Utility Functions ---
def get_standard_icon(standard_pixmap):
    return QApplication.style().standardIcon(standard_pixmap)

# --- MATLAB Connection Handling ---
class MatlabConnection(QObject):
    """Class to handle MATLAB connectivity"""
    connectionStatusChanged = pyqtSignal(bool, str)  # success, message
    simulationFinished = pyqtSignal(bool, str)      # success, message
    codeGenerationFinished = pyqtSignal(bool, str, str)  # success, message, output_dir

    def __init__(self):
        super().__init__()
        self.matlab_path = ""
        self.connected = False

    def set_matlab_path(self, path):
        """Set the path to MATLAB executable and test basic validity."""
        self.matlab_path = path
        if path and os.path.exists(path) and (os.access(path, os.X_OK) or path.endswith('.exe')): # Basic check
            self.connected = True
            self.connectionStatusChanged.emit(True, f"MATLAB path set: {path}")
            return True
        else:
            self.connected = False
            self.matlab_path = ""
            self.connectionStatusChanged.emit(False, "MATLAB path is invalid or not executable.")
            return False

    def test_connection(self):
        """Actively test MATLAB connection by running a simple command."""
        if not self.connected or not self.matlab_path:
            self.connectionStatusChanged.emit(False, "MATLAB path not set.")
            return False

        try:
            process = subprocess.run(
                [self.matlab_path, "-batch", "disp('MATLAB_CONNECTION_TEST_SUCCESS')"],
                capture_output=True, text=True, timeout=15, check=True
            )
            if "MATLAB_CONNECTION_TEST_SUCCESS" in process.stdout:
                self.connectionStatusChanged.emit(True, "MATLAB connection successful.")
                return True
            else:
                self.connected = False # Downgrade status if test fails
                error_msg = process.stderr or "Unexpected output from MATLAB."
                self.connectionStatusChanged.emit(False, f"MATLAB connection test failed: {error_msg}")
                return False
        except subprocess.TimeoutExpired:
            self.connected = False
            self.connectionStatusChanged.emit(False, "MATLAB connection test timed out.")
            return False
        except subprocess.CalledProcessError as e:
            self.connected = False
            self.connectionStatusChanged.emit(False, f"MATLAB error during test: {e.stderr or e.stdout or str(e)}")
            return False
        except FileNotFoundError:
            self.connected = False
            self.connectionStatusChanged.emit(False, "MATLAB executable not found at the specified path.")
            return False
        except Exception as e:
            self.connected = False
            self.connectionStatusChanged.emit(False, f"An unexpected error occurred during MATLAB test: {str(e)}")
            return False


    def detect_matlab(self):
        """Try to auto-detect MATLAB installation."""
        paths = []
        if sys.platform == 'win32':
            program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
            versions = ['R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b'] # Add more versions
            for v in versions:
                paths.append(os.path.join(program_files, 'MATLAB', v, 'bin', 'matlab.exe'))
        elif sys.platform == 'darwin':  # macOS
            versions = ['R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b']
            for v in versions:
                paths.append(f'/Applications/MATLAB_{v}.app/bin/matlab')
        else:  # Linux
            versions = ['R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b']
            for v in versions:
                paths.append(f'/usr/local/MATLAB/{v}/bin/matlab')

        for path in paths:
            if os.path.exists(path):
                self.set_matlab_path(path) # This will emit connectionStatusChanged
                return True
        self.connectionStatusChanged.emit(False, "MATLAB auto-detection failed.")
        return False

    def _run_matlab_script(self, script_content, worker_signal, success_message_prefix):
        if not self.connected:
            worker_signal.emit(False, "MATLAB not connected.", "") # Ensure 3 args for codegen
            return

        temp_dir = tempfile.mkdtemp()
        script_file = os.path.join(temp_dir, "matlab_script.m")
        with open(script_file, 'w') as f:
            f.write(script_content)

        worker = MatlabCommandWorker(self.matlab_path, script_file, worker_signal, success_message_prefix)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run_command)
        worker.finished_signal.connect(thread.quit)
        worker.finished_signal.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        # Keep a reference to the thread to prevent premature garbage collection if needed
        # For now, Qt's parent-child relationship or signal-slot might keep it alive.
        # Or, self.active_thread = thread

    def generate_simulink_model(self, states, transitions, actions_data, output_dir, model_name="BrainStateMachine"):
        """Generate a Simulink model file (.slx) from the state machine."""
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected.") # Using sim finished for general model gen
            return False

        slx_file_path = os.path.join(output_dir, f"{model_name}.slx").replace('\\', '/')

        script_lines = [
            f"% Auto-generated Simulink model script for {model_name}",
            f"disp('Starting Simulink model generation...');",
            f"modelName = '{model_name}';",
            f"outputModelPath = '{slx_file_path}';",
            "if exist(outputModelPath, 'file'), delete(outputModelPath); end", # Ensure clean slate
            "if bdIsLoaded(modelName), close_system(modelName, 0); end",
            "new_system(modelName);",
            "open_system(modelName);",
            "sfChart = Stateflow.Chart(modelName);",
            "sfChart.Name = 'BrainStateMachineChart';",
            "stateHandles = struct();"
        ]

        for i, state in enumerate(states):
            s_name_matlab = state['name'].replace("'", "''") # Escape single quotes for MATLAB strings
            s_id = f"s{i}"
            script_lines.extend([
                f"{s_id} = Stateflow.State(sfChart);",
                f"{s_id}.Name = '{s_name_matlab}';",
                # Adjust position and size as needed
                f"{s_id}.Position = [{state['x']}, {state['y']}, 120, 60];",
                f"stateHandles.('{s_name_matlab}') = {s_id};"
            ])
            if state.get('is_initial', False):
                script_lines.append(f"sfChart.defaultTransition = Stateflow.Transition(sfChart);")
                script_lines.append(f"sfChart.defaultTransition.Destination = {s_id};")


        for i, trans in enumerate(transitions):
            src_name_matlab = trans['source'].replace("'", "''")
            dst_name_matlab = trans['target'].replace("'", "''")
            t_label_matlab = trans['label'].replace("'", "''") if trans.get('label') else ''
            
            script_lines.extend([
                f"t{i} = Stateflow.Transition(sfChart);",
                f"t{i}.Source = stateHandles.('{src_name_matlab}');",
                f"t{i}.Destination = stateHandles.('{dst_name_matlab}');"
            ])
            if t_label_matlab:
                script_lines.append(f"t{i}.LabelString = '{t_label_matlab}';")

        script_lines.extend([
            "disp(['Attempting to save model to: ', outputModelPath]);",
            "save_system(modelName, outputModelPath);",
            "close_system(modelName, 0);",
            "disp(['Simulink model saved to: ', outputModelPath]);",
            "fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', outputModelPath);" # For worker to parse path
        ])
        
        script_content = "\n".join(script_lines)
        self._run_matlab_script(script_content, self.simulationFinished, "Model generation") # Re-use simulationFinished
        return True # Indicates process started

    def run_simulation(self, model_path, sim_time=10):
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected.")
            return False
        if not os.path.exists(model_path):
            self.simulationFinished.emit(False, f"Model file not found: {model_path}")
            return False

        model_path_matlab = model_path.replace('\\', '/')
        model_name = os.path.splitext(os.path.basename(model_path))[0]

        script_content = f"""
        disp('Starting simulation...');
        modelPath = '{model_path_matlab}';
        modelName = '{model_name}';
        load_system(modelPath);
        set_param(modelName, 'StopTime', '{sim_time}');
        try
            simOut = sim(modelName);
            disp('Simulation completed successfully.');
            fprintf('MATLAB_SCRIPT_SUCCESS:Simulation finished.\\n');
        catch e
            disp(['Simulation error: ', e.message]);
            rethrow(e); % This will cause non-zero exit code if script run with -batch
        end
        close_system(modelName, 0);
        """
        self._run_matlab_script(script_content, self.simulationFinished, "Simulation")
        return True


    def generate_code(self, model_path, language="C++", output_dir_base=None):
        if not self.connected:
            self.codeGenerationFinished.emit(False, "MATLAB not connected", "")
            return False

        model_path_matlab = model_path.replace('\\', '/')
        model_name = os.path.splitext(os.path.basename(model_path))[0]
        
        if not output_dir_base:
            output_dir_base = os.path.dirname(model_path)
        output_dir_matlab = output_dir_base.replace('\\', '/')


        script_content = f"""
        disp('Starting code generation...');
        modelPath = '{model_path_matlab}';
        modelName = '{model_name}';
        outputDir = '{output_dir_matlab}';
        
        load_system(modelPath);
        
        % Set up configuration object for C/C++ code generation
        cfg = coder.config('rtwlib'); % For ERT-based targets, typically used for libraries/executables
        if strcmpi('{language}', 'C++')
            cfg.TargetLang = 'C++';
            disp('Configured for C++ code generation.');
        else
            cfg.TargetLang = 'C';
            disp('Configured for C code generation.');
        end
        cfg.GenerateReport = true;
        cfg.GenCodeOnly = true; % Only generate code, don't compile to an executable here

        % Specify the code generation folder
        % The actual code is usually placed in a subfolder like 'modelName_ert_rtw'
        codeGenFolder = fullfile(outputDir, [modelName '_codegen']);
        if ~exist(codeGenFolder, 'dir')
           mkdir(codeGenFolder);
        end
        
        current_folder = pwd;
        cd(codeGenFolder); % Change to output directory for codegen
        
        try
            % Generate code
            rtwbuild(modelName, ' rýchlejšie', 'off', ' ধরে রাখাBuildFolder', codeGenFolder, ' Config', cfg); % Use rtwbuild for ert
            disp('Code generation command executed.');
            
            % Determine the actual output directory (often a subfolder)
            % This is heuristic, exact path depends on codegen settings
            actualCodeDir = fullfile(codeGenFolder, [modelName '_ert_rtw']); % Common for ERT
            if ~exist(actualCodeDir, 'dir')
                actualCodeDir = codeGenFolder; % Fallback
            end

            disp(['Code generation successful. Code saved in: ', actualCodeDir]);
            fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', actualCodeDir); % For worker to parse path
        catch e
            disp(['Code generation error: ', e.message]);
            cd(current_folder); % Restore original directory
            rethrow(e);
        end
        cd(current_folder); % Restore original directory
        close_system(modelName, 0);
        """
        self._run_matlab_script(script_content, self.codeGenerationFinished, "Code generation")
        return True

class MatlabCommandWorker(QObject):
    """Worker for running a generic MATLAB script."""
    finished_signal = pyqtSignal(bool, str, str) # success, message, data (e.g. path)

    def __init__(self, matlab_path, script_file, original_signal, success_message_prefix):
        super().__init__()
        self.matlab_path = matlab_path
        self.script_file = script_file
        self.original_signal = original_signal # The signal to emit on final completion (e.g., simulationFinished)
        self.success_message_prefix = success_message_prefix

    def run_command(self):
        try:
            cmd = [self.matlab_path, "-batch", f"run('{self.script_file}')"]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False) # check=False to handle errors manually

            output_data = ""
            success = False

            if process.returncode == 0:
                # Check for our custom success marker
                if "MATLAB_SCRIPT_SUCCESS" in process.stdout:
                    success = True
                    # Try to parse output data if present
                    for line in process.stdout.splitlines():
                        if line.startswith("MATLAB_SCRIPT_SUCCESS:"):
                            output_data = line.split(":", 1)[1].strip()
                            break
                    message = f"{self.success_message_prefix} completed successfully."
                    if output_data:
                         message += f" Output: {output_data}"
                else: # MATLAB script ran but didn't produce expected success marker
                    success = False
                    message = f"{self.success_message_prefix} finished with unexpected MATLAB output: {process.stdout[:200]}"
                    if process.stderr:
                        message += f"\nMATLAB stderr: {process.stderr[:200]}"

            else: # Non-zero exit code from MATLAB
                success = False
                error_output = process.stderr or process.stdout # MATLAB often prints errors to stdout in -batch
                message = f"{self.success_message_prefix} failed. MATLAB Error: {error_output[:500]}"
            
            # Emit the original signal
            if len(self.original_signal.argumentTypes()) == 3: # e.g. codeGenerationFinished
                 self.original_signal.emit(success, message, output_data if success else "")
            else: # e.g. simulationFinished (bool, str)
                 self.original_signal.emit(success, message)


        except subprocess.TimeoutExpired:
            self.original_signal.emit(False, f"{self.success_message_prefix} timed out.", "")
        except FileNotFoundError:
             self.original_signal.emit(False, "MATLAB executable not found.", "")
        except Exception as e:
            self.original_signal.emit(False, f"{self.success_message_prefix} worker error: {str(e)}", "")
        finally:
            # Clean up temporary script file
            if os.path.exists(self.script_file):
                try:
                    os.remove(self.script_file)
                    os.rmdir(os.path.dirname(self.script_file)) # Remove temp dir
                except OSError:
                    pass # Log this if needed
            self.finished_signal.emit(True, "", "") # Internal signal for thread cleanup

# --- Draggable Toolbox Buttons ---
class DraggableToolButton(QPushButton):
    def __init__(self, text, mime_type, style_sheet, parent=None):
        super().__init__(text, parent)
        self.mime_type = mime_type
        self.setFixedSize(120, 40)
        self.setStyleSheet(style_sheet + " border-radius: 5px;")
        self.drag_start_position = QPoint()

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
        mime_data.setText(self.text())  # Store display text
        mime_data.setData(self.mime_type, b"1") # Generic data for type checking
        drag.setMimeData(mime_data)

        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())

        drag.exec_(Qt.CopyAction)


# --- Graphics Items ---
class GraphicsStateItem(QGraphicsRectItem):
    Type = QGraphicsItem.UserType + 1
    def type(self): return GraphicsStateItem.Type

    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False):
        super().__init__(x, y, w, h)
        self.text_label = text
        self.is_initial = is_initial
        self.is_final = is_final
        self._text_color = Qt.black
        self._font = QFont("Arial", 10)

        self.setPen(QPen(Qt.black, 2))
        self.setBrush(QBrush(QColor(173, 216, 230))) # lightblue
        self.setFlags(QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges) # For itemChange

    def paint(self, painter, option, widget):
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())

        painter.setPen(self._text_color)
        painter.setFont(self._font)
        painter.drawText(self.rect(), Qt.AlignCenter, self.text_label)

        if self.is_initial:
            painter.setBrush(Qt.black)
            painter.setPen(Qt.NoPen)
            # Draw an arrow pointing to the state from outside
            start_x = self.rect().left() - 20
            start_y = self.rect().center().y()
            end_x = self.rect().left()
            end_y = self.rect().center().y()
            
            line = QLineF(QPointF(start_x, start_y), QPointF(end_x, end_y))
            painter.setPen(QPen(Qt.black, 2))
            painter.drawLine(line)
            
            # Arrowhead
            angle = line.angle()
            arrow_size = 8
            p1 = line.p2() - QPointF(arrow_size * 0.866, arrow_size * 0.5).transformed(QTransform().rotate(angle - 180)) # cos(30), sin(30)
            p2 = line.p2() - QPointF(arrow_size * 0.866, -arrow_size * 0.5).transformed(QTransform().rotate(angle - 180))
            painter.setBrush(Qt.black)
            painter.drawPolygon(p1, p2, line.p2())


        if self.is_final:
            painter.setPen(QPen(Qt.black, 1)) # Outer border already drawn by main rect
            inner_rect = self.rect().adjusted(4, 4, -4, -4)
            painter.drawRect(inner_rect)

        if self.isSelected():
            pen = QPen(Qt.blue, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect().adjusted(-2, -2, 2, 2)) # Slightly larger selection rect

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)

    def get_data(self):
        return {
            'name': self.text_label, 'x': self.x(), 'y': self.y(),
            'width': self.rect().width(), 'height': self.rect().height(),
            'is_initial': self.is_initial, 'is_final': self.is_final
        }
    
    def set_text(self, text):
        self.text_label = text
        self.update()

class GraphicsTransitionItem(QGraphicsPathItem):
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type

    def __init__(self, start_item, end_item, text=""):
        super().__init__()
        self.start_item = start_item
        self.end_item = end_item
        self.text_label = text
        self.arrow_size = 10
        self._text_color = Qt.black
        self._font = QFont("Arial", 9)

        self.setPen(QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.update_path()

    def update_path(self):
        if not self.start_item or not self.end_item:
            return

        line = QLineF(self.mapFromItem(self.start_item, self.start_item.boundingRect().center()),
                      self.mapFromItem(self.end_item, self.end_item.boundingRect().center()))

        path = QPainterPath(line.p1())

        if self.start_item == self.end_item: # Self-loop
            control_offset = 50
            p1 = line.p1()
            c1 = QPointF(p1.x() - control_offset, p1.y() - control_offset)
            c2 = QPointF(p1.x() + control_offset, p1.y() - control_offset)
            path.cubicTo(c1, c2, p1 + QPointF(0, 1)) # Small offset to ensure distinct end point
        else:
            path.lineTo(line.p2())
        
        self.setPath(path)

    def paint(self, painter, option, widget):
        if not self.start_item or not self.end_item:
            return

        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawPath(self.path())

        # Draw arrowhead
        line = QLineF(self.path().pointAtPercent(0.90 if self.start_item != self.end_item else 0.45), # Adjust percent for self-loop
                      self.path().pointAtPercent(1.00 if self.start_item != self.end_item else 0.55))
        
        if line.length() == 0: return

        angle = line.angle() # Angle of the line segment
        
        arrow_p1 = line.p2() - QPointF(self.arrow_size * 0.866, self.arrow_size * 0.5).transformed(QTransform().rotate(angle - 180))
        arrow_p2 = line.p2() - QPointF(self.arrow_size * 0.866, -self.arrow_size * 0.5).transformed(QTransform().rotate(angle - 180))

        painter.setBrush(Qt.black)
        painter.drawPolygon(arrow_p1, arrow_p2, line.p2())


        # Draw text label
        if self.text_label:
            painter.setPen(self._text_color)
            painter.setFont(self._font)
            text_pos = self.path().pointAtPercent(0.5)
            # Simple offset, could be more sophisticated
            text_pos += QPointF(5, -5 if line.dy() > 0 else 5) 
            painter.drawText(text_pos, self.text_label)

        if self.isSelected():
            selection_pen = QPen(Qt.blue, 2, Qt.DashLine)
            painter.setPen(selection_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(self.path())
    
    def get_data(self):
        return {
            'source': self.start_item.text_label,
            'target': self.end_item.text_label,
            'label': self.text_label
        }
    
    def set_text(self, text):
        self.text_label = text
        self.update()

# Other graphics items (Action, Simulink) can be added similarly if needed for pure GUI rendering
# For this "GUI Only" pass, I'll focus on states and transitions for diagramming.
# The provided code for MatlabConnection.generate_simulink_model uses 'actions' parameter.
# If these 'actions' are meant to be graphical items, they need their own GraphicsItem class.
# For now, I'll assume 'actions' data for MATLAB comes from somewhere else or is less critical for GUI.

# --- Undo Commands ---
class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item = item
        # If item is a transition, store start/end item names for potential re-linking if items are recreated
        if isinstance(item, GraphicsTransitionItem):
            self.start_item_name = item.start_item.text_label
            self.end_item_name = item.end_item.text_label

    def redo(self):
        self.scene.addItem(self.item)
        # If it's a transition that was re-added, ensure its path is updated
        if isinstance(self.item, GraphicsTransitionItem):
            # Find start/end items in scene (they should be there if this command is valid)
            start_node = next((it for it in self.scene.items() if isinstance(it, GraphicsStateItem) and it.text_label == self.start_item_name), None)
            end_node = next((it for it in self.scene.items() if isinstance(it, GraphicsStateItem) and it.text_label == self.end_item_name), None)
            if start_node and end_node:
                self.item.start_item = start_node
                self.item.end_item = end_node
                self.item.update_path()
        self.scene.clearSelection()
        self.item.setSelected(True)
        self.scene.set_dirty(True)

    def undo(self):
        self.scene.removeItem(self.item)
        self.scene.set_dirty(True)

class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items, description="Remove Items"):
        super().__init__(description)
        self.scene = scene
        self.items_data = [] # Store enough data to recreate items
        
        # Store items in an order that states are stored before transitions
        sorted_items = sorted(items, key=lambda x: 0 if isinstance(x, GraphicsStateItem) else 1)

        for item in sorted_items:
            data = {'type': item.type(), 'data': item.get_data()}
            if isinstance(item, GraphicsStateItem):
                data['item_instance'] = item # Keep instance for re-adding
            elif isinstance(item, GraphicsTransitionItem):
                # For transitions, we need to store start/end item names to relink
                data['start_item_name'] = item.start_item.text_label
                data['end_item_name'] = item.end_item.text_label
                data['item_instance'] = item
            self.items_data.append(data)
        
    def redo(self):
        for item_d in self.items_data:
            self.scene.removeItem(item_d['item_instance'])
        self.scene.set_dirty(True)

    def undo(self):
        # Re-add states first, then transitions
        recreated_states = {}
        for item_d in self.items_data:
            if item_d['type'] == GraphicsStateItem.Type:
                item = item_d['item_instance']
                self.scene.addItem(item)
                recreated_states[item.text_label] = item

        for item_d in self.items_data:
            if item_d['type'] == GraphicsTransitionItem.Type:
                item = item_d['item_instance']
                start_node = recreated_states.get(item_d['start_item_name'])
                end_node = recreated_states.get(item_d['end_item_name'])
                if start_node and end_node:
                    item.start_item = start_node
                    item.end_item = end_node
                    self.scene.addItem(item)
                    item.update_path()
        self.scene.set_dirty(True)


class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_positions, description="Move Items"):
        super().__init__(description)
        self.items_positions_new = items_positions # list of (item, new_pos)
        self.items_positions_old = []
        for item, _ in self.items_positions_new:
            self.items_positions_old.append((item, item.pos()))

    def redo(self):
        for item, new_pos in self.items_positions_new:
            item.setPos(new_pos)
        # Scene dirty flag should be handled by the scene itself after move
    
    def undo(self):
        for item, old_pos in self.items_positions_old:
            item.setPos(old_pos)

# --- Diagram Scene ---
class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool)

    def __init__(self, undo_stack, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 3000, 2000) # Larger scene
        self.current_mode = "select"
        self.transition_start_item = None
        self.log_function = print # Default log
        self.undo_stack = undo_stack
        self._dirty = False
        self._mouse_press_items_positions = {} # For move command

        self.item_moved.connect(self._handle_item_moved)
        self.setBackgroundBrush(QColor(240, 240, 240)) # Light gray background

    def set_dirty(self, dirty=True):
        if self._dirty != dirty:
            self._dirty = dirty
            self.modifiedStatusChanged.emit(dirty)
            
    def is_dirty(self):
        return self._dirty

    def set_log_function(self, log_function):
        self.log_function = log_function

    def set_mode(self, mode):
        self.current_mode = mode
        self.transition_start_item = None # Reset if mode changes
        if mode == "select":
            QApplication.setOverrideCursor(Qt.ArrowCursor)
        elif mode in ["state", "transition"]: # Add other modes if they use cross cursor
            QApplication.setOverrideCursor(Qt.CrossCursor)
        else:
            QApplication.restoreOverrideCursor() # Restore for other modes

    def _handle_item_moved(self, moved_item):
        if isinstance(moved_item, GraphicsStateItem):
            for item in self.items():
                if isinstance(item, GraphicsTransitionItem):
                    if item.start_item == moved_item or item.end_item == moved_item:
                        item.update_path()
        self.set_dirty()

    def mousePressEvent(self, event):
        pos = event.scenePos()
        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                self._add_state_item(pos)
            elif self.current_mode == "transition":
                item_at_pos = self.itemAt(pos, QTransform())
                if isinstance(item_at_pos, GraphicsStateItem):
                    self._handle_transition_click(item_at_pos)
                else: # Clicked on empty space, cancel transition drawing
                    self.transition_start_item = None
                    self.log_function("Transition drawing cancelled.")
            else: # Select mode
                super().mousePressEvent(event)
                self._mouse_press_items_positions.clear()
                for item in self.selectedItems():
                    self._mouse_press_items_positions[item] = item.pos()
                return
        else: # Other mouse buttons
            super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            moved_items_data = []
            for item, old_pos in self._mouse_press_items_positions.items():
                if item.pos() != old_pos : # Item actually moved
                    moved_items_data.append((item, item.pos())) # Store item and its new position
            
            if moved_items_data:
                self.undo_stack.push(MoveItemsCommand(moved_items_data))
                self.set_dirty() # Move command will handle its own dirtying, but scene confirms
            self._mouse_press_items_positions.clear()

        super().mouseReleaseEvent(event)


    def _add_state_item(self, pos):
        state_name, ok = QInputDialog.getText(None, "New State", "Enter state name:")
        if ok and state_name:
            # Check for duplicate state names
            if any(isinstance(item, GraphicsStateItem) and item.text_label == state_name for item in self.items()):
                QMessageBox.warning(None, "Duplicate Name", f"A state with the name '{state_name}' already exists.")
                return

            props_dialog = StatePropertiesDialog(state_name)
            if props_dialog.exec_() == QDialog.Accepted:
                new_state = GraphicsStateItem(
                    pos.x() - 60, pos.y() - 30, 120, 60, # Center the state on click
                    props_dialog.get_name(),
                    props_dialog.is_initial_cb.isChecked(),
                    props_dialog.is_final_cb.isChecked()
                )
                cmd = AddItemCommand(self, new_state, "Add State")
                self.undo_stack.push(cmd)
                self.log_function(f"Added state: {new_state.text_label}")
        self.set_mode("select") # Revert to select mode

    def _handle_transition_click(self, clicked_state_item):
        if not self.transition_start_item:
            self.transition_start_item = clicked_state_item
            self.log_function(f"Transition started from: {clicked_state_item.text_label}")
            # Visual feedback for start item could be added here
        else:
            if self.transition_start_item == clicked_state_item: # Clicked same state again
                # Optionally allow self-loops here or cancel
                self.log_function("Self-transition clicked. Define behavior or label.")
                # For now, let's proceed to ask for label for self-loop too
            
            label, ok = QInputDialog.getText(None, "New Transition", "Enter transition label (optional):")
            if ok: # Even if label is empty, user pressed OK
                new_transition = GraphicsTransitionItem(self.transition_start_item, clicked_state_item, label)
                cmd = AddItemCommand(self, new_transition, "Add Transition")
                self.undo_stack.push(cmd)
                self.log_function(f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{label}]")
            
            self.transition_start_item = None # Reset for next transition
            self.set_mode("select") # Revert to select mode

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            selected = self.selectedItems()
            if selected:
                # Need to handle deleting transitions connected to deleted states carefully
                # For simplicity, QUndoCommand for RemoveItems should handle this.
                cmd = RemoveItemsCommand(self, selected, "Delete Items")
                self.undo_stack.push(cmd)
                self.log_function(f"Deleted {len(selected)} item(s).")
        elif event.key() == Qt.Key_Escape:
            if self.transition_start_item:
                self.transition_start_item = None
                self.log_function("Transition drawing cancelled.")
                self.set_mode("select")
            else:
                self.clearSelection()
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-state-tool") or \
           event.mimeData().hasFormat("application/x-transition-tool"): # Add other tool types
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-state-tool") or \
           event.mimeData().hasFormat("application/x-transition-tool"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        pos = event.scenePos()
        if event.mimeData().hasFormat("application/x-state-tool"):
            # Dropped a state tool, similar to clicking "Add State" button then canvas
            self.set_mode("state") # Temporarily set mode
            self._add_state_item(pos) # Use the existing add state logic
            event.acceptProposedAction()
        # Add handling for other dropped tools if needed (e.g., transition tool is more complex via D&D)
        else:
            super().dropEvent(event)

    def get_diagram_data(self):
        data = {'states': [], 'transitions': []} # Add other item types if they have get_data
        for item in self.items():
            if isinstance(item, GraphicsStateItem):
                data['states'].append(item.get_data())
            elif isinstance(item, GraphicsTransitionItem):
                data['transitions'].append(item.get_data())
        return data

    def load_diagram_data(self, data):
        self.clear() # Clear existing items (consider QUndoStack implications if loading is undoable)
        
        # Important: disable dirty flag during loading
        current_dirty_state = self._dirty
        self.set_dirty(False) # Temporarily set to false

        state_items_map = {} # To link transitions correctly

        for state_data in data.get('states', []):
            state_item = GraphicsStateItem(
                state_data['x'], state_data['y'],
                state_data.get('width', 120), state_data.get('height', 60),
                state_data['name'],
                state_data.get('is_initial', False),
                state_data.get('is_final', False)
            )
            self.addItem(state_item)
            state_items_map[state_data['name']] = state_item

        for trans_data in data.get('transitions', []):
            src_item = state_items_map.get(trans_data['source'])
            tgt_item = state_items_map.get(trans_data['target'])
            if src_item and tgt_item:
                trans_item = GraphicsTransitionItem(src_item, tgt_item, trans_data.get('label', ''))
                self.addItem(trans_item)
            else:
                self.log_function(f"Warning: Could not link transition '{trans_data.get('label')}' due to missing states.")
        
        if not current_dirty_state: # If it wasn't dirty before load, keep it that way
            self.set_dirty(False) 
        else: # If it was dirty, loading new content makes it "modified" from empty/previous state
             self.set_dirty(True) # Or reset based on if it matches saved state. For now, new load = dirty.
        
        self.undo_stack.clear() # New file, clear undo history

# --- Dialogs ---
class StatePropertiesDialog(QDialog):
    def __init__(self, state_name="", initial=False, final=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        layout = QFormLayout(self)

        self.name_edit = QLineEdit(state_name)
        layout.addRow("Name:", self.name_edit)

        self.is_initial_cb = QCheckBox()
        self.is_initial_cb.setChecked(initial)
        layout.addRow("Initial State:", self.is_initial_cb)

        self.is_final_cb = QCheckBox()
        self.is_final_cb.setChecked(final)
        layout.addRow("Final State:", self.is_final_cb)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_name(self): return self.name_edit.text()
    # Other getters for checkboxes are direct e.g. dialog.is_initial_cb.isChecked()

class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings")
        self.setMinimumWidth(500)

        main_layout = QVBoxLayout(self)

        path_group = QGroupBox("MATLAB Executable Path")
        path_layout = QFormLayout()
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path)
        path_layout.addRow("Path:", self.path_edit)
        
        btn_layout = QHBoxLayout()
        auto_detect_btn = QPushButton("Auto-detect")
        auto_detect_btn.clicked.connect(self._auto_detect)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        btn_layout.addWidget(auto_detect_btn)
        btn_layout.addWidget(browse_btn)
        path_layout.addRow(btn_layout)
        path_group.setLayout(path_layout)
        main_layout.addWidget(path_group)

        test_group = QGroupBox("Connection Test")
        test_layout = QVBoxLayout()
        self.test_status_label = QLabel("Status: Unknown")
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_connection)
        test_layout.addWidget(test_btn)
        test_layout.addWidget(self.test_status_label)
        test_group.setLayout(test_layout)
        main_layout.addWidget(test_group)

        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.accepted.connect(self._apply_settings)
        dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)
        
        # Update status on initial show based on current connection
        self._update_test_label(self.matlab_connection.connected, "Already connected" if self.matlab_connection.connected else "Not connected")

    def _auto_detect(self):
        self.test_status_label.setText("Status: Auto-detecting...")
        QApplication.processEvents() # Update UI
        if self.matlab_connection.detect_matlab():
            self.path_edit.setText(self.matlab_connection.matlab_path)
            self._update_test_label(True, "MATLAB detected. Test to confirm.")
        else:
            self._update_test_label(False, "Auto-detection failed.")

    def _browse(self):
        exe_filter = "MATLAB Executable (matlab.exe);;All Files (*)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", "", exe_filter)
        if path:
            self.path_edit.setText(path)
            # Setting path here doesn't mean it's connected, only that user selected it
            self.test_status_label.setText("Status: Path selected. Test to confirm.")


    def _test_connection(self):
        path = self.path_edit.text()
        if not path:
            self._update_test_label(False, "Path is empty.")
            return

        # Temporarily set path for testing, without making it permanent in connection obj yet
        # Or, we can set it, and if test fails, connection obj will update its state
        self.test_status_label.setText("Status: Testing...")
        QApplication.processEvents()
        
        original_path = self.matlab_connection.matlab_path
        self.matlab_connection.set_matlab_path(path) # This will emit status change
        
        # The test_connection method itself will emit connectionStatusChanged
        # We need a way to capture *that specific signal emission* for this dialog
        # For simplicity here, we'll rely on the _update_test_label from main window's slot
        # Or, connect to it temporarily.
        
        # Let's make this dialog listen to the signal directly for its own update
        # To avoid complexity, we call test_connection, which updates the global status.
        # Then, we update our label based on that global status.
        
        # Make set_matlab_path silent for a moment for test_connection
        self.matlab_connection.matlab_path = path # directly set
        self.matlab_connection.connected = True # assume for test
        
        if self.matlab_connection.test_connection(): # This will emit and update internal state
             self._update_test_label(True, self.matlab_connection.connectionStatusChanged.arguments[0][1] if self.matlab_connection.connectionStatusChanged.arguments else "Test successful.")
        else:
             self._update_test_label(False, self.matlab_connection.connectionStatusChanged.arguments[0][1] if self.matlab_connection.connectionStatusChanged.arguments else "Test failed.")
        
        # Restore original path if test failed, or if we don't want to apply yet
        # The OK button will apply it.
        if not self.matlab_connection.connected : # if test failed
             self.matlab_connection.set_matlab_path(original_path) # revert
    
    def _update_test_label(self, success, message):
        status_text = "Status: " + ("Success: " if success else "Failed: ") + message
        self.test_status_label.setText(status_text)
        self.test_status_label.setStyleSheet("color: green;" if success else "color: red;")


    def _apply_settings(self):
        # This is called when OK is pressed
        path = self.path_edit.text()
        if self.matlab_connection.set_matlab_path(path): # This updates the global connection
            if not self.matlab_connection.test_connection(): # Test it one last time
                QMessageBox.warning(self, "MATLAB Connection", "MATLAB path was set, but connection test failed. Please verify the path and MATLAB installation.")
        elif path: # Path was set, but set_matlab_path failed (e.g. invalid path)
            QMessageBox.warning(self, "Invalid Path", "The specified MATLAB path is invalid.")
        
        self.accept()

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file_path = None
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)
        
        self.scene = DiagramScene(self.undo_stack, self)
        self.scene.set_log_function(self.log_message)
        self.scene.modifiedStatusChanged.connect(self.setWindowModified) # For '*' in title
        self.scene.modifiedStatusChanged.connect(self._update_save_actions)


        self.init_ui()
        self._update_matlab_status(False, "Not Connected. Configure in Simulation menu.")
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_process_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)

        self.setWindowTitle(f"Brain State Machine Designer")

    def init_ui(self):
        self.setGeometry(100, 100, 1400, 900)
        
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_docks()
        self._create_central_widget()
        self._update_save_actions() # Initial state for save actions

    def _create_actions(self):
        # File
        self.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon), "&New", self, shortcut="Ctrl+N", triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton), "&Open...", self, shortcut="Ctrl+O", triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton), "&Save", self, shortcut="Ctrl+S", triggered=self.on_save_file)
        self.save_as_action = QAction("Save &As...", self, triggered=self.on_save_file_as)
        self.export_matlab_action = QAction(get_standard_icon(QStyle.SP_ArrowRight), "Export to MATLAB &Model...", self, triggered=self.on_export_to_matlab_model)
        self.exit_action = QAction("E&xit", self, shortcut="Ctrl+Q", triggered=self.close)

        # Edit
        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowLeft)) # Or SP_UndoIcon if available
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowRight)) # Or SP_RedoIcon

        self.delete_action = QAction(get_standard_icon(QStyle.SP_TrashIcon), "&Delete", self, shortcut="Del", triggered=lambda: self.scene.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)))
        self.select_all_action = QAction("Select &All", self, shortcut="Ctrl+A", triggered=self.scene.selectAll)

        # Tools (Mode selection)
        self.mode_group = QActionGroup(self)
        self.select_mode_action = QAction(get_standard_icon(QStyle.SP_ArrowMove), "Select/Move", self, checkable=True, checked=True, triggered=lambda: self.scene.set_mode("select"))
        self.add_state_mode_action = QAction(get_standard_icon(QStyle.SP_FileDialogDetailedView), "Add State", self, checkable=True, triggered=lambda: self.scene.set_mode("state"))
        self.add_transition_mode_action = QAction(get_standard_icon(QStyle.SP_ArrowForward), "Add Transition", self, checkable=True, triggered=lambda: self.scene.set_mode("transition"))
        
        for act in [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action]:
            self.mode_group.addAction(act)

        # View
        self.zoom_in_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton), "Zoom &In", self, shortcut="Ctrl++", triggered=lambda: self.view.scale(1.2, 1.2))
        self.zoom_out_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton), "Zoom &Out", self, shortcut="Ctrl+-", triggered=lambda: self.view.scale(1/1.2, 1/1.2))
        self.zoom_reset_action = QAction("Reset Zoom", self, shortcut="Ctrl+0", triggered=self.view.resetTransform)

        # Simulation
        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay), "&Run Simulation...", self, triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(QStyle.SP_CommandLink), "&Generate Code...", self, triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon), "MATLAB Settings...", self, triggered=self.on_configure_matlab)
        
        # Help
        self.help_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton), "&Help Contents", self, shortcut="F1", triggered=self.on_show_help)
        self.about_action = QAction("&About...", self, triggered=self.on_show_about)

    def _create_menus(self):
        # File Menu
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_matlab_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        # Edit Menu
        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.delete_action)
        edit_menu.addAction(self.select_all_action)
        
        # View Menu
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addAction(self.zoom_reset_action)

        # Simulation Menu
        sim_menu = self.menuBar().addMenu("&Simulation")
        sim_menu.addAction(self.run_simulation_action)
        sim_menu.addAction(self.generate_code_action)
        sim_menu.addSeparator()
        sim_menu.addAction(self.matlab_settings_action)

        # Help Menu
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.help_action)
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        file_toolbar = self.addToolBar("File")
        file_toolbar.addAction(self.new_action)
        file_toolbar.addAction(self.open_action)
        file_toolbar.addAction(self.save_action)

        edit_toolbar = self.addToolBar("Edit")
        edit_toolbar.addAction(self.undo_action)
        edit_toolbar.addAction(self.redo_action)
        edit_toolbar.addAction(self.delete_action)
        
        tools_toolbar = self.addToolBar("Tools")
        tools_toolbar.addAction(self.select_mode_action)
        tools_toolbar.addAction(self.add_state_mode_action)
        tools_toolbar.addAction(self.add_transition_mode_action)

        sim_toolbar = self.addToolBar("Simulation")
        sim_toolbar.addAction(self.run_simulation_action)
        sim_toolbar.addAction(self.generate_code_action)

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1) # Stretch factor 1
        self.matlab_status_label = QLabel("MATLAB: Not Connected")
        self.status_bar.addPermanentWidget(self.matlab_status_label)

    def _create_docks(self):
        # Toolbox Dock
        toolbox_dock = QDockWidget("Toolbox", self)
        toolbox_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        toolbox = QToolBox()
        # States Page
        states_page = QWidget()
        states_layout = QVBoxLayout(states_page)
        states_layout.addWidget(DraggableToolButton("State", "application/x-state-tool", "background-color: lightblue;"))
        # Add more specific state tools if needed (Initial, Final) or handle via properties
        states_layout.addStretch()
        toolbox.addItem(states_page, "States")

        # (Transitions Page - typically not dragged, but drawn)
        # Could add a button here to activate transition mode
        
        toolbox_dock.setWidget(toolbox)
        self.addDockWidget(Qt.LeftDockWidgetArea, toolbox_dock)

        # Log Dock
        log_dock = QDockWidget("Log", self)
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        log_dock.setWidget(self.log_text_edit)
        self.addDockWidget(Qt.BottomDockWidgetArea, log_dock)
        
        # Properties Dock (placeholder, could be implemented to show selected item properties)
        # props_dock = QDockWidget("Properties", self)
        # props_widget = QWidget() # Implement property editor here
        # props_dock.setWidget(props_widget)
        # self.addDockWidget(Qt.RightDockWidgetArea, props_dock)


    def _create_central_widget(self):
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.RubberBandDrag) # For selecting multiple items
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setAcceptDrops(True) # To accept drops from toolbox
        self.setCentralWidget(self.view)

    def log_message(self, message):
        self.log_text_edit.append(message)
        self.status_label.setText(message.split('\n')[0]) # Show first line in status

    def _update_matlab_status(self, connected, message):
        self.matlab_status_label.setText(f"MATLAB: {'Connected' if connected else 'Not Connected'}")
        self.matlab_status_label.setStyleSheet("color: green;" if connected else "color: red;")
        self.log_message(f"MATLAB Status: {message}")
        
        # Enable/disable MATLAB-dependent actions
        self.export_matlab_action.setEnabled(connected)
        self.run_simulation_action.setEnabled(connected)
        self.generate_code_action.setEnabled(connected)
    
    def _handle_matlab_process_finished(self, success, message, model_path_or_data=""):
        if success:
            QMessageBox.information(self, "MATLAB Process", f"Process completed successfully.\n{message}")
            self.log_message(f"MATLAB Success: {message}")
            if model_path_or_data and os.path.exists(model_path_or_data): # If a path was returned and exists
                # Try to open the directory containing the file
                try:
                    if sys.platform == 'win32':
                        os.startfile(os.path.dirname(model_path_or_data))
                    elif sys.platform == 'darwin':
                        subprocess.call(['open', os.path.dirname(model_path_or_data)])
                    else: # linux variants
                        subprocess.call(['xdg-open', os.path.dirname(model_path_or_data)])
                except Exception as e:
                    self.log_message(f"Could not open output directory: {e}")

        else:
            QMessageBox.critical(self, "MATLAB Process Error", f"Process failed.\n{message}")
            self.log_message(f"MATLAB Error: {message}")

    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._handle_matlab_process_finished(success, message, output_dir) # Similar handling
        if success and output_dir:
            self.log_message(f"Code generated in: {output_dir}")

    def _update_window_title(self):
        title = "Brain State Machine Designer"
        if self.current_file_path:
            title = f"{os.path.basename(self.current_file_path)} - {title}"
        if self.scene.is_dirty():
            title += "*"
        self.setWindowTitle(title)

    def setWindowModified(self, modified):
        # QMainWindow's built-in modified state handling
        super().setWindowModified(modified) 
        self._update_window_title()
        
    def _update_save_actions(self):
        is_dirty = self.scene.is_dirty()
        self.save_action.setEnabled(is_dirty) # Only enable if dirty and has path, or always if no path
        # If no current_file_path, save_action should behave like save_as_action or be disabled.
        # Let's simplify: save_action is enabled if dirty. If no path, it calls save_as.
        if not self.current_file_path:
            self.save_action.setEnabled(is_dirty) # if dirty, can save (as)
        else:
            self.save_action.setEnabled(is_dirty)

    # --- Action Handlers (File) ---
    def on_new_file(self):
        if self._maybe_save():
            self.scene.clear()
            self.undo_stack.clear()
            self.current_file_path = None
            self.scene.set_dirty(False) # New file is not dirty
            self._update_window_title()
            self.log_message("New diagram created.")

    def on_open_file(self):
        if self._maybe_save():
            path, _ = QFileDialog.getOpenFileName(self, "Open File", "", FILE_FILTER)
            if path:
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                    self.scene.load_diagram_data(data)
                    self.current_file_path = path
                    self.scene.set_dirty(False) # Loaded file is not dirty initially
                    self._update_window_title()
                    self.undo_stack.clear() # Clear undo stack for new file
                    self.log_message(f"Opened: {path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error Opening File", f"Could not open file: {str(e)}")
                    self.log_message(f"Error opening {path}: {e}")

    def on_save_file(self):
        if not self.current_file_path:
            return self.on_save_file_as()
        else:
            return self._save_to_path(self.current_file_path)

    def on_save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save File As", self.current_file_path or "", FILE_FILTER)
        if path:
            if not path.lower().endswith(FILE_EXTENSION):
                 path += FILE_EXTENSION
            return self._save_to_path(path)
        return False

    def _save_to_path(self, path):
        try:
            data = self.scene.get_diagram_data()
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            self.current_file_path = path
            self.scene.set_dirty(False)
            self._update_window_title()
            self.log_message(f"Saved to: {path}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error Saving File", f"Could not save file: {str(e)}")
            self.log_message(f"Error saving to {path}: {e}")
            return False

    def _maybe_save(self):
        if not self.scene.is_dirty():
            return True
        
        reply = QMessageBox.question(self, "Unsaved Changes",
                                     "There are unsaved changes. Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if reply == QMessageBox.Save:
            return self.on_save_file()
        elif reply == QMessageBox.Cancel:
            return False
        return True # Discard

    def closeEvent(self, event):
        if self._maybe_save():
            event.accept()
        else:
            event.ignore()

    # --- Action Handlers (MATLAB/Simulation) ---
    def on_export_to_matlab_model(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "Please configure MATLAB connection first.")
            return

        output_dir = QFileDialog.getExistingDirectory(self, "Select Directory for SLX Model")
        if not output_dir:
            return

        model_name, ok = QInputDialog.getText(self, "Model Name", "Enter Simulink model name:", text="BrainStateMachine")
        if not ok or not model_name:
            return

        data = self.scene.get_diagram_data()
        # The 'actions' parameter for generate_simulink_model is not fully defined by current GUI items.
        # Passing empty list for now, or collect data if you have graphical action items.
        actions_data_for_matlab = [] # Placeholder
        
        self.log_message(f"Exporting to Simulink model '{model_name}.slx' in {output_dir}...")
        self.matlab_connection.generate_simulink_model(
            data['states'], data['transitions'], actions_data_for_matlab, output_dir, model_name
        )

    def on_run_simulation(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "Please configure MATLAB connection first.")
            return

        # Model needs to be generated first, or user selects an existing .slx
        # For now, let's assume we generate it first
        temp_model_dir = tempfile.mkdtemp(prefix="bsm_sim_")
        model_name = "TempSimModel"
        
        self.log_message(f"Generating temporary model for simulation in {temp_model_dir}...")
        data = self.scene.get_diagram_data()
        actions_data_for_matlab = [] # Placeholder
        
        # Use a signal to know when model generation is done, then run simulation
        # This is tricky with current setup. For simplicity, one action at a time.
        # Or, user should first export, then run that exported model.
        
        # For now, let's simplify: Ask user for existing SLX or one they just exported.
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model to Simulate", "", "Simulink Models (*.slx)")
        if not model_path:
            self.log_message("Simulation cancelled: No model selected.")
            return

        sim_time, ok = QInputDialog.getInt(self, "Simulation Time", "Enter simulation time (seconds):", 10, 1, 36000)
        if not ok:
            return
            
        self.log_message(f"Starting simulation for {model_path} (Time: {sim_time}s)...")
        self.matlab_connection.run_simulation(model_path, sim_time)


    def on_generate_code(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "Please configure MATLAB connection first.")
            return

        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model for Code Generation", "", "Simulink Models (*.slx)")
        if not model_path:
            self.log_message("Code generation cancelled: No model selected.")
            return

        language, ok = QInputDialog.getItem(self, "Target Language", "Select target language:", ["C", "C++"], 0, False)
        if not ok:
            return

        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory for Generated Code")
        if not output_dir:
            return
            
        self.log_message(f"Starting {language} code generation from {model_path} into {output_dir}...")
        self.matlab_connection.generate_code(model_path, language, output_dir)

    def on_configure_matlab(self):
        dialog = MatlabSettingsDialog(self.matlab_connection, self)
        # The dialog will now interact with self.matlab_connection and that will emit signals
        # which _update_matlab_status will catch.
        dialog.exec_() # This dialog now applies changes via its OK button.

    # --- Action Handlers (Help) ---
    def on_show_about(self):
        QMessageBox.about(self, "About Brain State Machine Designer",
                          f"""<h2>Brain State Machine Designer</h2>
                           <p>Version {APP_VERSION}</p>
                           <p>A tool for designing state machines with potential MATLAB/Simulink integration.</p>
                           <p>© 2024 Your Name/Organization</p>""")

    def on_show_help(self):
        # The existing help dialog structure from the original code is quite good.
        # For brevity in this refactor, I'll show a simpler message.
        # You can reintegrate the more detailed QTabWidget-based help if needed.
        QMessageBox.information(self, "Help",
                                """
                                <b>Basic Usage:</b>
                                <ul>
                                  <li>Use toolbar buttons or Edit menu to switch modes (Select, Add State, Add Transition).</li>
                                  <li><b>Add State:</b> Activate mode, then click on canvas.</li>
                                  <li><b>Add Transition:</b> Activate mode, click source state, then click target state.</li>
                                  <li><b>Select/Move:</b> Activate mode, click to select, drag to move.</li>
                                  <li>Use File menu to New, Open, Save diagrams (.bsm files).</li>
                                  <li>Configure MATLAB via Simulation > MATLAB Settings.</li>
                                  <li>Export, Simulate, Generate Code if MATLAB is configured.</li>
                                </ul>
                                """)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # app.setStyle("Fusion") # Optional: for a more modern look

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec_())