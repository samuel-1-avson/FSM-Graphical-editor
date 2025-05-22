Okay, I've incorporated the requested changes. Here's a summary of what's been done:

1.  **Draggable Transition Tool**:
    *   Added a "Transition" button to the "Drag to Canvas" section in the `ToolsDock`.
    *   This is a `DraggableToolButton` similar to the "State" and "Comment" buttons.
    *   When "Transition" is dragged and dropped onto the canvas, the `DiagramScene` now switches to the "transition" creation mode. The user then clicks the source and target states as usual.
    *   The MIME type for all draggable tools has been standardized to `application/x-bsm-tool`.

2.  **Easier Color Selection in Property Dialogs**:
    *   For both `StatePropertiesDialog` and `TransitionPropertiesDialog`:
        *   A predefined palette of 8 common colors has been added next to the "Choose Color..." button.
        *   Users can click these small color swatch buttons for quick selection.
        *   The "Choose Color..." button remains available for selecting any custom color via `QColorDialog`.
        *   The main color button now reflects the currently selected color.

Here's the updated code:

```python
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
    QToolButton, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent, 
    QGraphicsSceneHoverEvent, QGraphicsTextItem # Added QGraphicsTextItem
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
APP_VERSION = "1.4.1" # Incremented for new features
APP_NAME = "Brain State Machine Designer"
FILE_EXTENSION = ".bsm"
FILE_FILTER = f"Brain State Machine Files (*{FILE_EXTENSION});;All Files (*)"
DRAGGABLE_TOOL_MIME_TYPE = "application/x-bsm-tool"

# --- Utility Functions ---
def get_standard_icon(standard_pixmap_enum_value, fallback_text=None):
    icon = QIcon()
    try:
        icon = QApplication.style().standardIcon(standard_pixmap_enum_value)
    except Exception as e:
        print(f"Warning: Error getting standard icon for enum value {standard_pixmap_enum_value}: {e}")
        icon = QIcon() 
    
    if icon.isNull():
        if fallback_text:
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.drawText(pixmap.rect(), Qt.AlignCenter, fallback_text[:2])
            painter.end()
            return QIcon(pixmap)
        else:
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
# (This class remains unchanged from the previous correct version)
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
        else: 
            common_base_paths = ['/usr/local/MATLAB', '/opt/MATLAB']
            for base_path in common_base_paths:
                if os.path.isdir(base_path):
                    versions = sorted([d for d in os.listdir(base_path) if d.startswith('R20')], reverse=True)
                    for v_year_letter in versions:
                         paths_to_check.append(os.path.join(base_path, v_year_letter, 'bin', 'matlab'))
            paths_to_check.append('matlab') 

        for path_candidate in paths_to_check:
            if path_candidate == 'matlab' and sys.platform != 'win32': 
                try:
                    test_process = subprocess.run([path_candidate, "-batch", "exit"], timeout=5, capture_output=True)
                    if test_process.returncode == 0:
                        if self.set_matlab_path(path_candidate):
                           return True
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue 
            elif os.path.exists(path_candidate): 
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
        model_name_orig = model_name 

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
            "    chartSFObj.Name = 'BrainStateMachineLogic';", 
            
            "    chartBlockSimulinkPath = [modelNameVar, '/', 'BSM_Chart'];", 
            "    add_block('stateflow/Chart', chartBlockSimulinkPath, 'Chart', chartSFObj.Path);",
            "    disp(['Stateflow chart block added at: ', chartBlockSimulinkPath]);",

            "    stateHandles = containers.Map('KeyType','char','ValueType','any');",
            "% --- State Creation ---"
        ]

        for i, state in enumerate(states):
            s_name_matlab = state['name'].replace("'", "''") 
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
                f"{s_id_matlab_safe}.Position = [{state['x']/3}, {state['y']/3}, {state['width']/3}, {state['height']/3}];", 
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
            prevPath = path; 
            addpath(modelDir);
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
            matlab_run_command = f"run('{self.script_file.replace('\\', '/')}')" 
            cmd = [self.matlab_path, "-nodisplay", "-batch", matlab_run_command]
            
            timeout_seconds = 600 
            process = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                timeout=timeout_seconds,  
                check=False, 
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
        self.mime_type = mime_type # Standardized: DRAGGABLE_TOOL_MIME_TYPE
        self.item_type_data = item_type_data # e.g., "State", "Initial State", "Transition", "Comment"
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
        mime_data.setText(self.item_type_data) # Key data for dropEvent in DiagramScene
        mime_data.setData(self.mime_type, self.item_type_data.encode()) # Mime type and encoded data
        drag.setMimeData(mime_data)

        pixmap_size = QSize(max(120, self.width()), self.height()) 
        pixmap = QPixmap(pixmap_size)
        pixmap.fill(Qt.transparent) 

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        button_rect = QRectF(0,0, pixmap_size.width()-1, pixmap_size.height()-1)
        current_style = self.styleSheet()
        bg_color = QColor("#B0E0E6") 
        if "background-color:" in current_style:
            try:
                color_str = current_style.split("background-color:")[1].split(";")[0].strip()
                bg_color = QColor(color_str)
            except: pass 
        painter.setBrush(bg_color.lighter(110)) 
        border_color = QColor("#77AABB")
        if "border:" in current_style:
            try:
                b_parts = current_style.split("border:")[1].split(";")[0].strip().split()
                if len(b_parts) >=3: border_color = QColor(b_parts[2])
            except: pass
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(button_rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5)

        icon_pixmap = self.icon().pixmap(QSize(24,24), QIcon.Normal, QIcon.On)
        text_x_offset = 8 
        icon_y_offset = (pixmap_size.height() - icon_pixmap.height()) / 2
        if not icon_pixmap.isNull():
            painter.drawPixmap(int(text_x_offset), int(icon_y_offset), icon_pixmap)
            text_x_offset += icon_pixmap.width() + 8 
        
        painter.setPen(self.palette().buttonText().color()) 
        painter.setFont(self.font())
        text_rect = QRectF(text_x_offset, 0, pixmap_size.width() - text_x_offset - 5, pixmap_size.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 4, pixmap.height() // 2)) 

        drag.exec_(Qt.CopyAction | Qt.MoveAction)


# --- Graphics Items ---
# (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem, UndoCommands largely unchanged from 1.4.0)
# (State and Transition dialogs updated to include color palette - see below)

class GraphicsStateItem(QGraphicsRectItem):
    Type = QGraphicsItem.UserType + 1
    def type(self): return GraphicsStateItem.Type

    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False,
                 color=None, entry_action="", during_action="", exit_action="", description=""):
        super().__init__(x, y, w, h)
        self.text_label = text
        self.is_initial = is_initial
        self.is_final = is_final
        self.color = QColor(color) if color else QColor(190, 220, 255) # Default blueish
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
        painter.setBrush(self.color) # Use item's specific color
        painter.drawRoundedRect(self.rect(), 10, 10) 

        painter.setPen(self._text_color)
        painter.setFont(self._font)
        text_rect = self.rect().adjusted(8, 8, -8, -8) 
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)

        if self.is_initial:
            painter.setBrush(Qt.black)
            painter.setPen(QPen(Qt.black, 2)) 
            marker_radius = 7 
            line_length = 20 
            start_marker_center_x = self.rect().left() - line_length - marker_radius / 2
            start_marker_center_y = self.rect().center().y()
            painter.drawEllipse(QPointF(start_marker_center_x, start_marker_center_y), marker_radius, marker_radius)
            line_start_point = QPointF(start_marker_center_x + marker_radius, start_marker_center_y)
            line_end_point = QPointF(self.rect().left(), start_marker_center_y)
            painter.drawLine(line_start_point, line_end_point)
            arrow_size = 10 
            angle_rad = math.atan2(line_end_point.y() - line_start_point.y(), line_end_point.x() - line_start_point.x())
            arrow_p1 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad + math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad + math.pi / 6))
            arrow_p2 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad - math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad - math.pi / 6))
            painter.setBrush(Qt.black)
            painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))

        if self.is_final:
            painter.setPen(QPen(Qt.black, 2))
            inner_rect = self.rect().adjusted(6, 6, -6, -6) 
            painter.drawRoundedRect(inner_rect, 7, 7) 

        if self.isSelected():
            pen = QPen(QColor(0, 100, 255, 200), 2.5, Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            selection_rect = self.boundingRect().adjusted(-1,-1,1,1) 
            painter.drawRoundedRect(selection_rect, 11, 11)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self) 
        return super().itemChange(change, value)

    def get_data(self):
        return {
            'name': self.text_label, 'x': self.x(), 'y': self.y(),
            'width': self.rect().width(), 'height': self.rect().height(),
            'is_initial': self.is_initial, 'is_final': self.is_final,
            'color': self.color.name() if self.color else None,
            'entry_action': self.entry_action,
            'during_action': self.during_action,
            'exit_action': self.exit_action,
            'description': self.description
        }
    
    def set_text(self, text): 
        if self.text_label != text:
            self.prepareGeometryChange()
            self.text_label = text
            self.update()

    def set_properties(self, name, is_initial, is_final, color_hex=None,
                       entry="", during="", exit_a="", desc=""):
        changed = False
        if self.text_label != name: self.text_label = name; changed = True
        if self.is_initial != is_initial: self.is_initial = is_initial; changed = True
        if self.is_final != is_final: self.is_final = is_final; changed = True
        
        new_color = QColor(color_hex) if color_hex else QColor(190, 220, 255)
        if self.color != new_color:
            self.color = new_color
            self.setBrush(self.color) 
            changed = True
        
        if self.entry_action != entry: self.entry_action = entry; changed = True
        if self.during_action != during: self.during_action = during; changed = True
        if self.exit_action != exit_a: self.exit_action = exit_a; changed = True
        if self.description != desc: self.description = desc; changed = True
        
        if changed:
            self.prepareGeometryChange() 
            self.update() 

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
        self.color = QColor(color) if color else QColor(0, 120, 120) # Default teal
        self.description = description
        
        self.arrow_size = 12 
        self._text_color = QColor(30, 30, 30) 
        self._font = QFont("Arial", 9) 
        self.control_point_offset = QPointF(0,0)

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
        self.setPen(QPen(self.color.lighter(120), 3)) 
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent):
        self.setPen(QPen(self.color, 2.5))
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 25 
        path_bounds = self.path().boundingRect()
        current_label = self._compose_label_string()
        if current_label:
            fm = QFontMetrics(self._font)
            text_rect = fm.boundingRect(current_label)
            mid_point_on_path = self.path().pointAtPercent(0.5)
            text_render_rect = QRectF(mid_point_on_path.x() - text_rect.width() - 10, 
                                     mid_point_on_path.y() - text_rect.height() - 10,
                                     text_rect.width()*2 + 20, text_rect.height()*2 + 20) 
            path_bounds = path_bounds.united(text_render_rect)
        return path_bounds.adjusted(-extra, -extra, extra, extra)

    def shape(self): 
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(18 + self.pen().widthF()) 
        path_stroker.setCapStyle(Qt.RoundCap)
        path_stroker.setJoinStyle(Qt.RoundJoin)
        return path_stroker.createStroke(self.path())

    def update_path(self):
        if not self.start_item or not self.end_item:
            self.setPath(QPainterPath()) 
            return

        start_center = self.start_item.sceneBoundingRect().center()
        end_center = self.end_item.sceneBoundingRect().center()
        line_to_target = QLineF(start_center, end_center)
        start_point = self._get_intersection_point(self.start_item, line_to_target)
        line_from_target = QLineF(end_center, start_center) 
        end_point = self._get_intersection_point(self.end_item, line_from_target)

        if start_point is None: start_point = start_center
        if end_point is None: end_point = end_center    

        path = QPainterPath(start_point)

        if self.start_item == self.end_item: 
            rect = self.start_item.sceneBoundingRect()
            loop_radius_x = rect.width() * 0.45 
            loop_radius_y = rect.height() * 0.45
            p1 = QPointF(rect.center().x() + loop_radius_x * 0.3, rect.top())
            p2 = QPointF(rect.center().x() - loop_radius_x * 0.3, rect.top())
            ctrl1 = QPointF(rect.center().x() + loop_radius_x * 1.5, rect.top() - loop_radius_y * 3.0)
            ctrl2 = QPointF(rect.center().x() - loop_radius_x * 1.5, rect.top() - loop_radius_y * 3.0)
            path.moveTo(p1)
            path.cubicTo(ctrl1, ctrl2, p2)
            end_point = p2 
        else: 
            mid_x = (start_point.x() + end_point.x()) / 2
            mid_y = (start_point.y() + end_point.y()) / 2
            dx = end_point.x() - start_point.x()
            dy = end_point.y() - start_point.y()
            length = math.hypot(dx, dy); 
            if length == 0: length = 1 
            perp_x = -dy / length
            perp_y = dx / length
            ctrl_pt_x = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y()
            ctrl_pt_y = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()
            ctrl_pt = QPointF(ctrl_pt_x, ctrl_pt_y)
            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0:
                 path.lineTo(end_point) 
            else:
                 path.quadTo(ctrl_pt, end_point) 
        
        self.setPath(path)
        self.prepareGeometryChange() 

    def _get_intersection_point(self, item: QGraphicsRectItem, line: QLineF):
        item_rect = item.sceneBoundingRect() 
        edges = [
            QLineF(item_rect.topLeft(), item_rect.topRight()),      
            QLineF(item_rect.topRight(), item_rect.bottomRight()),  
            QLineF(item_rect.bottomRight(), item_rect.bottomLeft()),
            QLineF(item_rect.bottomLeft(), item_rect.topLeft())     
        ]
        intersect_points = []
        for edge in edges:
            intersection_point_var = QPointF() 
            intersect_type = line.intersect(edge, intersection_point_var)
            if intersect_type == QLineF.BoundedIntersection:
                edge_rect_for_check = QRectF(edge.p1(), edge.p2()).normalized()
                epsilon = 1e-3 
                if (edge_rect_for_check.left() - epsilon <= intersection_point_var.x() <= edge_rect_for_check.right() + epsilon and
                    edge_rect_for_check.top() - epsilon <= intersection_point_var.y() <= edge_rect_for_check.bottom() + epsilon):
                    intersect_points.append(QPointF(intersection_point_var))

        if not intersect_points: return item_rect.center() 
        closest_point = intersect_points[0]
        min_dist_sq = (QLineF(line.p1(), closest_point).length())**2
        for pt in intersect_points[1:]:
            dist_sq = (QLineF(line.p1(), pt).length())**2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_point = pt
        return closest_point

    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty(): return
        painter.setRenderHint(QPainter.Antialiasing)
        current_pen = self.pen() 
        if self.isSelected():
            stroker = QPainterPathStroker(); stroker.setWidth(current_pen.widthF() + 8) 
            stroker.setCapStyle(Qt.RoundCap); stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path())
            painter.setPen(Qt.NoPen) ; painter.setBrush(QColor(0,100,255,60)) 
            painter.drawPath(selection_path_shape)
        
        painter.setPen(current_pen) ; painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

        if self.path().elementCount() < 1 : return 
        percent_at_end = 0.999 
        if self.path().length() < 1: percent_at_end = 0.9 
        line_end_point = self.path().pointAtPercent(1.0)
        angle_at_end_rad = -self.path().angleAtPercent(percent_at_end) * (math.pi / 180.0) 
        arrow_p1 = line_end_point + QPointF(math.cos(angle_at_end_rad - math.pi / 6) * self.arrow_size,
                                           math.sin(angle_at_end_rad - math.pi / 6) * self.arrow_size)
        arrow_p2 = line_end_point + QPointF(math.cos(angle_at_end_rad + math.pi / 6) * self.arrow_size,
                                           math.sin(angle_at_end_rad + math.pi / 6) * self.arrow_size)
        painter.setBrush(current_pen.color()) 
        painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))

        current_label = self._compose_label_string()
        if current_label:
            painter.setFont(self._font); fm = QFontMetrics(self._font)
            text_rect_original = fm.boundingRect(current_label)
            text_pos_on_path = self.path().pointAtPercent(0.5)
            angle_at_mid_deg = self.path().angleAtPercent(0.5) 
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0)
            offset_dist = 12 
            text_center_x = text_pos_on_path.x() + offset_dist * math.cos(offset_angle_rad)
            text_center_y = text_pos_on_path.y() + offset_dist * math.sin(offset_angle_rad)
            text_final_pos = QPointF(text_center_x - text_rect_original.width() / 2,
                                     text_center_y - text_rect_original.height() / 2)
            bg_padding = 3
            bg_rect = QRectF(text_final_pos.x() - bg_padding, 
                             text_final_pos.y() - bg_padding, 
                             text_rect_original.width() + 2 * bg_padding, 
                             text_rect_original.height() + 2 * bg_padding)
            painter.setBrush(QColor(250, 250, 250, 200)) 
            painter.setPen(QPen(QColor(200,200,200,150), 0.5)) 
            painter.drawRoundedRect(bg_rect, 4, 4)
            painter.setPen(self._text_color)
            painter.drawText(text_final_pos, current_label)
    
    def get_data(self):
        return {
            'source': self.start_item.text_label if self.start_item else "None",
            'target': self.end_item.text_label if self.end_item else "None",
            'event': self.event_str, 'condition': self.condition_str, 'action': self.action_str,
            'color': self.color.name() if self.color else None,
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
            self.setPen(QPen(self.color, self.pen().widthF())) 
            changed = True
        
        if offset is not None and self.control_point_offset != offset:
            self.control_point_offset = offset
            changed = True 

        if changed:
            self.prepareGeometryChange() 
            if offset is not None : self.update_path() 
            self.update() 

    def set_control_point_offset(self, offset: QPointF): 
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
        self.setTextWidth(self._default_width) 
        self.adjust_size_to_text()
        self.border_pen = QPen(QColor(204, 204, 153), 1.5)
        self.background_brush = QBrush(QColor(255, 255, 224, 200))

    def paint(self, painter, option, widget):
        painter.setPen(self.border_pen)
        painter.setBrush(self.background_brush)
        painter.drawRoundedRect(self.boundingRect().adjusted(0.5,0.5,-0.5,-0.5), 5, 5)
        super().paint(painter, option, widget)
        if self.isSelected():
            pen = QPen(Qt.blue, 1.5, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())

    def get_data(self):
        return {
            'text': self.toPlainText(),
            'x': self.x(), 'y': self.y(),
            'width': self.boundingRect().width(), 
        }

    def set_properties(self, text, width=None):
        self.setPlainText(text)
        if width: self.setTextWidth(width)
        else: self.adjust_size_to_text()
        self.update()

    def adjust_size_to_text(self):
        self.prepareGeometryChange() 
        self.update()
        
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)


# --- Undo Commands ---
# (These classes AddItemCommand, RemoveItemsCommand, MoveItemsCommand, EditItemPropertiesCommand remain unchanged from 1.4.0)
class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item_instance = item 
        if isinstance(item, GraphicsTransitionItem):
            self.item_data = item.get_data()
            self.start_item_name = item.start_item.text_label if item.start_item else None
            self.end_item_name = item.end_item.text_label if item.end_item else None
        elif isinstance(item, (GraphicsStateItem, GraphicsCommentItem)):
            self.item_data = item.get_data()

    def redo(self):
        if self.item_instance.scene() is None: 
            self.scene.addItem(self.item_instance)
        
        if isinstance(self.item_instance, GraphicsTransitionItem):
            start_node = self.scene.get_state_by_name(self.start_item_name)
            end_node = self.scene.get_state_by_name(self.end_item_name)
            if start_node and end_node:
                self.item_instance.start_item = start_node
                self.item_instance.end_item = end_node
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
                self.scene.log_function(f"Error (Redo Add Transition): Could not link transition. State(s) missing for '{self.item_data.get('event', 'Unnamed Transition')}'.")
        
        self.scene.clearSelection()
        self.item_instance.setSelected(True)
        self.scene.set_dirty(True)

    def undo(self):
        self.scene.removeItem(self.item_instance)
        self.scene.set_dirty(True)

class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items_to_remove, description="Remove Items"):
        super().__init__(description)
        self.scene = scene
        self.removed_items_data = [] 
        self.item_instances_for_quick_toggle = list(items_to_remove) 

        for item in items_to_remove:
            item_data_entry = item.get_data() 
            item_data_entry['_type'] = item.type() 
            if isinstance(item, GraphicsTransitionItem):
                 item_data_entry['_start_name'] = item.start_item.text_label if item.start_item else None
                 item_data_entry['_end_name'] = item.end_item.text_label if item.end_item else None
            self.removed_items_data.append(item_data_entry)

    def redo(self): 
        for item_instance in self.item_instances_for_quick_toggle:
            if item_instance.scene() == self.scene: 
                self.scene.removeItem(item_instance)
        self.scene.set_dirty(True)

    def undo(self): 
        newly_re_added_instances = []
        states_map_for_undo = {} 

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
                states_map_for_undo[state.text_label] = state 
            elif item_data['_type'] == GraphicsCommentItem.Type:
                comment = GraphicsCommentItem(item_data['x'], item_data['y'], item_data['text'])
                comment.setTextWidth(item_data.get('width', 150))
                instance_to_add = comment
            
            if instance_to_add:
                self.scene.addItem(instance_to_add)
                newly_re_added_instances.append(instance_to_add)

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
        
        self.item_instances_for_quick_toggle = newly_re_added_instances 
        self.scene.set_dirty(True)

class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_and_new_positions, description="Move Items"):
        super().__init__(description)
        self.items_and_new_positions = items_and_new_positions
        self.items_and_old_positions = []
        self.scene_ref = None 
        
        if self.items_and_new_positions: 
            self.scene_ref = self.items_and_new_positions[0][0].scene() 
            for item, _ in self.items_and_new_positions:
                self.items_and_old_positions.append((item, item.pos())) 

    def _apply_positions(self, positions_list):
        if not self.scene_ref: return
        for item, pos in positions_list:
            item.setPos(pos) 
            if isinstance(item, GraphicsStateItem):
                 self.scene_ref._update_connected_transitions(item)
        self.scene_ref.update() 
        self.scene_ref.set_dirty(True)

    def redo(self): self._apply_positions(self.items_and_new_positions)
    def undo(self): self._apply_positions(self.items_and_old_positions)

class EditItemPropertiesCommand(QUndoCommand):
    def __init__(self, item, old_props_data, new_props_data, description="Edit Properties"):
        super().__init__(description)
        self.item = item 
        self.old_props_data = old_props_data 
        self.new_props_data = new_props_data 
        self.scene_ref = item.scene()

    def _apply_properties(self, props_to_apply):
        if not self.item or not self.scene_ref: return
        
        original_name_if_state = None 

        if isinstance(self.item, GraphicsStateItem):
            original_name_if_state = self.item.text_label 
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
            
        self.item.update() 
        self.scene_ref.update() 
        self.scene_ref.set_dirty(True)

    def redo(self): self._apply_properties(self.new_props_data)
    def undo(self): self._apply_properties(self.old_props_data)


# --- Diagram Scene ---
class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool) 

    def __init__(self, undo_stack, parent_window=None): 
        super().__init__(parent_window) 
        self.parent_window = parent_window
        self.setSceneRect(0, 0, 5000, 4000) 
        self.current_mode = "select" 
        self.transition_start_item = None
        self.log_function = print 
        self.undo_stack = undo_stack
        self._dirty = False 
        self._mouse_press_items_positions = {} 
        self._temp_transition_line = None 

        self.item_moved.connect(self._handle_item_moved) 

        self.grid_size = 20
        self.grid_pen_light = QPen(QColor(225, 225, 225), 0.8, Qt.SolidLine) 
        self.grid_pen_dark = QPen(QColor(200, 200, 200), 1.0, Qt.SolidLine)  
        self.setBackgroundBrush(QColor(248, 248, 248)) 

        self.snap_to_grid_enabled = True 

    def _update_connected_transitions(self, state_item: GraphicsStateItem):
        for item in self.items(): 
            if isinstance(item, GraphicsTransitionItem):
                if item.start_item == state_item or item.end_item == state_item:
                    item.update_path() 
    
    def _update_transitions_for_renamed_state(self, old_name:str, new_name:str):
        self.log_function(f"State '{old_name}' renamed to '{new_name}'. Dependent transitions may need data update if name was key.")

    def get_state_by_name(self, name: str):
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name:
                return item
        return None

    def set_dirty(self, dirty=True):
        if self._dirty != dirty:
            self._dirty = dirty
            self.modifiedStatusChanged.emit(dirty) 
            if self.parent_window: 
                self.parent_window._update_save_actions_enable_state()
            
    def is_dirty(self): return self._dirty
    def set_log_function(self, log_function): self.log_function = log_function

    def set_mode(self, mode: str):
        old_mode = self.current_mode
        if old_mode == mode: return 
        
        self.current_mode = mode
        self.log_function(f"Interaction mode changed to: {mode}")
        
        self.transition_start_item = None 
        if self._temp_transition_line:
            self.removeItem(self._temp_transition_line)
            self._temp_transition_line = None

        if mode == "select":
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            for item in self.items(): 
                if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): item.setFlag(QGraphicsItem.ItemIsMovable, True)
        elif mode == "state" or mode == "comment": 
            QApplication.setOverrideCursor(Qt.CrossCursor) 
            for item in self.items(): 
                 if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): item.setFlag(QGraphicsItem.ItemIsMovable, False)
        elif mode == "transition":
            QApplication.setOverrideCursor(Qt.PointingHandCursor) 
            for item in self.items(): 
                 if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): item.setFlag(QGraphicsItem.ItemIsMovable, False)
        
        if old_mode in ["state", "transition", "comment"] and mode not in ["state", "transition", "comment"]:
            QApplication.restoreOverrideCursor()
        
        if self.parent_window:
            action_map = {
                "select": self.parent_window.select_mode_action,
                "state": self.parent_window.add_state_mode_action,
                "transition": self.parent_window.add_transition_mode_action,
                "comment": self.parent_window.add_comment_mode_action
            }
            if mode in action_map and not action_map[mode].isChecked():
                action_map[mode].setChecked(True)


    def select_all(self):
        for item in self.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable:
                item.setSelected(True)

    def _handle_item_moved(self, moved_item):
        if isinstance(moved_item, GraphicsStateItem):
            self._update_connected_transitions(moved_item)
        if self.snap_to_grid_enabled and self._mouse_press_items_positions and \
           isinstance(moved_item, (GraphicsStateItem, GraphicsCommentItem)): 
            pass 

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos()
        items_at_pos = self.items(pos)
        top_item_at_pos = next((item for item in items_at_pos if isinstance(item, GraphicsStateItem)), None)
        if not top_item_at_pos: 
            top_item_at_pos = next((item for item in items_at_pos if isinstance(item, (GraphicsCommentItem, GraphicsTransitionItem))), None)
            if not top_item_at_pos and items_at_pos: top_item_at_pos = items_at_pos[0]

        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size - 60 
                grid_y = round(pos.y() / self.grid_size) * self.grid_size - 30 
                self._add_item_interactive(pos, item_type="State") 
            elif self.current_mode == "comment":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size
                grid_y = round(pos.y() / self.grid_size) * self.grid_size
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type="Comment")
            elif self.current_mode == "transition":
                if isinstance(top_item_at_pos, GraphicsStateItem): 
                    self._handle_transition_click(top_item_at_pos, pos)
                else: 
                    self.transition_start_item = None 
                    if self._temp_transition_line:
                        self.removeItem(self._temp_transition_line)
                        self._temp_transition_line = None
                    self.log_function("Transition drawing cancelled (clicked empty space/non-state).")
            else: 
                self._mouse_press_items_positions.clear()
                selected_movable = [item for item in self.selectedItems() if item.flags() & QGraphicsItem.ItemIsMovable]
                for item in selected_movable:
                     self._mouse_press_items_positions[item] = item.pos() 
                super().mousePressEvent(event) 
        
        elif event.button() == Qt.RightButton:
            if top_item_at_pos and isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem)):
                if not top_item_at_pos.isSelected(): 
                    self.clearSelection()
                    top_item_at_pos.setSelected(True)
                self._show_context_menu(top_item_at_pos, event.screenPos()) 
            else: 
                self.clearSelection() 
        else: 
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, event.scenePos()))
        else: 
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            if self._mouse_press_items_positions: 
                moved_items_data = []
                for item, old_pos in self._mouse_press_items_positions.items():
                    new_pos = item.pos() 
                    if self.snap_to_grid_enabled:
                        snapped_x = round(new_pos.x() / self.grid_size) * self.grid_size
                        snapped_y = round(new_pos.y() / self.grid_size) * self.grid_size
                        if new_pos.x() != snapped_x or new_pos.y() != snapped_y:
                            item.setPos(snapped_x, snapped_y) 
                            new_pos = QPointF(snapped_x, snapped_y) 
                    if (new_pos - old_pos).manhattanLength() > 0.1: 
                        moved_items_data.append((item, new_pos)) 
                if moved_items_data:
                    cmd = MoveItemsCommand(moved_items_data) 
                    self.undo_stack.push(cmd)
                self._mouse_press_items_positions.clear() 
        super().mouseReleaseEvent(event) 

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        items_at_pos = self.items(event.scenePos())
        item_to_edit = next((item for item in items_at_pos if isinstance(item, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem))), None)
        if item_to_edit:
            self.edit_item_properties(item_to_edit)
        else:
            super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, item, global_pos):
        menu = QMenu()
        menu.setStyleSheet(""" QMenu { background-color: #FAFAFA; border: 1px solid #D0D0D0; } QMenu::item { padding: 5px 20px 5px 20px; } QMenu::item:selected { background-color: #E0E0E0; color: black; } QMenu::separator { height: 1px; background-color: #D0D0D0; margin: 5px; } """)
        edit_action = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        delete_action = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")
        action = menu.exec_(global_pos)
        if action == edit_action: self.edit_item_properties(item)
        elif action == delete_action:
            if not item.isSelected(): self.clearSelection() ; item.setSelected(True)
            self.delete_selected_items() 

    def edit_item_properties(self, item):
        old_props = item.get_data() 
        dialog_executed_and_accepted = False
        new_props = {} # Initialize

        if isinstance(item, GraphicsStateItem):
            dialog = StatePropertiesDialog(parent=self.parent_window, current_properties=old_props)
            if dialog.exec_() == QDialog.Accepted:
                dialog_executed_and_accepted = True; new_props = dialog.get_properties()
                if new_props['name'] != old_props['name'] and self.get_state_by_name(new_props['name']):
                    QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state with the name '{new_props['name']}' already exists.")
                    return 
        elif isinstance(item, GraphicsTransitionItem):
            dialog = TransitionPropertiesDialog(parent=self.parent_window, current_properties=old_props)
            if dialog.exec_() == QDialog.Accepted:
                dialog_executed_and_accepted = True; new_props = dialog.get_properties()
        elif isinstance(item, GraphicsCommentItem):
            dialog = CommentPropertiesDialog(parent=self.parent_window, current_properties=old_props)
            if dialog.exec_() == QDialog.Accepted:
                dialog_executed_and_accepted = True; new_props = dialog.get_properties()
        else: return 

        if dialog_executed_and_accepted:
            final_new_props = old_props.copy(); final_new_props.update(new_props)
            cmd = EditItemPropertiesCommand(item, old_props, final_new_props, f"Edit {type(item).__name__} Properties")
            self.undo_stack.push(cmd)
            item_name_for_log = final_new_props.get('name', final_new_props.get('event', final_new_props.get('text', 'Item')))
            self.log_function(f"Properties updated for: {item_name_for_log}")
        self.update()

    def _add_item_interactive(self, pos: QPointF, item_type: str, name_prefix:str="Item", initial_data:dict=None):
        current_item = None
        initial_data = initial_data or {}
        is_initial_state_from_drag = initial_data.get('is_initial', False)
        is_final_state_from_drag = initial_data.get('is_final', False)

        if item_type == "State" or item_type == "Initial State" or item_type == "Final State":
            i = 1; base_name = name_prefix if name_prefix != "Item" else "State"
            while self.get_state_by_name(f"{base_name}{i}"): i += 1
            default_name = f"{base_name}{i}"
            state_name_from_input = initial_data.get('name', default_name)
            
            if 'name' not in initial_data: # Not from a pre-filled drag drop or specific creation command
                temp_name, ok = QInputDialog.getText(self.parent_window, "New State", "Enter state name:", text=default_name)
                if not (ok and temp_name and temp_name.strip()):
                    self.log_function(f"State addition cancelled."); self.set_mode("select"); return
                state_name_from_input = temp_name.strip()

            if self.get_state_by_name(state_name_from_input) and state_name_from_input != default_name:
                QMessageBox.warning(self.parent_window, "Duplicate Name", f"State '{state_name_from_input}' already exists."); self.set_mode("select"); return

            initial_dialog_props = {'name': state_name_from_input,'is_initial': is_initial_state_from_drag, 'is_final': is_final_state_from_drag}
            initial_dialog_props.update(initial_data) # Overlay any other passed initial_data
            
            props_dialog = StatePropertiesDialog(self.parent_window, current_properties=initial_dialog_props, is_new_state=True)
            if props_dialog.exec_() == QDialog.Accepted:
                final_props = props_dialog.get_properties()
                if final_props['name'] != state_name_from_input and self.get_state_by_name(final_props['name']):
                     QMessageBox.warning(self.parent_window, "Duplicate Name", f"State '{final_props['name']}' already exists."); self.set_mode("select"); return
                current_item = GraphicsStateItem(pos.x(), pos.y(), 120, 60, final_props['name'], final_props['is_initial'], final_props['is_final'], final_props.get('color'), final_props.get('entry_action',""), final_props.get('during_action',""), final_props.get('exit_action',""), final_props.get('description',""))
            else: self.set_mode("select"); return
                
        elif item_type == "Comment":
            initial_text = initial_data.get('text', "Comment")
            text, ok = QInputDialog.getMultiLineText(self.parent_window, "New Comment", "Enter comment text:", initial_text)
            if ok and text: current_item = GraphicsCommentItem(pos.x(), pos.y(), text)
            else: self.set_mode("select"); return
        else:
            self.log_function(f"Unknown item type for addition: {item_type}"); return

        if current_item:
            cmd = AddItemCommand(self, current_item, f"Add {item_type}")
            self.undo_stack.push(cmd)
            log_name = getattr(current_item, 'text_label', getattr(current_item, 'toPlainText', lambda: 'Item'))()
            self.log_function(f"Added {item_type}: {log_name} at ({pos.x():.0f},{pos.y():.0f})")
        
        if self.current_mode != "select" and item_type != "Transition": self.set_mode("select")


    def _handle_transition_click(self, clicked_state_item: GraphicsStateItem, click_pos: QPointF):
        if not self.transition_start_item: 
            self.transition_start_item = clicked_state_item
            if not self._temp_transition_line:
                self._temp_transition_line = QGraphicsLineItem() 
                self._temp_transition_line.setPen(QPen(Qt.black, 2, Qt.DashLine))
                self.addItem(self._temp_transition_line)
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, click_pos)) 
            self.log_function(f"Transition started from: {clicked_state_item.text_label}. Click target state.")
        else: 
            if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
            initial_props = {'event': "", 'condition': "", 'action': "", 'color': None, 'description':"", 'control_offset_x':0, 'control_offset_y':0}
            dialog = TransitionPropertiesDialog(self.parent_window, current_properties=initial_props, is_new_transition=True)
            if dialog.exec_() == QDialog.Accepted:
                props = dialog.get_properties()
                new_transition = GraphicsTransitionItem(self.transition_start_item, clicked_state_item, props['event'], props['condition'], props['action'], props.get('color'), props.get('description', ""))
                new_transition.set_control_point_offset(QPointF(props['control_offset_x'],props['control_offset_y']))
                cmd = AddItemCommand(self, new_transition, "Add Transition")
                self.undo_stack.push(cmd)
                self.log_function(f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{new_transition._compose_label_string()}]")
            else: self.log_function("Transition addition cancelled.")
            self.transition_start_item = None ; self.set_mode("select") 

    def keyPressEvent(self, event: QKeyEvent): 
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            if self.selectedItems(): self.delete_selected_items()
        elif event.key() == Qt.Key_Escape:
            if self.current_mode == "transition" and self.transition_start_item:
                self.transition_start_item = None
                if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
                self.log_function("Transition drawing cancelled by Escape."); self.set_mode("select")
            elif self.current_mode != "select": self.set_mode("select")
            else: self.clearSelection()
        else: super().keyPressEvent(event)

    def delete_selected_items(self):
        selected = self.selectedItems()
        if not selected: return
        items_to_delete_with_related = set() 
        for item in selected:
            items_to_delete_with_related.add(item) 
            if isinstance(item, GraphicsStateItem):
                for scene_item in self.items(): 
                    if isinstance(scene_item, GraphicsTransitionItem):
                        if scene_item.start_item == item or scene_item.end_item == item:
                            items_to_delete_with_related.add(scene_item)
        if items_to_delete_with_related:
            cmd = RemoveItemsCommand(self, list(items_to_delete_with_related), "Delete Items")
            self.undo_stack.push(cmd)
            self.log_function(f"Queued deletion of {len(items_to_delete_with_related)} item(s).")
            self.clearSelection() 

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent): 
        if event.mimeData().hasFormat(DRAGGABLE_TOOL_MIME_TYPE): 
            event.setAccepted(True); event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent): 
        if event.mimeData().hasFormat(DRAGGABLE_TOOL_MIME_TYPE):
            event.acceptProposedAction()
        else: super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent): 
        pos = event.scenePos()
        if event.mimeData().hasFormat(DRAGGABLE_TOOL_MIME_TYPE):
            item_type_data = event.mimeData().text() # "State", "Initial State", "Transition", "Comment"
            grid_x = round(pos.x() / self.grid_size) * self.grid_size
            grid_y = round(pos.y() / self.grid_size) * self.grid_size
            initial_props = {}
            item_type_to_add = None
            name_prefix_for_add = "Item"

            if item_type_data == "State":
                item_type_to_add = "State"; name_prefix_for_add = "State"
                grid_x -= 60; grid_y -= 30
            elif item_type_data == "Initial State":
                item_type_to_add = "State"; name_prefix_for_add = "Initial"
                initial_props['is_initial'] = True; grid_x -= 60; grid_y -= 30
            elif item_type_data == "Final State":
                item_type_to_add = "State"; name_prefix_for_add = "Final"
                initial_props['is_final'] = True; grid_x -= 60; grid_y -= 30
            elif item_type_data == "Comment":
                item_type_to_add = "Comment"; name_prefix_for_add = "Note"
            elif item_type_data == "Transition": # Special handling for Transition drop
                self.set_mode("transition") # Switch to transition mode
                self.log_function("Transition tool activated by drop. Click source then target state.")
                event.acceptProposedAction()
                return # Mode change is the action for transition drop
            else:
                event.ignore(); return

            if item_type_to_add:
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type_to_add, name_prefix_for_add, initial_props)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def get_diagram_data(self):
        data = {'states': [], 'transitions': [], 'comments': []} 
        for item in self.items():
            if isinstance(item, GraphicsStateItem): data['states'].append(item.get_data())
            elif isinstance(item, GraphicsTransitionItem):
                if item.start_item and item.end_item: data['transitions'].append(item.get_data())
                else: self.log_function(f"Warning: Skipping save of orphaned/invalid transition: '{item._compose_label_string()}'.")
            elif isinstance(item, GraphicsCommentItem): data['comments'].append(item.get_data())
        return data

    def load_diagram_data(self, data):
        self.clear(); self.set_dirty(False) 
        state_items_map = {} 
        for state_data in data.get('states', []):
            state_item = GraphicsStateItem(state_data['x'], state_data['y'],state_data.get('width', 120), state_data.get('height', 60),state_data['name'],state_data.get('is_initial', False), state_data.get('is_final', False),state_data.get('color'),state_data.get('entry_action',""), state_data.get('during_action',""),state_data.get('exit_action',""), state_data.get('description',""))
            self.addItem(state_item); state_items_map[state_data['name']] = state_item
        for trans_data in data.get('transitions', []):
            src_item = state_items_map.get(trans_data['source']); tgt_item = state_items_map.get(trans_data['target'])
            if src_item and tgt_item:
                trans_item = GraphicsTransitionItem(src_item, tgt_item, trans_data.get('event',""), trans_data.get('condition',""), trans_data.get('action',""),trans_data.get('color'), trans_data.get('description',""))
                trans_item.set_control_point_offset(QPointF(trans_data.get('control_offset_x', 0),trans_data.get('control_offset_y', 0)))
                self.addItem(trans_item)
            else:
                label_info = trans_data.get('event', '') + trans_data.get('condition', '') + trans_data.get('action', '')
                self.log_function(f"Warning (Load): Could not link transition '{label_info}'. Missing states: Src='{trans_data['source']}', Tgt='{trans_data['target']}'.")
        for comment_data in data.get('comments', []):
            comment_item = GraphicsCommentItem(comment_data['x'], comment_data['y'], comment_data.get('text', ""))
            comment_item.setTextWidth(comment_data.get('width', 150))
            self.addItem(comment_item)
        self.set_dirty(False); self.undo_stack.clear()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect) 
        view_rect = self.views()[0].viewport().rect() if self.views() else rect
        visible_scene_rect = self.views()[0].mapToScene(view_rect).boundingRect() if self.views() else rect
        left = int(visible_scene_rect.left()); right = int(visible_scene_rect.right())
        top = int(visible_scene_rect.top()); bottom = int(visible_scene_rect.bottom())
        first_left = left - (left % self.grid_size); first_top = top - (top % self.grid_size)
        
        painter.setPen(self.grid_pen_light)
        for x_coord in range(first_left, right, self.grid_size):
            if x_coord % (self.grid_size * 5) != 0: painter.drawLine(x_coord, top, x_coord, bottom) 
        for y_coord in range(first_top, bottom, self.grid_size):
            if y_coord % (self.grid_size * 5) != 0: painter.drawLine(left, y_coord, right, y_coord)

        major_grid_size = self.grid_size * 5
        first_major_left = left - (left % major_grid_size); first_major_top = top - (top % major_grid_size)
        painter.setPen(self.grid_pen_dark) 
        for x_coord in range(first_major_left, right, major_grid_size): painter.drawLine(x_coord, top, x_coord, bottom)
        for y_coord in range(first_major_top, bottom, major_grid_size): painter.drawLine(left, y_coord, right, y_coord)


# --- Zoomable Graphics View ---
# (ZoomableView largely unchanged from 1.4.0)
class ZoomableView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag) 
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.zoom_level = 0 
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._is_panning_with_space = False 
        self._is_panning_with_mouse_button = False 
        self._last_pan_point = QPoint()

    def wheelEvent(self, event: QWheelEvent): 
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y(); factor = 1.12 if delta > 0 else 1 / 1.12
            new_zoom_level = self.zoom_level + (1 if delta > 0 else -1)
            if -15 <= new_zoom_level <= 25: 
                self.scale(factor, factor); self.zoom_level = new_zoom_level
            event.accept() 
        else: super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = True; self._last_pan_point = event.pos() 
            self.setCursor(Qt.OpenHandCursor); event.accept()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal: 
            self.scale(1.12, 1.12); self.zoom_level +=1
        elif event.key() == Qt.Key_Minus: 
            self.scale(1/1.12, 1/1.12); self.zoom_level -=1
        elif event.key() == Qt.Key_0 or event.key() == Qt.Key_Asterisk: 
             self.resetTransform(); self.zoom_level = 0
        else: super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = False
            if not self._is_panning_with_mouse_button: self._restore_cursor_to_scene_mode()
            event.accept()
        else: super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent): 
        if event.button() == Qt.MiddleButton or (self._is_panning_with_space and event.button() == Qt.LeftButton):
            self._last_pan_point = event.pos() ; self.setCursor(Qt.ClosedHandCursor)
            self._is_panning_with_mouse_button = True ; event.accept()
        else:
            self._is_panning_with_mouse_button = False; super().mousePressEvent(event) 

    def mouseMoveEvent(self, event: QMouseEvent): 
        if self._is_panning_with_mouse_button:
            delta_view = event.pos() - self._last_pan_point; self._last_pan_point = event.pos()
            hsbar = self.horizontalScrollBar(); vsbar = self.verticalScrollBar()
            hsbar.setValue(hsbar.value() - delta_view.x()); vsbar.setValue(vsbar.value() - delta_view.y())
            event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent): 
        if self._is_panning_with_mouse_button and (event.button() == Qt.MiddleButton or (self._is_panning_with_space and event.button() == Qt.LeftButton)):
            self._is_panning_with_mouse_button = False 
            if self._is_panning_with_space: self.setCursor(Qt.OpenHandCursor)
            else: self._restore_cursor_to_scene_mode()
            event.accept()
        else: super().mouseReleaseEvent(event)
            
    def _restore_cursor_to_scene_mode(self):
        current_scene_mode = self.scene().current_mode if self.scene() else "select"
        if current_scene_mode == "select": self.setCursor(Qt.ArrowCursor)
        elif current_scene_mode == "state" or current_scene_mode == "comment": self.setCursor(Qt.CrossCursor)
        elif current_scene_mode == "transition": self.setCursor(Qt.PointingHandCursor)
        else: self.setCursor(Qt.ArrowCursor)


# --- Dialogs ---
class StatePropertiesDialog(QDialog):
    PALETTE_COLORS = [
        "#FFADAD", "#FFD6A5", "#FDFFB6", "#CAFFBF", # Pastels Red, Orange, Yellow, Green
        "#9BF6FF", "#A0C4FF", "#BDB2FF", "#FFC6FF"  # Pastels Cyan, Blue, Purple, Pink
    ]
    def __init__(self, parent=None, current_properties=None, is_new_state=False):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Props"))
        
        layout = QFormLayout(self); layout.setSpacing(10)
        p = current_properties or {}
        self.name_edit = QLineEdit(p.get('name', "StateName"))
        self.is_initial_cb = QCheckBox("Is Initial State"); self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Is Final State"); self.is_final_cb.setChecked(p.get('is_final', False))
        
        self.current_color = QColor(p.get('color', "#BEDFFF")) # Default: Light Blue

        color_row_widget = QWidget()
        color_row_layout = QHBoxLayout(color_row_widget)
        color_row_layout.setContentsMargins(0,0,0,0); color_row_layout.setSpacing(5)
        
        self.color_button = QPushButton("Choose Custom Color...")
        self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_custom_color)
        color_row_layout.addWidget(self.color_button)

        palette_widget = QWidget()
        palette_layout = QHBoxLayout(palette_widget)
        palette_layout.setContentsMargins(0,0,0,0); palette_layout.setSpacing(2)
        for color_hex in self.PALETTE_COLORS:
            palette_btn = QPushButton(); palette_btn.setFixedSize(22, 22)
            palette_btn.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #AAAAAA;")
            palette_btn.setToolTip(color_hex)
            palette_btn.clicked.connect(lambda checked, c=QColor(color_hex): self._set_color_from_palette(c))
            palette_layout.addWidget(palette_btn)
        palette_layout.addStretch()
        color_row_layout.addWidget(palette_widget)

        self.entry_action_edit = QTextEdit(p.get('entry_action', "")); self.entry_action_edit.setFixedHeight(60)
        self.during_action_edit = QTextEdit(p.get('during_action', "")); self.during_action_edit.setFixedHeight(60)
        self.exit_action_edit = QTextEdit(p.get('exit_action', "")); self.exit_action_edit.setFixedHeight(60)
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(80)

        layout.addRow("Name:", self.name_edit)
        layout.addRow(self.is_initial_cb); layout.addRow(self.is_final_cb)
        layout.addRow("Color:", color_row_widget)
        layout.addRow("Entry Action:", self.entry_action_edit)
        layout.addRow("During Action:", self.during_action_edit)
        layout.addRow("Exit Action:", self.exit_action_edit)
        layout.addRow("Description:", self.description_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addRow(buttons); self.setMinimumWidth(450)
        if is_new_state: self.name_edit.selectAll()

    def _choose_custom_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select State Color")
        if color.isValid(): self._set_color_from_palette(color) # Reuse logic

    def _set_color_from_palette(self, color: QColor):
        self.current_color = color
        self._update_color_button_style()

    def _update_color_button_style(self):
        palette = self.color_button.palette()
        palette.setColor(self.color_button.backgroundRole(), self.current_color)
        # For text contrast:
        brightness = (self.current_color.red() * 299 + self.current_color.green() * 587 + self.current_color.blue() * 114) / 1000
        text_color = Qt.black if brightness > 125 else Qt.white
        palette.setColor(self.color_button.foregroundRole(), text_color)
        self.color_button.setPalette(palette)
        self.color_button.setAutoFillBackground(True)
        self.color_button.setStyleSheet(f"QPushButton {{ background-color: {self.current_color.name()}; color: {text_color.name()}; border: 1px solid #888; padding: 4px; }}")

    def get_properties(self):
        return {
            'name': self.name_edit.text().strip(), 'is_initial': self.is_initial_cb.isChecked(),
            'is_final': self.is_final_cb.isChecked(), 'color': self.current_color.name(),
            'entry_action': self.entry_action_edit.toPlainText().strip(),
            'during_action': self.during_action_edit.toPlainText().strip(),
            'exit_action': self.exit_action_edit.toPlainText().strip(),
            'description': self.description_edit.toPlainText().strip()
        }

class TransitionPropertiesDialog(QDialog):
    PALETTE_COLORS = [ # Same palette for consistency or can be different
        "#D0D0D0", "#A9A9A9", "#708090", "#2F4F4F", # Grays and Dark Slates
        "#8B0000", "#006400", "#00008B", "#4B0082"  # Dark Red, Green, Blue, Indigo
    ]
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Props"))
        
        layout = QFormLayout(self); layout.setSpacing(10)
        p = current_properties or {}
        self.event_edit = QLineEdit(p.get('event', "")); self.event_edit.setPlaceholderText("e.g., mouseClick")
        self.condition_edit = QLineEdit(p.get('condition', "")); self.condition_edit.setPlaceholderText("e.g., data > 10")
        self.action_edit = QTextEdit(p.get('action', "")); self.action_edit.setPlaceholderText("e.g., counter++;"); self.action_edit.setFixedHeight(60)

        self.current_color = QColor(p.get('color', "#007878")) # Default: Dark Teal

        color_row_widget = QWidget()
        color_row_layout = QHBoxLayout(color_row_widget)
        color_row_layout.setContentsMargins(0,0,0,0); color_row_layout.setSpacing(5)
        
        self.color_button = QPushButton("Choose Custom Color...")
        self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_custom_color)
        color_row_layout.addWidget(self.color_button)

        palette_widget = QWidget()
        palette_layout = QHBoxLayout(palette_widget)
        palette_layout.setContentsMargins(0,0,0,0); palette_layout.setSpacing(2)
        for color_hex in self.PALETTE_COLORS:
            palette_btn = QPushButton(); palette_btn.setFixedSize(22, 22)
            palette_btn.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #AAAAAA;")
            palette_btn.setToolTip(color_hex)
            palette_btn.clicked.connect(lambda checked, c=QColor(color_hex): self._set_color_from_palette(c))
            palette_layout.addWidget(palette_btn)
        palette_layout.addStretch()
        color_row_layout.addWidget(palette_widget)

        self.offset_perp_spin = QSpinBox(); self.offset_perp_spin.setRange(-800, 800); self.offset_perp_spin.setSingleStep(10)
        self.offset_perp_spin.setValue(int(p.get('control_offset_x', 0))); self.offset_perp_spin.setToolTip("Perpendicular curve bend.")
        self.offset_tang_spin = QSpinBox(); self.offset_tang_spin.setRange(-800, 800); self.offset_tang_spin.setSingleStep(10)
        self.offset_tang_spin.setValue(int(p.get('control_offset_y', 0))); self.offset_tang_spin.setToolTip("Tangential curve midpoint shift.")
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(80)

        layout.addRow("Event Trigger:", self.event_edit)
        layout.addRow("Condition (Guard):", self.condition_edit)
        layout.addRow("Transition Action:", self.action_edit)
        layout.addRow("Color:", color_row_widget)
        layout.addRow("Curve Bend:", self.offset_perp_spin)
        layout.addRow("Curve Shift:", self.offset_tang_spin)
        layout.addRow("Description:", self.description_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addRow(buttons); self.setMinimumWidth(480)
        if is_new_transition: self.event_edit.setFocus()

    def _choose_custom_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select Transition Color")
        if color.isValid(): self._set_color_from_palette(color)

    def _set_color_from_palette(self, color: QColor):
        self.current_color = color
        self._update_color_button_style()

    def _update_color_button_style(self):
        palette = self.color_button.palette()
        palette.setColor(self.color_button.backgroundRole(), self.current_color)
        brightness = (self.current_color.red() * 299 + self.current_color.green() * 587 + self.current_color.blue() * 114) / 1000
        text_color = Qt.black if brightness > 125 else Qt.white
        palette.setColor(self.color_button.foregroundRole(), text_color)
        self.color_button.setPalette(palette)
        self.color_button.setAutoFillBackground(True)
        self.color_button.setStyleSheet(f"QPushButton {{ background-color: {self.current_color.name()}; color: {text_color.name()}; border: 1px solid #888; padding: 4px; }}")


    def get_properties(self):
        return {
            'event': self.event_edit.text().strip(), 'condition': self.condition_edit.text().strip(),
            'action': self.action_edit.toPlainText().strip(), 'color': self.current_color.name(),
            'control_offset_x': self.offset_perp_spin.value(), 'control_offset_y': self.offset_tang_spin.value(),
            'description': self.description_edit.toPlainText().strip()
        }

class CommentPropertiesDialog(QDialog):
    # (Unchanged from 1.4.0 as no color selection was specific for it)
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent)
        self.setWindowTitle("Comment Properties")
        p = current_properties or {}
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit(p.get('text', "Comment")); self.text_edit.setMinimumHeight(100)
        layout.addWidget(QLabel("Comment Text:")); layout.addWidget(self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons); self.setMinimumWidth(300)

    def get_properties(self):
        return {'text': self.text_edit.toPlainText()}


class MatlabSettingsDialog(QDialog):
    # (Unchanged from 1.4.0)
    def __init__(self, matlab_connection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings"); self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg")); self.setMinimumWidth(550)
        main_layout = QVBoxLayout(self)
        path_group = QGroupBox("MATLAB Executable Path"); path_form_layout = QFormLayout() 
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path); self.path_edit.setPlaceholderText("e.g., C:\\Program Files\\MATLAB\\R202Xy\\bin\\matlab.exe")
        path_form_layout.addRow("Path:", self.path_edit)
        btn_layout = QHBoxLayout()
        auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_FileDialogContentsView, "Det"), "Auto-detect"); auto_detect_btn.clicked.connect(self._auto_detect); auto_detect_btn.setToolTip("Attempt to find MATLAB installations.")
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), "Browse..."); browse_btn.clicked.connect(self._browse); browse_btn.setToolTip("Browse for MATLAB executable.")
        btn_layout.addWidget(auto_detect_btn); btn_layout.addWidget(browse_btn); btn_layout.addStretch()
        path_v_layout = QVBoxLayout(); path_v_layout.addLayout(path_form_layout); path_v_layout.addLayout(btn_layout)
        path_group.setLayout(path_v_layout); main_layout.addWidget(path_group)
        test_group = QGroupBox("Connection Test"); test_layout = QVBoxLayout()
        self.test_status_label = QLabel("Status: Unknown"); self.test_status_label.setWordWrap(True); self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        test_btn = QPushButton(get_standard_icon(QStyle.SP_CommandLink, "Test"), "Test Connection"); test_btn.clicked.connect(self._test_connection_and_update_label); test_btn.setToolTip("Test connection to the specified MATLAB path.")
        test_layout.addWidget(test_btn); test_layout.addWidget(self.test_status_label); test_group.setLayout(test_layout); main_layout.addWidget(test_group)
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close")
        dialog_buttons.accepted.connect(self._apply_settings); dialog_buttons.rejected.connect(self.reject); main_layout.addWidget(dialog_buttons)
        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        if self.matlab_connection.matlab_path and self.matlab_connection.connected: self._update_test_label_from_signal(True, f"Connected: {self.matlab_connection.matlab_path}")
        elif self.matlab_connection.matlab_path: self._update_test_label_from_signal(False, f"Path previously set ({self.matlab_connection.matlab_path}), but connection unconfirmed or failed.")
        else: self._update_test_label_from_signal(False, "MATLAB path not set.")
    def _auto_detect(self): self.test_status_label.setText("Status: Auto-detecting MATLAB..."); self.test_status_label.setStyleSheet(""); QApplication.processEvents(); self.matlab_connection.detect_matlab()
    def _browse(self):
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        start_dir = os.path.dirname(self.path_edit.text()) if self.path_edit.text() and os.path.isdir(os.path.dirname(self.path_edit.text())) else QDir.homePath()
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path: self.path_edit.setText(path); self._update_test_label_from_signal(False, "Path changed. Test or Apply.")
    def _test_connection_and_update_label(self):
        path = self.path_edit.text().strip()
        if not path: self._update_test_label_from_signal(False, "MATLAB path is empty."); return
        self.test_status_label.setText("Status: Testing connection..."); self.test_status_label.setStyleSheet(""); QApplication.processEvents()
        if self.matlab_connection.set_matlab_path(path): self.matlab_connection.test_connection()
    def _update_test_label_from_signal(self, success, message):
        status_prefix = "Status: "; color_style = "color: #B22222; font-weight: bold;"
        if success: 
            status_prefix = "Status: Connected! " if "successful" in message else "Status: Path validated. "
            color_style = "color: #006400; font-weight: bold;"
        self.test_status_label.setText(status_prefix + message); self.test_status_label.setStyleSheet(color_style)
        if success and self.matlab_connection.matlab_path: self.path_edit.setText(self.matlab_connection.matlab_path) 
    def _apply_settings(self): path = self.path_edit.text().strip(); self.matlab_connection.set_matlab_path(path) ; self.accept()


# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file_path = None
        self.last_generated_model_path = None 
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)
        
        self.scene = DiagramScene(self.undo_stack, self) 
        self.scene.set_log_function(self.log_message)
        self.scene.modifiedStatusChanged.connect(self.setWindowModified) 
        self.scene.modifiedStatusChanged.connect(self._update_window_title) 

        self.init_ui()
        self._update_matlab_status_display(False, "Initializing. Configure in Simulation menu or attempt auto-detect.")
        
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished) 

        self._update_window_title() 
        self.on_new_file(silent=True) 

        self.scene.selectionChanged.connect(self._update_properties_dock)
        self._update_properties_dock()

    def init_ui(self):
        self.setGeometry(50, 50, 1600, 1000) 
        self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "BSM")) 
        
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_docks() 
        self._create_central_widget() 

        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state() 
        self._update_undo_redo_actions_enable_state()
        
        self.select_mode_action.trigger() 

    def _create_actions(self):
        def _s(attr, fb=None): return getattr(QStyle,attr,getattr(QStyle,fb,QStyle.SP_CustomBase))
        self.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "New"), "&New", self, shortcut=QKeySequence.New, statusTip="Create a new file", triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "Opn"), "&Open...", self, shortcut=QKeySequence.Open, statusTip="Open an existing file", triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Sav"), "&Save", self, shortcut=QKeySequence.Save, statusTip="Save the current file", triggered=self.on_save_file)
        self.save_as_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton),"Save &As...", self, shortcut=QKeySequence.SaveAs, statusTip="Save current file with new name", triggered=self.on_save_file_as)
        self.exit_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", self, shortcut=QKeySequence.Quit, statusTip="Exit application", triggered=self.close)
        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo"); self.undo_action.setShortcut(QKeySequence.Undo); self.undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "Un")); self.undo_action.setStatusTip("Undo last action")
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo"); self.redo_action.setShortcut(QKeySequence.Redo); self.redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "Re")); self.redo_action.setStatusTip("Redo last undone action")
        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_actions_enable_state); self.undo_stack.canRedoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.select_all_action = QAction(get_standard_icon(_s("SP_FileDialogDetailedView"), "All"), "Select &All", self, shortcut=QKeySequence.SelectAll, statusTip="Select all items", triggered=self.on_select_all)
        self.delete_action = QAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "&Delete", self, shortcut=QKeySequence.Delete, statusTip="Delete selected items", triggered=self.on_delete_selected)
        
        self.mode_action_group = QActionGroup(self); self.mode_action_group.setExclusive(True)
        self.select_mode_action = QAction(QIcon.fromTheme("edit-select", get_standard_icon(_s("SP_ArrowCursor", "SP_PointingHandCursor"), "Sel")), "Select/Move", self, checkable=True, statusTip="Mode: Select/Move", triggered=lambda: self.scene.set_mode("select"))
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", get_standard_icon(_s("SP_FileDialogNewFolder", "SP_FileIcon"), "St")), "Add State", self, checkable=True, statusTip="Mode: Add State", triggered=lambda: self.scene.set_mode("state"))
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", get_standard_icon(_s("SP_FileDialogBack", "SP_ArrowRight"), "Tr")), "Add Transition", self, checkable=True, statusTip="Mode: Add Transition", triggered=lambda: self.scene.set_mode("transition"))
        self.add_comment_mode_action = QAction(QIcon.fromTheme("insert-text", get_standard_icon(_s("SP_MessageBoxInformation", "SP_FileLinkIcon"), "Cm")), "Add Comment", self, checkable=True, statusTip="Mode: Add Comment", triggered=lambda: self.scene.set_mode("comment"))
        for act in [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action]: self.mode_action_group.addAction(act)
        self.select_mode_action.setChecked(True)

        self.export_simulink_action = QAction(get_standard_icon(QStyle.SP_ArrowRight, "->M"), "&Export to Simulink...", self, statusTip="Generate Simulink model", triggered=self.on_export_simulink)
        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation...", self, statusTip="Run Simulink model", triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cde"), "Generate &Code (C/C++)...", self, statusTip="Generate C/C++ code", triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(_s("SP_ComputerIcon","SP_FileDialogDetailedView"), "Cfg"), "&MATLAB Settings...", self, statusTip="Configure MATLAB connection", triggered=self.on_matlab_settings)
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, statusTip=f"About {APP_NAME}", triggered=self.on_about)

    def _create_menus(self):
        menu_bar = self.menuBar(); menu_bar.setStyleSheet("QMenuBar { background-color: #E8E8E8; } QMenu::item:selected { background-color: #D0D0D0; }")
        file_menu = menu_bar.addMenu("&File"); file_menu.addActions([self.new_action, self.open_action, self.save_action, self.save_as_action]); file_menu.addSeparator(); file_menu.addAction(self.export_simulink_action); file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        edit_menu = menu_bar.addMenu("&Edit"); edit_menu.addActions([self.undo_action, self.redo_action]); edit_menu.addSeparator(); edit_menu.addActions([self.delete_action, self.select_all_action]); edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_DesktopIcon, "Mode"),"Interaction Mode"); mode_menu.addActions([self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action])
        sim_menu = menu_bar.addMenu("&Simulation"); sim_menu.addActions([self.run_simulation_action, self.generate_code_action]); sim_menu.addSeparator(); sim_menu.addAction(self.matlab_settings_action)
        self.view_menu = menu_bar.addMenu("&View")
        help_menu = menu_bar.addMenu("&Help"); help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(28,28) 
        def setup_toolbar(name, obj_name, actions):
            tb = self.addToolBar(name); tb.setObjectName(obj_name); tb.setIconSize(icon_size); tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon); tb.addActions(actions); return tb
        file_toolbar = setup_toolbar("File", "FileToolBar", [self.new_action, self.open_action, self.save_action])
        edit_toolbar = setup_toolbar("Edit", "EditToolBar", [self.undo_action, self.redo_action])
        edit_toolbar.addSeparator(); edit_toolbar.addAction(self.delete_action)
        tools_tb = setup_toolbar("Interaction Tools", "ToolsToolBar", [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action])
        self.addToolBarBreak()
        sim_toolbar = setup_toolbar("Simulation Tools", "SimulationToolBar", [self.export_simulink_action, self.run_simulation_action, self.generate_code_action])

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self); self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready"); self.status_bar.addWidget(self.status_label, 1) 
        self.matlab_status_label = QLabel("MATLAB: Init..."); self.matlab_status_label.setToolTip("MATLAB connection status."); self.matlab_status_label.setStyleSheet("padding: 0 10px 0 5px;")
        self.status_bar.addPermanentWidget(self.matlab_status_label)
        self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0,0); self.progress_bar.setVisible(False); self.progress_bar.setMaximumWidth(180); self.progress_bar.setTextVisible(False) 
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)
        self.tools_dock = QDockWidget("Tools", self); self.tools_dock.setObjectName("ToolsDock"); self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_widget = QWidget(); tools_main_layout = QVBoxLayout(tools_widget); tools_main_layout.setSpacing(10); tools_main_layout.setContentsMargins(8,8,8,8)
        
        mode_group_box = QGroupBox("Interaction Modes"); mode_layout = QVBoxLayout(); mode_layout.setSpacing(5)
        self.toolbox_select_button = QToolButton(); self.toolbox_select_button.setDefaultAction(self.select_mode_action)
        self.toolbox_add_state_button = QToolButton(); self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action)
        self.toolbox_transition_button = QToolButton(); self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action)
        self.toolbox_add_comment_button = QToolButton(); self.toolbox_add_comment_button.setDefaultAction(self.add_comment_mode_action)
        for btn in [self.toolbox_select_button, self.toolbox_add_state_button, self.toolbox_transition_button, self.toolbox_add_comment_button]:
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(20,20)); mode_layout.addWidget(btn)
        mode_group_box.setLayout(mode_layout); tools_main_layout.addWidget(mode_group_box)

        draggable_group_box = QGroupBox("Drag to Canvas"); draggable_layout = QVBoxLayout(); draggable_layout.setSpacing(5)
        common_style = "QPushButton { background-color: #E8F0FE; color: #1C3A5D; border: 1px solid #A9CCE3; padding: 6px; }" "QPushButton:hover { background-color: #D8E0EE; }" "QPushButton:pressed { background-color: #C8D0DE; }"
        btn_data = [
            ("State", "State", QStyle.SP_FileDialogNewFolder, "St"),
            ("Initial State", "Initial State", QStyle.SP_ToolBarHorizontalExtensionButton, "I"),
            ("Final State", "Final State", QStyle.SP_DialogOkButton, "F"),
            ("Transition", "Transition", QStyle.SP_FileDialogBack, "Tr"), # New Draggable Transition Tool
            ("Comment", "Comment", QStyle.SP_MessageBoxInformation, "Cm")
        ]
        for text, item_type, icon_enum, fallback in btn_data:
            drag_btn = DraggableToolButton(text, DRAGGABLE_TOOL_MIME_TYPE, item_type, common_style)
            drag_btn.setIcon(get_standard_icon(icon_enum, fallback)); drag_btn.setIconSize(QSize(22,22)); draggable_layout.addWidget(drag_btn)
        draggable_group_box.setLayout(draggable_layout); tools_main_layout.addWidget(draggable_group_box)
        
        tools_main_layout.addStretch(); self.tools_dock.setWidget(tools_widget); self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock); self.view_menu.addAction(self.tools_dock.toggleViewAction())

        self.log_dock = QDockWidget("Log Output", self); self.log_dock.setObjectName("LogDock"); self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.log_output = QTextEdit(); self.log_output.setReadOnly(True); self.log_output.setFont(QFont("Consolas", 9)); self.log_output.setStyleSheet("QTextEdit { background-color: #FDFDFD; color: #333; border: 1px solid #DDD; }")
        self.log_dock.setWidget(self.log_output); self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock); self.view_menu.addAction(self.log_dock.toggleViewAction())
        
        self.properties_dock = QDockWidget("Properties", self); self.properties_dock.setObjectName("PropertiesDock"); self.properties_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        properties_widget_main = QWidget(); self.properties_layout = QVBoxLayout(properties_widget_main) 
        self.properties_editor_label = QLabel("<i>No item selected.</i>"); self.properties_editor_label.setAlignment(Qt.AlignTop | Qt.AlignLeft); self.properties_editor_label.setWordWrap(True); self.properties_editor_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton,"Edt"), "Edit Properties..."); self.properties_edit_button.setEnabled(False); self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock); self.properties_edit_button.setIconSize(QSize(18,18))
        self.properties_layout.addWidget(self.properties_editor_label, 1); self.properties_layout.addWidget(self.properties_edit_button)
        properties_widget_main.setLayout(self.properties_layout); self.properties_dock.setWidget(properties_widget_main); self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock); self.view_menu.addAction(self.properties_dock.toggleViewAction())

    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self); self.setCentralWidget(self.view)

    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1:
            item = selected_items[0]; props = item.get_data(); item_info = f"<b>Type:</b> {type(item).__name__}<br><hr>"
            if isinstance(item, GraphicsStateItem):
                item_info += f"<b>Name:</b> {props['name']}<br>" + f"<b>Initial:</b> {'Yes' if props['is_initial'] else 'No'}<br>" + f"<b>Final:</b> {'Yes' if props['is_final'] else 'No'}<br>"
                item_info += f"<b>Color:</b> <span style='background-color:{props.get('color','#FFFFFF')};padding: 0 5px;'>&nbsp;</span> {props.get('color','N/A')}<br>"
                for k,v in [('Entry',props.get('entry_action')), ('During',props.get('during_action')), ('Exit',props.get('exit_action')), ('Desc',props.get('description'))]:
                    if v: item_info += f"<b>{k}:</b> {v[:30]}{'...' if len(v)>30 else ''}<br>"
            elif isinstance(item, GraphicsTransitionItem):
                full_label = item._compose_label_string() or "<i>(No Label)</i>"
                item_info += f"<b>Label:</b> {full_label}<br>" + f"<b>From:</b> {props['source']}<br>" + f"<b>To:</b> {props['target']}<br>"
                item_info += f"<b>Color:</b> <span style='background-color:{props.get('color','#FFFFFF')};padding: 0 5px;'>&nbsp;</span> {props.get('color','N/A')}<br>"
                if props.get('description'): item_info += f"<b>Desc:</b> {props['description'][:40]}{'...' if len(props['description'])>40 else ''}<br>"
                item_info += f"<b>Curve:</b> Bend={props['control_offset_x']:.0f}, Shift={props['control_offset_y']:.0f}"
            elif isinstance(item, GraphicsCommentItem): item_info += f"<b>Text:</b> {props['text'][:60]}{'...' if len(props['text']) > 60 else ''}<br>"
            else: item_info += "Unknown Item Type"
            self.properties_editor_label.setText(item_info); self.properties_edit_button.setEnabled(True); self.properties_edit_button.setToolTip(f"Edit {type(item).__name__} properties")
        elif len(selected_items) > 1:
            self.properties_editor_label.setText(f"<b>{len(selected_items)} items selected.</b><br><i>Select single item to edit.</i>"); self.properties_edit_button.setEnabled(False); self.properties_edit_button.setToolTip("Select single item.")
        else: 
            self.properties_editor_label.setText("<i>No item selected.</i>"); self.properties_edit_button.setEnabled(False); self.properties_edit_button.setToolTip("")

    def _on_edit_selected_item_properties_from_dock(self):
        if len(self.scene.selectedItems()) == 1: self.scene.edit_item_properties(self.scene.selectedItems()[0])

    def log_message(self, message: str):
        ts = QTime.currentTime().toString('hh:mm:ss.zzz'); self.log_output.append(f"[{ts}] {message}")
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
        self.status_label.setText(message.split('\n')[0][:120])

    def _update_window_title(self):
        title = f"{APP_NAME} - {os.path.basename(self.current_file_path) if self.current_file_path else 'Untitled'}[*]"
        self.setWindowTitle(title)

    def _update_save_actions_enable_state(self):
        is_dirty = self.isWindowModified(); self.save_action.setEnabled(is_dirty); self.save_as_action.setEnabled(True)

    def _update_undo_redo_actions_enable_state(self):
        can_undo = self.undo_stack.canUndo(); self.undo_action.setEnabled(can_undo)
        self.undo_action.setText(f"&Undo {self.undo_stack.undoText()}" if can_undo else "&Undo")
        can_redo = self.undo_stack.canRedo(); self.redo_action.setEnabled(can_redo)
        self.redo_action.setText(f"&Redo {self.undo_stack.redoText()}" if can_redo else "&Redo")

    def _update_matlab_status_display(self, connected, message):
        color = "#006400" if connected else "#B22222"
        self.matlab_status_label.setText(f"MATLAB: {'Connected' if connected else 'Disconnected'}")
        self.matlab_status_label.setToolTip(f"MATLAB Status: {message}")
        self.matlab_status_label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 0 10px 0 5px;")
        self.log_message(f"MATLAB Update: {message}"); self._update_matlab_actions_enabled_state()

    def _update_matlab_actions_enabled_state(self):
        is_conn = self.matlab_connection.connected
        self.export_simulink_action.setEnabled(is_conn); self.run_simulation_action.setEnabled(is_conn); self.generate_code_action.setEnabled(is_conn)

    def _start_matlab_operation(self, op_name):
        self.log_message(f"MATLAB: {op_name} starting..."); self.status_label.setText(f"Running: {op_name}...")
        self.progress_bar.setVisible(True); self.set_ui_enabled_for_matlab_op(False)

    def _finish_matlab_operation(self):
        self.progress_bar.setVisible(False); self.status_label.setText("Ready"); self.set_ui_enabled_for_matlab_op(True)
        self.log_message("MATLAB: Operation finished.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        self.menuBar().setEnabled(enabled)
        for child in self.findChildren(QToolBar): child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
        for name in ["ToolsDock", "PropertiesDock"]: 
            dock = self.findChild(QDockWidget, name)
            if dock: dock.setEnabled(enabled)

    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation(); self.log_message(f"MATLAB Result: {message}") 
        if success:
            if "Model generation" in message and data: 
                 self.last_generated_model_path = data; QMessageBox.information(self, "Simulink Model", f"Generated: {data}")
            elif "Simulation" in message: QMessageBox.information(self, "Simulation", f"Finished: {message}")
        else: QMessageBox.warning(self, "MATLAB Op Failed", message)
        
    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation(); self.log_message(f"MATLAB Code Gen: {message}") 
        if success and output_dir:
            mb = QMessageBox(self); mb.setIcon(QMessageBox.Information); mb.setWindowTitle("Code Generation")
            mb.setTextFormat(Qt.RichText); mb.setText(f"Completed.<br>Output: <a href='file:///{os.path.abspath(output_dir)}'>{os.path.abspath(output_dir)}</a>")
            btn = mb.addButton("Open Directory", QMessageBox.ActionRole); mb.addButton(QMessageBox.Ok); mb.exec_()
            if mb.clickedButton() == btn: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(output_dir)))
        elif not success: QMessageBox.warning(self, "Code Generation Failed", message)

    def _prompt_save_if_dirty(self) -> bool:
        if not self.isWindowModified(): return True 
        name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes?", f"'{name}' has unsaved changes. Save them?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save) 
        if reply == QMessageBox.Save: return self.on_save_file() 
        return reply != QMessageBox.Cancel

    def on_new_file(self, silent=False): 
        if not silent and not self._prompt_save_if_dirty(): return False 
        self.scene.clear(); self.scene.setSceneRect(0,0,5000,4000); self.current_file_path = None; self.last_generated_model_path = None 
        self.undo_stack.clear(); self.scene.set_dirty(False); self._update_window_title(); self._update_undo_redo_actions_enable_state()
        if not silent: self.log_message("New diagram created.")
        self.view.resetTransform(); self.view.centerOn(2500,2000); self.select_mode_action.trigger(); return True

    def on_open_file(self):
        if not self._prompt_save_if_dirty(): return
        start_dir = os.path.dirname(self.current_file_path or QDir.homePath())
        fpath, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)
        if fpath:
            self.log_message(f"Opening: {fpath}")
            if self._load_from_path(fpath):
                self.current_file_path = fpath; self.last_generated_model_path = None; self.undo_stack.clear(); self.scene.set_dirty(False)
                self._update_window_title(); self._update_undo_redo_actions_enable_state(); self.log_message(f"Opened: {fpath}")
                bounds = self.scene.itemsBoundingRect()
                self.view.fitInView(bounds.adjusted(-100,-100,100,100) if not bounds.isEmpty() else QRectF(0,0,5000,4000), Qt.KeepAspectRatio)
            else: QMessageBox.critical(self, "Error Opening File", f"Could not load: {fpath}"); self.log_message(f"Failed to open: {fpath}")

    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
            if not isinstance(data,dict) or not all(k in data for k in ['states','transitions']): raise ValueError("Invalid format")
            self.scene.load_diagram_data(data); return True
        except Exception as e: self.log_message(f"Error loading {file_path}: {type(e).__name__}: {e}"); return False

    def on_save_file(self) -> bool: 
        if self.current_file_path:
            if self._save_to_path(self.current_file_path): self.scene.set_dirty(False); return True
            return False 
        else: return self.on_save_file_as() 

    def on_save_file_as(self) -> bool:
        start_path = self.current_file_path or os.path.join(QDir.homePath(), "untitled" + FILE_EXTENSION)
        fpath, _ = QFileDialog.getSaveFileName(self, "Save BSM File As", start_path, FILE_FILTER)
        if fpath:
            if not fpath.lower().endswith(FILE_EXTENSION): fpath += FILE_EXTENSION
            if self._save_to_path(fpath):
                self.current_file_path = fpath; self.scene.set_dirty(False); self._update_window_title(); return True
        return False 

    def _save_to_path(self, file_path) -> bool:
        sf = QSaveFile(file_path)
        if not sf.open(QIODevice.WriteOnly | QIODevice.Text):
            err = sf.errorString(); self.log_message(f"Error opening {file_path}: {err}"); QMessageBox.critical(self, "Save Error", f"Failed to open:\n{err}"); return False
        try:
            data = self.scene.get_diagram_data(); json_data = json.dumps(data, indent=4, ensure_ascii=False)
            if sf.write(json_data.encode('utf-8')) == -1: raise IOError(sf.errorString())
            if not sf.commit(): raise IOError(sf.errorString())
            self.log_message(f"File saved: {file_path}"); return True
        except Exception as e:
            err = str(e); self.log_message(f"Error saving to {file_path}: {err}"); QMessageBox.critical(self, "Save Error", f"Error during save:\n{err}"); sf.cancelWriting(); return False
            
    def on_select_all(self): self.scene.select_all()
    def on_delete_selected(self): self.scene.delete_selected_items() 

    def on_export_simulink(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Not Connected", "Configure MATLAB first."); return
        dlg = QDialog(self); dlg.setWindowTitle("Export to Simulink"); dlg.setWindowIcon(get_standard_icon(QStyle.SP_ArrowRight, "->M")); layout = QFormLayout(dlg); layout.setSpacing(10)
        default_name = "".join(c if c.isalnum() or c=='_' else '_' for c in os.path.splitext(os.path.basename(self.current_file_path or "BSM_Model"))[0])
        if not default_name or not default_name[0].isalpha(): default_name = "Model_" + default_name
        name_edit = QLineEdit(default_name); name_edit.setPlaceholderText("Simulink model name"); layout.addRow("Model Name:", name_edit)
        out_dir_edit = QLineEdit(os.path.dirname(self.current_file_path or QDir.homePath()))
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"),"Browse..."); browse_btn.clicked.connect(lambda: out_dir_edit.setText(QFileDialog.getExistingDirectory(dlg, "Output Dir", out_dir_edit.text()) or out_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(out_dir_edit, 1); dir_layout.addWidget(browse_btn); layout.addRow("Output Dir:", dir_layout)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject); layout.addRow(btns); dlg.setMinimumWidth(450)
        if dlg.exec_() == QDialog.Accepted:
            model_name = name_edit.text().strip(); output_dir = out_dir_edit.text().strip()
            if not model_name or not output_dir: QMessageBox.warning(self, "Input Error", "Model name and output dir required."); return
            if not model_name[0].isalpha() or not all(c.isalnum() or c=='_' for c in model_name): QMessageBox.warning(self, "Invalid Model Name", "Use letters, numbers, underscores. Start with letter."); return
            if not os.path.exists(output_dir): os.makedirs(output_dir, exist_ok=True)
            data = self.scene.get_diagram_data()
            if not data['states']: QMessageBox.information(self, "Empty Diagram", "No states to export."); return
            self._start_matlab_operation(f"Exporting '{model_name}'"); self.matlab_connection.generate_simulink_model(data['states'], data['transitions'], output_dir, model_name)

    def on_run_simulation(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Not Connected", "Connect MATLAB first."); return
        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return; self.last_generated_model_path = model_path 
        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Stop time (s):", 10.0, 0.001, 86400.0, 3)
        if not ok: return
        self._start_matlab_operation(f"Simulating '{os.path.basename(model_path)}'"); self.matlab_connection.run_simulation(model_path, sim_time)

    def on_generate_code(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Not Connected", "Connect MATLAB first."); return
        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model", default_dir, "Simulink Models (*.slx);;All (*)")
        if not model_path: return; self.last_generated_model_path = model_path 
        dlg = QDialog(self); dlg.setWindowTitle("Code Gen Options"); dlg.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cde")); layout = QFormLayout(dlg); layout.setSpacing(10)
        lang_combo = QComboBox(); lang_combo.addItems(["C", "C++"]); lang_combo.setCurrentText("C++"); layout.addRow("Target Language:", lang_combo)
        out_dir_edit = QLineEdit(os.path.dirname(model_path)); out_dir_edit.setPlaceholderText("Base output dir")
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw"), "Browse..."); browse_btn.clicked.connect(lambda: out_dir_edit.setText(QFileDialog.getExistingDirectory(dlg, "Base Output Dir", out_dir_edit.text()) or out_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(out_dir_edit,1); dir_layout.addWidget(browse_btn); layout.addRow("Base Output Dir:", dir_layout)
        btns = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject); layout.addRow(btns); dlg.setMinimumWidth(450)
        if dlg.exec_() == QDialog.Accepted:
            lang = lang_combo.currentText(); output_dir_base = out_dir_edit.text().strip()
            if not output_dir_base: QMessageBox.warning(self, "Input Error", "Base output dir required."); return
            if not os.path.exists(output_dir_base): os.makedirs(output_dir_base, exist_ok=True)
            self._start_matlab_operation(f"Generating {lang} code for '{os.path.basename(model_path)}'"); self.matlab_connection.generate_code(model_path, lang, output_dir_base)

    def on_matlab_settings(self): MatlabSettingsDialog(self.matlab_connection, self).exec_() 

    def on_about(self): QMessageBox.about(self, f"About {APP_NAME}", f"<h3>{APP_NAME} v{APP_VERSION}</h3><p>Brain State Machine Designer.</p><p><b>Features:</b> Drag & drop, property editing (color, actions), Simulink export & code gen.</p><p><i>AI Revell Lab.</i></p>")

    def closeEvent(self, event: QCloseEvent): 
        if self._prompt_save_if_dirty():
            if self.matlab_connection._active_threads: self.log_message(f"Closing. {len(self.matlab_connection._active_threads)} MATLAB ops may run in background.")
            event.accept()
        else: event.ignore() 


if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
```