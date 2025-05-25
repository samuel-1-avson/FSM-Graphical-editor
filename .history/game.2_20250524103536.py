import pygame
import math
import random
import numpy as np
import json
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional
import time

# Initialize Pygame
pygame.init()
pygame.mixer.init()

# Constants
WIDTH, HEIGHT = 1600, 1000
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
GOLD = (255, 215, 0)
LIME = (0, 255, 0)
PINK = (255, 192, 203)
NAVY = (0, 0, 128)
SILVER = (192, 192, 192)

class WeatherType(Enum):
    CLEAR = "Clear"
    CLOUDY = "Cloudy"
    RAIN = "Rain"
    STORM = "Storm"
    FOG = "Fog"
    SNOW = "Snow"
    WIND_SHEAR = "Wind Shear"
    ICING = "Icing"

class AircraftType(Enum):
    FIGHTER = "Fighter"
    AIRLINER = "Airliner"
    GLIDER = "Glider"
    HELICOPTER = "Helicopter"
    CARGO = "Cargo"
    ULTRALIGHT = "Ultralight"

class MissionType(Enum):
    FREE_FLIGHT = "Free Flight"
    LANDING_CHALLENGE = "Landing Challenge"
    NAVIGATION = "Navigation"
    AEROBATICS = "Aerobatics"
    EMERGENCY = "Emergency"
    FORMATION = "Formation Flight"

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
    service_ceiling: float
    max_g_force: float
    climb_rate: float

@dataclass
class Waypoint:
    x: float
    z: float
    altitude: float
    name: str
    waypoint_type: str = "NAV"
    required_speed: Optional[float] = None
    required_altitude_tolerance: float = 100.0

class SoundManager:
    def __init__(self):
        self.sounds = {}
        self.engine_channel = None
        self.warning_channel = None
        self.ambient_channel = None
        self.enabled = True
        
    def create_engine_sound(self, frequency, duration=0.1):
        """Generate synthetic engine sound"""
        if not self.enabled:
            return
        
        sample_rate = 22050
        frames = int(duration * sample_rate)
        arr = np.zeros((frames, 2))
        
        for i in range(frames):
            # Basic engine rumble with harmonics
            wave = np.sin(2 * np.pi * frequency * i / sample_rate)
            wave += 0.3 * np.sin(2 * np.pi * frequency * 2 * i / sample_rate)
            wave += 0.1 * np.sin(2 * np.pi * frequency * 4 * i / sample_rate)
            
            # Add some noise for realism
            wave += 0.05 * (np.random.random() - 0.5)
            
            arr[i] = [wave * 0.1, wave * 0.1]  # Stereo
        
        # Convert to pygame sound
        sound_array = (arr * 32767).astype(np.int16)
        sound = pygame.sndarray.make_sound(sound_array)
        return sound
    
    def play_engine_sound(self, thrust_percent):
        """Play engine sound based on thrust"""
        if not self.enabled:
            return
            
        base_freq = 50 + thrust_percent * 2
        if self.engine_channel is None or not self.engine_channel.get_busy():
            sound = self.create_engine_sound(base_freq, 0.5)
            self.engine_channel = sound.play(-1)  # Loop
        
    def play_warning_sound(self):
        """Play warning beep"""
        if not self.enabled:
            return
            
        # Generate warning beep
        sample_rate = 22050
        duration = 0.2
        frames = int(duration * sample_rate)
        arr = np.zeros(frames)
        
        for i in range(frames):
            arr[i] = 0.3 * np.sin(2 * np.pi * 800 * i / sample_rate)
        
        sound_array = (arr * 32767).astype(np.int16)
        sound = pygame.sndarray.make_sound(sound_array)
        if self.warning_channel is None or not self.warning_channel.get_busy():
            self.warning_channel = sound.play()

class Weather:
    def __init__(self):
        self.type = WeatherType.CLEAR
        self.wind_speed = 5
        self.wind_direction = 270
        self.wind_gusts = 0
        self.visibility = 15000
        self.cloud_ceiling = 10000
        self.cloud_layers = []
        self.temperature = 15
        self.pressure = 1013.25
        self.humidity = 50
        self.turbulence = 0
        self.precipitation = 0
        self.lightning_strikes = []
        self.icing_intensity = 0
        self.wind_shear_altitude = 0
        self.wind_shear_strength = 0
        
        # Generate initial cloud layers
        self.generate_clouds()
        
    def generate_clouds(self):
        """Generate realistic cloud layers"""
        self.cloud_layers = []
        if self.type in [WeatherType.CLOUDY, WeatherType.STORM, WeatherType.RAIN]:
            num_layers = random.randint(1, 3)
            for _ in range(num_layers):
                layer = {
                    'altitude': random.randint(500, 8000),
                    'thickness': random.randint(200, 1500),
                    'coverage': random.uniform(0.3, 0.9),
                    'type': random.choice(['cumulus', 'stratus', 'cumulonimbus'])
                }
                self.cloud_layers.append(layer)
        
    def update(self, dt):
        # More realistic weather evolution
        if random.random() < 0.0005:  # Weather change
            old_type = self.type
            self.type = random.choice(list(WeatherType))
            if self.type != old_type:
                self.generate_clouds()
            self.update_conditions()
        
        # Wind gusts
        if random.random() < 0.01:
            self.wind_gusts = random.uniform(0, self.wind_speed * 0.5)
        else:
            self.wind_gusts *= 0.95
        
        # Lightning for storms
        if self.type == WeatherType.STORM and random.random() < 0.002:
            self.lightning_strikes.append({
                'x': random.uniform(-5000, 5000),
                'z': random.uniform(-5000, 5000),
                'intensity': random.uniform(0.7, 1.0),
                'time': time.time()
            })
        
        # Remove old lightning
        current_time = time.time()
        self.lightning_strikes = [strike for strike in self.lightning_strikes 
                                if current_time - strike['time'] < 0.2]
    
    def update_conditions(self):
        if self.type == WeatherType.CLEAR:
            self.visibility = random.uniform(12000, 20000)
            self.wind_speed = random.uniform(0, 15)
            self.turbulence = random.uniform(0, 2)
            self.precipitation = 0
            self.icing_intensity = 0
        elif self.type == WeatherType.CLOUDY:
            self.visibility = random.uniform(8000, 15000)
            self.wind_speed = random.uniform(5, 20)
            self.cloud_ceiling = random.uniform(1000, 4000)
            self.turbulence = random.uniform(1, 4)
        elif self.type == WeatherType.RAIN:
            self.visibility = random.uniform(2000, 6000)
            self.wind_speed = random.uniform(10, 30)
            self.turbulence = random.uniform(3, 6)
            self.precipitation = random.uniform(3, 7)
            self.humidity = random.uniform(80, 95)
        elif self.type == WeatherType.STORM:
            self.visibility = random.uniform(500, 2000)
            self.wind_speed = random.uniform(25, 50)
            self.turbulence = random.uniform(7, 10)
            self.precipitation = random.uniform(7, 10)
            self.humidity = 95
        elif self.type == WeatherType.FOG:
            self.visibility = random.uniform(100, 800)
            self.wind_speed = random.uniform(0, 8)
            self.turbulence = random.uniform(0, 2)
            self.humidity = random.uniform(95, 100)
        elif self.type == WeatherType.SNOW:
            self.visibility = random.uniform(1000, 4000)
            self.wind_speed = random.uniform(5, 25)
            self.turbulence = random.uniform(2, 5)
            self.precipitation = random.uniform(2, 6)
            self.temperature = random.uniform(-15, 2)
        elif self.type == WeatherType.WIND_SHEAR:
            self.wind_shear_altitude = random.uniform(500, 3000)
            self.wind_shear_strength = random.uniform(15, 35)
        elif self.type == WeatherType.ICING:
            self.icing_intensity = random.uniform(3, 8)
            self.temperature = random.uniform(-10, 2)
            self.humidity = random.uniform(85, 100)
        
        self.wind_direction = random.uniform(0, 360)
        self.pressure = random.uniform(995, 1030)

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
        self.flaps = 0
        self.spoilers = 0
        self.brakes = 0
        self.autopilot = False
        self.target_altitude = 0
        self.target_heading = 0
        self.target_speed = 0
        self.engine_on = True
        self.engine_count = 1
        self.engines_failed = []
        
        # Enhanced aircraft configurations
        self.configs = {
            AircraftType.FIGHTER: AircraftConfig(
                "F-16 Fighting Falcon", 180, 8500, 0.022, 1.3, 650, 120, 0.18, 18000, 6, 85, 15000, 9.0, 15
            ),
            AircraftType.AIRLINER: AircraftConfig(
                "Boeing 737-800", 120, 75000, 0.018, 1.0, 280, 300, 0.06, 14000, 2.5, 130, 12500, 2.5, 8
            ),
            AircraftType.GLIDER: AircraftConfig(
                "ASK-21 Glider", 0, 750, 0.012, 1.8, 120, 0, 0, 10000, 4, 45, 8000, 5.0, 3
            ),
            AircraftType.HELICOPTER: AircraftConfig(
                "UH-60 Black Hawk", 90, 5200, 0.045, 0.7, 90, 180, 0.15, 8000, 10, 0, 6000, 3.5, 12
            ),
            AircraftType.CARGO: AircraftConfig(
                "C-130 Hercules", 140, 35000, 0.025, 0.85, 220, 400, 0.08, 12000, 2, 110, 10000, 2.0, 6
            ),
            AircraftType.ULTRALIGHT: AircraftConfig(
                "Quicksilver MX", 25, 250, 0.035, 1.2, 65, 25, 0.12, 3000, 8, 35, 2500, 3.0, 5
            )
        }
        
        self.type = aircraft_type
        self.config = self.configs[aircraft_type]
        self.fuel = self.config.fuel_capacity
        self.max_thrust = self.config.max_thrust
        self.mass = self.config.mass
        
        # Enhanced systems
        self.waypoints: List[Waypoint] = []
        self.current_waypoint = 0
        self.nav_mode = False
        self.ils_locked = False
        self.approach_mode = False
        
        # Detailed aircraft systems
        self.electrical = True
        self.hydraulics = True
        self.avionics = True
        self.engine_health = [100] * max(1, self.engine_count)
        self.structural_integrity = 100
        self.ice_buildup = 0
        self.pitot_static_system = True
        
        # Flight envelope protection and performance
        self.max_g_force = self.config.max_g_force
        self.current_g_force = 1.0
        self.angle_of_attack = 0
        self.stall_warning = False
        self.overspeed_warning = False
        
        # Enhanced flight model parameters
        self.center_of_gravity = 0.3  # 0-1, affects stability
        self.weight_and_balance = True
        self.wing_loading = self.mass / 50  # Simplified wing area
        
        # Navigation and communication
        self.transponder = 1200  # Squawk code
        self.radio_freq = 121.5  # MHz
        self.gps_accuracy = 5  # meters
        
        # Performance tracking
        self.max_altitude_reached = 0
        self.max_speed_reached = 0
        self.flight_time = 0
        self.distance_traveled = 0
        self.fuel_used = 0
        
        # Landing system
        self.touchdown_rate = 0
        self.landing_score = 0
        
    def calculate_performance_envelope(self, altitude, weather):
        """Calculate current performance limits based on conditions"""
        # Altitude effects on engine performance
        altitude_factor = max(0.1, 1 - altitude / self.config.service_ceiling)
        
        # Weather effects
        weather_factor = 1.0
        if weather.type == WeatherType.ICING:
            weather_factor *= (1 - weather.icing_intensity * 0.05)
            self.ice_buildup = min(100, self.ice_buildup + 0.1)
        
        # Temperature effects (simplified)
        temp_factor = 1 + (15 - weather.temperature) * 0.01
        
        return altitude_factor * weather_factor * temp_factor
    
    def update_systems(self, dt, weather):
        """Update aircraft systems"""
        # System failures based on conditions
        if weather.type == WeatherType.STORM and random.random() < 0.0001:
            if random.random() < 0.3:
                self.electrical = False
            elif random.random() < 0.2:
                self.avionics = False
        
        # Pitot icing
        if weather.type == WeatherType.ICING and weather.temperature < 0:
            if random.random() < 0.001:
                self.pitot_static_system = False
        
        # Engine health degradation
        for i, health in enumerate(self.engine_health):
            if health > 0:
                # Normal wear
                self.engine_health[i] = max(0, health - 0.001)
                
                # Accelerated wear in harsh conditions
                if weather.type in [WeatherType.STORM, WeatherType.ICING]:
                    self.engine_health[i] = max(0, health - 0.005)
    
    def calculate_aerodynamics(self, weather):
        """Enhanced aerodynamic calculations"""
        speed = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        
        # Air density effects (altitude and temperature)
        air_density = 1.225 * math.exp(-self.y / 8000)  # Standard atmosphere
        air_density *= (288.15 / (288.15 + weather.temperature - 15)) ** 4.26
        
        # Dynamic pressure
        q = 0.5 * air_density * speed**2
        
        # Angle of attack calculation
        if speed > 1:
            self.angle_of_attack = math.degrees(math.atan2(self.vy, 
                                               math.sqrt(self.vx**2 + self.vz**2)))
        
        # Lift coefficient based on AoA and flaps
        base_cl = self.config.lift_coefficient
        flap_cl_bonus = (self.flaps / 40) * 0.8
        aoa_cl = math.sin(math.radians(self.angle_of_attack)) * 2
        
        cl = base_cl + flap_cl_bonus + aoa_cl
        
        # Stall characteristics
        critical_aoa = 15 + (self.flaps / 40) * 5
        if abs(self.angle_of_attack) > critical_aoa:
            cl *= 0.3  # Post-stall
            self.stall_warning = True
        else:
            self.stall_warning = False
        
        # Drag calculation
        cd_base = self.config.drag_coefficient
        cd_induced = cl**2 / (math.pi * 8)  # Induced drag
        cd_flaps = (self.flaps / 40) * 0.02
        cd_gear = 0.015 if self.gear_down else 0
        cd_spoilers = (self.spoilers / 100) * 0.08
        
        cd_total = cd_base + cd_induced + cd_flaps + cd_gear + cd_spoilers
        
        # Forces
        lift = cl * q * 50  # Wing area approximation
        drag = cd_total * q * 50
        
        return lift, drag, air_density
    
    def update_autopilot_advanced(self):
        """Enhanced autopilot with multiple modes"""
        if not self.autopilot:
            return
        
        current_speed = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        
        # Altitude hold with climb/descent rate limiting
        altitude_error = self.target_altitude - self.y
        max_climb_rate = self.config.climb_rate
        
        if abs(altitude_error) > 100:
            target_climb_rate = max(-max_climb_rate, 
                                  min(max_climb_rate, altitude_error * 0.1))
            pitch_adjustment = target_climb_rate / current_speed if current_speed > 0 else 0
            self.pitch = max(-20, min(20, math.degrees(pitch_adjustment)))
        
        # Speed hold with throttle control
        if self.target_speed > 0:
            speed_error = self.target_speed - current_speed
            throttle_adjustment = speed_error * 0.5
            self.thrust = max(0, min(100, self.thrust + throttle_adjustment))
        
        # Heading hold with coordinated turns
        heading_error = self.target_heading - self.yaw
        while heading_error > 180:
            heading_error -= 360
        while heading_error < -180:
            heading_error += 360
        
        if abs(heading_error) > 2:
            bank_angle = max(-25, min(25, heading_error * 0.5))
            self.roll = bank_angle
        else:
            self.roll *= 0.9
    
    def update_navigation_advanced(self):
        """Enhanced navigation with approach procedures"""
        if not self.waypoints or self.current_waypoint >= len(self.waypoints):
            return
        
        wp = self.waypoints[self.current_waypoint]
        
        # Calculate navigation parameters
        dx = wp.x - self.x
        dz = wp.z - self.z
        horizontal_distance = math.sqrt(dx**2 + dz**2)
        bearing = math.degrees(math.atan2(dz, dx))
        
        # Altitude constraint handling
        altitude_error = wp.altitude - self.y
        
        # Speed constraint handling
        current_speed = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        if wp.required_speed and abs(current_speed - wp.required_speed) > 10:
            speed_adjustment = (wp.required_speed - current_speed) * 0.02
            self.thrust = max(0, min(100, self.thrust + speed_adjustment))
        
        # Approach mode for airports
        if wp.waypoint_type == "AIRPORT" and horizontal_distance < 5000:
            self.approach_mode = True
            # ILS approach simulation
            if horizontal_distance < 1000:
                self.ils_locked = True
                glide_slope = -3  # degrees
                target_altitude = wp.altitude + (horizontal_distance * math.tan(math.radians(-glide_slope)))
                if abs(self.y - target_altitude) > 50:
                    self.target_altitude = target_altitude
        
        # Auto-navigation
        if self.nav_mode and horizontal_distance > 50:
            heading_diff = bearing - self.yaw
            while heading_diff > 180:
                heading_diff -= 360
            while heading_diff < -180:
                heading_diff += 360
            
            if abs(heading_diff) > 5:
                self.target_heading = bearing
        
        # Waypoint capture
        capture_radius = 200 if wp.waypoint_type == "AIRPORT" else 100
        if horizontal_distance < capture_radius and abs(altitude_error) < wp.required_altitude_tolerance:
            self.current_waypoint += 1
            self.approach_mode = False
            self.ils_locked = False
    
    def calculate_landing_score(self):
        """Calculate landing performance score"""
        if not self.on_ground:
            return 0
        
        score = 100
        
        # Touchdown rate penalty
        if abs(self.touchdown_rate) > 3:
            score -= min(50, abs(self.touchdown_rate) * 5)
        
        # Speed penalty
        touchdown_speed = math.sqrt(self.vx**2 + self.vz**2)
        if touchdown_speed > self.config.stall_speed * 1.3:
            score -= (touchdown_speed - self.config.stall_speed * 1.3) * 2
        
        # Centerline deviation (simplified)
        score = max(0, min(100, score))
        return score
    
    def update(self, dt, weather: Weather):
        if self.crashed:
            return
        
        # Update flight time and performance tracking
        self.flight_time += dt
        old_pos = (self.x, self.z)
        
        # Update systems
        self.update_systems(dt, weather)
        
        # Enhanced autopilot
        self.update_autopilot_advanced()
        
        # Enhanced navigation
        self.update_navigation_advanced()
        
        # Performance envelope
        performance_factor = self.calculate_performance_envelope(self.y, weather)
        
        # Fuel consumption with realistic factors
        if self.thrust > 0 and self.engine_on and any(h > 0 for h in self.engine_health):
            base_consumption = self.config.fuel_consumption * (self.thrust / 100) * dt
            altitude_factor = 1 - (self.y / self.config.service_ceiling) * 0.3
            consumption = base_consumption * altitude_factor * performance_factor
            self.fuel = max(0, self.fuel - consumption)
            self.fuel_used += consumption
        
        # Engine failure conditions
        avg_engine_health = sum(self.engine_health) / len(self.engine_health)
        if self.fuel <= 0 or avg_engine_health < 10:
            self.engine_on = False
            self.thrust = 0
        
        # Enhanced weather effects
        wind_effect_x = weather.wind_speed * math.cos(math.radians(weather.wind_direction)) * 0.05
        wind_effect_z = weather.wind_speed * math.sin(math.radians(weather.wind_direction)) * 0.05
        
        # Wind gusts
        if weather.wind_gusts > 0:
            gust_x = weather.wind_gusts * math.cos(math.radians(weather.wind_direction + random.uniform(-30, 30))) * 0.1
            gust_z = weather.wind_gusts * math.sin(math.radians(weather.wind_direction + random.uniform(-30, 30))) * 0.1
            wind_effect_x += gust_x
            wind_effect_z += gust_z
        
        # Wind shear effects
        if weather.type == WeatherType.WIND_SHEAR and abs(self.y - weather.wind_shear_altitude) < 200:
            shear_intensity = 1 - abs(self.y - weather.wind_shear_altitude) / 200
            wind_effect_x += weather.wind_shear_strength * shear_intensity * 0.1
            self.pitch += random.uniform(-5, 5) * shear_intensity
        
        # Turbulence with realistic effects
        if weather.turbulence > 0:
            turb_factor = weather.turbulence * 0.1
            self.pitch += random.uniform(-turb_factor, turb_factor)
            self.roll += random.uniform(-turb_factor, turb_factor)
            self.yaw += random.uniform(-turb_factor * 0.5, turb_factor * 0.5)
        
        # Enhanced physics
        lift, drag, air_density = self.calculate_aerodynamics(weather)
        
        # Thrust calculation with engine health
        available_thrust = self.thrust * performance_factor
        if self.engine_on:
            thrust_factor = avg_engine_health / 100
            available_thrust *= thrust_factor
        else:
            available_thrust = 0
        
        # Gravity
        gravity = -9.81 * self.mass
        
        # Ground effect
        if self.y < 100:
            ground_effect = (100 - self.y) / 100
            lift *= (1 + ground_effect * 0.3)
            drag *= (1 - ground_effect * 0.1)
        
        # Force calculations with proper 3D physics
        cos_yaw = math.cos(math.radians(self.yaw))
        sin_yaw = math.sin(math.radians(self.yaw))
        cos_pitch = math.cos(math.radians(self.pitch))
        sin_pitch = math.sin(math.radians(self.pitch))
        cos_roll = math.cos(math.radians(self.roll))
        sin_roll = math.sin(math.radians(self.roll))
        
        # Speed for drag calculation
        speed = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        
        # Thrust forces
        thrust_x = available_thrust * cos_yaw * cos_pitch
        thrust_y = available_thrust * sin_pitch
        thrust_z = available_thrust * sin_yaw * cos_pitch
        
        # Drag forces
        if speed > 0:
            drag_x = -drag * (self.vx / speed)
            drag_y = -drag * (self.vy / speed)
            drag_z = -drag * (self.vz / speed)
        else:
            drag_x = drag_y = drag_z = 0
        
        # Lift forces (perpendicular to velocity vector)
        lift_x = -lift * sin_roll * cos_yaw
        lift_y = lift * cos_roll
        lift_z = -lift * sin_roll * sin_yaw
        
        # Total forces
        fx = thrust_x + drag_x + lift_x + wind_effect_x
        fy = thrust_y + drag_y + lift_y + gravity
        fz = thrust_z + drag_z + lift_z + wind_effect_z
        
        # Accelerations
        ax = fx / self.mass
        ay = fy / self.mass
        az = fz / self.mass
        
        # Update velocities
        self.vx += ax * dt
        self.vy += ay * dt
        self.vz += az * dt
        
        # Store touchdown rate for landing scoring
        if self.y > 0 and self.y + self.vy * dt <= 0:
            self.touchdown_rate = self.vy
        
        # Update positions
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        
        # Track distance traveled
        new_pos = (self.x, self.z)
        distance_delta = math.sqrt((new_pos[0] - old_pos[0])**2 + (new_pos[1] - old_pos[1])**2)
        self.distance_traveled += distance_delta
        
        # Update performance records
        current_speed = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        self.max_altitude_reached = max(self.max_altitude_reached, self.y)
        self.max_speed_reached = max(self.max_speed_reached, current_speed)
        
        # Enhanced ground collision with landing scoring
        if self.y