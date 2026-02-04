from pyvis.network import Network
import os

def generate_holistic_hologram():
    """
    Manifests the Eve Ontology as a Holistic Neural Pathway.
    Mapping: Brain, Agents, Organs, and External APIs.
    Aesthetic: Bioluminescent Translucent Frame (Ref: image_134676)
    """
    net = Network(height="750px", width="100%", bgcolor="#050514", font_color="white", notebook=False)
    
    # 1. DEFINE THE ONTOLOGY NODES (Mapped from your Medspa System Design)
    nodes = [
        # THE DIVINE BRAIN (Cyan Glow)
        {"id": "Brain", "label": "EVE CORE\n(Orchestrator)", "group": "cns", "title": "LangGraph: Strategic Homeostasis"},
        {"id": "Physics", "label": "REFLEX\n(Physics Engine)", "group": "cns", "title": "Backpressure & Joule-Cost Analysis"},
        
        # AGENTS / ACTUATORS (Purple Glow)
        {"id": "Jonah", "label": "JONAH\n(Sensory Detection)", "group": "agent", "title": "Constraint & Inflammation Auditor"},
        {"id": "Ralph", "label": "RALPH\n(Execution)", "group": "agent", "title": "Flow Control & Gating"},
        {"id": "Retell", "label": "RETELL AI\n(The Mouth)", "group": "agent", "title": "Clinical Diagnostic Pivot"},

        # ORGANS / METABOLIC NODES (Rose/Pink Glow)
        {"id": "Mouth", "label": "RECEPTION\n(The Mouth)", "group": "organ", "title": "Nutrient Intake"},
        {"id": "Heart", "label": "LASER ROOM\n(The Heart)", "group": "organ", "title": "Primary Metabolism (Constraint)"},
        {"id": "Excretion", "label": "CHECKOUT\n(Excretion)", "group": "organ", "title": "Revenue Realization"},

        # EXTERNAL NERVES (Green Glow)
        {"id": "GHL", "label": "GHL\n(Long-Term Memory)", "group": "ext", "shape": "box"},
        {"id": "Make", "label": "MAKE.COM\n(The Synapse)", "group": "ext", "shape": "box"},
    ]

    for n in nodes:
        net.add_node(n["id"], label=n["label"], group=n["group"], title=n.get("title"), shape=n.get("shape", "dot"))

    # 2. MAP THE RELATIONSHIPS (The Pathways)
    # Mapping Data flow from GHL/Make to Retell and Ralph
    pathways = [
        ("GHL", "Brain", {"color": "#00ff99", "width": 2, "dashes": True}),
        ("Make", "Retell", {"color": "#00ff99", "width": 2}),
        ("Mouth", "Brain", {"color": "#00ffff", "width": 2}),
        ("Brain", "Physics", {"color": "#00ffff", "width": 4}),
        ("Physics", "Jonah", {"color": "#00ffff", "width": 2}),
        ("Jonah", "Ralph", {"color": "#9900ff", "width": 3}),
        ("Ralph", "Heart", {"color": "#ff3399", "width": 3, "label": "Release Flow"}),
        ("Ralph", "Retell", {"color": "#9900ff", "width": 2, "label": "Deploy Voice"}),
        ("Heart", "Excretion", {"color": "#ff3366", "width": 3}),
        ("Excretion", "Physics", {"color": "#ff3366", "width": 2, "dashes": True, "label": "Backpressure"}),
    ]
    
    for src, dst, attr in pathways:
        net.add_edge(src, dst, **attr)

    # 3. SET PHYSICS FOR "DIVINE" ANIMATION (Neuronal Floating Effect)
    net.set_options('{"nodes": {"font": {"size": 16, "face": "Helvetica Neue"}}, "physics": {"forceAtlas2Based": {"gravitationalConstant": -120, "solver": "forceAtlas2Based"}}}')
    
    tmp = "temp_holo.html"
    net.save_graph(tmp)
    with open(tmp, 'r') as f: html = f.read()
    os.remove(tmp)
    return html
