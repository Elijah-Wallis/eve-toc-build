import operator
from typing import Annotated, TypedDict, List
try:
    from langgraph.graph import StateGraph, END
except ImportError:
    print("Error: langgraph not installed. Run 'pip install langgraph'")

class PlantState(TypedDict):
    leads_queue: int
    chair_utilization: float
    cancellation_rate: float
    identified_constraint: str
    variance_analysis: str
    gating_decision: str
    logs: Annotated[List[str], operator.add]

def jonah_analyst(state: PlantState):
    util = state['chair_utilization']
    logs = [f"Jonah: Analyzing Plant... Utilization at {util*100}%."]
    constraint = "AESTHETICIAN_CHAIR_1" if util > 0.90 else None
    if constraint: logs.append(f"Jonah: ALERT. Constraint detected at {constraint}.")
    return {"identified_constraint": constraint, "logs": logs}

def herbie_optimizer(state: PlantState):
    constraint = state.get('identified_constraint')
    cancel_rate = state['cancellation_rate']
    logs = []
    analysis = "N/A"
    if constraint:
        if cancel_rate > 0.15:
            analysis = "High Variance (V) detected. Cancellation spike inflating Queue Time."
            logs.append(f"Herbie: {analysis}")
        else:
            analysis = "Low Variance."
            logs.append("Herbie: Variance nominal.")
    return {"variance_analysis": analysis, "logs": logs}

def ralph_scheduler(state: PlantState):
    constraint = state.get('identified_constraint')
    leads = state['leads_queue']
    logs = []
    decision = "CHOKE_INPUT" if (constraint and leads > 10) else "RELEASE_LEADS"
    logs.append(f"Ralph: Action: {decision}.")
    return {"gating_decision": decision, "logs": logs}

workflow = StateGraph(PlantState)
workflow.add_node("jonah", jonah_analyst)
workflow.add_node("herbie", herbie_optimizer)
workflow.add_node("ralph", ralph_scheduler)
workflow.set_entry_point("jonah")
workflow.add_conditional_edges("jonah", lambda x: "herbie" if x.get("identified_constraint") else "ralph", {"herbie": "herbie", "ralph": "ralph"})
workflow.add_edge("herbie", "ralph")
workflow.add_edge("ralph", END)
app = workflow.compile()

if __name__ == "__main__":
    mock_input = {"leads_queue": 15, "chair_utilization": 0.95, "cancellation_rate": 0.20, "logs": []}
    result = app.invoke(mock_input)
    print("\n--- EVE SYSTEM DIAGNOSTIC ---")
    for log in result['logs']: print(log)
    print(f"FINAL ACTION: {result['gating_decision']}")
