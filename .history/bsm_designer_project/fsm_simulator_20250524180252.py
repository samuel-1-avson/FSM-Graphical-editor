print("fsm_simulator.py is being imported with python-statemachine integration!")

from statemachine import StateMachine, State
from statemachine.exceptions import TransitionNotAllowed
from statemachine.event import Event as SMEvent # Renamed to avoid conflict if we use Event internally
from statemachine.transition_list import TransitionList as SMTransitionList
from functools import partial
import logging

# Configure logging to match main.py's style
logging.basicConfig(level=logging.INFO, format="--- FSM_SIM (%(asctime)s): %(message)s", datefmt="%H:%M:%S.%f")

class FSMError(Exception):
    pass

class StateMachinePoweredSimulator:
    def __init__(self, states_data, transitions_data):
        """Initialize the FSM simulator with state and transition data."""
        self._states_input_data = {s['name']: s for s in states_data}  # Map state names to data
        self._transitions_input_data = transitions_data
        self._variables = {}  # State machine model
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
            logging.error(f"Initialization failed: {e}")
            raise FSMError(f"FSM Initialization failed: {e}")

    def _log_action(self, message):
        """Log an action with timestamp, matching main.py's logging style."""
        self._action_log.append(message)
        logging.info(message)

    def _create_dynamic_callback(self, code_string, callback_type="action", original_name="dynamic_callback"):
        """Create a dynamic callback for actions or conditions."""
        def dynamic_callback_wrapper(*args, **kwargs):
            exec_eval_locals_dict = self._variables  # Use _variables as execution context
            log_prefix = "[Action]" if callback_type == "action" else "[Condition]"
            self._log_action(f"{log_prefix} Executing: '{code_string}' with variables: {exec_eval_locals_dict}")

            try:
                if callback_type == "action":
                    exec(code_string, {"__builtins__": {}}, exec_eval_locals_dict)
                    self._log_action(f"{log_prefix} Finished: '{code_string}'. Variables now: {exec_eval_locals_dict}")
                    return None
                elif callback_type == "condition":
                    result = eval(code_string, {"__builtins__": {}}, exec_eval_locals_dict)
                    self._log_action(f"{log_prefix} Result of '{code_string}': {result}")
                    return bool(result)
            except SyntaxError as e:
                err_msg = f"SyntaxError in {callback_type} '{code_string}': {e.msg} (line {e.lineno}, offset {e.offset})"
                self._log_action(f"[Eval Error] {err_msg}")
                if callback_type == "condition":
                    return False
            except NameError as e:
                err_msg = f"NameError in {callback_type} '{code_string}': {e}. Check if variable is defined."
                self._log_action(f"[Eval Error] {err_msg}")
                if callback_type == "condition":
                    return False
            except Exception as e:
                err_msg = f"Unexpected error in {callback_type} '{code_string}': {type(e).__name__} - {e}"
                self._log_action(f"[Eval Error] {err_msg}")
                if callback_type == "condition":
                    return False
            return None

        dynamic_callback_wrapper.__name__ = f"{original_name}_{callback_type}_{hash(code_string)}"
        return dynamic_callback_wrapper

    def _sm_on_enter_state(self, target: State, event_data, machine, **kwargs):
        """Log state entry."""
        self._log_action(f"Entering state: {target.id}")

    def _sm_on_exit_state(self, source: State, event_data, machine, **kwargs):
        """Log state exit."""
        self._log_action(f"Exiting state: {source.id}")

    def _sm_before_transition(self, event: str, source: State, target: State, event_data, machine, **kwargs):
        """Log before transition."""
        self._log_action(f"Before transition on '{event_data.event}' from '{source.id}' to '{target.id}'")

    def _sm_after_transition(self, event: str, source: State, target: State, event_data, machine, **kwargs):
        """Log after transition."""
        self._log_action(f"After transition on '{event_data.event}' from '{source.id}' to '{target.id}'")

    def _build_fsm_class_and_instance(self):
        """Build the dynamic StateMachine class and instance."""
        fsm_class_attrs = {}
        sm_states_obj_map = {}
        initial_state_found_in_data = False

        # Define State objects
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
                sm_states_obj_map[first_state_name_from_data]._initial = True # Accessing protected _initial
                self._initial_state_name = first_state_name_from_data
            else:
                raise FSMError("Error setting fallback initial state: First state not found in map.")
        elif not self._states_input_data:
            raise FSMError("No states defined in the FSM.")

        # Define Event objects and Transitions
        unique_event_names = set(t.get('event') for t in self._transitions_input_data if t.get('event'))

        for t_data in self._transitions_input_data:
            source_name = t_data['source']
            target_name = t_data['target']
            event_name = t_data.get('event')

            if not event_name:
                synthetic_event_name = f"_internal_transition_{source_name}_to_{target_name}"
                self._log_action(f"Warning: Transition {source_name}->{target_name} has no event. Assigning synthetic event: {synthetic_event_name}")
                event_name = synthetic_event_name
                # unique_event_names.add(event_name) # No longer need unique_event_names set

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
            
            # The python-statemachine library builds transitions by chaining them from events or states
            # state_from | state_to | event_name
            # We can express transitions by using state.to(other_state, on="event_name", cond=conditions, action=actions)
            # The library handles creating Event objects implicitly if an event name string is provided.

            # Get or create the event object in fsm_class_attrs
            if event_name not in fsm_class_attrs:
                # Create a new Event object. The actual event trigger will be assigned to the class.
                # The transitions themselves are attached to states.
                # The StateMachine metaclass handles linking event strings on transitions to these Event objects.
                fsm_class_attrs[event_name] = SMEvent(event_name) # Create an Event object for the SM
            
            # Now, define the transition from the source state
            # This uses the fluent API of the `python-statemachine` library
            # Transition from source_state_obj to target_state_obj on event_name
            transition_segment = source_state_obj.to(target_state_obj, event=event_name, cond=conditions or None, on=actions or None)
            
            # The library's metaclass should handle collecting these transitions defined on states.
            # We don't need to manually assign transition_segment to fsm_class_attrs[event_name]
            # as was done previously, because the .to() method on the State object already registers
            # the transition appropriately within the library's internal structures.


        # Add logging methods
        fsm_class_attrs["on_enter_state"] = self._sm_on_enter_state
        fsm_class_attrs["on_exit_state"] = self._sm_on_exit_state
        fsm_class_attrs["before_transition"] = self._sm_before_transition
        fsm_class_attrs["after_transition"] = self._sm_after_transition

        # Create and instantiate StateMachine
        try:
            self.FSMClass = type("DynamicBSMFSM", (StateMachine,), fsm_class_attrs)
            self.sm = self.FSMClass(model=self._variables)
        except Exception as e:
            logging.error(f"Failed to create StateMachine: {e}")
            raise FSMError(f"StateMachine creation failed: {e}")

    def get_current_state_name(self):
        """Return the current state name."""
        if not self.sm:
            logging.error("Cannot get current state: FSM not initialized.")
            return None
        return self.sm.current_state.id

    def get_variables(self):
        """Return a copy of the variables dictionary."""
        return self._variables.copy()

    def get_last_executed_actions_log(self):
        """Return and clear the action log."""
        log_copy = list(self._action_log)
        self._action_log.clear()
        return log_copy

    def reset(self):
        """Reset the FSM to its initial state."""
        self._log_action("--- FSM Resetting ---")
        self._variables.clear()

        if self.FSMClass:
            try:
                self.sm = self.FSMClass(model=self._variables)
                self._log_action(f"FSM Reset. Current state: {self.sm.current_state.id if self.sm else 'Unknown'}")
            except Exception as e:
                logging.error(f"Reset failed: {e}")
                raise FSMError(f"FSM Reset failed: {e}")
        else:
            logging.error("FSM Class not built, cannot reset.")
            raise FSMError("FSM Class not built, cannot reset.")

    def step(self, event_name=None):
        """Execute a step, optionally with an event."""
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
                temp_during_cb = self._create_dynamic_callback(during_action_str, "action", original_name=f"during_{current_state_id}")
                temp_during_cb()
            except Exception as e:
                self._log_action(f"Error executing during action '{during_action_str}': {e}")
                logging.error(f"During action error: {e}")

        if event_name:
            try:
                self.sm.send(event_name) # This internally calls the event method
            except TransitionNotAllowed:
                self._log_action(f"Event '{event_name}' is not allowed or did not cause a transition from state '{current_state_id}'.")
            except AttributeError as e:
                # Check if the event method actually exists on the sm instance
                if hasattr(self.sm, event_name) and callable(getattr(self.sm, event_name)):
                     # This might indicate an internal issue with the library or our dynamic setup if a defined event method fails this way
                    self._log_action(f"AttributeError processing event '{event_name}': {e}. This might be an internal setup issue.")
                else:
                    self._log_action(f"Event '{event_name}' is not defined on the FSM.")
            except Exception as e:
                self._log_action(f"Unexpected error during event '{event_name}': {type(e).__name__} - {e}")
                logging.error(f"Event processing error: {e}")
        else:
            self._log_action(f"No event provided. 'During' actions (if any) executed. State remains '{current_state_id}'.")

        return self.sm.current_state.id, self.get_last_executed_actions_log()

    def get_possible_events_from_current_state(self) -> list[str]:
        """Return a list of event names that can be triggered from the current state."""
        if not self.sm or not self.sm.current_state:
            logging.warning("Cannot get possible events: FSM or current state not available.")
            return []
        
        possible_events = set()
        # The `python-statemachine` library stores transitions on each state object.
        # Each transition has an `events` attribute (which is an `Events` collection).
        for transition in self.sm.current_state.transitions:
            for event_obj in transition.events: # event_obj is an Event instance
                possible_events.add(str(event_obj.id)) # Or str(event_obj)
        
        # Also consider events defined on the StateMachine class itself that might not be
        # directly tied to a transition from the current state but are still 'sendable'
        # (though they might result in TransitionNotAllowed).
        # For UI purposes, usually only events leading to valid transitions are desired.
        # The current approach of looking at current_state.transitions is typical.

        return sorted(list(possible_events))


# Compatibility alias for MainWindow
FSMSimulator = StateMachinePoweredSimulator

if __name__ == "__main__":
    # Example usage
    states_data = [
        {"name": "Initial", "is_initial": True},
        {"name": "Loading", "entry_action": "print('Loading started')"},
        {"name": "Success"},
        {"name": "Error"}
    ]
    transitions_data = [
        {"source": "Initial", "target": "Loading", "event": "start"},
        {"source": "Loading", "target": "Success", "event": "complete"},
        {"source": "Loading", "target": "Error", "event": "fail"}
    ]
    try:
        simulator = FSMSimulator(states_data, transitions_data)
        print("Initial state:", simulator.get_current_state_name())
        print("Possible events from Initial:", simulator.get_possible_events_from_current_state())

        next_state, log = simulator.step("start")
        print("After step 'start':", next_state)
        print("Log:", log)
        print("Possible events from Loading:", simulator.get_possible_events_from_current_state())

        next_state, log = simulator.step("complete")
        print("After step 'complete':", next_state)
        print("Log:", log)
        print("Possible events from Success:", simulator.get_possible_events_from_current_state())


    except FSMError as e:
        print(f"FSM Error: {e}")