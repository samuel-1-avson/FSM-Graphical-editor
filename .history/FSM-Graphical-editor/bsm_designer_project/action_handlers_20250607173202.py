# bsm_designer_project/action_handlers.py
import os
import json
import logging
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox, QInputDialog, QDialog, QFormLayout, QLineEdit, QPushButton, QHBoxLayout,
    QStyle, QDialogButtonBox # Added QDialogButtonBox
)
from PyQt5.QtCore import QObject, pyqtSlot, QDir, QUrl, QPointF, Qt, QRectF # Added Qt and QRectF
from PyQt5.QtGui import QDesktopServices # QRectF removed from here

from utils import get_standard_icon, _get_bundled_file_path # Moved _get_bundled_file_path to utils
from config import FILE_FILTER, FILE_EXTENSION, DEFAULT_EXECUTION_ENV
from undo_commands import MoveItemsCommand
from c_code_generator import generate_c_code_files # Import moved here
from export_utils import generate_plantuml_text, generate_mermaid_text # New import
from graphics_items import GraphicsStateItem, GraphicsCommentItem # Added for type checking


logger = logging.getLogger(__name__)

class ActionHandler(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

    def connect_actions(self):
        # File Actions
        self.mw.new_action.triggered.connect(self.on_new_file)
        self.mw.open_action.triggered.connect(self.on_open_file)
        self.mw.save_action.triggered.connect(self.on_save_file)
        self.mw.save_as_action.triggered.connect(self.on_save_file_as)
        self.mw.export_simulink_action.triggered.connect(self.on_export_simulink)
        self.mw.generate_c_code_action.triggered.connect(self.on_generate_c_code)
        self.mw.export_plantuml_action.triggered.connect(self.on_export_plantuml) # New
        self.mw.export_mermaid_action.triggered.connect(self.on_export_mermaid)   # New
        
        # Edit Actions
        self.mw.select_all_action.triggered.connect(self.on_select_all)
        self.mw.delete_action.triggered.connect(self.on_delete_selected)
        self.mw.find_item_action.triggered.connect(self.on_show_find_item_dialog)

        # View Actions
        self.mw.zoom_to_selection_action.triggered.connect(self.on_zoom_to_selection)
        self.mw.fit_diagram_action.triggered.connect(self.on_fit_diagram_in_view)
        self.mw.snap_to_objects_action.triggered.connect(self.on_toggle_snap_to_objects)
        self.mw.snap_to_grid_action.triggered.connect(self.on_toggle_snap_to_grid)
        self.mw.show_snap_guidelines_action.triggered.connect(self.on_toggle_show_snap_guidelines)
        
        # Align/Distribute Actions
        self.mw.align_left_action.triggered.connect(lambda: self.on_align_items("left"))
        self.mw.align_center_h_action.triggered.connect(lambda: self.on_align_items("center_h"))
        self.mw.align_right_action.triggered.connect(lambda: self.on_align_items("right"))
        self.mw.align_top_action.triggered.connect(lambda: self.on_align_items("top"))
        self.mw.align_middle_v_action.triggered.connect(lambda: self.on_align_items("middle_v"))
        self.mw.align_bottom_action.triggered.connect(lambda: self.on_align_items("bottom"))
        self.mw.distribute_h_action.triggered.connect(lambda: self.on_distribute_items("horizontal"))
        self.mw.distribute_v_action.triggered.connect(lambda: self.on_distribute_items("vertical"))

        # Help Actions
        self.mw.quick_start_action.triggered.connect(self.on_show_quick_start)
        self.mw.about_action.triggered.connect(self.on_about)
        
        # Example Actions
        self.mw.open_example_traffic_action.triggered.connect(lambda: self._open_example_file("traffic_light.bsm"))
        self.mw.open_example_toggle_action.triggered.connect(lambda: self._open_example_file("simple_toggle.bsm"))
        
        # MATLAB Actions (handled by MainWindow directly due to state complexity with matlab_connection)
        # self.mw.run_simulation_action.triggered.connect(self.on_run_simulation)
        # self.mw.generate_matlab_code_action.triggered.connect(self.on_generate_matlab_code)
        # self.mw.matlab_settings_action.triggered.connect(self.on_matlab_settings)


    @pyqtSlot(bool)
    def on_new_file(self, silent=False):
        if not silent:
            if not self.mw._prompt_save_if_dirty(): return False
            if hasattr(self.mw, 'ide_manager') and self.mw.ide_manager:
                if not self.mw.ide_manager.prompt_ide_save_if_dirty(): return False
            else:
                 logger.warning("ActionHandler: MainWindow.ide_manager not found for new_file check.")


        if hasattr(self.mw, 'py_sim_ui_manager') and self.mw.py_sim_ui_manager: 
            self.mw.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        self.mw.scene.clear()
        self.mw.scene.setSceneRect(0,0,6000,4500)
        self.mw.current_file_path = None
        self.mw.last_generated_model_path = None
        self.mw.undo_stack.clear()
        self.mw.scene.set_dirty(False)
        self.mw._update_window_title() 
        self.mw._update_undo_redo_actions_enable_state()
        self.mw._update_save_actions_enable_state()
        if not silent:
            logger.info("New diagram created.")
            if hasattr(self.mw, 'status_label'): self.mw.status_label.setText("New diagram. Ready.")
        if self.mw.view:
            self.mw.view.resetTransform()
            if self.mw.scene and self.mw.scene.sceneRect():
                self.mw.view.centerOn(self.mw.scene.sceneRect().center())
        if hasattr(self.mw, 'select_mode_action'): self.mw.select_mode_action.trigger()
        self.mw._refresh_find_dialog_if_visible()
        if self.mw.scene: self.mw.scene.run_all_validations("NewFile")
        return True

    @pyqtSlot()
    def on_open_file(self):
        if not self.mw._prompt_save_if_dirty(): return
        if hasattr(self.mw, 'ide_manager') and self.mw.ide_manager:
            if not self.mw.ide_manager.prompt_ide_save_if_dirty(): return
        else:
            logger.warning("ActionHandler: MainWindow.ide_manager not found for open_file check.")

        if hasattr(self.mw, 'py_sim_ui_manager') and self.mw.py_sim_ui_manager: 
            self.mw.py_sim_ui_manager.on_stop_py_simulation(silent=True)

        start_dir = os.path.dirname(self.mw.current_file_path) if self.mw.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(self.mw, "Open BSM File", start_dir, FILE_FILTER)

        if file_path:
            if self.mw._load_from_path(file_path): # MainWindow handles loading
                self.mw.current_file_path = file_path
                self.mw.last_generated_model_path = None
                self.mw.undo_stack.clear()
                self.mw.scene.set_dirty(False)
                self.mw._update_window_title()
                self.mw._update_undo_redo_actions_enable_state()
                self.mw._update_save_actions_enable_state()
                logger.info("Opened file: %s", file_path)
                if hasattr(self.mw, 'status_label'): self.mw.status_label.setText(f"Opened: {os.path.basename(file_path)}")
                bounds = self.mw.scene.itemsBoundingRect()
                if not bounds.isEmpty():
                    self.mw.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else:
                    self.mw.view.resetTransform()
                    self.mw.view.centerOn(self.mw.scene.sceneRect().center())
                self.mw._refresh_find_dialog_if_visible()
            else:
                QMessageBox.critical(self.mw, "Error Opening File", f"Could not load the diagram from:\n{file_path}")
                logger.error("Failed to open file: %s", file_path)

    @pyqtSlot()
    def on_save_file(self) -> bool:
        if not self.mw.current_file_path:
            return self.on_save_file_as()
        if self.mw.scene.is_dirty():
             return self.mw._save_to_path(self.mw.current_file_path) # MainWindow handles saving
        return True

    @pyqtSlot()
    def on_save_file_as(self) -> bool:
        default_filename = os.path.basename(self.mw.current_file_path or "untitled" + FILE_EXTENSION)
        start_dir = os.path.dirname(self.mw.current_file_path) if self.mw.current_file_path else QDir.homePath()

        file_path, _ = QFileDialog.getSaveFileName(self.mw, "Save BSM File As",
                                                   os.path.join(start_dir, default_filename),
                                                   FILE_FILTER)
        if file_path:
            if not file_path.lower().endswith(FILE_EXTENSION):
                file_path += FILE_EXTENSION
            if self.mw._save_to_path(file_path): # MainWindow handles saving
                self.mw.current_file_path = file_path
                return True
        return False

    @pyqtSlot()
    def on_export_simulink(self):
        mw = self.mw # For brevity
        if not mw.matlab_connection.connected:
            QMessageBox.warning(mw, "MATLAB Not Connected", "Please configure MATLAB path in Settings first.")
            return
        if mw.py_sim_active:
            QMessageBox.warning(mw, "Python Simulation Active", "Please stop the Python simulation before exporting to Simulink.")
            return

        dialog = QDialog(mw); dialog.setWindowTitle("Export to Simulink")
        dialog.setWindowIcon(get_standard_icon(QStyle.SP_ArrowUp, "->M")); layout = QFormLayout(dialog)
        layout.setSpacing(8); layout.setContentsMargins(10,10,10,10)
        base_name = os.path.splitext(os.path.basename(mw.current_file_path or "BSM_Model"))[0]
        default_model_name = "".join(c if c.isalnum() or c=='_' else '_' for c in base_name)
        if not default_model_name or not default_model_name[0].isalpha(): default_model_name = "Mdl_" + (default_model_name if default_model_name else "MyStateMachine")
        default_model_name = default_model_name.replace('-','_')
        name_edit = QLineEdit(default_model_name); layout.addRow("Simulink Model Name:", name_edit)
        default_output_dir = os.path.dirname(mw.current_file_path or QDir.homePath())
        output_dir_edit = QLineEdit(default_output_dir)
        browse_btn = QPushButton(get_standard_icon(QStyle.SP_DirOpenIcon,"Brw")," Browse..."); browse_btn.clicked.connect(lambda: output_dir_edit.setText(QFileDialog.getExistingDirectory(dialog, "Select Output Directory", output_dir_edit.text()) or output_dir_edit.text()))
        dir_layout = QHBoxLayout(); dir_layout.addWidget(output_dir_edit, 1); dir_layout.addWidget(browse_btn); layout.addRow("Output Directory:", dir_layout)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject); layout.addRow(btns)
        dialog.setMinimumWidth(450)
        if dialog.exec() == QDialog.Accepted:
            model_name = name_edit.text().strip(); output_dir = output_dir_edit.text().strip()
            if not model_name or not output_dir: QMessageBox.warning(mw, "Input Error", "Model name and output directory are required."); return
            if not model_name[0].isalpha() or not all(c.isalnum() or c=='_' for c in model_name): QMessageBox.warning(mw, "Invalid Model Name", "Simulink model name must start with a letter and contain only alphanumeric characters or underscores."); return
            try: os.makedirs(output_dir, exist_ok=True)
            except OSError as e: QMessageBox.critical(mw, "Directory Error", f"Could not create output directory:\n{e}"); return
            diagram_data = mw.scene.get_diagram_data()
            if not diagram_data['states']: QMessageBox.information(mw, "Empty Diagram", "Cannot export an empty diagram (no states defined)."); return
            mw._start_matlab_operation(f"Exporting '{model_name}' to Simulink")
            mw.matlab_connection.generate_simulink_model(diagram_data['states'], diagram_data['transitions'], output_dir, model_name)

    @pyqtSlot()
    def on_generate_c_code(self):
        mw = self.mw
        if not mw.scene.items(): QMessageBox.information(mw, "Empty Diagram", "Cannot generate code for an empty diagram."); return
        default_filename_base = "fsm_generated"
        if mw.current_file_path: default_filename_base = os.path.splitext(os.path.basename(mw.current_file_path))[0]
        default_filename_base = "".join(c if c.isalnum() or c == '_' else '_' for c in default_filename_base)
        if not default_filename_base or not default_filename_base[0].isalpha(): default_filename_base = "bsm_" + (default_filename_base if default_filename_base else "model")
        output_dir = QFileDialog.getExistingDirectory(mw, "Select Output Directory for C Code", QDir.homePath())
        if output_dir:
            filename_base, ok = QInputDialog.getText(mw, "Base Filename", "Enter base name for .c and .h files (e.g., my_fsm):", QLineEdit.Normal, default_filename_base)
            if ok and filename_base.strip():
                filename_base = filename_base.strip(); filename_base = "".join(c if c.isalnum() or c == '_' else '_' for c in filename_base)
                if not filename_base or not filename_base[0].isalpha(): QMessageBox.warning(mw, "Invalid Filename", "Base filename must start with a letter and contain only alphanumeric characters or underscores."); return
                diagram_data = mw.scene.get_diagram_data()
                try:
                    c_file_path, h_file_path = generate_c_code_files(diagram_data, output_dir, filename_base)
                    QMessageBox.information(mw, "C Code Generation Successful", f"Generated files:\n{c_file_path}\n{h_file_path}")
                    logger.info(f"C code generated successfully to {output_dir} with base name {filename_base}")
                except Exception as e: QMessageBox.critical(mw, "C Code Generation Error", f"Failed to generate C code: {e}"); logger.error(f"Error generating C code: {e}", exc_info=True)
            elif ok: QMessageBox.warning(mw, "Invalid Filename", "Base filename cannot be empty.")

    @pyqtSlot()
    def on_export_plantuml(self):
        mw = self.mw
        if not mw.scene.items():
            QMessageBox.information(mw, "Empty Diagram", "Cannot export an empty diagram.")
            return
        
        diagram_data = mw.scene.get_diagram_data()
        diagram_name = os.path.splitext(os.path.basename(mw.current_file_path or "FSM_Diagram"))[0]
        
        try:
            puml_text = generate_plantuml_text(diagram_data, diagram_name)
        except Exception as e:
            QMessageBox.critical(mw, "PlantUML Export Error", f"Failed to generate PlantUML text: {e}")
            logger.error(f"Error generating PlantUML text: {e}", exc_info=True)
            return

        default_filename = f"{diagram_name}.puml"
        start_dir = os.path.dirname(mw.current_file_path) if mw.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getSaveFileName(mw, "Save PlantUML File",
                                                   os.path.join(start_dir, default_filename),
                                                   "PlantUML Files (*.puml *.plantuml);;Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(puml_text)
                QMessageBox.information(mw, "PlantUML Export Successful", f"Diagram exported to:\n{file_path}")
                logger.info(f"PlantUML diagram exported to {file_path}")
            except IOError as e:
                QMessageBox.critical(mw, "File Save Error", f"Could not save PlantUML file: {e}")
                logger.error(f"Error saving PlantUML file to {file_path}: {e}", exc_info=True)

    @pyqtSlot()
    def on_export_mermaid(self):
        mw = self.mw
        if not mw.scene.items():
            QMessageBox.information(mw, "Empty Diagram", "Cannot export an empty diagram.")
            return

        diagram_data = mw.scene.get_diagram_data()
        diagram_name = os.path.splitext(os.path.basename(mw.current_file_path or "FSM_Diagram"))[0]

        try:
            mermaid_text = generate_mermaid_text(diagram_data, diagram_name)
        except Exception as e:
            QMessageBox.critical(mw, "Mermaid Export Error", f"Failed to generate Mermaid text: {e}")
            logger.error(f"Error generating Mermaid text: {e}", exc_info=True)
            return
            
        default_filename = f"{diagram_name}.md" # Mermaid often used in Markdown
        start_dir = os.path.dirname(mw.current_file_path) if mw.current_file_path else QDir.homePath()
        file_path, _ = QFileDialog.getSaveFileName(mw, "Save Mermaid File",
                                                   os.path.join(start_dir, default_filename),
                                                   "Markdown Files (*.md);;Mermaid Files (*.mmd);;Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(mermaid_text)
                QMessageBox.information(mw, "Mermaid Export Successful", f"Diagram exported to:\n{file_path}")
                logger.info(f"Mermaid diagram exported to {file_path}")
            except IOError as e:
                QMessageBox.critical(mw, "File Save Error", f"Could not save Mermaid file: {e}")
                logger.error(f"Error saving Mermaid file to {file_path}: {e}", exc_info=True)


    @pyqtSlot()
    def on_select_all(self): self.mw.scene.select_all()

    @pyqtSlot()
    def on_delete_selected(self): self.mw.scene.delete_selected_items()

    @pyqtSlot(bool)
    def on_toggle_snap_to_grid(self, checked): self.mw.scene.snap_to_grid_enabled = checked; logger.info(f"Snap to Grid {'enabled' if checked else 'disabled'}.")

    @pyqtSlot(bool)
    def on_toggle_snap_to_objects(self, checked): self.mw.scene.snap_to_objects_enabled = checked; logger.info(f"Snap to Objects {'enabled' if checked else 'disabled'}.")
    
    @pyqtSlot(bool)
    def on_toggle_show_snap_guidelines(self, checked):
        if hasattr(self.mw.scene, '_show_dynamic_snap_guidelines'):
            self.mw.scene._show_dynamic_snap_guidelines = checked
            if not checked: self.mw.scene._clear_dynamic_guidelines()
            logger.info(f"Dynamic Snap Guidelines {'shown' if checked else 'hidden'}.")

    @pyqtSlot()
    def on_zoom_to_selection(self):
        if hasattr(self.mw.view, 'zoom_to_selection'): self.mw.view.zoom_to_selection()

    @pyqtSlot()
    def on_fit_diagram_in_view(self):
        if hasattr(self.mw.view, 'fit_diagram_in_view'): self.mw.view.fit_diagram_in_view()

    @pyqtSlot(str)
    def on_align_items(self, mode: str):
        mw = self.mw
        # FIX: Simplified item type check
        selected_items = [item for item in mw.scene.selectedItems() if isinstance(item, (GraphicsStateItem, GraphicsCommentItem))]
        if len(selected_items) < 2: return
        old_positions_map = {item: item.pos() for item in selected_items}; moved_items_data_for_command = []
        
        overall_selection_rect = QRectF(); first = True
        for item in selected_items:
            if first: overall_selection_rect = item.sceneBoundingRect(); first = False
            else: overall_selection_rect = overall_selection_rect.united(item.sceneBoundingRect())
            
        if overall_selection_rect.isEmpty(): return # No items with bounds

        if mode == "left": ref_x = overall_selection_rect.left(); [item.setPos(ref_x, item.y()) for item in selected_items]
        elif mode == "center_h": ref_x_center = overall_selection_rect.center().x(); [item.setPos(ref_x_center - item.sceneBoundingRect().width() / 2.0, item.y()) for item in selected_items]
        elif mode == "right": ref_x = overall_selection_rect.right(); [item.setPos(ref_x - item.sceneBoundingRect().width(), item.y()) for item in selected_items]
        elif mode == "top": ref_y = overall_selection_rect.top(); [item.setPos(item.x(), ref_y) for item in selected_items]
        elif mode == "middle_v": ref_y_middle = overall_selection_rect.center().y(); [item.setPos(item.x(), ref_y_middle - item.sceneBoundingRect().height() / 2.0) for item in selected_items]
        elif mode == "bottom": ref_y = overall_selection_rect.bottom(); [item.setPos(item.x(), ref_y - item.sceneBoundingRect().height()) for item in selected_items]
        
        for item in selected_items:
            new_pos = item.pos(); old_pos = old_positions_map[item]
            if (new_pos - old_pos).manhattanLength() > 0.1: moved_items_data_for_command.append((item, old_pos, new_pos))
            if type(item).__name__ == "GraphicsStateItem": mw.scene._update_connected_transitions(item)
        if moved_items_data_for_command: cmd = MoveItemsCommand(moved_items_data_for_command, f"Align {mode.replace('_', ' ').title()}"); mw.undo_stack.push(cmd); mw.scene.set_dirty(True)

    @pyqtSlot(str)
    def on_distribute_items(self, mode: str):
        mw = self.mw
        # FIX: Simplified item type check
        selected_items = [item for item in mw.scene.selectedItems() if isinstance(item, (GraphicsStateItem, GraphicsCommentItem))]
        if len(selected_items) < 3: return
        old_positions_map = {item: item.pos() for item in selected_items}; moved_items_data_for_command = []
        if mode == "horizontal":
            selected_items.sort(key=lambda item: item.sceneBoundingRect().left()); start_x_coord = selected_items[0].sceneBoundingRect().left(); selected_items[0].setPos(start_x_coord, old_positions_map[selected_items[0]].y()); min_x_overall = selected_items[0].sceneBoundingRect().left(); max_x_overall_right_edge = selected_items[-1].sceneBoundingRect().right(); total_width_of_items = sum(item.sceneBoundingRect().width() for item in selected_items); actual_span_covered_by_items_edges = max_x_overall_right_edge - min_x_overall; spacing = 0 if len(selected_items) <= 1 else (actual_span_covered_by_items_edges - total_width_of_items) / (len(selected_items) - 1)
            if spacing < 0: spacing = 10; logger.warning("Distribute Horizontal: Items wider than span, distributing with minimal spacing.")
            current_x_edge = selected_items[0].sceneBoundingRect().left()
            for i, item in enumerate(selected_items): item.setPos(current_x_edge, old_positions_map[item].y()); current_x_edge += item.sceneBoundingRect().width() + spacing
        elif mode == "vertical":
            selected_items.sort(key=lambda item: item.sceneBoundingRect().top()); start_y_coord = selected_items[0].sceneBoundingRect().top(); selected_items[0].setPos(old_positions_map[selected_items[0]].x(), start_y_coord); min_y_overall = selected_items[0].sceneBoundingRect().top(); max_y_overall_bottom_edge = selected_items[-1].sceneBoundingRect().bottom(); total_height_of_items = sum(item.sceneBoundingRect().height() for item in selected_items); actual_span_covered_by_items_edges = max_y_overall_bottom_edge - min_y_overall; spacing = 0 if len(selected_items) <= 1 else (actual_span_covered_by_items_edges - total_height_of_items) / (len(selected_items) - 1)
            if spacing < 0: spacing = 10; logger.warning("Distribute Vertical: Items taller than span, distributing with minimal spacing.")
            current_y_edge = selected_items[0].sceneBoundingRect().top()
            for i, item in enumerate(selected_items): item.setPos(old_positions_map[item].x(), current_y_edge); current_y_edge += item.sceneBoundingRect().height() + spacing
        for item in selected_items:
            new_pos = item.pos(); old_pos = old_positions_map[item]
            if (new_pos - old_pos).manhattanLength() > 0.1: moved_items_data_for_command.append((item, old_pos, new_pos))
            if type(item).__name__ == "GraphicsStateItem": mw.scene._update_connected_transitions(item)
        if moved_items_data_for_command: cmd_text = "Distribute Horizontally" if mode == "horizontal" else "Distribute Vertically"; cmd = MoveItemsCommand(moved_items_data_for_command, cmd_text); mw.undo_stack.push(cmd); mw.scene.set_dirty(True)

    @pyqtSlot()
    def on_show_find_item_dialog(self): self.mw.on_show_find_item_dialog() # Delegate to MainWindow

    def _open_example_file(self, filename: str):
        if not self.mw._prompt_save_if_dirty(): return
        if hasattr(self.mw, 'py_sim_ui_manager') and self.mw.py_sim_ui_manager: self.mw.py_sim_ui_manager.on_stop_py_simulation(silent=True)
        example_path = _get_bundled_file_path(filename, resource_prefix="examples")
        if example_path:
            if self.mw._load_from_path(example_path):
                self.mw.current_file_path = f":/examples/{filename}" if example_path.startswith(QDir.tempPath()) and self.mw.RESOURCES_AVAILABLE else example_path
                self.mw.last_generated_model_path = None; self.mw.undo_stack.clear(); self.mw.scene.set_dirty(False); self.mw.setWindowModified(False)
                self.mw._update_window_title(); self.mw._update_undo_redo_actions_enable_state()
                logger.info("Opened example file: %s (from %s)", filename, example_path)
                if hasattr(self.mw, 'status_label'): self.mw.status_label.setText(f"Opened example: {filename}")
                bounds = self.mw.scene.itemsBoundingRect()
                if not bounds.isEmpty(): self.mw.view.fitInView(bounds.adjusted(-50,-50,50,50), Qt.KeepAspectRatio)
                else: self.mw.view.resetTransform(); self.mw.view.centerOn(self.mw.scene.sceneRect().center())
                self.mw._refresh_find_dialog_if_visible()
            else: QMessageBox.critical(self.mw, "Error Opening Example", f"Could not load the example file:\n{filename}\nPath tried: {example_path}"); logger.error("Failed to open example file: %s from path: %s", filename, example_path)
        else: QMessageBox.warning(self.mw, "Example File Not Found", f"The example file '{filename}' could not be found."); logger.warning("Example file '%s' not found.", filename)

    @pyqtSlot()
    def on_show_quick_start(self):
        guide_path = _get_bundled_file_path("QUICK_START.html", resource_prefix="docs")
        if guide_path:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path)): QMessageBox.warning(self.mw, "Could Not Open Guide", f"Failed to open the Quick Start Guide.\nPath: {guide_path}"); logger.warning("Failed to open Quick Start Guide from: %s", guide_path)
        else: QMessageBox.information(self.mw, "Guide Not Found", "The Quick Start Guide (QUICK_START.html) was not found.")

    @pyqtSlot()
    def on_about(self):
        from config import APP_NAME, APP_VERSION, COLOR_ACCENT_PRIMARY, COLOR_TEXT_SECONDARY # Local import for config values
        QMessageBox.about(self.mw, f"About {APP_NAME}",
                          f"""<h3 style='color:{COLOR_ACCENT_PRIMARY};'>{APP_NAME} v{APP_VERSION}</h3>
                             <p>A graphical tool for designing and simulating Brain State Machines.</p>
                             <ul>
                                 <li>Visual FSM design and editing.</li>
                                 <li>Internal Python-based FSM simulation.</li>
                                 <li>MATLAB/Simulink model generation and simulation control.</li>
                                 <li>AI Assistant for FSM generation and chat (requires Google AI API Key for Gemini).</li>
                             </ul>
                             <p style='font-size:8pt;color:{COLOR_TEXT_SECONDARY};'>
                                 This software is intended for research and educational purposes.
                                 Always verify generated models and code.
                             </p>
                          """)