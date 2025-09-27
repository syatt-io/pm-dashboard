#!/usr/bin/env python3
"""Test script to validate GPT-5 model access."""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load environment variables
load_dotenv()

def test_gpt5():
    """Test if GPT-5 model is accessible."""
    api_key = os.getenv("OPENAI_API_KEY")

    models_to_test = ["gpt-5", "gpt-5-mini", "gpt-5-nano"]

    for model in models_to_test:
        print(f"\nTesting model: {model}")
        print("-" * 40)
        try:
            llm = ChatOpenAI(
                model=model,
                temperature=0.7,
                max_tokens=50,
                api_key=api_key
            )

            response = llm.invoke("Tell me a very short joke.")

            if hasattr(response, 'content'):
                print(f"✅ SUCCESS: {model} is working!")
                print(f"Response: {response.content[:100]}...")
            else:
                print(f"✅ SUCCESS: {model} returned response")
                print(f"Response: {str(response)[:100]}...")

        except Exception as e:
            print(f"❌ FAILED: {model}")
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_gpt5()