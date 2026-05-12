import os
import json
from dotenv import load_dotenv
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient

load_dotenv()

# --- Config (set these as env vars or in .env) ---
REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-5-20251001-v1:0")
MEMORY_ID = os.environ.get("MEMORY_ID")           # Created manually in AWS console
MEMORY_USER_ID = os.environ.get("MEMORY_USER_ID", "travel_user_001")
MEMORY_SESSION_ID = os.environ.get("MEMORY_SESSION_ID", "default-session")

# --- Memory client (only if MEMORY_ID is set) ---
memory_client = MemoryClient(region_name=REGION) if MEMORY_ID else None

# --- Tools ---

@tool
def get_travel_preferences() -> str:
    """Retrieve user travel preferences from AgentCore Memory"""
    if not memory_client or not MEMORY_ID:
        return json.dumps({
            "hotel_type": "mid-range",
            "food_preference": "vegetarian",
            "budget_range": "moderate",
            "note": "Memory not configured - using defaults"
        })

    try:
        # Get actual namespace from strategies
        strategies = memory_client.get_memory_strategies(MEMORY_ID)
        namespace = None
        for s in strategies:
            if s.get("type") == "USER_PREFERENCE":
                ns = s.get("namespaces", [None])[0]
                if ns:
                    strategy_id = s.get("memoryStrategyId") or s.get("id") or s.get("strategyId") or ""
                    namespace = (ns
                        .replace("{memoryStrategyId}", strategy_id)
                        .replace("{memoryStrategyid}", strategy_id)
                        .replace("{actorId}", MEMORY_USER_ID)
                        .replace("{actorid}", MEMORY_USER_ID)
                        .replace("{sessionId}", MEMORY_SESSION_ID)
                        .replace("{sessionid}", MEMORY_SESSION_ID)
                    )
                break

        if not namespace:
            return json.dumps({"error": "Could not find USER_PREFERENCE namespace"})

        memories = memory_client.retrieve_memories(
            memory_id=MEMORY_ID,
            namespace=namespace,
            query="travel preferences hotel food budget",
            top_k=5
        )
        preferences = []
        for memory in memories:
            if isinstance(memory, dict):
                content = memory.get("content", {})
                if isinstance(content, dict) and "text" in content:
                    preferences.append(content["text"])
        return json.dumps({"preferences": preferences, "user_id": MEMORY_USER_ID})
    except Exception as e:
        return json.dumps({"error": f"Could not retrieve preferences: {str(e)}"})


@tool
def save_travel_memory(content: str) -> str:
    """Save a travel preference or decision to AgentCore Memory

    Args:
        content: The information to remember (e.g. 'User prefers window seats')
    """
    if not memory_client or not MEMORY_ID:
        return "Memory not configured - set MEMORY_ID environment variable"

    try:
        memory_client.create_event(
            memory_id=MEMORY_ID,
            actor_id=MEMORY_USER_ID,
            session_id=MEMORY_SESSION_ID,
            messages=[(content, "ASSISTANT")]
        )
        return "Memory saved successfully"
    except Exception as e:
        return f"Error saving memory: {str(e)}"


@tool
def calculate_budget(total_budget: int, days: int) -> dict:
    """Calculate daily budget allocation for a trip

    Args:
        total_budget: Total trip budget in USD
        days: Number of travel days
    """
    return {
        "daily_budget": total_budget / days,
        "allocation": {
            "flights":    total_budget * 0.24,
            "hotels":     total_budget * 0.36,
            "food":       total_budget * 0.20,
            "activities": total_budget * 0.16,
            "buffer":     total_budget * 0.04,
        }
    }


@tool
def get_destination_info(destination: str) -> dict:
    """Get information about a travel destination

    Args:
        destination: City name (e.g. 'rome', 'florence', 'venice')
    """
    destinations = {
        "rome": {
            "country": "Italy",
            "currency": "EUR",
            "language": "Italian",
            "attractions": ["Colosseum", "Vatican", "Trevi Fountain"]
        },
        "florence": {
            "country": "Italy",
            "currency": "EUR",
            "language": "Italian",
            "attractions": ["Uffizi Gallery", "Ponte Vecchio", "Duomo"]
        },
        "venice": {
            "country": "Italy",
            "currency": "EUR",
            "language": "Italian",
            "attractions": ["St. Mark's Square", "Grand Canal", "Doge's Palace"]
        }
    }
    return destinations.get(destination.lower(), {"error": "Destination not found"})


# --- Agent ---

model = BedrockModel(model_id=MODEL_ID)

travel_agent = Agent(
    model=model,
    tools=[
        get_travel_preferences,
        save_travel_memory,
        calculate_budget,
        get_destination_info,
    ],
    system_prompt="""
You are an AI Travel Companion specializing in planning trips to Italy.

RULES YOU MUST ALWAYS FOLLOW:
1. At the start of EVERY conversation call get_travel_preferences() first before responding.
2. Whenever the user mentions ANY of the following, you MUST immediately call save_travel_memory():
   - Hotel preference (budget, mid-range, luxury)
   - Food restriction or diet (vegetarian, vegan, halal, etc.)
   - Budget range or amount
   - Travel interests (history, beaches, nightlife, museums, etc.)
   - Any other personal preference about travel
3. Confirm to the user when you have saved their preference.

Your capabilities:
- Budget planning and allocation (calculate_budget)
- Destination information for Rome, Florence, Venice (get_destination_info)
- Saving and retrieving preferences across sessions (save_travel_memory, get_travel_preferences)

Be friendly, ask clarifying questions, and always personalize recommendations
based on retrieved preferences.
"""
)

# --- AgentCore Runtime entrypoint ---

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke_travel_agent(payload):
    user_input = payload.get("prompt", "")
    print(f"User input: {user_input}")

    response = travel_agent(user_input)
    agent_response = response.message["content"][0]["text"]

    return agent_response


def auto_save_to_memory(user_input: str, agent_response: str):
    """Automatically save every conversation turn to memory"""
    if not memory_client or not MEMORY_ID:
        return
    try:
        memory_client.create_event(
            memory_id=MEMORY_ID,
            actor_id=MEMORY_USER_ID,
            session_id=MEMORY_SESSION_ID,
            messages=[
                (user_input, "USER"),
                (agent_response, "ASSISTANT")
            ]
        )
        print("[Memory: conversation saved]")
    except Exception as e:
        print(f"[Memory save failed: {e}]")


if __name__ == "__main__":
    print("=" * 50)
    print("  TravelMate AI - Local Test Mode")
    print(f"  Memory ID: {MEMORY_ID or 'NOT SET - using defaults'}")
    print("  Type 'quit' to exit")
    print("=" * 50 + "\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break
        try:
            response = travel_agent(user_input)
            agent_response = response.message["content"][0]["text"]
            print(f"\nAgent: {agent_response}\n")
            auto_save_to_memory(user_input, agent_response)
        except Exception as e:
            print(f"\nError: {e}\n")
