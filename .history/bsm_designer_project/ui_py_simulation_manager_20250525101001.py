# bsm_designer_project/ui_py_simulation_manager.py
import html
from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QTextEdit, QLineEdit, QFormLayout
)
from fsm_simulator import FSMSimulator, FSMError
import logging

logger = logging.getLogger(__name__)

class PySimulationUIManager(QObject):
    # Define signals
    simulationStateChanged = pyqtSignal(bool)  # Signal for sim running state changes
    requestGlobalUIEnable = pyqtSignal(bool)   # Signal to request main window UI enable/disable

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.sim_log_output = None
        self.event_input = None
        self.step_button = None
        self.trigger_button = None
        self._connect_actions_to_manager_slots()

    def _connect_actions_to_manager_slots(self):
        """Connect MainWindow's actions to this manager's slots"""
        self.mw.start_py_sim_action.triggered.connect(self.on_start_py_simulation)
        self.mw.stop_py_sim_action.triggered.connect(self.on_stop_py_simulation)
        self.mw.reset_py_sim_action.triggered.connect(self.on_reset_py_simulation)

    def create_dock_widget_contents(self) -> QWidget:
        """Create and return the widget for the Python Simulation dock"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # Controls layout
        controls_layout = QHBoxLayout()
        self.step_button = QPushButton("Step")
        self.step_button.clicked.connect(self.on_step_py_simulation)
        self.step_button.setEnabled(False)
        
        # Event input
        event_layout = QFormLayout()
        self.event_input = QLineEdit()
        self.event_input.setPlaceholderText("Event name...")
        self.event_input.returnPressed.connect(self.on_trigger_py_event)
        self.trigger_button = QPushButton("Trigger")
        self.trigger_button.clicked.connect(self.on_trigger_py_event)
        event_layout.addRow("Event:", self.event_input)
        
        controls_layout.addWidget(self.step_button)
        controls_layout.addWidget(self.trigger_button)
        
        # Log output
        self.sim_log_output = QTextEdit()
        self.sim_log_output.setReadOnly(True)
        self.sim_log_output.setPlaceholderText("Simulation log will appear here...")
        
        layout.addLayout(controls_layout)
        layout.addLayout(event_layout)
        layout.addWidget(self.sim_log_output)
        
        return widget

    def on_start_py_simulation(self):
        """Start the Python simulation"""
        try:
            self.mw.py_fsm_engine = FSMSimulator(
                self.mw.scene.get_diagram_data()['states'],
                self.mw.scene.get_diagram_data()['transitions']
            )
            self.simulationStateChanged.emit(True)
            self.requestGlobalUIEnable.emit(False)
            self._update_internal_controls_enabled_state()
            self.append_to_action_log(["Simulation started."])
            self.update_dock_ui_contents()
        except FSMError as e:
            self.append_to_action_log([f"ERROR: {str(e)}"])
            self.on_stop_py_simulation()

    def on_stop_py_simulation(self, silent=False):
        """Stop the Python simulation"""
        self.mw.py_fsm_engine = None
        self.simulationStateChanged.emit(False)
        self.requestGlobalUIEnable.emit(True)
        self._update_internal_controls_enabled_state()
        if not silent:
            self.append_to_action_log(["Simulation stopped."])
        self.update_dock_ui_contents()

    def on_reset_py_simulation(self):
        """Reset the Python simulation"""
        if self.mw.py_fsm_engine:
            try:
                self.mw.py_fsm_engine.reset()
                self.append_to_action_log(["Simulation reset."])
                self.update_dock_ui_contents()
            except FSMError as e:
                self.append_to_action_log([f"Reset ERROR: {str(e)}"])
                self.on_stop_py_simulation()

    def on_step_py_simulation(self):
        """Execute one step in the simulation"""
        if self.mw.py_fsm_engine:
            try:
                self.mw.py_fsm_engine.step()
                self.update_dock_ui_contents()
            except FSMError as e:
                self.append_to_action_log([f"Step ERROR: {str(e)}"])
                self.on_stop_py_simulation()

    def on_trigger_py_event(self):
        """Trigger an event in the simulation"""
        if not self.mw.py_fsm_engine or not self.event_input:
            return
            
        event = self.event_input.text().strip()
        if not event:
            return
            
        try:
            self.mw.py_fsm_engine.trigger_event(event)
            self.update_dock_ui_contents()
            self.event_input.clear()
        except FSMError as e:
            self.append_to_action_log([f"Event ERROR: {str(e)}"])
            self.on_stop_py_simulation()

    def _update_internal_controls_enabled_state(self):
        """Update the enabled state of internal controls"""
        sim_active = bool(self.mw.py_fsm_engine)
        if hasattr(self, 'step_button'):
            self.step_button.setEnabled(sim_active)
        if hasattr(self, 'trigger_button'):
            self.trigger_button.setEnabled(sim_active)
        if hasattr(self, 'event_input'):
            self.event_input.setEnabled(sim_active)

    def update_dock_ui_contents(self):
        """Update the dock widget contents with current simulation state"""
        if not self.mw.py_fsm_engine:
            return
        
        try:
            current_state = self.mw.py_fsm_engine.get_current_state_name()
            variables = self.mw.py_fsm_engine.get_variables()
            log = self.mw.py_fsm_engine.get_last_executed_actions_log()
            
            if log:
                self.append_to_action_log(log)
                
            # Update scene visualization
            self._highlight_sim_active_state(current_state)
            
        except FSMError as e:
            self.append_to_action_log([f"Update ERROR: {str(e)}"])
            self.on_stop_py_simulation()

    def append_to_action_log(self, messages):
        """Append messages to the simulation log"""
        if self.sim_log_output:
            for msg in messages:
                self.sim_log_output.append(f"> {msg}")
            self.sim_log_output.verticalScrollBar().setValue(
                self.sim_log_output.verticalScrollBar().maximum()
            )

    def _highlight_sim_active_state(self, state_name):
        """Highlight the currently active state in the scene"""
        # Implementation depends on your GraphicsStateItem implementation
        pass

    def update_dock_ui_contents(self):
        # This replaces MainWindow._update_py_simulation_dock_ui
        if not self.mw.py_fsm_engine or not self.mw.py_sim_active:
            if self.py_sim_current_state_label: self.py_sim_current_state_label.setText("<i>Not Running</i>")
            if self.py_sim_variables_table: self.py_sim_variables_table.setRowCount(0)
            self._highlight_sim_active_state(None); self._highlight_sim_taken_transition(None)
            if self.py_sim_event_combo: self.py_sim_event_combo.clear(); self.py_sim_event_combo.addItem("None (Internal Step)")
            return

        hierarchical_state_name = self.mw.py_fsm_engine.get_current_state_name()
        if self.py_sim_current_state_label: self.py_sim_current_state_label.setText(f"<b>{html.escape(hierarchical_state_name or 'N/A')}</b>")
        self._highlight_sim_active_state(hierarchical_state_name)

        all_vars = []
        if self.mw.py_fsm_engine:
            all_vars.extend([(k, str(v)) for k, v in sorted(self.mw.py_fsm_engine.get_variables().items())])
            if self.mw.py_fsm_engine.active_sub_simulator:
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
            possible_events = sorted(list(set(self.mw.py_fsm_engine.get_possible_events_from_current_state() +
                                             (self.mw.py_fsm_engine.active_sub_simulator.get_possible_events_from_current_state() 
                                              if self.mw.py_fsm_engine.active_sub_simulator else []))))
            if possible_events: self.py_sim_event_combo.addItems(possible_events)
            idx = self.py_sim_event_combo.findText(current_text)
            self.py_sim_event_combo.setCurrentIndex(idx if idx != -1 else 0)
        
        self._update_internal_controls_enabled_state() # Ensure buttons are correctly enabled/disabled

    def append_to_action_log(self, log_entries: list[str]):
        # This replaces MainWindow._append_to_py_simulation_log
        if not self.py_sim_action_log_output: return
        for entry in log_entries:
            cleaned_entry = html.escape(entry)
            if "[Condition]" in entry or "[Eval Error]" in entry or "ERROR" in entry.upper() or "SecurityError" in entry:
                cleaned_entry = f"<span style='color:red; font-weight:bold;'>{cleaned_entry}</span>"
            elif "[Safety Check Failed]" in entry or "[Action Blocked]" in entry or "[Condition Blocked]" in entry:
                cleaned_entry = f"<span style='color:orange; font-weight:bold;'>{cleaned_entry}</span>"
            elif "Transitioned from" in entry or "Reset to state" in entry or "Simulation started" in entry or "Entering state" in entry or "Exiting state" in entry:
                cleaned_entry = f"<span style='color:{COLOR_ACCENT_PRIMARY.name()}; font-weight:bold;'>{cleaned_entry}</span>"
            elif "No eligible transition" in entry or "event is not allowed" in entry:
                cleaned_entry = f"<span style='color:{COLOR_TEXT_SECONDARY};'>{cleaned_entry}</span>"
            self.py_sim_action_log_output.append(cleaned_entry)
        self.py_sim_action_log_output.verticalScrollBar().setValue(self.py_sim_action_log_output.verticalScrollBar().maximum())
        # Logging to main logger if important
        if log_entries and any(kw in log_entries[-1] for kw in ["Transitioned", "ERROR", "Reset", "started", "stopped", "SecurityError", "HALTED"]):
            logger.info("PySimUI Log: %s", log_entries[-1].split('\n')[0][:100])

    @pyqtSlot()
    def on_start_py_simulation(self):
        # Replaces MainWindow.on_start_py_simulation
        if self.mw.py_sim_active:
            QMessageBox.information(self.mw, "Simulation Active", "Python simulation is already running.")
            return
        if self.mw.scene.is_dirty(): # Check MainWindow's scene
            if QMessageBox.question(self.mw, "Unsaved Changes", "Diagram has unsaved changes. Start sim anyway?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.No:
                return
        diagram_data = self.mw.scene.get_diagram_data()
        if not diagram_data.get('states'):
            QMessageBox.warning(self.mw, "Empty Diagram", "Cannot start simulation: The diagram has no states.")
            return
        try:
            self.mw.py_fsm_engine = FSMSimulator(diagram_data['states'], diagram_data['transitions'], halt_on_action_error=True)
            self._set_simulation_active_state(True)
            if self.py_sim_action_log_output: self.py_sim_action_log_output.clear(); self.py_sim_action_log_output.setHtml("<i>Log...</i>")
            initial_log = ["Python FSM Simulation started."] + self.mw.py_fsm_engine.get_last_executed_actions_log()
            self.append_to_action_log(initial_log)
            self.update_dock_ui_contents()
        except FSMError as e:
            QMessageBox.critical(self.mw, "FSM Init Error", f"Failed to start sim:\n{e}")
            self.append_to_action_log([f"ERROR Starting Sim: {e}"]); logger.error("PySimUI: Start FSM Error: %s", e, exc_info=True)
            self.mw.py_fsm_engine = None; self._set_simulation_active_state(False)
        except Exception as e:
            QMessageBox.critical(self.mw, "Sim Start Error", f"Unexpected error starting sim:\n{type(e).__name__}: {e}")
            self.append_to_action_log([f"UNEXPECTED ERROR Starting Sim: {e}"]); logger.error("PySimUI: Unexpected Start Error:", exc_info=True)
            self.mw.py_fsm_engine = None; self._set_simulation_active_state(False)

    @pyqtSlot(bool)
    def on_stop_py_simulation(self, silent=False):
        # Replaces MainWindow.on_stop_py_simulation
        if not self.mw.py_sim_active: return
        self._highlight_sim_active_state(None); self._highlight_sim_taken_transition(None)
        self.mw.py_fsm_engine = None
        self._set_simulation_active_state(False)
        self.update_dock_ui_contents()
        if not silent: self.append_to_action_log(["Python FSM Simulation stopped."])

    @pyqtSlot()
    def on_reset_py_simulation(self):
        # Replaces MainWindow.on_reset_py_simulation
        if not self.mw.py_fsm_engine or not self.mw.py_sim_active:
            QMessageBox.warning(self.mw, "Sim Not Active", "Python simulation is not running."); return
        try:
            self.mw.py_fsm_engine.reset()
            if self.py_sim_action_log_output: self.py_sim_action_log_output.append("<hr><i style='color:grey;'>Sim Reset</i><hr>")
            self.append_to_action_log(self.mw.py_fsm_engine.get_last_executed_actions_log())
            self.update_dock_ui_contents(); self._highlight_sim_taken_transition(None)
        except FSMError as e:
            QMessageBox.critical(self.mw, "FSM Reset Error", f"Failed to reset sim:\n{e}")
            self.append_to_action_log([f"ERROR DURING RESET: {e}"]); logger.error("PySimUI: Reset FSM Error: %s", e, exc_info=True)
        except Exception as e:
            QMessageBox.critical(self.mw, "Reset Error", f"Unexpected error during reset:\n{type(e).__name__}: {e}")
            self.append_to_action_log([f"UNEXPECTED ERROR DURING RESET: {e}"]); logger.error("PySimUI: Unexpected Reset Error:", exc_info=True)

    @pyqtSlot()
    def on_step_py_simulation(self):
        # Replaces MainWindow.on_step_py_simulation
        if not self.mw.py_fsm_engine or not self.mw.py_sim_active:
            QMessageBox.warning(self.mw, "Sim Not Active", "Python simulation is not running."); return
        try:
            _, log_entries = self.mw.py_fsm_engine.step(event_name=None)
            self.append_to_action_log(log_entries); self.update_dock_ui_contents(); self._highlight_sim_taken_transition(None)
            if self.mw.py_fsm_engine.simulation_halted_flag:
                self.append_to_action_log(["[HALTED] Sim halted. Reset."]); QMessageBox.warning(self.mw, "Sim Halted", "Sim halted due to FSM action error. Reset.")
        except FSMError as e:
            QMessageBox.warning(self.mw, "Sim Step Error", str(e))
            self.append_to_action_log([f"ERROR DURING STEP: {e}"]); logger.error("PySimUI: Step FSMError: %s", e, exc_info=True)
            if self.mw.py_fsm_engine and self.mw.py_fsm_engine.simulation_halted_flag: self.append_to_action_log(["[HALTED] Sim halted. Reset."])
        except Exception as e:
            QMessageBox.critical(self.mw, "Sim Step Error", f"Unexpected error during step:\n{type(e).__name__}: {e}")
            self.append_to_action_log([f"UNEXPECTED ERROR DURING STEP: {e}"]); logger.error("PySimUI: Unexpected Step Error:", exc_info=True)

    @pyqtSlot()
    def on_trigger_py_event(self):
        # Replaces MainWindow.on_trigger_py_event
        if not self.mw.py_fsm_engine or not self.mw.py_sim_active:
            QMessageBox.warning(self.mw, "Sim Not Active", "Python simulation is not running."); return
        event_name_combo = self.py_sim_event_combo.currentText() if self.py_sim_event_combo else ""
        event_name_edit = self.py_sim_event_name_edit.text().strip() if self.py_sim_event_name_edit else ""
        event_to_trigger = event_name_edit if event_name_edit else (event_name_combo if event_name_combo != "None (Internal Step)" else None)

        if not event_to_trigger: self.on_step_py_simulation(); return
        try:
            _, log_entries = self.mw.py_fsm_engine.step(event_name=event_to_trigger)
            self.append_to_action_log(log_entries); self.update_dock_ui_contents()
            if self.py_sim_event_name_edit: self.py_sim_event_name_edit.clear()
            self._highlight_sim_taken_transition(None)
            if self.mw.py_fsm_engine.simulation_halted_flag:
                self.append_to_action_log(["[HALTED] Sim halted. Reset."]); QMessageBox.warning(self.mw, "Sim Halted", "Sim halted due to FSM action error. Reset.")
        except FSMError as e:
            QMessageBox.warning(self.mw, "Sim Event Error", str(e))
            self.append_to_action_log([f"ERROR EVENT '{html.escape(event_to_trigger)}': {e}"]); logger.error("PySimUI: Event FSMError for '%s': %s", event_to_trigger, e, exc_info=True)
            if self.mw.py_fsm_engine and self.mw.py_fsm_engine.simulation_halted_flag: self.append_to_action_log(["[HALTED] Sim halted. Reset."])
        except Exception as e:
            QMessageBox.critical(self.mw, "Sim Event Error", f"Unexpected error on event '{html.escape(event_to_trigger)}':\n{type(e).__name__}: {e}")
            self.append_to_action_log([f"UNEXPECTED ERROR EVENT '{html.escape(event_to_trigger)}': {e}"]); logger.error("PySimUI: Unexpected Event Error for '%s':", event_to_trigger, exc_info=True)