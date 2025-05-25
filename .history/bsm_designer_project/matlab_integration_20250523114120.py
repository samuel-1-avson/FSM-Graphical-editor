import sys
import os
import tempfile
import subprocess
import json # Added for parsing error details
from PyQt5.QtCore import QObject, pyqtSignal, QThread

class MatlabConnection(QObject):
    connectionStatusChanged = pyqtSignal(bool, str)
    simulationFinished = pyqtSignal(bool, str, str) # success, message, data_output (e.g. model_path, sim_results_path)
    codeGenerationFinished = pyqtSignal(bool, str, str) # success, message, output_dir

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
            self.matlab_path = "" # Clear invalid path
            if old_path: # If a path was previously set and is now found invalid
                self.connectionStatusChanged.emit(False, f"MATLAB path '{old_path}' is invalid or not executable.")
            else: # If path was cleared by user or was empty initially
                self.connectionStatusChanged.emit(False, "MATLAB path cleared.")
            return False

    def test_connection(self):
        if not self.matlab_path:
            self.connected = False
            self.connectionStatusChanged.emit(False, "MATLAB path not set. Cannot test connection.")
            return False
        # If path is set but connection status is false, try to re-validate/set path first.
        # This handles cases where set_matlab_path was called with a valid-looking path but test_connection wasn't immediately run.
        if not self.connected and self.matlab_path:
             if not self.set_matlab_path(self.matlab_path): # This will emit its own status
                 return False # If re-validation fails, abort test.

        try:
            cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", "disp('MATLAB_CONNECTION_TEST_SUCCESS');"]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

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
            self.connected = False; self.connectionStatusChanged.emit(False, f"MATLAB error during test: {(e.stderr or e.stdout or str(e)).splitlines()[0]}"); return False
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
        elif sys.platform == 'darwin': # macOS
            base_app_path = '/Applications'
            potential_matlab_apps = sorted([d for d in os.listdir(base_app_path) if d.startswith('MATLAB_R20') and d.endswith('.app')], reverse=True)
            for app_name in potential_matlab_apps:
                paths_to_check.append(os.path.join(base_app_path, app_name, 'bin', 'matlab'))
        else: # Linux/Other Unix
            common_base_paths = ['/usr/local/MATLAB', '/opt/MATLAB']
            for base_path in common_base_paths:
                if os.path.isdir(base_path):
                    versions = sorted([d for d in os.listdir(base_path) if d.startswith('R20') and len(d) > 4], reverse=True)
                    for v_year_letter in versions:
                         paths_to_check.append(os.path.join(base_path, v_year_letter, 'bin', 'matlab'))
            paths_to_check.append('matlab') # Check if 'matlab' is in PATH

        for path_candidate in paths_to_check:
            if path_candidate == 'matlab' and sys.platform != 'win32':
                try:
                    test_process = subprocess.run([path_candidate, "-batch", "exit"], timeout=5, capture_output=True, check=False)
                    if test_process.returncode == 0:
                        if self.set_matlab_path(path_candidate): return True # set_matlab_path will emit status
                except (FileNotFoundError, subprocess.TimeoutExpired): continue
            elif os.path.exists(path_candidate):
                if self.set_matlab_path(path_candidate): return True # set_matlab_path will emit status

        self.connectionStatusChanged.emit(False, "MATLAB auto-detection failed. Please set the path manually."); return False

    def _run_matlab_script(self, script_content, worker_signal, success_message_prefix, temp_dir_base=None):
        if not self.connected:
            worker_signal.emit(False, "MATLAB not connected or path invalid.", "")
            return

        # Use provided temp_dir_base or create a new one if not provided
        # This allows passing the temp_dir to MATLAB if it needs to write there (e.g. for sim results)
        current_temp_dir = temp_dir_base
        cleanup_temp_dir_on_finish = False
        if not current_temp_dir:
            try:
                current_temp_dir = tempfile.mkdtemp(prefix="bsm_matlab_")
                cleanup_temp_dir_on_finish = True # Only clean up if we created it here
            except Exception as e:
                 worker_signal.emit(False, f"Failed to create temporary directory: {e}", "")
                 return

        try:
            script_file = os.path.join(current_temp_dir, "matlab_script.m")
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(script_content)
        except Exception as e:
            worker_signal.emit(False, f"Failed to create temporary MATLAB script: {e}", "")
            if cleanup_temp_dir_on_finish and os.path.exists(current_temp_dir):
                try: os.rmdir(current_temp_dir)
                except OSError: pass # Ignore if not empty or other issue during cleanup
            return

        worker = MatlabCommandWorker(self.matlab_path, script_file, worker_signal, success_message_prefix,
                                     temp_dir_to_clean=current_temp_dir if cleanup_temp_dir_on_finish else None)
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
            self.simulationFinished.emit(False, "MATLAB not connected.", "") # Uses simulationFinished for model gen status
            return False

        slx_file_path = os.path.join(output_dir, f"{model_name}.slx").replace('\\', '/')
        model_name_orig = model_name

        # MATLAB Error handling part in script
        matlab_error_handling = """
catch e
    disp('ERROR during Simulink model generation:');
    disp(getReport(e, 'extended', 'hyperlinks', 'off'));
    err_struct = struct('message', e.message, 'identifier', e.identifier);
    if ~isempty(e.stack), err_struct.file = e.stack(1).file; err_struct.line = e.stack(1).line; else, err_struct.file=''; err_struct.line=''; end
    err_json = jsonencode(err_struct);
    if bdIsLoaded(modelNameVar), try close_system(modelNameVar, 0); catch, end; end
    fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', err_json);
end
"""
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
            s_id_matlab_safe = ''.join(c for c in s_id_matlab_safe if c.isalnum() or c == '_') # Keep underscores
            if not s_id_matlab_safe or not s_id_matlab_safe[0].isalpha(): s_id_matlab_safe = 's_' + s_id_matlab_safe

            state_label_parts = []
            if state.get('entry_action'): state_label_parts.append(f"entry: {state['entry_action'].replace(chr(10), '; ')}")
            if state.get('during_action'): state_label_parts.append(f"during: {state['during_action'].replace(chr(10), '; ')}")
            if state.get('exit_action'): state_label_parts.append(f"exit: {state['exit_action'].replace(chr(10), '; ')}")
            s_label_string = "\\n".join(state_label_parts) if state_label_parts else ""
            s_label_string_matlab = s_label_string.replace("'", "''")

            sf_x = state['x'] / 2.5 + 20
            sf_y = state['y'] / 2.5 + 20
            sf_w = max(60, state['width'] / 2.5)
            sf_h = max(40, state['height'] / 2.5)

            script_lines.extend([
                f"    {s_id_matlab_safe} = Stateflow.State(chartSFObj);",
                f"    {s_id_matlab_safe}.Name = '{s_name_matlab}';",
                f"    {s_id_matlab_safe}.Position = [{sf_x}, {sf_y}, {sf_w}, {sf_h}];",
                f"    if ~isempty('{s_label_string_matlab}'), {s_id_matlab_safe}.LabelString = sprintf('{s_label_string_matlab}'); end",
                f"    stateHandles('{s_name_matlab}') = {s_id_matlab_safe};"
            ])
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
            t_label = " ".join(label_parts).strip()
            t_label_matlab = t_label.replace("'", "''")

            script_lines.extend([
                f"    if isKey(stateHandles, '{src_name_matlab}') && isKey(stateHandles, '{dst_name_matlab}')",
                f"        srcStateHandle = stateHandles('{src_name_matlab}');",
                f"        dstStateHandle = stateHandles('{dst_name_matlab}');",
                f"        t{i} = Stateflow.Transition(chartSFObj);",
                f"        t{i}.Source = srcStateHandle;",
                f"        t{i}.Destination = dstStateHandle;",
            ])
            if t_label_matlab:
                 script_lines.append(f"        if ~isempty('{t_label_matlab}'), t{i}.LabelString = '{t_label_matlab}'; end")
            # Map control_offset_x (perpendicular) to Midpoint y-offset (simplified)
            # Map control_offset_y (tangential) to Midpoint x-offset along line (simplified)
            # This is a very rough approximation
            offset_x_gui = trans.get('control_offset_x', 0)
            offset_y_gui = trans.get('control_offset_y', 0)
            if offset_x_gui != 0 or offset_y_gui != 0:
                script_lines.extend([
                f"        srcPos = t{i}.SourceEndpoint;",
                f"        dstPos = t{i}.DestinationEndpoint;",
                f"        midX = (srcPos(1)+dstPos(1))/2;",
                f"        midY = (srcPos(2)+dstPos(2))/2;",
                f"        dx = dstPos(1)-srcPos(1); dy = dstPos(2)-srcPos(2); len = sqrt(dx^2+dy^2);",
                f"        if len==0, len=1; end;",
                f"        perpDx = -dy/len; perpDy = dx/len; % Normalized perpendicular vector",
                f"        tangDx = dx/len; tangDy = dy/len; % Normalized tangent vector",
                f"        controlPtX_sf = midX + perpDx * {offset_x_gui/3} + tangDx * {offset_y_gui/3};", # Scale factor /3 is arbitrary
                f"        controlPtY_sf = midY + perpDy * {offset_x_gui/3} + tangDy * {offset_y_gui/3};",
                f"        t{i}.Midpoint = [controlPtX_sf, controlPtY_sf];"
                ])

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
            "    try close_system(modelNameVar, 0); catch, end;",
            "    disp(['Simulink model saved successfully to: ', outputModelPath]);",
            "    fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', outputModelPath);",
        ])
        script_lines.append(matlab_error_handling) # Add the catch block
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
        model_dir_matlab = os.path.dirname(model_path_matlab).replace('\\','/')
        model_name = os.path.splitext(os.path.basename(model_path))[0]

        # Prepare a temporary directory for potential results
        sim_temp_dir = ""
        try:
            sim_temp_dir = tempfile.mkdtemp(prefix="bsm_sim_results_")
        except Exception as e:
            self.simulationFinished.emit(False, f"Failed to create temp dir for sim results: {e}", "")
            return False
        sim_temp_dir_matlab = sim_temp_dir.replace('\\', '/')


        matlab_error_handling = f"""
catch e
    disp('ERROR during Simulink simulation:');
    disp(getReport(e, 'extended', 'hyperlinks', 'off'));
    err_struct = struct('message', e.message, 'identifier', e.identifier);
    if ~isempty(e.stack), err_struct.file = e.stack(1).file; err_struct.line = e.stack(1).line; else, err_struct.file=''; err_struct.line=''; end
    err_json = jsonencode(err_struct);
    if bdIsLoaded(modelName), try close_system(modelName, 0); catch, end; end
    path(prevPath); % Restore path on error
    fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', err_json);
end
if bdIsLoaded(modelName), try close_system(modelName, 0); catch, end; end
path(prevPath);
disp(['Restored MATLAB path. Removed: ', modelDir]);
if exist('{sim_temp_dir_matlab}', 'dir') && isempty(dir('{sim_temp_dir_matlab}')) % If we created it and it's empty
    try rmdir('{sim_temp_dir_matlab}'); catch, disp('Could not remove temp sim dir.'); end
end
"""
        script_content = f"""
disp('Starting Simulink simulation...');
modelPath = '{model_path_matlab}';
modelName = '{model_name}';
modelDir = '{model_dir_matlab}';
simTempDir = '{sim_temp_dir_matlab}'; % Temp dir for results
currentSimTime = {sim_time};
prevPath = path; % Store current path
try
    addpath(modelDir);
    disp(['Added to MATLAB path: ', modelDir]);

    load_system(modelPath);
    disp(['Simulating model: ', modelName, ' for ', num2str(currentSimTime), ' seconds.']);
    
    % Example: Log all outports to simOut, save specific signals if they exist
    simOut = sim(modelName, 'StopTime', num2str(currentSimTime), 'SaveOutput','on','OutputSaveName','yout');
    
    result_message = sprintf('Simulation of ''%s'' finished at t=%s.', modelName, num2str(currentSimTime));
    output_data_path = ''; % Will be path to .mat file if data is saved

    % Check if simOut has any data and try to save it
    if exist('simOut', 'var') && ~isempty(simOut.who) 
        results_mat_file = fullfile(simTempDir, [modelName '_sim_results.mat']);
        save(results_mat_file, 'simOut'); % Save the whole simOut structure
        result_message = [result_message, sprintf(' Results saved to: %s', results_mat_file)];
        output_data_path = results_mat_file;
        fprintf('MATLAB_SCRIPT_SUCCESS_DATA_FILE:%s\\n', output_data_path); % Signal with data file path
    else
        result_message = [result_message, ' No specific output data logged to file.'];
        fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', result_message); % Signal without data file
    end
    disp(result_message);
{matlab_error_handling}
"""
        self._run_matlab_script(script_content, self.simulationFinished, "Simulation", temp_dir_base=sim_temp_dir) # Pass temp_dir
        return True

    def generate_code(self, model_path, language="C++", output_dir_base=None):
        if not self.connected:
            self.codeGenerationFinished.emit(False, "MATLAB not connected", "")
            return False

        model_path_matlab = model_path.replace('\\', '/')
        model_dir_matlab = os.path.dirname(model_path_matlab).replace('\\','/')
        model_name = os.path.splitext(os.path.basename(model_path))[0]

        if not output_dir_base:
            output_dir_base = os.path.dirname(model_path)
        code_gen_root_matlab = output_dir_base.replace('\\', '/')

        matlab_error_handling = f"""
catch e
    disp('ERROR during Simulink code generation:');
    disp(getReport(e, 'extended', 'hyperlinks', 'off'));
    err_struct = struct('message', e.message, 'identifier', e.identifier);
    if ~isempty(e.stack), err_struct.file = e.stack(1).file; err_struct.line = e.stack(1).line; else, err_struct.file=''; err_struct.line=''; end
    err_json = jsonencode(err_struct);
    if bdIsLoaded(modelName), try close_system(modelName, 0); catch, end; end
    path(prevPath); % Restore path on error
    fprintf('MATLAB_SCRIPT_FAILURE:%s\\n', err_json);
end
if bdIsLoaded(modelName), try close_system(modelName, 0); catch, end; end
path(prevPath);
disp(['Restored MATLAB path. Removed: ', modelDir]);
"""
        script_content = f"""
disp('Starting Simulink code generation...');
modelPath = '{model_path_matlab}';
modelName = '{model_name}';
codeGenBaseDir = '{code_gen_root_matlab}';
modelDir = '{model_dir_matlab}';
prevPath = path; % Store current path
try
    addpath(modelDir);
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

    actualCodeDir = fullfile(codeGenBaseDir, [modelName '_ert_rtw']); % Standard folder name
    if ~exist(actualCodeDir, 'dir')
        % Try common alternative if suffix changes, e.g. grt for Generic Real-Time Target
        altCodeDir_grt = fullfile(codeGenBaseDir, [modelName '_grt_rtw']);
        if exist(altCodeDir_grt, 'dir')
            actualCodeDir = altCodeDir_grt;
        else
             disp(['Warning: Standard codegen subdir ''', actualCodeDir, ''' not found. Checking base dir.']);
             actualCodeDir = codeGenBaseDir; % Fallback, could be directly in base
        end
    end
    
    % If actualCodeDir still doesn't exist but base does, means it wrote to base (less common for ert.tlc)
    if ~exist(actualCodeDir, 'dir') && exist(codeGenBaseDir, 'dir')
        actualCodeDir = codeGenBaseDir;
    end


    disp(['Simulink code generation successful. Code and report expected in/under: ', actualCodeDir]);
    fprintf('MATLAB_SCRIPT_SUCCESS:%s\\n', actualCodeDir);
{matlab_error_handling}
"""
        self._run_matlab_script(script_content, self.codeGenerationFinished, "Code generation")
        return True


class MatlabCommandWorker(QObject):
    finished_signal = pyqtSignal(bool, str, str) # success, message, data_output

    def __init__(self, matlab_path, script_file, original_signal, success_message_prefix, temp_dir_to_clean=None):
        super().__init__()
        self.matlab_path = matlab_path
        self.script_file = script_file # Path to .m script
        self.original_signal = original_signal # The signal to emit on completion (simulationFinished or codeGenerationFinished)
        self.success_message_prefix = success_message_prefix # e.g., "Model generation", "Simulation"
        self.temp_dir_to_clean = temp_dir_to_clean # Directory that might need cleaning if this worker "owns" it

    def run_command(self):
        output_data_for_signal = "" # e.g. path to SLX, path to .mat file, path to code gen dir
        success = False
        message = ""
        try:
            matlab_run_command = f"run('{self.script_file.replace('\\', '/')}')"
            cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", matlab_run_command]
            timeout_seconds = 900 # 15 minutes, increased for potentially long code gen or sim

            process = subprocess.run(
                cmd, capture_output=True, text=True, encoding='utf-8',
                timeout=timeout_seconds, check=False, # We check returncode manually
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            stdout_str = process.stdout if process.stdout else ""
            stderr_str = process.stderr if process.stderr else ""

            # Check for our custom success/failure markers in stdout
            if "MATLAB_SCRIPT_FAILURE:" in stdout_str:
                success = False
                for line in stdout_str.splitlines():
                    if line.startswith("MATLAB_SCRIPT_FAILURE:"):
                        error_detail_json_str = line.split(":", 1)[1].strip()
                        try:
                            error_info = json.loads(error_detail_json_str)
                            msg_main = error_info.get('message', 'Unknown MATLAB error')
                            msg_id = error_info.get('identifier', '')
                            msg_loc = ""
                            if error_info.get('file') and error_info.get('line'):
                                msg_loc = f" (File: {os.path.basename(error_info['file'])}, Line: {error_info['line']})"
                            message = f"{self.success_message_prefix} script reported failure: {msg_main}"
                            if msg_id: message += f" (ID: {msg_id})"
                            message += msg_loc
                        except json.JSONDecodeError:
                            message = f"{self.success_message_prefix} script reported failure (unparseable detail): {error_detail_json_str}"
                        break
                if not message: # Fallback if marker parsing failed
                     message = f"{self.success_message_prefix} script indicated failure. Full stdout:\n{stdout_str[:500]}"
                if stderr_str and stderr_str not in message: # Avoid duplicating if basic report included it
                    message += f"\nStderr (may contain more details):\n{stderr_str[:300]}"

            elif process.returncode == 0:
                if "MATLAB_SCRIPT_SUCCESS_DATA_FILE:" in stdout_str: # For operations that return a file path
                    success = True
                    for line in stdout_str.splitlines():
                        if line.startswith("MATLAB_SCRIPT_SUCCESS_DATA_FILE:"):
                            output_data_for_signal = line.split(":", 1)[1].strip() # This is the path to the data file
                            break
                    message = f"{self.success_message_prefix} completed. Results file: {output_data_for_signal}"
                elif "MATLAB_SCRIPT_SUCCESS:" in stdout_str: # General success, data might be in message or just status
                    success = True
                    for line in stdout_str.splitlines():
                        if line.startswith("MATLAB_SCRIPT_SUCCESS:"):
                            output_data_for_signal = line.split(":", 1)[1].strip() # Could be a path or just a status message
                            break
                    message = f"{self.success_message_prefix} completed successfully."
                    if output_data_for_signal and self.success_message_prefix not in output_data_for_signal: # Avoid redundant info
                        message += f" Details: {output_data_for_signal}"
                else:
                    success = False
                    message = f"{self.success_message_prefix} script finished (MATLAB exit 0), but success marker not found."
                    message += f"\nStdout:\n{stdout_str[:500]}"
                if stderr_str:
                    message += f"\nStderr (possibly warnings):\n{stderr_str[:300]}"
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
            # Cleanup temporary script and its directory IF this worker "owns" the temp_dir
            if self.temp_dir_to_clean and os.path.exists(self.temp_dir_to_clean):
                try:
                    if os.path.exists(self.script_file): # Script is inside temp_dir_to_clean
                        os.remove(self.script_file)
                    # Only remove the directory if it's empty (or becomes empty after script removal)
                    # Some operations (like sim results) might leave files we want to keep temporarily
                    # The calling function (e.g., run_simulation) should handle the result file.
                    # For _run_matlab_script, if cleanup_temp_dir_on_finish is true, it means
                    # it was a generic operation, and the dir was created just for the script.
                    if not os.listdir(self.temp_dir_to_clean):
                        os.rmdir(self.temp_dir_to_clean)
                    else:
                        # This can happen if MATLAB generates other outputs in that temp dir
                        print(f"Info: Temp directory {self.temp_dir_to_clean} not empty after script run, not removed by worker. (May contain results)")
                except OSError as e_clean:
                    print(f"Warning: Could not clean up temp script/dir '{self.temp_dir_to_clean}': {e_clean}")
            elif os.path.exists(self.script_file): # Script exists but not in a dir we own
                 try: os.remove(self.script_file)
                 except OSError as e_clean_file: print(f"Warning: Could not clean up temp script file '{self.script_file}': {e_clean_file}")

            self.finished_signal.emit(success, message, output_data_for_signal)