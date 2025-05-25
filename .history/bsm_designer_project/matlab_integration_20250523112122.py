import sys
import os
import tempfile
import subprocess
from PyQt5.QtCore import QObject, pyqtSignal, QThread

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
             if not self.set_matlab_path(self.matlab_path): return False # Try to validate/set path again
        try:
            # -batch: Run script non-interactively, exit on completion/error
            # -nodisplay: For systems without display, headless.
            # -nosplash: Skip splash screen for faster startup.
            # -nodesktop: Run without MATLAB desktop GUI.
            cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", "disp('MATLAB_CONNECTION_TEST_SUCCESS')"]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

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
        except subprocess.CalledProcessError as e:
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
                # R20XXy (e.g., R2023b)
                versions = sorted([d for d in os.listdir(matlab_base) if d.startswith('R20') and len(d) > 4], reverse=True)
                for v_year_letter in versions:
                    paths_to_check.append(os.path.join(matlab_base, v_year_letter, 'bin', 'matlab.exe'))
        elif sys.platform == 'darwin': # macOS
            base_app_path = '/Applications'
            potential_matlab_apps = sorted([d for d in os.listdir(base_app_path) if d.startswith('MATLAB_R20') and d.endswith('.app')], reverse=True)
            for app_name in potential_matlab_apps:
                paths_to_check.append(os.path.join(base_app_path, app_name, 'bin', 'matlab'))
        else: # Linux/Other Unix
            common_base_paths = ['/usr/local/MATLAB', '/opt/MATLAB'] # Common installation prefixes
            for base_path in common_base_paths:
                if os.path.isdir(base_path):
                    versions = sorted([d for d in os.listdir(base_path) if d.startswith('R20') and len(d) > 4], reverse=True)
                    for v_year_letter in versions:
                         paths_to_check.append(os.path.join(base_path, v_year_letter, 'bin', 'matlab'))
            paths_to_check.append('matlab') # Check if 'matlab' is in PATH

        for path_candidate in paths_to_check:
            if path_candidate == 'matlab' and sys.platform != 'win32': # For 'matlab' in PATH on Linux/macOS
                try: # Test if 'matlab' command in PATH is actually functional
                    test_process = subprocess.run([path_candidate, "-batch", "exit"], timeout=5, capture_output=True)
                    if test_process.returncode == 0:
                        if self.set_matlab_path(path_candidate): return True
                except (FileNotFoundError, subprocess.TimeoutExpired): continue
            elif os.path.exists(path_candidate): # For specific paths found
                if self.set_matlab_path(path_candidate): return True

        self.connectionStatusChanged.emit(False, "MATLAB auto-detection failed. Please set the path manually."); return False

    def _run_matlab_script(self, script_content, worker_signal, success_message_prefix):
        if not self.connected:
            worker_signal.emit(False, "MATLAB not connected or path invalid.", "")
            return

        try:
            # Create a temporary directory specific to this run
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
        worker.finished_signal.connect(thread.quit) # Ensure thread quits
        worker.finished_signal.connect(worker.deleteLater) # Schedule worker for deletion
        thread.finished.connect(thread.deleteLater) # Schedule thread for deletion

        self._active_threads.append(thread)
        # Remove thread from list once it's finished to prevent memory leak
        thread.finished.connect(lambda t=thread: self._active_threads.remove(t) if t in self._active_threads else None)

        thread.start()


    def generate_simulink_model(self, states, transitions, output_dir, model_name="BrainStateMachine"):
        if not self.connected:
            self.simulationFinished.emit(False, "MATLAB not connected.", "")
            return False

        slx_file_path = os.path.join(output_dir, f"{model_name}.slx").replace('\\', '/')
        model_name_orig = model_name # Keep original for messages

        script_lines = [
            f"% Auto-generated Simulink model script for '{model_name_orig}'",
            f"disp('Starting Simulink model generation for {model_name_orig}...');",
            f"modelNameVar = '{model_name_orig}';",
            f"outputModelPath = '{slx_file_path}';",
            "try",
            "    if bdIsLoaded(modelNameVar), close_system(modelNameVar, 0); end",
            "    if exist(outputModelPath, 'file'), delete(outputModelPath); end", # Ensure overwrite
            "    hModel = new_system(modelNameVar);",
            "    open_system(hModel);", # Open model silently
            "    disp('Adding Stateflow chart...');",
            "    machine = sfroot.find('-isa', 'Stateflow.Machine', 'Name', modelNameVar);",
            "    if isempty(machine)", # Defensive check
            "        error('Stateflow machine for model ''%s'' not found after new_system.', modelNameVar);",
            "    end",
            "    chartSFObj = Stateflow.Chart(machine);", # Use existing machine
            "    chartSFObj.Name = 'BrainStateMachineLogic';",
            "    chartBlockSimulinkPath = [modelNameVar, '/', 'BSM_Chart'];", # Name for chart block in Simulink
            "    add_block('stateflow/Chart', chartBlockSimulinkPath, 'Chart', chartSFObj.Path);", # Link existing Chart object
            "    set_param(chartBlockSimulinkPath, 'Position', [100 50 400 350]);",
            "    disp(['Stateflow chart block added at: ', chartBlockSimulinkPath]);",
            "    stateHandles = containers.Map('KeyType','char','ValueType','any');",
            "% --- State Creation ---"
        ]

        for i, state in enumerate(states):
            s_name_matlab = state['name'].replace("'", "''") # Escape single quotes for MATLAB strings
            s_id_matlab_safe = f"state_{i}_{state['name'].replace(' ', '_').replace('-', '_')}"
            s_id_matlab_safe = ''.join(filter(str.isalnum, s_id_matlab_safe)) # Ensure valid MATLAB var name
            if not s_id_matlab_safe or not s_id_matlab_safe[0].isalpha(): s_id_matlab_safe = 's_' + s_id_matlab_safe


            state_label_parts = []
            if state.get('entry_action'): state_label_parts.append(f"entry: {state['entry_action'].replace(chr(10), '; ')}")
            if state.get('during_action'): state_label_parts.append(f"during: {state['during_action'].replace(chr(10), '; ')}")
            if state.get('exit_action'): state_label_parts.append(f"exit: {state['exit_action'].replace(chr(10), '; ')}")
            s_label_string = "\\n".join(state_label_parts) if state_label_parts else ""
            s_label_string_matlab = s_label_string.replace("'", "''")

            sf_x = state['x'] / 2.5 + 20 # Rough scaling/offset for Stateflow coords
            sf_y = state['y'] / 2.5 + 20
            sf_w = max(60, state['width'] / 2.5)
            sf_h = max(40, state['height'] / 2.5)

            script_lines.extend([
                f"{s_id_matlab_safe} = Stateflow.State(chartSFObj);",
                f"{s_id_matlab_safe}.Name = '{s_name_matlab}';",
                f"{s_id_matlab_safe}.Position = [{sf_x}, {sf_y}, {sf_w}, {sf_h}];",
                f"if ~isempty('{s_label_string_matlab}'), {s_id_matlab_safe}.LabelString = sprintf('{s_label_string_matlab}'); end",
                f"stateHandles('{s_name_matlab}') = {s_id_matlab_safe};"
            ])
            if state.get('is_initial', False):
                # Default transition to initial state
                script_lines.extend([
                    f"defaultTransition_{i} = Stateflow.Transition(chartSFObj);", # Add to chart, not specific source
                    f"defaultTransition_{i}.Destination = {s_id_matlab_safe};",
                    # Crude positioning for default transition start point
                    f"srcPos = [{sf_x-20} {sf_y + sf_h/2}];",
                    f"dstPos = [{sf_x} {sf_y + sf_h/2}];",
                    # defaultTransition_{i}.SourceEndpoint = srcPos; % Does not always work robustly this way
                    # defaultTransition_{i}.Midpoint = [(srcPos(1)+dstPos(1))/2, (srcPos(2)+dstPos(2))/2 -10];
                    f"defaultTransition_{i}.SourceOClock = 9;", # From left
                    f"defaultTransition_{i}.DestinationOClock = 9;", # To left side of state
                ])

        script_lines.append("% --- Transition Creation ---")
        for i, trans in enumerate(transitions):
            src_name_matlab = trans['source'].replace("'", "''")
            dst_name_matlab = trans['target'].replace("'", "''")

            label_parts = []
            if trans.get('event'): label_parts.append(trans['event'])
            if trans.get('condition'): label_parts.append(f"[{trans['condition']}]")
            if trans.get('action'): label_parts.append(f"/{{{trans['action']}}}") # { } for actions in SF
            t_label = " ".join(label_parts).strip()
            t_label_matlab = t_label.replace("'", "''")

            script_lines.extend([
                f"if isKey(stateHandles, '{src_name_matlab}') && isKey(stateHandles, '{dst_name_matlab}')",
                f"    srcStateHandle = stateHandles('{src_name_matlab}');",
                f"    dstStateHandle = stateHandles('{dst_name_matlab}');",
                f"    t{i} = Stateflow.Transition(chartSFObj);",
                f"    t{i}.Source = srcStateHandle;",
                f"    t{i}.Destination = dstStateHandle;",
            ])
            if t_label_matlab:
                 script_lines.append(f"    t{i}.LabelString = '{t_label_matlab}';")
            # Add logic for transition Midpoint if complex routing is needed from GUI's control_offset_x/y
            # This is non-trivial to map perfectly from a single Bezier control point to SF transition waypoints
            script_lines.extend([
                "else",
                f"    disp(['Warning: Could not create SF transition from ''{src_name_matlab}'' to ''{dst_name_matlab}''. State missing.']);",
                "end"
            ])

        script_lines.extend([
            "% --- Finalize and Save ---",
            "    Simulink.BlockDiagram.arrangeSystem(chartBlockSimulinkPath, 'FullLayout', 'true', 'Animation', 'false');", # Try to auto-layout
            "    sf('FitToView', chartSFObj.Id);", # Fit chart view
            "    disp(['Attempting to save Simulink model to: ', outputModelPath]);",
            "    save_system(modelNameVar, outputModelPath, 'OverwriteIfChangedOnDisk', true);",
            "    close_system(modelNameVar, 0);", # Close silently
            "    disp(['Simulink model saved successfully to: ', outputModelPath]);",
            "    fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', outputModelPath);", # Signal success with path
            "catch e",
            "    disp('ERROR during Simulink model generation:');",
            "    disp(getReport(e, 'extended', 'hyperlinks', 'off'));",
            "    if bdIsLoaded(modelNameVar), close_system(modelNameVar, 0); end", # Close if it was loaded
            "    fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', strrep(getReport(e, 'basic'), '\\n', ' '));", # Signal failure with brief error
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
    prevPath = path; % Store current path
    addpath(modelDir); % Add model's directory to path
    disp(['Added to MATLAB path: ', modelDir]);

    load_system(modelPath); % Load the model
    disp(['Simulating model: ', modelName, ' for ', num2str(currentSimTime), ' seconds.']);
    simOut = sim(modelName, 'StopTime', num2str(currentSimTime)); % Run simulation

    disp('Simulink simulation completed successfully.');
    % MATLAB_SCRIPT_SUCCESS used by worker to parse output
    fprintf('MATLAB_SCRIPT_SUCCESS:Simulation of ''%s'' finished at t=%s. Results in MATLAB workspace (simOut).\\n', modelName, num2str(currentSimTime));
catch e
    disp('ERROR during Simulink simulation:');
    disp(getReport(e, 'extended', 'hyperlinks', 'off')); % Detailed error for log
    fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', strrep(getReport(e, 'basic'),'\\n',' ')); % Basic error for status
end
if bdIsLoaded(modelName), close_system(modelName, 0); end % Close model if loaded
path(prevPath); % Restore original path
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

        if not output_dir_base:
            output_dir_base = os.path.dirname(model_path) # Default to model's directory
        code_gen_root_matlab = output_dir_base.replace('\\', '/')

        script_content = f"""
disp('Starting Simulink code generation...');
modelPath = '{model_path_matlab}';
modelName = '{model_name}';
codeGenBaseDir = '{code_gen_root_matlab}'; % Where code generation folder (e.g., model_ert_rtw) will be created
modelDir = '{model_dir_matlab}';

try
    prevPath = path; addpath(modelDir); % Add model dir to path
    disp(['Added to MATLAB path: ', modelDir]);

    load_system(modelPath); % Load the model

    % License check for required toolboxes
    if ~(license('test', 'MATLAB_Coder') && license('test', 'Simulink_Coder') && license('test', 'Embedded_Coder'))
        error('Required licenses (MATLAB Coder, Simulink Coder, Embedded Coder) are not available.');
    end

    set_param(modelName,'SystemTargetFile','ert.tlc'); % Embedded Coder target
    set_param(modelName,'GenerateMakefile','on'); % Default: on, needed for ert.tlc build process

    cfg = getActiveConfigSet(modelName);
    % Language specific settings
    if strcmpi('{language}', 'C++')
        set_param(cfg, 'TargetLang', 'C++');
        set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'C++ class');
        set_param(cfg.getComponent('Code Generation'),'TargetLangStandard', 'C++11 (ISO)');
        disp('Configured for C++ (class interface, C++11).');
    else % Default to C
        set_param(cfg, 'TargetLang', 'C');
        set_param(cfg.getComponent('Code Generation').getComponent('Interface'), 'CodeInterfacePackaging', 'Reusable function');
        disp('Configured for C (reusable function).');
    end

    set_param(cfg, 'GenerateReport', 'on'); % Generate HTML report
    set_param(cfg, 'GenCodeOnly', 'on'); % Do not try to compile/build, just generate source
    set_param(cfg, 'RTWVerbose', 'on'); % Verbose build logs

    % Set code generation folder, it creates <model_name>_ert_rtw inside this
    if ~exist(codeGenBaseDir, 'dir'), mkdir(codeGenBaseDir); disp(['Created base codegen dir: ', codeGenBaseDir]); end
    disp(['Code generation output base set to: ', codeGenBaseDir]);

    % Actual code generation command
    rtwbuild(modelName, 'CodeGenFolder', codeGenBaseDir, 'GenCodeOnly', true);
    disp('Code generation command (rtwbuild) executed.');

    % Determine actual output directory path
    actualCodeDir = fullfile(codeGenBaseDir, [modelName '_ert_rtw']);
    if ~exist(actualCodeDir, 'dir') % Fallback if folder structure is different
        disp(['Warning: Standard codegen subdir ''', actualCodeDir, ''' not found. Output may be directly in base dir.']);
        actualCodeDir = codeGenBaseDir; % Could be just base dir if customization happens
    end

    disp(['Simulink code generation successful. Code and report expected in/under: ', actualCodeDir]);
    fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', actualCodeDir); % Signal success with actual code dir
catch e
    disp('ERROR during Simulink code generation:');
    disp(getReport(e, 'extended', 'hyperlinks', 'off'));
    fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', strrep(getReport(e, 'basic'),'\\n',' '));
end
if bdIsLoaded(modelName), close_system(modelName, 0); end % Close model
path(prevPath);  disp(['Restored MATLAB path. Removed: ', modelDir]);
"""
        self._run_matlab_script(script_content, self.codeGenerationFinished, "Code generation")
        return True


class MatlabCommandWorker(QObject):
    finished_signal = pyqtSignal(bool, str, str) # success, message, data_output

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
            # Prepare command to run the script
            # Using 'run' ensures MATLAB environment (workspace, path) is set up
            matlab_run_command = f"run('{self.script_file.replace('\\', '/')}')" # Use forward slashes for MATLAB
            cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", matlab_run_command]
            timeout_seconds = 600 # 10 minutes, adjust as needed for long operations

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True, # Decodes output as text
                encoding='utf-8', # Be explicit about encoding
                timeout=timeout_seconds,
                check=False, # We check returncode manually
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            stdout_str = process.stdout if process.stdout else ""
            stderr_str = process.stderr if process.stderr else ""

            # Check for our custom success/failure markers in stdout
            if "MATLAB_SCRIPT_FAILURE:" in stdout_str:
                success = False
                for line in stdout_str.splitlines():
                    if line.startswith("MATLAB_SCRIPT_FAILURE:"):
                        error_detail = line.split(":", 1)[1].strip()
                        message = f"{self.success_message_prefix} script reported failure: {error_detail}"
                        break
                if not message: # Fallback if marker parsing failed
                     message = f"{self.success_message_prefix} script indicated failure. Full stdout:\n{stdout_str[:500]}"
                if stderr_str:
                    message += f"\nStderr:\n{stderr_str[:300]}"


            elif "MATLAB_SCRIPT_FAILURE:" in stdout_str:
                success = False
                for line in stdout_str.splitlines():
                    if line.startswith("MATLAB_SCRIPT_FAILURE:"):
                        error_detail_json_str = line.split(":", 1)[1].strip()
                        try:
                            error_info = json.loads(error_detail_json_str) # Assuming MATLAB sends JSON
                # Now you have error_info.identifier, error_info.message, etc.
                            message = f"{self.success_message_prefix} script reported failure: {error_info.get('message','Unknown MATLAB error')}"
                            if error_info.get('identifier'):
                                message += f" (ID: {error_info['identifier']})"
                                
            





            elif process.returncode == 0: # MATLAB process exited cleanly
                if "MATLAB_SCRIPT_SUCCESS:" in stdout_str:
                    success = True
                    for line in stdout_str.splitlines():
                        if line.startswith("MATLAB_SCRIPT_SUCCESS:"):
                            output_data_for_signal = line.split(":", 1)[1].strip()
                            break
                    message = f"{self.success_message_prefix} completed successfully."
                    # For model gen/code gen, include path in msg. For sim, it's already in data.
                    if output_data_for_signal and self.success_message_prefix != "Simulation":
                         message += f" Data: {output_data_for_signal}"
                    elif output_data_for_signal and self.success_message_prefix == "Simulation":
                         message = output_data_for_signal # The message itself is the output data for sim
                else:
                    # Process exited 0, but no success marker found - unusual.
                    success = False
                    message = f"{self.success_message_prefix} script finished (MATLAB exit 0), but success marker not found."
                    message += f"\nStdout:\n{stdout_str[:500]}"
                if stderr_str: # Even on success, stderr might have warnings
                    message += f"\nStderr (possibly warnings):\n{stderr_str[:300]}"
            else: # MATLAB process itself had an error (non-zero exit code)
                success = False
                error_output = stderr_str or stdout_str # Prefer stderr if available
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
            # Cleanup temporary script and directory
            if os.path.exists(self.script_file):
                try:
                    os.remove(self.script_file)
                    script_dir = os.path.dirname(self.script_file)
                    # Safety: only remove the directory if it's one we created and it's empty
                    if script_dir.startswith(tempfile.gettempdir()) and "bsm_matlab_" in script_dir:
                        if not os.listdir(script_dir): # Check if empty
                            os.rmdir(script_dir)
                        else:
                            # This could happen if MATLAB creates other files there
                            print(f"Warning: Temp directory {script_dir} not empty, not removed.")
                except OSError as e:
                    print(f"Warning: Could not clean up temp script/dir '{self.script_file}': {e}")
            self.finished_signal.emit(success, message, output_data_for_signal) # Internal signal to quit thread