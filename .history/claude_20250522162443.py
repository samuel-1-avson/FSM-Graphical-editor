
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
    QGraphicsSceneHoverEvent, QGraphicsTextItem
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
APP_VERSION = "1.5.1" # Incremented for fix
APP_NAME = "Brain State Machine Designer"
FILE_EXTENSION = ".bsm"
FILE_FILTER = f"Brain State Machine Files (*{FILE_EXTENSION});;All Files (*)"

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
                    # Test by running a simple command that exits
                    test_process = subprocess.run([path_candidate, "-batch", "exit"], timeout=5, capture_output=True)
                    if test_process.returncode == 0:
                        if self.set_matlab_path(path_candidate): # Validates and sets internal path
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
            # Create a temporary directory for MATLAB scripts
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

        # Connections for thread management
        thread.started.connect(worker.run_command)
        worker.finished_signal.connect(thread.quit)
        worker.finished_signal.connect(worker.deleteLater) # Clean up worker
        thread.finished.connect(thread.deleteLater)      # Clean up thread

        # Track active threads to prevent Python from exiting if MATLAB is still running
        self._active_threads.append(thread)
        thread.finished.connect(lambda t=thread: self._active_threads.remove(t) if t in self._active_threads else None)

        thread.start()

    def generate_simulink_model(self, states, transitions, output_dir, model_name="BrainStateMachine"):
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected.", "") # Using simulationFinished for this too
            return False

        slx_file_path = os.path.join(output_dir, f"{model_name}.slx").replace('\\', '/')
        model_name_orig = model_name # For use in strings

        script_lines = [
            f"% Auto-generated Simulink model script for '{model_name_orig}'",
            f"disp('Starting Simulink model generation for {model_name_orig}...');",
            f"modelNameVar = '{model_name_orig}';",
            f"outputModelPath = '{slx_file_path}';",
            "try",
            # Close if loaded, delete if existing on disk to prevent issues with chart objects
            "    if bdIsLoaded(modelNameVar), close_system(modelNameVar, 0); end",
            "    if exist(outputModelPath, 'file'), delete(outputModelPath); end", # Important for fresh creation

            "    hModel = new_system(modelNameVar);", # Create new model with this name
            "    open_system(hModel);",

            "    disp('Adding Stateflow chart...');",
            "    machine = sfroot.find('-isa', 'Stateflow.Machine', 'Name', modelNameVar);",
            "    if isempty(machine)",
            "        error('Stateflow machine for model ''%s'' not found after new_system.', modelNameVar);",
            "    end",

            "    chartSFObj = Stateflow.Chart(machine);", # Create chart inside the new machine
            "    chartSFObj.Name = 'BrainStateMachineLogic';", # Or some user-defined name

            # Link the Stateflow chart object to a block in the Simulink model
            "    chartBlockSimulinkPath = [modelNameVar, '/', 'BSM_Chart'];", # Path to chart block in Simulink
            "    add_block('stateflow/Chart', chartBlockSimulinkPath, 'Chart', chartSFObj.Path);",
            "    disp(['Stateflow chart block added at: ', chartBlockSimulinkPath]);",

            "    stateHandles = containers.Map('KeyType','char','ValueType','any');",
            "% --- State Creation ---"
        ]

        for i, state in enumerate(states):
            s_name_matlab = state['name'].replace("'", "''") # Escape single quotes for MATLAB strings
            # Create a MATLAB-safe variable name for the state handle
            s_id_matlab_safe = f"state_{i}_{state['name'].replace(' ', '_').replace('-', '_')}"
            s_id_matlab_safe = ''.join(filter(str.isalnum, s_id_matlab_safe))
            if not s_id_matlab_safe or not s_id_matlab_safe[0].isalpha(): s_id_matlab_safe = 's_' + s_id_matlab_safe

            state_label_parts = []
            if state.get('entry_action'):
                state_label_parts.append(f"entry: {state['entry_action'].replace(chr(10), '; ')}")
            if state.get('during_action'):
                state_label_parts.append(f"during: {state['during_action'].replace(chr(10), '; ')}")
            if state.get('exit_action'):
                state_label_parts.append(f"exit: {state['exit_action'].replace(chr(10), '; ')}")
            s_label_string = "\\n".join(state_label_parts) if state_label_parts else ""
            s_label_string_matlab = s_label_string.replace("'", "''")

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
            if trans.get('action'): label_parts.append(f"/{{{trans['action']}}}") # Correct Stateflow action syntax
            t_label = " ".join(label_parts).strip()
            t_label_matlab = t_label.replace("'", "''")

            script_lines.extend([
                f"if isKey(stateHandles, '{src_name_matlab}') && isKey(stateHandles, '{dst_name_matlab}')",
                f"    srcStateHandle = stateHandles('{src_name_matlab}');",
                f"    dstStateHandle = stateHandles('{dst_name_matlab}');",
                f"    t{i} = Stateflow.Transition(chartSFObj);",
                f"    t{i}.Source = srcStateHandle;",
                f"    t{i}.Destination = dstStateHandle;"
            ])
            if t_label_matlab:
                script_lines.append(f"    t{i}.LabelString = '{t_label_matlab}';")
            script_lines.append("else")
            script_lines.append(f"    disp(['Warning: Could not create SF transition from ''{src_name_matlab}'' to ''{dst_name_matlab}''. State missing.']);")
            script_lines.append("end")

        script_lines.extend([
            "% --- Finalize and Save ---",
            "    disp(['Attempting to save Simulink model to: ', outputModelPath]);",
            "    save_system(modelNameVar, outputModelPath, 'OverwriteIfChangedOnDisk', true);",
            "    close_system(modelNameVar, 0);", # Close model without saving again
            "    disp(['Simulink model saved successfully to: ', outputModelPath]);",
            "    fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', outputModelPath);", # Signal success with path
            "catch e",
            "    disp('ERROR during Simulink model generation:');",
            "    disp(getReport(e, 'extended', 'hyperlinks', 'off'));",
            "    if bdIsLoaded(modelNameVar), close_system(modelNameVar, 0); end", # Attempt to clean up model if open
            "    fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', strrep(getReport(e, 'basic'), '\\n', ' '));",
            "end"
        ])

        script_content = "\n".join(script_lines)
        # For debugging the script itself
        # print("--- MATLAB Script ---")
        # print(script_content)
        # print("---------------------")
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
            prevPath = path;
            addpath(modelDir);
            disp(['Added to MATLAB path: ', modelDir]);

            load_system(modelPath);
            disp(['Simulating model: ', modelName, ' for ', num2str(currentSimTime), ' seconds.']);

            % Consider adding outport for state activity for visualization if desired later
            simOut = sim(modelName, 'StopTime', num2str(currentSimTime));

            disp('Simulink simulation completed successfully.');
            % Could extract some results here if needed, e.g., from simOut.logsout
            fprintf('MATLAB_SCRIPT_SUCCESS:Simulation of ''%s'' finished at t=%s. Results in MATLAB workspace (simOut).\\n', modelName, num2str(currentSimTime));
        catch e
            disp('ERROR during Simulink simulation:');
            disp(getReport(e, 'extended', 'hyperlinks', 'off'));
            fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', strrep(getReport(e, 'basic'),'\\n',' '));
        end
        % Ensure model is closed even on error
        if bdIsLoaded(modelName), close_system(modelName, 0); end
        % Restore path
        path(prevPath);
        disp(['Restored MATLAB path. Removed: ', modelDir]);
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

        if not output_dir_base: output_dir_base = os.path.dirname(model_path) # Default to model's dir
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

            % Check for necessary licenses
            if ~(license('test', 'MATLAB_Coder') && license('test', 'Simulink_Coder') && license('test', 'Embedded_Coder'))
                error('Required licenses (MATLAB Coder, Simulink Coder, Embedded Coder) are not available.');
            end

            % Basic configuration for Embedded Coder (ert.tlc)
            set_param(modelName,'SystemTargetFile','ert.tlc'); % Using Embedded Coder Target
            set_param(modelName,'GenerateMakefile','on'); % Could be 'off' if user manages build

            % Configure for C or C++
            cfg = getActiveConfigSet(modelName);
            if strcmpi('{language}', 'C++')
                set_param(cfg, 'TargetLang', 'C++');
                % Configure C++ Interface - Class for the model
                set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'C++ class');
                set_param(cfg.getComponent('Code Generation'),'TargetLangStandard', 'C++11 (ISO)'); % Or C++14, C++17 as needed
                disp('Configured for C++ (class interface, C++11).');
            else % C
                set_param(cfg, 'TargetLang', 'C');
                set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'Reusable function'); % For C
                disp('Configured for C (reusable function).');
            end

            set_param(cfg, 'GenerateReport', 'on'); % Generates an HTML report
            set_param(cfg, 'GenCodeOnly', 'on'); % Don't compile, just generate code
            set_param(cfg, 'RTWVerbose', 'on'); % Verbose output during build

            % Specify output directory. Default is ./<model_name>_ert_rtw
            if ~exist(codeGenBaseDir, 'dir'), mkdir(codeGenBaseDir); disp(['Created base codegen dir: ', codeGenBaseDir]); end

            % Simulink usually creates a subdirectory like modelName_ert_rtw inside CodeGenFolder
            disp(['Code generation output base set to: ', codeGenBaseDir]);
            rtwbuild(modelName, 'CodeGenFolder', codeGenBaseDir, 'GenCodeOnly', true); % Invoke code generation
            disp('Code generation command (rtwbuild) executed.');

            % Try to determine the actual output directory (often a subdir)
            actualCodeDir = fullfile(codeGenBaseDir, [modelName '_ert_rtw']); % Common pattern
            if ~exist(actualCodeDir, 'dir')
                disp(['Warning: Standard codegen subdir ''', actualCodeDir, ''' not found. Output may be directly in base dir.']);
                actualCodeDir = codeGenBaseDir; % Fallback if specific subdir isn't created as expected
            end

            disp(['Simulink code generation successful. Code and report expected in/under: ', actualCodeDir]);
            fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', actualCodeDir); % Pass back actual dir
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
            # Construct command to run the script file
            matlab_run_command = f"run('{self.script_file.replace('\\', '/')}')" # Ensure forward slashes for MATLAB path
            cmd = [self.matlab_path, "-nodisplay", "-batch", matlab_run_command]

            # Increased timeout for potentially long operations like code generation
            timeout_seconds = 600 # 10 minutes, adjust as necessary
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8', # Try to catch MATLAB's output encoding
                timeout=timeout_seconds,  # Longer timeout
                check=False, # Don't raise exception on non-zero exit; handle manually
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0 # Hide console on Windows
            )

            stdout_str = process.stdout if process.stdout else ""
            stderr_str = process.stderr if process.stderr else ""

            # Check for custom failure marker from script
            if "MATLAB_SCRIPT_FAILURE:" in stdout_str:
                success = False
                for line in stdout_str.splitlines():
                    if line.startswith("MATLAB_SCRIPT_FAILURE:"):
                        error_detail = line.split(":", 1)[1].strip()
                        message = f"{self.success_message_prefix} script reported failure: {error_detail}"
                        break
                if not message: message = f"{self.success_message_prefix} script indicated failure. Full stdout:\n{stdout_str[:500]}"
                if stderr_str: message += f"\nStderr:\n{stderr_str[:300]}"

            elif process.returncode == 0: # MATLAB exited cleanly
                if "MATLAB_SCRIPT_SUCCESS:" in stdout_str:
                    success = True
                    for line in stdout_str.splitlines():
                        if line.startswith("MATLAB_SCRIPT_SUCCESS:"):
                            output_data_for_signal = line.split(":", 1)[1].strip() # Get data after marker
                            break
                    message = f"{self.success_message_prefix} completed successfully."
                    # Append the specific data only if it's not for generic simulation messages
                    if output_data_for_signal and self.success_message_prefix != "Simulation":
                         message += f" Data: {output_data_for_signal}"
                    elif output_data_for_signal and self.success_message_prefix == "Simulation":
                        message = output_data_for_signal # For simulation, the whole message is the output data
                else: # Script finished (exit 0) but marker not found
                    success = False
                    message = f"{self.success_message_prefix} script finished (MATLAB exit 0), but success marker not found."
                    message += f"\nStdout:\n{stdout_str[:500]}"
                    if stderr_str: message += f"\nStderr:\n{stderr_str[:300]}"
            else: # MATLAB process had non-zero exit code
                success = False
                error_output = stderr_str or stdout_str # Prefer stderr
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
            # Cleanup temp script and directory
            if os.path.exists(self.script_file):
                try:
                    os.remove(self.script_file)
                    script_dir = os.path.dirname(self.script_file)
                    # Only remove dir if it's one we created and it's empty
                    if script_dir.startswith(tempfile.gettempdir()) and "bsm_matlab_" in script_dir:
                        if not os.listdir(script_dir): os.rmdir(script_dir)
                        else: print(f"Warning: Temp directory {script_dir} not empty, not removed.")
                except OSError as e:
                    # Non-critical, just log
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
        # Basic styling for drag pixmap (could be more sophisticated)
        current_style = self.styleSheet()
        bg_color = QColor("#B0E0E6") # Default drag pixmap bg
        if "background-color:" in current_style:
            try:
                color_str = current_style.split("background-color:")[1].split(";")[0].strip()
                bg_color = QColor(color_str)
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

        # Draw icon and text on pixmap
        icon_pixmap = self.icon().pixmap(QSize(24,24), QIcon.Normal, QIcon.On)
        text_x_offset = 8
        icon_y_offset = (pixmap_size.height() - icon_pixmap.height()) / 2
        if not icon_pixmap.isNull():
            painter.drawPixmap(int(text_x_offset), int(icon_y_offset), icon_pixmap)
            text_x_offset += icon_pixmap.width() + 8

        painter.setPen(self.palette().buttonText().color()) # Use current theme's text color
        painter.setFont(self.font())
        text_rect = QRectF(text_x_offset, 0, pixmap_size.width() - text_x_offset - 5, pixmap_size.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()

        drag.setPixmap(pixmap)
        # hotspot approximately at mouse click relative to top-left
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
        self.setFlags(QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges |
                      QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setPen(self.pen())
        painter.setBrush(self.color)
        painter.drawRoundedRect(self.rect(), 10, 10)

        painter.setPen(self._text_color)
        painter.setFont(self._font)
        text_rect = self.rect().adjusted(8, 8, -8, -8)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)

        if self.is_initial:
            painter.setBrush(Qt.black)
            painter.setPen(QPen(Qt.black, 2))

            marker_radius = 7
            line_length = 20 # Distance of the marker from the state boundary
            # Position initial marker to the left of the state
            start_marker_center_x = self.rect().left() - line_length - marker_radius / 2
            start_marker_center_y = self.rect().center().y()

            # Draw filled circle
            painter.drawEllipse(QPointF(start_marker_center_x, start_marker_center_y), marker_radius, marker_radius)

            # Draw line from circle to state boundary
            line_start_point = QPointF(start_marker_center_x + marker_radius, start_marker_center_y)
            line_end_point = QPointF(self.rect().left(), start_marker_center_y)
            painter.drawLine(line_start_point, line_end_point)

            # Draw arrowhead at state boundary
            arrow_size = 10
            angle_rad = math.atan2(line_end_point.y() - line_start_point.y(), line_end_point.x() - line_start_point.x())

            arrow_p1 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad + math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad + math.pi / 6))
            arrow_p2 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad - math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad - math.pi / 6))

            painter.setBrush(Qt.black) # Solid arrow
            painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))

        if self.is_final:
            painter.setPen(QPen(Qt.black, 2))
            # Draw an inner circle (or rounded rect) inside the state for final state indication
            inner_rect = self.rect().adjusted(6, 6, -6, -6) # Make it smaller than the state
            painter.drawRoundedRect(inner_rect, 7, 7) # Adjust corner radius as needed

        if self.isSelected():
            pen = QPen(QColor(0, 100, 255, 200), 2.5, Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            selection_rect = self.boundingRect().adjusted(-1,-1,1,1) # Slightly outside for visibility
            painter.drawRoundedRect(selection_rect, 11, 11)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self) # Signal scene that item moved
        return super().itemChange(change, value)

    def get_data(self):
        return {
            'name': self.text_label, 'x': self.x(), 'y': self.y(),
            'width': self.rect().width(), 'height': self.rect().height(),
            'is_initial': self.is_initial, 'is_final': self.is_final,
            'color': self.color.name() if self.color else QColor(190, 220, 255).name(), # Provide default if None
            'entry_action': self.entry_action,
            'during_action': self.during_action,
            'exit_action': self.exit_action,
            'description': self.description
        }

    def set_text(self, text): # Renamed for clarity, used internally mostly
        if self.text_label != text:
            self.prepareGeometryChange()
            self.text_label = text
            self.update()

    def set_properties(self, name, is_initial, is_final, color_hex=None,
                       entry="", during="", exit_a="", desc=""):
        changed = False
        if self.text_label != name:
            self.text_label = name; changed = True
        if self.is_initial != is_initial:
            self.is_initial = is_initial; changed = True
        if self.is_final != is_final:
            self.is_final = is_final; changed = True

        new_color = QColor(color_hex) if color_hex else QColor(190, 220, 255)
        if self.color != new_color:
            self.color = new_color
            self.setBrush(self.color) # Update brush immediately
            changed = True

        if self.entry_action != entry: self.entry_action = entry; changed = True
        if self.during_action != during: self.during_action = during; changed = True
        if self.exit_action != exit_a: self.exit_action = exit_a; changed = True
        if self.description != desc: self.description = desc; changed = True

        if changed:
            self.prepareGeometryChange() # Important if text changes affect bounding rect
            self.update() # Redraw the item

class GraphicsTransitionItem(QGraphicsPathItem):
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type

    def __init__(self, start_item, end_item, event_str="", condition_str="", action_str="",
                 color=None, description=""):
        super().__init__()
        self.start_item = start_item
        self.end_item = end_item

        self.event_str = event_str
        self.condition_str = condition_str
        self.action_str = action_str

        self.color = QColor(color) if color else QColor(0, 120, 120) # Default dark teal
        self.description = description

        self.arrow_size = 12
        self._text_color = QColor(30, 30, 30)
        self._font = QFont("Arial", 9)
        self.control_point_offset = QPointF(0,0) # (perpendicular, tangential)

        self.setPen(QPen(self.color, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1)
        self.setAcceptHoverEvents(True)
        self.update_path()

    def _compose_label_string(self):
        parts = []
        if self.event_str: parts.append(self.event_str)
        if self.condition_str: parts.append(f"[{self.condition_str}]")
        if self.action_str: parts.append(f"/{{{self.action_str}}}")
        return " ".join(parts)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent):
        self.setPen(QPen(self.color.lighter(120), 3)) # Make it slightly lighter/brighter on hover
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent):
        self.setPen(QPen(self.color, 2.5))
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 25 # Nominal padding
        path_bounds = self.path().boundingRect()
        # Consider text bounding rect if text is visible
        current_label = self._compose_label_string()
        if current_label:
            fm = QFontMetrics(self._font)
            text_rect = fm.boundingRect(current_label)
            # Estimate text area based on mid-point of path for rough union
            mid_point_on_path = self.path().pointAtPercent(0.5)
            text_render_rect = QRectF(mid_point_on_path.x() - text_rect.width() - 10,
                                     mid_point_on_path.y() - text_rect.height() - 10,
                                     text_rect.width()*2 + 20, text_rect.height()*2 + 20) # Generous area
            path_bounds = path_bounds.united(text_render_rect)
        return path_bounds.adjusted(-extra, -extra, extra, extra)

    def shape(self): # For collision detection (selection)
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(18 + self.pen().widthF()) # Make it wider for easier selection
        path_stroker.setCapStyle(Qt.RoundCap)
        path_stroker.setJoinStyle(Qt.RoundJoin)
        return path_stroker.createStroke(self.path())

    def update_path(self):
        if not self.start_item or not self.end_item:
            self.setPath(QPainterPath()) # Clear path if items are invalid
            return

        start_center = self.start_item.sceneBoundingRect().center()
        end_center = self.end_item.sceneBoundingRect().center()

        # Line from start_center to end_center for intersection calculation
        line_to_target = QLineF(start_center, end_center)

        start_point = self._get_intersection_point(self.start_item, line_to_target)
        # Line from end_center to start_center for intersection at end_item
        line_from_target = QLineF(end_center, start_center)
        end_point = self._get_intersection_point(self.end_item, line_from_target)

        # Fallback if intersection points are not found (e.g., items are too small or overlapping)
        if start_point is None: start_point = start_center
        if end_point is None: end_point = end_center

        path = QPainterPath(start_point)

        if self.start_item == self.end_item: # Self-loop
            # Define points for a bezier curve loop above the state
            rect = self.start_item.sceneBoundingRect()
            loop_radius_x = rect.width() * 0.45 # Proportional to state size
            loop_radius_y = rect.height() * 0.45

            # Anchor points on the state's top edge, slightly offset from center
            p1 = QPointF(rect.center().x() + loop_radius_x * 0.3, rect.top())
            p2 = QPointF(rect.center().x() - loop_radius_x * 0.3, rect.top())

            # Control points for the curve, placed above the state
            ctrl1 = QPointF(rect.center().x() + loop_radius_x * 1.5, rect.top() - loop_radius_y * 3.0)
            ctrl2 = QPointF(rect.center().x() - loop_radius_x * 1.5, rect.top() - loop_radius_y * 3.0)

            path.moveTo(p1)
            path.cubicTo(ctrl1, ctrl2, p2)
            end_point = p2 # For arrow drawing logic
        else: # Transition between different states
            mid_x = (start_point.x() + end_point.x()) / 2
            mid_y = (start_point.y() + end_point.y()) / 2

            # Vector from start to end
            dx = end_point.x() - start_point.x()
            dy = end_point.y() - start_point.y()
            length = math.hypot(dx, dy)
            if length == 0: length = 1 # Avoid division by zero

            # Normalized perpendicular vector (rotated 90 deg counter-clockwise)
            perp_x = -dy / length
            perp_y = dx / length

            # Calculate control point for quadratic bezier
            # self.control_point_offset.x() is perpendicular offset
            # self.control_point_offset.y() is tangential offset (along the line between states)
            ctrl_pt_x = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y()
            ctrl_pt_y = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()

            ctrl_pt = QPointF(ctrl_pt_x, ctrl_pt_y)

            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0:
                 path.lineTo(end_point) # Straight line if no offset
            else:
                 path.quadTo(ctrl_pt, end_point) # Curved line

        self.setPath(path)
        self.prepareGeometryChange() # Notify Qt that bounding rect might change

    def _get_intersection_point(self, item: QGraphicsRectItem, line: QLineF):
        item_rect = item.sceneBoundingRect() # Use scene bounding rect for accurate position

        # Create lines for each edge of the item's bounding rect
        edges = [
            QLineF(item_rect.topLeft(), item_rect.topRight()),      # Top
            QLineF(item_rect.topRight(), item_rect.bottomRight()),  # Right
            QLineF(item_rect.bottomRight(), item_rect.bottomLeft()),# Bottom
            QLineF(item_rect.bottomLeft(), item_rect.topLeft())     # Left
        ]

        intersect_points = []
        for edge in edges:
            intersection_point_var = QPointF()
            # Use intersect method, check for bounded intersection
            intersect_type = line.intersect(edge, intersection_point_var)

            if intersect_type == QLineF.BoundedIntersection:
                # Double check point is on the segment of 'edge' due to floating point math.
                # This is often implicit in BoundedIntersection but doesn't hurt.
                edge_rect_for_check = QRectF(edge.p1(), edge.p2()).normalized()
                epsilon = 1e-3 # Small tolerance
                if (edge_rect_for_check.left() - epsilon <= intersection_point_var.x() <= edge_rect_for_check.right() + epsilon and
                    edge_rect_for_check.top() - epsilon <= intersection_point_var.y() <= edge_rect_for_check.bottom() + epsilon):
                    intersect_points.append(QPointF(intersection_point_var)) # Store a copy

        if not intersect_points:
            return item_rect.center() # Fallback if no intersection found

        # Find the intersection point closest to the start of the 'line' (line.p1())
        # This is typically the "entry" point of the line into the item.
        closest_point = intersect_points[0]
        min_dist_sq = (QLineF(line.p1(), closest_point).length())**2
        for pt in intersect_points[1:]:
            dist_sq = (QLineF(line.p1(), pt).length())**2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_point = pt
        return closest_point


    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty():
            return

        painter.setRenderHint(QPainter.Antialiasing)
        current_pen = self.pen() # Use the pen set by hover/selection status

        if self.isSelected():
            # Draw a wider, translucent path underneath for selection indication
            stroker = QPainterPathStroker()
            stroker.setWidth(current_pen.widthF() + 8) # Make it noticeably wider
            stroker.setCapStyle(Qt.RoundCap)
            stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path())
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0,100,255,60)) # Translucent blue for selection
            painter.drawPath(selection_path_shape)

        painter.setPen(current_pen) # Restore/set current pen for actual line
        painter.setBrush(Qt.NoBrush) # Transitions are not filled
        painter.drawPath(self.path())

        # Arrowhead drawing
        if self.path().elementCount() < 1 : return # Path must exist

        # Point and angle at the end of the path for arrow
        percent_at_end = 0.999 # Almost at the very end
        if self.path().length() < 1: percent_at_end = 0.9 # Shorter path adjustment

        line_end_point = self.path().pointAtPercent(1.0)
        # Angle is in degrees, clockwise from horizontal. Convert to radians and adjust.
        angle_at_end_rad = -self.path().angleAtPercent(percent_at_end) * (math.pi / 180.0)

        # Calculate arrowhead points
        arrow_p1 = line_end_point + QPointF(math.cos(angle_at_end_rad - math.pi / 6) * self.arrow_size,
                                           math.sin(angle_at_end_rad - math.pi / 6) * self.arrow_size)
        arrow_p2 = line_end_point + QPointF(math.cos(angle_at_end_rad + math.pi / 6) * self.arrow_size,
                                           math.sin(angle_at_end_rad + math.pi / 6) * self.arrow_size)

        painter.setBrush(current_pen.color()) # Fill arrow with line color
        painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))

        # Text Label
        current_label = self._compose_label_string()
        if current_label:
            painter.setFont(self._font)
            fm = QFontMetrics(self._font)
            text_rect_original = fm.boundingRect(current_label)

            # Position text near midpoint of the path
            text_pos_on_path = self.path().pointAtPercent(0.5)
            angle_at_mid_deg = self.path().angleAtPercent(0.5) # Angle for offsetting text

            # Offset text perpendicular to the path line for better readability
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0) # -90 for upward offset
            offset_dist = 12 # pixels away from the line

            text_center_x = text_pos_on_path.x() + offset_dist * math.cos(offset_angle_rad)
            text_center_y = text_pos_on_path.y() + offset_dist * math.sin(offset_angle_rad)

            text_final_pos = QPointF(text_center_x - text_rect_original.width() / 2,
                                     text_center_y - text_rect_original.height() / 2)

            # Optional: Draw a semi-transparent background for the text
            bg_padding = 3
            bg_rect = QRectF(text_final_pos.x() - bg_padding,
                             text_final_pos.y() - bg_padding,
                             text_rect_original.width() + 2 * bg_padding,
                             text_rect_original.height() + 2 * bg_padding)

            painter.setBrush(QColor(250, 250, 250, 200)) # Light, semi-transparent background
            painter.setPen(QPen(QColor(200,200,200,150), 0.5)) # Faint border for the background
            painter.drawRoundedRect(bg_rect, 4, 4)

            painter.setPen(self._text_color) # Text color
            painter.drawText(text_final_pos, current_label)

    def get_data(self):
        return {
            'source': self.start_item.text_label if self.start_item else "None",
            'target': self.end_item.text_label if self.end_item else "None",
            'event': self.event_str,
            'condition': self.condition_str,
            'action': self.action_str,
            'color': self.color.name() if self.color else QColor(0,120,120).name(),
            'description': self.description,
            'control_offset_x': self.control_point_offset.x(),
            'control_offset_y': self.control_point_offset.y()
        }

    def set_properties(self, event_str="", condition_str="", action_str="",
                       color_hex=None, description="", offset=None):
        changed = False
        if self.event_str != event_str: self.event_str = event_str; changed=True
        if self.condition_str != condition_str: self.condition_str = condition_str; changed=True
        if self.action_str != action_str: self.action_str = action_str; changed=True
        if self.description != description: self.description = description; changed=True

        new_color = QColor(color_hex) if color_hex else QColor(0, 120, 120)
        if self.color != new_color:
            self.color = new_color
            self.setPen(QPen(self.color, self.pen().widthF())) # Update pen color
            changed = True

        if offset is not None and self.control_point_offset != offset:
            self.control_point_offset = offset
            changed = True # Path will be updated below

        if changed:
            self.prepareGeometryChange()
            if offset is not None : self.update_path() # if offset changed, path needs full recalc
            self.update()

    def set_control_point_offset(self, offset: QPointF): # For external use by edit dialog
        if self.control_point_offset != offset:
            self.control_point_offset = offset
            self.update_path()
            self.update()

class GraphicsCommentItem(QGraphicsTextItem):
    Type = QGraphicsItem.UserType + 3
    def type(self): return GraphicsCommentItem.Type

    def __init__(self, x, y, text="Comment"):
        super().__init__()
        self.setPlainText(text)
        self.setPos(x, y)
        self.setFont(QFont("Arial", 10))
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlags(QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges |
                      QGraphicsItem.ItemIsFocusable)

        self._default_width = 150
        self._default_height = 60 # Approximate, will adjust to text
        self.setTextWidth(self._default_width)
        self.adjust_size_to_text()


        self.border_pen = QPen(QColor(204, 204, 153), 1.5) # Khaki-ish
        self.background_brush = QBrush(QColor(255, 255, 224, 200)) # Light yellow, semi-transparent

    def paint(self, painter, option, widget):
        # Draw a background rectangle
        painter.setPen(self.border_pen)
        painter.setBrush(self.background_brush)
        painter.drawRoundedRect(self.boundingRect().adjusted(0.5,0.5,-0.5,-0.5), 5, 5)
        super().paint(painter, option, widget) # Draw the text itself

        if self.isSelected():
            pen = QPen(Qt.blue, 1.5, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())

    def get_data(self):
        return {
            'text': self.toPlainText(),
            'x': self.x(), 'y': self.y(),
            'width': self.boundingRect().width(), # Use current width
        }

    def set_properties(self, text, width=None): # Used by undo command
        self.setPlainText(text)
        if width: self.setTextWidth(width)
        else: self.adjust_size_to_text()
        self.update()

    def adjust_size_to_text(self):
        # Simple auto-height adjustment, width is mostly fixed by user or default
        doc_height = self.document().size().height()
        current_rect = self.boundingRect()
        if abs(doc_height - current_rect.height()) > 5: # Only adjust if significant change
            # self.setTextWidth forces recalculation of height, this is a bit manual
            # For QGraphicsTextItem, height usually adjusts with text content and fixed width.
            # No explicit setHeight. BoundingRect should update.
            self.prepareGeometryChange() # Important
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)


# --- Undo Commands ---
class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item_instance = item # Keep the instance
        # Store data needed to recreate/relink if the instance cannot be simply added back
        if isinstance(item, GraphicsTransitionItem):
            self.item_data = item.get_data() # Full data
            # References for relinking
            self.start_item_name = item.start_item.text_label if item.start_item else None
            self.end_item_name = item.end_item.text_label if item.end_item else None
        elif isinstance(item, GraphicsStateItem) or isinstance(item, GraphicsCommentItem):
            self.item_data = item.get_data() # Store all serializable properties

    def redo(self):
        # If the item_instance already exists (e.g. first redo, or if it was never fully removed)
        if self.item_instance.scene() is None:
            self.scene.addItem(self.item_instance)

        # Ensure transitions are correctly linked if they were unlinked
        if isinstance(self.item_instance, GraphicsTransitionItem):
            start_node = self.scene.get_state_by_name(self.start_item_name)
            end_node = self.scene.get_state_by_name(self.end_item_name)
            if start_node and end_node:
                self.item_instance.start_item = start_node
                self.item_instance.end_item = end_node
                # Properties like text, color, offset etc should already be on item_instance
                self.item_instance.set_properties(
                    event_str=self.item_data['event'],
                    condition_str=self.item_data['condition'],
                    action_str=self.item_data['action'],
                    color_hex=self.item_data.get('color'),
                    description=self.item_data.get('description', ""),
                    offset=QPointF(self.item_data['control_offset_x'], self.item_data['control_offset_y'])
                )
                self.item_instance.update_path()
            else:
                # This case should ideally be handled if item_instance couldn't be re-added directly
                self.scene.log_function(f"Error (Redo Add Transition): Could not link transition. State(s) missing for '{self.item_data.get('event', 'Unnamed Transition')}'.")

        self.scene.clearSelection()
        self.item_instance.setSelected(True)
        self.scene.set_dirty(True)

    def undo(self):
        self.scene.removeItem(self.item_instance)
        # No need to delete self.item_instance, it will be re-added on redo
        self.scene.set_dirty(True)

class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items_to_remove, description="Remove Items"):
        super().__init__(description)
        self.scene = scene
        self.removed_items_data = [] # Stores full data for reconstruction
        # Also keep direct references for quick redo/undo toggling if items are not complex to restore
        self.item_instances_for_quick_toggle = list(items_to_remove)

        for item in items_to_remove:
            item_data_entry = item.get_data() # Gets all serializable properties
            item_data_entry['_type'] = item.type()
            if isinstance(item, GraphicsTransitionItem):
                 item_data_entry['_start_name'] = item.start_item.text_label if item.start_item else None
                 item_data_entry['_end_name'] = item.end_item.text_label if item.end_item else None
            self.removed_items_data.append(item_data_entry)

    def redo(self): # Actually remove items
        for item_instance in self.item_instances_for_quick_toggle:
            if item_instance.scene() == self.scene: # Check if it's still in the scene
                self.scene.removeItem(item_instance)
        self.scene.set_dirty(True)

    def undo(self): # Re-add items
        newly_re_added_instances = []
        # Map for relinking transitions after all states are restored
        states_map_for_undo = {}

        # First pass: restore states and comments
        for item_data in self.removed_items_data:
            instance_to_add = None
            if item_data['_type'] == GraphicsStateItem.Type:
                state = GraphicsStateItem(
                    item_data['x'], item_data['y'], item_data['width'], item_data['height'],
                    item_data['name'], item_data['is_initial'], item_data['is_final'],
                    item_data.get('color'), item_data.get('entry_action', ""),
                    item_data.get('during_action', ""), item_data.get('exit_action', ""),
                    item_data.get('description', "")
                )
                instance_to_add = state
                states_map_for_undo[state.text_label] = state # Store for transition linking
            elif item_data['_type'] == GraphicsCommentItem.Type:
                comment = GraphicsCommentItem(item_data['x'], item_data['y'], item_data['text'])
                comment.setTextWidth(item_data.get('width', 150))
                instance_to_add = comment

            if instance_to_add:
                self.scene.addItem(instance_to_add)
                newly_re_added_instances.append(instance_to_add)

        # Second pass: restore transitions
        for item_data in self.removed_items_data:
            if item_data['_type'] == GraphicsTransitionItem.Type:
                src_item = states_map_for_undo.get(item_data['_start_name'])
                tgt_item = states_map_for_undo.get(item_data['_end_name'])
                if src_item and tgt_item:
                    trans = GraphicsTransitionItem(src_item, tgt_item,
                                                   event_str=item_data['event'],
                                                   condition_str=item_data['condition'],
                                                   action_str=item_data['action'],
                                                   color=item_data.get('color'),
                                                   description=item_data.get('description',"")
                                                   )
                    trans.set_control_point_offset(QPointF(item_data['control_offset_x'], item_data['control_offset_y']))
                    self.scene.addItem(trans)
                    newly_re_added_instances.append(trans)
                else:
                    self.scene.log_function(f"Error (Undo Remove): Could not re-link transition. States '{item_data['_start_name']}' or '{item_data['_end_name']}' missing.")

        self.item_instances_for_quick_toggle = newly_re_added_instances # Update references
        self.scene.set_dirty(True)

class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_and_new_positions, description="Move Items"):
        super().__init__(description)
        # items_and_new_positions is a list of (item_instance, new_QPointF_pos)
        self.items_and_new_positions = items_and_new_positions
        self.items_and_old_positions = []
        self.scene_ref = None # To call update on connected transitions

        if self.items_and_new_positions: # Ensure there are items
            # All items should belong to the same scene
            self.scene_ref = self.items_and_new_positions[0][0].scene()
            for item, _ in self.items_and_new_positions:
                self.items_and_old_positions.append((item, item.pos())) # Store current pos as old_pos

    def _apply_positions(self, positions_list):
        if not self.scene_ref: return
        for item, pos in positions_list:
            item.setPos(pos) # Move the item
            # If state moved, update its transitions
            if isinstance(item, GraphicsStateItem):
                 self.scene_ref._update_connected_transitions(item)
        self.scene_ref.update() # Redraw relevant parts of the scene
        self.scene_ref.set_dirty(True)

    def redo(self): self._apply_positions(self.items_and_new_positions)
    def undo(self): self._apply_positions(self.items_and_old_positions)

class EditItemPropertiesCommand(QUndoCommand):
    def __init__(self, item, old_props_data, new_props_data, description="Edit Properties"):
        super().__init__(description)
        self.item = item # Direct reference to the QGraphicsItem instance
        self.old_props_data = old_props_data # Dict from item.get_data()
        self.new_props_data = new_props_data # Dict from dialog
        self.scene_ref = item.scene()

    def _apply_properties(self, props_to_apply):
        if not self.item or not self.scene_ref: return

        original_name_if_state = None # Used for renaming states and updating transitions

        if isinstance(self.item, GraphicsStateItem):
            original_name_if_state = self.item.text_label # Before changing it
            self.item.set_properties(
                props_to_apply['name'],
                props_to_apply.get('is_initial', False),
                props_to_apply.get('is_final', False),
                props_to_apply.get('color'),
                props_to_apply.get('entry_action', ""),
                props_to_apply.get('during_action', ""),
                props_to_apply.get('exit_action', ""),
                props_to_apply.get('description', "")
            )
            # If state name changed, transitions pointing to it need to be aware (mostly for data model, visual update happens via item.update())
            if original_name_if_state != props_to_apply['name']:
                self.scene_ref._update_transitions_for_renamed_state(original_name_if_state, props_to_apply['name'])

        elif isinstance(self.item, GraphicsTransitionItem):
            self.item.set_properties(
                event_str=props_to_apply.get('event',""),
                condition_str=props_to_apply.get('condition',""),
                action_str=props_to_apply.get('action',""),
                color_hex=props_to_apply.get('color'),
                description=props_to_apply.get('description',""),
                offset=QPointF(props_to_apply['control_offset_x'], props_to_apply['control_offset_y'])
            )

        elif isinstance(self.item, GraphicsCommentItem):
            self.item.set_properties(
                text=props_to_apply['text'],
                width=props_to_apply.get('width')
            )

        self.item.update() # Redraw the item itself
        self.scene_ref.update() # Redraw scene (might be needed if bounding box changed significantly)
        self.scene_ref.set_dirty(True)

    def redo(self): self._apply_properties(self.new_props_data)
    def undo(self): self._apply_properties(self.old_props_data)

# --- Diagram Scene ---
class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool) # Emitted when diagram is modified

    def __init__(self, undo_stack, parent_window=None): # parent_window is typically MainWindow
        super().__init__(parent_window) # Pass parent for context (e.g., for dialogs)
        self.parent_window = parent_window
        self.setSceneRect(0, 0, 5000, 4000) # Large canvas size
        self.current_mode = "select" # Default mode
        self.transition_start_item = None
        self.log_function = print # Default log, can be overridden
        self.undo_stack = undo_stack
        self._dirty = False # Tracks if diagram has unsaved changes
        self._mouse_press_items_positions = {} # For tracking moves for undo command
        self._temp_transition_line = None # Visual aid for drawing transitions

        # Connect item movement signal to handler
        self.item_moved.connect(self._handle_item_moved)

        # Grid settings
        self.grid_size = 20
        self.grid_pen_light = QPen(QColor(225, 225, 225), 0.8, Qt.SolidLine) # Lighter grid dots/lines
        self.grid_pen_dark = QPen(QColor(200, 200, 200), 1.0, Qt.SolidLine)  # Darker major grid lines
        self.setBackgroundBrush(QColor(248, 248, 248)) # Light gray background

        self.snap_to_grid_enabled = True # Toggleable snapping feature

    def _update_connected_transitions(self, state_item: GraphicsStateItem):
        # When a state item moves, redraw all transitions connected to it
        for item in self.items(): # Iterate through all items in the scene
            if isinstance(item, GraphicsTransitionItem):
                if item.start_item == state_item or item.end_item == state_item:
                    item.update_path() # Recalculate and redraw the transition path

    def _update_transitions_for_renamed_state(self, old_name:str, new_name:str):
        # This is primarily for ensuring data model integrity if names are critical (e.g., in get_data())
        # Visual updates of transitions (if any text based on state names) would happen via their own update mechanisms.
        # For now, our transition get_data relies on actual item text_label, so this isn't strictly needed for save/load yet.
        # However, it's good practice if inter-item references might use names.
        self.log_function(f"State '{old_name}' renamed to '{new_name}'. Dependent transitions may need data update if name was key.")


    def get_state_by_name(self, name: str):
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name:
                return item
        return None

    def set_dirty(self, dirty=True):
        if self._dirty != dirty:
            self._dirty = dirty
            self.modifiedStatusChanged.emit(dirty) # Signal main window
            if self.parent_window: # To update save actions enable state, window title etc.
                self.parent_window._update_save_actions_enable_state()

    def is_dirty(self):
        return self._dirty

    def set_log_function(self, log_function):
        self.log_function = log_function

    def set_mode(self, mode: str):
        old_mode = self.current_mode
        if old_mode == mode: return # No change

        self.current_mode = mode
        self.log_function(f"Interaction mode changed to: {mode}")

        # Reset transition drawing state if mode changes
        self.transition_start_item = None
        if self._temp_transition_line:
            self.removeItem(self._temp_transition_line)
            self._temp_transition_line = None

        # Change cursor and item movability based on mode
        if mode == "select":
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            for item in self.items(): # Make states movable again
                if isinstance(item, GraphicsStateItem): item.setFlag(QGraphicsItem.ItemIsMovable, True)
                if isinstance(item, GraphicsCommentItem): item.setFlag(QGraphicsItem.ItemIsMovable, True)
        elif mode == "state" or mode == "comment": # For adding new states or comments
            QApplication.setOverrideCursor(Qt.CrossCursor)
            for item in self.items(): # Make existing items not movable during add mode
                 if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): item.setFlag(QGraphicsItem.ItemIsMovable, False)
        elif mode == "transition":
            QApplication.setOverrideCursor(Qt.PointingHandCursor) # Indicates clickable items
            for item in self.items(): # Make existing items not movable
                 if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): item.setFlag(QGraphicsItem.ItemIsMovable, False)

        # Restore default cursor if leaving a mode that set an override
        if old_mode in ["state", "transition", "comment"] and mode not in ["state", "transition", "comment"]:
            QApplication.restoreOverrideCursor()

        # Ensure corresponding toolbar action is checked
        if self.parent_window:
            if mode == "select" and self.parent_window.select_mode_action.isChecked() is False:
                self.parent_window.select_mode_action.setChecked(True)
            elif mode == "state" and self.parent_window.add_state_mode_action.isChecked() is False:
                self.parent_window.add_state_mode_action.setChecked(True)
            elif mode == "transition" and self.parent_window.add_transition_mode_action.isChecked() is False:
                self.parent_window.add_transition_mode_action.setChecked(True)
            elif mode == "comment" and self.parent_window.add_comment_mode_action.isChecked() is False:
                self.parent_window.add_comment_mode_action.setChecked(True)


    def select_all(self):
        for item in self.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable:
                item.setSelected(True)

    def _handle_item_moved(self, moved_item):
        # This is connected to item_moved signal from GraphicsItem instances
        if isinstance(moved_item, GraphicsStateItem):
            self._update_connected_transitions(moved_item)
            # Snapping handled in mouseReleaseEvent when move command is finalized
            if self.snap_to_grid_enabled and self._mouse_press_items_positions:
                pass # Actual snapping applied later
        elif isinstance(moved_item, GraphicsCommentItem):
            if self.snap_to_grid_enabled and self._mouse_press_items_positions:
                pass # Actual snapping applied later

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos()
        items_at_pos = self.items(pos)
        # Prioritize StateItem for clicks
        top_item_at_pos = next((item for item in items_at_pos if isinstance(item, GraphicsStateItem)), None)
        if not top_item_at_pos: # If no state, check for comment or then any other
            top_item_at_pos = next((item for item in items_at_pos if isinstance(item, (GraphicsCommentItem, GraphicsTransitionItem))), None)
            if not top_item_at_pos and items_at_pos: top_item_at_pos = items_at_pos[0]


        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size - 60 # Approx center on grid for 120 width
                grid_y = round(pos.y() / self.grid_size) * self.grid_size - 30 # Approx center for 60 height
                self._add_item_interactive(pos, item_type="State") # Generic add item
            elif self.current_mode == "comment":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size
                grid_y = round(pos.y() / self.grid_size) * self.grid_size
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type="Comment")
            elif self.current_mode == "transition":
                if isinstance(top_item_at_pos, GraphicsStateItem): # Must click on a state to start/end
                    self._handle_transition_click(top_item_at_pos, pos)
                else: # Clicked empty space or non-state, cancel current transition drawing
                    self.transition_start_item = None
                    if self._temp_transition_line:
                        self.removeItem(self._temp_transition_line)
                        self._temp_transition_line = None
                    self.log_function("Transition drawing cancelled (clicked empty space/non-state).")
            else: # Select mode or other
                # Store initial positions of selected items for MoveCommand
                self._mouse_press_items_positions.clear()
                selected_movable = [item for item in self.selectedItems() if item.flags() & QGraphicsItem.ItemIsMovable]
                for item in selected_movable:
                     self._mouse_press_items_positions[item] = item.pos() # Store original position
                super().mousePressEvent(event) # Default handling (selection, move prep)

        elif event.button() == Qt.RightButton:
            # Context menu for items
            if top_item_at_pos and isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem)):
                if not top_item_at_pos.isSelected(): # If item under cursor not selected, select it exclusively
                    self.clearSelection()
                    top_item_at_pos.setSelected(True)
                self._show_context_menu(top_item_at_pos, event.screenPos()) # Show menu at screen coords
            else: # Clicked empty space, clear selection (optional, standard behavior usually keeps selection)
                self.clearSelection()
        else: # Other mouse buttons
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        # Update temporary transition line if drawing
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, event.scenePos()))
        else: # Default move handling for selected items
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            if self._mouse_press_items_positions: # If we were tracking item positions for a potential move
                moved_items_data = []
                for item, old_pos in self._mouse_press_items_positions.items():
                    new_pos = item.pos() # Get the final position after Qt's move

                    # Snap to grid if enabled
                    if self.snap_to_grid_enabled:
                        # Snap top-left corner for consistency
                        snapped_x = round(new_pos.x() / self.grid_size) * self.grid_size
                        snapped_y = round(new_pos.y() / self.grid_size) * self.grid_size
                        if new_pos.x() != snapped_x or new_pos.y() != snapped_y:
                            item.setPos(snapped_x, snapped_y) # Apply snap
                            new_pos = QPointF(snapped_x, snapped_y) # Update new_pos with snapped value

                    # Check if item actually moved significantly to warrant an undo command
                    if (new_pos - old_pos).manhattanLength() > 0.1: # Small threshold for float comparison
                        moved_items_data.append((item, new_pos)) # Store item and its new snapped position

                if moved_items_data:
                    # Create a composite move command for all moved items
                    # Note: old_pos was already captured in mousePress; MoveCommand will re-fetch it for robustness.
                    cmd = MoveItemsCommand(moved_items_data) # Pass items and their *new* final positions
                    self.undo_stack.push(cmd)
                self._mouse_press_items_positions.clear() # Clear tracking dict
        super().mouseReleaseEvent(event) # Default release handling

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        items_at_pos = self.items(event.scenePos())
        # Prioritize types for editing
        item_to_edit = next((item for item in items_at_pos if isinstance(item, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem))), None)

        if item_to_edit:
            self.edit_item_properties(item_to_edit)
        else:
            super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, item, global_pos):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background-color: #FAFAFA; border: 1px solid #D0D0D0; }
            QMenu::item { padding: 5px 20px 5px 20px; }
            QMenu::item:selected { background-color: #E0E0E0; color: black; }
            QMenu::separator { height: 1px; background-color: #D0D0D0; margin-left: 5px; margin-right: 5px; }
        """)
        edit_action = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        delete_action = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")

        action = menu.exec_(global_pos)
        if action == edit_action:
            self.edit_item_properties(item)
        elif action == delete_action:
            if not item.isSelected(): # If only one item and right-clicked, ensure it's "the" selected
                self.clearSelection()
                item.setSelected(True)
            self.delete_selected_items() # Operates on all selected items

    def edit_item_properties(self, item):
        old_props = item.get_data() # Get current properties for undo
        dialog_executed_and_accepted = False

        if isinstance(item, GraphicsStateItem):
            dialog = StatePropertiesDialog(parent=self.parent_window, current_properties=old_props)
            if dialog.exec_() == QDialog.Accepted:
                dialog_executed_and_accepted = True
                new_props = dialog.get_properties()
                # Check for name collision BEFORE creating command
                if new_props['name'] != old_props['name'] and self.get_state_by_name(new_props['name']):
                    QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state with the name '{new_props['name']}' already exists.")
                    return # Abort property change
        elif isinstance(item, GraphicsTransitionItem):
            dialog = TransitionPropertiesDialog(parent=self.parent_window, current_properties=old_props)
            if dialog.exec_() == QDialog.Accepted:
                dialog_executed_and_accepted = True
                new_props = dialog.get_properties()
        elif isinstance(item, GraphicsCommentItem):
            dialog = CommentPropertiesDialog(parent=self.parent_window, current_properties=old_props)
            if dialog.exec_() == QDialog.Accepted:
                dialog_executed_and_accepted = True
                new_props = dialog.get_properties()
        else: return # Unknown item type

        if dialog_executed_and_accepted:
            # Ensure all fields from get_data() are preserved or updated in new_props
            # This is important if the dialog doesn't edit all properties (e.g., x,y for state)
            final_new_props = old_props.copy() # Start with old, update with dialog changes
            final_new_props.update(new_props)

            cmd = EditItemPropertiesCommand(item, old_props, final_new_props, f"Edit {type(item).__name__} Properties")
            self.undo_stack.push(cmd)
            item_name_for_log = final_new_props.get('name', final_new_props.get('event', final_new_props.get('text', 'Item')))
            self.log_function(f"Properties updated for: {item_name_for_log}")
        self.update()

    def _add_item_interactive(self, pos: QPointF, item_type: str, name_prefix:str="Item", initial_data:dict=None):
        """ Handles interactive addition of various items (States, Comments) via click or drag-drop. """
        current_item = None
        is_initial_state_from_drag = initial_data.get('is_initial', False) if initial_data else False
        is_final_state_from_drag = initial_data.get('is_final', False) if initial_data else False

        if item_type == "State": # This handles regular, initial, final states based on initial_data
            i = 1
            base_name = name_prefix # Uses name_prefix passed from drop (e.g., "Initial", "Final", "State")
            while self.get_state_by_name(f"{base_name}{i}"): i += 1
            default_name = f"{base_name}{i}"

            state_name_from_input = default_name
            # For click-mode "state", it will not have initial_data, so name is prompted if needed.
            # For drag-drop, initial_data IS present, and a name might not be explicitly asked upfront yet.
            # The StatePropertiesDialog handles the final name input and check.

            initial_dialog_props = {
                'name': state_name_from_input,
                'is_initial': is_initial_state_from_drag,
                'is_final': is_final_state_from_drag,
                # other defaults can be set in StatePropertiesDialog constructor
            }
            if initial_data and 'color' in initial_data: initial_dialog_props['color'] = initial_data['color']
            # ... any other pre-filled properties for specific drag types can go here.


            props_dialog = StatePropertiesDialog(self.parent_window, current_properties=initial_dialog_props, is_new_state=True)

            if props_dialog.exec_() == QDialog.Accepted:
                final_props = props_dialog.get_properties()
                if self.get_state_by_name(final_props['name']) and final_props['name'] != state_name_from_input : # Re-check IF name was changed in dialog
                     QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state named '{final_props['name']}' already exists.")
                     if self.current_mode == "state": self.set_mode("select")
                     return

                current_item = GraphicsStateItem(
                    pos.x(), pos.y(), 120, 60, # Default W,H
                    final_props['name'], final_props['is_initial'], final_props['is_final'],
                    final_props.get('color'), final_props.get('entry_action',""),
                    final_props.get('during_action',""), final_props.get('exit_action',""),
                    final_props.get('description',"")
                )
            else: # User cancelled properties dialog
                if self.current_mode == "state": self.set_mode("select") # Revert mode if it was set for this action
                return

        elif item_type == "Comment":
            initial_text = (initial_data.get('text', "Comment") if initial_data else
                            (name_prefix if name_prefix != "Item" else "Comment"))

            text, ok = QInputDialog.getMultiLineText(self.parent_window, "New Comment", "Enter comment text:", initial_text)
            if ok and text:
                current_item = GraphicsCommentItem(pos.x(), pos.y(), text)
            else:
                if self.current_mode == "comment": self.set_mode("select") # Revert mode if applicable
                return
        else:
            self.log_function(f"Unknown item type for addition: {item_type}")
            return

        if current_item:
            cmd = AddItemCommand(self, current_item, f"Add {item_type}")
            self.undo_stack.push(cmd)
            log_name = current_item.text_label if hasattr(current_item, 'text_label') else current_item.toPlainText()
            self.log_function(f"Added {item_type}: {log_name} at ({pos.x():.0f},{pos.y():.0f})")

        # Revert to select mode after adding an item unless specified otherwise by flow
        if self.current_mode in ["state", "comment"]:
            self.set_mode("select")


    def _handle_transition_click(self, clicked_state_item: GraphicsStateItem, click_pos: QPointF):
        if not self.transition_start_item: # First click: define start of transition
            self.transition_start_item = clicked_state_item
            # Create and add temporary visual line
            if not self._temp_transition_line:
                self._temp_transition_line = QGraphicsLineItem()
                self._temp_transition_line.setPen(QPen(Qt.black, 2, Qt.DashLine))
                self.addItem(self._temp_transition_line)

            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, click_pos)) # Line from start to cursor
            self.log_function(f"Transition started from: {clicked_state_item.text_label}. Click target state.")
        else: # Second click: define end of transition
            if self._temp_transition_line: # Remove temporary line
                self.removeItem(self._temp_transition_line)
                self._temp_transition_line = None

            # Dialog for transition properties (event, condition, action, etc.)
            # Initial properties can be empty or defaults
            initial_props = {
                'event': "", 'condition': "", 'action': "", 'color': None,
                'description':"", 'control_offset_x':0, 'control_offset_y':0
            }
            dialog = TransitionPropertiesDialog(self.parent_window, current_properties=initial_props, is_new_transition=True)

            if dialog.exec_() == QDialog.Accepted:
                props = dialog.get_properties()
                new_transition = GraphicsTransitionItem(
                    self.transition_start_item, clicked_state_item,
                    event_str=props['event'], condition_str=props['condition'], action_str=props['action'],
                    color=props.get('color'), description=props.get('description', "")
                )
                new_transition.set_control_point_offset(QPointF(props['control_offset_x'],props['control_offset_y']))

                cmd = AddItemCommand(self, new_transition, "Add Transition")
                self.undo_stack.push(cmd)
                self.log_function(f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{new_transition._compose_label_string()}]")
            else: # User cancelled properties dialog for transition
                self.log_function("Transition addition cancelled by user.")

            self.transition_start_item = None # Reset for next transition
            self.set_mode("select") # Revert to select mode

    def keyPressEvent(self, event: QKeyEvent):
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
                self.log_function("Transition drawing cancelled by Escape.")
                self.set_mode("select") # Revert to select mode
            elif self.current_mode != "select": # If in any other non-select mode, Esc reverts to select
                 self.set_mode("select")
            else: # In select mode, Esc clears selection
                self.clearSelection()
        else:
            super().keyPressEvent(event)

    def delete_selected_items(self):
        selected = self.selectedItems()
        if not selected: return

        items_to_delete_with_related = set() # Use a set to avoid duplicates
        for item in selected:
            items_to_delete_with_related.add(item)
            # If a state is deleted, also delete transitions connected to it
            if isinstance(item, GraphicsStateItem):
                for scene_item in self.items(): # Check all items in scene
                    if isinstance(scene_item, GraphicsTransitionItem):
                        if scene_item.start_item == item or scene_item.end_item == item:
                            items_to_delete_with_related.add(scene_item)

        if items_to_delete_with_related:
            cmd = RemoveItemsCommand(self, list(items_to_delete_with_related), "Delete Items")
            self.undo_stack.push(cmd)
            self.log_function(f"Queued deletion of {len(items_to_delete_with_related)} item(s).")
            self.clearSelection() # Clear selection after queuing for deletion

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"): # Use a specific MIME type
            event.setAccepted(True)
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        pos = event.scenePos()
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            item_type_data_str = event.mimeData().text() # e.g., "State", "Initial State", "Comment"

            # Snap drop position to grid
            grid_x = round(pos.x() / self.grid_size) * self.grid_size
            grid_y = round(pos.y() / self.grid_size) * self.grid_size
            # Adjust for typical item center if it's a state-like item
            if "State" in item_type_data_str:
                grid_x -= 60 # Center width 120 item
                grid_y -= 30 # Center height 60 item

            initial_props_for_add = {}
            actual_item_type_to_add = "Item" # This will be determined below
            name_prefix_for_add = "Item"

            if item_type_data_str == "State":
                actual_item_type_to_add = "State"
                name_prefix_for_add = "State"
            elif item_type_data_str == "Initial State":
                actual_item_type_to_add = "State" # Still creates a "State" type GraphicsStateItem
                name_prefix_for_add = "Initial"   # Default name prefix for the dialog
                initial_props_for_add['is_initial'] = True
            elif item_type_data_str == "Final State":
                actual_item_type_to_add = "State"
                name_prefix_for_add = "Final"
                initial_props_for_add['is_final'] = True
            elif item_type_data_str == "Comment":
                actual_item_type_to_add = "Comment"
                name_prefix_for_add = "Note" # Used for default name generation

            else:
                self.log_function(f"Unknown item type dropped: {item_type_data_str}")
                event.ignore() # Unknown type
                return

            self._add_item_interactive(QPointF(grid_x, grid_y),
                                     item_type=actual_item_type_to_add,
                                     name_prefix=name_prefix_for_add,
                                     initial_data=initial_props_for_add)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def get_diagram_data(self):
        data = {'states': [], 'transitions': [], 'comments': []} # Added comments
        for item in self.items():
            if isinstance(item, GraphicsStateItem):
                data['states'].append(item.get_data())
            elif isinstance(item, GraphicsTransitionItem):
                if item.start_item and item.end_item: # Ensure valid transition
                    data['transitions'].append(item.get_data())
                else:
                    self.log_function(f"Warning: Skipping save of orphaned/invalid transition: '{item._compose_label_string()}'.")
            elif isinstance(item, GraphicsCommentItem):
                data['comments'].append(item.get_data())
        return data

    def load_diagram_data(self, data):
        self.clear() # Clear existing scene content
        self.set_dirty(False) # Reset dirty flag

        state_items_map = {} # For linking transitions by name

        # Load States
        for state_data in data.get('states', []):
            state_item = GraphicsStateItem(
                state_data['x'], state_data['y'],
                state_data.get('width', 120), state_data.get('height', 60),
                state_data['name'],
                state_data.get('is_initial', False), state_data.get('is_final', False),
                state_data.get('color'),
                state_data.get('entry_action',""), state_data.get('during_action',""),
                state_data.get('exit_action',""), state_data.get('description',"")
            )
            self.addItem(state_item)
            state_items_map[state_data['name']] = state_item

        # Load Transitions
        for trans_data in data.get('transitions', []):
            src_item = state_items_map.get(trans_data['source'])
            tgt_item = state_items_map.get(trans_data['target'])
            if src_item and tgt_item:
                trans_item = GraphicsTransitionItem(
                    src_item, tgt_item,
                    event_str=trans_data.get('event',""),
                    condition_str=trans_data.get('condition',""),
                    action_str=trans_data.get('action',""),
                    color=trans_data.get('color'),
                    description=trans_data.get('description',"")
                )
                trans_item.set_control_point_offset(QPointF(
                    trans_data.get('control_offset_x', 0),
                    trans_data.get('control_offset_y', 0)
                ))
                self.addItem(trans_item)
            else:
                label_info = trans_data.get('event', '') + trans_data.get('condition', '') + trans_data.get('action', '')
                self.log_function(f"Warning (Load): Could not link transition '{label_info}' due to missing states: Source='{trans_data['source']}', Target='{trans_data['target']}'.")

        # Load Comments
        for comment_data in data.get('comments', []):
            comment_item = GraphicsCommentItem(
                comment_data['x'], comment_data['y'], comment_data.get('text', "")
            )
            comment_item.setTextWidth(comment_data.get('width', 150)) # Set width if stored
            self.addItem(comment_item)

        self.set_dirty(False) # Still not dirty after load
        self.undo_stack.clear() # Clear undo stack for new file

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect) # Draws the basic background brush

        # Get the visible area from the view
        # This ensures we only draw grid for what's currently visible, improving performance
        view_rect = self.views()[0].viewport().rect() if self.views() else rect
        visible_scene_rect = self.views()[0].mapToScene(view_rect).boundingRect() if self.views() else rect

        left = int(visible_scene_rect.left())
        right = int(visible_scene_rect.right())
        top = int(visible_scene_rect.top())
        bottom = int(visible_scene_rect.bottom())

        # Align grid start to current view, not absolute (0,0) of scene
        first_left = left - (left % self.grid_size)
        first_top = top - (top % self.grid_size)

        # Draw minor grid lines
        painter.setPen(self.grid_pen_light)
        for x in range(first_left, right, self.grid_size):
            # Only draw lines if not on a major grid line
            if x % (self.grid_size * 5) != 0:
                painter.drawLine(x, top, x, bottom) # Vertical light lines
        for y in range(first_top, bottom, self.grid_size):
            if y % (self.grid_size * 5) != 0:
                 painter.drawLine(left, y, right, y) # Horizontal light lines


        # Draw major grid lines (darker)
        major_grid_size = self.grid_size * 5
        first_major_left = left - (left % major_grid_size)
        first_major_top = top - (top % major_grid_size)

        painter.setPen(self.grid_pen_dark) # Use darker pen for major lines
        for x in range(first_major_left, right, major_grid_size):
            painter.drawLine(x, top, x, bottom)
        for y in range(first_major_top, bottom, major_grid_size):
            painter.drawLine(left, y, right, y)


# --- Zoomable Graphics View ---
class ZoomableView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag) # For selecting multiple items
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate) # Optimize updates
        self.zoom_level = 0 # Tracks zoom steps

        # Anchor zoom/resize behavior
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

        # Panning state
        self._is_panning_with_space = False # Spacebar panning
        self._is_panning_with_mouse_button = False # Middle mouse button panning
        self._last_pan_point = QPoint()

    def wheelEvent(self, event: QWheelEvent):
        # Zoom with Ctrl + Mouse Wheel
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.12 if delta > 0 else 1 / 1.12

            # Limit zoom levels to prevent excessive scaling
            new_zoom_level = self.zoom_level + (1 if delta > 0 else -1)
            if -15 <= new_zoom_level <= 25: # Min/max zoom levels
                self.scale(factor, factor)
                self.zoom_level = new_zoom_level
            event.accept() # Consume the event
        else: # Default wheel event (scrolling)
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = True
            self._last_pan_point = event.pos() # Mouse position within view
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal: # Zoom in
            self.scale(1.12, 1.12); self.zoom_level +=1
        elif event.key() == Qt.Key_Minus: # Zoom out
            self.scale(1/1.12, 1/1.12); self.zoom_level -=1
        elif event.key() == Qt.Key_0 or event.key() == Qt.Key_Asterisk: # Reset zoom
             self.resetTransform() # Resets matrix to identity
             self.zoom_level = 0
        else: # Pass other key events to scene or parent
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = False
            # Restore cursor based on current scene mode if not also panning with mouse button
            if not self._is_panning_with_mouse_button:
                self._restore_cursor_to_scene_mode()
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        # Panning with Middle Mouse Button OR Left Mouse Button if Space is held
        if event.button() == Qt.MiddleButton or \
           (self._is_panning_with_space and event.button() == Qt.LeftButton):
            self._last_pan_point = event.pos() # Record press position
            self.setCursor(Qt.ClosedHandCursor)
            self._is_panning_with_mouse_button = True
            event.accept() # Consume event for panning
        else: # Other mouse presses for selection, item interaction
            self._is_panning_with_mouse_button = False
            super().mousePressEvent(event) # Let scene handle it

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button:
            delta_view = event.pos() - self._last_pan_point # Difference in view coordinates
            self._last_pan_point = event.pos()

            # Pan the view by adjusting scrollbar values
            hsbar = self.horizontalScrollBar()
            vsbar = self.verticalScrollBar()
            hsbar.setValue(hsbar.value() - delta_view.x())
            vsbar.setValue(vsbar.value() - delta_view.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        # Releasing middle mouse or left mouse (if space was held) during panning
        if self._is_panning_with_mouse_button and \
           (event.button() == Qt.MiddleButton or (self._is_panning_with_space and event.button() == Qt.LeftButton)):

            self._is_panning_with_mouse_button = False # Stop mouse button panning
            # If space is still held, revert to OpenHand, otherwise to scene mode cursor
            if self._is_panning_with_space:
                self.setCursor(Qt.OpenHandCursor)
            else:
                self._restore_cursor_to_scene_mode()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _restore_cursor_to_scene_mode(self):
        """Sets cursor based on the current mode of the scene."""
        current_scene_mode = self.scene().current_mode if self.scene() else "select"
        if current_scene_mode == "select": self.setCursor(Qt.ArrowCursor)
        elif current_scene_mode == "state" or current_scene_mode == "comment": self.setCursor(Qt.CrossCursor)
        elif current_scene_mode == "transition": self.setCursor(Qt.PointingHandCursor)
        else: self.setCursor(Qt.ArrowCursor) # Default fallback


# --- Dialogs ---
class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Props"))

        layout = QFormLayout(self)
        layout.setSpacing(10)

        # Defaults or from current_properties
        p = current_properties or {}
        self.name_edit = QLineEdit(p.get('name', "StateName"))
        self.name_edit.setPlaceholderText("Unique name for the state")

        self.is_initial_cb = QCheckBox("Is Initial State")
        self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Is Final State")
        self.is_final_cb.setChecked(p.get('is_final', False))

        self.color_button = QPushButton("Choose Color...")
        self.current_color = QColor(p.get('color', "#BEDFFF")) # Default state color
        self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)

        self.entry_action_edit = QTextEdit(p.get('entry_action', ""))
        self.entry_action_edit.setFixedHeight(60)
        self.entry_action_edit.setPlaceholderText("MATLAB code; e.g., output=1;")
        self.during_action_edit = QTextEdit(p.get('during_action', ""))
        self.during_action_edit.setFixedHeight(60)
        self.during_action_edit.setPlaceholderText("MATLAB code executed while in state")
        self.exit_action_edit = QTextEdit(p.get('exit_action', ""))
        self.exit_action_edit.setFixedHeight(60)
        self.exit_action_edit.setPlaceholderText("MATLAB code; e.g., cleanup_routine();")
        self.description_edit = QTextEdit(p.get('description', ""))
        self.description_edit.setFixedHeight(80)
        self.description_edit.setPlaceholderText("Optional description for this state")

        layout.addRow("Name:", self.name_edit)
        layout.addRow(self.is_initial_cb)
        layout.addRow(self.is_final_cb)
        layout.addRow("Color:", self.color_button)
        layout.addRow("Entry Action:", self.entry_action_edit)
        layout.addRow("During Action:", self.during_action_edit)
        layout.addRow("Exit Action:", self.exit_action_edit)
        layout.addRow("Description:", self.description_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setMinimumWidth(400)

        if is_new_state:
             self.name_edit.selectAll()
             self.name_edit.setFocus()


    def _choose_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select State Color")
        if color.isValid():
            self.current_color = color
            self._update_color_button_style()

    def _update_color_button_style(self):
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {'black' if self.current_color.lightnessF() > 0.5 else 'white'};")


    def get_properties(self):
        return {
            'name': self.name_edit.text().strip(),
            'is_initial': self.is_initial_cb.isChecked(),
            'is_final': self.is_final_cb.isChecked(),
            'color': self.current_color.name(),
            'entry_action': self.entry_action_edit.toPlainText().strip(),
            'during_action': self.during_action_edit.toPlainText().strip(),
            'exit_action': self.exit_action_edit.toPlainText().strip(),
            'description': self.description_edit.toPlainText().strip()
        }

class TransitionPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Props"))

        layout = QFormLayout(self)
        layout.setSpacing(10)

        p = current_properties or {}
        self.event_edit = QLineEdit(p.get('event', ""))
        self.event_edit.setPlaceholderText("e.g., mouseClick, timer_event")
        self.condition_edit = QLineEdit(p.get('condition', ""))
        self.condition_edit.setPlaceholderText("e.g., data > 10 && flag == true")
        self.action_edit = QTextEdit(p.get('action', ""))
        self.action_edit.setPlaceholderText("MATLAB code; e.g., counter = 0; call_func();")
        self.action_edit.setFixedHeight(60)

        self.color_button = QPushButton("Choose Color...")
        self.current_color = QColor(p.get('color', "#007878")) # Default transition color
        self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)

        self.offset_perp_spin = QSpinBox()
        self.offset_perp_spin.setRange(-800, 800); self.offset_perp_spin.setSingleStep(10)
        self.offset_perp_spin.setValue(int(p.get('control_offset_x', 0)))
        self.offset_perp_spin.setToolTip("Controls the perpendicular bend of the curve (0 for straight line). Positive values bend one way, negative the other.")

        self.offset_tang_spin = QSpinBox()
        self.offset_tang_spin.setRange(-800, 800); self.offset_tang_spin.setSingleStep(10)
        self.offset_tang_spin.setValue(int(p.get('control_offset_y', 0)))
        self.offset_tang_spin.setToolTip("Controls the tangential shift of the curve's midpoint. Affects how 'early' or 'late' the curve bends.")

        self.description_edit = QTextEdit(p.get('description', ""))
        self.description_edit.setFixedHeight(80)
        self.description_edit.setPlaceholderText("Optional description for this transition")

        layout.addRow("Event Trigger:", self.event_edit)
        layout.addRow("Condition (Guard):", self.condition_edit)
        layout.addRow("Transition Action:", self.action_edit)
        layout.addRow("Color:", self.color_button)
        layout.addRow("Curve Bend:", self.offset_perp_spin)
        layout.addRow("Curve Midpoint Shift:", self.offset_tang_spin)
        layout.addRow("Description:", self.description_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setMinimumWidth(450)

        if is_new_transition:
            self.event_edit.setFocus()


    def _choose_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select Transition Color")
        if color.isValid():
            self.current_color = color
            self._update_color_button_style()

    def _update_color_button_style(self):
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {'black' if self.current_color.lightnessF() > 0.5 else 'white'};")


    def get_properties(self):
        return {
            'event': self.event_edit.text().strip(),
            'condition': self.condition_edit.text().strip(),
            'action': self.action_edit.toPlainText().strip(),
            'color': self.current_color.name(),
            'control_offset_x': self.offset_perp_spin.value(),
            'control_offset_y': self.offset_tang_spin.value(),
            'description': self.description_edit.toPlainText().strip()
        }

class CommentPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent)
        self.setWindowTitle("Comment Properties")
        p = current_properties or {}

        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit(p.get('text', "Comment"))
        self.text_edit.setMinimumHeight(100)
        self.text_edit.setPlaceholderText("Enter your comment or note here.")

        # Optional: Width control for comments. For now, width is managed by setTextWidth.
        # self.width_spin = QSpinBox(); self.width_spin.setRange(50,1000); self.width_spin.setValue(int(p.get('width', 150)))
        # layout.addWidget(QLabel("Comment Width (approx):")); layout.addWidget(self.width_spin)

        layout.addWidget(QLabel("Comment Text:"))
        layout.addWidget(self.text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setMinimumWidth(350)
        self.text_edit.setFocus()
        self.text_edit.selectAll()

    def get_properties(self):
        return {
            'text': self.text_edit.toPlainText(),
            # 'width': self.width_spin.value() # if width control added
        }

class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings")
        self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"))
        self.setMinimumWidth(550)

        main_layout = QVBoxLayout(self)

        # Path Configuration Group
        path_group = QGroupBox("MATLAB Executable Path")
        path_form_layout = QFormLayout() # Use QFormLayout for label-field pairs
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path)
        self.path_edit.setPlaceholderText("e.g., C:\\Program Files\\MATLAB\\R202Xy\\bin\\matlab.exe")
        path_form_layout.addRow("Path:", self.path_edit)

        btn_layout = QHBoxLayout() # For buttons below path edit
        auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_FileDialogContentsView, "Det"), "Auto-detect")
        auto_detect_btn.clicked.connect(self._auto_detect)
        auto_detect_btn.setToolTip("Attempt to find MATLAB installations.")
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), "Browse...")
        browse_btn.clicked.connect(self._browse)
        browse_btn.setToolTip("Browse for MATLAB executable.")
        btn_layout.addWidget(auto_detect_btn)
        btn_layout.addWidget(browse_btn)
        btn_layout.addStretch() # Push buttons to the left

        path_v_layout = QVBoxLayout() # Vertical layout for form and buttons
        path_v_layout.addLayout(path_form_layout)
        path_v_layout.addLayout(btn_layout)
        path_group.setLayout(path_v_layout)
        main_layout.addWidget(path_group)

        # Connection Test Group
        test_group = QGroupBox("Connection Test")
        test_layout = QVBoxLayout()
        self.test_status_label = QLabel("Status: Unknown")
        self.test_status_label.setWordWrap(True) # Allow message to wrap
        self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse) # Allow copying status
        test_btn = QPushButton(get_standard_icon(QStyle.SP_CommandLink, "Test"), "Test Connection")
        test_btn.clicked.connect(self._test_connection_and_update_label) # Specific handler
        test_btn.setToolTip("Test connection to the specified MATLAB path.")
        test_layout.addWidget(test_btn)
        test_layout.addWidget(self.test_status_label)
        test_group.setLayout(test_layout)
        main_layout.addWidget(test_group)

        # Dialog Buttons (Ok/Cancel)
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close")
        dialog_buttons.accepted.connect(self._apply_settings)
        dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)

        # Initial status update
        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        if self.matlab_connection.matlab_path and self.matlab_connection.connected:
            self._update_test_label_from_signal(True, f"Connected: {self.matlab_connection.matlab_path}")
        elif self.matlab_connection.matlab_path: # Path set but connection state unknown or false
             self._update_test_label_from_signal(False, f"Path previously set ({self.matlab_connection.matlab_path}), but connection unconfirmed or failed.")
        else:
            self._update_test_label_from_signal(False, "MATLAB path not set.")

    def _auto_detect(self):
        self.test_status_label.setText("Status: Auto-detecting MATLAB, please wait...")
        self.test_status_label.setStyleSheet("") # Reset color
        QApplication.processEvents() # Update UI before blocking detection
        self.matlab_connection.detect_matlab() # This will emit connectionStatusChanged

    def _browse(self):
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        start_dir = os.path.dirname(self.path_edit.text()) if self.path_edit.text() and os.path.isdir(os.path.dirname(self.path_edit.text())) else QDir.homePath()
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path:
            self.path_edit.setText(path)
            # Don't test automatically on browse, user might want to edit further.
            # Update status to reflect change.
            self._update_test_label_from_signal(False, "Path changed. Click 'Test Connection' or 'Apply & Close'.")

    def _test_connection_and_update_label(self):
        path = self.path_edit.text().strip()
        if not path:
            self._update_test_label_from_signal(False, "MATLAB path is empty. Cannot test.")
            return

        self.test_status_label.setText("Status: Testing connection, please wait...")
        self.test_status_label.setStyleSheet("") # Reset color
        QApplication.processEvents()

        # Set path and then test. set_matlab_path will emit its own signal if path validity changes.
        # test_connection will emit its own signal based on test result.
        if self.matlab_connection.set_matlab_path(path): # if path seems initially valid
            self.matlab_connection.test_connection()
        # If set_matlab_path returns False, it means the path was invalid, and it emits its own status.

    def _update_test_label_from_signal(self, success, message):
        status_prefix = "Status: "
        if success: # General success signal
            if "MATLAB path set" in message : status_prefix = "Status: Path validated. "
            elif "successful" in message : status_prefix = "Status: Connected! "
        # Else, keep "Status: " or if it's an error message, that's fine.

        self.test_status_label.setText(status_prefix + message)
        self.test_status_label.setStyleSheet("color: #006400; font-weight: bold;" if success else "color: #B22222; font-weight: bold;")
        if success and self.matlab_connection.matlab_path: # If a successful detection/set occurred, update text field
             self.path_edit.setText(self.matlab_connection.matlab_path)

    def _apply_settings(self):
        path = self.path_edit.text().strip()
        # Setting the path here ensures the connection object has the latest from the dialog.
        # This might trigger connectionStatusChanged if path validity changes.
        self.matlab_connection.set_matlab_path(path)
        self.accept() # Close dialog


# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file_path = None
        self.last_generated_model_path = None # For convenience in subsequent ops
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)

        self.scene = DiagramScene(self.undo_stack, self) # Pass self as parent_window
        self.scene.set_log_function(self.log_message)
        self.scene.modifiedStatusChanged.connect(self.setWindowModified) # Connect to Qt's modified status
        self.scene.modifiedStatusChanged.connect(self._update_window_title) # Custom title update

        self.init_ui()
        self._update_matlab_status_display(False, "Initializing. Configure in Simulation menu or attempt auto-detect.")

        # Connect MATLAB connection signals
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)

        self._update_window_title() # Initial title setup
        self.on_new_file(silent=True) # Start with a clean, new file state

        self.scene.selectionChanged.connect(self._update_properties_dock) # Update properties dock on selection
        self._update_properties_dock() # Initial state of properties dock

    def init_ui(self):
        self.setGeometry(50, 50, 1600, 1000) # Slightly larger default size
        self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "BSM"))

        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_docks()
        self._create_central_widget()

        # Set initial enable states
        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()

        self.select_mode_action.trigger() # Start in select mode

    def _create_actions(self):
        # Helper for safe QStyle enum access
        def _safe_get_style_enum(attr_name, fallback_attr_name=None):
            try: return getattr(QStyle, attr_name)
            except AttributeError:
                if fallback_attr_name:
                    try: return getattr(QStyle, fallback_attr_name)
                    except AttributeError: pass
                return QStyle.SP_CustomBase # A generic fallback if primary and secondary miss

        # File Actions
        self.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "New"), "&New", self, shortcut=QKeySequence.New, statusTip="Create a new file", triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "Opn"), "&Open...", self, shortcut=QKeySequence.Open, statusTip="Open an existing file", triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Sav"), "&Save", self, shortcut=QKeySequence.Save, statusTip="Save the current file", triggered=self.on_save_file)
        self.save_as_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton),"Save &As...", self, shortcut=QKeySequence.SaveAs, statusTip="Save the current file with a new name", triggered=self.on_save_file_as)
        self.exit_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", self, shortcut=QKeySequence.Quit, statusTip="Exit the application", triggered=self.close)

        # Edit Actions
        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "Un"))
        self.undo_action.setStatusTip("Undo the last action")
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "Re"))
        self.redo_action.setStatusTip("Redo the last undone action")

        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.undo_stack.canRedoChanged.connect(self._update_undo_redo_actions_enable_state)

        self.select_all_action = QAction(get_standard_icon(_safe_get_style_enum("SP_FileDialogDetailedView"), "All"), "Select &All", self, shortcut=QKeySequence.SelectAll, statusTip="Select all items in the scene", triggered=self.on_select_all)
        self.delete_action = QAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "&Delete", self, shortcut=QKeySequence.Delete, statusTip="Delete selected items", triggered=self.on_delete_selected)

        # Mode Actions (for toolbar and menu)
        self.mode_action_group = QActionGroup(self)
        self.mode_action_group.setExclusive(True)

        select_icon_enum = _safe_get_style_enum("SP_ArrowCursor", "SP_PointingHandCursor")
        self.select_mode_action = QAction(QIcon.fromTheme("edit-select", get_standard_icon(select_icon_enum, "Sel")), "Select/Move", self, checkable=True, statusTip="Mode: Select and move items (Esc to cancel)", triggered=lambda: self.scene.set_mode("select"))

        state_icon_enum = _safe_get_style_enum("SP_FileDialogNewFolder", "SP_FileIcon")
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", get_standard_icon(state_icon_enum, "St")), "Add State", self, checkable=True, statusTip="Mode: Click on canvas to add a new state (Esc to cancel)", triggered=lambda: self.scene.set_mode("state"))

        trans_icon_enum = _safe_get_style_enum("SP_FileDialogBack", "SP_ArrowRight")
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", get_standard_icon(trans_icon_enum, "Tr")), "Add Transition", self, checkable=True, statusTip="Mode: Click source then target state (Esc to cancel)", triggered=lambda: self.scene.set_mode("transition"))

        comment_icon_enum = _safe_get_style_enum("SP_MessageBoxInformation", "SP_FileLinkIcon")
        self.add_comment_mode_action = QAction(QIcon.fromTheme("insert-text", get_standard_icon(comment_icon_enum, "Cm")), "Add Comment", self, checkable=True, statusTip="Mode: Click on canvas to add a comment (Esc to cancel)", triggered=lambda: self.scene.set_mode("comment"))

        self.mode_action_group.addAction(self.select_mode_action)
        self.mode_action_group.addAction(self.add_state_mode_action)
        self.mode_action_group.addAction(self.add_transition_mode_action)
        self.mode_action_group.addAction(self.add_comment_mode_action)
        self.select_mode_action.setChecked(True) # Default mode

        # Simulation/MATLAB Actions
        self.export_simulink_action = QAction(get_standard_icon(QStyle.SP_ArrowRight, "->M"), "&Export to Simulink...", self, statusTip="Generate a Simulink model from the diagram", triggered=self.on_export_simulink)
        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation...", self, statusTip="Run a Simulink model (requires MATLAB with Simulink)", triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cde"), "Generate &Code (C/C++)...", self, statusTip="Generate C/C++ code from a Simulink model (requires MATLAB Coder & Simulink Coder / Embedded Coder)", triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(_safe_get_style_enum("SP_ComputerIcon","SP_FileDialogDetailedView"), "Cfg"), "&MATLAB Settings...", self, statusTip="Configure MATLAB connection settings", triggered=self.on_matlab_settings)

        # Help Action
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, statusTip=f"Show information about {APP_NAME}", triggered=self.on_about)

    def _create_menus(self):
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet("QMenuBar { background-color: #E8E8E8; } QMenu::item:selected { background-color: #D0D0D0; }") # Basic styling

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_simulink_action) # Moved Export here as it's a form of "Save As"
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.delete_action)
        edit_menu.addAction(self.select_all_action)
        edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_DesktopIcon, "Mode"),"Interaction Mode") # Modes sub-menu
        mode_menu.addAction(self.select_mode_action)
        mode_menu.addAction(self.add_state_mode_action)
        mode_menu.addAction(self.add_transition_mode_action)
        mode_menu.addAction(self.add_comment_mode_action)


        sim_menu = menu_bar.addMenu("&Simulation")
        sim_menu.addAction(self.run_simulation_action)
        sim_menu.addAction(self.generate_code_action)
        sim_menu.addSeparator()
        sim_menu.addAction(self.matlab_settings_action)

        self.view_menu = menu_bar.addMenu("&View") # For toggling docks

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(28,28) # Standard icon size for toolbars

        # File Toolbar
        file_toolbar = self.addToolBar("File")
        file_toolbar.setObjectName("FileToolBar")
        file_toolbar.setIconSize(icon_size)
        file_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon) # Icon and text
        file_toolbar.addAction(self.new_action)
        file_toolbar.addAction(self.open_action)
        file_toolbar.addAction(self.save_action)

        # Edit Toolbar
        edit_toolbar = self.addToolBar("Edit")
        edit_toolbar.setObjectName("EditToolBar")
        edit_toolbar.setIconSize(icon_size)
        edit_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        edit_toolbar.addAction(self.undo_action)
        edit_toolbar.addAction(self.redo_action)
        edit_toolbar.addSeparator()
        edit_toolbar.addAction(self.delete_action)

        # Interaction Tools Toolbar
        tools_tb = self.addToolBar("Interaction Tools")
        tools_tb.setObjectName("ToolsToolBar")
        tools_tb.setIconSize(icon_size)
        tools_tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        tools_tb.addAction(self.select_mode_action)
        tools_tb.addAction(self.add_state_mode_action)
        tools_tb.addAction(self.add_transition_mode_action)
        tools_tb.addAction(self.add_comment_mode_action)
        self.addToolBarBreak() # Start new row of toolbars if space is constrained

        # Simulation Toolbar (new)
        sim_toolbar = self.addToolBar("Simulation Tools")
        sim_toolbar.setObjectName("SimulationToolBar")
        sim_toolbar.setIconSize(icon_size)
        sim_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        sim_toolbar.addAction(self.export_simulink_action)
        sim_toolbar.addAction(self.run_simulation_action)
        sim_toolbar.addAction(self.generate_code_action)


    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready") # General status messages
        self.status_bar.addWidget(self.status_label, 1) # Stretchable label

        self.matlab_status_label = QLabel("MATLAB: Initializing...")
        self.matlab_status_label.setToolTip("MATLAB connection status.")
        self.matlab_status_label.setStyleSheet("padding-right: 10px; padding-left: 5px;") # Spacing
        self.status_bar.addPermanentWidget(self.matlab_status_label) # Non-stretchable, on the right

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0,0) # Indeterminate progress
        self.progress_bar.setVisible(False) # Hidden by default
        self.progress_bar.setMaximumWidth(180) # Limit width
        self.progress_bar.setTextVisible(False) # No text on progress bar itself
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)

        # --- Tools Dock (Interaction Modes + Draggable Items) ---
        self.tools_dock = QDockWidget("Tools", self)
        self.tools_dock.setObjectName("ToolsDock")
        self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        tools_widget = QWidget()
        tools_main_layout = QVBoxLayout(tools_widget)
        tools_main_layout.setSpacing(10)
        tools_main_layout.setContentsMargins(8,8,8,8)

        # Interaction Modes Group
        mode_group_box = QGroupBox("Interaction Modes")
        mode_layout = QVBoxLayout()
        mode_layout.setSpacing(5)

        self.toolbox_select_button = QToolButton(); self.toolbox_select_button.setDefaultAction(self.select_mode_action)
        self.toolbox_add_state_button = QToolButton(); self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action)
        self.toolbox_transition_button = QToolButton(); self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action)
        self.toolbox_add_comment_button = QToolButton(); self.toolbox_add_comment_button.setDefaultAction(self.add_comment_mode_action)

        for btn in [self.toolbox_select_button, self.toolbox_add_state_button, self.toolbox_transition_button, self.toolbox_add_comment_button]:
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setIconSize(QSize(20,20))
            mode_layout.addWidget(btn)
        mode_group_box.setLayout(mode_layout)
        tools_main_layout.addWidget(mode_group_box)

        # Draggable Items Group
        draggable_group_box = QGroupBox("Drag to Canvas")
        draggable_layout = QVBoxLayout()
        draggable_layout.setSpacing(5)

        common_style = "QPushButton { background-color: #E8F0FE; color: #1C3A5D; border: 1px solid #A9CCE3; padding: 6px; }" \
                       "QPushButton:hover { background-color: #D8E0EE; }" \
                       "QPushButton:pressed { background-color: #C8D0DE; }"

        drag_state_btn = DraggableToolButton("State", "application/x-bsm-tool", "State", common_style)
        drag_state_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))

        drag_initial_state_btn = DraggableToolButton("Initial State", "application/x-bsm-tool", "Initial State", common_style)
        drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "I")) # Simple 'I' or dot

        drag_final_state_btn = DraggableToolButton("Final State", "application/x-bsm-tool", "Final State", common_style)
        drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "F")) # Checkmark for final

        drag_comment_btn = DraggableToolButton("Comment", "application/x-bsm-tool", "Comment", common_style)
        drag_comment_btn.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))

        for btn in [drag_state_btn, drag_initial_state_btn, drag_final_state_btn, drag_comment_btn]:
             btn.setIconSize(QSize(22,22))
             draggable_layout.addWidget(btn)

        draggable_group_box.setLayout(draggable_layout)
        tools_main_layout.addWidget(draggable_group_box)

        tools_main_layout.addStretch() # Pushes content to top
        self.tools_dock.setWidget(tools_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock)
        self.view_menu.addAction(self.tools_dock.toggleViewAction())


        # --- Log Output Dock ---
        self.log_dock = QDockWidget("Log Output", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9)) # Monospaced font for logs
        self.log_output.setStyleSheet("QTextEdit { background-color: #FDFDFD; color: #333; border: 1px solid #DDD; }")
        self.log_dock.setWidget(self.log_output)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.view_menu.addAction(self.log_dock.toggleViewAction())

        # --- Properties Dock ---
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        properties_widget_main = QWidget()
        self.properties_layout = QVBoxLayout(properties_widget_main)

        self.properties_editor_label = QLabel("<i>No item selected.</i>") # Displays item info
        self.properties_editor_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.properties_editor_label.setWordWrap(True)
        self.properties_editor_label.setTextInteractionFlags(Qt.TextSelectableByMouse) # Allow copy

        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton,"Edt"), "Edit Properties...")
        self.properties_edit_button.setEnabled(False) # Enabled when single item selected
        self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock)
        self.properties_edit_button.setIconSize(QSize(18,18))

        self.properties_layout.addWidget(self.properties_editor_label, 1) # Label takes most space
        self.properties_layout.addWidget(self.properties_edit_button) # Button at bottom
        properties_widget_main.setLayout(self.properties_layout)
        self.properties_dock.setWidget(properties_widget_main)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        self.view_menu.addAction(self.properties_dock.toggleViewAction())

    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self) # Our custom zoomable view
        self.setCentralWidget(self.view)

    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1:
            item = selected_items[0]
            props = item.get_data()
            item_type_name = type(item).__name__.replace("Graphics", "").replace("Item", "")
            item_info = f"<b>Type:</b> {item_type_name}<br><hr style='margin: 3px 0;'>"

            def format_multiline(text_content, max_chars=30): # Renamed variable to avoid conflict
                if not text_content: return "<i>(none)</i>"
                first_line = text_content.split('\n')[0]
                # Use html.escape here
                return html.escape(first_line[:max_chars] + ('...' if len(first_line) > max_chars or '\n' in text_content else ''))

            if isinstance(item, GraphicsStateItem):
                item_info += f"<b>Name:</b> {html.escape(props['name'])}<br>" # Changed
                item_info += f"<b>Initial:</b> {'Yes' if props['is_initial'] else 'No'}<br>"
                item_info += f"<b>Final:</b> {'Yes' if props['is_final'] else 'No'}<br>"
                item_info += f"<b>Color:</b> <span style='background-color:{props.get('color','#FFFFFF')}; color:{'black' if QColor(props.get('color','#FFFFFF')).lightnessF() > 0.5 else 'white'}; padding: 0px 5px;'>&nbsp;{html.escape(props.get('color','N/A'))}&nbsp;</span><br>" # Changed
                item_info += f"<b>Entry:</b> {format_multiline(props.get('entry_action'))}<br>"
                item_info += f"<b>During:</b> {format_multiline(props.get('during_action'))}<br>"
                item_info += f"<b>Exit:</b> {format_multiline(props.get('exit_action'))}<br>"
                if props.get('description'): item_info += f"<hr style='margin: 3px 0;'><b>Desc:</b> {format_multiline(props.get('description'), 40)}<br>"

            elif isinstance(item, GraphicsTransitionItem):
                label_parts = []
                if props.get('event'): label_parts.append(html.escape(props['event'])) # Changed
                if props.get('condition'): label_parts.append(f"[{html.escape(props['condition'])}]") # Changed
                if props.get('action'): label_parts.append(f"/{{{format_multiline(props['action'],20)}}}") # format_multiline now uses html.escape
                full_label = " ".join(label_parts) if label_parts else "<i>(No Label)</i>"

                item_info += f"<b>Label:</b> {full_label}<br>"
                item_info += f"<b>From:</b> {html.escape(props['source'])}<br>" # Changed
                item_info += f"<b>To:</b> {html.escape(props['target'])}<br>"   # Changed
                item_info += f"<b>Color:</b> <span style='background-color:{props.get('color','#FFFFFF')}; color:{'black' if QColor(props.get('color','#FFFFFF')).lightnessF() > 0.5 else 'white'}; padding: 0px 5px;'>&nbsp;{html.escape(props.get('color','N/A'))}&nbsp;</span><br>" # Changed
                item_info += f"<b>Curve:</b> Bend={props.get('control_offset_x',0):.0f}, Shift={props.get('control_offset_y',0):.0f}<br>"
                if props.get('description'): item_info += f"<hr style='margin: 3px 0;'><b>Desc:</b> {format_multiline(props.get('description'), 40)}<br>"

            elif isinstance(item, GraphicsCommentItem):
                item_info += f"<b>Text:</b> {format_multiline(props['text'], 60)}<br>"

            else: item_info += "Unknown Item Type"

            self.properties_editor_label.setText(item_info)
            self.properties_edit_button.setEnabled(True)
            self.properties_edit_button.setToolTip(f"Edit properties of selected {item_type_name}")
        elif len(selected_items) > 1:
            self.properties_editor_label.setText(f"<b>{len(selected_items)} items selected.</b><br><i>Select a single item to view/edit its properties.</i>")
            self.properties_edit_button.setEnabled(False)
            self.properties_edit_button.setToolTip("Select a single item to edit properties.")
        else: # No items selected
            self.properties_editor_label.setText("<i>No item selected.</i><br>Click an item in the diagram or use tools to add new items.")
            self.properties_edit_button.setEnabled(False)
            self.properties_edit_button.setToolTip("")

    def _on_edit_selected_item_properties_from_dock(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1:
            self.scene.edit_item_properties(selected_items[0]) # Delegate to scene's method

    def log_message(self, message: str):
        timestamp = QTime.currentTime().toString('hh:mm:ss.zzz')
        self.log_output.append(f"[{timestamp}] {message}")
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum()) # Auto-scroll
        self.status_label.setText(message.split('\n')[0][:120]) # Show first line in status bar (truncated)

    def _update_window_title(self):
        title = APP_NAME
        if self.current_file_path:
            title += f" - {os.path.basename(self.current_file_path)}"
        else:
            title += " - Untitled"
        title += "[*]" # Placeholder for modified status indicator (handled by setWindowModified)
        self.setWindowTitle(title)

    def _update_save_actions_enable_state(self):
        is_dirty = self.isWindowModified() # Qt's built-in dirty flag check
        self.save_action.setEnabled(is_dirty)
        # Save As is always enabled if there's content (even if not dirty), or even for an empty new file.
        # Changed logic: Save As always enabled.
        self.save_as_action.setEnabled(True)

    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo())
        self.redo_action.setEnabled(self.undo_stack.canRedo())
        # Optionally set text to show what will be undone/redone
        self.undo_action.setText(f"&Undo {self.undo_stack.undoText()}" if self.undo_stack.canUndo() else "&Undo")
        self.redo_action.setText(f"&Redo {self.undo_stack.redoText()}" if self.undo_stack.canRedo() else "&Redo")

    def _update_matlab_status_display(self, connected, message):
        self.matlab_status_label.setText(f"MATLAB: {'Connected' if connected else 'Disconnected'}")
        self.matlab_status_label.setToolTip(f"MATLAB Status: {message}")
        if connected:
            self.matlab_status_label.setStyleSheet("color: #006400; font-weight: bold; padding-right: 10px; padding-left: 5px;")
        else:
            self.matlab_status_label.setStyleSheet("color: #B22222; font-weight: bold; padding-right: 10px; padding-left: 5px;")
        self.log_message(f"MATLAB Connection Update: {message}")
        self._update_matlab_actions_enabled_state()

    def _update_matlab_actions_enabled_state(self):
        connected = self.matlab_connection.connected
        # Enable/disable actions that require MATLAB
        self.export_simulink_action.setEnabled(connected)
        self.run_simulation_action.setEnabled(connected)
        self.generate_code_action.setEnabled(connected)
        # Enable state for toolbar buttons (they share actions) will update automatically.

    def _start_matlab_operation(self, operation_name):
        self.log_message(f"MATLAB Operation: {operation_name} starting...")
        self.status_label.setText(f"Running: {operation_name}...")
        self.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False) # Disable UI during op

    def _finish_matlab_operation(self):
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready") # Reset status bar
        self.set_ui_enabled_for_matlab_op(True) # Re-enable UI
        self.log_message("MATLAB Operation: Finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        # Disable/Enable major UI elements during MATLAB ops
        self.menuBar().setEnabled(enabled)
        # Toolbars
        for child in self.findChildren(QToolBar): # Find all toolbars
            child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
        # Docks (be careful with log dock if you want it to update)
        for dock_name in ["ToolsDock", "PropertiesDock"]: # "LogDock" can remain enabled
            dock = self.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(enabled)

    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        # 'data' is typically file path for model gen, or specific message for sim
        self._finish_matlab_operation()
        self.log_message(f"MATLAB Result ({('Success' if success else 'Failure')}): {message}")
        if success:
            if "Model generation" in message and data: # Check if data (path) exists
                 self.last_generated_model_path = data # Store for later use (e.g. default for run sim)
                 QMessageBox.information(self, "Simulink Model Generation",
                                        f"Simulink model generated successfully:\n{data}")
            elif "Simulation" in message: # Sim message usually in 'message' directly
                 QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else: # Failure
            QMessageBox.warning(self, "MATLAB Operation Failed", message)

    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation()
        self.log_message(f"MATLAB Code Gen Result ({('Success' if success else 'Failure')}): {message}")
        if success and output_dir:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText) # To allow hyperlink
            msg_box.setText(f"Code generation process completed.<br>"
                            f"Output directory: <a href='file:///{os.path.abspath(output_dir)}'>{os.path.abspath(output_dir)}</a>")

            open_dir_button = msg_box.addButton("Open Directory", QMessageBox.ActionRole)
            msg_box.addButton(QMessageBox.Ok)
            msg_box.exec_()

            if msg_box.clickedButton() == open_dir_button:
                try:
                    # Ensure path is absolute and uses system separators for QDesktopServices
                    abs_path_for_open = os.path.abspath(output_dir)
                    QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path_for_open))
                except Exception as e:
                    self.log_message(f"Error opening directory {output_dir}: {e}")
                    QMessageBox.warning(self, "Error Opening Directory", f"Could not open directory:\n{e}")
        elif not success:
            QMessageBox.warning(self, "Code Generation Failed", message)

    def _prompt_save_if_dirty(self) -> bool: # Return True if safe to proceed, False if cancelled
        if not self.isWindowModified(): # No changes, safe to proceed
            return True

        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes?",
                                     f"The document '{file_name}' has unsaved changes.\n"
                                     "Do you want to save them before continuing?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save) # Default to Save
        if reply == QMessageBox.Save:
            return self.on_save_file() # Returns True on successful save, False on cancel/fail
        elif reply == QMessageBox.Cancel:
            return False # User cancelled the operation
        return True # User chose Discard

    # --- File Menu Handlers ---
    def on_new_file(self, silent=False): # silent flag for internal calls like __init__
        if not silent and not self._prompt_save_if_dirty():
            return False # User cancelled save, so abort new file creation

        self.scene.clear()
        self.scene.setSceneRect(0,0,5000,4000) # Reset scene bounds if needed
        self.current_file_path = None
        self.last_generated_model_path = None
        self.undo_stack.clear() # Clear history for new file
        self.scene.set_dirty(False) # New file is not dirty
        self._update_window_title()
        self._update_undo_redo_actions_enable_state()
        if not silent: self.log_message("New diagram created. Ready.")
        # Reset view
        self.view.resetTransform()
        self.view.centerOn(2500,2000) # Center on a typical starting area
        self.select_mode_action.trigger() # Ensure select mode
        return True

    def on_open_file(self):
        if not self._prompt_save_if_dirty():
            return

        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)
        if file_path:
            self.log_message(f"Attempting to open file: {file_path}")
            if self._load_from_path(file_path):
                self.current_file_path = file_path
                self.last_generated_model_path = None # Reset generated model path
                self.undo_stack.clear()
                self.scene.set_dirty(False) # Freshly loaded file is not dirty
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                self.log_message(f"Successfully opened: {file_path}")
                # Fit view to content
                items_bounds = self.scene.itemsBoundingRect()
                if not items_bounds.isEmpty():
                    # Add some padding around the content
                    padded_bounds = items_bounds.adjusted(-100, -100, 100, 100)
                    self.view.fitInView(padded_bounds, Qt.KeepAspectRatio)
                else: # Empty file, reset view
                    self.view.resetTransform()
                    self.view.centerOn(2500,2000)
            else: # Load failed
                QMessageBox.critical(self, "Error Opening File", f"Could not load or parse the file: {file_path}")
                self.log_message(f"Failed to open file: {file_path}")

    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Basic validation of root structure (can be more thorough)
            if not isinstance(data, dict) or ('states' not in data or 'transitions' not in data): # comments are optional
                self.log_message(f"Error: Invalid BSM file format in {file_path}. Missing 'states' or 'transitions'.")
                return False
            self.scene.load_diagram_data(data) # Delegate loading to scene
            return True
        except json.JSONDecodeError as e:
            self.log_message(f"Error decoding JSON from {file_path}: {str(e)}")
            return False
        except Exception as e:
            self.log_message(f"Unexpected error loading file {file_path}: {type(e).__name__}: {str(e)}")
            return False

    def on_save_file(self) -> bool: # Return True on success, False on failure/cancel
        if self.current_file_path: # If already has a path, save to it
            if self._save_to_path(self.current_file_path):
                self.scene.set_dirty(False) # Mark as not dirty
                return True
            return False # Save failed
        else: # No current path, so 'Save As...'
            return self.on_save_file_as()

    def on_save_file_as(self) -> bool:
        # Suggest a filename if current_file_path exists, or "untitled"
        start_path = self.current_file_path if self.current_file_path else os.path.join(QDir.homePath(), "untitled" + FILE_EXTENSION)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As",
                                                   start_path,
                                                   FILE_FILTER)
        if file_path:
            # Ensure correct extension
            if not file_path.lower().endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION

            if self._save_to_path(file_path):
                self.current_file_path = file_path # Update current path
                self.scene.set_dirty(False) # Mark as not dirty
                self._update_window_title() # Update window title with new name
                return True
        return False # User cancelled or save failed

    def _save_to_path(self, file_path) -> bool:
        # Use QSaveFile for safer atomic saves
        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            error_str = save_file.errorString()
            self.log_message(f"Error opening save file {file_path}: {error_str}")
            QMessageBox.critical(self, "Save Error", f"Failed to open file for saving:\n{error_str}")
            return False
        try:
            data = self.scene.get_diagram_data() # Get data from scene
            json_data = json.dumps(data, indent=4, ensure_ascii=False) # Pretty print JSON

            bytes_written = save_file.write(json_data.encode('utf-8'))
            if bytes_written == -1: # Error during write
                error_str = save_file.errorString()
                self.log_message(f"Error writing data to {file_path}: {error_str}")
                QMessageBox.critical(self, "Save Error", f"Failed to write data to file:\n{error_str}")
                save_file.cancelWriting()
                return False

            if not save_file.commit(): # Finalize save (atomic operation)
                error_str = save_file.errorString()
                self.log_message(f"Error committing save to {file_path}: {error_str}")
                QMessageBox.critical(self, "Save Error", f"Failed to commit saved file:\n{error_str}")
                return False

            self.log_message(f"File saved successfully: {file_path}")
            return True
        except Exception as e:
            self.log_message(f"Error preparing data or writing to save file {file_path}: {type(e).__name__}: {str(e)}")
            QMessageBox.critical(self, "Save Error", f"An error occurred during saving:\n{str(e)}")
            save_file.cancelWriting() # Important to clean up if exception occurs before commit
            return False

    # --- Edit Menu Handlers ---
    def on_select_all(self):
        self.scene.select_all()

    def on_delete_selected(self):
        self.scene.delete_selected_items()

    # --- Simulation Menu Handlers ---
    def on_export_simulink(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected. Please configure MATLAB settings first in the Simulation menu.")
            return

        # Dialog for model name and output directory
        dialog = QDialog(self)
        dialog.setWindowTitle("Export to Simulink")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowRight, "->M"))
        layout = QFormLayout(dialog); layout.setSpacing(10)

        # Model Name
        model_name_default = "BSM_SimulinkModel"
        if self.current_file_path: # Use current filename as base if available
            base_name = os.path.splitext(os.path.basename(self.current_file_path))[0]
            model_name_default = "".join(c if c.isalnum() or c=='_' else '_' for c in base_name) # Simulink safe name
            if not model_name_default or not model_name_default[0].isalpha(): model_name_default = "Model_" + model_name_default

        model_name_edit = QLineEdit(model_name_default)
        model_name_edit.setPlaceholderText("Valid Simulink model name")
        layout.addRow("Simulink Model Name:", model_name_edit)

        # Output Directory
        default_out_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        output_dir_edit = QLineEdit(default_out_dir)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"),"Browse...")
        browse_btn.setToolTip("Select directory to save the .slx file.")
        def browse_dir(): # Lambda-like helper
            d = QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text())
            if d: output_dir_edit.setText(d)
        browse_btn.clicked.connect(browse_dir)

        dir_layout = QHBoxLayout() # For line edit and browse button
        dir_layout.addWidget(output_dir_edit, 1) # Line edit takes available space
        dir_layout.addWidget(browse_btn)
        layout.addRow("Output Directory:", dir_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        dialog.setMinimumWidth(450)

        if dialog.exec_() == QDialog.Accepted:
            model_name = model_name_edit.text().strip()
            output_dir = output_dir_edit.text().strip()
            if not model_name or not output_dir:
                QMessageBox.warning(self, "Input Error", "Model name and output directory must be specified.")
                return

            # Basic Simulink model name validation
            if not model_name[0].isalpha() or not all(c.isalnum() or c == '_' for c in model_name):
                QMessageBox.warning(self, "Invalid Model Name", "Model name must start with a letter and contain only alphanumeric characters and underscores.")
                return

            if not os.path.exists(output_dir):
                try: os.makedirs(output_dir, exist_ok=True)
                except OSError as e:
                    QMessageBox.critical(self, "Directory Creation Error", f"Could not create output directory:\n{e}")
                    return

            diagram_data = self.scene.get_diagram_data()
            if not diagram_data['states']: # Check if there are any states to export
                QMessageBox.information(self, "Empty Diagram", "Cannot export an empty diagram (no states found). Please add states first.")
                return

            self._start_matlab_operation(f"Exporting '{model_name}' to Simulink")
            self.matlab_connection.generate_simulink_model(
                diagram_data['states'], diagram_data['transitions'], output_dir, model_name
            )

    def on_run_simulation(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected.")
            return

        # File dialog to select model, suggest last generated or current file's dir
        default_model_dir = os.path.dirname(self.last_generated_model_path) if self.last_generated_model_path else \
                            (os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model to Simulate",
                                                   default_model_dir,
                                                   "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return # User cancelled
        self.last_generated_model_path = model_path # Update for next time

        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Enter simulation stop time (seconds):", 10.0, 0.001, 86400.0, 3)
        if not ok: return # User cancelled

        self._start_matlab_operation(f"Running Simulink simulation for '{os.path.basename(model_path)}'")
        self.matlab_connection.run_simulation(model_path, sim_time)

    def on_generate_code(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected.")
            return

        default_model_dir = os.path.dirname(self.last_generated_model_path) if self.last_generated_model_path else \
                            (os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model for Code Generation",
                                                   default_model_dir,
                                                   "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return
        self.last_generated_model_path = model_path

        # Dialog for code generation options
        dialog = QDialog(self)
        dialog.setWindowTitle("Code Generation Options")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cde"))
        layout = QFormLayout(dialog); layout.setSpacing(10)

        lang_combo = QComboBox(); lang_combo.addItems(["C", "C++"]); lang_combo.setCurrentText("C++")
        layout.addRow("Target Language:", lang_combo)

        default_output_base = os.path.dirname(model_path) # Default near model
        output_dir_edit = QLineEdit(default_output_base)
        output_dir_edit.setPlaceholderText("Base directory for generated code")
        browse_btn_codegen = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), "Browse...")
        def browse_dir_codegen_fn(): # Needs a unique name or lambda
            d = QFileDialog.getExistingDirectory(dialog, "Select Base Output Directory for Code", output_dir_edit.text())
            if d: output_dir_edit.setText(d)
        browse_btn_codegen.clicked.connect(browse_dir_codegen_fn)
        dir_layout_codegen = QHBoxLayout(); dir_layout_codegen.addWidget(output_dir_edit, 1); dir_layout_codegen.addWidget(browse_btn_codegen)
        layout.addRow("Base Output Directory:", dir_layout_codegen)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        dialog.setMinimumWidth(450)

        if dialog.exec_() == QDialog.Accepted:
            language = lang_combo.currentText()
            output_dir_base = output_dir_edit.text().strip()
            if not output_dir_base:
                QMessageBox.warning(self, "Input Error", "Base output directory must be specified for code generation.")
                return

            if not os.path.exists(output_dir_base): # Ensure output dir exists
                 try: os.makedirs(output_dir_base, exist_ok=True)
                 except OSError as e:
                     QMessageBox.critical(self, "Directory Creation Error", f"Could not create output directory:\n{e}")
                     return

            self._start_matlab_operation(f"Generating {language} code for '{os.path.basename(model_path)}'")
            self.matlab_connection.generate_code(model_path, language, output_dir_base)

    def on_matlab_settings(self):
        dialog = MatlabSettingsDialog(self.matlab_connection, self)
        dialog.exec_() # Modal dialog

    # --- Help Menu Handler ---
    def on_about(self):
        QMessageBox.about(self, "About " + APP_NAME,
                          f"<h3>{APP_NAME} v{APP_VERSION}</h3>"
                          "<p>A graphical tool for designing brain-inspired state machines. "
                          "It facilitates the creation, visualization, and modification of state diagrams, "
                          "and integrates with MATLAB/Simulink for simulation and C/C++ code generation.</p>"
                          "<p><b>Key Features:</b></p>"
                          "<ul>"
                          "<li>Intuitive diagramming: click-to-add, drag-and-drop elements (States, Initial/Final States, Comments).</li>"
                          "<li>Rich property editing for states (color, entry/during/exit actions, description) and transitions (event, condition, action, color, curve control, description).</li>"
                          "<li>Persistent storage in JSON format ({FILE_EXTENSION}).</li>"
                          "<li>Robust Undo/Redo functionality.</li>"
                          "<li>Zoomable and pannable canvas with grid and snapping.</li>"
                          "<li><b>MATLAB Integration (requires MATLAB, Simulink, Stateflow, Coders):</b>"
                          "<ul><li>Auto-detection or manual configuration of MATLAB path.</li>"
                          "<li>Export diagrams to Simulink models (.slx) with state actions and transition logic.</li>"
                          "<li>Run simulations of exported models directly from the tool.</li>"
                          "<li>Generate C or C++ code (via Embedded Coder) from Simulink models.</li></ul></li>"
                          "</ul>"
                          "<p><i>Developed by the AI Revell Lab.</i></p>"
                          "<p>This tool is intended for research and educational purposes in designing, "
                          "simulating, and implementing complex state-based systems, particularly those inspired by cognitive or neural architectures.</p>")

    # --- Window Close Event ---
    def closeEvent(self, event: QCloseEvent):
        if self._prompt_save_if_dirty(): # Ask to save if modified
            active_threads = list(self.matlab_connection._active_threads) # Make a copy for safety
            if active_threads:
                self.log_message(f"Closing application. {len(active_threads)} MATLAB process(es) may still be running in background if not completed. Please check task manager if needed.")
                # Note: Ideally, threads should be properly managed to terminate/wait, but can be complex for external processes.
            event.accept() # Proceed with closing
        else:
            event.ignore() # Cancel close if user chose Cancel in save prompt


if __name__ == '__main__':
    # Enable High DPI scaling for better visuals on modern displays
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    # You can set a global style here if desired, e.g., Fusion
    # app.setStyle("Fusion")

    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
