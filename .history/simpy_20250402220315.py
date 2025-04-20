import simpy
import random

# Simulation parameters
RANDOM_SEED = 42
NUM_CHARGERS = 2      # Number of charging stations
SIM_TIME = 10         # Simulation time in minutes

def car(env, name, charging_station):
    """Car arrives, waits for a charger, charges, and then leaves."""
    print(f'{name} arrives at {env.now:.2f}')
    
    with charging_station.request() as req:
        yield req
        print(f'{name} starts charging at {env.now:.2f}')
        yield env.timeout(random.uniform(1, 3))  # Charging time
        print(f'{name} leaves at {env.now:.2f}')

# Create environment
env = simpy.Environment()
charging_station = simpy.Resource(env, capacity=NUM_CHARGERS)

# Add cars to the simulation
for i in range(5):
    env.process(car(env, f'Car-{i}', charging_station))
    yield env.timeout(random.uniform(0.5, 2))  # Arrival interval

# Run simulation
env.run(until=SIM_TIME)
