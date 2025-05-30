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
                # This was previously `pass`. If we want to allow user-defined functions that are somehow made available
                # in the execution scope (e.g., via `self._variables` initially or through other safe mechanisms),
                # then `pass` is okay. If we want to be stricter and only allow predefined safe builtins and variables
                # explicitly in `self._variables`, then this should also append a violation.
                # For now, keeping it as `pass` assuming advanced users might inject safe callables.
                pass
        super().generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.attr, str):
            if node.attr in self.truly_dangerous_attributes:
                self.violations.append(f"SecurityError: Access to the attribute '{node.attr}' is restricted.")
            elif node.attr.startswith('__') and node.attr.endswith('__') and node.attr not in self.allowed_dunder_attrs:
                self.violations.append(f"SecurityError: Access to the special attribute '{node.attr}' is restricted.")
        super().generic_visit(node)

    def visit_Exec(self, node): # Python 2.x specific, unlikely to be used with ast.parse in Py3
        self.violations.append("SecurityError: The 'exec' statement/function is not allowed.")
        super().generic_visit(node)

def check_code_safety_basic(code_string: str, fsm_variables: set) -> tuple[bool, str]:
    if not code_string.strip():
        return True, ""
    try:
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
        self._variables = {}
        self._action_log = []
        self.FSMClass = None
        self.sm: StateMachine | None = None
        self._initial_state_name = None
        self.parent_simulator: StateMachinePoweredSimulator | None = parent_simulator
        self.log_prefix = log_prefix

        self.active_sub_simulator: StateMachinePoweredSimulator | None = None
        self.active_superstate_name: str | None = None
        self._halt_simulation_on_action_error = halt_on_action_error
        self.simulation_halted_flag = False

        try:
            self._build_fsm_class_and_instance()
            if self.sm and self.sm.current_state:
                self._log_action(f"FSM Initialized. Current state: {self.sm.current_state.id}")
            elif not self._states_input_data and not self.parent_simulator: # Top-level FSM with no states
                 raise FSMError("No states defined in the FSM.")
            elif not self._states_input_data and self.parent_simulator: # Sub-FSM with no states
                self._log_action("Sub-FSM initialized but has no states (inactive).")
            # If FSMClass was built but self.sm is None (e.g., no initial state resolved and instantiation failed)
            elif self.FSMClass and not self.sm and (self._states_input_data or self.parent_simulator):
                 raise FSMError("FSM Initialization failed: StateMachine (sm) instance is None after build. Check initial state definition.")

        except InvalidDefinition as e:
            logger.error(f"{self.log_prefix}FSM Definition Error during Initialization: {e}", exc_info=False)
            raise FSMError(f"FSM Definition Error: {e}")
        except FSMError: # Re-raise FSMError directly
            raise
        except Exception as e: # Catch other unexpected errors
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
                unsafe_condition_wrapper.__name__ = f"{original_name}_blocked_condition_safety_{hash(code_string)}"
                return unsafe_condition_wrapper
            else: # action
                def unsafe_action_wrapper(*args, **kwargs):
                    self._log_action(f"[Action Blocked by Safety Check] Unsafe code ignored: '{code_string}'.")
                unsafe_action_wrapper.__name__ = f"{original_name}_blocked_action_safety_{hash(code_string)}"
                return unsafe_action_wrapper

        simulator_self = self

        def dynamic_callback_wrapper(*args, **kwargs_from_sm_call):
            sm_instance_arg = None
            if args and isinstance(args[0], StateMachine):
                sm_instance_arg = args[0]
            elif 'machine' in kwargs_from_sm_call:
                sm_instance_arg = kwargs_from_sm_call['machine']
            
            if not sm_instance_arg:
                passed_args = args[1:] if args and isinstance(args[0], StateMachine) else args
                simulator_self._log_action(f"[Callback Error] Could not determine StateMachine instance for '{original_name}'. Args: {passed_args}, Kwargs: {list(kwargs_from_sm_call.keys())}")
                if callback_type == "condition": return False
                return

            exec_eval_locals_dict = simulator_self._variables # Always use the simulator's _variables

            log_prefix_runtime = "[Action Runtime]" if callback_type == "action" else "[Condition Runtime]"
            current_state_for_log = "UnknownState"
            if sm_instance_arg and sm_instance_arg.current_state:
                 current_state_for_log = sm_instance_arg.current_state.id
            elif simulator_self.parent_simulator and simulator_self.parent_simulator.sm and simulator_self.parent_simulator.sm.current_state:
                 current_state_for_log = f"{simulator_self.parent_simulator.sm.current_state.id} (sub-context)"
            
            action_or_cond_id = original_name.split('_')[-1] if '_' in original_name else original_name

            simulator_self._log_action(f"{log_prefix_runtime} Executing: '{code_string}' in state '{current_state_for_log}' for '{action_or_cond_id}' with vars: {exec_eval_locals_dict}")

            try:
                if callback_type == "action":
                    exec(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict)
                    simulator_self._log_action(f"{log_prefix_runtime} Finished: '{code_string}'. Variables now: {exec_eval_locals_dict}")
                    return None
                elif callback_type == "condition":
                    result = eval(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict.copy()) # Use a copy for eval to prevent modification
                    simulator_self._log_action(f"{log_prefix_runtime} Result of '{code_string}': {result}")
                    return bool(result)
            except SyntaxError as e:
                err_msg = (f"SyntaxError in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{e.msg} (line {e.lineno}, offset {e.offset}). Code: '{code_string}'")
                simulator_self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{simulator_self.log_prefix}{err_msg}", exc_info=False)
                if callback_type == "condition": return False
                if simulator_self._halt_simulation_on_action_error and callback_type == "action": simulator_self.simulation_halted_flag = True; raise FSMError(err_msg)
            except NameError as e:
                err_msg = (f"NameError in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{e}. Variable not defined or not in SAFE_BUILTINS? Code: '{code_string}'")
                simulator_self._log_action(f"[Code Error] {err_msg}")
                logger.warning(f"{simulator_self.log_prefix}{err_msg}")
                if callback_type == "condition": return False
                if simulator_self._halt_simulation_on_action_error and callback_type == "action": simulator_self.simulation_halted_flag = True; raise FSMError(err_msg)
            except TypeError as e:
                err_msg = (f"TypeError in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{e}. Code: '{code_string}'")
                simulator_self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{simulator_self.log_prefix}{err_msg}", exc_info=True)
                if callback_type == "condition": return False
                if simulator_self._halt_simulation_on_action_error and callback_type == "action": simulator_self.simulation_halted_flag = True; raise FSMError(err_msg)
            except (AttributeError, IndexError, KeyError, ValueError, ZeroDivisionError) as e:
                err_msg = (f"{type(e).__name__} in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{e}. Code: '{code_string}'")
                simulator_self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{simulator_self.log_prefix}{err_msg}", exc_info=True)
                if callback_type == "condition": return False
                if simulator_self._halt_simulation_on_action_error and callback_type == "action": simulator_self.simulation_halted_flag = True; raise FSMError(err_msg)
            except Exception as e:
                err_msg = (f"Unexpected runtime error in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{type(e).__name__} - {e}. Code: '{code_string}'")
                simulator_self._log_action(f"[Code Error] {err_msg}")
                logger.error(f"{simulator_self.log_prefix}{err_msg}", exc_info=True)
                if callback_type == "condition": return False
                if simulator_self._halt_simulation_on_action_error and callback_type == "action": simulator_self.simulation_halted_flag = True; raise FSMError(err_msg)
            return None
        dynamic_callback_wrapper.__name__ = f"{original_name}_{callback_type}_{hash(code_string)}"
        return dynamic_callback_wrapper

    def _master_on_enter_state_impl(self, sm_instance: StateMachine, target: State, **kwargs):
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
                        # Capture and append sub-simulator's initialization logs
                        for sub_log_entry in self.active_sub_simulator.get_last_executed_actions_log():
                            self._action_log.append(sub_log_entry)
                    except Exception as e:
                        self._log_action(f"ERROR initializing sub-machine for '{target_state_name}': {e}")
                        logger.error(f"{self.log_prefix}Sub-machine init error for '{target_state_name}':", exc_info=True)
                        self.active_sub_simulator = None; self.active_superstate_name = None
                        if self._halt_simulation_on_action_error: self.simulation_halted_flag = True; raise FSMError(f"Sub-FSM init failed for {target_state_name}: {e}")
                else:
                    self._log_action(f"Superstate '{target_state_name}' has no defined sub-machine data or states.")

    def _master_on_exit_state_impl(self, sm_instance: StateMachine, source: State, **kwargs):
        source_state_name = source.id
        self._log_action(f"Exiting state: {source_state_name}")

        if self.active_sub_simulator and self.active_superstate_name == source_state_name:
            self._log_action(f"Superstate '{source_state_name}' exited. Terminating its sub-machine.")
            if hasattr(self.active_sub_simulator, 'get_last_executed_actions_log'):
                 # Capture and append sub-simulator's final logs before it's nulled
                 for sub_log_entry in self.active_sub_simulator.get_last_executed_actions_log():
                     self._action_log.append(sub_log_entry)
            self.active_sub_simulator = None
            self.active_superstate_name = None

    def _sm_before_transition_impl(self, sm_instance: StateMachine, event: str, source: State, target: State, **kwargs):
        event_data_obj = kwargs.get('event_data')
        triggered_event_name = event_data_obj.event if event_data_obj else event
        self._log_action(f"Before transition on '{triggered_event_name}' from '{source.id}' to '{target.id}'")

    def _sm_after_transition_impl(self, sm_instance: StateMachine, event: str, source: State, target: State, **kwargs):
        event_data_obj = kwargs.get('event_data')
        triggered_event_name = event_data_obj.event if event_data_obj else event
        self._log_action(f"After transition on '{triggered_event_name}' from '{source.id}' to '{target.id}'")


    def _build_fsm_class_and_instance(self):
        fsm_class_attrs = {}
        sm_states_obj_map = {}
        initial_state_name_from_data = None
        simulator_self = self # Closure for lambdas

        for s_name, s_data in self._states_input_data.items():
            is_initial = s_data.get('is_initial', False)
            if is_initial:
                if initial_state_name_from_data:
                    raise FSMError(f"Multiple initial states defined: '{initial_state_name_from_data}' and '{s_name}'.")
                initial_state_name_from_data = s_name
                self._initial_state_name = s_name

            state_obj = State(name=s_name, value=s_name, initial=is_initial, final=s_data.get('is_final', False))
            
            if s_data.get('entry_action'):
                # Capture s_data and s_name by value for the lambda
                fsm_class_attrs[f"on_enter_{s_name}"] = lambda sm_instance, *args, sd=s_data.copy(), sn=s_name, **kwargs: \
                    simulator_self._create_dynamic_callback(
                        sd['entry_action'], "action", f"entry_{sn}"
                    )(sm_instance, *args, **kwargs)

            if s_data.get('exit_action'):
                # Capture s_data and s_name by value for the lambda
                fsm_class_attrs[f"on_exit_{s_name}"] = lambda sm_instance, *args, sd=s_data.copy(), sn=s_name, **kwargs: \
                    simulator_self._create_dynamic_callback(
                        sd['exit_action'], "action", f"exit_{sn}"
                    )(sm_instance, *args, **kwargs)
            
            fsm_class_attrs[s_name] = state_obj
            sm_states_obj_map[s_name] = state_obj

        if not initial_state_name_from_data and self._states_input_data: # If states exist but no initial
            first_state_name_from_data = next(iter(self._states_input_data)) # Take the first state as initial
            if first_state_name_from_data in sm_states_obj_map:
                self._log_action(f"Warning: No initial state explicitly defined. Using first state '{first_state_name_from_data}' as initial.")
                sm_states_obj_map[first_state_name_from_data]._initial = True # Set initial flag on the State object
                self._initial_state_name = first_state_name_from_data
            else: # Should not happen if map is built correctly
                 raise FSMError("Fallback initial state error: First state not found in map.")
        elif not self._states_input_data: # No states defined at all
            if not self.parent_simulator: raise FSMError("No states defined in FSM.")
            else: self._log_action("Sub-FSM has no states defined. It will be inactive."); self.FSMClass = self.sm = None; return

        # Ensure there's at least one event defined if there are transitions.
        # python-statemachine will raise InvalidDefinition if no events are present.
        # If there are no transitions, this is okay for an FSM with only states (though unusual).
        if not self._transitions_input_data and self._states_input_data:
            self._log_action("Warning: FSM has states but no transitions. No events will be defined beyond potential state actions.")
            # Add a dummy event if no transitions, to satisfy python-statemachine if it strictly requires an event.
            # This is often needed if the library expects at least one SMEvent instance.
            if not any(isinstance(attr, SMEvent) for attr in fsm_class_attrs.values()):
                dummy_event_name = f"_internal_dummy_event_{id(self)}"
                fsm_class_attrs[dummy_event_name] = SMEvent(dummy_event_name)
                self._log_action(f"Added dummy event '{dummy_event_name}' as no transitions were defined.")


        defined_events = {}
        for t_idx, t_data in enumerate(self._transitions_input_data):
            source_name, target_name = t_data['source'], t_data['target']
            event_name_str = t_data.get('event')
            if not event_name_str: # Create a synthetic event name if none provided
                event_name_str = f"_internal_t{t_idx}_{source_name}_to_{target_name}"
                event_name_str = "".join(c if c.isalnum() or c == '_' else '_' for c in event_name_str) # Sanitize
                self._log_action(f"Warning: Transition {source_name}->{target_name} has no event. Synthetic event ID: {event_name_str}")

            source_state_obj = sm_states_obj_map.get(source_name)
            target_state_obj = sm_states_obj_map.get(target_name)

            if not source_state_obj or not target_state_obj:
                self._log_action(f"Warning: Skipping transition for event '{event_name_str}' from '{source_name}' to '{target_name}' due to missing state object(s)."); continue
            
            # Create or reuse SMEvent object
            if event_name_str not in defined_events:
                event_obj = SMEvent(event_name_str)
                defined_events[event_name_str] = event_obj
                fsm_class_attrs[event_name_str] = event_obj # Add event trigger to class
            else: event_obj = defined_events[event_name_str]

            # Create condition callback if specified
            cond_cb = simulator_self._create_dynamic_callback(
                t_data['condition'], "condition", f"cond_t{t_idx}_{event_name_str}"
            ) if t_data.get('condition') else None

            # Create action callback if specified
            action_cb = simulator_self._create_dynamic_callback(
                t_data['action'], "action", f"action_t{t_idx}_{event_name_str}"
            ) if t_data.get('action') else None
            
            # Define the transition on the source state object
            _ = source_state_obj.to(target_state_obj, event=event_obj, cond=cond_cb, on=action_cb)

        # Add master state enter/exit and transition before/after hooks
        fsm_class_attrs.update({
            "on_enter_state": lambda sm_instance, target, **kwargs: simulator_self._master_on_enter_state_impl(sm_instance, target, **kwargs),
            "on_exit_state": lambda sm_instance, source, **kwargs: simulator_self._master_on_exit_state_impl(sm_instance, source, **kwargs),
            "before_transition": lambda sm_instance, event, source, target, **kwargs: simulator_self._sm_before_transition_impl(sm_instance, event, source, target, **kwargs),
            "after_transition": lambda sm_instance, event, source, target, **kwargs: simulator_self._sm_after_transition_impl(sm_instance, event, source, target, **kwargs)
        })
        
        # Create the StateMachine class dynamically
        try:
            unique_class_name = f"DynamicBSMFSM_{self.log_prefix.replace(' ', '').replace('[','').replace(']','').replace('-','')}_{id(self)}"
            self.FSMClass = type(unique_class_name, (StateMachine,), fsm_class_attrs)
        except InvalidDefinition as e_def:
             logger.error(f"{self.log_prefix}FSM Definition Error for '{unique_class_name}': {e_def}", exc_info=False)
             raise FSMError(f"FSM Definition Error: {e_def}")
        except Exception as e: # Catch other errors during class creation
            logger.error(f"{self.log_prefix}Failed to create StateMachine class '{unique_class_name}': {e}", exc_info=True)
            raise FSMError(f"StateMachine class creation failed: {e}")

        # Instantiate the StateMachine
        try:
            # Pass model for variable storage, allow_event_without_transition for flexibility
            self.sm = self.FSMClass(model=self._variables, allow_event_without_transition=True)
        except InvalidDefinition as e_def: # Catch definition errors during instantiation
            logger.error(f"{self.log_prefix}FSM Instance Creation Error for '{unique_class_name}': {e_def}", exc_info=False)
            raise FSMError(f"FSM Instance Creation Error: {e_def}")
        except Exception as e: # Catch other errors during instantiation
            logger.error(f"{self.log_prefix}Failed to instantiate StateMachine '{unique_class_name}': {e}", exc_info=True)
            raise FSMError(f"StateMachine instantiation failed: {e}")

        # Post-instantiation check
        if self.sm and self.sm.current_state:
            # Successfully initialized with a current state
            pass
        elif self.sm and not self.sm.current_state and self._states_input_data:
            # SM instance created but no current state (e.g. initial state logic failed in python-statemachine)
            raise FSMError(f"FSM '{unique_class_name}' initialized but no current state. Ensure initial=True for one state or check for library errors.")

    def get_current_state_name(self):
        if not self.sm: return "Uninitialized" if not self.parent_simulator else "EmptySubFSM"
        name = self.sm.current_state.id
        if self.active_sub_simulator and self.active_sub_simulator.sm: # If sub-FSM is active
            name += f" ({self.active_sub_simulator.get_current_state_name()})" # Append sub-state
        return name

    def get_current_leaf_state_name(self):
        if self.active_sub_simulator and self.active_sub_simulator.sm :
            return self.active_sub_simulator.get_current_leaf_state_name()
        elif self.sm and self.sm.current_state: return self.sm.current_state.id
        return "UnknownLeaf" # Should not happen in a valid FSM

    def get_variables(self): return self._variables.copy()
    def get_last_executed_actions_log(self):
        log_snapshot = self._action_log[:]
        self._action_log = [] # Clear log after retrieval
        return log_snapshot

    def reset(self):
        self._log_action("--- FSM Resetting ---")
        self._variables.clear()
        self.simulation_halted_flag = False
        if self.active_sub_simulator:
            self._log_action("Resetting active sub-machine...")
            self.active_sub_simulator.reset() # Recursively reset sub-machine
            self._action_log.extend(self.active_sub_simulator.get_last_executed_actions_log()) # Collect sub-log
            self.active_sub_simulator = self.active_superstate_name = None
        
        if self.FSMClass:
            try:
                # Re-instantiate the FSM using the existing class definition
                self.sm = self.FSMClass(model=self._variables, allow_event_without_transition=True)
                current_state_id = self.sm.current_state.id if self.sm and self.sm.current_state else 'Unknown (No Initial State?)'
                self._log_action(f"FSM Reset. Current state: {current_state_id}")
            except Exception as e:
                logger.error(f"{self.log_prefix}Reset failed during SM re-instantiation: {e}", exc_info=True)
                raise FSMError(f"Reset failed during SM re-instantiation: {e}")
        elif not self.parent_simulator and not self._states_input_data: # Top-level FSM with no states
            logger.error(f"{self.log_prefix}FSM Class not built (no states defined), cannot reset properly.")
        # If it's a sub-FSM with no states, it's already considered "reset" (inactive)
        
    def step(self, event_name=None):
        if self.simulation_halted_flag:
            self._log_action(f"Simulation HALTED. Event '{event_name or 'Internal'}' ignored. Reset required.")
            return self.get_current_state_name(), self.get_last_executed_actions_log()

        if not self.sm: # If StateMachine instance (self.sm) is None
            if not self.parent_simulator and not self._states_input_data : # Top-level FSM with no states
                 logger.error(f"{self.log_prefix}Cannot step: FSM not initialized (no states)."); raise FSMError("Cannot step, FSM not initialized (no states).")
            elif self.parent_simulator and not self._states_input_data: # Empty sub-FSM
                self._log_action("Cannot step: Sub-FSM is empty/not defined.")
                return self.get_current_state_name(), self.get_last_executed_actions_log()
            else: # Should have been caught by __init__ if FSMClass was built but sm is None
                logger.error(f"{self.log_prefix}Cannot step: FSM.sm not initialized."); raise FSMError("Cannot step, FSM.sm not initialized.")

        main_state_id = self.sm.current_state.id
        self._log_action(f"--- Step. State: {self.get_current_state_name()}. Event: {event_name or 'Internal'} ---")

        try:
            # Execute 'during' action of the current main state
            main_state_data = self._states_input_data.get(main_state_id)
            if main_state_data and main_state_data.get('during_action'):
                action_str = main_state_data['during_action']
                self._log_action(f"During action for '{main_state_id}': {action_str}")
                during_cb = self._create_dynamic_callback(action_str, "action", f"during_{main_state_id}")
                during_cb(self.sm) # Pass the StateMachine instance

            if self.simulation_halted_flag: return self.get_current_state_name(), self.get_last_executed_actions_log()

            # If there's an active sub-simulator, step it (internal step, no explicit event)
            if self.active_sub_simulator:
                superstate_log_name = self.active_superstate_name or main_state_id
                self._log_action(f"Internal step for sub-machine in '{superstate_log_name}'.")
                _, sub_log = self.active_sub_simulator.step(event_name=None) # Internal step for sub-machine
                self._action_log.extend(sub_log)
                if self.active_sub_simulator.simulation_halted_flag:
                    self.simulation_halted_flag = True
                    self._log_action(f"Propagation: Parent HALTED due to sub-machine error in '{superstate_log_name}'."); return self.get_current_state_name(), self.get_last_executed_actions_log()
                
                # Check if sub-machine reached a final state
                sub_sm_instance = self.active_sub_simulator.sm
                if sub_sm_instance and sub_sm_instance.current_state and sub_sm_instance.current_state.final:
                    self._log_action(f"Sub-machine in '{superstate_log_name}' reached final state: '{sub_sm_instance.current_state.id}'.")
                    if self.active_superstate_name: # If we know the superstate name
                         self._variables[f"{self.active_superstate_name}_sub_completed"] = True
                         self._log_action(f"Variable '{self.active_superstate_name}_sub_completed' set to True in parent FSM.")
            
            if self.simulation_halted_flag: return self.get_current_state_name(), self.get_last_executed_actions_log()

            # Send event to the main FSM if an event_name is provided
            if event_name:
                self._log_action(f"Sending event '{event_name}' to FSM.")
                self.sm.send(event_name) # This triggers transitions, entry/exit actions, etc.
            elif not self.active_sub_simulator: # No event and no active sub-sim
                 self._log_action(f"No event. 'During' actions done. State remains '{main_state_id}'.")

        except FSMError as e_halt: # Catch FSMError if an action callback raised it to halt
            if self.simulation_halted_flag or "HALTED due to error" in str(e_halt):
                self._log_action(f"[SIMULATION HALTED internally] {e_halt}"); self.simulation_halted_flag = True
            else: self._log_action(f"FSM Logic Error during step: {e_halt}"); logger.error(f"{self.log_prefix}FSM Logic Error:", exc_info=True)
        except TransitionNotAllowed: self._log_action(f"Event '{event_name}' not allowed or no transition from '{main_state_id}'.")
        except AttributeError as e: # e.g. event name not defined on FSM
            log_msg = f"Event '{event_name}' not defined on FSM."
            if event_name and hasattr(self.sm, event_name) and not callable(getattr(self.sm, event_name)):
                log_msg = f"Event name '{event_name}' conflicts with state or non-event attribute."
            elif event_name and hasattr(self.sm, event_name) and callable(getattr(self.sm, event_name)): # Should be callable if it's an event
                log_msg = f"AttributeError processing event '{event_name}': {e}. Internal setup/callback issue?"
            self._log_action(log_msg); logger.error(f"{self.log_prefix}AttributeError for '{event_name}':", exc_info=True)
        except Exception as e: self._log_action(f"Unexpected error on event '{event_name}': {type(e).__name__} - {e}"); logger.error(f"{self.log_prefix}Event processing error:", exc_info=True)

        return self.get_current_state_name(), self.get_last_executed_actions_log()

    def get_possible_events_from_current_state(self) -> list[str]:
        if not self.sm or not self.sm.current_state: return []
        
        possible_events_set = set()
        current_sm_to_query = self.sm # Start with the main FSM
        
        # If a sub-machine is active, its events take precedence or are combined
        if self.active_sub_simulator and self.active_sub_simulator.sm:
            current_sm_to_query = self.active_sub_simulator.sm
        
        if current_sm_to_query and current_sm_to_query.current_state:
            # `allowed_events` on python-statemachine returns a list of BoundEvent objects
            possible_events_set.update(str(evt.id) for evt in current_sm_to_query.allowed_events)
        
        # Also add events from the parent FSM if a sub-FSM was active,
        # as parent transitions might be triggered by events while in a superstate.
        if self.active_sub_simulator and self.sm and self.sm.current_state:
             possible_events_set.update(str(evt.id) for evt in self.sm.allowed_events)

        return sorted(list(possible_events_set))


FSMSimulator = StateMachinePoweredSimulator

if __name__ == "__main__":
    main_states_data = [
        {"name": "Idle", "is_initial": True, "entry_action": "print('Main: Idle Entered'); idle_counter = 0; Processing_sub_completed = False"},
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
        {"name": "Done", "is_final": True, "entry_action": "print('Main: Done Entered')"}
    ]
    main_transitions_data = [
        {"source": "Idle", "target": "Processing", "event": "start_processing"},
        {"source": "Processing", "target": "Done", "event": "auto_finish", "condition": "Processing_sub_completed == True"}
    ]

    print("--- HIERARCHICAL SIMULATOR TEST (python-statemachine) ---")
    try:
        simulator = FSMSimulator(main_states_data, main_transitions_data, halt_on_action_error=False)

        def print_status(sim, step_name=""):
            print(f"\n--- {step_name} ---")
            print(f"Current State: {sim.get_current_state_name()}")
            print(f"Leaf State: {sim.get_current_leaf_state_name()}")
            print(f"Main Vars: {sim.get_variables()}")
            if sim.active_sub_simulator: print(f"Sub Vars: {sim.active_sub_simulator.get_variables()}")
            log = sim.get_last_executed_actions_log()
            if log: print("Log:"); [print(f"  {entry}") for entry in log]
            print("Possible events:", sim.get_possible_events_from_current_state())
            print("--------------------")

        print_status(simulator, "INITIAL STATE")
        simulator.step("start_processing"); print_status(simulator, "AFTER 'start_processing'")
        
        if simulator.active_sub_simulator:
            print("\n>>> Trigger 'start_sub_work' on sub-machine (via parent's step) <<<")
            # In this model, parent steps and sub-machine events are handled somewhat separately.
            # To trigger sub-event, one might need to call step on active_sub_simulator directly
            # or ensure parent step can proxy specific events to sub-machine.
            # For this test, we'll directly step the sub-simulator.
            simulator.active_sub_simulator.step("start_sub_work")
            # Important: after stepping sub-simulator, its log is in its own _action_log.
            # The parent's step method would typically collect this if it were managing the sub-step.
            # For direct sub-step, we can manually append or review its log.
            print("Sub-log after direct sub-step:", simulator.active_sub_simulator.get_last_executed_actions_log())
            print_status(simulator, "AFTER sub-event 'start_sub_work'")
        
        simulator.step(None); print_status(simulator, "AFTER main internal step 1 (sub during actions run)")
        simulator.step(None); print_status(simulator, "AFTER main internal step 2 (sub during actions run)")
        
        if simulator.active_sub_simulator:
            print("\n>>> Trigger 'finish_sub_work' on sub-machine (via parent's step) <<<")
            simulator.active_sub_simulator.step("finish_sub_work")
            print("Sub-log after direct sub-step:", simulator.active_sub_simulator.get_last_executed_actions_log())
            print_status(simulator, "AFTER sub-event 'finish_sub_work'")
        
        simulator.step("auto_finish"); print_status(simulator, "AFTER 'auto_finish'")

        print("\n--- Test Unsafe Code (should be blocked) ---")
        unsafe_states_s = [{"name": "UnsafeStateS", "is_initial": True, "entry_action": "__import__('os').system('echo THIS_SHOULD_BE_BLOCKED')"}]
        unsafe_trans_s = [{"source": "UnsafeStateS", "target": "UnsafeStateS", "event": "dummy_event_unsafe"}]
        try:
            unsafe_sim_s = FSMSimulator(unsafe_states_s, unsafe_trans_s)
            print_status(unsafe_sim_s, "Unsafe Sim Test Start (check logs for blocking)")
        except FSMError as e: print(f"FSM Error during unsafe_sim_s setup: {e}") 
        except Exception as e: print(f"Unexpected error during unsafe_sim_s: {e}")

        print("\n--- Test Action Error (NameError, non-halting) ---")
        error_states = [{"name": "ErrState", "is_initial": True, "entry_action": "my_undefined_var = 1 / 0"}]
        error_trans = [{"source": "ErrState", "target": "ErrState", "event": "dummy_event_error"}]
        try:
            error_sim = FSMSimulator(error_states, error_trans, halt_on_action_error=False)
            print_status(error_sim, "Error Sim Start (NameError, non-halting)")
        except FSMError as e: print(f"FSM Error during error_sim setup: {e}")

        print("\n--- Test Action Error (ZeroDivisionError, with halting) ---")
        halt_error_states = [{"name": "HaltErrState", "is_initial": True, "entry_action": "x = 1 / 0"}]
        halt_error_trans = [{"source": "HaltErrState", "target": "HaltErrState", "event": "dummy_event_halt"}]
        halt_sim = None 
        try:
            halt_sim = FSMSimulator(halt_error_states, halt_error_trans, halt_on_action_error=True)
            # This print_status might not be reached if the FSMError due to action error occurs during SM instantiation's initial state entry
            print_status(halt_sim, "Halt Error Sim (MAY NOT REACH HERE if error in init path)")
        except FSMError as e: 
            print(f"FSM Error (as expected from halt_on_action_error): {e}")
            # If halt_sim was partially initialized before error, try to get logs
            if halt_sim and hasattr(halt_sim, 'get_last_executed_actions_log'):
                 log = halt_sim.get_last_executed_actions_log()
                 if log: print("Log from (partially) halted sim:"); [print(f"  {entry}") for entry in log]

    except FSMError as e: print(f"FSM Error: {e}")
    except Exception as e: print(f"An unexpected error occurred: {e}"); import traceback; traceback.print_exc()