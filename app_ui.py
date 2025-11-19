import streamlit as st
import networkx as nx
import plotly.graph_objects as go
import random

try:
    from simulation_backend import ReliabilityMath, TopologyManager
except ImportError:
    st.error("❌ Error: 'simulation_backend.py' not found.")
    st.stop()

st.set_page_config(page_title="Active SAN Visualization", layout="wide")

# --- SESSION STATE ---
if 'nodes' not in st.session_state:
    st.session_state['nodes'] = ['Server-1', 'SwA1', 'SwB1', 'Sw-Standby', 'SwA2', 'SwB2', 'Storage-1']

st.sidebar.header("1. Controls")
# NOTE: Slider default set to 1800 to demonstrate the split
traffic_input = st.sidebar.slider("Traffic Load (MB/s)", 0, 3000, 1800) 
scenario = st.sidebar.radio("Defense Mode", ["1. Baseline", "2. ANS Compression", "3. Rerouting (N+1)", "4. Full Defense"])
threshold = 1000

# --- SIMULATION ---
G, pos = TopologyManager.get_predefined_topology("Mesh (Standard)")
node_data, logs, ratio, edge_flows = ReliabilityMath.simulate_traffic_flow(G, traffic_input, scenario, threshold)

# --- VISUALIZATION ---
def draw_flow_graph(G, pos, node_data, edge_flows):
    fig = go.Figure()

    # 1. DRAW PIPES (EDGES)
    for edge in G.edges():
        start, end = edge
        if start not in pos or end not in pos: continue
        x0, y0 = pos[start]; x1, y1 = pos[end]
        
        # Get exact flow calculated by backend
        flow = int(edge_flows.get(edge, 0))
        
        # VISUAL LOGIC
        if flow == 0:
            # If no flow, draw faint ghost line (or hidden)
            line_color = '#EEEEEE'
            line_dash = 'dot'
            width = 1
            show_arrow = False
            label = ""
        else:
            # Active Flow
            show_arrow = True
            label = f"{flow} MB"
            width = 3
            
            # Color Logic
            if "Standby" in end or "Standby" in start:
                line_color = '#FFA15A' # Orange for Reroute
                line_dash = 'dash'
            else:
                line_color = '#888888' # Grey for Main
                line_dash = 'solid'
                
                # Check if this specific pipe is overloaded (simplified visual check)
                if flow > threshold:
                    line_color = '#EF553B' # Red

        # Draw Line
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1],
            line=dict(width=width, color=line_color, dash=line_dash),
            hoverinfo='none', mode='lines'
        ))

        # Draw Label
        if show_arrow:
            mid_x = (x0 + x1) / 2; mid_y = (y0 + y1) / 2
            fig.add_annotation(
                x=mid_x, y=mid_y, text=label, showarrow=True,
                arrowhead=2, arrowsize=1, arrowwidth=width, arrowcolor=line_color,
                ax=(x0 + mid_x)/2, ay=(y0 + mid_y)/2,
                bgcolor="white", bordercolor=line_color, borderwidth=1,
                font=dict(size=10, color="black")
            )

    # 2. DRAW NODES
    node_x, node_y, node_c, node_txt, border_c, node_s = [], [], [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x); node_y.append(y)
        
        data = node_data.get(node, {'load': 0, 'color': 'grey'})
        node_c.append(data['color'])
        
        # Size Logic: Hide Standby if unused
        if "Standby" in node and data['state'] == 'Idle':
             node_s.append(15) # Tiny dot
             border_c.append('#DDDDDD')
        else:
             node_s.append(45) # Normal bubble
             border_c.append('black')

        hover = f"<b>{node}</b><br>Load: {int(data['load'])} MB<br>Status: {data.get('state','OK')}"
        node_txt.append(hover)

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode='markers+text',
        text=list(G.nodes()), textposition="top center",
        hoverinfo='text', hovertext=node_txt,
        marker=dict(size=node_s, color=node_c, line=dict(width=2, color=border_c))
    ))

    fig.update_layout(showlegend=False, margin=dict(b=0,l=0,r=0,t=0), xaxis={'visible':False}, yaxis={'visible':False}, height=600)
    return fig

# --- RENDER ---
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader(f"N+1 Topology View: {scenario}")
    st.plotly_chart(draw_flow_graph(G, pos, node_data, edge_flows), use_container_width=True)

with col2:
    st.subheader("Metrics")
    max_load = max([d['load'] for d in node_data.values()])
    st.metric("Max Load", f"{int(max_load)} MB/s")
    
    # Calculate Total Saved
    saved_flow = node_data['Sw-Standby']['load']
    if saved_flow > 0:
        st.metric("Rerouted Traffic", f"{int(saved_flow)} MB/s", delta="Saved by N+1")
    
    st.write("---")
    for msg in logs:
        if "FAIL" in msg: st.error(msg)
        elif "Reroute" in msg: st.warning(msg)
        elif "ANS" in msg: st.success(msg)