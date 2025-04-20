import simpy
import random
import matplotlib.pyplot as plt

# Simulation parameters
RANDOM_SEED = 42
NUM_CHARGERS = 2  
SIM_TIME = 10  

# To store the car events for plotting
arrival_times = []
departure_times = []

def car(env, name, charging_station):
    """Car arrives, waits for a charger, charges, and then leaves."""
    arrival_time = env.now
    arrival_times.append(arrival_time)  # Store arrival time
    print(f'{name} arrives at {arrival_time:.2f}')
    
    with charging_station.request() as req:
        yield req  # Wait for an available charger
        print(f'{name} starts charging at {env.now:.2f}')
        yield env.timeout(random.uniform(1, 3))  # Charging time
        departure_time = env.now
        departure_times.append(departure_time)  # Store departure time
        print(f'{name} leaves at {departure_time:.2f}')

def setup(env):
    """Creates car arrivals over time."""
    charging_station = simpy.Resource(env, capacity=NUM_CHARGERS)
    
    for i in range(5):  # 5 cars arriving
        env.process(car(env, f'Car-{i}', charging_station))
        yield env.timeout(random.uniform(0.5, 2))  # Arrival interval

# Run simulation
env = simpy.Environment()
env.process(setup(env))  # Start the setup function
env.run(until=SIM_TIME)

# Plotting 2D Visualization
plt.figure(figsize=(10, 6))
plt.scatter(arrival_times, [1] * len(arrival_times), color='blue', label='Arrival', s=100)
plt.scatter(departure_times, [2] * len(departure_times), color='red', label='Departure', s=100)

plt.axhline(y=1, color='gray', linestyle='--', label="Charging Station")
plt.axhline(y=2, color='gray', linestyle='--', label="Car Departure")

plt.title("2D Simulation: Car Charging Station")
plt.xlabel("Time")
plt.ylabel("Car Queue")
plt.legend(loc="best")

# Show the plot
plt.show()
