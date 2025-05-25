import pygraphviz as pgv
import os

# Print PATH to verify Graphviz is accessible
print("System PATH:", os.environ["PATH"])

try:
    G = pgv.AGraph(directed=True)
    G.add_node("A")
    G.add_node("B")
    G.add_edge("A", "B")
    G.layout(prog="dot")
    print("Layout successful!")
    for node in G.nodes():
        pos = node.attr['pos'].split(',')
        print(f"Node {node}: Position ({pos[0]}, {pos[1]})")
except Exception as e:
    print(f"Graphviz error: {str(e).strip() or 'Unknown error'}")
    print("Ensure Graphviz is installed and compatible with pygraphviz 1.14")
    print("Try running 'dot -V' in Command Prompt to verify Graphviz")