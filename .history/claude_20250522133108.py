
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
    QToolButton
)
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform, QKeyEvent, QPainterPathStroker, QPolygonF
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QTimer, QSize, QTime # <--- CORRECTED: Added QTime
)
import math


# --- Configuration ---
APP_VERSION = "1.2" # Incremented version due to toolbox/GUI improvements
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
            self.matlab_path = "" # Clear invalid path
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
            versions = ['R2024a', 'R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b', 'R2020b', 'R2020a'] # Added more versions
            for v in versions:
                paths.append(os.path.join(program_files, 'MATLAB', v, 'bin', 'matlab.exe'))
        elif sys.platform == 'darwin': # macOS
            versions = ['R2024a', 'R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b', 'R2020b', 'R2020a']
            for v in versions:
                paths.append(f'/Applications/MATLAB_{v}.app/bin/matlab')
        else:  # Linux
            versions = ['R2024a', 'R2023b', 'R2023a', 'R2022b', 'R2022a', 'R2021b', 'R2020b', 'R2020a']
            for v in versions:
                paths.append(f'/usr/local/MATLAB/{v}/bin/matlab') # Common path, might vary

        for path in paths:
            if os.path.exists(path):
                if self.set_matlab_path(path): # Use set_matlab_path to also emit signal
                    return True
        self.connectionStatusChanged.emit(False, "MATLAB auto-detection failed. Please set the path manually.")
        return False

    def _run_matlab_script(self, script_content, worker_signal, success_message_prefix):
        if not self.connected:
            worker_signal.emit(False, "MATLAB not connected.", "")
            return

        temp_dir = tempfile.mkdtemp(prefix="bsm_matlab_")
        script_file = os.path.join(temp_dir, "matlab_script.m")
        with open(script_file, 'w', encoding='utf-8') as f: # Specify encoding
            f.write(script_content)

        worker = MatlabCommandWorker(self.matlab_path, script_file, worker_signal, success_message_prefix)
        thread = QThread()
        worker.moveToThread(thread)

        thread.started.connect(worker.run_command)
        worker.finished_signal.connect(thread.quit) # Ensure thread quits
        worker.finished_signal.connect(worker.deleteLater) # Schedule worker for deletion
        thread.finished.connect(thread.deleteLater) # Schedule thread for deletion
        
        self._active_threads.append(thread) # Keep track
        # Clean up from list when thread finishes
        thread.finished.connect(lambda t=thread: self._active_threads.remove(t) if t in self._active_threads else None)
        
        thread.start()


    def generate_simulink_model(self, states, transitions, output_dir, model_name="BrainStateMachine"):
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected.", "") 
            return False

        slx_file_path = os.path.join(output_dir, f"{model_name}.slx").replace('\\', '/')

        # Sanitize model_name for MATLAB variable names if used directly in script logic
        # For new_system and sfChart, direct use of model_name is usually fine.
        # Simulink paths should use '/'
        model_name_matlab_safe = model_name.replace(' ', '_').replace('-', '_')
        model_name_matlab_safe = ''.join(filter(str.isalnum, model_name_matlab_safe))
        if not model_name_matlab_safe or not model_name_matlab_safe[0].isalpha():
             model_name_matlab_safe = 'bsm_' + model_name_matlab_safe

        script_lines = [
            f"% Auto-generated Simulink model script for '{model_name}'", # Use original name in comments
            f"disp('Starting Simulink model generation for {model_name}...');",
            f"modelNameVar = '{model_name}'; % Use original name for system creation",
            f"outputModelPath = '{slx_file_path}';",
            "try",
            # Ensure model is closed if loaded, and file is deleted if exists
            "    if bdIsLoaded(modelNameVar), close_system(modelNameVar, 0); end",
            "    if exist(outputModelPath, 'file'), delete(outputModelPath); end", 
            
            "    new_system(modelNameVar);", # Create the Simulink model
            "    open_system(modelNameVar);", # Open it
            
            # Add a Stateflow chart to the model
            "    chartBlockPath = [modelNameVar '/BrainStateMachineChart'];",
            "    chartHandle = sfnew(modelNameVar); % Creates a new chart block in the model
            # chartHandle is a Stateflow.Chart object, not a block handle.
            # We need to get the chart object that was added to the model.
            # Let's find the chart within the model's machine.
            "    machine = sfroot.find('-isa', 'Stateflow.Machine', 'Name', modelNameVar);",
            "    if isempty(machine)",
            "        error('Stateflow machine for model %s not found.', modelNameVar);",
            "    end",
            # The sfnew command should already add a chart. Let's find it.
            "     A new chart is typically named 'Chart'. If sfnew returns it, use that.
            "    % If sfnew adds it with a default name, and we need to rename the block:
            "    % Assume sfnew creates a block named 'Chart' and we get its path.
            "    % chartBlock = find_system(modelNameVar, 'MaskType', 'Stateflow'); % This might be too generic
            "    % if isempty(chartBlock), error('Could not find Stateflow chart block.'); end
            "    % chartObj = get_param(chartBlock{1}, 'Object').find('-isa','Stateflow.Chart');
            "    % A more direct way after sfnew:
            "    chartObj = machine.find('-isa', 'Stateflow.Chart'); % Find first chart in machine
            "    if isempty(chartObj)",
            "        error('No Stateflow chart found in machine %s after sfnew.', modelNameVar);",
            "    elseif numel(chartObj) > 1",
            "        chartObj = chartObj(end); % Pick the last one, likely newest
            "        disp(['Warning: Multiple charts found, using chart: ' chartObj.Name]);",
            "    else",
            "        chartObj = chartObj(1);",
            "    end",
            "    chartObj.Name = 'BrainStateMachineLogic'; % Rename the chart object itself (Stateflow editor name)
            # Set the block name in Simulink diagram
            "    slChartBlock = find_system(modelNameVar, 'BlockType', 'SubSystem', 'MaskType', 'Stateflow');",
            "    if ~isempty(slChartBlock)",
            "        set_param(slChartBlock{1}, 'Name', 'BrainStateMachineChartBlock'); % Rename the Simulink block
            "    else disp('Warning: Could not find Stateflow block to rename.'); end",


            "    stateHandles = containers.Map('KeyType','char','ValueType','any');",
            "% --- State Creation ---"
        ]

        for i, state in enumerate(states):
            s_name_matlab = state['name'].replace("'", "''") # Escape single quotes for MATLAB string
            # Create a MATLAB-safe variable name for the state handle
            s_id_matlab_safe = f"state_{i}_{state['name'].replace(' ', '_').replace('-', '_')}";
            s_id_matlab_safe = ''.join(filter(str.isalnum, s_id_matlab_safe)) # Remove non-alphanumeric
            if not s_id_matlab_safe or not s_id_matlab_safe[0].isalpha(): s_id_matlab_safe = 's_' + s_id_matlab_safe


            script_lines.extend([
                f"{s_id_matlab_safe} = Stateflow.State(chartObj);", # Add state to the chart object
                f"{s_id_matlab_safe}.Name = '{s_name_matlab}';",
                # Position and size: [left, top, width, height]
                # Adjust scaling if needed, Stateflow units might differ from pixels
                f"{s_id_matlab_safe}.Position = [{state['x']/4}, {state['y']/4}, {state['width']/4}, {state['height']/4}];",
                f"stateHandles('{s_name_matlab}') = {s_id_matlab_safe}; % Map original name to handle"
            ])
            if state.get('is_initial', False):
                # Create a default transition to this state
                script_lines.append(f"defaultTransition_{i} = Stateflow.Transition(chartObj);")
                script_lines.append(f"defaultTransition_{i}.Destination = {s_id_matlab_safe};")
                # Default transitions have no .Source property to set, or it's implicitly the chart entry
                # script_lines.append(f"chartObj.DefaultTransition = defaultTransition_{i}; % This might not be correct API")
                # Default transitions are drawn from the chart border to the state
                # The creation with Destination only should suffice.
        
        script_lines.append("% --- Transition Creation ---")
        for i, trans in enumerate(transitions):
            src_name_matlab = trans['source'].replace("'", "''")
            dst_name_matlab = trans['target'].replace("'", "''")
            t_label_matlab = trans['label'].replace("'", "''") if trans.get('label') else ''
            
            script_lines.extend([
                f"if isKey(stateHandles, '{src_name_matlab}') && isKey(stateHandles, '{dst_name_matlab}')",
                f"    srcStateHandle = stateHandles('{src_name_matlab}');",
                f"    dstStateHandle = stateHandles('{dst_name_matlab}');",
                f"    t{i} = Stateflow.Transition(chartObj);", # Add transition to chart
                f"    t{i}.Source = srcStateHandle;",
                f"    t{i}.Destination = dstStateHandle;"
            ])
            if t_label_matlab:
                script_lines.append(f"    t{i}.LabelString = '{t_label_matlab}';")
            # Add logic for transition path/midpoint if available from GUI (more complex)
            script_lines.append("else")
            script_lines.append(f"    disp(['Warning: Could not create transition from ''{src_name_matlab}'' to ''{dst_name_matlab}'' - one or both states not found in map.']);")
            script_lines.append("end")

        script_lines.extend([
            "% --- Finalize and Save ---",
            "    sfpref('AnimationSpeed', 'Fast'); % Optional: Speed up animation if model is run",
            "    set_param(modelNameVar, 'PaperOrientation', 'landscape');",
            "    set_param(modelNameVar, 'PaperType', 'A4');",
            "    % Auto-arrange layout (optional, can sometimes make things worse for complex charts)",
            "    % chartObj.layoutDynamic(); % Or chartObj.layout diferite options",
            "    % Or use Simulink's auto-layout on the block if needed",
            "    % Simulink.BlockDiagram.arrangeSystem(modelNameVar);",
            "    disp(['Attempting to save model to: ', outputModelPath]);",
            "    save_system(modelNameVar, outputModelPath);",
            "    close_system(modelNameVar, 0);", # Close without saving again
            "    disp(['Simulink model saved to: ', outputModelPath]);",
            "    fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', outputModelPath);", 
            "catch e",
            "    disp('Error during Simulink model generation:');",
            "    disp(getReport(e, 'extended', 'hyperlinks', 'off'));",
            "    if bdIsLoaded(modelNameVar), close_system(modelNameVar, 0); end",  
            "    fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', getReport(e, 'basic'));", % Send basic error back
            "    % rethrow(e); % Don't rethrow if we want to control output message format",
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
        disp('Starting simulation...');
        modelPath = '{model_path_matlab}';
        modelName = '{model_name}';
        modelDir = '{model_dir_matlab}';
        currentSimTime = {sim_time};
        
        try
            % Add model directory to path to ensure any dependencies are found
            addpath(modelDir);
            disp(['Added to path: ', modelDir]);

            load_system(modelPath);
            disp(['Simulating model: ', modelName, ' for ', num2str(currentSimTime), ' seconds.']);
            
            % Configure simulation parameters
            % set_param(modelName, 'SolverType', 'Variable-step'); % Example: Set solver
            % set_param(modelName, 'Solver', 'ode45');          % Example: Set solver
            % set_param(modelName, 'SaveOutput', 'on');         % Ensure output is saved
            % set_param(modelName, 'OutputSaveName', 'yout');   % Default output variable name
            
            % Run simulation
            simOut = sim(modelName, 'StopTime', num2str(currentSimTime));
            
            disp('Simulation completed successfully.');
            % Example: Access simulation data (if 'yout' is used and structure is known)
            % if isfield(simOut, 'yout') && ~isempty(simOut.yout)
            %    timeVector = simOut.yout.Time;
            %    dataVector = simOut.yout.Data;
            %    disp(['Simulation produced ', num2str(length(timeVector)), ' time points.']);
            %    % For simplicity, just report success. More complex data passing would need serialization.
            % else
            %    disp('No standard output variable ''yout'' found in simOut, or it is empty.');
            % end
            
            % For now, just a success message with model name
            fprintf('MATLAB_SCRIPT_SUCCESS:Simulation finished for %s at t=%s. Results in workspace (simOut).\\n', modelName, num2str(currentSimTime));
        catch e
            disp('Simulation error:');
            disp(getReport(e, 'extended', 'hyperlinks', 'off'));
            if bdIsLoaded(modelName), close_system(modelName, 0); end 
            fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', getReport(e, 'basic'));
        end
        if bdIsLoaded(modelName), close_system(modelName, 0); end
        % Remove model directory from path if added
        rmpath(modelDir);
        disp(['Removed from path: ', modelDir]);
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
        
        if not output_dir_base:
            output_dir_base = os.path.dirname(model_path) 
        
        # Simulink typically creates a folder like 'modelName_ert_rtw' inside the CodeGenFolder.
        # We will set CodeGenFolder to output_dir_base, and let Simulink create its subdirs.
        # The actual generated code will be in a subfolder.
        code_gen_root_matlab = output_dir_base.replace('\\', '/')


        script_content = f"""
        disp('Starting code generation...');
        modelPath = '{model_path_matlab}';
        modelName = '{model_name}';
        codeGenBaseDir = '{code_gen_root_matlab}'; % Base directory for slbuild/rtwbuild output
        modelDir = '{model_dir_matlab}';
        
        try
            % Add model directory to path
            addpath(modelDir);
            disp(['Added to path: ', modelDir]);

            load_system(modelPath);
            
            % Check for Embedded Coder license
            if ~license('test', 'MATLAB_Coder') || ~license('test', 'Simulink_Coder') || ~license('test', 'Embedded_Coder')
                error('Required licenses (MATLAB Coder, Simulink Coder, Embedded Coder) are not available.');
            end

            % Configure for ERT (Embedded Coder Target)
            set_param(modelName,'SystemTargetFile','ert.tlc'); 
            % Make sure the make command is appropriate if building
            % set_param(modelName,'MakeCommand','make_rtw'); % Default for ert.tlc
            set_param(modelName,'GenerateMakefile','on'); % Usually 'on' for ert.tlc

            cfg = getActiveConfigSet(modelName);
            
            if strcmpi('{language}', 'C++')
                set_param(cfg, 'TargetLang', 'C++');
                % For C++, set interface to C++ class for Stateflow if it's a chart model
                % This depends on the model structure. If it's a chart at the top level,
                % you might want class generation.
                % Check if Stateflow is present and adjust interface packaging
                isStateflowModel = ~isempty(find_system(modelName, 'MaskType', 'Stateflow'));
                if isStateflowModel
                    set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'C++ class');
                    disp('Configured for C++ class interface (Stateflow detected).');
                else
                    set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'Reusable function');
                     disp('Configured for C++ reusable function interface.');
                end
                set_param(cfg.getComponent('Code Generation'),'TargetLangStandard', 'C++11 (ISO)');
                disp('Configured for C++ code generation.');
            else % C
                set_param(cfg, 'TargetLang', 'C');
                set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'Reusable function');
                disp('Configured for C code generation.');
            end
            
            % Other common settings
            set_param(cfg, 'GenerateReport', 'on'); % Generate HTML report
            set_param(cfg, 'GenCodeOnly', 'on');  % Only generate code, don't compile/link
            set_param(cfg, 'RTWVerbose', 'on'); % More verbose output during codegen

            % Set the base folder for code generation.
            % Simulink will create subdirectories like 'modelName_ert_rtw' inside this.
            if ~exist(codeGenBaseDir, 'dir')
               mkdir(codeGenBaseDir);
               disp(['Created code generation base directory: ', codeGenBaseDir]);
            end
            
            % Using rtwbuild for more control over code generation process for ERT
            disp(['Code generation output target base directory: ', codeGenBaseDir]);
            % Pass CodeGenFolder to rtwbuild. It will create modelName_target_rtw subdir.
            rtwbuild(modelName, 'CodeGenFolder', codeGenBaseDir, 'GenCodeOnly', true);
            
            disp('Code generation command (rtwbuild) executed.');
            
            % Determine the actual output directory (usually modelName_ert_rtw inside CodeGenFolder)
            % This logic assumes ert.tlc standard naming.
            actualCodeDir = fullfile(codeGenBaseDir, [modelName '_ert_rtw']); % Common pattern
            if ~exist(actualCodeDir, 'dir')
                % Fallback or search if the common pattern doesn't exist
                disp(['Warning: Expected code directory ', actualCodeDir, ' not found. Using base directory.']);
                actualCodeDir = codeGenBaseDir; % Point to base if specific subdir not found
            end
            
            disp(['Code generation successful. Code and report expected in or under: ', actualCodeDir]);
            fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', actualCodeDir); 
        catch e
            disp('Code generation error:');
            disp(getReport(e, 'extended', 'hyperlinks', 'off'));
            if bdIsLoaded(modelName), close_system(modelName, 0); end 
            fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', getReport(e, 'basic'));
        end
        if bdIsLoaded(modelName), close_system(modelName, 0); end
        % Remove model directory from path
        rmpath(modelDir);
        disp(['Removed from path: ', modelDir]);
        """
        self._run_matlab_script(script_content, self.codeGenerationFinished, "Code generation")
        return True

class MatlabCommandWorker(QObject):
    finished_signal = pyqtSignal(bool, str, str) # Internal signal for thread management

    def __init__(self, matlab_path, script_file, original_signal, success_message_prefix):
        super().__init__()
        self.matlab_path = matlab_path
        self.script_file = script_file
        self.original_signal = original_signal # The signal to emit to the main app
        self.success_message_prefix = success_message_prefix

    def run_command(self):
        output_data_for_signal = "" # Data payload for the original_signal (e.g., path)
        success = False
        message = "" # Detailed message for original_signal
        try:
            # Ensure script_file path is correctly quoted for MATLAB's run command
            matlab_run_command = f"run('{self.script_file.replace('\\', '/')}')"
            cmd = [self.matlab_path, "-batch", matlab_run_command]
            
            timeout_seconds = 600 # 10 minutes, adjust as needed
            process = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', # Specify encoding for output
                timeout=timeout_seconds,  
                check=False, # We check returncode manually
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0 
            )

            # Check for specific failure marker from script first
            if "MATLAB_SCRIPT_FAILURE:" in process.stdout:
                success = False
                for line in process.stdout.splitlines():
                    if line.startswith("MATLAB_SCRIPT_FAILURE:"):
                        error_detail = line.split(":", 1)[1].strip()
                        message = f"{self.success_message_prefix} failed in MATLAB script: {error_detail}"
                        break
                if not message: # Fallback if parsing failed
                    message = f"{self.success_message_prefix} failed. MATLAB script indicated failure.\nStdout:\n{process.stdout[:500]}"
                if process.stderr:
                    message += f"\nStderr:\n{process.stderr[:300]}"

            elif process.returncode == 0: # MATLAB exited normally
                if "MATLAB_SCRIPT_SUCCESS:" in process.stdout:
                    success = True
                    for line in process.stdout.splitlines():
                        if line.startswith("MATLAB_SCRIPT_SUCCESS:"):
                            output_data_for_signal = line.split(":", 1)[1].strip()
                            break
                    message = f"{self.success_message_prefix} completed successfully."
                    if output_data_for_signal and self.success_message_prefix != "Simulation":
                         message += f" Output at: {output_data_for_signal}"
                    elif output_data_for_signal and self.success_message_prefix == "Simulation":
                        message = output_data_for_signal # Sim success message often comes from MATLAB
                    elif not output_data_for_signal and self.success_message_prefix == "Simulation":
                        message = f"{self.success_message_prefix} completed, but no specific data returned by script. MATLAB Output:\n{process.stdout[:300]}"
                else: 
                    success = False 
                    message = f"{self.success_message_prefix} finished (MATLAB exit 0), but success marker not found."
                    message += f"\nMATLAB stdout:\n{process.stdout[:500]}"
                    if process.stderr:
                        message += f"\nMATLAB stderr:\n{process.stderr[:300]}"
            else: # MATLAB process exited with an error code
                success = False
                error_output = process.stderr or process.stdout # Prefer stderr for errors
                message = f"{self.success_message_prefix} failed. MATLAB Process Error (Return Code {process.returncode}):\n{error_output[:1000]}"
            
            self.original_signal.emit(success, message, output_data_for_signal if success else "")

        except subprocess.TimeoutExpired:
            message = f"{self.success_message_prefix} timed out after {timeout_seconds/60:.1f} minutes."
            self.original_signal.emit(False, message, "")
        except FileNotFoundError:
            message = f"MATLAB executable not found at: {self.matlab_path}"
            self.original_signal.emit(False, message, "")
        except Exception as e:
            message = f"Unexpected error in {self.success_message_prefix} worker: {str(e)}"
            self.original_signal.emit(False, message, "")
        finally:
            # Clean up temporary script and directory
            if os.path.exists(self.script_file):
                try:
                    os.remove(self.script_file)
                    # Only remove dir if it's empty (safer) or known to be exclusively for this script
                    script_dir = os.path.dirname(self.script_file)
                    if not os.listdir(script_dir): # Check if empty
                        os.rmdir(script_dir)
                    else:
                        print(f"Warning: Temp directory {script_dir} not empty, not removed.")
                except OSError as e:
                    print(f"Warning: Could not clean up temp script/dir: {e}") 
            self.finished_signal.emit(success, message, output_data_for_signal) # Signal thread completion


# --- Draggable Toolbox Buttons ---
class DraggableToolButton(QPushButton):
    def __init__(self, text, mime_type, style_sheet, parent=None):
        super().__init__(text, parent)
        self.mime_type = mime_type
        self.setText(text) 
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Ensure text is aligned beside icon if icon is present
        self.setStyleSheet(style_sheet + " QPushButton { border-radius: 5px; text-align: left; padding-left: 5px; }")
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
        mime_data.setText(self.text()) 
        mime_data.setData(self.mime_type, b"1") 
        drag.setMimeData(mime_data)

        pixmap_size = QSize(max(120, self.width()), self.height()) 
        pixmap = QPixmap(pixmap_size)
        pixmap.fill(Qt.transparent) 

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        button_rect = QRectF(0,0, pixmap_size.width()-1, pixmap_size.height()-1) # -1 for crisp border
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
        text_x_offset = 8 # Increased padding
        icon_y_offset = (pixmap_size.height() - icon_pixmap.height()) / 2
        if not icon_pixmap.isNull():
            painter.drawPixmap(int(text_x_offset), int(icon_y_offset), icon_pixmap)
            text_x_offset += icon_pixmap.width() + 8 # Space after icon
        
        painter.setPen(self.palette().buttonText().color()) # Use theme's text color
        painter.setFont(self.font())
        text_rect = QRectF(text_x_offset, 0, pixmap_size.width() - text_x_offset - 5, pixmap_size.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 4, pixmap.height() // 2)) # Hotspot more to the left

        drag.exec_(Qt.CopyAction | Qt.MoveAction) # Allow move if appropriate, though scene uses Copy


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
        self._font = QFont("Arial", 10, QFont.Bold) # Bold text

        self.setPen(QPen(QColor(50, 50, 50), 2)) # Darker border
        self.setBrush(QBrush(QColor(190, 220, 255))) # Lighter, cooler blue
        self.setFlags(QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges |
                      QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True) # For hover effects if needed

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Shadow effect (optional, can impact performance on many items)
        # painter.setPen(Qt.NoPen)
        # painter.setBrush(QColor(100,100,100,80))
        # painter.drawRoundedRect(self.rect().translated(3,3), 10, 10)

        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), 10, 10) 

        painter.setPen(self._text_color)
        painter.setFont(self._font)
        text_rect = self.rect().adjusted(8, 8, -8, -8) 
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)

        if self.is_initial:
            painter.setBrush(Qt.black)
            painter.setPen(QPen(Qt.black, 2)) # Thicker marker
            
            marker_radius = 7 # Smaller circle
            line_length = 20
            # Position marker to the left, ensuring it doesn't overlap with text if state is small
            start_marker_center_x = self.rect().left() - line_length - marker_radius / 2
            start_marker_center_y = self.rect().center().y()
            
            painter.drawEllipse(QPointF(start_marker_center_x, start_marker_center_y), marker_radius, marker_radius)

            line_start_point = QPointF(start_marker_center_x + marker_radius, start_marker_center_y)
            line_end_point = QPointF(self.rect().left(), start_marker_center_y)
            painter.drawLine(line_start_point, line_end_point)
            
            arrow_size = 10 # Larger arrowhead
            angle_rad = math.atan2(line_end_point.y() - line_start_point.y(), line_end_point.x() - line_start_point.x())
            
            arrow_p1 = line_end_point + QPointF(arrow_size * math.cos(angle_rad + math.pi / 6), arrow_size * math.sin(angle_rad + math.pi / 6))
            arrow_p2 = line_end_point + QPointF(arrow_size * math.cos(angle_rad - math.pi / 6), arrow_size * math.sin(angle_rad - math.pi / 6))
            # Corrected arrowhead direction: points towards line_end_point
            arrow_p1 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad + math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad + math.pi / 6))
            arrow_p2 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad - math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad - math.pi / 6))


            painter.setBrush(Qt.black)
            painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))


        if self.is_final:
            painter.setPen(QPen(Qt.black, 2))
            inner_rect = self.rect().adjusted(6, 6, -6, -6) # Thicker double border
            painter.drawRoundedRect(inner_rect, 7, 7) 

        if self.isSelected():
            pen = QPen(QColor(0, 100, 255, 200), 2.5, Qt.SolidLine) # More prominent selection
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            selection_rect = self.boundingRect().adjusted(-1,-1,1,1) # Slightly outside
            painter.drawRoundedRect(selection_rect, 11, 11) # Match rounding

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self) # For updating connected transitions
            # Snap to grid if enabled in scene (TODO: add grid snapping logic)
            # new_pos = self.pos()
            # grid_size = self.scene().grid_size
            # snapped_x = round(new_pos.x() / grid_size) * grid_size
            # snapped_y = round(new_pos.y() / grid_size) * grid_size
            # if new_pos.x() != snapped_x or new_pos.y() != snapped_y:
            #     self.setPos(snapped_x, snapped_y)
            #     return QPointF(snapped_x, snapped_y) # Inform system of actual new position
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
            self.prepareGeometryChange() # Call if visual representation might change
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

        self.setPen(QPen(QColor(0, 120, 120), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)) # Darker teal
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1) # Draw behind states if overlapping slightly
        self.setAcceptHoverEvents(True)
        self.update_path()

    def hoverEnterEvent(self, event: QEvent):
        self.setPen(QPen(QColor(0, 160, 160), 3)) # Highlight on hover
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QEvent):
        self.setPen(QPen(QColor(0, 120, 120), 2.5)) # Revert to normal pen
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 25 # Increased for text label and selection
        path_bounds = self.path().boundingRect()
        if self.text_label:
            fm = QFontMetrics(self._font)
            text_rect = fm.boundingRect(self.text_label)
            mid_point_on_path = self.path().pointAtPercent(0.5) # Approximate text position
            # Rough estimate of text render area relative to path midpoint
            # This needs to be generous as text position varies.
            text_render_rect = QRectF(mid_point_on_path.x() - text_rect.width() - 10, 
                                     mid_point_on_path.y() - text_rect.height() - 10,
                                     text_rect.width()*2 + 20, text_rect.height()*2 + 20) # Generous area
            path_bounds = path_bounds.united(text_render_rect)
        return path_bounds.adjusted(-extra, -extra, extra, extra)


    def shape(self): # Used for collision detection and selection outline
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(18 + self.pen().widthF()) # Wider for easier clicking
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
        line_from_target = QLineF(end_center, start_center) # Reversed for end item intersection
        end_point = self._get_intersection_point(self.end_item, line_from_target)


        if start_point is None: start_point = start_center # Fallback
        if end_point is None: end_point = end_center    # Fallback

        path = QPainterPath(start_point)

        if self.start_item == self.end_item: # Self-loop
            rect = self.start_item.sceneBoundingRect()
            loop_radius_x = rect.width() * 0.45 # Adjust loop size
            loop_radius_y = rect.height() * 0.45
            
            # Start and end points on the top edge for the loop
            p1 = QPointF(rect.center().x() + loop_radius_x * 0.3, rect.top())
            p2 = QPointF(rect.center().x() - loop_radius_x * 0.3, rect.top())
            
            # Control points for a more pronounced arc above the state
            ctrl1 = QPointF(rect.center().x() + loop_radius_x * 1.5, rect.top() - loop_radius_y * 3.0)
            ctrl2 = QPointF(rect.center().x() - loop_radius_x * 1.5, rect.top() - loop_radius_y * 3.0)
            
            path.moveTo(p1)
            path.cubicTo(ctrl1, ctrl2, p2)
            end_point = p2 # Update end_point for arrowhead calculation
        else: # Regular transition
            mid_x = (start_point.x() + end_point.x()) / 2
            mid_y = (start_point.y() + end_point.y()) / 2
            
            dx = end_point.x() - start_point.x()
            dy = end_point.y() - start_point.y()
            length = math.hypot(dx, dy) # math.hypot is sqrt(dx*dx + dy*dy)
            if length == 0: length = 1 

            # Normalized perpendicular vector (-dy/length, dx/length)
            perp_x = -dy / length
            perp_y = dx / length

            # control_point_offset.x() is perpendicular magnitude
            # control_point_offset.y() is tangential magnitude (shift along original line direction)
            
            ctrl_pt_x = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y()
            ctrl_pt_y = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()
            
            ctrl_pt = QPointF(ctrl_pt_x, ctrl_pt_y)
            
            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0:
                 path.lineTo(end_point)
            else:
                 path.quadTo(ctrl_pt, end_point)
        
        self.setPath(path)
        self.prepareGeometryChange()

    def _get_intersection_point(self, item, line):
        item_rect = item.sceneBoundingRect() 
        
        edges = [
            QLineF(item_rect.topLeft(), item_rect.topRight()),      
            QLineF(item_rect.topRight(), item_rect.bottomRight()),  
            QLineF(item_rect.bottomRight(), item_rect.bottomLeft()),
            QLineF(item_rect.bottomLeft(), item_rect.topLeft())     
        ]
        
        intersect_points = []
        temp_intersect_point = QPointF() # Re-use for QLineF.intersect
        for edge in edges:
            intersect_type = line.intersect(edge, temp_intersect_point)
            if intersect_type == QLineF.BoundedIntersection :
                 # Verify the intersection point is truly on the finite segment of 'edge'
                 # This is important because QLineF.BoundedIntersection checks against infinite lines.
                 edge_rect_for_check = QRectF(edge.p1(), edge.p2()).normalized()
                 # Add small tolerance for floating point issues
                 epsilon = 1e-3 
                 if (edge_rect_for_check.left() - epsilon <= temp_intersect_point.x() <= edge_rect_for_check.right() + epsilon and
                     edge_rect_for_check.top() - epsilon <= temp_intersect_point.y() <= edge_rect_for_check.bottom() + epsilon):
                    intersect_points.append(QPointF(temp_intersect_point)) # Store a copy

        if not intersect_points:
            # Fallback: if line starts inside the item, or no edge intersection found
            # return line.p1() # Could be problematic, use center
            return item_rect.center() 

        closest_point = intersect_points[0]
        min_dist_sq = QLineF(line.p1(), closest_point).lengthSquared() # Use lengthSquared for efficiency
        for pt in intersect_points[1:]:
            dist_sq = QLineF(line.p1(), pt).lengthSquared()
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_point = pt
        return closest_point


    def paint(self, painter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty():
            return

        painter.setRenderHint(QPainter.Antialiasing)
        current_pen = self.pen() # This might have been changed by hover events
        
        if self.isSelected():
            selection_pen = QPen(QColor(0,100,255,180), current_pen.widthF() + 2, Qt.SolidLine) 
            selection_pen.setCapStyle(Qt.RoundCap)
            selection_pen.setJoinStyle(Qt.RoundJoin)
            
            # Draw shape as selection highlight (drawn first, under the main line)
            stroker = QPainterPathStroker()
            stroker.setWidth(current_pen.widthF() + 8) # Make selection wider than line
            stroker.setCapStyle(Qt.RoundCap)
            stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path())
            painter.setPen(Qt.NoPen) # No border for this outer glow
            painter.setBrush(QColor(0,100,255,60)) # Softer glow
            painter.drawPath(selection_path_shape)
        
        painter.setPen(current_pen) 
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

        if self.path().elementCount() < 1 : return 

        # Arrowhead: use angleAtPercent for smoother arrow direction on curves
        percent_at_end = 0.999 # Slightly before the actual end to get a good tangent
        if self.path().length() < 1: percent_at_end = 0.9 # for very short paths
        
        line_end_point = self.path().pointAtPercent(1.0)
        # Angle is in degrees, convert to radians. Angle is CCW from positive X-axis.
        angle_at_end_rad = -self.path().angleAtPercent(percent_at_end) * (math.pi / 180.0) 
        # Negative because angleAtPercent is tangent direction, arrow needs to point "backwards" along tangent


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
            
            # Position text near midpoint, offset perpendicularly
            text_pos_on_path = self.path().pointAtPercent(0.5)
            angle_at_mid_deg = self.path().angleAtPercent(0.5) # Tangent angle at midpoint
            
            # Perpendicular offset (upwards from the line direction)
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0)
            offset_dist = 12 # Distance from path to text baseline
            
            # Adjust for text box height to center it relative to offset_dist
            text_center_x = text_pos_on_path.x() + offset_dist * math.cos(offset_angle_rad)
            text_center_y = text_pos_on_path.y() + offset_dist * math.sin(offset_angle_rad)

            # Final text drawing position (top-left of text bounding box)
            text_final_pos = QPointF(text_center_x - text_rect_original.width() / 2,
                                     text_center_y - text_rect_original.height() / 2)

            # Background for text for readability
            bg_padding = 3
            bg_rect = QRectF(text_final_pos.x() - bg_padding, 
                             text_final_pos.y() - bg_padding, 
                             text_rect_original.width() + 2 * bg_padding, 
                             text_rect_original.height() + 2 * bg_padding)
            
            painter.setBrush(QColor(250, 250, 250, 200)) # Semi-transparent light background
            painter.setPen(QPen(QColor(200,200,200,150), 0.5)) # Faint border for text bg
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
            self.update_path() # This will prepareGeometryChange
            self.update()


# --- Undo Commands ---
class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item_instance = item 

        if isinstance(item, GraphicsTransitionItem):
            # Store names for robust relinking if states are also part of undo/redo chains separately
            self.start_item_name = item.start_item.text_label if item.start_item else None
            self.end_item_name = item.end_item.text_label if item.end_item else None
            # Store other relevant properties to fully reconstruct if needed
            self.label = item.text_label
            self.control_offset = item.control_point_offset
        elif isinstance(item, GraphicsStateItem):
            self.item_data = item.get_data() # Store all data to recreate if item is complex

    def redo(self):
        if self.item_instance.scene() is None: # If undone, item is removed from scene
            self.scene.addItem(self.item_instance)

        if isinstance(self.item_instance, GraphicsTransitionItem):
            # Ensure links are valid, especially if states were involved in other undo/redo
            start_node = self.scene.get_state_by_name(self.start_item_name)
            end_node = self.scene.get_state_by_name(self.end_item_name)
            if start_node and end_node:
                self.item_instance.start_item = start_node
                self.item_instance.end_item = end_node
                self.item_instance.update_path()
            else:
                # This is a critical issue if states are missing
                self.scene.log_function(f"Error (Redo Add Transition): Could not link transition '{self.label}'. Source '{self.start_item_name}' or Target '{self.end_item_name}' state missing.")
                # Decide: remove the transition, or leave it disconnected?
                # For now, it's added but might be visually incorrect.
                # self.scene.removeItem(self.item_instance) # Option: remove if invalid
        
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
        # Store full data to recreate items, not just instances, for robustness across sessions/complex undos
        self.removed_items_data = []
        for item in items_to_remove:
            item_data = item.get_data()
            item_data['_type'] = item.type() # Store type for reconstruction
            self.removed_items_data.append(item_data)
        
        # Keep instances for quick redo/undo if they are not complexly managed
        self.item_instances_for_quick_toggle = list(items_to_remove)


    def redo(self): # Perform the removal
        for item_instance in self.item_instances_for_quick_toggle:
            if item_instance.scene() == self.scene: 
                self.scene.removeItem(item_instance)
        self.scene.set_dirty(True)

    def undo(self): # Add the items back
        # Recreate items from stored data for robustness
        # This assumes get_data() and constructor logic is sufficient
        newly_added_instances = []
        states_map_for_undo = {}

        # Add states first
        for item_data in self.removed_items_data:
            if item_data['_type'] == GraphicsStateItem.Type:
                state = GraphicsStateItem(item_data['x'], item_data['y'], item_data['width'], item_data['height'],
                                          item_data['name'], item_data['is_initial'], item_data['is_final'])
                self.scene.addItem(state)
                newly_added_instances.append(state)
                states_map_for_undo[state.text_label] = state
        
        # Then add transitions, linking them to newly added states
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
        
        # Update the quick toggle list for next redo (if applicable, though this path reconstructs)
        self.item_instances_for_quick_toggle = newly_added_instances
        self.scene.set_dirty(True)


class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_and_new_positions, description="Move Items"):
        super().__init__(description)
        # items_and_new_positions: list of (item_instance, new_QPointF_pos)
        self.items_and_new_positions = items_and_new_positions
        self.items_and_old_positions = []
        self.scene_ref = None
        if self.items_and_new_positions: 
            # Get the scene from the first item, assuming all items are from the same scene
            self.scene_ref = self.items_and_new_positions[0][0].scene()
            for item, _ in self.items_and_new_positions:
                self.items_and_old_positions.append((item, item.pos())) # Store current (old) pos

    def _apply_positions(self, positions_list):
        if not self.scene_ref: return
        for item, pos in positions_list:
            item.setPos(pos) # This will trigger itemChange in GraphicsStateItem
                             # which in turn emits item_moved, handled by scene to update transitions
            # Explicitly update transitions if itemChange isn't robust enough or for other types
            if isinstance(item, GraphicsStateItem):
                 self.scene_ref._update_connected_transitions(item)

        self.scene_ref.update() # Request a repaint of the scene
        self.scene_ref.set_dirty(True)

    def redo(self):
        self._apply_positions(self.items_and_new_positions)
    
    def undo(self):
        self._apply_positions(self.items_and_old_positions)

class EditItemPropertiesCommand(QUndoCommand):
    def __init__(self, item, old_props, new_props, description="Edit Properties"):
        super().__init__(description)
        self.item = item # The actual QGraphicsItem instance
        self.old_props = old_props # dict: e.g., {'name': 'S1', 'is_initial': False}
        self.new_props = new_props # dict
        self.scene_ref = item.scene()

    def _apply_properties(self, props_to_apply):
        if not self.item or not self.scene_ref: return

        original_name_if_state = None
        if isinstance(self.item, GraphicsStateItem):
            original_name_if_state = self.item.text_label # Store before changing
            self.item.set_properties(props_to_apply['name'], 
                                     props_to_apply.get('is_initial', False), # Use .get for safety
                                     props_to_apply.get('is_final', False))
            # If state name changed, transitions need to know (conceptually, their data changes)
            if original_name_if_state != props_to_apply['name']:
                self.scene_ref._update_transitions_for_renamed_state(original_name_if_state, props_to_apply['name'])
        
        elif isinstance(self.item, GraphicsTransitionItem):
            self.item.set_text(props_to_apply['label'])
            if 'control_offset_x' in props_to_apply and 'control_offset_y' in props_to_apply:
                 self.item.set_control_point_offset(QPointF(props_to_apply['control_offset_x'], 
                                                            props_to_apply['control_offset_y']))
        
        self.item.update() # Redraw the item
        self.scene_ref.update() # Redraw the scene
        self.scene_ref.set_dirty(True)

    def redo(self):
        self._apply_properties(self.new_props)

    def undo(self):
        self._apply_properties(self.old_props)


# --- Diagram Scene ---
class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem) # Emitted by GraphicsStateItem.itemChange
    # itemSelected = pyqtSignal(QGraphicsItem) # If needed for property editor etc.
    modifiedStatusChanged = pyqtSignal(bool) # True if scene is dirty

    def __init__(self, undo_stack, parent_window=None): # parent_window for mode change coupling
        super().__init__(parent_window) # parent_window is QMainWindow here
        self.parent_window = parent_window
        self.setSceneRect(0, 0, 5000, 4000) # Larger default scene
        self.current_mode = "select" 
        self.transition_start_item = None
        self.log_function = print 
        self.undo_stack = undo_stack
        self._dirty = False
        self._mouse_press_items_positions = {} 
        self._temp_transition_line = None 

        self.item_moved.connect(self._handle_item_moved) 

        # Grid settings
        self.grid_size = 20
        self.grid_pen_light = QPen(QColor(225, 225, 225), 0.8, Qt.SolidLine) # Slightly darker light lines
        self.grid_pen_dark = QPen(QColor(200, 200, 200), 1.0, Qt.SolidLine) # Slightly darker major lines
        self.setBackgroundBrush(QColor(248, 248, 248)) # Very light grey

        # For snapping items to grid during move (optional)
        self.snap_to_grid_enabled = True 


    def _update_connected_transitions(self, state_item):
        """Updates all transitions connected to the given state_item."""
        for item in self.items(): # Iterate over all items in the scene
            if isinstance(item, GraphicsTransitionItem):
                if item.start_item == state_item or item.end_item == state_item:
                    item.update_path() # Recalculate and redraw the transition path
    
    def _update_transitions_for_renamed_state(self, old_name, new_name):
        """
        Called by EditItemPropertiesCommand when a state's name changes.
        Transitions store direct references, so their internal `start_item.text_label`
        will reflect the new name. This function is mostly for data integrity if
        names were used as keys elsewhere or if transitions stored names instead of refs.
        For visual updates, `_update_connected_transitions` is more direct if a state MOVES.
        If only name changes, the transition's `get_data()` will be correct.
        The transition's paint method reading `start_item.text_label` will also be fine.
        No specific action needed here if transitions use direct item references.
        """
        # self.log_function(f"State '{old_name}' renamed to '{new_name}'. Transitions using this state will reflect the change.")
        # Force update of any transitions that might be using this state by name in their labels (unlikely for path)
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                if (item.start_item and item.start_item.text_label == new_name) or \
                   (item.end_item and item.end_item.text_label == new_name):
                    item.update() # Trigger a repaint, which might re-evaluate labels if they depend on names

    def get_state_by_name(self, name):
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name:
                return item
        return None

    def set_dirty(self, dirty=True):
        if self._dirty != dirty:
            self._dirty = dirty
            self.modifiedStatusChanged.emit(dirty) 
            if self.parent_window: # Update main window's save actions
                self.parent_window._update_save_actions_enable_state()
            
    def is_dirty(self):
        return self._dirty

    def set_log_function(self, log_function):
        self.log_function = log_function

    def set_mode(self, mode):
        old_mode = self.current_mode
        if old_mode == mode: return # No change
        
        self.current_mode = mode
        self.log_function(f"Interaction mode changed to: {mode}")
        
        self.transition_start_item = None 
        if self._temp_transition_line:
            self.removeItem(self._temp_transition_line)
            self._temp_transition_line = None

        # Update cursors and item flags
        if mode == "select":
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            for item in self.items(): 
                if isinstance(item, GraphicsStateItem): item.setFlag(QGraphicsItem.ItemIsMovable, True)
        elif mode == "state":
            QApplication.setOverrideCursor(Qt.CrossCursor) 
            for item in self.items(): 
                 if isinstance(item, GraphicsStateItem): item.setFlag(QGraphicsItem.ItemIsMovable, False)
        elif mode == "transition":
            QApplication.setOverrideCursor(Qt.PointingHandCursor) # Indicate clickable states
            for item in self.items(): 
                 if isinstance(item, GraphicsStateItem): item.setFlag(QGraphicsItem.ItemIsMovable, False)
        
        # If old mode had an override cursor, restore it unless new mode also sets one
        if old_mode in ["state", "transition"] and mode not in ["state", "transition"]:
            QApplication.restoreOverrideCursor()
        
        # Ensure toolbar buttons in MainWindow reflect the change
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
            # Snapping logic (if enabled and item is being moved by user, not programmatically)
            if self.snap_to_grid_enabled and self._mouse_press_items_positions: # Check if user drag
                new_pos = moved_item.pos()
                snapped_x = round(new_pos.x() / self.grid_size) * self.grid_size
                snapped_y = round(new_pos.y() / self.grid_size) * self.grid_size
                if new_pos.x() != snapped_x or new_pos.y() != snapped_y:
                    # This can cause recursion if setPos also triggers itemChange->item_moved
                    # So, MoveItemsCommand should handle snapping *after* move.
                    # For now, this is a direct snap.
                    # moved_item.setPos(snapped_x, snapped_y)
                    # self._update_connected_transitions(moved_item) # Update again after snap
                    pass # Let MoveCommand handle final snapping

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos()
        items_at_pos = self.items(pos)
        # Prioritize State items for interaction
        state_item_at_pos = next((item for item in items_at_pos if isinstance(item, GraphicsStateItem)), None)
        top_item_at_pos = state_item_at_pos if state_item_at_pos else (items_at_pos[0] if items_at_pos else None)

        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size - 60 # Offset for centering
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
            else: # Select mode
                self._mouse_press_items_positions.clear()
                # Record positions only for selected items that are movable
                selected_movable = [item for item in self.selectedItems() if item.flags() & QGraphicsItem.ItemIsMovable]
                for item in selected_movable:
                     self._mouse_press_items_positions[item] = item.pos()
                # If clicking an unselected item, it will be selected by super().mousePressEvent
                # If clicking empty space for rubber band, super also handles it.
                super().mousePressEvent(event) 
        
        elif event.button() == Qt.RightButton:
            if top_item_at_pos and isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsTransitionItem)):
                if not top_item_at_pos.isSelected():
                    self.clearSelection()
                    top_item_at_pos.setSelected(True)
                self._show_context_menu(top_item_at_pos, event.screenPos())
            else: 
                self.clearSelection()
                # self._show_scene_context_menu(event.screenPos()) # For scene-wide actions
        else: 
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            self._temp_transition_line.setLine(QLineF(self.transition_start_item.sceneBoundingRect().center(), event.scenePos()))
            # self.update() # Scene updates automatically for QGraphicsLineItem changes
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            if self._mouse_press_items_positions: 
                moved_items_data = []
                for item, old_pos in self._mouse_press_items_positions.items():
                    new_pos = item.pos()
                    # Snap to grid after move, if enabled
                    if self.snap_to_grid_enabled:
                        snapped_x = round(new_pos.x() / self.grid_size) * self.grid_size
                        snapped_y = round(new_pos.y() / self.grid_size) * self.grid_size
                        # If snapping changes position, update item and use snapped_pos for command
                        if new_pos.x() != snapped_x or new_pos.y() != snapped_y:
                            item.setPos(snapped_x, snapped_y) # This triggers item_moved -> _handle_item_moved
                            new_pos = QPointF(snapped_x, snapped_y)
                    
                    if (new_pos - old_pos).manhattanLength() > 1: # Threshold for significant move
                        moved_items_data.append((item, new_pos)) 
                
                if moved_items_data:
                    cmd = MoveItemsCommand(moved_items_data)
                    self.undo_stack.push(cmd)
                    # _handle_item_moved and MoveCommand's redo/undo update transitions
                self._mouse_press_items_positions.clear()

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        items_at_pos = self.items(event.scenePos())
        state_item_at_pos = next((item for item in items_at_pos if isinstance(item, GraphicsStateItem)), None)
        item_to_edit = state_item_at_pos
        if not item_to_edit: # If no state, check for transition
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
            if not item.isSelected(): # Should be selected by right-click logic
                self.clearSelection() 
                item.setSelected(True)
            self.delete_selected_items()

    def edit_item_properties(self, item):
        original_name = None # For state name duplicate check
        if isinstance(item, GraphicsStateItem):
            original_name = item.text_label 
            old_props = item.get_data() # Use get_data for consistent property set
            dialog = StatePropertiesDialog(item.text_label, item.is_initial, item.is_final, self.parent_window)
            if dialog.exec_() == QDialog.Accepted:
                new_name = dialog.get_name()
                if new_name != original_name and self.get_state_by_name(new_name):
                    QMessageBox.warning(self.parent_window, "Duplicate Name", f"A state with the name '{new_name}' already exists.")
                    return
                
                new_props = {'name': new_name, 
                             'is_initial': dialog.is_initial_cb.isChecked(), 
                             'is_final': dialog.is_final_cb.isChecked(),
                             # Carry over position and size from old_props if not changed by dialog
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
                             # Carry over source/target from old_props
                             'source': old_props['source'], 'target': old_props['target']}
                cmd = EditItemPropertiesCommand(item, old_props, new_props, "Edit Transition Properties")
                self.undo_stack.push(cmd)
                self.log_function(f"Properties updated for transition: {new_props['label']}")
        
        self.update()

    def _add_state_item(self, pos: QPointF, name_prefix="State"): # pos is top-left for new state
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
                    pos.x(), pos.y(), 120, 60, # Use pos as top-left directly
                    props_dialog.get_name(),
                    props_dialog.is_initial_cb.isChecked(),
                    props_dialog.is_final_cb.isChecked()
                )
                cmd = AddItemCommand(self, new_state, "Add State")
                self.undo_stack.push(cmd)
                self.log_function(f"Added state: {new_state.text_label} at ({pos.x():.0f},{pos.y():.0f})")
        
        if self.current_mode == "state": # Revert mode after click-add
            self.set_mode("select") # This will trigger parent_window's action check


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

            # If clicking same state for self-loop, or different state for regular transition
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

        items_to_delete_with_related = set() # Use a set to avoid duplicates
        for item in selected:
            items_to_delete_with_related.add(item) # Add the initially selected item
            if isinstance(item, GraphicsStateItem):
                # Find all transitions connected to this state
                for scene_item in self.items(): 
                    if isinstance(scene_item, GraphicsTransitionItem):
                        if scene_item.start_item == item or scene_item.end_item == item:
                            items_to_delete_with_related.add(scene_item)
        
        if items_to_delete_with_related:
            cmd = RemoveItemsCommand(self, list(items_to_delete_with_related), "Delete Items")
            self.undo_stack.push(cmd)
            self.log_function(f"Queued deletion of {len(items_to_delete_with_related)} item(s).")
            # Actual removal happens in cmd.redo(), selection cleared by scene after command usually
            self.clearSelection() # Clear selection immediately for visual feedback


    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-state-tool"):
            event.setAccepted(True) # Indicate valid drop target
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
            
            grid_x = round(pos.x() / self.grid_size) * self.grid_size - 60 # Offset to center on drop
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
                if item.start_item and item.end_item: # Only save valid transitions
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
        super().drawBackground(painter, rect) # Draws the self.backgroundBrush()

        # Define visible rectangle in scene coordinates
        view_rect = self.views()[0].viewport().rect() if self.views() else rect
        visible_scene_rect = self.views()[0].mapToScene(view_rect).boundingRect() if self.views() else rect
        
        left = int(visible_scene_rect.left())
        right = int(visible_scene_rect.right())
        top = int(visible_scene_rect.top())
        bottom = int(visible_scene_rect.bottom())

        first_left = left - (left % self.grid_size)
        first_top = top - (top % self.grid_size)

        # Light grid lines (dots for less visual clutter)
        painter.setPen(self.grid_pen_light)
        for x in range(first_left, right, self.grid_size):
            for y in range(first_top, bottom, self.grid_size):
                 if (x % (self.grid_size * 5) != 0) and (y % (self.grid_size * 5) != 0): # Avoid drawing over dark lines
                    painter.drawPoint(x, y)


        # Darker grid lines (full lines for major divisions)
        dark_lines = []
        major_grid_size = self.grid_size * 5
        first_major_left = left - (left % major_grid_size)
        first_major_top = top - (top % major_grid_size)

        painter.setPen(self.grid_pen_dark)
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
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate) # More efficient
        self.zoom_level = 0 

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter) # AnchorUnderMouse can be jumpy
        self._is_panning = False
        self._is_panning_with_mouse = False # For middle mouse button pan
        self._last_pan_point = QPoint()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0: factor = 1.12; self.zoom_level += 1
            else: factor = 1 / 1.12; self.zoom_level -= 1
            
            # Limit zoom (e.g., 10 levels in/out)
            if -10 <= self.zoom_level <= 20: 
                self.scale(factor, factor)
            else: # Revert zoom_level if limit reached
                if delta > 0: self.zoom_level -=1 
                else: self.zoom_level +=1
            event.accept()
        else:
            super().wheelEvent(event) # Default for scrolling

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not self._is_panning and not event.isAutoRepeat():
            self._is_panning = True
            # Note: QGraphicsView's event.pos() is in view coordinates. mapToScene for scene coords.
            self._last_pan_point = event.pos() # Store view coords for panning delta
            self.setCursor(Qt.OpenHandCursor) # Indicate panning is possible
            event.accept()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal: 
            self.scale(1.12, 1.12); self.zoom_level +=1
        elif event.key() == Qt.Key_Minus: 
            self.scale(1/1.12, 1/1.12); self.zoom_level -=1
        elif event.key() == Qt.Key_0 or event.key() == Qt.Key_Asterisk: # Reset zoom
             self.resetTransform() 
             self.zoom_level = 0
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and self._is_panning and not event.isAutoRepeat():
            self._is_panning = False
            # Restore cursor based on current scene mode
            current_scene_mode = self.scene().current_mode if self.scene() else "select"
            if current_scene_mode == "select": self.setCursor(Qt.ArrowCursor)
            elif current_scene_mode == "state": self.setCursor(Qt.CrossCursor)
            elif current_scene_mode == "transition": self.setCursor(Qt.PointingHandCursor)
            else: self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        # Middle mouse button panning OR Space + Left Click panning
        if event.button() == Qt.MiddleButton or \
           (self._is_panning and event.button() == Qt.LeftButton):
            self._last_pan_point = event.pos() # View coordinates
            self.setCursor(Qt.ClosedHandCursor)
            self._is_panning_with_mouse = True 
            event.accept()
        else:
            self._is_panning_with_mouse = False
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse:
            delta_view = event.pos() - self._last_pan_point # Delta in view coordinates
            self._last_pan_point = event.pos()
            
            # Translate the view by adjusting scrollbars
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
            if self._is_panning: # If space was held, cursor is OpenHand until space release
                self.setCursor(Qt.OpenHandCursor)
            else: # Middle mouse only, restore appropriate cursor
                current_scene_mode = self.scene().current_mode if self.scene() else "select"
                if current_scene_mode == "select": self.setCursor(Qt.ArrowCursor)
                # ... other modes as in keyReleaseEvent
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
        self.offset_perp_spin.setRange(-800, 800) # Wider range for curve control
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

    def get_label(self): return self.label_edit.text() # Not stripping, label can have spaces
    def get_control_offset(self): return QPointF(self.offset_perp_spin.value(), self.offset_tang_spin.value())


class MatlabSettingsDialog(QDialog):
    def __init__(self, matlab_connection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings")
        self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"))
        self.setMinimumWidth(550) # Increased width for longer messages

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
        self.test_status_label.setWordWrap(True) # Allow long messages to wrap
        self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse) # Allow copying status
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
        if self.matlab_connection.detect_matlab(): 
            self.path_edit.setText(self.matlab_connection.matlab_path)
            # Signal from detect_matlab will call _update_test_label_from_signal
        # else: # Signal also handles failure message


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
        
        # set_matlab_path will emit status, then test_connection will emit its own status
        # This sequence is important.
        if self.matlab_connection.set_matlab_path(path): # Path is structurally valid
            self.matlab_connection.test_connection() # Actively test it
        # else: set_matlab_path already emitted "invalid path"


    def _update_test_label_from_signal(self, success, message):
        # This signal is emitted by MatlabConnection for various events
        status_prefix = "Status: "
        if "MATLAB path set" in message and success: # From set_matlab_path success
             status_prefix = "Status: Path validated. "
        elif "successful" in message and success: # From test_connection success
             status_prefix = "Status: Connected! "

        self.test_status_label.setText(status_prefix + message)
        self.test_status_label.setStyleSheet("color: #006400; font-weight: bold;" if success else "color: #B22222; font-weight: bold;")
        if success and self.matlab_connection.matlab_path: 
             self.path_edit.setText(self.matlab_connection.matlab_path) 

    def _apply_settings(self):
        path = self.path_edit.text().strip()
        # Attempt to set the path. If it's structurally invalid, set_matlab_path handles it and emits.
        # If it's structurally valid, it's set, and then we might test it if not already done.
        if not self.matlab_connection.set_matlab_path(path): # Path is empty or invalid format
            if path: # If user entered something invalid
                QMessageBox.warning(self, "Invalid Path", 
                                    self.test_status_label.text().replace("Status: ", "") + 
                                    "\nPlease ensure the path points to a valid MATLAB executable.")
                # Don't accept if path is non-empty and invalid.
                # If path is empty, set_matlab_path clears it and returns True (effectively) or connection status changes.
                # The goal is to store a valid or empty path.
                if not self.matlab_connection.connected: # If set_matlab_path failed and path was not empty
                    return 
            # If path was empty, set_matlab_path clears internal path and emits disconnected status. That's fine to accept.
        
        # If path is now set (valid format) and connection status is not True yet (e.g. path changed, not tested after)
        # or if user wants to be sure on Apply.
        # However, the signals should keep status_label mostly up-to-date.
        # The crucial part is that matlab_connection has the new path.
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
        # Initial MATLAB status display (will be updated by signal if auto-detect works or settings are loaded)
        self._update_matlab_status_display(False, "Initializing. Configure in Simulation menu or attempt auto-detect.")
        
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished) 

        self._update_window_title() 
        self.on_new_file(silent=True) 

        self.scene.selectionChanged.connect(self._update_properties_dock)
        self._update_properties_dock() # Initial state

        # Attempt auto-detection of MATLAB on startup (optional)
        # QTimer.singleShot(1000, self.matlab_connection.detect_matlab) # Delay slightly


    def init_ui(self):
        self.setGeometry(50, 50, 1500, 950) # Larger default window
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
        # self.scene.set_mode("select") # Trigger should handle this


    def _create_actions(self):
        # Helper to safely get QStyle enum values
        def _safe_get_style_enum(attr_name, fallback_attr_name=None):
            try: return getattr(QStyle, attr_name)
            except AttributeError:
                if fallback_attr_name:
                    try: return getattr(QStyle, fallback_attr_name)
                    except AttributeError: pass
                return QStyle.SP_CustomBase 


        # File
        self.new_action = QAction(get_standard_icon(QStyle.SP_FileIcon, "New"), "&New", self, shortcut=QKeySequence.New, statusTip="Create a new file", triggered=self.on_new_file)
        self.open_action = QAction(get_standard_icon(QStyle.SP_DialogOpenButton, "Opn"), "&Open...", self, shortcut=QKeySequence.Open, statusTip="Open an existing file", triggered=self.on_open_file)
        self.save_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton, "Sav"), "&Save", self, shortcut=QKeySequence.Save, statusTip="Save the current file", triggered=self.on_save_file)
        self.save_as_action = QAction(get_standard_icon(QStyle.SP_DialogSaveButton),"Save &As...", self, shortcut=QKeySequence.SaveAs, statusTip="Save the current file with a new name", triggered=self.on_save_file_as)
        self.exit_action = QAction(get_standard_icon(QStyle.SP_DialogCloseButton, "Exit"), "E&xit", self, shortcut=QKeySequence.Quit, statusTip="Exit the application", triggered=self.close)

        # Edit
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
        
        # Scene Interaction Modes
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

        # Simulation
        self.export_simulink_action = QAction(get_standard_icon(QStyle.SP_ArrowRight, "->M"), "&Export to Simulink...", self, statusTip="Generate a Simulink model from the diagram", triggered=self.on_export_simulink)
        self.run_simulation_action = QAction(get_standard_icon(QStyle.SP_MediaPlay, "Run"), "&Run Simulation...", self, statusTip="Run a Simulink model (requires MATLAB with Simulink)", triggered=self.on_run_simulation)
        self.generate_code_action = QAction(get_standard_icon(QStyle.SP_ComputerIcon, "Cde"), "Generate &Code (C/C++)...", self, statusTip="Generate C/C++ code from a Simulink model (requires MATLAB Coder & Simulink Coder / Embedded Coder)", triggered=self.on_generate_code)
        self.matlab_settings_action = QAction(get_standard_icon(_safe_get_style_enum("SP_ComputerIcon"), "Cfg"), "&MATLAB Settings...", self, statusTip="Configure MATLAB connection settings", triggered=self.on_matlab_settings)

        # Help
        self.about_action = QAction(get_standard_icon(QStyle.SP_DialogHelpButton, "?"), "&About", self, statusTip=f"Show information about {APP_NAME}", triggered=self.on_about)


    def _create_menus(self):
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet("QMenuBar { background-color: #E8E8E8; } QMenu::item:selected { background-color: #D0D0D0; }")
        # File Menu
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_simulink_action) 
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
        mode_menu = edit_menu.addMenu(get_standard_icon(QStyle.SP_DesktopIcon, "Mode"),"Interaction Mode") 
        mode_menu.addAction(self.select_mode_action)
        mode_menu.addAction(self.add_state_mode_action)
        mode_menu.addAction(self.add_transition_mode_action)


        # Simulation Menu
        sim_menu = menu_bar.addMenu("&Simulation")
        sim_menu.addAction(self.run_simulation_action)
        sim_menu.addAction(self.generate_code_action)
        sim_menu.addSeparator()
        sim_menu.addAction(self.matlab_settings_action)

        self.view_menu = menu_bar.addMenu("&View")
        # View menu will get dock toggles later

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        icon_size = QSize(28,28) # Larger icons
        # File Toolbar
        file_toolbar = self.addToolBar("File")
        file_toolbar.setObjectName("FileToolBar")
        file_toolbar.setIconSize(icon_size)
        file_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon) # Text under icon
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
        
        # Tools Toolbar (Interaction Modes)
        tools_tb = self.addToolBar("Interaction Tools") # Renamed for clarity
        tools_tb.setObjectName("ToolsToolBar")
        tools_tb.setIconSize(icon_size)
        tools_tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        tools_tb.addAction(self.select_mode_action)
        tools_tb.addAction(self.add_state_mode_action)
        tools_tb.addAction(self.add_transition_mode_action)
        self.addToolBarBreak() # Move next toolbar to new row

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
        self.progress_bar.setTextVisible(False) # Cleaner look for indeterminate
        self.status_bar.addPermanentWidget(self.progress_bar)


    def _create_docks(self):
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)
        # Tools Dock 
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

        # Log Dock
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
        
        # Properties Dock
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
        # Keep log scrolled to bottom
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
        
        # Update status bar briefly
        self.status_label.setText(message.split('\n')[0][:120]) 
        # QTimer.singleShot(7000, lambda: self.status_label.setText("Ready") if not self.progress_bar.isVisible() else None)


    def _update_window_title(self):
        title = APP_NAME
        if self.current_file_path:
            title += f" - {os.path.basename(self.current_file_path)}"
        else:
            title += " - Untitled"
        
        title += "[*]" 
        self.setWindowTitle(title)

    def _update_save_actions_enable_state(self):
        is_dirty = self.scene.is_dirty() # or self.isWindowModified()
        self.save_action.setEnabled(is_dirty)
        # save_as_action should always be enabled as long as there's a scene
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
        
        # Disable UI elements that might interfere
        self.set_ui_enabled_for_matlab_op(False)

    def _finish_matlab_operation(self):
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready") # Reset general status
        self.set_ui_enabled_for_matlab_op(True)
        self.log_message("MATLAB Operation: Finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        """Helper to enable/disable UI parts during long operations."""
        self.menuBar().setEnabled(enabled)
        # Iterate over toolbars and disable/enable them
        for child in self.children(): # More robust way to find toolbars
            if isinstance(child, QToolBar):
                child.setEnabled(enabled)
        if self.centralWidget(): self.centralWidget().setEnabled(enabled)
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock"]: 
            dock = self.findChild(QDockWidget, dock_name)
            if dock: 
                # For LogDock, we might want to keep it enabled to see messages
                if dock_name == "LogDock" and not enabled: # Disabling
                    pass # Keep log dock enabled
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
                    # Use QDesktopServices for platform-agnostic opening
                    from PyQt5.QtGui import QDesktopServices
                    from PyQt5.QtCore import QUrl
                    QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(output_dir)))
                except Exception as e:
                    self.log_message(f"Error opening directory {output_dir}: {e}")
                    QMessageBox.warning(self, "Error Opening Directory", f"Could not open directory:\n{e}")

        elif not success:
            QMessageBox.warning(self, "Code Generation Failed", message)


    # --- File Operations ---
    def _prompt_save_if_dirty(self):
        if not self.isWindowModified(): # Checks the [*] status
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
        return True # Discard

    def on_new_file(self, silent=False): 
        if not silent and not self._prompt_save_if_dirty():
            return False 
        
        self.scene.clear() 
        self.scene.setSceneRect(0,0,5000,4000) 
        self.current_file_path = None
        self.last_generated_model_path = None 
        self.undo_stack.clear() # Clear history for new file
        self.scene.set_dirty(False) # Sets windowModified to False
        self._update_window_title() 
        # _update_save_actions_enable_state called by set_dirty
        self._update_undo_redo_actions_enable_state()
        if not silent: self.log_message("New diagram created. Ready.")
        self.view.resetTransform() # Reset zoom/pan for new file
        self.view.centerOn(2500,2000) # Center view on typical start area
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
                self.undo_stack.clear() # Clear undo for new file
                self.scene.set_dirty(False) # Loaded file is initially not dirty
                self._update_window_title()
                self._update_undo_redo_actions_enable_state()
                self.log_message(f"Successfully opened: {file_path}")
                # Fit view to loaded content
                # Ensure itemsBoundingRect is valid (not empty)
                items_bounds = self.scene.itemsBoundingRect()
                if not items_bounds.isEmpty():
                    # Add some padding around the items
                    padded_bounds = items_bounds.adjusted(-100, -100, 100, 100)
                    self.view.fitInView(padded_bounds, Qt.KeepAspectRatio)
                else: # Empty diagram, reset view
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
                self.scene.set_dirty(False) # Mark as not modified
                # _update_save_actions_enable_state is called by set_dirty
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
        try:
            data = self.scene.get_diagram_data()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False) 
            self.log_message(f"File saved successfully: {file_path}")
            return True
        except Exception as e:
            self.log_message(f"Error saving file to {file_path}: {str(e)}")
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{str(e)}")
            return False
            
    # --- Action Handlers ---
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
        dir_layout.addWidget(output_dir_edit, 1) # Make edit stretch
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
                # Threads are QThreads managing subprocesses. Quitting QThread doesn't kill subprocess directly.
                # Proper cleanup would involve storing subprocess.Popen objects and terminating them.
                # For now, this is a notification.
            event.accept()
        else:
            event.ignore() 


if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    
    # Optional: Apply a global stylesheet for a more consistent look
    # app.setStyleSheet("""
    #     QMainWindow, QDialog, QDockWidget { background-color: #F0F0F0; }
    #     QPushButton { background-color: #E0E0E0; border: 1px solid #C0C0C0; padding: 5px; border-radius: 3px; }
    #     QPushButton:hover { background-color: #D0D0D0; }
    #     QPushButton:pressed { background-color: #C0C0C0; }
    #     QLineEdit, QTextEdit, QSpinBox, QComboBox { background-color: white; border: 1px solid #B0B0B0; padding: 3px; border-radius: 3px; }
    #     QGroupBox { font-weight: bold; }
    # """)
    # Or use a predefined style
    # app.setStyle(QStyleFactory.create('Fusion'))


    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
