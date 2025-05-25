# bsm_designer_project/fsm_simulator.py
print("fsm_simulator.py is being imported with python-statemachine integration!")

from statemachine import StateMachine, State
from statemachine.exceptions import TransitionNotAllowed # Corrected import
from statemachine.event import Event as SMEvent # Alias to avoid conflict if any
from statemachine.transition_list import TransitionList as SMTransitionList
from functools import partial # update_wrapper is not strictly needed if we assign __name__ directly

class FSMError(Exception):
    pass

class StateMachinePoweredSimulator:
    def __init__(self, states_data, transitions_data):
        self._states_input_data = {s['name']: s for s in states_data} # For easy lookup of original props
        self._transitions_input_data = transitions_data
        
        self._variables = {} # This will be the model for the StateMachine
        self._action_log = []
        
        self.FSMClass = None
        self.sm = None
        self._initial_state_name = None

        self._build_fsm_class_and_instance()
        
        if self.sm and self.sm.current_state:
             self._log_action(f"FSM Initialized. Current state: {self.sm.current_state.id}")
        elif not self._states_input_data:
             raise FSMError("No states defined in the FSM.")
        else:
             raise FSMError("FSM Initialization failed: Could not determine current state after build.")


    def _log_action(self, message):
        self._action_log.append(message)

    def _create_dynamic_callback(self, code_string, callback_type="action", original_name="dynamic_callback"):
        def dynamic_callback_wrapper(*args, **kwargs):
            # model_from_statemachine = kwargs.get('model') # This is the Model object from statemachine
            
            # --- CORRECTED PART ---
            # We need the actual dictionary (self._variables) for exec/eval.
            # The `model` kwarg from python-statemachine might be an object wrapper.
            # Our _variables dictionary IS the intended "model" for the exec/eval context.
            exec_eval_locals_dict = self._variables 
            # --- END CORRECTED PART ---

            log_prefix = "[Action]" if callback_type == "action" else "[Condition]"
            # Log with the actual dictionary that will be used by exec/eval
            self._log_action(f"{log_prefix} Executing: '{code_string}' with variables: {exec_eval_locals_dict}")

            try:
                if callback_type == "action":
                    # Use exec_eval_locals_dict (which is self._variables) here
                    exec(code_string, {"__builtins__": {}}, exec_eval_locals_dict)
                    self._log_action(f"{log_prefix} Finished: '{code_string}'. Variables now: {exec_eval_locals_dict}")
                    return None
                elif callback_type == "condition":
                    # Use exec_eval_locals_dict here
                    result = eval(code_string, {"__builtins__": {}}, exec_eval_locals_dict)
                    self._log_action(f"{log_prefix} Result of '{code_string}': {result}")
                    return bool(result)
            except SyntaxError as e:
                err_msg = f"SyntaxError in {callback_type} '{code_string}': {e.msg} (line {e.lineno}, offset {e.offset})"
                self._log_action(f"[Eval Error] {err_msg}")
                if callback_type == "condition": return False
            except NameError as e:
                err_msg = f"NameError in {callback_type} '{code_string}': {e}. Check if variable is defined."
                self._log_action(f"[Eval Error] {err_msg}")
                if callback_type == "condition": return False
            except Exception as e:
                err_msg = f"Unexpected error in {callback_type} '{code_string}': {type(e).__name__} - {e}"
                self._log_action(f"[Eval Error] {err_msg}")
                if callback_type == "condition": return False
            return None

        dynamic_callback_wrapper.__name__ = f"{original_name}_{callback_type}_{hash(code_string)}"
        return dynamic_callback_wrapper


    # --- Logging callbacks for StateMachine ---
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
        
        # 1. Define State objects
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
                sm_states_obj_map[first_state_name_from_data]._initial = True 
                self._initial_state_name = first_state_name_from_data
            else: 
                 raise FSMError("Error setting fallback initial state: First state not found in map.")
        elif not self._states_input_data:
             raise FSMError("No states defined in the FSM.")

        # 2. Define Event objects and their Transitions
        unique_event_names = set(t.get('event') for t in self._transitions_input_data if t.get('event'))
        
        for t_data in self._transitions_input_data:
            source_name = t_data['source']
            target_name = t_data['target']
            event_name = t_data.get('event')

            if not event_name:
                synthetic_event_name = f"_internal_transition_{source_name}_to_{target_name}"
                self._log_action(f"Warning: Transition {source_name}->{target_name} has no event. Assigning synthetic event: {synthetic_event_name}")
                event_name = synthetic_event_name
                unique_event_names.add(event_name) 

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

            transition_segment = source_state_obj.to(target_state_obj, cond=conditions or None, on=actions or None)
            
            if event_name not in fsm_class_attrs:
                fsm_class_attrs[event_name] = transition_segment
            else:
                if isinstance(fsm_class_attrs[event_name], SMTransitionList):
                    fsm_class_attrs[event_name].add_transitions(transition_segment)
                else: 
                    self._log_action(f"Error: Attribute {event_name} was not a TransitionList when merging.")
                    current_val = fsm_class_attrs[event_name]
                    new_list = SMTransitionList()
                    if isinstance(current_val, SMTransitionList): new_list.add_transitions(current_val)
                    else: new_list.add_transitions(SMTransitionList([current_val])) 
                    new_list.add_transitions(transition_segment)
                    fsm_class_attrs[event_name] = new_list
        
        # 3. Add generic logging methods to the class attributes
        fsm_class_attrs["on_enter_state"] = self._sm_on_enter_state 
        fsm_class_attrs["on_exit_state"] = self._sm_on_exit_state
        fsm_class_attrs["before_transition"] = self._sm_before_transition
        fsm_class_attrs["after_transition"] = self._sm_after_transition
        
        # 4. Create the StateMachine class
        self.FSMClass = type("DynamicBSMFSM", (StateMachine,), fsm_class_attrs)
        
        # 5. Instantiate the StateMachine, passing self._variables as the model
        # The StateMachine library will use this dictionary for its operations
        # if the dynamic callbacks correctly access it (which they now do via self._variables).
        self.sm = self.FSMClass(model=self._variables)

    # --- Public API (matching old FSMSimulator) ---
    def get_current_state_name(self):
        if not self.sm: return None
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
            # Re-instantiate with the cleared _variables dictionary as the model
            self.sm = self.FSMClass(model=self._variables)
        else:
            raise FSMError("FSM Class not built, cannot reset.")
        self._log_action(f"FSM Reset. Current state: {self.sm.current_state.id if self.sm else 'Unknown'}")


    def step(self, event_name=None):
        if not self.sm:
            raise FSMError("Cannot step, FSM is not initialized.")

        current_state_id = self.sm.current_state.id
        self._log_action(f"--- Step triggered. Current state: {current_state_id}. Event: {event_name or 'None (internal)'} ---")

        current_state_input_data = self._states_input_data.get(current_state_id)
        if current_state_input_data and current_state_input_data.get('during_action'):
            during_action_str = current_state_input_data['during_action']
            self._log_action(f"Executing during actions for state '{current_state_id}': {during_action_str}")
            temp_during_cb = self._create_dynamic_callback(during_action_str, "action", original_name=f"during_{current_state_id}")
            # The dynamic callback wrapper will use self._variables for its execution context
            temp_during_cb() # No need to pass model here, wrapper accesses self._variables

        if event_name:
            try:
                self.sm.send(event_name) 
            except TransitionNotAllowed:
                self._log_action(f"Event '{event_name}' is not allowed or did not cause a transition from state '{current_state_id}'.")
            except AttributeError as e: # Handles cases where event_name is not a defined method on the SM
                if hasattr(self.sm, event_name) and callable(getattr(self.sm, event_name)):
                    # This case should ideally be caught by TransitionNotAllowed if it's a valid event method
                    # but the conditions aren't met or no transition is defined for it from the current state.
                    # However, if it's some other attribute error:
                    self._log_action(f"AttributeError processing event '{event_name}': {type(e).__name__} - {e}")
                else: # The event name isn't even an attribute (method) of the SM
                     self._log_action(f"Event '{event_name}' is not defined on the FSM.")
            except Exception as e:
                self._log_action(f"Unexpected error during event '{event_name}': {type(e).__name__} - {e}")
        else:
            self._log_action(f"No event provided. 'During' actions (if any) executed. State remains '{current_state_id}'.")
            
        return self.sm.current_state.id, self.get_last_executed_actions_log()

# For compatibility, if MainWindow imports FSMSimulator, we point it to the new class
FSMSimulator = StateMachinePoweredSimulator