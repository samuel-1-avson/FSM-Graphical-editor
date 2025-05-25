# bsm_designer_project/ui_ai_chatbot_manager.py
import html
import re
from PyQt5.QtWidgets import (You
    QTextEdit, QLineEdit, QPushButton, QLabel, QInputDialog, QMessageBox, QAction,
    QWidget are absolutely correct. It seems I made the same oversight in `ui_ai_, QVBoxLayout, QHBoxLayout, QStyle
)
from PyQt5.QtCore import QObject, pyqtSlot, Qchatbot_manager.py` as I did in `ui_py_simulation_manager.py` regarding the callsTime
from PyQt5.QtGui import QIcon

from utils import get_standard_icon # Assumes utils.py to `get_standard_icon`.

The `TypeError` is occurring because `get_standard_icon(self.mw./get_standard_icon takes 2 args
from config import COLOR_ACCENT_PRIMARY, COLOR_ACCENT_SECONDARY, COLOR_TEXT_PRIMARY

import logging
logger = logging.getLogger(__name__)

class AIChatUIManager(Qstyle(), QStyle.SP_ArrowForward, "Snd")` is still passing three arguments, but `get_standard_Object):
    def __init__(self, main_window, parent=None):
        super().__init__(icon` in `utils.py` (after our previous fixes) now expects only one or two.

**The Fix:**parent)
        self.mw = main_window 

        self.ai_chat_display: QTextEdit

In `bsm_designer_project/ui_ai_chatbot_manager.py`, you need to correct = None
        self.ai_chat_input: QLineEdit = None
        self.ai_chat_ the call to `get_standard_icon` for the `ai_chat_send_button`.

**Correctsend_button: QPushButton = None
        self.ai_chat_status_label: QLabel = None
        ed `bsm_designer_project/ui_ai_chatbot_manager.py`:**

```python

        self._connect_actions_to_manager_slots()
        self._connect_ai_chatbot_signals()

    def _connect_actions_to_manager_slots(self):
        if hasattr(self# bsm_designer_project/ui_ai_chatbot_manager.py
import html
import re
from PyQt5.QtWidgets import (
    QTextEdit, QLineEdit, QPushButton, QLabel, QInputDialog, QMessageBox, QAction.mw, 'ask_ai_to_generate_fsm_action'):
            self.mw.ask_ai_to_generate_fsm_action.triggered.connect(self.on_ask_ai_,
    QWidget, QVBoxLayout, QHBoxLayout, QStyle
)
from PyQt5.QtCore import QObject, pyqtSlot, QTime
from PyQt5.QtGui import QIcon

from utils import get_standard_icon #to_generate_fsm)
        
        if hasattr(self.mw, 'openai_settings_action'):
            self.mw.openai_settings_action.triggered.connect(self.on_openai_settings)
 Assumes utils.py/get_standard_icon takes 2 args
from config import COLOR_ACCENT_PRIMARY, COLOR_ACCENT_SECONDARY, COLOR_TEXT_PRIMARY

import logging
logger = logging.getLogger(__name        
        if hasattr(self.mw, 'clear_ai_chat_action'):
            self.mw.clear_ai_chat_action.triggered.connect(self.on_clear_ai_chat_history__)

class AIChatUIManager(QObject):
    def __init__(self, main_window, parent=)

    def _connect_ai_chatbot_signals(self):
        if self.mw.ai_None):
        super().__init__(parent)
        self.mw = main_window 

        self.ai_chatchatbot_manager:
            self.mw.ai_chatbot_manager.statusUpdate.connect(self.update_display: QTextEdit = None
        self.ai_chat_input: QLineEdit = None
        self_status_display)
            self.mw.ai_chatbot_manager.errorOccurred.connect(self.ai_chat_send_button: QPushButton = None
        self.ai_chat_status_label:.handle_ai_error)
            self.mw.ai_chatbot_manager.fsmDataReceived. QLabel = None
        
        self._connect_actions_to_manager_slots()
        self._connectconnect(self.handle_fsm_data_from_ai)
            self.mw.ai_chatbot_ai_chatbot_signals()

    def _connect_actions_to_manager_slots(self):
_manager.plainResponseReady.connect(self.handle_plain_ai_response)

    def create_        if hasattr(self.mw, 'ask_ai_to_generate_fsm_action'):
            self.dock_widget_contents(self) -> QWidget:
        ai_chat_widget = QWidget()
mw.ask_ai_to_generate_fsm_action.triggered.connect(self.on_ask        ai_chat_layout = QVBoxLayout(ai_chat_widget)
        ai_chat_layout._ai_to_generate_fsm)
        
        if hasattr(self.mw, 'openai_setContentsMargins(5,5,5,5); ai_chat_layout.setSpacing(5)

settings_action'):
            self.mw.openai_settings_action.triggered.connect(self.on_        self.ai_chat_display = QTextEdit(); self.ai_chat_display.setReadOnly(Trueopenai_settings)
        
        if hasattr(self.mw, 'clear_ai_chat_action'):)
        self.ai_chat_display.setObjectName("AIChatDisplay"); self.ai_chat_display.setStyleSheet
            self.mw.clear_ai_chat_action.triggered.connect(self.on_clear_("font-size: 9pt; padding: 5px;")
        self.ai_chat_displayai_chat_history)

    def _connect_ai_chatbot_signals(self):
        if self.mw.ai_chatbot_manager:
            self.mw.ai_chatbot_manager.statusUpdate..setPlaceholderText("AI chat history will appear here...")
        ai_chat_layout.addWidget(self.ai_chatconnect(self.update_status_display)
            self.mw.ai_chatbot_manager.errorOcc_display, 1)

        input_layout = QHBoxLayout()
        self.ai_chat_input = QLineEdit(); self.ai_chat_input.setObjectName("AIChatInput")
        self.ai_urred.connect(self.handle_ai_error)
            self.mw.ai_chatbot_manager.fsmDataReceived.connect(self.handle_fsm_data_from_ai)
            self.chat_input.setPlaceholderText("Type your message to the AI...")
        self.ai_chat_inputmw.ai_chatbot_manager.plainResponseReady.connect(self.handle_plain_ai_response).returnPressed.connect(self.on_send_ai_chat_message)
        input_layout.

    def create_dock_widget_contents(self) -> QWidget:
        ai_chat_widgetaddWidget(self.ai_chat_input, 1)

        # ***** THIS IS THE LINE FROM THE TRACE = QWidget()
        ai_chat_layout = QVBoxLayout(ai_chat_widget)
        ai_chat_BACK - CORRECTED CALL *****
        self.ai_chat_send_button = QPushButton(get_standard_layout.setContentsMargins(5,5,5,5); ai_chat_layout.setSpacing(5icon(QStyle.SP_ArrowForward, "Snd"), "Send")
        # ***** END OF CORRECTION FOR THIS)

        self.ai_chat_display = QTextEdit(); self.ai_chat_display.setReadOnly LINE *****
        self.ai_chat_send_button.setObjectName("AIChatSendButton")
        self(True)
        self.ai_chat_display.setObjectName("AIChatDisplay"); self.ai_chat_display..ai_chat_send_button.clicked.connect(self.on_send_ai_chat_messagesetStyleSheet("font-size: 9pt; padding: 5px;")
        self.ai_chat_)
        input_layout.addWidget(self.ai_chat_send_button)
        ai_chat_layout.addLayout(input_layout)

        self.ai_chat_status_label = QLabel("display.setPlaceholderText("AI chat history will appear here...")
        ai_chat_layout.addWidget(self.aiStatus: Initializing...")
        self.ai_chat_status_label.setObjectName("AIChatStatusLabel");_chat_display, 1)

        input_layout = QHBoxLayout()
        self.ai_chat self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey;")_input = QLineEdit(); self.ai_chat_input.setObjectName("AIChatInput")
        self.ai_chat_input.setPlaceholderText("Type your message to the AI...")
        self.ai_chat
        ai_chat_layout.addWidget(self.ai_chat_status_label)
        
        self_input.returnPressed.connect(self.on_send_ai_chat_message)
        input_.update_status_display("Status: API Key required. Configure in Settings.") 
        return ai_chat_widgetlayout.addWidget(self.ai_chat_input, 1)

        # ***** THIS IS THE LINE FROM THE TRACE

    # ... (rest of the methods in AIChatUIManager)
    @pyqtSlot(str)
    BACK - CORRECTED CALL *****
        self.ai_chat_send_button = QPushButton(get_standard_def update_status_display(self, status_text: str):
        if not self.ai_chaticon(QStyle.SP_ArrowForward, "Snd"), "Send")
        # ***** END OF COR_status_label: return
        self.ai_chat_status_label.setText(status_text)
        isRECTION *****
        self.ai_chat_send_button.setObjectName("AIChatSendButton")
        self.ai_thinking = any(s in status_text.lower() for s in ["thinking...", "sending...", "generating_chat_send_button.clicked.connect(self.on_send_ai_chat_message)
..."])
        is_key_req = any(s in status_text.lower() for s in ["        input_layout.addWidget(self.ai_chat_send_button)
        ai_chat_layoutapi key required", "inactive", "api key error"])
        is_error = "error" in status_.addLayout(input_layout)

        self.ai_chat_status_label = QLabel("Status:text.lower() or "failed" in status_text.lower() or is_key_req

        if Initializing...")
        self.ai_chat_status_label.setObjectName("AIChatStatusLabel"); self.ai_ is_error: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: red;")
        elif is_thinking: self.ai_chat_status_label.setStyleSheet(fchat_status_label.setStyleSheet("font-size: 8pt; color: grey;")
        ai_chat_layout"font-size: 8pt; color: {COLOR_ACCENT_SECONDARY.name()};")
.addWidget(self.ai_chat_status_label)
        
        self.update_status_display        else: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color("Status: API Key required. Configure in Settings.") 
        return ai_chat_widget

    # ... (rest of: grey;")

        can_send = not is_thinking and not is_key_req
        if self.ai_ the methods in AIChatUIManager) ...
    @pyqtSlot(str)
    def update_status_display(selfchat_send_button: self.ai_chat_send_button.setEnabled(can_send)
        , status_text: str):
        if not self.ai_chat_status_label: return
        if self.ai_chat_input:
            self.ai_chat_input.setEnabled(can_sendself.ai_chat_status_label.setText(status_text)
        is_thinking = any(s in status)
            if can_send and hasattr(self.mw, 'ai_chatbot_dock') and self.mw_text.lower() for s in ["thinking...", "sending...", "generating..."])
        is_key_.ai_chatbot_dock and self.mw.ai_chatbot_dock.isVisible() and self.mw.isActiveWindow():req = any(s in status_text.lower() for s in ["api key required", "inactive", "
                self.ai_chat_input.setFocus()
        if hasattr(self.mw, 'ask_ai_api key error"])
        is_error = "error" in status_text.lower() or "failed"to_generate_fsm_action'):
            self.mw.ask_ai_to_generate_f in status_text.lower() or is_key_req

        if is_error: self.ai_chat_statussm_action.setEnabled(can_send)

    def _append_to_chat_display(self,_label.setStyleSheet("font-size: 8pt; color: red;")
        elif is_thinking: self. sender: str, message: str):
        if not self.ai_chat_display: return
        timestampai_chat_status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR = QTime.currentTime().toString('hh:mm')
        sender_color = COLOR_ACCENT_PRIMARY.name()_ACCENT_SECONDARY.name()};") # Assuming COLOR_ACCENT_SECONDARY is QColor
        else: self.ai_chat_status_label.setStyleSheet("font-size: 8pt; color: grey # Use .name() if COLOR_ACCENT_PRIMARY is QColor
        if sender == "You": sender;")

        can_send = not is_thinking and not is_key_req
        if self.ai_color = COLOR_ACCENT_SECONDARY.name() # Use .name() if QColor
        elif sender == "System_chat_send_button: self.ai_chat_send_button.setEnabled(can_send)
 Error" or sender == "System": sender_color = "#D32F2F"

        escaped_message =        if self.ai_chat_input:
            self.ai_chat_input.setEnabled(can_ html.escape(message)
        escaped_message = re.sub(r'\*\*(.*?)\*\send)
            if can_send and hasattr(self.mw, 'ai_chatbot_dock') and self.mw*', r'<b>\1</b>', escaped_message)
        escaped_message = re.sub(r.ai_chatbot_dock and self.mw.ai_chatbot_dock.isVisible() and self.mw.isActiveWindow():'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'<i>\
                self.ai_chat_input.setFocus()
        
        if hasattr(self.mw,1</i>', escaped_message)
        escaped_message = re.sub(r'```(.*?)```', r'<pre><code style="background-color:#f0f0f0; padding:2px  'ask_ai_to_generate_fsm_action'):
            self.mw.ask_ai_to_generate_fsm_action.setEnabled(can_send)

    def _append_to_chat_display4px; border-radius:3px; display:block; white-space:pre-wrap;">\1</code></pre(self, sender: str, message: str):
        if not self.ai_chat_display: return>', escaped_message, flags=re.DOTALL)
        escaped_message = re.sub(r
        timestamp = QTime.currentTime().toString('hh:mm')
        sender_color = COLOR_ACC'`(.*?)`', r'<code style="background-color:#f0f0f0; padding:1px 3px; border-radius:2px;">\1</code>', escaped_message)
        escapedENT_PRIMARY # Assuming this is a string hex
        if sender == "You": sender_color = COLOR_ACCENT_message = escaped_message.replace("\n", "<br>")
        
        formatted_html = (f_SECONDARY # Assuming this is a string hex
        elif sender == "System Error" or sender == "System": sender_color"<div style='margin-bottom: 8px;'>"
                          f"<span style='font-size: = "#D32F2F"

        escaped_message = html.escape(message)
        escaped8pt; color:grey;'>[{timestamp}]</span> "
                          f"<strong style='color:{sender_color};'>{_message = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped_html.escape(sender)}:</strong>"
                          f"<div style='margin-top: 3px;message)
        escaped_message = re.sub(r'(?<!\*)\*(?!\*)(.*? padding-left: 5px; border-left: 2px solid {sender_color if sender_color != '#)(?<!\*)\*(?!\*)', r'<i>\1</i>', escaped_message)
        escapD32F2F' else '#FFCDD2'};'>{escaped_message}</div></div>")
        ed_message = re.sub(r'```(.*?)```', r'<pre><code style="background-self.ai_chat_display.append(formatted_html)
        self.ai_chat_display.color:#f0f0f0; padding:2px 4px; border-radius:3px; display:ensureCursorVisible()

    @pyqtSlot(str)
    def handle_ai_error(self, error_messageblock; white-space:pre-wrap;">\1</code></pre>', escaped_message, flags=re.DOTALL): str):
        self._append_to_chat_display("System Error", error_message)
        
        escaped_message = re.sub(r'`(.*?)`', r'<code style="background-logger.error("AIChatUI: AI Chatbot Error: %s", error_message)
        self.updatecolor:#f0f0f0; padding:1px 3px; border-radius:2px;">_status_display(f"Error: {error_message.splitlines()[0][:50]}...")

\1</code>', escaped_message)
        escaped_message = escaped_message.replace("\n", "<    @pyqtSlot(dict, str)
    def handle_fsm_data_from_ai(br>")
        
        formatted_html = (f"<div style='margin-bottom: 8px;self, fsm_data: dict, source_message: str):
        logger.info("AIChatUI'>"
                          f"<span style='font-size:8pt; color:grey;'>[{timestamp}]</span> ": Received FSM data. Source: '%s...'", source_message[:30])
        self._append
                          f"<strong style='color:{sender_color};'>{html.escape(sender)}:</strong>"
                          f_to_chat_display("AI", f"Received FSM structure. (Source: {source_message[:"<div style='margin-top: 3px; padding-left: 5px; border-left:30]}...) Adding to diagram.")
        if not fsm_data or (not fsm_data. 2px solid {sender_color if sender_color != '#D32F2F' else '#FFCDDget('states') and not fsm_data.get('transitions')):
            logger.error("AIChatUI: AI2'};'>{escaped_message}</div></div>")
        self.ai_chat_display.append(formatted returned empty or invalid FSM data."); self.update_status_display("Status: AI returned no FSM data_html)
        self.ai_chat_display.ensureCursorVisible()

    @pyqtSlot(.")
            self._append_to_chat_display("System", "AI did not return a valid FSM structurestr)
    def handle_ai_error(self, error_message: str):
        self._append to draw."); return

        msg_box = QMessageBox(self.mw); msg_box.setIcon(QMessageBox._to_chat_display("System Error", error_message)
        logger.error("AIChatUI: AI Chatbot Error: %s", error_message)
        self.update_status_display(f"ErrorQuestion); msg_box.setWindowTitle("Add AI Generated FSM")
        msg_box.setText("AI has generated an FSM. Do you want to clear the current diagram before adding the new FSM, or add to the existing one?"): {error_message.splitlines()[0][:50]}...")

    @pyqtSlot(dict, str)
    def handle_fsm_data_from_ai(self, fsm_data: dict
        clear_btn = msg_box.addButton("Clear and Add", QMessageBox.AcceptRole)
        add_btn = msg_box.addButton("Add to Existing", QMessageBox.AcceptRole)
        cancel_btn = msg, source_message: str):
        logger.info("AIChatUI: Received FSM data. Source: '%_box.addButton("Cancel", QMessageBox.RejectRole); msg_box.setDefaultButton(cancel_btn)
s...'", source_message[:30])
        self._append_to_chat_display("AI", f"Received        msg_box.exec()
        clicked = msg_box.clickedButton()
        if clicked == cancel FSM structure. (Source: {source_message[:30]}...) Adding to diagram.")
        if not_btn: logger.info("AIChatUI: User cancelled adding AI FSM."); self.update_status_ fsm_data or (not fsm_data.get('states') and not fsm_data.get('transitionsdisplay("Status: FSM generation cancelled."); return
        
        self.mw._add_fsm_data_to')):
            logger.error("AIChatUI: AI returned empty or invalid FSM data."); self.update_status_display("Status: AI returned no FSM data.")
            self._append_to_chat_display_scene(fsm_data, clear_current_diagram=(clicked == clear_btn), original_user_prompt=source_message)
        self.update_status_display("Status: FSM added to diagram.")
        logger.("System", "AI did not return a valid FSM structure to draw."); return

        msg_box = QMessageBoxinfo("AIChatUI: FSM data from AI processed and added to scene.")

    @pyqtSlot(str)
(self.mw); msg_box.setIcon(QMessageBox.Question); msg_box.setWindowTitle("Add AI Generated FSM    def handle_plain_ai_response(self, ai_message: str):
        logger.info("")
        msg_box.setText("AI has generated an FSM. Do you want to clear the current diagram before addingAIChatUI: Received plain AI response.")
        self._append_to_chat_display("AI", ai the new FSM, or add to the existing one?")
        clear_btn = msg_box.addButton("Clear and Add_message)

    @pyqtSlot()
    def on_send_ai_chat_message(self", QMessageBox.AcceptRole)
        add_btn = msg_box.addButton("Add to Existing", QMessageBox.AcceptRole):
        if not self.ai_chat_input: return
        message = self.ai_chat_)
        cancel_btn = msg_box.addButton("Cancel", QMessageBox.RejectRole); msg_box.input.text().strip()
        if not message: return
        self.ai_chat_input.clearsetDefaultButton(cancel_btn)
        msg_box.exec()
        clicked = msg_box.clicked(); self._append_to_chat_display("You", message)
        if self.mw.ai_chatbot_managerButton()
        if clicked == cancel_btn: logger.info("AIChatUI: User cancelled adding AI F:
            self.mw.ai_chatbot_manager.send_message(message)
            self.updateSM."); self.update_status_display("Status: FSM generation cancelled."); return
        
        self._status_display("Status: Sending message...")
        else:
            self.handle_ai_error("mw._add_fsm_data_to_scene(fsm_data, clear_current_diagram=(clickedAI Chatbot Manager not initialized.")

    @pyqtSlot()
    def on_ask_ai_to == clear_btn), original_user_prompt=source_message)
        self.update_status_display("Status_generate_fsm(self):
        description, ok = QInputDialog.getMultiLineText(self.mw, ": FSM added to diagram.")
        logger.info("AIChatUI: FSM data from AI processed and added toGenerate FSM", "Describe the FSM you want to create:", "Example: A traffic light with states Red, scene.")

    @pyqtSlot(str)
    def handle_plain_ai_response(self, Yellow, Green...")
        if ok and description.strip():
            logger.info("AIChatUI: Sending ai_message: str):
        logger.info("AIChatUI: Received plain AI response.")
        self FSM desc: '%s...'", description[:50])
            self.update_status_display("Status: Generating F._append_to_chat_display("AI", ai_message)

    @pyqtSlot()
    SM from description...")
            if self.mw.ai_chatbot_manager:
                self.mw.aidef on_send_ai_chat_message(self):
        if not self.ai_chat_input_chatbot_manager.generate_fsm_from_description(description)
                self._append_to_: return
        message = self.ai_chat_input.text().strip()
        if not message:chat_display("You", f"Generate an FSM: {description}")
            else:
                self. return
        self.ai_chat_input.clear(); self._append_to_chat_display("You", message)handle_ai_error("AI Chatbot Manager not initialized.")
        elif ok: QMessageBox.warning(self.mw,
        if self.mw.ai_chatbot_manager:
            self.mw.ai_chatbot_manager "Empty Description", "Please provide a description for the FSM.")

    @pyqtSlot()
    def.send_message(message)
            self.update_status_display("Status: Sending message...")
         on_openai_settings(self):
        if not self.mw.ai_chatbot_manager:
            else:
            self.handle_ai_error("AI Chatbot Manager not initialized.")

    @pyqtlogger.warning("AIChatUI: AI Chatbot Manager not available for settings.")
            QMessageBox.warning(self.Slot()
    def on_ask_ai_to_generate_fsm(self):
        description, ok = Qmw, "AI Error", "AI Chatbot Manager is not initialized.")
            return

        current_key =InputDialog.getMultiLineText(self.mw, "Generate FSM", "Describe the FSM you want to self.mw.ai_chatbot_manager.api_key or ""
        key, ok = QInputDialog. create:", "Example: A traffic light with states Red, Yellow, Green...")
        if ok and description.stripgetText(
            self.mw,
            "OpenAI API Key",
            "Enter your OpenAI API Key (leave blank():
            logger.info("AIChatUI: Sending FSM desc: '%s...'", description[:50])
             to clear):",
            QLineEdit.PasswordEchoOnEdit, 
            current_key
        )
        ifself.update_status_display("Status: Generating FSM from description...")
            if self.mw.ai ok:
            new_key_value = key.strip()
            self.mw.ai_chatbot__chatbot_manager:
                self.mw.ai_chatbot_manager.generate_fsm_from_manager.set_api_key(new_key_value if new_key_value else None)
            description(description)
                self._append_to_chat_display("You", f"Generate an FSMif new_key_value:
                logger.info("AIChatUI: OpenAI API Key set/updated.")
                : {description}")
            else:
                self.handle_ai_error("AI Chatbot Manager not initialized.")
        self.update_status_display("Status: API Key Set. Ready.")
            else:
                logger.elif ok: QMessageBox.warning(self.mw, "Empty Description", "Please provide a description for the FSMinfo("AIChatUI: OpenAI API Key cleared.")
                self.update_status_display("Status: API.")

    @pyqtSlot()
    def on_openai_settings(self):
        if not self Key Cleared. AI Inactive.")

    @pyqtSlot()
    def on_clear_ai_chat.mw.ai_chatbot_manager:
            logger.warning("AIChatUI: AI Chatbot Manager not_history(self):
        if self.mw.ai_chatbot_manager:
            self.mw. available for settings.")
            QMessageBox.warning(self.mw, "AI Error", "AI Chatbot Manager is not initialized.")
            return

        current_key = self.mw.ai_chatbot_manager.apiai_chatbot_manager.clear_conversation_history()
            if self.ai_chat_display: self.ai_chat_display.clear(); self.ai_chat_display.setPlaceholderText("AI chat history will appear here_key or ""
        key, ok = QInputDialog.getText(
            self.mw,
            "OpenAI...")
            logger.info("AIChatUI: Chat history cleared.")
            self.update_status_display API Key",
            "Enter your OpenAI API Key (leave blank to clear):",
            QLineEdit.PasswordEcho("Status: Chat history cleared.") 
        else:
            self.handle_ai_error("AI ChatOnEdit, 
            current_key
        )
        if ok:
            new_key_value = key.bot Manager not initialized.")