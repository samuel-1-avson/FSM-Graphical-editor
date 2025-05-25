
# bsm_designer_project/main.py

import sys
import os
import tempfile
import subprocess
import json
import html
import math
import socket
import re
from PyQt5.QtCore import QTime, QTimer, QPointF, QMetaObject # Added QMetaObject
import pygraphviz as pgv

# --- Custom Modules ---
from graphics_scene import DiagramScene, ZoomableView
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
from fsm_simulator import FSMSimulator, FSMError
from ai_chatbot import AIChatbotManager
# from matlab_integration import MatlabConnection # Removed this import
from dialogs import (StatePropertiesDialog, TransitionPropertiesDialog, CommentPropertiesDialog,
                     MatlabSettingsDialog) # MatlabSettingsDialog will now take the embedded MatlabConnection
from config import (
    APP_VERSION, APP_NAME, FILE_EXTENSION, FILE_FILTER, STYLE_SHEET_GLOBAL,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG,
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_PRIMARY_LIGHT,
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_BACKGROUND_LIGHT, COLOR_GRID_MINOR, COLOR_GRID_MAJOR,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_ON_ACCENT,
    COLOR_ACCENT_SECONDARY, COLOR_BORDER_LIGHT, COLOR_BORDER_MEDIUM
)
from utils import get_standard_icon

# --- Logging Setup ---
import logging
try:
    from logging_setup import setup_global_logging
except ImportError:
    print("CRITICAL: logging_setup.py not found. Logging will be basic.")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
# --- End Logging Setup ---

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QToolBox, QAction,
    QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QStatusBar, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
    QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
    QFileDialog, QProgressBar, QTabWidget, QCheckBox, QActionGroup, QGraphicsItem,
    QGroupBox, QUndoStack, QUndoCommand, QStyle, QSizePolicy, QGraphicsLineItem,
    QToolButton, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent,
    QGraphicsSceneHoverEvent, QGraphicsTextItem, QGraphicsDropShadowEffect,
    QHeaderView, QTableWidget, QTableWidgetItem, QAbstractItemView
)
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform, QKeyEvent, QPainterPathStroker, QPolygonF, QKeySequence,
    QDesktopServices, QWheelEvent, QMouseEvent, QCloseEvent, QFontMetrics, QPalette
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QSize, QUrl,
    QSaveFile, QIODevice, pyqtSlot
)

# --- Resource Monitoring Imports ---
import psutil
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None

logger = logging.getLogger(__name__)

# --- Embedded MATLAB Integration Logic ---

class MatlabCommandWorker(QObject):
    finished_signal = pyqtSignal(bool, str, str) # success, message, data_output

    def __init__(self, matlab_path, script_file, original_signal, success_message_prefix, model_name_for_context=None):
        super().__init__()
        self.matlab_path = matlab_path
        self.script_file = script_file
        self.original_signal = original_signal # This will be simulationFinished or codeGenerationFinished
        self.success_message_prefix = success_message_prefix
        self.model_name_for_context = model_name_for_context

    @pyqtSlot()
    def run_command(self):
        output_data_for_signal = ""
        success = False
        message = ""
        timeout_seconds = 600  # 10 minutes
        try:
            # Ensure script_file path uses forward slashes for MATLAB compatibility
            matlab_run_command = f"run('{self.script_file.replace(os.sep, '/')}')"
            cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", matlab_run_command]
            
            logger.debug(f"Executing MATLAB command: {' '.join(cmd)}")

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True, # Keep as True, will handle decoding if needed
                encoding='utf-8', # Specify encoding
                errors='replace', # Handle potential decoding errors gracefully
                timeout=timeout_seconds,
                check=False, # Don't raise CalledProcessError automatically
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            stdout_str = process.stdout if process.stdout else ""
            stderr_str = process.stderr if process.stderr else ""
            
            logger.debug(f"MATLAB STDOUT:\n{stdout_str[:1000]}...") # Log first 1000 chars
            if stderr_str:
                logger.debug(f"MATLAB STDERR:\n{stderr_str[:1000]}...")


            if "MATLAB_SCRIPT_SUCCESS:" in stdout_str:
                success = True
                for line in stdout_str.splitlines():
                    if line.startswith("MATLAB_SCRIPT_SUCCESS:"):
                        output_data_for_signal = line.split(":", 1)[1].strip()
                        break
                message = f"{self.success_message_prefix} successful."
                if output_data_for_signal: message += f" Output: {output_data_for_signal}"

            elif "MATLAB_SCRIPT_FAILURE:" in stdout_str:
                success = False
                extracted_error_detail = "Details not found in script output."
                for line in stdout_str.splitlines():
                    if line.startswith("MATLAB_SCRIPT_FAILURE:"):
                        extracted_error_detail = line.split(":", 1)[1].strip()
                        break
                message = f"{self.success_message_prefix} script reported failure: {extracted_error_detail}"
                
                if stderr_str and extracted_error_detail not in stderr_str:
                    message += f"\nMATLAB Stderr: {stderr_str[:500]}"
                
                stdout_context_lines = [line for line in stdout_str.splitlines()
                                        if "ERROR" in line.upper() or "WARNING" in line.upper() or
                                           (self.model_name_for_context and self.model_name_for_context in line)]
                stdout_context_for_failure = "\n".join(stdout_context_lines[:10])
                if stdout_context_for_failure and extracted_error_detail not in stdout_context_for_failure:
                    message += f"\nRelevant MATLAB Stdout: {stdout_context_for_failure[:500]}"

            elif process.returncode != 0:
                success = False
                error_output_detail = stderr_str or stdout_str
                matlab_error_lines = [line for line in error_output_detail.splitlines() if line.strip().startswith("Error using") or line.strip().startswith("Error:")]
                if matlab_error_lines:
                    specific_error = " ".join(matlab_error_lines[:2])
                    message = f"{self.success_message_prefix} process failed. MATLAB Exit Code {process.returncode}. Error: {specific_error[:500]}"
                else:
                    message = f"{self.success_message_prefix} process failed. MATLAB Exit Code {process.returncode}:\n{error_output_detail[:1000]}"
            else: # Fallback if no explicit markers but exit code 0
                success = True
                message = f"{self.success_message_prefix} completed (no explicit success/failure marker, but exit code 0)."
                output_data_for_signal = stdout_str

            self.original_signal.emit(success, message, output_data_for_signal if success else "")

        except subprocess.TimeoutExpired:
            message = f"{self.success_message_prefix} process timed out after {timeout_seconds/60:.1f} minutes."
            self.original_signal.emit(False, message, "")
            logger.error(message)
        except FileNotFoundError:
            message = f"MATLAB executable not found: {self.matlab_path}"
            self.original_signal.emit(False, message, "")
            logger.error(message)
        except Exception as e:
            message = f"Unexpected error in {self.success_message_prefix} worker: {type(e).__name__}: {str(e)}"
            self.original_signal.emit(False, message, "")
            logger.error(message, exc_info=True)
        finally:
            if os.path.exists(self.script_file):
                try:
                    os.remove(self.script_file)
                    script_dir = os.path.dirname(self.script_file)
                    if script_dir.startswith(tempfile.gettempdir()) and "bsm_matlab_" in script_dir:
                        if not os.listdir(script_dir):
                            os.rmdir(script_dir)
                        else:
                            logger.warning(f"Temp directory {script_dir} not empty, not removed.")
                except OSError as e_os:
                    logger.warning(f"Could not clean up temp script/dir '{self.script_file}': {e_os}")
            self.finished_signal.emit(success, message, output_data_for_signal)


class MatlabConnection(QObject):
    connectionStatusChanged = pyqtSignal(bool, str)
    simulationFinished = pyqtSignal(bool, str, str)
    codeGenerationFinished = pyqtSignal(bool, str, str)

    def __init__(self):
        super().__init__()
        self.matlab_path = ""
        self.connected = False
        self._active_threads: list[QThread] = [] # Keep track of active worker threads

    def set_matlab_path(self, path):
        self.matlab_path = path.strip() if path else "" # Handle None path
        if self.matlab_path and os.path.exists(self.matlab_path) and \
           (os.access(self.matlab_path, os.X_OK) or self.matlab_path.lower().endswith('.exe')):
            # Path seems structurally okay, actual connection test is separate
            self.connected = True # Assume connectable until test_connection proves otherwise or is called
            self.connectionStatusChanged.emit(True, f"MATLAB path set and appears valid: {self.matlab_path}")
            return True
        else:
            old_path = self.matlab_path
            self.connected = False
            self.matlab_path = "" # Clear invalid path
            if old_path:
                self.connectionStatusChanged.emit(False, f"MATLAB path '{old_path}' is invalid or not executable.")
            else:
                 self.connectionStatusChanged.emit(False, "MATLAB path cleared or not set.")
            return False

    def test_connection(self):
        if not self.matlab_path:
            self.connected = False
            self.connectionStatusChanged.emit(False, "MATLAB path not set. Cannot test connection.")
            return False
        
        if not self.connected: # Re-validate if not already marked as connected
            if not self.set_matlab_path(self.matlab_path): 
                return False

        try:
            cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", "disp('MATLAB_CONNECTION_TEST_SUCCESS')"]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

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
            self.connected = False; self.connectionStatusChanged.emit(False, "MATLAB connection test timed out (20s)."); return False
        except subprocess.CalledProcessError as e: # Should not happen with check=False
            self.connected = False; self.connectionStatusChanged.emit(False, f"MATLAB error during test: {e.stderr or e.stdout or str(e)}".splitlines()[0]); return False
        except FileNotFoundError:
            self.connected = False; self.connectionStatusChanged.emit(False, f"MATLAB executable not found at: {self.matlab_path}"); return False
        except Exception as e:
            self.connected = False; self.connectionStatusChanged.emit(False, f"An unexpected error occurred during MATLAB test: {str(e)}"); return False

    def detect_matlab(self):
        paths_to_check = []
        if sys.platform == 'win32':
            program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
            matlab_base = os.path.join(program_files, 'MATLAB')
            if os.path.isdir(matlab_base):
                versions = sorted([d for d in os.listdir(matlab_base) if d.startswith('R20') and len(d) > 4], reverse=True)
                for v_year_letter in versions:
                    paths_to_check.append(os.path.join(matlab_base, v_year_letter, 'bin', 'matlab.exe'))
        elif sys.platform == 'darwin':
            base_app_path = '/Applications'
            potential_matlab_apps = sorted([d for d in os.listdir(base_app_path) if d.startswith('MATLAB_R20') and d.endswith('.app')], reverse=True)
            for app_name in potential_matlab_apps:
                paths_to_check.append(os.path.join(base_app_path, app_name, 'bin', 'matlab'))
        else: # Linux
            common_base_paths = ['/usr/local/MATLAB', '/opt/MATLAB']
            for base_path in common_base_paths:
                if os.path.isdir(base_path):
                    versions = sorted([d for d in os.listdir(base_path) if d.startswith('R20') and len(d) > 4], reverse=True)
                    for v_year_letter in versions:
                         paths_to_check.append(os.path.join(base_path, v_year_letter, 'bin', 'matlab'))
            paths_to_check.append('matlab') # Check if 'matlab' is in PATH

        for path_candidate in paths_to_check:
            if path_candidate == 'matlab' and sys.platform != 'win32': # 'matlab' in PATH
                try: 
                    test_process = subprocess.run([path_candidate, "-batch", "exit"], timeout=5, capture_output=True, check=False)
                    if test_process.returncode == 0:
                        if self.set_matlab_path(path_candidate): return True
                except (FileNotFoundError, subprocess.TimeoutExpired): continue
            elif os.path.exists(path_candidate) and os.access(path_candidate, os.X_OK): 
                if self.set_matlab_path(path_candidate): return True

        self.connectionStatusChanged.emit(False, "MATLAB auto-detection failed. Please set the path manually."); return False

    def _run_matlab_script(self, script_content, worker_signal, success_message_prefix, model_name_for_context=None):
        if not self.connected:
            worker_signal.emit(False, "MATLAB not connected or path invalid.", "")
            return

        try:
            temp_dir = tempfile.mkdtemp(prefix="bsm_matlab_")
            script_file_name = "matlab_script.m"
            script_file_path = os.path.join(temp_dir, script_file_name)
            with open(script_file_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            logger.debug(f"Temporary MATLAB script created at: {script_file_path}")
        except Exception as e:
            worker_signal.emit(False, f"Failed to create temporary MATLAB script: {e}", "")
            logger.error(f"Failed to create temp script: {e}", exc_info=True)
            return

        worker = MatlabCommandWorker(self.matlab_path, script_file_path, worker_signal, success_message_prefix, model_name_for_context)
        thread = QThread() # No parent here, managed by _active_threads
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

        slx_file_path = os.path.join(output_dir, f"{model_name}.slx").replace(os.sep, '/')
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
            "    set_param(chartBlockSimulinkPath, 'Position', [100 50 400 350]);",
            "    disp(['Stateflow chart block added at: ', chartBlockSimulinkPath]);",
            "    stateHandles = containers.Map('KeyType','char','ValueType','any');",
            "% --- State Creation ---"
        ]

        for i, state in enumerate(states):
            s_name_matlab = state['name'].replace("'", "''") 
            s_id_matlab_safe = f"state_{i}_{state['name'].replace(' ', '_').replace('-', '_')}"
            s_id_matlab_safe = ''.join(filter(str.isalnum, s_id_matlab_safe)) 
            if not s_id_matlab_safe or not s_id_matlab_safe[0].isalpha(): s_id_matlab_safe = 's_' + s_id_matlab_safe
            
            sf_x = state.get('x', 20 + i*150) / 2.5 + 20  # Provide default x if missing
            sf_y = state.get('y', 20) / 2.5 + 20            # Provide default y if missing
            sf_w = max(60, state.get('width', 120) / 2.5)   # Provide default width if missing
            sf_h = max(40, state.get('height', 60) / 2.5)  # Provide default height if missing


            state_label_parts = []
            for action_key, action_desc in [('entry_action', 'entry'), ('during_action', 'during'), ('exit_action', 'exit')]:
                action_code = state.get(action_key)
                if action_code:
                    escaped_action_code = action_code.replace("'", "''").replace(chr(10), '; ')
                    state_label_parts.append(f"{action_desc}: {escaped_action_code}")
            
            s_label_string_matlab = "\\n".join(state_label_parts)

            script_lines.extend([
                f"    {s_id_matlab_safe} = Stateflow.State(chartSFObj);",
                f"    {s_id_matlab_safe}.Name = '{s_name_matlab}';",
                f"    {s_id_matlab_safe}.Position = [{sf_x}, {sf_y}, {sf_w}, {sf_h}];",
            ])
            if s_label_string_matlab:
                 script_lines.append(f"    {s_id_matlab_safe}.LabelString = '{s_label_string_matlab}';")
            script_lines.append(f"    stateHandles('{s_name_matlab}') = {s_id_matlab_safe};")
            
            if state.get('is_initial', False):
                script_lines.extend([
                    f"    defaultTransition_{i} = Stateflow.Transition(chartSFObj);", 
                    f"    defaultTransition_{i}.Destination = {s_id_matlab_safe};",
                    f"    defaultTransition_{i}.SourceOClock = 9;", 
                    f"    defaultTransition_{i}.DestinationOClock = 9;", 
                ])

        script_lines.append("% --- Transition Creation ---")
        for i, trans in enumerate(transitions):
            src_name_matlab = trans['source'].replace("'", "''")
            dst_name_matlab = trans['target'].replace("'", "''")

            label_parts = []
            if trans.get('event'): label_parts.append(trans['event'])
            if trans.get('condition'): label_parts.append(f"[{trans['condition']}]")
            if trans.get('action'): label_parts.append(f"/{{{trans['action']}}}") 
            
            t_label_matlab = " ".join(label_parts).strip().replace("'", "''")

            script_lines.extend([
                f"    if isKey(stateHandles, '{src_name_matlab}') && isKey(stateHandles, '{dst_name_matlab}')",
                f"        srcStateHandle = stateHandles('{src_name_matlab}');",
                f"        dstStateHandle = stateHandles('{dst_name_matlab}');",
                f"        t{i} = Stateflow.Transition(chartSFObj);",
                f"        t{i}.Source = srcStateHandle;",
                f"        t{i}.Destination = dstStateHandle;",
            ])
            if t_label_matlab:
                 script_lines.append(f"        t{i}.LabelString = '{t_label_matlab}';")
            script_lines.extend([
                "    else",
                f"        disp(['Warning: Could not create SF transition from ''{src_name_matlab}'' to ''{dst_name_matlab}''. State missing.']);",
                "    end"
            ])

        script_lines.extend([
            "% --- Finalize and Save ---",
            "    Simulink.BlockDiagram.arrangeSystem(chartBlockSimulinkPath, 'FullLayout', 'true', 'Animation', 'false');", 
            "    sf('FitToView', chartSFObj.Id);", 
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
        self._run_matlab_script(script_content, self.simulationFinished, "Model generation", model_name_orig)
        return True

    def run_simulation(self, model_path, sim_time=10):
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected.", "")
            return False
        if not os.path.exists(model_path):
            self.simulationFinished.emit(False, f"Model file not found: {model_path}", "")
            return False

        model_path_matlab = model_path.replace(os.sep, '/')
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
        self._run_matlab_script(script_content, self.simulationFinished, "Simulation", model_name)
        return True

    def generate_code(self, model_path, language="C++", output_dir_base=None):
        if not self.connected:
            self.codeGenerationFinished.emit(False, "MATLAB not connected", "")
            return False

        model_path_matlab = model_path.replace(os.sep, '/')
        model_dir_matlab = os.path.dirname(model_path_matlab)
        model_name = os.path.splitext(os.path.basename(model_path))[0]

        if not output_dir_base:
            output_dir_base = os.path.dirname(model_path) 
        code_gen_root_matlab = output_dir_base.replace(os.sep, '/')

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
    else 
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
        self._run_matlab_script(script_content, self.codeGenerationFinished, "Code generation", model_name)
        return True

# --- End of Embedded MATLAB Integration Logic ---


# --- Resource Monitor Worker (already defined above) ---
# class ResourceMonitorWorker(QObject): ...

# --- DraggableToolButton (already defined above) ---
# class DraggableToolButton(QPushButton): ...

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_file_path = None
        self.last_generated_model_path = None
        self.matlab_connection = MatlabConnection() # Uses the embedded class
        self.undo_stack = QUndoStack(self)

        self.ai_chatbot_manager = AIChatbotManager(self)
        self.scene = DiagramScene(self.undo_stack, self)
        
        if not hasattr(self.scene, 'log_function'):
            logger.info("Monkey-patching self.scene.log_function for compatibility with undo_commands.py")
            self.scene.log_function = lambda msg, level="ERROR": self.scene._log_to_parent(level, msg)

        self.scene.modifiedStatusChanged.connect(self.setWindowModified)
        self.scene.modifiedStatusChanged.connect(self._update_window_title)

        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False
        self._py_sim_currently_highlighted_item: GraphicsStateItem | None = None
        self._py_sim_currently_highlighted_transition: GraphicsTransitionItem | None = None

        self._internet_connected: bool | None = None
        self.internet_check_timer = QTimer(self)
        
        self.resource_monitor_worker: ResourceMonitorWorker | None = None
        self.resource_monitor_thread: QThread | None = None

        self.init_ui()

        try:
            setup_global_logging(self.log_output)
            logger.info("Main window initialized and logging configured.")
        except AttributeError as e:
            logger.error(f"Failed to run setup_global_logging: {e}. UI logs might not work correctly.")
        except NameError:
            logger.error("Failed to run setup_global_logging (NameError). UI logs might not work.")

        self._init_resource_monitor()

        self.ai_chatbot_manager.statusUpdate.connect(self._update_ai_chat_status)
        self.ai_chatbot_manager.errorOccurred.connect(self._handle_ai_error)
        self.ai_chatbot_manager.fsmDataReceived.connect(self._handle_fsm_data_from_ai)
        self.ai_chatbot_manager.plainResponseReady.connect(self._handle_plain_ai_response)

        if hasattr(self, 'ai_chat_display'): self.ai_chat_display.setObjectName("AIChatDisplay")
        if hasattr(self, 'ai_chat_input'): self.ai_chat_input.setObjectName("AIChatInput")
        if hasattr(self, 'ai_chat_send_button'): self.ai_chat_send_button.setObjectName("AIChatSendButton")
        if hasattr(self, 'ai_chat_status_label'): self.ai_chat_status_label.setObjectName("AIChatStatusLabel")
        self._update_ai_chat_status("Status: API Key required. Configure in Settings.")

        if hasattr(self, 'matlab_status_label'): self.matlab_status_label.setObjectName("MatlabStatusLabel")
        if hasattr(self, 'py_sim_status_label'): self.py_sim_status_label.setObjectName("PySimStatusLabel")
        if hasattr(self, 'internet_status_label'): self.internet_status_label.setObjectName("InternetStatusLabel")
        if hasattr(self, 'status_label'): self.status_label.setObjectName("StatusLabel")

        self._update_matlab_status_display(False, "Initializing. Configure MATLAB settings or attempt auto-detect.")
        self._update_py_sim_status_display()

        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)

        self._update_window_title()
        self.on_new_file(silent=True)
        self._init_internet_status_check()
        self.scene.selectionChanged.connect(self._update_properties_dock)
        self._update_properties_dock()
        self._update_py_simulation_actions_enabled_state()

        if not self.ai_chatbot_manager.api_key:
            self._update_ai_chat_status("Status: API Key required. Configure in Settings.")
        else:
            self._update_ai_chat_status("Status: Ready.")

    # ... (rest of MainWindow methods: init_ui, _create_central_widget, _create_actions, etc. remain largely unchanged) ...
    # Small modification in on_matlab_settings to pass the embedded MatlabConnection
    def on_matlab_settings(self):
        if self.py_sim_active:
             QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before changing MATLAB settings.")
             return
        # Pass the embedded self.matlab_connection instance
        MatlabSettingsDialog(self.matlab_connection, self).exec_()

    # Ensure all other methods that were calling self.matlab_connection.some_method()
    # will now correctly use the embedded self.matlab_connection object.
    # The structure of those calls doesn't need to change.

    # init_ui, _create_actions, _create_menus, _create_toolbars, _create_docks,
    # _create_status_bar, resource monitor methods, AI methods, Properties dock methods,
    # Window and File Management methods, Python Simulation methods, log_message, closeEvent
    # should remain structurally the same as in the previous version,
    # but ensure they are correctly placed within the MainWindow class.
    # The only key change for this request is the embedding of MatlabConnection.

    # Placeholder for the rest of the MainWindow methods (copied from previous correct version)
    # --- Start of copy-pasted methods ---
    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050)
        self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM"))
        self._create_central_widget()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_docks()
        self._create_status_bar()
        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger()


    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self)
        self.view.setObjectName("MainDiagramView")
        self.setCentralWidget(self.view)

    def _create_actions(self):
        def _safe_get_style_enum(attr_name, fallback_attr_name=None):
            try: return getattr(QStyle, attr_name)
            except AttributeError:
                if fallback_attr_name:
                    try: return getattr(QStyle, fallback_attr_name)
                    except AttributeError: pass
                return QStyle.SP_CustomBase

        self.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "New"), "&New", self, shortcut=QKeySequence.New, statusTip="Create a new file", triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "Opn"), "&Open...", self, shortcut=QKeySequence.Open, statusTip="Open an existing file", triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Sav"), "&Save", self, shortcut=QKeySequence.Save, statusTip="Save the current file", triggered=self.on_save_file)
        self.save_as_action = QAction(
        get_standard_icon(_safe_get_style_enum("SP_DriveHDIcon", "SP_DialogSaveButton"), "SA"),
        "Save &As...",
        self,
        shortcut=QKeySequence.SaveAs,
        statusTip="Save the current file with a new name",
        triggered=self.on_save_file_as
    )
        self.export_simulink_action = QAction(get_standard_icon(_safe_get_style_enum("SP_ArrowUp","SP_ArrowRight"), "->M"), "&Export to Simulink...", self, triggered=self.on_export_simulink)
        self.exit_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", self, shortcut=QKeySequence.Quit, statusTip="Exit the application", triggered=self.close)

        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "Un"))
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "Re"))
        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.undo_stack.canRedoChanged.connect(self._update_undo_redo_actions_enable_state)

        self.select_all_action = QAction(get_standard_icon(_safe_get_style_enum("SP_FileDialogListView", "SP_FileDialogDetailedView"), "All"), "Select &All", self, shortcut=QKeySequence.SelectAll, triggered=self.on_select_all)
        self.delete_action = QAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "&Delete", self, shortcut=QKeySequence.Delete, triggered=self.on_delete_selected)

        self.mode_action_group = QActionGroup(self)
        self.mode_action_group.setExclusive(True)
        self.select_mode_action = QAction(QIcon.fromTheme("edit-select", get_standard_icon(QStyle.SP_ArrowRight, "Sel")), "Select/Move", self, checkable=True, triggered=lambda: self.scene.set_mode("select"))
        self.select_mode_action.setObjectName("select_mode_action")
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", get_standard_icon(QStyle.SP_FileDialogNewFolder, "St")), "Add State", self, checkable=True, triggered=lambda: self.scene.set_mode("state"))
        self.add_state_mode_action.setObjectName("add_state_mode_action")
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", get_standard_icon(QStyle.SP_ArrowForward, "Tr")), "Add Transition", self, checkable=True, triggered=lambda: self.scene.set_mode("transition"))
        self.add_transition_mode_action.setObjectName("add_transition_mode_action")
        self.add_comment_mode_action = QAction(QIcon.fromTheme("insert-text", get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm")), "Add Comment", self, checkable=True, triggered=lambda: self.scene.set_mode("comment"))
        self.add_comment_mode_action.setObjectName("add_comment_mode_action")
        for action in [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action]:
            self.mode_action_group.addAction(action)
        self.select_mode_action.setChecked(True)

        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation (MATLAB)...", self, triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"), "Generate &Code (C/C++ via MATLAB)...", self, triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"), "&MATLAB Settings...", self, triggered=self.on_matlab_settings)

        self.start_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Py▶"), "&Start Python Simulation", self, statusTip="Start internal FSM simulation", triggered=self.on_start_py_simulation)
        self.stop_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaStop, "Py■"), "S&top Python Simulation", self, statusTip="Stop internal FSM simulation", triggered=self.on_stop_py_simulation, enabled=False)
        self.reset_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaSkipBackward, "Py«"), "&Reset Python Simulation", self, statusTip="Reset internal FSM simulation to initial state", triggered=self.on_reset_py_simulation, enabled=False)

        self.openai_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "AISet"), "AI Assistant Settings...", self, triggered=self.on_openai_settings)
        self.clear_ai_chat_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "Clear"), "Clear Chat History", self, triggered=self.on_clear_ai_chat_history)
        self.ask_ai_to_generate_fsm_action = QAction(QIcon.fromTheme("system-run", get_standard_icon(QStyle.SP_DialogYesButton, "AIGen")), "Generate FSM from Description...", self, triggered=self.on_ask_ai_to_generate_fsm)

        self.open_example_menu_action = QAction("Open E&xample...", self)
        self.quick_start_action = QAction(get_standard_icon(QStyle.SP_MessageBoxQuestion, "QS"), "&Quick Start Guide", self, triggered=self.on_show_quick_start)
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, triggered=self.on_about)

    def _create_menus(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        example_menu = file_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ex"), "Open E&xample")
        self.open_example_traffic_action = example_menu.addAction("Traffic Light FSM", lambda: self._open_example_file("traffic_light.bsm"))
        self.open_example_toggle_action = example_menu.addAction("Simple Toggle FSM", lambda: self._open_example_file("simple_toggle.bsm"))
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_simulink_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.delete_action)
        edit_menu.addAction(self.select_all_action)
        edit_menu.addSeparator()
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Mode"),"Interaction Mode")
        mode_menu.addAction(self.select_mode_action)
        mode_menu.addAction(self.add_state_mode_action)
        mode_menu.addAction(self.add_transition_mode_action)
        mode_menu.addAction(self.add_comment_mode_action)

        sim_menu = menu_bar.addMenu("&Simulation")
        py_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_MediaPlay, "PyS"), "Python Simulation (Internal)")
        py_sim_menu.addAction(self.start_py_sim_action)
        py_sim_menu.addAction(self.stop_py_sim_action)
        py_sim_menu.addAction(self.reset_py_sim_action)
        sim_menu.addSeparator()
        matlab_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_ComputerIcon, "M"), "MATLAB/Simulink")
        matlab_sim_menu.addAction(self.run_simulation_action)
        matlab_sim_menu.addAction(self.generate_code_action)
        matlab_sim_menu.addSeparator()
        matlab_sim_menu.addAction(self.matlab_settings_action)

        self.view_menu = menu_bar.addMenu("&View")

        ai_menu = menu_bar.addMenu("&AI Assistant")
        ai_menu.addAction(self.ask_ai_to_generate_fsm_action)
        ai_menu.addAction(self.clear_ai_chat_action)
        ai_menu.addSeparator()
        ai_menu.addAction(self.openai_settings_action)

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.quick_start_action)
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(22,22)
        tb_style = Qt.ToolButtonTextBesideIcon

        file_toolbar = self.addToolBar("File")
        file_toolbar.setObjectName("FileToolBar")
        file_toolbar.setIconSize(icon_size)
        file_toolbar.setToolButtonStyle(tb_style)
        file_toolbar.addAction(self.new_action)
        file_toolbar.addAction(self.open_action)
        file_toolbar.addAction(self.save_action)

        edit_toolbar = self.addToolBar("Edit")
        edit_toolbar.setObjectName("EditToolBar")
        edit_toolbar.setIconSize(icon_size)
        edit_toolbar.setToolButtonStyle(tb_style)
        edit_toolbar.addAction(self.undo_action)
        edit_toolbar.addAction(self.redo_action)
        edit_toolbar.addSeparator()
        edit_toolbar.addAction(self.delete_action)

        tools_tb = self.addToolBar("Interaction Tools")
        tools_tb.setObjectName("ToolsToolBar")
        tools_tb.setIconSize(icon_size)
        tools_tb.setToolButtonStyle(tb_style)
        tools_tb.addAction(self.select_mode_action)
        tools_tb.addAction(self.add_state_mode_action)
        tools_tb.addAction(self.add_transition_mode_action)
        tools_tb.addAction(self.add_comment_mode_action)

        sim_toolbar = self.addToolBar("Simulation Tools")
        sim_toolbar.setObjectName("SimulationToolBar")
        sim_toolbar.setIconSize(icon_size)
        sim_toolbar.setToolButtonStyle(tb_style)
        sim_toolbar.addAction(self.start_py_sim_action)
        sim_toolbar.addAction(self.stop_py_sim_action)
        sim_toolbar.addAction(self.reset_py_sim_action)
        sim_toolbar.addSeparator()
        sim_toolbar.addAction(self.export_simulink_action)
        sim_toolbar.addAction(self.run_simulation_action)
        sim_toolbar.addAction(self.generate_code_action)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)

        self.tools_dock = QDockWidget("Tools", self)
        self.tools_dock.setObjectName("ToolsDock")
        self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_widget_main = QWidget()
        tools_widget_main.setObjectName("ToolsDockWidgetContents")
        tools_main_layout = QVBoxLayout(tools_widget_main)
        tools_main_layout.setSpacing(10)
        tools_main_layout.setContentsMargins(5,5,5,5)

        mode_group_box = QGroupBox("Interaction Modes")
        mode_layout = QVBoxLayout()
        mode_layout.setSpacing(5)
        self.toolbox_select_button = QToolButton(); self.toolbox_select_button.setDefaultAction(self.select_mode_action)
        self.toolbox_add_state_button = QToolButton(); self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action)
        self.toolbox_transition_button = QToolButton(); self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action)
        self.toolbox_add_comment_button = QToolButton(); self.toolbox_add_comment_button.setDefaultAction(self.add_comment_mode_action)
        for btn in [self.toolbox_select_button, self.toolbox_add_state_button, self.toolbox_transition_button, self.toolbox_add_comment_button]:
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setIconSize(QSize(18,18))
            mode_layout.addWidget(btn)
        mode_group_box.setLayout(mode_layout)
        tools_main_layout.addWidget(mode_group_box)

        draggable_group_box = QGroupBox("Drag New Elements")
        draggable_layout = QVBoxLayout()
        draggable_layout.setSpacing(5)
        drag_state_btn = DraggableToolButton(" State", "application/x-bsm-tool", "State")
        drag_state_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))
        drag_initial_state_btn = DraggableToolButton(" Initial State", "application/x-bsm-tool", "Initial State")
        drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt"))
        drag_final_state_btn = DraggableToolButton(" Final State", "application/x-bsm-tool", "Final State")
        drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt"))
        drag_comment_btn = DraggableToolButton(" Comment", "application/x-bsm-tool", "Comment")
        drag_comment_btn.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))
        for btn in [drag_state_btn, drag_initial_state_btn, drag_final_state_btn, drag_comment_btn]:
            btn.setIconSize(QSize(18,18))
            draggable_layout.addWidget(btn)
        draggable_group_box.setLayout(draggable_layout)
        tools_main_layout.addWidget(draggable_group_box)

        tools_main_layout.addStretch()
        self.tools_dock.setWidget(tools_widget_main)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.tools_dock.toggleViewAction())

        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        properties_widget = QWidget()
        properties_layout = QVBoxLayout(properties_widget)
        properties_layout.setContentsMargins(5,5,5,5)
        properties_layout.setSpacing(5)
        self.properties_editor_label = QLabel("<i>No item selected.</i><br><small>Click an item in the diagram or use tools to add new items.</small>")
        self.properties_editor_label.setWordWrap(True)
        self.properties_editor_label.setTextFormat(Qt.RichText)
        self.properties_editor_label.setAlignment(Qt.AlignTop)
        self.properties_editor_label.setStyleSheet(f"padding: 5px; background-color: {COLOR_BACKGROUND_LIGHT}; border: 1px solid {COLOR_BORDER_MEDIUM};")
        properties_layout.addWidget(self.properties_editor_label, 1)
        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"),"Edit Properties")
        self.properties_edit_button.setEnabled(False)
        self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock)
        properties_layout.addWidget(self.properties_edit_button)
        self.properties_dock.setWidget(properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.properties_dock.toggleViewAction())

        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(5,5,5,5)
        self.log_output = QTextEdit()
        self.log_output.setObjectName("LogOutput")
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)
        self.log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.log_dock.toggleViewAction())

        self.py_sim_dock = QDockWidget("Python Simulation", self)
        self.py_sim_dock.setObjectName("PySimDock")
        self.py_sim_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        py_sim_widget = QWidget()
        py_sim_layout = QVBoxLayout(py_sim_widget)
        py_sim_layout.setContentsMargins(5,5,5,5)
        py_sim_layout.setSpacing(5)

        controls_group = QGroupBox("Controls")
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(5)
        self.py_sim_start_btn = QToolButton(); self.py_sim_start_btn.setDefaultAction(self.start_py_sim_action)
        self.py_sim_stop_btn = QToolButton(); self.py_sim_stop_btn.setDefaultAction(self.stop_py_sim_action)
        self.py_sim_reset_btn = QToolButton(); self.py_sim_reset_btn.setDefaultAction(self.reset_py_sim_action)
        self.py_sim_step_btn = QPushButton(get_standard_icon(QStyle.SP_MediaSeekForward, "Step"),"Step")
        self.py_sim_step_btn.clicked.connect(self.on_step_py_simulation)
        for btn in [self.py_sim_start_btn, self.py_sim_stop_btn, self.py_sim_reset_btn]:
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly); btn.setIconSize(QSize(18,18)); controls_layout.addWidget(btn)
        controls_layout.addWidget(self.py_sim_step_btn)
        controls_layout.addStretch()
        controls_group.setLayout(controls_layout)
        py_sim_layout.addWidget(controls_group)

        event_group = QGroupBox("Event Trigger")
        event_layout = QHBoxLayout()
        event_layout.setSpacing(5)
        self.py_sim_event_combo = QComboBox()
        self.py_sim_event_combo.addItem("None (Internal Step)")
        self.py_sim_event_combo.setEditable(False)
        event_layout.addWidget(self.py_sim_event_combo, 1)

        self.py_sim_event_name_edit = QLineEdit()
        self.py_sim_event_name_edit.setPlaceholderText("Custom event name")
        event_layout.addWidget(self.py_sim_event_name_edit, 1)
        self.py_sim_trigger_event_btn = QPushButton(get_standard_icon(QStyle.SP_MediaPlay, "Trg"),"Trigger")
        self.py_sim_trigger_event_btn.clicked.connect(self.on_trigger_py_event)
        event_layout.addWidget(self.py_sim_trigger_event_btn)
        event_group.setLayout(event_layout)
        py_sim_layout.addWidget(event_group)

        state_group = QGroupBox("Current State")
        state_layout = QVBoxLayout()
        self.py_sim_current_state_label = QLabel("<i>Not Running</i>")
        self.py_sim_current_state_label.setStyleSheet("font-size: 9pt; padding: 3px;")
        state_layout.addWidget(self.py_sim_current_state_label)
        state_group.setLayout(state_layout)
        py_sim_layout.addWidget(state_group)

        variables_group = QGroupBox("Variables")
        variables_layout = QVBoxLayout()
        self.py_sim_variables_table = QTableWidget()
        self.py_sim_variables_table.setRowCount(0); self.py_sim_variables_table.setColumnCount(2)
        self.py_sim_variables_table.setHorizontalHeaderLabels(["Name", "Value"])
        self.py_sim_variables_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.py_sim_variables_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.py_sim_variables_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        variables_layout.addWidget(self.py_sim_variables_table)
        variables_group.setLayout(variables_layout)
        py_sim_layout.addWidget(variables_group)

        log_group = QGroupBox("Action Log")
        log_layout = QVBoxLayout()
        self.py_sim_action_log_output = QTextEdit()
        self.py_sim_action_log_output.setReadOnly(True)
        self.py_sim_action_log_output.setObjectName("PySimActionLog")
        self.py_sim_action_log_output.setHtml("<i>Simulation log will appear here...</i>")
        log_layout.addWidget(self.py_sim_action_log_output)
        log_group.setLayout(log_layout)
        py_sim_layout.addWidget(log_group, 1)

        self.py_sim_dock.setWidget(py_sim_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.py_sim_dock.toggleViewAction())

        self.ai_chatbot_dock = QDockWidget("AI Chatbot", self)
        self.ai_chatbot_dock.setObjectName("AIChatbotDock")
        self.ai_chatbot_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        ai_chat_widget = QWidget()
        ai_chat_layout = QVBoxLayout(ai_chat_widget)
        ai_chat_layout.setContentsMargins(5,5,5,5)
        ai_chat_layout.setSpacing(5)
        self.ai_chat_display = QTextEdit()
        self.ai_chat_display.setReadOnly(True)
        self.ai_chat_display.setStyleSheet("font-size: 9pt; padding: 5px;")
        self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
        ai_chat_layout.addWidget(self.ai_chat_display, 1)

        input_layout = QHBoxLayout()
        self.ai_chat_input = QLineEdit()
        self.ai_chat_input.setPlaceholderText("Type your message to the AI...")
        self.ai_chat_input.returnPressed.connect(self.on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_input, 1)
        self.ai_chat_send_button = QPushButton(get_standard_icon(QStyle.SP_ArrowForward, "Snd"),"Send")
        self.ai_chat_send_button.clicked.connect(self.on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_send_button)
        ai_chat_layout.addLayout(input_layout)

        self.ai_chat_status_label = QLabel("Status: Initializing...")
        self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;")
        ai_chat_layout.addWidget(self.ai_chat_status_label)

        self.ai_chatbot_dock.setWidget(ai_chat_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.ai_chatbot_dock.toggleViewAction())

        self.tabifyDockWidget(self.properties_dock, self.ai_chatbot_dock)
        self.tabifyDockWidget(self.ai_chatbot_dock, self.py_sim_dock)


    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1)

        self.cpu_status_label = QLabel("CPU: --%")
        self.cpu_status_label.setToolTip("CPU Usage")
        self.cpu_status_label.setMinimumWidth(90)
        self.cpu_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.cpu_status_label)

        self.ram_status_label = QLabel("RAM: --%")
        self.ram_status_label.setToolTip("RAM Usage")
        self.ram_status_label.setMinimumWidth(90)
        self.ram_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.ram_status_label)

        self.gpu_status_label = QLabel("GPU: N/A")
        self.gpu_status_label.setToolTip("GPU Usage (NVIDIA only, if available and pynvml installed)")
        self.gpu_status_label.setMinimumWidth(130)
        self.gpu_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.gpu_status_label)

        self.py_sim_status_label = QLabel("PySim: Idle")
        self.py_sim_status_label.setToolTip("Internal Python FSM Simulation Status.")
        self.py_sim_status_label.setMinimumWidth(100)
        self.py_sim_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.py_sim_status_label)

        self.matlab_status_label = QLabel("MATLAB: Initializing...")
        self.matlab_status_label.setToolTip("MATLAB connection status.")
        self.matlab_status_label.setMinimumWidth(150)
        self.matlab_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.matlab_status_label)

        self.internet_status_label = QLabel("Internet: Init...")
        self.internet_status_label.setToolTip("Internet connectivity status. Checks periodically.")
        self.internet_status_label.setMinimumWidth(120)
        self.internet_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.internet_status_label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0,0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setTextVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _init_resource_monitor(self):
        self.resource_monitor_thread = QThread(self)
        self.resource_monitor_worker = ResourceMonitorWorker(interval_ms=2000)
        self.resource_monitor_worker.moveToThread(self.resource_monitor_thread)

        self.resource_monitor_worker.resourceUpdate.connect(self._update_resource_display)
        self.resource_monitor_thread.started.connect(self.resource_monitor_worker.start_monitoring)
        
        self.resource_monitor_thread.finished.connect(self.resource_monitor_worker.deleteLater)
        self.resource_monitor_thread.finished.connect(self.resource_monitor_thread.deleteLater)
        
        self.resource_monitor_thread.start()
        logger.info("Resource monitor thread initialized and started.")

    @pyqtSlot(float, float, float, str)
    def _update_resource_display(self, cpu_usage, ram_usage, gpu_util, gpu_name):
        if hasattr(self, 'cpu_status_label'):
            self.cpu_status_label.setText(f"CPU: {cpu_usage:.1f}%")
        if hasattr(self, 'ram_status_label'):
            self.ram_status_label.setText(f"RAM: {ram_usage:.1f}%")
        if hasattr(self, 'gpu_status_label'):
            if gpu_util == -1.0:
                self.gpu_status_label.setText(f"GPU: {gpu_name}")
            elif gpu_util == -2.0:
                 self.gpu_status_label.setText(f"GPU: {gpu_name}")
            else:
                self.gpu_status_label.setText(f"GPU: {gpu_util:.0f}% ({gpu_name})")

    def on_ask_ai_to_generate_fsm(self):
        description, ok = QInputDialog.getMultiLineText(
            self, "Generate FSM", "Describe the FSM you want to create:",
            "Example: A traffic light with states Red, Yellow, Green. Event 'TIMER_EXPIRED' cycles through them."
        )
        if ok and description.strip():
            logger.info("AI: Sending FSM description to AI: '%s...'", description[:50])
            self._update_ai_chat_status("Status: Generating FSM from description...")
            self.ai_chatbot_manager.generate_fsm_from_description(description)
            self._append_to_ai_chat_display("You", f"Generate an FSM: {description}")
        elif ok:
            QMessageBox.warning(self, "Empty Description", "Please provide a description for the FSM.")

    def _handle_fsm_data_from_ai(self, fsm_data: dict, source_message: str):
        logger.info("AI: Received FSM data. Source: '%s...'", source_message[:30])
        self._append_to_ai_chat_display("AI", f"Received FSM structure. (Source: {source_message[:30]}...) Adding to diagram.")

        if not fsm_data or (not fsm_data.get('states') and not fsm_data.get('transitions')):
            logger.error("AI: Returned empty or invalid FSM data structure.")
            self._update_ai_chat_status("Status: AI returned no FSM data.")
            self._append_to_ai_chat_display("System", "AI did not return a valid FSM structure to draw.")
            return

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("Add AI Generated FSM")
        msg_box.setText("AI has generated an FSM. Do you want to clear the current diagram before adding the new FSM, or add to the existing one?")

        clear_button = msg_box.addButton("Clear and Add", QMessageBox.AcceptRole)
        add_to_existing_button = msg_box.addButton("Add to Existing", QMessageBox.AcceptRole)
        cancel_button = msg_box.addButton("Cancel", QMessageBox.RejectRole)
        msg_box.setDefaultButton(cancel_button)
        msg_box.exec_()

        clicked_button = msg_box.clickedButton()
        reply = -1
        if clicked_button == clear_button: reply = 0
        elif clicked_button == add_to_existing_button: reply = 1
        elif clicked_button == cancel_button: reply = 2

        if reply == 2 or reply == -1:
            logger.info("AI: User cancelled adding AI generated FSM.")
            self._update_ai_chat_status("Status: FSM generation cancelled by user.")
            return

        clear_current = (reply == 0)
        self._add_fsm_data_to_scene(fsm_data, clear_current_diagram=clear_current, original_user_prompt=source_message)
        self._update_ai_chat_status("Status: FSM added to diagram.")
        logger.info("AI: FSM data from AI processed and added to scene.")

    def _handle_plain_ai_response(self, ai_message: str):
        logger.info("AI: Received plain AI response.")
        self._append_to_ai_chat_display("AI", ai_message)

    def on_send_ai_chat_message(self):
        message = self.ai_chat_input.text().strip()
        if not message: return
        self.ai_chat_input.clear()
        self._append_to_ai_chat_display("You", message)
        self.ai_chatbot_manager.send_message(message)
        self._update_ai_chat_status("Status: Sending message...")

    def _add_fsm_data_to_scene(self, fsm_data: dict, clear_current_diagram: bool = False, original_user_prompt: str = "AI Generated FSM"):
        logger.info("AI: ADD_FSM_TO_SCENE clear_current_diagram=%s", clear_current_diagram)
        logger.debug("AI: Received FSM Data (states: %d, transitions: %d)",
                     len(fsm_data.get('states',[])), len(fsm_data.get('transitions',[])))

        if clear_current_diagram:
            if not self.on_new_file(silent=True):
                 logger.warning("AI: Clearing diagram cancelled by user (save prompt). Cannot add AI FSM.")
                 return
            logger.info("AI: Cleared diagram before AI generation.")

        if not clear_current_diagram:
            self.undo_stack.beginMacro(f"Add AI FSM: {original_user_prompt[:30]}...")

        state_items_map = {}
        items_to_add_for_undo_command = []

        layout_start_x, layout_start_y = 100, 100
        items_per_row = 3
        default_item_width, default_item_height = 120, 60
        padding_x, padding_y = 150, 100
        GV_SCALE = 1.2

        G = pgv.AGraph(directed=True, strict=False, rankdir='TB', ratio='auto', nodesep='0.75', ranksep='1.2 equally')

        for state_data in fsm_data.get('states', []):
            name = state_data.get('name')
            if name:
                label_for_gv = name
                G.add_node(name, label=label_for_gv, width=str(default_item_width/72.0), height=str(default_item_height/72.0), shape='box', style='rounded')

        for trans_data in fsm_data.get('transitions', []):
            source = trans_data.get('source')
            target = trans_data.get('target')
            if source and target and G.has_node(source) and G.has_node(target):
                event_label = trans_data.get('event', '')
                G.add_edge(source, target, label=event_label)
            else:
                logger.warning("AI: Skipping Graphviz edge due to missing node(s): %s->%s", source, target)

        graphviz_positions = {}
        try:
            G.layout(prog="dot")
            logger.debug("AI: Graphviz layout ('dot') successful.")

            raw_gv_positions = []
            for node in G.nodes():
                try:
                    pos_str = node.attr['pos']
                    parts = pos_str.split(',')
                    if len(parts) == 2:
                        raw_gv_positions.append({'name': node.name, 'x': float(parts[0]), 'y': float(parts[1])})
                    else:
                        logger.warning("AI: Graphviz malformed pos '%s' for node '%s'.", pos_str, node.name)
                except KeyError:
                    logger.warning("AI: Graphviz node '%s' has no 'pos' attribute.", node.name)
                except ValueError:
                    logger.warning("AI: Graphviz cannot parse pos '%s' for node '%s'.", node.attr.get('pos'), node.name)

            if raw_gv_positions:
                min_x_gv = min(p['x'] for p in raw_gv_positions) if raw_gv_positions else 0
                max_y_gv = max(p['y'] for p in raw_gv_positions) if raw_gv_positions else 0

                for p_gv in raw_gv_positions:
                    qt_x = (p_gv['x'] - min_x_gv) * GV_SCALE + layout_start_x
                    qt_y = (max_y_gv - p_gv['y']) * GV_SCALE + layout_start_y
                    graphviz_positions[p_gv['name']] = QPointF(qt_x, qt_y)
            else:
                 logger.warning("AI: Graphviz - No valid positions extracted from nodes.")
        except Exception as e:
            error_msg = str(e).strip() or "Unknown Graphviz error (ensure 'dot' is in PATH)"
            logger.error("AI: Graphviz layout error: %s. Falling back to grid layout.", error_msg, exc_info=True)
            if hasattr(self, '_append_to_ai_chat_display'): self._append_to_ai_chat_display("System", f"Warning: AI FSM layout using Graphviz failed ({error_msg[:60]}...). Using basic grid layout.")
            graphviz_positions = {}

        for i, state_data in enumerate(fsm_data.get('states', [])):
            name = state_data.get('name')
            if not name:
                logger.warning("AI: State data missing 'name'. Skipping: %s", state_data)
                continue

            item_w = state_data.get('width', default_item_width)
            item_h = state_data.get('height', default_item_height)

            pos = graphviz_positions.get(name)
            if pos:
                pos_x, pos_y = pos.x(), pos.y()
            else:
                logger.debug("AI: Using fallback grid layout for state '%s'.", name)
                pos_x = layout_start_x + (i % items_per_row) * (item_w + padding_x)
                pos_y = layout_start_y + (i // items_per_row) * (item_h + padding_y)

            try:
                state_item = GraphicsStateItem(
                    pos_x, pos_y, item_w, item_h, name,
                    is_initial=state_data.get('is_initial', False),
                    is_final=state_data.get('is_final', False),
                    color=state_data.get('properties', {}).get('color', state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG)),
                    entry_action=state_data.get('entry_action', ""),
                    during_action=state_data.get('during_action', ""),
                    exit_action=state_data.get('exit_action', ""),
                    description=state_data.get('description', fsm_data.get('description', "") if i==0 else ""),
                    is_superstate=state_data.get('is_superstate', False),
                    sub_fsm_data=state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]})
                )
                items_to_add_for_undo_command.append(state_item)
                state_items_map[name] = state_item
            except Exception as e:
                logger.error("AI: Error creating GraphicsStateItem '%s': %s", name, e, exc_info=True)

        for trans_data in fsm_data.get('transitions', []):
            source_name = trans_data.get('source')
            target_name = trans_data.get('target')

            if not source_name or not target_name:
                logger.warning("AI: Transition missing source/target. Skipping: %s", trans_data)
                continue

            source_item = state_items_map.get(source_name)
            target_item = state_items_map.get(target_name)

            if source_item and target_item:
                try:
                    trans_item = GraphicsTransitionItem(
                        source_item, target_item,
                        event_str=trans_data.get('event', ""),
                        condition_str=trans_data.get('condition', ""),
                        action_str=trans_data.get('action', ""),
                        color=trans_data.get('properties', {}).get('color', trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT)),
                        description=trans_data.get('description', "")
                    )
                    offset_x = trans_data.get('control_offset_x')
                    offset_y = trans_data.get('control_offset_y')
                    if offset_x is not None and offset_y is not None:
                        try:
                            trans_item.set_control_point_offset(QPointF(float(offset_x), float(offset_y)))
                        except ValueError:
                            logger.warning("AI: Invalid control offsets for transition %s->%s. Using defaults.", source_name, target_name)
                    items_to_add_for_undo_command.append(trans_item)
                except Exception as e:
                    logger.error("AI: Error creating GraphicsTransitionItem %s->%s: %s", source_name, target_name, e, exc_info=True)
            else:
                logger.warning("AI: Could not find source ('%s') or target ('%s') for transition. Skipping.", source_name, target_name)

        max_y_of_laid_out_items = layout_start_y
        if state_items_map:
             max_y_val_gen = (item.scenePos().y() + item.boundingRect().height() for item in state_items_map.values() if item.scenePos())
             max_y_of_laid_out_items = max(max_y_val_gen, default=layout_start_y)


        comment_start_y_fallback = max_y_of_laid_out_items + padding_y
        comment_start_x_fallback = layout_start_x

        for i, comment_data in enumerate(fsm_data.get('comments', [])):
            text = comment_data.get('text')
            if not text: continue

            comment_x = comment_data.get('x', comment_start_x_fallback + i * (150 + 20))
            comment_y = comment_data.get('y', comment_start_y_fallback)
            comment_width = comment_data.get('width')

            try:
                comment_item = GraphicsCommentItem(comment_x, comment_y, text)
                if comment_width is not None:
                    try: comment_item.setTextWidth(float(comment_width))
                    except ValueError: logger.warning("AI: Invalid width '%s' for comment.", comment_width)
                items_to_add_for_undo_command.append(comment_item)
            except Exception as e:
                logger.error("AI: Error creating GraphicsCommentItem: %s", e, exc_info=True)

        if items_to_add_for_undo_command:
            for item in items_to_add_for_undo_command:
                item_type_name = type(item).__name__.replace("Graphics","").replace("Item","")
                cmd_text = f"Add AI {item_type_name}"
                if hasattr(item, 'text_label') and item.text_label: cmd_text += f": {item.text_label}"
                elif hasattr(item, '_compose_label_string'): cmd_text += f" ({item._compose_label_string()})"
                elif hasattr(item, 'toPlainText') and item.toPlainText(): cmd_text += f": {item.toPlainText()[:20]}..."

                add_cmd = AddItemCommand(self.scene, item, cmd_text)
                self.undo_stack.push(add_cmd)

            logger.info("AI: Added %d items to diagram via undo commands.", len(items_to_add_for_undo_command))
            QTimer.singleShot(100, self._fit_view_to_new_ai_items)
        else:
            logger.info("AI: No valid items were generated to add to the diagram.")

        if not clear_current_diagram and items_to_add_for_undo_command:
            self.undo_stack.endMacro()
        elif not clear_current_diagram and not items_to_add_for_undo_command:
             if self.undo_stack.count() > 0 and self.undo_stack.command(self.undo_stack.count() -1).childCount() == 0:
                 pass
             self.undo_stack.endMacro()

        if self.py_sim_active and items_to_add_for_undo_command:
            logger.info("AI: Reinitializing Python simulation after adding AI-generated FSM.")
            current_diagram_data = self.scene.get_diagram_data()
            try:
                self.py_fsm_engine = FSMSimulator(current_diagram_data['states'], current_diagram_data['transitions'])
                self._append_to_py_simulation_log(["Python FSM Simulation reinitialized for new diagram from AI."])
                self._update_py_simulation_dock_ui()
            except FSMError as e:
                self._append_to_py_simulation_log([f"ERROR Re-initializing Sim after AI: {e}"])
                self.on_stop_py_simulation(silent=True)

        logger.debug("AI: ADD_FSM_TO_SCENE processing finished. Items involved: %d", len(items_to_add_for_undo_command))

    def _fit_view_to_new_ai_items(self):
        if not self.scene.items(): return
        items_bounds = self.scene.itemsBoundingRect()
        if self.view and not items_bounds.isNull():
            padded_bounds = items_bounds.adjusted(-50, -50, 50, 50)
            self.view.fitInView(padded_bounds, Qt.KeepAspectRatio)
            logger.info("AI: View adjusted to AI generated items.")
        elif self.view and self.scene.sceneRect():
             self.view.centerOn(self.scene.sceneRect().center())

    def _handle_ai_error(self, error_message: str):
        self._append_to_ai_chat_display("System Error", error_message)
        logger.error("AI Chatbot Error: %s", error_message)
        short_error = error_message.split('\n')[0].split(':')[0][:50]
        self._update_ai_chat_status(f"Error: {short_error}...")

    def _update_ai_chat_status(self, status_text: str):
        if hasattr(self, 'ai_chat_status_label'):
            self.ai_chat_status_label.setText(status_text)
            is_thinking = "thinking..." in status_text.lower() or \
                          "sending..." in status_text.lower() or \
                          "generating..." in status_text.lower()
            is_key_required = "api key required" in status_text.lower() or \
                              "inactive" in status_text.lower() or \
                              "api key error" in status_text.lower()
            is_error_state = "error" in status_text.lower() or \
                             "failed" in status_text.lower() or \
                             is_key_required

            if is_error_state: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: red;")
            elif is_thinking: self.ai_chat_status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_ACCENT_SECONDARY};")
            else: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;")

            can_send = not is_thinking and not is_key_required

            if hasattr(self, 'ai_chat_send_button'): self.ai_chat_send_button.setEnabled(can_send)
            if hasattr(self, 'ai_chat_input'):
                self.ai_chat_input.setEnabled(can_send)
                if can_send and hasattr(self, 'ai_chatbot_dock') and self.ai_chatbot_dock.isVisible() and self.isActiveWindow():
                    self.ai_chat_input.setFocus()
            if hasattr(self, 'ask_ai_to_generate_fsm_action'):
                self.ask_ai_to_generate_fsm_action.setEnabled(can_send)

    def _append_to_ai_chat_display(self, sender: str, message: str):
        timestamp = QTime.currentTime().toString('hh:mm')
        sender_color_hex_str = COLOR_ACCENT_PRIMARY
        if sender == "You": sender_color_hex_str = COLOR_ACCENT_SECONDARY
        elif sender == "System Error" or sender == "System": sender_color_hex_str = "#D32F2F"

        escaped_message = html.escape(message)
        escaped_message = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped_message)
        escaped_message = re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'<i>\1</i>', escaped_message)
        escaped_message = re.sub(r'```(.*?)```', r'<pre><code style="background-color:#f0f0f0; padding:2px 4px; border-radius:3px; display:block; white-space:pre-wrap;">\1</code></pre>', escaped_message, flags=re.DOTALL)
        escaped_message = re.sub(r'`(.*?)`', r'<code style="background-color:#f0f0f0; padding:1px 3px; border-radius:2px;">\1</code>', escaped_message)
        escaped_message = escaped_message.replace("\n", "<br>")

        formatted_html = (
            f"<div style='margin-bottom: 8px;'>"
            f"<span style='font-size:8pt; color:grey;'>[{timestamp}]</span> "
            f"<strong style='color:{sender_color_hex_str};'>{html.escape(sender)}:</strong>"
            f"<div style='margin-top: 3px; padding-left: 5px; border-left: 2px solid {sender_color_hex_str if sender != 'System Error' else '#FFCDD2'};'>{escaped_message}</div>"
            f"</div>"
        )
        self.ai_chat_display.append(formatted_html)
        self.ai_chat_display.ensureCursorVisible()

    def on_openai_settings(self):
        current_key = self.ai_chatbot_manager.api_key if self.ai_chatbot_manager.api_key else ""
        key, ok = QInputDialog.getText(
            self, "OpenAI API Key", "Enter OpenAI API Key (blank to clear):",
            QLineEdit.PasswordEchoOnEdit, current_key
        )
        if ok:
            new_key = key.strip()
            self.ai_chatbot_manager.set_api_key(new_key if new_key else None)
            if new_key:
                logger.info("AI: OpenAI API Key set/updated.")
            else:
                logger.info("AI: OpenAI API Key cleared.")

    def on_clear_ai_chat_history(self):
        if self.ai_chatbot_manager:
            self.ai_chatbot_manager.clear_conversation_history()
            if hasattr(self, 'ai_chat_display'):
                self.ai_chat_display.clear()
                self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
            logger.info("AI: Chat history cleared.")

    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems()
        html_content = ""
        edit_enabled = False
        item_type_for_tooltip = "item"

        if len(selected_items) == 1:
            item = selected_items[0]
            props = item.get_data() if hasattr(item, 'get_data') else {}
            item_type_name = type(item).__name__.replace("Graphics", "").replace("Item", "")
            item_type_for_tooltip = item_type_name.lower()
            edit_enabled = True

            def format_prop_text(text_content, max_chars=25):
                if not text_content: return "<i>(none)</i>"
                escaped = html.escape(str(text_content))
                first_line = escaped.split('\n')[0]
                if len(first_line) > max_chars or '\n' in escaped:
                    return first_line[:max_chars] + "…"
                return first_line

            rows_html = ""
            if isinstance(item, GraphicsStateItem):
                color_val = props.get('color', COLOR_ITEM_STATE_DEFAULT_BG)
                try: color_obj = QColor(color_val)
                except: color_obj = QColor(COLOR_ITEM_STATE_DEFAULT_BG)
                text_on_color = 'black' if color_obj.lightnessF() > 0.5 else 'white'
                color_style = f"background-color:{color_obj.name()}; color:{text_on_color}; padding: 1px 4px; border-radius:2px;"

                rows_html += f"<tr><td><b>Name:</b></td><td>{html.escape(props.get('name', 'N/A'))}</td></tr>"
                rows_html += f"<tr><td><b>Initial:</b></td><td>{'Yes' if props.get('is_initial') else 'No'}</td></tr>"
                rows_html += f"<tr><td><b>Final:</b></td><td>{'Yes' if props.get('is_final') else 'No'}</td></tr>"
                if props.get('is_superstate'):
                     sub_fsm_data = props.get('sub_fsm_data',{})
                     num_sub_states = len(sub_fsm_data.get('states',[]))
                     num_sub_trans = len(sub_fsm_data.get('transitions',[]))
                     rows_html += f"<tr><td><b>Superstate:</b></td><td>Yes ({num_sub_states} sub-states, {num_sub_trans} sub-trans.)</td></tr>"

                rows_html += f"<tr><td><b>Color:</b></td><td><span style='{color_style}'>{html.escape(color_obj.name())}</span></td></tr>"
                rows_html += f"<tr><td><b>Entry:</b></td><td>{format_prop_text(props.get('entry_action', ''))}</td></tr>"
                rows_html += f"<tr><td><b>During:</b></td><td>{format_prop_text(props.get('during_action', ''))}</td></tr>"
                rows_html += f"<tr><td><b>Exit:</b></td><td>{format_prop_text(props.get('exit_action', ''))}</td></tr>"
                if props.get('description'): rows_html += f"<tr><td colspan='2'><b>Desc:</b> {format_prop_text(props.get('description'), 50)}</td></tr>"

            elif isinstance(item, GraphicsTransitionItem):
                color_val = props.get('color', COLOR_ITEM_TRANSITION_DEFAULT)
                try: color_obj = QColor(color_val)
                except: color_obj = QColor(COLOR_ITEM_TRANSITION_DEFAULT)
                text_on_color = 'black' if color_obj.lightnessF() > 0.5 else 'white'
                color_style = f"background-color:{color_obj.name()}; color:{text_on_color}; padding: 1px 4px; border-radius:2px;"

                event_text = html.escape(props.get('event', '')) if props.get('event') else ''
                condition_text = f"[{html.escape(props.get('condition', ''))}]" if props.get('condition') else ''
                action_text = f"/{{{format_prop_text(props.get('action', ''), 15)}}}" if props.get('action') else ''
                label_parts = [p for p in [event_text, condition_text, action_text] if p]
                full_label = " ".join(label_parts) if label_parts else "<i>(No Label)</i>"

                rows_html += f"<tr><td><b>Label:</b></td><td style='font-size:8pt;'>{full_label}</td></tr>"
                rows_html += f"<tr><td><b>From:</b></td><td>{html.escape(props.get('source','N/A'))}</td></tr>"
                rows_html += f"<tr><td><b>To:</b></td><td>{html.escape(props.get('target','N/A'))}</td></tr>"
                rows_html += f"<tr><td><b>Color:</b></td><td><span style='{color_style}'>{html.escape(color_obj.name())}</span></td></tr>"
                rows_html += f"<tr><td><b>Curve:</b></td><td>Bend={props.get('control_offset_x',0):.0f}, Shift={props.get('control_offset_y',0):.0f}</td></tr>"
                if props.get('description'): rows_html += f"<tr><td colspan='2'><b>Desc:</b> {format_prop_text(props.get('description'), 50)}</td></tr>"

            elif isinstance(item, GraphicsCommentItem):
                rows_html += f"<tr><td colspan='2'><b>Text:</b> {format_prop_text(props.get('text', ''), 60)}</td></tr>"
            else:
                rows_html = "<tr><td>Unknown Item Type</td></tr>"
                item_type_name = "Unknown"

            html_content = f"""<div style='font-family: "Segoe UI", Arial, sans-serif; font-size: 9pt; line-height: 1.5;'>
                             <h4 style='margin:0 0 5px 0; padding:2px 0; color: {COLOR_ACCENT_PRIMARY}; border-bottom: 1px solid {COLOR_BORDER_LIGHT};'>Type: {item_type_name}</h4>
                             <table style='width: 100%; border-collapse: collapse;'>{rows_html}</table></div>"""
        elif len(selected_items) > 1:
            html_content = f"<i><b>{len(selected_items)} items selected.</b><br>Select a single item to view/edit its properties.</i>"
            item_type_for_tooltip = f"{len(selected_items)} items"
        else:
            html_content = "<i>No item selected.</i><br><small>Click an item in the diagram or use tools to add new items.</small>"

        self.properties_editor_label.setText(html_content)
        self.properties_edit_button.setEnabled(edit_enabled)
        self.properties_edit_button.setToolTip(f"Edit detailed properties of the selected {item_type_for_tooltip}" if edit_enabled else "Select a single item to enable editing")

    def _on_edit_selected_item_properties_from_dock(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1:
            self.scene.edit_item_properties(selected_items[0])

    def _update_window_title(self):
        title = APP_NAME
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        title += f" - {file_name}"
        if self.py_sim_active: title += " [PySim Running]"
        self.setWindowTitle(title + ("[*]" if self.isWindowModified() else ""))
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"File: {file_name}{' *' if self.isWindowModified() else ''} | PySim: {'Active' if self.py_sim_active else 'Idle'}")

    def _update_save_actions_enable_state(self):
        self.save_action.setEnabled(self.isWindowModified())

    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo())
        self.redo_action.setEnabled(self.undo_stack.canRedo())
        undo_text = self.undo_stack.undoText()
        redo_text = self.undo_stack.redoText()
        self.undo_action.setText(f"&Undo {undo_text}" if undo_text else "&Undo")
        self.redo_action.setText(f"&Redo {redo_text}" if redo_text else "&Redo")

    def _update_matlab_status_display(self, connected, message):
        text = f"MATLAB: {'Connected' if connected else 'Not Connected'}"
        tooltip = f"MATLAB Status: {message}"
        if hasattr(self, 'matlab_status_label'):
            self.matlab_status_label.setText(text)
            self.matlab_status_label.setToolTip(tooltip)
            style_sheet = f"font-weight: bold; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE if connected else '#C62828'};"
            self.matlab_status_label.setStyleSheet(style_sheet)
        if "Initializing" not in message:
            logging.info("MATLAB Conn: %s", message)
        self._update_matlab_actions_enabled_state()

    def _update_matlab_actions_enabled_state(self):
        can_run_matlab = self.matlab_connection.connected and not self.py_sim_active
        for action in [self.export_simulink_action, self.run_simulation_action, self.generate_code_action]:
            action.setEnabled(can_run_matlab)
        self.matlab_settings_action.setEnabled(not self.py_sim_active)

    def _start_matlab_operation(self, operation_name):
        logging.info("MATLAB Operation: %s starting...", operation_name)
        if hasattr(self, 'status_label'): self.status_label.setText(f"Running: {operation_name}...")
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False)

    def _finish_matlab_operation(self):
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(False)
        if hasattr(self, 'status_label'): self.status_label.setText("Ready")
        self.set_ui_enabled_for_matlab_op(True)
        logging.info("MATLAB Operation: Finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        if hasattr(self, 'menuBar'): self.menuBar().setEnabled(enabled)
        for child in self.findChildren(QToolBar): child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock"]:
            dock = self.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(enabled)
        self._update_py_simulation_actions_enabled_state()

    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation()
        log_level = logging.INFO if success else logging.ERROR
        logging.log(log_level, "MATLAB Result: %s", message)
        if success:
            if "Model generation" in message and data:
                self.last_generated_model_path = data
                QMessageBox.information(self, "Simulink Model Generation", f"Simulink model generated successfully:\n{data}")
            elif "Simulation" in message:
                QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else:
            QMessageBox.warning(self, "MATLAB Operation Failed", message)

    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation()
        log_level = logging.INFO if success else logging.ERROR
        logging.log(log_level, "MATLAB Code Gen Result: %s", message)

        if success and output_dir:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText)
            abs_output_dir = os.path.abspath(output_dir)
            msg_box.setText(f"Code generation completed.<br>Output directory: <a href='file:///{abs_output_dir}'>{abs_output_dir}</a>")
            msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction)
            open_dir_button = msg_box.addButton("Open Directory", QMessageBox.ActionRole)
            msg_box.addButton(QMessageBox.Ok)
            msg_box.exec_()
            if msg_box.clickedButton() == open_dir_button:
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(abs_output_dir)):
                    logging.error("Error opening directory %s", abs_output_dir)
                    QMessageBox.warning(self, "Error Opening Directory", f"Could not open directory:\n{abs_output_dir}")
        elif not success:
            QMessageBox.warning(self, "Code Generation Failed", message)

    def _prompt_save_if_dirty(self) -> bool:
        if not self.isWindowModified(): return True

        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python FSM simulation before saving or opening a new file.")
            return False

        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes?",
                                     f"The document '{file_name}' has unsaved changes.\nDo you want to save them before continuing?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save)

        if reply == QMessageBox.Save: return self.on_save_file()
        return reply != QMessageBox.Cancel

    def on_new_file(self, silent=False):
        if not silent and not self._prompt_save_if_dirty(): return False

        self.on_stop_py_simulation(silent=True)
        self.scene.clear()
        self.scene.setSceneRect(0,0,6000,4500)
        self.current_file_path = None
        self.last_generated_model_path = None
        self.undo_stack.clear()
        self.scene.set_dirty(False)
        self.setWindowModified(False)

        self._update_window_title()
        self._update_undo_redo_actions_enable_state()
        if not silent:
            logging.info("New diagram created. Ready.")
            if hasattr(self, 'status_label'): self.status_label.setText("New diagram created. Ready.")
        self.view.resetTransform()
        self.view.centerOn(self.scene.sceneRect().center())
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger()
        return True

    def on_open_file(self):
        if not self._prompt_save_if_dirty(): return

        self.on_stop_py_simulation(silent=True)
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)

        if file_path:
            logging.info("Attempting to open file: %s", file_path)
            if self._load_from_path(file_path):
                self.current_file_path = file_path
                self.last_generated_model_path = None
                self.undo_stack.clear()
                self.scene.set_dirty(False)
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                logging.info("Successfully opened: %s", file_path)
                if hasattr(self, 'status_label'): self.status_label.setText(f"Opened: {os.path.basename(file_path)}")
                items_bounds = self.scene.itemsBoundingRect()
                if not items_bounds.isEmpty():
                    self.view.fitInView(items_bounds.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)
                else:
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())
            else:
                QMessageBox.critical(self, "Error Opening File", f"Could not load or parse file: {file_path}")
                logging.error("Failed to open file: %s", file_path)

    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict) or ('states' not in data or 'transitions' not in data):
                logging.error("Error: Invalid BSM file format in %s. Missing 'states' or 'transitions' keys.", file_path)
                return False
            self.scene.load_diagram_data(data)
            return True
        except json.JSONDecodeError as e:
            logging.error("Error decoding JSON from %s: %s", file_path, e)
            return False
        except Exception as e:
            logging.error("Error loading file %s: %s: %s", file_path, type(e).__name__, str(e), exc_info=True)
            return False

    def on_save_file(self) -> bool:
        if not self.current_file_path:
            return self.on_save_file_as()
        return self._save_to_path(self.current_file_path)

    def on_save_file_as(self) -> bool:
        start_path = self.current_file_path if self.current_file_path \
                     else os.path.join(QDir.homePath(), "untitled" + FILE_EXTENSION)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As", start_path, FILE_FILTER)

        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION
            if self._save_to_path(file_path):
                self.current_file_path = file_path
                return True
        return False

    def _save_to_path(self, file_path) -> bool:
        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python FSM simulation before saving.")
            return False

        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            error_str = save_file.errorString()
            logging.error("Error opening save file %s: %s", file_path, error_str)
            QMessageBox.critical(self, "Save Error", f"Failed to open file for saving:\n{error_str}")
            return False
        try:
            data = self.scene.get_diagram_data()
            json_data = json.dumps(data, indent=4, ensure_ascii=False)
            bytes_written = save_file.write(json_data.encode('utf-8'))

            if bytes_written == -1:
                error_str = save_file.errorString()
                logging.error("Error writing data to %s: %s", file_path, error_str)
                QMessageBox.critical(self, "Save Error", f"Failed to write data to file:\n{error_str}")
                save_file.cancelWriting()
                return False

            if not save_file.commit():
                error_str = save_file.errorString()
                logging.error("Error committing save to %s: %s", file_path, error_str)
                QMessageBox.critical(self, "Save Error", f"Failed to commit saved file:\n{error_str}")
                return False

            logging.info("File saved successfully: %s", file_path)
            if hasattr(self, 'status_label'): self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            self.scene.set_dirty(False)
            self.setWindowModified(False)
            self._update_window_title()
            return True
        except Exception as e:
            logging.error("Error saving file %s: %s: %s", file_path, type(e).__name__, str(e), exc_info=True)
            QMessageBox.critical(self, "Save Error", f"An error occurred during saving:\n{str(e)}")
            save_file.cancelWriting()
            return False

    def on_select_all(self): self.scene.select_all()
    def on_delete_selected(self): self.scene.delete_selected_items()

    def on_export_simulink(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected. Configure in Simulation menu.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before exporting to Simulink.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Export to Simulink")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp, "->M"))
        layout = QFormLayout(dialog)
        layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)

        default_model_name_base = os.path.splitext(os.path.basename(self.current_file_path))[0] if self.current_file_path else "BSM_Model"
        model_name_default = "".join(c if c.isalnum() or c=='_' else '_' for c in default_model_name_base)
        if not model_name_default or not model_name_default[0].isalpha():
            model_name_default = "Mdl_" + model_name_default
        model_name_default = model_name_default.replace('-', '_')

        model_name_edit = QLineEdit(model_name_default)
        layout.addRow("Simulink Model Name:", model_name_edit)

        default_out_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        output_dir_edit = QLineEdit(default_out_dir)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw")," Browse...")
        browse_btn.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(output_dir_edit, 1); dir_layout.addWidget(browse_btn)
        layout.addRow("Output Directory:", dir_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        dialog.setMinimumWidth(450)

        if dialog.exec_() == QDialog.Accepted:
            model_name = model_name_edit.text().strip()
            output_dir = output_dir_edit.text().strip()
            if not model_name or not output_dir:
                QMessageBox.warning(self, "Input Error", "Model name and output directory must be specified.")
                return
            if not model_name[0].isalpha() or not all(c.isalnum() or c == '_' for c in model_name):
                QMessageBox.warning(self, "Invalid Model Name", "Model name must start with a letter, and contain only alphanumeric characters or underscores.")
                return
            try: os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create directory:\n{e}")
                return

            diagram_data = self.scene.get_diagram_data()
            if not diagram_data['states']:
                QMessageBox.information(self, "Empty Diagram", "Cannot export: the diagram contains no states.")
                return

            self._start_matlab_operation(f"Exporting '{model_name}' to Simulink")
            self.matlab_connection.generate_simulink_model(diagram_data['states'], diagram_data['transitions'], output_dir, model_name)

    def on_run_simulation(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before running a MATLAB simulation.")
            return

        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model to Simulate", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path
        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Simulation stop time (seconds):", 10.0, 0.001, 86400.0, 3)
        if not ok: return

        self._start_matlab_operation(f"Running Simulink simulation for '{os.path.basename(model_path)}'")
        self.matlab_connection.run_simulation(model_path, sim_time)

    def on_generate_code(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before generating code via MATLAB.")
            return

        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model for Code Generation", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path
        dialog = QDialog(self)
        dialog.setWindowTitle("Code Generation Options")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"))
        layout = QFormLayout(dialog); layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)

        lang_combo = QComboBox(); lang_combo.addItems(["C", "C++"]); lang_combo.setCurrentText("C++")
        layout.addRow("Target Language:", lang_combo)

        output_dir_edit = QLineEdit(os.path.dirname(model_path))
        browse_btn_codegen = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw")," Browse...")
        browse_btn_codegen.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Base Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
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
                QMessageBox.warning(self, "Input Error", "Base output directory required.")
                return
            try: os.makedirs(output_dir_base, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create directory:\n{e}")
                return

            self._start_matlab_operation(f"Generating {language} code for '{os.path.basename(model_path)}'")
            self.matlab_connection.generate_code(model_path, language, output_dir_base)

    def _get_bundled_file_path(self, filename: str) -> str | None:
        try:
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                base_path = sys._MEIPASS
            elif getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))

            possible_paths = [
                os.path.join(base_path, filename),
                os.path.join(base_path, 'docs', filename),
                os.path.join(base_path, 'resources', filename),
                os.path.join(base_path, 'examples', filename)
            ]
            for path_to_check in possible_paths:
                if os.path.exists(path_to_check):
                    return path_to_check
            direct_path = os.path.join(base_path, filename)
            if os.path.exists(direct_path):
                return direct_path

            logger.warning("Bundled file '%s' not found in expected locations relative to %s.", filename, base_path)
            return None
        except Exception as e:
            logger.error("Error determining bundled file path for '%s': %s", filename, e, exc_info=True)
            return None

    def _open_example_file(self, filename: str):
        if not self._prompt_save_if_dirty():
            return

        example_file_path = self._get_bundled_file_path(filename)

        if example_file_path and os.path.exists(example_file_path):
            logger.info("Attempting to open example file: %s", example_file_path)
            if self._load_from_path(example_file_path):
                self.current_file_path = example_file_path
                self.last_generated_model_path = None
                self.undo_stack.clear()
                self.scene.set_dirty(False)
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                logging.info("Successfully opened example: %s", filename)
                if hasattr(self, 'status_label'): self.status_label.setText(f"Opened example: {filename}")
                items_bounds = self.scene.itemsBoundingRect()
                if not items_bounds.isEmpty():
                    self.view.fitInView(items_bounds.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)
                else:
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())
            else:
                QMessageBox.critical(self, "Error Opening Example", f"Could not load or parse example file: {filename}")
                logging.error("Failed to open example file: %s", filename)
        else:
            QMessageBox.warning(self, "Example Not Found", f"The example file '{filename}' could not be found.")
            logging.warning("Example file '%s' not found at expected path: %s", filename, example_file_path)

    def on_show_quick_start(self):
        guide_filename = "QUICK_START.html"
        guide_path = self._get_bundled_file_path(guide_filename)
        if guide_path:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path)):
                QMessageBox.warning(self, "Could Not Open Guide", f"Failed to open the quick start guide using the default application for '{guide_filename}'. Path: {guide_path}")
                logging.warning("Failed to open quick start guide at %s", guide_path)
        else:
            QMessageBox.information(self, "Quick Start Not Found", f"The quick start guide ('{guide_filename}') was not found in the application bundle.")

    def on_about(self):
        about_text = f"""<h3 style='color:{COLOR_ACCENT_PRIMARY};'>{APP_NAME} v{APP_VERSION}</h3>
                         <p>A graphical tool for designing, simulating, and generating code for Finite State Machines (FSMs).</p>
                         <p>Features:</p>
                         <ul>
                             <li>Intuitive FSM diagram creation and editing.</li>
                             <li>Internal Python-based FSM simulation.</li>
                             <li>Integration with MATLAB/Simulink for model export, simulation, and C/C++ code generation.</li>
                             <li>AI Assistant for FSM generation from descriptions and chat-based help.</li>
                         </ul>
                         <p>Developed as a versatile environment for FSM development and education.</p>
                         <p style='font-size:8pt; color:{COLOR_TEXT_SECONDARY};'>
                           This tool is intended for research and educational purposes.
                           Always verify generated models and code.
                         </p>
                      """
        QMessageBox.about(self, "About " + APP_NAME, about_text)

    def closeEvent(self, event: QCloseEvent):
        self.on_stop_py_simulation(silent=True)
        if self.internet_check_timer and self.internet_check_timer.isActive():
            self.internet_check_timer.stop()

        if self.ai_chatbot_manager:
            self.ai_chatbot_manager.stop_chatbot()

        if self.resource_monitor_worker and self.resource_monitor_thread:
            logger.info("Stopping resource monitor...")
            if self.resource_monitor_thread.isRunning():
                QMetaObject.invokeMethod(self.resource_monitor_worker, "stop_monitoring", Qt.QueuedConnection)
                self.resource_monitor_thread.quit()
                if not self.resource_monitor_thread.wait(2500):
                    logger.warning("Resource monitor thread did not quit gracefully. Terminating.")
                    self.resource_monitor_thread.terminate()
                    self.resource_monitor_thread.wait()
                else:
                    logger.info("Resource monitor thread stopped.")
            self.resource_monitor_worker = None
            self.resource_monitor_thread = None


        if self._prompt_save_if_dirty():
            if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads:
                logging.info("Closing. %d MATLAB processes may persist if not completed.", len(self.matlab_connection._active_threads))
            event.accept()
        else:
            event.ignore()
            if self.internet_check_timer:
                self.internet_check_timer.start()

    def _init_internet_status_check(self):
        self.internet_check_timer.timeout.connect(self._run_internet_check_job)
        self.internet_check_timer.start(15000)
        QTimer.singleShot(100, self._run_internet_check_job)

    def _run_internet_check_job(self):
        host_to_check = "8.8.8.8"
        port_to_check = 53
        connection_timeout = 1.5

        current_status = False
        status_message_detail = "Checking..."
        try:
            s = socket.create_connection((host_to_check, port_to_check), timeout=connection_timeout)
            s.close()
            current_status = True
            status_message_detail = "Connected"
        except socket.timeout:
            status_message_detail = "Disconnected (Timeout)"
        except socket.gaierror as e:
            status_message_detail = "Disconnected (DNS/Net Issue)"
        except OSError as e:
            status_message_detail = "Disconnected (Net Error)"

        if current_status != self._internet_connected or self._internet_connected is None:
            self._internet_connected = current_status
            self._update_internet_status_display(current_status, status_message_detail)

    def _update_internet_status_display(self, is_connected: bool, message_detail: str):
        full_status_text = f"Internet: {message_detail}"
        if hasattr(self, 'internet_status_label'):
            self.internet_status_label.setText(full_status_text)
            try:
                check_host_name_for_tooltip = socket.getfqdn('8.8.8.8') if is_connected else '8.8.8.8'
            except Exception: check_host_name_for_tooltip = '8.8.8.8'
            self.internet_status_label.setToolTip(f"{full_status_text} (Checks {check_host_name_for_tooltip}:{53})")

            style_sheet = f"font-weight: normal; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE if is_connected else '#D32F2F'};"
            self.internet_status_label.setStyleSheet(style_sheet)
        logging.debug("Internet Status: %s", message_detail)

        if hasattr(self.ai_chatbot_manager, 'set_online_status'):
            self.ai_chatbot_manager.set_online_status(is_connected)

    def _update_py_sim_status_display(self):
        if hasattr(self, 'py_sim_status_label'):
            if self.py_sim_active and self.py_fsm_engine:
                state_name_display = self.py_fsm_engine.get_current_state_name()
                self.py_sim_status_label.setText(f"PySim: Active ({state_name_display})")
                self.py_sim_status_label.setStyleSheet(f"font-weight: bold; padding: 0px 5px; color: {COLOR_PY_SIM_STATE_ACTIVE};")
            else:
                self.py_sim_status_label.setText("PySim: Idle")
                self.py_sim_status_label.setStyleSheet("font-weight: normal; padding: 0px 5px;")

    def _update_py_simulation_actions_enabled_state(self):
        is_matlab_op_running = self.progress_bar.isVisible() if hasattr(self, 'progress_bar') else False
        sim_inactive = not self.py_sim_active

        self.start_py_sim_action.setEnabled(sim_inactive and not is_matlab_op_running)
        if hasattr(self, 'py_sim_start_btn'): self.py_sim_start_btn.setEnabled(sim_inactive and not is_matlab_op_running)

        sim_controls_enabled = self.py_sim_active and not is_matlab_op_running
        for widget in [self.stop_py_sim_action, self.reset_py_sim_action]: widget.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_stop_btn'): self.py_sim_stop_btn.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_reset_btn'): self.py_sim_reset_btn.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_step_btn'): self.py_sim_step_btn.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_event_name_edit'): self.py_sim_event_name_edit.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_trigger_event_btn'): self.py_sim_trigger_event_btn.setEnabled(sim_controls_enabled)
        if hasattr(self, 'py_sim_event_combo'): self.py_sim_event_combo.setEnabled(sim_controls_enabled)

    def set_ui_enabled_for_py_sim(self, is_sim_running: bool):
        self.py_sim_active = is_sim_running
        self._update_window_title()
        is_editable = not is_sim_running

        if is_sim_running and self.scene.current_mode != "select":
            self.scene.set_mode("select")
        elif not is_sim_running and self.scene.current_mode != "select":
            pass

        for item in self.scene.items():
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)):
                item.setFlag(QGraphicsItem.ItemIsMovable, is_editable and self.scene.current_mode == "select")

        actions_to_toggle = [
            self.new_action, self.open_action, self.save_action, self.save_as_action,
            self.undo_action, self.redo_action, self.delete_action, self.select_all_action,
            self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action
        ]
        for action in actions_to_toggle:
            if hasattr(action, 'setEnabled'): action.setEnabled(is_editable)

        if hasattr(self, 'tools_dock'): self.tools_dock.setEnabled(is_editable)
        if hasattr(self, 'properties_edit_button'):
             self.properties_edit_button.setEnabled(is_editable and len(self.scene.selectedItems())==1)

        self._update_matlab_actions_enabled_state()
        self._update_py_simulation_actions_enabled_state()
        self._update_py_sim_status_display()

    def _highlight_sim_active_state(self, state_name_to_highlight: str | None):
        if self._py_sim_currently_highlighted_item:
            logging.debug("PySim: Unhighlighting state '%s'", self._py_sim_currently_highlighted_item.text_label)
            self._py_sim_currently_highlighted_item.set_py_sim_active_style(False)
            self._py_sim_currently_highlighted_item = None

        if state_name_to_highlight and self.py_fsm_engine:
            top_level_active_state_id = self.py_fsm_engine.sm.current_state.id if self.py_fsm_engine.sm and self.py_fsm_engine.sm.current_state else None
            
            if top_level_active_state_id:
                for item in self.scene.items():
                    if isinstance(item, GraphicsStateItem) and item.text_label == top_level_active_state_id:
                        logging.debug("PySim: Highlighting top-level active state '%s' (full hierarchical: '%s')", top_level_active_state_id, state_name_to_highlight)
                        item.set_py_sim_active_style(True)
                        self._py_sim_currently_highlighted_item = item
                        if self.view and not self.view.ensureVisible(item, 50, 50):
                            self.view.centerOn(item)
                        break
        self.scene.update()

    def _highlight_sim_taken_transition(self, transition_label_or_id: str | None):
        if self._py_sim_currently_highlighted_transition:
            if hasattr(self._py_sim_currently_highlighted_transition, 'set_py_sim_active_style'):
                 self._py_sim_currently_highlighted_transition.set_py_sim_active_style(False) # type: ignore
            self._py_sim_currently_highlighted_transition = None
        self.scene.update()


    def _update_py_simulation_dock_ui(self):
        if not self.py_fsm_engine or not self.py_sim_active:
            self.py_sim_current_state_label.setText("<i>Not Running</i>")
            self.py_sim_variables_table.setRowCount(0)
            self._highlight_sim_active_state(None)
            self._highlight_sim_taken_transition(None)
            self.py_sim_event_combo.clear()
            self.py_sim_event_combo.addItem("None (Internal Step)")
            return

        hierarchical_state_name = self.py_fsm_engine.get_current_state_name()
        self.py_sim_current_state_label.setText(f"<b>{html.escape(hierarchical_state_name or 'N/A')}</b>")
        self._highlight_sim_active_state(hierarchical_state_name)

        all_vars_display = []
        main_vars = self.py_fsm_engine.get_variables()
        for name, value in sorted(main_vars.items()):
            all_vars_display.append((f"{name}", str(value)))

        if self.py_fsm_engine.active_sub_simulator:
            sub_vars = self.py_fsm_engine.active_sub_simulator.get_variables()
            for name, value in sorted(sub_vars.items()):
                all_vars_display.append((f"[SUB] {name}", str(value)))

        self.py_sim_variables_table.setRowCount(len(all_vars_display))
        for row, (name, value) in enumerate(all_vars_display):
            self.py_sim_variables_table.setItem(row, 0, QTableWidgetItem(name))
            self.py_sim_variables_table.setItem(row, 1, QTableWidgetItem(value))
        self.py_sim_variables_table.resizeColumnsToContents()

        current_combo_text = self.py_sim_event_combo.currentText()
        self.py_sim_event_combo.clear()
        self.py_sim_event_combo.addItem("None (Internal Step)")
        
        possible_events_set = set()
        if self.py_fsm_engine.active_sub_simulator and self.py_fsm_engine.active_sub_simulator.sm:
            sub_events = self.py_fsm_engine.active_sub_simulator.get_possible_events_from_current_state()
            possible_events_set.update(sub_events)
        
        main_fsm_events = self.py_fsm_engine.get_possible_events_from_current_state()
        possible_events_set.update(main_fsm_events)
        
        possible_events = sorted(list(possible_events_set))

        if possible_events:
            self.py_sim_event_combo.addItems(possible_events)

        index = self.py_sim_event_combo.findText(current_combo_text)
        if index != -1:
            self.py_sim_event_combo.setCurrentIndex(index)
        elif not possible_events:
             self.py_sim_event_combo.setCurrentIndex(0)


    def _append_to_py_simulation_log(self, log_entries: list[str]):
        for entry in log_entries:
            cleaned_entry = html.escape(entry)
            if "[Condition]" in entry or "[Eval Error]" in entry or "ERROR" in entry.upper() or "SecurityError" in entry:
                cleaned_entry = f"<span style='color:red; font-weight:bold;'>{cleaned_entry}</span>"
            elif "[Safety Check Failed]" in entry or "[Action Blocked]" in entry or "[Condition Blocked]" in entry:
                cleaned_entry = f"<span style='color:orange; font-weight:bold;'>{cleaned_entry}</span>"
            elif "Transitioned from" in entry or "Reset to state" in entry or "Simulation started" in entry or "Entering state" in entry or "Exiting state" in entry:
                cleaned_entry = f"<span style='color:{COLOR_ACCENT_PRIMARY}; font-weight:bold;'>{cleaned_entry}</span>"
            elif "No eligible transition" in entry or "event is not allowed" in entry:
                cleaned_entry = f"<span style='color:{COLOR_TEXT_SECONDARY};'>{cleaned_entry}</span>"

            self.py_sim_action_log_output.append(cleaned_entry)
        self.py_sim_action_log_output.verticalScrollBar().setValue(self.py_sim_action_log_output.verticalScrollBar().maximum())

        if log_entries:
            last_log_short = log_entries[-1].split('\n')[0][:100]
            important_keywords = ["Transitioned from", "No eligible transition", "ERROR", "Reset to state",
                                  "Simulation started", "Simulation stopped", "SecurityError",
                                  "Safety Check Failed", "Action Blocked", "Condition Blocked",
                                  "Entering state", "Exiting state", "HALTED"]
            if any(keyword in log_entries[-1] for keyword in important_keywords):
                logger.info("PySim: %s", last_log_short)

    def on_start_py_simulation(self):
        if self.py_sim_active:
            QMessageBox.information(self, "Simulation Active", "Python simulation is already running.")
            return

        if self.scene.is_dirty():
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "The diagram has unsaved changes that won't be reflected in the simulation unless saved.\nStart simulation with the current in-memory state anyway?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No:
                return

        diagram_data = self.scene.get_diagram_data()
        if not diagram_data.get('states'):
            QMessageBox.warning(self, "Empty Diagram", "Cannot start simulation: The diagram has no states.")
            return
        try:
            self.py_fsm_engine = FSMSimulator(diagram_data['states'], diagram_data['transitions'], halt_on_action_error=True)
            self.set_ui_enabled_for_py_sim(True)
            self.py_sim_action_log_output.clear()
            self.py_sim_action_log_output.setHtml("<i>Simulation log will appear here...</i>")
            initial_log = ["Python FSM Simulation started."] + self.py_fsm_engine.get_last_executed_actions_log()
            self._append_to_py_simulation_log(initial_log)
            self._update_py_simulation_dock_ui()
        except FSMError as e:
            msg = f"Failed to start Python FSM simulation:\n{e}"
            QMessageBox.critical(self, "FSM Initialization Error", msg)
            self._append_to_py_simulation_log([f"ERROR Starting Sim: {msg}"])
            logger.error("PySim: Failed to start Python FSM simulation: %s", e, exc_info=True)
            self.py_fsm_engine = None
            self.set_ui_enabled_for_py_sim(False)
        except Exception as e:
            msg = f"An unexpected error occurred while starting simulation:\n{type(e).__name__}: {e}"
            QMessageBox.critical(self, "Simulation Start Error", msg)
            self._append_to_py_simulation_log([f"UNEXPECTED ERROR Starting Sim: {msg}"])
            logger.error("PySim: Unexpected error starting simulation:", exc_info=True)
            self.py_fsm_engine = None
            self.set_ui_enabled_for_py_sim(False)

    def on_stop_py_simulation(self, silent=False):
        if not self.py_sim_active: return

        self._highlight_sim_active_state(None)
        self._highlight_sim_taken_transition(None)

        self.py_fsm_engine = None
        self.set_ui_enabled_for_py_sim(False)
        self._update_py_simulation_dock_ui()

        if not silent:
            self._append_to_py_simulation_log(["Python FSM Simulation stopped."])

    def on_reset_py_simulation(self):
        if not self.py_fsm_engine or not self.py_sim_active:
            QMessageBox.warning(self, "Simulation Not Active", "Python simulation is not running. Start it first.")
            return
        try:
            self.py_fsm_engine.reset()
            self.py_sim_action_log_output.append("<hr><i style='color:grey;'>Simulation Reset</i><hr>")
            reset_logs = self.py_fsm_engine.get_last_executed_actions_log()
            self._append_to_py_simulation_log(reset_logs)
            self._update_py_simulation_dock_ui()
            self._highlight_sim_taken_transition(None)
        except FSMError as e:
            msg = f"Failed to reset Python FSM simulation:\n{e}"
            QMessageBox.critical(self, "FSM Reset Error", msg)
            self._append_to_py_simulation_log([f"ERROR DURING RESET: {msg}"])
            logger.error("PySim: Failed to reset: %s", e, exc_info=True)
        except Exception as e:
            msg = f"An unexpected error occurred during FSM reset:\n{type(e).__name__}: {e}"
            QMessageBox.critical(self, "FSM Reset Error", msg)
            self._append_to_py_simulation_log([f"UNEXPECTED ERROR DURING RESET: {msg}"])
            logger.error("PySim: Unexpected error during reset:", exc_info=True)


    def on_step_py_simulation(self):
        if not self.py_fsm_engine or not self.py_sim_active:
            QMessageBox.warning(self, "Simulation Not Active", "Python simulation is not running.")
            return
        try:
            _, log_entries = self.py_fsm_engine.step(event_name=None)
            self._append_to_py_simulation_log(log_entries)
            self._update_py_simulation_dock_ui()
            self._highlight_sim_taken_transition(None)
            if self.py_fsm_engine.simulation_halted_flag:
                self._append_to_py_simulation_log(["[HALTED] Simulation halted due to an error in an action. Please reset."])
                QMessageBox.warning(self, "Simulation Halted", "Simulation halted due to an error in an FSM action. Please reset the simulation.")
        except FSMError as e:
            msg = f"Simulation Step Error: {e}"
            QMessageBox.warning(self, "Simulation Step Error", str(e))
            self._append_to_py_simulation_log([f"ERROR DURING STEP: {msg}"])
            logger.error("PySim: Step error: %s", e, exc_info=True)
            if self.py_fsm_engine.simulation_halted_flag:
                self._append_to_py_simulation_log(["[HALTED] Simulation halted. Please reset."])
        except Exception as e:
            msg = f"An unexpected error occurred during simulation step:\n{type(e).__name__}: {e}"
            QMessageBox.critical(self, "Simulation Step Error", msg)
            self._append_to_py_simulation_log([f"UNEXPECTED ERROR DURING STEP: {msg}"])
            logger.error("PySim: Unexpected step error:", exc_info=True)


    def on_trigger_py_event(self):
        if not self.py_fsm_engine or not self.py_sim_active:
            QMessageBox.warning(self, "Simulation Not Active", "Python simulation is not running.")
            return

        event_name_from_combo = self.py_sim_event_combo.currentText()
        event_name_from_edit = self.py_sim_event_name_edit.text().strip()

        event_to_trigger = None
        if event_name_from_edit:
            event_to_trigger = event_name_from_edit
        elif event_name_from_combo and event_name_from_combo != "None (Internal Step)":
            event_to_trigger = event_name_from_combo

        if not event_to_trigger:
            self.on_step_py_simulation()
            return

        try:
            _, log_entries = self.py_fsm_engine.step(event_name=event_to_trigger)
            self._append_to_py_simulation_log(log_entries)
            self._update_py_simulation_dock_ui()
            self.py_sim_event_name_edit.clear()
            self._highlight_sim_taken_transition(None)
            if self.py_fsm_engine.simulation_halted_flag:
                self._append_to_py_simulation_log(["[HALTED] Simulation halted due to an error in an action. Please reset."])
                QMessageBox.warning(self, "Simulation Halted", "Simulation halted due to an error in an FSM action. Please reset the simulation.")
        except FSMError as e:
            msg = f"Simulation Event Error ({html.escape(event_to_trigger)}): {e}"
            QMessageBox.warning(self, "Simulation Event Error", str(e))
            self._append_to_py_simulation_log([f"ERROR DURING EVENT '{html.escape(event_to_trigger)}': {msg}"])
            logger.error("PySim: Event trigger error for '%s': %s", event_to_trigger, e, exc_info=True)
            if self.py_fsm_engine.simulation_halted_flag:
                 self._append_to_py_simulation_log(["[HALTED] Simulation halted. Please reset."])
        except Exception as e:
            msg = f"An unexpected error occurred during event '{html.escape(event_to_trigger)}':\n{type(e).__name__}: {e}"
            QMessageBox.critical(self, "Simulation Event Error", msg)
            self._append_to_py_simulation_log([f"UNEXPECTED ERROR DURING EVENT '{html.escape(event_to_trigger)}': {msg}"])
            logger.error("PySim: Unexpected event trigger error for '%s':", event_to_trigger, exc_info=True)

    def log_message(self, level_str: str, message: str):
        level = getattr(logging, level_str.upper(), logging.INFO)
        logger.log(level, message)

    # --- End of copy-pasted methods ---

if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app_dir = os.path.dirname(os.path.abspath(__file__))
    dependencies_dir = os.path.join(app_dir, "dependencies", "icons")
    if not os.path.exists(dependencies_dir):
        try:
            os.makedirs(dependencies_dir, exist_ok=True)
            print(f"Info: Created directory for QSS icons (if needed): {dependencies_dir}")
        except OSError as e:
            print(f"Warning: Could not create directory {dependencies_dir}: {e}")

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET_GLOBAL)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
