
# bsm_designer_project/ui_py_simulation_manager.py
import html
from PyQt5.QtWidgets import (
    QLabel, QTextEdit, QComboBox, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QAction, QMessageBox, QGroupBox, QHBoxLayout, QVBoxLayout,
    QToolButton, QHeaderView, QAbstractItemView, QWidget, QStyle
)
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal, QSize, Qt

from fsm_simulator import FSMSimulator, FSMError
from graphics_items import GraphicsStateItem # For type hint
from utils import get_standard_icon 
from config import COLOR_ACCENT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_PY_SIM_STATE_ACTIVE

import logging
logger = logging.getLogger(__name__)

class PySimulationUIManager(QObject):
    simulationStateChanged = pyqtSignal(bool) 
    requestGlobalUIEnable = pyqtSignal(bool)  

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window 

        self.py_sim_start_btn: QToolButton = None
        self.py_sim_stop_btn: QToolButton = None
        self.py_sim_reset_btn: QToolButton = None
        self.py_sim_step_btn: QPushButton = None
        self.py_sim_event_combo: QComboBox = None
        self.py_sim_event_name_edit: QLineEdit = None
        self.py_sim_trigger_event_btn: QPushButton = None
        self.py_sim_current_state_label: QLabel = None
        self.py_sim_variables_table: QTableWidget = None
        self.py_sim_action_log_output: QTextEdit = None
        self._py_sim_currently_highlighted_item: GraphicsStateItem | None = None
        self._connect_actions_to_manager_slots()

    def _connect_actions_to_manager_slots(self):
        logger.debug("PySimUI: Connecting actions to manager slots...")
        if hasattr(self.mw, 'start_py_sim_action'):
            self.mw.start_py_sim_action.triggered.connect(self.on_start_py_simulation)
            logger.debug("PySimUI: start_py_sim_action connected.")
        else:
            logger.warning("PySimUI: MainWindow missing start_py_sim_action.")

        if hasattr(self.mw, 'stop_py_sim_action'):
            self.mw.stop_py_sim_action.triggered.connect(lambda: self.on_stop_py_simulation(silent=False))
            logger.debug("PySimUI: stop_py_sim_action connected.")
        else:
            logger.warning("PySimUI: MainWindow missing stop_py_sim_action.")

        if hasattr(self.mw, 'reset_py_sim_action'):
            self.mw.reset_py_sim_action.triggered.connect(self.on_reset_py_simulation)
            logger.debug("PySimUI: reset_py_sim_action connected.")
        else:
            logger.warning("PySimUI: MainWindow missing reset_py_sim_action.")


    def create_dock_widget_contents(self) -> QWidget:
        py_sim_widget = QWidget()
        py_sim_layout = QVBoxLayout(py_sim_widget)
        py_sim_layout.setContentsMargins(5, 5, 5, 5); py_sim_layout.setSpacing(5)

        controls_group = QGroupBox("Controls")
        controls_layout = QHBoxLayout(); controls_layout.setSpacing(5)
        
        self.py_sim_start_btn = QToolButton()
        if hasattr(self.mw, 'start_py_sim_action'): self.py_sim_start_btn.setDefaultAction(self.mw.start_py_sim_action)
        else: 
            self.py_sim_start_btn.setText("Start")
            self.py_sim_start_btn.setIcon(get_standard_icon(QStyle.SP_MediaPlay, "Py▶"))
            self.py_sim_start_btn.clicked.connect(self.on_start_py_simulation)

        self.py_sim_stop_btn = QToolButton()
        if hasattr(self.mw, 'stop_py_sim_action'): self.py_sim_stop_btn.setDefaultAction(self.mw.stop_py_sim_action)
        else: 
            self.py_sim_stop_btn.setText("Stop")
            self.py_sim_stop_btn.setIcon(get_standard_icon(QStyle.SP_MediaStop, "Py■"))
            self.py_sim_stop_btn.clicked.connect(lambda: self.on_stop_py_simulation(silent=False))

        self.py_sim_reset_btn = QToolButton()
        if hasattr(self.mw, 'reset_py_sim_action'): self.py_sim_reset_btn.setDefaultAction(self.mw.reset_py_sim_action)
        else: 
            self.py_sim_reset_btn.setText("Reset")
            self.py_sim_reset_btn.setIcon(get_standard_icon(QStyle.SP_MediaSkipBackward, "Py«"))
            self.py_sim_reset_btn.clicked.connect(self.on_reset_py_simulation)

        self.py_sim_step_btn = QPushButton("Step")
        self.py_sim_step_btn.setIcon(get_standard_icon(QStyle.SP_MediaSeekForward, "Step"))
        self.py_sim_step_btn.clicked.connect(self.on_step_py_simulation)

        for btn in [self.py_sim_start_btn, self.py_sim_stop_btn, self.py_sim_reset_btn]:
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly); btn.setIconSize(QSize(18, 18)); controls_layout.addWidget(btn)
        controls_layout.addWidget(self.py_sim_step_btn); controls_layout.addStretch()
        controls_group.setLayout(controls_layout); py_sim_layout.addWidget(controls_group)

        event_group = QGroupBox("Event Trigger")
        event_layout = QHBoxLayout(); event_layout.setSpacing(5)
        self.py_sim_event_combo = QComboBox(); self.py_sim_event_combo.addItem("None (Internal Step)"); self.py_sim_event_combo.setEditable(False)
        event_layout.addWidget(self.py_sim_event_combo, 1)
        self.py_sim_event_name_edit = QLineEdit(); self.py_sim_event_name_edit.setPlaceholderText("Custom event name")
        event_layout.addWidget(self.py_sim_event_name_edit, 1)
        
        self.py_sim_trigger_event_btn = QPushButton("Trigger")
        self.py_sim_trigger_event_btn.setIcon(get_standard_icon(QStyle.SP_MediaPlay, "Trg"))
        self.py_sim_trigger_event_btn.clicked.connect(self.on_trigger_py_event)
        event_layout.addWidget(self.py_sim_trigger_event_btn)
        event_group.setLayout(event_layout); py_sim_layout.addWidget(event_group)

        state_group = QGroupBox("Current State")
        state_layout = QVBoxLayout()
        self.py_sim_current_state_label = QLabel("<i>Not Running</i>"); self.py_sim_current_state_label.setStyleSheet("font-size: 9pt; padding: 3px;")
        state_layout.addWidget(self.py_sim_current_state_label)
        state_group.setLayout(state_layout); py_sim_layout.addWidget(state_group)

        variables_group = QGroupBox("Variables")
        variables_layout = QVBoxLayout()
        self.py_sim_variables_table = QTableWidget(); self.py_sim_variables_table.setRowCount(0); self.py_sim_variables_table.setColumnCount(2)
        self.py_sim_variables_table.setHorizontalHeaderLabels(["Name", "Value"])
        self.py_sim_variables_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.py_sim_variables_table.setSelectionMode(QAbstractItemView.NoSelection); self.py_sim_variables_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        variables_layout.addWidget(self.py_sim_variables_table)
        variables_group.setLayout(variables_layout); py_sim_layout.addWidget(variables_group)

        log_group = QGroupBox("Action Log")
        log_layout = QVBoxLayout()
        self.py_sim_action_log_output = QTextEdit(); self.py_sim_action_log_output.setReadOnly(True)
        self.py_sim_action_log_output.setObjectName("PySimActionLog") 
        self.py_sim_action_log_output.setHtml("<i>Simulation log will appear here...</i>")
        log_layout.addWidget(self.py_sim_action_log_output)
        log_group.setLayout(log_layout); py_sim_layout.addWidget(log_group, 1)
        
        self._update_internal_controls_enabled_state() 
        return py_sim_widget
    
    def _update_internal_controls_enabled_state(self):
        is_matlab_op_running = False
        if hasattr(self.mw, 'progress_bar') and self.mw.progress_bar: 
            is_matlab_op_running = self.mw.progress_bar.isVisible()
            
        sim_active = self.mw.py_sim_active 

        sim_controls_enabled = sim_active and not is_matlab_op_running
        
        if self.py_sim_start_btn: self.py_sim_start_btn.setEnabled(not sim_active and not is_matlab_op_running)
        if self.py_sim_stop_btn: self.py_sim_stop_btn.setEnabled(sim_active and not is_matlab_op_running)
        if self.py_sim_reset_btn: self.py_sim_reset_btn.setEnabled(sim_active and not is_matlab_op_running)
        
        if self.py_sim_step_btn: self.py_sim_step_btn.setEnabled(sim_controls_enabled)
        if self.py_sim_event_name_edit: self.py_sim_event_name_edit.setEnabled(sim_controls_enabled)
        if self.py_sim_trigger_event_btn: self.py_sim_trigger_event_btn.setEnabled(sim_controls_enabled)
        if self.py_sim_event_combo: self.py_sim_event_combo.setEnabled(sim_controls_enabled)


    def _set_simulation_active_state(self, is_running: bool):
        self.mw.py_sim_active = is_running 
        self.simulationStateChanged.emit(is_running) 
        self.requestGlobalUIEnable.emit(not is_running) 
        self._update_internal_controls_enabled_state() 

    def _highlight_sim_active_state(self, state_name_to_highlight: str | None):
        if self._py_sim_currently_highlighted_item:
            self._py_sim_currently_highlighted_item.set_py_sim_active_style(False)
            self._py_sim_currently_highlighted_item = None

        if state_name_to_highlight and self.mw.py_fsm_engine: 
            top_level_active_state_id = None
            if self.mw.py_fsm_engine.sm and self.mw.py_fsm_engine.sm.current_state:
                top_level_active_state_id = self.mw.py_fsm_engine.sm.current_state.id
            
            if top_level_active_state_id:
                for item in self.mw.scene.items(): 
                    if isinstance(item, GraphicsStateItem) and item.text_label == top_level_active_state_id:
                        logger.debug("PySimUI: Highlighting top-level active state '%s' (full hierarchical: '%s')", top_level_active_state_id, state_name_to_highlight)
                        item.set_py_sim_active_style(True)
                        self._py_sim_currently_highlighted_item = item
                        if self.mw.view: 
                             if hasattr(self.mw.view, 'ensureVisible') and callable(self.mw.view.ensureVisible):
                                if not self.mw.view.ensureVisible(item, 50, 50): 
                                    self.mw.view.centerOn(item)
                             else: 
                                self.mw.view.centerOn(item)
                        break
        self.mw.scene.update()

    def _highlight_sim_taken_transition(self, transition_label_or_id: str | None):
        # Placeholder: Future implementation could highlight the path of the last taken transition.
        # For now, just ensure the scene updates if any visual state needs to be cleared/reset.
        self.mw.scene.update() 

    def update_dock_ui_contents(self):
        if not self.mw.py_fsm_engine or not self.mw.py_sim_active: 
            if self.py_sim_current_state_label: self.py_sim_current_state_label.setText("<i>Not Running</i>")
            if self.py_sim_variables_table: self.py_sim_variables_table.setRowCount(0)
            self._highlight_sim_active_state(None); self._highlight_sim_taken_transition(None)
            if self.py_sim_event_combo: self.py_sim_event_combo.clear(); self.py_sim_event_combo.addItem("None (Internal Step)")
            self._update_internal_controls_enabled_state()
            return

        hierarchical_state_name = self.mw.py_fsm_engine.get_current_state_name()
        if self.py_sim_current_state_label: self.py_sim_current_state_label.setText(f"<b>{html.escape(hierarchical_state_name or 'N/A')}</b>")
        self._highlight_sim_active_state(hierarchical_state_name)

        all_vars = []
        if self.mw.py_fsm_engine:
            all_vars.extend([(k, str(v)) for k, v in sorted(self.mw.py_fsm_engine.get_variables().items())])
            if self.mw.py_fsm_engine.active_sub_simulator: # If sub-FSM is active
                all_vars.extend([(f"[SUB] {k}", str(v)) for k, v in sorted(self.mw.py_fsm_engine.active_sub_simulator.get_variables().items())])
        
        if self.py_sim_variables_table:
            self.py_sim_variables_table.setRowCount(len(all_vars))
            for r, (name, val) in enumerate(all_vars):
                self.py_sim_variables_table.setItem(r, 0, QTableWidgetItem(name))
                self.py_sim_variables_table.setItem(r, 1, QTableWidgetItem(val))
            self.py_sim_variables_table.resizeColumnsToContents()

        if self.py_sim_event_combo:
            current_text = self.py_sim_event_combo.currentText()
            self.py_sim_event_combo.clear(); self.py_sim_event_combo.addItem("None (Internal Step)")
            
            possible_events_set = set()
            # Get events from active sub-simulator if it exists and is running
            if self.mw.py_fsm_engine.active_sub_simulator and self.mw.py_fsm_engine.active_sub_simulator.sm:
                possible_events_set.update(self.mw.py_fsm_engine.active_sub_simulator.get_possible_events_from_current_state())
            
            # Get events from the main simulator (or top-level if no sub-simulator is active)
            possible_events_set.update(self.mw.py_fsm_engine.get_possible_events_from_current_state())
            
            possible_events = sorted(list(possible_events_set))

            if possible_events: self.py_sim_event_combo.addItems(possible_events)
            
            idx = self.py_sim_event_combo.findText(current_text)
            # If current_text not found, default to "None" (idx 0) or first actual event if "None" isn't desired
            self.py_sim_event_combo.setCurrentIndex(idx if idx != -1 else (0 if not possible_events else self.py_sim_event_combo.count() - len(possible_events)))
        
        self._update_internal_controls_enabled_state()

    def append_to_action_log(self, log_entries: list[str]):
        if not self.py_sim_action_log_output: return
        
        # Determine color for the main FSM state for context in logs
        accent_color_name = COLOR_ACCENT_PRIMARY.name() if isinstance(COLOR_ACCENT_PRIMARY, QColor) else COLOR_ACCENT_PRIMARY
        
        for entry in log_entries:
            cleaned_entry = html.escape(entry)
            # Basic color coding based on keywords
            if "[Condition]" in entry or "[Eval Error]" in entry or "ERROR" in entry.upper() or "SecurityError" in entry:
                cleaned_entry = f"<span style='color:red; font-weight:bold;'>{cleaned_entry}</span>"
            elif "[Safety Check Failed]" in entry or "[Action Blocked]" in entry or "[Condition Blocked]" in entry:
                cleaned_entry = f"<span style='color:orange; font-weight:bold;'>{cleaned_entry}</span>"
            elif "Transitioned from" in entry or "Reset to state" in entry or "Simulation started" in entry or "Entering state" in entry or "Exiting state" in entry:
                cleaned_entry = f"<span style='color:{accent_color_name}; font-weight:bold;'>{cleaned_entry}</span>"
            elif "No eligible transition" in entry or "event is not allowed" in entry:
                cleaned_entry = f"<span style='color:{COLOR_TEXT_SECONDARY};'>{cleaned_entry}</span>"
            
            self.py_sim_action_log_output.append(cleaned_entry)
        
        self.py_sim_action_log_output.verticalScrollBar().setValue(self.py_sim_action_log_output.verticalScrollBar().maximum())
        
        # Log the last significant entry to the main logger
        if log_entries and any(kw in log_entries[-1] for kw in ["Transitioned", "ERROR", "Reset", "started", "stopped", "SecurityError", "HALTED"]):
            logger.info("PySimUI Log: %s", log_entries[-1].split('\n')[0][:100]) # Log first 100 chars of last significant log

    @pyqtSlot()
    def on_start_py_simulation(self):
        logger.info("PySimUI: on_start_py_simulation CALLED!")
        if self.mw.py_sim_active:
            logger.warning("PySimUI: Simulation already active, returning.")
            QMessageBox.information(self.mw, "Simulation Active", "Python simulation is already running.")
            return
        
        if self.mw.scene.is_dirty():
            logger.debug("PySimUI: Diagram is dirty, prompting user.")
            reply = QMessageBox.question(self.mw, "Unsaved Changes", 
                                         "The diagram has unsaved changes. Start simulation anyway?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No:
                logger.info("PySimUI: User chose not to start sim due to unsaved changes.")
                return
                
        diagram_data = self.mw.scene.get_diagram_data()
        logger.debug(f"PySimUI: Diagram data for simulation - States: {len(diagram_data.get('states', []))}, Transitions: {len(diagram_data.get('transitions', []))}")

        if not diagram_data.get('states'):
            logger.warning("PySimUI: No states found in diagram_data for simulation.")
            QMessageBox.warning(self.mw, "Empty Diagram", "Cannot start simulation: The diagram has no states.")
            return

        try:
            logger.info("PySimUI: Attempting to instantiate FSMSimulator...")
            self.mw.py_fsm_engine = FSMSimulator(diagram_data['states'], diagram_data['transitions'], halt_on_action_error=True)
            logger.info("PySimUI: FSMSimulator instantiated successfully.")
            self._set_simulation_active_state(True) 
            if self.py_sim_action_log_output: self.py_sim_action_log_output.clear(); self.py_sim_action_log_output.setHtml("<i>Simulation log will appear here...</i>")
            
            initial_log = ["Python FSM Simulation started."] + self.mw.py_fsm_engine.get_last_executed_actions_log()
            self.append_to_action_log(initial_log)
            self.update_dock_ui_contents()
        except FSMError as e:
            logger.error(f"PySimUI: FSMError during FSMSimulator instantiation: {e}", exc_info=True)
            QMessageBox.critical(self.mw, "FSM Initialization Error", f"Failed to start Python FSM simulation:\n{e}")
            self.append_to_action_log([f"ERROR Starting Sim: {e}"])
            self.mw.py_fsm_engine = None; self._set_simulation_active_state(False)
        except Exception as e: 
            logger.error(f"PySimUI: Unexpected error during FSMSimulator instantiation: {e}", exc_info=True)
            QMessageBox.critical(self.mw, "Simulation Start Error", f"An unexpected error occurred while starting the simulation:\n{type(e).__name__}: {e}")
            self.append_to_action_log([f"UNEXPECTED ERROR Starting Sim: {e}"])
            self.mw.py_fsm_engine = None; self._set_simulation_active_state(False)


    @pyqtSlot(bool)
    def on_stop_py_simulation(self, silent=False):
        logger.info(f"PySimUI: on_stop_py_simulation CALLED (silent={silent}). Current sim_active: {self.mw.py_sim_active}")
        if not self.mw.py_sim_active: 
            logger.info("PySimUI: Stop called but simulation not active.")
            return 
        
        self._highlight_sim_active_state(None) 
        self._highlight_sim_taken_transition(None) 

        self.mw.py_fsm_engine = None 
        self._set_simulation_active_state(False) 
        
        self.update_dock_ui_contents() 
        if not silent:
            self.append_to_action_log(["Python FSM Simulation stopped."])
            logger.info("PySimUI: Simulation stopped by user.")


    @pyqtSlot()
    def on_reset_py_simulation(self):
        logger.info("PySimUI: on_reset_py_simulation CALLED!")
        if not self.mw.py_fsm_engine or not self.mw.py_sim_active:
            logger.warning("PySimUI: Reset called but simulation not active or engine not available.")
            QMessageBox.warning(self.mw, "Simulation Not Active", "Python simulation is not running.")
            return
        try:
            self.mw.py_fsm_engine.reset()
            if self.py_sim_action_log_output: 
                self.py_sim_action_log_output.append("<hr><i style='color:grey;'>Simulation Reset</i><hr>")
            self.append_to_action_log(self.mw.py_fsm_engine.get_last_executed_actions_log())
            self.update_dock_ui_contents(); self._highlight_sim_taken_transition(None) 
        except FSMError as e:
            logger.error(f"PySimUI: FSMError during reset: {e}", exc_info=True)
            QMessageBox.critical(self.mw, "FSM Reset Error", f"Failed to reset simulation:\n{e}")
            self.append_to_action_log([f"ERROR DURING RESET: {e}"])
        except Exception as e:
            logger.error(f"PySimUI: Unexpected error during reset: {e}", exc_info=True)
            QMessageBox.critical(self.mw, "Reset Error", f"An unexpected error occurred during reset:\n{type(e).__name__}: {e}")
            self.append_to_action_log([f"UNEXPECTED ERROR DURING RESET: {e}"])


    @pyqtSlot()
    def on_step_py_simulation(self):
        logger.debug("PySimUI: on_step_py_simulation CALLED!")
        if not self.mw.py_fsm_engine or not self.mw.py_sim_active:
            QMessageBox.warning(self.mw, "Simulation Not Active", "Python simulation is not running.")
            return
        try:
            _, log_entries = self.mw.py_fsm_engine.step(event_name=None)
            self.append_to_action_log(log_entries); self.update_dock_ui_contents(); self._highlight_sim_taken_transition(None)
            if self.mw.py_fsm_engine.simulation_halted_flag:
                self.append_to_action_log(["[HALTED] Simulation halted due to an error. Please Reset."]); QMessageBox.warning(self.mw, "Simulation Halted", "The simulation has been halted due to an FSM action error. Please reset.")
        except FSMError as e: 
            QMessageBox.warning(self.mw, "Simulation Step Error", str(e))
            self.append_to_action_log([f"ERROR DURING STEP: {e}"]); logger.error("PySimUI: Step FSMError: %s", e, exc_info=True)
            if self.mw.py_fsm_engine and self.mw.py_fsm_engine.simulation_halted_flag: self.append_to_action_log(["[HALTED] Simulation halted. Please Reset."])
        except Exception as e:
            QMessageBox.critical(self.mw, "Simulation Step Error", f"An unexpected error occurred during step:\n{type(e).__name__}: {e}")
            self.append_to_action_log([f"UNEXPECTED ERROR DURING STEP: {e}"]); logger.error("PySimUI: Unexpected Step Error:", exc_info=True)

    @pyqtSlot()
    def on_trigger_py_event(self):
        logger.debug("PySimUI: on_trigger_py_event CALLED!")
        if not self.mw.py_fsm_engine or not self.mw.py_sim_active:
            QMessageBox.warning(self.mw, "Simulation Not Active", "Python simulation is not running.")
            return
        
        event_name_combo = self.py_sim_event_combo.currentText() if self.py_sim_event_combo else ""
        event_name_edit = self.py_sim_event_name_edit.text().strip() if self.py_sim_event_name_edit else ""
        
        event_to_trigger = event_name_edit if event_name_edit else (event_name_combo if event_name_combo != "None (Internal Step)" else None)
        logger.debug(f"PySimUI: Event to trigger: '{event_to_trigger}' (from edit: '{event_name_edit}', from combo: '{event_name_combo}')")


        if not event_to_trigger:
            self.on_step_py_simulation()
            return

        try:
            _, log_entries = self.mw.py_fsm_engine.step(event_name=event_to_trigger)
            self.append_to_action_log(log_entries); self.update_dock_ui_contents()
            if self.py_sim_event_name_edit: self.py_sim_event_name_edit.clear()
            self._highlight_sim_taken_transition(None)
            if self.mw.py_fsm_engine.simulation_halted_flag:
                self.append_to_action_log(["[HALTED] Simulation halted due to an error. Please Reset."]); QMessageBox.warning(self.mw, "Simulation Halted", "The simulation has been halted due to an FSM action error. Please reset.")
        except FSMError as e:
            QMessageBox.warning(self.mw, "Simulation Event Error", str(e))
            self.append_to_action_log([f"ERROR EVENT '{html.escape(event_to_trigger)}': {e}"]); logger.error("PySimUI: Event FSMError for '%s': %s", event_to_trigger, e, exc_info=True)
            if self.mw.py_fsm_engine and self.mw.py_fsm_engine.simulation_halted_flag: self.append_to_action_log(["[HALTED] Simulation halted. Please Reset."])
        except Exception as e:
            QMessageBox.critical(self.mw, "Simulation Event Error", f"An unexpected error occurred on event '{html.escape(event_to_trigger)}':\n{type(e).__name__}: {e}")
            self.append_to_action_log([f"UNEXPECTED ERROR EVENT '{html.escape(event_to_trigger)}': {e}"]); logger.error("PySimUI: Unexpected Event Error for '%s':", event_to_trigger, exc_info=True)
