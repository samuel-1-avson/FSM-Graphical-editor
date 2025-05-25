import pygraphviz as pgv
import os

# Add Graphviz to PATH
graphviz_path = r"C:\Program Files\Graphviz\bin"  # Adjust based on 'where dot'
os.environ["PATH"] += os.pathsep + graphviz_path
print("Updated PATH:", os.environ["PATH"])

try:
    G = pgv.AGraph(directed=True)
    G.add_node("A")
    G.add_node("B")
    G.add_edge("A", "B")
    print(f"Graph nodes: {G.nodes()}")
    print(f"Graph edges: {G.edges()}")
    G.layout(prog="dot")
    print("Layout successful!")
    for node in G.nodes():
        pos = node.attr['pos'].split(',')
        print(f"Node {node}: Position ({pos[0]}, {pos[1]})")
except Exception as e:
    error_msg = str(e).strip() or "Could not execute Graphviz 'dot' (check PATH or compatibility)"
    print(f"Graphviz error: {error_msg}")
    print(f"Graphviz version: {os.popen('dot -V').read().strip() or 'Not found'}")
    print(f"Ensured PATH includes: {graphviz_path}")
    print("Verify with 'dot -V' in Command Prompt")
    print("Try 'conda install -c conda-forge pygraphviz=1.12'")