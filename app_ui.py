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

# --- SIDEBAR ---
st.sidebar.header("1. System Config")
mode = st.sidebar.radio("Select Topology", 
    ["N+1 Redundancy", "Full Mesh", "Fat-Tree", "Ring Topology", "Custom Builder"]
)

st.sidebar.markdown("---")
st.sidebar.header("2. Simulation Controls")
traffic_input = st.sidebar.slider("Traffic Load (MB/s)", 0, 3000, 2500) 
scenario = st.sidebar.radio("Defense Strategy", ["Baseline", "ANS Compression", "Dynamic Rerouting", "Full Defense"])

# --- SIMULATION LOGIC ---
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

node_data, logs, ratio, edge_flows = ReliabilityMath.simulate_traffic_flow(G, traffic_input, scenario, 1000)


# --- VISUALIZATION FUNCTION (STABLE ANIMATION) ---
def draw_hybrid_graph(G, pos, node_data, edge_flows):
    fig = go.Figure()
    annotations = [] 

    # --- 1. GROUPED EDGE TRACES (Fixes Disappearing Lines) ---
    # We collect coordinates for all edges of a specific type, then draw them as ONE trace.
    # 'None' is used to break the line between different edges in the same trace.
    
    trace_groups = {
        'grey': {'x': [], 'y': [], 'color': '#888888', 'width': 3, 'dash': 'solid'},
        'red': {'x': [], 'y': [], 'color': '#EF553B', 'width': 4, 'dash': 'solid'},
        'orange': {'x': [], 'y': [], 'color': '#FFA15A', 'width': 3, 'dash': 'dash'},
        'dotted': {'x': [], 'y': [], 'color': '#E5E5E5', 'width': 2, 'dash': 'dot'}
    }

    for edge in G.edges():
        u, v = edge
        if u not in pos or v not in pos: continue
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        flow = edge_flows.get(edge, 0)

        # Determine Group
        group_key = 'dotted'
        if flow > 0:
            if flow > 1000: group_key = 'red'
            elif "Standby" in u or "Standby" in v: group_key = 'orange'
            else: group_key = 'grey'
        
        # Add Coordinates + None to break line
        trace_groups[group_key]['x'].extend([x0, x1, None])
        trace_groups[group_key]['y'].extend([y0, y1, None])

        # Add Annotation (Text Box)
        if flow > 0:
            mid_x = (x0 + x1) / 2
            mid_y = (y0 + y1) / 2
            # Match box border to line color
            box_color = trace_groups[group_key]['color']
            
            annotations.append(dict(
                x=mid_x, y=mid_y,
                text=f"<b>{int(flow)}</b>",
                font=dict(color="black", size=10),
                showarrow=False,
                bgcolor="white",
                bordercolor=box_color,
                borderwidth=1,
                opacity=0.9
            ))

    # Add the 4 Static Edge Layers
    for key, style in trace_groups.items():
        if style['x']: # Only add if there are edges in this group
            fig.add_trace(go.Scatter(
                x=style['x'], y=style['y'],
                mode='lines',
                line=dict(width=style['width'], color=style['color'], dash=style['dash']),
                hoverinfo='none',
                name=key # Helper for debug
            ))

    # --- 2. NODES ---
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
            
        tooltip = (
            f"<b>{n}</b><br>"
            f"Status: {data.get('state', 'Unknown')}<br>"
            f"Load: {int(data['load'])} MB/s<br>"
            f"Capacity: {data.get('capacity', 'N/A')}"
        )
        node_txt.append(tooltip)

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=[n.split('-')[0] for n in G.nodes()], 
        textposition='middle center',
        textfont=dict(color='white', size=9, weight='bold'),
        hoverinfo='text', hovertext=node_txt,
        marker=dict(size=node_s, color=node_c, line=dict(width=2, color='#333'))
    ))

    # --- 3. ANIMATION SETUP ---
    # We need to identify the index of the next trace we add, so the animation knows what to update.
    # Current traces = (up to 4 edge traces) + (1 node trace)
    packet_trace_index = len(fig.data)

    # Add Dummy Packet Trace (Placeholder)
    fig.add_trace(go.Scatter(
        x=[], y=[], mode='markers', 
        marker=dict(size=6, line=dict(width=1, color='#333'))
    ))

    # --- 4. ANIMATION FRAMES (Multiple Packets) ---
    frames = []
    num_frames = 40 # Higher = Smoother
    
    # Create offsets to simulate multiple packets on the line
    packet_offsets = [0.0,0.2,0.4,0.6,0.8,1.0] 

    for k in range(num_frames):
        base_t = k / (num_frames - 1)
        p_x, p_y, p_c = [], [], []
        
        for edge, flow in edge_flows.items():
            if flow > 0:
                u, v = edge
                x0, y0 = pos[u]; x1, y1 = pos[v]
                
                # Generate Multiple Packets per Edge
                for offset in packet_offsets:
                    # Calculate t with wrapping (modulo)
                    t = (base_t + offset) % 1.0
                    
                    curr_x = x0 + (x1 - x0) * t
                    curr_y = y0 + (y1 - y0) * t
                    
                    p_x.append(curr_x)
                    p_y.append(curr_y)
                    
                    # Color Logic
                    if flow > 1000: p_c.append('#FF0000')
                    elif "Standby" in str(edge): p_c.append('#FFA500')
                    else: p_c.append('#FFFFFF')

        # Define the Frame
        # IMPORTANT: traces=[packet_trace_index] ensures we ONLY update the packets
        # and don't redraw/clear the static edge lines.
        frames.append(go.Frame(
            data=[go.Scatter(
                x=p_x, y=p_y,
                mode='markers',
                marker=dict(color=p_c, size=6, line=dict(width=1, color='#333'))
            )],
            traces=[packet_trace_index], 
            name=str(k)
        ))

    # --- 5. LAYOUT CONFIG ---
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

# --- RENDER ---
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