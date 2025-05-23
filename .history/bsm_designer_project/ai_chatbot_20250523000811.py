# ai_chatbot.py

import openai
from PyQt5.QtCore import QObject, pyqtSignal, QThread
import os # For environment variables if you use them for API key

class ChatbotWorker(QObject):
    """
    Worker object to handle OpenAI API calls in a separate thread.
    """
    responseReady = pyqtSignal(str)  # Signal to send AI's response back to main thread
    errorOccurred = pyqtSignal(str)  # Signal for errors
    statusUpdate = pyqtSignal(str)   # Signal for status updates like "Thinking..."

    def __init__(self, api_key, model_name="gpt-3.5-turbo"):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        if self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
            except Exception as e:
                # This might happen if API key format is immediately invalid or other init issues
                print(f"Error initializing OpenAI client: {e}") 
                # Note: self.errorOccurred cannot be emitted directly from __init__ 
                # if it's meant for a different thread context until moveToThread is called.
                # It's better to check client validity before making calls.

        self.conversation_history = [] # To maintain context

    def set_api_key(self, api_key):
        """Allows updating the API key and re-initializing the client."""
        self.api_key = api_key
        if self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                print("OpenAI client re-initialized with new API key.")
            except Exception as e:
                self.client = None
                print(f"Error re-initializing OpenAI client: {e}")
                self.errorOccurred.emit(f"Failed to initialize OpenAI with new key: {str(e)}")
        else:
            self.client = None
            print("OpenAI client cleared (no API key).")


    def process_message(self, user_message: str):
        if not self.api_key or not self.client:
            self.errorOccurred.emit("OpenAI API key not set or client not initialized.")
            return

        self.statusUpdate.emit("Thinking...")
        
        # Add user message to history (adjust role as needed by OpenAI API for "user")
        self.conversation_history.append({"role": "user", "content": user_message})

        try:
            # Make the API call
            # Use a system message for initial instructions if desired
            messages_to_send = [{"role": "system", "content": "You are a helpful assistant."}] + self.conversation_history

            chat_completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages_to_send 
            )
            
            ai_response = chat_completion.choices[0].message.content
            
            # Add AI response to history
            self.conversation_history.append({"role": "assistant", "content": ai_response})
            
            self.responseReady.emit(ai_response)
            self.statusUpdate.emit("Ready.") # Or clear status
            
        except openai.APIConnectionError as e:
            self.errorOccurred.emit(f"API Connection Error: {e}")
        except openai.RateLimitError as e:
            self.errorOccurred.emit(f"Rate Limit Exceeded: {e}")
        except openai.AuthenticationError as e:
            self.errorOccurred.emit(f"Authentication Error: Invalid API Key? {e}")
        except openai.APIError as e: # Generic OpenAI API error
            self.errorOccurred.emit(f"OpenAI API Error: {e}")
        except Exception as e:
            # Catch any other unexpected errors
            self.errorOccurred.emit(f"An unexpected error occurred: {str(e)}")
        finally:
            # Ensure status is updated even if an error occurs before responseReady
            if not self.statusUpdate.emit("Ready."): # Check if thinking was set
                self.statusUpdate.emit("Error occurred.")


    def clear_history(self):
        self.conversation_history = []
        print("Chatbot conversation history cleared.")


class AIChatbotManager:
    """
    Manages the ChatbotWorker and its thread.
    This class will be instantiated in the MainWindow.
    """
    def __init__(self, parent_window): # parent_window for emitting signals to GUI slots
        self.parent_window = parent_window # Keep a reference if needed for signals
        self.api_key = None # Set via set_api_key from MainWindow

        self.chatbot_thread = QThread()
        self.chatbot_worker = None # Will be created once API key is set
        
        # Get API key from environment variable as a fallback or primary source
        # self.set_api_key(os.getenv("OPENAI_API_KEY")) # Optional: Load at init


    def set_api_key(self, api_key: str):
        self.api_key = api_key
        if self.chatbot_worker:
            self.chatbot_worker.set_api_key(self.api_key)
        else:
            self._setup_worker() # Setup worker if API key is set for the first time

    def _setup_worker(self):
        if not self.api_key:
            # print("Cannot setup chatbot worker: API key is not set.")
            if hasattr(self.parent_window, 'ai_chat_status_label'): # Update GUI status if available
                 self.parent_window.ai_chat_status_label.setText("Status: API Key required.")
            return

        if self.chatbot_worker and self.chatbot_thread.isRunning():
            # If worker exists and thread is running, it might be an update of key.
            # The set_api_key on worker handles re-initialization.
            print("Chatbot worker already exists, API key updated if necessary.")
            return
        
        if self.chatbot_thread.isRunning():
             self.chatbot_thread.quit()
             self.chatbot_thread.wait() # Wait for thread to finish cleanly

        self.chatbot_worker = ChatbotWorker(self.api_key)
        self.chatbot_worker.moveToThread(self.chatbot_thread)

        # Connect worker signals to MainWindow slots
        self.chatbot_worker.responseReady.connect(self.parent_window._handle_ai_response)
        self.chatbot_worker.errorOccurred.connect(self.parent_window._handle_ai_error)
        self.chatbot_worker.statusUpdate.connect(self.parent_window._update_ai_chat_status)
        
        self.chatbot_thread.start()
        print("AI Chatbot worker thread started.")


    def send_message(self, user_message: str):
        if not self.chatbot_worker or not self.chatbot_thread.isRunning():
            self._setup_worker() # Try to set up if not already
            if not self.chatbot_worker or not self.chatbot_thread.isRunning(): # If still not setup
                 if hasattr(self.parent_window, '_handle_ai_error'):
                    self.parent_window._handle_ai_error("Chatbot is not ready. Check API key and settings.")
                 else:
                    print("Error: Chatbot is not ready. Check API key and settings.")
                 return
        
        # Call process_message on the worker (will run in the worker's thread)
        # Need a way to pass the message to the worker thread.
        # QMetaObject.invokeMethod can be used, or a custom signal from manager to worker.
        # For simplicity here, we'll add a signal on the worker to trigger processing
        # or rely on a direct method call that will be queued if worker is in a different thread
        # QMetaObject.invokeMethod(self.chatbot_worker, "process_message", Qt.QueuedConnection, Q_ARG(str, user_message))
        
        # Let's refine: ChatbotWorker should have a slot to receive the message
        # So we connect a signal from the manager (or directly from GUI) to that slot
        # For now, a direct call. Qt handles cross-thread method invocation with QueuedConnection 
        # for QObject methods if moveToThread was used and thread is running.
        if hasattr(self.chatbot_worker, 'process_message'):
            # This will be queued and executed in the worker's thread
            QTimer.singleShot(0, lambda: self.chatbot_worker.process_message(user_message)) 
        else:
            self.parent_window._handle_ai_error("Chatbot worker not configured correctly.")


    def clear_conversation_history(self):
        if self.chatbot_worker:
            # self.chatbot_worker.clear_history() # Direct call ok if worker manages its own data
            # Or if history needs to be cleared from a different thread:
            QTimer.singleShot(0, lambda: self.chatbot_worker.clear_history())
            if hasattr(self.parent_window, 'ai_chat_display') and hasattr(self.parent_window.ai_chat_display, 'clear'):
                self.parent_window.ai_chat_display.clear() # Also clear GUI display
                self.parent_window.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
            self.parent_window._update_ai_chat_status("Conversation history cleared.")


    def stop_chatbot(self):
        if self.chatbot_thread.isRunning():
            self.chatbot_thread.quit()
            self.chatbot_thread.wait() # Wait for the thread to finish
            print("AI Chatbot worker thread stopped.")