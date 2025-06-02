# bsm_designer_project/ui_ai_chatbot_manager.py
import html
import re
from PyQt5.QtWidgets import (
    QTextEdit, QLineEdit, QPushButton, QLabel, QInputDialog, QMessageBox, QAction,
    QWidget, QVBoxLayout, QHBoxLayout, QStyle
)
from PyQt5.QtCore import QObject, pyqtSlot, QTime
from PyQt5.QtGui import QIcon, QColor, QPalette

# Import AIStatus from ai_chatbot module where it's defined
from ai_chatbot import AIStatus

from config import COLOR_TEXT_SECONDARY, COLOR_ACCENT_SUCCESS, COLOR_ACCENT_ERROR
from utils import get_standard_icon
from config import ( 
    APP_FONT_SIZE_SMALL, COLOR_BACKGROUND_MEDIUM, COLOR_ACCENT_WARNING,
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_SECONDARY, COLOR_TEXT_PRIMARY,
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_ACCENT_ERROR, COLOR_TEXT_EDITOR_DARK_SECONDARY,
    COLOR_BACKGROUND_EDITOR_DARK, COLOR_TEXT_EDITOR_DARK_PRIMARY, COLOR_BORDER_LIGHT,
    COLOR_TEXT_ON_ACCENT, COLOR_BACKGROUND_DIALOG # Added COLOR_BACKGROUND_DIALOG
)

import logging
logger = logging.getLogger(__name__)

class AIChatUIManager(QObject):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window # This is the MainWindow instance

        self.ai_chat_display: QTextEdit = None
        self.ai_chat_input: QLineEdit = None
        self.ai_chat_send_button: QPushButton = None
        self.ai_chat_status_label: QLabel = None
        self.original_send_button_icon: QIcon | None = None # Store original icon
        # self.thinking_spinner_movie: QMovie | None = None # Spinner not yet implemented

        self._connect_actions_to_manager_slots()
        self._connect_ai_chatbot_signals()

    def _connect_actions_to_manager_slots(self):
        logger.debug("AIChatUI: Connecting actions to manager slots...")
        if hasattr(self.mw, 'ask_ai_to_generate_fsm_action'):
            self.mw.ask_ai_to_generate_fsm_action.triggered.connect(self.on_ask_ai_to_generate_fsm)
        if hasattr(self.mw, 'openai_settings_action'): # Action name in main.py
            self.mw.openai_settings_action.triggered.connect(self.on_gemini_settings) # Method name in this class
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
        
        self.ai_chat_send_button = QPushButton() # Icon will be set in update_status_display
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

    @pyqtSlot(AIStatus, str) # <--- CORRECTED SIGNATURE
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
            if self.mw.ai_chatbot_manager and self.mw.ai_chatbot_manager.api_key and \
               self.mw.ai_chatbot_manager.chatbot_worker and self.mw.ai_chatbot_manager.chatbot_worker.client: # Check underlying state
                can_send_message = True
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
        # Status display update now comes from the manager's statusUpdate signal (AIStatus.ERROR)

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
            if self.mw.ai_chatbot_manager: # Manager should set status to READY if appropriate
                self.mw.ai_chatbot_manager._update_current_ai_status(AIStatus.READY, "Status: FSM generation cancelled.")
            return
        
        clear_current = (clicked_button == clear_btn)
        self.mw._add_fsm_data_to_scene(fsm_data, clear_current_diagram=clear_current, original_user_prompt=source_message)
        # The worker's `finally` block should emit READY status after successful processing.
        logger.info("AIChatUI: FSM data from AI processed and added to scene.")

    @pyqtSlot(str)
    def handle_plain_ai_response(self, ai_message: str):
        logger.info("AIChatUI: Received plain AI response.")
        self._append_to_chat_display("AI", ai_message)
        # Status update (to READY) should come from the worker's finally block.

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
            self.handle_ai_error("AI Chatbot Manager not initialized.") # Should also set error status via manager if possible

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