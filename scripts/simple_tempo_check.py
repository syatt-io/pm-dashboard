#!/usr/bin/env python3
"""Simple script to check Tempo data in Pinecone without heavy dependencies."""

import os
from pinecone import Pinecone
from openai import OpenAI

# Get credentials from environment
PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
PINECONE_INDEX_NAME = os.environ.get('PINECONE_INDEX_NAME', 'agent-pm')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

if not PINECONE_API_KEY or not OPENAI_API_KEY:
    print("❌ Missing API keys in environment")
    exit(1)

# Initialize clients
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Get a query embedding
print("🔍 Generating query embedding...")
response = openai_client.embeddings.create(
    model="text-embedding-3-small",
    input="tempo worklogs"
)
query_embedding = response.data[0].embedding

# Query for ANY Tempo data
print("🔍 Querying Pinecone for Tempo data...\n")

filter_query = {"source": "tempo"}

results = index.query(
    vector=query_embedding,
    top_k=10,
    filter=filter_query,
    include_metadata=True
)

matches = results.get('matches', [])
print(f"✅ Found {len(matches)} Tempo worklogs in Pinecone\n")

if matches:
    print("=" * 80)
    print("📋 SAMPLE TEMPO WORKLOGS")
    print("=" * 80)

    for i, match in enumerate(matches[:5], 1):
        metadata = match.get('metadata', {})
        print(f"\n{i}. Worklog ID: {match.get('id', 'unknown')}")
        print(f"   Author: {metadata.get('author_name', 'N/A')}")
        print(f"   Issue: {metadata.get('issue_key', 'N/A')}")
        print(f"   Date: {metadata.get('start_date', 'N/A')}")
        print(f"   Hours: {float(metadata.get('time_spent_seconds', 0)) / 3600:.2f}")
        print(f"   Description: {metadata.get('description', 'N/A')[:100]}")
else:
    print("⚠️  No Tempo worklogs found - backfill may have failed")
