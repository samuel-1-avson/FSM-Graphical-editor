
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
    QGroupBox, QUndoStack, QUndoCommand, QStyle, QSizePolicy, QGraphicsLineItem,
    QToolButton # Added QToolButton
)
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform, QKeyEvent, QPainterPathStroker, QPolygonF
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QTimer, QSize # Added QSize
)
import math


# --- Configuration ---
APP_VERSION = "1.1"
APP_NAME = "Brain State Machine Designer"
FILE_EXTENSION = ".bsm"
FILE_FILTER = f"Brain State Machine Files (*{FILE_EXTENSION});;All Files (*)"

# --- Utility Functions ---
def get_standard_icon(standard_pixmap_enum_value, fallback_text=None):
    # standard_pixmap_enum_value is now the actual enum value (e.g., QStyle.SP_FileIcon)
    icon = QIcon() # Default to empty icon
    try:
        # This call itself should handle invalid enum values gracefully by returning a null icon.
        icon = QApplication.style().standardIcon(standard_pixmap_enum_value)
    except Exception as e: # Catch any unexpected error during icon retrieval
        print(f"Warning: Error getting standard icon for enum value {standard_pixmap_enum_value}: {e}")
        icon = QIcon() # Ensure icon is QIcon instance
    
    if icon.isNull():
        if fallback_text:
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.drawText(pixmap.rect(), Qt.AlignCenter, fallback_text[:2])
            painter.end()
            return QIcon(pixmap)
        else:
            # Fallback to a very generic icon if everything fails
            # This is a last resort to ensure a QIcon is always returned
            # For example, a small colored square
            pixmap = QPixmap(16,16)
            pixmap.fill(QColor(192,192,192)) # Light gray
            painter = QPainter(pixmap)
            painter.setPen(Qt.black)
            painter.drawRect(0,0,15,15)
            if fallback_text:
                 painter.drawText(pixmap.rect(), Qt.AlignCenter, fallback_text[0] if fallback_text else "?")
            painter.end()
            return QIcon(pixmap)
    return icon

# --- MATLAB Connection Handling ---
class MatlabConnection(QObject):
    """Class to handle MATLAB connectivity"""
    connectionStatusChanged = pyqtSignal(bool, str)  # success, message
    simulationFinished = pyqtSignal(bool, str, str)      # success, message, data (model_path or general message)
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
            versions = ['R2024a', 'R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b']
            for v in versions:
                paths.append(os.path.join(program_files, 'MATLAB', v, 'bin', 'matlab.exe'))
        elif sys.platform == 'darwin':
            versions = ['R2024a', 'R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b']
            for v in versions:
                paths.append(f'/Applications/MATLAB_{v}.app/bin/matlab')
        else:  # Linux
            versions = ['R2024a', 'R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b']
            for v in versions:
                paths.append(f'/usr/local/MATLAB/{v}/bin/matlab')

        for path in paths:
            if os.path.exists(path):
                if self.set_matlab_path(path): # Use set_matlab_path to also emit signal
                    return True
        self.connectionStatusChanged.emit(False, "MATLAB auto-detection failed.")
        return False

    def _run_matlab_script(self, script_content, worker_signal, success_message_prefix):
        if not self.connected:
            worker_signal.emit(False, "MATLAB not connected.", "")
            return

        temp_dir = tempfile.mkdtemp(prefix="bsm_matlab_")
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
        
        self._active_threads.append(thread)
        thread.finished.connect(lambda t=thread: self._active_threads.remove(t) if t in self._active_threads else None)
        
        thread.start()


    def generate_simulink_model(self, states, transitions, output_dir, model_name="BrainStateMachine"):
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected.", "") 
            return False

        slx_file_path = os.path.join(output_dir, f"{model_name}.slx").replace('\\', '/')

        script_lines = [
            f"% Auto-generated Simulink model script for {model_name}",
            f"disp('Starting Simulink model generation for {model_name}...');",
            f"modelName = '{model_name}';",
            f"outputModelPath = '{slx_file_path}';",
            "try",
            "    if exist(outputModelPath, 'file'), delete(outputModelPath); end", 
            "    if bdIsLoaded(modelName), close_system(modelName, 0); end",
            "    new_system(modelName);",
            "    open_system(modelName);",
            # Ensure Stateflow chart is added to the model, not as a standalone
            "    root = sfroot;",
            "    machine = root.find('-isa', 'Stateflow.Machine', 'Name', modelName);",
            "    if isempty(machine)",
            "        machine = Stateflow.Machine(modelName);", # This might not be needed if new_system creates one
            "    end",
            "    sfChart = Stateflow.Chart(machine);", # Add chart to machine associated with model
            "    sfChart.Name = 'BrainStateMachineChart';",
            # Add chart to Simulink model as a block
            "    chartBlockPath = [modelName '/Stateflow Chart'];",
            "    Simulink.SubSystem.deleteContents(modelName);", # Clear model before adding chart
            "    sfChartHandle = sfnew(modelName);", # Creates a new chart block and returns its handle
            "    set_param(sfChartHandle, 'Name', 'BrainStateMachineChart');", # Rename the block if desired
            # Get the chart object from the handle
            "    chartObj = get_param(sfChartHandle, 'Object').find('-isa','Stateflow.Chart');",

            "    stateHandles = containers.Map('KeyType','char','ValueType','any');"
        ]

        for i, state in enumerate(states):
            s_name_matlab = state['name'].replace("'", "''") 
            s_id_matlab_safe = f"state_{i}_{state['name'].replace(' ', '_').replace('-', '_')}";
            s_id_matlab_safe = ''.join(filter(str.isalnum, s_id_matlab_safe))
            if not s_id_matlab_safe or not s_id_matlab_safe[0].isalpha(): s_id_matlab_safe = 's_' + s_id_matlab_safe


            script_lines.extend([
                f"{s_id_matlab_safe} = Stateflow.State(chartObj);", # Use chartObj
                f"{s_id_matlab_safe}.Name = '{s_name_matlab}';",
                f"{s_id_matlab_safe}.Position = [{state['x']/5}, {state['y']/5}, {state['width']/5}, {state['height']/5}];",
                f"stateHandles('{s_name_matlab}') = {s_id_matlab_safe};"
            ])
            if state.get('is_initial', False):
                script_lines.append(f"defaultTransition_{i} = Stateflow.Transition(chartObj);") # Use chartObj
                script_lines.append(f"defaultTransition_{i}.Destination = {s_id_matlab_safe};")
                script_lines.append(f"defaultTransition_{i}.Source = [];") # Default transition has no source state

        for i, trans in enumerate(transitions):
            src_name_matlab = trans['source'].replace("'", "''")
            dst_name_matlab = trans['target'].replace("'", "''")
            t_label_matlab = trans['label'].replace("'", "''") if trans.get('label') else ''
            
            script_lines.extend([
                f"if isKey(stateHandles, '{src_name_matlab}') && isKey(stateHandles, '{dst_name_matlab}')",
                f"    t{i} = Stateflow.Transition(chartObj);", # Use chartObj
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
            "    close_system(modelName, 0);", # Close without saving, as it's already saved
            "    disp(['Simulink model saved to: ', outputModelPath]);",
            "    fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', outputModelPath);", 
            "catch e",
            "    disp(['Error during Simulink model generation: ', getReport(e, 'extended')]);",
            "    if bdIsLoaded(modelName), close_system(modelName, 0); end",  
            "    rethrow(e);",
            "end"
        ])
        
        script_content = "\n".join(script_lines)
        self._run_matlab_script(script_content, self.simulationFinished, "Model generation")
        return True 

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
            disp(['Simulating model: ', modelName, ' for ', num2str({sim_time}), ' seconds.']);
            simOut = sim(modelName, 'StopTime', num2str({sim_time})); % Pass StopTime to sim command
            disp('Simulation completed successfully.');
            % You might want to pass some results back via output_data_for_signal
            % For example, if simOut contains relevant data, serialize it or save to a file.
            % For now, just a success message.
            fprintf('MATLAB_SCRIPT_SUCCESS:Simulation finished for %s.\\n', modelName);
        catch e
            disp(['Simulation error: ', getReport(e, 'extended')]);
            if bdIsLoaded(modelName), close_system(modelName, 0); end 
            rethrow(e); 
        end
        if bdIsLoaded(modelName), close_system(modelName, 0); end % Close without saving changes
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
            output_dir_base = os.path.dirname(model_path) # Default to model's directory
        # Ensure a unique folder for codegen, e.g., modelName_ert_rtw
        # Simulink often creates subfolders like 'modelName_ert_rtw' by default.
        # Let's let Simulink manage the exact subfolder name within output_dir_base.
        output_dir_matlab_codegen_root = os.path.join(output_dir_base, f"{model_name}_codegen_output").replace('\\', '/')


        script_content = f"""
        disp('Starting code generation...');
        modelPath = '{model_path_matlab}';
        modelName = '{model_name}';
        codeGenBaseDir = '{output_dir_matlab_codegen_root}'; % Base for slbuild output
        
        try
            load_system(modelPath);
            
            % Configure for ERT (Embedded Coder)
            set_param(modelName,'SystemTargetFile','ert.tlc'); 
            set_param(modelName,'GenerateMakefile','on'); % Typically needed for ERT
            % set_param(modelName,'MakeCommand','make_rtw'); % Default, usually okay

            cfg = getActiveConfigSet(modelName);
            if strcmpi('{language}', 'C++')
                set_param(cfg, 'TargetLang', 'C++');
                % For C++, ensure C++ specific settings if needed, e.g., class interface
                set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'C++ class'); 
                set_param(cfg.getComponent('Code Generation'),'TargetLangStandard', 'C++11 (ISO)'); % Example
                disp('Configured for C++ code generation.');
            else
                set_param(cfg, 'TargetLang', 'C');
                 % For C, ensure 'Reusable function' or 'Model reference' as appropriate
                set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'Reusable function');
                disp('Configured for C code generation.');
            end
            set_param(cfg, 'GenerateReport', 'on'); % Generate HTML report
            set_param(cfg, 'GenCodeOnly', 'on');  % Important: Only generate code, don't try to build/download
            
            % Set code generation folder; slbuild will create subdirs here
            % Example: codeGenBaseDir/modelName_ert_rtw
            if ~exist(codeGenBaseDir, 'dir')
               mkdir(codeGenBaseDir);
            end
            
            disp(['Code generation output target base directory: ', codeGenBaseDir]);
            % slbuild command handles the build process including code generation
            rtwbuild(modelName, 'CodeGenFolder', codeGenBaseDir); % rtwbuild is often preferred for GenCodeOnly
            
            disp('Code generation command (rtwbuild) executed.');
            
            % Determine actual output directory (often modelName_ert_rtw inside CodeGenFolder)
            % This part can be tricky as it depends on Simulink version and settings
            % For now, we point to codeGenBaseDir, user can navigate from there.
            actualCodeDir = codeGenBaseDir; 

            disp(['Code generation successful. Code and report expected in or under: ', actualCodeDir]);
            fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', actualCodeDir); 
        catch e
            disp(['Code generation error: ', getReport(e, 'extended')]);
            if bdIsLoaded(modelName), close_system(modelName, 0); end 
            rethrow(e);
        end
        if bdIsLoaded(modelName), close_system(modelName, 0); end % Close without saving
        """
        self._run_matlab_script(script_content, self.codeGenerationFinished, "Code generation")
        return True

class MatlabCommandWorker(QObject):
    finished_signal = pyqtSignal(bool, str, str) 

    def __init__(self, matlab_path, script_file, original_signal, success_message_prefix):
        super().__init__()
        self.matlab_path = matlab_path
        self.script_file = script_file
        self.original_signal = original_signal
        self.success_message_prefix = success_message_prefix

    def run_command(self):
        output_data_for_signal = ""
        success = False
        message = ""
        try:
            cmd = [self.matlab_path, "-batch", f"run('{self.script_file}')"]
            # Setting a longer timeout for potentially complex MATLAB operations
            timeout_seconds = 600 # 10 minutes
            process = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout_seconds,  
                check=False,   
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0 
            )

            if process.returncode == 0:
                if "MATLAB_SCRIPT_SUCCESS" in process.stdout:
                    success = True
                    for line in process.stdout.splitlines():
                        if line.startswith("MATLAB_SCRIPT_SUCCESS:"):
                            output_data_for_signal = line.split(":", 1)[1].strip()
                            break
                    message = f"{self.success_message_prefix} completed successfully."
                    if output_data_for_signal and self.success_message_prefix != "Simulation":
                         message += f" Output at: {output_data_for_signal}"
                    elif output_data_for_signal and self.success_message_prefix == "Simulation":
                        message = output_data_for_signal # Simulation success message comes from MATLAB
                    elif not output_data_for_signal and self.success_message_prefix == "Simulation":
                        message = f"{self.success_message_prefix} completed, but no specific data returned. MATLAB Output:\n{process.stdout[:300]}"


                else: 
                    success = False 
                    # More detailed error if success marker not found but return code is 0
                    message = f"{self.success_message_prefix} finished with ambiguous results (return code 0, but success marker missing)."
                    message += f"\nMATLAB stdout:\n{process.stdout[:500]}"
                    if process.stderr:
                        message += f"\nMATLAB stderr:\n{process.stderr[:300]}"
            else: 
                success = False
                error_output = process.stderr or process.stdout # Prefer stderr
                message = f"{self.success_message_prefix} failed. MATLAB Error (Return Code {process.returncode}):\n{error_output[:1000]}" # Increased length
            
            self.original_signal.emit(success, message, output_data_for_signal if success else "")

        except subprocess.TimeoutExpired:
            message = f"{self.success_message_prefix} timed out after {timeout_seconds/60} minutes."
            self.original_signal.emit(False, message, "")
        except FileNotFoundError:
            message = "MATLAB executable not found."
            self.original_signal.emit(False, message, "")
        except Exception as e:
            message = f"{self.success_message_prefix} worker error: {str(e)}"
            self.original_signal.emit(False, message, "")
        finally:
            if os.path.exists(self.script_file):
                try:
                    os.remove(self.script_file)
                    os.rmdir(os.path.dirname(self.script_file))
                except OSError as e: # Catch potential error if rmdir fails (e.g. dir not empty)
                    print(f"Warning: Could not clean up temp script/dir: {e}") 
            self.finished_signal.emit(success, message, output_data_for_signal)


# --- Draggable Toolbox Buttons ---
class DraggableToolButton(QPushButton):
    def __init__(self, text, mime_type, style_sheet, parent=None):
        super().__init__(text, parent)
        self.mime_type = mime_type
        self.setText(text) # Ensure text is set for QDrag's mime_data.setText
        # self.setFixedSize(120, 40) # Replaced by SSizePolicy and minHeight
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(style_sheet + " border-radius: 5px; text-align: left; padding-left: 5px;") # Align text left for icon
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
        mime_data.setText(self.text()) # This is used by scene's dropEvent
        mime_data.setData(self.mime_type, b"1") # Identifies the type of drag
        drag.setMimeData(mime_data)

        # Create a representative pixmap for the drag
        pixmap_size = QSize(max(100, self.width()), self.height()) # Ensure minimum width for drag pixmap
        pixmap = QPixmap(pixmap_size)
        pixmap.fill(Qt.transparent) # Use transparent background

        # Paint a simpler representation for dragging
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw a styled rect similar to the button
        button_rect = QRectF(0,0, pixmap_size.width(), pixmap_size.height())
        current_style = self.styleSheet()
        bg_color = QColor("#B0E0E6") # Default if not found in stylesheet
        if "background-color:" in current_style:
            try:
                color_str = current_style.split("background-color:")[1].split(";")[0].strip()
                bg_color = QColor(color_str)
            except: pass # Keep default
        painter.setBrush(bg_color)
        border_color = QColor("#77AABB")
        if "border:" in current_style:
            # simplified border parsing
            try:
                b_parts = current_style.split("border:")[1].split(";")[0].strip().split()
                if len(b_parts) >=3:
                    border_color = QColor(b_parts[2])
            except: pass
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(button_rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5)

        # Draw icon and text
        icon_pixmap = self.icon().pixmap(QSize(24,24))
        text_x_offset = 5
        if not icon_pixmap.isNull():
            painter.drawPixmap(5, (pixmap_size.height() - icon_pixmap.height()) / 2, icon_pixmap)
            text_x_offset += icon_pixmap.width() + 5
        
        painter.setPen(Qt.black) # Text color
        painter.setFont(self.font())
        painter.drawText(QRectF(text_x_offset, 0, pixmap_size.width() - text_x_offset - 5, pixmap_size.height()),
                         Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2)) # Center hotspot

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
        self.setBrush(QBrush(QColor(173, 216, 230))) # Light blue
        self.setFlags(QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges |
                      QGraphicsItem.ItemIsFocusable)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), 10, 10) # More rounded corners

        painter.setPen(self._text_color)
        painter.setFont(self._font)
        text_rect = self.rect().adjusted(5, 5, -5, -5) # Padding for text
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)

        if self.is_initial:
            painter.setBrush(Qt.black)
            painter.setPen(QPen(Qt.black, 1.5)) # Thinner pen for arrow
            
            # Position initial marker to the left of the state
            marker_radius = 8
            line_length = 15
            start_x = self.rect().left() - line_length - marker_radius
            start_y = self.rect().center().y()
            
            # Draw filled circle as start point
            painter.drawEllipse(QPointF(start_x, start_y), marker_radius, marker_radius)

            # Draw line from circle to state edge
            line_start_point = QPointF(start_x + marker_radius, start_y)
            line_end_point = QPointF(self.rect().left(), start_y)
            painter.drawLine(line_start_point, line_end_point)
            
            # Draw arrowhead at the state edge
            arrow_size = 8
            angle_rad = math.atan2(line_end_point.y() - line_start_point.y(), line_end_point.x() - line_start_point.x())
            
            p2_x = line_end_point.x() - arrow_size * math.cos(angle_rad + math.pi / 6)
            p2_y = line_end_point.y() - arrow_size * math.sin(angle_rad + math.pi / 6)
            p3_x = line_end_point.x() - arrow_size * math.cos(angle_rad - math.pi / 6)
            p3_y = line_end_point.y() - arrow_size * math.sin(angle_rad - math.pi / 6)

            painter.setBrush(Qt.black)
            painter.drawPolygon(QPolygonF([line_end_point, QPointF(p2_x, p2_y), QPointF(p3_x, p3_y)]))


        if self.is_final:
            painter.setPen(QPen(Qt.black, 2))
            # Draw an outer circle slightly larger than the state bounds if it were circular
            # For a rect, draw a double border
            inner_rect = self.rect().adjusted(5, 5, -5, -5)
            painter.drawRoundedRect(inner_rect, 7, 7) # Slightly less rounded inner border

        if self.isSelected():
            pen = QPen(Qt.blue, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            # Draw selection rectangle slightly larger
            selection_rect = self.boundingRect().adjusted(-2,-2,2,2)
            painter.drawRect(selection_rect)

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
        self.prepareGeometryChange()
        self.text_label = text
        self.update()

    def set_properties(self, name, is_initial, is_final):
        self.prepareGeometryChange()
        self.text_label = name
        self.is_initial = is_initial
        self.is_final = is_final
        self.update()

class GraphicsTransitionItem(QGraphicsPathItem):
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type

    def __init__(self, start_item, end_item, text=""):
        super().__init__()
        self.start_item = start_item
        self.end_item = end_item
        self.text_label = text
        self.arrow_size = 12 # Slightly larger arrow
        self._text_color = QColor(50, 50, 50) # Darker gray for text
        self._font = QFont("Arial", 9) # Non-bold for less clutter
        self.control_point_offset = QPointF(0,0) # Relative to midpoint of straight line

        self.setPen(QPen(QColor(0, 100, 100), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)) # Teal color
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1) 
        self.update_path()

    def boundingRect(self):
        # Adjusted bounding rect for text and selection outline
        extra = (self.pen().width() + self.arrow_size) / 2.0 + 20 # Increased extra for text
        path_bounds = self.path().boundingRect()
        # Include text label bounds if present
        if self.text_label:
            fm = QFontMetrics(self._font)
            text_rect = fm.boundingRect(self.text_label)
            # Approximate text position near midpoint
            mid_point = self.path().pointAtPercent(0.5)
            text_render_rect = QRectF(mid_point.x() - text_rect.width()/2, 
                                     mid_point.y() - text_rect.height() - 5, # Position above line
                                     text_rect.width(), text_rect.height())
            path_bounds = path_bounds.united(text_render_rect)
        return path_bounds.adjusted(-extra, -extra, extra, extra)


    def shape(self): 
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(15 + self.pen().width()) # Wider for easier selection
        path_stroker.setCapStyle(Qt.RoundCap)
        path_stroker.setJoinStyle(Qt.RoundJoin)
        return path_stroker.createStroke(self.path())


    def update_path(self):
        if not self.start_item or not self.end_item:
            self.setPath(QPainterPath()) 
            return

        # Use sceneBoundingRect for accurate global positions
        start_center = self.start_item.sceneBoundingRect().center()
        end_center = self.end_item.sceneBoundingRect().center()
        
        line = QLineF(start_center, end_center)
        
        start_point = self._get_intersection_point(self.start_item, line)
        # For end_point, reverse the line direction to find intersection from outside
        end_point = self._get_intersection_point(self.end_item, QLineF(line.p2(), line.p1()))


        if start_point is None: start_point = start_center
        if end_point is None: end_point = end_center    

        path = QPainterPath(start_point)

        if self.start_item == self.end_item: # Self-loop
            rect = self.start_item.sceneBoundingRect()
            # Position loop above the state
            loop_radius_x = rect.width() * 0.4
            loop_radius_y = rect.height() * 0.4
            
            # Start slightly to the right of top-middle, end slightly to the left
            p1 = QPointF(rect.center().x() + loop_radius_x * 0.5, rect.top())
            p2 = QPointF(rect.center().x() - loop_radius_x * 0.5, rect.top())
            
            # Control points for a nice arc above the state
            ctrl1 = QPointF(rect.center().x() + loop_radius_x * 1.2, rect.top() - loop_radius_y * 2.5)
            ctrl2 = QPointF(rect.center().x() - loop_radius_x * 1.2, rect.top() - loop_radius_y * 2.5)
            
            path.moveTo(p1)
            path.cubicTo(ctrl1, ctrl2, p2)
            end_point = p2 # Arrow will point here
        else: # Regular transition
            # Calculate midpoint of the straight line between start_point and end_point
            mid_x = (start_point.x() + end_point.x()) / 2
            mid_y = (start_point.y() + end_point.y()) / 2
            
            # Apply the control_point_offset relative to this midpoint
            # The offset is perpendicular to the line for a nice curve
            dx = end_point.x() - start_point.x()
            dy = end_point.y() - start_point.y()
            length = math.sqrt(dx*dx + dy*dy)
            if length == 0: length = 1 # Avoid division by zero

            # Normalized perpendicular vector
            perp_x = -dy / length
            perp_y = dx / length

            # control_point_offset.x() can be thought of as magnitude along perpendicular
            # control_point_offset.y() can be thought of as magnitude along the line (for S-curves, not used here)
            
            # For a simple quadratic bezier, one control point
            # Offset the midpoint perpendicularly by control_point_offset.x()
            # and along the line by control_point_offset.y() (relative to midpoint)
            ctrl_pt_x = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y()
            ctrl_pt_y = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()
            
            ctrl_pt = QPointF(ctrl_pt_x, ctrl_pt_y)
            
            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0: # Straight line
                 path.lineTo(end_point)
            else: # Curved line
                 path.quadTo(ctrl_pt, end_point)
        
        self.setPath(path)
        self.prepareGeometryChange() # Important for view updates

    def _get_intersection_point(self, item, line):
        # item.sceneBoundingRect() is the rectangle in scene coordinates
        item_rect = item.sceneBoundingRect() 
        
        # Create lines for each edge of the item's bounding rect
        edges = [
            QLineF(item_rect.topLeft(), item_rect.topRight()),      # Top
            QLineF(item_rect.topRight(), item_rect.bottomRight()),  # Right
            QLineF(item_rect.bottomRight(), item_rect.bottomLeft()),# Bottom
            QLineF(item_rect.bottomLeft(), item_rect.topLeft())     # Left
        ]
        
        intersect_points = []
        for edge in edges:
            intersection_point = QPointF() # Must be default-constructed for QLineF.intersect
            intersect_type = line.intersect(edge, intersection_point)
            # We want bounded intersections on the item's edge
            if intersect_type == QLineF.BoundedIntersection :
                 # Check if intersection_point is actually on the segment 'edge'
                 # This check is crucial because QLineF.BoundedIntersection means the intersection
                 # is within the bounds of *both* lines if they were infinite.
                 # We need to ensure it's on the finite segment of 'edge'.
                 edge_rect = QRectF(edge.p1(), edge.p2()).normalized()
                 # Add a small tolerance for floating point comparisons
                 tolerance = 1e-3 
                 if (edge_rect.left() - tolerance <= intersection_point.x() <= edge_rect.right() + tolerance and
                     edge_rect.top() - tolerance <= intersection_point.y() <= edge_rect.bottom() + tolerance):
                    intersect_points.append(QPointF(intersection_point)) # Create new QPointF instance

        if not intersect_points:
            return item_rect.center() # Fallback if no intersection found (e.g., line starts inside)

        # Find the closest intersection point to the start of the 'line' (line.p1())
        closest_point = intersect_points[0]
        min_dist_sq = QLineF(line.p1(), closest_point).length() ** 2
        for pt in intersect_points[1:]:
            dist_sq = QLineF(line.p1(), pt).length() ** 2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_point = pt
        return closest_point


    def paint(self, painter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty():
            return

        painter.setRenderHint(QPainter.Antialiasing)
        current_pen = self.pen()
        if self.isSelected():
            selection_pen = QPen(Qt.blue, current_pen.widthF() + 1, Qt.SolidLine) # Make selection highlight thicker
            selection_pen.setCapStyle(Qt.RoundCap)
            selection_pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(selection_pen)
            painter.drawPath(self.shape()) # Draw shape for selection highlight first
        
        painter.setPen(current_pen) # Reset to original pen for the main line
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

        # Arrowhead calculation
        if self.path().elementCount() < 1 : return 

        # Get point and angle at the very end of the path for arrowhead
        line_end_point = self.path().pointAtPercent(1.0)
        angle_at_end_rad = self.path().angleAtPercent(1.0) * (math.pi / 180.0) # angleAtPercent is in degrees
        # Adjust angle because Qt's angle is CCW from positive X-axis,
        # but our arrowhead calculation expects angle of the line segment itself.
        # The angle from path is of the tangent. We need to reverse it for arrowhead pointing inward.
        angle_rad = angle_at_end_rad + math.pi


        arrow_p1 = line_end_point + QPointF(math.cos(angle_rad + math.pi / 6) * self.arrow_size,
                                           math.sin(angle_rad + math.pi / 6) * self.arrow_size)
        arrow_p2 = line_end_point + QPointF(math.cos(angle_rad - math.pi / 6) * self.arrow_size,
                                           math.sin(angle_rad - math.pi / 6) * self.arrow_size)
        
        painter.setBrush(self.pen().color()) # Fill arrowhead
        painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))


        if self.text_label:
            painter.setPen(self._text_color)
            painter.setFont(self._font)
            
            # Position text near the midpoint of the path, offset perpendicularly
            text_pos_on_path = self.path().pointAtPercent(0.5)
            angle_at_mid_deg = self.path().angleAtPercent(0.5)
            
            # Metrics for text bounding box
            fm = QFontMetrics(self._font)
            text_rect = fm.boundingRect(self.text_label)
            
            # Offset perpendicular to the path tangent
            # Angle from path.angleAtPercent is 0 for horizontal right, increases CCW.
            # Perpendicular upwards is angle - 90 degrees.
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0)
            offset_dist = 10 + text_rect.height() / 2 # Distance above the line
            
            # If the transition is mostly vertical, offset horizontally
            # angle_at_mid_deg is between 0-360. Vertical up ~270, vertical down ~90
            is_vertical_ish = (75 < angle_at_mid_deg < 105) or (255 < angle_at_mid_deg < 285)
            if is_vertical_ish:
                offset_angle_rad = (angle_at_mid_deg - (180 if (angle_at_mid_deg > 180) else 0)) * (math.pi / 180.0) # horizontal offset
                offset_dist = 10 + text_rect.width() /2


            dx = offset_dist * math.cos(offset_angle_rad)
            dy = offset_dist * math.sin(offset_angle_rad)

            text_final_pos = text_pos_on_path + QPointF(dx - text_rect.width()/2, dy - text_rect.height()/2)
            
            # Simple background for readability
            bg_rect = QRectF(text_final_pos.x() - 2, text_final_pos.y() - 2, text_rect.width() + 4, text_rect.height() + 4)
            painter.setBrush(QColor(255,255,255,180)) # Semi-transparent white
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bg_rect, 3,3)

            painter.setPen(self._text_color) # Reset pen for text
            painter.drawText(text_final_pos, self.text_label)

    
    def get_data(self):
        return {
            'source': self.start_item.text_label,
            'target': self.end_item.text_label,
            'label': self.text_label,
            'control_offset_x': self.control_point_offset.x(), # Perpendicular offset
            'control_offset_y': self.control_point_offset.y()  # Tangential offset (for S-curves, or general use)
        }
    
    def set_text(self, text):
        self.prepareGeometryChange() 
        self.text_label = text
        self.update() # Triggers repaint and re-evaluation of boundingRect

    def set_control_point_offset(self, offset): # offset is QPointF
        if self.control_point_offset != offset:
            self.control_point_offset = offset
            self.update_path()
            self.update()


# --- Undo Commands ---
class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item_instance = item # This is the actual QGraphicsItem instance

        # For transitions, store names to relink if items are recreated by other commands
        if isinstance(item, GraphicsTransitionItem):
            self.start_item_name = item.start_item.text_label
            self.end_item_name = item.end_item.text_label
            self.label = item.text_label
            self.control_offset = item.control_point_offset
            # item_instance itself stores start_item and end_item references

    def redo(self):
        # If item was removed from scene (e.g. by undo), ensure it's re-added
        if self.item_instance.scene() is None:
            self.scene.addItem(self.item_instance)

        # Special handling for transitions to ensure start/end items are correctly linked
        # This is important if states might be added/removed/recreated by other undo/redo ops
        if isinstance(self.item_instance, GraphicsTransitionItem):
            start_node = self.scene.get_state_by_name(self.start_item_name)
            end_node = self.scene.get_state_by_name(self.end_item_name)
            if start_node and end_node:
                self.item_instance.start_item = start_node
                self.item_instance.end_item = end_node
                self.item_instance.update_path() # Crucial to redraw based on potentially new item positions
            else:
                # This case should ideally not happen if state creation/deletion is also undoable
                # Or if state items persist across undo/redo of transitions
                print(f"Warning (Redo Add Transition): Could not re-link transition '{self.label}'. Missing states.")
                # Potentially remove the transition if it cannot be linked, or leave it orphaned
                # For now, it's added but might be visually incorrect or disconnected
        
        self.scene.clearSelection()
        self.item_instance.setSelected(True)
        self.scene.set_dirty(True)

    def undo(self):
        # Simply remove the item from the scene. It's kept in memory by the command.
        self.scene.removeItem(self.item_instance)
        self.scene.set_dirty(True)

class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items_to_remove, description="Remove Items"):
        super().__init__(description)
        self.scene = scene
        # Store actual item instances. Sort so states are processed before transitions if needed,
        # though addItem/removeItem order doesn't strictly matter for scene.
        self.removed_items_instances = sorted(list(items_to_remove), 
                                              key=lambda x: 0 if isinstance(x, GraphicsStateItem) else 1)
        
        # For transitions, save all necessary data to recreate them if they don't persist,
        # or to relink them if they do. Since we store instances, relinking is key.
        self.transition_connections = []
        for item in self.removed_items_instances:
            if isinstance(item, GraphicsTransitionItem):
                self.transition_connections.append({
                    'trans_item': item, # The instance itself
                    'start_name': item.start_item.text_label if item.start_item else None,
                    'end_name': item.end_item.text_label if item.end_item else None,
                    'label': item.text_label,
                    'control_offset': item.control_point_offset
                })
        
    def redo(self): # Perform the removal
        for item_instance in self.removed_items_instances:
            if item_instance.scene() == self.scene: # Only remove if it's currently in the scene
                self.scene.removeItem(item_instance)
        self.scene.set_dirty(True)

    def undo(self): # Add the items back
        # Add states first
        for item_instance in self.removed_items_instances:
            if isinstance(item_instance, GraphicsStateItem):
                if item_instance.scene() is None: # Add back if not in scene
                    self.scene.addItem(item_instance)
        
        # Then add transitions, attempting to relink them
        for conn_info in self.transition_connections:
            trans_item = conn_info['trans_item']
            if trans_item.scene() is None: # Add back if not in scene
                self.scene.addItem(trans_item)
            
            # Try to find the state items by name (they should have been added back if they were removed)
            start_node = self.scene.get_state_by_name(conn_info['start_name'])
            end_node = self.scene.get_state_by_name(conn_info['end_name'])

            if start_node and end_node:
                trans_item.start_item = start_node
                trans_item.end_item = end_node
                trans_item.update_path() # Update its visual path
            else:
                # This is a problem: state items it connected to are no longer available by that name
                print(f"Warning (Undo Remove Transition): Could not re-link transition '{conn_info['label']}'. Missing states.")
                # The transition is added back, but may be disconnected or visually wrong.

        # Add any other types of items
        for item_instance in self.removed_items_instances:
            if not isinstance(item_instance, (GraphicsStateItem, GraphicsTransitionItem)):
                if item_instance.scene() is None:
                     self.scene.addItem(item_instance)

        self.scene.set_dirty(True)


class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_positions_new, description="Move Items"):
        super().__init__(description)
        # items_positions_new is a list of (item_instance, new_QPointF_pos)
        self.items_positions_new = items_positions_new 
        self.items_positions_old = []
        self.scene_ref = None
        if self.items_positions_new: # Ensure list is not empty
            for item, _ in self.items_positions_new:
                self.items_positions_old.append((item, item.pos())) # Store current (old) pos
                if not self.scene_ref and item.scene(): self.scene_ref = item.scene()


    def redo(self):
        if not self.scene_ref: return
        for item, new_pos in self.items_positions_new:
            item.setPos(new_pos)
            # If item is a state, its connected transitions need updating
            if isinstance(item, GraphicsStateItem):
                self.scene_ref._update_connected_transitions(item)
        self.scene_ref.set_dirty(True)
    
    def undo(self):
        if not self.scene_ref: return
        for item, old_pos in self.items_positions_old:
            item.setPos(old_pos)
            if isinstance(item, GraphicsStateItem):
                self.scene_ref._update_connected_transitions(item)
        self.scene_ref.set_dirty(True)

class EditItemPropertiesCommand(QUndoCommand):
    def __init__(self, item, old_props, new_props, description="Edit Properties"):
        super().__init__(description)
        self.item = item
        self.old_props = old_props # dict of properties
        self.new_props = new_props # dict of properties
        self.scene_ref = item.scene()

    def _apply_properties(self, props):
        if isinstance(self.item, GraphicsStateItem):
            # If name changes, need to update transitions linked to this state by its old name
            old_name = self.item.text_label
            new_name = props['name']
            
            self.item.set_properties(new_name, props['is_initial'], props['is_final'])

            if old_name != new_name and self.scene_ref:
                self.scene_ref._update_transitions_for_renamed_state(old_name, new_name)

        elif isinstance(self.item, GraphicsTransitionItem):
            self.item.set_text(props['label'])
            if 'control_offset_x' in props and 'control_offset_y' in props:
                 self.item.set_control_point_offset(QPointF(props['control_offset_x'], props['control_offset_y']))
        
        if self.scene_ref:
            self.scene_ref.set_dirty(True)
        self.item.update() # Ensure visual update
        if self.item.scene(): self.item.scene().update() # Force scene update too

    def redo(self):
        self._apply_properties(self.new_props)

    def undo(self):
        self._apply_properties(self.old_props)


# --- Diagram Scene ---
class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool) # Renamed from itemSelected for clarity

    def __init__(self, undo_stack, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 4000, 3000) 
        self.current_mode = "select" # "select", "state", "transition"
        self.transition_start_item = None
        self.log_function = print # Placeholder for logging
        self.undo_stack = undo_stack
        self._dirty = False
        self._mouse_press_items_positions = {} # For MoveItemsCommand
        self._temp_transition_line = None # For drawing new transitions

        self.item_moved.connect(self._handle_item_moved) # Connect internal signal

        # Grid settings
        self.grid_size = 20
        self.grid_pen_light = QPen(QColor(220, 220, 220), 0.5)
        self.grid_pen_dark = QPen(QColor(180, 180, 180), 0.7)
        self.setBackgroundBrush(QColor(245, 245, 245)) # Light grey background

    def _update_connected_transitions(self, state_item):
        """Updates all transitions connected to the given state_item."""
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                if item.start_item == state_item or item.end_item == state_item:
                    item.update_path()
    
    def _update_transitions_for_renamed_state(self, old_name, new_name):
        """
        When a state is renamed, its `text_label` is updated.
        Transitions store start/end item *references*, so their `get_data()` would reflect new name.
        This is more for data consistency if names were primary keys somewhere else.
        For the display, direct reference update is fine.
        However, if reloading or complex undo, name mapping might be needed.
        Currently, EditItemPropertiesCommand directly updates item.text_label.
        The transitions connected to it via item reference will show the new name automatically
        when their paint method accesses `item.start_item.text_label`.
        This function is more of a placeholder if deep data model linkage by name was required.
        For now, it's not strictly necessary with object references.
        """
        pass # Item references are updated, direct name tracking in transitions not primary.


    def get_state_by_name(self, name):
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name:
                return item
        return None

    def set_dirty(self, dirty=True):
        if self._dirty != dirty:
            self._dirty = dirty
            self.modifiedStatusChanged.emit(dirty) # Emit standard signal
            
    def is_dirty(self):
        return self._dirty

    def set_log_function(self, log_function):
        self.log_function = log_function

    def set_mode(self, mode):
        old_mode = self.current_mode
        self.current_mode = mode
        self.log_function(f"Mode changed to: {mode}")
        
        # Reset transition drawing state
        self.transition_start_item = None 
        if self._temp_transition_line:
            self.removeItem(self._temp_transition_line)
            self._temp_transition_line = None

        # Update cursors and item flags based on mode
        if mode == "select":
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            for item in self.items(): 
                if isinstance(item, GraphicsStateItem): item.setFlag(QGraphicsItem.ItemIsMovable, True)
        elif mode == "state":
            QApplication.setOverrideCursor(Qt.CrossCursor) # Cross for placing new state
            for item in self.items(): 
                 if isinstance(item, GraphicsStateItem): item.setFlag(QGraphicsItem.ItemIsMovable, False)
        elif mode == "transition":
            QApplication.setOverrideCursor(Qt.CrossCursor) # Cross for selecting states for transition
            for item in self.items(): 
                 if isinstance(item, GraphicsStateItem): item.setFlag(QGraphicsItem.ItemIsMovable, False)
        else: # Fallback or if a mode was left without setting to known one
            if old_mode in ["state", "transition"] and mode != old_mode : # only restore if cursor was changed
                QApplication.restoreOverrideCursor()


    def select_all(self):
        for item in self.items():
            item.setSelected(True)

    def _handle_item_moved(self, moved_item):
        # This signal is emitted by GraphicsStateItem on itemChange
        if isinstance(moved_item, GraphicsStateItem):
            self._update_connected_transitions(moved_item)


    def mousePressEvent(self, event):
        pos = event.scenePos()
        # Prioritize state items if multiple items are under cursor (e.g., transition line over state)
        items_under_cursor = self.items(pos)
        state_items_under_cursor = [it for it in items_under_cursor if isinstance(it, GraphicsStateItem)]
        
        top_item = None
        if state_items_under_cursor:
            top_item = state_items_under_cursor[0] # Usually the one with higher Z or added last
        elif items_under_cursor:
            top_item = items_under_cursor[0] # Could be a transition or other item

        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                # Add state at click position, snapping to grid
                grid_x = round(pos.x() / self.grid_size) * self.grid_size
                grid_y = round(pos.y() / self.grid_size) * self.grid_size
                self._add_state_item(QPointF(grid_x, grid_y))
            elif self.current_mode == "transition":
                if isinstance(top_item, GraphicsStateItem):
                    self._handle_transition_click(top_item, pos)
                else: # Clicked on empty space while in transition mode
                    self.transition_start_item = None # Cancel current transition drawing
                    if self._temp_transition_line:
                        self.removeItem(self._temp_transition_line)
                        self._temp_transition_line = None
                    self.log_function("Transition drawing cancelled (clicked empty space).")
            else: # Select mode or other modes not handled above
                self._mouse_press_items_positions.clear()
                selected_movable_items = [item for item in self.selectedItems() if item.flags() & QGraphicsItem.ItemIsMovable]
                if selected_movable_items: # Only record if there are selected, movable items
                    for item in selected_movable_items:
                         self._mouse_press_items_positions[item] = item.pos()
                super().mousePressEvent(event) # Allow normal selection/move
                # Do not return here if we want context menu on empty space for select mode
        
        elif event.button() == Qt.RightButton:
            if top_item and isinstance(top_item, (GraphicsStateItem, GraphicsTransitionItem)):
                if not top_item.isSelected(): # If right-clicked item is not selected, select it exclusively
                    self.clearSelection()
                    top_item.setSelected(True)
                self._show_context_menu(top_item, event.screenPos())
            else: # Right-click on empty space
                self.clearSelection()
                # Optionally, show a scene context menu here (e.g., Paste, Select All)
                # self._show_scene_context_menu(event.screenPos())
        else: 
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            # Update temporary line endpoint to mouse cursor
            self._temp_transition_line.setLine(QLineF(self.transition_start_item.sceneBoundingRect().center(), event.scenePos()))
            self.update() # Redraw scene to show temp line moving
        else: # Handle normal dragging in select mode
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            if self._mouse_press_items_positions: 
                # Check if any item actually moved significantly
                moved_items_data = []
                for item, old_pos in self._mouse_press_items_positions.items():
                    # Use a small threshold to avoid tiny movements creating undo steps
                    if (item.pos() - old_pos).manhattanLength() > QApplication.startDragDistance() / 2: 
                        moved_items_data.append((item, item.pos())) # Store item and its new position
                
                if moved_items_data:
                    cmd = MoveItemsCommand(moved_items_data) # Pass new positions
                    self.undo_stack.push(cmd)
                    # No need to call set_dirty here, MoveItemsCommand does it
                self._mouse_press_items_positions.clear()

        super().mouseReleaseEvent(event) # Standard handling

    def mouseDoubleClickEvent(self, event):
        # Prioritize state items for double-click edit
        items_under_cursor = self.items(event.scenePos())
        state_items_under_cursor = [it for it in items_under_cursor if isinstance(it, GraphicsStateItem)]
        
        item_to_edit = None
        if state_items_under_cursor:
            item_to_edit = state_items_under_cursor[0]
        elif items_under_cursor and isinstance(items_under_cursor[0], GraphicsTransitionItem):
            item_to_edit = items_under_cursor[0]

        if item_to_edit:
            self.edit_item_properties(item_to_edit)
        else:
            super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, item, global_pos):
        menu = QMenu()
        edit_action = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        delete_action = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")
        
        action = menu.exec_(global_pos)
        if action == edit_action:
            self.edit_item_properties(item)
        elif action == delete_action:
            # Ensure the item to be deleted is selected for the command
            if not item.isSelected():
                self.clearSelection() # Should already be selected by mousePress right-click logic
                item.setSelected(True)
            self.delete_selected_items() # This will operate on all selected items

    def edit_item_properties(self, item):
        original_name = None
        if isinstance(item, GraphicsStateItem):
            original_name = item.text_label # Store original name for checking duplicates
            old_props = {'name': item.text_label, 'is_initial': item.is_initial, 'is_final': item.is_final}
            dialog = StatePropertiesDialog(item.text_label, item.is_initial, item.is_final)
            if dialog.exec_() == QDialog.Accepted:
                new_name = dialog.get_name()
                # Check for duplicate name only if name has changed
                if new_name != original_name and self.get_state_by_name(new_name):
                    QMessageBox.warning(None, "Duplicate Name", f"A state with the name '{new_name}' already exists.")
                    return # Do not apply changes
                
                new_props = {'name': new_name, 
                             'is_initial': dialog.is_initial_cb.isChecked(), 
                             'is_final': dialog.is_final_cb.isChecked()}
                cmd = EditItemPropertiesCommand(item, old_props, new_props, "Edit State Properties")
                self.undo_stack.push(cmd)
                self.log_function(f"Properties updated for state: {new_name}")

        elif isinstance(item, GraphicsTransitionItem):
            old_props = {
                'label': item.text_label,
                'control_offset_x': item.control_point_offset.x(),
                'control_offset_y': item.control_point_offset.y()
            }
            dialog = TransitionPropertiesDialog(item.text_label, item.control_point_offset)
            if dialog.exec_() == QDialog.Accepted:
                new_props = {
                    'label': dialog.get_label(),
                    'control_offset_x': dialog.get_control_offset().x(),
                    'control_offset_y': dialog.get_control_offset().y()
                }
                cmd = EditItemPropertiesCommand(item, old_props, new_props, "Edit Transition Properties")
                self.undo_stack.push(cmd)
                self.log_function(f"Properties updated for transition: {new_props['label']}")
        
        self.update() # Redraw the scene to reflect property changes

    def _add_state_item(self, pos, name_prefix="State"): # pos is QPointF from scene coords
        # Generate a unique default name
        i = 1
        while self.get_state_by_name(f"{name_prefix}{i}"):
            i += 1
        default_name = f"{name_prefix}{i}"

        # Prompt for name
        state_name, ok = QInputDialog.getText(None, "New State", "Enter state name:", text=default_name)
        if ok and state_name:
            if self.get_state_by_name(state_name): # Check for duplicates
                QMessageBox.warning(None, "Duplicate Name", f"A state with the name '{state_name}' already exists.")
                if self.current_mode == "state": self.set_mode("select") # Revert mode if from click
                return

            # Prompt for other properties (initial/final)
            props_dialog = StatePropertiesDialog(state_name) # Pass the chosen name
            if props_dialog.exec_() == QDialog.Accepted:
                new_state = GraphicsStateItem(
                    pos.x() - 60, pos.y() - 30, 120, 60, # Center item on pos
                    props_dialog.get_name(), # Use name from props_dialog (should match state_name)
                    props_dialog.is_initial_cb.isChecked(),
                    props_dialog.is_final_cb.isChecked()
                )
                cmd = AddItemCommand(self, new_state, "Add State")
                self.undo_stack.push(cmd)
                self.log_function(f"Added state: {new_state.text_label} at ({pos.x()},{pos.y()})")
        
        # If adding state via click in "state" mode, revert to "select" mode after adding or cancelling
        if self.current_mode == "state":
            self.set_mode("select") # Or trigger the select_mode_action if main window manages actions
            # Assuming the main window will update its UI (toolbar buttons) based on scene mode change signal
            if self.parent() and hasattr(self.parent(), 'select_mode_action'): # A bit coupled
                 QTimer.singleShot(0, self.parent().select_mode_action.trigger)


    def _handle_transition_click(self, clicked_state_item, click_pos):
        if not self.transition_start_item: # This is the first click (selecting source state)
            self.transition_start_item = clicked_state_item
            # Create a temporary line for visual feedback
            if not self._temp_transition_line:
                self._temp_transition_line = QGraphicsLineItem() 
                self._temp_transition_line.setPen(QPen(Qt.black, 1.5, Qt.DashLine))
                self.addItem(self._temp_transition_line)
            
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, click_pos)) # Line from source to cursor
            self.log_function(f"Transition started from: {clicked_state_item.text_label}. Click target state.")
        else: # This is the second click (selecting target state)
            if self._temp_transition_line: # Remove temporary line
                self.removeItem(self._temp_transition_line)
                self._temp_transition_line = None

            if self.transition_start_item == clicked_state_item: # Self-transition
                # Allow self-transitions, prompt for label
                pass # Continue to label prompt

            # Prompt for transition label
            label, ok = QInputDialog.getText(None, "New Transition", "Enter transition label (optional):")
            if ok: # User clicked OK (label can be empty)
                new_transition = GraphicsTransitionItem(self.transition_start_item, clicked_state_item, label)
                cmd = AddItemCommand(self, new_transition, "Add Transition")
                self.undo_stack.push(cmd)
                self.log_function(f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{label}]")
            
            # Reset for next transition or mode change
            self.transition_start_item = None 
            self.set_mode("select") # Revert to select mode
            if self.parent() and hasattr(self.parent(), 'select_mode_action'):
                 QTimer.singleShot(0, self.parent().select_mode_action.trigger)


    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            if self.selectedItems():
                self.delete_selected_items()
        elif event.key() == Qt.Key_Escape:
            if self.current_mode == "transition" and self.transition_start_item:
                # Cancel ongoing transition drawing
                self.transition_start_item = None
                if self._temp_transition_line:
                    self.removeItem(self._temp_transition_line)
                    self._temp_transition_line = None
                self.log_function("Transition drawing cancelled by Escape key.")
                self.set_mode("select") # Revert to select mode
                if self.parent() and hasattr(self.parent(), 'select_mode_action'):
                    QTimer.singleShot(0, self.parent().select_mode_action.trigger)

            else: # General escape: clear selection
                self.clearSelection()
        else:
            super().keyPressEvent(event)

    def delete_selected_items(self):
        selected = self.selectedItems()
        if not selected: return

        # Collect all items to be deleted, including transitions connected to deleted states
        items_to_delete_directly = set(selected)
        related_transitions_to_delete = set()

        for item in list(items_to_delete_directly): # Iterate over a copy
            if isinstance(item, GraphicsStateItem):
                # Find all transitions connected to this state
                for scene_item in self.items(): # Check all items in the scene
                    if isinstance(scene_item, GraphicsTransitionItem):
                        if scene_item.start_item == item or scene_item.end_item == item:
                            related_transitions_to_delete.add(scene_item)
        
        all_items_to_delete = items_to_delete_directly.union(related_transitions_to_delete)
        
        if all_items_to_delete:
            cmd = RemoveItemsCommand(self, list(all_items_to_delete), "Delete Items")
            self.undo_stack.push(cmd)
            self.log_function(f"Deleted {len(all_items_to_delete)} item(s).")
            # Selection is cleared by RemoveItemsCommand redo or implicitly
            self.clearSelection() 


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
            dropped_text = event.mimeData().text() # e.g., "State" from DraggableToolButton
            
            # Snap drop position to grid
            grid_x = round(pos.x() / self.grid_size) * self.grid_size
            grid_y = round(pos.y() / self.grid_size) * self.grid_size
            
            self._add_state_item(QPointF(grid_x, grid_y), name_prefix=dropped_text or "State")
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def get_diagram_data(self):
        data = {'states': [], 'transitions': []} 
        for item in self.items():
            if isinstance(item, GraphicsStateItem):
                data['states'].append(item.get_data())
            elif isinstance(item, GraphicsTransitionItem):
                # Ensure transitions only save if connected states are valid (robustness)
                if item.start_item and item.end_item:
                    data['transitions'].append(item.get_data())
                else:
                    self.log_function(f"Warning: Skipping save of orphaned transition: {item.text_label}")
        return data

    def load_diagram_data(self, data):
        self.clear() # Clears all items, selection, etc.
        self.set_dirty(False) # Loading a file makes it non-dirty initially

        state_items_map = {} # To link transitions by state name

        for state_data in data.get('states', []):
            # Use get() for optional width/height with defaults
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
                # Load control point offset for curves
                trans_item.set_control_point_offset(QPointF(
                    trans_data.get('control_offset_x', 0),
                    trans_data.get('control_offset_y', 0)
                ))
                self.addItem(trans_item)
            else:
                self.log_function(f"Warning: Could not link loaded transition '{trans_data.get('label')}' due to missing states: {trans_data['source']} or {trans_data['target']}.")
        
        self.set_dirty(False) # Confirm non-dirty status
        self.undo_stack.clear() # Clear undo history for newly loaded file

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect) # Draws the self.backgroundBrush()

        left = int(rect.left())
        right = int(rect.right())
        top = int(rect.top())
        bottom = int(rect.bottom())

        # Snap to grid for drawing start points
        first_left = left - (left % self.grid_size)
        first_top = top - (top % self.grid_size)

        # Light grid lines
        light_lines = []
        for x in range(first_left, right, self.grid_size):
            light_lines.append(QLineF(x, top, x, bottom))
        for y in range(first_top, bottom, self.grid_size):
            light_lines.append(QLineF(left, y, right, y))
        
        painter.setPen(self.grid_pen_light)
        painter.drawLines(light_lines)

        # Darker grid lines (e.g., every 5th light line)
        dark_lines = []
        major_grid_size = self.grid_size * 5
        first_major_left = left - (left % major_grid_size)
        first_major_top = top - (top % major_grid_size)

        for x in range(first_major_left, right, major_grid_size):
            dark_lines.append(QLineF(x, top, x, bottom))
        for y in range(first_major_top, bottom, major_grid_size):
            dark_lines.append(QLineF(left, y, right, y))

        painter.setPen(self.grid_pen_dark)
        painter.drawLines(dark_lines)

# --- Zoomable Graphics View ---
class ZoomableView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag) # For selecting multiple items
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate) # Can be optimized later if needed
        self.zoom_factor_base = 1.0015 # Fine-tuned for smoother zoom
        self.zoom_level = 0 # Internal tracking of zoom steps

        # Panning setup
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self._is_panning = False
        self._last_pan_point = QPoint()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0: # Zoom in
                factor = 1.15 # Increase scale by 15%
                self.zoom_level += 1
            else: # Zoom out
                factor = 1 / 1.15 # Decrease scale
                self.zoom_level -= 1
            
            # Limit zoom levels
            if -10 < self.zoom_level < 15: # Arbitrary limits
                self.scale(factor, factor)
            else: # Reached zoom limit, revert zoom_level change
                if delta > 0: self.zoom_level -=1
                else: self.zoom_level +=1
            event.accept()
        else:
            # Default wheel event for scrolling (if scrollbars are visible)
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not self._is_panning:
            self._is_panning = True
            self._last_pan_point = self.mapToScene(event.pos()).toPoint() # For QGraphicsView, event.pos() is view coords
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal: # Zoom in
            self.scale(1.15, 1.15)
        elif event.key() == Qt.Key_Minus: # Zoom out
            self.scale(1/1.15, 1/1.15)
        elif event.key() == Qt.Key_0: # Reset zoom (approximate)
             self.resetTransform() # Resets all transformations
             self.zoom_level = 0
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor) # Or whatever the current mode's cursor is
            event.accept()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QEvent):
        if event.button() == Qt.MiddleButton or (self._is_panning and event.button() == Qt.LeftButton):
            self._last_pan_point = self.mapToScene(event.pos()).toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            self._is_panning_with_mouse = True # Separate flag for mouse panning
            event.accept()
            return
        self._is_panning_with_mouse = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QEvent):
        if self._is_panning_with_mouse or (self._is_panning and event.buttons() & Qt.LeftButton) :
            new_pan_point = self.mapToScene(event.pos()).toPoint()
            delta = new_pan_point - self._last_pan_point
            
            # Translate the view (scene)
            # Note: QGraphicsView translates its viewport, not the scene itself directly
            # For panning, we adjust scrollbars or transform the view
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            
            self._last_pan_point = self.mapToScene(event.pos()).toPoint() # Update for next move
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QEvent):
        if self._is_panning_with_mouse and event.button() == Qt.MiddleButton :
            self.setCursor(Qt.ArrowCursor) # Or current mode cursor
            self._is_panning_with_mouse = False
            event.accept()
            return
        # If panning with Space + Left Mouse, KeyRelease handles cursor
        super().mouseReleaseEvent(event)


# --- Dialogs ---
class StatePropertiesDialog(QDialog):
    def __init__(self, state_name="", initial=False, final=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Props"))
        layout = QFormLayout(self)

        self.name_edit = QLineEdit(state_name)
        self.name_edit.setPlaceholderText("Enter a unique state name")
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

    def get_name(self): return self.name_edit.text().strip()

class TransitionPropertiesDialog(QDialog):
    def __init__(self, label="", control_offset=QPointF(0,0), parent=None):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Props"))
        layout = QFormLayout(self)

        self.label_edit = QLineEdit(label)
        self.label_edit.setPlaceholderText("Optional event/condition")
        layout.addRow("Label:", self.label_edit)

        # control_offset.x() is perpendicular distance, y() is tangential shift
        self.offset_perp_spin = QSpinBox()
        self.offset_perp_spin.setRange(-500, 500)
        self.offset_perp_spin.setValue(int(control_offset.x()))
        self.offset_perp_spin.setToolTip("Perpendicular distance from line midpoint to curve control point.")
        layout.addRow("Curve (Perpendicular):", self.offset_perp_spin)

        self.offset_tang_spin = QSpinBox()
        self.offset_tang_spin.setRange(-500, 500)
        self.offset_tang_spin.setValue(int(control_offset.y()))
        self.offset_tang_spin.setToolTip("Tangential shift of curve control point along the line (for S-curves).")
        layout.addRow("Curve (Tangential):", self.offset_tang_spin)


        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_label(self): return self.label_edit.text()
    def get_control_offset(self): return QPointF(self.offset_perp_spin.value(), self.offset_tang_spin.value())


class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings")
        self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"))
        self.setMinimumWidth(500)

        main_layout = QVBoxLayout(self)

        path_group = QGroupBox("MATLAB Executable Path")
        path_form_layout = QFormLayout() 
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path)
        self.path_edit.setPlaceholderText("Path to MATLAB executable (e.g., matlab.exe)")
        path_form_layout.addRow("Path:", self.path_edit)
        
        btn_layout = QHBoxLayout()
        auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_FileDialogContentsView, "Det"), "Auto-detect")
        auto_detect_btn.clicked.connect(self._auto_detect)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), "Browse...")
        browse_btn.clicked.connect(self._browse)
        btn_layout.addWidget(auto_detect_btn)
        btn_layout.addWidget(browse_btn)
        btn_layout.addStretch() 
        
        path_v_layout = QVBoxLayout() 
        path_v_layout.addLayout(path_form_layout)
        path_v_layout.addLayout(btn_layout)
        path_group.setLayout(path_v_layout)
        main_layout.addWidget(path_group)


        test_group = QGroupBox("Connection Test")
        test_layout = QVBoxLayout()
        self.test_status_label = QLabel("Status: Unknown")
        self.test_status_label.setWordWrap(True)
        test_btn = QPushButton(get_standard_icon(QStyle.SP_CommandLink, "Test"), "Test Connection")
        test_btn.clicked.connect(self._test_connection_and_update_label) 
        test_layout.addWidget(test_btn)
        test_layout.addWidget(self.test_status_label)
        test_group.setLayout(test_layout)
        main_layout.addWidget(test_group)

        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.accepted.connect(self._apply_settings)
        dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)
        
        # Connect signal AFTER UI elements that it might update are created
        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        # Initial status display
        if self.matlab_connection.matlab_path and self.matlab_connection.connected:
            self._update_test_label_from_signal(True, f"MATLAB path: {self.matlab_connection.matlab_path}")
        elif self.matlab_connection.matlab_path and not self.matlab_connection.connected: # Path set but connection failed
             self._update_test_label_from_signal(False, f"MATLAB path set ({self.matlab_connection.matlab_path}), but connection failed or not tested.")
        else:
            self._update_test_label_from_signal(False, "MATLAB path not set.")


    def _auto_detect(self):
        self.test_status_label.setText("Status: Auto-detecting MATLAB...")
        QApplication.processEvents() # Allow UI to update
        if self.matlab_connection.detect_matlab(): 
            self.path_edit.setText(self.matlab_connection.matlab_path)
            # Signal will update the label
        else:
            # Signal from detect_matlab already handles this
            pass


    def _browse(self):
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        # Try to start browsing from the current path if valid, else home
        start_dir = os.path.dirname(self.path_edit.text()) if self.path_edit.text() and os.path.exists(os.path.dirname(self.path_edit.text())) else QDir.homePath()
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path:
            self.path_edit.setText(path)
            # Don't automatically test, let user click Test or Apply
            self._update_test_label_from_signal(False, "Path changed. Test or Apply to confirm.")


    def _test_connection_and_update_label(self):
        path = self.path_edit.text()
        if not path:
            self._update_test_label_from_signal(False, "MATLAB path is empty.")
            return

        self.test_status_label.setText("Status: Testing connection with current path...")
        self.test_status_label.setStyleSheet("") # Reset color
        QApplication.processEvents()
        
        # Temporarily set path for testing without committing it if test fails immediately
        # The MatlabConnection.set_matlab_path itself emits status changes
        current_path_valid = self.matlab_connection.set_matlab_path(path)
        if current_path_valid:
            self.matlab_connection.test_connection() # This will emit status change
        # If set_matlab_path returned false, it already emitted the "invalid path" status.


    def _update_test_label_from_signal(self, success, message):
        status_text = "Status: " + message
        self.test_status_label.setText(status_text)
        self.test_status_label.setStyleSheet("color: green;" if success else "color: red;")
        if success and self.matlab_connection.matlab_path: # Ensure path_edit reflects confirmed path
             self.path_edit.setText(self.matlab_connection.matlab_path) 

    def _apply_settings(self):
        path = self.path_edit.text()
        # `set_matlab_path` will emit signal, which updates label and path_edit if successful
        if not self.matlab_connection.set_matlab_path(path):
            # If path is empty, set_matlab_path handles it.
            # If path is invalid, set_matlab_path handles it and emits.
            # This warning is a bit redundant if set_matlab_path fails due to invalidity.
            if path: # Only show warning if a path was actually provided but was bad
                QMessageBox.warning(self, "Invalid Path", 
                                    self.test_status_label.text().replace("Status: ", "") + 
                                    "\nPlease ensure the path is correct and executable.")
                # Do not accept the dialog if path is invalid and non-empty
                return 

        # If path is valid or empty, proceed to accept
        if path and self.matlab_connection.connected: # Path is set and seems valid initially
            # Re-test connection explicitly on Apply if not already successfully tested
            # This ensures the connection is live.
            # However, test_connection is already part of the flow or set_matlab_path logic.
            # The main thing is that the path is stored in matlab_connection.
            pass # set_matlab_path has done its job.

        self.accept()

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file_path = None
        self.last_generated_model_path = None # Store path of last Simulink model
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)
        
        # Pass self to scene so scene can trigger main window actions (e.g. select_mode_action)
        self.scene = DiagramScene(self.undo_stack, self) 
        self.scene.set_log_function(self.log_message)
        self.scene.modifiedStatusChanged.connect(self.setWindowModified) 
        self.scene.modifiedStatusChanged.connect(self._update_window_title) 


        self.init_ui()
        self._update_matlab_status_display(False, "Not Connected. Configure in Simulation menu.")
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        # self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_actions_enabled_state) # Covered by _update_matlab_status_display
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished) 

        self._update_window_title() 
        self.on_new_file(silent=True) # Create a new empty setup

        # Connect scene selection changes to update the properties dock
        self.scene.selectionChanged.connect(self._update_properties_dock)
        # Initial call to set properties dock state
        self._update_properties_dock()


    def init_ui(self):
        self.setGeometry(100, 100, 1400, 900)
        self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "App")) # Generic app icon
        
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_docks() # Docks should be created before central widget if they affect its size
        self._create_central_widget() # Central widget after docks usually

        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state() 
        self._update_undo_redo_actions_enable_state()
        
        # Set initial mode and ensure UI consistency
        self.select_mode_action.trigger() # Triggers scene.set_mode and updates QActionGroup
        self.scene.set_mode("select") # Explicitly set scene's internal mode too


    def _create_actions(self):
        # Helper to safely get QStyle enum values
        def _safe_get_style_enum(attr_name, fallback_attr_name=None):
            try: return getattr(QStyle, attr_name)
            except AttributeError:
                if fallback_attr_name:
                    try: return getattr(QStyle, fallback_attr_name)
                    except AttributeError: pass
                return QStyle.SP_CustomBase # A known invalid or base value


        # File
        self.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "New"), "&New", self, shortcut="Ctrl+N", statusTip="Create a new file", triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "Opn"), "&Open...", self, shortcut="Ctrl+O", statusTip="Open an existing file", triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Sav"), "&Save", self, shortcut="Ctrl+S", statusTip="Save the current file", triggered=self.on_save_file)
        self.save_as_action = QAction("Save &As...", self, shortcut="Ctrl+Shift+S", statusTip="Save the current file with a new name", triggered=self.on_save_file_as)
        self.exit_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", self, shortcut="Ctrl+Q", statusTip="Exit the application", triggered=self.close)

        # Edit
        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "Un"))
        self.undo_action.setStatusTip("Undo the last action")
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        self.redo_action.setShortcut("Ctrl+Y") # Common alternative: Ctrl+Shift+Z
        self.redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "Re"))
        self.redo_action.setStatusTip("Redo the last undone action")
        
        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.undo_stack.canRedoChanged.connect(self._update_undo_redo_actions_enable_state)

        self.select_all_action = QAction(get_standard_icon(_safe_get_style_enum("SP_FileDialogDetailedView", "SP_ Thủ thuật"), "All"), "Select &All", self, shortcut="Ctrl+A", statusTip="Select all items in the scene", triggered=self.on_select_all)
        self.delete_action = QAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "&Delete", self, shortcut="Delete", statusTip="Delete selected items", triggered=self.on_delete_selected)
        
        # Scene Interaction Modes
        self.mode_action_group = QActionGroup(self)
        self.mode_action_group.setExclusive(True)
        
        select_icon_enum = _safe_get_style_enum("SP_ArrowCursor", "SP_PointingHandCursor")
        self.select_mode_action = QAction(QIcon.fromTheme("edit-select", get_standard_icon(select_icon_enum, "Sel")), "Select/Move", self, checkable=True, statusTip="Mode: Select and move items", triggered=lambda: self.scene.set_mode("select"))
        
        state_icon_enum = _safe_get_style_enum("SP_FileDialogNewFolder", "SP_FileIcon") # NewFolder for "new state"
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", get_standard_icon(state_icon_enum, "St")), "Add State", self, checkable=True, statusTip="Mode: Click on canvas to add a new state", triggered=lambda: self.scene.set_mode("state"))
        
        trans_icon_enum = _safe_get_style_enum("SP_FileDialogBack", "SP_ArrowRight") # Back/Next often used for connections
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", get_standard_icon(trans_icon_enum, "Tr")), "Add Transition", self, checkable=True, statusTip="Mode: Click source then target state to add a transition", triggered=lambda: self.scene.set_mode("transition"))
        
        self.mode_action_group.addAction(self.select_mode_action)
        self.mode_action_group.addAction(self.add_state_mode_action)
        self.mode_action_group.addAction(self.add_transition_mode_action)
        self.select_mode_action.setChecked(True) # Default mode

        # Simulation
        self.export_simulink_action = QAction(get_standard_icon(QStyle.SP_ArrowRight, "->M"), "&Export to Simulink...", self, statusTip="Generate a Simulink model from the diagram", triggered=self.on_export_simulink)
        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation...", self, statusTip="Run a Simulink model", triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cde"), "Generate &Code (C/C++)...", self, statusTip="Generate C/C++ code from a Simulink model", triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(_safe_get_style_enum("SP_ComputerIcon","SP_DesktopIcon"), "Cfg"), "&MATLAB Settings...", self, statusTip="Configure MATLAB connection settings", triggered=self.on_matlab_settings)

        # Help
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, statusTip=f"Show information about {APP_NAME}", triggered=self.on_about)


    def _create_menus(self):
        menu_bar = self.menuBar()
        # File Menu
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_simulink_action) # Moved from its own menu for conciseness
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        # Edit Menu
        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.delete_action)
        edit_menu.addAction(self.select_all_action)
        edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_DesktopIcon),"Interaction Mode") # Icon for menu
        mode_menu.addAction(self.select_mode_action)
        mode_menu.addAction(self.add_state_mode_action)
        mode_menu.addAction(self.add_transition_mode_action)


        # Simulation Menu
        sim_menu = menu_bar.addMenu("&Simulation")
        sim_menu.addAction(self.run_simulation_action)
        sim_menu.addAction(self.generate_code_action)
        sim_menu.addSeparator()
        sim_menu.addAction(self.matlab_settings_action)

        # View Menu (for docks and other view options)
        self.view_menu = menu_bar.addMenu("&View")
        # Dock toggles will be added in _create_docks

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        # File Toolbar
        file_toolbar = self.addToolBar("File")
        file_toolbar.setObjectName("FileToolBar")
        file_toolbar.setIconSize(QSize(24,24))
        file_toolbar.addAction(self.new_action)
        file_toolbar.addAction(self.open_action)
        file_toolbar.addAction(self.save_action)

        # Edit Toolbar
        edit_toolbar = self.addToolBar("Edit")
        edit_toolbar.setObjectName("EditToolBar")
        edit_toolbar.setIconSize(QSize(24,24))
        edit_toolbar.addAction(self.undo_action)
        edit_toolbar.addAction(self.redo_action)
        edit_toolbar.addSeparator()
        edit_toolbar.addAction(self.delete_action)
        
        # Tools Toolbar (Interaction Modes)
        tools_toolbar = self.addToolBar("Tools")
        tools_toolbar.setObjectName("ToolsToolBar")
        tools_toolbar.setIconSize(QSize(24,24))
        tools_toolbar.addAction(self.select_mode_action)
        tools_toolbar.addAction(self.add_state_mode_action)
        tools_toolbar.addAction(self.add_transition_mode_action)

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready") # General status messages
        self.status_bar.addWidget(self.status_label, 1) # Stretch factor 1

        self.matlab_status_label = QLabel("MATLAB: Unknown")
        self.matlab_status_label.setToolTip("MATLAB connection status. Configure in Simulation > MATLAB Settings.")
        self.status_bar.addPermanentWidget(self.matlab_status_label)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0,0) # Indeterminate progress
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(150) # Limit width
        self.status_bar.addPermanentWidget(self.progress_bar)


    def _create_docks(self):
        # Tools Dock (replaces ToolboxDock)
        self.tools_dock = QDockWidget("Tools", self)
        self.tools_dock.setObjectName("ToolsDock")
        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)
        tools_layout.setSpacing(10)
        tools_layout.setContentsMargins(5, 5, 5, 5)

        # Mode Buttons Section (using QToolButton linked to actions)
        mode_group = QGroupBox("Interaction Modes")
        mode_layout = QVBoxLayout()

        self.toolbox_select_button = QToolButton()
        self.toolbox_select_button.setDefaultAction(self.select_mode_action)
        self.toolbox_select_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mode_layout.addWidget(self.toolbox_select_button)

        # If you want an "Add State" mode button in toolbox as well:
        self.toolbox_add_state_button = QToolButton()
        self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action)
        self.toolbox_add_state_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mode_layout.addWidget(self.toolbox_add_state_button)


        self.toolbox_transition_button = QToolButton()
        self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action)
        self.toolbox_transition_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mode_layout.addWidget(self.toolbox_transition_button)
        
        mode_group.setLayout(mode_layout)
        tools_layout.addWidget(mode_group)


        # Draggable Items Section
        draggable_group = QGroupBox("Drag to Canvas")
        draggable_layout = QVBoxLayout()
        
        state_drag_button = DraggableToolButton(
            "State", # Text for the button (and for mime data)
            "application/x-state-tool",
            # Basic styling, can be enhanced
            "QPushButton { background-color: #B0E0E6; color: #1A5276; border: 1px solid #77AABB; padding: 5px; }"
            "QPushButton:hover { background-color: #A0D0D6; }"
        )
        state_drag_button.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))
        state_drag_button.setIconSize(QSize(20,20))
        draggable_layout.addWidget(state_drag_button)
        draggable_group.setLayout(draggable_layout)
        tools_layout.addWidget(draggable_group)

        tools_layout.addStretch() # Push content to the top
        self.tools_dock.setWidget(tools_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock)
        self.view_menu.addAction(self.tools_dock.toggleViewAction())

        # Log Dock
        self.log_dock = QDockWidget("Log Output", self)
        self.log_dock.setObjectName("LogDock")
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Courier New", 9))
        self.log_dock.setWidget(self.log_output)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.view_menu.addAction(self.log_dock.toggleViewAction())
        
        # Properties Dock
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        properties_widget = QWidget()
        self.properties_layout = QVBoxLayout(properties_widget) # Use a layout
        self.properties_editor_label = QLabel("No item selected.")
        self.properties_editor_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.properties_editor_label.setWordWrap(True)
        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton,"Edt"), "Edit Properties...")
        self.properties_edit_button.setEnabled(False)
        self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock)

        self.properties_layout.addWidget(self.properties_editor_label, 1) # Label takes available space
        self.properties_layout.addWidget(self.properties_edit_button)
        # self.properties_layout.addStretch() # Removed to let label expand
        properties_widget.setLayout(self.properties_layout)
        self.properties_dock.setWidget(properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        self.view_menu.addAction(self.properties_dock.toggleViewAction())


    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self) # Use the new ZoomableView class
        self.setCentralWidget(self.view)

    # Method to update Properties Dock based on scene selection
    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1:
            item = selected_items[0]
            item_info = "<b>Type:</b> "
            if isinstance(item, GraphicsStateItem):
                item_info += "State<br>"
                item_info += f"<b>Name:</b> {item.text_label}<br>"
                item_info += f"<b>Initial:</b> {'Yes' if item.is_initial else 'No'}<br>"
                item_info += f"<b>Final:</b> {'Yes' if item.is_final else 'No'}"
            elif isinstance(item, GraphicsTransitionItem):
                item_info += "Transition<br>"
                item_info += f"<b>Label:</b> {item.text_label if item.text_label else '[No Label]'}<br>"
                item_info += f"<b>From:</b> {item.start_item.text_label if item.start_item else 'N/A'}<br>"
                item_info += f"<b>To:</b> {item.end_item.text_label if item.end_item else 'N/A'}<br>"
                item_info += f"<b>Curve Offset:</b> ({item.control_point_offset.x():.0f}, {item.control_point_offset.y():.0f})"
            else:
                item_info += "Unknown Item"
            
            self.properties_editor_label.setText(item_info)
            self.properties_edit_button.setEnabled(True)
        elif len(selected_items) > 1:
            self.properties_editor_label.setText(f"<b>{len(selected_items)} items selected.</b><br>Batch editing not yet supported.")
            self.properties_edit_button.setEnabled(False)
        else:
            self.properties_editor_label.setText("<i>No item selected.</i><br>Click an item in the diagram to see its properties.")
            self.properties_edit_button.setEnabled(False)

    def _on_edit_selected_item_properties_from_dock(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1:
            self.scene.edit_item_properties(selected_items[0]) # Call existing scene method


    def log_message(self, message):
        self.log_output.append(f"[{QTime.currentTime().toString('hh:mm:ss')}] {message}")
        self.status_label.setText(message.split('\n')[0][:100]) # Show first line in status bar
        # QTimer.singleShot(5000, lambda: self.status_label.setText("Ready")) # Reset status bar after a delay

    def _update_window_title(self):
        title = APP_NAME
        if self.current_file_path:
            title += f" - {os.path.basename(self.current_file_path)}"
        else:
            title += " - Untitled"
        
        title += "[*]" # For setWindowModified asterisk
        self.setWindowTitle(title)

    def _update_save_actions_enable_state(self):
        is_dirty = self.scene.is_dirty()
        self.save_action.setEnabled(is_dirty)
        # save_as_action is always enabled if there's content, or could be tied to dirty too.
        # For simplicity, let save_as always be enabled if a scene exists.

    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo())
        self.redo_action.setEnabled(self.undo_stack.canRedo())

    def _update_matlab_status_display(self, connected, message):
        self.matlab_status_label.setText(f"MATLAB: {'Connected' if connected else 'Disconnected'}")
        self.matlab_status_label.setStyleSheet("color: green; font-weight: bold;" if connected else "color: red;")
        self.log_message(f"MATLAB Status Update: {message}") # Log the detailed message
        self._update_matlab_actions_enabled_state()

    def _update_matlab_actions_enabled_state(self):
        connected = self.matlab_connection.connected
        self.export_simulink_action.setEnabled(connected)
        self.run_simulation_action.setEnabled(connected)
        self.generate_code_action.setEnabled(connected)

    def _start_matlab_operation(self, operation_name):
        self.log_message(f"MATLAB Operation: {operation_name} started...")
        self.progress_bar.setVisible(True)
        # Disable parts of UI that shouldn't be used during MATLAB op
        self.menuBar().setEnabled(False) 
        for i in range(self.layout().count()): # Disable toolbars - more complex
            toolbar = self.layout().itemAt(i).widget()
            if isinstance(toolbar, QToolBar):
                toolbar.setEnabled(False)
        if self.centralWidget(): self.centralWidget().setEnabled(False)
        for dock_name in ["ToolsDock", "PropertiesDock"]: # Docks
            dock = self.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(False)


    def _finish_matlab_operation(self):
        self.progress_bar.setVisible(False)
        self.menuBar().setEnabled(True)
        for i in range(self.layout().count()):
            toolbar = self.layout().itemAt(i).widget()
            if isinstance(toolbar, QToolBar):
                toolbar.setEnabled(True)
        if self.centralWidget(): self.centralWidget().setEnabled(True)
        for dock_name in ["ToolsDock", "PropertiesDock"]:
            dock = self.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(True)
        self.log_message("MATLAB Operation: Finished.")


    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation()
        self.log_message(f"MATLAB Process Result: {message}") # Log first
        if success:
            if "Model generation" in message and data: 
                 self.last_generated_model_path = data # Store for later use
                 QMessageBox.information(self, "Simulink Model Generation", 
                                        f"Model generated successfully:\n{data}")
            elif "Simulation" in message: # 'message' here might be the success output from MATLAB
                 QMessageBox.information(self, "Simulation Complete", f"Simulation finished.\nDetails: {message}")
        else:
            QMessageBox.warning(self, "MATLAB Operation Failed", message)
        
    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation()
        self.log_message(f"MATLAB Code Generation Result: {message}") # Log first
        if success and output_dir:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText) # Allow HTML like links
            msg_box.setText(f"Code generation successful.<br>"
                            f"Output directory: <a href='file:///{output_dir}'>{output_dir}</a>")
            
            open_dir_button = msg_box.addButton("Open Directory", QMessageBox.ActionRole)
            msg_box.addButton(QMessageBox.Ok)
            msg_box.exec_()

            if msg_box.clickedButton() == open_dir_button:
                try:
                    if sys.platform == "win32":
                        os.startfile(output_dir)
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", output_dir])
                    else: # Linux, etc.
                        subprocess.Popen(["xdg-open", output_dir])
                except Exception as e:
                    self.log_message(f"Could not open directory {output_dir}: {e}")
                    QMessageBox.warning(self, "Error Opening Directory", f"Could not open directory:\n{e}")

        elif not success:
            QMessageBox.warning(self, "Code Generation Failed", message)


    # --- File Operations ---
    def _prompt_save_if_dirty(self):
        if not self.scene.is_dirty(): # Or: if not self.isWindowModified()
            return True 
        
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes",
                                     f"The document '{file_name}' has unsaved changes.\n"
                                     "Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save) # Default to Save
        if reply == QMessageBox.Save:
            return self.on_save_file() # Returns True if save successful, False otherwise
        elif reply == QMessageBox.Cancel:
            return False # User cancelled operation
        return True # User chose Discard

    def on_new_file(self, silent=False): # silent used for initial setup
        if not silent and not self._prompt_save_if_dirty():
            return False # Indicate operation was cancelled
        
        self.scene.clear() # Clears items
        self.scene.setSceneRect(0,0,4000,3000) # Reset scene rect if it was changed
        self.current_file_path = None
        self.last_generated_model_path = None # Reset
        self.scene.set_dirty(False) # New file is not dirty
        self.undo_stack.clear() # Clear undo history
        self._update_window_title()
        self._update_save_actions_enable_state()
        self._update_undo_redo_actions_enable_state()
        if not silent: self.log_message("New diagram created.")
        self.select_mode_action.trigger() # Ensure select mode is active
        return True


    def on_open_file(self):
        if not self._prompt_save_if_dirty():
            return
        
        # Default directory: user's documents or home, or last used dir
        start_dir = QDir.homePath() 
        if self.current_file_path:
            start_dir = os.path.dirname(self.current_file_path)

        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", start_dir, FILE_FILTER)
        if file_path:
            if self._load_from_path(file_path):
                self.current_file_path = file_path
                self.last_generated_model_path = None # Reset
                self.scene.set_dirty(False) 
                self.undo_stack.clear()
                self._update_window_title()
                self._update_save_actions_enable_state()
                self._update_undo_redo_actions_enable_state()
                self.log_message(f"File opened: {file_path}")
                # Fit view to content after loading
                self.view.setSceneRect(self.scene.itemsBoundingRect().adjusted(-50,-50,50,50)) # Add margin
                self.view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

            else: # _load_from_path failed
                QMessageBox.critical(self, "Error Opening File", f"Could not load file: {file_path}")
                self.log_message(f"Failed to open file: {file_path}")


    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            # Basic validation of file content
            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data:
                self.log_message(f"Error: Invalid file format in {file_path}. Missing 'states' or 'transitions'.")
                return False
            self.scene.load_diagram_data(data) # Scene handles item creation
            return True
        except json.JSONDecodeError as e:
            self.log_message(f"Error decoding JSON from file {file_path}: {str(e)}")
            QMessageBox.critical(self, "Load Error", f"Failed to parse file (invalid JSON):\n{str(e)}")
            return False
        except Exception as e:
            self.log_message(f"Error loading file {file_path}: {str(e)}")
            QMessageBox.critical(self, "Load Error", f"An unexpected error occurred while loading file:\n{str(e)}")
            return False

    def on_save_file(self):
        if self.current_file_path:
            if self._save_to_path(self.current_file_path):
                self.scene.set_dirty(False) # Mark as not modified
                self._update_save_actions_enable_state()
                return True
            return False # Save failed
        else:
            return self.on_save_file_as() # Prompts for new path

    def on_save_file_as(self):
        default_filename = os.path.basename(self.current_file_path) if self.current_file_path else "untitled" + FILE_EXTENSION
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Save File As", 
                                                   os.path.join(start_dir, default_filename), 
                                                   FILE_FILTER)
        if file_path:
            # Ensure correct extension
            if not file_path.lower().endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION
            
            if self._save_to_path(file_path):
                self.current_file_path = file_path # Update current path
                self.scene.set_dirty(False) # Mark as not modified
                self._update_window_title() # Update title with new path
                self._update_save_actions_enable_state()
                return True
        return False # User cancelled or save failed

    def _save_to_path(self, file_path):
        try:
            data = self.scene.get_diagram_data()
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4) # Pretty print JSON
            self.log_message(f"File saved: {file_path}")
            return True
        except Exception as e:
            self.log_message(f"Error saving file {file_path}: {str(e)}")
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{str(e)}")
            return False
            
    # --- Action Handlers ---
    def on_select_all(self):
        self.scene.select_all()

    def on_delete_selected(self):
        self.scene.delete_selected_items() 

    def on_export_simulink(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected. Please configure MATLAB settings first.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Export to Simulink")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowRight, "->M"))
        layout = QFormLayout(dialog)
        
        model_name_edit = QLineEdit("BrainStateMachineModel")
        layout.addRow("Model Name:", model_name_edit)

        # Default output directory to document's directory or home
        default_out_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        output_dir_edit = QLineEdit(default_out_dir)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"),"Browse...")
        def browse_dir():
            d = QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text())
            if d: output_dir_edit.setText(d)
        browse_btn.clicked.connect(browse_dir)
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(output_dir_edit)
        dir_layout.addWidget(browse_btn)
        layout.addRow("Output Directory:", dir_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            model_name = model_name_edit.text().strip()
            output_dir = output_dir_edit.text().strip()
            if not model_name or not output_dir:
                QMessageBox.warning(self, "Input Error", "Model name and output directory must be specified.")
                return
            
            # Validate model name (basic check for typical Simulink model name rules)
            if not model_name[0].isalpha() or not model_name.replace('_','').isalnum():
                QMessageBox.warning(self, "Invalid Model Name", "Model name must start with a letter and contain only alphanumeric characters and underscores.")
                return

            if not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                except OSError as e:
                    QMessageBox.critical(self, "Directory Error", f"Could not create output directory:\n{e}")
                    return

            diagram_data = self.scene.get_diagram_data()
            if not diagram_data['states']:
                QMessageBox.information(self, "Empty Diagram", "Cannot export an empty diagram (no states found).")
                return

            self._start_matlab_operation("Simulink model generation")
            self.matlab_connection.generate_simulink_model(
                diagram_data['states'], diagram_data['transitions'], output_dir, model_name
            )

    def on_run_simulation(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected.")
            return

        # Default to last generated model or user's home directory
        default_model_dir = os.path.dirname(self.last_generated_model_path) if self.last_generated_model_path else QDir.homePath()
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model (.slx)", 
                                                   default_model_dir, 
                                                   "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path # Update for next time

        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Enter simulation time (seconds):", 10.0, 0.01, 36000.0, 2) # Min, Max, Decimals
        if not ok: return

        self._start_matlab_operation("Simulink simulation")
        self.matlab_connection.run_simulation(model_path, sim_time)


    def on_generate_code(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected.")
            return

        default_model_dir = os.path.dirname(self.last_generated_model_path) if self.last_generated_model_path else QDir.homePath()
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model (.slx) for Code Generation",
                                                   default_model_dir,
                                                   "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return
        
        self.last_generated_model_path = model_path # Update

        dialog = QDialog(self)
        dialog.setWindowTitle("Generate Code Options")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cde"))
        layout = QFormLayout(dialog)

        lang_combo = QComboBox()
        lang_combo.addItems(["C", "C++"])
        lang_combo.setCurrentText("C++") # Default to C++
        layout.addRow("Target Language:", lang_combo)

        # Default output base directory to model's directory
        default_output_base = os.path.dirname(model_path)
        output_dir_edit = QLineEdit(default_output_base) 
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), "Browse...")
        def browse_dir_codegen():
            d = QFileDialog.getExistingDirectory(dialog, "Select Base Output Directory for Code", output_dir_edit.text())
            if d: output_dir_edit.setText(d)
        browse_btn.clicked.connect(browse_dir_codegen)
        dir_layout_codegen = QHBoxLayout()
        dir_layout_codegen.addWidget(output_dir_edit)
        dir_layout_codegen.addWidget(browse_btn)
        layout.addRow("Base Output Directory:", dir_layout_codegen)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            language = lang_combo.currentText()
            output_dir_base = output_dir_edit.text().strip()
            if not output_dir_base:
                QMessageBox.warning(self, "Input Error", "Base output directory must be specified.")
                return
            
            if not os.path.exists(output_dir_base):
                 try: os.makedirs(output_dir_base, exist_ok=True)
                 except OSError as e:
                     QMessageBox.critical(self, "Directory Error", f"Could not create output directory:\n{e}")
                     return

            self._start_matlab_operation("Code generation")
            self.matlab_connection.generate_code(model_path, language, output_dir_base)

    def on_matlab_settings(self):
        dialog = MatlabSettingsDialog(self.matlab_connection, self)
        dialog.exec_() # Dialog handles applying settings to matlab_connection

    def on_about(self):
        QMessageBox.about(self, "About " + APP_NAME,
                          f"<b>{APP_NAME}</b> v{APP_VERSION}\n\n"
                          "A graphical tool for designing brain-inspired state machines and "
                          "integrating with MATLAB/Simulink for simulation and code generation.\n\n"
                          "Features:\n"
                          "- Intuitive state and transition creation\n"
                          "- Undo/Redo support\n"
                          "- Save/Load designs in JSON format\n"
                          "- Simulink model export\n"
                          "- Simulation via MATLAB (requires Simulink & Stateflow)\n"
                          "- C/C++ code generation (requires Simulink Coder/Embedded Coder)\n\n"
                          "(c) 2024 AI Revell Lab")


    def closeEvent(self, event):
        if self._prompt_save_if_dirty():
            # Attempt to clean up any running MATLAB threads gracefully
            active_threads = list(self.matlab_connection._active_threads) # Copy list
            if active_threads:
                self.log_message(f"Attempting to close {len(active_threads)} active MATLAB process(es)...")
                # This is a simple quit, processes might not terminate instantly.
                # A more robust solution would involve QProcess and terminate/kill signals.
                for thread in active_threads:
                    if thread.isRunning():
                        thread.quit() # Request thread to stop
                        thread.wait(1000) # Wait up to 1 sec
                        if thread.isRunning():
                             self.log_message(f"Warning: MATLAB thread {thread} did not terminate gracefully.")
                             # For subprocesses, one might need to store process PIDs and try to terminate.
            event.accept()
        else:
            event.ignore() # User cancelled closing


if __name__ == '__main__':
    # Enable High DPI scaling for better look on modern displays
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    
    # Apply a style for a more modern look, if desired (optional)
    # app.setStyle("Fusion") 

    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
