import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

# Import your backend classes
# Make sure simulation_backend.py is in the same folder
try:
    from simulation_backend import ANSCompressor, ReliabilityMath
except ImportError:
    st.error("Error: 'simulation_backend.py' not found. Please save your backend code in the same directory.")
    st.stop()

# --- CONFIGURATION ---
st.set_page_config(page_title="Active SAN Defense Framework", layout="wide")
THRESHOLD_MBPS = 800

# --- HELPER FUNCTIONS ---

def build_topology():
    """
    Creates the NetworkX DiGraph and Layout.
    Hierarchical Layout: Server (Top) -> Switches (Middle) -> Storage (Bottom).
    """
    G = nx.DiGraph()
    
    # Nodes
    nodes = ['Server', 'SwA1', 'SwB1', 'SwA2', 'SwB2', 'Storage']
    G.add_nodes_from(nodes)
    
    # Edges (Directed)
    edges = [
        ('Server', 'SwA1'), ('Server', 'SwB1'),
        ('SwA1', 'SwA2'), 
        ('SwB1', 'SwB2'),
        ('SwA2', 'Storage'), ('SwB2', 'Storage')
    ]
    G.add_edges_from(edges)
    
    # Manual Positions for Hierarchical View (x, y)
    pos = {
        'Server':  (0, 3),
        'SwA1':   (-1, 2), 'SwB1': (1, 2),
        'SwA2':   (-1, 1), 'SwB2': (1, 1),
        'Storage': (0, 0)
    }
    return G, pos

def calculate_node_status(G, raw_traffic, use_ans, use_rerouting):
    """
    Logic for Novelty #1 (Compression) and Novelty #2 (Rerouting/Coloring).
    Returns: colors list, node_labels dict, log_messages list
    """
    colors = []
    labels = {}
    logs = []
    
    # 1. Initialize ANS Compressor from Backend
    compressor = ANSCompressor()
    
    # 2. Determine Load per path (Split 50/50 from Server)
    path_a_load = raw_traffic / 2
    path_b_load = raw_traffic / 2
    
    # Apply Novelty #1: ANS Compression
    comp_ratio = 1.0
    if use_ans:
        # Compress the traffic using backend logic
        path_a_load, comp_ratio = compressor.compress(path_a_load)
        path_b_load = path_b_load / comp_ratio # Apply same ratio to path B for consistency
        logs.append(f"**ANS Active:** Compressed traffic by ratio {comp_ratio:.2f}x")

    # Map loads to nodes
    node_loads = {
        'Server': raw_traffic,
        'SwA1': path_a_load, 'SwA2': path_a_load,
        'SwB1': path_b_load, 'SwB2': path_b_load,
        'Storage': path_a_load + path_b_load
    }

    # 3. Iterate nodes to determine Color and Logic
    for node in G.nodes():
        load = node_loads.get(node, 0)
        
        # Label text (Node Name + Load)
        labels[node] = f"{node}\n{int(load)}MB/s"
        
        # Default Colors
        if node in ['Server', 'Storage']:
            colors.append('#d3d3d3') # Grey for endpoints
            continue

        # --- NOVELTY #2 LOGIC ---
        if load > THRESHOLD_MBPS:
            if use_rerouting:
                # Logic: Simulate moving traffic, color GREEN, print message
                colors.append('#90EE90') # Green (Safe/Fixed)
                
                # Identify neighbor for logging
                neighbor = "SwB1" if "SwA" in node else "SwA1"
                logs.append(f"⚠️ **Defense Triggered:** {node} overloaded ({int(load)} MB/s). Traffic dynamically rerouted to {neighbor}.")
            else:
                # Logic: Danger State
                colors.append('#FF4B4B') # Red (Critical)
                logs.append(f"❌ **CRITICAL:** {node} Overloaded ({int(load)} MB/s). Packet loss imminent.")
        else:
            # Normal State
            colors.append('#90EE90') # Green (Safe)

    return colors, labels, logs, comp_ratio

# --- MAIN APP ---

def main():
    st.title("🛡️ Active SAN Defense Framework")
    st.markdown("Research Implementation: *Reliability of Storage Area Networks*")

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("Simulation Controls")
        
        # Input 1: Traffic Slider
        traffic_input = st.slider("Input Traffic Load (MB/s)", min_value=0, max_value=2000, value=1500, step=50)
        
        st.markdown("---")
        st.subheader("Research Novelties")
        
        # Input 2: Novelty 1 Checkbox
        enable_ans = st.checkbox("Enable ANS Compression (Novelty 1)")
        
        # Input 3: Novelty 2 Checkbox
        enable_reroute = st.checkbox("Enable Dynamic Rerouting (Novelty 2)")
        
        st.markdown("---")
        st.info(f"Overload Threshold: {THRESHOLD_MBPS} MB/s")

    # --- LAYOUT ---
    col_graph, col_logs = st.columns([2, 1])

    # --- LOGIC EXECUTION ---
    G, pos = build_topology()
    node_colors, node_labels, log_messages, ratio = calculate_node_status(
        G, traffic_input, enable_ans, enable_reroute
    )

    # --- VISUALIZATION (Matplotlib + NetworkX) ---
    with col_graph:
        st.subheader("Topology Visualization")
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Draw Edges
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color='gray', arrowstyle='->', arrowsize=20)
        
        # Draw Nodes
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=2500, edgecolors='black')
        
        # Draw Labels
        nx.draw_networkx_labels(G, pos, ax=ax, labels=node_labels, font_size=9, font_weight='bold')
        
        # Formatting
        ax.set_title(f"Current Traffic Flow (Total: {traffic_input} MB/s)")
        ax.axis('off')
        
        # Render in Streamlit
        st.pyplot(fig)

    # --- LOGS & METRICS (Backend Integration) ---
    with col_logs:
        st.subheader("System Status")
        
        # 1. Display Logs
        if log_messages:
            for msg in log_messages:
                if "CRITICAL" in msg:
                    st.error(msg)
                elif "Defense" in msg:
                    st.success(msg)
                else:
                    st.info(msg)
        else:
            st.write("✅ System operating within normal parameters.")

        st.markdown("---")
        st.subheader("🧮 Backend Metrics")
        
        # 2. Calculate Reliability using Backend Class
        # We simulate a snapshot at T=1 hour for the current load
        sw_load = traffic_input / 2 
        if enable_ans: sw_load = sw_load / ratio
        
        fail_rate = ReliabilityMath.calculate_failure_rate('SwA1', sw_load, alpha=0.005)
        reliability = ReliabilityMath.calculate_reliability(fail_rate, time_t=24) # 24 Hour projection
        
        # Display Metrics
        st.metric("Projected Reliability (24h)", f"{reliability:.5f}")
        st.metric("Failure Rate (h(t))", f"{fail_rate:.2e}")
        
        if enable_ans:
            st.metric("Compression Benefit", f"{ratio:.2f}x Reduction")

if __name__ == "__main__":
    main()