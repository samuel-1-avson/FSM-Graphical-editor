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
    API_KEY_ERROR = auto()
    OFFLINE = auto()
    ERROR = auto()
    INACTIVE = auto()
    HISTORY_CLEARED = auto()
    CONTENT_BLOCKED = auto()
    RATE_LIMIT = auto()
    CONNECTION_ERROR = auto()
    AUTHENTICATION_ERROR = auto()

class ChatbotWorker(QObject):
    responseReady = pyqtSignal(str, bool)
    errorOccurred = pyqtSignal(AIStatus, str)
    statusUpdate = pyqtSignal(AIStatus, str)

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
                logger.error(f"Failed to initialize Gemini client: {e}", exc_info=True)
        else:
            self.client = None
            logger.info("Gemini client not initialized (no API key).")

    @pyqtSlot(str)
    def set_api_key_slot(self, api_key: str):
        logger.info(f"WORKER: set_api_key_slot called (new key {'SET' if api_key else 'NOT SET'}).")
        self.api_key = api_key
        self._initialize_client()

        if not self.api_key:
            self.statusUpdate.emit(AIStatus.API_KEY_REQUIRED, "Status: API Key cleared. AI Assistant inactive.")
        elif self.client:
             self.statusUpdate.emit(AIStatus.READY, "Status: API Key set and AI Assistant ready.")
        else:
            self.errorOccurred.emit(AIStatus.API_KEY_ERROR, "Failed to initialize Gemini client with the new API key.")
            self.statusUpdate.emit(AIStatus.API_KEY_ERROR, "Status: API Key Error.")

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
            self.errorOccurred.emit(AIStatus.API_KEY_REQUIRED, error_msg)
            self.statusUpdate.emit(AIStatus.API_KEY_REQUIRED, "Status: API Key required.")
            self._current_processing_had_error = True
            return

        if not self.client:
            error_msg = "Gemini client not initialized. This might be due to an invalid API key or a network issue during initialization."
            logger.warning("process_message: %s", error_msg)
            self.errorOccurred.emit(AIStatus.API_KEY_ERROR, error_msg)
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

        api_contents = []
        if system_prompt_content:
            api_contents.append({"role": "user", "parts": [{"text": system_prompt_content}]})
            api_contents.append({"role": "model", "parts": [{"text": "Understood. I will follow these instructions carefully."}]})

        history_context_limit = -6 # Send last 3 user/model pairs (6 messages)
        if self.conversation_history:
            for msg in self.conversation_history[history_context_limit:]:
                if isinstance(msg, dict) and "role" in msg and "parts" in msg:
                    if msg["role"] in ["user", "model"]:
                        # Gemini API requires alternating user/model roles.
                        # If the last appended message has the same role as the current one,
                        # insert a dummy message to ensure alternation.
                        if api_contents and api_contents[-1]["role"] == msg["role"]:
                            dummy_role = "model" if msg["role"] == "user" else "user"
                            api_contents.append({"role": dummy_role, "parts": [{"text": "Okay."}]}) # Dummy content
                        api_contents.append(msg)
                    else:
                        logger.warning(f"Skipping malformed history message with invalid role: {msg.get('role')}")
                else:
                    logger.warning(f"Skipping malformed history message: {msg}")

        # Ensure the last message before the new user message is from 'model'
        if api_contents and api_contents[-1]["role"] == "user":
            api_contents.append({"role": "model", "parts": [{"text": "Acknowledged."}]}) # Dummy acknowledgement

        api_contents.append({"role": "user", "parts": [{"text": user_message}]})

        generation_config = genai.types.GenerationConfig(
            temperature=0.7, # Adjust temperature as needed
        )
        if is_fsm_generation_attempt:
            generation_config.response_mime_type = "application/json" # Request JSON format
            logger.info("WORKER_PROCESS: Requesting JSON object format from Gemini.")


        try:
            if self._is_stopped:
                logger.info("WORKER_PROCESS: Worker stopped just before creating completion.")
                return

            generation_args = {"contents": api_contents, "generation_config": generation_config}

            logger.debug(f"WORKER_PROCESS: Sending to Gemini. Contents (first part text len, role):")
            for i, item_content in enumerate(api_contents):
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
            elif hasattr(response, 'text'): # Fallback if structure is slightly different
                ai_response_content = response.text
            else: # Handle cases where response might be empty or blocked
                feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "No feedback."
                finish_reason = response.candidates[0].finish_reason if response.candidates else "Unknown reason."
                error_msg = f"Gemini response was empty or blocked. Finish Reason: {finish_reason}. Feedback: {feedback}"
                logger.error(error_msg)

                # Extract detailed blocking reasons if available
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    block_reason_msg = getattr(response.prompt_feedback, 'block_reason_message', None)
                    if block_reason_msg: error_msg += f" Block Reason Message: {block_reason_msg}"
                    for rating in response.prompt_feedback.safety_ratings:
                        if rating.blocked:
                             error_msg += f" Safety Blocked: Category {rating.category}, Probability {rating.probability.name}"

                self.errorOccurred.emit(AIStatus.CONTENT_BLOCKED, error_msg)
                self._current_processing_had_error = True
                self.statusUpdate.emit(AIStatus.ERROR, f"Status: Error - {error_msg[:50]}...")
                return


            self.conversation_history.append({"role": "user", "parts": [{"text": user_message}]})
            self.conversation_history.append({"role": "model", "parts": [{"text": ai_response_content}]})
            logger.debug("WORKER_PROCESS: AI response received and added to history.")
            self.responseReady.emit(ai_response_content, is_fsm_generation_attempt)

        except google.api_core.exceptions.ServiceUnavailable as e:
            err_str = f"API Connection Error: {str(e)[:200]}"
            logger.error("Gemini API Connection/Service Error: %s", err_str, exc_info=True)
            self.errorOccurred.emit(AIStatus.CONNECTION_ERROR, err_str)
            self.statusUpdate.emit(AIStatus.OFFLINE, "Status: Offline/Connection Error.")
            self._current_processing_had_error = True
        except google.api_core.exceptions.ResourceExhausted as e:
            err_str = f"Rate Limit Exceeded: {str(e)[:200]}"
            logger.error("Gemini Rate Limit Exceeded: %s", err_str, exc_info=True)
            self.errorOccurred.emit(AIStatus.RATE_LIMIT, err_str)
            self.statusUpdate.emit(AIStatus.ERROR, "Status: Rate Limit Exceeded.")
            self._current_processing_had_error = True
        except (google.api_core.exceptions.PermissionDenied, google.auth.exceptions.RefreshError, google.auth.exceptions.DefaultCredentialsError) as e:
            err_str = f"Authentication Error (Invalid API Key?): {str(e)[:200]}"
            logger.error("Gemini Authentication/Permission Error: %s", err_str, exc_info=True)
            self.errorOccurred.emit(AIStatus.AUTHENTICATION_ERROR, err_str)
            self.statusUpdate.emit(AIStatus.API_KEY_ERROR, "Status: API Key Error.")
            self._current_processing_had_error = True
        except google.api_core.exceptions.GoogleAPIError as e:
            error_detail = str(e)
            if hasattr(e, 'message') and e.message: error_detail = e.message
            err_str = f"Google API Error: {type(e).__name__} - {error_detail[:250]}"
            logger.error("Gemini API Error: %s - %s", type(e).__name__, error_detail[:250], exc_info=True)
            self.errorOccurred.emit(AIStatus.ERROR, err_str)
            self.statusUpdate.emit(AIStatus.ERROR, f"Status: API Error - {type(e).__name__}.")
            self._current_processing_had_error = True
        except (genai.types.BlockedPromptException, genai.types.StopCandidateException) as e:
            error_msg = f"Gemini content generation blocked or stopped: {e}"
            logger.error("WORKER_PROCESS: %s", error_msg, exc_info=True)
            self.errorOccurred.emit(AIStatus.CONTENT_BLOCKED, error_msg)
            self.statusUpdate.emit(AIStatus.ERROR, "Status: Content Blocked.")
            self._current_processing_had_error = True
        except Exception as e:
            error_msg = f"Unexpected error in AI worker: {type(e).__name__} - {str(e)[:150]}"
            logger.error("WORKER_PROCESS: %s", error_msg, exc_info=True)
            self.errorOccurred.emit(AIStatus.ERROR, error_msg)
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

        self._connect_actions_to_manager_slots()
        self._connect_ai_chatbot_signals()

    def _connect_actions_to_manager_slots(self):
        logger.debug("AIChatUI: Connecting actions to manager slots...")
        if hasattr(self.mw, 'ask_ai_to_generate_fsm_action'):
            self.mw.ask_ai_to_generate_fsm_action.triggered.connect(self.on_ask_ai_to_generate_fsm)
        if hasattr(self.mw, 'openai_settings_action'): # Name from main.py
            self.mw.openai_settings_action.triggered.connect(self.on_gemini_settings) # Method in this class
        if hasattr(self.mw, 'clear_ai_chat_action'):
            self.mw.clear_ai_chat_action.triggered.connect(self.on_clear_ai_chat_history)

    def _connect_ai_chatbot_signals(self):
        if self.mw.ai_chatbot_manager:
            self.mw.ai_chatbot_manager.statusUpdate.connect(self.update_status_display)
            self.mw.ai_chatbot_manager.errorOccurred.connect(self.handle_ai_error)
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

        return ai_chat_widget

    @pyqtSlot(AIStatus, str)
    def update_status_display(self, status_enum: AIStatus, status_text: str):
        if not self.ai_chat_status_label: return
        self.ai_chat_status_label.setText(status_text)

        base_style = f"font-size: {APP_FONT_SIZE_SMALL}; padding: 2px 4px; border-radius: 3px;"
        can_send_message = False
        is_thinking_ui = False

        if status_enum in [AIStatus.API_KEY_REQUIRED, AIStatus.API_KEY_ERROR, AIStatus.INACTIVE, AIStatus.AUTHENTICATION_ERROR]:
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: white; background-color: {COLOR_ACCENT_ERROR}; font-weight: bold;")
        elif status_enum == AIStatus.OFFLINE or status_enum == AIStatus.CONNECTION_ERROR:
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: {COLOR_TEXT_PRIMARY}; background-color: {COLOR_ACCENT_WARNING};")
        elif status_enum == AIStatus.ERROR or status_enum == AIStatus.CONTENT_BLOCKED or status_enum == AIStatus.RATE_LIMIT:
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: white; background-color: {COLOR_ACCENT_ERROR}; font-weight: bold;")
        elif status_enum == AIStatus.THINKING or status_enum == AIStatus.INITIALIZING:
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: {COLOR_TEXT_PRIMARY}; background-color: {QColor(COLOR_ACCENT_SECONDARY).lighter(130).name()}; font-style: italic;")
            is_thinking_ui = True
        elif status_enum == AIStatus.READY:
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: white; background-color: {COLOR_ACCENT_SUCCESS};")
            can_send_message = True
        elif status_enum == AIStatus.HISTORY_CLEARED:
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: {COLOR_TEXT_SECONDARY}; background-color: {QColor(COLOR_BACKGROUND_MEDIUM).lighter(105).name()};")
            # Determine if AI is generally ready even after history clear
            if self.mw.ai_chatbot_manager and self.mw.ai_chatbot_manager.get_current_ai_status() == AIStatus.READY:
                 can_send_message = True
        else: # Default or unknown status
            self.ai_chat_status_label.setStyleSheet(f"{base_style} color: {COLOR_TEXT_SECONDARY}; background-color: {COLOR_BACKGROUND_MEDIUM};")

        if self.ai_chat_send_button:
            self.ai_chat_send_button.setEnabled(can_send_message)
            if is_thinking_ui:
                self.ai_chat_send_button.setText("...") # Visual cue for thinking
                self.ai_chat_send_button.setIcon(QIcon()) # Hide icon when text is "..."
            else:
                self.ai_chat_send_button.setText("")
                self.ai_chat_send_button.setIcon(self.original_send_button_icon) # Restore original icon

        if self.ai_chat_input:
            self.ai_chat_input.setEnabled(can_send_message)
            if can_send_message and self.mw and hasattr(self.mw, 'ai_chatbot_dock') and self.mw.ai_chatbot_dock and self.mw.ai_chatbot_dock.isVisible() and self.mw.isActiveWindow():
                # QTimer.singleShot(0, self.ai_chat_input.setFocus) # Ensure focus happens after UI updates
                self.ai_chat_input.setFocus()


        if hasattr(self.mw, 'ask_ai_to_generate_fsm_action'):
            self.mw.ask_ai_to_generate_fsm_action.setEnabled(can_send_message)

    def _format_code_block(self, code_content: str, language: str = "") -> str:
        bg_color = COLOR_BACKGROUND_EDITOR_DARK
        text_color = COLOR_TEXT_EDITOR_DARK_PRIMARY
        border_color = QColor(bg_color).lighter(130).name()
        lang_display = f"<span style='color: {COLOR_TEXT_SECONDARY}; font-size: 7pt; margin-bottom: 3px; display: block;'>{html.escape(language)}</span>" if language else ""

        escaped_code = html.escape(code_content)
        return (f'<div style="margin: 8px 0; padding: 10px; background-color:{bg_color}; color:{text_color}; '
                f'border:1px solid {border_color}; border-radius:4px; font-family: Consolas, monospace; white-space:pre-wrap; overflow-x:auto;">'
                f'{lang_display}'
                f'{escaped_code}</div>')

    def _markdown_to_html_basic(self, text_part: str) -> str:
        # Phase 1: Inline element placeholder substitution
        # Inline code `text` (highest precedence)
        text_part = re.sub(r'`(.*?)`', r'‹‹‹ICODE›››\1‹‹‹/ICODE›››', text_part, flags=re.DOTALL)
        # Bold: **text** or __text__ (ensure content exists)
        text_part = re.sub(r'\*\*(?=\S)(.*?\S)\*\*', r'‹‹‹STRONG›››\1‹‹‹/STRONG›››', text_part, flags=re.DOTALL)
        text_part = re.sub(r'__(?=\S)(.*?\S)__', r'‹‹‹STRONG›››\1‹‹‹/STRONG›››', text_part, flags=re.DOTALL)
        # Italic: *text* or _text_ (handle word boundaries and avoid conflict with bold)
        text_part = re.sub(r'(?<![\*_])\*(?=\S)(.*?\S)\*(?![\*_])', r'‹‹‹EM›››\1‹‹‹/EM›››', text_part)
        text_part = re.sub(r'(?<![\*_])_(?=\S)(.*?\S)_(?![\*_])', r'‹‹‹EM›››\1‹‹‹/EM›››', text_part)

        # Phase 2: Line-by-line processing for lists and paragraphs
        lines = text_part.splitlines()
        html_lines = []
        in_list_ul = False # Tracks if we are inside a <ul>

        for line_content_with_placeholders in lines:
            list_match = re.match(r'^\s*([\-\*+])\s+(.*)', line_content_with_placeholders)

            if list_match:
                list_item_text_with_placeholders = list_match.group(2).strip()
                # Content already has placeholders. Escape it.
                escaped_list_item_content = html.escape(list_item_text_with_placeholders)

                if not in_list_ul:
                    html_lines.append("<ul>")
                    in_list_ul = True
                html_lines.append(f"<li>{escaped_list_item_content}</li>")
            else:
                # Not a list item
                if in_list_ul:
                    html_lines.append("</ul>")
                    in_list_ul = False

                if line_content_with_placeholders.strip(): # A content line
                    # This line (paragraph part) already has placeholders. Escape it.
                    html_lines.append(html.escape(line_content_with_placeholders))
                elif html_lines and not html_lines[-1].endswith("</ul>") and not html_lines[-1] == "<br>":
                    # An empty line likely means a paragraph break, add a <br> if the last line wasn't a list closing
                    # and not already a <br>.
                    html_lines.append("<br>")


        if in_list_ul: # Close any open list at the end
            html_lines.append("</ul>")

        # Assemble HTML, carefully handling <br> for paragraphs
        processed_html_block = ""
        for i, line_html in enumerate(html_lines):
            if i > 0:
                # Add <br> between non-list lines to simulate paragraphs
                # or after a list ends and before new non-list content.
                prev_line_html = html_lines[i-1]
                is_prev_li_or_ul_related = prev_line_html.startswith("<li") or prev_line_html.startswith("<ul")
                is_current_li_or_ul_related = line_html.startswith("<li") or line_html.startswith("<ul")

                if not is_prev_li_or_ul_related and not is_current_li_or_ul_related and line_html != "<br>":
                    processed_html_block += "<br>"
                elif prev_line_html.startswith("</ul>") and not is_current_li_or_ul_related and line_html != "<br>":
                     processed_html_block += "<br>"


            processed_html_block += line_html

        # Phase 3: Replace escaped placeholders with actual HTML tags
        final_html_output = processed_html_block
        final_html_output = final_html_output.replace(html.escape("‹‹‹STRONG›››"), "<strong>").replace(html.escape("‹‹‹/STRONG›››"), "</strong>")
        final_html_output = final_html_output.replace(html.escape("‹‹‹EM›››"), "<em>").replace(html.escape("‹‹‹/EM›››"), "</em>")

        inline_code_style = f"background-color:{QColor(COLOR_BACKGROUND_MEDIUM).lighter(105).name()}; color:{COLOR_ACCENT_PRIMARY}; padding:1px 4px; border-radius:3px; font-family:Consolas,monospace; font-size: 0.9em;"
        final_html_output = final_html_output.replace(html.escape("‹‹‹ICODE›››"), f"<code style='{inline_code_style}'>").replace(html.escape("‹‹‹/ICODE›››"), "</code>")

        return final_html_output

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
        # Regex to find ```lang\ncode\n``` blocks
        code_block_regex = re.compile(r'```([a-zA-Z0-9_+#.-]*)\s*\n(.*?)\n```', flags=re.DOTALL | re.MULTILINE)
        last_index = 0

        for match in code_block_regex.finditer(message):
            text_before = message[last_index:match.start()]
            if text_before.strip(): # Only process if there's actual text
                processed_message_html_parts.append(self._markdown_to_html_basic(text_before))

            language_hint = match.group(1).strip() # Language from ```lang
            code_content = match.group(2).strip('\n')
            processed_message_html_parts.append(self._format_code_block(code_content, language_hint))
            last_index = match.end()

        text_after = message[last_index:]
        if text_after.strip(): # Process remaining text
            processed_message_html_parts.append(self._markdown_to_html_basic(text_after))

        final_message_html = "".join(processed_message_html_parts)

        bg_msg_color = QColor(sender_color_str).lighter(185).name()
        if sender == "System Error": bg_msg_color = QColor(COLOR_ACCENT_ERROR).lighter(180).name()
        elif sender == "System": bg_msg_color = QColor(COLOR_BACKGROUND_MEDIUM).lighter(105).name()

        html_to_append = (f"<div style='margin-bottom: 12px; padding: 8px 10px; border-left: 4px solid {sender_color_str}; background-color: {bg_msg_color}; border-radius: 5px;'>"
                          f"<div style='margin-bottom: 4px;'>"
                          f"<strong style='color:{sender_color_str}; font-size: 9pt;'>{sender_name_html}</strong>"
                          f"<span style='font-size:7.5pt; color:{COLOR_TEXT_SECONDARY}; margin-left: 8px;'>[{timestamp}]</span> "
                          f"</div>"
                          f"<div style='padding-left: 2px; line-height:1.45; font-size: 9pt; white-space: pre-wrap;'>{final_message_html}</div></div>")

        self.ai_chat_display.append(html_to_append)
        self.ai_chat_display.ensureCursorVisible()

    @pyqtSlot(AIStatus, str) # Match errorOccurred signal which now sends AIStatus too
    def handle_ai_error(self, error_status_enum: AIStatus, error_message: str):
        # The status display is already updated by the manager's statusUpdate signal.
        # This method just needs to log the error to the chat display.
        self._append_to_chat_display("System Error", error_message)
        logger.error("AIChatUI: AI Chatbot Error (%s): %s", error_status_enum.name, error_message)


    @pyqtSlot(dict, str)
    def handle_fsm_data_from_ai(self, fsm_data: dict, source_message: str):
        logger.info("AIChatUI: Received FSM data. Source: '%s...'", source_message[:30])
        self._append_to_chat_display("AI", f"Received FSM structure. (Source: {source_message[:30]}...) Adding to diagram.")
        if not fsm_data or (not fsm_data.get('states') and not fsm_data.get('transitions')):
            logger.error("AIChatUI: AI returned empty or invalid FSM data.")
            self._append_to_chat_display("System", "AI did not return a valid FSM structure to draw.")
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
        logger.info("AIChatUI: FSM data from AI processed and added to scene.")

    @pyqtSlot(str)
    def handle_plain_ai_response(self, ai_message: str):
        logger.info("AIChatUI: Received plain AI response.")
        self._append_to_chat_display("AI", ai_message)

    @pyqtSlot()
    def on_send_ai_chat_message(self):
        if not self.ai_chat_input or not self.ai_chat_send_button.isEnabled(): return
        message = self.ai_chat_input.text().strip()
        if not message: return
        self.ai_chat_input.clear(); self._append_to_chat_display("You", message)
        if self.mw.ai_chatbot_manager:
            self.mw.ai_chatbot_manager.send_message(message)
        else:
            err_msg = "AI Chatbot Manager not initialized. Cannot send message."
            # The handle_ai_error and update_status_display calls should now correctly use AIStatus
            self.handle_ai_error(AIStatus.ERROR, err_msg) # Assuming handle_ai_error now takes AIStatus
            self.update_status_display(AIStatus.ERROR, f"Status: Error - {err_msg}")


    @pyqtSlot()
    def on_ask_ai_to_generate_fsm(self):
        logger.info("AIChatUI: on_ask_ai_to_generate_fsm CALLED!")
        description, ok = QInputDialog.getMultiLineText(self.mw, "Generate FSM", "Describe the FSM you want to create:", "Example: A traffic light with states Red, Yellow, Green...")
        if ok and description.strip():
            logger.info("AIChatUI: Sending FSM desc: '%s...'", description[:50])
            if self.mw.ai_chatbot_manager:
                self.mw.ai_chatbot_manager.generate_fsm_from_description(description)
                self._append_to_chat_display("You", f"Generate an FSM: {description}")
            else:
                self.handle_ai_error(AIStatus.ERROR, "AI Chatbot Manager not initialized.")
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
                self.mw.ai_chatbot_manager.clear_conversation_history()
                if self.ai_chat_display:
                    self.ai_chat_display.clear()
                    self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
                logger.info("AIChatUI: Chat history cleared by user.")
                self._append_to_chat_display("System", "Chat history cleared.")
            else:
                logger.info("AIChatUI: User cancelled clearing chat history.")
        else:
            self.handle_ai_error(AIStatus.ERROR, "AI Chatbot Manager not initialized.")


class AIChatbotManager(QObject):
    statusUpdate = pyqtSignal(AIStatus, str)
    errorOccurred = pyqtSignal(AIStatus, str)
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
        self._current_ai_status = AIStatus.INITIALIZING

    def _update_current_ai_status(self, new_status_enum: AIStatus, status_text: str):
        self._current_ai_status = new_status_enum
        self.statusUpdate.emit(new_status_enum, status_text)
        logger.debug(f"MGR_STATUS_UPDATE: Enum={new_status_enum.name}, Text='{status_text}'")

    @pyqtSlot(AIStatus, str)
    def _handle_worker_error_with_status(self, error_status: AIStatus, error_message: str):
        logger.error(f"MGR_WORKER_ERROR (Status: {error_status.name}): {error_message}")
        self.errorOccurred.emit(error_status, error_message)
        # The statusUpdate signal with the error_status is now typically emitted by the worker directly,
        # or by logic in set_api_key/process_message_slot within the worker before emitting errorOccurred.
        # If we want to ensure a specific status text from the manager level here, we could do:
        # self._update_current_ai_status(error_status, f"Status: Error - {error_status.name}")


    def get_current_ai_status(self) -> AIStatus:
        return self._current_ai_status

    def _cleanup_existing_worker_and_thread(self):
        logger.debug("MGR_CLEANUP: CALLED.")
        if self.chatbot_thread and self.chatbot_thread.isRunning():
            logger.debug("MGR_CLEANUP: Attempting to quit existing thread...")
            if self.chatbot_worker:
                # Ensure stop_processing_slot is called correctly based on thread affinity
                if QThread.currentThread() != self.chatbot_thread:
                    QMetaObject.invokeMethod(self.chatbot_worker, "stop_processing_slot", Qt.BlockingQueuedConnection)
                else:
                    self.chatbot_worker.stop_processing_slot() # Direct call if on same thread
                logger.debug("MGR_CLEANUP: stop_processing_slot invoked on worker.")

            self.chatbot_thread.quit()
            if not self.chatbot_thread.wait(1000): # Increased wait time
                logger.warning("MGR_CLEANUP: Thread did not quit gracefully. Terminating.")
                self.chatbot_thread.terminate()
                self.chatbot_thread.wait(500)
            logger.debug("MGR_CLEANUP: Existing thread stopped.")
        self.chatbot_thread = None # Clear reference after stopping

        if self.chatbot_worker:
            logger.debug("MGR_CLEANUP: Disconnecting signals and scheduling old worker for deletion.")
            # Disconnect signals robustly
            try: self.chatbot_worker.responseReady.disconnect(self._handle_worker_response)
            except (TypeError, RuntimeError): pass # Ignore if not connected or already gone
            try: self.chatbot_worker.errorOccurred.disconnect(self._handle_worker_error_with_status)
            except (TypeError, RuntimeError): pass
            try: self.chatbot_worker.statusUpdate.disconnect(self._update_current_ai_status)
            except (TypeError, RuntimeError): pass
            self.chatbot_worker.deleteLater()
            logger.debug("MGR_CLEANUP: Old worker scheduled for deletion.")
        self.chatbot_worker = None # Clear reference after scheduling deletion
        logger.debug("MGR_CLEANUP: Finished. Worker and thread are None.")


    def set_api_key(self, api_key: str | None):
        old_key_status = 'SET' if self.api_key else 'NONE'
        new_key_status = 'SET' if api_key else 'NONE'
        logger.info(f"MGR_SET_API_KEY (Gemini): New key: '{new_key_status}', Old key: '{old_key_status}'")

        old_api_key_val = self.api_key
        self.api_key = api_key

        # Condition to (re)setup worker:
        # 1. API key actually changed.
        # 2. API key is set, but worker/thread is not properly initialized or running.
        if old_api_key_val != self.api_key or \
           (self.api_key and (not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning())):
            self._cleanup_existing_worker_and_thread() # Clean up before setting up new or if key is cleared
            if self.api_key:
                self._setup_worker() # This will call set_api_key_slot on the new worker
            else: # API key cleared
                self._update_current_ai_status(AIStatus.API_KEY_REQUIRED, "Status: Gemini API Key cleared. AI Assistant inactive.")
        elif self.chatbot_worker and self.api_key and self.chatbot_thread and self.chatbot_thread.isRunning():
             # API key value might be the same, but we might want to re-initialize client if internal state dictates.
             # For now, assume set_api_key_slot handles re-initialization if needed.
             QMetaObject.invokeMethod(self.chatbot_worker, "set_api_key_slot", Qt.QueuedConnection,
                                      Q_ARG(str, self.api_key))
        elif not self.api_key: # API key is None and was None, and no worker running
            self._update_current_ai_status(AIStatus.API_KEY_REQUIRED, "Status: Gemini API Key required.")


    def _setup_worker(self):
        if not self.api_key:
            logger.warning("MGR_SETUP_WORKER: Cannot setup - API key is not set.")
            self._update_current_ai_status(AIStatus.API_KEY_REQUIRED, "Status: API Key required.")
            return

        # Ensure any previous worker/thread is fully cleaned up before creating new ones.
        if self.chatbot_worker or (self.chatbot_thread and self.chatbot_thread.isRunning()):
            logger.info("MGR_SETUP_WORKER: Worker/thread exists or is running. Cleaning up first.")
            self._cleanup_existing_worker_and_thread()
            # Add a small delay or check if cleanup is truly finished if issues persist.
            # QTimer.singleShot(100, self._proceed_with_setup_worker) # Example of deferred setup
            # return # if using deferred setup
        
        logger.info("MGR_SETUP_WORKER: Setting up new worker and thread.")
        self.chatbot_thread = QThread(self) # Parent to manager for lifecycle management
        self.chatbot_worker = ChatbotWorker(self.api_key) # Pass current API key
        self.chatbot_worker.moveToThread(self.chatbot_thread)

        # Connect signals from worker to manager's slots or directly to UI manager if appropriate
        self.chatbot_worker.responseReady.connect(self._handle_worker_response)
        self.chatbot_worker.errorOccurred.connect(self._handle_worker_error_with_status)
        self.chatbot_worker.statusUpdate.connect(self._update_current_ai_status) # Manager updates its own status

        # For cleanup when thread finishes
        # self.chatbot_thread.finished.connect(self.chatbot_worker.deleteLater) # Worker cleans up
        # self.chatbot_thread.finished.connect(self.chatbot_thread.deleteLater) # Thread cleans up

        self.chatbot_thread.start()
        logger.info("MGR_SETUP_WORKER: New AI Chatbot worker thread started.")

        # Initial status update
        self._update_current_ai_status(AIStatus.INITIALIZING, "Status: AI Assistant Initializing...")
        # Call set_api_key_slot on the worker to initialize its client with the API key
        # This ensures the worker's client is configured after it has moved to the thread.
        QMetaObject.invokeMethod(self.chatbot_worker, "set_api_key_slot", Qt.QueuedConnection,
                                      Q_ARG(str, self.api_key))


    @pyqtSlot(str, bool)
    def _handle_worker_response(self, ai_response_content: str, was_fsm_generation_attempt: bool):
        logger.info(f"MGR_HANDLE_WORKER_RESPONSE: Received from worker. Was FSM attempt: {was_fsm_generation_attempt}")

        if was_fsm_generation_attempt:
            try:
                # Attempt to find JSON within ```json ... ``` or ``` ... ```
                match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", ai_response_content, re.DOTALL | re.IGNORECASE)
                if match:
                    cleaned_json_str = match.group(1)
                    logger.debug("MGR_HANDLE_WORKER_RESPONSE: Extracted JSON via regex from markdown block.")
                else:
                    # If no markdown block, try to parse the whole string, stripping whitespace.
                    # This handles cases where Gemini directly returns a JSON object as per instructions.
                    if "```" not in ai_response_content:
                        logger.debug("MGR_HANDLE_WORKER_RESPONSE: No ```json``` block found, trying to parse directly.")
                        cleaned_json_str = ai_response_content.strip()
                    else:
                        # If ``` is present but not matching our regex, it's likely invalid or mixed content.
                        logger.warning("MGR_HANDLE_WORKER_RESPONSE: Markdown ``` found, but not a recognized JSON block. Treating as plain text.")
                        # Force JSONDecodeError to go to the plain text path
                        raise json.JSONDecodeError("Markdown ``` found, but not a recognized JSON block.", ai_response_content, 0)

                fsm_data = json.loads(cleaned_json_str)
                if isinstance(fsm_data, dict) and ('states' in fsm_data or 'transitions' in fsm_data): # Basic validation
                    logger.info("MGR_HANDLE_WORKER_RESPONSE: Parsed FSM JSON successfully. Emitting fsmDataReceived.")
                    source_desc = self.last_fsm_request_description or "AI Generated FSM"
                    self.fsmDataReceived.emit(fsm_data, source_desc)
                    # Status will be updated to READY by the worker if all went well.
                    return
                else:
                    err_msg = "AI returned JSON, but it's not a valid FSM structure (missing 'states' or 'transitions'). Displaying as text."
                    logger.warning("MGR_HANDLE_WORKER_RESPONSE: " + err_msg)
                    self.errorOccurred.emit(AIStatus.ERROR, err_msg) # Signal error to UI
                    self._update_current_ai_status(AIStatus.ERROR, "Status: Invalid FSM JSON from AI.")
            except json.JSONDecodeError as e:
                err_msg = f"AI response for FSM generation was not valid JSON. Raw response (see chat for full):\n{ai_response_content[:200]}..."
                logger.warning(f"MGR_HANDLE_WORKER_RESPONSE: Failed to parse AI response as JSON: {e}. Treating as plain text.", exc_info=True)
                self.errorOccurred.emit(AIStatus.ERROR, err_msg) # Signal error to UI
                self._update_current_ai_status(AIStatus.ERROR, "Status: AI response was not valid FSM JSON.")
                # Fall through to emit as plain text

        # If not FSM generation or if FSM parsing failed, emit as plain text
        logger.debug("MGR_HANDLE_WORKER_RESPONSE: Emitting plainResponseReady.")
        self.plainResponseReady.emit(ai_response_content)
        # Worker should set status to READY if no errors occurred during its processing.


    def _prepare_and_send_to_worker(self, user_message_text: str, is_fsm_gen_specific: bool = False):
        logger.info(f"MGR_PREP_SEND: For: '{user_message_text[:30]}...', FSM_specific_req: {is_fsm_gen_specific}")

        if not self.api_key:
            err_msg = "Gemini API Key not set. Configure in Settings."
            logger.warning("MGR_PREP_SEND: API Key not set.")
            self.errorOccurred.emit(AIStatus.API_KEY_REQUIRED, err_msg)
            self._update_current_ai_status(AIStatus.API_KEY_REQUIRED, "Status: API Key required.")
            # Append to UI chat directly if possible, or let UI handle the errorOccurred signal
            if self.parent_window and hasattr(self.parent_window, 'ai_chat_ui_manager') and self.parent_window.ai_chat_ui_manager:
                self.parent_window.ai_chat_ui_manager._append_to_chat_display("System Error", err_msg)
            return

        if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
            logger.warning("MGR_PREP_SEND: Worker/Thread not ready.")
            # Attempt to re-setup if API key is present but worker is not running
            if self.api_key and (not self.chatbot_thread or not self.chatbot_thread.isRunning()):
                 logger.info("MGR_PREP_SEND: Attempting to re-setup worker because it's not running.")
                 self._setup_worker() # This will start the thread and initialize the worker

            # Re-check after setup attempt
            if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
                err_msg = "AI Assistant is not ready. Please wait or check settings."
                self.errorOccurred.emit(AIStatus.ERROR, err_msg) # Or a more specific status like INACTIVE
                self._update_current_ai_status(AIStatus.ERROR, "Status: AI Assistant Not Ready.")
                if self.parent_window and hasattr(self.parent_window, 'ai_chat_ui_manager') and self.parent_window.ai_chat_ui_manager:
                    self.parent_window.ai_chat_ui_manager._append_to_chat_display("System Error", err_msg)
                return


        if is_fsm_gen_specific:
            self.last_fsm_request_description = user_message_text
        else:
            self.last_fsm_request_description = None # Clear if not an FSM gen request

        # Prepare diagram context (lean version)
        diagram_json_str: str | None = None
        if self.parent_window and hasattr(self.parent_window, 'scene') and hasattr(self.parent_window.scene, 'get_diagram_data'):
            try:
                diagram_data = self.parent_window.scene.get_diagram_data()
                # Create a "lean" version of the diagram data for context
                lean_diagram_data = {
                    "states": [{"name": s.get("name"), "is_initial": s.get("is_initial"), "is_final": s.get("is_final")}
                               for s in diagram_data.get("states", [])],
                    "transitions": [{"source": t.get("source"), "target": t.get("target"), "event": t.get("event")}
                                    for t in diagram_data.get("transitions", [])]
                    # Optionally add comments or superstate info if relevant and concise
                }
                diagram_json_str = json.dumps(lean_diagram_data)
                logger.debug(f"MGR_PREP_SEND: Lean diagram context (first 100 chars): {diagram_json_str[:100]}")
            except Exception as e:
                logger.error(f"MGR_PREP_SEND: Error getting/processing diagram data: {e}", exc_info=True)
                diagram_json_str = json.dumps({"error": "Could not retrieve diagram context."})
        else:
             diagram_json_str = json.dumps({"error": "Diagram context unavailable."})


        # Send to worker
        if self.chatbot_worker:
            # Update diagram context on worker (queued)
            effective_diagram_json_str = diagram_json_str if diagram_json_str is not None else "" # Ensure empty string if None
            QMetaObject.invokeMethod(self.chatbot_worker, "set_diagram_context_slot", Qt.QueuedConnection,
                                     Q_ARG(str, effective_diagram_json_str))
            # Process message on worker (queued)
            QMetaObject.invokeMethod(self.chatbot_worker, "process_message_slot", Qt.QueuedConnection,
                                     Q_ARG(str, user_message_text),
                                     Q_ARG(bool, is_fsm_gen_specific))
            logger.debug("MGR_PREP_SEND: Methods queued for worker.")
        else:
            # This should ideally be caught by the checks above
            logger.error("MGR_PREP_SEND: Chatbot worker is None, cannot queue methods.")
            err_msg = "AI Assistant encountered an internal error (worker missing). Please try restarting AI features."
            self.errorOccurred.emit(AIStatus.ERROR, err_msg)
            self._update_current_ai_status(AIStatus.ERROR, "Status: Internal Error (Worker Missing).")


    def send_message(self, user_message_text: str):
        self._prepare_and_send_to_worker(user_message_text, is_fsm_gen_specific=False)

    def generate_fsm_from_description(self, description: str):
         self._prepare_and_send_to_worker(description, is_fsm_gen_specific=True)

    def clear_conversation_history(self):
        logger.info("MGR: clear_conversation_history CALLED.")
        if self.chatbot_worker and self.chatbot_thread and self.chatbot_thread.isRunning():
            QMetaObject.invokeMethod(self.chatbot_worker, "clear_history_slot", Qt.QueuedConnection)
            logger.debug("MGR: clear_history invoked on worker.")
            # Status update will come from the worker's clear_history_slot
        else:
            # If worker isn't active, manager can still update status.
            if not self.api_key:
                self._update_current_ai_status(AIStatus.API_KEY_REQUIRED, "Status: API Key required. Chat inactive.")
            else:
                self._update_current_ai_status(AIStatus.INACTIVE, "Status: Chatbot not active.")
            logger.warning("MGR: Chatbot not active, cannot clear history from worker.")


    def stop_chatbot(self):
        logger.info("MGR_STOP: stop_chatbot CALLED.")
        self._cleanup_existing_worker_and_thread() # This handles stopping the worker and thread
        self._update_current_ai_status(AIStatus.INACTIVE, "Status: AI Assistant Stopped.")
        logger.info("MGR_STOP: Chatbot stopped and cleaned up.")


    def set_online_status(self, is_online: bool):
        """Called by MainWindow when internet status changes."""
        logger.info(f"MGR_NET_STATUS: Online status changed to: {is_online}")

        if not self.api_key:
            # API key is the primary requirement, regardless of online status
            if is_online:
                self._update_current_ai_status(AIStatus.API_KEY_REQUIRED, "Status: Online, Gemini API Key required.")
            else:
                self._update_current_ai_status(AIStatus.OFFLINE, "Status: Offline, Gemini API Key required.")
            return

        # API key is present, now consider online status
        if is_online:
            # If online and worker/thread not running, try to set it up
            if not self.chatbot_thread or not self.chatbot_thread.isRunning():
                logger.info("MGR_NET_STATUS: Network online, API key present, attempting worker setup.")
                self._setup_worker() # This will trigger INITIALIZING then READY/ERROR
            else: # Thread is running
                # Check if worker and its client are initialized
                if self.chatbot_worker and self.chatbot_worker.client: # Worker and client initialized
                    self._update_current_ai_status(AIStatus.READY, "Status: Online and Ready.")
                elif self.chatbot_worker and not self.chatbot_worker.client: # Worker exists but client failed (e.g. bad key after init)
                    self._update_current_ai_status(AIStatus.API_KEY_ERROR, "Status: Online, API Key Error.")
                else: # Thread running but worker might not be fully ready (should be caught by initializing)
                    self._update_current_ai_status(AIStatus.INITIALIZING, "Status: Online, Initializing...")
        else: # Offline
            # If worker is running, it will eventually hit connection errors.
            # Manager can proactively set status to OFFLINE.
            # No need to stop the worker thread here, it will fail gracefully on next API call.
            self._update_current_ai_status(AIStatus.OFFLINE, "Status: Offline. Gemini AI features unavailable.")