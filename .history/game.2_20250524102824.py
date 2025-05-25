import pygame
import math
import random
import numpy as np
import json
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 1400, 900
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (135, 206, 235)
DARK_BLUE = (25, 25, 112)
GREEN = (34, 139, 34)
DARK_GREEN = (0, 100, 0)
BROWN = (139, 69, 19)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)
CYAN = (0, 255, 255)
LIGHT_GRAY = (192, 192, 192)

class WeatherType(Enum):
    CLEAR = "Clear"
    CLOUDY = "Cloudy"
    RAIN = "Rain"
    STORM = "Storm"
    FOG = "Fog"
    SNOW = "Snow"

class AircraftType(Enum):
    FIGHTER = "Fighter"
    AIRLINER = "Airliner"
    GLIDER = "Glider"
    HELICOPTER = "Helicopter"

@dataclass
class AircraftConfig:
    name: str
    max_thrust: float
    mass: float
    drag_coefficient: float
    lift_coefficient: float
    max_speed: float
    fuel_capacity: float
    fuel_consumption: float
    max_altitude: float
    turn_rate: float
    stall_speed: float

@dataclass
class Waypoint:
    x: float
    z: float
    altitude: float
    name: str
    waypoint_type: str = "NAV"  # NAV, AIRPORT, VOR, etc.

class Weather:
    def __init__(self):
        self.type = WeatherType.CLEAR
        self.wind_speed = 0
        self.wind_direction = 0
        self.visibility = 10000  # meters
        self.cloud_ceiling = 10000  # meters
        self.temperature = 15  # celsius
        self.pressure = 1013.25  # hPa
        self.turbulence = 0  # 0-10 scale
        self.precipitation = 0  # 0-10 scale
        
    def update(self, dt):
        # Dynamic weather changes
        if random.random() < 0.001:  # 0.1% chance per frame to change weather
            self.type = random.choice(list(WeatherType))
            self.update_conditions()
    
    def update_conditions(self):
        if self.type == WeatherType.CLEAR:
            self.visibility = 15000
            self.wind_speed = random.uniform(0, 10)
            self.turbulence = random.uniform(0, 2)
            self.precipitation = 0
        elif self.type == WeatherType.CLOUDY:
            self.visibility = 8000
            self.wind_speed = random.uniform(5, 15)
            self.cloud_ceiling = random.uniform(1000, 3000)
            self.turbulence = random.uniform(1, 4)
        elif self.type == WeatherType.RAIN:
            self.visibility = 3000
            self.wind_speed = random.uniform(10, 25)
            self.turbulence = random.uniform(3, 6)
            self.precipitation = random.uniform(3, 7)
        elif self.type == WeatherType.STORM:
            self.visibility = 1000
            self.wind_speed = random.uniform(20, 40)
            self.turbulence = random.uniform(6, 10)
            self.precipitation = random.uniform(7, 10)
        elif self.type == WeatherType.FOG:
            self.visibility = 500
            self.wind_speed = random.uniform(0, 5)
            self.turbulence = random.uniform(0, 2)
        elif self.type == WeatherType.SNOW:
            self.visibility = 2000
            self.wind_speed = random.uniform(5, 20)
            self.turbulence = random.uniform(2, 5)
            self.precipitation = random.uniform(2, 6)
            self.temperature = random.uniform(-10, 2)
        
        self.wind_direction = random.uniform(0, 360)

class Aircraft:
    def __init__(self, x, y, z, aircraft_type: AircraftType):
        self.x = x
        self.y = y
        self.z = z
        self.vx = 0
        self.vy = 0
        self.vz = 0
        self.pitch = 0
        self.yaw = 0
        self.roll = 0
        self.thrust = 0
        self.crashed = False
        self.on_ground = False
        self.gear_down = True
        self.flaps = 0  # 0-40 degrees
        self.autopilot = False
        self.target_altitude = 0
        self.target_heading = 0
        self.engine_on = True
        
        # Aircraft-specific configuration
        self.configs = {
            AircraftType.FIGHTER: AircraftConfig(
                "F-16 Fighter", 150, 8000, 0.025, 1.2, 600, 100, 0.15, 15000, 5, 80
            ),
            AircraftType.AIRLINER: AircraftConfig(
                "Boeing 737", 100, 70000, 0.02, 0.9, 250, 200, 0.08, 12000, 2, 120
            ),
            AircraftType.GLIDER: AircraftConfig(
                "ASK-21 Glider", 0, 800, 0.015, 1.5, 100, 0, 0, 8000, 3, 50
            ),
            AircraftType.HELICOPTER: AircraftConfig(
                "UH-60 Blackhawk", 80, 5000, 0.04, 0.6, 80, 150, 0.12, 6000, 8, 0
            )
        }
        
        self.type = aircraft_type
        self.config = self.configs[aircraft_type]
        self.fuel = self.config.fuel_capacity
        self.max_thrust = self.config.max_thrust
        self.mass = self.config.mass
        
        # Navigation
        self.waypoints: List[Waypoint] = []
        self.current_waypoint = 0
        self.nav_mode = False
        
        # Systems
        self.electrical = True
        self.hydraulics = True
        self.engine_health = 100
        self.structural_integrity = 100
        
        # Flight envelope protection
        self.max_g_force = 9.0 if aircraft_type == AircraftType.FIGHTER else 2.5
        self.current_g_force = 1.0
        
    def add_waypoint(self, waypoint: Waypoint):
        self.waypoints.append(waypoint)
    
    def navigate_to_waypoint(self):
        if not self.waypoints or self.current_waypoint >= len(self.waypoints):
            return
            
        wp = self.waypoints[self.current_waypoint]
        
        # Calculate bearing to waypoint
        dx = wp.x - self.x
        dz = wp.z - self.z
        bearing = math.degrees(math.atan2(dz, dx))
        
        # Distance to waypoint
        distance = math.sqrt(dx**2 + dz**2)
        
        # Auto-navigation if enabled
        if self.nav_mode and distance > 100:
            # Adjust heading towards waypoint
            heading_diff = bearing - self.yaw
            while heading_diff > 180:
                heading_diff -= 360
            while heading_diff < -180:
                heading_diff += 360
                
            if abs(heading_diff) > 5:
                self.yaw += 2 if heading_diff > 0 else -2
        
        # Check if reached waypoint
        if distance < 200:
            self.current_waypoint += 1
    
    def update_autopilot(self):
        if not self.autopilot:
            return
            
        # Altitude hold
        altitude_error = self.target_altitude - self.y
        if abs(altitude_error) > 50:
            pitch_adjustment = max(-10, min(10, altitude_error * 0.02))
            self.pitch = max(-30, min(30, pitch_adjustment))
        
        # Heading hold
        heading_error = self.target_heading - self.yaw
        while heading_error > 180:
            heading_error -= 360
        while heading_error < -180:
            heading_error += 360
            
        if abs(heading_error) > 5:
            self.yaw += 2 if heading_error > 0 else -2
    
    def update(self, dt, weather: Weather):
        if self.crashed:
            return
            
        # Update autopilot
        self.update_autopilot()
        
        # Navigate to waypoints
        self.navigate_to_waypoint()
        
        # Fuel consumption
        if self.thrust > 0 and self.engine_on:
            consumption = self.config.fuel_consumption * (self.thrust / 100) * dt
            self.fuel = max(0, self.fuel - consumption)
        
        # Engine failure if no fuel
        if self.fuel <= 0:
            self.engine_on = False
            self.thrust = 0
        
        # Weather effects
        wind_effect_x = weather.wind_speed * math.cos(math.radians(weather.wind_direction)) * 0.1
        wind_effect_z = weather.wind_speed * math.sin(math.radians(weather.wind_direction)) * 0.1
        
        # Turbulence
        if weather.turbulence > 0:
            turbulence_pitch = random.uniform(-weather.turbulence, weather.turbulence) * 0.5
            turbulence_roll = random.uniform(-weather.turbulence, weather.turbulence) * 0.5
            self.pitch += turbulence_pitch
            self.roll += turbulence_roll
        
        # Physics calculations
        thrust_force = self.thrust * (1 if self.engine_on else 0) * (0.8 if not self.electrical else 1.0)
        
        # Gravity
        gravity = -9.81 * self.mass
        
        # Speed calculation
        speed = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        
        # Stall check
        if speed < self.config.stall_speed and self.y > 10:
            self.pitch -= 5  # Nose drops in stall
            thrust_force *= 0.5  # Reduced control authority
        
        # Drag force
        drag_multiplier = 1.0 + (self.flaps / 40.0) * 0.5  # Flaps increase drag
        if speed > 0:
            drag_x = -self.config.drag_coefficient * speed * self.vx * drag_multiplier
            drag_y = -self.config.drag_coefficient * speed * self.vy * drag_multiplier
            drag_z = -self.config.drag_coefficient * speed * self.vz * drag_multiplier
        else:
            drag_x = drag_y = drag_z = 0
        
        # Lift force
        lift_multiplier = 1.0 + (self.flaps / 40.0) * 0.3  # Flaps increase lift
        lift_force = self.config.lift_coefficient * speed * math.sin(math.radians(self.pitch)) * lift_multiplier
        
        # Calculate forces
        cos_yaw = math.cos(math.radians(self.yaw))
        sin_yaw = math.sin(math.radians(self.yaw))
        cos_pitch = math.cos(math.radians(self.pitch))
        sin_pitch = math.sin(math.radians(self.pitch))
        
        fx = thrust_force * cos_yaw * cos_pitch + drag_x + wind_effect_x
        fy = thrust_force * sin_pitch + lift_force + gravity + drag_y
        fz = thrust_force * sin_yaw * cos_pitch + drag_z + wind_effect_z
        
        # Update velocities
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
        
        # Ground collision
        if self.y <= 0:
            self.on_ground = True
            if speed > 100 or abs(self.pitch) > 15:  # Hard landing
                self.crashed = True
                self.structural_integrity = 0
            else:
                self.y = 0
                self.vy = 0
                if speed < 5:
                    self.vx *= 0.8  # Ground friction
                    self.vz *= 0.8
        else:
            self.on_ground = False
        
        # Calculate G-force
        if speed > 0:
            centripetal_accel = (self.vx * ax + self.vy * ay + self.vz * az) / speed
            self.current_g_force = abs(centripetal_accel / 9.81) + 1
            
            # G-force damage
            if self.current_g_force > self.max_g_force:
                self.structural_integrity -= (self.current_g_force - self.max_g_force) * 10 * dt
        
        # System failures
        if self.structural_integrity <= 0:
            self.crashed = True
        
        # Bounds checking
        self.x = max(-10000, min(10000, self.x))
        self.z = max(-10000, min(10000, self.z))
        self.y = max(0, min(self.config.max_altitude, self.y))
        
        # Normalize angles
        self.yaw = self.yaw % 360
        self.pitch = max(-90, min(90, self.pitch))
        self.roll = max(-90, min(90, self.roll))
    
    def handle_input(self, keys):
        if self.crashed:
            return
            
        # Engine control
        if keys[pygame.K_e]:
            self.engine_on = not self.engine_on
            
        # Thrust control
        if keys[pygame.K_w]:
            self.thrust = min(self.max_thrust, self.thrust + 3)
        elif keys[pygame.K_s]:
            self.thrust = max(0, self.thrust - 3)
            
        # Pitch control
        if keys[pygame.K_UP]:
            self.pitch = min(45, self.pitch + 2)
        elif keys[pygame.K_DOWN]:
            self.pitch = max(-45, self.pitch - 2)
        else:
            self.pitch *= 0.95
            
        # Yaw control
        if keys[pygame.K_LEFT]:
            self.yaw -= self.config.turn_rate
        elif keys[pygame.K_RIGHT]:
            self.yaw += self.config.turn_rate
            
        # Roll control
        if keys[pygame.K_a]:
            self.roll = max(-60, self.roll - 3)
        elif keys[pygame.K_d]:
            self.roll = min(60, self.roll + 3)
        else:
            self.roll *= 0.9
            
        # Flaps control
        if keys[pygame.K_f]:
            self.flaps = min(40, self.flaps + 1)
        elif keys[pygame.K_g]:
            self.flaps = max(0, self.flaps - 1)
            
        # Landing gear
        if keys[pygame.K_l]:
            self.gear_down = not self.gear_down
            
        # Autopilot
        if keys[pygame.K_p]:
            self.autopilot = not self.autopilot
            if self.autopilot:
                self.target_altitude = self.y
                self.target_heading = self.yaw
                
        # Navigation mode
        if keys[pygame.K_n]:
            self.nav_mode = not self.nav_mode

class Terrain:
    def __init__(self):
        self.chunks = {}
        self.chunk_size = 200
        self.airports = [
            Waypoint(0, 0, 0, "Main Airport", "AIRPORT"),
            Waypoint(3000, 2000, 0, "City Airport", "AIRPORT"),
            Waypoint(-2000, 3000, 0, "Mountain Airport", "AIRPORT"),
        ]
        
    def get_height(self, x, z):
        # More complex terrain with mountains, valleys, and flat areas
        base_height = 100 * math.sin(x * 0.001) * math.cos(z * 0.001)
        mountains = 300 * math.sin(x * 0.0005) * math.sin(z * 0.0005)
        hills = 50 * math.sin(x * 0.005) * math.cos(z * 0.005)
        
        # Flatten around airports
        for airport in self.airports:
            dist = math.sqrt((x - airport.x)**2 + (z - airport.z)**2)
            if dist < 500:
                flatten_factor = max(0, 1 - dist / 500)
                return base_height * (1 - flatten_factor)
        
        return base_height + mountains + hills
    
    def get_chunk(self, chunk_x, chunk_z):
        key = (chunk_x, chunk_z)
        if key not in self.chunks:
            points = []
            for i in range(0, self.chunk_size, 20):
                for j in range(0, self.chunk_size, 20):
                    world_x = chunk_x * self.chunk_size + i
                    world_z = chunk_z * self.chunk_size + j
                    height = self.get_height(world_x, world_z)
                    points.append((world_x, height, world_z))
            self.chunks[key] = points
        return self.chunks[key]

class FlightSimulator:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Advanced Flight Simulator")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 20)
        self.large_font = pygame.font.Font(None, 48)
        
        # Game state
        self.aircraft_type = AircraftType.FIGHTER
        self.aircraft = Aircraft(0, 1000, 0, self.aircraft_type)
        self.terrain = Terrain()
        self.weather = Weather()
        
        # Camera
        self.camera_distance = 300
        self.camera_height = 100
        self.camera_mode = 0  # 0: follow, 1: cockpit, 2: free
        
        # UI state
        self.paused = False
        self.show_help = False
        self.show_weather = False
        self.show_navigation = False
        self.hud_mode = 0  # Different HUD layouts
        
        # Time
        self.game_time = 0
        self.time_scale = 1.0
        
        # Setup waypoints
        self.setup_navigation()
        
        # Particle systems for effects
        self.particles = []
        
    def setup_navigation(self):
        """Setup navigation waypoints"""
        nav_points = [
            Waypoint(1000, 500, 1000, "Alpha", "NAV"),
            Waypoint(2000, 1500, 1200, "Bravo", "NAV"),
            Waypoint(500, 2000, 800, "Charlie", "NAV"),
            Waypoint(-1000, 1000, 1500, "Delta", "NAV"),
        ]
        
        for wp in nav_points + self.terrain.airports:
            self.aircraft.add_waypoint(wp)
    
    def create_particle_effect(self, x, y, z, effect_type="exhaust"):
        """Create particle effects for engine exhaust, etc."""
        if effect_type == "exhaust" and self.aircraft.thrust > 0:
            for _ in range(int(self.aircraft.thrust / 20)):
                particle = {
                    'x': x - random.uniform(5, 15),
                    'y': y + random.uniform(-2, 2),
                    'z': z - random.uniform(5, 15),
                    'vx': random.uniform(-10, -5),
                    'vy': random.uniform(-2, 2),
                    'vz': random.uniform(-2, 2),
                    'life': random.uniform(0.5, 1.5),
                    'max_life': random.uniform(0.5, 1.5),
                    'type': 'exhaust'
                }
                self.particles.append(particle)
    
    def update_particles(self, dt):
        """Update particle system"""
        for particle in self.particles[:]:
            particle['x'] += particle['vx'] * dt
            particle['y'] += particle['vy'] * dt
            particle['z'] += particle['vz'] * dt
            particle['life'] -= dt
            
            if particle['life'] <= 0:
                self.particles.remove(particle)
    
    def project_3d_to_2d(self, x, y, z, camera_x, camera_y, camera_z, yaw, pitch=0):
        # Enhanced 3D projection with pitch
        dx = x - camera_x
        dy = y - camera_y
        dz = z - camera_z
        
        # Rotate around y-axis (yaw)
        cos_yaw = math.cos(math.radians(yaw))
        sin_yaw = math.sin(math.radians(yaw))
        
        rx = dx * cos_yaw - dz * sin_yaw
        ry = dy
        rz = dx * sin_yaw + dz * cos_yaw
        
        # Rotate around x-axis (pitch)
        cos_pitch = math.cos(math.radians(pitch))
        sin_pitch = math.sin(math.radians(pitch))
        
        ry2 = ry * cos_pitch - rz * sin_pitch
        rz2 = ry * sin_pitch + rz * cos_pitch
        
        if rz2 <= 1:
            return None
            
        focal_length = 600
        screen_x = WIDTH // 2 + (rx * focal_length) / rz2
        screen_y = HEIGHT // 2 - (ry2 * focal_length) / rz2
        
        return (int(screen_x), int(screen_y))
    
    def draw_aircraft(self, camera_x, camera_y, camera_z, camera_yaw, camera_pitch):
        # More detailed aircraft model
        if self.aircraft.type == AircraftType.FIGHTER:
            aircraft_points = [
                # Fuselage
                (0, 0, -25), (0, 0, 25), (0, 2, 10), (0, -2, -20),
                # Wings
                (-40, 0, 5), (40, 0, 5), (-30, 0, -5), (30, 0, -5),
                # Tail
                (0, 15, -25), (0, -10, -25), (-8, 8, -20), (8, 8, -20)
            ]
        elif self.aircraft.type == AircraftType.AIRLINER:
            aircraft_points = [
                # Fuselage
                (0, 0, -40), (0, 0, 40), (0, 5, 20), (0, -5, -30),
                # Wings
                (-60, 0, 0), (60, 0, 0), (-50, 0, -10), (50, 0, -10),
                # Tail
                (0, 20, -40), (0, -10, -40), (-15, 15, -35), (15, 15, -35)
            ]
        else:  # Default model
            aircraft_points = [
                (0, 0, -20), (0, 0, 20), (-30, 0, 0), (30, 0, 0),
                (0, 10, -20), (0, -5, -20)
            ]
        
        projected_points = []
        for px, py, pz in aircraft_points:
            # Apply aircraft rotations
            cos_yaw = math.cos(math.radians(self.aircraft.yaw))
            sin_yaw = math.sin(math.radians(self.aircraft.yaw))
            cos_pitch = math.cos(math.radians(self.aircraft.pitch))
            sin_pitch = math.sin(math.radians(self.aircraft.pitch))
            cos_roll = math.cos(math.radians(self.aircraft.roll))
            sin_roll = math.sin(math.radians(self.aircraft.roll))
            
            # Yaw rotation
            x1 = px * cos_yaw - pz * sin_yaw
            z1 = px * sin_yaw + pz * cos_yaw
            
            # Pitch rotation
            y2 = py * cos_pitch - z1 * sin_pitch
            z2 = py * sin_pitch + z1 * cos_pitch
            
            # Roll rotation
            x3 = x1 * cos_roll - y2 * sin_roll
            y3 = x1 * sin_roll + y2 * cos_roll
            
            world_x = self.aircraft.x + x3
            world_y = self.aircraft.y + y3
            world_z = self.aircraft.z + z2
            
            point = self.project_3d_to_2d(world_x, world_y, world_z, 
                                        camera_x, camera_y, camera_z, 
                                        camera_yaw, camera_pitch)
            if point:
                projected_points.append(point)
        
        # Draw aircraft with different colors based on type
        color = WHITE
        if self.aircraft.type == AircraftType.FIGHTER:
            color = GRAY
        elif self.aircraft.type == AircraftType.AIRLINER:
            color = WHITE
        elif self.aircraft.type == AircraftType.HELICOPTER:
            color = DARK_GRAY
        
        # Draw aircraft lines
        if len(projected_points) >= 4:
            pygame.draw.lines(self.screen, color, False, projected_points[:4], 2)
            if len(projected_points) >= 8:
                pygame.draw.lines(self.screen, color, False, projected_points[4:8], 2)
            if len(projected_points) >= 12:
                pygame.draw.lines(self.screen, color, False, projected_points[8:12], 2)
    
    def draw_particles(self, camera_x, camera_y, camera_z, camera_yaw, camera_pitch):
        """Draw particle effects"""
        for particle in self.particles:
            point = self.project_3d_to_2d(particle['x'], particle['y'], particle['z'],
                                        camera_x, camera_y, camera_z, camera_yaw, camera_pitch)
            if point:
                alpha = int(255 * (particle['life'] / particle['max_life']))
                color = (255, 100, 0) if particle['type'] == 'exhaust' else WHITE
                # Create a temporary surface for alpha blending
                surf = pygame.Surface((4, 4))
                surf.set_alpha(alpha)
                surf.fill(color)
                self.screen.blit(surf, (point[0]-2, point[1]-2))
    
    def draw_terrain(self, camera_x, camera_y, camera_z, camera_yaw, camera_pitch):
        chunk_x = int(camera_x // self.terrain.chunk_size)
        chunk_z = int(camera_z // self.terrain.chunk_size)
        
        for dx in range(-3, 4):
            for dz in range(-3, 4):
                points = self.terrain.get_chunk(chunk_x + dx, chunk_z + dz)
                projected_points = []
                
                for x, y, z in points:
                    point = self.project_3d_to_2d(x, y, z, camera_x, camera_y, camera_z, 
                                                camera_yaw, camera_pitch)
                    if point and -100 <= point[0] <= WIDTH+100 and -100 <= point[1] <= HEIGHT+100:
                        projected_points.append((point, y))
                
                # Draw terrain with height-based coloring
                for (point, height) in projected_points:
                    if height < 50:
                        color = GREEN
                    elif height < 200:
                        color = DARK_GREEN
                    elif height < 400:
                        color = BROWN
                    else:
                        color = WHITE  # Snow-capped peaks
                    
                    pygame.draw.circle(self.screen, color, point, 2)
    
    def draw_waypoints(self, camera_x, camera_y, camera_z, camera_yaw, camera_pitch):
        """Draw navigation waypoints"""
        for i, wp in enumerate(self.aircraft.waypoints):
            point = self.project_3d_to_2d(wp.x, wp.altitude, wp.z, 
                                        camera_x, camera_y, camera_z, 
                                        camera_yaw, camera_pitch)
            if point:
                color = YELLOW if i == self.aircraft.current_waypoint else CYAN
                if wp.waypoint_type == "AIRPORT":
                    color = GREEN
                
                pygame.draw.circle(self.screen, color, point, 8)
                
                # Draw waypoint name
                text = self.small_font.render(wp.name, True, color)
                self.screen.blit(text, (point[0] + 10, point[1] - 10))
    
    def draw_weather_effects(self):
        """Draw weather visual effects"""
        if self.weather.type == WeatherType.RAIN or self.weather.type == WeatherType.STORM:
            for _ in range(int(self.weather.precipitation * 20)):
                x = random.randint(0, WIDTH)
                y = random.randint(0, HEIGHT)
                pygame.draw.line(self.screen, LIGHT_GRAY, (x, y), (x-2, y+10), 1)
        
        elif self.weather.type == WeatherType.SNOW:
            for _ in range(int(self.weather.precipitation * 15)):
                x = random.randint(0, WIDTH)
                y = random.randint(0, HEIGHT)
                pygame.draw.circle(self.screen, WHITE, (x, y), 2)
        
        elif self.weather.type == WeatherType.FOG:
            # Create fog overlay
            fog_surface = pygame.Surface((WIDTH, HEIGHT))
            fog_surface.set_alpha(100)
            fog_surface.fill(LIGHT_GRAY)
            self.screen.blit(fog_surface, (0, 0))
    
    def draw_advanced_hud(self):
        """Enhanced HUD with multiple modes"""
        if self.hud_mode == 0:  # Basic HUD
            self.draw_basic_hud()
        elif self.hud_mode == 1:  # Advanced HUD
            self.draw_tactical_hud()
        elif self.hud_mode == 2:  # Minimal HUD
            self.draw_minimal_hud()
    
    def draw_basic_hud(self):
        """Standard flight information display"""
        # Left panel - Flight data
        y_offset = 10
        info_items = [
            f"Aircraft: {self.aircraft.config.name}",
            f"Altitude: {int(self.aircraft.y)}m",
            f"Speed: {int(math.sqrt(self.aircraft.vx**2 + self.aircraft.vy**2 + self.aircraft.vz**2))} m/s",
            f"Thrust: {int(self.aircraft.thrust)}%",
            f"Fuel: {int(self.aircraft.fuel)}%",
            f"Pitch: {int(self.aircraft.pitch)}°",
            f"Heading: {int(self.aircraft.yaw)}°",
            f"Roll: {int(self.aircraft.roll)}°",
            f"G-Force: {self.aircraft.current_g_force:.1f}g",
            f"Flaps: {int(self.aircraft.flaps)}°",
        ]
        
        for item in info_items:
            color = WHITE
            if "Fuel:" in item and self.aircraft.fuel < 20:
                color = RED
            elif "G-Force:" in item and self.aircraft.current_g_force > 5:
                color = RED
            
            text = self.font.render(item, True, color)
            self.screen.blit(text, (10, y_offset))
            y_offset += 30
        
        # Right panel - Systems and weather
        y_offset = 10
        systems_items = [
            f"Engine: {'ON' if self.aircraft.engine_on else 'OFF'}",
            f"Gear: {'DOWN' if self.aircraft.gear_down else 'UP'}",
            f"Autopilot: {'ON' if self.aircraft.autopilot else 'OFF'}",
            f"Nav Mode: {'ON' if self.aircraft.nav_mode else 'OFF'}",
            f"Weather: {self.weather.type.value}",
            f"Wind: {int(self.weather.wind_speed)} m/s @ {int(self.weather.wind_direction)}°",
            f"Visibility: {int(self.weather.visibility)}m",
            f"Turbulence: {int(self.weather.turbulence)}/10",
        ]
        
        for item in systems_items:
            color = WHITE
            if "Engine: OFF" in item:
                color = RED
            elif "Autopilot: ON" in item:
                color = GREEN
            elif "Nav Mode: ON" in item:
                color = CYAN
            
            text = self.font.render(item, True, color)
            self.screen.blit(text, (WIDTH - 300, y_offset))
            y_offset += 30
    
    def draw_tactical_hud(self):
        """Military-style HUD for fighter aircraft"""
        center_x, center_y = WIDTH // 2, HEIGHT // 2
        
        # Crosshair
        pygame.draw.line(self.screen, GREEN, (center_x - 20, center_y), (center_x + 20, center_y), 2)
        pygame.draw.line(self.screen, GREEN, (center_x, center_y - 20), (center_x, center_y + 20), 2)
        
        # Altitude ladder (right side)
        for alt in range(int(self.aircraft.y // 100) * 100 - 500, int(self.aircraft.y // 100) * 100 + 500, 100):
            if alt >= 0:
                y_pos = center_y - (alt - self.aircraft.y) * 0.5
                if 50 < y_pos < HEIGHT - 50:
                    pygame.draw.line(self.screen, GREEN, (WIDTH - 100, int(y_pos)), (WIDTH - 80, int(y_pos)), 2)
                    text = self.small_font.render(str(alt), True, GREEN)
                    self.screen.blit(text, (WIDTH - 75, int(y_pos) - 10))
        
        # Speed tape (left side)
        speed = int(math.sqrt(self.aircraft.vx**2 + self.aircraft.vy**2 + self.aircraft.vz**2))
        for spd in range(speed - 50, speed + 50, 10):
            if spd >= 0:
                y_pos = center_y - (spd - speed) * 2
                if 50 < y_pos < HEIGHT - 50:
                    pygame.draw.line(self.screen, GREEN, (80, int(y_pos)), (100, int(y_pos)), 2)
                    text = self.small_font.render(str(spd), True, GREEN)
                    self.screen.blit(text, (10, int(y_pos) - 10))
        
        # Heading indicator (top)
        for hdg in range(int(self.aircraft.yaw // 10) * 10 - 90, int(self.aircraft.yaw // 10) * 10 + 90, 10):
            hdg_norm = hdg % 360
            x_pos = center_x + (hdg - self.aircraft.yaw) * 3
            if 50 < x_pos < WIDTH - 50:
                pygame.draw.line(self.screen, GREEN, (int(x_pos), 80), (int(x_pos), 100), 2)
                text = self.small_font.render(str(int(hdg_norm)), True, GREEN)
                self.screen.blit(text, (int(x_pos) - 10, 50))
        
        # Current aircraft indicator
        pygame.draw.polygon(self.screen, YELLOW, [
            (center_x, center_y - 10),
            (center_x - 15, center_y + 10),
            (center_x + 15, center_y + 10)
        ])
        
        # Waypoint information
        if self.aircraft.waypoints and self.aircraft.current_waypoint < len(self.aircraft.waypoints):
            wp = self.aircraft.waypoints[self.aircraft.current_waypoint]
            distance = math.sqrt((wp.x - self.aircraft.x)**2 + (wp.z - self.aircraft.z)**2)
            bearing = math.degrees(math.atan2(wp.z - self.aircraft.z, wp.x - self.aircraft.x))
            
            nav_text = [
                f"Next WP: {wp.name}",
                f"Distance: {int(distance)}m",
                f"Bearing: {int(bearing)}°"
            ]
            
            for i, text in enumerate(nav_text):
                rendered = self.font.render(text, True, CYAN)
                self.screen.blit(rendered, (10, HEIGHT - 100 + i * 25))
    
    def draw_minimal_hud(self):
        """Clean, minimal HUD for civilian aircraft"""
        # Essential info only
        speed = int(math.sqrt(self.aircraft.vx**2 + self.aircraft.vy**2 + self.aircraft.vz**2))
        
        essential_info = [
            f"ALT: {int(self.aircraft.y)}m",
            f"SPD: {speed} m/s",
            f"HDG: {int(self.aircraft.yaw)}°",
            f"FUEL: {int(self.aircraft.fuel)}%"
        ]
        
        for i, info in enumerate(essential_info):
            color = RED if ("FUEL:" in info and self.aircraft.fuel < 20) else WHITE
            text = self.font.render(info, True, color)
            self.screen.blit(text, (10, 10 + i * 30))
    
    def draw_artificial_horizon(self):
        """Enhanced artificial horizon indicator"""
        center_x, center_y = WIDTH - 150, HEIGHT - 150
        radius = 100
        
        # Background circle
        pygame.draw.circle(self.screen, BLACK, (center_x, center_y), radius)
        pygame.draw.circle(self.screen, WHITE, (center_x, center_y), radius, 2)
        
        # Sky and ground
        sky_color = BLUE if self.weather.type == WeatherType.CLEAR else DARK_BLUE
        ground_color = BROWN
        
        # Calculate horizon line based on pitch
        horizon_y = center_y + self.aircraft.pitch * 2
        
        # Draw sky (upper half)
        points = []
        for angle in range(0, 181, 10):
            x = center_x + radius * math.cos(math.radians(angle))
            y = min(horizon_y, center_y + radius * math.sin(math.radians(angle)))
            points.append((x, y))
        
        if len(points) > 2:
            pygame.draw.polygon(self.screen, sky_color, points)
        
        # Draw ground (lower half)
        points = []
        for angle in range(180, 361, 10):
            x = center_x + radius * math.cos(math.radians(angle))
            y = max(horizon_y, center_y + radius * math.sin(math.radians(angle)))
            points.append((x, y))
        
        if len(points) > 2:
            pygame.draw.polygon(self.screen, ground_color, points)
        
        # Roll indicator
        roll_angle = self.aircraft.roll
        roll_x = center_x + (radius - 20) * math.sin(math.radians(roll_angle))
        roll_y = center_y - (radius - 20) * math.cos(math.radians(roll_angle))
        pygame.draw.line(self.screen, WHITE, (center_x, center_y - radius + 10), (roll_x, roll_y), 3)
        
        # Aircraft symbol (fixed)
        pygame.draw.line(self.screen, YELLOW, (center_x - 30, center_y), (center_x + 30, center_y), 3)
        pygame.draw.line(self.screen, YELLOW, (center_x, center_y - 15), (center_x, center_y + 15), 3)
        
        # Pitch lines
        for pitch_line in range(-30, 31, 10):
            if pitch_line != 0:
                line_y = center_y + pitch_line * 2 + self.aircraft.pitch * 2
                if abs(line_y - center_y) < radius - 10:
                    line_length = 40 if pitch_line % 20 == 0 else 20
                    pygame.draw.line(self.screen, WHITE, 
                                   (center_x - line_length//2, line_y), 
                                   (center_x + line_length//2, line_y), 1)
                    
                    # Pitch value labels
                    if pitch_line % 20 == 0:
                        pitch_text = self.small_font.render(str(abs(pitch_line)), True, WHITE)
                        self.screen.blit(pitch_text, (center_x + line_length//2 + 5, line_y - 8))
    
    def draw_radar_display(self):
        """Mini radar/map display"""
        radar_x, radar_y = 50, HEIGHT - 150
        radar_size = 100
        
        # Radar background
        pygame.draw.circle(self.screen, BLACK, (radar_x, radar_y), radar_size)
        pygame.draw.circle(self.screen, GREEN, (radar_x, radar_y), radar_size, 2)
        pygame.draw.circle(self.screen, GREEN, (radar_x, radar_y), radar_size//2, 1)
        
        # Aircraft position (center)
        pygame.draw.circle(self.screen, YELLOW, (radar_x, radar_y), 3)
        
        # Draw waypoints on radar
        for i, wp in enumerate(self.aircraft.waypoints):
            # Scale waypoint position to radar
            dx = (wp.x - self.aircraft.x) / 100  # Scale factor
            dz = (wp.z - self.aircraft.z) / 100
            
            if abs(dx) < radar_size and abs(dz) < radar_size:
                wp_x = int(radar_x + dx)
                wp_y = int(radar_y + dz)
                
                color = YELLOW if i == self.aircraft.current_waypoint else CYAN
                if wp.waypoint_type == "AIRPORT":
                    color = GREEN
                
                pygame.draw.circle(self.screen, color, (wp_x, wp_y), 2)
        
        # Heading indicator
        heading_rad = math.radians(self.aircraft.yaw)
        end_x = radar_x + 30 * math.cos(heading_rad)
        end_y = radar_y + 30 * math.sin(heading_rad)
        pygame.draw.line(self.screen, WHITE, (radar_x, radar_y), (end_x, end_y), 2)
    
    def draw_system_warnings(self):
        """Draw system warnings and alerts"""
        warnings = []
        
        if self.aircraft.fuel < 20:
            warnings.append("LOW FUEL")
        if not self.aircraft.engine_on:
            warnings.append("ENGINE OFF")
        if self.aircraft.current_g_force > self.aircraft.max_g_force * 0.8:
            warnings.append("HIGH G-FORCE")
        if self.aircraft.structural_integrity < 50:
            warnings.append("STRUCTURAL DAMAGE")
        if self.weather.turbulence > 7:
            warnings.append("SEVERE TURBULENCE")
        
        # Stall warning
        speed = math.sqrt(self.aircraft.vx**2 + self.aircraft.vy**2 + self.aircraft.vz**2)
        if speed < self.aircraft.config.stall_speed * 1.1 and self.aircraft.y > 50:
            warnings.append("STALL WARNING")
        
        # Display warnings
        for i, warning in enumerate(warnings):
            color = RED if random.randint(0, 10) > 5 else YELLOW  # Blinking effect
            text = self.font.render(warning, True, color)
            text_rect = text.get_rect(center=(WIDTH//2, 100 + i * 40))
            self.screen.blit(text, text_rect)
    
    def draw_help_screen(self):
        """Comprehensive help display"""
        help_sections = {
            "BASIC CONTROLS": [
                "W/S - Throttle Up/Down",
                "Arrow Keys - Pitch Control",
                "A/D - Roll Left/Right", 
                "Left/Right - Yaw Control",
                "F/G - Flaps Up/Down",
                "L - Landing Gear Toggle",
                "E - Engine On/Off"
            ],
            "ADVANCED CONTROLS": [
                "P - Autopilot Toggle",
                "N - Navigation Mode",
                "H - Toggle Help",
                "SPACE - Pause",
                "R - Restart (if crashed)",
                "1/2/3 - Change Aircraft Type",
                "TAB - Change HUD Mode",
                "C - Change Camera Mode"
            ],
            "AUTOPILOT": [
                "Set target altitude/heading",
                "Aircraft will maintain settings",
                "Manual input overrides autopilot",
                "Use with navigation waypoints"
            ],
            "NAVIGATION": [
                "Follow waypoints automatically",
                "Green = Airports",
                "Yellow = Current waypoint", 
                "Cyan = Navigation points"
            ]
        }
        
        # Semi-transparent background
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))
        
        x_offset = 50
        y_offset = 50
        
        for section, items in help_sections.items():
            # Section header
            header = self.font.render(section, True, YELLOW)
            self.screen.blit(header, (x_offset, y_offset))
            y_offset += 40
            
            # Section items
            for item in items:
                text = self.small_font.render(item, True, WHITE)
                self.screen.blit(text, (x_offset + 20, y_offset))
                y_offset += 25
            
            y_offset += 20
            
            # Move to next column if needed
            if y_offset > HEIGHT - 100:
                x_offset += 400
                y_offset = 50
    
    def handle_aircraft_selection(self, keys):
        """Handle aircraft type selection"""
        if keys[pygame.K_1]:
            self.aircraft_type = AircraftType.FIGHTER
            self.restart_game()
        elif keys[pygame.K_2]:
            self.aircraft_type = AircraftType.AIRLINER
            self.restart_game()
        elif keys[pygame.K_3]:
            self.aircraft_type = AircraftType.GLIDER
            self.restart_game()
        elif keys[pygame.K_4]:
            self.aircraft_type = AircraftType.HELICOPTER
            self.restart_game()
    
    def get_camera_position(self):
        """Calculate camera position based on mode"""
        if self.camera_mode == 0:  # Follow camera
            camera_x = self.aircraft.x - self.camera_distance * math.cos(math.radians(self.aircraft.yaw))
            camera_y = self.aircraft.y + self.camera_height
            camera_z = self.aircraft.z - self.camera_distance * math.sin(math.radians(self.aircraft.yaw))
            camera_yaw = self.aircraft.yaw
            camera_pitch = self.aircraft.pitch * 0.3
        elif self.camera_mode == 1:  # Cockpit view
            camera_x = self.aircraft.x + 10 * math.cos(math.radians(self.aircraft.yaw))
            camera_y = self.aircraft.y + 5
            camera_z = self.aircraft.z + 10 * math.sin(math.radians(self.aircraft.yaw))
            camera_yaw = self.aircraft.yaw
            camera_pitch = self.aircraft.pitch
        else:  # Free camera (simplified)
            camera_x = self.aircraft.x
            camera_y = self.aircraft.y + 500
            camera_z = self.aircraft.z - 500
            camera_yaw = 45
            camera_pitch = -30
        
        return camera_x, camera_y, camera_z, camera_yaw, camera_pitch
    
    def restart_game(self):
        """Restart with selected aircraft type"""
        self.aircraft = Aircraft(0, 1000, 0, self.aircraft_type)
        self.setup_navigation()
        self.particles = []
    
    def update_game_time(self, dt):
        """Update game time and time-based events"""
        self.game_time += dt * self.time_scale
        
        # Day/night cycle effects
        hour = (self.game_time / 3600) % 24
        if 6 <= hour <= 18:  # Day
            sky_color = BLUE
        else:  # Night
            sky_color = DARK_BLUE
        
        return sky_color
    
    def run(self):
        """Main game loop"""
        running = True
        
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_h:
                        self.show_help = not self.show_help
                    elif event.key == pygame.K_SPACE:
                        self.paused = not self.paused
                    elif event.key == pygame.K_r and self.aircraft.crashed:
                        self.restart_game()
                    elif event.key == pygame.K_TAB:
                        self.hud_mode = (self.hud_mode + 1) % 3
                    elif event.key == pygame.K_c:
                        self.camera_mode = (self.camera_mode + 1) % 3
                    elif event.key == pygame.K_t:
                        self.time_scale = 2.0 if self.time_scale == 1.0 else 1.0
            
            # Handle input
            keys = pygame.key.get_pressed()
            self.handle_aircraft_selection(keys)
            
            if not self.paused:
                # Handle aircraft input
                self.aircraft.handle_input(keys)
                
                # Update systems
                self.aircraft.update(dt, self.weather)
                self.weather.update(dt)
                
                # Create particle effects
                if self.aircraft.thrust > 0 and self.aircraft.engine_on:
                    self.create_particle_effect(self.aircraft.x, self.aircraft.y, self.aircraft.z)
                
                # Update particles
                self.update_particles(dt)
            
            # Update game time
            sky_color = self.update_game_time(dt)
            
            # Get camera position
            camera_x, camera_y, camera_z, camera_yaw, camera_pitch = self.get_camera_position()
            
            # Clear screen
            self.screen.fill(sky_color)
            
            # Draw world
            if not self.show_help:
                self.draw_terrain(camera_x, camera_y, camera_z, camera_yaw, camera_pitch)
                self.draw_waypoints(camera_x, camera_y, camera_z, camera_yaw, camera_pitch)
                self.draw_aircraft(camera_x, camera_y, camera_z, camera_yaw, camera_pitch)
                self.draw_particles(camera_x, camera_y, camera_z, camera_yaw, camera_pitch)
                
                # Draw weather effects
                self.draw_weather_effects()
                
                # Draw UI
                self.draw_advanced_hud()
                self.draw_artificial_horizon()
                self.draw_radar_display()
                self.draw_system_warnings()
            
            # Draw help screen
            if self.show_help:
                self.draw_help_screen()
            
            # Draw pause indicator
            if self.paused:
                pause_text = self.large_font.render("PAUSED", True, YELLOW)
                text_rect = pause_text.get_rect(center=(WIDTH//2, HEIGHT//2))
                self.screen.blit(pause_text, text_rect)
            
            # Draw crash screen
            if self.aircraft.crashed:
                crash_text = self.large_font.render("AIRCRAFT CRASHED", True, RED)
                restart_text = self.font.render("Press R to restart", True, WHITE)
                crash_rect = crash_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 50))
                restart_rect = restart_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 50))
                self.screen.blit(crash_text, crash_rect)
                self.screen.blit(restart_text, restart_rect)
            
            pygame.display.flip()
        
        pygame.quit()

if __name__ == "__main__":
    print("Advanced Flight Simulator")
    print("=========================")
    print("Aircraft Types: 1=Fighter, 2=Airliner, 3=Glider, 4=Helicopter")
    print("Press H for help, SPACE to pause")
    print("Use autopilot (P) and navigation (N) for assisted flight")
    print()
    
    game = FlightSimulator()
    game.run()