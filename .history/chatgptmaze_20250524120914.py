import pygame
import sys

# Initialize Pygame
pygame.init()

# Screen dimensions
WIDTH, HEIGHT = 600, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Maze Game")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (50, 50, 255)
GREEN = (0, 255, 0)

# Player settings
player_size = 20
player_pos = [40, 40]
player_speed = 5

# Goal settings
goal_size = 20
goal_pos = [560, 560]

# Maze walls (x, y, width, height)
walls = [
    pygame.Rect(0, 0, 600, 20),
    pygame.Rect(0, 0, 20, 600),
    pygame.Rect(0, 580, 600, 20),
    pygame.Rect(580, 0, 20, 600),
    pygame.Rect(100, 20, 20, 500),
    pygame.Rect(200, 100, 20, 500),
    pygame.Rect(300, 20, 20, 500),
    pygame.Rect(400, 100, 20, 500),
    pygame.Rect(500, 20, 20, 500),
]

# Clock
clock = pygame.time.Clock()

# Main game loop
running = True
while running:
    screen.fill(WHITE)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    keys = pygame.key.get_pressed()
    old_pos = list(player_pos)

    if keys[pygame.K_LEFT]:
        player_pos[0] -= player_speed
    if keys[pygame.K_RIGHT]:
        player_pos[0] += player_speed
    if keys[pygame.K_UP]:
        player_pos[1] -= player_speed
    if keys[pygame.K_DOWN]:
        player_pos[1] += player_speed

    player_rect = pygame.Rect(player_pos[0], player_pos[1], player_size, player_size)

    for wall in walls:
        if player_rect.colliderect(wall):
            player_pos = old_pos
            break

    goal_rect = pygame.Rect(goal_pos[0], goal_pos[1], goal_size, goal_size)
    if player_rect.colliderect(goal_rect):
        print("You Win!")
        pygame.quit()
        sys.exit()

    # Draw walls
    for wall in walls:
        pygame.draw.rect(screen, BLACK, wall)

    # Draw goal
    pygame.draw.rect(screen, GREEN, goal_rect)

    # Draw player
    pygame.draw.rect(screen, BLUE, player_rect)

    pygame.display.update()
    clock.tick(30)
