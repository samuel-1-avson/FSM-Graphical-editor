Okay, I understand. It seems the previous response was too long and got truncated, leading to incomplete code and issues.

I will revert to the version of the code you provided at the very beginning of our conversation (which you confirmed was working) and *then carefully* apply the following enhancements:

1.  **APP_VERSION**: Set to "1.6.0".
2.  **Drag-and-Drop Transition Tool**: A new button in the "Drag to Canvas" toolbox. Dropping it will activate the "Add Transition" mode.
3.  **Mechatronics/Embedded Placeholder Texts**: Update placeholder examples in State and Transition property dialogs.
4.  **Chart I/O Data Definition**:
    *   New "Chart I/O Data..." action in the "Simulation" menu.
    *   A new dialog (`ChartIOPropertiesDialog`) to define Inputs, Outputs, Local data, Parameters, and Constants for the Stateflow chart (Name, Scope, Data Type, Initial Value, Description).
    *   Store this I/O data within the `.bsm` project file.
    *   When exporting to Simulink, these data items will be created as `Stateflow.Data` objects in the chart, automatically generating Inports and Outports for "Input" and "Output" scopes.

This will be a more methodical approach. I'll ensure the new features are integrated without breaking existing functionality.

Here is the updated code, starting from your original base and with the new features and fixes carefully integrated:

```python
import sys
import os
import tempfile
import subprocess
import json
import html # <--- Added this import
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QToolBox, QAction,
    QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
    QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
    QFileDialog, QProgressBar, QTabWidget, QCheckBox, QActionGroup, QGraphicsItem,
    QGroupBox, QUndoStack, QUndoCommand, QStyle, QSizePolicy, QGraphicsLineItem,
    QToolButton, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent,
    QGraphicsSceneHoverEvent, QGraphicsTextItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform, QKeyEvent, QPainterPathStroker, QPolygonF, QKeySequence,
    QDesktopServices, QWheelEvent, QMouseEvent, QCloseEvent, QFontMetrics
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QTimer, QSize, QTime, QUrl,
    QSaveFile, QIODevice
)
import math


# --- Configuration ---
APP_VERSION = "1.6.0" # Incremented for Chart I/O, Drag Transition, fixes
APP_NAME = "Brain State Machine Designer"
FILE_EXTENSION = ".bsm"
FILE_FILTER = f"Brain State Machine Files (*{FILE_EXTENSION});;All Files (*)"
CHART_DATA_SCOPES = ["Input", "Output", "Local", "Parameter", "Constant"]
CHART_DATA_TYPES = ["double", "single", "int8", "uint8", "int16", "uint16", "int32", "uint32", "boolean"]


# --- Utility Functions ---
def get_standard_icon(standard_pixmap_enum_value, fallback_text=None):
    icon = QIcon()
    try:
        icon = QApplication.style().standardIcon(standard_pixmap_enum_value)
    except Exception as e:
        print(f"Warning: Error getting standard icon for enum value {standard_pixmap_enum_value}: {e}")
        icon = QIcon() # Fallback to empty icon

    if icon.isNull():
        if fallback_text:
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.drawText(pixmap.rect(), Qt.AlignCenter, fallback_text[:2])
            painter.end()
            return QIcon(pixmap)
        else:
            # Generic fallback placeholder icon
            pixmap = QPixmap(16,16)
            pixmap.fill(QColor(192,192,192))
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
    connectionStatusChanged = pyqtSignal(bool, str)
    simulationFinished = pyqtSignal(bool, str, str)
    codeGenerationFinished = pyqtSignal(bool, str, str)

    def __init__(self):
        super().__init__()
        self.matlab_path = ""
        self.connected = False
        self._active_threads = []

    def set_matlab_path(self, path):
        self.matlab_path = path.strip()
        if self.matlab_path and os.path.exists(self.matlab_path) and \
           (os.access(self.matlab_path, os.X_OK) or self.matlab_path.lower().endswith('.exe')):
            self.connected = True
            self.connectionStatusChanged.emit(True, f"MATLAB path set and appears valid: {self.matlab_path}")
            return True
        else:
            old_path = self.matlab_path
            self.connected = False
            self.matlab_path = ""
            if old_path:
                self.connectionStatusChanged.emit(False, f"MATLAB path '{old_path}' is invalid or not executable.")
            else:
                self.connectionStatusChanged.emit(False, "MATLAB path cleared.")
            return False

    def test_connection(self):
        if not self.matlab_path:
            self.connected = False
            self.connectionStatusChanged.emit(False, "MATLAB path not set. Cannot test connection.")
            return False
        if not self.connected and self.matlab_path :
             if not self.set_matlab_path(self.matlab_path):
                  return False

        try:
            cmd = [self.matlab_path, "-nodisplay", "-batch", "disp('MATLAB_CONNECTION_TEST_SUCCESS')"]
            process = subprocess.run(
                cmd, capture_output=True, text=True, timeout=20, check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if "MATLAB_CONNECTION_TEST_SUCCESS" in process.stdout:
                self.connected = True
                self.connectionStatusChanged.emit(True, "MATLAB connection test successful.")
                return True
            else:
                self.connected = False
                error_msg = process.stderr or process.stdout or "Unexpected output from MATLAB."
                self.connectionStatusChanged.emit(False, f"MATLAB connection test failed: {error_msg[:200]}")
                return False
        except subprocess.TimeoutExpired:
            self.connected = False
            self.connectionStatusChanged.emit(False, "MATLAB connection test timed out (20s).")
            return False
        except subprocess.CalledProcessError as e:
            self.connected = False
            self.connectionStatusChanged.emit(False, f"MATLAB error during test: {e.stderr or e.stdout or str(e)}".splitlines()[0])
            return False
        except FileNotFoundError:
            self.connected = False
            self.connectionStatusChanged.emit(False, f"MATLAB executable not found at: {self.matlab_path}")
            return False
        except Exception as e:
            self.connected = False
            self.connectionStatusChanged.emit(False, f"An unexpected error occurred during MATLAB test: {str(e)}")
            return False

    def detect_matlab(self):
        paths_to_check = []
        if sys.platform == 'win32':
            program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
            matlab_base = os.path.join(program_files, 'MATLAB')
            if os.path.isdir(matlab_base):
                versions = sorted([d for d in os.listdir(matlab_base) if d.startswith('R20')], reverse=True)
                for v_year_letter in versions:
                    paths_to_check.append(os.path.join(matlab_base, v_year_letter, 'bin', 'matlab.exe'))
        elif sys.platform == 'darwin':
            base_app_path = '/Applications'
            potential_matlab_apps = sorted([d for d in os.listdir(base_app_path) if d.startswith('MATLAB_R20') and d.endswith('.app')], reverse=True)
            for app_name in potential_matlab_apps:
                 paths_to_check.append(os.path.join(base_app_path, app_name, 'bin', 'matlab'))
        else: # Linux / other Unix
            common_base_paths = ['/usr/local/MATLAB', '/opt/MATLAB']
            for base_path in common_base_paths:
                if os.path.isdir(base_path):
                    versions = sorted([d for d in os.listdir(base_path) if d.startswith('R20')], reverse=True)
                    for v_year_letter in versions:
                         paths_to_check.append(os.path.join(base_path, v_year_letter, 'bin', 'matlab'))
            paths_to_check.append('matlab') # Check if 'matlab' is in PATH

        for path_candidate in paths_to_check:
            if path_candidate == 'matlab' and sys.platform != 'win32': # Check if in PATH (non-Windows)
                try:
                    test_process = subprocess.run([path_candidate, "-batch", "exit"], timeout=5, capture_output=True)
                    if test_process.returncode == 0:
                        if self.set_matlab_path(path_candidate):
                           return True
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue # Try next candidate
            elif os.path.exists(path_candidate): # Check if explicit path exists
                if self.set_matlab_path(path_candidate):
                    return True

        self.connectionStatusChanged.emit(False, "MATLAB auto-detection failed. Please set the path manually.")
        return False

    def _run_matlab_script(self, script_content, worker_signal, success_message_prefix):
        if not self.connected:
            worker_signal.emit(False, "MATLAB not connected or path invalid.", "")
            return

        try:
            temp_dir = tempfile.mkdtemp(prefix="bsm_matlab_")
            script_file = os.path.join(temp_dir, "matlab_script.m")
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(script_content)
        except Exception as e:
            worker_signal.emit(False, f"Failed to create temporary MATLAB script: {e}", "")
            return

        worker = MatlabCommandWorker(self.matlab_path, script_file, worker_signal, success_message_prefix)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run_command)
        worker.finished_signal.connect(thread.quit)
        worker.finished_signal.connect(worker.deleteLater) # Clean up worker
        thread.finished.connect(thread.deleteLater)      # Clean up thread
        self._active_threads.append(thread)
        thread.finished.connect(lambda t=thread: self._active_threads.remove(t) if t in self._active_threads else None)
        thread.start()

    def generate_simulink_model(self, states, transitions, chart_io_data, output_dir, model_name="BrainStateMachine"):
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected.", "")
            return False

        slx_file_path = os.path.join(output_dir, f"{model_name}.slx").replace('\\', '/')
        model_name_orig = model_name # For use in strings

        script_lines = [
            f"% Auto-generated Simulink model script for '{model_name_orig}'",
            f"disp('Starting Simulink model generation for {model_name_orig}...');",
            f"modelNameVar = '{model_name_orig}';",
            f"outputModelPath = '{slx_file_path}';",
            "try",
            "    if bdIsLoaded(modelNameVar), close_system(modelNameVar, 0); end",
            "    if exist(outputModelPath, 'file'), delete(outputModelPath); end",
            "    hModel = new_system(modelNameVar);",
            "    open_system(hModel);",
            "    disp('Adding Stateflow chart...');",
            "    machine = sfroot.find('-isa', 'Stateflow.Machine', 'Name', modelNameVar);",
            "    if isempty(machine)",
            "        error('Stateflow machine for model ''%s'' not found after new_system.', modelNameVar);",
            "    end",
            "    chartSFObj = Stateflow.Chart(machine);",
            "    chartSFObj.Name = 'BSM_Logic'; % Customizable Chart Name", # Make name consistent/customizable
            "    chartBlockSimulinkPath = [modelNameVar, '/', chartSFObj.Name];",
            "    add_block('stateflow/Chart', chartBlockSimulinkPath, 'Chart', chartSFObj.Path);",
            "    disp(['Stateflow chart block added at: ', chartBlockSimulinkPath]);",
            # Chart I/O Data Definition
            "% --- Chart Data Objects (Inputs, Outputs, Locals, Parameters, Constants) ---",
            "chartDataMap = containers.Map('KeyType','char','ValueType','any');"
        ]

        # Mapping of tool scopes to Stateflow.DataScope strings
        sf_scope_map = {
            "Input": "Input",
            "Output": "Output",
            "Local": "Local",
            "Parameter": "Parameter",
            "Constant": "Constant"
        }

        for io_item in chart_io_data:
            io_name = io_item['name'].replace("'", "''") # Escape single quotes
            io_scope_tool = io_item['scope']
            io_scope_sf = sf_scope_map.get(io_scope_tool, "Local") # Default to Local if scope somehow invalid
            io_type = io_item['datatype']
            io_init_val = io_item.get('initial_value', '').replace("'", "''") # Escape single quotes

            # Create a MATLAB-safe variable name for the data handle
            io_id_safe = f"data_{io_name.replace(' ', '_')}"
            io_id_safe = ''.join(filter(str.isalnum, io_id_safe)) # Remove non-alphanumeric
            if not io_id_safe or not io_id_safe[0].isalpha(): io_id_safe = 'd_' + io_id_safe # Ensure starts with letter

            script_lines.extend([
                f"{io_id_safe} = Stateflow.Data(chartSFObj);",
                f"{io_id_safe}.Name = '{io_name}';",
                f"{io_id_safe}.Scope = '{io_scope_sf}';", # Stateflow expects 'Input', 'Output', 'Local', etc.
                f"{io_id_safe}.DataType = '{io_type}';"
            ])
            # InitialValue property is under 'Props' sub-object for some SF versions or data objects.
            # Using try-catch for robustness.
            if io_scope_tool in ["Local", "Parameter", "Constant"] and io_init_val:
                 script_lines.append(f"    try, {io_id_safe}.Props.InitialValue = '{io_init_val}'; catch e_init, disp(['Warning: Could not set InitialValue for {io_name}: ', e_init.message]); end")

            # Stateflow automatically numbers ports for Inputs and Outputs.
            # If you needed explicit port numbers (rarely), it would be {io_id_safe}.Port = X;

            script_lines.append(f"chartDataMap('{io_name}') = {io_id_safe};")


        script_lines.append("    stateHandles = containers.Map('KeyType','char','ValueType','any');")
        script_lines.append("% --- State Creation ---")

        for i, state in enumerate(states):
            s_name_matlab = state['name'].replace("'", "''")
            s_id_matlab_safe = f"state_{i}_{state['name'].replace(' ', '_').replace('-', '_')}"
            s_id_matlab_safe = ''.join(filter(str.isalnum, s_id_matlab_safe))
            if not s_id_matlab_safe or not s_id_matlab_safe[0].isalpha(): s_id_matlab_safe = 's_' + s_id_matlab_safe
            state_label_parts = []
            if state.get('entry_action'): state_label_parts.append(f"entry: {state['entry_action'].replace(chr(10), '; ')}")
            if state.get('during_action'): state_label_parts.append(f"during: {state['during_action'].replace(chr(10), '; ')}")
            if state.get('exit_action'): state_label_parts.append(f"exit: {state['exit_action'].replace(chr(10), '; ')}")
            s_label_string_matlab = ("\\n".join(state_label_parts)).replace("'", "''")
            script_lines.extend([
                f"{s_id_matlab_safe} = Stateflow.State(chartSFObj);",
                f"{s_id_matlab_safe}.Name = '{s_name_matlab}';",
                f"{s_id_matlab_safe}.Position = [{state['x']/3}, {state['y']/3}, {state['width']/3}, {state['height']/3}];", # Rough scaling
                f"if ~isempty('{s_label_string_matlab}'), {s_id_matlab_safe}.LabelString = sprintf('{s_label_string_matlab}'); end",
                f"stateHandles('{s_name_matlab}') = {s_id_matlab_safe};"
            ])
            if state.get('is_initial', False):
                script_lines.append(f"defaultTransition_{i} = Stateflow.Transition(chartSFObj);")
                script_lines.append(f"defaultTransition_{i}.Destination = {s_id_matlab_safe};")

        script_lines.append("% --- Transition Creation ---")
        for i, trans in enumerate(transitions):
            src_name_matlab = trans['source'].replace("'", "''")
            dst_name_matlab = trans['target'].replace("'", "''")
            label_parts = []
            if trans.get('event'): label_parts.append(trans['event'])
            if trans.get('condition'): label_parts.append(f"[{trans['condition']}]")
            if trans.get('action'): label_parts.append(f"/{{{trans['action']}}}")
            t_label_matlab = (" ".join(label_parts).strip()).replace("'", "''")
            script_lines.extend([
                f"if isKey(stateHandles, '{src_name_matlab}') && isKey(stateHandles, '{dst_name_matlab}')",
                f"    srcStateHandle = stateHandles('{src_name_matlab}');",
                f"    dstStateHandle = stateHandles('{dst_name_matlab}');",
                f"    t{i} = Stateflow.Transition(chartSFObj);",
                f"    t{i}.Source = srcStateHandle;",
                f"    t{i}.Destination = dstStateHandle;"
            ])
            if t_label_matlab: script_lines.append(f"    t{i}.LabelString = '{t_label_matlab}';")
            script_lines.append("else")
            script_lines.append(f"    disp(['Warning: Could not create SF transition for ''{src_name_matlab}'' -> ''{dst_name_matlab}''. State missing.']);")
            script_lines.append("end")

        script_lines.extend([
            "% --- Finalize and Save ---",
            "    disp(['Attempting to save Simulink model to: ', outputModelPath]);",
            "    save_system(modelNameVar, outputModelPath, 'OverwriteIfChangedOnDisk', true);",
            "    close_system(modelNameVar, 0);",
            "    disp(['Simulink model saved successfully to: ', outputModelPath]);",
            "    fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', outputModelPath);",
            "catch e",
            "    disp('ERROR during Simulink model generation:');",
            "    disp(getReport(e, 'extended', 'hyperlinks', 'off'));",
            "    if bdIsLoaded(modelNameVar), close_system(modelNameVar, 0); end",
            "    fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', strrep(getReport(e, 'basic'), '\\n', ' '));",
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
        model_dir_matlab = os.path.dirname(model_path_matlab)
        model_name = os.path.splitext(os.path.basename(model_path))[0]

        script_content = f"""
        disp('Starting Simulink simulation...');
        modelPath = '{model_path_matlab}';
        modelName = '{model_name}';
        modelDir = '{model_dir_matlab}';
        currentSimTime = {sim_time};

        try
            prevPath = path; addpath(modelDir);
            disp(['Added to MATLAB path: ', modelDir]);
            load_system(modelPath);
            disp(['Simulating model: ', modelName, ' for ', num2str(currentSimTime), ' seconds.']);
            simOut = sim(modelName, 'StopTime', num2str(currentSimTime));
            disp('Simulink simulation completed successfully.');
            fprintf('MATLAB_SCRIPT_SUCCESS:Simulation of ''%s'' finished at t=%s. Results in MATLAB workspace (simOut).\\n', modelName, num2str(currentSimTime));
        catch e
            disp('ERROR during Simulink simulation:');
            disp(getReport(e, 'extended', 'hyperlinks', 'off'));
            fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', strrep(getReport(e, 'basic'),'\\n',' '));
        end
        if bdIsLoaded(modelName), close_system(modelName, 0); end
        path(prevPath); disp(['Restored MATLAB path. Removed: ', modelDir]);
        """
        self._run_matlab_script(script_content, self.simulationFinished, "Simulation")
        return True

    def generate_code(self, model_path, language="C++", output_dir_base=None):
        if not self.connected:
            self.codeGenerationFinished.emit(False, "MATLAB not connected", "")
            return False

        model_path_matlab = model_path.replace('\\', '/')
        model_dir_matlab = os.path.dirname(model_path_matlab)
        model_name = os.path.splitext(os.path.basename(model_path))[0]

        if not output_dir_base: output_dir_base = os.path.dirname(model_path)
        code_gen_root_matlab = output_dir_base.replace('\\', '/')

        script_content = f"""
        disp('Starting Simulink code generation...');
        modelPath = '{model_path_matlab}';
        modelName = '{model_name}';
        codeGenBaseDir = '{code_gen_root_matlab}';
        modelDir = '{model_dir_matlab}';

        try
            prevPath = path; addpath(modelDir);
            disp(['Added to MATLAB path: ', modelDir]);
            load_system(modelPath);
            if ~(license('test', 'MATLAB_Coder') && license('test', 'Simulink_Coder') && license('test', 'Embedded_Coder'))
                error('Required licenses (MATLAB Coder, Simulink Coder, Embedded Coder) are not available.');
            end
            set_param(modelName,'SystemTargetFile','ert.tlc');
            set_param(modelName,'GenerateMakefile','on');
            cfg = getActiveConfigSet(modelName);
            if strcmpi('{language}', 'C++')
                set_param(cfg, 'TargetLang', 'C++');
                set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'C++ class');
                set_param(cfg.getComponent('Code Generation'),'TargetLangStandard', 'C++11 (ISO)');
                disp('Configured for C++ (class interface, C++11).');
            else % C
                set_param(cfg, 'TargetLang', 'C');
                set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'Reusable function');
                disp('Configured for C (reusable function).');
            end
            set_param(cfg, 'GenerateReport', 'on');
            set_param(cfg, 'GenCodeOnly', 'on');
            set_param(cfg, 'RTWVerbose', 'on');
            if ~exist(codeGenBaseDir, 'dir'), mkdir(codeGenBaseDir); disp(['Created base codegen dir: ', codeGenBaseDir]); end
            disp(['Code generation output base set to: ', codeGenBaseDir]);
            rtwbuild(modelName, 'CodeGenFolder', codeGenBaseDir, 'GenCodeOnly', true);
            disp('Code generation command (rtwbuild) executed.');
            actualCodeDir = fullfile(codeGenBaseDir, [modelName '_ert_rtw']);
            if ~exist(actualCodeDir, 'dir')
                disp(['Warning: Standard codegen subdir ''', actualCodeDir, ''' not found. Output may be directly in base dir.']);
                actualCodeDir = codeGenBaseDir;
            end
            disp(['Simulink code generation successful. Code and report expected in/under: ', actualCodeDir]);
            fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', actualCodeDir);
        catch e
            disp('ERROR during Simulink code generation:');
            disp(getReport(e, 'extended', 'hyperlinks', 'off'));
            fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', strrep(getReport(e, 'basic'),'\\n',' '));
        end
        if bdIsLoaded(modelName), close_system(modelName, 0); end
        path(prevPath);  disp(['Restored MATLAB path. Removed: ', modelDir]);
        """
        self._run_matlab_script(script_content, self.codeGenerationFinished, "Code generation")
        return True

class MatlabCommandWorker(QObject):
    finished_signal = pyqtSignal(bool, str, str) # success, message, data_for_signal

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
            matlab_run_command = f"run('{self.script_file.replace('\\', '/')}')"
            cmd = [self.matlab_path, "-nodisplay", "-batch", matlab_run_command]
            timeout_seconds = 600 # 10 minutes
            process = subprocess.run(
                cmd, capture_output=True, text=True, encoding='utf-8',
                timeout=timeout_seconds, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            stdout_str = process.stdout if process.stdout else ""
            stderr_str = process.stderr if process.stderr else ""

            if "MATLAB_SCRIPT_FAILURE:" in stdout_str:
                success = False
                for line in stdout_str.splitlines():
                    if line.startswith("MATLAB_SCRIPT_FAILURE:"):
                        error_detail = line.split(":", 1)[1].strip()
                        message = f"{self.success_message_prefix} script reported failure: {error_detail}"
                        break
                if not message: message = f"{self.success_message_prefix} script indicated failure. Full stdout:\n{stdout_str[:500]}"
                if stderr_str: message += f"\nStderr:\n{stderr_str[:300]}"
            elif process.returncode == 0:
                if "MATLAB_SCRIPT_SUCCESS:" in stdout_str:
                    success = True
                    for line in stdout_str.splitlines():
                        if line.startswith("MATLAB_SCRIPT_SUCCESS:"):
                            output_data_for_signal = line.split(":", 1)[1].strip()
                            break
                    message = f"{self.success_message_prefix} completed successfully."
                    if output_data_for_signal and self.success_message_prefix != "Simulation":
                         message += f" Data: {output_data_for_signal}"
                    elif output_data_for_signal and self.success_message_prefix == "Simulation":
                        message = output_data_for_signal
                else:
                    success = False
                    message = f"{self.success_message_prefix} script finished (MATLAB exit 0), but success marker not found."
                    message += f"\nStdout:\n{stdout_str[:500]}"
                    if stderr_str: message += f"\nStderr:\n{stderr_str[:300]}"
            else:
                success = False
                error_output = stderr_str or stdout_str
                message = f"{self.success_message_prefix} process failed. MATLAB Exit Code {process.returncode}:\n{error_output[:1000]}"
            self.original_signal.emit(success, message, output_data_for_signal if success else "")
        except subprocess.TimeoutExpired:
            message = f"{self.success_message_prefix} process timed out after {timeout_seconds/60:.1f} minutes."
            self.original_signal.emit(False, message, "")
        except FileNotFoundError:
            message = f"MATLAB executable not found: {self.matlab_path}"
            self.original_signal.emit(False, message, "")
        except Exception as e:
            message = f"Unexpected error in {self.success_message_prefix} worker: {type(e).__name__}: {str(e)}"
            self.original_signal.emit(False, message, "")
        finally:
            if os.path.exists(self.script_file):
                try:
                    os.remove(self.script_file)
                    script_dir = os.path.dirname(self.script_file)
                    if script_dir.startswith(tempfile.gettempdir()) and "bsm_matlab_" in script_dir:
                        if not os.listdir(script_dir): os.rmdir(script_dir)
                        else: print(f"Warning: Temp directory {script_dir} not empty, not removed.")
                except OSError as e:
                    print(f"Warning: Could not clean up temp script/dir '{self.script_file}': {e}")
            self.finished_signal.emit(success, message, output_data_for_signal)

# --- Draggable Toolbox Buttons ---
class DraggableToolButton(QPushButton):
    def __init__(self, text, mime_type, item_type_data, style_sheet, parent=None):
        super().__init__(text, parent)
        self.mime_type = mime_type
        self.item_type_data = item_type_data # e.g., "State", "Initial State"
        self.setText(text)
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(style_sheet + " QPushButton { border-radius: 5px; text-align: left; padding-left: 5px; }")
        self.drag_start_position = QPoint()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.item_type_data) # Use specific type data for drop handler
        mime_data.setData(self.mime_type, self.item_type_data.encode())
        drag.setMimeData(mime_data)

        pixmap_size = QSize(max(120, self.width()), self.height())
        pixmap = QPixmap(pixmap_size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        button_rect = QRectF(0,0, pixmap_size.width()-1, pixmap_size.height()-1)
        current_style = self.styleSheet()
        bg_color = QColor("#B0E0E6") # Default drag pixmap bg
        if "background-color:" in current_style:
            try: bg_color = QColor(current_style.split("background-color:")[1].split(";")[0].strip())
            except: pass
        painter.setBrush(bg_color.lighter(110)) # Lighter for drag
        border_color = QColor("#77AABB")
        if "border:" in current_style:
            try:
                b_parts = current_style.split("border:")[1].split(";")[0].strip().split()
                if len(b_parts) >=3: border_color = QColor(b_parts[2])
            except: pass
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(button_rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5)
        icon_pixmap = self.icon().pixmap(QSize(24,24), QIcon.Normal, QIcon.On)
        text_x_offset = 8; icon_y_offset = (pixmap_size.height() - icon_pixmap.height()) / 2
        if not icon_pixmap.isNull():
            painter.drawPixmap(int(text_x_offset), int(icon_y_offset), icon_pixmap)
            text_x_offset += icon_pixmap.width() + 8
        painter.setPen(self.palette().buttonText().color()) # Use current theme's text color
        painter.setFont(self.font())
        text_rect = QRectF(text_x_offset, 0, pixmap_size.width() - text_x_offset - 5, pixmap_size.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 4, pixmap.height() // 2))
        drag.exec_(Qt.CopyAction | Qt.MoveAction)

# --- Graphics Items ---
class GraphicsStateItem(QGraphicsRectItem):
    Type = QGraphicsItem.UserType + 1
    def type(self): return GraphicsStateItem.Type

    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False,
                 color=None, entry_action="", during_action="", exit_action="", description=""):
        super().__init__(x, y, w, h)
        self.text_label = text
        self.is_initial = is_initial
        self.is_final = is_final
        self.color = QColor(color) if color else QColor(190, 220, 255) # Default light blue
        self.entry_action = entry_action
        self.during_action = during_action
        self.exit_action = exit_action
        self.description = description
        self._text_color = Qt.black
        self._font = QFont("Arial", 10, QFont.Bold)
        self.setPen(QPen(QColor(50, 50, 50), 2))
        self.setBrush(QBrush(self.color))
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self.pen()); painter.setBrush(self.color)
        painter.drawRoundedRect(self.rect(), 10, 10)
        painter.setPen(self._text_color); painter.setFont(self._font)
        painter.drawText(self.rect().adjusted(8, 8, -8, -8), Qt.AlignCenter | Qt.TextWordWrap, self.text_label)
        if self.is_initial:
            painter.setBrush(Qt.black); painter.setPen(QPen(Qt.black, 2))
            marker_radius = 7; line_length = 20
            start_marker_center_x = self.rect().left() - line_length - marker_radius / 2
            start_marker_center_y = self.rect().center().y()
            painter.drawEllipse(QPointF(start_marker_center_x, start_marker_center_y), marker_radius, marker_radius)
            line_start_point = QPointF(start_marker_center_x + marker_radius, start_marker_center_y)
            line_end_point = QPointF(self.rect().left(), start_marker_center_y)
            painter.drawLine(line_start_point, line_end_point)
            arrow_size = 10
            angle_rad = math.atan2(line_end_point.y() - line_start_point.y(), line_end_point.x() - line_start_point.x())
            arrow_p1 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad + math.pi / 6), line_end_point.y() - arrow_size * math.sin(angle_rad + math.pi / 6))
            arrow_p2 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad - math.pi / 6), line_end_point.y() - arrow_size * math.sin(angle_rad - math.pi / 6))
            painter.setBrush(Qt.black)
            painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))
        if self.is_final:
            painter.setPen(QPen(Qt.black, 2))
            painter.drawRoundedRect(self.rect().adjusted(6, 6, -6, -6), 7, 7)
        if self.isSelected():
            pen = QPen(QColor(0, 100, 255, 200), 2.5, Qt.SolidLine)
            painter.setPen(pen); painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.boundingRect().adjusted(-1,-1,1,1), 11, 11)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)

    def get_data(self):
        return { 'name': self.text_label, 'x': self.x(), 'y': self.y(),
            'width': self.rect().width(), 'height': self.rect().height(),
            'is_initial': self.is_initial, 'is_final': self.is_final,
            'color': self.color.name() if self.color else QColor(190, 220, 255).name(),
            'entry_action': self.entry_action, 'during_action': self.during_action,
            'exit_action': self.exit_action, 'description': self.description }

    def set_text(self, text):
        if self.text_label != text:
            self.prepareGeometryChange(); self.text_label = text; self.update()

    def set_properties(self, name, is_initial, is_final, color_hex=None,
                       entry="", during="", exit_a="", desc=""):
        changed = False
        if self.text_label != name: self.text_label = name; changed = True
        if self.is_initial != is_initial: self.is_initial = is_initial; changed = True
        if self.is_final != is_final: self.is_final = is_final; changed = True
        new_color = QColor(color_hex) if color_hex else QColor(190, 220, 255)
        if self.color != new_color: self.color = new_color; self.setBrush(self.color); changed = True
        if self.entry_action != entry: self.entry_action = entry; changed = True
        if self.during_action != during: self.during_action = during; changed = True
        if self.exit_action != exit_a: self.exit_action = exit_a; changed = True
        if self.description != desc: self.description = desc; changed = True
        if changed: self.prepareGeometryChange(); self.update()

class GraphicsTransitionItem(QGraphicsPathItem):
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type

    def __init__(self, start_item, end_item, event_str="", condition_str="", action_str="",
                 color=None, description=""):
        super().__init__()
        self.start_item = start_item; self.end_item = end_item
        self.event_str = event_str; self.condition_str = condition_str; self.action_str = action_str
        self.color = QColor(color) if color else QColor(0, 120, 120)
        self.description = description
        self.arrow_size = 12
        self._text_color = QColor(30, 30, 30)
        self._font = QFont("Arial", 9)
        self.control_point_offset = QPointF(0,0)
        self.setPen(QPen(self.color, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True); self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1); self.setAcceptHoverEvents(True); self.update_path()

    def _compose_label_string(self):
        parts = []
        if self.event_str: parts.append(self.event_str)
        if self.condition_str: parts.append(f"[{self.condition_str}]")
        if self.action_str: parts.append(f"/{{{self.action_str}}}")
        return " ".join(parts)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent): self.setPen(QPen(self.color.lighter(120), 3)); super().hoverEnterEvent(event)
    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent): self.setPen(QPen(self.color, 2.5)); super().hoverLeaveEvent(event)
    def boundingRect(self):
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 25
        path_bounds = self.path().boundingRect()
        current_label = self._compose_label_string()
        if current_label:
            fm = QFontMetrics(self._font); text_rect = fm.boundingRect(current_label)
            mid_point_on_path = self.path().pointAtPercent(0.5)
            text_render_rect = QRectF(mid_point_on_path.x() - text_rect.width() - 10, mid_point_on_path.y() - text_rect.height() - 10, text_rect.width()*2 + 20, text_rect.height()*2 + 20)
            path_bounds = path_bounds.united(text_render_rect)
        return path_bounds.adjusted(-extra, -extra, extra, extra)

    def shape(self):
        path_stroker = QPainterPathStroker(); path_stroker.setWidth(18 + self.pen().widthF())
        path_stroker.setCapStyle(Qt.RoundCap); path_stroker.setJoinStyle(Qt.RoundJoin)
        return path_stroker.createStroke(self.path())

    def update_path(self):
        if not self.start_item or not self.end_item: self.setPath(QPainterPath()); return
        start_center = self.start_item.sceneBoundingRect().center(); end_center = self.end_item.sceneBoundingRect().center()
        start_point = self._get_intersection_point(self.start_item, QLineF(start_center, end_center))
        end_point = self._get_intersection_point(self.end_item, QLineF(end_center, start_center))
        if start_point is None: start_point = start_center
        if end_point is None: end_point = end_center
        path = QPainterPath(start_point)
        if self.start_item == self.end_item:
            rect = self.start_item.sceneBoundingRect()
            loop_radius_x = rect.width() * 0.45; loop_radius_y = rect.height() * 0.45
            p1 = QPointF(rect.center().x() + loop_radius_x * 0.3, rect.top())
            p2 = QPointF(rect.center().x() - loop_radius_x * 0.3, rect.top())
            ctrl1 = QPointF(rect.center().x() + loop_radius_x * 1.5, rect.top() - loop_radius_y * 3.0)
            ctrl2 = QPointF(rect.center().x() - loop_radius_x * 1.5, rect.top() - loop_radius_y * 3.0)
            path.moveTo(p1); path.cubicTo(ctrl1, ctrl2, p2); end_point = p2
        else:
            mid_x = (start_point.x() + end_point.x()) / 2; mid_y = (start_point.y() + end_point.y()) / 2
            dx = end_point.x() - start_point.x(); dy = end_point.y() - start_point.y()
            length = math.hypot(dx, dy)
            if length == 0: length = 1
            perp_x = -dy / length; perp_y = dx / length
            ctrl_pt_x = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y()
            ctrl_pt_y = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()
            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0: path.lineTo(end_point)
            else: path.quadTo(QPointF(ctrl_pt_x, ctrl_pt_y), end_point)
        self.setPath(path); self.prepareGeometryChange()

    def _get_intersection_point(self, item: QGraphicsRectItem, line: QLineF):
        item_rect = item.sceneBoundingRect()
        edges = [ QLineF(item_rect.topLeft(), item_rect.topRight()), QLineF(item_rect.topRight(), item_rect.bottomRight()),
                  QLineF(item_rect.bottomRight(), item_rect.bottomLeft()), QLineF(item_rect.bottomLeft(), item_rect.topLeft()) ]
        intersect_points = []
        for edge in edges:
            intersection_point_var = QPointF(); intersect_type = line.intersect(edge, intersection_point_var)
            if intersect_type == QLineF.BoundedIntersection:
                edge_rect_for_check = QRectF(edge.p1(), edge.p2()).normalized(); epsilon = 1e-3
                if (edge_rect_for_check.left() - epsilon <= intersection_point_var.x() <= edge_rect_for_check.right() + epsilon and
                    edge_rect_for_check.top() - epsilon <= intersection_point_var.y() <= edge_rect_for_check.bottom() + epsilon):
                    intersect_points.append(QPointF(intersection_point_var))
        if not intersect_points: return item_rect.center()
        closest_point = intersect_points[0]; min_dist_sq = (QLineF(line.p1(), closest_point).length())**2
        for pt in intersect_points[1:]:
            dist_sq = (QLineF(line.p1(), pt).length())**2
            if dist_sq < min_dist_sq: min_dist_sq = dist_sq; closest_point = pt
        return closest_point

    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty(): return
        painter.setRenderHint(QPainter.Antialiasing); current_pen = self.pen()
        if self.isSelected():
            stroker = QPainterPathStroker(); stroker.setWidth(current_pen.widthF() + 8); stroker.setCapStyle(Qt.RoundCap); stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path())
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(0,100,255,60)); painter.drawPath(selection_path_shape)
        painter.setPen(current_pen); painter.setBrush(Qt.NoBrush); painter.drawPath(self.path())
        if self.path().elementCount() < 1 : return
        percent_at_end = 0.999;
        if self.path().length() < 1: percent_at_end = 0.9
        line_end_point = self.path().pointAtPercent(1.0); angle_at_end_rad = -self.path().angleAtPercent(percent_at_end) * (math.pi / 180.0)
        arrow_p1 = line_end_point + QPointF(math.cos(angle_at_end_rad - math.pi / 6) * self.arrow_size, math.sin(angle_at_end_rad - math.pi / 6) * self.arrow_size)
        arrow_p2 = line_end_point + QPointF(math.cos(angle_at_end_rad + math.pi / 6) * self.arrow_size, math.sin(angle_at_end_rad + math.pi / 6) * self.arrow_size)
        painter.setBrush(current_pen.color()); painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))
        current_label = self._compose_label_string()
        if current_label:
            painter.setFont(self._font); fm = QFontMetrics(self._font); text_rect_original = fm.boundingRect(current_label)
            text_pos_on_path = self.path().pointAtPercent(0.5); angle_at_mid_deg = self.path().angleAtPercent(0.5)
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0); offset_dist = 12
            text_center_x = text_pos_on_path.x() + offset_dist * math.cos(offset_angle_rad); text_center_y = text_pos_on_path.y() + offset_dist * math.sin(offset_angle_rad)
            text_final_pos = QPointF(text_center_x - text_rect_original.width() / 2, text_center_y - text_rect_original.height() / 2)
            bg_padding = 3; bg_rect = QRectF(text_final_pos.x() - bg_padding, text_final_pos.y() - bg_padding, text_rect_original.width() + 2 * bg_padding, text_rect_original.height() + 2 * bg_padding)
            painter.setBrush(QColor(250, 250, 250, 200)); painter.setPen(QPen(QColor(200,200,200,150), 0.5)); painter.drawRoundedRect(bg_rect, 4, 4)
            painter.setPen(self._text_color); painter.drawText(text_final_pos, current_label)

    def get_data(self):
        return { 'source': self.start_item.text_label if self.start_item else "None",
            'target': self.end_item.text_label if self.end_item else "None",
            'event': self.event_str, 'condition': self.condition_str, 'action': self.action_str,
            'color': self.color.name() if self.color else QColor(0,120,120).name(),
            'description': self.description, 'control_offset_x': self.control_point_offset.x(),
            'control_offset_y': self.control_point_offset.y() }

    def set_properties(self, event_str="", condition_str="", action_str="", color_hex=None, description="", offset=None):
        changed = False
        if self.event_str != event_str: self.event_str = event_str; changed=True
        if self.condition_str != condition_str: self.condition_str = condition_str; changed=True
        if self.action_str != action_str: self.action_str = action_str; changed=True
        if self.description != description: self.description = description; changed=True
        new_color = QColor(color_hex) if color_hex else QColor(0, 120, 120)
        if self.color != new_color: self.color = new_color; self.setPen(QPen(self.color, self.pen().widthF())); changed = True
        if offset is not None and self.control_point_offset != offset: self.control_point_offset = offset; changed = True
        if changed: self.prepareGeometryChange();
                    if offset is not None : self.update_path(); self.update()

    def set_control_point_offset(self, offset: QPointF):
        if self.control_point_offset != offset: self.control_point_offset = offset; self.update_path(); self.update()

class GraphicsCommentItem(QGraphicsTextItem):
    Type = QGraphicsItem.UserType + 3
    def type(self): return GraphicsCommentItem.Type

    def __init__(self, x, y, text="Comment"):
        super().__init__(); self.setPlainText(text); self.setPos(x, y)
        self.setFont(QFont("Arial", 10)); self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self._default_width = 150; self.setTextWidth(self._default_width); self.adjust_size_to_text()
        self.border_pen = QPen(QColor(204, 204, 153), 1.5); self.background_brush = QBrush(QColor(255, 255, 224, 200))

    def paint(self, painter, option, widget):
        painter.setPen(self.border_pen); painter.setBrush(self.background_brush)
        painter.drawRoundedRect(self.boundingRect().adjusted(0.5,0.5,-0.5,-0.5), 5, 5)
        super().paint(painter, option, widget)
        if self.isSelected(): pen = QPen(Qt.blue, 1.5, Qt.DashLine); painter.setPen(pen); painter.setBrush(Qt.NoBrush); painter.drawRect(self.boundingRect())
    def get_data(self): return { 'text': self.toPlainText(), 'x': self.x(), 'y': self.y(), 'width': self.boundingRect().width(), }
    def set_properties(self, text, width=None): self.setPlainText(text);
                                                 if width: self.setTextWidth(width); else: self.adjust_size_to_text(); self.update()
    def adjust_size_to_text(self):
        if abs(self.document().size().height() - self.boundingRect().height()) > 5: self.prepareGeometryChange()
        self.update()
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene(): self.scene().item_moved.emit(self)
        return super().itemChange(change, value)

# --- Undo Commands ---
class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description); self.scene = scene; self.item_instance = item
        if isinstance(item, GraphicsTransitionItem):
            self.item_data = item.get_data()
            self.start_item_name = item.start_item.text_label if item.start_item else None
            self.end_item_name = item.end_item.text_label if item.end_item else None
        elif isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): self.item_data = item.get_data()
    def redo(self):
        if self.item_instance.scene() is None: self.scene.addItem(self.item_instance)
        if isinstance(self.item_instance, GraphicsTransitionItem):
            start_node = self.scene.get_state_by_name(self.start_item_name); end_node = self.scene.get_state_by_name(self.end_item_name)
            if start_node and end_node:
                self.item_instance.start_item = start_node; self.item_instance.end_item = end_node
                self.item_instance.set_properties(event_str=self.item_data['event'], condition_str=self.item_data['condition'], action_str=self.item_data['action'],
                    color_hex=self.item_data.get('color'), description=self.item_data.get('description', ""),
                    offset=QPointF(self.item_data['control_offset_x'], self.item_data['control_offset_y']))
                self.item_instance.update_path()
            else: self.scene.log_function(f"Error (Redo Add Transition): States missing for '{self.item_data.get('event', '')}'.")
        self.scene.clearSelection(); self.item_instance.setSelected(True); self.scene.set_dirty(True)
    def undo(self): self.scene.removeItem(self.item_instance); self.scene.set_dirty(True)

class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items_to_remove, description="Remove Items"):
        super().__init__(description); self.scene = scene; self.removed_items_data = []
        self.item_instances_for_quick_toggle = list(items_to_remove)
        for item in items_to_remove:
            item_data_entry = item.get_data(); item_data_entry['_type'] = item.type()
            if isinstance(item, GraphicsTransitionItem):
                 item_data_entry['_start_name'] = item.start_item.text_label if item.start_item else None
                 item_data_entry['_end_name'] = item.end_item.text_label if item.end_item else None
            self.removed_items_data.append(item_data_entry)
    def redo(self):
        for item_instance in self.item_instances_for_quick_toggle:
            if item_instance.scene() == self.scene: self.scene.removeItem(item_instance)
        self.scene.set_dirty(True)
    def undo(self):
        newly_re_added_instances = []; states_map_for_undo = {}
        for item_data in self.removed_items_data: # Restore states and comments first
            instance_to_add = None
            if item_data['_type'] == GraphicsStateItem.Type:
                state = GraphicsStateItem(item_data['x'], item_data['y'], item_data['width'], item_data['height'], item_data['name'], item_data['is_initial'],
                    item_data['is_final'], item_data.get('color'), item_data.get('entry_action', ""), item_data.get('during_action', ""), item_data.get('exit_action', ""), item_data.get('description', ""))
                instance_to_add = state; states_map_for_undo[state.text_label] = state
            elif item_data['_type'] == GraphicsCommentItem.Type:
                comment = GraphicsCommentItem(item_data['x'], item_data['y'], item_data['text']); comment.setTextWidth(item_data.get('width', 150)); instance_to_add = comment
            if instance_to_add: self.scene.addItem(instance_to_add); newly_re_added_instances.append(instance_to_add)
        for item_data in self.removed_items_data: # Restore transitions
            if item_data['_type'] == GraphicsTransitionItem.Type:
                src_item = states_map_for_undo.get(item_data['_start_name']); tgt_item = states_map_for_undo.get(item_data['_end_name'])
                if src_item and tgt_item:
                    trans = GraphicsTransitionItem(src_item, tgt_item, event_str=item_data['event'], condition_str=item_data['condition'], action_str=item_data['action'],
                                                   color=item_data.get('color'), description=item_data.get('description',""))
                    trans.set_control_point_offset(QPointF(item_data['control_offset_x'], item_data['control_offset_y']))
                    self.scene.addItem(trans); newly_re_added_instances.append(trans)
                else: self.scene.log_function(f"Error (Undo Remove): States missing for transition '{item_data.get('event','')}'.")
        self.item_instances_for_quick_toggle = newly_re_added_instances; self.scene.set_dirty(True)

class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_and_new_positions, description="Move Items"):
        super().__init__(description); self.items_and_new_positions = items_and_new_positions; self.items_and_old_positions = []; self.scene_ref = None
        if self.items_and_new_positions:
            self.scene_ref = self.items_and_new_positions[0][0].scene()
            for item, _ in self.items_and_new_positions: self.items_and_old_positions.append((item, item.pos()))
    def _apply_positions(self, positions_list):
        if not self.scene_ref: return
        for item, pos in positions_list:
            item.setPos(pos)
            if isinstance(item, GraphicsStateItem): self.scene_ref._update_connected_transitions(item)
        self.scene_ref.update(); self.scene_ref.set_dirty(True)
    def redo(self): self._apply_positions(self.items_and_new_positions)
    def undo(self): self._apply_positions(self.items_and_old_positions)

class EditItemPropertiesCommand(QUndoCommand):
    def __init__(self, item, old_props_data, new_props_data, description="Edit Properties"):
        super().__init__(description); self.item = item; self.old_props_data = old_props_data; self.new_props_data = new_props_data; self.scene_ref = item.scene()
    def _apply_properties(self, props_to_apply):
        if not self.item or not self.scene_ref: return
        original_name_if_state = None
        if isinstance(self.item, GraphicsStateItem):
            original_name_if_state = self.item.text_label
            self.item.set_properties(props_to_apply['name'], props_to_apply.get('is_initial', False), props_to_apply.get('is_final', False),
                props_to_apply.get('color'), props_to_apply.get('entry_action', ""), props_to_apply.get('during_action', ""),
                props_to_apply.get('exit_action', ""), props_to_apply.get('description', ""))
            if original_name_if_state != props_to_apply['name']: self.scene_ref._update_transitions_for_renamed_state(original_name_if_state, props_to_apply['name'])
        elif isinstance(self.item, GraphicsTransitionItem):
            self.item.set_properties(event_str=props_to_apply.get('event',""), condition_str=props_to_apply.get('condition',""),
                action_str=props_to_apply.get('action',""), color_hex=props_to_apply.get('color'), description=props_to_apply.get('description',""),
                offset=QPointF(props_to_apply['control_offset_x'], props_to_apply['control_offset_y']))
        elif isinstance(self.item, GraphicsCommentItem): self.item.set_properties(text=props_to_apply['text'], width=props_to_apply.get('width'))
        self.item.update(); self.scene_ref.update(); self.scene_ref.set_dirty(True)
    def redo(self): self._apply_properties(self.new_props_data)
    def undo(self): self._apply_properties(self.old_props_data)

# --- Diagram Scene ---
class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool)
    def __init__(self, undo_stack, parent_window=None):
        super().__init__(parent_window); self.parent_window = parent_window; self.setSceneRect(0, 0, 5000, 4000); self.current_mode = "select"
        self.transition_start_item = None; self.log_function = print; self.undo_stack = undo_stack; self._dirty = False
        self._mouse_press_items_positions = {}; self._temp_transition_line = None; self.item_moved.connect(self._handle_item_moved)
        self.grid_size = 20; self.grid_pen_light = QPen(QColor(225, 225, 225), 0.8, Qt.SolidLine)
        self.grid_pen_dark = QPen(QColor(200, 200, 200), 1.0, Qt.SolidLine); self.setBackgroundBrush(QColor(248, 248, 248)); self.snap_to_grid_enabled = True

    def _update_connected_transitions(self, state_item: GraphicsStateItem):
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem) and (item.start_item == state_item or item.end_item == state_item): item.update_path()
    def _update_transitions_for_renamed_state(self, old_name:str, new_name:str): self.log_function(f"State '{old_name}' renamed to '{new_name}'.")
    def get_state_by_name(self, name: str):
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name: return item
        return None
    def set_dirty(self, dirty=True):
        if self._dirty != dirty: self._dirty = dirty; self.modifiedStatusChanged.emit(dirty)
                                  if self.parent_window: self.parent_window._update_save_actions_enable_state()
    def is_dirty(self): return self._dirty
    def set_log_function(self, log_function): self.log_function = log_function
    def set_mode(self, mode: str):
        old_mode = self.current_mode;
        if old_mode == mode: return
        self.current_mode = mode; self.log_function(f"Mode: {mode}")
        self.transition_start_item = None
        if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
        cursor_map = {"select": Qt.ArrowCursor, "state": Qt.CrossCursor, "comment": Qt.CrossCursor, "transition": Qt.PointingHandCursor}
        QApplication.setOverrideCursor(cursor_map.get(mode, Qt.ArrowCursor))
        movable = (mode == "select")
        for item in self.items():
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): item.setFlag(QGraphicsItem.ItemIsMovable, movable)
        if old_mode in ["state", "transition", "comment"] and mode not in ["state", "transition", "comment"]: QApplication.restoreOverrideCursor()
        if self.parent_window:
            action_map = {"select": self.parent_window.select_mode_action, "state": self.parent_window.add_state_mode_action,
                          "transition": self.parent_window.add_transition_mode_action, "comment": self.parent_window.add_comment_mode_action}
            if mode in action_map and not action_map[mode].isChecked(): action_map[mode].setChecked(True)

    def select_all(self):
        for item in self.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable: item.setSelected(True)
    def _handle_item_moved(self, moved_item):
        if isinstance(moved_item, GraphicsStateItem): self._update_connected_transitions(moved_item)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos(); items_at_pos = self.items(pos)
        top_item = next((it for it in items_at_pos if isinstance(it, GraphicsStateItem)), None)
        if not top_item: top_item = next((it for it in items_at_pos if isinstance(it, (GraphicsCommentItem, GraphicsTransitionItem))), None)
        if not top_item and items_at_pos: top_item = items_at_pos[0]

        if event.button() == Qt.LeftButton:
            if self.current_mode == "state": self._add_item_interactive(pos, item_type="State")
            elif self.current_mode == "comment": self._add_item_interactive(pos, item_type="Comment")
            elif self.current_mode == "transition":
                if isinstance(top_item, GraphicsStateItem): self._handle_transition_click(top_item, pos)
                else: self.transition_start_item = None;
                      if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
            else: # Select mode
                self._mouse_press_items_positions.clear()
                for item in [it for it in self.selectedItems() if it.flags() & QGraphicsItem.ItemIsMovable]: self._mouse_press_items_positions[item] = item.pos()
                super().mousePressEvent(event)
        elif event.button() == Qt.RightButton:
            if top_item and isinstance(top_item, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem)):
                if not top_item.isSelected(): self.clearSelection(); top_item.setSelected(True)
                self._show_context_menu(top_item, event.screenPos())
            else: self.clearSelection()
        else: super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            self._temp_transition_line.setLine(QLineF(self.transition_start_item.sceneBoundingRect().center(), event.scenePos()))
        else: super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton and self.current_mode == "select" and self._mouse_press_items_positions:
            moved_data = []
            for item, old_pos in self._mouse_press_items_positions.items():
                new_pos = item.pos()
                if self.snap_to_grid_enabled:
                    snapped_x = round(new_pos.x() / self.grid_size) * self.grid_size; snapped_y = round(new_pos.y() / self.grid_size) * self.grid_size
                    if new_pos.x() != snapped_x or new_pos.y() != snapped_y: item.setPos(snapped_x, snapped_y); new_pos = QPointF(snapped_x, snapped_y)
                if (new_pos - old_pos).manhattanLength() > 0.1: moved_data.append((item, new_pos))
            if moved_data: self.undo_stack.push(MoveItemsCommand(moved_data))
            self._mouse_press_items_positions.clear()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        item = next((it for it in self.items(event.scenePos()) if isinstance(it, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem))), None)
        if item: self.edit_item_properties(item)
        else: super().mouseDoubleClickEvent(event)
    def _show_context_menu(self, item, global_pos):
        menu = QMenu(); menu.setStyleSheet("QMenu { background-color: #FAFAFA; border: 1px solid #D0D0D0; } QMenu::item { padding: 5px 20px; } QMenu::item:selected { background-color: #E0E0E0; }")
        edit_act = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        del_act = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")
        chosen_act = menu.exec_(global_pos)
        if chosen_act == edit_act: self.edit_item_properties(item)
        elif chosen_act == del_act:
            if not item.isSelected(): self.clearSelection(); item.setSelected(True)
            self.delete_selected_items()
    def edit_item_properties(self, item):
        old_props = item.get_data(); new_props = None
        if isinstance(item, GraphicsStateItem):
            dialog = StatePropertiesDialog(parent=self.parent_window, current_properties=old_props)
            if dialog.exec_() == QDialog.Accepted: new_props = dialog.get_properties()
        elif isinstance(item, GraphicsTransitionItem):
            dialog = TransitionPropertiesDialog(parent=self.parent_window, current_properties=old_props)
            if dialog.exec_() == QDialog.Accepted: new_props = dialog.get_properties()
        elif isinstance(item, GraphicsCommentItem):
            dialog = CommentPropertiesDialog(parent=self.parent_window, current_properties=old_props)
            if dialog.exec_() == QDialog.Accepted: new_props = dialog.get_properties()
        else: return

        if new_props is not None:
            if isinstance(item, GraphicsStateItem) and new_props['name'] != old_props['name'] and self.get_state_by_name(new_props['name']):
                QMessageBox.warning(self.parent_window, "Duplicate Name", f"State '{new_props['name']}' exists."); return
            final_new_props = old_props.copy(); final_new_props.update(new_props)
            self.undo_stack.push(EditItemPropertiesCommand(item, old_props, final_new_props, f"Edit {type(item).__name__}"))
            name_for_log = final_new_props.get('name', final_new_props.get('event', final_new_props.get('text', 'Item')))
            self.log_function(f"Properties updated for: {name_for_log}")
        self.update() # Ensures scene redraws with updated item

    def _add_item_interactive(self, pos: QPointF, item_type: str, name_prefix:str="Item", initial_data:dict=None):
        current_item = None
        if item_type == "State":
            i = 1; base_name = name_prefix
            while self.get_state_by_name(f"{base_name}{i}"): i += 1
            dialog_props = {'name': f"{base_name}{i}", 'is_initial': (initial_data.get('is_initial', False) if initial_data else False),
                            'is_final': (initial_data.get('is_final', False) if initial_data else False)}
            if initial_data and 'color' in initial_data: dialog_props['color'] = initial_data['color']
            props_dialog = StatePropertiesDialog(self.parent_window, current_properties=dialog_props, is_new_state=True)
            if props_dialog.exec_() == QDialog.Accepted:
                final_props = props_dialog.get_properties()
                if self.get_state_by_name(final_props['name']): QMessageBox.warning(self.parent_window, "Duplicate Name", f"State '{final_props['name']}' exists."); return
                current_item = GraphicsStateItem(pos.x(), pos.y(), 120, 60, final_props['name'], final_props['is_initial'], final_props['is_final'],
                    final_props.get('color'), final_props.get('entry_action',""), final_props.get('during_action',""), final_props.get('exit_action',""), final_props.get('description',""))
            else:
                if self.current_mode == "state": self.set_mode("select"); return
        elif item_type == "Comment":
            text, ok = QInputDialog.getMultiLineText(self.parent_window, "New Comment", "Text:", (initial_data.get('text',"Comment") if initial_data else name_prefix))
            if ok and text: current_item = GraphicsCommentItem(pos.x(), pos.y(), text)
            else:
                if self.current_mode == "comment": self.set_mode("select"); return
        else: self.log_function(f"Unknown item type for addition: {item_type}"); return

        if current_item:
            self.undo_stack.push(AddItemCommand(self, current_item, f"Add {item_type}"))
            name = current_item.text_label if hasattr(current_item,'text_label') else current_item.toPlainText()
            self.log_function(f"Added {item_type}: {name} at ({pos.x():.0f},{pos.y():.0f})")
        if self.current_mode in ["state", "comment"] and item_type != "TransitionTool": self.set_mode("select")

    def _handle_transition_click(self, clicked_state_item: GraphicsStateItem, click_pos: QPointF):
        if not self.transition_start_item:
            self.transition_start_item = clicked_state_item
            if not self._temp_transition_line:
                self._temp_transition_line = QGraphicsLineItem(); self._temp_transition_line.setPen(QPen(Qt.black, 2, Qt.DashLine)); self.addItem(self._temp_transition_line)
            self._temp_transition_line.setLine(QLineF(self.transition_start_item.sceneBoundingRect().center(), click_pos))
            self.log_function(f"Transition from: {clicked_state_item.text_label}. Click target.")
        else:
            if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
            props_dialog = TransitionPropertiesDialog(self.parent_window, current_properties={'event': "", 'condition': "", 'action': ""}, is_new_transition=True)
            if props_dialog.exec_() == QDialog.Accepted:
                props = props_dialog.get_properties()
                new_trans = GraphicsTransitionItem(self.transition_start_item, clicked_state_item, event_str=props['event'], condition_str=props['condition'],
                    action_str=props['action'], color=props.get('color'), description=props.get('description',""))
                new_trans.set_control_point_offset(QPointF(props['control_offset_x'],props['control_offset_y']))
                self.undo_stack.push(AddItemCommand(self, new_trans, "Add Transition"))
                self.log_function(f"Transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{new_trans._compose_label_string()}]")
            else: self.log_function("Transition cancelled.")
            self.transition_start_item = None; self.set_mode("select")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in [Qt.Key_Delete, Qt.Key_Backspace] and self.selectedItems(): self.delete_selected_items()
        elif event.key() == Qt.Key_Escape:
            if self.current_mode == "transition" and self.transition_start_item:
                self.transition_start_item = None;
                if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
                self.log_function("Transition cancelled by Esc."); self.set_mode("select")
            elif self.current_mode != "select": self.set_mode("select")
            else: self.clearSelection()
        else: super().keyPressEvent(event)
    def delete_selected_items(self):
        selected = self.selectedItems()
        if not selected: return
        to_delete = set(selected)
        for item in selected:
            if isinstance(item, GraphicsStateItem):
                for scene_item in self.items():
                    if isinstance(scene_item, GraphicsTransitionItem) and (scene_item.start_item == item or scene_item.end_item == item): to_delete.add(scene_item)
        if to_delete: self.undo_stack.push(RemoveItemsCommand(self, list(to_delete), "Delete Items")); self.log_function(f"Queued deletion of {len(to_delete)} item(s)."); self.clearSelection()
    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"): event.acceptProposedAction()
        else: super().dragEnterEvent(event)
    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"): event.acceptProposedAction()
        else: super().dragMoveEvent(event)
    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        pos = event.scenePos()
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            item_type_str = event.mimeData().text()
            grid_x = round(pos.x() / self.grid_size) * self.grid_size; grid_y = round(pos.y() / self.grid_size) * self.grid_size
            if "State" in item_type_str: grid_x -= 60; grid_y -= 30 # Adjust for typical center
            
            init_props = {}; add_type = "Item"; name_prefix = "Item"
            if item_type_str == "State": add_type = "State"; name_prefix = "State"
            elif item_type_str == "Initial State": add_type = "State"; name_prefix = "Initial"; init_props['is_initial'] = True
            elif item_type_str == "Final State": add_type = "State"; name_prefix = "Final"; init_props['is_final'] = True
            elif item_type_str == "Comment": add_type = "Comment"; name_prefix = "Note"
            elif item_type_str == "Transition": # Handling dragged transition tool
                self.log_function("Transition tool dropped: Activating Add Transition mode.")
                self.set_mode("transition") # Switch to transition drawing mode
                event.acceptProposedAction(); return # Done for this drop type
            else: self.log_function(f"Unknown item type dropped: {item_type_str}"); event.ignore(); return
            self._add_item_interactive(QPointF(grid_x, grid_y), add_type, name_prefix, init_props)
            event.acceptProposedAction()
        else: super().dropEvent(event)

    def get_diagram_data(self):
        data = {'states': [], 'transitions': [], 'comments': []}
        for item in self.items():
            if isinstance(item, GraphicsStateItem): data['states'].append(item.get_data())
            elif isinstance(item, GraphicsTransitionItem):
                if item.start_item and item.end_item: data['transitions'].append(item.get_data())
                else: self.log_function(f"Warning: Skipping save of orphaned transition: '{item._compose_label_string()}'.")
            elif isinstance(item, GraphicsCommentItem): data['comments'].append(item.get_data())
        return data
    def load_diagram_data(self, data):
        self.clear(); self.set_dirty(False); state_map = {}
        for s_data in data.get('states', []):
            item = GraphicsStateItem(s_data['x'], s_data['y'], s_data.get('width',120), s_data.get('height',60), s_data['name'],
                s_data.get('is_initial',False), s_data.get('is_final',False), s_data.get('color'), s_data.get('entry_action',""),
                s_data.get('during_action',""), s_data.get('exit_action',""), s_data.get('description',""))
            self.addItem(item); state_map[s_data['name']] = item
        for t_data in data.get('transitions', []):
            src = state_map.get(t_data['source']); tgt = state_map.get(t_data['target'])
            if src and tgt:
                item = GraphicsTransitionItem(src, tgt, event_str=t_data.get('event',""), condition_str=t_data.get('condition',""),
                    action_str=t_data.get('action',""), color=t_data.get('color'), description=t_data.get('description',""))
                item.set_control_point_offset(QPointF(t_data.get('control_offset_x',0),t_data.get('control_offset_y',0)))
                self.addItem(item)
            else: self.log_function(f"Warning (Load): Missing states for transition '{t_data.get('event','N/A')}'.")
        for c_data in data.get('comments', []):
            item = GraphicsCommentItem(c_data['x'], c_data['y'], c_data.get('text',"")); item.setTextWidth(c_data.get('width',150)); self.addItem(item)
        self.set_dirty(False); self.undo_stack.clear()
    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        view_rect = self.views()[0].viewport().rect() if self.views() else rect
        vis_rect = self.views()[0].mapToScene(view_rect).boundingRect() if self.views() else rect
        left=int(vis_rect.left()); right=int(vis_rect.right()); top=int(vis_rect.top()); bottom=int(vis_rect.bottom())
        first_left = left - (left % self.grid_size); first_top = top - (top % self.grid_size)
        painter.setPen(self.grid_pen_light)
        for x in range(first_left, right, self.grid_size):
            if x % (self.grid_size * 5) != 0: painter.drawLine(x, top, x, bottom)
        for y in range(first_top, bottom, self.grid_size):
            if y % (self.grid_size * 5) != 0: painter.drawLine(left, y, right, y)
        major_grid_size = self.grid_size * 5; first_major_left = left - (left % major_grid_size); first_major_top = top - (top % major_grid_size)
        painter.setPen(self.grid_pen_dark)
        for x in range(first_major_left, right, major_grid_size): painter.drawLine(x, top, x, bottom)
        for y in range(first_major_top, bottom, major_grid_size): painter.drawLine(left, y, right, y)

# --- Zoomable Graphics View ---
class ZoomableView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent); self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag); self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate); self.zoom_level = 0
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._is_panning_with_space = False; self._is_panning_with_mouse_button = False; self._last_pan_point = QPoint()
    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y(); factor = 1.12 if delta > 0 else 1 / 1.12
            new_zoom = self.zoom_level + (1 if delta > 0 else -1)
            if -15 <= new_zoom <= 25: self.scale(factor, factor); self.zoom_level = new_zoom
            event.accept()
        else: super().wheelEvent(event)
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = True; self._last_pan_point = event.pos(); self.setCursor(Qt.OpenHandCursor); event.accept()
        elif event.key() in [Qt.Key_Plus, Qt.Key_Equal]: self.scale(1.12,1.12); self.zoom_level+=1
        elif event.key() == Qt.Key_Minus: self.scale(1/1.12,1/1.12); self.zoom_level-=1
        elif event.key() in [Qt.Key_0, Qt.Key_Asterisk]: self.resetTransform(); self.zoom_level=0
        else: super().keyPressEvent(event)
    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = False;
            if not self._is_panning_with_mouse_button: self._restore_cursor_to_scene_mode()
            event.accept()
        else: super().keyReleaseEvent(event)
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton or (self._is_panning_with_space and event.button() == Qt.LeftButton):
            self._last_pan_point = event.pos(); self.setCursor(Qt.ClosedHandCursor); self._is_panning_with_mouse_button = True; event.accept()
        else: self._is_panning_with_mouse_button = False; super().mousePressEvent(event)
    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button:
            delta = event.pos() - self._last_pan_point; self._last_pan_point = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y()); event.accept()
        else: super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button and (event.button() == Qt.MiddleButton or (self._is_panning_with_space and event.button() == Qt.LeftButton)):
            self._is_panning_with_mouse_button = False;
            if self._is_panning_with_space: self.setCursor(Qt.OpenHandCursor)
            else: self._restore_cursor_to_scene_mode()
            event.accept()
        else: super().mouseReleaseEvent(event)
    def _restore_cursor_to_scene_mode(self):
        mode = self.scene().current_mode if self.scene() else "select"
        cursors = {"select": Qt.ArrowCursor, "state": Qt.CrossCursor, "comment": Qt.CrossCursor, "transition": Qt.PointingHandCursor}
        self.setCursor(cursors.get(mode, Qt.ArrowCursor))

# --- Dialogs ---
class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False):
        super().__init__(parent); self.setWindowTitle("State Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Props"))
        layout = QFormLayout(self); layout.setSpacing(10); p = current_properties or {}
        self.name_edit = QLineEdit(p.get('name', "State")); self.name_edit.setPlaceholderText("Unique state name")
        self.is_initial_cb = QCheckBox("Initial State"); self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Final State"); self.is_final_cb.setChecked(p.get('is_final', False))
        self.color_button = QPushButton("Color..."); self.current_color = QColor(p.get('color', "#BEDFFF")); self._update_color_button_style(); self.color_button.clicked.connect(self._choose_color)
        self.entry_action_edit = QTextEdit(p.get('entry_action',"")); self.entry_action_edit.setFixedHeight(60); self.entry_action_edit.setPlaceholderText("MATLAB: e.g., set_pin_high(LED_PIN); init_timer(TIMER_A, 100);")
        self.during_action_edit = QTextEdit(p.get('during_action',"")); self.during_action_edit.setFixedHeight(60); self.during_action_edit.setPlaceholderText("MATLAB: e.g., motor_speed = read_encoder(); current_mA = read_adc(SHUNT_PIN)*SCALE_FACTOR;")
        self.exit_action_edit = QTextEdit(p.get('exit_action',"")); self.exit_action_edit.setFixedHeight(60); self.exit_action_edit.setPlaceholderText("MATLAB: e.g., set_pin_low(MOTOR_ENABLE); disable_interrupts();")
        self.description_edit = QTextEdit(p.get('description',"")); self.description_edit.setFixedHeight(80); self.description_edit.setPlaceholderText("Optional state description")
        layout.addRow("Name:", self.name_edit); layout.addRow(self.is_initial_cb); layout.addRow(self.is_final_cb); layout.addRow("Color:", self.color_button)
        layout.addRow("Entry Action:", self.entry_action_edit); layout.addRow("During Action:", self.during_action_edit); layout.addRow("Exit Action:", self.exit_action_edit); layout.addRow("Description:", self.description_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addRow(buttons)
        self.setMinimumWidth(400)
        if is_new_state: self.name_edit.selectAll(); self.name_edit.setFocus()
    def _choose_color(self): color = QColorDialog.getColor(self.current_color, self, "Select State Color");
                          if color.isValid(): self.current_color = color; self._update_color_button_style()
    def _update_color_button_style(self): self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {'black' if self.current_color.lightnessF() > 0.5 else 'white'};")
    def get_properties(self):
        return {'name':self.name_edit.text().strip(), 'is_initial':self.is_initial_cb.isChecked(), 'is_final':self.is_final_cb.isChecked(), 'color':self.current_color.name(),
                'entry_action':self.entry_action_edit.toPlainText().strip(), 'during_action':self.during_action_edit.toPlainText().strip(),
                'exit_action':self.exit_action_edit.toPlainText().strip(), 'description':self.description_edit.toPlainText().strip()}

class TransitionPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent); self.setWindowTitle("Transition Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Props"))
        layout = QFormLayout(self); layout.setSpacing(10); p = current_properties or {}
        self.event_edit = QLineEdit(p.get('event',"")); self.event_edit.setPlaceholderText("e.g., button_A_pressed, ObstacleDetected, RX_data_ready")
        self.condition_edit = QLineEdit(p.get('condition',"")); self.condition_edit.setPlaceholderText("e.g., sensor_value > THRESHOLD && is_safe_to_move")
        self.action_edit = QTextEdit(p.get('action',"")); self.action_edit.setFixedHeight(60); self.action_edit.setPlaceholderText("MATLAB: e.g., update_display(); send_can_msg(0x101, [duty_cycle, 0]);")
        self.color_button = QPushButton("Color..."); self.current_color = QColor(p.get('color', "#007878")); self._update_color_button_style(); self.color_button.clicked.connect(self._choose_color)
        self.offset_perp_spin = QSpinBox(); self.offset_perp_spin.setRange(-800,800); self.offset_perp_spin.setSingleStep(10); self.offset_perp_spin.setValue(int(p.get('control_offset_x',0))); self.offset_perp_spin.setToolTip("Perpendicular curve bend")
        self.offset_tang_spin = QSpinBox(); self.offset_tang_spin.setRange(-800,800); self.offset_tang_spin.setSingleStep(10); self.offset_tang_spin.setValue(int(p.get('control_offset_y',0))); self.offset_tang_spin.setToolTip("Tangential curve midpoint shift")
        self.description_edit = QTextEdit(p.get('description',"")); self.description_edit.setFixedHeight(80); self.description_edit.setPlaceholderText("Optional transition description")
        layout.addRow("Event Trigger:", self.event_edit); layout.addRow("Condition (Guard):", self.condition_edit); layout.addRow("Transition Action:", self.action_edit); layout.addRow("Color:", self.color_button)
        layout.addRow("Curve Bend:", self.offset_perp_spin); layout.addRow("Curve Midpoint Shift:", self.offset_tang_spin); layout.addRow("Description:", self.description_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addRow(buttons)
        self.setMinimumWidth(450)
        if is_new_transition: self.event_edit.setFocus()
    def _choose_color(self): color = QColorDialog.getColor(self.current_color, self, "Select Transition Color");
                          if color.isValid(): self.current_color = color; self._update_color_button_style()
    def _update_color_button_style(self): self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {'black' if self.current_color.lightnessF() > 0.5 else 'white'};")
    def get_properties(self):
        return {'event':self.event_edit.text().strip(), 'condition':self.condition_edit.text().strip(), 'action':self.action_edit.toPlainText().strip(),
                'color':self.current_color.name(), 'control_offset_x':self.offset_perp_spin.value(), 'control_offset_y':self.offset_tang_spin.value(), 'description':self.description_edit.toPlainText().strip()}

class CommentPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent); self.setWindowTitle("Comment Properties"); p = current_properties or {}
        layout = QVBoxLayout(self); self.text_edit = QTextEdit(p.get('text',"Comment")); self.text_edit.setMinimumHeight(100); self.text_edit.setPlaceholderText("Enter comment text")
        layout.addWidget(QLabel("Comment Text:")); layout.addWidget(self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.setMinimumWidth(350); self.text_edit.setFocus(); self.text_edit.selectAll()
    def get_properties(self): return {'text':self.text_edit.toPlainText()}

class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection, parent=None):
        super().__init__(parent); self.matlab_connection = matlab_connection; self.setWindowTitle("MATLAB Settings"); self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg")); self.setMinimumWidth(550)
        main_layout = QVBoxLayout(self); path_group = QGroupBox("MATLAB Executable Path"); path_form = QFormLayout(); self.path_edit = QLineEdit(self.matlab_connection.matlab_path); self.path_edit.setPlaceholderText("e.g., C:\\...\\matlab.exe")
        path_form.addRow("Path:", self.path_edit); btn_layout = QHBoxLayout(); auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_FileDialogContentsView, "Det"), "Auto-detect"); auto_detect_btn.clicked.connect(self._auto_detect)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), "Browse..."); browse_btn.clicked.connect(self._browse); btn_layout.addWidget(auto_detect_btn); btn_layout.addWidget(browse_btn); btn_layout.addStretch()
        path_v_layout = QVBoxLayout(); path_v_layout.addLayout(path_form); path_v_layout.addLayout(btn_layout); path_group.setLayout(path_v_layout); main_layout.addWidget(path_group)
        test_group = QGroupBox("Connection Test"); test_layout = QVBoxLayout(); self.test_status_label = QLabel("Status: Unknown"); self.test_status_label.setWordWrap(True); self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        test_btn = QPushButton(get_standard_icon(QStyle.SP_CommandLink, "Test"), "Test Connection"); test_btn.clicked.connect(self._test_conn); test_layout.addWidget(test_btn); test_layout.addWidget(self.test_status_label)
        test_group.setLayout(test_layout); main_layout.addWidget(test_group); dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close")
        dialog_buttons.accepted.connect(self._apply); dialog_buttons.rejected.connect(self.reject); main_layout.addWidget(dialog_buttons); self.matlab_connection.connectionStatusChanged.connect(self._update_status_label)
        self._update_status_label(self.matlab_connection.connected, f"Path: {self.matlab_connection.matlab_path if self.matlab_connection.matlab_path else 'Not set'}")
    def _auto_detect(self): self._update_status_label(False, "Auto-detecting..."); QApplication.processEvents(); self.matlab_connection.detect_matlab()
    def _browse(self): path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB", os.path.dirname(self.path_edit.text()) if self.path_edit.text() else QDir.homePath(), "MATLAB (matlab.exe matlab)" if sys.platform=='win32' else "MATLAB (matlab);;All Files (*)");
                     if path: self.path_edit.setText(path); self._update_status_label(False, "Path changed. Test or Apply.")
    def _test_conn(self): path = self.path_edit.text().strip();
                       if not path: self._update_status_label(False, "Path empty."); return; self._update_status_label(False, "Testing..."); QApplication.processEvents()
                       if self.matlab_connection.set_matlab_path(path): self.matlab_connection.test_connection()
    def _update_status_label(self, success, message): self.test_status_label.setText(f"Status: {message}"); self.test_status_label.setStyleSheet(f"color: {'#006400' if success else '#B22222'}; font-weight: bold;")
                                                    if success and self.matlab_connection.matlab_path: self.path_edit.setText(self.matlab_connection.matlab_path)
    def _apply(self): self.matlab_connection.set_matlab_path(self.path_edit.text().strip()); self.accept()

# New Dialog for Chart Data Item properties
class ChartDataItemDialog(QDialog):
    def __init__(self, parent=None, current_data=None, existing_names=None, default_scope="Input"):
        super().__init__(parent)
        self.setWindowTitle("Chart Data Item Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "IO"))
        self.existing_names = existing_names or [] # All names currently in chart_io_data
        self.is_edit_mode = current_data is not None
        self.original_name = current_data.get('name') if self.is_edit_mode else None # Store original name for uniqueness check

        p = current_data or {}

        layout = QFormLayout(self)
        layout.setSpacing(10)

        self.name_edit = QLineEdit(p.get('name', "newDataItem"))
        self.name_edit.setPlaceholderText("Unique C-style variable name")
        layout.addRow("Name:", self.name_edit)

        self.scope_combo = QComboBox()
        self.scope_combo.addItems(CHART_DATA_SCOPES)
        self.scope_combo.setCurrentText(p.get('scope', default_scope))
        layout.addRow("Scope:", self.scope_combo)

        self.type_combo = QComboBox()
        self.type_combo.addItems(CHART_DATA_TYPES)
        self.type_combo.setCurrentText(p.get('datatype', "double"))
        layout.addRow("Data Type:", self.type_combo)

        self.initial_value_edit = QLineEdit(p.get('initial_value', ""))
        self.initial_value_label = QLabel("Initial Value:") # Separate label for hide/show
        layout.addRow(self.initial_value_label, self.initial_value_edit)

        self.description_edit = QTextEdit(p.get('description', ""))
        self.description_edit.setFixedHeight(60)
        self.description_edit.setPlaceholderText("Optional description of this data item.")
        layout.addRow("Description:", self.description_edit)

        self.scope_combo.currentTextChanged.connect(self._update_initial_value_visibility)
        self._update_initial_value_visibility(self.scope_combo.currentText()) # Initial setup

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.on_accept) # Use custom accept handler for validation
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setMinimumWidth(380)
        self.name_edit.setFocus()
        if not self.is_edit_mode : self.name_edit.selectAll()


    def _update_initial_value_visibility(self, scope_text):
        # Initial value is relevant for Local, Parameter, Constant
        visible = scope_text in ["Local", "Parameter", "Constant"]
        self.initial_value_label.setVisible(visible)
        self.initial_value_edit.setVisible(visible)
        self.initial_value_edit.setPlaceholderText("e.g., 0, true" if visible else "N/A for this scope")

    def on_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Name cannot be empty.")
            return
        # Basic C-identifier check: starts with letter or underscore, followed by letters, numbers, or underscores
        if not (name[0].isalpha() or name[0] == '_') or not all(c.isalnum() or c == '_' for c in name[1:]):
            QMessageBox.warning(self, "Input Error", "Name must be a valid C-style identifier (e.g., my_var, _tempVal, counter2).")
            return
        # Check for name uniqueness, allowing current name if editing
        if name in self.existing_names and name != self.original_name:
            QMessageBox.warning(self, "Input Error", f"The name '{name}' is already in use for another chart data item.")
            return

        scope = self.scope_combo.currentText()
        initial_value = self.initial_value_edit.text().strip()
        if scope in ["Parameter", "Constant"] and not initial_value:
             QMessageBox.warning(self, "Input Error", f"Initial value is required for a '{scope}' data item.")
             return
        # Input/Output initial values usually set by Simulink model context, not chart definition. Stateflow might ignore.
        if scope in ["Input", "Output"] and initial_value:
            QMessageBox.information(self, "Information", f"Initial value for '{scope}' scope is typically managed by Simulink or MATLAB workspace. It may be ignored within Stateflow properties here.")
            # Optionally clear or just let it pass based on user workflow
            # self.initial_value_edit.clear() # If strict

        super().accept() # If all checks pass, accept the dialog


    def get_data_properties(self):
        return {
            'name': self.name_edit.text().strip(),
            'scope': self.scope_combo.currentText(),
            'datatype': self.type_combo.currentText(),
            'initial_value': self.initial_value_edit.text().strip() if self.initial_value_edit.isVisible() else "",
            'description': self.description_edit.toPlainText().strip()
        }

# New Dialog for managing all Chart I/O Data
class ChartIOPropertiesDialog(QDialog):
    def __init__(self, parent=None, chart_io_data_list=None):
        super().__init__(parent)
        self.setWindowTitle("Chart Input/Output & Data Store Management")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "IO"))
        self.setMinimumSize(750, 550)

        # Work on a deep copy of the data list
        self.current_io_data = [dict(item) for item in (chart_io_data_list if chart_io_data_list else [])]

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        self.tables = {} # scope_str -> QTableWidget

        for scope in CHART_DATA_SCOPES:
            page_widget = QWidget()
            page_layout = QVBoxLayout(page_widget)

            table = QTableWidget()
            table.setColumnCount(4) # Name, Type, Initial Value, Description
            table.setHorizontalHeaderLabels(["Name", "Data Type", "Initial Value", "Description"])
            table.horizontalHeader().setStretchLastSection(True)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setSelectionMode(QAbstractItemView.SingleSelection) # Ensure one item at a time
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            # Store scope in table for easier access in lambda
            table.setProperty("scope_name", scope)
            table.doubleClicked.connect(lambda index, t=table: self._edit_item(t.property("scope_name"), index.row()))

            self.tables[scope] = table
            page_layout.addWidget(table)

            button_layout = QHBoxLayout()
            add_btn = QPushButton(get_standard_icon(QStyle.SP_FileDialogNewFolder,"Add"),f"Add {scope}...")
            add_btn.clicked.connect(lambda _, s=scope: self._add_item(s)) # Capture scope for lambda
            edit_btn = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton,"Edit"),"Edit Selected...")
            edit_btn.clicked.connect(lambda _, t=table: self._edit_item_selected(t))
            remove_btn = QPushButton(get_standard_icon(QStyle.SP_TrashIcon,"Del"),"Remove Selected")
            remove_btn.clicked.connect(lambda _, t=table: self._remove_item_selected(t))

            button_layout.addWidget(add_btn); button_layout.addWidget(edit_btn); button_layout.addWidget(remove_btn)
            button_layout.addStretch()
            page_layout.addLayout(button_layout)
            self.tab_widget.addTab(page_widget, scope)

        main_layout.addWidget(self.tab_widget)
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.accepted.connect(self.accept) # Commit changes
        dialog_buttons.rejected.connect(self.reject) # Discard changes
        main_layout.addWidget(dialog_buttons)
        self._refresh_all_tables()

    def _get_all_names(self): # Helper to get all names from self.current_io_data
        return [item['name'] for item in self.current_io_data]

    def _refresh_table(self, scope):
        table = self.tables[scope]
        table.setRowCount(0)
        items_for_scope = [item for item in self.current_io_data if item['scope'] == scope]
        for row, item_data in enumerate(items_for_scope):
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(item_data.get('name', '')))
            table.setItem(row, 1, QTableWidgetItem(item_data.get('datatype', '')))
            # Only show initial value meaningfully for these scopes
            initial_val_display = "N/A"
            if scope in ["Local", "Parameter", "Constant"]: initial_val_display = item_data.get('initial_value', '')
            table.setItem(row, 2, QTableWidgetItem(initial_val_display))
            table.setItem(row, 3, QTableWidgetItem(item_data.get('description', '')))
        table.resizeColumnsToContents()

    def _refresh_all_tables(self):
        for scope in CHART_DATA_SCOPES: self._refresh_table(scope)

    def _add_item(self, scope_to_add):
        dialog = ChartDataItemDialog(self, existing_names=self._get_all_names(), default_scope=scope_to_add)
        if dialog.exec_() == QDialog.Accepted:
            new_item_data = dialog.get_data_properties()
            self.current_io_data.append(new_item_data)
            self._refresh_table(new_item_data['scope']) # Refresh added scope's table

    def _edit_item_selected(self, table_widget): # Pass the table widget itself
        scope = table_widget.property("scope_name")
        selected_rows = table_widget.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Edit Item", "Please select an item to edit from the table.")
            return
        self._edit_item(scope, selected_rows[0].row())

    def _edit_item(self, scope_of_item, row_index):
        items_for_this_scope = [item for item in self.current_io_data if item['scope'] == scope_of_item]
        if 0 <= row_index < len(items_for_this_scope):
            item_to_edit_dict_ref = items_for_this_scope[row_index] # This is a reference to a dict in self.current_io_data
            # For uniqueness check, pass all names EXCEPT the original name of the item being edited.
            dialog = ChartDataItemDialog(self, current_data=item_to_edit_dict_ref, existing_names=self._get_all_names())
            if dialog.exec_() == QDialog.Accepted:
                updated_props = dialog.get_data_properties()
                original_scope_before_edit = item_to_edit_dict_ref['scope']
                # Update the dictionary in-place, since item_to_edit_dict_ref is a reference.
                item_to_edit_dict_ref.update(updated_props)
                if original_scope_before_edit != updated_props['scope']:
                    self._refresh_table(original_scope_before_edit) # Refresh table of old scope
                self._refresh_table(updated_props['scope']) # Refresh table of new/current scope
        else: QMessageBox.warning(self, "Error", "Selected item for editing not found.")

    def _remove_item_selected(self, table_widget): # Pass the table widget
        scope = table_widget.property("scope_name")
        selected_rows = table_widget.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Remove Item", "Please select an item to remove.")
            return
        row_to_remove = selected_rows[0].row()
        items_for_scope = [item for item in self.current_io_data if item['scope'] == scope]
        if 0 <= row_to_remove < len(items_for_scope):
            item_dict_to_remove = items_for_scope[row_to_remove] # The actual dict from list
            reply = QMessageBox.question(self, "Confirm Deletion", f"Remove data item '{item_dict_to_remove.get('name')}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.current_io_data.remove(item_dict_to_remove) # Remove from main list
                self._refresh_table(scope) # Refresh current table
        else: QMessageBox.warning(self, "Error", "Could not find item to remove.")

    def get_updated_io_data(self):
        return self.current_io_data


# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file_path = None
        self.last_generated_model_path = None
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)
        self.chart_io_data = [] # List of dicts {'name': 'x', 'scope': 'Input', 'datatype': 'double', ...}

        self.scene = DiagramScene(self.undo_stack, self)
        self.scene.set_log_function(self.log_message)
        self.scene.modifiedStatusChanged.connect(self.setWindowModified)
        self.scene.modifiedStatusChanged.connect(self._update_window_title)

        self.init_ui()
        self._update_matlab_status_display(False, "Initializing. Configure in Simulation menu or attempt auto-detect.")
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)

        self._update_window_title(); self.on_new_file(silent=True)
        self.scene.selectionChanged.connect(self._update_properties_dock); self._update_properties_dock()

    def init_ui(self):
        self.setGeometry(50, 50, 1600, 1000)
        self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "BSM"))
        self._create_actions(); self._create_menus(); self._create_toolbars()
        self._create_status_bar(); self._create_docks(); self._create_central_widget()
        self._update_save_actions_enable_state(); self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state(); self.select_mode_action.trigger()

    def _create_actions(self):
        def _s(attr, fb=None): return getattr(QStyle,attr, getattr(QStyle,fb,QStyle.SP_CustomBase) if fb else QStyle.SP_CustomBase)
        self.new_action = QAction(get_standard_icon(_s("SP_FileIcon"),"New"), "&New", self, shortcut=QKeySequence.New, triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(_s("SP_DialogOpenButton"),"Opn"), "&Open...", self, shortcut=QKeySequence.Open, triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(_s("SP_DialogSaveButton"),"Sav"), "&Save", self, shortcut=QKeySequence.Save, triggered=self.on_save_file)
        self.save_as_action = QAction(get_standard_icon(_s("SP_DialogSaveButton")), "Save &As...", self, shortcut=QKeySequence.SaveAs, triggered=self.on_save_file_as)
        self.exit_action = QAction(get_standard_icon(_s("SP_DialogCloseButton"),"Exit"), "E&xit", self, shortcut=QKeySequence.Quit, triggered=self.close)
        self.undo_action = self.undo_stack.createUndoAction(self,"&Undo"); self.undo_action.setShortcut(QKeySequence.Undo); self.undo_action.setIcon(get_standard_icon(_s("SP_ArrowBack"),"Un"))
        self.redo_action = self.undo_stack.createRedoAction(self,"&Redo"); self.redo_action.setShortcut(QKeySequence.Redo); self.redo_action.setIcon(get_standard_icon(_s("SP_ArrowForward"),"Re"))
        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_actions_enable_state); self.undo_stack.canRedoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.select_all_action = QAction(get_standard_icon(_s("SP_FileDialogDetailedView"),"All"),"Select &All",self,shortcut=QKeySequence.SelectAll,triggered=self.on_select_all)
        self.delete_action = QAction(get_standard_icon(_s("SP_TrashIcon"),"Del"), "&Delete",self,shortcut=QKeySequence.Delete,triggered=self.on_delete_selected)

        self.mode_action_group = QActionGroup(self); self.mode_action_group.setExclusive(True)
        self.select_mode_action = QAction(QIcon.fromTheme("edit-select",get_standard_icon(_s("SP_ArrowCursor","SP_PointingHandCursor"),"Sel")),"Select/Move",self,checkable=True,triggered=lambda: self.scene.set_mode("select"))
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle",get_standard_icon(_s("SP_FileDialogNewFolder","SP_FileIcon"),"St")),"Add State",self,checkable=True,triggered=lambda: self.scene.set_mode("state"))
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector",get_standard_icon(_s("SP_ArrowRight","SP_FileDialogBack"),"Tr")),"Add Transition",self,checkable=True,triggered=lambda: self.scene.set_mode("transition"))
        self.add_comment_mode_action = QAction(QIcon.fromTheme("insert-text",get_standard_icon(_s("SP_MessageBoxInformation","SP_FileLinkIcon"),"Cm")),"Add Comment",self,checkable=True,triggered=lambda: self.scene.set_mode("comment"))
        for act in [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action]: self.mode_action_group.addAction(act)
        self.select_mode_action.setChecked(True)

        self.export_simulink_action = QAction(get_standard_icon(_s("SP_ArrowRight"),"->M"),"&Export to Simulink...",self,triggered=self.on_export_simulink)
        self.edit_chart_io_action = QAction(get_standard_icon(_s("SP_FileDialogContentsView","SP_CustomBase"),"IO"), "Chart &I/O Data...", self, statusTip="Define Input, Output, Local data for the Stateflow Chart", triggered=self.on_edit_chart_io_properties) # New Action
        self.run_simulation_action = QAction(get_standard_icon(_s("SP_MediaPlay"),"Run"),"&Run Simulation...",self,triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(_s("SP_ComputerIcon"),"Cde"),"Generate &Code (C/C++)...",self,triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(_s("SP_ComputerIcon","SP_FileDialogInfoView"),"Cfg"),"&MATLAB Settings...",self,triggered=self.on_matlab_settings)
        self.about_action = QAction(get_standard_icon(_s("SP_DialogHelpButton"),"?"),"&About",self,triggered=self.on_about)

    def _create_menus(self):
        menu_bar=self.menuBar(); menu_bar.setStyleSheet("QMenuBar {background-color:#E8E8E8;} QMenu::item:selected {background-color:#D0D0D0;}")
        file_menu=menu_bar.addMenu("&File"); file_menu.addActions([self.new_action,self.open_action,self.save_action,self.save_as_action]); file_menu.addSeparator()
        file_menu.addAction(self.export_simulink_action); file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        edit_menu=menu_bar.addMenu("&Edit"); edit_menu.addActions([self.undo_action,self.redo_action]); edit_menu.addSeparator()
        edit_menu.addActions([self.delete_action,self.select_all_action]); edit_menu.addSeparator()
        mode_menu=edit_menu.addMenu(get_standard_icon(QStyle.SP_DesktopIcon,"Mode"),"Interaction Mode"); mode_menu.addActions([self.select_mode_action,self.add_state_mode_action,self.add_transition_mode_action,self.add_comment_mode_action])
        sim_menu=menu_bar.addMenu("&Simulation"); sim_menu.addAction(self.edit_chart_io_action); sim_menu.addSeparator() # Added Chart I/O menu item
        sim_menu.addActions([self.run_simulation_action,self.generate_code_action]); sim_menu.addSeparator(); sim_menu.addAction(self.matlab_settings_action)
        self.view_menu=menu_bar.addMenu("&View"); help_menu=menu_bar.addMenu("&Help"); help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        isz=QSize(28,28); tbs=Qt.ToolButtonTextUnderIcon
        ftb=self.addToolBar("File"); ftb.setIconSize(isz); ftb.setToolButtonStyle(tbs); ftb.addActions([self.new_action,self.open_action,self.save_action])
        etb=self.addToolBar("Edit"); etb.setIconSize(isz); etb.setToolButtonStyle(tbs); etb.addActions([self.undo_action,self.redo_action]); etb.addSeparator(); etb.addAction(self.delete_action)
        tools_tb=self.addToolBar("Tools"); tools_tb.setIconSize(isz); tools_tb.setToolButtonStyle(tbs); tools_tb.addActions([self.select_mode_action,self.add_state_mode_action,self.add_transition_mode_action,self.add_comment_mode_action])
        self.addToolBarBreak()
        sim_tb=self.addToolBar("Simulation"); sim_tb.setIconSize(isz); sim_tb.setToolButtonStyle(tbs)
        sim_tb.addActions([self.export_simulink_action, self.edit_chart_io_action, self.run_simulation_action,self.generate_code_action]) # Added Chart I/O action to toolbar

    def _create_status_bar(self):
        self.status_bar=QStatusBar(self); self.setStatusBar(self.status_bar); self.status_label=QLabel("Ready"); self.status_bar.addWidget(self.status_label,1)
        self.matlab_status_label=QLabel("MATLAB: Init..."); self.matlab_status_label.setToolTip("MATLAB Status"); self.matlab_status_label.setStyleSheet("padding:0 10px 0 5px;")
        self.status_bar.addPermanentWidget(self.matlab_status_label)
        self.progress_bar=QProgressBar(self); self.progress_bar.setRange(0,0); self.progress_bar.setVisible(False); self.progress_bar.setMaximumWidth(180); self.progress_bar.setTextVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)
        self.tools_dock=QDockWidget("Tools",self); self.tools_dock.setObjectName("ToolsDock"); self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea|Qt.RightDockWidgetArea)
        tools_w=QWidget(); tools_ml=QVBoxLayout(tools_w); tools_ml.setSpacing(10); tools_ml.setContentsMargins(8,8,8,8)
        mode_gb=QGroupBox("Interaction Modes"); mode_l=QVBoxLayout(); mode_l.setSpacing(5)
        btn_acts=[self.select_mode_action,self.add_state_mode_action,self.add_transition_mode_action,self.add_comment_mode_action]
        for act in btn_acts: btn=QToolButton(); btn.setDefaultAction(act); btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(20,20)); mode_l.addWidget(btn)
        mode_gb.setLayout(mode_l); tools_ml.addWidget(mode_gb)

        drag_gb=QGroupBox("Drag to Canvas"); drag_l=QVBoxLayout(); drag_l.setSpacing(5)
        cstyle="QPushButton{background-color:#E8F0FE;color:#1C3A5D;border:1px solid #A9CCE3;padding:6px;} QPushButton:hover{background-color:#D8E0EE;} QPushButton:pressed{background-color:#C8D0DE;}"
        drag_defs = [ ("State","application/x-bsm-tool","State",QStyle.SP_FileDialogNewFolder,"St"),
                      ("Initial State","application/x-bsm-tool","Initial State",QStyle.SP_ToolBarHorizontalExtensionButton,"I"),
                      ("Final State","application/x-bsm-tool","Final State",QStyle.SP_DialogOkButton,"F"),
                      ("Transition", "application/x-bsm-tool", "Transition", QStyle.SP_ArrowRight, "Tr"), # Added Transition
                      ("Comment","application/x-bsm-tool","Comment",QStyle.SP_MessageBoxInformation,"Cm")]
        for txt,mime,data,st_enum,fb_txt in drag_defs:
            btn=DraggableToolButton(txt,mime,data,cstyle); btn.setIcon(get_standard_icon(st_enum,fb_txt)); btn.setIconSize(QSize(22,22)); drag_l.addWidget(btn)
        drag_gb.setLayout(drag_l); tools_ml.addWidget(drag_gb)

        tools_ml.addStretch(); self.tools_dock.setWidget(tools_w); self.addDockWidget(Qt.LeftDockWidgetArea,self.tools_dock); self.view_menu.addAction(self.tools_dock.toggleViewAction())
        self.log_dock=QDockWidget("Log",self); self.log_dock.setObjectName("LogDock"); self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea|Qt.TopDockWidgetArea)
        self.log_output=QTextEdit(); self.log_output.setReadOnly(True); self.log_output.setFont(QFont("Consolas",9)); self.log_output.setStyleSheet("QTextEdit{background-color:#FDFDFD;color:#333;border:1px solid #DDD;}")
        self.log_dock.setWidget(self.log_output); self.addDockWidget(Qt.BottomDockWidgetArea,self.log_dock); self.view_menu.addAction(self.log_dock.toggleViewAction())
        self.prop_dock=QDockWidget("Properties",self); self.prop_dock.setObjectName("PropertiesDock"); self.prop_dock.setAllowedAreas(Qt.RightDockWidgetArea|Qt.LeftDockWidgetArea)
        prop_w_main=QWidget(); self.prop_layout=QVBoxLayout(prop_w_main); self.prop_editor_label=QLabel("<i>No item selected.</i>")
        self.prop_editor_label.setAlignment(Qt.AlignTop|Qt.AlignLeft); self.prop_editor_label.setWordWrap(True); self.prop_editor_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.prop_edit_btn=QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton,"Edt"),"Edit Properties..."); self.prop_edit_btn.setEnabled(False); self.prop_edit_btn.clicked.connect(self._on_edit_selected_props_dock); self.prop_edit_btn.setIconSize(QSize(18,18))
        self.prop_layout.addWidget(self.prop_editor_label,1); self.prop_layout.addWidget(self.prop_edit_btn); prop_w_main.setLayout(self.prop_layout)
        self.prop_dock.setWidget(prop_w_main); self.addDockWidget(Qt.RightDockWidgetArea,self.prop_dock); self.view_menu.addAction(self.prop_dock.toggleViewAction())

    def _create_central_widget(self): self.view=ZoomableView(self.scene,self); self.setCentralWidget(self.view)
    def _update_properties_dock(self):
        sel=self.scene.selectedItems(); info_html=""
        if len(sel)==1:
            item=sel[0]; props=item.get_data(); item_type=type(item).__name__.replace("Graphics","").replace("Item","")
            info_html=f"<b>Type:</b> {item_type}<br><hr style='margin:3px 0;'>"
            def _fmt(s,ml=30): return "<i>(none)</i>" if not s else html.escape(s.split('\n')[0][:ml] + ('...' if len(s.split('\n')[0])>ml or '\n' in s else ''))
            def _clr(c): hc = QColor(c); return f"<span style='background-color:{hc.name()};color:{'black' if hc.lightnessF()>0.5 else 'white'};padding:0 5px;'>&nbsp;{html.escape(hc.name())}&nbsp;</span>"
            if isinstance(item,GraphicsStateItem):
                info_html+=f"<b>Name:</b> {html.escape(props['name'])}<br><b>Initial:</b> {'Yes' if props['is_initial'] else 'No'}<br><b>Final:</b> {'Yes' if props['is_final'] else 'No'}<br><b>Color:</b> {_clr(props.get('color','#FFFFFF'))}<br>"
                info_html+=f"<b>Entry:</b> {_fmt(props.get('entry_action'))}<br><b>During:</b> {_fmt(props.get('during_action'))}<br><b>Exit:</b> {_fmt(props.get('exit_action'))}<br>"
                if props.get('description'): info_html+=f"<hr style='margin:3px 0;'><b>Desc:</b> {_fmt(props.get('description'),40)}<br>"
            elif isinstance(item,GraphicsTransitionItem):
                lbl_p=[html.escape(props['event'])] if props.get('event') else []
                if props.get('condition'): lbl_p.append(f"[{html.escape(props['condition'])}]")
                if props.get('action'): lbl_p.append(f"/{{{_fmt(props['action'],20)}}}")
                info_html+=f"<b>Label:</b> {' '.join(lbl_p) if lbl_p else '<i>(No Label)</i>'}<br><b>From:</b> {html.escape(props['source'])}<br><b>To:</b> {html.escape(props['target'])}<br><b>Color:</b> {_clr(props.get('color','#FFFFFF'))}<br>"
                info_html+=f"<b>Curve:</b> Bend={props.get('control_offset_x',0):.0f}, Shift={props.get('control_offset_y',0):.0f}<br>"
                if props.get('description'): info_html+=f"<hr style='margin:3px 0;'><b>Desc:</b> {_fmt(props.get('description'),40)}<br>"
            elif isinstance(item,GraphicsCommentItem): info_html+=f"<b>Text:</b> {_fmt(props['text'],60)}<br>"
            else: info_html+="Unknown Item"
            self.prop_edit_btn.setEnabled(True); self.prop_edit_btn.setToolTip(f"Edit {item_type}")
        elif len(sel)>1: info_html=f"<b>{len(sel)} items selected.</b><br><i>Select single item.</i>"; self.prop_edit_btn.setEnabled(False); self.prop_edit_btn.setToolTip("Select single item.")
        else: info_html="<i>No item selected.</i>"; self.prop_edit_btn.setEnabled(False); self.prop_edit_btn.setToolTip("")
        self.prop_editor_label.setText(info_html)

    def _on_edit_selected_props_dock(self):
        if len(self.scene.selectedItems())==1: self.scene.edit_item_properties(self.scene.selectedItems()[0])
    def log_message(self,message:str): ts=QTime.currentTime().toString('hh:mm:ss.zzz'); self.log_output.append(f"[{ts}] {message}"); self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum()); self.status_label.setText(message.split('\n')[0][:120])
    def _update_window_title(self): self.setWindowTitle(f"{APP_NAME} - {os.path.basename(self.current_file_path) if self.current_file_path else 'Untitled'}[*]")
    def _update_save_actions_enable_state(self): self.save_action.setEnabled(self.isWindowModified()); self.save_as_action.setEnabled(True)
    def _update_undo_redo_actions_enable_state(self): self.undo_action.setEnabled(self.undo_stack.canUndo()); self.redo_action.setEnabled(self.undo_stack.canRedo()); self.undo_action.setText(f"&Undo {self.undo_stack.undoText()}" if self.undo_stack.canUndo() else "&Undo"); self.redo_action.setText(f"&Redo {self.undo_stack.redoText()}" if self.undo_stack.canRedo() else "&Redo")
    def _update_matlab_status_display(self,connected,message): self.matlab_status_label.setText(f"MATLAB: {'Conn' if connected else 'Disconn'}"); self.matlab_status_label.setToolTip(f"Status: {message}"); self.matlab_status_label.setStyleSheet(f"color:{'#006400' if connected else '#B22222'};font-weight:bold;padding:0 10px 0 5px;"); self.log_message(f"MATLAB: {message}"); self._update_matlab_actions_enabled_state()
    def _update_matlab_actions_enabled_state(self): is_conn=self.matlab_connection.connected; self.export_simulink_action.setEnabled(is_conn); self.run_simulation_action.setEnabled(is_conn); self.generate_code_action.setEnabled(is_conn) # self.edit_chart_io_action is always enabled
    def _start_matlab_operation(self,op_name): self.log_message(f"MATLAB Op: {op_name} starting..."); self.status_label.setText(f"Running: {op_name}..."); self.progress_bar.setVisible(True); self.set_ui_enabled_for_matlab_op(False)
    def _finish_matlab_operation(self): self.progress_bar.setVisible(False); self.status_label.setText("Ready"); self.set_ui_enabled_for_matlab_op(True); self.log_message("MATLAB Op: Finished.")
    def set_ui_enabled_for_matlab_op(self,enabled:bool): self.menuBar().setEnabled(enabled); [c.setEnabled(enabled) for c in self.findChildren(QToolBar)];
                                                        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
                                                        for d_name in ["ToolsDock","PropertiesDock"]: d=self.findChild(QDockWidget,d_name);
                                                                                                   if d: d.setEnabled(enabled)
    def _handle_matlab_modelgen_or_sim_finished(self,success,message,data): self._finish_matlab_operation(); self.log_message(f"MATLAB ({'Ok' if success else 'Fail'}): {message}");
                                                                          if success:
                                                                              if "Model gen" in message and data: self.last_generated_model_path=data; QMessageBox.information(self,"Simulink Export",f"Model generated:\n{data}")
                                                                              elif "Simulation" in message: QMessageBox.information(self,"Simulation",f"Sim finished.\n{message}")
                                                                          else: QMessageBox.warning(self,"MATLAB Op Failed",message)
    def _handle_matlab_codegen_finished(self,success,message,output_dir): self._finish_matlab_operation(); self.log_message(f"MATLAB CodeGen ({'Ok' if success else 'Fail'}): {message}");
                                                                      if success and output_dir:
                                                                          mb=QMessageBox(self);mb.setIcon(QMessageBox.Information);mb.setWindowTitle("Code Gen Success");mb.setTextFormat(Qt.RichText);mb.setText(f"Code gen ok.<br>Out: <a href='file:///{os.path.abspath(output_dir)}'>{os.path.abspath(output_dir)}</a>")
                                                                          ob=mb.addButton("Open Dir",QMessageBox.ActionRole);mb.addButton(QMessageBox.Ok);mb.exec_();
                                                                          if mb.clickedButton()==ob:
                                                                              try:QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(output_dir)))
                                                                              except Exception as e: self.log_message(f"Err opening dir {output_dir}:{e}"); QMessageBox.warning(self,"Err",f"Could not open:\n{e}")
                                                                      elif not success: QMessageBox.warning(self,"CodeGen Fail",message)
    def _prompt_save_if_dirty(self)->bool:
        if not self.isWindowModified(): return True
        fn=os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        r=QMessageBox.question(self,"Save? ",f"'{fn}' has unsaved changes.\nSave?",QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Save)
        if r==QMessageBox.Save: return self.on_save_file()
        elif r==QMessageBox.Cancel: return False
        return True

    def on_new_file(self,silent=False):
        if not silent and not self._prompt_save_if_dirty(): return False
        self.scene.clear(); self.scene.setSceneRect(0,0,5000,4000); self.current_file_path=None; self.last_generated_model_path=None
        self.chart_io_data = [] # Reset Chart I/O Data for new file
        self.undo_stack.clear(); self.scene.set_dirty(False); self._update_window_title(); self._update_undo_redo_actions_enable_state()
        if not silent: self.log_message("New diagram created."); self.view.resetTransform(); self.view.centerOn(2500,2000); self.select_mode_action.trigger()
        return True
    def on_open_file(self):
        if not self._prompt_save_if_dirty(): return
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        fp, _ = QFileDialog.getOpenFileName(self,"Open BSM",start_dir,FILE_FILTER)
        if fp:
            self.log_message(f"Opening: {fp}")
            if self._load_from_path(fp):
                self.current_file_path=fp;self.last_generated_model_path=None;self.undo_stack.clear();self.scene.set_dirty(False)
                self._update_window_title();self._update_undo_redo_actions_enable_state();self.log_message(f"Opened: {fp}")
                items_rect = self.scene.itemsBoundingRect()
                if not items_rect.isEmpty(): self.view.fitInView(items_rect.adjusted(-100,-100,100,100), Qt.KeepAspectRatio)
                else: self.view.resetTransform(); self.view.centerOn(2500,2000)
            else: QMessageBox.critical(self,"Open Error",f"Could not load: {fp}");self.log_message(f"Fail open: {fp}")
    def _load_from_path(self,file_path):
        try:
            with open(file_path,'r',encoding='utf-8') as f: data=json.load(f)
            if not isinstance(data,dict) or 'states' not in data or 'transitions' not in data: self.log_message(f"Err: Invalid BSM: {file_path}"); return False
            self.scene.load_diagram_data(data)
            self.chart_io_data = data.get('chart_io_data', []) # Load Chart I/O, default to empty if not present
            return True
        except Exception as e: self.log_message(f"Load err {file_path}:{type(e).__name__}:{e}"); return False
    def on_save_file(self)->bool: return self._save_to_path(self.current_file_path) if self.current_file_path else self.on_save_file_as()
    def on_save_file_as(self)->bool:
        start_path = self.current_file_path if self.current_file_path else os.path.join(QDir.homePath(),"untitled"+FILE_EXTENSION)
        fp, _ = QFileDialog.getSaveFileName(self,"Save BSM As",start_path,FILE_FILTER)
        if fp:
            if not fp.lower().endswith(FILE_EXTENSION): fp+=FILE_EXTENSION
            if self._save_to_path(fp): self.current_file_path=fp;self._update_window_title(); return True
        return False
    def _save_to_path(self,file_path)->bool:
        sf = QSaveFile(file_path)
        if not sf.open(QIODevice.WriteOnly|QIODevice.Text): self.log_message(f"Err opening save {file_path}:{sf.errorString()}");QMessageBox.critical(self,"Save Err",f"Fail open:{sf.errorString()}"); return False
        try:
            diagram_data = self.scene.get_diagram_data()
            # Combine diagram data with app version and chart_io_data for saving
            full_data = {'app_version': APP_VERSION, **diagram_data, 'chart_io_data': self.chart_io_data}
            json_data = json.dumps(full_data,indent=4,ensure_ascii=False)
            if sf.write(json_data.encode('utf-8'))==-1 or not sf.commit():
                err=sf.errorString(); self.log_message(f"Err write/commit {file_path}:{err}"); QMessageBox.critical(self,"Save Err",f"Fail:{err}"); sf.cancelWriting(); return False
            self.log_message(f"Saved: {file_path}"); self.scene.set_dirty(False); return True
        except Exception as e: self.log_message(f"Save err {file_path}:{e}"); QMessageBox.critical(self,"Save Err",f"Err:{e}"); sf.cancelWriting(); return False

    def on_select_all(self): self.scene.select_all()
    def on_delete_selected(self): self.scene.delete_selected_items()

    def on_export_simulink(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self,"MATLAB Err","MATLAB not connected."); return
        dlg=QDialog(self);dlg.setWindowTitle("Export to Simulink");dlg.setWindowIcon(get_standard_icon(QStyle.SP_ArrowRight,"->M"));lo=QFormLayout(dlg);lo.setSpacing(10)
        mname_def="BSM_SL_Model";
        if self.current_file_path: base=os.path.splitext(os.path.basename(self.current_file_path))[0]; mname_def="".join(c if c.isalnum()or c=='_' else '_' for c in base)
        if not mname_def or not mname_def[0].isalpha():mname_def="M_"+mname_def
        mname_edit=QLineEdit(mname_def); lo.addRow("Model Name:",mname_edit)
        out_dir_def=os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath(); out_dir_edit=QLineEdit(out_dir_def)
        browse_btn=QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw"),"Browse...")
        def _brs_dir():d=QFileDialog.getExistingDirectory(dlg,"Select Output Dir",out_dir_edit.text());
                       if d:out_dir_edit.setText(d)
        browse_btn.clicked.connect(_brs_dir); dir_lo=QHBoxLayout(); dir_lo.addWidget(out_dir_edit,1);dir_lo.addWidget(browse_btn);lo.addRow("Output Dir:",dir_lo)
        btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);btns.accepted.connect(dlg.accept);btns.rejected.connect(dlg.reject);lo.addRow(btns);dlg.setMinimumWidth(450)
        if dlg.exec_()==QDialog.Accepted:
            mname=mname_edit.text().strip();out_dir=out_dir_edit.text().strip()
            if not mname or not out_dir: QMessageBox.warning(self,"Input Err","Model name and output dir required."); return
            if not mname[0].isalpha() or not all(c.isalnum() or c=='_' for c in mname): QMessageBox.warning(self,"Invalid Name","Model name must start with letter, contain alnum/underscores."); return
            if not os.path.exists(out_dir):
                try:os.makedirs(out_dir,exist_ok=True)
                except OSError as e:QMessageBox.critical(self,"Dir Err",f"Could not create dir:\n{e}"); return
            diag_data=self.scene.get_diagram_data()
            if not diag_data['states']: QMessageBox.information(self,"Empty","No states to export."); return
            self._start_matlab_operation(f"Exporting '{mname}' to Simulink")
            # Pass chart_io_data to the Simulink generation function
            self.matlab_connection.generate_simulink_model(diag_data['states'],diag_data['transitions'], self.chart_io_data, out_dir, mname)

    # New method for Chart I/O Properties
    def on_edit_chart_io_properties(self):
        dialog = ChartIOPropertiesDialog(self, chart_io_data_list=self.chart_io_data)
        if dialog.exec_() == QDialog.Accepted:
            updated_data = dialog.get_updated_io_data()
            if self.chart_io_data != updated_data: # Check if something actually changed
                self.chart_io_data = updated_data
                self.scene.set_dirty(True) # Mark the project as modified
                self.log_message("Chart I/O data configuration updated.")
        # Else: User cancelled, self.chart_io_data remains unchanged

    def on_run_simulation(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self,"MATLAB Err","MATLAB not connected."); return
        def_dir = os.path.dirname(self.last_generated_model_path) if self.last_generated_model_path else (os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath())
        mp, _ = QFileDialog.getOpenFileName(self,"Select Simulink Model",def_dir,"Simulink (*.slx);;All(*)")
        if not mp:return; self.last_generated_model_path=mp
        stime,ok=QInputDialog.getDouble(self,"Sim Time","Stop time(s):",10.0,0.001,86400.0,3)
        if not ok: return
        self._start_matlab_operation(f"Running Simulink for '{os.path.basename(mp)}'")
        self.matlab_connection.run_simulation(mp,stime)
    def on_generate_code(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self,"MATLAB Err","MATLAB not connected."); return
        def_dir=os.path.dirname(self.last_generated_model_path) if self.last_generated_model_path else (os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath())
        mp, _ = QFileDialog.getOpenFileName(self,"Select Model for CodeGen",def_dir,"Simulink (*.slx);;All(*)")
        if not mp: return; self.last_generated_model_path=mp
        dlg=QDialog(self);dlg.setWindowTitle("CodeGen Opts");dlg.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon,"Cde"));lo=QFormLayout(dlg);lo.setSpacing(10)
        lang_cb=QComboBox(); lang_cb.addItems(["C","C++"]); lang_cb.setCurrentText("C++"); lo.addRow("Lang:",lang_cb)
        def_out_base=os.path.dirname(mp); out_dir_edit=QLineEdit(def_out_base); br_btn_cg=QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw"),"Browse...")
        def _brs_dir_cg():d=QFileDialog.getExistingDirectory(dlg,"Select Base Output Dir",out_dir_edit.text());
                         if d:out_dir_edit.setText(d)
        br_btn_cg.clicked.connect(_brs_dir_cg); dir_lo_cg=QHBoxLayout(); dir_lo_cg.addWidget(out_dir_edit,1);dir_lo_cg.addWidget(br_btn_cg);lo.addRow("Base Out Dir:",dir_lo_cg)
        btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);btns.accepted.connect(dlg.accept);btns.rejected.connect(dlg.reject);lo.addRow(btns);dlg.setMinimumWidth(450)
        if dlg.exec_()==QDialog.Accepted:
            lang=lang_cb.currentText();out_dir_base=out_dir_edit.text().strip()
            if not out_dir_base: QMessageBox.warning(self,"Input Err","Base output dir required."); return
            if not os.path.exists(out_dir_base):
                try: os.makedirs(out_dir_base,exist_ok=True)
                except OSError as e: QMessageBox.critical(self,"Dir Err",f"Could not create dir:\n{e}"); return
            self._start_matlab_operation(f"Generating {lang} code for '{os.path.basename(mp)}'")
            self.matlab_connection.generate_code(mp,lang,out_dir_base)
    def on_matlab_settings(self): MatlabSettingsDialog(self.matlab_connection,self).exec_()
    def on_about(self): QMessageBox.about(self,"About "+APP_NAME,f"<h3>{APP_NAME} v{APP_VERSION}</h3><p>Graphical FSM designer. Integrates with MATLAB/Simulink for simulation & C/C++ code generation.</p><p><b>Features:</b> Diagramming, properties, JSON save/load ({FILE_EXTENSION}), Undo/Redo, Zoom/Pan, Grid/Snap, Simulink Export, Chart I/O, Sim, CodeGen.</p><p><i>AI Revell Lab</i></p>")
    def closeEvent(self,event:QCloseEvent):
        if self._prompt_save_if_dirty():
            if self.matlab_connection._active_threads: self.log_message(f"Closing. {len(self.matlab_connection._active_threads)} MATLAB ops might run in bg.")
            event.accept()
        else: event.ignore()

if __name__ == '__main__':
    if hasattr(Qt,'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling,True)
    if hasattr(Qt,'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps,True)
    app=QApplication(sys.argv)
    main_win=MainWindow()
    main_win.show()
    sys.exit(app.exec_())
```