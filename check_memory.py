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

# Check 1: List all memories stored
print("\n[1] Searching stored memories...\n")
queries = [
    "hotel preference",
    "food diet vegetarian",
    "budget amount",
    "travel interests destinations",
]

for query in queries:
    print(f"  Query: '{query}'")
    try:
        results = client.retrieve_memories(
            memory_id=MEMORY_ID,
            query=query,
            top_k=3
        )
        if results:
            for r in results:
                content = r.get("content", {})
                text = content.get("text", "") if isinstance(content, dict) else str(content)
                if text:
                    print(f"    → {text}")
        else:
            print("    → No memories found")
    except Exception as e:
        print(f"    → Error: {e}")
    print()

print("=" * 50)
print("Done.")
