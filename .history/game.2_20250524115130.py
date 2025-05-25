
import pygame
import pygame.gfxdraw # For anti-aliased shapes
import math
import random
import numpy as np
# import json # Not strictly used, can be removed if no file I/O
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
import time

# Initialize Pygame
pygame.init()
pygame.mixer.init() # Initialize the mixer

# Initialize Pygame
pygame.init()
pygame.mixer.init() # Initialize the mixer

# Constants
WIDTH, HEIGHT = 1600, 1000
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (135, 206, 235) # <<<<<<<<<<<<<<<<<<<<<<<<<<< ADD THIS LINE BACK / UNCOMMENT
DARK_BLUE = (0, 102, 204)
SKY_BLUE_HORIZON = (173, 216, 230) # Light blue for horizon
SKY_BLUE_ZENITH = (20, 60, 120)     # Darker blue for upper sky
SUN_COLOR = (255, 255, 200)
GREEN = (34, 139, 34)
DARK_GREEN = (0, 100, 0)
GROUND_COLOR_BASE = (80, 120, 45)
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
RUNWAY_MARKING_WHITE = (220, 220, 220)
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
    HELICOPTER = "Helicopter" # Note: flight model not really for helis
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
class LightSource:
    direction: np.ndarray = field(default_factory=lambda: np.array([0.7, 0.8, -0.5])) # Pointing from top-right-ish
    ambient_intensity: float = 0.35
    diffuse_intensity: float = 0.65
    color: Tuple[int,int,int] = WHITE

    def __post_init__(self):
        norm = np.linalg.norm(self.direction)
        if norm > 0:
            self.direction = self.direction / norm


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
    cl_alpha: float = 2 * math.pi * 0.08 # Lift curve slope per degree
    engine_spool_rate: float = 0.2
    # Model scaling parameters
    fuselage_length_mult: float = 1.0
    fuselage_radius_mult: float = 1.0
    wing_span_mult: float = 1.0
    tail_height_mult: float = 1.0


@dataclass
class Waypoint:
    x: float
    z: float
    altitude: float
    name: str
    waypoint_type: str = "NAV" # NAV, AIRPORT, FIX
    required_speed: Optional[float] = None
    required_altitude_tolerance: float = 100.0 # meters

class SoundManager:
    def __init__(self):
        self.sounds: Dict[str, Optional[pygame.mixer.Sound]] = {}
        self.engine_channel: Optional[pygame.mixer.Channel] = None
        self.warning_channel: Optional[pygame.mixer.Channel] = None
        self.ambient_channel: Optional[pygame.mixer.Channel] = None
        self.enabled = False # Sounds disabled by default now
        # self.load_sounds() # Don't load external files

    def load_sounds(self): # Kept for structure, but does nothing now
        pass

    def create_synthetic_sound(self, frequency, duration=0.1, volume=0.1, shape='sine'):
        if not self.enabled or not pygame.mixer.get_init(): return None
        return None

    def play_engine_sound(self, rpm_percent, engine_type=AircraftType.AIRLINER):
        if not self.enabled: return
        pass

    def play_sound(self, sound_name, loops=0):
        if not self.enabled: return
        pass

    def play_warning_beep(self, frequency=800, duration=0.2, volume=0.3):
        if not self.enabled: return
        pass

    def stop_all_sounds(self):
        if not pygame.mixer.get_init(): return
        if self.engine_channel: self.engine_channel.stop()
        if self.warning_channel: self.warning_channel.stop()
        if self.ambient_channel: self.ambient_channel.stop()

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
                    'type': random.choice(['cumulus', 'stratus', 'cumulonimbus']) # Not used for rendering yet
                }
                self.cloud_layers.append(layer)
        self.generate_cloud_particles()

    def generate_cloud_particles(self):
        self.cloud_particles = []
        if self.type in [WeatherType.CLOUDY, WeatherType.STORM, WeatherType.RAIN, WeatherType.SNOW, WeatherType.FOG]:
            for layer in self.cloud_layers:
                for _ in range(int(layer['coverage'] * 25)): # Increased particle density slightly
                    particle = {
                        'x': random.uniform(-20000, 20000), # Wider distribution
                        'z': random.uniform(-20000, 20000),
                        'y': layer['altitude'] + random.uniform(-layer['thickness']/2, layer['thickness']/2),
                        'size': random.uniform(300, 1000) * layer['coverage'], # Larger base size
                        'opacity': random.uniform(40, 100) * layer['coverage'], # Slightly less opaque
                        'num_puffs': random.randint(3, 7) # For multi-ellipse clouds
                    }
                    self.cloud_particles.append(particle)

    def update(self, dt):
        # Random weather change (less frequent)
        if random.random() < 0.0001: # Reduced frequency
            if self.type != WeatherType.STORM: # Avoid rapid storm toggling
                old_type = self.type
                self.type = random.choice(list(WeatherType))
                if self.type != old_type:
                    print(f"Weather changing from {old_type.value} to {self.type.value}")
                    self.generate_clouds() # Regenerate clouds on weather type change
                self.update_conditions()

        # Wind gusts
        if random.random() < 0.01:
            self.wind_gusts = random.uniform(0, self.wind_speed * 0.6)
        else:
            self.wind_gusts *= (1 - 0.5 * dt) # More gradual decay

        # Lightning for storms
        if self.type == WeatherType.STORM and random.random() < 0.008: # Slightly more frequent bolts
            self.lightning_strikes.append({
                'x': random.uniform(-15000, 15000),
                'z': random.uniform(-15000, 15000),
                'intensity': random.uniform(0.7, 1.0),
                'time': time.time()
            })

        # Clear old lightning strikes
        current_time = time.time()
        self.lightning_strikes = [s for s in self.lightning_strikes if current_time - s['time'] < 0.30] # Slightly longer flash

    def update_conditions(self):
        # Base clear weather values
        self.visibility = random.uniform(12000, 20000)
        self.wind_speed = random.uniform(0, 15)
        self.turbulence = random.uniform(0, 2)
        self.precipitation = 0
        self.icing_intensity = 0
        self.temperature = 15 # Sea level temp
        self.humidity = 50
        self.cloud_ceiling = 10000 # Effectively unlimited for clear

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
            self.precipitation = random.uniform(3, 7) # mm/hr equivalent for effect strength
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
            self.cloud_ceiling = random.uniform(0, 300) # Ground fog often
        elif self.type == WeatherType.SNOW:
            self.visibility = random.uniform(1000, 4000)
            self.wind_speed = random.uniform(5, 25)
            self.turbulence = random.uniform(2, 5)
            self.precipitation = random.uniform(2, 6)
            self.temperature = random.uniform(-15, 0) # Colder for snow
            self.humidity = random.uniform(70, 90)
            self.cloud_ceiling = random.uniform(300, 2000)
        elif self.type == WeatherType.WIND_SHEAR: # Usually localized, doesn't change global vis much
            self.wind_shear_altitude = random.uniform(500, 3000) # meters AGL
            self.wind_shear_strength = random.uniform(15, 35) # knots difference
            self.turbulence = random.uniform(4, 7) # Associated turbulence
        elif self.type == WeatherType.ICING: # Occurs in specific temp/moisture
            self.icing_intensity = random.uniform(3, 8) # Severity scale
            self.temperature = random.uniform(-10, 2) # Icing conditions temperature range
            self.humidity = random.uniform(85, 100) # High humidity
            self.cloud_ceiling = random.uniform(500, 3000) # Often in clouds
            self.visibility = random.uniform(3000, 8000) # Can be reduced

        # General randomization for some parameters
        self.wind_direction = random.uniform(0, 360)
        self.pressure = random.uniform(995, 1030) # hPa


# Aircraft Class
class Aircraft:
    def __init__(self, x, y, z, aircraft_type: AircraftType):
        self.x = x
        self.y = y # Altitude AGL (or MSL if terrain is implemented that way)
        self.z = z # Forward/backward
        
        self.vx = 0.0 # m/s world X (East/West if yaw=0 is North)
        self.vy = 0.0 # m/s world Y (Vertical)
        self.vz = 0.0 # m/s world Z (North/South if yaw=0 is North)
        
        self.pitch = 0.0 # Degrees, positive = nose up
        self.yaw = 0.0   # Degrees, 0 = North, 90 = East, 180 = South, 270 = West
        self.roll = 0.0  # Degrees, positive = right wing down
        # Rates (degrees per second)
        self.pitch_rate = 0.0
        self.yaw_rate = 0.0
        self.roll_rate = 0.0

        self.thrust_input = 0.0 # Player input % (0-100)
        self.engine_rpm_percent = 0.0 # Actual engine RPM % (affected by spool rate)

        self.crashed = False
        self.on_ground = (y <= 0.1) # Simple ground check
        self.gear_down = True
        self.flaps_setting = 0 # Index in flaps_degrees
        self.flaps_max_setting = 3
        self.flaps_degrees = [0, 10, 25, 40] # Common flap settings
        self.spoilers_deployed = False
        self.brakes_input = 0.0 # 0 to 1 for braking strength
        
        self.autopilot_on = False
        self.ap_target_altitude: Optional[float] = None
        self.ap_target_heading: Optional[float] = None
        self.ap_target_speed: Optional[float] = None
        
        self.engine_on = True # Can be turned off by fuel or failure
        
        # Aircraft configurations
        self.configs = {
            AircraftType.FIGHTER: AircraftConfig("F-16", 120000, 8500, 0.016, 1.6, 30, 8, 650, 3000, 0.1, 18000, 15, 70, 15000, 9.0, 250, engine_count=1, critical_aoa_positive=20.0, cl_alpha=0.11, engine_spool_rate=0.5, fuselage_length_mult=0.9, fuselage_radius_mult=0.8, wing_span_mult=0.8, tail_height_mult=0.9),
            AircraftType.AIRLINER: AircraftConfig("B737", 110000*2, 75000, 0.020, 1.5, 125, 9, 280, 26000, 0.06, 14000, 3, 65, 12500, 2.5, 150, engine_count=2, critical_aoa_positive=16.0, cl_alpha=0.1, engine_spool_rate=0.15, fuselage_length_mult=1.2, fuselage_radius_mult=1.2, wing_span_mult=1.1, tail_height_mult=1.1),
            AircraftType.GLIDER: AircraftConfig("ASK-21", 0, 600, 0.010, 1.8, 17, 26, 70, 0, 0, 10000, 4, 30, 8000, 4.5, 20, engine_count=0, critical_aoa_positive=14.0, cl_alpha=0.1, fuselage_length_mult=0.8, fuselage_radius_mult=0.7, wing_span_mult=1.5, tail_height_mult=0.8),
            AircraftType.CARGO: AircraftConfig("C-130", 4 * 15000, 70000, 0.028, 1.2, 160, 7, 180, 20000, 0.09, 10000, 2, 55, 9000, 2.0, 100, engine_count=4, critical_aoa_positive=15.0, cl_alpha=0.09, engine_spool_rate=0.1, fuselage_length_mult=1.3, fuselage_radius_mult=1.3, wing_span_mult=1.2, tail_height_mult=1.2),
            AircraftType.ULTRALIGHT: AircraftConfig("Quicksilver", 3000, 250, 0.030, 1.4, 15, 10, 30, 50, 0.12, 3000, 5, 20, 2500, 3.0, 20, engine_count=1, critical_aoa_positive=18.0, cl_alpha=0.09, engine_spool_rate=0.3, fuselage_length_mult=0.6, fuselage_radius_mult=0.6, wing_span_mult=0.9, tail_height_mult=0.7),
            AircraftType.HELICOPTER: AircraftConfig("UH-60", 2*1200, 5200, 0.06, 0.4, 20, 5, 80, 1300, 0.15, 6000, 10, 0, 5800, 3.5, 50, engine_count=2, critical_aoa_positive=90.0, cl_alpha=0.05, fuselage_length_mult=1.0, fuselage_radius_mult=1.0, wing_span_mult=0.5, tail_height_mult=0.8), # Wing span here might mean rotor diameter influence
        }
        
        self.type = aircraft_type
        self.config = self.configs[aircraft_type]
        self.fuel = self.config.fuel_capacity # kg
        self.engines_failed = [False] * self.config.engine_count # Status for each engine
        
        self.waypoints: List[Waypoint] = []
        self.current_waypoint_index = 0
        self.nav_mode_active = False # Whether to follow waypoints with AP or show NAV display
        
        # Systems status
        self.electrical_power = True
        self.hydraulic_power = True
        self.avionics_power = True # For HUD/displays
        self.engine_health = [100.0] * self.config.engine_count # % health for each engine
        self.structural_integrity = 100.0 # %
        self.ice_buildup_kg = 0.0 # Mass of ice accumulated
        self.pitot_heat_on = False # For pitot tube icing
        
        # Flight parameters
        self.current_g_force = 1.0
        self.aoa_degrees = 0.0 # Angle of Attack
        self.stall_warning_active = False
        self.overspeed_warning_active = False
        
        # Statistics for debrief
        self.flight_time_sec = 0.0
        self.distance_traveled_m = 0.0
        self.max_altitude_reached = y
        self.max_speed_reached = 0.0
        
        self.touchdown_vertical_speed_mps = 0.0 # For landing score
        self.landing_score = 0.0
        self.landed_successfully = False

        self.pitch_trim = 0.0 # Degrees of elevator trim

        # Control surface effectiveness (can be affected by damage, icing, speed)
        self.elevator_effectiveness = 1.0
        self.aileron_effectiveness = 1.0
        self.rudder_effectiveness = 1.0

        # --- 3D Model Definition ---
        cfg = self.config
        fl = 12.0 * cfg.fuselage_length_mult  # Base fuselage length
        fr = 1.5 * cfg.fuselage_radius_mult   # Base fuselage radius
        ws = 15.0 * cfg.wing_span_mult        # Base wing span
        wc = ws / (cfg.aspect_ratio if cfg.aspect_ratio > 0 else 5.0) # Wing chord
        th = 3.0 * cfg.tail_height_mult         # Tail height
        wt = 0.2 * cfg.fuselage_radius_mult   # Wing thickness factor

        # Define vertices for a generic aircraft shape
        self.model_vertices_local = [
            # Fuselage (box-like) - 8 vertices
            (fr, -fr, fl * 0.6), (-fr, -fr, fl * 0.6), (-fr, fr, fl * 0.6), (fr, fr, fl * 0.6),  # Nose section bottom/top
            (fr, -fr, -fl * 0.4), (-fr, -fr, -fl * 0.4), (-fr, fr, -fl * 0.4), (fr, fr, -fl * 0.4), # Tail section bottom/top

            # Wings (with thickness) - 8 vertices per wing (not fully implemented, using flat planes for now)
            # Right Wing (vertices 8-11 for top, 12-15 for bottom) - simplified as flat for now
            (fr, 0, wc * 0.5), (ws/2, 0, wc*0.3), (ws/2, 0, -wc*0.7), (fr, 0, -wc*0.5), # Simplified Right wing (flat polygon)
            # Left Wing (vertices 12-15 for top, 16-19 for bottom) - simplified as flat for now
            (-fr, 0, wc * 0.5), (-ws/2, 0, wc*0.3), (-ws/2, 0, -wc*0.7), (-fr, 0, -wc*0.5), # Simplified Left wing (flat polygon)

            # Vertical Stabilizer (Tail Fin) - 4 vertices for a surface
            (0, fr, -fl * 0.35), (0, fr + th, -fl * 0.38), (0, fr + th, -fl * 0.45 - wc*0.1), (0, fr, -fl*0.45 - wc*0.05), # Top, tip-front, tip-rear, root-rear
            
            # Horizontal Stabilizers - 4 vertices per side
            # Right HStab
            (fr*0.5, 0, -fl*0.35), (ws/3.5, 0, -fl*0.38), (ws/3.5, 0, -fl*0.42 - wc*0.05), (fr*0.5, 0, -fl*0.40 - wc*0.05),
            # Left HStab
            (-fr*0.5, 0, -fl*0.35), (-ws/3.5, 0, -fl*0.38), (-ws/3.5, 0, -fl*0.42 - wc*0.05), (-fr*0.5, 0, -fl*0.40 - wc*0.05),
        ]
        
        # Define colors for parts
        fuselage_color = GRAY if aircraft_type != AircraftType.FIGHTER else DARK_GRAY
        wing_color = LIGHT_GRAY if aircraft_type != AircraftType.FIGHTER else SILVER
        tail_color = SILVER
        
        self.model_colors = {
            "fuselage": fuselage_color,
            "wing": wing_color,
            "tail": tail_color,
            "cockpit": (100,150,200) # Bluish tint for cockpit windows
        }
        
        # Define faces (list of vertex indices and color key)
        # Ensure CCW winding for outward normals, or use normal_mult = -1
        self.model_faces = [
            # Fuselage
            {"v_indices": [0, 1, 2, 3], "color": "fuselage", "normal_mult": -1},  # Front face (nose) - if positive Z is forward
            {"v_indices": [7, 6, 5, 4], "color": "fuselage", "normal_mult": -1},  # Rear face
            {"v_indices": [3, 2, 6, 7], "color": "fuselage"},  # Top face
            {"v_indices": [4, 5, 1, 0], "color": "fuselage"},  # Bottom face
            {"v_indices": [0, 3, 7, 4], "color": "fuselage"},  # Right face
            {"v_indices": [1, 5, 6, 2], "color": "fuselage"},  # Left face
            # Cockpit (superimposed on front-top fuselage)
            {"v_indices": [ (fr*0.8, fr*0.8, fl*0.55), (-fr*0.8, fr*0.8, fl*0.55), # c0, c1
                            (-fr*0.8, fr*1.5, fl*0.45), (fr*0.8, fr*1.5, fl*0.45) ], # c2, c3
             "color": "cockpit", "normal_mult": 1, "is_custom_verts": True}, # Windshield
            {"v_indices": [ (fr*0.8, fr*1.5, fl*0.45), (fr*0.8, fr*0.8, fl*0.35), #c3, c4
                            (fr*0.6, fr*0.8, fl*0.25), (fr*0.7, fr*1.5, fl*0.28) ], #c5, c6
             "color": "cockpit", "normal_mult": 1, "is_custom_verts": True}, # Right side window
            {"v_indices": [ (-fr*0.8, fr*1.5, fl*0.45), (-fr*0.8, fr*0.8, fl*0.35), #c2, c7 (like c4 but -x)
                            (-fr*0.6, fr*0.8, fl*0.25), (-fr*0.7, fr*1.5, fl*0.28) ], #c8, c9 (like c5,c6 but -x)
             "color": "cockpit", "normal_mult": -1, "is_custom_verts": True}, # Left side window (flipped normal)

            # Wings (using simplified flat vertices 8-11 for R, 12-15 for L)
            {"v_indices": [8, 9, 10, 11], "color": "wing"}, # Right Wing (top)
            {"v_indices": [11, 10, 9, 8], "color": "wing"}, # Right Wing (bottom)
            {"v_indices": [12, 13, 14, 15], "color": "wing"},# Left Wing (top)
            {"v_indices": [15, 14, 13, 12], "color": "wing"},# Left Wing (bottom)

            # Vertical Stabilizer (vertices 16-19)
            {"v_indices": [16, 17, 18, 19], "color": "tail"}, # Right side of VStab
            {"v_indices": [19, 18, 17, 16], "color": "tail"}, # Left side of VStab

            # Horizontal Stabilizers
            # Right (vertices 20-23)
            {"v_indices": [20, 21, 22, 23], "color": "tail"}, # Top
            {"v_indices": [23, 22, 21, 20], "color": "tail"}, # Bottom
            # Left (vertices 24-27)
            {"v_indices": [24, 25, 26, 27], "color": "tail"}, # Top
            {"v_indices": [27, 26, 25, 24], "color": "tail"}, # Bottom
        ]
        # Original model_lines is not used for solid rendering anymore
        # self.model_lines = [ ... ]
        
    def get_current_mass(self):
        return self.config.mass + (self.fuel * 0.8) + self.ice_buildup_kg # Fuel density ~0.8 kg/L

    def get_flaps_deflection(self):
        return self.flaps_degrees[self.flaps_setting]

    def update_engine_rpm(self, dt):
        # Target RPM is thrust_input, but clamp to idle if fuel is present
        target_rpm = self.thrust_input
        idle_rpm = 0
        if self.type != AircraftType.GLIDER and self.engine_on and self.fuel > 0:
            idle_rpm = 20 if self.type == AircraftType.AIRLINER else 25
            if self.thrust_input < idle_rpm :
                 target_rpm = idle_rpm
        
        diff = target_rpm - self.engine_rpm_percent
        change = self.config.engine_spool_rate * 100 * dt # Max % change per second
        
        if abs(diff) < change:
            self.engine_rpm_percent = target_rpm
        else:
            self.engine_rpm_percent += math.copysign(change, diff)
        
        self.engine_rpm_percent = np.clip(self.engine_rpm_percent, 0, 100)
        if self.fuel <= 0 or not self.engine_on:
            self.engine_rpm_percent = np.clip(self.engine_rpm_percent - 30*dt, 0, 100) # Engine spools down if off/no fuel


    def calculate_aerodynamics(self, air_density, current_speed_mps, weather: Weather):
        q = 0.5 * air_density * current_speed_mps**2 # Dynamic pressure

        # Angle of Attack (AoA) calculation
        if current_speed_mps > 1: # Avoid division by zero
            # Velocity vector in body frame (simplified, assuming vx_body is along longitudinal axis)
            # This is an approximation; true AoA needs velocity relative to aircraft body axes.
            # For simplicity, we use world velocity components and aircraft pitch.
            horizontal_speed_world = math.sqrt(self.vx**2 + self.vz**2)
            if horizontal_speed_world > 0.1:
                 flight_path_angle_rad_world = math.atan2(self.vy, horizontal_speed_world)
                 self.aoa_degrees = self.pitch - math.degrees(flight_path_angle_rad_world)
            else: # Pure vertical flight
                 self.aoa_degrees = self.pitch - math.copysign(90, self.vy) if abs(self.vy) > 0.1 else self.pitch
        else:
            self.aoa_degrees = self.pitch # At very low speeds, AoA is effectively pitch
        
        self.aoa_degrees = np.clip(self.aoa_degrees, -30, 30) # Clamp AoA to a reasonable range

        # Lift Coefficient (Cl)
        cl = 0.0
        cl_from_aoa = self.config.cl_alpha * self.aoa_degrees
        
        # Stall model
        if self.aoa_degrees > self.config.critical_aoa_positive:
            self.stall_warning_active = True
            # Gradual lift reduction past critical AoA
            overshoot = self.aoa_degrees - self.config.critical_aoa_positive
            cl = self.config.lift_coefficient_max - overshoot * 0.05 
            cl = max(0.1, cl) # Still some lift in stall
        elif self.aoa_degrees < self.config.critical_aoa_negative:
            self.stall_warning_active = True
            # Similar for negative stall
            overshoot = abs(self.aoa_degrees - self.config.critical_aoa_negative)
            cl = -self.config.lift_coefficient_max + overshoot * 0.05
            cl = min(-0.1, cl)
        else:
            self.stall_warning_active = False
            cl = cl_from_aoa
        
        # Flaps effect on Cl (increases max lift and Cl at given AoA)
        cl_flaps_increment = (self.get_flaps_deflection() / 40.0) * 0.7 # Max 0.7 Cl increase from flaps
        cl += cl_flaps_increment
        # Clamp Cl to overall max/min possible for the airfoil
        cl = np.clip(cl, -self.config.lift_coefficient_max -0.4, self.config.lift_coefficient_max + 0.4)


        # Drag Coefficient (Cd)
        cd_base = self.config.drag_coefficient_base # Parasitic drag
        # Induced drag (more significant at high AoA / low speed)
        cd_induced = (cl**2) / (math.pi * 0.75 * self.config.aspect_ratio) if self.config.aspect_ratio > 0 else 0 # 0.75 is Oswald efficiency
        
        cd_flaps = (self.get_flaps_deflection() / 40.0)**1.5 * 0.06 # Flaps add significant drag
        cd_gear = 0.020 if self.gear_down else 0.002 # Gear drag
        cd_spoilers = 0.08 if self.spoilers_deployed else 0.0 # Spoilers/Speedbrakes
        cd_ice = self.ice_buildup_kg * 0.0002 # Drag from ice accumulation

        cd_total = cd_base + cd_induced + cd_flaps + cd_gear + cd_spoilers + cd_ice

        # Calculate forces
        lift_force = cl * q * self.config.wing_area
        drag_force = cd_total * q * self.config.wing_area

        # Spoilers reduce lift
        if self.spoilers_deployed:
            lift_force *= 0.65 # Reduce lift by 35%

        # Control surface effectiveness based on dynamic pressure (airspeed)
        # Stall speed is a reference point for when controls become less effective
        # Effectiveness scales with q, up to a certain point.
        # Simplified: full effectiveness above ~1.5x stall speed, reduced below.
        q_at_stall_1_5 = 0.5 * 1.225 * (self.config.stall_speed_clean * 1.5)**2
        effectiveness_factor = np.clip(q / q_at_stall_1_5, 0.1, 1.0) # At least 10% effective
        self.elevator_effectiveness = effectiveness_factor
        self.aileron_effectiveness = effectiveness_factor
        self.rudder_effectiveness = effectiveness_factor


        return lift_force, drag_force

    def apply_forces_and_torques(self, dt, lift, drag, thrust_force, weather: Weather, current_speed_mps):
        current_mass = self.get_current_mass()
        if current_mass <= 0: return # Avoid division by zero if mass is invalid

        gravity_force_y = -9.81 * current_mass # World frame

        # Aircraft orientation (radians)
        p_rad, y_rad, r_rad = math.radians(self.pitch), math.radians(self.yaw), math.radians(self.roll)
        
        # Rotation matrix components (Body to World)
        # Simplified: Z_body is forward, Y_body is up, X_body is right
        # Thrust acts along Z_body (forward)
        # Lift acts along Y_body (upwards relative to wings)
        # Drag acts opposite to velocity vector (simplification: along -Z_body if no sideslip)

        cos_p, sin_p = math.cos(p_rad), math.sin(p_rad)
        cos_y, sin_y = math.cos(y_rad), math.sin(y_rad)
        cos_r, sin_r = math.cos(r_rad), math.sin(r_rad)

        # --- Transform forces from body to world frame ---
        # Thrust vector (along body's Z-axis) in world frame
        # Z_body_world = (cos_p * sin_y, sin_p, cos_p * cos_y) - This is for yaw first, then pitch.
        # If using standard aerospace sequence (yaw, pitch, roll):
        # Z_body_world_x = sin_y * cos_p
        # Z_body_world_y = sin_p
        # Z_body_world_z = cos_y * cos_p
        
        # For a standard ZYX rotation order (Yaw, Pitch, Roll):
        # Direction of thrust (aircraft's longitudinal axis) in world coordinates
        thrust_dir_world_x = cos_p * sin_y
        thrust_dir_world_y = sin_p
        thrust_dir_world_z = cos_p * cos_y
        
        thrust_fx = thrust_force * thrust_dir_world_x
        thrust_fy = thrust_force * thrust_dir_world_y
        thrust_fz = thrust_force * thrust_dir_world_z
        
        # Lift vector (aircraft's Y-axis, perpendicular to wings) in world coordinates
        # Y_body_world_x = sin_y * sin_p * sin_r + cos_y * cos_r
        # Y_body_world_y = cos_p * sin_r
        # Y_body_world_z = cos_y * sin_p * sin_r - sin_y * cos_r
        # A simpler common one for lift direction (assuming roll transforms the pitch-yaw frame):
        lift_dir_world_x = -cos_p * sin_r * cos_y - sin_p * sin_y # Mistake in derivation, standard way:
        lift_dir_world_x = (cos_r * sin_p * sin_y - sin_r * cos_y)
        lift_dir_world_y = (cos_r * cos_p)
        lift_dir_world_z = (cos_r * sin_p * cos_y + sin_r * sin_y)

        lift_fx = lift * lift_dir_world_x
        lift_fy = lift * lift_dir_world_y
        lift_fz = lift * lift_dir_world_z

        # Drag force (opposite to velocity vector)
        if current_speed_mps > 0.1:
            drag_fx = -drag * (self.vx / current_speed_mps)
            drag_fy = -drag * (self.vy / current_speed_mps)
            drag_fz = -drag * (self.vz / current_speed_mps)
        else:
            drag_fx, drag_fy, drag_fz = 0,0,0
        
        # Wind effect (as a force/acceleration) - simplified
        # Wind speed in m/s
        wind_speed_mps = weather.wind_speed * 0.51444 # Knots to m/s
        wind_dir_rad = math.radians(weather.wind_direction - 90) # Convert to math angle (0=East)
        
        # Wind components relative to aircraft's current velocity (causes drift)
        # This is a simplification; true wind effect is on airspeed vector for aero calculations
        # Here, apply as a direct force/acceleration difference
        # Relative wind: (wind_vel - aircraft_vel)
        # For simplicity, let's assume wind creates a small acceleration towards its direction
        # if the aircraft is slower than the wind in that component.
        # This is not aerodynamically perfect but creates a drift effect.
        wind_effect_x = wind_speed_mps * math.cos(wind_dir_rad)
        wind_effect_z = wind_speed_mps * math.sin(wind_dir_rad)

        # A simple model for wind force: proportional to difference between wind and aircraft velocity
        # This is more like a "push" from the wind, rather than changing the relative airflow for lift/drag.
        # (A more accurate model would adjust vx, vy, vz used in AoA/dynamic pressure BEFORE force calculation)
        wind_force_factor = 0.1 * current_mass # Arbitrary factor
        wind_fx = (wind_effect_x - self.vx) * wind_force_factor * dt # Small nudge
        wind_fz = (wind_effect_z - self.vz) * wind_force_factor * dt
        
        # Total forces in world frame
        total_fx = thrust_fx + drag_fx + lift_fx + wind_fx
        total_fy = thrust_fy + drag_fy + lift_fy + gravity_force_y
        total_fz = thrust_fz + drag_fz + lift_fz + wind_fz

        # --- Rotational Dynamics ---
        # Damping based on airspeed and control effectiveness (already factored into rates)
        # Pitch rate damping (natural aerodynamic stability)
        # Roll rate damping (wings resist rolling)
        # Yaw rate damping (fin resists yawing)
        # These factors increase with q (dynamic pressure)
        q_factor_damping = np.clip(current_speed_mps / (self.config.stall_speed_clean * 2.0), 0.1, 1.0)

        damping_factor_pitch = (0.8 + self.elevator_effectiveness * 0.5) * q_factor_damping
        damping_factor_roll = (1.0 + self.aileron_effectiveness * 0.8) * q_factor_damping
        damping_factor_yaw = (0.5 + self.rudder_effectiveness * 0.3) * q_factor_damping

        # Apply damping: rate reduces proportionally to itself
        # The control inputs modify these rates elsewhere (handle_continuous_input)
        self.pitch_rate *= (1 - damping_factor_pitch * dt * abs(self.pitch_rate) * 0.05) # Reduce oscillation
        self.roll_rate *= (1 - damping_factor_roll * dt * abs(self.roll_rate) * 0.08)
        self.yaw_rate *= (1 - damping_factor_yaw * dt * abs(self.yaw_rate) * 0.03)

        # Update orientation
        self.pitch += self.pitch_rate * dt
        self.roll += self.roll_rate * dt
        self.yaw = (self.yaw + self.yaw_rate * dt + 360) % 360 # Keep yaw in 0-360

        # Clamp pitch and roll
        self.pitch = np.clip(self.pitch, -90, 90)
        self.roll = ((self.roll + 180) % 360) - 180 # Keep roll in -180 to 180

        # --- Translational Dynamics (Newton's 2nd Law) ---
        ax = total_fx / current_mass
        ay = total_fy / current_mass
        az = total_fz / current_mass
        
        # Update velocity
        self.vx += ax * dt
        self.vy += ay * dt
        self.vz += az * dt

        # Check for touchdown this frame
        if self.y > 0.1 and (self.y + self.vy * dt) <= 0.1: # Transitioning to on_ground
            self.touchdown_vertical_speed_mps = self.vy # Record for landing score

        # Update position
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        
        # Update flight statistics
        self.max_altitude_reached = max(self.max_altitude_reached, self.y)
        self.max_speed_reached = max(self.max_speed_reached, current_speed_mps)

        # G-force calculation (simplified: based on vertical acceleration relative to gravity)
        # More accurate G-force would consider centripetal acceleration in turns.
        # current_ay_body = (ay - gravity_force_y/current_mass) # This isn't quite right.
        # G-force is felt lift / weight, or total acceleration in body Y / g
        # For simplicity, use vertical world acceleration component relative to 1G.
        g_vertical = (ay - (-9.81)) / 9.81 if current_mass > 0 else 1.0 # Component of accel beyond gravity
        self.current_g_force = abs(g_vertical) # Simple approximation

        # Structural damage from Over-G
        if self.current_g_force > self.config.max_g_force and not self.on_ground:
            damage = (self.current_g_force - self.config.max_g_force) * 10 * dt # Damage factor
            self.structural_integrity = max(0, self.structural_integrity - damage)
            if self.structural_integrity <= 0 and not self.crashed:
                self.crashed = True; print("CRASH: Over-G Structural Failure")

    def update_autopilot(self, dt, current_speed_mps):
        if not self.autopilot_on or self.crashed: return

        # PID controllers (simplified P or PD for now)
        # Altitude hold
        ap_p_alt, ap_i_alt, ap_d_alt = 0.02, 0.001, 0.05 # PID gains for altitude
        # Heading hold
        ap_p_hdg, ap_i_hdg, ap_d_hdg = 0.4, 0.02, 0.1   # PID gains for heading
        # Speed hold
        ap_p_spd = 0.8 # Proportional gain for speed (adjusts thrust)

        # Retrieve or initialize persistent PID terms
        ap_integral_alt = getattr(self, 'ap_integral_alt', 0)
        ap_prev_alt_error = getattr(self, 'ap_prev_alt_error', 0)
        ap_integral_hdg = getattr(self, 'ap_integral_hdg', 0)
        ap_prev_hdg_error = getattr(self, 'ap_prev_hdg_error', 0)

        if self.ap_target_altitude is not None:
            alt_error = self.ap_target_altitude - self.y
            ap_integral_alt += alt_error * dt
            ap_integral_alt = np.clip(ap_integral_alt, -100, 100) # Anti-windup
            derivative_alt = (alt_error - ap_prev_alt_error) / dt if dt > 0 else 0
            
            # Desired pitch rate command from PID
            target_pitch_rate_cmd = (ap_p_alt * alt_error) + \
                                    (ap_i_alt * ap_integral_alt) + \
                                    (ap_d_alt * derivative_alt)
            # Clamp command to reasonable aircraft pitch rates
            target_pitch_rate_cmd = np.clip(target_pitch_rate_cmd, -self.config.turn_rate*0.3, self.config.turn_rate*0.3) # Max 30% of max turn rate
            
            # Smoothly adjust aircraft's actual pitch rate towards command
            self.pitch_rate += (target_pitch_rate_cmd - self.pitch_rate) * 0.1 * (dt*FPS if dt > 0 else 1) # Smoothing factor
            self.ap_prev_alt_error = alt_error

        if self.ap_target_heading is not None:
            # Error is shortest angle to target heading (-180 to 180)
            heading_error = (self.ap_target_heading - self.yaw + 540) % 360 - 180
            ap_integral_hdg += heading_error * dt
            ap_integral_hdg = np.clip(ap_integral_hdg, -180, 180) # Anti-windup
            derivative_hdg = (heading_error - ap_prev_hdg_error) / dt if dt > 0 else 0

            # Desired roll angle command (degrees) to achieve heading change
            # A positive heading error (target is to the right) requires a right roll.
            target_roll_cmd_deg = (ap_p_hdg * heading_error) + \
                                  (ap_i_hdg * ap_integral_hdg) + \
                                  (ap_d_hdg * derivative_hdg)
            # Clamp target roll to a max bank angle (e.g., 25-30 degrees)
            target_roll_cmd_deg = np.clip(target_roll_cmd_deg, -25, 25)

            # Command roll rate to achieve target roll angle
            roll_error_to_target = target_roll_cmd_deg - self.roll
            # Adjust roll rate towards this error (P controller for roll angle)
            self.roll_rate += (roll_error_to_target * 0.5) * (dt*FPS if dt > 0 else 1) # Smoothing factor
            self.ap_prev_hdg_error = heading_error

        if self.ap_target_speed is not None:
            speed_error_mps = self.ap_target_speed - current_speed_mps
            # Adjust thrust input based on speed error (P controller)
            # Thrust adjustment is % change to thrust_input
            thrust_adj_percent = np.clip(speed_error_mps * ap_p_spd, -20, 20) # Max 20% thrust change per update cycle
            self.thrust_input = np.clip(self.thrust_input + thrust_adj_percent * dt, 0, 100)
        
        # Store PID terms for next iteration
        self.ap_integral_alt = ap_integral_alt
        self.ap_integral_hdg = ap_integral_hdg


    def update(self, dt, weather: Weather, sound_manager: SoundManager):
        if self.crashed:
            # Simple crash physics: reduce speed, stop rotation
            self.vx *= (1 - 0.5 * dt)
            self.vz *= (1 - 0.5 * dt)
            self.vy =0 # Stick to ground
            self.pitch_rate = 0; self.roll_rate = 0; self.yaw_rate = 0;
            return

        self.flight_time_sec += dt
        old_x, old_z = self.x, self.z # For distance calculation

        self.update_engine_rpm(dt) # Update engine RPM based on thrust input and spool rate

        # --- Environmental Factors ---
        # Air density decreases with altitude (simplified ISA model)
        air_density = 1.225 * math.exp(-self.y / 8500) # 8500m is scale height
        current_speed_mps = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)

        # --- Aerodynamics ---
        lift, drag = self.calculate_aerodynamics(air_density, current_speed_mps, weather)

        # --- Propulsion ---
        # Calculate available thrust based on engine health and failures
        num_active_engines = sum(1 for i in range(self.config.engine_count) if not self.engines_failed[i])
        health_factor = sum((self.engine_health[i] / 100.0) for i in range(self.config.engine_count) if not self.engines_failed[i])
        
        total_available_thrust_factor = (health_factor / num_active_engines) if num_active_engines > 0 else 0
        if self.config.engine_count == 0: total_available_thrust_factor = 0 # Glider

        actual_thrust_percent = self.engine_rpm_percent if self.engine_on and self.fuel > 0 else 0
        thrust_force = (actual_thrust_percent / 100.0) * self.config.max_thrust * total_available_thrust_factor

        # --- Apply Physics ---
        self.apply_forces_and_torques(dt, lift, drag, thrust_force, weather, current_speed_mps)
        
        # --- Autopilot ---
        self.update_autopilot(dt, current_speed_mps)
        
        # --- Systems Updates ---
        # Fuel consumption
        if self.engine_on and self.config.engine_count > 0 and self.fuel > 0:
            # Consumption scales with RPM (approx power) and number of active engines
            # A more realistic model would use Thrust Specific Fuel Consumption (TSFC)
            consumption_rate_per_engine_sec = self.config.fuel_consumption * (self.engine_rpm_percent / 100.0)**1.5 # Base consumption rate
            total_consumption_sec = consumption_rate_per_engine_sec * num_active_engines
            fuel_consumed_kg = total_consumption_sec * dt
            self.fuel = max(0, self.fuel - fuel_consumed_kg)

            if self.fuel == 0 and self.engine_on:
                print("Fuel Empty! Engine(s) shutting down.")
                self.engine_on = False # Engines flame out
                # Could also set individual engines_failed here.

        # --- Ground Interaction ---
        terrain_height = 0 # Assuming flat terrain for now at y=0
        if self.y <= terrain_height + 0.1 and not self.on_ground: # Just touched down
            self.on_ground = True
            self.y = terrain_height # Snap to ground
            
            impact_g = abs(self.touchdown_vertical_speed_mps / 9.81) # Gs at touchdown
            horizontal_speed_kts_touchdown = current_speed_mps * 1.94384
            print(f"Touchdown: VS={self.touchdown_vertical_speed_mps:.2f}m/s ({impact_g:.2f}G), HS={horizontal_speed_kts_touchdown:.1f}kts, Roll={self.roll:.1f}°")

            # Landing success/crash criteria
            max_safe_vs_mps = -3.0 # Approx -600 fpm
            max_safe_hs_mps_landing = self.config.stall_speed_clean * 1.8 # Don't land too fast
            
            # Check for hard landing / improper configuration
            if not self.gear_down or \
               self.touchdown_vertical_speed_mps < max_safe_vs_mps * 1.5 or \
               current_speed_mps > max_safe_hs_mps_landing or \
               abs(self.roll) > 10 or abs(self.pitch) > 15: # Too much bank or pitch
                self.crashed = True
                self.structural_integrity = 0 # Severe damage
                print("CRASH: Hard or improper landing.")
            else: # Successful landing
                self.landed_successfully = True
                self.vy = 0 # Stop vertical movement
                # Calculate landing score
                score = 100
                # Penalty for vertical speed (target ~ -0.5 to -1 m/s)
                score -= min(50, abs(self.touchdown_vertical_speed_mps - (-0.75)) * 25)
                # Penalty for horizontal speed (target ~1.2-1.3x stall speed)
                score -= min(30, abs(current_speed_mps - self.config.stall_speed_clean * 1.2) * 2)
                # Penalty for roll
                score -= min(20, abs(self.roll) * 3)
                self.landing_score = max(0, int(score))
                print(f"Successful Landing! Score: {self.landing_score}")

        if self.on_ground:
            self.y = terrain_height # Stay on ground
            self.vy = 0 # No vertical velocity
            # Dampen rotation quickly on ground
            self.pitch_rate *= (1 - 0.8 * dt) 
            self.roll_rate *= (1 - 0.95 * dt) 

            # Ground friction and braking
            friction_coeff_rolling = 0.02 # Rolling resistance
            friction_coeff_braking = 0.6 if current_speed_mps > 5 else 0.3 # Brakes more effective at higher speeds
            total_friction_coeff = friction_coeff_rolling + self.brakes_input * friction_coeff_braking
            
            horizontal_speed_ground = math.sqrt(self.vx**2 + self.vz**2)
            if horizontal_speed_ground > 0.01:
                friction_deceleration = total_friction_coeff * 9.81 # Decel = mu * g
                decel_this_frame = min(friction_deceleration * dt, horizontal_speed_ground) # Don't overshoot zero
                # Apply deceleration opposite to velocity vector
                self.vx -= (self.vx / horizontal_speed_ground) * decel_this_frame
                self.vz -= (self.vz / horizontal_speed_ground) * decel_this_frame
            else: # Stopped
                self.vx, self.vz = 0,0
            
            # Wing strike check
            if abs(self.roll) > 30 and current_speed_mps > 5: # Wingtip hits ground
                if not self.crashed: print("CRASH: Wing strike on ground!")
                self.crashed = True; self.structural_integrity = 0

        # --- Warnings and Limits ---
        # Overspeed warning
        if current_speed_mps > self.config.max_speed * 0.98 and not self.overspeed_warning_active:
            self.overspeed_warning_active = True
            sound_manager.play_sound('stall_warning') # Re-use stall for overspeed for now
        elif current_speed_mps < self.config.max_speed * 0.95: # Hysteresis
            self.overspeed_warning_active = False

        if self.stall_warning_active: # Continuously play if stalling
            sound_manager.play_sound('stall_warning')

        # Update distance traveled (ground distance)
        dx_frame = self.x - old_x; dz_frame = self.z - old_z
        self.distance_traveled_m += math.sqrt(dx_frame**2 + dz_frame**2)

        # Altitude limits / structural failure from other causes
        if self.y > self.config.service_ceiling * 1.3 and not self.crashed: # Exceeded max altitude significantly
             print("CRASH: Exceeded safe altitude limits (hypoxia/structural)."); self.crashed = True
        if self.structural_integrity <=0 and not self.crashed: # Already damaged to 0
            print("CRASH: Cumulative structural failure."); self.crashed = True
            
    def set_flaps(self, direction, sound_manager): # direction is +1 or -1
        new_setting = self.flaps_setting + direction
        if 0 <= new_setting <= self.flaps_max_setting:
            self.flaps_setting = new_setting
            print(f"Flaps: {self.get_flaps_deflection()} degrees (Setting {self.flaps_setting})")
            sound_manager.play_sound("flaps_move") # Placeholder sound

    def toggle_gear(self, sound_manager: SoundManager):
        current_speed_mps = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        # Gear operating speed limit (Vlo), e.g., 2x stall speed clean
        gear_operating_speed_mps = self.config.stall_speed_clean * 2.0 
        
        if not self.gear_down and current_speed_mps > gear_operating_speed_mps: # Trying to retract above Vlo
            print(f"Cannot retract gear above {gear_operating_speed_mps*1.94384:.0f} kts (Vlo)!")
            sound_manager.play_sound('stall_warning') # Generic warning
            return
        if self.gear_down and current_speed_mps > gear_operating_speed_mps * 1.1: # Trying to extend above Vle (bit higher)
            print(f"Cannot extend gear above {gear_operating_speed_mps*1.1*1.94384:.0f} kts (Vle)!")
            sound_manager.play_sound('stall_warning') # Generic warning
            return

        self.gear_down = not self.gear_down
        sound_manager.play_sound("gear_down" if self.gear_down else "gear_up")
        print(f"Gear: {'DOWN' if self.gear_down else 'UP'}")
    
    def get_nav_display_info(self):
        if self.nav_mode_active and self.waypoints and \
           self.current_waypoint_index < len(self.waypoints):
            
            wp = self.waypoints[self.current_waypoint_index]
            
            # Calculate distance and bearing to waypoint
            dx_to_wp = wp.x - self.x
            dz_to_wp = wp.z - self.z # Note: Sim Z is often North/South, X is East/West

            distance_m_to_wp = math.sqrt(dx_to_wp**2 + dz_to_wp**2)
            
            # Waypoint arrival check
            arrival_radius_m = 250 if wp.waypoint_type == "AIRPORT" else 100 # Smaller radius for fixes
            if distance_m_to_wp < arrival_radius_m:
                print(f"Reached Waypoint: {wp.name}")
                self.current_waypoint_index +=1
                if self.current_waypoint_index >= len(self.waypoints):
                    print("All waypoints reached. NAV mode disengaging.")
                    self.nav_mode_active = False
                    # Optionally, set AP to hold current heading/alt if it was on NAV mode
                    if self.autopilot_on and self.ap_target_heading is None: # Example logic
                        self.ap_target_heading = self.yaw
                    return None # No more waypoints
                else: # Advance to next waypoint
                    wp = self.waypoints[self.current_waypoint_index]
                    # Recalculate for the new waypoint immediately
                    dx_to_wp = wp.x - self.x
                    dz_to_wp = wp.z - self.z
                    distance_m_to_wp = math.sqrt(dx_to_wp**2 + dz_to_wp**2)

            # Bearing to waypoint (degrees from North)
            # atan2(dx, dz) where dx is Easting, dz is Northing
            bearing_rad_to_wp = math.atan2(dx_to_wp, dz_to_wp) 
            bearing_deg_to_wp = (math.degrees(bearing_rad_to_wp) + 360) % 360
            
            # Desired Track (DTK) is usually the bearing to the waypoint
            desired_track_deg = bearing_deg_to_wp
            
            # Current Ground Track (degrees from North)
            current_ground_speed_horizontal = math.sqrt(self.vx**2 + self.vz**2)
            if current_ground_speed_horizontal > 1.0: # Minimum speed to have a reliable track
                current_track_rad = math.atan2(self.vx, self.vz)
                current_track_deg = (math.degrees(current_track_rad) + 360) % 360
            else: # Use heading if stationary or very slow
                current_track_deg = self.yaw
            
            # Track Error (deviation from DTK)
            # Shortest angle between current track and desired track
            track_error_deg = (desired_track_deg - current_track_deg + 540) % 360 - 180

            return {
                "wp_name": wp.name, "wp_type": wp.waypoint_type,
                "distance_nm": distance_m_to_wp / 1852.0, # Meters to nautical miles
                "bearing_deg": bearing_deg_to_wp,
                "desired_track_deg": desired_track_deg,
                "track_error_deg": track_error_deg, # Cross-track error (angular)
                "altitude_ft": wp.altitude * 3.28084, # Target altitude in feet
                "current_alt_ft": self.y * 3.28084,
                "altitude_error_ft": (wp.altitude - self.y) * 3.28084
            }
        return None


# Camera Class
class Camera:
    def __init__(self):
        # Camera position in world coordinates
        self.x, self.y, self.z = 0, 100, -200 # Initial offset if not following
        # Target point the camera is looking at
        self.target_x, self.target_y, self.target_z = 0,0,0
        
        # Perspective projection parameters
        self.fov_y_deg = 60 # Vertical field of view
        self.aspect_ratio = WIDTH / HEIGHT
        self.near_clip, self.far_clip = 0.5, 30000.0 # Clipping planes

        # Follow/Orbit mode parameters
        self.distance = 25 # Distance from aircraft in follow modes
        self.orbit_angle_h_deg = 0 # Horizontal orbit angle relative to aircraft tail
        self.orbit_angle_v_deg = 15 # Vertical orbit angle (elevation)
        
        self.mode = "follow_mouse_orbit" # "cockpit", "follow", "follow_mouse_orbit", "external_fixed_mouse_orbit"
        self.smooth_factor = 0.1 # For camera movement smoothing (0-1, 1=instant)

        # Mouse orbiting state
        self.is_mouse_orbiting = False
        self.last_mouse_pos: Optional[Tuple[int,int]] = None

        # Camera's own orientation (used for cockpit view and transforming points)
        self.cam_yaw_deg = 0
        self.cam_pitch_deg = 0
        self.cam_roll_deg = 0 # Usually 0, unless cockpit view follows aircraft roll

    def update(self, aircraft: Aircraft, dt):
        desired_cam_x, desired_cam_y, desired_cam_z = self.x, self.y, self.z

        if self.mode == "cockpit":
            # Position camera inside the cockpit (approximate)
            # Offset slightly forward and up from aircraft CG
            # These offsets should be relative to aircraft's orientation
            ac_p_rad, ac_y_rad, ac_r_rad = math.radians(aircraft.pitch), math.radians(aircraft.yaw), math.radians(aircraft.roll)
            
            # Cockpit offset in aircraft's local frame (e.g. slightly forward, up)
            cockpit_offset_local = np.array([0, aircraft.config.fuselage_radius_mult * 0.8, aircraft.config.fuselage_length_mult * 1.5]) # x, y (up), z (fwd)
            
            # Rotate offset by aircraft's orientation
            # Simplified rotation (ignoring roll for camera position to avoid sickness, but roll affects view angles)
            # Body X axis (right): (cos_y, 0, -sin_y)
            # Body Y axis (up):    (sin_y*sin_p, cos_p, cos_y*sin_p)
            # Body Z axis (fwd):   (sin_y*cos_p, -sin_p, cos_y*cos_p) - Error here, should be:
            # Z_body_world_x = cos_p * sin_y
            # Z_body_world_y = sin_p
            # Z_body_world_z = cos_p * cos_y
            # Y_body_world_x = sin_y * sin_p * cos_r - cos_y * sin_r (if roll included)
            # Y_body_world_x = (cos_r * sin_p * sin_y - sin_r * cos_y)

            # Simpler: position at aircraft CG + small Y offset
            desired_cam_x = aircraft.x 
            desired_cam_y = aircraft.y + aircraft.config.fuselage_radius_mult * 0.7 # Eye height
            desired_cam_z = aircraft.z

            # Camera orientation matches aircraft orientation
            self.cam_yaw_deg = aircraft.yaw
            self.cam_pitch_deg = aircraft.pitch
            self.cam_roll_deg = aircraft.roll # Cockpit view rolls with aircraft
           
            # Target point is far in front along aircraft's pointing direction
            look_dist = 1000 # meters
            fwd_x_world = math.cos(ac_p_rad) * math.sin(ac_y_rad)
            fwd_y_world = math.sin(ac_p_rad)
            fwd_z_world = math.cos(ac_p_rad) * math.cos(ac_y_rad)
            
            self.target_x = desired_cam_x + fwd_x_world * look_dist
            self.target_y = desired_cam_y + fwd_y_world * look_dist
            self.target_z = desired_cam_z + fwd_z_world * look_dist

        elif "follow" in self.mode or "external" in self.mode:
            # Camera orbits around the aircraft
            self.cam_roll_deg = 0 # External views usually don't roll with aircraft
            
            # Effective horizontal angle includes aircraft's yaw
            effective_orbit_h_deg = self.orbit_angle_h_deg + aircraft.yaw
            
            orbit_h_rad = math.radians(effective_orbit_h_deg)
            orbit_v_rad = math.radians(self.orbit_angle_v_deg)

            # Calculate camera offset from aircraft in world space
            # Offset in a coordinate system where Z is aligned with orbit_h_rad, Y is up
            offset_x_world = self.distance * math.cos(orbit_v_rad) * math.sin(orbit_h_rad)
            offset_y_world = self.distance * math.sin(orbit_v_rad) # Vertical offset
            offset_z_world = self.distance * math.cos(orbit_v_rad) * math.cos(orbit_h_rad)
            
            # Desired camera position is aircraft position MINUS this offset (camera looks AT aircraft)
            desired_cam_x = aircraft.x - offset_x_world
            desired_cam_y = aircraft.y + offset_y_world # Add vertical offset for better view
            desired_cam_z = aircraft.z - offset_z_world

            # Target is the aircraft itself
            self.target_x = aircraft.x
            self.target_y = aircraft.y # Could add a slight vertical offset to target for better framing
            self.target_z = aircraft.z

        # Smooth camera movement
        # Interpolate current camera position towards desired position
        # The (dt*FPS) factor attempts to make smoothing frame-rate independent. Max 1.0 (instant).
        lerp_factor = np.clip(self.smooth_factor * (dt * FPS if dt > 0 else 1.0), 0.01, 1.0)
        self.x += (desired_cam_x - self.x) * lerp_factor
        self.y += (desired_cam_y - self.y) * lerp_factor
        self.z += (desired_cam_z - self.z) * lerp_factor

    def handle_mouse_input(self, event, aircraft: Aircraft):
        if "mouse_orbit" not in self.mode: # Only allow mouse orbit in specific modes
            self.is_mouse_orbiting = False # Ensure it's off if mode changes
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3: # Right mouse button
                self.is_mouse_orbiting = True
                self.last_mouse_pos = event.pos
                pygame.mouse.set_visible(False) # Hide cursor
                pygame.event.set_grab(True) # Confine cursor to window
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 3: # Right mouse button
                self.is_mouse_orbiting = False
                self.last_mouse_pos = None
                pygame.mouse.set_visible(True) # Show cursor
                pygame.event.set_grab(False) # Release cursor
        elif event.type == pygame.MOUSEMOTION:
            if self.is_mouse_orbiting and self.last_mouse_pos:
                dx = event.pos[0] - self.last_mouse_pos[0]
                dy = event.pos[1] - self.last_mouse_pos[1]
                
                # Adjust orbit angles based on mouse movement
                self.orbit_angle_h_deg -= dx * 0.3 # Sensitivity factor
                self.orbit_angle_v_deg = np.clip(self.orbit_angle_v_deg - dy * 0.3, -85, 85) # Clamp vertical
                self.last_mouse_pos = event.pos
        
        if event.type == pygame.MOUSEWHEEL: # Zoom with mouse wheel
            scroll_speed = self.distance * 0.1 # Zoom proportional to current distance
            self.distance = np.clip(self.distance - event.y * scroll_speed, 3, 300) # Min/max zoom

# Terrain Class
class Terrain:
    def __init__(self):
        self.height_map: Dict[Tuple[int, int], float] = {} # Grid cell -> height
        self.airports: List[Dict] = []
        self.trees: List[Dict] = [] # Simple tree representation

        self.generate_terrain() # Create height data
        self.generate_airports() # Place airports (flattens terrain locally)
        self.generate_trees() # Place trees on terrain

    def generate_terrain(self, grid_size=500, extent=15000):
        print("Generating terrain...")
        # Using integer keys for height_map for easier lookup
        for x_coord in range(-extent, extent + 1, grid_size):
            for z_coord in range(-extent, extent + 1, grid_size):
                # Sum of sines for basic procedural terrain
                height = 0
                height += 150 * math.sin(x_coord * 0.00005 + 1) * math.cos(z_coord * 0.00005 + 1)
                height += 80 * math.sin(x_coord * 0.00015 + 2) * math.cos(z_coord * 0.00015 + 2)
                height += 40 * math.sin(x_coord * 0.00055 + 3) * math.cos(z_coord * 0.00055 + 3)
                height += random.uniform(-20, 20) # Some random noise
                # Store height for the cell, ensuring it's not below sea level (0) for simplicity
                self.height_map[(x_coord // grid_size, z_coord // grid_size)] = max(0, height)
        print(f"Generated {len(self.height_map)} terrain height points.")

    def generate_airports(self, grid_size=500):
        self.airports = []
        # Define airport data (position, elevation, runway details)
        airport_data = [
            {"x": 0, "z": 0, "elevation": 10, "name": "MAIN INTL (KXYZ)", "rwy_len": 3200, "rwy_width": 50, "rwy_hdg": 165},
            {"x": 10000, "z": 6000, "elevation": 200, "name": "ALPINE PEAK (KAPV)", "rwy_len": 1800, "rwy_width": 30, "rwy_hdg": 80},
            {"x": -7000, "z": -9000, "elevation": 5, "name": "SEASIDE STRIP (KSTS)", "rwy_len": 1200, "rwy_width": 25, "rwy_hdg": 310},
            {"x": 13000, "z": -4000, "elevation": 350, "name": "PLATEAU BASE (KPLB)", "rwy_len": 2200, "rwy_width": 40, "rwy_hdg": 45}
        ]
        for ap_data in airport_data:
            # Flatten terrain around airport
            # Extent of flattening around airport center (e.g., 2x2 grid cells)
            flatten_radius_cells = int((ap_data['rwy_len'] / 2.5) / grid_size) # Rough estimate
            
            center_cell_x, center_cell_z = ap_data['x'] // grid_size, ap_data['z'] // grid_size
            for dx_cell in range(-flatten_radius_cells, flatten_radius_cells + 1):
                for dz_cell in range(-flatten_radius_cells, flatten_radius_cells + 1):
                    self.height_map[(center_cell_x + dx_cell, center_cell_z + dz_cell)] = ap_data['elevation']
            
            self.airports.append({
                'x': ap_data['x'], 'z': ap_data['z'], 'elevation': ap_data['elevation'],
                'name': ap_data['name'],
                'runway_length': ap_data['rwy_len'],
                'runway_width': ap_data['rwy_width'],
                'runway_heading': ap_data['rwy_hdg'], # Degrees from North
                'has_ils': random.choice([True, False]), # Future use
                'has_lights': True # Future use for night rendering
            })
        print(f"Generated {len(self.airports)} airports and flattened local terrain.")

    def get_height_at(self, x, z, grid_size=500):
        # Get terrain height at specific world coordinates
        # Uses nearest grid cell height for simplicity
        key_x, key_z = int(round(x / grid_size)), int(round(z / grid_size))
        return self.height_map.get((key_x, key_z), 0) # Default to 0 if outside map

    def generate_trees(self, count=150):
        self.trees = []
        print(f"Generating {count} trees...")
        for _ in range(count):
            tree_x = random.uniform(-15000, 15000)
            tree_z = random.uniform(-15000, 15000)
            
            # Avoid placing trees directly on runways or very close to airport centers
            on_airport_area = False
            for airport in self.airports:
                # Check distance to airport center; if too close, skip
                dist_sq_to_airport_center = (tree_x - airport['x'])**2 + (tree_z - airport['z'])**2
                # Consider airport area larger than just runway length
                if dist_sq_to_airport_center < (airport['runway_length'] * 1.5)**2: # Increased exclusion zone
                    on_airport_area = True
                    break
            
            if not on_airport_area:
                 base_h = self.get_height_at(tree_x, tree_z)
                 # Avoid trees in water (if y=0 is sea level and terrain can go below)
                 # Or if terrain is too high (e.g., above tree line - simplified)
                 if base_h < 0.1 and random.random() < 0.7: continue # Less trees at sea level if it's water
                 if base_h > 2000 and random.random() < 0.8: continue # Fewer trees on high mountains

                 tree_h_val = random.uniform(8, 25) # Tree height
                 self.trees.append({
                     'x': tree_x, 'y': base_h + tree_h_val / 2, # Center Y of tree
                     'z': tree_z, 'height': tree_h_val,
                     'radius': random.uniform(3, 8) # Radius of tree canopy
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
                    return True # Event handled
        return False

    def draw(self, surface):
        current_color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(surface, current_color, self.rect, border_radius=5)
        # Subtle border
        border_color = tuple(np.clip(c*0.7,0,255) for c in current_color)
        pygame.draw.rect(surface, border_color, self.rect, 2, border_radius=5)
        
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

# Renderer Class
class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font_small = pygame.font.Font(None, 22)
        self.font_medium = pygame.font.Font(None, 30)
        self.font_large = pygame.font.Font(None, 52)
        self.font_hud = pygame.font.SysFont("Consolas", 20) # Monospaced for HUD
        self.font_hud_large = pygame.font.SysFont("Consolas", 26)

        self.light = LightSource() # Global light source for the scene

        self.cockpit_overlay_img = None
        try:
            self.cockpit_overlay_img = pygame.image.load("cockpit_overlay.png").convert_alpha()
            self.cockpit_overlay_img = pygame.transform.scale(self.cockpit_overlay_img, (WIDTH, HEIGHT))
        except pygame.error:
            print("Warning: cockpit_overlay.png not found or error loading. Using basic frame.")
            # Dummy overlay created in main guard now

    def project_point_3d_to_2d(self, x_world, y_world, z_world, camera: Camera) -> Optional[Tuple[int, int, float]]:
        # --- View Transformation (World to Camera Space) ---
        # Vector from camera eye to point P in world space
        p_world = np.array([x_world, y_world, z_world])
        eye_world = np.array([camera.x, camera.y, camera.z])
        
        # Camera orientation vectors (LookAt matrix construction)
        if camera.mode == "cockpit": # Use aircraft's orientation for cockpit view
            cam_p_rad = math.radians(camera.cam_pitch_deg)
            cam_y_rad = math.radians(camera.cam_yaw_deg)
            # Forward vector (camera's -Z axis)
            fwd_x = math.cos(cam_p_rad) * math.sin(cam_y_rad)
            fwd_y = math.sin(cam_p_rad)
            fwd_z = math.cos(cam_p_rad) * math.cos(cam_y_rad)
            forward_vec = np.array([fwd_x, fwd_y, fwd_z])
        else: # External cameras look at target_x,y,z
            target_world = np.array([camera.target_x, camera.target_y, camera.target_z])
            forward_vec = target_world - eye_world
            norm_fwd = np.linalg.norm(forward_vec)
            if norm_fwd < 1e-6: return None # Avoid division by zero if eye is at target
            forward_vec = forward_vec / norm_fwd

        # Global 'up' vector (positive Y in world space)
        # Note: Camera roll is handled for cockpit view by rotating this up_approx
        world_up_approx = np.array([0, 1, 0])
        if camera.mode == "cockpit" and abs(camera.cam_roll_deg) > 0.1:
             cam_r_rad = math.radians(camera.cam_roll_deg)
             # Rotate world_up_approx around forward_vec by -cam_roll_deg
             # This is complex; a simpler approximation for cockpit roll:
             # Assume up vector in camera space is tilted by roll.
             # For now, the standard cross product method will handle it if forward_vec isn't vertical.
             # If forward_vec is vertical, need a different 'right' vector.
             # Simplified: assume world_up is fine and rely on screen rotation for ADI for roll.
             # The projection itself usually doesn't incorporate camera roll directly in this way;
             # The world is transformed relative to a non-rolled camera, or vertices are pre-rolled.

        # Right vector (camera's X axis)
        right_vec = np.cross(forward_vec, world_up_approx)
        norm_right = np.linalg.norm(right_vec)
        if norm_right < 1e-6: # If forward is aligned with world_up (looking straight up/down)
            # Use a different world_up_approx if forward is (nearly) vertical
            if abs(forward_vec[1]) > 0.99: # Looking straight up or down
                 world_up_for_right = np.array([0,0, -1 if forward_vec[1] > 0 else 1]) # Use world Z
                 right_vec = np.cross(forward_vec, world_up_for_right)
                 norm_right = np.linalg.norm(right_vec)
                 if norm_right < 1e-6: return None # Should not happen now
            else: # Should not be reachable if previous check works
                 return None 
        right_vec = right_vec / norm_right

        # Up vector (camera's Y axis)
        up_vec = np.cross(right_vec, forward_vec) # Already normalized due to right_vec and forward_vec orthogonality

        # Point relative to camera eye
        p_rel_eye_world = p_world - eye_world
        
        # Project p_rel_eye_world onto camera axes
        x_cam = np.dot(p_rel_eye_world, right_vec)
        y_cam = np.dot(p_rel_eye_world, up_vec)
        z_cam = np.dot(p_rel_eye_world, forward_vec) # Depth in camera space (distance along forward vector)

        # --- Perspective Projection (Camera to Screen Space) ---
        # Frustum culling (near/far planes)
        if not (camera.near_clip < z_cam < camera.far_clip):
            return None
        
        # Perspective divide
        # tan_half_fovy handles FOV, aspect_ratio handles screen shape
        tan_half_fovy = math.tan(math.radians(camera.fov_y_deg) / 2.0)
        if abs(z_cam) < 1e-6: return None # Avoid division by zero
        
        # Normalized Device Coordinates (NDC), typically [-1, 1] range
        sx_ndc = (x_cam / (camera.aspect_ratio * tan_half_fovy * z_cam))
        sy_ndc = (y_cam / (tan_half_fovy * z_cam))

        # Convert NDC to screen coordinates (pixels)
        # (0,0) is top-left, (WIDTH, HEIGHT) is bottom-right
        screen_x = int((sx_ndc + 1.0) / 2.0 * WIDTH)
        screen_y = int((1.0 - sy_ndc) / 2.0 * HEIGHT) # Y is inverted in screen space

        return screen_x, screen_y, z_cam # Return z_cam for depth sorting

    def draw_horizon_and_sky(self, aircraft: Aircraft, camera: Camera):
        # Sky Gradient
        for y_scan in range(HEIGHT // 2 + 50): # Draw slightly below horizon for safety
            # Interpolate color from zenith to horizon
            ratio = y_scan / (HEIGHT // 2 + 49.0) # 0 at top, 1 at horizon_ish
            sky_color_r = int(SKY_BLUE_ZENITH[0] * (1 - ratio) + SKY_BLUE_HORIZON[0] * ratio)
            sky_color_g = int(SKY_BLUE_ZENITH[1] * (1 - ratio) + SKY_BLUE_HORIZON[1] * ratio)
            sky_color_b = int(SKY_BLUE_ZENITH[2] * (1 - ratio) + SKY_BLUE_HORIZON[2] * ratio)
            pygame.draw.line(self.screen, (sky_color_r, sky_color_g, sky_color_b), (0, y_scan), (WIDTH, y_scan))
        
        # Sun (simple circle) - position based on light direction
        # Project a point far away in the *opposite* of light direction
        sun_world_pos = camera.x - self.light.direction[0] * (camera.far_clip * 0.8), \
                        camera.y - self.light.direction[1] * (camera.far_clip * 0.8), \
                        camera.z - self.light.direction[2] * (camera.far_clip * 0.8)
        sun_proj = self.project_point_3d_to_2d(sun_world_pos[0], sun_world_pos[1], sun_world_pos[2], camera)
        
        if sun_proj and sun_proj[1] < HEIGHT * 0.6: # Only draw if above horizon line and visible
            sun_screen_x, sun_screen_y, sun_depth = sun_proj
            sun_radius = int(np.clip(2000 / sun_depth if sun_depth > 1 else 20, 5, 30)) # Size diminishes with "depth"
            pygame.gfxdraw.filled_circle(self.screen, sun_screen_x, sun_screen_y, sun_radius, SUN_COLOR)
            pygame.gfxdraw.aacircle(self.screen, sun_screen_x, sun_screen_y, sun_radius, tuple(c*0.8 for c in SUN_COLOR))


        # Ground plane (simplified: a large polygon at y=0, or slightly below horizon)
        # To make it look like it's at y=0 world, project corners of a large quad at y=0
        ground_y_world = 0 # Assuming ground is at y=0
        
        # Define corners of a large ground quad in world space
        # Far clip distance used to determine quad size for good coverage
        extent = camera.far_clip * 0.95
        ground_corners_world = [
            (camera.x - extent, ground_y_world, camera.z - extent),
            (camera.x + extent, ground_y_world, camera.z - extent),
            (camera.x + extent, ground_y_world, camera.z + extent),
            (camera.x - extent, ground_y_world, camera.z + extent),
        ]
        
        ground_polygon_screen = []
        min_ground_depth = camera.far_clip
        for gx, gy, gz in ground_corners_world:
            pt_info = self.project_point_3d_to_2d(gx, gy, gz, camera)
            if pt_info:
                ground_polygon_screen.append((pt_info[0], pt_info[1]))
                min_ground_depth = min(min_ground_depth, pt_info[2])
            else: # If any corner is not visible, fall back to simple rect
                ground_polygon_screen = None; break
        
        # Determine ground color with slight variation
        # Base ground color, slightly modulated by a noise pattern or camera position for subtle variation
        # Using a very simple noise based on camera position to break monotony
        noise_val = (math.sin(camera.x * 0.0001) + math.cos(camera.z * 0.0001)) * 10 # Small variation
        ground_r = np.clip(GROUND_COLOR_BASE[0] + noise_val, 0, 255)
        ground_g = np.clip(GROUND_COLOR_BASE[1] + noise_val, 0, 255)
        ground_b = np.clip(GROUND_COLOR_BASE[2] + noise_val, 0, 255)
        current_ground_color = (int(ground_r), int(ground_g), int(ground_b))


        if ground_polygon_screen and len(ground_polygon_screen) == 4:
            pygame.draw.polygon(self.screen, current_ground_color, ground_polygon_screen)
        else: # Fallback if polygon projection is weird (e.g. camera inside ground)
            # Draw from horizon down
            horizon_y_approx = HEIGHT // 2 + 50 # Approximate screen Y for horizon
            pygame.draw.rect(self.screen, current_ground_color, (0, horizon_y_approx, WIDTH, HEIGHT - horizon_y_approx))


    def _apply_lighting(self, base_color, normal_world):
        # Simple Lambertian lighting + Ambient
        norm_normal = np.linalg.norm(normal_world)
        if norm_normal < 1e-6: # Should not happen for valid faces
            return base_color 
        normal_world = normal_world / norm_normal

        # Diffuse component
        diffuse_factor = np.dot(normal_world, self.light.direction)
        diffuse_factor = max(0, diffuse_factor) # Light only on one side
        
        # Combine ambient and diffuse
        intensity = self.light.ambient_intensity + self.light.diffuse_intensity * diffuse_factor
        intensity = np.clip(intensity, 0, 1)
        
        # Modulate base color by intensity and light color
        # Assuming white light for now, so light.color is not used directly on base_color modulation
        lit_color = tuple(int(c * intensity) for c in base_color)
        return lit_color

    def draw_aircraft_model(self, aircraft: Aircraft, camera: Camera):
        if camera.mode == "cockpit" and not aircraft.crashed : return # Don't draw external model in cockpit view

        # Aircraft's world transformation
        pitch_rad = math.radians(aircraft.pitch)
        yaw_rad = math.radians(aircraft.yaw)
        roll_rad = math.radians(aircraft.roll)

        # Transform local model vertices to world space
        world_vertices = []
        for v_local_orig in aircraft.model_vertices_local:
            v_local = np.array(v_local_orig)
            # Apply rotations: Yaw, then Pitch, then Roll (standard aerospace sequence)
            # Yaw rotation (around Y axis)
            x1 = v_local[0] * math.cos(yaw_rad) - v_local[2] * math.sin(yaw_rad) # Corrected Yaw
            y1 = v_local[1]
            z1 = v_local[0] * math.sin(yaw_rad) + v_local[2] * math.cos(yaw_rad) # Corrected Yaw
            v_rot_yaw = np.array([x1, y1, z1])

            # Pitch rotation (around new X axis)
            x2 = v_rot_yaw[0]
            y2 = v_rot_yaw[1] * math.cos(pitch_rad) - v_rot_yaw[2] * math.sin(pitch_rad)
            z2 = v_rot_yaw[1] * math.sin(pitch_rad) + v_rot_yaw[2] * math.cos(pitch_rad)
            v_rot_pitch = np.array([x2, y2, z2])
            
            # Roll rotation (around new Z axis)
            x3 = v_rot_pitch[0] * math.cos(roll_rad) - v_rot_pitch[1] * math.sin(roll_rad)
            y3 = v_rot_pitch[0] * math.sin(roll_rad) + v_rot_pitch[1] * math.cos(roll_rad)
            z3 = v_rot_pitch[2]
            v_rotated = np.array([x3, y3, z3])
            
            # Translate to world position
            v_world = v_rotated + np.array([aircraft.x, aircraft.y, aircraft.z])
            world_vertices.append(v_world)
        
        # Project all world vertices to screen space once
        screen_points_cache = [self.project_point_3d_to_2d(v[0], v[1], v[2], camera) for v in world_vertices]

        # Collect faces for drawing and sorting (Painter's Algorithm)
        faces_to_draw = []
        for face_def in aircraft.model_faces:
            face_v_indices = face_def["v_indices"]
            is_custom = face_def.get("is_custom_verts", False)

            current_face_world_verts = []
            if is_custom: # Vertices are defined directly in face_def
                for v_local_custom in face_v_indices:
                    # Transform these custom local vertices same way as model_vertices_local
                    v_local_c = np.array(v_local_custom)
                    x1c = v_local_c[0] * math.cos(yaw_rad) - v_local_c[2] * math.sin(yaw_rad)
                    y1c = v_local_c[1]
                    z1c = v_local_c[0] * math.sin(yaw_rad) + v_local_c[2] * math.cos(yaw_rad)
                    v_rot_yaw_c = np.array([x1c, y1c, z1c])
                    x2c = v_rot_yaw_c[0]
                    y2c = v_rot_yaw_c[1] * math.cos(pitch_rad) - v_rot_yaw_c[2] * math.sin(pitch_rad)
                    z2c = v_rot_yaw_c[1] * math.sin(pitch_rad) + v_rot_yaw_c[2] * math.cos(pitch_rad)
                    v_rot_pitch_c = np.array([x2c, y2c, z2c])
                    x3c = v_rot_pitch_c[0] * math.cos(roll_rad) - v_rot_pitch_c[1] * math.sin(roll_rad)
                    y3c = v_rot_pitch_c[0] * math.sin(roll_rad) + v_rot_pitch_c[1] * math.cos(roll_rad)
                    z3c = v_rot_pitch_c[2]
                    v_rotated_c = np.array([x3c, y3c, z3c])
                    current_face_world_verts.append(v_rotated_c + np.array([aircraft.x, aircraft.y, aircraft.z]))
            else: # Vertex indices refer to aircraft.model_vertices_local
                current_face_world_verts = [world_vertices[i] for i in face_v_indices]

            # Project face vertices to screen
            screen_polygon_points = []
            avg_depth = 0
            valid_face = True
            for v_world in current_face_world_verts:
                pt_info = self.project_point_3d_to_2d(v_world[0], v_world[1], v_world[2], camera)
                if pt_info:
                    screen_polygon_points.append((pt_info[0], pt_info[1]))
                    avg_depth += pt_info[2]
                else:
                    valid_face = False; break # Skip face if any vertex is unprojectable
            
            if valid_face and len(screen_polygon_points) >= 3:
                avg_depth /= len(screen_polygon_points)
                
                # Calculate face normal in world space for lighting
                # (Assumes face vertices are co-planar and ordered CCW from outside)
                v0, v1, v2 = current_face_world_verts[0], current_face_world_verts[1], current_face_world_verts[2]
                edge1 = v1 - v0
                edge2 = v2 - v0
                face_normal_world = np.cross(edge1, edge2)
                if face_def.get("normal_mult", 1) == -1:
                    face_normal_world *= -1
                
                base_color = aircraft.model_colors[face_def["color"]]
                lit_color = self._apply_lighting(base_color, face_normal_world)
                
                # Handle transparency for cockpit glass
                if face_def["color"] == "cockpit":
                    final_color = (*lit_color, 100) # Add alpha for transparency
                else:
                    final_color = lit_color

                faces_to_draw.append({
                    "depth": avg_depth,
                    "points": screen_polygon_points,
                    "color": final_color
                })

        # Sort faces by depth (farthest first)
        faces_to_draw.sort(key=lambda f: f["depth"], reverse=True)

        # Draw sorted faces
        for face_data in faces_to_draw:
            color = face_data["color"]
            points = face_data["points"]
            if len(color) == 4: # RGBA color
                temp_surface = self.screen.convert_alpha() # Ensure temp surface supports alpha
                temp_surface.fill((0,0,0,0)) # Transparent fill
                pygame.draw.polygon(temp_surface, color, points)
                self.screen.blit(temp_surface, (0,0))
            else: # RGB color
                pygame.draw.polygon(self.screen, color, points)
                # Optional: draw wireframe outline for definition
                # pygame.draw.polygon(self.screen, tuple(c*0.5 for c in color), points, 1)


        # Smoke trail if damaged/crashed (same as before)
        if not aircraft.engine_on or any(h < 30 for h in aircraft.engine_health) or aircraft.crashed:
            cg_proj_info = self.project_point_3d_to_2d(aircraft.x, aircraft.y, aircraft.z, camera)
            if cg_proj_info:
                sx, sy, _ = cg_proj_info
                for i in range(8): # Number of smoke particles
                    offset_x = -aircraft.vx * 0.1 * i + random.uniform(-3,3) # Trail behind
                    offset_y = -aircraft.vy * 0.1 * i + random.uniform(-3,3) # Trail behind
                    smoke_screen_x = sx + int(offset_x)
                    smoke_screen_y = sy + int(offset_y) + i*3 # Settle down slightly
                    smoke_color = (80,80,80, max(0, 150 - i*15)) # Fading alpha
                    pygame.gfxdraw.filled_circle(self.screen, smoke_screen_x, smoke_screen_y, max(1, 5 - i//2), smoke_color)

    def draw_terrain_features(self, camera: Camera, terrain: Terrain, weather: Weather):
        # Airports
        for airport in terrain.airports:
            ap_x, ap_y_base, ap_z = airport['x'], airport['elevation'], airport['z']
            
            # Basic culling: if airport center too far, skip
            dist_sq_to_ap_center = (ap_x - camera.x)**2 + (ap_y_base - camera.y)**2 + (ap_z - camera.z)**2
            if dist_sq_to_ap_center > (camera.far_clip * 0.8)**2: continue

            # Runway polygon
            length, width = airport['runway_length'], airport['runway_width']
            hdg_rad = math.radians(airport['runway_heading']) # Heading from North, clockwise
            
            # Runway corners relative to airport center (local XY plane, Z=0 for drawing)
            # X along width, Y along length
            hl, hw = length / 2, width / 2
            corners_local_rwy = [(-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl)] # (x,y) for 2D polygon on XY plane
            
            runway_corners_world = []
            for clx_local, clz_local in corners_local_rwy: # Treat local y as z for world projection
                # Rotate local runway coords by heading (around Y axis)
                rot_x_world = clx_local * math.cos(hdg_rad) - clz_local * math.sin(hdg_rad)
                rot_z_world = clx_local * math.sin(hdg_rad) + clz_local * math.cos(hdg_rad)
                # Add to airport center and elevation
                runway_corners_world.append( (ap_x + rot_x_world, ap_y_base + 0.1, ap_z + rot_z_world) ) # 0.1m above terrain

            screen_corners_rwy = []
            all_visible_rwy = True
            min_depth_rwy = camera.far_clip
            for cw_x, cw_y, cw_z in runway_corners_world:
                pt_info = self.project_point_3d_to_2d(cw_x, cw_y, cw_z, camera)
                if pt_info:
                    screen_corners_rwy.append((pt_info[0], pt_info[1]))
                    min_depth_rwy = min(min_depth_rwy, pt_info[2])
                else: all_visible_rwy = False; break
            
            if all_visible_rwy and len(screen_corners_rwy) == 4:
                # Apply simple lighting to runway (normal is [0,1,0])
                rwy_normal_world = np.array([0,1,0])
                rwy_base_color = DARK_GRAY
                lit_rwy_color = self._apply_lighting(rwy_base_color, rwy_normal_world)
                pygame.draw.polygon(self.screen, lit_rwy_color, screen_corners_rwy)

                # Runway Markings (centerline, threshold) - simplified
                # Centerline dashes
                num_dashes = int(length / 50) # Dash every 50m
                dash_len, dash_gap = 30, 20 # m
                for i in range(num_dashes):
                    cl_z_local_start = -hl + i * (dash_len + dash_gap)
                    cl_z_local_end = cl_z_local_start + dash_len
                    if cl_z_local_end > hl: break # Don't draw past runway end

                    # Define dash corners (thin rectangle)
                    dash_width_local = 0.5 # meters wide
                    dash_verts_local = [
                        (-dash_width_local, cl_z_local_start), (dash_width_local, cl_z_local_start),
                        (dash_width_local, cl_z_local_end), (-dash_width_local, cl_z_local_end)
                    ]
                    dash_verts_world = []
                    for dvx, dvz in dash_verts_local:
                        rot_dvx = dvx * math.cos(hdg_rad) - dvz * math.sin(hdg_rad)
                        rot_dvz = dvx * math.sin(hdg_rad) + dvz * math.cos(hdg_rad)
                        dash_verts_world.append( (ap_x + rot_dvx, ap_y_base + 0.15, ap_z + rot_dvz) ) # Slightly above runway
                    
                    dash_screen_pts = [self.project_point_3d_to_2d(v[0],v[1],v[2],camera) for v in dash_verts_world]
                    if all(p is not None for p in dash_screen_pts):
                        pygame.draw.polygon(self.screen, RUNWAY_MARKING_WHITE, [(p[0],p[1]) for p in dash_screen_pts])
                
                # Airport name (if close enough)
                if min_depth_rwy < 8000: # Show name if relatively close
                    center_proj = self.project_point_3d_to_2d(ap_x, ap_y_base, ap_z, camera)
                    if center_proj:
                        name_surf = self.font_small.render(airport['name'], True, WHITE)
                        self.screen.blit(name_surf, (center_proj[0] - name_surf.get_width()//2, center_proj[1] - 25))
        
        # Trees (simplified cylinders/sprites)
        drawn_trees = 0
        # Sort trees by distance for pseudo-alpha blending (draw farthest first) - not perfect
        # This is not strictly necessary if not using alpha, but good practice
        # sorted_trees = sorted(terrain.trees, key=lambda t: (t['x']-camera.x)**2 + (t['y']-camera.y)**2 + (t['z']-camera.z)**2, reverse=True)

        for tree in terrain.trees: # Use sorted_trees if implementing proper alpha/sorting
            if drawn_trees > 75: break # Limit number of trees drawn for performance
            
            # Basic culling
            dist_sq_to_tree_cam = (tree['x']-camera.x)**2 + (tree['z']-camera.z)**2 # Horizontal distance
            if dist_sq_to_tree_cam > (camera.far_clip * 0.4)**2 : continue # Too far horizontally

            # Project tree base and top
            tree_base_y = tree['y'] - tree['height']/2
            tree_top_y = tree['y'] + tree['height']/2
            bottom_proj = self.project_point_3d_to_2d(tree['x'], tree_base_y, tree['z'], camera)
            top_proj = self.project_point_3d_to_2d(tree['x'], tree_top_y, tree['z'], camera)

            if bottom_proj and top_proj:
                bx_screen, by_screen, b_depth = bottom_proj
                tx_screen, ty_screen, t_depth = top_proj
                
                # Further culling based on screen position or depth
                if b_depth < camera.near_clip or t_depth < camera.near_clip: continue # Too close
                if not (0 <= bx_screen < WIDTH and 0 <= by_screen < HEIGHT) and \
                   not (0 <= tx_screen < WIDTH and 0 <= ty_screen < HEIGHT): continue # Off-screen

                # Determine on-screen size based on depth
                # Scale factor for size: closer trees are larger
                scale_factor_depth = 500 / b_depth if b_depth > 1 else 500
                
                screen_radius_trunk = max(1, int(tree['radius'] * 0.2 * scale_factor_depth))
                screen_radius_leaves = max(2, int(tree['radius'] * 0.8 * scale_factor_depth))
                if screen_radius_leaves < 2: continue # Too small to draw

                # Lighting for trees (treat as rough sphere/cylinder with vertical normal for trunk)
                trunk_normal_world = np.array([ (camera.x - tree['x'])/b_depth if b_depth > 0 else 0, 0, (camera.z - tree['z'])/b_depth if b_depth > 0 else 0]) # Points to camera roughly
                if np.linalg.norm(trunk_normal_world) > 0: trunk_normal_world /= np.linalg.norm(trunk_normal_world)
                else: trunk_normal_world = np.array([0,0,1]) # fallback

                trunk_base_color = (101, 67, 33) # Brown
                leaves_base_color = (34, 80, 34) # Dark green

                lit_trunk_color = self._apply_lighting(trunk_base_color, trunk_normal_world)
                # For leaves, could use a more upward normal, or average
                # For simplicity, use similar lighting as trunk, or slightly brighter ambient
                leaves_normal_world = np.array([trunk_normal_world[0]*0.5, 0.5, trunk_normal_world[2]*0.5]) # Mix horizontal and up
                if np.linalg.norm(leaves_normal_world) > 0: leaves_normal_world /= np.linalg.norm(leaves_normal_world)
                else: leaves_normal_world = np.array([0,1,0])

                lit_leaves_color = self._apply_lighting(leaves_base_color, leaves_normal_world)
                
                # Draw trunk (line)
                pygame.draw.line(self.screen, lit_trunk_color, (bx_screen, by_screen), (tx_screen, ty_screen), screen_radius_trunk)
                # Draw leaves (circle)
                pygame.gfxdraw.filled_circle(self.screen, tx_screen, ty_screen, screen_radius_leaves, lit_leaves_color)
                pygame.gfxdraw.aacircle(self.screen, tx_screen, ty_screen, screen_radius_leaves, tuple(c*0.8 for c in lit_leaves_color)) # Outline
                drawn_trees +=1

    def draw_weather_effects(self, weather: Weather, camera: Camera, aircraft: Aircraft):
        particle_count, particle_color_base, particle_prop = 0, WHITE, {}

        # Define particle properties based on weather type
        if weather.type == WeatherType.RAIN or weather.type == WeatherType.STORM:
            particle_count = int(weather.precipitation * 60) # More particles for heavier rain
            particle_color_base = (100, 100, 220) # Bluish rain
            particle_prop = {'type': 'line', 'length': 18, 'thickness': 1}
        elif weather.type == WeatherType.SNOW:
            particle_count = int(weather.precipitation * 50)
            particle_color_base = (230, 230, 255) # Off-white snow
            particle_prop = {'type': 'circle', 'radius': 3}

        # Draw rain/snow particles
        if particle_count > 0:
            for _ in range(particle_count):
                # Particle generation relative to camera/aircraft
                # Spread particles in a volume around the camera
                rel_x = random.uniform(-80, 80) # Wider horizontal spread
                rel_y = random.uniform(-40, 40)  # Vertical spread
                # Depth in front of camera, ensuring they are beyond near clip
                rel_z_cam_space = random.uniform(camera.near_clip + 1, 100) # Depth range
                
                # Particle origin depends on camera mode (cockpit vs external)
                origin_x, origin_y, origin_z = camera.x, camera.y, camera.z
                if camera.mode == "cockpit": # Particles relative to aircraft if in cockpit
                    origin_x, origin_y, origin_z = aircraft.x, aircraft.y, aircraft.z
                
                # Approximate world position of particle (this is simplified, true particles move with wind)
                # This makes particles appear fixed relative to camera/aircraft volume
                # TODO: A better particle system would have world-space particles affected by wind
                p_world_x = origin_x + rel_x # This needs to be transformed by camera orientation if rel_x,y,z are camera space
                p_world_y = origin_y + rel_y 
                # For now, assume rel_x,y are world offsets, and rel_z_cam_space is depth
                # This means particles are in a screen-aligned box.
                # A slightly better way: create point in camera space, then transform to world
                # This is complex; current method is a visual approximation.
                
                # For simplicity, treat rel_x, rel_y, rel_z_cam_space as offsets in a view-aligned box
                # This is not physically correct but visually acceptable for simple effects.
                # The particle position needs to be projected.
                # Let's assume particle is at (origin + (rel_x, rel_y, 0)) and then project with depth rel_z_cam_space
                # This also isn't quite right.
                # Simplest: generate random screen points and give them a random depth for effects.
                # For now, keeping the old logic of projecting a world point that's offset.
                
                # Create particle world position based on camera's current view frustum slice
                # This is still a bit of a hack for particle systems without full world simulation.
                # A point `d` units along camera forward, then offset sideways/upwards in camera plane
                fwd = np.array([camera.target_x - camera.x, camera.target_y - camera.y, camera.target_z - camera.z])
                if np.linalg.norm(fwd) > 0: fwd /= np.linalg.norm(fwd)
                else: fwd = np.array([0,0,1]) # Default if camera at target
                
                # Get camera's right and up vectors (already computed in project_point_3d_to_2d, but re-derive for clarity)
                world_up_approx = np.array([0,1,0])
                cam_right = np.cross(fwd, world_up_approx)
                if np.linalg.norm(cam_right) > 0: cam_right /= np.linalg.norm(cam_right)
                else: cam_right = np.array([1,0,0]) # Fallback
                cam_up = np.cross(cam_right, fwd) # Should be normalized

                pt_on_fwd_axis = np.array([camera.x, camera.y, camera.z]) + fwd * rel_z_cam_space
                particle_world_pos = pt_on_fwd_axis + cam_right * rel_x + cam_up * rel_y

                pt_info = self.project_point_3d_to_2d(particle_world_pos[0], particle_world_pos[1], particle_world_pos[2], camera)

                if pt_info:
                    sx, sy, depth_particle = pt_info
                    if not (0 <= sx < WIDTH and 0 <= sy < HEIGHT): continue # Cull if off-screen
                    
                    # Particle appearance based on depth
                    intensity_depth = np.clip(1.0 - (depth_particle / 150.0), 0.2, 1.0) # Fade with distance
                    final_particle_color = tuple(int(c * intensity_depth) for c in particle_color_base)

                    if particle_prop['type'] == 'circle':
                        # Snowflakes: size affected by depth
                        size = int(np.clip(particle_prop['radius'] * 80 / depth_particle if depth_particle > 1 else particle_prop['radius'], 1, 6) * intensity_depth)
                        pygame.gfxdraw.filled_circle(self.screen, sx, sy, size, final_particle_color)
                    elif particle_prop['type'] == 'line':
                        # Rain streaks: length and angle affected by depth and aircraft speed
                        length = int(np.clip(particle_prop['length'] * 80 / depth_particle if depth_particle > 1 else particle_prop['length'], 2, 25) * intensity_depth)
                        # Streak angle influenced by aircraft's relative wind (simplified: use aircraft world velocity)
                        # Project aircraft velocity onto screen plane for streak direction
                        # This is approximate; true relative wind is complex.
                        streak_dx = -aircraft.vx * 0.05 * length * intensity_depth # Scale effect
                        streak_dy = -aircraft.vy * 0.05 * length * intensity_depth + length # Gravity pull on rain
                        pygame.draw.line(self.screen, final_particle_color, (sx, sy), 
                                         (sx + int(streak_dx), sy + int(streak_dy)), particle_prop['thickness'])
        
        # Fog effect
        if weather.type == WeatherType.FOG and weather.visibility < 2000: # Apply fog if visibility is low
            # Alpha increases as visibility decreases
            alpha_fog = np.clip( (2000 - weather.visibility) / 2000 * 220, 0, 220) # Max alpha 220
            fog_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA) # Per-pixel alpha surface
            fog_surf.fill((LIGHT_GRAY[0], LIGHT_GRAY[1], LIGHT_GRAY[2], int(alpha_fog)))
            self.screen.blit(fog_surf, (0,0))

        # Clouds (improved: multiple ellipses per cloud particle for "fluffier" look)
        # Sort by depth for correct alpha blending (farthest first)
        sorted_clouds = sorted(weather.cloud_particles, 
                               key=lambda p: (p['x']-camera.x)**2 + (p['y']-camera.y)**2 + (p['z']-camera.z)**2, 
                               reverse=True)
        drawn_clouds_count = 0
        for cloud_particle in sorted_clouds:
            if drawn_clouds_count > 25: break # Limit drawn cloud "systems" for performance
            
            # Project main cloud particle center
            pt_info_cloud = self.project_point_3d_to_2d(cloud_particle['x'], cloud_particle['y'], cloud_particle['z'], camera)
            if pt_info_cloud:
                sx_center, sy_center, depth_cloud = pt_info_cloud
                # Cull if too close, too far, or main point off-screen (though puffs might be visible)
                if depth_cloud < camera.near_clip + 10 or depth_cloud > camera.far_clip * 0.9: continue
                
                base_screen_size_w = int(np.clip( (cloud_particle['size'] * 150) / depth_cloud if depth_cloud > 1 else 0, 10, 500 )) # Max width 500px
                if base_screen_size_w < 20: continue # Skip if too small to be meaningful

                # Draw multiple "puffs" for this cloud particle
                for i in range(cloud_particle['num_puffs']):
                    # Offset puffs slightly from center, vary size and opacity
                    offset_factor = 0.3 # How much puffs can spread from center
                    puff_offset_x = random.uniform(-base_screen_size_w * offset_factor, base_screen_size_w * offset_factor)
                    puff_offset_y = random.uniform(-(base_screen_size_w*0.5) * offset_factor, (base_screen_size_w*0.5) * offset_factor)
                    
                    puff_sx = sx_center + int(puff_offset_x * (1 - i*0.1)) # Puffs closer to center for later i
                    puff_sy = sy_center + int(puff_offset_y * (1 - i*0.1))

                    puff_size_w = int(base_screen_size_w * random.uniform(0.4, 0.8))
                    puff_size_h = int(puff_size_w * random.uniform(0.4, 0.7)) # Elliptical puffs

                    # Alpha based on main cloud opacity, depth, and puff variation
                    alpha_puff = np.clip(cloud_particle['opacity'] * (1 - depth_cloud / (camera.far_clip*0.8)) * random.uniform(0.5, 0.8) , 10, 80) # Max alpha per puff
                    
                    cloud_color_base = (210, 210, 225) if weather.type != WeatherType.STORM else (100,100,110) # Darker storm clouds
                    
                    # Apply very basic lighting to clouds (darker bottom)
                    # This assumes light from above. A y-offset for puff can simulate this.
                    # Positive puff_offset_y means puff is lower on screen (potentially higher in world if y screen inverted)
                    # Let's make puffs lower on screen (higher y value) slightly darker
                    color_mult = 1.0 - np.clip(puff_offset_y / (base_screen_size_w*0.5 * offset_factor), 0, 1) * 0.3
                    final_cloud_puff_color = tuple(int(c * color_mult) for c in cloud_color_base)

                    temp_puff_surf = pygame.Surface((puff_size_w, puff_size_h), pygame.SRCALPHA)
                    pygame.draw.ellipse(temp_puff_surf, (*final_cloud_puff_color, int(alpha_puff)), (0,0, puff_size_w, puff_size_h))
                    self.screen.blit(temp_puff_surf, (puff_sx - puff_size_w//2, puff_sy - puff_size_h//2))
                
                drawn_clouds_count +=1
        
        # Lightning flashes for storms
        if weather.type == WeatherType.STORM:
            for strike in weather.lightning_strikes:
                # Intensity fades over the strike duration
                flash_intensity_factor = strike['intensity'] * (1 - (time.time() - strike['time']) / 0.30) # Duration 0.3s
                if flash_intensity_factor > 0:
                    flash_alpha = int(flash_intensity_factor * 150) # Max alpha for flash
                    flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    # Bright yellowish white flash
                    flash_surf.fill((255,255,230, flash_alpha)) 
                    self.screen.blit(flash_surf, (0,0))
                    # Optional: Draw a quick random line for a "bolt"
                    if random.random() < 0.3: # Only for some flashes
                        x_start, y_start = random.randint(0, WIDTH), 0
                        x_end, y_end = random.randint(x_start-100, x_start+100), random.randint(HEIGHT//3, HEIGHT//2)
                        pygame.draw.aaline(self.screen, (230,230,255, int(flash_alpha*0.8)), (x_start,y_start), (x_end,y_end), random.randint(1,3))


    def draw_attitude_indicator(self, aircraft: Aircraft, x, y, size):
        center_x, center_y = x + size // 2, y + size // 2
        radius = size // 2 - 8 # Main instrument radius

        # Background and bezel
        pygame.gfxdraw.filled_circle(self.screen, center_x, center_y, radius + 8, (30,30,30)) # Outer casing
        pygame.gfxdraw.aacircle(self.screen, center_x, center_y, radius + 8, (60,60,60))
        pygame.gfxdraw.filled_circle(self.screen, center_x, center_y, radius + 2, (10,10,10)) # Instrument face
        pygame.gfxdraw.aacircle(self.screen, center_x, center_y, radius + 2, (50,50,50))
        
        # Clipping mask for the moving sphere part
        clip_rect = pygame.Rect(center_x - radius, center_y - radius, 2 * radius, 2 * radius)
        original_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)

        # --- Draw the translating/rotating sphere part ---
        pixels_per_degree_pitch = radius / 30.0 # How much 1 degree of pitch moves the display vertically

        # Create a surface for the pitch/sky sphere
        # Larger surface to allow for rotation without cutting off edges
        sphere_surf_size = int(size * 1.8) 
        sphere_surface = pygame.Surface((sphere_surf_size, sphere_surf_size), pygame.SRCALPHA)
        sphere_surf_center_x, sphere_surf_center_y = sphere_surf_size // 2, sphere_surf_size // 2
        
        # Sky part (blue)
        sky_rect_height = sphere_surf_center_y - aircraft.pitch * pixels_per_degree_pitch
        pygame.draw.rect(sphere_surface, (70, 130, 180), (0, 0, sphere_surf_size, sky_rect_height))
        # Ground part (brown)
        pygame.draw.rect(sphere_surface, (139, 90, 43), (0, sky_rect_height, sphere_surf_size, sphere_surf_size - sky_rect_height))
        
        # Pitch lines on the sphere surface
        for p_deg in range(-60, 61, 10): # From -60 to +60 degrees, every 10
            # Y position of the line on the sphere surface, adjusted for current pitch
            line_screen_y_on_sphere = sphere_surf_center_y - (p_deg - aircraft.pitch) * pixels_per_degree_pitch
            
            # Cull lines far off the visible part of the sphere
            if abs(p_deg - aircraft.pitch) > 45 : continue

            line_width_adi = radius * (0.4 if p_deg == 0 else (0.25 if p_deg % 30 == 0 else 0.15))
            line_thickness = 2 if p_deg == 0 else 1 # Horizon line is thicker
            
            # Draw line using gfxdraw for AA
            # pygame.draw.line(sphere_surface, WHITE, (sphere_surf_center_x - line_width_adi, line_screen_y_on_sphere), 
            #                                       (sphere_surf_center_x + line_width_adi, line_screen_y_on_sphere), line_thickness)
            # Using aaline which takes separate start/end, so draw two segments for thickness > 1
            pygame.draw.aaline(sphere_surface, WHITE, (sphere_surf_center_x - line_width_adi, line_screen_y_on_sphere), 
                                                    (sphere_surf_center_x + line_width_adi, line_screen_y_on_sphere))
            if line_thickness > 1: # Draw adjacent line for thickness
                 pygame.draw.aaline(sphere_surface, WHITE, (sphere_surf_center_x - line_width_adi, line_screen_y_on_sphere+1), 
                                                    (sphere_surf_center_x + line_width_adi, line_screen_y_on_sphere+1))


            # Pitch angle numbers
            if p_deg != 0 and (p_deg % 20 == 0 or p_deg==10 or p_deg==-10): # Labels for 10, 20, 30, 40, etc.
                num_text_surf = self.font_small.render(str(abs(p_deg)), True, WHITE)
                # Position text next to lines
                sphere_surface.blit(num_text_surf, (sphere_surf_center_x - line_width_adi - 20, line_screen_y_on_sphere - num_text_surf.get_height()//2))
                sphere_surface.blit(num_text_surf, (sphere_surf_center_x + line_width_adi + 5, line_screen_y_on_sphere - num_text_surf.get_height()//2))

        # Rotate the sphere surface for roll
        rotated_sphere_surf = pygame.transform.rotate(sphere_surface, aircraft.roll)
        # Blit the rotated sphere onto the main screen, centered in the ADI
        self.screen.blit(rotated_sphere_surf, rotated_sphere_surf.get_rect(center=(center_x, center_y)))
        
        # Restore clipping
        self.screen.set_clip(original_clip)

        # --- Draw fixed ADI elements (aircraft symbol, roll scale) ---
        # Aircraft symbol (fixed part of ADI)
        pygame.draw.aaline(self.screen, YELLOW, (center_x - radius*0.4, center_y), (center_x - radius*0.1, center_y))
        pygame.draw.aaline(self.screen, YELLOW, (center_x + radius*0.1, center_y), (center_x + radius*0.4, center_y))
        pygame.draw.aaline(self.screen, YELLOW, (center_x - radius*0.1, center_y), (center_x, center_y - 5)) # Winglet up
        pygame.draw.aaline(self.screen, YELLOW, (center_x + radius*0.1, center_y), (center_x, center_y - 5)) # Winglet up
        pygame.gfxdraw.filled_circle(self.screen, center_x, center_y, 3, YELLOW) # Center dot

        # Roll indicator scale (fixed around the bezel)
        # Top roll pointer (triangle)
        pygame.draw.polygon(self.screen, YELLOW, [(center_x, center_y - radius + 8), 
                                                  (center_x-5, center_y-radius-2), 
                                                  (center_x+5, center_y-radius-2)])
        # Roll angle ticks (0, 10, 20, 30, 45, 60 degrees)
        roll_tick_angles = [-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60]
        for angle_deg in roll_tick_angles:
            if angle_deg == 0: continue # Skip center, already marked by triangle
            
            # Angle for drawing on circle (0 is right, 90 is up, etc.)
            # We want 0 at top, so subtract 90. No roll adjustment here, aircraft symbol rolls relative to this.
            rad = math.radians(angle_deg - 90) 
            
            tick_len_outer = radius + 1 # Tick starts slightly inside bezel
            tick_len_inner = radius - (6 if abs(angle_deg) % 30 == 0 else 3) # Major ticks longer
            
            start_x = center_x + tick_len_inner * math.cos(rad)
            start_y = center_y + tick_len_inner * math.sin(rad)
            end_x = center_x + tick_len_outer * math.cos(rad)
            end_y = center_y + tick_len_outer * math.sin(rad)
            pygame.draw.aaline(self.screen, WHITE, (start_x, start_y), (end_x, end_y))


    def draw_horizontal_situation_indicator(self, aircraft: Aircraft, nav_info, x, y, size):
        center_x, center_y = x + size // 2, y + size // 2
        radius = size // 2 - 8

        # Background and bezel
        pygame.gfxdraw.filled_circle(self.screen, center_x, center_y, radius + 8, (30,30,30))
        pygame.gfxdraw.aacircle(self.screen, center_x, center_y, radius + 8, (60,60,60))
        pygame.gfxdraw.filled_circle(self.screen, center_x, center_y, radius, BLACK) # Instrument face
        pygame.gfxdraw.aacircle(self.screen, center_x, center_y, radius, (50,50,50))

        # Rotating Compass Card
        for angle_deg_abs in range(0, 360, 10): # Every 10 degrees absolute heading
            # Angle on screen, adjusted for aircraft's current yaw
            # (absolute heading - current yaw - 90 for top-down display)
            angle_on_screen_rad = math.radians((angle_deg_abs - aircraft.yaw - 90 + 360)%360)
            
            is_cardinal = (angle_deg_abs % 90 == 0) # N, E, S, W
            is_major_tick = (angle_deg_abs % 30 == 0) # e.g., 30, 60, 120
            
            tick_len_hsi = radius * (0.18 if is_cardinal else (0.12 if is_major_tick else 0.08))
            tick_color = HUD_GREEN if is_cardinal else WHITE
            
            start_x_tick = center_x + (radius - tick_len_hsi) * math.cos(angle_on_screen_rad)
            start_y_tick = center_y + (radius - tick_len_hsi) * math.sin(angle_on_screen_rad)
            end_x_tick = center_x + radius * math.cos(angle_on_screen_rad)
            end_y_tick = center_y + radius * math.sin(angle_on_screen_rad)
            pygame.draw.aaline(self.screen, tick_color, (start_x_tick, start_y_tick), (end_x_tick, end_y_tick))

            # Heading labels
            if is_major_tick :
                if is_cardinal: 
                    label = "N" if angle_deg_abs == 0 else \
                            "E" if angle_deg_abs == 90 else \
                            "S" if angle_deg_abs == 180 else "W"
                else: 
                    label = str(angle_deg_abs // 10) # e.g., 3, 6, 12, 15
                
                text_surf_hsi = self.font_small.render(label, True, tick_color)
                text_dist_hsi = radius - tick_len_hsi - (12 if is_cardinal else 10) # Distance from center for text
                text_x_hsi = center_x + text_dist_hsi * math.cos(angle_on_screen_rad) - text_surf_hsi.get_width()//2
                text_y_hsi = center_y + text_dist_hsi * math.sin(angle_on_screen_rad) - text_surf_hsi.get_height()//2
                self.screen.blit(text_surf_hsi, (text_x_hsi, text_y_hsi))

        # Fixed Aircraft Symbol / Lubber Line (points to current heading at top)
        pygame.draw.polygon(self.screen, YELLOW, [ (center_x, center_y - 7), (center_x - 5, center_y + 5), (center_x + 5, center_y + 5)]) # Small triangle
        pygame.draw.aaline(self.screen, YELLOW, (center_x, center_y - radius), (center_x, center_y - radius + 15)) # Line at top

        # Autopilot Heading Bug
        if aircraft.autopilot_on and aircraft.ap_target_heading is not None:
            hdg_bug_abs = aircraft.ap_target_heading
            hdg_bug_screen_rad = math.radians((hdg_bug_abs - aircraft.yaw - 90 + 360)%360)
            
            bug_outer_x = center_x + radius * 0.95 * math.cos(hdg_bug_screen_rad)
            bug_outer_y = center_y + radius * 0.95 * math.sin(hdg_bug_screen_rad)
            bug_inner_x = center_x + radius * 0.85 * math.cos(hdg_bug_screen_rad)
            bug_inner_y = center_y + radius * 0.85 * math.sin(hdg_bug_screen_rad)
            # Draw a small magenta bug shape (e.g. a small line or chevron)
            pygame.draw.aaline(self.screen, CYAN, (bug_inner_x, bug_inner_y), (bug_outer_x, bug_outer_y))
            # Small perpendicular lines for bug "wings"
            bug_wing_len = 5
            bug_wing1_x = bug_outer_x + bug_wing_len * math.cos(hdg_bug_screen_rad + math.pi/2)
            bug_wing1_y = bug_outer_y + bug_wing_len * math.sin(hdg_bug_screen_rad + math.pi/2)
            bug_wing2_x = bug_outer_x + bug_wing_len * math.cos(hdg_bug_screen_rad - math.pi/2)
            bug_wing2_y = bug_outer_y + bug_wing_len * math.sin(hdg_bug_screen_rad - math.pi/2)
            pygame.draw.aaline(self.screen, CYAN, (bug_wing1_x, bug_wing1_y), (bug_wing2_x, bug_wing2_y))

        # Navigation Display (CDI - Course Deviation Indicator)
        if nav_info:
            # Desired Track (DTK) pointer (often a double arrow or line across compass)
            dtk_abs = nav_info['desired_track_deg']
            dtk_screen_rad = math.radians((dtk_abs - aircraft.yaw - 90 + 360)%360)
            
            # Course pointer line across the HSI
            crs_p1_x = center_x + (radius*0.85) * math.cos(dtk_screen_rad)
            crs_p1_y = center_y + (radius*0.85) * math.sin(dtk_screen_rad)
            crs_p2_x = center_x - (radius*0.85) * math.cos(dtk_screen_rad) # Opposite side
            crs_p2_y = center_y - (radius*0.85) * math.sin(dtk_screen_rad) # Opposite side
            pygame.draw.aaline(self.screen, PURPLE, (crs_p1_x, crs_p1_y), (crs_p2_x, crs_p2_y))
            # Arrowhead for course pointer
            # ... (can add small chevrons at crs_p1)

            # CDI bar (shows deviation from DTK)
            max_dev_hsi_display_deg = 10.0 # Full scale deflection = 10 degrees
            # Scaled deviation: -1 (full left) to +1 (full right)
            deviation_scaled = np.clip(nav_info['track_error_deg'] / max_dev_hsi_display_deg, -1.0, 1.0)
            
            cdi_bar_half_len_screen = radius * 0.5 # Length of the CDI bar on screen
            # Offset of CDI bar from center, perpendicular to DTK line
            cdi_bar_offset_pixels = deviation_scaled * (radius * 0.35) # Max offset on screen
            
            # Center of the CDI bar
            cdi_center_on_screen_x = center_x + cdi_bar_offset_pixels * math.cos(dtk_screen_rad + math.pi/2) # Perpendicular offset
            cdi_center_on_screen_y = center_y + cdi_bar_offset_pixels * math.sin(dtk_screen_rad + math.pi/2)
            
            # Endpoints of the CDI bar (aligned with DTK)
            cdi_p1_x = cdi_center_on_screen_x - cdi_bar_half_len_screen * math.cos(dtk_screen_rad)
            cdi_p1_y = cdi_center_on_screen_y - cdi_bar_half_len_screen * math.sin(dtk_screen_rad)
            cdi_p2_x = cdi_center_on_screen_x + cdi_bar_half_len_screen * math.cos(dtk_screen_rad)
            cdi_p2_y = cdi_center_on_screen_y + cdi_bar_half_len_screen * math.sin(dtk_screen_rad)
            pygame.draw.line(self.screen, PURPLE, (cdi_p1_x, cdi_p1_y), (cdi_p2_x, cdi_p2_y), 3) # Thicker line for CDI bar

            # TO/FROM indicator
            # Bearing to WP vs DTK. If bearing is close to DTK -> TO. If opposite -> FROM.
            bearing_to_wp_deg = nav_info['bearing_deg']
            angle_diff_brg_dtk = (bearing_to_wp_deg - dtk_abs + 540) % 360 - 180 # Shortest angle
            
            to_from_text = ""
            if abs(angle_diff_brg_dtk) < 85: to_from_text = "TO"  # Within ~85 deg of course
            elif abs(angle_diff_brg_dtk) > 95: to_from_text = "FR" # More than ~95 deg from course
            
            if to_from_text:
                tf_surf = self.font_small.render(to_from_text, True, PURPLE)
                # Position TO/FROM indicator (e.g., near center or along course line)
                self.screen.blit(tf_surf, (center_x - tf_surf.get_width()//2, center_y + radius*0.15))

        # Digital Heading Readout above HSI
        hdg_txt_surf = self.font_hud.render(f"{aircraft.yaw:03.0f}°", True, WHITE)
        readout_bg_rect = pygame.Rect(center_x - 25, y - 22, 50, 20)
        pygame.draw.rect(self.screen, BLACK, readout_bg_rect) # Small black background
        pygame.draw.rect(self.screen, DARK_GRAY, readout_bg_rect, 1) # Border
        self.screen.blit(hdg_txt_surf, (center_x - hdg_txt_surf.get_width()//2, y - 20))


    def draw_hud(self, aircraft: Aircraft, weather: Weather, camera: Camera, nav_info):
        # Determine base HUD color based on aircraft state
        hud_color = HUD_GREEN
        if aircraft.crashed: hud_color = RED
        elif aircraft.stall_warning_active or aircraft.overspeed_warning_active: hud_color = HUD_AMBER
        
        # Speed Tape (left side)
        speed_kts = math.sqrt(aircraft.vx**2 + aircraft.vy**2 + aircraft.vz**2) * 1.94384
        # Basic speed display box (can be expanded to a tape later)
        speed_box_x, speed_box_y, speed_box_w, speed_box_h = 30, HEIGHT//2 - 25, 80, 50
        pygame.draw.rect(self.screen, (*BLACK,180), (speed_box_x, speed_box_y, speed_box_w, speed_box_h), border_radius=3)
        spd_txt = self.font_hud_large.render(f"{speed_kts:3.0f}", True, hud_color)
        self.screen.blit(spd_txt, (speed_box_x + speed_box_w//2 - spd_txt.get_width()//2, 
                                   speed_box_y + speed_box_h//2 - spd_txt.get_height()//2 - 5))
        self.screen.blit(self.font_hud.render("KT", True, hud_color), 
                         (speed_box_x + speed_box_w//2 - 10, speed_box_y + speed_box_h - 20))

        # Altitude Tape (right side)
        alt_ft = aircraft.y * 3.28084
        alt_box_x, alt_box_y, alt_box_w, alt_box_h = WIDTH - 30 - 90, HEIGHT//2 - 25, 90, 50 # Wider for 5 digits
        pygame.draw.rect(self.screen, (*BLACK,180), (alt_box_x, alt_box_y, alt_box_w, alt_box_h), border_radius=3)
        alt_txt = self.font_hud_large.render(f"{alt_ft:5.0f}", True, hud_color)
        self.screen.blit(alt_txt, (alt_box_x + alt_box_w//2 - alt_txt.get_width()//2, 
                                  alt_box_y + alt_box_h//2 - alt_txt.get_height()//2 - 5))
        self.screen.blit(self.font_hud.render("FT", True, hud_color), 
                         (alt_box_x + alt_box_w//2 - 10, alt_box_y + alt_box_h - 20))

        # Primary Flight Instruments (ADI & HSI) at bottom center
        adi_hsi_size = 220 # Size of each instrument display
        total_width_instruments = adi_hsi_size * 2 + 20 # ADI, HSI, and spacing
        start_x_instruments = WIDTH//2 - total_width_instruments//2
        instruments_y = HEIGHT - adi_hsi_size - 15 # Positioned at bottom

        self.draw_attitude_indicator(aircraft, start_x_instruments, instruments_y, adi_hsi_size)
        self.draw_horizontal_situation_indicator(aircraft, nav_info, start_x_instruments + adi_hsi_size + 20, instruments_y, adi_hsi_size)

        # Cockpit overlay (if in cockpit view)
        if camera.mode == "cockpit":
            if self.cockpit_overlay_img: 
                self.screen.blit(self.cockpit_overlay_img, (0,0))
            else: # Fallback basic frame if image not loaded
                pygame.draw.rect(self.screen, (40,40,40,200), (0,0,WIDTH,HEIGHT), 30) # Semi-transparent border

        # Status indicators (top-right)
        status_x, status_y_start = WIDTH - 190, 20 # Start position for status block
        current_y_status = status_y_start
        # Background for status block
        pygame.draw.rect(self.screen, (*BLACK, 150), (status_x - 10, current_y_status -5, 190, 210), border_radius=5)

        def draw_status_line(label, value_str, color=hud_color):
            nonlocal current_y_status # Use status_y from outer scope
            lbl_surf = self.font_hud.render(label, True, LIGHT_GRAY) # Label in light gray
            val_surf = self.font_hud.render(value_str, True, color)  # Value in hud_color
            self.screen.blit(lbl_surf, (status_x, current_y_status))
            self.screen.blit(val_surf, (status_x + 75, current_y_status)) # Align values
            current_y_status += lbl_surf.get_height() + 3 # Spacing
            return current_y_status

        draw_status_line("THR", f"{aircraft.engine_rpm_percent:3.0f}%")
        fuel_gal = (aircraft.fuel / 0.8) / 3.785 if aircraft.fuel > 0 else 0 # kg to L, then L to Gal
        draw_status_line("FUEL", f"{fuel_gal:3.0f} Gal", RED if fuel_gal < (aircraft.config.fuel_capacity/0.8/3.785)*0.1 else hud_color)
        gear_status_text = "DOWN" if aircraft.gear_down else " UP "
        gear_color = LIME if aircraft.gear_down else \
                     (RED if speed_kts > 100 and not aircraft.gear_down and aircraft.y < 1000 else hud_color) # Red if gear up, fast, and low
        draw_status_line("GEAR", gear_status_text, gear_color)
        draw_status_line("FLAP", f"{aircraft.get_flaps_deflection():2.0f}°")
        draw_status_line("TRIM", f"{aircraft.pitch_trim:+3.1f}°") # Show sign and one decimal
        g_force_color = RED if aircraft.current_g_force > aircraft.config.max_g_force*0.85 else hud_color
        draw_status_line("  G ", f"{aircraft.current_g_force:3.1f}", g_force_color)

        if aircraft.autopilot_on:
            ap_s = self.font_hud.render("AUTOPILOT", True, CYAN); self.screen.blit(ap_s, (status_x, current_y_status)); current_y_status += ap_s.get_height() +2
            if aircraft.ap_target_altitude: draw_status_line(" AP ALT", f"{aircraft.ap_target_altitude*3.28084:5.0f} FT", CYAN)
            if aircraft.ap_target_heading: draw_status_line(" AP HDG", f"{aircraft.ap_target_heading:03.0f}°", CYAN)
            if aircraft.ap_target_speed: draw_status_line(" AP SPD", f"{aircraft.ap_target_speed*1.94384:3.0f} KT", CYAN)

        # Warnings (center top)
        warn_y_pos = 20
        warning_messages = []
        if aircraft.stall_warning_active: warning_messages.append(("STALL", RED))
        if aircraft.overspeed_warning_active: warning_messages.append(("OVERSPEED", RED))
        if not aircraft.engine_on and aircraft.type != AircraftType.GLIDER: warning_messages.append(("ENGINE OFF", RED))
        if aircraft.structural_integrity < 50: warning_messages.append((f"DAMAGE {aircraft.structural_integrity:.0f}%", RED))
        
        for msg_text, msg_color in warning_messages:
            msg_surf = self.font_hud_large.render(msg_text, True, msg_color)
            self.screen.blit(msg_surf, (WIDTH//2 - msg_surf.get_width()//2, warn_y_pos))
            warn_y_pos += msg_surf.get_height() + 2


        # NAV Display Block (top-left) if NAV mode active
        if nav_info:
            nav_block_x, nav_block_y, nav_block_w, nav_block_h = 20, 20, 280, 120 # Increased size
            pygame.draw.rect(self.screen, (*BLACK,150), (nav_block_x, nav_block_y, nav_block_w, nav_block_h), border_radius=5)
            
            current_ny_nav = nav_block_y + 8
            nx_val_nav = nav_block_x + 100 # Indent for values
            def draw_nav_line(label, value, color=WHITE):
                nonlocal current_ny_nav
                lbl_s = self.font_hud.render(label, True, LIGHT_GRAY); 
                val_s = self.font_hud.render(value, True, color)
                self.screen.blit(lbl_s, (nav_block_x + 8, current_ny_nav))
                self.screen.blit(val_s, (nx_val_nav, current_ny_nav))
                current_ny_nav += lbl_s.get_height() + 3
            
            draw_nav_line("WAYPOINT:", nav_info['wp_name'][:15], CYAN) # Allow more chars
            draw_nav_line("DISTANCE:", f"{nav_info['distance_nm']:.1f} NM")
            draw_nav_line("BEARING:", f"{nav_info['bearing_deg']:.0f}°")
            draw_nav_line("DTK:", f"{nav_info['desired_track_deg']:.0f}° (Dev {nav_info['track_error_deg']:.0f}°) ")
            alt_err_str = f"{nav_info['altitude_error_ft']:.0f}"
            if nav_info['altitude_error_ft'] > 0 : alt_err_str = "+" + alt_err_str
            draw_nav_line("WP ALT:", f"{nav_info['altitude_ft']:.0f} FT ({alt_err_str})")


    def draw_main_menu(self, buttons, selected_aircraft_type):
        self.screen.fill(NAVY) # Dark blue background
        title_surf = self.font_large.render("Pygame Flight Simulator Evo", True, GOLD)
        self.screen.blit(title_surf, (WIDTH//2 - title_surf.get_width()//2, HEIGHT//4 - 50))
        
        ac_text_surf = self.font_medium.render(f"Selected Aircraft: {selected_aircraft_type.value}", True, YELLOW)
        self.screen.blit(ac_text_surf, (WIDTH//2 - ac_text_surf.get_width()//2, HEIGHT//2 - 80))
        
        info_text_surf = self.font_small.render("Press 'C' to cycle aircraft. Mouse click or Enter to Start.", True, LIGHT_GRAY)
        self.screen.blit(info_text_surf, (WIDTH//2 - info_text_surf.get_width()//2, HEIGHT//2 - 40))
        
        for button in buttons: button.draw(self.screen)
        pygame.display.flip()

    def draw_pause_menu(self, buttons, help_visible, aircraft_controls_info):
        # Draw semi-transparent overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 20, 40, 200)) # Dark, semi-transparent blue
        self.screen.blit(overlay, (0,0))
        
        title_surf = self.font_large.render("GAME PAUSED", True, ORANGE)
        self.screen.blit(title_surf, (WIDTH//2 - title_surf.get_width()//2, 100))
        
        for button in buttons: button.draw(self.screen)
        
        help_start_y = HEIGHT//2 - 20 # Anchor for help text/box
        help_prompt_surf = self.font_small.render("Press 'H' for Controls | 'M' for Weather Cycle | 'C' for Next Flight Aircraft", True, LIGHT_GRAY)
        self.screen.blit(help_prompt_surf, (WIDTH//2 - help_prompt_surf.get_width()//2, help_start_y - 30))
        
        if help_visible:
            help_box_w, help_box_h = 560, 260 # Slightly larger for more controls
            help_box_x = WIDTH//2 - help_box_w//2
            pygame.draw.rect(self.screen, (*DARK_GRAY, 220), (help_box_x, help_start_y, help_box_w, help_box_h), border_radius=8)
            
            line_y_offset = 10
            for i, line in enumerate(aircraft_controls_info):
                txt_surf = self.font_small.render(line, True, WHITE)
                self.screen.blit(txt_surf, (help_box_x + 10, help_start_y + line_y_offset))
                line_y_offset += txt_surf.get_height() + 2 # Spacing
        
        pygame.display.flip()

    def draw_debrief_screen(self, aircraft: Aircraft, buttons):
        self.screen.fill((20,30,50)) # Dark background for debrief
        
        title_text = "SIMULATION ENDED"; title_color = ORANGE
        if aircraft.crashed: title_text = "AIRCRAFT CRASHED"; title_color = RED
        elif aircraft.landed_successfully: title_text = "LANDING SUCCESSFUL"; title_color = LIME
        
        title_surf = self.font_large.render(title_text, True, title_color)
        self.screen.blit(title_surf, (WIDTH//2 - title_surf.get_width()//2, 80))
        
        stats_y_start = 200; stats_x_center = WIDTH//2
        stats_lines = [
            f"Flight Time: {aircraft.flight_time_sec:.1f} s",
            f"Distance Flown: {aircraft.distance_traveled_m/1000:.2f} km ({aircraft.distance_traveled_m/1852:.1f} NM)",
            f"Max Altitude Reached: {aircraft.max_altitude_reached*3.28084:.0f} ft MSL",
            f"Max Speed Reached: {aircraft.max_speed_reached*1.94384:.0f} kts IAS",
            f"Fuel Used: {((aircraft.config.fuel_capacity - aircraft.fuel)/0.8)/3.785:.1f} Gal", # Assuming 0.8kg/L for fuel
            f"Structural Integrity: {aircraft.structural_integrity:.0f}%"
        ]
        if aircraft.landed_successfully:
            stats_lines.append(f"Touchdown V/S: {aircraft.touchdown_vertical_speed_mps*196.85:.0f} fpm") # m/s to fpm
            stats_lines.append(f"Landing Score: {aircraft.landing_score:.0f} / 100")
        
        current_stat_y = stats_y_start
        for stat_line_text in stats_lines:
            stat_surf = self.font_medium.render(stat_line_text, True, WHITE)
            self.screen.blit(stat_surf, (stats_x_center - stat_surf.get_width()//2, current_stat_y))
            current_stat_y += stat_surf.get_height() + 10 # Spacing
            
        for button in buttons: button.draw(self.screen)
        pygame.display.flip()


# FlightSimulator Class (Main Game Logic)
class FlightSimulator:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Pygame Flight Simulator Evo")
        self.clock = pygame.time.Clock()
        
        self.sound_manager = SoundManager() # Sounds are now disabled by default in SoundManager
        self.weather = Weather()
        self.terrain = Terrain()
        self.camera = Camera()
        self.renderer = Renderer(self.screen) # Initialize renderer with screen
        
        self.selected_aircraft_type = AircraftType.AIRLINER
        self.aircraft: Optional[Aircraft] = None

        self.game_state = GameState.MENU
        
        self.show_help_in_pause = False
        self.aircraft_controls_info = [ # Updated controls list
            "W/S: Pitch Control (Elevator)",
            "A/D: Roll Control (Ailerons)",
            "Q/E: Yaw Control (Rudder)",
            "LShift/LCtrl or PgUp/PgDn: Throttle",
            "Home: Max Throttle | End: Idle Throttle",
            "G: Toggle Landing Gear",
            "F/V: Flaps Extend/Retract",
            "B: Toggle Spoilers/Speed Brakes", 
            "Spacebar: Apply Wheel Brakes (Hold)",
            "[/]: Adjust Pitch Trim (Nose Up/Down)",
            "Tab: Toggle Autopilot (Preset Alt/Hdg/Spd)",
            "N: Toggle NAV Mode (Follow Waypoints)",
            "1: Cockpit View",
            "2: Chase Camera (Mouse Orbit)",
            "3: External Fixed Orbit Camera",
            "RMouse+Drag: Orbit Camera View",
            "Scroll Wheel: Zoom Camera In/Out",
            "R: Reset Current Flight (In-Game/Pause)",
            "P or Esc: Pause Game / Navigate Menus"
        ]
        self._init_buttons()

    def _init_buttons(self):
        btn_font = self.renderer.font_medium # Use renderer's font
        btn_w, btn_h = 260, 55 # Slightly wider buttons
        btn_spacing = 70
        
        # Menu Buttons
        start_y_menu = HEIGHT//2 + 10 # Adjusted start y
        self.menu_buttons = [
            Button(WIDTH//2 - btn_w//2, start_y_menu, btn_w, btn_h, "Start Flight", self.start_game, btn_font, self.sound_manager, color=DARK_GREEN, hover_color=GREEN),
            Button(WIDTH//2 - btn_w//2, start_y_menu + btn_spacing, btn_w, btn_h, "Quit Game", self.quit_game, btn_font, self.sound_manager, color=DARK_GRAY, hover_color=GRAY)
        ]
        
        # Pause Menu Buttons
        start_y_pause = HEIGHT//2 - 120
        self.pause_buttons = [
            Button(WIDTH//2 - btn_w//2, start_y_pause, btn_w, btn_h, "Resume Flight", self.toggle_pause, btn_font, self.sound_manager, color=DARK_GREEN, hover_color=GREEN),
            Button(WIDTH//2 - btn_w//2, start_y_pause + btn_spacing, btn_w, btn_h, "Main Menu", self.go_to_main_menu, btn_font, self.sound_manager),
            Button(WIDTH//2 - btn_w//2, start_y_pause + btn_spacing*2, btn_w, btn_h, "Quit Game", self.quit_game, btn_font, self.sound_manager, color=DARK_GRAY, hover_color=GRAY)
        ]
        
        # Debrief Screen Buttons
        start_y_debrief = HEIGHT - 220
        self.debrief_buttons = [
            Button(WIDTH//2 - btn_w//2, start_y_debrief, btn_w, btn_h, "Restart Flight", self.restart_flight, btn_font, self.sound_manager, color=DARK_BLUE, hover_color=BLUE),
            Button(WIDTH//2 - btn_w//2, start_y_debrief + btn_spacing, btn_w, btn_h, "Main Menu", self.go_to_main_menu, btn_font, self.sound_manager)
        ]

    def start_game(self):
        # Select an airport for starting position
        # Default to first airport if specific one not found
        start_airport = next((ap for ap in self.terrain.airports if "MAIN" in ap['name']), self.terrain.airports[0])
        
        # Create aircraft instance
        # Initial position: on runway or slightly above for air start
        initial_altitude = start_airport['elevation'] + 1.5 # Start on ground, gear height
        if self.selected_aircraft_type != AircraftType.GLIDER : # Air start for most
            initial_altitude = start_airport['elevation'] + 250 # ~800ft AGL air start
        
        self.aircraft = Aircraft(start_airport['x'], initial_altitude, start_airport['z'], self.selected_aircraft_type)
        self.aircraft.yaw = start_airport['runway_heading'] # Align with runway
        
        # Set initial speed if air start
        if initial_altitude > start_airport['elevation'] + 10:
            initial_speed_mps = self.aircraft.config.stall_speed_clean * 1.3 # Start above stall
            self.aircraft.vx = math.sin(math.radians(self.aircraft.yaw)) * initial_speed_mps
            self.aircraft.vz = math.cos(math.radians(self.aircraft.yaw)) * initial_speed_mps
            self.aircraft.on_ground = False
            self.aircraft.gear_down = False # Retract gear for air start
        else: # Ground start
            self.aircraft.on_ground = True
            self.aircraft.gear_down = True

        # Setup basic waypoints (e.g., to another airport)
        if len(self.terrain.airports) > 1:
            destination_airport = next((ap for ap in self.terrain.airports if ap['name'] != start_airport['name']), self.terrain.airports[1])
            self.aircraft.waypoints = [
                # Departure fix
                Waypoint(start_airport['x'] + math.sin(math.radians(start_airport['runway_heading']))*8000, # ~4NM out
                         start_airport['z'] + math.cos(math.radians(start_airport['runway_heading']))*8000,
                         start_airport['elevation'] + 1200, # ~4000ft AGL
                         "DEP FIX", "NAV"),
                # Arrival IAF (Initial Approach Fix)
                Waypoint(destination_airport['x'], destination_airport['z'], 
                         destination_airport['elevation'] + 600, # ~2000ft AGL at destination
                         destination_airport['name'].split(' ')[0] + " IAF", "NAV"), # e.g. KAPV IAF
                # Airport itself
                Waypoint(destination_airport['x'], destination_airport['z'], 
                         destination_airport['elevation'], 
                         destination_airport['name'], "AIRPORT")
            ]
        self.aircraft.current_waypoint_index = 0
        
        # Reset camera
        self.camera = Camera() # Fresh camera instance
        self.camera.mode = "follow_mouse_orbit" # Default view
        self.camera.distance = 35 if self.selected_aircraft_type in [AircraftType.AIRLINER, AircraftType.CARGO] else 20
        
        # Randomize weather slightly for new flight
        self.weather.type = random.choice(list(WeatherType))
        self.weather.update_conditions()
        self.weather.generate_clouds() # Ensure clouds match weather
        
        self.game_state = GameState.PLAYING
        # self.sound_manager.enabled = True # Enable sounds if you have them configured
        # if self.aircraft and self.sound_manager.enabled:
        #     self.sound_manager.play_engine_sound(self.aircraft.engine_rpm_percent, self.aircraft.type)

    def restart_flight(self):
        # if self.sound_manager.enabled: self.sound_manager.stop_all_sounds()
        self.start_game() # Re-initializes everything for a new flight

    def go_to_main_menu(self):
        # if self.sound_manager.enabled: self.sound_manager.stop_all_sounds()
        # self.sound_manager.enabled = False
        self.aircraft = None # Clear aircraft instance
        self.game_state = GameState.MENU
        pygame.mouse.set_visible(True) # Ensure mouse is visible in menu
        pygame.event.set_grab(False) # Ensure mouse is not grabbed
        
    def quit_game(self):
        self.running = False # Signal main loop to exit

    def toggle_pause(self):
        if self.game_state == GameState.PLAYING:
            self.game_state = GameState.PAUSED
            # self.sound_manager.enabled = False # Pause sounds
            pygame.mouse.set_visible(True); pygame.event.set_grab(False)
        elif self.game_state == GameState.PAUSED:
            self.game_state = GameState.PLAYING
            self.show_help_in_pause = False # Hide help when resuming
            # if self.aircraft: self.sound_manager.enabled = True # Resume sounds
            # Handle mouse grab if camera was orbiting
            if self.camera.is_mouse_orbiting : 
                pygame.mouse.set_visible(False); pygame.event.set_grab(True)

    def cycle_aircraft_type(self):
        types = list(AircraftType)
        try:
            current_idx = types.index(self.selected_aircraft_type)
            self.selected_aircraft_type = types[(current_idx + 1) % len(types)]
        except ValueError: # Should not happen if selected_aircraft_type is always valid
            self.selected_aircraft_type = types[0]
            
        if self.aircraft and self.game_state == GameState.PAUSED: # Info for next flight if in pause
            print(f"Next flight will use aircraft: {self.selected_aircraft_type.value}")
        elif self.game_state == GameState.MENU: # Directly update if in menu
             print(f"Selected aircraft: {self.selected_aircraft_type.value}")


    def handle_continuous_input(self, dt):
        if not self.aircraft: return
        keys = pygame.key.get_pressed()
        
        # Control authority scales with effectiveness (airspeed dependent)
        pitch_authority = self.aircraft.config.turn_rate * 0.8 * self.aircraft.elevator_effectiveness
        roll_authority = self.aircraft.config.turn_rate * 1.2 * self.aircraft.aileron_effectiveness # Ailerons usually more responsive
        yaw_authority = self.aircraft.config.turn_rate * 0.5 * self.aircraft.rudder_effectiveness
        
        # Pitch
        if keys[pygame.K_w]: self.aircraft.pitch_rate -= pitch_authority * dt * 2.0 # Adjusted sensitivity
        if keys[pygame.K_s]: self.aircraft.pitch_rate += pitch_authority * dt * 2.0
        # Apply pitch trim effect (trim adjust desired pitch_rate towards 0, or sets a constant rate)
        # Simplified: trim directly adds to pitch rate command (like holding stick slightly)
        self.aircraft.pitch_rate += self.aircraft.pitch_trim * 0.15 * self.aircraft.elevator_effectiveness * (dt*FPS if dt > 0 else 1) * 0.1 # Trim effect factor
        
        # Roll
        if keys[pygame.K_a]: self.aircraft.roll_rate -= roll_authority * dt * 2.5 # Adjusted sensitivity
        if keys[pygame.K_d]: self.aircraft.roll_rate += roll_authority * dt * 2.5
        
        # Yaw
        if keys[pygame.K_q]: self.aircraft.yaw_rate -= yaw_authority * dt * 2.0
        if keys[pygame.K_e]: self.aircraft.yaw_rate += yaw_authority * dt * 2.0
        
        # Clamp rates to sensible maximums
        self.aircraft.pitch_rate = np.clip(self.aircraft.pitch_rate, -50, 50) # Deg/s
        self.aircraft.roll_rate = np.clip(self.aircraft.roll_rate, -120, 120) # Deg/s
        self.aircraft.yaw_rate = np.clip(self.aircraft.yaw_rate, -30, 30)   # Deg/s
        
        # Throttle
        throttle_change_rate_percent_sec = 30.0 # % per second
        if keys[pygame.K_LSHIFT] or keys[pygame.K_PAGEUP]: 
            self.aircraft.thrust_input = min(100, self.aircraft.thrust_input + throttle_change_rate_percent_sec * dt)
        if keys[pygame.K_LCTRL] or keys[pygame.K_PAGEDOWN]: 
            self.aircraft.thrust_input = max(0, self.aircraft.thrust_input - throttle_change_rate_percent_sec * dt)
        
        # Brakes
        self.aircraft.brakes_input = 1.0 if keys[pygame.K_SPACE] else 0.0


    def handle_event(self, event):
        if self.aircraft: self.camera.handle_mouse_input(event, self.aircraft)
        
        if self.game_state == GameState.MENU:
            for btn in self.menu_buttons: 
                if btn.handle_event(event): return # Event handled by button
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER: self.start_game()
                if event.key == pygame.K_c: self.cycle_aircraft_type()
        
        elif self.game_state == GameState.PAUSED:
            for btn in self.pause_buttons: 
                if btn.handle_event(event): return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_h: self.show_help_in_pause = not self.show_help_in_pause
                if event.key == pygame.K_c: self.cycle_aircraft_type() # Cycle for next flight
                if event.key == pygame.K_m: # Cycle weather manually
                    current_idx = list(WeatherType).index(self.weather.type)
                    self.weather.type = list(WeatherType)[(current_idx + 1) % len(list(WeatherType))]
                    self.weather.update_conditions(); self.weather.generate_clouds()
                    print(f"Weather manually set to: {self.weather.type.value}")
                if event.key == pygame.K_r: self.restart_flight()
        
        elif self.game_state == GameState.PLAYING and self.aircraft:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_g: self.aircraft.toggle_gear(self.sound_manager)
                if event.key == pygame.K_f: self.aircraft.set_flaps(1, self.sound_manager) # Extend
                if event.key == pygame.K_v: self.aircraft.set_flaps(-1, self.sound_manager) # Retract
                if event.key == pygame.K_b: self.aircraft.spoilers_deployed = not self.aircraft.spoilers_deployed; print(f"Spoilers: {'DEPLOYED' if self.aircraft.spoilers_deployed else 'RETRACTED'}")
                
                if event.key == pygame.K_LEFTBRACKET: self.aircraft.pitch_trim -= 0.1
                if event.key == pygame.K_RIGHTBRACKET: self.aircraft.pitch_trim += 0.1
                self.aircraft.pitch_trim = np.clip(self.aircraft.pitch_trim, -5.0, 5.0) # Clamp trim range
                
                if event.key == pygame.K_END: self.aircraft.thrust_input = 0 # Idle thrust
                if event.key == pygame.K_HOME: self.aircraft.thrust_input = 100 # Max thrust
                
                # Camera view changes
                if event.key == pygame.K_1: self.camera.mode = "cockpit"
                if event.key == pygame.K_2: self.camera.mode = "follow_mouse_orbit"; self.camera.distance=max(15,self.camera.distance)
                if event.key == pygame.K_3: self.camera.mode = "external_fixed_mouse_orbit"; self.camera.distance=max(25,self.camera.distance) # Example fixed orbit mode
                
                if event.key == pygame.K_TAB: # Toggle Autopilot
                    self.aircraft.autopilot_on = not self.aircraft.autopilot_on
                    if self.aircraft.autopilot_on: 
                        # Set AP targets to current values if not already set
                        if self.aircraft.ap_target_altitude is None: self.aircraft.ap_target_altitude = self.aircraft.y
                        if self.aircraft.ap_target_heading is None: self.aircraft.ap_target_heading = self.aircraft.yaw
                        if self.aircraft.ap_target_speed is None: self.aircraft.ap_target_speed = math.sqrt(self.aircraft.vx**2 + self.aircraft.vy**2 + self.aircraft.vz**2)
                        print("Autopilot Engaged. Targets: ALT, HDG, SPD.")
                    else: 
                        print("Autopilot Disengaged.")
                
                if event.key == pygame.K_n: # Toggle NAV mode for waypoints
                    self.aircraft.nav_mode_active = not self.aircraft.nav_mode_active
                    print(f"NAV mode {'ACTIVE' if self.aircraft.nav_mode_active else 'INACTIVE'}")
                    # If AP is on and NAV mode activated, AP should use NAV targets
                    if self.aircraft.autopilot_on and self.aircraft.nav_mode_active:
                        nav_data = self.aircraft.get_nav_display_info()
                        if nav_data:
                            self.aircraft.ap_target_heading = nav_data['desired_track_deg']
                            self.aircraft.ap_target_altitude = self.aircraft.waypoints[self.aircraft.current_waypoint_index].altitude
                            # Speed can be managed manually or from waypoint data if available
                
                if event.key == pygame.K_r: self.restart_flight()
        
        elif self.game_state == GameState.DEBRIEF:
            for btn in self.debrief_buttons: 
                if btn.handle_event(event): return
        
        # Global quit and pause/menu navigation
        if event.type == pygame.QUIT: self.running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.game_state == GameState.PLAYING: self.toggle_pause()
                elif self.game_state == GameState.PAUSED: self.toggle_pause() # Resume
                elif self.game_state == GameState.MENU: self.quit_game()
                elif self.game_state == GameState.DEBRIEF: self.go_to_main_menu()
            
            if event.key == pygame.K_p and (self.game_state == GameState.PLAYING or self.game_state == GameState.PAUSED) : 
                self.toggle_pause()

    def update(self, dt):
        if self.game_state == GameState.PLAYING and self.aircraft:
            self.handle_continuous_input(dt) # Process sustained key presses
            self.aircraft.update(dt, self.weather, self.sound_manager) # Update aircraft physics & systems
            self.weather.update(dt) # Update weather conditions
            self.camera.update(self.aircraft, dt) # Update camera position and target
            
            # Minimal sound update logic (if sounds are re-enabled and implemented)
            # Example: adjust engine sound volume based on RPM
            # if self.sound_manager.enabled and self.aircraft.engine_on and self.aircraft.fuel > 0:
            #     if self.sound_manager.engine_channel is None or not self.sound_manager.engine_channel.get_busy():
            #          # self.sound_manager.play_engine_sound(self.aircraft.engine_rpm_percent, self.aircraft.type)
            #          pass # Actual sound playing logic
            #     elif self.sound_manager.engine_channel:
            #          # self.sound_manager.engine_channel.set_volume(0.05 + (self.aircraft.engine_rpm_percent / 100.0) * 0.25)
            #          pass # Volume adjustment logic
            # elif self.sound_manager.engine_channel and self.sound_manager.engine_channel.get_busy():
            #     # self.sound_manager.engine_channel.stop()
            #     pass

            # Transition to Debrief state
            if self.aircraft.crashed or \
               (self.aircraft.on_ground and math.sqrt(self.aircraft.vx**2 + self.aircraft.vz**2) < 0.2 and self.aircraft.landed_successfully and self.aircraft.thrust_input < 5): # Stopped after successful landing
                self.game_state = GameState.DEBRIEF
                # if self.sound_manager.enabled: self.sound_manager.stop_all_sounds()
                # self.sound_manager.enabled = False
                pygame.mouse.set_visible(True); pygame.event.set_grab(False) # Ensure mouse is usable
    
    def render(self):
        if self.game_state == GameState.MENU: 
            self.renderer.draw_main_menu(self.menu_buttons, self.selected_aircraft_type)
        elif self.game_state == GameState.PAUSED: 
            self.renderer.draw_pause_menu(self.pause_buttons, self.show_help_in_pause, self.aircraft_controls_info)
        elif self.game_state == GameState.DEBRIEF and self.aircraft: 
            self.renderer.draw_debrief_screen(self.aircraft, self.debrief_buttons)
        elif self.game_state == GameState.PLAYING and self.aircraft:
            # Main rendering sequence for flight
            self.renderer.draw_horizon_and_sky(self.aircraft, self.camera)
            self.renderer.draw_terrain_features(self.camera, self.terrain, self.weather) # Airports, trees
            self.renderer.draw_aircraft_model(self.aircraft, self.camera)
            self.renderer.draw_weather_effects(self.weather, self.camera, self.aircraft) # Rain, snow, fog, clouds
            
            nav_data = self.aircraft.get_nav_display_info() # Get data for HSI/NAV display
            self.renderer.draw_hud(self.aircraft, self.weather, self.camera, nav_data) # Draw HUD and instruments
            
            pygame.display.flip() # Update the full display
        else: # Fallback for unknown states or if aircraft not loaded
            self.screen.fill(BLACK)
            pygame.display.flip()

    def run(self):
        self.running = True
        while self.running:
            # Delta time calculation
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05) # Cap dt to prevent large simulation steps if lagging (max 20 FPS equivalent sim step)
            
            for event in pygame.event.get(): # Process all events
                self.handle_event(event)
            
            self.update(dt) # Update game logic and physics
            self.render()   # Draw the current game state
            
            pygame.display.set_caption(f"Pygame Flight Sim Evo - FPS: {self.clock.get_fps():.1f}")


        # if self.sound_manager.enabled: self.sound_manager.stop_all_sounds()
        pygame.quit()

if __name__ == "__main__":
    # Ensure a dummy cockpit overlay exists if the real one is missing
    try: 
        open("cockpit_overlay.png", "rb").close()
    except FileNotFoundError:
        try:
            print("cockpit_overlay.png not found, creating a dummy.")
            dummy_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA) # Use SRCALPHA for transparency
            # Simple frame: transparent center, semi-transparent borders
            frame_color = (50, 50, 60, 180) # Dark semi-transparent gray
            border_thickness = 80
            # Top border
            pygame.draw.rect(dummy_surf, frame_color, (0, 0, WIDTH, border_thickness))
            # Bottom border (for instruments, usually part of HUD) - can be smaller or different
            pygame.draw.rect(dummy_surf, frame_color, (0, HEIGHT - border_thickness - 150, WIDTH, border_thickness + 150)) # Larger bottom for "dashboard"
            # Side borders
            pygame.draw.rect(dummy_surf, frame_color, (0, 0, border_thickness, HEIGHT))
            pygame.draw.rect(dummy_surf, frame_color, (WIDTH - border_thickness, 0, border_thickness, HEIGHT))
            pygame.image.save(dummy_surf, "cockpit_overlay.png")
            print("Created dummy cockpit_overlay.png")
        except Exception as e_img_create: 
            print(f"Could not create dummy cockpit_overlay.png: {e_img_create}")
    
    print("Sound file checks/creation are disabled by user modifications.")

    sim = FlightSimulator()
    sim.run()
