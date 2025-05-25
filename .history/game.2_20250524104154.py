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
        if self.y <= 0:
            self.y = 0
            self.vy = 0
            self.on_ground = True
            
            # Calculate G-force on impact
            impact_g = abs(self.touchdown_rate) / 9.81
            
            # Determine if crash or successful landing
            if not self.gear_down or impact_g > 3 or current_speed > self.config.stall_speed * 1.5:
                self.crashed = True
                self.structural_integrity = 0
            else:
                # Successful landing - calculate score
                self.landing_score = self.calculate_landing_score()
                
                # Apply ground friction
                ground_friction = 0.1 + (self.brakes / 100) * 0.3
                self.vx *= (1 - ground_friction * dt)
                self.vz *= (1 - ground_friction * dt)
        
        # G-force calculation
        if speed > 0:
            centripetal_acceleration = (speed**2) / 1000  # Simplified
            self.current_g_force = (abs(ay) + centripetal_acceleration) / 9.81
            
            # Structural damage from excessive G-forces
            if self.current_g_force > self.max_g_force:
                damage = (self.current_g_force - self.max_g_force) * 10
                self.structural_integrity = max(0, self.structural_integrity - damage)
                if self.structural_integrity <= 0:
                    self.crashed = True
        
        # Altitude limits
        if self.y > self.config.service_ceiling:
            # Engine performance degradation at extreme altitude
            self.thrust *= 0.5
        
        # Overspeed warning
        if current_speed > self.config.max_speed * 0.9:
            self.overspeed_warning = True
        else:
            self.overspeed_warning = False

class Camera:
    def __init__(self):
        self.x = 0
        self.y = 1000
        self.z = 0
        self.target_x = 0
        self.target_y = 0
        self.target_z = 0
        self.distance = 500
        self.angle_h = 0
        self.angle_v = -30
        self.mode = "follow"  # follow, cockpit, external, free
        self.smooth_factor = 0.1
        
    def update(self, aircraft: Aircraft, dt):
        if self.mode == "follow":
            # Smooth follow camera
            target_x = aircraft.x - self.distance * math.cos(math.radians(self.angle_h))
            target_y = aircraft.y + 200 - self.distance * math.sin(math.radians(self.angle_v))
            target_z = aircraft.z - self.distance * math.sin(math.radians(self.angle_h))
            
            self.x += (target_x - self.x) * self.smooth_factor
            self.y += (target_y - self.y) * self.smooth_factor
            self.z += (target_z - self.z) * self.smooth_factor
            
            self.target_x = aircraft.x
            self.target_y = aircraft.y
            self.target_z = aircraft.z
            
        elif self.mode == "cockpit":
            # Cockpit view
            self.x = aircraft.x
            self.y = aircraft.y + 5
            self.z = aircraft.z
            
            # Look in aircraft direction
            self.target_x = aircraft.x + 1000 * math.cos(math.radians(aircraft.yaw))
            self.target_y = aircraft.y + 1000 * math.sin(math.radians(aircraft.pitch))
            self.target_z = aircraft.z + 1000 * math.sin(math.radians(aircraft.yaw))
            
        elif self.mode == "external":
            # External fixed camera
            self.x = aircraft.x + 300
            self.y = aircraft.y + 100
            self.z = aircraft.z + 300
            
            self.target_x = aircraft.x
            self.target_y = aircraft.y
            self.target_z = aircraft.z

class Terrain:
    def __init__(self):
        self.height_map = {}
        self.airports = []
        self.generate_terrain()
        self.generate_airports()
    
    def generate_terrain(self):
        """Generate procedural terrain"""
        for x in range(-10000, 10000, 500):
            for z in range(-10000, 10000, 500):
                # Simple Perlin-like noise
                height = 0
                height += 100 * math.sin(x * 0.0001) * math.cos(z * 0.0001)
                height += 50 * math.sin(x * 0.0003) * math.cos(z * 0.0003)
                height += 25 * math.sin(x * 0.001) * math.cos(z * 0.001)
                self.height_map[(x, z)] = max(0, height)
    
    def generate_airports(self):
        """Generate airports"""
        airport_locations = [
            (0, 0, 0, "MAIN AIRPORT"),
            (5000, 3000, 150, "MOUNTAIN FIELD"),
            (-3000, -4000, 50, "COASTAL STRIP"),
            (8000, -2000, 300, "HIGHLAND BASE")
        ]
        
        for x, z, elevation, name in airport_locations:
            airport = {
                'x': x, 'z': z, 'elevation': elevation, 'name': name,
                'runway_length': random.randint(1500, 3500),
                'runway_width': random.randint(30, 60),
                'runway_heading': random.randint(0, 359),
                'has_ils': random.choice([True, False]),
                'has_lights': True
            }
            self.airports.append(airport)
    
    def get_height_at(self, x, z):
        """Get terrain height at position"""
        # Find nearest height map point
        grid_x = round(x / 500) * 500
        grid_z = round(z / 500) * 500
        return self.height_map.get((grid_x, grid_z), 0)

class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        self.large_font = pygame.font.Font(None, 36)
        
    def world_to_screen(self, world_x, world_y, world_z, camera):
        """Convert 3D world coordinates to 2D screen coordinates"""
        # Simple perspective projection
        dx = world_x - camera.x
        dy = world_y - camera.y
        dz = world_z - camera.z
        
        # Camera transformation
        distance = math.sqrt(dx**2 + dy**2 + dz**2)
        if distance < 1:
            return None
        
        # Project to screen
        screen_x = WIDTH // 2 + dx * 200 / max(1, dz + 200)
        screen_y = HEIGHT // 2 - dy * 200 / max(1, dz + 200)
        
        return (int(screen_x), int(screen_y))
    
    def draw_horizon(self, camera):
        """Draw horizon line and sky gradient"""
        # Sky gradient
        for y in range(HEIGHT // 2):
            color_intensity = y / (HEIGHT // 2)
            sky_color = (
                int(BLUE[0] * (1 - color_intensity) + WHITE[0] * color_intensity),
                int(BLUE[1] * (1 - color_intensity) + WHITE[1] * color_intensity),
                int(BLUE[2] * (1 - color_intensity) + WHITE[2] * color_intensity)
            )
            pygame.draw.line(self.screen, sky_color, (0, y), (WIDTH, y))
        
        # Ground
        pygame.draw.rect(self.screen, GREEN, (0, HEIGHT // 2, WIDTH, HEIGHT // 2))
        
        # Horizon line
        pygame.draw.line(self.screen, WHITE, (0, HEIGHT // 2), (WIDTH, HEIGHT // 2), 2)
    
    def draw_aircraft(self, aircraft: Aircraft, camera):
        """Draw aircraft"""
        pos = self.world_to_screen(aircraft.x, aircraft.y, aircraft.z, camera)
        if not pos:
            return
        
        screen_x, screen_y = pos
        
        # Aircraft body (simplified)
        size = 10
        if camera.mode == "cockpit":
            # Don't draw aircraft in cockpit view
            return
        
        # Aircraft color based on type
        colors = {
            AircraftType.FIGHTER: RED,
            AircraftType.AIRLINER: WHITE,
            AircraftType.GLIDER: YELLOW,
            AircraftType.HELICOPTER: DARK_GREEN,
            AircraftType.CARGO: GRAY,
            AircraftType.ULTRALIGHT: ORANGE
        }
        color = colors.get(aircraft.type, WHITE)
        
        # Draw aircraft body
        pygame.draw.circle(self.screen, color, (screen_x, screen_y), size)
        
        # Draw aircraft orientation
        nose_x = screen_x + size * 2 * math.cos(math.radians(aircraft.yaw))
        nose_y = screen_y + size * 2 * math.sin(math.radians(aircraft.yaw))
        pygame.draw.line(self.screen, BLACK, (screen_x, screen_y), (nose_x, nose_y), 3)
        
        # Smoke trail if engine problems
        if not aircraft.engine_on or any(h < 50 for h in aircraft.engine_health):
            for i in range(5):
                trail_x = screen_x - i * 5
                trail_y = screen_y + random.randint(-2, 2)
                pygame.draw.circle(self.screen, DARK_GRAY, (trail_x, trail_y), 2)
    
    def draw_terrain(self, camera, terrain):
        """Draw terrain features"""
        # Draw airports
        for airport in terrain.airports:
            pos = self.world_to_screen(airport['x'], airport['elevation'], airport['z'], camera)
            if pos:
                screen_x, screen_y = pos
                
                # Airport symbol
                pygame.draw.rect(self.screen, GRAY, (screen_x - 20, screen_y - 5, 40, 10))
                
                # Airport name
                text = self.small_font.render(airport['name'], True, WHITE)
                self.screen.blit(text, (screen_x - text.get_width() // 2, screen_y - 25))
    
    def draw_weather_effects(self, weather):
        """Draw weather effects"""
        if weather.type == WeatherType.RAIN or weather.type == WeatherType.STORM:
            # Rain drops
            for _ in range(int(weather.precipitation * 20)):
                x = random.randint(0, WIDTH)
                y = random.randint(0, HEIGHT)
                pygame.draw.line(self.screen, BLUE, (x, y), (x + 2, y + 8), 1)
        
        elif weather.type == WeatherType.SNOW:
            # Snow flakes
            for _ in range(int(weather.precipitation * 15)):
                x = random.randint(0, WIDTH)
                y = random.randint(0, HEIGHT)
                pygame.draw.circle(self.screen, WHITE, (x, y), 2)
        
        elif weather.type == WeatherType.FOG:
            # Fog overlay
            fog_surface = pygame.Surface((WIDTH, HEIGHT))
            fog_surface.set_alpha(int(255 * (1 - weather.visibility / 1000)))
            fog_surface.fill(LIGHT_GRAY)
            self.screen.blit(fog_surface, (0, 0))
        
        # Lightning
        for strike in weather.lightning_strikes:
            x = random.randint(WIDTH // 4, 3 * WIDTH // 4)
            y = random.randint(0, HEIGHT // 2)
            for _ in range(3):
                end_x = x + random.randint(-50, 50)
                end_y = y + random.randint(50, 200)
                pygame.draw.line(self.screen, YELLOW, (x, y), (end_x, end_y), 3)
    
    def draw_hud(self, aircraft: Aircraft, weather: Weather):
        """Draw heads-up display"""
        # Flight instruments background
        pygame.draw.rect(self.screen, (0, 0, 0, 128), (10, 10, 300, 200))
        
        # Speed
        speed = math.sqrt(aircraft.vx**2 + aircraft.vy**2 + aircraft.vz**2)
        speed_text = f"Speed: {speed:.0f} kt"
        text = self.font.render(speed_text, True, WHITE)
        self.screen.blit(text, (20, 20))
        
        # Altitude
        alt_text = f"Altitude: {aircraft.y:.0f} ft"
        text = self.font.render(alt_text, True, WHITE)
        self.screen.blit(text, (20, 45))
        
        # Heading
        heading_text = f"Heading: {aircraft.yaw:.0f}°"
        text = self.font.render(heading_text, True, WHITE)
        self.screen.blit(text, (20, 70))
        
        # Throttle
        throttle_text = f"Throttle: {aircraft.thrust:.0f}%"
        text = self.font.render(throttle_text, True, WHITE)
        self.screen.blit(text, (20, 95))
        
        # Fuel
        fuel_text = f"Fuel: {aircraft.fuel:.0f} gal"
        fuel_color = RED if aircraft.fuel < aircraft.config.fuel_capacity * 0.1 else WHITE
        text = self.font.render(fuel_text, True, fuel_color)
        self.screen.blit(text, (20, 120))
        
        # G-Force
        g_text = f"G-Force: {aircraft.current_g_force:.1f}g"
        g_color = RED if aircraft.current_g_force > aircraft.max_g_force * 0.8 else WHITE
        text = self.font.render(g_text, True, g_color)
        self.screen.blit(text, (20, 145))
        
        # Weather info
        weather_text = f"Weather: {weather.type.value}"
        text = self.font.render(weather_text, True, WHITE)
        self.screen.blit(text, (20, 170))
        
        # Wind
        wind_text = f"Wind: {weather.wind_speed:.0f} kt @ {weather.wind_direction:.0f}°"
        text = self.small_font.render(wind_text, True, WHITE)
        self.screen.blit(text, (20, 195))
        
        # Warnings
        warning_y = 250
        if aircraft.stall_warning:
            warning = self.font.render("STALL WARNING", True, RED)
            self.screen.blit(warning, (20, warning_y))
            warning_y += 25
        
        if aircraft.overspeed_warning:
            warning = self.font.render("OVERSPEED", True, RED)
            self.screen.blit(warning, (20, warning_y))
            warning_y += 25
        
        if not aircraft.engine_on:
            warning = self.font.render("ENGINE FAILURE", True, RED)
            self.screen.blit(warning, (20, warning_y))
            warning_y += 25
        
        if aircraft.fuel <= 0:
            warning = self.font.render("FUEL EMPTY", True, RED)
            self.screen.blit(warning, (20, warning_y))
        
        # Autopilot status
        if aircraft.autopilot:
            ap_text = "AUTOPILOT ON"
            text = self.font.render(ap_text, True, GREEN)
            self.screen.blit(text, (WIDTH - 150, 20))
        
        # Navigation info
        if aircraft.waypoints and aircraft.current_waypoint < len(aircraft.waypoints):
            wp = aircraft.waypoints[aircraft.current_waypoint]
            dx = wp.x - aircraft.x
            dz = wp.z - aircraft.z
            distance = math.sqrt(dx**2 + dz**2)
            bearing = math.degrees(math.atan2(dz, dx))
            
            nav_text = f"Next WP: {wp.name}"
            text = self.small_font.render(nav_text, True, WHITE)
            self.screen.blit(text, (WIDTH - 200, 50))
            
            dist_text = f"Distance: {distance:.0f} nm"
            text = self.small_font.render(dist_text, True, WHITE)
            self.screen.blit(text, (WIDTH - 200, 70))
            
            bearing_text = f"Bearing: {bearing:.0f}°"
            text = self.small_font.render(bearing_text, True, WHITE)
            self.screen.blit(text, (WIDTH - 200, 90))
        
        # Performance stats
        stats_text = [
            f"Flight Time: {aircraft.flight_time:.0f}s",
            f"Distance: {aircraft.distance_traveled/1000:.1f} nm",
            f"Max Alt: {aircraft.max_altitude_reached:.0f} ft",
            f"Max Speed: {aircraft.max_speed_reached:.0f} kt"
        ]
        
        for i, stat in enumerate(stats_text):
            text = self.small_font.render(stat, True, WHITE)
            self.screen.blit(text, (WIDTH - 200, HEIGHT - 100 + i * 20))

class FlightSimulator:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Advanced Flight Simulator")
        self.clock = pygame.time.Clock()
        
        # Initialize components
        self.aircraft = Aircraft(0, 1000, 0, AircraftType.AIRLINER)
        self.weather = Weather()
        self.camera = Camera()
        self.terrain = Terrain()
        self.renderer = Renderer(self.screen)
        self.sound_manager = SoundManager()
        
        # Game state
        self.paused = False
        self.show_help = False
        self.mission_type = MissionType.FREE_FLIGHT
        
        # Add some waypoints for testing
        self.aircraft.waypoints = [
            Waypoint(2000, 2000, 2000, "WP1"),
            Waypoint(4000, 1000, 1500, "WP2"),
            Waypoint(5000, 3000, 500, "MOUNTAIN FIELD", "AIRPORT")
        ]
        
    def handle_input(self):
        """Handle keyboard and mouse input"""
        keys = pygame.key.get_pressed()
        
        # Flight controls
        if keys[pygame.K_w]:
            self.aircraft.pitch = max(-45, self.aircraft.pitch - 1)
        if keys[pygame.K_s]:
            self.aircraft.pitch = min(45, self.aircraft.pitch + 1)
        if keys[pygame.K_a]:
            self.aircraft.roll = max(-45, self.aircraft.roll - 1)
        if keys[pygame.K_d]:
            self.aircraft.roll = min(45, self.aircraft.roll + 1)
        if keys[pygame.K_q]:
            self.aircraft.yaw = (self.aircraft.yaw - 1) % 360
        if keys[pygame.K_e]:
            self.aircraft.yaw = (self.aircraft.yaw + 1) % 360
        
        # Throttle
        if keys[pygame.K_LSHIFT]:
            self.aircraft.thrust = min(100, self.aircraft.thrust + 1)
        if keys[pygame.K_LCTRL]:
            self.aircraft.thrust = max(0, self.aircraft.thrust - 1)
        
        # Landing gear
        if keys[pygame.K_g]:
            self.aircraft.gear_down = not self.aircraft.gear_down
        
        # Flaps
        if keys[pygame.K_f]:
            self.aircraft.flaps = min(40, self.aircraft.flaps + 1)
        if keys[pygame.K_v]:
            self.aircraft.flaps = max(0, self.aircraft.flaps - 1)
        
        # Spoilers
        if keys[pygame.K_b]:
            self.aircraft.spoilers = 100 if self.aircraft.spoilers == 0 else 0
        
        # Brakes
        if keys[pygame.K_SPACE]:
            self.aircraft.brakes = 100
        else:
            self.aircraft.brakes = 0
        
        # Camera controls
        if keys[pygame.K_1]:
            self.camera.mode = "follow"
        if keys[pygame.K_2]:
            self.camera.mode = "cockpit"
        if keys[pygame.K_3]:
            self.camera.mode = "external"
        
        # Autopilot
        if keys[pygame.K_TAB]:
            self.aircraft.autopilot = not self.aircraft.autopilot
            if self.aircraft.autopilot:
                self.aircraft.target_altitude = self.aircraft.y
                self.aircraft.target_heading = self.aircraft.yaw
                self.aircraft.target_speed = math.sqrt(
                    self.aircraft.vx**2 + self.aircraft.vy**2 + self.aircraft.vz**2
                )
        
        # Navigation
        if keys[pygame.K_n]:
            self.aircraft.nav_mode = not self.aircraft.nav_mode
        
        # Reset aircraft
        if keys[pygame.K_r]:
            self.aircraft = Aircraft(0, 1000, 0, self.aircraft.type)
    
    def update(self, dt):
        """Update game state"""
        if not self.paused:
            self.aircraft.update(dt, self.weather)
            self.weather.update(dt)
            self.camera.update(self.aircraft, dt)
            
            # Sound effects
            self.sound_manager.play_engine_sound(self.aircraft.thrust)
            
            if self.aircraft.stall_warning or self.aircraft.overspeed_warning:
                self.sound_manager.play_warning_sound()
    
    def render(self):
        """Render the game"""
        # Clear screen
        self.screen.fill(BLACK)
        
        # Draw world
        self.renderer.draw_horizon(self.camera)
        self.renderer.draw_terrain(self.camera, self.terrain)
        self.renderer.draw_aircraft(self.aircraft, self.camera)
        self.renderer.draw_weather_effects(self.weather)
        
        # Draw HUD
        self.renderer.draw_hud(self.aircraft, self.weather)
        
        # Help text
        if self.show_help:
            help_texts = [
                "WASD - Pitch/Roll", "QE - Yaw", "Shift/Ctrl - Throttle",
                "G - Gear", "F/V - Flaps", "B - Spoilers", "Space - Brakes",
                "Tab - Autopilot", "N - Navigation", "123 - Camera", "R - Reset"
            ]
            for i, text in enumerate(help_texts):
                rendered = self.renderer.small_font.render(text, True, WHITE)
                self.screen.blit(rendered, (WIDTH - 200, 200 + i * 20))
        
        # Crash message
        if self.aircraft.crashed:
            crash_text = self.renderer.large_font.render("AIRCRAFT CRASHED", True, RED)
            text_rect = crash_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
            self.screen.blit(crash_text, text_rect)
        
        pygame.display.flip()
    
    def run(self):
        """Main game loop"""
        running = True
        
        while running:
            dt = self.clock.tick(FPS) / 1000.0  # Delta time in seconds
            
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_p:
                        self.paused = not self.paused
                    elif event.key == pygame.K_h:
                        self.show_help = not self.show_help
                    elif event.key == pygame.K_c:
                        # Change aircraft type
                        types = list(AircraftType)
                        current_index = types.index(self.aircraft.type)
                        new_type = types[(current_index + 1) % len(types)]
                        old_pos = (self.aircraft.x, self.aircraft.y, self.aircraft.z)
                        self.aircraft = Aircraft(old_pos[0], old_pos[1], old_pos[2], new_type)
                    elif event.key == pygame.K_m:
                        # Change weather
                        self.weather.type = random.choice(list(WeatherType))
                        self.weather.update_conditions()
            
            # Handle continuous input
            self.handle_input()
            
            # Update game
            self.update(dt)
            
            # Render
            self.render()
        
        pygame.quit()

if __name__ == "__main__":
    game = FlightSimulator()
    game.run()