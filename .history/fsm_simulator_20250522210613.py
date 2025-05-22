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
    It can also handle basic event payloads for conditions.
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
        self._mock_functions: dict[str, callable] = {} # For future stub/mock functions

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
            action = part.split('%', 1)[0].strip() # Remove MATLAB-style comments (%), then strip
            if action:
                actions.append(action)
        return actions

    def _execute_code_line(self, code_line: str, context_info: str, event_payload: dict | None = None):
        """
        Executes a single line of action code.
        Tries to parse simple assignments (var = expr), increments (var++),
        decrements (var--), or calls registered mock functions.
        Other code is logged as "executed symbolically".
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
                # Pass event_payload for expressions in actions (e.g. var = event_param)
                value = self._evaluate_expression(expr_str, event_payload)
                self._variables[var_name] = value
                self._action_log.append(f"[{context_info}] Set '{var_name}' = {value} (type: {type(value).__name__})")
            except Exception as e:
                self._action_log.append(f"[{context_info}] Error assigning to '{var_name}': {e}")
            return

        # 2. Increment: my_var++
        match_increment = re.fullmatch(r"([a-zA-Z_]\w*)\s*\+\+", code_line)
        if match_increment:
            var_name = match_increment.group(1)
            current_val = self._variables.get(var_name, 0) # Default to 0 if not exists
            if isinstance(current_val, (int, float)):
                self._variables[var_name] = current_val + 1
                self._action_log.append(f"[{context_info}] Incremented '{var_name}' to {self._variables[var_name]}")
            else: # Variable exists but is not a number, try to initialize
                self._variables[var_name] = 1 
                self._action_log.append(f"[{context_info}] Initialized and incremented '{var_name}' to 1 (was non-numeric: {current_val})")
            return
            
        # 3. Decrement: my_var--
        match_decrement = re.fullmatch(r"([a-zA-Z_]\w*)\s*--", code_line)
        if match_decrement:
            var_name = match_decrement.group(1)
            current_val = self._variables.get(var_name, 0) # Default to 0 if not exists
            if isinstance(current_val, (int, float)):
                self._variables[var_name] = current_val - 1
                self._action_log.append(f"[{context_info}] Decremented '{var_name}' to {self._variables[var_name]}")
            else: # Variable exists but is not a number, try to initialize
                self._variables[var_name] = -1
                self._action_log.append(f"[{context_info}] Initialized and decremented '{var_name}' to -1 (was non-numeric: {current_val})")
            return

        # 4. Mock Function Call: func_name(arg1, arg2_expr, ...)
        match_func_call = re.fullmatch(r"([a-zA-Z_]\w*)\s*\((.*)\)", code_line)
        if match_func_call:
            func_name = match_func_call.group(1)
            args_str = match_func_call.group(2).strip()

            if func_name in self._mock_functions:
                parsed_args = []
                if args_str:
                    # Super basic arg parsing: split by comma, then eval each part
                    # This is simplistic and won't handle complex args like nested calls or strings with commas well
                    raw_arg_parts = args_str.split(',')
                    for arg_part_str in raw_arg_parts:
                        try:
                            parsed_args.append(self._evaluate_expression(arg_part_str.strip(), event_payload))
                        except Exception as e:
                            self._action_log.append(f"[{context_info}] Error evaluating argument '{arg_part_str.strip()}' for function '{func_name}': {e}. Skipping call.")
                            return # Abort function call if an arg fails to evaluate
                try:
                    result = self._mock_functions[func_name](*parsed_args) # Call the mock
                    self._action_log.append(f"[{context_info}] Called mock function '{func_name}({', '.join(map(repr, parsed_args))})'. Result: {result if result is not None else '(No explicit result)'}")
                    # Potentially allow mock functions to return a value and assign it to a variable:
                    # For e.g. result_var = my_mock_func(arg)
                    # This would require a different regex. Current handles `my_mock_func(arg)` directly.
                except Exception as e:
                    self._action_log.append(f"[{context_info}] Error calling mock function '{func_name}': {type(e).__name__}: {e}")
                return
            # else: func_name not in mock_functions, falls through to symbolic execution

        # 5. Default: Log as symbolic execution
        self._action_log.append(f"[{context_info}] Executed (symbolically): {code_line}")

    def _evaluate_expression(self, expr_str: str, event_payload: dict | None = None):
        """
        Safely evaluates an expression string (used for RHS of assignments and conditions).
        Handles basic arithmetic, comparisons, boolean logic, and event payload variables.
        """
        expr_str = expr_str.split('%', 1)[0].strip() # Remove MATLAB-style comments and strip
        if not expr_str:
            return True # For conditions, an empty string implies true.

        py_expr_str = re.sub(r'\btrue\b', 'True', expr_str, flags=re.IGNORECASE)
        py_expr_str = re.sub(r'\bfalse\b', 'False', py_expr_str, flags=re.IGNORECASE)
        
        safe_globals = {
            "math": math, "abs": abs, "round": round, "min": min, "max": max, "len": len,
            "str": str, "int": int, "float": float,
            "True": True, "False": False, "None": None,
            "sin": math.sin, "cos": math.cos, "tan": math.tan, "sqrt": math.sqrt,
            "pow": math.pow, "log": math.log, "log10": math.log10, "exp": math.exp
        }
        
        default_placeholders = {
            "PIN_NUMBER": 0, "DUTY_VALUE_0_255": 0, "ADC_CHANNEL": 0, "TIMER_ID": "T_0", "DURATION_MS": 1000,
            "NEW_VALUE": 0, "CAN_ID": 0, "BYTE1":0, "MOTOR_ID": 0, "SPEED_VALUE":0, "POSITION_TARGET":0,
            "VALVE_ID": 0, "SUBSYSTEM_X": "SYS_X", "BUTTON_NUMBER": 0, "SENSOR_NAME":"sensor", "CHANNEL":"ch0",
            "SIGNAL_NAME":"sigA", "MSG_TYPE_ID":"msg0", "FAULT_CODE":0, "COMMAND_CODE":0, "NOMINAL_MODE": "NOMINAL",
            "MAX_RETRIES":3, "TARGET_STATE_VALUE":1, "MINIMUM_OPERATING_VOLTAGE_MV":3000,
            "SENSOR_MIN_VALID":0, "SENSOR_MAX_VALID":1023, "POSITION_TOLERANCE":0.1, "PIN_FOR_CONDITION":0,
            "VALVE_OPEN_CMD":"OPEN_CMD_STR", "VALVE_CLOSE_CMD":"CLOSE_CMD_STR"
        }
        eval_locals = default_placeholders.copy()
        if event_payload: # Add event payload variables
            eval_locals.update(event_payload)
        eval_locals.update(self._variables) # FSM-defined variables override

        try:
            if py_expr_str.endswith(';'): # Guard against expression ending with semicolon
                py_expr_str = py_expr_str[:-1].strip()
            
            result = eval(py_expr_str, {"__builtins__": {}}, eval_locals) # Strict eval
            return result
        except NameError as ne:
            err_msg = f"NameError evaluating '{expr_str}' (became '{py_expr_str}'): {ne}. Variable not defined in FSM state, event payload, or placeholders."
            self._action_log.append(f"[Eval Error] {err_msg}")
            raise FSMError(err_msg) from ne
        except Exception as e:
            err_msg = f"Error evaluating expression '{expr_str}' (became '{py_expr_str}'): {type(e).__name__}: {e}"
            self._action_log.append(f"[Eval Error] {err_msg}")
            raise FSMError(err_msg) from e

    def _process_action_string_for_state(self, actions_str: str, state_name_context: str, action_type_context: str, event_payload: dict | None = None):
        """Helper to tokenize and execute a block of actions for a state, passing event_payload."""
        if not actions_str:
            return
        tokenized_actions = self._tokenize_actions(actions_str)
        for action_code in tokenized_actions:
            self._execute_code_line(action_code, f"{state_name_context}:{action_type_context}", event_payload)

    def reset(self):
        """Resets the FSM to its initial state and clears variables and logs."""
        if not self._initial_state_name:
            raise FSMError("Initial state name not identified, cannot reset FSM.")
        
        self.current_state_name = self._initial_state_name
        self._variables.clear()
        self._action_log.clear()
        self._action_log.append(f"FSM Reset. Current state: '{self.current_state_name}'")

        initial_state_obj = self.states.get(self.current_state_name)
        if initial_state_obj:
            # Entry actions on reset typically don't have an associated event payload
            self._process_action_string_for_state(initial_state_obj.entry_actions_str, self.current_state_name, "Entry", None)
        else:
            raise FSMError(f"Initial state '{self.current_state_name}' object not found during reset.")

    def step(self, event_name: str | None = None, event_payload: dict | None = None) -> tuple[str | None, list[str]]:
        """
        Advances the FSM by one step.
        Args:
            event_name: The name of the event to process. None for internal step.
            event_payload: Optional dictionary of data associated with the event.
        Returns:
            A tuple: (new_current_state_name, list_of_actions_executed_in_this_step).
        """
        self._action_log.clear()

        if self.current_state_name is None:
            self._action_log.append("FSM cannot step: Not initialized or in an undefined state.")
            return None, self._action_log

        current_state_obj = self.states.get(self.current_state_name)
        if not current_state_obj:
            raise FSMError(f"Current state '{self.current_state_name}' object is missing.")

        if current_state_obj.is_final and not any(t.source_name == self.current_state_name for t in self.transitions):
             self._action_log.append(f"In final state '{self.current_state_name}' with no outgoing transitions. Simulation halted here.")
             return self.current_state_name, self._action_log

        self._process_action_string_for_state(current_state_obj.during_actions_str, self.current_state_name, "During", event_payload)
        
        eligible_transitions = [t for t in self.transitions if t.source_name == self.current_state_name]
        transition_to_take = None
        for trans in eligible_transitions:
            event_match = False
            # Check for parameterized events or exact matches
            # Simple approach: if event_name is like "data_event(param=value)" and trans.event is "data_event"
            # This is a basic placeholder for more advanced event parsing if needed.
            # Current behavior: exact event name match or completion.
            if not trans.event:
                event_match = True
            elif event_name:
                if trans.event.lower() == event_name.lower(): # Exact match
                     event_match = True
                # Future: Add regex or prefix matching for parameterized events here.
                # e.g. if event_name.startswith(trans.event.split('(')[0]) for events like func_name(params)
                
            if event_match:
                condition_met = False
                if not trans.condition_str:
                    condition_met = True
                    self._action_log.append(f"[Condition] Transition '{trans.event}' from '{trans.source_name}': No condition, assumed True.")
                else:
                    try:
                        eval_result = self._evaluate_expression(trans.condition_str, event_payload)
                        if isinstance(eval_result, bool):
                            condition_met = eval_result
                            self._action_log.append(f"[Condition] '{trans.condition_str}' (from '{trans.source_name}') evaluated to: {condition_met}")
                        else:
                            self._action_log.append(f"[Condition Warning] '{trans.condition_str}' (from '{trans.source_name}') evaluated to non-boolean '{eval_result}'. Assuming False.")
                            condition_met = False 
                    except FSMError as e:
                         self._action_log.append(f"[Condition Error] Evaluating '{trans.condition_str}': {e}. Assuming False.")
                         condition_met = False
                
                if condition_met:
                    transition_to_take = trans
                    break
        
        if transition_to_take:
            self._process_action_string_for_state(current_state_obj.exit_actions_str, self.current_state_name, "Exit", event_payload)
            self._process_action_string_for_state(transition_to_take.actions_str, f"Transition {transition_to_take.source_name}->{transition_to_take.target_name}", "Action", event_payload)

            old_state_name = self.current_state_name
            self.current_state_name = transition_to_take.target_name
            self._action_log.append(f"Transitioned from '{old_state_name}' to '{self.current_state_name}' (Event: '{event_name or 'completion'}')")

            new_state_obj = self.states.get(self.current_state_name)
            if new_state_obj:
                self._process_action_string_for_state(new_state_obj.entry_actions_str, self.current_state_name, "Entry", event_payload) # Pass payload for entry actions too
            else:
                raise FSMError(f"Critical: Transitioned to undefined state '{self.current_state_name}'.")
        else:
            self._action_log.append(f"No eligible transition taken from '{self.current_state_name}' for event '{event_name or '(none)'}'.")

        return self.current_state_name, list(self._action_log)

    def get_current_state_name(self) -> str | None:
        return self.current_state_name

    def get_variables(self) -> dict:
        return self._variables.copy()

    def get_last_executed_actions_log(self) -> list[str]:
        return list(self._action_log)

    def register_mock_function(self, name: str, func: callable):
        """Registers a Python callable as a mock function for the simulator."""
        if not callable(func):
            raise ValueError(f"Provided mock for '{name}' is not callable.")
        self._mock_functions[name] = func
        self._action_log.append(f"[System] Mock function '{name}' registered.")

    def unregister_mock_function(self, name: str):
        """Unregisters a mock function."""
        if name in self._mock_functions:
            del self._mock_functions[name]
            self._action_log.append(f"[System] Mock function '{name}' unregistered.")

if __name__ == '__main__':
    # Example Usage
    states_def = [
        {'name': 'Idle', 'is_initial': True, 'entry_action': "counter = 0; status_msg = 'System Idle'; mock_log('Entering Idle');", 'during_action': '', 'exit_action': "mock_log('Exiting Idle');"},
        {'name': 'Armed', 'is_initial': False, 'entry_action': "mock_set_led('RED', 1); arm_timer = 100; status_msg = 'System Armed';", 'during_action': 'arm_timer = arm_timer - 10; mock_check_sensor()', 'exit_action': "mock_set_led('RED', 0);"},
        {'name': 'Active', 'is_initial': False, 'entry_action': "mock_set_motor(50); status_msg = 'Motor Active';", 'during_action': "mock_log('Motor running'); duration = duration - 1", 'exit_action': "mock_set_motor(0);"},
        {'name': 'ErrorState', 'is_initial': False, 'entry_action': "error_code = current_fault; status_msg = 'System Error';", 'during_action': '', 'exit_action': ''}
    ]
    transitions_def = [
        {'source': 'Idle', 'target': 'Armed', 'event': 'ARM_CMD', 'condition': 'counter < 3', 'action': 'counter++'},
        {'source': 'Armed', 'target': 'Active', 'event': 'TRIGGER', 'condition': 'sensor_val > threshold && arm_timer > 0', 'action': 'duration = 20; threshold = 100'}, # Added threshold var
        {'source': 'Armed', 'target': 'Idle', 'event': 'DISARM_CMD', 'condition': '', 'action': ''},
        {'source': 'Armed', 'target': 'Idle', 'event': 'TIMEOUT', 'condition': 'arm_timer <= 0', 'action': "mock_log('Arming timed out')"},
        {'source': 'Active', 'target': 'Idle', 'event': 'STOP_CMD', 'condition': '', 'action': "mock_log('Motor stopping by command')"},
        {'source': 'Active', 'target': 'Idle', 'event': '', 'condition': 'duration <= 0', 'action': "mock_log('Active duration complete')"}, # Completion transition
        {'source': 'Idle', 'target': 'ErrorState', 'event': 'FAULT_DETECTED', 'condition': 'is_critical_fault == True', 'action': 'current_fault = fault_id'},
        {'source': 'Armed', 'target': 'ErrorState', 'event': 'FAULT_DETECTED', 'condition': '', 'action': 'current_fault = fault_id'},
        {'source': 'Active', 'target': 'ErrorState', 'event': 'FAULT_DETECTED', 'condition': '', 'action': 'current_fault = fault_id'},
    ]

    print("--- FSM Simulator Test with Mocks and Event Payload ---")
    
    # Define some simple mock Python functions
    mock_hardware_state = {'LED_RED': 0, 'MOTOR_SPEED': 0, 'LOGS': []}
    def my_mock_log(message):
        mock_hardware_state['LOGS'].append(f"[SIM_LOG] {message}")
        # print(f"    Mock Logged: {message}") # Optional immediate print
        return len(mock_hardware_state['LOGS'])

    def my_mock_set_led(color, state):
        if color.upper() == 'RED':
            mock_hardware_state['LED_RED'] = int(state)
        # print(f"    Mock Set LED {color} to {state}")

    def my_mock_set_motor(speed):
        mock_hardware_state['MOTOR_SPEED'] = int(speed)
        # print(f"    Mock Set Motor Speed to {speed}")

    def my_mock_check_sensor():
        # Simulate sensor check, maybe update a variable
        if 'sensor_val' not in fsm._variables: # Access internal for demo, better via method if exists
            fsm._variables['sensor_val'] = 50 # Default sensor value
        fsm._variables['sensor_val'] += 5 # Sensor value slowly rising
        # print(f"    Mock Checked Sensor. Value is now: {fsm._variables['sensor_val']}")


    try:
        fsm = FSMSimulator(states_def, transitions_def)
        fsm.register_mock_function("mock_log", my_mock_log)
        fsm.register_mock_function("mock_set_led", my_mock_set_led)
        fsm.register_mock_function("mock_set_motor", my_mock_set_motor)
        fsm.register_mock_function("mock_check_sensor", my_mock_check_sensor)


        # Initialize some external FSM variables (e.g. parameters from system)
        fsm._variables['threshold'] = 70 # Needs to be visible for conditions/actions
        fsm._variables['is_critical_fault'] = False
        fsm._variables['fault_id'] = "NO_FAULT"

        print(f"Initial State: {fsm.get_current_state_name()}")
        print("Initial FSM Variables:", fsm.get_variables())
        print("Initial Mock Hardware State:", mock_hardware_state)
        print("Initial Actions Log (from reset):")
        for act_log in fsm.get_last_executed_actions_log(): print(f"  {act_log}")
        print("-" * 20)

        def print_step_info(fsm_instance, event_n=None, event_p=None):
            print(f"\n--- STEP --- Event: '{event_n or '(internal)'}' --- Payload: {event_p or '{}'} ---")
            state_before = fsm_instance.get_current_state_name()
            vars_before = fsm_instance.get_variables()
            
            new_state, log = fsm_instance.step(event_name=event_n, event_payload=event_p)
            
            print(f"State Before: {state_before} -> State After: {new_state}")
            print(f"FSM Variables Before: {vars_before}")
            print(f"FSM Variables After: {fsm_instance.get_variables()}")
            print(f"Mock Hardware After: {mock_hardware_state}")
            print("Log for this step:")
            for entry in log: print(f"  {entry}")
            print("-" * 30)
            return new_state

        # Scenario: Arm, sensor triggers, active runs out, then fault
        print_step_info(fsm, 'ARM_CMD')                      # Idle -> Armed
        while fsm.get_variables().get('arm_timer', 0) > 0 and fsm.get_current_state_name() == 'Armed' and fsm.get_variables().get('sensor_val', 0) <= fsm.get_variables().get('threshold', 1000):
             print_step_info(fsm) # During actions in Armed (sensor check, timer decrement)
        
        # If sensor became > threshold while arm_timer > 0, TRIGGER event should work
        if fsm.get_variables().get('sensor_val', 0) > fsm.get_variables().get('threshold', 0) and fsm.get_variables().get('arm_timer',0) >0 :
            print_step_info(fsm, 'TRIGGER')                   # Armed -> Active
        else: # Condition for trigger might not have met, or it timed out
             print_step_info(fsm, 'TIMEOUT') # Check timeout condition explicitly if needed, or just let it flow
             print("Sensor did not exceed threshold in time or arming timed out.")


        while fsm.get_variables().get('duration', 0) > 0 and fsm.get_current_state_name() == 'Active':
            print_step_info(fsm)                           # Active (during action, duration decrement)
                                                           # Will eventually take completion transition Active -> Idle
        
        # Ensure it's back in Idle due to completion, or force it
        if fsm.get_current_state_name() != "Idle":
             print_step_info(fsm) # One more step to ensure completion transition is processed
        
        print("\n--- Injecting a FAULT ---")
        fsm._variables['is_critical_fault'] = True # Set condition for fault
        print_step_info(fsm, 'FAULT_DETECTED', {'fault_id': 'PWR_FAIL', 'severity': 10}) # Idle -> ErrorState
                                                                        # Note: 'severity' in payload isn't used by current logic, but good for demo

    except FSMError as e:
        print(f"FSM Error: {e}")
    except Exception as e:
        import traceback
        print(f"General Test Error: {type(e).__name__}: {e}")
        traceback.print_exc()