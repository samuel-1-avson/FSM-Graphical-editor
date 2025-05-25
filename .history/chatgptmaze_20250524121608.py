import pygame
import sys
import random
import time

pygame.init()

WIDTH, HEIGHT = 600, 600
ROWS, COLS = 20, 20
CELL_SIZE = WIDTH // COLS

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Maze Adventure")

# Colors
WHITE, BLACK, BLUE, GREEN, RED, GOLD, GRAY = (255, 255, 255), (0, 0, 0), (50, 100, 255), (0, 255, 0), (200, 50, 50), (255, 215, 0), (100, 100, 100)

font = pygame.font.SysFont(None, 28)
big_font = pygame.font.SysFont(None, 48)

# Levels
levels = []

# Sample maze template
base_maze = [
    "11111111111111111111",
    "10001000000100000001",
    "10101011110101111101",
    "10100000000100000101",
    "10111111010111110101",
    "10000001000000000101",
    "11111101111111110101",
    "10000000000000010101",
    "10111111111110110101",
    "10100000000100100101",
    "10101111110101110101",
    "10000000000100000101",
    "11111111010111110101",
    "10000001000100000101",
    "10111011110111110101",
    "10001000000100000001",
    "10101111111111111101",
    "10000000100000000001",
    "10111110101111111101",
    "11111111111111111111"
]

# Convert maze string to grid
def parse_maze(maze_string):
    return [[int(c) for c in row] for row in maze_string]

# Generate coins
def generate_coins(maze, count=10):
    coins = []
    while len(coins) < count:
        r, c = random.randint(1, ROWS-2), random.randint(1, COLS-2)
        if maze[r][c] == 0 and (r, c) not in coins:
            coins.append((r, c))
    return coins

# Generate traps
def generate_traps(maze, count=5):
    traps = []
    while len(traps) < count:
        r, c = random.randint(1, ROWS-2), random.randint(1, COLS-2)
        if maze[r][c] == 0 and (r, c) not in traps:
            traps.append((r, c))
    return traps

# Game state
class Game:
    def __init__(self):
        self.level = 0
        self.load_level()
        self.lives = 3
        self.score = 0
        self.start_time = time.time()
        self.time_limit = 60
        self.game_over = False
        self.win = False

    def load_level(self):
        self.maze = parse_maze(base_maze)
        self.player_pos = [1, 1]
        self.goal_pos = [18, 18]
        self.coins = generate_coins(self.maze)
        self.traps = generate_traps(self.maze)

    def reset(self):
        self.__init__()

    def advance_level(self):
        self.level += 1
        self.load_level()
        self.start_time = time.time()

game = Game()

# Draw functions
def draw_maze():
    for row in range(ROWS):
        for col in range(COLS):
            rect = pygame.Rect(col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            color = WHITE if game.maze[row][col] == 0 else BLACK
            pygame.draw.rect(screen, color, rect)

def draw_entities():
    # Coins
    for r, c in game.coins:
        pygame.draw.circle(screen, GOLD, (c * CELL_SIZE + CELL_SIZE//2, r * CELL_SIZE + CELL_SIZE//2), CELL_SIZE//4)

    # Traps
    for r, c in game.traps:
        pygame.draw.rect(screen, RED, (c * CELL_SIZE, r * CELL_SIZE, CELL_SIZE, CELL_SIZE))

    # Goal
    gr, gc = game.goal_pos
    pygame.draw.rect(screen, GREEN, (gc * CELL_SIZE, gr * CELL_SIZE, CELL_SIZE, CELL_SIZE))

    # Player
    pr, pc = game.player_pos
    pygame.draw.rect(screen, BLUE, (pc * CELL_SIZE, pr * CELL_SIZE, CELL_SIZE, CELL_SIZE))

def draw_hud():
    elapsed = int(time.time() - game.start_time)
    remaining = max(0, game.time_limit - elapsed)
    texts = [
        f"Level: {game.level + 1}",
        f"Score: {game.score}",
        f"Lives: {game.lives}",
        f"Time: {remaining}s"
    ]
    for i, txt in enumerate(texts):
        img = font.render(txt, True, BLACK)
        screen.blit(img, (10, 10 + i * 25))

    if game.game_over:
        text = big_font.render("Game Over! Press R to Restart", True, RED)
        screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2))

    elif game.win:
        text = big_font.render("Level Complete! Press R", True, GREEN)
        screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2))

# Movement check
def can_move(pos):
    r, c = pos
    return 0 <= r < ROWS and 0 <= c < COLS and game.maze[r][c] == 0

def update_player(move):
    if game.game_over or game.win:
        return

    new_r = game.player_pos[0] + move[0]
    new_c = game.player_pos[1] + move[1]
    if can_move((new_r, new_c)):
        game.player_pos = [new_r, new_c]

    # Coin collection
    if (new_r, new_c) in game.coins:
        game.coins.remove((new_r, new_c))
        game.score += 10

    # Trap collision
    if (new_r, new_c) in game.traps:
        game.traps.remove((new_r, new_c))
        game.lives -= 1
        game.time_limit = max(5, game.time_limit - 5)
        if game.lives <= 0:
            game.game_over = True

    # Time out
    if time.time() - game.start_time > game.time_limit:
        game.game_over = True

    # Reached goal
    if game.player_pos == game.goal_pos:
        game.win = True
        game.score += 50

def main():
    clock = pygame.time.Clock()
    while True:
        screen.fill(GRAY)
        draw_maze()
        draw_entities()
        draw_hud()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    if game.win:
                        game.advance_level()
                    else:
                        game.reset()
                if not game.game_over and not game.win:
                    if event.key == pygame.K_UP:
                        update_player((-1, 0))
                    elif event.key == pygame.K_DOWN:
                        update_player((1, 0))
                    elif event.key == pygame.K_LEFT:
                        update_player((0, -1))
                    elif event.key == pygame.K_RIGHT:
                        update_player((0, 1))

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
