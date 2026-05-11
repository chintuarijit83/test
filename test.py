import boto3
from bedrock_agentcore.memory import MemoryClient

REGION = "us-east-1"
MEMORY_ID = "TravelMateMemory-1424245"

print("Step 1: Checking AWS credentials...")
try:
    sts = boto3.client("sts", region_name=REGION)
    identity = sts.get_caller_identity()
    print(f"  Connected as: {identity['Arn']}")
except Exception as e:
    print(f"  FAILED: {e}")
    exit(1)

print("\nStep 2: Connecting to AgentCore Memory...")
try:
    client = MemoryClient(region_name=REGION)
    print("  Memory client created")
except Exception as e:
    print(f"  FAILED: {e}")
    exit(1)

print("\nStep 3: Fetching memory details...")
try:
    memories = client.list_memories()
    match = next((m for m in memories if MEMORY_ID in str(m)), None)
    if match:
        print(f"  Found: {match}")
    else:
        print(f"  Memory ID not found in list. All memories: {memories}")
except Exception as e:
    print(f"  FAILED: {e}")
    exit(1)

print("\nStep 4: Fetching memory strategies...")
try:
    strategies = client.get_memory_strategies(MEMORY_ID)
    for s in strategies:
        print(f"  Strategy: {s}")
except Exception as e:
    print(f"  FAILED: {e}")

print("\nAll done!")
