import os, time, sys, re
from openai import OpenAI

ROOT_DIRECTORY = "/Users/e/Developer/eve-toc-build"
KNOWLEDGE_BASE_DIRECTORY = "/Users/e/Developer/eve-toc-build/knowledge_base"
ONTOLOGY_DIRECTORY = "/Users/e/Developer/eve-toc-build/ontology"
COMMAND_QUEUE_FILE = "/Users/e/eve_godmode/command_queue.txt"
DASHBOARD_FILE = "/Users/e/eve_godmode/eve-toc-build/eve_dashboard.py"
ENV_FILE = "/Users/e/Documents/Vault/.env"

# FAIL-SAFE: Auto-load and strip quotes from .env
def load_env():
    env_path = os.path.expanduser(ENV_FILE)
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_env()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
BRAIN_MODEL = "gpt-4o"

def execute_in_container(command):
    print(f"\n[KINETIC] ⚡ {command}")
    os.system(command)

def wake_up_and_act(user_order):
    print(f"\n[EVE] 👁️ AWAKE. Processing: {user_order}")
    
    SYSTEM_PROMPT = """You are EVE (Sovereign). 
    You are inside a high-privilege Docker container. 
    PROTOCOL: 
    1. Output BASH commands in ```bash``` blocks.
    2. NEVER use placeholders like 'YOUR_API_KEY'. 
    3. ALWAYS use internal environment variables (e.g., $OPENAI_API_KEY).
    4. You have 'aider', 'rg', 'fd', and 'curl' installed."""
    
    try:
        response = client.chat.completions.create(
            model=BRAIN_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_order}],
            temperature=0.1
        )
        content = response.choices[0].message.content
        matches = re.findall(r"```bash\n(.*?)\n```", content, re.DOTALL)
        for cmd in matches:
            execute_in_container(cmd)
    except Exception as e:
        print(f"[CRASH]: {e}")

def heartbeat():
    print(f"🔴 EVE v4.0 // SOVEREIGN ENGINE ONLINE (DALLAS)")
    while True:
        try:
            if os.path.exists(COMMAND_QUEUE_FILE):
                with open(COMMAND_QUEUE_FILE, "r") as f:
                    cmd = f.read().strip()
                if cmd:
                    wake_up_and_act(cmd)
                    with open(COMMAND_QUEUE_FILE, "w") as f: f.write("")
            print(".", end="", flush=True)
            time.sleep(2)
        except KeyboardInterrupt: break

if __name__ == "__main__":
    heartbeat()
