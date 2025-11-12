#!/usr/bin/env python3
"""Check if specific Jira tickets exist in Pinecone."""

import os
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX_NAME", "agent-pm-context"))

# First check what metadata is available
print("Checking metadata structure...")
sample_result = index.query(
    vector=[0.0] * 1536,
    filter={"issue_key": {"$eq": "SUBS-623"}},
    top_k=1,
    include_metadata=True,
)
if sample_result.matches:
    print("\nMetadata fields available:")
    for key in sample_result.matches[0].metadata.keys():
        print(f"  - {key}")
    print()

# List of SearchSpring epic tickets to check
tickets_to_check = [
    "SUBS-617",  # Epic itself
    "SUBS-623",
    "SUBS-625",
    "SUBS-627",
    "SUBS-640",  # Mentioned in summary
    # Add more if you know them
    "SUBS-618",
    "SUBS-619",
    "SUBS-620",
    "SUBS-621",
    "SUBS-622",
    "SUBS-624",
    "SUBS-626",
    "SUBS-628",
    "SUBS-629",
    "SUBS-630",
    "SUBS-631",
    "SUBS-632",
    "SUBS-633",
    "SUBS-634",
    "SUBS-635",
]

print("Checking Pinecone for SearchSpring tickets...")
print("=" * 80)

found = []
not_found = []

for ticket_key in tickets_to_check:
    # Query by metadata filter for this specific ticket
    try:
        results = index.query(
            vector=[0.0] * 1536,  # Dummy vector, we only care about metadata filter
            filter={"issue_key": {"$eq": ticket_key}},
            top_k=1,
            include_metadata=True,
        )

        if results.matches and len(results.matches) > 0:
            match = results.matches[0]
            metadata = match.metadata
            found.append(ticket_key)
            print(f"✅ {ticket_key:12} - {metadata.get('summary', 'N/A')[:60]}")
            print(
                f"   Status: {metadata.get('status', 'N/A')} | Updated: {metadata.get('updated', 'N/A')[:10]}"
            )
        else:
            not_found.append(ticket_key)
            print(f"❌ {ticket_key:12} - NOT IN PINECONE")
    except Exception as e:
        print(f"⚠️  {ticket_key:12} - Error querying: {e}")
        not_found.append(ticket_key)

print("=" * 80)
print(f"\n📊 Summary:")
print(f"   Found: {len(found)} tickets")
print(f"   Not Found: {len(not_found)} tickets")

if not_found:
    print(f"\n❌ Missing tickets: {', '.join(not_found)}")
