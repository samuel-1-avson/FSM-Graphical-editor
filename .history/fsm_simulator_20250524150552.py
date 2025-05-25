import pygraphviz as pgv
G = pgv.AGraph(directed=True)
G.add_node("A")
G.add_node("B")
G.add_edge("A", "B")
G.layout(prog="dot")
print("Layout successful!")