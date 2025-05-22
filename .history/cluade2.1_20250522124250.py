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
            s_id_matlab_safe = f"state_{i}"; # Unique safe var name
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
        min_dist_sq = QLineF(line.p1(), closest_point).length()**2
        for pt in points[1:]:
            dist_sq = QLineF(line.p1(), pt).length()**2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_point = pt
        return closest_point


    def paint(self, painter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty():
            return

        painter.setPen(self.pen())
        painter.setBrush(self.brush()) # Should be NoBrush for path typically
        painter.drawPath(self.path())

        # Draw arrowhead
        # Get the last segment of the path for arrowhead direction
        if self.path().elementCount() < 2 : return # Not enough elements for a line

        # For self-loops, the end point is where the arc finishes
        if self.start_item == self.end_item:
            # For quadTo, angleAtPercent(1) should give tangent at end
            angle = self.path().angleAtPercent(1) 
            # Arrow points towards the end of the arc
            line_end_point = self.path().pointAtPercent(1)
            # Adjust angle for arrowhead pointing "into" the node
            # This angle is the tangent of the curve. Arrow should be along this tangent.
            # Arrowhead points towards path end
            transform = QTransform().rotate(angle) 
            arrow_p1 = line_end_point + transform.map(QPointF(-self.arrow_size * 0.866, -self.arrow_size * 0.5))
            arrow_p2 = line_end_point + transform.map(QPointF(-self.arrow_size * 0.866, self.arrow_size * 0.5))

        else: # Straight or simple curved line
            line_end_point = self.path().pointAtPercent(1)
            # Create a short line segment towards the end of the path to get its angle
            # Use pointAtPercent(0.95) and pointAtPercent(1.0)
            p_before_end = self.path().pointAtPercent(0.95)
            angle_line = QLineF(p_before_end, line_end_point)
            if angle_line.length() < 0.01: # Points are too close, use a fallback
                if self.path().elementCount() > 1:
                    p_before_end = self.path().elementAt(self.path().elementCount() - 2) # Second to last point
                    angle_line = QLineF(QPointF(p_before_end.x, p_before_end.y), line_end_point)
                else: return # Cannot determine angle

            angle = angle_line.angle() # Angle of the line segment
            transform = QTransform().rotate(angle - 180) # Angle for arrowhead pointing from start to end
            arrow_p1 = line_end_point + transform.map(QPointF(self.arrow_size * 0.866, self.arrow_size * 0.5))
            arrow_p2 = line_end_point + transform.map(QPointF(self.arrow_size * 0.866, -self.arrow_size * 0.5))
        
        painter.setBrush(Qt.black)
        painter.drawPolygon(arrow_p1, arrow_p2, line_end_point)


        if self.text_label:
            painter.setPen(self._text_color)
            painter.setFont(self._font)
            text_pos = self.path().pointAtPercent(0.5)
            
            # Offset text slightly from the line
            # Calculate a normal to the path at midpoint
            tangent_angle = self.path().angleAtPercent(0.5)
            normal_angle = tangent_angle - 90 # Perpendicular
            offset_dist = 10
            offset_x = offset_dist * QLineF.fromPolar(1, normal_angle).dx() # Using QLineF for cos/sin
            offset_y = offset_dist * QLineF.fromPolar(1, normal_angle).dy()
            text_pos += QPointF(offset_x, offset_y)

            painter.drawText(text_pos, self.text_label)

        if self.isSelected():
            selection_pen = QPen(Qt.blue, 2, Qt.DashLine)
            painter.setPen(selection_pen)
            painter.setBrush(Qt.NoBrush)
            # Draw a slightly larger path for selection emphasis or just use the shape
            stroker = QPainterPathStroker()
            stroker.setWidth(self.pen().width() + 4)
            selection_path = stroker.createStroke(self.path())
            painter.drawPath(selection_path)
    
    def get_data(self):
        return {
            'source': self.start_item.text_label,
            'target': self.end_item.text_label,
            'label': self.text_label
        }
    
    def set_text(self, text):
        self.text_label = text
        self.prepareGeometryChange() # Important if text affects bounding rect
        self.update()

# --- Undo Commands ---
class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item = item
        self.item_data = item.get_data() # Store data for re-creation if needed
        self.item_type = item.type()

        if isinstance(item, GraphicsTransitionItem):
            self.start_item_name = item.start_item.text_label
            self.end_item_name = item.end_item.text_label

    def redo(self):
        # If item was already created and just removed, re-add it.
        # This simple AddItemCommand assumes item is already constructed.
        self.scene.addItem(self.item)
        if isinstance(self.item, GraphicsTransitionItem):
            # Re-find start/end items if scene was cleared or items recreated
            start_node = next((it for it in self.scene.items() if isinstance(it, GraphicsStateItem) and it.text_label == self.start_item_name), None)
            end_node = next((it for it in self.scene.items() if isinstance(it, GraphicsStateItem) and it.text_label == self.end_item_name), None)
            if start_node and end_node:
                self.item.start_item = start_node
                self.item.end_item = end_node
                self.item.update_path()
            else: # Should not happen if states are added before transitions
                 print(f"Warning: Could not fully re-link transition for redo: {self.item_data.get('label')}")


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
        self.items_data = [] 
        
        # Store items in an order: states first, then transitions
        # This helps when re-adding: states must exist before transitions link to them.
        sorted_items = sorted(list(items), key=lambda x: 0 if isinstance(x, GraphicsStateItem) else 1)

        for item in sorted_items:
            data = {'type': item.type(), 'data': item.get_data(), 'item_instance': item}
            if isinstance(item, GraphicsTransitionItem):
                data['start_item_name'] = item.start_item.text_label
                data['end_item_name'] = item.end_item.text_label
            self.items_data.append(data)
        
    def redo(self): # Actually remove
        for item_d in self.items_data:
            # Check if item is still in scene (it should be if this is a redo after an undo)
            if item_d['item_instance'].scene() == self.scene:
                self.scene.removeItem(item_d['item_instance'])
        self.scene.set_dirty(True)

    def undo(self): # Re-add
        recreated_states_map = {}
        for item_d in self.items_data:
            item_instance = item_d['item_instance']
            if item_instance.scene() is None: # Only add if not already in scene
                self.scene.addItem(item_instance)
            
            if isinstance(item_instance, GraphicsStateItem):
                recreated_states_map[item_instance.text_label] = item_instance

        # Second pass for transitions to ensure states are linked
        for item_d in self.items_data:
            item_instance = item_d['item_instance']
            if isinstance(item_instance, GraphicsTransitionItem):
                start_node = recreated_states_map.get(item_d['start_item_name'])
                end_node = recreated_states_map.get(item_d['end_item_name'])
                if start_node and end_node:
                    item_instance.start_item = start_node
                    item_instance.end_item = end_node
                    item_instance.update_path()
                else:
                    print(f"Warning: Could not re-link transition for undo: {item_d['data'].get('label')}")
        self.scene.set_dirty(True)


class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_positions_new, description="Move Items"):
        super().__init__(description)
        # items_positions_new is a list of (item_instance, QPointF_new_position)
        self.items_positions_new = items_positions_new
        self.items_positions_old = []
        for item, _ in self.items_positions_new:
            self.items_positions_old.append((item, item.pos())) # Store item and its old position

    def redo(self):
        for item, new_pos in self.items_positions_new:
            item.setPos(new_pos)
        self.scene().set_dirty(True) # Access scene via one of the items
    
    def undo(self):
        for item, old_pos in self.items_positions_old:
            item.setPos(old_pos)
        self.scene().set_dirty(True)

    def scene(self): # Helper to get scene reference
        if self.items_positions_new:
            return self.items_positions_new[0][0].scene()
        return None

# --- Diagram Scene ---
class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool)

    def __init__(self, undo_stack, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 3000, 2000)
        self.current_mode = "select"
        self.transition_start_item = None
        self.log_function = print
        self.undo_stack = undo_stack
        self._dirty = False
        self._mouse_press_items_positions = {}

        self.item_moved.connect(self._handle_item_moved)
        self.setBackgroundBrush(QColor(240, 240, 240))

    def set_dirty(self, dirty=True):
        if self._dirty != dirty:
            self._dirty = dirty
            self.modifiedStatusChanged.emit(dirty)
            
    def is_dirty(self):
        return self._dirty

    def set_log_function(self, log_function):
        self.log_function = log_function

    def set_mode(self, mode):
        old_mode = self.current_mode
        self.current_mode = mode
        self.transition_start_item = None 
        if mode == "select":
            QApplication.setOverrideCursor(Qt.ArrowCursor)
        elif mode in ["state", "transition"]:
            QApplication.setOverrideCursor(Qt.CrossCursor)
        else: # If mode is neither, or changing away from special cursor mode
            if old_mode in ["state", "transition"] and mode != old_mode:
                QApplication.restoreOverrideCursor()

    def select_all(self):
        """Select all items in the scene"""
        for item in self.items():
            item.setSelected(True)

    def _handle_item_moved(self, moved_item):
        if isinstance(moved_item, GraphicsStateItem):
            # Find all transitions connected to this state and update their paths
            for item in self.items():
                if isinstance(item, GraphicsTransitionItem):
                    if item.start_item == moved_item or item.end_item == moved_item:
                        item.update_path()
        # self.set_dirty() # Move command will handle dirtying

    def mousePressEvent(self, event):
        pos = event.scenePos()
        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                self._add_state_item(pos)
            elif self.current_mode == "transition":
                item_at_pos = self.itemAt(pos, QTransform())
                # Prefer selecting state items even if transition is on top
                state_items_under_cursor = [it for it in self.items(pos) if isinstance(it, GraphicsStateItem)]
                if state_items_under_cursor:
                    item_at_pos = state_items_under_cursor[0] # Take the first one (topmost state)

                if isinstance(item_at_pos, GraphicsStateItem):
                    self._handle_transition_click(item_at_pos)
                else: 
                    self.transition_start_item = None
                    self.log_function("Transition drawing cancelled (clicked empty space).")
            else: # Select mode
                super().mousePressEvent(event)
                self._mouse_press_items_positions.clear()
                # Only store positions for movable items
                for item in self.selectedItems():
                    if item.flags() & QGraphicsItem.ItemIsMovable:
                         self._mouse_press_items_positions[item] = item.pos()
                return # Important to return here for select mode
        else: 
            super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            moved_items_data = []
            for item, old_pos in self._mouse_press_items_positions.items():
                if item.pos() != old_pos : 
                    moved_items_data.append((item, item.pos())) 
            
            if moved_items_data:
                cmd = MoveItemsCommand(moved_items_data)
                self.undo_stack.push(cmd)
                # self.set_dirty() # MoveCommand will set dirty
            self._mouse_press_items_positions.clear()

        super().mouseReleaseEvent(event)


    def _add_state_item(self, pos, name_prefix="State"):
        # Generate a unique default name
        i = 1
        while any(isinstance(item, GraphicsStateItem) and item.text_label == f"{name_prefix}{i}" for item in self.items()):
            i += 1
        default_name = f"{name_prefix}{i}"

        state_name, ok = QInputDialog.getText(None, "New State", "Enter state name:", text=default_name)
        if ok and state_name:
            if any(isinstance(item, GraphicsStateItem) and item.text_label == state_name for item in self.items()):
                QMessageBox.warning(None, "Duplicate Name", f"A state with the name '{state_name}' already exists.")
                return

            props_dialog = StatePropertiesDialog(state_name)
            if props_dialog.exec_() == QDialog.Accepted:
                new_state = GraphicsStateItem(
                    pos.x() - 60, pos.y() - 30, 120, 60,
                    props_dialog.get_name(),
                    props_dialog.is_initial_cb.isChecked(),
                    props_dialog.is_final_cb.isChecked()
                )
                cmd = AddItemCommand(self, new_state, "Add State")
                self.undo_stack.push(cmd)
                self.log_function(f"Added state: {new_state.text_label}")
        self.set_mode("select")

    def _handle_transition_click(self, clicked_state_item):
        if not self.transition_start_item:
            self.transition_start_item = clicked_state_item
            self.log_function(f"Transition started from: {clicked_state_item.text_label}")
        else:
            label, ok = QInputDialog.getText(None, "New Transition", "Enter transition label (optional):")
            if ok: 
                new_transition = GraphicsTransitionItem(self.transition_start_item, clicked_state_item, label)
                cmd = AddItemCommand(self, new_transition, "Add Transition")
                self.undo_stack.push(cmd)
                self.log_function(f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{label}]")
            
            self.transition_start_item = None 
            self.set_mode("select") 

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            selected = self.selectedItems()
            if selected:
                # Collect all transitions connected to states being deleted, if those transitions are not also selected
                items_to_delete = set(selected)
                for item in list(selected): # Iterate on a copy
                    if isinstance(item, GraphicsStateItem):
                        for scene_item in self.items():
                            if isinstance(scene_item, GraphicsTransitionItem):
                                if scene_item.start_item == item or scene_item.end_item == item:
                                    items_to_delete.add(scene_item) # Also mark connected transition for deletion
                
                if items_to_delete:
                    cmd = RemoveItemsCommand(self, list(items_to_delete), "Delete Items")
                    self.undo_stack.push(cmd)
                    self.log_function(f"Deleted {len(items_to_delete)} item(s).")
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
        if event.mimeData().hasFormat("application/x-state-tool"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-state-tool"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        pos = event.scenePos()
        if event.mimeData().hasFormat("application/x-state-tool"):
            dropped_text = event.mimeData().text() # e.g., "State"
            self._add_state_item(pos, name_prefix=dropped_text or "State")
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def get_diagram_data(self):
        data = {'states': [], 'transitions': []} 
        for item in self.items():
            if isinstance(item, GraphicsStateItem):
                data['states'].append(item.get_data())
            elif isinstance(item, GraphicsTransitionItem):
                data['transitions'].append(item.get_data())
        return data

    def load_diagram_data(self, data):
        self.clear() 
        
        current_dirty_state = self._dirty
        self.set_dirty(False)

        state_items_map = {} 

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
                self.log_function(f"Warning: Could not link transition '{trans_data.get('label')}' due to missing states: {trans_data['source']} or {trans_data['target']}.")
        
        self.set_dirty(False) # Loaded file is considered not dirty
        self.undo_stack.clear()

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

class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings")
        self.setMinimumWidth(500)

        main_layout = QVBoxLayout(self)

        path_group = QGroupBox("MATLAB Executable Path")
        path_form_layout = QFormLayout() # Use QFormLayout for path_edit and its label
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path)
        path_form_layout.addRow("Path:", self.path_edit)
        
        btn_layout = QHBoxLayout()
        auto_detect_btn = QPushButton("Auto-detect")
        auto_detect_btn.clicked.connect(self._auto_detect)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        btn_layout.addWidget(auto_detect_btn)
        btn_layout.addWidget(browse_btn)
        btn_layout.addStretch() # Push buttons to the left
        
        path_v_layout = QVBoxLayout() # QVBoxLayout to hold form and button layout
        path_v_layout.addLayout(path_form_layout)
        path_v_layout.addLayout(btn_layout)
        path_group.setLayout(path_v_layout)
        main_layout.addWidget(path_group)


        test_group = QGroupBox("Connection Test")
        test_layout = QVBoxLayout()
        self.test_status_label = QLabel("Status: Unknown")
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_connection_and_update_label) # Connect to new method
        test_layout.addWidget(test_btn)
        test_layout.addWidget(self.test_status_label)
        test_group.setLayout(test_layout)
        main_layout.addWidget(test_group)

        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.accepted.connect(self._apply_settings)
        dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)
        
        # Listen to external connection status changes to update our label too
        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        self._update_test_label_from_signal(self.matlab_connection.connected, "Current status.")


    def _auto_detect(self):
        self.test_status_label.setText("Status: Auto-detecting...")
        QApplication.processEvents()
        if self.matlab_connection.detect_matlab(): # This will emit signal
            self.path_edit.setText(self.matlab_connection.matlab_path)
            # Signal handler _update_test_label_from_signal will update the label
        else:
            # detect_matlab emits (False, "Auto-detection failed.")
            pass # Label updated by signal

    def _browse(self):
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", "", exe_filter)
        if path:
            self.path_edit.setText(path)
            self.test_status_label.setText("Status: Path selected. Test or Apply to confirm.")
            self.test_status_label.setStyleSheet("") # Reset color

    def _test_connection_and_update_label(self):
        path = self.path_edit.text()
        if not path:
            self._update_test_label_from_signal(False, "Path is empty.")
            return

        self.test_status_label.setText("Status: Testing...")
        self.test_status_label.setStyleSheet("")
        QApplication.processEvents()
        
        # Temporarily set path in connection object for testing
        # The test_connection method will emit connectionStatusChanged
        current_path_in_connection = self.matlab_connection.matlab_path
        self.matlab_connection.set_matlab_path(path) # Attempt to set it
        
        if self.matlab_connection.connected: # If set_matlab_path thought it was valid
            self.matlab_connection.test_connection() # This will emit signal
        else: # set_matlab_path failed (e.g. path doesn't exist)
            # set_matlab_path already emitted its failure signal
             pass

        # If the test changed the connection's actual path, and we don't want that yet, revert.
        # However, test_connection itself might set self.connected = False
        # The OK button is what makes the change permanent.
        # So, we might need to restore the connection's state if test failed.
        if not self.matlab_connection.connected: # if test resulted in a disconnected state
            self.matlab_connection.set_matlab_path(current_path_in_connection) # Restore previous valid path if any


    def _update_test_label_from_signal(self, success, message):
        # This is a slot connected to matlab_connection.connectionStatusChanged
        status_text = "Status: " + ("Success: " if success else "Failed: ") + message
        self.test_status_label.setText(status_text)
        self.test_status_label.setStyleSheet("color: green;" if success else "color: red;")

    def _apply_settings(self):
        path = self.path_edit.text()
        # set_matlab_path will emit the signal, which updates the main window's status
        if not self.matlab_connection.set_matlab_path(path) and path:
            # If setting path failed (e.g., non-existent file) and path was not empty
            QMessageBox.warning(self, "Invalid Path", "The specified MATLAB path is invalid or not executable.")
            self.reject() # Keep dialog open or handle as error
            return
        
        if self.matlab_connection.connected: # If path seems valid
            if not self.matlab_connection.test_connection(): # Test it
                QMessageBox.warning(self, "MATLAB Connection", 
                                    "MATLAB path was set, but the connection test failed. "
                                    "Please verify the path and your MATLAB installation.")
                # Do not close dialog on failed test after apply, let user correct
                # self.reject() 
                # return
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
        self.scene.modifiedStatusChanged.connect(self.setWindowModified)
        self.scene.modifiedStatusChanged.connect(self._update_save_actions)


        self.init_ui()
        self._update_matlab_status_display(False, "Not Connected. Configure in Simulation menu.")
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_process_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_process_finished) # Use same handler

        self.setWindowTitle(f"Brain State Machine Designer")
        self._update_window_title() # Initial title update

    def init_ui(self):
        self.setGeometry(100, 100, 1400, 900)
        
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_docks()
        self._create_central_widget()
        self._update_save_actions()
        self._update_matlab_actions_enabled_state() # Initial state of MATLAB actions

    def _create_actions(self):
        self.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon), "&New", self, shortcut="Ctrl+N", triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton), "&Open...", self, shortcut="Ctrl+O", triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton), "&Save", self, shortcut="Ctrl+S", triggered=self.on_save_file)
        self.save_as_action = QAction("Save &As...", self, triggered=self.on_save_file_as)
        self.export_matlab_action = QAction("Export to MATLAB...", self, triggered=self.on_export_matlab)
        self.exit_action = QAction("E&xit", self, shortcut="Ctrl+Q", triggered=self.close)

        # Edit actions
        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowLeft))
        
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowRight))
        
        self.select_all_action = QAction("Select &All", self, shortcut="Ctrl+A", triggered=self.scene.select_all)
        self.delete_action = QAction("&Delete", self, shortcut="Delete", triggered=self.on_delete_selected)

        # View actions
        self.zoom_in_action = QAction("Zoom &In", self, shortcut="Ctrl+=", triggered=self.on_zoom_in)
        self.zoom_out_action = QAction("Zoom &Out", self, shortcut="Ctrl+-", triggered=self.on_zoom_out)
        self.zoom_fit_action = QAction("&Fit to Window", self, shortcut="Ctrl+0", triggered=self.on_zoom_fit)

        # Mode actions - create action group for mutual exclusivity
        self.mode_group = QActionGroup(self)
        self.select_mode_action = QAction("&Select", self, checkable=True, checked=True)
        self.select_mode_action.triggered.connect(lambda: self.scene.set_mode("select"))
        self.mode_group.addAction(self.select_mode_action)

        self.state_mode_action = QAction("Add &State", self, checkable=True)
        self.state_mode_action.triggered.connect(lambda: self.scene.set_mode("state"))
        self.mode_group.addAction(self.state_mode_action)

        self.transition_mode_action = QAction("Add &Transition", self, checkable=True)  
        self.transition_mode_action.triggered.connect(lambda: self.scene.set_mode("transition"))
        self.mode_group.addAction(self.transition_mode_action)

        # MATLAB/Simulation actions
        self.matlab_settings_action = QAction("MATLAB &Settings...", self, triggered=self.on_matlab_settings)
        self.generate_model_action = QAction("&Generate Simulink Model...", self, triggered=self.on_generate_model)
        self.run_simulation_action = QAction("&Run Simulation...", self, triggered=self.on_run_simulation)
        self.generate_code_action = QAction("Generate &Code...", self, triggered=self.on_generate_code)

        # Help actions
        self.about_action = QAction("&About", self, triggered=self.on_about)

    def _create_menus(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_matlab_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.select_all_action)
        edit_menu.addAction(self.delete_action)

        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addAction(self.zoom_fit_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        tools_menu.addAction(self.select_mode_action)
        tools_menu.addAction(self.state_mode_action)
        tools_menu.addAction(self.transition_mode_action)

        # Simulation menu
        simulation_menu = menubar.addMenu("&Simulation")
        simulation_menu.addAction(self.matlab_settings_action)
        simulation_menu.addSeparator()
        simulation_menu.addAction(self.generate_model_action)
        simulation_menu.addAction(self.run_simulation_action)
        simulation_menu.addAction(self.generate_code_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        # Main toolbar
        main_toolbar = self.addToolBar("Main")
        main_toolbar.addAction(self.new_action)
        main_toolbar.addAction(self.open_action)
        main_toolbar.addAction(self.save_action)
        main_toolbar.addSeparator()
        main_toolbar.addAction(self.undo_action)
        main_toolbar.addAction(self.redo_action)

        # Mode toolbar
        mode_toolbar = self.addToolBar("Mode")
        mode_toolbar.addAction(self.select_mode_action)
        mode_toolbar.addAction(self.state_mode_action)
        mode_toolbar.addAction(self.transition_mode_action)

        # View toolbar
        view_toolbar = self.addToolBar("View")
        view_toolbar.addAction(self.zoom_in_action)
        view_toolbar.addAction(self.zoom_out_action)
        view_toolbar.addAction(self.zoom_fit_action)

    def _create_status_bar(self):
        self.status_bar = self.statusBar()
        self.mode_label = QLabel("Mode: Select")
        self.matlab_status_label = QLabel("MATLAB: Not Connected")
        
        self.status_bar.addWidget(self.mode_label)
        self.status_bar.addPermanentWidget(self.matlab_status_label)

        # Connect mode changes to status update
        self.scene.current_mode = "select"  # Initialize
        for action in self.mode_group.actions():
            action.triggered.connect(self._update_mode_status)

    def _create_docks(self):
        # Toolbox dock
        toolbox_dock = QDockWidget("Toolbox", self)
        toolbox_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        toolbox_widget = QWidget()
        toolbox_layout = QVBoxLayout(toolbox_widget)
        
        # Add draggable state button
        state_button = DraggableToolButton(
            "State", "application/x-state-tool",
            "background-color: lightblue; border: 1px solid black;"
        )
        toolbox_layout.addWidget(state_button)
        toolbox_layout.addStretch()
        
        toolbox_dock.setWidget(toolbox_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, toolbox_dock)

        # Properties dock
        properties_dock = QDockWidget("Properties", self)
        properties_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        self.properties_widget = QWidget()
        self.properties_layout = QVBoxLayout(self.properties_widget)
        self.properties_layout.addWidget(QLabel("Select an item to view properties"))
        self.properties_layout.addStretch()
        
        properties_dock.setWidget(self.properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, properties_dock)

        # Log dock
        log_dock = QDockWidget("Log", self)
        log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        
        log_dock.setWidget(self.log_text)
        self.addDockWidget(Qt.BottomDockWidgetArea, log_dock)

    def _create_central_widget(self):
        self.graphics_view = QGraphicsView(self.scene)
        self.graphics_view.setDragMode(QGraphicsView.RubberBandDrag)
        self.graphics_view.setRenderHint(QPainter.Antialiasing)
        self.setCentralWidget(self.graphics_view)

    def _update_save_actions(self):
        """Update the enabled state of save actions based on file state"""
        has_content = bool(self.scene.items())
        self.save_action.setEnabled(self.scene.is_dirty())
        self.save_as_action.setEnabled(has_content)
        self.export_matlab_action.setEnabled(has_content)

    def _update_matlab_actions_enabled_state(self):
        """Update enabled state of MATLAB-dependent actions"""
        connected = self.matlab_connection.connected
        has_content = bool(self.scene.items())
        
        self.generate_model_action.setEnabled(connected and has_content)
        self.run_simulation_action.setEnabled(connected)
        self.generate_code_action.setEnabled(connected)

    def _update_matlab_status_display(self, success, message):
        """Update MATLAB connection status in UI"""
        status_text = f"MATLAB: {'Connected' if success else 'Disconnected'}"
        self.matlab_status_label.setText(status_text)
        self.matlab_status_label.setStyleSheet(
            "color: green;" if success else "color: red;"
        )
        self.log_message(f"MATLAB: {message}")
        self._update_matlab_actions_enabled_state()

    def _update_mode_status(self):
        """Update mode display in status bar"""
        if self.select_mode_action.isChecked():
            mode = "Select"
        elif self.state_mode_action.isChecked():
            mode = "Add State"
        elif self.transition_mode_action.isChecked():
            mode = "Add Transition"
        else:
            mode = "Unknown"
        
        self.mode_label.setText(f"Mode: {mode}")

    def _update_window_title(self):
        """Update window title with current file info"""
        title = "Brain State Machine Designer"
        if self.current_file_path:
            filename = os.path.basename(self.current_file_path)
            title = f"{filename} - {title}"
        
        if self.scene.is_dirty():
            title = f"*{title}"
            
        self.setWindowTitle(title)

    def log_message(self, message):
        """Add a message to the log"""
        self.log_text.append(f"[{QDateTime.currentDateTime().toString()}] {message}")

    def _handle_matlab_process_finished(self, success, message, data=""):
        """Handle completion of MATLAB processes"""
        if success:
            self.log_message(f"Success: {message}")
            if data:
                self.log_message(f"Output: {data}")
        else:
            self.log_message(f"Error: {message}")
            QMessageBox.warning(self, "MATLAB Process Failed", message)

    # File operations
    def on_new_file(self):
        if self._check_save_changes():
            self.scene.clear()
            self.current_file_path = None
            self.scene.set_dirty(False)
            self._update_window_title()
            self.log_message("New file created")

    def on_open_file(self):
        if not self._check_save_changes():
            return
            
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Brain State Machine", "", FILE_FILTER
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                self.scene.load_diagram_data(data)
                self.current_file_path = file_path
                self._update_window_title()
                self.log_message(f"Opened: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file:\n{str(e)}")
                self.log_message(f"Failed to open {file_path}: {str(e)}")

    def on_save_file(self):
        if self.current_file_path:
            self._save_to_file(self.current_file_path)
        else:
            self.on_save_file_as()

    def on_save_file_as(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Brain State Machine", "", FILE_FILTER
        )
        
        if file_path:
            if not file_path.endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION
            self._save_to_file(file_path)

    def _save_to_file(self, file_path):
        try:
            data = self.scene.get_diagram_data()
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.current_file_path = file_path
            self.scene.set_dirty(False)
            self._update_window_title()
            self.log_message(f"Saved: {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{str(e)}")
            self.log_message(f"Failed to save {file_path}: {str(e)}")

    def _check_save_changes(self):
        """Check if user wants to save changes before proceeding"""
        if not self.scene.is_dirty():
            return True
            
        reply = QMessageBox.question(
            self, "Unsaved Changes",
            "The document has unsaved changes. Do you want to save them?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Save:
            self.on_save_file()
            return not self.scene.is_dirty()  # Return True if save succeeded
        elif reply == QMessageBox.Discard:
            return True
        else:  # Cancel
            return False

    # Edit operations
    def on_delete_selected(self):
        selected = self.scene.selectedItems()
        if selected:
            # Let the scene handle the deletion (it will use undo commands)
            self.scene.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))

    # View operations
    def on_zoom_in(self):
        self.graphics_view.scale(1.2, 1.2)

    def on_zoom_out(self):
        self.graphics_view.scale(0.8, 0.8)

    def on_zoom_fit(self):
        self.graphics_view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    # MATLAB operations
    def on_matlab_settings(self):
        dialog = MatlabSettingsDialog(self.matlab_connection, self)
        dialog.exec_()

    def on_generate_model(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", 
                              "Please configure MATLAB connection first.")
            return

        data = self.scene.get_diagram_data()
        if not data['states']:
            QMessageBox.information(self, "No States", "Add some states first.")
            return

        # Get output directory
        output_dir = QFileDialog.getExistingDirectory(
            self, "Select Output Directory"
        )
        if not output_dir:
            return

        # Get model name
        model_name, ok = QInputDialog.getText(
            self, "Model Name", "Enter Simulink model name:", text="BrainStateMachine"
        )
        if not ok or not model_name:
            return

        self.log_message(f"Generating Simulink model: {model_name}")
        success = self.matlab_connection.generate_simulink_model(
            data['states'], data['transitions'], {}, output_dir, model_name
        )
        
        if not success:
            QMessageBox.warning(self, "Generation Failed", 
                              "Failed to start model generation process.")

    def on_run_simulation(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", 
                              "Please configure MATLAB connection first.")
            return

        # Get model file
        model_path, _ = QFileDialog.getOpenFileName(
            self, "Select Simulink Model", "", "Simulink Models (*.slx *.mdl);;All Files (*)"
        )
        if not model_path:
            return

        # Get simulation time
        sim_time, ok = QInputDialog.getDouble(
            self, "Simulation Time", "Enter simulation time (seconds):", 
            value=10.0, min=0.1, max=1000.0, decimals=1
        )
        if not ok:
            return

        self.log_message(f"Running simulation: {os.path.basename(model_path)}")
        success = self.matlab_connection.run_simulation(model_path, sim_time)
        
        if not success:
            QMessageBox.warning(self, "Simulation Failed", 
                              "Failed to start simulation process.")

    def on_generate_code(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", 
                              "Please configure MATLAB connection first.")
            return

        # Get model file
        model_path, _ = QFileDialog.getOpenFileName(
            self, "Select Simulink Model", "", "Simulink Models (*.slx *.mdl);;All Files (*)"
        )
        if not model_path:
            return

        # Get output directory
        output_dir = QFileDialog.getExistingDirectory(
            self, "Select Code Output Directory"
        )
        if not output_dir:
            return

        # Get language choice
        languages = ["C++", "C"]
        language, ok = QInputDialog.getItem(
            self, "Target Language", "Select target language:", languages, 0, False
        )
        if not ok:
            return

        self.log_message(f"Generating {language} code for: {os.path.basename(model_path)}")
        success = self.matlab_connection.generate_code(model_path, language, output_dir)
        
        if not success:
            QMessageBox.warning(self, "Code Generation Failed", 
                              "Failed to start code generation process.")

    def on_export_matlab(self):
        """Export current diagram to MATLAB script format"""
        data = self.scene.get_diagram_data()
        if not data['states']:
            QMessageBox.information(self, "No States", "Add some states first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to MATLAB Script", "", "MATLAB Scripts (*.m);;All Files (*)"
        )
        
        if file_path:
            try:
                self._export_to_matlab_script(data, file_path)
                self.log_message(f"Exported to MATLAB script: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to export:\n{str(e)}")

    def _export_to_matlab_script(self, data, file_path):
        """Generate MATLAB script from diagram data"""
        with open(file_path, 'w') as f:
            f.write("% Brain State Machine MATLAB Script\n")
            f.write("% Generated from Brain State Machine Designer\n\n")
            
            f.write("% States:\n")
            for i, state in enumerate(data['states']):
                f.write(f"% {i+1}. {state['name']}")
                if state.get('is_initial'):
                    f.write(" (Initial)")
                if state.get('is_final'):
                    f.write(" (Final)")
                f.write(f" - Position: ({state['x']:.0f}, {state['y']:.0f})\n")
            
            f.write("\n% Transitions:\n")
            for i, trans in enumerate(data['transitions']):
                label = trans.get('label', '')
                f.write(f"% {i+1}. {trans['source']} -> {trans['target']}")
                if label:
                    f.write(f" [{label}]")
                f.write("\n")
            
            f.write("\n% TODO: Add your MATLAB state machine implementation here\n")

    def on_about(self):
        QMessageBox.about(self, "About Brain State Machine Designer",
                         f"Brain State Machine Designer v{APP_VERSION}\n\n"
                         "A visual tool for designing brain state machines\n"
                         "with MATLAB/Simulink integration.")

    def closeEvent(self, event):
        if self._check_save_changes():
            event.accept()
        else:
            event.ignore()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Brain State Machine Designer")
    app.setApplicationVersion(APP_VERSION)
    
    # Set application icon if available
    try:
        app.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon))
    except:
        pass
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()