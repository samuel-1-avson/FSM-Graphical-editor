# bsm_designer_project/fsm_simulator.py

print("fsm_simulator.py is being imported with python-statemachine integration, HIERARCHY AWARENESS, and Enhanced Security/Robustness!")

from statemachine import StateMachine, State
from statemachine.exceptions import TransitionNotAllowed, InvalidDefinition
from statemachine.event import Event as SMEvent


import logging
import ast # For AST-based safety checks

# Configure logging for this module
logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Avoid adding multiple handlers
    LOGGING_DATE_FORMAT = "%H:%M:%S"
    handler = logging.StreamHandler()
    formatter = logging.Formatter("--- FSM_SIM (%(asctime)s.%(msecs)03d): %(message)s", datefmt=LOGGING_DATE_FORMAT)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# --- START: Enhanced AST Safety Checker ---
class BasicSafetyVisitor(ast.NodeVisitor):
    def __init__(self, allowed_variable_names=None):
        super().__init__()
        self.violations = []
        self.allowed_call_names = {
            'print', 'len', 'abs', 'min', 'max', 'int', 'float', 'str', 'bool', 'round',
            'list', 'dict', 'set', 'tuple', 'range', 'sorted', 'sum', 'all', 'any',
            'isinstance', 'hasattr',
        }
        self.allowed_dunder_attrs = {
            '__len__', '__getitem__', '__setitem__', '__delitem__', '__contains__',
            '__add__', '__sub__', '__mul__', '__truediv__', '__floordiv__', '__mod__', '__pow__',
            '__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__',
            '__iter__', '__next__', '__call__',
            '__str__', '__repr__',
            '__bool__', '__hash__', '__abs__',
        }
        self.dangerous_attributes = {
            '__globals__', '__builtins__', '__code__', '__closure__', '__self__',
            '__class__', '__bases__', '__subclasses__', '__mro__',
            '__init__', '__new__', '__del__', '__dict__',
            '__getattribute__', '__setattr__', '__delattr__',
            '__get__', '__set__', '__delete__',
            '__init_subclass__', '__prepare__',
            'f_locals', 'f_globals', 'f_builtins', 'f_code', 'f_back', 'f_trace',
            'gi_frame', 'gi_code', 'gi_running', 'gi_yieldfrom',
            'co_code', 'co_consts', 'co_names', 'co_varnames', 'co_freevars', 'co_cellvars',
            'func_code', 'func_globals', 'func_builtins', 'func_closure', 'func_defaults',
            '__file__', '__cached__', '__loader__', '__package__', '__spec__',
            '_as_parameter_', '_fields_', '_length_', '_type_',
            '__annotations__', '__qualname__', '__module__',
            '__slots__', '__weakref__', '__set_name__',
            'format_map', 'mro', 'with_traceback',
        }
        self.truly_dangerous_attributes = self.dangerous_attributes - self.allowed_dunder_attrs
        self.allowed_variable_names = allowed_variable_names if allowed_variable_names else set()

    def visit_Import(self, node):
        self.violations.append("SecurityError: Imports (import) are not allowed in FSM code.")
        super().generic_visit(node)

    def visit_ImportFrom(self, node):
        self.violations.append("SecurityError: From-imports (from ... import) are not allowed in FSM code.")
        super().generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ('eval', 'exec', 'compile', 'open', 'input',
                             'getattr', 'setattr', 'delattr',
                             'globals', 'locals', 'vars',
                             '__import__',
                             'memoryview', 'bytearray', 'bytes'
                             ):
                self.violations.append(f"SecurityError: Calling the function '{func_name}' is not allowed.")
            elif func_name not in self.allowed_call_names and \
                 func_name not in self.allowed_variable_names and \
                 func_name not in SAFE_BUILTINS:
                # Allow calls to user-defined variables that might be functions stored in self._variables
                pass # Allow, assuming it's a variable that is callable
        super().generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.attr, str):
            if node.attr in self.truly_dangerous_attributes:
                self.violations.append(f"SecurityError: Access to the attribute '{node.attr}' is restricted.")
            elif node.attr.startswith('__') and node.attr.endswith('__') and node.attr not in self.allowed_dunder_attrs:
                self.violations.append(f"SecurityError: Access to the special attribute '{node.attr}' is restricted.")
        super().generic_visit(node)

    def visit_Exec(self, node): # For Python 2, though ast.parse might handle it in Py3 context
        self.violations.append("SecurityError: The 'exec' statement/function is not allowed.")
        super().generic_visit(node)

def check_code_safety_basic(code_string: str, fsm_variables: set) -> tuple[bool, str]:
    if not code_string.strip():
        return True, ""
    try:
        tree = ast.parse(code_string, mode='exec') # mode='exec' for statements
        visitor = BasicSafetyVisitor(allowed_variable_names=fsm_variables)
        visitor.visit(tree)
        if visitor.violations:
            return False, "; ".join(visitor.violations)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError in user code: {e.msg} (line {e.lineno}, offset {e.offset})"
    except Exception as e:
        return False, f"Unexpected error during code safety check: {type(e).__name__} - {e}"

SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "float": float,
    "int": int, "len": len, "list": list, "max": max, "min": min, "print": print,
    "range": range, "round": round, "set": set, "str": str, "sum": sum, "tuple": tuple,
    "True": True, "False": False, "None": None,
    "isinstance": isinstance, "hasattr": hasattr,
}
# --- END: Enhanced AST Safety Checker ---


class FSMError(Exception):
    pass

class StateMachinePoweredSimulator:
    def __init__(self, states_data, transitions_data, parent_simulator=None, log_prefix="", halt_on_action_error=False):
        self._states_input_data = {s['name']: s for s in states_data}
        self._transitions_input_data = transitions_data
        self._variables = {} # This will be the model for python-statemachine
        self._action_log = []
        self.FSMClass = None
        self.sm: StateMachine | None = None # Type hint for python-statemachine's StateMachine
        self._initial_state_name = None
        self.parent_simulator: StateMachinePoweredSimulator | None = parent_simulator
        self.log_prefix = log_prefix

        self.active_sub_simulator: StateMachinePoweredSimulator | None = None
        self.active_superstate_name: str | None = None
        self._halt_simulation_on_action_error = halt_on_action_error
        self.simulation_halted_flag = False

        try:
            self._build_fsm_class_and_instance()
            # Log initial state after successful build and SM instantiation
            if self.sm and self.sm.current_state:
                self._log_action(f"FSM Initialized. Current state: {self.sm.current_state.id}")
            elif not self._states_input_data and not self.parent_simulator:
                 # This case should ideally be caught by _build_fsm_class_and_instance
                 raise FSMError("No states defined in the FSM.")
            elif not self._states_input_data and self.parent_simulator:
                self._log_action("Sub-FSM initialized but has no states (inactive).")
            elif not self.sm and (self._states_input_data or self.parent_simulator):
                 raise FSMError("FSM Initialization failed: StateMachine (sm) instance is None after build.")

        except InvalidDefinition as e:
            logger.error(f"{self.log_prefix}FSM Definition Error during Initialization: {e}", exc_info=False)
            raise FSMError(f"FSM Definition Error: {e}")
        except FSMError: # Re-raise FSMError from _build_fsm_class_and_instance
            raise
        except Exception as e:
            logger.error(f"{self.log_prefix}Initialization failed: {e}", exc_info=True)
            raise FSMError(f"FSM Initialization failed: {e}")

    def _log_action(self, message, level_prefix_override=None):
        prefix_to_use = level_prefix_override if level_prefix_override is not None else self.log_prefix
        full_message = f"{prefix_to_use}{message}"
        self._action_log.append(full_message)
        logger.info(full_message)

    def _create_dynamic_callback(self, code_string, callback_type="action", original_name="dynamic_callback"):
        is_safe, safety_message = check_code_safety_basic(code_string, set(self._variables.keys()))
        if not is_safe:
            err_msg = f"SecurityError: Code execution blocked for '{original_name}'. Reason: {safety_message}"
            self._log_action(f"[Safety Check Failed] {err_msg}")
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

        def dynamic_callback_wrapper(*args, **kwargs):
            # The first argument should be the StateMachine instance
            sm_instance_arg = args[0] if args else self.sm
            exec_eval_locals_dict = sm_instance_arg.model if hasattr(sm_instance_arg, 'model') else self._variables
            log_prefix_runtime = "[Action Runtime]" if callback_type == "action" else "[Condition Runtime]"
            current_state_for_log = "UnknownState"
            if sm_instance_arg and hasattr(sm_instance_arg, 'current_state') and sm_instance_arg.current_state:
                 current_state_for_log = sm_instance_arg.current_state.id
            elif self.parent_simulator and self.parent_simulator.sm and self.parent_simulator.sm.current_state:
                 current_state_for_log = f"{self.parent_simulator.sm.current_state.id} -> {original_name.split('_')[-1] if '_' in original_name else original_name}"

            self._log_action(f"{log_prefix_runtime} Executing: '{code_string}' in state '{current_state_for_log}' for '{original_name}' with vars: {exec_eval_locals_dict}")

            try:
                if callback_type == "action":
                    exec(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict)
                    self._log_action(f"{log_prefix_runtime} Finished: '{code_string}'. Variables now: {exec_eval_locals_dict}")
                    return None
                elif callback_type == "condition":
                    result = eval(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict.copy())
                    self._log_action(f"{log_prefix_runtime} Result of '{code_string}': {result}")
                    return bool(result)
            except SyntaxError as e:
                err_msg = (f"SyntaxError in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{e.msg} (line {e.lineno}, offset {e.offset}). Code: '{code_string}'")
                self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{self.log_prefix}{err_msg}", exc_info=False)
                if callback_type == "condition": return False
                if self._halt_simulation_on_action_error and callback_type == "action": self.simulation_halted_flag = True; raise FSMError(err_msg)
            except NameError as e:
                err_msg = (f"NameError in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{e}. Variable not defined or not in SAFE_BUILTINS? Code: '{code_string}'")
                self._log_action(f"[Code Error] {err_msg}")
                logger.warning(f"{self.log_prefix}{err_msg}")
                if callback_type == "condition": return False
                if self._halt_simulation_on_action_error and callback_type == "action": self.simulation_halted_flag = True; raise FSMError(err_msg)
            except (TypeError, AttributeError, IndexError, KeyError, ValueError, ZeroDivisionError) as e:
                err_msg = (f"{type(e).__name__} in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{e}. Code: '{code_string}'")
                self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{self.log_prefix}{err_msg}", exc_info=True)
                if callback_type == "condition": return False
                if self._halt_simulation_on_action_error and callback_type == "action": self.simulation_halted_flag = True; raise FSMError(err_msg)
            except Exception as e:
                err_msg = (f"Unexpected runtime error in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{type(e).__name__} - {e}. Code: '{code_string}'")
                self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{self.log_prefix}{err_msg}", exc_info=True)
                if callback_type == "condition": return False
                if self._halt_simulation_on_action_error and callback_type == "action": self.simulation_halted_flag = True; raise FSMError(err_msg)
            return None
        dynamic_callback_wrapper.__name__ = f"{original_name}_{callback_type}_{hash(code_string)}"
        return dynamic_callback_wrapper

    def _master_on_enter_state(self, target, **kwargs):
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
                            log_prefix=self.log_prefix + "  [SUB] ",
                            halt_on_action_error=self._halt_simulation_on_action_error
                        )
                        self.active_superstate_name = target_state_name
                        for sub_log_entry in self.active_sub_simulator.get_last_executed_actions_log():
                            self._action_log.append(sub_log_entry)
                    except Exception as e:
                        self._log_action(f"ERROR initializing sub-machine for '{target_state_name}': {e}")
                        logger.error(f"{self.log_prefix}Sub-machine init error for '{target_state_name}':", exc_info=True)
                        self.active_sub_simulator = None; self.active_superstate_name = None
                else:
                    self._log_action(f"Superstate '{target_state_name}' has no defined sub-machine data or states.")

    def _master_on_exit_state(self, source, **kwargs):
        source_state_name = source.id
        self._log_action(f"Exiting state: {source_state_name}")

        if self.active_sub_simulator and self.active_superstate_name == source_state_name:
            self._log_action(f"Superstate '{source_state_name}' exited. Terminating its sub-machine.")
            if hasattr(self.active_sub_simulator, 'get_last_executed_actions_log'):
                 for sub_log_entry in self.active_sub_simulator.get_last_executed_actions_log():
                     self._action_log.append(sub_log_entry)
            self.active_sub_simulator = None
            self.active_superstate_name = None

    def _sm_before_transition(self, event, source, target, **kwargs):
        event_name = event if isinstance(event, str) else (event.id if hasattr(event, 'id') else str(event))
        self._log_action(f"Before transition on '{event_name}' from '{source.id}' to '{target.id}'")

    def _sm_after_transition(self, event, source, target, **kwargs):
        event_name = event if isinstance(event, str) else (event.id if hasattr(event, 'id') else str(event))
        self._log_action(f"After transition on '{event_name}' from '{source.id}' to '{target.id}'")

    def _build_fsm_class_and_instance(self):
        fsm_class_attrs = {}
        sm_states_obj_map = {}
        initial_state_name_from_data = None

        for s_name, s_data in self._states_input_data.items():
            is_initial = s_data.get('is_initial', False)
            if is_initial:
                if initial_state_name_from_data:
                    raise FSMError(f"Multiple initial states: '{initial_state_name_from_data}' and '{s_name}'.")
                initial_state_name_from_data = s_name
                self._initial_state_name = s_name

            state_obj = State(name=s_name, value=s_name, initial=is_initial, final=s_data.get('is_final', False))
            
            if s_data.get('entry_action'):
                fsm_class_attrs[f"on_enter_{s_name}"] = self._create_dynamic_callback(
                    s_data['entry_action'], "action", f"entry_{s_name}"
                )
            if s_data.get('exit_action'):
                fsm_class_attrs[f"on_exit_{s_name}"] = self._create_dynamic_callback(
                    s_data['exit_action'], "action", f"exit_{s_name}"
                )
            
            fsm_class_attrs[s_name] = state_obj
            sm_states_obj_map[s_name] = state_obj

        if not initial_state_name_from_data and self._states_input_data:
            first_state_name_from_data = next(iter(self._states_input_data))
            if first_state_name_from_data in sm_states_obj_map:
                self._log_action(f"No initial state explicitly defined. Using first state '{first_state_name_from_data}' as initial.")
                sm_states_obj_map[first_state_name_from_data]._initial = True
                self._initial_state_name = first_state_name_from_data
            else:
                 raise FSMError("Fallback initial state error: First state not in map.")
        elif not self._states_input_data:
            if not self.parent_simulator: raise FSMError("No states defined in FSM.")
            else: self._log_action("Sub-FSM has no states defined. It will be inactive."); self.FSMClass = self.sm = None; return

        defined_events = {}
        for t_idx, t_data in enumerate(self._transitions_input_data):
            source_name, target_name = t_data['source'], t_data['target']
            event_name_str = t_data.get('event')
            if not event_name_str:
                event_name_str = f"_internal_t{t_idx}_{source_name}_to_{target_name}"
                event_name_str = "".join(c if c.isalnum() or c == '_' else '_' for c in event_name_str)
                self._log_action(f"Warning: Transition {source_name}->{target_name} has no event. Synthetic event ID: {event_name_str}")

            source_state_obj = sm_states_obj_map.get(source_name)
            target_state_obj = sm_states_obj_map.get(target_name)

            if not source_state_obj or not target_state_obj:
                self._log_action(f"Warning: Skipping transition for event '{event_name_str}' from '{source_name}' to '{target_name}' due to missing state object(s)."); continue
            
            if event_name_str not in defined_events:
                event_obj = SMEvent(event_name_str)
                defined_events[event_name_str] = event_obj
                fsm_class_attrs[event_name_str] = event_obj
            else: event_obj = defined_events[event_name_str]

            cond_cb = self._create_dynamic_callback(t_data['condition'], "condition", f"cond_t{t_idx}_{event_name_str}") if t_data.get('condition') else None
            action_cb = self._create_dynamic_callback(t_data['action'], "action", f"action_t{t_idx}_{event_name_str}") if t_data.get('action') else None
            
            _ = source_state_obj.to(target_state_obj, event=event_obj, cond=cond_cb, on=action_cb)

        fsm_class_attrs.update({
            "on_enter_state": self._master_on_enter_state,
            "on_exit_state": self._master_on_exit_state,
            "before_transition": self._sm_before_transition,
            "after_transition": self._sm_after_transition
        })
        
        try:
            unique_class_name = f"DynamicBSMFSM_{self.log_prefix.replace(' ', '').replace('[','').replace(']','').replace('-','')}_{id(self)}"
            self.FSMClass = type(unique_class_name, (StateMachine,), fsm_class_attrs)
        except InvalidDefinition as e_def:
             logger.error(f"{self.log_prefix}FSM Definition Error for '{unique_class_name}': {e_def}", exc_info=False)
             raise FSMError(f"FSM Definition Error: {e_def}")
        except Exception as e:
            logger.error(f"{self.log_prefix}Failed to create StateMachine class '{unique_class_name}': {e}", exc_info=True)
            raise FSMError(f"StateMachine class creation failed: {e}")

        try:
            self.sm = self.FSMClass(model=self._variables, allow_event_without_transition=True)
        except InvalidDefinition as e_def:
            logger.error(f"{self.log_prefix}FSM Instance Creation Error for '{unique_class_name}': {e_def}", exc_info=False)
            raise FSMError(f"FSM Instance Creation Error: {e_def}")
        except Exception as e:
            logger.error(f"{self.log_prefix}Failed to instantiate StateMachine '{unique_class_name}': {e}", exc_info=True)
            raise FSMError(f"StateMachine instantiation failed: {e}")

        if self.sm and self.sm.current_state:
            # This log is now deferred to the main constructor after _build_fsm_class_and_instance completes
            pass
        elif self.sm and not self.sm.current_state and self._states_input_data:
            raise FSMError(f"FSM '{unique_class_name}' initialized but no current state. Ensure initial=True for one state.")


    def get_current_state_name(self):
        if not self.sm: return "Uninitialized" if not self.parent_simulator else "EmptySubFSM"
        name = self.sm.current_state.id
        if self.active_sub_simulator and self.active_sub_simulator.sm:
            name += f" ({self.active_sub_simulator.get_current_state_name()})"
        return name

    def get_current_leaf_state_name(self):
        if self.active_sub_simulator and self.active_sub_simulator.sm :
            return self.active_sub_simulator.get_current_leaf_state_name()
        elif self.sm and self.sm.current_state: return self.sm.current_state.id
        return "UnknownLeaf"

    def get_variables(self): return self._variables.copy()
    def get_last_executed_actions_log(self):
        log_snapshot = self._action_log[:]
        self._action_log = []
        return log_snapshot

    def reset(self):
        self._log_action("--- FSM Resetting ---")
        self._variables.clear()
        self.simulation_halted_flag = False
        if self.active_sub_simulator:
            self._log_action("Resetting active sub-machine...")
            self.active_sub_simulator.reset()
            self._action_log.extend(self.active_sub_simulator.get_last_executed_actions_log())
            self.active_sub_simulator = self.active_superstate_name = None
        
        if self.FSMClass:
            try:
                self.sm = self.FSMClass(model=self._variables, allow_event_without_transition=True)
                current_state_id = self.sm.current_state.id if self.sm and self.sm.current_state else 'Unknown (No Initial State?)'
                self._log_action(f"FSM Reset. Current state: {current_state_id}")
            except Exception as e:
                logger.error(f"{self.log_prefix}Reset failed during SM re-instantiation: {e}", exc_info=True)
                raise FSMError(f"Reset failed during SM re-instantiation: {e}")
        elif not self.parent_simulator and not self._states_input_data:
            logger.error(f"{self.log_prefix}FSM Class not built (no states), cannot reset properly.")
        
    def step(self, event_name=None):
        if self.simulation_halted_flag:
            self._log_action(f"Simulation HALTED. Event '{event_name or 'Internal'}' ignored. Reset required.")
            return self.get_current_state_name(), self.get_last_executed_actions_log()

        if not self.sm:
            if not self.parent_simulator and not self._states_input_data :
                 logger.error(f"{self.log_prefix}Cannot step: FSM not initialized (no states)."); raise FSMError("Cannot step, FSM not initialized (no states).")
            elif self.parent_simulator and not self._states_input_data:
                self._log_action("Cannot step: Sub-FSM is empty/not defined.")
                return self.get_current_state_name(), self.get_last_executed_actions_log()
            else: logger.error(f"{self.log_prefix}Cannot step: FSM.sm not initialized."); raise FSMError("Cannot step, FSM.sm not initialized.")

        main_state_id = self.sm.current_state.id
        self._log_action(f"--- Step. State: {self.get_current_state_name()}. Event: {event_name or 'Internal'} ---")

        try:
            main_state_data = self._states_input_data.get(main_state_id)
            if main_state_data and main_state_data.get('during_action'):
                action_str = main_state_data['during_action']
                self._log_action(f"During action for '{main_state_id}': {action_str}")
                during_cb = self._create_dynamic_callback(action_str, "action", f"during_{main_state_id}")
                during_cb(self.sm)

            if self.simulation_halted_flag: return self.get_current_state_name(), self.get_last_executed_actions_log()

            if self.active_sub_simulator:
                superstate_log_name = self.active_superstate_name or main_state_id
                self._log_action(f"Internal step for sub-machine in '{superstate_log_name}'.")
                _, sub_log = self.active_sub_simulator.step(event_name=None)
                self._action_log.extend(sub_log)
                if self.active_sub_simulator.simulation_halted_flag:
                    self.simulation_halted_flag = True
                    self._log_action(f"Propagation: Parent HALTED due to sub-machine error in '{superstate_log_name}'."); return self.get_current_state_name(), self.get_last_executed_actions_log()
                
                sub_sm_instance = self.active_sub_simulator.sm
                if sub_sm_instance and sub_sm_instance.current_state and sub_sm_instance.current_state.final:
                    self._log_action(f"Sub-machine in '{superstate_log_name}' reached final state: '{sub_sm_instance.current