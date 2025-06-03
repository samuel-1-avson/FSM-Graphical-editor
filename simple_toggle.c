#include "simple_toggle.h"
#include <stdio.h> // For basic printf in stubs

static FSM_State_t current_fsm_state;

// --- FSM Global Variables (if any, declare them here) ---
// Example: static int my_fsm_counter = 0;

void simple_toggle_init(void) {
    current_fsm_state = STATE_OFF;
    entry_action_Off(); // Call entry action for initial state
}

FSM_State_t simple_toggle_get_current_state(void) {
    return current_fsm_state;
}

void simple_toggle_run(int event_id) {
    FSM_State_t previous_state = current_fsm_state;
    FSM_State_t next_state = current_fsm_state; // Assume no transition initially
    int transition_taken = 0;

    // Note: FSM_NO_EVENT is defined as -1 in the header

    switch (current_fsm_state) {
        case STATE_ON: {
            if (event_id != FSM_NO_EVENT && (event_id == EVENT_TOGGLE) && (1)) {
                action_trans_On_to_Off_toggle();
                next_state = STATE_OFF;
                transition_taken = 1;
            }
            break;
        }
        default:
            // Should not happen: Unhandled current_fsm_state
            break;
    } // end switch (current_fsm_state)

    if (transition_taken && next_state != previous_state) {
        // Call entry action for the new state (if it changed)
        switch (next_state) {
            case STATE_ON: entry_action_On(); break;
            case STATE_OFF: entry_action_Off(); break;
            default: /* No entry action for this state or unknown */ break;
        }
    }

    current_fsm_state = next_state;
}


// --- User-Defined Action Function Implementations (STUBS) ---
// --- Please fill these in with your custom logic ---
void action_trans_Off_to_On_toggle(void) { // Original action source: action for Off to On on toggle. Python: print('Toggling ON')
    printf("%s\n", 'Toggling ON');
    // Example: printf("Action stub: action_trans_Off_to_On_toggle called\n");
}

void action_trans_On_to_Off_toggle(void) { // Original action source: action for On to Off on toggle. Python: print('Toggling OFF')
    printf("%s\n", 'Toggling OFF');
    // Example: printf("Action stub: action_trans_On_to_Off_toggle called\n");
}

void entry_action_Off(void) { // Original action source: entry_action for Off. Python: is_on = False print('Device is OFF')
    digitalWrite(PIN_FOR_IS_ON, LOW);  // TODO: Define PIN_FOR_IS_ON and ensure is_on is conceptual.
    printf("%s\n", 'Device is OFF');
    // Example: printf("Action stub: entry_action_Off called\n");
}

void entry_action_On(void) { // Original action source: entry_action for On. Python: is_on = True print('Device is ON')
    digitalWrite(PIN_FOR_IS_ON, HIGH); // TODO: Define PIN_FOR_IS_ON (e.g., #define PIN_FOR_IS_ON 13) and ensure is_on is conceptual.
    printf("%s\n", 'Device is ON');
    // Example: printf("Action stub: entry_action_On called\n");
}
