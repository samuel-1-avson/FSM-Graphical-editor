from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTime, QTimer, Qt, QMetaObject, pyqtSlot # pyqtSlot added for clarity
import openai
import json
# from PyQt5.QtCore import pyqtSlot # Redundant if already imported above

# Q_ARG for invokeMethod is not directly available in Python,
# we pass arguments directly to the lambda or method.
# from PyQt5.QtCore import Q_ARG # Not needed for Python direct calls / lambdas

class ChatbotWorker(QObject):
    """
    Worker object to handle OpenAI API calls in a separate thread.
    """
    responseReady = pyqtSignal(str, bool) # str: response content, bool: was_fsm_generation_attempt
    errorOccurred = pyqtSignal(str)
    statusUpdate = pyqtSignal(str)

    def __init__(self, api_key, model_name="gpt-3.5-turbo", parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        self.conversation_history = []
        self.current_diagram_context_json_str = None
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
                self.errorOccurred.emit(f"Failed to initialize OpenAI client: {e}") # Notify manager/UI
        else:
            self.client = None
            print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): OpenAI client not initialized (no API key). ---")

    @pyqtSlot(str) # Explicitly mark as slot if called via QMetaObject.invokeMethod from another thread
    def set_api_key(self, api_key):
        print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): set_api_key called. ---")
        self.api_key = api_key
        self._initialize_client()

    @pyqtSlot(str)
    def set_current_diagram_context(self, diagram_json_str: str | None): # diagram_json_str can be None
        self.current_diagram_context_json_str = diagram_json_str
        print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): Diagram context set/updated in worker. ---")

    @pyqtSlot(str) # Mark as slot for clarity and cross-thread invocation
    def process_message(self, user_message: str):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- WORKER_PROCESS ({current_time}): process_message CALLED for: '{user_message}' ---")
        print(f"--- WORKER_PROCESS ({current_time}): Using diagram context: {'YES' if self.current_diagram_context_json_str else 'NO'} ---")

        if not self.api_key or not self.client:
            self.errorOccurred.emit("OpenAI API key not set or client not initialized. Please set it in AI Assistant Settings.")
            self.statusUpdate.emit("Status: API Key required.")
            return

        self.statusUpdate.emit("Status: Thinking...")

        keywords_for_generation = [
            "generate fsm", "create fsm", "generate an fsm model",
            "generate state machine", "create state machine", "design state machine",
            "model fsm", "model state machine",
            "draw fsm", "draw state machine", "make an fsm", "fsm design for",
            # "design it", # Too broad, can lead to false positives
            "/generate_fsm" # A more explicit command
        ]
        user_msg_lower = user_message.lower()
        # More robust check: ensure keyword is a whole word or at start/end of phrase
        is_fsm_generation_attempt = any(re.search(r'\b' + re.escape(keyword) + r'\b', user_msg_lower) for keyword in keywords_for_generation)

        print(f"--- WORKER_PROCESS ({current_time}): is_fsm_generation_attempt = {is_fsm_generation_attempt} for '{user_message}' ---")

        system_prompt_content = "You are a helpful assistant for designing Finite State Machines."
        if self.current_diagram_context_json_str:
            try:
                # Ensure it's not None before trying to load
                if self.current_diagram_context_json_str is not None:
                    diagram = json.loads(self.current_diagram_context_json_str)
                    if "error" not in diagram: # Check for our own error marker
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
                else:
                    system_prompt_content += " No diagram context was provided for this request." # Or, The current diagram is empty.

            except json.JSONDecodeError:
                print(f"--- WORKER_PROCESS_CTX_ERROR ({current_time}): JSONDecodeError processing diagram context. ---")
                system_prompt_content += " (Error reading diagram context in worker)."
            except Exception as e_ctx:
                print(f"--- WORKER_PROCESS_CTX_ERROR ({current_time}): Error processing diagram context: {e_ctx} ---")
                system_prompt_content += " (Issue with diagram context string)."

        if is_fsm_generation_attempt:
            system_prompt_content += (
                " When asked to generate an FSM, you MUST respond with ONLY a valid JSON object that directly represents the FSM data. "
                "The root of the JSON should be an object. "
                "This JSON object should have a top-level string key 'description' for a brief FSM description (e.g., 'A simple traffic light controller.'). "
                "It MUST have a key 'states' which is a list of state objects. "
                "Each state object MUST have a 'name' (string, required and unique for the FSM). "
                "Optional state object keys: 'is_initial' (boolean, default false), 'is_final' (boolean, default false), "
                "'entry_action' (string), 'during_action' (string), 'exit_action' (string), "
                "and a 'properties' object (optional) which can contain 'color' (string, CSS hex e.g., '#RRGGBB'). "
                "The JSON object MUST also have a key 'transitions' which is a list of transition objects. "
                "Each transition object MUST have 'source' (string, an existing state name from the 'states' list) and 'target' (string, an existing state name from the 'states' list). "
                "Optional transition object keys: 'event' (string), 'condition' (string), 'action' (string), "
                "'control_offset_x' (number, for curve horizontal bend), 'control_offset_y' (number, for curve vertical shift from midpoint), " # Added control points
                "and a 'properties' object (optional) for 'color'. "
                "Optionally, include a top-level key 'comments' which is a list of comment objects. Each comment object can have 'text' (string), 'x' (number, optional for layout hint), 'y' (number, optional for layout hint), 'width' (number, optional). "
                "Do not include any state positions (x, y, width, height for states) in the JSON, as the application will handle layout. "
                "Absolutely no other text, greetings, explanations, or markdown formatting like ```json should be outside or inside this single JSON object response. The response must be parseable by json.loads()."
            )
        else: # General chat
             system_prompt_content += " For general conversation, provide helpful and concise answers."


        messages_for_api = [{"role": "system", "content": system_prompt_content}]
        history_context_limit = -6 # last 3 user/assistant turns (6 messages)
        if self.conversation_history:
            messages_for_api.extend(self.conversation_history[history_context_limit:])
        messages_for_api.append({"role": "user", "content": user_message})

        try:
            request_params = {
                "model": self.model_name,
                "messages": messages_for_api
            }
            if is_fsm_generation_attempt:
                request_params["response_format"] = {"type": "json_object"}
                print(f"--- WORKER_PROCESS ({QTime.currentTime().toString('hh:mm:ss.zzz')}): Requesting JSON object format from AI. ---")

            chat_completion = self.client.chat.completions.create(**request_params)
            ai_response_content = chat_completion.choices[0].message.content

            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": ai_response_content})

            self.responseReady.emit(ai_response_content, is_fsm_generation_attempt) # Emit with the flag

        except openai.APIConnectionError as e:
            self.errorOccurred.emit(f"API Connection Error: {str(e)[:200]}")
        except openai.RateLimitError as e:
            self.errorOccurred.emit(f"Rate Limit Exceeded: {str(e)[:200]}")
        except openai.AuthenticationError as e:
            self.errorOccurred.emit(f"Authentication Error (Invalid API Key?): {str(e)[:200]}")
        except openai.APIError as e:
            error_detail = str(e)
            if hasattr(e, 'message') and e.message: error_detail = e.message
            # Try to get more info from json_body if it exists
            json_body_error = ""
            if hasattr(e, 'json_body') and e.json_body and 'error' in e.json_body and 'message' in e.json_body['error']:
                json_body_error = e.json_body['error']['message']
            if json_body_error: error_detail += f" (Detail: {json_body_error})"
            self.errorOccurred.emit(f"OpenAI API Error: {type(e).__name__} - {error_detail[:250]}")
        except Exception as e:
            error_msg = f"Unexpected error in AI worker: {type(e).__name__} - {str(e)[:150]}"
            print(f"--- WORKER_PROCESS ERROR ({QTime.currentTime().toString('hh:mm:ss.zzz')}): {error_msg} ---")
            self.errorOccurred.emit(error_msg)
        finally:
            self.statusUpdate.emit("Status: Ready.") # Always revert to Ready or specific error status

    @pyqtSlot()
    def clear_history(self):
        self.conversation_history = []
        print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): Conversation history cleared. ---")
        self.statusUpdate.emit("Status: Chat history cleared.")


class AIChatbotManager(QObject):
    statusUpdate = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    # This is the signal MainWindow connects to for FSM data
    fsmDataReceived = pyqtSignal(dict, str) # dict: FSM data, str: original user description/prompt
    # New signal for plain chat responses
    plainResponseReady = pyqtSignal(str) # str: plain text AI response

    def __init__(self, parent=None): # parent is expected to be MainWindow
        super().__init__(parent)
        self.parent_window = parent
        self.api_key: str | None = None
        self.chatbot_worker: ChatbotWorker | None = None
        self.chatbot_thread: QThread | None = None
        self.last_fsm_request_description: str | None = None # Store the description that triggered FSM gen
        print(f"--- MGR ({QTime.currentTime().toString('hh:mm:ss.zzz')}): AIChatbotManager initialized. ---")

    def _cleanup_existing_worker_and_thread(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_CLEANUP ({current_time}): CALLED ---")

        if self.chatbot_thread and self.chatbot_thread.isRunning():
            print(f"--- MGR_CLEANUP ({current_time}): Attempting to quit existing thread... ---")
            self.chatbot_thread.quit()
            if not self.chatbot_thread.wait(1000):
                print(f"--- MGR_CLEANUP WARN ({current_time}): Thread did not quit gracefully. Terminating. ---")
                self.chatbot_thread.terminate()
                self.chatbot_thread.wait()
            print(f"--- MGR_CLEANUP ({current_time}): Existing thread stopped. ---")
        self.chatbot_thread = None # Ensure it's None after stopping

        if self.chatbot_worker:
            print(f"--- MGR_CLEANUP ({current_time}): Disconnecting signals and scheduling old worker for deletion. ---")
            # Disconnect signals:
            # It's generally safer to disconnect specific slots if you know them,
            # or just let deleteLater handle it if the object has no other strong refs.
            # If worker signals were connected to manager slots, they need to be disconnected here.
            try: self.chatbot_worker.responseReady.disconnect(self._handle_worker_response)
            except (TypeError, RuntimeError): pass # Already disconnected or never connected
            try: self.chatbot_worker.errorOccurred.disconnect(self.errorOccurred) # if directly forwarded
            except (TypeError, RuntimeError): pass
            try: self.chatbot_worker.statusUpdate.disconnect(self.statusUpdate) # if directly forwarded
            except (TypeError, RuntimeError): pass

            self.chatbot_worker.deleteLater()
            print(f"--- MGR_CLEANUP ({current_time}): Old worker scheduled for deletion. ---")
        self.chatbot_worker = None # Ensure it's None
        print(f"--- MGR_CLEANUP ({current_time}): Finished. Worker and thread are None. ---")


    def set_api_key(self, api_key: str | None):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        old_key = self.api_key
        self.api_key = api_key
        print(f"--- MGR_SET_API_KEY ({current_time}): New key: '{'SET' if api_key else 'NONE'}', Old key: '{'SET' if old_key else 'NONE'}' ---")

        # Re-setup worker if key changed OR if key is set and worker doesn't exist/run
        if old_key != self.api_key or (self.api_key and (not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning())):
            self._cleanup_existing_worker_and_thread()
            if self.api_key:
                self._setup_worker()
            else:
                self.statusUpdate.emit("Status: API Key cleared. AI Assistant inactive.")
        elif self.chatbot_worker and self.api_key: # Key is the same, and worker exists
             # Use QMetaObject.invokeMethod for thread-safe call to worker's slot
             QMetaObject.invokeMethod(self.chatbot_worker, "set_api_key", Qt.QueuedConnection, Q_ARG(str, self.api_key)) # Q_ARG needed for C++ signature matching
             self.statusUpdate.emit("Status: Ready. API Key re-confirmed.")
        elif not self.api_key:
            self.statusUpdate.emit("Status: API Key required.")


    def _setup_worker(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        if not self.api_key:
            print(f"--- MGR_SETUP_WORKER ({current_time}): Cannot setup - API key is not set. ---")
            self.statusUpdate.emit("Status: API Key required.")
            return

        if self.chatbot_worker or (self.chatbot_thread and self.chatbot_thread.isRunning()):
            print(f"--- MGR_SETUP_WORKER ({current_time}): Worker/thread exists or is running. Cleaning up first. ---")
            self._cleanup_existing_worker_and_thread() # Important to prevent multiple workers

        print(f"--- MGR_SETUP_WORKER ({current_time}): Setting up new worker and thread. ---")
        self.chatbot_thread = QThread(self) # Parent thread to Manager for lifecycle mgmt
        self.chatbot_worker = ChatbotWorker(self.api_key) # No parent, will be managed by thread
        self.chatbot_worker.moveToThread(self.chatbot_thread)

        # Connect WORKER signals to MANAGER slots (or directly to MainWindow if appropriate)
        self.chatbot_worker.responseReady.connect(self._handle_worker_response)
        self.chatbot_worker.errorOccurred.connect(self.errorOccurred) # Forward worker errors
        self.chatbot_worker.statusUpdate.connect(self.statusUpdate) # Forward worker status

        self.chatbot_thread.start()
        print(f"--- MGR_SETUP_WORKER ({current_time}): New AI Chatbot worker thread started. ---")
        self.statusUpdate.emit("Status: AI Assistant Ready.")

    @pyqtSlot(str, bool) # Slot for worker's responseReady(str_content, bool_was_fsm_attempt)
    def _handle_worker_response(self, ai_response_content: str, was_fsm_generation_attempt: bool):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_HANDLE_WORKER_RESPONSE ({current_time}): Received from worker. Was FSM attempt: {was_fsm_generation_attempt} ---")
        # MainWindow's _append_to_ai_chat_display should be called with "AI" and ai_response_content
        # This can be done by MainWindow connecting to plainResponseReady or fsmDataReceived.

        if was_fsm_generation_attempt:
            try:
                fsm_data = json.loads(ai_response_content)
                # Basic validation (more can be added)
                if isinstance(fsm_data, dict) and ('states' in fsm_data or 'transitions' in fsm_data): # Looser check, states or transitions
                    print(f"--- MGR_HANDLE_WORKER_RESPONSE ({current_time}): Parsed FSM JSON successfully. Emitting fsmDataReceived. ---")
                    # Use self.last_fsm_request_description here for context
                    source_desc = self.last_fsm_request_description or "AI Generated FSM"
                    self.fsmDataReceived.emit(fsm_data, source_desc)
                    self.parent_window._append_to_ai_chat_display("AI", f"Generated FSM structure (see diagram). Original prompt: {source_desc[:50]}...") # Give feedback
                    return # Handled as FSM
                else:
                    print(f"--- MGR_HANDLE_WORKER_RESPONSE ({current_time}): JSON parsed but not valid FSM structure. Treating as plain text. ---")
                    self.errorOccurred.emit("AI returned JSON, but it's not a valid FSM structure. Displaying as text.")
            except json.JSONDecodeError:
                print(f"--- MGR_HANDLE_WORKER_RESPONSE ({current_time}): Failed to parse AI response as JSON. Treating as plain text. ---")
                # Not an error for the user directly, just means it wasn't FSM JSON.
                # Could emit a specific status or just let it fall through to plainResponseReady.
                self.statusUpdate.emit("Status: AI response was not valid FSM JSON.")
            # If it was an FSM attempt but failed parsing or validation, it falls through to plainResponseReady.
            # This means MainWindow will display the raw (potentially malformed JSON) response from AI.

        # If not an FSM attempt, or if FSM parsing failed, emit as plain response
        print(f"--- MGR_HANDLE_WORKER_RESPONSE ({current_time}): Emitting plainResponseReady. ---")
        self.plainResponseReady.emit(ai_response_content)


    def _prepare_and_send_to_worker(self, user_message_text: str, is_fsm_gen_specific: bool = False):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_PREP_SEND ({current_time}): For: '{user_message_text[:30]}...', FSM_specific_req: {is_fsm_gen_specific} ---")

        if not self.api_key:
            self.errorOccurred.emit("API Key not set. Configure in Settings.")
            self.parent_window._append_to_ai_chat_display("System Error", "API Key not set.")
            return

        if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
            print(f"--- MGR_PREP_SEND ({current_time}): Worker/Thread not ready. ---")
            if self.api_key and (not self.chatbot_thread or not self.chatbot_thread.isRunning()):
                 print(f"--- MGR_PREP_SEND ({current_time}): Attempting to re-setup worker. ---")
                 self._setup_worker()
            if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
                self.errorOccurred.emit("AI Assistant is not ready. Please wait or check settings.")
                self.parent_window._append_to_ai_chat_display("System Error", "AI Assistant is not ready.")
                return
        
        # Store description if it's an FSM generation request
        if is_fsm_gen_specific:
            self.last_fsm_request_description = user_message_text
        else: # For general chat, clear it so a plain response isn't misattributed
            self.last_fsm_request_description = None 

        diagram_json_str = None
        if self.parent_window and hasattr(self.parent_window, 'scene'):
            try:
                diagram_data = self.parent_window.scene.get_diagram_data()
                # Optionally, simplify diagram_data for context if it's too large
                # e.g., only send state names and transition counts
                diagram_json_str = json.dumps(diagram_data)
            except Exception as e:
                print(f"--- MGR_PREP_SEND ({current_time}): Error getting diagram data: {e} ---")
                diagram_json_str = json.dumps({"error": "Could not retrieve diagram context."})
        
        # Use QMetaObject.invokeMethod for thread-safe calls to worker slots
        # The lambda ensures the context is set before process_message is attempted.
        # Note: Q_ARG is for C++ signatures. For Python, pass args directly or use lambdas.
        if diagram_json_str is not None: # Only set if we have it
             QMetaObject.invokeMethod(self.chatbot_worker, "set_current_diagram_context", Qt.QueuedConnection, Q_ARG(str, diagram_json_str))
        
        QMetaObject.invokeMethod(self.chatbot_worker, "process_message", Qt.QueuedConnection, Q_ARG(str, user_message_text))
        
        print(f"--- MGR_PREP_SEND ({current_time}): process_message call queued for worker. ---")
        # MainWindow should update its UI to "Thinking..."
        if hasattr(self.parent_window, '_update_ai_chat_status'):
            self.parent_window._update_ai_chat_status("Status: Sending to AI...")


    def send_message(self, user_message_text: str): # General chat
        self._prepare_and_send_to_worker(user_message_text, is_fsm_gen_specific=False)

    def generate_fsm_from_description(self, description: str): # Specific FSM generation
         self._prepare_and_send_to_worker(description, is_fsm_gen_specific=True)


    def clear_conversation_history(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR ({current_time}): clear_conversation_history CALLED. ---")
        if self.chatbot_worker and self.chatbot_thread and self.chatbot_thread.isRunning():
            QMetaObject.invokeMethod(self.chatbot_worker, "clear_history", Qt.QueuedConnection)
            print(f"--- MGR ({current_time}): clear_history invoked on worker. ---")
        else:
            # If worker isn't running, the history is effectively "cleared" from its perspective
            # Manager itself doesn't hold history; worker does.
            self.statusUpdate.emit("Status: Chatbot not active (history is in worker).")

    def stop_chatbot(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_STOP ({current_time}): stop_chatbot CALLED. ---")
        self._cleanup_existing_worker_and_thread()
        self.statusUpdate.emit("Status: AI Assistant Stopped.")
        print(f"--- MGR_STOP ({current_time}): Chatbot stopped and cleaned up. ---")

    def set_online_status(self, is_online: bool): # Called by MainWindow's internet check
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_NET_STATUS ({current_time}): Online status: {is_online} ---")
        if self.api_key:
            if is_online:
                self.statusUpdate.emit("Status: Online and Ready.")
                if not self.chatbot_thread or not self.chatbot_thread.isRunning(): # If was offline and came back online
                    self._setup_worker() # Try to re-initialize worker
            else:
                self.statusUpdate.emit("Status: Offline. AI features unavailable.")
                # Optionally stop/pause worker thread if it makes sense
                # self._cleanup_existing_worker_and_thread() # Or a less destructive pause
        else:
            if is_online:
                self.statusUpdate.emit("Status: Online, API Key required.")
            else:
                self.statusUpdate.emit("Status: Offline, API Key required.")