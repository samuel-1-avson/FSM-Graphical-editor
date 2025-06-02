# bsm_designer_project/c_code_generator.py
import os
import re
import logging

logger = logging.getLogger(__name__)

def sanitize_c_identifier(name_str: str, prefix_if_digit="s_") -> str:
    if not name_str:
        return f"{prefix_if_digit}Unnamed"
    
    # Replace spaces and common problematic characters with underscores
    sanitized = name_str.replace(' ', '_').replace('-', '_').replace('.', '_')
    sanitized = sanitized.replace(':', '_').replace('/', '_').replace('\\', '_')
    sanitized = sanitized.replace('(', '').replace(')', '').replace('[', '')
    sanitized = sanitized.replace(']', '').replace('{', '').replace('}', '')
    sanitized = sanitized.replace('"', '').replace("'", "")

    # Remove any remaining characters not alphanumeric or underscore
    sanitized = "".join(c if c.isalnum() or c == '_' else '' for c in sanitized)
    
    # Ensure it doesn't start with a number and isn't a C keyword
    # Basic C keywords list (can be expanded)
    c_keywords = {
        "auto", "break", "case", "char", "const", "continue", "default", "do",
        "double", "else", "enum", "extern", "float", "for", "goto", "if",
        "int", "long", "register", "return", "short", "signed", "sizeof", "static",
        "struct", "switch", "typedef", "union", "unsigned", "void", "volatile", "while"
    }
    if sanitized in c_keywords:
        sanitized = f"fsm_{sanitized}"

    if not sanitized: # If all characters were problematic
         return f"{prefix_if_digit}SanitizedEmpty"
    if sanitized[0].isdigit():
        sanitized = prefix_if_digit + sanitized
    
    return sanitized

def generate_c_code_files(diagram_data: dict, output_dir: str, base_filename: str) -> tuple[str, str]:
    states = diagram_data.get('states', [])
    transitions = diagram_data.get('transitions', [])

    if not states:
        raise ValueError("Cannot generate code: No states defined in the diagram.")

    base_filename_c = sanitize_c_identifier(base_filename, "fsm_")

    # --- Prepare Data ---
    state_name_to_enum = {}
    state_name_to_data = {s['name']: s for s in states}
    initial_state_c_name = None

    c_code = []
    h_code = []

    # Create state enums
    h_code.append(f"#ifndef {base_filename_c.upper()}_H")
    h_code.append(f"#define {base_filename_c.upper()}_H\n")
    h_code.append("typedef enum {")
    for i, state_data in enumerate(states):
        c_name = sanitize_c_identifier(state_data['name'])
        state_name_to_enum[state_data['name']] = f"STATE_{c_name.upper()}"
        h_code.append(f"    {state_name_to_enum[state_data['name']]},")
        if state_data.get('is_initial', False):
            if initial_state_c_name:
                logger.warning(f"Multiple initial states found. Using the first one: {initial_state_c_name}")
            else:
                initial_state_c_name = state_name_to_enum[state_data['name']]
    h_code.append("    FSM_NUM_STATES") # For array sizing or loop limits if needed
    h_code.append("} FSM_State_t;\n")

    if not initial_state_c_name and states:
        first_state_name = states[0]['name']
        initial_state_c_name = state_name_to_enum[first_state_name]
        logger.warning(f"No initial state explicitly set. Defaulting to first state: {first_state_name} ({initial_state_c_name})")


    # Create event enums (or #defines)
    unique_events = sorted(list(set(t['event'] for t in transitions if t.get('event'))))
    event_name_to_id = {}
    if unique_events:
        h_code.append("typedef enum {")
        for i, event_name_str in enumerate(unique_events):
            c_event_name = sanitize_c_identifier(event_name_str, "event_")
            event_id = f"EVENT_{c_event_name.upper()}"
            event_name_to_id[event_name_str] = event_id
            h_code.append(f"    {event_id},")
        h_code.append("    FSM_NUM_EVENTS")
        h_code.append("} FSM_Event_t;\n")
    else:
        h_code.append("// No events with names defined in transitions.\n")


    # --- Generate .h file content ---
    h_code.append("// Function Prototypes for FSM")
    h_code.append(f"void {base_filename_c}_init(void);")
    h_code.append(f"void {base_filename_c}_run(FSM_Event_t event_id); // Pass event_id or -1 for during_action")
    h_code.append(f"FSM_State_t {base_filename_c}_get_current_state(void);\n")
    
    h_code.append("// User-defined Action Function Prototypes (implement these!)")
    action_prototypes = set()
    for state_data in states:
        for action_type in ['entry_action', 'during_action', 'exit_action']:
            action_code = state_data.get(action_type)
            if action_code: 
                func_name = sanitize_c_identifier(f"{action_type}_{state_data['name']}")
                action_prototypes.add(f"void {func_name}(void);")
    for trans_data in transitions:
        action_code = trans_data.get('action')
        if action_code:
            event_suffix = sanitize_c_identifier(trans_data.get('event',''))
            func_name = sanitize_c_identifier(f"action_trans_{trans_data['source']}_to_{trans_data['target']}" + (f"_{event_suffix}" if event_suffix else ""))
            action_prototypes.add(f"void {func_name}(void);")
    
    for proto in sorted(list(action_prototypes)):
        h_code.append(proto)
    h_code.append("\n#endif // " + f"{base_filename_c.upper()}_H")


    # --- Generate .c file content ---
    c_code.append(f'#include "{base_filename_c}.h"')
    c_code.append("#include <stdio.h> // For basic printf in stubs\n") # Example include

    c_code.append("static FSM_State_t current_fsm_state;\n")
    # Placeholder for FSM variables if you decide to support them (e.g. from Python sim)
    c_code.append("// --- FSM Global Variables (if any) ---")
    c_code.append("// Example: static int my_fsm_variable = 0;\n")

    c_code.append(f"void {base_filename_c}_init(void) {{")
    if initial_state_c_name:
        c_code.append(f"    current_fsm_state = {initial_state_c_name};")
        initial_state_orig_name = next((s['name'] for s in states if state_name_to_enum[s['name']] == initial_state_c_name), None)
        if initial_state_orig_name:
            entry_action_code = state_name_to_data[initial_state_orig_name].get('entry_action')
            if entry_action_code:
                func_name = sanitize_c_identifier(f"entry_action_{initial_state_orig_name}")
                c_code.append(f"    {func_name}();")
    else:
        c_code.append("    // ERROR: No initial state defined!")
    c_code.append("}\n")

    c_code.append(f"FSM_State_t {base_filename_c}_get_current_state(void) {{")
    c_code.append("    return current_fsm_state;")
    c_code.append("}\n")

    c_code.append(f"void {base_filename_c}_run(FSM_Event_t event_id) {{")
    c_code.append("    FSM_State_t next_state = current_fsm_state;")
    c_code.append("    int transition_taken = 0;\n")
    c_code.append("    switch (current_fsm_state) {")

    for state_data in states:
        state_enum_val = state_name_to_enum[state_data['name']]
        c_code.append(f"        case {state_enum_val}: {{")
        
        # During Action
        during_action_code = state_data.get('during_action')
        if during_action_code:
            func_name = sanitize_c_identifier(f"during_action_{state_data['name']}")
            c_code.append(f"            // During action for {state_data['name']}")
            c_code.append(f"            if (event_id == -1) {{ // Assuming -1 or specific value for 'no event' / tick")
            c_code.append(f"                {func_name}();")
            c_code.append(f"            }}")


        # Transitions from this state
        first_trans_for_state = True
        for trans_data in transitions:
            if trans_data['source'] == state_data['name']:
                event_name_str = trans_data.get('event')
                target_state_enum_val = state_name_to_enum[trans_data['target']]
                condition_str = trans_data.get('condition',"").strip() # User writes C conditions
                trans_action_code = trans_data.get('action')

                if_prefix = "if" if first_trans_for_state else "else if"
                first_trans_for_state = False
                
                event_check = "1" # Always true if no event name defined for this transition
                if event_name_str and event_name_str in event_name_to_id:
                    event_check = f"(event_id == {event_name_to_id[event_name_str]})"
                elif event_name_str: # Event string exists but not in our enum (e.g. if user makes a typo)
                    c_code.append(f"            // WARNING: Event '{event_name_str}' for transition to {trans_data['target']} not found in event enum.")
                    event_check = "0" # Effectively disable this transition

                condition_check = f"({condition_str})" if condition_str else "(1)" # Default to true if no condition

                c_code.append(f"            {if_prefix} ({event_check} && {condition_check}) {{")
                
                # Exit action of current state
                exit_action_code = state_data.get('exit_action')
                if exit_action_code:
                    func_name = sanitize_c_identifier(f"exit_action_{state_data['name']}")
                    c_code.append(f"                {func_name}();")

                # Transition action
                if trans_action_code:
                    event_suffix = sanitize_c_identifier(trans_data.get('event',''))
                    func_name = sanitize_c_identifier(f"action_trans_{trans_data['source']}_to_{trans_data['target']}" + (f"_{event_suffix}" if event_suffix else ""))
                    c_code.append(f"                {func_name}();")
                
                c_code.append(f"                next_state = {target_state_enum_val};")
                c_code.append(f"                transition_taken = 1;")

                # Entry action of next state (only if state changes)
                # This will be handled after the switch for clarity, if transition_taken
                c_code.append("            }")
        
        c_code.append("            break;") # Break from this state's case
        c_code.append("        }") # Close case block
        
    c_code.append("        default:")
    c_code.append("            // Should not happen")
    c_code.append("            break;")
    c_code.append("    } // end switch (current_fsm_state)\n")

    c_code.append("    if (transition_taken && next_state != current_fsm_state) {")
    # This loop is a bit inefficient but clear for now. Could use a function map.
    for state_data_for_entry in states:
        state_enum_val_entry = state_name_to_enum[state_data_for_entry['name']]
        entry_action_code_entry = state_data_for_entry.get('entry_action')
        if entry_action_code_entry:
            func_name_entry = sanitize_c_identifier(f"entry_action_{state_data_for_entry['name']}")
            c_code.append(f"        if (next_state == {state_enum_val_entry}) {{ {func_name_entry}(); }}")
    c_code.append("    }\n")
    
    c_code.append("    current_fsm_state = next_state;")
    c_code.append("}\n") # end fsm_run


    # --- Generate Action Function Stubs ---
    c_code.append("\n// --- User-Defined Action Function Implementations (STUBS) ---")
    c_code.append("// --- Please fill these in with your custom logic ---")
    for proto in sorted(list(action_prototypes)):
        func_signature = proto[:-1] # Remove semicolon
        c_code.append(f"{func_signature} {{")
        c_code.append(f"    // TODO: Implement action for {func_signature.split(' ')[1]}")
        c_code.append(f"    // printf(\"Action: {func_signature.split(' ')[1]} called\\n\");")
        c_code.append("}\n")

    # --- Write files ---
    h_file_path = os.path.join(output_dir, f"{base_filename_c}.h")
    c_file_path = os.path.join(output_dir, f"{base_filename_c}.c")

    try:
        with open(h_file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(h_code))
        logger.info(f"Generated C header file: {h_file_path}")

        with open(c_file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(c_code))
        logger.info(f"Generated C source file: {c_file_path}")
        
        return c_file_path, h_file_path
    except IOError as e:
        logger.error(f"IOError writing C code files: {e}")
        raise IOError(f"Failed to write C code files: {e}")
    except Exception as e:
        logger.error(f"Unexpected error writing C code files: {e}", exc_info=True)
        raise Exception(f"An unexpected error occurred while writing C code: {e}")