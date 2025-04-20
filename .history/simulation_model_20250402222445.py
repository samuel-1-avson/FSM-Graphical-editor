import simpy
import random
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Simulation parameters
RANDOM_SEED = 42
NUM_CHARGERS = 2  
SIM_TIME = 10  

# To store car events for plotting
arrival_times = []
departure_times = []
cars_in_station = []  # Track which cars are in the charging station
car_labels = []  # Track car labels for animation

def car(env, name, charging_station):
    """Car arrives, waits for a charger, charges, and then leaves."""
    arrival_time = env.now
    arrival_times.append(arrival_time)  # Store arrival time
    car_labels.append(name)  # Store car label for animation
    print(f'{name} arrives at {arrival_time:.2f}')
    
    with charging_station.request() as req:
        yield req  # Wait for an available charger
        cars_in_station.append((name, env.now))  # Track car's start time in the station
        print(f'{name} starts charging at {env.now:.2f}')
        yield env.timeout(random.uniform(1, 3))  # Charging time
        departure_time = env.now
        departure_times.append(departure_time)  # Store departure time
        print(f'{name} leaves at {departure_time:.2f}')
        
        # Safely remove the car from the charging station
        car_in_station = (name, env.now)
        if car_in_station in cars_in_station:
            cars_in_station.remove(car_in_station)  # Remove car from station once done

def setup(env):
    """Creates car arrivals over time."""
    charging_station = simpy.Resource(env, capacity=NUM_CHARGERS)
    
    for i in range(5):  # 5 cars arriving
        env.process(car(env, f'Car-{i}', charging_station))
        yield env.timeout(random.uniform(0.5, 2))  # Arrival interval

# Set up the environment and simulation
env = simpy.Environment()
env.process(setup(env))  # Start the setup function

# Create a figure and axes for the animation
fig, ax = plt.subplots(figsize=(10, 6))

# Initialize the plot elements
arrival_scatter = ax.scatter([], [], color='blue', label='Arrival', s=100)
departure_scatter = ax.scatter([], [],
