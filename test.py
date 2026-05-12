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

# Step 1: Get strategies and print everything raw
print("\n[1] Raw strategy details...\n")
strategies = []
try:
    strategies = client.get_memory_strategies(MEMORY_ID)
    for s in strategies:
        print(f"  Full strategy object: {s}\n")
except Exception as e:
    print(f"  Error: {e}")
    exit(1)

# Step 2: Build namespaces by replacing ALL placeholders
print("=" * 50)
print("\n[2] Building namespaces...\n")

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
        print(f"  Raw      : {ns}")
        print(f"  Resolved : {resolved}\n")
        namespaces.append((s.get("name"), resolved))

# Step 3: Search memories using resolved namespaces
print("=" * 50)
print("\n[3] Searching stored memories...\n")

queries = [
    "hotel preference",
    "food vegetarian",
    "budget",
    "travel destination",
]

for strategy_name, ns in namespaces:
    print(f"  Strategy : {strategy_name}")
    print(f"  Namespace: {ns}")
    for query in queries:
        try:
            results = client.retrieve_memories(
                memory_id=MEMORY_ID,
                namespace=ns,
                query=query,
                top_k=3
            )
            if results:
                for r in results:
                    content = r.get("content", {})
                    text = content.get("text", "") if isinstance(content, dict) else str(content)
                    if text:
                        print(f"    [{query}] → {text}")
        except Exception as e:
            print(f"    [{query}] → Error: {e}")
    print()

print("=" * 50)
print("Done.")
