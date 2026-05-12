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

# Get namespaces from strategies
strategies = client.get_memory_strategies(MEMORY_ID)
namespaces = []
for s in strategies:
    strategy_id = s.get("memoryStrategyId") or s.get("id") or s.get("strategyId") or ""
    for ns in s.get("namespaces", []):
        resolved = (ns
            .replace("{memoryStrategyId}", strategy_id)
            .replace("{memoryStrategyid}", strategy_id)
            .replace("{actorId}", MEMORY_USER_ID)
            .replace("{actorid}", MEMORY_USER_ID)
            .replace("{sessionId}", MEMORY_SESSION_ID)
            .replace("{sessionid}", MEMORY_SESSION_ID)
        )
        namespaces.append((s.get("name"), resolved))

# Search and print only the memory text
print("\nStored Preferences:\n")
queries = ["hotel preference", "food diet", "budget", "travel interests"]

found_any = False
for strategy_name, ns in namespaces:
    for query in queries:
        try:
            results = client.retrieve_memories(
                memory_id=MEMORY_ID,
                namespace=ns,
                query=query,
                top_k=3
            )
            for r in results:
                content = r.get("content", {})
                text = content.get("text", "") if isinstance(content, dict) else ""
                if text:
                    print(f"  • {text}")
                    found_any = True
        except Exception:
            pass

if not found_any:
    print("  No preferences found yet. Run the agent first and wait 1-2 minutes.")

print("\n" + "=" * 50)
