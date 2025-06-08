# bsm_designer_project/c_code_generator.py
import os
import re
import logging
import html # For unescaping if needed, though less likely here

logger = logging.getLogger(__name__)

def sanitize_c_identifier(name_str: str, prefix_if_digit="s_") -> str:
    if not name_str:
        return f"{prefix_if_digit}Unnamed"
    
    # Replace spaces and common problematic characters with underscores
    sanitized = name_str.replace(' ', '_').replace('-', '_').replace('.', '_')
    sanitized = sanitized.replace(':', '_').replace('/', '_').replace('\\', '_')
    sanitized = sanitized.replace('(', '').replace(')', '').replace('[', '') # Remove parentheses and brackets
    sanitized = sanitized.replace(']', '').replace('{', '').replace('}', '')
    sanitized = sanitized.replace('"', '').replace("'", "")

    # Remove any remaining characters not alphanumeric or underscore
    sanitized = "".join(c if c.isalnum() or c == '_' else '' for c in sanitized)
    
    c_keywords = {
        "auto", "break", "case", "char", "const", "continue", "default", "do",
        "double", "else", "enum", "extern", "float", "for", "goto", "if",
        "int", "long", "register", "return", "short", "signed", "sizeof", "static",
        "struct", "switch", "typedef", "union", "unsigned", "void", "volatile", "while",
        # Add C++ keywords if targeting C++ specifically and they differ significantly in this context
        "class", "public", "private", "protected", "new", "delete", "this", "try", "catch", "throw",
        "namespace", "template", "typename", "virtual", "explicit", "operator" 
    }
    if sanitized in c_keywords:
        sanitized = f"fsm_{sanitized}" # Prefix to avoid keyword clash

    if not sanitized: 
         return f"{prefix_if_digit}SanitizedEmpty"
    if sanitized and sanitized[0].isdigit(): # Check if sanitized is not empty before indexing
        sanitized = prefix_if_digit + sanitized
    
    return sanitized

def parse_c_function_name_to_action_details(c_func_name_full: str) -> tuple[str | None, str | None, str | None, str | None]:
    name_part = c_func_name_full.replace("void ", "").replace("(void)", "").strip()

    if name_part.startswith("entry_action_"):
        return "entry_action", name_part.replace("entry_action_", ""), None, None
    elif name_part.startswith("during_action_"):
        return "during_action", name_part.replace("during_action_", ""), None, None
    elif name_part.startswith("exit_action_"):
        return "exit_action", name_part.replace("exit_action_", ""), None, None
    elif name_part.startswith("action_trans_"):
        remainder = name_part.replace("action_trans_", "")
        # Expecting Source_to_Target or Source_to_Target_EventName
        # Example: action_trans_StateA_to_StateB_eventX
        # A more robust separator like "__EVT__" between target and event would be better.
        # Current heuristic: find the last "_to_"
        parts = remainder.split("_to_")
        if len(parts) == 2:
            source_name_c_safe = parts[0]
            target_and_event_part = parts[1]
            
            # Heuristic to separate target from event:
            # Try to split by the last underscore, assuming event names are simpler.
            # This is still fragile if state names contain underscores that look like event separators.
            # A better approach is to use a well-defined unique separator during generation.
            
            last_underscore_idx = target_and_event_part.rfind('_')
            target_name_c_safe = target_and_event_part
            event_name_c_safe = None

            # If an underscore exists and it's not the first character (avoiding _event)
            # and it's not the last character (avoiding target_)
            if last_underscore_idx > 0 and last_underscore_idx < len(target_and_event_part) - 1:
                # Check if the part after the last underscore looks like a plausible event
                # This is a very rough check. A list of known (sanitized) event names would be better.
                potential_event = target_and_event_part[last_underscore_idx+1:]
                potential_target = target_and_event_part[:last_underscore_idx]
                
                # This heuristic is weak. Example: State_With_Underscore_to_Target_Event
                # Let's assume for now if one underscore, it's Target_Event.
                # If multiple underscores, the last segment is event.
                # This is a known limitation of parsing back from generated names without more metadata.
                
                # For now, a simpler split: if there's an underscore, assume last part is event
                # This is not perfect.
                target_event_split = target_and_event_part.split('_')
                if len(target_event_split) > 1:
                    event_name_c_safe = target_event_split[-1]
                    target_name_c_safe = "_".join(target_event_split[:-1])
                    if not target_name_c_safe: # case like _to_EventName (unlikely to be generated)
                        target_name_c_safe = event_name_c_safe # assume it was target
                        event_name_c_safe = None
                else: # Only one part, must be target
                    target_name_c_safe = target_event_split[0]
                    event_name_c_safe = None
            else: # No underscore or at ends, assume it's all target name
                target_name_c_safe = target_and_event_part
                event_name_c_safe = None


            return "action", source_name_c_safe, target_name_c_safe, event_name_c_safe
    
    logger.warning(f"Could not parse C function name: {c_func_name_full}")
    return None, None, None, None


def get_original_action_code(diagram_data: dict, 
                             action_type: str | None, 
                             c_safe_primary_name: str | None, 
                             c_safe_target_name_if_trans: str | None, 
                             c_safe_event_if_trans: str | None,
                             state_name_to_data_map: dict, 
                             transitions_list: list) -> str:
    if not action_type or not c_safe_primary_name:
        return ""

    original_primary_name = None
    for name, data in state_name_to_data_map.items():
        if sanitize_c_identifier(name) == c_safe_primary_name:
            original_primary_name = name
            break
    
    if action_type in ["entry_action", "during_action", "exit_action"]:
        if original_primary_name and original_primary_name in state_name_to_data_map:
            return state_name_to_data_map[original_primary_name].get(action_type, "")
        else:
            logger.warning(f"Could not find original state for C name '{c_safe_primary_name}' to get action '{action_type}'")

    elif action_type == "action": # Transition action
        if not original_primary_name: # Source state must be found
            logger.warning(f"Transition action lookup: Original source state for C name '{c_safe_primary_name}' not found.")
            return ""

        original_target_name = None
        if c_safe_target_name_if_trans:
            for name, data in state_name_to_data_map.items():
                if sanitize_c_identifier(name) == c_safe_target_name_if_trans:
                    original_target_name = name
                    break
        if not original_target_name:
            logger.warning(f"Transition action lookup: Original target state for C name '{c_safe_target_name_if_trans}' not found.")
            return ""

        for t_data in transitions_list:
            if t_data.get('source') == original_primary_name and \
               t_data.get('target') == original_target_name:
                current_trans_event_original = t_data.get('event', "")
                current_trans_event_c_safe = sanitize_c_identifier(current_trans_event_original)

                # Match if:
                # 1. C safe event from func name matches sanitized event from transition, OR
                # 2. C safe event from func name is None (meaning no event in func name) AND original transition event is also empty
                if (c_safe_event_if_trans and c_safe_event_if_trans == current_trans_event_c_safe) or \
                   (c_safe_event_if_trans is None and not current_trans_event_original):
                    return t_data.get('action', "")
        logger.warning(f"Could not find matching transition for {original_primary_name}->{original_target_name} (event: {c_safe_event_if_trans}) to get action.")
    return ""


def translate_action_to_c_stub_line(py_action_line: str) -> str:
    py_action_line = py_action_line.strip()
    if not py_action_line or py_action_line.startswith("#"):
        return f"    // {html.escape(py_action_line)}" if py_action_line.startswith("#") else ""

    # Pattern: variable = 1 or variable = True or variable = HIGH (case insensitive)
    m_set_high = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(1|True|HIGH)$", py_action_line, re.IGNORECASE)
    if m_set_high:
        var_name = sanitize_c_identifier(m_set_high.group(1))
        return f"    digitalWrite(PIN_FOR_{var_name.upper()}, HIGH); // TODO: Define PIN_FOR_{var_name.upper()} (e.g., #define PIN_FOR_{var_name.upper()} 13) and ensure {var_name} is conceptual."

    m_set_low = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(0|False|LOW)$", py_action_line, re.IGNORECASE)
    if m_set_low:
        var_name = sanitize_c_identifier(m_set_low.group(1))
        return f"    digitalWrite(PIN_FOR_{var_name.upper()}, LOW);  // TODO: Define PIN_FOR_{var_name.upper()} and ensure {var_name} is conceptual."

    m_set_value = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(\d+)$", py_action_line)
    if m_set_value:
        var_name = sanitize_c_identifier(m_set_value.group(1))
        value = m_set_value.group(2)
        return f"    {var_name} = {value}; // TODO: Ensure '{var_name}' is declared (e.g., static int {var_name};). Or map to hardware e.g. analogWrite(PIN_FOR_{var_name.upper()}, {value});"

    m_func_call_simple = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*\)$", py_action_line)
    if m_func_call_simple:
        func_name = sanitize_c_identifier(m_func_call_simple.group(1))
        return f"    {func_name}(); // TODO: Implement function {func_name}()"
    
    # Python print to C printf (very basic)
    m_print = re.match(r"print\s*\((.*)\)$", py_action_line)
    if m_print:
        inner_print = m_print.group(1).strip()
        # Handle simple f-strings like print(f"Value: {var}")
        m_fstring = re.match(r"f(['\"])(.*?)(\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\})(.*)\1", inner_print)
        if m_fstring:
            prefix = m_fstring.group(2)
            var_name = sanitize_c_identifier(m_fstring.group(4))
            suffix = m_fstring.group(5)
            # Assume int for simplicity, user must adjust format specifier
            return f'    printf("{html.escape(prefix)}%d{html.escape(suffix)}\\n", {var_name}); // TODO: Verify type & format specifier for {var_name}'
        elif inner_print.startswith("'") and inner_print.endswith("'") or \
             inner_print.startswith('"') and inner_print.endswith('"'):
            return f'    printf("%s\\n", {inner_print});' # Assumes string literal
        else: # Assumes it's a variable
            var_name = sanitize_c_identifier(inner_print)
            return f'    printf("Value of {var_name}: %d\\n", {var_name}); // TODO: Verify type & format specifier for {var_name}'


    # Default fallback with more explicit TODO
    return f"    // TODO: Manually translate this Python-like action: {html.escape(py_action_line)}"


def generate_c_code_files(diagram_data: dict, output_dir: str, base_filename: str) -> tuple[str, str]:
    states = diagram_data.get('states', [])
    transitions = diagram_data.get('transitions', [])

    if not states:
        raise ValueError("Cannot generate code: No states defined in the diagram.")

    base_filename_c = sanitize_c_identifier(base_filename, "fsm_")

    state_name_to_enum = {}
    state_name_to_data_map = {s_data['name']: s_data for s_data in states} 
    initial_state_c_name = None

    h_code = [f"#ifndef {base_filename_c.upper()}_H", f"#define {base_filename_c.upper()}_H\n"]
    h_code.append("typedef enum {")
    for i, state_data in enumerate(states):
        c_name = sanitize_c_identifier(state_data['name'])
        state_enum_name = f"STATE_{c_name.upper()}"
        state_name_to_enum[state_data['name']] = state_enum_name
        h_code.append(f"    {state_enum_name},")
        if state_data.get('is_initial', False) and not initial_state_c_name:
            initial_state_c_name = state_enum_name
    h_code.append("    FSM_NUM_STATES // Helper for array sizing or loop limits")
    h_code.append("} FSM_State_t;\n")

    if not initial_state_c_name and states:
        first_state_name = states[0]['name']
        initial_state_c_name = state_name_to_enum.get(first_state_name) 
        if initial_state_c_name:
            logger.warning(f"No initial state explicitly set. Defaulting to first state: {first_state_name} ({initial_state_c_name})")
        else: 
            logger.error("CRITICAL: Could not determine a default initial state enum value. FSM will likely not init correctly.")
            initial_state_c_name = "/* ERROR_NO_INITIAL_STATE_DEFINED */ (FSM_State_t)0" # Fallback to 0, but with comment

    unique_events = sorted(list(set(t['event'] for t in transitions if t.get('event'))))
    event_name_to_id = {}
    if unique_events:
        h_code.append("typedef enum {")
        for i, event_name_str in enumerate(unique_events):
            c_event_name = sanitize_c_identifier(event_name_str, "event_")
            event_id = f"EVENT_{c_event_name.upper()}"
            event_name_to_id[event_name_str] = event_id
            h_code.append(f"    {event_id},")
        h_code.append("    FSM_NUM_EVENTS // Helper for array sizing or loop limits")
        h_code.append("} FSM_Event_t;\n")
        h_code.append("#define FSM_NO_EVENT -1 // Special value for triggering 'during' actions or internal steps\n")
    else:
        h_code.append("// No events with names defined in transitions.\n")
        h_code.append("#define FSM_NO_EVENT -1\n") # Still define FSM_NO_EVENT

    h_code.append("// Function Prototypes for FSM")
    h_code.append(f"void {base_filename_c}_init(void);")
    h_code.append(f"void {base_filename_c}_run(int event_id); // Pass FSM_Event_t or FSM_NO_EVENT")
    h_code.append(f"FSM_State_t {base_filename_c}_get_current_state(void);\n")
    
    h_code.append("// User-defined Action Function Prototypes (implement these!)")
    action_prototypes_details = [] # Store (c_func_signature, original_py_code, type, name1, name2, event_orig)
    
    for state_data in states:
        original_state_name = state_data['name']
        c_safe_state_name = sanitize_c_identifier(original_state_name)
        for action_type_key in ['entry_action', 'during_action', 'exit_action']:
            py_action_code = state_data.get(action_type_key, "").strip()
            if py_action_code: 
                c_func_name = sanitize_c_identifier(f"{action_type_key}_{c_safe_state_name}")
                action_prototypes_details.append(
                    (f"void {c_func_name}(void);", py_action_code, action_type_key, original_state_name, None, None)
                )
    for trans_data in transitions:
        py_action_code = trans_data.get('action', "").strip()
        if py_action_code:
            c_safe_source_name = sanitize_c_identifier(trans_data['source'])
            c_safe_target_name = sanitize_c_identifier(trans_data['target'])
            original_event_name = trans_data.get('event','')
            c_safe_event_suffix = sanitize_c_identifier(original_event_name)
            
            func_name_base = f"action_trans_{c_safe_source_name}_to_{c_safe_target_name}"
            if c_safe_event_suffix: func_name_base += f"_{c_safe_event_suffix}"
            c_func_name = sanitize_c_identifier(func_name_base) # Sanitize the whole thing again
            action_prototypes_details.append(
                (f"void {c_func_name}(void);", py_action_code, "action", trans_data['source'], trans_data['target'], original_event_name)
            )

    # Ensure unique prototypes and sort them for consistent order in .h
    unique_proto_signatures = sorted(list(set(details[0] for details in action_prototypes_details)))
    for sig in unique_proto_signatures:
        h_code.append(sig)
    h_code.append("\n#endif // " + f"{base_filename_c.upper()}_H")

    c_code = [f'#include "{base_filename_c}.h"', "#include <stdio.h> // For basic printf in stubs\n"]
    c_code.append("static FSM_State_t current_fsm_state;\n")
    c_code.append("// --- FSM Global Variables (if any, declare them here) ---")
    c_code.append("// Example: static int my_fsm_counter = 0;\n")

    c_code.append(f"void {base_filename_c}_init(void) {{")
    if initial_state_c_name and "ERROR" not in initial_state_c_name:
        c_code.append(f"    current_fsm_state = {initial_state_c_name};")
        initial_state_orig_name = next((s['name'] for s_name_key,s_enum_val in state_name_to_enum.items() for s in states if s['name'] == s_name_key and s_enum_val == initial_state_c_name ), None)
        if initial_state_orig_name:
            entry_action_code = state_name_to_data_map.get(initial_state_orig_name, {}).get('entry_action')
            if entry_action_code:
                c_safe_state_name = sanitize_c_identifier(initial_state_orig_name)
                func_name = sanitize_c_identifier(f"entry_action_{c_safe_state_name}")
                c_code.append(f"    {func_name}(); // Call entry action for initial state")
    else:
        c_code.append("    // FATAL ERROR: No initial state was properly defined for the FSM!")
        c_code.append("    // current_fsm_state = (FSM_State_t)0; // Or some other default/error state")
    c_code.append("}\n")

    c_code.append(f"FSM_State_t {base_filename_c}_get_current_state(void) {{")
    c_code.append("    return current_fsm_state;")
    c_code.append("}\n")

    c_code.append(f"void {base_filename_c}_run(int event_id) {{")
    c_code.append("    FSM_State_t previous_state = current_fsm_state;")
    c_code.append("    FSM_State_t next_state = current_fsm_state; // Assume no transition initially")
    c_code.append("    int transition_taken = 0;\n")
    c_code.append("    // Note: FSM_NO_EVENT is defined as -1 in the header\n")
    c_code.append("    switch (current_fsm_state) {")

    for state_data in states:
        original_state_name = state_data['name']
        c_safe_state_name = sanitize_c_identifier(original_state_name)
        state_enum_val = state_name_to_enum.get(original_state_name, "/*UNKNOWN_STATE_ENUM*/")
        c_code.append(f"        case {state_enum_val}: {{")
        
        during_action_code = state_data.get('during_action')
        if during_action_code:
            func_name = sanitize_c_identifier(f"during_action_{c_safe_state_name}")
            c_code.append(f"            if (event_id == FSM_NO_EVENT) {{ // Process 'during' action if no specific event")
            c_code.append(f"                {func_name}();")
            c_code.append( "            }")
        
        # Transitions from this state
        first_trans_for_state_event_block = True
        for trans_data in transitions:
            if trans_data['source'] == original_state_name:
                event_name_str = trans_data.get('event')
                c_safe_target_name = sanitize_c_identifier(trans_data['target'])
                target_state_enum_val = state_name_to_enum.get(trans_data['target'], "/*UNKNOWN_TARGET_ENUM*/")
                condition_str = trans_data.get('condition',"").strip()
                
                if_keyword = "if" if first_trans_for_state_event_block else "else if"
                
                event_check = "event_id != FSM_NO_EVENT" # Base check that an event IS being processed
                if event_name_str and event_name_str in event_name_to_id:
                    event_check += f" && (event_id == {event_name_to_id[event_name_str]})"
                    first_trans_for_state_event_block = False # Next one for same state needs else if
                elif event_name_str: 
                    c_code.append(f"            /* Transition with event '{html.escape(event_name_str)}' to {html.escape(trans_data['target'])} skipped - event not in enum. */")
                    continue # Skip this transition if event name is bad
                elif not event_name_str: # Eventless transition
                    # Eventless transitions are typically evaluated if no specific event matches or on internal steps.
                    # Current logic: only if FSM_NO_EVENT. This might need adjustment based on desired FSM semantics
                    # for eventless transitions when other events are present.
                    event_check = "(event_id == FSM_NO_EVENT)"
                    if not first_trans_for_state_event_block: if_keyword = "else if"
                    else: if_keyword = "if"
                    first_trans_for_state_event_block = False


                condition_check = f"({condition_str})" if condition_str else "(1)"

                c_code.append(f"            {if_keyword} ({event_check} && {condition_check}) {{")
                
                exit_action_code = state_data.get('exit_action')
                if exit_action_code:
                    func_name = sanitize_c_identifier(f"exit_action_{c_safe_state_name}")
                    c_code.append(f"                {func_name}();")

                trans_py_action_code = trans_data.get('action')
                if trans_py_action_code:
                    c_safe_event_suffix = sanitize_c_identifier(trans_data.get('event',''))
                    func_name_base = f"action_trans_{c_safe_state_name}_to_{c_safe_target_name}"
                    if c_safe_event_suffix: func_name_base += f"_{c_safe_event_suffix}"
                    c_func_name = sanitize_c_identifier(func_name_base)
                    c_code.append(f"                {c_func_name}();")
                
                c_code.append(f"                next_state = {target_state_enum_val};")
                c_code.append(f"                transition_taken = 1;")
                c_code.append("            }")
            
        c_code.append("            break;") 
        c_code.append("        }") 
            
    c_code.append("        default:")
    c_code.append("            // Should not happen: Unhandled current_fsm_state")
    c_code.append("            break;")
    c_code.append("    } // end switch (current_fsm_state)\n")

    c_code.append("    if (transition_taken && next_state != previous_state) {")
    c_code.append("        // Call entry action for the new state (if it changed)")
    c_code.append("        current_fsm_state = next_state; // Update current_fsm_state *before* calling entry action of new state")
    c_code.append("        switch (next_state) {")
    for s_data_entry in states:
        s_enum_entry = state_name_to_enum.get(s_data_entry['name'], "/*UNKNOWN_STATE_ENUM_FOR_ENTRY*/")
        entry_py_code = s_data_entry.get('entry_action')
        if entry_py_code:
            c_safe_entry_state_name = sanitize_c_identifier(s_data_entry['name'])
            entry_func_name = sanitize_c_identifier(f"entry_action_{c_safe_entry_state_name}")
            c_code.append(f"            case {s_enum_entry}: {entry_func_name}(); break;")
    c_code.append("            default: /* No entry action for this state or unknown */ break;")
    c_code.append("        }")
    c_code.append("    } else if (!transition_taken) {")
    c_code.append("        current_fsm_state = next_state; // No transition, state remains same (next_state was init to current_fsm_state)")
    c_code.append("    }\n")
    
    # Moved this line up: current_fsm_state = next_state;
    c_code.append("}\n") 

    c_code.append("\n// --- User-Defined Action Function Implementations (STUBS) ---")
    c_code.append("// --- Please fill these in with your custom logic ---")
    
    processed_c_func_names = set()
    for c_func_signature, original_py_code, action_type_orig, name1_orig, name2_orig, event_orig in sorted(list(action_prototypes_details), key=lambda x: x[0]):
        c_func_name_only = c_func_signature.replace("void ", "").replace("(void);", "").strip()
        if c_func_name_only in processed_c_func_names: continue # Avoid duplicate stubs if names clash after sanitization
        processed_c_func_names.add(c_func_name_only)

        c_code.append(f"{c_func_signature[:-1]} {{ // Original action source: {action_type_orig} for {name1_orig}" + 
                      (f" to {name2_orig} on {event_orig}" if name2_orig and event_orig else (f" to {name2_orig}" if name2_orig else (f" on {event_orig}" if event_orig else ""))) + # Nicer formatting
                      f". Python: {original_py_code.replace(chr(10), ' ')[:50]}" + ("..." if len(original_py_code)>50 else "") +"")
        if original_py_code:
            py_action_lines = original_py_code.split('\n')
            for line in py_action_lines:
                line = line.strip()
                if line : # Process non-empty lines
                    translated_c_line = translate_action_to_c_stub_line(line)
                    if translated_c_line.strip() and not translated_c_line.strip().startswith("// "): # Add if translation produced something not just a comment
                         c_code.append(translated_c_line)
                    elif line.startswith("#"): # Keep python comments as C comments
                        c_code.append(f"    // {html.escape(line)}")
        else:
            c_code.append(f"    // No action defined for {c_func_name_only}")
        c_code.append(f"    // Example: printf(\"Action stub: {c_func_name_only} called\\n\");")
        c_code.append("}\n")

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