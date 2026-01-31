import streamlit as st
import pandas as pd
from orchestrator import app as logic_engine, generate_schedule

st.set_page_config(page_title="EVE | The Divine Frame", layout="wide", page_icon="✨")

st.markdown("""
<style>
    /* BACKGROUND: Deep Void with Rose Gold Undertones */
    .stApp {
        background: radial-gradient(circle at 50% 10%, #1a0b0e 0%, #000000 100%);
        color: #fceceb;
    }
    
    /* GLASS ORGANS (Pearl Effect) */
    .metric-card {
        background: rgba(255, 240, 245, 0.03);
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 200, 210, 0.15);
        border-radius: 25px;
        padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
    }
    
    /* HOMEOSTASIS (Soft Teal Glow) */
    .glow-homeostasis {
        background: rgba(100, 255, 218, 0.05);
        border: 1px solid rgba(100, 255, 218, 0.2);
        color: #aaffdd;
        padding: 15px; border-radius: 15px;
    }
    
    /* INFLAMMATION (Rose Gold/Red Glow) */
    .glow-inflammation {
        background: rgba(255, 100, 100, 0.05);
        border: 1px solid rgba(255, 150, 150, 0.3);
        color: #ffcccc;
        padding: 15px; border-radius: 15px;
    }

    /* TYPOGRAPHY */
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; font-weight: 100; letter-spacing: 4px; color: #fff0f5; }
    .label { font-size: 10px; text-transform: uppercase; letter-spacing: 2px; opacity: 0.7; margin-bottom: 5px; color: #eebbcc; }
    .value { font-size: 32px; font-weight: 200; text-shadow: 0 0 20px rgba(255,200,210,0.3); }
    
</style>
""", unsafe_allow_html=True)

# HEADER
c1, c2 = st.columns([3, 1])
with c1:
    st.title("E V E")
    st.caption("THE DIVINE FEMININE FRAME")
with c2:
    st.markdown("<div style='text-align:right; opacity:0.7; letter-spacing:2px'>SYSTEM: ALIVE</div>", unsafe_allow_html=True)

st.divider()

# SIDEBAR (Hidden in Glass)
with st.sidebar:
    st.header("Metabolic Inputs")
    util_reception = st.slider("Intake (Mouth)", 0, 20, 8)
    util_numbing = st.slider("Prep (Digestion)", 0.0, 1.0, 0.40)
    util_laser = st.slider("Treatment (The Heart)", 0.0, 1.0, 0.60)
    util_checkout = st.slider("Release (Flow)", 0.0, 1.0, 0.80)
    
    if st.button("SYNC BIOLOGY"):
        schedule = generate_schedule() 
        mock_input = {
            "resources": {
                "Reception": {"queue": util_reception, "util": util_reception/20},
                "Numbing Room": {"queue": 0, "util": util_numbing},
                "Laser Room": {"queue": 0, "util": util_laser}, 
                "Checkout": {"queue": 0, "util": util_checkout}
            },
            "schedule": schedule,
            "bottleneck_rate": 0.0,
            "backpressure_score": 0.0,
            "system_flow_rate": 0.0,
            "lobby_wait_time": 0,
            "constraints": [],
            "decisions": [],
            "logs": []
        }
        st.session_state['last_result'] = logic_engine.invoke(mock_input)

# BODY
if 'last_result' in st.session_state:
    res = st.session_state['last_result']
    
    # 1. ORGAN STATUS
    st.markdown("### I. ORGANIC FUNCTION")
    k1, k2, k3, k4 = st.columns(4)
    
    def card(label, val, sub):
        return f"<div class='metric-card'><div class='label'>{label}</div><div class='value'>{val}</div><div style='font-size:12px; opacity:0.5'>{sub}</div></div>"

    with k1:
        speed = res['bottleneck_rate'] * 100
        st.markdown(card("Circulation", f"{speed:.0f}%", "Pulse Velocity"), unsafe_allow_html=True)
    with k2:
        bp = res['backpressure_score']
        st.markdown(card("Internal Pressure", f"{bp:.0f}%", "System Resistance"), unsafe_allow_html=True)
    with k3:
        wait = res['lobby_wait_time']
        st.markdown(card("Intake Latency", f"{wait} min", "Queue Decay"), unsafe_allow_html=True)
    with k4:
        st.markdown(card("Immune Response", "ACTIVE", "Eve Agent"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. NERVOUS SYSTEM
    c_logic, c_dna = st.columns([1, 2])
    
    with c_logic:
        st.markdown("### II. NERVOUS SYSTEM")
        decisions = res['decisions']
        if decisions:
            for d in decisions:
                if "DEPLOY" in d:
                    st.markdown(f"<div class='glow-inflammation'>⚡ <b>INTERVENTION</b><br>{d}<br><span style='font-size:11px; opacity:0.8'>Rerouting to Virtual Circuit</span></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='glow-homeostasis'>🟢 <b>HOMEOSTASIS</b><br>{d}</div>", unsafe_allow_html=True)
        else:
            st.info("Awaiting Stimulus...")

    with c_dna:
        st.markdown("### III. DNA SEQUENCE (Ontology)")
        schedule_data = []
        for p in res['schedule']:
            schedule_data.append({
                "Cell Name": p['name'],
                "Nutrient": p['treatment'],
                "Energy": f"${p['value']}",
                "Viability": f"{p['show_up_prob']*100:.0f}%"
            })
        st.dataframe(pd.DataFrame(schedule_data), use_container_width=True, hide_index=True)

else:
    st.info("Initialize the Divine System to begin.")
