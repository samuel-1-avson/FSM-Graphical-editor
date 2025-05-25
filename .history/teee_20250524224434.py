import matlab.engine
eng = matlab.engine.start_matlab()
print("MATLAB Engine installed successfully!")
eng.quit()