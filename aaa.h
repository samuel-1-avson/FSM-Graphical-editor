#ifndef AAA_H
#define AAA_H

typedef enum {
    STATE_UNSTABLE,
    STATE_WAITING,
    STATE_STABLE,
    FSM_NUM_STATES
} FSM_State_t;

typedef enum {
    EVENT_DEBOUNCE_TIMER_EXPIRED,
    EVENT_INPUT_CHANGE,
    EVENT_INPUT_CHANGE_WHILE_WAITING,
    EVENT_INPUT_GOES_UNSTABLE_AGAIN,
    FSM_NUM_EVENTS
} FSM_Event_t;

// Function Prototypes for FSM
void aaa_init(void);
void aaa_run(FSM_Event_t event_id); // Pass event_id or -1 for during_action
FSM_State_t aaa_get_current_state(void);

// User-defined Action Function Prototypes (implement these!)
void entry_action_Waiting(void);

#endif // AAA_H