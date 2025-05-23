# ai_chatbot.py

import openai
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer # <--- ADD QTimer HERE
import os 

class ChatbotWorker(QObject):
    """
    Worker object to handle OpenAI API calls in a separate thread.
    """
    responseReady = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    statusUpdate = pyqtSignal(str)

    def __init__(self, api_key, model_name="gpt-4-turbo"):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        self.conversation_history = [] # To maintain context
        self._initialize_client() # Call helper to initialize client

    def _initialize_client(self):
        """Helper to initialize or re-initialize the OpenAI client."""
        if self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                print(f"OpenAI client initialized/re-initialized for model {self.model_name}.")
                # self.statusUpdate.emit("Status: OpenAI Client Ready.") # Optional status update
            except Exception as e:
                self.client = None
                print(f"Error initializing OpenAI client: {e}")
                # Defer emitting error until a send attempt, or if status is critical
                # self.errorOccurred.emit(f"Failed to initialize OpenAI client: {str(e)}")
        else:
            self.client = None
            print("OpenAI client not initialized (no API key).")

    def set_api_key(self, api_key):
        """Allows updating the API key and re-initializing the client."""
        self.api_key = api_key
        self._initialize_client()

    # ai_chatbot.py (ChatbotWorker class)

    def process_message(self, user_message: str):
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
                " When asked to generate an FSM, you MUST respond with ONLY a valid JSON object. "
                "The JSON should have 'states' and 'transitions' keys. "
                "States should be a list of objects, each with 'name' (string, required), "
                "'is_initial' (boolean, optional, default false), 'is_final' (boolean, optional, default false), "
                "'entry_action', 'during_action', 'exit_action' (strings, optional), "
                "and optionally a 'properties' object for things like 'color' (hex string e.g., '#RRGGBB'). "
                "Transitions should be a list of objects, each with 'source' (string, required state name), "
                "'target' (string, required state name), 'event', 'condition', 'action' (strings, optional). "
                "Optionally, include a 'description' (string) at the top level of the JSON for the FSM, and a 'comments' list "
                " (objects with 'text', 'x', 'y'). Do not include any other text, greetings, or explanations outside the JSON."
            )
        
        # Prepare messages for the API call (happens once)
        # Use a shorter history for generation requests if needed, or consistent history for all
        history_length_for_context = -6 if is_generation_request else -10 # Example: shorter context for strict JSON output
        
        # Always include the system prompt. The content of system_prompt_content changes based on request type.
        messages_for_api = [{"role": "system", "content": system_prompt_content}]
        
        # Add recent conversation history
        if self.conversation_history:
            messages_for_api.extend(self.conversation_history[history_length_for_context:])
            
        # Add the current user message
        messages_for_api.append({"role": "user", "content": user_message})

        try:
            chat_completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages_for_api,
                # For models like gpt-3.5-turbo-1106 or gpt-4-1106-preview and later:
                # if is_generation_request:
                #    response_format={"type": "json_object"} # This can greatly improve JSON reliability
            )
            ai_response_content = chat_completion.choices[0].message.content
            
            # Append current user message and AI response to conversation history *after* successful API call
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": ai_response_content})
            
            # Emit the raw content. MainWindow's _handle_ai_response will try to parse JSON
            # if it was an FSM generation request (it can know this by re-checking the original user_message,
            # or we can pass a flag, but re-checking user_message is simpler for now).
            self.responseReady.emit(ai_response_content) 
            
        except openai.APIConnectionError as e:
            self.errorOccurred.emit(f"API Connection Error: {e}")
        except openai.RateLimitError as e:
            self.errorOccurred.emit(f"Rate Limit Exceeded. Please check your OpenAI plan and usage. Details: {e}")
        except openai.AuthenticationError as e:
            self.errorOccurred.emit(f"Authentication Error: Invalid API Key? Details: {e}")
        except openai.APIError as e: 
            self.errorOccurred.emit(f"OpenAI API Error: {e}")
        except Exception as e:
            self.errorOccurred.emit(f"An unexpected error occurred with AI: {str(e)}")
        # No 'finally' to update status here, as responseReady or errorOccurred
        # will trigger the status update in the main thread via _handle_ai_response/_handle_ai_error
        # which then call _update_ai_chat_status.
        
        
        
        
    def clear_history(self):
        self.conversation_history = []
        print("Chatbot conversation history cleared by worker.")
        self.statusUpdate.emit("Status: Chat history cleared.")


class AIChatbotManager:
    def __init__(self, parent_window):
        self.parent_window = parent_window
        self.api_key = None
        self.chatbot_thread = QThread()
        self.chatbot_worker = None
        # Optionally load API key from environment or settings at init
        # self.set_api_key(os.getenv("OPENAI_API_KEY"))

    def set_api_key(self, api_key: str | None):
        print(f"--- MGR: set_api_key called. New key: '{'SET' if api_key else 'NONE'}' ---")
        self._cleanup_existing_worker_and_thread() # Always clean up before setting up anew
        
        self.api_key = api_key
        if self.api_key:
            self._setup_worker()
        else:
            if hasattr(self.parent_window, '_update_ai_chat_status'):
                self.parent_window._update_ai_chat_status("Status: API Key cleared. AI Assistant inactive.")

    def _setup_worker(self):
        if not self.api_key:
            print("--- MGR: Cannot setup worker - API key is not set. ---")
            if hasattr(self.parent_window, '_update_ai_chat_status'):
                 self.parent_window._update_ai_chat_status("Status: API Key required.")
            return

        print("--- MGR: Setting up new worker and thread ---")
        self.chatbot_thread = QThread() # Create a new thread instance
        self.chatbot_worker = ChatbotWorker(self.api_key)
        self.chatbot_worker.moveToThread(self.chatbot_thread)

        # Connect signals ONCE
        self.chatbot_worker.responseReady.connect(self.parent_window._handle_ai_response)
        self.chatbot_worker.errorOccurred.connect(self.parent_window._handle_ai_error)
        self.chatbot_worker.statusUpdate.connect(self.parent_window._update_ai_chat_status)
        print("--- MGR: Signals connected for new worker. ---")
        
        self.chatbot_thread.start()
        print("--- MGR: New AI Chatbot worker thread started. ---")
        if hasattr(self.parent_window, '_update_ai_chat_status'):
            self.parent_window._update_ai_chat_status("Status: AI Assistant Ready.")


    def send_message(self, user_message: str):
        print(f"--- MGR: send_message request for: '{user_message}' ---")
        if not self.api_key:
            print("--- MGR: No API Key in send_message ---")
            if hasattr(self.parent_window, '_handle_ai_error'):
                self.parent_window._handle_ai_error("API Key not set. Please configure in AI Assistant Settings.")
            return
        
        if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
            print("--- MGR: Worker/Thread not ready in send_message. Attempting to set up. ---")
            # This should ideally not happen often if set_api_key is the main entry for setup.
            # It indicates the API key might have been set, but worker setup failed or was cleared.
            self._setup_worker() 
            if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
                 print("--- MGR: Worker/Thread setup FAILED in send_message. ---")
                 if hasattr(self.parent_window, '_handle_ai_error'):
                    self.parent_window._handle_ai_error("Chatbot is not ready. Try setting API key again.")
                 return
        
        print(f"--- MGR: Queuing process_message for worker: '{user_message}' ---")
        QTimer.singleShot(0, lambda: self.chatbot_worker.process_message(user_message))

    def clear_conversation_history(self):
        if self.chatbot_worker and self.chatbot_thread.isRunning():
            QTimer.singleShot(0, lambda: self.chatbot_worker.clear_history())
            if hasattr(self.parent_window, 'ai_chat_display'):
                self.parent_window.ai_chat_display.clear() 
                self.parent_window.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
            # Worker will emit status update "Chat history cleared."
        elif hasattr(self.parent_window, '_update_ai_chat_status'):
            self.parent_window._update_ai_chat_status("Status: Chatbot not active to clear history.")


    def stop_chatbot(self):
        if self.chatbot_thread.isRunning():
            print("Requesting AI Chatbot worker thread to stop...")
            self.chatbot_thread.quit()
            if not self.chatbot_thread.wait(3000): # Wait 3 seconds
                print("Warning: AI Chatbot thread did not quit gracefully. Terminating...")
                self.chatbot_thread.terminate()
                self.chatbot_thread.wait() # Wait for termination
            print("AI Chatbot worker thread stopped.")
        self.chatbot_worker = None # Clean up worker reference