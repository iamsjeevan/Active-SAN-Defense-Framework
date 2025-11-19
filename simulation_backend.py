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
            nodes = ['Server-1', 'SwA1', 'SwB1', 'SwA2', 'SwB2', 'Storage-1']
            
            # Vertical Flow
            primary_edges = [
                ('Server-1', 'SwA1'), ('Server-1', 'SwB1'), 
                ('SwA1', 'SwA2'), ('SwB1', 'SwB2'), 
                ('SwA2', 'Storage-1'), ('SwB2', 'Storage-1')
            ]
            # Horizontal Flow
            backup_edges = [
                ('SwA1', 'SwB1'), ('SwB1', 'SwA1'),
                ('SwA2', 'SwB2'), ('SwB2', 'SwA2')
            ]
            
            G.add_nodes_from(nodes)
            for u, v in primary_edges: G.add_edge(u, v, type='primary')
            for u, v in backup_edges: G.add_edge(u, v, type='backup')

            pos = {
                'Server-1': (0, 3), 'Storage-1': (0, 0),
                'SwA1': (-1, 2), 'SwB1': (1, 2),
                'SwA2': (-1, 1), 'SwB2': (1, 1)
            }
        
        return G, pos

class ReliabilityMath:
    @staticmethod
    def calculate_failure_rate(component_name, load_L, alpha=0.005):
        base = LAMBDA_0.get('Switch', 4.75e-11)
        if load_L > 1200: alpha *= 5 
        return base * np.exp(alpha * load_L)

    @staticmethod
    def calculate_reliability(lam, t):
        return np.exp(-lam * t)

    @staticmethod
    def simulate_traffic_flow(G, raw_traffic, scenario_type, threshold):
        node_status = {}
        compressor = ANSCompressor()
        comp_ratio = 1.0
        logs = []

        # 1. Initialize Nodes
        for node in G.nodes():
            node_status[node] = {'load': 0, 'color': '#00CC96', 'state': 'Safe'}

        # 2. Source Injection
        servers = [n for n in G.nodes() if "Server" in n]
        if not servers: return {}, ["⚠️ No Server"], 1.0
        
        traffic_to_send = raw_traffic
        if "ANS" in scenario_type or "Full" in scenario_type:
            traffic_to_send, comp_ratio = compressor.compress(raw_traffic)
            logs.append(f"✅ **ANS:** Reduced {int(raw_traffic)}MB -> {int(traffic_to_send)}MB")

        # --- STEP A: SERVER -> LAYER 1 (IMBALANCED) ---
        # To show Rerouting working, we intentionally imbalance the load
        # SwA1 gets 60%, SwB1 gets 40%. 
        # This ensures SwA1 fails first, allowing SwB1 to save it.
        layer_1 = ['SwA1', 'SwB1']
        layer_2 = ['SwA2', 'SwB2']
        
        # Traffic Logic
        node_status['SwA1']['load'] += traffic_to_send * 0.60 # Heavier Load
        node_status['SwB1']['load'] += traffic_to_send * 0.40 # Lighter Load

        # --- STEP B: PROCESS LAYER 1 ---
        for sw in layer_1:
            load = node_status[sw]['load']
            
            if load > threshold:
                # REROUTING LOGIC
                if "Rerouting" in scenario_type or "Full" in scenario_type:
                    neighbor = 'SwB1' if sw == 'SwA1' else 'SwA1'
                    
                    # Check if Neighbor has space
                    neighbor_load = node_status[neighbor]['load']
                    if neighbor_load < threshold:
                        # Calculate how much to move
                        slack = threshold - neighbor_load
                        excess = load - threshold + 50 # Move enough to be safe
                        
                        # Can't move more than slack
                        move_amount = min(excess, slack) 
                        
                        node_status[sw]['load'] -= move_amount
                        node_status[neighbor]['load'] += move_amount
                        
                        node_status[sw]['state'] = 'Rerouted'
                        node_status[sw]['color'] = '#FFA15A' # Orange
                        logs.append(f"⚠️ **Reroute Active:** {sw} was {int(load)}MB. Moved {int(move_amount)}MB to {neighbor}.")
                    else:
                        # Neighbor full too? Die.
                        node_status[sw]['state'] = 'Dead'
                        node_status[sw]['color'] = '#000000'
                        logs.append(f"❌ **FAIL:** {sw} overloaded ({int(load)}MB) & neighbor full.")
                else:
                    # BASELINE (No Rerouting)
                    node_status[sw]['state'] = 'Dead'
                    node_status[sw]['color'] = '#000000'
                    logs.append(f"❌ **FAIL:** {sw} overloaded ({int(load)}MB). No defense.")

        # --- STEP C: LAYER 1 -> LAYER 2 ---
        for sw in layer_1:
            if node_status[sw]['state'] != 'Dead':
                # Push to Layer 2 counterpart
                target = 'SwA2' if sw == 'SwA1' else 'SwB2'
                node_status[target]['load'] += node_status[sw]['load']

        # --- STEP D: PROCESS LAYER 2 ---
        for sw in layer_2:
            load = node_status[sw]['load']
            if load > threshold:
                # Same Rerouting Logic for Layer 2
                if "Rerouting" in scenario_type or "Full" in scenario_type:
                    neighbor = 'SwB2' if sw == 'SwA2' else 'SwA2'
                    neighbor_load = node_status[neighbor]['load']
                    
                    if neighbor_load < threshold:
                        slack = threshold - neighbor_load
                        excess = load - threshold + 50
                        move_amount = min(excess, slack)
                        
                        node_status[sw]['load'] -= move_amount
                        node_status[neighbor]['load'] += move_amount
                        node_status[sw]['state'] = 'Rerouted'
                        node_status[sw]['color'] = '#FFA15A'
                        logs.append(f"⚠️ **Reroute:** {sw} -> {neighbor}")
                    else:
                        node_status[sw]['state'] = 'Dead'
                        node_status[sw]['color'] = '#000000'
                        logs.append(f"❌ **FAIL:** {sw} overloaded.")
                else:
                    node_status[sw]['state'] = 'Dead'
                    node_status[sw]['color'] = '#000000'
                    logs.append(f"❌ **FAIL:** {sw} overloaded.")

        # --- STEP E: LAYER 2 -> STORAGE ---
        for sw in layer_2:
             if node_status[sw]['state'] != 'Dead':
                node_status['Storage-1']['load'] += node_status[sw]['load']

        return node_status, logs, comp_ratio