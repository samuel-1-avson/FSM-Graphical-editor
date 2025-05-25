import pygame
import asyncio
import platform
import random
from collections import deque

# Initialize Pygame
pygame.init()

# Constants
CELL_SIZE = 40
FPS = 60
MIN_GRID_SIZE = 10
MAX_GRID_SIZE = 20

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
GRAY = (200, 200, 200)
YELLOW = (255, 255, 0)

# Game state
class GameState:
    def __init__(self):
        self.grid_size = MIN_GRID_SIZE
        self.window_size = (self.grid_size * CELL_SIZE, self.grid_size * CELL_SIZE + 50)
        self.screen = pygame.display.set_mode(self.window_size)
        pygame.display.set_caption("Maze Game")
        self.player_pos = [1, 1]
        self.goal_pos = [0, 0]
        self.maze = []
        self.score = 0
        self.moves = 0
        self.level = 1
        self.start_time = 0
        self.trail = deque(maxlen=10)
        self.game_won = False
        self.win_animation_time = 0
        self.generate_maze()

    def generate_maze(self):
        # Initialize maze with walls
        self.maze = [[1 for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        stack = [(1, 1)]
        self.maze[1][1] = 0
        directions = [(0, 2), (2, 0), (0, -2), (-2, 0)]
        
        while stack:
            x, y = stack[-1]
            random.shuffle(directions)
            neighbors = []
            for dx, dy in directions:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size and self.maze[nx][ny] == 1:
                    neighbors.append((nx, ny))
            if neighbors:
                nx, ny = random.choice(neighbors)
                self.maze[nx][ny] = 0
                self.maze[x + (nx - x) // 2][y + (ny - y) // 2] = 0
                stack.append((nx, ny))
            else:
                stack.pop()
        
        self.player_pos = [1, 1]
        self.goal_pos = [self.grid_size - 2, self.grid_size - 2]
        self.maze[self.goal_pos[0]][self.goal_pos[1]] = 0
        self.start_time = pygame.time.get_ticks()
        self.moves = 0
        self.trail.clear()
        self.game_won = False
        self.win_animation_time = 0

game = GameState()

def draw_maze():
    for row in range(game.grid_size):
        for col in range(game.grid_size):
            color = BLACK if game.maze[row][col] == 1 else WHITE
            pygame.draw.rect(game.screen, color, (col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE))
            pygame.draw.rect(game.screen, GRAY, (col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE), 1)

def draw_trail():
    for pos in game.trail:
        pygame.draw.rect(game.screen, (100, 100, 255), (pos[1] * CELL_SIZE + 5, pos[0] * CELL_SIZE + 5, CELL_SIZE - 10, CELL_SIZE - 10))

def draw_player():
    pygame.draw.rect(game.screen, BLUE, (game.player_pos[1] * CELL_SIZE, game.player_pos[0] * CELL_SIZE, CELL_SIZE, CELL_SIZE))

def draw_goal():
    if game.game_won:
        t = (pygame.time.get_ticks() - game.win_animation_time) % 1000 / 1000
        size = int(CELL_SIZE * (1 + 0.2 * (1 - t)))
        offset = (CELL_SIZE - size) // 2
        pygame.draw.rect(game.screen, GREEN, (game.goal_pos[1] * CELL_SIZE + offset, game.goal_pos[0] * CELL_SIZE + offset, size, size))
    else:
        pygame.draw.rect(game.screen, GREEN, (game.goal_pos[1] * CELL_SIZE, game.goal_pos[0] * CELL_SIZE, CELL_SIZE, CELL_SIZE))

def draw_hud():
    font = pygame.font.Font(None, 36)
    time_elapsed = (pygame.time.get_ticks() - game.start_time) // 1000
    text = font.render(f"Score: {game.score}  Level: {game.level}  Time: {time_elapsed}s", True, RED)
    game.screen.blit(text, (10, game.grid_size * CELL_SIZE + 10))
    if game.game_won:
        win_text = font.render("You Win! Press R to Restart", True, YELLOW)
        game.screen.blit(win_text, (game.window_size[0] // 2 - win_text.get_width() // 2, game.window_size[1] // 2))

def move_player(dx, dy):
    if game.game_won:
        return False
    new_x = game.player_pos[0] + dx
    new_y = game.player_pos[1] + dy
    if 0 <= new_x < game.grid_size and 0 <= new_y < game.grid_size and game.maze[new_x][new_y] == 0:
        game.player_pos[0] = new_x
        game.player_pos[1] = new_y
        game.moves += 1
        game.trail.append(game.player_pos.copy())
        game.score += 10
    won = game.player_pos[0] == game.goal_pos[0] and game.player_pos[1] == game.goal_pos[1]
    if won:
        game.game_won = True
        game.win_animation_time = pygame.time.get_ticks()
        time_bonus = max(0, 1000 - (pygame.time.get_ticks() - game.start_time) // 100)
        game.score += time_bonus + 500
    return won

def setup():
    game.screen.fill(WHITE)
    draw_maze()
    draw_trail()
    draw_goal()
    draw_player()
    draw_hud()
    pygame.display.flip()

def update_loop():
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            if game.game_won and event.key == pygame.K_r:
                game.level += 1
                game.grid_size = min(game.grid_size + 2, MAX_GRID_SIZE)
                game.window_size = (game.grid_size * CELL_SIZE, game.grid_size * CELL_SIZE + 50)
                game.screen = pygame.display.set_mode(game.window_size)
                game.generate_maze()
            elif not game.game_won:
                if event.key == pygame.K_UP:
                    move_player(-1, 0)
                elif event.key == pygame.K_DOWN:
                    move_player(1, 0)
                elif event.key == pygame.K_LEFT:
                    move_player(0, -1)
                elif event.key == pygame.K_RIGHT:
                    move_player(0, 1)
    
    game.screen.fill(WHITE)
    draw_maze()
    draw_trail()
    draw_goal()
    draw_player()
    draw_hud()
    pygame.display.flip()

async def main():
    setup()
    while True:
        update_loop()
        await asyncio.sleep(1.0 / FPS)

if platform.system() == "Emscripten":
    asyncio.ensure_future(main())
else:
    if __name__ == "__main__":
        asyncio.run(main())