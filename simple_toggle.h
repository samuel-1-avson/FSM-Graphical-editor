#ifndef SIMPLE_TOGGLE_H
#define SIMPLE_TOGGLE_H

typedef enum {
    STATE_ON,
    STATE_OFF,
    FSM_NUM_STATES // Helper for array sizing or loop limits
} FSM_State_t;

typedef enum {
    EVENT_TOGGLE,
    FSM_NUM_EVENTS // Helper for array sizing or loop limits
} FSM_Event_t;

#define FSM_NO_EVENT -1 // Special value for triggering 'during' actions or internal steps

// Function Prototypes for FSM
void simple_toggle_init(void);
void simple_toggle_run(int event_id); // Pass FSM_Event_t or FSM_NO_EVENT
FSM_State_t simple_toggle_get_current_state(void);

// User-defined Action Function Prototypes (implement these!)
void action_trans_Off_to_On_toggle(void);
void action_trans_On_to_Off_toggle(void);
void entry_action_Off(void);
void entry_action_On(void);

#endif // SIMPLE_TOGGLE_H