# bsm_designer_project/undo_commands.py

from PyQt5.QtWidgets import QUndoCommand, QGraphicsItem
from PyQt5.QtCore import QPointF
# Ensure GraphicsStateItem is importable. If in same dir, relative import is fine.
# Adjust if your project structure is different.
try:
    from .graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
except ImportError:
    from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem

from .config import DEFAULT_EXECUTION_ENV # Import default
import logging # Added for logging

logger = logging.getLogger(__name__)

class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item_instance = item

        self.item_data = item.get_data()
        self.item_data['_type'] = item.type()
        item_name_for_log = "UnknownItem" # Default

        if isinstance(item, GraphicsStateItem):
            self.item_data['_type'] = GraphicsStateItem.Type # Ensure correct type for reconstruction
            item_name_for_log = item.text_label
        elif isinstance(item, GraphicsTransitionItem):
            self.item_data['_type'] = GraphicsTransitionItem.Type
            self.item_data['_start_name'] = item.start_item.text_label if item.start_item else None
            self.item_data['_end_name'] = item.end_item.text_label if item.end_item else None
            event_str = item.event_str or "Unnamed Event"
            item_name_for_log = f"Transition ({event_str} from '{self.item_data['_start_name']}' to '{self.item_data['_end_name']}')"
        elif isinstance(item, GraphicsCommentItem):
            self.item_data['_type'] = GraphicsCommentItem.Type
            plain_text = item.toPlainText()
            item_name_for_log = plain_text[:20] + "..." if len(plain_text) > 23 else plain_text
        
        logger.debug(f"AddItemCommand: Initialized for item '{item_name_for_log}' of type {type(item).__name__}. Desc: {description}")


    def _get_display_name_for_log(self, item_instance_or_data):
        # Helper to get a display name for logging, works with instance or stored data
        is_instance = isinstance(item_instance_or_data, QGraphicsItem)
        
        item_type = item_instance_or_data.type() if is_instance else item_instance_or_data.get('_type')
        
        if item_type == GraphicsStateItem.Type:
            name = item_instance_or_data.text_label if is_instance else item_instance_or_data.get('name')
            return name or "StateItem"
        elif item_type == GraphicsTransitionItem.Type:
            event = item_instance_or_data.event_str if is_instance else item_instance_or_data.get('event')
            start_name = ""
            end_name = ""
            if is_instance:
                start_name = item_instance_or_data.start_item.text_label if item_instance_or_data.start_item else "UnknownSrc"
                end_name = item_instance_or_data.end_item.text_label if item_instance_or_data.end_item else "UnknownTgt"
            else: # From data
                start_name = item_instance_or_data.get('_start_name', "UnknownSrc")
                end_name = item_instance_or_data.get('_end_name', "UnknownTgt")
            return f"Transition ({event or 'unnamed'} from '{start_name}' to '{end_name}')"
        elif item_type == GraphicsCommentItem.Type:
            plain_text = item_instance_or_data.toPlainText() if is_instance else item_instance_or_data.get('text')
            return (plain_text[:20] + "..." if plain_text and len(plain_text) > 23 else plain_text) or "CommentItem"
        return "UnknownItem"

    def redo(self):
        display_name = self._get_display_name_for_log(self.item_instance)

        if self.item_instance.scene() is None:
            self.scene.addItem(self.item_instance)
            logger.debug(f"AddItemCommand: Redo - Added item '{display_name}' to scene.")
        else:
            logger.debug(f"AddItemCommand: Redo - Item '{display_name}' was already in scene. Not re-adding.")

        if isinstance(self.item_instance, GraphicsStateItem) and self.scene.parent_window:
            if hasattr(self.scene.parent_window, 'connect_state_item_signals'):
                self.scene.parent_window.connect_state_item_signals(self.item_instance)
                logger.debug(f"AddItemCommand: Redo - Connected signals for state '{self.item_instance.text_label}'.")

        if isinstance(self.item_instance, GraphicsTransitionItem):
            start_node = self.scene.get_state_by_name(self.item_data['_start_name'])
            end_node = self.scene.get_state_by_name(self.item_data['_end_name'])
            if start_node and end_node:
                self.item_instance.start_item = start_node
                self.item_instance.end_item = end_node
                self.item_instance.set_properties(
                    event_str=self.item_data['event'],
                    condition_str=self.item_data['condition'],
                    action_language=self.item_data.get('action_language', DEFAULT_EXECUTION_ENV),
                    action_str=self.item_data['action'],
                    color_hex=self.item_data.get('color'),
                    description=self.item_data.get('description', ""),
                    offset=QPointF(self.item_data['control_offset_x'], self.item_data['control_offset_y'])
                )
                self.item_instance.update_path()
                logger.debug(f"AddItemCommand: Redo - Relinked transition '{display_name}'")
            else:
                log_msg = f"Error (Redo Add Transition): Could not link transition. State(s) missing for '{display_name}'. Source: '{self.item_data['_start_name']}', Target: '{self.item_data['_end_name']}'."
                logger.error(f"AddItemCommand: {log_msg}")
                if hasattr(self.scene, 'log_function'):
                    self.scene.log_function(log_msg, level="ERROR")

        self.scene.clearSelection()
        self.item_instance.setSelected(True)
        self.scene.set_dirty(True)
        self.scene.scene_content_changed_for_find.emit()
        self.scene.run_all_validations(f"AddItemCommand_Redo_{display_name}")

    def undo(self):
        display_name = self._get_display_name_for_log(self.item_instance)

        if self.item_instance.scene() == self.scene:
            self.scene.removeItem(self.item_instance)
            logger.debug(f"AddItemCommand: Undo - Removed item '{display_name}' from scene.")
        else:
            logger.debug(f"AddItemCommand: Undo - Item '{display_name}' was not in the scene to remove.")

        self.scene.set_dirty(True)
        self.scene.scene_content_changed_for_find.emit()
        self.scene.run_all_validations(f"AddItemCommand_Undo_{display_name}")


class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items_to_remove, description="Remove Items"):
        super().__init__(description)
        self.scene = scene
        self.removed_items_data = [] # Store data to recreate items
        # self.item_instances_for_quick_toggle = list(items_to_remove) # Keep direct references for redo initially

        for item in items_to_remove:
            item_data_entry = item.get_data()
            item_data_entry['_type'] = item.type()
            if isinstance(item, GraphicsTransitionItem):
                item_data_entry['_start_name'] = item.start_item.text_label if item.start_item else None
                item_data_entry['_end_name'] = item.end_item.text_label if item.end_item else None
            self.removed_items_data.append(item_data_entry)
        logger.debug(f"RemoveItemsCommand: Initialized with {len(self.removed_items_data)} items to remove.")


    def redo(self):
        # When redoing a remove, we need to find the items currently in the scene
        # that match the data we stored, because the original instances might be gone
        # if an undo/redo sequence involving add/remove happened.
        # This is complex if IDs are not persistent or if item properties can change.
        # For now, if we simply re-add from stored data on undo, redo will remove those instances.
        
        # Simplification: Assume undo re-adds the exact instances or recreates them and
        # they are then targeted for removal here. The logic in undo needs to manage
        # self.item_instances_for_quick_toggle.

        # This redo relies on the instances being correctly put back by undo()
        # or that self.item_instances_for_quick_toggle holds valid references after an undo.
        # If undo recreates items, self.item_instances_for_quick_toggle must be updated by undo().
        
        items_actually_removed_this_redo = []
        for item_data in self.removed_items_data: # Iterate over stored data to identify what to remove
            item_to_remove = None
            if item_data['_type'] == GraphicsStateItem.Type:
                item_to_remove = self.scene.get_state_by_name(item_data['name'])
            elif item_data['_type'] == GraphicsCommentItem.Type:
                # Comments don't have unique names, find by properties (can be tricky)
                # For simplicity, if undo recreates, it should populate instances list.
                # This is a limitation if we don't have persistent unique IDs for comments.
                # Let's assume for now undo correctly restores instances to item_instances_for_quick_toggle.
                # We'll iterate through scene items and match.
                for scene_item in self.scene.items():
                    if isinstance(scene_item, GraphicsCommentItem) and \
                       scene_item.x() == item_data['x'] and \
                       scene_item.y() == item_data['y'] and \
                       scene_item.toPlainText() == item_data['text']:
                        item_to_remove = scene_item
                        break
            elif item_data['_type'] == GraphicsTransitionItem.Type:
                 # Find by source, target, and event primarily
                 for scene_item in self.scene.items():
                     if isinstance(scene_item, GraphicsTransitionItem):
                         if scene_item.start_item and scene_item.start_item.text_label == item_data['_start_name'] and \
                            scene_item.end_item and scene_item.end_item.text_label == item_data['_end_name'] and \
                            scene_item.event_str == item_data['event']: # Add more checks if needed
                             item_to_remove = scene_item
                             break
            
            if item_to_remove and item_to_remove.scene() == self.scene:
                self.scene.removeItem(item_to_remove)
                items_actually_removed_this_redo.append(item_to_remove)
                logger.debug(f"RemoveItemsCommand: Redo - Removed item type {item_data['_type']} with data {item_data.get('name', item_data.get('text', 'Transition'))}")

        self.scene.set_dirty(True)
        self.scene.scene_content_changed_for_find.emit()
        self.scene.run_all_validations(f"RemoveItemsCommand_Redo_{len(items_actually_removed_this_redo)}") # Added validation call
        logger.debug(f"RemoveItemsCommand: Redo - Total items removed: {len(items_actually_removed_this_redo)}")


    def undo(self):
        newly_re_added_instances = []
        states_map_for_undo = {}

        # First pass: re-create states and comments, map states by name
        for item_data in self.removed_items_data:
            instance_to_add = None
            item_name_for_log = item_data.get('name', item_data.get('text', 'UnknownItem'))
            logger.debug(f"RemoveItemsCommand: Undo - Attempting to recreate item {item_name_for_log} of type {item_data['_type']}")

            if item_data['_type'] == GraphicsStateItem.Type:
                # Check if a state with this name already exists (e.g. from a different undo path)
                if self.scene.get_state_by_name(item_data['name']):
                    logger.warning(f"RemoveItemsCommand: Undo - State '{item_data['name']}' already exists in scene. Skipping recreation for this specific instance data.")
                    # Try to find an existing matching item to re-populate self.item_instances_for_quick_toggle
                    # This part is complex and error-prone if properties changed.
                    # For now, we'll rely on AddItemCommand being the primary way items get added.
                    continue 

                state = GraphicsStateItem(item_data['x'], item_data['y'],
                                          item_data['width'], item_data['height'], item_data['name'],
                                          item_data['is_initial'], item_data['is_final'],
                                          item_data.get('color'),
                                          action_language=item_data.get('action_language', DEFAULT_EXECUTION_ENV),
                                          entry_action=item_data.get('entry_action', ""),
                                          during_action=item_data.get('during_action', ""),
                                          exit_action=item_data.get('exit_action', ""),
                                          description=item_data.get('description', ""),
                                          is_superstate=item_data.get('is_superstate', False),
                                          sub_fsm_data=item_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]})
                                          )
                instance_to_add = state
                states_map_for_undo[state.text_label] = state
                if self.scene.parent_window and hasattr(self.scene.parent_window, 'connect_state_item_signals'):
                    self.scene.parent_window.connect_state_item_signals(state)
            elif item_data['_type'] == GraphicsCommentItem.Type:
                comment = GraphicsCommentItem(item_data['x'], item_data['y'], item_data['text'])
                comment.setTextWidth(item_data.get('width', 150))
                instance_to_add = comment

            if instance_to_add:
                self.scene.addItem(instance_to_add)
                newly_re_added_instances.append(instance_to_add)
                logger.debug(f"RemoveItemsCommand: Undo - Re-added item {item_name_for_log}")


        # Second pass: re-create transitions using the mapped states
        for item_data in self.removed_items_data:
            if item_data['_type'] == GraphicsTransitionItem.Type:
                src_item = states_map_for_undo.get(item_data['_start_name'])
                tgt_item = states_map_for_undo.get(item_data['_end_name'])
                if src_item and tgt_item:
                    trans = GraphicsTransitionItem(src_item, tgt_item,
                                                   event_str=item_data['event'],
                                                   condition_str=item_data['condition'],
                                                   action_language=item_data.get('action_language', DEFAULT_EXECUTION_ENV),
                                                   action_str=item_data['action'],
                                                   color=item_data.get('color'),
                                                   description=item_data.get('description',""))
                    trans.set_control_point_offset(QPointF(item_data['control_offset_x'], item_data['control_offset_y']))
                    self.scene.addItem(trans)
                    newly_re_added_instances.append(trans)
                    logger.debug(f"RemoveItemsCommand: Undo - Re-added transition '{item_data.get('event', 'Unnamed Trans')}'")
                else:
                    log_msg = f"Error (Undo Remove): Could not re-link transition. States '{item_data['_start_name']}' or '{item_data['_end_name']}' missing for event '{item_data.get('event','Unnamed Trans')}'."
                    logger.error(f"RemoveItemsCommand: {log_msg}")
                    if hasattr(self.scene, 'log_function'):
                        self.scene.log_function(log_msg, level="ERROR")

        # self.item_instances_for_quick_toggle = newly_re_added_instances # This caused issues. Redo should find them.
        self.scene.set_dirty(True)
        self.scene.scene_content_changed_for_find.emit()
        self.scene.run_all_validations(f"RemoveItemsCommand_Undo_{len(newly_re_added_instances)}") # Added validation call
        logger.debug(f"RemoveItemsCommand: Undo - Total items re-added: {len(newly_re_added_instances)}")


class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_and_positions_info, description="Move Items"):
        super().__init__(description)
        self.items_and_positions_info = items_and_positions_info
        self.scene_ref = None
        if self.items_and_positions_info:
            self.scene_ref = self.items_and_positions_info[0][0].scene()

    def _apply_positions(self, use_new_positions: bool):
        if not self.scene_ref: return
        for item, old_pos, new_pos in self.items_and_positions_info:
            target_pos = new_pos if use_new_positions else old_pos
            item.setPos(target_pos)
            if isinstance(item, GraphicsStateItem):
                self.scene_ref._update_connected_transitions(item)
        self.scene_ref.update()
        self.scene_ref.set_dirty(True)

    def redo(self):
        self._apply_positions(use_new_positions=True)
        logger.debug(f"MoveItemsCommand: Redo - Moved {len(self.items_and_positions_info)} items.")
        if self.scene_ref: self.scene_ref.run_all_validations("MoveItemsCommand_Redo") # Added validation


    def undo(self):
        self._apply_positions(use_new_positions=False)
        logger.debug(f"MoveItemsCommand: Undo - Moved {len(self.items_and_positions_info)} items back.")
        if self.scene_ref: self.scene_ref.run_all_validations("MoveItemsCommand_Undo") # Added validation


class EditItemPropertiesCommand(QUndoCommand):
    def __init__(self, item, old_props_data, new_props_data, description="Edit Properties"):
        super().__init__(description)
        self.item = item
        self.old_props_data = old_props_data
        self.new_props_data = new_props_data
        self.scene_ref = item.scene()
        item_name_for_log = self.new_props_data.get('name', self.new_props_data.get('event', self.new_props_data.get('text', type(item).__name__)))
        logger.debug(f"EditItemPropertiesCommand: Initialized for item '{item_name_for_log}'. Old: {old_props_data}, New: {new_props_data}")


    def _apply_properties(self, props_to_apply):
        if not self.item or not self.scene_ref:
            logger.error("EditItemPropertiesCommand: Item or scene reference is missing.")
            return

        original_name_if_state = None

        if isinstance(self.item, GraphicsStateItem):
            original_name_if_state = self.item.text_label
            self.item.set_properties(
                name=props_to_apply['name'],
                is_initial=props_to_apply.get('is_initial', False),
                is_final=props_to_apply.get('is_final', False),
                color_hex=props_to_apply.get('color'),
                action_language=props_to_apply.get('action_language', DEFAULT_EXECUTION_ENV),
                entry=props_to_apply.get('entry_action', ""),
                during=props_to_apply.get('during_action', ""),
                exit_a=props_to_apply.get('exit_action', ""),
                desc=props_to_apply.get('description', ""),
                is_superstate_prop=props_to_apply.get('is_superstate'),
                sub_fsm_data_prop=props_to_apply.get('sub_fsm_data')
            )
            if original_name_if_state != props_to_apply['name']:
                self.scene_ref._update_transitions_for_renamed_state(original_name_if_state, props_to_apply['name'])
                # scene_content_changed_for_find will be emitted by _update_transitions_for_renamed_state

        elif isinstance(self.item, GraphicsTransitionItem):
            self.item.set_properties(event_str=props_to_apply.get('event',""),
                                     condition_str=props_to_apply.get('condition',""),
                                     action_language=props_to_apply.get('action_language', DEFAULT_EXECUTION_ENV),
                                     action_str=props_to_apply.get('action',""),
                                     color_hex=props_to_apply.get('color'),
                                     description=props_to_apply.get('description',""),
                                     offset=QPointF(props_to_apply['control_offset_x'], props_to_apply['control_offset_y']))
        elif isinstance(self.item, GraphicsCommentItem):
            self.item.set_properties(text=props_to_apply['text'], width=props_to_apply.get('width'))
            self.scene_ref.scene_content_changed_for_find.emit() # Comments don't have names, but list might need update if text is shown there

        self.item.update()
        self.scene_ref.update()
        self.scene_ref.set_dirty(True)
        # If it's not a state name change, but other properties changed, Find dialog doesn't need update typically.
        # However, if properties dock or other UI relies on this, a more generic signal might be needed from scene.
        # For now, only state name changes and add/remove trigger the find dialog refresh.

    def redo(self):
        logger.debug(f"EditItemPropertiesCommand: Redo - Applying new properties to item.")
        self._apply_properties(self.new_props_data)
        if self.scene_ref: self.scene_ref.run_all_validations("EditItemProperties_Redo") # Added validation


    def undo(self):
        logger.debug(f"EditItemPropertiesCommand: Undo - Applying old properties to item.")
        self._apply_properties(self.old_props_data)
        if self.scene_ref: self.scene_ref.run_all_validations("EditItemProperties_Undo") # Added validation