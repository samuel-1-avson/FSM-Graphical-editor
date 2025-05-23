from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTime # Ensure QTime is imported
import openai # Keep your openai import as it was
import json

class ChatbotWorker(QObject):
    """
    Worker object to handle OpenAI API calls in a separate thread.
    """
    responseReceived = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    statusUpdate = pyqtSignal(str)

    def __init__(self, api_key, model_name="gpt-3.5-turbo"): # Consider gpt-4-turbo-preview for better JSON
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        self.conversation_history = [] 
        self._initialize_client()
        print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): ChatbotWorker initialized ---")


    def _initialize_client(self):
        """Helper to initialize or re-initialize the OpenAI client."""
        if self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): OpenAI client initialized/re-initialized for model {self.model_name}. ---")
            except Exception as e:
                self.client = None
                print(f"--- WORKER ERROR ({QTime.currentTime().toString('hh:mm:ss.zzz')}): Error initializing OpenAI client: {e} ---")
                # self.errorOccurred.emit(f"Failed to initialize OpenAI client: {str(e)}") # Emit only on send attempt
        else:
            self.client = None
            print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): OpenAI client not initialized (no API key). ---")

    def set_api_key(self, api_key):
        print(f"--- WORKER ({QTime.currentTime().toString('hh:mm:ss.zzz')}): set_api_key called. ---")
        self.api_key = api_key
        self._initialize_client()

    def process_message(self, user_message: str):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- WORKER_PROCESS ({current_time}): process_message CALLED for: '{user_message}' ---")

        if not self.api_key or not self.client:
            self.errorOccurred.emit("OpenAI API key not set or client not initialized. Please set it in AI Assistant Settings.")
            self.statusUpdate.emit("Status: API Key required.")
            return

        self.statusUpdate.emit("Status: Thinking...")
        
        is_generation_request = "generate fsm" in user_message.lower() or \
                                 "create a state machine" in user_message.lower() or \
                                 "/generate_fsm" in user_message.lower()
                                 
        system_prompt_content = "You are a helpful assistant for designing Finite State Machines."
        
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
        
        messages_for_api = [{"role": "system", "content": system_prompt_content}]
        
        # Add limited conversation history for context
        # Take last N messages (e.g., 6 messages = 3 user/assistant turns)
        history_context_limit = -6 
        if self.conversation_history:
            messages_for_api.extend(self.conversation_history[history_context_limit:])
            
        messages_for_api.append({"role": "user", "content": user_message})

        try:
            request_params = {
                "model": self.model_name,
                "messages": messages_for_api
            }
            if is_generation_request:
                 # For newer models (e.g., gpt-3.5-turbo-1106, gpt-4-1106-preview, gpt-4-turbo-preview and later)
                 # This significantly increases reliability of JSON output.
                request_params["response_format"] = {"type": "json_object"}
                print(f"--- WORKER_PROCESS ({QTime.currentTime().toString('hh:mm:ss.zzz')}): Requesting JSON object format from AI. ---")


            chat_completion = self.client.chat.completions.create(**request_params)
            ai_response_content = chat_completion.choices[0].message.content
            
            current_time = QTime.currentTime().toString('hh:mm:ss.zzz') # Update time before logging
            print(f"--- WORKER_PROCESS ({current_time}): BEFORE EMITTING responseReady for: '{ai_response_content[:30].replace('\n',' ')}...' ---")
            
            # Update history *before* emitting, so if main thread processes response and asks another question, history is up-to-date
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": ai_response_content})
            
            self.responseReady.emit(ai_response_content) 
            print(f"--- WORKER_PROCESS ({QTime.currentTime().toString('hh:mm:ss.zzz')}): AFTER EMITTING responseReady ---")
            
        except openai.APIConnectionError as e:
            self.errorOccurred.emit(f"API Connection Error: {e}")
        except openai.RateLimitError as e:
            self.errorOccurred.emit(f"Rate Limit Exceeded: {e}")
        except openai.AuthenticationError as e:
            self.errorOccurred.emit(f"Authentication Error (Invalid API Key?): {e}")
        except openai.APIError as e: 
            self.errorOccurred.emit(f"OpenAI API Error: {e}")
        except Exception as e:
            error_msg = f"Unexpected error in AI worker: {type(e).__name__} - {str(e)}"
            print(f"--- WORKER_PROCESS ERROR ({QTime.currentTime().toString('hh:mm:ss.zzz')}): {error_msg} ---")
            self.errorOccurred.emit(error_msg)

    def clear_history(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        self.conversation_history = []
        print(f"--- WORKER ({current_time}): Conversation history cleared by worker. ---")
        self.statusUpdate.emit("Status: Chat history cleared.")


# In ai_chatbot.py

# ... (ChatbotWorker class as you provided) ...

class AIChatbotManager(QObject): # Make sure this is QObject
    # Signals for MainWindow to connect to if manager needs to emit something itself,
    # but mostly, MainWindow will connect directly to ChatbotWorker signals.
    # statusUpdate could still be useful for manager-level status.
    statusUpdate = pyqtSignal(str)
    # errorOccurred might also be for manager-level errors (e.g., worker setup fail)
    errorOccurred = pyqtSignal(str)


    def __init__(self, parent=None):
        super().__init__(parent) # CORRECT INITIALIZATION
        self.parent_window = parent
        self.api_key = None
        self.chatbot_worker: ChatbotWorker | None = None
        self.chatbot_thread: QThread | None = None
        print(f"--- MGR ({QTime.currentTime().toString('hh:mm:ss.zzz')}): AIChatbotManager initialized. ---")

    def _cleanup_existing_worker_and_thread(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_CLEANUP ({current_time}): CALLED ---")

        if self.chatbot_thread and self.chatbot_thread.isRunning():
            print(f"--- MGR_CLEANUP ({current_time}): Attempting to quit existing thread... ---")
            self.chatbot_thread.quit()
            if not self.chatbot_thread.wait(1000): # Reduced wait time
                print(f"--- MGR_CLEANUP WARN ({current_time}): Thread did not quit gracefully. Terminating. ---")
                self.chatbot_thread.terminate()
                self.chatbot_thread.wait()
            print(f"--- MGR_CLEANUP ({current_time}): Existing thread stopped. ---")
        # else:
            # print(f"--- MGR_CLEANUP ({current_time}): No running thread to stop. ---")

        if self.chatbot_worker:
            print(f"--- MGR_CLEANUP ({current_time}): Scheduling old worker for deletion and disconnecting signals. ---")
            # Disconnect ALL signals to avoid issues when worker is deleted or reused
            # Assuming direct connections from worker to MainWindow were made.
            # This cleanup is crucial.
            try: self.chatbot_worker.responseReady.disconnect()
            except TypeError: pass
            try: self.chatbot_worker.errorOccurred.disconnect()
            except TypeError: pass
            try: self.chatbot_worker.statusUpdate.disconnect()
            except TypeError: pass
            self.chatbot_worker.deleteLater()
            print(f"--- MGR_CLEANUP ({current_time}): Old worker scheduled for deletion. ---")

        self.chatbot_thread = None
        self.chatbot_worker = None
        print(f"--- MGR_CLEANUP ({current_time}): Finished. ---")

    def set_api_key(self, api_key: str | None):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        old_key = self.api_key
        self.api_key = api_key # Set the new key
        print(f"--- MGR_SET_API_KEY ({current_time}): New key: '{'SET' if api_key else 'NONE'}', Old key: '{'SET' if old_key else 'NONE'}' ---")

        if old_key != self.api_key or not self.chatbot_worker : # If key changed or worker not setup
            self._cleanup_existing_worker_and_thread()
            if self.api_key:
                self._setup_worker() # Setup new worker if new key is valid
            else:
                self.statusUpdate.emit("Status: API Key cleared. AI Assistant inactive.")
        elif self.chatbot_worker: # API key is the same, just pass to existing worker if worker exists
            self.chatbot_worker.set_api_key(self.api_key) # ChatbotWorker has a set_api_key
            self.statusUpdate.emit("Status: Ready. API Key is set.")

    def _setup_worker(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        if not self.api_key:
            print(f"--- MGR_SETUP_WORKER ({current_time}): Cannot setup - API key is not set. ---")
            self.statusUpdate.emit("Status: API Key required.") # Manager emits its status
            return

        if self.chatbot_worker or (self.chatbot_thread and self.chatbot_thread.isRunning()):
            print(f"--- MGR_SETUP_WORKER ({current_time}): Worker/thread already exists. Cleaning up first. ---")
            self._cleanup_existing_worker_and_thread() # Ensure clean state

        print(f"--- MGR_SETUP_WORKER ({current_time}): Setting up new worker and thread. ---")
        self.chatbot_thread = QThread(self.parent_window) # Parent QThread to MainWindow for proper cleanup on app close
        self.chatbot_worker = ChatbotWorker(self.api_key) # Pass current API key
        self.chatbot_worker.moveToThread(self.chatbot_thread)

        # Connect signals from WORKER directly to MAINWINDOW slots
        self.chatbot_worker.responseReady.connect(self.parent_window._handle_ai_response)
        self.chatbot_worker.errorOccurred.connect(self.parent_window._handle_ai_error)
        self.chatbot_worker.statusUpdate.connect(self.parent_window._update_ai_chat_status)

        self.chatbot_thread.start()
        print(f"--- MGR_SETUP_WORKER ({current_time}): New AI Chatbot worker thread started. ---")
        QTimer.singleShot(0, lambda: self.statusUpdate.emit("Status: AI Assistant Ready.")) # Manager signals ready

    def send_message(self, user_message_text: str):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_SEND ({current_time}): send_message CALLED with: '{user_message_text[:30]}...' ---")

        if not self.api_key:
            self.errorOccurred.emit("API Key not set. Configure in Settings.")
            # No need to call self.parent_window._update_ai_chat_status directly
            return

        if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
            print(f"--- MGR_SEND ({current_time}): Worker/Thread not ready. Attempting setup or emitting error. ---")
            if self.api_key:
                self._setup_worker() # Try to set up if not already (e.g., after API key was cleared and reset)
                # Need to re-evaluate if worker became ready after setup before proceeding.
                # For simplicity now, we'll let the user try sending again after setup status.
                if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
                     self.errorOccurred.emit("AI Assistant is not ready. Please wait or check settings.")
                     return
            else: # No API key, so setup won't work.
                self.errorOccurred.emit("AI Assistant is not ready (No API Key).")
                return
        
        # Diagram context still needs to be obtained by the manager from the main window.
        diagram_json_str = None
        if self.parent_window and hasattr(self.parent_window, 'scene'):
            try:
                diagram_data = self.parent_window.scene.get_diagram_data()
                diagram_json_str = json.dumps(diagram_data)
                print(f"--- MGR_SEND ({current_time}): Diagram context prepared (States: {len(diagram_data.get('states',[]))}). ---")
            except Exception as e:
                print(f"--- MGR_SEND ({current_time}): Error getting diagram data for worker: {e} ---")
                # Optionally pass an error placeholder or None
                diagram_json_str = json.dumps({"error": "Could not retrieve diagram context for AI."})
        
        # Pass the message AND diagram context to the worker's process_message method.
        # This requires ChatbotWorker.process_message to accept diagram_json_str
        # Option 1: Modify ChatbotWorker.process_message (PREFERRED)
        # QMetaObject.invokeMethod(self.chatbot_worker, "process_message", Qt.QueuedConnection,
        #                          Q_ARG(str, user_message_text),
        #                          Q_ARG(str, diagram_json_str if diagram_json_str else ""))
        # Option 2: (Less clean) set a property then call method
        # self.chatbot_worker.current_diagram_context = diagram_json_str
        # QMetaObject.invokeMethod(self.chatbot_worker, "process_message", Qt.QueuedConnection, Q_ARG(str, user_message_text))
        
        # Let's assume for now that `process_message` in `ChatbotWorker` is modified
        # to accept the diagram context, similar to how _prepare_messages_for_api did.
        # **THIS IS A CRITICAL MODIFICATION NEEDED IN ChatbotWorker**
        if hasattr(self.chatbot_worker, 'set_current_diagram_context'): # if using setter method
             self.chatbot_worker.set_current_diagram_context(diagram_json_str if diagram_json_str else "")
        
        QTimer.singleShot(0, lambda: self.chatbot_worker.process_message(user_message_text))
        print(f"--- MGR_SEND ({current_time}): process_message invoked on worker. ---")

    def clear_conversation_history(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR ({current_time}): clear_conversation_history called. ---")
        if self.chatbot_worker and self.chatbot_thread and self.chatbot_thread.isRunning():
            # self.chatbot_worker.clear_history() # Call directly if safe, or via invokeMethod
            QMetaObject.invokeMethod(self.chatbot_worker, "clear_history", Qt.QueuedConnection)
            print(f"--- MGR ({current_time}): clear_history invoked on worker. ---")
        else:
            self.statusUpdate.emit("Status: Chatbot not active to clear history.")

    def stop_chatbot(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_STOP ({current_time}): stop_chatbot CALLED. ---")
        self._cleanup_existing_worker_and_thread()
        print(f"--- MGR_STOP ({current_time}): Chatbot stopped and cleaned up. ---")