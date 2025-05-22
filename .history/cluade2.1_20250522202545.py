import sys
import os
import tempfile
import subprocess
import json
import html # Used for escaping in properties dock
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QToolBox, QAction,
    QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QGraphicsView, QGraphicsScene, QStatusBar, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QInputDialog, QLineEdit, QColorDialog, QDialog, QFormLayout,
    QSpinBox, QComboBox, QGraphicsRectItem, QGraphicsPathItem, QDialogButtonBox,
    QFileDialog, QProgressBar, QTabWidget, QCheckBox, QActionGroup, QGraphicsItem,
    QGroupBox, QUndoStack, QUndoCommand, QStyle, QSizePolicy, QGraphicsLineItem,
    QToolButton, QGraphicsSceneMouseEvent, QGraphicsSceneDragDropEvent,
    QGraphicsSceneHoverEvent, QGraphicsTextItem, QGraphicsDropShadowEffect,
    QHeaderView, QTableWidget, QTableWidgetItem, QAbstractItemView 
)
from PyQt5.QtGui import (
    QIcon, QBrush, QColor, QFont, QPen, QPixmap, QDrag, QPainter, QPainterPath,
    QTransform, QKeyEvent, QPainterPathStroker, QPolygonF, QKeySequence,
    QDesktopServices, QWheelEvent, QMouseEvent, QCloseEvent, QFontMetrics, QPalette
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QObject, pyqtSignal, QThread, QDir,
    QEvent, QTimer, QSize, QTime, QUrl,
    QSaveFile, QIODevice
)
import math

# --- FSM SIMULATOR IMPORT ---
from fsm_simulator import FSMSimulator, FSMError 


# --- Configuration ---
APP_VERSION = "1.7.1" # Fixes for event handling and icon loading
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
    "Timer Timeout": "timeout(TIMER_ID)", "Button Press": "button_pressed(BUTTON_NUMBER)",
    "Sensor Threshold Breach": "sensor_threshold(SENSOR_NAME)", "Data Packet Received": "data_reception_complete(CHANNEL)",
    "Emergency Stop Active": "emergency_stop", "Rising Edge Detection": "positive_edge(SIGNAL_NAME)",
    "Falling Edge Detection": "negative_edge(SIGNAL_NAME)", "Message Received": "msg_arrived(MSG_TYPE_ID)",
    "System Error Occurred": "system_fault(FAULT_CODE)", "User Input Event": "user_command(COMMAND_CODE)",
}
MECHATRONICS_COMMON_CONDITIONS = {
    "Is System Safe": "is_safety_interlock_active() == false", "Is Mode Nominal": "get_operating_mode() == NOMINAL_MODE",
    "Counter Reached Limit": "retry_counter >= MAX_RETRIES", "Variable is Value": "my_control_variable == TARGET_STATE_VALUE",
    "Flag is True": "is_ready_flag == true", "Flag is False": "is_busy_flag == false",
    "Battery Level OK": "get_battery_voltage_mv() > MINIMUM_OPERATING_VOLTAGE_MV",
    "Communication Healthy": "is_communication_link_up() == true",
    "Sensor Value In Range": "(sensor_data >= SENSOR_MIN_VALID && sensor_data <= SENSOR_MAX_VALID)",
    "Target Reached": "abs(current_position - target_position) < POSITION_TOLERANCE",
    "Input Signal High": "read_digital_input(PIN_FOR_CONDITION) == 1",
    "Input Signal Low": "read_digital_input(PIN_FOR_CONDITION) == 0",
}

# --- UI Styling and Theme Colors ---
COLOR_BACKGROUND_LIGHT = "#F5F5F5"; COLOR_BACKGROUND_MEDIUM = "#EEEEEE"; COLOR_BACKGROUND_DARK = "#E0E0E0"
COLOR_BACKGROUND_DIALOG = "#FFFFFF"; COLOR_TEXT_PRIMARY = "#212121"; COLOR_TEXT_SECONDARY = "#757575"
COLOR_TEXT_ON_ACCENT = "#FFFFFF"; COLOR_ACCENT_PRIMARY = "#1976D2"; COLOR_ACCENT_PRIMARY_LIGHT = "#BBDEFB"
COLOR_ACCENT_SECONDARY = "#FF8F00"; COLOR_ACCENT_SECONDARY_LIGHT = "#FFECB3"; COLOR_BORDER_LIGHT = "#CFD8DC"
COLOR_BORDER_MEDIUM = "#90A4AE"; COLOR_BORDER_DARK = "#607D8B"; COLOR_ITEM_STATE_DEFAULT_BG = "#E3F2FD"
COLOR_ITEM_STATE_DEFAULT_BORDER = "#90CAF9"; COLOR_ITEM_STATE_SELECTION = "#FFD54F"
COLOR_ITEM_TRANSITION_DEFAULT = "#009688"; COLOR_ITEM_TRANSITION_SELECTION = "#80CBC4"
COLOR_ITEM_COMMENT_BG = "#FFFDE7"; COLOR_ITEM_COMMENT_BORDER = "#FFF59D"
COLOR_GRID_MINOR = "#ECEFF1"; COLOR_GRID_MAJOR = "#CFD8DC"
COLOR_PY_SIM_STATE_ACTIVE = QColor("#4CAF50"); COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH = 2.5
APP_FONT_FAMILY = "Segoe UI, Arial, sans-serif"
STYLE_SHEET_GLOBAL = f"""  /* ... (Your full QSS string remains here, ensure it's valid) ... */ """ # Truncated for brevity


# --- Utility Functions ---
def get_standard_icon(standard_pixmap_enum_value, fallback_text=None): # This is your complex one
    icon = QIcon()
    try:
        icon = QApplication.style().standardIcon(standard_pixmap_enum_value)
    except Exception: pass
    if icon.isNull():
        pixmap_size = QSize(24, 24); pixmap = QPixmap(pixmap_size); pixmap.fill(QColor(COLOR_BACKGROUND_MEDIUM))
        painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing)
        border_rect = QRectF(0.5, 0.5, pixmap_size.width() -1, pixmap_size.height() -1)
        painter.setPen(QPen(QColor(COLOR_BORDER_MEDIUM), 1)); painter.drawRoundedRect(border_rect, 3, 3)
        if fallback_text:
            font = QFont(APP_FONT_FAMILY, 10, QFont.Bold); painter.setFont(font); painter.setPen(QColor(COLOR_TEXT_PRIMARY))
            display_text = fallback_text[:2].upper()
            if len(fallback_text) == 1: display_text = fallback_text[0].upper()
            elif len(fallback_text) > 1 and fallback_text[1].islower() and not fallback_text[0].isdigit(): display_text = fallback_text[0].upper()
            painter.drawText(pixmap.rect(), Qt.AlignCenter, display_text)
        else:
             painter.setPen(QPen(QColor(COLOR_ACCENT_PRIMARY), 2)); center_pt = pixmap.rect().center()
             painter.drawLine(center_pt.x() - 4, center_pt.y(), center_pt.x() + 4, center_pt.y())
             painter.drawLine(center_pt.x(), center_pt.y() -4, center_pt.x(), center_pt.y() + 4)
        painter.end(); return QIcon(pixmap)
    return icon

# --- MATLAB Connection Handling --- (No change to this class itself)
class MatlabConnection(QObject):
    connectionStatusChanged = pyqtSignal(bool, str); simulationFinished = pyqtSignal(bool, str, str); codeGenerationFinished = pyqtSignal(bool, str, str)
    def __init__(self): super().__init__(); self.matlab_path = ""; self.connected = False; self._active_threads = []
    def set_matlab_path(self, path): # ... (Method content unchanged) ...
        self.matlab_path = path.strip()
        if self.matlab_path and os.path.exists(self.matlab_path) and \
           (os.access(self.matlab_path, os.X_OK) or self.matlab_path.lower().endswith('.exe')):
            self.connected = True; self.connectionStatusChanged.emit(True, f"MATLAB path set and appears valid: {self.matlab_path}"); return True
        else:
            old_path = self.matlab_path; self.connected = False; self.matlab_path = ""
            if old_path: self.connectionStatusChanged.emit(False, f"MATLAB path '{old_path}' is invalid or not executable.")
            else: self.connectionStatusChanged.emit(False, "MATLAB path cleared.")
            return False
    def test_connection(self): # ... (Method content unchanged) ...
        if not self.matlab_path: self.connected = False; self.connectionStatusChanged.emit(False, "MATLAB path not set. Cannot test connection."); return False
        if not self.connected and self.matlab_path :
             if not self.set_matlab_path(self.matlab_path): return False
        try:
            cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", "disp('MATLAB_CONNECTION_TEST_SUCCESS')"]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if "MATLAB_CONNECTION_TEST_SUCCESS" in process.stdout: self.connected = True; self.connectionStatusChanged.emit(True, "MATLAB connection test successful."); return True
            else: self.connected = False; error_msg = process.stderr or process.stdout or "Unexpected output from MATLAB."; self.connectionStatusChanged.emit(False, f"MATLAB connection test failed: {error_msg[:200]}"); return False
        except subprocess.TimeoutExpired: self.connected = False; self.connectionStatusChanged.emit(False, "MATLAB connection test timed out (20s)."); return False
        except subprocess.CalledProcessError as e: self.connected = False; self.connectionStatusChanged.emit(False, f"MATLAB error during test: {e.stderr or e.stdout or str(e)}".splitlines()[0]); return False
        except FileNotFoundError: self.connected = False; self.connectionStatusChanged.emit(False, f"MATLAB executable not found at: {self.matlab_path}"); return False
        except Exception as e: self.connected = False; self.connectionStatusChanged.emit(False, f"An unexpected error occurred during MATLAB test: {str(e)}"); return False
    def detect_matlab(self): # ... (Method content unchanged) ...
        paths_to_check = []; program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
        if sys.platform == 'win32': matlab_base = os.path.join(program_files, 'MATLAB')
        if os.path.isdir(matlab_base): versions = sorted([d for d in os.listdir(matlab_base) if d.startswith('R20')], reverse=True); [paths_to_check.append(os.path.join(matlab_base, v, 'bin', 'matlab.exe')) for v in versions]
        elif sys.platform == 'darwin': base_app_path = '/Applications'; potential_matlab_apps = sorted([d for d in os.listdir(base_app_path) if d.startswith('MATLAB_R20') and d.endswith('.app')], reverse=True); [paths_to_check.append(os.path.join(base_app_path, app, 'bin', 'matlab')) for app in potential_matlab_apps]
        else: common_base_paths = ['/usr/local/MATLAB', '/opt/MATLAB']; [paths_to_check.extend(os.path.join(bp, v, 'bin', 'matlab') for v in sorted([d for d in os.listdir(bp) if d.startswith('R20')], reverse=True)) for bp in common_base_paths if os.path.isdir(bp)]; paths_to_check.append('matlab')
        for pc in paths_to_check:
            if pc == 'matlab' and sys.platform != 'win32':
                try:
                    if subprocess.run([pc, "-batch", "exit"], timeout=5, capture_output=True).returncode == 0 and self.set_matlab_path(pc): return True
                except: continue
            elif os.path.exists(pc) and self.set_matlab_path(pc): return True
        self.connectionStatusChanged.emit(False, "MATLAB auto-detection failed. Please set the path manually."); return False
    def _run_matlab_script(self, script_content, worker_signal, success_message_prefix): # ... (Method content unchanged) ...
        if not self.connected: worker_signal.emit(False, "MATLAB not connected or path invalid.", ""); return
        try: temp_dir = tempfile.mkdtemp(prefix="bsm_matlab_"); script_file = os.path.join(temp_dir, "matlab_script.m");
        with open(script_file, 'w', encoding='utf-8') as f: f.write(script_content)
        except Exception as e: worker_signal.emit(False, f"Failed to create temporary MATLAB script: {e}", ""); return
        worker = MatlabCommandWorker(self.matlab_path, script_file, worker_signal, success_message_prefix); thread = QThread(); worker.moveToThread(thread)
        thread.started.connect(worker.run_command); worker.finished_signal.connect(thread.quit); worker.finished_signal.connect(worker.deleteLater); thread.finished.connect(thread.deleteLater)
        self._active_threads.append(thread); thread.finished.connect(lambda t=thread: self._active_threads.remove(t) if t in self._active_threads else None); thread.start()
    def generate_simulink_model(self, states, transitions, output_dir, model_name="BrainStateMachine"): # ... (Method content unchanged - long script definition omitted for brevity) ...
        if not self.connected: self.simulationFinished.emit(False, "MATLAB not connected.", ""); return False; slx_file_path = os.path.join(output_dir, f"{model_name}.slx").replace('\\', '/'); script_lines = ["..."]; script_content = "\n".join(script_lines); self._run_matlab_script(script_content, self.simulationFinished, "Model generation"); return True
    def run_simulation(self, model_path, sim_time=10): # ... (Method content unchanged - long script definition omitted for brevity) ...
        if not self.connected: self.simulationFinished.emit(False, "MATLAB not connected.", ""); return False; script_content = f"""..."""; self._run_matlab_script(script_content, self.simulationFinished, "Simulation"); return True
    def generate_code(self, model_path, language="C++", output_dir_base=None): # ... (Method content unchanged - long script definition omitted for brevity) ...
        if not self.connected: self.codeGenerationFinished.emit(False, "MATLAB not connected", ""); return False; script_content = f"""..."""; self._run_matlab_script(script_content, self.codeGenerationFinished, "Code generation"); return True
class MatlabCommandWorker(QObject): # ... (Class content unchanged) ...
    finished_signal = pyqtSignal(bool, str, str)
    def __init__(self, matlab_path, script_file, original_signal, success_message_prefix): super().__init__(); self.matlab_path, self.script_file, self.original_signal, self.success_message_prefix = matlab_path, script_file, original_signal, success_message_prefix
    def run_command(self): # ... (Method content unchanged) ...
        output_data_for_signal, success, message = "", False, ""
        try: # ...
            matlab_run_command = f"run('{self.script_file.replace('\\', '/')}')"; cmd = [self.matlab_path, "-nodisplay", "-nosplash", "-nodesktop", "-batch", matlab_run_command]; timeout_seconds = 600
            process = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=timeout_seconds, check=False, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            # ... (stdout/stderr processing unchanged) ...
        # ... (exception handling unchanged) ...
        finally: # ... (cleanup unchanged) ...
            self.finished_signal.emit(success, message, output_data_for_signal)

# --- Draggable Toolbox Buttons ---
class DraggableToolButton(QPushButton):
    def __init__(self, text, mime_type, item_type_data, parent=None):
        super().__init__(text, parent); self.setObjectName("DraggableToolButton"); self.mime_type = mime_type
        self.item_type_data = item_type_data; self.setText(text); self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed); self.drag_start_position = QPoint()
    def mousePressEvent(self, event: QMouseEvent): # event is QMouseEvent
        if event.button() == Qt.LeftButton: self.drag_start_position = event.pos() # event.pos() is correct for QMouseEvent
        super().mousePressEvent(event)
    def mouseMoveEvent(self, event: QMouseEvent): # CORRECTED - event is QMouseEvent here
        if not (event.buttons() & Qt.LeftButton): return
        # event.pos() is correct for QMouseEvent. Manhattan length for drag initiation.
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance(): return
        drag = QDrag(self); mime_data = QMimeData(); mime_data.setText(self.item_type_data) 
        mime_data.setData(self.mime_type, self.item_type_data.encode()); drag.setMimeData(mime_data)
        pixmap_size = QSize(max(150, self.width()), max(40,self.height())); pixmap = QPixmap(pixmap_size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing)
        button_rect = QRectF(0, 0, pixmap_size.width() - 1, pixmap_size.height() - 1)
        bg_color = QColor(self.palette().color(self.backgroundRole())).lighter(110)
        if not bg_color.isValid() or bg_color.alpha() == 0 : bg_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT)
        border_color = QColor(COLOR_ACCENT_PRIMARY)
        painter.setBrush(bg_color); painter.setPen(QPen(border_color, 1.5))
        painter.drawRoundedRect(button_rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5)
        icon_pixmap = self.icon().pixmap(QSize(20,20), QIcon.Normal, QIcon.On)
        text_x_offset = 10; icon_y_offset = (pixmap_size.height() - icon_pixmap.height()) / 2
        if not icon_pixmap.isNull(): painter.drawPixmap(int(text_x_offset), int(icon_y_offset), icon_pixmap); text_x_offset += icon_pixmap.width() + 8
        text_color = self.palette().color(QPalette.ButtonText)
        if not text_color.isValid(): text_color = QColor(COLOR_TEXT_PRIMARY)
        painter.setPen(text_color); painter.setFont(self.font())
        text_rect = QRectF(text_x_offset, 0, pixmap_size.width() - text_x_offset - 5, pixmap_size.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text()); painter.end()
        drag.setPixmap(pixmap); drag.setHotSpot(QPoint(pixmap.width() // 4, pixmap.height() // 2))
        drag.exec_(Qt.CopyAction | Qt.MoveAction)

# --- Graphics Items --- 
class GraphicsStateItem(QGraphicsRectItem): # ... (Class content mostly unchanged, ensure PySim related paint logic is fine) ...
    Type = QGraphicsItem.UserType + 1; def type(self): return GraphicsStateItem.Type
    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False,color=None, entry_action="", during_action="", exit_action="", description=""):
        super().__init__(x,y,w,h); self.text_label=text; self.is_initial=is_initial; self.is_final=is_final
        self.base_color=QColor(color) if color else QColor(COLOR_ITEM_STATE_DEFAULT_BG); self.border_color=QColor(color).darker(120) if color else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)
        self.entry_action, self.during_action, self.exit_action, self.description = entry_action,during_action,exit_action,description
        self._text_color=QColor(COLOR_TEXT_PRIMARY); self._font=QFont(APP_FONT_FAMILY,10,QFont.Bold); self._border_pen_width=1.5
        self.setPen(QPen(self.border_color,self._border_pen_width)); self.setBrush(QBrush(self.base_color))
        self.setFlags(QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemSendsGeometryChanges|QGraphicsItem.ItemIsFocusable); self.setAcceptHoverEvents(True)
        self.shadow_effect=QGraphicsDropShadowEffect(); self.shadow_effect.setBlurRadius(10); self.shadow_effect.setColor(QColor(0,0,0,60)); self.shadow_effect.setOffset(2.5,2.5); self.setGraphicsEffect(self.shadow_effect)
        self.is_py_sim_active=False; self.original_pen_for_py_sim_restore=self.pen()
    def paint(self, painter: QPainter, option, widget): # ... (Paint logic including py_sim_active unchanged) ...
        painter.setRenderHint(QPainter.Antialiasing); current_rect=self.rect(); border_radius=10; pen_to_use=self.pen()
        if self.is_py_sim_active: pen_to_use=QPen(COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH, Qt.DashLine)
        painter.setPen(pen_to_use); painter.setBrush(self.brush()); painter.drawRoundedRect(current_rect,border_radius,border_radius)
        painter.setPen(self._text_color); painter.setFont(self._font); text_rect=current_rect.adjusted(8,8,-8,-8); painter.drawText(text_rect,Qt.AlignCenter|Qt.TextWordWrap,self.text_label)
        if self.is_initial: # ... (initial marker drawing unchanged) ...
            m_r,l_l,m_c=6,18,Qt.black; s_m_c_x,s_m_c_y = current_rect.left()-l_l-m_r/2,current_rect.center().y(); painter.setBrush(m_c); painter.setPen(QPen(m_c,self._border_pen_width)); painter.drawEllipse(QPointF(s_m_c_x,s_m_c_y),m_r,m_r); l_s_p,l_e_p=QPointF(s_m_c_x+m_r,s_m_c_y),QPointF(current_rect.left(),s_m_c_y); painter.drawLine(l_s_p,l_e_p); a_s,a_r=8,0; a_p1=QPointF(l_e_p.x()-a_s*math.cos(a_r+math.pi/6),l_e_p.y()-a_s*math.sin(a_r+math.pi/6)); a_p2=QPointF(l_e_p.x()-a_s*math.cos(a_r-math.pi/6),l_e_p.y()-a_s*math.sin(a_r-math.pi/6)); painter.drawPolygon(QPolygonF([l_e_p,a_p1,a_p2]))
        if self.is_final: painter.setPen(QPen(self.border_color.darker(120),self._border_pen_width+0.5)); i_r=current_rect.adjusted(5,5,-5,-5); painter.setBrush(Qt.NoBrush); painter.drawRoundedRect(i_r,border_radius-3,border_radius-3)
        if self.isSelected() and not self.is_py_sim_active: s_p=QPen(QColor(COLOR_ITEM_STATE_SELECTION),self._border_pen_width+1,Qt.SolidLine); s_r=self.boundingRect().adjusted(-1,-1,1,1); painter.setPen(s_p); painter.setBrush(Qt.NoBrush); painter.drawRoundedRect(s_r,border_radius+1,border_radius+1)
    def set_py_sim_active_style(self,active:bool): # ... (Unchanged) ...
        if self.is_py_sim_active == active: return
        self.is_py_sim_active = active
        if active: self.original_pen_for_py_sim_restore=QPen(self.pen())
        else: self.setPen(self.original_pen_for_py_sim_restore)
        self.update()
    def itemChange(self,change,value): # ... (Unchanged) ...
        if change==QGraphicsItem.ItemPositionHasChanged and self.scene():self.scene().item_moved.emit(self)
        return super().itemChange(change,value)
    def get_data(self): # ... (Unchanged) ...
        return {'name':self.text_label,'x':self.x(),'y':self.y(),'width':self.rect().width(),'height':self.rect().height(),'is_initial':self.is_initial,'is_final':self.is_final,'color':self.base_color.name()if self.base_color else QColor(COLOR_ITEM_STATE_DEFAULT_BG).name(),'entry_action':self.entry_action,'during_action':self.during_action,'exit_action':self.exit_action,'description':self.description}
    def set_text(self,text): # ... (Unchanged) ...
        if self.text_label!=text:self.prepareGeometryChange();self.text_label=text;self.update()
    def set_properties(self,name,is_initial,is_final,color_hex=None,entry="",during="",exit_a="",desc=""): # ... (Unchanged logic ensuring original_pen_for_py_sim_restore is updated) ...
        changed=False; # ... (Property setting logic remains, critical part is below) ...
        if self.base_color != (new_base_color := QColor(color_hex) if color_hex else QColor(COLOR_ITEM_STATE_DEFAULT_BG)):
            self.base_color,self.border_color = new_base_color, (new_base_color.darker(120) if color_hex else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)); self.setBrush(self.base_color); new_pen=QPen(self.border_color,self._border_pen_width); self.setPen(new_pen)
            if not self.is_py_sim_active: self.original_pen_for_py_sim_restore = new_pen # Keep this logic
            changed=True
        # ... (rest of property checks) ...
        if changed: self.prepareGeometryChange(); self.update()
class GraphicsTransitionItem(QGraphicsPathItem): # ... (Class content unchanged) ...
    Type = QGraphicsItem.UserType+2; def type(self): return GraphicsTransitionItem.Type; # ...
class GraphicsCommentItem(QGraphicsTextItem): # ... (Class content unchanged) ...
    Type = QGraphicsItem.UserType+3; def type(self): return GraphicsCommentItem.Type; # ...

# --- Undo Commands --- (No changes needed here)
class AddItemCommand(QUndoCommand): # ... (Unchanged) ...
class RemoveItemsCommand(QUndoCommand): # ... (Unchanged) ...
class MoveItemsCommand(QUndoCommand): # ... (Unchanged) ...
class EditItemPropertiesCommand(QUndoCommand): # ... (Unchanged) ...

# --- Diagram Scene ---
class DiagramScene(QGraphicsScene):
    item_moved = pyqtSignal(QGraphicsItem); modifiedStatusChanged = pyqtSignal(bool) 
    def __init__(self, undo_stack, parent_window=None): # ... (Initialization unchanged) ...
        super().__init__(parent_window); self.parent_window=parent_window; self.setSceneRect(0,0,6000,4500); self.current_mode="select"
        self.transition_start_item=None; self.log_function=print; self.undo_stack=undo_stack; self._dirty=False; self._mouse_press_items_positions={}; self._temp_transition_line=None
        self.item_moved.connect(self._handle_item_moved); self.grid_size=20; self.grid_pen_light=QPen(QColor(COLOR_GRID_MINOR),0.7,Qt.DotLine); self.grid_pen_dark=QPen(QColor(COLOR_GRID_MAJOR),0.9,Qt.SolidLine); self.setBackgroundBrush(QColor(COLOR_BACKGROUND_LIGHT)); self.snap_to_grid_enabled=True
    # ... (Most DiagramScene methods unchanged: _update_connected_transitions, get_state_by_name, etc.)
    # Key change is ensuring mousePressEvent EXPECTS and USES QGraphicsSceneMouseEvent.pos() directly.
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent): # Expecting QGraphicsSceneMouseEvent
        # The 'event' here SHOULD be a QGraphicsSceneMouseEvent if ZoomableView.super().mousePressEvent is called
        print(f"DEBUG: DiagramScene mousePressEvent received event of type: {type(event)}")
        pos = event.scenePos() # DIRECTLY use scenePos for QGraphicsSceneMouseEvent

        items_at_pos = self.items(pos)
        top_item_at_pos = next((item for item in items_at_pos if isinstance(item, GraphicsStateItem)), None)
        if not top_item_at_pos:
            top_item_at_pos = next((item for item in items_at_pos if isinstance(item, (GraphicsCommentItem, GraphicsTransitionItem))), None)
            if not top_item_at_pos and items_at_pos:
                top_item_at_pos = items_at_pos[0]
    
        if event.button() == Qt.LeftButton:
            if self.current_mode == "state":
                grid_x = round(pos.x() / self.grid_size) * self.grid_size - 60
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
                    self.transition_start_item = None 
                    if self._temp_transition_line:
                        self.removeItem(self._temp_transition_line)
                        self._temp_transition_line = None
                    self.log_function("Transition drawing cancelled (clicked empty space/non-state).")
            elif self.current_mode == "select": 
                self._mouse_press_items_positions.clear()
                selected_movable = [item for item in self.selectedItems() 
                                    if item.flags() & QGraphicsItem.ItemIsMovable]
                for item in selected_movable:
                    self._mouse_press_items_positions[item] = item.pos()
                super().mousePressEvent(event) 
            else: # Should not happen if modes are limited
                super().mousePressEvent(event)

        elif event.button() == Qt.RightButton:
            if top_item_at_pos and isinstance(top_item_at_pos, (GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem)):
                if not top_item_at_pos.isSelected():
                    self.clearSelection()
                    top_item_at_pos.setSelected(True)
                self._show_context_menu(top_item_at_pos, event.screenPos()) # screenPos is fine for QGraphicsSceneMouseEvent
            else:
                self.clearSelection()
        else:
            super().mousePressEvent(event)
    # ... (rest of DiagramScene methods remain, such as mouseMoveEvent, mouseReleaseEvent, etc. - assumed they correctly use QGraphicsSceneMouseEvent if applicable)
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent): # Ensure type hint is correct
        if self.current_mode == "transition" and self.transition_start_item and self._temp_transition_line:
            center_start = self.transition_start_item.sceneBoundingRect().center(); self._temp_transition_line.setLine(QLineF(center_start, event.scenePos()))
        else: super().mouseMoveEvent(event)

# --- Zoomable Graphics View ---
class ZoomableView(QGraphicsView): # Ensure super().mousePressEvent IS CALLED FOR NON-PANNING EVENTS
    def __init__(self, scene, parent=None): # ... (Init unchanged) ...
        super().__init__(scene, parent); self.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform|QPainter.TextAntialiasing); self.setDragMode(QGraphicsView.RubberBandDrag); self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate); self.zoom_level=0; self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); self.setResizeAnchor(QGraphicsView.AnchorViewCenter); self._is_panning_with_space=False; self._is_panning_with_mouse_button=False; self._last_pan_point=QPoint()
    # ... (wheelEvent, keyPressEvent, keyReleaseEvent mostly unchanged, but review logic if scene interaction fails)
    def mousePressEvent(self, event: QMouseEvent): # Receives QMouseEvent from widget system
        if (event.button() == Qt.MiddleButton or
           (self._is_panning_with_space and event.button() == Qt.LeftButton)):
            self._last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            self._is_panning_with_mouse_button = True
            event.accept() 
        else:
            self._is_panning_with_mouse_button = False
            super().mousePressEvent(event) # ESSENTIAL FOR SCENE EVENTS
    # ... (mouseMoveEvent, mouseReleaseEvent, _restore_cursor_to_scene_mode unchanged from your last version) ...

# --- Dialogs ---
class StatePropertiesDialog(QDialog):
    def __init__(self, parent=None, current_properties=None, is_new_state=False):
        super().__init__(parent); self.setWindowTitle("State Properties")
        self.setWindowIcon(get_standard_icon(QStyle.SP_DialogApplyButton, "Props")) 
        self.setMinimumWidth(480); layout = QFormLayout(self); layout.setSpacing(8); layout.setContentsMargins(12,12,12,12)
        p = current_properties or {}; self.name_edit = QLineEdit(p.get('name', "StateName")); self.name_edit.setPlaceholderText("Unique name for the state")
        self.is_initial_cb = QCheckBox("Is Initial State"); self.is_initial_cb.setChecked(p.get('is_initial', False))
        self.is_final_cb = QCheckBox("Is Final State"); self.is_final_cb.setChecked(p.get('is_final', False))
        self.color_button = QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton"); self.current_color = QColor(p.get('color', COLOR_ITEM_STATE_DEFAULT_BG)); self._update_color_button_style(); self.color_button.clicked.connect(self._choose_color)
        self.entry_action_edit = QTextEdit(p.get('entry_action', "")); self.entry_action_edit.setFixedHeight(65); self.entry_action_edit.setPlaceholderText("MATLAB actions on entry...")
        entry_action_btn = self._create_insert_snippet_button(self.entry_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        self.during_action_edit = QTextEdit(p.get('during_action', "")); self.during_action_edit.setFixedHeight(65); self.during_action_edit.setPlaceholderText("MATLAB actions during state...")
        during_action_btn = self._create_insert_snippet_button(self.during_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        self.exit_action_edit = QTextEdit(p.get('exit_action', "")); self.exit_action_edit.setFixedHeight(65); self.exit_action_edit.setPlaceholderText("MATLAB actions on exit...")
        exit_action_btn = self._create_insert_snippet_button(self.exit_action_edit, MECHATRONICS_COMMON_ACTIONS, " Insert Action")
        self.description_edit = QTextEdit(p.get('description', "")); self.description_edit.setFixedHeight(75); self.description_edit.setPlaceholderText("Optional notes about this state")
        layout.addRow("Name:", self.name_edit); cb_layout = QHBoxLayout(); cb_layout.addWidget(self.is_initial_cb); cb_layout.addWidget(self.is_final_cb); cb_layout.addStretch(); layout.addRow("", cb_layout); layout.addRow("Color:", self.color_button)
        def add_field(lbl, te, btn): h=QHBoxLayout();h.setSpacing(5);h.addWidget(te,1);v=QVBoxLayout();v.addWidget(btn);v.addStretch();h.addLayout(v);layout.addRow(lbl,h)
        add_field("Entry Action:",self.entry_action_edit,entry_action_btn); add_field("During Action:",self.during_action_edit,during_action_btn); add_field("Exit Action:",self.exit_action_edit,exit_action_btn); layout.addRow("Description:",self.description_edit)
        btns = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); btns.accepted.connect(self.accept); btns.rejected.connect(self.reject); layout.addRow(btns)
        if is_new_state: self.name_edit.selectAll(); self.name_edit.setFocus()
    def _create_insert_snippet_button(self, target_widget: QTextEdit, snippets_dict: dict, button_text="Insert...", icon_size_px=14): # Takes QTextEdit
        button = QPushButton(button_text); button.setObjectName("SnippetButton"); button.setToolTip("Insert common snippets")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView, "Ins")) # Use the global get_standard_icon
        button.setIconSize(QSize(icon_size_px + 2, icon_size_px + 2)) 
        menu = QMenu(self)
        for name, snippet in snippets_dict.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, text_edit=target_widget, s=snippet: text_edit.insertPlainText(s + "\n"))
            menu.addAction(action)
        button.setMenu(menu); return button
    def _choose_color(self): # ... (Unchanged) ...
        color = QColorDialog.getColor(self.current_color, self, "Select State Color")
        if color.isValid(): self.current_color = color; self._update_color_button_style()
    def _update_color_button_style(self): # ... (Unchanged) ...
        l=self.current_color.lightnessF();tc=COLOR_TEXT_PRIMARY if l>0.5 else COLOR_TEXT_ON_ACCENT;self.color_button.setStyleSheet(f"background-color:{self.current_color.name()};color:{tc};")
    def get_properties(self): return {'name':self.name_edit.text().strip(),'is_initial':self.is_initial_cb.isChecked(),'is_final':self.is_final_cb.isChecked(),'color':self.current_color.name(),'entry_action':self.entry_action_edit.toPlainText().strip(),'during_action':self.during_action_edit.toPlainText().strip(),'exit_action':self.exit_action_edit.toPlainText().strip(),'description':self.description_edit.toPlainText().strip()}

class TransitionPropertiesDialog(QDialog): # ... (Corrected _choose_color; _create_insert_snippet_buttons calls corrected global icon func)
    def __init__(self, parent=None, current_properties=None, is_new_transition=False):
        super().__init__(parent); self.setWindowTitle("Transition Properties"); self.setWindowIcon(get_standard_icon(QStyle.SP_FileDialogInfoView, "Props")); self.setMinimumWidth(520)
        layout=QFormLayout(self);layout.setSpacing(8);layout.setContentsMargins(12,12,12,12); p=current_properties or {}
        self.event_edit=QLineEdit(p.get('event',"")); self.event_edit.setPlaceholderText("e.g., timeout, button_press(ID)"); event_btn=self._create_insert_snippet_button_lineedit(self.event_edit,MECHATRONICS_COMMON_EVENTS," Insert Event")
        self.condition_edit=QLineEdit(p.get('condition',"")); self.condition_edit.setPlaceholderText("e.g., var_x > 10 && flag_y == true"); condition_btn=self._create_insert_snippet_button_lineedit(self.condition_edit,MECHATRONICS_COMMON_CONDITIONS," Insert Condition")
        self.action_edit=QTextEdit(p.get('action',"")); self.action_edit.setPlaceholderText("MATLAB actions on transition..."); self.action_edit.setFixedHeight(65); action_btn=self._create_insert_snippet_button_qtextedit(self.action_edit,MECHATRONICS_COMMON_ACTIONS," Insert Action")
        self.color_button=QPushButton("Choose Color..."); self.color_button.setObjectName("ColorButton"); self.current_color=QColor(p.get('color',COLOR_ITEM_TRANSITION_DEFAULT)); self._update_color_button_style(); self.color_button.clicked.connect(self._choose_color)
        self.offset_perp_spin=QSpinBox(); self.offset_perp_spin.setRange(-1000,1000); self.offset_perp_spin.setSingleStep(10); self.offset_perp_spin.setValue(int(p.get('control_offset_x',0))); self.offset_perp_spin.setToolTip("Perpendicular bend (0 for straight).")
        self.offset_tang_spin=QSpinBox(); self.offset_tang_spin.setRange(-1000,1000); self.offset_tang_spin.setSingleStep(10); self.offset_tang_spin.setValue(int(p.get('control_offset_y',0))); self.offset_tang_spin.setToolTip("Tangential shift of midpoint.")
        self.description_edit=QTextEdit(p.get('description',"")); self.description_edit.setFixedHeight(75); self.description_edit.setPlaceholderText("Optional notes")
        def add_f_w_b(l,ew,b): h=QHBoxLayout();h.setSpacing(5);h.addWidget(ew,1);v=QVBoxLayout();v.addWidget(b);v.addStretch();h.addLayout(v);layout.addRow(l,h)
        add_f_w_b("Event Trigger:",self.event_edit,event_btn); add_f_w_b("Condition (Guard):",self.condition_edit,condition_btn); add_f_w_b("Transition Action:",self.action_edit,action_btn)
        layout.addRow("Color:",self.color_button); cv_l=QHBoxLayout();cv_l.addWidget(QLabel("Bend(Perp):"));cv_l.addWidget(self.offset_perp_spin);cv_l.addSpacing(10);cv_l.addWidget(QLabel("Mid Shift(Tang):"));cv_l.addWidget(self.offset_tang_spin);cv_l.addStretch();layout.addRow("Curve Shape:",cv_l); layout.addRow("Description:",self.description_edit)
        btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); btns.accepted.connect(self.accept);btns.rejected.connect(self.reject);layout.addRow(btns)
        if is_new_transition:self.event_edit.setFocus()
    def _create_insert_snippet_button_lineedit(self, target_line_edit:QLineEdit, snippets_dict:dict, button_text="Insert...", icon_size_px=14):
        button=QPushButton(button_text); button.setObjectName("SnippetButton"); button.setToolTip("Insert common snippets.")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins")); button.setIconSize(QSize(icon_size_px+2,icon_size_px+2))
        menu=QMenu(self);
        for n,s in snippets_dict.items(): a=QAction(n,self); a.triggered.connect(lambda c=False,le=target_line_edit,sn=s:(lambda l,t: (l.setText(l.text()[:l.cursorPosition()]+t+l.text()[l.cursorPosition():]),l.setCursorPosition(l.cursorPosition()+len(t)-(len(l.text())-(l.cursorPosition()+len(t))))))(le,sn)); menu.addAction(a) # original complex lambda
        button.setMenu(menu); return button
    def _create_insert_snippet_button_qtextedit(self, target_text_edit:QTextEdit, snippets_dict:dict, button_text="Insert...", icon_size_px=14):
        button=QPushButton(button_text);button.setObjectName("SnippetButton");button.setToolTip("Insert common snippets.")
        button.setIcon(get_standard_icon(QStyle.SP_FileDialogContentsView,"Ins"));button.setIconSize(QSize(icon_size_px+2,icon_size_px+2))
        menu=QMenu(self)
        for n,s in snippets_dict.items():a=QAction(n,self);a.triggered.connect(lambda c=False,te=target_text_edit,sn=s:te.insertPlainText(sn+"\n"));menu.addAction(a)
        button.setMenu(menu);return button
    def _choose_color(self): # CORRECTED
        color = QColorDialog.getColor(self.current_color, self, "Select Transition Color")
        if color.isValid(): self.current_color = color; self._update_color_button_style()
    def _update_color_button_style(self): l=self.current_color.lightnessF();tc=COLOR_TEXT_PRIMARY if l>0.5 else COLOR_TEXT_ON_ACCENT;self.color_button.setStyleSheet(f"background-color:{self.current_color.name()};color:{tc};")
    def get_properties(self): return {'event':self.event_edit.text().strip(),'condition':self.condition_edit.text().strip(),'action':self.action_edit.toPlainText().strip(),'color':self.current_color.name(),'control_offset_x':self.offset_perp_spin.value(),'control_offset_y':self.offset_tang_spin.value(),'description':self.description_edit.toPlainText().strip()}
class CommentPropertiesDialog(QDialog): # ... (Unchanged) ...
class MatlabSettingsDialog(QDialog): # ... (Unchanged - assumed get_standard_icon calls here were already correct) ...

# --- Main Window --- (Ensure its _create_actions uses the global get_standard_icon correctly)
class MainWindow(QMainWindow):
    def __init__(self): # ... (Init unchanged) ...
        super().__init__();self.current_file_path=None;self.last_generated_model_path=None;self.matlab_connection=MatlabConnection();self.undo_stack=QUndoStack(self)
        self.scene=DiagramScene(self.undo_stack,self);self.scene.set_log_function(self.log_message);self.scene.modifiedStatusChanged.connect(self.setWindowModified);self.scene.modifiedStatusChanged.connect(self._update_window_title)
        self.py_fsm_engine:FSMSimulator|None=None;self.py_sim_active=False;self._py_sim_currently_highlighted_item:GraphicsStateItem|None=None
        self.init_ui()
        self.status_label.setObjectName("StatusLabel");self.matlab_status_label.setObjectName("MatlabStatusLabel");self.py_sim_status_label.setObjectName("PySimStatusLabel")
        self._update_matlab_status_display(False,"Initializing. Configure MATLAB settings or attempt auto-detect.");self._update_py_sim_status_display()
        self.matlab_connection.connectionStatusChanged.connect(self._update_matlab_status_display);self.matlab_connection.simulationFinished.connect(self._handle_matlab_modelgen_or_sim_finished);self.matlab_connection.codeGenerationFinished.connect(self._handle_matlab_codegen_finished)
        self._update_window_title();self.on_new_file(silent=True);self.scene.selectionChanged.connect(self._update_properties_dock);self._update_properties_dock();self._update_py_simulation_actions_enabled_state()
    # ... (All other MainWindow methods, Python Sim methods, event handlers etc., unchanged from your last provided version with PySim integration)

# if __name__ == '__main__': (Unchanged)
# ... (The rest of your file) ...

if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app_dir = os.path.dirname(os.path.abspath(__file__))
    dependencies_dir = os.path.join(app_dir, "dependencies", "icons") # For combo box arrow, etc.
    if not os.path.exists(dependencies_dir): os.makedirs(dependencies_dir, exist_ok=True)
    # If you have an arrow_down.png, ensure it's in ./dependencies/icons/ for the QSS

    app = QApplication(sys.argv)
    # Set a consistent application style if desired, can help with icon rendering
    # app.setStyle("Fusion") # Or "Windows", "WindowsVista" 
    app.setStyleSheet(STYLE_SHEET_GLOBAL) # Apply global QSS
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())