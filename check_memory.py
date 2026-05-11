import os
from dotenv import load_dotenv
from bedrock_agentcore.memory import MemoryClient

load_dotenv()

REGION = os.environ.get("AWS_REGION", "us-east-1")
MEMORY_ID = os.environ.get("MEMORY_ID", "TravelMateMemory-1424245")
MEMORY_USER_ID = os.environ.get("MEMORY_USER_ID", "travel_user_001")

client = MemoryClient(region_name=REGION)

print("=" * 50)
print(f"  Memory ID : {MEMORY_ID}")
print(f"  User ID   : {MEMORY_USER_ID}")
print("=" * 50)

# Step 1: Get actual namespaces from memory strategies
print("\n[1] Fetching memory strategies and namespaces...\n")
namespaces = []
try:
    strategies = client.get_memory_strategies(MEMORY_ID)
    for s in strategies:
        print(f"  Strategy : {s.get('name')} ({s.get('type')})")
        for ns in s.get("namespaces", []):
            # Replace placeholders with actual user ID
            actual_ns = ns.replace("{actorId}", MEMORY_USER_ID).replace("{sessionId}", "default-session")
            print(f"  Namespace: {actual_ns}")
            namespaces.append(actual_ns)
        print()
except Exception as e:
    print(f"  Error fetching strategies: {e}")

if not namespaces:
    print("No namespaces found. Cannot retrieve memories.")
    exit(1)

# Step 2: Search each namespace
print("=" * 50)
print("\n[2] Searching stored memories...\n")

queries = [
    "hotel preference",
    "food diet vegetarian",
    "budget amount",
    "travel interests destinations",
]

for ns in namespaces:
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
