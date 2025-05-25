
# run_test_fsm.py
from fsm_simulator import StateMachinePoweredSimulator, FSMError

def print_sim_status(sim, step_name=""):
    print(f"\n--- {step_name} ---")
    print(f"Current State: {sim.get_current_state_name()}")
    print(f"Variables: {sim.get_variables()}")
    log = sim.get_last_executed_actions_log()
    if log:
        print("Log:")
        for entry in log:
            print(f"  {entry}")
    print("--------------------")

if __name__ == "__main__":
    # Define the FSM structure programmatically
    states_data = [
        {
            "name": "Standby", "is_initial": True, "is_final": False,
            "entry_action": "status_message = 'System ready in Standby'; activation_count = 0; uptime_ticks = 0", # Init vars here
            "exit_action": "last_op = 'Exited Standby'"
        },
        {
            "name": "Active", "is_initial": False, "is_final": False,
            "entry_action": "activation_count = activation_count + 1; current_task = 'monitoring'",
            "during_action": "uptime_ticks = uptime_ticks + 1",
            "exit_action": "current_task = 'none'"
        },
        {
            "name": "Maintenance", "is_initial": False, "is_final": False,
            "entry_action": "status_message = 'Maintenance mode active'",
            "exit_action": "status_message = 'Exiting Maintenance'"
        }
    ]

    transitions_data = [
        {
            "source": "Standby", "target": "Active", "event": "power_on",
            "action": "system_log = 'Power ON sequence initiated'"
        },
        {
            "source": "Active", "target": "Standby", "event": "power_off",
            "action": "system_log = 'Power OFF sequence initiated'"
        },
        {
            "source": "Active", "target": "Maintenance", "event": "enter_maint",
            "condition": "uptime_ticks > 5", # Condition for this transition
            "action": "maint_reason = 'Scheduled check'"
        },
        {
            "source": "Maintenance", "target": "Active", "event": "exit_maint"
        }
    ]

    print("Creating FSM Simulator...")
    try:
        simulator = StateMachinePoweredSimulator(states_data, transitions_data)
        print_sim_status(simulator, "INITIAL STATE")

        # --- Test Scenario ---

        # 1. Power on
        simulator.step(event_name="power_on")
        print_sim_status(simulator, "AFTER 'power_on'")

        # 2. Let some "during" actions in Active state run
        for i in range(7): # This will make uptime_ticks go from 0 to 6
            simulator.step(event_name=None) # Trigger "during" actions
            print_sim_status(simulator, f"AFTER INTERNAL STEP {i+1} in Active")

        # 3. Try to enter maintenance (condition should now be true: uptime_ticks > 5)
        simulator.step(event_name="enter_maint")
        print_sim_status(simulator, "AFTER 'enter_maint' (condition met)")

        # 4. Try to trigger an event not allowed from Maintenance
        simulator.step(event_name="power_on") # Not defined from Maintenance
        print_sim_status(simulator, "AFTER trying invalid 'power_on' from Maintenance")

        # 5. Exit maintenance
        simulator.step(event_name="exit_maint")
        print_sim_status(simulator, "AFTER 'exit_maint'")

        # 6. Power off
        simulator.step(event_name="power_off")
        print_sim_status(simulator, "AFTER 'power_off'")

        # 7. Reset
        print("\n>>> RESETTING FSM <<<")
        simulator.reset()
        print_sim_status(simulator, "AFTER RESET")

    except FSMError as e:
        print(f"FSM Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()