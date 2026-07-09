"""
Debug helper - see the RAW text a real Rules KB retrieve() call returns,
before trusting rules_kb_service.py's parser to make sense of it.

Run this FIRST when testing against a real Rules KB, before running
main.py - if the parser silently returns zero rules, this tells you why
(and what the chunk actually looks like, so you can fix the parser).

Usage:
    python inspect_rules_kb.py --client-id AMAZON_PL
"""

import argparse
import json

import boto3

import config


def main():
    parser = argparse.ArgumentParser(description="Print raw Rules KB retrieve() output")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--query", default=None, help="Override the retrieval query text")
    args = parser.parse_args()

    if not config.RULES_KB_ID:
        raise SystemExit("RULES_KB_ID is not set in .env - nothing to inspect")

    query_text = args.query or f"fraud rules applicable to client {args.client_id}"
    client = boto3.client("bedrock-agent-runtime", region_name=config.AWS_REGION)

    response = client.retrieve(
        knowledgeBaseId=config.RULES_KB_ID,
        retrievalQuery={"text": query_text},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 20}},
    )

    results = response.get("retrievalResults", [])
    print(f"Query: {query_text!r}")
    print(f"{len(results)} chunk(s) returned\n")

    for i, result in enumerate(results, start=1):
        text = result.get("content", {}).get("text", "")
        score = result.get("score")
        print(f"--- chunk {i} (score={score}) ---")
        print(text)
        print()

    if not results:
        print("No chunks returned at all - check the KB is synced and the query text is reasonable.")


if __name__ == "__main__":
    main()
