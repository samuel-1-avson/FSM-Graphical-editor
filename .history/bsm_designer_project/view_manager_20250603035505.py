# bsm_designer_project/view_manager.py

import logging
from PyQt5.QtCore import QObject, pyqtSlot
from PyQt5.QtWidgets import QAction # For type hinting if actions are passed

logger = logging.getLogger(__name__)

class ViewManager(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window # Reference to MainWindow
        self._connected_signals = [] # Keep track of connections

        if hasattr(self.mw, 'view') and self.mw.view:
            try:
                self.mw.view.zoomChanged.connect(self.update_zoom_status_display)
                self._connected_signals.append((self.mw.view.zoomChanged, self.update_zoom_status_display))
            except Exception as e:
                logger.error(f"ViewManager: Error connecting view.zoomChanged: {e}")

        if hasattr(self.mw, 'scene') and self.mw.scene:
            try:
                self.mw.scene.selectionChanged.connect(self.update_zoom_to_selection_action_enable_state)
                self._connected_signals.append((self.mw.scene.selectionChanged, self.update_zoom_to_selection_action_enable_state))
            except Exception as e:
                logger.error(f"ViewManager: Error connecting scene.selectionChanged: {e}")

        # Initialize snap action states from scene if actions are available
        if hasattr(self.mw, 'snap_to_grid_action') and hasattr(self.mw.scene, 'snap_to_grid_enabled'):
            self.mw.snap_to_grid_action.setChecked(self.mw.scene.snap_to_grid_enabled)
        if hasattr(self.mw, 'snap_to_objects_action') and hasattr(self.mw.scene, 'snap_to_objects_enabled'):
            self.mw.snap_to_objects_action.setChecked(self.mw.scene.snap_to_objects_enabled)
        if hasattr(self.mw, 'show_snap_guidelines_action') and hasattr(self.mw.scene, '_show_dynamic_snap_guidelines'):
            self.mw.show_snap_guidelines_action.setChecked(self.mw.scene._show_dynamic_snap_guidelines)

    def cleanup(self):
        logger.debug("ViewManager: Cleaning up signal connections.")
        for signal_obj, slot_func in self._connected_signals:
            try:
                if signal_obj: # Check if the object emitting the signal still exists
                    signal_obj.disconnect(slot_func)
            except (TypeError, RuntimeError) as e:
                logger.debug(f"ViewManager: Error disconnecting signal (obj may be gone): {e}")
        self._connected_signals.clear()
        self.mw = None # Break reference to main window

    @pyqtSlot(float)
    def update_zoom_status_display(self, scale_factor: float):
        if not self.mw or not hasattr(self.mw, 'zoom_status_label') or not self.mw.zoom_status_label:
            return
        zoom_percentage = int(scale_factor * 100)
        self.mw.zoom_status_label.setText(f"Zoom: {zoom_percentage}%")

    @pyqtSlot()
    def update_zoom_to_selection_action_enable_state(self):
        if not self.mw or not hasattr(self.mw, 'zoom_to_selection_action') or not self.mw.zoom_to_selection_action:
            return
        
        has_selection = False
        if hasattr(self.mw, 'scene') and self.mw.scene:
            try:
                # Check if scene object is still valid before accessing methods
                if sip_is_deleted(self.mw.scene): # Requires: from PyQt5 import sip; then use sip.isdeleted
                    logger.warning("ViewManager: Scene C++ object deleted in update_zoom_to_selection_action_enable_state.")
                    return
                has_selection = bool(self.mw.scene.selectedItems())
            except RuntimeError:
                logger.warning("ViewManager: Scene accessed after deletion in update_zoom_to_selection_action_enable_state (RuntimeError).")
                return
            except AttributeError: # Scene might be None
                logger.warning("ViewManager: Scene attribute missing in update_zoom_to_selection_action_enable_state.")
                return
        self.mw.zoom_to_selection_action.setEnabled(has_selection)


    @pyqtSlot()
    def on_zoom_to_selection(self):
        if not self.mw or not hasattr(self.mw, 'view') or not self.mw.view or not hasattr(self.mw.view, 'zoom_to_selection'):
            return
        self.mw.view.zoom_to_selection()

    @pyqtSlot()
    def on_fit_diagram_in_view(self):
        if not self.mw or not hasattr(self.mw, 'view') or not self.mw.view or not hasattr(self.mw.view, 'fit_diagram_in_view'):
            return
        self.mw.view.fit_diagram_in_view()

    @pyqtSlot(bool)
    def on_toggle_snap_to_grid(self, checked: bool):
        if not self.mw or not hasattr(self.mw, 'scene') or not self.mw.scene:
            return
        self.mw.scene.snap_to_grid_enabled = checked
        logger.info(f"Snap to Grid {'enabled' if checked else 'disabled'}.")

    @pyqtSlot(bool)
    def on_toggle_snap_to_objects(self, checked: bool):
        if not self.mw or not hasattr(self.mw, 'scene') or not self.mw.scene:
            return
        self.mw.scene.snap_to_objects_enabled = checked
        logger.info(f"Snap to Objects {'enabled' if checked else 'disabled'}.")

    @pyqtSlot(bool)
    def on_toggle_show_snap_guidelines(self, checked: bool):
        if not self.mw or not hasattr(self.mw, 'scene') or not self.mw.scene or not hasattr(self.mw.scene, '_show_dynamic_snap_guidelines'):
            return
        self.mw.scene._show_dynamic_snap_guidelines = checked
        if not checked and hasattr(self.mw.scene, '_clear_dynamic_guidelines'):
            self.mw.scene._clear_dynamic_guidelines()
        logger.info(f"Dynamic Snap Guidelines {'shown' if checked else 'hidden'}.")

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

# You'll need to import sip for sip.isdeleted()
# from PyQt5 import sip # Add this at the top of view_manager.py
# then use: if sip.isdeleted(self.mw.scene):