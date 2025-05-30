# bsm_designer_project/ui_ai_chatbot_manager.py
import html
import re
from PyQt5.QtWidgets import (
    QTextEdit, QLineEdit, QPushButton, QLabel, QInputDialog, QMessageBox, QAction,
    QWidget, QVBoxLayout, QHBoxLayout, QStyle
)
from PyQt5.QtCore import QObject, pyqtSlot, QTime
from PyQt5.QtGui import QIcon, QColor

from utils import get_standard_icon
from config import (
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_SECONDARY, COLOR_TEXT_PRIMARY,
    COLOR_PY_SIM_STATE_ACTIVE
)

import logging
logger = logging.getLogger(__name__)

class AIChatUIManager(QObject):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window

        self.ai_chat_display: QTextEdit | None = None
        self.ai_chat_input: QLineEdit | None = None
        self.ai_chat_send_button: QPushButton | None = None
        self.ai_chat_status_label: QLabel | None = None

        self._connect_actions_to_manager_slots()
        self._connect_ai_chatbot_signals()

    def _connect_actions_to_manager_slots(self):
        logger.debug("AIChatUI: Connecting actions to manager slots...")
        if hasattr(self.mw, 'ask_ai_to_generate_fsm_action'):
            self.mw.ask_ai_to_generate_fsm_action.triggered.connect(self.on_ask_ai_to_generate_fsm)
            logger.debug("AIChatUI: ask_ai_to_generate_fsm_action connected.")
        else:
            logger.warning("AIChatUI: MainWindow missing ask_ai_to_generate_fsm_action.")

        if hasattr(self.mw, 'openai_settings_action'): # Still using this action name internally, text changed in main.py
            self.mw.openai_settings_action.triggered.connect(self.on_openai_settings)
            logger.debug("AIChatUI: openai_settings_action connected.")
        else:
            logger.warning("AIChatUI: MainWindow missing openai_settings_action.")

        if hasattr(self.mw, 'clear_ai_chat_action'):
            self.mw.clear_ai_chat_action.triggered.connect(self.on_clear_ai_chat_history)
            logger.debug("AIChatUI: clear_ai_chat_action connected.")
        else:
            logger.warning("AIChatUI: MainWindow missing clear_ai_chat_action.")

    def _connect_ai_chatbot_signals(self):
        if self.mw.ai_chatbot_manager:
            self.mw.ai_chatbot_manager.statusUpdate.connect(self.update_status_display)
            self.mw.ai_chatbot_manager.errorOccurred.connect(self.handle_ai_error)
            self.mw.ai_chatbot_manager.fsmDataReceived.connect(self.handle_fsm_data_from_ai)
            self.mw.ai_chatbot_manager.plainResponseReady.connect(self.handle_plain_ai_response)
        else:
            logger.error("AIChatUI: AI Chatbot Manager not available in MainWindow for signal connection.")


    def create_dock_widget_contents(self) -> QWidget:
        ai_chat_widget = QWidget()
        ai_chat_layout = QVBoxLayout(ai_chat_widget)
        ai_chat_layout.setContentsMargins(5,5,5,5); ai_chat_layout.setSpacing(5)

        self.ai_chat_display = QTextEdit(); self.ai_chat_display.setReadOnly(True)
        self.ai_chat_display.setObjectName("AIChatDisplay"); self.ai_chat_display.setStyleSheet("font-size: 9pt; padding: 5px;")
        self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
        ai_chat_layout.addWidget(self.ai_chat_display, 1) # Display takes most space

        input_layout = QHBoxLayout()
        self.ai_chat_input = QLineEdit(); self.ai_chat_input.setObjectName("AIChatInput")
        self.ai_chat_input.setPlaceholderText("Type your message to the AI...")
        self.ai_chat_input.returnPressed.connect(self.on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_input, 1)

        self.ai_chat_send_button = QPushButton(get_standard_icon(QStyle.SP_ArrowForward, "Snd"), "Send")
        self.ai_chat_send_button.setObjectName("AIChatSendButton") # For QSS
        self.ai_chat_send_button.clicked.connect(self.on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_send_button)
        ai_chat_layout.addLayout(input_layout)

        self.ai_chat_status_label = QLabel("Status: Initializing...")
        self.ai_chat_status_label.setObjectName("AIChatStatusLabel"); self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;")
        ai_chat_layout.addWidget(self.ai_chat_status_label)

        # Initial status often depends on API key presence and internet
        # This will be updated by signals from the manager or internet check.
        # For now, a generic initial message.
        self.update_status_display("Status: Initializing AI...")
        return ai_chat_widget

    @pyqtSlot(str)
    def update_status_display(self, status_text: str):
        if not self.ai_chat_status_label: return
        self.ai_chat_status_label.setText(status_text)
        
        # Determine style based on status text
        is_thinking = any(s in status_text.lower() for s in ["thinking...", "sending...", "generating...", "processing..."])
        is_key_req = any(s in status_text.lower() for s in ["api key required", "inactive", "api key error", "api key cleared"])
        is_offline = "offline" in status_text.lower()
        is_error = "error" in status_text.lower() or "failed" in status_text.lower() or is_key_req or is_offline
        is_ready = "ready" in status_text.lower() and not is_error and not is_thinking

        # Use QColor objects for consistency if colors are QColor in config
        accent_secondary_color_str = COLOR_ACCENT_SECONDARY.name() if isinstance(COLOR_ACCENT_SECONDARY, QColor) else COLOR_ACCENT_SECONDARY
        color_py_sim_active_str = COLOR_PY_SIM_STATE_ACTIVE.name() if isinstance(COLOR_PY_SIM_STATE_ACTIVE, QColor) else COLOR_PY_SIM_STATE_ACTIVE

        if is_error: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: red; font-weight: bold;")
        elif is_thinking: self.ai_chat_status_label.setStyleSheet(f"font-size: 8pt; color: {accent_secondary_color_str}; font-style: italic;")
        elif is_ready: self.ai_chat_status_label.setStyleSheet(f"font-size: 8pt; color: {color_py_sim_active_str};")
        else: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;") # Default/Initializing

        # Enable/disable input and send button based on status
        can_send_message = not is_thinking and not is_key_req and not is_offline

        if self.ai_chat_send_button: self.ai_chat_send_button.setEnabled(can_send_message)
        if self.ai_chat_input:
            self.ai_chat_input.setEnabled(can_send_message)
            # Auto-focus input if dock is visible and app is active, and can send
            if can_send_message and hasattr(self.mw, 'ai_chatbot_dock') and self.mw.ai_chatbot_dock and self.mw.ai_chatbot_dock.isVisible() and self.mw.isActiveWindow():
                self.ai_chat_input.setFocus()

        # Enable/disable "Generate FSM from Description" action
        if hasattr(self.mw, 'ask_ai_to_generate_fsm_action'):
            self.mw.ask_ai_to_generate_fsm_action.setEnabled(can_send_message)

    def _append_to_chat_display(self, sender: str, message: str):
        if not self.ai_chat_display: return
        timestamp = QTime.currentTime().toString('hh:mm:ss')

        # Determine sender color
        sender_color_obj = COLOR_ACCENT_PRIMARY # Default for AI
        if sender == "You": sender_color_obj = COLOR_ACCENT_SECONDARY
        elif sender == "System Error" or sender == "System": sender_color_obj = QColor("#D32F2F") # Red for errors

        sender_color_str = sender_color_obj.name() if isinstance(sender_color_obj, QColor) else sender_color_obj

        # Process message for markdown-like formatting (bold, italic, code blocks)
        processed_message_parts = []
        # Regex to split message by ```code``` blocks, keeping delimiters
        parts = re.split(r'(```.*?```)', message, flags=re.DOTALL | re.MULTILINE)

        for i, part in enumerate(parts):
            if part.startswith("```") and part.endswith("```"):
                # Extract code content, remove potential language specifier from first line
                code_content_full = part[3:-3]
                first_line_end = code_content_full.find('\n')
                if first_line_end != -1:
                    first_line = code_content_full[:first_line_end].strip()
                    # Simple check if first line is just a language specifier (e.g., "python", "c")
                    if re.match(r'^[a-zA-Z_+#\-/.]+$', first_line) and len(first_line) < 15: # Heuristic
                        code_content = code_content_full[first_line_end+1:]
                    else:
                        code_content = code_content_full
                else: # Single line code block
                    code_content = code_content_full
                
                escaped_code = html.escape(code_content.strip())
                processed_message_parts.append(f'<pre><code style="background-color:#f0f0f0; padding:3px 5px; border-radius:3px; display:block; white-space:pre-wrap; border: 1px solid #ddd;">{escaped_code}</code></pre>')
            else: # Not a code block part
                escaped_part = html.escape(part)
                # Bold: **text**
                escaped_part = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped_part)
                # Italic: *text* (ensure not part of **text**)
                escaped_part = re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'<i>\1</i>', escaped_part)
                # Inline code: `text`
                escaped_part = re.sub(r'`(.*?)`', r'<code style="background-color:#f0f0f0; padding:1px 3px; border-radius:2px;">\1</code>', escaped_part)
                # Convert newlines to <br> for HTML
                escaped_part = escaped_part.replace("\n", "<br>")
                processed_message_parts.append(escaped_part)

        final_message_html = "".join(processed_message_parts)

        # Construct the full HTML for the chat entry
        formatted_html = (f"<div style='margin-bottom: 8px;'>"
                          f"<span style='font-size:8pt; color:grey;'>[{timestamp}]</span> "
                          f"<strong style='color:{sender_color_str};'>{html.escape(sender)}:</strong>"
                          f"<div style='margin-top: 3px; padding-left: 5px; border-left: 2px solid {sender_color_str if sender_color_str != '#D32F2F' else '#FFCDD2'};'>{final_message_html}</div></div>")
        self.ai_chat_display.append(formatted_html)
        self.ai_chat_display.ensureCursorVisible() # Scroll to bottom

    @pyqtSlot(str)
    def handle_ai_error(self, error_message: str):
        self._append_to_chat_display("System Error", error_message)
        logger.error("AIChatUI: AI Chatbot Error: %s", error_message)
        # Update status to reflect error, showing first line for brevity
        self.update_status_display(f"Error: {error_message.splitlines()[0][:50]}...")

    @pyqtSlot(dict, str)
    def handle_fsm_data_from_ai(self, fsm_data: dict, source_message: str):
        logger.info("AIChatUI: Received FSM data. Source: '%s...'", source_message[:30])
        self._append_to_chat_display("AI", f"Received FSM structure. (Source: {source_message[:30]}...) Adding to diagram.")
        
        if not fsm_data or (not fsm_data.get('states') and not fsm_data.get('transitions')): # Check if FSM data is empty
            logger.error("AIChatUI: AI returned empty or invalid FSM data."); self.update_status_display("Status: AI returned no FSM data.")
            self._append_to_chat_display("System", "AI did not return a valid FSM structure to draw."); return

        # Ask user whether to clear current diagram or add to it
        msg_box = QMessageBox(self.mw); msg_box.setIcon(QMessageBox.Question); msg_box.setWindowTitle("Add AI Generated FSM")
        msg_box.setText("AI has generated an FSM. Do you want to clear the current diagram before adding the new FSM, or add to the existing one?")
        clear_btn = msg_box.addButton("Clear and Add", QMessageBox.AcceptRole)
        add_btn = msg_box.addButton("Add to Existing", QMessageBox.AcceptRole)
        cancel_btn = msg_box.addButton("Cancel", QMessageBox.RejectRole); msg_box.setDefaultButton(cancel_btn) # Default to cancel
        msg_box.exec()
        
        clicked = msg_box.clickedButton()
        if clicked == cancel_btn: 
            logger.info("AIChatUI: User cancelled adding AI FSM."); self.update_status_display("Status: FSM generation cancelled."); return

        # Delegate to MainWindow's method to add FSM data to the scene
        self.mw._add_fsm_data_to_scene(fsm_data, clear_current_diagram=(clicked == clear_btn), original_user_prompt=source_message)
        self.update_status_display("Status: FSM added to diagram.")
        logger.info("AIChatUI: FSM data from AI processed and added to scene.")

    @pyqtSlot(str)
    def handle_plain_ai_response(self, ai_message: str):
        logger.info("AIChatUI: Received plain AI response.")
        self._append_to_chat_display("AI", ai_message)
        # Status update is handled by the worker's finally block after successful response

    @pyqtSlot()
    def on_send_ai_chat_message(self):
        if not self.ai_chat_input: return
        message = self.ai_chat_input.text().strip()
        if not message: return # Don't send empty messages
        
        self.ai_chat_input.clear(); self._append_to_chat_display("You", message)
        if self.mw.ai_chatbot_manager:
            self.mw.ai_chatbot_manager.send_message(message)
            self.update_status_display("Status: Sending message...") # Update status immediately
        else:
            self.handle_ai_error("AI Chatbot Manager not initialized.") # Should not happen if UI enabled

    @pyqtSlot()
    def on_ask_ai_to_generate_fsm(self):
        logger.info("AIChatUI: on_ask_ai_to_generate_fsm CALLED!")
        # Get FSM description from user
        description, ok = QInputDialog.getMultiLineText(self.mw, "Generate FSM", "Describe the FSM you want to create:", "Example: A traffic light with states Red, Yellow, Green that cycle on a timer event.")
        if ok and description.strip():
            logger.info("AIChatUI: Sending FSM desc: '%s...'", description[:50])
            self.update_status_display("Status: Generating FSM from description...")
            if self.mw.ai_chatbot_manager:
                self.mw.ai_chatbot_manager.generate_fsm_from_description(description)
                self._append_to_chat_display("You", f"Generate an FSM: {description}")
            else:
                self.handle_ai_error("AI Chatbot Manager not initialized.")
        elif ok: # User clicked OK but description was empty
            QMessageBox.warning(self.mw, "Empty Description", "Please provide a description for the FSM.")

    @pyqtSlot()
    def on_openai_settings(self): # Name reflects old system, but logic is for Gemini
        logger.info("AIChatUI: on_openai_settings CALLED! (Now Google AI/Gemini Settings)")
        if not self.mw.ai_chatbot_manager:
            logger.warning("AIChatUI: AI Chatbot Manager (mw.ai_chatbot_manager) not available for settings.")
            QMessageBox.warning(self.mw, "AI Error", "AI Chatbot Manager is not initialized. Cannot open settings.")
            return

        current_key = self.mw.ai_chatbot_manager.api_key or ""
        # Prompt user for API key
        key, ok = QInputDialog.getText(
            self.mw,
            "Google AI API Key (Gemini)", 
            "Enter your Google AI API Key for Gemini (leave blank to clear):", 
            QLineEdit.PasswordEchoOnEdit, # Hide key entry
            current_key
        )
        if ok: # User clicked OK
            new_key_value = key.strip()
            logger.info(f"AIChatUI: Google AI API Key dialog returned. OK: {ok}, Key: {'SET' if new_key_value else 'EMPTY'}")
            self.mw.ai_chatbot_manager.set_api_key(new_key_value if new_key_value else None) # Set key in manager
            if new_key_value:
                self.update_status_display("Status: API Key Set. Ready.")
                if hasattr(self.mw, 'log_message'): self.mw.log_message("INFO","Google AI API Key has been set/updated.")
            else: # Key was cleared
                self.update_status_display("Status: API Key Cleared. AI Inactive.")
                if hasattr(self.mw, 'log_message'): self.mw.log_message("INFO","Google AI API Key has been cleared.")
        else: # User cancelled
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
                if self.ai_chat_display: # Clear UI display
                    self.ai_chat_display.clear()
                    self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
                logger.info("AIChatUI: Chat history cleared by user.")
                self.update_status_display("Status: Chat history cleared.")
                self._append_to_chat_display("System", "Chat history cleared.")
            else:
                logger.info("AIChatUI: User cancelled clearing chat history.")
        else:
            self.handle_ai_error("AI Chatbot Manager not initialized.")