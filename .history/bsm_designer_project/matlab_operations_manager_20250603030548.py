# bsm_designer_project/matlab_operations_manager.py

import os
import logging
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox, QDialog, QFormLayout, QLineEdit,
    QPushButton, QComboBox, QDialogButtonBox, QHBoxLayout, QStyle
)
from PyQt5.QtCore import QDir, QUrl, pyqtSlot
from PyQt5.QtGui import QDesktopServices

from matlab_integration import MatlabConnection # Keep reference to the actual connection logic
from dialogs import MatlabSettingsDialog # Dialog is UI, but invoked by this manager
from utils import get_standard_icon

logger = logging.getLogger(__name__)

class MatlabOperationsManager(QObject):
    def __init__(self, main_window, matlab_connection: MatlabConnection):
        super().__init__()
        self.mw = main_window
        self.matlab_connection = matlab_connection
        self.last_generated_model_path: str | None = None # Manager now owns this state

        # Connect signals from MatlabConnection to this manager's slots
        self.matlab_connection.connectionStatusChanged.connect(self.update_matlab_status_display)
        self.matlab_connection.simulationFinished.connect(self.handle_matlab_modelgen_or_sim_finished)
        self.matlab_connection.codeGenerationFinished.connect(self.handle_matlab_codegen_finished)

    def _start_matlab_operation(self, operation_name: str):
        logger.info("MATLAB Operation: '%s' starting...", operation_name)
        if hasattr(self.mw, 'status_label'):
            self.mw.status_label.setText(f"Running MATLAB: {operation_name}...")
        if hasattr(self.mw, 'progress_bar'):
            self.mw.progress_bar.setVisible(True)
        self.set_ui_enabled_for_matlab_op(False)

    def _finish_matlab_operation(self):
        if hasattr(self.mw, 'progress_bar'):
            self.mw.progress_bar.setVisible(False)
        if hasattr(self.mw, 'status_label'):
            self.mw.status_label.setText("Ready") # Reset main status
        self.set_ui_enabled_for_matlab_op(True)
        logger.info("MATLAB Operation: Finished processing.")

    def set_ui_enabled_for_matlab_op(self, enabled: bool):
        """Enables/disables main UI elements during a MATLAB operation."""
        if hasattr(self.mw, 'menuBar'): self.mw.menuBar().setEnabled(enabled)
        # Disable toolbars (more selective disabling might be needed if some tools should remain active)
        for child in self.mw.findChildren(QToolBar):
            child.setEnabled(enabled)
        if self.mw.centralWidget(): self.mw.centralWidget().setEnabled(enabled)

        # Disable/enable docks (consider which docks are safe to interact with)
        for dock_name in ["ToolsDock", "PropertiesDock", "LogDock", "PySimDock", "AIChatbotDock", "IDEDock", "ProblemsDock"]:
            dock = self.mw.findChild(QDockWidget, dock_name)
            if dock: dock.setEnabled(enabled)
        self.mw._update_py_simulation_actions_enabled_state() # MainWindow handles this based on sim_active and MATLAB op

    @pyqtSlot(bool, str)
    def update_matlab_status_display(self, connected: bool, message: str):
        # This method now updates the UI directly in MainWindow
        self.mw._update_matlab_status_display(connected, message) # Call MainWindow's method
        self.update_matlab_actions_enabled_state() # Update actions based on new status

    def update_matlab_actions_enabled_state(self):
        can_run_matlab_ops = self.matlab_connection.connected and not self.mw.py_sim_active

        if hasattr(self.mw, 'export_simulink_action'): self.mw.export_simulink_action.setEnabled(can_run_matlab_ops)
        if hasattr(self.mw, 'run_simulation_action'): self.mw.run_simulation_action.setEnabled(can_run_matlab_ops)
        if hasattr(self.mw, 'generate_matlab_code_action'): self.mw.generate_matlab_code_action.setEnabled(can_run_matlab_ops)
        if hasattr(self.mw, 'matlab_settings_action'): self.mw.matlab_settings_action.setEnabled(not self.mw.py_sim_active)

    @pyqtSlot(bool, str, str)
    def handle_matlab_modelgen_or_sim_finished(self, success: bool, message: str, data: str):
        self._finish_matlab_operation()
        logger.log(logging.INFO if success else logging.ERROR, "MATLAB Result (ModelGen/Sim): %s", message)
        if success:
            if "Model generation" in message and data:
                self.last_generated_model_path = data
                QMessageBox.information(self.mw, "Simulink Model Generation", f"Model generated successfully:\n{data}")
            elif "Simulation" in message:
                QMessageBox.information(self.mw, "Simulation Complete", f"MATLAB simulation finished.\n{message}")
        else:
            QMessageBox.warning(self.mw, "MATLAB Operation Failed", message)

    @pyqtSlot(bool, str, str)
    def handle_matlab_codegen_finished(self, success: bool, message: str, output_dir: str):
        self._finish_matlab_operation()
        logger.log(logging.INFO if success else logging.ERROR, "MATLAB Code Gen Result: %s", message)
        if success and output_dir:
            msg_box = QMessageBox(self.mw); msg_box.setIcon(QMessageBox.Information); msg_box.setWindowTitle("Code Generation Successful")
            msg_box.setTextFormat(Qt.RichText); abs_dir = os.path.abspath(output_dir)
            msg_box.setText(f"Code generation completed successfully.<br>Generated files are in: <a href='file:///{abs_dir}'>{abs_dir}</a>")
            msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction)
            open_btn = msg_box.addButton("Open Directory", QMessageBox.ActionRole); msg_box.addButton(QMessageBox.Ok)
            msg_box.exec()
            if msg_box.clickedButton() == open_btn:
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(abs_dir)):
                    logger.error("Error opening directory: %s", abs_dir)
                    QMessageBox.warning(self.mw, "Error Opening Directory", f"Could not automatically open the directory:\n{abs_dir}")
        elif not success:
            QMessageBox.warning(self.mw, "Code Generation Failed", message)

    @pyqtSlot()
    def on_export_simulink(self):
        if not self.matlab_connection.connected:
            QMessageBox.warning(self.mw, "MATLAB Not Connected", "Please configure MATLAB path in Settings first.")
            return
        if self.mw.py_sim_active:
            QMessageBox.warning(self.mw, "Python Simulation Active", "Please stop the Python simulation before exporting to Simulink.")
            return

        dialog = QDialog(self.mw)
        dialog.setWindowTitle("Export to Simulink")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp, "->M"))
        layout = QFormLayout(dialog)
        layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)

        base_name = os.path.splitext(os.path.basename(self.mw.current_file_path or "BSM_Model"))[0]
        default_model_name = "".join(c if c.isalnum() or c=='_' else '_' for c in base_name)
        if not default_model_name or not default_model_name[0].isalpha():
            default_model_name = "Mdl_" + default_model_name if default_model_name else "Mdl_MyStateMachine"
        default_model_name = default_model_name.replace('-','_')

        name_edit = QLineEdit(default_model_name)
        layout.addRow("Simulink Model Name:", name_edit)

        default_output_dir = os.path.dirname(self.mw.current_file_path or QDir.homePath())
        output_dir_edit = QLineEdit(default_output_dir)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw")," Browse..."); browse_btn.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(output_dir_edit, 1); dir_layout.addWidget(browse_btn)
        layout.addRow("Output Directory:", dir_layout)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        dialog.setMinimumWidth(450)

        if dialog.exec() == QDialog.Accepted:
            model_name = name_edit.text().strip()
            output_dir = output_dir_edit.text().strip()
            if not model_name or not output_dir:
                QMessageBox.warning(self.mw, "Input Error", "Model name and output directory are required.")
                return
            if not model_name[0].isalpha() or not all(c.isalnum() or c=='_' for c in model_name):
                QMessageBox.warning(self.mw, "Invalid Model Name", "Simulink model name must start with a letter and contain only alphanumeric characters or underscores.")
                return
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self.mw, "Directory Error", f"Could not create output directory:\n{e}")
                return

            diagram_data = self.mw.scene.get_diagram_data()
            if not diagram_data['states']:
                QMessageBox.information(self.mw, "Empty Diagram", "Cannot export an empty diagram (no states defined).")
                return

            self._start_matlab_operation(f"Exporting '{model_name}' to Simulink")
            self.matlab_connection.generate_simulink_model(diagram_data['states'], diagram_data['transitions'], output_dir, model_name)

    @pyqtSlot()
    def on_run_simulation(self): # MATLAB simulation
        if not self.matlab_connection.connected:
            QMessageBox.warning(self.mw, "MATLAB Not Connected", "Please configure MATLAB path in Settings.")
            return
        if self.mw.py_sim_active:
            QMessageBox.warning(self.mw, "Python Simulation Active", "Please stop the Python simulation before running a MATLAB simulation.")
            return

        default_dir = os.path.dirname(self.last_generated_model_path or self.mw.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self.mw, "Select Simulink Model to Simulate", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path
        sim_time, ok = QInputDialog.getDouble(self.mw, "Simulation Time", "Enter simulation stop time (seconds):", 10.0, 0.001, 86400.0, 3)
        if not ok: return

        self._start_matlab_operation(f"Running Simulink simulation for '{os.path.basename(model_path)}'")
        self.matlab_connection.run_simulation(model_path, sim_time)

    @pyqtSlot()
    def on_generate_matlab_code(self): # C/C++ via MATLAB
        if not self.matlab_connection.connected:
            QMessageBox.warning(self.mw, "MATLAB Not Connected", "Please configure MATLAB path in Settings.")
            return
        if self.mw.py_sim_active:
            QMessageBox.warning(self.mw, "Python Simulation Active", "Please stop the Python simulation before generating code.")
            return

        default_dir = os.path.dirname(self.last_generated_model_path or self.mw.current_file_path or QDir.homePath())
        model_path, _ = QFileDialog.getOpenFileName(self.mw, "Select Simulink Model for Code Generation", default_dir, "Simulink Models (*.slx);;All Files (*)")
        if not model_path: return

        self.last_generated_model_path = model_path

        dialog = QDialog(self.mw); dialog.setWindowTitle("Code Generation Options"); dialog.setWindowIcon(get_standard_icon(QStyle.SP_DialogSaveButton, "Cde"))
        layout = QFormLayout(dialog); layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)
        lang_combo = QComboBox(); lang_combo.addItems(["C", "C++"]); lang_combo.setCurrentText("C++")
        layout.addRow("Target Language:", lang_combo)

        output_dir_edit = QLineEdit(os.path.dirname(model_path))
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon, "Brw")," Browse..."); browse_btn.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Base Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(output_dir_edit, 1); dir_layout.addWidget(browse_btn)
        layout.addRow("Base Output Directory:", dir_layout)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject); layout.addRow(btns)
        dialog.setMinimumWidth(450)

        if dialog.exec() == QDialog.Accepted:
            language = lang_combo.currentText()
            output_dir_base = output_dir_edit.text().strip()
            if not output_dir_base:
                QMessageBox.warning(self.mw, "Input Error", "Base output directory is required.")
                return
            try:
                os.makedirs(output_dir_base, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self.mw, "Directory Error", f"Could not create output directory:\n{e}")
                return

            self._start_matlab_operation(f"Generating {language} code for '{os.path.basename(model_path)}'")
            self.matlab_connection.generate_code(model_path, language, output_dir_base)

    @pyqtSlot()
    def on_matlab_settings(self):
        dialog = MatlabSettingsDialog(matlab_connection=self.matlab_connection, parent=self.mw)
        dialog.exec()
        logger.info("MATLAB settings dialog closed.")