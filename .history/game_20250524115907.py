import pygame
import random
import sys

# Initialize Pygame
pygame.init()
# pygame.mixer.init() # REMOVED: Sound initialization

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
LIGHT_GRAY = (200, 200, 200)
DARK_GRAY = (50, 50, 50)
BACKGROUND_COLOR = (210, 210, 210) # Main window background

# Game constants
GRID_WIDTH = 10
GRID_HEIGHT = 20
CELL_SIZE = 30
PREVIEW_CELL_SIZE = 20 # For Next/Hold pieces

# Layout
GRID_X_OFFSET = 50
GRID_Y_OFFSET = 50
SIDE_PANEL_WIDTH = 250
PANEL_PADDING = 10

WINDOW_WIDTH = GRID_WIDTH * CELL_SIZE + 2 * GRID_X_OFFSET + SIDE_PANEL_WIDTH
WINDOW_HEIGHT = GRID_HEIGHT * CELL_SIZE + 2 * GRID_Y_OFFSET

# Gameplay constants
LOCK_DELAY_DURATION = 500  # milliseconds
LINE_CLEAR_ANIM_DURATION = 300 # ms
LINE_FLASH_INTERVAL = 75 # ms

# Tetris pieces (tetrominoes) - Standard 5x5 representation
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
      '.#...',
      '###..',
      '.....',
      '.....'],
     ['.....',
      '.#...',
      '.##..',
      '.#...',
      '.....'],
     ['.....',
      '.....',
      '###..',
      '.#...',
      '.....'],
     ['.....',
      '.#...',
      '##...',
      '.#...',
      '.....']],
    # S-piece
    [['.....',
      '.....',
      '.##..',
      '##...',
      '.....'],
     ['.....',
      '.#...',
      '.##..',
      '..#..',
      '.....']],
    # Z-piece
    [['.....',
      '.....',
      '##...',
      '.##..',
      '.....'],
     ['.....',
      '..#..',
      '.##..',
      '.#...',
      '.....']],
    # J-piece
    [['.....',
      '.#...',
      '.#...',
      '##...',
      '.....'],
     ['.....',
      '#....',
      '###..',
      '.....',
      '.....'],
     ['.....',
      '.##..',
      '.#...',
      '.#...',
      '.....'],
     ['.....',
      '###..',
      '..#..',
      '.....',
      '.....']],
    # L-piece
    [['.....',
      '..#..',
      '..#..',
      '.##..',
      '.....'],
     ['.....',
      '###..',
      '#....',
      '.....',
      '.....'],
     ['.....',
      '##...',
      '.#...',
      '.#...',
      '.....'],
     ['.....',
      '..#..',
      '###..',
      '.....',
      '.....']]
]

PIECE_COLORS = [CYAN, YELLOW, PURPLE, GREEN, RED, BLUE, ORANGE]
GHOST_COLOR = (100, 100, 100, 150) # Semi-transparent gray

class Tetris:
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Enhanced Tetris (No Sound)") # Updated caption
        self.clock = pygame.time.Clock()
        self.font_large = pygame.font.Font(None, 36)
        self.font_medium = pygame.font.Font(None, 28)
        self.font_small = pygame.font.Font(None, 20)
        
        # REMOVED: All sfx attributes
        # self.sfx_move = self.load_sound("move.wav")
        # ... and others

        self.reset_game()

    # REMOVED: load_sound method
    # def load_sound(self, filename):
    #     ...

    def reset_game(self):
        self.grid = [[0 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.current_piece = self.new_piece()
        self.next_piece = self.new_piece()
        self.held_piece = None
        self.can_swap_hold = True
        
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        
        self.fall_time = 0
        self.fall_speed = 500  # milliseconds
        
        self.is_on_ground = False
        self.lock_timer = 0
        
        self.lines_to_clear_indices = []
        self.is_clearing_lines_animation = False
        self.line_clear_anim_timer = 0
        
        self.game_over = False
        self.paused = False
        
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
    
    def get_piece_shape(self, piece_data, rotation=None):
        if rotation is None:
            rotation = piece_data['rotation']
        return PIECES[piece_data['type']][rotation]

    def is_valid_position(self, piece_data, dx=0, dy=0, rotation=None):
        _rotation = rotation if rotation is not None else piece_data['rotation']
        shape = self.get_piece_shape(piece_data, _rotation)
        
        for r, row_str in enumerate(shape):
            for c, cell_char in enumerate(row_str):
                if cell_char == '#':
                    new_x = piece_data['x'] + c + dx
                    new_y = piece_data['y'] + r + dy
                    
                    if not (0 <= new_x < GRID_WIDTH and 0 <= new_y < GRID_HEIGHT):
                        if new_x < 0 or new_x >= GRID_WIDTH or new_y >= GRID_HEIGHT:
                            return False
                    elif new_y >= 0 and self.grid[new_y][new_x] != 0:
                        return False
        return True

    def place_piece(self):
        shape = self.get_piece_shape(self.current_piece)
        for r, row_str in enumerate(shape):
            for c, cell_char in enumerate(row_str):
                if cell_char == '#':
                    grid_x = self.current_piece['x'] + c
                    grid_y = self.current_piece['y'] + r
                    if 0 <= grid_y < GRID_HEIGHT and 0 <= grid_x < GRID_WIDTH:
                        self.grid[grid_y][grid_x] = self.current_piece['type'] + 1
        # self.sfx_land.play() # REMOVED

    def clear_lines(self):
        full_lines = []
        for r_idx in range(GRID_HEIGHT):
            if all(self.grid[r_idx][c_idx] != 0 for c_idx in range(GRID_WIDTH)):
                full_lines.append(r_idx)
        
        if full_lines:
            self.lines_to_clear_indices = full_lines
            self.is_clearing_lines_animation = True
            self.line_clear_anim_timer = LINE_CLEAR_ANIM_DURATION
            # self.sfx_clear.play() # REMOVED

            num_cleared = len(full_lines)
            self.lines_cleared += num_cleared
            score_values = [0, 40, 100, 300, 1200]
            self.score += score_values[min(num_cleared, 4)] * self.level
            
            new_level = self.lines_cleared // 10 + 1
            if new_level > self.level:
                self.level = new_level
                self.fall_speed = max(100, 500 - (self.level - 1) * 40)
        
        return len(full_lines)

    def move_piece(self, dx, dy):
        if self.is_valid_position(self.current_piece, dx, dy):
            self.current_piece['x'] += dx
            self.current_piece['y'] += dy
            if dy > 0 :
                self.is_on_ground = False
                self.lock_timer = 0
            elif dx != 0 and self.is_on_ground:
                 self.lock_timer = LOCK_DELAY_DURATION
            # if dx != 0: self.sfx_move.play() # REMOVED
            return True
        return False

    def rotate_current_piece(self):
        piece = self.current_piece
        new_rotation = (piece['rotation'] + 1) % len(PIECES[piece['type']])
        kick_offsets = [0, 1, -1, 2, -2] 
        
        for dx_kick in kick_offsets:
            if self.is_valid_position(piece, dx=dx_kick, dy=0, rotation=new_rotation):
                piece['x'] += dx_kick
                piece['rotation'] = new_rotation
                piece['shape'] = self.get_piece_shape(piece)
                
                if self.is_on_ground:
                    self.lock_timer = LOCK_DELAY_DURATION
                # self.sfx_rotate.play() # REMOVED
                return True
        return False

    def drop_piece(self):
        dropped_rows = 0
        while self.move_piece(0, 1):
            dropped_rows +=1
        self.score += dropped_rows * 1
        self.place_piece()
        self.process_after_lock()
        # self.sfx_hard_drop.play() # REMOVED

    def hold_current_piece(self):
        if not self.can_swap_hold:
            return

        # self.sfx_hold.play() # REMOVED
        if self.held_piece is None:
            self.held_piece = self.current_piece
            self.current_piece = self.next_piece
            self.next_piece = self.new_piece()
        else:
            self.current_piece, self.held_piece = self.held_piece, self.current_piece
        
        self.current_piece['x'] = GRID_WIDTH // 2 - 2
        self.current_piece['y'] = 0
        self.current_piece['rotation'] = 0
        self.current_piece['shape'] = self.get_piece_shape(self.current_piece)

        self.is_on_ground = False
        self.lock_timer = 0
        self.can_swap_hold = False

        if not self.is_valid_position(self.current_piece):
            self.game_over = True

    def process_after_lock(self):
        self.clear_lines()
        if not self.is_clearing_lines_animation:
            self.current_piece = self.next_piece
            self.next_piece = self.new_piece()
            self.can_swap_hold = True
            self.is_on_ground = False
            if not self.is_valid_position(self.current_piece):
                self.game_over = True
                # self.sfx_gameover.play() # REMOVED

    def update(self, dt):
        if self.game_over or self.paused:
            return

        if self.is_clearing_lines_animation:
            self.line_clear_anim_timer -= dt
            if self.line_clear_anim_timer <= 0:
                self.is_clearing_lines_animation = False
                for r_idx in sorted(self.lines_to_clear_indices, reverse=True):
                    del self.grid[r_idx]
                    self.grid.insert(0, [0 for _ in range(GRID_WIDTH)])
                self.lines_to_clear_indices = []
                
                self.current_piece = self.next_piece
                self.next_piece = self.new_piece()
                self.can_swap_hold = True
                self.is_on_ground = False
                if not self.is_valid_position(self.current_piece):
                    self.game_over = True
                    # self.sfx_gameover.play() # REMOVED
            return

        self.fall_time += dt
        
        if not self.is_valid_position(self.current_piece, 0, 1):
            if not self.is_on_ground:
                self.is_on_ground = True
                self.lock_timer = LOCK_DELAY_DURATION
            
            if self.is_on_ground:
                self.lock_timer -= dt
                if self.lock_timer <= 0:
                    self.place_piece()
                    self.process_after_lock()
        else:
            self.is_on_ground = False
            self.lock_timer = 0
            if self.fall_time >= self.fall_speed:
                self.move_piece(0, 1)
                self.fall_time = 0
    
    def draw_styled_cell(self, surface, rect, cell_color, for_ghost=False):
        if for_ghost:
            s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            s.fill((cell_color[0], cell_color[1], cell_color[2], GHOST_COLOR[3]))
            surface.blit(s, rect.topleft)
            pygame.draw.rect(surface, (200,200,200,100), rect, 1)
            return

        pygame.draw.rect(surface, cell_color, rect)
        highlight_color = tuple(min(255, c + 40) for c in cell_color)
        shadow_color = tuple(max(0, c - 40) for c in cell_color)
        pygame.draw.line(surface, highlight_color, (rect.left + 1, rect.top + 1), (rect.right - 2, rect.top + 1), 1)
        pygame.draw.line(surface, highlight_color, (rect.left + 1, rect.top + 1), (rect.left + 1, rect.bottom - 2), 1)
        pygame.draw.line(surface, shadow_color, (rect.left + 1, rect.bottom - 2), (rect.right - 2, rect.bottom - 2), 1)
        pygame.draw.line(surface, shadow_color, (rect.right - 2, rect.top + 1), (rect.right - 2, rect.bottom - 2), 1)
        pygame.draw.rect(surface, BLACK, rect, 1)

    def draw_grid(self):
        grid_bg_color = (180, 180, 180)
        grid_rect_outer = pygame.Rect(GRID_X_OFFSET - 2, GRID_Y_OFFSET - 2, 
                                 GRID_WIDTH * CELL_SIZE + 4, GRID_HEIGHT * CELL_SIZE + 4)
        pygame.draw.rect(self.screen, DARK_GRAY, grid_rect_outer, border_radius=3)
        grid_rect_inner = pygame.Rect(GRID_X_OFFSET, GRID_Y_OFFSET, 
                                 GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE)
        pygame.draw.rect(self.screen, grid_bg_color, grid_rect_inner)

        for r_idx in range(GRID_HEIGHT):
            for c_idx in range(GRID_WIDTH):
                cell_value = self.grid[r_idx][c_idx]
                if cell_value != 0:
                    color_idx = cell_value - 1
                    color = PIECE_COLORS[color_idx]
                    rect = pygame.Rect(GRID_X_OFFSET + c_idx * CELL_SIZE,
                                     GRID_Y_OFFSET + r_idx * CELL_SIZE,
                                     CELL_SIZE, CELL_SIZE)
                    
                    if self.is_clearing_lines_animation and r_idx in self.lines_to_clear_indices:
                        flash_on = (self.line_clear_anim_timer // LINE_FLASH_INTERVAL) % 2 == 0
                        draw_color = WHITE if flash_on else color
                        pygame.draw.rect(self.screen, draw_color, rect)
                        pygame.draw.rect(self.screen, BLACK, rect, 1)
                    else:
                        self.draw_styled_cell(self.screen, rect, color)
        
        line_color = (150, 150, 150)
        for c_idx in range(1, GRID_WIDTH):
            pygame.draw.line(self.screen, line_color,
                           (GRID_X_OFFSET + c_idx * CELL_SIZE, GRID_Y_OFFSET),
                           (GRID_X_OFFSET + c_idx * CELL_SIZE, GRID_Y_OFFSET + GRID_HEIGHT * CELL_SIZE))
        for r_idx in range(1, GRID_HEIGHT):
            pygame.draw.line(self.screen, line_color,
                           (GRID_X_OFFSET, GRID_Y_OFFSET + r_idx * CELL_SIZE),
                           (GRID_X_OFFSET + GRID_WIDTH * CELL_SIZE, GRID_Y_OFFSET + r_idx * CELL_SIZE))

    def draw_piece(self, piece_data, screen_x_offset, screen_y_offset, cell_size, is_ghost=False, is_preview=False):
        shape = self.get_piece_shape(piece_data)
        base_x = piece_data['x'] if not is_preview else 0
        base_y = piece_data['y'] if not is_preview else 0
        
        if is_preview:
            min_r, min_c = 5, 5
            max_r, max_c = 0, 0
            has_blocks = False
            for r, row_str in enumerate(shape):
                for c, cell_char in enumerate(row_str):
                    if cell_char == '#':
                        has_blocks = True
                        min_r = min(min_r, r)
                        min_c = min(min_c, c)
                        max_r = max(max_r, r)
                        max_c = max(max_c, c)
            
            if has_blocks:
                piece_width_in_cells = max_c - min_c + 1
                piece_height_in_cells = max_r - min_r + 1
                preview_area_width = 4 * cell_size 
                preview_area_height = 4 * cell_size
                offset_x = (preview_area_width - piece_width_in_cells * cell_size) / 2 - min_c * cell_size
                offset_y = (preview_area_height - piece_height_in_cells * cell_size) / 2 - min_r * cell_size
            else:
                offset_x, offset_y = 0,0

        for r_idx, row_str in enumerate(shape):
            for c_idx, cell_char in enumerate(row_str):
                if cell_char == '#':
                    if is_preview:
                        screen_x = screen_x_offset + c_idx * cell_size + offset_x
                        screen_y = screen_y_offset + r_idx * cell_size + offset_y
                    else:
                        screen_x = screen_x_offset + (base_x + c_idx) * cell_size
                        screen_y = screen_y_offset + (base_y + r_idx) * cell_size
                    
                    if not is_preview and screen_y < GRID_Y_OFFSET:
                        continue
                        
                    rect = pygame.Rect(screen_x, screen_y, cell_size, cell_size)
                    color_to_draw = GHOST_COLOR if is_ghost else piece_data['color']
                    self.draw_styled_cell(self.screen, rect, color_to_draw, for_ghost=is_ghost)

    def get_ghost_piece_y(self):
        ghost_y = self.current_piece['y']
        while self.is_valid_position(self.current_piece, 0, ghost_y - self.current_piece['y'] + 1):
            ghost_y += 1
        return ghost_y

    def draw_panel(self, x, y, width, height, title):
        panel_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, LIGHT_GRAY, panel_rect, border_radius=5)
        pygame.draw.rect(self.screen, DARK_GRAY, panel_rect, 2, border_radius=5)

        title_text = self.font_medium.render(title, True, BLACK)
        title_rect = title_text.get_rect(centerx=panel_rect.centerx, top=panel_rect.top + PANEL_PADDING)
        self.screen.blit(title_text, title_rect)
        return panel_rect

    def draw_side_panel_content(self):
        panel_x = GRID_X_OFFSET + GRID_WIDTH * CELL_SIZE + GRID_X_OFFSET // 2
        current_y = GRID_Y_OFFSET

        hold_panel_height = 4 * PREVIEW_CELL_SIZE + 2 * PANEL_PADDING + 30
        hold_panel_rect = self.draw_panel(panel_x, current_y, SIDE_PANEL_WIDTH - GRID_X_OFFSET, hold_panel_height, "HOLD (C)")
        if self.held_piece:
            self.draw_piece(self.held_piece, 
                            hold_panel_rect.left + PANEL_PADDING, 
                            hold_panel_rect.top + 30 + PANEL_PADDING, 
                            PREVIEW_CELL_SIZE, is_preview=True)
        current_y += hold_panel_height + PANEL_PADDING

        next_panel_height = 4 * PREVIEW_CELL_SIZE + 2 * PANEL_PADDING + 30
        next_panel_rect = self.draw_panel(panel_x, current_y, SIDE_PANEL_WIDTH - GRID_X_OFFSET, next_panel_height, "NEXT")
        if self.next_piece:
            self.draw_piece(self.next_piece, 
                            next_panel_rect.left + PANEL_PADDING, 
                            next_panel_rect.top + 30 + PANEL_PADDING, 
                            PREVIEW_CELL_SIZE, is_preview=True)
        current_y += next_panel_height + PANEL_PADDING

        info_panel_height = 150
        info_panel_rect = self.draw_panel(panel_x, current_y, SIDE_PANEL_WIDTH - GRID_X_OFFSET, info_panel_height, "INFO")
        
        score_text = self.font_medium.render(f"Score: {self.score}", True, BLACK)
        level_text = self.font_medium.render(f"Level: {self.level}", True, BLACK)
        lines_text = self.font_medium.render(f"Lines: {self.lines_cleared}", True, BLACK)
        
        info_content_y = info_panel_rect.top + 30 + PANEL_PADDING
        self.screen.blit(score_text, (info_panel_rect.left + PANEL_PADDING, info_content_y))
        self.screen.blit(level_text, (info_panel_rect.left + PANEL_PADDING, info_content_y + 30))
        self.screen.blit(lines_text, (info_panel_rect.left + PANEL_PADDING, info_content_y + 60))
        
        if self.game_over:
            game_over_text = self.font_large.render("GAME OVER", True, RED)
            self.screen.blit(game_over_text, (info_panel_rect.left + PANEL_PADDING, info_content_y + 90))
        elif self.paused:
            paused_text = self.font_large.render("PAUSED", True, BLUE)
            self.screen.blit(paused_text, (info_panel_rect.left + PANEL_PADDING, info_content_y + 90))

        current_y += info_panel_height + PANEL_PADDING

        controls_text_list = [
            "← → Move", "↓ Soft Drop", "↑ Rotate",
            "SPACE Hard Drop", "C Hold", "P Pause", "R Restart"
        ]
        controls_panel_height = len(controls_text_list) * 20 + 2 * PANEL_PADDING + 30
        controls_panel_rect = self.draw_panel(panel_x, current_y, SIDE_PANEL_WIDTH - GRID_X_OFFSET, controls_panel_height, "CONTROLS")

        controls_content_y = controls_panel_rect.top + 30 + PANEL_PADDING
        for i, control_str in enumerate(controls_text_list):
            text = self.font_small.render(control_str, True, DARK_GRAY)
            self.screen.blit(text, (controls_panel_rect.left + PANEL_PADDING, controls_content_y + i * 20))

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        self.reset_game()
                        continue

                    if event.key == pygame.K_p:
                        if not self.game_over:
                           self.paused = not self.paused
                        continue
                    
                    if self.game_over or self.paused or self.is_clearing_lines_animation:
                        continue

                    if event.key == pygame.K_LEFT:
                        self.move_piece(-1, 0)
                    elif event.key == pygame.K_RIGHT:
                        self.move_piece(1, 0)
                    elif event.key == pygame.K_DOWN:
                        if self.move_piece(0, 1):
                            self.score += 1
                            self.fall_time = 0
                    elif event.key == pygame.K_UP:
                        self.rotate_current_piece()
                    elif event.key == pygame.K_SPACE:
                        self.drop_piece()
                    elif event.key == pygame.K_c:
                        self.hold_current_piece()
            
            self.update(dt)
            
            self.screen.fill(BACKGROUND_COLOR)
            self.draw_grid()
            
            if not self.game_over:
                ghost_y_pos = self.get_ghost_piece_y()
                ghost_piece_data = self.current_piece.copy()
                ghost_piece_data['y'] = ghost_y_pos
                self.draw_piece(ghost_piece_data, GRID_X_OFFSET, GRID_Y_OFFSET, CELL_SIZE, is_ghost=True)
                
                self.draw_piece(self.current_piece, GRID_X_OFFSET, GRID_Y_OFFSET, CELL_SIZE)

            self.draw_side_panel_content()
            
            pygame.display.flip()
        
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = Tetris()
    game.run()