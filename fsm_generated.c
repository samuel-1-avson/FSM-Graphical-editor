#include "fsm_generated.h"
#include <stdio.h> // For basic printf in stubs

static FSM_State_t current_fsm_state;

// --- FSM Global Variables (if any) ---
// Example: static int my_fsm_variable = 0;

void fsm_generated_init(void) {
    current_fsm_state = STATE_RED;
}

FSM_State_t fsm_generated_get_current_state(void) {
    return current_fsm_state;
}

void fsm_generated_run(FSM_Event_t event_id) {
    FSM_State_t next_state = current_fsm_state;
    int transition_taken = 0;

    switch (current_fsm_state) {
        case STATE_GREEN: {
            if ((event_id == EVENT_TIMER) && (1)) {
                action_trans_Green_to_Yellow_timer();
                next_state = STATE_YELLOW;
                transition_taken = 1;
            }
            break;
        }
        case STATE_YELLOW: {
            if ((event_id == EVENT_TIMER) && (1)) {
                action_trans_Yellow_to_Red_timer();
                next_state = STATE_RED;
                transition_taken = 1;
            }
            break;
        }
        case STATE_RED: {
            if ((event_id == EVENT_TIMER) && (1)) {
                action_trans_Red_to_Green_timer();
                next_state = STATE_GREEN;
                transition_taken = 1;
            }
            break;
        }
        default:
            // Should not happen
            break;
    } // end switch (current_fsm_state)

    if (transition_taken && next_state != current_fsm_state) {
    }

    current_fsm_state = next_state;
}


// --- User-Defined Action Function Implementations (STUBS) ---
// --- Please fill these in with your custom logic ---
void action_trans_Green_to_Yellow_timer(void) {
    // TODO: Implement action for action_trans_Green_to_Yellow_timer(void)
    // printf("Action: action_trans_Green_to_Yellow_timer(void) called\n");
}

void action_trans_Red_to_Green_timer(void) {
    // TODO: Implement action for action_trans_Red_to_Green_timer(void)
    // printf("Action: action_trans_Red_to_Green_timer(void) called\n");
}

void action_trans_Yellow_to_Red_timer(void) {
    // TODO: Implement action for action_trans_Yellow_to_Red_timer(void)
    // printf("Action: action_trans_Yellow_to_Red_timer(void) called\n");
}
