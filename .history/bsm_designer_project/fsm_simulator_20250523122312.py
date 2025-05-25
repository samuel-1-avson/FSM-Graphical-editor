# fsm_simulator.py
print("fsm_simulator.py is being imported!")
import types # For checking if something is a function

class FSMError(Exception):
    pass

class FSMSimulator:
    def __init__(self, states_data, transitions_data, environment_module=None): # Added environment_module
        self.states_data = states_data
        self.transitions_data = transitions_data
        self.current_state_name = None
        self._variables = {} # FSM's internal variables
        self._action_log = [] # Renamed from self.action_log to avoid conflict if env has 'action_log'

        # --- Environment Integration ---
        self.env = environment_module
        self.env_exposed_functions = {} # Functions from env callable by FSM actions/conditions
        # self.env_shared_variables_config = {} # For future explicit config of shared vars (not used yet)

        if self.env:
            env_name_for_log = self.env.__name__ if hasattr(self.env, '__name__') else 'anonymous_env_module'
            self._log_action(f"Environment module '{env_name_for_log}' loaded.")
            self._discover_env_functions()
            if hasattr(self.env, 'initialize_environment'):
                try:
                    # Pass a copy of FSM variables, env can modify it and we can merge back if needed
                    # Or, env can directly modify self._variables if passed (more direct but less controlled)
                    # For now, let's pass self._variables directly for simplicity, env can add keys.
                    self.env.initialize_environment(self._variables)
                    self._log_action("Called environment.initialize_environment().")
                except Exception as e:
                    self._log_action(f"[Env Error] initialize_environment: {e}")
        # --- End Init Modifications for Environment ---

        self._find_initial_state()
        if self.current_state_name:
            self._execute_entry_actions(self.current_state_name)


    def _discover_env_functions(self):
        if not self.env:
            return
        for name in dir(self.env):
            if not name.startswith("_"):
                attr = getattr(self.env, name)
                if isinstance(attr, (types.FunctionType, types.MethodType)): # Check for both
                    self.env_exposed_functions[name] = attr
        if self.env_exposed_functions:
            self._log_action(f"Discovered environment functions: {', '.join(self.env_exposed_functions.keys())}")


    def _log_action(self, message):
        self._action_log.append(message)
        # print(f"FSMSimLog: {message}") # Optional console log for debugging

    def _find_initial_state(self):
        for state_dict in self.states_data: # Iterate over list of dicts
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
        for state_dict in self.states_data: # Iterate over list of dicts
            if state_dict['name'] == state_name:
                return state_dict
        return None

    def _prepare_evaluation_context(self):
        """Prepares the context (globals) for eval() and exec()."""
        context = self._variables.copy()
        context.update(self.env_exposed_functions)

        if self.env:
            for name in dir(self.env):
                if not name.startswith("_") and name not in self.env_exposed_functions:
                    attr = getattr(self.env, name)
                    # Avoid adding modules, functions, or methods that aren't explicitly exposed
                    if not isinstance(attr, (types.ModuleType, types.FunctionType, types.MethodType)):
                        # If the name is already in context (from _variables), prioritize _variables
                        # unless we implement specific logic for env overriding FSM vars.
                        # For now, FSM vars take precedence if names clash.
                        if name not in context:
                            context[name] = attr
        return context

    def _evaluate_condition(self, condition_str):
        if not condition_str:
            return True
        try:
            eval_context = self._prepare_evaluation_context()
            # self._log_action(f"[Condition] Evaluating: {condition_str} with context keys: {list(eval_context.keys())}")
            result = eval(condition_str, {"__builtins__": {}}, eval_context) # Pass combined context
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
                    exec(stmt, {"__builtins__": {}}, exec_context) # Execute in combined context

            # Update FSM's internal variables (_variables) and environment module attributes
            for var_name, var_value in exec_context.items():
                if var_name in self.env_exposed_functions or var_name == "__builtins__":
                    continue

                # Check if this variable originated from self.env (and is not a function)
                is_env_module_var = False
                if self.env and hasattr(self.env, var_name):
                    attr_in_env = getattr(self.env, var_name)
                    if not isinstance(attr_in_env, (types.FunctionType, types.MethodType, types.ModuleType)):
                        is_env_module_var = True

                if is_env_module_var:
                    # If it's an env var and its value changed in exec_context, update it in the env module
                    if getattr(self.env, var_name) != var_value:
                        try:
                            setattr(self.env, var_name, var_value)
                            self._log_action(f"Environment Variable '{var_name}' updated to: {var_value} via FSM action.")
                        except AttributeError: # Should not happen if hasattr was true
                            self._log_action(f"[Env Error] Could not set attr '{var_name}' on environment module.")
                else:
                    # If it's not an env var (or doesn't exist in env), update/create in FSM's _variables
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
        # Return a combined view of FSM variables and relevant environment variables
        combined_vars = self._variables.copy()
        if self.env:
            for name in dir(self.env):
                 if not name.startswith("_") and name not in self.env_exposed_functions:
                    attr = getattr(self.env, name)
                    if not isinstance(attr, (types.ModuleType, types.FunctionType, types.MethodType)):
                        # Prefix env vars to distinguish them in the UI if names clash.
                        # Show current value from the env module.
                        combined_vars[f"env.{name}"] = attr
        return combined_vars


    def get_last_executed_actions_log(self):
        log_copy = list(self._action_log) # Use the renamed attribute
        self._action_log.clear()
        return log_copy

    def reset(self):
        self._log_action("--- FSM Resetting ---")
        self._variables.clear()
        self.current_state_name = None
        if self.env and hasattr(self.env, 'reset_environment'):
            try:
                # Pass self._variables so env can set initial values or read FSM config
                self.env.reset_environment(self._variables)
                self._log_action("Called environment.reset_environment().")
            except Exception as e:
                self._log_action(f"[Env Error] reset_environment: {e}")

        self._find_initial_state()
        if self.current_state_name:
            self._execute_entry_actions(self.current_state_name)
        else:
             raise FSMError("Reset failed: Could not determine initial state after reset.")

    def _update_environment(self, event_name=None):
        """Call the environment's update function, if it exists."""
        if self.env and hasattr(self.env, 'update_environment'):
            try:
                self._log_action(f"Calling environment.update_environment(event='{event_name}')...")
                # The environment update function receives the FSM's variable dictionary.
                # It can modify this dictionary directly to update FSM variables,
                # or it can modify its own module-level variables which the FSM can read.
                # No explicit return of changed_fsm_vars is needed if env modifies the dict in-place.
                self.env.update_environment(self._variables, event_name)
                self._log_action("environment.update_environment() finished.")
            except Exception as e:
                self._log_action(f"[Env Error] update_environment: {e}")


    def step(self, event_name=None):
        if not self.current_state_name:
            raise FSMError("Cannot step, FSM is not in a valid state (no current state).")

        self._log_action(f"--- Step triggered. Current state: {self.current_state_name}. Event: {event_name or 'None (internal)'} ---")

        # 0. Update environment (e.g., simulate plant dynamics for one step)
        self._update_environment(event_name)

        # 1. Execute 'during' actions of the current state
        self._execute_during_actions(self.current_state_name)

        # 2. Evaluate transitions
        eligible_transition = None
        for trans_data in self.transitions_data: # Iterate over list of dicts
            if trans_data['source'] == self.current_state_name:
                # Event matching logic:
                # 1. No event specified on transition (always a candidate if source matches)
                # 2. Event on transition matches current_event
                # 3. Wildcard '*' on transition and an event *is* provided for the step
                event_on_trans = trans_data.get('event')
                event_match = (not event_on_trans) or \
                              (event_on_trans == event_name) or \
                              (event_on_trans == '*' and event_name is not None)

                if event_match:
                    self._log_action(f"Considering transition from '{trans_data['source']}' to '{trans_data['target']}' for event '{event_on_trans or 'ANY/NONE'}'.")
                    if self._evaluate_condition(trans_data.get('condition', "")):
                        eligible_transition = trans_data
                        self._log_action(f"Transition from '{self.current_state_name}' to '{eligible_transition['target']}' is eligible.")
                        break # First eligible transition wins
        
        if eligible_transition:
            old_state = self.current_state_name
            new_state = eligible_transition['target']
            self._execute_exit_actions(old_state)
            self._evaluate_action(eligible_transition.get('action', "")) # Transition action
            self.current_state_name = new_state
            self._log_action(f"Transitioned from '{old_state}' to '{new_state}'.")
            self._execute_entry_actions(new_state)
        else:
             self._log_action(f"No eligible transition found from state '{self.current_state_name}' for event '{event_name or 'None'}'.")

        return self.current_state_name, self.get_last_executed_actions_log()