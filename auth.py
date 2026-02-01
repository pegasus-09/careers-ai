"""
Authentication middleware for Supabase using REST API
Verifies tokens by calling Supabase auth endpoint
"""
from typing import Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from supabase_client import get_supabase, SupabaseClient

security = HTTPBearer()


class AuthUser(BaseModel):
    """Authenticated user information"""
    user_id: str
    email: Optional[str] = None
    token: str  # Store token to pass to queries


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    supabase: SupabaseClient = Depends(get_supabase)
) -> AuthUser:
    """
    Verify user JWT token by calling Supabase auth endpoint.
    Supabase handles the verification using the new key format.
    
    Args:
        credentials: HTTP Authorization credentials with Bearer token
        supabase: Supabase client instance
        
    Returns:
        AuthUser: Authenticated user information with token
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials
    
    try:
        # Let Supabase verify the token
        user_data = await supabase.verify_user_token(token)
        
        if not user_data or not user_data.get("user_id"):
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        return AuthUser(
            user_id=user_data["user_id"],
            email=user_data.get("email"),
            token=token  # Pass token along for RLS queries
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}"
        )

