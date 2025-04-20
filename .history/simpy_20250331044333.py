import simpy
import random

class StateMachineSimulation:
    def __init__(self, env):
        self.env = env
        self.current_state = None
        self.transitions = {}  # {source: [(target, probability, delay), ...]}
        self.final_states = set()
        self.state_actions = {}  # {state: [action_functions]}
        
    def add_transition(self, source, target, probability=1.0, delay=1.0):
        """Add a transition between states with probability and delay"""
        if source not in self.transitions:
            self.transitions[source] = []
        self.transitions[source].append((target, probability, delay))
        
    def add_state_action(self, state, action_func):
        """Add an action to be executed when entering a state"""
        if state not in self.state_actions:
            self.state_actions[state] = []
        self.state_actions[state].append(action_func)
        
    def add_final_state(self, state):
        """Mark a state as final (termination state)"""
        self.final_states.add(state)
        
    def set_initial_state(self, state):
        """Set the initial state of the machine"""
        self.current_state = state
        self._execute_state_actions(state)
        
    def _execute_state_actions(self, state):
        """Execute all actions associated with entering a state"""
        if state in self.state_actions:
            for action in self.state_actions[state]:
                action()
                
    def run(self):
        """Main simulation process"""
        while self.current_state not in self.final_states:
            yield self.env.process(self.step())
        print(f"Reached final state: {self.current_state}")
        
    def step(self):
        """Process one state transition"""
        if self.current_state not in self.transitions:
            print(f"No transitions from state {self.current_state}")
            return
            
        # Normalize probabilities
        total_prob = sum(prob for _, prob, _ in self.transitions[self.current_state])
        if total_prob <= 0:
            print(f"No valid transitions from {self.current_state}")
            return
            
        # Select transition
        r = random.random() * total_prob
        cumulative_prob = 0
        
        for target, prob, delay in self.transitions[self.current_state]:
            cumulative_prob += prob
            if r <= cumulative_prob:
                print(f"Transition: {self.current_state} -> {target} (delay: {delay})")
                yield self.env.timeout(delay)
                self.current_state = target
                self._execute_state_actions(target)
                return
                
        print(f"No transition selected from {self.current_state}")

def main():
    # Create simulation environment
    env = simpy.Environment()
    
    # Create state machine
    sm = StateMachineSimulation(env)
    
    # Define states and transitions
    sm.set_initial_state('idle')
    
    # Add state actions
    sm.add_state_action('idle', lambda: print("System is idle"))
    sm.add_state_action('moving', lambda: print("System is moving"))
    sm.add_state_action('stopped', lambda: print("System has stopped"))
    
    # Add transitions (source, target, probability, delay)
    sm.add_transition('idle', 'moving', 0.7, 2.0)
    sm.add_transition('idle', 'stopped', 0.3, 1.0)
    sm.add_transition('moving', 'stopped', 1.0, 3.0)
    
    # Set final state
    sm.add_final_state('stopped')
    
    # Run simulation
    env.process(sm.run())
    env.run(until=20)  # Run for max 20 time units

if __name__ == '__main__':
    main()