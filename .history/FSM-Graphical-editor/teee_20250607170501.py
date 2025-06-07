import pygame
import random
import os

# Constants\ nWIDTH = 480
HEIGHT = 600
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Initialize pygame and create window
pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Arcade Racer")
clock = pygame.time.Clock()

# Asset loading
def load_image(name):
    fullname = os.path.join('assets', name)
    try:
        image = pygame.image.load(fullname)
        return image.convert_alpha()
    except pygame.error as e:
        print(f"Cannot load image: {fullname}")
        raise SystemExit(e)

# Player car
class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = load_image('player_car.png')
        self.rect = self.image.get_rect()
        self.rect.centerx = WIDTH // 2
        self.rect.bottom = HEIGHT - 10
        self.speedx = 0

    def update(self):
        self.speedx = 0
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self.speedx = -5
        if keys[pygame.K_RIGHT]:
            self.speedx = 5
        self.rect.x += self.speedx
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > WIDTH:
            self.rect.right = WIDTH

# Obstacle cars
class Obstacle(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = load_image('obstacle_car.png')
        self.rect = self.image.get_rect()
        self.rect.x = random.randrange(0, WIDTH - self.rect.width)
        self.rect.y = random.randrange(-150, -100)
        self.speedy = random.randrange(5, 10)

    def update(self):
        self.rect.y += self.speedy
        # respawn off-screen
        if self.rect.top > HEIGHT:
            self.rect.x = random.randrange(0, WIDTH - self.rect.width)
            self.rect.y = random.randrange(-150, -100)
            self.speedy = random.randrange(5, 10)

# Main game loop
def main():
    running = True

    # Sprite groups
    all_sprites = pygame.sprite.Group()
    obstacles = pygame.sprite.Group()

    player = Player()
    all_sprites.add(player)

    for _ in range(5):
        obs = Obstacle()
        all_sprites.add(obs)
        obstacles.add(obs)

    score = 0
    font = pygame.font.Font(None, 36)

    while running:
        clock.tick(FPS)
        # Input events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Update
        all_sprites.update()
        # Check collisions
        hits = pygame.sprite.spritecollide(player, obstacles, False)
        if hits:
            running = False  # End game on collision

        # Draw / render
        screen.fill(GREEN)
        all_sprites.draw(screen)

        # Score display
        score += 1
        score_text = font.render(f"Score: {score}", True, WHITE)
        screen.blit(score_text, (10, 10))

        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    main()
