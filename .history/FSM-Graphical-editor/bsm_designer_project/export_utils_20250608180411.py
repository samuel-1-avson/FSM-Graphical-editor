# bsm_designer_project/export_utils.py
import logging
import re # For Mermaid sanitization

logger = logging.getLogger(__name__)

def _sanitize_id_general(name: str, prefix_if_digit: str = "id_") -> str:
    """
    General sanitizer for IDs (PlantUML, Mermaid, etc.).
    Removes/replaces common problematic characters. Ensures it doesn't start with a digit.
    """
    if not name:
        return f"{prefix_if_digit}Unnamed" # Default if name is empty
    
    # Replace spaces and common problematic characters with underscores or remove them
    sanitized = name.replace(' ', '_').replace('-', '_').replace('.', '_')
    sanitized = sanitized.replace(':', '_').replace('/', '_').replace('\\', '_')
    sanitized = sanitized.replace('(', '').replace(')', '').replace('[', '') # Mermaid dislikes these
    sanitized = sanitized.replace(']', '').replace('{', '').replace('}', '')
    sanitized = sanitized.replace('"', '').replace("'", "") # Remove quotes

    # Remove any remaining characters not alphanumeric or underscore
    sanitized = "".join(c if c.isalnum() or c == '_' else '' for c in sanitized)
    
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = prefix_if_digit + sanitized

    return sanitized if sanitized else f"{prefix_if_digit}SanitizedEmpty"


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
        s_id = f"{parent_id_prefix}__{_sanitize_id_general(s_original_name, 'sub_s_')}" # Using double underscore as a separator
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

    safe_diagram_name = _sanitize_id_general(diagram_name, "diag_")

    if not states:
        return f"@startuml {safe_diagram_name}\n' No states defined in the diagram.\n@enduml"

    puml_text = f"@startuml {safe_diagram_name}\n"
    puml_text += "left to right direction\n" 
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
    state_id_map = {} # Map of original state name to sanitized PlantUML ID

    # First pass: assign unique sanitized IDs to all top-level states
    for state_data in states:
        s_original_name = state_data.get('name', f'UnnamedState_{len(state_id_map)}')
        s_id = _sanitize_id_general(s_original_name, 's_')
        # Ensure uniqueness if sanitized names clash
        if s_id in state_id_map.values() and s_original_name not in state_id_map : # Check if sanitized ID is already used by a *different* original name
            s_id = f"{s_id}_{sum(1 for v in state_id_map.values() if v.startswith(s_id))}" 
        state_id_map[s_original_name] = s_id

    # Second pass: define states and their actions
    for state_data in states:
        s_original_name = state_data.get('name', 'ErrorStateName') # Should always have a name from first pass
        s_id = state_id_map.get(s_original_name)
        if not s_id: # Should not happen if first pass was correct
            logger.error(f"PlantUML Export: Could not find mapped ID for state '{s_original_name}'. Skipping state definition.")
            continue

        s_label = state_data.get('name', 'UnnamedState')
        
        if state_data.get('is_superstate') and state_data.get('sub_fsm_data'):
            puml_text += f"state \"{s_label}\" as {s_id} {{\n"
            # Pass the global state_id_map for sub-FSMs to use and potentially add to (for their internal states)
            puml_text += _generate_plantuml_sub_fsm(state_data['sub_fsm_data'], s_id, state_id_map, 1)
            puml_text += "}}\n"
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
            puml_text += f"{s_id} :\n" # Note: PlantUML state actions are defined after 'state Name as ID'
            for action_line in actions:
                puml_text += f"  {action_line}\n" # Indent actions
        
        if state_data.get('is_initial'):
            initial_state_id = s_id
        if state_data.get('is_final'):
            puml_text += f"{s_id} --> [*]\n"

    # Initial transition for the main FSM
    if initial_state_id:
        puml_text += f"[*] --> {initial_state_id}\n"
    
    # Define top-level transitions
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
            action_text = trans_data['action'].replace(chr(10), '\\n') # Escape newlines for PlantUML
            label_parts.append(f"/ {{{action_text}}}") # Use curly braces for actions for better parsing by PlantUML
        
        label = (" : " + " ".join(label_parts)) if label_parts else "" # Add colon only if there's a label
        puml_text += f"{src_id} --> {tgt_id}{label}\n"

    # Add comments as notes
    for i, comment_data in enumerate(comments):
        comment_text = comment_data.get('text', '')
        if comment_text:
            # PlantUML notes are best kept simple, newlines are supported with \n
            escaped_comment_text = comment_text.replace(chr(10), '\\n') 
            puml_text += f"\nnote \"{escaped_comment_text}\" as N_comment_{i}\n"
            # Could try to attach notes to nearest state if x,y are provided, but that's complex.
            # For now, just list them.

    puml_text += "\n@enduml\n"
    logger.debug("Generated PlantUML text: \n%s", puml_text)
    return puml_text


def _generate_mermaid_sub_fsm(sub_fsm_data: dict, parent_id_prefix: str, state_id_map: dict, indent_level: int = 1) -> str:
    """
    Recursively generates Mermaid text for a sub-FSM (composite state).
    """
    mermaid_text = ""
    indent = "  " * indent_level
    sub_states = sub_fsm_data.get('states', [])
    sub_transitions = sub_fsm_data.get('transitions', [])

    initial_sub_state_id = None

    for state_data in sub_states:
        s_original_name = state_data.get('name', f'UnnamedSubState_{len(state_id_map)}')
        s_id = f"{parent_id_prefix}__{_sanitize_id_general(s_original_name, 'sub_s_')}"
        state_id_map[f"{parent_id_prefix}/{s_original_name}"] = s_id
        s_label = state_data.get('name', 'UnnamedSubState').replace('"', '#quot;') # Mermaid label quote escape

        actions = []
        if state_data.get('entry_action'): actions.append(f"entry: {state_data['entry_action']}")
        if state_data.get('during_action'): actions.append(f"during: {state_data['during_action']}")
        if state_data.get('exit_action'): actions.append(f"exit: {state_data['exit_action']}")
        
        action_str_for_label = "<br/>".join(a.replace(chr(10), "<br/>").replace('"', '#quot;') for a in actions)
        full_label = f"{s_label}<br/>{action_str_for_label}" if action_str_for_label else s_label

        if state_data.get('is_superstate') and state_data.get('sub_fsm_data'):
            mermaid_text += f"{indent}state \"{full_label}\" as {s_id}\n" # Mermaid syntax for composite states is different
            mermaid_text += f"{indent}state {s_id} {{\n" # Start subgraph
            mermaid_text += _generate_mermaid_sub_fsm(state_data['sub_fsm_data'], s_id, state_id_map, indent_level + 1)
            mermaid_text += f"{indent}}}\n" # End subgraph
        else:
            mermaid_text += f"{indent}{s_id}[\"{full_label}\"]\n"
        
        if state_data.get('is_initial'): initial_sub_state_id = s_id
        if state_data.get('is_final'): mermaid_text += f"{indent}{s_id} --> [*]\n"
            
    if initial_sub_state_id:
        mermaid_text += f"{indent}[*] --> {initial_sub_state_id}\n"

    for trans_data in sub_transitions:
        src_original_name = trans_data.get('source')
        tgt_original_name = trans_data.get('target')
        if not src_original_name or not tgt_original_name: continue
            
        src_id = state_id_map.get(f"{parent_id_prefix}/{src_original_name}")
        tgt_id = state_id_map.get(f"{parent_id_prefix}/{tgt_original_name}")
        if not src_id or not tgt_id: continue
            
        label_parts = []
        if trans_data.get('event'): label_parts.append(trans_data['event'])
        if trans_data.get('condition'): label_parts.append(f"[{trans_data['condition']}]")
        if trans_data.get('action'): label_parts.append(f"/{trans_data['action']}")
        
        label = " : ".join(p.replace(chr(10), ' ').replace('"', '#quot;') for p in label_parts) if label_parts else ""
        mermaid_text += f"{indent}{src_id} --> {tgt_id} : {label}\n"
        
    return mermaid_text


def generate_mermaid_text(diagram_data: dict, diagram_title: str = "FSM Diagram") -> str:
    """
    Generates Mermaid JS text representation from diagram data.
    """
    states_data = diagram_data.get('states', [])
    transitions_data = diagram_data.get('transitions', [])
    comments_data = diagram_data.get('comments', [])
    if not states_data:
        return "```mermaid\nstateDiagram-v2\n  %% No states defined\n```"

    mermaid_text = "```mermaid\nstateDiagram-v2\n"
    mermaid_text += f"  %% Title: {diagram_title.replace(chr(10), ' ').replace('"', '')}\n"
    mermaid_text += "  direction LR\n" # Or TB

    initial_state_id = None
    state_id_map = {}  # Maps original name to sanitized Mermaid ID

    for state_data in states_data:
        s_original_name = state_data.get('name', f'UnnamedState_{len(state_id_map)}')
        s_id = _sanitize_id_general(s_original_name, 's_')
        if s_id in state_id_map.values() and s_original_name not in state_id_map:
            s_id = f"{s_id}_{sum(1 for v in state_id_map.values() if v.startswith(s_id))}"
        state_id_map[s_original_name] = s_id

    for state_data in states_data:
        s_original_name = state_data.get('name', 'ErrorStateName')
        s_id = state_id_map.get(s_original_name)
        if not s_id:
            logger.error(f"Mermaid Export: Could not find mapped ID for state '{s_original_name}'. Skipping.")
            continue

        s_label = state_data.get('name', 'UnnamedState').replace('"', '#quot;') # Escape quotes for Mermaid label
        
        actions = []
        if state_data.get('entry_action'): actions.append(f"entry: {state_data['entry_action']}")
        if state_data.get('during_action'): actions.append(f"during: {state_data['during_action']}")
        if state_data.get('exit_action'): actions.append(f"exit: {state_data['exit_action']}")
        
        # Clean action strings for Mermaid label (replace newlines, escape quotes)
        action_str_for_label = "<br/>".join(a.replace(chr(10), "<br/>").replace('"', '#quot;') for a in actions)
        
        full_label = f"{s_label}"
        if action_str_for_label:
            full_label += f"<br/>{action_str_for_label}"

        if state_data.get('is_superstate') and state_data.get('sub_fsm_data'):
            mermaid_text += f"  state \"{full_label}\" as {s_id}\n" # Define the superstate with its label
            mermaid_text += f"  state {s_id} {{\n" # Start subgraph definition
            mermaid_text += _generate_mermaid_sub_fsm(state_data['sub_fsm_data'], s_id, state_id_map, 2)
            mermaid_text += "  }}\n" # End subgraph
        else:
            mermaid_text += f"  {s_id}[\"{full_label}\"]\n"

        if state_data.get('is_initial'): initial_state_id = s_id
        if state_data.get('is_final'): mermaid_text += f"  {s_id} --> [*]\n"

    if initial_state_id:
        mermaid_text += f"  [*] --> {initial_state_id}\n"

    for trans_data in transitions_data:
        src_original_name = trans_data.get('source')
        tgt_original_name = trans_data.get('target')
        if not src_original_name or not tgt_original_name: continue

        src_id = state_id_map.get(src_original_name)
        tgt_id = state_id_map.get(tgt_original_name)
        if not src_id or not tgt_id: continue

        label_parts = []
        if trans_data.get('event'): label_parts.append(trans_data['event'])
        if trans_data.get('condition'): label_parts.append(f"[{trans_data['condition']}]")
        if trans_data.get('action'): label_parts.append(f"/{trans_data['action']}")
        
        # Clean label parts for Mermaid (replace newlines, escape quotes)
        label = " : ".join(p.replace(chr(10), ' ').replace('"', '#quot;') for p in label_parts) if label_parts else ""
        mermaid_text += f"  {src_id} --> {tgt_id} : {label}\n"

    for comment_data in comments_data:
        comment_text = comment_data.get('text', '')
        if comment_text:
            # Mermaid comments are `%% comment text`
            mermaid_text += f"  %% {comment_text.replace(chr(10), ' - ').replace('"', '')}\n"
            
    mermaid_text += "```\n"
    logger.debug("Generated Mermaid text: \n%s", mermaid_text)
    return mermaid_text