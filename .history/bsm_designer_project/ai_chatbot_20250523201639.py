from PyQt5.QtCore import (
    QObject, pyqtSignal, QThread, QTimer, QMutex, QMutexLocker,
    QWaitCondition, Qt, QMetaObject, pyqtSlot, Q_ARG
)
from PyQt5.QtWidgets import QApplication
import openai
import json
import time
import logging
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading # Not strictly needed for QThread approach but often seen with workers
from functools import wraps

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatbotState(Enum):
    """Chatbot operational states"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    ERROR = "error"
    STOPPING = "stopping"
    STOPPED = "stopped"

@dataclass
class ChatMessage:
    """Structured chat message"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ChatbotConfig:
    """Configuration for chatbot behavior"""
    model_name: str = "gpt-3.5-turbo"
    max_history_length: int = 20
    timeout_seconds: int = 30 # Note: This specific timeout isn't directly used by openai client's create method in current code
    max_retries: int = 3
    retry_delay: float = 1.0
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    generation_keywords: List[str] = field(default_factory=lambda: [
        "generate fsm", "create fsm", "generate an fsm model",
        "generate state machine", "create state machine", "design state machine",
        "model fsm", "model state machine", "draw fsm", "draw state machine",
        "design it", "/generate_fsm"
    ])
    # Removed api_key from here as it's not a config of behavior but a credential

def thread_safe(func):
    """Decorator to ensure thread-safe execution using QMutex"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if hasattr(self, '_mutex') and isinstance(self._mutex, QMutex):
            with QMutexLocker(self._mutex):
                return func(self, *args, **kwargs)
        # Fallback or warning if _mutex is not available or not a QMutex
        # logger.warning(f"Method {func.__name__} called without QMutex context.")
        return func(self, *args, **kwargs)
    return wrapper

class ChatbotWorker(QObject):
    responseReady = pyqtSignal(str, dict)
    errorOccurred = pyqtSignal(str, str)
    statusUpdate = pyqtSignal(str, str)
    progressUpdate = pyqtSignal(int)
    configChanged = pyqtSignal(dict) # Emitted when config is updated on the worker

    def __init__(self, config: ChatbotConfig, parent=None):
        super().__init__(parent)
        self.config = config # Worker receives a copy of the config
        self.client: Optional[openai.OpenAI] = None
        self.conversation_history: List[ChatMessage] = []
        self.current_diagram_context: Optional[Dict] = None # JSON serializable dict
        self._state = ChatbotState.IDLE # Use underscore for internal state var
        self._mutex = QMutex()
        self._stop_requested = False
        self._current_request_id: Optional[str] = None
        logger.info(f"ChatbotWorker initialized with model: {self.config.model_name}")

    @property
    @thread_safe
    def state(self) -> ChatbotState:
        return self._state

    @thread_safe # Ensure thread-safe modification
    def _set_state(self, new_state: ChatbotState, details: str = ""):
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            detail_msg = details if details else f"State changed from {old_state.value}"
            self.statusUpdate.emit(new_state.value, detail_msg)
            logger.info(f"Worker state: {old_state.value} -> {new_state.value} ({detail_msg})")

    @pyqtSlot(str)
    def set_api_key(self, api_key: str):
        """Sets the OpenAI API key and initializes the OpenAI client."""
        logger.info("ChatbotWorker: set_api_key called.")
        if not api_key or not api_key.strip():
            self._set_state(ChatbotState.ERROR, "API key cannot be empty.")
            self.errorOccurred.emit("API key cannot be empty", "API_KEY_EMPTY")
            self.client = None
            return

        try:
            self._set_state(ChatbotState.INITIALIZING, "Setting API key...")
            self.client = openai.OpenAI(api_key=api_key.strip())
            # Perform a lightweight test call to validate the key
            self._test_api_connection()
            self._set_state(ChatbotState.READY, "API key validated and client initialized.")
        except openai.AuthenticationError as e:
            logger.error(f"AuthenticationError during API key set: {e}")
            self._set_state(ChatbotState.ERROR, "Invalid API key.")
            self.errorOccurred.emit(f"Invalid API key: {e}", "AUTH_ERROR")
            self.client = None
        except Exception as e:
            logger.error(f"Error setting API key or initializing client: {e}")
            self._set_state(ChatbotState.ERROR, f"Client initialization failed: {e}")
            self.errorOccurred.emit(f"Client initialization failed: {e}", "INIT_ERROR")
            self.client = None
            
    def _test_api_connection(self):
        """ Test API connection with a minimal request. Raises exception on failure. """
        if not self.client:
            raise FSMError("OpenAI client not initialized for API test.") # Or a more specific internal error
        try:
            logger.info("Testing API connection...")
            # Using a very small model and prompt for testing
            self.client.completions.create(
                model="text-davinci-002",  # Or any other small, fast model
                prompt="Test",
                max_tokens=1
            )
            logger.info("API connection test successful.")
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            raise # Re-raise the exception to be caught by the caller

    @pyqtSlot(str) # Expects a JSON string for config
    def update_config(self, config_json: str):
        logger.info(f"ChatbotWorker: update_config called with JSON: {config_json[:100]}...")
        try:
            config_dict = json.loads(config_json)
            updated_any = False
            for key, value in config_dict.items():
                if hasattr(self.config, key):
                    if getattr(self.config, key) != value:
                        setattr(self.config, key, value)
                        updated_any = True
                        logger.info(f"Worker config '{key}' updated to: {value}")
            if updated_any:
                self.configChanged.emit(config_dict) # Emit the updated parts
                # If model_name changed and client is initialized, we might need to re-test or re-init client if model capabilities differ significantly.
                # For now, assume client handles model changes per request.
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config JSON: {e}")
            self.errorOccurred.emit(f"Invalid configuration format: {e}", "CONFIG_JSON_ERROR")
        except Exception as e:
            logger.error(f"Error updating worker configuration: {e}")
            self.errorOccurred.emit(f"Configuration update failed: {e}", "CONFIG_ERROR")

    @pyqtSlot(str) # Expects JSON string or empty string
    def set_diagram_context(self, diagram_json: str):
        logger.info(f"ChatbotWorker: set_diagram_context called.")
        if not diagram_json:
            self.current_diagram_context = None
            logger.info("Diagram context cleared.")
            return
        try:
            self.current_diagram_context = json.loads(diagram_json)
            logger.info("Diagram context updated.")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid diagram JSON for context: {e}")
            self.current_diagram_context = {"error": "Invalid diagram data received."}
            # Optionally emit an error or status update
            # self.errorOccurred.emit(f"Invalid diagram context: {e}", "DIAGRAM_CONTEXT_ERROR")


    @pyqtSlot(str, str)
    def process_message(self, user_message: str, request_id: str = None):
        logger.info(f"ChatbotWorker: process_message '{user_message[:30]}...' (Req ID: {request_id})")
        if self.state not in [ChatbotState.READY, ChatbotState.IDLE]: # IDLE might be okay if client is set
            logger.warning(f"Worker not ready to process message (state: {self.state.value}).")
            self.errorOccurred.emit("Worker not ready", "WORKER_NOT_READY")
            return

        if not self.client:
            logger.error("OpenAI client not initialized. Cannot process message.")
            self.errorOccurred.emit("OpenAI client not initialized.", "NO_CLIENT")
            return

        self._current_request_id = request_id or str(int(time.time() * 1000))
        self._set_state(ChatbotState.PROCESSING, f"Processing message ID: {self._current_request_id}")
        self._stop_requested = False # Reset stop flag for new request

        try:
            self._process_message_internal(user_message)
        except InterruptedError:
            logger.info(f"Processing cancelled for request ID: {self._current_request_id}")
            self._set_state(ChatbotState.READY, "Processing cancelled.") # Or IDLE if preferred
            # self.errorOccurred.emit("Processing cancelled by user.", "USER_CANCELLED") # Optional
        except Exception as e:
            logger.error(f"Error during message processing (Req ID: {self._current_request_id}): {e}", exc_info=True)
            self.errorOccurred.emit(f"Message processing failed: {e}", "PROCESSING_ERROR")
            self._set_state(ChatbotState.ERROR, f"Error processing: {e}") # Go to error state
        finally:
            if self.state == ChatbotState.PROCESSING: # If not already set to ERROR or another state by the process
                 self._set_state(ChatbotState.READY, "Finished processing.")
            self._current_request_id = None


    def _process_message_internal(self, user_message: str):
        is_generation_request = any(keyword in user_message.lower() for keyword in self.config.generation_keywords)
        
        system_prompt_content = "You are a helpful AI assistant. "
        if is_generation_request:
            system_prompt_content += (
                "When asked to generate an FSM, create a state machine diagram. "
                "Respond with ONLY a valid JSON object that conforms to the specified FSM schema. "
                "The JSON should have 'description' (string), 'states' (array of state objects), "
                "and 'transitions' (array of transition objects). "
                "Each state object requires 'name' (string, unique), and can have 'is_initial' (bool), 'is_final' (bool), 'entry_action', 'during_action', 'exit_action' (strings), and 'properties' (object, e.g., {'color': '#RRGGBB'}). "
                "Each transition object requires 'source' (string, existing state name), 'target' (string, existing state name), and can have 'event', 'condition', 'action' (strings), and 'properties' (object). "
                "Optionally, include a 'comments' array with objects having 'text', 'x', 'y'. "
                "Do not include any explanatory text, markdown, or anything outside the single JSON object in your response."
            )
        if self.current_diagram_context:
            context_str = json.dumps(self.current_diagram_context, indent=2)[:1000] # Limit context size
            system_prompt_content += f"\nConsider the current diagram context: {context_str}"

        messages = [{"role": "system", "content": system_prompt_content}]
        
        # Add limited conversation history
        history_to_include = self.conversation_history[-(self.config.max_history_length * 2):] # user+assistant pairs
        for msg in history_to_include:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_message})

        response_content = self._make_api_request_with_retries(messages, is_generation_request)

        self._update_conversation_history(user_message, response_content)
        
        metadata = {
            "request_id": self._current_request_id,
            "is_generation": is_generation_request,
            "model": self.config.model_name,
            "timestamp": time.time()
        }
        self.responseReady.emit(response_content, metadata)

    def _make_api_request_with_retries(self, messages: List[Dict], is_generation: bool) -> str:
        last_exception = None
        for attempt in range(self.config.max_retries):
            if self._stop_requested:
                raise InterruptedError("Request processing was cancelled.")
            
            self.progressUpdate.emit(int((attempt + 1) * 100 / self.config.max_retries))
            logger.info(f"Attempt {attempt + 1}/{self.config.max_retries} for API request.")
            
            try:
                request_params = {
                    "model": self.config.model_name,
                    "messages": messages,
                    "temperature": self.config.temperature,
                }
                if self.config.max_tokens:
                    request_params["max_tokens"] = self.config.max_tokens
                if is_generation: # Request JSON object output if it's a generation task
                    request_params["response_format"] = {"type": "json_object"}

                response = self.client.chat.completions.create(**request_params)
                content = response.choices[0].message.content
                self.progressUpdate.emit(100)
                return content.strip() if content else ""

            except openai.RateLimitError as e:
                last_exception = e
                logger.warning(f"Rate limit error: {e}. Retrying in {self.config.retry_delay * (2**attempt)}s...")
                if attempt < self.config.max_retries - 1: time.sleep(self.config.retry_delay * (2**attempt))
                else: raise
            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                last_exception = e
                logger.warning(f"API connection/timeout error: {e}. Retrying in {self.config.retry_delay}s...")
                if attempt < self.config.max_retries - 1: time.sleep(self.config.retry_delay)
                else: raise
            except openai.AuthenticationError as e: # Non-retryable
                logger.error(f"Authentication error: {e}")
                self.errorOccurred.emit("Authentication failed. Check API key.", "AUTH_ERROR_WORKER")
                self._set_state(ChatbotState.ERROR, "Authentication Failed")
                raise # Propagate to stop further processing
            except openai.BadRequestError as e: # e.g. model not found, invalid request
                 logger.error(f"Bad request error: {e}")
                 self.errorOccurred.emit(f"Invalid request to OpenAI: {e}", "BAD_REQUEST_ERROR")
                 self._set_state(ChatbotState.ERROR, f"Bad Request: {e}")
                 raise
            except Exception as e: # Catch other OpenAI errors or unexpected issues
                last_exception = e
                logger.error(f"Unexpected API error (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1: time.sleep(self.config.retry_delay)
                else: raise
        
        # Should not be reached if an exception is always raised on final attempt
        if last_exception:
            raise last_exception # Re-raise the last captured exception
        else: # Fallback, though logic implies an exception should always exist here
            raise FSMError(f"Failed to get response after {self.config.max_retries} retries.")


    def _update_conversation_history(self, user_message: str, ai_response: str):
        self.conversation_history.append(ChatMessage(role="user", content=user_message))
        self.conversation_history.append(ChatMessage(role="assistant", content=ai_response))
        # Trim history if it exceeds max_history_length (considering pairs)
        if len(self.conversation_history) > self.config.max_history_length * 2 :
            excess_items = len(self.conversation_history) - (self.config.max_history_length * 2)
            self.conversation_history = self.conversation_history[excess_items:]
            logger.info(f"Trimmed {excess_items // 2} pairs from conversation history.")

    @pyqtSlot()
    @thread_safe
    def clear_history(self):
        count = len(self.conversation_history)
        self.conversation_history.clear()
        logger.info(f"Conversation history cleared ({count} messages).")
        self.statusUpdate.emit("history_cleared", f"{count} messages cleared.")

    @pyqtSlot()
    def stop_processing(self):
        logger.info("ChatbotWorker: Stop processing requested.")
        self._stop_requested = True
        # If in PROCESSING state, this flag will be checked by _make_api_request_with_retries
        if self.state == ChatbotState.PROCESSING:
             self._set_state(ChatbotState.STOPPING, "Stop request received during processing.")
        else: # If not processing, just signal that a stop was requested if it implies anything else
             self.statusUpdate.emit("stop_requested_idle", "Stop requested while not actively processing.")


class AIChatbotManager(QObject):
    statusChanged = pyqtSignal(str, str) # overall manager status, details
    errorOccurred = pyqtSignal(str, str) # error_message, error_code
    workerReady = pyqtSignal() # Emitted when worker is initialized and ready
    workerStopped = pyqtSignal() # Emitted when worker thread has fully stopped
    configChanged = pyqtSignal(dict) # Forwards worker's configChanged signal

    def __init__(self, config: ChatbotConfig = None, parent=None):
        super().__init__(parent)
        self.parent_window = parent # Reference to MainWindow
        self.config = config or ChatbotConfig()
        self._last_api_key: Optional[str] = None # Store the API key at manager level

        self.worker: Optional[ChatbotWorker] = None
        self.worker_thread: Optional[QThread] = None
        self._state = ChatbotState.STOPPED # Manager's own state
        self._mutex = QMutex() # For thread-safe access to shared manager attributes if needed

        self._request_counter = 0
        logger.info("AIChatbotManager initialized")
        self.set_state(ChatbotState.INITIALIZING) # Initial state after creation
        # Try to initialize worker if an API key might be available from settings
        # This part will be handled by MainWindow calling set_api_key after loading settings
        self.set_state(ChatbotState.STOPPED) # Back to stopped if no immediate key

    @property
    @thread_safe
    def state(self) -> ChatbotState:
        return self._state

    @thread_safe
    def set_state(self, new_state: ChatbotState, details: str = ""):
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            detail_msg = details if details else f"Manager state changed"
            self.statusChanged.emit(new_state.value, detail_msg)
            logger.info(f"Manager state: {old_state.value} -> {new_state.value} ({detail_msg})")

    @property # Public getter for the last API key
    def api_key(self) -> Optional[str]:
        return self._last_api_key

    @pyqtSlot(str)
    def set_api_key(self, api_key: Optional[str]):
        logger.info(f"AIChatbotManager: set_api_key called ({'key provided' if api_key else 'key cleared'}).")
        new_api_key_stripped = api_key.strip() if api_key else None

        if self._last_api_key == new_api_key_stripped and self.worker_thread and self.worker_thread.isRunning():
            logger.info("API key is the same and worker is running. No change needed.")
            if self.worker and self.worker.state == ChatbotState.READY:
                 self.set_state(ChatbotState.READY, "API key confirmed, worker ready.")
            return

        self.set_state(ChatbotState.INITIALIZING, "Processing API key...")
        self._stop_worker_gracefully() # Ensure any old worker is stopped

        self._last_api_key = new_api_key_stripped

        if self._last_api_key:
            logger.info("Valid API key provided. Starting worker.")
            self._start_worker(self._last_api_key)
        else:
            logger.info("API key cleared or not provided.")
            self.set_state(ChatbotState.STOPPED, "No API key. Worker not started.")
            self.workerStopped.emit() # Signal that any potential worker operation is done

    def _start_worker(self, api_key_to_use: str):
        if self.worker_thread and self.worker_thread.isRunning():
            logger.warning("Worker thread already running. Attempting to stop first.")
            self._stop_worker_gracefully()

        self.worker_thread = QThread(self) # Parent self to QThread for lifecycle management
        self.worker = ChatbotWorker(self.config) # Pass a copy of the current manager config
        self.worker.moveToThread(self.worker_thread)

        # Connect worker signals to manager slots or forward them
        self._connect_worker_signals()

        # When thread starts, call set_api_key on the worker in its own thread context
        self.worker_thread.started.connect(lambda key=api_key_to_use: QMetaObject.invokeMethod(self.worker, "set_api_key", Qt.QueuedConnection, Q_ARG(str, key)))
        self.worker_thread.finished.connect(self._on_worker_thread_finished)

        self.worker_thread.start()
        logger.info("Worker thread started.")
        # Manager state will be updated by worker's statusUpdate signal (e.g., to READY or ERROR)

    def _connect_worker_signals(self):
        if not self.worker: return
        # Forward signals from worker to manager's parent (MainWindow)
        if self.parent_window:
            if hasattr(self.parent_window, '_handle_ai_response'):
                self.worker.responseReady.connect(self.parent_window._handle_ai_response)
            # Error already connected to manager's _on_worker_error, which then emits manager's errorOccurred
            # Status already connected to manager's _on_worker_status_update
            
            # Let MainWindow handle specific worker status updates if it wants to
            if hasattr(self.parent_window, '_update_ai_chat_status'): # This is the general status label
                 self.worker.statusUpdate.connect(self.parent_window._update_ai_chat_status)
            if hasattr(self.parent_window, '_handle_ai_error'): # This is the general error handler
                 self.worker.errorOccurred.connect(self.parent_window._handle_ai_error)


        self.worker.statusUpdate.connect(self._on_worker_status_update)
        self.worker.errorOccurred.connect(self._on_worker_error)
        self.worker.configChanged.connect(self.configChanged.emit) # Forward this

    def _disconnect_worker_signals(self):
        if not self.worker: return
        signals_to_disconnect = [
            self.worker.responseReady,
            self.worker.errorOccurred,
            self.worker.statusUpdate,
            self.worker.progressUpdate,
            self.worker.configChanged
        ]
        for signal in signals_to_disconnect:
            try: signal.disconnect()
            except (TypeError, RuntimeError) as e: logger.debug(f"Error disconnecting signal (may already be disconnected or worker deleted): {e}")


    @pyqtSlot(str, str)
    def _on_worker_status_update(self, worker_status_val: str, details: str):
        logger.info(f"Manager received worker status: {worker_status_val}, details: {details}")
        try:
            worker_state_enum = ChatbotState(worker_status_val)
            if worker_state_enum == ChatbotState.READY:
                self.set_state(ChatbotState.READY, f"Worker ready. {details}")
                self.workerReady.emit()
            elif worker_state_enum == ChatbotState.ERROR:
                self.set_state(ChatbotState.ERROR, f"Worker in error state. {details}")
            elif worker_state_enum == ChatbotState.IDLE and self.state == ChatbotState.INITIALIZING :
                 # If worker becomes idle during manager initialization, it might mean API key was bad.
                 # The errorOccurred signal from worker should handle this more directly.
                 pass
            # Other worker states could map to manager states or just be logged.
        except ValueError:
            logger.warning(f"Received unknown worker status value: {worker_status_val}")


    @pyqtSlot(str, str)
    def _on_worker_error(self, error_message: str, error_code: str):
        logger.error(f"Manager received worker error: [{error_code}] {error_message}")
        self.set_state(ChatbotState.ERROR, f"Worker error: {error_code}")
        self.errorOccurred.emit(error_message, error_code) # Forward error
        if error_code == "AUTH_ERROR_WORKER" or error_code == "AUTH_ERROR" : # If auth error from worker
            self._last_api_key = None # Invalidate stored API key

    def _stop_worker_gracefully(self, timeout_ms=5000):
        logger.info("Manager: Stopping worker gracefully...")
        if self.worker_thread and self.worker_thread.isRunning():
            if self.worker:
                # Request worker to stop any ongoing processing
                QMetaObject.invokeMethod(self.worker, "stop_processing", Qt.QueuedConnection)
            
            self.worker_thread.quit() # Ask thread to exit event loop
            if not self.worker_thread.wait(timeout_ms):
                logger.warning("Worker thread did not quit gracefully within timeout. Terminating...")
                self.worker_thread.terminate() # Force terminate
                self.worker_thread.wait(1000) # Wait a bit more after terminate
            else:
                logger.info("Worker thread quit gracefully.")
        else:
            logger.info("Worker thread not running or doesn't exist.")
        
        self._cleanup_worker_resources()


    def _cleanup_worker_resources(self):
        logger.info("Manager: Cleaning up worker resources.")
        if self.worker:
            self._disconnect_worker_signals()
            self.worker.deleteLater()
            self.worker = None
        if self.worker_thread:
            # self.worker_thread.finished.disconnect(self._on_worker_thread_finished) # Disconnect if connected
            self.worker_thread.deleteLater()
            self.worker_thread = None
        # Manager state is typically set to STOPPED by _on_worker_thread_finished or after _stop_worker_gracefully
        if self.state != ChatbotState.STOPPED:
             self.set_state(ChatbotState.STOPPED, "Worker resources cleaned up.")


    def _on_worker_thread_finished(self):
        logger.info("Manager: Worker thread finished signal received.")
        self._cleanup_worker_resources() # Ensure resources are cleaned up
        self.workerStopped.emit()
        # State should be STOPPED now unless a new worker is being started immediately.
        if self.state != ChatbotState.INITIALIZING: # Avoid setting to stopped if we are immediately restarting
             self.set_state(ChatbotState.STOPPED, "Worker thread has finished.")


    @pyqtSlot(str)
    def send_message(self, message: str) -> Optional[str]:
        logger.info(f"Manager: send_message request for '{message[:30]}...'")
        if self.state != ChatbotState.READY:
            err_msg = f"Cannot send message. Manager not ready (State: {self.state.value})"
            logger.error(err_msg)
            self.errorOccurred.emit(err_msg, "MANAGER_NOT_READY")
            return None
        if not self.worker or not self.worker_thread or not self.worker_thread.isRunning():
            logger.error("Worker not available to send message.")
            self.errorOccurred.emit("Worker not available.", "NO_WORKER_INSTANCE")
            return None

        self._request_counter += 1
        request_id = f"req_{int(time.time())}_{self._request_counter}"
        
        # Update diagram context on worker before sending message
        self._update_diagram_context_on_worker()

        # Queue the process_message call on the worker's thread
        success = QMetaObject.invokeMethod(self.worker, "process_message", Qt.QueuedConnection,
                                           Q_ARG(str, message), Q_ARG(str, request_id))
        if success:
            logger.info(f"Message (ID: {request_id}) queued for worker processing.")
            return request_id
        else:
            logger.error(f"Failed to invoke process_message on worker for ID: {request_id}.")
            self.errorOccurred.emit("Failed to queue message for worker.", "INVOKE_METHOD_FAILED")
            return None
            
    def _update_diagram_context_on_worker(self):
        if not self.worker: return
        diagram_json = "{}" # Default to empty if no parent or scene
        if self.parent_window and hasattr(self.parent_window, 'scene') and \
           hasattr(self.parent_window.scene, 'get_diagram_data'):
            try:
                diagram_data = self.parent_window.scene.get_diagram_data()
                diagram_json = json.dumps(diagram_data)
            except Exception as e:
                logger.error(f"Failed to get/serialize diagram data: {e}")
                diagram_json = json.dumps({"error": f"Failed to get diagram: {str(e)}"})
        
        QMetaObject.invokeMethod(self.worker, "set_diagram_context", Qt.QueuedConnection, Q_ARG(str, diagram_json))


    @pyqtSlot()
    def clear_conversation_history(self):
        logger.info("Manager: clear_conversation_history requested.")
        if self.worker:
            QMetaObject.invokeMethod(self.worker, "clear_history", Qt.QueuedConnection)
        else:
            logger.warning("Cannot clear history: Worker not available.")
            self.errorOccurred.emit("Worker not available to clear history.", "NO_WORKER_INSTANCE")

    @pyqtSlot(dict)
    def update_config(self, new_config_dict: Dict[str, Any]):
        logger.info(f"Manager: update_config requested with: {new_config_dict}")
        # Update manager's own copy of config
        updated_manager_config = False
        for key, value in new_config_dict.items():
            if hasattr(self.config, key):
                if getattr(self.config, key) != value:
                    setattr(self.config, key, value)
                    updated_manager_config = True
                    logger.info(f"Manager config '{key}' updated to: {value}")
        
        if updated_manager_config:
            self.configChanged.emit(self.config.__dict__) # Emit manager's full config if changed

        # If worker exists, send the partial update to it
        if self.worker and self.worker_thread and self.worker_thread.isRunning():
            config_json = json.dumps(new_config_dict) # Send only the delta
            QMetaObject.invokeMethod(self.worker, "update_config", Qt.QueuedConnection, Q_ARG(str, config_json))
        elif self.state == ChatbotState.STOPPED and self._last_api_key and 'model_name' in new_config_dict:
            # If manager is stopped but has an API key, and model name changes,
            # re-initialize the worker with the new config.
            logger.info("Manager stopped but API key exists. Model changed, re-initializing worker.")
            self.set_api_key(self._last_api_key) # This will use the updated self.config

    def stop(self):
        logger.info("AIChatbotManager: Stop method called.")
        self.set_state(ChatbotState.STOPPING, "Manager stop initiated.")
        self._stop_worker_gracefully()
        # Final state should be set by _on_worker_thread_finished or _cleanup_worker_resources

    def __del__(self):
        logger.info("AIChatbotManager: __del__ called. Ensuring cleanup.")
        self.stop()