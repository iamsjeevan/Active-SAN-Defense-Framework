# File: simulations/02_static_fattree_baseline.py
# FINAL CORRECTED VERSION

import simpy
import functools
import random
import networkx as nx  # <<< --- STEP 1: IMPORT THE NETWORKX LIBRARY

from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.topos.fattree import build as build_fattree
from san_components.failing_switch import FailingSwitch

def get_port_index(ft, switch_id, neighbor_id):
            neighbors = list(ft.adj[switch_id])
            return neighbors.index(neighbor_id)

def run_simulation(simulation_time=2000):
    """
    Sets up a static Fat-Tree network baseline.

    This simulation builds a full network topology populated with FailingSwitch instances.
    It establishes a single, statically routed path from a source to a sink and sends
    high traffic along it to induce a cascading failure. This represents the full
    "problem" that our defense strategies will later solve.
    """
    env = simpy.Environment()

    # --- 1. Build the Network Topology ---
    ft = build_fattree(k=4)

    # --- 2. Instantiate and Replace Switches ---
    for node_id in ft.nodes():
        if ft.nodes[node_id]['type'] == 'switch':
            ft.nodes[node_id]['device'] = FailingSwitch(
                env=env,
                n_ports=len(ft.adj[node_id]),
                port_rate=1e9,
                buffer_size=1024 * 1024, # 1MB buffer
                switch_id=node_id,
                base_mttf=500,
                failure_alpha=15.0
            )

    # --- 3. Set up a Single Traffic Flow ---
    hosts = [n for n, d in ft.nodes(data=True) if d['type'] == 'host']
    server_id = hosts[0]
    sink_id = hosts[-1] # Use the first and last hosts for our flow

    # Create the sink
    sink = PacketSink(env, rec_flow_ids=True)
    ft.nodes[sink_id]['device'] = sink

    # Create the traffic generator for Flow 0
    adist = functools.partial(random.expovariate, 8e8 / (1500 * 8)) # 800 Mbps
    sdist = functools.partial(random.choice, [1500])
    packet_generator = DistPacketGenerator(
        env,
        f"Flow_0_Gen",
        adist,
        sdist,
        flow_id=0
    )
    ft.nodes[server_id]['device'] = packet_generator

    # --- 4. Manually Program the Static Route ---
    # Find the shortest path for our flow
    # <<< --- STEP 2: USE THE CORRECT NETWORKX FUNCTION SYNTAX --- >>>
    path = list(nx.all_shortest_paths(ft, server_id, sink_id))[0]

    # Wire the generator to the first switch
    first_switch_id = path[1]
    packet_generator.out = ft.nodes[first_switch_id]['device']

    print(f"--- Setting up static route for Flow 0 ---")
    print(f"Path: {' -> '.join(map(str, path))}")

    # Program the Forwarding Information Base (FIB) for each switch in the path
    # for i in range(1, len(path) - 1):
    #     current_switch_id = path[i]
    #     next_hop_id = path[i+1]
        
    #     # Find the port on the current switch that connects to the next hop

    #     port_to_next_hop = get_port_index(ft, current_switch_id, next_hop_id)

        
    #     current_switch = ft.nodes[current_switch_id]['device']
    #     next_hop_device = ft.nodes[next_hop_id]['device']

    #     # Set the forwarding rule: "If you see a packet with flow_id 0, send it out of this port"
    #     current_switch.demux.fib[0] = port_to_next_hop
        
    #     # Physically connect the port's output to the next device in the chain
    #     current_switch.ports[port_to_next_hop].out = next_hop_device
    # --- 4. Manually Program the Static Route ---
    for i in range(1, len(path) - 1):
        current_switch_id = path[i]
        next_hop_id = path[i + 1]

        current_switch = ft.nodes[current_switch_id]["device"]
        next_hop_device = ft.nodes[next_hop_id]["device"]

        # Determine outgoing port index
        port_to_next_hop = get_port_index(ft, current_switch_id, next_hop_id)

        # Disconnect ALL ports first
        for port in current_switch.ports:
            port.out = None

        # Connect ONLY the correct port
        current_switch.ports[port_to_next_hop].out = next_hop_device
        print(f"Route: Switch {current_switch_id} → port {port_to_next_hop} → Switch {next_hop_id}")
    # --- 5. Run the Simulation ---
    print(f"--- Starting Static Fat-Tree SAN Simulation ---")
    env.run(until=simulation_time)
    print("\n--- Simulation Finished ---")
    
    # --- 6. Report Results ---
    total_failed = sum(1 for node_id in ft.nodes() if ft.nodes[node_id]['type'] == 'switch' and ft.nodes[node_id]['device'].is_failed)
    path_switches = path[1:-1]
    failed_on_path = sum(1 for switch_id in path_switches if ft.nodes[switch_id]['device'].is_failed)

    print(f"Total switches in network: {len(ft.nodes()) - len(hosts)}")
    print(f"Total switches failed: {total_failed}")
    print(f"Switches on the high-traffic path: {len(path_switches)}")
    print(f"Switches failed ON THE PATH: {failed_on_path}")

if __name__ == "__main__":
    run_simulation()