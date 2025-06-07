# bsm_designer_project/fsm_simulator.py

# print("fsm_simulator.py is being imported with python-statemachine integration, HIERARCHY AWARENESS, and Enhanced Security/Robustness!")

import logging
import ast # For AST-based safety checks

# Configure logging for this module
logger = logging.getLogger(__name__)
# Removed the direct handler setup here. It will be configured by logging_setup.py when imported.

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
                # Allow calls to user-defined functions if they are among allowed_variable_names (e.g. if they were pre-defined in scope)
                # Or if they are known safe builtins (already handled)
                # This part might need refinement based on how user functions are exposed to the exec context.
                # For now, if it's not a known safe function or an allowed variable, it's implicitly allowed by passing.
                # A stricter approach would be to disallow unknown calls unless explicitly in allowed_variable_names.
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
        self.sm: "StateMachine | None" = None # Use the actual StateMachine type if available
        self._initial_state_name = None
        self.parent_simulator: StateMachinePoweredSimulator | None = parent_simulator
        self.log_prefix = log_prefix

        self.active_sub_simulator: StateMachinePoweredSimulator | None = None
        self.active_superstate_name: str | None = None
        self._halt_simulation_on_action_error = halt_on_action_error
        self.simulation_halted_flag = False
        
        self.current_tick = 0
        
        self.breakpoints = {"states": set(), "transitions": set()} 
        self.breakpoint_hit_flag = False 
        self.paused_on_breakpoint = False 

        # Dynamically import from the vendored statemachine library
        # This avoids a top-level import that might conflict if python-statemachine
        # is also installed globally and sys.path is not set up as expected.
        # However, for type hinting and clarity, a direct import is usually preferred
        # if the vendoring is the primary way the library is used.
        # Let's assume for now the direct import works due to project structure.
        from statemachine import StateMachine, State, TransitionNotAllowed, InvalidDefinition

        self.StateMachineModule_StateMachine = StateMachine
        self.StateMachineModule_State = State
        self.StateMachineModule_TransitionNotAllowed = TransitionNotAllowed
        self.StateMachineModule_InvalidDefinition = InvalidDefinition


        try:
            self._build_fsm_class_and_instance()
            if self.sm and self.sm.current_state:
                self._log_action(f"FSM Initialized. Current state: {self.sm.current_state.id}")
            elif not self._states_input_data and not self.parent_simulator:
                 raise FSMError("No states defined in the FSM.")
            elif not self._states_input_data and self.parent_simulator:
                self._log_action("Sub-FSM initialized but has no states (inactive).")
            elif self.FSMClass and not self.sm and (self._states_input_data or self.parent_simulator):
                 raise FSMError("FSM Initialization failed: StateMachine (sm) instance is None after build. Check initial state definition.")

        except self.StateMachineModule_InvalidDefinition as e: # Use the imported class
            logger.error(f"{self.log_prefix}FSM Definition Error during Initialization: {e}", exc_info=False)
            raise FSMError(f"FSM Definition Error: {e}")
        except FSMError:
            raise
        except Exception as e:
            logger.error(f"{self.log_prefix}Initialization failed: {e}", exc_info=True)
            raise FSMError(f"FSM Initialization failed: {e}")

    def _log_action(self, message, level_prefix_override=None):
        prefix_to_use = level_prefix_override if level_prefix_override is not None else self.log_prefix
        full_message = f"{prefix_to_use}[Tick {self.current_tick}] {message}"
        self._action_log.append(full_message)
        logger.info(full_message)

    def _create_dynamic_callback(self, code_string, callback_type="action", original_name="dynamic_callback"):
        current_fsm_variables = set(self._variables.keys())
        is_safe, safety_message = check_code_safety_basic(code_string, current_fsm_variables)
        
        if not is_safe:
            err_msg = f"SecurityError: Code execution blocked for '{original_name}'. Reason: {safety_message}"
            self._log_action(f"[Safety Check Failed] {err_msg}")
            if callback_type == "condition":
                def unsafe_condition_wrapper(*args, **kwargs):
                    self._log_action(f"[Condition Blocked by Safety Check] Unsafe code: '{code_string}' evaluated as False.")
                    return False
                unsafe_condition_wrapper.__name__ = f"{original_name}_blocked_condition_safety_{hash(code_string)}"
                return unsafe_condition_wrapper
            else: 
                def unsafe_action_wrapper(*args, **kwargs):
                    self._log_action(f"[Action Blocked by Safety Check] Unsafe code ignored: '{code_string}'.")
                unsafe_action_wrapper.__name__ = f"{original_name}_blocked_action_safety_{hash(code_string)}"
                return unsafe_action_wrapper

        simulator_self = self

        def dynamic_callback_wrapper(*args, **kwargs_from_sm_call):
            sm_instance_arg = None
            if args and isinstance(args[0], self.StateMachineModule_StateMachine):
                sm_instance_arg = args[0]
            elif 'machine' in kwargs_from_sm_call:
                sm_instance_arg = kwargs_from_sm_call['machine']
            
            if not sm_instance_arg:
                passed_args = args[1:] if args and isinstance(args[0], self.StateMachineModule_StateMachine) else args
                simulator_self._log_action(f"[Callback Error] Could not determine StateMachine instance for '{original_name}'. Args: {passed_args}, Kwargs: {list(kwargs_from_sm_call.keys())}")
                if callback_type == "condition": return False
                return

            exec_eval_locals_dict = simulator_self._variables.copy() 
            exec_eval_locals_dict['current_tick'] = simulator_self.current_tick
            
            log_prefix_runtime = "[Action Runtime]" if callback_type == "action" else "[Condition Runtime]"
            current_state_for_log = "UnknownState"
            if sm_instance_arg and sm_instance_arg.current_state:
                 current_state_for_log = sm_instance_arg.current_state.id
            elif simulator_self.parent_simulator and simulator_self.parent_simulator.sm and simulator_self.parent_simulator.sm.current_state:
                 current_state_for_log = f"{simulator_self.parent_simulator.sm.current_state.id} (sub-context)"
            
            action_or_cond_id = original_name.split('_')[-1] if '_' in original_name else original_name
            simulator_self._log_action(f"{log_prefix_runtime} Executing: '{code_string}' in state '{current_state_for_log}' for '{action_or_cond_id}' with vars: {list(exec_eval_locals_dict.keys())}")


            try:
                if callback_type == "action":
                    exec(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict)
                    for key, value in exec_eval_locals_dict.items():
                        if key not in SAFE_BUILTINS and key != 'current_tick' and key != '__builtins__':
                            simulator_self._variables[key] = value
                    simulator_self._log_action(f"{log_prefix_runtime} Finished: '{code_string}'. Variables updated.")
                    return None
                elif callback_type == "condition":
                    result = eval(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict) 
                    simulator_self._log_action(f"{log_prefix_runtime} Result of '{code_string}': {result}")
                    return bool(result)
            except Exception as e: 
                err_type_name = type(e).__name__
                err_detail = str(e)
                if isinstance(e, SyntaxError): err_detail = f"{e.msg} (line {e.lineno}, offset {e.offset})"
                
                err_msg = (f"{err_type_name} in {callback_type} '{original_name}' (state context: {current_state_for_log}): "
                           f"{err_detail}. Code: '{code_string}'")
                simulator_self._log_action(f"[Code Error] {err_msg}")
                log_level = logging.ERROR if isinstance(e, (SyntaxError, TypeError, ZeroDivisionError)) else logging.WARNING
                logger.log(log_level, f"{simulator_self.log_prefix}{err_msg}", exc_info=isinstance(e, (TypeError, AttributeError, IndexError, KeyError, ValueError, ZeroDivisionError)))
                
                if callback_type == "condition": return False
                if simulator_self._halt_simulation_on_action_error and callback_type == "action": 
                    simulator_self.simulation_halted_flag = True
                    raise FSMError(err_msg) 
            return None
        dynamic_callback_wrapper.__name__ = f"{original_name}_{callback_type}_{hash(code_string)}"
        return dynamic_callback_wrapper

    def _master_on_enter_state_impl(self, sm_instance, target, **kwargs): # sm_instance is StateMachine, target is State
        target_state_name = target.id
        self._log_action(f"Entering state: {target_state_name}")

        if target_state_name in self.breakpoints["states"]:
            self._log_action(f"BREAKPOINT HIT on entering state: {target_state_name}")
            self.breakpoint_hit_flag = True 
            return 

        if target_state_name in self._states_input_data:
            state_def = self._states_input_data[target_state_name]
            if state_def.get('is_superstate', False) and state_def.get('sub_fsm_data'):
                sub_fsm_states = state_def['sub_fsm_data'].get('states', [])
                sub_fsm_transitions = state_def['sub_fsm_data'].get('transitions', [])
                if sub_fsm_states: # Only create sub-machine if it has states
                    self._log_action(f"Creating sub-machine for superstate '{target_state_name}'")
                    try:
                        self.active_sub_simulator = StateMachinePoweredSimulator(
                            sub_fsm_states, sub_fsm_transitions,
                            parent_simulator=self,
                            log_prefix=f"{self.log_prefix}  [Sub-{target_state_name}] ",
                            halt_on_action_error=self._halt_simulation_on_action_error
                        )
                        self.active_superstate_name = target_state_name
                        if self.active_sub_simulator.sm and self.active_sub_simulator.sm.current_state:
                             self._log_action(f"Sub-machine for '{target_state_name}' initialized. Current sub-state: {self.active_sub_simulator.sm.current_state.id}")
                             self._action_log.extend(self.active_sub_simulator.get_last_executed_actions_log()) # Collect initial sub-log
                        else:
                             self._log_action(f"Sub-machine for '{target_state_name}' created but has no active state (e.g., no initial sub-state).")
                    except FSMError as e_sub:
                        err_msg = f"Failed to initialize sub-machine for '{target_state_name}': {e_sub}"
                        self._log_action(f"[Error] {err_msg}")
                        logger.error(f"{self.log_prefix}{err_msg}", exc_info=True)
                        if self._halt_simulation_on_action_error: self.simulation_halted_flag = True; raise FSMError(err_msg) from e_sub
                    except Exception as e_sub_unexp:
                        err_msg = f"Unexpected error initializing sub-machine for '{target_state_name}': {e_sub_unexp}"
                        self._log_action(f"[Error] {err_msg}")
                        logger.error(f"{self.log_prefix}{err_msg}", exc_info=True)
                        if self._halt_simulation_on_action_error: self.simulation_halted_flag = True; raise FSMError(err_msg) from e_sub_unexp


    def _master_on_exit_state_impl(self, sm_instance, source, **kwargs): # sm_instance is StateMachine, source is State
        source_state_name = source.id
        self._log_action(f"Exiting state: {source_state_name}")
        if self.active_sub_simulator and self.active_superstate_name == source_state_name:
            self._log_action(f"Destroying sub-machine for superstate '{source_state_name}'")
            # Any cleanup for the sub-machine if needed, e.g., final exit actions if not handled by python-statemachine
            self._action_log.extend(self.active_sub_simulator.get_last_executed_actions_log()) # Get any final logs
            self.active_sub_simulator = None
            self.active_superstate_name = None


    def _sm_before_transition_impl(self, sm_instance, event: str, source, target, **kwargs):
        event_data_obj = kwargs.get('event_data')
        triggered_event_name = event_data_obj.event if event_data_obj else event
        self._log_action(f"Before transition on '{triggered_event_name}' from '{source.id}' to '{target.id}'")
        
    def _sm_after_transition_impl(self, sm_instance, event: str, source, target, **kwargs):
        event_data_obj = kwargs.get('event_data')
        triggered_event_name = event_data_obj.event if event_data_obj else event
        self._log_action(f"After transition on '{triggered_event_name}' from '{source.id}' to '{target.id}'")

    def _build_fsm_class_and_instance(self):
        if not self._states_input_data:
            logger.warning(f"{self.log_prefix}No states defined. FSM class not built.")
            self.FSMClass = None; self.sm = None
            return

        # Dynamically create the FSM class
        fsm_class_name = f"DynamicFSM_{self.log_prefix.replace(' ', '').replace('[','').replace(']','').replace('-','')}_{hash(str(self._states_input_data))}"
        
        # Create State objects for python-statemachine
        sm_states = []
        for s_name, s_data in self._states_input_data.items():
            state_params = {
                'name': s_name,
                'value': s_data.get('value', s_name), # Use name as value if not specified
                'initial': s_data.get('is_initial', False)
            }
            if s_data.get('entry_action'):
                state_params['enter'] = self._create_dynamic_callback(s_data['entry_action'], "action", f"entry_{s_name}")
            if s_data.get('exit_action'):
                state_params['exit'] = self._create_dynamic_callback(s_data['exit_action'], "action", f"exit_{s_name}")
            
            sm_state = self.StateMachineModule_State(**state_params)
            setattr(sm_state, "_original_during_action_code", s_data.get('during_action', '')) # Store for step()
            setattr(sm_state, "_original_is_superstate", s_data.get('is_superstate', False)) # Store for enter hook
            setattr(sm_state, "_original_sub_fsm_data", s_data.get('sub_fsm_data')) # Store for enter hook

            sm_states.append(sm_state)
            if state_params['initial']:
                self._initial_state_name = s_name

        if not self._initial_state_name and sm_states: # Default to first if none marked initial
             first_state = sm_states[0]
             first_state.initial = True # This attribute might be direct or a setter
             self._initial_state_name = first_state.id
             logger.warning(f"{self.log_prefix}No initial state found, defaulting to first state: {self._initial_state_name}")
        elif not sm_states:
             logger.error(f"{self.log_prefix}Cannot build FSM: No states defined to create State objects.")
             self.FSMClass = None; self.sm = None; return


        # Prepare class attributes for StateMachine
        fsm_attrs = {s.id: s for s in sm_states}
        fsm_attrs['__qualname__'] = fsm_class_name # Helps with qualname generation for events/states

        # Create transitions and events
        for t_data in self._transitions_input_data:
            src_state_name = t_data['source']
            tgt_state_name = t_data['target']
            event_name = t_data.get('event')

            if not event_name: continue # Skip eventless transitions for explicit event setup

            src_state_obj = fsm_attrs.get(src_state_name)
            tgt_state_obj = fsm_attrs.get(tgt_state_name)

            if not src_state_obj or not tgt_state_obj:
                logger.warning(f"{self.log_prefix}Skipping transition: source '{src_state_name}' or target '{tgt_state_name}' not found in FSM states.")
                continue
            
            transition_actions = {}
            if t_data.get('action'):
                action_name = f"action_{src_state_name}_to_{tgt_state_name}_{event_name}".replace(" ","_")
                transition_actions['on'] = self._create_dynamic_callback(t_data['action'], "action", action_name)
            
            if t_data.get('condition'):
                cond_name = f"cond_{src_state_name}_to_{tgt_state_name}_{event_name}".replace(" ","_")
                transition_actions['cond'] = self._create_dynamic_callback(t_data['condition'], "condition", cond_name)

            # Create or get existing event, then add transition to it
            if event_name not in fsm_attrs:
                fsm_attrs[event_name] = src_state_obj.to(tgt_state_obj, event=event_name, **transition_actions)
            else:
                # Event already exists, add this transition path to it
                # python-statemachine's event object (created by .to()) can be OR-ed (|)
                fsm_attrs[event_name] |= src_state_obj.to(tgt_state_obj, event=event_name, **transition_actions)
        
        # Add master enter/exit/before/after for all states/transitions
        fsm_attrs['on_enter_state'] = self._master_on_enter_state_impl
        fsm_attrs['on_exit_state'] = self._master_on_exit_state_impl
        fsm_attrs['before_transition'] = self._sm_before_transition_impl
        fsm_attrs['after_transition'] = self._sm_after_transition_impl


        self.FSMClass = type(fsm_class_name, (self.StateMachineModule_StateMachine,), fsm_attrs)
        
        if self.FSMClass:
            try:
                # allow_event_without_transition=True helps if events are triggered that
                # don't have a defined transition from current state, or for sub-machine event propagation.
                self.sm = self.FSMClass(model=self._variables, allow_event_without_transition=True)
            except self.StateMachineModule_InvalidDefinition as e:
                logger.error(f"{self.log_prefix}Invalid FSM definition during SM instantiation: {e}", exc_info=True)
                raise FSMError(f"Invalid FSM Definition: {e}") from e
            except Exception as e_inst:
                logger.error(f"{self.log_prefix}Unexpected error during SM instantiation: {e_inst}", exc_info=True)
                raise FSMError(f"SM Instantiation Error: {e_inst}") from e_inst

    def reset(self):
        self._log_action("--- FSM Resetting ---")
        self._variables.clear()
        self.simulation_halted_flag = False
        self.current_tick = 0
        self.breakpoint_hit_flag = False
        self.paused_on_breakpoint = False
        
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
                self._action_log.extend(self.get_last_executed_actions_log()) # Get initial state entry log
            except Exception as e:
                logger.error(f"{self.log_prefix}Reset failed during SM re-instantiation: {e}", exc_info=True)
                raise FSMError(f"Reset failed during SM re-instantiation: {e}")
        elif not self.parent_simulator and not self._states_input_data : 
            logger.error(f"{self.log_prefix}FSM Class not built (no states defined), cannot reset properly.")

    def step(self, event_name=None):
        if self.simulation_halted_flag:
            self._log_action(f"Simulation HALTED. Event '{event_name or 'Internal (Tick)'}' ignored. Reset required.")
            return self.get_current_state_name(), self.get_last_executed_actions_log()

        if self.paused_on_breakpoint:
            self._log_action(f"Simulation PAUSED at breakpoint. Current state: {self.get_current_state_name()}. Event '{event_name or 'None'}' ignored. Use 'Continue'.")
            return self.get_current_state_name(), self.get_last_executed_actions_log()

        if not self.sm: 
            if not self.parent_simulator: # Top-level FSM is uninitialized
                 err_msg = "FSM not initialized. Cannot step."
                 self._log_action(f"[Error] {err_msg}")
                 logger.error(f"{self.log_prefix}{err_msg}")
                 return "Uninitialized", self.get_last_executed_actions_log()
            else: # This is a sub-simulator that might be validly empty
                 self._log_action("Sub-FSM is empty or uninitialized, no step taken.")
                 return "EmptySubFSM", self.get_last_executed_actions_log()


        self.current_tick += 1
        main_state_id = self.sm.current_state.id if self.sm and self.sm.current_state else "Uninitialized"
        self._log_action(f"--- Step. State: {self.get_current_state_name()}. Event: {event_name or 'Internal (Tick)'} ---")
        
        if self.breakpoint_hit_flag:
            self.paused_on_breakpoint = True
            self.breakpoint_hit_flag = False 
            self._log_action(f"Simulation PAUSED at breakpoint. Current state: {self.get_current_state_name()}")
            return self.get_current_state_name(), self.get_last_executed_actions_log()

        try:
            main_state_obj = self.sm.current_state if self.sm and self.sm.current_state else None
            if main_state_obj and hasattr(main_state_obj, '_original_during_action_code'):
                action_str = getattr(main_state_obj, '_original_during_action_code', '')
                if action_str:
                    self._log_action(f"During action for '{main_state_id}': {action_str}")
                    during_cb = self._create_dynamic_callback(action_str, "action", f"during_{main_state_id}")
                    during_cb(self.sm) # Pass the StateMachine instance

            if self.simulation_halted_flag: return self.get_current_state_name(), self.get_last_executed_actions_log()
            if self.breakpoint_hit_flag: 
                self.paused_on_breakpoint = True; self.breakpoint_hit_flag = False
                self._log_action(f"Simulation PAUSED at breakpoint (hit during pre-step hook). Current state: {self.get_current_state_name()}")
                return self.get_current_state_name(), self.get_last_executed_actions_log()


            if self.active_sub_simulator:
                superstate_log_name = self.active_superstate_name or main_state_id
                self._log_action(f"Stepping sub-machine in '{superstate_log_name}' with event: {event_name or 'None (Internal)'}.")
                _, sub_log = self.active_sub_simulator.step(event_name=event_name) 
                self._action_log.extend(sub_log) 
                if self.active_sub_simulator.simulation_halted_flag:
                    self.simulation_halted_flag = True
                    self._log_action(f"Propagation: Parent HALTED due to sub-machine error in '{superstate_log_name}'."); return self.get_current_state_name(), self.get_last_executed_actions_log()
                if self.active_sub_simulator.paused_on_breakpoint: 
                    self.paused_on_breakpoint = True 
                    self._log_action(f"Propagation: Parent PAUSED because sub-machine in '{superstate_log_name}' hit a breakpoint.")
                    return self.get_current_state_name(), self.get_last_executed_actions_log()

                sub_sm_instance = self.active_sub_simulator.sm
                if sub_sm_instance and sub_sm_instance.current_state and sub_sm_instance.current_state.final:
                    self._log_action(f"Sub-machine in '{superstate_log_name}' reached final state: '{sub_sm_instance.current_state.id}'.")
                    if self.active_superstate_name: 
                         self._variables[f"{self.active_superstate_name}_sub_completed"] = True
                         self._log_action(f"Variable '{self.active_superstate_name}_sub_completed' set to True in parent FSM.")
            
            if self.simulation_halted_flag: return self.get_current_state_name(), self.get_last_executed_actions_log()
            if self.breakpoint_hit_flag: 
                self.paused_on_breakpoint = True; self.breakpoint_hit_flag = False
                self._log_action(f"Simulation PAUSED at breakpoint (hit during pre-step hook). Current state: {self.get_current_state_name()}")
                return self.get_current_state_name(), self.get_last_executed_actions_log()

            if event_name:
                self._log_action(f"Sending event '{event_name}' to FSM (current level: {'parent' if self.active_sub_simulator else 'main'}).")
                self.sm.send(event_name)
            elif not self.active_sub_simulator: 
                 self._log_action(f"No event. 'During' actions done. State remains '{main_state_id}'.")
            
            if self.breakpoint_hit_flag:
                self.paused_on_breakpoint = True; self.breakpoint_hit_flag = False
                self._log_action(f"Simulation PAUSED at breakpoint (hit during/after event processing). Current state: {self.get_current_state_name()}")

        except FSMError as e_halt: 
            if self.simulation_halted_flag or "HALTED due to error" in str(e_halt):
                self._log_action(f"[SIMULATION HALTED internally] {e_halt}"); self.simulation_halted_flag = True
            else: self._log_action(f"FSM Logic Error during step: {e_halt}"); logger.error(f"{self.log_prefix}FSM Logic Error:", exc_info=True)
        except self.StateMachineModule_TransitionNotAllowed: self._log_action(f"Event '{event_name}' not allowed or no transition from '{main_state_id}'.")
        except AttributeError as e: 
            log_msg = f"AttributeError during step (event: '{event_name}')."
            if event_name and hasattr(self.sm, event_name) and not callable(getattr(self.sm, event_name)):
                log_msg = f"Event name '{event_name}' conflicts with state or non-event attribute."
            elif event_name and hasattr(self.sm, event_name) and callable(getattr(self.sm, event_name)): 
                log_msg = f"AttributeError processing event '{event_name}': {e}. Internal setup/callback issue?"
            self._log_action(log_msg); logger.error(f"{self.log_prefix}AttributeError for '{event_name}': {e}", exc_info=True)
        except Exception as e: self._log_action(f"Unexpected error on event '{event_name}': {type(e).__name__} - {e}"); logger.error(f"{self.log_prefix}Event processing error:", exc_info=True)

        return self.get_current_state_name(), self.get_last_executed_actions_log()

    def add_state_breakpoint(self, state_name: str):
        self.breakpoints["states"].add(state_name)
        self._log_action(f"Breakpoint ADDED for state entry: {state_name}")

    def remove_state_breakpoint(self, state_name: str):
        if state_name in self.breakpoints["states"]:
            self.breakpoints["states"].remove(state_name)
            self._log_action(f"Breakpoint REMOVED for state entry: {state_name}")

    def continue_simulation(self) -> bool:
        if self.paused_on_breakpoint:
            self._log_action("Continuing simulation from breakpoint...")
            self.paused_on_breakpoint = False
            self.breakpoint_hit_flag = False 
            return True
        self._log_action("Continue called, but not paused at a breakpoint.")
        return False

    def get_current_state_name(self):
        if not self.sm: return "Uninitialized" if not self.parent_simulator else "EmptySubFSM"
        name = self.sm.current_state.id if self.sm and self.sm.current_state else "Unknown"
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

    def get_possible_events_from_current_state(self) -> list[str]:
        if not self.sm or not self.sm.current_state: return []
        
        possible_events_set = set()
        current_sm_to_query = self.sm 
        
        if self.active_sub_simulator and self.active_sub_simulator.sm:
            current_sm_to_query = self.active_sub_simulator.sm
        
        if current_sm_to_query and current_sm_to_query.current_state:
            possible_events_set.update(str(evt.id) for evt in current_sm_to_query.allowed_events)
        
        if self.active_sub_simulator and self.sm and self.sm.current_state:
             possible_events_set.update(str(evt.id) for evt in self.sm.allowed_events)

        return sorted(list(filter(None, possible_events_set))) 


FSMSimulator = StateMachinePoweredSimulator

if __name__ == "__main__":
    if not logger.hasHandlers() or not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler()
        LOGGING_DATE_FORMAT = "%H:%M:%S"
        formatter = logging.Formatter(
            "--- FSM_SIM (%(asctime)s.%(msecs)03d) [%(levelname)s]: %(message)s",
            datefmt=LOGGING_DATE_FORMAT
        )
        console_handler.setFormatter(formatter)
        if not logging.getLogger().hasHandlers():
            logger.addHandler(console_handler)
            logger.setLevel(logging.INFO) 
        else: 
            logger.setLevel(logging.INFO)

    logger.info("Running fsm_simulator.py directly for testing...")
    main_states_data = [
        {"name": "Idle", "is_initial": True, 
         "entry_action": "print('Main: Idle Entered'); idle_counter = 0; Processing_sub_completed = False; my_timer_start_tick = current_tick",
         "during_action": "print(f'Idle during action at tick {current_tick}')"
        },
        {"name": "Processing", "is_superstate": True,
         "sub_fsm_data": {
             "states": [
                 {"name": "SubIdle", "is_initial": True, "entry_action": "print('Sub: SubIdle Entered'); sub_var = 10"},
                 {"name": "SubActive", "during_action": "sub_var = sub_var + 1; print(f'Sub: SubActive during, sub_var is {sub_var}, sub_tick is {current_tick}')"},
                 {"name": "SubDone", "is_final": True, "entry_action": "print('Sub: SubDone Entered (final)')"}
             ],
             "transitions": [
                 {"source": "SubIdle", "target": "SubActive", "event": "start_sub_work"},
                 {"source": "SubActive", "target": "SubDone", "event": "finish_sub_work", "condition": "sub_var > 11"}
             ],
             "comments": []
         },
         "entry_action": "print('Main: Processing Superstate Entered')",
         "during_action": "print(f'Main: Processing Superstate During, idle_counter is {idle_counter}, main_tick is {current_tick}'); idle_counter = idle_counter + 1",
         "exit_action": "print('Main: Processing Superstate Exited')"
        },
        {"name": "Done", "is_final": True, "entry_action": "print('Main: Done Entered')"}
    ]
    main_transitions_data = [
        {"source": "Idle", "target": "Processing", "event": "start_processing", "condition": "current_tick >= my_timer_start_tick + 3"}, 
        {"source": "Processing", "target": "Done", "event": "auto_finish", "condition": "Processing_sub_completed == True and idle_counter > 1"}
    ]

    print("--- HIERARCHICAL SIMULATOR TEST (python-statemachine with Ticks & Breakpoints) ---")
    try:
        simulator = FSMSimulator(main_states_data, main_transitions_data, halt_on_action_error=False)

        def print_status(sim, step_name=""):
            print(f"\n--- {step_name} (Tick: {sim.current_tick}) ---")
            print(f"Current State: {sim.get_current_state_name()}")
            print(f"Leaf State: {sim.get_current_leaf_state_name()}")
            print(f"Main Vars: {sim.get_variables()}")
            if sim.active_sub_simulator: print(f"Sub Vars: {sim.active_sub_simulator.get_variables()}, Sub Tick: {sim.active_sub_simulator.current_tick}")
            log = sim.get_last_executed_actions_log()
            if log: print("Log:"); [print(f"  {entry}") for entry in log]
            print("Possible events:", sim.get_possible_events_from_current_state())
            print(f"Paused on BP: {sim.paused_on_breakpoint}, BP Hit Flag: {sim.breakpoint_hit_flag}")
            print("--------------------")


        print_status(simulator, "INITIAL STATE") 
        
        simulator.add_state_breakpoint("Processing") 

        simulator.step(None); print_status(simulator, "AFTER main internal step 1 (Idle during)") 
        simulator.step(None); print_status(simulator, "AFTER main internal step 2 (Idle during)") 
        
        simulator.step("start_processing"); print_status(simulator, "AFTER 'start_processing' (should be paused)") 
        
        if simulator.paused_on_breakpoint:
            simulator.continue_simulation()
            print_status(simulator, "AFTER Continue from BP on Processing")
            simulator.step(None) 
            print_status(simulator, "AFTER internal step in Processing (after continue)")


        if simulator.active_sub_simulator:
            simulator.add_state_breakpoint("SubActive") 
            simulator.step("start_sub_work") 
            print_status(simulator, "AFTER sub-event 'start_sub_work' (should be paused in SubActive)")
            if simulator.paused_on_breakpoint: 
                simulator.continue_simulation()
                print_status(simulator, "AFTER Continue from BP on SubActive")
                simulator.step(None) 
                print_status(simulator, "AFTER internal step in SubActive")


        simulator.step(None); print_status(simulator, "AFTER main internal step ") 
        simulator.step(None); print_status(simulator, "AFTER main internal step ") 
        
        if simulator.active_sub_simulator:
            simulator.step("finish_sub_work")
            print_status(simulator, "AFTER sub-event 'finish_sub_work'")
        
        simulator.step("auto_finish"); print_status(simulator, "AFTER 'auto_finish'")

    except FSMError as e: print(f"FSM Error: {e}")
    except Exception as e: print(f"An unexpected error occurred: {e}"); import traceback; traceback.print_exc()