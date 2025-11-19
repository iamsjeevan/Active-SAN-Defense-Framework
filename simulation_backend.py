import numpy as np
import random
import networkx as nx

# --- CONFIGURATION ---
LAMBDA_0 = {
    'Server': 1.04e-7, 
    'Storage': 4.75e-11,
    'Switch': 4.75e-11
}

class ANSCompressor:
    def __init__(self, min_ratio=1.2, max_ratio=2.8):
        self.min_ratio = min_ratio
        self.max_ratio = max_ratio

    def compress(self, data_size_mb):
        ratio = random.uniform(self.min_ratio, self.max_ratio)
        return data_size_mb / ratio, ratio

class TopologyManager:
    @staticmethod
    def get_predefined_topology(type="Mesh"):
        G = nx.DiGraph()
        pos = {}
        
        if type == "Mesh (Standard)":
            # N+1 Topology: Standby in the middle
            nodes = ['Server-1', 'SwA1', 'SwB1', 'Sw-Standby', 'SwA2', 'SwB2', 'Storage-1']
            
            edges = [
                ('Server-1', 'SwA1'), ('Server-1', 'SwB1'), 
                ('SwA1', 'SwA2'), ('SwB1', 'SwB2'),
                ('SwA2', 'Storage-1'), ('SwB2', 'Storage-1'),
                # Standby Paths (Hidden unless active)
                ('SwA1', 'Sw-Standby'), ('SwB1', 'Sw-Standby'), 
                ('Sw-Standby', 'Storage-1')
            ]
            
            G.add_nodes_from(nodes)
            G.add_edges_from(edges)

            pos = {
                'Server-1': (0, 3), 'Storage-1': (0, 0),
                'SwA1': (-1.5, 2), 'SwB1': (1.5, 2),
                'Sw-Standby': (0, 1.2), # Center
                'SwA2': (-1.5, 1), 'SwB2': (1.5, 1)
            }
        
        return G, pos

class ReliabilityMath:
    @staticmethod
    def simulate_traffic_flow(G, raw_traffic, scenario_type, threshold):
        node_status = {}
        edge_flows = {} 
        compressor = ANSCompressor()
        comp_ratio = 1.0
        logs = []

        # 1. Initialize Nodes & Edges
        for node in G.nodes():
            node_status[node] = {'load': 0, 'color': '#DDDDDD', 'state': 'Idle'}
        
        for u, v in G.edges():
            edge_flows[(u, v)] = 0

        # 2. Determine Traffic Input
        traffic_to_send = raw_traffic
        if "ANS" in scenario_type or "Full" in scenario_type:
            traffic_to_send, comp_ratio = compressor.compress(raw_traffic)
            logs.append(f"✅ **ANS Active:** Traffic reduced to {int(traffic_to_send)}MB")

        # 3. Server Distribution (Imbalanced 60/40)
        load_A = traffic_to_send * 0.60
        load_B = traffic_to_send * 0.40
        
        node_status['Server-1']['load'] = traffic_to_send
        node_status['Server-1']['color'] = '#00CC96'
        node_status['Server-1']['state'] = 'OK'

        node_status['SwA1']['load'] = load_A
        node_status['SwB1']['load'] = load_B
        
        edge_flows[('Server-1', 'SwA1')] = load_A
        edge_flows[('Server-1', 'SwB1')] = load_B

        # --- PROCESS LAYER 1 (SwA1, SwB1) ---
        layer_1 = ['SwA1', 'SwB1']
        
        for sw in layer_1:
            current_load = node_status[sw]['load']
            flow_main = current_load
            flow_standby = 0
            
            # LOGIC: Check Threshold
            if current_load > threshold:
                
                # CASE: REROUTING ON
                if "Rerouting" in scenario_type or "Full" in scenario_type:
                    # Math: Keep 95% of threshold, send rest to standby
                    safe_capacity = threshold * 0.95
                    excess = current_load - safe_capacity
                    
                    flow_main = safe_capacity
                    flow_standby = excess
                    
                    # Update Status
                    node_status[sw]['color'] = '#FFA15A' # Orange
                    node_status[sw]['state'] = 'Rerouted'
                    logs.append(f"⚠️ **Reroute:** {sw} sent {int(flow_standby)}MB to Standby.")

                # CASE: BASELINE (No Reroute)
                else:
                    # Switch Dies. Flow stops.
                    node_status[sw]['color'] = '#000000' # Black
                    node_status[sw]['state'] = 'Dead'
                    flow_main = 0 # Pipe Broken
                    flow_standby = 0
                    logs.append(f"❌ **FAILURE:** {sw} overloaded ({int(current_load)}MB).")
            
            else:
                # Normal Operation
                node_status[sw]['color'] = '#00CC96' # Green
                node_status[sw]['state'] = 'Safe'

            # Update Downstream Flows
            # 1. To Main Layer 2
            target = 'SwA2' if sw == 'SwA1' else 'SwB2'
            edge_flows[(sw, target)] = flow_main
            node_status[target]['load'] += flow_main
            
            # 2. To Standby (Only if flow > 0)
            if flow_standby > 0:
                edge_flows[(sw, 'Sw-Standby')] = flow_standby
                node_status['Sw-Standby']['load'] += flow_standby
                node_status['Sw-Standby']['color'] = '#FFA15A' # Active
                node_status['Sw-Standby']['state'] = 'Active'

        # --- PROCESS STANDBY ---
        # If Standby has load, push to storage
        standby_load = node_status['Sw-Standby']['load']
        if standby_load > 0:
             edge_flows[('Sw-Standby', 'Storage-1')] = standby_load
             node_status['Storage-1']['load'] += standby_load

        # --- PROCESS LAYER 2 (SwA2, SwB2) ---
        layer_2 = ['SwA2', 'SwB2']
        for sw in layer_2:
            load = node_status[sw]['load']
            
            if load > 0:
                if load > threshold:
                    node_status[sw]['color'] = '#EF553B' # Red (Warning)
                    node_status[sw]['state'] = 'Overloaded'
                    logs.append(f"❌ **Layer 2 Fail:** {sw} Overloaded.")
                    # Assume broken pipe if layer 2 fails
                    edge_flows[(sw, 'Storage-1')] = 0 
                else:
                    node_status[sw]['color'] = '#00CC96'
                    node_status[sw]['state'] = 'Safe'
                    # Push to storage
                    edge_flows[(sw, 'Storage-1')] = load
                    node_status['Storage-1']['load'] += load
            else:
                # If no load reached here (upstream dead), stay grey
                node_status[sw]['color'] = '#DDDDDD'

        # Storage Status
        node_status['Storage-1']['color'] = '#00CC96'

        return node_status, logs, comp_ratio, edge_flows