# enhanced_fsm_simulator.py
import re
import time
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

print("Enhanced FSM Simulator is being imported!")

class FSMError(Exception):
    """Base exception for FSM-related errors"""
    pass

class TransitionError(FSMError):
    """Raised when a transition fails"""
    pass

class StateError(FSMError):
    """Raised when there's an issue with state operations"""
    pass

class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

@dataclass
class FSMMetrics:
    """Tracks FSM execution metrics"""
    total_steps: int = 0
    total_transitions: int = 0
    state_visit_counts: Dict[str, int] = field(default_factory=dict)
    transition_counts: Dict[str, int] = field(default_factory=dict)
    execution_time: float = 0.0
    start_time: Optional[float] = None

@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: float
    level: LogLevel
    message: str
    state: Optional[str] = None
    event: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None

class SafeEvaluator:
    """Safe evaluation context with limited built-ins"""
    
    ALLOWED_BUILTINS = {
        'abs', 'all', 'any', 'bool', 'dict', 'divmod', 'enumerate',
        'filter', 'float', 'format', 'frozenset', 'getattr', 'hasattr',
        'hash', 'hex', 'id', 'int', 'isinstance', 'issubclass', 'iter',
        'len', 'list', 'map', 'max', 'min', 'next', 'oct', 'ord',
        'pow', 'range', 'repr', 'reversed', 'round', 'set', 'setattr',
        'slice', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip'
    }
    
    @classmethod
    def create_safe_context(cls, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Create a safe evaluation context"""
        safe_builtins = {name: getattr(__builtins__, name) 
                        for name in cls.ALLOWED_BUILTINS 
                        if hasattr(__builtins__, name)}
        
        context = variables.copy()
        context['__builtins__'] = safe_builtins
        return context

class EnhancedFSMSimulator:
    """Enhanced Finite State Machine Simulator with improved features"""
    
    def __init__(self, 
                 states_data: List[Dict[str, Any]], 
                 transitions_data: List[Dict[str, Any]],
                 enable_metrics: bool = True,
                 enable_detailed_logging: bool = True,
                 max_steps: int = 10000,
                 validation_mode: bool = True):
        
        self.states_data = states_data
        self.transitions_data = transitions_data
        self.enable_metrics = enable_metrics
        self.enable_detailed_logging = enable_detailed_logging
        self.max_steps = max_steps
        self.validation_mode = validation_mode
        
        # Core state
        self.current_state_name: Optional[str] = None
        self._variables: Dict[str, Any] = {}
        self._step_count = 0
        
        # Logging and metrics
        self._log_entries: List[LogEntry] = []
        self.metrics = FSMMetrics() if enable_metrics else None
        
        # Caching for performance
        self._state_lookup: Dict[str, Dict[str, Any]] = {}
        self._transition_lookup: Dict[str, List[Dict[str, Any]]] = {}
        self._compiled_conditions: Dict[str, Any] = {}
        
        # Event system
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._global_event_handlers: List[Callable] = []
        
        # History tracking
        self._state_history: List[Tuple[str, float]] = []
        self._transition_history: List[Dict[str, Any]] = []
        
        self._initialize()
    
    def _initialize(self):
        """Initialize the FSM"""
        if self.validation_mode:
            self._validate_fsm_data()
        
        self._build_lookup_tables()
        self._find_initial_state()
        
        if self.metrics:
            self.metrics.start_time = time.time()
        
        if self.current_state_name:
            self._execute_entry_actions(self.current_state_name)
            self._record_state_visit(self.current_state_name)
    
    def _validate_fsm_data(self):
        """Validate FSM configuration"""
        if not self.states_data:
            raise FSMError("No states defined in the FSM")
        
        state_names = {state['name'] for state in self.states_data}
        
        # Check for duplicate state names
        if len(state_names) != len(self.states_data):
            raise FSMError("Duplicate state names found")
        
        # Validate transitions reference valid states
        for trans in self.transitions_data:
            if trans['source'] not in state_names:
                raise FSMError(f"Transition references unknown source state: {trans['source']}")
            if trans['target'] not in state_names:
                raise FSMError(f"Transition references unknown target state: {trans['target']}")
        
        # Check for initial state
        initial_states = [s for s in self.states_data if s.get('is_initial', False)]
        if len(initial_states) > 1:
            raise FSMError("Multiple initial states defined")
    
    def _build_lookup_tables(self):
        """Build lookup tables for performance"""
        # State name to state data mapping
        self._state_lookup = {state['name']: state for state in self.states_data}
        
        # Source state to transitions mapping
        self._transition_lookup = {}
        for trans in self.transitions_data:
            source = trans['source']
            if source not in self._transition_lookup:
                self._transition_lookup[source] = []
            self._transition_lookup[source].append(trans)
    
    def _log(self, level: LogLevel, message: str, **kwargs):
        """Enhanced logging with structured data"""
        if not self.enable_detailed_logging and level != LogLevel.ERROR:
            return
        
        entry = LogEntry(
            timestamp=time.time(),
            level=level,
            message=message,
            state=self.current_state_name,
            **kwargs
        )
        self._log_entries.append(entry)
    
    def _find_initial_state(self):
        """Find and set the initial state"""
        for state_dict in self.states_data:
            if state_dict.get('is_initial', False):
                self.current_state_name = state_dict['name']
                self._log(LogLevel.INFO, f"Initial state set to: {self.current_state_name}")
                return
        
        if self.states_data:
            self.current_state_name = self.states_data[0]['name']
            self._log(LogLevel.WARNING, f"No initial state defined. Using first state: {self.current_state_name}")
        else:
            raise StateError("No states defined in the FSM")
    
    def _get_state_data(self, state_name: str) -> Optional[Dict[str, Any]]:
        """Get state data by name (cached lookup)"""
        return self._state_lookup.get(state_name)
    
    def _evaluate_condition(self, condition_str: str) -> bool:
        """Safely evaluate a condition with caching"""
        if not condition_str or condition_str.strip() == "":
            return True
        
        # Use cached compiled condition if available
        if condition_str in self._compiled_conditions:
            compiled_condition = self._compiled_conditions[condition_str]
        else:
            try:
                compiled_condition = compile(condition_str, '<condition>', 'eval')
                self._compiled_conditions[condition_str] = compiled_condition
            except SyntaxError as e:
                self._log(LogLevel.ERROR, f"Syntax error in condition '{condition_str}': {e}")
                return False
        
        try:
            context = SafeEvaluator.create_safe_context(self._variables)
            result = eval(compiled_condition, context)
            self._log(LogLevel.DEBUG, f"Condition '{condition_str}' evaluated to: {result}")
            return bool(result)
        except Exception as e:
            self._log(LogLevel.ERROR, f"Error evaluating condition '{condition_str}': {e}")
            return False
    
    def _execute_action(self, action_str: str):
        """Safely execute an action"""
        if not action_str or action_str.strip() == "":
            return
        
        try:
            context = SafeEvaluator.create_safe_context(self._variables)
            
            # Split by semicolon and execute each statement
            statements = [stmt.strip() for stmt in action_str.split(';') if stmt.strip()]
            
            for stmt in statements:
                self._log(LogLevel.DEBUG, f"Executing: {stmt}")
                exec(stmt, context)
            
            # Update variables, excluding builtins
            for var_name, var_value in context.items():
                if var_name != '__builtins__':
                    if var_name not in self._variables or self._variables[var_name] != var_value:
                        self._log(LogLevel.DEBUG, f"Variable '{var_name}' updated to: {var_value}")
                        self._variables[var_name] = var_value
                        
        except Exception as e:
            self._log(LogLevel.ERROR, f"Error executing action '{action_str}': {e}")
    
    def _execute_entry_actions(self, state_name: str):
        """Execute entry actions for a state"""
        state_data = self._get_state_data(state_name)
        if state_data and state_data.get('entry_action'):
            self._log(LogLevel.INFO, f"Executing entry actions for '{state_name}'")
            self._execute_action(state_data['entry_action'])
    
    def _execute_exit_actions(self, state_name: str):
        """Execute exit actions for a state"""
        state_data = self._get_state_data(state_name)
        if state_data and state_data.get('exit_action'):
            self._log(LogLevel.INFO, f"Executing exit actions for '{state_name}'")
            self._execute_action(state_data['exit_action'])
    
    def _execute_during_actions(self, state_name: str):
        """Execute during actions for a state"""
        state_data = self._get_state_data(state_name)
        if state_data and state_data.get('during_action'):
            self._log(LogLevel.DEBUG, f"Executing during actions for '{state_name}'")
            self._execute_action(state_data['during_action'])
    
    def _record_state_visit(self, state_name: str):
        """Record state visit for metrics and history"""
        if self.metrics:
            self.metrics.state_visit_counts[state_name] = \
                self.metrics.state_visit_counts.get(state_name, 0) + 1
        
        self._state_history.append((state_name, time.time()))
    
    def _record_transition(self, from_state: str, to_state: str, event: Optional[str]):
        """Record transition for metrics and history"""
        transition_key = f"{from_state}->{to_state}"
        
        if self.metrics:
            self.metrics.total_transitions += 1
            self.metrics.transition_counts[transition_key] = \
                self.metrics.transition_counts.get(transition_key, 0) + 1
        
        self._transition_history.append({
            'from': from_state,
            'to': to_state,
            'event': event,
            'timestamp': time.time()
        })
    
    def _trigger_event_handlers(self, event_name: str):
        """Trigger registered event handlers"""
        # Global handlers
        for handler in self._global_event_handlers:
            try:
                handler(self, event_name)
            except Exception as e:
                self._log(LogLevel.ERROR, f"Error in global event handler: {e}")
        
        # Specific event handlers
        if event_name in self._event_handlers:
            for handler in self._event_handlers[event_name]:
                try:
                    handler(self, event_name)
                except Exception as e:
                    self._log(LogLevel.ERROR, f"Error in event handler for '{event_name}': {e}")
    
    def step(self, event_name: Optional[str] = None) -> Tuple[str, List[LogEntry]]:
        """Execute one step of the FSM"""
        if not self.current_state_name:
            raise StateError("Cannot step, FSM is not in a valid state")
        
        if self._step_count >= self.max_steps:
            raise FSMError(f"Maximum steps ({self.max_steps}) exceeded. Possible infinite loop.")
        
        self._step_count += 1
        if self.metrics:
            self.metrics.total_steps += 1
        
        self._log(LogLevel.INFO, f"Step {self._step_count}: Current state: {self.current_state_name}, Event: {event_name or 'None'}")
        
        # Trigger event handlers
        if event_name:
            self._trigger_event_handlers(event_name)
        
        # Execute during actions
        self._execute_during_actions(self.current_state_name)
        
        # Find eligible transition
        eligible_transition = self._find_eligible_transition(event_name)
        
        if eligible_transition:
            self._execute_transition(eligible_transition, event_name)
        else:
            self._log(LogLevel.DEBUG, f"No eligible transition found for event '{event_name or 'None'}'")
        
        # Return current logs and clear them
        current_logs = self._log_entries.copy()
        self._log_entries.clear()
        
        return self.current_state_name, current_logs
    
    def _find_eligible_transition(self, event_name: Optional[str]) -> Optional[Dict[str, Any]]:
        """Find the first eligible transition from current state"""
        transitions = self._transition_lookup.get(self.current_state_name, [])
        
        for trans in transitions:
            event_on_trans = trans.get('event')
            
            # Check if event matches
            event_match = (
                not event_on_trans or  # No event specified on transition
                event_on_trans == event_name or  # Exact match
                (event_on_trans == '*' and event_name is not None)  # Wildcard match
            )
            
            if event_match:
                self._log(LogLevel.DEBUG, f"Checking transition to '{trans['target']}'")
                if self._evaluate_condition(trans.get('condition', '')):
                    return trans
        
        return None
    
    def _execute_transition(self, transition: Dict[str, Any], event_name: Optional[str]):
        """Execute a transition"""
        old_state = self.current_state_name
        new_state = transition['target']
        
        try:
            # Exit actions for current state
            self._execute_exit_actions(old_state)
            
            # Transition action
            if transition.get('action'):
                self._log(LogLevel.INFO, f"Executing transition action")
                self._execute_action(transition['action'])
            
            # Change state
            self.current_state_name = new_state
            self._log(LogLevel.INFO, f"Transitioned from '{old_state}' to '{new_state}'")
            
            # Record transition
            self._record_transition(old_state, new_state, event_name)
            self._record_state_visit(new_state)
            
            # Entry actions for new state
            self._execute_entry_actions(new_state)
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Error during transition: {e}")
            raise TransitionError(f"Failed to transition from '{old_state}' to '{new_state}': {e}")
    
    def run_until_stable(self, max_steps: Optional[int] = None) -> List[str]:
        """Run the FSM until no more transitions occur"""
        if max_steps is None:
            max_steps = self.max_steps
        
        states_visited = [self.current_state_name]
        steps = 0
        
        while steps < max_steps:
            old_state = self.current_state_name
            self.step()
            steps += 1
            
            if self.current_state_name == old_state:
                # No transition occurred
                break
            
            states_visited.append(self.current_state_name)
        
        return states_visited
    
    def add_event_handler(self, event_name: str, handler: Callable):
        """Add an event handler for specific events"""
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)
    
    def add_global_event_handler(self, handler: Callable):
        """Add a global event handler (called for all events)"""
        self._global_event_handlers.append(handler)
    
    def get_current_state(self) -> str:
        """Get current state name"""
        return self.current_state_name
    
    def get_variables(self) -> Dict[str, Any]:
        """Get copy of all variables"""
        return self._variables.copy()
    
    def set_variable(self, name: str, value: Any):
        """Set a variable value"""
        self._variables[name] = value
        self._log(LogLevel.DEBUG, f"Variable '{name}' set to: {value}")
    
    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a variable value"""
        return self._variables.get(name, default)
    
    def get_metrics(self) -> Optional[FSMMetrics]:
        """Get execution metrics"""
        if self.metrics and self.metrics.start_time:
            self.metrics.execution_time = time.time() - self.metrics.start_time
        return self.metrics
    
    def get_state_history(self) -> List[Tuple[str, float]]:
        """Get state visit history"""
        return self._state_history.copy()
    
    def get_transition_history(self) -> List[Dict[str, Any]]:
        """Get transition history"""
        return self._transition_history.copy()
    
    def reset(self):
        """Reset the FSM to initial state"""
        self._log(LogLevel.INFO, "Resetting FSM")
        
        # Clear state
        self._variables.clear()
        self._step_count = 0
        self.current_state_name = None
        
        # Clear history
        self._state_history.clear()
        self._transition_history.clear()
        self._log_entries.clear()
        
        # Reset metrics
        if self.metrics:
            self.metrics = FSMMetrics()
            self.metrics.start_time = time.time()
        
        # Reinitialize
        self._find_initial_state()
        if self.current_state_name:
            self._execute_entry_actions(self.current_state_name)
            self._record_state_visit(self.current_state_name)
    
    def export_state(self) -> Dict[str, Any]:
        """Export current FSM state for persistence"""
        return {
            'current_state': self.current_state_name,
            'variables': self._variables.copy(),
            'step_count': self._step_count,
            'metrics': self.metrics.__dict__ if self.metrics else None
        }
    
    def import_state(self, state_data: Dict[str, Any]):
        """Import FSM state from exported data"""
        self.current_state_name = state_data.get('current_state')
        self._variables = state_data.get('variables', {}).copy()
        self._step_count = state_data.get('step_count', 0)
        
        if self.metrics and state_data.get('metrics'):
            for key, value in state_data['metrics'].items():
                if hasattr(self.metrics, key):
                    setattr(self.metrics, key, value)
    
    def __str__(self) -> str:
        """String representation of FSM state"""
        return (f"FSM(current_state='{self.current_state_name}', "
                f"variables={len(self._variables)}, "
                f"steps={self._step_count})")
    
    def __repr__(self) -> str:
        return self.__str__()