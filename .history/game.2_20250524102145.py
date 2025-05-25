import pygame
import math
import random
import numpy as np

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 1200, 800
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (135, 206, 235)  # Sky blue
GREEN = (34, 139, 34)   # Forest green
BROWN = (139, 69, 19)   # Brown
GRAY = (128, 128, 128)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)

class Aircraft:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y  # Height
        self.z = z
        self.vx = 0  # Velocity components
        self.vy = 0
        self.vz = 0
        self.pitch = 0    # Nose up/down
        self.yaw = 0      # Left/right turn
        self.roll = 0     # Banking
        self.thrust = 0   # Engine power
        self.max_thrust = 100
        self.mass = 1000
        self.drag_coefficient = 0.02
        self.lift_coefficient = 0.8
        self.crashed = False
        self.fuel = 100
        
    def update(self, dt):
        if self.crashed:
            return
            
        # Consume fuel
        if self.thrust > 0:
            self.fuel -= self.thrust * 0.001 * dt
            if self.fuel < 0:
                self.fuel = 0
                
        # Physics calculations
        # Thrust force
        thrust_force = self.thrust * (1 if self.fuel > 0 else 0)
        
        # Gravity
        gravity = -9.81 * self.mass
        
        # Drag force (opposing motion)
        speed = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        if speed > 0:
            drag_x = -self.drag_coefficient * speed * self.vx
            drag_y = -self.drag_coefficient * speed * self.vy
            drag_z = -self.drag_coefficient * speed * self.vz
        else:
            drag_x = drag_y = drag_z = 0
            
        # Lift force (perpendicular to motion, affected by pitch)
        lift_force = self.lift_coefficient * speed * math.sin(math.radians(self.pitch))
        
        # Calculate forces in world coordinates
        fx = thrust_force * math.cos(math.radians(self.yaw)) * math.cos(math.radians(self.pitch)) + drag_x
        fy = thrust_force * math.sin(math.radians(self.pitch)) + lift_force + gravity + drag_y
        fz = thrust_force * math.sin(math.radians(self.yaw)) * math.cos(math.radians(self.pitch)) + drag_z
        
        # Update velocities (F = ma)
        ax = fx / self.mass
        ay = fy / self.mass
        az = fz / self.mass
        
        self.vx += ax * dt
        self.vy += ay * dt
        self.vz += az * dt
        
        # Update positions
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        
        # Check for ground collision
        if self.y <= 0:
            if speed > 50:  # Crash if landing too fast
                self.crashed = True
            else:
                self.y = 0
                self.vy = 0
                
        # Keep aircraft in bounds
        self.x = max(-5000, min(5000, self.x))
        self.z = max(-5000, min(5000, self.z))
        
    def handle_input(self, keys):
        if self.crashed:
            return
            
        # Thrust control
        if keys[pygame.K_w]:
            self.thrust = min(self.max_thrust, self.thrust + 2)
        elif keys[pygame.K_s]:
            self.thrust = max(0, self.thrust - 2)
            
        # Pitch control (up/down)
        if keys[pygame.K_UP]:
            self.pitch = min(45, self.pitch + 1)
        elif keys[pygame.K_DOWN]:
            self.pitch = max(-45, self.pitch - 1)
        else:
            self.pitch *= 0.98  # Gradual return to level
            
        # Yaw control (left/right)
        if keys[pygame.K_LEFT]:
            self.yaw -= 2
        elif keys[pygame.K_RIGHT]:
            self.yaw += 2
            
        # Roll control
        if keys[pygame.K_a]:
            self.roll = max(-45, self.roll - 2)
        elif keys[pygame.K_d]:
            self.roll = min(45, self.roll + 2)
        else:
            self.roll *= 0.95  # Gradual return to level
            
        # Normalize yaw
        self.yaw = self.yaw % 360

class Terrain:
    def __init__(self):
        self.chunks = {}
        self.chunk_size = 100
        
    def get_height(self, x, z):
        # Simple terrain generation using sine waves
        return 50 * math.sin(x * 0.01) * math.cos(z * 0.01) + 100 * math.sin(x * 0.005) * math.sin(z * 0.005)
    
    def get_chunk(self, chunk_x, chunk_z):
        key = (chunk_x, chunk_z)
        if key not in self.chunks:
            # Generate terrain chunk
            points = []
            for i in range(0, self.chunk_size, 10):
                for j in range(0, self.chunk_size, 10):
                    world_x = chunk_x * self.chunk_size + i
                    world_z = chunk_z * self.chunk_size + j
                    height = self.get_height(world_x, world_z)
                    points.append((world_x, height, world_z))
            self.chunks[key] = points
        return self.chunks[key]

class FlightSimulator:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Flight Simulator")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        self.aircraft = Aircraft(0, 1000, 0)
        self.terrain = Terrain()
        self.camera_distance = 200
        self.camera_height = 50
        
        # Game state
        self.paused = False
        self.show_help = False
        
    def project_3d_to_2d(self, x, y, z, camera_x, camera_y, camera_z, yaw):
        # Translate to camera space
        dx = x - camera_x
        dy = y - camera_y
        dz = z - camera_z
        
        # Rotate around y-axis (yaw)
        cos_yaw = math.cos(math.radians(yaw))
        sin_yaw = math.sin(math.radians(yaw))
        
        rx = dx * cos_yaw - dz * sin_yaw
        ry = dy
        rz = dx * sin_yaw + dz * cos_yaw
        
        # Perspective projection
        if rz <= 0:
            return None
            
        focal_length = 400
        screen_x = WIDTH // 2 + (rx * focal_length) / rz
        screen_y = HEIGHT // 2 - (ry * focal_length) / rz
        
        return (int(screen_x), int(screen_y))
    
    def draw_aircraft(self, camera_x, camera_y, camera_z, camera_yaw):
        # Aircraft body points
        aircraft_points = [
            # Fuselage
            (0, 0, -20), (0, 0, 20),
            # Wings
            (-30, 0, 0), (30, 0, 0),
            # Tail
            (0, 10, -20), (0, -5, -20)
        ]
        
        projected_points = []
        for px, py, pz in aircraft_points:
            # Rotate points based on aircraft orientation
            cos_yaw = math.cos(math.radians(self.aircraft.yaw))
            sin_yaw = math.sin(math.radians(self.aircraft.yaw))
            cos_pitch = math.cos(math.radians(self.aircraft.pitch))
            sin_pitch = math.sin(math.radians(self.aircraft.pitch))
            cos_roll = math.cos(math.radians(self.aircraft.roll))
            sin_roll = math.sin(math.radians(self.aircraft.roll))
            
            # Apply rotations
            x1 = px * cos_yaw - pz * sin_yaw
            z1 = px * sin_yaw + pz * cos_yaw
            
            y2 = py * cos_pitch - z1 * sin_pitch
            z2 = py * sin_pitch + z1 * cos_pitch
            
            x3 = x1 * cos_roll - y2 * sin_roll
            y3 = x1 * sin_roll + y2 * cos_roll
            
            # Translate to world position
            world_x = self.aircraft.x + x3
            world_y = self.aircraft.y + y3
            world_z = self.aircraft.z + z2
            
            point = self.project_3d_to_2d(world_x, world_y, world_z, camera_x, camera_y, camera_z, camera_yaw)
            if point:
                projected_points.append(point)
        
        # Draw aircraft
        if len(projected_points) >= 4:
            # Draw fuselage
            pygame.draw.line(self.screen, WHITE, projected_points[0], projected_points[1], 3)
            # Draw wings
            pygame.draw.line(self.screen, WHITE, projected_points[2], projected_points[3], 3)
            # Draw tail lines
            if len(projected_points) >= 6:
                pygame.draw.line(self.screen, WHITE, projected_points[0], projected_points[4], 2)
                pygame.draw.line(self.screen, WHITE, projected_points[0], projected_points[5], 2)
    
    def draw_terrain(self, camera_x, camera_y, camera_z, camera_yaw):
        # Determine which terrain chunks to render
        chunk_x = int(camera_x // self.terrain.chunk_size)
        chunk_z = int(camera_z // self.terrain.chunk_size)
        
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                points = self.terrain.get_chunk(chunk_x + dx, chunk_z + dz)
                projected_points = []
                
                for x, y, z in points:
                    point = self.project_3d_to_2d(x, y, z, camera_x, camera_y, camera_z, camera_yaw)
                    if point and 0 <= point[0] <= WIDTH and 0 <= point[1] <= HEIGHT:
                        projected_points.append(point)
                
                # Draw terrain points
                for point in projected_points:
                    pygame.draw.circle(self.screen, GREEN, point, 2)
    
    def draw_hud(self):
        # Altitude
        alt_text = self.font.render(f"Altitude: {int(self.aircraft.y)}m", True, WHITE)
        self.screen.blit(alt_text, (10, 10))
        
        # Speed
        speed = math.sqrt(self.aircraft.vx**2 + self.aircraft.vy**2 + self.aircraft.vz**2)
        speed_text = self.font.render(f"Speed: {int(speed)} m/s", True, WHITE)
        self.screen.blit(speed_text, (10, 50))
        
        # Thrust
        thrust_text = self.font.render(f"Thrust: {int(self.aircraft.thrust)}%", True, WHITE)
        self.screen.blit(thrust_text, (10, 90))
        
        # Fuel
        fuel_color = RED if self.aircraft.fuel < 20 else WHITE
        fuel_text = self.font.render(f"Fuel: {int(self.aircraft.fuel)}%", True, fuel_color)
        self.screen.blit(fuel_text, (10, 130))
        
        # Attitude indicator
        pitch_text = self.font.render(f"Pitch: {int(self.aircraft.pitch)}°", True, WHITE)
        self.screen.blit(pitch_text, (WIDTH - 200, 10))
        
        yaw_text = self.font.render(f"Heading: {int(self.aircraft.yaw)}°", True, WHITE)
        self.screen.blit(yaw_text, (WIDTH - 200, 50))
        
        roll_text = self.font.render(f"Roll: {int(self.aircraft.roll)}°", True, WHITE)
        self.screen.blit(roll_text, (WIDTH - 200, 90))
        
        # Crash indicator
        if self.aircraft.crashed:
            crash_text = self.font.render("CRASHED! Press R to restart", True, RED)
            text_rect = crash_text.get_rect(center=(WIDTH//2, HEIGHT//2))
            self.screen.blit(crash_text, text_rect)
        
        # Controls help
        if self.show_help:
            help_lines = [
                "CONTROLS:",
                "W/S - Throttle Up/Down",
                "Arrow Keys - Pitch Up/Down",
                "A/D - Roll Left/Right",
                "Left/Right Arrows - Yaw",
                "H - Toggle Help",
                "P - Pause",
                "R - Restart (if crashed)"
            ]
            
            y_offset = HEIGHT // 2 - 100
            for line in help_lines:
                text = self.small_font.render(line, True, WHITE)
                self.screen.blit(text, (WIDTH // 2 - 100, y_offset))
                y_offset += 25
    
    def draw_horizon(self, camera_yaw, pitch, roll):
        # Simple artificial horizon
        center_x, center_y = WIDTH - 150, HEIGHT - 150
        radius = 80
        
        # Horizon line
        horizon_y = center_y + pitch * 2
        pygame.draw.line(self.screen, WHITE, 
                        (center_x - radius, horizon_y), 
                        (center_x + radius, horizon_y), 2)
        
        # Aircraft symbol
        pygame.draw.line(self.screen, YELLOW,
                        (center_x - 20, center_y),
                        (center_x + 20, center_y), 3)
        pygame.draw.line(self.screen, YELLOW,
                        (center_x, center_y - 10),
                        (center_x, center_y + 10), 3)
        
        # Circle border
        pygame.draw.circle(self.screen, WHITE, (center_x, center_y), radius, 2)
    
    def restart_game(self):
        self.aircraft = Aircraft(0, 1000, 0)
    
    def run(self):
        running = True
        
        while running:
            dt = self.clock.tick(FPS) / 1000.0  # Delta time in seconds
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_h:
                        self.show_help = not self.show_help
                    elif event.key == pygame.K_p:
                        self.paused = not self.paused
                    elif event.key == pygame.K_r and self.aircraft.crashed:
                        self.restart_game()
            
            if not self.paused:
                # Handle input
                keys = pygame.key.get_pressed()
                self.aircraft.handle_input(keys)
                
                # Update aircraft
                self.aircraft.update(dt)
            
            # Camera follows aircraft
            camera_x = self.aircraft.x - self.camera_distance * math.cos(math.radians(self.aircraft.yaw))
            camera_y = self.aircraft.y + self.camera_height
            camera_z = self.aircraft.z - self.camera_distance * math.sin(math.radians(self.aircraft.yaw))
            camera_yaw = self.aircraft.yaw
            
            # Clear screen with sky color
            self.screen.fill(BLUE)
            
            # Draw terrain
            self.draw_terrain(camera_x, camera_y, camera_z, camera_yaw)
            
            # Draw aircraft
            self.draw_aircraft(camera_x, camera_y, camera_z, camera_yaw)
            
            # Draw HUD
            self.draw_hud()
            
            # Draw artificial horizon
            self.draw_horizon(camera_yaw, self.aircraft.pitch, self.aircraft.roll)
            
            # Draw pause indicator
            if self.paused:
                pause_text = self.font.render("PAUSED", True, YELLOW)
                text_rect = pause_text.get_rect(center=(WIDTH//2, 50))
                self.screen.blit(pause_text, text_rect)
            
            pygame.display.flip()
        
        pygame.quit()

if __name__ == "__main__":
    game = FlightSimulator()
    game.run()