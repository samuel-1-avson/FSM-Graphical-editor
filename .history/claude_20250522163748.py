
import sys
import os
import tempfile
import subprocess
import json
import html
import math

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


# --- Application Constants ---
APP_VERSION = "1.6.0" # Incremented for GUI/interactivity improvements
APP_NAME = "Brain State Machine Designer"
APP_ORGANIZATION_NAME = "AIRL" # Example
FILE_EXTENSION = ".bsm"
FILE_FILTER = f"Brain State Machine Files (*{FILE_EXTENSION});;All Files (*)"

# --- Stylesheet ---
MAIN_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #ECEFF1; /* Light bluish-grey */
}

QToolBar {
    background-color: #CFD8DC; /* Slightly darker toolbar */
    border-bottom: 1px solid #B0BEC5;
    spacing: 5px;
}
QToolBar QToolButton {
    padding: 6px;
    border-radius: 4px;
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #FFFFFF, stop:1 #E0E0E0);
    border: 1px solid #BDBDBD;
    color: #37474F; /* Dark grey text */
}
QToolBar QToolButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #F5F5F5, stop:1 #D5D5D5);
    border: 1px solid #9E9E9E;
}
QToolBar QToolButton:pressed, QToolBar QToolButton:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #D5D5D5, stop:1 #BDBDBD);
    border: 1px solid #757575;
}

QMenuBar {
    background-color: #CFD8DC;
    color: #37474F;
    border-bottom: 1px solid #B0BEC5;
}
QMenuBar::item {
    background-color: transparent;
    padding: 4px 10px;
}
QMenuBar::item:selected {
    background-color: #B0BEC5; /* Hover */
    color: #263238;
}
QMenuBar::item:pressed {
    background-color: #90A4AE;
}

QMenu {
    background-color: #FFFFFF; /* White background for menus */
    border: 1px solid #BDBDBD;
    color: #37474F;
}
QMenu::item {
    padding: 5px 25px 5px 25px;
}
QMenu::item:selected {
    background-color: #E3F2FD; /* Light blue selection */
    color: #1976D2;
}
QMenu::separator {
    height: 1px;
    background: #E0E0E0;
    margin-left: 5px;
    margin-right: 5px;
}

QDockWidget {
    background-color: #F5F5F5; /* Slightly lighter dock background */
    color: #37474F;
}
QDockWidget::title {
    text-align: left;
    background-color: #B0BEC5; /* Bluish grey title bar */
    padding: 6px;
    border: 1px solid #90A4AE;
    border-bottom: 2px solid #78909C; /* Thicker bottom border */
    color: #263238; /* Darker text for title */
    font-weight: bold;
}

QStatusBar {
    background-color: #CFD8DC;
    border-top: 1px solid #B0BEC5;
    color: #37474F;
}
QStatusBar QLabel { /* Styles general labels in status bar */
    padding: 0px 5px;
}
QStatusBar QProgressBar {
    border: 1px solid #90A4AE;
    border-radius: 3px;
    background-color: #ECEFF1;
    text-align: center; /* If text visible */
}
QStatusBar QProgressBar::chunk {
    background-color: #4CAF50; /* Green progress */
    width: 10px;
    margin: 0.5px;
}

QGroupBox {
    background-color: #ECEFF1; /* Match main background or slightly lighter */
    border: 1px solid #B0BEC5;
    border-radius: 6px;
    margin-top: 12px; /* Space for title */
    padding: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px 0 5px;
    left: 10px;
    color: #37474F;
    font-weight: bold;
}

QPushButton {
    background-color: #E0E0E0;
    border: 1px solid #BDBDBD;
    border-radius: 4px;
    padding: 6px 12px;
    color: #37474F;
}
QPushButton:hover {
    background-color: #D5D5D5;
    border-color: #9E9E9E;
}
QPushButton:pressed {
    background-color: #BDBDBD;
    border-color: #757575;
}
QPushButton:disabled {
    background-color: #EEEEEE;
    border-color: #E0E0E0;
    color: #9E9E9E;
}

QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #BDBDBD;
    border-radius: 4px;
    padding: 4px;
    color: #37474F;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #64B5F6; /* Light blue focus border */
}
QComboBox::drop-down {
    border: 0px; /* Omit border for cleaner look */
}
QComboBox::down-arrow {
    image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-down-arrow-16.png); /* Needs to be available resource */
}

QTabWidget::pane {
    border: 1px solid #B0BEC5;
    border-radius: 4px;
    background: #FFFFFF; /* White background for tab content area */
    padding: 5px;
}
QTabBar::tab {
    background: #CFD8DC;
    border: 1px solid #B0BEC5;
    border-bottom: none; /* Create "attached" look */
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 8px 15px;
    color: #37474F;
    margin-right: 2px; /* Space between tabs */
}
QTabBar::tab:selected {
    background: #FFFFFF; /* Selected tab matches pane background */
    color: #1976D2; /* Highlighted text for selected tab */
    border-color: #B0BEC5;
}
QTabBar::tab:hover:!selected {
    background: #B0BEC5;
}

QScrollBar:vertical {
    border: 1px solid #BDBDBD;
    background: #F5F5F5;
    width: 12px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background: #BDBDBD;
    min-height: 20px;
    border-radius: 6px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px; width: 0px;
}
QScrollBar:horizontal {
    border: 1px solid #BDBDBD;
    background: #F5F5F5;
    height: 12px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:horizontal {
    background: #BDBDBD;
    min-width: 20px;
    border-radius: 6px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0px; width: 0px;
}

QToolTip {
    border: 1px solid #757575;
    background-color: #FFFFE0; /* Light yellow */
    color: #333333;
    padding: 4px;
    opacity: 220; /* Slightly transparent */
    border-radius: 3px;
}
"""


# --- Utility Functions ---
def get_standard_icon(standard_pixmap_enum_value, fallback_text="?"): # Changed default for fallback
    """
    Tries to get a standard Qt icon. If it fails or the icon is null,
    it creates a fallback icon with the given text.
    """
    icon = QApplication.style().standardIcon(standard_pixmap_enum_value) \
           if QApplication.style() else QIcon()

    if icon.isNull() or standard_pixmap_enum_value is None : # check standard_pixmap_enum_value directly too
        pixmap_size = 24 # Small default size
        pixmap = QPixmap(pixmap_size, pixmap_size)
        pixmap.fill(QColor(200,200,200, 150)) # Semi-transparent grey
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(50,50,50))
        # Draw simple shape for distinction
        if "Del" in fallback_text or "Trash" in fallback_text: # Delete icon hint
             painter.drawLine(5, 5, pixmap_size-5, pixmap_size-5)
             painter.drawLine(pixmap_size-5, 5, 5, pixmap_size-5)
        elif "Save" in fallback_text: # Save icon hint (floppy)
            painter.drawRect(4,4, pixmap_size-8, pixmap_size-8)
            painter.fillRect(6,4, pixmap_size-12, 6, QColor(100,100,100))
        else: # Default fallback
            font = QFont()
            font.setPixelSize(pixmap_size // (1.8 if len(fallback_text) == 1 else 2.5))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignCenter, fallback_text[:2])
        painter.end()
        icon = QIcon(pixmap)
    return icon

# --- MATLAB Connection Handling --- (Code from original prompt, assumed okay for this iteration)
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
            "    chartSFObj.Name = 'BSM_Logic';", # Keep consistent
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
                script_lines.append(f"defaultTransition_{i}.DestinationOClock = 9; % Entry point from left ")
                script_lines.append(f"chartSFObj.defaultTransition = defaultTransition_{i}; % Also works, often needs chart refresh")


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
            "    Simulink.BlockDiagram.arrangeSystem(chartBlockSimulinkPath, 'FullLayout', true, 'Animation', false);", # Auto-layout chart
            "    Simulink.BlockDiagram.arrangeSystem(modelNameVar, 'FullLayout', true, 'Animation', false);",        # Auto-layout model

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
        # ... (rest of MatlabConnection method remains same) ...
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
        # ... (rest of MatlabConnection method remains same) ...
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
            timeout_seconds = 600
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
    def __init__(self, text, mime_type, item_type_data, parent=None):
        super().__init__(text, parent)
        self.mime_type = mime_type
        self.item_type_data = item_type_data
        self.setText(text)
        self.setMinimumHeight(42) # Increased for better touch/click
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Styling now handled by global stylesheet or MainWindow if more specific needed
        # self.setStyleSheet(style_sheet + " QPushButton { border-radius: 5px; text-align: left; padding-left: 5px; }")
        self.setIconSize(QSize(20,20)) # Set default icon size for these buttons
        self.drag_start_position = QPoint()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton): return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance(): return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.item_type_data)
        mime_data.setData(self.mime_type, self.item_type_data.encode())
        drag.setMimeData(mime_data)

        # Improved Drag Pixmap
        pixmap_width = max(150, self.width() + 20)
        pixmap_height = self.height() + 10
        pixmap = QPixmap(QSize(pixmap_width, pixmap_height))
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Dragged item visual
        path = QPainterPath()
        rect = QRectF(2, 2, pixmap_width - 4, pixmap_height - 4) # Leave space for shadow
        path.addRoundedRect(rect, 8, 8)

        # Subtle shadow
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 50)) # Shadow color
        painter.drawPath(path.translated(2,2))

        painter.setBrush(QColor(230, 240, 255, 230)) # Light blue, semi-transparent
        painter.setPen(QPen(QColor(100, 150, 220), 1.5)) # Blueish border
        painter.drawPath(path)

        # Icon and Text
        icon_pix = self.icon().pixmap(QSize(24,24))
        text_x_offset = 12
        icon_y_offset = (pixmap_height - icon_pix.height()) / 2
        if not icon_pix.isNull():
            painter.drawPixmap(int(text_x_offset), int(icon_y_offset), icon_pix)
            text_x_offset += icon_pix.width() + 10

        font = self.font()
        font.setPointSize(font.pointSize() + 1) # Slightly larger text for drag
        painter.setFont(font)
        painter.setPen(QColor(30,30,30)) # Dark text
        text_rect = QRectF(text_x_offset, 0, pixmap_width - text_x_offset - 8, pixmap_height)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos() - self.rect().topLeft() + QPoint(2,2)) # Keep hotspot relative to button click
        drag.exec_(Qt.CopyAction | Qt.MoveAction)


# --- Graphics Items ---
class GraphicsStateItem(QGraphicsRectItem):
    # ... (StateItem remains largely unchanged internally) ...
    Type = QGraphicsItem.UserType + 1
    def type(self): return GraphicsStateItem.Type

    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False,
                 color=None, entry_action="", during_action="", exit_action="", description=""):
        super().__init__(x, y, w, h)
        self.text_label = text
        self.is_initial = is_initial
        self.is_final = is_final
        self.color = QColor(color) if color else QColor("#B2DFDB") # Default tealish color
        self.entry_action = entry_action
        self.during_action = during_action
        self.exit_action = exit_action
        self.description = description

        self._text_color = QColor("#1A237E") # Dark indigo
        self._font = QFont("Segoe UI", 10, QFont.Bold)

        self.setPen(QPen(QColor(50, 80, 100), 2)) # Bluish grey border
        self.setBrush(QBrush(self.color))
        self.setFlags(QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges |
                      QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)

        # Main state body
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 10, 10)
        painter.setPen(self.pen())
        painter.setBrush(self.color)
        painter.drawPath(path)

        # Text
        painter.setPen(self._text_color)
        painter.setFont(self._font)
        text_rect = self.rect().adjusted(10, 10, -10, -10) # More padding
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)

        # Initial state indicator
        if self.is_initial:
            pen_initial = QPen(Qt.black, 2.5)
            brush_initial = QBrush(Qt.black)
            painter.setPen(pen_initial)

            marker_radius = 8
            line_len = 25
            start_marker_center_x = self.rect().left() - line_len - marker_radius
            start_marker_center_y = self.rect().center().y()

            painter.setBrush(brush_initial)
            painter.drawEllipse(QPointF(start_marker_center_x, start_marker_center_y), marker_radius, marker_radius)
            line_start = QPointF(start_marker_center_x + marker_radius, start_marker_center_y)
            line_end = QPointF(self.rect().left(), start_marker_center_y)
            painter.drawLine(line_start, line_end)

            # Arrowhead
            angle = math.atan2(line_end.y() - line_start.y(), line_end.x() - line_start.x())
            arrow_size = 10
            arrow_p1 = line_end - QPointF(math.cos(angle + math.pi / 6) * arrow_size,
                                         math.sin(angle + math.pi / 6) * arrow_size)
            arrow_p2 = line_end - QPointF(math.cos(angle - math.pi / 6) * arrow_size,
                                         math.sin(angle - math.pi / 6) * arrow_size)
            painter.drawPolygon(QPolygonF([line_end, arrow_p1, arrow_p2]))


        # Final state indicator (double border)
        if self.is_final:
            final_pen = QPen(self.pen().color().darker(120), self.pen().widthF() * 0.8)
            painter.setPen(final_pen)
            painter.setBrush(Qt.NoBrush)
            inner_rect = self.rect().adjusted(5, 5, -5, -5)
            painter.drawRoundedRect(inner_rect, 7, 7)

        # Selection highlight
        if self.isSelected():
            pen = QPen(QColor(33, 150, 243, 220), 3, Qt.DotLine) # Blue, thicker, dotted
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            selection_rect = self.boundingRect().adjusted(-2, -2, 2, 2)
            painter.drawRoundedRect(selection_rect, 12, 12)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)

    def get_data(self):
        return {
            'name': self.text_label, 'x': self.x(), 'y': self.y(),
            'width': self.rect().width(), 'height': self.rect().height(),
            'is_initial': self.is_initial, 'is_final': self.is_final,
            'color': self.color.name() if self.color else QColor("#B2DFDB").name(),
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
        new_color = QColor(color_hex) if color_hex else QColor("#B2DFDB")
        if self.color != new_color: self.color = new_color; self.setBrush(self.color); changed = True
        if self.entry_action != entry: self.entry_action = entry; changed = True
        if self.during_action != during: self.during_action = during; changed = True
        if self.exit_action != exit_a: self.exit_action = exit_a; changed = True
        if self.description != desc: self.description = desc; changed = True
        if changed: self.prepareGeometryChange(); self.update()


class GraphicsTransitionItem(QGraphicsPathItem):
    # ... (TransitionItem remains largely unchanged internally) ...
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
        self.color = QColor(color) if color else QColor(0, 105, 92) # Darker teal
        self.description = description
        self.arrow_size = 13
        self._text_color = QColor(20, 20, 20)
        self._font = QFont("Segoe UI", 9)
        self.control_point_offset = QPointF(0,0)

        self.setPen(QPen(self.color, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable)
        self.setZValue(-1) # Behind states
        self.setAcceptHoverEvents(True)
        self.update_path()

    def _compose_label_string(self):
        parts = []
        if self.event_str: parts.append(self.event_str)
        if self.condition_str: parts.append(f"[{self.condition_str}]")
        if self.action_str: parts.append(f"/{{{self.action_str}}}")
        return " ".join(parts)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent):
        self.setPen(QPen(self.color.lighter(130), 3.5)) # Brighter and thicker
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent):
        self.setPen(QPen(self.color, 2.5))
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 30 # Slightly more padding
        path_bounds = self.path().boundingRect()
        current_label = self._compose_label_string()
        if current_label:
            fm = QFontMetrics(self._font)
            text_rect = fm.boundingRect(QRectF(), Qt.AlignLeft, current_label) # Get rect for label
            mid_point = self.path().pointAtPercent(0.5)
            # More generous estimated rect for text label relative to path mid point
            text_render_rect = QRectF(mid_point.x() - text_rect.width() - 20,
                                      mid_point.y() - text_rect.height() - 20,
                                      text_rect.width() * 2 + 40, # Width * 2 + padding
                                      text_rect.height() * 2 + 40) # Height * 2 + padding
            path_bounds = path_bounds.united(text_render_rect)
        return path_bounds.adjusted(-extra, -extra, extra, extra)

    def shape(self):
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(20 + self.pen().widthF()) # Wider for easier selection
        path_stroker.setCapStyle(Qt.RoundCap); path_stroker.setJoinStyle(Qt.RoundJoin)
        return path_stroker.createStroke(self.path())

    def update_path(self):
        if not self.start_item or not self.end_item: self.setPath(QPainterPath()); return

        start_center = self.start_item.sceneBoundingRect().center()
        end_center = self.end_item.sceneBoundingRect().center()
        line_to_target = QLineF(start_center, end_center)
        start_point = self._get_intersection_point(self.start_item, line_to_target)
        line_from_target = QLineF(end_center, start_center)
        end_point = self._get_intersection_point(self.end_item, line_from_target)

        if start_point is None: start_point = start_center
        if end_point is None: end_point = end_center

        path = QPainterPath(start_point)
        if self.start_item == self.end_item: # Self-loop
            rect = self.start_item.sceneBoundingRect()
            loop_radius_x = rect.width() * 0.5
            loop_radius_y = rect.height() * 0.55
            p1 = QPointF(rect.center().x() + loop_radius_x * 0.35, rect.top())
            p2 = QPointF(rect.center().x() - loop_radius_x * 0.35, rect.top())
            ctrl1 = QPointF(p1.x() + loop_radius_x * 0.8, p1.y() - loop_radius_y * 2.5)
            ctrl2 = QPointF(p2.x() - loop_radius_x * 0.8, p2.y() - loop_radius_y * 2.5)
            path.moveTo(p1); path.cubicTo(ctrl1, ctrl2, p2)
            end_point = p2
        else: # Standard transition
            mid_x = (start_point.x() + end_point.x()) / 2; mid_y = (start_point.y() + end_point.y()) / 2
            dx = end_point.x() - start_point.x(); dy = end_point.y() - start_point.y()
            length = math.hypot(dx, dy)
            if length < 1e-6: length = 1e-6 # Avoid div by zero for coincident points
            perp_x = -dy / length; perp_y = dx / length
            ctrl_pt_x = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y()
            ctrl_pt_y = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()
            ctrl_pt = QPointF(ctrl_pt_x, ctrl_pt_y)
            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0: path.lineTo(end_point)
            else: path.quadTo(ctrl_pt, end_point)
        self.setPath(path); self.prepareGeometryChange()

    def _get_intersection_point(self, item: QGraphicsRectItem, line: QLineF):
        item_rect = item.sceneBoundingRect()
        edges = [
            QLineF(item_rect.topLeft(), item_rect.topRight()), QLineF(item_rect.topRight(), item_rect.bottomRight()),
            QLineF(item_rect.bottomRight(), item_rect.bottomLeft()), QLineF(item_rect.bottomLeft(), item_rect.topLeft())
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
        min_dist_sq = QLineF(line.p1(), closest_point).length() ** 2
        for pt in intersect_points[1:]:
            dist_sq = QLineF(line.p1(), pt).length() ** 2
            if dist_sq < min_dist_sq: min_dist_sq = dist_sq; closest_point = pt
        return closest_point

    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty(): return
        painter.setRenderHint(QPainter.Antialiasing)
        current_pen = self.pen()

        if self.isSelected():
            stroker = QPainterPathStroker(); stroker.setWidth(current_pen.widthF() + 10)
            stroker.setCapStyle(Qt.RoundCap); stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path())
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(33, 150, 243, 70)) # Translucent blue
            painter.drawPath(selection_path_shape)

        painter.setPen(current_pen); painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

        if self.path().elementCount() < 1: return
        line_end_point = self.path().pointAtPercent(1.0)
        angle_rad = -self.path().angleAtPercent(0.999) * (math.pi / 180.0) # Corrected for angle dir
        arrow_p1 = line_end_point + QPointF(math.cos(angle_rad - math.pi / 6) * self.arrow_size,
                                           math.sin(angle_rad - math.pi / 6) * self.arrow_size)
        arrow_p2 = line_end_point + QPointF(math.cos(angle_rad + math.pi / 6) * self.arrow_size,
                                           math.sin(angle_rad + math.pi / 6) * self.arrow_size)
        painter.setBrush(current_pen.color()); painter.setPen(Qt.NoPen) # No border for arrow
        painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))

        # Text Label
        current_label = self._compose_label_string()
        if current_label:
            painter.setFont(self._font)
            fm = QFontMetrics(self._font)
            text_rect_orig = fm.boundingRect(QRectF(), Qt.AlignLeft, current_label) # Precise bounds

            # Calculate position slightly offset from path's midpoint, perpendicular to tangent
            mid_point_on_path = self.path().pointAtPercent(0.5)
            angle_at_mid_deg = self.path().angleAtPercent(0.5)
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0) # Perpendicular up/left
            offset_dist = 15 # Pixels from the line

            # Calculate text top-left based on center point, rect width/height
            text_center_x = mid_point_on_path.x() + offset_dist * math.cos(offset_angle_rad)
            text_center_y = mid_point_on_path.y() + offset_dist * math.sin(offset_angle_rad)
            text_draw_pos = QPointF(text_center_x - text_rect_orig.width() / 2,
                                    text_center_y - text_rect_orig.height() / 2)

            # Background for text
            bg_padding = 4
            bg_rect = text_rect_orig.translated(text_draw_pos).adjusted(-bg_padding, -bg_padding, bg_padding, bg_padding)
            painter.setBrush(QColor(250, 250, 250, 210)) # Semi-transparent white
            painter.setPen(QPen(QColor(200,200,200,180), 0.8)) # Faint border
            painter.drawRoundedRect(bg_rect, 5, 5)

            painter.setPen(self._text_color)
            painter.drawText(text_draw_pos, current_label)

    def get_data(self):
        return {
            'source': self.start_item.text_label if self.start_item else "None",
            'target': self.end_item.text_label if self.end_item else "None",
            'event': self.event_str, 'condition': self.condition_str, 'action': self.action_str,
            'color': self.color.name() if self.color else QColor(0,105,92).name(),
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
        new_color = QColor(color_hex) if color_hex else QColor(0,105,92)
        if self.color != new_color: self.color = new_color; self.setPen(QPen(self.color, self.pen().widthF())); changed=True
        if offset is not None and self.control_point_offset != offset: self.control_point_offset = offset; changed=True
        if changed:
            self.prepareGeometryChange()
            if offset is not None : self.update_path()
            self.update()

    def set_control_point_offset(self, offset: QPointF):
        if self.control_point_offset != offset:
            self.control_point_offset = offset; self.update_path(); self.update()


class GraphicsCommentItem(QGraphicsTextItem):
    # ... (CommentItem remains largely unchanged internally) ...
    Type = QGraphicsItem.UserType + 3
    def type(self): return GraphicsCommentItem.Type

    def __init__(self, x, y, text="Comment"):
        super().__init__()
        self.setPlainText(text); self.setPos(x,y)
        self.setFont(QFont("Segoe UI", 10, QFont.StyleItalic))
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self._default_width = 160; self._default_height = 70
        self.setTextWidth(self._default_width); self.adjust_size_to_text()
        self.border_pen = QPen(QColor(220, 198, 111), 1.5) # Gold-ish
        self.background_brush = QBrush(QColor(255, 249, 196, 220)) # Light yellow sticky-note like

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        bg_rect = self.boundingRect()
        # Subtle "dog-ear" or shadow effect might be too much, simple rounded rect is good
        painter.setPen(self.border_pen)
        painter.setBrush(self.background_brush)
        painter.drawRoundedRect(bg_rect, 8, 8)
        super().paint(painter, option, widget) # Draws text
        if self.isSelected():
            pen = QPen(QColor(33, 150, 243, 200), 2, Qt.DashLine)
            painter.setPen(pen); painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(bg_rect.adjusted(-1,-1,1,1), 9, 9)

    def get_data(self): return {'text': self.toPlainText(), 'x': self.x(), 'y': self.y(), 'width': self.boundingRect().width()}
    def set_properties(self, text, width=None): self.setPlainText(text); self.setTextWidth(width if width else self._default_width); self.adjust_size_to_text(); self.update()
    def adjust_size_to_text(self): self.prepareGeometryChange(); self.update() # Document height usually manages this
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene(): self.scene().item_moved.emit(self)
        return super().itemChange(change, value)


# --- Undo Commands --- (Assumed okay, focusing on GUI. Review if issues arise.)
class AddItemCommand(QUndoCommand): # ... as before
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item_instance = item
        if isinstance(item, GraphicsTransitionItem):
            self.item_data = item.get_data()
            self.start_item_name = item.start_item.text_label if item.start_item else None
            self.end_item_name = item.end_item.text_label if item.end_item else None
        elif isinstance(item, GraphicsStateItem) or isinstance(item, GraphicsCommentItem):
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
                self.scene.log_function(f"Error (Redo Add Transition): Could not link. State(s) missing for '{self.item_data.get('event', 'Unnamed Transition')}'.")
        self.scene.clearSelection()
        self.item_instance.setSelected(True)
        self.scene.set_dirty(True)

    def undo(self):
        self.scene.removeItem(self.item_instance)
        self.scene.set_dirty(True)

class RemoveItemsCommand(QUndoCommand): # ... as before
    def __init__(self, scene, items_to_remove, description="Remove Items"):
        super().__init__(description)
        self.scene = scene
        self.removed_items_data = []
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
        newly_re_added_instances = []
        states_map_for_undo = {}
        for item_data in self.removed_items_data: # Restore states and comments first
            instance_to_add = None
            if item_data['_type'] == GraphicsStateItem.Type:
                state = GraphicsStateItem(item_data['x'], item_data['y'], item_data['width'], item_data['height'],
                    item_data['name'], item_data['is_initial'], item_data['is_final'], item_data.get('color'),
                    item_data.get('entry_action', ""), item_data.get('during_action', ""),
                    item_data.get('exit_action', ""), item_data.get('description', ""))
                instance_to_add = state; states_map_for_undo[state.text_label] = state
            elif item_data['_type'] == GraphicsCommentItem.Type:
                comment = GraphicsCommentItem(item_data['x'], item_data['y'], item_data['text'])
                comment.setTextWidth(item_data.get('width', 150)); instance_to_add = comment
            if instance_to_add: self.scene.addItem(instance_to_add); newly_re_added_instances.append(instance_to_add)

        for item_data in self.removed_items_data: # Restore transitions
            if item_data['_type'] == GraphicsTransitionItem.Type:
                src_item = states_map_for_undo.get(item_data['_start_name'])
                tgt_item = states_map_for_undo.get(item_data['_end_name'])
                if src_item and tgt_item:
                    trans = GraphicsTransitionItem(src_item, tgt_item, event_str=item_data['event'], condition_str=item_data['condition'],
                                                   action_str=item_data['action'], color=item_data.get('color'), description=item_data.get('description',""))
                    trans.set_control_point_offset(QPointF(item_data['control_offset_x'], item_data['control_offset_y']))
                    self.scene.addItem(trans); newly_re_added_instances.append(trans)
                else: self.scene.log_function(f"Error (Undo Remove): Cound not re-link transition. States missing.")
        self.item_instances_for_quick_toggle = newly_re_added_instances
        self.scene.set_dirty(True)

class MoveItemsCommand(QUndoCommand): # ... as before
    def __init__(self, items_and_new_positions, description="Move Items"):
        super().__init__(description)
        self.items_and_new_positions = items_and_new_positions
        self.items_and_old_positions = []
        self.scene_ref = None
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

class EditItemPropertiesCommand(QUndoCommand): # ... as before
    def __init__(self, item, old_props_data, new_props_data, description="Edit Properties"):
        super().__init__(description)
        self.item = item; self.old_props_data = old_props_data
        self.new_props_data = new_props_data; self.scene_ref = item.scene()

    def _apply_properties(self, props_to_apply):
        if not self.item or not self.scene_ref: return
        original_name_if_state = None
        if isinstance(self.item, GraphicsStateItem):
            original_name_if_state = self.item.text_label
            self.item.set_properties(props_to_apply['name'], props_to_apply.get('is_initial', False), props_to_apply.get('is_final', False),
                props_to_apply.get('color'), props_to_apply.get('entry_action', ""), props_to_apply.get('during_action', ""),
                props_to_apply.get('exit_action', ""), props_to_apply.get('description', ""))
            if original_name_if_state != props_to_apply['name']:
                self.scene_ref._update_transitions_for_renamed_state(original_name_if_state, props_to_apply['name'])
        elif isinstance(self.item, GraphicsTransitionItem):
            self.item.set_properties(event_str=props_to_apply.get('event',""), condition_str=props_to_apply.get('condition',""),
                action_str=props_to_apply.get('action',""), color_hex=props_to_apply.get('color'),
                description=props_to_apply.get('description',""),
                offset=QPointF(props_to_apply['control_offset_x'], props_to_apply['control_offset_y']))
        elif isinstance(self.item, GraphicsCommentItem):
            self.item.set_properties(text=props_to_apply['text'], width=props_to_apply.get('width'))
        self.item.update(); self.scene_ref.update(); self.scene_ref.set_dirty(True)

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
        self.grid_pen_light = QPen(QColor(220, 225, 230), 0.8, Qt.SolidLine)
        self.grid_pen_dark = QPen(QColor(195, 200, 205), 1.0, Qt.SolidLine)
        self.setBackgroundBrush(QColor(245, 247, 249)) # Very light grey/blue background
        self.snap_to_grid_enabled = True

    def _update_connected_transitions(self, state_item: GraphicsStateItem):
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                if item.start_item == state_item or item.end_item == state_item:
                    item.update_path()

    def _update_transitions_for_renamed_state(self, old_name:str, new_name:str):
        self.log_function(f"State '{old_name}' renamed to '{new_name}'. (Internal data logic)")

    def get_state_by_name(self, name: str):
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name:
                return item
        return None

    def set_dirty(self, dirty=True):
        if self._dirty != dirty:
            self._dirty = dirty
            self.modifiedStatusChanged.emit(dirty)
            if self.parent_window: self.parent_window._update_save_actions_enable_state()

    def is_dirty(self): return self._dirty
    def set_log_function(self, log_function): self.log_function = log_function

    def set_mode(self, mode: str):
        old_mode = self.current_mode
        if old_mode == mode: return
        self.current_mode = mode
        self.log_function(f"Interaction mode changed to: {mode}")

        self.transition_start_item = None
        if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None

        if mode == "select": QApplication.setOverrideCursor(Qt.ArrowCursor)
        elif mode == "state" or mode == "comment": QApplication.setOverrideCursor(Qt.CrossCursor)
        elif mode == "transition": QApplication.setOverrideCursor(Qt.PointingHandCursor)

        for item in self.items(): # Manage movability
            can_move = mode == "select"
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)):
                 item.setFlag(QGraphicsItem.ItemIsMovable, can_move)

        if old_mode in ["state", "transition", "comment"] and mode not in ["state", "transition", "comment"]:
            QApplication.restoreOverrideCursor()

        if self.parent_window: # Ensure toolbar buttons are checked correctly
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
            if item.flags() & QGraphicsItem.ItemIsSelectable: item.setSelected(True)

    def _handle_item_moved(self, moved_item):
        if isinstance(moved_item, GraphicsStateItem):
            self._update_connected_transitions(moved_item)
        # Snapping for both state and comment handled in mouseReleaseEvent

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos()
        items_at_pos = self.items(pos)
        top_item_at_pos = None
        if items_at_pos:
            # Prioritize: State > Transition > Comment > Other
            type_priority = [GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem]
            for item_type in type_priority:
                top_item_at_pos = next((it for it in items_at_pos if isinstance(it, item_type)), None)
                if top_item_at_pos: break
            if not top_item_at_pos: top_item_at_pos = items_at_pos[0]

        if event.button() == Qt.LeftButton:
            if self.current_mode in ["state", "comment"]:
                grid_pos = self._snap_to_grid(pos)
                self._add_item_interactive(grid_pos, item_type=self.current_mode.capitalize())
            elif self.current_mode == "transition":
                if isinstance(top_item_at_pos, GraphicsStateItem): self._handle_transition_click(top_item_at_pos, pos)
                else: self.transition_start_item = None; # Cancel on empty click
                      if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
            else: # Select mode
                self._mouse_press_items_positions.clear()
                selected_movable = [item for item in self.selectedItems() if item.flags() & QGraphicsItem.ItemIsMovable]
                for item in selected_movable: self._mouse_press_items_positions[item] = item.pos()
                super().mousePressEvent(event)

        elif event.button() == Qt.RightButton: # Context menu
            if top_item_at_pos and isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem)):
                if not top_item_at_pos.isSelected():
                    self.clearSelection(); top_item_at_pos.setSelected(True)
                self._show_context_menu(top_item_at_pos, event.screenPos())
            else: # Right-click on empty canvas
                self.clearSelection()
                self._show_scene_context_menu(event.screenPos(), event.scenePos())
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, event.scenePos()))
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            if self._mouse_press_items_positions:
                moved_items_data = []
                for item, old_pos in self._mouse_press_items_positions.items():
                    current_item_pos = item.pos()
                    if self.snap_to_grid_enabled:
                        snapped_pos = self._snap_to_grid(current_item_pos)
                        if snapped_pos != current_item_pos : item.setPos(snapped_pos); current_item_pos = snapped_pos

                    if (current_item_pos - old_pos).manhattanLength() > 0.1:
                        moved_items_data.append((item, current_item_pos)) # (item, NEW pos)

                if moved_items_data:
                    cmd = MoveItemsCommand(moved_items_data) # Pass list of (item, new_pos) tuples
                    self.undo_stack.push(cmd)
                self._mouse_press_items_positions.clear()
        super().mouseReleaseEvent(event)

    def _snap_to_grid(self, pos: QPointF) -> QPointF:
        if not self.snap_to_grid_enabled: return pos
        return QPointF(round(pos.x() / self.grid_size) * self.grid_size,
                       round(pos.y() / self.grid_size) * self.grid_size)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        items_at_pos = self.items(event.scenePos())
        item_to_edit = next((item for item in items_at_pos if isinstance(item, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem))), None)
        if item_to_edit: self.edit_item_properties(item_to_edit)
        else: super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, item, global_pos):
        menu = QMenu(self.parent_window) # Ensure parent for styling
        # Stylesheet is now global or in main_window, this specific style might not be needed if global covers it.
        # menu.setStyleSheet(self.parent_window.styleSheet()) # Apply app style

        edit_action = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        delete_action = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")

        action = menu.exec_(global_pos)
        if action == edit_action: self.edit_item_properties(item)
        elif action == delete_action:
            if not item.isSelected(): self.clearSelection(); item.setSelected(True)
            self.delete_selected_items()

    def _show_scene_context_menu(self, global_pos, scene_pos):
        menu = QMenu(self.parent_window)
        add_state_action = menu.addAction(get_standard_icon(QStyle.SP_FileDialogNewFolder, "St"), "Add State Here")
        add_comment_action = menu.addAction(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"), "Add Comment Here")
        # Paste action (example - implement _handle_paste if needed)
        # paste_action = menu.addAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "Pst"), "Paste")
        # paste_action.setEnabled(QApplication.clipboard().mimeData().hasFormat("application/x-bsm-item-data"))

        action = menu.exec_(global_pos)
        grid_pos = self._snap_to_grid(scene_pos) # Snap to grid
        if action == add_state_action:
            self._add_item_interactive(grid_pos, item_type="State", name_prefix="State")
        elif action == add_comment_action:
            self._add_item_interactive(grid_pos, item_type="Comment", name_prefix="Comment")
        # elif action == paste_action: self._handle_paste(scene_pos)

    def edit_item_properties(self, item):
        old_props = item.get_data()
        dialog_executed_and_accepted = False
        new_props = {}

        if isinstance(item, GraphicsStateItem):
            dialog = StatePropertiesDialog(parent=self.parent_window, current_properties=old_props)
            if dialog.exec_() == QDialog.Accepted: dialog_executed_and_accepted = True; new_props = dialog.get_properties()
                if new_props['name'] != old_props['name'] and self.get_state_by_name(new_props['name']):
                    QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state named '{new_props['name']}' already exists."); return
        elif isinstance(item, GraphicsTransitionItem):
            dialog = TransitionPropertiesDialog(parent=self.parent_window, current_properties=old_props)
            if dialog.exec_() == QDialog.Accepted: dialog_executed_and_accepted = True; new_props = dialog.get_properties()
        elif isinstance(item, GraphicsCommentItem):
            dialog = CommentPropertiesDialog(parent=self.parent_window, current_properties=old_props)
            if dialog.exec_() == QDialog.Accepted: dialog_executed_and_accepted = True; new_props = dialog.get_properties()
        else: return

        if dialog_executed_and_accepted:
            final_new_props = old_props.copy(); final_new_props.update(new_props)
            cmd = EditItemPropertiesCommand(item, old_props, final_new_props, f"Edit {type(item).__name__} Props")
            self.undo_stack.push(cmd)
            item_name_for_log = final_new_props.get('name', final_new_props.get('event', final_new_props.get('text', 'Item')))
            self.log_function(f"Properties updated for: {item_name_for_log}")
        self.update()

    def _add_item_interactive(self, pos: QPointF, item_type: str, name_prefix:str="Item", initial_data:dict=None):
        current_item = None
        final_props = {}
        # Use self._snap_to_grid for item placement for consistent alignment
        # For States, snap to center if width/height known, else top-left
        item_x, item_y = pos.x(), pos.y()


        if item_type == "State":
            base_name = initial_data.get("base_name_suggestion", name_prefix) if initial_data else name_prefix
            i = 1
            while self.get_state_by_name(f"{base_name}{i}"): i += 1
            default_name = f"{base_name}{i}"

            props_for_dialog = {
                'name': default_name, 'is_initial': False, 'is_final': False,
                'color': QColor("#B2DFDB").name() # Default new state color
            }
            if initial_data: props_for_dialog.update(initial_data) # Override with any passed data (e.g. for drag-drop)

            # Snap state center to grid_pos
            item_width_half, item_height_half = 120/2, 60/2
            item_x = pos.x() - item_width_half
            item_y = pos.y() - item_height_half
            snapped_top_left = self._snap_to_grid(QPointF(item_x, item_y))


            dialog = StatePropertiesDialog(self.parent_window, current_properties=props_for_dialog, is_new_state=True)
            if dialog.exec_() == QDialog.Accepted: final_props = dialog.get_properties()
            else: self.set_mode("select"); return # Cancelled dialog

            if self.get_state_by_name(final_props['name']): # Final check for name duplication
                 QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state named '{final_props['name']}' already exists.")
                 self.set_mode("select"); return

            current_item = GraphicsStateItem(
                snapped_top_left.x(), snapped_top_left.y(), 120, 60, # Use snapped top-left for creation
                final_props['name'], final_props['is_initial'], final_props['is_final'],
                final_props.get('color'), final_props.get('entry_action',""), final_props.get('during_action',""),
                final_props.get('exit_action',""), final_props.get('description',"") )

        elif item_type == "Comment":
            initial_text = initial_data.get('text', "Double-click to edit") if initial_data else "Double-click to edit"
            # Comments: snap top-left to grid pos directly
            snapped_top_left = self._snap_to_grid(pos)
            # Simpler creation, edit properties via double-click or context menu later.
            current_item = GraphicsCommentItem(snapped_top_left.x(), snapped_top_left.y(), initial_text)

        else: self.log_function(f"Unknown item type for addition: {item_type}"); return

        if current_item:
            cmd = AddItemCommand(self, current_item, f"Add {item_type}")
            self.undo_stack.push(cmd)
            log_name = getattr(current_item, 'text_label', getattr(current_item, 'toPlainText', lambda: "Item")())
            self.log_function(f"Added {item_type}: {log_name} at ({item_x:.0f},{item_y:.0f})")
        self.set_mode("select")


    def _handle_transition_click(self, clicked_state_item: GraphicsStateItem, click_pos: QPointF):
        if not self.transition_start_item:
            self.transition_start_item = clicked_state_item
            if not self._temp_transition_line:
                self._temp_transition_line = QGraphicsLineItem()
                pen = QPen(QColor(50,50,50, 180), 2.5, Qt.DashLine)
                pen.setDashPattern([4, 4])
                self._temp_transition_line.setPen(pen)
                self.addItem(self._temp_transition_line)
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, click_pos))
            self.log_function(f"Transition started from: {clicked_state_item.text_label}. Click target state.")
        else:
            if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
            props_dialog = TransitionPropertiesDialog(self.parent_window, current_properties=None, is_new_transition=True)
            if props_dialog.exec_() == QDialog.Accepted:
                props = props_dialog.get_properties()
                new_trans = GraphicsTransitionItem(
                    self.transition_start_item, clicked_state_item,
                    props['event'], props['condition'], props['action'],
                    props.get('color'), props.get('description',""))
                new_trans.set_control_point_offset(QPointF(props['control_offset_x'],props['control_offset_y']))
                cmd = AddItemCommand(self, new_trans, "Add Transition")
                self.undo_stack.push(cmd)
                self.log_function(f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} {new_trans._compose_label_string()}")
            else: self.log_function("Transition addition cancelled.")
            self.transition_start_item = None
            self.set_mode("select")


    def keyPressEvent(self, event: QKeyEvent):
        # ... (keyPressEvent remains same, relies on selectedItems and scene modes)
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            if self.selectedItems(): self.delete_selected_items()
        elif event.key() == Qt.Key_Escape:
            if self.current_mode == "transition" and self.transition_start_item:
                self.transition_start_item = None
                if self._temp_transition_line: self.removeItem(self._temp_transition_line); self._temp_transition_line = None
                self.log_function("Transition drawing cancelled by Escape.")
                self.set_mode("select")
            elif self.current_mode != "select": self.set_mode("select")
            else: self.clearSelection()
        else: super().keyPressEvent(event)

    def delete_selected_items(self):
        selected = self.selectedItems()
        if not selected: return
        items_to_delete = set(selected)
        for item in selected: # If deleting state, also remove its transitions
            if isinstance(item, GraphicsStateItem):
                for scene_item in self.items():
                    if isinstance(scene_item, GraphicsTransitionItem) and \
                       (scene_item.start_item == item or scene_item.end_item == item):
                        items_to_delete.add(scene_item)
        if items_to_delete:
            cmd = RemoveItemsCommand(self, list(items_to_delete), "Delete Items")
            self.undo_stack.push(cmd)
            self.log_function(f"Queued deletion of {len(items_to_delete)} item(s).")
            self.clearSelection()

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            event.setAccepted(True); event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"): event.acceptProposedAction()
        else: super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        pos = event.scenePos()
        snapped_pos = self._snap_to_grid(pos) # Use snapped pos for dropping
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            item_type_data_str = event.mimeData().text()
            initial_props_for_add = {'color': QColor("#B2DFDB").name()} # Default color from GraphicsStateItem
            item_type_to_add = "Item"
            name_prefix = "Item"

            if item_type_data_str == "State":
                item_type_to_add = "State"; name_prefix = "State"
            elif item_type_data_str == "Initial State":
                item_type_to_add = "State"; name_prefix = "Initial"; initial_props_for_add['is_initial'] = True
                initial_props_for_add['color'] = QColor("#C8E6C9").name() # Light green for initial
            elif item_type_data_str == "Final State":
                item_type_to_add = "State"; name_prefix = "Final"; initial_props_for_add['is_final'] = True
                initial_props_for_add['color'] = QColor("#FFCDD2").name() # Light red for final
            elif item_type_data_str == "Comment":
                item_type_to_add = "Comment"; name_prefix = "Note"
            else: event.ignore(); return

            # Provide a base name suggestion for the dialog if it's a state being dropped
            if "State" in item_type_to_add : initial_props_for_add["base_name_suggestion"] = name_prefix

            self._add_item_interactive(snapped_pos, item_type=item_type_to_add,
                                     name_prefix=name_prefix, initial_data=initial_props_for_add)
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
        self.clear(); self.set_dirty(False)
        state_items_map = {}
        for state_data in data.get('states', []):
            state_item = GraphicsStateItem(
                state_data['x'], state_data['y'], state_data.get('width', 120), state_data.get('height', 60),
                state_data['name'], state_data.get('is_initial', False), state_data.get('is_final', False),
                state_data.get('color'), state_data.get('entry_action',""), state_data.get('during_action',""),
                state_data.get('exit_action',""), state_data.get('description',""))
            self.addItem(state_item); state_items_map[state_data['name']] = state_item
        for trans_data in data.get('transitions', []):
            src_item = state_items_map.get(trans_data['source']); tgt_item = state_items_map.get(trans_data['target'])
            if src_item and tgt_item:
                trans_item = GraphicsTransitionItem(src_item, tgt_item,
                    event_str=trans_data.get('event',""), condition_str=trans_data.get('condition',""),
                    action_str=trans_data.get('action',""), color=trans_data.get('color'),
                    description=trans_data.get('description',""))
                trans_item.set_control_point_offset(QPointF(
                    trans_data.get('control_offset_x', 0), trans_data.get('control_offset_y', 0)))
                self.addItem(trans_item)
            else: self.log_function(f"Warning (Load): Could not link transition. Missing states for source='{trans_data['source']}', target='{trans_data['target']}'.")
        for comment_data in data.get('comments', []):
            comment_item = GraphicsCommentItem(comment_data['x'], comment_data['y'], comment_data.get('text', ""))
            comment_item.setTextWidth(comment_data.get('width', 150)); self.addItem(comment_item)
        self.set_dirty(False); self.undo_stack.clear()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        view_rect = self.views()[0].viewport().rect() if self.views() else rect
        visible_scene_rect = self.views()[0].mapToScene(view_rect).boundingRect() if self.views() else rect
        left = int(visible_scene_rect.left()); right = int(visible_scene_rect.right())
        top = int(visible_scene_rect.top()); bottom = int(visible_scene_rect.bottom())
        first_left = left - (left % self.grid_size); first_top = top - (top % self.grid_size)

        lines_light = []
        lines_dark = []
        major_interval = self.grid_size * 5

        for x in range(first_left, right, self.grid_size):
            if x % major_interval == 0: lines_dark.append(QLineF(x, top, x, bottom))
            else: lines_light.append(QLineF(x, top, x, bottom))
        for y in range(first_top, bottom, self.grid_size):
            if y % major_interval == 0: lines_dark.append(QLineF(left, y, right, y))
            else: lines_light.append(QLineF(left, y, right, y))

        painter.setPen(self.grid_pen_light); painter.drawLines(lines_light)
        painter.setPen(self.grid_pen_dark); painter.drawLines(lines_dark)


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
        self._is_panning_with_space = False
        self._is_panning_with_mouse_button = False
        self._last_pan_point = QPoint()
        self.setStyleSheet("border: 1px solid #B0BEC5; border-radius: 4px;") # Style the view itself

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.12 if delta > 0 else 1 / 1.12
            new_zoom_level = self.zoom_level + (1 if delta > 0 else -1)
            if -20 <= new_zoom_level <= 30: # Adjusted zoom limits
                self.scale(factor, factor); self.zoom_level = new_zoom_level
            event.accept()
        else: super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = True; self._last_pan_point = event.pos()
            self.setCursor(Qt.OpenHandCursor); event.accept()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal: self.zoom_in()
        elif event.key() == Qt.Key_Minus: self.zoom_out()
        elif event.key() == Qt.Key_0 or event.key() == Qt.Key_Asterisk: self.reset_zoom_and_fit()
        else: super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = False
            if not self._is_panning_with_mouse_button: self._restore_cursor_to_scene_mode()
            event.accept()
        else: super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton or \
           (self._is_panning_with_space and event.button() == Qt.LeftButton):
            self._last_pan_point = event.pos(); self.setCursor(Qt.ClosedHandCursor)
            self._is_panning_with_mouse_button = True; event.accept()
        else: self._is_panning_with_mouse_button = False; super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button:
            delta_view = event.pos() - self._last_pan_point; self._last_pan_point = event.pos()
            hsbar = self.horizontalScrollBar(); vsbar = self.verticalScrollBar()
            hsbar.setValue(hsbar.value() - delta_view.x()); vsbar.setValue(vsbar.value() - delta_view.y())
            event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button and \
           (event.button() == Qt.MiddleButton or (self._is_panning_with_space and event.button() == Qt.LeftButton)):
            self._is_panning_with_mouse_button = False
            if self._is_panning_with_space: self.setCursor(Qt.OpenHandCursor)
            else: self._restore_cursor_to_scene_mode()
            event.accept()
        else: super().mouseReleaseEvent(event)

    def _restore_cursor_to_scene_mode(self):
        current_scene_mode = self.scene().current_mode if self.scene() else "select"
        cursors = {"select": Qt.ArrowCursor, "state": Qt.CrossCursor, "comment": Qt.CrossCursor, "transition": Qt.PointingHandCursor}
        self.setCursor(cursors.get(current_scene_mode, Qt.ArrowCursor))

    def zoom_in(self): self.scale(1.12, 1.12); self.zoom_level +=1
    def zoom_out(self): self.scale(1/1.12, 1/1.12); self.zoom_level -=1
    def reset_zoom_and_fit(self):
        self.resetTransform(); self.zoom_level = 0
        self.fit_to_content()

    def fit_to_content(self):
        if self.scene():
            items_rect = self.scene().itemsBoundingRect()
            if not items_rect.isEmpty():
                # Add padding to ensure items are not at the very edge
                padded_rect = items_rect.adjusted(-50, -50, 50, 50)
                self.fitInView(padded_rect, Qt.KeepAspectRatio)
            else: # No items, center view on a default area
                self.centerOn(self.scene().sceneRect().center())

# --- Dialogs ---
class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Props"))
        self.setMinimumWidth(480) # Increased width for tabs

        main_layout = QVBoxLayout(self)
        tab_widget = QTabWidget()
        p = current_properties or {}

        # General Tab
        general_tab = QWidget()
        form_layout = QFormLayout(general_tab)
        form_layout.setSpacing(10)
        self.name_edit = QLineEdit(p.get('name', "StateName"))
        self.name_edit.setPlaceholderText("Unique state name (alphanumeric, underscores)")
        self.is_initial_cb = QCheckBox("Is Initial State"); self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Is Final State"); self.is_final_cb.setChecked(p.get('is_final', False))
        self.color_button = QPushButton("Choose Color...")
        self.current_color = QColor(p.get('color', "#B2DFDB")) # Default: Teal 200
        self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)
        form_layout.addRow("Name:", self.name_edit)
        form_layout.addRow(self.is_initial_cb)
        form_layout.addRow(self.is_final_cb)
        form_layout.addRow("Color:", self.color_button)
        tab_widget.addTab(general_tab, "General")

        # Actions Tab
        actions_tab = QWidget()
        actions_layout = QFormLayout(actions_tab)
        actions_layout.setSpacing(10)
        self.entry_action_edit = QTextEdit(p.get('entry_action', "")); self.entry_action_edit.setPlaceholderText("MATLAB code executed on entry")
        self.during_action_edit = QTextEdit(p.get('during_action', "")); self.during_action_edit.setPlaceholderText("MATLAB code executed while active")
        self.exit_action_edit = QTextEdit(p.get('exit_action', "")); self.exit_action_edit.setPlaceholderText("MATLAB code executed on exit")
        for editor in [self.entry_action_edit, self.during_action_edit, self.exit_action_edit]: editor.setFixedHeight(70); editor.setFont(QFont("Consolas", 9))
        actions_layout.addRow("Entry Action:", self.entry_action_edit)
        actions_layout.addRow("During Action:", self.during_action_edit)
        actions_layout.addRow("Exit Action:", self.exit_action_edit)
        tab_widget.addTab(actions_tab, "Actions")

        # Description Tab
        desc_tab = QWidget()
        desc_layout = QVBoxLayout(desc_tab)
        desc_layout.setContentsMargins(5,5,5,5)
        self.description_edit = QTextEdit(p.get('description', ""))
        self.description_edit.setPlaceholderText("Optional notes or detailed description about this state's purpose and behavior.")
        self.description_edit.setMinimumHeight(100)
        desc_layout.addWidget(QLabel("Description:"))
        desc_layout.addWidget(self.description_edit)
        tab_widget.addTab(desc_tab, "Description")

        main_layout.addWidget(tab_widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        if is_new_state: self.name_edit.selectAll(); self.name_edit.setFocus()

    def _choose_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select State Color", QColorDialog.ShowAlphaChannel)
        if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self):
        palette = self.current_color.lightnessF() > 0.5
        text_color = "black" if palette else "white"
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color}; border: 1px solid grey;")

    def get_properties(self):
        return {
            'name': self.name_edit.text().strip(), 'is_initial': self.is_initial_cb.isChecked(),
            'is_final': self.is_final_cb.isChecked(), 'color': self.current_color.name(),
            'entry_action': self.entry_action_edit.toPlainText().strip(),
            'during_action': self.during_action_edit.toPlainText().strip(),
            'exit_action': self.exit_action_edit.toPlainText().strip(),
            'description': self.description_edit.toPlainText().strip()}

class TransitionPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Props"))
        self.setMinimumWidth(480)

        main_layout = QVBoxLayout(self)
        tab_widget = QTabWidget()
        p = current_properties or {}

        # Logic Tab
        logic_tab = QWidget()
        form_layout = QFormLayout(logic_tab)
        form_layout.setSpacing(10)
        self.event_edit = QLineEdit(p.get('event', "")); self.event_edit.setPlaceholderText("e.g., timeout_event, data_received")
        self.condition_edit = QLineEdit(p.get('condition', "")); self.condition_edit.setPlaceholderText("Guard: e.g., input_val > threshold && attempts < 3")
        self.action_edit = QTextEdit(p.get('action', "")); self.action_edit.setPlaceholderText("MATLAB code: e.g., counter = 0; update_display();")
        self.action_edit.setFixedHeight(70); self.action_edit.setFont(QFont("Consolas", 9))
        form_layout.addRow("Event Trigger:", self.event_edit)
        form_layout.addRow("Condition (Guard):", self.condition_edit)
        form_layout.addRow("Transition Action:", self.action_edit)
        tab_widget.addTab(logic_tab, "Logic")

        # Appearance Tab
        appearance_tab = QWidget()
        app_layout = QFormLayout(appearance_tab)
        app_layout.setSpacing(10)
        self.color_button = QPushButton("Choose Color...")
        self.current_color = QColor(p.get('color', "#00695C")) # Default: Dark Teal
        self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)
        self.offset_perp_spin = QSpinBox(); self.offset_perp_spin.setRange(-800, 800); self.offset_perp_spin.setSingleStep(5); self.offset_perp_spin.setValue(int(p.get('control_offset_x', 0)))
        self.offset_perp_spin.setToolTip("Perpendicular curve bend. 0 = straight.")
        self.offset_tang_spin = QSpinBox(); self.offset_tang_spin.setRange(-800, 800); self.offset_tang_spin.setSingleStep(5); self.offset_tang_spin.setValue(int(p.get('control_offset_y', 0)))
        self.offset_tang_spin.setToolTip("Tangential shift of curve midpoint.")
        app_layout.addRow("Color:", self.color_button)
        app_layout.addRow("Curve Bend (Perp.):", self.offset_perp_spin)
        app_layout.addRow("Curve Shift (Tang.):", self.offset_tang_spin)
        tab_widget.addTab(appearance_tab, "Appearance")

        # Description Tab
        desc_tab = QWidget()
        desc_layout = QVBoxLayout(desc_tab)
        self.description_edit = QTextEdit(p.get('description', ""))
        self.description_edit.setPlaceholderText("Optional notes about this transition's conditions or purpose.")
        self.description_edit.setMinimumHeight(100)
        desc_layout.addWidget(QLabel("Description:"))
        desc_layout.addWidget(self.description_edit)
        tab_widget.addTab(desc_tab, "Description")

        main_layout.addWidget(tab_widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        if is_new_transition: self.event_edit.setFocus()

    def _choose_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select Transition Color", QColorDialog.ShowAlphaChannel)
        if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self):
        palette = self.current_color.lightnessF() > 0.5
        text_color = "black" if palette else "white"
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color}; border: 1px solid grey;")

    def get_properties(self):
        return {'event': self.event_edit.text().strip(), 'condition': self.condition_edit.text().strip(),
                'action': self.action_edit.toPlainText().strip(), 'color': self.current_color.name(),
                'control_offset_x': self.offset_perp_spin.value(), 'control_offset_y': self.offset_tang_spin.value(),
                'description': self.description_edit.toPlainText().strip()}

class CommentPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent)
        self.setWindowTitle("Comment Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cm"))
        self.setMinimumWidth(400)
        p = current_properties or {}
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.text_edit = QTextEdit(p.get('text', "Enter comment..."))
        self.text_edit.setMinimumHeight(120)
        self.text_edit.setPlaceholderText("Detailed notes or annotations for the diagram.")
        layout.addWidget(QLabel("Comment Text:"))
        layout.addWidget(self.text_edit)

        # No width spinbox, let user resize or QGraphicsTextItem auto-width.
        # Width can be implicitly set by drag-resizing comment item in future, or manual value here if added.

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.text_edit.setFocus(); self.text_edit.selectAll()

    def get_properties(self):
        return {'text': self.text_edit.toPlainText().strip()}

class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings")
        self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"))
        self.setMinimumWidth(600)

        main_layout = QVBoxLayout(self); self.setLayout(main_layout)

        path_group = QGroupBox("MATLAB Executable Path")
        path_v_layout = QVBoxLayout(); path_group.setLayout(path_v_layout)
        path_form_layout = QFormLayout()
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path)
        self.path_edit.setPlaceholderText("e.g., /usr/local/MATLAB/R202Xy/bin/matlab or C:\\...\\matlab.exe")
        path_form_layout.addRow("Path:", self.path_edit)
        path_v_layout.addLayout(path_form_layout)
        btn_layout = QHBoxLayout()
        auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_FileDialogContentsView, "Auto"), "Auto-detect"); auto_detect_btn.clicked.connect(self._auto_detect)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Browse"), "Browse..."); browse_btn.clicked.connect(self._browse)
        btn_layout.addWidget(auto_detect_btn); btn_layout.addWidget(browse_btn); btn_layout.addStretch()
        path_v_layout.addLayout(btn_layout)
        main_layout.addWidget(path_group)

        test_group = QGroupBox("Connection Test")
        test_layout = QVBoxLayout(); test_group.setLayout(test_layout)
        self.test_status_label = QLabel("Status: Unknown"); self.test_status_label.setWordWrap(True); self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        test_btn = QPushButton(get_standard_icon(QStyle.SP_CommandLink, "Test"), "Test Connection"); test_btn.clicked.connect(self._test_connection_and_update_label)
        test_layout.addWidget(test_btn); test_layout.addWidget(self.test_status_label)
        main_layout.addWidget(test_group)

        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close")
        dialog_buttons.accepted.connect(self._apply_settings); dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)

        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        initial_msg = f"Connected: {self.matlab_connection.matlab_path}" if self.matlab_connection.connected and self.matlab_connection.matlab_path else \
                      (f"Path set ({self.matlab_connection.matlab_path}), connection unknown/failed." if self.matlab_connection.matlab_path else "MATLAB path not set.")
        self._update_test_label_from_signal(self.matlab_connection.connected, initial_msg)


    def _auto_detect(self):
        self.test_status_label.setText("Status: Auto-detecting MATLAB, please wait..."); self.test_status_label.setStyleSheet("")
        QApplication.processEvents(); self.matlab_connection.detect_matlab()

    def _browse(self):
        exe_filter = "MATLAB Executable (matlab.exe matlab)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        start_dir = os.path.dirname(self.path_edit.text()) if self.path_edit.text() and os.path.isdir(os.path.dirname(self.path_edit.text())) else QDir.homePath()
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path: self.path_edit.setText(path); self._update_test_label_from_signal(False, "Path changed. Click 'Test' or 'Apply'.")

    def _test_connection_and_update_label(self):
        path = self.path_edit.text().strip()
        if not path: self._update_test_label_from_signal(False, "Path is empty."); return
        self.test_status_label.setText("Status: Testing, please wait..."); self.test_status_label.setStyleSheet("")
        QApplication.processEvents()
        if self.matlab_connection.set_matlab_path(path): self.matlab_connection.test_connection()

    def _update_test_label_from_signal(self, success, message):
        self.test_status_label.setText(f"Status: {message}")
        style = "color: #008000; font-weight: bold;" if success else "color: #D32F2F; font-weight: bold;"
        self.test_status_label.setStyleSheet(style)
        if success and self.matlab_connection.matlab_path: self.path_edit.setText(self.matlab_connection.matlab_path)

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

        # Store app path for icon resources
        self.app_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        app_icon_path = os.path.join(self.app_path, "resources", "app_icon.png") # Placeholder
        if os.path.exists(app_icon_path):
            self.setWindowIcon(QIcon(app_icon_path))
        else:
            self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "BSM")) # Fallback

        self.init_ui()
        self._update_matlab_status_display(False, "Initializing...")
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)

        self._update_window_title()
        self.on_new_file(silent=True)
        self.scene.selectionChanged.connect(self._update_properties_dock)
        self._update_properties_dock()
        self.restore_geometry_and_state()


    def init_ui(self):
        self.setGeometry(100, 100, 1600, 1000) # Default position and size
        self.setStyleSheet(MAIN_STYLESHEET) # Apply global style

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
        def _get_std_icon(style_enum, fallback): return get_standard_icon(style_enum, fallback)

        # File Actions
        self.new_action = QAction(_get_std_icon(QStyle.SP_FileIcon, "New"), "&New", self, shortcut=QKeySequence.New, triggered=self.on_new_file, statusTip="Create new diagram")
        self.open_action = QAction(_get_std_icon(QStyle.SP_DialogOpenButton, "Open"), "&Open...", self, shortcut=QKeySequence.Open, triggered=self.on_open_file, statusTip="Open diagram")
        self.save_action = QAction(_get_std_icon(QStyle.SP_DialogSaveButton, "Save"), "&Save", self, shortcut=QKeySequence.Save, triggered=self.on_save_file, statusTip="Save diagram")
        self.save_as_action = QAction(_get_std_icon(QStyle.SP_DialogSaveButton, "SaveAs"), "Save &As...", self, shortcut=QKeySequence.SaveAs, triggered=self.on_save_file_as, statusTip="Save diagram with new name")
        self.exit_action = QAction(_get_std_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", self, shortcut=QKeySequence.Quit, triggered=self.close, statusTip="Exit application")

        # Edit Actions
        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo"); self.undo_action.setShortcut(QKeySequence.Undo); self.undo_action.setIcon(_get_std_icon(QStyle.SP_ArrowBack, "Undo")); self.undo_action.setStatusTip("Undo last action")
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo"); self.redo_action.setShortcut(QKeySequence.Redo); self.redo_action.setIcon(_get_std_icon(QStyle.SP_ArrowForward, "Redo")); self.redo_action.setStatusTip("Redo last action")
        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.undo_stack.canRedoChanged.connect(self._update_undo_redo_actions_enable_state)
        self.select_all_action = QAction(_get_std_icon(QStyle.SP_FileDialogDetailedView, "All"), "Select &All", self, shortcut=QKeySequence.SelectAll, triggered=self.on_select_all, statusTip="Select all items")
        self.delete_action = QAction(_get_std_icon(QStyle.SP_TrashIcon, "Del"), "&Delete", self, shortcut=QKeySequence.Delete, triggered=self.on_delete_selected, statusTip="Delete selected items")

        # Mode Actions
        self.mode_action_group = QActionGroup(self); self.mode_action_group.setExclusive(True)
        self.select_mode_action = QAction(QIcon.fromTheme("edit-select", _get_std_icon(QStyle.SP_ArrowCursor, "Sel")), "Select/Move", self, checkable=True, triggered=lambda: self.scene.set_mode("select"), statusTip="Mode: Select/Move")
        self.add_state_mode_action = QAction(QIcon.fromTheme("draw-rectangle", _get_std_icon(QStyle.SP_FileDialogNewFolder, "State")), "Add State", self, checkable=True, triggered=lambda: self.scene.set_mode("state"), statusTip="Mode: Add State")
        self.add_transition_mode_action = QAction(QIcon.fromTheme("draw-connector", _get_std_icon(QStyle.SP_FileDialogBack, "Trans")), "Add Transition", self, checkable=True, triggered=lambda: self.scene.set_mode("transition"), statusTip="Mode: Add Transition")
        self.add_comment_mode_action = QAction(QIcon.fromTheme("insert-text", _get_std_icon(QStyle.SP_MessageBoxInformation, "Cmnt")), "Add Comment", self, checkable=True, triggered=lambda: self.scene.set_mode("comment"), statusTip="Mode: Add Comment")
        for action in [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action]: self.mode_action_group.addAction(action)
        self.select_mode_action.setChecked(True)

        # View Actions
        self.zoom_in_action = QAction(_get_std_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "Zm+"), "Zoom In", self, shortcut=QKeySequence.ZoomIn, triggered=lambda: self.view.zoom_in(), statusTip="Zoom in")
        self.zoom_out_action = QAction(_get_std_icon(QStyle.SP_ToolBarVerticalExtensionButton, "Zm-"), "Zoom Out", self, shortcut=QKeySequence.ZoomOut, triggered=lambda: self.view.zoom_out(), statusTip="Zoom out")
        self.fit_view_action = QAction(_get_std_icon(QStyle.SP_FileDialogListView, "Fit"), "Fit to Content", self, shortcut=Qt.CTRL + Qt.Key_0, triggered=lambda: self.view.reset_zoom_and_fit(), statusTip="Fit view to content")
        self.toggle_grid_action = QAction("Show &Grid", self, checkable=True, statusTip="Toggle grid visibility") # Needs implementation
        self.toggle_grid_action.setChecked(True); # self.toggle_grid_action.triggered.connect(self.on_toggle_grid)

        # MATLAB/Simulink Actions
        self.export_simulink_action = QAction(_get_std_icon(QStyle.SP_ArrowRight, "ExpSim"), "&Export to Simulink...", self, triggered=self.on_export_simulink, statusTip="Generate Simulink model")
        self.run_simulation_action = QAction(_get_std_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation...", self, triggered=self.on_run_simulation, statusTip="Run Simulink model")
        self.generate_code_action = QAction(_get_std_icon(QStyle.SP_ComputerIcon, "GenC"), "Generate &Code (C/C++)...", self, triggered=self.on_generate_code, statusTip="Generate C/C++ code")
        self.matlab_settings_action = QAction(_get_std_icon(QStyle.SP_FileDialogDetailedView, "SetM"), "&MATLAB Settings...", self, triggered=self.on_matlab_settings, statusTip="Configure MATLAB")

        # Help Actions
        self.about_action = QAction(_get_std_icon(QStyle.SP_DialogHelpButton, "Help"), "&About", self, triggered=self.on_about, statusTip=f"About {APP_NAME}")


    def _create_menus(self):
        menu_bar = self.menuBar()
        # File
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_action); file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action); file_menu.addAction(self.save_as_action)
        file_menu.addSeparator(); file_menu.addAction(self.export_simulink_action)
        file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        # Edit
        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action); edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator(); edit_menu.addAction(self.delete_action); edit_menu.addAction(self.select_all_action)
        mode_menu = edit_menu.addMenu(_get_std_icon(QStyle.SP_DesktopIcon,"Mode"), "Interaction Mode")
        mode_menu.addActions(self.mode_action_group.actions())
        # View
        self.view_menu = menu_bar.addMenu("&View")
        self.view_menu.addAction(self.zoom_in_action); self.view_menu.addAction(self.zoom_out_action)
        self.view_menu.addAction(self.fit_view_action)
        # self.view_menu.addAction(self.toggle_grid_action) # If fully implemented
        self.view_menu.addSeparator() # Docks will be added after creation
        # Simulation
        sim_menu = menu_bar.addMenu("&Simulation")
        sim_menu.addAction(self.run_simulation_action); sim_menu.addAction(self.generate_code_action)
        sim_menu.addSeparator(); sim_menu.addAction(self.matlab_settings_action)
        # Help
        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(24,24) # Slightly smaller icons for text under style
        # File Toolbar
        file_tb = self.addToolBar("File Actions"); file_tb.setObjectName("FileToolBar"); file_tb.setIconSize(icon_size); file_tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        file_tb.addAction(self.new_action); file_tb.addAction(self.open_action); file_tb.addAction(self.save_action)
        # Edit Toolbar
        edit_tb = self.addToolBar("Edit Actions"); edit_tb.setObjectName("EditToolBar"); edit_tb.setIconSize(icon_size); edit_tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        edit_tb.addAction(self.undo_action); edit_tb.addAction(self.redo_action); edit_tb.addAction(self.delete_action)
        self.addToolBarBreak() # New row for toolbars
        # Interaction Tools Toolbar
        mode_tb = self.addToolBar("Interaction Modes"); mode_tb.setObjectName("ModeToolBar"); mode_tb.setIconSize(icon_size); mode_tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mode_tb.addActions(self.mode_action_group.actions())
        # View Toolbar
        view_tb = self.addToolBar("View Controls"); view_tb.setObjectName("ViewToolBar"); view_tb.setIconSize(icon_size); view_tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        view_tb.addAction(self.zoom_in_action); view_tb.addAction(self.zoom_out_action); view_tb.addAction(self.fit_view_action)


    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready"); self.status_label.setObjectName("GeneralStatusLabel")
        self.status_bar.addWidget(self.status_label, 1)
        self.matlab_status_label = QLabel("MATLAB: Initializing..."); self.matlab_status_label.setObjectName("MatlabStatusLabel")
        self.matlab_status_label.setToolTip("MATLAB connection status.")
        self.matlab_status_label.setStyleSheet("padding: 0 8px; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.matlab_status_label)
        self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0,0); self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200); self.progress_bar.setTextVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)
        # Tools Dock
        self.tools_dock = QDockWidget("Tools", self); self.tools_dock.setObjectName("ToolsDock"); self.tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_widget = QWidget(); tools_main_layout = QVBoxLayout(tools_widget); tools_main_layout.setSpacing(12); tools_main_layout.setContentsMargins(10,10,10,10)
        # Mode Group (re-uses toolbar actions in QToolButtons)
        mode_group = QGroupBox("Interaction Modes"); mode_layout = QVBoxLayout(); mode_layout.setSpacing(6)
        for action in [self.select_mode_action, self.add_state_mode_action, self.add_transition_mode_action, self.add_comment_mode_action]:
            btn = QToolButton(); btn.setDefaultAction(action); btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setIconSize(QSize(20,20)); mode_layout.addWidget(btn)
        mode_group.setLayout(mode_layout); tools_main_layout.addWidget(mode_group)
        # Draggable Items Group
        drag_group = QGroupBox("Drag to Canvas"); drag_layout = QVBoxLayout(); drag_layout.setSpacing(6)
        items_to_drag = [
            ("State", "application/x-bsm-tool", "State", QStyle.SP_FileDialogNewFolder, "St"),
            ("Initial State", "application/x-bsm-tool", "Initial State", QStyle.SP_ToolBarHorizontalExtensionButton, "Init"),
            ("Final State", "application/x-bsm-tool", "Final State", QStyle.SP_DialogOkButton, "End"),
            ("Comment", "application/x-bsm-tool", "Comment", QStyle.SP_MessageBoxInformation, "Cmnt")
        ]
        for text, mime, data_str, icon_enum, fb_text in items_to_drag:
            btn = DraggableToolButton(text, mime, data_str); btn.setIcon(get_standard_icon(icon_enum, fb_text))
            # Applying specific style to DraggableToolButtons for better distinction:
            btn.setStyleSheet("""
                DraggableToolButton {
                    background-color: #E8F5E9; /* Light green */
                    border: 1px solid #A5D6A7;
                    text-align: left; padding-left: 8px;
                    border-radius: 4px; color: #2E7D32;
                }
                DraggableToolButton:hover { background-color: #C8E6C9; border-color: #81C784; }
                DraggableToolButton:pressed { background-color: #A5D6A7; }
            """)
            drag_layout.addWidget(btn)
        drag_group.setLayout(drag_layout); tools_main_layout.addWidget(drag_group)
        tools_main_layout.addStretch(); self.tools_dock.setWidget(tools_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tools_dock); self.view_menu.addAction(self.tools_dock.toggleViewAction())

        # Log Output Dock
        self.log_dock = QDockWidget("Log Output", self); self.log_dock.setObjectName("LogDock"); self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.log_output = QTextEdit(); self.log_output.setReadOnly(True); self.log_output.setFont(QFont("Consolas", 9))
        # QTextEdit specific style from main stylesheet usually covers this. Could add: self.log_output.setStyleSheet("background-color: #FCFCFC; color: #424242; border: 1px solid #E0E0E0;")
        self.log_dock.setWidget(self.log_output)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock); self.view_menu.addAction(self.log_dock.toggleViewAction())

        # Properties Dock
        self.properties_dock = QDockWidget("Item Properties", self); self.properties_dock.setObjectName("PropertiesDock"); self.properties_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        prop_widget = QWidget(); prop_layout = QVBoxLayout(prop_widget); prop_layout.setSpacing(10); prop_layout.setContentsMargins(10,10,10,10)
        self.properties_editor_label = QLabel("<i>Select an item to view its properties.</i>"); self.properties_editor_label.setObjectName("PropertiesLabel")
        self.properties_editor_label.setAlignment(Qt.AlignTop | Qt.AlignLeft); self.properties_editor_label.setWordWrap(True)
        self.properties_editor_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.properties_editor_label.setStyleSheet("background-color: #FFFFFF; border: 1px solid #CFD8DC; border-radius: 4px; padding: 8px; min-height: 150px;")
        self.properties_edit_button = QPushButton(get_standard_icon(QStyle.SP_DialogApplyButton,"Edit"), "Edit Properties..."); self.properties_edit_button.setEnabled(False)
        self.properties_edit_button.clicked.connect(self._on_edit_selected_item_properties_from_dock); self.properties_edit_button.setIconSize(QSize(16,16))
        prop_layout.addWidget(self.properties_editor_label, 1); prop_layout.addWidget(self.properties_edit_button)
        self.properties_dock.setWidget(prop_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock); self.view_menu.addAction(self.properties_dock.toggleViewAction())


    def _create_central_widget(self):
        self.view = ZoomableView(self.scene, self)
        self.setCentralWidget(self.view)

    def _update_properties_dock(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1:
            item = selected_items[0]
            props = item.get_data()
            item_type_name = type(item).__name__.replace("Graphics", "").replace("Item", "")
            item_info = f"<b>Type:</b> {html.escape(item_type_name)}<br><hr style='margin: 3px 0;'>"

            def fmt_multiline(txt, max_chars=25):
                if not txt: return "<i>(none)</i>"
                first_line = html.escape(txt.split('\n')[0])
                return first_line[:max_chars] + ('...' if len(first_line) > max_chars or '\n' in html.escape(txt) else '')

            if isinstance(item, GraphicsStateItem):
                item_info += f"<b>Name:</b> {html.escape(props['name'])}<br>"
                item_info += f"<b>Initial:</b> {'Yes' if props['is_initial'] else 'No'}, <b>Final:</b> {'Yes' if props['is_final'] else 'No'}<br>"
                clr = QColor(props.get('color', '#FFFFFF'))
                item_info += f"<b>Color:</b> <span style='background-color:{clr.name()}; color:{'black' if clr.lightnessF() > 0.5 else 'white'}; padding: 1px 6px; border-radius:3px;'>&nbsp;{html.escape(clr.name())}&nbsp;</span><br>"
                item_info += f"<b>Entry:</b> {fmt_multiline(props.get('entry_action'))}<br>"
                item_info += f"<b>During:</b> {fmt_multiline(props.get('during_action'))}<br>"
                item_info += f"<b>Exit:</b> {fmt_multiline(props.get('exit_action'))}<br>"
                if props.get('description'): item_info += f"<hr style='margin: 3px 0;'><b>Desc:</b> {fmt_multiline(props.get('description'), 35)}<br>"
            elif isinstance(item, GraphicsTransitionItem):
                parts = []
                if props.get('event'): parts.append(html.escape(props['event']))
                if props.get('condition'): parts.append(f"[{html.escape(props['condition'])}]")
                if props.get('action'): parts.append(f"/{{{fmt_multiline(props['action'],20)}}}")
                label = " ".join(parts) if parts else "<i>(Unlabeled)</i>"
                item_info += f"<b>Label:</b> {label}<br>"
                item_info += f"<b>From:</b> {html.escape(props['source'])} To: {html.escape(props['target'])}<br>"
                clr = QColor(props.get('color', '#FFFFFF'))
                item_info += f"<b>Color:</b> <span style='background-color:{clr.name()}; color:{'black' if clr.lightnessF() > 0.5 else 'white'}; padding: 1px 6px; border-radius:3px;'>&nbsp;{html.escape(clr.name())}&nbsp;</span><br>"
                item_info += f"<b>Curve:</b> B={props.get('control_offset_x',0):.0f}, S={props.get('control_offset_y',0):.0f}<br>"
                if props.get('description'): item_info += f"<hr style='margin: 3px 0;'><b>Desc:</b> {fmt_multiline(props.get('description'), 35)}<br>"
            elif isinstance(item, GraphicsCommentItem):
                item_info += f"<b>Text:</b> {fmt_multiline(props['text'], 50)}<br>"
            else: item_info += "Selected item type: Unknown"

            self.properties_editor_label.setText(item_info)
            self.properties_edit_button.setEnabled(True)
            self.properties_edit_button.setToolTip(f"Edit properties of selected {item_type_name}")
        elif len(selected_items) > 1:
            self.properties_editor_label.setText(f"<b>{len(selected_items)} items selected.</b><br><i>Properties view shows single item details.</i>")
            self.properties_edit_button.setEnabled(False)
            self.properties_edit_button.setToolTip("Select a single item to edit its properties.")
        else:
            self.properties_editor_label.setText("<i>Select an item to view its properties.</i><br>You can also use tools to add new items, or right-click the canvas.")
            self.properties_edit_button.setEnabled(False)
            self.properties_edit_button.setToolTip("")


    def _on_edit_selected_item_properties_from_dock(self):
        selected = self.scene.selectedItems()
        if len(selected) == 1: self.scene.edit_item_properties(selected[0])

    def log_message(self, message: str):
        timestamp = QTime.currentTime().toString('hh:mm:ss')
        self.log_output.append(f"<span style='color:#757575;'>[{timestamp}]</span> {html.escape(message)}")
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
        self.status_label.setText(message.split('\n')[0][:150])

    def _update_window_title(self):
        base_title = APP_NAME
        if self.current_file_path: base_title += f" - {os.path.basename(self.current_file_path)}"
        else: base_title += " - Untitled"
        self.setWindowTitle(base_title + "[*]") # Qt handles [*] based on isWindowModified

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
        self.matlab_status_label.setToolTip(f"Status: {html.escape(message)}")
        self.matlab_status_label.setStyleSheet(f"color: {'#00695C' if connected else '#C62828'}; font-weight: bold; padding: 0 8px;") # Teal for connected, Red for disconnected
        self.log_message(f"MATLAB Update: {message}")
        self._update_matlab_actions_enabled_state()

    def _update_matlab_actions_enabled_state(self):
        is_conn = self.matlab_connection.connected
        self.export_simulink_action.setEnabled(is_conn)
        self.run_simulation_action.setEnabled(is_conn)
        self.generate_code_action.setEnabled(is_conn)

    def _start_matlab_operation(self, op_name):
        self.log_message(f"MATLAB: '{op_name}' starting..."); self.status_label.setText(f"Running: {op_name}...")
        self.progress_bar.setVisible(True); self.set_ui_enabled_for_matlab_op(False)

    def _finish_matlab_operation(self):
        self.progress_bar.setVisible(False); self.status_label.setText("Ready")
        self.set_ui_enabled_for_matlab_op(True); self.log_message("MATLAB: Operation finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        self.menuBar().setEnabled(enabled)
        for tb in self.findChildren(QToolBar): tb.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
        for dock_name in ["ToolsDock", "PropertiesDock"]: # Keep LogDock enabled
            dock = self.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(enabled)

    def _handle_matlab_modelgen_or_sim_finished(self, success, message, data):
        self._finish_matlab_operation()
        self.log_message(f"MATLAB Result ({('Success' if success else 'Failure')}): {message}")
        if success:
            if "Model generation" in message and data:
                 self.last_generated_model_path = data
                 QMessageBox.information(self, "Simulink Model Generation", f"Simulink model generated successfully:\n{data}")
            elif "Simulation" in message:
                 QMessageBox.information(self, "Simulation Complete", f"MATLAB simulation finished.\n{html.escape(message)}")
        else: QMessageBox.warning(self, "MATLAB Operation Failed", f"Operation failed:\n{html.escape(message)}")


    def _handle_matlab_codegen_finished(self, success, message, output_dir):
        self._finish_matlab_operation()
        self.log_message(f"MATLAB Code Gen Result ({('Success' if success else 'Failure')}): {message}")
        if success and output_dir:
            msg_box = QMessageBox(self); msg_box.setIcon(QMessageBox.Information); msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText)
            abs_path_for_open = os.path.abspath(output_dir) # Ensure absolute path for link and opening
            msg_box.setText(f"Code generation process completed.<br>"
                            f"Output directory: <a href='file:///{abs_path_for_open}'>{html.escape(abs_path_for_open)}</a>")
            open_dir_button = msg_box.addButton("Open Directory", QMessageBox.ActionRole); msg_box.addButton(QMessageBox.Ok)
            msg_box.exec_()
            if msg_box.clickedButton() == open_dir_button:
                try: QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path_for_open))
                except Exception as e: self.log_message(f"Error opening directory {abs_path_for_open}: {e}"); QMessageBox.warning(self, "Error", f"Could not open directory:\n{e}")
        elif not success: QMessageBox.warning(self, "Code Generation Failed", f"Failed:\n{html.escape(message)}")


    def _prompt_save_if_dirty(self) -> bool:
        if not self.isWindowModified(): return True
        file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
        reply = QMessageBox.question(self, "Save Changes?",
                                     f"The diagram '{html.escape(file_name)}' has unsaved changes.\n"
                                     "Do you want to save them before continuing?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if reply == QMessageBox.Save: return self.on_save_file()
        elif reply == QMessageBox.Cancel: return False
        return True # Discard


    def on_new_file(self, silent=False):
        if not silent and not self._prompt_save_if_dirty(): return False
        self.scene.clear(); self.scene.setSceneRect(0,0,5000,4000); self.current_file_path = None
        self.last_generated_model_path = None; self.undo_stack.clear(); self.scene.set_dirty(False)
        self._update_window_title(); self._update_undo_redo_actions_enable_state()
        if not silent: self.log_message("New diagram created.")
        self.view.reset_zoom_and_fit() # This also calls fit_to_content, which handles empty scene.
        self.select_mode_action.trigger()
        return True

    def on_open_file(self):
        if not self._prompt_save_if_dirty(): return
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open BSM File", start_dir, FILE_FILTER)
        if file_path:
            self.log_message(f"Opening file: {file_path}")
            if self._load_from_path(file_path):
                self.current_file_path = file_path; self.last_generated_model_path = None
                self.undo_stack.clear(); self.scene.set_dirty(False)
                self._update_window_title(); self._update_undo_redo_actions_enable_state()
                self.log_message(f"Successfully opened: {file_path}")
                self.view.reset_zoom_and_fit()
            else: QMessageBox.critical(self, "Error Opening File", f"Could not load file: {html.escape(file_path)}"); self.log_message(f"Failed to open: {file_path}")


    def _load_from_path(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
            if not isinstance(data, dict) or not ('states' in data and 'transitions' in data): # Basic check
                self.log_message(f"Error: Invalid BSM file format in {file_path}."); return False
            self.scene.load_diagram_data(data); return True
        except json.JSONDecodeError as e: self.log_message(f"JSON decode error in {file_path}: {e}"); return False
        except Exception as e: self.log_message(f"Load error {file_path}: {type(e).__name__}: {e}"); return False


    def on_save_file(self) -> bool:
        if self.current_file_path:
            if self._save_to_path(self.current_file_path): self.scene.set_dirty(False); return True
            return False
        else: return self.on_save_file_as()

    def on_save_file_as(self) -> bool:
        start_path = self.current_file_path if self.current_file_path else os.path.join(QDir.homePath(), "untitled" + FILE_EXTENSION)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save BSM File As", start_path, FILE_FILTER)
        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION): file_path += FILE_EXTENSION
            if self._save_to_path(file_path):
                self.current_file_path = file_path; self.scene.set_dirty(False)
                self._update_window_title(); return True
        return False


    def _save_to_path(self, file_path) -> bool:
        save_file = QSaveFile(file_path)
        if not save_file.open(QIODevice.WriteOnly | QIODevice.Text):
            err = save_file.errorString()
            self.log_message(f"Error opening {file_path} for saving: {err}")
            QMessageBox.critical(self, "Save Error", f"Failed to open file for saving:\n{html.escape(err)}"); return False
        try:
            data = self.scene.get_diagram_data()
            json_data = json.dumps(data, indent=2, ensure_ascii=False) # Indent 2 for smaller files
            bytes_written = save_file.write(json_data.encode('utf-8'))
            if bytes_written == -1: # Error
                err = save_file.errorString(); self.log_message(f"Error writing to {file_path}: {err}")
                QMessageBox.critical(self, "Save Error", f"Failed to write data:\n{html.escape(err)}"); save_file.cancelWriting(); return False
            if not save_file.commit():
                err = save_file.errorString(); self.log_message(f"Error committing {file_path}: {err}")
                QMessageBox.critical(self, "Save Error", f"Failed to commit file:\n{html.escape(err)}"); return False
            self.log_message(f"File saved: {file_path}"); return True
        except Exception as e:
            self.log_message(f"Exception during save to {file_path}: {type(e).__name__}: {e}")
            QMessageBox.critical(self, "Save Error", f"An error occurred:\n{html.escape(str(e))}"); save_file.cancelWriting(); return False

    def on_select_all(self): self.scene.select_all()
    def on_delete_selected(self): self.scene.delete_selected_items()


    def on_export_simulink(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Error", "MATLAB not connected. Configure in Simulation menu."); return
        dialog = QDialog(self); dialog.setWindowTitle("Export to Simulink"); dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowRight, "->M"))
        layout = QFormLayout(dialog); layout.setSpacing(10)
        default_name = "BSM_Model"; # Basic default
        if self.current_file_path:
            base = os.path.splitext(os.path.basename(self.current_file_path))[0]
            default_name = "".join(c if c.isalnum() or c=='_' else '_' for c in base)
            if not default_name or not default_name[0].isalpha(): default_name = "Model_" + default_name
        name_edit = QLineEdit(default_name); name_edit.setPlaceholderText("Simulink model name (no spaces/special chars)")
        layout.addRow("Model Name:", name_edit)
        default_dir = os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath()
        dir_edit = QLineEdit(default_dir); browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), "Browse...")
        def browse(): d = QFileDialog.getExistingDirectory(dialog, "Select Output Directory", dir_edit.text());
                       if d: dir_edit.setText(d)
        browse_btn.clicked.connect(browse); dir_hbox = QHBoxLayout(); dir_hbox.addWidget(dir_edit,1); dir_hbox.addWidget(browse_btn)
        layout.addRow("Output Directory:", dir_hbox)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject)
        layout.addRow(btns); dialog.setMinimumWidth(450)
        if dialog.exec_() == QDialog.Accepted:
            model_name = name_edit.text().strip(); output_dir = dir_edit.text().strip()
            if not (model_name and output_dir): QMessageBox.warning(self, "Input Error", "Model name and directory are required."); return
            if not model_name[0].isalpha() or not all(c.isalnum() or c == '_' for c in model_name): QMessageBox.warning(self, "Invalid Name", "Model name must start with a letter and use alphanumeric/underscores."); return
            if not os.path.exists(output_dir):
                try: os.makedirs(output_dir, exist_ok=True)
                except OSError as e: QMessageBox.critical(self, "Error", f"Cannot create directory:\n{e}"); return
            data = self.scene.get_diagram_data()
            if not data['states']: QMessageBox.information(self, "Empty Diagram", "No states to export."); return
            self._start_matlab_operation(f"Exporting '{model_name}'"); self.matlab_connection.generate_simulink_model(data['states'], data['transitions'], output_dir, model_name)

    def on_run_simulation(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Error", "MATLAB not connected."); return
        default_dir = os.path.dirname(self.last_generated_model_path) if self.last_generated_model_path else \
                      (os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model", default_dir, "Simulink (*.slx);;All (*)")
        if not model_path: return
        self.last_generated_model_path = model_path # Remember for next time
        sim_time, ok = QInputDialog.getDouble(self, "Simulation Time", "Stop time (seconds):", 10.0, 0.001, 1e6, 3)
        if not ok: return
        self._start_matlab_operation(f"Running '{os.path.basename(model_path)}'"); self.matlab_connection.run_simulation(model_path, sim_time)


    def on_generate_code(self):
        if not self.matlab_connection.connected: QMessageBox.warning(self, "MATLAB Error", "MATLAB not connected."); return
        default_dir = os.path.dirname(self.last_generated_model_path) if self.last_generated_model_path else \
                      (os.path.dirname(self.current_file_path) if self.current_file_path else QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Simulink Model", default_dir, "Simulink (*.slx);;All (*)")
        if not model_path: return
        self.last_generated_model_path = model_path

        dialog = QDialog(self); dialog.setWindowTitle("Generate Code"); dialog.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon,"GenC"))
        layout = QFormLayout(dialog); layout.setSpacing(10)
        lang_combo = QComboBox(); lang_combo.addItems(["C", "C++"]); lang_combo.setCurrentText("C++")
        layout.addRow("Target Language:", lang_combo)
        default_output = os.path.dirname(model_path)
        dir_edit = QLineEdit(default_output); dir_edit.setPlaceholderText("Base directory for generated code")
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), "Browse...")
        def browse_cg(): d = QFileDialog.getExistingDirectory(dialog, "Select Code Output Directory", dir_edit.text());
                         if d: dir_edit.setText(d)
        browse_btn.clicked.connect(browse_cg); dir_hbox = QHBoxLayout(); dir_hbox.addWidget(dir_edit,1); dir_hbox.addWidget(browse_btn)
        layout.addRow("Base Output Dir:", dir_hbox)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject)
        layout.addRow(btns); dialog.setMinimumWidth(450)
        if dialog.exec_() == QDialog.Accepted:
            language = lang_combo.currentText(); output_dir_base = dir_edit.text().strip()
            if not output_dir_base: QMessageBox.warning(self, "Input Error", "Base output directory required."); return
            if not os.path.exists(output_dir_base):
                try: os.makedirs(output_dir_base, exist_ok=True)
                except OSError as e: QMessageBox.critical(self, "Error", f"Cannot create directory:\n{e}"); return
            self._start_matlab_operation(f"Generating {language} for '{os.path.basename(model_path)}'"); self.matlab_connection.generate_code(model_path, language, output_dir_base)


    def on_matlab_settings(self): MatlabSettingsDialog(self.matlab_connection, self).exec_()


    def on_about(self):
        QMessageBox.about(self, "About " + APP_NAME,
            f"<h3>{APP_NAME} v{APP_VERSION}</h3>"
            "<p>Design, simulate, and generate code for state machines.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Intuitive visual diagramming with states, transitions, comments.</li>"
            "<li>Drag-and-drop tools, snapping grid, zoom/pan.</li>"
            "<li>Customizable properties: actions, colors, descriptions.</li>"
            "<li>Undo/Redo, JSON file format (.bsm).</li>"
            "<li><b>MATLAB/Simulink Integration (Requires MATLAB & toolboxes):</b>"
            "<ul><li>Export diagrams to Simulink (.slx).</li>"
            "<li>Run simulations within MATLAB.</li>"
            "<li>Generate C/C++ code via Embedded Coder.</li></ul></li>"
            "</ul>"
            f"<p><i>&copy; {QTime.currentTime().year()} {APP_ORGANIZATION_NAME}. All rights reserved (example).</i></p>")

    def save_geometry_and_state(self):
        settings = QSettings(APP_ORGANIZATION_NAME, APP_NAME)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.setValue("matlabPath", self.matlab_connection.matlab_path)


    def restore_geometry_and_state(self):
        settings = QSettings(APP_ORGANIZATION_NAME, APP_NAME)
        geom = settings.value("geometry")
        if geom: self.restoreGeometry(geom)
        state = settings.value("windowState")
        if state: self.restoreState(state)
        matlab_path = settings.value("matlabPath", "")
        if matlab_path:
             self.matlab_connection.set_matlab_path(matlab_path)
             # Optional: Trigger a silent connection test or just update status
             if self.matlab_connection.connected:
                 self._update_matlab_status_display(True, f"Restored path: {matlab_path}")
             else: # Path exists but not validated as connected by set_matlab_path alone
                  self._update_matlab_status_display(False, f"Restored path (unverified): {matlab_path}")


    def closeEvent(self, event: QCloseEvent):
        if self._prompt_save_if_dirty():
            self.save_geometry_and_state() # Save window state
            if self.matlab_connection._active_threads:
                self.log_message(f"Closing application. {len(self.matlab_connection._active_threads)} MATLAB process(es) may continue.")
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    # Enable High DPI scaling
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION_NAME)
    app.setApplicationName(APP_NAME)

    # Set a good default style for consistency, Fusion is a good cross-platform choice
    # Only set if it exists, some minimal Qt builds might not have it.
    if "Fusion" in QStyleFactory.keys():
         app.setStyle(QStyleFactory.create("Fusion"))
    else:
         print("Warning: Fusion style not available, using default.")
    # Apply global font if desired (optional)
    # default_font = QFont("Segoe UI", 9)
    # app.setFont(default_font)

    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
