"""
Test script to get a real user token and test the backend
"""
import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


async def get_user_token(email: str, password: str):
    """Get JWT token by logging in as a user"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            json={
                "email": email,
                "password": password
            },
            headers={
                "apikey": SUPABASE_SECRET_KEY,
                "Content-Type": "application/json"
            }
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"Login failed: {response.status_code}")
            print(response.text)
            return None


async def test_backend(token: str):
    """Test backend endpoints with token"""
    async with httpx.AsyncClient() as client:
        # Test student profile
        print("\n=== Testing /student/profile ===")
        response = await client.get(
            "http://localhost:8000/student/profile",
            headers={"Authorization": f"Bearer {token}"}
        )
        print(f"Status: {response.status_code}")
        try:
            print(response.json())
        except Exception as e:
            print(f"JSON decode error: {e}")
            print(f"Raw response: {response.text}")

        # Test assessment submission
        print("\n=== Testing /student/assessment ===")
        answers = {
            **{f"A{i}": 4 for i in range(1, 6)},
            **{f"I{i}": 3 for i in range(1, 7)},
            **{f"T{i}": 4 for i in range(1, 7)},
            **{f"V{i}": 5 for i in range(1, 7)},
            **{f"W{i}": 3 for i in range(1, 5)}
        }
        print(answers)

        response = await client.post(
            "http://localhost:8000/student/assessment",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={"answers": answers}
        )
        print(f"Status: {response.status_code}")
        try:
            print(response.text)
            print(response.json())
        except Exception as e:
            print(f"JSON decode error: {e}")
            print(f"Raw response: {response.text}")


async def main():
    print("=== Getting User Token ===")

    # Login as student
    email = "student@testschool.edu"
    password = 'password'

    token = await get_user_token(email, password)

    if token:
        print(f"\n✅ Got token: {token[:50]}...")
        print("\n=== Testing Backend ===")
        await test_backend(token)
    else:
        print("❌ Failed to get token")


if __name__ == "__main__":
    asyncio.run(main())