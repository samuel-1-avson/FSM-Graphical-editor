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
departure_scatter = ax.scatter([], [], color='red', label='Departure', s=100)
charging_scatter = ax.scatter([], [], color='green', label='Charging', s=100)

ax.axhline(y=1, color='gray', linestyle='--', label="Charging Station")
ax.axhline(y=2, color='gray', linestyle='--', label="Car Departure")

ax.set_xlim(0, SIM_TIME)
ax.set_ylim(0, 3)
ax.set_title("Animated 2D Simulation: Car Charging Station")
ax.set_xlabel("Time")
ax.set_ylabel("Car Queue")
ax.legend(loc="best")

# Function to update the plot during the animation
def update(frame):
    """Update the plot elements at each frame."""
    # Filter the arrivals and departures up to the current frame
    arrival_data = [t for t in arrival_times if t <= frame]
    departure_data = [t for t in departure_times if t <= frame]
    charging_data = [t for name, t in cars_in_station if t <= frame]
    
    # Update the scatter data
    arrival_scatter.set_offsets([(t, 1) for t in arrival_data])
    departure_scatter.set_offsets([(t, 2) for t in departure_data])  # Ensure departure_data is 2D
    charging_scatter.set_offsets([(t, 1.5) for t in charging_data])
    
    return arrival_scatter, departure_scatter, charging_scatter

# Run the simulation and animate the plot
env.process(setup(env))  # Start the simulation
env.run(until=SIM_TIME)

# Set up the animation
ani = FuncAnimation(fig, update, frames=[i * 0.1 for i in range(int(SIM_TIME * 10))], interval=100, blit=True)

# Show the animation
plt.show()
