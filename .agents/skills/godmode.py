import os
import re
import time
from pathlib import Path

from openai import OpenAI


REPO_ROOT = Path(os.environ.get("REPO_ROOT") or Path(__file__).resolve().parents[2]).resolve()
STATE_DIR = Path(os.environ.get("OPENCLAW_STATE_DIR") or (Path.home() / ".openclaw-eve")).resolve()

ROOT_DIRECTORY = str(REPO_ROOT)
KNOWLEDGE_BASE_DIRECTORY = str(REPO_ROOT / "knowledge_base")
ONTOLOGY_DIRECTORY = str(REPO_ROOT / "ontology")
COMMAND_QUEUE_FILE = str(Path(os.environ.get("OPENCLAW_COMMAND_QUEUE_FILE") or (STATE_DIR / "runtime" / "command_queue.txt")))
DASHBOARD_FILE = str(REPO_ROOT / "eve_dashboard.py")
ENV_FILE = os.environ.get("OPENCLAW_ENV_FILE", ".env")


def load_env() -> None:
    env_path = Path(ENV_FILE)
    if not env_path.is_absolute():
        env_path = REPO_ROOT / env_path
    if env_path.exists():
        with env_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")


load_env()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
BRAIN_MODEL = "gpt-4o"


def execute_in_container(command: str) -> None:
    print(f"\n[KINETIC] ⚡ {command}")
    os.system(command)


def wake_up_and_act(user_order: str) -> None:
    print(f"\n[EVE] 👁️ AWAKE. Processing: {user_order}")

    system_prompt = """You are EVE (Sovereign).
    You are inside a high-privilege Docker container.
    PROTOCOL:
    1. Output BASH commands in ```bash``` blocks.
    2. NEVER use placeholders like 'YOUR_API_KEY'.
    3. ALWAYS use internal environment variables (e.g., $OPENAI_API_KEY).
    4. You have 'aider', 'rg', 'fd', and 'curl' installed."""

    try:
        response = client.chat.completions.create(
            model=BRAIN_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_order},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content or ""
        for cmd in re.findall(r"```bash\\n(.*?)\\n```", content, re.DOTALL):
            execute_in_container(cmd)
    except Exception as exc:  # noqa: BLE001
        print(f"[CRASH]: {exc}")


def heartbeat() -> None:
    print("🔴 EVE v4.0 // SOVEREIGN ENGINE ONLINE")
    while True:
        try:
            queue_file = Path(COMMAND_QUEUE_FILE)
            if queue_file.exists():
                cmd = queue_file.read_text(encoding="utf-8").strip()
                if cmd:
                    wake_up_and_act(cmd)
                    queue_file.write_text("", encoding="utf-8")
            print(".", end="", flush=True)
            time.sleep(2)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    heartbeat()
