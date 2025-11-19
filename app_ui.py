import streamlit as st
import networkx as nx
import plotly.graph_objects as go
import random

# Import Backend
try:
    from simulation_backend import ReliabilityMath, TopologyManager
except ImportError:
    st.error("❌ Error: 'simulation_backend.py' not found.")
    st.stop()

st.set_page_config(page_title="Active SAN Visualization", layout="wide")

# --- INITIALIZATION ---
if 'nodes' not in st.session_state:
    st.session_state['nodes'] = ['Server-1', 'SwA1', 'SwB1', 'SwA2', 'SwB2', 'Storage-1']
if 'edges' not in st.session_state:
    st.session_state['edges'] = [
        ('Server-1', 'SwA1'), ('Server-1', 'SwB1'), 
        ('SwA1', 'SwA2'), ('SwB1', 'SwB2'), 
        ('SwA2', 'Storage-1'), ('SwB2', 'Storage-1'),
        ('SwA1', 'SwB1'), ('SwA2', 'SwB2')
    ]

# --- CONTROLS ---
st.sidebar.header("1. Controls")
scenario = st.sidebar.radio("Scenario", ["1. Baseline", "2. ANS Compression", "3. Rerouting", "4. Full Defense"])
traffic_input = st.sidebar.slider("Traffic Load (MB/s)", 0, 3000, 1800)
threshold = 1000

st.sidebar.markdown("---")
st.sidebar.header("2. Topology")
mode = st.sidebar.selectbox("Mode", ["Predefined Mesh", "Custom Builder"])

G = nx.DiGraph()
pos = {}

if mode == "Predefined Mesh":
    G, pos = TopologyManager.get_predefined_topology("Mesh (Standard)")
else:
    G.add_nodes_from(st.session_state['nodes'])
    G.add_edges_from(st.session_state['edges'])
    pos = nx.spring_layout(G, seed=42)

# --- RUN BACKEND SIMULATION ---
node_data, logs, ratio = ReliabilityMath.simulate_traffic_flow(G, traffic_input, scenario, threshold)

# --- VISUALIZATION FUNCTION ---
def draw_flow_graph(G, pos, node_data, scenario_mode, limit):
    fig = go.Figure()

    # 1. DRAW PIPES (EDGES)
    for edge in G.edges():
        start, end = edge
        if start not in pos or end not in pos: continue
        x0, y0 = pos[start]
        x1, y1 = pos[end]
        
        # Status checks
        start_status = node_data.get(start, {})
        end_status = node_data.get(end, {})
        is_horizontal = abs(y0 - y1) < 0.5 
        
        # Default Style
        line_color = '#888888'
        line_dash = 'solid'
        label_text = "" 
        show_arrow = True
        width = 2

        # LOGIC: What does this pipe look like?
        
        # A. DEAD PATH (Source Died)
        if start_status.get('state') == 'Dead':
            line_color = '#444444' # Dark Grey
            line_dash = 'dot'
            label_text = "DISCONNECTED"
            show_arrow = False
            
        # B. REROUTE PATH (Horizontal)
        elif is_horizontal:
            # Only show if Active Reroute happened
            if ("Rerouting" in scenario_mode or "Full" in scenario_mode) and start_status.get('state') == 'Rerouted':
                line_color = '#FFA15A' # Orange
                width = 4
                # Parse logs to find amount moved (simple heuristic for visualization)
                moved_amount = int(node_data[end]['load'] - (limit * 0.9)) if node_data[end]['load'] > 0 else 0
                # If exact calc fails, just show generic "Reroute"
                label_text = f"REROUTING<br>~{moved_amount} MB" if moved_amount > 0 else "REROUTING"
            else:
                # Inactive Backup Path
                line_color = '#EEEEEE' 
                line_dash = 'dot'
                show_arrow = False
                
        # C. NORMAL PATH (Vertical)
        else:
            current_flow = int(end_status.get('load', 0))
            label_text = f"{current_flow} MB"
            
            # Overload Check
            if current_flow > limit:
                line_color = '#EF553B' # Red
                width = 4
                label_text += " (CRITICAL)"

        # DRAW LINE
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1],
            line=dict(width=width, color=line_color, dash=line_dash),
            hoverinfo='none', mode='lines'
        ))

        # DRAW ARROW & LABEL
        if show_arrow:
            mid_x = (x0 + x1) / 2
            mid_y = (y0 + y1) / 2
            
            fig.add_annotation(
                x=mid_x, y=mid_y,
                text=label_text,
                showarrow=True,
                arrowhead=2,
                arrowsize=1.5,
                arrowwidth=1,
                arrowcolor=line_color,
                ax=(x0 + mid_x)/2, ay=(y0 + mid_y)/2,
                bgcolor="white", # White Box for Text
                bordercolor=line_color,
                borderwidth=1,
                font=dict(size=10, color="black")
            )

    # 2. DRAW NODES
    node_x, node_y, node_c, node_txt, border_c = [], [], [], [], []
    for node in G.nodes():
        if node not in pos: continue
        x, y = pos[node]
        node_x.append(x); node_y.append(y)
        
        data = node_data.get(node, {'load': 0, 'color': 'grey'})
        node_c.append(data['color'])
        
        hover = f"<b>{node}</b><br>Load: {int(data['load'])} MB/s<br>State: {data.get('state', 'OK')}"
        node_txt.append(hover)
        border_c.append('black')

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode='markers+text',
        text=list(G.nodes()), textposition="top center",
        hoverinfo='text', hovertext=node_txt,
        marker=dict(size=45, color=node_c, line=dict(width=2, color=border_c))
    ))

    fig.update_layout(showlegend=False, margin=dict(b=0,l=0,r=0,t=0), xaxis={'visible':False}, yaxis={'visible':False}, height=600)
    return fig

# --- RENDER UI ---
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader(f"Network Flow: {scenario}")
    if len(G.nodes) > 0:
        st.plotly_chart(draw_flow_graph(G, pos, node_data, scenario, threshold), use_container_width=True)

with col2:
    st.subheader("Analysis")
    max_load = max([d['load'] for d in node_data.values()]) if node_data else 0
    
    st.metric("Max Load", f"{int(max_load)} MB/s", help=f"Limit: {threshold}")
    if ratio > 1.0: st.metric("Compression", f"{ratio:.2f}x")
    
    st.write("---")
    for msg in logs:
        if "FAIL" in msg: st.error(msg)
        elif "Reroute" in msg: st.warning(msg)
        elif "ANS" in msg: st.success(msg)
        else: st.info(msg)