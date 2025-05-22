
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
    QGraphicsSceneHoverEvent # CORRECTED: Added import
)
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform, QKeyEvent, QPainterPathStroker, QPolygonF, QKeySequence, 
    QDesktopServices, QWheelEvent, QMouseEvent, QCloseEvent, QFontMetrics # Added QFontMetrics
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QTimer, QSize, QTime, QUrl, 
    QSaveFile, QIODevice 
)
import math


# --- Configuration ---
APP_VERSION = "1.3.2" # Incremented for fixes
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

            script_lines.extend([
                f"{s_id_matlab_safe} = Stateflow.State(chartSFObj);",
                f"{s_id_matlab_safe}.Name = '{s_name_matlab}';",
                f"{s_id_matlab_safe}.Position = [{state['x']/3}, {state['y']/3}, {state['width']/3}, {state['height']/3}];", 
                f"stateHandles('{s_name_matlab}') = {s_id_matlab_safe};"
            ])
            if state.get('is_initial', False):
                script_lines.append(f"defaultTransition_{i} = Stateflow.Transition(chartSFObj);")
                script_lines.append(f"defaultTransition_{i}.Destination = {s_id_matlab_safe};")
        
        script_lines.append("% --- Transition Creation ---")
        for i, trans in enumerate(transitions):
            src_name_matlab = trans['source'].replace("'", "''")
            dst_name_matlab = trans['target'].replace("'", "''")
            t_label_matlab = trans['label'].replace("'", "''") if trans.get('label') else ''
            
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
    def __init__(self, text, mime_type, style_sheet, parent=None):
        super().__init__(text, parent)
        self.mime_type = mime_type
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
        mime_data.setText(self.text()) 
        mime_data.setData(self.mime_type, b"1") 
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
        painter.setBrush(bg_color)
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
class GraphicsStateItem(QGraphicsRectItem):
    Type = QGraphicsItem.UserType + 1
    def type(self): return GraphicsStateItem.Type

    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False):
        super().__init__(x, y, w, h)
        self.text_label = text
        self.is_initial = is_initial
        self.is_final = is_final
        self._text_color = Qt.black
        self._font = QFont("Arial", 10, QFont.Bold)

        self.setPen(QPen(QColor(50, 50, 50), 2)) 
        self.setBrush(QBrush(QColor(190, 220, 255))) 
        self.setFlags(QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges |
                      QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True) 

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
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
            'is_initial': self.is_initial, 'is_final': self.is_final
        }
    
    def set_text(self, text):
        if self.text_label != text:
            self.prepareGeometryChange()
            self.text_label = text
            self.update()

    def set_properties(self, name, is_initial, is_final):
        changed = False
        if self.text_label != name:
            self.text_label = name
            changed = True
        if self.is_initial != is_initial:
            self.is_initial = is_initial
            changed = True
        if self.is_final != is_final:
            self.is_final = is_final
            changed = True
        
        if changed:
            self.prepareGeometryChange()
            self.update()

class GraphicsTransitionItem(QGraphicsPathItem):
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type

    def __init__(self, start_item, end_item, text=""):
        super().__init__()
        self.start_item = start_item
        self.end_item = end_item
        self.text_label = text
        self.arrow_size = 12 
        self._text_color = QColor(30, 30, 30) 
        self._font = QFont("Arial", 9) 
        self.control_point_offset = QPointF(0,0) 

        self.setPen(QPen(QColor(0, 120, 120), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1) 
        self.setAcceptHoverEvents(True)
        self.update_path()

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent):
        self.setPen(QPen(QColor(0, 160, 160), 3)) 
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent):
        self.setPen(QPen(QColor(0, 120, 120), 2.5))
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 25 
        path_bounds = self.path().boundingRect()
        if self.text_label:
            fm = QFontMetrics(self._font)
            text_rect = fm.boundingRect(self.text_label)
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
            length = math.hypot(dx, dy) 
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

    def _get_intersection_point(self, item, line: QLineF): # Added QLineF type hint for line
        item_rect = item.sceneBoundingRect() 
        
        edges = [
            QLineF(item_rect.topLeft(), item_rect.topRight()),      
            QLineF(item_rect.topRight(), item_rect.bottomRight()),  
            QLineF(item_rect.bottomRight(), item_rect.bottomLeft()),
            QLineF(item_rect.bottomLeft(), item_rect.topLeft())     
        ]
        
        intersect_points = []
        for edge in edges:
            # QLineF.intersect requires a QPointF to store the result.
            # The IntersectType enum indicates if and how they intersect.
            intersection_point_var = QPointF() 
            intersect_type = line.intersect(edge, intersection_point_var)
            
            if intersect_type == QLineF.BoundedIntersection:
                # Check if the intersection point lies on the segment of 'edge'
                # This is an additional check sometimes needed due to floating point arithmetic.
                # However, QLineF.BoundedIntersection should theoretically mean it's on both segments.
                edge_rect_for_check = QRectF(edge.p1(), edge.p2()).normalized()
                epsilon = 1e-3 
                if (edge_rect_for_check.left() - epsilon <= intersection_point_var.x() <= edge_rect_for_check.right() + epsilon and
                    edge_rect_for_check.top() - epsilon <= intersection_point_var.y() <= edge_rect_for_check.bottom() + epsilon):
                    intersect_points.append(QPointF(intersection_point_var)) # Store a copy

        if not intersect_points:
            return item_rect.center() 

        closest_point = intersect_points[0]
        min_dist_sq = (QLineF(line.p1(), closest_point).length()) ** 2 # CORRECTED
        for pt in intersect_points[1:]:
            dist_sq = (QLineF(line.p1(), pt).length()) ** 2 # CORRECTED
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_point = pt
        return closest_point


    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty():
            return

        painter.setRenderHint(QPainter.Antialiasing)
        current_pen = self.pen() 
        
        if self.isSelected():
            stroker = QPainterPathStroker()
            stroker.setWidth(current_pen.widthF() + 8) 
            stroker.setCapStyle(Qt.RoundCap)
            stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path())
            painter.setPen(Qt.NoPen) 
            painter.setBrush(QColor(0,100,255,60)) 
            painter.drawPath(selection_path_shape)
        
        painter.setPen(current_pen) 
        painter.setBrush(Qt.NoBrush)
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

        if self.text_label:
            painter.setFont(self._font)
            fm = QFontMetrics(self._font)
            text_rect_original = fm.boundingRect(self.text_label)
            
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
            painter.drawText(text_final_pos, self.text_label)
    
    def get_data(self):
        return {
            'source': self.start_item.text_label if self.start_item else "None",
            'target': self.end_item.text_label if self.end_item else "None",
            'label': self.text_label,
            'control_offset_x': self.control_point_offset.x(),
            'control_offset_y': self.control_point_offset.y()
        }
    
    def set_text(self, text):
        if self.text_label != text:
            self.prepareGeometryChange() 
            self.text_label = text
            self.update() 

    def set_control_point_offset(self, offset: QPointF): 
        if self.control_point_offset != offset:
            self.control_point_offset = offset
            self.update_path()
            self.update()


# --- Undo Commands ---
# (These classes AddItemCommand, RemoveItemsCommand, MoveItemsCommand, EditItemPropertiesCommand remain unchanged from previous correct versions)
class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item_instance = item 
        if isinstance(item, GraphicsTransitionItem):
            self.start_item_name = item.start_item.text_label if item.start_item else None
            self.end_item_name = item.end_item.text_label if item.end_item else None
            self.label = item.text_label
            self.control_offset = item.control_point_offset
        elif isinstance(item, GraphicsStateItem):
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
                self.item_instance.update_path()
            else:
                self.scene.log_function(f"Error (Redo Add Transition): Could not link transition '{self.label}'. Source '{self.start_item_name}' or Target '{self.end_item_name}' state missing.")
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
        for item in items_to_remove:
            item_data = item.get_data()
            item_data['_type'] = item.type() 
            self.removed_items_data.append(item_data)
        self.item_instances_for_quick_toggle = list(items_to_remove)

    def redo(self): 
        for item_instance in self.item_instances_for_quick_toggle:
            if item_instance.scene() == self.scene: 
                self.scene.removeItem(item_instance)
        self.scene.set_dirty(True)

    def undo(self):
        newly_added_instances = []
        states_map_for_undo = {}
        for item_data in self.removed_items_data:
            if item_data['_type'] == GraphicsStateItem.Type:
                state = GraphicsStateItem(item_data['x'], item_data['y'], item_data['width'], item_data['height'],
                                          item_data['name'], item_data['is_initial'], item_data['is_final'])
                self.scene.addItem(state)
                newly_added_instances.append(state)
                states_map_for_undo[state.text_label] = state
        for item_data in self.removed_items_data:
            if item_data['_type'] == GraphicsTransitionItem.Type:
                src_item = states_map_for_undo.get(item_data['source'])
                tgt_item = states_map_for_undo.get(item_data['target'])
                if src_item and tgt_item:
                    trans = GraphicsTransitionItem(src_item, tgt_item, item_data['label'])
                    trans.set_control_point_offset(QPointF(item_data['control_offset_x'], item_data['control_offset_y']))
                    self.scene.addItem(trans)
                    newly_added_instances.append(trans)
                else:
                    self.scene.log_function(f"Error (Undo Remove): Could not re-link transition '{item_data['label']}'. States missing.")
        self.item_instances_for_quick_toggle = newly_added_instances
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
    def __init__(self, item, old_props, new_props, description="Edit Properties"):
        super().__init__(description)
        self.item = item 
        self.old_props = old_props 
        self.new_props = new_props 
        self.scene_ref = item.scene()

    def _apply_properties(self, props_to_apply):
        if not self.item or not self.scene_ref: return
        original_name_if_state = None
        if isinstance(self.item, GraphicsStateItem):
            original_name_if_state = self.item.text_label 
            self.item.set_properties(props_to_apply['name'], 
                                     props_to_apply.get('is_initial', False), 
                                     props_to_apply.get('is_final', False))
            if original_name_if_state != props_to_apply['name']:
                self.scene_ref._update_transitions_for_renamed_state(original_name_if_state, props_to_apply['name'])
        elif isinstance(self.item, GraphicsTransitionItem):
            self.item.set_text(props_to_apply['label'])
            if 'control_offset_x' in props_to_apply and 'control_offset_y' in props_to_apply:
                 self.item.set_control_point_offset(QPointF(props_to_apply['control_offset_x'], 
                                                            props_to_apply['control_offset_y']))
        self.item.update() 
        self.scene_ref.update() 
        self.scene_ref.set_dirty(True)

    def redo(self): self._apply_properties(self.new_props)
    def undo(self): self._apply_properties(self.old_props)

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

    def _update_connected_transitions(self, state_item):
        for item in self.items(): 
            if isinstance(item, GraphicsTransitionItem):
                if item.start_item == state_item or item.end_item == state_item:
                    item.update_path() 
    
    def _update_transitions_for_renamed_state(self, old_name, new_name):
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                if (item.start_item and item.start_item.text_label == new_name) or \
                   (item.end_item and item.end_item.text_label == new_name):
                    item.update()

    def get_state_by_name(self, name):
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
            
    def is_dirty(self):
        return self._dirty

    def set_log_function(self, log_function):
        self.log_function = log_function

    def set_mode(self, mode):
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
                if isinstance(item, GraphicsStateItem): item.setFlag(QGraphicsItem.ItemIsMovable, True)
        elif mode == "state":
            QApplication.setOverrideCursor(Qt.CrossCursor) 
            for item in self.items(): 
                 if isinstance(item, GraphicsStateItem): item.setFlag(QGraphicsItem.ItemIsMovable, False)
        elif mode == "transition":
            QApplication.setOverrideCursor(Qt.PointingHandCursor) 
            for item in self.items(): 
                 if isinstance(item, GraphicsStateItem): item.setFlag(QGraphicsItem.ItemIsMovable, False)
        
        if old_mode in ["state", "transition"] and mode not in ["state", "transition"]:
            QApplication.restoreOverrideCursor()
        
        if self.parent_window:
            if mode == "select" and self.parent_window.select_mode_action.isChecked() is False:
                self.parent_window.select_mode_action.setChecked(True)
            elif mode == "state" and self.parent_window.add_state_mode_action.isChecked() is False:
                self.parent_window.add_state_mode_action.setChecked(True)
            elif mode == "transition" and self.parent_window.add_transition_mode_action.isChecked() is False:
                self.parent_window.add_transition_mode_action.setChecked(True)

    def select_all(self):
        for item in self.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable:
                item.setSelected(True)

    def _handle_item_moved(self, moved_item):
        if isinstance(moved_item, GraphicsStateItem):
            self._update_connected_transitions(moved_item)
            if self.snap_to_grid_enabled and self._mouse_press_items_positions: 
                pass # Snapping handled in mouseReleaseEvent for MoveCommand

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos()
        items_at_pos = self.items(pos)
        state_item_at_pos = next((item for item in items_at_pos if isinstance(item, GraphicsStateItem)), None)
        top_item_at_pos = state_item_at_pos if state_item_at_pos else (items_at_pos[0] if items_at_pos else None)

        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size - 60 
                grid_y = round(pos.y() / self.grid_size) * self.grid_size - 30
                self._add_state_item(QPointF(grid_x, grid_y))
            elif self.current_mode == "transition":
                if isinstance(top_item_at_pos, GraphicsStateItem):
                    self._handle_transition_click(top_item_at_pos, pos)
                else: 
                    self.transition_start_item = None 
                    if self._temp_transition_line:
                        self.removeItem(self._temp_transition_line)
                        self._temp_transition_line = None
                    self.log_function("Transition drawing cancelled (clicked empty space).")
            else: 
                self._mouse_press_items_positions.clear()
                selected_movable = [item for item in self.selectedItems() if item.flags() & QGraphicsItem.ItemIsMovable]
                for item in selected_movable:
                     self._mouse_press_items_positions[item] = item.pos()
                super().mousePressEvent(event) 
        
        elif event.button() == Qt.RightButton:
            if top_item_at_pos and isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsTransitionItem)):
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
            self._temp_transition_line.setLine(QLineF(self.transition_start_item.sceneBoundingRect().center(), event.scenePos()))
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
                    
                    if (new_pos - old_pos).manhattanLength() > 1: 
                        moved_items_data.append((item, new_pos)) 
                
                if moved_items_data:
                    cmd = MoveItemsCommand(moved_items_data)
                    self.undo_stack.push(cmd)
                self._mouse_press_items_positions.clear()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        items_at_pos = self.items(event.scenePos())
        state_item_at_pos = next((item for item in items_at_pos if isinstance(item, GraphicsStateItem)), None)
        item_to_edit = state_item_at_pos
        if not item_to_edit: 
            item_to_edit = next((item for item in items_at_pos if isinstance(item, GraphicsTransitionItem)), None)

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
            if not item.isSelected(): 
                self.clearSelection() 
                item.setSelected(True)
            self.delete_selected_items()

    def edit_item_properties(self, item):
        original_name = None 
        if isinstance(item, GraphicsStateItem):
            original_name = item.text_label 
            old_props = item.get_data() 
            dialog = StatePropertiesDialog(item.text_label, item.is_initial, item.is_final, self.parent_window)
            if dialog.exec_() == QDialog.Accepted:
                new_name = dialog.get_name()
                if new_name != original_name and self.get_state_by_name(new_name):
                    QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state with the name '{new_name}' already exists.")
                    return
                
                new_props = {'name': new_name, 
                             'is_initial': dialog.is_initial_cb.isChecked(), 
                             'is_final': dialog.is_final_cb.isChecked(),
                             'x': old_props['x'], 'y': old_props['y'],
                             'width': old_props['width'], 'height': old_props['height']}
                cmd = EditItemPropertiesCommand(item, old_props, new_props, "Edit State Properties")
                self.undo_stack.push(cmd)
                self.log_function(f"Properties updated for state: {new_name}")

        elif isinstance(item, GraphicsTransitionItem):
            old_props = item.get_data()
            dialog = TransitionPropertiesDialog(item.text_label, item.control_point_offset, self.parent_window)
            if dialog.exec_() == QDialog.Accepted:
                new_label = dialog.get_label()
                new_offset = dialog.get_control_offset()
                new_props = {'label': new_label,
                             'control_offset_x': new_offset.x(),
                             'control_offset_y': new_offset.y(),
                             'source': old_props['source'], 'target': old_props['target']}
                cmd = EditItemPropertiesCommand(item, old_props, new_props, "Edit Transition Properties")
                self.undo_stack.push(cmd)
                self.log_function(f"Properties updated for transition: {new_props['label']}")
        self.update()

    def _add_state_item(self, pos: QPointF, name_prefix="State"): 
        i = 1
        while self.get_state_by_name(f"{name_prefix}{i}"): i += 1
        default_name = f"{name_prefix}{i}"

        state_name, ok = QInputDialog.getText(self.parent_window, "New State", "Enter state name:", text=default_name)
        if ok and state_name:
            state_name = state_name.strip()
            if not state_name:
                QMessageBox.warning(self.parent_window, "Invalid Name", "State name cannot be empty.")
                if self.current_mode == "state": self.set_mode("select")
                return
            if self.get_state_by_name(state_name):
                QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state with the name '{state_name}' already exists.")
                if self.current_mode == "state": self.set_mode("select")
                return

            props_dialog = StatePropertiesDialog(state_name, parent=self.parent_window) 
            if props_dialog.exec_() == QDialog.Accepted:
                new_state = GraphicsStateItem(
                    pos.x(), pos.y(), 120, 60, 
                    props_dialog.get_name(),
                    props_dialog.is_initial_cb.isChecked(),
                    props_dialog.is_final_cb.isChecked()
                )
                cmd = AddItemCommand(self, new_state, "Add State")
                self.undo_stack.push(cmd)
                self.log_function(f"Added state: {new_state.text_label} at ({pos.x():.0f},{pos.y():.0f})")
        
        if self.current_mode == "state": 
            self.set_mode("select") 

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
            if self._temp_transition_line:
                self.removeItem(self._temp_transition_line)
                self._temp_transition_line = None

            label, ok = QInputDialog.getText(self.parent_window, "New Transition", "Enter transition label (optional):")
            if ok: 
                new_transition = GraphicsTransitionItem(self.transition_start_item, clicked_state_item, label)
                cmd = AddItemCommand(self, new_transition, "Add Transition")
                self.undo_stack.push(cmd)
                self.log_function(f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{label}]")
            
            self.transition_start_item = None 
            self.set_mode("select") 

    def keyPressEvent(self, event: QKeyEvent): 
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            if self.selectedItems():
                self.delete_selected_items()
        elif event.key() == Qt.Key_Escape:
            if self.current_mode == "transition" and self.transition_start_item:
                self.transition_start_item = None
                if self._temp_transition_line:
                    self.removeItem(self._temp_transition_line)
                    self._temp_transition_line = None
                self.log_function("Transition drawing cancelled by Escape.")
                self.set_mode("select")
            else:
                self.clearSelection()
        else:
            super().keyPressEvent(event)

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
        if event.mimeData().hasFormat("application/x-state-tool"):
            event.setAccepted(True) 
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent): 
        if event.mimeData().hasFormat("application/x-state-tool"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent): 
        pos = event.scenePos()
        if event.mimeData().hasFormat("application/x-state-tool"):
            dropped_text = event.mimeData().text() 
            
            grid_x = round(pos.x() / self.grid_size) * self.grid_size - 60 
            grid_y = round(pos.y() / self.grid_size) * self.grid_size - 30
            
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
                if item.start_item and item.end_item: 
                    data['transitions'].append(item.get_data())
                else:
                    self.log_function(f"Warning: Skipping save of orphaned/invalid transition: {item.text_label if item.text_label else 'Untitled'}")
        return data

    def load_diagram_data(self, data):
        self.clear() 
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
                trans_item.set_control_point_offset(QPointF(
                    trans_data.get('control_offset_x', 0),
                    trans_data.get('control_offset_y', 0)
                ))
                self.addItem(trans_item)
            else:
                self.log_function(f"Warning (Load): Could not link transition '{trans_data.get('label')}' due to missing states: Source='{trans_data['source']}', Target='{trans_data['target']}'.")
        
        self.set_dirty(False) 
        self.undo_stack.clear()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)

        view_rect = self.views()[0].viewport().rect() if self.views() else rect
        visible_scene_rect = self.views()[0].mapToScene(view_rect).boundingRect() if self.views() else rect
        
        left = int(visible_scene_rect.left())
        right = int(visible_scene_rect.right())
        top = int(visible_scene_rect.top())
        bottom = int(visible_scene_rect.bottom())

        first_left = left - (left % self.grid_size)
        first_top = top - (top % self.grid_size)

        painter.setPen(self.grid_pen_light)
        for x in range(first_left, right, self.grid_size):
            for y in range(first_top, bottom, self.grid_size):
                 if (x % (self.grid_size * 5) != 0) and (y % (self.grid_size * 5) != 0): 
                    painter.drawPoint(x, y)

        # This section seems to be for major grid lines, which were previously full lines.
        # If dots are preferred everywhere, this section for 'dark_lines' might be redundant
        # or needs adjustment if a mix of dots and lines is desired.
        # For purely dotted grid, comment out or remove dark_lines drawing.
        major_grid_size = self.grid_size * 5
        first_major_left = left - (left % major_grid_size)
        first_major_top = top - (top % major_grid_size)

        painter.setPen(self.grid_pen_dark) # Using darker pen for these
        for x in range(first_major_left, right, major_grid_size):
            painter.drawLine(x, top, x, bottom)
        for y in range(first_major_top, bottom, major_grid_size):
            painter.drawLine(left, y, right, y)


# --- Zoomable Graphics View ---
class ZoomableView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag) 
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.zoom_level = 0 

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._is_panning = False
        self._is_panning_with_mouse = False
        self._last_pan_point = QPoint()

    def wheelEvent(self, event: QWheelEvent): 
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0: factor = 1.12; self.zoom_level += 1
            else: factor = 1 / 1.12; self.zoom_level -= 1
            
            if -10 <= self.zoom_level <= 20: 
                self.scale(factor, factor)
            else: 
                if delta > 0: self.zoom_level -=1 
                else: self.zoom_level +=1
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not self._is_panning and not event.isAutoRepeat():
            self._is_panning = True
            self._last_pan_point = event.pos() 
            self.setCursor(Qt.OpenHandCursor) 
            event.accept()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal: 
            self.scale(1.12, 1.12); self.zoom_level +=1
        elif event.key() == Qt.Key_Minus: 
            self.scale(1/1.12, 1/1.12); self.zoom_level -=1
        elif event.key() == Qt.Key_0 or event.key() == Qt.Key_Asterisk: 
             self.resetTransform() 
             self.zoom_level = 0
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and self._is_panning and not event.isAutoRepeat():
            self._is_panning = False
            current_scene_mode = self.scene().current_mode if self.scene() else "select"
            if current_scene_mode == "select": self.setCursor(Qt.ArrowCursor)
            elif current_scene_mode == "state": self.setCursor(Qt.CrossCursor)
            elif current_scene_mode == "transition": self.setCursor(Qt.PointingHandCursor)
            else: self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent): 
        if event.button() == Qt.MiddleButton or \
           (self._is_panning and event.button() == Qt.LeftButton):
            self._last_pan_point = event.pos() 
            self.setCursor(Qt.ClosedHandCursor)
            self._is_panning_with_mouse = True 
            event.accept()
        else:
            self._is_panning_with_mouse = False
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent): 
        if self._is_panning_with_mouse:
            delta_view = event.pos() - self._last_pan_point 
            self._last_pan_point = event.pos()
            
            hsbar = self.horizontalScrollBar()
            vsbar = self.verticalScrollBar()
            hsbar.setValue(hsbar.value() - delta_view.x())
            vsbar.setValue(vsbar.value() - delta_view.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent): 
        if self._is_panning_with_mouse and \
           (event.button() == Qt.MiddleButton or (self._is_panning and event.button() == Qt.LeftButton)):
            if self._is_panning: 
                self.setCursor(Qt.OpenHandCursor)
            else: 
                current_scene_mode = self.scene().current_mode if self.scene() else "select"
                if current_scene_mode == "select": self.setCursor(Qt.ArrowCursor)
                else: self.setCursor(Qt.ArrowCursor)
            self._is_panning_with_mouse = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)


# --- Dialogs ---
class StatePropertiesDialog(QDialog):
    def __init__(self, state_name="", initial=False, final=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Props"))
        layout = QFormLayout(self)
        layout.setSpacing(10)

        self.name_edit = QLineEdit(state_name)
        self.name_edit.setPlaceholderText("Enter a unique state name")
        layout.addRow("Name:", self.name_edit)

        self.is_initial_cb = QCheckBox("Is Initial State")
        self.is_initial_cb.setChecked(initial)
        layout.addRow(self.is_initial_cb)

        self.is_final_cb = QCheckBox("Is Final State")
        self.is_final_cb.setChecked(final)
        layout.addRow(self.is_final_cb)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setMinimumWidth(300)

    def get_name(self): return self.name_edit.text().strip()

class TransitionPropertiesDialog(QDialog):
    def __init__(self, label="", control_offset=QPointF(0,0), parent=None):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Props"))
        layout = QFormLayout(self)
        layout.setSpacing(10)

        self.label_edit = QLineEdit(label)
        self.label_edit.setPlaceholderText("Optional event / [condition] / {action}")
        layout.addRow("Label:", self.label_edit)

        self.offset_perp_spin = QSpinBox()
        self.offset_perp_spin.setRange(-800, 800) 
        self.offset_perp_spin.setSingleStep(10)
        self.offset_perp_spin.setValue(int(control_offset.x()))
        self.offset_perp_spin.setToolTip("Controls curve perpendicular to the line (-ve: left/up, +ve: right/down).")
        layout.addRow("Curve Bend:", self.offset_perp_spin)

        self.offset_tang_spin = QSpinBox()
        self.offset_tang_spin.setRange(-800, 800)
        self.offset_tang_spin.setSingleStep(10)
        self.offset_tang_spin.setValue(int(control_offset.y()))
        self.offset_tang_spin.setToolTip("Shifts curve midpoint along the line (for S-curves or asymmetry).")
        layout.addRow("Curve Shift:", self.offset_tang_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setMinimumWidth(350)

    def get_label(self): return self.label_edit.text()
    def get_control_offset(self): return QPointF(self.offset_perp_spin.value(), self.offset_tang_spin.value())


class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings")
        self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"))
        self.setMinimumWidth(550)

        main_layout = QVBoxLayout(self)

        path_group = QGroupBox("MATLAB Executable Path")
        path_form_layout = QFormLayout() 
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path)
        self.path_edit.setPlaceholderText("e.g., C:\\Program Files\\MATLAB\\R202Xy\\bin\\matlab.exe")
        path_form_layout.addRow("Path:", self.path_edit)
        
        btn_layout = QHBoxLayout()
        auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_FileDialogContentsView, "Det"), "Auto-detect")
        auto_detect_btn.clicked.connect(self._auto_detect)
        auto_detect_btn.setToolTip("Attempt to find MATLAB installations.")
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), "Browse...")
        browse_btn.clicked.connect(self._browse)
        browse_btn.setToolTip("Browse for MATLAB executable.")
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
        self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        test_btn = QPushButton(get_standard_icon(QStyle.SP_CommandLink, "Test"), "Test Connection")
        test_btn.clicked.connect(self._test_connection_and_update_label) 
        test_btn.setToolTip("Test connection to the specified MATLAB path.")
        test_layout.addWidget(test_btn)
        test_layout.addWidget(self.test_status_label)
        test_group.setLayout(test_layout)
        main_layout.addWidget(test_group)

        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close")
        dialog_buttons.accepted.connect(self._apply_settings)
        dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)
        
        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        if self.matlab_connection.matlab_path and self.matlab_connection.connected:
            self._update_test_label_from_signal(True, f"Connected: {self.matlab_connection.matlab_path}")
        elif self.matlab_connection.matlab_path:
             self._update_test_label_from_signal(False, f"Path previously set ({self.matlab_connection.matlab_path}), but connection unconfirmed or failed.")
        else:
            self._update_test_label_from_signal(False, "MATLAB path not set.")

    def _auto_detect(self):
        self.test_status_label.setText("Status: Auto-detecting MATLAB, please wait...")
        self.test_status_label.setStyleSheet("")
        QApplication.processEvents() 
        self.matlab_connection.detect_matlab() 

    def _browse(self):
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        start_dir = os.path.dirname(self.path_edit.text()) if self.path_edit.text() and os.path.isdir(os.path.dirname(self.path_edit.text())) else QDir.homePath()
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path:
            self.path_edit.setText(path)
            self._update_test_label_from_signal(False, "Path changed. Click 'Test Connection' or 'Apply & Close'.")

    def _test_connection_and_update_label(self):
        path = self.path_edit.text().strip()
        if not path:
            self._update_test_label_from_signal(False, "MATLAB path is empty. Cannot test.")
            return

        self.test_status_label.setText("Status: Testing connection, please wait...")
        self.test_status_label.setStyleSheet("")
        QApplication.processEvents()
        
        if self.matlab_connection.set_matlab_path(path):
            self.matlab_connection.test_connection()

    def _update_test_label_from_signal(self, success, message):
        status_prefix = "Status: "
        if success:
            if "MATLAB path set" in message : status_prefix = "Status: Path validated. "
            elif "successful" in message : status_prefix = "Status: Connected! "
        
        self.test_status_label.setText(status_prefix + message)
        self.test_status_label.setStyleSheet("color: #006400; font-weight: bold;" if success else "color: #B22222; font-weight: bold;")
        if success and self.matlab_connection.matlab_path: 
             self.path_edit.setText(self.matlab_connection.matlab_path) 

    def _apply_settings(self):
        path = self.path_edit.text().strip()
        self.matlab_connection.set_matlab_path(path) 
        self.accept()

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
        self.setGeometry(50, 50, 1500, 950) 
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
        self.save_as_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton),"Save &As...", self, shortcut=QKeySequence.SaveAs, statusTip="Save the current file with a new name", triggered=self.on_save_file_as)
        self.exit_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", self, shortcut=QKeySequence.Quit, statusTip="Exit the application", triggered=self.close)

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
        
        self.mode_action_group = QActionGroup(self)
        self.mode_action_group.setExclusive(True)
        
        select_icon_enum = _safe_get_style_enum("SP_ArrowCursor", "SP_PointingHandCursor")
        self.select_mode_action = QAction(QIcon.fromTheme("edit-select", get_standard_icon(select_icon_enum, "Sel")), "Select/Move", self, checkable=True, statusTip="Mode: Select and move items (Esc to cancel)", triggered=lambda: self.scene.set_mode("select"))
        
        state_icon_enum = _safe_get_style_enum("SP_FileDialogNewFolder", "SP_FileIcon") 
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", get_standard_icon(state_icon_enum, "St")), "Add State", self, checkable=True, statusTip="Mode: Click on canvas to add a new state (Esc to cancel)", triggered=lambda: self.scene.set_mode("state"))
        
        trans_icon_enum = _safe_get_style_enum("SP_FileDialogBack", "SP_ArrowRight") 
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", get_standard_icon(trans_icon_enum, "Tr")), "Add Transition", self, checkable=True, statusTip="Mode: Click source then target state (Esc to cancel)", triggered=lambda: self.scene.set_mode("transition"))
        
        self.mode_action_group.addAction(self.select_mode_action)
        self.mode_action_group.addAction(self.add_state_mode_action)
        self.mode_action_group.addAction(self.add_transition_mode_action)
        self.select_mode_action.setChecked(True) 

        self.export_simulink_action = QAction(get_standard_icon(QStyle.SP_ArrowRight, "->M"), "&Export to Simulink...", self, statusTip="Generate a Simulink model from the diagram", triggered=self.on_export_simulink)
        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation...", self, statusTip="Run a Simulink model (requires MATLAB with Simulink)", triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cde"), "Generate &Code (C/C++)...", self, statusTip="Generate C/C++ code from a Simulink model (requires MATLAB Coder & Simulink Coder / Embedded Coder)", triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(_safe_get_style_enum("SP_ComputerIcon"), "Cfg"), "&MATLAB Settings...", self, statusTip="Configure MATLAB connection settings", triggered=self.on_matlab_settings)

        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, statusTip=f"Show information about {APP_NAME}", triggered=self.on_about)

    def _create_menus(self):
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet("QMenuBar { background-color: #E8E8E8; } QMenu::item:selected { background-color: #D0D0D0; }")
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
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
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_DesktopIcon, "Mode"),"Interaction Mode") 
        mode_menu.addAction(self.select_mode_action)
        mode_menu.addAction(self.add_state_mode_action)
        mode_menu.addAction(self.add_transition_mode_action)

        sim_menu = menu_bar.addMenu("&Simulation")
        sim_menu.addAction(self.run_simulation_action)
        sim_menu.addAction(self.generate_code_action)
        sim_menu.addSeparator()
        sim_menu.addAction(self.matlab_settings_action)

        self.view_menu = menu_bar.addMenu("&View")

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(28,28) 
        file_toolbar = self.addToolBar("File")
        file_toolbar.setObjectName("FileToolBar")
        file_toolbar.setIconSize(icon_size)
        file_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon) 
        file_toolbar.addAction(self.new_action)
        file_toolbar.addAction(self.open_action)
        file_toolbar.addAction(self.save_action)

        edit_toolbar = self.addToolBar("Edit")
        edit_toolbar.setObjectName("EditToolBar")
        edit_toolbar.setIconSize(icon_size)
        edit_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        edit_toolbar.addAction(self.undo_action)
        edit_toolbar.addAction(self.redo_action)
        edit_toolbar.addSeparator()
        edit_toolbar.addAction(self.delete_action)
        
        tools_tb = self.addToolBar("Interaction Tools") 
        tools_tb.setObjectName("ToolsToolBar")
        tools_tb.setIconSize(icon_size)
        tools_tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        tools_tb.addAction(self.select_mode_action)
        tools_tb.addAction(self.add_state_mode_action)
        tools_tb.addAction(self.add_transition_mode_action)
        self.addToolBarBreak() 

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready") 
        self.status_bar.addWidget(self.status_label, 1) 

        self.matlab_status_label = QLabel("MATLAB: Initializing...")
        self.matlab_status_label.setToolTip("MATLAB connection status.")
        self.matlab_status_label.setStyleSheet("padding-right: 10px; padding-left: 5px;")
        self.status_bar.addPermanentWidget(self.matlab_status_label)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0,0) 
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(180) 
        self.progress_bar.setTextVisible(False) 
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)
        self.tools_dock = QDockWidget("Tools", self)
        self.tools_dock.setObjectName("ToolsDock")
        self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)
        tools_layout.setSpacing(8)
        tools_layout.setContentsMargins(8, 8, 8, 8)

        mode_group = QGroupBox("Interaction Modes")
        mode_layout = QVBoxLayout()
        mode_layout.setSpacing(5)

        self.toolbox_select_button = QToolButton()
        self.toolbox_select_button.setDefaultAction(self.select_mode_action)
        self.toolbox_select_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toolbox_select_button.setIconSize(QSize(20,20))
        mode_layout.addWidget(self.toolbox_select_button)

        self.toolbox_add_state_button = QToolButton()
        self.toolbox_add_state_button.setDefaultAction(self.add_state_mode_action)
        self.toolbox_add_state_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toolbox_add_state_button.setIconSize(QSize(20,20))
        mode_layout.addWidget(self.toolbox_add_state_button)

        self.toolbox_transition_button = QToolButton()
        self.toolbox_transition_button.setDefaultAction(self.add_transition_mode_action)
        self.toolbox_transition_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toolbox_transition_button.setIconSize(QSize(20,20))
        mode_layout.addWidget(self.toolbox_transition_button)
        
        mode_group.setLayout(mode_layout)
        tools_layout.addWidget(mode_group)

        draggable_group = QGroupBox("Drag to Canvas")
        draggable_layout = QVBoxLayout()
        draggable_layout.setSpacing(5)
        state_drag_button = DraggableToolButton(
            "State", 
            "application/x-state-tool",
            "QPushButton { background-color: #D8E8F8; color: #2C3E50; border: 1px solid #A9CCE3; padding: 6px; text-align: left;}"
            "QPushButton:hover { background-color: #C8D8E8; }"
            "QPushButton:pressed { background-color: #B8C8D8; }"
        )
        state_drag_button.setIcon(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"))
        state_drag_button.setIconSize(QSize(22,22))
        draggable_layout.addWidget(state_drag_button)
        draggable_group.setLayout(draggable_layout)
        tools_layout.addWidget(draggable_group)

        tools_layout.addStretch() 
        self.tools_dock.setWidget(tools_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock)
        self.view_menu.addAction(self.tools_dock.toggleViewAction())

        self.log_dock = QDockWidget("Log Output", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9)) 
        self.log_output.setStyleSheet("QTextEdit { background-color: #FDFDFD; color: #333; border: 1px solid #DDD; }")
        self.log_dock.setWidget(self.log_output)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.view_menu.addAction(self.log_dock.toggleViewAction())
        
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        properties_widget = QWidget()
        self.properties_layout = QVBoxLayout(properties_widget) 
        self.properties_editor_label = QLabel("<i>No item selected.</i>")
        self.properties_editor_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.properties_editor_label.setWordWrap(True)
        self.properties_editor_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton,"Edt"), "Edit Properties...")
        self.properties_edit_button.setEnabled(False)
        self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock)
        self.properties_edit_button.setIconSize(QSize(18,18))

        self.properties_layout.addWidget(self.properties_editor_label, 1) 
        self.properties_layout.addWidget(self.properties_edit_button)
        properties_widget.setLayout(self.properties_layout)
        self.properties_dock.setWidget(properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        self.view_menu.addAction(self.properties_dock.toggleViewAction())

    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self) 
        self.setCentralWidget(self.view)

    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1:
            item = selected_items[0]
            item_info = "<b>Type:</b> "
            if isinstance(item, GraphicsStateItem):
                item_info += "State<br>"
                item_info += f"<b>Name:</b> {item.text_label}<br>"
                item_info += f"<b>Initial:</b> {'Yes' if item.is_initial else 'No'}<br>"
                item_info += f"<b>Final:</b> {'Yes' if item.is_final else 'No'}<br>"
                item_info += f"<b>Position:</b> ({item.x():.0f}, {item.y():.0f})<br>"
                item_info += f"<b>Size:</b> {item.rect().width():.0f} x {item.rect().height():.0f}"
            elif isinstance(item, GraphicsTransitionItem):
                item_info += "Transition<br>"
                item_info += f"<b>Label:</b> {item.text_label if item.text_label else '<i>(No Label)</i>'}<br>"
                item_info += f"<b>From:</b> {item.start_item.text_label if item.start_item else 'N/A'}<br>"
                item_info += f"<b>To:</b> {item.end_item.text_label if item.end_item else 'N/A'}<br>"
                item_info += f"<b>Curve:</b> Bend={item.control_point_offset.x():.0f}, Shift={item.control_point_offset.y():.0f}"
            else:
                item_info += "Unknown Item Type"
            
            self.properties_editor_label.setText(item_info)
            self.properties_edit_button.setEnabled(True)
            self.properties_edit_button.setToolTip(f"Edit properties of selected {type(item).__name__}")
        elif len(selected_items) > 1:
            self.properties_editor_label.setText(f"<b>{len(selected_items)} items selected.</b><br><i>Select a single item to view/edit its properties.</i>")
            self.properties_edit_button.setEnabled(False)
            self.properties_edit_button.setToolTip("Select a single item to edit properties.")
        else:
            self.properties_editor_label.setText("<i>No item selected.</i><br>Click an item in the diagram or use tools to add new items.")
            self.properties_edit_button.setEnabled(False)
            self.properties_edit_button.setToolTip("")

    def _on_edit_selected_item_properties_from_dock(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1:
            self.scene.edit_item_properties(selected_items[0]) 

    def log_message(self, message: str):
        timestamp = QTime.currentTime().toString('hh:mm:ss.zzz')
        self.log_output.append(f"[{timestamp}] {message}")
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
        self.status_label.setText(message.split('\n')[0][:120]) 

    def _update_window_title(self):
        title = APP_NAME
        if self.current_file_path:
            title += f" - {os.path.basename(self.current_file_path)}"
        else:
            title += " - Untitled"
        title += "[*]" 
        self.setWindowTitle(title)

    def _update_save_actions_enable_state(self):
        is_dirty = self.isWindowModified()
        self.save_action.setEnabled(is_dirty)
        self.save_as_action.setEnabled(True) 

    def _update_undo_redo_actions_enable_state(self):
        self.undo_action.setEnabled(self.undo_stack.canUndo())
        self.redo_action.setEnabled(self.undo_stack.canRedo())
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
        self.export_simulink_action.setEnabled(connected)
        self.run_simulation_action.setEnabled(connected)
        self.generate_code_action.setEnabled(connected)

    def _start_matlab_operation(self, operation_name):
        self.log_message(f"MATLAB Operation: {operation_name} starting...")
        self.status_label.setText(f"Running: {operation_name}...")
        self.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False)

    def _finish_matlab_operation(self):
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready") 
        self.set_ui_enabled_for_matlab_op(True)
        self.log_message("MATLAB Operation: Finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        self.menuBar().setEnabled(enabled)
        for child in self.children(): 
            if isinstance(child, QToolBar):
                child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock"]: 
            dock = self.findChild(QDockWidget, dock_name)
            if dock: 
                if dock_name == "LogDock" and not enabled: 
                    pass 
                else:
                    dock.setEnabled(enabled)

    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation()
        self.log_message(f"MATLAB Result ({('Success' if success else 'Failure')}): {message}") 
        if success:
            if "Model generation" in message and data: 
                 self.last_generated_model_path = data 
                 QMessageBox.information(self, "Simulink Model Generation", 
                                        f"Simulink model generated successfully:\n{data}")
            elif "Simulation" in message: 
                 QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else:
            QMessageBox.warning(self, "MATLAB Operation Failed", message)
        
    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation()
        self.log_message(f"MATLAB Code Gen Result ({('Success' if success else 'Failure')}): {message}") 
        if success and output_dir:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText) 
            msg_box.setText(f"Code generation process completed.<br>"
                            f"Output directory: <a href='file:///{os.path.abspath(output_dir)}'>{os.path.abspath(output_dir)}</a>")
            
            open_dir_button = msg_box.addButton("Open Directory", QMessageBox.ActionRole)
            msg_box.addButton(QMessageBox.Ok)
            msg_box.exec_()

            if msg_box.clickedButton() == open_dir_button:
                try:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(output_dir)))
                except Exception as e:
                    self.log_message(f"Error opening directory {output_dir}: {e}")
                    QMessageBox.warning(self, "Error Opening Directory", f"Could not open directory:\n{e}")
        elif not success:
            QMessageBox.warning(self, "Code Generation Failed", message)

    def _prompt_save_if_dirty(self):
        if not self.isWindowModified(): 
            return True 
        
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes?",
                                     f"The document '{file_name}' has unsaved changes.\n"
                                     "Do you want to save them before continuing?",
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
        
        self.scene.clear() 
        self.scene.setSceneRect(0,0,5000,4000) 
        self.current_file_path = None
        self.last_generated_model_path = None 
        self.undo_stack.clear() 
        self.scene.set_dirty(False) 
        self._update_window_title() 
        self._update_undo_redo_actions_enable_state()
        if not silent: self.log_message("New diagram created. Ready.")
        self.view.resetTransform() 
        self.view.centerOn(2500,2000) 
        self.select_mode_action.trigger() 
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
                self.last_generated_model_path = None 
                self.undo_stack.clear() 
                self.scene.set_dirty(False) 
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                self.log_message(f"Successfully opened: {file_path}")
                items_bounds = self.scene.itemsBoundingRect()
                if not items_bounds.isEmpty():
                    padded_bounds = items_bounds.adjusted(-100, -100, 100, 100)
                    self.view.fitInView(padded_bounds, Qt.KeepAspectRatio)
                else: 
                    self.view.resetTransform()
                    self.view.centerOn(2500,2000)
            else: 
                QMessageBox.critical(self, "Error Opening File", f"Could not load or parse the file: {file_path}")
                self.log_message(f"Failed to open file: {file_path}")

    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict) or 'states' not in data or 'transitions' not in data:
                self.log_message(f"Error: Invalid BSM file format in {file_path}.")
                return False
            self.scene.load_diagram_data(data) 
            return True
        except json.JSONDecodeError as e:
            self.log_message(f"Error decoding JSON from {file_path}: {str(e)}")
            return False
        except Exception as e:
            self.log_message(f"Unexpected error loading file {file_path}: {str(e)}")
            return False

    def on_save_file(self):
        if self.current_file_path:
            if self._save_to_path(self.current_file_path):
                self.scene.set_dirty(False) 
                return True
            return False 
        else:
            return self.on_save_file_as() 

    def on_save_file_as(self):
        start_path = self.current_file_path if self.current_file_path else os.path.join(QDir.homePath(), "untitled" + FILE_EXTENSION)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As", 
                                                   start_path, 
                                                   FILE_FILTER)
        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION
            if self._save_to_path(file_path):
                self.current_file_path = file_path 
                self.scene.set_dirty(False) 
                self._update_window_title() 
                return True
        return False 

    def _save_to_path(self, file_path):
        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            self.log_message(f"Error opening save file {file_path}: {save_file.errorString()}")
            QMessageBox.critical(self, "Save Error", f"Failed to open file for saving:\n{save_file.errorString()}")
            return False
        try:
            data = self.scene.get_diagram_data()
            json_data = json.dumps(data, indent=4, ensure_ascii=False)
            save_file.write(json_data.encode('utf-8'))
            if not save_file.commit():
                self.log_message(f"Error committing save to {file_path}: {save_file.errorString()}")
                QMessageBox.critical(self, "Save Error", f"Failed to commit saved file:\n{save_file.errorString()}")
                return False
            self.log_message(f"File saved successfully: {file_path}")
            return True
        except Exception as e:
            self.log_message(f"Error preparing data or writing to save file {file_path}: {str(e)}")
            QMessageBox.critical(self, "Save Error", f"An error occurred during saving:\n{str(e)}")
            save_file.cancelWriting() 
            return False
            
    def on_select_all(self):
        self.scene.select_all()

    def on_delete_selected(self):
        self.scene.delete_selected_items() 

    def on_export_simulink(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self, "MATLAB Not Connected", "MATLAB is not connected. Please configure MATLAB settings first in the Simulation menu.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Export to Simulink")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowRight, "->M"))
        layout = QFormLayout(dialog)
        layout.setSpacing(10)
        
        model_name_edit = QLineEdit("BSM_SimulinkModel")
        model_name_edit.setPlaceholderText("Valid Simulink model name")
        layout.addRow("Simulink Model Name:", model_name_edit)

        default_out_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        output_dir_edit = QLineEdit(default_out_dir)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"),"Browse...")
        browse_btn.setToolTip("Select directory to save the .slx file.")
        def browse_dir():
            d = QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text())
            if d: output_dir_edit.setText(d)
        browse_btn.clicked.connect(browse_dir)
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(output_dir_edit, 1) 
        dir_layout.addWidget(browse_btn)
        layout.addRow("Output Directory:", dir_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        dialog.setMinimumWidth(400)

        if dialog.exec_() == QDialog.Accepted:
            model_name = model_name_edit.text().strip()
            output_dir = output_dir_edit.text().strip()
            if not model_name or not output_dir:
                QMessageBox.warning(self, "Input Error", "Model name and output directory must be specified.")
                return
            
            if not model_name[0].isalpha() or not all(c.isalnum() or c == '_' for c in model_name):
                QMessageBox.warning(self, "Invalid Model Name", "Model name must start with a letter and contain only alphanumeric characters and underscores.")
                return

            if not os.path.exists(output_dir):
                try: os.makedirs(output_dir, exist_ok=True)
                except OSError as e:
                    QMessageBox.critical(self, "Directory Creation Error", f"Could not create output directory:\n{e}")
                    return

            diagram_data = self.scene.get_diagram_data()
            if not diagram_data['states']:
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

        default_model_dir = os.path.dirname(self.last_generated_model_path) if self.last_generated_model_path else \
                            (os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model to Simulate", 
                                                   default_model_dir, 
                                                   "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return
        self.last_generated_model_path = model_path 

        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Enter simulation stop time (seconds):", 10.0, 0.001, 86400.0, 3)
        if not ok: return

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

        dialog = QDialog(self)
        dialog.setWindowTitle("Code Generation Options")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cde"))
        layout = QFormLayout(dialog)
        layout.setSpacing(10)

        lang_combo = QComboBox()
        lang_combo.addItems(["C", "C++"])
        lang_combo.setCurrentText("C++") 
        layout.addRow("Target Language:", lang_combo)

        default_output_base = os.path.dirname(model_path)
        output_dir_edit = QLineEdit(default_output_base) 
        output_dir_edit.setPlaceholderText("Base directory for generated code")
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), "Browse...")
        def browse_dir_codegen():
            d = QFileDialog.getExistingDirectory(dialog, "Select Base Output Directory for Code", output_dir_edit.text())
            if d: output_dir_edit.setText(d)
        browse_btn.clicked.connect(browse_dir_codegen)
        dir_layout_codegen = QHBoxLayout()
        dir_layout_codegen.addWidget(output_dir_edit, 1)
        dir_layout_codegen.addWidget(browse_btn)
        layout.addRow("Base Output Directory:", dir_layout_codegen)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        dialog.setMinimumWidth(450)

        if dialog.exec_() == QDialog.Accepted:
            language = lang_combo.currentText()
            output_dir_base = output_dir_edit.text().strip()
            if not output_dir_base:
                QMessageBox.warning(self, "Input Error", "Base output directory must be specified for code generation.")
                return
            
            if not os.path.exists(output_dir_base):
                 try: os.makedirs(output_dir_base, exist_ok=True)
                 except OSError as e:
                     QMessageBox.critical(self, "Directory Creation Error", f"Could not create output directory:\n{e}")
                     return

            self._start_matlab_operation(f"Generating {language} code for '{os.path.basename(model_path)}'")
            self.matlab_connection.generate_code(model_path, language, output_dir_base)

    def on_matlab_settings(self):
        dialog = MatlabSettingsDialog(self.matlab_connection, self)
        dialog.exec_() 

    def on_about(self):
        QMessageBox.about(self, "About " + APP_NAME,
                          f"<h3>{APP_NAME} v{APP_VERSION}</h3>"
                          "<p>A graphical tool for designing brain-inspired state machines. "
                          "It facilitates the creation, visualization, and modification of state diagrams, "
                          "and integrates with MATLAB/Simulink for simulation and C/C++ code generation.</p>"
                          "<p><b>Features:</b></p>"
                          "<ul>"
                          "<li>Intuitive drag-and-drop and click-to-add interface for states and transitions.</li>"
                          "<li>Persistent storage of designs in JSON format ({FILE_EXTENSION}).</li>"
                          "<li>Undo/Redo functionality for robust editing.</li>"
                          "<li>Interactive property editing for states and transitions.</li>"
                          "<li>Zoomable and pannable diagram view with grid background.</li>"
                          "<li><b>MATLAB Integration (requires MATLAB, Simulink, Stateflow, Coders):</b>"
                          "<ul><li>Auto-detection of MATLAB installation.</li>"
                          "<li>Export diagrams to Simulink models (.slx).</li>"
                          "<li>Run simulations of exported models directly via MATLAB.</li>"
                          "<li>Generate C or C++ code from Simulink models.</li></ul></li>"
                          "</ul>"
                          "<p><i>Developed by the AI Revell Lab.</i></p>"
                          "<p>This tool is intended for research and educational purposes in designing and "
                          "simulating complex state-based systems.</p>")

    def closeEvent(self, event: QCloseEvent): 
        if self._prompt_save_if_dirty():
            active_threads = list(self.matlab_connection._active_threads) 
            if active_threads:
                self.log_message(f"Closing application. {len(active_threads)} MATLAB process(es) may still be running in background if not completed.")
            event.accept()
        else:
            event.ignore() 


if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
