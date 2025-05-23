# fsm_simulator.py

class FSMError(Exception): # Make sure this is also top-level
    pass

class FSMSimulator:
    def __init__(self, states, transitions):
        # ... your simulator logic ...
        self.states_data = states
        self.transitions_data = transitions
        self.current_state_name = None
        self._variables = {}
        self._action_log = []
        self._find_initial_state()
        if self.current_state_name:
            self._execute_entry_actions(self.current_state_name)

    def _log_action(self, message):
        self._action_log.append(message)
        # print(f"FSMSimLog: {message}") # Optional console log

    def _find_initial_state(self):
        for state in self.states_data:
            if state.get('is_initial', False):
                self.current_state_name = state['name']
                self._log_action(f"Initial state set to: {self.current_state_name}")
                return
        # If no initial state explicitly defined, try to pick the first one or raise error
        if self.states_data:
             self.current_state_name = self.states_data[0]['name']
             self._log_action(f"No initial state explicitly defined. Using first state as initial: {self.current_state_name}")
        else:
            raise FSMError("No states defined in the FSM.")


    def _execute_entry_actions(self, state_name):
        state_data = self._get_state_data_by_name(state_name)
        if state_data and state_data.get('entry_action'):
            action_str = state_data['entry_action']
            self._log_action(f"Executing entry actions for state '{state_name}': {action_str}")
            self._evaluate_action(action_str)

    def _execute_exit_actions(self, state_name):
        state_data = self._get_state_data_by_name(state_name)
        if state_data and state_data.get('exit_action'):
            action_str = state_data['exit_action']
            self._log_action(f"Executing exit actions for state '{state_name}': {action_str}")
            self._evaluate_action(action_str)

    def _execute_during_actions(self, state_name):
        state_data = self._get_state_data_by_name(state_name)
        if state_data and state_data.get('during_action'):
            action_str = state_data['during_action']
            self._log_action(f"Executing during actions for state '{state_name}': {action_str}")
            self._evaluate_action(action_str)


    def _evaluate_condition(self, condition_str):
        if not condition_str:
            return True # No condition means true
        try:
            # VERY UNSAFE for general purpose Python.
            # In a real app, use a restricted eval or a custom parser.
            self._log_action(f"[Condition] Evaluating: {condition_str}")
            result = eval(condition_str, {"__builtins__": {}}, self._variables.copy()) # Pass variables as globals
            self._log_action(f"[Condition] Result of '{condition_str}': {result}")
            return bool(result)
        except Exception as e:
            self._log_action(f"[Eval Error] Condition '{condition_str}': {e}")
            # raise FSMError(f"Error evaluating condition '{condition_str}': {e}")
            return False # Treat evaluation errors as false condition

    def _evaluate_action(self, action_str):
        if not action_str:
            return
        try:
            # VERY UNSAFE for general purpose Python. Use a restricted eval or custom parser.
            # Create a copy of variables to pass, as exec can modify its globals.
            local_vars_for_exec = self._variables.copy()
            # Execute action string; multiple statements separated by ';' or newline
            # Note: exec does not return a value. It modifies the passed dictionary.
            for stmt in action_str.split(';'): # simple split, might need better parsing
                stmt = stmt.strip()
                if stmt:
                    self._log_action(f"[Action] Executing: {stmt}")
                    exec(stmt, {"__builtins__": {}}, local_vars_for_exec)
            
            # Update the FSM's variables with any changes from the exec'd actions
            for var_name, var_value in local_vars_for_exec.items():
                if var_name not in self._variables or self._variables[var_name] != var_value:
                    self._log_action(f"Variable '{var_name}' updated to: {var_value}")
                    self._variables[var_name] = var_value

        except Exception as e:
            self._log_action(f"[Eval Error] Action '{action_str}': {e}")
            # Depending on desired strictness, you might re-raise or just log.
            # raise FSMError(f"Error executing action '{action_str}': {e}")


    def _get_state_data_by_name(self, state_name):
        for state in self.states_data:
            if state['name'] == state_name:
                return state
        return None

    def get_current_state_name(self):
        return self.current_state_name

    def get_variables(self):
        return self._variables.copy() # Return a copy

    def get_last_executed_actions_log(self):
        log_copy = list(self._action_log)
        self._action_log.clear() # Clear log after retrieval
        return log_copy

    def reset(self):
        self._log_action("--- FSM Resetting ---")
        self._variables.clear()
        self.current_state_name = None # Will be set by _find_initial_state
        self._find_initial_state()
        if self.current_state_name:
            self._execute_entry_actions(self.current_state_name)
        else: # Should have been caught by _find_initial_state earlier
             raise FSMError("Reset failed: Could not determine initial state after reset.")


    def step(self, event_name=None):
        if not self.current_state_name:
            raise FSMError("Cannot step, FSM is not in a valid state (no current state).")

        self._log_action(f"--- Step triggered. Current state: {self.current_state_name}. Event: {event_name or 'None (internal)'} ---")

        # 1. Execute 'during' actions of the current state
        self._execute_during_actions(self.current_state_name)

        # 2. Evaluate transitions
        eligible_transition = None
        for trans_data in self.transitions_data:
            if trans_data['source'] == self.current_state_name:
                event_match = (not trans_data.get('event')) or (trans_data.get('event') == event_name)
                if event_match: # Check if event matches or if transition has no event (always considered for conditions)
                    self._log_action(f"Considering transition from '{trans_data['source']}' to '{trans_data['target']}' on event '{trans_data.get('event','ANY/NONE')}'.")
                    if self._evaluate_condition(trans_data.get('condition', "")):
                        eligible_transition = trans_data
                        self._log_action(f"Transition from '{self.current_state_name}' to '{eligible_transition['target']}' is eligible.")
                        break # First eligible transition wins (common FSM behavior)
        
        if eligible_transition:
            old_state = self.current_state_name
            new_state = eligible_transition['target']

            # 3a. Execute exit actions of current state
            self._execute_exit_actions(old_state)
            
            # 3b. Execute transition actions
            self._evaluate_action(eligible_transition.get('action', ""))
            
            # 3c. Change current state
            self.current_state_name = new_state
            self._log_action(f"Transitioned from '{old_state}' to '{new_state}'.")

            # 3d. Execute entry actions of new state
            self._execute_entry_actions(new_state)
        else:
             self._log_action(f"No eligible transition found from state '{self.current_state_name}' for event '{event_name or 'None'}'.")

        return self.current_state_name, self.get_last_executed_actions_log()
# ...