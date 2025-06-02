import sys
import os
import tempfile
import subprocess
import logging # Added for logging within this module
from PyQt5.QtCore import QObject, pyqtSignal, QThread

logger = logging.getLogger(__name__) # Logger specific to this module

class MatlabCommandWorker(QObject):
    finished_signal = pyqtSignal(bool, str, str) # success, message, data_output

    def __init__(self, matlab_path, script_file, original_signal, success_message_prefix, model_name_for_context=None):
        super().__init__()
        self.matlab_path = matlab_path
        self.script_file = script_file
        self.original_signal = original_signal
        self.success_message_prefix = success_message_prefix
        self.model_name_for_context = model_name_for_context # Store for use in error messages

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
                    if line.strip().startswith("MATLAB_SCRIPT_FAILURE:"):
                        extracted_error_detail = line.split(":", 1)[1].strip()
                        break
                message = f"{self.success_message_prefix} script reported failure: {extracted_error_detail}"

                # Attempt to add more context from stdout/stderr
                if stderr_str and extracted_error_detail not in stderr_str:
                    message += f"\nMATLAB Stderr: {stderr_str[:500]}"

                # Try to get more context from stdout if error detail is brief or generic
                if "Details not found" in extracted_error_detail or len(extracted_error_detail) < 50:
                    stdout_context_lines = [line for line in stdout_str.splitlines()
                                            if "ERROR" in line.upper() or "WARNING" in line.upper() or
                                               (self.model_name_for_context and self.model_name_for_context in line)]
                    stdout_context_for_failure = "\n".join(stdout_context_lines[:10]) # Limit lines
                    if stdout_context_for_failure and extracted_error_detail not in stdout_context_for_failure:
                        # Avoid duplicating the exact error if it was already in stdout_context
                        message += f"\nRelevant MATLAB Stdout: {stdout_context_for_failure[:500]}" # Limit length

            elif process.returncode != 0:
                success = False
                error_output_detail = stderr_str or stdout_str
                matlab_error_lines = [line for line in error_output_detail.splitlines() if line.strip().startswith("Error using") or line.strip().startswith("Error:")]
                if matlab_error_lines:
                    specific_error = " ".join(matlab_error_lines[:2])
                    message = f"{self.success_message_prefix} process failed. MATLAB Exit Code {process.returncode}. Error: {specific_error[:500]}"
                    if len(error_output_detail) > 500 : message += "\n(More details in application log if logging is comprehensive)"
                else: # Generic failure if specific error lines not found
                    message = f"{self.success_message_prefix} process failed. MATLAB Exit Code {process.returncode}:\n{error_output_detail[:1000]}"
            else: # Should be caught by SUCCESS or FAILURE markers, but as a fallback
                success = True # Assuming if no error markers and exit 0, it's success
                message = f"{self.success_message_prefix} completed (no explicit success/failure marker, but exit code 0)."
                output_data_for_signal = stdout_str # Give all stdout as data in this ambiguous case

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