import os

print("✨ INITIATING RE-GENESIS PROTOCOL...")

# 1. REPAIR THE BRAIN (orchestrator.py)
# This restores the missing 'backpressure_score' logic.
brain_code = """import operator
import random
from typing import Annotated, Dict, TypedDict, List
from langgraph.graph import StateGraph, END

class Patient(TypedDict):
    name: str
    treatment: str
    value: int
    show_up_prob: float
    status: str 

class PlantState(TypedDict):
    resources: Dict[str, dict]
    schedule: List[Patient] 
    bottleneck_rate: float 
    backpressure_score: float  # <--- FIXED
    lobby_wait_time: int 
    constraints: Annotated[list, operator.add]
    decisions: Annotated[list, operator.add]
    logs: Annotated[list, operator.add]

def generate_schedule():
    treatments = [("Botox", 450, 0.95), ("Laser", 1200, 0.85), ("Filler", 800, 0.90), ("Consult", 0, 0.60)]
    names = ["Sarah L.", "Mike T.", "Jessica R.", "Amanda B.", "Chris P."]
    schedule = []
    for n in names:
        t_name, t_val, t_prob = random.choice(treatments)
        schedule.append({"name": n, "treatment": t_name, "value": t_val, "show_up_prob": t_prob, "status": "Scheduled"})
    return schedule

def run_physics_engine(state: PlantState):
    resources = state['resources']
    checkout_friction = resources['Checkout']['util']
    laser_load = resources['Laser Room']['util']
    numbing_load = resources['Numbing Room']['util']
    
    raw_laser_speed = 1.0 - laser_load
    effective_laser_speed = raw_laser_speed * (1.0 - (checkout_friction * 0.5))
    system_rate = min(effective_laser_speed, 1.0 - numbing_load, 1.0 - resources['Reception']['util'])
    
    lobby_queue = resources['Reception']['queue']
    if system_rate < 0.05: wait_time = lobby_queue * 45 
    else: wait_time = int(lobby_queue * (10 / (system_rate + 0.1)))

    state['bottleneck_rate'] = system_rate
    state['backpressure_score'] = checkout_friction * 100
    state['lobby_wait_time'] = wait_time
    return {"logs": ["Physics calculated"]}

def run_jonah(state: PlantState):
    constraints = []
    if state['backpressure_score'] > 40: constraints.append("CONSTRAINT: Checkout Friction")
    if state['lobby_wait_time'] > 20: constraints.append("CONSTRAINT: Lobby Overflow")
    return {"constraints": constraints}

def run_ralph(state: PlantState):
    decisions = []
    schedule = state['schedule']
    if state['bottleneck_rate'] < 0.3:
        for p in schedule:
            if p['show_up_prob'] < 0.80: decisions.append(f"DEPLOY EVE AGENT: Virtual Consult for {p['name']}")
    if not decisions: decisions.append("RELEASE JOB: Schedule Optimized.")
    return {"decisions": decisions}

workflow = StateGraph(PlantState)
workflow.add_node("physics", run_physics_engine)
workflow.add_node("jonah", run_jonah)
workflow.add_node("ralph", run_ralph)
workflow.set_entry_point("physics")
workflow.add_edge("physics", "jonah")
workflow.add_edge("jonah", "ralph")
workflow.add_edge("ralph", END)
app = workflow.compile()
"""

with open("orchestrator.py", "w") as f:
    f.write(brain_code)
print("   [+] Brain Restored (Backpressure Logic Active)")

# 2. UPDATE THE DASHBOARD (The Divine Feminine)
# Changing aesthetics to Rose Gold, Pearl, and Soft Light.
dashboard_code = """import streamlit as st
import pandas as pd
from orchestrator import app as logic_engine, generate_schedule

st.set_page_config(page_title="EVE | The Divine Frame", layout="wide", page_icon="✨")

st.markdown(\"\"\"
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
\"\"\", unsafe_allow_html=True)

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
"""

with open("eve_dashboard.py", "w") as f:
    f.write(dashboard_code)
print("   [+] Aesthetic Applied (Rose Gold & Pearl)")
print("✨ RE-GENESIS COMPLETE.")
