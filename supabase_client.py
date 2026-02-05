"""
Supabase REST API client wrapper
Uses Supabase to verify user tokens (no local JWT decoding)
"""
import os
import httpx
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL environment variable is required")
if not SUPABASE_SECRET_KEY:
    raise ValueError("SUPABASE_SECRET_KEY environment variable is required")


class SupabaseClient:
    """Simple Supabase REST API client"""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip('/')
        self.key = key
        self.client = httpx.AsyncClient(timeout=120.0)  # Increased for heavy computations

    async def verify_user_token(self, user_token: str) -> Optional[Dict]:
        """
        Verify user JWT token by calling Supabase auth endpoint.
        This lets Supabase handle token verification.
        """
        try:
            # Call Supabase auth endpoint to verify token
            response = await self.client.get(
                f"{self.url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {user_token}",
                    "apikey": self.key
                }
            )

            if response.status_code == 200:
                user_data = response.json()
                return {
                    "user_id": user_data.get("id"),
                    "email": user_data.get("email"),
                    "role": user_data.get("role")
                }
            return None

        except Exception as e:
            print(f"Token verification error: {e}")
            return None

    def get_headers(self, user_token: Optional[str] = None) -> Dict:
        """
        Get headers for Supabase requests.
        Uses secret key for admin operations, or user token for user-scoped operations.
        """
        if user_token:
            # Use user's token - RLS will apply
            return {
                "Authorization": f"Bearer {user_token}",
                "apikey": self.key,
                "Content-Type": "application/json"
            }
        else:
            # Use secret key - bypasses RLS
            return {
                "Authorization": f"Bearer {self.key}",
                "apikey": self.key,
                "Content-Type": "application/json"
            }

    def query(self, table: str, user_token: Optional[str] = None) -> 'QueryBuilder':
        """Start a query on a table"""
        return QueryBuilder(self, table, user_token)

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


class QueryBuilder:
    """SQL-like query builder for Supabase"""

    def __init__(self, client: SupabaseClient, table: str, user_token: Optional[str] = None):
        self.client = client
        self.table = table
        self.user_token = user_token
        self.url = f"{client.url}/rest/v1/{table}"
        self.params = {}
        self.method = "GET"
        self.body = None

    def select(self, columns: str = "*") -> 'QueryBuilder':
        """Select columns"""
        self.params["select"] = columns
        return self

    def eq(self, column: str, value: Any) -> 'QueryBuilder':
        """Filter: column equals value"""
        self.params[column] = f"eq.{value}"
        return self

    def in_(self, column: str, values: List[Any]) -> 'QueryBuilder':
        """Filter: column in list"""
        values_str = ",".join([f'"{v}"' if isinstance(v, str) else str(v) for v in values])
        self.params[column] = f"in.({values_str})"
        return self

    def insert(self, data: Dict) -> 'QueryBuilder':
        """Insert data"""
        self.method = "POST"
        self.body = data
        return self

    def upsert(self, data: Dict, on_conflict: str = "user_id") -> 'QueryBuilder':
        """
        Upsert data.
        on_conflict: Column name to use for conflict resolution
        """
        self.method = "POST"
        self.body = data
        self.on_conflict = on_conflict
        self.params["on_conflict"] = on_conflict
        return self

    def update(self, data: Dict) -> 'QueryBuilder':
        """Update data"""
        self.method = "PATCH"
        self.body = data
        return self

    def delete(self) -> 'QueryBuilder':
        """Delete data"""
        self.method = "DELETE"
        return self

    async def execute(self) -> Dict:
        """Execute the query"""
        try:
            headers = self.client.get_headers(self.user_token)

            if self.method == "GET":
                response = await self.client.client.get(
                    self.url,
                    headers=headers,
                    params=self.params
                )
            elif self.method == "POST":
                # For upsert, add resolution header
                post_headers = {**headers}
                if hasattr(self, 'on_conflict'):
                    post_headers["Prefer"] = f"resolution=merge-duplicates"
                else:
                    post_headers["Prefer"] = "return=representation"

                response = await self.client.client.post(
                    self.url,
                    headers=post_headers,
                    params=self.params,
                    json=self.body
                )
            elif self.method == "PATCH":
                response = await self.client.client.patch(
                    self.url,
                    headers={**headers, "Prefer": "return=representation"},
                    params=self.params,
                    json=self.body
                )
            elif self.method == "DELETE":
                response = await self.client.client.delete(
                    self.url,
                    headers=headers,
                    params=self.params
                )

            response.raise_for_status()

            if response.status_code == 204:
                return {"data": [], "error": None}

            # Handle empty responses (common with upserts)
            if not response.text or response.text.strip() == "":
                print(f"[DEBUG] Empty response with status {response.status_code} - treating as success")
                return {"data": [], "error": None}

            # Try to parse JSON
            try:
                data = response.json()
                return {"data": data if isinstance(data, list) else [data], "error": None}
            except Exception as json_err:
                # If JSON parsing fails, return the raw text
                print(f"[ERROR] JSON decode failed. Status: {response.status_code}")
                print(f"[ERROR] Response text: {response.text[:500]}")
                return {"data": [], "error": f"Invalid JSON response: {response.text[:200]}"}

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if hasattr(e, 'response') else str(e)
            print(f"HTTP Error: {e.response.status_code} - {error_detail}")
            return {"data": [], "error": error_detail}
        except Exception as e:
            print(f"Exception: {str(e)}")
            return {"data": [], "error": str(e)}


# Global client instance
supabase_client = SupabaseClient(SUPABASE_URL, SUPABASE_SECRET_KEY)


async def get_supabase() -> SupabaseClient:
    """Dependency to get Supabase client"""
    return supabase_client
