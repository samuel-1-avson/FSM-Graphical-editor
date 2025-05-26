
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
import psutil
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None # Ensure pynvml is defined even if import fails

logger = logging.getLogger(__name__) # Ensure logger is defined if not already
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
from utils import get_standard_icon

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

            # This was self.original_signal.emit before, should use worker's finished_signal
            # However, the worker is designed to emit finished_signal at the very end.
            # The logic here implies an immediate feedback on the original_signal.
            # Let's assume original_signal is for UI updates that can happen before worker truly finishes.
            # For clarity, let's keep the original_signal emit here, but ensure finished_signal is also emitted in finally.
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
            # Ensure finished_signal is emitted once at the very end of processing
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
        self.matlab_path = path.strip() if path else ""
        if self.matlab_path and os.path.exists(self.matlab_path) and \
           (os.access(self.matlab_path, os.X_OK) or self.matlab_path.lower().endswith('.exe')):
            self.connected = True # Assume connectable, test_connection will confirm
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
        
        if not self.connected: # If path was set but not tested yet, or test failed previously
            if not self.set_matlab_path(self.matlab_path): 
                return False # set_matlab_path emits status

        try:
            # -batch option is crucial for non-interactive execution
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
            paths_to_check.append('matlab') # Check if 'matlab' is in PATH

        for path_candidate in paths_to_check:
            logger.debug(f"Auto-detect: Checking MATLAB candidate path: {path_candidate}")
            if path_candidate == 'matlab' and sys.platform != 'win32': # For 'matlab' in PATH on non-Windows
                try: 
                    # A lightweight test to see if 'matlab' command runs
                    test_process = subprocess.run([path_candidate, "-batch", "exit"], timeout=5, capture_output=True, check=False)
                    if test_process.returncode == 0:
                        logger.info(f"Auto-detect: Found MATLAB in PATH: {path_candidate}")
                        if self.set_matlab_path(path_candidate): return True
                except (FileNotFoundError, subprocess.TimeoutExpired): 
                    logger.debug(f"Auto-detect: 'matlab' in PATH check failed or timed out for {path_candidate}")
                    continue
            elif os.path.exists(path_candidate) and os.access(path_candidate, os.X_OK): 
                logger.info(f"Auto-detect: Found MATLAB at: {path_candidate}")
                if self.set_matlab_path(path_candidate): return True # set_matlab_path emits status

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

        # Pass the actual signal instance, not its name as a string
        worker = MatlabCommandWorker(self.matlab_path, script_file_path, worker_signal, success_message_prefix, model_name_for_context)
        thread = QThread()
        worker.moveToThread(thread)

        thread.started.connect(worker.run_command)
        # Connect the worker's finished_signal to clean up the thread
        worker.finished_signal.connect(thread.quit) 
        worker.finished_signal.connect(worker.deleteLater) 
        thread.finished.connect(thread.deleteLater) 

        self._active_threads.append(thread)
        thread.finished.connect(lambda t=thread: self._active_threads.remove(t) if t in self._active_threads else None)

        thread.start()

    def generate_simulink_model(self, states, transitions, output_dir, model_name="BrainStateMachine"):
        if not self.connected:
            # Use the correct signal for this operation
            self.simulationFinished.emit(False, "MATLAB not connected.", "") # Changed from codeGenerationFinished
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


class ResourceMonitorWorker(QObject):
    resourceUpdate = pyqtSignal(float, float, float, str) # cpu, ram, gpu_util, gpu_name
    
    



# MainWindow Class
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_file_path = None
        self.last_generated_model_path = None # To remember the last SLX for sim/codegen
        self.matlab_connection = MatlabConnection()
        self.undo_stack = QUndoStack(self)

        # AI Chatbot Manager Initialization
        self.ai_chatbot_manager = AIChatbotManager(self) # Pass self (MainWindow) as parent
        
        # Scene Initialization (Undo stack and parent window reference for logging/dialogs)
        self.scene = DiagramScene(self.undo_stack, self) # Pass self as parent_window

        self.scene.modifiedStatusChanged.connect(self.setWindowModified)
        self.scene.modifiedStatusChanged.connect(self._update_window_title)

        # Python FSM Simulation
        self.py_fsm_engine: FSMSimulator | None = None
        self.py_sim_active = False # Tracks if Python sim is active

        # UI Managers
        self.py_sim_ui_manager = PySimulationUIManager(self) # Manages Python Sim Dock UI
        self.ai_chat_ui_manager = AIChatUIManager(self)   # Manages AI Chat Dock UI

        # Connect signals from PySimulationUIManager
        self.py_sim_ui_manager.simulationStateChanged.connect(self._handle_py_sim_state_changed_by_manager)
        self.py_sim_ui_manager.requestGlobalUIEnable.connect(self._handle_py_sim_global_ui_enable_by_manager)


        # Internet Status
        self._internet_connected: bool | None = None # Tri-state: None (unknown), True, False
        self.internet_check_timer = QTimer(self)
        
        # Resource Monitor
        self.resource_monitor_worker: ResourceMonitorWorker | None = None
        self.resource_monitor_thread: QThread | None = None

        self.init_ui() # Must be before setup_global_logging if log_widget is part of init_ui

        # Setup logging (assuming self.log_output is created in init_ui)
        try:
            setup_global_logging(self.log_output) 
            logger.info("Main window initialized and logging configured.")
        except Exception as e: # Catch if self.log_output isn't ready
            logger.error(f"Failed to run setup_global_logging: {e}. UI logs might not work.")
            # Fallback basic logging if UI widget isn't ready
            if not logging.getLogger().hasHandlers():
                 logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


        self._init_resource_monitor()

        # Object names for QSS styling
        if hasattr(self, 'matlab_status_label'): self.matlab_status_label.setObjectName("MatlabStatusLabel")
        if hasattr(self, 'py_sim_status_label'): self.py_sim_status_label.setObjectName("PySimStatusLabel")
        if hasattr(self, 'internet_status_label'): self.internet_status_label.setObjectName("InternetStatusLabel")
        if hasattr(self, 'status_label'): self.status_label.setObjectName("StatusLabel")


        # Initial status updates
        self._update_matlab_status_display(False, "Initializing. Configure MATLAB settings or attempt auto-detect.")
        self._update_py_sim_status_display() # Will show "PySim: Idle"

        # Connect MATLAB signals
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)
        
        # Final UI setup
        self._update_window_title()
        self.on_new_file(silent=True) # Start with a clean, untitled diagram
        self._init_internet_status_check()
        self.scene.selectionChanged.connect(self._update_properties_dock)
        self._update_properties_dock() # Initial state of properties dock
        self._update_py_simulation_actions_enabled_state() # Initial state of PySim buttons

        # Initial AI Chat status based on API key presence
        if not self.ai_chatbot_manager.api_key:
            self.ai_chat_ui_manager.update_status_display("Status: API Key required. Configure in Settings.")
        else:
            self.ai_chat_ui_manager.update_status_display("Status: Ready.")


    def init_ui(self):
        self.setGeometry(50, 50, 1650, 1050) # Adjusted default size
        self.setWindowIcon(get_standard_icon(QStyle.SP_DesktopIcon, "BSM")) # Main app icon
        self._create_central_widget()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_docks() # Creates self.log_output here
        self._create_status_bar()
        self._update_save_actions_enable_state()
        self._update_matlab_actions_enabled_state()
        self._update_undo_redo_actions_enable_state()
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger() # Default to select mode


    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self)
        self.view.setObjectName("MainDiagramView") # For QSS if needed
        self.setCentralWidget(self.view)

    def _create_actions(self):
        # Helper to safely get QStyle enum values, useful if some are platform-specific
        def _safe_get_style_enum(attr_name, fallback_attr_name=None):
            try: return getattr(QStyle, attr_name)
            except AttributeError:
                if fallback_attr_name:
                    try: return getattr(QStyle, fallback_attr_name)
                    except AttributeError: pass
                return QStyle.SP_CustomBase # A generic fallback

        # File Actions
        self.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "New"), "&New", self, shortcut=QKeySequence.New, statusTip="Create a new file", triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "Opn"), "&Open...", self, shortcut=QKeySequence.Open, statusTip="Open an existing file", triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Sav"), "&Save", self, shortcut=QKeySequence.Save, statusTip="Save the current file", triggered=self.on_save_file)
        self.save_as_action = QAction(
            get_standard_icon(_safe_get_style_enum("SP_DriveHDIcon", "SP_DialogSaveButton"), "SA"), # Fallback for SP_DriveHDIcon
            "Save &As...", self, shortcut=QKeySequence.SaveAs,
            statusTip="Save the current file with a new name", triggered=self.on_save_file_as
        )
        self.export_simulink_action = QAction(get_standard_icon(_safe_get_style_enum("SP_ArrowUp","SP_ArrowRight"), "->M"), "&Export to Simulink...", self, triggered=self.on_export_simulink)
        self.exit_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", self, shortcut=QKeySequence.Quit, statusTip="Exit the application", triggered=self.close)

        # Edit Actions
        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "Un"))
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "Re"))
        # Connect canUndoChanged/canRedoChanged to update action enabled state
        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.undo_stack.canRedoChanged.connect(self._update_undo_redo_actions_enable_state)

        self.select_all_action = QAction(get_standard_icon(_safe_get_style_enum("SP_FileDialogListView", "SP_FileDialogDetailedView"), "All"), "Select &All", self, shortcut=QKeySequence.SelectAll, triggered=self.on_select_all)
        self.delete_action = QAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "&Delete", self, shortcut=QKeySequence.Delete, triggered=self.on_delete_selected)

        # Mode Actions
        self.mode_action_group = QActionGroup(self)
        self.mode_action_group.setExclusive(True)
        self.select_mode_action = QAction(QIcon.fromTheme("edit-select", get_standard_icon(QStyle.SP_ArrowRight, "Sel")), "Select/Move", self, checkable=True, triggered=lambda: self.scene.set_mode("select"))
        self.select_mode_action.setObjectName("select_mode_action") # For QSS or direct access
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", get_standard_icon(QStyle.SP_FileDialogNewFolder, "St")), "Add State", self, checkable=True, triggered=lambda: self.scene.set_mode("state"))
        self.add_state_mode_action.setObjectName("add_state_mode_action")
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", get_standard_icon(QStyle.SP_ArrowForward, "Tr")), "Add Transition", self, checkable=True, triggered=lambda: self.scene.set_mode("transition"))
        self.add_transition_mode_action.setObjectName("add_transition_mode_action")
        self.add_comment_mode_action = QAction(QIcon.fromTheme("insert-text", get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm")), "Add Comment", self, checkable=True, triggered=lambda: self.scene.set_mode("comment"))
        self.add_comment_mode_action.setObjectName("add_comment_mode_action")
        for action in [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action]:
            self.mode_action_group.addAction(action)
        self.select_mode_action.setChecked(True) # Default mode

        # MATLAB Simulation/Codegen Actions
        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation (MATLAB)...", self, triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"), "Generate &Code (C/C++ via MATLAB)...", self, triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"), "&MATLAB Settings...", self, triggered=self.on_matlab_settings)

        # Python Simulation Actions (connections handled by PySimulationUIManager)
        self.start_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Py▶"), "&Start Python Simulation", self, statusTip="Start internal FSM simulation")
        self.stop_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaStop, "Py■"), "S&top Python Simulation", self, statusTip="Stop internal FSM simulation", enabled=False)
        self.reset_py_sim_action = QAction(get_standard_icon(QStyle.SP_MediaSkipBackward, "Py«"), "&Reset Python Simulation", self, statusTip="Reset internal FSM simulation", enabled=False)

        # AI Chatbot Actions (connections handled by AIChatUIManager)
        self.openai_settings_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "AISet"), "AI Assistant Settings...", self)
        # The connection for openai_settings_action is now done in AIChatUIManager's constructor
        self.clear_ai_chat_action = QAction(get_standard_icon(QStyle.SP_DialogResetButton, "Clear"), "Clear Chat History", self)
        self.ask_ai_to_generate_fsm_action = QAction(QIcon.fromTheme("system-run", get_standard_icon(QStyle.SP_DialogYesButton, "AIGen")), "Generate FSM from Description...", self)


        # Help Actions
        self.open_example_menu_action = QAction("Open E&xample...", self) # Placeholder, submenu created in _create_menus
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
        # Add more examples here if needed
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
        py_sim_menu.addAction(self.start_py_sim_action) # Connected in PySimUIManager
        py_sim_menu.addAction(self.stop_py_sim_action)  # Connected in PySimUIManager
        py_sim_menu.addAction(self.reset_py_sim_action) # Connected in PySimUIManager
        sim_menu.addSeparator()
        matlab_sim_menu = sim_menu.addMenu(get_standard_icon(QStyle.SP_ComputerIcon, "M"), "MATLAB/Simulink")
        matlab_sim_menu.addAction(self.run_simulation_action)
        matlab_sim_menu.addAction(self.generate_code_action)
        matlab_sim_menu.addSeparator()
        matlab_sim_menu.addAction(self.matlab_settings_action)

        self.view_menu = menu_bar.addMenu("&View") # Docks will add their actions here

        ai_menu = menu_bar.addMenu("&AI Assistant")
        ai_menu.addAction(self.ask_ai_to_generate_fsm_action) # Connected in AIChatUIManager
        ai_menu.addAction(self.clear_ai_chat_action)         # Connected in AIChatUIManager
        ai_menu.addSeparator()
        ai_menu.addAction(self.openai_settings_action)      # Connected in AIChatUIManager

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.quick_start_action)
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(22,22) # Standard icon size for toolbars
        tb_style = Qt.ToolButtonTextBesideIcon # Or Qt.ToolButtonIconOnly

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
        tools_widget_main.setObjectName("ToolsDockWidgetContents") # For QSS
        tools_main_layout = QVBoxLayout(tools_widget_main)
        tools_main_layout.setSpacing(10); tools_main_layout.setContentsMargins(5,5,5,5)
        mode_group_box = QGroupBox("Interaction Modes")
        mode_layout = QVBoxLayout(); mode_layout.setSpacing(5)
        # Create QToolButtons and assign actions to them
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
        drag_initial_state_btn.setIcon(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "ISt")) # Example icon
        drag_final_state_btn = DraggableToolButton(" Final State", "application/x-bsm-tool", "Final State")
        drag_final_state_btn.setIcon(get_standard_icon(QStyle.SP_DialogOkButton, "FSt")) # Example icon
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
        properties_layout.addWidget(self.properties_editor_label, 1) # Make label expand
        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"),"Edit Properties")
        self.properties_edit_button.setEnabled(False) # Initially disabled
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
        self.log_output = QTextEdit() # This is where logs will go
        self.log_output.setObjectName("LogOutputWidget") # For QSS styling
        self.log_output.setReadOnly(True)
        # self.log_output.setFont(QFont("Consolas", 9)) # Example monospace font
        log_layout.addWidget(self.log_output)
        self.log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.log_dock.toggleViewAction())

        # Python Simulation Dock (content created by PySimulationUIManager)
        self.py_sim_dock = QDockWidget("Python Simulation", self)
        self.py_sim_dock.setObjectName("PySimDock")
        self.py_sim_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        py_sim_contents_widget = self.py_sim_ui_manager.create_dock_widget_contents()
        self.py_sim_dock.setWidget(py_sim_contents_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.py_sim_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.py_sim_dock.toggleViewAction())

        # AI Chatbot Dock (content created by AIChatUIManager)
        self.ai_chatbot_dock = QDockWidget("AI Chatbot", self)
        self.ai_chatbot_dock.setObjectName("AIChatbotDock")
        self.ai_chatbot_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        ai_chat_contents_widget = self.ai_chat_ui_manager.create_dock_widget_contents()
        self.ai_chatbot_dock.setWidget(ai_chat_contents_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chatbot_dock)
        if hasattr(self, 'view_menu'): self.view_menu.addAction(self.ai_chatbot_dock.toggleViewAction())

        # Tabify docks for better layout management
        self.tabifyDockWidget(self.properties_dock, self.ai_chatbot_dock)
        self.tabifyDockWidget(self.ai_chatbot_dock, self.py_sim_dock)


    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1) # Main status, stretchable

        # Resource monitors (permanent widgets)
        self.cpu_status_label = QLabel("CPU: --%"); self.cpu_status_label.setToolTip("CPU Usage"); self.cpu_status_label.setMinimumWidth(90); self.cpu_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.cpu_status_label)
        self.ram_status_label = QLabel("RAM: --%"); self.ram_status_label.setToolTip("RAM Usage"); self.ram_status_label.setMinimumWidth(90); self.ram_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.ram_status_label)
        self.gpu_status_label = QLabel("GPU: N/A"); self.gpu_status_label.setToolTip("GPU Usage (NVIDIA only, if pynvml installed)"); self.gpu_status_label.setMinimumWidth(130); self.gpu_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.gpu_status_label)

        # Specific status labels
        self.py_sim_status_label = QLabel("PySim: Idle"); self.py_sim_status_label.setToolTip("Internal Python FSM Simulation Status."); self.py_sim_status_label.setMinimumWidth(100); self.py_sim_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.py_sim_status_label)
        self.matlab_status_label = QLabel("MATLAB: Initializing..."); self.matlab_status_label.setToolTip("MATLAB connection status."); self.matlab_status_label.setMinimumWidth(150); self.matlab_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.matlab_status_label)
        self.internet_status_label = QLabel("Internet: Init..."); self.internet_status_label.setToolTip("Internet connectivity. Checks periodically."); self.internet_status_label.setMinimumWidth(120); self.internet_status_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.internet_status_label)

        self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0,0); self.progress_bar.setVisible(False); self.progress_bar.setMaximumWidth(150); self.progress_bar.setTextVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _init_resource_monitor(self):
        self.resource_monitor_thread = QThread(self) # Parent to main window
        self.resource_monitor_worker = ResourceMonitorWorker(interval_ms=2000)
        self.resource_monitor_worker.moveToThread(self.resource_monitor_thread)

        self.resource_monitor_worker.resourceUpdate.connect(self._update_resource_display)
        self.resource_monitor_thread.started.connect(self.resource_monitor_worker.start_monitoring)
        # Ensure proper cleanup
        self.resource_monitor_thread.finished.connect(self.resource_monitor_worker.deleteLater)
        self.resource_monitor_thread.finished.connect(self.resource_monitor_thread.deleteLater) # Important for QThread cleanup
        self.resource_monitor_thread.start()
        logger.info("Resource monitor thread initialized and started.")

    @pyqtSlot(float, float, float, str)
    def _update_resource_display(self, cpu_usage, ram_usage, gpu_util, gpu_name):
        if hasattr(self, 'cpu_status_label'): self.cpu_status_label.setText(f"CPU: {cpu_usage:.1f}%")
        if hasattr(self, 'ram_status_label'): self.ram_status_label.setText(f"RAM: {ram_usage:.1f}%")
        if hasattr(self, 'gpu_status_label'):
            if gpu_util == -1.0: self.gpu_status_label.setText(f"GPU: {gpu_name}") # N/A or NVML not init
            elif gpu_util == -2.0: self.gpu_status_label.setText(f"GPU: {gpu_name}") # Error polling
            else: self.gpu_status_label.setText(f"GPU: {gpu_util:.0f}% ({gpu_name})")
    
    @pyqtSlot(bool)
    def _handle_py_sim_state_changed_by_manager(self, is_running: bool):
        logger.debug(f"MW: PySim state changed by manager to: {is_running}")
        self.py_sim_active = is_running # Update MainWindow's tracking flag
        self._update_window_title()
        self._update_py_sim_status_display() # Update status bar text
        self._update_matlab_actions_enabled_state() # MATLAB actions might depend on PySim state
        self._update_py_simulation_actions_enabled_state() # Update PySim related actions in main window

    @pyqtSlot(bool)
    def _handle_py_sim_global_ui_enable_by_manager(self, enable: bool):
        logger.debug(f"MW: Global UI enable requested by PySim manager: {enable}")
        is_editable = enable # If True, UI is editable; if False, it's view-only

        # Actions that modify the diagram
        diagram_editing_actions = [
            self.new_action, self.open_action, self.save_action, self.save_as_action,
            self.undo_action, self.redo_action, self.delete_action, self.select_all_action,
            self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action
            # Potentially export_simulink_action too if it shouldn't run during PySim
        ]
        for action in diagram_editing_actions:
            if hasattr(action, 'setEnabled'): action.setEnabled(is_editable)

        # Enable/disable docks or their contents
        if hasattr(self, 'tools_dock'): self.tools_dock.setEnabled(is_editable)
        # Properties edit button depends on both global editability and item selection
        if hasattr(self, 'properties_edit_button'):
             self.properties_edit_button.setEnabled(is_editable and len(self.scene.selectedItems())==1)
        
        # Make scene items non-movable if UI is not editable
        for item in self.scene.items(): 
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)): # Transitions are not user-movable directly
                item.setFlag(QGraphicsItem.ItemIsMovable, is_editable and self.scene.current_mode == "select")
        
        # If UI is disabled and not in select mode, switch to select mode
        if not is_editable and self.scene.current_mode != "select":
            self.scene.set_mode("select") # This will also update mode buttons if connected
        
        self._update_matlab_actions_enabled_state() # Re-evaluate MATLAB actions
        self._update_py_simulation_actions_enabled_state() # Re-evaluate PySim specific actions


    def _add_fsm_data_to_scene(self, fsm_data: dict, clear_current_diagram: bool = False, original_user_prompt: str = "AI Generated FSM"):
        logger.info("MW: ADD_FSM_TO_SCENE clear_current_diagram=%s", clear_current_diagram)
        logger.debug("MW: Received FSM Data (states: %d, transitions: %d)",
                     len(fsm_data.get('states',[])), len(fsm_data.get('transitions',[])))

        if clear_current_diagram:
            if not self.on_new_file(silent=True): # This will stop PySim if active and prompt for save
                 logger.warning("MW: Clearing diagram cancelled by user (save prompt). Cannot add AI FSM.")
                 return # User cancelled the "New File" operation
            logger.info("MW: Cleared diagram before AI generation.")

        # If we are not clearing, start an undo macro for adding multiple items
        if not clear_current_diagram:
            self.undo_stack.beginMacro(f"Add AI FSM: {original_user_prompt[:30]}...")

        state_items_map = {} # To link transitions
        items_to_add_for_undo_command = [] # Collect items for a single AddItemCommand if not clearing

        # Basic layout parameters
        layout_start_x, layout_start_y = 100, 100
        default_item_width, default_item_height = 120, 60
        GV_SCALE = 1.2 # Scale factor for Graphviz coordinates

        # Use pygraphviz for layout
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
                min_x_gv = min(p['x'] for p in raw_gv_pos); max_y_gv = max(p['y'] for p in raw_gv_pos) # GV y is often inverted
                for p_gv in raw_gv_pos: graphviz_positions[p_gv['name']] = QPointF((p_gv['x'] - min_x_gv) * GV_SCALE + layout_start_x, (max_y_gv - p_gv['y']) * GV_SCALE + layout_start_y)
            else: logger.warning("MW: Graphviz - No valid positions extracted for AI FSM nodes.")
        except Exception as e:
            logger.error("MW: Graphviz layout error for AI FSM: %s. Falling back to grid.", str(e).strip() or "Unknown", exc_info=True)
            if hasattr(self, 'ai_chat_ui_manager') and self.ai_chat_ui_manager: # Check if manager exists
                self.ai_chat_ui_manager._append_to_chat_display("System", f"Warning: AI FSM layout failed (Graphviz error). Using basic grid layout.")
            graphviz_positions = {} # Ensure it's empty on error

        # Create and add states
        for i, state_data in enumerate(fsm_data.get('states', [])):
            name = state_data.get('name'); item_w, item_h = default_item_width, default_item_height
            if not name: logger.warning("MW: AI State data missing 'name'. Skipping."); continue
            pos = graphviz_positions.get(name)
            pos_x, pos_y = (pos.x(), pos.y()) if pos else (layout_start_x + (i % 3) * (item_w + 150), layout_start_y + (i // 3) * (item_h + 100)) # Fallback grid
            try:
                state_item = GraphicsStateItem(pos_x, pos_y, item_w, item_h, name,
                    is_initial=state_data.get('is_initial', False), is_final=state_data.get('is_final', False),
                    color=state_data.get('properties', {}).get('color', state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG)),
                    entry_action=state_data.get('entry_action', ""), during_action=state_data.get('during_action', ""), exit_action=state_data.get('exit_action', ""),
                    description=state_data.get('description', fsm_data.get('description', "") if i==0 else ""), # Use FSM desc for first state
                    is_superstate=state_data.get('is_superstate', False), sub_fsm_data=state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}))
                items_to_add_for_undo_command.append(state_item); state_items_map[name] = state_item
            except Exception as e: logger.error("MW: Error creating AI GraphicsStateItem '%s': %s", name, e, exc_info=True)

        # Create and add transitions
        for trans_data in fsm_data.get('transitions', []):
            src_name, tgt_name = trans_data.get('source'), trans_data.get('target')
            if not src_name or not tgt_name: logger.warning("MW: AI Transition missing source/target. Skipping."); continue
            src_item, tgt_item = state_items_map.get(src_name), state_items_map.get(tgt_name)
            if src_item and tgt_item:
                try:
                    trans_item = GraphicsTransitionItem(src_item, tgt_item,
                        event_str=trans_data.get('event', ""), condition_str=trans_data.get('condition', ""), action_str=trans_data.get('action', ""),
                        color=trans_data.get('properties', {}).get('color', trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT)), description=trans_data.get('description', ""))
                    # Handle control_offset if present in AI data
                    ox, oy = trans_data.get('control_offset_x'), trans_data.get('control_offset_y')
                    if ox is not None and oy is not None:
                        try: trans_item.set_control_point_offset(QPointF(float(ox), float(oy)))
                        except ValueError: logger.warning("MW: Invalid AI control offsets for transition %s->%s.", src_name, tgt_name)
                    items_to_add_for_undo_command.append(trans_item)
                except Exception as e: logger.error("MW: Error creating AI GraphicsTransitionItem %s->%s: %s", src_name, tgt_name, e, exc_info=True)
            else: logger.warning("MW: Could not find source/target GraphicsStateItem for AI transition: %s->%s. Skipping.", src_name, tgt_name)
        
        # Create and add comments (positioning might need refinement)
        max_y_items = max((item.scenePos().y() + item.boundingRect().height() for item in state_items_map.values() if item.scenePos()), default=layout_start_y) if state_items_map else layout_start_y
        for i, comment_data in enumerate(fsm_data.get('comments', [])):
            text = comment_data.get('text'); width = comment_data.get('width')
            if not text: continue
            # Basic fallback positioning for comments if 'x' or 'y' not provided by AI
            pos_x = comment_data.get('x', layout_start_x + i * (150 + 20)) # Simple horizontal spread
            pos_y = comment_data.get('y', max_y_items + 100) # Below states
            try:
                comment_item = GraphicsCommentItem(pos_x, pos_y, text)
                if width:
                    try: comment_item.setTextWidth(float(width))
                    except ValueError: logger.warning("MW: Invalid AI width for comment.")
                items_to_add_for_undo_command.append(comment_item)
            except Exception as e: logger.error("MW: Error creating AI GraphicsCommentItem: %s", e, exc_info=True)


        if items_to_add_for_undo_command:
            # If clearing, we don't use a single AddItemCommand for multiple items in this simplified undo example.
            # Instead, load_diagram_data (called by on_new_file) clears the undo stack.
            # If not clearing, we wrap the additions in an AddItemCommand or a macro.
            # For simplicity here, let's assume AddItemCommand can handle a list (it doesn't, fix this if needed)
            # Or better: iterate and push individual AddItemCommands if not clearing.
            if not clear_current_diagram:
                for item_to_add in items_to_add_for_undo_command:
                    item_type_name = type(item_to_add).__name__.replace("Graphics","").replace("Item","")
                    cmd_text = f"Add AI {item_type_name}" + (f": {item_to_add.text_label}" if hasattr(item_to_add, 'text_label') and item_to_add.text_label else "")
                    self.undo_stack.push(AddItemCommand(self.scene, item_to_add, cmd_text))
            else: # If cleared, items are added directly without undo for this specific load.
                for item_to_add in items_to_add_for_undo_command:
                     self.scene.addItem(item_to_add)

            logger.info("MW: Added %d AI-generated items to diagram.", len(items_to_add_for_undo_command))
            self.scene.set_dirty(True) # Mark as modified
            # Schedule fitInView after items are processed by the event loop
            QTimer.singleShot(100, self._fit_view_to_new_ai_items)
        else:
            logger.info("MW: No valid AI-generated items to add.")

        if not clear_current_diagram and items_to_add_for_undo_command: # Only end macro if started
            self.undo_stack.endMacro()
        elif not clear_current_diagram: # Ensure macro is ended even if no items were added
             self.undo_stack.endMacro() 


        # If Python simulation was active, re-initialize it with the new diagram
        if self.py_sim_active and items_to_add_for_undo_command: # Check MainWindow's py_sim_active
            logger.info("MW: Reinitializing Python simulation after adding AI FSM.")
            try:
                # self.py_fsm_engine should be updated by the UI manager's start
                if self.py_sim_ui_manager:
                    self.py_sim_ui_manager.on_stop_py_simulation(silent=True) # Stop first
                    self.py_sim_ui_manager.on_start_py_simulation() # Start with new data
                    self.py_sim_ui_manager.append_to_action_log(["Python FSM Simulation reinitialized for new diagram from AI."])
                    # update_dock_ui_contents will be called by on_start_py_simulation
            except FSMError as e:
                if self.py_sim_ui_manager:
                    self.py_sim_ui_manager.append_to_action_log([f"ERROR Re-initializing Sim after AI: {e}"])
                    self.py_sim_ui_manager.on_stop_py_simulation(silent=True) # Ensure it's stopped on error
        logger.debug("MW: ADD_FSM_TO_SCENE processing finished. Items involved: %d", len(items_to_add_for_undo_command))


    def _fit_view_to_new_ai_items(self):
        if not self.scene.items(): return
        items_bounds = self.scene.itemsBoundingRect()
        if self.view and not items_bounds.isNull():
            # Add some padding around the items
            self.view.fitInView(items_bounds.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)
            logger.info("MW: View adjusted to AI generated items.")
        elif self.view and self.scene.sceneRect(): # Fallback to scene rect if no items somehow
            self.view.centerOn(self.scene.sceneRect().center())


    def on_matlab_settings(self):
        # This dialog interacts with self.matlab_connection
        dialog = MatlabSettingsDialog(matlab_connection=self.matlab_connection, parent=self)
        dialog.exec() # exec_ for older Qt versions, exec for Qt5+
        # Status is updated via signals from MatlabConnection
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

            # Helper for formatting text, limiting length, and escaping HTML
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
                item_type_name = "Unknown" # Fallback
            
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
        else: # No items selected
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
        sim_status_suffix = " [PySim Running]" if self.py_sim_active else ""
        title = f"{APP_NAME} - {file_name}{sim_status_suffix}"
        self.setWindowTitle(title + "[*]") # [*] indicates modified status for QMainWindow
        if hasattr(self, 'status_label'): # Check if status_label is initialized
            self.status_label.setText(f"File: {file_name}{' *' if self.isWindowModified() else ''} | PySim: {'Active' if self.py_sim_active else 'Idle'}")

    def _update_save_actions_enable_state(self):
        # Save action is enabled if the window is modified (has unsaved changes)
        self.save_action.setEnabled(self.isWindowModified())
        # Save As is always enabled as long as there's content (or even if not, to save an empty file)
        # self.save_as_action.setEnabled(True) # Generally always enabled

    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo())
        self.redo_action.setEnabled(self.undo_stack.canRedo())
        # Optionally update text to show what will be undone/redone
        self.undo_action.setText(f"&Undo {self.undo_stack.undoText()}" if self.undo_stack.undoText() else "&Undo")
        self.redo_action.setText(f"&Redo {self.undo_stack.redoText()}" if self.undo_stack.redoText() else "&Redo")

    def _update_matlab_status_display(self, connected, message):
        text_color = COLOR_PY_SIM_STATE_ACTIVE.name() if connected else "#C62828" # Green for connected, Red for not
        status_text = f"MATLAB: {'Connected' if connected else 'Not Connected'}"
        tooltip_text = f"MATLAB Status: {message}"

        if hasattr(self, 'matlab_status_label'):
            self.matlab_status_label.setText(status_text)
            self.matlab_status_label.setToolTip(tooltip_text)
            self.matlab_status_label.setStyleSheet(f"font-weight:bold;padding:0 5px;color:{text_color};")
        
        # Log significant status changes, but not minor updates like "Initializing" repeatedly
        if "Initializing" not in message or (connected and "Initializing" in message): # Log if connected or if error message
            logging.info("MATLAB Connection Status: %s", message)
        
        self._update_matlab_actions_enabled_state()


    def _update_matlab_actions_enabled_state(self):
        # MATLAB operations should be disabled if PySim is active or MATLAB isn't connected
        can_run_matlab_ops = self.matlab_connection.connected and not self.py_sim_active
        
        if hasattr(self, 'export_simulink_action'): self.export_simulink_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'run_simulation_action'): self.run_simulation_action.setEnabled(can_run_matlab_ops)
        if hasattr(self, 'generate_code_action'): self.generate_code_action.setEnabled(can_run_matlab_ops)
        # MATLAB settings can be accessed even if not connected, but not if PySim is running
        if hasattr(self, 'matlab_settings_action'): self.matlab_settings_action.setEnabled(not self.py_sim_active)

    def _start_matlab_operation(self, operation_name):
        logging.info("MATLAB Operation: '%s' starting...", operation_name)
        if hasattr(self, 'status_label'): self.status_label.setText(f"Running MATLAB: {operation_name}...")
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False)

    def _finish_matlab_operation(self):
        if hasattr(self, 'progress_bar'): self.progress_bar.setVisible(False)
        if hasattr(self, 'status_label'): self.status_label.setText("Ready") # Reset main status
        self.set_ui_enabled_for_matlab_op(True)
        logging.info("MATLAB Operation: Finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        # Disable/Enable UI elements that could interfere with a MATLAB operation
        if hasattr(self, 'menuBar'): self.menuBar().setEnabled(enabled)
        for child in self.findChildren(QToolBar): # All toolbars
            child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled) # The view
        
        # Docks might need specific handling depending on their content
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock"]:
            dock = self.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(enabled) # Or dock.widget().setEnabled(enabled)
        
        self._update_py_simulation_actions_enabled_state() # PySim actions should also be disabled


    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation() # Re-enable UI
        logging.log(logging.INFO if success else logging.ERROR, "MATLAB Result (ModelGen/Sim): %s", message)
        if success:
            if "Model generation" in message and data: # data is the model_path
                self.last_generated_model_path = data
                QMessageBox.information(self, "Simulink Model Generation", f"Model generated successfully:\n{data}")
            elif "Simulation" in message: # data might be sim output summary or empty
                QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else:
            QMessageBox.warning(self, "MATLAB Operation Failed", message)

    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation() # Re-enable UI
        logging.log(logging.INFO if success else logging.ERROR, "MATLAB Code Gen Result: %s", message)
        if success and output_dir:
            msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Information); msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText); abs_dir = os.path.abspath(output_dir)
            msg_box.setText(f"Code generation completed successfully.<br>Generated files are in: <a href='file:///{abs_dir}'>{abs_dir}</a>")
            msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction) # Allow clicking link
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
        if self.py_sim_active: # Don't allow save/open if sim is active without stopping it first
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving or opening a new file.")
            return False

        file_desc = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes?",
                                     f"The diagram '{file_desc}' has unsaved changes. Do you want to save them?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Save) # Default to Save

        if reply == QMessageBox.Save:
            return self.on_save_file() # on_save_file returns True on success
        elif reply == QMessageBox.Cancel:
            return False
        return True # Discard implies proceeding with the action

    def on_new_file(self, silent=False):
        if not silent and not self._prompt_save_if_dirty():
            return False # User cancelled
        
        # Stop Python simulation if active
        if self.py_sim_ui_manager: # Check if manager exists
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True) # Stop silently
        
        self.scene.clear()
        self.scene.setSceneRect(0,0,6000,4500) # Reset scene rect
        self.current_file_path = None
        self.last_generated_model_path = None # Reset this too
        self.undo_stack.clear()
        self.scene.set_dirty(False) # Should be clean after new
        self.setWindowModified(False) # Explicitly set for QMainWindow
        self._update_window_title()
        self._update_undo_redo_actions_enable_state()
        if not silent:
            logging.info("New diagram created.")
            if hasattr(self, 'status_label'): self.status_label.setText("New diagram. Ready.")
        self.view.resetTransform() # Reset zoom/pan
        self.view.centerOn(self.scene.sceneRect().center())
        if hasattr(self, 'select_mode_action'): self.select_mode_action.trigger() # Default to select mode
        return True


    def on_open_file(self):
        if not self._prompt_save_if_dirty():
            return # User cancelled
        if self.py_sim_ui_manager: # Stop sim before opening
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)

        if file_path:
            if self._load_from_path(file_path):
                self.current_file_path = file_path
                self.last_generated_model_path = None # Reset for new file
                self.undo_stack.clear() # Clear undo for new file
                self.scene.set_dirty(False)
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                logging.info("Opened file: %s", file_path)
                if hasattr(self, 'status_label'): self.status_label.setText(f"Opened: {os.path.basename(file_path)}")
                # Fit view to loaded content
                bounds = self.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    self.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else: # Empty diagram, reset view
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
            self.scene.load_diagram_data(data) # This clears the scene and loads new data
            return True
        except json.JSONDecodeError as e:
            logging.error("JSONDecodeError loading %s: %s", file_path, e)
            return False
        except Exception as e:
            logging.error("Unexpected error loading %s: %s", file_path, e, exc_info=True)
            return False

    def on_save_file(self) -> bool:
        if not self.current_file_path: # If no current path, it's like Save As
            return self.on_save_file_as()
        return self._save_to_path(self.current_file_path)

    def on_save_file_as(self) -> bool:
        # Suggest a filename based on current path or "untitled"
        default_filename = os.path.basename(self.current_file_path) if self.current_file_path else "untitled" + FILE_EXTENSION
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As",
                                                   os.path.join(start_dir, default_filename),
                                                   FILE_FILTER)
        if file_path:
            # Ensure the file has the correct extension
            if not file_path.lower().endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION
            
            if self._save_to_path(file_path):
                self.current_file_path = file_path # Update current path
                # Window title and modified status are handled by _save_to_path
                return True
        return False

    def _save_to_path(self, file_path) -> bool:
        if self.py_sim_active:
            QMessageBox.warning(self, "Simulation Active", "Please stop the Python simulation before saving.")
            return False
            
        # Use QSaveFile for safer saving (writes to temp file first)
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
            
            if bytes_written == -1: # Error during write
                 error_str = save_file.errorString()
                 logging.error("Error writing to QSaveFile %s: %s", file_path, error_str)
                 QMessageBox.critical(self, "Save Error", f"Could not write data to file:\n{error_str}")
                 save_file.cancelWriting() # Important to cancel
                 return False

            if not save_file.commit(): # Finalize write (rename temp to actual)
                error_str = save_file.errorString()
                logging.error("Failed to commit QSaveFile for %s: %s", file_path, error_str)
                QMessageBox.critical(self, "Save Error", f"Could not finalize saving file:\n{error_str}")
                # No need for cancelWriting after commit failure, it's implicit
                return False

            logging.info("Successfully saved diagram to: %s", file_path)
            if hasattr(self, 'status_label'): self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            self.scene.set_dirty(False)
            self.setWindowModified(False) # Update QMainWindow's modified status
            self._update_window_title() # Reflect new name and clean status
            return True
        except Exception as e: # Catch any other Python exceptions during data prep or dump
            logging.error("Unexpected error during save to %s: %s", file_path, e, exc_info=True)
            QMessageBox.critical(self, "Save Error", f"An unexpected error occurred during saving:\n{e}")
            save_file.cancelWriting() # Ensure temp file is handled on Python error
            return False

    # --- Edit Menu Item Slots ---
    def on_select_all(self):
        self.scene.select_all()

    def on_delete_selected(self):
        self.scene.delete_selected_items() # Scene handles undo stack for this

    # --- MATLAB/Simulink Action Slots ---
    def on_export_simulink(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "Please configure MATLAB path in Settings first.")
            return
        if self.py_sim_active:
            QMessageBox.warning(self, "Python Simulation Active", "Please stop the Python simulation before exporting to Simulink.")
            return

        # Dialog to get model name and output directory
        dialog = QDialog(self)
        dialog.setWindowTitle("Export to Simulink")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp, "->M")) # Re-use icon
        layout = QFormLayout(dialog)
        layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)

        # Suggest model name based on current file or default
        base_name = os.path.splitext(os.path.basename(self.current_file_path or "BSM_Model"))[0]
        default_model_name = "".join(c if c.isalnum() or c=='_' else '_' for c in base_name) # Sanitize
        if not default_model_name or not default_model_name[0].isalpha(): # Ensure valid MATLAB var name
            default_model_name = "Mdl_" + default_model_name if default_model_name else "Mdl_MyStateMachine"
        default_model_name = default_model_name.replace('-','_') # Replace hyphens

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

        # Ask user for SLX file, suggest last generated or current file's dir
        default_dir = os.path.dirname(self.last_generated_model_path or self.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model to Simulate", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path # Remember for next time
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
        
        # Default output dir to same dir as SLX model
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

    # --- Help Menu Item Slots ---
    def _get_bundled_file_path(self, filename: str) -> str | None:
        """Determines the path to a bundled file, checking common locations."""
        # Determine base path: sys._MEIPASS for PyInstaller, else script/executable dir
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        elif getattr(sys, 'frozen', False): # For cx_Freeze or similar if _MEIPASS not set
             base_path = os.path.dirname(sys.executable)
        else: # Development mode
            base_path = os.path.dirname(os.path.abspath(__file__))

        # List of potential subdirectories where resources might be
        possible_subdirs = ['', 'docs', 'resources', 'examples', '_internal/bsm_designer_project/docs', '_internal/bsm_designer_project/examples'] # Added PyInstaller nested paths

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
                self.current_file_path = example_path # Set as current file
                self.last_generated_model_path = None
                self.undo_stack.clear()
                self.scene.set_dirty(False)
                self.setWindowModified(False)
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                logging.info("Opened example file: %s", filename)
                if hasattr(self, 'status_label'): self.status_label.setText(f"Opened example: {filename}")
                # Fit view to loaded content
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

    # --- Window Event Overrides ---
    def closeEvent(self, event: QCloseEvent):
        # Ensure Python simulation is stopped
        if self.py_sim_ui_manager: # Check if manager exists
            self.py_sim_ui_manager.on_stop_py_simulation(silent=True) # Stop silently

        # Stop internet check timer
        if self.internet_check_timer and self.internet_check_timer.isActive():
            self.internet_check_timer.stop()
        
        # Stop AI Chatbot manager
        if self.ai_chatbot_manager:
            self.ai_chatbot_manager.stop_chatbot()

        # Stop resource monitor
        if self.resource_monitor_worker and self.resource_monitor_thread:
            logger.info("Stopping resource monitor on close...")
            if self.resource_monitor_thread.isRunning():
                # Ensure stop_monitoring is called in the worker's thread context via queued connection
                QMetaObject.invokeMethod(self.resource_monitor_worker, "stop_monitoring", Qt.QueuedConnection)
                self.resource_monitor_thread.quit() # Ask the event loop to finish
                
                # Wait for interval_ms + a small buffer to allow the worker's loop to finish
                wait_time = 2200 # Default wait time
                if hasattr(self.resource_monitor_worker, 'interval_ms'):
                     wait_time = self.resource_monitor_worker.interval_ms + 200
                
                if not self.resource_monitor_thread.wait(wait_time): # Increased timeout
                    logger.warning("Resource monitor thread did not quit gracefully. Terminating.")
                    self.resource_monitor_thread.terminate() # Force terminate if stuck
                    self.resource_monitor_thread.wait(100) # Brief wait after terminate
                else:
                    logger.info("Resource monitor thread stopped gracefully.")
            # Set to None to help with garbage collection and prevent re-use
            self.resource_monitor_worker = None 
            self.resource_monitor_thread = None
        
        # Prompt for save if dirty
        if self._prompt_save_if_dirty():
            # Check for active MATLAB threads (best effort, might not catch all scenarios)
            if self.matlab_connection and hasattr(self.matlab_connection, '_active_threads') and self.matlab_connection._active_threads:
                logging.info("Closing application. %d MATLAB processes initiated by this session may still be running in the background if not completed.", len(self.matlab_connection._active_threads))
            event.accept()
        else:
            event.ignore()
            # If user cancels close, restart timers if they were active
            if self.internet_check_timer and not self.internet_check_timer.isActive(): 
                self.internet_check_timer.start()
            if self.resource_monitor_thread is None and self.resource_monitor_worker is None: # If it was stopped and nulled
                self._init_resource_monitor() # Re-init if needed

    # --- Internet Status Check ---
    def _init_internet_status_check(self):
        self.internet_check_timer.timeout.connect(self._run_internet_check_job)
        self.internet_check_timer.start(15000) # Check every 15 seconds
        QTimer.singleShot(100, self._run_internet_check_job) # Initial check soon after startup

    def _run_internet_check_job(self):
        current_status = False
        status_detail = "Checking..."
        try:
            # Try connecting to a reliable host (Google DNS) on a common port (DNS)
            # Timeout is crucial to prevent UI freezing
            s = socket.create_connection(("8.8.8.8", 53), timeout=1.5)
            s.close()
            current_status = True
            status_detail = "Connected"
        except socket.timeout:
            status_detail = "Disconnected (Timeout)"
        except (socket.gaierror, OSError): # Covers DNS resolution errors and other network issues
            status_detail = "Disconnected (Net Issue)"
        
        # Update UI only if status changed or first time
        if current_status != self._internet_connected or self._internet_connected is None:
            self._internet_connected = current_status
            self._update_internet_status_display(current_status, status_detail)


    def _update_internet_status_display(self, is_connected: bool, message_detail: str):
        full_status_text = f"Internet: {message_detail}"
        if hasattr(self, 'internet_status_label'):
            self.internet_status_label.setText(full_status_text)
            host_for_tooltip = socket.getfqdn('8.8.8.8') if is_connected else '8.8.8.8' # Show FQDN if resolved
            self.internet_status_label.setToolTip(f"{full_status_text} (Checks connection to {host_for_tooltip}:53)")
            text_color = COLOR_PY_SIM_STATE_ACTIVE.name() if is_connected else "#D32F2F" # Green / Red
            self.internet_status_label.setStyleSheet(f"padding:0 5px;color:{text_color};")
        
        logging.debug("Internet Status Update: %s", message_detail)
        # Notify AI Chatbot Manager of network status change
        if hasattr(self.ai_chatbot_manager, 'set_online_status'):
            self.ai_chatbot_manager.set_online_status(is_connected)

    # --- Python Simulation UI Updates ---
    def _update_py_sim_status_display(self):
        if hasattr(self, 'py_sim_status_label'):
            if self.py_sim_active and self.py_fsm_engine: # Check both flags
                current_state_name = self.py_fsm_engine.get_current_state_name()
                self.py_sim_status_label.setText(f"PySim: Active ({html.escape(current_state_name)})")
                self.py_sim_status_label.setStyleSheet(f"font-weight:bold;padding:0 5px;color:{COLOR_PY_SIM_STATE_ACTIVE.name()};")
            else:
                self.py_sim_status_label.setText("PySim: Idle")
                self.py_sim_status_label.setStyleSheet("font-weight:normal;padding:0 5px;")

    def _update_py_simulation_actions_enabled_state(self):
        # This method centralizes enabling/disabling of PySim related actions in MainWindow
        # It should be called whenever py_sim_active changes or other conditions (like MATLAB op) change
        
        # Check if a MATLAB operation is running (indicated by progress bar visibility)
        is_matlab_op_running = False
        if hasattr(self, 'progress_bar') and self.progress_bar: # Ensure progress_bar exists
            is_matlab_op_running = self.progress_bar.isVisible()
            
        sim_can_start = not self.py_sim_active and not is_matlab_op_running
        sim_can_be_controlled = self.py_sim_active and not is_matlab_op_running

        if hasattr(self, 'start_py_sim_action'): self.start_py_sim_action.setEnabled(sim_can_start)
        if hasattr(self, 'stop_py_sim_action'): self.stop_py_sim_action.setEnabled(sim_can_be_controlled)
        if hasattr(self, 'reset_py_sim_action'): self.reset_py_sim_action.setEnabled(sim_can_be_controlled)
        
        # Also update controls within the PySimDock via its UI manager
        if self.py_sim_ui_manager: # Check if manager exists
            self.py_sim_ui_manager._update_internal_controls_enabled_state()


    # Generic log message receiver (can be called by other modules)
    def log_message(self, level_str: str, message: str):
        """
        Logs a message to the application's log widget and the standard logger.
        level_str: "INFO", "WARNING", "ERROR", "DEBUG"
        message: The message to log.
        """
        level = getattr(logging, level_str.upper(), logging.INFO)
        logger.log(level, message) # This will go to console and file via logging_setup
        # The QTextEditHandler in logging_setup should handle UI updates automatically.
        # No need for direct self.log_output.append here if setup_global_logging worked.


if __name__ == '__main__':
    # Enable High DPI scaling for better visuals on high-resolution displays
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Ensure ./dependencies/icons directory exists for QSS relative paths
    app_dir = os.path.dirname(os.path.abspath(__file__))
    deps_icons_dir = os.path.join(app_dir, "dependencies", "icons")
    if not os.path.exists(deps_icons_dir):
        try:
            os.makedirs(deps_icons_dir, exist_ok=True)
            # This print is mostly for dev; can be logger.info if logger is configured early
            print(f"Info: Created directory for QSS icons: {deps_icons_dir}")
        except OSError as e:
            print(f"Warning: Could not create directory {deps_icons_dir}: {e}")


    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET_GLOBAL) # Apply global stylesheet
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
