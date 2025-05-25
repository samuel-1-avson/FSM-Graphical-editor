import pygame
import os
import time
import copy

# --- Pygame Initialization ---
pygame.init()
pygame.font.init() # Initialize font module

# --- Game Constants & Settings ---
TILE_SIZE = 30  # Size of each maze tile in pixels
FPS = 30        # Frames per second

# Colors (R, G, B)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 0, 0)
GREEN = (0, 200, 0)
BLUE = (0, 0, 200)
LIGHT_BLUE = (100, 100, 255)
YELLOW = (220, 220, 0)
ORANGE = (255, 165, 0)
GREY = (128, 128, 128)
DARK_GREY = (50, 50, 50) # For fog

# Maze Characters (same as before, but now map to colors)
WALL_CHAR = "#"
PATH_CHAR = " "
START_CHAR = "S"
END_CHAR = "E"
PLAYER_CHAR = "P" # Player isn't usually in the maze data, but drawn at player_pos
KEY_CHAR = "K"
DOOR_CHAR = "D"
FOG_CHAR = "." # Not drawn, but used for logic

# Tile Colors
TILE_COLORS = {
    WALL_CHAR: GREY,
    PATH_CHAR: WHITE,
    START_CHAR: LIGHT_BLUE,
    END_CHAR: GREEN,
    KEY_CHAR: YELLOW,
    DOOR_CHAR: ORANGE,
    PLAYER_CHAR: BLUE, # Player color
    "FOG": DARK_GREY
}

VISIBILITY_RADIUS = 3 # How many cells the player can see (diamond shape)
INFO_PANEL_HEIGHT = 60 # Height for displaying game info

# --- Maze Definitions (same as before) ---
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

def find_char_position(maze_layout, char_to_find):
    for r_idx, row in enumerate(maze_layout):
        for c_idx, char_in_cell in enumerate(row):
            if char_in_cell == char_to_find:
                return [r_idx, c_idx] # Returns [row, col]
    return None

def update_visibility(player_pos_grid, maze_layout, visited_cells):
    pr, pc = player_pos_grid # Player row, col in grid
    max_r, max_c = len(maze_layout), len(maze_layout[0])

    for r_offset in range(-VISIBILITY_RADIUS, VISIBILITY_RADIUS + 1):
        for c_offset in range(-VISIBILITY_RADIUS, VISIBILITY_RADIUS + 1):
            if abs(r_offset) + abs(c_offset) <= VISIBILITY_RADIUS: # Manhattan distance
                vr, vc = pr + r_offset, pc + c_offset
                if 0 <= vr < max_r and 0 <= vc < max_c:
                    visited_cells.add((vr, vc)) # Add (row, col) tuple

def draw_text(surface, text, pos, font, color=BLACK):
    text_surface = font.render(text, True, color)
    surface.blit(text_surface, pos)

def display_message(screen, message, font, duration=2):
    screen_width, screen_height = screen.get_size()
    text_surface = font.render(message, True, WHITE, BLACK) # White text, black background
    text_rect = text_surface.get_rect(center=(screen_width // 2, screen_height // 2))
    screen.blit(text_surface, text_rect)
    pygame.display.flip()
    pygame.time.wait(duration * 1000)


# --- Main Game Function ---
def run_game():
    global SCREEN, CLOCK, FONT_SMALL, FONT_MEDIUM, FONT_LARGE # Make them accessible

    current_level_index = 0
    game_state = "INTRO" # INTRO, PLAYING, LEVEL_COMPLETE, GAME_OVER, QUIT

    # --- Game State Variables (reset per level) ---
    player_pos_grid = [0, 0] # Current [row, col] of player
    current_maze_instance = []
    level_name = ""
    moves_count = 0
    has_key = False
    visited_cells = set()
    level_start_time = 0
    message_queue = [] # For temporary on-screen messages

    def load_level(level_idx):
        nonlocal player_pos_grid, current_maze_instance, level_name, moves_count
        nonlocal has_key, visited_cells, level_start_time, message_queue

        level_data = LEVELS_DATA[level_idx]
        current_maze_instance = copy.deepcopy(level_data["layout"])
        level_name = level_data["name"]
        
        start_pos = find_char_position(current_maze_instance, START_CHAR)
        if start_pos:
            player_pos_grid = list(start_pos) # Ensure it's a list for modification
        else:
            print(f"Error: Start position 'S' not found in level {level_name}!")
            return False # Indicate error

        # Reset level-specific state
        moves_count = 0
        has_key = False
        visited_cells = set()
        level_start_time = time.time()
        message_queue = []
        update_visibility(player_pos_grid, current_maze_instance, visited_cells)
        return True

    # Screen setup (done once, but dimensions depend on first maze or a max)
    # For simplicity, let's use the first maze's dimensions to init screen
    # A more robust solution would find max dimensions or allow scrolling
    temp_maze_for_dims = LEVELS_DATA[0]["layout"]
    maze_width_tiles = len(temp_maze_for_dims[0])
    maze_height_tiles = len(temp_maze_for_dims)
    SCREEN_WIDTH = maze_width_tiles * TILE_SIZE
    SCREEN_HEIGHT = maze_height_tiles * TILE_SIZE + INFO_PANEL_HEIGHT

    SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pygame Maze Runner")
    CLOCK = pygame.time.Clock()

    # Fonts
    try:
        FONT_SMALL = pygame.font.SysFont("Arial", 18)
        FONT_MEDIUM = pygame.font.SysFont("Arial", 24)
        FONT_LARGE = pygame.font.SysFont("Arial", 48)
    except pygame.error: # Fallback if system font not found
        FONT_SMALL = pygame.font.Font(None, 24)
        FONT_MEDIUM = pygame.font.Font(None, 30)
        FONT_LARGE = pygame.font.Font(None, 60)


    running = True
    while running:
        dt = CLOCK.tick(FPS) / 1000.0 # Delta time in seconds

        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                game_state = "QUIT"

            if game_state == "PLAYING":
                if event.type == pygame.KEYDOWN:
                    new_player_pos_grid = list(player_pos_grid) # Important: copy
                    moved = False
                    if event.key == pygame.K_w or event.key == pygame.K_UP:
                        new_player_pos_grid[0] -= 1
                        moved = True
                    elif event.key == pygame.K_s or event.key == pygame.K_DOWN:
                        new_player_pos_grid[0] += 1
                        moved = True
                    elif event.key == pygame.K_a or event.key == pygame.K_LEFT:
                        new_player_pos_grid[1] -= 1
                        moved = True
                    elif event.key == pygame.K_d or event.key == pygame.K_RIGHT:
                        new_player_pos_grid[1] += 1
                        moved = True
                    elif event.key == pygame.K_q:
                        running = False
                        game_state = "QUIT"

                    if moved:
                        # Boundary check (grid coordinates)
                        pr, pc = new_player_pos_grid
                        if 0 <= pr < len(current_maze_instance) and \
                           0 <= pc < len(current_maze_instance[0]):
                            
                            target_tile_char = current_maze_instance[pr][pc]
                            can_move = False

                            if target_tile_char == WALL_CHAR:
                                message_queue.append(("Ouch! A wall!", time.time()))
                            elif target_tile_char == DOOR_CHAR:
                                if has_key:
                                    message_queue.append(("Door unlocked!", time.time()))
                                    current_maze_instance[pr][pc] = PATH_CHAR # Open door
                                    has_key = False # Key is used up
                                    can_move = True
                                else:
                                    message_queue.append(("Door is locked. Find a key (K)!", time.time()))
                            else: # Path, Start, End, Key
                                can_move = True
                            
                            if can_move:
                                player_pos_grid = new_player_pos_grid
                                moves_count += 1
                                update_visibility(player_pos_grid, current_maze_instance, visited_cells)

                                # Check for special tiles at new position
                                if current_maze_instance[player_pos_grid[0]][player_pos_grid[1]] == KEY_CHAR:
                                    has_key = True
                                    current_maze_instance[player_pos_grid[0]][player_pos_grid[1]] = PATH_CHAR # Pick up key
                                    message_queue.append(("Key collected!", time.time()))
                                
                                elif current_maze_instance[player_pos_grid[0]][player_pos_grid[1]] == END_CHAR:
                                    game_state = "LEVEL_COMPLETE"

                        else: # Out of bounds
                            message_queue.append(("Can't go outside the maze!", time.time()))
            
            elif game_state == "INTRO":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    if load_level(current_level_index):
                        # Dynamically adjust screen size for the current level
                        maze_width_tiles = len(current_maze_instance[0])
                        maze_height_tiles = len(current_maze_instance)
                        SCREEN_WIDTH = maze_width_tiles * TILE_SIZE
                        SCREEN_HEIGHT = maze_height_tiles * TILE_SIZE + INFO_PANEL_HEIGHT
                        SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
                        pygame.display.set_caption(f"Pygame Maze Runner - {level_name}")
                        game_state = "PLAYING"
                    else:
                        running = False # Error loading level
            elif game_state == "LEVEL_COMPLETE":
                 if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    current_level_index += 1
                    if current_level_index < len(LEVELS_DATA):
                        if load_level(current_level_index):
                            # Adjust screen size for new level
                            maze_width_tiles = len(current_maze_instance[0])
                            maze_height_tiles = len(current_maze_instance)
                            SCREEN_WIDTH = maze_width_tiles * TILE_SIZE
                            SCREEN_HEIGHT = maze_height_tiles * TILE_SIZE + INFO_PANEL_HEIGHT
                            SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
                            pygame.display.set_caption(f"Pygame Maze Runner - {level_name}")
                            game_state = "PLAYING"
                        else:
                             running = False # Error loading next level
                    else:
                        game_state = "GAME_OVER"
            elif game_state == "GAME_OVER":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    running = False # Or restart: current_level_index = 0; game_state = "INTRO"; load_level(0)
                    game_state = "QUIT"


        # --- Drawing ---
        SCREEN.fill(BLACK) # Background for the whole window

        if game_state == "INTRO":
            draw_text(SCREEN, "MAZE RUNNER EXTREME", (SCREEN_WIDTH//2 - FONT_LARGE.size("MAZE RUNNER EXTREME")[0]//2, SCREEN_HEIGHT//3), FONT_LARGE, WHITE)
            draw_text(SCREEN, "Press ENTER to Start", (SCREEN_WIDTH//2 - FONT_MEDIUM.size("Press ENTER to Start")[0]//2, SCREEN_HEIGHT//2), FONT_MEDIUM, WHITE)
            draw_text(SCREEN, "W/A/S/D or Arrows to move. Q to Quit.", (10, SCREEN_HEIGHT - 30), FONT_SMALL, WHITE)
        
        elif game_state == "PLAYING":
            # Draw Maze (respecting fog of war)
            for r, row in enumerate(current_maze_instance):
                for c, tile_char in enumerate(row):
                    tile_rect = pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                    if (r, c) in visited_cells:
                        char_to_draw = current_maze_instance[r][c]
                        # If it's the start tile but player moved, draw it as path
                        if char_to_draw == START_CHAR and (r,c) != tuple(find_char_position(current_maze_instance, START_CHAR)): # Check original start
                             pygame.draw.rect(SCREEN, TILE_COLORS[PATH_CHAR], tile_rect)
                        else:
                             pygame.draw.rect(SCREEN, TILE_COLORS.get(char_to_draw, WHITE), tile_rect)

                        # Optionally, draw grid lines
                        # pygame.draw.rect(SCREEN, BLACK, tile_rect, 1)
                    else:
                        pygame.draw.rect(SCREEN, TILE_COLORS["FOG"], tile_rect)
            
            # Draw Player
            player_pixel_x = player_pos_grid[1] * TILE_SIZE
            player_pixel_y = player_pos_grid[0] * TILE_SIZE
            player_rect = pygame.Rect(player_pixel_x, player_pixel_y, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(SCREEN, TILE_COLORS[PLAYER_CHAR], player_rect)

            # Draw Info Panel
            info_panel_rect = pygame.Rect(0, SCREEN_HEIGHT - INFO_PANEL_HEIGHT, SCREEN_WIDTH, INFO_PANEL_HEIGHT)
            pygame.draw.rect(SCREEN, BLACK, info_panel_rect)
            
            elapsed_time = int(time.time() - level_start_time)
            info_text = f"Level: {level_name} | Moves: {moves_count} | Time: {elapsed_time}s | Key: {'Yes' if has_key else 'No'}"
            draw_text(SCREEN, info_text, (10, SCREEN_HEIGHT - INFO_PANEL_HEIGHT + 10), FONT_SMALL, WHITE)

            # Display temporary messages
            current_time = time.time()
            new_message_queue = []
            msg_y_offset = SCREEN_HEIGHT - INFO_PANEL_HEIGHT - 25 # Above info panel
            for msg_text, msg_time in message_queue:
                if current_time - msg_time < 2: # Display for 2 seconds
                    draw_text(SCREEN, msg_text, (10, msg_y_offset), FONT_SMALL, YELLOW)
                    msg_y_offset -= 20 # Stack messages if multiple
                    new_message_queue.append((msg_text, msg_time))
            message_queue = new_message_queue


        elif game_state == "LEVEL_COMPLETE":
            draw_text(SCREEN, f"Level '{level_name}' Complete!", (SCREEN_WIDTH//2 - FONT_MEDIUM.size(f"Level '{level_name}' Complete!")[0]//2, SCREEN_HEIGHT//3), FONT_MEDIUM, GREEN)
            draw_text(SCREEN, f"Moves: {moves_count}, Time: {int(time.time() - level_start_time)}s", (SCREEN_WIDTH//2 - FONT_SMALL.size(f"Moves: {moves_count}, Time: {int(time.time() - level_start_time)}s")[0]//2, SCREEN_HEIGHT//2), FONT_SMALL, WHITE)
            draw_text(SCREEN, "Press ENTER for Next Level", (SCREEN_WIDTH//2 - FONT_SMALL.size("Press ENTER for Next Level")[0]//2, SCREEN_HEIGHT//2 + 40), FONT_SMALL, WHITE)

        elif game_state == "GAME_OVER":
            draw_text(SCREEN, "YOU WIN! All Levels Cleared!", (SCREEN_WIDTH//2 - FONT_LARGE.size("YOU WIN! All Levels Cleared!")[0]//2, SCREEN_HEIGHT//3), FONT_LARGE, GREEN)
            draw_text(SCREEN, "Press ENTER to Exit", (SCREEN_WIDTH//2 - FONT_MEDIUM.size("Press ENTER to Exit")[0]//2, SCREEN_HEIGHT//2), FONT_MEDIUM, WHITE)


        pygame.display.flip() # Update the full screen

    pygame.quit()

# --- Start the Game ---
if __name__ == "__main__":
    run_game()