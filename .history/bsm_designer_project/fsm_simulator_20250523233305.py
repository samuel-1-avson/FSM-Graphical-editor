# bsm_designer_project/fsm_simulator.py
print("fsm_simulator.py is being imported with python-statemachine integration!")

from statemachine import StateMachine, State, TransitionNotAllowed
from statemachine.event import Event as SMEvent # Alias to avoid conflict if any
from statemachine.transition_list import TransitionList as SMTransitionList
from functools import partial

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
        
        # Initial state entry actions and logging are handled by StateMachine constructor
        # and our hooked on_enter_state. We just log the fact that it's set.
        if self.sm and self.sm.current_state:
             # The on_enter_state for initial state will already have logged "Entering state: X"
             self._log_action(f"FSM Initialized. Current state: {self.sm.current_state.id}")
        elif not self._states_input_data:
             raise FSMError("No states defined in the FSM.")
        else:
             # This case should ideally be caught by _find_initial_state logic
             raise FSMError("FSM Initialization failed: Could not determine current state after build.")


    def _log_action(self, message):
        self._action_log.append(message)

    def _create_dynamic_callback(self, code_string, callback_type="action"):
        # callback_type can be "action" (exec) or "condition" (eval)
        
        # This wrapper will be called by python-statemachine.
        # It will receive 'model', 'event_data', 'machine', etc. as kwargs.
        # 'model' is our self._variables dictionary.
        def dynamic_callback_wrapper(*args, **kwargs):
            model = kwargs.get('model') # This is self._variables
            if model is None:
                # Fallback or error if model not passed, though it should be.
                # For robustness, can use self._variables directly if sure about context.
                # However, relying on 'model' kwarg is cleaner with the library.
                self._log_action(f"[Callback Error] 'model' not found in kwargs for '{code_string}'. Using simulator's _variables.")
                model = self._variables


            log_prefix = "[Action]" if callback_type == "action" else "[Condition]"
            self._log_action(f"{log_prefix} Executing: '{code_string}' with variables: {model}")

            try:
                if callback_type == "action":
                    # exec modifies the 'model' dict (which is self._variables) in place.
                    exec(code_string, {"__builtins__": {}}, model) 
                    self._log_action(f"{log_prefix} Finished: '{code_string}'. Variables now: {model}")
                    return None # Actions don't return significant values to the FSM
                
                elif callback_type == "condition":
                    result = eval(code_string, {"__builtins__": {}}, model)
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
            return None # Should not be reached for condition if error handling is correct

        # functools.partial is used to "bake in" the code_string and callback_type
        # The resulting partial object is callable and will pass along any *args, **kwargs from statemachine
        return partial(dynamic_callback_wrapper)


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
        sm_states_obj_map = {} # Store State machine State objects
        initial_state_found_in_data = False
        for s_name, s_data in self._states_input_data.items():
            is_initial = s_data.get('is_initial', False)
            if is_initial:
                self._initial_state_name = s_name
                initial_state_found_in_data = True

            enter_callbacks = []
            if s_data.get('entry_action'):
                # Pass the action string and type to the creator
                enter_callbacks.append(self._create_dynamic_callback(s_data['entry_action'], "action"))
            # Note: Logging for enter/exit is now handled by generic SM callbacks if preferred

            exit_callbacks = []
            if s_data.get('exit_action'):
                exit_callbacks.append(self._create_dynamic_callback(s_data['exit_action'], "action"))

            state_obj = State(
                name=s_name, # Using name as id
                value=s_name, # And value
                initial=is_initial,
                final=s_data.get('is_final', False),
                enter=enter_callbacks or None,
                exit=exit_callbacks or None
            )
            fsm_class_attrs[s_name] = state_obj # Add state to class attributes
            sm_states_obj_map[s_name] = state_obj

        if not initial_state_found_in_data and self._states_input_data:
            # Fallback: Mark the first state from input data as initial
            first_state_name_from_data = next(iter(self._states_input_data))
            if first_state_name_from_data in sm_states_obj_map:
                self._log_action(f"No initial state explicitly defined. Using first state as initial: {first_state_name_from_data}")
                sm_states_obj_map[first_state_name_from_data]._initial = True # Directly set internal flag
                self._initial_state_name = first_state_name_from_data
            else: # Should not happen if all states are processed
                 raise FSMError("Error setting fallback initial state: First state not found in map.")
        elif not self._states_input_data:
             raise FSMError("No states defined in the FSM.")


        # 2. Define Event objects and their Transitions
        unique_event_names = set(t.get('event') for t in self._transitions_input_data if t.get('event'))
        
        # Add a special event for "eventless" transitions if any, or handle them differently
        # For now, we assume transitions require an event name. If a transition in data has no event,
        # it needs a placeholder event name to be triggered.

        for t_data in self._transitions_input_data:
            source_name = t_data['source']
            target_name = t_data['target']
            event_name = t_data.get('event')

            if not event_name:
                # This transition was "eventless" in the old model.
                # To make it work with python-statemachine, it needs an event trigger.
                # We can create a synthetic event for it, or decide such transitions
                # are evaluated differently (e.g., only checked during a specific "tick" event).
                # For now, let's log a warning and skip, or assign a default synthetic event.
                # Let's make a synthetic event name for now.
                synthetic_event_name = f"_internal_transition_{source_name}_to_{target_name}"
                self._log_action(f"Warning: Transition {source_name}->{target_name} has no event. Assigning synthetic event: {synthetic_event_name}")
                event_name = synthetic_event_name
                unique_event_names.add(event_name) # Add to set if not already there

            source_state_obj = sm_states_obj_map.get(source_name)
            target_state_obj = sm_states_obj_map.get(target_name)

            if not source_state_obj or not target_state_obj:
                self._log_action(f"Warning: Skipping transition due to missing source '{source_name}' or target '{target_name}'.")
                continue

            conditions = []
            if t_data.get('condition'):
                conditions.append(self._create_dynamic_callback(t_data['condition'], "condition"))
            
            actions = []
            if t_data.get('action'):
                actions.append(self._create_dynamic_callback(t_data['action'], "action"))

            # Create a TransitionList segment for this specific transition
            # `source_state_obj.to(target_state_obj)` returns a TransitionList
            transition_segment = source_state_obj.to(target_state_obj, cond=conditions or None, on=actions or None)
            
            # Add this segment to the correct Event attribute in fsm_class_attrs
            if event_name not in fsm_class_attrs:
                fsm_class_attrs[event_name] = transition_segment
            else:
                # If event_name already exists, it should be a TransitionList; append to it
                if isinstance(fsm_class_attrs[event_name], SMTransitionList):
                    fsm_class_attrs[event_name].add_transitions(transition_segment)
                else: # Should be a TransitionList already from a previous .to() call
                    self._log_action(f"Error: Attribute {event_name} was not a TransitionList when merging.")
                    # Fallback: wrap existing and new, then assign
                    current_val = fsm_class_attrs[event_name]
                    new_list = SMTransitionList()
                    if isinstance(current_val, SMTransitionList): new_list.add_transitions(current_val)
                    else: new_list.add_transitions(SMTransitionList([current_val])) # Assuming it was a single Transition
                    new_list.add_transitions(transition_segment)
                    fsm_class_attrs[event_name] = new_list
        
        # 3. Add generic logging methods to the class attributes
        # These methods need to be part of the class, or be callable with `machine` instance
        fsm_class_attrs["_sm_on_enter_state_handler"] = self._sm_on_enter_state
        fsm_class_attrs["_sm_on_exit_state_handler"] = self._sm_on_exit_state
        fsm_class_attrs["_sm_before_transition_handler"] = self._sm_before_transition
        fsm_class_attrs["_sm_after_transition_handler"] = self._sm_after_transition
        
        # Assign these handlers to the generic StateMachine callbacks
        # The StateMachineMetaclass looks for on_enter_state, on_exit_state etc.
        fsm_class_attrs["on_enter_state"] = self._sm_on_enter_state # Will be bound to SM instance
        fsm_class_attrs["on_exit_state"] = self._sm_on_exit_state
        fsm_class_attrs["before_transition"] = self._sm_before_transition
        fsm_class_attrs["after_transition"] = self._sm_after_transition
        
        # 4. Create the StateMachine class
        self.FSMClass = type("DynamicBSMFSM", (StateMachine,), fsm_class_attrs)
        
        # 5. Instantiate the StateMachine
        self.sm = self.FSMClass(model=self._variables) # Pass self._variables as the model

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
        
        # Re-instantiate the FSM with a fresh model
        if self.FSMClass:
            self.sm = self.FSMClass(model=self._variables)
            # Logging for initial state entry is handled by on_enter_state callback
        else:
            raise FSMError("FSM Class not built, cannot reset.")
        self._log_action(f"FSM Reset. Current state: {self.sm.current_state.id if self.sm else 'Unknown'}")


    def step(self, event_name=None):
        if not self.sm:
            raise FSMError("Cannot step, FSM is not initialized.")

        current_state_id = self.sm.current_state.id
        self._log_action(f"--- Step triggered. Current state: {current_state_id}. Event: {event_name or 'None (internal)'} ---")

        # 1. Execute 'during' actions of the current state
        current_state_input_data = self._states_input_data.get(current_state_id)
        if current_state_input_data and current_state_input_data.get('during_action'):
            during_action_str = current_state_input_data['during_action']
            self._log_action(f"Executing during actions for state '{current_state_id}': {during_action_str}")
            # Create and call a temporary dynamic callback for the during action
            # It needs the 'model' (self._variables) to operate on.
            temp_during_cb_partial = self._create_dynamic_callback(during_action_str, "action")
            temp_during_cb_partial(model=self._variables) # Manually pass our model

        # 2. Process event if provided
        if event_name:
            try:
                # The send method will trigger all relevant callbacks (before_transition, exit, on, enter, after_transition)
                # including custom action/condition callbacks and our logging callbacks.
                self.sm.send(event_name) 
            except TransitionNotAllowed:
                self._log_action(f"Event '{event_name}' is not allowed or did not cause a transition from state '{current_state_id}'.")
            except AttributeError as e:
                # This can happen if event_name does not correspond to a defined Event method on the SM
                if f"'{type(self.sm).__name__}' object has no attribute '{event_name}'" in str(e):
                     self._log_action(f"Event '{event_name}' is not defined on the FSM.")
                else:
                    self._log_action(f"Error processing event '{event_name}': {type(e).__name__} - {e}")
                    # raise # Optionally re-raise if it's a critical error
            except Exception as e:
                self._log_action(f"Unexpected error during event '{event_name}': {type(e).__name__} - {e}")
                # raise 
        else:
            # If no event is provided, only "during" actions are executed (handled above).
            # The state remains the same unless an event is sent.
            self._log_action(f"No event provided. 'During' actions (if any) executed. State remains '{current_state_id}'.")
            
        return self.sm.current_state.id, self.get_last_executed_actions_log()

# For compatibility, if MainWindow imports FSMSimulator, we point it to the new class
FSMSimulator = StateMachinePoweredSimulator