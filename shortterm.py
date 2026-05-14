import os
import json
import logging
from colorama import init, Fore, Style
from dotenv import load_dotenv
from strands import Agent
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient

load_dotenv()
init(autoreset=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-5-20251001-v1:0")
MEMORY_ID = os.environ.get("MEMORY_ID", "mystmmemory-otBM7C6wjc")
SESSION_ID = "default_session"

memory_client = MemoryClient(region_name=REGION)

# ─────────────────────────────────────────
# SHORT TERM MEMORY HELPERS
# ─────────────────────────────────────────

def add_event(role: str, content: str):
    role = role.upper()
    try:
        response = memory_client.create_event(
            memory_id=MEMORY_ID,
            actor_id=role,
            session_id=SESSION_ID,
            messages=[(str(content), role)]
        )
        logger.info(Fore.MAGENTA + f"Created event: {response.get('eventId', 'unknown')}")
        return response
    except Exception as e:
        logger.error(Fore.RED + f"Failed to create event: {e}")
        return {}


def get_session_history():
    try:
        events = memory_client.list_events(
            memory_id=MEMORY_ID,
            actor_id="USER",
            session_id=SESSION_ID,
            include_payload=True,
            max_results=50
        )
        return events if isinstance(events, list) else []
    except Exception as e:
        logger.error(Fore.RED + f"list_events failed: {e}")
        return []


def reset_memory():
    for actor in ["USER", "ASSISTANT"]:
        try:
            events = memory_client.list_events(
                memory_id=MEMORY_ID,
                actor_id=actor,
                session_id=SESSION_ID,
                include_payload=False,
                max_results=100
            )
            for e in (events if isinstance(events, list) else []):
                memory_client.delete_event(
                    memoryId=MEMORY_ID,
                    sessionId=SESSION_ID,
                    eventId=e["eventId"],
                    actorId=actor
                )
        except Exception as e:
            logger.error(Fore.RED + f"reset failed for {actor}: {e}")
    logger.info(Fore.CYAN + "Memory reset complete.")


# ─────────────────────────────────────────
# AGENT (Strands)
# ─────────────────────────────────────────

model = BedrockModel(model_id=MODEL_ID)

agent = Agent(
    model=model,
    system_prompt="""
You are a helpful assistant with short term memory.
Use all prior context provided to continue the conversation naturally.
Respond only to the latest user message.
"""
)


def build_prompt_with_history(user_input: str) -> str:
    """Prepend session history to the current user message so Strands has full context"""
    events = get_session_history()
    history_lines = []
    for e in events:
        for m in e.get("payload", []):
            conv = m.get("conversational", {})
            role = conv.get("role", "")
            content = conv.get("content", {})
            text = content.get("text", "") if isinstance(content, dict) else str(content)
            if role and text:
                history_lines.append(f"{role}: {text}")

    if history_lines:
        history_text = "\n".join(history_lines)
        return f"Conversation so far:\n{history_text}\n\nUser: {user_input}"
    return user_input


# ─────────────────────────────────────────
# AGENTCORE ENTRYPOINT (for deployment)
# ─────────────────────────────────────────

@app.entrypoint
def invoke(payload):
    if isinstance(payload, (bytes, str)):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    user_input = payload.get("prompt") or payload.get("input") or ""
    if not user_input:
        return {"message": "No prompt provided."}

    if user_input.strip().lower() == "reset":
        reset_memory()
        return {"message": "Memory reset. Let's start fresh!"}

    add_event("USER", user_input)

    prompt = build_prompt_with_history(user_input)
    response = agent(prompt)
    agent_response = response.message["content"][0]["text"]

    add_event("ASSISTANT", agent_response)
    return {"message": agent_response}


# ─────────────────────────────────────────
# LOCAL INTERACTIVE LOOP (no curl needed)
# ─────────────────────────────────────────

if __name__ == "__main__":
    print(Fore.CYAN + "=" * 50)
    print(Fore.CYAN + "  MySTM Agent - Short Term Memory (Strands)")
    print(Fore.CYAN + f"  Memory ID  : {MEMORY_ID}")
    print(Fore.CYAN + f"  Session ID : {SESSION_ID}")
    print(Fore.CYAN + "  Type 'reset' to clear session memory")
    print(Fore.CYAN + "  Type 'quit'  to exit")
    print(Fore.CYAN + "=" * 50 + "\n")

    while True:
        user_input = input(Fore.GREEN + "You: " + Style.RESET_ALL).strip()

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print(Fore.YELLOW + "Goodbye!")
            break

        if user_input.lower() == "reset":
            reset_memory()
            print(Fore.YELLOW + "Memory reset. Starting fresh!\n")
            continue

        add_event("USER", user_input)

        try:
            prompt = build_prompt_with_history(user_input)
            response = agent(prompt)
            agent_response = response.message["content"][0]["text"]
            print(Fore.BLUE + "\nAgent: " + Style.RESET_ALL + f"{agent_response}\n")
            add_event("ASSISTANT", agent_response)
            logger.info(Fore.MAGENTA + f"Turn saved to short term memory → session: {SESSION_ID}")
        except Exception as e:
            print(Fore.RED + f"\nError: {e}\n")
