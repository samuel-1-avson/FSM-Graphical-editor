import json
import argparse

class FSM:
    def __init__(self, states, initial_state, transitions):
        self.states = states
        self.current_state = initial_state
        self.transitions = transitions

    def trigger(self, event):
        # Search for a valid transition given the current state and event
        for trans in self.transitions:
            if trans['source'] == self.current_state and trans['event'] == event:
                print(f"\nTransition: {self.current_state} --({event})--> {trans['target']}")
                self.current_state = trans['target']
                if 'action' in trans and trans['action']:
                    print(f"Action: {trans['action']}")
                return
        print(f"\nNo valid transition from '{self.current_state}' on event '{event}'.")

def load_fsm_from_json(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    return FSM(data['states'], data['initial_state'], data['transitions'])

def main():
    parser = argparse.ArgumentParser(description="FSM Generator and Simulator for Mechatronics")
    parser.add_argument("json_file", help="Path to the FSM configuration JSON file")
    args = parser.parse_args()

    fsm = load_fsm_from_json(args.json_file)
    print(f"FSM loaded. Initial state: {fsm.current_state}")
    print("Enter events to trigger transitions. Type 'exit' to quit.")

    while True:
        event = input("\nEvent: ").strip()
        if event.lower() == "exit":
            break
        fsm.trigger(event)
        print(f"Current state: {fsm.current_state}")

if __name__ == "__main__":
    main()
