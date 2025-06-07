import asyncio
import platform
import pygame
import random

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 600
FPS = 60
CAR_WIDTH, CAR_HEIGHT = 50, 100
OBSTACLE_WIDTH, OBSTACLE_HEIGHT = 50, 100
ROAD_WIDTH = 300

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (50, 50, 50)
RED = (255, 0, 0)

# Setup
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Car Racing Game")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 35)

# Game variables
car_x = WIDTH // 2 - CAR_WIDTH // 2
car_y = HEIGHT - CAR_HEIGHT - 10
car_speed = 5
move_left = False
move_right = False

road_x = (WIDTH - ROAD_WIDTH) // 2
road_marking_y = 0
road_speed = 5

obstacles = []
obstacle_speed = 5
obstacle_timer = 0

score = 0
running = True

def draw_car(x, y):
    pygame.draw.rect(screen, BLACK, (x, y, CAR_WIDTH, CAR_HEIGHT))

def draw_road():
    pygame.draw.rect(screen, GRAY, (road_x, 0, ROAD_WIDTH, HEIGHT))
    for i in range(0, HEIGHT, 40):
        pygame.draw.rect(screen, WHITE, (WIDTH // 2 - 5, (i + road_marking_y) % HEIGHT, 10, 20))

def create_obstacle():
    x = random.randint(road_x, road_x + ROAD_WIDTH - OBSTACLE_WIDTH)
    obstacles.append([x, -OBSTACLE_HEIGHT])

def draw_obstacles():
    for obs in obstacles:
        pygame.draw.rect(screen, RED, (obs[0], obs[1], OBSTACLE_WIDTH, OBSTACLE_HEIGHT))

def check_collision():
    for obs in obstacles:
        if (car_x < obs[0] + OBSTACLE_WIDTH and
            car_x + CAR_WIDTH > obs[0] and
            car_y < obs[1] + OBSTACLE_HEIGHT and
            car_y + CAR_HEIGHT > obs[1]):
            return True
    return False

def display_score():
    score_text = font.render(f"Score: {score}", True, BLACK)
    screen.blit(score_text, (10, 10))

def setup():
    global running
    running = True

async def update_loop():
    global car_x, road_marking_y, obstacle_timer, score, running
    screen.fill(WHITE)

    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                globals()['move_left'] = True
            if event.key == pygame.K_RIGHT:
                globals()['move_right'] = True
        if event.type == pygame.KEYUP:
            if event.key == pygame.K_LEFT:
                globals()['move_left'] = False
            if event.key == pygame.K_RIGHT:
                globals()['move_right'] = False

    # Move car
    if move_left and car_x > road_x:
        car_x -= car_speed
    if move_right and car_x < road_x + ROAD_WIDTH - CAR_WIDTH:
        car_x += car_speed

    # Update road
    road_marking_y += road_speed
    if road_marking_y > HEIGHT:
        road_marking_y = 0

    # Generate obstacles
    obstacle_timer += 1
    if obstacle_timer > 50:
        create_obstacle()
        obstacle_timer = 0

    # Move obstacles
    for obs in obstacles:
        obs[1] += obstacle_speed
    obstacles[:] = [obs for obs in obstacles if obs[1] < HEIGHT]

    # Check collision
    if check_collision():
        running = False
        game_over_text = font.render(f"Game Over! Score: {score}", True, BLACK)
        screen.blit(game_over_text, (WIDTH // 2 - 100, HEIGHT // 2))

    # Update score
    score += 1

    # Draw everything
    draw_road()
    draw_car(car_x, car_y)
    draw_obstacles()
    display_score()

    pygame.display.flip()

async def main():
    setup()
    while running:
        await update_loop()
        await asyncio.sleep(1.0 / FPS)

if platform.system() == "Emscripten":
    asyncio.ensure_future(main())
else:
    if __name__ == "__main__":
        asyncio.run(main())