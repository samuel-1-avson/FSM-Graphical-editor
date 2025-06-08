# bsm_designer_project/python_code_generator.py
import os
import re
import logging
import textwrap # For indenting code blocks

logger = logging.getLogger(__name__)

PYTHON_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
    "while", "with", "yield"
}

def sanitize_python_identifier(name_str: str, prefix_if_invalid="s_") -> str:
    if not name_str:
        return f"{prefix_if_invalid}unnamed_identifier"

    # Replace spaces and common problematic characters with underscores
    sanitized = name_str.replace(' ', '_').replace('-', '_').replace('.', '_')
    sanitized = sanitized.replace(':', '_').replace('/', '_').replace('\\', '_')
    sanitized = sanitized.replace('(', '_').replace(')', '_').replace('[', '_') # Underscore for these too
    sanitized = sanitized.replace(']', '_').replace('{', '_').replace('}', '_')
    sanitized = sanitized.replace('"', '_').replace("'", "_")

    # Remove any remaining characters not alphanumeric or underscore
    sanitized = "".join(c if c.isalnum() or c == '_' else '' for c in sanitized)

    # Remove leading/trailing underscores that might have resulted
    sanitized = sanitized.strip('_')

    # Ensure it's not empty after sanitization
    if not sanitized:
        return f"{prefix_if_invalid}sanitized_empty"

    # Check if it starts with a digit
    if sanitized[0].isdigit():
        sanitized = prefix_if_invalid + sanitized

    # Check against Python keywords
    if sanitized in PYTHON_KEYWORDS:
        sanitized = f"{sanitized}_" # Add trailing underscore for keywords

    # Ensure it's a valid identifier after all changes (e.g. not just underscores)
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', sanitized):
        # If still not valid (e.g., "___"), provide a generic prefix
        return f"{prefix_if_invalid}{sanitized}".replace("__", "_") # Basic cleanup

    return sanitized

def generate_python_fsm_file(diagram_data: dict, output_dir: str, class_name_base: str) -> str:
    states = diagram_data.get('states', [])
    transitions = diagram_data.get('transitions', [])

    if not states:
        raise ValueError("Cannot generate Python code: No states defined in the diagram.")

    base_py_class_name = sanitize_python_identifier(class_name_base.capitalize(), "FSM")
    if not base_py_class_name[0].isupper(): # Ensure class name starts with uppercase
        base_py_class_name = base_py_class_name[0].upper() + base_py_class_name[1:]


    py_code = []
    py_code.append(f"# Auto-generated Python FSM by {APP_NAME} v{APP_VERSION}") # Use APP_NAME, APP_VERSION from config if available
    py_code.append(f"# FSM Name: {class_name_base}")
    py_code.append(f"# Generated on: {QDateTime.currentDateTime().toString(Qt.ISODate)}\n") # Requires QDateTime, Qt from PyQt5.QtCore

    py_code.append("from statemachine import StateMachine, State, Event\n")
    py_code.append(f"class {base_py_class_name}(StateMachine):\n")

    # --- State Definitions ---
    state_name_to_py_var = {}
    initial_state_py_var = None
    for s_data in states:
        original_name = s_data['name']
        py_var_name = sanitize_python_identifier(original_name.lower(), "state_")
        state_name_to_py_var[original_name] = py_var_name

        is_initial = s_data.get('is_initial', False)
        is_final = s_data.get('is_final', False)
        
        state_params = [f'name="{original_name}"', f'value="{original_name}"'] # Use original name for value too for simplicity
        if is_initial:
            state_params.append("initial=True")
            initial_state_py_var = py_var_name
        if is_final:
            state_params.append("final=True")
        
        # Add entry/exit/during actions as methods
        entry_action_code = s_data.get('entry_action', "").strip()
        exit_action_code = s_data.get('exit_action', "").strip()
        during_action_code = s_data.get('during_action', "").strip() # python-statemachine doesn't have direct "during" on State def

        entry_method_name = None
        exit_method_name = None
        
        if entry_action_code:
            entry_method_name = sanitize_python_identifier(f"on_enter_{original_name.lower()}", "action_")
            state_params.append(f'entry="{entry_method_name}"')
        if exit_action_code:
            exit_method_name = sanitize_python_identifier(f"on_exit_{original_name.lower()}", "action_")
            state_params.append(f'exit="{exit_method_name}"')

        py_code.append(f"    {py_var_name} = State({', '.join(state_params)})")

    if not initial_state_py_var and state_name_to_py_var: # Default to first if none explicitly initial
        first_state_orig_name = states[0]['name']
        first_state_py_var = state_name_to_py_var[first_state_orig_name]
        # Need to modify the existing line for this state to add initial=True
        for i, line in enumerate(py_code):
            if line.strip().startswith(f"{first_state_py_var} = State("):
                if "initial=True" not in line:
                    py_code[i] = line.rstrip(')') + ", initial=True)"
                break
        logger.warning(f"Python Gen: No initial state set. Defaulting to '{first_state_orig_name}'.")

    py_code.append("") # Blank line

    # --- Event and Transition Definitions ---
    # Group transitions by event for cleaner Event definitions
    events_to_transitions_map = {} # event_str -> list of (source_py_var, target_py_var, cond_method_name, action_method_name)

    for t_data in transitions:
        event_str = t_data.get('event', "").strip()
        if not event_str: # Eventless transitions are harder with python-statemachine declarations
            logger.warning(f"Python Gen: Skipping eventless transition from {t_data['source']} to {t_data['target']}. Consider adding an internal event name.")
            continue

        source_py_var = state_name_to_py_var.get(t_data['source'])
        target_py_var = state_name_to_py_var.get(t_data['target'])

        if not source_py_var or not target_py_var:
            logger.warning(f"Python Gen: Skipping transition due to unknown source/target: {t_data['source']}->{t_data['target']}")
            continue
        
        condition_code = t_data.get('condition', "").strip()
        action_code = t_data.get('action', "").strip()

        cond_method_name = None
        if condition_code:
            cond_method_name = sanitize_python_identifier(f"cond_{source_py_var}_to_{target_py_var}_on_{event_str.lower()}", "check_")
            
        action_method_name = None
        if action_code:
            action_method_name = sanitize_python_identifier(f"act_{source_py_var}_to_{target_py_var}_on_{event_str.lower()}", "do_")

        if event_str not in events_to_transitions_map:
            events_to_transitions_map[event_str] = []
        events_to_transitions_map[event_str].append((source_py_var, target_py_var, cond_method_name, action_method_name))

    # Create Event objects and assign transitions
    event_py_var_names = {}
    for event_str, trans_details_list in events_to_transitions_map.items():
        event_py_var = sanitize_python_identifier(event_str.lower(), "event_")
        event_py_var_names[event_str] = event_py_var
        py_code.append(f"    {event_py_var} = Event(name='{event_str}')") # Define event first

        for source_py_var, target_py_var, cond_method_name, action_method_name in trans_details_list:
            transition_params = [f"event={event_py_var}"]
            if cond_method_name:
                transition_params.append(f"cond='{cond_method_name}'")
            if action_method_name:
                transition_params.append(f"on='{action_method_name}'")
            
            # Transition definition: my_event = state1.to(state2, event=my_event_obj, on="action", cond="condition")
            # Or use event decorators: @my_event.to(state2) | state1
            # For simplicity, let's use the direct assignment for now.
            # It's hard to dynamically generate the decorator syntax easily if one event has multiple source states.
            # Alternative: define transitions within the Event() constructor if possible, or use event.transitions(...)
            # Let's try: event_name = State.to(State, event=..., on=..., cond=...)
            
            transition_var_name = sanitize_python_identifier(f"t_{source_py_var}_to_{target_py_var}_on_{event_py_var}", "trans_")
            py_code.append(f"    {transition_var_name} = {source_py_var}.to({target_py_var}, {', '.join(transition_params)})")

    py_code.append("")

    # --- Method Implementations (Actions, Conditions, During) ---
    py_code.append("    # --- Action, Condition, and During methods ---")
    
    # State entry/exit/during methods
    for s_data in states:
        original_name = s_data['name']
        for action_type_key, action_code_str in [
            ('entry_action', s_data.get('entry_action', "")),
            ('exit_action', s_data.get('exit_action', "")),
            # ('during_action', s_data.get('during_action', "")) # 'during' needs special handling
        ]:
            action_code_str = action_code_str.strip()
            if action_code_str:
                method_name_prefix = "on_enter_" if action_type_key == 'entry_action' else "on_exit_"
                method_name = sanitize_python_identifier(f"{method_name_prefix}{original_name.lower()}", "action_")
                py_code.append(f"\n    def {method_name}(self):")
                py_code.append(f"        # Original {action_type_key} for state: {original_name}")
                py_code.append(textwrap.indent(action_code_str if action_code_str else "pass", "        "))

        # Handle 'during' actions - python-statemachine doesn't have a direct 'during' hook on states.
        # One way is to create a self-transition on an internal "tick" event.
        during_action_code = s_data.get('during_action', "").strip()
        if during_action_code:
            state_py_var = state_name_to_py_var.get(original_name)
            during_method_name = sanitize_python_identifier(f"during_{original_name.lower()}", "action_")
            
            # Create a method for the during action
            py_code.append(f"\n    def {during_method_name}(self):")
            py_code.append(f"        # Original during_action for state: {original_name}")
            py_code.append(textwrap.indent(during_action_code if during_action_code else "pass", "        "))

            # Add a comment about how to trigger it, or define a specific internal event
            py_code.append(f"        # TODO: To simulate 'during' for {original_name}, trigger an internal event")
            py_code.append(f"        # that causes a self-transition on {state_py_var} calling this method,")
            py_code.append(f"        # or call this method from your external loop when in this state.")
            # Example:
            # internal_tick_event = Event(name="internal_tick")
            # t_during_my_state = my_state.to(my_state, event=internal_tick_event, on="during_my_state_method")


    # Transition condition/action methods
    for event_str, trans_details_list in events_to_transitions_map.items():
        for source_py_var, target_py_var, cond_method_name, action_method_name in trans_details_list:
            original_source_name = next(k for k,v in state_name_to_py_var.items() if v == source_py_var)
            original_target_name = next(k for k,v in state_name_to_py_var.items() if v == target_py_var)
            
            # Find original condition/action code
            original_cond_code = ""
            original_action_code = ""
            for t_data_orig in transitions:
                if t_data_orig.get('source') == original_source_name and \
                   t_data_orig.get('target') == original_target_name and \
                   t_data_orig.get('event') == event_str:
                    original_cond_code = t_data_orig.get('condition',"").strip()
                    original_action_code = t_data_orig.get('action',"").strip()
                    break 

            if cond_method_name and original_cond_code:
                py_code.append(f"\n    def {cond_method_name}(self):")
                py_code.append(f"        # Condition for transition: {original_source_name} -> {original_target_name} on event '{event_str}'")
                py_code.append(textwrap.indent(f"return {original_cond_code}" if original_cond_code else "return True", "        "))
            
            if action_method_name and original_action_code:
                py_code.append(f"\n    def {action_method_name}(self):")
                py_code.append(f"        # Action for transition: {original_source_name} -> {original_target_name} on event '{event_str}'")
                py_code.append(textwrap.indent(original_action_code if original_action_code else "pass", "        "))
    
    py_code.append("\n# Example usage (you can uncomment and run this file):\n"
                   f"# if __name__ == '__main__':\n"
                   f"#     fsm = {base_py_class_name}()\n"
                   f"#     print(f'Initial state: {{fsm.current_state.id}}')\n"
                   f"#     # Example: fsm.send('your_event_name')\n"
                   f"#     # print(f'State after event: {{fsm.current_state.id}}')")

    py_file_path = os.path.join(output_dir, f"{base_py_class_name.lower()}.py")
    try:
        with open(py_file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(py_code))
        logger.info(f"Generated Python FSM file: {py_file_path}")
        return py_file_path
    except IOError as e:
        logger.error(f"IOError writing Python FSM file: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error writing Python FSM file: {e}", exc_info=True)
        raise