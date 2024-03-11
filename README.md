# python_libraries
These are a list of various python libraries that I've created

Try using the following for the display and labels:
fig, ax = plt.subplots(figsize=(15, 15))
nx.draw(G, sbt.pos, node_size=1000, node_color=[sbt.node_colors[node] for node in G.nodes], node_shape='o', font_size=8, font_color='black', font_weight='bold', arrowsize=20, connectionstyle='arc3, rad=0.1')
nx.draw_networkx_labels(G, sbt.label_pos, font_size=8, font_color='black', font_weight='bold')
