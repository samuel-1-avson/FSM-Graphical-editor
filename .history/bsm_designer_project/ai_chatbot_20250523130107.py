from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTime, QTimer, Qt, QMetaObject, pyqtSlot, Q_ARG
import openai
import json
from PyQt5.QtCore import pyqtSlot
class ChatbotWorker(QObject):
    """
    Worker object to handle OpenAI API calls in a separate thread.
    """
    responseReady = pyqtSignal(str) # Renamed from responseReceived to avoid confusion with Manager's signal
    errorOccurred = pyqtSignal(str)
    statusUpdate = pyqtSignal(str)

    def __init__(self, api_key, model_name="gpt-3.5-turbo", parent=None):
        super().__init__(parent) # Proper QObject init with parent
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        self.conversation_history = []
        self.current_diagram_context_json_str = None # To store diagram context
        self._initialize_client()
        print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): ChatbotWorker initialized ---")

    def _initialize_client(self):
        if self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): OpenAI client initialized for model {self.model_name}. ---")
            except Exception as e:
                self.client = None
                print(f"--- WORKER ERROR ({QTime.currentTime().toString('hh:mm:ss.zzz')}): Error initializing OpenAI client: {e} ---")
        else:
            self.client = None
            print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): OpenAI client not initialized (no API key). ---")    @pyqtSlot(str)
    def set_api_key(self, api_key):
        print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): set_api_key called. ---")
        self.api_key = api_key
        self._initialize_client()    @pyqtSlot('str')
    def set_current_diagram_context(self, diagram_json_str: str | None):
        self.current_diagram_context_json_str = diagram_json_str
        print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): Diagram context set/updated in worker. ---")

    # In ai_chatbot.py, class ChatbotWorker

    def process_message(self, user_message: str):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- WORKER_PROCESS ({current_time}): process_message CALLED for: '{user_message}' ---")
        print(f"--- WORKER_PROCESS ({current_time}): Using diagram context: {'YES' if self.current_diagram_context_json_str else 'NO'} ---")

        if not self.api_key or not self.client:
            self.errorOccurred.emit("OpenAI API key not set or client not initialized. Please set it in AI Assistant Settings.")
            self.statusUpdate.emit("Status: API Key required.")
            return

        self.statusUpdate.emit("Status: Thinking...") # Worker signals it's thinking

        # --- Start: Define is_generation_request (USE ONLY ONE DEFINITION) ---
        keywords_for_generation = [
            "generate fsm", "create fsm", "generate an fsm model", # Added more specific one
            "generate state machine", "create state machine", "design state machine",
            "model fsm", "model state machine",
            "draw fsm", "draw state machine",
            "design it", # Broad, keep with caution
            "/generate_fsm"
        ]
        user_msg_lower = user_message.lower()
        is_generation_request = any(keyword in user_msg_lower for keyword in keywords_for_generation)
        print(f"--- WORKER_PROCESS ({current_time}): is_generation_request = {is_generation_request} for '{user_message}' ---")
        # --- End: Define is_generation_request ---

        # --- System Prompt Construction ---
        system_prompt_content = "You are a helpful assistant for designing Finite State Machines."
        if self.current_diagram_context_json_str:
            try:
                diagram = json.loads(self.current_diagram_context_json_str)
                if "error" not in diagram:
                    state_names = [s.get('name', 'UnnamedState') for s in diagram.get('states', [])]
                    num_transitions = len(diagram.get('transitions', []))
                    if state_names:
                        context_summary = (
                            f" The current diagram has states: {', '.join(state_names[:5])}"
                            f"{' and others' if len(state_names) > 5 else ''}."
                            f" It has {num_transitions} transition(s)."
                        )
                        system_prompt_content += context_summary
                    else:
                        system_prompt_content += " The current diagram is empty."
            except json.JSONDecodeError:
                system_prompt_content += " (Error reading diagram context in worker)."
            except Exception as e_ctx:
                print(f"--- WORKER_PROCESS_CTX_ERROR ({current_time}): Error processing diagram context: {e_ctx} ---")
                system_prompt_content += " (Issue with diagram context string)."

        if is_generation_request:
            system_prompt_content += (
                " When asked to generate an FSM, you MUST respond with ONLY a valid JSON object that directly represents the FSM data. "
                "The root of the JSON should be an object. "
                "This JSON object should have a top-level string key 'description' for a brief FSM description. "
                "It MUST have a key 'states' which is a list of state objects. "
                "Each state object MUST have a 'name' (string, required and unique). "
                "Optional state object keys: 'is_initial' (boolean, default false), 'is_final' (boolean, default false), "
                "'entry_action' (string), 'during_action' (string), 'exit_action' (string), "
                "and a 'properties' object (optional) which can contain 'color' (string, CSS hex e.g., '#RRGGBB'). "
                "The JSON object MUST also have a key 'transitions' which is a list of transition objects. "
                "Each transition object MUST have 'source' (string, existing state name) and 'target' (string, existing state name). "
                "Optional transition object keys: 'event' (string), 'condition' (string), 'action' (string), "
                "and a 'properties' object (optional) for 'color'. "
                "Optionally, include a top-level key 'comments' which is a list of comment objects. Each comment object can have 'text' (string), 'x' (number, optional), 'y' (number, optional). "
                "Absolutely no other text, greetings, explanations, or markdown formatting like ```json should be outside or inside this single JSON object response."
            )
        # --- End System Prompt Construction ---

        # --- Initialize messages_for_api with the system prompt ---
        messages_for_api = [{"role": "system", "content": system_prompt_content}]
        # --- Add conversation history ---
        history_context_limit = -6 # last 3 user/assistant turns
        if self.conversation_history:
            messages_for_api.extend(self.conversation_history[history_context_limit:])
        # --- Add the current user message ---
        messages_for_api.append({"role": "user", "content": user_message}) # Use the original user_message

        try:
            request_params = {
                "model": self.model_name,
                "messages": messages_for_api
            }
            if is_generation_request:
                request_params["response_format"] = {"type": "json_object"}
                print(f"--- WORKER_PROCESS ({QTime.currentTime().toString('hh:mm:ss.zzz')}): Requesting JSON object format from AI. ---")

            chat_completion = self.client.chat.completions.create(**request_params)
            ai_response_content = chat_completion.choices[0].message.content

            # Update history before emitting response
            self.conversation_history.append({"role": "user", "content": user_message}) # Store original user message
            self.conversation_history.append({"role": "assistant", "content": ai_response_content})

            self.responseReady.emit(ai_response_content)

        except openai.APIConnectionError as e:
            self.errorOccurred.emit(f"API Connection Error: {str(e)[:200]}")
        except openai.RateLimitError as e:
            self.errorOccurred.emit(f"Rate Limit Exceeded: {str(e)[:200]}")
        except openai.AuthenticationError as e:
            self.errorOccurred.emit(f"Authentication Error (Invalid API Key?): {str(e)[:200]}")
        except openai.APIError as e:
            self.errorOccurred.emit(f"OpenAI API Error: {str(e)[:200]}")
        except Exception as e:
            error_msg = f"Unexpected error in AI worker: {type(e).__name__} - {str(e)[:150]}"
            print(f"--- WORKER_PROCESS ERROR ({QTime.currentTime().toString('hh:mm:ss.zzz')}): {error_msg} ---")
            self.errorOccurred.emit(error_msg)

    @pyqtSlot()
    def clear_history(self):
        # Your logic to clear the conversation history
        self.conversation_history = []
        # Optionally emit a signal to notify the UI
        self.statusUpdate.emit("Chat history cleared.")


class AIChatbotManager(QObject):
    # Manager specific signals, if any, e.g., for when its own state changes.
    # MainWindow will mostly connect to ChatbotWorker signals.
    statusUpdate = pyqtSignal(str) # e.g. "Manager ready", "Manager stopped"
    errorOccurred = pyqtSignal(str) # Manager-level errors, e.g. worker setup failed.

    def __init__(self, parent=None):
        super().__init__(parent)  # CORRECT QObject INITIALIZATION
        self.parent_window = parent # This is MainWindow
        self.api_key: str | None = None
        self.chatbot_worker: ChatbotWorker | None = None
        self.chatbot_thread: QThread | None = None
        print(f"--- MGR ({QTime.currentTime().toString('hh:mm:ss.zzz')}): AIChatbotManager initialized. ---")

    def _cleanup_existing_worker_and_thread(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_CLEANUP ({current_time}): CALLED ---")

        if self.chatbot_thread and self.chatbot_thread.isRunning():
            print(f"--- MGR_CLEANUP ({current_time}): Attempting to quit existing thread... ---")
            self.chatbot_thread.quit()
            if not self.chatbot_thread.wait(1000): # Wait up to 1 second
                print(f"--- MGR_CLEANUP WARN ({current_time}): Thread did not quit gracefully. Terminating. ---")
                self.chatbot_thread.terminate()
                self.chatbot_thread.wait() # Wait for termination
            print(f"--- MGR_CLEANUP ({current_time}): Existing thread stopped. ---")
        # else:
            # print(f"--- MGR_CLEANUP ({current_time}): No running thread to stop or thread is None. ---")


        if self.chatbot_worker:
            print(f"--- MGR_CLEANUP ({current_time}): Scheduling old worker for deletion and disconnecting signals. ---")
            # Ensure signals are disconnected if they were connected
            # Since connections are made to MainWindow slots, this cleanup is important.
            # This is robust as it checks if disconnect is possible
            try: self.chatbot_worker.responseReady.disconnect(self.parent_window._handle_ai_response)
            except (TypeError, RuntimeError): pass
            try: self.chatbot_worker.errorOccurred.disconnect(self.parent_window._handle_ai_error)
            except (TypeError, RuntimeError): pass
            try: self.chatbot_worker.statusUpdate.disconnect(self.parent_window._update_ai_chat_status)
            except (TypeError, RuntimeError): pass
            self.chatbot_worker.deleteLater()
            print(f"--- MGR_CLEANUP ({current_time}): Old worker scheduled for deletion. ---")
        
        self.chatbot_thread = None
        self.chatbot_worker = None
        print(f"--- MGR_CLEANUP ({current_time}): Finished. Worker and thread are None. ---")

    def set_api_key(self, api_key: str | None):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        old_key = self.api_key
        self.api_key = api_key
        print(f"--- MGR_SET_API_KEY ({current_time}): New key: '{'SET' if api_key else 'NONE'}', Old key: '{'SET' if old_key else 'NONE'}' ---")

        if old_key != self.api_key or (self.api_key and not self.chatbot_worker):
            self._cleanup_existing_worker_and_thread() # Cleanup before setting up new
            if self.api_key:
                self._setup_worker()
            else:
                # Emit status for API key cleared from Manager.
                self.statusUpdate.emit("Status: API Key cleared. AI Assistant inactive.")
        elif self.chatbot_worker: # Key is same, or was null and still null
             if self.api_key : # Key exists and is same, update worker if needed
                 QMetaObject.invokeMethod(self.chatbot_worker, "set_api_key", Qt.QueuedConnection, Q_ARG(str, self.api_key))
                 self.statusUpdate.emit("Status: Ready. API Key re-confirmed.") # or some other appropriate status
             else: # No key, do nothing or emit cleared status if not already.
                 self.statusUpdate.emit("Status: API Key required.")


    def _setup_worker(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        if not self.api_key:
            print(f"--- MGR_SETUP_WORKER ({current_time}): Cannot setup - API key is not set. ---")
            self.statusUpdate.emit("Status: API Key required.")
            return

        # Ensure any previous worker/thread is fully gone before creating new ones.
        if self.chatbot_worker or (self.chatbot_thread and self.chatbot_thread.isRunning()):
            print(f"--- MGR_SETUP_WORKER ({current_time}): Worker/thread exists or is running. Cleaning up first. ---")
            self._cleanup_existing_worker_and_thread()


        print(f"--- MGR_SETUP_WORKER ({current_time}): Setting up new worker and thread. ---")
        self.chatbot_thread = QThread(self.parent_window) # Parent QThread to MainWindow for proper cleanup
        self.chatbot_worker = ChatbotWorker(self.api_key, parent=None) # Worker shouldn't have GUI parent if moved to thread
        self.chatbot_worker.moveToThread(self.chatbot_thread)

        # Connect signals from WORKER directly to MAINWINDOW slots
        self.chatbot_worker.responseReady.connect(self.parent_window._handle_ai_response)
        self.chatbot_worker.errorOccurred.connect(self.parent_window._handle_ai_error)
        self.chatbot_worker.statusUpdate.connect(self.parent_window._update_ai_chat_status)

        # To start the worker's event loop if it has one or to start processing if thread is for tasks
        # self.chatbot_thread.started.connect(self.chatbot_worker.some_initial_method_if_needed) # If worker needs an init on thread
        
        self.chatbot_thread.start()
        print(f"--- MGR_SETUP_WORKER ({current_time}): New AI Chatbot worker thread started. ---")
        self.statusUpdate.emit("Status: AI Assistant Ready.") # Manager informs it's ready

    def send_message(self, user_message_text: str):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_SEND ({current_time}): send_message CALLED for: '{user_message_text[:30]}...' ---")

        if not self.api_key:
            self.errorOccurred.emit("API Key not set. Configure in Settings.")
            return

        if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
            print(f"--- MGR_SEND ({current_time}): Worker/Thread not ready. ---")
            if self.api_key and not (self.chatbot_thread and self.chatbot_thread.isRunning()):
                 print(f"--- MGR_SEND ({current_time}): Attempting to re-setup worker as thread is not running. ---")
                 self._setup_worker() # Attempt to set up if thread isn't running
            
            # After setup attempt, re-check
            if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
                self.errorOccurred.emit("AI Assistant is not ready. Please wait or check settings.")
                return
        
        diagram_json_str = None
        if self.parent_window and hasattr(self.parent_window, 'scene'):
            try:
                diagram_data = self.parent_window.scene.get_diagram_data()
                diagram_json_str = json.dumps(diagram_data)
            except Exception as e:
                print(f"--- MGR_SEND ({current_time}): Error getting diagram data for worker: {e} ---")
                diagram_json_str = json.dumps({"error": "Could not retrieve diagram context for AI."})
        
        # Set context and then invoke process_message using QTimer.singleShot for thread safety
        if diagram_json_str:
            QTimer.singleShot(0, lambda: self.chatbot_worker.set_current_diagram_context(diagram_json_str))
        
        QTimer.singleShot(0, lambda: self.chatbot_worker.process_message(user_message_text))
        print(f"--- MGR_SEND ({current_time}): process_message call queued for worker. ---")
        # MainWindow's _on_send_ai_chat_message should have already updated UI to "thinking..." or similar

    def clear_conversation_history(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR ({current_time}): clear_conversation_history CALLED. ---")
        if self.chatbot_worker and self.chatbot_thread and self.chatbot_thread.isRunning():
            QMetaObject.invokeMethod(self.chatbot_worker, "clear_history", Qt.QueuedConnection)
            print(f"--- MGR ({current_time}): clear_history invoked on worker. ---")
        else:
            self.statusUpdate.emit("Status: Chatbot not active to clear history.")

    def stop_chatbot(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_STOP ({current_time}): stop_chatbot CALLED. ---")
        self._cleanup_existing_worker_and_thread()
        self.statusUpdate.emit("Status: AI Assistant Stopped.")
        print(f"--- MGR_STOP ({current_time}): Chatbot stopped and cleaned up. ---")