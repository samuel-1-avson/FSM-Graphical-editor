# fsm_simulator.py
print("fsm_simulator.py is being imported!")
# import types # No longer needed for environment interaction

class FSMError(Exception):
    pass

class FSMSimulator:
    def __init__(self, states_data, transitions_data): # Removed environment_module
        self.states_data = states_data
        self.transitions_data = transitions_data
        self.current_state_name = None
        self._variables = {} # FSM's internal variables
        self._action_log = []

        self._find_initial_state()
        if self.current_state_name:
            self._execute_entry_actions(self.current_state_name)

    def _log_action(self, message):
        self._action_log.append(message)
        # print(f"FSMSimLog: {message}")

    def _find_initial_state(self):
        for state_dict in self.states_data:
            if state_dict.get('is_initial', False):
                self.current_state_name = state_dict['name']
                self._log_action(f"Initial state set to: {self.current_state_name}")
                return
        if self.states_data:
             self.current_state_name = self.states_data[0]['name']
             self._log_action(f"No initial state explicitly defined. Using first state as initial: {self.current_state_name}")
        else:
            raise FSMError("No states defined in the FSM.")

    def _get_state_data_by_name(self, state_name):
        for state_dict in self.states_data:
            if state_dict['name'] == state_name:
                return state_dict
        return None

    def _prepare_evaluation_context(self):
        """Prepares the context (globals) for eval() and exec()."""
        # Context is now just the FSM's internal variables
        context = self._variables.copy()
        return context

    def _evaluate_condition(self, condition_str):
        if not condition_str:
            return True
        try:
            eval_context = self._prepare_evaluation_context()
            # self._log_action(f"[Condition] Evaluating: {condition_str} with context keys: {list(eval_context.keys())}")
            result = eval(condition_str, {"__builtins__": {}}, eval_context)
            self._log_action(f"[Condition] Result of '{condition_str}': {result}")
            return bool(result)
        except Exception as e:
            self._log_action(f"[Eval Error] Condition '{condition_str}': {e}")
            return False

    def _evaluate_action(self, action_str):
        if not action_str:
            return
        try:
            exec_context = self._prepare_evaluation_context()
            # self._log_action(f"[Action] Executing: {action_str} with context keys: {list(exec_context.keys())}")

            for stmt in action_str.split(';'):
                stmt = stmt.strip()
                if stmt:
                    self._log_action(f"  Executing statement: {stmt}")
                    exec(stmt, {"__builtins__": {}}, exec_context)

            # Update FSM's internal variables (_variables) with any changes
            for var_name, var_value in exec_context.items():
                if var_name == "__builtins__": # Don't copy builtins back
                    continue
                if var_name not in self._variables or self._variables[var_name] != var_value:
                    self._log_action(f"FSM Variable '{var_name}' updated/set to: {var_value}")
                    self._variables[var_name] = var_value
        except Exception as e:
            self._log_action(f"[Eval Error] Action '{action_str}': {e}")

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

    def get_current_state_name(self):
        return self.current_state_name

    def get_variables(self):
        # Now only returns FSM's internal variables
        return self._variables.copy()

    def get_last_executed_actions_log(self):
        log_copy = list(self._action_log)
        self._action_log.clear()
        return log_copy

    def reset(self):
        self._log_action("--- FSM Resetting ---")
        self._variables.clear()
        self.current_state_name = None
        # No environment reset call
        self._find_initial_state()
        if self.current_state_name:
            self._execute_entry_actions(self.current_state_name)
        else:
             raise FSMError("Reset failed: Could not determine initial state after reset.")

    # _update_environment method is removed

    def step(self, event_name=None):
        if not self.current_state_name:
            raise FSMError("Cannot step, FSM is not in a valid state (no current state).")

        self._log_action(f"--- Step triggered. Current state: {self.current_state_name}. Event: {event_name or 'None (internal)'} ---")

        # No environment update call here

        # 1. Execute 'during' actions of the current state
        self._execute_during_actions(self.current_state_name)

        # 2. Evaluate transitions
        eligible_transition = None
        for trans_data in self.transitions_data:
            if trans_data['source'] == self.current_state_name:
                event_on_trans = trans_data.get('event')
                event_match = (not event_on_trans) or \
                              (event_on_trans == event_name) or \
                              (event_on_trans == '*' and event_name is not None)

                if event_match:
                    self._log_action(f"Considering transition from '{trans_data['source']}' to '{trans_data['target']}' for event '{event_on_trans or 'ANY/NONE'}'.")
                    if self._evaluate_condition(trans_data.get('condition', "")):
                        eligible_transition = trans_data
                        self._log_action(f"Transition from '{self.current_state_name}' to '{eligible_transition['target']}' is eligible.")
                        break
        
        if eligible_transition:
            old_state = self.current_state_name
            new_state = eligible_transition['target']
            self._execute_exit_actions(old_state)
            self._evaluate_action(eligible_transition.get('action', ""))
            self.current_state_name = new_state
            self._log_action(f"Transitioned from '{old_state}' to '{new_state}'.")
            self._execute_entry_actions(new_state)
        else:
             self._log_action(f"No eligible transition found from state '{self.current_state_name}' for event '{event_name or 'None'}'.")

        return self.current_state_name, self.get_last_executed_actions_log()