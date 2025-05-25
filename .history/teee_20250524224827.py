import matlab.engine

# Start MATLAB engine
eng = matlab.engine.start_matlab()

# Execute MATLAB commands
result = eng.sqrt(4.0)
print(f"Square root of 4: {result}")

# Execute MATLAB functions
eng.workspace['x'] = 5.0
eng.eval('y = x^2', nargout=0)
y = eng.workspace['y']
print(f"5 squared: {y}")

# Close the engine
eng.quit()