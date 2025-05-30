# bsm_designer_project/export_utils.py
import logging

logger = logging.getLogger(__name__)
def get_standard_icon_name(style_enum):
    """
    Returns the name of a standard icon based on the provided style enum.
    This is useful for debugging or logging purposes.
    """
    from PyQt5.QtWidgets import QApplication, QStyle
    if not QApplication.instance():
        logger.warning("No QApplication instance found. Cannot retrieve standard icon name.")
        return None
    icon = QApplication.style().standardIcon(style_enum)
    if icon.isNull():
        logger.warning(f"No standard icon found for style enum: {style_enum}")
        return None
    return icon.name()  # Returns the name of the icon, if available
def get_standard_icon(style_enum, fallback_name=None):
    # Example implementation, adjust as needed for your app
    from PyQt5.QtWidgets import QApplication, QStyle
    from PyQt5.QtGui import QIcon
    icon = QApplication.style().standardIcon(style_enum)
    if not icon or icon.isNull():
        # Optionally, provide a fallback icon here
        icon = QIcon()
    return icon
def _sanitize_puml_id(name: str) -> str:
    """Sanitizes a name to be a valid PlantUML ID (no spaces, special chars)."""
    if not name:
        return "Unnamed"
    # Replace spaces and common special characters with underscores
    name = name.replace(' ', '_').replace('-', '_').replace('.', '_').replace(':', '_')
    # Remove any characters not alphanumeric or underscore
    name = "".join(c if c.isalnum() or c == '_' else '' for c in name)
    # Ensure it doesn't start with a number (PlantUML might be okay, but good practice)
    if name and name[0].isdigit():
        name = "_" + name
    return name if name else "SanitizedEmptyName"

def _generate_plantuml_sub_fsm(sub_fsm_data: dict, parent_id_prefix: str, indent_level: int = 1) -> str:
    """
    Recursively generates PlantUML text for a sub-FSM (composite state).
    """
    puml_text = ""
    indent = "  " * indent_level
    sub_states = sub_fsm_data.get('states', [])
    sub_transitions = sub_fsm_data.get('transitions', [])
    sub_comments = sub_fsm_data.get('comments', [])

    initial_sub_state_id = None

    # Define sub-states
    for state_data in sub_states:
        s_name = state_data.get('name', 'UnnamedSubState')
        s_id = f"{parent_id_prefix}_{_sanitize_puml_id(s_name)}"
        s_label = state_data.get('name', 'UnnamedSubState')
        
        puml_text += f"{indent}state \"{s_label}\" as {s_id}\n"
        
        actions = []
        if state_data.get('entry_action'):
            actions.append(f"entry / {state_data['entry_action'].replace(chr(10), '; ')}")
        if state_data.get('during_action'):
            actions.append(f"during / {state_data['during_action'].replace(chr(10), '; ')}")
        if state_data.get('exit_action'):
            actions.append(f"exit / {state_data['exit_action'].replace(chr(10), '; ')}")
        
        if actions:
            puml_text += f"{indent}{s_id} : {chr(10)}{indent}  {chr(10).join([f'{indent}  {a}' for a in actions])}\n"

        if state_data.get('is_initial'):
            initial_sub_state_id = s_id
        if state_data.get('is_final'):
            puml_text += f"{indent}{s_id} --> [*]\n" # Final state within sub-machine

        # Recursively handle nested sub-FSMs if any state is also a superstate
        if state_data.get('is_superstate') and state_data.get('sub_fsm_data'):
            puml_text += f"{indent}state {s_id} {{\n"
            puml_text += _generate_plantuml_sub_fsm(state_data['sub_fsm_data'], s_id, indent_level + 1)
            puml_text += f"{indent}}}\n"


    # Initial transition for the sub-machine
    if initial_sub_state_id:
        puml_text += f"{indent}[*] --> {initial_sub_state_id}\n"
    
    # Define sub-transitions
    for trans_data in sub_transitions:
        src_name = trans_data.get('source')
        tgt_name = trans_data.get('target')
        if not src_name or not tgt_name:
            continue
            
        src_id = f"{parent_id_prefix}_{_sanitize_puml_id(src_name)}"
        tgt_id = f"{parent_id_prefix}_{_sanitize_puml_id(tgt_name)}"
        
        label_parts = []
        if trans_data.get('event'):
            label_parts.append(trans_data['event'])
        if trans_data.get('condition'):
            label_parts.append(f"[{trans_data['condition']}]")
        if trans_data.get('action'):
            label_parts.append(f"/ {{{trans_data['action'].replace(chr(10), '; ')}}}") # Escape newlines in action
        
        label = " : ".join(label_parts) if label_parts else ""
        puml_text += f"{indent}{src_id} --> {tgt_id}{label}\n"

    # Sub-comments (PlantUML notes can be attached to states)
    for comment_data in sub_comments:
        # PlantUML notes are typically attached to specific elements.
        # For general sub-FSM comments, we might need a strategy, e.g., attach to first state or a placeholder.
        # For now, skipping detailed sub-comment placement, but could be added.
        pass
        
    return puml_text


def generate_plantuml_text(diagram_data: dict, diagram_name: str = "FSM Diagram") -> str:
    """
    Generates PlantUML text representation from diagram data.
    """
    states = diagram_data.get('states', [])
    transitions = diagram_data.get('transitions', [])
    comments = diagram_data.get('comments', [])

    if not states:
        return "@startuml\n' No states defined in the diagram.\n@enduml"

    puml_text = f"@startuml {diagram_name}\n"
    puml_text += "skinparam state {\n"
    puml_text += "  ArrowColor #555555\n"
    puml_text += "  BorderColor #555555\n"
    puml_text += "  FontName Arial\n"
    puml_text += "}\n"
    puml_text += "hide empty description\n\n" # Good default for cleaner diagrams

    initial_state_id = None
    state_id_map = {} # Map original name to sanitized ID

    # Define states and their actions
    for state_data in states:
        s_name = state_data.get('name', 'UnnamedState')
        s_id = _sanitize_puml_id(s_name)
        state_id_map[s_name] = s_id
        s_label = state_data.get('name', 'UnnamedState')
        
        if state_data.get('is_superstate') and state_data.get('sub_fsm_data'):
            puml_text += f"state \"{s_label}\" as {s_id} {{\n"
            puml_text += _generate_plantuml_sub_fsm(state_data['sub_fsm_data'], s_id, 1)
            puml_text += "}\n"
        else:
            puml_text += f"state \"{s_label}\" as {s_id}\n"

        actions = []
        if state_data.get('entry_action'):
            actions.append(f"entry / {state_data['entry_action'].replace(chr(10), '; ')}") # Escape newlines
        if state_data.get('during_action'):
            actions.append(f"during / {state_data['during_action'].replace(chr(10), '; ')}")
        if state_data.get('exit_action'):
            actions.append(f"exit / {state_data['exit_action'].replace(chr(10), '; ')}")
        
        if actions:
            # PlantUML state actions are defined as: state_id : action1\naction2
            puml_text += f"{s_id} :\n"
            for action_line in actions:
                puml_text += f"  {action_line}\n"
        
        if state_data.get('is_initial'):
            initial_state_id = s_id
        if state_data.get('is_final'):
            puml_text += f"{s_id} --> [*]\n" # Final state marker

    # Initial state transition
    if initial_state_id:
        puml_text += f"[*] --> {initial_state_id}\n"
    
    # Define transitions
    for trans_data in transitions:
        src_name = trans_data.get('source')
        tgt_name = trans_data.get('target')

        if not src_name or not tgt_name:
            logger.warning(f"PlantUML Export: Skipping transition due to missing source/target. Data: {trans_data}")
            continue
            
        src_id = state_id_map.get(src_name)
        tgt_id = state_id_map.get(tgt_name)

        if not src_id or not tgt_id:
            logger.warning(f"PlantUML Export: Could not find mapped ID for source '{src_name}' or target '{tgt_name}'. Skipping transition.")
            continue
            
        label_parts = []
        if trans_data.get('event'):
            label_parts.append(trans_data['event'])
        if trans_data.get('condition'):
            label_parts.append(f"[{trans_data['condition']}]")
        if trans_data.get('action'):
            # Escape newlines in action for PlantUML label
            action_text = trans_data['action'].replace(chr(10), '\\n') 
            label_parts.append(f"/ {{{action_text}}}")
        
        label = " : ".join(label_parts) if label_parts else ""
        puml_text += f"{src_id} --> {tgt_id}{label}\n"

    # Add comments as notes (simplified: general notes, or attached to first state if specific attachment is hard)
    # PlantUML notes are more flexible; they can be attached to states or float.
    # For simplicity, we can make them float or attach to a state if an 'attach_to' field were in comment_data.
    for i, comment_data in enumerate(comments):
        comment_text = comment_data.get('text', '')
        if comment_text:
            # Sanitize comment text for PlantUML (e.g., escaping special characters if needed, though PlantUML notes are quite liberal)
            puml_text += f"\nnote \"{comment_text.replace(chr(10), '\\n')}\" as N{i}\n"


    puml_text += "\n@enduml\n"
    return puml_text