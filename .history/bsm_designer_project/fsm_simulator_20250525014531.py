# bsm_designer_project/fsm_simulator.py

print("fsm_simulator.py is being imported with python-statemachine integration AND HIERARCHY AWARENESS!")

from statemachine import StateMachine, State
from statemachine.exceptions import TransitionNotAllowed
from statemachine.event import Event as SMEvent
from statemachine.transition_list import TransitionList as SMTransitionList # Not directly used here, but good to know
from functools import partial
import logging
import time
import ast

# Configure logging for this module specifically if not relying on root logger
# This basicConfig will be overridden if setup_global_logging runs later and configures the root logger.
# If you want this module to always have this specific format, use a named logger.
logger = logging.getLogger(__name__) # Use a named logger
if not logger.hasHandlers(): # Avoid adding multiple handlers if imported multiple times or root is configured
    LOGGING_DATE_FORMAT = "%H:%M:%S"
    handler = logging.StreamHandler() # Default to console output
    formatter = logging.Formatter("--- FSM_SIM (%(asctime)s.%(msecs)03d): %(message)s", datefmt=LOGGING_DATE_FORMAT)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO) # Default level for this logger


# --- START: AST Safety Checker ---
class BasicSafetyVisitor(ast.NodeVisitor):
    def __init__(self, allowed_variable_names=None):
        self.violations = []
        self.allowed_call_names = {'print', 'len', 'abs', 'min', 'max', 'int', 'float', 'str', 'bool', 'round'}
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
        if isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec', 'compile', 'open', 'input', 'getattr', 'setattr', 'delattr'):
            self.violations.append(f"SecurityError: Calling '{node.func.id}' is not allowed.")
        super().generic_visit(node)

    def visit_Attribute(self, node):
        # Stricter dunder attribute check
        if isinstance(node.attr, str) and node.attr.startswith('__') and node.attr.endswith('__'):
            # Blacklist particularly dangerous dunders
            dangerous_dunders = {'__globals__', '__builtins__', '__code__', '__closure__', 
                                 '__self__', '__class__', '__bases__', '__subclasses__', '__mro__',
                                 '__init__', '__new__', '__del__', '__dict__', 
                                 '__getattribute__', '__setattr__', '__delattr__'} # and more
            if node.attr in dangerous_dunders and node.attr not in self.allowed_dunder_attrs:
                 self.violations.append(f"SecurityError: Access to special attribute '{node.attr}' is restricted.")
        elif isinstance(node.attr, str) and node.attr in ('f_locals', 'f_globals', 'f_builtins', 'f_code'): # Frame attributes
            self.violations.append(f"SecurityError: Access to frame attribute '{node.attr}' is restricted.")

        super().generic_visit(node)

    def visit_Exec(self, node):
        self.violations.append("SecurityError: 'exec' statement is not allowed.")
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
}
# --- END: AST Safety Checker ---


class FSMError(Exception):
    pass

class StateMachinePoweredSimulator:
    def __init__(self, states_data, transitions_data, parent_simulator=None, log_prefix=""):
        self._states_input_data = {s['name']: s for s in states_data}
        self._transitions_input_data = transitions_data
        self._variables = {}
        self._action_log = []
        self.FSMClass = None
        self.sm = None
        self._initial_state_name = None
        self.parent_simulator: StateMachinePoweredSimulator | None = parent_simulator
        self.log_prefix = log_prefix # Prefix for logs (e.g., "  [SUB] ")

        self.active_sub_simulator: StateMachinePoweredSimulator | None = None
        self.active_superstate_name: str | None = None

        try:
            self._build_fsm_class_and_instance()
            if self.sm and self.sm.current_state:
                self._log_action(f"FSM Initialized. Current state: {self.sm.current_state.id}")
            elif not self._states_input_data:
                raise FSMError("No states defined in the FSM.")
            else:
                raise FSMError("FSM Initialization failed: Could not determine current state after build.")
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
                    self._log_action(f"[Condition Blocked] Unsafe code: '{code_string}' evaluated as False.")
                    return False
                unsafe_condition_wrapper.__name__ = f"{original_name}_blocked_condition"
                return unsafe_condition_wrapper
            else:
                def unsafe_action_wrapper(*args, **kwargs):
                    self._log_action(f"[Action Blocked] Unsafe code ignored: '{code_string}'.")
                unsafe_action_wrapper.__name__ = f"{original_name}_blocked_action"
                return unsafe_action_wrapper

        def dynamic_callback_wrapper(*args, **kwargs):
            exec_eval_locals_dict = self._variables
            log_prefix = "[Action]" if callback_type == "action" else "[Condition]"
            self._log_action(f"{log_prefix} Executing: '{code_string}' with variables: {exec_eval_locals_dict}")
            try:
                if callback_type == "action":
                    exec(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict)
                    self._log_action(f"{log_prefix} Finished: '{code_string}'. Variables now: {exec_eval_locals_dict}")
                    return None
                elif callback_type == "condition":
                    result = eval(code_string, {"__builtins__": SAFE_BUILTINS}, exec_eval_locals_dict)
                    self._log_action(f"{log_prefix} Result of '{code_string}': {result}")
                    return bool(result)
            except SyntaxError as e:
                err_msg = f"SyntaxError in {callback_type} '{code_string}': {e.msg} (line {e.lineno}, offset {e.offset})"
                self._log_action(f"[Eval Error] {err_msg}")
                if callback_type == "condition": return False
            except NameError as e:
                err_msg = f"NameError in {callback_type} '{code_string}': {e}. Check variable or allowed builtins."
                self._log_action(f"[Eval Error] {err_msg}")
                if callback_type == "condition": return False
            except Exception as e:
                err_msg = f"Unexpected error in {callback_type} '{code_string}': {type(e).__name__} - {e}"
                self._log_action(f"[Eval Error] {err_msg}", level_prefix_override=f"{self.log_prefix}[ERR] ")
                logger.error(f"{self.log_prefix}Callback execution error for '{code_string}':", exc_info=True)
                if callback_type == "condition": return False
            return None
        dynamic_callback_wrapper.__name__ = f"{original_name}_{callback_type}_{hash(code_string)}"
        return dynamic_callback_wrapper

    def _master_on_enter_state(self, target: State, event_data, machine, **kwargs):
        target_state_name = target.id
        self._log_action(f"Entering state: {target_state_name}")

        # Deactivate previous sub-simulator if we were in a different superstate
        # This is generally handled by _master_on_exit_state of the source superstate.

        # Activate new sub-simulator if target is a superstate
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
                            log_prefix=self.log_prefix + "  [SUB] " # Indent sub-machine logs
                        )
                        self.active_superstate_name = target_state_name
                        for sub_log_entry in self.active_sub_simulator.get_last_executed_actions_log():
                            self._action_log.append(sub_log_entry) # Already prefixed by sub-simulator
                    except Exception as e:
                        self._log_action(f"ERROR initializing sub-machine for '{target_state_name}': {e}")
                        logger.error(f"{self.log_prefix}Sub-machine init error for '{target_state_name}':", exc_info=True)
                        self.active_sub_simulator = None
                        self.active_superstate_name = None
                else:
                    self._log_action(f"Superstate '{target_state_name}' has no defined sub-machine data.")


        # Execute the main state's entry action (if any)
        entry_action_code = self._states_input_data.get(target_state_name, {}).get('entry_action')
        if entry_action_code:
            entry_action_cb = self._create_dynamic_callback(
                entry_action_code, "action", original_name=f"on_enter_{target_state_name}"
            )
            entry_action_cb()

    def _master_on_exit_state(self, source: State, event_data, machine, **kwargs):
        source_state_name = source.id
        self._log_action(f"Exiting state: {source_state_name}")

        # Execute the main state's exit action (if any)
        exit_action_code = self._states_input_data.get(source_state_name, {}).get('exit_action')
        if exit_action_code:
            exit_action_cb = self._create_dynamic_callback(
                exit_action_code, "action", original_name=f"on_exit_{source_state_name}"
            )
            exit_action_cb()

        # Deactivate sub-simulator if we are exiting its superstate
        if self.active_sub_simulator and self.active_superstate_name == source_state_name:
            self._log_action(f"Superstate '{source_state_name}' exited. Terminating its sub-machine.")
            # Get final logs from sub-machine if any meaningful termination actions were performed
            # For now, just clear it.
            self.active_sub_simulator = None
            self.active_superstate_name = None

    def _sm_before_transition(self, event: str, source: State, target: State, event_data, machine, **kwargs):
        self._log_action(f"Before transition on '{event_data.event}' from '{source.id}' to '{target.id}'")

    def _sm_after_transition(self, event: str, source: State, target: State, event_data, machine, **kwargs):
        self._log_action(f"After transition on '{event_data.event}' from '{source.id}' to '{target.id}'")


    def _build_fsm_class_and_instance(self):
        # Add a helper method to check for states without outgoing transitions
        def has_outgoing_transitions(state_name: str) -> bool:
            return any(t['source'] == state_name for t in self._transitions_input_data)

        # Add validation before creating FSM class
        states_without_transitions = []
        for state_name, state_data in self._states_input_data.items():
            if not state_data.get('is_final', False) and not has_outgoing_transitions(state_name):
                states_without_transitions.append(state_name)
    
        if states_without_transitions:
            self._log_action(f"Warning: Non-final states without outgoing transitions: {states_without_transitions}")
        fsm_class_attrs = {}
        sm_states_obj_map = {}
        initial_state_found_in_data = False

        for s_name, s_data in self._states_input_data.items():
            is_initial = s_data.get('is_initial', False)
            if is_initial:
                self._initial_state_name = s_name
                initial_state_found_in_data = True
            
            # Note: Entry/Exit actions are handled by _master_on_enter/exit_state now for hierarchy
            # So, we don't directly pass them to the State object here if we use generic hooks.
            # However, python-statemachine can also call on_enter_<statename> methods.
            # For simplicity with our hierarchical model, we'll rely on the generic hooks.
            state_obj = State(
                name=s_name,
                value=s_name, # Use name as value
                initial=is_initial,
                final=s_data.get('is_final', False)
                # `enter` and `exit` callbacks are now managed by _master_on_enter/exit_state
            )
            fsm_class_attrs[s_name] = state_obj
            sm_states_obj_map[s_name] = state_obj

        if not initial_state_found_in_data and self._states_input_data:
            first_state_name_from_data = next(iter(self._states_input_data)) # Fallback
            if first_state_name_from_data in sm_states_obj_map:
                self._log_action(f"No initial state explicitly defined. Using first state '{first_state_name_from_data}' as initial.")
                sm_states_obj_map[first_state_name_from_data]._initial = True # type: ignore
                self._initial_state_name = first_state_name_from_data
            else:
                raise FSMError("Error setting fallback initial state: First state not found in map.")
        elif not self._states_input_data:
            if not self.parent_simulator: # Only raise if it's the top-level FSM
                raise FSMError("No states defined in the FSM.")
            else: # Sub-FSM can be empty if not defined
                self._log_action("Sub-FSM has no states defined. It will be inactive.")
                return # Cannot build SM class for an empty sub-FSM

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
            
            # Use the `python-statemachine` way to define transitions on state objects
            _ = source_state_obj.to(target_state_obj, event=event_name, cond=conditions or None, on=actions or None) # type: ignore


        # Add generic hooks for state entry/exit and transitions
        fsm_class_attrs["on_enter_state"] = self._master_on_enter_state
        fsm_class_attrs["on_exit_state"] = self._master_on_exit_state
        fsm_class_attrs["before_transition"] = self._sm_before_transition
        fsm_class_attrs["after_transition"] = self._sm_after_transition

        try:
            self.FSMClass = type(f"DynamicBSMFSM_{self.log_prefix.replace(' ', '')}_{id(self)}", (StateMachine,), fsm_class_attrs)
            self.sm = self.FSMClass(model=self._variables) # type: ignore Pass model for variable access if needed
        except Exception as e:
            logger.error(f"{self.log_prefix}Failed to create StateMachine class/instance: {e}", exc_info=True)
            raise FSMError(f"StateMachine creation failed: {e}")

    def get_current_state_name(self):
        if not self.sm:
            logger.error(f"{self.log_prefix}Cannot get current state: FSM not initialized.")
            return None
        current_state_name = self.sm.current_state.id
        if self.active_sub_simulator:
            sub_state_name = self.active_sub_simulator.get_current_state_name()
            return f"{current_state_name} ({sub_state_name})" # e.g. SuperStateA (SubStateX)
        return current_state_name
    
    def get_current_leaf_state_name(self):
        """Gets the name of the most deeply nested active state."""
        if self.active_sub_simulator:
            return self.active_sub_simulator.get_current_leaf_state_name()
        elif self.sm and self.sm.current_state:
            return self.sm.current_state.id
        return None
    
    
    def is_in_final_state(self) -> bool:
        
        if not self.sm or not self.sm.current_state:
            return False
    
        
        if self.sm.current_state.final:
            return True
        
        
        if self.active_sub_simulator:
            return self.active_sub_simulator.is_in_final_state()
    
        return False
    
    
    
    def get_all_variables(self) -> dict:
        
        variables = self._variables.copy()
        if self.active_sub_simulator:
            sub_vars = self.active_sub_simulator.get_variables()
            variables.update({f"sub_{k}": v for k, v in sub_vars.items()})
        return variables
    
    
    
    def _validate_transitions(self) -> list[str]:
        
        issues = []
        state_names = set(self._states_input_data.keys())
    
        for trans in self._transitions_input_data:
            source = trans.get('source')
            target = trans.get('target')
            event = trans.get('event')
        
            if not source or source not in state_names:
                issues.append(f"Invalid source state '{source}' in transition")
            if not target or target not in state_names:
                issues.append(f"Invalid target state '{target}' in transition")
            if not event:
                issues.append(f"Missing event in transition {source}->{target}")
            
        return issues
    
    
    
    def _execute_action_safely(self, action_code: str, context: str) -> bool:
        """Execute an action with additional error handling and logging."""
        try:
            temp_cb = self._create_dynamic_callback(action_code, "action", f"{context}_action")
            temp_cb()
            return True
        except Exception as e:
            self._log_action(f"Error executing {context} action: {str(e)}", level_prefix_override=f"{self.log_prefix}[ERR] ")
            logger.error(f"{self.log_prefix}{context} action error:", exc_info=True)
            return False
    
    
    
    
    


    def get_variables(self):
        # For now, only returns variables of this FSM level.
        # Could be extended to merge with sub-FSM variables if needed.
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
            self.active_sub_simulator.reset() # Recursively reset
            for sub_log_entry in self.active_sub_simulator.get_last_executed_actions_log():
                 self._action_log.append(sub_log_entry) # Collect logs from sub-reset
            self.active_sub_simulator = None # Clear it, will be re-created on superstate entry
            self.active_superstate_name = None


        if self.FSMClass:
            try:
                self.sm = self.FSMClass(model=self._variables) # type: ignore Re-instantiate
                self._log_action(f"FSM Reset. Current state: {self.sm.current_state.id if self.sm else 'Unknown'}") # type: ignore
            except Exception as e:
                logger.error(f"{self.log_prefix}Reset failed: {e}", exc_info=True)
                raise FSMError(f"FSM Reset failed: {e}")
        else:
            logger.error(f"{self.log_prefix}FSM Class not built, cannot reset.")
            # This might happen if the FSM was empty (e.g. an undefined sub-FSM)
            if not self.parent_simulator: # Only raise if it's top-level
                 raise FSMError("FSM Class not built, cannot reset.")


    def step(self, event_name=None):
        if not self.sm:
            if not self.parent_simulator and not self._states_input_data : # Top-level and truly empty
                 logger.error(f"{self.log_prefix}Cannot step: FSM not initialized (no states).")
                 raise FSMError("Cannot step, FSM is not initialized (no states).")
            elif self.parent_simulator and not self._states_input_data: # Empty sub-fsm
                self._log_action("Cannot step: Sub-FSM is empty/not defined.")
                return None, self.get_last_executed_actions_log() # Return None state, current logs
            else: # Should not happen if constructor succeeded
                 logger.error(f"{self.log_prefix}Cannot step: FSM.sm not initialized.")
                 raise FSMError("Cannot step, FSM.sm is not initialized.")


        current_main_state_id = self.sm.current_state.id
        self._log_action(f"--- Step triggered. Current state: {current_main_state_id}. Event: {event_name or 'None (internal)'} ---")

        # Execute "during" action of the main FSM's current state
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

        # If there's an active sub-simulator, step it (internal step for its during_actions)
        if self.active_sub_simulator:
            superstate_for_log = self.active_superstate_name or current_main_state_id
            self._log_action(f"Processing internal step for active sub-machine in superstate '{superstate_for_log}'.")
            try:
                _, sub_log = self.active_sub_simulator.step(event_name=None)
                for sub_entry in sub_log:
                    self._action_log.append(sub_entry) # Already prefixed

                # Check if sub-machine reached a final state (informational, no automatic transition yet)
                sub_sm_obj = self.active_sub_simulator.sm
                if sub_sm_obj and sub_sm_obj.current_state and sub_sm_obj.current_state.final:
                    self._log_action(f"Sub-machine in '{superstate_for_log}' has reached a final state: '{sub_sm_obj.current_state.id}'.")
                    # Potentially set a variable in the PARENT's scope:
                    # self._variables[f"{self.active_superstate_name}_sub_completed"] = True
            except Exception as e_sub:
                self._log_action(f"Error during sub-machine internal step: {e_sub}")
                logger.error(f"{self.log_prefix}Sub-machine step error:", exc_info=True)

        # Process event for the main FSM
        if event_name:
            try:
                self.sm.send(event_name) # This will trigger on_exit, on_enter hooks
            except TransitionNotAllowed:
                self._log_action(f"Event '{event_name}' is not allowed or did not cause a transition from state '{current_main_state_id}'.")
            except AttributeError as e: # e.g. event not defined on FSM class
                if hasattr(self.sm, event_name) and callable(getattr(self.sm, event_name)):
                    self._log_action(f"AttributeError processing event '{event_name}': {e}. This might be an internal setup issue.")
                else:
                    self._log_action(f"Event '{event_name}' is not defined on the FSM.")
                logger.error(f"{self.log_prefix}AttributeError for event '{event_name}':", exc_info=True)
            except Exception as e:
                self._log_action(f"Unexpected error during event '{event_name}': {type(e).__name__} - {e}")
                logger.error(f"{self.log_prefix}Event processing error:", exc_info=True)
        else:
            if not self.active_sub_simulator: # Only log if no sub-sim was processed (as sub-sim step is already logged)
                 self._log_action(f"No event provided. 'During' actions (if any) executed. State remains '{current_main_state_id}'.")

        return self.get_current_state_name(), self.get_last_executed_actions_log()


    def get_possible_events_from_current_state(self) -> list[str]:
        if not self.sm or not self.sm.current_state:
            logger.warning(f"{self.log_prefix}Cannot get possible events: FSM or current state not available.")
            return []
        
        possible_events = set()
        # Main FSM events
        for transition in self.sm.current_state.transitions:
            for event_obj in transition.events: 
                possible_events.add(str(event_obj.id))
        
        # If a sub-machine is active, its events are generally internal or triggered by parent actions,
        # not directly from the top-level event trigger UI for now.
        # If you want to expose sub-machine events:
        # if self.active_sub_simulator:
        #     sub_events = self.active_sub_simulator.get_possible_events_from_current_state()
        #     for sub_event in sub_events:
        #         possible_events.add(f"[SUB] {sub_event}") # Prefix to distinguish

        return sorted(list(possible_events))

FSMSimulator = StateMachinePoweredSimulator # Alias for external use

if __name__ == "__main__":
    # Define the FSM structure programmatically for testing
    main_states_data = [
        {"name": "Idle", "is_initial": True, "entry_action": "print('Main: Idle Entered'); idle_counter = 0"},
        {"name": "Processing", "is_superstate": True, 
         "sub_fsm_data": {
             "states": [
                 {"name": "SubIdle", "is_initial": True, "entry_action": "print('Sub: SubIdle Entered'); sub_var = 10"},
                 {"name": "SubActive", "during_action": "sub_var = sub_var + 1; print('Sub: SubActive during, sub_var is', sub_var)"}
             ],
             "transitions": [
                 {"source": "SubIdle", "target": "SubActive", "event": "start_sub_work"}
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
        {"source": "Processing", "target": "Done", "event": "finish_processing", "condition": "idle_counter > 2"}
    ]

    print("--- HIERARCHICAL SIMULATOR TEST ---")
    try:
        simulator = FSMSimulator(main_states_data, main_transitions_data)
        
        def print_status(sim, step_name=""):
            print(f"\n--- {step_name} ---")
            print(f"Current State: {sim.get_current_state_name()}")
            # print(f"Leaf State: {sim.get_current_leaf_state_name()}") # Test this if you implement it
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

        # Trigger event for sub-machine (via parent action or direct call for testing)
        if simulator.active_sub_simulator:
            print("\n>>> Manually triggering 'start_sub_work' on sub-machine <<<")
            simulator.active_sub_simulator.step("start_sub_work")
            print_status(simulator, "AFTER sub-event 'start_sub_work'")
        
        simulator.step(None) # Internal step, should run during actions for Main and Sub
        print_status(simulator, "AFTER internal step 1")

        simulator.step(None) # Internal step
        print_status(simulator, "AFTER internal step 2")
        
        simulator.step(None) # Internal step
        print_status(simulator, "AFTER internal step 3 (idle_counter should be 3 now)")

        simulator.step("finish_processing") # Condition idle_counter > 2 should be met
        print_status(simulator, "AFTER 'finish_processing'")

        print("\n>>> Testing Reset <<<")
        simulator.reset()
        print_status(simulator, "AFTER RESET")


    except FSMError as e:
        print(f"FSM Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()