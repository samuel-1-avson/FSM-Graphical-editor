

from PyQt5.QtWidgets import QUndoCommand, QGraphicsItem
from PyQt5.QtCore import QPointF
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
from config import DEFAULT_EXECUTION_ENV # Import default

class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item_instance = item 

        if isinstance(item, GraphicsTransitionItem):
            self.item_data = item.get_data()
            self.start_item_name = item.start_item.text_label if item.start_item else None
            self.end_item_name = item.end_item.text_label if item.end_item else None
        elif isinstance(item, GraphicsStateItem) or isinstance(item, GraphicsCommentItem):
            self.item_data = item.get_data()

    def redo(self):
        if self.item_instance.scene() is None:
            self.scene.addItem(self.item_instance)

        if isinstance(self.item_instance, GraphicsTransitionItem):
            start_node = self.scene.get_state_by_name(self.start_item_name)
            end_node = self.scene.get_state_by_name(self.end_item_name)
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
            else: 
                if hasattr(self.scene, 'log_function') and callable(self.scene.log_function):
                    self.scene.log_function(f"Error (Redo Add Transition): Could not link transition. State(s) missing for '{self.item_data.get('event', 'Unnamed Transition')}'.", level="ERROR")
                else:
                    print(f"LOG_ERROR (AddItemCommand): Scene has no log_function. Message: Error (Redo Add Transition): Could not link transition. State(s) missing for '{self.item_data.get('event', 'Unnamed Transition')}'.")


        self.scene.clearSelection()
        self.item_instance.setSelected(True)
        self.scene.set_dirty(True)

    def undo(self):
        self.scene.removeItem(self.item_instance)
        self.scene.set_dirty(True)


class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items_to_remove, description="Remove Items"):
        super().__init__(description)
        self.scene = scene
        self.removed_items_data = [] 
        self.item_instances_for_quick_toggle = list(items_to_remove) 

        for item in items_to_remove:
            item_data_entry = item.get_data()
            item_data_entry['_type'] = item.type() 
            if isinstance(item, GraphicsTransitionItem):
                item_data_entry['_start_name'] = item.start_item.text_label if item.start_item else None
                item_data_entry['_end_name'] = item.end_item.text_label if item.end_item else None
            self.removed_items_data.append(item_data_entry)

    def redo(self): 
        for item_instance in self.item_instances_for_quick_toggle:
            if item_instance.scene() == self.scene : 
                self.scene.removeItem(item_instance)
        self.scene.set_dirty(True)

    def undo(self): 
        newly_re_added_instances = []
        states_map_for_undo = {} 

        for item_data in self.removed_items_data:
            instance_to_add = None
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
                instance_to_add = state
                states_map_for_undo[state.text_label] = state 
            elif item_data['_type'] == GraphicsCommentItem.Type:
                comment = GraphicsCommentItem(item_data['x'], item_data['y'], item_data['text'])
                comment.setTextWidth(item_data.get('width', 150))
                instance_to_add = comment

            if instance_to_add:
                self.scene.addItem(instance_to_add)
                newly_re_added_instances.append(instance_to_add)

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
                else:
                    if hasattr(self.scene, 'log_function') and callable(self.scene.log_function):
                        self.scene.log_function(f"Error (Undo Remove): Could not re-link transition. States '{item_data['_start_name']}' or '{item_data['_end_name']}' missing.", level="ERROR")
                    else:
                        print(f"LOG_ERROR (RemoveItemsCommand): Scene has no log_function. Message: Error (Undo Remove): Could not re-link transition. States '{item_data['_start_name']}' or '{item_data['_end_name']}' missing.")

        self.item_instances_for_quick_toggle = newly_re_added_instances 
        self.scene.set_dirty(True)

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

    def undo(self):
        self._apply_positions(use_new_positions=False)


class EditItemPropertiesCommand(QUndoCommand):
    def __init__(self, item, old_props_data, new_props_data, description="Edit Properties"):
        super().__init__(description)
        self.item = item
        self.old_props_data = old_props_data 
        self.new_props_data = new_props_data 
        self.scene_ref = item.scene()

    def _apply_properties(self, props_to_apply):
        if not self.item or not self.scene_ref: return

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

        self.item.update() 
        self.scene_ref.update() 
        self.scene_ref.set_dirty(True)

    def redo(self):
        self._apply_properties(self.new_props_data)

    def undo(self):
        self._apply_properties(self.old_props_data)
