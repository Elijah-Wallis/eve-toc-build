import operator
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
