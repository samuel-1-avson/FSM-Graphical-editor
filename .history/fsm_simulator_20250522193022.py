# fsm_simulator.py
import math
import re

class FSMError(Exception):
    """Custom exception for FSM simulation errors."""
    pass

class FSMState:
    """Represents a state in the Finite State Machine."""
    def __init__(self, name: str, entry_actions_str: str, during_actions_str: str, exit_actions_str: str, is_initial: bool, is_final: bool):
        self.name = name
        self.entry_actions_str = entry_actions_str
        self.during_actions_str = during_actions_str
        self.exit_actions_str = exit_actions_str
        self.is_initial = is_initial
        self.is_final = is_final

    def __repr__(self):
        return f"FSMState(name='{self.name}', initial={self.is_initial}, final={self.is_final})"

class FSMTransition:
    """Represents a transition between states in the FSM."""
    def __init__(self, source_name: str, target_name: str, event: str, condition_str: str, actions_str: str):
        self.source_name = source_name
        self.target_name = target_name
        self.event = event.strip() if event else ""
        self.condition_str = condition_str.strip() if condition_str else ""
        self.actions_str = actions_str.strip() if actions_str else ""

    def __repr__(self):
        label_parts = []
        if self.event:
            label_parts.append(f"Event: '{self.event}'")
        if self.condition_str:
            label_parts.append(f"[{self.condition_str}]")
        if self.actions_str:
            label_parts.append(f"/{{{self.actions_str}}}")
        label = ", ".join(label_parts)
        return f"FSMTransition(from='{self.source_name}', to='{self.target_name}', {label})"

class FSMSimulator:
    """
    A simple Finite State Machine simulator.

    It interprets FSM definitions with states and transitions,
    simulates basic actions (variable assignments, simple arithmetic),
    and evaluates conditions to determine state changes.
    """
    def __init__(self, states_data: list[dict], transitions_data: list[dict]):
        """
        Initializes the FSM simulator.
        Args:
            states_data: A list of dictionaries, each defining a state.
                         Expected keys: 'name', 'entry_action', 'during_action', 
                                        'exit_action', 'is_initial', 'is_final'.
            transitions_data: A list of dictionaries, each defining a transition.
                              Expected keys: 'source', 'target', 'event', 
                                             'condition', 'action'.
        Raises:
            FSMError: If FSM definition is invalid (e.g., no initial state, duplicate names).
        """
        self.states: dict[str, FSMState] = {}
        self.transitions: list[FSMTransition] = []
        self._variables: dict = {}
        self._action_log: list[str] = []
        self.current_state_name: str | None = None
        self._initial_state_name: str | None = None

        self._parse_diagram_data(states_data, transitions_data)
        self.reset()

    def _parse_diagram_data(self, states_data: list[dict], transitions_data: list[dict]):
        initial_states_count = 0
        for s_data in states_data:
            name = s_data.get('name')
            if not name:
                raise FSMError("State data is missing the 'name' field.")
            if name in self.states:
                raise FSMError(f"Duplicate state name found: '{name}'.")

            state = FSMState(
                name=name,
                entry_actions_str=s_data.get('entry_action', ""),
                during_actions_str=s_data.get('during_action', ""),
                exit_actions_str=s_data.get('exit_action', ""),
                is_initial=s_data.get('is_initial', False),
                is_final=s_data.get('is_final', False)
            )
            self.states[name] = state
            if state.is_initial:
                initial_states_count += 1
                self._initial_state_name = name
        
        if initial_states_count == 0:
            raise FSMError("No initial state defined in the FSM.")
        if initial_states_count > 1:
            raise FSMError("Multiple initial states defined. Only one is allowed.")

        for t_data in transitions_data:
            source = t_data.get('source')
            target = t_data.get('target')
            if not source or not target:
                raise FSMError("Transition data is missing 'source' or 'target' field.")
            if source not in self.states:
                raise FSMError(f"Transition source state '{source}' not defined.")
            if target not in self.states:
                raise FSMError(f"Transition target state '{target}' not defined.")
            
            transition = FSMTransition(
                source_name=source,
                target_name=target,
                event=t_data.get('event', ""),
                condition_str=t_data.get('condition', ""),
                actions_str=t_data.get('action', "")
            )
            self.transitions.append(transition)
            
    def _tokenize_actions(self, actions_str: str) -> list[str]:
        """Splits a string of actions (semicolon-separated) into a list of individual action strings."""
        if not actions_str:
            return []
        
        actions = []
        for part in actions_str.split(';'):
            # Remove MATLAB-style comments (%), then strip whitespace
            action = part.split('%', 1)[0].strip()
            if action:
                actions.append(action)
        return actions

    def _execute_code_line(self, code_line: str, context_info: str):
        """
        Executes a single line of action code.
        Tries to parse simple assignments (var = expr), increments (var++),
        decrements (var--). Other code is logged as "executed symbolically".
        """
        code_line = code_line.strip()
        if not code_line:
            return

        self._action_log.append(f"[{context_info}] Processing: {code_line}")

        # 1. Variable assignment: my_var = value_expression
        match_assign = re.fullmatch(r"([a-zA-Z_]\w*)\s*=\s*(.+)", code_line)
        if match_assign:
            var_name = match_assign.group(1)
            expr_str = match_assign.group(2).strip()
            try:
                value = self._evaluate_expression(expr_str)
                self._variables[var_name] = value
                self._action_log.append(f"[{context_info}] Set '{var_name}' = {value} (type: {type(value).__name__})")
            except Exception as e:
                self._action_log.append(f"[{context_info}] Error assigning to '{var_name}': {e}")
            return

        # 2. Increment: my_var++
        match_increment = re.fullmatch(r"([a-zA-Z_]\w*)\s*\+\+", code_line)
        if match_increment:
            var_name = match_increment.group(1)
            if var_name in self._variables and isinstance(self._variables[var_name], (int, float)):
                self._variables[var_name] += 1
                self._action_log.append(f"[{context_info}] Incremented '{var_name}' to {self._variables[var_name]}")
            else:
                self._variables[var_name] = self._variables.get(var_name, 0) + 1 # Initialize if not exists, assumes number
                self._action_log.append(f"[{context_info}] Incremented (or initialized) '{var_name}' to {self._variables[var_name]}")

            return
            
        # 3. Decrement: my_var--
        match_decrement = re.fullmatch(r"([a-zA-Z_]\w*)\s*--", code_line)
        if match_decrement:
            var_name = match_decrement.group(1)
            if var_name in self._variables and isinstance(self._variables[var_name], (int, float)):
                self._variables[var_name] -= 1
                self._action_log.append(f"[{context_info}] Decremented '{var_name}' to {self._variables[var_name]}")
            else:
                self._variables[var_name] = self._variables.get(var_name, 0) - 1 # Initialize if not exists, assumes number
                self._action_log.append(f"[{context_info}] Decremented (or initialized) '{var_name}' to {self._variables[var_name]}")
            return

        # 4. Default: Log as symbolic execution
        self._action_log.append(f"[{context_info}] Executed (symbolically): {code_line}")

    def _evaluate_expression(self, expr_str: str):
        """
        Safely evaluates an expression string (used for RHS of assignments and conditions).
        Handles basic arithmetic, comparisons, and boolean logic.
        """
        # Remove MATLAB-style comments and strip
        expr_str = expr_str.split('%', 1)[0].strip()
        if not expr_str: # Empty expression (e.g. from an empty condition string)
            return True # For conditions, an empty string often means always true. For assignment, this is an error state handled by _execute_code_line.

        # Pythonize boolean literals
        py_expr_str = re.sub(r'\btrue\b', 'True', expr_str, flags=re.IGNORECASE)
        py_expr_str = re.sub(r'\bfalse\b', 'False', py_expr_str, flags=re.IGNORECASE)
        
        # Define a safe environment for eval
        safe_globals = {
            "math": math, "abs": abs, "round": round, "min": min, "max": max, "len": len,
            "str": str, "int": int, "float": float,
            "True": True, "False": False, "None": None,
            # Make some math functions directly available
            "sin": math.sin, "cos": math.cos, "tan": math.tan, "sqrt": math.sqrt,
            "pow": math.pow, "log": math.log, "log10": math.log10, "exp": math.exp
        }
        
        # Use current FSM variables in the expression's local scope
        # Add known mechatronics placeholders with default values to prevent immediate NameErrors for common terms.
        # This is a pragmatic choice for this type of simulator; these aren't truly "executed".
        default_placeholders = {
            "PIN_NUMBER": 0, "DUTY_VALUE_0_255": 0, "ADC_CHANNEL": 0, "TIMER_ID": "T_0", "DURATION_MS": 1000,
            "NEW_VALUE": 0, "CAN_ID": 0, "BYTE1":0, "MOTOR_ID": 0, "SPEED_VALUE":0, "POSITION_TARGET":0,
            "VALVE_ID": 0, "SUBSYSTEM_X": "SYS_X", "BUTTON_NUMBER": 0, "SENSOR_NAME":"sensor", "CHANNEL":"ch0",
            "SIGNAL_NAME":"sigA", "MSG_TYPE_ID":"msg0", "FAULT_CODE":0, "COMMAND_CODE":0, "NOMINAL_MODE": "NOMINAL",
            "MAX_RETRIES":3, "TARGET_STATE_VALUE":1, "MINIMUM_OPERATING_VOLTAGE_MV":3000,
            "SENSOR_MIN_VALID":0, "SENSOR_MAX_VALID":1023, "POSITION_TOLERANCE":0.1, "PIN_FOR_CONDITION":0,
            "VALVE_OPEN_CMD":"OPEN_CMD_STR", "VALVE_CLOSE_CMD":"CLOSE_CMD_STR" # Use strings to avoid type issues in conditions
        }
        eval_locals = default_placeholders.copy()
        eval_locals.update(self._variables) # FSM-defined variables override placeholders

        try:
            # Guard against expression ending with semicolon from an action context
            if py_expr_str.endswith(';'):
                py_expr_str = py_expr_str[:-1].strip()
            
            result = eval(py_expr_str, {"__builtins__": {}}, eval_locals) # Strict eval with controlled scope
            return result
        except NameError as ne:
            # A variable in the expression was not found in FSM variables or placeholders.
            # This usually indicates an FSM design error or reliance on an uninitialized variable.
            err_msg = f"NameError evaluating '{expr_str}' (became '{py_expr_str}'): {ne}. Variable not defined in FSM state or as a known placeholder."
            self._action_log.append(f"[Eval Error] {err_msg}")
            raise FSMError(err_msg) from ne
        except Exception as e:
            err_msg = f"Error evaluating expression '{expr_str}' (became '{py_expr_str}'): {type(e).__name__}: {e}"
            self._action_log.append(f"[Eval Error] {err_msg}")
            raise FSMError(err_msg) from e

    def _process_action_string_for_state(self, actions_str: str, state_name_context: str, action_type_context: str):
        """Helper to tokenize and execute a block of actions for a state."""
        if not actions_str:
            return
        tokenized_actions = self._tokenize_actions(actions_str)
        for action_code in tokenized_actions:
            self._execute_code_line(action_code, f"{state_name_context}:{action_type_context}")

    def reset(self):
        """Resets the FSM to its initial state and clears variables and logs."""
        if not self._initial_state_name: # Should be caught by __init__
            raise FSMError("Initial state name not identified, cannot reset FSM.")
        
        self.current_state_name = self._initial_state_name
        self._variables.clear()
        self._action_log.clear()
        self._action_log.append(f"FSM Reset. Current state: '{self.current_state_name}'")

        initial_state_obj = self.states.get(self.current_state_name)
        if initial_state_obj:
            self._process_action_string_for_state(initial_state_obj.entry_actions_str, self.current_state_name, "Entry")
        else: # Should not happen due to init validation
            raise FSMError(f"Initial state '{self.current_state_name}' object not found during reset.")

    def step(self, event_name: str | None = None, event_payload: dict | None = None) -> tuple[str | None, list[str]]:
        """
        Advances the FSM by one step.
        Processes 'during' actions, then evaluates transitions based on the current event (if any) and conditions.
        If a transition is taken, 'exit' actions of the old state, transition actions, and 'entry' actions
        of the new state are processed in order.

        Args:
            event_name: The name of the event to process. None for internal step/completion transitions.
            event_payload: Optional dictionary of data associated with the event, accessible in conditions/actions.

        Returns:
            A tuple: (new_current_state_name, list_of_actions_executed_in_this_step).
        """
        self._action_log.clear() # Fresh log for this step

        if self.current_state_name is None:
            self._action_log.append("FSM cannot step: Not initialized or in an undefined state.")
            return None, self._action_log

        current_state_obj = self.states.get(self.current_state_name)
        if not current_state_obj: # Should not happen
            raise FSMError(f"Current state '{self.current_state_name}' object is missing.")

        if current_state_obj.is_final and not any(t.source_name == self.current_state_name for t in self.transitions):
             self._action_log.append(f"In final state '{self.current_state_name}' with no outgoing transitions. Simulation halted here.")
             return self.current_state_name, self._action_log

        # 1. Execute 'during' actions of the current state
        self._process_action_string_for_state(current_state_obj.during_actions_str, self.current_state_name, "During")
        
        # Prepare context for expression evaluation, including event payload
        # Note: current _evaluate_expression does not directly use event_payload yet
        # but it's good practice to prepare it. Can be added to `eval_locals`.
        
        # 2. Evaluate transitions
        eligible_transitions = [t for t in self.transitions if t.source_name == self.current_state_name]
        
        transition_to_take = None
        for trans in eligible_transitions:
            event_match = False
            if not trans.event:  # Completion transition (eventless)
                event_match = True
            elif event_name and trans.event.lower() == event_name.lower(): # Exact event name match (case-insensitive)
                event_match = True
            # Future: Could add regex matching for parameterized events like "button(ID)" here.

            if event_match:
                condition_met = False
                if not trans.condition_str: # No condition means true
                    condition_met = True
                    self._action_log.append(f"[Condition] Transition '{trans.event}' from '{trans.source_name}': No condition, assumed True.")
                else:
                    try:
                        eval_result = self._evaluate_expression(trans.condition_str)
                        if isinstance(eval_result, bool):
                            condition_met = eval_result
                            self._action_log.append(f"[Condition] '{trans.condition_str}' from '{trans.source_name}' evaluated to: {condition_met}")
                        else:
                            self._action_log.append(f"[Condition Warning] '{trans.condition_str}' from '{trans.source_name}' evaluated to non-boolean '{eval_result}' (type: {type(eval_result).__name__}). Assuming False.")
                            condition_met = False 
                    except FSMError as e: # Catch evaluation errors specifically
                         self._action_log.append(f"[Condition Error] Evaluating '{trans.condition_str}': {e}. Assuming False.")
                         condition_met = False
                
                if condition_met:
                    transition_to_take = trans
                    break # First valid transition is taken (implicit priority by list order)
        
        if transition_to_take:
            # Perform transition: Exit old -> Transition actions -> Enter new
            self._process_action_string_for_state(current_state_obj.exit_actions_str, self.current_state_name, "Exit")
            
            self._process_action_string_for_state(transition_to_take.actions_str, f"Transition {transition_to_take.source_name}->{transition_to_take.target_name}", "Action")

            old_state_name = self.current_state_name
            self.current_state_name = transition_to_take.target_name
            self._action_log.append(f"Transitioned from '{old_state_name}' to '{self.current_state_name}' (Event: '{event_name or 'completion'}')")

            new_state_obj = self.states.get(self.current_state_name)
            if new_state_obj:
                self._process_action_string_for_state(new_state_obj.entry_actions_str, self.current_state_name, "Entry")
            else: # Should be caught by _parse_diagram_data
                raise FSMError(f"Critical: Transitioned to undefined state '{self.current_state_name}'.")
        else:
            self._action_log.append(f"No eligible transition taken from '{self.current_state_name}' for event '{event_name or '(none)'}'.")

        return self.current_state_name, list(self._action_log) # Return copy of log

    def get_current_state_name(self) -> str | None:
        """Returns the name of the FSM's current state."""
        return self.current_state_name

    def get_variables(self) -> dict:
        """Returns a copy of the FSM's current internal variables."""
        return self._variables.copy()

    def get_last_executed_actions_log(self) -> list[str]:
        """Returns a copy of the log of actions executed in the most recent step."""
        return list(self._action_log)


if __name__ == '__main__':
    # Example Usage (same as in thought process, for quick validation)
    states_def = [
        {'name': 'Idle', 'is_initial': True, 'entry_action': "counter = 0; log_event('Entering Idle'); output = \"Idle mode activated\";", 'during_action': '', 'exit_action': ''},
        {'name': 'Active', 'is_initial': False, 'entry_action': "log_event('Entering Active'); active_timer = 10", 'during_action': 'active_timer = active_timer - 1', 'exit_action': "log_event('Exiting Active');"},
        {'name': 'Error', 'is_initial': False, 'entry_action': "error_code = 1", 'during_action': '', 'exit_action': ''}
    ]
    transitions_def = [
        {'source': 'Idle', 'target': 'Active', 'event': 'START', 'condition': 'counter < 5', 'action': 'counter++ % Increment counter'},
        {'source': 'Active', 'target': 'Idle', 'event': 'STOP', 'condition': '', 'action': ''},
        {'source': 'Active', 'target': 'Idle', 'event': 'TIMEOUT', 'condition': 'active_timer <= 0', 'action': 'log_event("Active state timed out")'},
        {'source': 'Active', 'target': 'Error', 'event': 'FAULT', 'condition': '', 'action': 'fault_info = "critical failure"'},
    ]

    print("--- FSM Simulator Test ---")
    try:
        fsm = FSMSimulator(states_def, transitions_def)
        print(f"Initial State: {fsm.get_current_state_name()}")
        print("Initial Variables:", fsm.get_variables())
        print("Initial Actions Log:")
        for act_log in fsm.get_last_executed_actions_log(): print(f"  {act_log}")
        print("-" * 20)

        def print_step_details(event_name, fsm_instance):
            new_state, actions_log = fsm_instance.step(event_name)
            print(f"\n--- Event: {event_name or '(Internal Step)'} ---")
            print(f"Current State: {new_state}")
            print(f"Variables: {fsm_instance.get_variables()}")
            print("Actions Log for this step:")
            for act_detail in actions_log: print(f"  {act_detail}")
            print("-" * 20)
            return new_state

        current = fsm.get_current_state_name()

        current = print_step_details('START', fsm) # Idle -> Active
        current = print_step_details(None, fsm)    # Active (during action)
        
        # Simulate timer countdown to trigger TIMEOUT
        while fsm.get_variables().get('active_timer', 0) > 0 and current == 'Active':
            current = print_step_details(None, fsm) # During actions primarily
        
        current = print_step_details('TIMEOUT', fsm) # Active -> Idle (due to timer condition)

        # Test FAULT transition
        print_step_details('START', fsm) # To Active
        print_step_details('FAULT', fsm) # To Error

    except FSMError as e:
        print(f"FSM Error: {e}")
    except Exception as e:
        print(f"General Test Error: {type(e).__name__}: {e}")