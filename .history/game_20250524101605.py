import pygame
import random
import sys

# Initialize Pygame
pygame.init()

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
CYAN = (0, 255, 255)
BLUE = (0, 0, 255)
ORANGE = (255, 165, 0)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)
PURPLE = (128, 0, 128)
RED = (255, 0, 0)
GRAY = (128, 128, 128)

# Game constants
GRID_WIDTH = 10
GRID_HEIGHT = 20
CELL_SIZE = 30
GRID_X_OFFSET = 50
GRID_Y_OFFSET = 50
WINDOW_WIDTH = GRID_WIDTH * CELL_SIZE + 2 * GRID_X_OFFSET + 200
WINDOW_HEIGHT = GRID_HEIGHT * CELL_SIZE + 2 * GRID_Y_OFFSET

# Tetris pieces (tetrominoes)
PIECES = [
    # I-piece
    [['.....',
      '..#..',
      '..#..',
      '..#..',
      '..#..'],
     ['.....',
      '.....',
      '####.',
      '.....',
      '.....']],
    
    # O-piece
    [['.....',
      '.....',
      '.##..',
      '.##..',
      '.....']],
    
    # T-piece
    [['.....',
      '.....',
      '.#...',
      '###..',
      '.....'],
     ['.....',
      '.....',
      '.#...',
      '.##..',
      '.#...'],
     ['.....',
      '.....',
      '.....',
      '###..',
      '.#...'],
     ['.....',
      '.....',
      '.#...',
      '##...',
      '.#...']],
    
    # S-piece
    [['.....',
      '.....',
      '.##..',
      '##...',
      '.....'],
     ['.....',
      '.....',
      '.#...',
      '.##..',
      '..#..']],
    
    # Z-piece
    [['.....',
      '.....',
      '##...',
      '.##..',
      '.....'],
     ['.....',
      '.....',
      '..#..',
      '.##..',
      '.#...']],
    
    # J-piece
    [['.....',
      '.....',
      '.#...',
      '.#...',
      '##...'],
     ['.....',
      '.....',
      '.....',
      '#....',
      '###..'],
     ['.....',
      '.....',
      '.##..',
      '.#...',
      '.#...'],
     ['.....',
      '.....',
      '.....',
      '###..',
      '..#..']],
    
    # L-piece
    [['.....',
      '.....',
      '.#...',
      '.#...',
      '.##..'],
     ['.....',
      '.....',
      '.....',
      '###..',
      '#....'],
     ['.....',
      '.....',
      '##...',
      '.#...',
      '.#...'],
     ['.....',
      '.....',
      '.....',
      '..#..',
      '###..']]
]

PIECE_COLORS = [CYAN, YELLOW, PURPLE, GREEN, RED, BLUE, ORANGE]

class Tetris:
    def __init__(self):
        self.grid = [[0 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.current_piece = self.new_piece()
        self.next_piece = self.new_piece()
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.fall_time = 0
        self.fall_speed = 500  # milliseconds
        self.game_over = False
        
        # Initialize display
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Tetris")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        
    def new_piece(self):
        piece_type = random.randint(0, len(PIECES) - 1)
        return {
            'type': piece_type,
            'rotation': 0,
            'x': GRID_WIDTH // 2 - 2,
            'y': 0,
            'shape': PIECES[piece_type][0],
            'color': PIECE_COLORS[piece_type]
        }
    
    def rotate_piece(self, piece):
        rotations = PIECES[piece['type']]
        return (piece['rotation'] + 1) % len(rotations)
    
    def get_rotated_piece(self, piece, rotation):
        return PIECES[piece['type']][rotation]
    
    def is_valid_position(self, piece, dx=0, dy=0, rotation=None):
        if rotation is None:
            rotation = piece['rotation']
        
        shape = self.get_rotated_piece(piece, rotation)
        
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell == '#':
                    new_x = piece['x'] + x + dx
                    new_y = piece['y'] + y + dy
                    
                    if (new_x < 0 or new_x >= GRID_WIDTH or 
                        new_y >= GRID_HEIGHT or
                        (new_y >= 0 and self.grid[new_y][new_x] != 0)):
                        return False
        return True
    
    def place_piece(self, piece):
        shape = self.get_rotated_piece(piece, piece['rotation'])
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell == '#':
                    grid_x = piece['x'] + x
                    grid_y = piece['y'] + y
                    if grid_y >= 0:
                        self.grid[grid_y][grid_x] = piece['type'] + 1
    
    def clear_lines(self):
        lines_to_clear = []
        for y in range(GRID_HEIGHT):
            if all(cell != 0 for cell in self.grid[y]):
                lines_to_clear.append(y)
        
        for y in lines_to_clear:
            del self.grid[y]
            self.grid.insert(0, [0 for _ in range(GRID_WIDTH)])
        
        lines_cleared = len(lines_to_clear)
        if lines_cleared > 0:
            self.lines_cleared += lines_cleared
            # Scoring: 40, 100, 300, 1200 for 1, 2, 3, 4 lines
            score_values = [0, 40, 100, 300, 1200]
            self.score += score_values[min(lines_cleared, 4)] * (self.level + 1)
            
            # Increase level every 10 lines
            self.level = self.lines_cleared // 10 + 1
            self.fall_speed = max(50, 500 - (self.level - 1) * 50)
        
        return lines_cleared
    
    def move_piece(self, dx, dy):
        if self.is_valid_position(self.current_piece, dx, dy):
            self.current_piece['x'] += dx
            self.current_piece['y'] += dy
            return True
        return False
    
    def rotate_current_piece(self):
        new_rotation = self.rotate_piece(self.current_piece)
        if self.is_valid_position(self.current_piece, rotation=new_rotation):
            self.current_piece['rotation'] = new_rotation
            self.current_piece['shape'] = self.get_rotated_piece(self.current_piece, new_rotation)
    
    def drop_piece(self):
        while self.move_piece(0, 1):
            self.score += 2  # Bonus points for hard drop
    
    def update(self, dt):
        if self.game_over:
            return
        
        self.fall_time += dt
        if self.fall_time >= self.fall_speed:
            if not self.move_piece(0, 1):
                self.place_piece(self.current_piece)
                self.clear_lines()
                self.current_piece = self.next_piece
                self.next_piece = self.new_piece()
                
                # Check game over
                if not self.is_valid_position(self.current_piece):
                    self.game_over = True
            
            self.fall_time = 0
    
    def draw_grid(self):
        # Draw grid background
        grid_rect = pygame.Rect(GRID_X_OFFSET, GRID_Y_OFFSET, 
                               GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE)
        pygame.draw.rect(self.screen, WHITE, grid_rect)
        pygame.draw.rect(self.screen, BLACK, grid_rect, 2)
        
        # Draw placed pieces
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if self.grid[y][x] != 0:
                    color = PIECE_COLORS[self.grid[y][x] - 1]
                    rect = pygame.Rect(GRID_X_OFFSET + x * CELL_SIZE,
                                     GRID_Y_OFFSET + y * CELL_SIZE,
                                     CELL_SIZE, CELL_SIZE)
                    pygame.draw.rect(self.screen, color, rect)
                    pygame.draw.rect(self.screen, BLACK, rect, 1)
        
        # Draw grid lines
        for x in range(GRID_WIDTH + 1):
            pygame.draw.line(self.screen, GRAY,
                           (GRID_X_OFFSET + x * CELL_SIZE, GRID_Y_OFFSET),
                           (GRID_X_OFFSET + x * CELL_SIZE, GRID_Y_OFFSET + GRID_HEIGHT * CELL_SIZE))
        
        for y in range(GRID_HEIGHT + 1):
            pygame.draw.line(self.screen, GRAY,
                           (GRID_X_OFFSET, GRID_Y_OFFSET + y * CELL_SIZE),
                           (GRID_X_OFFSET + GRID_WIDTH * CELL_SIZE, GRID_Y_OFFSET + y * CELL_SIZE))
    
    def draw_piece(self, piece):
        shape = self.get_rotated_piece(piece, piece['rotation'])
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell == '#':
                    screen_x = GRID_X_OFFSET + (piece['x'] + x) * CELL_SIZE
                    screen_y = GRID_Y_OFFSET + (piece['y'] + y) * CELL_SIZE
                    
                    if screen_y >= GRID_Y_OFFSET:  # Only draw if visible
                        rect = pygame.Rect(screen_x, screen_y, CELL_SIZE, CELL_SIZE)
                        pygame.draw.rect(self.screen, piece['color'], rect)
                        pygame.draw.rect(self.screen, BLACK, rect, 1)
    
    def draw_next_piece(self):
        # Draw next piece preview
        next_x = GRID_X_OFFSET + GRID_WIDTH * CELL_SIZE + 20
        next_y = GRID_Y_OFFSET + 50
        
        text = self.font.render("NEXT:", True, BLACK)
        self.screen.blit(text, (next_x, next_y - 30))
        
        shape = self.next_piece['shape']
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell == '#':
                    rect = pygame.Rect(next_x + x * 20, next_y + y * 20, 20, 20)
                    pygame.draw.rect(self.screen, self.next_piece['color'], rect)
                    pygame.draw.rect(self.screen, BLACK, rect, 1)
    
    def draw_info(self):
        info_x = GRID_X_OFFSET + GRID_WIDTH * CELL_SIZE + 20
        info_y = GRID_Y_OFFSET + 200
        
        score_text = self.font.render(f"Score: {self.score}", True, BLACK)
        level_text = self.font.render(f"Level: {self.level}", True, BLACK)
        lines_text = self.font.render(f"Lines: {self.lines_cleared}", True, BLACK)
        
        self.screen.blit(score_text, (info_x, info_y))
        self.screen.blit(level_text, (info_x, info_y + 40))
        self.screen.blit(lines_text, (info_x, info_y + 80))
        
        if self.game_over:
            game_over_text = self.font.render("GAME OVER", True, RED)
            restart_text = self.font.render("Press R to restart", True, BLACK)
            self.screen.blit(game_over_text, (info_x, info_y + 120))
            self.screen.blit(restart_text, (info_x, info_y + 160))
    
    def draw_controls(self):
        controls_x = GRID_X_OFFSET + GRID_WIDTH * CELL_SIZE + 20
        controls_y = GRID_Y_OFFSET + 350
        
        controls = [
            "Controls:",
            "← → Move",
            "↓ Soft drop",
            "↑ Rotate",
            "Space Hard drop",
            "R Restart"
        ]
        
        for i, control in enumerate(controls):
            color = BLACK if i == 0 else GRAY
            font_size = 24 if i == 0 else 18
            font = pygame.font.Font(None, font_size)
            text = font.render(control, True, color)
            self.screen.blit(text, (controls_x, controls_y + i * 25))
    
    def restart(self):
        self.__init__()
    
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                elif event.type == pygame.KEYDOWN:
                    if self.game_over:
                        if event.key == pygame.K_r:
                            self.restart()
                    else:
                        if event.key == pygame.K_LEFT:
                            self.move_piece(-1, 0)
                        elif event.key == pygame.K_RIGHT:
                            self.move_piece(1, 0)
                        elif event.key == pygame.K_DOWN:
                            if self.move_piece(0, 1):
                                self.score += 1
                        elif event.key == pygame.K_UP:
                            self.rotate_current_piece()
                        elif event.key == pygame.K_SPACE:
                            self.drop_piece()
                    
                    if event.key == pygame.K_r and self.game_over:
                        self.restart()
            
            self.update(dt)
            
            # Draw everything
            self.screen.fill(WHITE)
            self.draw_grid()
            if not self.game_over:
                self.draw_piece(self.current_piece)
            self.draw_next_piece()
            self.draw_info()
            self.draw_controls()
            
            pygame.display.flip()
        
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = Tetris()
    game.run()