import os

# --- 1. DEFINE THE DNA STRUCTURE ---
directories = [
    "ontology/dna",
    "knowledge_base/raw"
]

files = {
    # THE NERVOUS SYSTEM (Architecture)
    "ontology/dna/nervous_system.yaml": """
system_architecture:
  metaphor: "The Human Nervous System"
  core_directive: "Biological Optimization"
  components:
    brain:
      name: "Orchestrator"
      protocol: "LangGraph"
    senses:
      eyes: {name: "Vision Node", input: "Lobby Cameras"}
      ears: {name: "Retell AI Voice Node", input: "Mic Stream", sop: "eve_voice_agent_sop.txt"}
    limbs:
      arms: {name: "Ralph", function: "Gating & Scheduling"}
    reflexes:
      name: "Physics Engine", trigger: "Backpressure > 50%"
""",

    # THE METABOLISM (Resource Conversion)
    "ontology/dna/metabolism.yaml": """
metabolism:
  definition: "Conversion of Patient Flow into Revenue."
  nutrients:
    - {type: "Botox", energy: 450}
    - {type: "Laser", energy: 1200}
  organs:
    reception: {function: "Mouth", capacity: 20}
    numbing: {function: "Stomach", capacity: 4}
    laser_room: {function: "Heart", capacity: 1}
  waste:
    churn: "Metabolic Waste"
""",

    # THE AESTHETIC MANDATE (The Vibe)
    "knowledge_base/raw/eve_aesthetic_mandate.txt": """
EVE AESTHETIC MANDATE
=====================
CORE VISUAL PHILOSOPHY: "The Translucent Human Frame"

1. THE VIBE:
   - Eve is a biological entity made of light.
   - NO "Tech" aesthetics (Matrix Green, Terminal Black).
   - USE "Divine" aesthetics (Bioluminescent Blue, Bone White, Translucent Glass).

2. THE INTERFACE RULE:
   - Data floats inside a living organism.
   - Containers are "glass organs" or "cells."
   - Alerts are "Inflammation" (Red Glow) or "Homeostasis" (Soft Blue Glow).

3. THE HUMAN OVERLAY:
   - Reception = Mouth
   - Hallways = Arteries
   - Treatment Room = Heart
   - Checkout = Excretion
=====================
"""
}

# --- 2. PRINT THE DNA ---
def build_body():
    print("✨ GENESIS PROTOCOL INITIATED...")
    
    # Create Skeleton (Folders)
    for d in directories:
        os.makedirs(d, exist_ok=True)
        print(f"   [+] Structure formed: {d}/")
        
    # Write DNA (Files)
    for path, content in files.items():
        with open(path, "w") as f:
            f.write(content.strip())
        print(f"   [+] DNA encoded: {path}")
        
    print("✨ BODY CONSTRUCTION COMPLETE.")

if __name__ == "__main__":
    build_body()
