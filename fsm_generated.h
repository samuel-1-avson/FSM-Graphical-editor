#ifndef FSM_GENERATED_H
#define FSM_GENERATED_H

typedef enum {
    STATE_GREEN,
    STATE_YELLOW,
    STATE_RED,
    FSM_NUM_STATES
} FSM_State_t;

typedef enum {
    EVENT_TIMER,
    FSM_NUM_EVENTS
} FSM_Event_t;

// Function Prototypes for FSM
void fsm_generated_init(void);
void fsm_generated_run(FSM_Event_t event_id); // Pass event_id or -1 for during_action
FSM_State_t fsm_generated_get_current_state(void);

// User-defined Action Function Prototypes (implement these!)
void action_trans_Green_to_Yellow_timer(void);
void action_trans_Red_to_Green_timer(void);
void action_trans_Yellow_to_Red_timer(void);

#endif // FSM_GENERATED_H