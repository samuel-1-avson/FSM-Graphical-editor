# bsm_designer_project/ai_chatbot.py

from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTime, QTimer, Qt, QMetaObject, pyqtSlot, Q_ARG
import json
import re
import logging
from enum import Enum, auto
import html # For AIChatUIManager

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold # For safety settings
import google.api_core.exceptions # For Gemini API exceptions
from PyQt5.QtGui import QMovie, QIcon, QColor # Add QMovie for potential animation
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QLineEdit, QPushButton, QLabel, QStyle, QMessageBox, QInputDialog

from config import (
    APP_FONT_SIZE_SMALL, COLOR_BACKGROUND_MEDIUM, COLOR_ACCENT_WARNING,
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_SECONDARY, COLOR_TEXT_PRIMARY,
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_ACCENT_ERROR, COLOR_TEXT_SECONDARY,
    COLOR_BACKGROUND_EDITOR_DARK, COLOR_TEXT_EDITOR_DARK_PRIMARY, COLOR_BORDER_LIGHT,
    COLOR_TEXT_ON_ACCENT, COLOR_ACCENT_SUCCESS, COLOR_BACKGROUND_DIALOG
)
from utils import get_standard_icon


logger = logging.getLogger(__name__)

class AIStatus(Enum):
    INITIALIZING = auto()
    READY = auto()
    THINKING = auto()
    API_KEY_REQUIRED = auto()
    API_KEY_ERROR = auto() # Specific error for bad key
    OFFLINE = auto()
    ERROR = auto() # General error
    INACTIVE = auto() # User/system deliberately made it inactive
    HISTORY_CLEARED = auto()

class ChatbotWorker(QObject):
    responseReady = pyqtSignal(str, bool)
    errorOccurred = pyqtSignal(str) # Emits a string for the error message
    statusUpdate = pyqtSignal(AIStatus, str) # Emits (AIStatus Enum, status_string)

    def __init__(self, api_key, model_name="gemini-1.5-flash-latest", parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.model_name = model_name
        self.client: genai.GenerativeModel | None = None
        self.conversation_history = []
        self.current_diagram_context_json_str: str | None = None
        self._current_processing_had_error = False
        self._is_stopped = False
        self._initialize_client()
        logger.info(f"ChatbotWorker initialized (Gemini API Key {'SET' if api_key else 'NOT SET'}).")

    def _initialize_client(self):
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
                self.client = genai.GenerativeModel(self.model_name, safety_settings=safety_settings)
                logger.info(f"Gemini client initialized for model {self.model_name}.")
            except Exception as e:
                self.client = None
                error_msg = f"Failed to initialize Gemini client: {e}"
                logger.error(error_msg, exc_info=True)
                # Let the caller (e.g., set_api_key_slot or process_message_slot) emit the status/error
        else:
            self.client = None
            logger.info("Gemini client not initialized (no API key).")

    @pyqtSlot(str)
    def set_api_key_slot(self, api_key: str):
        logger.info(f"WORKER: set_api_key_slot called (new key {'SET' if api_key else 'NOT SET'}).")
        self.api_key = api_key
        old_client_state = bool(self.client)
        self._initialize_client()
        new_client_state = bool(self.client)

        if not self.api_key:
            self.statusUpdate.emit(AIStatus.API_KEY_REQUIRED, "Status: API Key cleared. AI Assistant inactive.")
        elif new_client_state and not old_client_state: # Successfully initialized a new client
             self.statusUpdate.emit(AIStatus.READY, "Status: API Key set and AI Assistant ready.")
        elif not new_client_state: # Failed to initialize client with new key
            self.errorOccurred.emit("Failed to initialize Gemini client with the new API key.") # Emits string
            self.statusUpdate.emit(AIStatus.API_KEY_ERROR, "Status: API Key Error.")
        # If client state didn't change (e.g., re-confirming a working key), no status update needed here.

    @pyqtSlot(str)
    def set_diagram_context_slot(self, diagram_json_str: str):
        if not diagram_json_str:
            logger.debug(f"WORKER: Setting diagram context to None (received empty string).")
            self.current_diagram_context_json_str = None
        else:
            logger.debug(f"WORKER: Setting diagram context. Length: {len(diagram_json_str)}")
            self.current_diagram_context_json_str = diagram_json_str

    @pyqtSlot(str, bool)
    def process_message_slot(self, user_message: str, force_fsm_generation: bool):
        if self._is_stopped:
            logger.info("WORKER_PROCESS: Worker is stopped, ignoring message.")
            return

        logger.info(f"WORKER_PROCESS: process_message_slot CALLED for: '{user_message[:50]}...' (force_fsm_generation={force_fsm_generation})")
        self._current_processing_had_error = False

        if not self.api_key:
            error_msg = "Gemini API key not set. Please set it in AI Assistant Settings."
            logger.warning("process_message: %s", error_msg)
            self.errorOccurred.emit(error_msg) # Emits string
            self.statusUpdate.emit(AIStatus.API_KEY_REQUIRED, "Status: API Key required.")
            self._current_processing_had_error = True
            return
        
        if not self.client:
            error_msg = "Gemini client not initialized. This might be due to an invalid API key or a network issue during initialization."
            logger.warning("process_message: %s", error_msg)
            self.errorOccurred.emit(error_msg) # Emits string
            self.statusUpdate.emit(AIStatus.API_KEY_ERROR, "Status: API Client Error.") 
            self._current_processing_had_error = True
            return

        if self._is_stopped:
            logger.info("WORKER_PROCESS: Worker stopped before API call.")
            return

        self.statusUpdate.emit(AIStatus.THINKING, "Status: Thinking...")

        is_fsm_generation_attempt = False
        if force_fsm_generation:
            is_fsm_generation_attempt = True
        else:
            keywords_for_generation = [
                "generate fsm", "create fsm", "generate an fsm model",
                "generate state machine", "create state machine", "design state machine",
                "model fsm", "model state machine",
                "draw fsm", "draw state machine", "make an fsm", "fsm design for",
                "/generate_fsm"
            ]
            user_msg_lower = user_message.lower()
            is_fsm_generation_attempt = any(re.search(r'\b' + re.escape(keyword) + r'\b', user_msg_lower) for keyword in keywords_for_generation)

        is_embedded_code_request = False
        if not is_fsm_generation_attempt:
            embedded_keywords = [
                "arduino", "raspberry pi", "rpi", "esp32", "stm32",
                "microcontroller", "embedded c", "gpio", "pwm", "adc",
                "i2c", "spi", "sensor code", "actuator code", "mechatronics code",
                "robotics code", "control system code", "firmware snippet"
            ]
            user_msg_lower_for_embedded = user_message.lower()
            if any(re.search(r'\b' + re.escape(keyword) + r'\b', user_msg_lower_for_embedded) for keyword in embedded_keywords):
                is_embedded_code_request = True
                logger.debug(f"WORKER_PROCESS: Detected embedded code request keywords in '{user_message[:50]}...'")

        logger.debug(f"WORKER_PROCESS: is_fsm_generation_attempt = {is_fsm_generation_attempt} for '{user_message[:50]}...'")

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
                logger.warning("WORKER_PROCESS_CTX_ERROR: JSONDecodeError processing diagram context.", exc_info=True)
                system_prompt_content += " (Error reading diagram context in worker)."
            except Exception as e_ctx:
                logger.error(f"WORKER_PROCESS_CTX_ERROR: Error processing diagram context: {e_ctx}", exc_info=True)
                system_prompt_content += " (Issue with diagram context string)."
        else:
             system_prompt_content += " No diagram context was provided for this request."

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
            if is_embedded_code_request:
                system_prompt_content += (
                    " You are also an expert assistant for mechatronics and embedded systems programming. "
                    "If the user asks for Arduino code, structure it with `void setup() {}` and `void loop() {}`. "
                    "If for Raspberry Pi, provide Python code, using `RPi.GPIO` for GPIO tasks if appropriate, or other common libraries like `smbus` for I2C. "
                    "For other microcontrollers like ESP32 or STM32, provide C/C++ code in a typical embedded style (e.g., using Arduino framework for ESP32 if common, or HAL/LL for STM32 if specified). "
                    "Provide clear, well-commented code snippets. "
                    "If including explanations, clearly separate the code block using markdown (e.g., ```c or ```python or ```cpp). "
                    "Focus on the specific request and aim for functional, copy-pasteable code where possible. "
                    "For general mechatronics algorithms (e.g., PID, kinematics), pseudocode or Python is often suitable unless a specific language is requested."
                )
            else:
                 system_prompt_content += " For general conversation, provide helpful and concise answers."

        # --- Start: Corrected API Content Construction ---
        api_contents = []

        # 1. Add System Prompt and a dummy model response to ensure role alternation
        if system_prompt_content:
            api_contents.append({"role": "user", "parts": [{"text": system_prompt_content}]})
            api_contents.append({"role": "model", "parts": [{"text": "Understood. I will follow these instructions carefully."}]})

        # 2. Add Conversation History
        # self.conversation_history is assumed to be already in alternating user/model roles.
        history_context_limit = -6 # Max 3 user/model message pairs
        if self.conversation_history:
            for msg in self.conversation_history[history_context_limit:]:
                if isinstance(msg, dict) and "role" in msg and "parts" in msg:
                    # Ensure history roles are valid and append
                    if msg["role"] in ["user", "model"]:
                        # Critical check for alternation with the last item in api_contents
                        if api_contents and api_contents[-1]["role"] == msg["role"]:
                            logger.warning(f"Correcting role sequence: inserting dummy opposite role before history message: {msg['parts'][0]['text'][:30]}...")
                            # Insert a dummy message of the opposite role
                            dummy_role = "model" if msg["role"] == "user" else "user"
                            api_contents.append({"role": dummy_role, "parts": [{"text": "Okay."}]})
                        api_contents.append(msg)
                    else:
                        logger.warning(f"Skipping malformed history message with invalid role: {msg.get('role')}")
                else:
                    logger.warning(f"Skipping malformed history message: {msg}")
        
        # 3. Add Current User Message
        # Ensure current user message follows a "model" role if api_contents is not empty
        if api_contents and api_contents[-1]["role"] == "user":
            logger.warning("Correcting role sequence: last message was 'user', adding dummy model ack before current user message.")
            api_contents.append({"role": "model", "parts": [{"text": "Acknowledged."}]})
        
        api_contents.append({"role": "user", "parts": [{"text": user_message}]})
        # --- End: Corrected API Content Construction ---
        
        generation_config = genai.types.GenerationConfig(
            temperature=0.7,
        )
        if is_fsm_generation_attempt:
            generation_config.response_mime_type = "application/json"
            logger.info("WORKER_PROCESS: Requesting JSON object format from Gemini.")

        try:
            if self._is_stopped:
                logger.info("WORKER_PROCESS: Worker stopped just before creating completion.")
                return
            
            generation_args = {
                "contents": api_contents, # Use the correctly constructed api_contents
                "generation_config": generation_config,
            }
            
            logger.debug(f"WORKER_PROCESS: Sending to Gemini. Contents (first part text len, role):")
            for i, item_content in enumerate(api_contents): # Log the final contents for debugging
                first_part_text = item_content.get("parts", [{}])[0].get("text", "")
                preview = first_part_text[:80].replace('\n', ' ') + ('...' if len(first_part_text) > 80 else '')
                logger.debug(f"  Part {i}: Role '{item_content.get('role', 'N/A')}', Text Len: {len(first_part_text)}, Preview: '{preview}'")

            response = self.client.generate_content(**generation_args)

            if self._is_stopped:
                logger.info("WORKER_PROCESS: Worker stopped during/after API call, discarding response.")
                return

            ai_response_content = ""
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                ai_response_content = response.candidates[0].content.parts[0].text
            elif hasattr(response, 'text'): # Fallback for older/different response structures
                ai_response_content = response.text
            else:
                feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "No feedback."
                finish_reason = response.candidates[0].finish_reason if response.candidates else "Unknown reason."
                error_msg = f"Gemini response was empty or blocked. Finish Reason: {finish_reason}. Feedback: {feedback}"
                logger.error(error_msg)
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    block_reason_msg = getattr(response.prompt_feedback, 'block_reason_message', None) # Safe access
                    if block_reason_msg: error_msg += f" Block Reason Message: {block_reason_msg}"
                    for rating in response.prompt_feedback.safety_ratings:
                        if rating.blocked:
                             error_msg += f" Safety Blocked: Category {rating.category}, Probability {rating.probability.name}"
                self.errorOccurred.emit(error_msg) # Emits string
                self._current_processing_had_error = True
                self.statusUpdate.emit(AIStatus.ERROR, f"Status: Error - {error_msg[:50]}...")
                return

            # Add original user message and AI response to history
            # Ensure we use the original user_message, not one potentially modified with system prompt
            self.conversation_history.append({"role": "user", "parts": [{"text": user_message}]})
            self.conversation_history.append({"role": "model", "parts": [{"text": ai_response_content}]})
            logger.debug("WORKER_PROCESS: AI response received and added to history.")
            self.responseReady.emit(ai_response_content, is_fsm_generation_attempt)

        except google.api_core.exceptions.ServiceUnavailable as e:
            err_str = f"API Connection Error: {str(e)[:200]}"
            logger.error("Gemini API Connection/Service Error: %s", err_str, exc_info=True)
            self.errorOccurred.emit(err_str) # Emits string
            self.statusUpdate.emit(AIStatus.OFFLINE, "Status: Offline/Connection Error.")
            self._current_processing_had_error = True
        except google.api_core.exceptions.ResourceExhausted as e:
            err_str = f"Rate Limit Exceeded: {str(e)[:200]}"
            logger.error("Gemini Rate Limit Exceeded: %s", err_str, exc_info=True)
            self.errorOccurred.emit(err_str) # Emits string
            self.statusUpdate.emit(AIStatus.ERROR, "Status: Rate Limit Exceeded.")
            self._current_processing_had_error = True
        except (google.api_core.exceptions.PermissionDenied, google.auth.exceptions.RefreshError, google.auth.exceptions.DefaultCredentialsError) as e:
            err_str = f"Authentication Error (Invalid API Key?): {str(e)[:200]}"
            logger.error("Gemini Authentication/Permission Error: %s", err_str, exc_info=True)
            self.errorOccurred.emit(err_str) # Emits string
            self.statusUpdate.emit(AIStatus.API_KEY_ERROR, "Status: API Key Error.")
            self._current_processing_had_error = True
        except google.api_core.exceptions.GoogleAPIError as e: 
            error_detail = str(e)
            if hasattr(e, 'message') and e.message: error_detail = e.message
            err_str = f"Google API Error: {type(e).__name__} - {error_detail[:250]}"
            logger.error("Gemini API Error: %s - %s", type(e).__name__, error_detail[:250], exc_info=True)
            self.errorOccurred.emit(err_str) # Emits string
            self.statusUpdate.emit(AIStatus.ERROR, f"Status: API Error - {type(e).__name__}.")
            self._current_processing_had_error = True
        except (genai.types.BlockedPromptException, genai.types.StopCandidateException) as e: 
            error_msg = f"Gemini content generation blocked or stopped: {e}"
            logger.error("WORKER_PROCESS: %s", error_msg, exc_info=True)
            self.errorOccurred.emit(error_msg) # Emits string
            self.statusUpdate.emit(AIStatus.ERROR, "Status: Content Blocked.")
            self._current_processing_had_error = True
        except Exception as e:
            error_msg = f"Unexpected error in AI worker: {type(e).__name__} - {str(e)[:150]}"
            logger.error("WORKER_PROCESS: %s", error_msg, exc_info=True)
            self.errorOccurred.emit(error_msg) # Emits string
            self.statusUpdate.emit(AIStatus.ERROR, "Status: Unexpected Error.")
            self._current_processing_had_error = True
        finally:
            if not self._current_processing_had_error and self.client and not self._is_stopped:
                self.statusUpdate.emit(AIStatus.READY, "Status: Ready.")

    @pyqtSlot()
    def clear_history_slot(self):
        self.conversation_history = []
        logger.info("Conversation history cleared.")
        self.statusUpdate.emit(AIStatus.HISTORY_CLEARED, "Status: Chat history cleared.")

    @pyqtSlot()
    def stop_processing_slot(self):
        logger.info("WORKER: stop_processing_slot called.")
        self._is_stopped = True


class AIChatUIManager(QObject):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window

        self.ai_chat_display: QTextEdit = None
        self.ai_chat_input: QLineEdit = None
        self.ai_chat_send_button: QPushButton = None
        self.ai_chat_status_label: QLabel = None
        self.original_send_button_icon: QIcon = None
        self.thinking_spinner_movie: QMovie | None = None

        self._connect_actions_to_manager_slots()
        self._connect_ai_chatbot_signals()

    def _connect_actions_to_manager_slots(self):
        logger.debug("AIChatUI: Connecting actions to manager slots...")
        if hasattr(self.mw, 'ask_ai_to_generate_fsm_action'):
            self.mw.ask_ai_to_generate_fsm_action.triggered.connect(self.on_ask_ai_to_generate_fsm)
        if hasattr(self.mw, 'openai_settings_action'): # Retained name for now, though it's Gemini
            self.mw.openai_settings_action.triggered.connect(self.on_gemini_settings)
        if hasattr(self.mw, 'clear_ai_chat_action'):
            self.mw.clear_ai_chat_action.triggered.connect(self.on_clear_ai_chat_history)

    def _connect_ai_chatbot_signals(self):
        if self.mw.ai_chatbot_manager:
            # The manager's statusUpdate now emits (AIStatus, str)
            self.mw.ai_chatbot_manager.statusUpdate.connect(self.update_status_display)
            self.mw.ai_chatbot_manager.errorOccurred.connect(self.handle_ai_error) # Still expects string
            self.mw.ai_chatbot_manager.fsmDataReceived.connect(self.handle_fsm_data_from_ai)
            self.mw.ai_chatbot_manager.plainResponseReady.connect(self.handle_plain_ai_response)

    def create_dock_widget_contents(self) -> QWidget:
        ai_chat_widget = QWidget()
        ai_chat_layout = QVBoxLayout(ai_chat_widget)
        ai_chat_layout.setContentsMargins(5,5,5,5); ai_chat_layout.setSpacing(5)

        self.ai_chat_display = QTextEdit(); self.ai_chat_display.setReadOnly(True)
        self.ai_chat_display.setObjectName("AIChatDisplay"); 
        self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
        ai_chat_layout.addWidget(self.ai_chat_display, 1)

        input_layout = QHBoxLayout()
        self.ai_chat_input = QLineEdit(); self.ai_chat_input.setObjectName("AIChatInput")
        self.ai_chat_input.setPlaceholderText("Type your message to the AI...")
        self.ai_chat_input.returnPressed.connect(self.on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_input, 1)

        self.ai_chat_send_button = QPushButton()
        self.original_send_button_icon = get_standard_icon(QStyle.SP_ArrowRight, "SndAI")
        self.ai_chat_send_button.setIcon(self.original_send_button_icon)

        self.ai_chat_send_button.setObjectName("AIChatSendButton")
        self.ai_chat_send_button.setToolTip("Send message to AI")
        self.ai_chat_send_button.setFixedWidth(40) 
        self.ai_chat_send_button.clicked.connect(self.on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_send_button)
        ai_chat_layout.addLayout(input_layout)

        self.ai_chat_status_label = QLabel("Status: Initializing...")
        self.ai_chat_status_label.setObjectName("AIChatStatusLabel")
        ai_chat_layout.addWidget(self.ai_chat_status_label)
        
        # Initial status is set by AIChatbotManager based on API key and network status.
        return ai_chat_widget

    @pyqtSlot(AIStatus, str)
    def update_status_display(self, status_enum: AIStatus, status_text: str):
        if not self.ai_chat_status_label: return
        self.ai_chat_status_label.setText(status_text)
        
        base_style = f"font-size: {APP_FONT_SIZE_SMALL}; padding: 2px 4px; border-radius: 3px;"
        can_send_message = False
        is_thinking_ui = False

        if status_enum in [AIStatus.API_KEY_REQUIRED, AIStatus.API_KEY_ERROR, AIStatus.INACTIVE]:
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: white; background-color: {COLOR_ACCENT_ERROR}; font-weight: bold;")
        elif status_enum == AIStatus.OFFLINE:
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: {COLOR_TEXT_PRIMARY}; background-color: {COLOR_ACCENT_WARNING};")
        elif status_enum == AIStatus.ERROR:
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: white; background-color: {COLOR_ACCENT_ERROR}; font-weight: bold;")
        elif status_enum == AIStatus.THINKING or status_enum == AIStatus.INITIALIZING:
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: {COLOR_TEXT_PRIMARY}; background-color: {QColor(COLOR_ACCENT_SECONDARY).lighter(130).name()}; font-style: italic;")
            is_thinking_ui = True
        elif status_enum == AIStatus.READY:
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: white; background-color: {COLOR_ACCENT_SUCCESS};")
            can_send_message = True
        elif status_enum == AIStatus.HISTORY_CLEARED:
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: {COLOR_TEXT_SECONDARY}; background-color: {QColor(COLOR_BACKGROUND_MEDIUM).lighter(105).name()};")
            # After history clear, if API key is present and client is good, it's Ready.
            if self.mw.ai_chatbot_manager and self.mw.ai_chatbot_manager.api_key and \
               self.mw.ai_chatbot_manager.chatbot_worker and self.mw.ai_chatbot_manager.chatbot_worker.client:
                can_send_message = True # It should be ready to send.
                # Manager should emit READY status after HISTORY_CLEARED if appropriate.
        else: 
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: {COLOR_TEXT_SECONDARY}; background-color: {COLOR_BACKGROUND_MEDIUM};")
       
        if self.ai_chat_send_button:
            self.ai_chat_send_button.setEnabled(can_send_message)
            if is_thinking_ui:
                self.ai_chat_send_button.setText("...") 
                self.ai_chat_send_button.setIcon(QIcon()) 
            else:
                self.ai_chat_send_button.setText("") 
                self.ai_chat_send_button.setIcon(self.original_send_button_icon)

        if self.ai_chat_input:
            self.ai_chat_input.setEnabled(can_send_message)
            if can_send_message and self.mw and hasattr(self.mw, 'ai_chatbot_dock') and self.mw.ai_chatbot_dock and self.mw.ai_chatbot_dock.isVisible() and self.mw.isActiveWindow():
                self.ai_chat_input.setFocus()

        if hasattr(self.mw, 'ask_ai_to_generate_fsm_action'):
            self.mw.ask_ai_to_generate_fsm_action.setEnabled(can_send_message)

    def _format_code_block(self, code_content: str) -> str:
        bg_color = COLOR_BACKGROUND_EDITOR_DARK
        text_color = COLOR_TEXT_EDITOR_DARK_PRIMARY
        border_color = QColor(bg_color).lighter(130).name()
        
        escaped_code = html.escape(code_content)
        return (f'<div style="margin: 5px 0; padding: 8px; background-color:{bg_color}; color:{text_color}; '
                f'border:1px solid {border_color}; border-radius:4px; font-family: Consolas, monospace; white-space:pre-wrap; overflow-x:auto;">'
                f'{escaped_code}</div>')

    def _append_to_chat_display(self, sender: str, message: str):
        if not self.ai_chat_display: return
        timestamp = QTime.currentTime().toString('hh:mm:ss')

        sender_color = COLOR_ACCENT_PRIMARY
        sender_name_raw = sender 
        if sender == "You":
            sender_color = COLOR_ACCENT_SECONDARY
        elif sender == "System Error":
            sender_color = COLOR_ACCENT_ERROR
            sender_name_raw = f"<b>{html.escape(sender)}</b>" 
        elif sender == "System":
            sender_color = QColor(COLOR_TEXT_SECONDARY)
        
        sender_color_str = sender_color.name() if isinstance(sender_color, QColor) else sender_color
        sender_name_html = sender_name_raw if sender in ["System Error"] else html.escape(sender)

        processed_message_html_parts = []
        code_block_regex = re.compile(r'```([a-zA-Z0-9_+#.-]*)\s*\n(.*?)\n```', flags=re.DOTALL | re.MULTILINE)
        last_index = 0

        for match in code_block_regex.finditer(message):
            text_before = message[last_index:match.start()]
            if text_before:
                part_html = text_before
                part_html = part_html.replace("<strong>", "_एसटीआरओएनजी_एसटीएआरटि_").replace("</strong>", "_एसटीआरओएनजी_ईएनडी_")
                part_html = part_html.replace("<em>", "_ईएम_एसटीएआरटि_").replace("</em>", "_ईएम_ईएनडी_")
                part_html = part_html.replace("<code>", "_सीओडीई_आईएनएलआईएनई_एसटीएआरटि_").replace("</code>", "_सीओडीई_आईएनएलआईएनई_ईएनडी_")

                part_html = re.sub(r'\*\*(.*?)\*\*', r'_एसटीआरओएनजी_एसटीएआरटि_\1_एसटीआरओएनजी_ईएनडी_', part_html, flags=re.DOTALL)
                part_html = re.sub(r'(?<![*\w])\*([^* \n][^*]*?)\*(?![*\w])', r'_ईएम_एसटीएआरटि_\1_ईएम_ईएनडी_', part_html, flags=re.DOTALL)
                part_html = re.sub(r'`(.*?)`', r'_सीओडीई_आईएनएलआईएनई_एसटीएआरटि_\1_सीओडीई_आईएनएलआईएनई_ईएनडी_', part_html, flags=re.DOTALL)
                
                part_html_escaped = html.escape(part_html).replace("\n", "<br>")
                
                part_html_escaped = part_html_escaped.replace(html.escape("_एसटीआरओएनजी_एसटीएआरटि_"), "<strong>").replace(html.escape("_एसटीआरओएनजी_ईएनडी_"), "</strong>")
                part_html_escaped = part_html_escaped.replace(html.escape("_ईएम_एसटीएआरटि_"), "<em>").replace(html.escape("_ईएम_ईएनडी_"), "</em>")
                inline_code_style = "background-color:#E0E0E0; color:#3F51B5; padding:1px 4px; border-radius:3px; font-family:Consolas,monospace;"
                part_html_escaped = part_html_escaped.replace(html.escape("_सीओडीई_आईएनएलआईएनई_एसटीएआरटि_"), f"<code style='{inline_code_style}'>").replace(html.escape("_सीओडीई_आईएनएलआईएनई_ईएनडी_"), "</code>")
                
                processed_message_html_parts.append(part_html_escaped)

            code_content = match.group(2).strip('\n') 
            processed_message_html_parts.append(self._format_code_block(code_content))
            last_index = match.end()

        text_after = message[last_index:]
        if text_after:
            part_html = text_after
            part_html = part_html.replace("<strong>", "_एसटीआरओएनजी_एसटीएआरटि_").replace("</strong>", "_एसटीआरओएनजी_ईएनडी_")
            part_html = part_html.replace("<em>", "_ईएम_एसटीएआरटि_").replace("</em>", "_ईएम_ईएनडी_")
            part_html = part_html.replace("<code>", "_सीओडीई_आईएनएलआईएनई_एसटीएआरटि_").replace("</code>", "_सीओडीई_आईएनएलआईएनई_ईएनडी_")

            part_html = re.sub(r'\*\*(.*?)\*\*', r'_एसटीआरओएनजी_एसटीएआरटि_\1_एसटीआरओएनजी_ईएनडी_', part_html, flags=re.DOTALL)
            part_html = re.sub(r'(?<![*\w])\*([^* \n][^*]*?)\*(?![*\w])', r'_ईएम_एसटीएआरटि_\1_ईएम_ईएनडी_', part_html, flags=re.DOTALL)
            part_html = re.sub(r'`(.*?)`', r'_सीओडीई_आईएनएलआईएनई_एसटीएआरटि_\1_सीओडीई_आईएनएलआईएनई_ईएनडी_', part_html, flags=re.DOTALL)
            
            part_html_escaped = html.escape(part_html).replace("\n", "<br>")

            part_html_escaped = part_html_escaped.replace(html.escape("_एसटीआरओएनजी_एसटीएआरटि_"), "<strong>").replace(html.escape("_एसटीआरओएनजी_ईएनडी_"), "</strong>")
            part_html_escaped = part_html_escaped.replace(html.escape("_ईएम_एसटीएआरटि_"), "<em>").replace(html.escape("_ईएम_ईएनडी_"), "</em>")
            inline_code_style = "background-color:#E0E0E0; color:#3F51B5; padding:1px 4px; border-radius:3px; font-family:Consolas,monospace;"
            part_html_escaped = part_html_escaped.replace(html.escape("_सीओडीई_आईएनएलआईएनई_एसटीएआरटि_"), f"<code style='{inline_code_style}'>").replace(html.escape("_सीओडीई_आईएनएलआईएनई_ईएनडी_"), "</code>")

            processed_message_html_parts.append(part_html_escaped)

        final_message_html = "".join(processed_message_html_parts)

        bg_msg_color = QColor(sender_color_str).lighter(185).name()
        if sender == "System Error": bg_msg_color = QColor(COLOR_ACCENT_ERROR).lighter(180).name()
        elif sender == "System": bg_msg_color = QColor(COLOR_BACKGROUND_MEDIUM).lighter(105).name()

        html_to_append = (f"<div style='margin-bottom: 10px; padding: 5px; border-left: 3px solid {sender_color_str}; background-color: {bg_msg_color}; border-radius: 3px;'>"
                          f"<span style='font-size:8pt; color:{COLOR_TEXT_SECONDARY};'>[{timestamp}]</span> "
                          f"<strong style='color:{sender_color_str};'>{sender_name_html}:</strong>"
                          f"<div style='margin-top: 4px; padding-left: 2px; line-height:1.4;'>{final_message_html}</div></div>")
        
        self.ai_chat_display.append(html_to_append)
        self.ai_chat_display.ensureCursorVisible()

    @pyqtSlot(str)
    def handle_ai_error(self, error_message: str):
        self._append_to_chat_display("System Error", error_message)
        logger.error("AIChatUI: AI Chatbot Error: %s", error_message)
        # The status display update will now come from the manager's statusUpdate signal
        # which should emit an AIStatus.ERROR enum along with a descriptive text.

    @pyqtSlot(dict, str)
    def handle_fsm_data_from_ai(self, fsm_data: dict, source_message: str):
        logger.info("AIChatUI: Received FSM data. Source: '%s...'", source_message[:30])
        self._append_to_chat_display("AI", f"Received FSM structure. (Source: {source_message[:30]}...) Adding to diagram.")
        if not fsm_data or (not fsm_data.get('states') and not fsm_data.get('transitions')):
            logger.error("AIChatUI: AI returned empty or invalid FSM data.")
            self._append_to_chat_display("System", "AI did not return a valid FSM structure to draw.")
            # Manager should emit an ERROR status if this occurs
            if self.mw.ai_chatbot_manager:
                 self.mw.ai_chatbot_manager._update_current_ai_status(AIStatus.ERROR, "Status: AI returned no FSM data.")
            return

        msg_box = QMessageBox(self.mw); msg_box.setIcon(QMessageBox.Question); msg_box.setWindowTitle("Add AI Generated FSM")
        msg_box.setText("AI has generated an FSM. Do you want to clear the current diagram before adding the new FSM, or add to the existing one?")
        clear_btn = msg_box.addButton("Clear and Add", QMessageBox.YesRole)
        add_btn = msg_box.addButton("Add to Existing", QMessageBox.NoRole)
        cancel_btn = msg_box.addButton("Cancel", QMessageBox.RejectRole); msg_box.setDefaultButton(cancel_btn)
        msg_box.exec()
        
        clicked_button = msg_box.clickedButton()
        if clicked_button == cancel_btn: 
            logger.info("AIChatUI: User cancelled adding AI FSM.")
            if self.mw.ai_chatbot_manager:
                self.mw.ai_chatbot_manager._update_current_ai_status(AIStatus.READY, "Status: FSM generation cancelled.")
            return
        
        clear_current = (clicked_button == clear_btn)
        self.mw._add_fsm_data_to_scene(fsm_data, clear_current_diagram=clear_current, original_user_prompt=source_message)
        # Status should be READY after this, manager's worker:finally block will typically set this.
        # self.update_status_display(AIStatus.READY, "Status: FSM added to diagram.") # Or let worker handle
        logger.info("AIChatUI: FSM data from AI processed and added to scene.")

    @pyqtSlot(str)
    def handle_plain_ai_response(self, ai_message: str):
        logger.info("AIChatUI: Received plain AI response.")
        self._append_to_chat_display("AI", ai_message)
        # Status update (to READY) should come from the worker's finally block.
        # if self.mw.ai_chatbot_manager and self.mw.ai_chatbot_manager.get_current_ai_status() == AIStatus.THINKING:
        #     self.update_status_display(AIStatus.READY, "Status: Ready.")

    @pyqtSlot()
    def on_send_ai_chat_message(self):
        if not self.ai_chat_input or not self.ai_chat_send_button.isEnabled(): return
        message = self.ai_chat_input.text().strip()
        if not message: return
        self.ai_chat_input.clear(); self._append_to_chat_display("You", message)
        if self.mw.ai_chatbot_manager:
            self.mw.ai_chatbot_manager.send_message(message)
            # Status update (THINKING) will come from manager/worker
        else:
            self.handle_ai_error("AI Chatbot Manager not initialized.")

    @pyqtSlot()
    def on_ask_ai_to_generate_fsm(self):
        logger.info("AIChatUI: on_ask_ai_to_generate_fsm CALLED!")
        description, ok = QInputDialog.getMultiLineText(self.mw, "Generate FSM", "Describe the FSM you want to create:", "Example: A traffic light with states Red, Yellow, Green...")
        if ok and description.strip():
            logger.info("AIChatUI: Sending FSM desc: '%s...'", description[:50])
            if self.mw.ai_chatbot_manager:
                self.mw.ai_chatbot_manager.generate_fsm_from_description(description)
                self._append_to_chat_display("You", f"Generate an FSM: {description}")
                # Status update (THINKING) will come from manager/worker
            else:
                self.handle_ai_error("AI Chatbot Manager not initialized.")
        elif ok: QMessageBox.warning(self.mw, "Empty Description", "Please provide a description for the FSM.")

    @pyqtSlot()
    def on_gemini_settings(self): 
        logger.info("AIChatUI: on_gemini_settings CALLED!")
        if not self.mw.ai_chatbot_manager:
            logger.warning("AIChatUI: AI Chatbot Manager not available for settings.")
            QMessageBox.warning(self.mw, "AI Error", "AI Chatbot Manager is not initialized. Cannot open settings.")
            return

        current_key = self.mw.ai_chatbot_manager.api_key or ""
        key, ok = QInputDialog.getText(
            self.mw,
            "Google AI API Key (Gemini)", 
            "Enter your Google AI API Key for Gemini (leave blank to clear):", 
            QLineEdit.PasswordEchoOnEdit, 
            current_key
        )
        if ok:
            new_key_value = key.strip()
            logger.info(f"AIChatUI: Google AI API Key dialog returned. OK: {ok}, Key: {'SET' if new_key_value else 'EMPTY'}")
            self.mw.ai_chatbot_manager.set_api_key(new_key_value if new_key_value else None)
            # Status update (API_KEY_REQUIRED or READY/API_KEY_ERROR) will come from manager
        else:
            logger.debug("AIChatUI: Google AI API Key dialog cancelled by user.")

    @pyqtSlot()
    def on_clear_ai_chat_history(self):
        logger.info("AIChatUI: on_clear_ai_chat_history CALLED!")
        if self.mw.ai_chatbot_manager:
            reply = QMessageBox.question(self.mw, "Clear Chat History",
                                         "Are you sure you want to clear the entire AI chat history?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.mw.ai_chatbot_manager.clear_conversation_history() # Manager emits HISTORY_CLEARED
                if self.ai_chat_display:
                    self.ai_chat_display.clear()
                    self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
                logger.info("AIChatUI: Chat history cleared by user.")
                self._append_to_chat_display("System", "Chat history cleared.")
            else:
                logger.info("AIChatUI: User cancelled clearing chat history.")
        else:
            self.handle_ai_error("AI Chatbot Manager not initialized.")

class AIChatbotManager(QObject):
    statusUpdate = pyqtSignal(AIStatus, str) # Emits (AIStatus Enum, status_string)
    errorOccurred = pyqtSignal(str) # Emits string for error details
    fsmDataReceived = pyqtSignal(dict, str)
    plainResponseReady = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.api_key: str | None = None
        self.chatbot_worker: ChatbotWorker | None = None
        self.chatbot_thread: QThread | None = None
        self.last_fsm_request_description: str | None = None
        logger.info("AIChatbotManager initialized.")
        self._current_ai_status = AIStatus.INITIALIZING # Internal tracking

    def _update_current_ai_status(self, new_status_enum: AIStatus, status_text: str):
        # This method is the single point for emitting statusUpdate from the manager
        self._current_ai_status = new_status_enum
        self.statusUpdate.emit(new_status_enum, status_text)
        logger.debug(f"MGR_STATUS_UPDATE: Enum={new_status_enum.name}, Text='{status_text}'")


    def get_current_ai_status(self) -> AIStatus:
        return self._current_ai_status

    def _cleanup_existing_worker_and_thread(self):
        logger.debug("MGR_CLEANUP: CALLED.")
        if self.chatbot_thread and self.chatbot_thread.isRunning():
            logger.debug("MGR_CLEANUP: Attempting to quit existing thread...")
            if self.chatbot_worker:
                # Ensure stop_processing_slot is invoked before quitting the thread
                QMetaObject.invokeMethod(self.chatbot_worker, "stop_processing_slot", Qt.BlockingQueuedConnection if QThread.currentThread() != self.chatbot_thread else Qt.DirectConnection)
                logger.debug("MGR_CLEANUP: stop_processing_slot invoked on worker.")

            self.chatbot_thread.quit()
            if not self.chatbot_thread.wait(300): # Increased wait time slightly
                logger.warning("MGR_CLEANUP: Thread did not quit gracefully. Terminating.")
                self.chatbot_thread.terminate()
                self.chatbot_thread.wait(200)
            logger.debug("MGR_CLEANUP: Existing thread stopped.")
        self.chatbot_thread = None

        if self.chatbot_worker:
            logger.debug("MGR_CLEANUP: Disconnecting signals and scheduling old worker for deletion.")
            try: self.chatbot_worker.responseReady.disconnect(self._handle_worker_response)
            except (TypeError, RuntimeError): pass
            try: self.chatbot_worker.errorOccurred.disconnect(self.errorOccurred) # errorOccurred still emits string
            except (TypeError, RuntimeError): pass
            try: self.chatbot_worker.statusUpdate.disconnect(self._update_current_ai_status) # Connect worker's statusUpdate to manager's method
            except (TypeError, RuntimeError): pass
            self.chatbot_worker.deleteLater() # Schedule for deletion by the event loop of its thread
            logger.debug("MGR_CLEANUP: Old worker scheduled for deletion.")
        self.chatbot_worker = None
        logger.debug("MGR_CLEANUP: Finished. Worker and thread are None.")


    def set_api_key(self, api_key: str | None):
        old_key_status = 'SET' if self.api_key else 'NONE'
        new_key_status = 'SET' if api_key else 'NONE'
        logger.info(f"MGR_SET_API_KEY (Gemini): New key: '{new_key_status}', Old key: '{old_key_status}'")

        old_api_key_val = self.api_key
        self.api_key = api_key

        if old_api_key_val != self.api_key or \
           (self.api_key and (not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning())):
            self._cleanup_existing_worker_and_thread() 
            if self.api_key:
                self._setup_worker() 
                # Worker's _initialize_client (called from set_api_key_slot) will emit status via its own statusUpdate
            else:
                self._update_current_ai_status(AIStatus.API_KEY_REQUIRED, "Status: Gemini API Key cleared. AI Assistant inactive.")
        elif self.chatbot_worker and self.api_key and self.chatbot_thread and self.chatbot_thread.isRunning():
             QMetaObject.invokeMethod(self.chatbot_worker, "set_api_key_slot", Qt.QueuedConnection,
                                      Q_ARG(str, self.api_key))
             # Worker's set_api_key_slot will re-initialize and potentially emit new status.
             # If successful, it might emit READY.
             # If it was already ready and key is same, it might not emit anything from worker,
             # so we can confirm here if the key seems fine.
             if self.chatbot_worker.client: # Check if client is still valid after call
                 self._update_current_ai_status(AIStatus.READY, "Status: Ready. Gemini API Key re-confirmed.")
             else: # Client became invalid, worker should have emitted API_KEY_ERROR or similar.
                 # The worker's set_api_key_slot should handle emitting the API_KEY_ERROR status.
                 pass 
        elif not self.api_key: 
            self._update_current_ai_status(AIStatus.API_KEY_REQUIRED, "Status: Gemini API Key required.")


    def _setup_worker(self):
        if not self.api_key:
            logger.warning("MGR_SETUP_WORKER: Cannot setup - API key is not set.")
            self._update_current_ai_status(AIStatus.API_KEY_REQUIRED, "Status: API Key required.")
            return

        if self.chatbot_worker or (self.chatbot_thread and self.chatbot_thread.isRunning()):
            logger.info("MGR_SETUP_WORKER: Worker/thread exists or is running. Cleaning up first.")
            self._cleanup_existing_worker_and_thread()

        logger.info("MGR_SETUP_WORKER: Setting up new worker and thread.")
        self.chatbot_thread = QThread(self) 
        self.chatbot_worker = ChatbotWorker(self.api_key)
        self.chatbot_worker.moveToThread(self.chatbot_thread)

        self.chatbot_worker.responseReady.connect(self._handle_worker_response)
        self.chatbot_worker.errorOccurred.connect(self.errorOccurred) # Still emits string
        self.chatbot_worker.statusUpdate.connect(self._update_current_ai_status) # Connect to manager's status handler

        self.chatbot_thread.start()
        logger.info("MGR_SETUP_WORKER: New AI Chatbot worker thread started.")
        self._update_current_ai_status(AIStatus.INITIALIZING, "Status: AI Assistant Initializing...")
        # Explicitly tell worker to initialize its client with the current key,
        # which will then emit its own status (READY or API_KEY_ERROR).
        QMetaObject.invokeMethod(self.chatbot_worker, "set_api_key_slot", Qt.QueuedConnection,
                                      Q_ARG(str, self.api_key))


    @pyqtSlot(str, bool)
    def _handle_worker_response(self, ai_response_content: str, was_fsm_generation_attempt: bool):
        logger.info(f"MGR_HANDLE_WORKER_RESPONSE: Received from worker. Was FSM attempt: {was_fsm_generation_attempt}")

        if was_fsm_generation_attempt:
            try:
                # Use regex to find the JSON block, allowing for optional language specifier
                # and being more flexible with surrounding text/whitespace.
                match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", ai_response_content, re.DOTALL | re.IGNORECASE)
                if match:
                    cleaned_json_str = match.group(1)
                    logger.debug("MGR_HANDLE_WORKER_RESPONSE: Extracted JSON via regex.")
                else:
                    # If regex fails, try a more direct parse attempt (if no ``` at all)
                    # or assume it's not FSM JSON if it has ``` but not the pattern.
                    if "```" not in ai_response_content:
                        logger.debug("MGR_HANDLE_WORKER_RESPONSE: No ```json``` block found, trying to parse directly.")
                        cleaned_json_str = ai_response_content.strip()
                    else: # Has ``` but not the expected JSON block pattern
                        logger.warning("MGR_HANDLE_WORKER_RESPONSE: Markdown ``` found, but not a recognized JSON block. Treating as plain text.")
                        raise json.JSONDecodeError("Markdown ``` found, but not a recognized JSON block.", ai_response_content, 0)

                fsm_data = json.loads(cleaned_json_str) 
                if isinstance(fsm_data, dict) and ('states' in fsm_data or 'transitions' in fsm_data):
                    logger.info("MGR_HANDLE_WORKER_RESPONSE: Parsed FSM JSON successfully. Emitting fsmDataReceived.")
                    source_desc = self.last_fsm_request_description or "AI Generated FSM"
                    self.fsmDataReceived.emit(fsm_data, source_desc)
                    # Status should be Ready now, handled by worker's finally block.
                    return 
                else:
                    logger.warning("MGR_HANDLE_WORKER_RESPONSE: JSON parsed but not valid FSM structure. Treating as plain text.")
                    self.errorOccurred.emit("AI returned JSON, but it's not a valid FSM structure. Displaying as text.")
                    self._update_current_ai_status(AIStatus.ERROR, "Status: Invalid FSM JSON from AI.")
                    # Fall through to plainResponseReady to display the malformed JSON as text.
            except json.JSONDecodeError:
                logger.warning("MGR_HANDLE_WORKER_RESPONSE: Failed to parse AI response as JSON. Treating as plain text.", exc_info=True)
                self._update_current_ai_status(AIStatus.ERROR, "Status: AI response was not valid FSM JSON.")
                self.errorOccurred.emit(f"AI response for FSM generation was not valid JSON. Raw response (see chat for full):\n{ai_response_content[:200]}...")
                # Fall through to plainResponseReady to display the non-JSON response.

        # If not FSM attempt, or if FSM attempt parsing failed and we want to show the raw response
        logger.debug("MGR_HANDLE_WORKER_RESPONSE: Emitting plainResponseReady.")
        self.plainResponseReady.emit(ai_response_content)
        # Worker's finally block should set to Ready if no error.


    def _prepare_and_send_to_worker(self, user_message_text: str, is_fsm_gen_specific: bool = False):
        logger.info(f"MGR_PREP_SEND: For: '{user_message_text[:30]}...', FSM_specific_req: {is_fsm_gen_specific}")

        if not self.api_key:
            logger.warning("MGR_PREP_SEND: API Key not set.")
            self.errorOccurred.emit("Gemini API Key not set. Configure in Settings.") # Emits string
            self._update_current_ai_status(AIStatus.API_KEY_REQUIRED, "Status: API Key required.")
            if self.parent_window and hasattr(self.parent_window, 'ai_chat_ui_manager') and self.parent_window.ai_chat_ui_manager:
                self.parent_window.ai_chat_ui_manager._append_to_chat_display("System Error", "API Key not set.")
            return

        if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
            logger.warning("MGR_PREP_SEND: Worker/Thread not ready.")
            if self.api_key and (not self.chatbot_thread or not self.chatbot_thread.isRunning()):
                 logger.info("MGR_PREP_SEND: Attempting to re-setup worker because it's not running.")
                 self._setup_worker() # This will setup and start the thread.

            if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
                err_msg = "AI Assistant is not ready. Please wait or check settings."
                self.errorOccurred.emit(err_msg) # Emits string
                self._update_current_ai_status(AIStatus.ERROR, "Status: AI Assistant Not Ready.")
                if self.parent_window and hasattr(self.parent_window, 'ai_chat_ui_manager') and self.parent_window.ai_chat_ui_manager:
                    self.parent_window.ai_chat_ui_manager._append_to_chat_display("System Error", err_msg)
                return

        if is_fsm_gen_specific:
            self.last_fsm_request_description = user_message_text
        else:
            self.last_fsm_request_description = None

        diagram_json_str: str | None = None
        if self.parent_window and hasattr(self.parent_window, 'scene') and hasattr(self.parent_window.scene, 'get_diagram_data'):
            try:
                diagram_data = self.parent_window.scene.get_diagram_data()
                lean_diagram_data = {
                    "states": [{"name": s.get("name"), "is_initial": s.get("is_initial"), "is_final": s.get("is_final")} 
                               for s in diagram_data.get("states", [])],
                    "transitions": [{"source": t.get("source"), "target": t.get("target"), "event": t.get("event")}
                                    for t in diagram_data.get("transitions", [])]
                }
                diagram_json_str = json.dumps(lean_diagram_data)
                logger.debug(f"MGR_PREP_SEND: Lean diagram context (first 100 chars): {diagram_json_str[:100]}")
            except Exception as e:
                logger.error(f"MGR_PREP_SEND: Error getting/processing diagram data: {e}", exc_info=True)
                diagram_json_str = json.dumps({"error": "Could not retrieve diagram context."})
        else:
             diagram_json_str = json.dumps({"error": "Diagram context unavailable."})

        if self.chatbot_worker:
            effective_diagram_json_str = diagram_json_str if diagram_json_str is not None else ""
            # Ensure worker is on its thread for these calls
            QMetaObject.invokeMethod(self.chatbot_worker, "set_diagram_context_slot", Qt.QueuedConnection,
                                     Q_ARG(str, effective_diagram_json_str))
            QMetaObject.invokeMethod(self.chatbot_worker, "process_message_slot", Qt.QueuedConnection,
                                     Q_ARG(str, user_message_text),
                                     Q_ARG(bool, is_fsm_gen_specific))
            logger.debug("MGR_PREP_SEND: Methods queued for worker.")
            # Worker will emit THINKING status
        else:
            logger.error("MGR_PREP_SEND: Chatbot worker is None, cannot queue methods.")
            err_msg = "AI Assistant encountered an internal error (worker missing). Please try restarting AI features."
            self.errorOccurred.emit(err_msg) # Emits string
            self._update_current_ai_status(AIStatus.ERROR, "Status: Internal Error (Worker Missing).")

    def send_message(self, user_message_text: str):
        self._prepare_and_send_to_worker(user_message_text, is_fsm_gen_specific=False)

    def generate_fsm_from_description(self, description: str):
         self._prepare_and_send_to_worker(description, is_fsm_gen_specific=True)

    def clear_conversation_history(self):
        logger.info("MGR: clear_conversation_history CALLED.")
        if self.chatbot_worker and self.chatbot_thread and self.chatbot_thread.isRunning():
            QMetaObject.invokeMethod(self.chatbot_worker, "clear_history_slot", Qt.QueuedConnection)
            # Worker will emit HISTORY_CLEARED status, which manager will then relay.
            logger.debug("MGR: clear_history invoked on worker.")
        else:
            # If worker not running, there's no history in worker to clear. Local history is cleared by worker init.
            # If no API key, it's API_KEY_REQUIRED.
            if not self.api_key:
                self._update_current_ai_status(AIStatus.API_KEY_REQUIRED, "Status: API Key required. Chat inactive.")
            else: # Worker might be stopped for other reasons
                self._update_current_ai_status(AIStatus.INACTIVE, "Status: Chatbot not active.")
            logger.warning("MGR: Chatbot not active, cannot clear history from worker.")


    def stop_chatbot(self):
        logger.info("MGR_STOP: stop_chatbot CALLED.")
        self._cleanup_existing_worker_and_thread()
        self._update_current_ai_status(AIStatus.INACTIVE, "Status: AI Assistant Stopped.")
        logger.info("MGR_STOP: Chatbot stopped and cleaned up.")

    def set_online_status(self, is_online: bool):
        logger.info(f"MGR_NET_STATUS: Online status: {is_online}")
        if not self.api_key:
            if is_online:
                self._update_current_ai_status(AIStatus.API_KEY_REQUIRED, "Status: Online, Gemini API Key required.")
            else:
                self._update_current_ai_status(AIStatus.OFFLINE, "Status: Offline, Gemini API Key required.")
            return

        # API Key IS present
        if is_online:
            if not self.chatbot_thread or not self.chatbot_thread.isRunning():
                logger.info("MGR_NET_STATUS: Network online, API key present, attempting worker setup.")
                self._setup_worker() # This will emit INITIALIZING, then worker emits READY/ERROR
            else: # Thread is running
                if self.chatbot_worker and self.chatbot_worker.client:
                    # Worker seems fine, ensure status reflects online and ready
                    self._update_current_ai_status(AIStatus.READY, "Status: Online and Ready.")
                elif self.chatbot_worker and not self.chatbot_worker.client:
                    # Worker exists but client is bad (e.g. API key error from previous attempt)
                    self._update_current_ai_status(AIStatus.API_KEY_ERROR, "Status: Online, API Key Error.")
                else: # Worker not fully instantiated or in an unexpected state
                    self._update_current_ai_status(AIStatus.INITIALIZING, "Status: Online, Initializing...")
        else: # Offline, but API key is present
            self._update_current_ai_status(AIStatus.OFFLINE, "Status: Offline. Gemini AI features unavailable.")