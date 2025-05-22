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
    QGroupBox, QUndoStack, QUndoCommand, QStyle  # Added QStyle
)
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform, QKeyEvent  # Added QKeyEvent
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent  # Added QEvent
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
    simulationFinished = pyqtSignal(bool, str, str)      # success, message, data (model_path)
    codeGenerationFinished = pyqtSignal(bool, str, str)  # success, message, output_dir

    def __init__(self):
        super().__init__()
        self.matlab_path = ""
        self.connected = False
        self._active_threads = [] # To keep track of running threads

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
                capture_output=True, text=True, timeout=15, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
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
            versions = ['R2024a', 'R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b'] # Add more versions
            for v in versions:
                paths.append(os.path.join(program_files, 'MATLAB', v, 'bin', 'matlab.exe'))
        elif sys.platform == 'darwin':  # macOS
            versions = ['R2024a', 'R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b']
            for v in versions:
                paths.append(f'/Applications/MATLAB_{v}.app/bin/matlab')
        else:  # Linux
            versions = ['R2024a', 'R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b']
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
            # Ensure 3 args for codegen, 2 for simulationFinished
            if worker_signal == self.codeGenerationFinished:
                 worker_signal.emit(False, "MATLAB not connected.", "")
            else:
                 worker_signal.emit(False, "MATLAB not connected.")
            return

        temp_dir = tempfile.mkdtemp()
        script_file = os.path.join(temp_dir, "matlab_script.m")
        with open(script_file, 'w') as f:
            f.write(script_content)

        worker = MatlabCommandWorker(self.matlab_path, script_file, worker_signal, success_message_prefix)
        thread = QThread()
        worker.moveToThread(thread)

        thread.started.connect(worker.run_command)
        worker.finished_signal.connect(thread.quit) # Worker signals when it's done
        # Clean up thread and worker after they finish
        worker.finished_signal.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        
        # Keep a reference to the thread to prevent it from being garbage collected prematurely
        self._active_threads.append(thread)
        thread.finished.connect(lambda t=thread: self._active_threads.remove(t) if t in self._active_threads else None)
        
        thread.start()


    def generate_simulink_model(self, states, transitions, actions_data, output_dir, model_name="BrainStateMachine"):
        """Generate a Simulink model file (.slx) from the state machine."""
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected.", "") # Using sim finished for general model gen
            return False

        slx_file_path = os.path.join(output_dir, f"{model_name}.slx").replace('\\', '/')

        script_lines = [
            f"% Auto-generated Simulink model script for {model_name}",
            f"disp('Starting Simulink model generation for {model_name}...');",
            f"modelName = '{model_name}';",
            f"outputModelPath = '{slx_file_path}';",
            "try",
            "    if exist(outputModelPath, 'file'), delete(outputModelPath); end", # Ensure clean slate
            "    if bdIsLoaded(modelName), close_system(modelName, 0); end",
            "    new_system(modelName);",
            "    open_system(modelName);",
            "    sfChart = Stateflow.Chart(modelName);",
            "    sfChart.Name = 'BrainStateMachineChart';",
            "    stateHandles = containers.Map('KeyType','char','ValueType','any'); % Use containers.Map for safety with names"
        ]

        for i, state in enumerate(states):
            s_name_matlab = state['name'].replace("'", "''") # Escape single quotes for MATLAB strings
            s_id_matlab_safe = f"state_{java.util.UUID.randomUUID().toString().replace('-', '')}"; # Unique safe var name
            script_lines.extend([
                f"{s_id_matlab_safe} = Stateflow.State(sfChart);",
                f"{s_id_matlab_safe}.Name = '{s_name_matlab}';",
                # Adjust position and size as needed
                f"{s_id_matlab_safe}.Position = [{state['x']}, {state['y']}, 120, 60];", # Using fixed size for now
                f"stateHandles('{s_name_matlab}') = {s_id_matlab_safe};"
            ])
            if state.get('is_initial', False):
                # Default transition points to the initial state
                script_lines.append(f"defaultTransition_{i} = Stateflow.Transition(sfChart);")
                script_lines.append(f"defaultTransition_{i}.Destination = {s_id_matlab_safe};")
                script_lines.append(f"sfChart.defaultTransition = defaultTransition_{i};")


        for i, trans in enumerate(transitions):
            src_name_matlab = trans['source'].replace("'", "''")
            dst_name_matlab = trans['target'].replace("'", "''")
            t_label_matlab = trans['label'].replace("'", "''") if trans.get('label') else ''
            
            # Check if source and destination states exist in map
            script_lines.extend([
                f"if isKey(stateHandles, '{src_name_matlab}') && isKey(stateHandles, '{dst_name_matlab}')",
                f"    t{i} = Stateflow.Transition(sfChart);",
                f"    t{i}.Source = stateHandles('{src_name_matlab}');",
                f"    t{i}.Destination = stateHandles('{dst_name_matlab}');"
            ])
            if t_label_matlab:
                script_lines.append(f"    t{i}.LabelString = '{t_label_matlab}';")
            script_lines.append("else")
            script_lines.append(f"    disp(['Warning: Could not create transition from {src_name_matlab} to {dst_name_matlab} - state not found.']);")
            script_lines.append("end")


        script_lines.extend([
            "    disp(['Attempting to save model to: ', outputModelPath]);",
            "    save_system(modelName, outputModelPath);",
            "    close_system(modelName, 0);",
            "    disp(['Simulink model saved to: ', outputModelPath]);",
            "    fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', outputModelPath);", # For worker to parse path
            "catch e",
            "    disp(['Error during Simulink model generation: ', getReport(e, 'extended')]);",
            "    if bdIsLoaded(modelName), close_system(modelName, 0); end",  #Try to clean up
            "    rethrow(e);",
            "end"
        ])
        
        script_content = "\n".join(script_lines)
        # Use simulationFinished signal as it takes (bool, str, str)
        self._run_matlab_script(script_content, self.simulationFinished, "Model generation")
        return True # Indicates process started

    def run_simulation(self, model_path, sim_time=10):
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected.", "")
            return False
        if not os.path.exists(model_path):
            self.simulationFinished.emit(False, f"Model file not found: {model_path}", "")
            return False

        model_path_matlab = model_path.replace('\\', '/')
        model_name = os.path.splitext(os.path.basename(model_path))[0]

        script_content = f"""
        disp('Starting simulation...');
        modelPath = '{model_path_matlab}';
        modelName = '{model_name}';
        try
            load_system(modelPath);
            set_param(modelName, 'StopTime', '{sim_time}');
            simOut = sim(modelName);
            disp('Simulation completed successfully.');
            fprintf('MATLAB_SCRIPT_SUCCESS:Simulation finished for %s.\\n', modelName);
        catch e
            disp(['Simulation error: ', getReport(e, 'extended')]);
            if bdIsLoaded(modelName), close_system(modelName, 0); end % Try to clean up
            rethrow(e); % This will cause non-zero exit code if script run with -batch
        end
        if bdIsLoaded(modelName), close_system(modelName, 0); end
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
        
        try
            load_system(modelPath);
            
            % Set up configuration object for C/C++ code generation
            cfg = coder.config('rtwlib'); % For ERT-based targets
            if strcmpi('{language}', 'C++')
                cfg.TargetLang = 'C++';
                disp('Configured for C++ code generation.');
            else
                cfg.TargetLang = 'C';
                disp('Configured for C code generation.');
            end
            cfg.GenerateReport = true;
            cfg.GenCodeOnly = true; 

            % Specify the code generation folder
            codeGenFolder = fullfile(outputDir, [modelName '_codegen_ert_rtw']); % ERT specific
            if ~exist(codeGenFolder, 'dir')
               mkdir(codeGenFolder);
            end
            
            % Set build arguments: use CodeGenFolder for output
            buildArgs = coder.BuildConfig;
            buildArgs.Config = cfg;
            buildArgs.BuildDirectory = codeGenFolder; % ERT requires this for rtwbuild
            
            current_folder = pwd;
            % No need to cd if BuildDirectory is set correctly for rtwbuild with ERT
            
            % Generate code using rtwbuild for ERT targets
            rtwbuild(modelName, buildArgs);
            disp('Code generation command executed.');
            
            actualCodeDir = codeGenFolder; % The build directory is the main output

            disp(['Code generation successful. Code saved in: ', actualCodeDir]);
            fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', actualCodeDir); 
        catch e
            disp(['Code generation error: ', getReport(e, 'extended')]);
            % cd(current_folder); % Restore original directory if cd was used
            if bdIsLoaded(modelName), close_system(modelName, 0); end % Try to clean up
            rethrow(e);
        end
        % cd(current_folder); % Restore original directory if cd was used
        if bdIsLoaded(modelName), close_system(modelName, 0); end
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
        self.original_signal = original_signal
        self.success_message_prefix = success_message_prefix

    def run_command(self):
        output_data_for_signal = ""
        try:
            cmd = [self.matlab_path, "-batch", f"run('{self.script_file}')"]
            process = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300,  # 5 minutes timeout
                check=False,   # Handle non-zero exit codes manually
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0 # Hide console on Windows
            )

            output_data_for_signal = "" # Specific data like path extracted from MATLAB output
            success = False

            if process.returncode == 0:
                if "MATLAB_SCRIPT_SUCCESS" in process.stdout:
                    success = True
                    for line in process.stdout.splitlines():
                        if line.startswith("MATLAB_SCRIPT_SUCCESS:"):
                            output_data_for_signal = line.split(":", 1)[1].strip()
                            break
                    message = f"{self.success_message_prefix} completed successfully."
                    if output_data_for_signal:
                         message += f" Output data: {output_data_for_signal}"
                else:
                    success = False
                    message = f"{self.success_message_prefix} finished, but success marker not found. MATLAB output: {process.stdout[:200]}"
                    if process.stderr:
                        message += f"\nMATLAB stderr: {process.stderr[:200]}"
            else:
                success = False
                error_output = process.stderr or process.stdout
                message = f"{self.success_message_prefix} failed. MATLAB Error (Return Code {process.returncode}): {error_output[:500]}"
            
            # Emit the original_signal based on its expected signature
            # simulationFinished expects (bool, str, str) after my change
            # codeGenerationFinished expects (bool, str, str)
            self.original_signal.emit(success, message, output_data_for_signal if success else "")

        except subprocess.TimeoutExpired:
            self.original_signal.emit(False, f"{self.success_message_prefix} timed out after 5 minutes.", output_data_for_signal)
        except FileNotFoundError:
             self.original_signal.emit(False, "MATLAB executable not found.", output_data_for_signal)
        except Exception as e:
            self.original_signal.emit(False, f"{self.success_message_prefix} worker error: {str(e)}", output_data_for_signal)
        finally:
            if os.path.exists(self.script_file):
                try:
                    os.remove(self.script_file)
                    os.rmdir(os.path.dirname(self.script_file))
                except OSError as e:
                    print(f"Warning: Could not clean up temp script: {e}") # Log this
            self.finished_signal.emit(True, "", "") # Internal signal for thread cleanup, always emit

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
        mime_data.setText(self.text())
        mime_data.setData(self.mime_type, b"1")
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
                      QGraphicsItem.ItemSendsGeometryChanges)

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
            start_x = self.rect().left() - 20
            start_y = self.rect().center().y()
            end_x = self.rect().left()
            end_y = self.rect().center().y()
            
            line = QLineF(QPointF(start_x, start_y), QPointF(end_x, end_y))
            painter.setPen(QPen(Qt.black, 2))
            painter.drawLine(line)
            
            angle = line.angle()
            arrow_size = 8
            transform = QTransform().rotate(angle - 180) # Angle for arrowhead pointing from start to end
            p1 = line.p2() + transform.map(QPointF(-arrow_size * 0.866, -arrow_size * 0.5))
            p2 = line.p2() + transform.map(QPointF(-arrow_size * 0.866, arrow_size * 0.5))

            painter.setBrush(Qt.black)
            painter.drawPolygon(p1, p2, line.p2())


        if self.is_final:
            painter.setPen(QPen(Qt.black, 1))
            inner_rect = self.rect().adjusted(4, 4, -4, -4)
            painter.drawRect(inner_rect)

        if self.isSelected():
            pen = QPen(Qt.blue, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect().adjusted(-2, -2, 2, 2))

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
        self.setZValue(-1) # Draw transitions behind states
        self.update_path()

    def boundingRect(self):
        # Add some padding to the path's bounding rect for selection and text
        extra = (self.pen().width() + self.arrow_size) / 2.0
        return self.path().boundingRect().adjusted(-extra - 5, -extra - 15, extra + 5, extra + 5)


    def shape(self): # More precise shape for collision detection
        path = QPainterPathStroker()
        path.setWidth(10 + self.pen().width()) # Make selection area wider than line
        return path.createStroke(self.path())


    def update_path(self):
        if not self.start_item or not self.end_item:
            self.setPath(QPainterPath()) # Empty path if items are gone
            return

        # Calculate intersection points with item boundaries
        line = QLineF(self.start_item.sceneBoundingRect().center(), 
                      self.end_item.sceneBoundingRect().center())
        
        start_point = self._get_intersection_point(self.start_item, line)
        end_point = self._get_intersection_point(self.end_item, QLineF(line.p2(), line.p1())) # Reverse line for end item

        if start_point is None: start_point = line.p1() # Fallback
        if end_point is None: end_point = line.p2()     # Fallback

        path = QPainterPath(start_point)

        if self.start_item == self.end_item: # Self-loop
            # Simplified self-loop: draw an arc above the state
            rect = self.start_item.sceneBoundingRect()
            loop_width = rect.width() * 0.6
            loop_height = rect.height() * 0.8
            
            # Anchor points on the state's top edge
            anchor1 = QPointF(rect.center().x() - loop_width / 4, rect.top())
            anchor2 = QPointF(rect.center().x() + loop_width / 4, rect.top())
            
            # Control point for the arc
            ctrl_pt = QPointF(rect.center().x(), rect.top() - loop_height)
            
            path = QPainterPath(anchor1)
            path.quadTo(ctrl_pt, anchor2)
            end_point = anchor2 # Arrowhead will point to anchor2
        else:
            # Add a control point for a slight curve if desired, or just a straight line
            # mid_x = (start_point.x() + end_point.x()) / 2
            # mid_y = (start_point.y() + end_point.y()) / 2
            # ctrl_offset = 30 # Adjust for curve amount
            # # Perpendicular vector for control point
            # dx = end_point.x() - start_point.x()
            # dy = end_point.y() - start_point.y()
            # norm = (dx**2 + dy**2)**0.5
            # if norm > 0:
            #     ctrl_pt = QPointF(mid_x - dy/norm * ctrl_offset, mid_y + dx/norm * ctrl_offset)
            #     path.quadTo(ctrl_pt, end_point)
            # else:
            path.lineTo(end_point)
        
        self.setPath(path)

    def _get_intersection_point(self, item, line):
        """ Helper to find intersection of line with item's bounding rect. """
        item_rect = item.sceneBoundingRect()
        points = []
        
        # Top edge
        top_line = QLineF(item_rect.topLeft(), item_rect.topRight())
        intersect_type, p = line.intersects(top_line)
        if intersect_type == QLineF.BoundedIntersection: points.append(p)
        
        # Bottom edge
        bottom_line = QLineF(item_rect.bottomLeft(), item_rect.bottomRight())
        intersect_type, p = line.intersects(bottom_line)
        if intersect_type == QLineF.BoundedIntersection: points.append(p)

        # Left edge
        left_line = QLineF(item_rect.topLeft(), item_rect.bottomLeft())
        intersect_type, p = line.intersects(left_line)
        if intersect_type == QLineF.BoundedIntersection: points.append(p)

        # Right edge
        right_line = QLineF(item_rect.topRight(), item_rect.bottomRight())
        intersect_type, p = line.intersects(right_line)
        if intersect_type == QLineF.BoundedIntersection: points.append(p)

        # Find closest intersection point to the line's start
        if not points: return item_rect.center() # Fallback

        closest_point = points[0]
        min_dist