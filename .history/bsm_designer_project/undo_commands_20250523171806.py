from PyQt5.QtWidgets import QUndoCommand, QGraphicsItem
from PyQt5.QtCore import QPointF
from graphics_items import GraphicsStateItem, GraphicsTransitionItem, GraphicsCommentItem
import weakref
from typing import List, Dict, Any, Optional, Tuple
import logging

# Base command with common functionality
class BaseItemCommand(QUndoCommand):
    """Base class for item commands with common utilities."""
    
    def __init__(self, scene, description: str):
        super().__init__(description)
        self.scene = scene
        self._logger = logging.getLogger(self.__class__.__name__)
    
    def _log_error(self, message: str):
        """Centralized error logging."""
        self._logger.error(message)
        if hasattr(self.scene, 'log_function'):
            self.scene.log_function(f"Error: {message}")
    
    def _update_scene(self, set_dirty: bool = True):
        """Update scene and mark as dirty if needed."""
        if set_dirty:
            self.scene.set_dirty(True)
        self.scene.update()

class ItemFactory:
    """Factory for creating graphics items from data."""
    
    @staticmethod
    def create_item(item_data: Dict[str, Any], states_map: Optional[Dict[str, GraphicsStateItem]] = None):
        """Create a graphics item from data dictionary."""
        item_type = item_data.get('_type')
        
        if item_type == GraphicsStateItem.Type:
            return ItemFactory._create_state(item_data)
        elif item_type == GraphicsCommentItem.Type:
            return ItemFactory._create_comment(item_data)
        elif item_type == GraphicsTransitionItem.Type:
            return ItemFactory._create_transition(item_data, states_map or {})
        else:
            raise ValueError(f"Unknown item type: {item_type}")
    
    @staticmethod
    def _create_state(data: Dict[str, Any]) -> GraphicsStateItem:
        """Create a state item from data."""
        return GraphicsStateItem(
            data['x'], data['y'], data['width'], data['height'],
            data['name'], data['is_initial'], data['is_final'],
            data.get('color'), data.get('entry_action', ""),
            data.get('during_action', ""), data.get('exit_action', ""),
            data.get('description', "")
        )
    
    @staticmethod
    def _create_comment(data: Dict[str, Any]) -> GraphicsCommentItem:
        """Create a comment item from data."""
        comment = GraphicsCommentItem(data['x'], data['y'], data['text'])
        comment.setTextWidth(data.get('width', 150))
        return comment
    
    @staticmethod
    def _create_transition(data: Dict[str, Any], states_map: Dict[str, GraphicsStateItem]) -> Optional[GraphicsTransitionItem]:
        """Create a transition item from data."""
        start_name = data.get('_start_name')
        end_name = data.get('_end_name')
        
        if not start_name or not end_name:
            return None
            
        start_item = states_map.get(start_name)
        end_item = states_map.get(end_name)
        
        if not start_item or not end_item:
            return None
        
        transition = GraphicsTransitionItem(
            start_item, end_item,
            event_str=data.get('event', ''),
            condition_str=data.get('condition', ''),
            action_str=data.get('action', ''),
            color=data.get('color'),
            description=data.get('description', '')
        )
        
        # Set control point offset
        offset_x = data.get('control_offset_x', 0)
        offset_y = data.get('control_offset_y', 0)
        transition.set_control_point_offset(QPointF(offset_x, offset_y))
        
        return transition

class AddItemCommand(BaseItemCommand):
    """Command for adding items to the scene."""
    
    def __init__(self, scene, item, description: str = "Add Item"):
        super().__init__(scene, description)
        
        # Store weak reference to avoid memory leaks
        self._item_ref = weakref.ref(item)
        
        # Store item data for recreation if needed
        self.item_data = self._extract_item_data(item)
        self._item_added = False
    
    def _extract_item_data(self, item) -> Dict[str, Any]:
        """Extract data from item for storage."""
        data = item.get_data()
        data['_type'] = item.type()
        
        if isinstance(item, GraphicsTransitionItem):
            data['_start_name'] = item.start_item.text_label if item.start_item else None
            data['_end_name'] = item.end_item.text_label if item.end_item else None
        
        return data
    
    def _get_or_recreate_item(self):
        """Get existing item or recreate from data."""
        item = self._item_ref() if self._item_ref else None
        
        if item is None:
            # Item was garbage collected, recreate it
            if self.item_data['_type'] == GraphicsTransitionItem.Type:
                # Need to get states for transition
                states_map = {
                    state.text_label: state 
                    for state in self.scene.items() 
                    if isinstance(state, GraphicsStateItem)
                }
                item = ItemFactory.create_item(self.item_data, states_map)
            else:
                item = ItemFactory.create_item(self.item_data)
            
            if item:
                self._item_ref = weakref.ref(item)
        
        return item
    
    def redo(self):
        """Add item to scene."""
        item = self._get_or_recreate_item()
        if not item:
            self._log_error("Failed to create/retrieve item for redo")
            return
        
        if item.scene() is None:
            self.scene.addItem(item)
            self._item_added = True
            
            # Select the newly added item
            self.scene.clearSelection()
            item.setSelected(True)
            
            self._update_scene()
    
    def undo(self):
        """Remove item from scene."""
        item = self._item_ref() if self._item_ref else None
        if item and item.scene() == self.scene:
            self.scene.removeItem(item)
            self._item_added = False
            self._update_scene()

class RemoveItemsCommand(BaseItemCommand):
    """Command for removing multiple items from the scene."""
    
    def __init__(self, scene, items_to_remove: List[QGraphicsItem], description: str = "Remove Items"):
        super().__init__(scene, description)
        
        # Store item data for recreation
        self.items_data = []
        for item in items_to_remove:
            data = item.get_data()
            data['_type'] = item.type()
            
            if isinstance(item, GraphicsTransitionItem):
                data['_start_name'] = item.start_item.text_label if item.start_item else None
                data['_end_name'] = item.end_item.text_label if item.end_item else None
            
            self.items_data.append(data)
        
        # Keep weak references to original items
        self._item_refs = [weakref.ref(item) for item in items_to_remove]
        self._recreated_items = []
    
    def redo(self):
        """Remove items from scene."""
        for item_ref in self._item_refs:
            item = item_ref() if item_ref else None
            if item and item.scene() == self.scene:
                self.scene.removeItem(item)
        
        self._recreated_items.clear()
        self._update_scene()
    
    def undo(self):
        """Re-add removed items to scene."""
        self._recreated_items.clear()
        states_map = {}
        
        # First pass: Create states and comments
        for data in self.items_data:
            if data['_type'] in [GraphicsStateItem.Type, GraphicsCommentItem.Type]:
                try:
                    item = ItemFactory.create_item(data)
                    if item:
                        self.scene.addItem(item)
                        self._recreated_items.append(item)
                        
                        if isinstance(item, GraphicsStateItem):
                            states_map[item.text_label] = item
                            
                except Exception as e:
                    self._log_error(f"Failed to recreate item: {e}")
        
        # Second pass: Create transitions
        for data in self.items_data:
            if data['_type'] == GraphicsTransitionItem.Type:
                try:
                    item = ItemFactory.create_item(data, states_map)
                    if item:
                        self.scene.addItem(item)
                        self._recreated_items.append(item)
                    else:
                        start_name = data.get('_start_name', 'Unknown')
                        end_name = data.get('_end_name', 'Unknown')
                        self._log_error(f"Could not recreate transition between '{start_name}' and '{end_name}'")
                        
                except Exception as e:
                    self._log_error(f"Failed to recreate transition: {e}")
        
        self._update_scene()

class MoveItemsCommand(BaseItemCommand):
    """Command for moving items."""
    
    def __init__(self, items_and_positions: List[Tuple[QGraphicsItem, QPointF]], description: str = "Move Items"):
        super().__init__(None, description)  # Scene will be set from first item
        
        if not items_and_positions:
            raise ValueError("No items provided for move command")
        
        self.scene = items_and_positions[0][0].scene()
        
        # Store weak references and positions
        self._moves_data = []
        for item, new_pos in items_and_positions:
            self._moves_data.append({
                'item_ref': weakref.ref(item),
                'old_pos': QPointF(item.pos()),
                'new_pos': QPointF(new_pos)
            })
    
    def _apply_positions(self, use_new_pos: bool):
        """Apply positions to items."""
        moved_states = []
        
        for move_data in self._moves_data:
            item = move_data['item_ref']() if move_data['item_ref'] else None
            if not item:
                continue
                
            pos = move_data['new_pos'] if use_new_pos else move_data['old_pos']
            item.setPos(pos)
            
            # Track states for transition updates
            if isinstance(item, GraphicsStateItem):
                moved_states.append(item)
        
        # Update connected transitions for moved states
        for state in moved_states:
            if hasattr(self.scene, '_update_connected_transitions'):
                self.scene._update_connected_transitions(state)
        
        self._update_scene()
    
    def redo(self):
        """Apply new positions."""
        self._apply_positions(True)
    
    def undo(self):
        """Restore old positions."""
        self._apply_positions(False)

class EditItemPropertiesCommand(BaseItemCommand):
    """Command for editing item properties."""
    
    def __init__(self, item, old_props: Dict[str, Any], new_props: Dict[str, Any], description: str = "Edit Properties"):
        super().__init__(item.scene(), description)
        
        self._item_ref = weakref.ref(item)
        self.old_props = old_props.copy()
        self.new_props = new_props.copy()
        self._item_type = type(item)
    
    def _apply_properties(self, props: Dict[str, Any]):
        """Apply properties to item."""
        item = self._item_ref() if self._item_ref else None
        if not item:
            self._log_error("Item no longer exists")
            return
        
        try:
            # Handle state name changes specially
            old_name = None
            if isinstance(item, GraphicsStateItem) and 'name' in props:
                old_name = item.text_label
            
            # Apply properties based on item type
            if isinstance(item, GraphicsStateItem):
                self._apply_state_properties(item, props)
                
                # Update transitions if name changed
                if old_name and old_name != props.get('name', old_name):
                    if hasattr(self.scene, '_update_transitions_for_renamed_state'):
                        self.scene._update_transitions_for_renamed_state(old_name, props['name'])
                        
            elif isinstance(item, GraphicsTransitionItem):
                self._apply_transition_properties(item, props)
            elif isinstance(item, GraphicsCommentItem):
                self._apply_comment_properties(item, props)
            
            item.update()
            self._update_scene()
            
        except Exception as e:
            self._log_error(f"Failed to apply properties: {e}")
    
    def _apply_state_properties(self, item: GraphicsStateItem, props: Dict[str, Any]):
        """Apply properties to state item."""
        item.set_properties(
            props.get('name', ''),
            props.get('is_initial', False),
            props.get('is_final', False),
            props.get('color'),
            props.get('entry_action', ''),
            props.get('during_action', ''),
            props.get('exit_action', ''),
            props.get('description', '')
        )
    
    def _apply_transition_properties(self, item: GraphicsTransitionItem, props: Dict[str, Any]):
        """Apply properties to transition item."""
        offset = QPointF(
            props.get('control_offset_x', 0),
            props.get('control_offset_y', 0)
        )
        
        item.set_properties(
            event_str=props.get('event', ''),
            condition_str=props.get('condition', ''),
            action_str=props.get('action', ''),
            color_hex=props.get('color'),
            description=props.get('description', ''),
            offset=offset
        )
    
    def _apply_comment_properties(self, item: GraphicsCommentItem, props: Dict[str, Any]):
        """Apply properties to comment item."""
        item.set_properties(
            text=props.get('text', ''),
            width=props.get('width')
        )
    
    def redo(self):
        """Apply new properties."""
        self._apply_properties(self.new_props)
    
    def undo(self):
        """Restore old properties."""
        self._apply_properties(self.old_props)

# Utility function for batch operations
class BatchCommand(QUndoCommand):
    """Command that combines multiple commands into one."""
    
    def __init__(self, commands: List[QUndoCommand], description: str = "Batch Operation"):
        super().__init__(description)
        self.commands = commands
    
    def redo(self):
        for command in self.commands:
            command.redo()
    
    def undo(self):
        # Undo in reverse order
        for command in reversed(self.commands):
            command.undo()