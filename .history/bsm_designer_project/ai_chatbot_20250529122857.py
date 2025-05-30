# bsm_designer_project/ai_chatbot.py

from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTime, QTimer, Qt, QMetaObject, pyqtSlot, Q_ARG
import json
import re
import logging
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold # For safety settings
import google.api_core.exceptions # For Gemini API exceptions

logger = logging.getLogger(__name__)

class ChatbotWorker(QObject):
    responseReady = pyqtSignal(str, bool)
    errorOccurred = pyqtSignal(str)
    statusUpdate = pyqtSignal(str)

    def __init__(self, api_key, model_name="gemini-1.5-flash-latest", parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.model_name = model_name
        self.client: genai.GenerativeModel | None = None
        self.conversation_history = [] # Stores dicts: {"role": "user/model", "parts": [{"text": "..."}]}
        self.current_diagram_context_json_str: str | None = None
        self._current_processing_had_error = False
        self._is_stopped = False
        self._initialize_client()
        logger.info(f"ChatbotWorker initialized (Gemini API Key {'SET' if api_key else 'NOT SET'}).")

    def _initialize_client(self):
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                # Safety settings: BLOCK_NONE allows all content. Review for production.
                # For a tool like this, BLOCK_NONE is often necessary for code generation requests.
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
                # System instruction is not set here because it's dynamic (based on diagram context)
                # and will be prepended to the user message for the current turn.
                self.client = genai.GenerativeModel(self.model_name, safety_settings=safety_settings)
                logger.info(f"Gemini client initialized for model {self.model_name}.")
            except Exception as e:
                self.client = None
                error_msg = f"Failed to initialize Gemini client: {e}"
                logger.error(error_msg, exc_info=True)
                self.errorOccurred.emit(error_msg)
        else:
            self.client = None
            logger.info("Gemini client not initialized (no API key).")

    @pyqtSlot(str)
    def set_api_key_slot(self, api_key: str):
        logger.info(f"WORKER: set_api_key_slot called (new key {'SET' if api_key else 'NOT SET'}).")
        self.api_key = api_key
        self._initialize_client()

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
        self._current_processing_had_error = False # Reset error flag for this specific processing attempt

        if not self.api_key or not self.client:
            error_msg = "Gemini API key not set or client not initialized. Please set it in AI Assistant Settings."
            logger.warning("process_message: %s", error_msg)
            self.errorOccurred.emit(error_msg)
            self.statusUpdate.emit("Status: API Key required.")
            self._current_processing_had_error = True
            return

        if self._is_stopped: # Check again before potentially long operations
            logger.info("WORKER_PROCESS: Worker stopped before system prompt generation.")
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

        # --- System Prompt Construction ---
        system_prompt_parts = ["You are a helpful assistant for designing Finite State Machines."]
        if self.current_diagram_context_json_str:
            try:
                diagram = json.loads(self.current_diagram_context_json_str)
                if "error" not in diagram: # Check if the context itself is an error message
                    state_names = [s.get('name', 'UnnamedState') for s in diagram.get('states', [])]
                    num_transitions = len(diagram.get('transitions', []))
                    if state_names:
                        state_names_list_str = ', '.join(state_names[:5])
                        if len(state_names) > 5:
                            state_names_list_str += f" and {len(state_names)-5} other(s)"

                        max_state_names_summary_len = 150 # Truncate if too long
                        if len(state_names_list_str) > max_state_names_summary_len:
                            state_names_list_str = state_names_list_str[:max_state_names_summary_len - 3] + "..."
                        
                        context_summary = (
                            f" The current diagram has states: {state_names_list_str}."
                            f" It has {num_transitions} transition(s)."
                        )
                        system_prompt_parts.append(context_summary)
                    else:
                        system_prompt_parts.append(" The current diagram is empty.")
                else: # Context string contained an error message
                    system_prompt_parts.append(f" Diagram context indicates an error: {diagram.get('error','Unknown error')}")
            except json.JSONDecodeError:
                logger.warning("WORKER_PROCESS_CTX_ERROR: JSONDecodeError processing diagram context.", exc_info=True)
                system_prompt_parts.append(" (Error reading diagram context in worker - invalid JSON).")
            except Exception as e_ctx:
                logger.error(f"WORKER_PROCESS_CTX_ERROR: Error processing diagram context: {e_ctx}", exc_info=True)
                system_prompt_parts.append(" (Technical issue with diagram context string processing).")
        else:
             system_prompt_parts.append(" No diagram context is currently active or provided for this request.") # Slightly improved wording

        if is_fsm_generation_attempt:
            system_prompt_parts.append(
                " When asked to generate an FSM, you MUST respond with ONLY a valid JSON object that directly represents the FSM data. "
                "The root of the JSON MUST be an object. "
                "This JSON object MUST have a top-level string key 'description' for a brief FSM description (e.g., 'A simple traffic light controller.'). "
                "It MUST have a key 'states' which is a list of state objects. "
                "Each state object MUST have a 'name' (string, required and unique for the FSM). "
                "Optional state object keys: 'is_initial' (boolean, default false), 'is_final' (boolean, default false), "
                "'entry_action' (string), 'during_action' (string), 'exit_action' (string), "
                "'action_language' (string, e.g., 'Python (Generic Simulation)', 'Arduino (C++)'), " 
                "and a 'properties' object (optional) which can contain 'color' (string, CSS hex e.g., '#RRGGBB'). "
                "The JSON object MUST also have a key 'transitions' which is a list of transition objects. "
                "Each transition object MUST have 'source' (string, an existing state name from the 'states' list) and 'target' (string, an existing state name from the 'states' list). "
                "Optional transition object keys: 'event' (string), 'condition' (string), 'action' (string), "
                "'action_language' (string, e.g., 'Python (Generic Simulation)', 'Arduino (C++)'), " 
                "'control_offset_x' (number, for curve horizontal bend), 'control_offset_y' (number, for curve vertical shift from midpoint), "
                "and a 'properties' object (optional) for 'color'. "
                "Optionally, include a top-level key 'comments' which is a list of comment objects. Each comment object can have 'text' (string), 'x' (number, optional for layout hint), 'y' (number, optional for layout hint), 'width' (number, optional). "
                "Do not include any state positions (x, y, width, height for states) in the JSON, as the application will handle layout. "
                "Your entire response must be ONLY this single JSON object, correctly formatted and parsable by json.loads(). Do not include any other text, greetings, explanations, or markdown formatting like ```json outside or inside this single JSON object."
            )
        else: # Not an FSM generation attempt
            if is_embedded_code_request:
                system_prompt_parts.append(
                    " You are also an expert assistant for mechatronics and embedded systems programming. "
                    "If the user asks for Arduino code, structure it with `void setup() {}` and `void loop() {}`. "
                    "If for Raspberry Pi, provide Python code, using `RPi.GPIO` for GPIO tasks if appropriate, or other common libraries like `smbus` for I2C. "
                    "For other microcontrollers like ESP32 or STM32, provide C/C++ code in a typical embedded style (e.g., using Arduino framework for ESP32 if common, or HAL/LL for STM32 if specified). "
                    "Provide clear, well-commented code snippets. "
                    "If including explanations, clearly separate the code block using markdown (e.g., ```c or ```python or ```cpp). "
                    "Focus on the specific request and aim for functional, copy-pasteable code where possible. "
                    "For general mechatronics algorithms (e.g., PID, kinematics), pseudocode or Python is often suitable unless a specific language is requested."
                )
            else: # General conversation
                 system_prompt_parts.append(" For general conversation, provide helpful and concise answers.")

        final_system_prompt = "".join(system_prompt_parts)
        logger.debug(f"WORKER_PROCESS: Final System Prompt for this call:\n{final_system_prompt}")
        # --- End System Prompt Construction ---

        api_contents = []
        # The conversation history should be "pure" interactions without the dynamic system prompt.
        history_to_include = self.conversation_history[-12:] # Limit context window
        api_contents.extend(history_to_include)

        # The dynamic system prompt is prepended to the current user message for this turn.
        # This ensures the model sees the latest context along with the user's query.
        effective_user_message_for_api = f"{final_system_prompt}\n\nHuman: {user_message}"
        api_contents.append({"role": "user", "parts": [{"text": effective_user_message_for_api}]})
        
        logger.debug(f"WORKER_PROCESS: Contents being sent to Gemini API (last item contains current query with system prompt):\n{json.dumps(api_contents, indent=2)}")

        generation_config = genai.types.GenerationConfig(temperature=0.7)
        if is_fsm_generation_attempt:
            generation_config.response_mime_type = "application/json"
            logger.info("WORKER_PROCESS: Requesting JSON object format from Gemini.")

        try:
            if self._is_stopped: return # Check before API call
            response = self.client.generate_content(contents=api_contents, generation_config=generation_config)
            if self._is_stopped: return # Check after API call returns

            ai_response_content = ""
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                ai_response_content = response.candidates[0].content.parts[0].text
            elif hasattr(response, 'text') and response.text: # Fallback for simpler response structures
                ai_response_content = response.text
            else:
                # More detailed error for blocked/empty responses
                feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "No feedback."
                finish_reason_obj = response.candidates[0].finish_reason if response.candidates and response.candidates[0].finish_reason else None
                finish_reason_str = genai.types.FinishReason(finish_reason_obj).name if finish_reason_obj else "Unknown reason" 
                
                error_msg = f"Gemini response was empty or blocked. Finish Reason: {finish_reason_str}. Feedback: {feedback}"
                logger.error(error_msg)
                logger.error(f"Full Gemini response object on block/empty: {response}") # Log the whole object for debugging
                self.errorOccurred.emit(error_msg)
                self._current_processing_had_error = True
                return

            # Add to history: original user message (without system prompt) and AI response
            self.conversation_history.append({"role": "user", "parts": [{"text": user_message}]})
            self.conversation_history.append({"role": "model", "parts": [{"text": ai_response_content}]})
            
            logger.debug("WORKER_PROCESS: AI response received and added to history.")
            self.responseReady.emit(ai_response_content, is_fsm_generation_attempt)

        except google.api_core.exceptions.ServiceUnavailable as e:
            logger.error("Gemini API Connection/Service Error: %s", str(e)[:200], exc_info=True)
            self.errorOccurred.emit(f"API Connection Error: {str(e)[:200]}"); self._current_processing_had_error = True
        except google.api_core.exceptions.ResourceExhausted as e:
            logger.error("Gemini Rate Limit Exceeded: %s", str(e)[:200], exc_info=True)
            self.errorOccurred.emit(f"Rate Limit Exceeded: {str(e)[:200]}"); self._current_processing_had_error = True
        except (google.api_core.exceptions.PermissionDenied, google.api_core.exceptions.Unauthenticated, google.auth.exceptions.RefreshError, google.auth.exceptions.DefaultCredentialsError) as e:
            logger.error("Gemini Authentication/Permission Error: %s", str(e)[:200], exc_info=True)
            self.errorOccurred.emit(f"Authentication Error (Invalid API Key?): {str(e)[:200]}"); self.statusUpdate.emit("Status: API Key Error."); self._current_processing_had_error = True
        except google.api_core.exceptions.InvalidArgument as e:
            logger.error("Gemini Invalid Argument/Bad Request: %s", str(e)[:500], exc_info=True)
            self.errorOccurred.emit(f"Invalid request to Gemini (check logs): {str(e)[:200]}"); self._current_processing_had_error = True
        except google.api_core.exceptions.GoogleAPIError as e: 
            error_detail = str(e);
            if hasattr(e, 'message') and e.message: error_detail = e.message
            logger.error("Gemini API Error: %s - %s", type(e).__name__, error_detail[:250], exc_info=True)
            self.errorOccurred.emit(f"Google API Error: {type(e).__name__} - {error_detail[:250]}"); self._current_processing_had_error = True
        except (genai.types.BlockedPromptException, genai.types.StopCandidateException) as e: 
            error_msg = f"Gemini content generation blocked or stopped due to safety settings or other reasons: {e}"
            logger.error("WORKER_PROCESS: %s", error_msg, exc_info=True)
            self.errorOccurred.emit(error_msg); self._current_processing_had_error = True
        except Exception as e:
            error_msg = f"Unexpected error in AI worker: {type(e).__name__} - {str(e)[:150]}"
            logger.error("WORKER_PROCESS: %s", error_msg, exc_info=True)
            self.errorOccurred.emit(error_msg); self._current_processing_had_error = True
        finally:
            if not self._current_processing_had_error and self.client and not self._is_stopped:
                self.statusUpdate.emit("Status: Ready.")

    @pyqtSlot()
    def clear_history_slot(self):
        self.conversation_history = []
        logger.info("Conversation history cleared.")
        self.statusUpdate.emit("Status: Chat history cleared.")

    @pyqtSlot()
    def stop_processing_slot(self):
        logger.info("WORKER: stop_processing_slot called.")
        self._is_stopped = True

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
                QMetaObject.invokeMethod(self.chatbot_worker, "stop_processing_slot", Qt.QueuedConnection)
                logger.debug("MGR_CLEANUP: stop_processing_slot invoked on worker.")

            self.chatbot_thread.quit()
            if not self.chatbot_thread.wait(300): 
                logger.warning("MGR_CLEANUP: Thread did not quit gracefully. Terminating.")
                self.chatbot_thread.terminate() 
                self.chatbot_thread.wait(200) 
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
        logger.info(f"MGR_SET_API_KEY (Gemini): New key: '{new_key_status}', Old key: '{old_key_status}'")

        old_api_key_val = self.api_key
        self.api_key = api_key

        if old_api_key_val != self.api_key or \
           (self.api_key and (not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning())):
            self._cleanup_existing_worker_and_thread()
            if self.api_key:
                self._setup_worker()
            else:
                self.statusUpdate.emit("Status: Gemini API Key cleared. AI Assistant inactive.")
        elif self.chatbot_worker and self.api_key and self.chatbot_thread and self.chatbot_thread.isRunning():
             QMetaObject.invokeMethod(self.chatbot_worker, "set_api_key_slot", Qt.QueuedConnection,
                                      Q_ARG(str, self.api_key))
             self.statusUpdate.emit("Status: Ready. Gemini API Key re-confirmed.")
        elif not self.api_key: 
            self.statusUpdate.emit("Status: Gemini API Key required.")

    def _setup_worker(self):
        if not self.api_key:
            logger.warning("MGR_SETUP_WORKER: Cannot setup - API key is not set.")
            self.statusUpdate.emit("Status: API Key required.")
            return

        if self.chatbot_worker or (self.chatbot_thread and self.chatbot_thread.isRunning()):
            logger.info("MGR_SETUP_WORKER: Worker/thread unexpectedly exists or is running. Cleaning up first.")
            self._cleanup_existing_worker_and_thread()

        logger.info("MGR_SETUP_WORKER: Setting up new worker and thread.")
        self.chatbot_thread = QThread(self) 
        self.chatbot_worker = ChatbotWorker(self.api_key) 
        self.chatbot_worker.moveToThread(self.chatbot_thread)

        self.chatbot_worker.responseReady.connect(self._handle_worker_response)
        self.chatbot_worker.errorOccurred.connect(self.errorOccurred) 
        self.chatbot_worker.statusUpdate.connect(self.statusUpdate) 

        self.chatbot_thread.start()
        logger.info("MGR_SETUP_WORKER: New AI Chatbot worker thread started.")
        self.statusUpdate.emit("Status: AI Assistant Ready.") 

    def _validate_fsm_schema(self, data: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(data, dict):
            errors.append("AI Response: Root must be a JSON object.")
            return False, errors
        
        if 'description' not in data or not isinstance(data['description'], str):
            errors.append("AI Response: Missing or invalid top-level 'description' (string).")

        state_names = set() 
        if 'states' not in data or not isinstance(data['states'], list):
            errors.append("AI Response: Missing or invalid 'states' list at the top level.")
        else:
            if not data['states']: 
                errors.append("AI Response: 'states' list is empty. An FSM should generally have states.")
            
            for i, s_obj in enumerate(data['states']):
                if not isinstance(s_obj, dict):
                    errors.append(f"AI Response: State at index {i} is not an object.")
                    continue
                s_name = s_obj.get('name')
                if not s_name or not isinstance(s_name, str) or not s_name.strip():
                    errors.append(f"AI Response: State at index {i} is missing a valid 'name' (string).")
                elif s_name in state_names:
                    errors.append(f"AI Response: Duplicate state name '{s_name}' found at index {i}.")
                else:
                    state_names.add(s_name) 
                
                if 'is_initial' in s_obj and not isinstance(s_obj['is_initial'], bool):
                    errors.append(f"AI Response: State '{s_name}' has invalid 'is_initial' (must be boolean).")
                if 'is_final' in s_obj and not isinstance(s_obj['is_final'], bool):
                    errors.append(f"AI Response: State '{s_name}' has invalid 'is_final' (must be boolean).")
                if 'entry_action' in s_obj and not isinstance(s_obj['entry_action'], str):
                     errors.append(f"AI Response: State '{s_name}' has invalid 'entry_action' (must be string).")
                if 'during_action' in s_obj and not isinstance(s_obj['during_action'], str):
                     errors.append(f"AI Response: State '{s_name}' has invalid 'during_action' (must be string).")
                if 'exit_action' in s_obj and not isinstance(s_obj['exit_action'], str):
                     errors.append(f"AI Response: State '{s_name}' has invalid 'exit_action' (must be string).")
                if 'action_language' in s_obj and not isinstance(s_obj['action_language'], str): 
                     errors.append(f"AI Response: State '{s_name}' has invalid 'action_language' (must be string).")
                if 'properties' in s_obj and not isinstance(s_obj['properties'], dict):
                    errors.append(f"AI Response: State '{s_name}' has invalid 'properties' (must be object).")
                elif 'properties' in s_obj and 'color' in s_obj['properties'] and not isinstance(s_obj['properties']['color'], str):
                    errors.append(f"AI Response: State '{s_name}' properties has invalid 'color' (must be string).")
                
                if s_obj.get('is_superstate') and ('sub_fsm_data' not in s_obj or not isinstance(s_obj['sub_fsm_data'], dict)):
                    errors.append(f"AI Response: Superstate '{s_name}' is missing 'sub_fsm_data' object or it's invalid.")
                elif 'sub_fsm_data' in s_obj: 
                    sub_data = s_obj['sub_fsm_data']
                    if not isinstance(sub_data, dict) or \
                       'states' not in sub_data or not isinstance(sub_data['states'], list) or \
                       'transitions' not in sub_data or not isinstance(sub_data['transitions'], list):
                        errors.append(f"AI Response: Superstate '{s_name}' has malformed 'sub_fsm_data' (missing states/transitions lists).")

        if 'transitions' not in data or not isinstance(data['transitions'], list):
            errors.append("AI Response: Missing or invalid 'transitions' list at the top level.")
        else:
            for i, t_obj in enumerate(data['transitions']):
                if not isinstance(t_obj, dict):
                    errors.append(f"AI Response: Transition at index {i} is not an object.")
                    continue
                src = t_obj.get('source')
                tgt = t_obj.get('target')
                if not src or not isinstance(src, str) or not src.strip():
                    errors.append(f"AI Response: Transition at index {i} has missing or invalid 'source' (string).")
                elif src not in state_names: 
                     errors.append(f"AI Response: Transition at index {i} references non-existent source state '{src}'.")
                
                if not tgt or not isinstance(tgt, str) or not tgt.strip():
                    errors.append(f"AI Response: Transition at index {i} has missing or invalid 'target' (string).")
                elif tgt not in state_names: 
                     errors.append(f"AI Response: Transition at index {i} references non-existent target state '{tgt}'.")

                if 'event' in t_obj and not isinstance(t_obj['event'], str):
                     errors.append(f"AI Response: Transition at index {i} ('{src}'->'{tgt}') has invalid 'event' (must be string).")
                if 'condition' in t_obj and not isinstance(t_obj['condition'], str):
                     errors.append(f"AI Response: Transition at index {i} ('{src}'->'{tgt}') has invalid 'condition' (must be string).")
                if 'action' in t_obj and not isinstance(t_obj['action'], str):
                     errors.append(f"AI Response: Transition at index {i} ('{src}'->'{tgt}') has invalid 'action' (must be string).")
                if 'action_language' in t_obj and not isinstance(t_obj['action_language'], str): 
                     errors.append(f"AI Response: Transition at index {i} ('{src}'->'{tgt}') has invalid 'action_language' (must be string).")
                if 'control_offset_x' in t_obj and not isinstance(t_obj['control_offset_x'], (int, float)):
                    errors.append(f"AI Response: Transition at index {i} ('{src}'->'{tgt}') has invalid 'control_offset_x' (must be number).")
                if 'control_offset_y' in t_obj and not isinstance(t_obj['control_offset_y'], (int, float)):
                    errors.append(f"AI Response: Transition at index {i} ('{src}'->'{tgt}') has invalid 'control_offset_y' (must be number).")

        if 'comments' in data and not isinstance(data['comments'], list):
            errors.append("AI Response: Optional 'comments' key, if present, must be a list of objects.")
        elif 'comments' in data:
            for i, c_obj in enumerate(data['comments']):
                if not isinstance(c_obj, dict):
                     errors.append(f"AI Response: Comment at index {i} is not an object.")
                     continue
                if 'text' not in c_obj or not isinstance(c_obj['text'], str):
                    errors.append(f"AI Response: Comment at index {i} is missing or has invalid 'text' (string).")
                if 'x' in c_obj and not isinstance(c_obj['x'], (int, float)):
                    errors.append(f"AI Response: Comment at index {i} has invalid 'x' (must be number).")
                if 'y' in c_obj and not isinstance(c_obj['y'], (int, float)):
                    errors.append(f"AI Response: Comment at index {i} has invalid 'y' (must be number).")
                if 'width' in c_obj and not isinstance(c_obj['width'], (int, float)):
                    errors.append(f"AI Response: Comment at index {i} has invalid 'width' (must be number).")

        return not errors, errors


    @pyqtSlot(str, bool)
    def _handle_worker_response(self, ai_response_content: str, was_fsm_generation_attempt: bool):
        logger.info(f"MGR_HANDLE_WORKER_RESPONSE: Received from worker. Was FSM attempt: {was_fsm_generation_attempt}")
        logger.debug(f"MGR_HANDLE_WORKER_RESPONSE: Raw AI response content (first 200 chars): '{ai_response_content[:200]}...'")

        if was_fsm_generation_attempt:
            logger.info(f"MGR_HANDLE_WORKER_RESPONSE: Raw AI response for FSM attempt (full):\n---\n{ai_response_content}\n---")
            try:
                match = re.search(r"```json\s*([\s\S]*?)\s*```", ai_response_content, re.DOTALL)
                json_to_parse = ai_response_content
                if match:
                    logger.info("MGR_HANDLE_WORKER_RESPONSE: Extracted JSON from markdown block.")
                    json_to_parse = match.group(1).strip()
                else:
                    first_brace = json_to_parse.find('{')
                    last_brace = json_to_parse.rfind('}')
                    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                        potential_json = json_to_parse[first_brace : last_brace+1]
                        try:
                            fsm_data_test = json.loads(potential_json)
                            json_to_parse = potential_json
                            logger.info("MGR_HANDLE_WORKER_RESPONSE: Extracted JSON object from potentially noisy response.")
                        except json.JSONDecodeError:
                            logger.debug("MGR_HANDLE_WORKER_RESPONSE: Substring JSON extraction failed, trying full response.")
                            pass 

                fsm_data = json.loads(json_to_parse)
                is_valid_schema, schema_errors = self._validate_fsm_schema(fsm_data)

                if is_valid_schema:
                    logger.info("MGR_HANDLE_WORKER_RESPONSE: Parsed and schema-validated FSM JSON successfully. Emitting fsmDataReceived.")
                    source_desc = self.last_fsm_request_description or "AI Generated FSM"
                    self.fsmDataReceived.emit(fsm_data, source_desc)
                    return 
                else:
                    error_summary = "; ".join(schema_errors) if schema_errors else "JSON structure is not a valid FSM."
                    full_error_message = f"AI returned JSON, but it's not a valid FSM: {error_summary}. Displaying as text. Problematic JSON received: {json_to_parse[:200]}..."
                    logger.warning(f"MGR_HANDLE_WORKER_RESPONSE: AI FSM Schema validation failed: {error_summary}. Data (first 200 chars): {json_to_parse[:200]}...")
                    self.errorOccurred.emit(full_error_message)
            
            except json.JSONDecodeError as e:
                logger.warning(f"MGR_HANDLE_WORKER_RESPONSE: Failed to parse AI response as JSON: {e}. Treating as plain text.", exc_info=False)
                self.statusUpdate.emit("Status: AI response was not valid FSM JSON.")
                logger.debug(f"MGR_HANDLE_WORKER_RESPONSE: Problematic content for FSM JSON parsing (first 200 chars): {ai_response_content[:200]}...")

        logger.debug("MGR_HANDLE_WORKER_RESPONSE: Emitting plainResponseReady.")
        self.plainResponseReady.emit(ai_response_content)


    def _prepare_and_send_to_worker(self, user_message_text: str, is_fsm_gen_specific: bool = False):
        logger.info(f"MGR_PREP_SEND: For: '{user_message_text[:30]}...', FSM_specific_req: {is_fsm_gen_specific}")

        if not self.api_key:
            logger.warning("MGR_PREP_SEND: API Key not set.")
            self.errorOccurred.emit("Gemini API Key not set. Configure in Settings.")
            if self.parent_window and hasattr(self.parent_window, 'ai_chat_ui_manager') and self.parent_window.ai_chat_ui_manager:
                self.parent_window.ai_chat_ui_manager._append_to_chat_display("System Error", "API Key not set.")
            return

        if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
            logger.warning("MGR_PREP_SEND: Worker/Thread not ready.")
            if self.api_key and (not self.chatbot_thread or not self.chatbot_thread.isRunning()):
                 logger.info("MGR_PREP_SEND: Attempting to re-setup worker because key is present but thread not running.")
                 self._setup_worker() 

            if not self.chatbot_worker or not self.chatbot_thread or not self.chatbot_thread.isRunning():
                self.errorOccurred.emit("AI Assistant is not ready. Please wait or check settings.")
                if self.parent_window and hasattr(self.parent_window, 'ai_chat_ui_manager') and self.parent_window.ai_chat_ui_manager:
                    self.parent_window.ai_chat_ui_manager._append_to_chat_display("System Error", "AI Assistant is not ready.")
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
             logger.warning("MGR_PREP_SEND: Diagram context (parent_window.scene.get_diagram_data) unavailable.")
             diagram_json_str = json.dumps({"error": "Diagram context source unavailable to manager."})


        if self.chatbot_worker: 
            effective_diagram_json_str = diagram_json_str if diagram_json_str is not None else ""
            QMetaObject.invokeMethod(self.chatbot_worker, "set_diagram_context_slot", Qt.QueuedConnection,
                                     Q_ARG(str, effective_diagram_json_str))
            QMetaObject.invokeMethod(self.chatbot_worker, "process_message_slot", Qt.QueuedConnection,
                                     Q_ARG(str, user_message_text),
                                     Q_ARG(bool, is_fsm_gen_specific))
            logger.debug("MGR_PREP_SEND: Methods to set context and process message queued for worker.")
            if self.parent_window and hasattr(self.parent_window, 'ai_chat_ui_manager') and self.parent_window.ai_chat_ui_manager:
                self.parent_window.ai_chat_ui_manager.update_status_display("Status: Sending to AI...")
        else: 
            logger.error("MGR_PREP_SEND: Chatbot worker is None (was not set up correctly), cannot queue methods.")
            self.errorOccurred.emit("AI Assistant encountered an internal error (worker missing). Please try restarting AI features.")


    def send_message(self, user_message_text: str):
        self._prepare_and_send_to_worker(user_message_text, is_fsm_gen_specific=False)

    def generate_fsm_from_description(self, description: str):
         self._prepare_and_send_to_worker(description, is_fsm_gen_specific=True)

    def clear_conversation_history(self):
        logger.info("MGR: clear_conversation_history CALLED.")
        if self.chatbot_worker and self.chatbot_thread and self.chatbot_thread.isRunning():
            QMetaObject.invokeMethod(self.chatbot_worker, "clear_history_slot", Qt.QueuedConnection)
            logger.debug("MGR: clear_history_slot invoked on worker.")
        else:
            self.statusUpdate.emit("Status: Chatbot not active (history is in worker).")
            logger.warning("MGR: Chatbot not active, cannot clear history from worker. History might be stale or non-existent.")


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
                self.statusUpdate.emit("Status: Offline. Gemini AI features unavailable.")
        else: 
            if is_online:
                self.statusUpdate.emit("Status: Online, Gemini API Key required.")
            else: 
                self.statusUpdate.emit("Status: Offline, Gemini API Key required.")