# -*- coding: utf-8 -*-
"""
Created on Tue Apr 15 11:22:12 2025

@author: sohca, ChatGPT
"""

# C E 367R converting my CSVs to shapefiles with geopandas


# NEED TO REDUCE THE SIZE OF THE NETWORK

#%%

# importing

import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point, LineString, MultiLineString
import matplotlib.pyplot as plt
# from adjustText import adjust_text
# import contextily as ctx

#%%

# reading our data

bikeshare_stations_path = 'C:/Users/sohca/OneDrive - The University of Texas at Austin/_UT Austin/2024-2025 coursework/C E-367R Sp25 - Optimization Techniques for Transportation Engineers/bikeshare_stations.shp'
intersections_path = 'C:/Users/sohca/OneDrive - The University of Texas at Austin/_UT Austin/2024-2025 coursework/C E-367R Sp25 - Optimization Techniques for Transportation Engineers/intersections.shp'
street_centerline_path = 'C:/Users/sohca/OneDrive - The University of Texas at Austin/_UT Austin/2024-2025 coursework/C E-367R Sp25 - Optimization Techniques for Transportation Engineers/street_centerline_clip1.shp'

bikeshare_stations = gpd.read_file(bikeshare_stations_path)
intersections = gpd.read_file(intersections_path)
street_centerline = gpd.read_file(street_centerline_path)

#%%

# adding an index to the intersections dataframe

intersection_id = []

for i in range(len(intersections)):
    intersection_id.append(i)

intersections.insert(35, 'intersection_id', intersection_id)

#%%

# establishing connectivity between centerlines and intersections

def get_start_point(geom):
    if isinstance(geom, LineString):
        return Point(geom.coords[0])
    elif isinstance(geom, MultiLineString):
        return Point(list(geom.geoms[0].coords)[0])
    else:
        return None

def get_end_point(geom):
    if isinstance(geom, LineString):
        return Point(geom.coords[-1])
    elif isinstance(geom, MultiLineString):
        return Point(list(geom.geoms[-1].coords)[-1])
    else:
        return None

# Step 1: Extract start and end points safely
start_points = street_centerline.geometry.apply(get_start_point)
end_points = street_centerline.geometry.apply(get_end_point)

# Step 2: Create GeoDataFrames for those points
start_gdf = gpd.GeoDataFrame(geometry=start_points, crs=street_centerline.crs)
end_gdf = gpd.GeoDataFrame(geometry=end_points, crs=street_centerline.crs)

# Step 3: Spatial join to match with intersections
start_joined = gpd.sjoin(start_gdf, intersections[['geometry', 'intersection_id']], how='left', predicate='within')
end_joined = gpd.sjoin(end_gdf, intersections[['geometry', 'intersection_id']], how='left', predicate='within')

# Step 4: Extract intersection IDs
start_node_ids = start_joined['intersection_id'].tolist()
end_node_ids = end_joined['intersection_id'].tolist()


street_centerline.insert(35, 'start_node_id', start_node_ids)
street_centerline.insert(36, 'end_node_ids', end_node_ids)

#%%

bikeshare_stations = bikeshare_stations[bikeshare_stations['kiosk_stat'] == 'active']

# Perform spatial join to get nearest intersection for each bikeshare station
stations_with_intersections = gpd.sjoin_nearest(
    bikeshare_stations,
    intersections[['geometry', 'intersection_id']],
    how='left',  # keep all bikeshare stations
    distance_col='distance_to_intersection'  # optional: to record the distance
)

# Now assign the intersection_id column back to the original GeoDataFrame
bikeshare_stations['nearest_intersection_id'] = stations_with_intersections['intersection_id']

#%%
#FIXME

# # Save street centerlines
# street_centerline.to_file("street_centerline_clip0.shp")

# # Save intersections
# intersections.to_file("intersections0.shp")

# # Save bikeshare stations
# bikeshare_stations.to_file("bikeshare_stations0.shp")


# # Convert geometry to WKT strings
# bikeshare_stations['geometry'] = bikeshare_stations.geometry.apply(lambda geom: geom.wkt)

# # Save to CSV
# bikeshare_stations.to_csv("bikeshare_stations.csv", index=False)


#%%

# creating the nodes and links lists for our network

# ex. nodes = ['Austin', 'Dallas', 'San_Antonio', 'Houston', 'Galveston', 'Corpus_Christi', 't']

nodes = intersections['intersection_id'].tolist()


directed_links = []

for i in range(len(street_centerline)):
    directed_links.append((street_centerline['start_node_id'][i], street_centerline['end_node_ids'][i]))

# Step 1: Start with a set for fast lookup and to avoid duplicates
original_links_set = set(directed_links)
full_links_set = set(directed_links)  # Start with the original ones

# Step 2: Loop over each link and add reverse if it's missing
for a, b in directed_links:
    if (b, a) not in original_links_set:
        full_links_set.add((b, a))

# Step 3: Convert back to a list if needed
links = list(full_links_set)

# Check how many links were added
# print(f"Original links: {len(directed_links)}")
# print(f"Total bidirectional links: {len(links)}")

#%%

# creating the costs and capacity dictionaries for the network

numberTrucks = 1       # trucks
bikesPerTruck = 16      # bikes/trucks


# Then create the costs dictionary
costs = {}

for (start, end), length in zip(directed_links, street_centerline['shape_leng']):
    costs[(start, end)] = length
    costs[(end, start)] = length


# capacity is 16 bikes per truck

capacity = {}

for (start, end), length in zip(directed_links, street_centerline['shape_leng']):
    capacity[(start, end)] = numberTrucks * bikesPerTruck
    capacity[(end, start)] = numberTrucks * bikesPerTruck

# # Example: print a few to verify
# print(list(costs.items())[:5])


#%%

# establishing the demand at our nodes

demand_path = 'C:/Users/sohca/OneDrive - The University of Texas at Austin/_UT Austin/2024-2025 coursework/C E-367R Sp25 - Optimization Techniques for Transportation Engineers/bikeshare_demand_04_15_09am.csv'

bikeshare_demand = pd.read_csv(demand_path)

bikeshare_stations = bikeshare_stations.merge(
    bikeshare_demand[['kiosk_id', 'bikes', 'empty_docks', 'total_docks', 'demand_minus', 'demand_notes', 'created']],
    on='kiosk_id',
    how='left')

# Step 1: Group bikeshare demand by nearest intersection
demand_by_node = bikeshare_stations.groupby('nearest_intersection_id')['demand_minus'].sum()

# Step 2: Initialize the demand_dict using intersections
net_demand = {}

for node_id in intersections['intersection_id']:
    # Use .get() to return 0 if the node ID isn't in demand_by_node
    net_demand[node_id] = -demand_by_node.get(node_id, 0)

# # Example: preview a few entries
# print(list(net_demand.items())[:5])

#%%

import time
from pyomo.environ import * # Import the Pyomo package, which include many useful functions and classes for optimization modeling, such as Objective(), Constraint(), Var(), SolverFactory(), etc.


start_time = time.time()

def get_incidence_matrix(nodes, links, directed):
    """
    Computes the node-link incidence matrix for an undirected graph.
    
    Parameters:
        nodes (list): List of node names.
        links (list of tuples): List of edges as (node1, node2).
        directed (bool): Whether the graph is directed.

    Returns:
        dictionary: Incidence matrix of shape (num_nodes, num_edges).
    """
    # Initialize the incidence matrix
    M = {}
    for i in nodes:
        for a in links:
            if i == a[0]: # source
                if directed:
                    M[i, a] = -1
                else:
                    M[i, a] = 1
            elif i == a[1]: # sink
                M[i, a] = 1
            else:
                M[i, a] = 0
    return M

print('creating model')
print("--- %s seconds ---" % (time.time() - start_time))
model = ConcreteModel() # Create a concrete model objective. ContreteModel is a class in Pyomo package.

print('getting incidence matrix')
print("--- %s seconds ---" % (time.time() - start_time))
incidence_matrix = get_incidence_matrix(nodes, links, True)

# Variables: flow on each link
print('creating variables')
print("--- %s seconds ---" % (time.time() - start_time))
model.flow = Var(links, domain=NonNegativeReals) # Define a variable x for link flow.

# Objective: Minimize total costs
def objective_rule(model):
    return sum(costs[a]*model.flow[a] for a in links)

print('creating objective rule')
print("--- %s seconds ---" % (time.time() - start_time))
model.Objective = Objective(rule=objective_rule, sense=minimize)  # minimize the total costs

# Constraints: flow conservation
def cons_flow_conservation_rule(model, i):
    return sum(model.flow[a] * incidence_matrix[i,a] for a in links) == net_demand[i]

print('creating flow conservation constraint')
print("--- %s seconds ---" % (time.time() - start_time))
model.cons_flow_conservation = Constraint(nodes, rule=cons_flow_conservation_rule)

# Constraints: flow capacity constraint
def cons_flow_capacity_rule(model, i,j):
    return model.flow[i,j] <= capacity[i,j]

print('creating flow capacity constraint')
print("--- %s seconds ---" % (time.time() - start_time))
model.cons_flow_capacity = Constraint(links, rule=cons_flow_capacity_rule)             


# Solve the problem
print('solving')
print("--- %s seconds ---" % (time.time() - start_time))
solver = SolverFactory('glpk')  # Use any installed solver, e.g., 'glpk', 'cbc', 'gurobi'
result = solver.solve(model)

print("--- %s seconds ---" % (time.time() - start_time))

# Display results
print("The minimum cost is: ", value(model.Objective))

model_flow = {}
for a in links:
    model_flow[a] = value(model.flow[a])

#%%

# Step 1: Create a flow dictionary with only positive flow
flow_links = {link: flow for link, flow in model_flow.items() if flow > 0}

# Step 2: Define a function to get flow value or NaN
def get_flow(row):
    a = row['start_node_id']
    b = row['end_node_ids']
    if (a, b) in flow_links:
        return flow_links[(a, b)]
    elif (b, a) in flow_links:
        return flow_links[(b, a)]
    else:
        return np.nan  # indicates no positive flow

# Step 3: Create a new column with flow values
street_centerline['flow'] = street_centerline.apply(get_flow, axis=1)

# Step 4: Filter to only those with positive flow
street_with_positive_flow = street_centerline[street_centerline['flow'].notna()].reset_index(drop=True)

#%%

# finding the cost for the actual trucks

trucks_cost = 0
truck_links = 0

for link in model_flow:
    if model_flow[link] > 0:
        trucks_cost += costs[link]
        truck_links += 1

trucks_nodes_served = 0
trucks_bikes_moved = 0

for node in net_demand:
    if net_demand[node] != 0:
        trucks_nodes_served += 1
    if net_demand[node] > 0:
        trucks_bikes_moved += net_demand[node]

#%%

# Save street centerlines with positive flow
# street_with_positive_flow.to_file("street_centerline_flow_real.shp")

# Save bikeshare stations
# bikeshare_stations.to_file("bikeshare_stations_demand_real.shp")

#%%

# creating a visualization for the report

# full_street_centerline_path = ('C:/Users/sohca/OneDrive - The University of Texas at Austin/_UT Austin/2024-2025 coursework/C E-367R Sp25 - Optimization Techniques for Transportation Engineers/street_centerline_total.shp')
# full_street_centerline = gpd.read_file(full_street_centerline_path)
# full_street_centerline_web = full_street_centerline.to_crs(epsg=3857)

# Make sure links and nodes are in Web Mercator (EPSG:3857) for basemap compatibility
links_web = street_centerline.to_crs(epsg=3857)
nodes_web = intersections.to_crs(epsg=3857)
stations_web = stations_with_intersections.to_crs(epsg=3857)

# Set up the plot
fig, ax = plt.subplots(figsize=(10, 8))

# Plot links and nodes
links_web.plot(ax=ax, color='gray', linewidth=1, label='Street Centerlines')
# full_street_centerline_web.plot(ax=ax, color='gray', linewidth=1, label='Street Centerlines')
nodes_web.plot(ax=ax, color='blue', markersize=15, label='Nodes')
# stations_web.plot(ax=ax, color='red', markersize=15, label='Bikeshare Kiosks')

# Add text labels and adjust them to avoid overlap

# if 'kiosk_name' in stations_with_intersections.columns:
#     for x, y, label in zip(stations_web.geometry.x, stations_web.geometry.y, stations_with_intersections['kiosk_name']):
#         ax.text(
#                     x + 0.0001, y + 0.0001, str(label),
#                     fontsize=8,
#                     color='white',  # Text color
#                     bbox=dict(facecolor='black', alpha=0.6, edgecolor='none', boxstyle='round,pad=0.2')  # Background box
#                 )

# Add basemap
# ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)

# Final layout
ax.set_title("Austin's Road Network", fontsize=14)
ax.legend(loc='lower left', fontsize='medium')  # Adjust position/font size as needed
ax.set_axis_off()  # Hide axes for map-style plot
plt.tight_layout()
plt.show()
