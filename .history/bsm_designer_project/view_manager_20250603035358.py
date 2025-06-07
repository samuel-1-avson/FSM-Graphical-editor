# bsm_designer_project/view_manager.py

import logging
from PyQt5.QtCore import QObject, pyqtSlot
from PyQt5.QtWidgets import QAction # For type hinting if actions are passed

logger = logging.getLogger(__name__)

class ViewManager(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window

        if hasattr(self.mw, 'view') and self.mw.view:
            try:
                self.mw.view.zoomChanged.disconnect(self.update_zoom_status_display)
            except TypeError: # Was not connected
                pass
            self.mw.view.zoomChanged.connect(self.update_zoom_status_display)

        if hasattr(self.mw, 'scene') and self.mw.scene:
            try:
                self.mw.scene.selectionChanged.disconnect(self.update_zoom_to_selection_action_enable_state)
            except TypeError: # Was not connected
                pass
            self.mw.scene.selectionChanged.connect(self.update_zoom_to_selection_action_enable_state)
        # ... (rest of __init__)

    def cleanup(self):
        logger.debug("ViewManager: Cleaning up signal connections.")
        if hasattr(self.mw, 'view') and self.mw.view and self.mw.view is not None:
            try:
                self.mw.view.zoomChanged.disconnect(self.update_zoom_status_display)
            except (TypeError, RuntimeError): # Add RuntimeError for "deleted C/C++ object"
                pass # Signal might already be disconnected or object deleted
        if hasattr(self.mw, 'scene') and self.mw.scene and self.mw.scene is not None:
            try:
                self.mw.scene.selectionChanged.disconnect(self.update_zoom_to_selection_action_enable_state)
            except (TypeError, RuntimeError): # Add RuntimeError
                pass
        self.mw = None # Break reference to main window


    @pyqtSlot(float)
    def update_zoom_status_display(self, scale_factor: float):
        if hasattr(self.mw, 'zoom_status_label'):
            zoom_percentage = int(scale_factor * 100)
            self.mw.zoom_status_label.setText(f"Zoom: {zoom_percentage}%")

    @pyqtSlot()
    def update_zoom_to_selection_action_enable_state(self):
        if hasattr(self.mw, 'zoom_to_selection_action'):
            has_selection = False
            if hasattr(self.mw, 'scene') and self.mw.scene:
                has_selection = bool(self.mw.scene.selectedItems())
            self.mw.zoom_to_selection_action.setEnabled(has_selection)

    @pyqtSlot()
    def on_zoom_to_selection(self):
        if hasattr(self.mw, 'view') and self.mw.view and hasattr(self.mw.view, 'zoom_to_selection'):
            self.mw.view.zoom_to_selection()

    @pyqtSlot()
    def on_fit_diagram_in_view(self):
        if hasattr(self.mw, 'view') and self.mw.view and hasattr(self.mw.view, 'fit_diagram_in_view'):
            self.mw.view.fit_diagram_in_view()

    @pyqtSlot(bool)
    def on_toggle_snap_to_grid(self, checked: bool):
        if hasattr(self.mw, 'scene'):
            self.mw.scene.snap_to_grid_enabled = checked
            logger.info(f"Snap to Grid {'enabled' if checked else 'disabled'}.")

    @pyqtSlot(bool)
    def on_toggle_snap_to_objects(self, checked: bool):
        if hasattr(self.mw, 'scene'):
            self.mw.scene.snap_to_objects_enabled = checked
            logger.info(f"Snap to Objects {'enabled' if checked else 'disabled'}.")

    @pyqtSlot(bool)
    def on_toggle_show_snap_guidelines(self, checked: bool):
        if hasattr(self.mw, 'scene') and hasattr(self.mw.scene, '_show_dynamic_snap_guidelines'):
            self.mw.scene._show_dynamic_snap_guidelines = checked
            if not checked and hasattr(self.mw.scene, '_clear_dynamic_guidelines'):
                self.mw.scene._clear_dynamic_guidelines()
            logger.info(f"Dynamic Snap Guidelines {'shown' if checked else 'hidden'}.")

    # Methods to connect actions from MainWindow to this manager
    def connect_zoom_actions(self):
        if hasattr(self.mw, 'zoom_in_action') and hasattr(self.mw, 'view') and self.mw.view:
            self.mw.zoom_in_action.triggered.connect(self.mw.view.zoom_in)
        if hasattr(self.mw, 'zoom_out_action') and hasattr(self.mw, 'view') and self.mw.view:
            self.mw.zoom_out_action.triggered.connect(self.mw.view.zoom_out)
        if hasattr(self.mw, 'reset_zoom_action') and hasattr(self.mw, 'view') and self.mw.view:
            self.mw.reset_zoom_action.triggered.connect(self.mw.view.reset_view_and_zoom)
        if hasattr(self.mw, 'zoom_to_selection_action'):
            self.mw.zoom_to_selection_action.triggered.connect(self.on_zoom_to_selection)
        if hasattr(self.mw, 'fit_diagram_action'):
            self.mw.fit_diagram_action.triggered.connect(self.on_fit_diagram_in_view)

    def connect_snap_actions(self):
        if hasattr(self.mw, 'snap_to_grid_action'):
            self.mw.snap_to_grid_action.triggered.connect(self.on_toggle_snap_to_grid)
        if hasattr(self.mw, 'snap_to_objects_action'):
            self.mw.snap_to_objects_action.triggered.connect(self.on_toggle_snap_to_objects)
        if hasattr(self.mw, 'show_snap_guidelines_action'):
            self.mw.show_snap_guidelines_action.triggered.connect(self.on_toggle_show_snap_guidelines)