from PyQt5.QtWidgets import QUndoCommand, QGraphicsItem
from PyQt5.QtCore import QPointF
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem

class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item_instance = item # The actual QGraphicsItem instance

        # Store data representation of the item for redo/undo
        if isinstance(item, GraphicsTransitionItem):
            self.item_data = item.get_data()
            # Store names for re-linking as item instances themselves won't be valid across remove/add
            self.start_item_name = item.start_item.text_label if item.start_item else None
            self.end_item_name = item.end_item.text_label if item.end_item else None
        elif isinstance(item, GraphicsStateItem) or isinstance(item, GraphicsCommentItem):
            self.item_data = item.get_data()

    def redo(self):
        # If item isn't in scene (e.g., initial redo, or after undo), add it.
        if self.item_instance.scene() is None:
            self.scene.addItem(self.item_instance)

        # If it's a transition, re-establish connections using stored names
        # This is crucial if the states it connects to were also part of a larger undo/redo operation
        if isinstance(self.item_instance, GraphicsTransitionItem):
            start_node = self.scene.get_state_by_name(self.start_item_name)
            end_node = self.scene.get_state_by_name(self.end_item_name)
            if start_node and end_node:
                self.item_instance.start_item = start_node
                self.item_instance.end_item = end_node
                # Ensure properties (like control points) are also restored correctly from item_data
                self.item_instance.set_properties(
                    event_str=self.item_data['event'],
                    condition_str=self.item_data['condition'],
                    action_str=self.item_data['action'],
                    color_hex=self.item_data.get('color'),
                    description=self.item_data.get('description', ""),
                    offset=QPointF(self.item_data['control_offset_x'], self.item_data['control_offset_y'])
                )
                self.item_instance.update_path()
            else: # Should not happen if state creation/deletion is also in undo stack correctly
                self.scene.log_function(f"Error (Redo Add Transition): Could not link transition. State(s) missing for '{self.item_data.get('event', 'Unnamed Transition')}'.")

        self.scene.clearSelection()
        self.item_instance.setSelected(True)
        self.scene.set_dirty(True)

    def undo(self):
        # Simply remove the item. Item's data and linkage info remain in self.item_data for redo.
        self.scene.removeItem(self.item_instance)
        self.scene.set_dirty(True)


class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items_to_remove, description="Remove Items"):
        super().__init__(description)
        self.scene = scene
        self.removed_items_data = [] # Store data of removed items, not instances
        self.item_instances_for_quick_toggle = list(items_to_remove) # Keep original list for first redo

        for item in items_to_remove:
            item_data_entry = item.get_data()
            item_data_entry['_type'] = item.type() # Store custom type for re-creation
            if isinstance(item, GraphicsTransitionItem):
                # Store names of connected states
                item_data_entry['_start_name'] = item.start_item.text_label if item.start_item else None
                item_data_entry['_end_name'] = item.end_item.text_label if item.end_item else None
            self.removed_items_data.append(item_data_entry)

    def redo(self): # Perform the removal
        # Remove items from the scene using the stored instances (if they exist in scene)
        for item_instance in self.item_instances_for_quick_toggle:
            if item_instance.scene() == self.scene : # Check if it's still in the scene
                self.scene.removeItem(item_instance)
        self.scene.set_dirty(True)

    def undo(self): # Re-add the removed items
        newly_re_added_instances = []
        states_map_for_undo = {} # Temporarily map names to newly created state items for linking transitions

        # First pass: Re-create states and comments, populate states_map
        for item_data in self.removed_items_data:
            instance_to_add = None
            if item_data['_type'] == GraphicsStateItem.Type:
                state = GraphicsStateItem(item_data['x'], item_data['y'],
                                          item_data['width'], item_data['height'], item_data['name'],
                                          item_data['is_initial'], item_data['is_final'],
                                          item_data.get('color'), item_data.get('entry_action', ""),
                                          item_data.get('during_action', ""), item_data.get('exit_action', ""),
                                          item_data.get('description', ""))
                instance_to_add = state
                states_map_for_undo[state.text_label] = state # Map name to new instance
            elif item_data['_type'] == GraphicsCommentItem.Type:
                comment = GraphicsCommentItem(item_data['x'], item_data['y'], item_data['text'])
                comment.setTextWidth(item_data.get('width', 150))
                instance_to_add = comment

            if instance_to_add:
                self.scene.addItem(instance_to_add)
                newly_re_added_instances.append(instance_to_add)

        # Second pass: Re-create transitions, linking them using the states_map
        for item_data in self.removed_items_data:
            if item_data['_type'] == GraphicsTransitionItem.Type:
                src_item = states_map_for_undo.get(item_data['_start_name'])
                tgt_item = states_map_for_undo.get(item_data['_end_name'])
                if src_item and tgt_item:
                    trans = GraphicsTransitionItem(src_item, tgt_item,
                                                   event_str=item_data['event'],
                                                   condition_str=item_data['condition'],
                                                   action_str=item_data['action'],
                                                   color=item_data.get('color'),
                                                   description=item_data.get('description',""))
                    trans.set_control_point_offset(QPointF(item_data['control_offset_x'], item_data['control_offset_y']))
                    self.scene.addItem(trans)
                    newly_re_added_instances.append(trans)
                else:
                    self.scene.log_function(f"Error (Undo Remove): Could not re-link transition. States '{item_data['_start_name']}' or '{item_data['_end_name']}' missing.")

        self.item_instances_for_quick_toggle = newly_re_added_instances # Update for next potential redo
        self.scene.set_dirty(True)

class MoveItemsCommand(QUndoCommand):
    def __init__(self, items_and_new_positions, description="Move Items"):
        super().__init__(description)
        self.items_and_new_positions = items_and_new_positions # List of (item_instance, QPointF_new_pos)
        self.items_and_old_positions = []
        self.scene_ref = None
        if self.items_and_new_positions: # Ensure list is not empty
            self.scene_ref = self.items_and_new_positions[0][0].scene() # Get scene from first item
            for item, _ in self.items_and_new_positions:
                self.items_and_old_positions.append((item, item.pos())) # Store current (old) positions

    def _apply_positions(self, positions_list):
        if not self.scene_ref: return
        for item, pos in positions_list:
            item.setPos(pos) # QGraphicsItem.setPos()
            # If a state moved, connected transitions need path updates
            if isinstance(item, GraphicsStateItem):
                self.scene_ref._update_connected_transitions(item)
        self.scene_ref.update() # Request redraw of relevant area
        self.scene_ref.set_dirty(True)

    def redo(self):
        self._apply_positions(self.items_and_new_positions)

    def undo(self):
        self._apply_positions(self.items_and_old_positions)


class EditItemPropertiesCommand(QUndoCommand):
    def __init__(self, item, old_props_data, new_props_data, description="Edit Properties"):
        super().__init__(description)
        self.item = item
        self.old_props_data = old_props_data # Dict of properties before change
        self.new_props_data = new_props_data # Dict of properties after change
        self.scene_ref = item.scene()

    def _apply_properties(self, props_to_apply):
        if not self.item or not self.scene_ref: return

        original_name_if_state = None # Used only for GraphicsStateItem name changes

        if isinstance(self.item, GraphicsStateItem):
            original_name_if_state = self.item.text_label # Capture current name BEFORE changing it
            self.item.set_properties(props_to_apply['name'], props_to_apply.get('is_initial', False),
                                     props_to_apply.get('is_final', False), props_to_apply.get('color'),
                                     props_to_apply.get('entry_action', ""), props_to_apply.get('during_action', ""),
                                     props_to_apply.get('exit_action', ""), props_to_apply.get('description', ""))
            # If name changed, scene needs to know to update transition data if they refer to it by name
            if original_name_if_state != props_to_apply['name']:
                self.scene_ref._update_transitions_for_renamed_state(original_name_if_state, props_to_apply['name'])

        elif isinstance(self.item, GraphicsTransitionItem):
            self.item.set_properties(event_str=props_to_apply.get('event',""),
                                     condition_str=props_to_apply.get('condition',""),
                                     action_str=props_to_apply.get('action',""),
                                     color_hex=props_to_apply.get('color'),
                                     description=props_to_apply.get('description',""),
                                     offset=QPointF(props_to_apply['control_offset_x'], props_to_apply['control_offset_y']))
        elif isinstance(self.item, GraphicsCommentItem):
            self.item.set_properties(text=props_to_apply['text'], width=props_to_apply.get('width'))

        self.item.update() # Repaint the item
        self.scene_ref.update() # Repaint scene (transitions might need general update)
        self.scene_ref.set_dirty(True)

    def redo(self):
        self._apply_properties(self.new_props_data)

    def undo(self):
        self._apply_properties(self.old_props_data)