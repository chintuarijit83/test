import os
from dotenv import load_dotenv
from bedrock_agentcore.memory import MemoryClient

load_dotenv()

REGION = os.environ.get("AWS_REGION", "us-east-1")
MEMORY_ID = os.environ.get("MEMORY_ID", "TravelMateMemory-1424245")
MEMORY_USER_ID = os.environ.get("MEMORY_USER_ID", "travel_user_001")
MEMORY_SESSION_ID = os.environ.get("MEMORY_SESSION_ID", "default-session")

client = MemoryClient(region_name=REGION)

print("=" * 50)
print(f"  Memory ID : {MEMORY_ID}")
print(f"  User ID   : {MEMORY_USER_ID}")
print("=" * 50)

# Get only USER_PREFERENCE namespace
strategies = client.get_memory_strategies(MEMORY_ID)
preference_namespace = None
for s in strategies:
    if s.get("type") == "USER_PREFERENCE":
        strategy_id = s.get("memoryStrategyId") or s.get("id") or s.get("strategyId") or ""
        ns = s.get("namespaces", [None])[0]
        if ns:
            preference_namespace = (ns
                .replace("{memoryStrategyId}", strategy_id)
                .replace("{memoryStrategyid}", strategy_id)
                .replace("{actorId}", MEMORY_USER_ID)
                .replace("{actorid}", MEMORY_USER_ID)
                .replace("{sessionId}", MEMORY_SESSION_ID)
                .replace("{sessionid}", MEMORY_SESSION_ID)
            )
        break

if not preference_namespace:
    print("\nNo USER_PREFERENCE strategy found.")
    exit(1)

# Retrieve and deduplicate
print("\nStored Preferences:\n")
try:
    results = client.retrieve_memories(
        memory_id=MEMORY_ID,
        namespace=preference_namespace,
        query="travel preferences hotel food budget interests",
        top_k=10
    )

    seen = set()
    found_any = False
    for r in results:
        content = r.get("content", {})
        text = content.get("text", "") if isinstance(content, dict) else ""
        if text and text not in seen:
            seen.add(text)
            print(f"  • {text}")
            found_any = True

    if not found_any:
        print("  No preferences found yet. Run the agent first and wait 1-2 minutes.")

except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 50)
