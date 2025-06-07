# bsm_designer_project/alignment_manager.py

import logging
import math # For hypot if needed in more complex distribution
from PyQt5.QtCore import QObject, pyqtSlot, QRectF
from PyQt5.QtWidgets import QGraphicsItem, QAction, QStyle # For type hinting & QAction
from PyQt5.QtGui import QIcon # For QIcon

# Assuming these are in the same project path
from graphics_items import GraphicsStateItem, GraphicsCommentItem
from undo_commands import MoveItemsCommand
from utils import get_standard_icon # For icons

logger = logging.getLogger(__name__)

class AlignmentManager(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window # Reference to MainWindow

        # Create and own the actions
        self._create_actions()

        # Connect to scene selectionChanged if MainWindow doesn't do it for this manager
        if hasattr(self.mw, 'scene') and self.mw.scene:
            try:
                self.mw.scene.selectionChanged.disconnect(self.update_align_distribute_actions_enable_state)
            except (TypeError, RuntimeError):
                pass
            self.mw.scene.selectionChanged.connect(self.update_align_distribute_actions_enable_state)

        self.update_align_distribute_actions_enable_state() # Initial state

    def _create_actions(self):
        """Creates all alignment and distribution QActions."""
        self.align_left_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "AlL"), "Align Left", self.mw, statusTip="Align selected items to the left")
        self.align_left_action.triggered.connect(lambda: self.on_align_items("left"))

        self.align_center_h_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "AlCH"), "Align Center Horizontally", self.mw, statusTip="Align selected items to their horizontal center")
        self.align_center_h_action.triggered.connect(lambda: self.on_align_items("center_h"))

        self.align_right_action = QAction(get_standard_icon(QStyle.SP_ToolBarHorizontalExtensionButton, "AlR"), "Align Right", self.mw, statusTip="Align selected items to the right")
        self.align_right_action.triggered.connect(lambda: self.on_align_items("right"))

        self.align_top_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "AlT"), "Align Top", self.mw, statusTip="Align selected items to the top")
        self.align_top_action.triggered.connect(lambda: self.on_align_items("top"))

        self.align_middle_v_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "AlMV"), "Align Middle Vertically", self.mw, statusTip="Align selected items to their vertical middle")
        self.align_middle_v_action.triggered.connect(lambda: self.on_align_items("middle_v"))

        self.align_bottom_action = QAction(get_standard_icon(QStyle.SP_ToolBarVerticalExtensionButton, "AlB"), "Align Bottom", self.mw, statusTip="Align selected items to the bottom")
        self.align_bottom_action.triggered.connect(lambda: self.on_align_items("bottom"))

        self.distribute_h_action = QAction(get_standard_icon(QStyle.SP_ArrowLeft, "DstH"), "Distribute Horizontally", self.mw, statusTip="Distribute selected items horizontally")
        self.distribute_h_action.triggered.connect(lambda: self.on_distribute_items("horizontal"))

        self.distribute_v_action = QAction(get_standard_icon(QStyle.SP_ArrowUp, "DstV"), "Distribute Vertically", self.mw, statusTip="Distribute selected items vertically")
        self.distribute_v_action.triggered.connect(lambda: self.on_distribute_items("vertical"))

        self.align_actions = [
            self.align_left_action, self.align_center_h_action, self.align_right_action,
            self.align_top_action, self.align_middle_v_action, self.align_bottom_action
        ]
        self.distribute_actions = [self.distribute_h_action, self.distribute_v_action]

    def get_align_actions(self) -> list[QAction]:
        return self.align_actions

    def get_distribute_actions(self) -> list[QAction]:
        return self.distribute_actions

    def cleanup(self):
        logger.debug("AlignmentManager: Cleaning up signal connections.")
        if hasattr(self.mw, 'scene') and self.mw.scene:
            try:
                self.mw.scene.selectionChanged.disconnect(self.update_align_distribute_actions_enable_state)
            except (TypeError, RuntimeError):
                pass
        self.mw = None


    @pyqtSlot()
    def update_align_distribute_actions_enable_state(self):
        if not self.mw or not hasattr(self.mw, 'scene') or not self.mw.scene:
            selected_count = 0
        else:
            try:
                selected_count = len(self.mw.scene.selectedItems())
            except RuntimeError: # Scene might be deleted
                logger.warning("AlignmentManager: Scene deleted during update_align_distribute_actions_enable_state")
                selected_count = 0


        can_align = selected_count >= 2
        for action in self.align_actions:
            if action: action.setEnabled(can_align)

        can_distribute = selected_count >= 3
        for action in self.distribute_actions:
            if action: action.setEnabled(can_distribute)

    @pyqtSlot(str)
    def on_align_items(self, mode: str):
        if not self.mw or not hasattr(self.mw, 'scene') or not self.mw.scene or \
           not hasattr(self.mw, 'undo_stack') or not self.mw.undo_stack:
            logger.error("AlignmentManager.on_align_items: MainWindow, scene, or undo_stack not available.")
            return

        selected_items = [item for item in self.mw.scene.selectedItems() if isinstance(item, (GraphicsStateItem, GraphicsCommentItem))]
        if len(selected_items) < 2:
            logger.debug(f"Alignment '{mode}': Not enough items selected ({len(selected_items)}).")
            return

        old_positions_map = {item: item.pos() for item in selected_items}
        moved_items_data_for_command = []

        overall_selection_rect = QRectF()
        first = True
        for item in selected_items:
            if first:
                overall_selection_rect = item.sceneBoundingRect()
                first = False
            else:
                overall_selection_rect = overall_selection_rect.united(item.sceneBoundingRect())

        if mode == "left":
            ref_x = overall_selection_rect.left()
            for item in selected_items: item.setPos(ref_x, item.y())
        elif mode == "center_h":
            ref_x_center = overall_selection_rect.center().x()
            for item in selected_items: item.setPos(ref_x_center - item.sceneBoundingRect().width() / 2.0, item.y())
        elif mode == "right":
            ref_x = overall_selection_rect.right()
            for item in selected_items: item.setPos(ref_x - item.sceneBoundingRect().width(), item.y())
        elif mode == "top":
            ref_y = overall_selection_rect.top()
            for item in selected_items: item.setPos(item.x(), ref_y)
        elif mode == "middle_v":
            ref_y_middle = overall_selection_rect.center().y()
            for item in selected_items: item.setPos(item.x(), ref_y_middle - item.sceneBoundingRect().height() / 2.0)
        elif mode == "bottom":
            ref_y = overall_selection_rect.bottom()
            for item in selected_items: item.setPos(item.x(), ref_y - item.sceneBoundingRect().height())
        else:
            logger.warning(f"Unknown alignment mode: {mode}")
            return

        for item in selected_items:
            new_pos = item.pos()
            old_pos = old_positions_map[item]
            if (new_pos - old_pos).manhattanLength() > 0.1: # Check if position actually changed
                moved_items_data_for_command.append((item, old_pos, new_pos))
            if isinstance(item, GraphicsStateItem) and hasattr(self.mw.scene, '_update_connected_transitions'):
                self.mw.scene._update_connected_transitions(item)

        if moved_items_data_for_command:
            cmd = MoveItemsCommand(moved_items_data_for_command, f"Align {mode.replace('_', ' ').title()}")
            self.mw.undo_stack.push(cmd)
            if self.mw.scene: self.mw.scene.set_dirty(True)
            logger.info(f"Aligned {len(moved_items_data_for_command)} items: {mode}")
        else:
            logger.debug(f"Alignment '{mode}': No items actually moved.")


    @pyqtSlot(str)
    def on_distribute_items(self, mode: str):
        if not self.mw or not hasattr(self.mw, 'scene') or not self.mw.scene or \
           not hasattr(self.mw, 'undo_stack') or not self.mw.undo_stack:
            logger.error("AlignmentManager.on_distribute_items: MainWindow, scene, or undo_stack not available.")
            return

        selected_items = [item for item in self.mw.scene.selectedItems() if isinstance(item, (GraphicsStateItem, GraphicsCommentItem))]
        if len(selected_items) < 3: # Distribution needs at least 3 items
            logger.debug(f"Distribution '{mode}': Not enough items selected ({len(selected_items)}). Needs at least 3.")
            return

        old_positions_map = {item: item.pos() for item in selected_items}
        moved_items_data_for_command = []

        if mode == "horizontal":
            selected_items.sort(key=lambda item: item.sceneBoundingRect().left())
            min_x_overall = selected_items[0].sceneBoundingRect().left()
            max_x_overall_right_edge = selected_items[-1].sceneBoundingRect().right()
            
            total_width_of_items = sum(item.sceneBoundingRect().width() for item in selected_items)
            actual_span_covered_by_items_edges = max_x_overall_right_edge - min_x_overall

            if len(selected_items) <= 1: spacing = 0 
            else: spacing = (actual_span_covered_by_items_edges - total_width_of_items) / (len(selected_items) - 1)

            if spacing < 0:
                spacing = 10 
                logger.warning("Distribute Horizontal: Items wider than span or too close, distributing with minimal spacing.")

            current_x_edge = selected_items[0].sceneBoundingRect().left() 
            for i, item in enumerate(selected_items):
                item.setPos(current_x_edge, old_positions_map[item].y()) 
                current_x_edge += item.sceneBoundingRect().width() + spacing

        elif mode == "vertical":
            selected_items.sort(key=lambda item: item.sceneBoundingRect().top())
            min_y_overall = selected_items[0].sceneBoundingRect().top()
            max_y_overall_bottom_edge = selected_items[-1].sceneBoundingRect().bottom()
            total_height_of_items = sum(item.sceneBoundingRect().height() for item in selected_items)
            actual_span_covered_by_items_edges = max_y_overall_bottom_edge - min_y_overall
            if len(selected_items) <= 1: spacing = 0
            else: spacing = (actual_span_covered_by_items_edges - total_height_of_items) / (len(selected_items) - 1)
            if spacing < 0:
                spacing = 10; logger.warning("Distribute Vertical: Items taller than span or too close, distributing with minimal spacing.")
            current_y_edge = selected_items[0].sceneBoundingRect().top()
            for i, item in enumerate(selected_items):
                item.setPos(old_positions_map[item].x(), current_y_edge) 
                current_y_edge += item.sceneBoundingRect().height() + spacing
        else:
            logger.warning(f"Unknown distribution mode: {mode}")
            return

        for item in selected_items:
            new_pos = item.pos()
            old_pos = old_positions_map[item]
            if (new_pos - old_pos).manhattanLength() > 0.1:
                moved_items_data_for_command.append((item, old_pos, new_pos))
            if isinstance(item, GraphicsStateItem) and hasattr(self.mw.scene, '_update_connected_transitions'):
                self.mw.scene._update_connected_transitions(item)

        if moved_items_data_for_command:
            cmd_text = "Distribute Horizontally" if mode == "horizontal" else "Distribute Vertically"
            cmd = MoveItemsCommand(moved_items_data_for_command, cmd_text)
            self.mw.undo_stack.push(cmd)
            if self.mw.scene: self.mw.scene.set_dirty(True)
            logger.info(f"Distributed {len(moved_items_data_for_command)} items: {mode}")
        else:
            logger.debug(f"Distribution '{mode}': No items actually moved.")