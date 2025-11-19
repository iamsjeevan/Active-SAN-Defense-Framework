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
    def get_predefined_topology(type="N+1 Redundancy"):
        G = nx.DiGraph()
        pos = {}
        
        if type == "N+1 Redundancy":
            nodes = ['Server-1', 'SwA1', 'SwB1', 'Sw-Standby', 'SwA2', 'SwB2', 'Storage-1']
            edges = [
                ('Server-1', 'SwA1'), ('Server-1', 'SwB1'), 
                ('SwA1', 'SwA2'), ('SwB1', 'SwB2'),
                ('SwA2', 'Storage-1'), ('SwB2', 'Storage-1'),
                ('SwA1', 'Sw-Standby'), ('SwB1', 'Sw-Standby'), 
                ('Sw-Standby', 'Storage-1')
            ]
            G.add_nodes_from(nodes)
            G.add_edges_from(edges)
            pos = {
                'Server-1': (0, 3), 'Storage-1': (0, 0),
                'SwA1': (-1.5, 2), 'SwB1': (1.5, 2),
                'Sw-Standby': (0, 1.2),
                'SwA2': (-1.5, 1), 'SwB2': (1.5, 1)
            }

        elif type == "Full Mesh":
            nodes = ['Server-Gen', 'Sw1', 'Sw2', 'Sw3', 'Sw4', 'Storage-Gen']
            edges = [
                ('Server-Gen', 'Sw1'), ('Server-Gen', 'Sw2'),
                ('Sw1', 'Sw3'), ('Sw1', 'Sw4'), 
                ('Sw2', 'Sw3'), ('Sw2', 'Sw4'), 
                ('Sw3', 'Storage-Gen'), ('Sw4', 'Storage-Gen')
            ]
            G.add_nodes_from(nodes)
            G.add_edges_from(edges)
            pos = {
                'Server-Gen': (0, 3),
                'Sw1': (-1, 2), 'Sw2': (1, 2),
                'Sw3': (-1, 1), 'Sw4': (1, 1),
                'Storage-Gen': (0, 0)
            }

        elif type == "Fat-Tree":
            nodes = ['Server-Gen', 'Edge1', 'Edge2', 'Core1', 'Core2', 'Storage-Gen']
            edges = [
                ('Server-Gen', 'Edge1'), ('Server-Gen', 'Edge2'),
                ('Edge1', 'Core1'), ('Edge1', 'Core2'),
                ('Edge2', 'Core1'), ('Edge2', 'Core2'),
                ('Core1', 'Storage-Gen'), ('Core2', 'Storage-Gen')
            ]
            G.add_nodes_from(nodes)
            G.add_edges_from(edges)
            pos = {
                'Server-Gen': (0, 3),
                'Edge1': (-1.5, 2), 'Edge2': (1.5, 2),
                'Core1': (-0.5, 1), 'Core2': (0.5, 1),
                'Storage-Gen': (0, 0)
            }

        elif type == "Ring Topology":
            nodes = ['Server-Gen', 'Sw1', 'Sw2', 'Sw3', 'Sw4', 'Storage-Gen']
            edges = [
                ('Server-Gen', 'Sw1'),
                ('Sw1', 'Sw2'), ('Sw2', 'Sw3'), ('Sw3', 'Sw4'), ('Sw4', 'Sw1'),
                ('Sw3', 'Storage-Gen')
            ]
            G.add_nodes_from(nodes)
            G.add_edges_from(edges)
            pos = {
                'Server-Gen': (-2, 2),
                'Sw1': (-1, 2), 'Sw2': (1, 2),
                'Sw3': (1, 1), 'Sw4': (-1, 1),
                'Storage-Gen': (2, 1)
            }

        return G, pos

    @staticmethod
    def build_custom_topology(node_list, edge_list):
        G = nx.DiGraph()
        G.add_nodes_from(node_list)
        G.add_edges_from(edge_list)
        try:
            pos = nx.shell_layout(G)
        except:
            pos = nx.spring_layout(G)
        for node in G.nodes():
            x, y = pos[node]
            if "Server" in node: pos[node] = (x, 1.5)
            elif "Storage" in node: pos[node] = (x, -1.5)
            else: pos[node] = (x * 1.2, y)
        return G, pos

class ReliabilityMath:
    @staticmethod
    def simulate_traffic_flow(G, raw_traffic, scenario_type, threshold):
        # Delegate to Generic if not the special N+1 case
        if 'Server-1' not in G.nodes():
            return ReliabilityMath.simulate_generic_flow(G, raw_traffic, threshold, scenario_type)

        # --- N+1 SPECIAL LOGIC ---
        # UPDATED: Added 'capacity' to init
        node_status = {n: {'load': 0, 'color': '#DDDDDD', 'state': 'Idle', 'capacity': threshold} for n in G.nodes()}
        
        # Servers/Storage technically have "Infinite" or higher cap, but we'll mark them as Source/Sink
        node_status['Server-1']['capacity'] = 'Source'
        node_status['Storage-1']['capacity'] = 'Sink'
        
        edge_flows = {e: 0 for e in G.edges()} 
        compressor = ANSCompressor()
        comp_ratio = 1.0
        logs = []

        traffic_to_send = raw_traffic
        if "ANS" in scenario_type or "Full" in scenario_type:
            traffic_to_send, comp_ratio = compressor.compress(raw_traffic)
            logs.append(f"✅ ANS Active: Input {int(raw_traffic)}MB → {int(traffic_to_send)}MB")

        node_status['Server-1'].update({'load': traffic_to_send, 'color': '#00CC96', 'state': 'OK'})
        load_A = traffic_to_send * 0.6; load_B = traffic_to_send * 0.4
        edge_flows[('Server-1', 'SwA1')] = load_A
        edge_flows[('Server-1', 'SwB1')] = load_B
        node_status['SwA1']['load'] = load_A
        node_status['SwB1']['load'] = load_B

        for sw in ['SwA1', 'SwB1']:
            load = node_status[sw]['load']
            flow_main = load
            flow_standby = 0
            
            if load > threshold:
                if "Rerouting" in scenario_type or "Full" in scenario_type:
                    flow_main = threshold * 0.95
                    flow_standby = load - flow_main
                    node_status[sw].update({'color': '#FFA15A', 'state': 'Rerouted'})
                    logs.append(f"⚠️ Reroute: {sw} -> Standby ({int(flow_standby)}MB)")
                else:
                    node_status[sw].update({'color': '#000000', 'state': 'Failure'})
                    flow_main = 0
                    logs.append(f"❌ FAILURE: {sw} crashed.")
            else:
                node_status[sw].update({'color': '#00CC96', 'state': 'Safe'})

            target = 'SwA2' if sw == 'SwA1' else 'SwB2'
            edge_flows[(sw, target)] = flow_main
            node_status[target]['load'] += flow_main
            
            if flow_standby > 0:
                edge_flows[(sw, 'Sw-Standby')] = flow_standby
                node_status['Sw-Standby']['load'] += flow_standby
                node_status['Sw-Standby'].update({'color': '#FFA15A', 'state': 'Active'})

        s_load = node_status['Sw-Standby']['load']
        if s_load > 0:
            edge_flows[('Sw-Standby', 'Storage-1')] = s_load
            node_status['Storage-1']['load'] += s_load

        for sw in ['SwA2', 'SwB2']:
            load = node_status[sw]['load']
            if load > 0:
                if load > threshold:
                    node_status[sw].update({'color': '#EF553B', 'state': 'Overload'})
                    edge_flows[(sw, 'Storage-1')] = 0 
                else:
                    node_status[sw].update({'color': '#00CC96', 'state': 'Safe'})
                    edge_flows[(sw, 'Storage-1')] = load
                    node_status['Storage-1']['load'] += load
            else:
                node_status[sw]['color'] = '#DDDDDD'

        node_status['Storage-1'].update({'color': '#00CC96', 'state': 'Online'})
        return node_status, logs, comp_ratio, edge_flows

    @staticmethod
    def simulate_generic_flow(G, raw_traffic, threshold, scenario_type="Baseline"):
        # UPDATED: Added 'capacity' to init
        node_status = {n: {'load': 0, 'color': '#DDDDDD', 'state': 'Idle', 'capacity': threshold} for n in G.nodes()}
        
        edge_flows = {e: 0 for e in G.edges()}
        logs = []
        compressor = ANSCompressor()
        comp_ratio = 1.0

        sources = [n for n in G.nodes() if "Server" in n]
        if not sources: return node_status, ["❌ No Server nodes found."], 1.0, edge_flows

        traffic_to_distribute = raw_traffic
        if "ANS" in scenario_type or "Full" in scenario_type:
            traffic_to_distribute, comp_ratio = compressor.compress(raw_traffic)
            logs.append(f"✅ ANS Active: Input {int(raw_traffic)}MB → {int(traffic_to_distribute)}MB")

        per_server = traffic_to_distribute / len(sources)
        queue = []
        
        for src in sources:
            node_status[src]['load'] = per_server
            node_status[src]['color'] = '#00CC96'
            node_status[src]['state'] = 'Source'
            node_status[src]['capacity'] = 'Source'
            queue.append(src)

        steps = 0
        max_steps = len(G.nodes()) * 3
        
        while queue and steps < max_steps:
            current = queue.pop(0)
            load_in = node_status[current]['load']
            
            if "Server" not in current and "Storage" not in current:
                if load_in > threshold:
                    if "Rerouting" in scenario_type or "Full" in scenario_type:
                        pass_load = threshold
                        node_status[current].update({'color': '#FFA15A', 'state': 'Capped/Rerouted'})
                        logs.append(f"⚠️ {current}: Traffic capped at {threshold}MB (Rerouting Active)")
                    else:
                        pass_load = 0 
                        node_status[current].update({'color': '#000000', 'state': 'Crashed'})
                        logs.append(f"❌ {current} CRASHED due to overload!")
                else:
                    pass_load = load_in
                    node_status[current].update({'color': '#00CC96', 'state': 'Safe'})
            else:
                pass_load = load_in
                if "Storage" in current: 
                    node_status[current].update({'color': '#00CC96', 'state': 'Sink', 'capacity': 'Sink'})

            neighbors = list(G.successors(current))
            if not neighbors: continue
            
            if pass_load > 0:
                out_per_link = pass_load / len(neighbors)
                for nbr in neighbors:
                    edge_flows[(current, nbr)] = out_per_link
                    node_status[nbr]['load'] += out_per_link
                    if nbr not in queue:
                        queue.append(nbr)
            
            steps += 1

        return node_status, logs, comp_ratio, edge_flows