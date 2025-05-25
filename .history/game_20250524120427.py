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
LIGHT_GRAY = (200, 200, 200) # Base for panels
DARK_GRAY = (50, 50, 50)    # Base for borders/shadows

# Gradient and Theming Colors
BG_GRAD_TOP = (25, 25, 70) # Dark blueish-purple
BG_GRAD_BOTTOM = (50, 25, 90) # Slightly lighter purple

PANEL_GRAD_TOP = (225, 225, 235) # Light bluish gray
PANEL_GRAD_BOTTOM = (195, 195, 205) # Slightly darker bluish gray

GRID_BG_COLOR = (40, 40, 40) # Dark background for the play area cells
GRID_LINE_COLOR = (60, 60, 60) # Subtle lines within the grid

GHOST_COLOR_BASE = (200, 200, 200) # Base color for ghost, alpha will be applied
GHOST_ALPHA = 100


# Game constants
GRID_WIDTH = 10
GRID_HEIGHT = 20
CELL_SIZE = 30
PREVIEW_CELL_SIZE = 20

# Layout
GRID_X_OFFSET = 50
GRID_Y_OFFSET = 50
SIDE_PANEL_WIDTH = 250
PANEL_PADDING = 10
PANEL_BORDER_RADIUS = 8
CELL_BORDER_RADIUS = 4

WINDOW_WIDTH = GRID_WIDTH * CELL_SIZE + 2 * GRID_X_OFFSET + SIDE_PANEL_WIDTH
WINDOW_HEIGHT = GRID_HEIGHT * CELL_SIZE + 2 * GRID_Y_OFFSET

# Gameplay constants
LOCK_DELAY_DURATION = 500
LINE_CLEAR_ANIM_DURATION = 300
LINE_FLASH_INTERVAL = 75

PIECES = [ # Same as before ]
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


def create_gradient_surface(width, height, top_color, bottom_color, vertical=True):
    """Creates a surface with a linear gradient."""
    surface = pygame.Surface((width, height))
    if vertical:
        for y in range(height):
            r = top_color[0] + (bottom_color[0] - top_color[0]) * y / height
            g = top_color[1] + (bottom_color[1] - top_color[1]) * y / height
            b = top_color[2] + (bottom_color[2] - top_color[2]) * y / height
            pygame.draw.line(surface, (int(r), int(g), int(b)), (0, y), (width -1 , y))
    else: # Horizontal
        for x in range(width):
            r = top_color[0] + (bottom_color[0] - top_color[0]) * x / width
            g = top_color[1] + (bottom_color[1] - top_color[1]) * x / width
            b = top_color[2] + (bottom_color[2] - top_color[2]) * x / width
            pygame.draw.line(surface, (int(r), int(g), int(b)), (x, 0), (x, height -1))
    return surface

class Tetris:
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Graphically Enhanced Tetris")
        self.clock = pygame.time.Clock()
        
        self.font_title = pygame.font.Font(None, 32) # For panel titles
        self.font_large = pygame.font.Font(None, 40) # For Game Over/Paused
        self.font_medium = pygame.font.Font(None, 28) # For score/level
        self.font_small = pygame.font.Font(None, 20)  # For controls text

        self.background_surface = create_gradient_surface(WINDOW_WIDTH, WINDOW_HEIGHT, BG_GRAD_TOP, BG_GRAD_BOTTOM)
        self.panel_gradient_cache = {} # Cache for panel gradients

        self.reset_game()

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
        self.fall_speed = 500
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
            'type': piece_type, 'rotation': 0,
            'x': GRID_WIDTH // 2 - 2, 'y': 0, 
            'shape': PIECES[piece_type][0], 'color': PIECE_COLORS[piece_type]
        }
    
    def get_piece_shape(self, piece_data, rotation=None):
        # ... (same as before)
        if rotation is None:
            rotation = piece_data['rotation']
        return PIECES[piece_data['type']][rotation]


    def is_valid_position(self, piece_data, dx=0, dy=0, rotation=None):
        # ... (same as before)
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
        # ... (same as before)
        shape = self.get_piece_shape(self.current_piece)
        for r, row_str in enumerate(shape):
            for c, cell_char in enumerate(row_str):
                if cell_char == '#':
                    grid_x = self.current_piece['x'] + c
                    grid_y = self.current_piece['y'] + r
                    if 0 <= grid_y < GRID_HEIGHT and 0 <= grid_x < GRID_WIDTH:
                        self.grid[grid_y][grid_x] = self.current_piece['type'] + 1

    def clear_lines(self):
        # ... (same as before, scoring logic unchanged)
        full_lines = []
        for r_idx in range(GRID_HEIGHT):
            if all(self.grid[r_idx][c_idx] != 0 for c_idx in range(GRID_WIDTH)):
                full_lines.append(r_idx)
        
        if full_lines:
            self.lines_to_clear_indices = full_lines
            self.is_clearing_lines_animation = True
            self.line_clear_anim_timer = LINE_CLEAR_ANIM_DURATION

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
        # ... (same as before)
        if self.is_valid_position(self.current_piece, dx, dy):
            self.current_piece['x'] += dx
            self.current_piece['y'] += dy
            if dy > 0 :
                self.is_on_ground = False
                self.lock_timer = 0
            elif dx != 0 and self.is_on_ground:
                 self.lock_timer = LOCK_DELAY_DURATION
            return True
        return False

    def rotate_current_piece(self):
        # ... (same as before)
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
                return True
        return False

    def drop_piece(self):
        # ... (same as before)
        dropped_rows = 0
        while self.move_piece(0, 1):
            dropped_rows +=1
        self.score += dropped_rows * 1
        self.place_piece()
        self.process_after_lock()

    def hold_current_piece(self):
        # ... (same as before)
        if not self.can_swap_hold:
            return

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
        # ... (same as before)
        self.clear_lines()
        if not self.is_clearing_lines_animation:
            self.current_piece = self.next_piece
            self.next_piece = self.new_piece()
            self.can_swap_hold = True
            self.is_on_ground = False
            if not self.is_valid_position(self.current_piece):
                self.game_over = True

    def update(self, dt):
        # ... (same as before)
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
    
    def draw_styled_cell(self, surface, rect, cell_color, cell_size_ref, for_ghost=False):
        """Draws a styled cell with rounded corners and inset effect."""
        dynamic_border_radius = max(1, int(cell_size_ref * 0.15)) # e.g., 4 for CELL_SIZE 30
        line_thickness = max(1, int(cell_size_ref * 0.1))    # e.g., 3 for CELL_SIZE 30

        if for_ghost:
            ghost_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            # Draw a slightly darker version of the ghost base for the main fill
            darker_ghost_base = tuple(max(0, c - 30) for c in GHOST_COLOR_BASE)
            pygame.draw.rect(ghost_surface, darker_ghost_base + (GHOST_ALPHA,), 
                             (0,0,rect.width, rect.height), border_radius=dynamic_border_radius)
            
            # Ghost highlight (brighter than base)
            highlight_ghost = tuple(min(255, c + 20) for c in GHOST_COLOR_BASE)
            pygame.draw.lines(ghost_surface, highlight_ghost + (GHOST_ALPHA,), False, [
                (line_thickness, line_thickness),
                (rect.width - line_thickness -1, line_thickness) ], line_thickness) # Top
            pygame.draw.lines(ghost_surface, highlight_ghost + (GHOST_ALPHA,), False, [
                (line_thickness, line_thickness),
                (line_thickness, rect.height - line_thickness -1)], line_thickness) # Left
            
            surface.blit(ghost_surface, rect.topleft)
            pygame.draw.rect(surface, tuple(c // 2 for c in GHOST_COLOR_BASE), rect, 1, border_radius=dynamic_border_radius) # Darker border
            return

        # Base color fill
        pygame.draw.rect(surface, cell_color, rect, border_radius=dynamic_border_radius)

        highlight_color = tuple(min(255, c + 60) for c in cell_color)
        shadow_color = tuple(max(0, c - 60) for c in cell_color)

        # Highlight (top and left edges, inset)
        pygame.draw.lines(surface, highlight_color, False, [
            (rect.left + line_thickness, rect.top + line_thickness),
            (rect.right - line_thickness -1, rect.top + line_thickness) # Top line
        ], line_thickness)
        pygame.draw.lines(surface, highlight_color, False, [
            (rect.left + line_thickness, rect.top + line_thickness + (line_thickness//2)), # Adjusted start to avoid corner overlap
            (rect.left + line_thickness, rect.bottom - line_thickness -1) # Left line
        ], line_thickness)

        # Shadow (bottom and right edges, inset)
        pygame.draw.lines(surface, shadow_color, False, [
            (rect.left + line_thickness, rect.bottom - line_thickness -1),
            (rect.right - line_thickness -1, rect.bottom - line_thickness -1) # Bottom line
        ], line_thickness)
        pygame.draw.lines(surface, shadow_color, False, [
            (rect.right - line_thickness -1, rect.top + line_thickness + (line_thickness//2)), # Adjusted start
            (rect.right - line_thickness -1, rect.bottom - line_thickness -(line_thickness//2)) # Right line
        ], line_thickness)
        
        # Outer border
        pygame.draw.rect(surface, BLACK, rect, 1, border_radius=dynamic_border_radius)


    def draw_grid(self):
        # Draw Grid Well Effect
        well_rect_outer = pygame.Rect(
            GRID_X_OFFSET - 4, GRID_Y_OFFSET - 4,
            GRID_WIDTH * CELL_SIZE + 8, GRID_HEIGHT * CELL_SIZE + 8
        )
        # Shadow part of the well
        pygame.draw.rect(self.screen, (20,20,20), well_rect_outer, border_radius=PANEL_BORDER_RADIUS)
        # Highlight part of the well (slightly offset)
        well_highlight_rect = pygame.Rect(
             GRID_X_OFFSET - 6, GRID_Y_OFFSET - 6,
            GRID_WIDTH * CELL_SIZE + 8, GRID_HEIGHT * CELL_SIZE + 8
        )
        pygame.draw.rect(self.screen, (90,90,100), well_highlight_rect, 2, border_radius=PANEL_BORDER_RADIUS)


        # Draw grid background (actual play area)
        grid_rect_inner = pygame.Rect(GRID_X_OFFSET, GRID_Y_OFFSET, 
                                 GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE)
        pygame.draw.rect(self.screen, GRID_BG_COLOR, grid_rect_inner)

        # Draw placed pieces
        for r_idx in range(GRID_HEIGHT):
            for c_idx in range(GRID_WIDTH):
                cell_value = self.grid[r_idx][c_idx]
                if cell_value != 0:
                    color = PIECE_COLORS[cell_value - 1]
                    rect = pygame.Rect(GRID_X_OFFSET + c_idx * CELL_SIZE,
                                     GRID_Y_OFFSET + r_idx * CELL_SIZE,
                                     CELL_SIZE, CELL_SIZE)
                    
                    if self.is_clearing_lines_animation and r_idx in self.lines_to_clear_indices:
                        flash_on = (self.line_clear_anim_timer // LINE_FLASH_INTERVAL) % 2 == 0
                        draw_color = WHITE if flash_on else color
                        # Simple flash for clearing lines
                        pygame.draw.rect(self.screen, draw_color, rect, border_radius=CELL_BORDER_RADIUS)
                        pygame.draw.rect(self.screen, BLACK, rect, 1, border_radius=CELL_BORDER_RADIUS)
                    else:
                        self.draw_styled_cell(self.screen, rect, color, CELL_SIZE)
        
        # Draw grid lines (subtle)
        for c_idx in range(1, GRID_WIDTH):
            pygame.draw.line(self.screen, GRID_LINE_COLOR,
                           (GRID_X_OFFSET + c_idx * CELL_SIZE, GRID_Y_OFFSET),
                           (GRID_X_OFFSET + c_idx * CELL_SIZE, GRID_Y_OFFSET + GRID_HEIGHT * CELL_SIZE))
        for r_idx in range(1, GRID_HEIGHT):
            pygame.draw.line(self.screen, GRID_LINE_COLOR,
                           (GRID_X_OFFSET, GRID_Y_OFFSET + r_idx * CELL_SIZE),
                           (GRID_X_OFFSET + GRID_WIDTH * CELL_SIZE, GRID_Y_OFFSET + r_idx * CELL_SIZE))

    def draw_piece(self, piece_data, screen_x_offset, screen_y_offset, current_cell_size, is_ghost=False, is_preview=False):
        shape = self.get_piece_shape(piece_data)
        base_x = piece_data['x'] if not is_preview else 0
        base_y = piece_data['y'] if not is_preview else 0
        
        offset_x, offset_y = 0, 0
        if is_preview:
            min_r, min_c, max_r, max_c, has_blocks = 5, 5, 0, 0, False
            for r, row_str in enumerate(shape):
                for c, cell_char in enumerate(row_str):
                    if cell_char == '#':
                        has_blocks = True
                        min_r, min_c, max_r, max_c = min(min_r, r), min(min_c, c), max(max_r, r), max(max_c, c)
            if has_blocks:
                piece_width_cells = max_c - min_c + 1
                piece_height_cells = max_r - min_r + 1
                preview_area_cells_dim = 4 # Draw piece within a 4x4 cell area for preview
                offset_x = (preview_area_cells_dim * current_cell_size - piece_width_cells * current_cell_size) / 2 - min_c * current_cell_size
                offset_y = (preview_area_cells_dim * current_cell_size - piece_height_cells * current_cell_size) / 2 - min_r * current_cell_size

        for r_idx, row_str in enumerate(shape):
            for c_idx, cell_char in enumerate(row_str):
                if cell_char == '#':
                    if is_preview:
                        screen_x = screen_x_offset + c_idx * current_cell_size + offset_x
                        screen_y = screen_y_offset + r_idx * current_cell_size + offset_y
                    else:
                        screen_x = screen_x_offset + (base_x + c_idx) * current_cell_size
                        screen_y = screen_y_offset + (base_y + r_idx) * current_cell_size
                    
                    if not is_preview and screen_y < GRID_Y_OFFSET: # Don't draw parts above visible grid
                        continue
                        
                    rect = pygame.Rect(screen_x, screen_y, current_cell_size, current_cell_size)
                    self.draw_styled_cell(self.screen, rect, piece_data['color'], current_cell_size, for_ghost=is_ghost)


    def get_ghost_piece_y(self):
        # ... (same as before)
        ghost_y = self.current_piece['y']
        while self.is_valid_position(self.current_piece, 0, ghost_y - self.current_piece['y'] + 1):
            ghost_y += 1
        return ghost_y

    def draw_panel(self, x, y, width, height, title):
        panel_rect = pygame.Rect(x, y, width, height)

        # Get or create gradient surface for the panel
        grad_key = (width, height)
        if grad_key not in self.panel_gradient_cache:
            self.panel_gradient_cache[grad_key] = create_gradient_surface(width, height, PANEL_GRAD_TOP, PANEL_GRAD_BOTTOM)
        
        self.screen.blit(self.panel_gradient_cache[grad_key], panel_rect.topleft)
        pygame.draw.rect(self.screen, DARK_GRAY, panel_rect, 2, border_radius=PANEL_BORDER_RADIUS)

        title_text = self.font_title.render(title, True, DARK_GRAY) # Darker title text
        title_rect = title_text.get_rect(centerx=panel_rect.centerx, top=panel_rect.top + PANEL_PADDING // 2)
        self.screen.blit(title_text, title_rect)
        return panel_rect

    def draw_side_panel_content(self):
        # ... (layout logic largely same, font/color updates)
        panel_x = GRID_X_OFFSET + GRID_WIDTH * CELL_SIZE + GRID_X_OFFSET // 2
        current_y = GRID_Y_OFFSET
        panel_width = SIDE_PANEL_WIDTH - GRID_X_OFFSET # Adjusted width for content

        # Hold Piece Panel
        hold_panel_height = 4 * PREVIEW_CELL_SIZE + 2 * PANEL_PADDING + 35 
        hold_panel_rect = self.draw_panel(panel_x, current_y, panel_width, hold_panel_height, "HOLD (C)")
        if self.held_piece:
            self.draw_piece(self.held_piece, 
                            hold_panel_rect.left + PANEL_PADDING, 
                            hold_panel_rect.top + 35, # Space for title
                            PREVIEW_CELL_SIZE, is_preview=True)
        current_y += hold_panel_height + PANEL_PADDING

        # Next Piece Panel
        next_panel_height = 4 * PREVIEW_CELL_SIZE + 2 * PANEL_PADDING + 35
        next_panel_rect = self.draw_panel(panel_x, current_y, panel_width, next_panel_height, "NEXT")
        if self.next_piece:
            self.draw_piece(self.next_piece, 
                            next_panel_rect.left + PANEL_PADDING, 
                            next_panel_rect.top + 35, 
                            PREVIEW_CELL_SIZE, is_preview=True)
        current_y += next_panel_height + PANEL_PADDING

        # Info Panel
        info_panel_height = 160 
        info_panel_rect = self.draw_panel(panel_x, current_y, panel_width, info_panel_height, "INFO")
        
        score_text = self.font_medium.render(f"Score: {self.score}", True, BLACK)
        level_text = self.font_medium.render(f"Level: {self.level}", True, BLACK)
        lines_text = self.font_medium.render(f"Lines: {self.lines_cleared}", True, BLACK)
        
        info_content_y = info_panel_rect.top + 35 + PANEL_PADDING // 2
        text_spacing = 30
        self.screen.blit(score_text, (info_panel_rect.left + PANEL_PADDING, info_content_y))
        self.screen.blit(level_text, (info_panel_rect.left + PANEL_PADDING, info_content_y + text_spacing))
        self.screen.blit(lines_text, (info_panel_rect.left + PANEL_PADDING, info_content_y + 2 * text_spacing))
        
        if self.game_over:
            game_over_text = self.font_large.render("GAME OVER", True, RED)
            text_rect = game_over_text.get_rect(centerx=info_panel_rect.centerx, top=info_content_y + 3 * text_spacing)
            self.screen.blit(game_over_text, text_rect)
        elif self.paused:
            paused_text = self.font_large.render("PAUSED", True, BLUE)
            text_rect = paused_text.get_rect(centerx=info_panel_rect.centerx, top=info_content_y + 3 * text_spacing)
            self.screen.blit(paused_text, text_rect)

        current_y += info_panel_height + PANEL_PADDING

        # Controls Panel
        controls_text_list = [
            "← → Move", "↓ Soft Drop", "↑ Rotate",
            "SPACE Hard Drop", "C Hold", "P Pause", "R Restart"
        ]
        controls_panel_height = len(controls_text_list) * 22 + 2 * PANEL_PADDING + 35
        controls_panel_rect = self.draw_panel(panel_x, current_y, panel_width, controls_panel_height, "CONTROLS")

        controls_content_y = controls_panel_rect.top + 35 + PANEL_PADDING //2
        for i, control_str in enumerate(controls_text_list):
            text = self.font_small.render(control_str, True, BLACK) # Black for better readability
            self.screen.blit(text, (controls_panel_rect.left + PANEL_PADDING, controls_content_y + i * 22))


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
                        if not self.game_over: self.paused = not self.paused
                        continue
                    if self.game_over or self.paused or self.is_clearing_lines_animation:
                        continue
                    # Gameplay inputs (same as before)
                    if event.key == pygame.K_LEFT: self.move_piece(-1, 0)
                    elif event.key == pygame.K_RIGHT: self.move_piece(1, 0)
                    elif event.key == pygame.K_DOWN:
                        if self.move_piece(0, 1): self.score += 1; self.fall_time = 0
                    elif event.key == pygame.K_UP: self.rotate_current_piece()
                    elif event.key == pygame.K_SPACE: self.drop_piece()
                    elif event.key == pygame.K_c: self.hold_current_piece()
            
            self.update(dt)
            
            # Draw everything
            self.screen.blit(self.background_surface, (0,0)) # Blit pre-rendered background
            self.draw_grid()
            
            if not self.game_over and self.current_piece: # Ensure current_piece exists
                ghost_y_pos = self.get_ghost_piece_y()
                ghost_piece_data = {**self.current_piece, 'y': ghost_y_pos} # Create a new dict for ghost
                self.draw_piece(ghost_piece_data, GRID_X_OFFSET, GRID_Y_OFFSET, CELL_SIZE, is_ghost=True)
                self.draw_piece(self.current_piece, GRID_X_OFFSET, GRID_Y_OFFSET, CELL_SIZE)

            self.draw_side_panel_content()
            pygame.display.flip()
        
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = Tetris()
    game.run()