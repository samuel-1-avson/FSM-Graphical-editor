
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
BLUE = (135, 206, 235) # Sky blue
DARK_BLUE = (0, 102, 204) # Darker Sky (changed from original for better contrast)
GREEN = (34, 139, 34) # Ground Green
DARK_GREEN = (0, 100, 0)
BROWN = (165, 42, 42) # Ground Brown (ADI) (changed for better ground color)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)
CYAN = (0, 255, 255)
LIGHT_GRAY = (192, 192, 192)
GOLD = (255, 215, 0)
LIME = (0, 255, 0) # Used for HUD elements often
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
    lift_coefficient_max: float # Approx Cl_max for clean configuration
    wing_area: float
    aspect_ratio: float
    max_speed: float # Vne (Never Exceed Speed) in m/s
    fuel_capacity: float # Liters
    fuel_consumption: float # Liters per second at max thrust (100% RPM)
    max_altitude: float # Theoretical max altitude, m
    turn_rate: float # Max sustained turn rate deg/s (example, actual varies)
    stall_speed_clean: float # Vs1 (stall speed clean) in m/s
    service_ceiling: float # m
    max_g_force: float # Positive G limit
    climb_rate: float # Max initial climb rate m/s
    engine_count: int = 1
    critical_aoa_positive: float = 15.0 # Degrees
    critical_aoa_negative: float = -12.0 # Degrees
    cl_alpha: float = 2 * math.pi * 0.08 # Lift curve slope (per degree AoA, simplified from per radian)
    engine_spool_rate: float = 0.2 # How fast engine RPM changes (% of total RPM range per second)

@dataclass
class Waypoint:
    x: float
    z: float
    altitude: float # meters
    name: str
    waypoint_type: str = "NAV"
    required_speed: Optional[float] = None # m/s
    required_altitude_tolerance: float = 100.0 # meters

class SoundManager:
    def __init__(self):
        self.sounds: Dict[str, Optional[pygame.mixer.Sound]] = {}
        self.engine_channel: Optional[pygame.mixer.Channel] = None
        self.warning_channel: Optional[pygame.mixer.Channel] = None
        self.ambient_channel: Optional[pygame.mixer.Channel] = None
        self.enabled = True
        self.load_sounds()

    def load_sounds(self):
        sound_files = {
            'stall_warning': "stall_warning.wav",
            'gear_up': "gear_up.wav",
            'gear_down': "gear_down.wav",
            'click': "click.wav" # For UI buttons
        }
        for name, filename in sound_files.items():
            try:
                self.sounds[name] = pygame.mixer.Sound(filename)
            except pygame.error as e:
                print(f"Warning: Could not load sound file {filename}: {e}")
                self.sounds[name] = None

    def create_synthetic_sound(self, frequency, duration=0.1, volume=0.1, shape='sine'):
        if not self.enabled or not pygame.mixer.get_init(): return None # Check if mixer is initialized
        sample_rate = pygame.mixer.get_init()[0]
        if sample_rate == 0: return None # Mixer not properly initialized
        
        frames = int(duration * sample_rate)
        arr = np.zeros((frames, 2), dtype=np.float32) # Stereo

        for i in range(frames):
            t_sample = float(i) / sample_rate
            if shape == 'sine':
                wave = np.sin(2 * np.pi * frequency * t_sample)
            elif shape == 'square':
                wave = np.sign(np.sin(2 * np.pi * frequency * t_sample))
            elif shape == 'sawtooth':
                # More harmonics for engine
                wave = 0.6 * (2 * (t_sample * frequency - np.floor(0.5 + t_sample * frequency))) # Saw
                wave += 0.3 * np.sin(2 * np.pi * frequency * 2 * t_sample) # Add harmonic
                wave += 0.1 * np.random.uniform(-1,1) # Add a bit of noise
            else: # noise as default
                wave = np.random.uniform(-1, 1)
            
            arr[i, 0] = wave * volume # Left channel
            arr[i, 1] = wave * volume # Right channel
        
        sound_array = np.clip(arr * 32767, -32768, 32767).astype(np.int16)
        try:
            return pygame.sndarray.make_sound(sound_array)
        except Exception as e:
            print(f"Error creating synthetic sound: {e}")
            return None


    def play_engine_sound(self, rpm_percent, engine_type=AircraftType.AIRLINER):
        if not self.enabled or not pygame.mixer.get_init(): return
        
        base_freq = 60 # Lower base for rumble
        if engine_type == AircraftType.FIGHTER: base_freq = 80
        elif engine_type == AircraftType.ULTRALIGHT: base_freq = 120

        # More pronounced frequency change with RPM
        current_freq = base_freq + (rpm_percent / 100.0) * (base_freq * 2.5)
        current_volume = 0.05 + (rpm_percent / 100.0) * 0.25 # Volume also scales with RPM

        if self.engine_channel is None or not self.engine_channel.get_busy():
            # Create a longer looping sound
            engine_loop_sound = self.create_synthetic_sound(current_freq, duration=1.0, volume=current_volume, shape='sawtooth')
            if engine_loop_sound:
                self.engine_channel = engine_loop_sound.play(loops=-1) # Play indefinitely
        
        if self.engine_channel and self.engine_channel.get_sound():
            # Adjust volume dynamically (frequency change needs recreating the sound, which is expensive for loops)
            self.engine_channel.set_volume(current_volume)
            # For frequency, a proper synth is needed. This is a placeholder.
            # If freq changes drastically, one might stop and restart the sound, but it can be choppy.
            # A more advanced approach involves an audio stream that's continuously updated.
            pass


    def play_sound(self, sound_name, loops=0):
        if not self.enabled or not pygame.mixer.get_init(): return
        
        sound_to_play = self.sounds.get(sound_name)
        if sound_to_play:
            sound_to_play.play(loops)
        elif sound_name == 'stall_warning':
            self.play_warning_beep(frequency=700, duration=0.4, volume=0.4) # Distinct stall beep
        elif sound_name in ['gear_up', 'gear_down', 'flaps_move']:
             self.play_warning_beep(frequency=300, duration=0.3, volume=0.2) # Generic mechanical
        elif sound_name == 'click':
            self.play_warning_beep(frequency=1000, duration=0.05, volume=0.3)


    def play_warning_beep(self, frequency=800, duration=0.2, volume=0.3):
        if not self.enabled or not pygame.mixer.get_init(): return
        # Ensure only one warning beep plays at a time or queue them
        if self.warning_channel is None or not self.warning_channel.get_busy():
            sound = self.create_synthetic_sound(frequency, duration, volume, shape='square')
            if sound: self.warning_channel = sound.play()

    def stop_all_sounds(self):
        if not pygame.mixer.get_init(): return
        if self.engine_channel: self.engine_channel.stop()
        if self.warning_channel: self.warning_channel.stop()
        if self.ambient_channel: self.ambient_channel.stop()
        pygame.mixer.stop() # Stops all active sounds on all channels

# Corrected Weather Class
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
                # Reduce particle count for performance; billboards are expensive
                for _ in range(int(layer['coverage'] * 20)): # Reduced from 50
                    particle = {
                        'x': random.uniform(-15000, 15000), # Wider distribution for particles
                        'z': random.uniform(-15000, 15000),
                        'y': layer['altitude'] + random.uniform(-layer['thickness']/2, layer['thickness']/2),
                        'size': random.uniform(200, 800) * layer['coverage'], # World size
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
            self.wind_gusts = random.uniform(0, self.wind_speed * 0.6) # Gusts can be stronger
        else:
            self.wind_gusts *= (1 - 0.5 * dt) # More gradual decay

        if self.type == WeatherType.STORM and random.random() < 0.008: # More frequent lightning
            self.lightning_strikes.append({
                'x': random.uniform(-15000, 15000),
                'z': random.uniform(-15000, 15000),
                'intensity': random.uniform(0.7, 1.0),
                'time': time.time()
            })

        current_time = time.time()
        self.lightning_strikes = [s for s in self.lightning_strikes if current_time - s['time'] < 0.25] # Slightly longer flash

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
        self.flaps_degrees = [0, 10, 25, 40] # Example flap deflections
        self.spoilers_deployed = False
        self.brakes_input = 0.0 # 0-1 strength
        
        self.autopilot_on = False
        self.ap_target_altitude: Optional[float] = None
        self.ap_target_heading: Optional[float] = None
        self.ap_target_speed: Optional[float] = None
        
        self.engine_on = True
        
        self.configs = {
            AircraftType.FIGHTER: AircraftConfig("F-16", 120000, 8500, 0.016, 1.6, 30, 8, 650, 3000, 0.1, 18000, 15, 70, 15000, 9.0, 250, engine_count=1, critical_aoa_positive=20.0, cl_alpha=0.11, engine_spool_rate=0.5), # cl_alpha per degree
            AircraftType.AIRLINER: AircraftConfig("B737", 110000, 75000, 0.020, 1.5, 125, 9, 280, 26000, 0.06, 14000, 3, 65, 12500, 2.5, 150, engine_count=2, critical_aoa_positive=16.0, cl_alpha=0.1, engine_spool_rate=0.15),
            AircraftType.GLIDER: AircraftConfig("ASK-21", 0, 600, 0.010, 1.8, 17, 26, 70, 0, 0, 10000, 4, 30, 8000, 4.5, 20, engine_count=0, critical_aoa_positive=14.0, cl_alpha=0.1),
            AircraftType.CARGO: AircraftConfig("C-130", 4 * 15000, 70000, 0.028, 1.2, 160, 7, 180, 20000, 0.09, 10000, 2, 55, 9000, 2.0, 100, engine_count=4, critical_aoa_positive=15.0, cl_alpha=0.09, engine_spool_rate=0.1),
            AircraftType.ULTRALIGHT: AircraftConfig("Quicksilver", 3000, 250, 0.030, 1.4, 15, 10, 30, 50, 0.12, 3000, 5, 20, 2500, 3.0, 20, engine_count=1, critical_aoa_positive=18.0, cl_alpha=0.09, engine_spool_rate=0.3),
            AircraftType.HELICOPTER: AircraftConfig("UH-60", 2*1200, 5200, 0.06, 0.4, 20, 5, 80, 1300, 0.15, 6000, 10, 0, 5800, 3.5, 50, engine_count=2, critical_aoa_positive=90.0, cl_alpha=0.05), # Placeholder
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
        wing_chord = (wing_span / self.config.aspect_ratio) if self.config.aspect_ratio > 0 else 2.0 # Calculate based on AR
        tail_height = 3.5 if aircraft_type == AircraftType.AIRLINER else 2.5
        
        self.model_vertices_local = [
            (fuselage_radius, -fuselage_radius, fuselage_length * 0.6), (fuselage_radius, fuselage_radius, fuselage_length * 0.6),
            (-fuselage_radius, fuselage_radius, fuselage_length * 0.6), (-fuselage_radius, -fuselage_radius, fuselage_length * 0.6), # Nose section front face (0-3)
            (fuselage_radius, -fuselage_radius, -fuselage_length * 0.4), (fuselage_radius, fuselage_radius, -fuselage_length * 0.4),
            (-fuselage_radius, fuselage_radius, -fuselage_length * 0.4), (-fuselage_radius, -fuselage_radius, -fuselage_length * 0.4), # Tail section back face (4-7)
            # Wings (root at y=0, z around CG)
            (wing_span/2, 0, wing_chord/2), (wing_span/2, 0, -wing_chord/2), # Right wingtip fore/aft (8,9)
            (-wing_span/2, 0, wing_chord/2), (-wing_span/2, 0, -wing_chord/2),# Left wingtip fore/aft (10,11)
            (fuselage_radius *0.8, 0, wing_chord/2), (fuselage_radius*0.8, 0, -wing_chord/2), # Right wing root (12,13)
            (-fuselage_radius*0.8, 0, wing_chord/2), (-fuselage_radius*0.8, 0, -wing_chord/2),# Left wing root (14,15)
            # Tail (Vertical Stabilizer)
            (0, tail_height, -fuselage_length*0.35), (0, 0, -fuselage_length*0.35), (0,0,-fuselage_length*0.45 + wing_chord*0.2), # Vert stab top, base_fwd, base_aft (16,17,18)
            # Horizontal Stabilizer (smaller span than main wings)
            (wing_span/3.5, 0, -fuselage_length*0.38), (-wing_span/3.5, 0, -fuselage_length*0.38), # Horiz stab tips (19,20)
            (0, 0, -fuselage_length*0.30) # Horiz stab center forward (for visual connection) (21)
        ]
        self.model_lines = [
            (0,1), (1,2), (2,3), (3,0), (4,5), (5,6), (6,7), (7,4), # Fuselage front/back faces
            (0,4), (1,5), (2,6), (3,7), # Fuselage longitudinal lines
            (8,12), (9,13), (12,13), (8,9), # Right wing surface outline
            (10,14), (11,15), (14,15), (10,11), # Left wing surface outline
            (12,14), (13,15), # Connecting wing roots across fuselage (approx)
            (16,17), (17,18), (18,16), # Vertical stabilizer
            (19,21), (20,21), (19,20) # Horizontal stabilizer (simplified triangle)
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
        
        self.aoa_degrees = np.clip(self.aoa_degrees, -30, 30) # Realistic AoA limits for normal flight

        cl = 0.0
        # Cl from AoA (using per-degree slope)
        cl_from_aoa = self.config.cl_alpha * self.aoa_degrees
        
        if self.aoa_degrees > self.config.critical_aoa_positive:
            self.stall_warning_active = True
            overshoot = self.aoa_degrees - self.config.critical_aoa_positive
            cl = self.config.lift_coefficient_max - overshoot * 0.05 # Gradual Cl drop post-stall
            cl = max(0.1, cl)
        elif self.aoa_degrees < self.config.critical_aoa_negative:
            self.stall_warning_active = True
            overshoot = abs(self.aoa_degrees - self.config.critical_aoa_negative)
            cl = -self.config.lift_coefficient_max + overshoot * 0.05
            cl = min(-0.1, cl)
        else:
            self.stall_warning_active = False
            cl = cl_from_aoa
        
        cl_flaps = (self.get_flaps_deflection() / 40.0) * 0.7 # Max 0.7 Cl bonus from flaps
        cl += cl_flaps
        cl = np.clip(cl, -self.config.lift_coefficient_max -0.4, self.config.lift_coefficient_max + 0.4)

        cd_base = self.config.drag_coefficient_base
        cd_induced = (cl**2) / (math.pi * 0.75 * self.config.aspect_ratio) if self.config.aspect_ratio > 0 else 0 # e=0.75
        
        cd_flaps = (self.get_flaps_deflection() / 40.0)**1.5 * 0.06 # Non-linear flap drag
        cd_gear = 0.020 if self.gear_down else 0.002
        cd_spoilers = 0.08 if self.spoilers_deployed else 0.0
        cd_ice = self.ice_buildup_kg * 0.0002

        cd_total = cd_base + cd_induced + cd_flaps + cd_gear + cd_spoilers + cd_ice

        lift_force = cl * q * self.config.wing_area
        drag_force = cd_total * q * self.config.wing_area

        if self.spoilers_deployed:
            lift_force *= 0.65 # Spoilers reduce lift significantly

        effectiveness_factor = np.clip(q / (0.5 * 1.225 * (self.config.stall_speed_clean*1.5)**2), 0.1, 1.0) # Scale with q, min 10%
        self.elevator_effectiveness = effectiveness_factor
        self.aileron_effectiveness = effectiveness_factor
        self.rudder_effectiveness = effectiveness_factor

        return lift_force, drag_force

    def apply_forces_and_torques(self, dt, lift, drag, thrust_force, weather, current_speed_mps):
        current_mass = self.get_current_mass()
        gravity_force_y = -9.81 * current_mass

        # --- Forces in Body Axes (X_b right, Y_b up, Z_b forward) ---
        # Thrust acts along Z_b
        F_body_z = thrust_force
        # Drag acts opposite to velocity vector, Lift perpendicular.
        # For simplicity, project Lift and Drag onto body axes based on AoA and slip (slip ignored here)
        # Assume Lift is primarily along Y_b, Drag along -Z_b relative to airflow.
        # For now, take total L and D and rotate them from a "wind" frame to body frame.
        # This is simplified: true L/D are defined in wind axes.
        
        # Transform forces from body to world frame
        # Rotation angles (ensure consistent definition for rotations)
        p_rad, y_rad, r_rad = math.radians(self.pitch), math.radians(self.yaw), math.radians(self.roll)
        
        cos_p, sin_p = math.cos(p_rad), math.sin(p_rad)
        cos_y, sin_y = math.cos(y_rad), math.sin(y_rad)
        cos_r, sin_r = math.cos(r_rad), math.sin(r_rad)

        # Body Z-axis (thrust vector) in world frame
        body_z_x = cos_p * sin_y
        body_z_y = sin_p
        body_z_z = cos_p * cos_y # If +Z world is North, +X world is East

        thrust_fx = thrust_force * body_z_x
        thrust_fy = thrust_force * body_z_y
        thrust_fz = thrust_force * body_z_z
        
        # Body Y-axis (lift vector approx) in world frame
        # Lift acts along aircraft's Y_body axis. Transform this axis to world.
        # Y_body_world_x = sin_r * cos_y + cos_r * sin_p * sin_y  (Full rotation matrix Y column)
        # Y_body_world_y = cos_r * cos_p
        # Y_body_world_z = sin_r * sin_y - cos_r * sin_p * cos_y
        # Simplified: lift primarily opposes gravity, modified by roll and pitch
        lift_fx = lift * (cos_r * sin_p * sin_y - sin_r * cos_y)
        lift_fy = lift * (cos_r * cos_p)
        lift_fz = lift * (cos_r * sin_p * cos_y + sin_r * sin_y)

        # Drag acts opposite to velocity vector
        if current_speed_mps > 0.1:
            drag_fx = -drag * (self.vx / current_speed_mps)
            drag_fy = -drag * (self.vy / current_speed_mps)
            drag_fz = -drag * (self.vz / current_speed_mps)
        else:
            drag_fx, drag_fy, drag_fz = 0,0,0
        
        # Wind forces
        # V_rel = V_aircraft - V_wind. Wind effect is complex.
        # Simplified: Add wind as a direct force/acceleration component.
        wind_effect_x = weather.wind_speed * 0.5144 * math.cos(math.radians(weather.wind_direction)) # knots to m/s for speed
        wind_effect_z = weather.wind_speed * 0.5144 * math.sin(math.radians(weather.wind_direction))
        # This should affect relative airspeed for aero calculations, or be a force.
        # For now, treat as an additional acceleration (scaled)
        wind_accel_x = (wind_effect_x - self.vx) * 0.05 # Aircraft tries to match wind slowly
        wind_accel_z = (wind_effect_z - self.vz) * 0.05
        
        # Total forces in world coordinates
        total_fx = thrust_fx + drag_fx + lift_fx # + wind_accel_x * current_mass (if treated as force)
        total_fy = thrust_fy + drag_fy + lift_fy + gravity_force_y
        total_fz = thrust_fz + drag_fz + lift_fz # + wind_accel_z * current_mass

        # --- Torques and Rotational Motion --- (Simplified direct rate control)
        # Damping proportional to square of rotation rate for stability
        damping_factor_pitch = 0.8 + self.elevator_effectiveness * 0.5
        damping_factor_roll = 1.0 + self.aileron_effectiveness * 0.8 # Roll is usually more damped
        damping_factor_yaw = 0.5 + self.rudder_effectiveness * 0.3

        self.pitch_rate *= (1 - damping_factor_pitch * dt * abs(self.pitch_rate) * 0.1)
        self.roll_rate *= (1 - damping_factor_roll * dt * abs(self.roll_rate) * 0.1)
        self.yaw_rate *= (1 - damping_factor_yaw * dt * abs(self.yaw_rate) * 0.1)

        self.pitch += self.pitch_rate * dt
        self.roll += self.roll_rate * dt
        self.yaw = (self.yaw + self.yaw_rate * dt + 360) % 360

        self.pitch = np.clip(self.pitch, -90, 90)
        self.roll = ((self.roll + 180) % 360) - 180

        # --- Update Velocities and Positions ---
        ax = total_fx / current_mass
        ay = total_fy / current_mass
        az = total_fz / current_mass
        
        self.vx += (ax + wind_accel_x) * dt # Add wind accel here
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
        self.current_g_force = abs(g_vertical) # Simplified G

        if self.current_g_force > self.config.max_g_force and not self.on_ground:
            damage = (self.current_g_force - self.config.max_g_force) * 8 * dt
            self.structural_integrity = max(0, self.structural_integrity - damage)
            if self.structural_integrity <= 0 and not self.crashed:
                self.crashed = True; print("CRASH: Over-G")


    def update_autopilot(self, dt, current_speed_mps):
        if not self.autopilot_on or self.crashed: return

        # PID Controller constants (example values, need tuning)
        ap_p_alt, ap_i_alt, ap_d_alt = 0.02, 0.001, 0.05 # For altitude -> pitch rate
        ap_p_hdg, ap_i_hdg, ap_d_hdg = 0.4, 0.02, 0.1   # For heading -> roll rate
        ap_p_spd, ap_i_spd, ap_d_spd = 0.8, 0.05, 0.2   # For speed -> thrust input change

        # Shared integral and previous error terms (simplistic, per-axis needed for real PID)
        # This is a placeholder. A real AP needs separate PID states for each control loop.
        ap_integral_alt = getattr(self, 'ap_integral_alt', 0)
        ap_prev_alt_error = getattr(self, 'ap_prev_alt_error', 0)
        ap_integral_hdg = getattr(self, 'ap_integral_hdg', 0)
        ap_prev_hdg_error = getattr(self, 'ap_prev_hdg_error', 0)


        if self.ap_target_altitude is not None:
            alt_error = self.ap_target_altitude - self.y
            ap_integral_alt += alt_error * dt
            ap_integral_alt = np.clip(ap_integral_alt, -100, 100) # Anti-windup
            derivative_alt = (alt_error - ap_prev_alt_error) / dt if dt > 0 else 0
            
            # Target pitch rate based on PID output
            target_pitch_rate_cmd = (ap_p_alt * alt_error) + \
                                    (ap_i_alt * ap_integral_alt) + \
                                    (ap_d_alt * derivative_alt)
            target_pitch_rate_cmd = np.clip(target_pitch_rate_cmd, -self.config.turn_rate*0.3, self.config.turn_rate*0.3) # Limit commanded rate
            
            # Smoothly adjust aircraft's pitch rate towards commanded rate
            self.pitch_rate += (target_pitch_rate_cmd - self.pitch_rate) * 0.1 * dt * 20 # Smoothing factor
            self.ap_prev_alt_error = alt_error


        if self.ap_target_heading is not None:
            heading_error = (self.ap_target_heading - self.yaw + 540) % 360 - 180
            ap_integral_hdg += heading_error * dt
            ap_integral_hdg = np.clip(ap_integral_hdg, -180, 180)
            derivative_hdg = (heading_error - ap_prev_hdg_error) / dt if dt > 0 else 0

            # Target roll angle based on PID output for heading correction
            target_roll_cmd_deg = (ap_p_hdg * heading_error) + \
                                  (ap_i_hdg * ap_integral_hdg) + \
                                  (ap_d_hdg * derivative_hdg)
            target_roll_cmd_deg = np.clip(target_roll_cmd_deg, -25, 25) # Max 25 deg bank for AP

            # Smoothly adjust aircraft's roll towards commanded roll angle (via roll rate)
            roll_error_to_target = target_roll_cmd_deg - self.roll
            self.roll_rate += (roll_error_to_target * 0.5) * dt * 20 # Proportional control to roll rate
            self.ap_prev_hdg_error = heading_error


        if self.ap_target_speed is not None:
            speed_error = self.ap_target_speed - current_speed_mps
            # Simplified P controller for autothrottle
            thrust_adj = np.clip(speed_error * ap_p_spd, -20, 20) # Max thrust change % per update cycle
            self.thrust_input = np.clip(self.thrust_input + thrust_adj * dt, 0, 100)
        
        # Store PID states back to aircraft object if they were fetched with getattr
        self.ap_integral_alt = ap_integral_alt
        self.ap_integral_hdg = ap_integral_hdg

    def update(self, dt, weather: Weather, sound_manager: SoundManager):
        if self.crashed:
            self.vx *= (1 - 0.5 * dt) # Higher friction when crashed
            self.vz *= (1 - 0.5 * dt)
            self.vy =0
            self.pitch_rate = 0; self.roll_rate = 0; self.yaw_rate = 0;
            return

        self.flight_time_sec += dt
        old_x, old_z = self.x, self.z

        self.update_engine_rpm(dt)

        air_density = 1.225 * math.exp(-self.y / 8500) # ISA density approx
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
            # Consumption scales with RPM^1.5 (more realistic for jets/props)
            consumption_rate = self.config.fuel_consumption * (self.engine_rpm_percent / 100.0)**1.5 * \
                               (active_engines / self.config.engine_count if self.config.engine_count > 0 else 0)
            fuel_consumed = consumption_rate * dt
            self.fuel = max(0, self.fuel - fuel_consumed)
            if self.fuel == 0 and self.engine_on:
                print("Fuel Empty! Engine(s) shutting down."); self.engine_on = False

        terrain_height = 0 # Simplified for now
        if self.y <= terrain_height + 0.1 and not self.on_ground: # Touchdown logic
            self.on_ground = True
            self.y = terrain_height
            # self.vy = 0 # Simple stop; could add bounce/suspension later
            
            impact_g = abs(self.touchdown_vertical_speed_mps / 9.81)
            hs_kts = current_speed_mps * 1.94384
            print(f"Touchdown: VS={self.touchdown_vertical_speed_mps:.2f}m/s ({impact_g:.2f}G), HS={hs_kts:.1f}kts, Roll={self.roll:.1f}")

            max_safe_vs_mps = -3.0 # Approx -600 fpm
            max_safe_hs_mps = self.config.stall_speed_clean * 1.8 # Landing speed range

            if not self.gear_down or \
               self.touchdown_vertical_speed_mps < max_safe_vs_mps * 1.5 or \
               current_speed_mps > max_safe_hs_mps or \
               abs(self.roll) > 10 or abs(self.pitch) > 15:
                self.crashed = True
                self.structural_integrity = 0
                print("CRASH: Hard or improper landing.")
            else:
                self.landed_successfully = True
                self.vy = 0 # Absorb impact smoothly if successful
                score = 100
                score -= min(50, abs(self.touchdown_vertical_speed_mps - (-0.75)) * 25) # Ideal ~-0.75m/s
                score -= min(30, abs(current_speed_mps - self.config.stall_speed_clean * 1.2) * 2)
                score -= min(20, abs(self.roll) * 3)
                self.landing_score = max(0, int(score))
                print(f"Successful Landing! Score: {self.landing_score}")

        if self.on_ground:
            self.y = terrain_height
            # Ground friction
            self.vy = 0 # No vertical movement on ground unless taking off
            self.pitch_rate *= (1 - 0.8 * dt) # Dampen rotations heavily
            self.roll_rate *= (1 - 0.95 * dt) 

            friction_coeff_rolling = 0.02
            friction_coeff_braking = 0.6 if current_speed_mps > 5 else 0.3 # Brakes more effective at speed
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

        if current_speed_mps > self.config.max_speed * 0.98 and not self.overspeed_warning_active: # Closer to Vne
            self.overspeed_warning_active = True
            sound_manager.play_warning_beep(frequency=1200, duration=0.5)
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
        gear_operating_speed_mps = self.config.stall_speed_clean * 2.0 # Vlo/Vle approx
        if current_speed_mps > gear_operating_speed_mps and not self.gear_down: # Check only when retracting
            print(f"Cannot retract gear above {gear_operating_speed_mps*1.94384:.0f} kts!")
            sound_manager.play_warning_beep(frequency=1000, duration=0.3)
            return

        self.gear_down = not self.gear_down
        sound_manager.play_sound("gear_down" if self.gear_down else "gear_up")
        print(f"Gear: {'DOWN' if self.gear_down else 'UP'}")
    
    def get_nav_display_info(self):
        if self.nav_mode_active and self.waypoints and self.current_waypoint_index < len(self.waypoints):
            wp = self.waypoints[self.current_waypoint_index]
            # World +X East, +Z North. Aircraft yaw 0 = North.
            dx = wp.x - self.x
            dz_nav = wp.z - self.z # Target Z relative to current Z

            distance_m = math.sqrt(dx**2 + dz_nav**2)
            if distance_m < (250 if wp.waypoint_type == "AIRPORT" else 100): # Waypoint capture
                print(f"Reached Waypoint: {wp.name}")
                self.current_waypoint_index +=1
                if self.current_waypoint_index >= len(self.waypoints):
                    print("All waypoints reached.")
                    self.nav_mode_active = False
                    return None # No more waypoints
                else: # Get next waypoint immediately
                    wp = self.waypoints[self.current_waypoint_index]
                    dx = wp.x - self.x
                    dz_nav = wp.z - self.z
                    distance_m = math.sqrt(dx**2 + dz_nav**2)


            bearing_rad = math.atan2(dx, dz_nav)
            bearing_deg = (math.degrees(bearing_rad) + 360) % 360
            
            desired_track_deg = bearing_deg
            
            # Current ground track
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

class Camera:
    def __init__(self):
        self.x, self.y, self.z = 0, 100, -200
        self.target_x, self.target_y, self.target_z = 0,0,0
        
        self.fov_y_deg = 60
        self.aspect_ratio = WIDTH / HEIGHT
        self.near_clip, self.far_clip = 0.5, 30000.0 # Adjusted near clip

        self.distance = 25
        self.orbit_angle_h_deg = 0
        self.orbit_angle_v_deg = 15 # Slightly above
        
        self.mode = "follow_mouse_orbit"
        self.smooth_factor = 0.1 # Increased for responsiveness

        self.is_mouse_orbiting = False
        self.last_mouse_pos: Optional[Tuple[int,int]] = None

        self.cam_yaw_deg = 0 # For cockpit view, mirrors aircraft
        self.cam_pitch_deg = 0
        self.cam_roll_deg = 0


    def update(self, aircraft: Aircraft, dt):
        desired_cam_x, desired_cam_y, desired_cam_z = self.x, self.y, self.z

        if self.mode == "cockpit":
            offset_forward = 0.3 # Pilot's eye point relative to CG
            offset_up = aircraft.config.mass / 80000 * 1.2 # Eye height scaled roughly with aircraft size
            
            # Camera position is at aircraft CG + local offset
            # Rotate offset by aircraft attitude
            # Local offset vector: (0, offset_up, offset_forward) in aircraft body frame if Z is fwd, Y is up
            ac_p, ac_y, ac_r = math.radians(aircraft.pitch), math.radians(aircraft.yaw), math.radians(aircraft.roll)
            
            # Simplified: position near aircraft CG, view matrix handles orientation
            desired_cam_x = aircraft.x
            desired_cam_y = aircraft.y + offset_up # Simple vertical offset for eye height from CG
            desired_cam_z = aircraft.z

            # Camera orientation IS aircraft orientation
            self.cam_yaw_deg = aircraft.yaw
            self.cam_pitch_deg = aircraft.pitch
            self.cam_roll_deg = aircraft.roll # Needed for view matrix construction
           
            # Target point for lookAt calculation (far in front of camera/aircraft)
            look_dist = 1000
            # Forward vector of camera (same as aircraft)
            fwd_x = math.cos(ac_p) * math.sin(ac_y)
            fwd_y = math.sin(ac_p)
            fwd_z = math.cos(ac_p) * math.cos(ac_y)
            self.target_x = desired_cam_x + fwd_x * look_dist
            self.target_y = desired_cam_y + fwd_y * look_dist
            self.target_z = desired_cam_z + fwd_z * look_dist

        elif "follow" in self.mode or "external" in self.mode:
            self.cam_roll_deg = 0 # External cameras typically don't roll with target unless intended

            # Orbit around aircraft's current position
            # Note: orbit_angle_h_deg is relative to world North if not modified by aircraft.yaw
            # For a chase cam, it should be aircraft.yaw + manual_orbit_offset
            effective_orbit_h_deg = self.orbit_angle_h_deg + aircraft.yaw # Makes orbit relative to aircraft tail
            
            orbit_h_rad = math.radians(effective_orbit_h_deg)
            orbit_v_rad = math.radians(self.orbit_angle_v_deg)

            offset_x_world = self.distance * math.cos(orbit_v_rad) * math.sin(orbit_h_rad)
            offset_y_world = self.distance * math.sin(orbit_v_rad)
            offset_z_world = self.distance * math.cos(orbit_v_rad) * math.cos(orbit_h_rad)
            
            desired_cam_x = aircraft.x - offset_x_world # Place camera behind based on offset
            desired_cam_y = aircraft.y + offset_y_world
            desired_cam_z = aircraft.z - offset_z_world

            self.target_x = aircraft.x # Always look at the aircraft
            self.target_y = aircraft.y
            self.target_z = aircraft.z

        # Smooth interpolation
        self.x += (desired_cam_x - self.x) * self.smooth_factor * (dt*FPS if dt > 0 else 1) # Scale with dt
        self.y += (desired_cam_y - self.y) * self.smooth_factor * (dt*FPS if dt > 0 else 1)
        self.z += (desired_cam_z - self.z) * self.smooth_factor * (dt*FPS if dt > 0 else 1)


    def handle_mouse_input(self, event, aircraft: Aircraft):
        if "mouse_orbit" not in self.mode:
            self.is_mouse_orbiting = False
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3: # Right mouse button
                self.is_mouse_orbiting = True
                self.last_mouse_pos = event.pos
                pygame.mouse.set_visible(False) # Hide cursor while orbiting
                pygame.event.set_grab(True)     # Confine cursor to window
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
                
                self.orbit_angle_h_deg -= dx * 0.3  # Sensitivity
                self.orbit_angle_v_deg = np.clip(self.orbit_angle_v_deg - dy * 0.3, -85, 85) # Limit vertical orbit
                # For grabbed mouse, use relative motion if available, or reset last_mouse_pos to center
                # pygame.mouse.set_pos((WIDTH//2, HEIGHT//2)) # If you want to keep mouse centered
                # self.last_mouse_pos = (WIDTH//2, HEIGHT//2)
                self.last_mouse_pos = event.pos # Standard update if not resetting
        
        if event.type == pygame.MOUSEWHEEL:
            scroll_speed = self.distance * 0.1 # Zoom proportional to current distance
            self.distance = np.clip(self.distance - event.y * scroll_speed, 3, 300)

# Corrected Terrain Class
class Terrain:
    def __init__(self):
        self.height_map: Dict[Tuple[int, int], float] = {}
        self.airports: List[Dict] = []
        self.trees: List[Dict] = []

        self.generate_terrain()
        self.generate_airports() # This will populate self.airports
        self.generate_trees()    # This uses self.airports to avoid placing trees on them

    def generate_terrain(self):
        print("Generating terrain...")
        # Coarse grid for basic height variation
        for x_coord in range(-15000, 15001, 1000): # Wider range, coarser step
            for z_coord in range(-15000, 15001, 1000):
                height = 0
                # Multiple sine waves for Perlin-like noise
                height += 150 * math.sin(x_coord * 0.00005 + 1) * math.cos(z_coord * 0.00005 + 1)
                height += 80 * math.sin(x_coord * 0.00015 + 2) * math.cos(z_coord * 0.00015 + 2)
                height += 40 * math.sin(x_coord * 0.00055 + 3) * math.cos(z_coord * 0.00055 + 3)
                # Introduce some randomness to break uniformity
                height += random.uniform(-20, 20)
                self.height_map[(x_coord // 500, z_coord // 500)] = max(0, height) # Store with coarser key for get_height_at
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
            # Flatten terrain around airport
            for dx in range(-2, 3): # Grid units around airport center
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
        # Bilinear interpolation for smoother terrain height (optional, simple for now)
        key_x, key_z = int(round(x / 500)), int(round(z / 500))
        return self.height_map.get((key_x, key_z), 0) # Default to 0 (sea level)

    def generate_trees(self, count=150): # Reduced count for performance
        self.trees = []
        print(f"Generating {count} trees...")
        for _ in range(count):
            tree_x = random.uniform(-15000, 15000)
            tree_z = random.uniform(-15000, 15000)
            
            on_airport_area = False
            for airport in self.airports:
                # Wider exclusion zone for airports
                dist_sq_to_airport = (tree_x - airport['x'])**2 + (tree_z - airport['z'])**2
                if dist_sq_to_airport < (airport['runway_length'] * 1.5)**2: # Exclude if within ~1.5x runway length radius
                    on_airport_area = True
                    break
            
            if not on_airport_area:
                 base_h = self.get_height_at(tree_x, tree_z)
                 if base_h < 0.1 and random.random() < 0.7: continue # Fewer trees at sea level / water

                 tree_h_val = random.uniform(8, 25) # Taller trees possible
                 self.trees.append({
                     'x': tree_x, 'y': base_h + tree_h_val / 2,
                     'z': tree_z, 'height': tree_h_val,
                     'radius': random.uniform(3, 8) # Wider trees
                 })
        print(f"Finished generating trees: {len(self.trees)} placed.")


# --- Button Class for UI ---
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
                self.sound_manager.play_sound('click')
                if self.callback:
                    self.callback()
                    return True
        return False

    def draw(self, surface):
        current_color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(surface, current_color, self.rect, border_radius=5)
        pygame.draw.rect(surface, tuple(np.clip(c*0.7,0,255) for c in current_color), self.rect, 2, border_radius=5) # Darker border
        
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font_small = pygame.font.Font(None, 22) # Slightly larger small font
        self.font_medium = pygame.font.Font(None, 30)
        self.font_large = pygame.font.Font(None, 52)
        self.font_hud = pygame.font.SysFont("Consolas", 20) # Adjusted HUD font size
        self.font_hud_large = pygame.font.SysFont("Consolas", 26)

        self.cockpit_overlay_img = None
        try:
            # Ensure image uses alpha for transparency
            self.cockpit_overlay_img = pygame.image.load("cockpit_overlay.png").convert_alpha()
            self.cockpit_overlay_img = pygame.transform.scale(self.cockpit_overlay_img, (WIDTH, HEIGHT))
        except pygame.error:
            print("Warning: cockpit_overlay.png not found or error loading. Using basic frame.")

    def project_point_3d_to_2d(self, x, y, z, camera: Camera) -> Optional[Tuple[int, int, float]]:
        # Simplified perspective projection
        # Assumes camera is at (cam_x, cam_y, cam_z) and looks towards (target_x, target_y, target_z)
        # Or, for cockpit view, uses camera's own yaw, pitch, roll.

        # Step 1: Transform point from World Space to Camera View Space
        # Vector from camera eye to point P in world space
        p_world = np.array([x, y, z, 1.0])
        
        # Construct View Matrix (LookAt)
        eye = np.array([camera.x, camera.y, camera.z])
        if camera.mode == "cockpit":
            # For cockpit, target is determined by camera's (aircraft's) orientation
            cam_p_rad = math.radians(camera.cam_pitch_deg)
            cam_y_rad = math.radians(camera.cam_yaw_deg)
            # Forward vector based on camera's pitch and yaw
            fwd_x = math.cos(cam_p_rad) * math.sin(cam_y_rad)
            fwd_y = math.sin(cam_p_rad)
            fwd_z = math.cos(cam_p_rad) * math.cos(cam_y_rad)
            target_pt = eye + np.array([fwd_x, fwd_y, fwd_z]) * 100 # Look 100 units ahead
        else: # External cameras look at aircraft CG
            target_pt = np.array([camera.target_x, camera.target_y, camera.target_z])

        world_up = np.array([0, 1, 0]) # Assuming Y is up in world space

        f = target_pt - eye
        norm_f = np.linalg.norm(f)
        if norm_f < 1e-6: return None
        f = f / norm_f

        s = np.cross(f, world_up) # Right vector
        norm_s = np.linalg.norm(s)
        if norm_s < 1e-6: # f is collinear with world_up, use a different temp_up for s
            s = np.cross(f, np.array([0,0,1])) # Try Z-axis for temp_up
            norm_s = np.linalg.norm(s)
            if norm_s < 1e-6: return None # Still problematic
        s = s / norm_s
        
        u = np.cross(s, f) # True Up vector for camera

        # If in cockpit mode, apply camera's (aircraft's) roll to the 'u' and 's' vectors
        if camera.mode == "cockpit":
            cam_r_rad = math.radians(camera.cam_roll_deg)
            # Rotate s and u around f by -cam_r_rad (Rodrigues' rotation formula or quaternion)
            # Simplified: this part is complex to do correctly without full matrix lib.
            # Pygame's 2D rotation can't be directly used here.
            # For now, cockpit roll is mostly handled by ADI visuals.
            pass


        # View Matrix (M_view = T_inv * R_inv)
        # R_inv has rows s, u, -f. T_inv translates by -eye.
        # P_camera = R_inv * (P_world - eye)
        p_rel_to_eye = np.array([x - eye[0], y - eye[1], z - eye[2]])
        
        x_cam = np.dot(p_rel_to_eye, s)
        y_cam = np.dot(p_rel_to_eye, u)
        z_cam = -np.dot(p_rel_to_eye, f) # Depth along negative forward axis (OpenGL convention)
                                        # Or +f if Z is into screen in camera space

        if not (camera.near_clip < z_cam < camera.far_clip):
            return None

        # Step 2: Projection Matrix (Perspective)
        # tan(fov_y_rad / 2) = (H/2) / d_proj_z  => d_proj_z = (H/2) / tan(fov_y_rad/2)
        # x_proj = x_cam * (d_proj_z / z_cam)
        # y_proj = y_cam * (d_proj_z / z_cam)
        # Aspect ratio: fov_x = 2 * atan(tan(fov_y/2) * aspect)
        
        # Using a common projection formula:
        # screen_x = x_cam / (z_cam * tan(fov_x/2))
        # screen_y = y_cam / (z_cam * tan(fov_y/2))
        # This gives normalized device coordinates (NDC) in range like [-1, 1]

        # Focal length for y f_y = 1 / tan(fov_y / 2)
        # Focal length for x f_x = 1 / tan(fov_x / 2) = 1 / (tan(fov_y / 2) * aspect_ratio)
        
        tan_half_fovy = math.tan(math.radians(camera.fov_y_deg) / 2.0)
        
        # Projected x, y in a normalized space (e.g. -1 to 1 if fov correctly handled)
        # Ensure z_cam is not zero
        if abs(z_cam) < 1e-6: return None
        
        sx_ndc = (x_cam / (camera.aspect_ratio * tan_half_fovy * z_cam))
        sy_ndc = (y_cam / (tan_half_fovy * z_cam))

        # Convert NDC [-1, 1] to screen [0, W] and [0, H]
        screen_x = int((sx_ndc + 1.0) / 2.0 * WIDTH)
        screen_y = int((1.0 - sy_ndc) / 2.0 * HEIGHT) # Y is inverted

        return screen_x, screen_y, z_cam


    def draw_horizon_and_sky(self, aircraft: Aircraft, camera: Camera):
        # Fill with a base sky color
        self.screen.fill(DARK_BLUE) # Deep sky
        # Gradient for lower sky
        gradient_rect = pygame.Rect(0, int(HEIGHT * 0.2), WIDTH, int(HEIGHT*0.8))
        # pygame.draw.rect(self.screen, BLUE, gradient_rect) # Lighter blue lower

        # Ground plane (very simplified)
        # Project 4 far points of a ground quad and draw it
        # For now, a simple green rectangle if camera is above ground
        # A true 3D horizon is complex; it's where sky and ground plane meet at infinity.
        
        # If camera is looking down significantly, more ground is visible.
        # This is best handled by projecting a large ground quad.
        # Quick hack for now:
        ground_y_screen = HEIGHT * 0.6 # Default horizon position on screen
        
        # If in cockpit, adjust "horizon" based on pitch
        if camera.mode == "cockpit":
            # Pitch affects where the center of the screen horizon lies
            # pixels_per_degree = (HEIGHT/2) / 45 # e.g. 45deg pitch fills half screen
            # ground_y_screen += aircraft.pitch * pixels_per_degree
            # ground_y_screen = np.clip(ground_y_screen, 0, HEIGHT)
            # This is better handled by ADI. Main view should show true perspective.
            # So, for main view, we always try to render a 3D ground.
            pass

        # Render a large ground quad
        ground_quad_world = [ # Large square on Y=0 plane
            (-camera.far_clip, 0, -camera.far_clip),
            ( camera.far_clip, 0, -camera.far_clip),
            ( camera.far_clip, 0,  camera.far_clip),
            (-camera.far_clip, 0,  camera.far_clip),
        ]
        ground_quad_screen = []
        visible_ground_points = 0
        for p_world in ground_quad_world:
            p_screen_info = self.project_point_3d_to_2d(p_world[0], p_world[1], p_world[2], camera)
            if p_screen_info:
                ground_quad_screen.append((p_screen_info[0], p_screen_info[1]))
                visible_ground_points+=1
        
        if visible_ground_points >=3 : # Need at least 3 points for a polygon
            try:
                pygame.draw.polygon(self.screen, DARK_GREEN, ground_quad_screen)
            except ValueError: # If points are collinear or not enough for polygon
                pass # Could happen if camera view is very specific
        else: # Fallback if ground quad isn't projecting well (e.g., looking straight up)
             pygame.draw.rect(self.screen, DARK_GREEN, (0, ground_y_screen, WIDTH, HEIGHT - ground_y_screen))


    def rotate_point_3d(self, p, pitch_rad, yaw_rad, roll_rad, order='YXZ'):
        # Standard rotation order: Yaw (Y), Pitch (X), Roll (Z) is common for aircraft intrinsic
        # Or fixed axes: Roll (Z world), Pitch (X world), Yaw (Y world)
        # For local model vertices, usually intrinsic: ZXY or YXZ or XYZ
        # Let's use YXZ: Yaw around original Y, then Pitch around new X, then Roll around new Z

        px, py, pz = p[0], p[1], p[2]

        # Yaw around Y axis
        x1 = px * math.cos(yaw_rad) + pz * math.sin(yaw_rad)
        z1 = -px * math.sin(yaw_rad) + pz * math.cos(yaw_rad)
        px, pz = x1, z1
        
        # Pitch around X axis (new X after yaw)
        y1 = py * math.cos(pitch_rad) - pz * math.sin(pitch_rad)
        z1 = py * math.sin(pitch_rad) + pz * math.cos(pitch_rad)
        py, pz = y1, z1
        
        # Roll around Z axis (new Z after yaw and pitch)
        x2 = px * math.cos(roll_rad) - py * math.sin(roll_rad)
        y2 = px * math.sin(roll_rad) + py * math.cos(roll_rad)
        px, py = x2, y2
        
        return (px, py, pz)

    def draw_aircraft_model(self, aircraft: Aircraft, camera: Camera):
        if camera.mode == "cockpit" and not aircraft.crashed :
             return

        pitch_rad = math.radians(aircraft.pitch)
        yaw_rad = math.radians(aircraft.yaw)
        roll_rad = math.radians(aircraft.roll)

        world_vertices = []
        for v_local in aircraft.model_vertices_local:
            # Rotate (YXZ order: Yaw, then Pitch, then Roll)
            v_rotated_yaw = (v_local[0]*math.cos(yaw_rad) + v_local[2]*math.sin(yaw_rad),
                             v_local[1],
                             -v_local[0]*math.sin(yaw_rad) + v_local[2]*math.cos(yaw_rad))
            
            v_rotated_pitch_yaw = (v_rotated_yaw[0],
                                   v_rotated_yaw[1]*math.cos(pitch_rad) - v_rotated_yaw[2]*math.sin(pitch_rad),
                                   v_rotated_yaw[1]*math.sin(pitch_rad) + v_rotated_yaw[2]*math.cos(pitch_rad))

            v_rotated_final = (v_rotated_pitch_yaw[0]*math.cos(roll_rad) - v_rotated_pitch_yaw[1]*math.sin(roll_rad),
                               v_rotated_pitch_yaw[0]*math.sin(roll_rad) + v_rotated_pitch_yaw[1]*math.cos(roll_rad),
                               v_rotated_pitch_yaw[2])
            
            v_world = (v_rotated_final[0] + aircraft.x, 
                       v_rotated_final[1] + aircraft.y, 
                       v_rotated_final[2] + aircraft.z)
            world_vertices.append(v_world)

        screen_points_with_depth = []
        for wx, wy, wz_world in world_vertices: # Renamed wz to wz_world
            pt_info = self.project_point_3d_to_2d(wx, wy, wz_world, camera)
            screen_points_with_depth.append(pt_info)

        # Basic back-face culling or line sorting by depth can be added here.
        # For lines, just draw if both points are visible.
        for line_indices in aircraft.model_lines:
            p1_info = screen_points_with_depth[line_indices[0]]
            p2_info = screen_points_with_depth[line_indices[1]]

            if p1_info and p2_info:
                avg_depth = (p1_info[2] + p2_info[2]) / 2.0
                intensity = np.clip(1.0 - (avg_depth / (camera.far_clip*0.6)), 0.15, 1.0) # Fog/distance fade
                
                aircraft_base_color = SILVER if aircraft.type == AircraftType.AIRLINER else \
                                      RED if aircraft.type == AircraftType.FIGHTER else \
                                      YELLOW if aircraft.type == AircraftType.GLIDER else WHITE
                
                final_color = tuple(int(c * intensity) for c in aircraft_base_color)

                pygame.draw.line(self.screen, final_color, (p1_info[0], p1_info[1]), (p2_info[0], p2_info[1]), 2) # Thicker lines

        if not aircraft.engine_on or any(h < 30 for h in aircraft.engine_health) or aircraft.crashed:
            cg_proj_info = self.project_point_3d_to_2d(aircraft.x, aircraft.y, aircraft.z, camera)
            if cg_proj_info:
                sx, sy, _ = cg_proj_info
                for i in range(8): # More smoke particles
                    # Smoke appears behind based on world velocity projected
                    # This is a simplified effect
                    offset_x = -aircraft.vx * 0.1 * i + random.uniform(-3,3)
                    offset_y = -aircraft.vy * 0.1 * i + random.uniform(-3,3) # Smoke rises/falls slightly
                    # Screen position of smoke particles, relative to aircraft's screen center
                    smoke_screen_x = sx + int(offset_x)
                    smoke_screen_y = sy + int(offset_y) + i*3 # Drift down/back
                    pygame.draw.circle(self.screen, tuple(int(c*0.8) for c in DARK_GRAY), 
                                       (smoke_screen_x, smoke_screen_y), 
                                       max(1, 5 - i//2))


    def draw_terrain_features(self, camera: Camera, terrain: Terrain, weather: Weather):
        for airport in terrain.airports:
            ap_x, ap_y, ap_z = airport['x'], airport['elevation'], airport['z']
            dist_sq_to_ap = (ap_x-camera.x)**2 + (ap_y-camera.y)**2 + (ap_z-camera.z)**2
            if dist_sq_to_ap > (camera.far_clip * 0.8)**2: continue # Cull far airports

            length, width = airport['runway_length'], airport['runway_width']
            hdg_rad = math.radians(airport['runway_heading'])
            hl, hw = length / 2, width / 2
            
            # Runway corners in local frame (Z along runway, X across)
            corners_local_rwy = [(-hw, 0, hl), (hw, 0, hl), (hw, 0, -hl), (-hw, 0, -hl)]
            runway_corners_world = []
            for clx, cly, clz in corners_local_rwy:
                rot_x = clx * math.cos(hdg_rad) - clz * math.sin(hdg_rad) # Mistake here, usually Z is fwd
                rot_z = clx * math.sin(hdg_rad) + clz * math.cos(hdg_rad) # This rotates points in XZ plane
                runway_corners_world.append( (ap_x + rot_x, ap_y + cly, ap_z + rot_z) ) # cly is 0

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
                rwy_color = tuple(int(c * intensity) for c in DARK_GRAY) # Darker runways
                pygame.draw.polygon(self.screen, rwy_color, screen_corners)
                
                if min_depth < 8000: # Show name if relatively close
                    center_proj = self.project_point_3d_to_2d(ap_x, ap_y, ap_z, camera)
                    if center_proj:
                        name_surf = self.font_small.render(airport['name'], True, WHITE)
                        self.screen.blit(name_surf, (center_proj[0] - name_surf.get_width()//2, center_proj[1] - 25))
        
        # Draw Trees (limit number drawn for performance)
        # Sort by distance (optional, can be slow) or just draw a subset
        # trees_to_draw = sorted(terrain.trees, key=lambda t: (t['x']-camera.x)**2 + (t['y']-camera.y)**2 + (t['z']-camera.z)**2, reverse=True)
        # trees_to_draw = trees_to_draw[:50] # Draw closest 50 after sorting
        
        # Simplified: draw based on proximity, no sorting needed if drawing all (up to a limit)
        drawn_trees = 0
        for tree in terrain.trees:
            if drawn_trees > 75: break # Hard limit on trees drawn per frame
            dist_sq_to_tree = (tree['x']-camera.x)**2 + (tree['z']-camera.z)**2 # 2D distance for culling
            if dist_sq_to_tree > (camera.far_clip * 0.4)**2 : continue # Cull far trees

            bottom_proj = self.project_point_3d_to_2d(tree['x'], tree['y'] - tree['height']/2, tree['z'], camera)
            top_proj = self.project_point_3d_to_2d(tree['x'], tree['y'] + tree['height']/2, tree['z'], camera)

            if bottom_proj and top_proj:
                bx, by, bz = bottom_proj; tx, ty, tz = top_proj
                if bz < camera.near_clip or tz < camera.near_clip: continue # Clipped by near plane

                # Screen radius based on tree's world radius and distance
                # Approx: screen_radius = (world_radius / depth) * focal_length_pixels
                # Simplified: scale with depth
                screen_radius_trunk = max(1, int( (tree['radius']*0.3 * 500) / bz if bz > 1 else 5 ))
                screen_radius_leaves = max(2, int( (tree['radius'] * 600) / bz if bz > 1 else 8 ))


                intensity = np.clip(1.0 - (bz / (camera.far_clip * 0.5)), 0.2, 1.0)
                trunk_clr = tuple(int(c * intensity) for c in (101, 67, 33)) # Darker Brown
                leaves_clr = tuple(int(c * intensity) for c in (34, 80, 34)) # Darker Green

                pygame.draw.line(self.screen, trunk_clr, (bx, by), (tx, ty), screen_radius_trunk)
                pygame.draw.circle(self.screen, leaves_clr, (tx, ty), screen_radius_leaves)
                drawn_trees +=1


    def draw_weather_effects(self, weather: Weather, camera: Camera, aircraft: Aircraft):
        particle_count, particle_color, particle_prop = 0, WHITE, {}

        if weather.type == WeatherType.RAIN or weather.type == WeatherType.STORM:
            particle_count = int(weather.precipitation * 60) # More rain drops
            particle_color = (100, 100, 220) # Bluish rain
            particle_prop = {'type': 'line', 'length': 18, 'thickness': 1}
        elif weather.type == WeatherType.SNOW:
            particle_count = int(weather.precipitation * 50)
            particle_color = (230, 230, 255) # Off-white snow
            particle_prop = {'type': 'circle', 'radius': 3}

        if particle_count > 0:
            for _ in range(particle_count):
                # Spawn particles in a cube around the camera
                rel_x = random.uniform(-80, 80) # Wider particle spawn area
                rel_y = random.uniform(-40, 40) 
                rel_z_cam_space = random.uniform(camera.near_clip + 1, 100) # Depth in camera space

                # Transform particle from camera space to world space (approx)
                # This is for visual effect, not true particle simulation in world
                # Simpler: place particles relative to aircraft if cockpit, or camera if external
                origin_x, origin_y, origin_z = camera.x, camera.y, camera.z
                if camera.mode == "cockpit": # Particles relative to moving aircraft
                    origin_x, origin_y, origin_z = aircraft.x, aircraft.y, aircraft.z

                # Simplified: just project from a point in front of camera
                # For now, assume particles are just screen-space effects near camera view plane
                # This needs a proper particle system in 3D that moves with world/camera
                
                # Visual particles within a view frustum slice
                p_world_x = origin_x + rel_x # Simplistic attachment to origin
                p_world_y = origin_y + rel_y 
                p_world_z = origin_z + rel_z_cam_space # If rel_z is depth from origin

                pt_info = self.project_point_3d_to_2d(p_world_x, p_world_y, p_world_z, camera)

                if pt_info:
                    sx, sy, depth = pt_info
                    if not (0 <= sx < WIDTH and 0 <= sy < HEIGHT): continue
                    
                    intensity = np.clip(1.0 - (depth / 200.0), 0.2, 1.0) # Fade quickly
                    final_color_vals = tuple(int(c * intensity) for c in particle_color)

                    if particle_prop['type'] == 'circle':
                        size = int(np.clip(particle_prop['radius'] * 80 / depth if depth > 1 else particle_prop['radius'], 1, 6) * intensity)
                        pygame.draw.circle(self.screen, final_color_vals, (sx, sy), size)
                    elif particle_prop['type'] == 'line':
                        length = int(np.clip(particle_prop['length'] * 80 / depth if depth > 1 else particle_prop['length'], 2, 25) * intensity)
                        # Rain streaks angled by aircraft speed (visual effect)
                        angle_offset_x = -aircraft.vx * 0.05 * length
                        angle_offset_y = -aircraft.vy * 0.05 * length + length # Base downward motion
                        pygame.draw.line(self.screen, final_color_vals, (sx, sy), 
                                         (sx + int(angle_offset_x), sy + int(angle_offset_y)), 
                                         particle_prop['thickness'])
        
        if weather.type == WeatherType.FOG and weather.visibility < 2000: # More gradual fog
            alpha = np.clip( (2000 - weather.visibility) / 2000 * 220, 0, 220)
            fog_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fog_surf.fill((LIGHT_GRAY[0], LIGHT_GRAY[1], LIGHT_GRAY[2], int(alpha)))
            self.screen.blit(fog_surf, (0,0))

        # Clouds (Billboard rendering) - sort by depth for correct alpha blending
        # This is expensive. Limit count.
        sorted_clouds = sorted(
            weather.cloud_particles, 
            key=lambda p: (p['x']-camera.x)**2 + (p['y']-camera.y)**2 + (p['z']-camera.z)**2, 
            reverse=True # Furthest first, so closest are drawn on top
        )

        drawn_clouds = 0
        for cloud_particle in sorted_clouds:
            if drawn_clouds > 25: break # Limit clouds drawn
            
            pt_info = self.project_point_3d_to_2d(cloud_particle['x'], cloud_particle['y'], cloud_particle['z'], camera)
            if pt_info:
                sx, sy, depth = pt_info
                if depth < camera.near_clip + 10 or depth > camera.far_clip * 0.9: continue # Cull very near/far clouds

                screen_size_w = int(np.clip( (cloud_particle['size'] * 150) / depth if depth > 1 else 0, 10, 400 )) # Width
                screen_size_h = int(screen_size_w * 0.5) # Flatter clouds
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
                    flash_surf.fill((255,255,230, int(flash_intensity * 120))) # Brighter, shorter alpha
                    self.screen.blit(flash_surf, (0,0))


    def draw_attitude_indicator(self, aircraft: Aircraft, x, y, size):
        center_x, center_y = x + size // 2, y + size // 2
        radius = size // 2 - 8 # Smaller radius for thicker casing

        # Casing
        pygame.draw.circle(self.screen, (30,30,30), (center_x, center_y), radius + 8)
        pygame.draw.circle(self.screen, (80,80,80), (center_x, center_y), radius + 6, 2)
        
        clip_rect = pygame.Rect(center_x - radius, center_y - radius, 2 * radius, 2 * radius)
        original_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)

        pixels_per_degree_pitch = radius / 30 # Show +-30 degrees pitch effectively in display

        adi_surface = pygame.Surface((size*2, size*2), pygame.SRCALPHA) # Larger surface for rotation
        adi_surf_center_x, adi_surf_center_y = size, size
        
        # Sky (blue)
        pygame.draw.rect(adi_surface, (70, 130, 180), (0, 0, size*2, adi_surf_center_y - aircraft.pitch * pixels_per_degree_pitch))
        # Ground (brown)
        pygame.draw.rect(adi_surface, (139, 90, 43), (0, adi_surf_center_y - aircraft.pitch * pixels_per_degree_pitch, size*2, size*2))
        
        # Pitch ladder
        for p_deg in range(-60, 61, 10):
            line_screen_y = adi_surf_center_y - (p_deg - aircraft.pitch) * pixels_per_degree_pitch
            if abs(p_deg - aircraft.pitch) > 45 : continue # Cull lines too far off screen

            line_width_adi = radius * (0.4 if p_deg == 0 else (0.25 if p_deg % 30 == 0 else 0.15))
            line_thickness = 3 if p_deg == 0 else 1
            pygame.draw.line(adi_surface, WHITE, 
                             (adi_surf_center_x - line_width_adi, line_screen_y), 
                             (adi_surf_center_x + line_width_adi, line_screen_y), line_thickness)
            if p_deg != 0 and (p_deg % 20 == 0 or p_deg==10 or p_deg==-10):
                num_text = self.font_small.render(str(abs(p_deg)), True, WHITE)
                adi_surface.blit(num_text, (adi_surf_center_x - line_width_adi - 20, line_screen_y - num_text.get_height()//2))
                adi_surface.blit(num_text, (adi_surf_center_x + line_width_adi + 5, line_screen_y - num_text.get_height()//2))

        rotated_adi_surf = pygame.transform.rotate(adi_surface, aircraft.roll)
        self.screen.blit(rotated_adi_surf, rotated_adi_surf.get_rect(center=(center_x, center_y)))
        self.screen.set_clip(original_clip)

        # Fixed aircraft symbol
        pygame.draw.line(self.screen, YELLOW, (center_x - radius*0.4, center_y), (center_x - radius*0.1, center_y), 3)
        pygame.draw.line(self.screen, YELLOW, (center_x + radius*0.1, center_y), (center_x + radius*0.4, center_y), 3)
        pygame.draw.line(self.screen, YELLOW, (center_x - radius*0.1, center_y), (center_x, center_y - 5), 3)
        pygame.draw.line(self.screen, YELLOW, (center_x + radius*0.1, center_y), (center_x, center_y - 5), 3)
        pygame.draw.circle(self.screen, YELLOW, (center_x, center_y), 3)

        # Roll scale and pointer
        # pygame.draw.arc(self.screen, WHITE, ... ) # Arc for scale
        for angle_deg in range(-60, 61, 10): # Ticks for roll
            if angle_deg == 0: continue
            rad = math.radians(angle_deg - 90 + aircraft.roll) # Rotate ticks with roll
            start_x = center_x + (radius - (8 if angle_deg % 30 == 0 else 4)) * math.cos(rad)
            start_y = center_y + (radius - (8 if angle_deg % 30 == 0 else 4)) * math.sin(rad)
            end_x = center_x + radius * math.cos(rad)
            end_y = center_y + radius * math.sin(rad)
            pygame.draw.line(self.screen, WHITE, (start_x, start_y), (end_x, end_y), 1)
        # Fixed pointer at top for roll
        pygame.draw.polygon(self.screen, YELLOW, [(center_x, center_y - radius + 8), (center_x-5, center_y-radius-2), (center_x+5, center_y-radius-2)])


    def draw_horizontal_situation_indicator(self, aircraft: Aircraft, nav_info, x, y, size):
        center_x, center_y = x + size // 2, y + size // 2
        radius = size // 2 - 8

        pygame.draw.circle(self.screen, (30,30,30), (center_x, center_y), radius + 8)
        pygame.draw.circle(self.screen, (80,80,80), (center_x, center_y), radius + 6, 2)
        pygame.draw.circle(self.screen, BLACK, (center_x, center_y), radius)

        for angle_deg_abs in range(0, 360, 10): # Absolute compass degrees
            # Angle of this tick mark on the screen, relative to aircraft's current heading (top = current heading)
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

            if is_major_tick : # Labels for N, E, S, W or numbers
                text_angle_rad = angle_on_screen_rad # Use same angle for text positioning
                if is_cardinal:
                    label = "N" if angle_deg_abs == 0 else "E" if angle_deg_abs == 90 else \
                            "S" if angle_deg_abs == 180 else "W"
                else: # Numeric labels for 30, 60, 120 etc.
                    label = str(angle_deg_abs // 10) # Show 3 for 30, 12 for 120
                
                text_surf = self.font_small.render(label, True, tick_color)
                text_dist = radius - tick_len - (12 if is_cardinal else 10)
                text_x = center_x + text_dist * math.cos(text_angle_rad) - text_surf.get_width()//2
                text_y = center_y + text_dist * math.sin(text_angle_rad) - text_surf.get_height()//2
                self.screen.blit(text_surf, (text_x, text_y))

        # Aircraft symbol (fixed, pointing up)
        pygame.draw.polygon(self.screen, YELLOW, [ (center_x, center_y - 7), (center_x - 5, center_y + 5), (center_x + 5, center_y + 5)])
        # Lubber line (current heading indicator)
        pygame.draw.line(self.screen, YELLOW, (center_x, center_y - radius), (center_x, center_y - radius + 15), 3)

        if aircraft.autopilot_on and aircraft.ap_target_heading is not None:
            hdg_bug_screen_rad = math.radians((aircraft.ap_target_heading - aircraft.yaw - 90 + 360)%360)
            bug_x = center_x + radius * 0.9 * math.cos(hdg_bug_screen_rad) # Slightly inside rose
            bug_y = center_y + radius * 0.9 * math.sin(hdg_bug_screen_rad)
            # Simple magenta diamond for heading bug
            pygame.draw.polygon(self.screen, CYAN, [(bug_x, bug_y - 6), (bug_x + 6, bug_y), (bug_x, bug_y + 6), (bug_x - 6, bug_y)])
        
        if nav_info:
            # Course select pointer (desired track)
            dtk_screen_rad = math.radians((nav_info['desired_track_deg'] - aircraft.yaw - 90 + 360)%360)
            crs_x1 = center_x + (radius*0.85) * math.cos(dtk_screen_rad)
            crs_y1 = center_y + (radius*0.85) * math.sin(dtk_screen_rad)
            crs_x2 = center_x + (radius*1.0) * math.cos(dtk_screen_rad) # Arrowhead points to edge
            crs_y2 = center_y + (radius*1.0) * math.sin(dtk_screen_rad)
            pygame.draw.line(self.screen, PURPLE, (crs_x1, crs_y1), (crs_x2, crs_y2), 3)
            # Arrowhead for course pointer
            # pygame.draw.polygon(self.screen, PURPLE, ... arrowhead points ...)

            # CDI needle (shows deviation from desired_track_deg)
            # Max deviation shown on HSI (e.g., 10 degrees = full scale deflection)
            max_dev_hsi_deg = 10.0 
            dev_scaled = np.clip(nav_info['track_error_deg'] / max_dev_hsi_deg, -1.0, 1.0)
            
            # Needle moves left/right relative to the HSI center, along an axis perpendicular to desired track line
            # For simplicity, CDI bar is horizontal on screen, moves based on dev_scaled if course is near top/bottom
            # True CDI bar rotates with course and moves laterally.
            # Simplified: Fixed horizontal bar in center, moves left/right.
            # needle_center_offset_x = dev_scaled * (radius * 0.5) # Deviation from center
            # This offset should be perpendicular to the selected course line
            cdi_bar_half_len = radius * 0.6
            cdi_bar_offset_pixels = dev_scaled * (radius * 0.4) # How far the bar is shifted from center

            # Calculate points for CDI bar, rotated by desired track on screen
            # Center of CDI bar, offset from HSI center
            cdi_center_x = center_x + cdi_bar_offset_pixels * math.cos(dtk_screen_rad + math.pi/2) # Perpendicular shift
            cdi_center_y = center_y + cdi_bar_offset_pixels * math.sin(dtk_screen_rad + math.pi/2)
            
            # Endpoints of CDI bar (parallel to desired track line)
            cdi_p1_x = cdi_center_x - cdi_bar_half_len * math.cos(dtk_screen_rad)
            cdi_p1_y = cdi_center_y - cdi_bar_half_len * math.sin(dtk_screen_rad)
            cdi_p2_x = cdi_center_x + cdi_bar_half_len * math.cos(dtk_screen_rad)
            cdi_p2_y = cdi_center_y + cdi_bar_half_len * math.sin(dtk_screen_rad)
            pygame.draw.line(self.screen, PURPLE, (cdi_p1_x, cdi_p1_y), (cdi_p2_x, cdi_p2_y), 4)

            # TO/FROM indicator (basic)
            # If bearing to WP is roughly aligned with desired track (e.g. within 90 deg) = TO
            # If bearing is roughly opposite to desired track = FROM
            bearing_to_wp_deg = nav_info['bearing_deg']
            dtk_deg = nav_info['desired_track_deg']
            angle_diff_brg_dtk = (bearing_to_wp_deg - dtk_deg + 540) % 360 - 180
            
            to_from_text = ""
            if abs(angle_diff_brg_dtk) < 85: to_from_text = "TO"
            elif abs(angle_diff_brg_dtk) > 95: to_from_text = "FR" # FROM
            
            if to_from_text:
                tf_surf = self.font_small.render(to_from_text, True, PURPLE)
                # Position near CDI, e.g., above/below center
                self.screen.blit(tf_surf, (center_x - tf_surf.get_width()//2, center_y + radius*0.2))


        hdg_txt_surf = self.font_hud.render(f"{aircraft.yaw:03.0f}°", True, WHITE)
        pygame.draw.rect(self.screen, BLACK, (center_x - 25, y - 22, 50, 20))
        self.screen.blit(hdg_txt_surf, (center_x - hdg_txt_surf.get_width()//2, y - 20))


    def draw_hud(self, aircraft: Aircraft, weather: Weather, camera: Camera, nav_info):
        hud_color = HUD_GREEN
        if aircraft.crashed: hud_color = RED
        elif aircraft.stall_warning_active or aircraft.overspeed_warning_active: hud_color = HUD_AMBER
        
        # Speed Tape (left)
        speed_kts = math.sqrt(aircraft.vx**2 + aircraft.vy**2 + aircraft.vz**2) * 1.94384
        speed_tape_x, speed_tape_y, speed_tape_w, speed_tape_h = 30, HEIGHT//2 - 100, 80, 200
        # pygame.draw.rect(self.screen, (*BLACK,180), (speed_tape_x, speed_tape_y, speed_tape_w, speed_tape_h)) # Box
        # Actual speed in center of tape
        spd_txt = self.font_hud_large.render(f"{speed_kts:3.0f}", True, hud_color)
        pygame.draw.rect(self.screen, (*BLACK,180), (speed_tape_x + speed_tape_w//2 - 35, speed_tape_y + speed_tape_h//2 - 20, 70, 40), border_radius=3)
        self.screen.blit(spd_txt, (speed_tape_x + speed_tape_w//2 - spd_txt.get_width()//2, speed_tape_y + speed_tape_h//2 - spd_txt.get_height()//2))
        # Add "SPD" label
        self.screen.blit(self.font_hud.render("KT", True, hud_color), (speed_tape_x + speed_tape_w//2 - 15, speed_tape_y + speed_tape_h//2 + 15))


        # Altitude Tape (right)
        alt_ft = aircraft.y * 3.28084
        alt_tape_x, alt_tape_y, alt_tape_w, alt_tape_h = WIDTH - 30 - 80, HEIGHT//2 - 100, 80, 200
        # pygame.draw.rect(self.screen, (*BLACK,180), (alt_tape_x, alt_tape_y, alt_tape_w, alt_tape_h)) # Box
        alt_txt = self.font_hud_large.render(f"{alt_ft:5.0f}", True, hud_color)
        pygame.draw.rect(self.screen, (*BLACK,180), (alt_tape_x + alt_tape_w//2 - 50, alt_tape_y + alt_tape_h//2 - 20, 100, 40), border_radius=3)
        self.screen.blit(alt_txt, (alt_tape_x + alt_tape_w//2 - alt_txt.get_width()//2, alt_tape_y + alt_tape_h//2 - alt_txt.get_height()//2))
        self.screen.blit(self.font_hud.render("FT", True, hud_color), (alt_tape_x + alt_tape_w//2 - 15, alt_tape_y + alt_tape_h//2 + 15))

        # Bottom Instruments (ADI & HSI)
        adi_hsi_size = 220 # Larger instruments
        total_width_instruments = adi_hsi_size * 2 + 20 # 2 instruments + spacing
        start_x_instruments = WIDTH//2 - total_width_instruments//2
        instruments_y = HEIGHT - adi_hsi_size - 15 # Positioned at bottom

        self.draw_attitude_indicator(aircraft, start_x_instruments, instruments_y, adi_hsi_size)
        self.draw_horizontal_situation_indicator(aircraft, nav_info, start_x_instruments + adi_hsi_size + 20, instruments_y, adi_hsi_size)

        if camera.mode == "cockpit":
            if self.cockpit_overlay_img:
                self.screen.blit(self.cockpit_overlay_img, (0,0))
            else:
                pygame.draw.rect(self.screen, (40,40,40,200), (0,0,WIDTH,HEIGHT), 30) # Fallback frame

        # Top Right Status Block
        status_x, status_y_start = WIDTH - 180, 20
        current_y = status_y_start
        pygame.draw.rect(self.screen, (*BLACK, 150), (status_x - 10, current_y -5, 180, 200), border_radius=5) # Background for status

        def draw_status(label, value_str, color=hud_color):
            nonlocal current_y
            lbl_surf = self.font_hud.render(label, True, LIGHT_GRAY)
            val_surf = self.font_hud.render(value_str, True, color)
            self.screen.blit(lbl_surf, (status_x, current_y))
            self.screen.blit(val_surf, (status_x + 70, current_y))
            current_y += lbl_surf.get_height() + 2
            return current_y

        draw_status("THR", f"{aircraft.engine_rpm_percent:3.0f}%")
        draw_status("FUEL", f"{aircraft.fuel/(3.785 if aircraft.fuel > 0 else 1):3.0f} Gal", 
                    RED if aircraft.fuel < aircraft.config.fuel_capacity*0.1 else hud_color)
        draw_status("GEAR", "DOWN" if aircraft.gear_down else " UP ", 
                    LIME if aircraft.gear_down else (RED if speed_kts > 100 and not aircraft.gear_down and aircraft.y < 3000 else hud_color))
        draw_status("FLAP", f"{aircraft.get_flaps_deflection():2.0f}°")
        draw_status("TRIM", f"{aircraft.pitch_trim:+2.1f}°") # Show sign for trim
        draw_status("  G ", f"{aircraft.current_g_force:2.1f}", 
                    RED if aircraft.current_g_force > aircraft.config.max_g_force*0.85 else hud_color)

        if aircraft.autopilot_on:
            ap_s = self.font_hud.render("AUTOPILOT", True, CYAN)
            self.screen.blit(ap_s, (status_x, current_y)); current_y += ap_s.get_height() +2
            if aircraft.ap_target_altitude: draw_status(" AP ALT", f"{aircraft.ap_target_altitude*3.28084:5.0f} FT", CYAN)
            if aircraft.ap_target_heading: draw_status(" AP HDG", f"{aircraft.ap_target_heading:03.0f}°", CYAN)
            if aircraft.ap_target_speed: draw_status(" AP SPD", f"{aircraft.ap_target_speed*1.94384:3.0f} KT", CYAN)


        # Central Warnings (Top Middle)
        warn_y = 20
        if aircraft.stall_warning_active:
            ws = self.font_hud_large.render("STALL", True, RED); self.screen.blit(ws, (WIDTH//2 - ws.get_width()//2, warn_y)); warn_y += ws.get_height()
        if aircraft.overspeed_warning_active:
            ws = self.font_hud_large.render("OVERSPEED", True, RED); self.screen.blit(ws, (WIDTH//2 - ws.get_width()//2, warn_y)); warn_y += ws.get_height()
        if not aircraft.engine_on and aircraft.type != AircraftType.GLIDER:
            ws = self.font_hud_large.render("ENGINE OFF", True, RED); self.screen.blit(ws, (WIDTH//2 - ws.get_width()//2, warn_y)); warn_y += ws.get_height()
        if aircraft.structural_integrity < 50:
            ws = self.font_hud_large.render(f"DAMAGE {aircraft.structural_integrity:.0f}%", True, RED); self.screen.blit(ws, (WIDTH//2 - ws.get_width()//2, warn_y)); warn_y += ws.get_height()


        # Nav Display (Top Left)
        if nav_info:
            nav_block_x, nav_block_y = 20, 20
            nav_block_w, nav_block_h = 260, 110
            pygame.draw.rect(self.screen, (*BLACK,150), (nav_block_x, nav_block_y, nav_block_w, nav_block_h), border_radius=5)
            
            ny = nav_block_y + 8; nx_val = nav_block_x + 80 # Indent for values
            def draw_nav(label, value, color=WHITE):
                nonlocal ny
                lbl_s = self.font_hud.render(label, True, LIGHT_GRAY)
                val_s = self.font_hud.render(value, True, color)
                self.screen.blit(lbl_s, (nav_block_x + 8, ny))
                self.screen.blit(val_s, (nx_val, ny))
                ny += lbl_s.get_height() + 2

            draw_nav("WAYPOINT:", nav_info['wp_name'][:12], CYAN) # Truncate long names
            draw_nav("DISTANCE:", f"{nav_info['distance_nm']:.1f} NM")
            draw_nav("BEARING:", f"{nav_info['bearing_deg']:.0f}°")
            draw_nav("DTK:", f"{nav_info['desired_track_deg']:.0f}° (Dev {nav_info['track_error_deg']:.0f}°) ")
            draw_nav("WP ALT:", f"{nav_info['altitude_ft']:.0f} FT (Err {nav_info['altitude_error_ft']:.0f})")


    def draw_main_menu(self, buttons, selected_aircraft_type):
        self.screen.fill(NAVY) # Darker background for menu
        title = self.font_large.render("Flight Simulator X-treme", True, GOLD) # Catchy title
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//4 - 50))

        ac_text = self.font_medium.render(f"Aircraft: {selected_aircraft_type.value}", True, YELLOW)
        self.screen.blit(ac_text, (WIDTH//2 - ac_text.get_width()//2, HEIGHT//2 - 80))
        info_text = self.font_small.render("Press 'C' to change aircraft. Mouse click or Enter to Start.", True, LIGHT_GRAY)
        self.screen.blit(info_text, (WIDTH//2 - info_text.get_width()//2, HEIGHT//2 - 40))

        for button in buttons: button.draw(self.screen)
        pygame.display.flip()

    def draw_pause_menu(self, buttons, help_visible, aircraft_controls_info):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 20, 40, 200)) # Dark blue overlay
        self.screen.blit(overlay, (0,0))

        title = self.font_large.render("GAME PAUSED", True, ORANGE)
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 100))

        for button in buttons: button.draw(self.screen)
        
        help_start_y = HEIGHT//2 - 20
        help_info_text = self.font_small.render("Press 'H' for Controls | 'M' for Weather | 'C' for Aircraft", True, LIGHT_GRAY)
        self.screen.blit(help_info_text, (WIDTH//2 - help_info_text.get_width()//2, help_start_y - 30))

        if help_visible:
            pygame.draw.rect(self.screen, (*DARK_GRAY, 220), (WIDTH//2 - 280, help_start_y, 560, 240), border_radius=8)
            for i, line in enumerate(aircraft_controls_info):
                txt = self.font_small.render(line, True, WHITE)
                self.screen.blit(txt, (WIDTH//2 - 270, help_start_y + 10 + i * 22))
        pygame.display.flip()

    def draw_debrief_screen(self, aircraft: Aircraft, buttons):
        self.screen.fill((20,30,50)) # Dark background
        title_text = "SIMULATION ENDED"
        title_color = ORANGE
        if aircraft.crashed: title_text = "AIRCRAFT CRASHED"; title_color = RED
        elif aircraft.landed_successfully: title_text = "LANDING SUCCESSFUL"; title_color = LIME
        
        title = self.font_large.render(title_text, True, title_color)
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 80))

        stats_y_start = 200; stats_x = WIDTH//2
        stats = [
            f"Flight Time: {aircraft.flight_time_sec:.1f} s",
            f"Distance Flown: {aircraft.distance_traveled_m/1000:.2f} km ({aircraft.distance_traveled_m/1852:.1f} NM)",
            f"Max Altitude: {aircraft.max_altitude_reached*3.28084:.0f} ft",
            f"Max Speed: {aircraft.max_speed_reached*1.94384:.0f} kts",
            f"Fuel Used: {(aircraft.config.fuel_capacity - aircraft.fuel)/3.785:.1f} Gal",
            f"Structural Integrity: {aircraft.structural_integrity:.0f}%"
        ]
        if aircraft.landed_successfully:
            stats.append(f"Touchdown V/S: {aircraft.touchdown_vertical_speed_mps*196.85:.0f} fpm") # m/s to fpm
            stats.append(f"Landing Score: {aircraft.landing_score:.0f} / 100")

        for i, stat_line in enumerate(stats):
            txt = self.font_medium.render(stat_line, True, WHITE)
            self.screen.blit(txt, (stats_x - txt.get_width()//2, stats_y_start + i * 40))
        
        for button in buttons: button.draw(self.screen)
        pygame.display.flip()


class FlightSimulator:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Flight Simulator Pro Alpha")
        self.clock = pygame.time.Clock()
        
        self.sound_manager = SoundManager()
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
        btn_w, btn_h = 240, 55 # Larger buttons
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
        self.aircraft.y = main_airport['elevation'] + 150 # Start airborne for quick test
        self.aircraft.z = main_airport['z']
        self.aircraft.yaw = main_airport['runway_heading']
        self.aircraft.vx = math.sin(math.radians(self.aircraft.yaw)) * self.aircraft.config.stall_speed_clean * 0.8 # Initial speed
        self.aircraft.vz = math.cos(math.radians(self.aircraft.yaw)) * self.aircraft.config.stall_speed_clean * 0.8
        self.aircraft.on_ground = False
        self.aircraft.gear_down = True # Typically up after takeoff

        self.aircraft.waypoints = [
            Waypoint(main_airport['x'] + math.sin(math.radians(main_airport['runway_heading']))*8000,
                     main_airport['z'] + math.cos(math.radians(main_airport['runway_heading']))*8000,
                     1200, "DEP FIX", "NAV"),
            Waypoint(other_airport['x'], other_airport['z'], other_airport['elevation'] + 400,
                     other_airport['name'] + " IAF", "NAV"), # Initial Approach Fix
            Waypoint(other_airport['x'], other_airport['z'], other_airport['elevation'],
                     other_airport['name'], "AIRPORT")
        ]
        self.aircraft.current_waypoint_index = 0
        
        self.camera = Camera()
        self.camera.mode = "follow_mouse_orbit"
        self.camera.distance = 35 if self.selected_aircraft_type == AircraftType.AIRLINER else 20
        
        self.weather.type = random.choice(list(WeatherType)) # Random weather on start
        self.weather.update_conditions()

        self.game_state = GameState.PLAYING
        self.sound_manager.enabled = True
        self.sound_manager.play_engine_sound(self.aircraft.engine_rpm_percent, self.aircraft.type) # Start engine sound

    def restart_flight(self):
        self.sound_manager.stop_all_sounds()
        self.start_game()

    def go_to_main_menu(self):
        self.sound_manager.stop_all_sounds()
        self.sound_manager.enabled = False
        self.aircraft = None
        self.game_state = GameState.MENU
        pygame.mouse.set_visible(True) # Ensure mouse is visible in menu
        pygame.event.set_grab(False)
        
    def quit_game(self):
        self.running = False

    def toggle_pause(self):
        if self.game_state == GameState.PLAYING:
            self.game_state = GameState.PAUSED
            self.sound_manager.enabled = False # Or pygame.mixer.pause()
            pygame.mouse.set_visible(True)
            pygame.event.set_grab(False)
        elif self.game_state == GameState.PAUSED:
            self.game_state = GameState.PLAYING
            self.show_help_in_pause = False
            self.sound_manager.enabled = True # Or pygame.mixer.unpause()
            if self.camera.is_mouse_orbiting : # If mouse was orbiting before pause
                 pygame.mouse.set_visible(False)
                 pygame.event.set_grab(True)


    def cycle_aircraft_type(self):
        types = list(AircraftType)
        current_idx = types.index(self.selected_aircraft_type)
        self.selected_aircraft_type = types[(current_idx + 1) % len(types)]
        if self.aircraft and self.game_state == GameState.PAUSED:
            # Store more state to transfer to new aircraft if desired
            # For now, just changes selected type for next flight start
            print(f"Next flight aircraft: {self.selected_aircraft_type.value}")


    def handle_continuous_input(self, dt): # Renamed from handle_input
        if not self.aircraft: return

        keys = pygame.key.get_pressed()
        
        # Effective control surface deflection scales with effectiveness
        pitch_authority = self.aircraft.config.turn_rate * 0.8 * self.aircraft.elevator_effectiveness
        roll_authority = self.aircraft.config.turn_rate * 1.2 * self.aircraft.aileron_effectiveness
        yaw_authority = self.aircraft.config.turn_rate * 0.5 * self.aircraft.rudder_effectiveness
        
        # Pitch - W/S control pitch rate directly
        if keys[pygame.K_w]: self.aircraft.pitch_rate -= pitch_authority * dt * 2.0 # Faster response
        if keys[pygame.K_s]: self.aircraft.pitch_rate += pitch_authority * dt * 2.0
        # Apply pitch trim as a constant small rate adjustment
        self.aircraft.pitch_rate += self.aircraft.pitch_trim * 0.15 * self.aircraft.elevator_effectiveness * dt * 10

        # Roll - A/D control roll rate
        if keys[pygame.K_a]: self.aircraft.roll_rate -= roll_authority * dt * 2.5
        if keys[pygame.K_d]: self.aircraft.roll_rate += roll_authority * dt * 2.5

        # Yaw (Rudder) - Q/E control yaw rate
        if keys[pygame.K_q]: self.aircraft.yaw_rate -= yaw_authority * dt * 2.0
        if keys[pygame.K_e]: self.aircraft.yaw_rate += yaw_authority * dt * 2.0
        
        # Clamp max rotation rates
        self.aircraft.pitch_rate = np.clip(self.aircraft.pitch_rate, -50, 50) # deg/s
        self.aircraft.roll_rate = np.clip(self.aircraft.roll_rate, -120, 120)
        self.aircraft.yaw_rate = np.clip(self.aircraft.yaw_rate, -30, 30)

        # Throttle
        throttle_change_rate = 30.0 # % per second
        if keys[pygame.K_LSHIFT] or keys[pygame.K_PAGEUP]:
            self.aircraft.thrust_input = min(100, self.aircraft.thrust_input + throttle_change_rate * dt)
        if keys[pygame.K_LCTRL] or keys[pygame.K_PAGEDOWN]:
            self.aircraft.thrust_input = max(0, self.aircraft.thrust_input - throttle_change_rate * dt)
        
        self.aircraft.brakes_input = 1.0 if keys[pygame.K_SPACE] else 0.0


    def handle_event(self, event): # For discrete key presses / UI events
        # Let camera handle its mouse events first, regardless of game state for orbit/zoom
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
                if event.key == pygame.K_3: self.camera.mode = "external_fixed_mouse_orbit"; self.camera.distance=max(25,self.camera.distance) # Similar modes now
                
                if event.key == pygame.K_TAB:
                    self.aircraft.autopilot_on = not self.aircraft.autopilot_on
                    if self.aircraft.autopilot_on:
                        self.aircraft.ap_target_altitude = self.aircraft.y
                        self.aircraft.ap_target_heading = self.aircraft.yaw
                        self.aircraft.ap_target_speed = math.sqrt(self.aircraft.vx**2 + self.aircraft.vy**2 + self.aircraft.vz**2)
                        print("AP ON. Targets: Alt, Hdg, Spd set to current.")
                    else: print("AP OFF.")
                if event.key == pygame.K_n:
                    self.aircraft.nav_mode_active = not self.aircraft.nav_mode_active
                    print(f"NAV mode {'ACTIVE' if self.aircraft.nav_mode_active else 'INACTIVE'}")

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
            if event.key == pygame.K_p and (self.game_state == GameState.PLAYING or self.game_state == GameState.PAUSED) :
                    self.toggle_pause()


    def update(self, dt):
        if self.game_state == GameState.PLAYING and self.aircraft:
            self.handle_continuous_input(dt)
            self.aircraft.update(dt, self.weather, self.sound_manager)
            self.weather.update(dt)
            self.camera.update(self.aircraft, dt)
            
            # Update engine sound more frequently if it's a short loop that needs params change
            # For now, play_engine_sound in init of game, and volume adjusts.
            # If engine sound stops (e.g. fuel out), this logic might need adjustment
            if self.aircraft.engine_on and self.aircraft.fuel > 0:
                 if self.sound_manager.engine_channel is None or not self.sound_manager.engine_channel.get_busy():
                      self.sound_manager.play_engine_sound(self.aircraft.engine_rpm_percent, self.aircraft.type)
                 elif self.sound_manager.engine_channel: # Adjust volume if playing
                      self.sound_manager.engine_channel.set_volume(0.05 + (self.aircraft.engine_rpm_percent / 100.0) * 0.25)
            elif self.sound_manager.engine_channel and self.sound_manager.engine_channel.get_busy():
                self.sound_manager.engine_channel.stop() # Stop engine sound if engine off or no fuel


            if self.aircraft.crashed or \
               (self.aircraft.on_ground and math.sqrt(self.aircraft.vx**2 + self.aircraft.vz**2) < 0.2 and self.aircraft.landed_successfully):
                self.game_state = GameState.DEBRIEF
                self.sound_manager.stop_all_sounds()
                self.sound_manager.enabled = False
                pygame.mouse.set_visible(True)
                pygame.event.set_grab(False)
    
    def render(self):
        if self.game_state == GameState.MENU:
            self.renderer.draw_main_menu(self.menu_buttons, self.selected_aircraft_type)
        elif self.game_state == GameState.PAUSED:
            # To make pause menu appear over game screen, draw game first then menu
            # If game objects are not updated, it shows the frozen frame.
            # For now, it just draws the menu on whatever was on screen or over a dark overlay.
            self.renderer.draw_pause_menu(self.pause_buttons, self.show_help_in_pause, self.aircraft_controls_info)
        elif self.game_state == GameState.DEBRIEF and self.aircraft:
            self.renderer.draw_debrief_screen(self.aircraft, self.debrief_buttons)
        elif self.game_state == GameState.PLAYING and self.aircraft:
            self.renderer.draw_horizon_and_sky(self.aircraft, self.camera)
            self.renderer.draw_terrain_features(self.camera, self.terrain, self.weather)
            self.renderer.draw_aircraft_model(self.aircraft, self.camera)
            self.renderer.draw_weather_effects(self.weather, self.camera, self.aircraft)
            nav_data = self.aircraft.get_nav_display_info()
            self.renderer.draw_hud(self.aircraft, self.weather, self.camera, nav_data)
            pygame.display.flip() # Flip only after game world is drawn for PLAYING state
        else: # Should not be reached if state logic is correct
            self.screen.fill(BLACK)
            pygame.display.flip()


    def run(self):
        self.running = True
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05) # Cap dt to prevent large physics steps on lag spikes (e.g. max 50ms step)

            for event in pygame.event.get():
                self.handle_event(event)
            
            self.update(dt)
            self.render() # render handles its own display.flip based on state
        
        self.sound_manager.stop_all_sounds()
        pygame.quit()

if __name__ == "__main__":
    # Dummy asset creation (optional, for testing if assets are missing)
    # Check and create dummy cockpit_overlay.png
    try: open("cockpit_overlay.png", "rb").close()
    except FileNotFoundError:
        try:
            surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA) # Use SRCALPHA
            # Example: draw a simple frame
            frame_color = (80, 90, 100, 180) # Semi-transparent dark gray
            pygame.draw.rect(surf, frame_color, (0, 0, WIDTH, 120))  # Top bar
            pygame.draw.rect(surf, frame_color, (0, HEIGHT - 80, WIDTH, 80)) # Bottom dashboard area
            pygame.draw.rect(surf, frame_color, (0, 0, 80, HEIGHT))    # Left pillar
            pygame.draw.rect(surf, frame_color, (WIDTH - 80, 0, 80, HEIGHT))# Right pillar
            pygame.image.save(surf, "cockpit_overlay.png")
            print("Created dummy cockpit_overlay.png")
        except Exception as e_img: print(f"Could not create dummy cockpit_overlay.png: {e_img}")
    
    # Dummy sound files (very short silences or beeps)
    sound_files_to_check = ["stall_warning.wav", "gear_up.wav", "gear_down.wav", "click.wav"]
    for sf_name in sound_files_to_check:
        try: open(sf_name, "rb").close()
        except FileNotFoundError:
            try:
                # Create a short 0.1s beep/silence as placeholder
                sr = 22050; frames = int(0.1 * sr)
                arr = np.zeros((frames,1), dtype=np.int16) # Mono for wav
                if "click" in sf_name: # Make click a short pulse
                    for i in range(int(0.01*sr)): arr[i] = 10000
                # For others, a short sine wave or silence
                elif "stall" in sf_name: # Stall a bit longer
                    frames = int(0.3*sr); arr = np.zeros((frames,1), dtype=np.int16)
                    for i in range(frames): arr[i] = int(10000 * math.sin(2 * math.pi * 800 * i / sr))


                # Pygame cannot directly save wav. Need scipy.io.wavfile or wave module
                # This is complex for a quick dummy. For now, just acknowledge missing.
                # For actual dummy sound creation, you'd use 'wave' module:
                # import wave
                # with wave.open(sf_name, 'w') as wf:
                # wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
                # wf.writeframes(arr.tobytes())
                print(f"Dummy sound file '{sf_name}' would be created here (manual creation needed or ignore warning).")
            except Exception as e_snd: print(f"Could not create dummy {sf_name}: {e_snd}")


    sim = FlightSimulator()
    sim.run()
