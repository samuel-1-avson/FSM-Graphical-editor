import pygame
import random
import math
import sys

# Initialize Pygame
pygame.init()

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)

class Car:
    def __init__(self, x, y, color=RED):
        self.x = x
        self.y = y
        self.width = 30
        self.height = 50
        self.color = color
        self.speed = 0
        self.max_speed = 8
        self.acceleration = 0.2
        self.friction = 0.1
        self.angle = 0
        self.turn_speed = 3
        
    def update(self, keys):
        # Handle input
        if keys[pygame.K_UP]:
            self.speed = min(self.speed + self.acceleration, self.max_speed)
        elif keys[pygame.K_DOWN]:
            self.speed = max(self.speed - self.acceleration, -self.max_speed/2)
        else:
            # Apply friction
            if self.speed > 0:
                self.speed = max(0, self.speed - self.friction)
            elif self.speed < 0:
                self.speed = min(0, self.speed + self.friction)
        
        # Handle turning (only when moving)
        if abs(self.speed) > 0.1:
            if keys[pygame.K_LEFT]:
                self.angle -= self.turn_speed
            if keys[pygame.K_RIGHT]:
                self.angle += self.turn_speed
        
        # Update position based on angle and speed
        self.x += math.cos(math.radians(self.angle)) * self.speed
        self.y += math.sin(math.radians(self.angle)) * self.speed
        
        # Keep car on screen
        self.x = max(0, min(SCREEN_WIDTH - self.width, self.x))
        self.y = max(0, min(SCREEN_HEIGHT - self.height, self.y))
    
    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)
    
    def draw(self, screen):
        # Create car surface
        car_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.rect(car_surface, self.color, (0, 0, self.width, self.height))
        pygame.draw.rect(car_surface, BLACK, (0, 0, self.width, self.height), 2)
        
        # Add details
        pygame.draw.rect(car_surface, WHITE, (5, 5, 20, 10))  # Windshield
        pygame.draw.rect(car_surface, WHITE, (5, 35, 20, 10))  # Rear window
        
        # Rotate the car
        rotated_car = pygame.transform.rotate(car_surface, -self.angle)
        rect = rotated_car.get_rect(center=(self.x + self.width//2, self.y + self.height//2))
        screen.blit(rotated_car, rect)

class Obstacle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 40
        self.height = 40
        self.speed = random.uniform(1, 3)
        self.color = random.choice([BLUE, GREEN, YELLOW])
    
    def update(self):
        self.y += self.speed
    
    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)
    
    def draw(self, screen):
        pygame.draw.rect(screen, self.color, (self.x, self.y, self.width, self.height))
        pygame.draw.rect(screen, BLACK, (self.x, self.y, self.width, self.height), 2)

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Car Racing Arcade Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        self.player = Car(SCREEN_WIDTH//2, SCREEN_HEIGHT - 100)
        self.obstacles = []
        self.score = 0
        self.game_over = False
        self.obstacle_spawn_timer = 0
        self.spawn_rate = 120  # frames between spawns
        
    def spawn_obstacle(self):
        x = random.randint(0, SCREEN_WIDTH - 40)
        self.obstacles.append(Obstacle(x, -40))
    
    def check_collisions(self):
        player_rect = self.player.get_rect()
        for obstacle in self.obstacles:
            if player_rect.colliderect(obstacle.get_rect()):
                self.game_over = True
                break
    
    def update(self):
        if not self.game_over:
            keys = pygame.key.get_pressed()
            self.player.update(keys)
            
            # Update obstacles
            for obstacle in self.obstacles[:]:
                obstacle.update()
                if obstacle.y > SCREEN_HEIGHT:
                    self.obstacles.remove(obstacle)
                    self.score += 10
            
            # Spawn new obstacles
            self.obstacle_spawn_timer += 1
            if self.obstacle_spawn_timer >= self.spawn_rate:
                self.spawn_obstacle()
                self.obstacle_spawn_timer = 0
                # Increase difficulty over time
                self.spawn_rate = max(30, self.spawn_rate - 1)
            
            self.check_collisions()
    
    def draw(self):
        self.screen.fill(GRAY)
        
        # Draw road markings
        for y in range(0, SCREEN_HEIGHT, 40):
            pygame.draw.rect(self.screen, WHITE, (SCREEN_WIDTH//2 - 2, y, 4, 20))
        
        # Draw road edges
        pygame.draw.rect(self.screen, DARK_GRAY, (0, 0, 20, SCREEN_HEIGHT))
        pygame.draw.rect(self.screen, DARK_GRAY, (SCREEN_WIDTH - 20, 0, 20, SCREEN_HEIGHT))
        
        # Draw game objects
        self.player.draw(self.screen)
        for obstacle in self.obstacles:
            obstacle.draw(self.screen)
        
        # Draw UI
        score_text = self.font.render(f"Score: {self.score}", True, BLACK)
        self.screen.blit(score_text, (10, 10))
        
        speed_text = self.small_font.render(f"Speed: {abs(self.player.speed):.1f}", True, BLACK)
        self.screen.blit(speed_text, (10, 50))
        
        if self.game_over:
            game_over_text = self.font.render("GAME OVER!", True, RED)
            restart_text = self.small_font.render("Press R to restart or ESC to quit", True, BLACK)
            
            game_over_rect = game_over_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
            restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 40))
            
            self.screen.blit(game_over_text, game_over_rect)
            self.screen.blit(restart_text, restart_rect)
        
        # Draw instructions
        if self.score == 0 and not self.game_over:
            instructions = [
                "Use ARROW KEYS to control your car",
                "UP/DOWN: Accelerate/Brake",
                "LEFT/RIGHT: Steer",
                "Avoid the obstacles!"
            ]
            for i, instruction in enumerate(instructions):
                text = self.small_font.render(instruction, True, BLACK)
                self.screen.blit(text, (SCREEN_WIDTH - 250, 10 + i * 25))
        
        pygame.display.flip()
    
    def restart(self):
        self.player = Car(SCREEN_WIDTH//2, SCREEN_HEIGHT - 100)
        self.obstacles = []
        self.score = 0
        self.game_over = False
        self.obstacle_spawn_timer = 0
        self.spawn_rate = 120
    
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r and self.game_over:
                        self.restart()
            
            self.update()
            self.draw()
            self.clock.tick(FPS)
        
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    # Check if pygame is available
    try:
        game = Game()
        game.run()
    except pygame.error as e:
        print(f"Pygame error: {e}")
        print("Make sure pygame is installed: pip install pygame")
    except ImportError:
        print("Pygame not found. Install it with: pip install pygame")