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
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_ACCENT_ERROR, COLOR_TEXT_EDITOR_DARK_SECONDARY,
    COLOR_BACKGROUND_EDITOR_DARK, COLOR_TEXT_EDITOR_DARK_PRIMARY
)

import logging
logger = logging.getLogger(__name__)

class AIChatUIManager(QObject):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window

        self.ai_chat_display: QTextEdit = None
        self.ai_chat_input: QLineEdit = None
        self.ai_chat_send_button: QPushButton = None
        self.ai_chat_status_label: QLabel = None

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

    def create_dock_widget_contents(self) -> QWidget:
        ai_chat_widget = QWidget()
        ai_chat_layout = QVBoxLayout(ai_chat_widget)
        ai_chat_layout.setContentsMargins(5,5,5,5); ai_chat_layout.setSpacing(5)

        self.ai_chat_display = QTextEdit(); self.ai_chat_display.setReadOnly(True)
        self.ai_chat_display.setObjectName("AIChatDisplay"); # QSS handles styling
        self.ai_chat_display.setPlaceholderText("AI chat history will appear here...")
        ai_chat_layout.addWidget(self.ai_chat_display, 1)

        input_layout = QHBoxLayout()
        self.ai_chat_input = QLineEdit(); self.ai_chat_input.setObjectName("AIChatInput")
        self.ai_chat_input.setPlaceholderText("Type your message to the AI...")
        self.ai_chat_input.returnPressed.connect(self.on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_input, 1)

        self.ai_chat_send_button = QPushButton(get_standard_icon(QStyle.SP_ArrowRight, "SndAI"), "") # Text removed, rely on QSS to style
        self.ai_chat_send_button.setObjectName("AIChatSendButton")
        self.ai_chat_send_button.setToolTip("Send message to AI")
        self.ai_chat_send_button.setFixedWidth(40) # Make it a square-ish button
        self.ai_chat_send_button.clicked.connect(self.on_send_ai_chat_message)
        input_layout.addWidget(self.ai_chat_send_button)
        ai_chat_layout.addLayout(input_layout)

        self.ai_chat_status_label = QLabel("Status: Initializing...")
        self.ai_chat_status_label.setObjectName("AIChatStatusLabel") # QSS handles specific style
        ai_chat_layout.addWidget(self.ai_chat_status_label)

        self.update_status_display("Status: API Key required. Configure in Settings.")
        return ai_chat_widget

    @pyqtSlot(str)
    def update_status_display(self, status_text: str):
        if not self.ai_chat_status_label: return
        self.ai_chat_status_label.setText(status_text)
        
        is_thinking = any(s in status_text.lower() for s in ["thinking...", "sending...", "generating...", "processing..."])
        is_key_req = any(s in status_text.lower() for s in ["api key required", "inactive", "api key error", "api key cleared"])
        is_error_state = "error" in status_text.lower() or "failed" in status_text.lower() or is_key_req
        is_ready = "ready" in status_text.lower() and not is_error_state and not is_thinking
        
        if is_error_state: 
            self.ai_chat_status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_ACCENT_ERROR}; font-weight: bold;")
        elif is_thinking: 
            self.ai_chat_status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_ACCENT_SECONDARY}; font-style: italic;")
        elif is_ready: 
            self.ai_chat_status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_ACCENT_SUCCESS};")
        else: # Default/Neutral
            self.ai_chat_status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_TEXT_SECONDARY};")

        can_send_message = not is_thinking and not is_key_req and not ("offline" in status_text.lower())

        if self.ai_chat_send_button: self.ai_chat_send_button.setEnabled(can_send_message)
        if self.ai_chat_input:
            self.ai_chat_input.setEnabled(can_send_message)
            if can_send_message and hasattr(self.mw, 'ai_chatbot_dock') and self.mw.ai_chatbot_dock and self.mw.ai_chatbot_dock.isVisible() and self.mw.isActiveWindow():
                self.ai_chat_input.setFocus()

        if hasattr(self.mw, 'ask_ai_to_generate_fsm_action'):
            self.mw.ask_ai_to_generate_fsm_action.setEnabled(can_send_message)


    def _format_code_block(self, code_content: str) -> str:
        # Using background and text colors defined in config.py for dark editors
        bg_color = COLOR_BACKGROUND_EDITOR_DARK
        text_color = COLOR_TEXT_EDITOR_DARK_PRIMARY
        border_color = QColor(bg_color).lighter(130).name()
        
        escaped_code = html.escape(code_content)
        # Preserve leading/trailing newlines for multi-line code blocks if they are significant
        if code_content.startswith("\n"): escaped_code = "<br>" + escaped_code
        if code_content.endswith("\n"): escaped_code += "<br>"
        
        # Try to determine language for syntax hint (very basic)
        lang_hint = ""
        if "def " in code_content or "import " in code_content or "class " in code_content: lang_hint = "python"
        elif "void setup()" in code_content or "void loop()" in code_content or "#include" in code_content: lang_hint = "cpp" # Could be Arduino
        
        return (f'<div style="margin: 5px 0; padding: 8px; background-color:{bg_color}; color:{text_color}; '
                f'border:1px solid {border_color}; border-radius:4px; font-family: Consolas, monospace; white-space:pre-wrap; overflow-x:auto;">'
                f'{escaped_code}</div>')


    def _append_to_chat_display(self, sender: str, message: str):
        if not self.ai_chat_display: return
        timestamp = QTime.currentTime().toString('hh:mm:ss')

        sender_color = COLOR_ACCENT_PRIMARY
        sender_name = html.escape(sender)
        if sender == "You": 
            sender_color = COLOR_ACCENT_SECONDARY
        elif sender == "System Error": 
            sender_color = COLOR_ACCENT_ERROR
            sender_name = f"<span style='font-weight:bold;'>{sender_name}</span>" # Bold system errors
        elif sender == "System":
             sender_color = QColor(COLOR_TEXT_SECONDARY)


        sender_color_str = sender_color.name() if isinstance(sender_color, QColor) else sender_color
        
        # Improved regex to capture language hint from markdown code blocks
        # e.g., ```python, ```cpp, ```c, ```, etc.
        parts = re.split(r'(```(?:[a-zA-Z0-9_+#-]+)?\s*?\n.*?\n```)', message, flags=re.DOTALL | re.MULTILINE)
        
        processed_message_html_parts = []
        for i, part in enumerate(parts):
            if part.startswith("```") and part.endswith("```"):
                # Strip initial ```[lang]\n and final \n```
                lang_match = re.match(r'```([a-zA-Z0-9_+#-]+)?\s*\n', part)
                code_content = part
                if lang_match:
                    code_content = part[len(lang_match.group(0)):-3] # Strip ```lang\n and ```
                else: # No language hint or malformed
                    code_content = part[3:-3] # Strip ``` and ```

                # Remove leading/trailing newlines from the content block itself if they exist just from formatting
                code_content = code_content.strip('\n') 
                processed_message_html_parts.append(self._format_code_block(code_content))
            else:
                escaped_part = html.escape(part).replace("\n", "<br>")
                # Simple markdown for bold and italic - make sure it doesn't break HTML
                escaped_part = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped_part)
                escaped_part = re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'<i>\1</i>', escaped_part) # Avoid ** turning into *<i></i>*
                escaped_part = re.sub(r'`(.*?)`', r'<code style="background-color:#E8EAF6; color:#3F51B5; padding:1px 4px; border-radius:3px; font-family:Consolas,monospace;">\1</code>', escaped_part)
                processed_message_html_parts.append(escaped_part)

        final_message_html = "".join(processed_message_html_parts)

        # Styling for the entire message block from one sender
        html_to_append = (f"<div style='margin-bottom: 10px; padding: 5px; border-left: 3px solid {sender_color_str}; background-color: {QColor(sender_color_str).lighter(185).name() if sender != 'System Error' else QColor(COLOR_ACCENT_ERROR).lighter(180).name()}; border-radius: 3px;'>"
                          f"<span style='font-size:8pt; color:{COLOR_TEXT_SECONDARY};'>[{timestamp}]</span> "
                          f"<strong style='color:{sender_color_str};'>{sender_name}:</strong>"
                          f"<div style='margin-top: 4px; padding-left: 2px; line-height:1.4;'>{final_message_html}</div></div>")
        
        self.ai_chat_display.append(html_to_append)
        self.ai_chat_display.ensureCursorVisible()

    @pyqtSlot(str)
    def handle_ai_error(self, error_message: str):
        self._append_to_chat_display("System Error", error_message)
        logger.error("AIChatUI: AI Chatbot Error: %s", error_message)
        self.update_status_display(f"Error: {error_message.splitlines()[0][:50]}...")

    @pyqtSlot(dict, str)
    def handle_fsm_data_from_ai(self, fsm_data: dict, source_message: str):
        logger.info("AIChatUI: Received FSM data. Source: '%s...'", source_message[:30])
        self._append_to_chat_display("AI", f"Received FSM structure. (Source: {source_message[:30]}...) Adding to diagram.")
        if not fsm_data or (not fsm_data.get('states') and not fsm_data.get('transitions')):
            logger.error("AIChatUI: AI returned empty or invalid FSM data."); self.update_status_display("Status: AI returned no FSM data.")
            self._append_to_chat_display("System", "AI did not return a valid FSM structure to draw."); return

        msg_box = QMessageBox(self.mw); msg_box.setIcon(QMessageBox.Question); msg_box.setWindowTitle("Add AI Generated FSM")
        msg_box.setText("AI has generated an FSM. Do you want to clear the current diagram before adding the new FSM, or add to the existing one?")
        clear_btn = msg_box.addButton("Clear and Add", QMessageBox.AcceptRole)
        add_btn = msg_box.addButton("Add to Existing", QMessageBox.AcceptRole)
        cancel_btn = msg_box.addButton("Cancel", QMessageBox.RejectRole); msg_box.setDefaultButton(cancel_btn)
        msg_box.exec()
        clicked = msg_box.clickedButton()
        if clicked == cancel_btn: logger.info("AIChatUI: User cancelled adding AI FSM."); self.update_status_display("Status: FSM generation cancelled."); return

        self.mw._add_fsm_data_to_scene(fsm_data, clear_current_diagram=(clicked == clear_btn), original_user_prompt=source_message)
        self.update_status_display("Status: FSM added to diagram.")
        logger.info("AIChatUI: FSM data from AI processed and added to scene.")

    @pyqtSlot(str)
    def handle_plain_ai_response(self, ai_message: str):
        logger.info("AIChatUI: Received plain AI response.")
        self._append_to_chat_display("AI", ai_message)

    @pyqtSlot()
    def on_send_ai_chat_message(self):
        if not self.ai_chat_input: return
        message = self.ai_chat_input.text().strip()
        if not message: return
        self.ai_chat_input.clear(); self._append_to_chat_display("You", message)
        if self.mw.ai_chatbot_manager:
            self.mw.ai_chatbot_manager.send_message(message)
            self.update_status_display("Status: Sending message...")
        else:
            self.handle_ai_error("AI Chatbot Manager not initialized.")

    @pyqtSlot()
    def on_ask_ai_to_generate_fsm(self):
        logger.info("AIChatUI: on_ask_ai_to_generate_fsm CALLED!")
        description, ok = QInputDialog.getMultiLineText(self.mw, "Generate FSM", "Describe the FSM you want to create:", "Example: A traffic light with states Red, Yellow, Green...")
        if ok and description.strip():
            logger.info("AIChatUI: Sending FSM desc: '%s...'", description[:50])
            self.update_status_display("Status: Generating FSM from description...")
            if self.mw.ai_chatbot_manager:
                self.mw.ai_chatbot_manager.generate_fsm_from_description(description)
                self._append_to_chat_display("You", f"Generate an FSM: {description}")
            else:
                self.handle_ai_error("AI Chatbot Manager not initialized.")
        elif ok: QMessageBox.warning(self.mw, "Empty Description", "Please provide a description for the FSM.")

    @pyqtSlot()
    def on_openai_settings(self): # Method name unchanged, but logic is for Gemini now
        logger.info("AIChatUI: on_openai_settings CALLED! (Now Google AI/Gemini Settings)")
        if not self.mw.ai_chatbot_manager:
            logger.warning("AIChatUI: AI Chatbot Manager (mw.ai_chatbot_manager) not available for settings.")
            QMessageBox.warning(self.mw, "AI Error", "AI Chatbot Manager is not initialized. Cannot open settings.")
            return

        current_key = self.mw.ai_chatbot_manager.api_key or ""
        key, ok = QInputDialog.getText(
            self.mw,
            "Google AI API Key (Gemini)", # Changed dialog title
            "Enter your Google AI API Key for Gemini (leave blank to clear):", # Changed dialog label
            QLineEdit.PasswordEchoOnEdit, # Keep as PasswordEchoOnEdit
            current_key
        )
        if ok:
            new_key_value = key.strip()
            logger.info(f"AIChatUI: Google AI API Key dialog returned. OK: {ok}, Key: {'SET' if new_key_value else 'EMPTY'}")
            self.mw.ai_chatbot_manager.set_api_key(new_key_value if new_key_value else None)
            if new_key_value:
                self.update_status_display("Status: API Key Set. Ready.")
                if hasattr(self.mw, 'log_message'): self.mw.log_message("INFO","Google AI API Key has been set/updated.")
            else:
                self.update_status_display("Status: API Key Cleared. AI Inactive.")
                if hasattr(self.mw, 'log_message'): self.mw.log_message("INFO","Google AI API Key has been cleared.")
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
                self.update_status_display("Status: Chat history cleared.")
                self._append_to_chat_display("System", "Chat history cleared.")
            else:
                logger.info("AIChatUI: User cancelled clearing chat history.")
        else:
            self.handle_ai_error("AI Chatbot Manager not initialized.")