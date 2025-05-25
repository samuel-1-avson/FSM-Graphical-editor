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
from PyQt5.QtCore import QTime, QTimer, QPointF, QMetaObject
import pygraphviz as pgv

# --- Custom Modules ---
from graphics_scene import DiagramScene, ZoomableView
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand
from fsm_simulator import FSMSimulator, FSMError
from ai_chatbot import AIChatbotManager
from dialogs import (MatlabSettingsDialog)
from config import (
    APP_VERSION, APP_NAME, FILE_EXTENSION, FILE_FILTER, STYLE_SHEET_GLOBAL,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG,
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_PRIMARY_LIGHT,
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_BACKGROUND_LIGHT, COLOR_GRID_MINOR, COLOR_GRID_MAJOR,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_ON_ACCENT,
    COLOR_ACCENT_SECONDARY, COLOR_BORDER_LIGHT, COLOR_BORDER_MEDIUM
)
from utils import get_standard_icon # Ensure utils.py is updated to take 2 args

# --- UI Managers ---
from ui_py_simulation_manager import PySimulationUIManager
from ui_ai_chatbot_manager import AIChatUIManager

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
            self.finished_signal.emit(success, message, output_data_for_signal)


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
        self.matlab_path = path.strip() if path else ""
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
            if path_candidate == 'matlab' and sys.platform != 'win32':
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


# --- Resource Monitor Worker ---
class ResourceMonitorWorker(QObject):
    resourceUpdate = pyqtSignal(float, float, float, str)

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
            except Exception as e:
                logger.warning(f"Could not initialize NVML (for NVIDIA GPU monitoring): {e}")
                self._nvml_initialized = False
                self._gpu_name_cache = "NVIDIA NVML Err"
        elif not PYNVML_AVAILABLE:
            self._gpu_name_cache = "N/A (pynvml N/A)"

    @pyqtSlot()
    def start_monitoring(self):
        self._monitoring = True
        self._monitor_resources()

    @pyqtSlot()
    def stop_monitoring(self):
        self._monitoring = False
        if self._nvml_initialized and PYNVML_AVAILABLE and pynvml:
            try: pynvml.nvmlShutdown()
            except Exception as e: logger.warning(f"Error shutting down NVML: {e}")

    def _monitor_resources(self):
        while self._monitoring:
            if self._nvml_initialized and not self._gpu_handle and PYNVML_AVAILABLE and pynvml:
                try:
                    if pynvml.nvmlDeviceGetCount() > 0:
                        self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                        self._gpu_name_cache = pynvml.nvmlDeviceGetName(self._gpu_handle).decode('utf-8')
                except Exception as e_nvml: logger.debug(f"NVML: No GPU handle/name: {e_nvml}")
            try:
                cpu_usage = psutil.cpu_percent(interval=None)
                ram_percent = psutil.virtual_memory().percent
                gpu_util, gpu_name_to_emit = -1.0, self._gpu_name_cache
                if self._nvml_initialized and self._gpu_handle and PYNVML_AVAILABLE and pynvml:
                    try: gpu_util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle).gpu
                    except Exception: gpu_util, gpu_name_to_emit = -2.0, "NVIDIA GPU Poll Err"
                self.resourceUpdate.emit(cpu_usage, ram_percent, gpu_util, gpu_name_to_emit)
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                self.resourceUpdate.emit(-1, -1, -1, f"Error: {str(e)[:20]}")
            QThread.msleep(self.interval_ms)


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

        self.py_sim_ui_manager = PySimulationUIManager(self)
        self.ai_chat_ui_manager = AIChatUIManager(self)

        self.py_sim_ui_manager.simulationStateChanged.connect(self._handle_py_sim_state_changed_by_manager)
        self.py_sim_ui_manager.requestGlobalUIEnable.connect(self._handle_py_sim_global_ui_enable_by_manager)

        self._internet_connected: bool | None = None
        self.internet_check_timer = QTimer(self)
        
        self.resource_monitor_worker: ResourceMonitorWorker | None = None
        self.resource_monitor_thread: QThread | None = None

        self.init_ui() 

        try:
            setup_global_logging(self.log_output) 
            logger.info("Main window initialized and logging configured.")
        except Exception as e: 
            logger.error(f"Failed to run setup_global_logging: {e}. UI logs might not work.")

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

        self._update_window_title()
        self.on_new_file(silent=True)
        self._init_internet_status_check()
        self.scene.selectionChanged.connect(self._update_properties_dock)
        self._update_properties_dock()
        self._update_py_simulation_actions_enabled_state() 

        if not self.ai_chatbot_manager.api_key:
            self.ai_chat_ui_manager.update_status_display("Status: API Key required. Configure in Settings.")
        else:
            self.ai_chat_ui_manager.update_status_display("Status: Ready.")


    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050)
        # Corrected: Pass QStyle.SP_DesktopIcon directly as get_standard_icon expects the enum value
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
        # All calls to get_standard_icon now pass 2 arguments
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
        self.ask_ai_to_generate_fsm_action = QAction(QIcon.fromTheme("system-run", get_standard_icon(QStyle.SP_DialogYesButton, "AIGen")), "Generate FSM from Description...", self)

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

        # Tools Dock
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

        # Properties Dock
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

        # Log Dock
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

        # Python Simulation Dock
        self.py_sim_dock = QDockWidget("Python Simulation", self)
        self.py_sim_dock.setObjectName("PySimDock")
        self.py_sim_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        py_sim_contents_widget = self.py_sim_ui_manager.create_dock_widget_contents()
        self.py_sim_dock.setWidget(py_sim_contents_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.py_sim_dock.toggleViewAction())

        # AI Chatbot Dock
        self.ai_chatbot_dock = QDockWidget("AI Chatbot", self)
        self.ai_chatbot_dock.setObjectName("AIChatbotDock")
        self.ai_chatbot_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        ai_chat_contents_widget = self.ai_chat_ui_manager.create_dock_widget_contents()
        self.ai_chatbot_dock.setWidget(ai_chat_contents_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.ai_chatbot_dock.toggleViewAction())

        self.tabifyDockWidget(self.properties_dock, self.ai_chatbot_dock)
        self.tabifyDockWidget(self.ai_chatbot_dock, self.py_sim_dock)


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
                self.ai_chat_ui_manager._append_to_chat_display("System", f"Warning: AI FSM layout failed. Using basic grid.")
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
                        except ValueError: logger.warning("MW: Invalid AI control offsets for %s->%s.", src_name, tgt_name)
                    items_to_add_for_undo_command.append(trans_item)
                except Exception as e: logger.error("MW: Error creating AI GraphicsTransitionItem %s->%s: %s", src_name, tgt_name, e, exc_info=True)
            else: logger.warning("MW: Could not find source/target for AI transition: %s->%s. Skipping.", src_name, tgt_name)

        max_y_items = max((item.scenePos().y() + item.boundingRect().height() for item in state_items_map.values() if item.scenePos()), default=layout_start_y) if state_items_map else layout_start_y
        for i, comment_data in enumerate(fsm_data.get('comments', [])):
            text = comment_data.get('text'); width = comment_data.get('width')
            if not text: continue
            pos_x = comment_data.get('x', layout_start_x + i * (150 + 20)); pos_y = comment_data.get('y', max_y_items + 100)
            try:
                comment_item = GraphicsCommentItem(pos_x, pos_y, text)
                if width:
                    try: comment_item.setTextWidth(float(width))
                    except ValueError: logger.warning("MW: Invalid AI width for comment.")
                items_to_add_for_undo_command.append(comment_item)
            except Exception as e: logger.error("MW: Error creating AI GraphicsCommentItem: %s", e, exc_info=True)

        if items_to_add_for_undo_command:
            for item in items_to_add_for_undo_command:
                item_type = type(item).__name__.replace("Graphics","").replace("Item","")
                cmd_txt = f"Add AI {item_type}" + (f": {item.text_label}" if hasattr(item, 'text_label') and item.text_label else (f" ({item._compose_label_string()})" if hasattr(item, '_compose_label_string') else (f": {item.toPlainText()[:20]}..." if hasattr(item, 'toPlainText') and item.toPlainText() else "")))
                self.undo_stack.push(AddItemCommand(self.scene, item, cmd_txt))
            logger.info("MW: Added %d AI items to diagram.", len(items_to_add_for_undo_command))
            QTimer.singleShot(100, self._fit_view_to_new_ai_items)
        else: logger.info("MW: No valid AI items generated to add.")

        if not clear_current_diagram and items_to_add_for_undo_command: self.undo_stack.endMacro()
        elif not clear_current_diagram: self.undo_stack.endMacro() 

        if self.py_sim_active and items_to_add_for_undo_command: # Check MW's py_sim_active
            logger.info("MW: Reinitializing Python simulation after adding AI FSM.")
            try:
                self.py_fsm_engine = FSMSimulator(self.scene.get_diagram_data()['states'], self.scene.get_diagram_data()['transitions'])
                if self.py_sim_ui_manager:
                    self.py_sim_ui_manager.append_to_action_log(["Python FSM Simulation reinitialized for new diagram from AI."])
                    self.py_sim_ui_manager.update_dock_ui_contents()
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
        elif self.view and self.scene.sceneRect(): self.view.centerOn(self.scene.sceneRect().center())

    def on_matlab_settings(self):
        dialog = MatlabSettingsDialog(matlab_connection=self.matlab_connection, parent=self)
        dialog.exec()
        logger.info("MATLAB settings dialog closed.")


    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems()
        html_content, edit_enabled, item_type_tooltip = "", False, "item"
        if len(selected_items) == 1:
            item, props = selected_items[0], selected_items[0].get_data() if hasattr(selected_items[0], 'get_data') else {}
            item_type_name = type(item).__name__.replace("Graphics", "").replace("Item", ""); item_type_tooltip, edit_enabled = item_type_name.lower(), True
            fmt = lambda txt, max_chars=25: "<i>(none)</i>" if not txt else (html.escape(str(txt)).split('\n')[0][:max_chars] + ("…" if len(html.escape(str(txt)).split('\n')[0]) > max_chars or '\n' in html.escape(str(txt)) else ""))
            rows = ""
            if isinstance(item, GraphicsStateItem):
                c = QColor(props.get('color', COLOR_ITEM_STATE_DEFAULT_BG)); cs = f"background-color:{c.name()}; color:{'black' if c.lightnessF()>0.5 else 'white'}; padding:1px 4px; border-radius:2px;"
                rows += f"<tr><td><b>Name:</b></td><td>{html.escape(props.get('name', 'N/A'))}</td></tr>"
                rows += f"<tr><td><b>Initial/Final:</b></td><td>{'Yes' if props.get('is_initial') else 'No'} / {'Yes' if props.get('is_final') else 'No'}</td></tr>"
                if props.get('is_superstate'): rows += f"<tr><td><b>Superstate:</b></td><td>Yes ({len(props.get('sub_fsm_data',{}).get('states',[]))} sub-states)</td></tr>"
                rows += f"<tr><td><b>Color:</b></td><td><span style='{cs}'>{html.escape(c.name())}</span></td></tr>"
                for act in ['entry_action', 'during_action', 'exit_action']: rows += f"<tr><td><b>{act.split('_')[0].capitalize()}:</b></td><td>{fmt(props.get(act, ''))}</td></tr>"
                if props.get('description'): rows += f"<tr><td colspan='2'><b>Desc:</b> {fmt(props.get('description'), 50)}</td></tr>"
            elif isinstance(item, GraphicsTransitionItem):
                c = QColor(props.get('color', COLOR_ITEM_TRANSITION_DEFAULT)); cs = f"background-color:{c.name()}; color:{'black' if c.lightnessF()>0.5 else 'white'}; padding:1px 4px; border-radius:2px;"
                lbl = " ".join(p for p in [html.escape(props.get('event','')) if props.get('event') else '', f"[{html.escape(props.get('condition',''))}]" if props.get('condition') else '', f"/{{{fmt(props.get('action',''),15)}}}" if props.get('action') else ''] if p) or "<i>(No Label)</i>"
                rows += f"<tr><td><b>Label:</b></td><td style='font-size:8pt;'>{lbl}</td></tr>"
                rows += f"<tr><td><b>From/To:</b></td><td>{html.escape(props.get('source','N/A'))} → {html.escape(props.get('target','N/A'))}</td></tr>"
                rows += f"<tr><td><b>Color:</b></td><td><span style='{cs}'>{html.escape(c.name())}</span></td></tr>"
                rows += f"<tr><td><b>Curve:</b></td><td>Bend={props.get('control_offset_x',0):.0f}, Shift={props.get('control_offset_y',0):.0f}</td></tr>"
                if props.get('description'): rows += f"<tr><td colspan='2'><b>Desc:</b> {fmt(props.get('description'), 50)}</td></tr>"
            elif isinstance(item, GraphicsCommentItem): rows += f"<tr><td colspan='2'><b>Text:</b> {fmt(props.get('text', ''), 60)}</td></tr>"
            else: rows, item_type_name = "<tr><td>Unknown Item Type</td></tr>", "Unknown"
            html_content = f"""<div style='font-family:"Segoe UI",Arial;font-size:9pt;line-height:1.5;'><h4 style='margin:0 0 5px 0;padding:2px 0;color:{COLOR_ACCENT_PRIMARY};border-bottom:1px solid {COLOR_BORDER_LIGHT};'>Type: {item_type_name}</h4><table style='width:100%;border-collapse:collapse;'>{rows}</table></div>"""
        elif len(selected_items) > 1: html_content, item_type_tooltip = f"<i><b>{len(selected_items)} items selected.</b><br>Select single item.</i>", f"{len(selected_items)} items"
        else: html_content = "<i>No item selected.</i><br><small>Click an item or use tools to add.</small>"
        self.properties_editor_label.setText(html_content)
        self.properties_edit_button.setEnabled(edit_enabled)
        self.properties_edit_button.setToolTip(f"Edit properties of selected {item_type_tooltip}" if edit_enabled else "Select single item to enable")

    def _on_edit_selected_item_properties_from_dock(self):
        selected = self.scene.selectedItems()
        if len(selected) == 1: self.scene.edit_item_properties(selected[0])

    def _update_window_title(self):
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        title = f"{APP_NAME} - {file_name}{' [PySim Running]' if self.py_sim_active else ''}"
        self.setWindowTitle(title + "[*]")
        if hasattr(self, 'status_label'): self.status_label.setText(f"File: {file_name}{' *' if self.isWindowModified() else ''} | PySim: {'Active' if self.py_sim_active else 'Idle'}")

    def _update_save_actions_enable_state(self):
        self.save_action.setEnabled(self.isWindowModified())

    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo())
        self.redo_action.setEnabled(self.undo_stack.canRedo())
        self.undo_action.setText(f"&Undo {self.undo_stack.undoText()}" if self.undo_stack.undoText() else "&Undo")
        self.redo_action.setText(f"&Redo {self.undo_stack.redoText()}" if self.undo_stack.redoText() else "&Redo")

    def _update_matlab_status_display(self, connected, message):
        text, tooltip = f"MATLAB: {'Connected' if connected else 'Not Connected'}", f"MATLAB Status: {message}"
        if hasattr(self, 'matlab_status_label'):
            self.matlab_status_label.setText(text); self.matlab_status_label.setToolTip(tooltip)
            self.matlab_status_label.setStyleSheet(f"font-weight:bold;padding:0 5px;color:{COLOR_PY_SIM_STATE_ACTIVE.name() if connected else '#C62828'};")
        if "Initializing" not in message: logging.info("MATLAB Conn: %s", message)
        self._update_matlab_actions_enabled_state()

    def _update_matlab_actions_enabled_state(self):
        can_run_matlab = self.matlab_connection.connected and not self.py_sim_active
        for action in [self.export_simulink_action, self.run_simulation_action, self.generate_code_action]:
            action.setEnabled(can_run_matlab)
        self.matlab_settings_action.setEnabled(not self.py_sim_active)

    def _start_matlab_operation(self, operation_name):
        logging.info("MATLAB Op: %s starting...", operation_name)
        if hasattr(self, 'status_label'): self.status_label.setText(f"Running: {operation_name}...")
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False)

    def _finish_matlab_operation(self):
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(False)
        if hasattr(self, 'status_label'): self.status_label.setText("Ready")
        self.set_ui_enabled_for_matlab_op(True)
        logging.info("MATLAB Op: Finished processing.")

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
        logging.log(logging.INFO if success else logging.ERROR, "MATLAB Result: %s", message)
        if success:
            if "Model generation" in message and data: self.last_generated_model_path = data; QMessageBox.information(self, "Simulink Model Generation", f"Model generated: {data}")
            elif "Simulation" in message: QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else: QMessageBox.warning(self, "MATLAB Operation Failed", message)

    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation()
        logging.log(logging.INFO if success else logging.ERROR, "MATLAB Code Gen Result: %s", message)
        if success and output_dir:
            msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Information); msg_box.setWindowTitle("Code Gen Successful")
            msg_box.setTextFormat(Qt.RichText); abs_dir = os.path.abspath(output_dir)
            msg_box.setText(f"Code generation completed.<br>Output: <a href='file:///{abs_dir}'>{abs_dir}</a>")
            msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction)
            open_btn = msg_box.addButton("Open Directory", QMessageBox.ActionRole); msg_box.addButton(QMessageBox.Ok)
            msg_box.exec()
            if msg_box.clickedButton() == open_btn and not QDesktopServices.openUrl(QUrl.fromLocalFile(abs_dir)):
                logging.error("Error opening dir %s", abs_dir); QMessageBox.warning(self, "Error Opening Dir", f"Could not open:\n{abs_dir}")
        elif not success: QMessageBox.warning(self, "Code Gen Failed", message)

    def _prompt_save_if_dirty(self) -> bool:
        if not self.isWindowModified(): return True
        if self.py_sim_active: QMessageBox.warning(self, "Sim Active", "Stop Python sim before save/open."); return False
        reply = QMessageBox.question(self, "Save Changes?", f"'{os.path.basename(self.current_file_path or 'Untitled')}' has unsaved changes. Save?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if reply == QMessageBox.Save: return self.on_save_file()
        return reply != QMessageBox.Cancel

    def on_new_file(self, silent=False):
        if not silent and not self._prompt_save_if_dirty(): return False
        if self.py_sim_ui_manager: self.py_sim_ui_manager.on_stop_py_simulation(silent=True) 
        self.scene.clear(); self.scene.setSceneRect(0,0,6000,4500)
        self.current_file_path = self.last_generated_model_path = None
        self.undo_stack.clear(); self.scene.set_dirty(False); self.setWindowModified(False)
        self._update_window_title(); self._update_undo_redo_actions_enable_state()
        if not silent: logging.info("New diagram created."); self.status_label.setText("New diagram. Ready.")
        self.view.resetTransform(); self.view.centerOn(self.scene.sceneRect().center())
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger()
        return True

    def on_open_file(self):
        if not self._prompt_save_if_dirty(): return
        if self.py_sim_ui_manager: self.py_sim_ui_manager.on_stop_py_simulation(silent=True)
        start_dir = os.path.dirname(self.current_file_path or QDir.homePath())
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)
        if file_path:
            if self._load_from_path(file_path):
                self.current_file_path = file_path; self.last_generated_model_path = None
                self.undo_stack.clear(); self.scene.set_dirty(False); self.setWindowModified(False)
                self._update_window_title(); self._update_undo_redo_actions_enable_state()
                logging.info("Opened: %s", file_path); self.status_label.setText(f"Opened: {os.path.basename(file_path)}")
                bounds = self.scene.itemsBoundingRect()
                if not bounds.isEmpty(): self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else: self.view.resetTransform(); self.view.centerOn(self.scene.sceneRect().center())
            else: QMessageBox.critical(self, "Error Opening", f"Could not load: {file_path}"); logging.error("Failed to open: %s", file_path)

    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data:
                logging.error("Invalid BSM format: %s. Missing keys.", file_path); return False
            self.scene.load_diagram_data(data); return True
        except json.JSONDecodeError as e: logging.error("JSONDecodeError in %s: %s", file_path, e); return False
        except Exception as e: logging.error("Error loading %s: %s", file_path, e, exc_info=True); return False

    def on_save_file(self) -> bool:
        if not self.current_file_path: return self.on_save_file_as()
        return self._save_to_path(self.current_file_path)

    def on_save_file_as(self) -> bool:
        start_path = self.current_file_path or os.path.join(QDir.homePath(), "untitled" + FILE_EXTENSION)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As", start_path, FILE_FILTER)
        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION): file_path += FILE_EXTENSION
            if self._save_to_path(file_path): self.current_file_path = file_path; return True
        return False

    def _save_to_path(self, file_path) -> bool:
        if self.py_sim_active: QMessageBox.warning(self, "Sim Active", "Stop Python sim before saving."); return False
        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            err = save_file.errorString(); logging.error("Save file open error %s: %s", file_path, err)
            QMessageBox.critical(self, "Save Error", f"Failed to open for saving:\n{err}"); return False
        try:
            data = json.dumps(self.scene.get_diagram_data(), indent=4, ensure_ascii=False)
            if save_file.write(data.encode('utf-8')) == -1 or not save_file.commit():
                err = save_file.errorString(); logging.error("Save write/commit error %s: %s", file_path, err)
                QMessageBox.critical(self, "Save Error", f"Failed to write/commit:\n{err}"); save_file.cancelWriting(); return False
            logging.info("Saved: %s", file_path); self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            self.scene.set_dirty(False); self.setWindowModified(False); self._update_window_title(); return True
        except Exception as e:
            logging.error("Save error %s: %s", file_path, e, exc_info=True)
            QMessageBox.critical(self, "Save Error", f"Error during saving:\n{e}"); save_file.cancelWriting(); return False

    def on_select_all(self): self.scene.select_all()
    def on_delete_selected(self): self.scene.delete_selected_items()

    def on_export_simulink(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Not Connected", "Configure MATLAB."); return
        if self.py_sim_active: QMessageBox.warning(self, "PySim Active", "Stop Python sim first."); return
        dialog = QDialog(self); dialog.setWindowTitle("Export to Simulink"); dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp, "->M"))
        layout = QFormLayout(dialog); layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)
        name_base = os.path.splitext(os.path.basename(self.current_file_path or "BSM_Model"))[0]
        name_def = "".join(c if c.isalnum() or c=='_' else '_' for c in name_base); name_def = ("Mdl_" + name_def) if not name_def or not name_def[0].isalpha() else name_def.replace('-','_')
        name_edit = QLineEdit(name_def); layout.addRow("Model Name:", name_edit)
        out_dir_def = os.path.dirname(self.current_file_path or QDir.homePath()); out_dir_edit = QLineEdit(out_dir_def)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw")," Browse..."); browse_btn.clicked.connect(lambda: out_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Output Dir", out_dir_edit.text()) or out_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(out_dir_edit, 1); dir_layout.addWidget(browse_btn); layout.addRow("Output Dir:", dir_layout)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject); layout.addRow(btns); dialog.setMinimumWidth(450)
        if dialog.exec() == QDialog.Accepted:
            model_name, out_dir = name_edit.text().strip(), out_dir_edit.text().strip()
            if not model_name or not out_dir: QMessageBox.warning(self, "Input Error", "Model name & output dir required."); return
            if not model_name[0].isalpha() or not all(c.isalnum() or c=='_' for c in model_name): QMessageBox.warning(self, "Invalid Model Name", "Must start with letter, only alphanumeric/underscores."); return
            try: os.makedirs(out_dir, exist_ok=True)
            except OSError as e: QMessageBox.critical(self, "Dir Error", f"Could not create dir:\n{e}"); return
            if not self.scene.get_diagram_data()['states']: QMessageBox.information(self, "Empty Diagram", "Cannot export: no states."); return
            self._start_matlab_operation(f"Exporting '{model_name}' to Simulink")
            self.matlab_connection.generate_simulink_model(self.scene.get_diagram_data()['states'], self.scene.get_diagram_data()['transitions'], out_dir, model_name)

    def on_run_simulation(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Not Connected", "Configure MATLAB."); return
        if self.py_sim_active: QMessageBox.warning(self, "PySim Active", "Stop Python sim first."); return
        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model", default_dir, "Simulink Models (*.slx);;All (*)")
        if not model_path: return
        self.last_generated_model_path = model_path
        sim_time, ok = QInputDialog.getDouble(self, "Sim Time", "Stop time (s):", 10.0, 0.001, 86400.0, 3)
        if not ok: return
        self._start_matlab_operation(f"Running Simulink sim for '{os.path.basename(model_path)}'")
        self.matlab_connection.run_simulation(model_path, sim_time)

    def on_generate_code(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Not Connected", "Configure MATLAB."); return
        if self.py_sim_active: QMessageBox.warning(self, "PySim Active", "Stop Python sim first."); return
        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model for Code Gen", default_dir, "Simulink Models (*.slx);;All (*)")
        if not model_path: return
        self.last_generated_model_path = model_path
        dialog = QDialog(self); dialog.setWindowTitle("Code Gen Options"); dialog.setWindowIcon(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"))
        layout = QFormLayout(dialog); layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)
        lang_combo = QComboBox(); lang_combo.addItems(["C", "C++"]); lang_combo.setCurrentText("C++"); layout.addRow("Target Language:", lang_combo)
        out_dir_edit = QLineEdit(os.path.dirname(model_path))
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw")," Browse..."); browse_btn.clicked.connect(lambda: out_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Base Output Dir", out_dir_edit.text()) or out_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(out_dir_edit, 1); dir_layout.addWidget(browse_btn); layout.addRow("Base Output Dir:", dir_layout)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject); layout.addRow(btns); dialog.setMinimumWidth(450)
        if dialog.exec() == QDialog.Accepted:
            language, out_dir_base = lang_combo.currentText(), out_dir_edit.text().strip()
            if not out_dir_base: QMessageBox.warning(self, "Input Error", "Base output dir required."); return
            try: os.makedirs(out_dir_base, exist_ok=True)
            except OSError as e: QMessageBox.critical(self, "Dir Error", f"Could not create dir:\n{e}"); return
            self._start_matlab_operation(f"Generating {language} code for '{os.path.basename(model_path)}'")
            self.matlab_connection.generate_code(model_path, language, out_dir_base)

    def _get_bundled_file_path(self, filename: str) -> str | None:
        base_path = sys._MEIPASS if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS') else (os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)))
        for sub in ['', 'docs', 'resources', 'examples']:
            path_check = os.path.join(base_path, sub, filename)
            if os.path.exists(path_check): return path_check
        logger.warning("Bundled file '%s' not found near %s.", filename, base_path); return None

    def _open_example_file(self, filename: str):
        if not self._prompt_save_if_dirty(): return
        example_path = self._get_bundled_file_path(filename)
        if example_path and os.path.exists(example_path):
            if self._load_from_path(example_path):
                self.current_file_path, self.last_generated_model_path = example_path, None
                self.undo_stack.clear(); self.scene.set_dirty(False); self.setWindowModified(False)
                self._update_window_title(); self._update_undo_redo_actions_enable_state()
                logging.info("Opened example: %s", filename); self.status_label.setText(f"Opened example: {filename}")
                bounds = self.scene.itemsBoundingRect()
                if not bounds.isEmpty(): self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else: self.view.resetTransform(); self.view.centerOn(self.scene.sceneRect().center())
            else: QMessageBox.critical(self, "Error Opening Example", f"Could not load: {filename}"); logging.error("Failed to open example: %s", filename)
        else: QMessageBox.warning(self, "Example Not Found", f"'{filename}' not found."); logging.warning("Example '%s' not found at: %s", filename, example_path)

    def on_show_quick_start(self):
        guide_path = self._get_bundled_file_path("QUICK_START.html")
        if guide_path and not QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path)):
            QMessageBox.warning(self, "Could Not Open", f"Failed to open quick start. Path: {guide_path}"); logging.warning("Failed to open quick start: %s", guide_path)
        elif not guide_path: QMessageBox.information(self, "Not Found", "Quick start guide not found.")

    def on_about(self):
        QMessageBox.about(self, f"About {APP_NAME}", f"""<h3 style='color:{COLOR_ACCENT_PRIMARY};'>{APP_NAME} v{APP_VERSION}</h3><p>Graphical FSM tool.</p><ul><li>Visual design & editing.</li><li>Python simulation.</li><li>MATLAB/Simulink integration.</li><li>AI Assistant.</li></ul><p style='font-size:8pt;color:{COLOR_TEXT_SECONDARY};'>For research/education. Verify outputs.</p>""")

    def closeEvent(self, event: QCloseEvent):
        if self.py_sim_ui_manager: self.py_sim_ui_manager.on_stop_py_simulation(silent=True) 
        if self.internet_check_timer and self.internet_check_timer.isActive(): self.internet_check_timer.stop()
        if self.ai_chatbot_manager: self.ai_chatbot_manager.stop_chatbot()

        if self.resource_monitor_worker and self.resource_monitor_thread:
            logger.info("Stopping resource monitor...")
            if self.resource_monitor_thread.isRunning():
                # Ensure stop_monitoring is called in the worker's thread context
                QMetaObject.invokeMethod(self.resource_monitor_worker, "stop_monitoring", Qt.QueuedConnection)
                self.resource_monitor_thread.quit() # Asks the event loop to finish
                # Wait for interval_ms + a small buffer to allow the worker's loop to finish
                wait_time = self.resource_monitor_worker.interval_ms + 200 if self.resource_monitor_worker else 2200 # Default wait time
                if hasattr(self.resource_monitor_worker, 'interval_ms'): # Check if attribute exists
                     wait_time = self.resource_monitor_worker.interval_ms + 200

                if not self.resource_monitor_thread.wait(wait_time): 
                    logger.warning("Resource monitor thread did not quit gracefully. Terminating.")
                    self.resource_monitor_thread.terminate() # Forceful stop
                    self.resource_monitor_thread.wait(100) # Brief wait after terminate
                else:
                    logger.info("Resource monitor thread stopped.")
            self.resource_monitor_worker = None # Help with garbage collection
            self.resource_monitor_thread = None # Help with garbage collection

        if self._prompt_save_if_dirty():
            if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads:
                logging.info("Closing. %d MATLAB processes may persist.", len(self.matlab_connection._active_threads))
            event.accept()
        else:
            event.ignore()
            if self.internet_check_timer: self.internet_check_timer.start()

    def _init_internet_status_check(self):
        self.internet_check_timer.timeout.connect(self._run_internet_check_job)
        self.internet_check_timer.start(15000)
        QTimer.singleShot(100, self._run_internet_check_job)

    def _run_internet_check_job(self):
        current_status, status_detail = False, "Checking..."
        try:
            s = socket.create_connection(("8.8.8.8", 53), timeout=1.5); s.close(); current_status, status_detail = True, "Connected"
        except socket.timeout: status_detail = "Disconnected (Timeout)"
        except (socket.gaierror, OSError): status_detail = "Disconnected (Net Issue)"
        if current_status != self._internet_connected or self._internet_connected is None:
            self._internet_connected = current_status; self._update_internet_status_display(current_status, status_detail)

    def _update_internet_status_display(self, is_connected: bool, message_detail: str):
        full_status = f"Internet: {message_detail}"
        if hasattr(self, 'internet_status_label'):
            self.internet_status_label.setText(full_status)
            host_tip = socket.getfqdn('8.8.8.8') if is_connected else '8.8.8.8'
            self.internet_status_label.setToolTip(f"{full_status} (Checks {host_tip}:53)")
            self.internet_status_label.setStyleSheet(f"padding:0 5px;color:{COLOR_PY_SIM_STATE_ACTIVE.name() if is_connected else '#D32F2F'};")
        logging.debug("Internet Status: %s", message_detail)
        if hasattr(self.ai_chatbot_manager, 'set_online_status'): self.ai_chatbot_manager.set_online_status(is_connected)

    def _update_py_sim_status_display(self):
        if hasattr(self, 'py_sim_status_label'):
            if self.py_sim_active and self.py_fsm_engine:
                state_name = self.py_fsm_engine.get_current_state_name()
                self.py_sim_status_label.setText(f"PySim: Active ({state_name})")
                self.py_sim_status_label.setStyleSheet(f"font-weight:bold;padding:0 5px;color:{COLOR_PY_SIM_STATE_ACTIVE.name()};")
            else:
                self.py_sim_status_label.setText("PySim: Idle")
                self.py_sim_status_label.setStyleSheet("font-weight:normal;padding:0 5px;")

    def _update_py_simulation_actions_enabled_state(self):
        is_matlab_op_running = self.progress_bar.isVisible() if hasattr(self, 'progress_bar') else False
        sim_inactive = not self.py_sim_active 

        self.start_py_sim_action.setEnabled(sim_inactive and not is_matlab_op_running)
        self.stop_py_sim_action.setEnabled(self.py_sim_active and not is_matlab_op_running)
        self.reset_py_sim_action.setEnabled(self.py_sim_active and not is_matlab_op_running)
        
        if self.py_sim_ui_manager:
            self.py_sim_ui_manager._update_internal_controls_enabled_state()


    def log_message(self, level_str: str, message: str):
        level = getattr(logging, level_str.upper(), logging.INFO)
        logger.log(level, message)


if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app_dir = os.path.dirname(os.path.abspath(__file__))
    deps_icons_dir = os.path.join(app_dir, "dependencies", "icons")
    if not os.path.exists(deps_icons_dir):
        try: os.makedirs(deps_icons_dir, exist_ok=True); print(f"Info: Created dir for QSS icons: {deps_icons_dir}")
        except OSError as e: print(f"Warning: Could not create dir {deps_icons_dir}: {e}")

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET_GLOBAL)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())