# bsm_designer_project/fsm_simulator.py

print("fsm_simulator.py is being imported with python-statemachine integration AND HIERARCHY AWARENESS + Enhanced Security!")

from statemachine import StateMachine, State
from statemachine.exceptions import TransitionNotAllowed
# ... (other imports from fsm_simulator.py remain the same)
import logging
import ast

logger = logging.getLogger(__name__)
# ... (logger setup from previous version remains the same) ...

# --- START: Enhanced AST Safety Checker ---
class BasicSafetyVisitor(ast.NodeVisitor):
    def __init__(self, allowed_variable_names=None):
        super().__init__()
        self.violations = []
        # Allowed global-like function calls
        self.allowed_call_names = {
            'print', 'len', 'abs', 'min', 'max', 'int', 'float', 'str', 'bool', 'round',
            'list', 'dict', 'set', 'tuple', 'range', 'sorted', 'sum', 'all', 'any',
            'isinstance', 'hasattr', # Useful for type checking within conditions/actions
            # Consider adding math functions if needed, e.g., 'math.sqrt' would need 'math' in SAFE_BUILTINS
            # and a way to allow specific module attribute access. For now, keep it simple.
        }
        # Allowed dunder attributes (mostly for built-in operations or safe introspection)
        self.allowed_dunder_attrs = {
            '__len__', '__getitem__', '__setitem__', '__delitem__', '__contains__',
            '__add__', '__sub__', '__mul__', '__truediv__', '__floordiv__', '__mod__', '__pow__',
            '__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__',
            '__iter__', '__next__', '__call__', # Allow calling callables stored in variables
            '__str__', '__repr__', # For debugging/printing
            '__bool__', # For truthiness testing
            '__hash__', # For dictionary keys/set elements
            '__abs__', # For abs()
            # Be cautious adding more.
        }
        # More comprehensive list of dangerous dunders and attributes to block
        self.dangerous_attributes = {
            # Dunders for object internals and metaprogramming
            '__globals__', '__builtins__', '__code__', '__closure__', '__self__',
            '__class__', '__bases__', '__subclasses__', '__mro__',
            '__init__', '__new__', '__del__', '__dict__',
            '__getattribute__', '__setattr__', '__delattr__',
            '__get__', '__set__', '__delete__', # Descriptors
            '__init_subclass__', '__prepare__',
            # Frame attributes (if somehow accessed)
            'f_locals', 'f_globals', 'f_builtins', 'f_code', 'f_back', 'f_trace',
            'gi_frame', 'gi_code', 'gi_running', 'gi_yieldfrom',
            'co_code', 'co_consts', 'co_names', 'co_varnames', 'co_freevars', 'co_cellvars',
            # Function attributes that could be risky to modify/access directly
            'func_code', 'func_globals', 'func_builtins', 'func_closure', 'func_defaults',
            # Module attributes
            '__file__', '__cached__', '__loader__', '__package__', '__spec__',
            # ctypes/internal system access
            '_as_parameter_', '_fields_', '_length_', '_type_',
            # Other potentially problematic ones
            '__annotations__', '__qualname__', '__module__', # Less dangerous, but restrict for tidiness
            '__doc__', # Usually fine, but can be large. Keep allowed for now, or add to allowed_dunders if needed.
            '__slots__',
            '__weakref__',
            '__set_name__',
            # Specific methods that might bypass other checks
            'format_map', # Can access arbitrary attributes via a mapping
            'mro', # Method resolution order (use __mro__ instead for blocking)
            'with_traceback', # Exception manipulation
        }
        # Combine with allowed_dunder_attrs for checking
        self.truly_dangerous_attributes = self.dangerous_attributes - self.allowed_dunder_attrs

        self.allowed_variable_names = allowed_variable_names if allowed_variable_names else set()

    def visit_Import(self, node):
        self.violations.append("SecurityError: Imports (import) are not allowed in FSM code.")
        super().generic_visit(node)

    def visit_ImportFrom(self, node):
        self.violations.append("SecurityError: From-imports (from ... import) are not allowed in FSM code.")
        super().generic_visit(node)

    def visit_Call(self, node):
        # Disallow direct calls to known dangerous built-in functions or disallowed names
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ('eval', 'exec', 'compile', 'open', 'input',
                             'getattr', 'setattr', 'delattr', # These are powerful; prefer direct access
                             'globals', 'locals', 'vars', # Prevent access to symbol tables
                             '__import__', # Explicitly block the import function
                             'memoryview', 'bytearray', 'bytes' # Can be used for memory manipulation
                             ):
                self.violations.append(f"SecurityError: Calling the function '{func_name}' is not allowed.")
            elif func_name not in self.allowed_call_names and \
                 func_name not in self.allowed_variable_names and \
                 func_name not in SAFE_BUILTINS: # Check against SAFE_BUILTINS as well
                # This is a heuristic: if it's not an allowed global, not an FSM var, and not a safe builtin, it's suspect.
                # It might be a method call on an FSM variable (e.g. my_list.append()), which is handled by visit_Attribute for the 'append'.
                # Or it could be an attempt to call something defined outside the restricted scope.
                # A more robust check would involve type analysis, which is beyond simple AST.
                # For now, if it's an ast.Name and not recognized, flag it.
                # Consider if user-defined functions in _variables should be callable.
                # If func_name refers to a callable stored in self._variables, it should be fine,
                # as long as that callable itself is safe.
                # The check `func_name not in self.allowed_variable_names` covers this: if it's a var, it's okay to try to call it.
                pass


        # Check for calls on attributes that might be dangerous, e.g., some_object.system('ls')
        # This is harder. The primary defense is blocking `import os` and controlling `self._variables`.
        super().generic_visit(node)

    def visit_Attribute(self, node):
        # Check for access to dangerous attributes
        if isinstance(node.attr, str):
            if node.attr in self.truly_dangerous_attributes:
                self.violations.append(f"SecurityError: Access to the attribute '{node.attr}' is restricted.")
            # Also check for dunder attributes not explicitly allowed
            elif node.attr.startswith('__') and node.attr.endswith('__') and node.attr not in self.allowed_dunder_attrs:
                self.violations.append(f"SecurityError: Access to the special attribute '{node.attr}' is restricted.")
        super().generic_visit(node)

    def visit_Exec(self, node): # Python 2, but good to keep for completeness
        self.violations.append("SecurityError: The 'exec' statement is not allowed.")
        super().generic_visit(node)

    def visit_While(self, node): # Example of limiting statement types (can be too restrictive)
        # Simple check for `while True:` without an obvious break. This is heuristic.
        # A more robust check would involve control flow analysis.
        # For now, this is commented out as it might block legitimate loops.
        # if isinstance(node.test, (ast.Constant, ast.NameConstant)) and node.test.value is True:
        #     has_break = any(isinstance(n, ast.Break) for n in ast.walk(node))
        #     if not has_break:
        #         self.violations.append("SecurityError: 'while True' loops without a 'break' are discouraged for safety.")
        super().generic_visit(node)

    # Could add visit_Delete, visit_Assign, visit_AugAssign for more fine-grained control if needed.
    # For example, prevent deletion or reassignment of specific FSM variables if they are meant to be read-only.

# check_code_safety_basic function remains largely the same, just uses the enhanced visitor.
def check_code_safety_basic(code_string: str, fsm_variables: set) -> tuple[bool, str]:
    if not code_string.strip():
        return True, ""
    try:
        tree = ast.parse(code_string, mode='exec') # Parse as a module/statements
        visitor = BasicSafetyVisitor(allowed_variable_names=fsm_variables)
        visitor.visit(tree)
        if visitor.violations:
            return False, "; ".join(visitor.violations)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError in user code: {e.msg} (line {e.lineno}, offset {e.offset})"
    except Exception as e: # Catch any other parsing related errors
        return False, f"Unexpected error during code safety check: {type(e).__name__} - {e}"

# SAFE_BUILTINS list remains the same as defined previously.
SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "float": float,
    "int": int, "len": len, "list": list, "max": max, "min": min, "print": print,
    "range": range, "round": round, "set": set, "str": str, "sum": sum, "tuple": tuple,
    "True": True, "False": False, "None": None,
    "isinstance": isinstance, "hasattr": hasattr, # Added these
}
# --- END: Enhanced AST Safety Checker ---


class FSMError(Exception):
    pass

class StateMachinePoweredSimulator: # Unchanged parts are omitted for brevity
    def __init__(self, states_data, transitions_data, parent_simulator=None, log_prefix=""):
        self._states_input_data = {s['name']: s for s in states_data}
        self._transitions_input_data = transitions_data
        self._variables = {}
        self._action_log = []
        self.FSMClass = None
        self.sm = None
        self._initial_state_name = None
        self.parent_simulator: StateMachinePoweredSimulator | None = parent_simulator
        self.log_prefix = log_prefix

        self.active_sub_simulator: StateMachinePoweredSimulator | None = None
        self.active_superstate_name: str | None = None

        try:
            self._build_fsm_class_and_instance()
            if self.sm and self.sm.current_state:
                self._log_action(f"FSM Initialized. Current state: {self.sm.current_state.id}")
            elif not self._states_input_data and not self.parent_simulator: # Only error if top-level and no states
                raise FSMError("No states defined in the FSM.")
            elif not self._states_input_data and self.parent_simulator: # Empty sub-FSM is okay
                self._log_action("Sub-FSM initialized but has no states (inactive).")
            elif not self.sm: # FSM class build failed but didn't raise specific error earlier
                 raise FSMError("FSM Initialization failed: StateMachine (sm) instance is None after build.")

        except Exception as e:
            logger.error(f"{self.log_prefix}Initialization failed: {e}", exc_info=True)
            raise FSMError(f"FSM Initialization failed: {e}")

    def _log_action(self, message, level_prefix_override=None):
        # ... (implementation from previous correct version, ensure it uses self.log_prefix)
        prefix_to_use = level_prefix_override if level_prefix_override is not None else self.log_prefix
        full_message = f"{prefix_to_use}{message}"
        self._action_log.append(full_message)
        logger.info(full_message)


    def _create_dynamic_callback(self, code_string, callback_type="action", original_name="dynamic_callback"):
        # Uses the enhanced check_code_safety_basic
        is_safe, safety_message = check_code_safety_basic(code_string, set(self._variables.keys()))
        if not is_safe:
            err_msg = f"SecurityError: Code execution blocked for '{original_name}'. Reason: {safety_message}"
            self._log_action(f"[Safety Check Failed] {err_msg}")
            # Return no-op or False-returning functions as before
            if callback_type == "condition":
                def unsafe_condition_wrapper(*args, **kwargs):
                    self._log_action(f"[Condition Blocked by Safety Check] Unsafe code: '{code_string}' evaluated as False.")
                    return False
                unsafe_condition_wrapper.__name__ = f"{original_name}_blocked_condition_safety"
                return unsafe_condition_wrapper
            else:
                def unsafe_action_wrapper(*args, **kwargs):
                    self._log_action(f"[Action Blocked by Safety Check] Unsafe code ignored: '{code_string}'.")
                unsafe_action_wrapper.__name__ = f"{original_name}_blocked_action_safety"
                return unsafe_action_wrapper

        # --- Start: Improved Error Handling within callback_wrapper ---
        def dynamic_callback_wrapper(*args, **kwargs):
            exec_eval_locals_dict = self._variables
            log_prefix_runtime = "[Action Runtime]" if callback_type == "action" else "[Condition Runtime]"
            current_state_for_log = self.sm.current_state.id if self.sm and self.sm.current_state else "UnknownState"
            
            self._log_action(f"{log_prefix_runtime} Executing: '{code_string}' in state '{current_state_for_log}' with variables: {exec_eval_locals_dict}")

            try:
                if callback_type == "action":
                    exec(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict)
                    self._log_action(f"{log_prefix_runtime} Finished: '{code_string}'. Variables now: {exec_eval_locals_dict}")
                    return None
                elif callback_type == "condition":
                    # For conditions, consider passing a copy if strict read-only is desired,
                    # though eval should primarily read.
                    # eval_locals = exec_eval_locals_dict.copy() # If strict immutability needed for conditions
                    result = eval(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict)
                    self._log_action(f"{log_prefix_runtime} Result of '{code_string}': {result}")
                    return bool(result)
            except SyntaxError as e:
                err_msg = (f"SyntaxError in {callback_type} '{original_name}' (state: {current_state_for_log}): "
                           f"{e.msg} (line {e.lineno}, offset {e.offset}). Code: '{code_string}'")
                self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{self.log_prefix}{err_msg}", exc_info=False) # No need for full exc_info, msg is detailed
                if callback_type == "condition": return False
            except NameError as e:
                err_msg = (f"NameError in {callback_type} '{original_name}' (state: {current_state_for_log}): "
                           f"{e}. Variable not defined or not in SAFE_BUILTINS? Code: '{code_string}'")
                self._log_action(f"[Code Error] {err_msg}")
                logger.warning(f"{self.log_prefix}{err_msg}") # Warning, as it's user code error
                if callback_type == "condition": return False
            except TypeError as e:
                err_msg = (f"TypeError in {callback_type} '{original_name}' (state: {current_state_for_log}): "
                           f"{e}. Code: '{code_string}'")
                self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{self.log_prefix}{err_msg}", exc_info=True)
                if callback_type == "condition": return False
            except AttributeError as e:
                err_msg = (f"AttributeError in {callback_type} '{original_name}' (state: {current_state_for_log}): "
                           f"{e}. Code: '{code_string}'")
                self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{self.log_prefix}{err_msg}", exc_info=True)
                if callback_type == "condition": return False
            # Add more specific exceptions as needed: IndexError, KeyError, ValueError, ZeroDivisionError
            except (IndexError, KeyError, ValueError, ZeroDivisionError) as e:
                err_msg = (f"{type(e).__name__} in {callback_type} '{original_name}' (state: {current_state_for_log}): "
                           f"{e}. Code: '{code_string}'")
                self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{self.log_prefix}{err_msg}", exc_info=True)
                if callback_type == "condition": return False
            except Exception as e: # Catch-all for other unexpected errors in user code
                err_msg = (f"Unexpected runtime error in {callback_type} '{original_name}' (state: {current_state_for_log}): "
                           f"{type(e).__name__} - {e}. Code: '{code_string}'")
                self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{self.log_prefix}{err_msg}", exc_info=True)
                if callback_type == "condition": return False
                # For actions, decide on behavior: halt simulation or just log and continue?
                # Current behavior: logs and returns None (action effectively fails silently beyond the log)
                # To halt, you might raise an FSMError here or set a flag.
            return None # Default return for actions if no error, or if error occurred and not a condition
        # --- End: Improved Error Handling ---

        dynamic_callback_wrapper.__name__ = f"{original_name}_{callback_type}_{hash(code_string)}"
        return dynamic_callback_wrapper

    # ... (Rest of the FSMSimulator methods: _master_on_enter_state, _master_on_exit_state,
    #      _sm_before_transition, _sm_after_transition, _build_fsm_class_and_instance,
    #      get_current_state_name, get_current_leaf_state_name, get_variables,
    #      get_last_executed_actions_log, reset, step, get_possible_events_from_current_state
    #      remain IDENTICAL to the previous "full updated codes of fsm_simulator.py" you received)
    # Re-paste them here if you need the full file again. For brevity, I'm omitting them.
    # For example, _master_on_enter_state:
    def _master_on_enter_state(self, target: State, event_data, machine, **kwargs):
        target_state_name = target.id
        self._log_action(f"Entering state: {target_state_name}")

        if target_state_name in self._states_input_data:
            state_def = self._states_input_data[target_state_name]
            if state_def.get('is_superstate', False):
                sub_fsm_data = state_def.get('sub_fsm_data')
                if sub_fsm_data and sub_fsm_data.get('states'):
                    self._log_action(f"Superstate '{target_state_name}' entered. Initializing its sub-machine.")
                    try:
                        self.active_sub_simulator = StateMachinePoweredSimulator(
                            sub_fsm_data['states'], sub_fsm_data['transitions'],
                            parent_simulator=self,
                            log_prefix=self.log_prefix + "  [SUB] "
                        )
                        self.active_superstate_name = target_state_name
                        for sub_log_entry in self.active_sub_simulator.get_last_executed_actions_log():
                            self._action_log.append(sub_log_entry)
                    except Exception as e:
                        self._log_action(f"ERROR initializing sub-machine for '{target_state_name}': {e}")
                        logger.error(f"{self.log_prefix}Sub-machine init error for '{target_state_name}':", exc_info=True)
                        self.active_sub_simulator = None
                        self.active_superstate_name = None
                else:
                    self._log_action(f"Superstate '{target_state_name}' has no defined sub-machine data.")

        entry_action_code = self._states_input_data.get(target_state_name, {}).get('entry_action')
        if entry_action_code:
            entry_action_cb = self._create_dynamic_callback(
                entry_action_code, "action", original_name=f"on_enter_{target_state_name}"
            )
            entry_action_cb()

    def _master_on_exit_state(self, source: State, event_data, machine, **kwargs):
        source_state_name = source.id
        self._log_action(f"Exiting state: {source_state_name}")

        exit_action_code = self._states_input_data.get(source_state_name, {}).get('exit_action')
        if exit_action_code:
            exit_action_cb = self._create_dynamic_callback(
                exit_action_code, "action", original_name=f"on_exit_{source_state_name}"
            )
            exit_action_cb()

        if self.active_sub_simulator and self.active_superstate_name == source_state_name:
            self._log_action(f"Superstate '{source_state_name}' exited. Terminating its sub-machine.")
            self.active_sub_simulator = None
            self.active_superstate_name = None

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
            
            state_obj = State(
                name=s_name, value=s_name, initial=is_initial, final=s_data.get('is_final', False)
            )
            fsm_class_attrs[s_name] = state_obj
            sm_states_obj_map[s_name] = state_obj

        if not initial_state_found_in_data and self._states_input_data:
            first_state_name_from_data = next(iter(self._states_input_data))
            if first_state_name_from_data in sm_states_obj_map:
                self._log_action(f"No initial state explicitly defined. Using first state '{first_state_name_from_data}' as initial.")
                sm_states_obj_map[first_state_name_from_data]._initial = True
                self._initial_state_name = first_state_name_from_data
            else:
                raise FSMError("Error setting fallback initial state: First state not found in map.")
        elif not self._states_input_data:
            if not self.parent_simulator:
                raise FSMError("No states defined in the FSM.")
            else:
                self._log_action("Sub-FSM has no states defined. It will be inactive.")
                return

        for t_data in self._transitions_input_data:
            source_name = t_data['source']
            target_name = t_data['target']
            event_name = t_data.get('event')

            if not event_name:
                synthetic_event_name = f"_internal_transition_{source_name}_to_{target_name}"
                self._log_action(f"Warning: Transition {source_name}->{target_name} has no event. Assigning synthetic: {synthetic_event_name}")
                event_name = synthetic_event_name

            source_state_obj = sm_states_obj_map.get(source_name)
            target_state_obj = sm_states_obj_map.get(target_name)

            if not source_state_obj or not target_state_obj:
                self._log_action(f"Warning: Skipping transition missing source '{source_name}' or target '{target_name}'.")
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
                fsm_class_attrs[event_name] = SMEvent(event_name)
            
            _ = source_state_obj.to(target_state_obj, event=event_name, cond=conditions or None, on=actions or None)

        fsm_class_attrs["on_enter_state"] = self._master_on_enter_state
        fsm_class_attrs["on_exit_state"] = self._master_on_exit_state
        fsm_class_attrs["before_transition"] = self._sm_before_transition
        fsm_class_attrs["after_transition"] = self._sm_after_transition

        try:
            self.FSMClass = type(f"DynamicBSMFSM_{self.log_prefix.replace(' ', '')}_{id(self)}", (StateMachine,), fsm_class_attrs)
            self.sm = self.FSMClass(model=self._variables)
        except Exception as e:
            logger.error(f"{self.log_prefix}Failed to create StateMachine class/instance: {e}", exc_info=True)
            raise FSMError(f"StateMachine creation failed: {e}")

    def get_current_state_name(self):
        if not self.sm:
            # logger.error(f"{self.log_prefix}Cannot get current state: FSM not initialized.") # Can be noisy for empty sub-FSMs
            return "Uninitialized" if not self.parent_simulator else "EmptySubFSM"
        current_state_name = self.sm.current_state.id
        if self.active_sub_simulator and self.active_sub_simulator.sm: # Check sub_sim has .sm
            sub_state_name = self.active_sub_simulator.get_current_state_name()
            return f"{current_state_name} ({sub_state_name})"
        return current_state_name
    
    def get_current_leaf_state_name(self):
        if self.active_sub_simulator and self.active_sub_simulator.sm :
            return self.active_sub_simulator.get_current_leaf_state_name()
        elif self.sm and self.sm.current_state:
            return self.sm.current_state.id
        return "UnknownLeaf"

    def get_variables(self):
        return self._variables.copy()

    def get_last_executed_actions_log(self):
        log_copy = list(self._action_log)
        self._action_log.clear()
        return log_copy

    def reset(self):
        self._log_action("--- FSM Resetting ---")
        self._variables.clear()

        if self.active_sub_simulator:
            self._log_action("Resetting active sub-machine...")
            self.active_sub_simulator.reset()
            for sub_log_entry in self.active_sub_simulator.get_last_executed_actions_log():
                 self._action_log.append(sub_log_entry)
            self.active_sub_simulator = None
            self.active_superstate_name = None

        if self.FSMClass:
            try:
                self.sm = self.FSMClass(model=self._variables)
                self._log_action(f"FSM Reset. Current state: {self.sm.current_state.id if self.sm and self.sm.current_state else 'Unknown'}")
            except Exception as e:
                logger.error(f"{self.log_prefix}Reset failed: {e}", exc_info=True)
                raise FSMError(f"FSM Reset failed: {e}")
        elif not self.parent_simulator and not self._states_input_data : # Only error if top-level and truly empty
            logger.error(f"{self.log_prefix}FSM Class not built (no states), cannot reset.")
            raise FSMError("FSM Class not built (no states), cannot reset.")
        elif self.parent_simulator and not self._states_input_data: # Empty sub-fsm, already logged
            pass


    def step(self, event_name=None):
        if not self.sm:
            if not self.parent_simulator and not self._states_input_data :
                 logger.error(f"{self.log_prefix}Cannot step: FSM not initialized (no states).")
                 raise FSMError("Cannot step, FSM is not initialized (no states).")
            elif self.parent_simulator and not self._states_input_data:
                self._log_action("Cannot step: Sub-FSM is empty/not defined.")
                return self.get_current_state_name(), self.get_last_executed_actions_log()
            else:
                 logger.error(f"{self.log_prefix}Cannot step: FSM.sm not initialized.")
                 raise FSMError("Cannot step, FSM.sm is not initialized.")

        current_main_state_id = self.sm.current_state.id
        self._log_action(f"--- Step triggered. Current state: {self.get_current_state_name()}. Event: {event_name or 'None (internal)'} ---")

        current_main_state_input_data = self._states_input_data.get(current_main_state_id)
        if current_main_state_input_data and current_main_state_input_data.get('during_action'):
            during_action_str = current_main_state_input_data['during_action']
            self._log_action(f"Executing 'during' action for state '{current_main_state_id}': {during_action_str}")
            try:
                temp_during_cb = self._create_dynamic_callback(during_action_str, "action", original_name=f"during_{current_main_state_id}")
                temp_during_cb()
            except Exception as e:
                self._log_action(f"Error executing 'during' action '{during_action_str}': {e}")
                logger.error(f"{self.log_prefix}During action error:", exc_info=True)

        if self.active_sub_simulator:
            superstate_for_log = self.active_superstate_name or current_main_state_id
            self._log_action(f"Processing internal step for active sub-machine in superstate '{superstate_for_log}'.")
            try:
                _, sub_log = self.active_sub_simulator.step(event_name=None)
                for sub_entry in sub_log:
                    self._action_log.append(sub_entry)

                sub_sm_obj = self.active_sub_simulator.sm
                if sub_sm_obj and sub_sm_obj.current_state and sub_sm_obj.current_state.final:
                    self._log_action(f"Sub-machine in '{superstate_for_log}' has reached a final state: '{sub_sm_obj.current_state.id}'.")
                    if self.active_superstate_name: # Ensure we have the name
                         self._variables[f"{self.active_superstate_name}_sub_completed"] = True
                         self._log_action(f"Variable '{self.active_superstate_name}_sub_completed' set to True in parent scope.")

            except Exception as e_sub:
                self._log_action(f"Error during sub-machine internal step: {e_sub}")
                logger.error(f"{self.log_prefix}Sub-machine step error:", exc_info=True)

        if event_name:
            try:
                self.sm.send(event_name)
            except TransitionNotAllowed:
                self._log_action(f"Event '{event_name}' is not allowed or did not cause a transition from state '{current_main_state_id}'.")
            except AttributeError as e:
                if hasattr(self.sm, event_name) and callable(getattr(self.sm, event_name)):
                    self._log_action(f"AttributeError processing event '{event_name}': {e}. This might be an internal setup issue.")
                else:
                    self._log_action(f"Event '{event_name}' is not defined on the FSM.")
                logger.error(f"{self.log_prefix}AttributeError for event '{event_name}':", exc_info=True)
            except Exception as e:
                self._log_action(f"Unexpected error during event '{event_name}': {type(e).__name__} - {e}")
                logger.error(f"{self.log_prefix}Event processing error:", exc_info=True)
        else:
            if not self.active_sub_simulator:
                 self._log_action(f"No event provided. 'During' actions (if any) executed. State remains '{current_main_state_id}'.")

        return self.get_current_state_name(), self.get_last_executed_actions_log()

    def get_possible_events_from_current_state(self) -> list[str]:
        if not self.sm or not self.sm.current_state:
            # logger.warning(f"{self.log_prefix}Cannot get possible events: FSM or current state not available.")
            return []
        
        possible_events = set()
        for transition in self.sm.current_state.transitions:
            for event_obj in transition.events: 
                possible_events.add(str(event_obj.id))
        
        return sorted(list(possible_events))

FSMSimulator = StateMachinePoweredSimulator

if __name__ == "__main__": # Unchanged from previous correct version
    main_states_data = [
        {"name": "Idle", "is_initial": True, "entry_action": "print('Main: Idle Entered'); idle_counter = 0"},
        {"name": "Processing", "is_superstate": True,
         "sub_fsm_data": {
             "states": [
                 {"name": "SubIdle", "is_initial": True, "entry_action": "print('Sub: SubIdle Entered'); sub_var = 10"},
                 {"name": "SubActive", "during_action": "sub_var = sub_var + 1; print('Sub: SubActive during, sub_var is', sub_var)"},
                 {"name": "SubDone", "is_final": True, "entry_action": "print('Sub: SubDone Entered (final)')"}
             ],
             "transitions": [
                 {"source": "SubIdle", "target": "SubActive", "event": "start_sub_work"},
                 {"source": "SubActive", "target": "SubDone", "event": "finish_sub_work", "condition": "sub_var > 11"}
             ],
             "comments": []
         },
         "entry_action": "print('Main: Processing Superstate Entered')",
         "during_action": "print('Main: Processing Superstate During'); idle_counter = idle_counter + 1",
         "exit_action": "print('Main: Processing Superstate Exited')"
        },
        {"name": "Done", "entry_action": "print('Main: Done Entered')"}
    ]
    main_transitions_data = [
        {"source": "Idle", "target": "Processing", "event": "start_processing"},
        # Transition from superstate based on sub-machine completion
        {"source": "Processing", "target": "Done", "event": "auto_finish", "condition": "Processing_sub_completed == True"}
    ]

    print("--- HIERARCHICAL SIMULATOR TEST (WITH ENHANCED SECURITY) ---")
    try:
        simulator = FSMSimulator(main_states_data, main_transitions_data)

        def print_status(sim, step_name=""):
            print(f"\n--- {step_name} ---")
            print(f"Current State: {sim.get_current_state_name()}")
            print(f"Leaf State: {sim.get_current_leaf_state_name()}")
            print(f"Main Vars: {sim.get_variables()}")
            if sim.active_sub_simulator:
                print(f"Sub Vars: {sim.active_sub_simulator.get_variables()}")
            log = sim.get_last_executed_actions_log()
            if log:
                print("Log:")
                for entry in log: print(f"  {entry}")
            print("--------------------")

        print_status(simulator, "INITIAL STATE")

        simulator.step("start_processing")
        print_status(simulator, "AFTER 'start_processing' (Entered Superstate)")

        if simulator.active_sub_simulator:
            print("\n>>> Manually triggering 'start_sub_work' on sub-machine <<<")
            simulator.active_sub_simulator.step("start_sub_work")
            print_status(simulator, "AFTER sub-event 'start_sub_work'")

        simulator.step(None) # Main during, Sub during (sub_var=11)
        print_status(simulator, "AFTER internal step 1")

        simulator.step(None) # Main during, Sub during (sub_var=12)
        print_status(simulator, "AFTER internal step 2")

        if simulator.active_sub_simulator: # sub_var is 12, condition sub_var > 11 met
            print("\n>>> Manually triggering 'finish_sub_work' on sub-machine <<<")
            simulator.active_sub_simulator.step("finish_sub_work") # Sub goes to SubDone (final)
            # This should set Processing_sub_completed = True in main FSM's _variables
            print_status(simulator, "AFTER sub-event 'finish_sub_work' (Sub should be Done)")

        # Now, an internal step on main FSM should evaluate the condition for "auto_finish"
        simulator.step("auto_finish") # Try to trigger the auto-finish based on sub-completion
        print_status(simulator, "AFTER 'auto_finish' (Main FSM should be Done)")


        print("\n--- Test Unsafe Code (should be blocked) ---")
        unsafe_states = [{"name": "A", "is_initial": True, "entry_action": "import os; os.system('echo UNSAFE')"}]
        unsafe_sim = FSMSimulator(unsafe_states, [])
        print_status(unsafe_sim, "Unsafe Sim Start")


    except FSMError as e:
        print(f"FSM Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()