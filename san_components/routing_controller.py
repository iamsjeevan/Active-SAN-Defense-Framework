# san_components/routing_controller.py

import networkx as nx
import itertools

class RoutingController:
    """
    A centralized controller that actively monitors switch loads and dynamically
    updates routing tables (FIBs) to avoid congestion and prevent cascading failures.
    It operates as a SimPy process, periodically re-evaluating the network state.

    Parameters
    ----------
    env : simpy.Environment
        The simulation environment.
    network_graph : networkx.Graph
        The network topology, where nodes are switch IDs.
    switches : dict
        A dictionary mapping switch IDs to the actual switch objects.
    update_interval : float
        The interval in seconds at which the controller updates the routes.
    """
    def __init__(self, env, network_graph: nx.Graph, switches: dict, update_interval: float = 1.0):
        self.env = env
        self.network_graph = network_graph.copy() # Work on a copy
        self.switches = switches
        self.update_interval = update_interval
        self.action = env.process(self.run())
        self.nodes = list(self.switches.keys())

    def run(self):
        """The main process loop for the routing controller."""
        while True:
            # Wait for the next update cycle
            yield self.env.timeout(self.update_interval)

            print(f"[{self.env.now:.2f}s] RoutingController: Updating network routes...")

            # Step 1: Update the weights on the graph edges based on current switch load.
            # A higher load means a higher "cost" to traverse that edge.
            for u, v in self.network_graph.edges():
                destination_switch = self.switches[v]

                # This is the key integration point with Jeevan's FailingSwitch
                # We read its current_load and check if it has failed.
                if not destination_switch.is_failed:
                    # The cost is a base of 1 plus the load.
                    # This ensures that even an idle path has a cost.
                    load_cost = destination_switch.current_load
                    self.network_graph.edges[u, v]['weight'] = 1 + load_cost
                else:
                    # If the switch has failed, make the path to it infinitely expensive
                    self.network_graph.edges[u, v]['weight'] = float('inf')

            # Step 2: Recalculate all-pairs shortest paths and update switch FIBs.
            self.update_all_fibs()

    def update_all_fibs(self):
        """
        Calculates the shortest path between all pairs of nodes and updates the
        forwarding table (FIB) for every switch in the network.
        """
        # Use itertools.permutations to get all possible (source, destination) pairs
        for source, dest in itertools.permutations(self.nodes, 2):
            try:
                # Find the best path using the newly weighted graph
                path = nx.dijkstra_path(
                    self.network_graph, source, dest, weight='weight'
                )

                # Update the FIB for each switch along this new path
                # The path is [source, hop1, hop2, ..., dest]
                for i in range(len(path) - 1):
                    current_switch_id = path[i]
                    next_hop_id = path[i+1]
                    
                    # Get the switch object
                    current_switch = self.switches[current_switch_id]
                    
                    # Update its forwarding table: "to get to dest, send to next_hop_id"
                    if not current_switch.is_failed:
                        current_switch.fib[dest] = next_hop_id

            except nx.NetworkXNoPath:
                # This can happen if failures disconnect parts of the network.
                # We can log this, but for now we'll just skip.
                # print(f"  - No path from {source} to {dest}")
                pass