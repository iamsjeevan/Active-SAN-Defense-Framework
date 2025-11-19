import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt

# --- Configuration ---
st.set_page_config(page_title="SAN Reliability Dashboard", layout="wide")
SWITCH_CAPACITY_MBPS = 1000  # Assume each switch handles up to 1000 MB/s

def build_san_topology():
    """
    Creates the NetworkX Graph for the SAN Topology.
    Returns: Graph object (G) and Positions (pos) for plotting.
    """
    G = nx.DiGraph()

    # 1. Define Nodes
    nodes = ['Server', 'SwA1', 'SwB1', 'SwA2', 'SwB2', 'Storage']
    G.add_nodes_from(nodes)

    # 2. Define Edges (Mesh Topology)
    # Traffic flows from Server -> Row 1 Switches -> Row 2 Switches -> Storage
    edges = [
        ('Server', 'SwA1'), ('Server', 'SwB1'),    # Server links
        ('SwA1', 'SwA2'), ('SwA1', 'SwB2'),        # SwA1 cross-links
        ('SwB1', 'SwA2'), ('SwB1', 'SwB2'),        # SwB1 cross-links
        ('SwA2', 'Storage'), ('SwB2', 'Storage')   # Storage links
    ]
    G.add_edges_from(edges)

    # 3. Define Static Positions for a clean hierarchical view
    pos = {
        'Server':  (0, 3),
        'SwA1':   (-1, 2), 'SwB1': (1, 2),
        'SwA2':   (-1, 1), 'SwB2': (1, 1),
        'Storage': (0, 0)
    }
    
    return G, pos

def get_node_colors(G, loads):
    """
    Determines node colors based on load percentage.
    Green < 50%, Yellow < 80%, Red >= 80%.
    """
    colors = []
    for node in G.nodes():
        # Default Server and Storage to Grey/Blue (metrics usually focus on switches)
        if node in ['Server', 'Storage']:
            colors.append('#A0CBE2') 
            continue

        # Calculate Load Percentage
        current_load = loads.get(node, 0)
        usage_pct = (current_load / SWITCH_CAPACITY_MBPS) * 100

        if usage_pct < 50:
            colors.append('#90EE90') # Green
        elif usage_pct < 80:
            colors.append('#FFD700') # Yellow
        else:
            colors.append('#FF6347') # Red
            
    return colors

def redistribute_traffic(current_loads):
    """
    Novelty #2: Dynamic Load Redistribution Algorithm.
    Logic: If a switch > 80% capacity, move 50% of excess traffic 
    to its horizontal neighbor.
    """
    updated_loads = current_loads.copy()
    capacity_threshold = 0.8 * SWITCH_CAPACITY_MBPS
    
    # Define redundant pairs (Neighbors)
    pairs = [('SwA1', 'SwB1'), ('SwA2', 'SwB2')]

    reroute_log = []

    for sw1, sw2 in pairs:
        # Check Sw1 -> Sw2
        if updated_loads[sw1] > capacity_threshold:
            excess = updated_loads[sw1] - capacity_threshold
            # Only move if neighbor is safe (below threshold)
            if updated_loads[sw2] < capacity_threshold:
                move_amount = excess * 0.5
                updated_loads[sw1] -= move_amount
                updated_loads[sw2] += move_amount
                reroute_log.append(f"Rerouted {move_amount:.1f} MB/s from {sw1} to {sw2}")

        # Check Sw2 -> Sw1 (Symmetric check)
        elif updated_loads[sw2] > capacity_threshold:
            excess = updated_loads[sw2] - capacity_threshold
            if updated_loads[sw1] < capacity_threshold:
                move_amount = excess * 0.5
                updated_loads[sw2] -= move_amount
                updated_loads[sw1] += move_amount
                reroute_log.append(f"Rerouted {move_amount:.1f} MB/s from {sw2} to {sw1}")

    return updated_loads, reroute_log

# --- Main App UI ---
def main():
    st.title("🛡️ SAN Reliability Dashboard")
    st.markdown("**Project:** Dynamic Load Redistribution in Storage Area Networks")
    
    col1, col2 = st.columns([1, 3])

    # --- Sidebar Controls ---
    with st.sidebar:
        st.header("Network Controls")
        
        # Input Traffic
        total_traffic = st.slider("Total Input Traffic (MB/s)", 0, 2000, 1200)
        
        st.subheader("Traffic Distribution (Simulation)")
        st.info("Simulate an imbalance to test the algorithm.")
        imbalance = st.slider("Traffic Skew (SwA vs SwB)", 0.0, 1.0, 0.9, 
                              help="1.0 means all traffic hits Path A. 0.5 is balanced.")
        
        # Algorithm Toggle
        enable_algo = st.checkbox("Enable Dynamic Rerouting", value=False)
        
        st.markdown("---")
        st.write(f"**Switch Capacity:** {SWITCH_CAPACITY_MBPS} MB/s")

    # --- Logic Calculation ---
    
    # 1. Simulate Base Loads (Dummy Data based on sliders)
    # We assume Traffic flows into Row 1 (SwA1/B1) and cascades to Row 2 (SwA2/B2)
    load_swa1 = total_traffic * imbalance
    load_swb1 = total_traffic * (1 - imbalance)
    
    # Simple cascade logic: SwA1 sends mostly to SwA2, SwB1 to SwB2
    load_swa2 = load_swa1 * 0.9 
    load_swb2 = load_swb1 * 0.9

    current_loads = {
        'Server': 0, 'Storage': 0,
        'SwA1': load_swa1, 'SwB1': load_swb1,
        'SwA2': load_swa2, 'SwB2': load_swb2
    }

    # 2. Apply Algorithm if Enabled
    reroute_messages = []
    if enable_algo:
        current_loads, reroute_messages = redistribute_traffic(current_loads)

    # --- Visualization ---
    
    with col2:
        st.subheader("Network Topology & Status")
        
        G, pos = build_san_topology()
        node_colors = get_node_colors(G, current_loads)
        
        # Draw Graph using Matplotlib
        fig, ax = plt.subplots(figsize=(8, 5))
        nx.draw(
            G, pos, ax=ax,
            with_labels=True,
            node_color=node_colors,
            node_size=2000,
            edge_color="gray",
            font_size=10,
            font_weight="bold",
            arrows=True,
            arrowsize=20
        )
        
        # Add labels for load values on the plot
        # Offset the label slightly below the node
        label_pos = {k: (v[0], v[1] - 0.25) for k, v in pos.items()}
        load_labels = {
            k: f"{int(v)} MB/s" if k not in ['Server', 'Storage'] else "" 
            for k, v in current_loads.items()
        }
        nx.draw_networkx_labels(G, label_pos, labels=load_labels, font_size=8, font_color="blue")
        
        # Legend manually added via text
        plt.text(-1.5, 3, "Status Legend:", fontsize=9, fontweight='bold')
        plt.text(-1.5, 2.8, "● Normal (<50%)", color='green')
        plt.text(-1.5, 2.6, "● Warning (50-80%)", color='#D4AF37') # Darker yellow for text
        plt.text(-1.5, 2.4, "● Critical (>80%)", color='red')
        
        plt.margins(0.2)
        st.pyplot(fig)

    # --- Metrics & Logs ---
    with col1:
        st.subheader("System Status")
        
        # Determine overall system health
        max_load = max([current_loads[n] for n in ['SwA1', 'SwB1', 'SwA2', 'SwB2']])
        max_pct = (max_load / SWITCH_CAPACITY_MBPS) * 100
        
        if max_pct > 80:
            status_label = "CRITICAL"
            status_color = "inverse" # Renders red background in delta
        elif max_pct > 50:
            status_label = "WARNING"
            status_color = "off"
        else:
            status_label = "SAFE"
            status_color = "normal"

        st.metric(label="Peak Utilization", value=f"{max_pct:.1f}%", delta=status_label, delta_color=status_color)
        
        st.write("### Switch Loads")
        for sw in ['SwA1', 'SwB1', 'SwA2', 'SwB2']:
            val = current_loads[sw]
            st.progress(min(val / SWITCH_CAPACITY_MBPS, 1.0), text=f"{sw}: {int(val)} MB/s")

        if enable_algo and reroute_messages:
            st.success("Algorithm Active")
            with st.expander("Rerouting Logs", expanded=True):
                for msg in reroute_messages:
                    st.write(f"✅ {msg}")
        elif enable_algo:
             st.info("Algorithm Active: No rerouting needed.")

if __name__ == "__main__":
    main()