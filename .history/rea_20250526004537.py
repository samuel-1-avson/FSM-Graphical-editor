
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTime, QTimer, Qt, QMetaObject, pyqtSlot, Q_ARG
import openai
import json
import re 
import logging

logger = logging.getLogger(__name__)

class ChatbotWorker(QObject):
    responseReady = pyqtSignal(str, bool) 
    errorOccurred = pyqtSignal(str)
    statusUpdate = pyqtSignal(str)

    def __init__(self, api_key, model_name="gpt-3.5-turbo", parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        self.conversation_history = []
        self.current_diagram_context_json_str: str | None = None # Python type hint
        self._current_processing_had_error = False 
        self._is_stopped = False # Add a stop flag
        self._initialize_client()
        logger.info(f"ChatbotWorker initialized (API Key {'SET' if api_key else 'NOT SET'}).")

    def _initialize_client(self):
        if self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                logger.info(f"OpenAI client initialized for model {self.model_name}.")
            except Exception as e:
                self.client = None
                error_msg = f"Failed to initialize OpenAI client: {e}"
                logger.error(error_msg, exc_info=True)
                self.errorOccurred.emit(error_msg) 
        else:
            self.client = None
            logger.info("OpenAI client not initialized (no API key).")

    # Slot for API key - expects a string
    @pyqtSlot(str) 
    def set_api_key_slot(self, api_key: str): 
        logger.info(f"WORKER: set_api_key_slot called (new key {'SET' if api_key else 'NOT SET'}).")
        self.api_key = api_key
        self._initialize_client()

    # Slot for diagram context - expects a string.
    # The manager will ensure an empty string is passed if the context is None.
    @pyqtSlot(str) 
    def set_diagram_context_slot(self, diagram_json_str: str): 
        if not diagram_json_str: 
            logger.debug(f"WORKER: Setting diagram context to None (received empty string).")
            self.current_diagram_context_json_str = None
        else:
            logger.debug(f"WORKER: Setting diagram context. Length: {len(diagram_json_str)}")
            self.current_diagram_context_json_str = diagram_json_str

    # Slot for processing message - expects string and bool
    @pyqtSlot(str, bool) 
    def process_message_slot(self, user_message: str, force_fsm_generation: bool):
        if self._is_stopped:
            logger.info("WORKER_PROCESS: Worker is stopped, ignoring message.")
            return

        logger.info(f"WORKER_PROCESS: process_message_slot CALLED for: '{user_message[:50]}...' (force_fsm_generation={force_fsm_generation})")
        
        self._current_processing_had_error = False 
        
        if not self.api_key or not self.client:
            error_msg = "OpenAI API key not set or client not initialized. Please set it in AI Assistant Settings."
            logger.warning("process_message: %s", error_msg)
            self.errorOccurred.emit(error_msg)
            self.statusUpdate.emit("Status: API Key required.")
            self._current_processing_had_error = True 
            return
        
        if self._is_stopped: # Check again before long operation
            logger.info("WORKER_PROCESS: Worker stopped before API call.")
            return

        self.statusUpdate.emit("Status: Thinking...")

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
             system_prompt_content += " For general conversation, provide helpful and concise answers."

        messages_for_api = [{"role": "system", "content": system_prompt_content}]
        history_context_limit = -6 
        if self.conversation_history:
            messages_for_api.extend(self.conversation_history[history_context_limit:])
        messages_for_api.append({"role": "user", "content": user_message})

        try:
            if self._is_stopped: # Final check
                logger.info("WORKER_PROCESS: Worker stopped just before creating completion.")
                return

            request_params = {
                "model": self.model_name,
                "messages": messages_for_api
            }
            if is_fsm_generation_attempt:
                request_params["response_format"] = {"type": "json_object"}
                logger.info("WORKER_PROCESS: Requesting JSON object format from AI.")

            # This is the potentially long-running network call
            chat_completion = self.client.chat.completions.create(**request_params)
            
            if self._is_stopped: # Check if stopped during the API call
                logger.info("WORKER_PROCESS: Worker stopped during/after API call, discarding response.")
                return
            ai_response_content = chat_completion.choices[0].message.content

            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": ai_response_content})
            logger.debug("WORKER_PROCESS: AI response received and added to history.")
            self.responseReady.emit(ai_response_content, is_fsm_generation_attempt)

        except openai.APIConnectionError as e:
            logger.error("OpenAI API Connection Error: %s", str(e)[:200], exc_info=True)
            self.errorOccurred.emit(f"API Connection Error: {str(e)[:200]}")
            self._current_processing_had_error = True
        except openai.RateLimitError as e:
            logger.error("OpenAI Rate Limit Exceeded: %s", str(e)[:200], exc_info=True)
            self.errorOccurred.emit(f"Rate Limit Exceeded: {str(e)[:200]}")
            self._current_processing_had_error = True
        except openai.AuthenticationError as e: 
            logger.error("OpenAI Authentication Error: %s", str(e)[:200], exc_info=True)
            self.errorOccurred.emit(f"Authentication Error (Invalid API Key?): {str(e)[:200]}")
            self.statusUpdate.emit("Status: API Key Error.") 
            self._current_processing_had_error = True
        except openai.APIError as e:
            error_detail = str(e)
            if hasattr(e, 'message') and e.message: error_detail = e.message
            json_body_error_msg = ""
            if hasattr(e, 'json_body') and e.json_body and 'error' in e.json_body and 'message' in e.json_body['error']:
                json_body_error_msg = e.json_body['error']['message']
            if json_body_error_msg: error_detail += f" (Detail: {json_body_error_msg})"
            logger.error("OpenAI API Error: %s - %s", type(e).__name__, error_detail[:250], exc_info=True)
            self.errorOccurred.emit(f"OpenAI API Error: {type(e).__name__} - {error_detail[:250]}")
            self._current_processing_had_error = True
        except Exception as e:
            error_msg = f"Unexpected error in AI worker: {type(e).__name__} - {str(e)[:150]}"
            logger.error("WORKER_PROCESS: %s", error_msg, exc_info=True)
            self.errorOccurred.emit(error_msg)
            self._current_processing_had_error = True
        finally:
            if not self._current_processing_had_error and self.client and not self._is_stopped:
                self.statusUpdate.emit("Status: Ready.")

    @pyqtSlot() # No name needed if Python method name matches slot name
    def clear_history_slot(self): # Renamed for consistency
        self.conversation_history = []
        logger.info("Conversation history cleared.")
        self.statusUpdate.emit("Status: Chat history cleared.")

    @pyqtSlot()
    def stop_processing_slot(self):
        logger.info("WORKER: stop_processing_slot called.")
        self._is_stopped = True
        # Note: This doesn't actively interrupt an ongoing openai.create call.
        # For true interruption, more complex async handling or a different HTTP client would be needed.

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
        logger.info("AIChatbotManager initialized.")

    def _cleanup_existing_worker_and_thread(self):
        logger.debug("MGR_CLEANUP: CALLED.")
        if self.chatbot_thread and self.chatbot_thread.isRunning():
            logger.debug("MGR_CLEANUP: Attempting to quit existing thread...")
            if self.chatbot_worker:
                # Try to tell the worker to stop its current task if possible
                QMetaObject.invokeMethod(self.chatbot_worker, "stop_processing_slot", Qt.QueuedConnection)
                logger.debug("MGR_CLEANUP: stop_processing_slot invoked on worker.")

            self.chatbot_thread.quit()
            if not self.chatbot_thread.wait(200): # Reduced wait time
                logger.warning("MGR_CLEANUP: Thread did not quit gracefully. Terminating.")
                self.chatbot_thread.terminate()
                self.chatbot_thread.wait(100) # Brief wait after terminate
            logger.debug("MGR_CLEANUP: Existing thread stopped.")
        self.chatbot_thread = None

        if self.chatbot_worker:
            logger.debug("MGR_CLEANUP: Disconnecting signals and scheduling old worker for deletion.")
            try: self.chatbot_worker.responseReady.disconnect(self._handle_worker_response)
            except (TypeError, RuntimeError): pass 
            try: self.chatbot_worker.errorOccurred.disconnect(self.errorOccurred)
            except (TypeError, RuntimeError): pass
            try: self.chatbot_worker.statusUpdate.disconnect(self.statusUpdate)
            except (TypeError, RuntimeError): pass
            self.chatbot_worker.deleteLater()
            logger.debug("MGR_CLEANUP: Old worker scheduled for deletion.")
        self.chatbot_worker = None
        logger.debug("MGR_CLEANUP: Finished. Worker and thread are None.")


    def set_api_key(self, api_key: str | None):
        old_key_status = 'SET' if self.api_key else 'NONE'
        new_key_status = 'SET' if api_key else 'NONE'
        logger.info(f"MGR_SET_API_KEY: New key: '{new_key_status}', Old key: '{old_key_status}'")
        
        old_api_key_val = self.api_key 
        self.api_key = api_key

        if old_api_key_val != self.api_key or (self.api_key and (not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning())):
            self._cleanup_existing_worker_and_thread()
            if self.api_key:
                self._setup_worker()
            else:
                self.statusUpdate.emit("Status: API Key cleared. AI Assistant inactive.")
        elif self.chatbot_worker and self.api_key and self.chatbot_thread and self.chatbot_thread.isRunning():
             # Fixed QMetaObject.invokeMethod call using Q_ARG
             QMetaObject.invokeMethod(self.chatbot_worker, "set_api_key_slot", Qt.QueuedConnection, 
                                      Q_ARG(str, self.api_key)) 
             self.statusUpdate.emit("Status: Ready. API Key re-confirmed.")
        elif not self.api_key:
            self.statusUpdate.emit("Status: API Key required.")

    def _setup_worker(self):
        if not self.api_key:
            logger.warning("MGR_SETUP_WORKER: Cannot setup - API key is not set.")
            self.statusUpdate.emit("Status: API Key required.")
            return

        if self.chatbot_worker or (self.chatbot_thread and self.chatbot_thread.isRunning()):
            logger.info("MGR_SETUP_WORKER: Worker/thread exists or is running. Cleaning up first.")
            self._cleanup_existing_worker_and_thread()

        logger.info("MGR_SETUP_WORKER: Setting up new worker and thread.")
        self.chatbot_thread = QThread(self) 
        # self.chatbot_thread.setDaemon(True) # Option 1: Make it a daemon thread
        self.chatbot_worker = ChatbotWorker(self.api_key) 
        self.chatbot_worker.moveToThread(self.chatbot_thread)

        self.chatbot_worker.responseReady.connect(self._handle_worker_response)
        self.chatbot_worker.errorOccurred.connect(self.errorOccurred) 
        self.chatbot_worker.statusUpdate.connect(self.statusUpdate) 

        self.chatbot_thread.start()
        logger.info("MGR_SETUP_WORKER: New AI Chatbot worker thread started.")
        self.statusUpdate.emit("Status: AI Assistant Ready.")


    @pyqtSlot(str, bool)
    def _handle_worker_response(self, ai_response_content: str, was_fsm_generation_attempt: bool):
        logger.info(f"MGR_HANDLE_WORKER_RESPONSE: Received from worker. Was FSM attempt: {was_fsm_generation_attempt}")

        if was_fsm_generation_attempt:
            try:
                fsm_data = json.loads(ai_response_content)
                if isinstance(fsm_data, dict) and ('states' in fsm_data or 'transitions' in fsm_data):
                    logger.info("MGR_HANDLE_WORKER_RESPONSE: Parsed FSM JSON successfully. Emitting fsmDataReceived.")
                    source_desc = self.last_fsm_request_description or "AI Generated FSM"
                    self.fsmDataReceived.emit(fsm_data, source_desc)
                    return
                else:
                    logger.warning("MGR_HANDLE_WORKER_RESPONSE: JSON parsed but not valid FSM structure. Treating as plain text.")
                    self.errorOccurred.emit("AI returned JSON, but it's not a valid FSM structure. Displaying as text.")
            except json.JSONDecodeError:
                logger.warning("MGR_HANDLE_WORKER_RESPONSE: Failed to parse AI response as JSON. Treating as plain text.", exc_info=True)
                self.statusUpdate.emit("Status: AI response was not valid FSM JSON.")

        logger.debug("MGR_HANDLE_WORKER_RESPONSE: Emitting plainResponseReady.")
        self.plainResponseReady.emit(ai_response_content)


    def _prepare_and_send_to_worker(self, user_message_text: str, is_fsm_gen_specific: bool = False):
        logger.info(f"MGR_PREP_SEND: For: '{user_message_text[:30]}...', FSM_specific_req: {is_fsm_gen_specific}")

        if not self.api_key:
            logger.warning("MGR_PREP_SEND: API Key not set.")
            self.errorOccurred.emit("API Key not set. Configure in Settings.")
            if self.parent_window and hasattr(self.parent_window, '_append_to_ai_chat_display'):
                self.parent_window._append_to_ai_chat_display("System Error", "API Key not set.")
            return

        if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
            logger.warning("MGR_PREP_SEND: Worker/Thread not ready.")
            if self.api_key and (not self.chatbot_thread or not self.chatbot_thread.isRunning()):
                 logger.info("MGR_PREP_SEND: Attempting to re-setup worker.")
                 self._setup_worker() 
            
            if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
                self.errorOccurred.emit("AI Assistant is not ready. Please wait or check settings.")
                if self.parent_window and hasattr(self.parent_window, '_append_to_ai_chat_display'):
                    self.parent_window._append_to_ai_chat_display("System Error", "AI Assistant is not ready.")
                return

        if is_fsm_gen_specific:
            self.last_fsm_request_description = user_message_text
        else:
            self.last_fsm_request_description = None 

        diagram_json_str: str | None = None 
        if self.parent_window and hasattr(self.parent_window, 'scene') and hasattr(self.parent_window.scene, 'get_diagram_data'):
            try:
                diagram_data = self.parent_window.scene.get_diagram_data()
                diagram_json_str = json.dumps(diagram_data)
            except Exception as e:
                logger.error(f"MGR_PREP_SEND: Error getting diagram data: {e}", exc_info=True)
                diagram_json_str = json.dumps({"error": "Could not retrieve diagram context."})
        else: 
             diagram_json_str = json.dumps({"error": "Diagram context unavailable."})

        if self.chatbot_worker: 
            # Ensure string is passed to slot expecting string
            effective_diagram_json_str = diagram_json_str if diagram_json_str is not None else ""
            
            # Fixed QMetaObject.invokeMethod calls using Q_ARG instead of QGenericArgument
            QMetaObject.invokeMethod(self.chatbot_worker, "set_diagram_context_slot", Qt.QueuedConnection, 
                                     Q_ARG(str, effective_diagram_json_str))

            QMetaObject.invokeMethod(self.chatbot_worker, "process_message_slot", Qt.QueuedConnection,
                                     Q_ARG(str, user_message_text), 
                                     Q_ARG(bool, is_fsm_gen_specific))
            
            logger.debug("MGR_PREP_SEND: Methods queued for worker.")
            if hasattr(self.parent_window, '_update_ai_chat_status'): 
                self.parent_window._update_ai_chat_status("Status: Sending to AI...")
        else:
            logger.error("MGR_PREP_SEND: Chatbot worker is None, cannot queue methods.")
            self.errorOccurred.emit("AI Assistant encountered an internal error (worker missing). Please try restarting AI features.")


    def send_message(self, user_message_text: str):
        self._prepare_and_send_to_worker(user_message_text, is_fsm_gen_specific=False)

    def generate_fsm_from_description(self, description: str):
         self._prepare_and_send_to_worker(description, is_fsm_gen_specific=True)

    def clear_conversation_history(self):
        logger.info("MGR: clear_conversation_history CALLED.")
        if self.chatbot_worker and self.chatbot_thread and self.chatbot_thread.isRunning():
            QMetaObject.invokeMethod(self.chatbot_worker, "clear_history_slot", Qt.QueuedConnection)
            logger.debug("MGR: clear_history invoked on worker.")
        else:
            self.statusUpdate.emit("Status: Chatbot not active (history is in worker).")
            logger.warning("MGR: Chatbot not active, cannot clear history from worker.")


    def stop_chatbot(self):
        logger.info("MGR_STOP: stop_chatbot CALLED.")
        self._cleanup_existing_worker_and_thread()
        self.statusUpdate.emit("Status: AI Assistant Stopped.")
        logger.info("MGR_STOP: Chatbot stopped and cleaned up.")

    def set_online_status(self, is_online: bool):
        logger.info(f"MGR_NET_STATUS: Online status: {is_online}")
        if self.api_key:
            if is_online:
                self.statusUpdate.emit("Status: Online and Ready.")
                if not self.chatbot_thread or not self.chatbot_thread.isRunning():
                    logger.info("MGR_NET_STATUS: Network online, API key present, attempting worker setup.")
                    self._setup_worker()
            else:
                self.statusUpdate.emit("Status: Offline. AI features unavailable.")
        else: 
            if is_online:
                self.statusUpdate.emit("Status: Online, API Key required.")
            else:
                self.statusUpdate.emit("Status: Offline, API Key required.")
                
from PyQt5.QtGui import QColor

# --- Configuration ---
APP_VERSION = "1.7.0" # Added Python FSM Simulation
APP_NAME = "Brain State Machine Designer"
FILE_EXTENSION = ".bsm"
FILE_FILTER = f"Brain State Machine Files (*{FILE_EXTENSION});;All Files (*)"

# --- Mechatronics/Embedded Snippets ---
MECHATRONICS_COMMON_ACTIONS = {
    "Digital Output (High)": "set_digital_output(PIN_NUMBER, 1); % Set pin HIGH",
    "Digital Output (Low)": "set_digital_output(PIN_NUMBER, 0); % Set pin LOW",
    "Read Digital Input": "input_value = read_digital_input(PIN_NUMBER);",
    "Set PWM Duty Cycle": "set_pwm_duty_cycle(PWM_CHANNEL, DUTY_VALUE_0_255);",
    "Read Analog Input": "sensor_value = read_adc_channel(ADC_CHANNEL);",
    "Start Timer": "start_software_timer(TIMER_ID, DURATION_MS);",
    "Stop Timer": "stop_software_timer(TIMER_ID);",
    "Increment Counter": "counter_variable = counter_variable + 1;",
    "Reset Counter": "counter_variable = 0;",
    "Set Variable": "my_variable = NEW_VALUE;",
    "Log Message": "log_event('Event description or variable_value');",
    "Send CAN Message": "send_can_message(CAN_ID, [BYTE1, BYTE2, BYTE3]);",
    "Set Motor Speed": "set_motor_speed(MOTOR_ID, SPEED_VALUE);",
    "Set Motor Position": "set_motor_position(MOTOR_ID, POSITION_TARGET);",
    "Open Solenoid Valve": "control_solenoid(VALVE_ID, VALVE_OPEN_CMD);",
    "Close Solenoid Valve": "control_solenoid(VALVE_ID, VALVE_CLOSE_CMD);",
    "Enable Component": "enable_subsystem(SUBSYSTEM_X, true);",
    "Disable Component": "enable_subsystem(SUBSYSTEM_X, false);",
    "Acknowledge Fault": "fault_acknowledged_flag = true;",
}

MECHATRONICS_COMMON_EVENTS = {
    "Timer Timeout": "timeout(TIMER_ID)",
    "Button Press": "button_pressed(BUTTON_NUMBER)",
    "Sensor Threshold Breach": "sensor_threshold(SENSOR_NAME)",
    "Data Packet Received": "data_reception_complete(CHANNEL)",
    "Emergency Stop Active": "emergency_stop",
    "Rising Edge Detection": "positive_edge(SIGNAL_NAME)",
    "Falling Edge Detection": "negative_edge(SIGNAL_NAME)",
    "Message Received": "msg_arrived(MSG_TYPE_ID)",
    "System Error Occurred": "system_fault(FAULT_CODE)",
    "User Input Event": "user_command(COMMAND_CODE)",
}

MECHATRONICS_COMMON_CONDITIONS = {
    "Is System Safe": "is_safety_interlock_active() == false",
    "Is Mode Nominal": "get_operating_mode() == NOMINAL_MODE",
    "Counter Reached Limit": "retry_counter >= MAX_RETRIES",
    "Variable is Value": "my_control_variable == TARGET_STATE_VALUE",
    "Flag is True": "is_ready_flag == true",
    "Flag is False": "is_busy_flag == false",
    "Battery Level OK": "get_battery_voltage_mv() > MINIMUM_OPERATING_VOLTAGE_MV",
    "Communication Healthy": "is_communication_link_up() == true",
    "Sensor Value In Range": "(sensor_data >= SENSOR_MIN_VALID && sensor_data <= SENSOR_MAX_VALID)",
    "Target Reached": "abs(current_position - target_position) < POSITION_TOLERANCE",
    "Input Signal High": "read_digital_input(PIN_FOR_CONDITION) == 1",
    "Input Signal Low": "read_digital_input(PIN_FOR_CONDITION) == 0",
}


# --- UI Styling and Theme Colors ---
COLOR_BACKGROUND_LIGHT = "#F5F5F5"
COLOR_BACKGROUND_MEDIUM = "#EEEEEE"
COLOR_BACKGROUND_DARK = "#E0E0E0"
COLOR_BACKGROUND_DIALOG = "#FFFFFF"
COLOR_TEXT_PRIMARY = "#212121"
COLOR_TEXT_SECONDARY = "#757575"
COLOR_TEXT_ON_ACCENT = "#FFFFFF"
COLOR_ACCENT_PRIMARY = "#1976D2" # Primary definition
COLOR_ACCENT_PRIMARY_LIGHT = "#BBDEFB"
COLOR_ACCENT_SECONDARY = "#FF8F00"
COLOR_ACCENT_SECONDARY_LIGHT = "#FFECB3"
COLOR_BORDER_LIGHT = "#CFD8DC"
COLOR_BORDER_MEDIUM = "#90A4AE"
COLOR_BORDER_DARK = "#607D8B"
COLOR_ITEM_STATE_DEFAULT_BG = "#E3F2FD"
COLOR_ITEM_STATE_DEFAULT_BORDER = "#90CAF9"
COLOR_ITEM_STATE_SELECTION = "#FFD54F"
COLOR_ITEM_TRANSITION_DEFAULT = "#009688"
COLOR_ITEM_TRANSITION_SELECTION = "#80CBC4"
COLOR_ITEM_COMMENT_BG = "#FFFDE7"
COLOR_ITEM_COMMENT_BORDER = "#FFF59D"
COLOR_GRID_MINOR = "#ECEFF1"
COLOR_GRID_MAJOR = "#CFD8DC"
# --- NEW PYTHON SIMULATION HIGHLIGHT COLORS ---
COLOR_PY_SIM_STATE_ACTIVE = QColor("#4CAF50")  # Green for active state
COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH = 2.5

APP_FONT_FAMILY = "Segoe UI, Arial, sans-serif"
STYLE_SHEET_GLOBAL = f"""
    QWidget {{
        font-family: {APP_FONT_FAMILY};
        font-size: 9pt;
    }}
    QMainWindow {{
        background-color: {COLOR_BACKGROUND_LIGHT};
    }}
    QDockWidget::title {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        padding: 6px 8px;
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom: 2px solid {COLOR_ACCENT_PRIMARY};
        font-weight: bold;
        color: {COLOR_TEXT_PRIMARY};
    }}
    QDockWidget::close-button, QDockWidget::float-button {{
        subcontrol-position: top right;
        subcontrol-origin: margin;
        position: absolute;
        top: 0px; right: 5px;
    }}
    QToolBar {{
        background-color: {COLOR_BACKGROUND_DARK};
        border: none;
        padding: 3px;
        spacing: 4px;
    }}
    QToolButton {{
        background-color: transparent;
        color: {COLOR_TEXT_PRIMARY};
        padding: 5px 7px;
        margin: 1px;
        border: 1px solid transparent;
        border-radius: 4px;
    }}
    QToolBar QToolButton:hover {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QToolBar QToolButton:pressed {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}
    QToolBar QToolButton:checked {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
        border: 1px solid #0D47A1;
    }}
    QMenuBar {{
        background-color: {COLOR_BACKGROUND_DARK};
        color: {COLOR_TEXT_PRIMARY};
        border-bottom: 1px solid {COLOR_BORDER_LIGHT};
        padding: 2px;
    }}
    QMenuBar::item {{
        background-color: transparent;
        padding: 5px 12px;
    }}
    QMenuBar::item:selected {{
        background-color: {COLOR_ACCENT_PRIMARY_LIGHT};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QMenuBar::item:pressed {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}
    QMenu {{
        background-color: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 2px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 28px 6px 28px;
        border-radius: 3px;
    }}
    QMenu::item:selected {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
    }}
    QMenu::separator {{
        height: 1px;
        background: {COLOR_BORDER_LIGHT};
        margin: 4px 8px;
    }}
    QMenu::icon {{
        padding-left: 5px;
    }}
    QStatusBar {{
        background-color: {COLOR_BACKGROUND_DARK};
        color: {COLOR_TEXT_PRIMARY};
        border-top: 1px solid {COLOR_BORDER_LIGHT};
        padding: 2px;
    }}
    QStatusBar::item {{
        border: none;
    }}
    QLabel#StatusLabel, QLabel#MatlabStatusLabel, QLabel#PySimStatusLabel {{
         padding: 0px 5px;
    }}
    QDialog {{
        background-color: {COLOR_BACKGROUND_DIALOG};
    }}
    QLabel {{
        color: {COLOR_TEXT_PRIMARY};
        background-color: transparent;
    }}
    QLineEdit, QTextEdit, QSpinBox, QComboBox, QTableWidget {{
        background-color: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 3px;
        padding: 5px 6px;
        font-size: 9pt;
    }}
    QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus, QTableWidget:focus {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 22px;
        border-left-width: 1px;
        border-left-color: {COLOR_BORDER_MEDIUM};
        border-left-style: solid;
        border-top-right-radius: 3px;
        border-bottom-right-radius: 3px;
    }}
    QComboBox::down-arrow {{
         image: url(./dependencies/icons/arrow_down.png);
         width: 10px; height:10px;
    }}
    QPushButton {{
        background-color: #E0E0E0;
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        padding: 6px 15px;
        border-radius: 3px;
        min-height: 20px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: #D6D6D6;
        border-color: {COLOR_BORDER_DARK};
    }}
    QPushButton:pressed {{
        background-color: #BDBDBD;
    }}
    QPushButton:disabled {{
        background-color: #F5F5F5;
        color: #BDBDBD;
        border-color: #EEEEEE;
    }}
    QDialogButtonBox QPushButton {{
        min-width: 85px;
    }}
    QDialogButtonBox QPushButton[text="OK"], QDialogButtonBox QPushButton[text="Apply & Close"] {{
        background-color: {COLOR_ACCENT_PRIMARY};
        color: {COLOR_TEXT_ON_ACCENT};
        border-color: #0D47A1;
    }}
    QDialogButtonBox QPushButton[text="OK"]:hover, QDialogButtonBox QPushButton[text="Apply & Close"]:hover {{
        background-color: #1E88E5;
    }}
    QGroupBox {{
        background-color: {COLOR_BACKGROUND_LIGHT};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-radius: 5px;
        margin-top: 10px;
        padding: 10px 8px 8px 8px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        left: 10px;
        color: {COLOR_ACCENT_PRIMARY};
        font-weight: bold;
    }}
    QTabWidget::pane {{
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-radius: 4px;
        background-color: {COLOR_BACKGROUND_DIALOG};
        padding: 5px;
    }}
    QTabBar::tab {{
        background: {COLOR_BACKGROUND_DARK};
        color: {COLOR_TEXT_SECONDARY};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        padding: 7px 15px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background: {COLOR_BACKGROUND_DIALOG};
        color: {COLOR_TEXT_PRIMARY};
        border-color: {COLOR_BORDER_LIGHT};
        font-weight: bold;
    }}
    QTabBar::tab:!selected:hover {{
        background: {COLOR_ACCENT_PRIMARY_LIGHT};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QCheckBox {{
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 15px;
        height: 15px;
    }}
    QCheckBox::indicator:unchecked {{
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 3px;
        background-color: {COLOR_BACKGROUND_DIALOG};
    }}
    QCheckBox::indicator:unchecked:hover {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QCheckBox::indicator:checked {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
        border-radius: 3px;
        background-color: {COLOR_ACCENT_PRIMARY};
    }}
    QTextEdit#LogOutputWidget, QTextEdit#PySimActionLog {{
         font-family: Consolas, 'Courier New', monospace;
         background-color: #263238;
         color: #CFD8DC;
         border: 1px solid #37474F;
         border-radius: 3px;
         padding: 5px;
    }}
    QScrollBar:vertical {{
         border: 1px solid {COLOR_BORDER_LIGHT}; background: {COLOR_BACKGROUND_LIGHT};
         width: 14px; margin: 0px;
    }}
    QScrollBar::handle:vertical {{
         background: {COLOR_BORDER_MEDIUM}; min-height: 25px; border-radius: 7px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
         height: 0px; background: transparent;
    }}
    QScrollBar:horizontal {{
         border: 1px solid {COLOR_BORDER_LIGHT}; background: {COLOR_BACKGROUND_LIGHT};
         height: 14px; margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
         background: {COLOR_BORDER_MEDIUM}; min-width: 25px; border-radius: 7px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
         width: 0px; background: transparent;
    }}
    QPushButton#SnippetButton {{
        background-color: {COLOR_ACCENT_SECONDARY}; color: {COLOR_TEXT_ON_ACCENT};
        border: 1px solid #E65100; font-weight: normal;
    }}
    QPushButton#SnippetButton:hover {{
        background-color: #FFA000;
    }}
    QPushButton#ColorButton {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; min-height: 24px; padding: 3px;
    }}
    QPushButton#ColorButton:hover {{
        border: 1px solid {COLOR_ACCENT_PRIMARY};
    }}
    QProgressBar {{
        border: 1px solid {COLOR_BORDER_MEDIUM}; border-radius: 4px;
        background-color: {COLOR_BACKGROUND_LIGHT}; text-align: center;
        color: {COLOR_TEXT_PRIMARY}; height: 12px;
    }}
    QProgressBar::chunk {{
        background-color: {COLOR_ACCENT_PRIMARY}; border-radius: 3px;
    }}
    QPushButton#DraggableToolButton {{
        background-color: #E8EAF6; color: {COLOR_TEXT_PRIMARY};
        border: 1px solid #C5CAE9; padding: 8px 10px;
        border-radius: 4px; text-align: left; font-weight: 500;
    }}
    QPushButton#DraggableToolButton:hover {{
        background-color: #B9D9EB; border-color: {COLOR_ACCENT_PRIMARY};
    }}
    QPushButton#DraggableToolButton:pressed {{ background-color: #98BAD6; }}
    #PropertiesDock QLabel {{
        padding: 6px; background-color: {COLOR_BACKGROUND_DIALOG};
        border: 1px solid {COLOR_BORDER_LIGHT}; border-radius: 3px; line-height: 1.4;
    }}
    #PropertiesDock QPushButton {{
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT};
    }}
    #PropertiesDock QPushButton:hover {{ background-color: #1E88E5; }}
    QDockWidget#ToolsDock QToolButton {{
        padding: 6px 8px; text-align: left;
    }}
    QDockWidget#ToolsDock QToolButton:checked {{
        background-color: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_ON_ACCENT};
        border: 1px solid #0D47A1;
    }}
    QDockWidget#PySimDock QPushButton {{
        padding: 5px 10px;
    }}
    QDockWidget#PySimDock QPushButton:disabled {{
        background-color: #E0E0E0;
        color: #9E9E9E;
    }}
    QDockWidget#PySimDock QTableWidget {{
        alternate-background-color: {COLOR_BACKGROUND_LIGHT};
        gridline-color: {COLOR_BORDER_LIGHT};
    }}
     QDockWidget#PySimDock QHeaderView::section {{
        background-color: {COLOR_BACKGROUND_MEDIUM};
        padding: 4px;
        border: 1px solid {COLOR_BORDER_LIGHT};
        font-weight: bold;
    }}
"""


# bsm_designer_project/dialogs.py

import sys
import json
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QCheckBox, QPushButton, QTextEdit,
    QSpinBox, QComboBox, QDialogButtonBox, QColorDialog, QHBoxLayout,
    QLabel, QFileDialog, QGroupBox, QMenu, QAction, QVBoxLayout, QStyle,
    QMessageBox, QInputDialog, QGraphicsView, QUndoStack, QToolBar, QActionGroup
)
from PyQt5.QtGui import QColor, QIcon, QPalette
from PyQt5.QtCore import Qt, QDir, QSize, QPointF

from config import (
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_ON_ACCENT, MECHATRONICS_COMMON_ACTIONS, MECHATRONICS_COMMON_EVENTS,
    MECHATRONICS_COMMON_CONDITIONS, COLOR_ACCENT_PRIMARY
)
from utils import get_standard_icon
from matlab_integration import MatlabConnection

try:
    from graphics_scene import DiagramScene, ZoomableView
    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    print(f"SubFSMEditorDialog: Could not import DiagramScene/ZoomableView: {e}. Visual sub-editor will be disabled.")
    DiagramScene = None
    ZoomableView = None
    IMPORTS_SUCCESSFUL = False


class SubFSMEditorDialog(QDialog): # Unchanged from previous correct version
    def __init__(self, sub_fsm_data_initial: dict, parent_state_name: str, parent_window_ref=None):
        super().__init__(parent_window_ref)
        self.parent_window_ref = parent_window_ref
        self.setWindowTitle(f"Sub-Machine Editor: {parent_state_name}")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogDetailedView, "SubEdit"))
        self.setMinimumSize(800, 600)

        self.current_sub_fsm_data = sub_fsm_data_initial

        layout = QVBoxLayout(self)

        if IMPORTS_SUCCESSFUL:
            self.sub_undo_stack = QUndoStack(self)
            self.sub_scene = DiagramScene(self.sub_undo_stack, parent_window=self)
            self.sub_view = ZoomableView(self.sub_scene, self)
            toolbar = QToolBar("Sub-Editor Tools")
            toolbar.setIconSize(QSize(18,18))
            self.sub_mode_action_group = QActionGroup(self)
            self.sub_mode_action_group.setExclusive(True)
            actions_data = [
                ("select", "Select/Move", QStyle.SP_ArrowRight, "SelSub"),
                ("state", "Add State", QStyle.SP_FileDialogNewFolder, "StSub"),
                ("transition", "Add Transition", QStyle.SP_ArrowForward, "TrSub"),
                ("comment", "Add Comment", QStyle.SP_MessageBoxInformation, "CmSub")
            ]
            for mode, text, icon_enum, icon_alt in actions_data:
                action = QAction(get_standard_icon(icon_enum, icon_alt), text, self)
                action.setCheckable(True)
                action.triggered.connect(lambda checked=False, m=mode: self.sub_scene.set_mode(m))
                toolbar.addAction(action)
                self.sub_mode_action_group.addAction(action)
                setattr(self, f"sub_{mode}_action", action) # Store for easy access

            toolbar.addSeparator()
            self.sub_undo_action = self.sub_undo_stack.createUndoAction(self, "Undo")
            self.sub_undo_action.setIcon(get_standard_icon(QStyle.SP_ArrowBack, "UnSub"))
            toolbar.addAction(self.sub_undo_action)
            self.sub_redo_action = self.sub_undo_stack.createRedoAction(self, "Redo")
            self.sub_redo_action.setIcon(get_standard_icon(QStyle.SP_ArrowForward, "ReSub"))
            toolbar.addAction(self.sub_redo_action)

            layout.addWidget(toolbar)
            layout.addWidget(self.sub_view, 1)
            self.sub_scene.load_diagram_data(self.current_sub_fsm_data)
            self.sub_undo_stack.clear()
            self.sub_scene.set_dirty(False)
            self.sub_select_action.setChecked(True) # type: ignore
            self.sub_scene.set_mode("select")
            self.status_label = QLabel("Visually edit the sub-machine. Click OK to save changes to the parent state.")
        else:
            self.json_edit_label = QLabel("Sub-Machine Data (JSON - Visual Editor Failed to Load):")
            layout.addWidget(self.json_edit_label)
            self.json_text_edit = QTextEdit()
            self.json_text_edit.setPlainText(json.dumps(self.current_sub_fsm_data, indent=2, ensure_ascii=False))
            self.json_text_edit.setAcceptRichText(False); self.json_text_edit.setLineWrapMode(QTextEdit.NoWrap)
            layout.addWidget(self.json_text_edit, 1)
            self.status_label = QLabel("Hint: A full visual editor for sub-machines would replace this JSON view.")

        layout.addWidget(self.status_label)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_changes); button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept_changes(self): # Unchanged from previous version
        if IMPORTS_SUCCESSFUL and hasattr(self, 'sub_scene'):
            updated_data = self.sub_scene.get_diagram_data()
            if isinstance(updated_data, dict) and \
               all(k in updated_data for k in ['states', 'transitions', 'comments']) and \
               isinstance(updated_data.get('states'), list) and \
               isinstance(updated_data.get('transitions'), list) and \
               isinstance(updated_data.get('comments'), list):
                if updated_data.get('states'):
                    has_initial = any(s.get('is_initial', False) for s in updated_data.get('states', []))
                    if not has_initial:
                        reply = QMessageBox.question(self, "No Initial Sub-State",
                                                     "The sub-machine does not have an initial state defined. "
                                                     "It's recommended to define one for predictable behavior. "
                                                     "Continue saving?",
                                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                        if reply == QMessageBox.No: return
                self.current_sub_fsm_data = updated_data; self.accept()
            else: QMessageBox.warning(self, "Invalid Sub-Machine Structure", "Unexpected sub-machine editor data structure.")
        else:
            try:
                parsed_new_data = json.loads(self.json_text_edit.toPlainText()) # type: ignore
                if isinstance(parsed_new_data, dict) and all(k in parsed_new_data for k in ['states', 'transitions', 'comments']):
                    self.current_sub_fsm_data = parsed_new_data; self.accept()
                else: QMessageBox.warning(self, "Invalid JSON Structure", "JSON needs 'states', 'transitions', 'comments' lists.")
            except json.JSONDecodeError as e: QMessageBox.warning(self, "JSON Parse Error", f"Could not parse JSON: {e}")

    def get_updated_sub_fsm_data(self) -> dict: return self.current_sub_fsm_data # Unchanged
    def log_message(self, level, message): # Unchanged
        print(f"SubFSMEditor Log ({level}): {message}")
        if self.parent_window_ref and hasattr(self.parent_window_ref, 'log_message'):
             self.parent_window_ref.log_message(level, f"[SubEditor] {message}")


class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False, scene_ref=None):
        super().__init__(parent)
        self.setWindowTitle("State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "Props"))
        self.setMinimumWidth(480)

        self.parent_window_ref = parent
        self.scene_ref = scene_ref

        layout = QFormLayout(self)
        layout.setSpacing(10) # Increased spacing a bit
        layout.setContentsMargins(12,12,12,12)

        p = current_properties or {}

        self.name_edit = QLineEdit(p.get('name', "StateName"))
        # ... (name_edit, is_initial_cb, is_final_cb, color_button setup as before) ...
        self.is_initial_cb = QCheckBox("Is Initial State"); self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Is Final State"); self.is_final_cb.setChecked(p.get('is_final', False))
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton")
        self.current_color = QColor(p.get('color', COLOR_ITEM_STATE_DEFAULT_BG)); self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)

        self.is_superstate_cb = QCheckBox("Is Superstate (Composite State)")
        self.is_superstate_cb.setChecked(p.get('is_superstate', False))
        self.is_superstate_cb.toggled.connect(self._on_superstate_toggled)
        self.edit_sub_fsm_button = QPushButton(get_standard_icon(QStyle.SP_FileDialogDetailedView, "Sub"), "Edit Sub-Machine...")
        self.edit_sub_fsm_button.clicked.connect(self._on_edit_sub_fsm)
        self.edit_sub_fsm_button.setEnabled(self.is_superstate_cb.isChecked())
        raw_sub_fsm_data = p.get('sub_fsm_data', {})
        self.current_sub_fsm_data = raw_sub_fsm_data if isinstance(raw_sub_fsm_data, dict) and all(k in raw_sub_fsm_data for k in ['states', 'transitions', 'comments']) else {'states': [], 'transitions': [], 'comments': []}


        self.entry_action_edit = QTextEdit(p.get('entry_action', "")); self.entry_action_edit.setFixedHeight(65)
        self.during_action_edit = QTextEdit(p.get('during_action', "")); self.during_action_edit.setFixedHeight(65)
        self.exit_action_edit = QTextEdit(p.get('exit_action', "")); self.exit_action_edit.setFixedHeight(65)
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75)

        entry_action_btn = self._create_insert_snippet_button(self.entry_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        during_action_btn = self._create_insert_snippet_button(self.during_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        exit_action_btn = self._create_insert_snippet_button(self.exit_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")

        layout.addRow("Name:", self.name_edit)
        cb_layout = QHBoxLayout(); cb_layout.addWidget(self.is_initial_cb); cb_layout.addWidget(self.is_final_cb); cb_layout.addStretch()
        layout.addRow("", cb_layout)
        layout.addRow("Color:", self.color_button)
        cb_layout_super = QHBoxLayout(); cb_layout_super.addWidget(self.is_superstate_cb); cb_layout_super.addWidget(self.edit_sub_fsm_button); cb_layout_super.addStretch()
        layout.addRow("Hierarchy:", cb_layout_super)

        # --- Updated add_field_with_note helper ---
        def add_field_with_note(form_layout, label_text, text_edit_widget, snippet_button):
            h_editor_btn_layout = QHBoxLayout()
            h_editor_btn_layout.setSpacing(5)
            h_editor_btn_layout.addWidget(text_edit_widget, 1) # Text edit takes most space
            
            v_btn_container = QVBoxLayout()
            v_btn_container.addWidget(snippet_button)
            v_btn_container.addStretch() # Push button to top if space allows
            h_editor_btn_layout.addLayout(v_btn_container)

            safety_note_label = QLabel("<small><i>Note: Python code runs in a restricted environment.</i></small>")
            safety_note_label.setToolTip(
                "Code is checked for common unsafe operations (e.g., 'import os'). "
                "Review your code for correctness and unintended side effects."
            )
            safety_note_label.setStyleSheet("margin-top: 2px; color: grey;") # Minor styling

            field_v_layout = QVBoxLayout()
            field_v_layout.setSpacing(2) # Reduce spacing within this vertical group
            field_v_layout.addLayout(h_editor_btn_layout)
            field_v_layout.addWidget(safety_note_label)
            
            form_layout.addRow(label_text, field_v_layout)

        add_field_with_note(layout, "Entry Action:", self.entry_action_edit, entry_action_btn)
        add_field_with_note(layout, "During Action:", self.during_action_edit, during_action_btn)
        add_field_with_note(layout, "Exit Action:", self.exit_action_edit, exit_action_btn)
        # --- End of updated add_field_with_note ---

        layout.addRow("Description:", self.description_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addRow(btns)

        if is_new_state: self.name_edit.selectAll(); self.name_edit.setFocus()

    # _on_superstate_toggled, _on_edit_sub_fsm, _create_insert_snippet_button,
    # _choose_color, _update_color_button_style, get_properties methods remain UNCHANGED
    # from the previous correct version of StatePropertiesDialog.
    def _on_superstate_toggled(self, checked): # Unchanged
        self.edit_sub_fsm_button.setEnabled(checked)
        if not checked:
            if self.current_sub_fsm_data and \
               (self.current_sub_fsm_data.get('states') or self.current_sub_fsm_data.get('transitions')):
                reply = QMessageBox.question(self, "Discard Sub-Machine?",
                                             "Unchecking 'Is Superstate' will clear its internal diagram data. Continue?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.current_sub_fsm_data = {'states': [], 'transitions': [], 'comments': []}
                else:
                    self.is_superstate_cb.setChecked(True)

    def _on_edit_sub_fsm(self): # Unchanged
        parent_state_name = self.name_edit.text().strip() or "Unnamed Superstate"
        dialog_parent = self if not isinstance(self.parent_window_ref, SubFSMEditorDialog) else self.parent_window_ref
        sub_editor_dialog = SubFSMEditorDialog(self.current_sub_fsm_data, parent_state_name, dialog_parent)
        if sub_editor_dialog.exec() == QDialog.Accepted:
            updated_data = sub_editor_dialog.get_updated_sub_fsm_data()
            self.current_sub_fsm_data = updated_data
            QMessageBox.information(self, "Sub-Machine Updated",
                                    "Sub-machine data has been updated in this dialog. "
                                    "Click OK to save these changes to the state.")

    def _create_insert_snippet_button(self, target_widget: QTextEdit, snippets_dict: dict, button_text="Insert...", icon_size_px=14): # Unchanged
        button = QPushButton(button_text); button.setObjectName("SnippetButton")
        button.setToolTip("Insert common snippets"); button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ins"))
        button.setIconSize(QSize(icon_size_px + 2, icon_size_px + 2))
        menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n"))
            menu.addAction(action)
        button.setMenu(menu); return button

    def _choose_color(self): # Unchanged
        color = QColorDialog.getColor(self.current_color, self, "Select State Color")
        if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self): # Unchanged
        luminance = self.current_color.lightnessF()
        text_color = COLOR_TEXT_PRIMARY if luminance > 0.5 else COLOR_TEXT_ON_ACCENT
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color};")

    def get_properties(self): # Unchanged
        sub_data_to_return = {'states': [], 'transitions': [], 'comments': []}
        if self.is_superstate_cb.isChecked():
            sub_data_to_return = self.current_sub_fsm_data
        return {
            'name': self.name_edit.text().strip(), 'is_initial': self.is_initial_cb.isChecked(),
            'is_final': self.is_final_cb.isChecked(), 'color': self.current_color.name(),
            'entry_action': self.entry_action_edit.toPlainText().strip(),
            'during_action': self.during_action_edit.toPlainText().strip(),
            'exit_action': self.exit_action_edit.toPlainText().strip(),
            'description': self.description_edit.toPlainText().strip(),
            'is_superstate': self.is_superstate_cb.isChecked(), 'sub_fsm_data': sub_data_to_return
        }


class TransitionPropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent)
        self.setWindowTitle("Transition Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogInfoView, "Props"))
        self.setMinimumWidth(520)

        layout = QFormLayout(self); layout.setSpacing(10); layout.setContentsMargins(12,12,12,12) # Increased spacing
        p = current_properties or {}

        self.event_edit = QLineEdit(p.get('event', ""))
        self.condition_edit = QLineEdit(p.get('condition', ""))
        self.action_edit = QTextEdit(p.get('action', "")); self.action_edit.setFixedHeight(65)
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton")
        self.current_color = QColor(p.get('color', COLOR_ITEM_TRANSITION_DEFAULT)); self._update_color_button_style()
        self.color_button.clicked.connect(self._choose_color)
        self.offset_perp_spin = QSpinBox(); self.offset_perp_spin.setRange(-1000, 1000); self.offset_perp_spin.setValue(int(p.get('control_offset_x', 0)))
        self.offset_tang_spin = QSpinBox(); self.offset_tang_spin.setRange(-1000, 1000); self.offset_tang_spin.setValue(int(p.get('control_offset_y', 0)))
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75)

        event_btn = self._create_insert_snippet_button_lineedit(self.event_edit, MECHATRONICS_COMMON_EVENTS, " Insert Event")
        condition_btn = self._create_insert_snippet_button_lineedit(self.condition_edit, MECHATRONICS_COMMON_CONDITIONS, " Insert Condition")
        action_btn = self._create_insert_snippet_button_qtextedit(self.action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")

        # --- Updated add_field_with_button_and_note helper ---
        def add_field_with_button_and_note(form_layout, label_text, edit_widget, snippet_button, is_code_field=True):
            h_editor_btn_layout = QHBoxLayout()
            h_editor_btn_layout.setSpacing(5)
            h_editor_btn_layout.addWidget(edit_widget, 1)
            
            v_btn_container = QVBoxLayout()
            v_btn_container.addWidget(snippet_button)
            v_btn_container.addStretch()
            h_editor_btn_layout.addLayout(v_btn_container)

            field_v_layout = QVBoxLayout()
            field_v_layout.setSpacing(2)
            field_v_layout.addLayout(h_editor_btn_layout)

            if is_code_field: # Add safety note only for fields that accept code
                safety_note_label = QLabel("<small><i>Note: Python code runs in a restricted environment.</i></small>")
                safety_note_label.setToolTip(
                    "Code is checked for common unsafe operations. Review your code for correctness."
                )
                safety_note_label.setStyleSheet("margin-top: 2px; color: grey;")
                field_v_layout.addWidget(safety_note_label)
            
            form_layout.addRow(label_text, field_v_layout)

        add_field_with_button_and_note(layout, "Event Trigger:", self.event_edit, event_btn, is_code_field=False) # Event is usually not arbitrary code
        add_field_with_button_and_note(layout, "Condition (Guard):", self.condition_edit, condition_btn, is_code_field=True)
        add_field_with_button_and_note(layout, "Transition Action:", self.action_edit, action_btn, is_code_field=True)
        # --- End of updated helper ---

        layout.addRow("Color:", self.color_button)
        curve_layout = QHBoxLayout()
        curve_layout.addWidget(QLabel("Bend (Perp):")); curve_layout.addWidget(self.offset_perp_spin); curve_layout.addSpacing(10)
        curve_layout.addWidget(QLabel("Mid Shift (Tang):")); curve_layout.addWidget(self.offset_tang_spin); curve_layout.addStretch()
        layout.addRow("Curve Shape:", curve_layout)
        layout.addRow("Description:", self.description_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        if is_new_transition: self.event_edit.setFocus()

    # _create_insert_snippet_button_lineedit, _create_insert_snippet_button_qtextedit,
    # _choose_color, _update_color_button_style, get_properties methods remain UNCHANGED
    # from the previous correct version of TransitionPropertiesDialog.
    def _create_insert_snippet_button_lineedit(self, target_line_edit: QLineEdit, snippets_dict: dict, button_text="Insert..."): # Unchanged
        button = QPushButton(button_text); button.setObjectName("SnippetButton")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins")); button.setIconSize(QSize(14+2,14+2))
        button.setToolTip("Insert common snippets."); menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            def insert_logic(checked=False, line_edit=target_line_edit, s=snippet):
                current_text = line_edit.text(); cursor_pos = line_edit.cursorPosition()
                new_text = current_text[:cursor_pos] + s + current_text[cursor_pos:]
                line_edit.setText(new_text); line_edit.setCursorPosition(cursor_pos + len(s))
            action.triggered.connect(insert_logic); menu.addAction(action)
        button.setMenu(menu); return button

    def _create_insert_snippet_button_qtextedit(self, target_text_edit: QTextEdit, snippets_dict: dict, button_text="Insert..."): # Unchanged
        button = QPushButton(button_text); button.setObjectName("SnippetButton")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins")); button.setIconSize(QSize(14+2,14+2))
        button.setToolTip("Insert common snippets."); menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, text_edit=target_text_edit, s=snippet: text_edit.insertPlainText(s + "\n"))
            menu.addAction(action)
        button.setMenu(menu); return button

    def _choose_color(self): # Unchanged
        color = QColorDialog.getColor(self.current_color, self, "Select Transition Color")
        if color.isValid(): self.current_color = color; self._update_color_button_style()

    def _update_color_button_style(self): # Unchanged
        luminance = self.current_color.lightnessF()
        text_color = COLOR_TEXT_PRIMARY if luminance > 0.5 else COLOR_TEXT_ON_ACCENT
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color};")

    def get_properties(self): # Unchanged
        return {
            'event': self.event_edit.text().strip(), 'condition': self.condition_edit.text().strip(),
            'action': self.action_edit.toPlainText().strip(), 'color': self.current_color.name(),
            'control_offset_x': self.offset_perp_spin.value(), 'control_offset_y': self.offset_tang_spin.value(),
            'description': self.description_edit.toPlainText().strip()
        }


class CommentPropertiesDialog(QDialog): # Unchanged
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent)
        self.setWindowTitle("Comment Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_MessageBoxInformation, "Cmt"))
        p = current_properties or {}; layout = QVBoxLayout(self)
        layout.setSpacing(8); layout.setContentsMargins(12,12,12,12)
        self.text_edit = QTextEdit(p.get('text', "Comment"))
        self.text_edit.setMinimumHeight(100); self.text_edit.setPlaceholderText("Enter your comment or note here.")
        layout.addWidget(QLabel("Comment Text:")); layout.addWidget(self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setMinimumWidth(380); self.text_edit.setFocus(); self.text_edit.selectAll()

    def get_properties(self):
        return {'text': self.text_edit.toPlainText()}


class MatlabSettingsDialog(QDialog): # Unchanged
    def __init__(self, matlab_connection: MatlabConnection, parent=None):
        super().__init__(parent)
        self.matlab_connection = matlab_connection
        self.setWindowTitle("MATLAB Settings"); self.setWindowIcon(get_standard_icon(QStyle.SP_ComputerIcon, "Cfg"))
        self.setMinimumWidth(580)
        main_layout = QVBoxLayout(self); main_layout.setSpacing(10); main_layout.setContentsMargins(10,10,10,10)
        path_group = QGroupBox("MATLAB Executable Path"); path_form_layout = QFormLayout()
        self.path_edit = QLineEdit(self.matlab_connection.matlab_path)
        self.path_edit.setPlaceholderText("e.g., C:\\...\\MATLAB\\R202Xy\\bin\\matlab.exe")
        path_form_layout.addRow("Path:", self.path_edit)
        btn_layout = QHBoxLayout(); btn_layout.setSpacing(6)
        auto_detect_btn = QPushButton(get_standard_icon(QStyle.SP_BrowserReload,"Det"), " Auto-detect")
        auto_detect_btn.clicked.connect(self._auto_detect); auto_detect_btn.setToolTip("Attempt to find MATLAB installations.")
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw"), " Browse...")
        browse_btn.clicked.connect(self._browse); browse_btn.setToolTip("Browse for MATLAB executable.")
        btn_layout.addWidget(auto_detect_btn); btn_layout.addWidget(browse_btn); btn_layout.addStretch()
        path_v_layout = QVBoxLayout(); path_v_layout.setSpacing(8)
        path_v_layout.addLayout(path_form_layout); path_v_layout.addLayout(btn_layout)
        path_group.setLayout(path_v_layout); main_layout.addWidget(path_group)
        test_group = QGroupBox("Connection Test"); test_layout = QVBoxLayout(); test_layout.setSpacing(8)
        self.test_status_label = QLabel("Status: Unknown"); self.test_status_label.setWordWrap(True)
        self.test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse); self.test_status_label.setMinimumHeight(30)
        test_btn = QPushButton(get_standard_icon(QStyle.SP_CommandLink,"Test"), " Test Connection")
        test_btn.clicked.connect(self._test_connection_and_update_label); test_btn.setToolTip("Test connection to the specified MATLAB path.")
        test_layout.addWidget(test_btn); test_layout.addWidget(self.test_status_label, 1)
        test_group.setLayout(test_layout); main_layout.addWidget(test_group)
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.button(QDialogButtonBox.Ok).setText("Apply & Close")
        dialog_buttons.accepted.connect(self._apply_settings); dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)
        self.matlab_connection.connectionStatusChanged.connect(self._update_test_label_from_signal)
        if self.matlab_connection.matlab_path and self.matlab_connection.connected:
             self._update_test_label_from_signal(True, f"Connected: {self.matlab_connection.matlab_path}")
        elif self.matlab_connection.matlab_path:
            self._update_test_label_from_signal(False, f"Path previously set, but connection unconfirmed or failed.")
        else: self._update_test_label_from_signal(False, "MATLAB path not set.")

    def _auto_detect(self): # Unchanged
        self.test_status_label.setText("Status: Auto-detecting MATLAB, please wait..."); self.test_status_label.setStyleSheet("")
        from PyQt5.QtWidgets import QApplication; QApplication.processEvents()
        self.matlab_connection.detect_matlab()

    def _browse(self): # Unchanged
        exe_filter = "MATLAB Executable (matlab.exe)" if sys.platform == 'win32' else "MATLAB Executable (matlab);;All Files (*)"
        start_dir = QDir.homePath()
        if self.path_edit.text() and QDir(QDir.toNativeSeparators(self.path_edit.text())).exists():
             path_obj = QDir(self.path_edit.text()); path_obj.cdUp(); start_dir = path_obj.absolutePath()
        path, _ = QFileDialog.getOpenFileName(self, "Select MATLAB Executable", start_dir, exe_filter)
        if path: self.path_edit.setText(path); self._update_test_label_from_signal(False, "Path changed. Click 'Test Connection' or 'Apply & Close'.")

    def _test_connection_and_update_label(self): # Unchanged
        path = self.path_edit.text().strip()
        if not path: self._update_test_label_from_signal(False, "MATLAB path is empty. Cannot test."); return
        self.test_status_label.setText("Status: Testing connection, please wait..."); self.test_status_label.setStyleSheet("")
        from PyQt5.QtWidgets import QApplication; QApplication.processEvents()
        if self.matlab_connection.set_matlab_path(path): self.matlab_connection.test_connection()

    def _update_test_label_from_signal(self, success, message): # Unchanged
        status_prefix = "Status: "; current_style = "font-weight: bold; padding: 3px;"
        if success:
            if "path set and appears valid" in message : status_prefix = "Status: Path seems valid. "
            elif "test successful" in message : status_prefix = "Status: Connected! "
            current_style += f"color: {COLOR_ACCENT_PRIMARY};"
        else: status_prefix = "Status: Error. "; current_style += f"color: #C62828;"
        self.test_status_label.setText(status_prefix + message); self.test_status_label.setStyleSheet(current_style)
        if success and self.matlab_connection.matlab_path and not self.path_edit.text():
            self.path_edit.setText(self.matlab_connection.matlab_path)

    def _apply_settings(self): # Unchanged
        path = self.path_edit.text().strip()
        if self.matlab_connection.matlab_path != path:
            self.matlab_connection.set_matlab_path(path)
            if path and not self.matlab_connection.connected : self.matlab_connection.test_connection()
        self.accept()
        
# bsm_designer_project/graphics_items.py

import math
from PyQt5.QtWidgets import (QGraphicsRectItem, QGraphicsPathItem, QGraphicsTextItem,
                             QGraphicsItem, QGraphicsDropShadowEffect, QApplication, QGraphicsSceneMouseEvent)
from PyQt5.QtGui import (QBrush, QColor, QFont, QPen, QPainterPath, QPolygonF, QPainter,
                         QPainterPathStroker, QPixmap, QMouseEvent, QDrag, QPalette)
from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QSize

from config import (COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_STATE_DEFAULT_BORDER, APP_FONT_FAMILY,
                    COLOR_TEXT_PRIMARY, COLOR_ITEM_STATE_SELECTION, COLOR_ITEM_TRANSITION_DEFAULT,
                    COLOR_ITEM_TRANSITION_SELECTION, COLOR_ITEM_COMMENT_BG, COLOR_ITEM_COMMENT_BORDER,
                    COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH,
                    COLOR_BACKGROUND_LIGHT, COLOR_BORDER_LIGHT, COLOR_ACCENT_PRIMARY)


class GraphicsStateItem(QGraphicsRectItem):
    Type = QGraphicsItem.UserType + 1

    def type(self): return GraphicsStateItem.Type

    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False,
                 color=None, entry_action="", during_action="", exit_action="", description="",
                 is_superstate=False, sub_fsm_data=None): # New parameters for hierarchy
        super().__init__(x, y, w, h)
        self.text_label = text
        self.is_initial = is_initial
        self.is_final = is_final
        self.is_superstate = is_superstate  # New attribute
        # Ensure sub_fsm_data is always a dict with the correct keys
        if sub_fsm_data and isinstance(sub_fsm_data, dict) and \
           all(k in sub_fsm_data for k in ['states', 'transitions', 'comments']):
            self.sub_fsm_data = sub_fsm_data
        else:
            self.sub_fsm_data = {'states': [], 'transitions': [], 'comments': []}

        self.base_color = QColor(color) if color else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        self.border_color = QColor(color).darker(120) if color else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)
        self.entry_action = entry_action
        self.during_action = during_action
        self.exit_action = exit_action
        self.description = description

        self._text_color = QColor(COLOR_TEXT_PRIMARY)
        self._font = QFont(APP_FONT_FAMILY, 10, QFont.Bold)
        self._border_pen_width = 1.5

        self.setPen(QPen(self.border_color, self._border_pen_width))
        self.setBrush(QBrush(self.base_color))

        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)

        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(10)
        self.shadow_effect.setColor(QColor(0, 0, 0, 60))
        self.shadow_effect.setOffset(2.5, 2.5)
        self.setGraphicsEffect(self.shadow_effect)

        self.is_py_sim_active = False
        self.original_pen_for_py_sim_restore = self.pen()

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        current_rect = self.rect()
        border_radius = 10

        current_pen_to_use = self.pen()
        if self.is_py_sim_active:
            py_sim_pen = QPen(COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH, Qt.DashLine)
            current_pen_to_use = py_sim_pen

        painter.setPen(current_pen_to_use)
        painter.setBrush(self.brush())
        painter.drawRoundedRect(current_rect, border_radius, border_radius)

        painter.setPen(self._text_color)
        painter.setFont(self._font)
        text_rect = current_rect.adjusted(8, 8, -8, -8)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)

        if self.is_initial:
            marker_radius = 6; line_length = 18; marker_color = Qt.black
            start_marker_center_x = current_rect.left() - line_length - marker_radius / 2
            start_marker_center_y = current_rect.center().y()
            painter.setBrush(marker_color)
            painter.setPen(QPen(marker_color, self._border_pen_width))
            painter.drawEllipse(QPointF(start_marker_center_x, start_marker_center_y), marker_radius, marker_radius)
            line_start_point = QPointF(start_marker_center_x + marker_radius, start_marker_center_y)
            line_end_point = QPointF(current_rect.left(), start_marker_center_y)
            painter.drawLine(line_start_point, line_end_point)
            arrow_size = 8; angle_rad = 0
            arrow_p1 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad + math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad + math.pi / 6))
            arrow_p2 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad - math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad - math.pi / 6))
            painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))

        if self.is_final: # No special handling for superstate final marker yet
            painter.setPen(QPen(self.border_color.darker(120), self._border_pen_width + 0.5))
            inner_rect = current_rect.adjusted(5, 5, -5, -5)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(inner_rect, border_radius - 3, border_radius - 3)

        if self.is_superstate:
            # Draw a simple indicator for superstate (e.g., small stacked rectangles icon)
            icon_size = 12
            icon_margin = 5
            icon_rect_base = QRectF(current_rect.right() - icon_size - icon_margin,
                                    current_rect.top() + icon_margin,
                                    icon_size, icon_size)
            
            painter.setPen(QPen(self.border_color.darker(150), 1))
            painter.setBrush(self.border_color.lighter(120))
            
            # Main rectangle of icon
            rect1 = QRectF(icon_rect_base.left(), icon_rect_base.top(), icon_rect_base.width(), icon_rect_base.height() * 0.7)
            painter.drawRect(rect1)
            # Shadow rectangle below
            rect2 = QRectF(icon_rect_base.left() + icon_rect_base.width() * 0.2, 
                           icon_rect_base.top() + icon_rect_base.height() * 0.3, 
                           icon_rect_base.width(), icon_rect_base.height() * 0.7)
            painter.setBrush(self.border_color.lighter(140)) # Slightly different color for overlap
            painter.drawRect(rect2)


        if self.isSelected() and not self.is_py_sim_active:
            selection_pen = QPen(QColor(COLOR_ITEM_STATE_SELECTION), self._border_pen_width + 1, Qt.SolidLine)
            selection_rect = self.boundingRect().adjusted(-1, -1, 1, 1)
            painter.setPen(selection_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(selection_rect, border_radius + 1, border_radius + 1)

    def set_py_sim_active_style(self, active: bool):
        if self.is_py_sim_active == active: return
        self.is_py_sim_active = active
        if active: self.original_pen_for_py_sim_restore = QPen(self.pen())
        else: self.setPen(self.original_pen_for_py_sim_restore)
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)

    def get_data(self):
        return {
            'name': self.text_label, 'x': self.x(), 'y': self.y(),
            'width': self.rect().width(), 'height': self.rect().height(),
            'is_initial': self.is_initial, 'is_final': self.is_final,
            'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_STATE_DEFAULT_BG).name(),
            'entry_action': self.entry_action, 'during_action': self.during_action,
            'exit_action': self.exit_action, 'description': self.description,
            'is_superstate': self.is_superstate,
            'sub_fsm_data': self.sub_fsm_data
        }

    def set_text(self, text):
        if self.text_label != text:
            self.prepareGeometryChange()
            self.text_label = text
            self.update()

    def set_properties(self, name, is_initial, is_final, color_hex=None,
                       entry="", during="", exit_a="", desc="",
                       is_superstate_prop=None, sub_fsm_data_prop=None): # Added hierarchy props
        changed = False
        if self.text_label != name: self.text_label = name; changed = True
        if self.is_initial != is_initial: self.is_initial = is_initial; changed = True
        if self.is_final != is_final: self.is_final = is_final; changed = True

        if is_superstate_prop is not None and self.is_superstate != is_superstate_prop:
            self.is_superstate = is_superstate_prop
            changed = True
        
        if sub_fsm_data_prop is not None:
            # Validate structure of sub_fsm_data_prop before assigning
            if isinstance(sub_fsm_data_prop, dict) and \
               all(k in sub_fsm_data_prop for k in ['states', 'transitions', 'comments']) and \
               isinstance(sub_fsm_data_prop['states'], list) and \
               isinstance(sub_fsm_data_prop['transitions'], list) and \
               isinstance(sub_fsm_data_prop['comments'], list):
                if self.sub_fsm_data != sub_fsm_data_prop:
                     self.sub_fsm_data = sub_fsm_data_prop
                     changed = True
            elif self.is_superstate: # If it's supposed to be a superstate but data is bad, log/warn
                print(f"Warning: Invalid sub_fsm_data provided for superstate '{name}'. Resetting to empty.")
                # Keep existing valid sub_fsm_data or reset, depending on desired behavior
                # self.sub_fsm_data = {'states': [], 'transitions': [], 'comments': []} # Option to reset
                # changed = True # If reset
                pass # Or simply ignore bad data and keep old

        new_base_color = QColor(color_hex) if color_hex else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        new_border_color = new_base_color.darker(120) if color_hex else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)

        if self.base_color != new_base_color:
            self.base_color = new_base_color
            self.border_color = new_border_color
            self.setBrush(self.base_color)
            new_pen = QPen(self.border_color, self._border_pen_width)
            if not self.is_py_sim_active: self.setPen(new_pen)
            self.original_pen_for_py_sim_restore = new_pen
            changed = True

        if self.entry_action != entry: self.entry_action = entry; changed = True
        if self.during_action != during: self.during_action = during; changed = True
        if self.exit_action != exit_a: self.exit_action = exit_a; changed = True
        if self.description != desc: self.description = desc; changed = True

        if changed:
            self.prepareGeometryChange()
            self.update()


class GraphicsTransitionItem(QGraphicsPathItem):
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type

    def __init__(self, start_item, end_item, event_str="", condition_str="", action_str="",
                 color=None, description=""):
        super().__init__()
        self.start_item: GraphicsStateItem | None = start_item
        self.end_item: GraphicsStateItem | None = end_item
        self.event_str = event_str
        self.condition_str = condition_str
        self.action_str = action_str
        self.base_color = QColor(color) if color else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        self.description = description
        self.arrow_size = 10

        self._text_color = QColor(COLOR_TEXT_PRIMARY)
        self._font = QFont(APP_FONT_FAMILY, 8)
        self.control_point_offset = QPointF(0,0)
        self._pen_width = 2.0

        self.setPen(QPen(self.base_color, self._pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1)
        self.setAcceptHoverEvents(True)
        self.update_path()

    def _compose_label_string(self):
        parts = []
        if self.event_str: parts.append(self.event_str)
        if self.condition_str: parts.append(f"[{self.condition_str}]")
        if self.action_str: parts.append(f"/{{{self.action_str}}}")
        return " ".join(parts)

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        self.setPen(QPen(self.base_color.lighter(130), self._pen_width + 0.5))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        self.setPen(QPen(self.base_color, self._pen_width))
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 25
        path_bounds = self.path().boundingRect()
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics
            fm = QFontMetrics(self._font)
            text_rect = fm.boundingRect(current_label)
            mid_point_on_path = self.path().pointAtPercent(0.5)
            text_render_rect = QRectF(mid_point_on_path.x() - text_rect.width() - 10,
                                    mid_point_on_path.y() - text_rect.height() - 10,
                                    text_rect.width()*2 + 20, text_rect.height()*2 + 20)
            path_bounds = path_bounds.united(text_render_rect)
        return path_bounds.adjusted(-extra, -extra, extra, extra)

    def shape(self):
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(18 + self.pen().widthF())
        path_stroker.setCapStyle(Qt.RoundCap)
        path_stroker.setJoinStyle(Qt.RoundJoin)
        return path_stroker.createStroke(self.path())

    def update_path(self):
        if not self.start_item or not self.end_item:
            self.setPath(QPainterPath())
            return

        start_center = self.start_item.sceneBoundingRect().center()
        end_center = self.end_item.sceneBoundingRect().center()

        line_to_target = QLineF(start_center, end_center)
        start_point = self._get_intersection_point(self.start_item, line_to_target)
        line_from_target = QLineF(end_center, start_center)
        end_point = self._get_intersection_point(self.end_item, line_from_target)

        if start_point is None: start_point = start_center
        if end_point is None: end_point = end_center

        path = QPainterPath(start_point)
        if self.start_item == self.end_item:
            rect = self.start_item.sceneBoundingRect()
            loop_radius_x = rect.width() * 0.40; loop_radius_y = rect.height() * 0.40
            p1 = QPointF(rect.center().x() + loop_radius_x * 0.35, rect.top())
            p2 = QPointF(rect.center().x() - loop_radius_x * 0.35, rect.top())
            ctrl1 = QPointF(rect.center().x() + loop_radius_x * 1.6, rect.top() - loop_radius_y * 2.8)
            ctrl2 = QPointF(rect.center().x() - loop_radius_x * 1.6, rect.top() - loop_radius_y * 2.8)
            path.moveTo(p1); path.cubicTo(ctrl1, ctrl2, p2)
            end_point = p2
        else:
            mid_x = (start_point.x() + end_point.x()) / 2; mid_y = (start_point.y() + end_point.y()) / 2
            dx = end_point.x() - start_point.x(); dy = end_point.y() - start_point.y()
            length = math.hypot(dx, dy)
            if length == 0: length = 1
            perp_x = -dy / length; perp_y = dx / length
            ctrl_pt_x = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y()
            ctrl_pt_y = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()
            ctrl_pt = QPointF(ctrl_pt_x, ctrl_pt_y)
            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0:
                path.lineTo(end_point)
            else:
                path.quadTo(ctrl_pt, end_point)
        self.setPath(path)
        self.prepareGeometryChange()

    def _get_intersection_point(self, item: QGraphicsRectItem, line: QLineF):
        item_rect = item.sceneBoundingRect()
        edges = [
            QLineF(item_rect.topLeft(), item_rect.topRight()),
            QLineF(item_rect.topRight(), item_rect.bottomRight()),
            QLineF(item_rect.bottomRight(), item_rect.bottomLeft()),
            QLineF(item_rect.bottomLeft(), item_rect.topLeft())
        ]
        intersect_points = []
        for edge in edges:
            intersection_point_var = QPointF()
            intersect_type = line.intersect(edge, intersection_point_var)
            if intersect_type == QLineF.BoundedIntersection:
                edge_rect_for_check = QRectF(edge.p1(), edge.p2()).normalized()
                epsilon = 1e-3
                if (edge_rect_for_check.left() - epsilon <= intersection_point_var.x() <= edge_rect_for_check.right() + epsilon and
                    edge_rect_for_check.top() - epsilon <= intersection_point_var.y() <= edge_rect_for_check.bottom() + epsilon):
                     intersect_points.append(QPointF(intersection_point_var))
        if not intersect_points: return item_rect.center()
        closest_point = intersect_points[0]
        min_dist_sq = (QLineF(line.p1(), closest_point).length())**2
        for pt in intersect_points[1:]:
            dist_sq = (QLineF(line.p1(), pt).length())**2
            if dist_sq < min_dist_sq: min_dist_sq = dist_sq; closest_point = pt
        return closest_point

    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty(): return
        painter.setRenderHint(QPainter.Antialiasing)
        current_pen = self.pen()
        if self.isSelected():
            stroker = QPainterPathStroker(); stroker.setWidth(current_pen.widthF() + 6)
            stroker.setCapStyle(Qt.RoundCap); stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path())
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(COLOR_ITEM_TRANSITION_SELECTION))
            painter.drawPath(selection_path_shape)
        painter.setPen(current_pen); painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())
        if self.path().elementCount() < 1 : return
        percent_at_end = 0.999
        if self.path().length() < 1 : percent_at_end = 0.9
        line_end_point = self.path().pointAtPercent(1.0)
        angle_at_end_rad = -self.path().angleAtPercent(percent_at_end) * (math.pi / 180.0)
        arrow_p1 = line_end_point + QPointF(math.cos(angle_at_end_rad - math.pi / 7) * self.arrow_size,
                                            math.sin(angle_at_end_rad - math.pi / 7) * self.arrow_size)
        arrow_p2 = line_end_point + QPointF(math.cos(angle_at_end_rad + math.pi / 7) * self.arrow_size,
                                            math.sin(angle_at_end_rad + math.pi / 7) * self.arrow_size)
        painter.setBrush(current_pen.color())
        painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics
            painter.setFont(self._font); fm = QFontMetrics(self._font)
            text_rect_original = fm.boundingRect(current_label)
            text_pos_on_path = self.path().pointAtPercent(0.5)
            angle_at_mid_deg = self.path().angleAtPercent(0.5)
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0)
            offset_dist = 10
            text_center_x = text_pos_on_path.x() + offset_dist * math.cos(offset_angle_rad)
            text_center_y = text_pos_on_path.y() + offset_dist * math.sin(offset_angle_rad)
            text_final_pos = QPointF(text_center_x - text_rect_original.width() / 2,
                                     text_center_y - text_rect_original.height() / 2)
            bg_padding = 2
            bg_rect = QRectF(text_final_pos.x() - bg_padding, text_final_pos.y() - bg_padding,
                             text_rect_original.width() + 2 * bg_padding, text_rect_original.height() + 2 * bg_padding)
            painter.setBrush(QColor(COLOR_BACKGROUND_LIGHT).lighter(102))
            painter.setPen(QPen(QColor(COLOR_BORDER_LIGHT), 0.5))
            painter.drawRoundedRect(bg_rect, 3, 3)
            painter.setPen(self._text_color)
            painter.drawText(text_final_pos, current_label)

    def get_data(self):
        return {
            'source': self.start_item.text_label if self.start_item else "None",
            'target': self.end_item.text_label if self.end_item else "None",
            'event': self.event_str, 'condition': self.condition_str, 'action': self.action_str,
            'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_TRANSITION_DEFAULT).name(),
            'description': self.description,
            'control_offset_x': self.control_point_offset.x(),
            'control_offset_y': self.control_point_offset.y()
        }

    def set_properties(self, event_str="", condition_str="", action_str="",
                       color_hex=None, description="", offset=None):
        changed = False
        if self.event_str != event_str: self.event_str = event_str; changed=True
        if self.condition_str != condition_str: self.condition_str = condition_str; changed=True
        if self.action_str != action_str: self.action_str = action_str; changed=True
        if self.description != description: self.description = description; changed=True
        new_color = QColor(color_hex) if color_hex else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        if self.base_color != new_color:
            self.base_color = new_color
            self.setPen(QPen(self.base_color, self._pen_width))
            changed = True
        if offset is not None and self.control_point_offset != offset:
            self.control_point_offset = offset
            changed = True
        if changed: self.prepareGeometryChange()
        if offset is not None : self.update_path()
        self.update()

    def set_control_point_offset(self, offset: QPointF):
        if self.control_point_offset != offset:
            self.control_point_offset = offset
            self.update_path(); self.update()


class GraphicsCommentItem(QGraphicsTextItem):
    Type = QGraphicsItem.UserType + 3
    def type(self): return GraphicsCommentItem.Type

    def __init__(self, x, y, text="Comment"):
        super().__init__()
        self.setPlainText(text); self.setPos(x, y)
        self.setFont(QFont(APP_FONT_FAMILY, 9))
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self._default_width = 150; self.setTextWidth(self._default_width)
        self.border_pen = QPen(QColor(COLOR_ITEM_COMMENT_BORDER), 1)
        self.background_brush = QBrush(QColor(COLOR_ITEM_COMMENT_BG))
        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(8); self.shadow_effect.setColor(QColor(0, 0, 0, 50))
        self.shadow_effect.setOffset(2, 2); self.setGraphicsEffect(self.shadow_effect)
        if self.document(): self.document().contentsChanged.connect(self._on_contents_changed)

    def _on_contents_changed(self):
        self.prepareGeometryChange()
        if self.scene(): self.scene().item_moved.emit(self)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self.border_pen); painter.setBrush(self.background_brush)
        rect = self.boundingRect()
        painter.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5), 4, 4)
        self.setDefaultTextColor(QColor(COLOR_TEXT_PRIMARY))
        super().paint(painter, option, widget)
        if self.isSelected():
            selection_pen = QPen(QColor(COLOR_ACCENT_PRIMARY), 1.5, Qt.DashLine)
            painter.setPen(selection_pen); painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())

    def get_data(self):
        doc_width = self.document().idealWidth() if self.textWidth() < 0 else self.textWidth()
        return {'text': self.toPlainText(), 'x': self.x(), 'y': self.y(), 'width': doc_width}

    def set_properties(self, text, width=None):
        current_text = self.toPlainText(); text_changed = (current_text != text)
        width_changed = False
        current_text_width = self.textWidth()
        target_width = width if width and width > 0 else self._default_width
        if current_text_width != target_width: width_changed = True
        if text_changed: self.setPlainText(text)
        if width_changed: self.setTextWidth(target_width)
        if text_changed or width_changed : self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)
    # bsm_designer_project/fsm_simulator.py

print("fsm_simulator.py is being imported with python-statemachine integration, HIERARCHY AWARENESS, and Enhanced Security/Robustness!")

from statemachine import StateMachine, State
from statemachine.exceptions import TransitionNotAllowed, InvalidDefinition
from statemachine.event import Event as SMEvent


import logging
import ast # For AST-based safety checks

# Configure logging for this module
logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Avoid adding multiple handlers
    LOGGING_DATE_FORMAT = "%H:%M:%S"
    handler = logging.StreamHandler()
    formatter = logging.Formatter("--- FSM_SIM (%(asctime)s.%(msecs)03d): %(message)s", datefmt=LOGGING_DATE_FORMAT)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# --- START: Enhanced AST Safety Checker ---
class BasicSafetyVisitor(ast.NodeVisitor):
    def __init__(self, allowed_variable_names=None):
        super().__init__()
        self.violations = []
        self.allowed_call_names = {
            'print', 'len', 'abs', 'min', 'max', 'int', 'float', 'str', 'bool', 'round',
            'list', 'dict', 'set', 'tuple', 'range', 'sorted', 'sum', 'all', 'any',
            'isinstance', 'hasattr',
        }
        self.allowed_dunder_attrs = {
            '__len__', '__getitem__', '__setitem__', '__delitem__', '__contains__',
            '__add__', '__sub__', '__mul__', '__truediv__', '__floordiv__', '__mod__', '__pow__',
            '__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__',
            '__iter__', '__next__', '__call__',
            '__str__', '__repr__',
            '__bool__', '__hash__', '__abs__',
        }
        self.dangerous_attributes = {
            '__globals__', '__builtins__', '__code__', '__closure__', '__self__',
            '__class__', '__bases__', '__subclasses__', '__mro__',
            '__init__', '__new__', '__del__', '__dict__',
            '__getattribute__', '__setattr__', '__delattr__',
            '__get__', '__set__', '__delete__',
            '__init_subclass__', '__prepare__',
            'f_locals', 'f_globals', 'f_builtins', 'f_code', 'f_back', 'f_trace',
            'gi_frame', 'gi_code', 'gi_running', 'gi_yieldfrom',
            'co_code', 'co_consts', 'co_names', 'co_varnames', 'co_freevars', 'co_cellvars',
            'func_code', 'func_globals', 'func_builtins', 'func_closure', 'func_defaults',
            '__file__', '__cached__', '__loader__', '__package__', '__spec__',
            '_as_parameter_', '_fields_', '_length_', '_type_',
            '__annotations__', '__qualname__', '__module__',
            '__slots__', '__weakref__', '__set_name__',
            'format_map', 'mro', 'with_traceback',
        }
        self.truly_dangerous_attributes = self.dangerous_attributes - self.allowed_dunder_attrs
        self.allowed_variable_names = allowed_variable_names if allowed_variable_names else set()

    def visit_Import(self, node):
        self.violations.append("SecurityError: Imports (import) are not allowed in FSM code.")
        super().generic_visit(node)

    def visit_ImportFrom(self, node):
        self.violations.append("SecurityError: From-imports (from ... import) are not allowed in FSM code.")
        super().generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ('eval', 'exec', 'compile', 'open', 'input',
                             'getattr', 'setattr', 'delattr',
                             'globals', 'locals', 'vars',
                             '__import__',
                             'memoryview', 'bytearray', 'bytes'
                             ):
                self.violations.append(f"SecurityError: Calling the function '{func_name}' is not allowed.")
            elif func_name not in self.allowed_call_names and \
                 func_name not in self.allowed_variable_names and \
                 func_name not in SAFE_BUILTINS:
                # This was previously `pass`. If we want to allow user-defined functions that are somehow made available
                # in the execution scope (e.g., via `self._variables` initially or through other safe mechanisms),
                # then `pass` is okay. If we want to be stricter and only allow predefined safe builtins and variables
                # explicitly in `self._variables`, then this should also append a violation.
                # For now, keeping it as `pass` assuming advanced users might inject safe callables.
                pass
        super().generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.attr, str):
            if node.attr in self.truly_dangerous_attributes:
                self.violations.append(f"SecurityError: Access to the attribute '{node.attr}' is restricted.")
            elif node.attr.startswith('__') and node.attr.endswith('__') and node.attr not in self.allowed_dunder_attrs:
                self.violations.append(f"SecurityError: Access to the special attribute '{node.attr}' is restricted.")
        super().generic_visit(node)

    def visit_Exec(self, node): # Python 2.x specific, unlikely to be used with ast.parse in Py3
        self.violations.append("SecurityError: The 'exec' statement/function is not allowed.")
        super().generic_visit(node)

def check_code_safety_basic(code_string: str, fsm_variables: set) -> tuple[bool, str]:
    if not code_string.strip():
        return True, ""
    try:
        tree = ast.parse(code_string, mode='exec')
        visitor = BasicSafetyVisitor(allowed_variable_names=fsm_variables)
        visitor.visit(tree)
        if visitor.violations:
            return False, "; ".join(visitor.violations)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError in user code: {e.msg} (line {e.lineno}, offset {e.offset})"
    except Exception as e:
        return False, f"Unexpected error during code safety check: {type(e).__name__} - {e}"

SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "float": float,
    "int": int, "len": len, "list": list, "max": max, "min": min, "print": print,
    "range": range, "round": round, "set": set, "str": str, "sum": sum, "tuple": tuple,
    "True": True, "False": False, "None": None,
    "isinstance": isinstance, "hasattr": hasattr,
}
# --- END: Enhanced AST Safety Checker ---


class FSMError(Exception):
    pass

class StateMachinePoweredSimulator:
    def __init__(self, states_data, transitions_data, parent_simulator=None, log_prefix="", halt_on_action_error=False):
        self._states_input_data = {s['name']: s for s in states_data}
        self._transitions_input_data = transitions_data
        self._variables = {}
        self._action_log = []
        self.FSMClass = None
        self.sm: StateMachine | None = None
        self._initial_state_name = None
        self.parent_simulator: StateMachinePoweredSimulator | None = parent_simulator
        self.log_prefix = log_prefix

        self.active_sub_simulator: StateMachinePoweredSimulator | None = None
        self.active_superstate_name: str | None = None
        self._halt_simulation_on_action_error = halt_on_action_error
        self.simulation_halted_flag = False

        try:
            self._build_fsm_class_and_instance()
            if self.sm and self.sm.current_state:
                self._log_action(f"FSM Initialized. Current state: {self.sm.current_state.id}")
            elif not self._states_input_data and not self.parent_simulator: # Top-level FSM with no states
                 raise FSMError("No states defined in the FSM.")
            elif not self._states_input_data and self.parent_simulator: # Sub-FSM with no states
                self._log_action("Sub-FSM initialized but has no states (inactive).")
            # If FSMClass was built but self.sm is None (e.g., no initial state resolved and instantiation failed)
            elif self.FSMClass and not self.sm and (self._states_input_data or self.parent_simulator):
                 raise FSMError("FSM Initialization failed: StateMachine (sm) instance is None after build. Check initial state definition.")

        except InvalidDefinition as e:
            logger.error(f"{self.log_prefix}FSM Definition Error during Initialization: {e}", exc_info=False)
            raise FSMError(f"FSM Definition Error: {e}")
        except FSMError: # Re-raise FSMError directly
            raise
        except Exception as e: # Catch other unexpected errors
            logger.error(f"{self.log_prefix}Initialization failed: {e}", exc_info=True)
            raise FSMError(f"FSM Initialization failed: {e}")

    def _log_action(self, message, level_prefix_override=None):
        prefix_to_use = level_prefix_override if level_prefix_override is not None else self.log_prefix
        full_message = f"{prefix_to_use}{message}"
        self._action_log.append(full_message)
        logger.info(full_message)

    def _create_dynamic_callback(self, code_string, callback_type="action", original_name="dynamic_callback"):
        is_safe, safety_message = check_code_safety_basic(code_string, set(self._variables.keys()))
        if not is_safe:
            err_msg = f"SecurityError: Code execution blocked for '{original_name}'. Reason: {safety_message}"
            self._log_action(f"[Safety Check Failed] {err_msg}")
            if callback_type == "condition":
                def unsafe_condition_wrapper(*args, **kwargs):
                    self._log_action(f"[Condition Blocked by Safety Check] Unsafe code: '{code_string}' evaluated as False.")
                    return False
                unsafe_condition_wrapper.__name__ = f"{original_name}_blocked_condition_safety_{hash(code_string)}"
                return unsafe_condition_wrapper
            else: # action
                def unsafe_action_wrapper(*args, **kwargs):
                    self._log_action(f"[Action Blocked by Safety Check] Unsafe code ignored: '{code_string}'.")
                unsafe_action_wrapper.__name__ = f"{original_name}_blocked_action_safety_{hash(code_string)}"
                return unsafe_action_wrapper

        simulator_self = self

        def dynamic_callback_wrapper(*args, **kwargs_from_sm_call):
            sm_instance_arg = None
            if args and isinstance(args[0], StateMachine):
                sm_instance_arg = args[0]
            elif 'machine' in kwargs_from_sm_call:
                sm_instance_arg = kwargs_from_sm_call['machine']
            
            if not sm_instance_arg:
                passed_args = args[1:] if args and isinstance(args[0], StateMachine) else args
                simulator_self._log_action(f"[Callback Error] Could not determine StateMachine instance for '{original_name}'. Args: {passed_args}, Kwargs: {list(kwargs_from_sm_call.keys())}")
                if callback_type == "condition": return False
                return

            exec_eval_locals_dict = simulator_self._variables # Always use the simulator's _variables

            log_prefix_runtime = "[Action Runtime]" if callback_type == "action" else "[Condition Runtime]"
            current_state_for_log = "UnknownState"
            if sm_instance_arg and sm_instance_arg.current_state:
                 current_state_for_log = sm_instance_arg.current_state.id
            elif simulator_self.parent_simulator and simulator_self.parent_simulator.sm and simulator_self.parent_simulator.sm.current_state:
                 current_state_for_log = f"{simulator_self.parent_simulator.sm.current_state.id} (sub-context)"
            
            action_or_cond_id = original_name.split('_')[-1] if '_' in original_name else original_name

            simulator_self._log_action(f"{log_prefix_runtime} Executing: '{code_string}' in state '{current_state_for_log}' for '{action_or_cond_id}' with vars: {exec_eval_locals_dict}")

            try:
                if callback_type == "action":
                    exec(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict)
                    simulator_self._log_action(f"{log_prefix_runtime} Finished: '{code_string}'. Variables now: {exec_eval_locals_dict}")
                    return None
                elif callback_type == "condition":
                    result = eval(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict.copy()) # Use a copy for eval to prevent modification
                    simulator_self._log_action(f"{log_prefix_runtime} Result of '{code_string}': {result}")
                    return bool(result)
            except SyntaxError as e:
                err_msg = (f"SyntaxError in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{e.msg} (line {e.lineno}, offset {e.offset}). Code: '{code_string}'")
                simulator_self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{simulator_self.log_prefix}{err_msg}", exc_info=False)
                if callback_type == "condition": return False
                if simulator_self._halt_simulation_on_action_error and callback_type == "action": simulator_self.simulation_halted_flag = True; raise FSMError(err_msg)
            except NameError as e:
                err_msg = (f"NameError in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{e}. Variable not defined or not in SAFE_BUILTINS? Code: '{code_string}'")
                simulator_self._log_action(f"[Code Error] {err_msg}")
                logger.warning(f"{simulator_self.log_prefix}{err_msg}")
                if callback_type == "condition": return False
                if simulator_self._halt_simulation_on_action_error and callback_type == "action": simulator_self.simulation_halted_flag = True; raise FSMError(err_msg)
            except TypeError as e:
                err_msg = (f"TypeError in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{e}. Code: '{code_string}'")
                simulator_self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{simulator_self.log_prefix}{err_msg}", exc_info=True)
                if callback_type == "condition": return False
                if simulator_self._halt_simulation_on_action_error and callback_type == "action": simulator_self.simulation_halted_flag = True; raise FSMError(err_msg)
            except (AttributeError, IndexError, KeyError, ValueError, ZeroDivisionError) as e:
                err_msg = (f"{type(e).__name__} in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{e}. Code: '{code_string}'")
                simulator_self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{simulator_self.log_prefix}{err_msg}", exc_info=True)
                if callback_type == "condition": return False
                if simulator_self._halt_simulation_on_action_error and callback_type == "action": simulator_self.simulation_halted_flag = True; raise FSMError(err_msg)
            except Exception as e:
                err_msg = (f"Unexpected runtime error in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{type(e).__name__} - {e}. Code: '{code_string}'")
                simulator_self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{simulator_self.log_prefix}{err_msg}", exc_info=True)
                if callback_type == "condition": return False
                if simulator_self._halt_simulation_on_action_error and callback_type == "action": simulator_self.simulation_halted_flag = True; raise FSMError(err_msg)
            return None
        dynamic_callback_wrapper.__name__ = f"{original_name}_{callback_type}_{hash(code_string)}"
        return dynamic_callback_wrapper

    def _master_on_enter_state_impl(self, sm_instance: StateMachine, target: State, **kwargs):
        target_state_name = target.id
        self._log_action(f"Entering state: {target_state_name}")

        if target_state_name in self._states_input_data:
            state_def = self._states_input_data[target_state_name]
            if state_def.get('is_superstate', False):
                sub_fsm_data = state_def.get('sub_fsm_data')
                if sub_fsm_data and sub_fsm_data.get('states'):
                    self._log_action(f"Superstate '{target_state_name}' entered. Initializing its sub-machine.")
                    try:
                        self.active_sub_simulator = StateMachinePoweredSimulator(
                            sub_fsm_data['states'], sub_fsm_data['transitions'],
                            parent_simulator=self,
                            log_prefix=self.log_prefix + "  [SUB] ",
                            halt_on_action_error=self._halt_simulation_on_action_error
                        )
                        self.active_superstate_name = target_state_name
                        # Capture and append sub-simulator's initialization logs
                        for sub_log_entry in self.active_sub_simulator.get_last_executed_actions_log():
                            self._action_log.append(sub_log_entry)
                    except Exception as e:
                        self._log_action(f"ERROR initializing sub-machine for '{target_state_name}': {e}")
                        logger.error(f"{self.log_prefix}Sub-machine init error for '{target_state_name}':", exc_info=True)
                        self.active_sub_simulator = None; self.active_superstate_name = None
                        if self._halt_simulation_on_action_error: self.simulation_halted_flag = True; raise FSMError(f"Sub-FSM init failed for {target_state_name}: {e}")
                else:
                    self._log_action(f"Superstate '{target_state_name}' has no defined sub-machine data or states.")

    def _master_on_exit_state_impl(self, sm_instance: StateMachine, source: State, **kwargs):
        source_state_name = source.id
        self._log_action(f"Exiting state: {source_state_name}")

        if self.active_sub_simulator and self.active_superstate_name == source_state_name:
            self._log_action(f"Superstate '{source_state_name}' exited. Terminating its sub-machine.")
            if hasattr(self.active_sub_simulator, 'get_last_executed_actions_log'):
                 # Capture and append sub-simulator's final logs before it's nulled
                 for sub_log_entry in self.active_sub_simulator.get_last_executed_actions_log():
                     self._action_log.append(sub_log_entry)
            self.active_sub_simulator = None
            self.active_superstate_name = None

    def _sm_before_transition_impl(self, sm_instance: StateMachine, event: str, source: State, target: State, **kwargs):
        event_data_obj = kwargs.get('event_data')
        triggered_event_name = event_data_obj.event if event_data_obj else event
        self._log_action(f"Before transition on '{triggered_event_name}' from '{source.id}' to '{target.id}'")

    def _sm_after_transition_impl(self, sm_instance: StateMachine, event: str, source: State, target: State, **kwargs):
        event_data_obj = kwargs.get('event_data')
        triggered_event_name = event_data_obj.event if event_data_obj else event
        self._log_action(f"After transition on '{triggered_event_name}' from '{source.id}' to '{target.id}'")


    def _build_fsm_class_and_instance(self):
        fsm_class_attrs = {}
        sm_states_obj_map = {}
        initial_state_name_from_data = None
        simulator_self = self # Closure for lambdas

        for s_name, s_data in self._states_input_data.items():
            is_initial = s_data.get('is_initial', False)
            if is_initial:
                if initial_state_name_from_data:
                    raise FSMError(f"Multiple initial states defined: '{initial_state_name_from_data}' and '{s_name}'.")
                initial_state_name_from_data = s_name
                self._initial_state_name = s_name

            state_obj = State(name=s_name, value=s_name, initial=is_initial, final=s_data.get('is_final', False))
            
            if s_data.get('entry_action'):
                # Capture s_data and s_name by value for the lambda
                fsm_class_attrs[f"on_enter_{s_name}"] = lambda sm_instance, *args, sd=s_data.copy(), sn=s_name, **kwargs: \
                    simulator_self._create_dynamic_callback(
                        sd['entry_action'], "action", f"entry_{sn}"
                    )(sm_instance, *args, **kwargs)

            if s_data.get('exit_action'):
                # Capture s_data and s_name by value for the lambda
                fsm_class_attrs[f"on_exit_{s_name}"] = lambda sm_instance, *args, sd=s_data.copy(), sn=s_name, **kwargs: \
                    simulator_self._create_dynamic_callback(
                        sd['exit_action'], "action", f"exit_{sn}"
                    )(sm_instance, *args, **kwargs)
            
            fsm_class_attrs[s_name] = state_obj
            sm_states_obj_map[s_name] = state_obj

        if not initial_state_name_from_data and self._states_input_data: # If states exist but no initial
            first_state_name_from_data = next(iter(self._states_input_data)) # Take the first state as initial
            if first_state_name_from_data in sm_states_obj_map:
                self._log_action(f"Warning: No initial state explicitly defined. Using first state '{first_state_name_from_data}' as initial.")
                sm_states_obj_map[first_state_name_from_data]._initial = True # Set initial flag on the State object
                self._initial_state_name = first_state_name_from_data
            else: # Should not happen if map is built correctly
                 raise FSMError("Fallback initial state error: First state not found in map.")
        elif not self._states_input_data: # No states defined at all
            if not self.parent_simulator: raise FSMError("No states defined in FSM.")
            else: self._log_action("Sub-FSM has no states defined. It will be inactive."); self.FSMClass = self.sm = None; return

        # Ensure there's at least one event defined if there are transitions.
        # python-statemachine will raise InvalidDefinition if no events are present.
        # If there are no transitions, this is okay for an FSM with only states (though unusual).
        if not self._transitions_input_data and self._states_input_data:
            self._log_action("Warning: FSM has states but no transitions. No events will be defined beyond potential state actions.")
            # Add a dummy event if no transitions, to satisfy python-statemachine if it strictly requires an event.
            # This is often needed if the library expects at least one SMEvent instance.
            if not any(isinstance(attr, SMEvent) for attr in fsm_class_attrs.values()):
                dummy_event_name = f"_internal_dummy_event_{id(self)}"
                fsm_class_attrs[dummy_event_name] = SMEvent(dummy_event_name)
                self._log_action(f"Added dummy event '{dummy_event_name}' as no transitions were defined.")


        defined_events = {}
        for t_idx, t_data in enumerate(self._transitions_input_data):
            source_name, target_name = t_data['source'], t_data['target']
            event_name_str = t_data.get('event')
            if not event_name_str: # Create a synthetic event name if none provided
                event_name_str = f"_internal_t{t_idx}_{source_name}_to_{target_name}"
                event_name_str = "".join(c if c.isalnum() or c == '_' else '_' for c in event_name_str) # Sanitize
                self._log_action(f"Warning: Transition {source_name}->{target_name} has no event. Synthetic event ID: {event_name_str}")

            source_state_obj = sm_states_obj_map.get(source_name)
            target_state_obj = sm_states_obj_map.get(target_name)

            if not source_state_obj or not target_state_obj:
                self._log_action(f"Warning: Skipping transition for event '{event_name_str}' from '{source_name}' to '{target_name}' due to missing state object(s)."); continue
            
            # Create or reuse SMEvent object
            if event_name_str not in defined_events:
                event_obj = SMEvent(event_name_str)
                defined_events[event_name_str] = event_obj
                fsm_class_attrs[event_name_str] = event_obj # Add event trigger to class
            else: event_obj = defined_events[event_name_str]

            # Create condition callback if specified
            cond_cb = simulator_self._create_dynamic_callback(
                t_data['condition'], "condition", f"cond_t{t_idx}_{event_name_str}"
            ) if t_data.get('condition') else None

            # Create action callback if specified
            action_cb = simulator_self._create_dynamic_callback(
                t_data['action'], "action", f"action_t{t_idx}_{event_name_str}"
            ) if t_data.get('action') else None
            
            # Define the transition on the source state object
            _ = source_state_obj.to(target_state_obj, event=event_obj, cond=cond_cb, on=action_cb)

        # Add master state enter/exit and transition before/after hooks
        fsm_class_attrs.update({
            "on_enter_state": lambda sm_instance, target, **kwargs: simulator_self._master_on_enter_state_impl(sm_instance, target, **kwargs),
            "on_exit_state": lambda sm_instance, source, **kwargs: simulator_self._master_on_exit_state_impl(sm_instance, source, **kwargs),
            "before_transition": lambda sm_instance, event, source, target, **kwargs: simulator_self._sm_before_transition_impl(sm_instance, event, source, target, **kwargs),
            "after_transition": lambda sm_instance, event, source, target, **kwargs: simulator_self._sm_after_transition_impl(sm_instance, event, source, target, **kwargs)
        })
        
        # Create the StateMachine class dynamically
        try:
            unique_class_name = f"DynamicBSMFSM_{self.log_prefix.replace(' ', '').replace('[','').replace(']','').replace('-','')}_{id(self)}"
            self.FSMClass = type(unique_class_name, (StateMachine,), fsm_class_attrs)
        except InvalidDefinition as e_def:
             logger.error(f"{self.log_prefix}FSM Definition Error for '{unique_class_name}': {e_def}", exc_info=False)
             raise FSMError(f"FSM Definition Error: {e_def}")
        except Exception as e: # Catch other errors during class creation
            logger.error(f"{self.log_prefix}Failed to create StateMachine class '{unique_class_name}': {e}", exc_info=True)
            raise FSMError(f"StateMachine class creation failed: {e}")

        # Instantiate the StateMachine
        try:
            # Pass model for variable storage, allow_event_without_transition for flexibility
            self.sm = self.FSMClass(model=self._variables, allow_event_without_transition=True)
        except InvalidDefinition as e_def: # Catch definition errors during instantiation
            logger.error(f"{self.log_prefix}FSM Instance Creation Error for '{unique_class_name}': {e_def}", exc_info=False)
            raise FSMError(f"FSM Instance Creation Error: {e_def}")
        except Exception as e: # Catch other errors during instantiation
            logger.error(f"{self.log_prefix}Failed to instantiate StateMachine '{unique_class_name}': {e}", exc_info=True)
            raise FSMError(f"StateMachine instantiation failed: {e}")

        # Post-instantiation check
        if self.sm and self.sm.current_state:
            # Successfully initialized with a current state
            pass
        elif self.sm and not self.sm.current_state and self._states_input_data:
            # SM instance created but no current state (e.g. initial state logic failed in python-statemachine)
            raise FSMError(f"FSM '{unique_class_name}' initialized but no current state. Ensure initial=True for one state or check for library errors.")

    def get_current_state_name(self):
        if not self.sm: return "Uninitialized" if not self.parent_simulator else "EmptySubFSM"
        name = self.sm.current_state.id
        if self.active_sub_simulator and self.active_sub_simulator.sm: # If sub-FSM is active
            name += f" ({self.active_sub_simulator.get_current_state_name()})" # Append sub-state
        return name

    def get_current_leaf_state_name(self):
        if self.active_sub_simulator and self.active_sub_simulator.sm :
            return self.active_sub_simulator.get_current_leaf_state_name()
        elif self.sm and self.sm.current_state: return self.sm.current_state.id
        return "UnknownLeaf" # Should not happen in a valid FSM

    def get_variables(self): return self._variables.copy()
    def get_last_executed_actions_log(self):
        log_snapshot = self._action_log[:]
        self._action_log = [] # Clear log after retrieval
        return log_snapshot

    def reset(self):
        self._log_action("--- FSM Resetting ---")
        self._variables.clear()
        self.simulation_halted_flag = False
        if self.active_sub_simulator:
            self._log_action("Resetting active sub-machine...")
            self.active_sub_simulator.reset() # Recursively reset sub-machine
            self._action_log.extend(self.active_sub_simulator.get_last_executed_actions_log()) # Collect sub-log
            self.active_sub_simulator = self.active_superstate_name = None
        
        if self.FSMClass:
            try:
                # Re-instantiate the FSM using the existing class definition
                self.sm = self.FSMClass(model=self._variables, allow_event_without_transition=True)
                current_state_id = self.sm.current_state.id if self.sm and self.sm.current_state else 'Unknown (No Initial State?)'
                self._log_action(f"FSM Reset. Current state: {current_state_id}")
            except Exception as e:
                logger.error(f"{self.log_prefix}Reset failed during SM re-instantiation: {e}", exc_info=True)
                raise FSMError(f"Reset failed during SM re-instantiation: {e}")
        elif not self.parent_simulator and not self._states_input_data: # Top-level FSM with no states
            logger.error(f"{self.log_prefix}FSM Class not built (no states defined), cannot reset properly.")
        # If it's a sub-FSM with no states, it's already considered "reset" (inactive)
        
    def step(self, event_name=None):
        if self.simulation_halted_flag:
            self._log_action(f"Simulation HALTED. Event '{event_name or 'Internal'}' ignored. Reset required.")
            return self.get_current_state_name(), self.get_last_executed_actions_log()

        if not self.sm: # If StateMachine instance (self.sm) is None
            if not self.parent_simulator and not self._states_input_data : # Top-level FSM with no states
                 logger.error(f"{self.log_prefix}Cannot step: FSM not initialized (no states)."); raise FSMError("Cannot step, FSM not initialized (no states).")
            elif self.parent_simulator and not self._states_input_data: # Empty sub-FSM
                self._log_action("Cannot step: Sub-FSM is empty/not defined.")
                return self.get_current_state_name(), self.get_last_executed_actions_log()
            else: # Should have been caught by __init__ if FSMClass was built but sm is None
                logger.error(f"{self.log_prefix}Cannot step: FSM.sm not initialized."); raise FSMError("Cannot step, FSM.sm not initialized.")

        main_state_id = self.sm.current_state.id
        self._log_action(f"--- Step. State: {self.get_current_state_name()}. Event: {event_name or 'Internal'} ---")

        try:
            # Execute 'during' action of the current main state
            main_state_data = self._states_input_data.get(main_state_id)
            if main_state_data and main_state_data.get('during_action'):
                action_str = main_state_data['during_action']
                self._log_action(f"During action for '{main_state_id}': {action_str}")
                during_cb = self._create_dynamic_callback(action_str, "action", f"during_{main_state_id}")
                during_cb(self.sm) # Pass the StateMachine instance

            if self.simulation_halted_flag: return self.get_current_state_name(), self.get_last_executed_actions_log()

            # If there's an active sub-simulator, step it (internal step, no explicit event)
            if self.active_sub_simulator:
                superstate_log_name = self.active_superstate_name or main_state_id
                self._log_action(f"Internal step for sub-machine in '{superstate_log_name}'.")
                _, sub_log = self.active_sub_simulator.step(event_name=None) # Internal step for sub-machine
                self._action_log.extend(sub_log)
                if self.active_sub_simulator.simulation_halted_flag:
                    self.simulation_halted_flag = True
                    self._log_action(f"Propagation: Parent HALTED due to sub-machine error in '{superstate_log_name}'."); return self.get_current_state_name(), self.get_last_executed_actions_log()
                
                # Check if sub-machine reached a final state
                sub_sm_instance = self.active_sub_simulator.sm
                if sub_sm_instance and sub_sm_instance.current_state and sub_sm_instance.current_state.final:
                    self._log_action(f"Sub-machine in '{superstate_log_name}' reached final state: '{sub_sm_instance.current_state.id}'.")
                    if self.active_superstate_name: # If we know the superstate name
                         self._variables[f"{self.active_superstate_name}_sub_completed"] = True
                         self._log_action(f"Variable '{self.active_superstate_name}_sub_completed' set to True in parent FSM.")
            
            if self.simulation_halted_flag: return self.get_current_state_name(), self.get_last_executed_actions_log()

            # Send event to the main FSM if an event_name is provided
            if event_name:
                self._log_action(f"Sending event '{event_name}' to FSM.")
                self.sm.send(event_name) # This triggers transitions, entry/exit actions, etc.
            elif not self.active_sub_simulator: # No event and no active sub-sim
                 self._log_action(f"No event. 'During' actions done. State remains '{main_state_id}'.")

        except FSMError as e_halt: # Catch FSMError if an action callback raised it to halt
            if self.simulation_halted_flag or "HALTED due to error" in str(e_halt):
                self._log_action(f"[SIMULATION HALTED internally] {e_halt}"); self.simulation_halted_flag = True
            else: self._log_action(f"FSM Logic Error during step: {e_halt}"); logger.error(f"{self.log_prefix}FSM Logic Error:", exc_info=True)
        except TransitionNotAllowed: self._log_action(f"Event '{event_name}' not allowed or no transition from '{main_state_id}'.")
        except AttributeError as e: # e.g. event name not defined on FSM
            log_msg = f"Event '{event_name}' not defined on FSM."
            if event_name and hasattr(self.sm, event_name) and not callable(getattr(self.sm, event_name)):
                log_msg = f"Event name '{event_name}' conflicts with state or non-event attribute."
            elif event_name and hasattr(self.sm, event_name) and callable(getattr(self.sm, event_name)): # Should be callable if it's an event
                log_msg = f"AttributeError processing event '{event_name}': {e}. Internal setup/callback issue?"
            self._log_action(log_msg); logger.error(f"{self.log_prefix}AttributeError for '{event_name}':", exc_info=True)
        except Exception as e: self._log_action(f"Unexpected error on event '{event_name}': {type(e).__name__} - {e}"); logger.error(f"{self.log_prefix}Event processing error:", exc_info=True)

        return self.get_current_state_name(), self.get_last_executed_actions_log()

    def get_possible_events_from_current_state(self) -> list[str]:
        if not self.sm or not self.sm.current_state: return []
        
        possible_events_set = set()
        current_sm_to_query = self.sm # Start with the main FSM
        
        # If a sub-machine is active, its events take precedence or are combined
        if self.active_sub_simulator and self.active_sub_simulator.sm:
            current_sm_to_query = self.active_sub_simulator.sm
        
        if current_sm_to_query and current_sm_to_query.current_state:
            # `allowed_events` on python-statemachine returns a list of BoundEvent objects
            possible_events_set.update(str(evt.id) for evt in current_sm_to_query.allowed_events)
        
        # Also add events from the parent FSM if a sub-FSM was active,
        # as parent transitions might be triggered by events while in a superstate.
        if self.active_sub_simulator and self.sm and self.sm.current_state:
             possible_events_set.update(str(evt.id) for evt in self.sm.allowed_events)

        return sorted(list(possible_events_set))


FSMSimulator = StateMachinePoweredSimulator

if __name__ == "__main__":
    main_states_data = [
        {"name": "Idle", "is_initial": True, "entry_action": "print('Main: Idle Entered'); idle_counter = 0; Processing_sub_completed = False"},
        {"name": "Processing", "is_superstate": True,
         "sub_fsm_data": {
             "states": [
                 {"name": "SubIdle", "is_initial": True, "entry_action": "print('Sub: SubIdle Entered'); sub_var = 10"},
                 {"name": "SubActive", "during_action": "sub_var = sub_var + 1; print('Sub: SubActive during, sub_var is', sub_var)"},
                 {"name": "SubDone", "is_final": True, "entry_action": "print('Sub: SubDone Entered (final)')"}
             ],
             "transitions": [
                 {"source": "SubIdle", "target": "SubActive", "event": "start_sub_work"},
                 {"source": "SubActive", "target": "SubDone", "event": "finish_sub_work", "condition": "sub_var > 11"}
             ],
             "comments": []
         },
         "entry_action": "print('Main: Processing Superstate Entered')",
         "during_action": "print('Main: Processing Superstate During'); idle_counter = idle_counter + 1",
         "exit_action": "print('Main: Processing Superstate Exited')"
        },
        {"name": "Done", "is_final": True, "entry_action": "print('Main: Done Entered')"}
    ]
    main_transitions_data = [
        {"source": "Idle", "target": "Processing", "event": "start_processing"},
        {"source": "Processing", "target": "Done", "event": "auto_finish", "condition": "Processing_sub_completed == True"}
    ]

    print("--- HIERARCHICAL SIMULATOR TEST (python-statemachine) ---")
    try:
        simulator = FSMSimulator(main_states_data, main_transitions_data, halt_on_action_error=False)

        def print_status(sim, step_name=""):
            print(f"\n--- {step_name} ---")
            print(f"Current State: {sim.get_current_state_name()}")
            print(f"Leaf State: {sim.get_current_leaf_state_name()}")
            print(f"Main Vars: {sim.get_variables()}")
            if sim.active_sub_simulator: print(f"Sub Vars: {sim.active_sub_simulator.get_variables()}")
            log = sim.get_last_executed_actions_log()
            if log: print("Log:"); [print(f"  {entry}") for entry in log]
            print("Possible events:", sim.get_possible_events_from_current_state())
            print("--------------------")

        print_status(simulator, "INITIAL STATE")
        simulator.step("start_processing"); print_status(simulator, "AFTER 'start_processing'")
        
        if simulator.active_sub_simulator:
            print("\n>>> Trigger 'start_sub_work' on sub-machine (via parent's step) <<<")
            # In this model, parent steps and sub-machine events are handled somewhat separately.
            # To trigger sub-event, one might need to call step on active_sub_simulator directly
            # or ensure parent step can proxy specific events to sub-machine.
            # For this test, we'll directly step the sub-simulator.
            simulator.active_sub_simulator.step("start_sub_work")
            # Important: after stepping sub-simulator, its log is in its own _action_log.
            # The parent's step method would typically collect this if it were managing the sub-step.
            # For direct sub-step, we can manually append or review its log.
            print("Sub-log after direct sub-step:", simulator.active_sub_simulator.get_last_executed_actions_log())
            print_status(simulator, "AFTER sub-event 'start_sub_work'")
        
        simulator.step(None); print_status(simulator, "AFTER main internal step 1 (sub during actions run)")
        simulator.step(None); print_status(simulator, "AFTER main internal step 2 (sub during actions run)")
        
        if simulator.active_sub_simulator:
            print("\n>>> Trigger 'finish_sub_work' on sub-machine (via parent's step) <<<")
            simulator.active_sub_simulator.step("finish_sub_work")
            print("Sub-log after direct sub-step:", simulator.active_sub_simulator.get_last_executed_actions_log())
            print_status(simulator, "AFTER sub-event 'finish_sub_work'")
        
        simulator.step("auto_finish"); print_status(simulator, "AFTER 'auto_finish'")

        print("\n--- Test Unsafe Code (should be blocked) ---")
        unsafe_states_s = [{"name": "UnsafeStateS", "is_initial": True, "entry_action": "__import__('os').system('echo THIS_SHOULD_BE_BLOCKED')"}]
        unsafe_trans_s = [{"source": "UnsafeStateS", "target": "UnsafeStateS", "event": "dummy_event_unsafe"}]
        try:
            unsafe_sim_s = FSMSimulator(unsafe_states_s, unsafe_trans_s)
            print_status(unsafe_sim_s, "Unsafe Sim Test Start (check logs for blocking)")
        except FSMError as e: print(f"FSM Error during unsafe_sim_s setup: {e}") 
        except Exception as e: print(f"Unexpected error during unsafe_sim_s: {e}")

        print("\n--- Test Action Error (NameError, non-halting) ---")
        error_states = [{"name": "ErrState", "is_initial": True, "entry_action": "my_undefined_var = 1 / 0"}]
        error_trans = [{"source": "ErrState", "target": "ErrState", "event": "dummy_event_error"}]
        try:
            error_sim = FSMSimulator(error_states, error_trans, halt_on_action_error=False)
            print_status(error_sim, "Error Sim Start (NameError, non-halting)")
        except FSMError as e: print(f"FSM Error during error_sim setup: {e}")

        print("\n--- Test Action Error (ZeroDivisionError, with halting) ---")
        halt_error_states = [{"name": "HaltErrState", "is_initial": True, "entry_action": "x = 1 / 0"}]
        halt_error_trans = [{"source": "HaltErrState", "target": "HaltErrState", "event": "dummy_event_halt"}]
        halt_sim = None 
        try:
            halt_sim = FSMSimulator(halt_error_states, halt_error_trans, halt_on_action_error=True)
            # This print_status might not be reached if the FSMError due to action error occurs during SM instantiation's initial state entry
            print_status(halt_sim, "Halt Error Sim (MAY NOT REACH HERE if error in init path)")
        except FSMError as e: 
            print(f"FSM Error (as expected from halt_on_action_error): {e}")
            # If halt_sim was partially initialized before error, try to get logs
            if halt_sim and hasattr(halt_sim, 'get_last_executed_actions_log'):
                 log = halt_sim.get_last_executed_actions_log()
                 if log: print("Log from (partially) halted sim:"); [print(f"  {entry}") for entry in log]

    except FSMError as e: print(f"FSM Error: {e}")
    except Exception as e: print(f"An unexpected error: {e}"); import traceback; traceback.print_exc()
    
# bsm_designer_project/graphics_items.py

import math
from PyQt5.QtWidgets import (QGraphicsRectItem, QGraphicsPathItem, QGraphicsTextItem,
                             QGraphicsItem, QGraphicsDropShadowEffect, QApplication, QGraphicsSceneMouseEvent)
from PyQt5.QtGui import (QBrush, QColor, QFont, QPen, QPainterPath, QPolygonF, QPainter,
                         QPainterPathStroker, QPixmap, QMouseEvent, QDrag, QPalette)
from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QSize

from config import (COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_STATE_DEFAULT_BORDER, APP_FONT_FAMILY,
                    COLOR_TEXT_PRIMARY, COLOR_ITEM_STATE_SELECTION, COLOR_ITEM_TRANSITION_DEFAULT,
                    COLOR_ITEM_TRANSITION_SELECTION, COLOR_ITEM_COMMENT_BG, COLOR_ITEM_COMMENT_BORDER,
                    COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH,
                    COLOR_BACKGROUND_LIGHT, COLOR_BORDER_LIGHT, COLOR_ACCENT_PRIMARY)


class GraphicsStateItem(QGraphicsRectItem):
    Type = QGraphicsItem.UserType + 1

    def type(self): return GraphicsStateItem.Type

    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False,
                 color=None, entry_action="", during_action="", exit_action="", description="",
                 is_superstate=False, sub_fsm_data=None): # New parameters for hierarchy
        super().__init__(x, y, w, h)
        self.text_label = text
        self.is_initial = is_initial
        self.is_final = is_final
        self.is_superstate = is_superstate  # New attribute
        # Ensure sub_fsm_data is always a dict with the correct keys
        if sub_fsm_data and isinstance(sub_fsm_data, dict) and \
           all(k in sub_fsm_data for k in ['states', 'transitions', 'comments']):
            self.sub_fsm_data = sub_fsm_data
        else:
            self.sub_fsm_data = {'states': [], 'transitions': [], 'comments': []}

        self.base_color = QColor(color) if color else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        self.border_color = QColor(color).darker(120) if color else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)
        self.entry_action = entry_action
        self.during_action = during_action
        self.exit_action = exit_action
        self.description = description

        self._text_color = QColor(COLOR_TEXT_PRIMARY)
        self._font = QFont(APP_FONT_FAMILY, 10, QFont.Bold)
        self._border_pen_width = 1.5

        self.setPen(QPen(self.border_color, self._border_pen_width))
        self.setBrush(QBrush(self.base_color))

        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)

        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(10)
        self.shadow_effect.setColor(QColor(0, 0, 0, 60))
        self.shadow_effect.setOffset(2.5, 2.5)
        self.setGraphicsEffect(self.shadow_effect)

        self.is_py_sim_active = False
        self.original_pen_for_py_sim_restore = self.pen()

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        current_rect = self.rect()
        border_radius = 10

        current_pen_to_use = self.pen()
        if self.is_py_sim_active:
            py_sim_pen = QPen(COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH, Qt.DashLine)
            current_pen_to_use = py_sim_pen

        painter.setPen(current_pen_to_use)
        painter.setBrush(self.brush())
        painter.drawRoundedRect(current_rect, border_radius, border_radius)

        painter.setPen(self._text_color)
        painter.setFont(self._font)
        text_rect = current_rect.adjusted(8, 8, -8, -8)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)

        if self.is_initial:
            marker_radius = 6; line_length = 18; marker_color = Qt.black
            start_marker_center_x = current_rect.left() - line_length - marker_radius / 2
            start_marker_center_y = current_rect.center().y()
            painter.setBrush(marker_color)
            painter.setPen(QPen(marker_color, self._border_pen_width))
            painter.drawEllipse(QPointF(start_marker_center_x, start_marker_center_y), marker_radius, marker_radius)
            line_start_point = QPointF(start_marker_center_x + marker_radius, start_marker_center_y)
            line_end_point = QPointF(current_rect.left(), start_marker_center_y)
            painter.drawLine(line_start_point, line_end_point)
            arrow_size = 8; angle_rad = 0
            arrow_p1 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad + math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad + math.pi / 6))
            arrow_p2 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad - math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad - math.pi / 6))
            painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))

        if self.is_final: # No special handling for superstate final marker yet
            painter.setPen(QPen(self.border_color.darker(120), self._border_pen_width + 0.5))
            inner_rect = current_rect.adjusted(5, 5, -5, -5)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(inner_rect, border_radius - 3, border_radius - 3)

        if self.is_superstate:
            # Draw a simple indicator for superstate (e.g., small stacked rectangles icon)
            icon_size = 12
            icon_margin = 5
            icon_rect_base = QRectF(current_rect.right() - icon_size - icon_margin,
                                    current_rect.top() + icon_margin,
                                    icon_size, icon_size)
            
            painter.setPen(QPen(self.border_color.darker(150), 1))
            painter.setBrush(self.border_color.lighter(120))
            
            # Main rectangle of icon
            rect1 = QRectF(icon_rect_base.left(), icon_rect_base.top(), icon_rect_base.width(), icon_rect_base.height() * 0.7)
            painter.drawRect(rect1)
            # Shadow rectangle below
            rect2 = QRectF(icon_rect_base.left() + icon_rect_base.width() * 0.2, 
                           icon_rect_base.top() + icon_rect_base.height() * 0.3, 
                           icon_rect_base.width(), icon_rect_base.height() * 0.7)
            painter.setBrush(self.border_color.lighter(140)) # Slightly different color for overlap
            painter.drawRect(rect2)


        if self.isSelected() and not self.is_py_sim_active:
            selection_pen = QPen(QColor(COLOR_ITEM_STATE_SELECTION), self._border_pen_width + 1, Qt.SolidLine)
            selection_rect = self.boundingRect().adjusted(-1, -1, 1, 1)
            painter.setPen(selection_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(selection_rect, border_radius + 1, border_radius + 1)

    def set_py_sim_active_style(self, active: bool):
        if self.is_py_sim_active == active: return
        self.is_py_sim_active = active
        if active: self.original_pen_for_py_sim_restore = QPen(self.pen())
        else: self.setPen(self.original_pen_for_py_sim_restore)
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)

    def get_data(self):
        return {
            'name': self.text_label, 'x': self.x(), 'y': self.y(),
            'width': self.rect().width(), 'height': self.rect().height(),
            'is_initial': self.is_initial, 'is_final': self.is_final,
            'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_STATE_DEFAULT_BG).name(),
            'entry_action': self.entry_action, 'during_action': self.during_action,
            'exit_action': self.exit_action, 'description': self.description,
            'is_superstate': self.is_superstate,
            'sub_fsm_data': self.sub_fsm_data
        }

    def set_text(self, text):
        if self.text_label != text:
            self.prepareGeometryChange()
            self.text_label = text
            self.update()

    def set_properties(self, name, is_initial, is_final, color_hex=None,
                       entry="", during="", exit_a="", desc="",
                       is_superstate_prop=None, sub_fsm_data_prop=None): # Added hierarchy props
        changed = False
        if self.text_label != name: self.text_label = name; changed = True
        if self.is_initial != is_initial: self.is_initial = is_initial; changed = True
        if self.is_final != is_final: self.is_final = is_final; changed = True

        if is_superstate_prop is not None and self.is_superstate != is_superstate_prop:
            self.is_superstate = is_superstate_prop
            changed = True
        
        if sub_fsm_data_prop is not None:
            # Validate structure of sub_fsm_data_prop before assigning
            if isinstance(sub_fsm_data_prop, dict) and \
               all(k in sub_fsm_data_prop for k in ['states', 'transitions', 'comments']) and \
               isinstance(sub_fsm_data_prop['states'], list) and \
               isinstance(sub_fsm_data_prop['transitions'], list) and \
               isinstance(sub_fsm_data_prop['comments'], list):
                if self.sub_fsm_data != sub_fsm_data_prop:
                     self.sub_fsm_data = sub_fsm_data_prop
                     changed = True
            elif self.is_superstate: # If it's supposed to be a superstate but data is bad, log/warn
                print(f"Warning: Invalid sub_fsm_data provided for superstate '{name}'. Resetting to empty.")
                # Keep existing valid sub_fsm_data or reset, depending on desired behavior
                # self.sub_fsm_data = {'states': [], 'transitions': [], 'comments': []} # Option to reset
                # changed = True # If reset
                pass # Or simply ignore bad data and keep old

        new_base_color = QColor(color_hex) if color_hex else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        new_border_color = new_base_color.darker(120) if color_hex else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)

        if self.base_color != new_base_color:
            self.base_color = new_base_color
            self.border_color = new_border_color
            self.setBrush(self.base_color)
            new_pen = QPen(self.border_color, self._border_pen_width)
            if not self.is_py_sim_active: self.setPen(new_pen)
            self.original_pen_for_py_sim_restore = new_pen
            changed = True

        if self.entry_action != entry: self.entry_action = entry; changed = True
        if self.during_action != during: self.during_action = during; changed = True
        if self.exit_action != exit_a: self.exit_action = exit_a; changed = True
        if self.description != desc: self.description = desc; changed = True

        if changed:
            self.prepareGeometryChange()
            self.update()


class GraphicsTransitionItem(QGraphicsPathItem):
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type

    def __init__(self, start_item, end_item, event_str="", condition_str="", action_str="",
                 color=None, description=""):
        super().__init__()
        self.start_item: GraphicsStateItem | None = start_item
        self.end_item: GraphicsStateItem | None = end_item
        self.event_str = event_str
        self.condition_str = condition_str
        self.action_str = action_str
        self.base_color = QColor(color) if color else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        self.description = description
        self.arrow_size = 10

        self._text_color = QColor(COLOR_TEXT_PRIMARY)
        self._font = QFont(APP_FONT_FAMILY, 8)
        self.control_point_offset = QPointF(0,0)
        self._pen_width = 2.0

        self.setPen(QPen(self.base_color, self._pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1)
        self.setAcceptHoverEvents(True)
        self.update_path()

    def _compose_label_string(self):
        parts = []
        if self.event_str: parts.append(self.event_str)
        if self.condition_str: parts.append(f"[{self.condition_str}]")
        if self.action_str: parts.append(f"/{{{self.action_str}}}")
        return " ".join(parts)

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        self.setPen(QPen(self.base_color.lighter(130), self._pen_width + 0.5))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        self.setPen(QPen(self.base_color, self._pen_width))
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 25
        path_bounds = self.path().boundingRect()
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics
            fm = QFontMetrics(self._font)
            text_rect = fm.boundingRect(current_label)
            mid_point_on_path = self.path().pointAtPercent(0.5)
            text_render_rect = QRectF(mid_point_on_path.x() - text_rect.width() - 10,
                                    mid_point_on_path.y() - text_rect.height() - 10,
                                    text_rect.width()*2 + 20, text_rect.height()*2 + 20)
            path_bounds = path_bounds.united(text_render_rect)
        return path_bounds.adjusted(-extra, -extra, extra, extra)

    def shape(self):
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(18 + self.pen().widthF())
        path_stroker.setCapStyle(Qt.RoundCap)
        path_stroker.setJoinStyle(Qt.RoundJoin)
        return path_stroker.createStroke(self.path())

    def update_path(self):
        if not self.start_item or not self.end_item:
            self.setPath(QPainterPath())
            return

        start_center = self.start_item.sceneBoundingRect().center()
        end_center = self.end_item.sceneBoundingRect().center()

        line_to_target = QLineF(start_center, end_center)
        start_point = self._get_intersection_point(self.start_item, line_to_target)
        line_from_target = QLineF(end_center, start_center)
        end_point = self._get_intersection_point(self.end_item, line_from_target)

        if start_point is None: start_point = start_center
        if end_point is None: end_point = end_center

        path = QPainterPath(start_point)
        if self.start_item == self.end_item:
            rect = self.start_item.sceneBoundingRect()
            loop_radius_x = rect.width() * 0.40; loop_radius_y = rect.height() * 0.40
            p1 = QPointF(rect.center().x() + loop_radius_x * 0.35, rect.top())
            p2 = QPointF(rect.center().x() - loop_radius_x * 0.35, rect.top())
            ctrl1 = QPointF(rect.center().x() + loop_radius_x * 1.6, rect.top() - loop_radius_y * 2.8)
            ctrl2 = QPointF(rect.center().x() - loop_radius_x * 1.6, rect.top() - loop_radius_y * 2.8)
            path.moveTo(p1); path.cubicTo(ctrl1, ctrl2, p2)
            end_point = p2
        else:
            mid_x = (start_point.x() + end_point.x()) / 2; mid_y = (start_point.y() + end_point.y()) / 2
            dx = end_point.x() - start_point.x(); dy = end_point.y() - start_point.y()
            length = math.hypot(dx, dy)
            if length == 0: length = 1
            perp_x = -dy / length; perp_y = dx / length
            ctrl_pt_x = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y()
            ctrl_pt_y = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()
            ctrl_pt = QPointF(ctrl_pt_x, ctrl_pt_y)
            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0:
                path.lineTo(end_point)
            else:
                path.quadTo(ctrl_pt, end_point)
        self.setPath(path)
        self.prepareGeometryChange()

    def _get_intersection_point(self, item: QGraphicsRectItem, line: QLineF):
        item_rect = item.sceneBoundingRect()
        edges = [
            QLineF(item_rect.topLeft(), item_rect.topRight()),
            QLineF(item_rect.topRight(), item_rect.bottomRight()),
            QLineF(item_rect.bottomRight(), item_rect.bottomLeft()),
            QLineF(item_rect.bottomLeft(), item_rect.topLeft())
        ]
        intersect_points = []
        for edge in edges:
            intersection_point_var = QPointF()
            intersect_type = line.intersect(edge, intersection_point_var)
            if intersect_type == QLineF.BoundedIntersection:
                edge_rect_for_check = QRectF(edge.p1(), edge.p2()).normalized()
                epsilon = 1e-3
                if (edge_rect_for_check.left() - epsilon <= intersection_point_var.x() <= edge_rect_for_check.right() + epsilon and
                    edge_rect_for_check.top() - epsilon <= intersection_point_var.y() <= edge_rect_for_check.bottom() + epsilon):
                     intersect_points.append(QPointF(intersection_point_var))
        if not intersect_points: return item_rect.center()
        closest_point = intersect_points[0]
        min_dist_sq = (QLineF(line.p1(), closest_point).length())**2
        for pt in intersect_points[1:]:
            dist_sq = (QLineF(line.p1(), pt).length())**2
            if dist_sq < min_dist_sq: min_dist_sq = dist_sq; closest_point = pt
        return closest_point

    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty(): return
        painter.setRenderHint(QPainter.Antialiasing)
        current_pen = self.pen()
        if self.isSelected():
            stroker = QPainterPathStroker(); stroker.setWidth(current_pen.widthF() + 6)
            stroker.setCapStyle(Qt.RoundCap); stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path())
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(COLOR_ITEM_TRANSITION_SELECTION))
            painter.drawPath(selection_path_shape)
        painter.setPen(current_pen); painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())
        if self.path().elementCount() < 1 : return
        percent_at_end = 0.999
        if self.path().length() < 1 : percent_at_end = 0.9
        line_end_point = self.path().pointAtPercent(1.0)
        angle_at_end_rad = -self.path().angleAtPercent(percent_at_end) * (math.pi / 180.0)
        arrow_p1 = line_end_point + QPointF(math.cos(angle_at_end_rad - math.pi / 7) * self.arrow_size,
                                            math.sin(angle_at_end_rad - math.pi / 7) * self.arrow_size)
        arrow_p2 = line_end_point + QPointF(math.cos(angle_at_end_rad + math.pi / 7) * self.arrow_size,
                                            math.sin(angle_at_end_rad + math.pi / 7) * self.arrow_size)
        painter.setBrush(current_pen.color())
        painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics
            painter.setFont(self._font); fm = QFontMetrics(self._font)
            text_rect_original = fm.boundingRect(current_label)
            text_pos_on_path = self.path().pointAtPercent(0.5)
            angle_at_mid_deg = self.path().angleAtPercent(0.5)
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0)
            offset_dist = 10
            text_center_x = text_pos_on_path.x() + offset_dist * math.cos(offset_angle_rad)
            text_center_y = text_pos_on_path.y() + offset_dist * math.sin(offset_angle_rad)
            text_final_pos = QPointF(text_center_x - text_rect_original.width() / 2,
                                     text_center_y - text_rect_original.height() / 2)
            bg_padding = 2
            bg_rect = QRectF(text_final_pos.x() - bg_padding, text_final_pos.y() - bg_padding,
                             text_rect_original.width() + 2 * bg_padding, text_rect_original.height() + 2 * bg_padding)
            painter.setBrush(QColor(COLOR_BACKGROUND_LIGHT).lighter(102))
            painter.setPen(QPen(QColor(COLOR_BORDER_LIGHT), 0.5))
            painter.drawRoundedRect(bg_rect, 3, 3)
            painter.setPen(self._text_color)
            painter.drawText(text_final_pos, current_label)

    def get_data(self):
        return {
            'source': self.start_item.text_label if self.start_item else "None",
            'target': self.end_item.text_label if self.end_item else "None",
            'event': self.event_str, 'condition': self.condition_str, 'action': self.action_str,
            'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_TRANSITION_DEFAULT).name(),
            'description': self.description,
            'control_offset_x': self.control_point_offset.x(),
            'control_offset_y': self.control_point_offset.y()
        }

    def set_properties(self, event_str="", condition_str="", action_str="",
                       color_hex=None, description="", offset=None):
        changed = False
        if self.event_str != event_str: self.event_str = event_str; changed=True
        if self.condition_str != condition_str: self.condition_str = condition_str; changed=True
        if self.action_str != action_str: self.action_str = action_str; changed=True
        if self.description != description: self.description = description; changed=True
        new_color = QColor(color_hex) if color_hex else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        if self.base_color != new_color:
            self.base_color = new_color
            self.setPen(QPen(self.base_color, self._pen_width))
            changed = True
        if offset is not None and self.control_point_offset != offset:
            self.control_point_offset = offset
            changed = True
        if changed: self.prepareGeometryChange()
        if offset is not None : self.update_path()
        self.update()

    def set_control_point_offset(self, offset: QPointF):
        if self.control_point_offset != offset:
            self.control_point_offset = offset
            self.update_path(); self.update()


class GraphicsCommentItem(QGraphicsTextItem):
    Type = QGraphicsItem.UserType + 3
    def type(self): return GraphicsCommentItem.Type

    def __init__(self, x, y, text="Comment"):
        super().__init__()
        self.setPlainText(text); self.setPos(x, y)
        self.setFont(QFont(APP_FONT_FAMILY, 9))
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self._default_width = 150; self.setTextWidth(self._default_width)
        self.border_pen = QPen(QColor(COLOR_ITEM_COMMENT_BORDER), 1)
        self.background_brush = QBrush(QColor(COLOR_ITEM_COMMENT_BG))
        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(8); self.shadow_effect.setColor(QColor(0, 0, 0, 50))
        self.shadow_effect.setOffset(2, 2); self.setGraphicsEffect(self.shadow_effect)
        if self.document(): self.document().contentsChanged.connect(self._on_contents_changed)

    def _on_contents_changed(self):
        self.prepareGeometryChange()
        if self.scene(): self.scene().item_moved.emit(self)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self.border_pen); painter.setBrush(self.background_brush)
        rect = self.boundingRect()
        painter.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5), 4, 4)
        self.setDefaultTextColor(QColor(COLOR_TEXT_PRIMARY))
        super().paint(painter, option, widget)
        if self.isSelected():
            selection_pen = QPen(QColor(COLOR_ACCENT_PRIMARY), 1.5, Qt.DashLine)
            painter.setPen(selection_pen); painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())

    def get_data(self):
        doc_width = self.document().idealWidth() if self.textWidth() < 0 else self.textWidth()
        return {'text': self.toPlainText(), 'x': self.x(), 'y': self.y(), 'width': doc_width}

    def set_properties(self, text, width=None):
        current_text = self.toPlainText(); text_changed = (current_text != text)
        width_changed = False
        current_text_width = self.textWidth()
        target_width = width if width and width > 0 else self._default_width
        if current_text_width != target_width: width_changed = True
        if text_changed: self.setPlainText(text)
        if width_changed: self.setTextWidth(target_width)
        if text_changed or width_changed : self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)
    
# bsm_designer_project/graphics_scene.py

# Add this import at the top with other imports
from utils import get_standard_icon

# Update the imports section to include utils
import sys
import os
import json # For get_diagram_data
import logging # For logging within the scene
from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsLineItem,
    QMenu, QMessageBox, QDialog, QStyle, QGraphicsSceneMouseEvent,
    QGraphicsSceneDragDropEvent
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QKeyEvent, QCursor, QMouseEvent,
    QWheelEvent
)
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF, pyqtSignal, QPoint

# Add the import for get_standard_icon
from utils import get_standard_icon  # Add this line

from config import (
    COLOR_BACKGROUND_LIGHT, COLOR_GRID_MINOR, COLOR_GRID_MAJOR, COLOR_ACCENT_PRIMARY,
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_COMMENT_BG
)
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
# Dialogs are needed for edit_item_properties

# Undo commands
from undo_commands import AddItemCommand, MoveItemsCommand, RemoveItemsCommand, EditItemPropertiesCommand


logger = logging.getLogger(__name__) # Logger specific to this module

class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem)
    modifiedStatusChanged = pyqtSignal(bool)

    def __init__(self, undo_stack, parent_window=None):
        super().__init__(parent_window) # Pass parent_window to QGraphicsScene
        self.parent_window = parent_window # Store reference to main window or parent dialog
        self.setSceneRect(0, 0, 6000, 4500)
        self.current_mode = "select"
        self.transition_start_item = None
        self.undo_stack = undo_stack # This is QUndoStack instance
        self._dirty = False
        self._mouse_press_items_positions = {}
        self._temp_transition_line = None

        self.item_moved.connect(self._handle_item_moved_visual_update)

        self.grid_size = 20
        self.grid_pen_light = QPen(QColor(COLOR_GRID_MINOR), 0.7, Qt.DotLine)
        self.grid_pen_dark = QPen(QColor(COLOR_GRID_MAJOR), 0.9, Qt.SolidLine)
        self.setBackgroundBrush(QColor(COLOR_BACKGROUND_LIGHT))
        self.snap_to_grid_enabled = True

    def _log_to_parent(self, level, message):
        """Helper to log through the parent_window if it has a log_message method."""
        if self.parent_window and hasattr(self.parent_window, 'log_message'):
            self.parent_window.log_message(level, message)
        else: # Fallback if no parent logger
            logger.log(getattr(logging, level.upper(), logging.INFO), f"(SceneDirect) {message}")

    def log_function(self, message: str, level: str = "ERROR"):
        """Public logging function for external modules like undo_commands."""
        self._log_to_parent(level.upper(), message)


    def _update_connected_transitions(self, state_item: GraphicsStateItem):
        for item in self.items():
            if isinstance(item, GraphicsTransitionItem):
                if item.start_item == state_item or item.end_item == state_item:
                    item.update_path()

    def _update_transitions_for_renamed_state(self, old_name:str, new_name:str):
        # This method is called when a state's name changes.
        # It's primarily for logging or potentially complex updates if transitions stored names directly.
        # Since transitions store references to GraphicsStateItem, they update visually automatically.
        # The get_data() method for transitions uses the current text_label of the connected items.
        self._log_to_parent("INFO", f"Scene notified: State '{old_name}' changed to '{new_name}'. Dependent transitions' data should reflect this.")


    def get_state_by_name(self, name: str) -> GraphicsStateItem | None:
        for item in self.items():
            if isinstance(item, GraphicsStateItem) and item.text_label == name:
                return item
        return None

    def set_dirty(self, dirty=True):
        if self._dirty != dirty:
            self._dirty = dirty
            self.modifiedStatusChanged.emit(dirty)
        if self.parent_window and hasattr(self.parent_window, '_update_save_actions_enable_state'):
             self.parent_window._update_save_actions_enable_state()

    def is_dirty(self):
        return self._dirty

    def set_mode(self, mode: str):
        old_mode = self.current_mode
        if old_mode == mode: return
        self.current_mode = mode
        self._log_to_parent("INFO", f"Interaction mode changed to: {mode}")
        self.transition_start_item = None
        if self._temp_transition_line:
            self.removeItem(self._temp_transition_line)
            self._temp_transition_line = None
        
        # Update cursor based on mode (delegated to ZoomableView if it's the primary view)
        if self.views(): # Check if there are views attached
            main_view = self.views()[0]
            if hasattr(main_view, '_restore_cursor_to_scene_mode'):
                main_view._restore_cursor_to_scene_mode()

        # Enable/disable item movability
        for item in self.items():
            movable_flag = mode == "select"
            if isinstance(item, (GraphicsStateItem, GraphicsCommentItem)):
                item.setFlag(QGraphicsItem.ItemIsMovable, movable_flag)

        # Update mode buttons in the parent_window if it has them (e.g., MainWindow or SubFSMEditorDialog)
        if self.parent_window and hasattr(self.parent_window, 'mode_action_group'): # Main window actions
            actions_map = {
                "select": getattr(self.parent_window, 'select_mode_action', None),
                "state": getattr(self.parent_window, 'add_state_mode_action', None),
                "transition": getattr(self.parent_window, 'add_transition_mode_action', None),
                "comment": getattr(self.parent_window, 'add_comment_mode_action', None)
            }
            action_to_check = actions_map.get(mode)
            if action_to_check and hasattr(action_to_check, 'isChecked') and not action_to_check.isChecked():
                action_to_check.setChecked(True)
        elif self.parent_window and hasattr(self.parent_window, 'sub_mode_action_group'): # SubFSMEditorDialog actions
            actions_map_sub = {
                "select": getattr(self.parent_window, 'sub_select_action', None),
                "state": getattr(self.parent_window, 'sub_add_state_action', None),
                "transition": getattr(self.parent_window, 'sub_add_transition_action', None),
                "comment": getattr(self.parent_window, 'sub_add_comment_action', None)
            }
            action_to_check_sub = actions_map_sub.get(mode)
            if action_to_check_sub and hasattr(action_to_check_sub, 'isChecked') and not action_to_check_sub.isChecked():
                action_to_check_sub.setChecked(True)


    def select_all(self):
        for item in self.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable:
                item.setSelected(True)

    def _handle_item_moved_visual_update(self, moved_item):
        if isinstance(moved_item, GraphicsStateItem):
            self._update_connected_transitions(moved_item)


    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.scenePos()
        items_at_pos = self.items(pos)
        # Find the topmost relevant item (State > Comment/Transition > Others)
        top_item_at_pos = next((item for item in items_at_pos if isinstance(item, GraphicsStateItem)), None)
        if not top_item_at_pos:
            top_item_at_pos = next((item for item in items_at_pos if isinstance(item, (GraphicsCommentItem, GraphicsTransitionItem))), None)
            if not top_item_at_pos and items_at_pos: top_item_at_pos = items_at_pos[0] # Fallback to any item

        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size - 60 # Center item roughly on grid
                grid_y = round(pos.y() / self.grid_size) * self.grid_size - 30
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type="State")
            elif self.current_mode == "comment":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size
                grid_y = round(pos.y() / self.grid_size) * self.grid_size
                self._add_item_interactive(QPointF(grid_x, grid_y), item_type="Comment")
            elif self.current_mode == "transition":
                if isinstance(top_item_at_pos, GraphicsStateItem):
                    self._handle_transition_click(top_item_at_pos, pos)
                else: # Clicked empty space or non-state item
                    if self.transition_start_item:
                        self._log_to_parent("INFO", "Transition drawing cancelled (clicked non-state/empty space).")
                    self.transition_start_item = None # Cancel ongoing transition
                    if self._temp_transition_line:
                        self.removeItem(self._temp_transition_line)
                        self._temp_transition_line = None
            else: # Select mode
                self._mouse_press_items_positions.clear()
                selected_items_list = self.selectedItems()
                if selected_items_list: # If items are already selected, prepare for potential move
                    for item_to_process in [item for item in selected_items_list if item.flags() & QGraphicsItem.ItemIsMovable]:
                        self._mouse_press_items_positions[item_to_process] = item_to_process.pos()
                super().mousePressEvent(event) # Allow default selection/move initiation
        elif event.button() == Qt.RightButton:
            if top_item_at_pos and isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem)):
                if not top_item_at_pos.isSelected(): # If right-clicked item is not selected, select it exclusively
                    self.clearSelection()
                    top_item_at_pos.setSelected(True)
                self._show_context_menu(top_item_at_pos, event.screenPos()) # Line 199 in your trace
            else: # Right-click on empty space
                self.clearSelection()
                # Optionally show a scene context menu here (e.g., "Add State", "Paste")
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, event.scenePos()))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton and self.current_mode == "select":
            if self._mouse_press_items_positions: # If a move operation was potentially started
                moved_items_data_for_command = [] # (item, old_pos, new_pos)
                emit_item_moved_for_these = []

                for item, old_pos in self._mouse_press_items_positions.items():
                    new_pos = item.pos()
                    snapped_new_pos = new_pos
                    if self.snap_to_grid_enabled:
                        snapped_x = round(new_pos.x() / self.grid_size) * self.grid_size
                        snapped_y = round(new_pos.y() / self.grid_size) * self.grid_size
                        snapped_new_pos = QPointF(snapped_x, snapped_y)
                        if new_pos != snapped_new_pos:
                             item.setPos(snapped_new_pos) # Snap the item visually

                    if (snapped_new_pos - old_pos).manhattanLength() > 0.1: # Check if item actually moved
                        moved_items_data_for_command.append((item, old_pos, snapped_new_pos))
                        emit_item_moved_for_these.append(item)
                
                if moved_items_data_for_command:
                    cmd = MoveItemsCommand(moved_items_data_for_command, "Move Items")
                    self.undo_stack.push(cmd)
                    # No need to emit item_moved here, MoveItemsCommand.redo/_apply_positions will handle visual updates
                    # which in turn will trigger _handle_item_moved_visual_update via item.setPos -> itemChange
                
                self._mouse_press_items_positions.clear()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        items_at_pos = self.items(event.scenePos())
        item_to_edit = next((item for item in items_at_pos if isinstance(item, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem))), None)
        if item_to_edit:
            self.edit_item_properties(item_to_edit)
        else:
            super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, item, global_pos):
        menu = QMenu()
        edit_action = menu.addAction(get_standard_icon(QStyle.SP_DialogApplyButton, "Edt"), "Properties...")
        
        if isinstance(item, GraphicsStateItem) and item.is_superstate:
            # Assuming StatePropertiesDialog handles the "Edit Sub-Machine..." button internally
            # No need for a separate menu item here if double-click/Properties opens it
            pass

        delete_action = menu.addAction(get_standard_icon(QStyle.SP_TrashIcon, "Del"), "Delete")

        action = menu.exec_(global_pos) # For Qt5, exec_() is preferred for QMenu
        if action == edit_action:
            self.edit_item_properties(item) # Line 263 in your trace
        elif action == delete_action:
            if not item.isSelected(): # Ensure item is selected before deleting
                self.clearSelection()
                item.setSelected(True)
            self.delete_selected_items()

    def edit_item_properties(self, item):
        # Import dialogs here instead of at module level
        from dialogs import StatePropertiesDialog, TransitionPropertiesDialog, CommentPropertiesDialog
    
        dialog_executed_and_accepted = False
        new_props_from_dialog = None
        DialogType = None

        # Determine which dialog to use based on item type
        old_props = item.get_data() if hasattr(item, 'get_data') else {} # Ensure old_props is initialized
        if isinstance(item, GraphicsStateItem): DialogType = StatePropertiesDialog
        elif isinstance(item, GraphicsTransitionItem): DialogType = TransitionPropertiesDialog
        elif isinstance(item, GraphicsCommentItem): DialogType = CommentPropertiesDialog
        else: return # Unknown item type

        # The parent for the dialog should be the main window or the current dialog (SubFSMEditor)
        # self.parent_window is set during DiagramScene initialization
        dialog_parent = self.parent_window if self.parent_window else self.views()[0] if self.views() else None
        
        if DialogType == StatePropertiesDialog:
            dialog = DialogType(parent=dialog_parent, current_properties=old_props, is_new_state=False, scene_ref=self)
        else: # For TransitionPropertiesDialog and CommentPropertiesDialog
            dialog = DialogType(parent=dialog_parent, current_properties=old_props)
        
        if dialog.exec() == QDialog.Accepted: # Use exec()
            dialog_executed_and_accepted = True
            new_props_from_dialog = dialog.get_properties()

            if isinstance(item, GraphicsStateItem): # Special handling for state name uniqueness
                # old_name = old_props.get('name') # old_props is already defined above
                current_new_name = new_props_from_dialog.get('name')
                existing_state_with_new_name = self.get_state_by_name(current_new_name)
                # Allow if it's the same item, or if new name is unique
                if current_new_name != old_props.get('name') and existing_state_with_new_name and existing_state_with_new_name != item:
                    QMessageBox.warning(dialog_parent, "Duplicate Name", f"A state with the name '{current_new_name}' already exists.")
                    return # Don't proceed with edit if name is duplicate

        if dialog_executed_and_accepted and new_props_from_dialog is not None:
            # Merge new properties with old ones to ensure all keys are present if dialog doesn't return all
            final_new_props = old_props.copy()
            final_new_props.update(new_props_from_dialog)

            if final_new_props == old_props:
                self._log_to_parent("INFO", "Properties unchanged.")
                return

            cmd = EditItemPropertiesCommand(item, old_props, final_new_props, f"Edit {type(item).__name__} Properties")
            self.undo_stack.push(cmd)

            item_name_for_log = final_new_props.get('name', final_new_props.get('event', final_new_props.get('text', 'Item')))
            self._log_to_parent("INFO", f"Properties updated for: {item_name_for_log}")

        self.update() # Update the scene to reflect changes

    def _add_item_interactive(self, pos: QPointF, item_type: str, name_prefix:str="Item", initial_data:dict=None):
        from dialogs import StatePropertiesDialog, CommentPropertiesDialog
        current_item = None
        initial_data = initial_data or {}
        is_initial_state_from_drag = initial_data.get('is_initial', False)
        is_final_state_from_drag = initial_data.get('is_final', False)

        # Parent for dialogs
        dialog_parent = self.parent_window if self.parent_window else self.views()[0] if self.views() else None

        if item_type == "State":
            i = 1
            base_name = name_prefix if name_prefix != "Item" else "State" 
            while self.get_state_by_name(f"{base_name}{i}"): # Ensure unique name
                i += 1
            default_name = f"{base_name}{i}"

            initial_dialog_props = {
                'name': default_name,
                'is_initial': is_initial_state_from_drag,
                'is_final': is_final_state_from_drag,
                'color': initial_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG),
                'entry_action':"", 'during_action':"", 'exit_action':"", 'description':"",
                'is_superstate': False, 'sub_fsm_data': {'states': [], 'transitions': [], 'comments': []}
            }
            # Pass self (DiagramScene) as scene_ref to StatePropertiesDialog
            props_dialog = StatePropertiesDialog(dialog_parent, current_properties=initial_dialog_props, is_new_state=True, scene_ref=self)

            if props_dialog.exec() == QDialog.Accepted:
                final_props = props_dialog.get_properties()
                # Check for duplicate name again after dialog
                if self.get_state_by_name(final_props['name']) and final_props['name'] != default_name: 
                    QMessageBox.warning(dialog_parent, "Duplicate Name", f"A state named '{final_props['name']}' already exists.")
                else:
                    current_item = GraphicsStateItem(
                        pos.x(), pos.y(), 120, 60, # Default size
                        final_props['name'],
                        final_props['is_initial'], final_props['is_final'],
                        final_props.get('color'),
                        final_props.get('entry_action',""),
                        final_props.get('during_action',""),
                        final_props.get('exit_action',""),
                        final_props.get('description',""),
                        final_props.get('is_superstate', False),
                        final_props.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]})
                    )
            if self.current_mode == "state": # Switch back to select mode after adding
                self.set_mode("select")
            if not current_item: return # Dialog cancelled or error

        elif item_type == "Comment":
            initial_text = initial_data.get('text', "Comment" if name_prefix == "Item" else name_prefix)
            comment_props_dialog = CommentPropertiesDialog(dialog_parent, {'text': initial_text}) 

            if comment_props_dialog.exec() == QDialog.Accepted:
                final_comment_props = comment_props_dialog.get_properties()
                if final_comment_props['text']: # Ensure comment is not empty
                     current_item = GraphicsCommentItem(pos.x(), pos.y(), final_comment_props['text'])
                else: # If user cleared text and clicked OK
                    self.set_mode("select" if self.current_mode == "comment" else self.current_mode)
                    return
            else: # Dialog cancelled
                self.set_mode("select" if self.current_mode == "comment" else self.current_mode)
                return
        else:
            self._log_to_parent("WARNING", f"Unknown item type for addition: {item_type}")
            return

        if current_item:
            cmd = AddItemCommand(self, current_item, f"Add {item_type}")
            self.undo_stack.push(cmd)
            log_name = getattr(current_item, 'text_label', None) or \
                       (getattr(current_item, 'toPlainText', lambda: "Item")() if isinstance(current_item, GraphicsCommentItem) else "Item")
            self._log_to_parent("INFO", f"Added {item_type}: {log_name} at ({pos.x():.0f},{pos.y():.0f})")


    def _handle_transition_click(self, clicked_state_item: GraphicsStateItem, click_pos: QPointF):
        from dialogs import TransitionPropertiesDialog
        dialog_parent = self.parent_window if self.parent_window else self.views()[0] if self.views() else None
        if not self.transition_start_item: # Starting a new transition
            self.transition_start_item = clicked_state_item
            if not self._temp_transition_line:
                self._temp_transition_line = QGraphicsLineItem()
                self._temp_transition_line.setPen(QPen(QColor(COLOR_ACCENT_PRIMARY), 1.8, Qt.DashLine))
                self.addItem(self._temp_transition_line) # Add to scene to be visible
            center_start = self.transition_start_item.sceneBoundingRect().center()
            self._temp_transition_line.setLine(QLineF(center_start, click_pos))
            self._log_to_parent("INFO", f"Transition started from: {clicked_state_item.text_label}. Click target state.")
        else: # Completing a transition
            if self._temp_transition_line: # Remove temporary line
                self.removeItem(self._temp_transition_line)
                self._temp_transition_line = None

            initial_props = { # Default properties for a new transition
                'event': "", 'condition': "", 'action': "",
                'color': COLOR_ITEM_TRANSITION_DEFAULT, 'description':"",
                'control_offset_x':0, 'control_offset_y':0
            }
            dialog = TransitionPropertiesDialog(dialog_parent, current_properties=initial_props, is_new_transition=True)

            if dialog.exec() == QDialog.Accepted:
                props = dialog.get_properties()
                new_transition = GraphicsTransitionItem(
                    self.transition_start_item, clicked_state_item,
                    event_str=props['event'], condition_str=props['condition'], action_str=props['action'],
                    color=props.get('color'), description=props.get('description', "")
                )
                new_transition.set_control_point_offset(QPointF(props['control_offset_x'],props['control_offset_y']))

                cmd = AddItemCommand(self, new_transition, "Add Transition")
                self.undo_stack.push(cmd)
                self._log_to_parent("INFO", f"Added transition: {self.transition_start_item.text_label} -> {clicked_state_item.text_label} [{new_transition._compose_label_string()}]")
            else: # Transition dialog cancelled
                self._log_to_parent("INFO", "Transition addition cancelled by user.")

            self.transition_start_item = None # Reset for next transition
            self.set_mode("select") # Switch back to select mode

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Delete or (event.key() == Qt.Key_Backspace and sys.platform != 'darwin'): # Backspace for delete on some platforms
            if self.selectedItems():
                self.delete_selected_items()
        elif event.key() == Qt.Key_Escape:
            if self.current_mode == "transition" and self.transition_start_item:
                self.transition_start_item = None
                if self._temp_transition_line:
                    self.removeItem(self._temp_transition_line)
                    self._temp_transition_line = None
                self._log_to_parent("INFO", "Transition drawing cancelled by Escape.")
                self.set_mode("select")
            elif self.current_mode != "select": # If in any other add mode, escape to select mode
                self.set_mode("select")
            else: # In select mode, escape clears selection
                self.clearSelection()
        else:
            super().keyPressEvent(event)

    def delete_selected_items(self):
        selected = self.selectedItems()
        if not selected: return

        items_to_delete_with_related = set() # Use a set to avoid duplicates
        for item in selected:
            items_to_delete_with_related.add(item)
            if isinstance(item, GraphicsStateItem): # If a state is deleted, also delete its connected transitions
                for scene_item in self.items():
                    if isinstance(scene_item, GraphicsTransitionItem):
                        if scene_item.start_item == item or scene_item.end_item == item:
                            items_to_delete_with_related.add(scene_item)

        if items_to_delete_with_related:
            cmd = RemoveItemsCommand(self, list(items_to_delete_with_related), "Delete Items")
            self.undo_stack.push(cmd)
            self._log_to_parent("INFO", f"Queued deletion of {len(items_to_delete_with_related)} item(s).")
            self.clearSelection() # Clear selection after queuing deletion

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        pos = event.scenePos()
        if event.mimeData().hasFormat("application/x-bsm-tool"):
            item_type_data_str = event.mimeData().text() # e.g., "State", "Initial State"

            # Snap drop position to grid
            grid_x = round(pos.x() / self.grid_size) * self.grid_size
            grid_y = round(pos.y() / self.grid_size) * self.grid_size

            # Adjust for item center if it's a state-like item
            if "State" in item_type_data_str: # Catches "State", "Initial State", "Final State"
                grid_x -= 60 # Half default width
                grid_y -= 30 # Half default height

            initial_props_for_add = {}
            actual_item_type_to_add = "Item" # Default, should be overridden
            name_prefix_for_add = "Item" # Default name prefix

            if item_type_data_str == "State":
                actual_item_type_to_add = "State"
                name_prefix_for_add = "State"
            elif item_type_data_str == "Initial State":
                actual_item_type_to_add = "State"
                name_prefix_for_add = "Initial" # Or keep "State" and just set flag
                initial_props_for_add['is_initial'] = True
            elif item_type_data_str == "Final State":
                actual_item_type_to_add = "State"
                name_prefix_for_add = "Final"
                initial_props_for_add['is_final'] = True
            elif item_type_data_str == "Comment":
                actual_item_type_to_add = "Comment"
                name_prefix_for_add = "Note"
            else:
                self._log_to_parent("WARNING", f"Unknown item type dropped: {item_type_data_str}")
                event.ignore()
                return

            self._add_item_interactive(QPointF(grid_x, grid_y),
                                       item_type=actual_item_type_to_add,
                                       name_prefix=name_prefix_for_add,
                                       initial_data=initial_props_for_add)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def get_diagram_data(self):
        data = {'states': [], 'transitions': [], 'comments': []}
        for item in self.items():
            if isinstance(item, GraphicsStateItem):
                data['states'].append(item.get_data())
            elif isinstance(item, GraphicsTransitionItem):
                if item.start_item and item.end_item: # Ensure transition is valid
                    data['transitions'].append(item.get_data())
                else:
                    self._log_to_parent("WARNING", f"Skipping save of orphaned/invalid transition: '{item._compose_label_string()}'.")
            elif isinstance(item, GraphicsCommentItem):
                data['comments'].append(item.get_data())
        return data

    def load_diagram_data(self, data):
        self.clear() # Clear existing items
        self.set_dirty(False) # Reset dirty state after load
        state_items_map = {} # To link transitions by state name

        # Load states
        for state_data in data.get('states', []):
            state_item = GraphicsStateItem(
                state_data['x'], state_data['y'],
                state_data.get('width', 120), state_data.get('height', 60),
                state_data['name'],
                state_data.get('is_initial', False), state_data.get('is_final', False),
                state_data.get('color', COLOR_ITEM_STATE_DEFAULT_BG),
                state_data.get('entry_action',""), state_data.get('during_action',""),
                state_data.get('exit_action',""), state_data.get('description',""),
                state_data.get('is_superstate', False), 
                state_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}) 
            )
            self.addItem(state_item)
            state_items_map[state_data['name']] = state_item

        # Load transitions
        for trans_data in data.get('transitions', []):
            src_item = state_items_map.get(trans_data['source'])
            tgt_item = state_items_map.get(trans_data['target'])
            if src_item and tgt_item:
                trans_item = GraphicsTransitionItem(
                    src_item, tgt_item,
                    event_str=trans_data.get('event',""), condition_str=trans_data.get('condition',""),
                    action_str=trans_data.get('action',""),
                    color=trans_data.get('color', COLOR_ITEM_TRANSITION_DEFAULT),
                    description=trans_data.get('description',"")
                )
                trans_item.set_control_point_offset(QPointF(trans_data.get('control_offset_x',0), trans_data.get('control_offset_y',0)))
                self.addItem(trans_item)
            else:
                label_info = f"{trans_data.get('event','')}{trans_data.get('condition','')}{trans_data.get('action','')}"
                self._log_to_parent("WARNING", f"Load Warning: Could not link transition '{label_info}' due to missing states: Source='{trans_data['source']}', Target='{trans_data['target']}'.")


        # Load comments
        for comment_data in data.get('comments', []):
            comment_item = GraphicsCommentItem(comment_data['x'], comment_data['y'], comment_data.get('text', ""))
            comment_item.setTextWidth(comment_data.get('width', 150)) # Set width if specified
            self.addItem(comment_item)

        self.set_dirty(False) # Should be clean after a successful load
        if self.undo_stack: self.undo_stack.clear() # Clear undo stack after loading a new file

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect) # Draw default background (e.g., color)

        # Determine visible rect for efficient grid drawing
        # (rect is the area to be redrawn, not necessarily the full visible area)
        view_rect = self.views()[0].viewport().rect() if self.views() else rect
        visible_scene_rect = self.views()[0].mapToScene(view_rect).boundingRect() if self.views() else rect

        # Calculate grid lines based on visible_scene_rect
        left = int(visible_scene_rect.left() / self.grid_size) * self.grid_size - self.grid_size # Extend slightly beyond
        right = int(visible_scene_rect.right() / self.grid_size) * self.grid_size + self.grid_size
        top = int(visible_scene_rect.top() / self.grid_size) * self.grid_size - self.grid_size
        bottom = int(visible_scene_rect.bottom() / self.grid_size) * self.grid_size + self.grid_size

        # Draw minor grid lines
        painter.setPen(self.grid_pen_light)
        for x in range(left, right, self.grid_size):
            if x % (self.grid_size * 5) != 0: # Don't draw minor if it's a major
                painter.drawLine(x, top, x, bottom)
        for y in range(top, bottom, self.grid_size):
            if y % (self.grid_size * 5) != 0:
                painter.drawLine(left, y, right, y)

        # Draw major grid lines
        major_grid_size = self.grid_size * 5
        # Adjust start for major lines to align with multiples of major_grid_size
        first_major_left = left - (left % major_grid_size) if left >=0 else left - (left % major_grid_size) - major_grid_size
        first_major_top = top - (top % major_grid_size) if top >= 0 else top - (top % major_grid_size) - major_grid_size

        painter.setPen(self.grid_pen_dark)
        for x in range(first_major_left, right, major_grid_size):
            painter.drawLine(x, top, x, bottom)
        for y in range(first_major_top, bottom, major_grid_size):
            painter.drawLine(left, y, right, y)


class ZoomableView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag) # Default drag mode for selection
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate) # Optimization
        self.zoom_level = 0
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._is_panning_with_space = False
        self._is_panning_with_mouse_button = False # For middle mouse button panning
        self._last_pan_point = QPoint()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier: # Zoom with Ctrl + Mouse Wheel
            delta = event.angleDelta().y()
            factor = 1.12 if delta > 0 else 1 / 1.12
            new_zoom_level = self.zoom_level + (1 if delta > 0 else -1)
            # Limit zoom levels to prevent excessive zoom in/out
            if -15 <= new_zoom_level <= 25: # Arbitrary limits, adjust as needed
                self.scale(factor, factor)
                self.zoom_level = new_zoom_level
            event.accept()
        else: # Default behavior for vertical scrolling if Ctrl not pressed
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = True
            self._last_pan_point = self.mapFromGlobal(QCursor.pos()) # Use global pos for consistency
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal: # Zoom in
            self.scale(1.12, 1.12); self.zoom_level +=1
        elif event.key() == Qt.Key_Minus: # Zoom out
            self.scale(1/1.12, 1/1.12); self.zoom_level -=1
        elif event.key() == Qt.Key_0 or event.key() == Qt.Key_Asterisk: # Reset zoom and center
            self.resetTransform()
            self.zoom_level = 0
            if self.scene():
                content_rect = self.scene().itemsBoundingRect()
                if not content_rect.isEmpty():
                    self.centerOn(content_rect.center())
                elif self.scene().sceneRect(): # Fallback to sceneRect if no items
                    self.centerOn(self.scene().sceneRect().center())
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and self._is_panning_with_space and not event.isAutoRepeat():
            self._is_panning_with_space = False
            if not self._is_panning_with_mouse_button: # Restore cursor only if not also panning with mouse
                self._restore_cursor_to_scene_mode()
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton or \
           (self._is_panning_with_space and event.button() == Qt.LeftButton):
            self._last_pan_point = event.pos() # Store local position
            self.setCursor(Qt.ClosedHandCursor)
            self._is_panning_with_mouse_button = True
            event.accept()
        else:
            self._is_panning_with_mouse_button = False # Reset flag
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button:
            delta_view = event.pos() - self._last_pan_point
            self._last_pan_point = event.pos()
            # Adjust scrollbars to pan the view
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta_view.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta_view.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_panning_with_mouse_button and \
           (event.button() == Qt.MiddleButton or (self._is_panning_with_space and event.button() == Qt.LeftButton)):
            self._is_panning_with_mouse_button = False
            if self._is_panning_with_space: # If space is still held, keep OpenHand
                self.setCursor(Qt.OpenHandCursor)
            else: # Otherwise, restore to mode-specific cursor
                self._restore_cursor_to_scene_mode()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _restore_cursor_to_scene_mode(self):
        # Set cursor based on the current scene mode
        current_scene_mode = self.scene().current_mode if self.scene() and hasattr(self.scene(), 'current_mode') else "select"
        if current_scene_mode == "select":
            self.setCursor(Qt.ArrowCursor)
        elif current_scene_mode in ["state", "comment"]:
            self.setCursor(Qt.CrossCursor)
        elif current_scene_mode == "transition":
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor) # Default