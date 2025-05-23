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

    def process_message(self, user_message: str):
        if not self.api_key or not self.client:
            self.errorOccurred.emit("OpenAI API key not set or client not initialized. Please set it in AI Assistant Settings.")
            self.statusUpdate.emit("Status: API Key required.") # Also update general status
            return

        self.statusUpdate.emit("Status: Thinking...")
        
        
        is_generation_request = "generate fsm" in user_message.lower() or \
                                 "create a state machine" in user_message.lower() or \
                                 "/generate_fsm" in user_message.lower() # Example command
                                 
        system_prompt_content = "You are a helpful assistant for designing Finite State Machines." 
        
        
        
        
        
        
        
                                
        
        
        current_conversation = [{"role": "system", "content": "You are a helpful assistant for designing Finite State Machines."}] 
        
        # Limit history length to keep requests manageable (e.g., last N turns or token count)
        # For simplicity, let's take last 10 messages (5 turns)
        history_to_send = self.conversation_history[-10:] 
        
        messages_to_send = current_conversation + history_to_send + [{"role": "user", "content": user_message}]

        try:
            chat_completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages_to_send 
            )
            ai_response = chat_completion.choices[0].message.content
            
            self.conversation_history.append({"role": "user", "content": user_message}) # Add user message *after* successful call for history
            self.conversation_history.append({"role": "assistant", "content": ai_response})
            
            self.responseReady.emit(ai_response)
            # Status will be updated by _handle_ai_response in MainWindow via _update_ai_chat_status
            
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
        # No finally here, as responseReady or errorOccurred will trigger status update in main thread

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

    def set_api_key(self, api_key: str | None): # Allow None to clear key
        self.api_key = api_key
        if self.chatbot_worker:
            # Inform worker about new key. Worker handles re-init of OpenAI client.
             QTimer.singleShot(0, lambda: self.chatbot_worker.set_api_key(self.api_key))
        elif self.api_key: # Only setup if key is provided and worker not yet created
            self._setup_worker()

    def _setup_worker(self):
        if not self.api_key:
            if hasattr(self.parent_window, '_update_ai_chat_status'):
                 self.parent_window._update_ai_chat_status("Status: API Key required.")
            return

        if self.chatbot_thread.isRunning(): # Clean up old thread if exists
             print("Stopping existing chatbot thread before new setup...")
             self.chatbot_thread.quit()
             self.chatbot_thread.wait(3000) # Wait up to 3 seconds
             if self.chatbot_thread.isRunning():
                 print("Warning: Old chatbot thread did not quit gracefully. Terminating.")
                 self.chatbot_thread.terminate() # Force terminate if necessary
                 self.chatbot_thread.wait()

        self.chatbot_worker = ChatbotWorker(self.api_key)
        self.chatbot_worker.moveToThread(self.chatbot_thread)

        self.chatbot_worker.responseReady.connect(self.parent_window._handle_ai_response)
        self.chatbot_worker.errorOccurred.connect(self.parent_window._handle_ai_error)
        self.chatbot_worker.statusUpdate.connect(self.parent_window._update_ai_chat_status)
        
        self.chatbot_thread.start()
        print("AI Chatbot worker thread started.")
        if hasattr(self.parent_window, '_update_ai_chat_status'):
            self.parent_window._update_ai_chat_status("Status: AI Assistant Ready.")


    def send_message(self, user_message: str):
        if not self.api_key:
            if hasattr(self.parent_window, '_handle_ai_error'):
                self.parent_window._handle_ai_error("API Key not set. Please configure in AI Assistant Settings.")
            return
        if not self.chatbot_worker or not self.chatbot_thread.isRunning():
            self._setup_worker() 
            if not self.chatbot_worker or not self.chatbot_thread.isRunning():
                 if hasattr(self.parent_window, '_handle_ai_error'):
                    self.parent_window._handle_ai_error("Chatbot is not ready. Try setting API key again.")
                 return
        
        # Ensure the method on the worker is called in its own thread
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