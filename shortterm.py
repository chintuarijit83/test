import os
import json
import logging
import boto3
from colorama import init, Fore, Style
from dotenv import load_dotenv
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient

load_dotenv()
init(autoreset=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
MEMORY_ID = os.environ.get("MEMORY_ID", "mystmmemory-otBM7C6wjc")
SESSION_ID = "default_session"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
memory_client = MemoryClient(region_name=REGION)


def add_event(actor_id, content):
    role = actor_id.upper()
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
        logger.error(Fore.RED + f"Failed to create event: {e}", exc_info=True)
        return {}


def reset_memory():
    for actor in ["USER", "ASSISTANT"]:
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
    logger.info(Fore.CYAN + "Memory reset complete.")


def get_merged_messages():
    events = memory_client.list_events(
        memory_id=MEMORY_ID,
        actor_id="USER",
        session_id=SESSION_ID,
        include_payload=True,
        max_results=50
    )

    merged_messages = []
    last_role = None
    buffer = []

    for e in (events if isinstance(events, list) else []):
        for m in e.get("payload", []):
            msg = m.get("conversational", {})
            role = msg.get("role", "UNKNOWN").lower()
            content = msg.get("content", {}).get("text", "")
            if role not in {"user", "assistant"}:
                continue
            if role != last_role and buffer:
                merged_messages.append({
                    "role": last_role,
                    "content": "\n".join(buffer)
                })
                buffer = []
            buffer.append(content)
            last_role = role

    if buffer and last_role:
        merged_messages.append({
            "role": last_role,
            "content": "\n".join(buffer)
        })

    # Ensure last message is from user to maintain alternation
    if merged_messages and merged_messages[-1]["role"] == "user":
        merged_messages.append({"role": "assistant", "content": ""})

    return merged_messages


def call_claude(merged_messages):
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "system": "You are a helpful assistant. Use all prior messages for context and respond only to the last user message. Don't respond to the previous messages.",
        "messages": merged_messages,
        "max_tokens": 512,
        "temperature": 0.7,
        "top_p": 0.9
    }
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(request_body).encode("utf-8"),
        contentType="application/json",
        accept="application/json"
    )
    result = json.loads(response["body"].read())
    return result.get("content", str(result))


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

    try:
        merged_messages = get_merged_messages()
        assistant_text = call_claude(merged_messages)
        add_event("ASSISTANT", assistant_text)
        return {"message": assistant_text}
    except Exception as e:
        logger.error(Fore.RED + f"Error calling Claude: {e}", exc_info=True)
        return {"message": f"Error calling Claude: {e}"}


# ─────────────────────────────────────────
# LOCAL INTERACTIVE LOOP (no curl needed)
# ─────────────────────────────────────────

if __name__ == "__main__":
    print(Fore.CYAN + "=" * 50)
    print(Fore.CYAN + "  MySTM Agent - Short Term Memory")
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
            merged_messages = get_merged_messages()
            assistant_text = call_claude(merged_messages)
            print(Fore.BLUE + "\nAgent: " + Style.RESET_ALL + f"{assistant_text}\n")
            add_event("ASSISTANT", assistant_text)
        except Exception as e:
            print(Fore.RED + f"\nError: {e}\n")
