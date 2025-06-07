import pygame
import random
import sys

# Initialize Pygame
pygame.init()

# Screen dimensions
WIDTH, HEIGHT = 400, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Car Racing Arcade")

# Colors
WHITE = (255, 255, 255)
GRAY = (100, 100, 100)
RED = (200, 0, 0)
BLUE = (0, 0, 200)
GREEN = (0, 200, 0)

# Clock and font
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 48)

# Player car
player_width = 50
player_height = 100
player_x = WIDTH // 2 - player_width // 2
player_y = HEIGHT - player_height - 10
player_speed = 5

# Enemy car
enemy_width = 50
enemy_height = 100
enemy_x = random.randint(50, WIDTH - 100)
enemy_y = -100
enemy_speed = 5

# Road lines
line_y = 0

def draw_road():
    global line_y
    screen.fill(GRAY)
    pygame.draw.rect(screen, GREEN, (0, 0, 50, HEIGHT))
    pygame.draw.rect(screen, GREEN, (WIDTH - 50, 0, 50, HEIGHT))
    # Lane lines
    for i in range(20):
        pygame.draw.rect(screen, WHITE, (WIDTH//2 - 5, (i * 40 + line_y) % HEIGHT, 10, 30))
    line_y += 5
    if line_y > 40:
        line_y = 0

def draw_car(x, y, color):
    pygame.draw.rect(screen, color, (x, y, player_width, player_height))

def show_game_over():
    text = font.render("GAME OVER", True, RED)
    screen.blit(text, (WIDTH//2 - 100, HEIGHT//2 - 30))
    pygame.display.flip()
    pygame.time.wait(2000)
    sys.exit()

# Game loop
running = True
while running:
    clock.tick(60)
    draw_road()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Player movement
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT] and player_x > 60:
        player_x -= player_speed
    if keys[pygame.K_RIGHT] and player_x < WIDTH - player_width - 60:
        player_x += player_speed

    # Enemy car movement
    enemy_y += enemy_speed
    if enemy_y > HEIGHT:
        enemy_y = -100
        enemy_x = random.randint(60, WIDTH - 60 - enemy_width)

    # Draw player and enemy
    draw_car(player_x, player_y, BLUE)
    draw_car(enemy_x, enemy_y, RED)

    # Collision detection
    if (
        enemy_y + enemy_height > player_y and
        enemy_y < player_y + player_height and
        enemy_x + enemy_width > player_x and
        enemy_x < player_x + player_width
    ):
        show_game_over()

    pygame.display.update()

pygame.quit()
