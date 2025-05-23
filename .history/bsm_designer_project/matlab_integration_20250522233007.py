# (Keep imports and constants as defined before)

# ... (MatlabConnection class as above) ...

class MatlabCommandWorker(QObject):
    finished_signal = pyqtSignal(bool, str, str) 

    def __init__(self, matlab_path, script_file, temp_dir, original_signal, success_message_prefix):
        super().__init__()
        self.matlab_path = matlab_path
        self.script_file = script_file
        self.temp_dir = temp_dir 
        self.original_signal = original_signal
        self.success_message_prefix = success_message_prefix

    def run_command(self):
        output_data_for_signal = ""
        success = False
        message = ""
        
        # MATLAB command construction: cd to script's directory and then run the script.
        # This makes relative path references within the script (if any) work as expected.
        script_dir_for_matlab = os.path.dirname(self.script_file).replace('\\', '/')
        script_name_for_matlab = os.path.basename(self.script_file)
        # Using fullfile for path concatenation in MATLAB command for robustness
        matlab_run_command = f"cd('{script_dir_for_matlab}'); run(fullfile('{script_dir_for_matlab}', '{script_name_for_matlab}'));"

        try:
            cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", matlab_run_command]
            timeout_seconds = 600 

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True, 
                encoding='utf-8', 
                timeout=timeout_seconds,
                check=False, # We check returncode manually
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            stdout_str = process.stdout or ""
            stderr_str = process.stderr or ""
            
            if MATLAB_SCRIPT_FAILURE_MARKER in stdout_str:
                success = False
                for line in stdout_str.splitlines(): # Parse specific error from script
                    if line.startswith(MATLAB_SCRIPT_FAILURE_MARKER):
                        error_detail = line.split(":", 1)[1].strip()
                        message = f"{self.success_message_prefix} script reported failure: {error_detail}"
                        break
                if not message: # Fallback if marker was present but line parsing failed
                     message = f"{self.success_message_prefix} script indicated failure. Full stdout:\n{stdout_str[:500]}"
                if stderr_str:
                    message += f"\nStderr from MATLAB:\n{stderr_str[:300]}"

            elif process.returncode == 0: 
                if MATLAB_SCRIPT_SUCCESS_MARKER in stdout_str:
                    success = True
                    for line in stdout_str.splitlines(): # Parse specific data from script
                        if line.startswith(MATLAB_SCRIPT_SUCCESS_MARKER):
                            output_data_for_signal = line.split(":", 1)[1].strip()
                            break
                    message = f"{self.success_message_prefix} completed successfully."
                    # Tailor message based on context and if data is present
                    if output_data_for_signal and self.success_message_prefix != "Simulation":
                         message += f" Data: {output_data_for_signal}"
                    elif output_data_for_signal and self.success_message_prefix == "Simulation":
                         message = output_data_for_signal # Simulation success message is the data
                else:
                    success = False 
                    message = f"{self.success_message_prefix} script finished (MATLAB exit 0), but success marker not found."
                    message += f"\nStdout:\n{stdout_str[:500]}"
                if stderr_str: 
                    message += f"\nStderr (possibly warnings from MATLAB):\n{stderr_str[:300]}"
            else: 
                success = False
                error_output = stderr_str or stdout_str 
                message = f"{self.success_message_prefix} process failed. MATLAB Exit Code {process.returncode}:\n{error_output[:1000]}"

            self.original_signal.emit(success, message, output_data_for_signal if success else "")

        except subprocess.TimeoutExpired:
            message = f"{self.success_message_prefix} process timed out after {timeout_seconds/60:.1f} minutes."
            self.original_signal.emit(False, message, "")
            success = False 
        except FileNotFoundError:
            message = f"MATLAB executable not found: {self.matlab_path}"
            self.original_signal.emit(False, message, "")
            success = False
        except Exception as e:
            message = f"Unexpected error in {self.success_message_prefix} worker: {type(e).__name__}: {str(e)}"
            self.original_signal.emit(False, message, "")
            success = False
        finally:
            # Cleanup temporary script file
            if self.script_file and os.path.exists(self.script_file):
                try:
                    os.remove(self.script_file)
                except OSError as e:
                    print(f"Warning: Could not remove temp script '{self.script_file}': {e}")
            
            # Cleanup temporary directory if it's empty
            if self.temp_dir and os.path.exists(self.temp_dir):
                try:
                    if not os.listdir(self.temp_dir): 
                        os.rmdir(self.temp_dir)
                    else:
                        print(f"Warning: Temp directory {self.temp_dir} not empty after script execution, not removed by worker. Contents: {os.listdir(self.temp_dir)}")
                except OSError as e:
                    print(f"Warning: Could not remove temp directory '{self.temp_dir}': {e}")
            
            self.finished_signal.emit(success, message, output_data_for_signal if success else "")