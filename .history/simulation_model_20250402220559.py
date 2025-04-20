import simpy
import random

RANDOM_SEED = 42
NUM_CHARGERS = 2  
SIM_TIME = 10  

def car(env, name, charging_station):
    """Car arrives, waits for a charger, charges, and then leaves."""
    print(f'{name} arrives at {env.now:.2f}')
    
    with charging_station.request() as req:
        yield req  # Wait for an available charger
        print(f'{name} starts charging at {env.now:.2f}')
        yield env.timeout(random.uniform(1, 3))  # Charging time
        print(f'{name} leaves at {env.now:.2f}')

def setup(env):
    """Creates car arrivals over time."""
    charging_station = simpy.Resource(env, capacity=NUM_CHARGERS)
    
    for i in range(5):  
        env.process(car(env, f'Car-{i}', charging_station))
        yield env.timeout(random.uniform(0.5, 2))  # Arrival interval

# Run simulation
env = simpy.Environment()  # Make sure to use simpy here
env.process(setup(env))  # Start the setup function
env.run(until=SIM_TIME)
