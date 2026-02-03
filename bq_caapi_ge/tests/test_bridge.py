"""Test utility for verifying the A2A Bridge functionality."""

import asyncio
import json

import httpx


async def test_endpoint(path: str, query: str) -> None:
    """Test a specific bridge endpoint with a query.

    Args:
        path: The path to the agent (e.g., /orders).
        query: The user query to test.
    """
    print(f"\nTesting {path} with query: '{query}'")
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # 1. Test GET (Discovery)
            resp_get = await client.get(f"http://localhost:8000{path}")
            print(f"GET {path} Response Status: {resp_get.status_code}")

            # 2. Test POST (Chat)
            resp_post = await client.post(
                f"http://localhost:8000{path}/chat", json={"message": {"text": query}}
            )
            print(f"POST {path}/chat Response Status: {resp_post.status_code}")
            if resp_post.status_code == 200:
                print(json.dumps(resp_post.json(), indent=2))
            else:
                print(f"Error Content: {resp_post.text}")
        except Exception as e:
            print(f"Request Exception: {type(e).__name__}: {e}")


async def main() -> None:
    """Run tests for both agent endpoints."""
    await test_endpoint("/orders", "How many orders are in the 'complete' status?")
    await test_endpoint("/inventory", "What is the name of the product with ID 1?")


if __name__ == "__main__":
    asyncio.run(main())
