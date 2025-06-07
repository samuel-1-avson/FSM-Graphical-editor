# bsm_designer_project/view_manager.py

import logging
from PyQt5.QtCore import QObject, pyqtSlot
from PyQt5.QtWidgets import QAction # For type hinting if actions are passed
from PyQt5 import sip # <--- ADD THIS IMPORT

logger = logging.getLogger(__name__)

class ViewManager(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window # Reference to MainWindow
        self._connected_signals = [] # Keep track of connections

        if hasattr(self.mw, 'view') and self.mw.view:
            try:
                # Try to disconnect first to avoid multiple connections if re-initialized
                self.mw.view.zoomChanged.disconnect(self.update_zoom_status_display)
            except (TypeError, RuntimeError): # Was not connected or object might be in a weird state
                pass
            self.mw.view.zoomChanged.connect(self.update_zoom_status_display)
            self._connected_signals.append((self.mw.view.zoomChanged, self.update_zoom_status_display))

        if hasattr(self.mw, 'scene') and self.mw.scene:
            try:
                # Try to disconnect first
                self.mw.scene.selectionChanged.disconnect(self.update_zoom_to_selection_action_enable_state)
            except (TypeError, RuntimeError):
                pass
            self.mw.scene.selectionChanged.connect(self.update_zoom_to_selection_action_enable_state)
            self._connected_signals.append((self.mw.scene.selectionChanged, self.update_zoom_to_selection_action_enable_state))
        
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
                if signal_obj and not sip.isdeleted(signal_obj): # Check if signal emitter is still valid
                    signal_obj.disconnect(slot_func)
            except (TypeError, RuntimeError) as e: # TypeError if not connected, RuntimeError if obj deleted during call
                logger.debug(f"ViewManager: Error/Warning disconnecting signal (obj may be gone or not connected): {e}")
        self._connected_signals.clear()
        self.mw = None

    @pyqtSlot(float)
    def update_zoom_status_display(self, scale_factor: float):
        if not self.mw or not hasattr(self.mw, 'zoom_status_label') or not self.mw.zoom_status_label or sip.isdeleted(self.mw.zoom_status_label):
            return
        zoom_percentage = int(scale_factor * 100)
        self.mw.zoom_status_label.setText(f"Zoom: {zoom_percentage}%")

    @pyqtSlot()
    def update_zoom_to_selection_action_enable_state(self):
        if not self.mw or not hasattr(self.mw, 'zoom_to_selection_action') or not self.mw.zoom_to_selection_action or sip.isdeleted(self.mw.zoom_to_selection_action):
            return
        
        has_selection = False
        if hasattr(self.mw, 'scene') and self.mw.scene:
            try:
                if sip.isdeleted(self.mw.scene):
                    logger.warning("ViewManager: Scene C++ object deleted in update_zoom_to_selection_action_enable_state.")
                    self.mw.zoom_to_selection_action.setEnabled(False) # Disable if scene is gone
                    return
                has_selection = bool(self.mw.scene.selectedItems())
            except RuntimeError:
                logger.warning("ViewManager: Scene accessed after deletion in update_zoom_to_selection_action_enable_state (RuntimeError).")
                self.mw.zoom_to_selection_action.setEnabled(False)
                return
            except AttributeError:
                logger.warning("ViewManager: Scene attribute missing in update_zoom_to_selection_action_enable_state.")
                self.mw.zoom_to_selection_action.setEnabled(False)
                return
        self.mw.zoom_to_selection_action.setEnabled(has_selection)

    # ... (rest of ViewManager methods: on_zoom_to_selection, on_fit_diagram_in_view, etc.)
    # Make sure to add sip.isdeleted checks in other methods too if they access mw.scene or mw.view
    # For example:

    @pyqtSlot(bool)
    def on_toggle_snap_to_grid(self, checked: bool):
        if not self.mw or not hasattr(self.mw, 'scene') or not self.mw.scene or sip.isdeleted(self.mw.scene):
            return
        self.mw.scene.snap_to_grid_enabled = checked
        logger.info(f"Snap to Grid {'enabled' if checked else 'disabled'}.")

    @pyqtSlot(bool)
    def on_toggle_snap_to_objects(self, checked: bool):
        if not self.mw or not hasattr(self.mw, 'scene') or not self.mw.scene or sip.isdeleted(self.mw.scene):
            return
        self.mw.scene.snap_to_objects_enabled = checked
        logger.info(f"Snap to Objects {'enabled' if checked else 'disabled'}.")

    @pyqtSlot(bool)
    def on_toggle_show_snap_guidelines(self, checked: bool):
        if not self.mw or not hasattr(self.mw, 'scene') or not self.mw.scene or sip.isdeleted(self.mw.scene) or not hasattr(self.mw.scene, '_show_dynamic_snap_guidelines'):
            return
        self.mw.scene._show_dynamic_snap_guidelines = checked
        if not checked and hasattr(self.mw.scene, '_clear_dynamic_guidelines'):
            self.mw.scene._clear_dynamic_guidelines()
        logger.info(f"Dynamic Snap Guidelines {'shown' if checked else 'hidden'}.")

    # ... (connect_zoom_actions, connect_snap_actions remain the same)
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