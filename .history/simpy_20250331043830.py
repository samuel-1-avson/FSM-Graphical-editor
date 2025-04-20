import simpy
import random

class StateMachineSimulation:
    def __init__(self, env):
        self.env = env
        self.current_state = None
        self.transitions = {}
        self.final_states = set()

    def add_transition(self, source, target, probability=1.0, delay=1.0):
        if source not in self.transitions:
            self.transitions[source] = []
        self.transitions[source].append((target, probability, delay))

    def add_final_state(self, state):
        self.final_states.add(state)

    def set_initial_state(self, state):
        self.current_state = state

    def run(self):
        while self.current_state not in self.final_states:
            yield self.env.process(self.step())

    def step(self):
        if self.current_state not in self.transitions:
            return
            
        transitions = self.transitions[self.current_state]
        # Select transition based on probability
        r = random.random()
        cumulative_prob = 0
        selected_transition = None
        
        for target, prob, delay in transitions:
            cumulative_prob += prob
            if r <= cumulative_prob:
                selected_transition = (target, delay)
                break
        
        if selected_transition:
            target, delay = selected_transition
            print(f"Transitioning from {self.current_state} to {target} with delay {delay}")
            yield self.env.timeout(delay)
            self.current_state = target

# Example usage
def main():
    env = simpy.Environment()
    sm = StateMachineSimulation(env)

    # Set initial state
    sm.set_initial_state('start')

    # Define transitions
    sm.add_transition('stop', 'stop', 1.0, 1.0)
    sm.add_transition('start', 'moving', 1.0, 1.0)

    # Define final states
    sm.add_final_state('stop')

    # Run the simulation
    env.process(sm.run())
    env.run(until=100)  # Run for a maximum of 100 time units

if __name__ == '__main__':
    main()