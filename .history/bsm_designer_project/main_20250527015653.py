
# bsm_designer_project/main.py

import sys
import os
import tempfile
import subprocess
import io # For capturing stdout/stderr
import contextlib # For redirecting stdout/stderr
import json
import html
import math
import socket
import re
import logging
from PyQt5.QtCore import QTime, QTimer, QPointF, QMetaObject
import pygraphviz as pgv
import psutil
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None

# --- Custom Modules ---
from graphics_scene import DiagramScene, ZoomableView
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
from code_editor import CodeEditor # Import CodeEditor
from fsm_simulator import FSMSimulator, FSMError 
from ai_chatbot import AIChatbotManager
from dialogs import (MatlabSettingsDialog, FindReplaceDialog) # Added FindReplaceDialog
from config import (
    APP_VERSION, APP_NAME, FILE_EXTENSION, FILE_FILTER, STYLE_SHEET_GLOBAL,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG,
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_PRIMARY_LIGHT,
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_BACKGROUND_LIGHT, COLOR_GRID_MINOR, COLOR_GRID_MAJOR,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_ON_ACCENT,
    COLOR_ACCENT_SECONDARY, COLOR_BORDER_LIGHT, COLOR_BORDER_MEDIUM
)
from utils import get_standard_icon 

# --- UI Managers ---
from ui_py_simulation_manager import PySimulationUIManager
from ui_ai_chatbot_manager import AIChatUIManager

# --- Logging Setup ---
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

logger = logging.getLogger(__name__)

# --- DraggableToolButton Class Definition ---
class DraggableToolButton(QPushButton):
    def __init__(self, text, mime_type, item_type_data, parent=None):
        super().__init__(text, parent)
        self.setObjectName("DraggableToolButton")
        self.mime_type = mime_type
        self.item_type_data = item_type_data
        self.setText(text)
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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
        mime_data.setText(self.item_type_data)
        mime_data.setData(self.mime_type, self.item_type_data.encode())
        drag.setMimeData(mime_data)

        pixmap_size = QSize(max(150, self.width()), max(40, self.height()))
        pixmap = QPixmap(pixmap_size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        button_rect = QRectF(0, 0, pixmap_size.width() -1, pixmap_size.height() -1)
        bg_color = QColor(self.palette().color(self.backgroundRole())).lighter(110)
        if not bg_color.isValid() or bg_color.alpha() == 0:
            bg_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT)
        border_color_qcolor = QColor(COLOR_ACCENT_PRIMARY)

        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color_qcolor, 1.5))
        painter.drawRoundedRect(button_rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5)

        icon_pixmap = self.icon().pixmap(QSize(20, 20), QIcon.Normal, QIcon.On)
        text_x_offset = 10
        icon_y_offset = (pixmap_size.height() - icon_pixmap.height()) / 2
        if not icon_pixmap.isNull():
            painter.drawPixmap(int(text_x_offset), int(icon_y_offset), icon_pixmap)
            text_x_offset += icon_pixmap.width() + 8

        text_color_qcolor = self.palette().color(QPalette.ButtonText)
        if not text_color_qcolor.isValid():
            text_color_qcolor = QColor(COLOR_TEXT_PRIMARY)
        painter.setPen(text_color_qcolor)
        painter.setFont(self.font())

        text_rect = QRectF(text_x_offset, 0, pixmap_size.width() - text_x_offset - 5, pixmap_size.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 4, pixmap.height() // 2))
        drag.exec_(Qt.CopyAction | Qt.MoveAction)


# --- Embedded MATLAB Integration Logic ---
class MatlabCommandWorker(QObject):
    finished_signal = pyqtSignal(bool, str, str)

    def __init__(self, matlab_path, script_file, original_signal, success_message_prefix, model_name_for_context=None):
        super().__init__()
        self.matlab_path = matlab_path
        self.script_file = script_file
        self.original_signal = original_signal
        self.success_message_prefix = success_message_prefix
        self.model_name_for_context = model_name_for_context

    @pyqtSlot()
    def run_command(self):
        output_data_for_signal = ""
        success = False
        message = ""
        timeout_seconds = 600
        try:
            matlab_run_command = f"run('{self.script_file.replace(os.sep, '/')}')"
            cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", matlab_run_command]
            
            logger.debug(f"Executing MATLAB command: {' '.join(cmd)}")

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout_seconds,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            stdout_str = process.stdout if process.stdout else ""
            stderr_str = process.stderr if process.stderr else ""
            
            logger.debug(f"MATLAB STDOUT:\n{stdout_str[:1000]}...")
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
            else:
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
            self.finished_signal.emit(success, message, output_data_for_signal if success else "")


class MatlabConnection(QObject): 
    connectionStatusChanged = pyqtSignal(bool, str)
    simulationFinished = pyqtSignal(bool, str, str)
    codeGenerationFinished = pyqtSignal(bool, str, str)

    def __init__(self):
        super().__init__()
        self.matlab_path = ""
        self.connected = False
        self._active_threads: list[QThread] = []

    def set_matlab_path(self, path):
        old_path_attempt = path.strip() if path else "" 
        self.matlab_path = old_path_attempt

        if self.matlab_path and os.path.exists(self.matlab_path) and \
           (os.access(self.matlab_path, os.X_OK) or self.matlab_path.lower().endswith('.exe')):
            self.connected = True 
            self.connectionStatusChanged.emit(True, f"MATLAB path set and appears valid: {self.matlab_path}")
            return True
        else:
            self.connected = False
            self.matlab_path = "" 
            if old_path_attempt: 
                self.connectionStatusChanged.emit(False, f"MATLAB path '{old_path_attempt}' is invalid or not executable.")
            else: 
                 self.connectionStatusChanged.emit(False, "MATLAB path cleared or not set.")
            return False

    def test_connection(self):
        if not self.matlab_path:
            self.connected = False
            self.connectionStatusChanged.emit(False, "MATLAB path not set. Cannot test connection.")
            return False
        
        if not self.connected: 
            if not self.set_matlab_path(self.matlab_path): 
                return False 

        try:
            cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", "disp('MATLAB_CONNECTION_TEST_SUCCESS'); exit"]
            logger.debug(f"Testing MATLAB with command: {' '.join(cmd)}")
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            
            stdout_clean = process.stdout.strip() if process.stdout else ""
            stderr_clean = process.stderr.strip() if process.stderr else ""
            logger.debug(f"MATLAB Test STDOUT: {stdout_clean[:200]}")
            if stderr_clean: logger.debug(f"MATLAB Test STDERR: {stderr_clean[:200]}")


            if "MATLAB_CONNECTION_TEST_SUCCESS" in stdout_clean:
                self.connected = True
                self.connectionStatusChanged.emit(True, "MATLAB connection test successful.")
                return True
            else:
                self.connected = False
                error_msg = stderr_clean or stdout_clean or "Unexpected output from MATLAB."
                self.connectionStatusChanged.emit(False, f"MATLAB connection test failed: {error_msg[:200]}")
                return False
        except subprocess.TimeoutExpired:
            self.connected = False; self.connectionStatusChanged.emit(False, "MATLAB connection test timed out (20s)."); return False
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
            paths_to_check.append('matlab') 

        for path_candidate in paths_to_check:
            logger.debug(f"Auto-detect: Checking MATLAB candidate path: {path_candidate}")
            if path_candidate == 'matlab' and sys.platform != 'win32': 
                try: 
                    test_process = subprocess.run([path_candidate, "-batch", "exit"], timeout=5, capture_output=True, check=False)
                    if test_process.returncode == 0:
                        logger.info(f"Auto-detect: Found MATLAB in PATH: {path_candidate}")
                        if self.set_matlab_path(path_candidate): return True
                except (FileNotFoundError, subprocess.TimeoutExpired): 
                    logger.debug(f"Auto-detect: 'matlab' in PATH check failed or timed out for {path_candidate}")
                    continue
            elif os.path.exists(path_candidate) and os.access(path_candidate, os.X_OK): 
                logger.info(f"Auto-detect: Found MATLAB at: {path_candidate}")
                if self.set_matlab_path(path_candidate): return True 

        self.connectionStatusChanged.emit(False, "MATLAB auto-detection failed. Please set the path manually."); return False

    def _run_matlab_script(self, script_content, worker_signal, success_message_prefix, model_name_for_context=None):
        if not self.connected:
            worker_signal.emit(False, "MATLAB not connected or path invalid.", "")
            return

        try:
            temp_dir = tempfile.mkdtemp(prefix="bsm_matlab_")
            script_file_path = os.path.join(temp_dir, "matlab_script.m")
            with open(script_file_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            logger.debug(f"Temporary MATLAB script created at: {script_file_path}")
        except Exception as e:
            worker_signal.emit(False, f"Failed to create temporary MATLAB script: {e}", "")
            logger.error(f"Failed to create temp script: {e}", exc_info=True)
            return

        worker = MatlabCommandWorker(self.matlab_path, script_file_path, worker_signal, success_message_prefix, model_name_for_context)
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
            
            sf_x = state.get('x', 20 + i*150) / 2.5 + 20
            sf_y = state.get('y', 20) / 2.5 + 20
            sf_w = max(60, state.get('width', 120) / 2.5)
            sf_h = max(40, state.get('height', 60) / 2.5)


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


# --- ResourceMonitorWorker Class Definition (Moved to top level) ---
class ResourceMonitorWorker(QObject):
    resourceUpdate = pyqtSignal(float, float, float, str) # cpu, ram, gpu_util, gpu_name

    def __init__(self, interval_ms=2000, parent=None):
        super().__init__(parent)
        self.interval_ms = interval_ms
        self._monitoring = False
        self._nvml_initialized = False
        self._gpu_handle = None
        self._gpu_name_cache = "N/A"
        
        if PYNVML_AVAILABLE and pynvml:
            try:
                pynvml.nvmlInit()
                self._nvml_initialized = True
                if pynvml.nvmlDeviceGetCount() > 0:
                    self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    gpu_name_raw = pynvml.nvmlDeviceGetName(self._gpu_handle)
                    if isinstance(gpu_name_raw, bytes):
                        self._gpu_name_cache = gpu_name_raw.decode('utf-8')
                    elif isinstance(gpu_name_raw, str):
                        self._gpu_name_cache = gpu_name_raw
                    else:
                        logger.warning(f"NVML: Unexpected type for GPU name: {type(gpu_name_raw)}")
                        self._gpu_name_cache = "NVIDIA GPU Name TypeErr"
                else:
                    self._gpu_name_cache = "NVIDIA GPU N/A"
            except pynvml.NVMLError as e_nvml:
                logger.warning(f"Could not initialize NVML (for NVIDIA GPU monitoring): {e_nvml}")
                self._nvml_initialized = False
                error_code_str = f" (Code: {e_nvml.value})" if hasattr(e_nvml, 'value') else ""
                self._gpu_name_cache = f"NVIDIA NVML Err ({type(e_nvml).__name__}{error_code_str})"
            except AttributeError as e_attr: 
                 logger.warning(f"NVML: Attribute error during init (possibly on .decode for name): {e_attr}")
                 self._nvml_initialized = False
                 self._gpu_name_cache = "NVML Attr Err"
            except Exception as e: 
                logger.warning(f"Unexpected error during NVML init: {e}", exc_info=True)
                self._nvml_initialized = False
                self._gpu_name_cache = "NVML Init Error"
        elif not PYNVML_AVAILABLE:
            self._gpu_name_cache = "N/A (pynvml N/A)"

    @pyqtSlot()
    def start_monitoring(self):
        logger.info("ResourceMonitorWorker: start_monitoring called.")
        self._monitoring = True
        self._monitor_resources()

    @pyqtSlot()
    def stop_monitoring(self):
        logger.info("ResourceMonitorWorker: stop_monitoring called.")
        self._monitoring = False 
        if self._nvml_initialized and PYNVML_AVAILABLE and pynvml:
            try:
                pynvml.nvmlShutdown()
                logger.info("ResourceMonitorWorker: NVML shutdown.")
            except Exception as e:
                logger.warning(f"Error shutting down NVML: {e}")
        self._nvml_initialized = False
        self._gpu_handle = None

    def _monitor_resources(self):
        logger.debug("Resource monitor worker loop started.")
        short_sleep_ms = 100 
        cycles_per_update = max(1, self.interval_ms // short_sleep_ms)
        current_cycle = 0

        while self._monitoring:
            if not self._monitoring: 
                break

            if current_cycle == 0: 
                # --- NVML Re-initialization/Handle Acquisition Logic ---
                if PYNVML_AVAILABLE and pynvml and not self._nvml_initialized : 
                    try:
                        pynvml.nvmlInit()
                        self._nvml_initialized = True
                        logger.info("NVML re-initialized successfully in worker loop.")
                    except pynvml.NVMLError as e_reinit:
                        logger.warning(f"NVML: Failed to re-initialize in worker loop: {e_reinit}")
                        self._nvml_initialized = False 
                        error_code_str = f" (Code: {e_reinit.value})" if hasattr(e_reinit, 'value') else ""
                        self._gpu_name_cache = f"NVIDIA NVML ReinitErr ({type(e_reinit).__name__}{error_code_str})"
                
                if PYNVML_AVAILABLE and pynvml and self._nvml_initialized and not self._gpu_handle:
                    try:
                        if pynvml.nvmlDeviceGetCount() > 0:
                            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                            gpu_name_raw = pynvml.nvmlDeviceGetName(self._gpu_handle) 
                            if isinstance(gpu_name_raw, bytes): self._gpu_name_cache = gpu_name_raw.decode('utf-8')
                            elif isinstance(gpu_name_raw, str): self._gpu_name_cache = gpu_name_raw
                            else: self._gpu_name_cache = "NVIDIA GPU Name TypeErr (Poll)"
                            logger.info(f"NVML: GPU handle acquired for {self._gpu_name_cache} in worker loop.")
                        else:
                            self._gpu_name_cache = "NVIDIA GPU N/A" 
                    except pynvml.NVMLError as e_nvml_poll:
                        logger.debug(f"NVML: Error getting GPU handle during poll: {e_nvml_poll}")
                        error_code_str = f" (Code: {e_nvml_poll.value})" if hasattr(e_nvml_poll, 'value') else ""
                        self._gpu_name_cache = f"NVIDIA Poll Err ({type(e_nvml_poll).__name__}{error_code_str})"
                        self._gpu_handle = None 
                        if e_nvml_poll.value == pynvml.NVML_ERROR_UNINITIALIZED: self._nvml_initialized = False
                    except AttributeError as e_attr:
                         logger.warning(f"NVML: Attribute error getting GPU handle (possibly on .decode for name): {e_attr}")
                         self._gpu_name_cache = "NVML Handle Attr Err"
                         self._gpu_handle = None
                    except Exception as e_poll: 
                        logger.debug(f"NVML: Unexpected error getting GPU handle during poll: {e_poll}")
                        self._gpu_name_cache = "NVML Poll Error"
                        self._gpu_handle = None
                # --- End NVML Re-initialization/Handle Acquisition Logic ---
                
                try:
                    cpu_usage = psutil.cpu_percent(interval=None)
                    ram_percent = psutil.virtual_memory().percent
                    gpu_util, gpu_name_to_emit = -1.0, self._gpu_name_cache
                    
                    if self._nvml_initialized and self._gpu_handle and PYNVML_AVAILABLE and pynvml:
                        try: gpu_util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle).gpu
                        except pynvml.NVMLError as e_nvml_util:
                            logger.debug(f"NVML: Error getting GPU utilization: {e_nvml_util}")
                            gpu_util = -2.0 
                            error_code_str = f" (Code: {e_nvml_util.value})" if hasattr(e_nvml_util, 'value') else ""
                            gpu_name_to_emit = f"NVIDIA Util Err ({type(e_nvml_util).__name__}{error_code_str})"
                            if e_nvml_util.value in (pynvml.NVML_ERROR_GPU_IS_LOST, 
                                                     pynvml.NVML_ERROR_INVALID_ARGUMENT, 
                                                     pynvml.NVML_ERROR_UNINITIALIZED):
                                self._gpu_handle = None 
                                if e_nvml_util.value == pynvml.NVML_ERROR_UNINITIALIZED:
                                    self._nvml_initialized = False
                                logger.warning(f"NVML: GPU handle lost or error {e_nvml_util.value}. Attempting re-init/re-acquire on next cycle.")
                        except Exception as e_util_other: 
                            logger.debug(f"NVML: Unexpected error getting GPU utilization: {e_util_other}")
                            gpu_util = -2.0
                            gpu_name_to_emit = "NVML Util Error"
                    self.resourceUpdate.emit(cpu_usage, ram_percent, gpu_util, gpu_name_to_emit)
                except Exception as e:
                    logger.error(f"Error in resource monitoring data collection: {e}", exc_info=True)
                    self.resourceUpdate.emit(-1.0, -1.0, -3.0, f"Monitor Error: {str(e)[:20]}")
            
            QThread.msleep(short_sleep_ms) 
            current_cycle = (current_cycle + 1) % cycles_per_update
            
        logger.debug("Resource monitor worker loop finished.")


# MainWindow Class
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_file_path = None
        self.last_generated_model_path = None
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)

        self.ai_chatbot_manager = AIChatbotManager(self)
        
        self.scene = DiagramScene(self.undo_stack, self)

        self.scene.modifiedStatusChanged.connect(self.setWindowModified)
        self.scene.modifiedStatusChanged.connect(self._update_window_title)

        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False

        # --- IDE Dock Attributes ---
        self.ide_tab_widget: QTabWidget | None = None
        self.ide_run_script_action: QAction | None = None
        self.ide_close_tab_action: QAction | None = None 
        self.ide_find_action: QAction | None = None 
        self.ide_replace_action: QAction | None = None 
        self.ide_clear_console_action: QAction | None = None 
        self.ide_save_output_action: QAction | None = None 
        self.ide_analyze_action: QAction | None = None
        self._find_replace_dialog_instance: FindReplaceDialog | None = None 
        # --- CRITICAL ORDERING ---
        self.init_ui() 

        self.py_sim_ui_manager = PySimulationUIManager(self)
        self.ai_chat_ui_manager = AIChatUIManager(self)
        
        # NOW that UI managers are created, populate their dock contents
        self._populate_dynamic_docks()


        self.py_sim_ui_manager.simulationStateChanged.connect(self._handle_py_sim_state_changed_by_manager)
        self.py_sim_ui_manager.requestGlobalUIEnable.connect(self._handle_py_sim_global_ui_enable_by_manager)

        self._internet_connected: bool | None = None
        self.internet_check_timer = QTimer(self)
        
        self.resource_monitor_worker: ResourceMonitorWorker | None = None
        self.resource_monitor_thread: QThread | None = None

        try:
            setup_global_logging(self.log_output)
            logger.info("Main window initialized and logging configured.")
        except Exception as e:
            logger.error(f"Failed to run setup_global_logging: {e}. UI logs might not work.")
            if not logging.getLogger().hasHandlers():
                 logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

        self._init_resource_monitor()

        if hasattr(self, 'matlab_status_label'): self.matlab_status_label.setObjectName("MatlabStatusLabel")
        if hasattr(self, 'py_sim_status_label'): self.py_sim_status_label.setObjectName("PySimStatusLabel")
        if hasattr(self, 'internet_status_label'): self.internet_status_label.setObjectName("InternetStatusLabel")
        if hasattr(self, 'status_label'): self.status_label.setObjectName("StatusLabel")

        self._update_matlab_status_display(False, "Initializing. Configure MATLAB settings or attempt auto-detect.")
        self._update_py_sim_status_display()

        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)
        
        # self._update_window_title() # Called by on_new_file or _on_ide_current_tab_changed
        self.on_new_file(silent=True) # This will also trigger an IDE tab creation if needed.
        self._init_internet_status_check()
        self.scene.selectionChanged.connect(self._update_properties_dock)
        self._update_properties_dock()
        self._update_py_simulation_actions_enabled_state()
        self._update_ide_related_actions() # Init IDE actions enabled state

        if self.ai_chat_ui_manager: 
            if not self.ai_chatbot_manager.api_key:
                self.ai_chat_ui_manager.update_status_display("Status: API Key required. Configure in Settings.")
            else:
                self.ai_chat_ui_manager.update_status_display("Status: Ready.")
        else:
            logger.warning("MainWindow: ai_chat_ui_manager not initialized when trying to set initial status.")


    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050) 
        self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM")) 
        self._create_central_widget()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_docks() # This will create QDockWidget instances
        self._create_status_bar()
        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger() 

    def _populate_dynamic_docks(self):
        """Populates dock widgets whose content depends on UI managers."""
        if self.py_sim_ui_manager and self.py_sim_dock:
            py_sim_contents_widget = self.py_sim_ui_manager.create_dock_widget_contents()
            self.py_sim_dock.setWidget(py_sim_contents_widget)
        else:
            logger.error("Could not populate Python Simulation Dock: manager or dock missing.")

        if self.ai_chat_ui_manager and self.ai_chatbot_dock:
            ai_chat_contents_widget = self.ai_chat_ui_manager.create_dock_widget_contents()
            self.ai_chatbot_dock.setWidget(ai_chat_contents_widget)
        else:
            logger.error("Could not populate AI Chatbot Dock: manager or dock missing.")
        
        # Tabify after content is set
        self.tabifyDockWidget(self.properties_dock, self.ai_chatbot_dock)
        self.tabifyDockWidget(self.ai_chatbot_dock, self.py_sim_dock)
        if hasattr(self, 'ide_dock'): # If IDE dock exists
            self.tabifyDockWidget(self.py_sim_dock, self.ide_dock)


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
            "Save &As...", self, shortcut=QKeySequence.SaveAs,
            statusTip="Save the current file with a new name", triggered=self.on_save_file_as
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

        self.start_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Py▶"), "&Start Python Simulation", self, statusTip="Start internal FSM simulation")
        self.stop_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaStop, "Py■"), "S&top Python Simulation", self, statusTip="Stop internal FSM simulation", enabled=False)
        self.reset_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaSkipBackward, "Py«"), "&Reset Python Simulation", self, statusTip="Reset internal FSM simulation", enabled=False)

        self.openai_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "AISet"), "AI Assistant Settings...", self)
        self.clear_ai_chat_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "Clear"), "Clear Chat History", self)
        self.ask_ai_to_generate_fsm_action = QAction(
            get_standard_icon(QStyle.SP_ArrowRight, "AIGen"), 
            "Generate FSM from Description...", 
            self
        )

        self.open_example_menu_action = QAction("Open E&xample...", self) 
        self.quick_start_action = QAction(get_standard_icon(QStyle.SP_MessageBoxQuestion, "QS"), "&Quick Start Guide", self, triggered=self.on_show_quick_start)
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, triggered=self.on_about)
        
        # --- IDE Actions ---
        self.ide_new_file_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "IDENew"), "New Script", self, triggered=self.on_ide_new_file)
        self.ide_open_file_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "IDEOpn"), "Open Script...", self, triggered=self.on_ide_open_file)
        self.ide_save_file_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "IDESav"), "Save Script", self, triggered=self.on_ide_save_file)
        self.ide_save_as_file_action = QAction(get_standard_icon(_safe_get_style_enum("SP_DriveHDIcon", "SP_DialogSaveButton"), "IDESA"), "Save Script As...", self, triggered=self.on_ide_save_as_file)
        self.ide_close_tab_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "IDEClose"), "Close Script Tab", self, shortcut=QKeySequence.Close, triggered=self.on_ide_close_current_tab)
        self.ide_run_script_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "IDERunPy"), "Run Python Script", self, triggered=self.on_ide_run_python_script)
        self.ide_find_action = QAction(get_standard_icon(QStyle.SP_FileDialogContentsView, "IDEFind"), "Find in Script...", self, shortcut=QKeySequence.Find, triggered=self.on_ide_find)
        self.ide_replace_action = QAction(get_standard_icon(QStyle.SP_DialogApplyButton, "IDERepl"), "Replace in Script...", self, shortcut=QKeySequence.Replace, triggered=self.on_ide_replace)
        self.ide_clear_console_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "IDEClr"), "Clear Output Console", self, triggered=self.on_ide_clear_console)
        self.ide_save_output_action = QAction(get_standard_icon(QStyle.SP_DriveFDIcon, "IDESvOut"), "Save Output...", self, triggered=self.on_ide_save_output)
        self.ide_analyze_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "IDEAI"), "Analyze with AI", self, triggered=self.on_ide_analyze_with_ai)


        logger.debug(f"MW: AI actions created. Settings: {self.openai_settings_action}, Clear: {self.clear_ai_chat_action}, Generate: {self.ask_ai_to_generate_fsm_action}")


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

        tools_menu = menu_bar.addMenu("&Tools") # New Tools menu
        ide_menu = tools_menu.addMenu(get_standard_icon(QStyle.SP_FileDialogDetailedView, "IDE"), "Standalone IDE")
        ide_menu.addAction(self.ide_new_file_action)
        ide_menu.addAction(self.ide_open_file_action)
        ide_menu.addAction(self.ide_save_file_action)
        ide_menu.addAction(self.ide_save_as_file_action)
        ide_menu.addAction(self.ide_close_tab_action)
        ide_menu.addSeparator()
        ide_menu.addAction(self.ide_find_action)
        ide_menu.addAction(self.ide_replace_action)
        ide_menu.addSeparator()
        ide_menu.addAction(self.ide_run_script_action)
        ide_menu.addAction(self.ide_analyze_action)
        ide_menu.addSeparator()
        ide_menu.addAction(self.ide_clear_console_action)
        ide_menu.addAction(self.ide_save_output_action)


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

        # Tools Dock (Content created directly)
        self.tools_dock = QDockWidget("Tools", self)
        self.tools_dock.setObjectName("ToolsDock")
        self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_widget_main = QWidget()
        tools_widget_main.setObjectName("ToolsDockWidgetContents")
        tools_main_layout = QVBoxLayout(tools_widget_main)
        tools_main_layout.setSpacing(10); tools_main_layout.setContentsMargins(5,5,5,5)
        mode_group_box = QGroupBox("Interaction Modes")
        mode_layout = QVBoxLayout(); mode_layout.setSpacing(5)
        self.toolbox_select_button = QToolButton(); self.toolbox_select_button.setDefaultAction(self.select_mode_action)
        self.toolbox_add_state_button = QToolButton(); self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action)
        self.toolbox_transition_button = QToolButton(); self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action)
        self.toolbox_add_comment_button = QToolButton(); self.toolbox_add_comment_button.setDefaultAction(self.add_comment_mode_action)
        for btn in [self.toolbox_select_button, self.toolbox_add_state_button, self.toolbox_transition_button, self.toolbox_add_comment_button]:
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(18,18)); mode_layout.addWidget(btn)
        mode_group_box.setLayout(mode_layout); tools_main_layout.addWidget(mode_group_box)
        draggable_group_box = QGroupBox("Drag New Elements")
        draggable_layout = QVBoxLayout(); draggable_layout.setSpacing(5)
        drag_state_btn = DraggableToolButton(" State", "application/x-bsm-tool", "State")
        drag_state_btn.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))
        drag_initial_state_btn = DraggableToolButton(" Initial State", "application/x-bsm-tool", "Initial State")
        drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt"))
        drag_final_state_btn = DraggableToolButton(" Final State", "application/x-bsm-tool", "Final State")
        drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt"))
        drag_comment_btn = DraggableToolButton(" Comment", "application/x-bsm-tool", "Comment")
        drag_comment_btn.setIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))
        for btn in [drag_state_btn, drag_initial_state_btn, drag_final_state_btn, drag_comment_btn]:
            btn.setIconSize(QSize(18,18)); draggable_layout.addWidget(btn)
        draggable_group_box.setLayout(draggable_layout); tools_main_layout.addWidget(draggable_group_box)
        tools_main_layout.addStretch()
        self.tools_dock.setWidget(tools_widget_main)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.tools_dock.toggleViewAction())

        # Properties Dock (Content created directly)
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        properties_widget = QWidget()
        properties_layout = QVBoxLayout(properties_widget)
        properties_layout.setContentsMargins(5,5,5,5); properties_layout.setSpacing(5)
        self.properties_editor_label = QLabel("<i>No item selected.</i><br><small>Click an item to view/edit.</small>")
        self.properties_editor_label.setWordWrap(True); self.properties_editor_label.setTextFormat(Qt.RichText)
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

        # Log Dock (Content created directly)
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(5,5,5,5)
        self.log_output = QTextEdit()
        self.log_output.setObjectName("LogOutputWidget")
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)
        self.log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.log_dock.toggleViewAction())

        # Python Simulation Dock (QDockWidget instance created, content set later)
        self.py_sim_dock = QDockWidget("Python Simulation", self)
        self.py_sim_dock.setObjectName("PySimDock")
        self.py_sim_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.py_sim_dock.toggleViewAction())

        # AI Chatbot Dock (QDockWidget instance created, content set later)
        self.ai_chatbot_dock = QDockWidget("AI Chatbot", self)
        self.ai_chatbot_dock.setObjectName("AIChatbotDock")
        self.ai_chatbot_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.ai_chatbot_dock.toggleViewAction())

        # --- Standalone IDE Dock ---
        self._setup_ide_dock_widget()

        # Tabify docks: This should ideally happen AFTER their content widgets are set.
        # Moved to _populate_dynamic_docks.

    def _setup_ide_dock_widget(self):
        self.ide_dock = QDockWidget("Standalone Code IDE", self)
        self.ide_dock.setObjectName("IDEDock")
        self.ide_dock.setAllowedAreas(Qt.AllDockWidgetAreas) # Allow flexible placement

        ide_main_widget = QWidget()
        ide_main_layout = QVBoxLayout(ide_main_widget)
        ide_main_layout.setContentsMargins(0,0,0,0) # Toolbar will have its own margins
        ide_main_layout.setSpacing(0)

        # Toolbar for IDE
        ide_toolbar = QToolBar("IDE Tools")
        ide_toolbar.setIconSize(QSize(18,18))
        ide_toolbar.addAction(self.ide_new_file_action)
        ide_toolbar.addAction(self.ide_open_file_action)
        ide_toolbar.addAction(self.ide_save_file_action)
        ide_toolbar.addAction(self.ide_save_as_file_action)
        ide_toolbar.addAction(self.ide_close_tab_action)
        ide_toolbar.addSeparator()
        ide_toolbar.addAction(self.ide_find_action)
        ide_toolbar.addAction(self.ide_replace_action)
        ide_toolbar.addSeparator()
        ide_toolbar.addAction(self.ide_clear_console_action)
        ide_toolbar.addAction(self.ide_save_output_action)
        ide_toolbar.addSeparator()
        ide_toolbar.addAction(self.ide_run_script_action) 
        ide_toolbar.addSeparator()
        self.ide_language_combo = QComboBox()
        self.ide_language_combo.addItems(["Python", "C/C++ (Arduino)", "C/C++ (Generic)", "Text"])
        self.ide_language_combo.setToolTip("Select language (syntax highlighting for Python only currently)")
        self.ide_language_combo.currentTextChanged.connect(self._on_ide_language_changed)
        ide_toolbar.addWidget(QLabel(" Language: "))
        ide_toolbar.addWidget(self.ide_language_combo)
        ide_toolbar.addSeparator()
        ide_toolbar.addAction(self.ide_analyze_action)


        ide_main_layout.addWidget(ide_toolbar)

        self.ide_tab_widget = QTabWidget()
        self.ide_tab_widget.setTabsClosable(True)
        self.ide_tab_widget.tabCloseRequested.connect(self._on_ide_tab_close_requested)
        self.ide_tab_widget.currentChanged.connect(self._on_ide_current_tab_changed)
        ide_main_layout.addWidget(self.ide_tab_widget, 1)


        self.ide_dock.setWidget(ide_main_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ide_dock) # Add to right by default
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.ide_dock.toggleViewAction())
        
        # _on_ide_language_changed will be called by _add_ide_tab via _on_ide_current_tab_changed
        if self.ide_tab_widget.count() == 0: # Ensure at least one tab exists initially
             self._add_ide_tab(title="Untitled 1")


    def _create_status_bar(self): 
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1) 

        self.cpu_status_label = QLabel("CPU: --%"); self.cpu_status_label.setToolTip("CPU Usage"); self.cpu_status_label.setMinimumWidth(90); self.cpu_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.cpu_status_label)
        self.ram_status_label = QLabel("RAM: --%"); self.ram_status_label.setToolTip("RAM Usage"); self.ram_status_label.setMinimumWidth(90); self.ram_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.ram_status_label)
        self.gpu_status_label = QLabel("GPU: N/A"); self.gpu_status_label.setToolTip("GPU Usage (NVIDIA only, if pynvml installed)"); self.gpu_status_label.setMinimumWidth(130); self.gpu_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.gpu_status_label)

        self.py_sim_status_label = QLabel("PySim: Idle"); self.py_sim_status_label.setToolTip("Internal Python FSM Simulation Status."); self.py_sim_status_label.setMinimumWidth(100); self.py_sim_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.py_sim_status_label)
        self.matlab_status_label = QLabel("MATLAB: Initializing..."); self.matlab_status_label.setToolTip("MATLAB connection status."); self.matlab_status_label.setMinimumWidth(150); self.matlab_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.matlab_status_label)
        self.internet_status_label = QLabel("Internet: Init..."); self.internet_status_label.setToolTip("Internet connectivity. Checks periodically."); self.internet_status_label.setMinimumWidth(120); self.internet_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.internet_status_label)

        self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0,0); self.progress_bar.setVisible(False); self.progress_bar.setMaximumWidth(150); self.progress_bar.setTextVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self._update_ide_save_actions_enable_state() # Init IDE save actions

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
        if hasattr(self, 'cpu_status_label'): self.cpu_status_label.setText(f"CPU: {cpu_usage:.1f}%")
        if hasattr(self, 'ram_status_label'): self.ram_status_label.setText(f"RAM: {ram_usage:.1f}%")
        if hasattr(self, 'gpu_status_label'):
            if gpu_util == -1.0: self.gpu_status_label.setText(f"GPU: {gpu_name}") 
            elif gpu_util == -2.0: self.gpu_status_label.setText(f"GPU: {gpu_name}") 
            elif gpu_util == -3.0: self.gpu_status_label.setText(f"GPU: {gpu_name}") # Monitor error
            else: self.gpu_status_label.setText(f"GPU: {gpu_util:.0f}% ({gpu_name})")
    
    @pyqtSlot(bool)
    def _handle_py_sim_state_changed_by_manager(self, is_running: bool): 
        logger.debug(f"MW: PySim state changed by manager to: {is_running}")
        self.py_sim_active = is_running 
        self._update_window_title()
        self._update_py_sim_status_display() 
        self._update_matlab_actions_enabled_state() 
        self._update_py_simulation_actions_enabled_state() 

    @pyqtSlot(bool)
    def _handle_py_sim_global_ui_enable_by_manager(self, enable: bool): 
        logger.debug(f"MW: Global UI enable requested by PySim manager: {enable}")
        is_editable = enable 

        diagram_editing_actions = [
            self.new_action, self.open_action, self.save_action, self.save_as_action,
            self.undo_action, self.redo_action, self.delete_action, self.select_all_action,
            self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action
        ]
        for action in diagram_editing_actions:
            if hasattr(action, 'setEnabled'): action.setEnabled(is_editable)

        if hasattr(self, 'tools_dock'): self.tools_dock.setEnabled(is_editable)
        if hasattr(self, 'properties_edit_button'):
             self.properties_edit_button.setEnabled(is_editable and len(self.scene.selectedItems())==1)
        
        for item in self.scene.items(): 
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): 
                item.setFlag(QGraphicsItem.ItemIsMovable, is_editable and self.scene.current_mode == "select")
        
        if not is_editable and self.scene.current_mode != "select":
            self.scene.set_mode("select") 
        
        self._update_matlab_actions_enabled_state() 
        self._update_py_simulation_actions_enabled_state() 


    def _add_fsm_data_to_scene(self, fsm_data: dict, clear_current_diagram: bool = False, original_user_prompt: str = "AI Generated FSM"): 
        logger.info("MW: ADD_FSM_TO_SCENE clear_current_diagram=%s", clear_current_diagram)
        logger.debug("MW: Received FSM Data (states: %d, transitions: %d)",
                     len(fsm_data.get('states',[])), len(fsm_data.get('transitions',[])))

        if clear_current_diagram:
            if not self.on_new_file(silent=True): 
                 logger.warning("MW: Clearing diagram cancelled by user (save prompt). Cannot add AI FSM.")
                 return 
            logger.info("MW: Cleared diagram before AI generation.")

        if not clear_current_diagram:
            self.undo_stack.beginMacro(f"Add AI FSM: {original_user_prompt[:30]}...")

        state_items_map = {} 
        items_to_add_for_undo_command = [] 

        layout_start_x, layout_start_y = 100, 100
        default_item_width, default_item_height = 120, 60
        GV_SCALE = 1.2 

        G = pgv.AGraph(directed=True, strict=False, rankdir='TB', ratio='auto', nodesep='0.75', ranksep='1.2 equally')
        for state_data in fsm_data.get('states', []):
            name = state_data.get('name')
            if name: G.add_node(name, label=name, width=str(default_item_width/72.0), height=str(default_item_height/72.0), shape='box', style='rounded')
        for trans_data in fsm_data.get('transitions', []):
            source, target = trans_data.get('source'), trans_data.get('target')
            if source and target and G.has_node(source) and G.has_node(target): G.add_edge(source, target, label=trans_data.get('event', ''))
            else: logger.warning("MW: Skipping Graphviz edge for AI FSM due to missing node(s): %s->%s", source, target)

        graphviz_positions = {}
        try:
            G.layout(prog="dot"); logger.debug("MW: Graphviz layout ('dot') for AI FSM successful.")
            raw_gv_pos = [{'name': n.name, 'x': float(n.attr['pos'].split(',')[0]), 'y': float(n.attr['pos'].split(',')[1])} for n in G.nodes() if 'pos' in n.attr]
            if raw_gv_pos:
                min_x_gv = min(p['x'] for p in raw_gv_pos); max_y_gv = max(p['y'] for p in raw_gv_pos) 
                for p_gv in raw_gv_pos: graphviz_positions[p_gv['name']] = QPointF((p_gv['x'] - min_x_gv) * GV_SCALE + layout_start_x, (max_y_gv - p_gv['y']) * GV_SCALE + layout_start_y)
            else: logger.warning("MW: Graphviz - No valid positions extracted for AI FSM nodes.")
        except Exception as e:
            logger.error("MW: Graphviz layout error for AI FSM: %s. Falling back to grid.", str(e).strip() or "Unknown", exc_info=True)
            if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager: 
                self.ai_chat_ui_manager._append_to_chat_display("System", f"Warning: AI FSM layout failed (Graphviz error). Using basic grid layout.")
            graphviz_positions = {} 

        for i, state_data in enumerate(fsm_data.get('states', [])):
            name = state_data.get('name'); item_w, item_h = default_item_width, default_item_height
            if not name: logger.warning("MW: AI State data missing 'name'. Skipping."); continue
            pos = graphviz_positions.get(name)
            pos_x, pos_y = (pos.x(), pos.y()) if pos else (layout_start_x + (i % 3) * (item_w + 150), layout_start_y + (i // 3) * (item_h + 100)) 
            try:
                state_item = GraphicsStateItem(pos_x, pos_y, item_w, item_h, name,
                    is_initial=state_data.get('is_initial', False), is_final=state_data.get('is_final', False),
                    color=state_data.get('properties', {}).get('color', state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG)),
                    entry_action=state_data.get('entry_action', ""), during_action=state_data.get('during_action', ""), exit_action=state_data.get('exit_action', ""),
                    description=state_data.get('description', fsm_data.get('description', "") if i==0 else ""), 
                    is_superstate=state_data.get('is_superstate', False), sub_fsm_data=state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}))
                items_to_add_for_undo_command.append(state_item); state_items_map[name] = state_item
            except Exception as e: logger.error("MW: Error creating AI GraphicsStateItem '%s': %s", name, e, exc_info=True)

        for trans_data in fsm_data.get('transitions', []):
            src_name, tgt_name = trans_data.get('source'), trans_data.get('target')
            if not src_name or not tgt_name: logger.warning("MW: AI Transition missing source/target. Skipping."); continue
            src_item, tgt_item = state_items_map.get(src_name), state_items_map.get(tgt_name)
            if src_item and tgt_item:
                try:
                    trans_item = GraphicsTransitionItem(src_item, tgt_item,
                        event_str=trans_data.get('event', ""), condition_str=trans_data.get('condition', ""), action_str=trans_data.get('action', ""),
                        color=trans_data.get('properties', {}).get('color', trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT)), description=trans_data.get('description', ""))
                    ox, oy = trans_data.get('control_offset_x'), trans_data.get('control_offset_y')
                    if ox is not None and oy is not None:
                        try: trans_item.set_control_point_offset(QPointF(float(ox), float(oy)))
                        except ValueError: logger.warning("MW: Invalid AI control offsets for transition %s->%s.", src_name, tgt_name)
                    items_to_add_for_undo_command.append(trans_item)
                except Exception as e: logger.error("MW: Error creating AI GraphicsTransitionItem %s->%s: %s", src_name, tgt_name, e, exc_info=True)
            else: logger.warning("MW: Could not find source/target GraphicsStateItem for AI transition: %s->%s. Skipping.", src_name, tgt_name)
        
        max_y_items = max((item.scenePos().y() + item.boundingRect().height() for item in state_items_map.values() if item.scenePos()), default=layout_start_y) if state_items_map else layout_start_y
        for i, comment_data in enumerate(fsm_data.get('comments', [])):
            text = comment_data.get('text'); width = comment_data.get('width')
            if not text: continue
            pos_x = comment_data.get('x', layout_start_x + i * (150 + 20)) 
            pos_y = comment_data.get('y', max_y_items + 100) 
            try:
                comment_item = GraphicsCommentItem(pos_x, pos_y, text)
                if width:
                    try: comment_item.setTextWidth(float(width))
                    except ValueError: logger.warning("MW: Invalid AI width for comment.")
                items_to_add_for_undo_command.append(comment_item)
            except Exception as e: logger.error("MW: Error creating AI GraphicsCommentItem: %s", e, exc_info=True)


        if items_to_add_for_undo_command:
            if not clear_current_diagram:
                for item_to_add in items_to_add_for_undo_command:
                    item_type_name = type(item_to_add).__name__.replace("Graphics","").replace("Item","")
                    cmd_text = f"Add AI {item_type_name}" + (f": {item_to_add.text_label}" if hasattr(item_to_add, 'text_label') and item_to_add.text_label else "")
                    self.undo_stack.push(AddItemCommand(self.scene, item_to_add, cmd_text))
            else: 
                for item_to_add in items_to_add_for_undo_command:
                     self.scene.addItem(item_to_add)

            logger.info("MW: Added %d AI-generated items to diagram.", len(items_to_add_for_undo_command))
            self.scene.set_dirty(True) 
            QTimer.singleShot(100, self._fit_view_to_new_ai_items)
        else:
            logger.info("MW: No valid AI-generated items to add.")

        if not clear_current_diagram and items_to_add_for_undo_command: 
            self.undo_stack.endMacro()
        elif not clear_current_diagram: 
             self.undo_stack.endMacro() 

        if self.py_sim_active and items_to_add_for_undo_command: 
            logger.info("MW: Reinitializing Python simulation after adding AI FSM.")
            try:
                if self.py_sim_ui_manager:
                    self.py_sim_ui_manager.on_stop_py_simulation(silent=True) 
                    self.py_sim_ui_manager.on_start_py_simulation() 
                    self.py_sim_ui_manager.append_to_action_log(["Python FSM Simulation reinitialized for new diagram from AI."])
            except FSMError as e:
                if self.py_sim_ui_manager:
                    self.py_sim_ui_manager.append_to_action_log([f"ERROR Re-initializing Sim after AI: {e}"])
                    self.py_sim_ui_manager.on_stop_py_simulation(silent=True) 
        logger.debug("MW: ADD_FSM_TO_SCENE processing finished. Items involved: %d", len(items_to_add_for_undo_command))


    def _fit_view_to_new_ai_items(self): 
        if not self.scene.items(): return
        items_bounds = self.scene.itemsBoundingRect()
        if self.view and not items_bounds.isNull():
            self.view.fitInView(items_bounds.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)
            logger.info("MW: View adjusted to AI generated items.")
        elif self.view and self.scene.sceneRect(): 
            self.view.centerOn(self.scene.sceneRect().center())


    def on_matlab_settings(self): 
        dialog = MatlabSettingsDialog(matlab_connection=self.matlab_connection, parent=self)
        dialog.exec() 
        logger.info("MATLAB settings dialog closed.")


    def _update_properties_dock(self): 
        selected_items = self.scene.selectedItems()
        html_content = ""
        edit_enabled = False
        item_type_tooltip = "item"

        if len(selected_items) == 1:
            item = selected_items[0]
            props = item.get_data() if hasattr(item, 'get_data') else {}
            item_type_name = type(item).__name__.replace("Graphics", "").replace("Item", "")
            item_type_tooltip = item_type_name.lower()
            edit_enabled = True

            def fmt(txt, max_chars=25):
                if not txt: return "<i>(none)</i>"
                txt_str = str(txt)
                first_line = txt_str.split('\n')[0]
                escaped_first_line = html.escape(first_line)
                ellipsis = "…" if len(first_line) > max_chars or '\n' in txt_str else ""
                return escaped_first_line[:max_chars] + ellipsis

            rows = ""
            if isinstance(item, GraphicsStateItem):
                color_obj = QColor(props.get('color', COLOR_ITEM_STATE_DEFAULT_BG))
                color_style = f"background-color:{color_obj.name()}; color:{'black' if color_obj.lightnessF()>0.5 else 'white'}; padding:1px 4px; border-radius:2px;"
                rows += f"<tr><td><b>Name:</b></td><td>{html.escape(props.get('name', 'N/A'))}</td></tr>"
                rows += f"<tr><td><b>Initial/Final:</b></td><td>{'Yes' if props.get('is_initial') else 'No'} / {'Yes' if props.get('is_final') else 'No'}</td></tr>"
                if props.get('is_superstate'):
                    sub_states_count = len(props.get('sub_fsm_data',{}).get('states',[]))
                    rows += f"<tr><td><b>Superstate:</b></td><td>Yes ({sub_states_count} sub-state{'s' if sub_states_count != 1 else ''})</td></tr>"

                rows += f"<tr><td><b>Color:</b></td><td><span style='{color_style}'>{html.escape(color_obj.name())}</span></td></tr>"
                for act_key in ['entry_action', 'during_action', 'exit_action']:
                    act_label = act_key.replace('_action','').capitalize()
                    rows += f"<tr><td><b>{act_label}:</b></td><td>{fmt(props.get(act_key, ''))}</td></tr>"
                if props.get('description'): rows += f"<tr><td colspan='2'><b>Desc:</b> {fmt(props.get('description'), 50)}</td></tr>"

            elif isinstance(item, GraphicsTransitionItem):
                color_obj = QColor(props.get('color', COLOR_ITEM_TRANSITION_DEFAULT))
                color_style = f"background-color:{color_obj.name()}; color:{'black' if color_obj.lightnessF()>0.5 else 'white'}; padding:1px 4px; border-radius:2px;"
                
                label_parts = []
                if props.get('event'): label_parts.append(html.escape(props.get('event')))
                if props.get('condition'): label_parts.append(f"[{html.escape(props.get('condition'))}]")
                if props.get('action'): label_parts.append(f"/{{{fmt(props.get('action'),15)}}}")
                full_label = " ".join(p for p in label_parts if p) or "<i>(No Label)</i>"

                rows += f"<tr><td><b>Label:</b></td><td style='font-size:8pt;'>{full_label}</td></tr>"
                rows += f"<tr><td><b>From/To:</b></td><td>{html.escape(props.get('source','N/A'))} → {html.escape(props.get('target','N/A'))}</td></tr>"
                rows += f"<tr><td><b>Color:</b></td><td><span style='{color_style}'>{html.escape(color_obj.name())}</span></td></tr>"
                rows += f"<tr><td><b>Curve:</b></td><td>Bend={props.get('control_offset_x',0):.0f}, Shift={props.get('control_offset_y',0):.0f}</td></tr>"
                if props.get('description'): rows += f"<tr><td colspan='2'><b>Desc:</b> {fmt(props.get('description'), 50)}</td></tr>"

            elif isinstance(item, GraphicsCommentItem):
                rows += f"<tr><td colspan='2'><b>Text:</b> {fmt(props.get('text', ''), 60)}</td></tr>"
            else:
                rows = "<tr><td>Unknown Item Type</td></tr>"
                item_type_name = "Unknown" 
            
            html_content = f"""
                <div style='font-family:"Segoe UI",Arial;font-size:9pt;line-height:1.5;'>
                    <h4 style='margin:0 0 5px 0;padding:2px 0;color:{COLOR_ACCENT_PRIMARY};border-bottom:1px solid {COLOR_BORDER_LIGHT};'>
                        Type: {item_type_name}
                    </h4>
                    <table style='width:100%;border-collapse:collapse;'>{rows}</table>
                </div>"""
        elif len(selected_items) > 1:
            html_content = f"<i><b>{len(selected_items)} items selected.</b><br>Select a single item to view or edit its properties.</i>"
            item_type_tooltip = f"{len(selected_items)} items"
        else: 
            html_content = "<i>No item selected.</i><br><small>Click an item in the diagram or use the tools to add new elements.</small>"

        self.properties_editor_label.setText(html_content)
        self.properties_edit_button.setEnabled(edit_enabled)
        self.properties_edit_button.setToolTip(f"Edit properties of selected {item_type_tooltip}" if edit_enabled else "Select a single item to enable editing")


    def _on_edit_selected_item_properties_from_dock(self): 
        selected = self.scene.selectedItems()
        if len(selected) == 1:
            self.scene.edit_item_properties(selected[0])

    def _update_window_title(self): 
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        
        ide_suffix = ""
        active_ide_tab_widget = self._get_active_ide_tab_data() 
        if active_ide_tab_widget and active_ide_tab_widget.get("path"):
            ide_file_name = os.path.basename(active_ide_tab_widget["path"])
            ide_dirty_char = "*" if active_ide_tab_widget.get("is_dirty", False) else ""
            ide_suffix = f" | IDE: {ide_file_name}{ide_dirty_char}"
        elif self.ide_tab_widget and self.ide_tab_widget.count() > 0: 
             active_tab_index = self.ide_tab_widget.currentIndex()
             if active_tab_index != -1 : 
                 active_tab_title = self.ide_tab_widget.tabText(active_tab_index) 
                 active_tab_data = self._get_active_ide_tab_data() 
                 ide_dirty_char = "*" if active_tab_data and active_tab_data.get("is_dirty", False) else ""
                 ide_suffix = f" | IDE: {active_tab_title.replace('*','')}{ide_dirty_char}"


        sim_status_suffix = " [PySim Running]" if self.py_sim_active else ""
        title = f"{APP_NAME} - {file_name}{sim_status_suffix}{ide_suffix}"
        self.setWindowTitle(title + "[*]") 
        if hasattr(self, 'status_label'): 
            self.status_label.setText(f"File: {file_name}{' *' if self.isWindowModified() else ''} | PySim: {'Active' if self.py_sim_active else 'Idle'}")

    def _update_save_actions_enable_state(self): 
        self.save_action.setEnabled(self.isWindowModified())

    def _update_ide_save_actions_enable_state(self):
        active_tab_data = self._get_active_ide_tab_data()
        is_dirty = active_tab_data.get("is_dirty", False) if active_tab_data else False
        has_content = active_tab_data and active_tab_data.get("editor") is not None and \
                      bool(active_tab_data["editor"].toPlainText())

        if hasattr(self, 'ide_save_file_action'):
            self.ide_save_file_action.setEnabled(is_dirty)
        if hasattr(self, 'ide_save_as_file_action'):
             self.ide_save_as_file_action.setEnabled(has_content)


    def _update_undo_redo_actions_enable_state(self): 
        self.undo_action.setEnabled(self.undo_stack.canUndo())
        self.redo_action.setEnabled(self.undo_stack.canRedo())
        self.undo_action.setText(f"&Undo {self.undo_stack.undoText()}" if self.undo_stack.undoText() else "&Undo")
        self.redo_action.setText(f"&Redo {self.undo_stack.redoText()}" if self.undo_stack.redoText() else "&Redo")

    def _update_matlab_status_display(self, connected, message): 
        text_color = COLOR_PY_SIM_STATE_ACTIVE.name() if connected else "#C62828" 
        status_text = f"MATLAB: {'Connected' if connected else 'Not Connected'}"
        tooltip_text = f"MATLAB Status: {message}"

        if hasattr(self, 'matlab_status_label'):
            self.matlab_status_label.setText(status_text)
            self.matlab_status_label.setToolTip(tooltip_text)
            self.matlab_status_label.setStyleSheet(f"font-weight:bold;padding:0 5px;color:{text_color};")
        
        if "Initializing" not in message or (connected and "Initializing" in message): 
            logging.info("MATLAB Connection Status: %s", message)
        
        self._update_matlab_actions_enabled_state()


    def _update_matlab_actions_enabled_state(self): 
        can_run_matlab_ops = self.matlab_connection.connected and not self.py_sim_active
        
        if hasattr(self, 'export_simulink_action'): self.export_simulink_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'run_simulation_action'): self.run_simulation_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'generate_code_action'): self.generate_code_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'matlab_settings_action'): self.matlab_settings_action.setEnabled(not self.py_sim_active)

    def _start_matlab_operation(self, operation_name): 
        logging.info("MATLAB Operation: '%s' starting...", operation_name)
        if hasattr(self, 'status_label'): self.status_label.setText(f"Running MATLAB: {operation_name}...")
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False)

    def _finish_matlab_operation(self): 
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(False)
        if hasattr(self, 'status_label'): self.status_label.setText("Ready") 
        self.set_ui_enabled_for_matlab_op(True)
        logging.info("MATLAB Operation: Finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool): 
        if hasattr(self, 'menuBar'): self.menuBar().setEnabled(enabled)
        for child in self.findChildren(QToolBar): 
            child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled) 
        
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock", "IDEDock"]:
            dock = self.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(enabled) 
        
        self._update_py_simulation_actions_enabled_state() 


    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data): 
        self._finish_matlab_operation() 
        logging.log(logging.INFO if success else logging.ERROR, "MATLAB Result (ModelGen/Sim): %s", message)
        if success:
            if "Model generation" in message and data: 
                self.last_generated_model_path = data
                QMessageBox.information(self, "Simulink Model Generation", f"Model generated successfully:\n{data}")
            elif "Simulation" in message: 
                QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else:
            QMessageBox.warning(self, "MATLAB Operation Failed", message)

    def _handle_matlab_codegen_finished(self, success, message, output_dir): 
        self._finish_matlab_operation() 
        logging.log(logging.INFO if success else logging.ERROR, "MATLAB Code Gen Result: %s", message)
        if success and output_dir:
            msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Information); msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText); abs_dir = os.path.abspath(output_dir)
            msg_box.setText(f"Code generation completed successfully.<br>Generated files are in: <a href='file:///{abs_dir}'>{abs_dir}</a>")
            msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction) 
            open_btn = msg_box.addButton("Open Directory", QMessageBox.ActionRole); msg_box.addButton(QMessageBox.Ok)
            msg_box.exec()
            if msg_box.clickedButton() == open_btn:
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(abs_dir)):
                    logging.error("Error opening directory: %s", abs_dir)
                    QMessageBox.warning(self, "Error Opening Directory", f"Could not automatically open the directory:\n{abs_dir}")
        elif not success:
            QMessageBox.warning(self, "Code Generation Failed", message)

    def _prompt_save_if_dirty(self) -> bool: 
        if not self.isWindowModified():
            return True
        if self.py_sim_active: 
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving or opening a new file.")
            return False

        file_desc = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes?",
                                     f"The diagram '{file_desc}' has unsaved changes. Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save) 

        if reply == QMessageBox.Save:
            return self.on_save_file() 
        elif reply == QMessageBox.Cancel:
            return False
        return True 

    def on_new_file(self, silent=False): 
        if not silent and not self._prompt_save_if_dirty():
            return False 
        
        if self.py_sim_ui_manager: 
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True) 
        
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
            logging.info("New diagram created.")
            if hasattr(self, 'status_label'): self.status_label.setText("New diagram. Ready.")
        self.view.resetTransform() 
        self.view.centerOn(self.scene.sceneRect().center())
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger() 
        return True


    def on_open_file(self): 
        if not self._prompt_save_if_dirty():
            return 
        if self.py_sim_ui_manager: 
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)

        if file_path:
            if self._load_from_path(file_path):
                self.current_file_path = file_path
                self.last_generated_model_path = None 
                self.undo_stack.clear() 
                self.scene.set_dirty(False)
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                logging.info("Opened file: %s", file_path)
                if hasattr(self, 'status_label'): self.status_label.setText(f"Opened: {os.path.basename(file_path)}")
                bounds = self.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else: 
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())

            else:
                QMessageBox.critical(self, "Error Opening File", f"Could not load the diagram from:\n{file_path}")
                logging.error("Failed to open file: %s", file_path)

    def _load_from_path(self, file_path): 
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data:
                logging.error("Invalid BSM file format: %s. Missing required keys.", file_path)
                return False
            self.scene.load_diagram_data(data) 
            return True
        except json.JSONDecodeError as e:
            logging.error("JSONDecodeError loading %s: %s", file_path, e)
            return False
        except Exception as e:
            logging.error("Unexpected error loading %s: %s", file_path, e, exc_info=True)
            return False

    def on_save_file(self) -> bool: 
        if not self.current_file_path: 
            return self.on_save_file_as()
        return self._save_to_path(self.current_file_path)

    def on_save_file_as(self) -> bool: 
        default_filename = os.path.basename(self.current_file_path) if self.current_file_path else "untitled" + FILE_EXTENSION
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As",
                                                   os.path.join(start_dir, default_filename),
                                                   FILE_FILTER)
        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION
            
            if self._save_to_path(file_path):
                self.current_file_path = file_path 
                return True
        return False

    def _save_to_path(self, file_path) -> bool: 
        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving.")
            return False
            
        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            error_str = save_file.errorString()
            logging.error("Failed to open QSaveFile for %s: %s", file_path, error_str)
            QMessageBox.critical(self, "Save Error", f"Could not open file for saving:\n{error_str}")
            return False
        
        try:
            diagram_data = self.scene.get_diagram_data()
            json_data_str = json.dumps(diagram_data, indent=4, ensure_ascii=False)
            bytes_written = save_file.write(json_data_str.encode('utf-8'))
            
            if bytes_written == -1: 
                 error_str = save_file.errorString()
                 logging.error("Error writing to QSaveFile %s: %s", file_path, error_str)
                 QMessageBox.critical(self, "Save Error", f"Could not write data to file:\n{error_str}")
                 save_file.cancelWriting() 
                 return False

            if not save_file.commit(): 
                error_str = save_file.errorString()
                logging.error("Failed to commit QSaveFile for %s: %s", file_path, error_str)
                QMessageBox.critical(self, "Save Error", f"Could not finalize saving file:\n{error_str}")
                return False

            logging.info("Successfully saved diagram to: %s", file_path)
            if hasattr(self, 'status_label'): self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            self.scene.set_dirty(False)
            self.setWindowModified(False) 
            self._update_window_title() 
            return True
        except Exception as e: 
            logging.error("Unexpected error during save to %s: %s", file_path, e, exc_info=True)
            QMessageBox.critical(self, "Save Error", f"An unexpected error occurred during saving:\n{e}")
            save_file.cancelWriting() 
            return False

    def on_select_all(self): 
        self.scene.select_all()

    def on_delete_selected(self): 
        self.scene.delete_selected_items() 

    def on_export_simulink(self): 
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "Please configure MATLAB path in Settings first.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before exporting to Simulink.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Export to Simulink")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp, "->M")) 
        layout = QFormLayout(dialog)
        layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)

        base_name = os.path.splitext(os.path.basename(self.current_file_path or "BSM_Model"))[0]
        default_model_name = "".join(c if c.isalnum() or c=='_' else '_' for c in base_name) 
        if not default_model_name or not default_model_name[0].isalpha(): 
            default_model_name = "Mdl_" + default_model_name if default_model_name else "Mdl_MyStateMachine"
        default_model_name = default_model_name.replace('-','_') 

        name_edit = QLineEdit(default_model_name)
        layout.addRow("Simulink Model Name:", name_edit)

        default_output_dir = os.path.dirname(self.current_file_path or QDir.homePath())
        output_dir_edit = QLineEdit(default_output_dir)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw")," Browse...")
        browse_btn.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(output_dir_edit, 1); dir_layout.addWidget(browse_btn)
        layout.addRow("Output Directory:", dir_layout)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        dialog.setMinimumWidth(450)

        if dialog.exec() == QDialog.Accepted:
            model_name = name_edit.text().strip()
            output_dir = output_dir_edit.text().strip()
            if not model_name or not output_dir:
                QMessageBox.warning(self, "Input Error", "Model name and output directory are required.")
                return
            if not model_name[0].isalpha() or not all(c.isalnum() or c=='_' for c in model_name):
                QMessageBox.warning(self, "Invalid Model Name", "Simulink model name must start with a letter and contain only alphanumeric characters or underscores.")
                return
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create output directory:\n{e}")
                return

            diagram_data = self.scene.get_diagram_data()
            if not diagram_data['states']:
                QMessageBox.information(self, "Empty Diagram", "Cannot export an empty diagram (no states defined).")
                return

            self._start_matlab_operation(f"Exporting '{model_name}' to Simulink")
            self.matlab_connection.generate_simulink_model(diagram_data['states'], diagram_data['transitions'], output_dir, model_name)


    def on_run_simulation(self): 
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "Please configure MATLAB path in Settings.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before running a MATLAB simulation.")
            return

        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model to Simulate", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path 
        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Enter simulation stop time (seconds):", 10.0, 0.001, 86400.0, 3)
        if not ok: return

        self._start_matlab_operation(f"Running Simulink simulation for '{os.path.basename(model_path)}'")
        self.matlab_connection.run_simulation(model_path, sim_time)

    def on_generate_code(self): 
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "Please configure MATLAB path in Settings.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before generating code.")
            return

        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model for Code Generation", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path

        dialog = QDialog(self); dialog.setWindowTitle("Code Generation Options"); dialog.setWindowIcon(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"))
        layout = QFormLayout(dialog); layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)
        lang_combo = QComboBox(); lang_combo.addItems(["C", "C++"]); lang_combo.setCurrentText("C++")
        layout.addRow("Target Language:", lang_combo)
        
        output_dir_edit = QLineEdit(os.path.dirname(model_path))
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw")," Browse..."); browse_btn.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Base Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(output_dir_edit, 1); dir_layout.addWidget(browse_btn)
        layout.addRow("Base Output Directory:", dir_layout)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject); layout.addRow(btns)
        dialog.setMinimumWidth(450)

        if dialog.exec() == QDialog.Accepted:
            language = lang_combo.currentText()
            output_dir_base = output_dir_edit.text().strip()
            if not output_dir_base:
                QMessageBox.warning(self, "Input Error", "Base output directory is required.")
                return
            try:
                os.makedirs(output_dir_base, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create output directory:\n{e}")
                return

            self._start_matlab_operation(f"Generating {language} code for '{os.path.basename(model_path)}'")
            self.matlab_connection.generate_code(model_path, language, output_dir_base)

    def _get_bundled_file_path(self, filename: str) -> str | None: 
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        elif getattr(sys, 'frozen', False): 
             base_path = os.path.dirname(sys.executable)
        else: 
            base_path = os.path.dirname(os.path.abspath(__file__))

        possible_subdirs = ['', 'docs', 'resources', 'examples', '_internal/bsm_designer_project/docs', '_internal/bsm_designer_project/examples'] 

        for subdir in possible_subdirs:
            path_to_check = os.path.join(base_path, subdir, filename)
            if os.path.exists(path_to_check):
                logger.debug(f"Found bundled file '{filename}' at: {path_to_check}")
                return path_to_check
        
        logger.warning(f"Bundled file '{filename}' not found near base path '{base_path}'. Searched subdirs: {possible_subdirs}")
        return None


    def _open_example_file(self, filename: str): 
        if not self._prompt_save_if_dirty():
            return
        if self.py_sim_ui_manager: self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        example_path = self._get_bundled_file_path(filename)
        if example_path and os.path.exists(example_path):
            if self._load_from_path(example_path):
                self.current_file_path = example_path 
                self.last_generated_model_path = None
                self.undo_stack.clear()
                self.scene.set_dirty(False)
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                logging.info("Opened example file: %s", filename)
                if hasattr(self, 'status_label'): self.status_label.setText(f"Opened example: {filename}")
                bounds = self.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else:
                    self.view.resetTransform()
                    self.view.centerOn(self.scene.sceneRect().center())
            else:
                QMessageBox.critical(self, "Error Opening Example", f"Could not load the example file:\n{filename}")
                logging.error("Failed to open example file: %s", filename)
        else:
            QMessageBox.warning(self, "Example File Not Found", f"The example file '{filename}' could not be found.")
            logging.warning("Example file '%s' not found at path: %s", filename, example_path)

    def on_show_quick_start(self): 
        guide_path = self._get_bundled_file_path("QUICK_START.html")
        if guide_path:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path)):
                QMessageBox.warning(self, "Could Not Open Guide", f"Failed to open the Quick Start Guide.\nPath: {guide_path}")
                logging.warning("Failed to open Quick Start Guide from: %s", guide_path)
        else:
            QMessageBox.information(self, "Guide Not Found", "The Quick Start Guide (QUICK_START.html) was not found.")

    def on_about(self): 
        QMessageBox.about(self, f"About {APP_NAME}",
                          f"""<h3 style='color:{COLOR_ACCENT_PRIMARY};'>{APP_NAME} v{APP_VERSION}</h3>
                             <p>A graphical tool for designing and simulating Brain State Machines.</p>
                             <ul>
                                 <li>Visual FSM design and editing.</li>
                                 <li>Internal Python-based FSM simulation.</li>
                                 <li>MATLAB/Simulink model generation and simulation control.</li>
                                 <li>AI Assistant for FSM generation and chat (requires OpenAI API Key).</li>
                             </ul>
                             <p style='font-size:8pt;color:{COLOR_TEXT_SECONDARY};'>
                                 This software is intended for research and educational purposes.
                                 Always verify generated models and code.
                             </p>
                          """)

    def closeEvent(self, event: QCloseEvent): 
        if not self._prompt_ide_save_if_dirty(): # Check IDE first
            event.ignore()
            return
        
        if not self._prompt_save_if_dirty(): # Then check main diagram
            event.ignore()
            return

        if self.py_sim_ui_manager: 
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True) 

        if self.internet_check_timer and self.internet_check_timer.isActive():
            self.internet_check_timer.stop()
        
        if self.ai_chatbot_manager:
            self.ai_chatbot_manager.stop_chatbot()

        if self.resource_monitor_worker and self.resource_monitor_thread:
            logger.info("Stopping resource monitor on close...")
            if self.resource_monitor_thread.isRunning():
                QMetaObject.invokeMethod(self.resource_monitor_worker, "stop_monitoring", Qt.QueuedConnection)
                self.resource_monitor_thread.quit() 
                
                wait_time = 200 
                if hasattr(self.resource_monitor_worker, 'interval_ms'):
                     wait_time = self.resource_monitor_worker.interval_ms + 200 
                else: 
                    logger.warning("ResourceMonitorWorker has no interval_ms attribute, using default wait time for shutdown.")
                    wait_time = 2200


                if not self.resource_monitor_thread.wait(wait_time): 
                    logger.warning("Resource monitor thread did not quit gracefully. Terminating.")
                    self.resource_monitor_thread.terminate() 
                    self.resource_monitor_thread.wait(100) 
                else:
                    logger.info("Resource monitor thread stopped gracefully.")
            self.resource_monitor_worker = None 
            self.resource_monitor_thread = None
        
        # Both prompts passed or were not needed
        if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads:
            logging.info("Closing application. %d MATLAB processes initiated by this session may still be running in the background if not completed.", len(self.matlab_connection._active_threads))
        event.accept()


    def _init_internet_status_check(self): 
        self.internet_check_timer.timeout.connect(self._run_internet_check_job)
        self.internet_check_timer.start(15000) 
        QTimer.singleShot(100, self._run_internet_check_job) 

    def _run_internet_check_job(self): 
        current_status = False
        status_detail = "Checking..."
        try:
            s = socket.create_connection(("8.8.8.8", 53), timeout=1.5)
            s.close()
            current_status = True
            status_detail = "Connected"
        except socket.timeout:
            status_detail = "Disconnected (Timeout)"
        except (socket.gaierror, OSError): 
            status_detail = "Disconnected (Net Issue)"
        
        if current_status != self._internet_connected or self._internet_connected is None:
            self._internet_connected = current_status
            self._update_internet_status_display(current_status, status_detail)


    def _update_internet_status_display(self, is_connected: bool, message_detail: str): 
        full_status_text = f"Internet: {message_detail}"
        if hasattr(self, 'internet_status_label'):
            self.internet_status_label.setText(full_status_text)
            host_for_tooltip = socket.getfqdn('8.8.8.8') if is_connected else '8.8.8.8' 
            self.internet_status_label.setToolTip(f"{full_status_text} (Checks connection to {host_for_tooltip}:53)")
            text_color = COLOR_PY_SIM_STATE_ACTIVE.name() if is_connected else "#D32F2F" 
            self.internet_status_label.setStyleSheet(f"padding:0 5px;color:{text_color};")
        
        logging.debug("Internet Status Update: %s", message_detail)
        
        key_present = self.ai_chatbot_manager is not None and bool(self.ai_chatbot_manager.api_key)
        ai_ready = is_connected and key_present
        
        if hasattr(self.ai_chatbot_manager, 'set_online_status'):
            self.ai_chatbot_manager.set_online_status(is_connected) # Worker also needs to know
        
        self._update_ai_features_enabled_state(ai_ready)
        
        # Update AI Chatbot Dock status label specifically
        if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager:
            if not key_present:
                self.ai_chat_ui_manager.update_status_display("Status: API Key required. Configure in Settings.")
            elif not is_connected:
                self.ai_chat_ui_manager.update_status_display("Status: Offline. AI features unavailable.")
            # else: The AIChatbotManager will emit its own "Ready" or "Thinking" status (handled by its own statusUpdate signal)

    def _update_ai_features_enabled_state(self, is_online_and_key_present: bool):
        """Enables or disables AI-related UI elements."""
        if hasattr(self, 'ask_ai_to_generate_fsm_action'):
            self.ask_ai_to_generate_fsm_action.setEnabled(is_online_and_key_present)
        if hasattr(self, 'clear_ai_chat_action'): 
            self.clear_ai_chat_action.setEnabled(is_online_and_key_present) # Or always enabled if history is purely local
        
        if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager:
            if self.ai_chat_ui_manager.ai_chat_send_button:
                self.ai_chat_ui_manager.ai_chat_send_button.setEnabled(is_online_and_key_present)
            if self.ai_chat_ui_manager.ai_chat_input:
                self.ai_chat_ui_manager.ai_chat_input.setEnabled(is_online_and_key_present)
                current_placeholder = self.ai_chat_ui_manager.ai_chat_input.placeholderText()
                new_placeholder = "Type your message to the AI..."
                if not (self.ai_chatbot_manager and self.ai_chatbot_manager.api_key): # Check actual API key status
                    new_placeholder = "AI disabled: API Key required."
                elif not self._internet_connected : # Check MainWindow's internet status
                    new_placeholder = "AI disabled: Internet connection required."
                if current_placeholder != new_placeholder:
                    self.ai_chat_ui_manager.ai_chat_input.setPlaceholderText(new_placeholder)
        
        self._update_ide_related_actions() # This will handle ide_analyze_action based on its own logic


    def _update_py_sim_status_display(self): 
        if hasattr(self, 'py_sim_status_label'):
            if self.py_sim_active and self.py_fsm_engine: 
                current_state_name = self.py_fsm_engine.get_current_state_name()
                self.py_sim_status_label.setText(f"PySim: Active ({html.escape(current_state_name)})")
                self.py_sim_status_label.setStyleSheet(f"font-weight:bold;padding:0 5px;color:{COLOR_PY_SIM_STATE_ACTIVE.name()};")
            else:
                self.py_sim_status_label.setText("PySim: Idle")
                self.py_sim_status_label.setStyleSheet("font-weight:normal;padding:0 5px;")

    def _update_py_simulation_actions_enabled_state(self): 
        is_matlab_op_running = False
        if hasattr(self, 'progress_bar') and self.progress_bar: 
            is_matlab_op_running = self.progress_bar.isVisible()
            
        sim_can_start = not self.py_sim_active and not is_matlab_op_running
        sim_can_be_controlled = self.py_sim_active and not is_matlab_op_running

        if hasattr(self, 'start_py_sim_action'): self.start_py_sim_action.setEnabled(sim_can_start)
        if hasattr(self, 'stop_py_sim_action'): self.stop_py_sim_action.setEnabled(sim_can_be_controlled)
        if hasattr(self, 'reset_py_sim_action'): self.reset_py_sim_action.setEnabled(sim_can_be_controlled)
        
        if self.py_sim_ui_manager: 
            self.py_sim_ui_manager._update_internal_controls_enabled_state()

    # --- IDE Dock Methods ---

    def _get_active_ide_tab_data(self) -> dict | None:
        if not self.ide_tab_widget or self.ide_tab_widget.count() == 0:
            return None
        current_widget = self.ide_tab_widget.currentWidget()
        if current_widget and hasattr(current_widget, "_ide_tab_data"):
            return current_widget._ide_tab_data
        return None

    def _add_ide_tab(self, title="Untitled", content="", file_path=None, language="Python"):
        if not self.ide_tab_widget: return None

        # Generate a unique untitled name if needed
        final_title = title
        if not file_path and title.startswith("Untitled"):
            untitled_idx = 1
            existing_titles_no_star = {self.ide_tab_widget.tabText(i).replace("*","") for i in range(self.ide_tab_widget.count())}
            final_title = f"Untitled {untitled_idx}"
            while final_title in existing_titles_no_star:
                untitled_idx += 1
                final_title = f"Untitled {untitled_idx}"

        editor = CodeEditor()
        editor.setObjectName("StandaloneCodeEditor")
        editor.setPlainText(content)
        
        output_console = QTextEdit() 
        output_console.setObjectName("IDEOutputConsole")
        output_console.setReadOnly(True)
        output_console.setPlaceholderText("Script output will appear here...")
        output_console.setFixedHeight(100) 

        tab_content_widget = QWidget()
        tab_layout = QVBoxLayout(tab_content_widget)
        tab_layout.setContentsMargins(2,2,2,2)
        tab_layout.setSpacing(2)
        tab_layout.addWidget(editor)
        tab_layout.addWidget(output_console)

        tab_content_widget._ide_tab_data = {
            "editor": editor,
            "output_console": output_console,
            "path": file_path,
            "is_dirty": False if file_path and content else True, # New untitled tabs, or tabs with pre-filled content but no path, are dirty
            "language": language
        }
        editor.textChanged.connect(lambda widget=tab_content_widget: self._on_ide_text_changed_for_tab(widget))

        index = self.ide_tab_widget.addTab(tab_content_widget, final_title)
        self.ide_tab_widget.setCurrentIndex(index) # This will trigger _on_ide_current_tab_changed
        editor.setFocus()
        return tab_content_widget

    def _update_ide_tab_title(self, index: int):
        if not self.ide_tab_widget or index < 0 or index >= self.ide_tab_widget.count():
            return
        widget = self.ide_tab_widget.widget(index)
        if hasattr(widget, "_ide_tab_data"):
            tab_data = widget._ide_tab_data
            # Use the initially set tabText if it was an untitled tab, otherwise basename
            base_title = os.path.basename(tab_data["path"]) if tab_data["path"] else self.ide_tab_widget.tabText(index).replace("*","") 


            title = base_title
            if tab_data["is_dirty"]:
                title += "*"
            self.ide_tab_widget.setTabText(index, title)
            if self.ide_tab_widget.currentIndex() == index:
                self._update_window_title() 

    def _prompt_ide_save_if_dirty(self, tab_index: int = -1) -> bool:
        if not self.ide_tab_widget: return True
        
        target_tab_data = None
        tab_text_for_prompt = "current script"
        current_tab_index_to_save = tab_index

        if tab_index != -1 and tab_index < self.ide_tab_widget.count(): 
            widget = self.ide_tab_widget.widget(tab_index)
            if hasattr(widget, "_ide_tab_data"):
                target_tab_data = widget._ide_tab_data
                tab_text_for_prompt = self.ide_tab_widget.tabText(tab_index).replace("*","")
        else: 
            current_tab_index_to_save = self.ide_tab_widget.currentIndex()
            if current_tab_index_to_save != -1:
                 target_tab_data = self._get_active_ide_tab_data()
                 if target_tab_data:
                     tab_text_for_prompt = self.ide_tab_widget.tabText(current_tab_index_to_save).replace("*","")


        if not target_tab_data or not target_tab_data.get("is_dirty"):
            return True
        
        file_desc = os.path.basename(target_tab_data["path"]) if target_tab_data["path"] else tab_text_for_prompt
        reply = QMessageBox.question(self, "Save IDE Script?",
                                     f"The script '{file_desc}' has unsaved changes. Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save)
        if reply == QMessageBox.Save:
            return self._save_specific_ide_tab(current_tab_index_to_save)
        elif reply == QMessageBox.Cancel:
            return False
        return True # Discard

    def on_ide_new_file(self):
        untitled_idx = 1
        if self.ide_tab_widget:
            existing_titles_no_star = {self.ide_tab_widget.tabText(i).replace("*","") for i in range(self.ide_tab_widget.count())}
            new_title = f"Untitled {untitled_idx}"
            while new_title in existing_titles_no_star:
                untitled_idx += 1
                new_title = f"Untitled {untitled_idx}"
            self._add_ide_tab(title=new_title)
            logger.info(f"IDE: New script tab created: {new_title}")
        else: # Should not happen if IDE dock is properly set up
            logger.error("IDE: Tab widget not found for new file.")


    def on_ide_open_file(self):
        active_tab_idx = self.ide_tab_widget.currentIndex() if self.ide_tab_widget else -1
        active_tab_data = self._get_active_ide_tab_data()
        
        should_use_active_tab_for_open = False
        if active_tab_data and not active_tab_data["path"] and \
           (not active_tab_data["editor"] or not active_tab_data["editor"].toPlainText().strip()) and \
           not active_tab_data["is_dirty"]:
            should_use_active_tab_for_open = True
        elif active_tab_data and active_tab_data["is_dirty"]:
             if not self._prompt_ide_save_if_dirty(active_tab_idx):
                 return 

        start_dir = os.path.dirname(active_tab_data["path"]) if active_tab_data and active_tab_data["path"] else QDir.homePath()
        
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Script File", start_dir, 
                                                   "Python Files (*.py);;C/C++ Files (*.c *.cpp *.h *.ino);;Text Files (*.txt);;All Files (*)")
        if file_path:
            for i in range(self.ide_tab_widget.count()):
                tab_data = self.ide_tab_widget.widget(i)._ide_tab_data
                if tab_data["path"] == file_path:
                    self.ide_tab_widget.setCurrentIndex(i)
                    return

            target_tab_widget = None
            if should_use_active_tab_for_open and active_tab_idx != -1:
                target_tab_widget = self.ide_tab_widget.widget(active_tab_idx)
            else:
                new_tab_title = os.path.basename(file_path)
                # Ensure new tab title is unique if untitled with same name exists
                num_tabs = self.ide_tab_widget.count()
                existing_titles_no_star = {self.ide_tab_widget.tabText(i).replace("*","") for i in range(num_tabs)}
                if new_title in existing_titles_no_star:
                    untitled_idx = 1
                    temp_title = f"{new_title} ({untitled_idx})"
                    while temp_title in existing_titles_no_star:
                        untitled_idx += 1
                        temp_title = f"{new_title} ({untitled_idx})"
                    new_tab_title = temp_title

                target_tab_widget = self._add_ide_tab(title=new_tab_title, file_path=file_path)
                if not target_tab_widget: return 
            
            current_tab_data = target_tab_widget._ide_tab_data
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_tab_data["editor"].setPlainText(f.read())
                current_tab_data["path"] = file_path
                current_tab_data["is_dirty"] = False
                if "output_console" in current_tab_data and current_tab_data["output_console"]:
                    current_tab_data["output_console"].clear()
                
                idx = self.ide_tab_widget.indexOf(target_tab_widget)
                self.ide_tab_widget.setTabText(idx, os.path.basename(file_path)) # Set title without dirty marker first
                self._update_ide_tab_title(idx) 
                self.ide_tab_widget.setCurrentIndex(idx) 

                logger.info("IDE: Opened script: %s", file_path)
                
                ext = os.path.splitext(file_path)[1].lower()
                lang_to_set = "Python"
                if ext in [".ino", ".c", ".cpp", ".h"]: lang_to_set = "C/C++ (Arduino)"
                elif ext != ".py": lang_to_set = "Text"
                
                current_tab_data["language"] = lang_to_set
                if self.ide_language_combo.currentText() != lang_to_set: 
                    self.ide_language_combo.setCurrentText(lang_to_set) 
                else: 
                    current_tab_data["editor"].set_language(lang_to_set)
                
            except Exception as e:
                QMessageBox.critical(self, "Error Opening Script", f"Could not load script from {file_path}:\n{e}")
                logger.error("IDE: Failed to open script %s: %s", file_path, e)
                if target_tab_widget and not should_use_active_tab_for_open: 
                    self.ide_tab_widget.removeTab(self.ide_tab_widget.indexOf(target_tab_widget))
                elif should_use_active_tab_for_open and current_tab_data : 
                    current_tab_data["editor"].clear()
                    current_tab_data["path"] = None
                    current_tab_data["is_dirty"] = False
                    self._update_ide_tab_title(self.ide_tab_widget.currentIndex())
            
            self._update_ide_related_actions()

    def _save_specific_ide_tab(self, index: int) -> bool:
        if not self.ide_tab_widget or index < 0 or index >= self.ide_tab_widget.count():
            return False
        
        tab_widget_item = self.ide_tab_widget.widget(index)
        if not hasattr(tab_widget_item, "_ide_tab_data"): return False
        
        tab_data = tab_widget_item._ide_tab_data
        
        file_to_save_path = tab_data["path"]
        if not file_to_save_path: 
            current_tab_text = self.ide_tab_widget.tabText(index).replace("*","")
            default_filename = f"{current_tab_text}.py" # Default to .py for untitled
            
            lang = tab_data.get("language", "Python")
            if lang == "Python": default_filename = default_filename.rsplit('.',1)[0] + ".py"
            elif "Arduino" in lang: default_filename = default_filename.rsplit('.',1)[0] + ".ino"
            elif "C/C++" in lang: default_filename = default_filename.rsplit('.',1)[0] + ".cpp"
            else: default_filename = default_filename.rsplit('.',1)[0] + ".txt"

            start_dir = QDir.homePath()
            file_path_dialog, _ = QFileDialog.getSaveFileName(self, f"Save Script '{current_tab_text}' As", os.path.join(start_dir, default_filename),
                                                       "Python Files (*.py);;C/C++ Files (*.c *.cpp *.h *.ino);;Text Files (*.txt);;All Files (*)")
            if not file_path_dialog: return False 
            file_to_save_path = file_path_dialog

        try:
            with open(file_to_save_path, 'w', encoding='utf-8') as f:
                f.write(tab_data["editor"].toPlainText())
            tab_data["path"] = file_to_save_path 
            tab_data["is_dirty"] = False
            self.ide_tab_widget.setTabText(index, os.path.basename(file_to_save_path)) # Update tab text to new filename
            self._update_ide_tab_title(index) # Re-apply dirty marker logic if any (should be clean now)
            logger.info(f"IDE: Saved script in tab '{self.ide_tab_widget.tabText(index)}' to: {tab_data['path']}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error Saving Script", f"Could not save script to {file_to_save_path}:\n{e}")
            logger.error(f"IDE: Failed to save script {file_to_save_path}: {e}")
            return False

    def _save_ide_to_path(self, file_path) -> bool: # This will now save the CURRENT tab
        active_tab_data = self._get_active_ide_tab_data()
        if not active_tab_data or not active_tab_data["editor"]: return False
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(active_tab_data["editor"].toPlainText())
            active_tab_data["path"] = file_path
            active_tab_data["is_dirty"] = False
            self._update_ide_tab_title(self.ide_tab_widget.currentIndex())
            logger.info("IDE: Saved active script to: %s", file_path)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error Saving Script", f"Could not save script to {file_path}:\n{e}")
            logger.error("IDE: Failed to save script %s: %s", file_path, e)
            return False

    def on_ide_save_file(self) -> bool:
        active_tab_data = self._get_active_ide_tab_data()
        if not active_tab_data: return False

        if not active_tab_data["path"]:
            return self.on_ide_save_as_file() # Will operate on current tab
        if active_tab_data["is_dirty"]: 
             return self._save_ide_to_path(active_tab_data["path"])
        return True 

    def on_ide_save_as_file(self) -> bool:
        active_tab_data = self._get_active_ide_tab_data()
        if not active_tab_data or not active_tab_data["editor"]: return False

        current_tab_text = self.ide_tab_widget.tabText(self.ide_tab_widget.currentIndex()).replace("*","")
        default_filename = os.path.basename(active_tab_data["path"] or f"{current_tab_text}.py")
        
        lang = active_tab_data.get("language", "Python")
        if lang == "Python": default_filename = default_filename.rsplit('.',1)[0] + ".py"
        elif "Arduino" in lang: default_filename = default_filename.rsplit('.',1)[0] + ".ino"
        elif "C/C++" in lang: default_filename = default_filename.rsplit('.',1)[0] + ".cpp"
        else: default_filename = default_filename.rsplit('.',1)[0] + ".txt"

        start_dir = os.path.dirname(active_tab_data["path"]) if active_tab_data["path"] else QDir.homePath()
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Script As", os.path.join(start_dir, default_filename),
                                                   "Python Files (*.py);;C/C++ Files (*.c *.cpp *.h *.ino);;Text Files (*.txt);;All Files (*)")
        if file_path:
            active_tab_data["path"] = file_path # Update path for the current tab before saving
            
            ext = os.path.splitext(file_path)[1].lower()
            new_lang = "Python"
            if ext in [".ino", ".c", ".cpp", ".h"]: new_lang = "C/C++ (Arduino)"
            elif ext != ".py": new_lang = "Text"
            
            if active_tab_data["language"] != new_lang:
                active_tab_data["language"] = new_lang
                self.ide_language_combo.setCurrentText(new_lang) 
                active_tab_data["editor"].set_language(new_lang)

            return self._save_ide_to_path(file_path) 
        return False

    @pyqtSlot()
    def _on_ide_text_changed(self):
        pass # Handled by _on_ide_text_changed_for_tab

    def _on_ide_text_changed_for_tab(self, tab_widget_item):
        if hasattr(tab_widget_item, "_ide_tab_data"):
            tab_data = tab_widget_item._ide_tab_data
            if not tab_data["is_dirty"]:
                tab_data["is_dirty"] = True
                idx = self.ide_tab_widget.indexOf(tab_widget_item)
                if idx != -1: 
                    self._update_ide_tab_title(idx)
        self._update_ide_related_actions() 


    @pyqtSlot(str)
    def _on_ide_language_changed(self, language: str):
        active_tab_data = self._get_active_ide_tab_data()
        if active_tab_data and active_tab_data.get("editor"):
            active_tab_data["editor"].set_language(language)
            active_tab_data["language"] = language 
            logger.info(f"IDE: Language for tab '{self.ide_tab_widget.tabText(self.ide_tab_widget.currentIndex())}' set to {language}.")
        self._update_ide_related_actions() 

    def _update_ide_related_actions(self):
        active_tab_data = self._get_active_ide_tab_data()
        
        selected_language = active_tab_data["language"] if active_tab_data else "Python"
        
        has_text_in_ide = False
        if active_tab_data and active_tab_data.get("editor"):
            has_text_in_ide = bool(active_tab_data["editor"].toPlainText().strip())
        
        has_console_output = False
        if active_tab_data and active_tab_data.get("output_console"):
            has_console_output = bool(active_tab_data["output_console"].toPlainText().strip())

        
        is_python = (selected_language == "Python")
        can_analyze_with_ai = (selected_language == "Python" or selected_language.startswith("C/C++")) and \
                              self.ai_chatbot_manager is not None and \
                              bool(self.ai_chatbot_manager.api_key) and \
                              self._internet_connected 
        
        if self.ide_run_script_action:
            self.ide_run_script_action.setEnabled(is_python and has_text_in_ide)
            self.ide_run_script_action.setToolTip("Run the current Python script in the editor" if is_python else "Run is currently only supported for Python scripts")
        
        if self.ide_analyze_action:
            self.ide_analyze_action.setEnabled(can_analyze_with_ai and has_text_in_ide)
            tooltip = "Analyze the current code with AI"
            if not has_text_in_ide:
                tooltip = "Write some code to analyze with AI"
            elif not (self.ai_chatbot_manager and self.ai_chatbot_manager.api_key):
                tooltip += " (API Key required)"
            elif not self._internet_connected:
                 tooltip += " (Internet connection required)"
            elif not (selected_language == "Python" or selected_language.startswith("C/C++")):
                 tooltip += " (Best for Python or C/C++)"
            self.ide_analyze_action.setToolTip(tooltip)

        if self.ide_find_action:
            self.ide_find_action.setEnabled(has_text_in_ide)
        if self.ide_replace_action:
            self.ide_replace_action.setEnabled(has_text_in_ide)
        if self.ide_close_tab_action:
            self.ide_close_tab_action.setEnabled(self.ide_tab_widget is not None and self.ide_tab_widget.count() > 0)

        
        if self.ide_clear_console_action:
            self.ide_clear_console_action.setEnabled(has_console_output)
        if self.ide_save_output_action:
            self.ide_save_output_action.setEnabled(has_console_output)


        self._update_ide_save_actions_enable_state() 
        logger.debug(f"IDE actions updated. Lang: {selected_language}, Python Run: {is_python and has_text_in_ide}, AI Analyze: {can_analyze_with_ai and has_text_in_ide}")


    @pyqtSlot()
    def on_ide_run_python_script(self):
        active_tab_data = self._get_active_ide_tab_data()
        if not active_tab_data or not active_tab_data["editor"] or not active_tab_data["output_console"]:
            logger.error("IDE: Code editor or output console not available for running script.")
            return
        
        if active_tab_data["language"] != "Python": 
            QMessageBox.information(self, "Run Script", "Currently, only Python scripts can be run directly from the IDE.")
            return

        code_to_run = active_tab_data["editor"].toPlainText()
        if not code_to_run.strip():
            active_tab_data["output_console"].setHtml("<i>No Python code to run.</i>") 
            return

        active_tab_data["output_console"].clear()
        active_tab_data["output_console"].append(f"<i style='color:grey;'>Running Python script at {QTime.currentTime().toString('hh:mm:ss')}...</i><hr>")

        script_globals = {"__name__": "__ide_script__"}
        script_locals = {}
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                exec(code_to_run, script_globals, script_locals)
            
            active_tab_data["output_console"].append(html.escape(stdout_capture.getvalue()))
            err_output = stderr_capture.getvalue()
            if err_output:
                active_tab_data["output_console"].append(f"<pre style='color:red;'>{html.escape(err_output)}</pre>")
            active_tab_data["output_console"].append("<hr><i style='color:grey;'>Execution finished.</i>")
        except Exception as e:
            import traceback
            active_tab_data["output_console"].append(f"<pre style='color:red;'><b>Error during execution:</b>\n{html.escape(str(e))}\n--- Traceback ---\n{html.escape(traceback.format_exc())}</pre>")
            active_tab_data["output_console"].append("<hr><i style='color:red;'>Execution failed.</i>")
        finally:
            stdout_capture.close()
            stderr_capture.close()
            active_tab_data["output_console"].ensureCursorVisible()
        self._update_ide_related_actions()

    @pyqtSlot()
    def on_ide_analyze_with_ai(self):
        active_tab_data = self._get_active_ide_tab_data()
        if not active_tab_data or not active_tab_data["editor"] or not active_tab_data["output_console"]:
            logger.error("IDE: Code editor or output console not available for AI analysis.")
            return
        if not self.ai_chatbot_manager or not self.ai_chatbot_manager.api_key: 
            QMessageBox.warning(self, "AI Assistant Not Ready", "Please configure your OpenAI API key in AI Assistant Settings to use this feature.")
            return

        code_to_analyze = active_tab_data["editor"].toPlainText()
        if not code_to_analyze.strip():
            active_tab_data["output_console"].setHtml("<i>No code to analyze.</i>")
            return

        selected_language = active_tab_data["language"]
        language_context = ""
        if "Arduino" in selected_language: language_context = "for Arduino"
        elif "C/C++" in selected_language: language_context = "for generic C/C++"
        elif "Python" in selected_language: language_context = "for Python"

        prompt = f"Please review the following {selected_language} code snippet {language_context}. Check for syntax errors, common programming mistakes, potential bugs, or suggest improvements. Provide feedback and, if there are issues, offer a corrected version or explain the problem:\n\n```\n{code_to_analyze}\n```"
        
        active_tab_data["output_console"].append(f"<i style='color:grey;'>Sending code to AI for analysis ({selected_language})... (Response will appear in main AI Chat window)</i><hr>")
        self.ai_chat_ui_manager._append_to_chat_display("IDE", f"Requesting AI analysis for the current script ({selected_language}).") 
        self.ai_chatbot_manager.send_message(prompt) 

    @pyqtSlot()
    def on_ide_clear_console(self):
        active_tab_data = self._get_active_ide_tab_data()
        if active_tab_data and active_tab_data["output_console"]:
            active_tab_data["output_console"].clear()
            active_tab_data["output_console"].setPlaceholderText("Script output will appear here...")
            logger.info("IDE: Output console cleared.")
        self._update_ide_related_actions()


    @pyqtSlot()
    def on_ide_save_output(self):
        active_tab_data = self._get_active_ide_tab_data()
        if not active_tab_data or not active_tab_data["output_console"] or \
           not active_tab_data["output_console"].toPlainText().strip():
            QMessageBox.information(self, "Save Output", "Output console is empty. Nothing to save.")
            return
        
        start_dir = os.path.dirname(active_tab_data["path"]) if active_tab_data["path"] else QDir.homePath()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Console Output", os.path.join(start_dir, "ide_output.txt"), "Text Files (*.txt);;All Files (*)")
        if file_path:
            self._save_text_to_file(file_path, active_tab_data["output_console"].toPlainText())


    def on_ide_find(self):
        active_tab_data = self._get_active_ide_tab_data()
        if not active_tab_data or not active_tab_data.get("editor"):  
            return

        if not hasattr(self, '_find_replace_dialog_instance') or not self._find_replace_dialog_instance or not self._find_replace_dialog_instance.isVisible():
            self._find_replace_dialog_instance = FindReplaceDialog(active_tab_data["editor"], parent=self)
        else: 
            self._find_replace_dialog_instance.editor = active_tab_data["editor"] 
            self._find_replace_dialog_instance.prepare_for_mode(replace_mode=False)

        self._find_replace_dialog_instance.show()
        self._find_replace_dialog_instance.activateWindow() 
        self._find_replace_dialog_instance.set_find_focus()


    def on_ide_replace(self):
        active_tab_data = self._get_active_ide_tab_data()
        if not active_tab_data or not active_tab_data.get("editor"): return

        if not hasattr(self, '_find_replace_dialog_instance') or not self._find_replace_dialog_instance or not self._find_replace_dialog_instance.isVisible():
            self._find_replace_dialog_instance = FindReplaceDialog(active_tab_data["editor"], parent=self, replace_mode=True) 
        else:
            self._find_replace_dialog_instance.editor = active_tab_data["editor"]
            self._find_replace_dialog_instance.prepare_for_mode(True)

        self._find_replace_dialog_instance.show()
        self._find_replace_dialog_instance.activateWindow()
        self._find_replace_dialog_instance.set_replace_focus()

    @pyqtSlot(int)
    def _on_ide_tab_close_requested(self, index):
        if not self.ide_tab_widget: return
        
        if not self._prompt_ide_save_if_dirty(index): 
            return

        widget_to_remove = self.ide_tab_widget.widget(index)
        self.ide_tab_widget.removeTab(index)
        if widget_to_remove: 
            widget_to_remove.deleteLater() 

        if self.ide_tab_widget.count() == 0: 
            self.on_ide_new_file() # Calls _add_ide_tab with unique naming
        self._update_ide_related_actions()
        self._update_window_title()

    def on_ide_close_current_tab(self):
        if self.ide_tab_widget and self.ide_tab_widget.count() > 0:
            self._on_ide_tab_close_requested(self.ide_tab_widget.currentIndex())

    @pyqtSlot(int)
    def _on_ide_current_tab_changed(self, index):
        if index == -1 and self.ide_tab_widget and self.ide_tab_widget.count() == 0 : 
             # This case is tricky; if all tabs are closed and then one is added,
             # this signal might fire with -1 *before* the new tab's signal.
             # _add_ide_tab should handle the primary update.
             # For now, if no tabs, ensure actions are consistent.
             self._update_window_title()
             self._update_ide_related_actions()
             return
        elif index != -1: 
            self._update_window_title()
            self._update_ide_related_actions()
            active_tab_data = self._get_active_ide_tab_data()
            if active_tab_data and self.ide_language_combo:
                self.ide_language_combo.blockSignals(True)
                self.ide_language_combo.setCurrentText(active_tab_data.get("language", "Python"))
                self.ide_language_combo.blockSignals(False)
                if active_tab_data.get("editor"): 
                    active_tab_data["editor"].set_language(active_tab_data.get("language", "Python")) 
        else: # index is -1, but count > 0 (e.g. after a tab is removed but one still remains)
             self._update_window_title()
             self._update_ide_related_actions()


    def _save_text_to_file(self, file_path: str, text_content: str) -> bool:
        """Helper function to save generic text content to a file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text_content)
            logger.info(f"Content successfully saved to: {file_path}")
            if hasattr(self, 'status_label'): self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            return True
        except Exception as e:
            logger.error(f"Error saving content to {file_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Save Error", f"Could not save content to file:\n{e}")
            return False

    def log_message(self, level_str: str, message: str): 
        level = getattr(logging, level_str.upper(), logging.INFO)
        logger.log(level, message) 


if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    import traceback # Make sure traceback is imported for on_ide_run_python_script
    app_dir = os.path.dirname(os.path.abspath(__file__))
    deps_icons_dir = os.path.join(app_dir, "dependencies", "icons")
    if not os.path.exists(deps_icons_dir):
        try:
            os.makedirs(deps_icons_dir, exist_ok=True)
            print(f"Info: Created directory for QSS icons: {deps_icons_dir}")
        except OSError as e:
            print(f"Warning: Could not create directory {deps_icons_dir}: {e}")


    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET_GLOBAL) 
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
