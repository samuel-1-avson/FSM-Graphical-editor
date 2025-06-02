// fsm_toggle.h
#ifndef FSM_TOGGLE_H
#define FSM_TOGGLE_H

typedef enum
{
    STATE_OFF,
    STATE_ON,
    FSM_NUM_STATES
} FSM_State_t;

typedef enum
{
    EVENT_FLIP,
    FSM_NUM_EVENTS
} FSM_Event_t;

// Function Prototypes for FSM
void fsm_toggle_init(void);
void fsm_toggle_run(FSM_Event_t event_id);
FSM_State_t fsm_toggle_get_current_state(void);

// User-defined Action Function Prototypes (implement these!)
void entry_action_Off(void);
void entry_action_On(void);
void action_trans_Off_to_On_flip(void);
void action_trans_On_to_Off_flip(void);

#endif // FSM_TOGGLE_H