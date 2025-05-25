from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTime, QTimer, Qt, QMetaObject, pyqtSlot
import openai
import json
import re # For more robust keyword checking

# Q_ARG is a C++ macro, not directly used in Python this way.
# from PyQt5.QtCore import Q_ARG # This line should be removed or commented out

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
        self._current_processing_had_error = False # Flag to track errors within a process_message call
        self._initialize_client()
        print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): ChatbotWorker initialized ---")

    def _initialize_client(self):
        if self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): OpenAI client initialized for model {self.model_name}. ---")
            except Exception as e:
                self.client = None
                error_msg = f"Failed to initialize OpenAI client: {e}"
                print(f"--- WORKER ERROR ({QTime.currentTime().toString('hh:mm:ss.zzz')}): {error_msg} ---")
                self.errorOccurred.emit(error_msg) # Notify about initialization failure
        else:
            self.client = None
            print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): OpenAI client not initialized (no API key). ---")

    @pyqtSlot(str)
    def set_api_key(self, api_key: str):
        print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): set_api_key called. ---")
        self.api_key = api_key
        self._initialize_client()

    @pyqtSlot(str)
    def set_current_diagram_context(self, diagram_json_str: str | None):
        self.current_diagram_context_json_str = diagram_json_str
        # print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): Diagram context set/updated in worker. Length: {len(diagram_json_str) if diagram_json_str else 'None'} ---")

    @pyqtSlot(str)
    def process_message(self, user_message: str):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- WORKER_PROCESS ({current_time}): process_message CALLED for: '{user_message[:50]}...' ---")
        
        self._current_processing_had_error = False # Reset error flag for this processing attempt

        if not self.api_key or not self.client:
            error_msg = "OpenAI API key not set or client not initialized. Please set it in AI Assistant Settings."
            self.errorOccurred.emit(error_msg)
            self.statusUpdate.emit("Status: API Key required.")
            self._current_processing_had_error = True # Mark that an error handled status was set
            return

        self.statusUpdate.emit("Status: Thinking...")

        keywords_for_generation = [
            "generate fsm", "create fsm", "generate an fsm model",
            "generate state machine", "create state machine", "design state machine",
            "model fsm", "model state machine",
            "draw fsm", "draw state machine", "make an fsm", "fsm design for",
            "/generate_fsm"
        ]
        user_msg_lower = user_message.lower()
        is_fsm_generation_attempt = any(re.search(r'\b' + re.escape(keyword) + r'\b', user_msg_lower) for keyword in keywords_for_generation)

        print(f"--- WORKER_PROCESS ({current_time}): is_fsm_generation_attempt = {is_fsm_generation_attempt} for '{user_message[:50]}...' ---")

        system_prompt_content = "You are a helpful assistant for designing Finite State Machines."
        if self.current_diagram_context_json_str:
            try:
                if self.current_diagram_context_json_str is not None:
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
                else: # Explicitly None
                    system_prompt_content += " No diagram context was provided for this request."
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
                "'control_offset_x' (number, for curve horizontal bend), 'control_offset_y' (number, for curve vertical shift from midpoint), "
                "and a 'properties' object (optional) for 'color'. "
                "Optionally, include a top-level key 'comments' which is a list of comment objects. Each comment object can have 'text' (string), 'x' (number, optional for layout hint), 'y' (number, optional for layout hint), 'width' (number, optional). "
                "Do not include any state positions (x, y, width, height for states) in the JSON, as the application will handle layout. "
                "Absolutely no other text, greetings, explanations, or markdown formatting like ```json should be outside or inside this single JSON object response. The response must be parseable by json.loads()."
            )
        else:
             system_prompt_content += " For general conversation, provide helpful and concise answers."

        messages_for_api = [{"role": "system", "content": system_prompt_content}]
        history_context_limit = -6
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

            self.responseReady.emit(ai_response_content, is_fsm_generation_attempt)

        except openai.APIConnectionError as e:
            self.errorOccurred.emit(f"API Connection Error: {str(e)[:200]}")
            self._current_processing_had_error = True
        except openai.RateLimitError as e:
            self.errorOccurred.emit(f"Rate Limit Exceeded: {str(e)[:200]}")
            self._current_processing_had_error = True
        except openai.AuthenticationError as e: # This also typically means API key is bad
            self.errorOccurred.emit(f"Authentication Error (Invalid API Key?): {str(e)[:200]}")
            self.statusUpdate.emit("Status: API Key Error.") # More specific status
            self._current_processing_had_error = True
        except openai.APIError as e:
            error_detail = str(e)
            if hasattr(e, 'message') and e.message: error_detail = e.message
            json_body_error = ""
            if hasattr(e, 'json_body') and e.json_body and 'error' in e.json_body and 'message' in e.json_body['error']:
                json_body_error = e.json_body['error']['message']
            if json_body_error: error_detail += f" (Detail: {json_body_error})"
            self.errorOccurred.emit(f"OpenAI API Error: {type(e).__name__} - {error_detail[:250]}")
            self._current_processing_had_error = True
        except Exception as e:
            error_msg = f"Unexpected error in AI worker: {type(e).__name__} - {str(e)[:150]}"
            print(f"--- WORKER_PROCESS ERROR ({QTime.currentTime().toString('hh:mm:ss.zzz')}): {error_msg} ---")
            self.errorOccurred.emit(error_msg)
            self._current_processing_had_error = True
        finally:
            # If no error occurred during this specific processing call AND the client is still valid
            # (meaning API key was okay at the start of this call), then set status to Ready.
            # Errors or API key issues would have set their own status messages.
            if not self._current_processing_had_error and self.client:
                self.statusUpdate.emit("Status: Ready.")


    @pyqtSlot()
    def clear_history(self):
        self.conversation_history = []
        print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): Conversation history cleared. ---")
        self.statusUpdate.emit("Status: Chat history cleared.")


class AIChatbotManager(QObject):
    statusUpdate = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    fsmDataReceived = pyqtSignal(dict, str)
    plainResponseReady = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.api_key: str | None = None
        self.chatbot_worker: ChatbotWorker | None = None
        self.chatbot_thread: QThread | None = None
        self.last_fsm_request_description: str | None = None
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
        self.chatbot_thread = None

        if self.chatbot_worker:
            print(f"--- MGR_CLEANUP ({current_time}): Disconnecting signals and scheduling old worker for deletion. ---")
            try: self.chatbot_worker.responseReady.disconnect(self._handle_worker_response)
            except (TypeError, RuntimeError): pass
            try: self.chatbot_worker.errorOccurred.disconnect(self.errorOccurred)
            except (TypeError, RuntimeError): pass
            try: self.chatbot_worker.statusUpdate.disconnect(self.statusUpdate)
            except (TypeError, RuntimeError): pass
            self.chatbot_worker.deleteLater()
            print(f"--- MGR_CLEANUP ({current_time}): Old worker scheduled for deletion. ---")
        self.chatbot_worker = None
        print(f"--- MGR_CLEANUP ({current_time}): Finished. Worker and thread are None. ---")

    def set_api_key(self, api_key: str | None):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        old_key = self.api_key
        self.api_key = api_key
        print(f"--- MGR_SET_API_KEY ({current_time}): New key: '{'SET' if api_key else 'NONE'}', Old key: '{'SET' if old_key else 'NONE'}' ---")

        if old_key != self.api_key or (self.api_key and (not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning())):
            self._cleanup_existing_worker_and_thread()
            if self.api_key:
                self._setup_worker()
            else:
                self.statusUpdate.emit("Status: API Key cleared. AI Assistant inactive.")
        elif self.chatbot_worker and self.api_key:
             QTimer.singleShot(0, lambda: self.chatbot_worker.set_api_key(self.api_key) if self.chatbot_worker else None)
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
            self._cleanup_existing_worker_and_thread()

        print(f"--- MGR_SETUP_WORKER ({current_time}): Setting up new worker and thread. ---")
        self.chatbot_thread = QThread(self)
        self.chatbot_worker = ChatbotWorker(self.api_key)
        self.chatbot_worker.moveToThread(self.chatbot_thread)

        self.chatbot_worker.responseReady.connect(self._handle_worker_response)
        self.chatbot_worker.errorOccurred.connect(self.errorOccurred)
        self.chatbot_worker.statusUpdate.connect(self.statusUpdate)

        self.chatbot_thread.start()
        print(f"--- MGR_SETUP_WORKER ({current_time}): New AI Chatbot worker thread started. ---")
        self.statusUpdate.emit("Status: AI Assistant Ready.")

    @pyqtSlot(str, bool)
    def _handle_worker_response(self, ai_response_content: str, was_fsm_generation_attempt: bool):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_HANDLE_WORKER_RESPONSE ({current_time}): Received from worker. Was FSM attempt: {was_fsm_generation_attempt} ---")

        if was_fsm_generation_attempt:
            try:
                fsm_data = json.loads(ai_response_content)
                if isinstance(fsm_data, dict) and ('states' in fsm_data or 'transitions' in fsm_data):
                    print(f"--- MGR_HANDLE_WORKER_RESPONSE ({current_time}): Parsed FSM JSON successfully. Emitting fsmDataReceived. ---")
                    source_desc = self.last_fsm_request_description or "AI Generated FSM"
                    self.fsmDataReceived.emit(fsm_data, source_desc)
                    # MainWindow will append "AI: Generated FSM structure..." via its slot
                    return
                else:
                    print(f"--- MGR_HANDLE_WORKER_RESPONSE ({current_time}): JSON parsed but not valid FSM structure. Treating as plain text. ---")
                    self.errorOccurred.emit("AI returned JSON, but it's not a valid FSM structure. Displaying as text.")
            except json.JSONDecodeError:
                print(f"--- MGR_HANDLE_WORKER_RESPONSE ({current_time}): Failed to parse AI response as JSON. Treating as plain text. ---")
                self.statusUpdate.emit("Status: AI response was not valid FSM JSON.")
            # Fall through to plainResponseReady if FSM parsing/validation fails

        print(f"--- MGR_HANDLE_WORKER_RESPONSE ({current_time}): Emitting plainResponseReady. ---")
        self.plainResponseReady.emit(ai_response_content)

    def _prepare_and_send_to_worker(self, user_message_text: str, is_fsm_gen_specific: bool = False):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_PREP_SEND ({current_time}): For: '{user_message_text[:30]}...', FSM_specific_req: {is_fsm_gen_specific} ---")

        if not self.api_key:
            self.errorOccurred.emit("API Key not set. Configure in Settings.")
            if self.parent_window and hasattr(self.parent_window, '_append_to_ai_chat_display'):
                self.parent_window._append_to_ai_chat_display("System Error", "API Key not set.")
            return

        if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
            print(f"--- MGR_PREP_SEND ({current_time}): Worker/Thread not ready. ---")
            if self.api_key and (not self.chatbot_thread or not self.chatbot_thread.isRunning()):
                 print(f"--- MGR_PREP_SEND ({current_time}): Attempting to re-setup worker. ---")
                 self._setup_worker()
            if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
                self.errorOccurred.emit("AI Assistant is not ready. Please wait or check settings.")
                if self.parent_window and hasattr(self.parent_window, '_append_to_ai_chat_display'):
                    self.parent_window._append_to_ai_chat_display("System Error", "AI Assistant is not ready.")
                return

        if is_fsm_gen_specific: # This is used to set self.last_fsm_request_description
            self.last_fsm_request_description = user_message_text
        else:
            self.last_fsm_request_description = None

        diagram_json_str = None
        if self.parent_window and hasattr(self.parent_window, 'scene') and hasattr(self.parent_window.scene, 'get_diagram_data'):
            try:
                diagram_data = self.parent_window.scene.get_diagram_data()
                diagram_json_str = json.dumps(diagram_data)
            except Exception as e:
                print(f"--- MGR_PREP_SEND ({current_time}): Error getting diagram data: {e} ---")
                diagram_json_str = json.dumps({"error": "Could not retrieve diagram context."})
        else: # Handle case where parent_window or scene might not be fully set up
             diagram_json_str = json.dumps({"error": "Diagram context unavailable."})


        # Use QTimer.singleShot for thread-safe slot invocation
        if diagram_json_str is not None:
            # Ensure worker exists before trying to call its method
            QTimer.singleShot(0, lambda: self.chatbot_worker.set_current_diagram_context(diagram_json_str) if self.chatbot_worker else None)

        QTimer.singleShot(0, lambda: self.chatbot_worker.process_message(user_message_text) if self.chatbot_worker else None)

        print(f"--- MGR_PREP_SEND ({current_time}): set_current_diagram_context and process_message calls queued for worker. ---")
        if hasattr(self.parent_window, '_update_ai_chat_status'): # Check if parent_window is fully formed
            self.parent_window._update_ai_chat_status("Status: Sending to AI...")

    def send_message(self, user_message_text: str):
        self._prepare_and_send_to_worker(user_message_text, is_fsm_gen_specific=False)

    def generate_fsm_from_description(self, description: str):
         self._prepare_and_send_to_worker(description, is_fsm_gen_specific=True) # <--- Correctly passes True

    def clear_conversation_history(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR ({current_time}): clear_conversation_history CALLED. ---")
        if self.chatbot_worker and self.chatbot_thread and self.chatbot_thread.isRunning():
            QTimer.singleShot(0, lambda: self.chatbot_worker.clear_history() if self.chatbot_worker else None)
            print(f"--- MGR ({current_time}): clear_history invoked on worker. ---")
        else:
            self.statusUpdate.emit("Status: Chatbot not active (history is in worker).")

    def stop_chatbot(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_STOP ({current_time}): stop_chatbot CALLED. ---")
        self._cleanup_existing_worker_and_thread()
        self.statusUpdate.emit("Status: AI Assistant Stopped.")
        print(f"--- MGR_STOP ({current_time}): Chatbot stopped and cleaned up. ---")

    def set_online_status(self, is_online: bool):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_NET_STATUS ({current_time}): Online status: {is_online} ---")
        if self.api_key:
            if is_online:
                self.statusUpdate.emit("Status: Online and Ready.")
                if not self.chatbot_thread or not self.chatbot_thread.isRunning():
                    self._setup_worker()
            else:
                self.statusUpdate.emit("Status: Offline. AI features unavailable.")
                # Consider stopping the worker thread if offline for a long time to save resources
                # self._cleanup_existing_worker_and_thread() # Decided against auto-stop for now
        else:
            if is_online:
                self.statusUpdate.emit("Status: Online, API Key required.")
            else:
                self.statusUpdate.emit("Status: Offline, API Key required.")