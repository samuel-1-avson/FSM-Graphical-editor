



from PyQt5.QtWidgets import QUndoCommand, QGraphicsItem
from PyQt5.QtCore import QPointF
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from config import DEFAULT_EXECUTION_ENV # Import default

class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item_instance = item # Store the actual QGraphicsItem instance

        # Store data needed to reconstruct the item if it's removed and then re-added (e.g. by undo/redo)
        # This is more robust than just storing the instance if the instance gets deleted.
        if isinstance(item, GraphicsTransitionItem):
            self.item_data = item.get_data() # get_data() should capture all necessary info
            # Store names of connected states for re-linking
            self.start_item_name = item.start_item.text_label if item.start_item else None
            self.end_item_name = item.end_item.text_label if item.end_item else None
        elif isinstance(item, (GraphicsStateItem, GraphicsCommentItem)):
            self.item_data = item.get_data()

    def redo(self):
        # If the item instance is not already in the scene (e.g., after an undo), add it.
        if self.item_instance.scene() is None:
            self.scene.addItem(self.item_instance)

        # For transitions, ensure start_item and end_item references are correctly set/restored
        # This is crucial if the state items themselves were part of an undo/redo operation
        # or if the transition item was newly created by this command's first redo.
        if isinstance(self.item_instance, GraphicsTransitionItem):
            start_node = self.scene.get_state_by_name(self.start_item_name)
            end_node = self.scene.get_state_by_name(self.end_item_name)
            if start_node and end_node:
                self.item_instance.start_item = start_node
                self.item_instance.end_item = end_node
                # Re-apply properties to ensure it's fully configured, esp. if it was re-created
                self.item_instance.set_properties(
                    event_str=self.item_data['event'],
                    condition_str=self.item_data['condition'],
                    action_language=self.item_data.get('action_language', DEFAULT_EXECUTION_ENV),
                    action_str=self.item_data['action'],
                    color_hex=self.item_data.get('color'),
                    description=self.item_data.get('description', ""),
                    offset=QPointF(self.item_data['control_offset_x'], self.item_data['control_offset_y'])
                )
                self.item_instance.update_path() # Recalculate path
            else: 
                # Log an error if states can't be found for linking
                log_msg = f"Error (Redo Add Transition): Could not link transition. State(s) missing for '{self.item_data.get('event', 'Unnamed Transition')}'. Source: '{self.start_item_name}', Target: '{self.end_item_name}'."
                if hasattr(self.scene, 'log_function') and callable(self.scene.log_function):
                    self.scene.log_function(log_msg, level="ERROR")
                else: # Fallback print if scene logger not available
                    print(f"LOG_ERROR (AddItemCommand): Scene has no log_function. Message: {log_msg}")


        self.scene.clearSelection()
        self.item_instance.setSelected(True)
        self.scene.set_dirty(True)

    def undo(self):
        # Remove the item from the scene
        self.scene.removeItem(self.item_instance)
        self.scene.set_dirty(True)


class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items_to_remove, description="Remove Items"):
        super().__init__(description)
        self.scene = scene
        self.removed_items_data = [] # Store serialized data of items
        # Store instances only for the first redo/undo cycle. After that, rely on data.
        self.item_instances_for_quick_toggle = list(items_to_remove) 

        # Serialize items for robust undo/redo
        for item in items_to_remove:
            item_data_entry = item.get_data() # Get item's serializable data
            item_data_entry['_type'] = item.type() # Store item type
            # For transitions, also store names of connected states
            if isinstance(item, GraphicsTransitionItem):
                item_data_entry['_start_name'] = item.start_item.text_label if item.start_item else None
                item_data_entry['_end_name'] = item.end_item.text_label if item.end_item else None
            self.removed_items_data.append(item_data_entry)

    def redo(self): # Remove the items
        # If item_instances_for_quick_toggle has instances (first redo), use them.
        # Otherwise, this implies items were re-created on undo, so they shouldn't be in scene.
        for item_instance in self.item_instances_for_quick_toggle:
            if item_instance.scene() == self.scene : # Check if it's still in the scene
                self.scene.removeItem(item_instance)
        self.scene.set_dirty(True)

    def undo(self): # Re-add the items
        newly_re_added_instances = []
        states_map_for_undo = {} # Temp map to link re-added transitions to re-added states

        # First pass: Re-add all state items to populate states_map_for_undo
        for item_data in self.removed_items_data:
            if item_data['_type'] == GraphicsStateItem.Type:
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
                self.scene.addItem(state)
                newly_re_added_instances.append(state)
                states_map_for_undo[state.text_label] = state # Map by name for transitions

        # Second pass: Re-add comment items (no dependencies)
        for item_data in self.removed_items_data:
            if item_data['_type'] == GraphicsCommentItem.Type:
                comment = GraphicsCommentItem(item_data['x'], item_data['y'], item_data['text'])
                comment.setTextWidth(item_data.get('width', 150)) # Restore width
                self.scene.addItem(comment)
                newly_re_added_instances.append(comment)

        # Third pass: Re-add transition items, linking them to re-added states
        for item_data in self.removed_items_data:
            if item_data['_type'] == GraphicsTransitionItem.Type:
                src_item = states_map_for_undo.get(item_data['_start_name'])
                tgt_item = states_map_for_undo.get(item_data['_end_name'])
                if src_item and tgt_item: # Both source and target states must exist
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
                else: # Log error if states for transition not found
                    log_msg = f"Error (Undo Remove): Could not re-link transition. States '{item_data['_start_name']}' or '{item_data['_end_name']}' missing for transition '{item_data.get('event', 'Unnamed Transition')}'.'"
                    if hasattr(self.scene, 'log_function') and callable(self.scene.log_function):
                        self.scene.log_function(log_msg, level="ERROR")
                    else:
                        print(f"LOG_ERROR (RemoveItemsCommand): Scene has no log_function. Message: {log_msg}")
        
        # Update the list of instances for the next redo (if any)
        self.item_instances_for_quick_toggle = newly_re_added_instances 
        self.scene.set_dirty(True)

class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_and_positions_info, description="Move Items"):
        super().__init__(description)
        # items_and_positions_info is a list of tuples: (item_instance, old_QPointF, new_QPointF)
        self.items_and_positions_info = items_and_positions_info
        self.scene_ref = None # Store scene reference for convenience
        if self.items_and_positions_info: # Get scene from the first item
            self.scene_ref = self.items_and_positions_info[0][0].scene() 

    def _apply_positions(self, use_new_positions: bool):
        if not self.scene_ref: return # Safety check
        for item, old_pos, new_pos in self.items_and_positions_info:
            target_pos = new_pos if use_new_positions else old_pos
            item.setPos(target_pos) # Move the item
            # If item is a state, update its connected transitions
            if isinstance(item, GraphicsStateItem):
                self.scene_ref._update_connected_transitions(item)
        self.scene_ref.update() # Request scene repaint
        self.scene_ref.set_dirty(True)

    def redo(self): # Apply new positions
        self._apply_positions(use_new_positions=True)

    def undo(self): # Apply old positions
        self._apply_positions(use_new_positions=False)


class EditItemPropertiesCommand(QUndoCommand):
    def __init__(self, item, old_props_data, new_props_data, description="Edit Properties"):
        super().__init__(description)
        self.item = item # The QGraphicsItem instance being edited
        self.old_props_data = old_props_data # Dictionary of properties before edit
        self.new_props_data = new_props_data # Dictionary of properties after edit
        self.scene_ref = item.scene() # Get scene reference from item

    def _apply_properties(self, props_to_apply):
        if not self.item or not self.scene_ref: return

        original_name_if_state = None # To track if state name changes

        if isinstance(self.item, GraphicsStateItem):
            original_name_if_state = self.item.text_label # Store old name before applying new props
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
            # If state name changed, notify scene to update transition links if needed
            # (though transitions typically use item references, not names directly for linking)
            if original_name_if_state is not None and original_name_if_state != props_to_apply['name']:
                if hasattr(self.scene_ref, '_update_transitions_for_renamed_state'):
                    self.scene_ref._update_transitions_for_renamed_state(original_name_if_state, props_to_apply['name'])

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

        self.item.update() # Ensure item repaints with new properties
        self.scene_ref.update() # Ensure scene repaints (e.g., if bounding rect changed)
        self.scene_ref.set_dirty(True)

    def redo(self):
        self._apply_properties(self.new_props_data)

    def undo(self):
        self._apply_properties(self.old_props_data)
