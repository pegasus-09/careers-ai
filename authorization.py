"""
Role-based authorization helpers
"""
from typing import Optional
from fastapi import HTTPException, Depends

from auth import AuthUser, get_current_user
from database import get_user_profile, Profile, UserRole


async def require_profile(
    user: AuthUser = Depends(get_current_user)
) -> Profile:
    """
    Get the full profile for the authenticated user.
    Raises 404 if profile doesn't exist.
    """
    profile = await get_user_profile(user.user_id)
    
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="User profile not found. Please contact your administrator."
        )
    
    return profile


def require_role(*allowed_roles: str):
    """
    Decorator factory to require specific roles.
    
    Usage:
        @app.get("/admin/dashboard")
        async def admin_dashboard(profile: Profile = Depends(require_role(UserRole.ADMIN))):
            ...
    """
    async def role_checker(profile: Profile = Depends(require_profile)) -> Profile:
        if profile.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}"
            )
        return profile
    
    return role_checker


async def require_admin(profile: Profile = Depends(require_profile)) -> Profile:
    """Require admin role"""
    if profile.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return profile


async def require_teacher(profile: Profile = Depends(require_profile)) -> Profile:
    """Require teacher role"""
    if profile.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teacher access required")
    return profile


async def require_student(profile: Profile = Depends(require_profile)) -> Profile:
    """Require student role"""
    if profile.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Student access required")
    return profile


async def require_teacher_or_admin(profile: Profile = Depends(require_profile)) -> Profile:
    """Require teacher or admin role"""
    if profile.role not in [UserRole.TEACHER, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Teacher or Admin access required")
    return profile
