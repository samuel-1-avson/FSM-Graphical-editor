from collections import deque


def visit_connected_states(state):
    visit = deque()
    already_visited = set()
    visit.append(state)
    while visit:
        state = visit.popleft()
        if state in already_visited:
            continue
        already_visited.add(state)
        yield state
        visit.extend(t.target for t in state.transitions)


def iterate_states_and_transitions(states):
    for state in states:
        yield state
        yield from state.transitions