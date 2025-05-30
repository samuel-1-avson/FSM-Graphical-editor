# bsm_designer_project/export_utils.py
import logging

logger = logging.getLogger(__name__)

def _sanitize_puml_id(name: str) -> str:
    """
    Sanitizes a name to be a valid PlantUML ID.
    PlantUML IDs should generally not contain spaces or many special characters.
    Underscores are usually safe.
    """
    if not name:
        return "Unnamed_State" # Default if name is empty
    
    # Replace common problematic characters with underscores
    sanitized_name = name.replace(' ', '_').replace('-', '_').replace('.', '_')
    sanitized_name = sanitized_name.replace(':', '_').replace('/', '_').replace('\\', '_')
    sanitized_name = sanitized_name.replace('(', '_').replace(')', '_').replace('[', '_')
    sanitized_name = sanitized_name.replace(']', '_').replace('{', '_').replace('}', '_')
    
    # Remove any remaining characters not alphanumeric or underscore
    sanitized_name = "".join(c if c.isalnum() or c == '_' else '' for c in sanitized_name)
    
    # Ensure it doesn't start with a number (PlantUML alias requirement)
    if sanitized_name and sanitized_name[0].isdigit():
        sanitized_name = "s_" + sanitized_name # Prepend with a letter

    return sanitized_name if sanitized_name else "Sanitized_Empty_Name"

def _generate_plantuml_sub_fsm(sub_fsm_data: dict, parent_id_prefix: str, state_id_map: dict, indent_level: int = 1) -> str:
    """
    Recursively generates PlantUML text for a sub-FSM (composite state).
    Args:
        sub_fsm_data: The dictionary containing the sub-FSM structure.
        parent_id_prefix: The sanitized ID of the parent superstate, used for unique naming.
        state_id_map: The global map of original state names to their sanitized IDs.
        indent_level: Current indentation level for pretty printing.
    """
    puml_text = ""
    indent = "  " * indent_level
    sub_states = sub_fsm_data.get('states', [])
    sub_transitions = sub_fsm_data.get('transitions', [])
    # sub_comments = sub_fsm_data.get('comments', []) # Comments in sub-diagrams are harder to place contextually

    initial_sub_state_id = None

    # Define sub-states
    for state_data in sub_states:
        s_original_name = state_data.get('name', f'UnnamedSubState_{len(state_id_map)}')
        # Sub-state IDs need to be unique globally or within their parent context.
        # Here, we make them unique by prefixing with parent_id.
        s_id = f"{parent_id_prefix}__{_sanitize_puml_id(s_original_name)}" # Using double underscore as a separator
        state_id_map[f"{parent_id_prefix}/{s_original_name}"] = s_id # Store mapping for transitions within this sub-FSM

        s_label = state_data.get('name', 'UnnamedSubState')
        
        if state_data.get('is_superstate') and state_data.get('sub_fsm_data'):
            puml_text += f"{indent}state \"{s_label}\" as {s_id} {{\n"
            puml_text += _generate_plantuml_sub_fsm(state_data['sub_fsm_data'], s_id, state_id_map, indent_level + 1)
            puml_text += f"{indent}}}\n"
        else:
            puml_text += f"{indent}state \"{s_label}\" as {s_id}\n"
        
        actions = []
        if state_data.get('entry_action'):
            actions.append(f"entry / {state_data['entry_action'].replace(chr(10), '\\n  ')}")
        if state_data.get('during_action'):
            actions.append(f"during / {state_data['during_action'].replace(chr(10), '\\n  ')}")
        if state_data.get('exit_action'):
            actions.append(f"exit / {state_data['exit_action'].replace(chr(10), '\\n  ')}")
        
        if actions:
            puml_text += f"{indent}{s_id} :\n"
            for action_line in actions:
                puml_text += f"{indent}  {action_line}\n"

        if state_data.get('is_initial'):
            initial_sub_state_id = s_id
        if state_data.get('is_final'):
            puml_text += f"{indent}{s_id} --> [*]\n"

    # Initial transition for the sub-machine
    if initial_sub_state_id:
        puml_text += f"{indent}[*] --> {initial_sub_state_id}\n"
    
    # Define sub-transitions
    for trans_data in sub_transitions:
        src_original_name = trans_data.get('source')
        tgt_original_name = trans_data.get('target')
        
        if not src_original_name or not tgt_original_name:
            logger.warning(f"PlantUML Sub-FSM Export: Skipping transition due to missing source/target. Data: {trans_data}")
            continue
            
        # Use the prefixed names for lookup in state_id_map for sub-FSM context
        src_id = state_id_map.get(f"{parent_id_prefix}/{src_original_name}")
        tgt_id = state_id_map.get(f"{parent_id_prefix}/{tgt_original_name}")

        if not src_id or not tgt_id:
            logger.warning(f"PlantUML Sub-FSM Export: Could not find mapped ID for source '{src_original_name}' or target '{tgt_original_name}' within '{parent_id_prefix}'. Skipping.")
            continue
            
        label_parts = []
        if trans_data.get('event'):
            label_parts.append(trans_data['event'])
        if trans_data.get('condition'):
            label_parts.append(f"[{trans_data['condition']}]")
        if trans_data.get('action'):
            action_text = trans_data['action'].replace(chr(10), '\\n')
            label_parts.append(f"/ {{{action_text}}}")
        
        label = (" : " + " ".join(label_parts)) if label_parts else "" # Add colon only if there's a label
        puml_text += f"{indent}{src_id} --> {tgt_id}{label}\n"
        
    return puml_text


def generate_plantuml_text(diagram_data: dict, diagram_name: str = "FSM_Diagram") -> str:
    """
    Generates PlantUML text representation from diagram data.
    """
    states = diagram_data.get('states', [])
    transitions = diagram_data.get('transitions', [])
    comments = diagram_data.get('comments', [])

    # Sanitize the diagram name itself for use in PlantUML if needed, though it's often just a title.
    safe_diagram_name = _sanitize_puml_id(diagram_name)

    if not states:
        return f"@startuml {safe_diagram_name}\n' No states defined in the diagram.\n@enduml"

    puml_text = f"@startuml {safe_diagram_name}\n"
    puml_text += "left to right direction\n" # Or 'top to bottom direction'
    puml_text += "skinparam state {\n"
    puml_text += "  BackgroundColor FloralWhite\n"
    puml_text += "  BorderColor BurlyWood\n"
    puml_text += "  FontName Arial\n"
    puml_text += "  FontSize 12\n"
    puml_text += "  ArrowColor Olive\n"
    puml_text += "}\n"
    puml_text += "skinparam note {\n"
    puml_text += "  BackgroundColor LightYellow\n"
    puml_text += "  BorderColor Orange\n"
    puml_text += "}\n"
    puml_text += "hide empty description\n\n"

    initial_state_id = None
    state_id_map = {} # Map original state name to sanitized PlantUML ID

    # Pass 1: Define all states and map original names to sanitized IDs
    # This is important for transitions that might reference states defined later.
    for state_data in states:
        s_original_name = state_data.get('name', f'UnnamedState_{len(state_id_map)}')
        s_id = _sanitize_puml_id(s_original_name)
        if s_id in state_id_map.values() and s_original_name not in state_id_map : # ID conflict from sanitization
            s_id = f"{s_id}_{sum(1 for v in state_id_map.values() if v.startswith(s_id))}" # Make unique
        state_id_map[s_original_name] = s_id

    # Pass 2: Generate state definitions and actions
    for state_data in states:
        s_original_name = state_data.get('name', 'ErrorStateName') # Should have been caught if empty
        s_id = state_id_map.get(s_original_name)
        if not s_id: # Should not happen if Pass 1 was successful
            logger.error(f"PlantUML Export: Could not find mapped ID for state '{s_original_name}'. Skipping state definition.")
            continue

        s_label = state_data.get('name', 'UnnamedState')
        
        if state_data.get('is_superstate') and state_data.get('sub_fsm_data'):
            # For sub-FSMs, state_id_map is passed to allow _generate_plantuml_sub_fsm
            # to correctly map its internal transitions using globally unique IDs.
            puml_text += f"state \"{s_label}\" as {s_id} {{\n"
            puml_text += _generate_plantuml_sub_fsm(state_data['sub_fsm_data'], s_id, state_id_map, 1)
            puml_text += "}\n"
        else:
            puml_text += f"state \"{s_label}\" as {s_id}\n"

        actions = []
        if state_data.get('entry_action'):
            actions.append(f"entry / {state_data['entry_action'].replace(chr(10), '\\n  ')}")
        if state_data.get('during_action'):
            actions.append(f"during / {state_data['during_action'].replace(chr(10), '\\n  ')}")
        if state_data.get('exit_action'):
            actions.append(f"exit / {state_data['exit_action'].replace(chr(10), '\\n  ')}")
        
        if actions:
            puml_text += f"{s_id} :\n" # Colon indicates actions follow
            for action_line in actions:
                puml_text += f"  {action_line}\n" # Indent actions for readability
        
        if state_data.get('is_initial'):
            initial_state_id = s_id
        if state_data.get('is_final'):
            puml_text += f"{s_id} --> [*]\n"

    # Initial state transition for the main FSM
    if initial_state_id:
        puml_text += f"[*] --> {initial_state_id}\n"
    
    # Define transitions
    for trans_data in transitions:
        src_original_name = trans_data.get('source')
        tgt_original_name = trans_data.get('target')

        if not src_original_name or not tgt_original_name:
            logger.warning(f"PlantUML Export: Skipping transition due to missing source/target. Data: {trans_data}")
            continue
            
        src_id = state_id_map.get(src_original_name)
        tgt_id = state_id_map.get(tgt_original_name)

        if not src_id or not tgt_id:
            logger.warning(f"PlantUML Export: Could not find mapped ID for source '{src_original_name}' or target '{tgt_original_name}'. Skipping transition.")
            continue
            
        label_parts = []
        if trans_data.get('event'):
            label_parts.append(trans_data['event'])
        if trans_data.get('condition'):
            label_parts.append(f"[{trans_data['condition']}]")
        if trans_data.get('action'):
            action_text = trans_data['action'].replace(chr(10), '\\n') # Escape newlines for PlantUML label
            label_parts.append(f"/ {{{action_text}}}") # Use curly braces for action per some conventions
        
        label = (" : " + " ".join(label_parts)) if label_parts else "" # Add colon only if there's a label
        puml_text += f"{src_id} --> {tgt_id}{label}\n"

    # Add diagram-level comments as floating notes
    for i, comment_data in enumerate(comments):
        comment_text = comment_data.get('text', '')
        if comment_text:
            # Ensure quotes within the comment text are handled if necessary for PlantUML notes
            # PlantUML notes are generally quite flexible with content.
            escaped_comment_text = comment_text.replace(chr(10), '\\n') # Handle newlines
            puml_text += f"\nnote \"{escaped_comment_text}\" as N_comment_{i}\n"

    puml_text += "\n@enduml\n"
    logger.debug("Generated PlantUML text: \n%s", puml_text)
    return puml_text