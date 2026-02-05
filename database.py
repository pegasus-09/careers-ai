"""
Database utilities using Supabase REST API client
"""
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from supabase_client import supabase_client


# Enums
class UserRole:
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


class SubjectCategory:
    STEM = "STEM"
    HUMANITIES = "Humanities"
    LANGUAGES = "Languages"
    ARTS = "Arts"
    HEALTH_PE = "Health & PE"
    VOCATIONAL = "Vocational"


class YearLevel:
    YEAR_9 = "9"
    YEAR_10 = "10"
    YEAR_11 = "11"
    YEAR_12 = "12"


# Pydantic models
class Profile(BaseModel):
    id: str
    school_id: str
    role: str
    full_name: str
    email: str
    year_level: Optional[str] = None

    class Config:
        from_attributes = True


# Utility functions
async def get_user_profile(user_id: str) -> Optional[Profile]:
    """Get user profile from database"""
    try:
        query = supabase_client.query("profiles")
        result = await query.select("*").eq("id", user_id).execute()

        if result["data"] and len(result["data"]) > 0:
            return Profile(**result["data"][0])
        return None
    except Exception as e:
        print(f"Error fetching profile: {e}")
        return None


async def upsert_assessment_result(
    user_id: str,
    school_id: str,
    raw_answers: dict,
    ranking: list,
    profile_data: dict,
    user_token: str = None
) -> bool:
    """Upsert assessment result"""
    try:
        data = {
            "user_id": user_id,
            "school_id": school_id,
            "raw_answers": raw_answers,
            "ranking": ranking,
            "profile_data": profile_data,
            "updated_at": datetime.utcnow().isoformat()
        }

        query = await supabase_client.query("assessment_results", user_token)
        result = await query.upsert(data).execute()

        # Success if no error (even if data is empty)
        return result.get("error") is None
    except Exception as e:
        print(f"Error upserting assessment: {e}")
        return False