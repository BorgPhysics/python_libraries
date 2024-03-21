import json, os
from datetime import datetime
import networkx as nx

label_offset = 0.3
frequency_values = ['s', 'd', 'w', 'u']
color_chart = {'s': 'orange', 'd': 'green', 'w': 'skyblue', 'u': 'yellow'}
default_swimlane_directory = './swimlane_files'
notebook_keys = ['used_by', 'marker', 'freq']

# Method that determines the exact integer nodes that a vector traverses through
def get_traversed_integer_nodes(start_point, end_point):
    integer_coords = []
    print('\nstart_point:', start_point, 'end_point:', end_point)
    (x0, y0) = start_point
    (x1, y1) = end_point
    min_y = min(y0, y1)
    
    if x0 == x1:
        # Vertical slope
        max_y = max(y0, y1)
        for y in range(min_y+1, max_y):
            integer_coords.append(x0, y)
    else:
        slope = (y1-y0)  / (x1-x0)
        if slope == int(slope):
            slope = abs(int(slope))
            min_x = min(x0, x1)
            max_x = max(x0, x1)
            print('slope:', slope)
            for i, x in enumerate(range(min_x+1, max_x)):
    #             print('i,x:', i, x)
                if slope == 0:
                    # Everything is on the same row
                    integer_coords.append(x, y0)
                else:
                    integer_coords.append(x, min_y+((i+1)*slope))
                
    return integer_coords

# Method to determine number of child nodes that a node uses
def determine_children_for_parent(graph, node_name):
    children = []
    for item in graph:
        if node_name in item.get('used_by', []):
            children.append(item.get('name'))
            
    return children

# This helps to determine the length of the x-axis
def find_longest_path_from_final(graph, node_name, names_in_path=[]):  # TODO: Change names_in_path default to None and set if None.
    longest_path = []
    
    for item in graph:
        if 'used_by' not in item or node_name not in item['used_by']:
            continue
        child_name = item['name']
        # Don't recurse on items that reference theirselves in the used_by array
        if node_name == child_name or child_name in names_in_path:
            continue
            
        names_in_path.append(child_name)
        path = [child_name] + find_longest_path_from_final(graph, child_name, names_in_path=names_in_path)
        if len(path) > len(longest_path):
            longest_path = path
            
    return longest_path

def calculate_node_positions(height, num_nodes):
    if num_nodes == 1:
        positions = [(height/2)]
    else:
        positions = [(i / (num_nodes-1)) * height for i in range(num_nodes)]        
    return positions

def get_x_pos_from_lowest_parent(pos, max_width, parent_names):
    if not parent_names or len(parent_names) == 0:
        # This is a parent node
        return max_width
    else:
        # For each parent name, get its x postion and determine the lowest one
        x_pos = max_width
#         print('\nProcessing parent names for pos:', parent_names)
#         print('POS:', pos)
        for parent_name in parent_names:
            # Get the current position of the node
            parent_node = pos[parent_name]
            parent_x_pos = parent_node[0]
            if parent_x_pos > 0 and parent_x_pos < x_pos:
                x_pos = parent_x_pos                
    return x_pos-1

def load_swimlane_file(swimlane_file_name, documentation_dir):
    json_data = {}
    # This will attempt to load the existing file but will return and empty dictionary if it is not found
    json_file_name = os.path.join(documentation_dir, swimlane_file_name.replace(' ', '_'))
    if not json_file_name.endswith('.json'):
        json_file_name += '.json'
    if os.path.exists(json_file_name):
        with open(json_file_name, 'r') as file:
            json_data = json.load(file)
            file.close()
    else:
        print('Could not find the', json_file_name, 'file.')        
    return json_data

# This validates and merges two nodes to build a single, large node dictionary
def merge_node_values(build_dict, node_dict):
    # Use the existing build_dict and update it with the node_dict values but verify that there are no conflicts
    # Need to check used_by and freq.  Just leave the marker alone for now...
    build_dict_freq = build_dict.get('freq', 'u')
    node_dict_freq = node_dict.get('freq', 'u')
    # Update with the node_dict value if it's better
    if frequency_values.index(node_dict_freq) < frequency_values.index(build_dict_freq):
        build_dict['freq'] = node_dict_freq
        
    build_dict_used_by_list = build_dict.get('used_by', [])
    node_dict_used_by_list = node_dict.get('used_by', [])
    
    # Just merge them for now...
    for node_dict_used_by_item in node_dict_used_by_list:
        if node_dict_used_by_item not in build_dict_used_by_list:
            build_dict_used_by_list.append(node_dict_used_by_item)
            
    build_dict['used_by'] = build_dict_used_by_list
    return build_dict

# json_nodes are of the form [{}, {}, {}]  The nodes hae to be iterated through.
def set_colors_and_initial_node_positions(json_nodes):
    pos = {}
    node_colors = {}
    for node in json_nodes:
        node_name = node['name']
        # Set everything to -0.5, -0.5 for initial setup
        pos[node_name] = (-0.5, -0.5)
        color = color_chart.get(node.get('freq', ''), None)
        if not color:
            color = 'lightyellow'
            
        node_colors[node_name] = color        
    return pos, node_colors

def has_conflict(node_name, new_coords, pos):
    for existing_node, coords in pos.items():
        if node_name != existing_node and coords == new_coords:
            return True
    return False

def has_row_conflict(node_name, used_by, node_coords, pos):
    # Starting with the 'bottom' x_pos, loop through the records and make sure that
    # there isn't a record on that row that's between the current high and low
    (x_pos, y_pos) = node_coords
    current_high_x = None
    # First, look at just its connections to other nodes on the same row.
    for used_by_node_name in used_by:
        used_by_node_pos = pos[used_by_node_name]
        if y_pos == used_by_node_pos[1]:
            if not current_high_x:
                current_high_x = used_by_node_pos[0]
            else:
                # There are two related nodes on the same line
                return True
            
    # Second, examine other things in the row that might be in the way but only if there was already a current_high_x set for this row.
    if current_high_x:
        for existing_node, coords in pos.items():
            if y_pos == coords[1]:
                coord_x = coords[0]
                if coord_x > x_pos and coord_x < current_high_x:
                    return True                
    # Finally check for a regular conflict
    if has_conflict(node_name, (x_pos, y_pos), pos):
        return True    
    # All is well
    return False

def set_positions(pos, max_height, max_width, parent_dict, longest_parent_paths, sorted_parent_paths, base_nodes_and_used_by):
    # Work through the parent nodes from longest to shortest
#     print('SETTING POSITONS...')
#     print('\nmax_height:', max_height)
#     print('max_width:', max_width)
#     print('parent_dict:', parent_dict)
#     print('longest_parent_paths:', longest_parent_paths)
#     print('sorted_parent_paths:', sorted_parent_paths)
#     print('Initial positions:', pos)
    base_node_keys = base_nodes_and_used_by.keys()
    parent_node_positions = calculate_node_positions(max_height,len(sorted_parent_paths))
#     print('\nparent_node_positons:', parent_node_positons)
    for i, parent_node in enumerate(sorted_parent_paths):
        longest_parent_path = longest_parent_paths.get(parent_node)
        for j, node_name in enumerate(longest_parent_path):
            # Get the current position of the node
            current_node = pos[node_name]
            if current_node[0] < 0:
                # It can be set
                pos[node_name] = (max_width-j-1, parent_node_positions[i])
    
    # Now that the initial settings have been done for the longest path of each parent, examine the nodes that haven't been set
    for node_name in pos:
        node = pos[node_name]
#         print('node_name:', node_name, 'node:', node)
        if node[0] < 0:
            # Get the information that you need to set its position
            parent_names = parent_dict[node_name]
#             print('parent_names:', parent_names)
            if node_name in base_node_keys:
                # Try to set the x_pos to 0
                x_pos = 0
            else:
                x_pos = get_x_pos_from_lowest_parent(pos, max_width, parent_names)                
            y_pos = 0
            while has_conflict(node_name, (x_pos, y_pos), pos):
                y_pos += 1
                
            print('Setting', node_name, 'to', x_pos, y_pos)
            pos[node_name] = (x_pos, y_pos)
    
    # Now, examine all fo the nodes that aren't used by anything (base_node_names) to see if their connections are all on the same row.
    for node_name in base_node_keys:
        (x_pos, y_pos) = pos[node_name]
        used_by = base_nodes_and_used_by[node_name]
        while has_row_conflict(node_name, used_by, (x_pos, y_pos), pos):
            y_pos += 1
            
        pos[node_name] = (x_pos, y_pos)
        
    # TODO: Finally, we want to examine all of the integer node location that the vectors 
    # travel through and see if they pass through any assigned node positions (and how many).
    # If they pass through too many, move the offending node.  Otherwise, move the node that they pass through.
    # Loop through every node and determine the exact nodes that it traverses through.    
    
    
#     print('FINAL POSITIONS:', pos)
    return pos

def build_json_nodes(swimlane_files, documentation_dir):
    if not swimlane_files:
        # Build the list
        swimlane_files = []
        
        for file in os.listdir(documentation_dir):
            if file.endswith('.json'):
                swimlane_files.append(file)
        
        # Cleanup the file names
        build_files = []
        for file in swimlane_files:
            if not file.endswith('.json'):
                file += '.json'
            build_files.append(file)
        
    build_dictionary = {}
    for build_file in build_files:
        # Load a file
#         print(''Loading file, build_file)
        json_data = load_swimlane_file(build_file, documentation_dir)
#         formatted_nodes = json.dumps(json_data, indent=2)
#         print(formatted_nodes)
        swimlane_nodes = json_data['swimlane_nodes']
        for key in swimlane_nodes.keys():
            node_dict = swimlane_nodes[key]
            build_dict = build_dictionary.get(key, None)
            if not build_dict:
                build_dictionary[key] = node_dict
            else:
                # Need to merge them
                build_dictionary[key] = merge_node_values(build_dict, node_dict)

        formatted_nodes = json.dumps(build_dictionary, indent=2)
#         print('\n\nMERGED BUILD DICTIONARY:', formatted_nodes)
    
    # Finally, convert it to the previous array of dictionaries format
    json_nodes = []
    for key in build_dictionary.keys():
        dict_value = build_dictionary[key]
        # Add the name from the key
        dict_value['name'] = key
        json_nodes.append(dict_value)
    
    formatted_json_nodes = json.dumps(json_nodes, indent=2)
#     print('\n\nFINAL JSON NODES:', formatted_json_nodes)
    return json_nodes

def build_json_nodes_for_notebook(swimlane_files, documentation_dir):
    append_to_build_files = False    
    if not swimlane_files:
        append_to_build_files = True
        swimlane_files = []
        
    build_files = []
    # Build files are defined by the swimlane_files if they exist
    for file in swimlane_files:
        if not file.endswith('.json'):
            file += '.json'
        build_files.append(file)
    
    all_notebook_files = []
    for file in os.listdir(documentation_dir):
        if file.endswith('.json'):
            all_notebook_files.append(file)
            # Build files are comprised of all .json files in the directory if they haven't been defined by the swimlane_files variable
            if append_to_build_files:
                build_files.append(file)
    
    # Now that you have the file names for all of the files in the directory and the ones for notebooks that you care about, process them.
    build_dictionary = {}
    for filename in all_notebook_files:
        # Load all of the files
        json_data = load_swimlane_file(filename, documentation_dir)
        key = filename.replace('.json', '')
        
        if not key:
            raise Exception('The ' + filename + ' file does not have a name set.')
        
        node_dict = {notebook_key: json_data[notebook_key] for notebook_key in notebook_keys if notebook_key in json_data}
        build_dict = build_dictionary.get('name', None)
        
        # The notebook version is a little different such that it can reference top-level items that aren't described anywhere.
        # This would break later code downstream, so they need to be dynamically created here.
        node_used_by_list = node_dict.get('used_by', [])
        for node_used_by_item in node_used_by_list:
            # Put it in the build dict if it doesn't already exist
            build_item = build_dictionary.get(node_used_by_item, None)
            if not build_item:
                # Build it from scratch and save
                build_dictionary[node_used_by_item] = {'used_by':[], 'marker':'o', 'freq':'u'}
            
            if not build_dict:
                build_dictionary[key] = node_dict
            else:
                # Need to merge them
                build_dictionary[key] = merge_node_values(build_dict, node_dict)
    
    # Finally, convert it to the previous array of dictionaries format
    json_nodes = []
    for key in build_dictionary.keys():
        dict_value = build_dictionary[key]
        # Add the name from the key
        dict_value['name'] = key
        json_nodes.append(dict_value)
    
    formatted_json_nodes = json.dumps(json_nodes, indent=2)
#     print('\n\nFINAL JSON NOTEBOOK NODES:', formatted_json_nodes)
    return json_nodes

def set_final_node_and_label_positions(pos, json_nodes):
    label_pos = {}
    child_dict = {}
    parent_dict = {}
    longest_parent_paths = {}
    
    # Get the list of all names
    all_node_names = [node['name'] for node in json_nodes]
    # Get the list of all nodes that are 'used_by' another node
    names_of_nodes_using_another_node = set()
    for node in json_nodes:
        used_by_list = node.get('used_by', [])
        
        # Make sure that it's always an array of strings
        if isinstance(used_by_list, str):
            used_by_list = [used_by_list]
        
        for item in used_by_list:
            names_of_nodes_using_another_node.add(item)
    
    # Get the list of 'base' nodes that aren't using anything (never listed in any node's used_by variable)
    base_node_names = set(all_node_names) - names_of_nodes_using_another_node
    # This variable helps to determine row-level conflicts
    base_nodes_and_used_by = {}
    for node in json_nodes:
        node_name = node['name']
        if node_name in base_node_names:
            used_by_list = node.get('used_by', [])
            # Make sure that it's always an array of strings
            if isinstance(used_by_list, str):
                used_by_list = [used_by_list]
            base_nodes_and_used_by[node_name] = used_by_list
    
#     print('\nCALCULATIING HEIGHT:')
#     print('\nset(all_node_names):', set(all_node_names))
#     print('\nnames_of_nodes_using_another_node:', names_of_nodes_using_another_node)
#     print('\nbase_node_names (set(all_node_names) - names_of_nodes_using_another_node):', base_node_names)
    
    # Get the list of nodes without a used_by setting or an empty array
    final_node_names = [node['name'] for node in json_nodes if 'used_by' not in node or not node['used_by']]
    
    max_width = 0
    max_height = len(base_node_names)
    for node_name in final_node_names:
        longest_path = [node_name] + find_longest_path_from_final(json_nodes, node_name)
        longest_parent_paths[node_name] = longest_path
#         print(f"Longest path for {node_name}: {longest_path}", )
        path_length = len(longest_path)
        if path_length > max_width:
            max_width = path_length
    
    for node in json_nodes:
        node_name = node['name']
#         print('\nChecking number of children for', node_name)
        children = determine_children_for_parent(json_nodes, node_name)
        child_dict[node_name] = children
        parent_dict[node_name] = node.get('used_by', [])
#         print(f"Children for {node_name}: {children}")
        
    sorted_parent_paths = sorted(longest_parent_paths.keys(), key=lambda node: len(longest_parent_paths[node]), reverse=True)
    
    # Update the postions
    pos = set_positions(pos, max_height, max_width, parent_dict, longest_parent_paths, sorted_parent_paths, base_nodes_and_used_by)
    
    # Adjust the label positions based on the label offset and a 
    # row-based curving algorithm so that the names don't overwrite others on the same row
    center_x = max_width/2
    y_axis_shift = 0.4*max_height
    for k, (x,y) in pos.items():
        dist_from_center = abs(x - center_x)
        right_side_shift = 0.0
        if x-center_x >= 0:
            right_side_shift = label_offset
        
        y_offset = ((center_x - dist_from_center) * label_offset) + right_side_shift
        if y > y_axis_shift:
            label_pos[k] = (x, y + y_offset)
        else:
            label_pos[k] = (x, y - y_offset)
    
    return pos, label_pos

class SwimlaneBuildTool:
    
    def __init__ (self, swimlane_files=None, documentation_dir=default_swimlane_directory):
        # When initialized, this should preload all of the specified json files in the documentation directory.
        # If none are listed, then load them all from the documentation_dir and merge them.
        # In the end, you should end up with a file similar to the previous version.
        # If the documentation directory doesn't exist, throw an error
        if not os.path.exists(documentation_dir):
            raise Exception('The' + documentation_dir + ' directory does not exist!')
        
        self.json_nodes = build_json_nodes(swimlane_files, documentation_dir)
#         print('\nself.json_nodes', self.json_nodes, '\n\n')

        self.pos, self.node_colors = set_colors_and_initial_node_positions(self.json_nodes)
        self.pos, self.label_pos = set_final_node_and_label_positions(self.pos, self.json_nodes)
        
        self.json_notebook_nodes = build_json_nodes_for_notebook(swimlane_files, documentation_dir)
        self.notebook_pos, self.notebook_node_colors = set_colors_and_initial_node_positions(self.json_notebook_nodes)
#         print('\nself.notebook_pos:', self.notebook_pos)
#         print('\nself.notebook_node_colors:', self.notebook_node_colors)
        self.notebook_pos, self.notebook_label_pos = set_final_node_and_label_positions(self.notebook_pos, self.json_notebook_nodes)
        
    def get_initialized_notebook_DiGraph(self):
        return self.get_initialized_DiGraph(for_notebook=True)
    
    def get_initialized_DiGraph(self, for_notebook=False):
        # Create a directed graph
        G = nx.DiGraph()
        
        # Define nodes and edges
        node_items = self.json_nodes
        if for_notebook:
            node_items = self.json_notebook_nodes
        
        nodes = [node['name'] for node in node_items]
        edges = []
        
        for node in node_items:
            name = node.get('name', None)
            used_by = node.get('used_by', None)
            if name and used_by is not None:
                # Assume that it's an array
                for target in used_by:
                    edges.append((name, target))
            
#         print('NODES:', nodes)
#         print('EDGES:', edges)
#         if for_notebook:
#             print('NB POSITIONS:', self.notebook_pos)
#         else:
#             print('POSITIONS:', self.pos)
        
        # Add nodes and  edges to the graph
        G.add_nodes_from(nodes)
        G.add_edges_from(edges)
        return G
    
class SwimlaneDocumentation:
    def __init__(self, swimlane_file_name, notebook_name, documentation_dir=default_swimlane_directory, used_by=[], freq=None, user_name=None):
        self.user_name = user_name
        self.documentation_dir = documentation_dir
        self.swimlane_file_name = swimlane_file_name.replace(' ', '_')
        
        self.json_data = {}
        # Not sure if I'll need this variable but the method is definitely used elsewhere.
        self.existing_json_data = load_swimlane_file(self.swimlane_file_name, self.documentation_dir)
#         print('existing_json_data:', self.existing_json_data)
        
        # Make sure that the documentation directory exists
        os.makedirs(self.documentation_dir, exist_ok=True)
        
        # Make sure that its always an array of strings
        if isinstance(used_by, str):
            used_by = [used_by]
            
        self.json_data['name'] = notebook_name
        self.json_data['used_by'] = used_by
        self.json_data['notebook_loc'] = os.getcwd() 
        
        # Frequences are static, daily, weekly and unknown
        if freq and freq in frequency_values:
            self.json_data['freq'] = freq
        
        self.json_data['swimlane_nodes'] = {}
        
        self.save_file()
        
#         print('SwimlaneDocumentation notebook_name', self.notebook_name)
#         print('SwimlaneDocumentation cwd', os.getcwd())
        
    def save_file(self):
        # This just needs to save the file in its current state
        json_file_name = os.path.join(self.documentation_dir, self.swimlane_file_name.replace(' ', '_') + '.json')
        with open(json_file_name, 'w') as file:
            json.dump(self.json_data, file, indent=4)
        
    def add_node(self, name, used_by=None, marker='o', freq='u', notes=None):
        # Get the node's dictionary if it already exists.  Otherwise, default to an empty dictionare
        node_dict = self.json_data['swimlane_nodes'].get(name, {})
        existing_used_by = node_dict.get('used_by', [])
        
        if not used_by and len(existing_used_by) > 0:
            raise Exception('You attempted to set an empty used_by value on a node that has existing used_by values.  This is not allowed.')
        
        # Make sure that it's always an array of strings
        if isinstance(used_by, str):
            used_by = [used_by]
        
        if used_by:
            for elem in used_by:
                if elem not in existing_used_by:
                    existing_used_by.append(elem)
        
        node_dict['used_by'] = existing_used_by
        node_dict['marker'] = marker
        node_dict['freq'] = freq
        if notes:
            node_dict['notes'] = notes
        
        self.json_data['swimlane_nodes'][name] = node_dict
        self.save_file()
        
      # Not complete yet...
#     def load_and_document(self, message, print_to_console=False):
#         timestamp = datetime.now.strftime("%Y-%m-%d %H:%M:%S")
#         if self.user_name:
#             log_entry = f"{self.user_name} {timestamp}: {message}"
#         else:
#             log_entry = f"{timestamp}: {message}"
        
#         if print_to_console:
#             print(log_entry)
        
#         with open(self.log_file_name, "a") as log_file:
#             log_file.write(log_entry + "\n")
        
        
        
        
        
        