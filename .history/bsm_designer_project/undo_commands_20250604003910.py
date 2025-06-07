# bsm_designer_project/undo_commands.py

from PyQt5.QtWidgets import QUndoCommand, QGraphicsItem
from PyQt5.QtCore import QPointF
# Ensure GraphicsStateItem is importable. If in same dir, relative import is fine.
# Adjust if your project structure is different.
try:
    from .graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem
except ImportError:
    from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem, GraphicsHistoryPseudoStateItem

from config import DEFAULT_EXECUTION_ENV # Import default
import logging

logger = logging.getLogger(__name__)

class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item_instance = item # This instance already has a UUID

        # item_data will include the UUID from item.get_data()
        self.item_data = item.get_data() # This now includes 'uuid'
        self.item_data['_type'] = item.type()
        item_name_for_log = self.item_data.get('name', self.item_data.get('text', self.item_data.get('uuid', 'UnknownItem')))

        # For transitions, store source/target UUIDs instead of names for robust relinking
        if isinstance(item, GraphicsTransitionItem):
            self.item_data['_start_uuid'] = item.start_item.uuid if item.start_item else None
            self.item_data['_end_uuid'] = item.end_item.uuid if item.end_item else None
            event_str = item.event_str or "Unnamed Event"
            item_name_for_log = f"Transition ({event_str} from '{self.item_data['_start_uuid']}' to '{self.item_data['_end_uuid']}')"
        elif isinstance(item, GraphicsHistoryPseudoStateItem):
            self.item_data['_parent_superstate_uuid'] = item.parent_superstate_item.uuid if item.parent_superstate_item else None
            self.item_data['_default_target_substate_uuid'] = item.default_target_substate_item.uuid if item.default_target_substate_item else None
            item_name_for_log = f"HistoryItem ({item.uuid})"


        logger.debug(f"AddItemCommand: Initialized for item '{item_name_for_log}' (UUID: {self.item_data.get('uuid')}) of type {type(item).__name__}. Desc: {description}")


    def _get_display_name_for_log(self, item_data):
        # Helper to get a display name for logging from stored data
        item_type = item_data.get('_type')
        uuid_str = item_data.get('uuid', 'NoUUID')

        if item_type == GraphicsStateItem.Type:
            name = item_data.get('name')
            return f"{name or 'StateItem'} ({uuid_str})"
        elif item_type == GraphicsTransitionItem.Type:
            event = item_data.get('event')
            start_uuid = item_data.get('_start_uuid', "UnknownSrcUUID")
            end_uuid = item_data.get('_end_uuid', "UnknownTgtUUID")
            return f"Transition ({event or 'unnamed'} from '{start_uuid}' to '{end_uuid}') ({uuid_str})"
        elif item_type == GraphicsCommentItem.Type:
            plain_text = item_data.get('text')
            return f"Comment '{(plain_text[:20] + '...' if plain_text and len(plain_text) > 23 else plain_text) or ''}' ({uuid_str})"
        elif item_type == GraphicsHistoryPseudoStateItem.Type:
            return f"HistoryItem ({item_data.get('type','H')}) ({uuid_str})"
        return f"UnknownItem ({uuid_str})"

    def redo(self):
        display_name = self._get_display_name_for_log(self.item_data)

        # Check if an item with this UUID already exists (e.g. from another command path)
        existing_item = self.scene.get_item_by_uuid(self.item_data['uuid'])
        if existing_item and existing_item.scene() == self.scene:
            logger.debug(f"AddItemCommand: Redo - Item '{display_name}' already in scene. Not re-adding.")
            self.item_instance = existing_item # Ensure we are working with the scene's instance
        elif self.item_instance.scene() is None:
            self.scene.addItem(self.item_instance)
            logger.debug(f"AddItemCommand: Redo - Added item '{display_name}' to scene.")
        else:
            # This case implies item_instance has a scene but is not the one found by UUID.
            # This should be rare if UUIDs are truly unique and handled correctly.
            logger.warning(f"AddItemCommand: Redo - Item '{display_name}' instance has a different scene or UUID mismatch.")
            # Fallback to trying to add self.item_instance if it's not in any scene.
            if not self.item_instance.scene():
                self.scene.addItem(self.item_instance)


        if isinstance(self.item_instance, GraphicsStateItem) and self.scene.parent_window:
            if hasattr(self.scene.parent_window, 'connect_state_item_signals'):
                self.scene.parent_window.connect_state_item_signals(self.item_instance)

        if isinstance(self.item_instance, GraphicsTransitionItem):
            start_node = self.scene.get_item_by_uuid(self.item_data['_start_uuid'])
            end_node = self.scene.get_item_by_uuid(self.item_data['_end_uuid'])

            if isinstance(start_node, (GraphicsStateItem, GraphicsHistoryPseudoStateItem)) and \
               isinstance(end_node, (GraphicsStateItem, GraphicsHistoryPseudoStateItem)):
                self.item_instance.start_item = start_node
                self.item_instance.end_item = end_node # Target must be a state, or H if transition is to H
                # Properties should be set during __init__ of the item_instance
                self.item_instance.update_path()
                logger.debug(f"AddItemCommand: Redo - Relinked transition '{display_name}'")
            else:
                log_msg = f"Error (Redo Add Transition): Could not link. Start/End UUID not found or invalid type: '{display_name}'."
                logger.error(f"AddItemCommand: {log_msg} Start UUID: {self.item_data['_start_uuid']}, End UUID: {self.item_data['_end_uuid']}")


        self.scene.clearSelection()
        self.item_instance.setSelected(True)
        self.scene.set_dirty(True)
        self.scene.scene_content_changed_for_find.emit()
        self.scene.run_all_validations(f"AddItemCommand_Redo_{display_name}")

    def undo(self):
        display_name = self._get_display_name_for_log(self.item_data)
        item_to_remove = self.scene.get_item_by_uuid(self.item_data['uuid'])

        if item_to_remove and item_to_remove.scene() == self.scene:
            self.scene.removeItem(item_to_remove)
            logger.debug(f"AddItemCommand: Undo - Removed item '{display_name}' from scene.")
        elif self.item_instance.scene() == self.scene: # Fallback if UUID somehow mismatched but instance is there
            self.scene.removeItem(self.item_instance)
            logger.warning(f"AddItemCommand: Undo - Removed item '{display_name}' by instance ref (UUID mismatch or not found).")
        else:
            logger.debug(f"AddItemCommand: Undo - Item '{display_name}' was not in the scene to remove.")

        self.scene.set_dirty(True)
        self.scene.scene_content_changed_for_find.emit()
        self.scene.run_all_validations(f"AddItemCommand_Undo_{display_name}")


class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items_to_remove_instances, description="Remove Items"):
        super().__init__(description)
        self.scene = scene
        self.removed_items_data = []

        # Store full data (including UUIDs) of items to be removed.
        # Also store data of transitions connected to states being removed.
        items_to_fully_process_for_removal = set(items_to_remove_instances)

        for item_instance in items_to_remove_instances:
            if isinstance(item_instance, GraphicsStateItem):
                # Find all transitions connected to this state
                for scene_item in self.scene.items():
                    if isinstance(scene_item, GraphicsTransitionItem):
                        if scene_item.start_item == item_instance or scene_item.end_item == item_instance:
                            items_to_fully_process_for_removal.add(scene_item)
                # Find and add its history pseudo-states
                for h_child in list(item_instance.contained_history_pseudo_states): # Iterate copy
                    items_to_fully_process_for_removal.add(h_child)
                    if h_child.default_history_transition_item:
                        items_to_fully_process_for_removal.add(h_child.default_history_transition_item)


        for item in items_to_fully_process_for_removal:
            item_data_entry = item.get_data() # Includes UUID
            item_data_entry['_type'] = item.type()
            if isinstance(item, GraphicsTransitionItem):
                item_data_entry['_start_uuid'] = item.start_item.uuid if item.start_item else None
                item_data_entry['_end_uuid'] = item.end_item.uuid if item.end_item else None
            elif isinstance(item, GraphicsHistoryPseudoStateItem):
                item_data_entry['_parent_superstate_uuid'] = item.parent_superstate_item.uuid if item.parent_superstate_item else None
                item_data_entry['_default_target_substate_uuid'] = item.default_target_substate_item.uuid if item.default_target_substate_item else None

            self.removed_items_data.append(item_data_entry)

        # Sort for consistent recreation order (States -> H-Items -> Transitions -> Comments)
        def sort_key(data):
            type_order = {GraphicsStateItem.Type: 0, GraphicsHistoryPseudoStateItem.Type: 1, GraphicsTransitionItem.Type: 2, GraphicsCommentItem.Type: 3}
            return type_order.get(data['_type'], 4)
        self.removed_items_data.sort(key=sort_key)

        logger.debug(f"RemoveItemsCommand: Initialized with {len(self.removed_items_data)} items (incl. related) to remove.")


    def redo(self):
        items_actually_removed_this_redo_count = 0
        for item_data in self.removed_items_data:
            item_to_remove = self.scene.get_item_by_uuid(item_data['uuid'])
            if item_to_remove and item_to_remove.scene() == self.scene:
                # Special handling for HistoryPseudoState's parent link
                if isinstance(item_to_remove, GraphicsHistoryPseudoStateItem) and item_to_remove.parent_superstate_item:
                    item_to_remove.parent_superstate_item.remove_history_pseudo_state(item_to_remove)
                self.scene.removeItem(item_to_remove)
                items_actually_removed_this_redo_count += 1
                display_name = AddItemCommand._get_display_name_for_log(self, item_data) # Use helper
                logger.debug(f"RemoveItemsCommand: Redo - Removed item '{display_name}'")

        self.scene.set_dirty(True)
        self.scene.scene_content_changed_for_find.emit()
        self.scene.run_all_validations("RemoveItemsCommand_Redo")
        logger.debug(f"RemoveItemsCommand: Redo - Total items removed: {items_actually_removed_this_redo_count}")

    def undo(self):
        # Recreate items from stored data, respecting their original UUIDs
        # This is important so that other commands or scene logic can find them
        recreated_item_instances_map = {} # Map UUID to new instance

        # First pass: recreate states and comments, map by UUID
        for item_data in self.removed_items_data:
            item_uuid = item_data['uuid']
            if self.scene.get_item_by_uuid(item_uuid): # Should not happen if redo worked
                logger.warning(f"RemoveItemsCommand: Undo - Item with UUID '{item_uuid}' already in scene. Skipping recreation.")
                # Potentially re-map to existing instance if needed
                recreated_item_instances_map[item_uuid] = self.scene.get_item_by_uuid(item_uuid)
                continue

            instance_to_add = None
            display_name = AddItemCommand._get_display_name_for_log(self, item_data) # Use helper

            if item_data['_type'] == GraphicsStateItem.Type:
                state = GraphicsStateItem(
                    item_data['x'], item_data['y'], item_data['width'], item_data['height'],
                    item_data['name'], item_data['is_initial'], item_data['is_final'],
                    item_data.get('color'),
                    action_language=item_data.get('action_language', DEFAULT_EXECUTION_ENV),
                    entry_action=item_data.get('entry_action', ""),
                    during_action=item_data.get('during_action', ""),
                    exit_action=item_data.get('exit_action', ""),
                    description=item_data.get('description', ""),
                    is_superstate=item_data.get('is_superstate', False),
                    sub_fsm_data=item_data.get('sub_fsm_data', {'states':[], 'transitions':[], 'comments':[]}),
                    item_uuid=item_uuid # Pass original UUID
                )
                instance_to_add = state
                if self.scene.parent_window and hasattr(self.scene.parent_window, 'connect_state_item_signals'):
                    self.scene.parent_window.connect_state_item_signals(state)
            elif item_data['_type'] == GraphicsCommentItem.Type:
                comment = GraphicsCommentItem(
                    item_data['x'], item_data['y'], item_data['text'], item_uuid=item_uuid
                )
                comment.setTextWidth(item_data.get('width', 150))
                instance_to_add = comment
            
            if instance_to_add:
                self.scene.addItem(instance_to_add)
                recreated_item_instances_map[item_uuid] = instance_to_add
                logger.debug(f"RemoveItemsCommand: Undo - Re-added item '{display_name}'")

        # Second pass: recreate HistoryPseudoStateItems (need their parent states from first pass)
        for item_data in self.removed_items_data:
            item_uuid = item_data['uuid']
            if item_data['_type'] == GraphicsHistoryPseudoStateItem.Type:
                if item_uuid in recreated_item_instances_map: continue # Already handled if re-added above

                parent_uuid = item_data.get('_parent_superstate_uuid')
                parent_item = recreated_item_instances_map.get(parent_uuid)
                if not parent_item and self.scene: # If parent wasn't part of this removal, get from scene
                    parent_item = self.scene.get_item_by_uuid(parent_uuid)
                
                if isinstance(parent_item, GraphicsStateItem) and parent_item.is_superstate:
                    h_item = GraphicsHistoryPseudoStateItem(
                        x_relative=item_data['x_relative'],
                        y_relative=item_data['y_relative'],
                        parent_superstate_item=parent_item,
                        history_type=item_data.get('type', 'shallow'),
                        item_uuid=item_uuid # Pass original UUID
                    )
                    # Default target will be linked in third pass
                    recreated_item_instances_map[item_uuid] = h_item
                    logger.debug(f"RemoveItemsCommand: Undo - Re-added HistoryItem '{item_uuid}' to parent '{parent_item.uuid}'.")
                else:
                    logger.error(f"RemoveItemsCommand: Undo - Could not re-add HistoryItem '{item_uuid}'. Parent (UUID: {parent_uuid}) not found or not superstate.")


        # Third pass: recreate transitions using the recreated items (mapped by UUID)
        for item_data in self.removed_items_data:
            item_uuid = item_data['uuid']
            if item_data['_type'] == GraphicsTransitionItem.Type:
                if item_uuid in recreated_item_instances_map: continue # Already handled if re-added above

                start_uuid = item_data.get('_start_uuid')
                end_uuid = item_data.get('_end_uuid')
                
                src_item = recreated_item_instances_map.get(start_uuid)
                if not src_item and self.scene: src_item = self.scene.get_item_by_uuid(start_uuid)
                
                tgt_item = recreated_item_instances_map.get(end_uuid)
                if not tgt_item and self.scene: tgt_item = self.scene.get_item_by_uuid(end_uuid)

                display_name = AddItemCommand._get_display_name_for_log(self, item_data) # Use helper

                if src_item and tgt_item and \
                   isinstance(src_item, (GraphicsStateItem, GraphicsHistoryPseudoStateItem)) and \
                   isinstance(tgt_item, (GraphicsStateItem, GraphicsHistoryPseudoStateItem)):
                    
                    # Check if this transition is a default H-transition already managed by an H-item
                    is_managed_h_transition = False
                    if isinstance(src_item, GraphicsHistoryPseudoStateItem) and src_item.default_history_transition_item and src_item.default_history_transition_item.uuid == item_uuid:
                        is_managed_h_transition = True

                    if not is_managed_h_transition:
                        trans = GraphicsTransitionItem(
                            src_item, tgt_item,
                            event_str=item_data['event'],
                            condition_str=item_data['condition'],
                            action_language=item_data.get('action_language', DEFAULT_EXECUTION_ENV),
                            action_str=item_data['action'],
                            color=item_data.get('color'),
                            description=item_data.get('description', ""),
                            item_uuid=item_uuid # Pass original UUID
                        )
                        trans.set_control_point_offset(QPointF(item_data['control_offset_x'], item_data['control_offset_y']))
                        self.scene.addItem(trans)
                        recreated_item_instances_map[item_uuid] = trans
                        logger.debug(f"RemoveItemsCommand: Undo - Re-added transition '{display_name}'")
                    else:
                         logger.debug(f"RemoveItemsCommand: Undo - Skipped re-adding managed default H-transition '{display_name}'.")

                else:
                    log_msg = f"Error (Undo Remove): Could not re-link transition '{display_name}'. Source/Target UUIDs ('{start_uuid}', '{end_uuid}') not found or invalid types."
                    logger.error(f"RemoveItemsCommand: {log_msg}")

        # Final pass for H-item default transitions (if their target was also part of this removal set)
        for item_data in self.removed_items_data:
            if item_data['_type'] == GraphicsHistoryPseudoStateItem.Type:
                h_item_instance = recreated_item_instances_map.get(item_data['uuid'])
                if h_item_instance and isinstance(h_item_instance, GraphicsHistoryPseudoStateItem):
                    default_target_uuid = item_data.get('_default_target_substate_uuid')
                    if default_target_uuid:
                        target_state_instance = recreated_item_instances_map.get(default_target_uuid)
                        if not target_state_instance and self.scene: # If target wasn't removed, get from scene
                            target_state_instance = self.scene.get_item_by_uuid(default_target_uuid)
                        
                        if isinstance(target_state_instance, GraphicsStateItem):
                            h_item_instance.set_default_target_substate(target_state_instance)
                            # The update_default_history_transition will add the transition to scene
                        else:
                            logger.warning(f"RemoveItemsCommand: Undo - H-item '{h_item_instance.uuid}' default target (UUID: {default_target_uuid}) not found or invalid.")


        self.scene.set_dirty(True)
        self.scene.scene_content_changed_for_find.emit()
        self.scene.run_all_validations("RemoveItemsCommand_Undo")
        logger.debug(f"RemoveItemsCommand: Undo - Total items processed for re-addition: {len(recreated_item_instances_map)}")


class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_and_positions_info, description="Move Items"):
        super().__init__(description)
        # Store UUIDs along with positions for robustness
        self.items_info = []
        self.scene_ref = None
        if items_and_positions_info:
            first_item_ref = items_and_positions_info[0][0]
            if first_item_ref and hasattr(first_item_ref, 'scene') and first_item_ref.scene():
                 self.scene_ref = first_item_ref.scene()

            for item, old_pos, new_pos in items_and_positions_info:
                self.items_info.append({'uuid': item.uuid, 'old_pos': old_pos, 'new_pos': new_pos})
        logger.debug(f"MoveItemsCommand: Initialized for {len(self.items_info)} items.")

    def _apply_positions(self, use_new_positions: bool):
        if not self.scene_ref: return
        for item_info_dict in self.items_info:
            item = self.scene_ref.get_item_by_uuid(item_info_dict['uuid'])
            if item:
                target_pos = item_info_dict['new_pos'] if use_new_positions else item_info_dict['old_pos']
                item.setPos(target_pos)
                # ItemMoved signal connection in GraphicsStateItem/GraphicsHistoryPseudoStateItem
                # should handle calling _update_connected_transitions.
                # No explicit call needed here if signals are correctly set up.
            else:
                logger.warning(f"MoveItemsCommand: Could not find item with UUID {item_info_dict['uuid']} to apply position.")
        self.scene_ref.update()
        self.scene_ref.set_dirty(True)
        # No validation run needed for move usually, unless specific rules apply

    def redo(self):
        self._apply_positions(use_new_positions=True)
        logger.debug(f"MoveItemsCommand: Redo - Moved {len(self.items_info)} items.")

    def undo(self):
        self._apply_positions(use_new_positions=False)
        logger.debug(f"MoveItemsCommand: Undo - Moved {len(self.items_info)} items back.")


class EditItemPropertiesCommand(QUndoCommand):
    def __init__(self, item, old_props_data, new_props_data, description="Edit Properties"):
        super().__init__(description)
        self.item_uuid = item.uuid # Store UUID of the item
        self.old_props_data = old_props_data # Already includes UUID
        self.new_props_data = new_props_data # Already includes UUID
        self.scene_ref = item.scene()
        item_name_for_log = self.new_props_data.get('name', self.new_props_data.get('event', self.new_props_data.get('text', self.item_uuid)))
        logger.debug(f"EditItemPropertiesCommand: Initialized for item '{item_name_for_log}' (UUID: {self.item_uuid}).")


    def _apply_properties(self, props_to_apply):
        if not self.scene_ref:
            logger.error("EditItemPropertiesCommand: Scene reference is missing.")
            return
        
        item = self.scene_ref.get_item_by_uuid(self.item_uuid)
        if not item:
            logger.error(f"EditItemPropertiesCommand: Could not find item with UUID {self.item_uuid} in scene to apply properties.")
            return

        item_display_name_for_log = AddItemCommand._get_display_name_for_log(self, props_to_apply) # Use helper

        original_name_if_state = None
        if isinstance(item, GraphicsStateItem):
            original_name_if_state = item.text_label # Get current name before setting new props
            item.set_properties(
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
        elif isinstance(item, GraphicsTransitionItem):
            item.set_properties(event_str=props_to_apply.get('event',""),
                                     condition_str=props_to_apply.get('condition',""),
                                     action_language=props_to_apply.get('action_language', DEFAULT_EXECUTION_ENV),
                                     action_str=props_to_apply.get('action',""),
                                     color_hex=props_to_apply.get('color'),
                                     description=props_to_apply.get('description',""),
                                     offset=QPointF(props_to_apply['control_offset_x'], props_to_apply['control_offset_y']))
        elif isinstance(item, GraphicsCommentItem):
            item.set_properties(text=props_to_apply['text'], width=props_to_apply.get('width'))
        elif isinstance(item, GraphicsHistoryPseudoStateItem):
            # Find target substate item by UUID if it was part of the properties
            default_target_uuid = props_to_apply.get('default_target_substate_uuid')
            target_substate_item = None
            if default_target_uuid and self.scene_ref:
                target_substate_item = self.scene_ref.get_item_by_uuid(default_target_uuid)
                if not isinstance(target_substate_item, GraphicsStateItem):
                    logger.warning(f"EditItemProperties for HistoryItem: Target substate UUID '{default_target_uuid}' did not resolve to a GraphicsStateItem.")
                    target_substate_item = None # Ensure it's None if not valid

            item.set_properties(
                history_type=props_to_apply.get('type', 'shallow'),
                default_target_substate_item=target_substate_item
            )


        item.update()
        self.scene_ref.update()
        self.scene_ref.set_dirty(True)
        self.scene_ref.scene_content_changed_for_find.emit()
        self.scene_ref.run_all_validations(f"EditItemPropCmd_{item_display_name_for_log}")

    def redo(self):
        logger.debug(f"EditItemPropertiesCommand: Redo - Applying new properties to item UUID {self.item_uuid}.")
        self._apply_properties(self.new_props_data)

    def undo(self):
        logger.debug(f"EditItemPropertiesCommand: Undo - Applying old properties to item UUID {self.item_uuid}.")
        self._apply_properties(self.old_props_data)