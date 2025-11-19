import streamlit as st
import networkx as nx
import plotly.graph_objects as go
import numpy as np

try:
    from simulation_backend import ReliabilityMath, TopologyManager
except ImportError:
    st.error("❌ Error: 'simulation_backend.py' not found.")
    st.stop()

st.set_page_config(page_title="Active SAN Visualization", layout="wide")

# --- SESSION STATE ---
if 'custom_nodes' not in st.session_state: st.session_state['custom_nodes'] = []
if 'custom_edges' not in st.session_state: st.session_state['custom_edges'] = []

# --- UNIFIED SIDEBAR ---
st.sidebar.header("1. System Config")
mode = st.sidebar.radio("Select Topology", 
    ["N+1 Redundancy", "Full Mesh", "Fat-Tree", "Ring Topology", "Custom Builder"]
)

st.sidebar.markdown("---")
st.sidebar.header("2. Simulation Controls")
traffic_input = st.sidebar.slider("Traffic Load (MB/s)", 0, 3000, 2500) 
scenario = st.sidebar.radio("Defense Strategy", ["Baseline", "ANS Compression", "Dynamic Rerouting", "Full Defense"])

# --- TOPOLOGY & SIMULATION ---
G = None
pos = None

if mode == "Custom Builder":
    st.sidebar.markdown("---")
    st.sidebar.subheader("Custom Builder Tools")
    with st.sidebar.expander("Add Components", expanded=True):
        c_name = st.text_input("Name (e.g. Sw1)", key="c_name")
        c_type = st.selectbox("Type", ["Server", "Switch", "Storage"], key="c_type")
        if st.button("Add Component"):
            name = f"{c_type}-{c_name}" if c_name else f"{c_type}-{len(st.session_state['custom_nodes'])}"
            if name not in st.session_state['custom_nodes']:
                st.session_state['custom_nodes'].append(name)
    
    with st.sidebar.expander("Connect Components", expanded=True):
        if len(st.session_state['custom_nodes']) > 1:
            src = st.selectbox("From", st.session_state['custom_nodes'])
            tgt = st.selectbox("To", st.session_state['custom_nodes'])
            if st.button("Link"):
                if src != tgt: st.session_state['custom_edges'].append((src, tgt))

    if st.sidebar.button("Reset Topology"):
        st.session_state['custom_nodes'] = []
        st.session_state['custom_edges'] = []
        st.experimental_rerun()
    
    G, pos = TopologyManager.build_custom_topology(st.session_state['custom_nodes'], st.session_state['custom_edges'])

elif mode == "N+1 Redundancy":
    G, pos = TopologyManager.get_predefined_topology("N+1 Redundancy")

else:
    G, pos = TopologyManager.get_predefined_topology(mode)

# Run Simulation
node_data, logs, ratio, edge_flows = ReliabilityMath.simulate_traffic_flow(G, traffic_input, scenario, 1000)


# --- VISUALIZATION ---
def draw_hybrid_graph(G, pos, node_data, edge_flows):
    fig = go.Figure()
    annotations = [] 

    # 1. EDGES
    for edge in G.edges():
        u, v = edge
        if u not in pos or v not in pos: continue
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        flow = edge_flows.get(edge, 0)
        
        if flow > 0:
            if flow > 1000: 
                color = '#EF553B' # Red
                width = 4
            elif "Standby" in u or "Standby" in v:
                color = '#FFA15A' # Orange
                width = 3
            else:
                color = '#888888' # Grey
                width = 3
            dash = 'solid' if "Standby" not in str(edge) else 'dash'
        else:
            color = '#E5E5E5' 
            width = 2
            dash = 'dot'

        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1],
            mode='lines',
            line=dict(width=width, color=color, dash=dash),
            hoverinfo='none'
        ))

        if flow > 0:
            mid_x = (x0 + x1) / 2
            mid_y = (y0 + y1) / 2
            annotations.append(dict(
                x=mid_x, y=mid_y,
                text=f"<b>{int(flow)}</b>",
                font=dict(color="black", size=10),
                showarrow=False,
                bgcolor="white",
                bordercolor=color,
                borderwidth=1,
                opacity=0.9
            ))

    # 2. NODES
    node_x, node_y, node_c, node_s, node_txt = [], [], [], [], []
    for n in G.nodes():
        x, y = pos[n]
        node_x.append(x); node_y.append(y)
        data = node_data.get(n, {'color': 'grey', 'load': 0})
        node_c.append(data['color'])
        
        if "Standby" in n and data['load'] == 0:
            node_s.append(15)
        else:
            node_s.append(45)
            
        # UPDATED HOVER TEXT LOGIC
        capacity = data.get('capacity', 'N/A')
        state = data.get('state', 'Unknown')
        load = int(data['load'])
        
        # Formatting the tooltip
        tooltip = (
            f"<b>{n}</b><br>"
            f"Status: {state}<br>"
            f"Load: {load} MB/s<br>"
            f"Capacity: {capacity}"
        )
        node_txt.append(tooltip)

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=[n.split('-')[0] for n in G.nodes()], 
        textposition='middle center',
        textfont=dict(color='white', size=9, weight='bold'),
        hoverinfo='text', 
        hovertext=node_txt, # Applying the new tooltip
        marker=dict(size=node_s, color=node_c, line=dict(width=2, color='#333'))
    ))

    # 3. ANIMATION
    frames = []
    num_frames = 30 
    
    for k in range(num_frames):
        t = k / (num_frames - 1)
        p_x, p_y, p_c = [], [], []
        
        for edge, flow in edge_flows.items():
            if flow > 0:
                u, v = edge
                x0, y0 = pos[u]; x1, y1 = pos[v]
                
                curr_x = x0 + (x1 - x0) * t
                curr_y = y0 + (y1 - y0) * t
                
                p_x.append(curr_x)
                p_y.append(curr_y)
                
                if flow > 1000: p_c.append('#FF0000')
                elif "Standby" in str(edge): p_c.append('#FFA500')
                else: p_c.append('#FFFFFF')

        frames.append(go.Frame(
            data=[go.Scatter(
                x=p_x, y=p_y,
                mode='markers',
                marker=dict(color=p_c, size=6, line=dict(width=1, color='#333'))
            )],
            name=str(k)
        ))

    fig.add_trace(go.Scatter(
        x=[], y=[], mode='markers', marker=dict(size=6, color='white')
    ))

    fig.update_layout(
        height=600,
        showlegend=False,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor='rgba(0,0,0,0)',
        annotations=annotations,
        updatemenus=[dict(
            type="buttons",
            showactive=False,
            x=0.05, y=0.95,
            buttons=[dict(
                label="▶ Simulate Flow",
                method="animate",
                args=[None, dict(frame=dict(duration=50, redraw=False), fromcurrent=True, mode="immediate", loop=True)]
            )]
        )]
    )
    
    fig.frames = frames
    return fig

# --- RENDER MAIN UI ---
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader(f"Topology: {mode}")
    if G.number_of_nodes() > 0:
        st.plotly_chart(draw_hybrid_graph(G, pos, node_data, edge_flows), use_container_width=True)
    else:
        st.info("👈 Use the sidebar to build your network.")

with col2:
    st.subheader("Live Metrics")
    
    mx = max([d['load'] for d in node_data.values()]) if node_data else 0
    st.metric("Peak System Load", f"{int(mx)} MB/s")
    
    if mode == "N+1 Redundancy":
        saved = node_data.get('Sw-Standby', {}).get('load', 0)
        st.metric("Traffic Rerouted", f"{int(saved)} MB/s", delta="Protected" if saved > 0 else "Idle")
    else:
        if "ANS" in scenario:
            st.metric("Compression Savings", f"{ratio:.2f}x Ratio")

    st.write("---")
    st.write("**Event Log**")
    for msg in logs:
        if "FAIL" in msg or "CRASHED" in msg: st.error(msg)
        elif "Reroute" in msg or "capped" in msg: st.warning(msg)
        elif "ANS" in msg: st.success(msg)
        else: st.info(msg)