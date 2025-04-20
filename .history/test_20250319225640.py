import torch
import time

# Check if CUDA is available
if not torch.cuda.is_available():
    print("CUDA is not available. Please check your installation.")
else:
    print("CUDA is available! Running GPU stress test...")

    # Move tensors to GPU
    device = torch.device("cuda")
    size = 40000  # Large matrix size
    A = torch.randn(size, size, device=device)
    B = torch.randn(size, size, device=device)

    # Perform matrix multiplication on GPU
    start = time.time()
    C = torch.mm(A, B)
    torch.cuda.synchronize()  # Wait for computation to finish
    end = time.time()

    print(f"GPU computation completed in {end - start:.4f} seconds.")
