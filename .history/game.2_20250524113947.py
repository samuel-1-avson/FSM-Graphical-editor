import pygame
import math
import random
import numpy as np
# import json # Not strictly used, can be removed if no file I/O
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import time

# Initialize Pygame
pygame.init()
pygame.mixer.init() # Initialize the mixer

# Constants
WIDTH, HEIGHT = 1600, 1000
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (135, 206, 235)
DARK_BLUE = (0, 102, 204)
GREEN = (34, 139, 34)
DARK_GREEN = (0, 100, 0)
BROWN = (165, 42, 42)
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
HUD_GREEN = (0, 255, 0)
HUD_AMBER = (255, 191, 0)

# Game States
class GameState(Enum):
    MENU = 0
    PLAYING = 1
    PAUSED = 2
    DEBRIEF = 3

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
    drag_coefficient_base: float
    lift_coefficient_max: float
    wing_area: float
    aspect_ratio: float
    max_speed: float
    fuel_capacity: float
    fuel_consumption: float
    max_altitude: float
    turn_rate: float
    stall_speed_clean: float
    service_ceiling: float
    max_g_force: float
    climb_rate: float
    engine_count: int = 1
    critical_aoa_positive: float = 15.0
    critical_aoa_negative: float = -12.0
    cl_alpha: float = 2 * math.pi * 0.08
    engine_spool_rate: float = 0.2

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
        self.sounds: Dict[str, Optional[pygame.mixer.Sound]] = {}
        self.engine_channel: Optional[pygame.mixer.Channel] = None
        self.warning_channel: Optional[pygame.mixer.Channel] = None
        self.ambient_channel: Optional[pygame.mixer.Channel] = None
        self.enabled = False # Sounds disabled by default now
        # self.load_sounds() # Don't load external files

    def load_sounds(self): # Kept for structure, but does nothing now
        # sound_files = {
        #     'stall_warning': "stall_warning.wav",
        #     'gear_up': "gear_up.wav",
        #     'gear_down': "gear_down.wav",
        #     'click': "click.wav"
        # }
        # for name, filename in sound_files.items():
        #     try:
        #         self.sounds[name] = pygame.mixer.Sound(filename)
        #     except pygame.error as e:
        #         print(f"Skipping sound file {filename}: {e}") # Changed to skip
        #         self.sounds[name] = None
        pass


    def create_synthetic_sound(self, frequency, duration=0.1, volume=0.1, shape='sine'):
        if not self.enabled or not pygame.mixer.get_init(): return None
        # ... (synthetic sound creation can be kept if you want to re-enable later) ...
        # For now, let's make it return None to avoid issues if called
        return None

    def play_engine_sound(self, rpm_percent, engine_type=AircraftType.AIRLINER):
        if not self.enabled: return
        # ... (engine sound logic commented out) ...
        pass

    def play_sound(self, sound_name, loops=0):
        if not self.enabled: return
        # ... (play specific sound logic commented out) ...
        # if sound_name == 'stall_warning': # Can still call warning beep if needed
        #     self.play_warning_beep()
        pass

    def play_warning_beep(self, frequency=800, duration=0.2, volume=0.3):
        if not self.enabled: return
        # ... (warning beep logic commented out, or use a very simple placeholder if needed) ...
        pass

    def stop_all_sounds(self):
        if not pygame.mixer.get_init(): return
        if self.engine_channel: self.engine_channel.stop()
        if self.warning_channel: self.warning_channel.stop()
        if self.ambient_channel: self.ambient_channel.stop()
        # pygame.mixer.stop() # This might be too broad if other sounds are desired later

# Weather Class ( unchanged from previous version)
class Weather:
    def __init__(self):
        self.type = WeatherType.CLEAR
        self.wind_speed = 5 # knots
        self.wind_direction = 270 # Degrees from North
        self.wind_gusts = 0 # knots
        self.visibility = 15000 # meters
        self.cloud_ceiling = 10000 # meters
        self.cloud_layers: List[Dict] = []
        self.temperature = 15 # Celsius at sea level
        self.pressure = 1013.25 # hPa
        self.humidity = 50 # Percent
        self.turbulence = 0 # 0-10 scale
        self.precipitation = 0 # 0-10 scale
        self.lightning_strikes: List[Dict] = []
        self.icing_intensity = 0 # 0-10 scale
        self.wind_shear_altitude = 0 # meters
        self.wind_shear_strength = 0 # knots speed difference

        self.cloud_particles: List[Dict] = []

        self.generate_clouds()
        self.update_conditions()

    def generate_clouds(self):
        self.cloud_layers = []
        if self.type in [WeatherType.CLOUDY, WeatherType.STORM, WeatherType.RAIN, WeatherType.SNOW, WeatherType.FOG]:
            num_layers = random.randint(1, 3)
            for _ in range(num_layers):
                layer = {
                    'altitude': random.randint(500, 8000),
                    'thickness': random.randint(200, 1500),
                    'coverage': random.uniform(0.3, 0.9),
                    'type': random.choice(['cumulus', 'stratus', 'cumulonimbus'])
                }
                self.cloud_layers.append(layer)
        self.generate_cloud_particles()

    def generate_cloud_particles(self):
        self.cloud_particles = []
        if self.type in [WeatherType.CLOUDY, WeatherType.STORM, WeatherType.RAIN, WeatherType.SNOW, WeatherType.FOG]:
            for layer in self.cloud_layers:
                for _ in range(int(layer['coverage'] * 20)): 
                    particle = {
                        'x': random.uniform(-15000, 15000),
                        'z': random.uniform(-15000, 15000),
                        'y': layer['altitude'] + random.uniform(-layer['thickness']/2, layer['thickness']/2),
                        'size': random.uniform(200, 800) * layer['coverage'],
                        'opacity': random.uniform(30, 120) * layer['coverage']
                    }
                    self.cloud_particles.append(particle)

    def update(self, dt):
        if random.random() < 0.0002:
            if self.type != WeatherType.STORM:
                old_type = self.type
                self.type = random.choice(list(WeatherType))
                if self.type != old_type:
                    print(f"Weather changing from {old_type.value} to {self.type.value}")
                    self.generate_clouds()
                self.update_conditions()

        if random.random() < 0.01:
            self.wind_gusts = random.uniform(0, self.wind_speed * 0.6)
        else:
            self.wind_gusts *= (1 - 0.5 * dt)

        if self.type == WeatherType.STORM and random.random() < 0.008:
            self.lightning_strikes.append({
                'x': random.uniform(-15000, 15000),
                'z': random.uniform(-15000, 15000),
                'intensity': random.uniform(0.7, 1.0),
                'time': time.time()
            })

        current_time = time.time()
        self.lightning_strikes = [s for s in self.lightning_strikes if current_time - s['time'] < 0.25]

    def update_conditions(self):
        self.visibility = random.uniform(12000, 20000)
        self.wind_speed = random.uniform(0, 15)
        self.turbulence = random.uniform(0, 2)
        self.precipitation = 0
        self.icing_intensity = 0
        self.temperature = 15
        self.humidity = 50
        self.cloud_ceiling = 10000

        if self.type == WeatherType.CLEAR: pass
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
            self.cloud_ceiling = random.uniform(500, 2000)
        elif self.type == WeatherType.STORM:
            self.visibility = random.uniform(500, 2000)
            self.wind_speed = random.uniform(25, 50)
            self.turbulence = random.uniform(7, 10)
            self.precipitation = random.uniform(7, 10)
            self.humidity = 95
            self.cloud_ceiling = random.uniform(300, 1500)
        elif self.type == WeatherType.FOG:
            self.visibility = random.uniform(50, 800)
            self.wind_speed = random.uniform(0, 8)
            self.turbulence = random.uniform(0, 2)
            self.humidity = random.uniform(95, 100)
            self.cloud_ceiling = random.uniform(0, 300)
        elif self.type == WeatherType.SNOW:
            self.visibility = random.uniform(1000, 4000)
            self.wind_speed = random.uniform(5, 25)
            self.turbulence = random.uniform(2, 5)
            self.precipitation = random.uniform(2, 6)
            self.temperature = random.uniform(-15, 0)
            self.humidity = random.uniform(70, 90)
            self.cloud_ceiling = random.uniform(300, 2000)
        elif self.type == WeatherType.WIND_SHEAR:
            self.wind_shear_altitude = random.uniform(500, 3000)
            self.wind_shear_strength = random.uniform(15, 35)
            self.turbulence = random.uniform(4, 7)
        elif self.type == WeatherType.ICING:
            self.icing_intensity = random.uniform(3, 8)
            self.temperature = random.uniform(-10, 2)
            self.humidity = random.uniform(85, 100)
            self.cloud_ceiling = random.uniform(500, 3000)
            self.visibility = random.uniform(3000, 8000)

        self.wind_direction = random.uniform(0, 360)
        self.pressure = random.uniform(995, 1030)

# Aircraft Class ( unchanged from previous version)
class Aircraft:
    def __init__(self, x, y, z, aircraft_type: AircraftType):
        self.x = x
        self.y = y
        self.z = z
        
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
        
        self.pitch = 0.0
        self.yaw = 0.0
        self.roll = 0.0

        self.pitch_rate = 0.0
        self.yaw_rate = 0.0
        self.roll_rate = 0.0

        self.thrust_input = 0.0 # %
        self.engine_rpm_percent = 0.0 # %

        self.crashed = False
        self.on_ground = (y <= 0.1)
        self.gear_down = True
        self.flaps_setting = 0
        self.flaps_max_setting = 3
        self.flaps_degrees = [0, 10, 25, 40]
        self.spoilers_deployed = False
        self.brakes_input = 0.0
        
        self.autopilot_on = False
        self.ap_target_altitude: Optional[float] = None
        self.ap_target_heading: Optional[float] = None
        self.ap_target_speed: Optional[float] = None
        
        self.engine_on = True
        
        self.configs = {
            AircraftType.FIGHTER: AircraftConfig("F-16", 120000, 8500, 0.016, 1.6, 30, 8, 650, 3000, 0.1, 18000, 15, 70, 15000, 9.0, 250, engine_count=1, critical_aoa_positive=20.0, cl_alpha=0.11, engine_spool_rate=0.5),
            AircraftType.AIRLINER: AircraftConfig("B737", 110000, 75000, 0.020, 1.5, 125, 9, 280, 26000, 0.06, 14000, 3, 65, 12500, 2.5, 150, engine_count=2, critical_aoa_positive=16.0, cl_alpha=0.1, engine_spool_rate=0.15),
            AircraftType.GLIDER: AircraftConfig("ASK-21", 0, 600, 0.010, 1.8, 17, 26, 70, 0, 0, 10000, 4, 30, 8000, 4.5, 20, engine_count=0, critical_aoa_positive=14.0, cl_alpha=0.1),
            AircraftType.CARGO: AircraftConfig("C-130", 4 * 15000, 70000, 0.028, 1.2, 160, 7, 180, 20000, 0.09, 10000, 2, 55, 9000, 2.0, 100, engine_count=4, critical_aoa_positive=15.0, cl_alpha=0.09, engine_spool_rate=0.1),
            AircraftType.ULTRALIGHT: AircraftConfig("Quicksilver", 3000, 250, 0.030, 1.4, 15, 10, 30, 50, 0.12, 3000, 5, 20, 2500, 3.0, 20, engine_count=1, critical_aoa_positive=18.0, cl_alpha=0.09, engine_spool_rate=0.3),
            AircraftType.HELICOPTER: AircraftConfig("UH-60", 2*1200, 5200, 0.06, 0.4, 20, 5, 80, 1300, 0.15, 6000, 10, 0, 5800, 3.5, 50, engine_count=2, critical_aoa_positive=90.0, cl_alpha=0.05),
        }
        
        self.type = aircraft_type
        self.config = self.configs[aircraft_type]
        self.fuel = self.config.fuel_capacity
        self.engines_failed = [False] * self.config.engine_count
        
        self.waypoints: List[Waypoint] = []
        self.current_waypoint_index = 0
        self.nav_mode_active = False
        
        self.electrical_power = True
        self.hydraulic_power = True
        self.avionics_power = True
        self.engine_health = [100.0] * self.config.engine_count
        self.structural_integrity = 100.0
        self.ice_buildup_kg = 0.0
        self.pitot_heat_on = False
        
        self.current_g_force = 1.0
        self.aoa_degrees = 0.0
        self.stall_warning_active = False
        self.overspeed_warning_active = False
        
        self.flight_time_sec = 0.0
        self.distance_traveled_m = 0.0
        self.max_altitude_reached = y
        self.max_speed_reached = 0.0
        
        self.touchdown_vertical_speed_mps = 0.0
        self.landing_score = 0.0
        self.landed_successfully = False

        self.pitch_trim = 0.0

        self.elevator_effectiveness = 1.0
        self.aileron_effectiveness = 1.0
        self.rudder_effectiveness = 1.0

        fuselage_length = 15 if aircraft_type in [AircraftType.AIRLINER, AircraftType.CARGO] else 10
        fuselage_radius = 1.8 if aircraft_type in [AircraftType.AIRLINER, AircraftType.CARGO] else 1.2
        wing_span_mult = 1.0
        if aircraft_type == AircraftType.GLIDER: wing_span_mult = 1.5
        if aircraft_type == AircraftType.FIGHTER: wing_span_mult = 0.8
        wing_span = (18 if aircraft_type == AircraftType.AIRLINER else 12) * wing_span_mult
        wing_chord = (wing_span / self.config.aspect_ratio) if self.config.aspect_ratio > 0 else 2.0
        tail_height = 3.5 if aircraft_type == AircraftType.AIRLINER else 2.5
        
        self.model_vertices_local = [
            (fuselage_radius, -fuselage_radius, fuselage_length * 0.6), (fuselage_radius, fuselage_radius, fuselage_length * 0.6),
            (-fuselage_radius, fuselage_radius, fuselage_length * 0.6), (-fuselage_radius, -fuselage_radius, fuselage_length * 0.6), 
            (fuselage_radius, -fuselage_radius, -fuselage_length * 0.4), (fuselage_radius, fuselage_radius, -fuselage_length * 0.4),
            (-fuselage_radius, fuselage_radius, -fuselage_length * 0.4), (-fuselage_radius, -fuselage_radius, -fuselage_length * 0.4), 
            (wing_span/2, 0, wing_chord/2), (wing_span/2, 0, -wing_chord/2), 
            (-wing_span/2, 0, wing_chord/2), (-wing_span/2, 0, -wing_chord/2),
            (fuselage_radius *0.8, 0, wing_chord/2), (fuselage_radius*0.8, 0, -wing_chord/2), 
            (-fuselage_radius*0.8, 0, wing_chord/2), (-fuselage_radius*0.8, 0, -wing_chord/2),
            (0, tail_height, -fuselage_length*0.35), (0, 0, -fuselage_length*0.35), (0,0,-fuselage_length*0.45 + wing_chord*0.2), 
            (wing_span/3.5, 0, -fuselage_length*0.38), (-wing_span/3.5, 0, -fuselage_length*0.38), 
            (0, 0, -fuselage_length*0.30) 
        ]
        self.model_lines = [
            (0,1), (1,2), (2,3), (3,0), (4,5), (5,6), (6,7), (7,4), 
            (0,4), (1,5), (2,6), (3,7), 
            (8,12), (9,13), (12,13), (8,9), 
            (10,14), (11,15), (14,15), (10,11), 
            (12,14), (13,15), 
            (16,17), (17,18), (18,16), 
            (19,21), (20,21), (19,20) 
        ]
        
    def get_current_mass(self):
        return self.config.mass + (self.fuel * 0.8) + self.ice_buildup_kg

    def get_flaps_deflection(self):
        return self.flaps_degrees[self.flaps_setting]

    def update_engine_rpm(self, dt):
        diff = self.thrust_input - self.engine_rpm_percent
        change = self.config.engine_spool_rate * 100 * dt
        
        if abs(diff) < change:
            self.engine_rpm_percent = self.thrust_input
        else:
            self.engine_rpm_percent += math.copysign(change, diff)
        self.engine_rpm_percent = np.clip(self.engine_rpm_percent, 0, 100)

        if self.type != AircraftType.GLIDER and self.engine_on:
            idle_rpm = 20 if self.type == AircraftType.AIRLINER else 25
            if self.thrust_input < idle_rpm :
                 self.engine_rpm_percent = max(idle_rpm, self.engine_rpm_percent) if self.fuel > 0 else 0
            if self.thrust_input == 0 and self.engine_rpm_percent < idle_rpm and self.fuel > 0:
                self.engine_rpm_percent = idle_rpm

    def calculate_aerodynamics(self, air_density, current_speed_mps, weather: Weather):
        q = 0.5 * air_density * current_speed_mps**2

        if current_speed_mps > 1:
            horizontal_speed = math.sqrt(self.vx**2 + self.vz**2)
            if horizontal_speed > 0.1:
                 flight_path_angle_rad = math.atan2(self.vy, horizontal_speed)
                 self.aoa_degrees = self.pitch - math.degrees(flight_path_angle_rad)
            else:
                 self.aoa_degrees = self.pitch - math.copysign(90, self.vy) if abs(self.vy) > 0.1 else self.pitch
        else:
            self.aoa_degrees = self.pitch
        
        self.aoa_degrees = np.clip(self.aoa_degrees, -30, 30)

        cl = 0.0
        cl_from_aoa = self.config.cl_alpha * self.aoa_degrees
        
        if self.aoa_degrees > self.config.critical_aoa_positive:
            self.stall_warning_active = True
            overshoot = self.aoa_degrees - self.config.critical_aoa_positive
            cl = self.config.lift_coefficient_max - overshoot * 0.05
            cl = max(0.1, cl)
        elif self.aoa_degrees < self.config.critical_aoa_negative:
            self.stall_warning_active = True
            overshoot = abs(self.aoa_degrees - self.config.critical_aoa_negative)
            cl = -self.config.lift_coefficient_max + overshoot * 0.05
            cl = min(-0.1, cl)
        else:
            self.stall_warning_active = False
            cl = cl_from_aoa
        
        cl_flaps = (self.get_flaps_deflection() / 40.0) * 0.7
        cl += cl_flaps
        cl = np.clip(cl, -self.config.lift_coefficient_max -0.4, self.config.lift_coefficient_max + 0.4)

        cd_base = self.config.drag_coefficient_base
        cd_induced = (cl**2) / (math.pi * 0.75 * self.config.aspect_ratio) if self.config.aspect_ratio > 0 else 0
        
        cd_flaps = (self.get_flaps_deflection() / 40.0)**1.5 * 0.06
        cd_gear = 0.020 if self.gear_down else 0.002
        cd_spoilers = 0.08 if self.spoilers_deployed else 0.0
        cd_ice = self.ice_buildup_kg * 0.0002

        cd_total = cd_base + cd_induced + cd_flaps + cd_gear + cd_spoilers + cd_ice

        lift_force = cl * q * self.config.wing_area
        drag_force = cd_total * q * self.config.wing_area

        if self.spoilers_deployed:
            lift_force *= 0.65

        effectiveness_factor = np.clip(q / (0.5 * 1.225 * (self.config.stall_speed_clean*1.5)**2), 0.1, 1.0)
        self.elevator_effectiveness = effectiveness_factor
        self.aileron_effectiveness = effectiveness_factor
        self.rudder_effectiveness = effectiveness_factor

        return lift_force, drag_force

    def apply_forces_and_torques(self, dt, lift, drag, thrust_force, weather, current_speed_mps):
        current_mass = self.get_current_mass()
        gravity_force_y = -9.81 * current_mass

        p_rad, y_rad, r_rad = math.radians(self.pitch), math.radians(self.yaw), math.radians(self.roll)
        
        cos_p, sin_p = math.cos(p_rad), math.sin(p_rad)
        cos_y, sin_y = math.cos(y_rad), math.sin(y_rad)
        cos_r, sin_r = math.cos(r_rad), math.sin(r_rad)

        body_z_x = cos_p * sin_y
        body_z_y = sin_p
        body_z_z = cos_p * cos_y

        thrust_fx = thrust_force * body_z_x
        thrust_fy = thrust_force * body_z_y
        thrust_fz = thrust_force * body_z_z
        
        lift_fx = lift * (cos_r * sin_p * sin_y - sin_r * cos_y)
        lift_fy = lift * (cos_r * cos_p)
        lift_fz = lift * (cos_r * sin_p * cos_y + sin_r * sin_y)

        if current_speed_mps > 0.1:
            drag_fx = -drag * (self.vx / current_speed_mps)
            drag_fy = -drag * (self.vy / current_speed_mps)
            drag_fz = -drag * (self.vz / current_speed_mps)
        else:
            drag_fx, drag_fy, drag_fz = 0,0,0
        
        wind_effect_x = weather.wind_speed * 0.5144 * math.cos(math.radians(weather.wind_direction))
        wind_effect_z = weather.wind_speed * 0.5144 * math.sin(math.radians(weather.wind_direction))
        wind_accel_x = (wind_effect_x - self.vx) * 0.05
        wind_accel_z = (wind_effect_z - self.vz) * 0.05
        
        total_fx = thrust_fx + drag_fx + lift_fx
        total_fy = thrust_fy + drag_fy + lift_fy + gravity_force_y
        total_fz = thrust_fz + drag_fz + lift_fz

        damping_factor_pitch = 0.8 + self.elevator_effectiveness * 0.5
        damping_factor_roll = 1.0 + self.aileron_effectiveness * 0.8
        damping_factor_yaw = 0.5 + self.rudder_effectiveness * 0.3

        self.pitch_rate *= (1 - damping_factor_pitch * dt * abs(self.pitch_rate) * 0.1)
        self.roll_rate *= (1 - damping_factor_roll * dt * abs(self.roll_rate) * 0.1)
        self.yaw_rate *= (1 - damping_factor_yaw * dt * abs(self.yaw_rate) * 0.1)

        self.pitch += self.pitch_rate * dt
        self.roll += self.roll_rate * dt
        self.yaw = (self.yaw + self.yaw_rate * dt + 360) % 360

        self.pitch = np.clip(self.pitch, -90, 90)
        self.roll = ((self.roll + 180) % 360) - 180

        ax = total_fx / current_mass
        ay = total_fy / current_mass
        az = total_fz / current_mass
        
        self.vx += (ax + wind_accel_x) * dt
        self.vy += ay * dt
        self.vz += (az + wind_accel_z) * dt

        if self.y > 0.1 and (self.y + self.vy * dt) <= 0.1:
            self.touchdown_vertical_speed_mps = self.vy

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        
        self.max_altitude_reached = max(self.max_altitude_reached, self.y)
        self.max_speed_reached = max(self.max_speed_reached, current_speed_mps)

        g_vertical = (ay - (-9.81)) / 9.81 if current_mass > 0 else 1.0
        self.current_g_force = abs(g_vertical)

        if self.current_g_force > self.config.max_g_force and not self.on_ground:
            damage = (self.current_g_force - self.config.max_g_force) * 8 * dt
            self.structural_integrity = max(0, self.structural_integrity - damage)
            if self.structural_integrity <= 0 and not self.crashed:
                self.crashed = True; print("CRASH: Over-G")

    def update_autopilot(self, dt, current_speed_mps):
        if not self.autopilot_on or self.crashed: return

        ap_p_alt, ap_i_alt, ap_d_alt = 0.02, 0.001, 0.05
        ap_p_hdg, ap_i_hdg, ap_d_hdg = 0.4, 0.02, 0.1
        ap_p_spd = 0.8 # Simplified P for speed

        ap_integral_alt = getattr(self, 'ap_integral_alt', 0)
        ap_prev_alt_error = getattr(self, 'ap_prev_alt_error', 0)
        ap_integral_hdg = getattr(self, 'ap_integral_hdg', 0)
        ap_prev_hdg_error = getattr(self, 'ap_prev_hdg_error', 0)

        if self.ap_target_altitude is not None:
            alt_error = self.ap_target_altitude - self.y
            ap_integral_alt += alt_error * dt
            ap_integral_alt = np.clip(ap_integral_alt, -100, 100)
            derivative_alt = (alt_error - ap_prev_alt_error) / dt if dt > 0 else 0
            
            target_pitch_rate_cmd = (ap_p_alt * alt_error) + \
                                    (ap_i_alt * ap_integral_alt) + \
                                    (ap_d_alt * derivative_alt)
            target_pitch_rate_cmd = np.clip(target_pitch_rate_cmd, -self.config.turn_rate*0.3, self.config.turn_rate*0.3)
            
            self.pitch_rate += (target_pitch_rate_cmd - self.pitch_rate) * 0.1 * dt * 20
            self.ap_prev_alt_error = alt_error

        if self.ap_target_heading is not None:
            heading_error = (self.ap_target_heading - self.yaw + 540) % 360 - 180
            ap_integral_hdg += heading_error * dt
            ap_integral_hdg = np.clip(ap_integral_hdg, -180, 180)
            derivative_hdg = (heading_error - ap_prev_hdg_error) / dt if dt > 0 else 0

            target_roll_cmd_deg = (ap_p_hdg * heading_error) + \
                                  (ap_i_hdg * ap_integral_hdg) + \
                                  (ap_d_hdg * derivative_hdg)
            target_roll_cmd_deg = np.clip(target_roll_cmd_deg, -25, 25)

            roll_error_to_target = target_roll_cmd_deg - self.roll
            self.roll_rate += (roll_error_to_target * 0.5) * dt * 20
            self.ap_prev_hdg_error = heading_error

        if self.ap_target_speed is not None:
            speed_error = self.ap_target_speed - current_speed_mps
            thrust_adj = np.clip(speed_error * ap_p_spd, -20, 20)
            self.thrust_input = np.clip(self.thrust_input + thrust_adj * dt, 0, 100)
        
        self.ap_integral_alt = ap_integral_alt
        self.ap_integral_hdg = ap_integral_hdg

    def update(self, dt, weather: Weather, sound_manager: SoundManager):
        if self.crashed:
            self.vx *= (1 - 0.5 * dt)
            self.vz *= (1 - 0.5 * dt)
            self.vy =0
            self.pitch_rate = 0; self.roll_rate = 0; self.yaw_rate = 0;
            return

        self.flight_time_sec += dt
        old_x, old_z = self.x, self.z

        self.update_engine_rpm(dt)

        air_density = 1.225 * math.exp(-self.y / 8500)
        current_speed_mps = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)

        lift, drag = self.calculate_aerodynamics(air_density, current_speed_mps, weather)

        total_available_thrust_factor = sum(
            (self.engine_health[i] / 100.0) for i in range(self.config.engine_count) if not self.engines_failed[i]
        ) / self.config.engine_count if self.config.engine_count > 0 else 0
        
        actual_thrust_percent = self.engine_rpm_percent if self.engine_on and self.fuel > 0 else 0
        thrust_force = (actual_thrust_percent / 100.0) * self.config.max_thrust * total_available_thrust_factor

        self.apply_forces_and_torques(dt, lift, drag, thrust_force, weather, current_speed_mps)
        self.update_autopilot(dt, current_speed_mps)
        
        if self.engine_on and self.config.engine_count > 0 and self.fuel > 0:
            active_engines = sum(1 for failed in self.engines_failed if not failed)
            consumption_rate = self.config.fuel_consumption * (self.engine_rpm_percent / 100.0)**1.5 * \
                               (active_engines / self.config.engine_count if self.config.engine_count > 0 else 0)
            fuel_consumed = consumption_rate * dt
            self.fuel = max(0, self.fuel - fuel_consumed)
            if self.fuel == 0 and self.engine_on:
                print("Fuel Empty! Engine(s) shutting down."); self.engine_on = False

        terrain_height = 0
        if self.y <= terrain_height + 0.1 and not self.on_ground:
            self.on_ground = True
            self.y = terrain_height
            
            impact_g = abs(self.touchdown_vertical_speed_mps / 9.81)
            hs_kts = current_speed_mps * 1.94384
            print(f"Touchdown: VS={self.touchdown_vertical_speed_mps:.2f}m/s ({impact_g:.2f}G), HS={hs_kts:.1f}kts, Roll={self.roll:.1f}")

            max_safe_vs_mps = -3.0
            max_safe_hs_mps = self.config.stall_speed_clean * 1.8

            if not self.gear_down or \
               self.touchdown_vertical_speed_mps < max_safe_vs_mps * 1.5 or \
               current_speed_mps > max_safe_hs_mps or \
               abs(self.roll) > 10 or abs(self.pitch) > 15:
                self.crashed = True
                self.structural_integrity = 0
                print("CRASH: Hard or improper landing.")
            else:
                self.landed_successfully = True
                self.vy = 0
                score = 100
                score -= min(50, abs(self.touchdown_vertical_speed_mps - (-0.75)) * 25)
                score -= min(30, abs(current_speed_mps - self.config.stall_speed_clean * 1.2) * 2)
                score -= min(20, abs(self.roll) * 3)
                self.landing_score = max(0, int(score))
                print(f"Successful Landing! Score: {self.landing_score}")

        if self.on_ground:
            self.y = terrain_height
            self.vy = 0
            self.pitch_rate *= (1 - 0.8 * dt)
            self.roll_rate *= (1 - 0.95 * dt) 

            friction_coeff_rolling = 0.02
            friction_coeff_braking = 0.6 if current_speed_mps > 5 else 0.3
            total_friction_coeff = friction_coeff_rolling + self.brakes_input * friction_coeff_braking
            
            horizontal_speed = math.sqrt(self.vx**2 + self.vz**2)
            if horizontal_speed > 0.01:
                friction_decel = total_friction_coeff * 9.81
                decel_this_frame = min(friction_decel * dt, horizontal_speed)
                self.vx -= (self.vx / horizontal_speed) * decel_this_frame
                self.vz -= (self.vz / horizontal_speed) * decel_this_frame
            else:
                self.vx, self.vz = 0,0
            
            if abs(self.roll) > 30 and current_speed_mps > 5:
                if not self.crashed: print("CRASH: Wing strike!")
                self.crashed = True; self.structural_integrity = 0

        if current_speed_mps > self.config.max_speed * 0.98 and not self.overspeed_warning_active:
            self.overspeed_warning_active = True
            sound_manager.play_sound('stall_warning') # Re-use stall for overspeed for now
        elif current_speed_mps < self.config.max_speed * 0.95:
            self.overspeed_warning_active = False

        if self.stall_warning_active:
            sound_manager.play_sound('stall_warning')

        dx_frame = self.x - old_x; dz_frame = self.z - old_z
        self.distance_traveled_m += math.sqrt(dx_frame**2 + dz_frame**2)

        if self.y > self.config.service_ceiling * 1.3 and not self.crashed:
             print("CRASH: Exceeded altitude limits."); self.crashed = True
        if self.structural_integrity <=0 and not self.crashed:
            print("CRASH: Structural failure."); self.crashed = True
            
    def set_flaps(self, direction, sound_manager):
        new_setting = self.flaps_setting + direction
        if 0 <= new_setting <= self.flaps_max_setting:
            self.flaps_setting = new_setting
            print(f"Flaps: {self.get_flaps_deflection()} degrees (Setting {self.flaps_setting})")
            sound_manager.play_sound("flaps_move")

    def toggle_gear(self, sound_manager: SoundManager):
        current_speed_mps = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        gear_operating_speed_mps = self.config.stall_speed_clean * 2.0
        if current_speed_mps > gear_operating_speed_mps and not self.gear_down:
            print(f"Cannot retract gear above {gear_operating_speed_mps*1.94384:.0f} kts!")
            sound_manager.play_sound('stall_warning') # Generic warning
            return

        self.gear_down = not self.gear_down
        sound_manager.play_sound("gear_down" if self.gear_down else "gear_up")
        print(f"Gear: {'DOWN' if self.gear_down else 'UP'}")
    
    def get_nav_display_info(self):
        if self.nav_mode_active and self.waypoints and self.current_waypoint_index < len(self.waypoints):
            wp = self.waypoints[self.current_waypoint_index]
            dx = wp.x - self.x
            dz_nav = wp.z - self.z

            distance_m = math.sqrt(dx**2 + dz_nav**2)
            if distance_m < (250 if wp.waypoint_type == "AIRPORT" else 100):
                print(f"Reached Waypoint: {wp.name}")
                self.current_waypoint_index +=1
                if self.current_waypoint_index >= len(self.waypoints):
                    print("All waypoints reached.")
                    self.nav_mode_active = False
                    return None
                else:
                    wp = self.waypoints[self.current_waypoint_index]
                    dx = wp.x - self.x
                    dz_nav = wp.z - self.z
                    distance_m = math.sqrt(dx**2 + dz_nav**2)

            bearing_rad = math.atan2(dx, dz_nav)
            bearing_deg = (math.degrees(bearing_rad) + 360) % 360
            
            desired_track_deg = bearing_deg
            
            current_track_rad = math.atan2(self.vx, self.vz) if math.sqrt(self.vx**2 + self.vz**2) > 1 else math.radians(self.yaw)
            current_track_deg = (math.degrees(current_track_rad) + 360) % 360
            
            track_error_deg = (desired_track_deg - current_track_deg + 540) % 360 - 180

            return {
                "wp_name": wp.name, "wp_type": wp.waypoint_type,
                "distance_nm": distance_m / 1852.0,
                "bearing_deg": bearing_deg,
                "desired_track_deg": desired_track_deg,
                "track_error_deg": track_error_deg,
                "altitude_ft": wp.altitude * 3.28084,
                "current_alt_ft": self.y * 3.28084,
                "altitude_error_ft": (wp.altitude - self.y) * 3.28084
            }
        return None

# Camera Class ( unchanged from previous version)
class Camera:
    def __init__(self):
        self.x, self.y, self.z = 0, 100, -200
        self.target_x, self.target_y, self.target_z = 0,0,0
        
        self.fov_y_deg = 60
        self.aspect_ratio = WIDTH / HEIGHT
        self.near_clip, self.far_clip = 0.5, 30000.0

        self.distance = 25
        self.orbit_angle_h_deg = 0
        self.orbit_angle_v_deg = 15
        
        self.mode = "follow_mouse_orbit"
        self.smooth_factor = 0.1

        self.is_mouse_orbiting = False
        self.last_mouse_pos: Optional[Tuple[int,int]] = None

        self.cam_yaw_deg = 0
        self.cam_pitch_deg = 0
        self.cam_roll_deg = 0

    def update(self, aircraft: Aircraft, dt):
        desired_cam_x, desired_cam_y, desired_cam_z = self.x, self.y, self.z

        if self.mode == "cockpit":
            offset_up = aircraft.config.mass / 80000 * 1.2
            desired_cam_x = aircraft.x
            desired_cam_y = aircraft.y + offset_up
            desired_cam_z = aircraft.z

            self.cam_yaw_deg = aircraft.yaw
            self.cam_pitch_deg = aircraft.pitch
            self.cam_roll_deg = aircraft.roll
           
            look_dist = 1000
            ac_p, ac_y = math.radians(aircraft.pitch), math.radians(aircraft.yaw)
            fwd_x = math.cos(ac_p) * math.sin(ac_y)
            fwd_y = math.sin(ac_p)
            fwd_z = math.cos(ac_p) * math.cos(ac_y)
            self.target_x = desired_cam_x + fwd_x * look_dist
            self.target_y = desired_cam_y + fwd_y * look_dist
            self.target_z = desired_cam_z + fwd_z * look_dist

        elif "follow" in self.mode or "external" in self.mode:
            self.cam_roll_deg = 0
            effective_orbit_h_deg = self.orbit_angle_h_deg + aircraft.yaw
            
            orbit_h_rad = math.radians(effective_orbit_h_deg)
            orbit_v_rad = math.radians(self.orbit_angle_v_deg)

            offset_x_world = self.distance * math.cos(orbit_v_rad) * math.sin(orbit_h_rad)
            offset_y_world = self.distance * math.sin(orbit_v_rad)
            offset_z_world = self.distance * math.cos(orbit_v_rad) * math.cos(orbit_h_rad)
            
            desired_cam_x = aircraft.x - offset_x_world
            desired_cam_y = aircraft.y + offset_y_world
            desired_cam_z = aircraft.z - offset_z_world

            self.target_x = aircraft.x
            self.target_y = aircraft.y
            self.target_z = aircraft.z

        self.x += (desired_cam_x - self.x) * self.smooth_factor * (dt*FPS if dt > 0 else 1)
        self.y += (desired_cam_y - self.y) * self.smooth_factor * (dt*FPS if dt > 0 else 1)
        self.z += (desired_cam_z - self.z) * self.smooth_factor * (dt*FPS if dt > 0 else 1)

    def handle_mouse_input(self, event, aircraft: Aircraft):
        if "mouse_orbit" not in self.mode:
            self.is_mouse_orbiting = False
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:
                self.is_mouse_orbiting = True
                self.last_mouse_pos = event.pos
                pygame.mouse.set_visible(False)
                pygame.event.set_grab(True)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 3:
                self.is_mouse_orbiting = False
                self.last_mouse_pos = None
                pygame.mouse.set_visible(True)
                pygame.event.set_grab(False)
        elif event.type == pygame.MOUSEMOTION:
            if self.is_mouse_orbiting and self.last_mouse_pos:
                dx = event.pos[0] - self.last_mouse_pos[0]
                dy = event.pos[1] - self.last_mouse_pos[1]
                
                self.orbit_angle_h_deg -= dx * 0.3
                self.orbit_angle_v_deg = np.clip(self.orbit_angle_v_deg - dy * 0.3, -85, 85)
                self.last_mouse_pos = event.pos
        
        if event.type == pygame.MOUSEWHEEL:
            scroll_speed = self.distance * 0.1
            self.distance = np.clip(self.distance - event.y * scroll_speed, 3, 300)

# Terrain Class (unchanged from previous version)
class Terrain:
    def __init__(self):
        self.height_map: Dict[Tuple[int, int], float] = {}
        self.airports: List[Dict] = []
        self.trees: List[Dict] = []

        self.generate_terrain()
        self.generate_airports()
        self.generate_trees()

    def generate_terrain(self):
        print("Generating terrain...")
        for x_coord in range(-15000, 15001, 1000):
            for z_coord in range(-15000, 15001, 1000):
                height = 0
                height += 150 * math.sin(x_coord * 0.00005 + 1) * math.cos(z_coord * 0.00005 + 1)
                height += 80 * math.sin(x_coord * 0.00015 + 2) * math.cos(z_coord * 0.00015 + 2)
                height += 40 * math.sin(x_coord * 0.00055 + 3) * math.cos(z_coord * 0.00055 + 3)
                height += random.uniform(-20, 20)
                self.height_map[(x_coord // 500, z_coord // 500)] = max(0, height)
        print(f"Generated {len(self.height_map)} terrain height points.")

    def generate_airports(self):
        self.airports = []
        airport_data = [
            {"x": 0, "z": 0, "elevation": 10, "name": "MAIN INTL (KXYZ)", "rwy_len": 3200, "rwy_width": 50, "rwy_hdg": 165},
            {"x": 10000, "z": 6000, "elevation": 200, "name": "ALPINE PEAK (KAPV)", "rwy_len": 1800, "rwy_width": 30, "rwy_hdg": 80},
            {"x": -7000, "z": -9000, "elevation": 5, "name": "SEASIDE STRIP (KSTS)", "rwy_len": 1200, "rwy_width": 25, "rwy_hdg": 310},
            {"x": 13000, "z": -4000, "elevation": 350, "name": "PLATEAU BASE (KPLB)", "rwy_len": 2200, "rwy_width": 40, "rwy_hdg": 45}
        ]
        for ap_data in airport_data:
            for dx in range(-2, 3):
                for dz in range(-2, 3):
                    self.height_map[((ap_data['x'] // 500) + dx, (ap_data['z'] // 500) + dz)] = ap_data['elevation']
            
            self.airports.append({
                'x': ap_data['x'], 'z': ap_data['z'], 'elevation': ap_data['elevation'],
                'name': ap_data['name'],
                'runway_length': ap_data['rwy_len'],
                'runway_width': ap_data['rwy_width'],
                'runway_heading': ap_data['rwy_hdg'],
                'has_ils': random.choice([True, False]),
                'has_lights': True
            })
        print(f"Generated {len(self.airports)} airports.")

    def get_height_at(self, x, z):
        key_x, key_z = int(round(x / 500)), int(round(z / 500))
        return self.height_map.get((key_x, key_z), 0)

    def generate_trees(self, count=150):
        self.trees = []
        print(f"Generating {count} trees...")
        for _ in range(count):
            tree_x = random.uniform(-15000, 15000)
            tree_z = random.uniform(-15000, 15000)
            
            on_airport_area = False
            for airport in self.airports:
                dist_sq_to_airport = (tree_x - airport['x'])**2 + (tree_z - airport['z'])**2
                if dist_sq_to_airport < (airport['runway_length'] * 1.5)**2:
                    on_airport_area = True
                    break
            
            if not on_airport_area:
                 base_h = self.get_height_at(tree_x, tree_z)
                 if base_h < 0.1 and random.random() < 0.7: continue

                 tree_h_val = random.uniform(8, 25)
                 self.trees.append({
                     'x': tree_x, 'y': base_h + tree_h_val / 2,
                     'z': tree_z, 'height': tree_h_val,
                     'radius': random.uniform(3, 8)
                 })
        print(f"Finished generating trees: {len(self.trees)} placed.")

# Button Class ( unchanged from previous version)
class Button:
    def __init__(self, x, y, width, height, text, callback, font, 
                 sound_manager: SoundManager,
                 color=GRAY, hover_color=LIGHT_GRAY, text_color=WHITE):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.font = font
        self.sound_manager = sound_manager
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.is_hovered = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.is_hovered:
                self.sound_manager.play_sound('click') # Will do nothing if sounds disabled
                if self.callback:
                    self.callback()
                    return True
        return False

    def draw(self, surface):
        current_color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(surface, current_color, self.rect, border_radius=5)
        pygame.draw.rect(surface, tuple(np.clip(c*0.7,0,255) for c in current_color), self.rect, 2, border_radius=5)
        
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

# Renderer Class ( unchanged from previous version)
class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font_small = pygame.font.Font(None, 22)
        self.font_medium = pygame.font.Font(None, 30)
        self.font_large = pygame.font.Font(None, 52)
        self.font_hud = pygame.font.SysFont("Consolas", 20)
        self.font_hud_large = pygame.font.SysFont("Consolas", 26)

        self.cockpit_overlay_img = None
        try:
            self.cockpit_overlay_img = pygame.image.load("cockpit_overlay.png").convert_alpha()
            self.cockpit_overlay_img = pygame.transform.scale(self.cockpit_overlay_img, (WIDTH, HEIGHT))
        except pygame.error:
            print("Warning: cockpit_overlay.png not found or error loading. Using basic frame.")

    def project_point_3d_to_2d(self, x, y, z, camera: Camera) -> Optional[Tuple[int, int, float]]:
        eye = np.array([camera.x, camera.y, camera.z])
        if camera.mode == "cockpit":
            cam_p_rad = math.radians(camera.cam_pitch_deg)
            cam_y_rad = math.radians(camera.cam_yaw_deg)
            fwd_x = math.cos(cam_p_rad) * math.sin(cam_y_rad)
            fwd_y = math.sin(cam_p_rad)
            fwd_z = math.cos(cam_p_rad) * math.cos(cam_y_rad)
            target_pt = eye + np.array([fwd_x, fwd_y, fwd_z]) * 100
        else:
            target_pt = np.array([camera.target_x, camera.target_y, camera.target_z])

        world_up = np.array([0, 1, 0])

        f = target_pt - eye
        norm_f = np.linalg.norm(f)
        if norm_f < 1e-6: return None
        f = f / norm_f

        s = np.cross(f, world_up)
        norm_s = np.linalg.norm(s)
        if norm_s < 1e-6:
            s = np.cross(f, np.array([0,0,1]))
            norm_s = np.linalg.norm(s)
            if norm_s < 1e-6: return None
        s = s / norm_s
        
        u = np.cross(s, f)

        p_rel_to_eye = np.array([x - eye[0], y - eye[1], z - eye[2]])
        
        x_cam = np.dot(p_rel_to_eye, s)
        y_cam = np.dot(p_rel_to_eye, u)
        z_cam = -np.dot(p_rel_to_eye, f)

        if not (camera.near_clip < z_cam < camera.far_clip):
            return None
        
        tan_half_fovy = math.tan(math.radians(camera.fov_y_deg) / 2.0)
        if abs(z_cam) < 1e-6: return None
        
        sx_ndc = (x_cam / (camera.aspect_ratio * tan_half_fovy * z_cam))
        sy_ndc = (y_cam / (tan_half_fovy * z_cam))

        screen_x = int((sx_ndc + 1.0) / 2.0 * WIDTH)
        screen_y = int((1.0 - sy_ndc) / 2.0 * HEIGHT)

        return screen_x, screen_y, z_cam

    def draw_horizon_and_sky(self, aircraft: Aircraft, camera: Camera):
        self.screen.fill(DARK_BLUE)
        ground_y_screen = HEIGHT * 0.6
        
        ground_quad_world = [
            (-camera.far_clip, 0, -camera.far_clip), ( camera.far_clip, 0, -camera.far_clip),
            ( camera.far_clip, 0,  camera.far_clip), (-camera.far_clip, 0,  camera.far_clip),
        ]
        ground_quad_screen = []
        visible_ground_points = 0
        for p_world in ground_quad_world:
            p_screen_info = self.project_point_3d_to_2d(p_world[0], p_world[1], p_world[2], camera)
            if p_screen_info:
                ground_quad_screen.append((p_screen_info[0], p_screen_info[1]))
                visible_ground_points+=1
        
        if visible_ground_points >=3 :
            try: pygame.draw.polygon(self.screen, DARK_GREEN, ground_quad_screen)
            except ValueError: pass
        else:
             pygame.draw.rect(self.screen, DARK_GREEN, (0, ground_y_screen, WIDTH, HEIGHT - ground_y_screen))

    def rotate_point_3d(self, p, pitch_rad, yaw_rad, roll_rad, order='YXZ'):
        px, py, pz = p[0], p[1], p[2]
        x1 = px * math.cos(yaw_rad) + pz * math.sin(yaw_rad)
        z1 = -px * math.sin(yaw_rad) + pz * math.cos(yaw_rad)
        px, pz = x1, z1
        y1 = py * math.cos(pitch_rad) - pz * math.sin(pitch_rad)
        z1 = py * math.sin(pitch_rad) + pz * math.cos(pitch_rad)
        py, pz = y1, z1
        x2 = px * math.cos(roll_rad) - py * math.sin(roll_rad)
        y2 = px * math.sin(roll_rad) + py * math.cos(roll_rad)
        px, py = x2, y2
        return (px, py, pz)

    def draw_aircraft_model(self, aircraft: Aircraft, camera: Camera):
        if camera.mode == "cockpit" and not aircraft.crashed : return

        pitch_rad = math.radians(aircraft.pitch)
        yaw_rad = math.radians(aircraft.yaw)
        roll_rad = math.radians(aircraft.roll)

        world_vertices = []
        for v_local in aircraft.model_vertices_local:
            v_rotated_yaw = (v_local[0]*math.cos(yaw_rad) + v_local[2]*math.sin(yaw_rad), v_local[1], -v_local[0]*math.sin(yaw_rad) + v_local[2]*math.cos(yaw_rad))
            v_rotated_pitch_yaw = (v_rotated_yaw[0], v_rotated_yaw[1]*math.cos(pitch_rad) - v_rotated_yaw[2]*math.sin(pitch_rad), v_rotated_yaw[1]*math.sin(pitch_rad) + v_rotated_yaw[2]*math.cos(pitch_rad))
            v_rotated_final = (v_rotated_pitch_yaw[0]*math.cos(roll_rad) - v_rotated_pitch_yaw[1]*math.sin(roll_rad), v_rotated_pitch_yaw[0]*math.sin(roll_rad) + v_rotated_pitch_yaw[1]*math.cos(roll_rad), v_rotated_pitch_yaw[2])
            v_world = (v_rotated_final[0] + aircraft.x, v_rotated_final[1] + aircraft.y, v_rotated_final[2] + aircraft.z)
            world_vertices.append(v_world)

        screen_points_with_depth = []
        for wx, wy, wz_world in world_vertices:
            pt_info = self.project_point_3d_to_2d(wx, wy, wz_world, camera)
            screen_points_with_depth.append(pt_info)

        for line_indices in aircraft.model_lines:
            p1_info = screen_points_with_depth[line_indices[0]]
            p2_info = screen_points_with_depth[line_indices[1]]

            if p1_info and p2_info:
                avg_depth = (p1_info[2] + p2_info[2]) / 2.0
                intensity = np.clip(1.0 - (avg_depth / (camera.far_clip*0.6)), 0.15, 1.0)
                aircraft_base_color = SILVER if aircraft.type == AircraftType.AIRLINER else RED if aircraft.type == AircraftType.FIGHTER else YELLOW if aircraft.type == AircraftType.GLIDER else WHITE
                final_color = tuple(int(c * intensity) for c in aircraft_base_color)
                pygame.draw.line(self.screen, final_color, (p1_info[0], p1_info[1]), (p2_info[0], p2_info[1]), 2)

        if not aircraft.engine_on or any(h < 30 for h in aircraft.engine_health) or aircraft.crashed:
            cg_proj_info = self.project_point_3d_to_2d(aircraft.x, aircraft.y, aircraft.z, camera)
            if cg_proj_info:
                sx, sy, _ = cg_proj_info
                for i in range(8):
                    offset_x = -aircraft.vx * 0.1 * i + random.uniform(-3,3)
                    offset_y = -aircraft.vy * 0.1 * i + random.uniform(-3,3)
                    smoke_screen_x = sx + int(offset_x)
                    smoke_screen_y = sy + int(offset_y) + i*3
                    pygame.draw.circle(self.screen, tuple(int(c*0.8) for c in DARK_GRAY), (smoke_screen_x, smoke_screen_y), max(1, 5 - i//2))

    def draw_terrain_features(self, camera: Camera, terrain: Terrain, weather: Weather):
        for airport in terrain.airports:
            ap_x, ap_y, ap_z = airport['x'], airport['elevation'], airport['z']
            dist_sq_to_ap = (ap_x-camera.x)**2 + (ap_y-camera.y)**2 + (ap_z-camera.z)**2
            if dist_sq_to_ap > (camera.far_clip * 0.8)**2: continue

            length, width = airport['runway_length'], airport['runway_width']
            hdg_rad = math.radians(airport['runway_heading'])
            hl, hw = length / 2, width / 2
            
            corners_local_rwy = [(-hw, 0, hl), (hw, 0, hl), (hw, 0, -hl), (-hw, 0, -hl)]
            runway_corners_world = []
            for clx, cly, clz in corners_local_rwy:
                rot_x = clx * math.cos(hdg_rad) - clz * math.sin(hdg_rad)
                rot_z = clx * math.sin(hdg_rad) + clz * math.cos(hdg_rad)
                runway_corners_world.append( (ap_x + rot_x, ap_y + cly, ap_z + rot_z) )

            screen_corners = []
            all_visible = True
            min_depth = camera.far_clip
            for cw_x, cw_y, cw_z in runway_corners_world:
                pt_info = self.project_point_3d_to_2d(cw_x, cw_y, cw_z, camera)
                if pt_info:
                    screen_corners.append((pt_info[0], pt_info[1]))
                    min_depth = min(min_depth, pt_info[2])
                else: all_visible = False; break
            
            if all_visible and len(screen_corners) == 4:
                intensity = np.clip(1.0 - (min_depth / (camera.far_clip * 0.75)), 0.15, 1.0)
                rwy_color = tuple(int(c * intensity) for c in DARK_GRAY)
                pygame.draw.polygon(self.screen, rwy_color, screen_corners)
                
                if min_depth < 8000:
                    center_proj = self.project_point_3d_to_2d(ap_x, ap_y, ap_z, camera)
                    if center_proj:
                        name_surf = self.font_small.render(airport['name'], True, WHITE)
                        self.screen.blit(name_surf, (center_proj[0] - name_surf.get_width()//2, center_proj[1] - 25))
        
        drawn_trees = 0
        for tree in terrain.trees:
            if drawn_trees > 75: break
            dist_sq_to_tree = (tree['x']-camera.x)**2 + (tree['z']-camera.z)**2
            if dist_sq_to_tree > (camera.far_clip * 0.4)**2 : continue

            bottom_proj = self.project_point_3d_to_2d(tree['x'], tree['y'] - tree['height']/2, tree['z'], camera)
            top_proj = self.project_point_3d_to_2d(tree['x'], tree['y'] + tree['height']/2, tree['z'], camera)

            if bottom_proj and top_proj:
                bx, by, bz = bottom_proj; tx, ty, tz = top_proj
                if bz < camera.near_clip or tz < camera.near_clip: continue

                screen_radius_trunk = max(1, int( (tree['radius']*0.3 * 500) / bz if bz > 1 else 5 ))
                screen_radius_leaves = max(2, int( (tree['radius'] * 600) / bz if bz > 1 else 8 ))

                intensity = np.clip(1.0 - (bz / (camera.far_clip * 0.5)), 0.2, 1.0)
                trunk_clr = tuple(int(c * intensity) for c in (101, 67, 33))
                leaves_clr = tuple(int(c * intensity) for c in (34, 80, 34))

                pygame.draw.line(self.screen, trunk_clr, (bx, by), (tx, ty), screen_radius_trunk)
                pygame.draw.circle(self.screen, leaves_clr, (tx, ty), screen_radius_leaves)
                drawn_trees +=1

    def draw_weather_effects(self, weather: Weather, camera: Camera, aircraft: Aircraft):
        particle_count, particle_color, particle_prop = 0, WHITE, {}

        if weather.type == WeatherType.RAIN or weather.type == WeatherType.STORM:
            particle_count = int(weather.precipitation * 60)
            particle_color = (100, 100, 220)
            particle_prop = {'type': 'line', 'length': 18, 'thickness': 1}
        elif weather.type == WeatherType.SNOW:
            particle_count = int(weather.precipitation * 50)
            particle_color = (230, 230, 255)
            particle_prop = {'type': 'circle', 'radius': 3}

        if particle_count > 0:
            for _ in range(particle_count):
                rel_x = random.uniform(-80, 80)
                rel_y = random.uniform(-40, 40) 
                rel_z_cam_space = random.uniform(camera.near_clip + 1, 100)
                
                origin_x, origin_y, origin_z = camera.x, camera.y, camera.z
                if camera.mode == "cockpit":
                    origin_x, origin_y, origin_z = aircraft.x, aircraft.y, aircraft.z
                
                p_world_x = origin_x + rel_x
                p_world_y = origin_y + rel_y 
                p_world_z = origin_z + rel_z_cam_space

                pt_info = self.project_point_3d_to_2d(p_world_x, p_world_y, p_world_z, camera)

                if pt_info:
                    sx, sy, depth = pt_info
                    if not (0 <= sx < WIDTH and 0 <= sy < HEIGHT): continue
                    
                    intensity = np.clip(1.0 - (depth / 200.0), 0.2, 1.0)
                    final_color_vals = tuple(int(c * intensity) for c in particle_color)

                    if particle_prop['type'] == 'circle':
                        size = int(np.clip(particle_prop['radius'] * 80 / depth if depth > 1 else particle_prop['radius'], 1, 6) * intensity)
                        pygame.draw.circle(self.screen, final_color_vals, (sx, sy), size)
                    elif particle_prop['type'] == 'line':
                        length = int(np.clip(particle_prop['length'] * 80 / depth if depth > 1 else particle_prop['length'], 2, 25) * intensity)
                        angle_offset_x = -aircraft.vx * 0.05 * length
                        angle_offset_y = -aircraft.vy * 0.05 * length + length
                        pygame.draw.line(self.screen, final_color_vals, (sx, sy), (sx + int(angle_offset_x), sy + int(angle_offset_y)), particle_prop['thickness'])
        
        if weather.type == WeatherType.FOG and weather.visibility < 2000:
            alpha = np.clip( (2000 - weather.visibility) / 2000 * 220, 0, 220)
            fog_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fog_surf.fill((LIGHT_GRAY[0], LIGHT_GRAY[1], LIGHT_GRAY[2], int(alpha)))
            self.screen.blit(fog_surf, (0,0))

        sorted_clouds = sorted(weather.cloud_particles, key=lambda p: (p['x']-camera.x)**2 + (p['y']-camera.y)**2 + (p['z']-camera.z)**2, reverse=True)
        drawn_clouds = 0
        for cloud_particle in sorted_clouds:
            if drawn_clouds > 25: break
            pt_info = self.project_point_3d_to_2d(cloud_particle['x'], cloud_particle['y'], cloud_particle['z'], camera)
            if pt_info:
                sx, sy, depth = pt_info
                if depth < camera.near_clip + 10 or depth > camera.far_clip * 0.9: continue

                screen_size_w = int(np.clip( (cloud_particle['size'] * 150) / depth if depth > 1 else 0, 10, 400 ))
                screen_size_h = int(screen_size_w * 0.5)
                if screen_size_w < 10: continue

                alpha = np.clip(cloud_particle['opacity'] * (1 - depth / (camera.far_clip*0.8)) * 0.7 , 15, 110)
                cloud_color_base = (210, 210, 225) if weather.type != WeatherType.STORM else (120,120,130)
                
                temp_surf = pygame.Surface((screen_size_w, screen_size_h), pygame.SRCALPHA)
                pygame.draw.ellipse(temp_surf, (*cloud_color_base, int(alpha)), (0,0, screen_size_w, screen_size_h))
                self.screen.blit(temp_surf, (sx - screen_size_w//2, sy - screen_size_h//2))
                drawn_clouds +=1
        
        if weather.type == WeatherType.STORM:
            for strike in weather.lightning_strikes:
                flash_intensity = strike['intensity'] * (1 - (time.time() - strike['time']) / 0.25)
                if flash_intensity > 0:
                    flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    flash_surf.fill((255,255,230, int(flash_intensity * 120)))
                    self.screen.blit(flash_surf, (0,0))

    def draw_attitude_indicator(self, aircraft: Aircraft, x, y, size):
        center_x, center_y = x + size // 2, y + size // 2
        radius = size // 2 - 8

        pygame.draw.circle(self.screen, (30,30,30), (center_x, center_y), radius + 8)
        pygame.draw.circle(self.screen, (80,80,80), (center_x, center_y), radius + 6, 2)
        
        clip_rect = pygame.Rect(center_x - radius, center_y - radius, 2 * radius, 2 * radius)
        original_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)

        pixels_per_degree_pitch = radius / 30

        adi_surface = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
        adi_surf_center_x, adi_surf_center_y = size, size
        
        pygame.draw.rect(adi_surface, (70, 130, 180), (0, 0, size*2, adi_surf_center_y - aircraft.pitch * pixels_per_degree_pitch))
        pygame.draw.rect(adi_surface, (139, 90, 43), (0, adi_surf_center_y - aircraft.pitch * pixels_per_degree_pitch, size*2, size*2))
        
        for p_deg in range(-60, 61, 10):
            line_screen_y = adi_surf_center_y - (p_deg - aircraft.pitch) * pixels_per_degree_pitch
            if abs(p_deg - aircraft.pitch) > 45 : continue

            line_width_adi = radius * (0.4 if p_deg == 0 else (0.25 if p_deg % 30 == 0 else 0.15))
            line_thickness = 3 if p_deg == 0 else 1
            pygame.draw.line(adi_surface, WHITE, (adi_surf_center_x - line_width_adi, line_screen_y), (adi_surf_center_x + line_width_adi, line_screen_y), line_thickness)
            if p_deg != 0 and (p_deg % 20 == 0 or p_deg==10 or p_deg==-10):
                num_text = self.font_small.render(str(abs(p_deg)), True, WHITE)
                adi_surface.blit(num_text, (adi_surf_center_x - line_width_adi - 20, line_screen_y - num_text.get_height()//2))
                adi_surface.blit(num_text, (adi_surf_center_x + line_width_adi + 5, line_screen_y - num_text.get_height()//2))

        rotated_adi_surf = pygame.transform.rotate(adi_surface, aircraft.roll)
        self.screen.blit(rotated_adi_surf, rotated_adi_surf.get_rect(center=(center_x, center_y)))
        self.screen.set_clip(original_clip)

        pygame.draw.line(self.screen, YELLOW, (center_x - radius*0.4, center_y), (center_x - radius*0.1, center_y), 3)
        pygame.draw.line(self.screen, YELLOW, (center_x + radius*0.1, center_y), (center_x + radius*0.4, center_y), 3)
        pygame.draw.line(self.screen, YELLOW, (center_x - radius*0.1, center_y), (center_x, center_y - 5), 3)
        pygame.draw.line(self.screen, YELLOW, (center_x + radius*0.1, center_y), (center_x, center_y - 5), 3)
        pygame.draw.circle(self.screen, YELLOW, (center_x, center_y), 3)

        for angle_deg in range(-60, 61, 10):
            if angle_deg == 0: continue
            rad = math.radians(angle_deg - 90 + aircraft.roll)
            start_x = center_x + (radius - (8 if angle_deg % 30 == 0 else 4)) * math.cos(rad)
            start_y = center_y + (radius - (8 if angle_deg % 30 == 0 else 4)) * math.sin(rad)
            end_x = center_x + radius * math.cos(rad)
            end_y = center_y + radius * math.sin(rad)
            pygame.draw.line(self.screen, WHITE, (start_x, start_y), (end_x, end_y), 1)
        pygame.draw.polygon(self.screen, YELLOW, [(center_x, center_y - radius + 8), (center_x-5, center_y-radius-2), (center_x+5, center_y-radius-2)])

    def draw_horizontal_situation_indicator(self, aircraft: Aircraft, nav_info, x, y, size):
        center_x, center_y = x + size // 2, y + size // 2
        radius = size // 2 - 8

        pygame.draw.circle(self.screen, (30,30,30), (center_x, center_y), radius + 8)
        pygame.draw.circle(self.screen, (80,80,80), (center_x, center_y), radius + 6, 2)
        pygame.draw.circle(self.screen, BLACK, (center_x, center_y), radius)

        for angle_deg_abs in range(0, 360, 10):
            angle_on_screen_rad = math.radians((angle_deg_abs - aircraft.yaw - 90 + 360)%360)
            is_cardinal = (angle_deg_abs % 90 == 0)
            is_major_tick = (angle_deg_abs % 30 == 0)
            tick_len = radius * (0.18 if is_cardinal else (0.12 if is_major_tick else 0.08))
            tick_color = HUD_GREEN if is_cardinal else WHITE
            
            start_x = center_x + (radius - tick_len) * math.cos(angle_on_screen_rad)
            start_y = center_y + (radius - tick_len) * math.sin(angle_on_screen_rad)
            end_x = center_x + radius * math.cos(angle_on_screen_rad)
            end_y = center_y + radius * math.sin(angle_on_screen_rad)
            pygame.draw.line(self.screen, tick_color, (start_x, start_y), (end_x, end_y), 2 if is_major_tick else 1)

            if is_major_tick :
                text_angle_rad = angle_on_screen_rad
                if is_cardinal: label = "N" if angle_deg_abs == 0 else "E" if angle_deg_abs == 90 else "S" if angle_deg_abs == 180 else "W"
                else: label = str(angle_deg_abs // 10)
                
                text_surf = self.font_small.render(label, True, tick_color)
                text_dist = radius - tick_len - (12 if is_cardinal else 10)
                text_x = center_x + text_dist * math.cos(text_angle_rad) - text_surf.get_width()//2
                text_y = center_y + text_dist * math.sin(text_angle_rad) - text_surf.get_height()//2
                self.screen.blit(text_surf, (text_x, text_y))

        pygame.draw.polygon(self.screen, YELLOW, [ (center_x, center_y - 7), (center_x - 5, center_y + 5), (center_x + 5, center_y + 5)])
        pygame.draw.line(self.screen, YELLOW, (center_x, center_y - radius), (center_x, center_y - radius + 15), 3)

        if aircraft.autopilot_on and aircraft.ap_target_heading is not None:
            hdg_bug_screen_rad = math.radians((aircraft.ap_target_heading - aircraft.yaw - 90 + 360)%360)
            bug_x = center_x + radius * 0.9 * math.cos(hdg_bug_screen_rad)
            bug_y = center_y + radius * 0.9 * math.sin(hdg_bug_screen_rad)
            pygame.draw.polygon(self.screen, CYAN, [(bug_x, bug_y - 6), (bug_x + 6, bug_y), (bug_x, bug_y + 6), (bug_x - 6, bug_y)])
        
        if nav_info:
            dtk_screen_rad = math.radians((nav_info['desired_track_deg'] - aircraft.yaw - 90 + 360)%360)
            crs_x1 = center_x + (radius*0.85) * math.cos(dtk_screen_rad)
            crs_y1 = center_y + (radius*0.85) * math.sin(dtk_screen_rad)
            crs_x2 = center_x + (radius*1.0) * math.cos(dtk_screen_rad)
            crs_y2 = center_y + (radius*1.0) * math.sin(dtk_screen_rad)
            pygame.draw.line(self.screen, PURPLE, (crs_x1, crs_y1), (crs_x2, crs_y2), 3)

            max_dev_hsi_deg = 10.0 
            dev_scaled = np.clip(nav_info['track_error_deg'] / max_dev_hsi_deg, -1.0, 1.0)
            cdi_bar_half_len = radius * 0.6
            cdi_bar_offset_pixels = dev_scaled * (radius * 0.4)
            cdi_center_x = center_x + cdi_bar_offset_pixels * math.cos(dtk_screen_rad + math.pi/2)
            cdi_center_y = center_y + cdi_bar_offset_pixels * math.sin(dtk_screen_rad + math.pi/2)
            cdi_p1_x = cdi_center_x - cdi_bar_half_len * math.cos(dtk_screen_rad)
            cdi_p1_y = cdi_center_y - cdi_bar_half_len * math.sin(dtk_screen_rad)
            cdi_p2_x = cdi_center_x + cdi_bar_half_len * math.cos(dtk_screen_rad)
            cdi_p2_y = cdi_center_y + cdi_bar_half_len * math.sin(dtk_screen_rad)
            pygame.draw.line(self.screen, PURPLE, (cdi_p1_x, cdi_p1_y), (cdi_p2_x, cdi_p2_y), 4)

            bearing_to_wp_deg = nav_info['bearing_deg']
            dtk_deg = nav_info['desired_track_deg']
            angle_diff_brg_dtk = (bearing_to_wp_deg - dtk_deg + 540) % 360 - 180
            to_from_text = ""
            if abs(angle_diff_brg_dtk) < 85: to_from_text = "TO"
            elif abs(angle_diff_brg_dtk) > 95: to_from_text = "FR"
            if to_from_text:
                tf_surf = self.font_small.render(to_from_text, True, PURPLE)
                self.screen.blit(tf_surf, (center_x - tf_surf.get_width()//2, center_y + radius*0.2))

        hdg_txt_surf = self.font_hud.render(f"{aircraft.yaw:03.0f}°", True, WHITE)
        pygame.draw.rect(self.screen, BLACK, (center_x - 25, y - 22, 50, 20))
        self.screen.blit(hdg_txt_surf, (center_x - hdg_txt_surf.get_width()//2, y - 20))

    def draw_hud(self, aircraft: Aircraft, weather: Weather, camera: Camera, nav_info):
        hud_color = HUD_GREEN
        if aircraft.crashed: hud_color = RED
        elif aircraft.stall_warning_active or aircraft.overspeed_warning_active: hud_color = HUD_AMBER
        
        speed_kts = math.sqrt(aircraft.vx**2 + aircraft.vy**2 + aircraft.vz**2) * 1.94384
        speed_tape_x, speed_tape_y, speed_tape_w, speed_tape_h = 30, HEIGHT//2 - 100, 80, 200
        spd_txt = self.font_hud_large.render(f"{speed_kts:3.0f}", True, hud_color)
        pygame.draw.rect(self.screen, (*BLACK,180), (speed_tape_x + speed_tape_w//2 - 35, speed_tape_y + speed_tape_h//2 - 20, 70, 40), border_radius=3)
        self.screen.blit(spd_txt, (speed_tape_x + speed_tape_w//2 - spd_txt.get_width()//2, speed_tape_y + speed_tape_h//2 - spd_txt.get_height()//2))
        self.screen.blit(self.font_hud.render("KT", True, hud_color), (speed_tape_x + speed_tape_w//2 - 15, speed_tape_y + speed_tape_h//2 + 15))

        alt_ft = aircraft.y * 3.28084
        alt_tape_x, alt_tape_y, alt_tape_w, alt_tape_h = WIDTH - 30 - 80, HEIGHT//2 - 100, 80, 200
        alt_txt = self.font_hud_large.render(f"{alt_ft:5.0f}", True, hud_color)
        pygame.draw.rect(self.screen, (*BLACK,180), (alt_tape_x + alt_tape_w//2 - 50, alt_tape_y + alt_tape_h//2 - 20, 100, 40), border_radius=3)
        self.screen.blit(alt_txt, (alt_tape_x + alt_tape_w//2 - alt_txt.get_width()//2, alt_tape_y + alt_tape_h//2 - alt_txt.get_height()//2))
        self.screen.blit(self.font_hud.render("FT", True, hud_color), (alt_tape_x + alt_tape_w//2 - 15, alt_tape_y + alt_tape_h//2 + 15))

        adi_hsi_size = 220
        total_width_instruments = adi_hsi_size * 2 + 20
        start_x_instruments = WIDTH//2 - total_width_instruments//2
        instruments_y = HEIGHT - adi_hsi_size - 15

        self.draw_attitude_indicator(aircraft, start_x_instruments, instruments_y, adi_hsi_size)
        self.draw_horizontal_situation_indicator(aircraft, nav_info, start_x_instruments + adi_hsi_size + 20, instruments_y, adi_hsi_size)

        if camera.mode == "cockpit":
            if self.cockpit_overlay_img: self.screen.blit(self.cockpit_overlay_img, (0,0))
            else: pygame.draw.rect(self.screen, (40,40,40,200), (0,0,WIDTH,HEIGHT), 30)

        status_x, status_y_start = WIDTH - 180, 20
        current_y = status_y_start
        pygame.draw.rect(self.screen, (*BLACK, 150), (status_x - 10, current_y -5, 180, 200), border_radius=5)

        def draw_status(label, value_str, color=hud_color):
            nonlocal current_y
            lbl_surf = self.font_hud.render(label, True, LIGHT_GRAY)
            val_surf = self.font_hud.render(value_str, True, color)
            self.screen.blit(lbl_surf, (status_x, current_y))
            self.screen.blit(val_surf, (status_x + 70, current_y))
            current_y += lbl_surf.get_height() + 2
            return current_y

        draw_status("THR", f"{aircraft.engine_rpm_percent:3.0f}%")
        draw_status("FUEL", f"{aircraft.fuel/(3.785 if aircraft.fuel > 0 else 1):3.0f} Gal", RED if aircraft.fuel < aircraft.config.fuel_capacity*0.1 else hud_color)
        draw_status("GEAR", "DOWN" if aircraft.gear_down else " UP ", LIME if aircraft.gear_down else (RED if speed_kts > 100 and not aircraft.gear_down and aircraft.y < 3000 else hud_color))
        draw_status("FLAP", f"{aircraft.get_flaps_deflection():2.0f}°")
        draw_status("TRIM", f"{aircraft.pitch_trim:+2.1f}°")
        draw_status("  G ", f"{aircraft.current_g_force:2.1f}", RED if aircraft.current_g_force > aircraft.config.max_g_force*0.85 else hud_color)

        if aircraft.autopilot_on:
            ap_s = self.font_hud.render("AUTOPILOT", True, CYAN); self.screen.blit(ap_s, (status_x, current_y)); current_y += ap_s.get_height() +2
            if aircraft.ap_target_altitude: draw_status(" AP ALT", f"{aircraft.ap_target_altitude*3.28084:5.0f} FT", CYAN)
            if aircraft.ap_target_heading: draw_status(" AP HDG", f"{aircraft.ap_target_heading:03.0f}°", CYAN)
            if aircraft.ap_target_speed: draw_status(" AP SPD", f"{aircraft.ap_target_speed*1.94384:3.0f} KT", CYAN)

        warn_y = 20
        if aircraft.stall_warning_active: ws = self.font_hud_large.render("STALL", True, RED); self.screen.blit(ws, (WIDTH//2 - ws.get_width()//2, warn_y)); warn_y += ws.get_height()
        if aircraft.overspeed_warning_active: ws = self.font_hud_large.render("OVERSPEED", True, RED); self.screen.blit(ws, (WIDTH//2 - ws.get_width()//2, warn_y)); warn_y += ws.get_height()
        if not aircraft.engine_on and aircraft.type != AircraftType.GLIDER: ws = self.font_hud_large.render("ENGINE OFF", True, RED); self.screen.blit(ws, (WIDTH//2 - ws.get_width()//2, warn_y)); warn_y += ws.get_height()
        if aircraft.structural_integrity < 50: ws = self.font_hud_large.render(f"DAMAGE {aircraft.structural_integrity:.0f}%", True, RED); self.screen.blit(ws, (WIDTH//2 - ws.get_width()//2, warn_y)); warn_y += ws.get_height()

        if nav_info:
            nav_block_x, nav_block_y, nav_block_w, nav_block_h = 20, 20, 260, 110
            pygame.draw.rect(self.screen, (*BLACK,150), (nav_block_x, nav_block_y, nav_block_w, nav_block_h), border_radius=5)
            ny = nav_block_y + 8; nx_val = nav_block_x + 80
            def draw_nav(label, value, color=WHITE):
                nonlocal ny
                lbl_s = self.font_hud.render(label, True, LIGHT_GRAY); val_s = self.font_hud.render(value, True, color)
                self.screen.blit(lbl_s, (nav_block_x + 8, ny)); self.screen.blit(val_s, (nx_val, ny)); ny += lbl_s.get_height() + 2
            draw_nav("WAYPOINT:", nav_info['wp_name'][:12], CYAN)
            draw_nav("DISTANCE:", f"{nav_info['distance_nm']:.1f} NM")
            draw_nav("BEARING:", f"{nav_info['bearing_deg']:.0f}°")
            draw_nav("DTK:", f"{nav_info['desired_track_deg']:.0f}° (Dev {nav_info['track_error_deg']:.0f}°) ")
            draw_nav("WP ALT:", f"{nav_info['altitude_ft']:.0f} FT (Err {nav_info['altitude_error_ft']:.0f})")

    def draw_main_menu(self, buttons, selected_aircraft_type):
        self.screen.fill(NAVY)
        title = self.font_large.render("Flight Simulator X-treme", True, GOLD)
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//4 - 50))
        ac_text = self.font_medium.render(f"Aircraft: {selected_aircraft_type.value}", True, YELLOW)
        self.screen.blit(ac_text, (WIDTH//2 - ac_text.get_width()//2, HEIGHT//2 - 80))
        info_text = self.font_small.render("Press 'C' to change aircraft. Mouse click or Enter to Start.", True, LIGHT_GRAY)
        self.screen.blit(info_text, (WIDTH//2 - info_text.get_width()//2, HEIGHT//2 - 40))
        for button in buttons: button.draw(self.screen)
        pygame.display.flip()

    def draw_pause_menu(self, buttons, help_visible, aircraft_controls_info):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); overlay.fill((10, 20, 40, 200)); self.screen.blit(overlay, (0,0))
        title = self.font_large.render("GAME PAUSED", True, ORANGE); self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 100))
        for button in buttons: button.draw(self.screen)
        help_start_y = HEIGHT//2 - 20
        help_info_text = self.font_small.render("Press 'H' for Controls | 'M' for Weather | 'C' for Aircraft", True, LIGHT_GRAY)
        self.screen.blit(help_info_text, (WIDTH//2 - help_info_text.get_width()//2, help_start_y - 30))
        if help_visible:
            pygame.draw.rect(self.screen, (*DARK_GRAY, 220), (WIDTH//2 - 280, help_start_y, 560, 240), border_radius=8)
            for i, line in enumerate(aircraft_controls_info):
                txt = self.font_small.render(line, True, WHITE); self.screen.blit(txt, (WIDTH//2 - 270, help_start_y + 10 + i * 22))
        pygame.display.flip()

    def draw_debrief_screen(self, aircraft: Aircraft, buttons):
        self.screen.fill((20,30,50))
        title_text = "SIMULATION ENDED"; title_color = ORANGE
        if aircraft.crashed: title_text = "AIRCRAFT CRASHED"; title_color = RED
        elif aircraft.landed_successfully: title_text = "LANDING SUCCESSFUL"; title_color = LIME
        title = self.font_large.render(title_text, True, title_color); self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 80))
        stats_y_start = 200; stats_x = WIDTH//2
        stats = [
            f"Flight Time: {aircraft.flight_time_sec:.1f} s", f"Distance Flown: {aircraft.distance_traveled_m/1000:.2f} km ({aircraft.distance_traveled_m/1852:.1f} NM)",
            f"Max Altitude: {aircraft.max_altitude_reached*3.28084:.0f} ft", f"Max Speed: {aircraft.max_speed_reached*1.94384:.0f} kts",
            f"Fuel Used: {(aircraft.config.fuel_capacity - aircraft.fuel)/3.785:.1f} Gal", f"Structural Integrity: {aircraft.structural_integrity:.0f}%"
        ]
        if aircraft.landed_successfully:
            stats.append(f"Touchdown V/S: {aircraft.touchdown_vertical_speed_mps*196.85:.0f} fpm")
            stats.append(f"Landing Score: {aircraft.landing_score:.0f} / 100")
        for i, stat_line in enumerate(stats):
            txt = self.font_medium.render(stat_line, True, WHITE); self.screen.blit(txt, (stats_x - txt.get_width()//2, stats_y_start + i * 40))
        for button in buttons: button.draw(self.screen)
        pygame.display.flip()

# FlightSimulator Class (Main Game Logic)
class FlightSimulator:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Flight Simulator Pro Alpha")
        self.clock = pygame.time.Clock()
        
        self.sound_manager = SoundManager() # Sounds are now disabled by default in SoundManager
        self.weather = Weather()
        self.terrain = Terrain()
        self.camera = Camera()
        self.renderer = Renderer(self.screen)
        
        self.selected_aircraft_type = AircraftType.AIRLINER
        self.aircraft: Optional[Aircraft] = None

        self.game_state = GameState.MENU
        
        self.show_help_in_pause = False
        self.aircraft_controls_info = [
            "W/S: Pitch | A/D: Roll | Q/E: Yaw/Rudder",
            "LShift/LCtrl or PgUp/PgDn: Throttle",
            "Home: Max Thr | End: Idle Thr",
            "G: Gear | F/V: Flaps | B: Spoilers", 
            "Space: Brakes (Hold) | [/]: Pitch Trim",
            "Tab: Autopilot | N: NAV Mode",
            "1: Cockpit | 2: Chase Cam | 3: Orbit Cam",
            "RMouse+Drag: Orbit Cam | Scroll: Zoom Cam",
            "R: Reset Flight (in game/pause)",
            "P or Esc: Pause/Menu Navigation"
        ]
        self._init_buttons()

    def _init_buttons(self):
        btn_font = self.renderer.font_medium
        btn_w, btn_h = 240, 55
        spacing = 70
        start_y_menu = HEIGHT//2 + 0
        self.menu_buttons = [
            Button(WIDTH//2 - btn_w//2, start_y_menu, btn_w, btn_h, "Start Flight", self.start_game, btn_font, self.sound_manager),
            Button(WIDTH//2 - btn_w//2, start_y_menu + spacing, btn_w, btn_h, "Quit", self.quit_game, btn_font, self.sound_manager)
        ]
        start_y_pause = HEIGHT//2 - 120
        self.pause_buttons = [
            Button(WIDTH//2 - btn_w//2, start_y_pause, btn_w, btn_h, "Resume", self.toggle_pause, btn_font, self.sound_manager),
            Button(WIDTH//2 - btn_w//2, start_y_pause + spacing, btn_w, btn_h, "Main Menu", self.go_to_main_menu, btn_font, self.sound_manager),
            Button(WIDTH//2 - btn_w//2, start_y_pause + spacing*2, btn_w, btn_h, "Quit Game", self.quit_game, btn_font, self.sound_manager)
        ]
        start_y_debrief = HEIGHT - 220
        self.debrief_buttons = [
            Button(WIDTH//2 - btn_w//2, start_y_debrief, btn_w, btn_h, "Restart Flight", self.restart_flight, btn_font, self.sound_manager),
            Button(WIDTH//2 - btn_w//2, start_y_debrief + spacing, btn_w, btn_h, "Main Menu", self.go_to_main_menu, btn_font, self.sound_manager)
        ]

    def start_game(self):
        self.aircraft = Aircraft(0, 100, 0, self.selected_aircraft_type)
        main_airport = next((ap for ap in self.terrain.airports if "MAIN" in ap['name']), self.terrain.airports[0])
        other_airport = next((ap for ap in self.terrain.airports if "MAIN" not in ap['name']), self.terrain.airports[1])
        self.aircraft.x = main_airport['x']
        self.aircraft.y = main_airport['elevation'] + 150
        self.aircraft.z = main_airport['z']
        self.aircraft.yaw = main_airport['runway_heading']
        self.aircraft.vx = math.sin(math.radians(self.aircraft.yaw)) * self.aircraft.config.stall_speed_clean * 0.8
        self.aircraft.vz = math.cos(math.radians(self.aircraft.yaw)) * self.aircraft.config.stall_speed_clean * 0.8
        self.aircraft.on_ground = False
        self.aircraft.gear_down = True
        self.aircraft.waypoints = [
            Waypoint(main_airport['x'] + math.sin(math.radians(main_airport['runway_heading']))*8000, main_airport['z'] + math.cos(math.radians(main_airport['runway_heading']))*8000, 1200, "DEP FIX", "NAV"),
            Waypoint(other_airport['x'], other_airport['z'], other_airport['elevation'] + 400, other_airport['name'] + " IAF", "NAV"),
            Waypoint(other_airport['x'], other_airport['z'], other_airport['elevation'], other_airport['name'], "AIRPORT")
        ]
        self.aircraft.current_waypoint_index = 0
        self.camera = Camera()
        self.camera.mode = "follow_mouse_orbit"
        self.camera.distance = 35 if self.selected_aircraft_type == AircraftType.AIRLINER else 20
        self.weather.type = random.choice(list(WeatherType))
        self.weather.update_conditions()
        self.game_state = GameState.PLAYING
        # self.sound_manager.enabled = True # Enable sounds only if you have them
        # self.sound_manager.play_engine_sound(self.aircraft.engine_rpm_percent, self.aircraft.type)

    def restart_flight(self):
        # self.sound_manager.stop_all_sounds()
        self.start_game()

    def go_to_main_menu(self):
        # self.sound_manager.stop_all_sounds()
        # self.sound_manager.enabled = False
        self.aircraft = None
        self.game_state = GameState.MENU
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)
        
    def quit_game(self):
        self.running = False

    def toggle_pause(self):
        if self.game_state == GameState.PLAYING:
            self.game_state = GameState.PAUSED
            # self.sound_manager.enabled = False
            pygame.mouse.set_visible(True); pygame.event.set_grab(False)
        elif self.game_state == GameState.PAUSED:
            self.game_state = GameState.PLAYING
            self.show_help_in_pause = False
            # self.sound_manager.enabled = True
            if self.camera.is_mouse_orbiting : pygame.mouse.set_visible(False); pygame.event.set_grab(True)

    def cycle_aircraft_type(self):
        types = list(AircraftType)
        current_idx = types.index(self.selected_aircraft_type)
        self.selected_aircraft_type = types[(current_idx + 1) % len(types)]
        if self.aircraft and self.game_state == GameState.PAUSED:
            print(f"Next flight aircraft: {self.selected_aircraft_type.value}")

    def handle_continuous_input(self, dt):
        if not self.aircraft: return
        keys = pygame.key.get_pressed()
        pitch_authority = self.aircraft.config.turn_rate * 0.8 * self.aircraft.elevator_effectiveness
        roll_authority = self.aircraft.config.turn_rate * 1.2 * self.aircraft.aileron_effectiveness
        yaw_authority = self.aircraft.config.turn_rate * 0.5 * self.aircraft.rudder_effectiveness
        if keys[pygame.K_w]: self.aircraft.pitch_rate -= pitch_authority * dt * 2.0
        if keys[pygame.K_s]: self.aircraft.pitch_rate += pitch_authority * dt * 2.0
        self.aircraft.pitch_rate += self.aircraft.pitch_trim * 0.15 * self.aircraft.elevator_effectiveness * dt * 10
        if keys[pygame.K_a]: self.aircraft.roll_rate -= roll_authority * dt * 2.5
        if keys[pygame.K_d]: self.aircraft.roll_rate += roll_authority * dt * 2.5
        if keys[pygame.K_q]: self.aircraft.yaw_rate -= yaw_authority * dt * 2.0
        if keys[pygame.K_e]: self.aircraft.yaw_rate += yaw_authority * dt * 2.0
        self.aircraft.pitch_rate = np.clip(self.aircraft.pitch_rate, -50, 50)
        self.aircraft.roll_rate = np.clip(self.aircraft.roll_rate, -120, 120)
        self.aircraft.yaw_rate = np.clip(self.aircraft.yaw_rate, -30, 30)
        throttle_change_rate = 30.0
        if keys[pygame.K_LSHIFT] or keys[pygame.K_PAGEUP]: self.aircraft.thrust_input = min(100, self.aircraft.thrust_input + throttle_change_rate * dt)
        if keys[pygame.K_LCTRL] or keys[pygame.K_PAGEDOWN]: self.aircraft.thrust_input = max(0, self.aircraft.thrust_input - throttle_change_rate * dt)
        self.aircraft.brakes_input = 1.0 if keys[pygame.K_SPACE] else 0.0

    def handle_event(self, event):
        if self.aircraft: self.camera.handle_mouse_input(event, self.aircraft)
        if self.game_state == GameState.MENU:
            for btn in self.menu_buttons: btn.handle_event(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN: self.start_game()
                if event.key == pygame.K_c: self.cycle_aircraft_type()
        elif self.game_state == GameState.PAUSED:
            for btn in self.pause_buttons: btn.handle_event(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_h: self.show_help_in_pause = not self.show_help_in_pause
                if event.key == pygame.K_c: self.cycle_aircraft_type()
                if event.key == pygame.K_m:
                    current_idx = list(WeatherType).index(self.weather.type)
                    self.weather.type = list(WeatherType)[(current_idx + 1) % len(list(WeatherType))]
                    self.weather.update_conditions(); self.weather.generate_clouds()
                    print(f"Weather manually set to: {self.weather.type.value}")
                if event.key == pygame.K_r: self.restart_flight()
        elif self.game_state == GameState.PLAYING and self.aircraft:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_g: self.aircraft.toggle_gear(self.sound_manager)
                if event.key == pygame.K_f: self.aircraft.set_flaps(1, self.sound_manager)
                if event.key == pygame.K_v: self.aircraft.set_flaps(-1, self.sound_manager)
                if event.key == pygame.K_b: self.aircraft.spoilers_deployed = not self.aircraft.spoilers_deployed
                if event.key == pygame.K_LEFTBRACKET: self.aircraft.pitch_trim -= 0.1
                if event.key == pygame.K_RIGHTBRACKET: self.aircraft.pitch_trim += 0.1
                self.aircraft.pitch_trim = np.clip(self.aircraft.pitch_trim, -5.0, 5.0)
                if event.key == pygame.K_END: self.aircraft.thrust_input = 0
                if event.key == pygame.K_HOME: self.aircraft.thrust_input = 100
                if event.key == pygame.K_1: self.camera.mode = "cockpit"
                if event.key == pygame.K_2: self.camera.mode = "follow_mouse_orbit"; self.camera.distance=max(15,self.camera.distance)
                if event.key == pygame.K_3: self.camera.mode = "external_fixed_mouse_orbit"; self.camera.distance=max(25,self.camera.distance)
                if event.key == pygame.K_TAB:
                    self.aircraft.autopilot_on = not self.aircraft.autopilot_on
                    if self.aircraft.autopilot_on: self.aircraft.ap_target_altitude = self.aircraft.y; self.aircraft.ap_target_heading = self.aircraft.yaw; self.aircraft.ap_target_speed = math.sqrt(self.aircraft.vx**2 + self.aircraft.vy**2 + self.aircraft.vz**2); print("AP ON.")
                    else: print("AP OFF.")
                if event.key == pygame.K_n: self.aircraft.nav_mode_active = not self.aircraft.nav_mode_active; print(f"NAV mode {'ACTIVE' if self.aircraft.nav_mode_active else 'INACTIVE'}")
                if event.key == pygame.K_r: self.restart_flight()
        elif self.game_state == GameState.DEBRIEF:
            for btn in self.debrief_buttons: btn.handle_event(event)
        if event.type == pygame.QUIT: self.running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.game_state == GameState.PLAYING: self.toggle_pause()
                elif self.game_state == GameState.PAUSED: self.toggle_pause()
                elif self.game_state == GameState.MENU: self.quit_game()
                elif self.game_state == GameState.DEBRIEF: self.go_to_main_menu()
            if event.key == pygame.K_p and (self.game_state == GameState.PLAYING or self.game_state == GameState.PAUSED) : self.toggle_pause()

    def update(self, dt):
        if self.game_state == GameState.PLAYING and self.aircraft:
            self.handle_continuous_input(dt)
            self.aircraft.update(dt, self.weather, self.sound_manager)
            self.weather.update(dt)
            self.camera.update(self.aircraft, dt)
            
            # Minimal sound update logic if sounds are re-enabled
            # if self.sound_manager.enabled and self.aircraft.engine_on and self.aircraft.fuel > 0:
            #     if self.sound_manager.engine_channel is None or not self.sound_manager.engine_channel.get_busy():
            #          self.sound_manager.play_engine_sound(self.aircraft.engine_rpm_percent, self.aircraft.type)
            #     elif self.sound_manager.engine_channel:
            #          self.sound_manager.engine_channel.set_volume(0.05 + (self.aircraft.engine_rpm_percent / 100.0) * 0.25)
            # elif self.sound_manager.engine_channel and self.sound_manager.engine_channel.get_busy():
            #     self.sound_manager.engine_channel.stop()

            if self.aircraft.crashed or \
               (self.aircraft.on_ground and math.sqrt(self.aircraft.vx**2 + self.aircraft.vz**2) < 0.2 and self.aircraft.landed_successfully):
                self.game_state = GameState.DEBRIEF
                # self.sound_manager.stop_all_sounds()
                # self.sound_manager.enabled = False
                pygame.mouse.set_visible(True); pygame.event.set_grab(False)
    
    def render(self):
        if self.game_state == GameState.MENU: self.renderer.draw_main_menu(self.menu_buttons, self.selected_aircraft_type)
        elif self.game_state == GameState.PAUSED: self.renderer.draw_pause_menu(self.pause_buttons, self.show_help_in_pause, self.aircraft_controls_info)
        elif self.game_state == GameState.DEBRIEF and self.aircraft: self.renderer.draw_debrief_screen(self.aircraft, self.debrief_buttons)
        elif self.game_state == GameState.PLAYING and self.aircraft:
            self.renderer.draw_horizon_and_sky(self.aircraft, self.camera)
            self.renderer.draw_terrain_features(self.camera, self.terrain, self.weather)
            self.renderer.draw_aircraft_model(self.aircraft, self.camera)
            self.renderer.draw_weather_effects(self.weather, self.camera, self.aircraft)
            nav_data = self.aircraft.get_nav_display_info()
            self.renderer.draw_hud(self.aircraft, self.weather, self.camera, nav_data)
            pygame.display.flip()
        else: self.screen.fill(BLACK); pygame.display.flip()

    def run(self):
        self.running = True
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)
            for event in pygame.event.get(): self.handle_event(event)
            self.update(dt)
            self.render()
        # self.sound_manager.stop_all_sounds()
        pygame.quit()

if __name__ == "__main__":
    try: open("cockpit_overlay.png", "rb").close()
    except FileNotFoundError:
        try:
            surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            frame_color = (80, 90, 100, 180)
            pygame.draw.rect(surf, frame_color, (0, 0, WIDTH, 120))
            pygame.draw.rect(surf, frame_color, (0, HEIGHT - 80, WIDTH, 80))
            pygame.draw.rect(surf, frame_color, (0, 0, 80, HEIGHT))
            pygame.draw.rect(surf, frame_color, (WIDTH - 80, 0, 80, HEIGHT))
            pygame.image.save(surf, "cockpit_overlay.png")
            print("Created dummy cockpit_overlay.png")
        except Exception as e_img: print(f"Could not create dummy cockpit_overlay.png: {e_img}")
    
    print("Sound file checks/creation are disabled for now.")

    sim = FlightSimulator()
    sim.run()