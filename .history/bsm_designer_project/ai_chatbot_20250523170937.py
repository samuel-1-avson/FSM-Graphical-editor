"""
Enhanced AI Chatbot Manager with improved thread management, error handling, and functionality.
"""

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
import threading
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
    timeout_seconds: int = 30
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

def thread_safe(func):
    """Decorator to ensure thread-safe execution"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if hasattr(self, '_mutex'):
            with QMutexLocker(self._mutex):
                return func(self, *args, **kwargs)
        return func(self, *args, **kwargs)
    return wrapper

class ChatbotWorker(QObject):
    """Enhanced worker for OpenAI API interactions"""
    
    # Signals
    responseReady = pyqtSignal(str, dict)  # response, metadata
    errorOccurred = pyqtSignal(str, str)   # error_message, error_code
    statusUpdate = pyqtSignal(str, str)    # status, details
    progressUpdate = pyqtSignal(int)       # progress percentage
    configChanged = pyqtSignal(dict)       # new config
    
    def __init__(self, config: ChatbotConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.client: Optional[openai.OpenAI] = None
        self.conversation_history: List[ChatMessage] = []
        self.current_diagram_context: Optional[Dict] = None
        self.state = ChatbotState.IDLE
        self._mutex = QMutex()
        self._stop_requested = False
        self._current_request_id: Optional[str] = None
        
        logger.info(f"ChatbotWorker initialized with model: {self.config.model_name}")
    
    @thread_safe
    def get_state(self) -> ChatbotState:
        """Get current worker state"""
        return self.state
    
    @thread_safe
    def set_state(self, new_state: ChatbotState):
        """Set worker state and emit status update"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self.statusUpdate.emit(new_state.value, f"State changed from {old_state.value}")
            logger.info(f"Worker state: {old_state.value} -> {new_state.value}")
    
    @pyqtSlot(str)
    def set_api_key(self, api_key: str):
        """Set OpenAI API key and initialize client"""
        try:
            self.set_state(ChatbotState.INITIALIZING)
            
            if not api_key or not api_key.strip():
                raise ValueError("API key cannot be empty")
            
            self.client = openai.OpenAI(api_key=api_key.strip())
            
            # Test the API key with a minimal request
            self._test_api_connection()
            
            self.set_state(ChatbotState.READY)
            self.statusUpdate.emit("ready", "API key validated and client initialized")
            
        except openai.AuthenticationError:
            self.set_state(ChatbotState.ERROR)
            self.errorOccurred.emit("Invalid API key", "AUTH_ERROR")
        except Exception as e:
            self.set_state(ChatbotState.ERROR)
            self.errorOccurred.emit(f"Client initialization failed: {str(e)}", "INIT_ERROR")
    
    def _test_api_connection(self):
        """Test API connection with minimal request"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.model_name,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            logger.info("API connection test successful")
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            raise
    
    @pyqtSlot(str)  
    def update_config(self, config_json: str):
        """Update worker configuration"""
        try:
            config_dict = json.loads(config_json)
            
            # Update config attributes
            for key, value in config_dict.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            
            self.configChanged.emit(config_dict)
            logger.info(f"Configuration updated: {config_dict}")
            
        except Exception as e:
            self.errorOccurred.emit(f"Config update failed: {str(e)}", "CONFIG_ERROR")
    
    @pyqtSlot(str)
    def set_diagram_context(self, diagram_json: str):
        """Set current diagram context"""
        try:
            if diagram_json:
                self.current_diagram_context = json.loads(diagram_json)
                logger.info("Diagram context updated")
            else:
                self.current_diagram_context = None
                logger.info("Diagram context cleared")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid diagram JSON: {e}")
            self.current_diagram_context = {"error": "Invalid diagram data"}
    
    @pyqtSlot(str, str)
    def process_message(self, user_message: str, request_id: str = None):
        """Process user message with enhanced error handling and retries"""
        if self.state not in [ChatbotState.READY, ChatbotState.IDLE]:
            self.errorOccurred.emit("Worker not ready", "NOT_READY")
            return
        
        if not self.client:
            self.errorOccurred.emit("OpenAI client not initialized", "NO_CLIENT")
            return
        
        self._current_request_id = request_id or str(int(time.time() * 1000))
        self.set_state(ChatbotState.PROCESSING)
        
        try:
            self._process_message_internal(user_message)
        except Exception as e:
            logger.error(f"Unexpected error in process_message: {e}")
            self.errorOccurred.emit(f"Processing failed: {str(e)}", "PROCESSING_ERROR")
        finally:
            self.set_state(ChatbotState.READY)
            self._current_request_id = None
    
    def _process_message_internal(self, user_message: str):
        """Internal message processing with retries"""
        is_generation_request = self._is_generation_request(user_message)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(is_generation_request)
        
        # Prepare messages
        messages = self._prepare_messages(system_prompt, user_message)
        
        # Make API request with retries
        response_content = self._make_api_request_with_retries(messages, is_generation_request)
        
        # Update conversation history
        self._update_conversation_history(user_message, response_content)
        
        # Emit response with metadata
        metadata = {
            "request_id": self._current_request_id,
            "is_generation": is_generation_request,
            "model": self.config.model_name,
            "timestamp": time.time()
        }
        
        self.responseReady.emit(response_content, metadata)
    
    def _is_generation_request(self, message: str) -> bool:
        """Check if message is requesting FSM generation"""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in self.config.generation_keywords)
    
    def _build_system_prompt(self, is_generation: bool) -> str:
        """Build system prompt based on context and request type"""
        base_prompt = "You are a helpful assistant for designing Finite State Machines."
        
        # Add diagram context
        if self.current_diagram_context and "error" not in self.current_diagram_context:
            context_info = self._format_diagram_context()
            base_prompt += context_info
        
        # Add generation-specific instructions
        if is_generation:
            base_prompt += self._get_generation_instructions()
        
        return base_prompt
    
    def _format_diagram_context(self) -> str:
        """Format current diagram context for system prompt"""
        try:
            states = self.current_diagram_context.get('states', [])
            transitions = self.current_diagram_context.get('transitions', [])
            
            if states:
                state_names = [s.get('name', 'Unnamed') for s in states[:5]]
                context = f" Current diagram has states: {', '.join(state_names)}"
                if len(states) > 5:
                    context += " and others"
                context += f". It has {len(transitions)} transition(s)."
                return context
            else:
                return " The current diagram is empty."
                
        except Exception as e:
            logger.error(f"Error formatting diagram context: {e}")
            return " (Error reading diagram context)."
    
    def _get_generation_instructions(self) -> str:
        """Get instructions for FSM generation requests"""
        return (
            " When asked to generate an FSM, respond with ONLY a valid JSON object. "
            "The JSON must have: 'description' (string), 'states' (array of state objects), "
            "and 'transitions' (array of transition objects). "
            "State objects need 'name' (required, unique string) and optional: "
            "'is_initial' (boolean), 'is_final' (boolean), 'entry_action', 'during_action', "
            "'exit_action' (strings), and 'properties' (object with 'color'). "
            "Transition objects need 'source' and 'target' (existing state names) and optional: "
            "'event', 'condition', 'action' (strings), and 'properties' (object with 'color'). "
            "Optionally include 'comments' array with objects having 'text', 'x', 'y'. "
            "No markdown, explanations, or other text outside the JSON object."
        )
    
    def _prepare_messages(self, system_prompt: str, user_message: str) -> List[Dict]:
        """Prepare message list for API request"""
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history (limited)
        history_limit = min(self.config.max_history_length, len(self.conversation_history))
        if history_limit > 0:
            recent_history = self.conversation_history[-history_limit:]
            for msg in recent_history:
                messages.append({"role": msg.role, "content": msg.content})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def _make_api_request_with_retries(self, messages: List[Dict], is_generation: bool) -> str:
        """Make API request with retry logic"""
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            if self._stop_requested:
                raise InterruptedError("Request cancelled")
            
            try:
                self.progressUpdate.emit(int((attempt + 1) * 100 / self.config.max_retries))
                
                # Prepare request parameters
                request_params = {
                    "model": self.config.model_name,
                    "messages": messages,
                    "temperature": self.config.temperature
                }
                
                if self.config.max_tokens:
                    request_params["max_tokens"] = self.config.max_tokens
                
                if is_generation:
                    request_params["response_format"] = {"type": "json_object"}
                
                # Make the request
                response = self.client.chat.completions.create(**request_params)
                content = response.choices[0].message.content
                
                self.progressUpdate.emit(100)
                return content
                
            except openai.RateLimitError as e:
                last_exception = e
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Rate limit hit, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                    
            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                last_exception = e
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (attempt + 1)
                    logger.warning(f"Connection error, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                    
            except openai.AuthenticationError as e:
                # Don't retry auth errors
                self.errorOccurred.emit("Authentication failed - check API key", "AUTH_ERROR")
                raise
                
            except Exception as e:
                last_exception = e
                logger.error(f"API request failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay)
                    continue
        
        # All retries failed
        error_msg = f"All {self.config.max_retries} attempts failed"
        if last_exception:
            error_msg += f": {str(last_exception)}"
        
        raise Exception(error_msg)
    
    def _update_conversation_history(self, user_message: str, ai_response: str):
        """Update conversation history with size management"""
        # Add messages to history
        self.conversation_history.append(
            ChatMessage("user", user_message, metadata={"request_id": self._current_request_id})
        )
        self.conversation_history.append(
            ChatMessage("assistant", ai_response, metadata={"request_id": self._current_request_id})
        )
        
        # Trim history if too long
        if len(self.conversation_history) > self.config.max_history_length:
            excess = len(self.conversation_history) - self.config.max_history_length
            self.conversation_history = self.conversation_history[excess:]
            logger.info(f"Trimmed {excess} messages from history")
    
    @pyqtSlot()
    def clear_history(self):
        """Clear conversation history"""
        with QMutexLocker(self._mutex):
            history_count = len(self.conversation_history)
            self.conversation_history.clear()
            self.statusUpdate.emit("history_cleared", f"Cleared {history_count} messages")
            logger.info(f"Conversation history cleared ({history_count} messages)")
    
    @pyqtSlot()
    def stop_processing(self):
        """Stop current processing"""
        self._stop_requested = True
        self.statusUpdate.emit("stopping", "Stop requested")
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get conversation statistics"""
        return {
            "message_count": len(self.conversation_history),
            "user_messages": len([m for m in self.conversation_history if m.role == "user"]),
            "assistant_messages": len([m for m in self.conversation_history if m.role == "assistant"]),
            "oldest_message": self.conversation_history[0].timestamp if self.conversation_history else None,
            "newest_message": self.conversation_history[-1].timestamp if self.conversation_history else None
        }


class AIChatbotManager(QObject):
    """Enhanced manager for AI chatbot with robust thread management"""
    
    # Manager signals
    statusChanged = pyqtSignal(str, str)    # status, details
    errorOccurred = pyqtSignal(str, str)    # error_message, error_code
    workerReady = pyqtSignal()
    workerStopped = pyqtSignal()
    configChanged = pyqtSignal(dict)
    
    def __init__(self, config: ChatbotConfig = None, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = config or ChatbotConfig()
        
        # Thread management
        self.worker: Optional[ChatbotWorker] = None
        self.worker_thread: Optional[QThread] = None
        self.state = ChatbotState.STOPPED
        self._cleanup_timer = QTimer()
        self._cleanup_timer.setSingleShot(True)
        self._cleanup_timer.timeout.connect(self._force_cleanup)
        
        # Request management
        self._pending_requests = {}
        self._request_counter = 0
        
        logger.info("AIChatbotManager initialized")
    
    def get_state(self) -> ChatbotState:
        """Get current manager state"""
        return self.state
    
    def set_state(self, new_state: ChatbotState):
        """Set manager state"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self.statusChanged.emit(new_state.value, f"Manager state: {old_state.value} -> {new_state.value}")
            logger.info(f"Manager state: {old_state.value} -> {new_state.value}")
    
    def set_api_key(self, api_key: str):
        """Set API key and reinitialize worker if needed"""
        try:
            self.set_state(ChatbotState.INITIALIZING)
            
            # Stop existing worker
            self._stop_worker_gracefully()
            
            if api_key and api_key.strip():
                # Start new worker with API key
                self._start_worker(api_key.strip())
            else:
                self.set_state(ChatbotState.STOPPED)
                self.statusChanged.emit("stopped", "No API key provided")
                
        except Exception as e:
            self.set_state(ChatbotState.ERROR)
            self.errorOccurred.emit(f"Failed to set API key: {str(e)}", "API_KEY_ERROR")
    
    def _start_worker(self, api_key: str):
        """Start worker thread with proper setup"""
        try:
            # Create new thread and worker
            self.worker_thread = QThread(self)
            self.worker = ChatbotWorker(self.config)
            self.worker.moveToThread(self.worker_thread)
            
            # Connect worker signals
            self._connect_worker_signals()
            
            # Connect thread lifecycle
            self.worker_thread.started.connect(lambda: self.worker.set_api_key(api_key))
            self.worker_thread.finished.connect(self._on_thread_finished)
            
            # Start thread
            self.worker_thread.start()
            
            logger.info("Worker thread started")
            
        except Exception as e:
            logger.error(f"Failed to start worker: {e}")
            self._cleanup_worker()
            raise
    
    def _connect_worker_signals(self):
        """Connect worker signals to appropriate handlers"""
        if not self.worker:
            return
        
        # Connect to parent window if available
        if self.parent_window:
            if hasattr(self.parent_window, '_handle_ai_response'):
                self.worker.responseReady.connect(self.parent_window._handle_ai_response)
            if hasattr(self.parent_window, '_handle_ai_error'):
                self.worker.errorOccurred.connect(self.parent_window._handle_ai_error)
            if hasattr(self.parent_window, '_update_ai_chat_status'):
                self.worker.statusUpdate.connect(self.parent_window._update_ai_chat_status)
        
        # Connect to manager handlers
        self.worker.statusUpdate.connect(self._on_worker_status_update)
        self.worker.errorOccurred.connect(self._on_worker_error)
        self.worker.configChanged.connect(self.configChanged.emit)
    
    def _disconnect_worker_signals(self):
        """Safely disconnect worker signals"""
        if not self.worker:
            return
        
        try:
            self.worker.responseReady.disconnect()
            self.worker.errorOccurred.disconnect()
            self.worker.statusUpdate.disconnect()
            self.worker.progressUpdate.disconnect()
            self.worker.configChanged.disconnect()
        except (TypeError, RuntimeError):
            pass  # Signals already disconnected or object deleted
    
    @pyqtSlot(str, str)
    def _on_worker_status_update(self, status: str, details: str):
        """Handle worker status updates"""
        if status == "ready" and self.state == ChatbotState.INITIALIZING:
            self.set_state(ChatbotState.READY)
            self.workerReady.emit()
        elif status == "error":
            self.set_state(ChatbotState.ERROR)
    
    @pyqtSlot(str, str)
    def _on_worker_error(self, error_msg: str, error_code: str):
        """Handle worker errors"""
        logger.error(f"Worker error [{error_code}]: {error_msg}")
        if error_code == "AUTH_ERROR":
            self.set_state(ChatbotState.ERROR)
        self.errorOccurred.emit(error_msg, error_code)
    
    def _stop_worker_gracefully(self, timeout_ms: int = 3000):
        """Stop worker thread gracefully with timeout"""
        if not self.worker_thread or not self.worker_thread.isRunning():
            return
        
        try:
            self.set_state(ChatbotState.STOPPING)
            
            # Request worker to stop processing
            if self.worker:
                QMetaObject.invokeMethod(self.worker, "stop_processing", Qt.QueuedConnection)
            
            # Ask thread to quit
            self.worker_thread.quit()
            
            # Wait for graceful shutdown
            if not self.worker_thread.wait(timeout_ms):
                logger.warning("Thread did not stop gracefully, terminating...")
                self.worker_thread.terminate()
                self.worker_thread.wait(1000)  # Wait for termination
            
            logger.info("Worker thread stopped")
            
        except Exception as e:
            logger.error(f"Error stopping worker: {e}")
        finally:
            self._cleanup_worker()
    
    def _cleanup_worker(self):
        """Clean up worker and thread resources"""
        try:
            # Disconnect signals
            self._disconnect_worker_signals()
            
            # Schedule worker deletion
            if self.worker:
                self.worker.deleteLater()
                self.worker = None
            
            # Clean up thread
            if self.worker_thread:
                self.worker_thread.deleteLater()
                self.worker_thread = None
            
            logger.info("Worker cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def _on_thread_finished(self):
        """Handle thread finished signal"""
        logger.info("Worker thread finished")
        self.set_state(ChatbotState.STOPPED)
        self.workerStopped.emit()
    
    def _force_cleanup(self):
        """Force cleanup if graceful shutdown failed"""
        logger.warning("Forcing worker cleanup")
        self._cleanup_worker()
    
    def send_message(self, message: str) -> str:
        """Send message to worker with request tracking"""
        if self.state != ChatbotState.READY:
            error_msg = f"Manager not ready (state: {self.state.value})"
            self.errorOccurred.emit(error_msg, "NOT_READY")
            return None
        
        if not self.worker or not self.worker_thread or not self.worker_thread.isRunning():
            self.errorOccurred.emit("Worker not available", "NO_WORKER")
            return None
        
        try:
            # Generate request ID
            self._request_counter += 1
            request_id = f"req_{int(time.time())}_{self._request_counter}"
            
            # Update diagram context
            self._update_diagram_context()
            
            # Send message to worker
            QMetaObject.invokeMethod(
                self.worker, 
                "process_message", 
                Qt.QueuedConnection,
                Q_ARG(str, message),
                Q_ARG(str, request_id)
            )
            
            logger.info(f"Message queued for processing: {request_id}")
            return request_id
            
        except Exception as e:
            error_msg = f"Failed to send message: {str(e)}"
            self.errorOccurred.emit(error_msg, "SEND_ERROR")
            return None
    
    def _update_diagram_context(self):
        """Update worker with current diagram context"""
        if not self.parent_window or not hasattr(self.parent_window, 'scene'):
            return
        
        try:
            diagram_data = self.parent_window.scene.get_diagram_data()
            diagram_json = json.dumps(diagram_data)
            
            QMetaObject.invokeMethod(
                self.worker,
                "set_diagram_context",
                Qt.QueuedConnection,
                Q_ARG(str, diagram_json)
            )
            
        except Exception as e:
            logger.error(f"Failed to update diagram context: {e}")
            # Send error context
            error_context = json.dumps({"error": f"Failed to get diagram: {str(e)}"})
            QMetaObject.invokeMethod(
                self.worker,
                "set_diagram_context", 
                Qt.QueuedConnection,
                Q_ARG(str, error_context)
            )
    
    def clear_conversation_history(self):
        """Clear conversation history"""
        if self.state != ChatbotState.READY or not self.worker:
            self.errorOccurred.emit("Cannot clear history - worker not ready", "NOT_READY")
            return
        
        QMetaObject.invokeMethod(self.worker, "clear_history", Qt.QueuedConnection)
        logger.info("History clear requested")
    
    def update_config(self, new_config: Dict[str, Any]):
        """Update worker configuration"""
        try:
            # Update local config
            for key, value in new_config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            
            # Send to worker if available
            if self.worker and self.state == ChatbotState.READY:
                config_json = json.dumps(new_config)
                QMetaObject.invokeMethod(
                    self.worker,
                    "update_config",
                    Qt.QueuedConnection,
                    Q_ARG(str, config_json)
                )
            
            logger.info(f"Configuration updated: {new_config}")
            
        except Exception as e:
            self.errorOccurred.emit(f"Config update failed: {str(e)}", "CONFIG_ERROR")
    
    def stop(self):
        """Stop the chatbot manager"""
        logger.info("Stopping chatbot manager")
        self._stop_worker_gracefully()
    
    def get_status_info(self) -> Dict[str, Any]:
        """Get comprehensive status information"""
        return {
            "state": self.state.value,
            "has_worker": self.worker is not None,
            "thread_running": self.worker_thread.isRunning() if self.worker_thread else False,
            "config": {
                "model": self.config.model_name,
                "max_history": self.config.max_history_length,
                "timeout": self.config.timeout_seconds
            },
            "pending_requests": len(self._pending_requests)
        }
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.stop()
        except:
            pass