import pygraphviz as pgv
import os
import logging # Added for logging

logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Configure if not already configured
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


# Attempt to find Graphviz bin directory automatically or use a hardcoded path
def find_graphviz_bin():
    # Check common Program Files locations on Windows
    if os.name == 'nt':
        for pf_var in ['PROGRAMFILES', 'PROGRAMFILES(X86)']:
            program_files = os.environ.get(pf_var)
            if program_files:
                # Search for Graphviz versions (e.g., Graphviz, Graphviz\bin, Graphviz2.38\bin)
                # This is a simplified search; a more robust one might look for 'dot.exe'
                potential_paths = [
                    os.path.join(program_files, "Graphviz", "bin"),
                    os.path.join(program_files, "Graphviz2.38", "bin"), # Example old version
                    # Add more common versioned paths if known
                ]
                for path in potential_paths:
                    if os.path.isdir(path) and os.path.exists(os.path.join(path, "dot.exe")):
                        logger.info(f"Found Graphviz bin at: {path}")
                        return path
    
    # Fallback to a hardcoded path (user should adjust this if needed)
    # graphviz_hardcoded_path = r"C:\Program Files\Graphviz\bin"
    # if os.path.isdir(graphviz_hardcoded_path) and os.path.exists(os.path.join(graphviz_hardcoded_path, "dot.exe")):
    #     logger.info(f"Using hardcoded Graphviz path: {graphviz_hardcoded_path}")
    #     return graphviz_hardcoded_path
        
    logger.warning("Graphviz bin directory not automatically found. Ensure 'dot' is in PATH or configure path.")
    return None

graphviz_bin_path = find_graphviz_bin()

if graphviz_bin_path and graphviz_bin_path not in os.environ["PATH"]:
    os.environ["PATH"] += os.pathsep + graphviz_bin_path
    logger.info(f"Temporarily added {graphviz_bin_path} to PATH.")
    logger.debug(f"Updated PATH: {os.environ['PATH']}")
else:
    logger.info("Graphviz bin directory already in PATH or not found for automatic addition.")


try:
    G = pgv.AGraph(directed=True)
    G.add_node("A")
    G.add_node("B")
    G.add_edge("A", "B")
    logger.info(f"Graph nodes: {G.nodes()}")
    logger.info(f"Graph edges: {G.edges()}")
    G.layout(prog="dot") # Use 'dot' for layout
    logger.info("Layout successful!")
    for node in G.nodes():
        pos = node.attr['pos'].split(',')
        logger.info(f"Node {node}: Position ({pos[0]}, {pos[1]})")
    
    # Optional: Save the graph to a file to verify
    # output_file = "test_graph.png"
    # G.draw(output_file)
    # logger.info(f"Test graph saved to {output_file}")

except Exception as e:
    error_msg = str(e).strip() or "Could not execute Graphviz 'dot' (check PATH or compatibility)"
    logger.error(f"Graphviz error: {error_msg}", exc_info=True)
    
    # Try to get 'dot -V' output for diagnostics
    try:
        dot_version_process = os.popen('dot -V')
        dot_version_output = dot_version_process.read().strip()
        dot_version_process.close()
        logger.info(f"Graphviz version (dot -V): {dot_version_output or 'Not found or error running dot -V'}")
    except Exception as e_dot:
        logger.error(f"Error trying to get dot version: {e_dot}")

    if graphviz_bin_path: logger.info(f"Ensured PATH includes (or attempted to include): {graphviz_bin_path}")
    logger.info("Verify 'dot -V' in your system's Command Prompt/Terminal.")
    logger.info("If issues persist, consider reinstalling Graphviz and ensuring its bin directory is in the system PATH, or installing pygraphviz via conda if using Anaconda ('conda install -c conda-forge pygraphviz').")