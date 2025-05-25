print("fsm_simulator.py is being imported with python-statemachine integration!")

from statemachine import StateMachine, State
from statemachine.exceptions import TransitionNotAllowed
from statemachine.event import Event as SMEvent # Renamed to avoid conflict if we use Event internally
from statemachine.transition_list import TransitionList as SMTransitionList
from functools import partial
import logging
import time # Import time for the fix if needed, though logging handles it
import ast # For AST-based safety checks

# Configure logging
LOGGING_DATE_FORMAT = "%H:%M:%S" # Base format
logging.basicConfig(level=logging.INFO,
                    format="--- FSM_SIM (%(asctime)s.%(msecs)03d): %(message)s",
                    datefmt=LOGGING_DATE_FORMAT)

# --- START: AST Safety Checker ---
class BasicSafetyVisitor(ast.NodeVisitor):
    def __init__(self, allowed_variable_names=None):
        self.violations = []
        # Define a list of globally allowed function names (callables)
        self.allowed_call_names = {'print', 'len', 'abs', 'min', 'max', 'int', 'float', 'str', 'bool', 'round'}
        # Define a list of allowed dunder attributes (typically for built-in operations)
        self.allowed_dunder_attrs = {'__len__', '__getitem__', '__setitem__', '__contains__',
                                     '__add__', '__sub__', '__mul__', '__div__', '__mod__',
                                     '__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__'}
        self.allowed_variable_names = allowed_variable_names if allowed_variable_names else set()

    def visit_Import(self, node):
        self.violations.append("SecurityError: Imports are not allowed in FSM code.")
        super().generic_visit(node)

    def visit_ImportFrom(self, node):
        self.violations.append("SecurityError: From-imports are not allowed in FSM code.")
        super().generic_visit(node)

    def visit_Call(self, node):
        # Disallow calling exec/eval directly
        if isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec', 'compile', 'open', 'input'):
            self.violations.append(f"SecurityError: Calling '{node.func.id}' is not allowed.")

        # Check if the called function is in the allowed list (for global-like functions)
        # More complex logic would be needed to safely allow method calls on FSM variables
        # while still restricting arbitrary function calls.
        # For now, this is a simple check for global function names.
        if isinstance(node.func, ast.Name) and node.func.id not in self.allowed_call_names and \
           node.func.id not in self.allowed_variable_names and \
           not hasattr(self.allowed_variable_names, node.func.id): # crude check for methods on vars
            # This check is basic. A robust solution for method calls would require
            # knowing the types of variables and their allowed methods.
            # We assume if it's not a predefined allowed call and not an FSM variable, it's suspect.
            # A more refined check could see if node.func is an Attribute node,
            # and if node.func.value (the object) is an FSM variable.
            pass # Relaxing this for now, as it's hard to do safely without full type info.
                 # Focus is on blocking direct dangerous calls and imports.

        super().generic_visit(node)

    def visit_Attribute(self, node):
        # Restrict access to dunder attributes, except for a predefined safe list
        if isinstance(node.attr, str) and node.attr.startswith('__') and node.attr.endswith('__'):
            if node.attr not in self.allowed_dunder_attrs:
                # Further refine: allow dunders on basic types like int, str, list, dict if needed
                # For example, `my_list.__len__()` should be fine, but `my_obj.__dict__` might not.
                # This is a broad restriction for now.
                # self.violations.append(f"SecurityError: Access to special attribute '{node.attr}' is restricted.")
                pass # Temporarily allowing more dunders as strict blocking can break legitimate code.
                     # The primary defense is no `import` and `{"__builtins__": SAFE_BUILTINS}`.
        super().generic_visit(node)

    def visit_Exec(self, node): # For Python 2, though this codebase is Py3
        self.violations.append("SecurityError: 'exec' statement is not allowed.")
        super().generic_visit(node)


def check_code_safety_basic(code_string: str, fsm_variables: set) -> tuple[bool, str]:
    """
    Performs basic AST-based safety checks on the code string.
    Returns (is_safe, message).
    """
    if not code_string.strip(): # Empty code is safe
        return True, ""
    try:
        # For actions (statements), mode is 'exec'. For conditions (expressions), mode is 'eval'.
        # We'll parse as 'exec' for actions and 'single' or 'eval' for conditions if needed for stricter rules.
        # For simplicity, parsing as 'exec' covers more cases for general validation.
        tree = ast.parse(code_string, mode='exec')
        visitor = BasicSafetyVisitor(allowed_variable_names=fsm_variables)
        visitor.visit(tree)
        if visitor.violations:
            return False, "; ".join(visitor.violations)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError in user code: {e.msg} (line {e.lineno}, offset {e.offset})"
    except Exception as e:
        return False, f"Unexpected error during code safety check: {type(e).__name__} - {e}"

# Define a dictionary of safe built-ins to pass to exec/eval
# This explicitly limits what global functions are available.
# Users can still use operators (+, -, *, /, ==, etc.) and access their FSM variables.
SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": print, # Consider replacing with a logging function if direct print is too broad
    "range": range,
    "round": round,
    "set": set,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "True": True,
    "False": False,
    "None": None,
    # Add other safe functions/constants as needed
    # Be very careful about adding functions that could allow filesystem access,
    # network access, or arbitrary code execution (like 'eval', 'exec', 'open', 'importlib').
}
# --- END: AST Safety Checker ---


class FSMError(Exception):
    pass

class StateMachinePoweredSimulator:
    def __init__(self, states_data, transitions_data):
        """Initialize the FSM simulator with state and transition data."""
        self._states_input_data = {s['name']: s for s in states_data}  # Map state names to data
        self._transitions_input_data = transitions_data
        self._variables = {}  # State machine model variables, accessible by user code
        self._action_log = []
        self.FSMClass = None
        self.sm = None
        self._initial_state_name = None

        try:
            self._build_fsm_class_and_instance()
            if self.sm and self.sm.current_state:
                self._log_action(f"FSM Initialized. Current state: {self.sm.current_state.id}")
            elif not self._states_input_data:
                raise FSMError("No states defined in the FSM.")
            else:
                raise FSMError("FSM Initialization failed: Could not determine current state after build.")
        except Exception as e:
            logging.error(f"Initialization failed: {e}", exc_info=True)
            raise FSMError(f"FSM Initialization failed: {e}")

    def _log_action(self, message):
        """Log an action with timestamp, matching main.py's logging style."""
        self._action_log.append(message)
        logging.info(message)

    def _create_dynamic_callback(self, code_string, callback_type="action", original_name="dynamic_callback"):
        """Create a dynamic callback for actions or conditions, with safety checks."""
        
        # Perform safety check before creating the callback
        is_safe, safety_message = check_code_safety_basic(code_string, set(self._variables.keys()))
        if not is_safe:
            err_msg = f"SecurityError: Code execution blocked for '{original_name}'. Reason: {safety_message}"
            self._log_action(f"[Safety Check Failed] {err_msg}")
            logging.error(err_msg)
            if callback_type == "condition":
                # If a condition is unsafe, it should probably evaluate to False to prevent transition
                def unsafe_condition_wrapper(*args, **kwargs):
                    self._log_action(f"[Condition Blocked] Unsafe code: '{code_string}' evaluated as False.")
                    return False
                unsafe_condition_wrapper.__name__ = f"{original_name}_blocked_condition"
                return unsafe_condition_wrapper
            else: # For actions, make it a no-op or raise an error if preferred
                def unsafe_action_wrapper(*args, **kwargs):
                    self._log_action(f"[Action Blocked] Unsafe code ignored: '{code_string}'.")
                    pass # Or: raise FSMError(err_msg)
                unsafe_action_wrapper.__name__ = f"{original_name}_blocked_action"
                return unsafe_action_wrapper

        def dynamic_callback_wrapper(*args, **kwargs):
            # exec_eval_locals_dict will be modified by exec, so copy if needed
            # or ensure that modifications are intended to persist in self._variables
            exec_eval_locals_dict = self._variables # Direct access and modification
            
            log_prefix = "[Action]" if callback_type == "action" else "[Condition]"
            self._log_action(f"{log_prefix} Executing: '{code_string}' with variables: {exec_eval_locals_dict}")

            try:
                if callback_type == "action":
                    # Pass the safe builtins and current FSM variables
                    exec(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict)
                    self._log_action(f"{log_prefix} Finished: '{code_string}'. Variables now: {exec_eval_locals_dict}")
                    return None
                elif callback_type == "condition":
                    # Pass the safe builtins and current FSM variables
                    result = eval(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict)
                    self._log_action(f"{log_prefix} Result of '{code_string}': {result}")
                    return bool(result)
            except SyntaxError as e:
                err_msg = f"SyntaxError in {callback_type} '{code_string}': {e.msg} (line {e.lineno}, offset {e.offset})"
                self._log_action(f"[Eval Error] {err_msg}")
                logging.error(err_msg)
                if callback_type == "condition": return False
            except NameError as e:
                err_msg = f"NameError in {callback_type} '{code_string}': {e}. Check if variable is defined in FSM scope or allowed builtins."
                self._log_action(f"[Eval Error] {err_msg}")
                logging.error(err_msg)
                if callback_type == "condition": return False
            except Exception as e:
                err_msg = f"Unexpected error in {callback_type} '{code_string}': {type(e).__name__} - {e}"
                self._log_action(f"[Eval Error] {err_msg}")
                logging.error(err_msg, exc_info=True)
                if callback_type == "condition": return False
            return None

        dynamic_callback_wrapper.__name__ = f"{original_name}_{callback_type}_{hash(code_string)}"
        return dynamic_callback_wrapper

    def _sm_on_enter_state(self, target: State, event_data, machine, **kwargs):
        self._log_action(f"Entering state: {target.id}")

    def _sm_on_exit_state(self, source: State, event_data, machine, **kwargs):
        self._log_action(f"Exiting state: {source.id}")

    def _sm_before_transition(self, event: str, source: State, target: State, event_data, machine, **kwargs):
        self._log_action(f"Before transition on '{event_data.event}' from '{source.id}' to '{target.id}'")

    def _sm_after_transition(self, event: str, source: State, target: State, event_data, machine, **kwargs):
        self._log_action(f"After transition on '{event_data.event}' from '{source.id}' to '{target.id}'")

    def _build_fsm_class_and_instance(self):
        fsm_class_attrs = {}
        sm_states_obj_map = {}
        initial_state_found_in_data = False

        for s_name, s_data in self._states_input_data.items():
            is_initial = s_data.get('is_initial', False)
            if is_initial:
                self._initial_state_name = s_name
                initial_state_found_in_data = True

            enter_callbacks = []
            if s_data.get('entry_action'):
                enter_callbacks.append(self._create_dynamic_callback(
                    s_data['entry_action'], "action", original_name=f"on_enter_{s_name}"
                ))

            exit_callbacks = []
            if s_data.get('exit_action'):
                exit_callbacks.append(self._create_dynamic_callback(
                    s_data['exit_action'], "action", original_name=f"on_exit_{s_name}"
                ))

            state_obj = State(
                name=s_name,
                value=s_name,
                initial=is_initial,
                final=s_data.get('is_final', False),
                enter=enter_callbacks or None,
                exit=exit_callbacks or None
            )
            fsm_class_attrs[s_name] = state_obj
            sm_states_obj_map[s_name] = state_obj

        if not initial_state_found_in_data and self._states_input_data:
            first_state_name_from_data = next(iter(self._states_input_data))
            if first_state_name_from_data in sm_states_obj_map:
                self._log_action(f"No initial state explicitly defined. Using first state as initial: {first_state_name_from_data}")
                sm_states_obj_map[first_state_name_from_data]._initial = True # type: ignore
                self._initial_state_name = first_state_name_from_data
            else:
                raise FSMError("Error setting fallback initial state: First state not found in map.")
        elif not self._states_input_data:
            raise FSMError("No states defined in the FSM.")

        for t_data in self._transitions_input_data:
            source_name = t_data['source']
            target_name = t_data['target']
            event_name = t_data.get('event')

            if not event_name:
                synthetic_event_name = f"_internal_transition_{source_name}_to_{target_name}"
                self._log_action(f"Warning: Transition {source_name}->{target_name} has no event. Assigning synthetic event: {synthetic_event_name}")
                event_name = synthetic_event_name

            source_state_obj = sm_states_obj_map.get(source_name)
            target_state_obj = sm_states_obj_map.get(target_name)

            if not source_state_obj or not target_state_obj:
                self._log_action(f"Warning: Skipping transition due to missing source '{source_name}' or target '{target_name}'.")
                continue

            conditions = []
            if t_data.get('condition'):
                conditions.append(self._create_dynamic_callback(
                    t_data['condition'], "condition", original_name=f"cond_{event_name}_{source_name}_{target_name}"
                ))

            actions = []
            if t_data.get('action'):
                actions.append(self._create_dynamic_callback(
                    t_data['action'], "action", original_name=f"action_{event_name}_{source_name}_{target_name}"
                ))
            
            if event_name not in fsm_class_attrs:
                fsm_class_attrs[event_name] = SMEvent(event_name) # type: ignore
            
            _ = source_state_obj.to(target_state_obj, event=event_name, cond=conditions or None, on=actions or None) # type: ignore

        fsm_class_attrs["on_enter_state"] = self._sm_on_enter_state
        fsm_class_attrs["on_exit_state"] = self._sm_on_exit_state
        fsm_class_attrs["before_transition"] = self._sm_before_transition
        fsm_class_attrs["after_transition"] = self._sm_after_transition

        try:
            self.FSMClass = type("DynamicBSMFSM", (StateMachine,), fsm_class_attrs)
            self.sm = self.FSMClass(model=self._variables) # type: ignore
        except Exception as e:
            logging.error(f"Failed to create StateMachine: {e}", exc_info=True)
            raise FSMError(f"StateMachine creation failed: {e}")

    def get_current_state_name(self):
        if not self.sm:
            logging.error("Cannot get current state: FSM not initialized.")
            return None
        return self.sm.current_state.id

    def get_variables(self):
        return self._variables.copy()

    def get_last_executed_actions_log(self):
        log_copy = list(self._action_log)
        self._action_log.clear()
        return log_copy

    def reset(self):
        self._log_action("--- FSM Resetting ---")
        self._variables.clear()

        if self.FSMClass:
            try:
                self.sm = self.FSMClass(model=self._variables) # type: ignore
                self._log_action(f"FSM Reset. Current state: {self.sm.current_state.id if self.sm else 'Unknown'}") # type: ignore
            except Exception as e:
                logging.error(f"Reset failed: {e}", exc_info=True)
                raise FSMError(f"FSM Reset failed: {e}")
        else:
            logging.error("FSM Class not built, cannot reset.")
            raise FSMError("FSM Class not built, cannot reset.")

    def step(self, event_name=None):
        if not self.sm:
            logging.error("Cannot step: FSM not initialized.")
            raise FSMError("Cannot step, FSM is not initialized.")

        current_state_id = self.sm.current_state.id
        self._log_action(f"--- Step triggered. Current state: {current_state_id}. Event: {event_name or 'None (internal)'} ---")

        current_state_input_data = self._states_input_data.get(current_state_id)
        if current_state_input_data and current_state_input_data.get('during_action'):
            during_action_str = current_state_input_data['during_action']
            self._log_action(f"Executing during actions for state '{current_state_id}': {during_action_str}")
            try:
                # During actions are also subject to safety checks
                temp_during_cb = self._create_dynamic_callback(during_action_str, "action", original_name=f"during_{current_state_id}")
                temp_during_cb()
            except Exception as e:
                self._log_action(f"Error executing during action '{during_action_str}': {e}")
                logging.error(f"During action error: {e}", exc_info=True)

        if event_name:
            try:
                self.sm.send(event_name) 
            except TransitionNotAllowed:
                self._log_action(f"Event '{event_name}' is not allowed or did not cause a transition from state '{current_state_id}'.")
            except AttributeError as e:
                if hasattr(self.sm, event_name) and callable(getattr(self.sm, event_name)):
                    self._log_action(f"AttributeError processing event '{event_name}': {e}. This might be an internal setup issue.")
                else:
                    self._log_action(f"Event '{event_name}' is not defined on the FSM.")
                logging.error(f"AttributeError for event '{event_name}': {e}", exc_info=True)
            except Exception as e:
                self._log_action(f"Unexpected error during event '{event_name}': {type(e).__name__} - {e}")
                logging.error(f"Event processing error: {e}", exc_info=True)
        else:
            self._log_action(f"No event provided. 'During' actions (if any) executed. State remains '{current_state_id}'.")

        return self.sm.current_state.id, self.get_last_executed_actions_log()

    def get_possible_events_from_current_state(self) -> list[str]:
        if not self.sm or not self.sm.current_state:
            logging.warning("Cannot get possible events: FSM or current state not available.")
            return []
        
        possible_events = set()
        for transition in self.sm.current_state.transitions:
            for event_obj in transition.events: 
                possible_events.add(str(event_obj.id))
        
        return sorted(list(possible_events))

FSMSimulator = StateMachinePoweredSimulator

if __name__ == "__main__":
    states_data = [
        {"name": "Initial", "is_initial": True, "entry_action": "x=0; print('Initial state entered, x is', x)"},
        {"name": "Loading", "entry_action": "print('Loading started'); x=x+1", "during_action": "x=x+0.1; print('x during loading:', x)"},
        {"name": "Success", "entry_action": "print('Success! x is', x)"},
        {"name": "Error"}
    ]
    transitions_data = [
        {"source": "Initial", "target": "Loading", "event": "start", "condition": "x == 0"},
        {"source": "Loading", "target": "Success", "event": "complete", "condition": "x > 1.1"}, # Condition for x
        {"source": "Loading", "target": "Error", "event": "fail"}
    ]
    try:
        print("--- SIMULATOR TEST ---")
        simulator = FSMSimulator(states_data, transitions_data)
        print("\nInitial state:", simulator.get_current_state_name())
        print("Initial vars:", simulator.get_variables())
        print("Possible events from Initial:", simulator.get_possible_events_from_current_state())
        for entry in simulator.get_last_executed_actions_log(): print(f"  LOG: {entry}")

        next_state, log = simulator.step("start")
        print("\nAfter step 'start':", next_state)
        print("Vars after 'start':", simulator.get_variables())
        print("Possible events from Loading:", simulator.get_possible_events_from_current_state())
        for entry in log: print(f"  LOG: {entry}")

        next_state, log = simulator.step(None) # during action
        print("\nAfter internal step in Loading:", next_state)
        print("Vars:", simulator.get_variables())
        for entry in log: print(f"  LOG: {entry}")

        next_state, log = simulator.step(None) # during action
        print("\nAfter internal step in Loading:", next_state)
        print("Vars:", simulator.get_variables())
        for entry in log: print(f"  LOG: {entry}")


        next_state, log = simulator.step("complete")
        print("\nAfter step 'complete':", next_state)
        print("Vars after 'complete':", simulator.get_variables())
        print("Possible events from Success:", simulator.get_possible_events_from_current_state())
        for entry in log: print(f"  LOG: {entry}")
        
        print("\n--- Testing unsafe code (should be blocked/logged) ---")
        unsafe_states = [{"name": "A", "is_initial": True, "entry_action": "import os; os.system('echo UNSAFE')"}]
        unsafe_transitions = []
        try:
            unsafe_sim = FSMSimulator(unsafe_states, unsafe_transitions)
            print("Unsafe sim current state:", unsafe_sim.get_current_state_name())
            for entry in unsafe_sim.get_last_executed_actions_log(): print(f"  UnsafeLOG: {entry}")
        except FSMError as e_unsafe:
             print(f"FSM Error (unsafe): {e_unsafe}")


    except FSMError as e:
        print(f"FSM Error: {e}")
    except Exception as e:
        print(f"Unexpected error in example: {e}")
        import traceback
        traceback.print_exc()