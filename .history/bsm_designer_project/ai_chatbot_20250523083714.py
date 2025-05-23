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


class AIChatbotManager:
    
    
    
    responseReceived = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    statusUpdate = pyqtSignal(str)
    
    
    def __init__(self, parent=None): # Ensure 'parent' is the parameter name here
        QObject.__init__(self, parent)
        super().__init__(parent) # Correctly pass parent to superclass
        self.parent_window = parent
        self.api_key = None
        self.conversation_history = []
        self.worker_thread = None
        self.worker = None
        self.base_system_message = "You are a helpful assistant for designing Finite State Machines."
        print(f"--- MGR ({QTime.currentTime().toString('hh:mm:ss.zzz')}): AIChatbotManager initialized. ---")
        




        



    def _cleanup_existing_worker_and_thread(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_CLEANUP ({current_time}): CALLED ---")
        
        if self.chatbot_thread and self.chatbot_thread.isRunning():
            print(f"--- MGR_CLEANUP ({current_time}): Attempting to quit existing thread... ---")
            self.chatbot_thread.quit()
            if not self.chatbot_thread.wait(3000):
                print(f"--- MGR_CLEANUP WARN ({current_time}): Thread did not quit gracefully. Terminating. ---")
                self.chatbot_thread.terminate()
                self.chatbot_thread.wait()
            print(f"--- MGR_CLEANUP ({current_time}): Existing thread stopped. ---")
        else:
            print(f"--- MGR_CLEANUP ({current_time}): No running thread to stop. ---")
        
        if self.chatbot_worker:
            print(f"--- MGR_CLEANUP ({current_time}): Scheduling old worker for deletion and disconnecting signals. ---")
            try:
                self.chatbot_worker.responseReady.disconnect(self.parent_window._handle_ai_response)
            except (TypeError, RuntimeError): pass # Already disconnected or object gone
            try:
                self.chatbot_worker.errorOccurred.disconnect(self.parent_window._handle_ai_error)
            except (TypeError, RuntimeError): pass
            try:
                self.chatbot_worker.statusUpdate.disconnect(self.parent_window._update_ai_chat_status)
            except (TypeError, RuntimeError): pass
            self.chatbot_worker.deleteLater()
        
        self.chatbot_thread = None
        self.chatbot_worker = None
        print(f"--- MGR_CLEANUP ({current_time}): Finished. ---")


    def set_api_key(self, api_key: str | None):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_SET_API_KEY ({current_time}): New key: '{'SET' if api_key else 'NONE'}' ---")
        self._cleanup_existing_worker_and_thread() 
        
        self.api_key = api_key
        
        
        if not api_key:
            self.statusUpdate.emit("Status: API Key required. Configure in Settings.")
        else:
            self.statusUpdate.emit("Status: Ready. API Key set.")
        
        
        if self.api_key:
            self._setup_worker()
        else:
            if hasattr(self.parent_window, '_update_ai_chat_status'):
                self.parent_window._update_ai_chat_status("Status: API Key cleared. AI Assistant inactive.")
                
                
                
        def _prepare_messages_for_api(self, user_message_text: str, diagram_data_json: str = None):
            """
        Prepares the list of messages for the API call, including system prompt,
        diagram context (if provided), and conversation history.
        """
        messages = []

        # 1. System Message with Diagram Context
        system_message_content = self.base_system_message
        if diagram_data_json:
            # Keep context concise to manage token count.
            # For this phase, let's send a simplified summary or just presence.
            # In a more advanced phase, you'd send more detailed (but still token-aware) data.
            try:
                diagram = json.loads(diagram_data_json)
                state_names = [s.get('name', 'UnnamedState') for s in diagram.get('states', [])]
                num_transitions = len(diagram.get('transitions', []))
                if state_names:
                    context_summary = (
                        f" The current diagram has states: {', '.join(state_names[:5])}"
                        f"{' and others' if len(state_names) > 5 else ''}."
                        f" It has {num_transitions} transition(s)."
                    )
                    system_message_content += context_summary
                else:
                    system_message_content += " The current diagram is empty."

            except json.JSONDecodeError:
                system_message_content += " (Error reading diagram context)."
        
        messages.append({"role": "system", "content": system_message_content})

        # 2. Conversation History (simplified for brevity here, keep your existing logic)
        # Ensure history doesn't grow too large. You might need to truncate.
        for entry in self.conversation_history[-10:]: # Example: last 10 exchanges
            messages.append(entry)

        # 3. Current User Message
        messages.append({"role": "user", "content": user_message_text})
        return messages                
                
                
                
                        
                
                
                
                
                
                

    def _setup_worker(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        if not self.api_key:
            print(f"--- MGR_SETUP_WORKER ({current_time}): Cannot setup - API key is not set. ---")
            if hasattr(self.parent_window, '_update_ai_chat_status'):
                 self.parent_window._update_ai_chat_status("Status: API Key required.")
            return

        print(f"--- MGR_SETUP_WORKER ({current_time}): Setting up new worker and thread. ---")
        self.chatbot_thread = QThread(self.parent_window) # Parent QThread for proper cleanup
        self.chatbot_worker = ChatbotWorker(self.api_key)
        self.chatbot_worker.moveToThread(self.chatbot_thread)

        self.chatbot_worker.responseReady.connect(self.parent_window._handle_ai_response)
        self.chatbot_worker.errorOccurred.connect(self.parent_window._handle_ai_error)
        self.chatbot_worker.statusUpdate.connect(self.parent_window._update_ai_chat_status)
        print(f"--- MGR_SETUP_WORKER ({current_time}): Signals connected. Starting thread. ---")
        
        self.chatbot_thread.start()
        print(f"--- MGR_SETUP_WORKER ({current_time}): New AI Chatbot worker thread started. ---")
        if hasattr(self.parent_window, '_update_ai_chat_status'): # Update MainWindow status
            QTimer.singleShot(0, lambda: self.parent_window._update_ai_chat_status("Status: AI Assistant Ready."))


    def send_message(self, user_message_text: str):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_SEND ({current_time}): send_message called with: '{user_message_text[:30]}...' ---")

        if not self.api_key:
            print(f"--- MGR_SEND ({current_time}): No API Key. Emitting error. ---")
            self.errorOccurred.emit("API Key not set. Please configure it in Settings.")
            # No need to emit statusUpdate here as set_api_key already handles "API Key required" status
            return

        if self.worker_thread and self.worker_thread.isRunning():
            print(f"--- MGR_SEND ({current_time}): Worker busy. Emitting error. ---")
            self.errorOccurred.emit("AI Assistant is currently busy. Please wait.")
            # Status might be "Thinking..." from MainWindow already, so an additional one isn't strictly needed
            return
        
        self.statusUpdate.emit("Status: Sending message to AI...") # Inform MainWindow that we're starting

        # Get diagram data from MainWindow's scene
        diagram_json_str = None
        if self.parent_window and hasattr(self.parent_window, 'scene'):
            try:
                diagram_data = self.parent_window.scene.get_diagram_data()
                diagram_json_str = json.dumps(diagram_data) # Convert dict to JSON string for _prepare_messages_for_api
                print(f"--- MGR_SEND ({current_time}): Diagram context prepared (States: {len(diagram_data.get('states',[]))}). ---")
            except Exception as e:
                print(f"--- MGR_SEND ({current_time}): Error getting diagram data: {e} ---")
                diagram_json_str = json.dumps({"error": "Could not retrieve diagram data."})


        prepared_messages = self._prepare_messages_for_api(user_message_text, diagram_json_str)
        
        print(f"--- MGR_SEND ({current_time}): Messages for API: {prepared_messages} ---")

        self.worker = OpenAIWorker(self.api_key, prepared_messages)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker.responseReady.connect(self._handle_worker_response)
        self.worker.errorReady.connect(self._handle_worker_error)
        self.worker_thread.started.connect(self.worker.run)
        
        # Clean up
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()
        print(f"--- MGR_SEND ({current_time}): Worker thread started. ---")
        # The status will be updated to "Thinking..." by MainWindow after this call
        # based on MainWindow's _on_send_ai_chat_message setting its UI elements.
        
        
        
        
    def _handle_worker_response(self, response_text: str):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_HANDLE_RESP ({current_time}): Worker response received. Length: {len(response_text)} ---")
        if response_text:
            # Add AI response to conversation history
            self.conversation_history.append({"role": "assistant", "content": response_text})
            self.responseReceived.emit(response_text)
            # Status will be updated by MainWindow after processing the response
        else:
            self.errorOccurred.emit("Received an empty response from AI.")
        
        if self.worker_thread and self.worker_thread.isRunning(): # Ensure thread is still valid
             print(f"--- MGR_HANDLE_RESP ({current_time}): Worker thread will be quit. ---")
        # else:
        #      print(f"--- MGR_HANDLE_RESP ({current_time}): Worker thread already quit or None. ---")
        
        
        
        
        
    def _handle_worker_error(self, error_msg: str):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_HANDLE_ERR ({current_time}): Worker error: '{error_msg}' ---")
        self.errorOccurred.emit(error_msg)
        if self.worker_thread and self.worker_thread.isRunning():
             print(f"--- MGR_HANDLE_ERR ({current_time}): Worker thread will be quit due to error. ---")
        # else:
        #     print(f"--- MGR_HANDLE_ERR ({current_time}): Worker thread already quit or None for error. ---")            
        
        
        


    def clear_conversation_history(self):
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR ({current_time}): clear_conversation_history called. ---")
        if self.chatbot_worker and self.chatbot_thread and self.chatbot_thread.isRunning():
            QTimer.singleShot(0, lambda: self.chatbot_worker.clear_history())
            # GUI display clear is handled in MainWindow.on_clear_ai_chat_history
        elif hasattr(self.parent_window, '_update_ai_chat_status'):
            self.parent_window._update_ai_chat_status("Status: Chatbot not active to clear history.")

    def stop_chatbot(self): # Ensure graceful shutdown of thread if running
        current_time = QTime.currentTime().toString('hh:mm:ss.zzz')
        print(f"--- MGR_STOP ({current_time}): stop_chatbot called. ---")
        if self.worker_thread and self.worker_thread.isRunning():
            print(f"--- MGR_STOP ({current_time}): Requesting worker thread to quit. ---")
            self.worker_thread.quit()
            self.worker_thread.wait(2000) # Wait up to 2 seconds for graceful termination
            if self.worker_thread.isRunning(): # Force terminate if still running
                print(f"--- MGR_STOP ({current_time}): Worker thread still running, terminating. ---")
                self.worker_thread.terminate()
                self.worker_thread.wait()
            print(f"--- MGR_STOP ({current_time}): Worker thread stopped. ---")
        self.worker = None
        self.worker_thread = None