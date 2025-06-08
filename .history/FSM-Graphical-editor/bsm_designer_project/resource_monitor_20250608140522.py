

# bsm_designer_project/resource_monitor.py

import logging
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTime, pyqtSlot, QMetaObject, Qt

import psutil
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None

logger = logging.getLogger(__name__)

class ResourceMonitorWorker(QObject):
    resourceUpdate = pyqtSignal(float, float, float, str)
    finished_signal = pyqtSignal()
    MAX_NVML_REINIT_ATTEMPTS = 3
    NVML_REINIT_BACKOFF_SECONDS = 30
    WORKER_LOOP_CHECK_INTERVAL_MS = 100

    def __init__(self, interval_ms=2000, parent=None):
        super().__init__(parent)
        self.data_collection_interval_ms = interval_ms
        self._nvml_initialized = False
        self._gpu_handle = None
        self._gpu_name_cache = "N/A"
        self._nvml_reinit_attempts = 0
        self._last_nvml_reinit_attempt_time = 0 
        self._stop_requested = False

        if PYNVML_AVAILABLE and pynvml:
            self._attempt_nvml_init()
        elif not PYNVML_AVAILABLE:
            self._gpu_name_cache = "N/A (pynvml N/A)"
        logger.debug("ResourceMonitorWorker initialized.")

    def _attempt_nvml_init(self, from_worker_loop=False):
        if self._stop_requested or self._nvml_initialized:
            return

        current_time_sec = QTime.currentTime().msecsSinceStartOfDay() // 1000
        if self._nvml_reinit_attempts >= self.MAX_NVML_REINIT_ATTEMPTS and \
           (current_time_sec - self._last_nvml_reinit_attempt_time) < self.NVML_REINIT_BACKOFF_SECONDS and \
           from_worker_loop:
            return

        try:
            logger.debug("Attempting pynvml.nvmlInit().")
            pynvml.nvmlInit()
            self._nvml_initialized = True
            self._nvml_reinit_attempts = 0 
            if pynvml.nvmlDeviceGetCount() > 0:
                self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                gpu_name_raw = pynvml.nvmlDeviceGetName(self._gpu_handle)
                if isinstance(gpu_name_raw, bytes):
                    self._gpu_name_cache = gpu_name_raw.decode('utf-8')
                elif isinstance(gpu_name_raw, str):
                    self._gpu_name_cache = gpu_name_raw
                else:
                    self._gpu_name_cache = "NVIDIA GPU Name TypeErr"
                logger.info(f"NVML initialized. GPU: {self._gpu_name_cache}")
            else:
                self._gpu_name_cache = "NVIDIA GPU N/A (No devices)"
                logger.info("NVML initialized but no NVIDIA GPUs found.")
        except pynvml.NVMLError as e_nvml:
            self._nvml_reinit_attempts += 1
            self._last_nvml_reinit_attempt_time = current_time_sec
            if self._nvml_reinit_attempts <= self.MAX_NVML_REINIT_ATTEMPTS or not from_worker_loop:
                logger.warning(f"Could not initialize NVML (attempt {self._nvml_reinit_attempts}): {e_nvml}")
            else:
                logger.debug(f"NVML init attempt {self._nvml_reinit_attempts} failed (backoff active): {e_nvml.value if hasattr(e_nvml, 'value') else e_nvml}")
            self._nvml_initialized = False
            error_code_str = f" (Code: {e_nvml.value})" if hasattr(e_nvml, 'value') else ""
            self._gpu_name_cache = f"NVML Init Err{error_code_str}"
        except AttributeError as e_attr: # Catches potential attribute errors if pynvml is None but PYNVML_AVAILABLE was True
            logger.warning(f"NVML: Attribute error during init (pynvml likely None): {e_attr}")
            self._nvml_initialized = False
            self._gpu_name_cache = "NVML Attr Err"
        except Exception as e: 
            logger.warning(f"Unexpected error during NVML init: {e}", exc_info=True)
            self._nvml_initialized = False
            self._gpu_name_cache = "NVML Unexp. Err"

    @pyqtSlot()
    def start_monitoring(self):
        logger.info("ResourceMonitorWorker: start_monitoring called.")
        self._stop_requested = False
        self._monitor_resources()

    @pyqtSlot()
    def stop_monitoring(self):
        logger.info("ResourceMonitorWorker: stop_monitoring_slot called. Setting _stop_requested = True.")
        self._stop_requested = True

    def _shutdown_nvml(self):
        if self._nvml_initialized and PYNVML_AVAILABLE and pynvml:
            try:
                logger.debug("Attempting pynvml.nvmlShutdown().")
                pynvml.nvmlShutdown()
                logger.info("ResourceMonitorWorker: NVML shutdown successfully.")
            except Exception as e:
                logger.warning(f"Error shutting down NVML: {e}")
        self._nvml_initialized = False
        self._gpu_handle = None

    def _monitor_resources(self):
        logger.info("ResourceMonitorWorker: _monitor_resources loop STARTED.")
        last_data_emit_time_ms = 0
        worker_thread = self.thread()

        if not worker_thread:
            logger.error("ResourceMonitorWorker: CRITICAL - Worker is not associated with a QThread.")
            self.finished_signal.emit() 
            return

        loop_count = 0
        while not worker_thread.isInterruptionRequested() and not self._stop_requested:
            loop_count += 1
            if loop_count % 50 == 0 : # Log less frequently
                logger.debug(f"ResourceMonitorWorker: Loop iteration {loop_count}, InterruptionRequested: {worker_thread.isInterruptionRequested()}, StopRequested: {self._stop_requested}")

            current_loop_time_ms = QTime.currentTime().msecsSinceStartOfDay()

            if (current_loop_time_ms - last_data_emit_time_ms) >= self.data_collection_interval_ms or last_data_emit_time_ms == 0:
                if worker_thread.isInterruptionRequested() or self._stop_requested:
                    logger.debug("ResourceMonitorWorker: Interruption/stop detected before emitting resourceUpdate.")
                    break 
                try:
                    cpu_usage = psutil.cpu_percent(interval=None)
                    ram_percent = psutil.virtual_memory().percent
                    gpu_util = -1.0 
                    gpu_name_to_emit = self._gpu_name_cache

                    if self._nvml_initialized and self._gpu_handle and PYNVML_AVAILABLE and pynvml:
                        try:
                            gpu_info = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                            gpu_util = float(gpu_info.gpu)
                        except pynvml.NVMLError as e:
                            logger.warning(f"NVML error getting GPU util: {e}. Re-attempting init if needed.")
                            gpu_util = -2.0 
                            gpu_name_to_emit = f"NVML Read Err (Code: {e.value})" if hasattr(e, 'value') else "NVML Read Err"
                            self._nvml_initialized = False 
                            self._attempt_nvml_init(from_worker_loop=True) # Attempt re-init
                        except Exception as e_gen: 
                            logger.error(f"Unexpected error getting GPU util: {e_gen}")
                            gpu_util = -3.0 
                            gpu_name_to_emit = "GPU Mon. Err"
                    elif PYNVML_AVAILABLE and not self._nvml_initialized and pynvml: # If pynvml exists but not initialized
                        # FIX: Add check before attempting re-init in loop
                        current_time_sec_for_check = QTime.currentTime().msecsSinceStartOfDay() // 1000
                        can_attempt_reinit_in_loop = True
                        if self._nvml_reinit_attempts >= self.MAX_NVML_REINIT_ATTEMPTS and \
                           (current_time_sec_for_check - self._last_nvml_reinit_attempt_time) < self.NVML_REINIT_BACKOFF_SECONDS:
                            can_attempt_reinit_in_loop = False
                        
                        if can_attempt_reinit_in_loop:
                            self._attempt_nvml_init(from_worker_loop=True)


                    if not (worker_thread.isInterruptionRequested() or self._stop_requested):
                        self.resourceUpdate.emit(cpu_usage, ram_percent, gpu_util, gpu_name_to_emit)
                    last_data_emit_time_ms = current_loop_time_ms

                except Exception as e:
                    logger.error(f"ResourceMonitorWorker: Error in data collection: {e}", exc_info=False) # Keep exc_info concise
                    if not (worker_thread.isInterruptionRequested() or self._stop_requested):
                         self.resourceUpdate.emit(-1.0, -1.0, -3.0, "Data Error") # Emit error indication

            # Check for interruption/stop more frequently within the data collection interval
            inner_loop_checks = int(self.data_collection_interval_ms / self.WORKER_LOOP_CHECK_INTERVAL_MS)
            if inner_loop_checks <= 0: inner_loop_checks = 1 # Ensure at least one sleep

            for _i in range(inner_loop_checks):
                if worker_thread.isInterruptionRequested() or self._stop_requested:
                    break # Break inner loop
                QThread.msleep(self.WORKER_LOOP_CHECK_INTERVAL_MS)
            
            if worker_thread.isInterruptionRequested() or self._stop_requested: # Check again before continuing outer loop
                logger.debug("ResourceMonitorWorker: Exiting main while loop due to interruption/stop request.")
                break

        logger.info(f"ResourceMonitorWorker: _monitor_resources loop EXITED (Interruption: {worker_thread.isInterruptionRequested()}, StopFlag: {self._stop_requested}). Emitting finished_signal.")
        self.finished_signal.emit()


class ResourceMonitorManager(QObject):
    def __init__(self, main_window_ref, settings_manager, parent=None): # Added settings_manager
        super().__init__(parent)
        self.mw = main_window_ref
        self.settings_manager = settings_manager # Store it
        self.worker: ResourceMonitorWorker | None = None
        self.thread: QThread | None = None
        # setup_and_start_monitor will be called by MainWindow after checking settings

    def setup_and_start_monitor(self):
        if not self.settings_manager.get("resource_monitor_enabled"):
            logger.info("ResourceMonitorManager: Monitor is disabled by settings. Not starting.")
            return

        if self.thread or self.worker:
            logger.warning("ResourceMonitorManager: Monitor already set up.")
            return

        interval = self.settings_manager.get("resource_monitor_interval_ms")
        logger.info(f"ResourceMonitorManager: Setting up monitor with interval: {interval} ms.")

        self.thread = QThread(self.mw) 
        self.thread.setObjectName("ResourceMonitorQThread_Managed")
        self.worker = ResourceMonitorWorker(interval_ms=interval) # Pass interval from settings
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.start_monitoring)
        self.worker.finished_signal.connect(self.thread.quit)
        self.worker.finished_signal.connect(self._handle_worker_thread_finished) 

        self.thread.start()
        logger.info("ResourceMonitorManager: Monitor thread initialized and started.")
    
    @pyqtSlot()
    def _handle_worker_thread_finished(self):
        logger.debug("ResourceMonitorManager: Worker's finished_signal received, thread should be quitting.")
        # Further cleanup of worker/thread if needed after thread.quit() is done,
        # often handled by deleteLater.

    def stop_monitoring_system(self):
        logger.info("ResourceMonitorManager: stop_monitoring_system called.")
        worker_for_shutdown = None
        if self.thread and self.thread.isRunning():
            logger.info("ResourceMonitorManager: Attempting to stop resource monitor worker and thread...")
            
            worker_for_shutdown = self.worker 

            self.thread.requestInterruption() 
            logger.debug("ResourceMonitorManager: Interruption requested on resource monitor thread.")

            if self.worker:
                # Use invokeMethod for thread-safe call to worker's stop slot
                if QThread.currentThread() != self.thread:
                    QMetaObject.invokeMethod(self.worker, "stop_monitoring", Qt.QueuedConnection)
                else: # If called from the worker's own thread (less likely for stop_monitoring_system)
                    self.worker.stop_monitoring()
                logger.debug("ResourceMonitorManager: stop_monitoring slot invoked/queued on resource worker.")

            # The worker's finished_signal is connected to thread.quit(), so we wait for the thread.
            logger.debug("ResourceMonitorManager: Waiting for resource monitor thread to finish...")
            if not self.thread.wait(3500): # Increased timeout slightly
                logger.warning("ResourceMonitorManager: Resource monitor thread did not finish gracefully within timeout. Terminating.")
                self.thread.terminate()
                if not self.thread.wait(1000):
                     logger.error("ResourceMonitorManager: Resource monitor thread FAILED TO TERMINATE forcefully.")
                else:
                    logger.info("ResourceMonitorManager: Resource monitor thread terminated forcefully.")
            else:
                logger.info("ResourceMonitorManager: Resource monitor thread stopped gracefully.")
        
        elif self.worker: # Thread wasn't running, but worker exists
            worker_for_shutdown = self.worker
            logger.info("ResourceMonitorManager: Resource monitor thread was not running, but worker instance exists.")

        if worker_for_shutdown:
            logger.info("ResourceMonitorManager: Shutting down NVML via worker reference.")
            try:
                # Directly call _shutdown_nvml if worker is guaranteed to be in this thread or not active
                # If worker might be on another thread and still somehow active without self.thread running,
                # this direct call could be problematic, but usually, it's safe here.
                worker_for_shutdown._shutdown_nvml()
            except Exception as e:
                logger.error(f"Error during explicit NVML shutdown via manager: {e}")

        # Schedule for deletion
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self.thread:
            self.thread.deleteLater()
            self.thread = None
        logger.debug("ResourceMonitorManager: Worker and thread references cleared and scheduled for deletion.")
        pass
