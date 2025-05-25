import os
import time
import copy # For deep copying maze layouts

# --- Maze Configuration ---
WALL = "#"
PATH = " "
START = "S"
END = "E"
PLAYER = "P"
KEY = "K"
DOOR = "D"
FOG = "." # Character for unexplored areas in Fog of War

# --- Game Settings ---
VISIBILITY_RADIUS = 2 # How many cells the player can see around them (diamond shape)

# --- Maze Definitions ---
# Note: Mazes are now a list of dictionaries for easier state management per level
LEVELS_DATA = [
    {
        "name": "The Beginning",
        "layout": [
            ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
            ["#", "S", " ", "#", " ", " ", " ", " ", " ", "#"],
            ["#", " ", " ", "#", " ", "#", "#", "#", " ", "#"],
            ["#", " ", "#", "#", " ", "K", " ", "#", " ", "#"],
            ["#", " ", " ", " ", " ", "#", "D", "#", " ", "#"],
            ["#", "#", "#", "#", " ", "#", " ", "#", "E", "#"],
            ["#", " ", " ", " ", " ", "#", " ", " ", " ", "#"],
            ["#", " ", "#", "#", "#", "#", "#", "#", "#", "#"],
            ["#", " ", " ", " ", " ", " ", " ", " ", " ", "#"],
            ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
        ]
    },
    {
        "name": "Corridor of Choices",
        "layout": [
            ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
            ["#", "S", " ", " ", " ", "#", " ", " ", " ", " ", " ", "E", "#"],
            ["#", " ", "#", "#", " ", "#", " ", "#", "#", "#", " ", "#", "#"],
            ["#", " ", "#", "K", " ", " ", " ", "D", " ", "#", " ", " ", "#"],
            ["#", " ", "#", "#", "#", "#", "#", "#", " ", "#", "#", " ", "#"],
            ["#", " ", " ", " ", " ", " ", " ", " ", " ", " ", " ", " ", "#"],
            ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
        ]
    },
    {
        "name": "The Long Walk",
        "layout": [
            ["#", "#", "#", "#", "#", "#", "#"],
            ["#", "S", " ", " ", "K", " ", "#"],
            ["#", "#", "#", " ", "#", "#", "#"],
            ["#", " ", "D", " ", "#", "E", "#"],
            ["#", "#", "#", "#", "#", "#", "#"],
        ]
    }
]

# --- Helper Functions ---

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def find_char_position(maze_layout, char_to_find):
    """Finds the first occurrence of a character in the maze."""
    for r_idx, row in enumerate(maze_layout):
        for c_idx, char_in_cell in enumerate(row):
            if char_in_cell == char_to_find:
                return [r_idx, c_idx]
    return None

def update_visibility(player_pos, maze_layout, visited_cells):
    """Updates the set of visited cells based on player's current visibility."""
    pr, pc = player_pos
    max_r, max_c = len(maze_layout), len(maze_layout[0])

    for r_offset in range(-VISIBILITY_RADIUS, VISIBILITY_RADIUS + 1):
        for c_offset in range(-VISIBILITY_RADIUS, VISIBILITY_RADIUS + 1):
            # Manhattan distance for diamond shape visibility
            if abs(r_offset) + abs(c_offset) <= VISIBILITY_RADIUS:
                vr, vc = pr + r_offset, pc + c_offset
                if 0 <= vr < max_r and 0 <= vc < max_c:
                    visited_cells.add((vr, vc))

def display_maze(maze_layout, player_pos, visited_cells, level_name, moves, elapsed_time, has_key):
    clear_screen()
    print(f"--- MAZE RUNNER: {level_name} ---")
    print(f"Moves: {moves} | Time: {int(elapsed_time)}s | Key: {'Yes' if has_key else 'No'}")
    print("Controls: W (Up), A (Left), S (Down), D (Right), Q (Quit)")
    print("-" * (len(maze_layout[0]) * 2 + 3)) # Dynamic border based on maze width

    for r_idx, row in enumerate(maze_layout):
        display_row = "| " # Start of row border
        for c_idx, char_in_cell in enumerate(row):
            if [r_idx, c_idx] == player_pos:
                display_row += PLAYER + " "
            elif (r_idx, c_idx) in visited_cells:
                display_row += char_in_cell + " "
            else:
                display_row += FOG + " "
        display_row += "|" # End of row border
        print(display_row)
    print("-" * (len(maze_layout[0]) * 2 + 3)) # Dynamic border

def get_player_move():
    while True:
        move = input("Enter your move (W/A/S/D) or Q to quit: ").upper()
        if move in ["W", "A", "S", "D", "Q"]:
            return move
        else:
            print("Invalid move. Please use W, A, S, D, or Q.")

# --- Game Logic ---

def play_level(level_data, level_num):
    """Plays a single level of the maze game."""
    # Use a deep copy so modifications (like opening doors) don't affect original
    current_maze = copy.deepcopy(level_data["layout"])
    level_name = level_data["name"]

    player_pos = find_char_position(current_maze, START)
    if player_pos is None:
        print(f"Error: Start position 'S' not found in level {level_name}!")
        return "error" # Signal an error

    max_rows = len(current_maze)
    max_cols = len(current_maze[0])

    moves_count = 0
    has_key = False
    visited_cells = set() # For Fog of War - stores (row, col) tuples
    start_time = time.time()

    # Initial visibility update
    update_visibility(player_pos, current_maze, visited_cells)

    while True:
        elapsed_time = time.time() - start_time
        display_maze(current_maze, player_pos, visited_cells, level_name, moves_count, elapsed_time, has_key)

        # Check what's at the player's current position (after a move)
        current_tile_char = current_maze[player_pos[0]][player_pos[1]]

        if current_tile_char == END:
            print(f"\nCongratulations! You completed '{level_name}' in {moves_count} moves and {int(elapsed_time)}s!")
            input("Press Enter to proceed to the next level (if any)...")
            return "completed"

        if current_tile_char == KEY:
            has_key = True
            current_maze[player_pos[0]][player_pos[1]] = PATH # Key disappears
            print("You found a key!")
            # No need for input pause, display will refresh

        move = get_player_move()

        if move == "Q":
            print("\nThanks for playing! You quit the game.")
            return "quit"

        new_pos = list(player_pos) # Create a copy

        if move == "W": new_pos[0] -= 1
        elif move == "S": new_pos[0] += 1
        elif move == "A": new_pos[1] -= 1
        elif move == "D": new_pos[1] += 1

        # Check boundaries
        if not (0 <= new_pos[0] < max_rows and 0 <= new_pos[1] < max_cols):
            print("Ouch! You can't go outside the maze. Try again.")
            input("Press Enter to continue...")
            continue # Skip to next iteration of the loop

        # Check target tile
        target_tile_char = current_maze[new_pos[0]][new_pos[1]]

        can_move = False
        if target_tile_char == WALL:
            print("Ouch! You hit a wall. Try again.")
            input("Press Enter to continue...")
        elif target_tile_char == DOOR:
            if has_key:
                print("You used the key to open the door!")
                current_maze[new_pos[0]][new_pos[1]] = PATH # Door opens and becomes a path
                can_move = True
            else:
                print("This door is locked. You need a key (K)!")
                input("Press Enter to continue...")
        else: # Path, Start, End, Key (before picking up)
            can_move = True

        if can_move:
            player_pos = new_pos
            moves_count += 1
            update_visibility(player_pos, current_maze, visited_cells) # Update FoW after moving

    return "error" # Should not be reached


def game_intro():
    clear_screen()
    print("***************************")
    print("*     MAZE RUNNER EXTREME *")
    print("***************************")
    print("\nNavigate 'P' from 'S' (Start) to 'E' (End).")
    print("Collect 'K' (Keys) to open 'D' (Doors).")
    print(f"'{FOG}' marks unexplored areas. You can see {VISIBILITY_RADIUS} tiles around you.")
    print("\nGood luck!")
    input("\nPress Enter to start...")

# --- Main Execution ---
if __name__ == "__main__":
    game_intro()
    total_levels = len(LEVELS_DATA)

    for i, level_data_original in enumerate(LEVELS_DATA):
        level_status = play_level(level_data_original, i + 1)

        if level_status == "quit":
            break
        elif level_status == "error":
            print("A critical error occurred in the level. Exiting.")
            break
        elif level_status == "completed":
            if i < total_levels - 1:
                print(f"Level {i+1} complete!")
                # Optional: add a brief pause or message before next level
            else:
                print("\n\nWOOHOO! You've completed all the mazes!")
                print("You are a true Maze Runner!")
                break
    
    print("\nGame Over. Thanks for playing Maze Runner Extreme!")