# bsm_designer_project/python_code_generator.py
import os
import re
import logging
import textwrap # For indenting code blocks
from PyQt5.QtCore import QDateTime, Qt # For timestamp

# Assuming config.py is in the same directory or accessible via package import
try:
    from .config import APP_NAME, APP_VERSION, DEFAULT_EXECUTION_ENV
except ImportError: # Fallback for direct execution or different structure
    APP_NAME = "BSM_Designer"
    APP_VERSION = "Unknown"
    DEFAULT_EXECUTION_ENV = "Python (Generic Simulation)"


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
    sanitized = name_str
    for char_to_replace in " .-:/\\[]{}()\"'":
        sanitized = sanitized.replace(char_to_replace, '_')

    # Remove any remaining characters not alphanumeric or underscore
    sanitized = "".join(c if c.isalnum() or c == '_' else '' for c in sanitized)

    # Collapse multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized)

    # Remove leading/trailing underscores that might have resulted from replacements at ends
    sanitized = sanitized.strip('_')

    # Ensure it's not empty after sanitization
    if not sanitized:
        return f"{prefix_if_invalid}sanitized_empty"

    # Check if it starts with a digit
    if sanitized[0].isdigit():
        sanitized = prefix_if_invalid + sanitized
    
    if not sanitized: # Could become empty if prefix_if_invalid was "" and original was just digits
        return f"{prefix_if_invalid}sanitized_empty_after_digit_prefix"

    # Check against Python keywords
    if sanitized in PYTHON_KEYWORDS:
        sanitized = f"{sanitized}_"

    # Final check for validity (e.g., if it became just underscores like "s___")
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', sanitized):
        generic_name = "".join(c if c.isalnum() else '_' for c in name_str if c.isprintable()) # Take only printables
        generic_name = re.sub(r'_+', '_', generic_name).strip('_')
        if not generic_name: return f"{prefix_if_invalid}fully_sanitized_empty"
        
        candidate = generic_name
        if candidate[0].isdigit(): candidate = prefix_if_invalid + candidate
        if candidate in PYTHON_KEYWORDS: candidate += "_"
        
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', candidate):
            # Create a unique hash-based suffix if still invalid
            import hashlib
            name_hash = hashlib.md5(name_str.encode()).hexdigest()[:6]
            return f"{prefix_if_invalid}id_{name_hash}"
        return candidate
        
    return sanitized


def generate_python_fsm_file(diagram_data: dict, output_dir: str, class_name_base: str) -> str:
    states = diagram_data.get('states', [])
    transitions = diagram_data.get('transitions', [])

    if not states:
        raise ValueError("Cannot generate Python code: No states defined in the diagram.")

    # Sanitize class name: should be CamelCase
    temp_class_name = sanitize_python_identifier(class_name_base, "FSM")
    if not temp_class_name: temp_class_name = "GeneratedFsm" # Fallback
    base_py_class_name = temp_class_name[0].upper() + temp_class_name[1:]


    py_code = []
    py_code.append(f"# Auto-generated Python FSM by {APP_NAME} v{APP_VERSION}")
    py_code.append(f"# FSM Name: {class_name_base}")
    py_code.append(f"# Generated on: {QDateTime.currentDateTime().toString(Qt.ISODate)}\n")

    py_code.append("from statemachine import StateMachine, State # Assuming Event is not directly used in simple defs\n")
    py_code.append(f"class {base_py_class_name}(StateMachine):\n")

    # --- State Definitions ---
    state_name_to_py_var = {}
    initial_state_py_var_name = None # Store the python variable name of the initial state
    
    # First pass: assign sanitized Python variable names for all states
    for s_data in states:
        original_name = s_data['name']
        py_var_name = sanitize_python_identifier(original_name.lower(), "state_")
        # Ensure uniqueness if sanitized names clash (rare but possible)
        temp_py_var_name = py_var_name
        count = 1
        while temp_py_var_name in state_name_to_py_var.values():
            temp_py_var_name = f"{py_var_name}_{count}"
            count += 1
        state_name_to_py_var[original_name] = temp_py_var_name
        if s_data.get('is_initial', False) and not initial_state_py_var_name:
            initial_state_py_var_name = temp_py_var_name


    # Default to first state if no initial state is explicitly set
    if not initial_state_py_var_name and states:
        first_state_orig_name = states[0]['name']
        initial_state_py_var_name = state_name_to_py_var[first_state_orig_name]
        logger.warning(f"Python Gen: No initial state explicitly set. Defaulting to first state: '{first_state_orig_name}'.")


    for s_data in states:
        original_name = s_data['name']
        py_var_name = state_name_to_py_var[original_name]
        
        is_initial = (py_var_name == initial_state_py_var_name)
        is_final = s_data.get('is_final', False)
        
        state_params = [f'name="{original_name}"', f'value="{original_name}"']
        if is_initial:
            state_params.append("initial=True")
        if is_final:
            state_params.append("final=True")
        
        entry_action_code = s_data.get('entry_action', "").strip()
        exit_action_code = s_data.get('exit_action', "").strip()
        
        if entry_action_code:
            entry_method_name = sanitize_python_identifier(f"on_enter_{original_name.lower()}", "action_")
            state_params.append(f'entry="{entry_method_name}"')
        if exit_action_code:
            exit_method_name = sanitize_python_identifier(f"on_exit_{original_name.lower()}", "action_")
            state_params.append(f'exit="{exit_method_name}"')

        py_code.append(f"    {py_var_name} = State({', '.join(state_params)})")

    py_code.append("")

    # --- Transition Definitions (using decorators for clarity if simple) ---
    # This part is more complex with python-statemachine if events are shared across many source/target pairs.
    # A simpler approach is direct transition definition: transition_name = source.to(target, event="...", on="...", cond="...")
    
    transition_definitions = [] # Store as (var_name, definition_str)
    transition_methods_to_generate = {} # method_name -> (code_str, comment_str)

    for i, t_data in enumerate(transitions):
        event_str = t_data.get('event', "").strip()
        if not event_str:
            logger.warning(f"Python Gen: Skipping eventless transition from {t_data['source']} to {t_data['target']}.")
            continue

        source_py_var = state_name_to_py_var.get(t_data['source'])
        target_py_var = state_name_to_py_var.get(t_data['target'])

        if not source_py_var or not target_py_var:
            logger.warning(f"Python Gen: Skipping transition due to unknown source/target: {t_data['source']}->{t_data['target']}")
            continue
        
        transition_var_name = sanitize_python_identifier(f"t_{source_py_var}_to_{target_py_var}_on_{event_str.lower()}", f"transition_{i}_")
        
        trans_params = [f'event="{event_str}"'] # Event is a string name here

        condition_code = t_data.get('condition', "").strip()
        action_code = t_data.get('action', "").strip()
        action_lang = t_data.get('action_language', DEFAULT_EXECUTION_ENV)

        if condition_code:
            cond_method_name = sanitize_python_identifier(f"check_{transition_var_name}", "cond_")
            trans_params.append(f"cond='{cond_method_name}'")
            comment = f"# Condition for transition: {t_data['source']} -> {t_data['target']} on event '{event_str}'"
            if "Python" not in action_lang:
                comment += f"\n        # WARNING: Original language was '{action_lang}'. Code below might not be Python compatible."
            transition_methods_to_generate[cond_method_name] = (f"return {condition_code}", comment)
            
        if action_code:
            action_method_name = sanitize_python_identifier(f"do_{transition_var_name}", "act_")
            trans_params.append(f"on='{action_method_name}'")
            comment = f"# Action for transition: {t_data['source']} -> {t_data['target']} on event '{event_str}'"
            if "Python" not in action_lang:
                 comment += f"\n        # WARNING: Original language was '{action_lang}'. Code below might not be Python compatible."
            transition_methods_to_generate[action_method_name] = (action_code or "pass", comment)
        
        transition_definitions.append(f"    {transition_var_name} = {source_py_var}.to({target_py_var}, {', '.join(trans_params)})")

    py_code.extend(transition_definitions)
    py_code.append("")

    # --- Method Implementations (Actions, Conditions, During) ---
    py_code.append("    # --- Action and Condition methods ---")
    
    # State entry/exit methods
    for s_data in states:
        original_name = s_data['name']
        for action_type_key, code_str_original in [
            ('entry_action', s_data.get('entry_action', "")),
            ('exit_action', s_data.get('exit_action', "")),
        ]:
            code_str_clean = code_str_original.strip()
            if code_str_clean:
                method_name_prefix = "on_enter_" if action_type_key == 'entry_action' else "on_exit_"
                method_name = sanitize_python_identifier(f"{method_name_prefix}{original_name.lower()}", "action_")
                py_code.append(f"\n    def {method_name}(self):")
                py_code.append(f"        # {action_type_key} for state: {original_name}")
                action_lang = s_data.get('action_language', DEFAULT_EXECUTION_ENV)
                if "Python" not in action_lang:
                    py_code.append(f"        # WARNING: Original language was '{action_lang}'. Code below might not be Python compatible.")
                py_code.append(textwrap.indent(code_str_clean if code_str_clean else "pass", "        "))

        # 'During' actions are not directly supported by python-statemachine state definitions.
        # They need to be handled by a self-transition or external logic.
        during_action_code = s_data.get('during_action', "").strip()
        if during_action_code:
            py_code.append(f"\n    # For 'during_action' of state '{original_name}':")
            action_lang = s_data.get('action_language', DEFAULT_EXECUTION_ENV)
            if "Python" not in action_lang:
                py_code.append(f"    # WARNING: Original language was '{action_lang}'. Code below might not be Python compatible.")
            py_code.append(textwrap.indent(f"# {during_action_code.replace(chr(10), chr(10) + '    # ')}", "    "))
            py_code.append(f"    # This can be implemented by: ")
            py_code.append(f"    # 1. Calling a method from your main loop when in state '{original_name}'.")
            py_code.append(f"    # 2. Creating a self-transition on an internal 'tick' event for state '{original_name}'.")


    # Transition condition/action methods
    for method_name, (code_str, comment_str) in transition_methods_to_generate.items():
        py_code.append(f"\n    def {method_name}(self):")
        py_code.append(f"        {comment_str}")
        py_code.append(textwrap.indent(code_str if code_str else "pass", "        "))
    
    py_code.append(f"\n\n# Example usage (you can uncomment and run this file):\n"
                   f"# if __name__ == '__main__':\n"
                   f"#     fsm = {base_py_class_name}()\n"
                   f"#     print(f'Initial state: {{fsm.current_state.id}}')\n"
                   f"#     # Example: fsm.send('your_event_name') # Or fsm.your_event_name() if events are attributes\n"
                   f"#     # print(f'State after event: {{fsm.current_state.id}}')")

    file_name = f"{base_py_class_name.lower()}.py"
    py_file_path = os.path.join(output_dir, file_name)
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