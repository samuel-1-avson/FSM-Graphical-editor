
import pygame
import math
import random
import numpy as np
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import time

# Initialize Pygame
pygame.init()
pygame.mixer.init()

# Constants
WIDTH, HEIGHT = 1600, 1000
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (135, 206, 235) # Sky blue
DARK_BLUE = (25, 25, 112) # Darker Sky
GREEN = (34, 139, 34) # Ground Green
DARK_GREEN = (0, 100, 0)
BROWN = (139, 69, 19) # Ground Brown (ADI)
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
    HELICOPTER = "Helicopter" # Note: Helicopter physics are very different, current model won't suit well.
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
    max_thrust: float  # Max thrust in Newtons
    mass: float  # kg
    drag_coefficient_base: float # Base drag coefficient (Cd0)
    lift_coefficient_max: float # Max lift coefficient (Cl_max)
    wing_area: float # m^2
    aspect_ratio: float # Wing aspect ratio
    max_speed: float  # m/s (Vne)
    fuel_capacity: float  # Liters (approx gallons for simplicity in display)
    fuel_consumption: float  # Liters per second at max thrust
    max_altitude: float  # meters
    turn_rate: float  # degrees per second (max sustained)
    stall_speed_clean: float  # m/s (Vs1)
    service_ceiling: float  # meters
    max_g_force: float
    climb_rate: float  # m/s
    engine_count: int = 1
    # Critical Angle of Attack (degrees) where stall begins
    critical_aoa_positive: float = 15.0
    critical_aoa_negative: float = -12.0
    # Lift curve slope (per radian)
    cl_alpha: float = 2 * math.pi * 0.9 # 0.9 for typical airfoils
    engine_spool_rate: float = 0.2 # % per second


@dataclass
class Waypoint:
    x: float
    z: float
    altitude: float
    name: str
    waypoint_type: str = "NAV"  # NAV, AIRPORT, TARGET
    required_speed: Optional[float] = None
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
        # Try to load sounds, if they exist. Otherwise, use synthetic ones.
        try:
            self.sounds['stall_warning'] = pygame.mixer.Sound("stall_warning.wav") # Example
            self.sounds['gear_up'] = pygame.mixer.Sound("gear_up.wav")
            self.sounds['gear_down'] = pygame.mixer.Sound("gear_down.wav")
        except pygame.error:
            print("Warning: Could not load some sound files. Using synthetic sounds.")
            self.sounds['stall_warning'] = None # Fallback handled in play method

    def create_synthetic_sound(self, frequency, duration=0.1, volume=0.1, shape='sine'):
        if not self.enabled: return None
        sample_rate = pygame.mixer.get_init()[0] # Use actual initialized sample rate
        frames = int(duration * sample_rate)
        arr = np.zeros((frames, 2), dtype=np.float32)

        for i in range(frames):
            t = float(i) / sample_rate
            if shape == 'sine':
                wave = np.sin(2 * np.pi * frequency * t)
            elif shape == 'square':
                wave = np.sign(np.sin(2 * np.pi * frequency * t))
            elif shape == 'sawtooth':
                wave = 2 * (t * frequency - np.floor(0.5 + t * frequency))
            else: # noise as default
                wave = np.random.uniform(-1, 1)
            
            arr[i, 0] = wave * volume
            arr[i, 1] = wave * volume
        
        sound_array = (arr * 32767).astype(np.int16)
        return pygame.sndarray.make_sound(sound_array)

    def play_engine_sound(self, rpm_percent, engine_type=AircraftType.AIRLINER):
        if not self.enabled: return
        
        base_freq = 50
        if engine_type == AircraftType.FIGHTER: base_freq = 70
        elif engine_type == AircraftType.ULTRALIGHT: base_freq = 100

        current_freq = base_freq + (rpm_percent / 100) * (base_freq * 3) # More dynamic range
        
        if self.engine_channel is None or not self.engine_channel.get_busy():
            sound = self.create_synthetic_sound(current_freq, duration=0.5, volume=0.05 + (rpm_percent/100)*0.1, shape='sawtooth')
            if sound: self.engine_channel = sound.play(-1)
        elif self.engine_channel and hasattr(self.engine_channel, 'sound'): # Check if sound object exists
             # This is a simplified way; ideally, you'd crossfade or use a more complex synth
             # For now, just restart with new params if significantly different
             # A proper dynamic engine sound needs a more advanced audio engine
             pass # Re-creating sound every frame is too slow. Need a better method.
                  # For now, let it play and adjust volume if possible or just let it loop.
        if self.engine_channel:
            self.engine_channel.set_volume(0.1 + (rpm_percent/100)*0.2)


    def play_sound(self, sound_name, loops=0):
        if not self.enabled: return
        
        if sound_name in self.sounds and self.sounds[sound_name]:
            self.sounds[sound_name].play(loops)
        elif sound_name == 'stall_warning': # Fallback for critical sounds
            self.play_warning_beep(frequency=600, duration=0.5)
        elif sound_name == 'gear_up' or sound_name == 'gear_down':
             self.play_warning_beep(frequency=300, duration=0.3) # Generic mechanical sound


    def play_warning_beep(self, frequency=800, duration=0.2, volume=0.3):
        if not self.enabled: return
        if self.warning_channel is None or not self.warning_channel.get_busy():
            sound = self.create_synthetic_sound(frequency, duration, volume, shape='square')
            if sound: self.warning_channel = sound.play()

    def stop_all_sounds(self):
        if self.engine_channel: self.engine_channel.stop()
        if self.warning_channel: self.warning_channel.stop()
        if self.ambient_channel: self.ambient_channel.stop()
        # For other sounds, you might need to manage them individually if they are long playing.


class Weather(Weather): # Inherit from existing for brevity, then override/add
    def __init__(self):
        super().__init__()
        # Add more detailed cloud properties
        self.cloud_particles = []
        self.generate_cloud_particles()

    def generate_clouds(self):
        super().generate_clouds()
        self.generate_cloud_particles()

    def generate_cloud_particles(self):
        self.cloud_particles = []
        if self.type in [WeatherType.CLOUDY, WeatherType.STORM, WeatherType.RAIN, WeatherType.SNOW, WeatherType.FOG]:
            for layer in self.cloud_layers:
                for _ in range(int(layer['coverage'] * 50)): # More particles for denser clouds
                    particle = {
                        'x': random.uniform(-10000, 10000),
                        'z': random.uniform(-10000, 10000),
                        'y': layer['altitude'] + random.uniform(-layer['thickness']/2, layer['thickness']/2),
                        'size': random.uniform(100, 500) * layer['coverage'],
                        'opacity': random.uniform(50, 150) * layer['coverage']
                    }
                    self.cloud_particles.append(particle)
    
    def update(self, dt):
        super().update(dt)
        # Add logic for moving clouds with wind, etc. if desired
        if random.random() < 0.0002: # Slower weather change
            if self.type != WeatherType.STORM: # Storms persist longer
                 old_type = self.type
                 self.type = random.choice(list(WeatherType))
                 if self.type != old_type:
                     self.generate_clouds()
                 self.update_conditions()


class Aircraft:
    def __init__(self, x, y, z, aircraft_type: AircraftType):
        self.x = x  # World X (East/West)
        self.y = y  # World Y (Altitude)
        self.z = z  # World Z (North/South) - often -Z is forward in graphics
        
        self.vx = 0.0 # m/s
        self.vy = 0.0 # m/s
        self.vz = 0.0 # m/s
        
        self.pitch = 0.0  # Degrees, positive nose up
        self.yaw = 0.0    # Degrees, 0 North, 90 East, 180 South, 270 West
        self.roll = 0.0   # Degrees, positive right wing down

        self.pitch_rate = 0.0 # deg/s
        self.yaw_rate = 0.0   # deg/s
        self.roll_rate = 0.0  # deg/s

        self.thrust_input = 0.0 # Commanded thrust % (0-100)
        self.engine_rpm_percent = 0.0 # Actual engine RPM %

        self.crashed = False
        self.on_ground = (y <= 0.1) # More robust check
        self.gear_down = True
        self.flaps_setting = 0 # 0: Up, 1: Setting 1, 2: Setting 2 etc.
        self.flaps_max_setting = 3 # e.g. 0, 10, 25, 40 degrees
        self.flaps_degrees = [0, 10, 25, 40] # Corresponding flap deflection
        self.spoilers_deployed = False # True/False for armed/deployed
        self.brakes_input = 0.0 # 0-1 strength
        
        self.autopilot_on = False
        self.ap_target_altitude: Optional[float] = None
        self.ap_target_heading: Optional[float] = None
        self.ap_target_speed: Optional[float] = None
        
        self.engine_on = True # Master engine switch
        
        self.configs = {
            AircraftType.FIGHTER: AircraftConfig("F-16", 120000, 8500, 0.016, 1.6, 30, 8, 650, 3000, 0.1, 18000, 15, 70, 15000, 9.0, 250, engine_count=1, critical_aoa_positive=20.0, cl_alpha=5.8, engine_spool_rate=0.5),
            AircraftType.AIRLINER: AircraftConfig("B737", 110000, 75000, 0.020, 1.5, 125, 9, 280, 26000, 0.06, 14000, 3, 65, 12500, 2.5, 150, engine_count=2, critical_aoa_positive=16.0, cl_alpha=5.5, engine_spool_rate=0.15),
            AircraftType.GLIDER: AircraftConfig("ASK-21", 0, 600, 0.010, 1.8, 17, 26, 70, 0, 0, 10000, 4, 30, 8000, 4.5, 20, engine_count=0, critical_aoa_positive=14.0), # Higher AR
            AircraftType.CARGO: AircraftConfig("C-130", 4 * 15000, 70000, 0.028, 1.2, 160, 7, 180, 20000, 0.09, 10000, 2, 55, 9000, 2.0, 100, engine_count=4, critical_aoa_positive=15.0, engine_spool_rate=0.1),
            AircraftType.ULTRALIGHT: AircraftConfig("Quicksilver", 3000, 250, 0.030, 1.4, 15, 10, 30, 50, 0.12, 3000, 5, 20, 2500, 3.0, 20, engine_count=1, critical_aoa_positive=18.0, engine_spool_rate=0.3),
            # Helicopter is special, needs different physics model
            AircraftType.HELICOPTER: AircraftConfig("UH-60", 2*1200, 5200, 0.06, 0.4, 20, 5, 80, 1300, 0.15, 6000, 10, 0, 5800, 3.5, 50, engine_count=2, critical_aoa_positive=90.0), # Placeholder values
        }
        
        self.type = aircraft_type
        self.config = self.configs[aircraft_type]
        self.fuel = self.config.fuel_capacity
        self.engines_failed = [False] * self.config.engine_count
        
        self.waypoints: List[Waypoint] = []
        self.current_waypoint_index = 0
        self.nav_mode_active = False
        self.ils_locked = False
        self.approach_mode = False
        
        self.electrical_power = True
        self.hydraulic_power = True
        self.avionics_power = True
        self.engine_health = [100.0] * self.config.engine_count # % health
        self.structural_integrity = 100.0 # %
        self.ice_buildup_kg = 0.0 # kg of ice
        self.pitot_heat_on = False # Can be a player control
        
        self.current_g_force = 1.0
        self.aoa_degrees = 0.0 # Angle of Attack
        self.stall_warning_active = False
        self.overspeed_warning_active = False
        
        self.flight_time_sec = 0.0
        self.distance_traveled_m = 0.0
        
        self.touchdown_vertical_speed_mps = 0.0
        self.landing_score = 0.0
        self.landed_successfully = False

        self.pitch_trim = 0.0 # Degrees of elevator trim

        # Control surface effectiveness (0-1)
        self.elevator_effectiveness = 1.0
        self.aileron_effectiveness = 1.0
        self.rudder_effectiveness = 1.0

        # Aircraft model vertices (local coordinates, simple representation)
        # Format: (x, y, z) where +x is right, +y is up, +z is forward
        fuselage_length = 15 if aircraft_type == AircraftType.AIRLINER else 10
        fuselage_radius = 1.5 if aircraft_type == AircraftType.AIRLINER else 1
        wing_span = 20 if aircraft_type == AircraftType.AIRLINER else 12
        wing_chord = 3 if aircraft_type == AircraftType.AIRLINER else 2
        tail_height = 3 if aircraft_type == AircraftType.AIRLINER else 2
        
        self.model_vertices_local = [
            # Fuselage (simple box for now)
            (fuselage_radius, -fuselage_radius, fuselage_length * 0.6), (fuselage_radius, fuselage_radius, fuselage_length * 0.6),
            (-fuselage_radius, fuselage_radius, fuselage_length * 0.6), (-fuselage_radius, -fuselage_radius, fuselage_length * 0.6),
            (fuselage_radius, -fuselage_radius, -fuselage_length * 0.4), (fuselage_radius, fuselage_radius, -fuselage_length * 0.4),
            (-fuselage_radius, fuselage_radius, -fuselage_length * 0.4), (-fuselage_radius, -fuselage_radius, -fuselage_length * 0.4),
            # Wings
            (wing_span/2, 0, wing_chord/2), (wing_span/2, 0, -wing_chord/2),
            (-wing_span/2, 0, wing_chord/2), (-wing_span/2, 0, -wing_chord/2),
            (0,0,0), # Center point for wing-fuselage connection
            # Tail (Vertical Stabilizer)
            (0, tail_height, -fuselage_length*0.35), (0, 0, -fuselage_length*0.35), (0,0,-fuselage_length*0.45),
            # Horizontal Stabilizer
            (wing_span/4, 0, -fuselage_length*0.4), (-wing_span/4, 0, -fuselage_length*0.4),
            (0,0,-fuselage_length*0.3)
        ]
        self.model_lines = [
            # Fuselage
            (0,1), (1,2), (2,3), (3,0), (4,5), (5,6), (6,7), (7,4),
            (0,4), (1,5), (2,6), (3,7),
            # Wings (connecting to fuselage center)
            (12,8), (12,9), (8,9),
            (12,10), (12,11), (10,11),
            # Tail
            (13,14), (14,15), (15,13),
            # Horizontal Stabilizer
            (17,16), (17,18)
        ]
        
    def get_current_mass(self):
        return self.config.mass + (self.fuel * 0.8) + self.ice_buildup_kg # Fuel density ~0.8 kg/L

    def get_flaps_deflection(self):
        return self.flaps_degrees[self.flaps_setting]

    def update_engine_rpm(self, dt):
        # Engine spooling
        diff = self.thrust_input - self.engine_rpm_percent
        change = self.config.engine_spool_rate * 100 * dt # Rate is % of total thrust per second
        if abs(diff) < change:
            self.engine_rpm_percent = self.thrust_input
        else:
            self.engine_rpm_percent += math.copysign(change, diff)
        self.engine_rpm_percent = max(0, min(100, self.engine_rpm_percent))

        # Basic idle RPM for non-gliders
        if self.type != AircraftType.GLIDER and self.engine_on:
            idle_rpm = 20 if self.type == AircraftType.AIRLINER else 25 # %
            if self.thrust_input < idle_rpm : # if commanded thrust is below idle, engine still runs at idle
                 self.engine_rpm_percent = max(idle_rpm, self.engine_rpm_percent)
            if self.thrust_input == 0 and self.engine_rpm_percent < idle_rpm: # Ensure it can reach idle if commanded 0
                self.engine_rpm_percent = idle_rpm


    def calculate_aerodynamics(self, air_density, current_speed_mps, weather: Weather):
        q = 0.5 * air_density * current_speed_mps**2 # Dynamic pressure

        # Angle of Attack (AoA)
        if current_speed_mps > 1: # Avoid division by zero
            # Simplification: using vy against horizontal speed component
            horizontal_speed = math.sqrt(self.vx**2 + self.vz**2)
            if horizontal_speed > 0.1: # Avoid instability at very low horizontal speeds
                 # This is AoA relative to horizontal plane, not airflow. More complex for true AoA.
                 # True AoA needs velocity vector relative to aircraft body x-axis.
                 # For now, pitch - flight path angle
                 flight_path_angle_rad = math.atan2(self.vy, horizontal_speed)
                 self.aoa_degrees = self.pitch - math.degrees(flight_path_angle_rad)
            else: # If nearly vertical, AoA can be large
                 self.aoa_degrees = self.pitch - math.copysign(90, self.vy) if abs(self.vy) > 0.1 else self.pitch
        else:
            self.aoa_degrees = self.pitch
        
        # Clamp AoA to avoid extreme values from simplified model
        self.aoa_degrees = max(-90, min(90, self.aoa_degrees))
        aoa_rad = math.radians(self.aoa_degrees)

        # Lift Coefficient (Cl)
        cl = 0.0
        # Base Cl from AoA (linear part of lift curve)
        cl_from_aoa = self.config.cl_alpha * aoa_rad
        
        # Stall model
        if self.aoa_degrees > self.config.critical_aoa_positive:
            self.stall_warning_active = True
            # Simplified post-stall: Cl drops significantly
            overshoot = self.aoa_degrees - self.config.critical_aoa_positive
            cl = self.config.lift_coefficient_max - overshoot * 0.1 # Gradual drop past critical
            cl = max(0.2, cl) # Some lift remains
        elif self.aoa_degrees < self.config.critical_aoa_negative: # Negative stall
            self.stall_warning_active = True
            overshoot = abs(self.aoa_degrees - self.config.critical_aoa_negative)
            cl = -self.config.lift_coefficient_max + overshoot * 0.1
            cl = min(-0.2, cl)
        else:
            self.stall_warning_active = False
            cl = cl_from_aoa
        
        # Flap contribution to Cl (rough approximation)
        cl_flaps = (self.get_flaps_deflection() / 40.0) * 0.8 # Max 0.8 Cl bonus from flaps
        cl += cl_flaps
        cl = max(-self.config.lift_coefficient_max -0.5, min(self.config.lift_coefficient_max + 0.5, cl)) # Clamp total Cl

        # Drag Coefficient (Cd)
        cd_base = self.config.drag_coefficient_base
        # Induced Drag (Cd_i = Cl^2 / (pi * e * AR))
        # Oswald efficiency factor 'e', typically 0.7-0.85. Using 0.8.
        cd_induced = (cl**2) / (math.pi * 0.8 * self.config.aspect_ratio) if self.config.aspect_ratio > 0 else 0
        
        cd_flaps = (self.get_flaps_deflection() / 40.0) * 0.05 # Flaps add drag
        cd_gear = 0.025 if self.gear_down else 0.002 # Gear adds drag
        cd_spoilers = 0.10 if self.spoilers_deployed else 0.0 # Spoilers add significant drag
        
        # Ice accumulation drag
        cd_ice = self.ice_buildup_kg * 0.0001 

        cd_total = cd_base + cd_induced + cd_flaps + cd_gear + cd_spoilers + cd_ice

        # Calculate forces
        lift_force = cl * q * self.config.wing_area
        drag_force = cd_total * q * self.config.wing_area

        # Spoilers also reduce lift
        if self.spoilers_deployed:
            lift_force *= 0.7 # Reduce lift by 30%

        # Control Surface Effectiveness (scales with dynamic pressure, simplified)
        # Max effectiveness at a certain speed (e.g. 100 m/s), less at lower/higher.
        effectiveness_factor = min(1.0, q / (0.5 * 1.225 * 100**2)) # Normalized against q at 100 m/s
        self.elevator_effectiveness = effectiveness_factor
        self.aileron_effectiveness = effectiveness_factor
        self.rudder_effectiveness = effectiveness_factor

        return lift_force, drag_force

    def apply_forces_and_torques(self, dt, lift, drag, thrust_force, weather):
        current_mass = self.get_current_mass()
        gravity = -9.81 * current_mass

        # --- Forces ---
        # Transform forces from aircraft body frame to world frame
        # Rotation matrix components (from world to body: R_wb)
        # We need body to world: R_bw = R_wb.transpose()
        # Simplified: Decompose forces along world axes based on aircraft orientation.

        # Thrust acts along aircraft's longitudinal axis (roll=0, pitch=pitch, yaw=yaw)
        # For simplicity, assume thrust vector aligns with aircraft's Z body axis (forward)
        # Decompose thrust based on pitch and yaw.
        thrust_fx = thrust_force * math.cos(math.radians(self.pitch)) * math.sin(math.radians(self.yaw))
        thrust_fy = thrust_force * math.sin(math.radians(self.pitch))
        thrust_fz = thrust_force * math.cos(math.radians(self.pitch)) * math.cos(math.radians(self.yaw)) # Z world = North

        # Lift acts perpendicular to airflow, simplified as perpendicular to velocity vector in aircraft's pitch plane,
        # then rotated by roll.
        # Drag acts opposite to velocity vector.

        # Velocity vector in world frame
        v_vec = np.array([self.vx, self.vy, self.vz])
        speed = np.linalg.norm(v_vec)
        if speed < 0.01: # If stationary or very slow, no aero forces in specific directions
            drag_fx, drag_fy, drag_fz = 0,0,0
            lift_fx, lift_fy, lift_fz = 0,0,0 # Lift is more complex when stationary
            lift_fy = lift # Simplified: lift acts mostly upwards when slow
        else:
            v_dir = v_vec / speed
            # Drag force vector (opposite to velocity)
            drag_f_vec = -drag * v_dir
            drag_fx, drag_fy, drag_fz = drag_f_vec[0], drag_f_vec[1], drag_f_vec[2]

            # Lift force vector (more complex)
            # Perpendicular to velocity and aircraft's lateral (X_body) axis.
            # X_body_world = R_bw * [1,0,0]^T
            # Y_body_world = R_bw * [0,1,0]^T (Lift direction in body frame)
            # Z_body_world = R_bw * [0,0,1]^T
            
            # Simplified lift: acts mostly upwards relative to aircraft's wings
            # For a level flight, lift is mostly +Y world.
            # With roll, lift vector tilts. With pitch, it has forward/backward component.
            # Lift acts along aircraft's Y_body axis, rotated by roll, then decomposed.
            lift_x_body_component = lift * math.sin(math.radians(self.roll)) 
            lift_y_body_component = lift * math.cos(math.radians(self.roll))

            # Now rotate these components by pitch and yaw to world frame
            # This is still a simplification. True lift vector is perpendicular to relative wind.
            # Assume lift vector is (0, L, 0) in a coordinate system aligned with velocity and roll.
            # Then transform this to world. For now:
            lift_fx = lift_y_body_component * math.sin(math.radians(self.pitch)) * math.sin(math.radians(self.yaw)) - \
                      lift_x_body_component * math.cos(math.radians(self.yaw))
            lift_fy = lift_y_body_component * math.cos(math.radians(self.pitch))
            lift_fz = lift_y_body_component * math.sin(math.radians(self.pitch)) * math.cos(math.radians(self.yaw)) + \
                      lift_x_body_component * math.sin(math.radians(self.yaw))


        # Wind forces (applied directly in world frame)
        # Using the formula from before, but ensure it's applied as force
        # F_wind = 0.5 * rho * V_wind^2 * C_d_wind * A_frontal (very simplified)
        # For now, just add wind components to velocity change directly as before, or calculate a drag due to wind.
        # Let's use previous simplified wind effect on velocity directly, rather than force here.
        wind_force_x = weather.wind_speed * math.cos(math.radians(weather.wind_direction)) * 0.1 * current_mass # Scaled to be like an acceleration
        wind_force_z = weather.wind_speed * math.sin(math.radians(weather.wind_direction)) * 0.1 * current_mass

        # Total forces in world coordinates
        total_fx = thrust_fx + drag_fx + lift_fx + wind_force_x
        total_fy = thrust_fy + drag_fy + lift_fy + gravity
        total_fz = thrust_fz + drag_fz + lift_fz + wind_force_z
        
        # --- Torques and Rotational Motion ---
        # Simplified: directly control pitch, roll, yaw rates via player input
        # A proper model would use moments from control surfaces.
        # Max rotation rates from config, scaled by effectiveness
        max_pitch_rate_cfg = self.config.turn_rate * 2 # Heuristic
        max_roll_rate_cfg = self.config.turn_rate * 3
        max_yaw_rate_cfg = self.config.turn_rate * 0.5
        
        # Player inputs (conceptual, should come from handle_input)
        # Let's assume self.pitch_input, self.roll_input, self.yaw_input are {-1, 0, 1}
        # These are set by the FlightSimulator's handle_input logic when it modifies rates.

        # Damping: tendency to return to neutral rotational rates
        damping_factor = 0.5 # Lower is more damping
        self.pitch_rate *= (1 - damping_factor * dt)
        self.roll_rate *= (1 - damping_factor * dt)
        self.yaw_rate *= (1 - damping_factor * dt)
        
        # Apply changes to pitch, roll, yaw
        self.pitch += self.pitch_rate * dt
        self.roll += self.roll_rate * dt
        self.yaw = (self.yaw + self.yaw_rate * dt) % 360

        # Limit pitch and roll
        self.pitch = max(-90, min(90, self.pitch))
        self.roll = ((self.roll + 180) % 360) - 180 # Keep roll in -180 to 180 range

        # --- Update Velocities and Positions ---
        ax = total_fx / current_mass
        ay = total_fy / current_mass
        az = total_fz / current_mass
        
        self.vx += ax * dt
        self.vy += ay * dt
        self.vz += az * dt

        # Store touchdown Gs
        if self.y > 0 and (self.y + self.vy * dt) <= 0: # About to touch down
            self.touchdown_vertical_speed_mps = self.vy # Negative for descent

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        # Calculate G-force (simplified: vertical acceleration + centripetal for turns)
        # Vertical G
        g_vertical = (ay - (-9.81)) / 9.81 if current_mass > 0 else 1.0
        # Centripetal G (from yaw_rate / roll induced turn)
        # V_horizontal^2 / R.  R = V_horizontal / omega_yaw.  So G_lat = omega_yaw * V_horizontal / 9.81
        # omega_yaw_rad_s = math.radians(self.yaw_rate)
        # v_horizontal = math.sqrt(self.vx**2 + self.vz**2)
        # g_lateral = abs(omega_yaw_rad_s * v_horizontal) / 9.81 if speed > 1 else 0
        # self.current_g_force = math.sqrt(g_vertical**2 + g_lateral**2) # Vector sum
        self.current_g_force = abs(g_vertical) # Simpler for now: focus on vertical Gs

        if self.current_g_force > self.config.max_g_force and not self.on_ground:
            damage = (self.current_g_force - self.config.max_g_force) * 5 * dt # Damage per second
            self.structural_integrity = max(0, self.structural_integrity - damage)
            if self.structural_integrity <= 0 and not self.crashed:
                self.crashed = True
                print("CRASH: Structural failure due to Over-G")


    def update_autopilot(self, dt, current_speed_mps):
        if not self.autopilot_on or self.crashed: return

        # Altitude Hold
        if self.ap_target_altitude is not None:
            alt_error = self.ap_target_altitude - self.y
            # Proportional control for pitch to correct altitude
            # Target vertical speed based on error
            target_vy = np.clip(alt_error * 0.05, -self.config.climb_rate / 2, self.config.climb_rate / 2) # m/s
            current_vy_error = target_vy - self.vy
            # Pitch adjustment (simplified) - needs to be much more sophisticated (PID controller)
            pitch_command = np.clip(current_vy_error * 0.1, -5, 5) # Desired pitch change in degrees
            self.pitch = np.clip(self.pitch + pitch_command * dt * 10, -20, 20) # Apply with smoothing

        # Heading Hold
        if self.ap_target_heading is not None:
            heading_error = (self.ap_target_heading - self.yaw + 540) % 360 - 180 # Error between -180 and 180
            # Proportional control for roll to correct heading
            # Target roll angle based on error, max 30 deg bank
            target_roll = np.clip(heading_error * -0.5, -25, 25) # Negative due to how roll affects yaw typically
            self.roll = np.clip(self.roll + (target_roll - self.roll) * 0.1 * dt * 20, -30, 30)

        # Speed Hold (Autothrottle)
        if self.ap_target_speed is not None:
            speed_error = self.ap_target_speed - current_speed_mps
            # Proportional control for thrust
            self.thrust_input = np.clip(self.thrust_input + speed_error * 0.5, 0, 100)


    def update(self, dt, weather: Weather, sound_manager: SoundManager):
        if self.crashed:
            self.vx *= 0.8 # Friction if crashed
            self.vz *= 0.8
            self.vy =0
            return

        self.flight_time_sec += dt
        old_x, old_z = self.x, self.z

        self.update_engine_rpm(dt) # Update engine spooling

        # --- Get Environment and State ---
        air_density = 1.225 * math.exp(-self.y / 8500) # Approximation for air density
        current_speed_mps = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)

        # --- Aerodynamics ---
        lift, drag = self.calculate_aerodynamics(air_density, current_speed_mps, weather)

        # --- Propulsion ---
        # Effective thrust from engines that are not failed and have health
        total_available_thrust_factor = sum(
            (self.engine_health[i] / 100.0) for i in range(self.config.engine_count) if not self.engines_failed[i]
        ) / self.config.engine_count if self.config.engine_count > 0 else 0
        
        actual_thrust_percent = self.engine_rpm_percent if self.engine_on and self.fuel > 0 else 0
        thrust_force = (actual_thrust_percent / 100.0) * self.config.max_thrust * total_available_thrust_factor

        # --- Apply Forces and Update Motion ---
        self.apply_forces_and_torques(dt, lift, drag, thrust_force, weather)

        # --- Autopilot ---
        self.update_autopilot(dt, current_speed_mps)
        
        # --- Systems and Fuel ---
        if self.engine_on and self.config.engine_count > 0 and self.fuel > 0:
            # Fuel consumption based on actual RPM and number of working engines
            active_engines = sum(1 for failed in self.engines_failed if not failed)
            consumption_rate = self.config.fuel_consumption * (self.engine_rpm_percent / 100.0) * (active_engines / self.config.engine_count)
            fuel_consumed = consumption_rate * dt
            self.fuel = max(0, self.fuel - fuel_consumed)
            if self.fuel == 0:
                print("Fuel Empty!")
                self.engine_on = False # Or individual engines fail

        # --- Ground Interaction ---
        terrain_height = 0 # Simplified ground at y=0. TODO: Use terrain system
        if self.y <= terrain_height and not self.on_ground: # Just touched down
            self.on_ground = True
            self.y = terrain_height
            self.vy = 0 # Stop vertical motion immediately (can be bouncy in reality)
            
            # Landing score / crash check
            self.landed_successfully = False
            impact_g = abs(self.touchdown_vertical_speed_mps / 9.81) # Gs on touchdown
            print(f"Touchdown: VSpeed={self.touchdown_vertical_speed_mps:.2f} m/s ({impact_g:.2f} G), HSpeed={current_speed_mps:.2f} m/s")

            max_safe_vs_mps = -2.0 # e.g., -2 m/s (approx -400 fpm)
            max_safe_hs_mps = self.config.stall_speed_clean * 1.5

            if not self.gear_down or self.touchdown_vertical_speed_mps < (max_safe_vs_mps * 2) or \
               current_speed_mps > max_safe_hs_mps * 1.2 or self.roll > 15 or self.pitch > 10:
                self.crashed = True
                self.structural_integrity = 0
                print("CRASH: Hard landing or improper configuration.")
            else:
                self.landed_successfully = True
                # Score based on smoothness, centerline, speed
                score = 100
                score -= min(50, abs(self.touchdown_vertical_speed_mps - (-0.5)) * 20) # Ideal vs -0.5 m/s
                score -= min(30, abs(current_speed_mps - self.config.stall_speed_clean * 1.1) * 2) # Ideal speed
                score -= min(20, abs(self.roll) * 2) # Roll on touchdown
                self.landing_score = max(0, score)
                print(f"Successful Landing! Score: {self.landing_score:.0f}")

        if self.on_ground:
            self.y = terrain_height # Ensure it stays on ground
            self.vy = 0
            self.pitch_rate *= 0.5 # Dampen rotations on ground
            self.roll_rate *= 0.1 

            # Ground friction & braking
            friction_coeff = 0.02 # Rolling friction
            if self.brakes_input > 0:
                friction_coeff += self.brakes_input * (0.8 if current_speed_mps > 10 else 0.3) # Brakes more effective at speed
            
            # Apply friction to vx and vz (speed in x-z plane)
            horizontal_speed = math.sqrt(self.vx**2 + self.vz**2)
            if horizontal_speed > 0.01:
                friction_deceleration = friction_coeff * 9.81
                # Deceleration should be capped by current speed
                decel_this_frame = min(friction_deceleration * dt, horizontal_speed)
                self.vx -= (self.vx / horizontal_speed) * decel_this_frame
                self.vz -= (self.vz / horizontal_speed) * decel_this_frame
            else:
                self.vx, self.vz = 0,0 # Stop if very slow
            
            # Nose-wheel steering (rudder input becomes steering)
            # This is already handled by yaw_rate input, but could be made specific.
            if abs(self.roll) > 30: # Wing strike on ground
                if not self.crashed: print("CRASH: Wing strike on ground!")
                self.crashed = True


        # --- Warnings ---
        if current_speed_mps > self.config.max_speed * 0.95 and not self.overspeed_warning_active:
            self.overspeed_warning_active = True
            sound_manager.play_warning_beep(frequency=1200, duration=0.5)
        elif current_speed_mps < self.config.max_speed * 0.9:
            self.overspeed_warning_active = False

        if self.stall_warning_active:
            sound_manager.play_sound('stall_warning') # Plays its own beep if file not found

        # --- Update Distance Traveled ---
        dx = self.x - old_x
        dz = self.z - old_z
        self.distance_traveled_m += math.sqrt(dx**2 + dz**2)

        # --- Final checks ---
        if self.y > self.config.service_ceiling * 1.2 and not self.crashed: # Way above service ceiling
             print("CRASH: Exceeded maximum altitude significantly.")
             self.crashed = True # Hypoxia, structural limits etc.
        if self.structural_integrity <=0 and not self.crashed:
            print("CRASH: Aircraft disintegrated.")
            self.crashed = True
            
    def set_flaps(self, direction): # 1 for down, -1 for up
        new_setting = self.flaps_setting + direction
        if 0 <= new_setting <= self.flaps_max_setting:
            self.flaps_setting = new_setting
            print(f"Flaps: {self.get_flaps_deflection()} degrees (Setting {self.flaps_setting})")
            # sound_manager.play_sound("flaps_move") # Add a sound for flap movement

    def toggle_gear(self, sound_manager: SoundManager):
        # Simple speed restriction for gear
        current_speed_mps = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2)
        gear_operating_speed_mps = self.config.stall_speed_clean * 1.8 # Example Vlo
        if current_speed_mps > gear_operating_speed_mps:
            print(f"Cannot operate gear above {gear_operating_speed_mps:.0f} m/s!")
            sound_manager.play_warning_beep(frequency=1000, duration=0.3)
            return

        self.gear_down = not self.gear_down
        if self.gear_down:
            sound_manager.play_sound("gear_down")
            print("Gear: DOWN")
        else:
            sound_manager.play_sound("gear_up")
            print("Gear: UP")
    
    def get_nav_display_info(self):
        if self.nav_mode_active and self.waypoints and self.current_waypoint_index < len(self.waypoints):
            wp = self.waypoints[self.current_waypoint_index]
            dx = wp.x - self.x
            dz = wp.z - (-self.z) # Assuming world Z is North, aircraft Z is forward. Check consistency.
                               # Let's assume standard math coordinates: +X East, +Z North
                               # Pygame screen Y is down. My world Y is up (altitude).
                               # My world Z seems to be depth into screen if using basic projection.
                               # For HSI, usually 0 deg is North (+Z world). Aircraft yaw 0 is North.
                               # So if aircraft is at (x, z_aircraft) and waypoint (wx, wz_wp)
                               # dx = wx - x_aircraft
                               # dz = wz_wp - z_aircraft (This is standard for bearing calc if Z is North)

            # Correcting dz based on common convention if needed:
            # In many 3D graphics systems, +Z is "into the screen" or "forward".
            # If my world Z is "depth", then for North = +Z_world:
            dz_nav = wp.z - self.z # Assuming positive Z is North in world coords

            distance_m = math.sqrt(dx**2 + dz_nav**2)
            
            # Bearing to waypoint (degrees from North)
            bearing_rad = math.atan2(dx, dz_nav) # dx is Easting, dz is Northing
            bearing_deg = (math.degrees(bearing_rad) + 360) % 360
            
            # Course To Steer (CTS) / Desired Track
            desired_track_deg = bearing_deg
            
            # Cross Track Error (XTE) - complex, simplified: use heading error for now
            # True XTE needs current track and desired track.
            current_track_deg = (math.degrees(math.atan2(self.vx, self.vz)) + 360) % 360 if math.sqrt(self.vx**2 + self.vz**2) > 1 else self.yaw
            
            track_error_deg = (desired_track_deg - current_track_deg + 540) % 360 - 180

            return {
                "wp_name": wp.name,
                "distance_nm": distance_m / 1852.0, # Meters to Nautical Miles
                "bearing_deg": bearing_deg,
                "desired_track_deg": desired_track_deg,
                "track_error_deg": track_error_deg, # How many degrees left/right of desired track
                "altitude_ft": wp.altitude * 3.28084,
                "current_alt_ft": self.y * 3.28084,
                "altitude_error_ft": (wp.altitude - self.y) * 3.28084
            }
        return None


class Camera:
    def __init__(self):
        self.x = 0
        self.y = 100 # Camera's altitude
        self.z = -200 # Camera's Z position (often behind aircraft)
        
        self.target_x = 0
        self.target_y = 0
        self.target_z = 0
        
        self.fov_y_deg = 60 # Vertical field of view
        self.aspect_ratio = WIDTH / HEIGHT
        self.near_clip = 1.0
        self.far_clip = 20000.0

        self.distance = 20 # Distance from aircraft for follow cams
        self.orbit_angle_h_deg = 0 # Horizontal orbit (yaw)
        self.orbit_angle_v_deg = 20 # Vertical orbit (pitch)
        
        # Camera modes: "cockpit", "follow_basic", "follow_mouse_orbit", "external_fixed_mouse_orbit"
        self.mode = "follow_mouse_orbit" 
        self.smooth_factor = 0.05 # Lower is smoother

        # For mouse orbit
        self.is_mouse_orbiting = False
        self.last_mouse_pos: Optional[Tuple[int,int]] = None


    def update(self, aircraft: Aircraft, dt):
        # Target is always the aircraft's CG
        self.target_x = aircraft.x
        self.target_y = aircraft.y 
        self.target_z = aircraft.z

        # Calculate desired camera position based on mode
        desired_cam_x, desired_cam_y, desired_cam_z = self.x, self.y, self.z

        if self.mode == "cockpit":
            # Position slightly forward and up from aircraft CG, looking forward
            # Rotation is aircraft's rotation
            # Actual view direction handled by projection matrix relative to aircraft orientation
            offset_forward = 0.5 # Small offset forward for camera position within cockpit
            offset_up = 0.8 # Vertical offset for pilot's eye level
            
            # Camera orientation matches aircraft
            self.cam_yaw_deg = aircraft.yaw
            self.cam_pitch_deg = aircraft.pitch
            self.cam_roll_deg = aircraft.roll # Usually not applied to camera directly, but to view transform

            # Position camera relative to aircraft's local axes
            # Simplified: position at aircraft CG, view matrix will handle orientation.
            # If a cockpit model is drawn, camera is fixed relative to it.
            desired_cam_x = aircraft.x + offset_forward * math.cos(math.radians(aircraft.pitch)) * math.sin(math.radians(aircraft.yaw))
            desired_cam_y = aircraft.y + offset_up # Add fixed vertical offset for eye height
            desired_cam_z = aircraft.z + offset_forward * math.cos(math.radians(aircraft.pitch)) * math.cos(math.radians(aircraft.yaw))
           
            # Target is far in front of aircraft
            look_distance = 1000
            self.target_x = desired_cam_x + look_distance * math.cos(math.radians(self.cam_pitch_deg)) * math.sin(math.radians(self.cam_yaw_deg))
            self.target_y = desired_cam_y + look_distance * math.sin(math.radians(self.cam_pitch_deg))
            self.target_z = desired_cam_z + look_distance * math.cos(math.radians(self.cam_pitch_deg)) * math.cos(math.radians(self.cam_yaw_deg))


        elif "follow" in self.mode or "external" in self.mode:
            # Calculate camera position based on orbit angles and distance around aircraft
            # Convert orbit angles to radians
            orbit_h_rad = math.radians(self.orbit_angle_h_deg + aircraft.yaw) # Relative to aircraft yaw
            orbit_v_rad = math.radians(self.orbit_angle_v_deg)

            offset_x = self.distance * math.cos(orbit_v_rad) * math.sin(orbit_h_rad)
            offset_y = self.distance * math.sin(orbit_v_rad)
            offset_z = self.distance * math.cos(orbit_v_rad) * math.cos(orbit_h_rad)
            
            desired_cam_x = aircraft.x - offset_x # Camera is behind if orbit_h_rad makes sin negative
            desired_cam_y = aircraft.y + offset_y
            desired_cam_z = aircraft.z - offset_z # And cos negative

            # Camera always looks at the aircraft
            self.target_x = aircraft.x
            self.target_y = aircraft.y
            self.target_z = aircraft.z

        # Smoothly interpolate to desired position
        self.x += (desired_cam_x - self.x) * self.smooth_factor
        self.y += (desired_cam_y - self.y) * self.smooth_factor
        self.z += (desired_cam_z - self.z) * self.smooth_factor


    def handle_mouse_input(self, event, aircraft: Aircraft):
        if "mouse_orbit" not in self.mode:
            self.is_mouse_orbiting = False
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3: # Right mouse button
                self.is_mouse_orbiting = True
                self.last_mouse_pos = event.pos
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 3:
                self.is_mouse_orbiting = False
                self.last_mouse_pos = None
        elif event.type == pygame.MOUSEMOTION:
            if self.is_mouse_orbiting and self.last_mouse_pos:
                dx = event.pos[0] - self.last_mouse_pos[0]
                dy = event.pos[1] - self.last_mouse_pos[1]
                
                self.orbit_angle_h_deg -= dx * 0.5  # Sensitivity
                self.orbit_angle_v_deg = np.clip(self.orbit_angle_v_deg - dy * 0.5, -80, 80)
                self.last_mouse_pos = event.pos
        
        if event.type == pygame.MOUSEWHEEL: # Zoom
            self.distance = np.clip(self.distance - event.y * 2, 5, 200) # event.y is scroll amount


    def get_view_matrix(self):
        # Returns a 4x4 view matrix (camera transform)
        # This is complex. For now, the renderer will use camera x,y,z and target_x,y,z
        # In cockpit mode, the view matrix would be inverse of aircraft's world matrix.
        # Simplified lookAt functionality will be implicitly handled in world_to_screen.
        # A full view matrix requires matrix math (numpy).
        
        # If in cockpit mode, camera orientation matches aircraft.
        # We need to compute rotation matrix for camera.
        # Yaw, Pitch, Roll for camera (cam_yaw, cam_pitch, cam_roll)
        if self.mode == "cockpit":
            # In cockpit view, the camera's orientation IS the aircraft's orientation
            # The "target" is just "straight ahead" from the aircraft's perspective
            # The view matrix calculation later will use these directly.
            # The self.target_x,y,z are set correctly in update() for cockpit.
            pass # Target and position are already set. Renderer will use these.
        
        # For other modes, camera looks at aircraft. Target is aircraft.
        # Position is calculated based on orbit.
        # Renderer will use self.x,y,z (camera pos) and self.target_x,y,z (aircraft pos)

        # The renderer will effectively implement gluLookAt functionality.
        # We don't explicitly return a matrix here for this simplified model.
        # The renderer.world_to_screen_advanced will compute it.
        pass


class Terrain(Terrain): # Inherit and extend
    def __init__(self):
        super().__init__()
        # Additional terrain features
        self.trees = []
        self.generate_trees()

    def generate_airports(self): # Override to add more details
        self.airports = []
        airport_data = [
            {"x": 0, "z": 0, "elevation": 0, "name": "MAIN INTL (KSEA)", "rwy_len": 3000, "rwy_width": 45, "rwy_hdg": 160},
            {"x": 8000, "z": 5000, "elevation": 150, "name": "MOUNTAIN FIELD (KMWF)", "rwy_len": 1500, "rwy_width": 30, "rwy_hdg": 90},
            {"x": -6000, "z": -8000, "elevation": 20, "name": "COASTAL STRIP (KCTS)", "rwy_len": 1000, "rwy_width": 25, "rwy_hdg": 300},
            {"x": 12000, "z": -3000, "elevation": 300, "name": "HIGHLAND BASE (KHBS)", "rwy_len": 2000, "rwy_width": 40, "rwy_hdg": 30}
        ]
        for ap_data in airport_data:
            self.airports.append({
                'x': ap_data['x'], 'z': ap_data['z'], 'elevation': ap_data['elevation'], 
                'name': ap_data['name'],
                'runway_length': ap_data['rwy_len'],
                'runway_width': ap_data['rwy_width'],
                'runway_heading': ap_data['rwy_hdg'], # Degrees from North
                'has_ils': random.choice([True, False]),
                'has_lights': True
            })
    
    def generate_trees(self, count=200):
        self.trees = []
        for _ in range(count):
            x = random.uniform(-10000, 10000)
            z = random.uniform(-10000, 10000)
            # Avoid placing trees on airport runways
            on_runway = False
            for airport in self.airports:
                if airport['x'] - airport['runway_length']/2 < x < airport['x'] + airport['runway_length']/2 and \
                   airport['z'] - airport['runway_width']*5 < z < airport['z'] + airport['runway_width']*5 : # Wider check for airport area
                    on_runway = True
                    break
            if not on_runway:
                 base_height = self.get_height_at(x, z) # Get terrain height
                 tree_height = random.uniform(5, 20)
                 self.trees.append({'x': x, 'y': base_height + tree_height/2, 'z': z, 'height': tree_height, 'radius': random.uniform(2,5)})


# --- Button Class for UI ---
class Button:
    def __init__(self, x, y, width, height, text, callback, font, color=GRAY, hover_color=LIGHT_GRAY, text_color=WHITE):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.font = font
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.is_hovered = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.is_hovered:
                if self.callback:
                    self.callback()
                    return True # Event handled
        return False

    def draw(self, surface):
        color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(surface, color, self.rect)
        pygame.draw.rect(surface, DARK_GRAY, self.rect, 2) # Border
        
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font_small = pygame.font.Font(None, 20)
        self.font_medium = pygame.font.Font(None, 28)
        self.font_large = pygame.font.Font(None, 48)
        self.font_hud = pygame.font.SysFont("Consolas", 22) # Monospaced for HUD
        self.font_hud_large = pygame.font.SysFont("Consolas", 30)

        self.cockpit_overlay_img = None
        try:
            self.cockpit_overlay_img = pygame.image.load("cockpit_overlay.png").convert_alpha()
            self.cockpit_overlay_img = pygame.transform.scale(self.cockpit_overlay_img, (WIDTH, HEIGHT))
        except pygame.error:
            print("Warning: cockpit_overlay.png not found. Using basic frame.")

    def project_point_3d_to_2d(self, x, y, z, camera: Camera) -> Optional[Tuple[int, int, float]]:
        # World to Camera coordinates
        # Vector from camera to point
        dx, dy, dz = x - camera.x, y - camera.y, z - camera.z

        # Rotate point relative to camera orientation (if camera itself rotates, like in cockpit view)
        # For simplicity, assume camera's axes are aligned with world axes, but it looks at target.
        # This is effectively part of creating the View matrix.
        
        # For a "lookAt" camera:
        # 1. Compute camera basis vectors (forward, up, right)
        fwd = np.array([camera.target_x - camera.x, camera.target_y - camera.y, camera.target_z - camera.z])
        fwd_norm = np.linalg.norm(fwd)
        if fwd_norm < 1e-6: return None # Camera and target too close
        fwd = fwd / fwd_norm

        # Assume world up is (0,1,0). If fwd is (0,1,0) or (0,-1,0), choose a different temp_up.
        temp_up = np.array([0,1,0])
        if abs(np.dot(fwd, temp_up)) > 0.999: temp_up = np.array([0,0,1]) # if fwd is colinear with Y, use Z for temp_up

        right = np.cross(fwd, temp_up)
        right_norm = np.linalg.norm(right)
        if right_norm < 1e-6: return None 
        right = right / right_norm
        
        up = np.cross(right, fwd) # Recalculate up to ensure orthogonality

        # Point relative to camera origin
        p_rel = np.array([dx, dy, dz])

        # Transform point to camera space (coords relative to camera's axes)
        # This is P_camera = M_view * P_world
        # M_view involves inverse of camera's world rotation and translation.
        # Simpler: project p_rel onto camera's basis vectors
        x_cam = np.dot(p_rel, right)
        y_cam = np.dot(p_rel, up)
        z_cam = np.dot(p_rel, fwd) # This is depth in camera's view direction

        if z_cam < camera.near_clip or z_cam > camera.far_clip: # Depth culling
            return None

        # Perspective Projection
        # Screen coordinates are typically (-1, 1) for x and y after projection.
        # tan(fov_y_rad / 2) = (screen_height / 2) / focal_length_z
        # screen_y = y_cam / (z_cam * tan(fov_y_rad / 2))
        # screen_x = x_cam / (z_cam * tan(fov_x_rad / 2))
        # focal_y = 1 / math.tan(math.radians(camera.fov_y_deg) / 2)
        # focal_x = focal_y / camera.aspect_ratio (or focal_y * camera.aspect_ratio, depending on fov_y definition)

        # Simpler perspective scaling based on FOV (approximating focal length)
        # d = 1 / tan(fov/2).  x' = x * d / z, y' = y * d / z
        # For vertical FOV:
        scale_factor = (HEIGHT / 2) / math.tan(math.radians(camera.fov_y_deg) / 2) if z_cam > 0 else 10000

        screen_x_ndc = (x_cam * scale_factor) / z_cam  # Normalized device coordinates (-H/2 to H/2 range for y)
        screen_y_ndc = (y_cam * scale_factor) / z_cam  # (scaled by aspect for x later)

        # Convert NDC to screen pixels
        # From [-W/2, W/2] and [-H/2, H/2] (approx) to [0, W] and [0, H]
        # screen_x = (screen_x_ndc * camera.aspect_ratio) + WIDTH / 2 # if ndc was proportional to height
        screen_x = (screen_x_ndc / camera.aspect_ratio) + WIDTH / 2 # if x_cam was true world units scaled
        screen_y = -screen_y_ndc + HEIGHT / 2 # Y is inverted in screen coords

        return int(screen_x), int(screen_y), z_cam # Return depth for Z-buffering/scaling

    def draw_horizon_and_sky(self, aircraft: Aircraft, camera: Camera):
        # Sky gradient
        horizon_y_center_screen = HEIGHT / 2 # Default for level camera
        
        # Adjust horizon based on camera pitch relative to world
        # If camera always looks at aircraft from outside, its own pitch/roll is complex.
        # Simpler: if aircraft is source of view (cockpit), use aircraft pitch/roll
        if camera.mode == "cockpit":
            # Convert aircraft pitch and roll to screen displacement for horizon
            # Pitch shifts horizon line up/down
            # Roll rotates the horizon line
            # TODO: This needs proper 3D math for horizon projection
            
            # Simplified sky/ground based on aircraft attitude (for ADI-like background)
            # This is NOT a true 3D horizon, but a representation.
            # A true 3D horizon needs to project points at infinity.
            
            # For now, a static skybox, or the ADI handles this.
            # Let's draw a basic sky and ground
            self.screen.fill(DARK_BLUE) # Upper sky
            pygame.draw.rect(self.screen, BLUE, (0, HEIGHT * 0.3, WIDTH, HEIGHT * 0.7)) # Lower sky
            pygame.draw.rect(self.screen, DARK_GREEN, (0, HEIGHT / 2 + aircraft.pitch * 5 , WIDTH, HEIGHT / 2 - aircraft.pitch * 5)) # Ground
            # This is a very rudimentary way to show pitch on the main view.

        else: # External cameras
            self.screen.fill(DARK_BLUE)
            pygame.draw.rect(self.screen, BLUE, (0, HEIGHT * 0.3, WIDTH, HEIGHT * 0.7))
            # Approximate horizon based on camera's Y and target Y
            # This is complex. A simpler approach: draw a ground plane.
            # For now, just a flat green rect for ground
            pygame.draw.rect(self.screen, DARK_GREEN, (0, HEIGHT * 0.6, WIDTH, HEIGHT * 0.4))
            # pygame.draw.line(self.screen, WHITE, (0, int(HEIGHT*0.6)), (WIDTH, int(HEIGHT*0.6)), 2)


    def rotate_point_3d(self, p, pitch_rad, yaw_rad, roll_rad):
        # Rotate around X (pitch), then Y (yaw), then Z (roll) - order matters
        px, py, pz = p[0], p[1], p[2]

        # Pitch (around X axis)
        y1 = py * math.cos(pitch_rad) - pz * math.sin(pitch_rad)
        z1 = py * math.sin(pitch_rad) + pz * math.cos(pitch_rad)
        py, pz = y1, z1
        
        # Yaw (around Y axis)
        x1 = px * math.cos(yaw_rad) + pz * math.sin(yaw_rad)
        z1 = -px * math.sin(yaw_rad) + pz * math.cos(yaw_rad)
        px, pz = x1, z1

        # Roll (around Z axis)
        x2 = px * math.cos(roll_rad) - py * math.sin(roll_rad)
        y2 = px * math.sin(roll_rad) + py * math.cos(roll_rad)
        px, py = x2, y2
        
        return (px, py, pz)

    def draw_aircraft_model(self, aircraft: Aircraft, camera: Camera):
        if camera.mode == "cockpit" and not aircraft.crashed : # Don't draw own aircraft in cockpit unless crashed (external view of wreck)
             return

        # Aircraft orientation in radians
        pitch_rad = math.radians(aircraft.pitch)
        yaw_rad = math.radians(aircraft.yaw) # Careful: typically yaw is around Y axis
        roll_rad = math.radians(aircraft.roll)   # Careful: typically roll is around Z body axis (forward)

        # Transform vertices from model space to world space
        world_vertices = []
        for v_local in aircraft.model_vertices_local:
            # 1. Rotate by aircraft's attitude
            # Order: Roll, Pitch, Yaw common for aerospace. Or Yaw, Pitch, Roll.
            # Assuming Z_body is forward, Y_body is up, X_body is right.
            # Pitch around X_body, Yaw around Y_body, Roll around Z_body.
            # For simplicity using a specific rotation sequence:
            v_rotated = self.rotate_point_3d(v_local, pitch_rad, yaw_rad, roll_rad)
            
            # 2. Translate to aircraft's world position
            v_world = (v_rotated[0] + aircraft.x, 
                       v_rotated[1] + aircraft.y, 
                       v_rotated[2] + aircraft.z)
            world_vertices.append(v_world)

        # Project world vertices to screen
        screen_points_with_depth = []
        for wx, wy, wz in world_vertices:
            pt_info = self.project_point_3d_to_2d(wx, wy, wz, camera)
            screen_points_with_depth.append(pt_info)

        # Draw lines connecting projected points
        for line_indices in aircraft.model_lines:
            p1_info = screen_points_with_depth[line_indices[0]]
            p2_info = screen_points_with_depth[line_indices[1]]

            if p1_info and p2_info:
                # Basic depth sorting for lines (draw farther lines first or adjust alpha)
                # Avg depth of line. Closer lines drawn on top / brighter.
                avg_depth = (p1_info[2] + p2_info[2]) / 2
                # Attenuate color by distance (simple fog)
                intensity = np.clip(1.0 - (avg_depth / (camera.far_clip*0.5)), 0.1, 1.0)
                color = tuple(int(c * intensity) for c in WHITE) # Aircraft color WHITE for now

                pygame.draw.line(self.screen, color, (p1_info[0], p1_info[1]), (p2_info[0], p2_info[1]), 1)

        # Draw smoke trail if needed
        if not aircraft.engine_on or any(h < 50 for h in aircraft.engine_health) or aircraft.crashed:
            # Smoke origin point (e.g., rear of fuselage) - use one of the vertices
            # For simplicity, just use aircraft CG projected, then offset
            cg_proj = self.project_point_3d_to_2d(aircraft.x, aircraft.y, aircraft.z, camera)
            if cg_proj:
                for i in range(5):
                    # Trail drifts "behind" the aircraft on screen based on its projected movement
                    # This is a visual effect, not true 3D smoke particles
                    trail_x_offset = aircraft.vx * -0.05 * i # Simplified screen offset
                    trail_z_offset = aircraft.vz * -0.05 * i
                    
                    # Project a point slightly behind the aircraft.
                    # This needs better handling for smoke in 3D space.
                    # For now, just draw near aircraft's screen pos.
                    sx, sy, _ = cg_proj
                    pygame.draw.circle(self.screen, DARK_GRAY, 
                                       (sx - i*5, sy + random.randint(-2,2) + i*2), 
                                       max(1, 4 - i))


    def draw_terrain_features(self, camera: Camera, terrain: Terrain, weather: Weather):
        # Draw airports (runways)
        for airport in terrain.airports:
            # Runway center
            ap_x, ap_y, ap_z = airport['x'], airport['elevation'], airport['z']
            
            # Runway dimensions and orientation
            length = airport['runway_length']
            width = airport['runway_width']
            heading_deg = airport['runway_heading']
            heading_rad = math.radians(heading_deg)

            # Calculate 4 corners of the runway rectangle in world space
            # Half dimensions
            hl, hw = length / 2, width / 2
            
            # Points relative to runway center, aligned with runway heading
            # (Local X along width, Local Z along length)
            corners_local = [
                (-hw, 0, hl),  # Front-left (approaching from hl)
                (hw,  0, hl),  # Front-right
                (hw,  0, -hl), # Back-right
                (-hw, 0, -hl)  # Back-left
            ]
            
            runway_corners_world = []
            for clx, cly, clz in corners_local:
                # Rotate by runway heading (around Y axis)
                rot_x = clx * math.cos(heading_rad) - clz * math.sin(heading_rad)
                rot_z = clx * math.sin(heading_rad) + clz * math.cos(heading_rad)
                # Translate to airport center and add elevation
                runway_corners_world.append( (ap_x + rot_x, ap_y, ap_z + rot_z) )

            # Project corners to screen
            screen_corners = []
            all_corners_visible = True
            for corner_world in runway_corners_world:
                pt_info = self.project_point_3d_to_2d(corner_world[0], corner_world[1], corner_world[2], camera)
                if pt_info:
                    screen_corners.append((pt_info[0], pt_info[1]))
                else:
                    all_corners_visible = False
                    break
            
            if all_corners_visible and len(screen_corners) == 4:
                # Determine color based on visibility and distance
                # Simple distance check to one corner for brightness
                _, _, depth_to_corner = self.project_point_3d_to_2d(runway_corners_world[0][0], runway_corners_world[0][1], runway_corners_world[0][2], camera)
                intensity = np.clip(1.0 - (depth_to_corner / (camera.far_clip * 0.7)), 0.2, 1.0) if depth_to_corner else 0.2
                runway_color = tuple(int(c * intensity) for c in GRAY)
                
                pygame.draw.polygon(self.screen, runway_color, screen_corners)
                pygame.draw.polygon(self.screen, tuple(int(c*0.8*intensity) for c in DARK_GRAY), screen_corners, 2) # Border

                # Airport name (if close enough)
                if depth_to_corner and depth_to_corner < 5000:
                    center_proj_info = self.project_point_3d_to_2d(ap_x, ap_y, ap_z, camera)
                    if center_proj_info:
                        name_text = self.font_small.render(airport['name'], True, WHITE)
                        self.screen.blit(name_text, (center_proj_info[0] - name_text.get_width()//2, center_proj_info[1] - 20))
        
        # Draw trees (simple cylinders/circles for now)
        # Sort trees by distance for pseudo-3D or skip if too complex
        # For simplicity, just draw them
        for tree in terrain.trees:
            # Simple culling: if tree is too far, don't draw
            dist_sq = (tree['x']-camera.x)**2 + (tree['z']-camera.z)**2
            if dist_sq > (camera.far_clip * 0.3)**2: # Only draw closer trees
                continue

            bottom_proj = self.project_point_3d_to_2d(tree['x'], tree['y'] - tree['height']/2, tree['z'], camera)
            top_proj = self.project_point_3d_to_2d(tree['x'], tree['y'] + tree['height']/2, tree['z'], camera)

            if bottom_proj and top_proj:
                bx, by, bz = bottom_proj
                tx, ty, tz = top_proj
                
                # Size of tree on screen (radius) based on distance
                screen_radius = np.clip( (tree['radius'] * 500) / bz if bz > 0 else 5, 1, 20)

                intensity = np.clip(1.0 - (bz / (camera.far_clip * 0.3)), 0.3, 1.0)
                trunk_color = tuple(int(c * intensity) for c in BROWN)
                leaves_color = tuple(int(c * intensity) for c in DARK_GREEN)

                # Trunk (line)
                pygame.draw.line(self.screen, trunk_color, (bx, by), (tx, ty), max(1, int(screen_radius / 3)))
                # Leaves (circle at top)
                pygame.draw.circle(self.screen, leaves_color, (tx, ty), int(screen_radius))


    def draw_weather_effects(self, weather: Weather, camera: Camera, aircraft: Aircraft):
        # Rain/Snow particles in 3D space around camera
        particle_count = 0
        if weather.type == WeatherType.RAIN or weather.type == WeatherType.STORM:
            particle_count = int(weather.precipitation * 50)
            particle_char = "|" # Not used directly, drawing lines
            particle_color = BLUE
            particle_length = 15
        elif weather.type == WeatherType.SNOW:
            particle_count = int(weather.precipitation * 40)
            particle_char = "*"
            particle_color = WHITE
            particle_size = 3

        if particle_count > 0:
            for _ in range(particle_count):
                # Spawn particles in a volume around the camera/aircraft
                # Relative position to aircraft
                rel_x = random.uniform(-50, 50)
                rel_y = random.uniform(-30, 30) 
                rel_z = random.uniform(-50, 50) # In front and around

                # World position of particle (simplistic: attach to moving aircraft for now)
                p_world_x = aircraft.x + rel_x
                p_world_y = aircraft.y + rel_y 
                p_world_z = aircraft.z + rel_z
                
                pt_info = self.project_point_3d_to_2d(p_world_x, p_world_y, p_world_z, camera)
                if pt_info:
                    sx, sy, depth = pt_info
                    if sx < 0 or sx > WIDTH or sy < 0 or sy > HEIGHT: continue # Off screen
                    
                    intensity = np.clip(1.0 - (depth / 500.0), 0.3, 1.0) # Fade with distance
                    final_color = tuple(int(c * intensity) for c in particle_color)

                    if weather.type == WeatherType.SNOW:
                        size = int(np.clip(particle_size * 50 / depth if depth > 0 else particle_size, 1, 5) * intensity)
                        pygame.draw.circle(self.screen, final_color, (sx, sy), size)
                    else: # Rain
                        length = int(np.clip(particle_length * 50 / depth if depth > 0 else particle_length, 2, 20)* intensity)
                        pygame.draw.line(self.screen, final_color, (sx, sy), (sx, sy + length), 1)
        
        # Fog overlay
        if weather.type == WeatherType.FOG:
            # This is screen-space fog, not volumetric.
            # For volumetric, you'd adjust color intensity of objects based on depth.
            # The project_point_3d_to_2d and drawing functions partially handle this with 'intensity'.
            # Here, add a general screen overlay if visibility is very low.
            if weather.visibility < 1000:
                alpha = np.clip( (1000 - weather.visibility) / 1000 * 200, 0, 200) # Max alpha 200
                fog_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                fog_surf.fill((LIGHT_GRAY[0], LIGHT_GRAY[1], LIGHT_GRAY[2], int(alpha)))
                self.screen.blit(fog_surf, (0,0))

        # Clouds (billboards)
        # Sort clouds by distance from camera (far to near for correct alpha blending)
        # This is computationally expensive. For now, just draw them.
        sorted_clouds = sorted(weather.cloud_particles, key=lambda p: (p['x']-camera.x)**2 + (p['y']-camera.y)**2 + (p['z']-camera.z)**2, reverse=True)

        for cloud_particle in sorted_clouds[:50]: # Limit number of clouds drawn for performance
            dist_sq = (cloud_particle['x']-camera.x)**2 + (cloud_particle['y']-camera.y)**2 + (cloud_particle['z']-camera.z)**2
            if dist_sq > camera.far_clip**2 : continue # Basic culling

            pt_info = self.project_point_3d_to_2d(cloud_particle['x'], cloud_particle['y'], cloud_particle['z'], camera)
            if pt_info:
                sx, sy, depth = pt_info
                if depth < 50 : continue # Too close, clip

                # Size on screen depends on actual size and distance
                screen_size = int(np.clip( (cloud_particle['size'] * 200) / depth if depth > 0 else 0, 5, 300 ))
                if screen_size < 5: continue # Too small to see

                alpha = np.clip(cloud_particle['opacity'] * (1 - depth / camera.far_clip) * 0.5 , 10, 100) # Opacity reduces with dist
                
                # Create a temporary surface for the cloud billboard
                cloud_surf = pygame.Surface((screen_size, screen_size), pygame.SRCALPHA)
                # Cloud color - could vary by type, or be grayish
                cloud_color_base = (200, 200, 220) if weather.type != WeatherType.STORM else (100,100,120)
                
                pygame.draw.ellipse(cloud_surf, (cloud_color_base[0], cloud_color_base[1], cloud_color_base[2], int(alpha)), 
                                    (0,0, screen_size, screen_size * 0.6)) # Elliptical clouds
                
                self.screen.blit(cloud_surf, (sx - screen_size//2, sy - (screen_size*0.6)//2))
        
        # Lightning
        if weather.type == WeatherType.STORM:
            for strike in weather.lightning_strikes:
                # Flash effect: brighten whole screen briefly
                flash_intensity = strike['intensity'] * (1 - (time.time() - strike['time']) / 0.2) # Fades out
                if flash_intensity > 0:
                    flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    flash_surf.fill((255,255,220, int(flash_intensity * 100))) # Yellowish white, alpha based on intensity
                    self.screen.blit(flash_surf, (0,0))


    def draw_attitude_indicator(self, aircraft: Aircraft, x, y, size):
        # ADI (Attitude Direction Indicator)
        center_x, center_y = x + size // 2, y + size // 2
        radius = size // 2 - 5

        # Background (sky/ground representation)
        pygame.draw.circle(self.screen, DARK_GRAY, (center_x, center_y), radius + 5) # Casing
        
        # Save current clipping region
        original_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(center_x - radius, center_y - radius, 2 * radius, 2 * radius))

        # Sky/Ground based on pitch and roll
        # Amount of pixels per degree of pitch
        pixels_per_degree_pitch = radius / 45 # Show +-45 degrees pitch in the display
        
        # Vertical shift due to pitch
        pitch_shift = aircraft.pitch * pixels_per_degree_pitch
        
        # Ground part (brown)
        ground_poly = []
        # Create a large rectangle for ground, then rotate and clip
        # Points for a horizontal line at horizon, shifted by pitch
        # Then extend downwards to cover the bottom half. Rotate this whole shape.
        # Simpler: draw a large rotated rectangle for sky, another for ground
        
        # Rotated surface for ADI display
        adi_surface = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
        adi_center = size
        
        # Sky
        pygame.draw.rect(adi_surface, BLUE, (0, 0, size*2, adi_center - pitch_shift))
        # Ground
        pygame.draw.rect(adi_surface, BROWN, (0, adi_center - pitch_shift, size*2, adi_center + pitch_shift + size))
        
        # Pitch ladder lines
        for p_line in range(-90, 91, 10): # Every 10 degrees
            if p_line == 0: continue # Horizon line
            line_y = adi_center - (p_line - aircraft.pitch) * pixels_per_degree_pitch # Relative to aircraft pitch
            
            # Only draw if visible within approx +- 45 deg view
            if abs(p_line - aircraft.pitch) < 50:
                line_width = radius * 0.3 if p_line % 30 == 0 else radius * 0.15
                pygame.draw.line(adi_surface, WHITE, (adi_center - line_width, line_y), 
                                 (adi_center + line_width, line_y), 1)
                # Add numbers for major lines (e.g. 30, 60 deg)
                if p_line != 0 and p_line % 20 == 0 :
                    num_text = self.font_small.render(str(abs(p_line)), True, WHITE)
                    adi_surface.blit(num_text, (adi_center - line_width - 20, line_y - num_text.get_height()//2))
                    adi_surface.blit(num_text, (adi_center + line_width + 5, line_y - num_text.get_height()//2))


        # Horizon line (thicker)
        horizon_y_on_surf = adi_center + aircraft.pitch * pixels_per_degree_pitch
        pygame.draw.line(adi_surface, WHITE, (adi_center - radius*0.7, horizon_y_on_surf), 
                         (adi_center + radius*0.7, horizon_y_on_surf), 3)


        rotated_adi_surf = pygame.transform.rotate(adi_surface, aircraft.roll)
        new_rect = rotated_adi_surf.get_rect(center=(center_x, center_y))
        self.screen.blit(rotated_adi_surf, new_rect.topleft)
        
        # Restore clipping region
        self.screen.set_clip(original_clip)

        # Fixed aircraft symbol (dot and wings)
        pygame.draw.circle(self.screen, YELLOW, (center_x, center_y), 3) # Center dot
        pygame.draw.line(self.screen, YELLOW, (center_x - radius * 0.3, center_y), 
                         (center_x - radius * 0.1, center_y), 2) # Left wing
        pygame.draw.line(self.screen, YELLOW, (center_x + radius * 0.1, center_y), 
                         (center_x + radius * 0.3, center_y), 2) # Right wing
        pygame.draw.line(self.screen, YELLOW, (center_x, center_y),
                         (center_x, center_y - radius * 0.15), 2) # Vertical fin part
        
        # Roll indicator scale at top
        pygame.draw.arc(self.screen, WHITE, (center_x-radius, center_y-radius, 2*radius, 2*radius), 
                        math.radians(30), math.radians(150), 2) # Arc for scale
        for angle_deg in [-60, -30, -10, -5, 0, 5, 10, 30, 60]:
            rad = math.radians(angle_deg - 90) # Offset by 90 for top alignment
            len_factor = 0.05 if angle_deg % 30 !=0 else 0.1
            start_x = center_x + (radius-radius*len_factor) * math.cos(rad)
            start_y = center_y + (radius-radius*len_factor) * math.sin(rad)
            end_x = center_x + radius * math.cos(rad)
            end_y = center_y + radius * math.sin(rad)
            pygame.draw.line(self.screen, WHITE, (start_x, start_y), (end_x, end_y), 1 if angle_deg %30 !=0 else 2)
        
        # Roll pointer
        roll_pointer_rad = math.radians(-aircraft.roll - 90) # Pointer moves opposite to roll
        pointer_x = center_x + (radius-radius*0.1) * math.cos(roll_pointer_rad)
        pointer_y = center_y + (radius-radius*0.1) * math.sin(roll_pointer_rad)
        pygame.draw.polygon(self.screen, YELLOW, [
            (pointer_x, pointer_y),
            (center_x + (radius+5) * math.cos(roll_pointer_rad - math.radians(2)), center_y + (radius+5) * math.sin(roll_pointer_rad - math.radians(2))),
            (center_x + (radius+5) * math.cos(roll_pointer_rad + math.radians(2)), center_y + (radius+5) * math.sin(roll_pointer_rad + math.radians(2))),
        ])


    def draw_horizontal_situation_indicator(self, aircraft: Aircraft, nav_info, x, y, size):
        # HSI (Horizontal Situation Indicator) / Compass
        center_x, center_y = x + size // 2, y + size // 2
        radius = size // 2 - 5

        pygame.draw.circle(self.screen, DARK_GRAY, (center_x, center_y), radius + 5) # Casing
        pygame.draw.circle(self.screen, BLACK, (center_x, center_y), radius)     # Background

        # Draw compass rose (rotates with aircraft yaw)
        for angle_deg in range(0, 360, 10):
            line_rad = math.radians(angle_deg - aircraft.yaw - 90) # -90 to align 0 deg (North) at top
            
            is_cardinal = (angle_deg % 90 == 0)
            is_intercardinal = (angle_deg % 30 == 0) # Major ticks
            
            line_len = radius * (0.15 if is_cardinal else (0.1 if is_intercardinal else 0.05))
            
            start_x = center_x + (radius - line_len) * math.cos(line_rad)
            start_y = center_y + (radius - line_len) * math.sin(line_rad)
            end_x = center_x + radius * math.cos(line_rad)
            end_y = center_y + radius * math.sin(line_rad)
            pygame.draw.line(self.screen, HUD_GREEN, (start_x, start_y), (end_x, end_y), 2 if is_cardinal else 1)

            if is_cardinal:
                label = "N" if angle_deg == 0 else "E" if angle_deg == 90 else "S" if angle_deg == 180 else "W"
                text = self.font_small.render(label, True, HUD_GREEN)
                text_x = center_x + (radius - line_len - 10) * math.cos(line_rad) - text.get_width()//2
                text_y = center_y + (radius - line_len - 10) * math.sin(line_rad) - text.get_height()//2
                self.screen.blit(text, (text_x, text_y))
            elif is_intercardinal : # Numbered ticks
                num_text = self.font_small.render(str(angle_deg//10), True, HUD_GREEN) # Show 3 for 30 deg etc.
                text_x = center_x + (radius - line_len - 10) * math.cos(line_rad) - num_text.get_width()//2
                text_y = center_y + (radius - line_len - 10) * math.sin(line_rad) - num_text.get_height()//2
                self.screen.blit(num_text, (text_x, text_y))

        # Fixed aircraft symbol (triangle pointing up)
        pygame.draw.polygon(self.screen, YELLOW, [
            (center_x, center_y - radius * 0.15),
            (center_x - radius * 0.08, center_y + radius * 0.08),
            (center_x + radius * 0.08, center_y + radius * 0.08)
        ])
        # Lubber line (fixed at top, indicates current heading)
        pygame.draw.line(self.screen, WHITE, (center_x, center_y - radius), (center_x, center_y - radius + 10), 2)


        # Heading bug (if AP heading is set)
        if aircraft.autopilot_on and aircraft.ap_target_heading is not None:
            bug_rad = math.radians(aircraft.ap_target_heading - aircraft.yaw - 90)
            bug_x = center_x + radius * math.cos(bug_rad)
            bug_y = center_y + radius * math.sin(bug_rad)
            # Simple diamond shape for bug
            pygame.draw.polygon(self.screen, CYAN, [
                (bug_x, bug_y - 5), (bug_x + 5, bug_y),
                (bug_x, bug_y + 5), (bug_x - 5, bug_y)
            ])
        
        # Nav info (CDI - Course Deviation Indicator)
        if nav_info:
            # Desired Track Bug
            dtk_rad = math.radians(nav_info['desired_track_deg'] - aircraft.yaw - 90)
            dtk_x1 = center_x + (radius * 0.9) * math.cos(dtk_rad)
            dtk_y1 = center_y + (radius * 0.9) * math.sin(dtk_rad)
            dtk_x2 = center_x + (radius * 0.95) * math.cos(dtk_rad) # Hollow bug part
            dtk_y2 = center_y + (radius * 0.95) * math.sin(dtk_rad)
            pygame.draw.line(self.screen, PURPLE, (dtk_x1, dtk_y1), (dtk_x2, dtk_y2), 3) # DTK bug

            # Course Deviation Needle
            # Max deviation shown is e.g. 10 degrees. Needle moves left/right.
            deviation_scaled = np.clip(nav_info['track_error_deg'] / 10.0, -1.0, 1.0) # Scale to -1 to 1
            needle_offset_x = deviation_scaled * (radius * 0.4) # Max offset from center
            
            # Needle points from desired track bug, towards center if on course.
            # This is a simplified CDI needle. A real one is more complex.
            # Draw line from (center_x + needle_offset_x, center_y - radius*0.7) to (center_x + needle_offset_x, center_y + radius*0.7)
            # This line needs to be rotated with the desired track.
            # For now, a simple horizontal bar moving left/right.
            needle_top_y = center_y - radius*0.5
            needle_bottom_y = center_y + radius*0.5
            pygame.draw.line(self.screen, PURPLE, 
                             (center_x + needle_offset_x, needle_top_y),
                             (center_x + needle_offset_x, needle_bottom_y), 3)
            
            # To/From indicator (not implemented, complex logic)

        # Digital Heading display
        heading_text = self.font_hud.render(f"{aircraft.yaw:03.0f}°", True, WHITE)
        self.screen.blit(heading_text, (center_x - heading_text.get_width()//2, center_y - radius - 25))


    def draw_hud(self, aircraft: Aircraft, weather: Weather, camera: Camera, nav_info):
        hud_color = HUD_GREEN
        if aircraft.crashed: hud_color = RED
        elif aircraft.stall_warning_active or aircraft.overspeed_warning_active: hud_color = HUD_AMBER
        
        # --- Left Side HUD: Speed, Altitude ---
        # Speed Tape
        speed_mps = math.sqrt(aircraft.vx**2 + aircraft.vy**2 + aircraft.vz**2)
        speed_kts = speed_mps * 1.94384 # knots
        speed_text = f"SPD {speed_kts:3.0f} KT"
        text_surf = self.font_hud_large.render(speed_text, True, hud_color)
        pygame.draw.rect(self.screen, (*BLACK, 150), (10, HEIGHT//2 - 50, text_surf.get_width()+20, 100), border_radius=5)
        self.screen.blit(text_surf, (20, HEIGHT//2 - text_surf.get_height()//2))

        # Altitude Tape
        alt_ft = aircraft.y * 3.28084 # meters to feet
        alt_text = f"ALT {alt_ft:5.0f} FT"
        text_surf = self.font_hud_large.render(alt_text, True, hud_color)
        pygame.draw.rect(self.screen, (*BLACK, 150), (WIDTH - text_surf.get_width() - 30, HEIGHT//2 - 50, text_surf.get_width()+20, 100), border_radius=5)
        self.screen.blit(text_surf, (WIDTH - text_surf.get_width() - 20, HEIGHT//2 - text_surf.get_height()//2))

        # --- Bottom Center HUD: Heading, Flight Path Vector ---
        # Basic Heading (digital)
        heading_tape_width = 300
        heading_tape_x = WIDTH//2 - heading_tape_width//2
        heading_tape_y = HEIGHT - 80
        pygame.draw.rect(self.screen, (*BLACK,150), (heading_tape_x, heading_tape_y, heading_tape_width, 50), border_radius=5)
        
        # Simple digital heading at center of tape
        hdg_val_text = self.font_hud_large.render(f"{aircraft.yaw:03.0f}°", True, hud_color)
        self.screen.blit(hdg_val_text, (WIDTH//2 - hdg_val_text.get_width()//2, heading_tape_y + 25 - hdg_val_text.get_height()//2))
        # Lubber line for heading tape
        pygame.draw.line(self.screen, WHITE, (WIDTH//2, heading_tape_y), (WIDTH//2, heading_tape_y + 10), 2)

        # --- Central HUD elements: Pitch Ladder, FPV (if cockpit view) ---
        if camera.mode == "cockpit":
            # Draw a simple Flight Path Vector (FPV) - shows where aircraft is actually going
            # Requires projecting current velocity vector.
            # For now, a simple crosshair:
            pygame.draw.line(self.screen, hud_color, (WIDTH//2 - 10, HEIGHT//2), (WIDTH//2 + 10, HEIGHT//2), 1)
            pygame.draw.line(self.screen, hud_color, (WIDTH//2, HEIGHT//2 - 10), (WIDTH//2, HEIGHT//2 + 10), 1)

            if self.cockpit_overlay_img:
                self.screen.blit(self.cockpit_overlay_img, (0,0))
            else: # Fallback simple frame
                pygame.draw.rect(self.screen, (50,50,50), (0,0,WIDTH,HEIGHT), 20) # Border for "cockpit"

        # --- Instrument Displays (ADI, HSI) ---
        adi_size = 200
        hsi_size = 200
        adi_x, adi_y = WIDTH // 2 - adi_size - 10, HEIGHT - adi_size - 90
        hsi_x, hsi_y = WIDTH // 2 + 10, HEIGHT - hsi_size - 90

        self.draw_attitude_indicator(aircraft, adi_x, adi_y, adi_size)
        self.draw_horizontal_situation_indicator(aircraft, nav_info, hsi_x, hsi_y, hsi_size)


        # --- Top Right: Status indicators ---
        status_y = 20
        def draw_status_text(text, value, unit, y_offset, color=hud_color):
            full_text = f"{text}: {value}{unit}"
            surf = self.font_hud.render(full_text, True, color)
            self.screen.blit(surf, (WIDTH - surf.get_width() - 20, y_offset))
            return y_offset + surf.get_height() + 5

        status_y = draw_status_text("THR", f"{aircraft.engine_rpm_percent:3.0f}", "%", status_y)
        status_y = draw_status_text("FUEL", f"{aircraft.fuel/3.785:3.0f}", " Gal", status_y, 
                                    RED if aircraft.fuel < aircraft.config.fuel_capacity*0.1 else hud_color) # Fuel in Gallons approx
        status_y = draw_status_text("GEAR", "DN" if aircraft.gear_down else "UP", "", status_y, 
                                    GREEN if aircraft.gear_down else (RED if speed_kts > 100 and not aircraft.gear_down else hud_color))
        status_y = draw_status_text("FLAP", f"{aircraft.get_flaps_deflection():2.0f}", "°", status_y)
        status_y = draw_status_text("TRIM", f"{aircraft.pitch_trim:2.1f}", "°", status_y)
        status_y = draw_status_text("G", f"{aircraft.current_g_force:2.1f}", "", status_y, 
                                    RED if aircraft.current_g_force > aircraft.config.max_g_force*0.8 else hud_color)

        if aircraft.autopilot_on:
            ap_text = self.font_hud.render("AP ON", True, CYAN)
            self.screen.blit(ap_text, (WIDTH - ap_text.get_width() - 20, status_y))
            status_y += ap_text.get_height() + 5
            if aircraft.ap_target_altitude is not None:
                status_y = draw_status_text("AP ALT", f"{aircraft.ap_target_altitude*3.28084:5.0f}", " FT", status_y, CYAN)
            if aircraft.ap_target_heading is not None:
                status_y = draw_status_text("AP HDG", f"{aircraft.ap_target_heading:03.0f}", "°", status_y, CYAN)
            if aircraft.ap_target_speed is not None:
                 status_y = draw_status_text("AP SPD", f"{aircraft.ap_target_speed*1.94384:3.0f}", " KT", status_y, CYAN)


        # --- Warnings (Center Top) ---
        warning_y = 20
        if aircraft.stall_warning_active:
            warn_surf = self.font_hud_large.render("STALL", True, RED)
            self.screen.blit(warn_surf, (WIDTH//2 - warn_surf.get_width()//2, warning_y))
            warning_y += warn_surf.get_height()
        if aircraft.overspeed_warning_active:
            warn_surf = self.font_hud_large.render("OVERSPEED", True, RED)
            self.screen.blit(warn_surf, (WIDTH//2 - warn_surf.get_width()//2, warning_y))
            warning_y += warn_surf.get_height()
        if not aircraft.engine_on and aircraft.type != AircraftType.GLIDER:
            warn_surf = self.font_hud_large.render("ENGINE OFF", True, RED)
            self.screen.blit(warn_surf, (WIDTH//2 - warn_surf.get_width()//2, warning_y))
            warning_y += warn_surf.get_height()
        if aircraft.structural_integrity < 30:
            warn_surf = self.font_hud_large.render(f"DAMAGE {aircraft.structural_integrity:.0f}%", True, RED)
            self.screen.blit(warn_surf, (WIDTH//2 - warn_surf.get_width()//2, warning_y))


        # Nav display (Top Left)
        if nav_info:
            nav_y = 20
            pygame.draw.rect(self.screen, (*BLACK,150), (10, nav_y, 250, 120), border_radius=5)
            nav_y += 10
            
            ni_text = self.font_hud.render(f"NAV: {nav_info['wp_name']}", True, CYAN)
            self.screen.blit(ni_text, (20, nav_y))
            nav_y += ni_text.get_height()

            ni_text = self.font_hud.render(f"DIST: {nav_info['distance_nm']:.1f} NM", True, WHITE)
            self.screen.blit(ni_text, (20, nav_y))
            nav_y += ni_text.get_height()

            ni_text = self.font_hud.render(f"BRG: {nav_info['bearing_deg']:.0f}°  DTK: {nav_info['desired_track_deg']:.0f}°", True, WHITE)
            self.screen.blit(ni_text, (20, nav_y))
            nav_y += ni_text.get_height()
            
            ni_text = self.font_hud.render(f"ALT: {nav_info['altitude_ft']:.0f} FT (ERR {nav_info['altitude_error_ft']:.0f})", True, WHITE)
            self.screen.blit(ni_text, (20, nav_y))


    def draw_main_menu(self, buttons, selected_aircraft_type):
        self.screen.fill(DARK_BLUE)
        title = self.font_large.render("Advanced Flight Simulator", True, WHITE)
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//4))

        ac_text = self.font_medium.render(f"Selected Aircraft: {selected_aircraft_type.value}", True, YELLOW)
        self.screen.blit(ac_text, (WIDTH//2 - ac_text.get_width()//2, HEIGHT//2 - 50))
        info_text = self.font_small.render("Press 'C' in menu to change aircraft, 'Enter' to start.", True, LIGHT_GRAY)
        self.screen.blit(info_text, (WIDTH//2 - info_text.get_width()//2, HEIGHT//2 - 10))


        for button in buttons:
            button.draw(self.screen)
        pygame.display.flip()

    def draw_pause_menu(self, buttons, help_visible, aircraft_controls_info):
        # Semi-transparent overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0,0))

        title = self.font_large.render("PAUSED", True, WHITE)
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//4))

        for button in buttons:
            button.draw(self.screen)
        
        if help_visible:
            help_y = HEIGHT // 2 + 20
            pygame.draw.rect(self.screen, DARK_GRAY, (WIDTH//2 - 250, help_y - 10, 500, 220), border_radius=5)
            for i, line in enumerate(aircraft_controls_info):
                txt = self.font_small.render(line, True, WHITE)
                self.screen.blit(txt, (WIDTH//2 - 240, help_y + i * 20))

        pygame.display.flip()

    def draw_debrief_screen(self, aircraft: Aircraft, buttons):
        self.screen.fill(DARK_GRAY)
        title_text = "CRASHED!" if aircraft.crashed else "Flight Ended"
        if aircraft.landed_successfully : title_text = "Landed Successfully!"
        
        title = self.font_large.render(title_text, True, RED if aircraft.crashed else GREEN)
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 50))

        stats_y = 150
        stats = [
            f"Flight Time: {aircraft.flight_time_sec:.1f} s",
            f"Distance Traveled: {aircraft.distance_traveled_m/1000:.2f} km",
            f"Max Altitude Reached: {aircraft.max_altitude_reached*3.28084:.0f} ft",
            f"Max Speed Reached: {math.sqrt(aircraft.vx**2+aircraft.vy**2+aircraft.vz**2)*1.94384:.0f} kts (at end)", # This is current speed
            f"Fuel Remaining: {aircraft.fuel/3.785:.1f} Gal",
            f"Structural Integrity: {aircraft.structural_integrity:.0f}%"
        ]
        if aircraft.landed_successfully:
            stats.append(f"Landing Vertical Speed: {aircraft.touchdown_vertical_speed_mps:.2f} m/s")
            stats.append(f"Landing Score: {aircraft.landing_score:.0f} / 100")

        for i, stat_line in enumerate(stats):
            txt = self.font_medium.render(stat_line, True, WHITE)
            self.screen.blit(txt, (WIDTH//2 - txt.get_width()//2, stats_y + i * 35))
        
        for button in buttons:
            button.draw(self.screen)
        pygame.display.flip()


class FlightSimulator:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Enhanced Flight Simulator")
        self.clock = pygame.time.Clock()
        
        self.sound_manager = SoundManager()
        self.weather = Weather()
        self.terrain = Terrain() # Uses extended Terrain
        self.camera = Camera()
        self.renderer = Renderer(self.screen)
        
        self.selected_aircraft_type = AircraftType.AIRLINER
        self.aircraft: Optional[Aircraft] = None # Initialized on game start

        self.game_state = GameState.MENU
        self.mission_type = MissionType.FREE_FLIGHT
        
        self.show_help_in_pause = False
        self.aircraft_controls_info = [
            "W/S: Pitch | A/D: Roll | Q/E: Yaw (Rudder/Steering)",
            "Shift/Ctrl: Throttle | G: Gear | F/V: Flaps",
            "B: Spoilers (toggle) | Space: Brakes (hold)",
            "[/]: Pitch Trim",
            "Tab: Autopilot Toggle | N: Nav Mode Toggle",
            "1: Cockpit Cam | 2: Follow Cam (Mouse Orbit)",
            "3: External Cam (Mouse Orbit) | R: Reset Flight",
            "P: Pause | H: Toggle Help (in Pause)",
            "C: Change Aircraft (Menu/Pause) | M: Cycle Weather (Pause)"
        ]
        self._init_buttons()

    def _init_buttons(self):
        self.menu_buttons = [
            Button(WIDTH//2 - 100, HEIGHT//2 + 50, 200, 50, "Start Flight", self.start_game, self.renderer.font_medium),
            Button(WIDTH//2 - 100, HEIGHT//2 + 120, 200, 50, "Quit", self.quit_game, self.renderer.font_medium)
        ]
        self.pause_buttons = [
            Button(WIDTH//2 - 100, HEIGHT//2 - 100, 200, 50, "Resume", self.toggle_pause, self.renderer.font_medium),
            Button(WIDTH//2 - 100, HEIGHT//2 - 30, 200, 50, "Main Menu", self.go_to_main_menu, self.renderer.font_medium),
            Button(WIDTH//2 - 100, HEIGHT//2 + 40, 200, 50, "Quit", self.quit_game, self.renderer.font_medium)
        ]
        self.debrief_buttons = [
            Button(WIDTH//2 - 100, HEIGHT - 150, 200, 50, "Main Menu", self.go_to_main_menu, self.renderer.font_medium),
            Button(WIDTH//2 - 100, HEIGHT - 80, 200, 50, "Restart Flight", self.restart_flight, self.renderer.font_medium)
        ]

    def start_game(self):
        self.aircraft = Aircraft(0, 100, 0, self.selected_aircraft_type) # Start slightly above ground
        # Setup initial waypoints for navigation testing or landing challenge
        main_airport = next((ap for ap in self.terrain.airports if "MAIN" in ap['name']), self.terrain.airports[0])
        mountain_airport = next((ap for ap in self.terrain.airports if "MOUNTAIN" in ap['name']), self.terrain.airports[1])
        
        self.aircraft.x = main_airport['x']
        self.aircraft.y = main_airport['elevation'] + 100 # Start above main airport
        self.aircraft.z = main_airport['z']
        self.aircraft.yaw = main_airport['runway_heading'] # Align with runway
        self.aircraft.on_ground = False # Explicitly airborne
        self.aircraft.gear_down = True # For takeoff or if starting on ground for landing challenge

        self.aircraft.waypoints = [
            Waypoint(main_airport['x'] + math.sin(math.radians(main_airport['runway_heading']))*5000, # 5km out on runway heading
                     main_airport['z'] + math.cos(math.radians(main_airport['runway_heading']))*5000,
                     1000, "DEP WP", "NAV"),
            Waypoint(mountain_airport['x'], mountain_airport['z'], mountain_airport['elevation'] + 300, # Approach to mountain field
                     mountain_airport['name'] + " APPR", "NAV"),
            Waypoint(mountain_airport['x'], mountain_airport['z'], mountain_airport['elevation'],
                     mountain_airport['name'], "AIRPORT")
        ]
        self.aircraft.current_waypoint_index = 0
        
        self.camera = Camera() # Reset camera
        self.camera.mode = "follow_mouse_orbit" # Default camera
        self.camera.distance = 30 if self.selected_aircraft_type == AircraftType.AIRLINER else 15
        
        self.weather.update_conditions() # Set initial weather based on type

        self.game_state = GameState.PLAYING
        self.sound_manager.enabled = True # Ensure sounds are on

    def restart_flight(self):
        self.sound_manager.stop_all_sounds()
        self.start_game() # This re-initializes aircraft and other states

    def go_to_main_menu(self):
        self.sound_manager.stop_all_sounds()
        self.sound_manager.enabled = False # Disable game sounds in menu
        self.aircraft = None
        self.game_state = GameState.MENU
        
    def quit_game(self):
        self.running = False # Set flag to exit main loop

    def toggle_pause(self):
        if self.game_state == GameState.PLAYING:
            self.game_state = GameState.PAUSED
            self.sound_manager.enabled = False # Pause game sounds
            # pygame.mixer.pause() # Alternative: pause all channels
        elif self.game_state == GameState.PAUSED:
            self.game_state = GameState.PLAYING
            self.show_help_in_pause = False # Hide help when unpausing
            self.sound_manager.enabled = True # Resume game sounds
            # pygame.mixer.unpause()

    def cycle_aircraft_type(self):
        types = list(AircraftType)
        current_idx = types.index(self.selected_aircraft_type)
        self.selected_aircraft_type = types[(current_idx + 1) % len(types)]
        if self.aircraft and self.game_state == GameState.PAUSED: # If paused in game, update current aircraft
            old_ac_state = {
                'x':self.aircraft.x, 'y':self.aircraft.y, 'z':self.aircraft.z,
                'vx':self.aircraft.vx, 'vy':self.aircraft.vy, 'vz':self.aircraft.vz,
                'pitch':self.aircraft.pitch, 'roll':self.aircraft.roll, 'yaw':self.aircraft.yaw,
                'fuel': self.aircraft.fuel # Keep some state
            }
            self.aircraft = Aircraft(old_ac_state['x'], old_ac_state['y'], old_ac_state['z'], self.selected_aircraft_type)
            # Restore some critical state if needed, e.g. self.aircraft.vx = old_ac_state['vx'] ...
            print(f"Aircraft changed to: {self.selected_aircraft_type.value}")


    def handle_input(self):
        if not self.aircraft: return

        keys = pygame.key.get_pressed()
        
        # Control inputs (these are rates of change or direct settings)
        pitch_input_rate = 0
        roll_input_rate = 0
        yaw_input_rate = 0

        # Pitch
        if keys[pygame.K_w]: pitch_input_rate = -self.aircraft.config.turn_rate * 0.5 * self.aircraft.elevator_effectiveness
        if keys[pygame.K_s]: pitch_input_rate = self.aircraft.config.turn_rate * 0.5 * self.aircraft.elevator_effectiveness
        self.aircraft.pitch_rate += pitch_input_rate * (self.clock.get_time()/1000.0)
        # Apply pitch trim directly to pitch rate or as a persistent force
        self.aircraft.pitch_rate += self.aircraft.pitch_trim * 0.05 * self.aircraft.elevator_effectiveness # Trim effect scaled

        # Roll
        if keys[pygame.K_a]: roll_input_rate = -self.aircraft.config.turn_rate * self.aircraft.aileron_effectiveness
        if keys[pygame.K_d]: roll_input_rate = self.aircraft.config.turn_rate * self.aircraft.aileron_effectiveness
        self.aircraft.roll_rate += roll_input_rate * (self.clock.get_time()/1000.0)

        # Yaw (Rudder)
        if keys[pygame.K_q]: yaw_input_rate = -self.aircraft.config.turn_rate * 0.3 * self.aircraft.rudder_effectiveness
        if keys[pygame.K_e]: yaw_input_rate = self.aircraft.config.turn_rate * 0.3 * self.aircraft.rudder_effectiveness
        self.aircraft.yaw_rate += yaw_input_rate * (self.clock.get_time()/1000.0)
        
        # Max rotation rates (deg/s)
        self.aircraft.pitch_rate = np.clip(self.aircraft.pitch_rate, -45, 45)
        self.aircraft.roll_rate = np.clip(self.aircraft.roll_rate, -90, 90)
        self.aircraft.yaw_rate = np.clip(self.aircraft.yaw_rate, -20, 20)

        # Throttle
        throttle_change_rate = 20.0 # % per second
        if keys[pygame.K_LSHIFT] or keys[pygame.K_PAGEUP]:
            self.aircraft.thrust_input = min(100, self.aircraft.thrust_input + throttle_change_rate * (self.clock.get_time()/1000.0))
        if keys[pygame.K_LCTRL] or keys[pygame.K_PAGEDOWN]:
            self.aircraft.thrust_input = max(0, self.aircraft.thrust_input - throttle_change_rate * (self.clock.get_time()/1000.0))
        if keys[pygame.K_END]: self.aircraft.thrust_input = 0 # Idle
        if keys[pygame.K_HOME]: self.aircraft.thrust_input = 100 # Full thrust
        
        # Brakes
        if keys[pygame.K_SPACE]: self.aircraft.brakes_input = 1.0
        else: self.aircraft.brakes_input = 0.0


    def handle_event(self, event):
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
                if event.key == pygame.K_m: # Cycle weather
                    current_weather_idx = list(WeatherType).index(self.weather.type)
                    self.weather.type = list(WeatherType)[(current_weather_idx + 1) % len(list(WeatherType))]
                    self.weather.update_conditions()
                    print(f"Weather changed to: {self.weather.type.value}")


        elif self.game_state == GameState.PLAYING and self.aircraft:
            self.camera.handle_mouse_input(event, self.aircraft) # Mouse camera always active in playing state
            if event.type == pygame.KEYDOWN:
                 # Landing gear
                if event.key == pygame.K_g: self.aircraft.toggle_gear(self.sound_manager)
                # Flaps
                if event.key == pygame.K_f: self.aircraft.set_flaps(1) # Flaps down
                if event.key == pygame.K_v: self.aircraft.set_flaps(-1) # Flaps up
                # Spoilers
                if event.key == pygame.K_b: self.aircraft.spoilers_deployed = not self.aircraft.spoilers_deployed
                # Pitch Trim
                if event.key == pygame.K_LEFTBRACKET: self.aircraft.pitch_trim -= 0.1
                if event.key == pygame.K_RIGHTBRACKET: self.aircraft.pitch_trim += 0.1
                self.aircraft.pitch_trim = np.clip(self.aircraft.pitch_trim, -5.0, 5.0)
                
                # Camera modes
                if event.key == pygame.K_1: self.camera.mode = "cockpit"
                if event.key == pygame.K_2: self.camera.mode = "follow_mouse_orbit"
                if event.key == pygame.K_3: self.camera.mode = "external_fixed_mouse_orbit" # Similar to follow_mouse for now
                
                # Autopilot
                if event.key == pygame.K_TAB:
                    self.aircraft.autopilot_on = not self.aircraft.autopilot_on
                    if self.aircraft.autopilot_on:
                        # Engage AP: set targets to current values
                        self.aircraft.ap_target_altitude = self.aircraft.y
                        self.aircraft.ap_target_heading = self.aircraft.yaw
                        current_speed_mps = math.sqrt(self.aircraft.vx**2 + self.aircraft.vy**2 + self.aircraft.vz**2)
                        self.aircraft.ap_target_speed = current_speed_mps
                        print("Autopilot ON")
                    else:
                        print("Autopilot OFF")
                # Nav mode
                if event.key == pygame.K_n:
                    self.aircraft.nav_mode_active = not self.aircraft.nav_mode_active
                    print(f"NAV mode {'ACTIVE' if self.aircraft.nav_mode_active else 'OFF'}")

                if event.key == pygame.K_r: # Reset flight
                     self.restart_flight()
        
        elif self.game_state == GameState.DEBRIEF:
            for btn in self.debrief_buttons: btn.handle_event(event)


        # Global key events
        if event.type == pygame.QUIT:
            self.running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.game_state == GameState.PLAYING: self.toggle_pause()
                elif self.game_state == GameState.PAUSED: self.toggle_pause() # Escape also unpauses
                elif self.game_state == GameState.MENU: self.quit_game()
                elif self.game_state == GameState.DEBRIEF: self.go_to_main_menu()
            if event.key == pygame.K_p: # Toggle pause
                if self.game_state == GameState.PLAYING or self.game_state == GameState.PAUSED:
                    self.toggle_pause()


    def update(self, dt):
        if self.game_state == GameState.PLAYING and self.aircraft:
            self.handle_input() # Continuous key presses for flight controls
            self.aircraft.update(dt, self.weather, self.sound_manager)
            self.weather.update(dt) # Weather evolves
            self.camera.update(self.aircraft, dt)
            
            self.sound_manager.play_engine_sound(self.aircraft.engine_rpm_percent, self.aircraft.type)

            if self.aircraft.crashed or (self.aircraft.on_ground and math.sqrt(self.aircraft.vx**2 + self.aircraft.vz**2) < 0.1 and self.aircraft.landed_successfully):
                # If crashed, or landed and stopped
                self.game_state = GameState.DEBRIEF
                self.sound_manager.stop_all_sounds() # Stop game sounds for debrief
                self.sound_manager.enabled = False
    
    def render(self):
        if self.game_state == GameState.MENU:
            self.renderer.draw_main_menu(self.menu_buttons, self.selected_aircraft_type)
            return

        if self.game_state == GameState.PAUSED:
            # Draw last frame of gameplay as background, then pause menu over it
            # For simplicity here, just draw pause menu on black or current screen content
            self.renderer.draw_pause_menu(self.pause_buttons, self.show_help_in_pause, self.aircraft_controls_info)
            return

        if self.game_state == GameState.DEBRIEF and self.aircraft:
            self.renderer.draw_debrief_screen(self.aircraft, self.debrief_buttons)
            return

        if not self.aircraft or self.game_state != GameState.PLAYING:
            self.screen.fill(BLACK) # Should not happen if logic is correct
            pygame.display.flip()
            return

        # --- Main Game Rendering ---
        self.renderer.draw_horizon_and_sky(self.aircraft, self.camera) # Basic sky/ground
        self.renderer.draw_terrain_features(self.camera, self.terrain, self.weather) # Airports, trees
        self.renderer.draw_aircraft_model(self.aircraft, self.camera) # Draw the player's aircraft
        self.renderer.draw_weather_effects(self.weather, self.camera, self.aircraft) # Rain, snow, fog, clouds

        nav_info_for_hud = self.aircraft.get_nav_display_info()
        self.renderer.draw_hud(self.aircraft, self.weather, self.camera, nav_info_for_hud)
        
        pygame.display.flip()
    
    def run(self):
        self.running = True
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.1) # Cap delta time to prevent physics explosion on lag

            for event in pygame.event.get():
                self.handle_event(event) # Handle discrete events first
            
            self.update(dt) # Update game state (includes continuous input handling if playing)
            self.render()   # Draw current state
        
        pygame.quit()

if __name__ == "__main__":
    # Create a dummy cockpit_overlay.png if it doesn't exist for testing
    try:
        with open("cockpit_overlay.png", "rb") as f:
            pass
    except FileNotFoundError:
        try:
            surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.rect(surf, (50,50,50,180), (0,0,WIDTH,150)) # Top bar
            pygame.draw.rect(surf, (50,50,50,180), (0,HEIGHT-100,WIDTH,100)) # Bottom bar
            pygame.draw.rect(surf, (50,50,50,180), (0,0,100,HEIGHT)) # Left bar
            pygame.draw.rect(surf, (50,50,50,180), (WIDTH-100,0,100,HEIGHT)) # Right bar
            pygame.image.save(surf, "cockpit_overlay.png")
            print("Created a dummy cockpit_overlay.png")
        except Exception as e:
            print(f"Could not create dummy cockpit_overlay.png: {e}")

    game = FlightSimulator()
    game.run()

